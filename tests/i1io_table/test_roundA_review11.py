"""Round A of the i1iO table drive: review 11's findings, each with a test that failed before
the fix, and the owner's ruling on calibration and verification runs ("it just has to save the
measurement in the correct folder for every runtype with the correct name").

Against the simulated table and the simulated helper only (no USB, no instrument, no window
over the preview: the hand path's completion windows are answered by a stand-in for exec)."""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from core.file_manager import Calibration, Project, Run
from tests.i1io_table import reader_sim as RS
from tests.i1io_table.test_fix10_open_points import _measure_whole_chart, _rows_by_loc
from tests.i1io_table.test_fix10_open_points import _start_refining
from tests.i1io_table.test_fix10_review10 import _person
from tests.i1io_table.test_job_reading import small_sheet
from tests.i1io_table.test_window import moves, open_window, settings  # noqa: F401
from tests.i1io_table.test_window_in_the_measure_tab import beta, start, tab, table_run  # noqa: F401
from tests.i1io_table.window_sim import WindowSim
from ui import i1io_table_window as W
from workflow.measurement_state import Ti3State, classify

ROOT = Path(__file__).resolve().parents[2]


def _answer_windows(monkeypatch, seen=None, accept=False):
    """The hand path's completion windows, answered without a window on screen."""
    from PyQt6.QtWidgets import QDialog, QMessageBox, QPushButton
    seen = [] if seen is None else seen

    def exec_(dlg):
        seen.append((dlg.windowTitle(), [b.text() for b in dlg.findChildren(QPushButton)
                                         if b.isVisibleTo(dlg)],
                     " ".join(lab.text() for lab in dlg.findChildren(
                         __import__("PyQt6.QtWidgets", fromlist=["QLabel"]).QLabel))))
        return QDialog.DialogCode.Accepted if accept else QDialog.DialogCode.Rejected
    monkeypatch.setattr(QDialog, "exec", exec_)
    monkeypatch.setattr(QMessageBox, "exec", lambda self: seen.append(
        (self.windowTitle(), [], self.text())) or 0)
    return seen


def _finish(p, after_save=True):
    p.drive_until("end_of_session")
    p.press("Save and stop")
    p.drive_until(("home_offered", "done"))
    if p.page() == "home_offered":
        p.press("Leave it there")
    p.press("Close")


# ---- M-1: quit while the arm is brought home after a Save -------------------------------------

def test_m1_quit_while_homing_after_save_quits_without_an_error_page(
        tab, beta, tmp_path, monkeypatch, qtbot):
    _answer_windows(monkeypatch)
    run, sheet = table_run(tmp_path)
    sim = start(tab, run, monkeypatch)
    win = tab._table_window
    reasons = []
    win.finished_with.connect(reasons.append)
    p = _person(win, sim, qtbot)
    p.drive_until("end_of_session")
    p.press("Save and stop")
    p.drive_until("home_offered")
    sim.transport.delay_s = 0.05
    [b for b in win._buttons if b.text() == "Bring the arm home"][0].click()
    qtbot.wait(30)
    for _ in range(3):
        if win._busy:
            break
        [b for b in win._buttons if b.text() == "Go"][0].click()
        qtbot.wait(30)
    assert win._busy
    assert tab.confirm_quit_during_measurement() is False
    sim.transport.delay_s = 0.0
    qtbot.waitUntil(lambda: bool(reasons), timeout=15000)
    assert reasons == ["quit"]
    assert sim.jobs[0].phase == "closed"
    assert "refused" not in win.pages_shown and "error" not in win.pages_shown, \
        win.pages_shown[-6:]


