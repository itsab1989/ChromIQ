"""The printer calibration a chart was printed with (#182, approved by
Sebastian in 5959070209 after 5958466861).

* RECORD — every chart records, at build time and by the engine that made it,
  whether the calibration was applied (-K), only embedded (-I) or not used,
  because printtarg writes the same .ti2 for -K and -I (printtarg.c
  3348-3352 / 3791-3795) and nothing can read the choice back later.
* MODE — one helper, ``calibration_mode_of``, answers it for any chart, old
  ones included, in a fixed order: the record, printtarg's registry
  snapshot, then (an engine chart with no record) the older engine -K whose
  .ti3 differs from the .ti1, then the printed pixels.
* B7 — a verification printed through the profile of a -K run goes sRGB ->
  profile -> the run's own calibration (extracted from its .ti3), in one
  cctiff chain; a verification chart itself built with -K is refused on that
  route; the raw route of a -K run warns; the print record says what was
  applied.
* C1 — Apply Calibration on a profile from an older engine -K run warns
  first (the profile already describes the uncalibrated printer).
"""
from __future__ import annotations

import hashlib
import json
import os
import textwrap
from pathlib import Path

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from workflow import printer_calibration as pc                 # noqa: E402
from workflow import verification_print as vp                  # noqa: E402
from workflow.layout_engine import calibration, chart          # noqa: E402

TI1 = textwrap.dedent("""\
    CTI1

    DESCRIPTOR "Argyll Calibration Target chart information 1"
    COLOR_REP "iRGB"

    NUMBER_OF_FIELDS 7
    BEGIN_DATA_FORMAT
    SAMPLE_ID RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z
    END_DATA_FORMAT

    NUMBER_OF_SETS 6
    BEGIN_DATA
    1 100.0 100.0 100.0 95.1 100.0 108.8
    2 50.0 50.0 50.0 20.0 21.0 23.0
    3 25.0 75.0 40.0 20.0 30.0 15.0
    4 80.0 10.0 60.0 30.0 20.0 25.0
    5 0.0 0.0 0.0 1.0 1.0 1.0
    6 60.0 30.0 90.0 25.0 20.0 60.0
    END_DATA
    """)


def _cal_text() -> str:
    x = np.linspace(0.0, 1.0, 256)
    curves = [lambda v: v ** 1.6, lambda v: v ** 0.7,
              lambda v: 0.5 * (v + v ** 2.5)]
    rows = "\n".join(" ".join(f"{c:.6f}" for c in [v] + [f(v) for f in curves])
                     for v in x)
    return ('CAL\n\nDESCRIPTOR "Argyll Device Calibration Curves"\n'
            'ORIGINATOR "test"\nDEVICE_CLASS "OUTPUT"\nCOLOR_REP "iRGB"\n\n'
            "NUMBER_OF_FIELDS 4\nBEGIN_DATA_FORMAT\nRGB_I RGB_R RGB_G RGB_B\n"
            "END_DATA_FORMAT\n\nNUMBER_OF_SETS 256\nBEGIN_DATA\n"
            f"{rows}\nEND_DATA\n")


CAL = _cal_text()


def _write_cgats(path: Path, kind: str, rows, *, originator="test",
                 fields=("RGB_R", "RGB_G", "RGB_B"), cal: str = "",
                 with_loc: bool = False):
    """A .ti2 / .ti3 with the given ``[(id, (r, g, b))]`` rows."""
    head = ["SAMPLE_ID"] + (["SAMPLE_LOC"] if with_loc else []) + list(fields) \
        + ["XYZ_X", "XYZ_Y", "XYZ_Z"]
    lines = [kind, "", f'ORIGINATOR "{originator}"', 'COLOR_REP "iRGB_XYZ"', "",
             f"NUMBER_OF_FIELDS {len(head)}", "BEGIN_DATA_FORMAT", " ".join(head),
             "END_DATA_FORMAT", "", f"NUMBER_OF_SETS {len(rows)}", "BEGIN_DATA"]
    for sid, dev in rows:
        vals = [f"{v:.5f}" for v in dev]
        lines.append(" ".join([str(sid)] + (['"A1"'] if with_loc else [])
                              + vals + ["10.0", "10.0", "10.0"]))
    lines.append("END_DATA")
    path.write_text("\n".join(lines) + "\n" + (("\n" + cal) if cal else ""),
                    encoding="utf-8")


