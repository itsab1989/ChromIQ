"""#133 — the Measure tab's IMPORT module (verification runs).

A measurement made in i1Profiler enters the run through the same doors a
native verification read uses: guards, patch-for-patch validation, the dated
folder + chart snapshot, and only then the copy. These tests drive the real
tab offscreen; the fixture files are minimal CGATS tables (the real-Argyll
round trip is the on-screen driver's job).
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtCore import QSettings                        # noqa: E402
from PyQt6.QtWidgets import QApplication                  # noqa: E402

from core.argyll_runner import ArgyllRunner               # noqa: E402
from core.file_manager import FileManager, Project        # noqa: E402
from core.measurement_target import (                     # noqa: E402
    RUN_TYPE_PROFILING, RUN_TYPE_VERIFICATION)
from core.settings import AppSettings                     # noqa: E402
from ui.measurement_target_bar import MeasurementTargetController  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _env(tmp_path):
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    s.set("custom_output_path", str(tmp_path))
    fm = FileManager(s)
    Project.create(tmp_path / "P", "P").current_run().ensure_dir()
    fm.set_target_name("P")
    return s, fm, MeasurementTargetController(fm)


def _tab(s, fm, ctl):
    from ui.tabs.tab_measure import TabMeasure
    tab = TabMeasure(ArgyllRunner(s), s)
    tab.set_target_controller(ctl)
    return tab


#: Eight patches — RGB device values (0..100) with distinct design XYZ.
_PATCHES = [
    (0.0, 0.0, 0.0), (100.0, 100.0, 100.0), (100.0, 0.0, 0.0),
    (0.0, 100.0, 0.0), (0.0, 0.0, 100.0), (50.0, 50.0, 50.0),
    (25.0, 75.0, 10.0), (80.0, 20.0, 60.0),
]


def _cgats(kind: str, patches, extra_keywords: str = "") -> str:
    head = kind + "\n" + extra_keywords
    lines = [head,
             'DEVICE_CLASS "OUTPUT"', 'COLOR_REP "iRGB_XYZ"', "",
             "NUMBER_OF_FIELDS 8", "BEGIN_DATA_FORMAT",
             "SAMPLE_ID SAMPLE_LOC RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z",
             "END_DATA_FORMAT", "",
             f"NUMBER_OF_SETS {len(patches)}", "BEGIN_DATA"]
    for i, (r, g, b) in enumerate(patches, 1):
        # A crude, monotone XYZ so both files carry plausible colour columns.
        x, y, z = r * 0.6 + 5, g * 0.7 + 3, b * 0.5 + 2
        lines.append(f'{i} "{i}" {r:.4f} {g:.4f} {b:.4f} {x:.4f} {y:.4f} {z:.4f}')
    lines += ["END_DATA", ""]
    return "\n".join(lines)


def _verify_env(tmp_path):
    """A verification-ready run: profile + verify chart on disk, bar set."""
    s, fm, ctl = _env(tmp_path)
    run = fm.project().run("run1")
    run.profile_icc.write_bytes(b"icc")
    run.verifications_dir.mkdir(parents=True, exist_ok=True)
    run.verify_chart_ti2.write_text(_cgats("CTI2", _PATCHES))
    ctl.set_profile_run("run1")
    ctl.set_run_type(RUN_TYPE_VERIFICATION)
    return s, fm, ctl, run


def _measurement(tmp_path, patches=None, name="i1p-measurement.ti3") -> Path:
    p = tmp_path / name
    p.write_text(_cgats("CTI3", patches or _PATCHES))
    return p


def _capture_refusals(tab, monkeypatch):
    got: list = []
    monkeypatch.setattr(
        tab, "_show_import_refusal",
        lambda message, **kw: got.append((message.id, kw)))
    return got


def _silence_done_dialog(tab, monkeypatch):
    done: list = []
    monkeypatch.setattr(
        tab, "_show_import_done",
        lambda verification, dst: done.append((verification, dst)))
    # The how-printed question is a real modal (tested on its own below) —
    # mute it here or the happy path hangs offscreen.
    monkeypatch.setattr(tab, "_ask_how_printed", lambda ti3: None)
    return done


def test_import_button_appears_only_for_a_verification_run(qapp, tmp_path):
    s, fm, ctl = _env(tmp_path)
    tab = _tab(s, fm, ctl)
    assert not tab._import_btn.isVisibleTo(tab)
    ctl.set_profile_run("run1")
    ctl.set_run_type(RUN_TYPE_VERIFICATION)
    assert tab._import_btn.isVisibleTo(tab)
    # Switching away leaves the module and hides the button.
    tab._switch_mode("import")
    assert tab._stack.currentIndex() == 2
    ctl.set_run_type(RUN_TYPE_PROFILING)
    assert not tab._import_btn.isVisibleTo(tab)
    assert tab._stack.currentIndex() == 0


def test_import_mode_swaps_the_action_row(qapp, tmp_path):
    s, fm, ctl, run = _verify_env(tmp_path)
    tab = _tab(s, fm, ctl)
    tab._switch_mode("import")
    assert tab._import_go_btn.isVisibleTo(tab)
    for w in (tab._start_btn, tab._stop_btn, tab._save_defaults_btn):
        assert not w.isVisibleTo(tab)
    # No file chosen → the button is disabled and says why.
    assert not tab._import_go_btn.isEnabled()
    assert "folder button" in tab._import_go_btn.toolTip()
    tab._switch_mode("guided")
    assert not tab._import_go_btn.isVisibleTo(tab)
    assert tab._start_btn.isVisibleTo(tab)


def test_happy_path_files_a_copy_in_a_new_dated_folder(qapp, tmp_path,
                                                       monkeypatch):
    s, fm, ctl, run = _verify_env(tmp_path)
    tab = _tab(s, fm, ctl)
    tab._switch_mode("import")
    src = _measurement(tmp_path)
    before = src.read_text()
    tab._import_path = src
    refusals = _capture_refusals(tab, monkeypatch)
    done = _silence_done_dialog(tab, monkeypatch)

    tab._on_import_measurement()

    assert not refusals
    assert len(done) == 1
    verification, dst = done[0]
    assert dst.exists()
    assert dst.parent == verification.dir
    assert dst.parent.parent == run.verifications_dir
    # The verification marker is stamped, so the report/inspector treat it
    # as a verification and Build Profile never sees it.
    assert 'CHROMIQ_VERIFICATION "true"' in dst.read_text()
    # The bar moved to the new dated folder (same as a native read).
    assert ctl.target.verification_id == verification.id
    # The chart snapshot came along, so the result stays interpretable.
    from workflow.verify_chart_snapshot import has_snapshot
    assert has_snapshot(verification)
    # The user's original is untouched — ChromIQ filed a copy.
    assert src.read_text() == before
    assert "Measurement imported" in tab._log.toPlainText()


def test_a_patch_count_mismatch_is_refused_before_anything_is_written(
        qapp, tmp_path, monkeypatch):
    s, fm, ctl, run = _verify_env(tmp_path)
    tab = _tab(s, fm, ctl)
    tab._switch_mode("import")
    tab._import_path = _measurement(tmp_path, patches=_PATCHES[:5])
    refusals = _capture_refusals(tab, monkeypatch)

    tab._on_import_measurement()

    assert [r[0] for r in refusals] == ["M-IMPORT-MISMATCH"]
    reason = refusals[0][1]["reason"]
    assert "8" in reason and "5" in reason
    # Nothing was filed: no dated folder appeared.
    dated = [p for p in run.verifications_dir.iterdir() if p.is_dir()]
    assert dated == []


def test_reordered_patches_are_refused_by_the_identity_check(
        qapp, tmp_path, monkeypatch):
    """The pairing check the report itself uses: same patches, shuffled —
    exactly what measuring from the shuffled export produces."""
    s, fm, ctl, run = _verify_env(tmp_path)
    tab = _tab(s, fm, ctl)
    tab._switch_mode("import")
    shuffled = list(reversed(_PATCHES))
    tab._import_path = _measurement(tmp_path, patches=shuffled)
    refusals = _capture_refusals(tab, monkeypatch)

    tab._on_import_measurement()

    assert [r[0] for r in refusals] == ["M-IMPORT-MISMATCH"]
    dated = [p for p in run.verifications_dir.iterdir() if p.is_dir()]
    assert dated == []


def test_a_date_that_already_holds_a_measurement_is_refused(
        qapp, tmp_path, monkeypatch):
    s, fm, ctl, run = _verify_env(tmp_path)
    v = run.new_verification()
    v.ensure_dir()
    v.measurement_ti3.write_text(_cgats("CTI3", _PATCHES))
    kept = v.measurement_ti3.read_text()
    ctl.set_verification_id(v.id)
    tab = _tab(s, fm, ctl)
    tab._switch_mode("import")
    tab._import_path = _measurement(tmp_path)
    refusals = _capture_refusals(tab, monkeypatch)

    tab._on_import_measurement()

    assert [r[0] for r in refusals] == ["M-IMPORT-DATE-TAKEN"]
    assert v.measurement_ti3.read_text() == kept    # nothing replaced


def test_the_no_profile_guard_speaks_before_anything_runs(qapp, tmp_path,
                                                          monkeypatch):
    s, fm, ctl = _env(tmp_path)
    ctl.set_profile_run("run1")
    ctl.set_run_type(RUN_TYPE_VERIFICATION)
    tab = _tab(s, fm, ctl)
    tab._switch_mode("import")
    tab._import_path = _measurement(tmp_path)
    refusals = _capture_refusals(tab, monkeypatch)

    tab._on_import_measurement()

    assert [r[0] for r in refusals] == ["M-VERIFY-NO-PROFILE"]


def test_the_info_box_names_chart_and_destination(qapp, tmp_path):
    s, fm, ctl, run = _verify_env(tmp_path)
    tab = _tab(s, fm, ctl)
    tab._switch_mode("import")
    body = tab._import_box_body.text()
    assert run.verify_chart_ti2.name in body
    assert "8 patches" in body
    assert str(run.verifications_dir) in body
    # Choosing a chosen dated folder that already holds a measurement warns
    # in advance, before the user even presses the button.
    v = run.new_verification()
    v.ensure_dir()
    v.measurement_ti3.write_text(_cgats("CTI3", _PATCHES))
    ctl.set_verification_id(v.id)
    body = tab._import_box_body.text()
    assert "already holds a measurement" in body


def test_pretty_verification_when():
    from ui.tabs.tab_measure import TabMeasure
    assert TabMeasure._pretty_verification_when(
        "2026-08-09_142530") == "2026-08-09 14:25"
    assert TabMeasure._pretty_verification_when("custom-id") == "custom-id"


def test_report_dialog_gathers_all_dated_verifications(qapp, tmp_path):
    """Opening the report on ONE dated verification loads the run's WHOLE
    history — dates measured with report-saving off included (Sebastian,
    2026-08-10: three measured dates showed as '1 run')."""
    s, fm, ctl, run = _verify_env(tmp_path)
    ti3s = []
    for i in range(3):
        v = run.new_verification()
        v.ensure_dir()
        v.measurement_ti3.write_text(_cgats("CTI3", _PATCHES))
        import os, time
        t = time.time() - 300 + i * 60
        os.utime(v.measurement_ti3, (t, t))
        ti3s.append(v.measurement_ti3)

    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    dlg = MeasurementReportDialog(s, None, initial_ti3=ti3s[0])
    try:
        assert len(dlg._sources) == 1
        assert len(dlg._sources[0]["runs"]) == 3, \
            "all three dated verifications must be gathered"
        # Adding a sister date dedups — it is the same run's history.
        assert dlg._source_key(ti3s[1]) == dlg._source_key(ti3s[0])
    finally:
        dlg.deleteLater()


def test_measure_tab_report_opener_finds_dated_measurements(qapp, tmp_path,
                                                            monkeypatch):
    """After Restore Used Chart the Measure tab's report button claimed a
    measured verification chart was unmeasured — it looked beside the shared
    chart, where a verification's measurement never lives (Sebastian,
    2026-08-10)."""
    s, fm, ctl, run = _verify_env(tmp_path)
    v = run.new_verification()
    v.ensure_dir()
    v.measurement_ti3.write_text(_cgats("CTI3", _PATCHES))
    tab = _tab(s, fm, ctl)
    tab._ti1_path = run.verify_chart_ti2
    opened: list = []
    import ui.dialogs.measurement_report_dialog as mrd
    class _Fake:
        def __init__(self, *a, **kw):
            opened.append(kw.get("initial_ti3"))
        def exec(self):
            return 0
    monkeypatch.setattr(mrd, "MeasurementReportDialog", _Fake)

    # Without a selected date: the newest measured date is used.
    tab._open_measurement_report()
    assert opened and opened[-1] == v.measurement_ti3

    # With a date selected in the bar: that date wins.
    ctl.set_verification_id(v.id)
    tab._open_measurement_report()
    assert opened[-1] == v.measurement_ti3


def test_ask_how_printed_skips_when_a_record_exists(qapp, tmp_path, monkeypatch):
    """ChromIQ-printed sheets are never asked about — the record answers."""
    from workflow import verification_print as vp
    s, fm, ctl, run = _verify_env(tmp_path)
    v = run.new_verification()
    v.ensure_dir()
    (v.dir / "chart").mkdir()
    v.measurement_ti3.write_text(_cgats("CTI3", _PATCHES))
    vp.write_print_record(v.dir / "chart" / f"{run.verify_stem}.ti2",
                          colour=vp.COLOUR_RAW, intent="", profile=None,
                          route=vp.ROUTE_CHROMIQ)
    tab = _tab(s, fm, ctl)
    opened: list = []
    from PyQt6.QtWidgets import QMessageBox
    monkeypatch.setattr(QMessageBox, "exec",
                        lambda self, *a, **k: opened.append(1) or 0)
    tab._ask_how_printed(v.measurement_ti3)
    assert not opened, "a recorded sheet must never raise the question"


def test_ask_how_printed_stores_the_answer(qapp, tmp_path, monkeypatch):
    from workflow import verification_print as vp
    s, fm, ctl, run = _verify_env(tmp_path)
    v = run.new_verification()
    v.ensure_dir()
    v.measurement_ti3.write_text(_cgats("CTI3", _PATCHES))
    tab = _tab(s, fm, ctl)

    import json
    from PyQt6.QtWidgets import QMessageBox

    def _click(which):
        def _exec(box, *a, **k):
            for b in box.buttons():
                if which in b.text():
                    box._clicked = b        # noqa: SLF001 — test shim
                    break
            return 0
        return _exec

    # Answering "With colour management" writes the external-cm record.
    monkeypatch.setattr(QMessageBox, "exec", _click("colour management"))
    monkeypatch.setattr(QMessageBox, "clickedButton",
                        lambda self: getattr(self, "_clicked", None))
    tab._ask_how_printed(v.measurement_ti3)
    rec = vp.read_print_record(v.measurement_ti3)
    assert rec is not None
    assert rec["colour"] == vp.COLOUR_THROUGH
    assert rec["route"] == "external-cm"
    assert rec["recorded"] == "asked-at-measure"
    assert "printed_at" not in rec          # the print time is unknown

    # "Not sure" on a fresh date stores nothing.
    v2 = run.new_verification()
    v2.ensure_dir()
    v2.measurement_ti3.write_text(_cgats("CTI3", _PATCHES))
    monkeypatch.setattr(QMessageBox, "exec", _click("Not sure"))
    tab._ask_how_printed(v2.measurement_ti3)
    assert vp.read_print_record(v2.measurement_ti3) is None


def test_external_cm_answer_flips_the_report_yardstick(qapp, tmp_path,
                                                       monkeypatch):
    """The stored answer is what lets the report score the sheet fairly."""
    from workflow import verification_print as vp
    from workflow.measurement_report import build_report
    s, fm, ctl, run = _verify_env(tmp_path)
    v = run.new_verification()
    v.ensure_dir()
    v.measurement_ti3.write_text(_cgats("CTI3", _PATCHES))
    r = build_report(v.measurement_ti3)
    assert r["yardstick"] == "absolute"      # no record → judged as-is
    vp.write_print_record(v.measurement_ti3, colour=vp.COLOUR_THROUGH,
                          intent="unknown", profile=None, route="external-cm")
    r = build_report(v.measurement_ti3)
    assert r["yardstick"] == "media-relative"
    # A raw record keeps the absolute yardstick.
    vp.write_print_record(v.measurement_ti3, colour=vp.COLOUR_RAW,
                          intent="", profile=None, route="external")
    r = build_report(v.measurement_ti3)
    assert r["yardstick"] == "absolute"


def test_yardstick_golden_pins(qapp, tmp_path):
    """The scoring gate, pinned case by case: ONLY a white-mapping through
    print against the design reference switches yardsticks. Everything else
    is byte-identical to the absolute path."""
    from workflow import verification_print as vp
    from workflow.measurement_report import build_report
    s, fm, ctl, run = _verify_env(tmp_path)

    def _date_with(colour, intent, route=vp.ROUTE_CHROMIQ):
        v = run.new_verification()
        v.ensure_dir()
        v.measurement_ti3.write_text(_cgats("CTI3", _PATCHES))
        if colour is not None:
            vp.write_print_record(v.measurement_ti3, colour=colour,
                                  intent=intent, profile=None, route=route)
        return v.measurement_ti3

    # through + relative → media-relative (pairing 3)
    r = build_report(_date_with(vp.COLOUR_THROUGH, "relative"))
    assert r["yardstick"] == "media-relative"
    # through + ABSOLUTE intent → absolute stays (the print kept the ideal white)
    r = build_report(_date_with(vp.COLOUR_THROUGH, "absolute"))
    assert r["yardstick"] == "absolute"
    # paper white / max black stay physical facts in BOTH modes
    r2 = build_report(_date_with(vp.COLOUR_THROUGH, "relative"))
    assert r2["paper_white"]["lab"] == r["paper_white"]["lab"]

    # A colorimetric (gamut) chart NEVER switches — its reference already
    # includes the paper.
    from workflow.gamut_target import (GamutSelection, mark_chart_as_colorimetric,
                                       write_colorimetric_reference)
    from workflow.verification_print import colorimetric_reference_for
    sel = GamutSelection(master_version="T", master_total=8, in_gamut_total=8,
                         requested=8, intent="absolute", margin="safe")
    sel.targets = [(i, (50.0, 0.0, 0.0), (10.0 + i, 20.0, 30.0))
                   for i in range(8)]
    ref = colorimetric_reference_for(run.verify_chart_ti2)
    write_colorimetric_reference(sel, ref)
    mark_chart_as_colorimetric(run.verify_chart_ti2, ref)
    r = build_report(_date_with(vp.COLOUR_THROUGH, "relative"))
    assert r["reference_source"] == "colorimetric"
    assert r["yardstick"] == "absolute"