def test_m1_no_reason_id_is_ever_shown_as_text():
    """Every id the job can return (the literals in its refusals, and the formed ones) has a
    sentence, and no sentence, known or not, carries the id itself."""
    src = "\n".join(p.read_text(encoding="utf-8")
                    for p in (ROOT / "workflow/i1io/table").glob("*.py"))
    ids = set(re.findall(r'Kind\.(?:REFUSED|STOPPED),\s*"([a-z][a-z0-9_]+)"', src))
    # the reader's and the spot rows' failure ids reach the panel as a row's "why"
    for name in ("spot.py", "reader.py"):
        ids |= set(re.findall(r'"((?:reading|reader|helper|calibration)_[a-z_]+)"',
                              (ROOT / "workflow/i1io/table" / name).read_text(encoding="utf-8")))
    ids |= {"ended_already_saved", "ended_already_discarded", "ended_already_nothing_read",
            "saved", "discarded", "nothing_read", "stopped_after_a_failed_row",
            "a_brand_new_id_nobody_wrote_a_sentence_for"}
    assert len(ids) > 30
    for rid in sorted(i for i in ids if "_" in i):   # (an id like "saved" is also a word)
        text = W.reason_text(rid)
        assert rid not in text, (rid, text)
        assert "(" + rid not in text
    # every id the job and its reader really return has its own sentence
    fallback = W.reason_text("a_brand_new_id_nobody_wrote_a_sentence_for")
    plain = [rid for rid in sorted(ids) if "_" in rid and W.reason_text(rid) == fallback
             and rid != "a_brand_new_id_nobody_wrote_a_sentence_for"]
    assert plain == [], plain


def test_m1_the_instrument_check_is_said_in_words():
    text = W.seen_text({"i1pro_devices": 2, "other_instruments": ["0765:5020"], "tables": 1})
    assert "i1pro_devices" not in text and "tables" not in text
    assert "2 instruments of the i1Pro family" in text and "0765:5020" in text


# ---- M-2: quit just after Start while the USB is being opened ----------------------------------

def test_m2_quit_while_the_usb_opens_never_finishes_under_the_running_worker(
        qtbot, monkeypatch, tmp_path, settings):
    win, sim, run, p, saved, finished = open_window(qtbot, monkeypatch, tmp_path, settings)
    p.drive_until("ready_to_open")
    for cb in win._tick_widgets:
        cb.setChecked(True)
    sim.delay_s = 0.0
    real_open = sim.jobs[0].open
    import threading
    gate = threading.Event()

    def slow_open():
        gate.wait(5)
        return real_open()
    # the answer runs job.answer in the worker, which goes on into the USB opening
    job = sim.jobs[0]
    real_answer = job.answer

    def slow_answer(kind, value):
        gate.wait(5)
        return real_answer(kind, value)
    monkeypatch.setattr(job, "answer", slow_answer)
    [b for b in win._buttons if b.text() == "Start"][0].click()
    assert win._busy and job.phase == "new"
    assert win.request_quit() is False            # never closes under the running worker
    assert not finished and win.isVisible()
    gate.set()
    qtbot.waitUntil(lambda: bool(finished), timeout=15000)
    assert finished == ["quit"]
    assert job.phase in ("new", "closed")         # let go of whatever was opened


def test_m2_request_quit_tests_busy_before_the_phase(qtbot, monkeypatch, tmp_path, settings):
    win, sim, run, p, saved, finished = open_window(qtbot, monkeypatch, tmp_path, settings)
    p.drive_until("ready_to_open")
    win._busy = True
    try:
        assert win.request_quit() is False
        assert not finished
    finally:
        win._busy = False


# ---- S-6, F10: a quit while the ending is on screen waits for the person -----------------------

def test_s6_quit_with_the_ending_open_keeps_it_and_moves_nothing(
        tab, beta, tmp_path, monkeypatch, qtbot):
    _answer_windows(monkeypatch)
    run, sheet = table_run(tmp_path)
    sim = start(tab, run, monkeypatch)
    win = tab._table_window
    p = _person(win, sim, qtbot)
    p.drive_until("end_of_session")
    n = moves(sim)
    assert tab.confirm_quit_during_measurement() is False
    p.idle()
    assert win.pages_shown[-1] == "end_of_session" and win._ending_open
    assert tab._table_window is win and moves(sim) == n
    assert sim.jobs[0].phase == "open"