TI1_ROWS = [(1, (100.0, 100.0, 100.0)), (2, (50.0, 50.0, 50.0)),
            (3, (25.0, 75.0, 40.0)), (4, (80.0, 10.0, 60.0)),
            (5, (0.0, 0.0, 0.0)), (6, (60.0, 30.0, 90.0))]


def _cal_obj(tmp_path):
    p = tmp_path / "c.cal"
    p.write_text(CAL, encoding="utf-8")
    return p, calibration.read_cal(p)


def _old_engine_run(tmp_path, *, delta=None, pad=False, originator=None,
                    cal_in_ti2=True, reorder=False, ti1=True):
    """A run folder laid out like an OLDER engine -K chart: the .ti2 and the
    .ti3 carry cal(dev), not dev. ``delta`` replaces that with dev + delta."""
    rdir = tmp_path / "P" / "runs" / "run1"
    rdir.mkdir(parents=True)
    calp, cal = _cal_obj(tmp_path)
    if ti1:
        (rdir / "P.ti1").write_text(TI1, encoding="utf-8")
    rows = []
    for sid, dev in TI1_ROWS:
        v = (tuple(x + delta for x in dev) if delta is not None
             else cal.apply(dev))
        v = tuple(min(100.0, max(0.0, x)) for x in v) if delta is None else v
        rows.append((sid, v))
    if pad:
        rows.append((7, (12.0, 34.0, 56.0)))       # a padding id the .ti1 lacks
    fields = ("RGB_R", "RGB_G", "RGB_B")
    ti3_rows, ti3_fields = rows, fields
    if reorder:            # the .ti3 lists its device columns in another order
        ti3_fields = ("RGB_B", "RGB_R", "RGB_G")
        ti3_rows = [(s, (v[2], v[0], v[1])) for s, v in rows]
    _write_cgats(rdir / "P.ti2", "CTI2", rows,
                 originator=originator or pc.ENGINE_ORIGINATOR,
                 cal=CAL if cal_in_ti2 else "", with_loc=True)
    _write_cgats(rdir / "P.ti3", "CTI3", ti3_rows, fields=ti3_fields, cal=CAL)
    from core.file_manager import Run
    return Run.for_dir(rdir)


# ===========================================================================
# RECORD
# ===========================================================================
class _S:
    def get(self, key, default=None):
        return default


@pytest.mark.parametrize("cal_on,apply,mode", [
    (True, True, "apply"), (True, False, "include"), (False, False, "off")])
def test_the_engine_records_how_it_used_the_calibration(tmp_path, cal_on,
                                                        apply, mode):
    from workflow.chart_creator import ChartCreator, ChartParams
    calp, _cal = _cal_obj(tmp_path)
    cc = ChartCreator(None, None, _S())
    p = ChartParams(engine_cal_path=str(calp) if cal_on else None,
                    engine_apply_cal=apply,
                    # printtarg's own row is hidden under the engine and must
                    # never be what is recorded for an engine chart
                    extra_printtarg_args=f"-I {calp}")
    cc._write_channel_sidecar(tmp_path, "c", p, engine="chromiq")
    rec = json.loads((tmp_path / "c.channels.json").read_text())[
        "printer_calibration"]
    assert rec["mode"] == mode
    assert rec["engine"] == "chromiq"
    if cal_on:
        assert rec["cal_sha1"] == hashlib.sha1(calp.read_bytes()).hexdigest()
        assert rec["cal_name"] == "c.cal"


@pytest.mark.parametrize("extra,mode", [
    ("-K {cal}", "apply"), ("-I {cal}", "include"), ("-K{cal}", "apply"),
    ("-N -D 'x y'", "off"), ("", "off")])
def test_printtarg_records_what_its_arguments_said(tmp_path, extra, mode):
    from workflow.chart_creator import ChartCreator, ChartParams
    calp, _cal = _cal_obj(tmp_path)
    cc = ChartCreator(None, None, _S())
    p = ChartParams(extra_printtarg_args=extra.format(cal=calp),
                    engine_cal_path=str(calp), engine_apply_cal=True)
    cc._write_channel_sidecar(tmp_path, "c", p)        # printtarg by default
    rec = json.loads((tmp_path / "c.channels.json").read_text())[
        "printer_calibration"]
    assert rec["mode"] == mode and rec["engine"] == "printtarg"


