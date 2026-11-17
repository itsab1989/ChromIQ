"""Fix round 12 of the i1iO table drive: review 12's findings, each with a test that failed before
the fix (most of them start from the reviewer's probes, `review12/.../test_review12_probes.py`).

Against the simulated table and the simulated helper only (no USB, no instrument; the hand
path's completion windows are answered by a stand-in for exec)."""
from __future__ import annotations

import json
import re
import shutil
import types
from pathlib import Path

import pytest

from core.file_manager import Calibration, Run
from tests.i1io_table import reader_sim as RS
from tests.i1io_table.test_fix10_review10 import _person
from tests.i1io_table.test_roundA_review11 import (_answer_windows, _finish, _start_on,
                                                   cal_chart, verify_chart)
from tests.i1io_table.test_window import open_window, settings  # noqa: F401
from tests.i1io_table.test_window_in_the_measure_tab import beta, tab, table_run, start  # noqa: F401
from tests.i1io_table.window_sim import WindowSim
from ui import i1io_table_window as W
from workflow.i1io.table import session_end as se
from workflow.measurement_state import Ti3State, classify


def _to_done(p):
    p.drive_until("end_of_session")
    p.press("Save and stop")
    p.drive_until(("home_offered", "done"))
    if p.page() == "home_offered":
        p.press("Leave it there")
    p.drive_until("done")


def _target(tab, run, vid):
    """The target bar as a verification of *run*, on the date *vid* ("" = New verification)."""
    tab._target_ctl = types.SimpleNamespace(
        target=types.SimpleNamespace(verification_id=vid, profile_run=run.id,
                                     is_verification=lambda: True),
        project_or_none=lambda: None)
    # (the hand path's guard asks the bar for a built profile, which these runs do not need)
    tab._verification_guard = lambda: None


# ---- M-1: whatever closes the panel after a Save, a verification is filed ---------------------

@pytest.mark.parametrize("how", ["esc", "window_close", "close_button"])
def test_m1_a_saved_verification_is_filed_whatever_closes_the_last_page(
        tab, beta, tmp_path, monkeypatch, qtbot, how):
    _answer_windows(monkeypatch)
    proj, run, vc, sheet = verify_chart(tmp_path)
    sim = _start_on(tab, run.verify_chart_ti1, monkeypatch)
    win = tab._table_window
    why = []
    win.finished_with.connect(why.append)
    p = _person(win, sim, qtbot)
    _to_done(p)
    assert vc.measurement_ti3.is_file()            # saved beside the chart, not yet filed
    if how == "esc":
        win.reject()                               # the panel's Esc shortcut
    elif how == "window_close":
        win.close()
    else:
        p.press("Close")
    qtbot.waitUntil(lambda: tab._table_window is None, timeout=5000)
    qtbot.waitUntil(lambda: bool(run.verifications()), timeout=5000)
    assert why == ["ended"], why
    assert not vc.measurement_ti3.exists(), "left unfiled beside the chart"
    [v] = run.verifications()
    assert classify(v.measurement_ti3, vc.chart_ti2).state is Ti3State.COMPLETE


def test_m1_esc_on_the_done_page_of_a_profile_run_ends_it(tab, beta, tmp_path, monkeypatch,
                                                          qtbot):
    seen = _answer_windows(monkeypatch)
    run, sheet = table_run(tmp_path)
    sim = start(tab, run, monkeypatch)
    win = tab._table_window
    why = []
    win.finished_with.connect(why.append)
    p = _person(win, sim, qtbot)
    _to_done(p)
    win.reject()
    qtbot.waitUntil(lambda: tab._table_window is None, timeout=5000)
    qtbot.waitUntil(lambda: bool(seen), timeout=5000)     # the usual completion window
    assert why == ["ended"], why


