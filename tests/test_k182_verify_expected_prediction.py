"""#182: a verification sheet is judged against the profile's prediction.

Knut approved the rule on #182 (questions of 5963902307, answered in
5964173774 and 5964384250): while a verification chart ChromIQ printed is
measured, each patch is compared with the run profile's forward prediction of
the ink values really sent to the printer, at the "chart made from a profile"
limit (30), with the strip outlier test ignored; the sRGB estimate at 95 is the
fallback, also for a profile built under another light.

What fails without each part:

* raw predicts the ``.ti2`` RGB, through the profile predicts cctiff's output
  and NEVER the ``.ti2`` RGB, and the ``-K`` cases decide before/with the
  calibration: ``test_raw_*``, ``test_through_*``, ``test_k_*``;
* every fallback: ``test_falls_back_*``;
* the strip outlier fence is off on these charts only:
  ``test_the_fence_is_ignored_*`` / ``test_the_fence_still_rules_*``;
* the repaint after a measurement shows the live outlines:
  ``test_the_repaint_is_the_live_judgement``;
* the card: ``test_the_card_says_expected_is_the_profile_prediction``;
* timing on the real tools: ``test_real_argyll_*``.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from datetime import datetime, timedelta
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402
from PyQt6.QtCore import QRect  # noqa: E402
from PyQt6.QtWidgets import QApplication, QWidget  # noqa: E402

from workflow import verify_expected as ve  # noqa: E402
from workflow.measurement_report import engine_patch_de, per_patch_overlay  # noqa: E402

# A small RGB chart: (loc, device RGB 0..100, the .ti2's sRGB estimate XYZ).
PATCHES = [
    ("A1", (100.0, 100.0, 100.0), (95.05, 100.0, 108.9)),
    ("A2", (0.0, 0.0, 100.0), (18.05, 7.22, 95.05)),        # pure blue
    ("A3", (100.0, 0.0, 0.0), (41.24, 21.26, 1.93)),
    ("A4", (50.0, 50.0, 50.0), (20.52, 21.59, 23.51)),
    ("B1", (0.0, 100.0, 0.0), (35.76, 71.52, 11.92)),
    ("B2", (0.0, 0.0, 0.0), (1.0, 1.0, 1.0)),
    ("B3", (25.0, 75.0, 50.0), (25.0, 40.0, 30.0)),
    ("B4", (75.0, 25.0, 50.0), (30.0, 22.0, 25.0)),
]


@pytest.fixture
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture(autouse=True)
def _fresh_cache():
    ve.clear_cache()
    yield
    ve.clear_cache()


def _ti2_text(rgb_scale=1.0):
    lines = ['CTI2', '', 'ORIGINATOR "ChromIQ layout engine"',
             'APPROX_WHITE_POINT "95.050000 100.000000 108.900000"',
             'NUMBER_OF_FIELDS 8', 'BEGIN_DATA_FORMAT',
             'SAMPLE_ID SAMPLE_LOC RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z',
             'END_DATA_FORMAT', f'NUMBER_OF_SETS {len(PATCHES)}', 'BEGIN_DATA']
    for i, (loc, rgb, xyz) in enumerate(PATCHES, 1):
        r, g, b = (v * rgb_scale for v in rgb)
        lines.append(f'{i} "{loc}" {r:.4f} {g:.4f} {b:.4f} '
                     f'{xyz[0]:.4f} {xyz[1]:.4f} {xyz[2]:.4f}')
    lines.append('END_DATA')
    return "\n".join(lines) + "\n"


def _ti3_text(measured):
    lines = ['CTI3', '', 'NUMBER_OF_FIELDS 7', 'BEGIN_DATA_FORMAT',
             'SAMPLE_ID RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z', 'END_DATA_FORMAT',
             f'NUMBER_OF_SETS {len(PATCHES)}', 'BEGIN_DATA']
    for i, (loc, rgb, _xyz) in enumerate(PATCHES, 1):
        m = measured[loc]
        lines.append(f'{i} {rgb[0]:.4f} {rgb[1]:.4f} {rgb[2]:.4f} '
                     f'{m[0]:.4f} {m[1]:.4f} {m[2]:.4f}')
    lines.append('END_DATA')
    return "\n".join(lines) + "\n"


class _Meta:
    def __init__(self, profile_settings=None):
        self.profile_settings = dict(profile_settings or {})


class _Run:
    """The parts of core.file_manager.Run the decision reads."""

    def __init__(self, d: Path, settings=None):
        self.dir = d
        self._settings = settings

    def built_profile_icc(self):
        return self.dir / "proj.icc"

    @property
    def measurement_ti3(self):
        return self.dir / "proj.ti3"

    @property
    def chart_ti2(self):
        return self.dir / "proj.ti2"

    @property
    def chart_ti1(self):
        return self.dir / "proj.ti1"

    def load_meta(self):
        return _Meta(self._settings)


def _project(tmp_path, *, colour="raw", printed_at=None, settings=None,
             record_extra=None, record=True, rgb_scale=1.0):
    """runs/run1 with a profile, a verification chart and its print record."""
    run_dir = tmp_path / "proj" / "runs" / "run1"
    vdir = run_dir / "verifications"
    vdir.mkdir(parents=True)
    icc = run_dir / "proj.icc"
    icc.write_bytes(b"not read: the tools are faked")
    old = (datetime.now() - timedelta(days=1)).timestamp()
    os.utime(icc, (old, old))
    ti2 = vdir / "proj-verify.ti2"
    ti2.write_text(_ti2_text(rgb_scale), encoding="utf-8")
    if record:
        rec = {"printed_at": printed_at or datetime.now().isoformat(timespec="seconds"),
               "colour": colour, "intent": "relative" if colour != "raw" else "",
               "route": "chromiq",
               "source_profile": str(tmp_path / "sRGB.icm") if colour != "raw" else "",
               "printer_calibration": {"profiling_chart": "off",
                                       "verification_chart": "off",
                                       "applied_at_print": False}}
        (tmp_path / "sRGB.icm").write_bytes(b"source")
        if colour != "raw":
            rec.update(profile="proj.icc", profile_path=str(icc),
                       profile_mtime=datetime.fromtimestamp(old).isoformat(
                           timespec="seconds"))
        rec.update(record_extra or {})
        (vdir / "proj-verify.print.json").write_text(json.dumps(rec), encoding="utf-8")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    # Named as the app looks them up on this system (`.exe` on Windows).
    ext = ".exe" if os.name == "nt" else ""
    for tool in ("xicclu", "cctiff"):
        (bin_dir / (tool + ext)).write_text("", encoding="utf-8")
    return _Run(run_dir, settings), ti2, vdir / "proj-verify.ti3", bin_dir


class _Tools:
    """Stands in for cctiff and xicclu. cctiff writes *sent* (0..255) for
    every patch; xicclu answers each device row with X = r*100, Y = g*100,
    Z = b*100 so the prediction shows which values it was asked about."""

    def __init__(self, sent=None, cctiff_rc=0, xicclu_rc=0, timeout=False):
        self.sent = sent
        self.cctiff_rc = cctiff_rc
        self.xicclu_rc = xicclu_rc
        self.timeout = timeout
        self.calls = []
        self.xicclu_rows = []

    def __call__(self, cmd, **kw):
        import numpy as np
        import tifffile
        name = Path(str(cmd[0])).name.removesuffix(".exe")
        self.calls.append([str(c) for c in cmd])
        if self.timeout:
            raise subprocess.TimeoutExpired(cmd, kw.get("timeout"))
        if name == "cctiff":
            if self.cctiff_rc:
                return subprocess.CompletedProcess(cmd, self.cctiff_rc, b"",
                                                   b"Can't open profile 'x'")
            src, dst = Path(cmd[-2]), Path(cmd[-1])
            n = tifffile.imread(src).reshape(-1, 3).shape[0]
            px = np.array(self.sent[:n], dtype=np.uint8)[None, :, :]
            tifffile.imwrite(dst, px, photometric="rgb", metadata=None)
            return subprocess.CompletedProcess(cmd, 0, b"", b"")
        if name == "xicclu":
            if self.xicclu_rc:
                return subprocess.CompletedProcess(cmd, self.xicclu_rc, b"", b"bad")
            rows = [[float(v) for v in line.split()]
                    for line in kw["input"].decode().splitlines() if line.strip()]
            self.xicclu_rows.append(rows)
            out = "\n".join(
                f"{r[0]:.6f} {r[1]:.6f} {r[2]:.6f} [RGB] -> Lut -> "
                f"{r[0] * 100:.6f} {r[1] * 100:.6f} {r[2] * 100:.6f} [XYZ]"
                for r in rows) + "\n"
            return subprocess.CompletedProcess(cmd, 0, out.encode(), b"")
        raise AssertionError(cmd)


def _flat(rows):
    return [float(v) for r in rows for v in r]


def _ti2_rgb01():
    return [[v / 100.0 for v in rgb] for _l, rgb, _x in PATCHES]


# ---- what was sent -----------------------------------------------------------
def test_raw_predicts_the_charts_own_rgb(tmp_path):
    run, ti2, ti3, bin_dir = _project(tmp_path, colour="raw")
    tools = _Tools()
    le = ve.live_expected(ti2, ti3, run, bin_dir=bin_dir, runner=tools)
    assert le.is_prediction, le.reason
    assert not any(Path(c[0]).stem == "cctiff" for c in tools.calls)
    assert _flat(tools.xicclu_rows[0]) == pytest.approx(_flat(_ti2_rgb01()), abs=1e-6)
    xic = next(c for c in tools.calls if Path(c[0]).stem == "xicclu")
    assert "-ff" in xic and "-ia" in xic and "-pX" in xic       # absolute XYZ
    assert xic[-1] == str(run.built_profile_icc())
    assert le.expected_for("A2") == pytest.approx((0.0, 0.0, 100.0))


def test_raw_reads_a_0_to_255_chart_on_the_0_to_100_scale(tmp_path):
    run, ti2, ti3, bin_dir = _project(tmp_path, colour="raw", rgb_scale=2.55)
    tools = _Tools()
    le = ve.live_expected(ti2, ti3, run, bin_dir=bin_dir, runner=tools)
    assert le.is_prediction
    assert _flat(tools.xicclu_rows[0]) == pytest.approx(_flat(_ti2_rgb01()), abs=1e-4)


def test_through_predicts_what_cctiff_sent_never_the_ti2_rgb(tmp_path):
    """THE -K TRAP'S ELDER BROTHER: on a sheet printed through the profile the
    .ti2 RGB is the sRGB design value, which was never printed."""
    run, ti2, ti3, bin_dir = _project(tmp_path, colour="through-profile")
    sent = [(10 + 20 * i, 200 - 15 * i, 30 + 5 * i) for i in range(len(PATCHES))]
    tools = _Tools(sent=sent)
    le = ve.live_expected(ti2, ti3, run, bin_dir=bin_dir, runner=tools)
    assert le.is_prediction, le.reason
    cct = next(c for c in tools.calls if Path(c[0]).stem == "cctiff")
    # The chain the print used: -i <intent> <source> -i <intent> <profile>.
    assert cct[cct.index("-i") + 1] == "r"
    assert cct[cct.index("-i") + 2] == str(tmp_path / "sRGB.icm")
    assert str(run.built_profile_icc()) in cct
    assert not any(a.endswith(".cal") for a in cct)
    want = [[v / 255.0 for v in s] for s in sent]
    assert _flat(tools.xicclu_rows[0]) == pytest.approx(_flat(want), abs=1e-6)
    assert _flat(tools.xicclu_rows[0]) != pytest.approx(_flat(_ti2_rgb01()), abs=1e-3)


def test_through_uses_the_recorded_intent(tmp_path):
    run, ti2, ti3, bin_dir = _project(tmp_path, colour="through-profile",
                                      record_extra={"intent": "perceptual"})
    tools = _Tools(sent=[(1, 2, 3)] * len(PATCHES))
    assert ve.live_expected(ti2, ti3, run, bin_dir=bin_dir, runner=tools).is_prediction
    cct = next(c for c in tools.calls if Path(c[0]).stem == "cctiff")
    assert [cct[i + 1] for i, a in enumerate(cct) if a == "-i"] == ["p", "p"]


CAL = ("CAL\n\nDESCRIPTOR \"x\"\nKEYWORD \"DEVICE_CLASS\"\nDEVICE_CLASS \"OUTPUT\"\n"
       "COLOR_REP \"RGB\"\nNUMBER_OF_FIELDS 4\nBEGIN_DATA_FORMAT\n"
       "RGB_I RGB_R RGB_G RGB_B\nEND_DATA_FORMAT\nNUMBER_OF_SETS 2\nBEGIN_DATA\n"
       "0 0 0 0\n1 {v} 1 1\nEND_DATA\n")


def _with_run_cal(run, v="0.9"):
    run.measurement_ti3.write_text(
        "CTI3\n\nBEGIN_DATA_FORMAT\nSAMPLE_ID RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z\n"
        "END_DATA_FORMAT\nBEGIN_DATA\n1 0 0 0 1 1 1\nEND_DATA\n" + CAL.format(v=v),
        encoding="utf-8")
    from workflow import printer_calibration as pc
    return pc.cal_sha1_of_text(pc.embedded_cal_text(run.measurement_ti3))


def test_k_through_with_the_profiles_own_calibration_predicts_before_it(tmp_path):
    run, ti2, ti3, bin_dir = _project(tmp_path, colour="through-profile")
    sha = _with_run_cal(run)
    rec_path = ti2.with_name("proj-verify.print.json")
    rec = json.loads(rec_path.read_text(encoding="utf-8"))
    rec["printer_calibration"] = {"profiling_chart": "apply", "verification_chart": "off",
                                  "applied_at_print": True,
                                  "cal_from": str(run.measurement_ti3), "cal_sha1": sha}
    rec_path.write_text(json.dumps(rec), encoding="utf-8")
    tools = _Tools(sent=[(9, 9, 9)] * len(PATCHES))
    le = ve.live_expected(ti2, ti3, run, bin_dir=bin_dir, runner=tools)
    assert le.is_prediction, le.reason
    cct = next(c for c in tools.calls if Path(c[0]).stem == "cctiff")
    assert not any(a.endswith(".cal") for a in cct), "predicted BEFORE the .cal"
    assert tools.xicclu_rows[0][0] == pytest.approx([9 / 255] * 3, abs=1e-6)


def test_k_through_with_another_calibration_predicts_the_values_sent(tmp_path):
    run, ti2, ti3, bin_dir = _project(tmp_path, colour="through-profile")
    _with_run_cal(run, v="0.9")
    other = tmp_path / "other.ti3"
    other.write_text("CTI3\n\nBEGIN_DATA_FORMAT\nSAMPLE_ID\nEND_DATA_FORMAT\n"
                     "BEGIN_DATA\n1\nEND_DATA\n" + CAL.format(v="0.5"), encoding="utf-8")
    from workflow import printer_calibration as pc
    other_sha = pc.cal_sha1_of_text(pc.embedded_cal_text(other))
    rec_path = ti2.with_name("proj-verify.print.json")
    rec = json.loads(rec_path.read_text(encoding="utf-8"))
    rec["printer_calibration"] = {"profiling_chart": "apply", "verification_chart": "off",
                                  "applied_at_print": True, "cal_from": str(other),
                                  "cal_sha1": other_sha}
    rec_path.write_text(json.dumps(rec), encoding="utf-8")
    tools = _Tools(sent=[(9, 9, 9)] * len(PATCHES))
    le = ve.live_expected(ti2, ti3, run, bin_dir=bin_dir, runner=tools)
    assert le.is_prediction, le.reason
    cct = next(c for c in tools.calls if Path(c[0]).stem == "cctiff")
    assert any(a.endswith(".cal") for a in cct), "the values sent carry the .cal"


def test_k_through_without_a_record_of_the_calibration_falls_back(tmp_path):
    run, ti2, ti3, bin_dir = _project(tmp_path, colour="through-profile")
    _with_run_cal(run)
    rec_path = ti2.with_name("proj-verify.print.json")
    rec = json.loads(rec_path.read_text(encoding="utf-8"))
    rec["printer_calibration"] = {"profiling_chart": "apply", "verification_chart": "off",
                                  "applied_at_print": False}
    rec_path.write_text(json.dumps(rec), encoding="utf-8")
    le = ve.live_expected(ti2, ti3, run, bin_dir=bin_dir, runner=_Tools(sent=[(1, 1, 1)] * 8))
    assert not le.is_prediction and "calibration" in le.reason


def test_k_raw_printed_without_the_profiles_calibration_falls_back(tmp_path):
    run, ti2, ti3, bin_dir = _project(tmp_path, colour="raw", record_extra={
        "printer_calibration": {"profiling_chart": "apply",
                                "verification_chart": "off",
                                "applied_at_print": False}})
    le = ve.live_expected(ti2, ti3, run, bin_dir=bin_dir, runner=_Tools())
    assert not le.is_prediction and "calibration" in le.reason


# ---- the fallbacks -----------------------------------------------------------
def test_falls_back_without_a_print_record(tmp_path):
    run, ti2, ti3, bin_dir = _project(tmp_path, record=False)
    tools = _Tools()
    le = ve.live_expected(ti2, ti3, run, bin_dir=bin_dir, runner=tools)
    assert le.source == ve.SOURCE_ESTIMATE and "print record" in le.reason
    assert not tools.calls


@pytest.mark.parametrize("extra", [{"route": "external"}, {"printed_at": ""},
                                   {"colour": "unknown"}])
def test_falls_back_for_a_sheet_chromiq_did_not_print(tmp_path, extra):
    run, ti2, ti3, bin_dir = _project(tmp_path, record_extra=extra)
    le = ve.live_expected(ti2, ti3, run, bin_dir=bin_dir, runner=_Tools())
    assert not le.is_prediction and "not printed by ChromIQ" in le.reason


def test_falls_back_without_a_profile(tmp_path):
    run, ti2, ti3, bin_dir = _project(tmp_path)
    run.built_profile_icc().unlink()
    le = ve.live_expected(ti2, ti3, run, bin_dir=bin_dir, runner=_Tools())
    assert not le.is_prediction and "no profile" in le.reason


def test_falls_back_when_the_profile_changed_since_a_through_print(tmp_path):
    run, ti2, ti3, bin_dir = _project(tmp_path, colour="through-profile")
    os.utime(run.built_profile_icc(), None)            # rebuilt now
    le = ve.live_expected(ti2, ti3, run, bin_dir=bin_dir,
                          runner=_Tools(sent=[(1, 1, 1)] * 8))
    assert not le.is_prediction and "changed since" in le.reason


def test_falls_back_when_the_sheet_went_through_another_profile(tmp_path):
    run, ti2, ti3, bin_dir = _project(tmp_path, colour="through-profile",
                                      record_extra={"profile": "merged.icc"})
    le = ve.live_expected(ti2, ti3, run, bin_dir=bin_dir,
                          runner=_Tools(sent=[(1, 1, 1)] * 8))
    assert not le.is_prediction and "merged.icc" in le.reason


def test_falls_back_when_the_profile_is_newer_than_a_raw_print(tmp_path):
    then = (datetime.now() - timedelta(days=2)).isoformat(timespec="seconds")
    run, ti2, ti3, bin_dir = _project(tmp_path, colour="raw", printed_at=then)
    le = ve.live_expected(ti2, ti3, run, bin_dir=bin_dir, runner=_Tools())
    assert not le.is_prediction and "changed since" in le.reason


@pytest.mark.parametrize("settings, word", [
    ({"illuminant": "A"}, "illuminant"),
    ({"g_illuminant": "D65"}, "illuminant"),
    ({"illuminant": "D50M2"}, "illuminant"),
    ({"observer": "1964_10"}, "observer"),
    ({"g_observer": "2015_2"}, "observer"),
    ({"fwa_enabled": True}, "FWA"),
    ({"g_fwa_enabled": True}, "FWA"),
])
def test_falls_back_for_a_profile_built_under_another_light(tmp_path, settings, word):
    run, ti2, ti3, bin_dir = _project(tmp_path, settings=settings)
    tools = _Tools()
    le = ve.live_expected(ti2, ti3, run, bin_dir=bin_dir, runner=tools)
    assert not le.is_prediction and word in le.reason
    assert not tools.calls


def test_the_default_build_settings_do_not_fall_back(tmp_path):
    run, ti2, ti3, bin_dir = _project(tmp_path, settings={
        "illuminant": "", "observer": "", "fwa_enabled": False,
        "g_illuminant": "", "g_observer": "", "g_fwa_enabled": False})
    assert ve.live_expected(ti2, ti3, run, bin_dir=bin_dir,
                            runner=_Tools()).is_prediction


@pytest.mark.parametrize("tools, word", [
    (_Tools(sent=[(1, 1, 1)] * 8, cctiff_rc=1), "cctiff"),
    (_Tools(sent=[(1, 1, 1)] * 8, xicclu_rc=1), "xicclu"),
    (_Tools(sent=[(1, 1, 1)] * 8, timeout=True), "did not finish"),
])
def test_falls_back_when_a_conversion_fails(tmp_path, tools, word):
    run, ti2, ti3, bin_dir = _project(tmp_path, colour="through-profile")
    le = ve.live_expected(ti2, ti3, run, bin_dir=bin_dir, runner=tools)
    assert not le.is_prediction and word in le.reason


def test_the_decision_never_raises(tmp_path):
    le = ve.live_expected(tmp_path / "missing.ti2", tmp_path / "x.ti3", None,
                          bin_dir=tmp_path)
    assert le.source == ve.SOURCE_ESTIMATE


def test_a_dated_verification_reads_its_own_snapshot_record(tmp_path):
    """The live record beside the chart describes the LAST print; a dated
    measurement's own chart/ snapshot outranks it (read_print_record)."""
    run, ti2, _ti3, bin_dir = _project(tmp_path, colour="raw")
    dated = ti2.parent / "2026-10-03_002252"
    (dated / "chart").mkdir(parents=True)
    (dated / "chart" / "proj-verify.print.json").write_text(json.dumps(
        {"printed_at": "2026-10-03T00:19:53", "colour": "raw", "route": "external"}), encoding="utf-8")
    le = ve.live_expected(ti2, dated / "proj-verify.ti3", run, bin_dir=bin_dir,
                          runner=_Tools())
    assert not le.is_prediction and "not printed by ChromIQ" in le.reason


