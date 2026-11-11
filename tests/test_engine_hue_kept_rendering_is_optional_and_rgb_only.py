"""The hue-kept rendering (BuildSettings.hue_rendering = "kept", token
x1-huekeep; workflow/profile_engine/hue_keep.py) is an OPTION:

* off by default, and with it off nothing in a build changes;
* Maximum accuracy and RGB printers only: on an ink device the token does
  nothing and says so in one line;
* it touches the Perceptual and Saturation B2A tables and nothing else;
* the profile's bytes do not depend on the worker count;
* it does what it is for: less hue drift (judged in IPT, a hue space the
  step does not use), the neutral column untouched.

The builds are slow (the colprof oracle runs in each): --runslow only. The
suite runs with CHROMIQ_ENGINE_THREADS=1; the worker counts here are set
through BuildSettings.engine_workers.
"""
from __future__ import annotations

import re
import shutil
import struct
from datetime import datetime
from pathlib import Path

import numpy as np
import pytest

from core.resource_path import argyll_binary
from workflow.profile_engine import builder as B
from workflow.profile_engine import hue_keep as HK


# ------------------------------------------------------------ the option
def test_the_hue_option_is_off_by_default_and_maps_to_one_token():
    assert B.BuildSettings().hue_rendering == "argyll"
    assert B.HUE_RENDERING_TOKENS == {"argyll": None, "kept": "x1-huekeep"}
    assert HK.TOKEN == "x1-huekeep"
    assert "x1-huekeep" in B.ENGINE_CANDIDATE_TOKENS
    assert "no-x1-huekeep" in B.ENGINE_CANDIDATE_TOKENS
    assert "x1-huekeep" not in B.ACCURATE_DEFAULT_TOKENS
    assert B.hue_rendering_token("") is None
    assert B.hue_rendering_token(None) is None
    assert B.hue_rendering_token("Kept") == "x1-huekeep"


def test_an_unknown_hue_rendering_is_refused_like_an_unknown_black_depth():
    with pytest.raises(ValueError):
        B.hue_rendering_token("oklab")
    with pytest.raises(ValueError):
        B.effective_engine_candidates(
            B.BuildSettings(gammap_mode="accurate", hue_rendering="on"))


def test_the_hue_token_reaches_a_maximum_accuracy_build_only():
    plain = B.effective_engine_candidates(
        B.BuildSettings(gammap_mode="accurate"))
    assert plain == B.accurate_candidates(frozenset())
    assert "x1-huekeep" not in plain
    kept = B.effective_engine_candidates(
        B.BuildSettings(gammap_mode="accurate", hue_rendering="kept"))
    assert kept == plain | {"x1-huekeep"}
    assert B.accurate_candidates(kept) == kept          # idempotent
    assert kept == B.effective_engine_candidates(B.BuildSettings(
        gammap_mode="accurate", engine_candidates=frozenset({"x1-huekeep"})))
    off_again = B.effective_engine_candidates(B.BuildSettings(
        gammap_mode="accurate", hue_rendering="kept",
        engine_candidates=frozenset({"no-x1-huekeep"})))
    assert "x1-huekeep" not in off_again
    for mode in ("fast", "argyll"):
        assert B.effective_engine_candidates(B.BuildSettings(
            gammap_mode=mode, hue_rendering="kept")) == frozenset()
    # together with the black-depth option
    both = B.effective_engine_candidates(B.BuildSettings(
        gammap_mode="accurate", hue_rendering="kept", black_depth="deepest"))
    assert both == plain | {"x1-huekeep", "a88-black-deepest"}


def test_the_step_acts_on_rgb_devices_in_maximum_accuracy_only():
    on = frozenset({"x1-huekeep"})
    assert HK.applies(on, accurate=True, is_additive=True, n_channels=3)
    assert not HK.applies(on, accurate=True, is_additive=False, n_channels=3)
    assert not HK.applies(on, accurate=True, is_additive=False, n_channels=4)
    assert not HK.applies(on, accurate=True, is_additive=True, n_channels=4)
    assert not HK.applies(on, accurate=False, is_additive=True, n_channels=3)
    assert not HK.applies(frozenset(), accurate=True, is_additive=True,
                          n_channels=3)


def test_the_constants_of_the_method_are_the_validated_ones():
    """They are properties of the method, validated together (expert review
    2026-11-10/11): changing one invalidates that validation."""
    assert (HK.MU, HK.DARK_FADE_L, HK.CHROMA_WEIGHT) == (100.0, 16.0, 0.25)
    assert HK.ROTATION_SPACE == "oklab"
    assert HK.NEUTRAL_FADE_C == 0.03


def test_the_module_keeps_no_state_between_builds():
    """No module-level mutable container a build could leave something in:
    what a solve needs is passed as arguments."""
    for name, v in vars(HK).items():
        if name.startswith("__"):
            continue
        assert not isinstance(v, (list, dict, set, bytearray, np.ndarray)), (
            f"hue_keep.{name} is module state: {type(v)}")