def test_the_record_decides_before_anything_else(tmp_path):
    """An engine chart whose .ti3 differs from its .ti1 would read as the
    older engine -K; a record says otherwise and wins."""
    run = _old_engine_run(tmp_path)
    assert pc.calibration_mode_of(run.chart_ti2, run.measurement_ti3) == \
        pc.MODE_OLD_ENGINE_APPLY
    run.chart_channels_json.write_text(json.dumps(
        {"printer_calibration": {"mode": "include"}}))
    assert pc.calibration_mode_of(run.chart_ti2, run.measurement_ti3) == "include"


def test_a_profiling_build_fills_calibration_used(tmp_path):
    """Decision 5 of calibration_run_type.md: RunMeta.calibration_used holds
    the calibration's stem, from the chart's own record."""
    from core.file_manager import Run
    from ui.tabs.tab_chart import TabChart
    rdir = tmp_path / "P" / "runs" / "run1"
    rdir.mkdir(parents=True)
    ti2 = rdir / "P.ti2"
    ti2.write_text("CTI2\n")
    side = rdir / "P.channels.json"
    side.write_text(json.dumps({"printer_calibration": {
        "mode": "apply", "cal_name": "P-cal.cal"}}))
    TabChart._record_calibration_used(None, ti2)
    assert Run.for_dir(rdir).load_meta().calibration_used == "P-cal"
    side.write_text(json.dumps({"printer_calibration": {"mode": "off"}}))
    TabChart._record_calibration_used(None, ti2)
    assert Run.for_dir(rdir).load_meta().calibration_used == ""
    # a verification chart is not the run's profiling chart
    vdir = rdir / "verifications"
    vdir.mkdir()
    (vdir / "P-verify.ti2").write_text("CTI2\n")
    (vdir / "P-verify.channels.json").write_text(json.dumps(
        {"printer_calibration": {"mode": "apply", "cal_name": "X.cal"}}))
    TabChart._record_calibration_used(None, vdir / "P-verify.ti2")
    assert Run.for_dir(rdir).load_meta().calibration_used == ""


# ===========================================================================
# MODE — older charts
# ===========================================================================
def _printtarg_chart(tmp_path, *, cal: bool, snapshot: "dict | None"):
    rdir = tmp_path / "P" / "runs" / "run1"
    rdir.mkdir(parents=True)
    (rdir / "P.ti1").write_text(TI1, encoding="utf-8")
    _write_cgats(rdir / "P.ti2", "CTI2", TI1_ROWS, originator="Argyll printtarg",
                 cal=CAL if cal else "", with_loc=True)
    if snapshot is not None:
        (rdir / "P.channels.json").write_text(json.dumps(
            {"create_chart_settings": snapshot}))
    return rdir / "P.ti2"


@pytest.mark.parametrize("cal,snapshot,mode", [
    (True, {"printtarg-K": {"enabled": True, "value": "/x/c.cal"},
            "printtarg-I": {"enabled": False, "value": ""}}, "apply"),
    (True, {"printtarg-K": {"enabled": False, "value": "/x/c.cal"},
            "printtarg-I": {"enabled": True, "value": "/x/c.cal"}}, "include"),
    (False, {"printtarg-K": {"enabled": True, "value": "/x/c.cal"}}, "off"),
    (True, None, "unknown"),
])
def test_a_printtarg_chart_without_a_record_reads_its_snapshot(
        tmp_path, cal, snapshot, mode):
    assert pc.calibration_mode_of(_printtarg_chart(tmp_path, cal=cal,
                                                   snapshot=snapshot)) == mode


def test_an_older_engine_k_run_is_recognised(tmp_path):
    run = _old_engine_run(tmp_path)
    assert pc.run_calibration_mode(run) == pc.MODE_OLD_ENGINE_APPLY
    assert pc.run_is_old_engine_apply(run)


