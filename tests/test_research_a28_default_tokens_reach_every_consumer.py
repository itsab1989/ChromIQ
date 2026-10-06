"""Agent 28 (2026-10-06): the default-on research tokens reach EVERY reader.

Integration 3 (8624a056) resolved a Maximum accuracy build's token set
(defaults + requested - opt-outs) into a local variable in
``_build_profile_impl``, while ``gamut_map.build_mapped_b2a`` and
``f05_variant`` read the raw requested ``settings.engine_candidates``. A
default build therefore never ran a25-oracle-dev / a25-oracle-neutral (<= 4
inks) or a24-f05 (5+ inks) in its perceptual and saturation tables
(Agent 27, ProfileEngineResearch/Findings/agent27-01 s3.1). The set is now
resolved once, by ``effective_engine_candidates``, and every consumer reads
that.
"""
import ast
import dataclasses
import inspect
from pathlib import Path

import pytest

from benchmarks.synthetic import PRINTERS, make_chart, measure, write_ti3
from workflow.profile_engine import gamut_map
from workflow.profile_engine.builder import (BuildSettings,
                                             accurate_candidates,
                                             build_profile,
                                             effective_engine_candidates)

_ORACLE = {"a25-oracle-dev", "a25-oracle-neutral"}
_SRC = "assets/profiles/ClayRGB1998.icm"


def _spy_build(tmp_path, monkeypatch, printer, n_patches, tokens=()):
    """A real default Maximum accuracy build up to the mapped tables; the
    mapped-table builder is replaced by a recorder (no colprof oracle: no
    argyll_bin), which also asks f05_variant what the real one would."""
    seen = {}

    def recorder(model, meas, *a, settings=None, is_additive=False, **kw):
        seen["cands"] = frozenset(settings.engine_candidates)
        seen["neutral_axis"] = "neutral_axis" in kw
        seen["f05"] = gamut_map.f05_variant(settings, model,
                                            is_additive=is_additive,
                                            accurate=True)
        return {}

    monkeypatch.setattr(gamut_map, "build_mapped_b2a", recorder)
    p = PRINTERS[printer]
    chart = make_chart(p, n_patches)
    xyz, refl, _ = measure(p, chart)
    ti3 = write_ti3(tmp_path / f"{printer}.ti3", p, chart, xyz, refl)
    settings = BuildSettings(quality="l", gammap_mode="accurate",
                             source_gamut=_SRC,
                             engine_candidates=frozenset(tokens))
    build_profile(ti3, tmp_path / f"{printer}.icc", settings)
    # the caller's settings object is left as it was
    assert settings.engine_candidates == frozenset(tokens)
    return seen


@pytest.mark.slow
def test_a_default_cmyk_build_hands_the_oracle_tokens_to_the_gamut_map(
        tmp_path, monkeypatch):
    seen = _spy_build(tmp_path, monkeypatch, "S3", 400)
    assert _ORACLE <= seen["cands"], seen["cands"]
    assert seen["neutral_axis"]
    assert seen["f05"] is None          # 4 inks: F-05 never acts


@pytest.mark.slow
def test_an_opt_out_still_reaches_the_gamut_map(tmp_path, monkeypatch):
    seen = _spy_build(tmp_path, monkeypatch, "S3", 400,
                      tokens=("no-a25-oracle-dev",))
    assert "a25-oracle-dev" not in seen["cands"]
    assert "a25-oracle-neutral" in seen["cands"]


@pytest.mark.slow
def test_a_default_five_ink_build_runs_the_f05_black(tmp_path, monkeypatch):
    seen = _spy_build(tmp_path, monkeypatch, "S5", 500)
    assert seen["f05"] == "f05", seen


def test_the_effective_set_resolves_to_itself():
    for raw in (frozenset(), {"no-a25-oracle-dev"}, {"no-fin3", "gpfwd"},
                {"a24-l1", "no-a24-f05", "no-b2a33s"}, {"fin3"}):
        s = BuildSettings(gammap_mode="accurate",
                          engine_candidates=frozenset(raw))
        eff = effective_engine_candidates(s)
        assert accurate_candidates(eff) == accurate_candidates(raw)
        again = dataclasses.replace(s, engine_candidates=eff)
        assert effective_engine_candidates(again) == eff


def test_candidates_act_only_in_maximum_accuracy():
    for mode in ("fast", "bitexact", "argyll", ""):
        s = BuildSettings(gammap_mode=mode,
                          engine_candidates=frozenset({"a25-oracle-dev"}))
        assert effective_engine_candidates(s) == frozenset()


def test_an_explicit_f05_variant_wins_over_the_default():
    from types import SimpleNamespace
    m = SimpleNamespace(n_channels=6)
    for tok, var in gamut_map.F05_TOKENS.items():
        s = BuildSettings(gammap_mode="accurate",
                          engine_candidates=frozenset({tok}))
        s = dataclasses.replace(
            s, engine_candidates=effective_engine_candidates(s))
        assert gamut_map.f05_variant(s, m, is_additive=False,
                                     accurate=True) == var
    s = BuildSettings(gammap_mode="accurate",
                      engine_candidates=frozenset({"no-a24-f05"}))
    s = dataclasses.replace(s, engine_candidates=effective_engine_candidates(s))
    assert gamut_map.f05_variant(s, m, is_additive=False,
                                 accurate=True) is None


def test_the_build_resolves_the_set_before_any_reader():
    from workflow.profile_engine import builder
    src = inspect.getsource(builder._build_profile_impl)
    first = src.index("settings = _with_effective_candidates(settings)")
    assert first < src.index("_will_use_colprof_oracle(meas, settings)")
    assert first < src.index("build_mapped_b2a")


# --- the engine-OFF path: stock colprof, untouched ---------------------------

def test_the_colprof_path_imports_nothing_from_the_engine():
    import workflow.profile_builder as pb
    tree = ast.parse(Path(pb.__file__).read_text(encoding="utf-8"))
    mods = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            mods.add(node.module)
        elif isinstance(node, ast.Import):
            mods.update(a.name for a in node.names)
    assert not [m for m in mods if "profile_engine" in m], mods
    assert "engine_candidates" not in Path(pb.__file__).read_text(encoding="utf-8")


def test_the_colprof_argv_is_unchanged():
    from workflow.profile_builder import ProfileBuilder, ProfileParams
    b = ProfileBuilder.__new__(ProfileBuilder)
    args = b._build_args(ProfileParams(ti3_path=Path("/x/chart.ti3"),
                                       gamut_src="/x/src.icm"))
    # pinned on research-integration-3 (8624a056)
    assert args[:6] == ["-D", "chart", "-al", "-qm", "-s", "/x/src.icm"]
    assert not [a for a in args if "a25" in a or "a24" in a]