def test_m1_a_verification_is_filed_even_when_the_panel_ends_otherwise(
        tab, beta, tmp_path, monkeypatch, qtbot):
    """The tab files a saved verification whatever `why` the panel finishes with."""
    _answer_windows(monkeypatch)
    proj, run, vc, sheet = verify_chart(tmp_path)
    sim = _start_on(tab, run.verify_chart_ti1, monkeypatch)
    win = tab._table_window
    p = _person(win, sim, qtbot)
    _to_done(p)
    win._finish("not_started")
    qtbot.waitUntil(lambda: tab._table_window is None, timeout=5000)
    qtbot.waitUntil(lambda: bool(run.verifications()), timeout=5000)
    assert not vc.measurement_ti3.exists()


def test_m1_a_stray_verification_beside_the_chart_is_archived_at_start_and_never_blocks_save(
        tab, beta, tmp_path, monkeypatch, qtbot):
    """What a kill between the table's Save and its filing leaves: the hand path's START moves
    it to old/ first, and so does the table's; the whole chart read next can be saved."""
    _answer_windows(monkeypatch)
    proj, run, vc, sheet = verify_chart(tmp_path)
    sim = _start_on(tab, run.verify_chart_ti1, monkeypatch)
    _finish(_person(tab._table_window, sim, qtbot))
    qtbot.waitUntil(lambda: bool(run.verifications()), timeout=5000)
    qtbot.wait(100)
    [first] = run.verifications()
    stray = vc.measurement_ti3
    shutil.copyfile(first.measurement_ti3, stray)             # the unfiled file a kill leaves
    stray_bytes = stray.read_bytes()
    _target(tab, run, "")                                     # New verification
    sim2 = _start_on(tab, run.verify_chart_ti1, monkeypatch)
    win2 = tab._table_window
    assert win2 is not None
    assert not stray.exists(), "the stray file is still beside the chart at START"
    kept = sorted((run.verifications_dir / "old").glob("*/" + stray.name))
    assert [k.read_bytes() for k in kept] == [stray_bytes]
    p2 = _person(win2, sim2, qtbot)
    p2.drive_until("end_of_session")
    p2.press("Save and stop")
    p2.drive_until(("home_offered", "done", "refused", "error"))
    assert p2.page() in ("home_offered", "done"), (p2.page(), win2._text.text()[:300])


# ---- M-2: an old chart's sessions are never completed into a new chart ------------------------

def _session(place, stamp="20261117-100000", identity=True, chart=None):
    sdir = place.i1io_table_session_dir(stamp)
    sdir.mkdir(parents=True)
    (sdir / "session.log").write_text("x", encoding="utf-8")
    if identity:
        se.write_identity(sdir, chart if chart is not None else place.chart_ti2, place)
    return sdir


def test_m2_replace_of_a_verification_chart_sets_the_table_sessions_aside(tmp_path):
    """Review 12's probe R12-2: the import / Create Chart Replace archives the chart first."""
    from workflow.chart_import import archive_run_for_replace
    proj, run, vc, sheet = verify_chart(tmp_path)
    s1 = _session(vc)
    archive_run_for_replace(run, verification=True)
    run._clear_verify_chart_files()
    assert vc.i1io_table_sessions() == [], "the old chart's sessions stay for the new chart"
    moved = list((run.verifications_dir / "old").glob("*/" + s1.name))
    assert len(moved) == 1 and (moved[0] / "session.log").is_file()


def test_m2_clearing_a_verification_chart_with_no_chart_files_sets_the_sessions_aside(tmp_path):
    proj, run, vc, sheet = verify_chart(tmp_path)
    s1 = _session(vc)
    for f in list(run.verifications_dir.glob("*")):
        if f.is_file():
            run.archive_to_old([f], into=run.verifications_old_dir)
    run._clear_verify_chart_files()
    assert vc.i1io_table_sessions() == []


def _killed_copy(sdir: Path, stamp: str) -> Path:
    dst = sdir.parent / stamp
    shutil.copytree(sdir, dst, ignore=shutil.ignore_patterns(
        "session_result.json", "filing*.json", "*.acknowledged.json", "discarded.json"))
    return dst


def _saved_session(tab, chart_ti1, place, monkeypatch, qtbot):
    sim = _start_on(tab, chart_ti1, monkeypatch)
    _finish(_person(tab._table_window, sim, qtbot))
    qtbot.waitUntil(lambda: tab._table_window is None, timeout=5000)
    qtbot.wait(100)
    [s] = place.i1io_table_sessions()
    return s