# ------------------------------------------------------- the target rule
def _hue_ok(lab):
    ok = HK._lab_to_oklab(np.atleast_2d(np.asarray(lab, float)))
    return np.degrees(np.arctan2(ok[:, 2], ok[:, 1])), np.hypot(
        ok[:, 1], ok[:, 2]), ok[:, 0]


def test_a_target_takes_the_source_hue_and_keeps_the_prints_chroma():
    src = np.array([[60.0, 50.0, 20.0], [70.0, -40.0, 45.0]])
    printed = np.array([[55.0, 30.0, 25.0], [68.0, -20.0, 40.0]])
    tgt = HK.source_hue_targets(src, printed)
    hs, _, _ = _hue_ok(src)
    ht, ct, lt = _hue_ok(tgt)
    hp, cp, lp = _hue_ok(printed)
    assert np.abs((ht - hs + 180) % 360 - 180).max() < 1e-6
    assert np.abs(ct - cp).max() < 1e-9 and np.abs(lt - lp).max() < 1e-9
    assert np.abs((hp - hs + 180) % 360 - 180).min() > 1.0   # it did turn


def test_the_hue_weight_fades_out_at_the_neutral_axis_and_in_the_dark():
    printed = np.array([[50.0, 20.0, 10.0]])
    # a neutral source and a source at L* 0 leave the print as it is
    for src in ([[50.0, 0.0, 0.0]], [[0.0, 40.0, -60.0]]):
        tgt = HK.source_hue_targets(np.array(src), printed)
        # (the Lab -> OKLab -> Lab round trip itself is good to 1e-4)
        assert np.abs(tgt - printed).max() < 1e-3
    # continuous: half way down the fade the turn is partial
    src = np.array([[HK.DARK_FADE_L / 2.0, 30.0, -50.0]])
    full = HK.source_hue_targets(np.array([[60.0, 30.0, -50.0]]), printed)
    half = HK.source_hue_targets(src, printed)
    assert 0.0 < np.abs(half - printed).max() < np.abs(full - printed).max()


def test_the_metric_counts_a_chroma_error_a_quarter_and_is_plain_at_grey():
    w = HK.chroma_metric(np.array([[60.0, 0.0, 0.0], [60.0, 50.0, 20.0]]))
    # a Lab neutral has an OKLab chroma of a few 1e-4, not exactly zero
    assert np.allclose(w[0], np.eye(3), atol=1e-5)
    ev = np.sort(np.linalg.eigvalsh((w[1] + w[1].T) / 2.0))
    assert np.allclose(ev, [HK.CHROMA_WEIGHT, 1.0, 1.0], atol=1e-9)


def test_the_neutral_column_is_pinned():
    from workflow.profile_engine.pcs import LabPcs
    g = 9
    node = LabPcs.node_lab(g)
    shaped = np.random.default_rng(3).uniform(0.1, 0.9, (g ** 3, 3))
    free = HK.free_nodes(shaped, node, g)
    col = np.hypot(node[:, 1], node[:, 2]) < 1.0
    assert col.sum() == g and not free[col].any()
    assert free[~col].all()


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


def _build(ti3: Path, folder: Path, **kw):
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
        timestamp=datetime(2026, 1, 1), progress=lines.append, **kw)
    B.build_profile(ti3, folder / "p.icc", s)
    return (folder / "p.icc").read_bytes(), lines


@pytest.fixture(scope="module")
def rgb_builds(tmp_path_factory):
    from benchmarks.research import datasets as dsm
    work = tmp_path_factory.mktemp("huekeep_rgb")
    ds = dsm.synthetic("S1", work, 400)
    out = {"off": _build(ds.ti3, work / "off", engine_workers=1)}
    for n in (1, 2, 4, 8):
        out[n] = _build(ds.ti3, work / f"on{n}", hue_rendering="kept",
                        engine_workers=n)
    out["path_off"] = work / "off" / "p.icc"
    out["path_on"] = work / "on1" / "p.icc"
    out["ti3"], out["work"] = ds.ti3, work
    return out


needs_argyll = pytest.mark.skipif(_argyll_bin() is None,
                                  reason="ArgyllCMS not installed")


@pytest.mark.slow
@needs_argyll
def test_on_an_rgb_printer_only_the_perceptual_and_saturation_tables_change(
        rgb_builds):
    off, on = _tags(rgb_builds["off"][0]), _tags(rgb_builds[1][0])
    assert set(off) == set(on)
    changed = sorted(t for t in off if off[t] != on[t])
    assert changed == ["B2A0", "B2A2"]
    assert len(rgb_builds["off"][0]) == len(rgb_builds[1][0])
    said = [ln for ln in rgb_builds[1][1] if "Hue-kept rendering" in ln]
    assert len(said) == 2 and all("x1-huekeep" in ln for ln in said)
    assert "B2A0" in said[0] + said[1] and "B2A2" in said[0] + said[1]
    assert not [ln for ln in rgb_builds["off"][1] if "Hue-kept" in ln]


@pytest.mark.slow
@needs_argyll
def test_the_hue_kept_profile_does_not_depend_on_the_worker_count(rgb_builds):
    for n in (2, 4, 8):
        assert rgb_builds[n][0] == rgb_builds[1][0], f"{n} workers"


