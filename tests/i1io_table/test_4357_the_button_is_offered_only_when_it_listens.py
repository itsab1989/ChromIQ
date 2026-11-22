"""4.3.57 (item 32): the instrument's button is offered for a mark only once the helper said it
listens for that mark.

The table owner's 22 Nov evening run: after a refused aim, at the second try, the button did
not answer and he pressed Aimed on the screen. ``reader.PressWaiter.arm`` returned True as soon
as the command was WRITTEN; nothing checked that the helper answered ``press_armed`` (a new wait
that died, hung, or had not yet opened the instrument looked exactly like a working one). Now
``job._press_arm`` waits up to ``BUTTON_ARMED_WAIT_S`` for that answer; without it the page does
not offer the button and says plainly to press Aimed (M-I1IO-DRIVE-AIM-BUTTON-NOT-NOW). Nothing
is sent to the table either way.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

from core.i18n import tr
from tests.i1io_table.test_job_reading import read_page
from tests.i1io_table.test_roundB_button import ButtonPerson, _job, _to_aims
from tests.i1io_table.test_window import open_window, settings  # noqa: F401
from tests.i1io_table.window_sim import WindowSim
from workflow import measurement_messages as M
from workflow.i1io.table import job as J
from workflow.i1io.table import reader as rd


@pytest.fixture
def quick(monkeypatch):
    monkeypatch.setattr(J, "BUTTON_ARMED_WAIT_S", 0.05)


def test_a_deaf_button_wait_is_not_offered_and_the_panel_aims(tmp_path, quick):
    job, sim, helper, _run = _job(tmp_path, faults={"press": "deaf"})
    p = ButtonPerson(job, sim, helper)          # would press the button if it were offered
    _to_aims(job, p)
    r = p.drive(job.align())
    assert r.ok, r.reason
    aims = [a for a in p.asked if a[1] == J.Confirm.AIMED]
    assert len(aims) == 3 and p.pressed == 0
    for a in aims:
        assert a[2]["button"] is False and a[2]["button_token"] is None
        assert a[2]["button_unavailable"] == J.BUTTON_NOT_LISTENING
    log = job.diag.log_path.read_text(encoding="utf-8")
    assert log.count("did not answer that it listens for mark") == 3
    assert all(x.ok for x in read_page(job, p))
    job.close()


def test_a_listening_button_wait_is_offered_as_before(tmp_path, quick):
    job, sim, helper, _run = _job(tmp_path)
    p = ButtonPerson(job, sim, helper)
    _to_aims(job, p)
    assert p.drive(job.align()).ok
    assert p.pressed == 3 and job.button_unavailable is None
    job.close()


def test_the_page_says_to_press_aimed_when_the_button_does_not_listen(
        qtbot, monkeypatch, tmp_path, settings, quick):  # noqa: F811
    sim = WindowSim(press=True, faults={"press": "deaf"})
    win, sim, run, person, *_ = open_window(qtbot, monkeypatch, tmp_path, settings, sim=sim,
                                            asking=False)
    person.drive_until("aimed")
    text = win._text.text()
    assert tr(M.M_I1IO_DRIVE_AIM_BUTTON_NOT_NOW.body) in text
    assert "button on the i1Pro 2 itself" not in text
    assert win._aim_token is None


# ---- the real reader against a fake helper executable ---------------------------------------
FAKE = r'''
import json, sys
def say(ev):
    sys.stdout.write(json.dumps(ev) + "\n"); sys.stdout.flush()
say({"event": "press_wait_start", "build": "fake +i1io-press-wait"})
say({"event": "press_wait_ready", "model": "X-Rite i1 Pro 2"})
for line in sys.stdin:
    cmd = json.loads(line)
    if cmd.get("cmd") == "press_arm" and LISTENS:
        say({"event": "press_armed", "id": cmd["id"]})
    elif cmd.get("cmd") == "press_quit":
        break
'''


@pytest.mark.parametrize("listens", [True, False])
def test_the_real_reader_waits_for_the_helpers_own_answer(tmp_path, listens):
    exe = tmp_path / "chromiq-chartread"
    exe.write_text(f"#!{sys.executable}\nLISTENS = {listens}\n" + FAKE, encoding="utf-8")
    exe.chmod(0o755)
    w = rd.PressWaiter(exe, tmp_path / "button", lambda *a: None)
    try:
        assert w.arm("p1-m1-1") is True               # the write alone always "works"
        assert w.wait_armed("p1-m1-1", 2.0) is listens
        assert w.wait_armed("another", 0.1) is False  # an answer for another mark is not it
    finally:
        w.close()


def test_the_wait_is_bounded_by_its_measured_reason():
    # the helper's own start, measured 1.02 s on the owner's machine: four times that
    assert J.BUTTON_ARMED_WAIT_S == 4.0