# ---- the one substitution ----------------------------------------------------
def test_apply_expected_replaces_and_recomputes_like_the_engine():
    le = ve.LiveExpected(ve.SOURCE_PREDICTION, "t", {"A2": (10.0, 8.0, 40.0)})
    ev = [{"loc": "A2", "exyz": [18.05, 7.22, 95.05], "xyz": [9.0, 7.5, 38.0], "de": 100.0},
          {"loc": "Z9", "exyz": [1, 1, 1], "xyz": [2, 2, 2], "de": 5.0}]
    out = ve.apply_expected(ev, le)
    assert out[0]["exyz"] == [10.0, 8.0, 40.0]
    assert out[0]["de"] == round(engine_patch_de([10.0, 8.0, 40.0], [9.0, 7.5, 38.0]), 2)
    assert out[1] == ev[1]                                  # no prediction: as sent
    assert ev[0]["de"] == 100.0                             # the event is not touched
    assert ve.apply_expected(out, le) == out                # idempotent
    assert ve.apply_expected(ev, ve.estimate("x")) == ev
    assert ve.apply_expected(ev, None) == ev


def test_the_repaint_uses_the_same_function(tmp_path):
    ti2 = tmp_path / "c.ti2"
    ti2.write_text(_ti2_text(), encoding="utf-8")
    measured = {loc: tuple(v * 0.9 for v in x) for loc, _r, x in PATCHES}
    ti3 = tmp_path / "c.ti3"
    ti3.write_text(_ti3_text(measured), encoding="utf-8")
    le = ve.LiveExpected(ve.SOURCE_PREDICTION, "t",
                         {loc: tuple(v * 0.88 for v in x) for loc, _r, x in PATCHES})
    plain = per_patch_overlay(ti3, ti2)
    assert per_patch_overlay(ti3, ti2, expected=le) == ve.apply_expected(plain, le)
    assert per_patch_overlay(ti3, ti2, expected=None) == plain