# ---- S-6, F11: a refinement's Save writes the NEW readings of exactly the listed patches -------

def test_s6_a_refinement_save_writes_the_new_readings_of_the_listed_patches(
        tab, beta, tmp_path, monkeypatch, qtbot):
    _answer_windows(monkeypatch)
    run, sheet = table_run(tmp_path, small_sheet([4, 4, 4]))
    _measure_whole_chart(tab, run, monkeypatch, qtbot)
    fields, before = _rows_by_loc(run.measurement_ti3)
    # the simulated instrument reads DIFFERENT values now
    real = RS.spectrum_at
    # (the patches only: the table's white tile at rest stays white, so the stored-white
    # reference, on by default since 2026-11-18, keeps validating for both sessions)
    monkeypatch.setattr(RS, "spectrum_at",
                        lambda x, y: real(x, y) if y < 300 else [v * 0.5 for v in real(x, y)])
    sim = _start_refining(tab, run, monkeypatch, ["B"], ["B1", "B3"])
    p = _person(tab._table_window, sim, qtbot)
    _finish(p)
    _f, after = _rows_by_loc(run.measurement_ti3)
    changed = {loc for loc in before if before[loc] != after[loc]}
    assert changed == {"B1", "B3"}, changed


# ---- S-4: the report after a row that failed says it failed -------------------------------------

def test_s4_the_report_after_a_failed_row_says_it_could_not_be_read(
        tab, beta, tmp_path, monkeypatch, qtbot):
    _answer_windows(monkeypatch)
    run, sheet = table_run(tmp_path)
    sim = start(tab, run, monkeypatch, WindowSim(faults={"read_loc": {"B2": "dies"}}))
    win = tab._table_window
    p = _person(win, sim, qtbot)
    p.drive_until("row_failed")
    p.press("End this step")
    p.idle()
    assert win.pages_shown[-1] == "report_after_step", win.pages_shown[-3:]
    text = win._text.text()
    assert "could not be read" in text and "read its patches" not in text, text[:300]


def test_s4_texts():
    assert "read its patches" in W.step_done_text("read_row", {"row": 2, "page": 1,
                                                              "status": "read"})
    assert "could not be read" in W.step_done_text("read_row", {"row": 2, "page": 1,
                                                               "status": "skipped"})
    assert "could not be read" in W.step_done_text("read_row", {"row": 2},
                                                   page=1, reason="stopped_after_a_failed_row")
    assert "you pressed Stop" in W.step_done_text("read_row", {"row": 2}, page=1,
                                                reason="stopped_between_patches")


# ---- S-5: at a row's end the ring goes, the row's dot shows -------------------------------------

def test_s5_the_ring_goes_at_a_rows_end(tab, beta, tmp_path, monkeypatch, qtbot):
    run, sheet = table_run(tmp_path)
    tab.set_ti1_path(run.artefact(".ti1"))
    tab._table_sheet = sheet
    tab._table_patch_by_patch = True
    calls = []
    real = tab._preview.highlight_patch
    monkeypatch.setattr(tab._preview, "highlight_patch",
                        lambda page, box: calls.append(box) or real(page, box))
    tab._on_table_progress({"event": "patch_next", "loc": "A1", "page": 1, "row": 1})
    tab._on_table_progress({"event": "row_end", "page": 1, "row": 1, "status": "read"})
    assert calls and calls[-1] is None


# ---- S-2: a list of strips that names nothing of this chart ------------------------------------

def test_s2_a_strip_list_not_on_this_chart_is_refused_truthfully(
        tab, beta, tmp_path, monkeypatch, qtbot):
    _answer_windows(monkeypatch)
    run, sheet = table_run(tmp_path, small_sheet([4, 4, 4]))
    _measure_whole_chart(tab, run, monkeypatch, qtbot)
    sim = _start_refining(tab, run, monkeypatch, ["Q"], [])
    assert tab._table_window is None and sim.jobs == []          # nothing opened
    log = tab._log.toPlainText()
    assert "does not fit this chart" in log and "Q" in log
    assert "nothing to resume" not in log.lower()


