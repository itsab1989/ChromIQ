"""4.3.57, items 20, 22 and 23: what the table answered reaches the logs (the app log is the one
log), and the table's own log is one press away.

* 20: the repair at START logged "(found None)" for where the arm stood: the reading right
  before the homing is logged now.
* 22: the done page offers "Show the table's log"; the opening's state and mode answers (a0, f4)
  are in the app log's result line of the opening.
* 23: a strip row's speed answer (a3: A, T, speed) and its verdict are in the session log and
  the app log, every row.
"""
from __future__ import annotations

import logging

from core.i18n import tr
from tests.i1io_table.test_roundB_strip import _job, _ready
from tests.i1io_table.test_window import open_window, settings  # noqa: F401
from workflow.i1io.table import job as J


def test_a_strip_rows_speed_answer_and_verdict_are_logged(tmp_path):
    job, sim, helper, run, p = _job(tmp_path)
    _ready(job, p)
    seen = []
    job.on_progress = lambda ev: seen.append(ev) if ev.get("event") == "speed_answer" else None
    r = p.drive(job.read_row())
    assert r.ok and r.detail["row_kind"] == "strip"
    lines = [ln for ln in job.diag.lines if "a3 speed answer" in ln]
    assert lines and "as sent" in lines[0] and "mm/s" in lines[0]
    assert seen and seen[0]["a3"] and seen[0]["sent"][2] == seen[0]["a3"][2]


def test_the_speed_answer_reaches_the_app_log(caplog):
    from types import SimpleNamespace
    import ui.i1io_table_window as W
    win = SimpleNamespace(job=SimpleNamespace(page=0))
    with caplog.at_level(logging.INFO):
        W._applog_table_row(win, {"event": "speed_answer", "row": 2, "a3": [840, 1690, 168],
                                  "sent": [840, 1690, 168],
                                  "note": "a3 speed answer: ... (sent 840, 1690, 168): as sent"})
    text = "\n".join(r.getMessage() for r in caplog.records)
    assert "table speed answer" in text and "as sent" in text and "row=2" in text


def test_the_done_page_offers_the_tables_log(qtbot, monkeypatch, tmp_path, settings):  # noqa: F811
    opened = []
    from PyQt6.QtGui import QDesktopServices
    monkeypatch.setattr(QDesktopServices, "openUrl", lambda url: opened.append(url) or True)
    win, sim, run, p, saved, finished = open_window(qtbot, monkeypatch, tmp_path, settings,
                                                    asking=False)
    p.drive_until("end_of_session")
    p.press("Save and stop")
    p.drive_until("done")
    assert tr("Show the table's log") in p.labels()
    p.press("Show the table's log")
    assert opened and opened[0].toLocalFile().endswith(
        str(run.i1io_table_log(win._stamp).name))
    assert p.page() == "done"                      # the page stays


def test_the_opening_answers_reach_the_app_log(caplog):
    from types import SimpleNamespace
    import ui.i1io_table_window as W
    tbl = SimpleNamespace(a0_answer="130000", f4_answer="00", mode_left_on=False)
    job = SimpleNamespace(_table=tbl, page=0, alignment=None, ask_after_each_step=True,
                          auto_answers=[], countdowns=[])
    win = SimpleNamespace(job=job)
    res = SimpleNamespace(step="open", kind="ok", reason="", confirm=None, way_back="none",
                          state=None, detail={})
    with caplog.at_level(logging.INFO):
        W._applog_table_result(win, res)
    text = "\n".join(r.getMessage() for r in caplog.records)
    assert "a0=130000" in text and "f4=00" in text


def test_the_repair_line_names_where_the_arm_stood():
    from tests.i1io_table import job_harness as H
    from tests.i1io_table.test_4355_table_without_i1profiler import _leave_it_there
    sim = _leave_it_there()
    job2, sim2, _t = H.make_job(sim=sim)
    p2 = H.Person(job2, sim2)
    assert p2.drive(job2.open()).ok
    assert p2.drive(job2.repair_at_start()).ok
    line = [ln for ln in job2.diag.lines if "the aiming mode is ended" in ln][-1]
    assert "found None" not in line
    assert f"found {tuple(job2.homed_from)}" in line or f"found {job2.homed_from}" in line


def test_the_repair_line_never_names_an_earlier_homings_place():
    """Fix round (review N1): ``homed_from`` is written by every ending homing; the repair's
    line must name this homing's place or *found*, never one left by an earlier homing.
    MUTATION: drop the reset before ``_end_of_job`` in ``_repair_homing`` and the earlier
    place is still there when this homing starts."""
    from tests.i1io_table import job_harness as H
    from tests.i1io_table.test_4355_table_without_i1profiler import _leave_it_there
    sim = _leave_it_there()
    job2, sim2, _t = H.make_job(sim=sim)
    p2 = H.Person(job2, sim2)
    assert p2.drive(job2.open()).ok
    earlier = (4321, 1234)
    job2.homed_from = earlier                     # left by an earlier ending homing
    seen = []
    real = job2._end_of_job

    def spy(stage=None, **kw):
        seen.append(job2.homed_from)
        return real(stage, **kw)
    job2._end_of_job = spy
    assert p2.drive(job2.repair_at_start()).ok
    assert seen == [None]
    line = [ln for ln in job2.diag.lines if "the aiming mode is ended" in ln][-1]
    assert str(earlier) not in line