# ---- the Measure tab -----------------------------------------------------------
class _Settings:
    def __init__(self, d=None):
        self._d = dict(d or {})

    def get(self, k, default=None):
        return self._d.get(k, default)

    def set(self, k, v):
        self._d[k] = v


def _tab(tmp_path, settings=None):
    from core.argyll_runner import ArgyllRunner
    from ui.tabs.tab_measure import TabMeasure
    s = _Settings(settings or {"chartread_engine": "chromiq"})
    tab = TabMeasure(ArgyllRunner(s), s)
    ti2 = tmp_path / "c.ti2"
    ti2.write_text(_ti2_text(), encoding="utf-8")
    tab._ti1_path = ti2
    tab._page_stripe_rects = [[QRect(0, 20 * i, 600, 18) for i in range(2)]]
    tab._strips_per_page = [2]
    tab._engine_strips = [{"strip": c} for c in "AB"]
    tab._patch_boxes = [{loc: QRect(22 * (int(loc[1]) - 1), 20 * "AB".index(loc[0]), 20, 18)
                         for loc, _r, _x in PATCHES}]
    return tab


#: Every patch of strip A read evenly ~ΔE 40 off its prediction: nothing
#: stands out from the strip, so the fence would hide every one of them.
PRED = {loc: tuple(x) for loc, _r, x in PATCHES}