# ---- S-3: a CR30 chart after a table chart keeps the CR30's greyed options ---------------------

def test_s3_cr30_chart_after_a_table_chart_keeps_its_dead_options_greyed(
        tab, beta, tmp_path, monkeypatch):
    run, sheet = table_run(tmp_path)
    tab.set_ti1_path(run.artefact(".ti1"))
    tol = next(o for o in tab._m_chartread_opts if o.key == "tolerance")
    assert not tol.checkbox.isEnabled()
    monkeypatch.setattr(tab, "_chart_is_cr30", lambda: True)
    monkeypatch.setattr(tab, "_table_chart_loaded", lambda: False)
    tab._apply_cr30_dead_options()
    assert tol.suppressed and not tol.checkbox.isEnabled()
    assert "CR30" in tol.checkbox.toolTip()


def test_s3_back_to_a_plain_chart_everything_comes_back(tab, beta, tmp_path, monkeypatch):
    run, sheet = table_run(tmp_path)
    tol = next(o for o in tab._m_chartread_opts if o.key == "tolerance")
    was = tol.checkbox.isEnabled()
    tab.set_ti1_path(run.artefact(".ti1"))
    assert not tol.checkbox.isEnabled()
    monkeypatch.setattr(tab, "_table_chart_loaded", lambda: False)
    tab._apply_cr30_dead_options()
    assert tol.checkbox.isEnabled() == was and not tol.suppressed


# ---- S-1: the legend chip never covers the chart's own print ------------------------------------

def _chip_rect(tab, qtbot, size):
    pv = tab._preview
    pv.resize(*size)
    pv.show()
    qtbot.wait(50)
    pv._refresh() if hasattr(pv, "_refresh") else pv.update()
    qtbot.wait(50)
    return pv


def test_s1_the_keepout_comes_from_the_side_file_and_only_for_an_i1io_chart(
        tab, beta, tmp_path):
    run, sheet = table_run(tmp_path)
    sheet["generation"] = {"dpi": 100}
    sheet["pages"][0]["wordmark_mm"] = [20.0, 280.0, 120.0, 290.0, 6.0]
    run.i1io_side_file.write_text(json.dumps(sheet), encoding="utf-8")
    tab.set_ti1_path(run.artefact(".ti1"))
    ko = tab._preview._legend_keepout
    assert 0 in ko and len(ko[0]) >= 2
    assert 0 not in tab._preview._legend_ink or tab._preview._legend_ink[0]
    wm = ko[0][1]
    assert abs(wm.y() - 280 * 100 / 25.4) < 1 and abs(wm.height() - 10 * 100 / 25.4) < 1


def test_s1_the_chip_takes_a_free_place_or_is_not_drawn(qapp):
    """The placement alone: patches ending at y 360, a wordmark line under them with free
    paper on its left; the chip goes beside the wordmark, never on it, and with no free place
    at all it is not drawn (never over the print)."""
    from PyQt6.QtCore import QRectF
    from PyQt6.QtGui import QFont, QImage, QPainter
    from ui.tiff_preview import TiffPreview
    pv = TiffPreview()
    img = QImage(800, 600, QImage.Format.Format_RGB32)
    painter = QPainter(img)
    painter.setFont(QFont("Helvetica", 11))
    try:
        obstacles = [QRectF(20, 20, 760, 340),        # the patches
                     QRectF(420, 370, 360, 30)]       # the wordmark and name line
        got = pv._legend_clear_place(painter, "expected ◤ · measured ◢ (screen colours "
                                     "approximate)", obstacles, 0, 0, 800, 410, 0, 400)
        assert got is not None
        cx, cy, tw, th, _t, _f = got
        chip = QRectF(cx, cy, tw, th)
        assert not any(chip.intersects(o) for o in obstacles), (chip, obstacles)
        assert pv._legend_clear_place(painter, "x", [QRectF(0, 0, 800, 410)],
                                      0, 0, 800, 410, 0, 400) is None
    finally:
        painter.end()


