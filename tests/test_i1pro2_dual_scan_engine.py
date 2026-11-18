"""The i1Pro 2 dual scan (step 1, 2026-11-18) in the REAL chromiq-chartread,
through its replay instrument (CHROMIQ_REPLAY_INSTRUMENT=i1pro2, a DUALCAL
block and LAMP / UV lines: an INVENTED instrument, no real data):

* the C arithmetic (chromiq_dualscan.c) gives the Python module's numbers
  (workflow/dual_scan/model.py), patch for patch, and refuses the same things;
* with --dual-scale and --condition-dir the two other conditions go into the
  i1Pro 3 Beta's files (conditions/<hash>-M1.ti3 / -M2.ti3), so Build
  Profile's choice (workflow.i1pro3_conditions.choices_for) offers them with
  no code of its own; every file records the dual scan, the factor and its
  source, and the white reference;
* without --dual-scale nothing changes; an i1Pro 3 measurement is byte for
  byte the same with --dual-scale given; a dual session refuses to continue
  single-scan readings ("mixed") and a real i1Pro 2 is not offered it yet.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent / "helpers"))
from replay_tools import HELPER, ReplaySession, parse_ti2_rows  # noqa: E402

from workflow.dual_scan import model, storage  # noqa: E402
from workflow.dual_scan.reasons import DualScanRefused  # noqa: E402
from workflow.i1pro3_conditions import data_block_hash  # noqa: E402

needs_helper = pytest.mark.skipif(not HELPER.exists(),
                                  reason="chromiq-chartread helper not built")
WL = model.WAVELENGTHS
BAND = (WL >= 410) & (WL <= 550)
S = 1.137


def _invented():
    x = (WL - 410) / 140.0
    kA = np.where(BAND, 1.2e-4 * (1.0 + 0.8 * np.sin(np.pi * x)), 0.0)
    kD = np.where(BAND, kA * (1.6 + 0.9 * x), 0.0)
    W = 0.9 + 0.02 * np.cos(WL / 50.0)
    T = 0.012 * np.exp(-(WL - 380) / 25.0) + 1e-4
    E = 2.4e4 * (1.0 + 0.3 * (WL - 380) / 350.0)
    return (model.UVTables.from_values(kA[:18], kD[:18]),
            model.DualCalibration(W, T, E, 139, 139))


# ----------------------------------------------------------------- C == Python

def test_the_c_arithmetic_is_the_python_module(tmp_path_factory):
    from tests.test_i1pro3_lights_modes import _build_and_run
    out = _build_and_run(tmp_path_factory, "i1pro2_dual_maths_test")
    lines = {ln.split(" ", 1)[0] + (" " + ln.split()[1] if ln.startswith("patch") else ""): ln
             for ln in out.splitlines()}
    tab, cal = _invented()
    assert lines["check"] == "check ok"
    te = cal.te()
    for p in range(5):
        L = 0.1 + 0.15 * p + 0.001 * np.arange(36)
        U = 0.0005 * (p + 1) * np.exp(-0.5 * ((WL - 440) / 25.0) ** 2) \
            + 0.012 * np.exp(-(WL - 380) / 25.0) * L
        c = model.compute(L, U, cal, tab, S)
        t = lines[f"patch {p}"].split()
        assert t[2] == "ok"
        got = np.array([float(v) for v in t[3:]])
        np.testing.assert_allclose(got[:36], c.m1[0], rtol=0, atol=1e-13)
        np.testing.assert_allclose(got[36:], c.m2[0], rtol=0, atol=1e-13)
        assert np.abs(c.m2[0] - L)[BAND].max() > 1e-3        # real glow
        del te
        te = cal.te()
    for key, want in (("scale_nan", "bad_scale"), ("scale_big", "bad_scale"),
                      ("no_uv_tile", "no_dual_calibration"),
                      ("tile_dark", "uv_tile_dark"),
                      ("cut_aligned", "ok"), ("cut_half_pitch", "uv_pass_misaligned"),
                      ("table_out_of_band", "bad_uv_tables"),
                      ("no_tables", "no_uv_tables"), ("nan_value", "bad_values"),
                      ("cut_half", "uv_pass_short"),
                      ("cut_no_ruler", "no_ruler")):
        assert lines[key] == f"{key} {want}", lines.get(key)
    cut = lines["cut"].split()
    assert cut[1] == "ok"
    vals = [float(v.split(":")[0]) for v in cut[2:]]
    counts = [int(v.split(":")[1]) for v in cut[2:]]
    assert vals == [float(k) for k in range(1, 13)]
    # the Python cut on the same strip gives the same
    from workflow.dual_scan import cut as pcut
    lp = np.arange(120) * 7.0
    up = (np.arange(72)[::-1] + 0.5) * (70.0 / 6.0)
    pp = np.minimum((up // 70.0).astype(int), 11)
    r = pcut.cut_uv_pass([(k * 10, 10) for k in range(12)], lp, up,
                         np.repeat((pp + 1.0)[:, None], 36, axis=1))
    assert list(r.uv[:, 0]) == vals and r.counts == counts


# ----------------------------------------------------------------- the engine

def _paper(ys, seed):
    """Glow-free patches as light as the chart expects (so the engine's
    strip and direction checks see the colours they expect), with a little
    invented colour, and a brightener on top."""
    rng = np.random.default_rng(seed)
    n = len(ys)
    lvl = np.clip(np.asarray(ys, float)[:, None] / 100.0, 0.02, 0.95)
    m2 = np.clip(lvl * (0.97 + 0.06 * rng.random((n, 36))), 0.01, 0.97)
    g = m2.mean(axis=1, keepdims=True) * 900.0 * np.exp(-0.5 * ((WL - 440) / 25.0) ** 2)
    return m2, g


def _vec(v):
    return " ".join(f"{x:.10g}" for x in v)


def _chart(tmp: Path, *, uv_tile=True, xyz=False):
    """A real targen/printtarg chart and a dual replay script for it."""
    from test_chartread_engine import _make_chart
    base = _make_chart(tmp, randomised=False)
    steps, rows = parse_ti2_rows(base.with_suffix(".ti2"))
    tab, cal = _invented()
    truth = {}
    rp = tmp / "replay.txt"
    with rp.open("w", encoding="utf-8") as fp:
        fp.write(f"PATCHES {steps}\nDUALCAL\n")
        fp.write(f"W {_vec(cal.white)}\n")
        if uv_tile:
            fp.write(f"T {_vec(cal.uv_tile)}\n")
        fp.write(f"E {_vec(cal.emis)}\nKA {_vec(tab.kA[:18])}\nKD {_vec(tab.kD[:18])}\nCLOCKS 139 139\n")
        for k, letter in enumerate(sorted(rows)):
            m2, g = _paper([y for (_x, y, _z) in rows[letter]], k + 1)
            L, U, M1 = model.forward(m2, g, cal, tab, S)
            truth[letter] = (L, M1, m2)
            fp.write(f"STRIP {letter}\n")
            if xyz:                      # also plain XYZ lines (single-scan use)
                for (x, y, z) in rows[letter]:
                    fp.write(f"{x:.4f} {y:.4f} {z:.4f}\n")
            for i in range(len(rows[letter])):
                fp.write(f"LAMP {_vec(L[i])}\nUV {_vec(U[i])}\n")
    return base, rp, truth, steps


def _spectra(path: Path) -> "dict[str, np.ndarray]":
    text = path.read_text(encoding="latin-1")
    fields = text.split("BEGIN_DATA_FORMAT")[1].split("END_DATA_FORMAT")[0].split()
    data = text.split("\nBEGIN_DATA\n")[1].split("\nEND_DATA")[0]
    li = fields.index("SAMPLE_LOC")
    si = [fields.index(f"SPEC_{w}") for w in WL]
    out = {}
    for ln in data.splitlines():
        t = ln.split()
        if len(t) == len(fields):
            out[t[li].strip('"')] = np.array([float(t[i]) for i in si]) / 100.0
    return out


def _swipe(s, **kw):
    s.wait_event("strip_ready")
    i = s.event_index()
    s.send(cmd="swipe", **kw)
    s.wait_event("strip_ready", after=i)


def _done(s, unread=False):
    i = s.event_index()
    s.send(cmd="done")
    if unread:
        s.wait_event("unread_confirm", after=i)
        s.send(cmd="yes")
    s.wait_event("done", timeout=8, after=i)
    s.finish()


def _dual_args(cdir, s=S, source="standard", white="instrument"):
    return ["-S", "--condition-dir", str(cdir), "--dual-scale", f"{s:.4f}",
            "--dual-scale-source", source, "--dual-white", white]


def _strip_of(loc: str) -> str:
    return "".join(ch for ch in loc if ch.isalpha())


def _check(base: Path, cdir: Path, truth, reversed_strips=()):
    h = data_block_hash(base.with_suffix(".ti3"))
    main = _spectra(base.with_suffix(".ti3"))
    assert main
    files = {c: cdir / f"{h}-{c}.ti3" for c in ("M1", "M2")}
    for f in (base.with_suffix(".ti3"), *files.values()):
        rec = storage.read_dual_record(f)
        assert rec == storage.DualRecord(True, round(S, 4), "standard", "instrument"), f
    got = {c: _spectra(f) for c, f in files.items()}
    for loc, m0 in main.items():
        letter = _strip_of(loc)
        idx = int(loc[len(letter):]) - 1
        L, M1, m2 = truth[letter]
        np.testing.assert_allclose(m0, L[idx], atol=1e-6)
        np.testing.assert_allclose(got["M1"][loc], M1[idx], atol=1e-6)
        np.testing.assert_allclose(got["M2"][loc], m2[idx], atol=1e-6)
    for c, f in files.items():
        text = f.read_text(encoding="latin-1")
        assert f'MEASUREMENT_CONDITION "{c}"' in text
        assert f'CHROMIQ_CONDITION_OF "{h}"' in text
    return h


@needs_helper
def test_the_three_conditions_go_into_the_i1pro3_betas_files(tmp_path, monkeypatch):
    monkeypatch.setenv("CHROMIQ_REPLAY_INSTRUMENT", "i1pro2")
    base, rp, truth, _ = _chart(tmp_path)
    cdir = tmp_path / "conditions"
    cdir.mkdir()
    with ReplaySession(base, rp, extra_args=_dual_args(cdir)) as s:
        _swipe(s)
        _swipe(s, reversed=True)
        _done(s)
    ev = [e for e in s.events if e.get("event") == "conditions"]
    assert ev == [{"event": "conditions", "active": True, "instrument": "i1pro2",
                   "dual": True, "scale": round(S, 4), "scale_source": "standard",
                   "white": "instrument", "main": "M0", "extra": ["M1", "M2"],
                   "chosen": "M0"}]
    _check(base, cdir, truth)
    # Build Profile's choice, the i1Pro 3 Beta's own code, offers all three
    from workflow import i1pro3_conditions as c
    main = base.with_suffix(".ti3")
    assert c.file_condition(main) == "M0"
    ch = c.choices_for(main)
    assert [(x.cond, x.usable) for x in ch] == [("M0", True), ("M1", True), ("M2", True)]
    assert storage.start_guard(main, dual=True) is None
    assert storage.start_guard(main, dual=False) == "mixed_scan_kind"


@needs_helper
def test_a_resume_continues_the_dual_scan(tmp_path, monkeypatch):
    monkeypatch.setenv("CHROMIQ_REPLAY_INSTRUMENT", "i1pro2")
    base, rp, truth, _ = _chart(tmp_path)
    cdir = tmp_path / "conditions"
    cdir.mkdir()
    with ReplaySession(base, rp, extra_args=_dual_args(cdir)) as s:
        _swipe(s)
        _done(s, unread=True)
    first = _check(base, cdir, truth)
    with ReplaySession(base, rp, extra_args=["-r"] + _dual_args(cdir)) as s:
        _swipe(s)
        _done(s)
    assert [e for e in s.events if e.get("event") == "conditions"][0]["active"]
    assert _check(base, cdir, truth) != first


@needs_helper
def test_a_dual_session_does_not_continue_single_scan_readings(tmp_path, monkeypatch):
    monkeypatch.setenv("CHROMIQ_REPLAY_INSTRUMENT", "i1pro2")
    base, rp, truth, _ = _chart(tmp_path)
    cdir = tmp_path / "conditions"
    cdir.mkdir()
    with ReplaySession(base, rp, extra_args=["-S"]) as s:      # a single-scan session
        _swipe(s)
        _done(s, unread=True)
    main = base.with_suffix(".ti3")
    assert storage.start_guard(main, dual=True) == "mixed_scan_kind"
    assert storage.start_guard(main, dual=False) is None
    with ReplaySession(base, rp, extra_args=["-r"] + _dual_args(cdir)) as s:
        _swipe(s)
        _done(s)
    ev = [e for e in s.events if e.get("event") == "conditions"]
    assert ev == [{"event": "conditions", "active": False, "why": "mixed"}]
    assert list(cdir.iterdir()) == []


@needs_helper
def test_no_uv_tile_in_the_calibration_ends_them_with_the_reason(tmp_path, monkeypatch):
    monkeypatch.setenv("CHROMIQ_REPLAY_INSTRUMENT", "i1pro2")
    base, rp, truth, _ = _chart(tmp_path, uv_tile=False)
    cdir = tmp_path / "conditions"
    cdir.mkdir()
    with ReplaySession(base, rp, extra_args=_dual_args(cdir)) as s:
        _swipe(s)
        _done(s, unread=True)
    ev = [e for e in s.events if e.get("event") == "conditions"]
    assert ev[0]["active"] is True
    assert ev[1] == {"event": "conditions", "active": False,
                     "why": "dual_no_dual_calibration"}
    assert list(cdir.iterdir()) == []
    assert _spectra(base.with_suffix(".ti3"))           # M0 measured as always


@pytest.mark.parametrize("inst,args,why", [
    ("i1pro", [], "instrument"),                  # not an i1Pro 2
    ("i1pro2", ["--dual-scale", "9"], "instrument"),   # a scale out of range = not asked
    ("i1pro2", ["-F", "u"], "filter"),
])
@needs_helper
def test_where_it_does_not_apply_it_says_why(tmp_path, monkeypatch, inst, args, why):
    monkeypatch.setenv("CHROMIQ_REPLAY_INSTRUMENT", inst)
    base, rp, _t, _ = _chart(tmp_path)
    cdir = tmp_path / "conditions"
    cdir.mkdir()
    extra = ["-S", "--condition-dir", str(cdir)] + args
    if "--dual-scale" not in args:
        extra += ["--dual-scale", "1.1"]
    with ReplaySession(base, rp, extra_args=extra) as s:
        _swipe(s)
        _done(s, unread=True)
    ev = [e for e in s.events if e.get("event") == "conditions"]
    assert ev == [{"event": "conditions", "active": False, "why": why}]
    assert list(cdir.iterdir()) == []


@needs_helper
def test_without_dual_scale_an_i1pro2_reads_as_before(tmp_path, monkeypatch):
    """The same script read without --dual-scale: no conditions, no dual
    keyword, and the main file is the same lamp readings."""
    monkeypatch.setenv("CHROMIQ_REPLAY_INSTRUMENT", "i1pro2")
    base, rp, truth, _ = _chart(tmp_path)
    with ReplaySession(base, rp, extra_args=["-S"]) as s:
        _swipe(s)
        _done(s, unread=True)
    main = base.with_suffix(".ti3")
    assert not [e for e in s.events if e.get("event") == "conditions"]
    assert "CHROMIQ_DUAL" not in main.read_text(encoding="latin-1")
    assert storage.read_dual_record(main) == storage.DualRecord(False)


@needs_helper
def test_an_i1pro3_measurement_is_byte_for_byte_the_same_with_dual_scale(tmp_path, monkeypatch):
    """The i1Pro 3 Beta's path does not change when --dual-scale is given
    too: the main file and both condition files, byte for byte (CREATED
    aside)."""
    monkeypatch.setenv("CHROMIQ_REPLAY_INSTRUMENT", "i1pro3")
    from test_i1pro3_conditions_engine import _chart as chart3
    out = []
    for dual in (False, True):
        d = tmp_path / ("dual" if dual else "plain")
        d.mkdir()
        base, rp, _ = chart3(d)
        cdir = d / "conditions"
        cdir.mkdir()
        args = ["--condition-dir", str(cdir)] + (["--dual-scale", "1.1"] if dual else [])
        with ReplaySession(base, rp, extra_args=args) as s:
            _swipe(s)
            _swipe(s, reversed=True)
            _done(s)
        ev = [e for e in s.events if e.get("event") == "conditions"]
        assert ev[0]["active"] is True and ev[0]["instrument"] == "i1pro3"
        files = [base.with_suffix(".ti3")] + sorted(cdir.iterdir())
        out.append([b"\n".join(ln for ln in f.read_bytes().split(b"\n")
                               if not ln.startswith(b"CREATED")) for f in files])
    assert out[0] == out[1]


@needs_helper
def test_the_caps_and_the_build_say_it():
    o = subprocess.run([str(HELPER), "--caps"], capture_output=True, text=True,
                       encoding="utf-8", timeout=30).stdout
    j = json.loads(o.strip().splitlines()[-1])
    assert storage.CAPABILITY in j["caps"]
    assert storage.DEVICE_CAPABILITY in j["caps"]         # step 2: the device part is compiled in
    assert "+i1pro2-dual-conditions" in j["build"]


# ----------------------------------------------------------------- python side

def test_calibration_must_fit_the_reading_mode():
    f = storage.calibration_fits
    assert f(None, "dual") == "no_dual_calibration"
    assert f("single", "dual") == "no_dual_calibration"
    assert f("dual", "single") == "calibration_mode_changed"
    assert f("dual", "dual", calibration_clocks=(139, 139), reading_clocks=(154, 139)) == "calibration_mismatch"
    assert f("dual", "dual", calibration_clocks=(139, 139), reading_clocks=(139, 139)) is None
    assert f("single", "single") is None and f(None, "single") is None


def test_the_helper_arguments_and_the_refined_store():
    from workflow.dual_scan.scale import ScaleChoice

    class Store(dict):
        def set(self, k, v):
            self[k] = v

    st = Store()
    key = storage.instrument_key("i1Pro 2", "1234567", st)
    assert "1234567" not in key and len(key) == 20
    assert storage.scale_for(st, key) == ScaleChoice.standard()
    storage.store_refined(st, key, ScaleChoice(1.2, "refined"))
    assert storage.scale_for(st, key) == ScaleChoice(1.2, "refined")
    assert "1234567" not in json.dumps(st)
    assert storage.helper_args(storage.scale_for(st, key), "table") == [
        "--dual-scale", "1.2000", "--dual-scale-source", "refined", "--dual-white", "table",
        "--dual-chosen", "M0"]
    st[storage.REFINED_SETTING] = json.dumps({key: {"value": 7}})
    assert storage.scale_for(st, key) == ScaleChoice.standard()      # nonsense ignored
    storage.forget_refined(st, key)
    with pytest.raises(ValueError):
        storage.store_refined(st, key, ScaleChoice.standard())
    with pytest.raises(DualScanRefused):
        model.check_scale(7)


# ----------------------------------------------------------------- guarantees

ROOT = Path(__file__).resolve().parent.parent


def test_no_eeprom_write_is_compiled_into_the_i1pro2_driver():
    """X-Rite's program writes a usage log into the i1Pro 2's memory; ChromIQ
    must not. The vendored driver's only EEPROM writer is called only from
    i1pro_update_log, whose body sits under ENABLE_WRITE, which is undefined."""
    src = (ROOT / "native" / "instlib" / "i1pro_imp.c").read_text(encoding="utf-8", errors="replace")
    assert "#undef ENABLE_WRITE" in src and "#define ENABLE_WRITE" not in src
    calls = [i for i in range(len(src)) if src.startswith("i1pro_writeEEProm(p,", i)]
    assert calls, "the writer's calls moved: look again"
    a = src.index("i1pro_code i1pro_update_log(i1pro *p) {")
    guard = src.index("#ifdef ENABLE_WRITE", a)
    end = src.index("#endif", guard)
    assert all(guard < i < end for i in calls)


def test_the_dual_arithmetic_touches_no_instrument():
    for name in ("chromiq_dualscan.c", "chromiq_dualscan.h"):
        text = (ROOT / "native" / "chartread_helper" / name).read_text(encoding="utf-8")
        for word in ("usb_", "icom", "i1pro_", "EEProm", "fopen", "remove("):
            assert word not in text, (name, word)