def _shifted_strip(letter):
    out = []
    for loc, _r, x in PATCHES:
        if loc[0] != letter:
            continue
        m = (x[0] * 0.3, x[1] * 0.3, x[2] * 0.3)
        out.append({"id": loc, "loc": loc, "exyz": [1.0, 1.0, 1.0],
                    "xyz": list(m), "de": 150.0})
    return {"strip": letter, "patches": out}


def _flags(tab):
    by_box = {(b.x(), b.y()): loc for loc, b in tab._patch_boxes[0].items()}
    return {by_box[(it[0].x(), it[0].y())]: it[3]
            for it in tab._preview._patch_overlay.get(0, [])}


def _info(tab, loc):
    box = tab._patch_boxes[0][loc]
    for b, info in tab._preview._patch_info.get(0, []):
        if (b.x(), b.y()) == (box.x(), box.y()):
            return info
    raise AssertionError(loc)


def test_the_fence_is_ignored_and_the_limit_is_10_on_a_predicted_chart(qapp, tmp_path):
    """Beta 17: a verification chart's own strip-test box, off by default
    (Knut 6084176226), and its own patch error limit (5 by default since
    6070058549; 10 set here, as this test always measured at 10)."""
    tab = _tab(tmp_path, {"chartread_engine": "chromiq",
                          "patch_strip_test_estimated": True,
                          "patch_read_warn_de_prediction": 10.0})
    tab._live_expected = ve.LiveExpected(ve.SOURCE_PREDICTION, "t", PRED)
    assert tab._use_outlier_fence() is False
    assert tab._patch_warn_limit() == 10.0
    tab._on_strip_measured(_shifted_strip("A"))
    des = {loc: _info(tab, loc)["de"] for loc in ("A1", "A2", "A3", "A4")}
    for loc, d in des.items():
        want = engine_patch_de(PRED[loc], [v * 0.3 for v in PRED[loc]])
        assert d == pytest.approx(want, abs=0.01)            # against the prediction
    flagged = sorted(l for l, f in _flags(tab).items() if f)
    assert flagged == sorted(l for l, d in des.items() if d >= 10.0)
    assert len(flagged) >= 3                                 # the whole strip is off
    assert _info(tab, "A2")["exp_lab"][2] == pytest.approx(
        _lab(PRED["A2"])[2], abs=0.01)
    assert _info(tab, "A1")["fenced"] is False and _info(tab, "A1")["warn_de"] == 10.0