# ---- opinion (iii): Stop and Report a problem from the USB opening on --------------------------

def test_iii_stop_is_not_shown_before_the_usb_is_opened(qtbot, monkeypatch, tmp_path, settings):
    win, sim, run, p, saved, finished = open_window(qtbot, monkeypatch, tmp_path, settings)
    p.drive_until("ready_to_open")
    assert win._stop_btn.isHidden() and win._problem_btn.isHidden()
    p.answer_page("ready_to_open")
    p.drive_until(("go", "sheet_laid", "reader_consent"))
    assert sim.jobs[0].phase == "open"
    assert not win._stop_btn.isHidden() and not win._problem_btn.isHidden()


# ---- NOTES ----------------------------------------------------------------------------------------

def test_note_one_row_is_said_in_the_singular():
    assert W.rows_read_line(1, 1, 1, 1) == "Page 1 of 1: 1 of 1 row read."
    assert W.rows_read_line(1, 2, 3, 22) == "Page 1 of 2: 3 of 22 rows read."


def test_note_esc_in_the_note_field_does_not_ask_the_ending(
        qtbot, monkeypatch, tmp_path, settings):
    from PyQt6.QtCore import Qt
    win, sim, run, p, saved, finished = open_window(qtbot, monkeypatch, tmp_path, settings)
    p.drive_until("check_mark")
    win._show_note()
    win.activateWindow()
    win._note_edit.setFocus()
    qtbot.waitUntil(lambda: win._note_edit.hasFocus(), timeout=3000)
    shown = list(win.pages_shown)
    win.reject()                         # what the Esc shortcut calls
    p.idle()
    assert win.pages_shown == shown, win.pages_shown[-3:]
    win._note_edit.clearFocus()
    win.setFocus()
    qtbot.keyClick(win, Qt.Key.Key_Escape)


def test_note_acknowledged_app_markers_are_pruned_after_a_month(tmp_path):
    import os
    import time
    from workflow.i1io.table import session_end as se
    prefix = "chromiq-table-"
    old_m = tmp_path / se.app_in_use_name(prefix, "20250101-000000")
    new_m = tmp_path / se.app_in_use_name(prefix, "20261101-000000")
    open_m = tmp_path / se.app_in_use_name(prefix, "20250102-000000")
    for m in (old_m, new_m, open_m):
        m.write_text("{}", encoding="utf-8")
    for m in (old_m, new_m):
        se.acknowledged_path(m).write_text("{}", encoding="utf-8")
    past = time.time() - 40 * 86400
    os.utime(se.acknowledged_path(old_m), (past, past))
    assert se.app_markers(tmp_path, prefix) == [open_m]
    assert not old_m.exists() and not se.acknowledged_path(old_m).exists()
    assert new_m.exists() and open_m.exists()          # an unanswered one is never touched


def test_note_the_spec_says_dot_not_check_mark():
    text = (ROOT / "docs/design/i1io_table_support.md").read_text(encoding="utf-8")
    assert "green check mark" not in text


# ---- PART 2: every run type ---------------------------------------------------------------------

def _chart_text(sheet):
    return RS.chart_ti2_text(sheet).replace('TARGET_INSTRUMENT "X-Rite i1 Pro 2"',
                                            'TARGET_INSTRUMENT "X-Rite i1iO"')


def _locs(sheet):
    import copy
    sheet = copy.deepcopy(sheet)
    sheet["head_model"] = "i1Pro 2"
    r = 0
    for pg in sheet["pages"]:                 # one name per patch across every page
        for st in pg["strips"]:
            for c, q in enumerate(st["patches"]):
                q["loc"] = f"{chr(65 + r)}{c + 1}"
            r += 1
    return sheet


