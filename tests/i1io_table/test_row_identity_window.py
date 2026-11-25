"""The row identity check in front of a person: the question's page and its two answers, the failed
row's reason, the app log, and the Measure tab's preview (a dropped row's painted halves go)."""
from __future__ import annotations

import pytest

from tests.i1io_table import bed_sim as B
from tests.i1io_table.test_window import open_window, settings  # noqa: F401  (a fixture)
from tests.i1io_table.test_window_in_the_measure_tab import beta, start, tab  # noqa: F401
from tests.i1io_table.window_person import WindowPerson
from ui import i1io_table_window as W
from workflow import measurement_messages as M
from workflow.i1io.table import identity as idn

SPOT = ["-v", "-c", "1", "-p"]
STRIP = ["-v", "-c", "1"]


def _charts(tmp_path, pages=1):
    ch = B.build_chart(tmp_path, count=72 if pages == 1 else 600)
    other = B.build_chart(tmp_path, name="Other", colours=B.patch_set(72, seed=99), seed=9)
    return ch, other


def _window(qtbot, monkeypatch, tmp_path, settings, ch, bed, args=STRIP, **kw):  # noqa: F811
    sim = B.bed_window_sim(ch, bed)
    stem = str(ch.run.chart_ti2)[:-4]
    return open_window(qtbot, monkeypatch, tmp_path, settings, sheet=ch.sheet, sim=sim,
                       run=ch.run, args=args + [stem], asking=False, **kw)


def _lines(monkeypatch):
    got = []
    import core.app_log as al
    real = al.line
    monkeypatch.setattr(al, "line", lambda kind_, **k: (got.append((kind_, k)), real(kind_, **k))[1])
    return got


@pytest.mark.parametrize("guided", (None, False), ids=("pop-ups", "guidance off"))
def test_the_question_asks_in_both_modes_and_right_reads_on(qtbot, monkeypatch, tmp_path,
                                                           settings, guided):  # noqa: F811
    ch, other = _charts(tmp_path)
    lines = _lines(monkeypatch)
    win, sim, run, p, saved, finished = _window(qtbot, monkeypatch, tmp_path, settings, ch,
                                                B.Bed(other.laid()), guided=guided)
    assert p.drive_until("row_identity") == "row_identity"
    # ONE answer, and one way to end: the footer's own button, where it always is
    assert p.labels() == ["It is the right sheet, and it was not moved"]
    from PyQt6.QtWidgets import QPushButton
    texts = [b.text() for b in win.popup().findChildren(QPushButton) if b.isVisible()]
    assert texts.count("End measurement") == 1 and "End the measurement" not in texts
    assert "press “End measurement” below" in win._text.text()
    # and it is not the filled button: it keeps values that looked wrong
    assert [b.objectName() for b in win._buttons] == [""]
    title, body = M.M_I1IO_DRIVE_OTHER_SHEET.render(other="")
    assert win._title.text() == title and body.split("\n")[0] in win._text.text()
    n = len(sim.sim.received)
    assert len(sim.sim.received) == n
    p.press("It is the right sheet, and it was not moved")
    # (with the guidance off a chart read whole is saved without a question)
    if p.drive_until(("end_of_session", "done")) == "end_of_session":
        p.press("Save and stop")
    assert win.pages_shown.count("row_identity") == 1
    assert saved
    judged = [k for w, k in lines if w == "table row identity"]
    assert len(judged) == 3 and {k["verdict"] for k in judged} == {"ask"}
    for label in ("Bring the arm home, my hands are away", "Close"):
        if label in p.labels():
            p.press(label)
    total = [k for w, k in lines if w == "table row identity total"]
    assert [(k["rows"], k["asked"], k["confirmed_by_person"], k["not_judged"]) for k in total] \
        == [(3, 1, 2, 0)]
    assert not [k for w, k in lines if w == "table row dropped"]


