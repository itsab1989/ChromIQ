"""Build step 9: START MEASUREMENT on the Measure tab and the table window.

* Beta ON, a profile run's chart for an i1iO 2 with an i1Pro 2 (its side file says so): START
  opens the table window, in Manual and in Guided, with the mode's own chartread arguments.
* Beta ON, a chart without such a side file (an i1iO 3, a bare "i1iO", a calibration chart):
  today's Start window, untouched.
* Beta OFF: nothing of the window is read or imported; Start is as before.
* The window's Save is announced as after a hand measurement (``measure_finished``)."""
from __future__ import annotations

import json
import sys

import pytest
from PyQt6.QtCore import Qt

from core.file_manager import Project
from tests.i1io_table import reader_sim as RS
from tests.i1io_table.test_job_reading import small_sheet
from tests.i1io_table.window_person import WindowPerson
from tests.i1io_table.window_sim import WindowSim


@pytest.fixture
def tab(qapp, tmp_path):
    from PyQt6.QtCore import QSettings
    from core.argyll_runner import ArgyllRunner
    from core.settings import AppSettings
    from ui.tabs.tab_measure import TabMeasure
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "app.ini"), QSettings.Format.IniFormat)
    s.set("custom_output_path", str(tmp_path / "out"))
    t = TabMeasure(ArgyllRunner(s), s)
    yield t
    w = getattr(t, "_table_window", None)
    if w is not None:
        w._finished = True
        w.close()
    t.close()
    t.deleteLater()


@pytest.fixture
def beta(monkeypatch):
    import workflow.i1io.support as sup
    sup.set_enabled_for_this_process(True)
    yield
    sup.set_enabled_for_this_process(None)


def table_run(tmp_path, sheet=None, *, side=True, head="i1Pro 2"):
    import copy
    sheet = copy.deepcopy(sheet or small_sheet())
    sheet["head_model"] = head
    # locations as charts name them: the strip's letter and the patch's number
    for pg in sheet["pages"]:
        for r, st in enumerate(pg["strips"]):
            for c, q in enumerate(st["patches"]):
                q["loc"] = f"{chr(65 + r)}{c + 1}"
    proj = Project.create(tmp_path / "Table-Target", "Table-Target")
    run = proj.current_run()
    run.ensure_dir()
    text = RS.chart_ti2_text(sheet).replace('TARGET_INSTRUMENT "X-Rite i1 Pro 2"',
                                            'TARGET_INSTRUMENT "X-Rite i1iO"')
    run.chart_ti2.write_text(text, encoding="ascii")
    run.artefact(".ti1").write_text(text.replace("CTI2", "CTI1", 1), encoding="ascii")
    if side:
        run.i1io_side_file.write_text(json.dumps(sheet), encoding="utf-8")
    return run, sheet


def start(tab, run, monkeypatch, sim=None):
    import ui.i1io_table_window as W
    sim = sim or WindowSim()
    monkeypatch.setattr(W, "JOB_FACTORY", sim.factory)
    monkeypatch.setattr(W, "USB_STATUS", lambda: (True, ""))
    tab._settings.set(W.CONSENT_KEY, W.CONSENT_VERSION)
    tab.set_ti1_path(run.artefact(".ti1"))
    monkeypatch.setattr(tab, "_blocked_by_new_run", lambda: False)
    monkeypatch.setattr(tab, "_i1io_not_yet_window",
                        lambda: pytest.fail("the table chart got today's Start window"))
    tab._on_start()
    return sim


@pytest.mark.parametrize("mode", ["manual", "guided"])
def test_start_opens_the_table_window_in_both_modes(tab, beta, tmp_path, monkeypatch, qtbot,
                                                   mode):
    monkeypatch.setattr(tab, "_current_mode", lambda: mode)
    run, sheet = table_run(tmp_path)
    sim = start(tab, run, monkeypatch)
    win = tab._table_window
    # the panel stands in the tab's own measurement area: no window of its own
    assert win is not None and win._mode == mode and not win.isWindow()
    assert tab._stack.currentWidget() is win and win.isVisibleTo(tab)
    assert win._chart_args[:3] == ["-v", "-c", "1"]                # the mode's own args
    assert win._chart_args[-1].endswith("Table-Target")
    finished = []
    tab.measure_finished.connect(finished.append)
    p = WindowPerson(win, sim, lambda c: qtbot.waitUntil(c, timeout=15000))
    p.drive_until("end_of_session")
    p.press("Save and stop")
    assert finished == [run.measurement_ti3]
    assert "[OK] Measurement complete." in tab._log.toPlainText()