def test_m2_a_session_records_the_chart_it_reads(tab, beta, tmp_path, monkeypatch, qtbot):
    _answer_windows(monkeypatch)
    run, sheet = table_run(tmp_path)
    s = _saved_session(tab, run.artefact(".ti1"), run, monkeypatch, qtbot)
    rec = json.loads((s / se.IDENTITY).read_text(encoding="utf-8"))
    assert rec["chart_sha256"] == se.sha256_of(run.chart_ti2)
    assert rec["belongs_to"] is None


def test_m2_a_session_of_a_replaced_chart_is_never_offered_and_adoption_is_refused(
        tab, beta, tmp_path, monkeypatch, qtbot):
    """Any route that changes the chart's bytes (Restore Used Chart, a regenerate, an import,
    a reset): the session's recorded checksum no longer matches, so it is named and never
    completed into the new chart."""
    _answer_windows(monkeypatch)
    run, sheet = table_run(tmp_path)
    ti1 = run.artefact(".ti1")
    s = _saved_session(tab, ti1, run, monkeypatch, qtbot)
    killed = _killed_copy(s, "20261117-235959")
    run.measurement_ti3.unlink()                      # (a new chart has no measurement)
    assert se.belongs_elsewhere(run, killed, run.chart_ti2) is None
    assert any(se.offered_for_completion(e) for e in se.earlier_sessions(
        run, chart_ti2=run.chart_ti2))
    # the chart is replaced by one with the same locations (as Restore Used Chart would)
    run.chart_ti2.write_text(run.chart_ti2.read_text(encoding="ascii")
                             + "\nKEYWORD \"A_NEW_LAYOUT\"\n", encoding="ascii")
    [e] = [e for e in se.earlier_sessions(run, chart_ti2=run.chart_ti2)
           if e.stamp == killed.name]
    assert e.state == se.INTERRUPTED and not se.offered_for_completion(e)
    assert e.detail["belongs_elsewhere"] == se.ANOTHER_CHART
    # the job refuses to complete it, whatever asks
    sim = _start_on(tab, ti1, monkeypatch)
    win = tab._table_window
    qtbot.waitUntil(lambda: win._page_id in ("earlier_elsewhere", "earlier"), timeout=5000)
    assert win._page_id == "earlier_elsewhere", win.pages_shown
    assert "Complete it" not in [b.text() for b in win._buttons]
    text = win._text.text()
    assert "another chart" in text and "nothing is deleted" in text
    res = sim.jobs[0].adopt_earlier(killed.name)
    assert not res.ok and res.reason == se.ANOTHER_CHART
    assert W.reason_text(res.reason) != W.reason_text("no_such_id_anywhere")
    # Continue starts from the beginning
    _person(win, sim, qtbot).press("Continue")
    qtbot.waitUntil(lambda: win._page_id != "earlier_elsewhere", timeout=5000)
    assert sim.jobs[0]._earlier_dirs == []


def test_m2_a_session_with_no_record_of_its_chart_is_never_completed(tmp_path):
    """Sessions written before this change (none exist outside the developers' machines: the
    table drive is unreleased) cannot be proved to be of this chart: kept, never completed."""
    from tests.i1io_table.test_window import project
    from tests.i1io_table.test_job_reading import small_sheet
    _proj, run = project(tmp_path, small_sheet())
    sdir = _session(run, identity=False)
    assert se.belongs_elsewhere(run, sdir, run.chart_ti2) == se.CHART_NOT_RECORDED


def test_m2_calibration_reset_and_restore_routes_are_covered_by_the_checksum(tmp_path):
    proj, cal, sheet = cal_chart(tmp_path)
    sdir = _session(cal)
    assert se.belongs_elsewhere(cal, sdir, cal.ti2) is None
    cal.ti2.write_text(cal.ti2.read_text(encoding="ascii") + "\n", encoding="ascii")
    assert se.belongs_elsewhere(cal, sdir, cal.ti2) == se.ANOTHER_CHART


# ---- M-3: a verification's session belongs to its date ---------------------------------------