@pytest.mark.parametrize("apply,mode", [(True, "apply"), (False, "include")])
def test_a_current_engine_chart_without_a_record_is_read_off_its_pixels(
        tmp_path, apply, mode):
    """The current engine writes .ti2 == .ti1 for -K and -I alike; only the
    pixels differ, and the sidecar's patch rectangles say where to look."""
    calp, _cal = _cal_obj(tmp_path)
    ti1 = tmp_path / "t.ti1"
    ti1.write_text(TI1, encoding="utf-8")
    res = chart.build_chart(ti1, tmp_path / "t", instrument="i1", paper="A4",
                            seed=1, dpi=72, cal_path=calp, apply_cal=apply)
    strips = json.loads((tmp_path / "t.strips.json").read_text())
    (tmp_path / "t.channels.json").write_text(json.dumps(
        {"layout": {"engine": "chromiq", **strips}}))
    assert pc.calibration_mode_of(res.ti2_path) == mode
    # without the rectangles nothing can be read: unknown, never a guess
    (tmp_path / "t.channels.json").write_text(json.dumps(
        {"layout": {"engine": "chromiq"}}))
    assert pc.calibration_mode_of(res.ti2_path) == pc.MODE_UNKNOWN


def test_no_calibration_anywhere_is_off(tmp_path):
    run = _old_engine_run(tmp_path, delta=0.0)
    for p in (run.chart_ti2, run.measurement_ti3):
        text = p.read_text()
        p.write_text(text[:text.index("\nCAL")] + "\n")
    assert pc.run_calibration_mode(run) == pc.MODE_OFF


# ===========================================================================
# C1 — the rule
# ===========================================================================
def test_c1_rounding_is_not_a_difference(tmp_path):
    run = _old_engine_run(tmp_path, delta=0.004)
    assert not pc.run_is_old_engine_apply(run)


def test_c1_a_real_difference_is(tmp_path):
    run = _old_engine_run(tmp_path, delta=0.06)
    assert pc.run_is_old_engine_apply(run)


def test_c1_padding_ids_the_ti1_lacks_are_not_compared(tmp_path):
    """The engine tops a last strip up with paper-white patches the .ti1
    never had; a value there must not count."""
    run = _old_engine_run(tmp_path, delta=0.0, pad=True)
    assert not pc.run_is_old_engine_apply(run)


def test_c1_matches_device_fields_by_name(tmp_path):
    run = _old_engine_run(tmp_path, delta=0.0, reorder=True)
    assert not pc.run_is_old_engine_apply(run)
    run2 = _old_engine_run(tmp_path / "b", reorder=True)
    assert pc.run_is_old_engine_apply(run2)


def test_c1_needs_the_engine_a_calibration_and_a_ti1(tmp_path):
    assert not pc.run_is_old_engine_apply(
        _old_engine_run(tmp_path / "a", originator="Argyll printtarg"))
    assert not pc.run_is_old_engine_apply(_old_engine_run(tmp_path / "b", ti1=False))
    run = _old_engine_run(tmp_path / "c")
    for p in (run.chart_ti2, run.measurement_ti3):
        text = p.read_text()
        p.write_text(text[:text.index("\nCAL")] + "\n")
    assert not pc.run_is_old_engine_apply(run)


def test_c1_skips_a_profile_in_a_verification(tmp_path):
    run = _old_engine_run(tmp_path)
    assert pc.run_for_profile(run.dir / "P.icc") is not None
    v = run.dir / "verifications" / "2026-10-02" / "P.icc"
    assert pc.run_for_profile(v) is None


def test_apply_calibration_warns_before_calibrating_twice(qapp, tmp_path,
                                                          monkeypatch):
    from PyQt6.QtWidgets import QMessageBox
    from ui.tabs.tab_profile import TabProfile
    from workflow import measurement_messages as M
    run = _old_engine_run(tmp_path)
    shown: list = []

    def fake_exec(box, *a, **k):
        shown.append(box.text())
        return 0                       # nothing clicked: Cancel, the default

    monkeypatch.setattr(QMessageBox, "exec", fake_exec)
    icc = run.dir / "P.icc"
    assert TabProfile._confirm_not_calibrated_twice(_Parent(), icc) is False
    assert shown == [M.M_CAL_APPLIED_TWICE.render()[0]]
    ok = _old_engine_run(tmp_path / "ok", delta=0.0)
    assert TabProfile._confirm_not_calibrated_twice(_Parent(), ok.dir / "P.icc")
    assert len(shown) == 1