def _lab(xyz):
    from workflow.icc_info import xyz_to_lab
    return xyz_to_lab(tuple(v / 100.0 for v in xyz))


def test_the_fence_still_rules_every_other_chart(qapp, tmp_path):
    tab = _tab(tmp_path, {"chartread_engine": "chromiq",
                          "patch_strip_test_estimated": True})
    tab._live_expected = None
    assert tab._use_outlier_fence() is True
    assert tab._patch_warn_limit() == 95.0
    tab._live_expected = ve.estimate("no print record")
    assert tab._use_outlier_fence() is True
    # A second tab in a folder of its OWN inside tmp_path. Never `tmp_path /
    # ".."`: that is the worker's shared basetemp, and the c.ti2 written there
    # became the design reference of every later test's c.ti3 one folder down
    # (test_measurement_report.py read "design" for "device", 2026-10-03).
    (tmp_path / "second").mkdir()
    tab2 = _tab(tmp_path / "second", {"chartread_engine": "chromiq",
                                      "patch_strip_test_estimated": False})
    assert tab2._use_outlier_fence() is False                  # the user's own choice
    # The same evenly-off strip on a targen -c chart (accurate, NOT a
    # prediction): the user's fence still hides the strip there.
    (tmp_path / "acc").mkdir()
    acc = _tab(tmp_path / "acc", {"chartread_engine": "chromiq",
                                  "patch_strip_test_estimated": True})
    acc._ti1_path.write_text(_ti2_text().replace(
        'NUMBER_OF_FIELDS', 'ACCURATE_EXPECTED_VALUES "true"\nNUMBER_OF_FIELDS'),
        encoding="utf-8")
    ev = _shifted_strip("A")
    for p in ev["patches"]:
        p["exyz"] = list(PRED[p["loc"]])
        p["de"] = round(engine_patch_de(p["exyz"], p["xyz"]), 2)
    acc._on_strip_measured(ev)
    assert acc._patch_warn_limit() == 20.0 and acc._use_outlier_fence() is True
    over = [p["loc"] for p in ev["patches"] if p["de"] >= 20.0]
    flagged = [l for l, f in _flags(acc).items() if f]
    assert len(over) >= 3 and len(flagged) < len(over)