def test_m3_an_interrupted_verification_session_is_offered_only_to_its_own_date(
        tab, beta, tmp_path, monkeypatch, qtbot):
    """Review 12's probe R12-3, keyed: a session started on date A and cut off is offered only
    when date A is measured again, never to "New verification" or to date B."""
    _answer_windows(monkeypatch)
    proj, run, vc, sheet = verify_chart(tmp_path)
    sim = _start_on(tab, run.verify_chart_ti1, monkeypatch)
    _finish(_person(tab._table_window, sim, qtbot))
    qtbot.waitUntil(lambda: bool(run.verifications()), timeout=5000)
    qtbot.wait(100)
    date_a = run.verifications()[0].id
    [s] = vc.i1io_table_sessions()
    killed = _killed_copy(s, "20261117-235959")
    # as if that START had been made on date A (a re-read of that printed sheet)
    rec = se.read_identity(killed)
    rec["belongs_to"] = run.verification_chart(date_a).i1io_table_session_key
    (killed / se.IDENTITY).write_text(json.dumps(rec), encoding="utf-8")

    def offered(place):
        return [e.stamp for e in se.earlier_sessions(place, chart_ti2=vc.chart_ti2)
                if se.offered_for_completion(e)]
    assert offered(run.verification_chart(date_a)) == [killed.name]
    assert offered(run.verification_chart(None)) == []           # New verification
    assert offered(run.verification_chart("20261118-090000")) == []
    [e] = [e for e in se.earlier_sessions(run.verification_chart(None), chart_ti2=vc.chart_ti2)
           if e.stamp == killed.name]
    assert e.detail["belongs_elsewhere"] == se.ANOTHER_VERIFICATION


def test_m3_a_table_start_on_a_verification_records_its_date(
        tab, beta, tmp_path, monkeypatch, qtbot):
    _answer_windows(monkeypatch)
    proj, run, vc, sheet = verify_chart(tmp_path)
    _target(tab, run, "")
    sim = _start_on(tab, run.verify_chart_ti1, monkeypatch)
    assert tab._table_window._run.i1io_table_session_key == "verification:new"
    qtbot.waitUntil(lambda: bool(sim.jobs), timeout=5000)
    sdir = sim.jobs[0].run.i1io_table_session_dir(sim.jobs[0].stamp)
    assert se.read_identity(sdir)["belongs_to"] == "verification:new"


# ---- S-1 and S-4 (F9): a resumed table verification --------------------------------------------

def _resume_date(tab, run, vid, monkeypatch):
    dated = run.verification(vid).measurement_ti3
    _target(tab, run, vid)
    monkeypatch.setattr(tab, "_verification_to_stage", lambda: dated)
    monkeypatch.setattr(tab, "_read_builds_on_existing", lambda: True)
    return dated


def _partial_date(tab, beta_, tmp_path, monkeypatch, qtbot):
    """A verification of date A that holds the first row only (a partial measurement)."""
    _answer_windows(monkeypatch)
    proj, run, vc, sheet = verify_chart(tmp_path)
    sim = _start_on(tab, run.verify_chart_ti1, monkeypatch,
                    sim=WindowSim(faults={"read_loc": {"B2": "dies"}}))
    win = tab._table_window
    p = _person(win, sim, qtbot)
    p.script["row_failed"] = "Skip it"
    p.drive_until("end_of_session")
    p.press("Save and stop")
    p.drive_until(("home_offered", "done"))
    if p.page() == "home_offered":
        p.press("Leave it there")
    p.press("Close")
    qtbot.waitUntil(lambda: bool(run.verifications()), timeout=5000)
    qtbot.wait(100)
    [a] = run.verifications()
    assert classify(a.measurement_ti3, vc.chart_ti2).state is Ti3State.PARTIAL
    return proj, run, vc, sheet