@pytest.mark.slow
@needs_argyll
def test_switched_off_again_the_build_is_the_default_build(rgb_builds):
    """hue_rendering = "kept" with no-x1-huekeep is the build without the
    option, byte for byte: with the option off nothing else has moved."""
    again, lines = _build(rgb_builds["ti3"], rgb_builds["work"] / "offagain",
                          hue_rendering="kept", engine_workers=1,
                          engine_candidates=frozenset({"no-x1-huekeep"}))
    assert again == rgb_builds["off"][0]
    assert not [ln for ln in lines if "Hue-kept" in ln]


def _ipt_hue_drift(path: Path, tag: str) -> float:
    """Chroma weighted mean hue shift, source -> print, in IPT (degrees),
    over a fixed cloud of source colours, through the written tables."""
    from benchmarks.iccread import IccProfile
    from workflow.profile_engine import oog_clip as oc
    icc = IccProfile(path)
    rng = np.random.default_rng(5)
    ll = rng.uniform(30.0, 85.0, 4000)
    cc = rng.uniform(15.0, 60.0, 4000)
    hh = rng.uniform(0.0, 2.0 * np.pi, 4000)
    src = np.c_[ll, cc * np.cos(hh), cc * np.sin(hh)]
    pr = icc.a2b_lab(icc.b2a_device(src, tag), "A2B1")
    a, b = oc.lab_to_ipt(src), oc.lab_to_ipt(pr)
    d = np.abs((np.degrees(np.arctan2(b[:, 2], b[:, 1])
                           - np.arctan2(a[:, 2], a[:, 1])) + 180.0)
               % 360.0 - 180.0)
    w = np.hypot(a[:, 1], a[:, 2])
    return float((d * w).sum() / w.sum())


@pytest.mark.slow
@needs_argyll
def test_the_hue_drift_is_lower_and_the_neutral_column_is_unchanged(
        rgb_builds):
    from workflow.profile_engine.v4_prm import parse_mft2
    for tag in ("B2A0", "B2A2"):
        before = _ipt_hue_drift(rgb_builds["path_off"], tag)
        after = _ipt_hue_drift(rgb_builds["path_on"], tag)
        # IPT is not the space the step turns the hue in
        assert after < 0.75 * before, (tag, before, after)
        a = parse_mft2(_tags(rgb_builds["off"][0])[tag])
        b = parse_mft2(_tags(rgb_builds[1][0])[tag])
        g = a["grid"]
        c = (g - 1) // 2
        ca = np.array(a["clut"]).reshape(g, g, g, -1)
        cb = np.array(b["clut"]).reshape(g, g, g, -1)
        assert np.array_equal(ca[:, c, c, :], cb[:, c, c, :]), tag
        assert not np.array_equal(ca, cb)


@pytest.mark.slow
@needs_argyll
def test_on_an_ink_device_the_option_changes_nothing_and_says_so(
        tmp_path):
    from benchmarks.research import datasets as dsm
    ds = dsm.synthetic("X3", tmp_path, 400)
    off, _ = _build(ds.ti3, tmp_path / "off", engine_workers=1)
    on, lines = _build(ds.ti3, tmp_path / "on", hue_rendering="kept",
                       engine_workers=1)
    assert on == off
    # (the build's list of active switches names the token as well)
    said = [ln for ln in lines if "Hue-kept rendering" in ln]
    assert len(said) == 1 and said[0].endswith(HK.NOT_RGB_LINE)


# --------------------------------------------------------- the app adapter
def test_the_app_adapter_lists_the_field_and_hides_the_internal_lines():
    from workflow.engine_builder import EngineLines, build_settings_summary
    summary = build_settings_summary(
        B.BuildSettings(gammap_mode="accurate", hue_rendering="kept"))
    assert "hue_rendering" in summary and "kept" in summary
    shown: list[str] = []
    lines = EngineLines(shown.append)
    info = {"rounds": 8, "pinned": 33, "moved_median": 3.6, "moved_p95": 29.4,
            "miss_median": 0.2, "miss_p95": 5.5}
    # Since the option is in the app (2026-11-11) the window shows these
    # lines in its own words; the engine's line, with the token, is kept
    # for chromiq.log and meta.json only.
    said = [lines._present(msg) for msg in (
        HK.progress_line("B2A0", info), HK.progress_line("B2A2", info),
        HK.NOT_RGB_LINE, HK.NOT_LAB_LINE)]
    assert [r["switch"] for r in lines.reported] == ["x1-huekeep"] * 4
    assert all(t and t.startswith("Keep the original hue: ") for t in said)
    assert "Perceptual" in said[0] and "Saturation" in said[1]
    assert "RGB printers only" in said[2] and "changed nothing" in said[2]
    assert "changed nothing" in said[3]
    for text in said:
        assert not re.search(r"x1|huekeep|oklab|research|B2A|token", text,
                             re.I), text
        assert "\u2014" not in text
    # a form of the line this adapter does not know stays in the log only
    assert lines._present("Hue-kept rendering (x1-huekeep): something "
                          "new.") is None
    assert shown == []