def test_the_repaint_is_the_live_judgement(qapp, tmp_path):
    """UMM 10.6 with 10.8: the outlines painted from disk after the read are
    the outlines of the read."""
    live = _tab(tmp_path)
    live._live_expected = ve.LiveExpected(ve.SOURCE_PREDICTION, "t", PRED)
    ev = _shifted_strip("A")
    live._on_strip_measured(ev)
    live_flags = _flags(live)
    live_de = {loc: _info(live, loc)["de"] for loc in live_flags}
    # The same readings on disk.
    measured = {p["loc"]: p["xyz"] for p in ev["patches"]}
    measured.update({loc: x for loc, _r, x in PATCHES if loc[0] == "B"})
    ti3 = tmp_path / "c.ti3"
    ti3.write_text(_ti3_text(measured), encoding="utf-8")
    le = ve.LiveExpected(ve.SOURCE_PREDICTION, "t", PRED)
    patches = [p for p in per_patch_overlay(ti3, tmp_path / "c.ti2", expected=le)
               if p["loc"][0] == "A"]
    paint = _tab(tmp_path)
    paint._live_expected = le
    paint._on_chart_measured({"patches": patches}, live=False, strip_fence=True)
    assert _flags(paint) == live_flags
    assert {loc: _info(paint, loc)["de"] for loc in live_flags} == live_de