def test_s1_a_resumed_table_verification_keeps_the_dates_file_in_the_dates_old(
        tab, beta, tmp_path, monkeypatch, qtbot):
    proj, run, vc, sheet = _partial_date(tab, beta, tmp_path, monkeypatch, qtbot)
    [a] = run.verifications()
    before = a.measurement_ti3.read_bytes()
    dated = _resume_date(tab, run, a.id, monkeypatch)
    sim = _start_on(tab, run.verify_chart_ti1, monkeypatch)
    win = tab._table_window
    assert win._run.measurement_old_dir == a.dir / "old"
    assert win._run.i1io_table_session_key == f"verification:{a.id}"
    # the job saves the staged copy over itself (a re-read of the whole sheet)
    p = _person(win, sim, qtbot)
    p.drive_until("end_of_session")
    p.press("Save and stop")
    p.drive_until(("home_offered", "done", "refused", "error"))
    assert p.page() in ("home_offered", "done"), (p.page(), win._text.text()[:300])
    if p.page() == "home_offered":
        p.press("Leave it there")
    p.press("Close")
    qtbot.waitUntil(lambda: tab._table_window is None, timeout=5000)
    qtbot.wait(200)
    in_date = sorted((a.dir / "old").glob("*/*.ti3"))
    assert [f.read_bytes() for f in in_date] == [before], in_date
    assert not list((run.verifications_dir / "old").glob("*/*.ti3"))


def test_s4_f9_a_resumed_table_verification_that_read_nothing_leaves_no_copy_beside_the_chart(
        tab, beta, tmp_path, monkeypatch, qtbot):
    proj, run, vc, sheet = _partial_date(tab, beta, tmp_path, monkeypatch, qtbot)
    [a] = run.verifications()
    before = a.measurement_ti3.read_bytes()
    _resume_date(tab, run, a.id, monkeypatch)
    sim = _start_on(tab, run.verify_chart_ti1, monkeypatch)
    assert vc.measurement_ti3.is_file()                  # staged beside the chart
    win = tab._table_window
    win._on_close_pressed() if win._page_id != "consent" else None
    qtbot.waitUntil(lambda: tab._table_window is None or win.job is not None, timeout=5000)
    if tab._table_window is not None:
        win._finish_not_started()
    qtbot.waitUntil(lambda: tab._table_window is None, timeout=5000)
    qtbot.wait(100)
    assert not vc.measurement_ti3.exists(), "the unused staged copy stays beside the chart"
    assert a.measurement_ti3.read_bytes() == before


# ---- S-4 (F7): the legend chip's keep-out in the paint itself ---------------------------------

def test_s4_f7_the_legend_is_painted_outside_the_keep_out(qtbot, tmp_path):
    """The real paint (not only `_legend_clear_place`): with a keep-out over the place the chip
    takes on its own, the painted chip moves off it or is not drawn."""
    from PIL import Image
    from PyQt6.QtCore import QRect, QRectF
    from PyQt6.QtGui import QColor
    from PyQt6.QtWidgets import QApplication
    from ui.tiff_preview import TiffPreview
    pv = TiffPreview()
    qtbot.addWidget(pv)
    pv.resize(700, 700)
    tif = tmp_path / "sheet.tif"
    Image.new("RGB", (600, 600), (245, 245, 245)).save(tif)
    pv.load_tiff([tif])
    items = [(QRect(60 + 90 * c, 60 + 70 * r, 80, 60), QColor("#3050ff"), QColor("#20c060"),
              False) for r in range(6) for c in range(6)]
    pv.set_patch_overlay(0, items, replace_page=True)
    pv.show()
    qtbot.waitExposed(pv)
    QApplication.processEvents()
    qtbot.waitUntil(lambda: pv._legend_rect is not None, timeout=3000)
    free = QRect(pv._legend_rect)
    s, ox, oy = pv._paint_geom
    sy = pv._paint_scale_y or s
    ko = QRectF((free.x() - ox) / s, (free.y() - oy) / sy, free.width() / s,
                free.height() / sy)
    pv._legend_keepout = {pv._current: [ko]}
    pv.update()
    qtbot.wait(100)
    QApplication.processEvents()
    s, ox, oy = pv._paint_geom
    sy = pv._paint_scale_y or s
    kc = QRectF(ox + ko.x() * s, oy + ko.y() * sy, ko.width() * s, ko.height() * sy)
    got = pv._legend_rect
    assert got is None or not QRectF(got).intersects(kc), (got, kc)