def cal_chart(tmp_path, sheet=None):
    sheet = _locs(sheet or small_sheet())
    proj = Project.create(tmp_path / "Table-Target", "Table-Target")
    cal = proj.calibration
    cal.ensure_dir()
    text = _chart_text(sheet)
    cal.ti2.write_text(text, encoding="ascii")
    cal.ti1.write_text(text.replace("CTI2", "CTI1", 1), encoding="ascii")
    cal.i1io_side_file.write_text(json.dumps(sheet), encoding="utf-8")
    return proj, cal, sheet


def verify_chart(tmp_path, sheet=None):
    sheet = _locs(sheet or small_sheet())
    proj = Project.create(tmp_path / "Table-Target", "Table-Target")
    run = proj.current_run()
    run.ensure_dir()
    run.verifications_dir.mkdir(parents=True, exist_ok=True)
    text = _chart_text(sheet)
    vc = run.verification_chart()
    vc.chart_ti2.write_text(text, encoding="ascii")
    run.verify_chart_ti1.write_text(text.replace("CTI2", "CTI1", 1), encoding="ascii")
    vc.i1io_side_file.write_text(json.dumps(sheet), encoding="utf-8")
    return proj, run, vc, sheet


def test_table_place_by_run_type(tmp_path):
    proj, cal, _s = cal_chart(tmp_path / "a")
    assert isinstance(W.table_place(cal.ti2), Calibration)
    assert W.table_place(cal.ti2).measurement_ti3 == cal.ti3
    proj2, run, vc, _s = verify_chart(tmp_path / "b")
    place = W.table_place(vc.chart_ti2)
    assert place.run_type == "verification"
    assert place.measurement_ti3.parent == run.verifications_dir
    assert place.i1io_table_dir == run.verifications_dir / "i1io-table"
    r = W.table_place(run.chart_ti2)
    assert isinstance(r, Run) and r.run_type == "profile"
    assert W.table_place(tmp_path / "elsewhere" / "x.ti2") is None
    assert W.drivable_sheet(cal.ti2) is not None and W.drivable_sheet(vc.chart_ti2) is not None


def _start_on(tab, chart_ti1, monkeypatch, sim=None):
    sim = sim or WindowSim()
    monkeypatch.setattr(W, "JOB_FACTORY", sim.factory)
    monkeypatch.setattr(W, "USB_STATUS", lambda: (True, ""))
    tab._settings.set(W.CONSENT_KEY, W.CONSENT_VERSION)
    if not W.calibration_place(tab._settings):
        tab._settings.set(W.CAL_KEY, "table tile")
    tab.set_ti1_path(chart_ti1)
    monkeypatch.setattr(tab, "_blocked_by_new_run", lambda: False)
    monkeypatch.setattr(tab, "_i1io_not_yet_window",
                        lambda: pytest.fail("the table chart got today's Start window"))
    tab._on_start()
    return sim


@pytest.mark.parametrize("cal_mode", [True, False])
def test_calibration_run_is_driven_and_saved_into_cal(tab, beta, tmp_path, monkeypatch, qtbot,
                                                      cal_mode):
    seen = _answer_windows(monkeypatch)
    tab._settings.set("calibration_mode", cal_mode)
    # a calibration never averages (with the calibration options off, the hand path
    # treats the chart as any other, and so does the table)
    tab._settings.set("averaging_enabled", cal_mode)
    finished = []
    tab.measure_finished.connect(finished.append)
    try:
        proj, cal, sheet = cal_chart(tmp_path)
        sim = _start_on(tab, cal.ti1, monkeypatch)
        win = tab._table_window
        assert win is not None and win._run.run_type == "calibration"
        p = _person(win, sim, qtbot)
        _finish(p)
        qtbot.waitUntil(lambda: bool(seen), timeout=5000)
    finally:
        tab._settings.set("calibration_mode", False)
        tab._settings.set("averaging_enabled", False)
    assert classify(cal.ti3, cal.ti2).state is Ti3State.COMPLETE
    assert sim.jobs[0].run.measurement_ti3 == cal.ti3
    assert [Path(f) for f in finished] == [cal.ti3]
    sessions = cal.i1io_table_sessions()
    assert len(sessions) == 1 and sessions[0].parent == cal.dir / "i1io-table"
    assert not (proj.root / "runs" / "run1" / "i1io-table").exists() \
        if hasattr(proj, "root") else True
    title, buttons, text = seen[0]
    if cal_mode:
        assert title == "Calibration Measurement Complete"
        assert "Create Calibration File →" in buttons and "calibration chart" in text
        assert not any("Re-read" in b for b in buttons)
    else:
        assert title == "All Patches Read"