def test_end_the_measurement_goes_to_the_ending_and_keeps_only_what_was_read_right(
        qtbot, monkeypatch, tmp_path, settings):  # noqa: F811
    ch, other = _charts(tmp_path)
    lines = _lines(monkeypatch)
    bed = B.Bed(ch.laid())
    win, sim, run, p, saved, finished = _window(qtbot, monkeypatch, tmp_path, settings, ch, bed)
    sim.bed = bed
    real = W.TableMeasureWindow._live_event
    seen = []

    def live(self, ev):
        seen.append(dict(ev))
        # after the first row the person lays another sheet
        if ev.get("event") == "row_end" and ev.get("status") == "read":
            bed.laid = other.laid()
        return real(self, ev)
    monkeypatch.setattr(W.TableMeasureWindow, "_live_event", live)
    assert p.drive_until("row_identity") == "row_identity"
    win._on_end_pressed()                                  # the footer's button
    p.idle()
    assert p.page() == "end_of_session", win.pages_shown[-4:]
    p.press("Save and stop")
    assert saved
    from workflow.measurement_state import unread_locations
    unread = unread_locations(run.measurement_ti3, run.chart_ti2)
    assert len(unread) == 48
    dropped = [k for w, k in lines if w == "table row dropped"]
    assert [k["why"] for k in dropped] == [idn.REASON_ENDED]
    assert win.state_text()


def test_the_failed_rows_page_says_the_row_lies_beside_its_place(qtbot, monkeypatch, tmp_path,
                                                                 settings):  # noqa: F811
    ch, _other = _charts(tmp_path)
    win, sim, run, p, saved, finished = _window(qtbot, monkeypatch, tmp_path, settings, ch,
                                                B.Bed(ch.laid(), shift_mm=(11.0, 0.0)))
    assert p.drive_until("row_failed_strip") == "row_failed_strip"
    assert "beside its place" in win._text.text()
    assert p.labels()[0] == "Read it again as a strip"


def test_the_texts():
    one = W.row_identity_page({"row": 3, "page": 1, "pages": 1, "other": "row 4"})
    assert "this chart; they look like row 4." in one[1]
    many = W.row_identity_page({"row": 3, "page": 2, "pages": 4, "other": "page 1"})
    assert "look like page 2 of this chart; they look like page 1." in many[1]
    plain = W.row_identity_page({"row": 3, "page": 2, "pages": 4, "other": None})
    assert "look like page 2 of this chart. ChromIQ" in plain[1]
    for title, body in (one, many, plain):
        # (pieces come with charts of several pieces; a page of today is a sheet)
        assert "piece" not in title + body and title == "Is the right sheet on the table?"
    assert W.choice_label("row_identity", "right") == "It is the right sheet, and it was not moved"
    for rid in (*idn.REASONS, "ended_at_the_row_identity_question"):
        assert W.reason_text(rid) != W.reason_text("no_such_reason_at_all"), rid
    strip = M.strip_fallback_text(idn.REASON_STRIP, 3)
    # what happens, and no more: the rest is offered after a SECOND row, not a second try
    # (R3: the rest is not offered for this reason)
    assert "patch by patch" not in strip and "happens again" not in strip
    spot = M.strip_fallback_text(idn.REASON_SPOT, 3)
    assert "read the rest of the page patch by patch" not in spot and "aim at its marks again" in spot
    assert W.WITHDRAW["row_identity"] == "stop"
    assert W.POPUP_SOUND["row_identity"] == "INSTRUMENT_ERROR"
    rows = [{"page": 1, "strip": "A"}, {"page": 1, "strip": "C"}, {"page": 2, "strip": "B"}]
    assert W.strips_named(rows[:2], 1) == "A, C"
    assert W.strips_named(rows, 2) == "page 1: A, C; page 2: B"
    assert W.rows_not_judged_text([], 1) == ""


def test_a_chart_of_several_pages_asks_about_the_page(qtbot, monkeypatch, tmp_path,
                                                      settings):  # noqa: F811
    """Page 2 laid where page 1 belongs: the question names the pages, has one answer and no
    second way to end."""
    ch = B.build_chart(tmp_path, count=600)
    assert len(ch.sheet["pages"]) == 2
    win, sim, run, p, saved, finished = _window(qtbot, monkeypatch, tmp_path, settings, ch,
                                                B.Bed(ch.laid(1)))
    assert p.drive_until("row_identity") == "row_identity"
    assert p.labels() == ["It is the right sheet, and it was not moved"]
    text = win._text.text()
    assert "do not look like page 1 of this chart; they look like page 2." in text
    assert win._title.text() == "Is the right sheet on the table?" and "piece" not in text
    from PyQt6.QtWidgets import QPushButton
    texts = [b.text() for b in win.popup().findChildren(QPushButton) if b.isVisible()]
    assert texts.count("End measurement") == 1 and not any("piece" in t for t in texts)
    win._on_end_pressed()
    p.idle()


