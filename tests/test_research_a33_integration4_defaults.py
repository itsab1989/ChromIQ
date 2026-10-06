"""Integration 4 (Agent 33, 2026-10-06): ``a29-oog-darkmono-floor`` is a
Maximum accuracy default.

The factorial (ProfileEngineResearch/Findings/agent31-01-factorial.md s3.4)
adopted Agent 29b's clip floor as a default and kept Agent 29a's
``a29-blackhandover-ink`` opt-in. The default must reach the build through
the one effective token set (Agent 28), so a build that asks for NO token
runs the colorimetric B2A with the floor set; ``no-a29-oog-darkmono-floor``
turns it off; an explicitly requested other darkmono variant wins over the
default floor, so each variant still builds as on its own branch.
"""
import pytest

from benchmarks.synthetic import PRINTERS, make_chart, measure, write_ti3
from workflow.profile_engine import b2a, gamut_map, oog_clip
from workflow.profile_engine.builder import (ACCURATE_DEFAULT_TOKENS,
                                             ENGINE_CANDIDATE_TOKENS,
                                             BuildSettings,
                                             accurate_candidates,
                                             build_profile)

FLOOR = "a29-oog-darkmono-floor"
_SRC = "assets/profiles/ClayRGB1998.icm"


def test_the_floor_is_a_default_and_the_hand_over_is_not():
    assert FLOOR in ACCURATE_DEFAULT_TOKENS
    assert FLOOR in accurate_candidates(frozenset())
    assert "no-" + FLOOR in ENGINE_CANDIDATE_TOKENS
    assert FLOOR not in accurate_candidates({"no-" + FLOOR})
    for opt_in in ("a29-blackhandover-ink", "a29-blackhandover",
                   "a29-oog-darkmono", "a29-oog-darkmono-soft",
                   "a29-oog-darkmono-bpc"):
        assert opt_in in ENGINE_CANDIDATE_TOKENS
        assert opt_in not in accurate_candidates(frozenset())


def test_an_explicit_darkmono_variant_wins_over_the_default_floor():
    try:
        b2a.set_research_tokens(accurate_candidates(frozenset()),
                                is_additive=False)
        assert oog_clip.PARAMS["dm_on"] and oog_clip.PARAMS["dm_wj"] == 1.0
        b2a.set_research_tokens(accurate_candidates({"a29-oog-darkmono"}),
                                is_additive=False)
        assert oog_clip.PARAMS["dm_wj"] == oog_clip.DEFAULTS["dm_wj"]
        b2a.set_research_tokens(
            accurate_candidates({"a29-oog-darkmono-soft"}), is_additive=False)
        assert oog_clip.PARAMS["dm_wj"] == 6.0
        b2a.set_research_tokens(
            accurate_candidates({"a29-oog-darkmono-bpc"}), is_additive=False)
        assert oog_clip.PARAMS["dm_band"] == 15.0
        assert oog_clip.PARAMS["dm_wj"] == oog_clip.DEFAULTS["dm_wj"]
        b2a.set_research_tokens(accurate_candidates({"no-" + FLOOR}),
                                is_additive=False)
        assert not oog_clip.PARAMS["dm_on"]
    finally:
        b2a.set_research_tokens((), is_additive=False)


def _floor_seen_by_the_colorimetric_table(tmp_path, monkeypatch, printer,
                                          tokens=()):
    """A real Maximum accuracy build (mapped tables replaced by a stub);
    records the clip floor and clip parameters in force when the
    colorimetric B2A table is built."""
    seen = []
    real = b2a.build_b2a_clut

    def spy(*a, **kw):
        seen.append((oog_clip.dark_floor(), oog_clip.PARAMS.get("dm_on"),
                     oog_clip.PARAMS.get("dm_wj")))
        return real(*a, **kw)

    monkeypatch.setattr(b2a, "build_b2a_clut", spy)
    monkeypatch.setattr(gamut_map, "build_mapped_b2a",
                        lambda *a, **kw: {})
    p = PRINTERS[printer]
    chart = make_chart(p, 400)
    xyz, refl, _ = measure(p, chart)
    ti3 = write_ti3(tmp_path / f"{printer}.ti3", p, chart, xyz, refl)
    build_profile(ti3, tmp_path / f"{printer}.icc",
                  BuildSettings(quality="l", gammap_mode="accurate",
                                source_gamut=_SRC,
                                engine_candidates=frozenset(tokens)))
    assert seen, "the colorimetric B2A table was never built"
    return seen[0]


@pytest.mark.slow
def test_a_no_token_cmyk_build_runs_the_clip_floor(tmp_path, monkeypatch):
    floor, dm_on, dm_wj = _floor_seen_by_the_colorimetric_table(
        tmp_path, monkeypatch, "S3")
    assert dm_on and dm_wj == 1.0
    assert floor is not None and 0.0 < floor < 40.0, floor


@pytest.mark.slow
def test_a_no_token_rgb_build_runs_the_clip_floor(tmp_path, monkeypatch):
    floor, dm_on, dm_wj = _floor_seen_by_the_colorimetric_table(
        tmp_path, monkeypatch, "S1")
    assert dm_on and dm_wj == 1.0
    assert floor is not None and 0.0 <= floor < 40.0, floor


@pytest.mark.slow
def test_the_opt_out_builds_without_the_floor(tmp_path, monkeypatch):
    floor, dm_on, _ = _floor_seen_by_the_colorimetric_table(
        tmp_path, monkeypatch, "S3", tokens=("no-" + FLOOR,))
    assert floor is None and not dm_on