@pytest.mark.parametrize("pages", [1, 2])
def test_verification_run_is_driven_and_filed_on_its_date(tab, beta, tmp_path, monkeypatch,
                                                          qtbot, pages):
    seen = _answer_windows(monkeypatch)
    finished = []
    tab.measure_finished.connect(finished.append)
    proj, run, vc, sheet = verify_chart(tmp_path, small_sheet(pages=pages))
    sim = _start_on(tab, run.verify_chart_ti1, monkeypatch)
    win = tab._table_window
    assert win is not None and win._run.run_type == "verification"
    p = _person(win, sim, qtbot)
    _finish(p)
    qtbot.waitUntil(lambda: bool(run.verifications()), timeout=5000)
    qtbot.wait(100)
    dated = run.verifications()
    assert len(dated) == 1
    ti3 = dated[0].measurement_ti3
    assert ti3.is_file() and ti3.name == f"{run.verify_stem}.ti3"
    assert classify(ti3, vc.chart_ti2).state is Ti3State.COMPLETE
    assert not vc.measurement_ti3.exists()             # nothing left beside the chart
    assert not run.measurement_ti3.exists()            # the profiling run untouched
    assert finished == []                              # never Build Profile
    assert (run.verifications_dir / "i1io-table").is_dir()
    assert "[OK] Verification measurement saved." in tab._log.toPlainText()


def test_a_quit_during_a_table_verification_files_it_without_windows(
        tab, beta, tmp_path, monkeypatch, qtbot):
    seen = _answer_windows(monkeypatch)
    proj, run, vc, sheet = verify_chart(tmp_path)
    sim = _start_on(tab, run.verify_chart_ti1, monkeypatch)
    win = tab._table_window
    p = _person(win, sim, qtbot)
    p.drive_until("end_of_session")
    tab.window().close = lambda: None
    assert tab.confirm_quit_during_measurement() is False
    p.press("Save and stop")
    for _ in range(10):
        if tab._table_window is None:
            break
        pg = p.page()
        if pg == "home_offered":
            p.press("Leave it there")
        elif pg == "done":
            p.press("Close")
    qtbot.waitUntil(lambda: bool(run.verifications()), timeout=5000)
    assert run.verifications()[0].measurement_ti3.is_file()
    assert seen == []


def _a_reading(sdir):
    (sdir / "p1").mkdir(parents=True, exist_ok=True)
    (sdir / "p1" / "r1.row.json").write_text(json.dumps({"seq": 1, "accepted": [{"loc": "A1"}]}),
                                             encoding="utf-8")


def test_calibration_reset_sets_the_table_sessions_aside(tmp_path):
    proj, cal, sheet = cal_chart(tmp_path)
    s1 = cal.i1io_table_session_dir("20261117-100000")
    s1.mkdir(parents=True)
    (s1 / "session.log").write_text("x", encoding="utf-8")
    _a_reading(s1)            # review 12, S-5: only a session that holds a reading is set aside
    # unmeasured: the chart goes, the session is set aside, never deleted
    res = cal.reset()
    assert not s1.exists()
    kept = list((cal.old_dir).glob("*/i1io-table/20261117-100000/session.log"))
    assert len(kept) == 1 and res.archive is None


