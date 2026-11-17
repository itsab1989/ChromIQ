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


