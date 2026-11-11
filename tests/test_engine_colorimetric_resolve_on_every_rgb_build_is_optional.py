"""The colorimetric re-solve on every RGB build (token x2-smoothexact-always,
workflow/profile_engine/b2a.py A44B_ALWAYS_TOKEN) is a CANDIDATE, off by
default:

* today the RGB colorimetric table is re-solved by a44b-smoothexact only
  when a44-exactkeep restored at least one node; that count is zero or one
  on the inkjets, so re-read noise switches a whole-table step on and off.
  With the token the re-solve runs on every RGB Maximum accuracy build;
* off by default, and with it off nothing in a build changes;
* on, an RGB profile differs in the Colorimetric B2A1 table and in nothing
  else (Perceptual, Saturation and every A2B table byte for byte the same);
* an ink device (CMYK here) is not touched at all;
* the profile's bytes do not depend on the worker count;
* it changes WHEN smooth_exact runs, not what it does: without
  a44b-smoothexact (or a44-exactkeep) there is nothing to run.

The builds are slow (the colprof oracle runs in each): --runslow only. The
suite runs with CHROMIQ_ENGINE_THREADS=1; the worker counts here are set
through BuildSettings.engine_workers.
"""
from __future__ import annotations

import inspect
import shutil
import struct
from datetime import datetime
from pathlib import Path

import pytest

from core.resource_path import argyll_binary
from workflow.profile_engine import b2a
from workflow.profile_engine import builder as B

TOKEN = "x2-smoothexact-always"
KEPT = "Exact inversion kept at"
SMOOTHED = "Colorimetric table smoothed on its own branches"


# ------------------------------------------------------------- the token
def test_the_token_is_known_has_an_off_switch_and_is_not_a_default():
    assert b2a.A44B_ALWAYS_TOKEN == TOKEN
    assert TOKEN in B.ENGINE_CANDIDATE_TOKENS
    assert "no-" + TOKEN in B.ENGINE_CANDIDATE_TOKENS
    assert TOKEN not in B.ACCURATE_DEFAULT_TOKENS
    plain = B.effective_engine_candidates(
        B.BuildSettings(gammap_mode="accurate"))
    assert TOKEN not in plain


def test_the_token_reaches_a_maximum_accuracy_build_only_when_asked_for():
    plain = B.effective_engine_candidates(
        B.BuildSettings(gammap_mode="accurate"))
    on = B.effective_engine_candidates(B.BuildSettings(
        gammap_mode="accurate", engine_candidates=frozenset({TOKEN})))
    assert on == plain | {TOKEN}
    off_again = B.effective_engine_candidates(B.BuildSettings(
        gammap_mode="accurate",
        engine_candidates=frozenset({TOKEN, "no-" + TOKEN})))
    assert TOKEN not in off_again
    assert off_again - {"no-" + TOKEN} == plain
    for mode in ("fast", "argyll"):
        assert B.effective_engine_candidates(B.BuildSettings(
            gammap_mode=mode,
            engine_candidates=frozenset({TOKEN}))) == frozenset()


def test_it_acts_on_rgb_devices_in_maximum_accuracy_with_the_resolve_on():
    on = B.accurate_candidates(frozenset({TOKEN}))
    act = b2a.smooth_exact_always
    assert act(on, accurate=True, is_additive=True, n=3)
    assert not act(on, accurate=True, is_additive=False, n=3)      # CMY
    assert not act(on, accurate=True, is_additive=False, n=4)      # CMYK
    assert not act(on, accurate=True, is_additive=True, n=4)
    assert not act(on, accurate=False, is_additive=True, n=3)
    assert not act(B.accurate_candidates(frozenset()), accurate=True,
                   is_additive=True, n=3)
    # it changes when the re-solve runs, so the re-solve has to be on
    no_resolve = B.accurate_candidates(
        frozenset({TOKEN, "no-" + b2a.A44B_TOKEN}))
    assert TOKEN in no_resolve
    assert not act(no_resolve, accurate=True, is_additive=True, n=3)


def test_the_builder_asks_after_the_exact_keep_and_before_the_resolve():
    src = inspect.getsource(B._build_profile_impl)
    keep = src.index("b2a_mod.exact_keep(")
    ask = src.index("b2a_mod.smooth_exact_always(")
    solve = src.index("b2a_mod.smooth_exact(")
    assert keep < ask < solve
    # inside the a44-exactkeep block: without that token nothing runs
    assert src.rindex("b2a_mod.A44_TOKEN in candidates", 0, ask) > src.rindex(
        "nearblack_column(", 0, ask)
    assert src.count("b2a_mod.smooth_exact(") == 1    # one call, two triggers
    assert 'if ((_ek["nodes"] or _sx_always) and n == 3' in src[ask:solve]
    assert "is_additive=meas.is_additive" in src[ask:solve]


def test_the_progress_line_names_the_token_and_the_app_keeps_it_internal():
    from workflow.engine_builder import EngineLines
    line = b2a.smooth_exact_always_line(0)
    assert TOKEN in line and "restored at 0 nodes" in line
    assert chr(0x2014) not in line           # no em dash in a line of ours
    shown: list[str] = []
    lines = EngineLines(shown.append)
    assert lines._present(line) is None
    assert [r["switch"] for r in lines.reported] == [TOKEN]
    assert shown == []