def test_calibration_reset_of_a_measured_calibration_keeps_the_sessions_in_its_archive(
        tmp_path):
    proj, cal, sheet = cal_chart(tmp_path)
    cal.ti3.write_text("CTI3\n", encoding="ascii")
    s1 = cal.i1io_table_session_dir("20261117-100000")
    s1.mkdir(parents=True)
    _a_reading(s1)            # review 12, S-5: only a session that holds a reading is set aside
    res = cal.reset()
    assert res.archive is not None
    assert (res.archive / "i1io-table" / "20261117-100000").is_dir()
    assert cal.i1io_table_sessions() == []


def test_a_replaced_verification_chart_sets_its_table_sessions_aside(tmp_path):
    proj, run, vc, sheet = verify_chart(tmp_path)
    s1 = vc.i1io_table_session_dir("20261117-100000")
    s1.mkdir(parents=True)
    run._clear_verify_chart_files()
    assert vc.i1io_table_sessions() == []
    assert list(run.verifications_old_dir.glob("*/20261117-100000"))


def test_an_unanswered_marker_keeps_its_session_marked_discarded(tmp_path):
    proj, cal, sheet = cal_chart(tmp_path)
    s1 = cal.i1io_table_session_dir("20261117-100000")
    s1.mkdir(parents=True)
    (s1 / "TABLE_IN_USE.json").write_text("{}", encoding="utf-8")
    cal.reset()
    assert s1.is_dir() and (s1 / "discarded.json").is_file()


def test_a_marker_in_cal_is_asked_at_a_start_on_a_profile_run(tmp_path):
    from workflow.i1io.table import session_end as se
    proj, cal, sheet = cal_chart(tmp_path)
    run = proj.current_run()
    run.ensure_dir()
    s1 = cal.i1io_table_session_dir("20261117-100000")
    s1.mkdir(parents=True)
    (s1 / se.IN_USE_MARKER).write_text("{}", encoding="utf-8")
    assert (s1 / se.IN_USE_MARKER) in se.project_markers(Run.for_dir(run.dir))


def test_note_a_long_text_ends_on_a_whole_line_at_the_scroll_edge(
        qtbot, monkeypatch, tmp_path, settings):
    win, sim, run, p, saved, finished = open_window(qtbot, monkeypatch, tmp_path, settings,
                                                    consent=False)
    win.resize(420, 520)
    qtbot.wait(100)
    assert win.pages_shown[-1] == "consent"
    sc = win._scroll
    qtbot.waitUntil(lambda: sc.widget().sizeHint().height() > sc.height(), timeout=3000)
    qtbot.wait(100)
    ls = win._text.fontMetrics().lineSpacing()
    top = win._text.y() + win._text.contentsRect().y()
    visible = sc.viewport().height() - top
    assert visible % ls == 0, (visible, ls, sc.viewportMargins().bottom())


@pytest.mark.parametrize("height", [330, 430, 560, 900])
def test_note_the_answers_never_stand_over_the_text(qtbot, monkeypatch, tmp_path, settings,
                                                    height):
    """In the lowest panel the question's area is never squeezed under the answers (seen on
    screen in the smallest main window: the ending's text ran on under its buttons)."""
    win, sim, run, p, saved, finished = open_window(qtbot, monkeypatch, tmp_path, settings,
                                                    asking=False)
    p.drive_until("end_of_session")
    win.resize(440, height)
    qtbot.wait(150)
    from PyQt6.QtCore import QPoint
    text_bottom = win._text.mapTo(win, QPoint(0, win._text.height())).y()
    first = min(b.mapTo(win, QPoint(0, 0)).y() for b in win._buttons)
    if win._answers.parent() is win:
        # the answers under the panel's text area, never over it
        assert win._scroll.geometry().bottom() < first, (height, first)
    else:
        # the lowest panel: the answers scroll with the text, under it
        assert text_bottom <= first, (height, text_bottom, first)
    assert win._scroll.viewport().height() >= win._text.fontMetrics().lineSpacing() * 3
    # the footer with the one Stop stays in the panel, never in the scrolling area
    assert win._stop_btn.parent() is win and win._switch_off.parent() is win