def test_the_repaint_works_out_the_source_for_the_measurement_it_paints(
        qapp, tmp_path, monkeypatch):
    tab = _tab(tmp_path)
    seen = []
    le = ve.LiveExpected(ve.SOURCE_PREDICTION, "t", PRED)
    monkeypatch.setattr(tab, "_expected_source_for",
                        lambda ti3: (seen.append(ti3), le)[1])
    measured = {loc: tuple(v * 0.9 for v in x) for loc, _r, x in PATCHES}
    ti3 = tmp_path / "c.ti3"
    ti3.write_text(_ti3_text(measured), encoding="utf-8")
    monkeypatch.setattr(tab, "_existing_ti3_for_chart", lambda: ti3)
    monkeypatch.setattr(tab, "_locate_patch",
                        lambda loc: (0, tab._patch_boxes[0].get(loc)))
    assert tab._show_overlay_from_existing_ti3()
    assert seen == [ti3] and tab._live_expected is le
    assert _info(tab, "A2")["exp_lab"][2] == pytest.approx(_lab(PRED["A2"])[2], abs=0.01)


def test_a_session_asks_for_the_sheets_record(qapp, tmp_path, monkeypatch):
    """At the start of a read: the record beside the chart, or the dated
    folder a resume was staged from."""
    tab = _tab(tmp_path)
    seen = []
    monkeypatch.setattr(tab, "_is_verification_run", lambda: True)
    monkeypatch.setattr(tab, "_verification_run_obj", lambda: None)
    import workflow.verify_expected as mod
    monkeypatch.setattr(mod, "live_expected",
                        lambda chart, rec, run, **kw: (seen.append((chart, rec)),
                                                       ve.estimate("t"))[1])
    vdir = tmp_path / "verifications"
    vdir.mkdir()
    tab._ti1_path = vdir / "p-verify.ti2"
    tab._begin_live_expected()
    assert seen[-1][1] == vdir / "p-verify.ti3"
    tab._staged_verification_ti3 = vdir / "p-verify.ti3"
    tab._staged_from = vdir / "2026-10-03_002252" / "p-verify.ti3"
    tab._begin_live_expected()
    assert seen[-1][1] == vdir / "2026-10-03_002252" / "p-verify.ti3"
    # A chart outside verifications/ is never asked about.
    tab._ti1_path = tmp_path / "c.ti2"
    n = len(seen)
    tab._begin_live_expected()
    assert len(seen) == n and tab._live_expected is None


def test_the_patch_sound_hears_the_predicted_de(qapp, tmp_path):
    import core.sound as snd
    tab = _tab(tmp_path)
    played = []
    tab._sound = type("S", (), {"play": lambda self, e: played.append(e)})()
    loc, _r, x = PATCHES[1]
    ev = {"loc": loc, "exyz": [1, 1, 1], "xyz": list(x), "de": 140.0}
    tab._live_expected = ve.LiveExpected(ve.SOURCE_PREDICTION, "t", PRED)
    tab._on_patch_sound(ev)
    tab._live_expected = None
    tab._on_patch_sound(ev)
    assert played == [snd.PATCH_OK, snd.PATCH_OUT_OF_TOL]


def test_the_card_says_expected_is_the_profile_prediction(qapp, tmp_path):
    from ui.tiff_preview import _PatchInfoTile
    tab = _tab(tmp_path)
    tab._live_expected = ve.LiveExpected(ve.SOURCE_PREDICTION, "t", PRED)
    tab._on_strip_measured(_shifted_strip("A"))
    info = _info(tab, "A2")
    assert info["expected_source"] == "prediction" and info["accurate"] is True
    host = QWidget()
    tile = _PatchInfoTile(host)
    tile.set_content(info, "both")
    rows = [t for _s, t in tile._rows]
    assert "Expected: profile prediction" in rows and "Expected" not in rows
    (tmp_path / "other").mkdir()          # never tmp_path / "..": see above
    other = _tab(tmp_path / "other")
    other._on_strip_measured(_shifted_strip("A"))
    tile.set_content(_info(other, "A2"), "both")
    rows = [t for _s, t in tile._rows]
    assert "Expected" in rows and "Expected: profile prediction" not in rows