def test_a_stop_at_the_question_keeps_the_answer_and_then_stops(qtbot, monkeypatch, tmp_path,
                                                               settings):  # noqa: F811
    """Stop pressed while the question is open, then "It is the right sheet, and it was not moved": the row is kept, as
    the page says, and the stop's own page follows; nothing moves in between."""
    ch, other = _charts(tmp_path)
    win, sim, run, p, saved, finished = _window(qtbot, monkeypatch, tmp_path, settings, ch,
                                                B.Bed(other.laid()))
    assert p.drive_until("row_identity") == "row_identity"
    sent = len(sim.sim.received)
    win._on_stop()                                         # the tab's Stop
    p.idle()
    assert p.page() == "row_identity"
    p.press("It is the right sheet, and it was not moved")
    p.idle()
    assert len(sim.sim.received) == sent
    assert p.page() == "stopped_by_you", win.pages_shown[-4:]
    import json
    from workflow.i1io.table import measurement as ms
    folder = run.i1io_table_session_dir(win._stamp)
    recs = [json.loads(f.read_text(encoding="utf-8"))
            for f in folder.rglob("*" + ms.ROW_RECORD_SUFFIX)]
    assert [(r["status"], len(r["accepted"])) for r in recs] == [("read", 24)]


def test_the_ending_names_the_rows_nobody_could_judge(qtbot, monkeypatch, tmp_path,
                                                      settings):  # noqa: F811
    """Row A is one colour and more (not judged) and read on the wrong sheet, row B is asked
    about; End: A stays, and the ending and the app log say so, by its letter."""
    ch = B.build_chart(tmp_path, count=72, randomize=False,
                       colours=[(100.0, 100.0, 100.0)] * 24 + B.patch_set(48))
    other = B.build_chart(tmp_path, name="Other", colours=B.patch_set(72, seed=99), seed=9)
    lines = _lines(monkeypatch)
    win, sim, run, p, saved, finished = _window(qtbot, monkeypatch, tmp_path, settings, ch,
                                                B.Bed(other.laid()))
    assert p.drive_until("row_identity") == "row_identity"
    win._on_end_pressed()
    p.idle()
    assert p.page() == "end_of_session"
    text = win._text.text()
    assert M.M_I1IO_DRIVE_ROWS_NOT_JUDGED.render(strips="A")[1] in text
    assert "could be from the wrong sheet" in text and "Nothing is deleted without you" in text
    logged = [k for w, k in lines if w == "table rows not judged before the question"]
    assert len(logged) == 1 and logged[0]["rows"] == 1
    assert logged[0]["what"].startswith("page 1 strip A: 24 read, ")
    p.press("Save and stop")
    from workflow.measurement_state import unread_locations
    unread = set(unread_locations(run.measurement_ti3, run.chart_ti2))
    assert len(unread) == 48 and not {f"A{k}" for k in range(1, 25)} & unread


def test_an_ordinary_ending_names_nothing(qtbot, monkeypatch, tmp_path, settings):  # noqa: F811
    ch = B.build_chart(tmp_path, count=48, randomize=False,
                       colours=[(100.0, 100.0, 100.0)] * 24 + B.patch_set(24))
    lines = _lines(monkeypatch)
    win, sim, run, p, saved, finished = _window(qtbot, monkeypatch, tmp_path, settings, ch,
                                                B.Bed(ch.laid()))
    assert p.drive_until("end_of_session") == "end_of_session"
    assert "could not judge" not in win._text.text()
    assert not [k for w, k in lines if w == "table rows not judged before the question"]