def test_a_chart_without_the_side_file_keeps_todays_start_window(tab, beta, tmp_path,
                                                                 monkeypatch):
    run, sheet = table_run(tmp_path, side=False)
    shown = []
    monkeypatch.setattr(tab, "_i1io_window", lambda title, body: shown.append(title))
    tab.set_ti1_path(run.artefact(".ti1"))
    assert tab._started_the_table_drive() is False
    assert tab._refused_as_an_i1io_chart() is True and len(shown) == 1


def test_an_i1io_3_chart_keeps_todays_start_window(tab, beta, tmp_path, monkeypatch):
    run, sheet = table_run(tmp_path, head="i1Pro 3")
    tab.set_ti1_path(run.artefact(".ti1"))
    assert tab._started_the_table_drive() is False


def test_beta_off_reads_nothing_and_imports_no_window(tab, tmp_path, monkeypatch):
    import workflow.i1io.support as sup
    sup.set_enabled_for_this_process(False)
    try:
        run, sheet = table_run(tmp_path)
        tab.set_ti1_path(run.artefact(".ti1"))

        def asked(*_a, **_k):
            raise AssertionError("a chart was read for the table with the Beta off")
        monkeypatch.setattr(sup, "chart_names_i1io", asked)
        was = "ui.i1io_table_window" in sys.modules
        assert tab._started_the_table_drive() is False
        assert ("ui.i1io_table_window" in sys.modules) is was
    finally:
        sup.set_enabled_for_this_process(None)


def test_a_run_with_a_measurement_asks_the_hand_paths_replace_question_first(
        tab, beta, tmp_path, monkeypatch, qtbot):
    run, sheet = table_run(tmp_path)
    run.measurement_ti3.write_text("CTI3\n", encoding="ascii")
    asked = []
    monkeypatch.setattr(tab, "_confirm_replacing_measurement",
                        lambda: asked.append(1) or False)
    start(tab, run, monkeypatch)
    assert asked == [1] and getattr(tab, "_table_window", None) is None


def test_the_preferences_box_is_there_only_with_the_beta_on(qapp, tmp_path, monkeypatch):
    from PyQt6.QtCore import QSettings
    from core.settings import AppSettings
    from ui.dialogs.settings_dialog import SettingsDialog
    import workflow.i1io.support as sup
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "prefs.ini"), QSettings.Format.IniFormat)
    for on in (False, True):
        sup.set_enabled_for_this_process(on)
        try:
            dlg = SettingsDialog(s)
            box = getattr(dlg, "_i1io_ask_check", None)
            assert (box is not None) is on
            if on:
                assert box.isChecked()
                box.setChecked(False)
                dlg._save() if hasattr(dlg, "_save") else None
            dlg.deleteLater()
        finally:
            sup.set_enabled_for_this_process(None)