def test_the_apply_calibration_button_asks_and_cancel_runs_nothing(
        qapp, tmp_path, monkeypatch):
    from PyQt6.QtCore import QSettings
    from PyQt6.QtWidgets import QMessageBox
    from core.argyll_runner import ArgyllRunner
    from core.settings import AppSettings
    from ui.tabs.tab_profile import TabProfile
    run = _old_engine_run(tmp_path)
    (run.dir / "P.icc").write_bytes(b"icc")
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "t.ini"), QSettings.Format.IniFormat)
    tab = TabProfile(ArgyllRunner(s), s)
    tab._ac_cal_edit.setText(str(tmp_path / "c.cal"))
    tab._ac_in_edit.setText(str(run.dir / "P.icc"))
    tab._ac_mode_combo.setCurrentIndex(tab._ac_mode_combo.findData("apply"))
    shown: list = []
    monkeypatch.setattr(QMessageBox, "exec",
                        lambda box, *a, **k: shown.append(box.text()) or 0)
    ran: list = []
    monkeypatch.setattr(tab._applycal_runner, "run",
                        lambda **k: ran.append(k))
    tab._on_applycal_run()
    assert len(shown) == 1 and not ran          # asked, and Cancel ran nothing
    # "Check" writes nothing, so it is not asked about
    tab._ac_mode_combo.setCurrentIndex(tab._ac_mode_combo.findData("check"))
    tab._on_applycal_run()
    assert len(shown) == 1 and len(ran) == 1
    tab.deleteLater()


def test_check_refine_warns_on_such_a_runs_calibrated_icc(qapp, tmp_path,
                                                          monkeypatch):
    from PyQt6.QtWidgets import QMessageBox
    from ui.tabs.tab_check_refine import TabCheckRefine
    run = _old_engine_run(tmp_path)
    shown: list = []
    monkeypatch.setattr(QMessageBox, "exec",
                        lambda box, *a, **k: shown.append(box.text()) or 0)
    me = _Parent()
    me._icc_path = run.calibrated_icc
    assert TabCheckRefine._warn_calibrated_twice(me) is False
    me._icc_path = run.dir / "P.icc"                 # the plain profile: fine
    assert TabCheckRefine._warn_calibrated_twice(me) is True
    assert len(shown) == 1


def _Parent():
    """A stand-in `self` for the two warning methods: a plain QWidget."""
    from PyQt6.QtWidgets import QWidget
    return QWidget()


@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


# ===========================================================================
# B7 — the verification print
# ===========================================================================
def _current_k_run(tmp_path, *, k_verify=False):
    """A -K run as the current engine leaves it: .ti2/.ti3 == .ti1, CAL
    embedded, the record says apply. And its verification chart."""
    run = _old_engine_run(tmp_path, delta=0.0)
    run.chart_channels_json.write_text(json.dumps(
        {"printer_calibration": {"mode": "apply", "cal_name": "c.cal"}}))
    run.verifications_dir.mkdir(parents=True)
    _write_cgats(run.verify_chart_ti2, "CTI2", TI1_ROWS,
                 originator=pc.ENGINE_ORIGINATOR,
                 cal=CAL if k_verify else "", with_loc=True)
    if k_verify:
        run.verify_chart_channels_json.write_text(json.dumps(
            {"printer_calibration": {"mode": "apply"}}))
    return run


def test_convert_args_put_the_calibration_after_the_profile():
    from workflow.cctiff_apply import convert_args
    a = convert_args(Path("s.icm"), Path("p.icc"), Path("i.tif"),
                     Path("o.tif"), intent="r", calibration=Path("c.cal"))
    assert a[a.index("p.icc") + 1] == "c.cal"
    assert a[-2:] == ["i.tif", "o.tif"]
    assert "c.cal" not in convert_args(Path("s.icm"), Path("p.icc"),
                                       Path("i.tif"), Path("o.tif"))