# ------------------------------------------------------- real builds (slow)
def _argyll_bin() -> str | None:
    from tests.argyll_env import argyll_bin_dir
    d = argyll_bin_dir()
    if d is not None and (d / argyll_binary("colprof")).exists():
        return str(d)
    hit = shutil.which("colprof")
    return str(Path(hit).parent) if hit else None


def _tags(data: bytes) -> dict:
    n = struct.unpack(">I", data[128:132])[0]
    out = {}
    for i in range(n):
        sig, off, size = struct.unpack(">4sII",
                                       data[132 + 12 * i:144 + 12 * i])
        out[sig.decode()] = data[off:off + size]
    return out


def _build(ti3: Path, folder: Path, *tokens: str, workers: int = 1):
    """One Maximum accuracy build to ``folder``/p.icc (the same file name
    everywhere: the description tag is the file stem). Returns (bytes,
    progress lines)."""
    from workflow.profile_engine import gamut_map
    gamut_map._ORACLE_CACHE.clear()
    folder.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    s = B.BuildSettings(
        quality="m", gammap_mode="accurate", argyll_bin=_argyll_bin(),
        source_gamut=str(Path(B.__file__).resolve().parents[2]
                         / "assets/profiles/ClayRGB1998.icm"),
        timestamp=datetime(2026, 1, 1), progress=lines.append,
        engine_workers=workers, engine_candidates=frozenset(tokens))
    B.build_profile(ti3, folder / "p.icc", s)
    return (folder / "p.icc").read_bytes(), lines


@pytest.fixture(scope="module")
def rgb_builds(tmp_path_factory):
    from benchmarks.research import datasets as dsm
    work = tmp_path_factory.mktemp("resolve_always_rgb")
    ds = dsm.synthetic("S1", work, 400)
    out = {"off": _build(ds.ti3, work / "off")}
    for n in (1, 2, 4, 8):
        out[n] = _build(ds.ti3, work / f"on{n}", TOKEN, workers=n)
    out["ti3"], out["work"] = ds.ti3, work
    return out


needs_argyll = pytest.mark.skipif(_argyll_bin() is None,
                                  reason="ArgyllCMS not installed")


@pytest.mark.slow
@needs_argyll
def test_the_resolve_runs_although_the_exact_keep_restored_nothing(
        rgb_builds):
    """The fixture is a printer on which today's trigger does not fire: no
    node restored, so no re-solve. With the token the re-solve runs, and
    the one line of the token says that it did not wait for a node."""
    off_lines, on_lines = rgb_builds["off"][1], rgb_builds[1][1]
    assert not [ln for ln in off_lines if KEPT in ln]
    assert not [ln for ln in off_lines if SMOOTHED in ln]
    assert not [ln for ln in off_lines
                if b2a.smooth_exact_always_line(0)[:40] in ln]
    assert not [ln for ln in on_lines if KEPT in ln]
    assert len([ln for ln in on_lines if SMOOTHED in ln]) == 1
    said = [ln for ln in on_lines
            if ln.endswith(b2a.smooth_exact_always_line(0))]
    assert len(said) == 1


@pytest.mark.slow
@needs_argyll
def test_on_an_rgb_printer_only_the_colorimetric_b2a_table_changes(
        rgb_builds):
    off, on = _tags(rgb_builds["off"][0]), _tags(rgb_builds[1][0])
    assert set(off) == set(on)
    changed = sorted(t for t in off if off[t] != on[t])
    assert changed == ["B2A1"]
    assert len(rgb_builds["off"][0]) == len(rgb_builds[1][0])
    for same in ("A2B0", "A2B1", "A2B2", "B2A0", "B2A2"):
        assert same in off and off[same] == on[same], same


@pytest.mark.slow
@needs_argyll
def test_the_profile_does_not_depend_on_the_worker_count(rgb_builds):
    for n in (2, 4, 8):
        assert rgb_builds[n][0] == rgb_builds[1][0], f"{n} workers"


@pytest.mark.slow
@needs_argyll
def test_switched_off_again_the_build_is_the_default_build(rgb_builds):
    """The token with its own no- switch is the build without it, byte for
    byte: with the token off nothing else has moved."""
    again, lines = _build(rgb_builds["ti3"], rgb_builds["work"] / "offagain",
                          TOKEN, "no-" + TOKEN)
    assert again == rgb_builds["off"][0]
    assert not [ln for ln in lines if SMOOTHED in ln]


@pytest.mark.slow
@needs_argyll
def test_without_the_resolve_itself_the_token_does_nothing(rgb_builds):
    """no-a44b-smoothexact wins: the token moves the trigger of that step
    and has no table of its own."""
    none, lines = _build(rgb_builds["ti3"], rgb_builds["work"] / "noresolve",
                         TOKEN, "no-" + b2a.A44B_TOKEN)
    assert none == rgb_builds["off"][0]
    assert not [ln for ln in lines if SMOOTHED in ln]


@pytest.mark.slow
@needs_argyll
def test_on_a_cmyk_device_the_token_changes_nothing(tmp_path):
    from benchmarks.research import datasets as dsm
    ds = dsm.synthetic("X3", tmp_path, 400)
    off, _ = _build(ds.ti3, tmp_path / "off")
    on, lines = _build(ds.ti3, tmp_path / "on", TOKEN)
    assert on == off
    assert not [ln for ln in lines if SMOOTHED in ln]
    assert not [ln for ln in lines if "re-solved on every RGB build" in ln]