def test_the_card_line_is_approved_and_translated():
    from core.i18n import set_language, tr
    from workflow import measurement_messages as mm
    msg = mm.CATALOGUE["M-PATCH-EXPECTED-PREDICTED"]
    # Approved by Knut, #182 5965408335.
    assert msg.approved and msg.title == mm._CARD_EXPECTED_PREDICTED
    root = Path(__file__).resolve().parent.parent / "data" / "i18n"
    for f in sorted(root.glob("*.json")):
        assert mm._CARD_EXPECTED_PREDICTED in json.loads(f.read_text(encoding="utf-8")), f.name
    set_language("de")
    try:
        assert tr(mm._CARD_EXPECTED_PREDICTED) == "Erwartet: Profilvorhersage"
    finally:
        set_language("en")


# ---- the real tools ------------------------------------------------------------
def _argyll_bin():
    exe = shutil.which("xicclu")
    if exe and shutil.which("cctiff"):
        return Path(exe).parent
    p = Path("/Applications/Argyll/bin")
    return p if (p / "xicclu").exists() and (p / "cctiff").exists() else None


@pytest.mark.parametrize("colour", ["raw", "through-profile"])
def test_real_argyll_predicts_a_324_patch_sheet_quickly(tmp_path, colour):
    """xicclu and cctiff for real, with sRGB standing in as the run profile:
    the tifffile round trip through cctiff, the -pX parse, and the time."""
    bin_dir = _argyll_bin()
    if bin_dir is None:
        pytest.skip("ArgyllCMS xicclu/cctiff not installed")
    from workflow.verification_print import source_profile_path
    srgb = source_profile_path(bin_dir)
    if not srgb or not Path(srgb).is_file():
        pytest.skip("no sRGB profile")
    global PATCHES
    keep = PATCHES
    PATCHES = [(f"{chr(65 + i // 18)}{i % 18 + 1}",
                ((i * 37) % 101 * 1.0, (i * 53) % 101 * 1.0, (i * 71) % 101 * 1.0),
                (50.0, 50.0, 50.0)) for i in range(324)]
    try:
        run, ti2, ti3, _bin = _project(tmp_path, colour=colour)
        shutil.copy2(srgb, run.built_profile_icc())
        old = (datetime.now() - timedelta(days=1)).timestamp()
        os.utime(run.built_profile_icc(), (old, old))
        if colour != "raw":
            rec_path = ti2.with_name("proj-verify.print.json")
            rec = json.loads(rec_path.read_text(encoding="utf-8"))
            rec.update(source_profile=str(srgb), profile_mtime=datetime.fromtimestamp(
                old).isoformat(timespec="seconds"))
            rec_path.write_text(json.dumps(rec), encoding="utf-8")
        t = time.monotonic()
        le = ve.live_expected(ti2, ti3, run, bin_dir=bin_dir, use_cache=False)
        took = time.monotonic() - t
    finally:
        PATCHES = keep
    assert le.is_prediction, le.reason
    assert len(le.by_loc) == 324
    # A1 is device black: sRGB's black, absolute, is dark.
    assert le.expected_for("A1")[1] < 5.0
    assert took < 30.0, f"{took:.1f} s for 324 patches"


def test_tool_calls_are_capped_for_the_gui_thread():
    """Review AQ2: the prediction runs while the window waits, so no tool call
    may wait the module's 120 s."""
    import workflow.verify_expected as ve
    seen = {}

    def runner(*a, **kw):
        seen["timeout"] = kw.get("timeout")
        return "ok"
    assert ve._capped(runner)("x", timeout=120) == "ok"
    assert seen["timeout"] == ve._GUI_TIMEOUT_S <= 20
    ve._capped(runner)("x")
    assert seen["timeout"] == ve._GUI_TIMEOUT_S


def test_a_failed_prediction_is_remembered_like_a_success():
    import inspect
    import workflow.verify_expected as ve
    src = inspect.getsource(ve._decide)
    assert src.index("_predict(") < src.index("_CACHE[key] = result")


def test_a_predicted_card_names_its_limit_for_what_the_chart_is():
    """Knut, #182 5965408335: on a verification chart judged against its
    profile the red card says so, not "made from a profile"."""
    # Beta 17: the chart type is named with the limit, "verification charts"
    # (the k56 card Knut approved in 6084176226).
    from PyQt6.QtWidgets import QApplication, QWidget
    from ui.tiff_preview import _PatchInfoTile
    QApplication.instance() or QApplication([])
    host = QWidget()
    tile = _PatchInfoTile(host)
    tile.set_content({"loc": "H11", "exp_rgb": (60, 90, 160),
                      "meas_rgb": (70, 92, 150), "exp_lab": (39.1, 8.2, -45.3),
                      "meas_lab": (40.0, 5.1, -38.9), "de": 7.18,
                      "warn": True, "warn_de": 5.0, "accurate": True,
                      "expected_source": "prediction", "kind": "verification"},
                     "both")
    text = " ".join(t for _s, t in tile._rows)
    assert ("ΔE*ab 7.2 reached the patch error limit (5.0, verification "
            "charts).") in text
    assert "pre-conditioning" not in text