def test_a_k_run_prints_through_profile_then_its_own_calibration(tmp_path):
    run = _current_k_run(tmp_path)
    plan = vp.plan_calibration(run, run.verify_chart_ti2, vp.COLOUR_THROUGH,
                               tmp_path / "cache")
    assert not plan.refuse and plan.cal is not None
    # the calibration that was PRINTED: the one in the run's measurement
    assert plan.cal.read_text().strip() == \
        pc.embedded_cal_text(run.measurement_ti3).strip()
    assert plan.record["applied_at_print"] is True
    assert plan.record["cal_from"] == str(run.measurement_ti3)

    # and it reaches cctiff, after the profile, in one chain
    cmds: list = []

    class _R:
        returncode = 0
        stdout = stderr = ""

    def runner(cmd, **kw):
        cmds.append(cmd)
        Path(cmd[-1]).write_bytes(b"II*\x00")
        return _R()

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    from core.resource_path import argyll_binary
    (bin_dir / argyll_binary("cctiff")).write_text("")
    src = tmp_path / "sRGB.icm"
    src.write_bytes(b"x")
    prof = run.dir / "P.icc"
    prof.write_bytes(b"icc")
    page = tmp_path / "page.tif"
    page.write_bytes(b"II*\x00")
    vp.convert_pages_through_profile([page], prof, "relative",
                                     tmp_path / "out", bin_dir=bin_dir,
                                     source_profile=src, runner=runner,
                                     calibration=plan.cal)
    cmd = cmds[0]
    assert cmd[cmd.index(str(prof)) + 1] == str(plan.cal)


@pytest.mark.parametrize("make,why", [
    (lambda t: _old_engine_run(t), "older"),
    (lambda t: _old_engine_run(t, delta=0.0), "unknown"),     # CAL, no record
])
def test_other_runs_print_through_the_profile_alone(tmp_path, make, why):
    run = make(tmp_path)
    plan = vp.plan_calibration(run, None, vp.COLOUR_THROUGH, tmp_path / "c")
    assert plan.cal is None and not plan.refuse
    assert "no calibration" in plan.log


def test_include_and_off_print_through_the_profile_alone(tmp_path):
    for mode in ("include", "off"):
        run = _current_k_run(tmp_path / mode)
        run.chart_channels_json.write_text(json.dumps(
            {"printer_calibration": {"mode": mode}}))
        plan = vp.plan_calibration(run, run.verify_chart_ti2,
                                   vp.COLOUR_THROUGH, tmp_path / "c")
        assert plan.cal is None and not plan.refuse


def test_a_k_verification_chart_is_refused_through_the_profile(tmp_path):
    run = _current_k_run(tmp_path, k_verify=True)
    plan = vp.plan_calibration(run, run.verify_chart_ti2, vp.COLOUR_THROUGH,
                               tmp_path / "c")
    assert plan.refuse
    raw = vp.plan_calibration(run, run.verify_chart_ti2, vp.COLOUR_RAW,
                              tmp_path / "c")
    assert not raw.refuse and not raw.warn_raw
    assert raw.record["applied_at_print"] is True     # its pixels carry it


def test_the_raw_route_of_a_k_run_warns(tmp_path):
    run = _current_k_run(tmp_path)
    plan = vp.plan_calibration(run, run.verify_chart_ti2, vp.COLOUR_RAW,
                               tmp_path / "c")
    assert plan.warn_raw and not plan.refuse
    assert plan.record["applied_at_print"] is False


def test_a_k_run_whose_calibration_is_gone_does_not_print_uncalibrated(
        tmp_path):
    run = _current_k_run(tmp_path)
    for p in (run.chart_ti2, run.measurement_ti3):
        text = p.read_text()
        p.write_text(text[:text.index("\nCAL")] + "\n")
    plan = vp.plan_calibration(run, run.verify_chart_ti2, vp.COLOUR_THROUGH,
                               tmp_path / "c")
    assert plan.cal is not None and not plan.cal.exists()
    with pytest.raises(vp.VerificationPrintError):
        bin_dir = tmp_path / "bin"
        bin_dir.mkdir()
        from core.resource_path import argyll_binary
        (bin_dir / argyll_binary("cctiff")).write_text("")
        src = tmp_path / "s.icm"
        src.write_bytes(b"x")
        prof = tmp_path / "p.icc"
        prof.write_bytes(b"x")
        vp.convert_pages_through_profile(
            [tmp_path / "p.tif"], prof, "relative", tmp_path / "o",
            bin_dir=bin_dir, source_profile=src, calibration=plan.cal,
            runner=lambda *a, **k: pytest.fail("must not run"))