def test_the_window_says_a_calibration_chart_is_one(qtbot, monkeypatch, tmp_path,
                                                    settings):  # noqa: F811
    """A calibration chart has no expected colours: the place it is measured for says so."""
    import core.file_manager as fm
    ch, _other = _charts(tmp_path)
    win, sim, run, p, saved, finished = _window(qtbot, monkeypatch, tmp_path, settings, ch,
                                                B.Bed(ch.laid()))
    assert len(win.job.expected_lab) == 72
    monkeypatch.setattr(fm, "Calibration", type(ch.run))       # this run is a calibration now
    win._build_job()
    assert win.job.expected_lab == {} and win.job.expected_why == "a calibration chart"


def test_the_windows_job_gets_the_charts_expected_colours(qtbot, monkeypatch, tmp_path,
                                                          settings):  # noqa: F811
    ch, _other = _charts(tmp_path)
    win, sim, run, p, saved, finished = _window(qtbot, monkeypatch, tmp_path, settings, ch,
                                                B.Bed(ch.laid()))
    p.drive_until("ready_to_open")
    assert len(win.job.expected_lab) == 72 and win.job.expected_why == ""


def test_the_preview_takes_a_dropped_rows_halves_off(tab, beta, tmp_path, monkeypatch,  # noqa: F811
                                                     qtbot):
    ch = B.with_preview(B.build_chart(tmp_path, count=72))
    bed = B.Bed(ch.laid(), shift_mm=(11.0, 0.0))
    sim = B.bed_window_sim(ch, bed)
    monkeypatch.setattr(tab, "_current_mode", lambda: "manual")
    import ui.i1io_table_window as win_mod
    monkeypatch.setattr(win_mod, "JOB_FACTORY", sim.factory)
    start(tab, ch.run, monkeypatch, sim)
    # patch by patch: every patch is painted as it is read, and the row is then refused
    monkeypatch.setattr(tab._table_window, "_chart_args", SPOT + [str(ch.run.chart_ti2)[:-4]])
    p = WindowPerson(tab._table_window, sim, lambda c: qtbot.waitUntil(c, timeout=20000))
    painted = []
    real = tab._on_patch_measured
    monkeypatch.setattr(tab, "_on_patch_measured",
                        lambda ev: (real(ev), painted.append(len(
                            tab._preview._patch_overlay.get(0, [])))))
    page = p.drive_until(("row_failed", "row_failed_strip"))
    assert page == "row_failed" and painted and max(painted) == 24
    assert tab._preview._patch_overlay.get(0, []) == []
    assert 0 in tab._table_rows_failed and 0 not in tab._table_rows_done
    assert not set(tab._progress_locs) & {f"A{i}" for i in range(1, 25)}
    assert "beside its place" in tab._log.toPlainText()


def test_rows_that_cannot_be_judged_are_said_with_their_reason_and_counted(
        qtbot, monkeypatch, tmp_path, settings):  # noqa: F811
    """The app log: one line per row with the reason, and one line per sitting with the count."""
    ch = B.build_chart(tmp_path, count=72, colours=B.patch_set(40) + [(100.0, 100.0, 100.0)] * 32,
                       randomize=False)
    lines = _lines(monkeypatch)
    win, sim, run, p, saved, finished = _window(qtbot, monkeypatch, tmp_path, settings, ch,
                                                B.Bed(ch.laid()))
    p.drive_until("end_of_session")
    p.press("Save and stop")
    for label in ("Bring the arm home, my hands are away", "Close"):
        if label in p.labels():
            p.press(label)
    rows = [k for w, k in lines if w == "table row identity"]
    assert [k["judged"] for k in rows] == ["yes", "yes", "no"]
    assert "of its 24 patches are one colour" in rows[2]["why"] or "spreads by" in rows[2]["why"]
    total = [k for w, k in lines if w == "table row identity total"]
    assert len(total) == 1
    assert (total[0]["rows"], total[0]["ok"], total[0]["not_judged"]) == (3, 2, 1)
    assert total[0]["why"] == "1 x " + rows[2]["why"]
    import json
    doc = json.loads((run.i1io_table_session_dir(win._stamp) / "session_summary.json").read_text(
        encoding="utf-8"))
    assert doc["row_identity"] == {"ok": 2, "not judged: " + rows[2]["why"]: 1}