@pytest.mark.parametrize("pbp", [False, True], ids=["rows", "patch-by-patch"])
def test_the_preview_follows_the_job(tab, beta, tmp_path, monkeypatch, qtbot, pbp):
    """Rows mode: the strip of the row being read is highlighted (the hand path's
    _on_stripe_changed); patch by patch (-p): each patch before the arm moves to it
    (highlight_patch); every reading reaches the hand path's live overlay
    (_on_patch_measured)."""
    run, sheet = table_run(tmp_path)
    strips, patches, measured = [], [], []
    monkeypatch.setattr(tab, "_table_highlight_row",
                        lambda page, row, locs, status="": strips.append((page, row, locs[0]))
                        if not status else None)
    monkeypatch.setattr(tab, "_locate_patch", lambda loc: (0, loc))
    monkeypatch.setattr(tab._preview, "highlight_patch",
                        lambda page, box: patches.append(box))
    monkeypatch.setattr(tab, "_on_patch_measured", lambda ev: measured.append(ev["loc"]))
    import workflow.measure_manager as mm
    real = mm.MeasureManager._build_args

    def args(self, p):
        a = real(self, p)
        return (["-p"] + a) if pbp and "-p" not in a else [x for x in a if x != "-p" or pbp]
    monkeypatch.setattr(mm.MeasureManager, "_build_args", args)
    sim = start(tab, run, monkeypatch)
    win = tab._table_window
    p = WindowPerson(win, sim, lambda c: qtbot.waitUntil(c, timeout=15000))
    p.drive_until("end_of_session")
    qtbot.wait(50)
    rows = [st["patches"] for st in sheet["pages"][0]["strips"]]
    locs = [q["loc"] for r in rows for q in r]
    assert sorted(measured) == sorted(locs) and len(measured) == len(locs)  # every reading
    # fix round 10 (review 10, M-3): the row the job starts is the row highlighted, in the
    # job's order, in BOTH modes
    assert [(pg, r) for pg, r, _l in strips] == [(0, k) for k in range(len(rows))]
    if pbp:
        # the patch ringed before each move is the one read next, in the job's own order
        assert [b for b in patches if isinstance(b, str)] == measured
    else:
        assert not [b for b in patches if isinstance(b, str)]


def test_no_state_of_the_table_shows_a_modal_window(tab, beta, tmp_path, monkeypatch, qtbot):
    from PyQt6.QtWidgets import QApplication
    run, sheet = table_run(tmp_path)
    tab._settings.set("i1io_table_consent_given", 0)
    import ui.i1io_table_window as W
    sim = WindowSim()
    monkeypatch.setattr(W, "JOB_FACTORY", sim.factory)
    monkeypatch.setattr(W, "USB_STATUS", lambda: (True, ""))
    tab.set_ti1_path(run.artefact(".ti1"))
    monkeypatch.setattr(tab, "_blocked_by_new_run", lambda: False)
    tab._on_start()
    win = tab._table_window
    p = WindowPerson(win, sim, lambda c: qtbot.waitUntil(c, timeout=15000),
                     {"end_of_session": "Save and stop"})
    seen = []
    for _ in range(200):
        page = p.page()
        assert QApplication.activeModalWidget() is None, page
        assert not win.isWindow() and win.windowModality() == Qt.WindowModality.NonModal
        seen.append(page)
        if page == "done":
            break
        p.answer_page(page)
    assert {"consent", "go", "end_of_session", "done"} <= set(seen)
    p.press("Close")
    assert tab._table_window is None and tab._stack.currentWidget() is not win


def test_a_row_is_outlined_from_its_own_patch_boxes(tab, tmp_path):
    """The row being read: the preview's row overlay (set_scan_grid) with each row's cells
    from the chart's patch boxes; the active row is the job's, read rows are kept."""
    from PyQt6.QtCore import QRect
    sheet = {"pages": [{"strips": [{"patches": [{"loc": "A1"}, {"loc": "A2"}]},
                                   {"patches": [{"loc": "B1"}, {"loc": "B2"}]}]}]}
    tab._table_sheet = sheet
    tab._patch_boxes = [{"A1": QRect(0, 0, 10, 10), "A2": QRect(10, 0, 10, 10),
                         "B1": QRect(0, 20, 10, 10), "B2": QRect(10, 20, 10, 10)}]
    got = []
    tab._preview.set_table_rows = lambda page, rows, done=(), active=None, failed=(): got.append(
        (page, len(rows), set(done), active, rows[active][0] if active is not None else None))
    tab._table_highlight_row(0, 0, ["A1", "A2"])
    tab._table_highlight_row(0, 0, [], status="read")
    tab._table_highlight_row(0, 1, ["B1", "B2"])
    assert got[0] == (0, 2, set(), 0, QRect(0, 0, 10, 10))
    assert got[1][2] == {0} and got[1][3] is None
    assert got[2][2] == {0} and got[2][3] == 1