def test_the_print_record_says_what_was_applied(tmp_path):
    ti2 = tmp_path / "v.ti2"
    ti2.write_text("CTI2\n")
    vp.write_print_record(ti2, colour=vp.COLOUR_THROUGH, intent="relative",
                          profile=None, route=vp.ROUTE_CHROMIQ,
                          calibration={"profiling_chart": "apply",
                                       "applied_at_print": True})
    rec = json.loads(vp.print_record_path(ti2).read_text())
    assert rec["printer_calibration"]["applied_at_print"] is True


# --- the Print tab itself -------------------------------------------------
def _tab_env(tmp_path, *, k_verify=False):
    from PyQt6.QtCore import QSettings
    from core.file_manager import FileManager, Project
    from core.measurement_target import RUN_TYPE_VERIFICATION
    from core.settings import AppSettings
    from ui.measurement_target_bar import MeasurementTargetController
    from ui.tabs.tab_print import TabPrint
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    s.set("custom_output_path", str(tmp_path))
    s.set("use_native_print_dialog", False)
    fm = FileManager(s)
    Project.create(tmp_path / "P", "P").current_run().ensure_dir()
    fm.set_target_name("P")
    ctl = MeasurementTargetController(fm)
    run = fm.project().run("run1")
    stem = run.stem
    src = _current_k_run(tmp_path / "src", k_verify=k_verify)
    for name in ("ti1", "ti2", "ti3", "channels.json"):
        (run.dir / f"{stem}.{name}").write_bytes(
            (src.dir / f"P.{name}").read_bytes())
    run.verifications_dir.mkdir(parents=True, exist_ok=True)
    run.verify_chart_ti2.write_bytes(src.verify_chart_ti2.read_bytes())
    if k_verify:
        run.verify_chart_channels_json.write_bytes(
            src.verify_chart_channels_json.read_bytes())
    run.profile_icc.write_bytes(b"icc")
    page = run.verifications_dir / f"{run.verify_stem}_01.tif"
    from PIL import Image
    Image.new("RGB", (4, 4), (255, 255, 255)).save(page, format="TIFF")
    ctl.set_profile_run("run1")
    ctl.set_run_type(RUN_TYPE_VERIFICATION)
    tab = TabPrint(s)
    tab.set_target_controller(ctl)
    tab._current_ti2 = run.verify_chart_ti2
    tab.load_tiffs([page])
    tab._preview._pages = [(page, 0)]
    tab._preview._current = 0
    return tab, run, page


def test_the_print_tab_hands_the_runs_calibration_to_the_conversion(
        qapp, tmp_path, monkeypatch):
    tab, run, page = _tab_env(tmp_path)
    got: list = []

    def fake(pages, profile, intent, out_dir, **kw):
        got.append(kw.get("calibration"))
        return {p: p for p in pages}

    monkeypatch.setattr(vp, "convert_pages_through_profile", fake)
    out = tab._apply_verification_colour([(page, 0)])
    assert out is not None
    assert got and got[0] is not None and Path(got[0]).is_file()
    pending = tab._pending_print_record[1]
    assert pending["calibration"]["applied_at_print"] is True


def test_the_print_tab_refuses_a_k_verification_chart(qapp, tmp_path,
                                                      monkeypatch):
    from PyQt6.QtWidgets import QMessageBox
    from workflow import measurement_messages as M
    tab, run, page = _tab_env(tmp_path, k_verify=True)
    shown: list = []
    monkeypatch.setattr(QMessageBox, "exec",
                        lambda box, *a, **k: shown.append(box.text()) or 0)
    monkeypatch.setattr(vp, "convert_pages_through_profile",
                        lambda *a, **k: pytest.fail("must not convert"))
    assert tab._apply_verification_colour([(page, 0)]) is None
    assert shown == [M.M_CM_K_CHART_THROUGH.render()[0]]


def test_the_print_tab_asks_before_a_raw_print_of_a_k_run(qapp, tmp_path,
                                                          monkeypatch):
    from PyQt6.QtWidgets import QMessageBox
    tab, run, page = _tab_env(tmp_path)
    tab._cm_raw_rb.setChecked(True)
    shown: list = []
    monkeypatch.setattr(QMessageBox, "exec",
                        lambda box, *a, **k: shown.append(box.text()) or 0)
    assert tab._apply_verification_colour([(page, 0)]) is None    # Cancel
    from workflow import measurement_messages as M
    assert shown == [M.M_CM_RAW_UNCALIBRATED.render()[0]]
