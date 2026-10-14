"""The two Calibration Complete windows of a strip read carry the same to-do
points (Knut, #182 6154440320, 4.3.5 beta 3).

    *"When starting a measurement from scratch and then calibrating I
    remember the calibration finished message was smaller and did not have
    all the information with the steps to follow, with the list of
    shortcuts. Verify that the same todo points are on both calibration
    completed messages."*

Measured on screen with his run 2 (beta 4 report, M3): both windows already
hold the instrument's own steps and the full key list. They differ in form:
"Manual Re-measurement" (Refine / resume) numbers three steps, "How to
Measure" (a fresh read) puts the steps in a paragraph and ended on "These
instructions are always visible in the output log below.", which the other
one lacked. Beta 4: both end on that line now (no new text); the fresh
window's numbered steps are M-CAL-DONE-STEPS, built behind the message and
hidden until it is approved.
"""
from __future__ import annotations

import dataclasses
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtWidgets import QApplication, QFrame, QLabel  # noqa: E402

from workflow import measurement_messages as M  # noqa: E402

FOOT = "These instructions are always visible in the output log below."


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _window(qapp, tmp_path, monkeypatch, *, resume: bool):
    from core.argyll_runner import ArgyllRunner
    from core.settings import AppSettings
    from ui.tabs.tab_measure import TabMeasure
    s = AppSettings()
    tab = TabMeasure(ArgyllRunner(s), s)
    tab._spot_session = False
    tab._guided_refinement_active = False
    tab._strip_list = []
    tab._resume_active = resume
    tab._detected_instrument = "X-Rite i1 Pro 2"
    seen = {}

    def grab(dlg):
        seen["title"] = dlg.windowTitle()
        seen["labels"] = [lb.text() for lb in dlg.findChildren(QLabel)]
        seen["frames"] = {f.objectName() for f in dlg.findChildren(QFrame)}
        return 0
    monkeypatch.setattr(tab, "_exec_measurement_window", grab)
    tab._on_calibration_done()
    tab.deleteLater()
    return seen


def test_both_windows_end_on_the_same_line(qapp, tmp_path, monkeypatch):
    fresh = _window(qapp, tmp_path, monkeypatch, resume=False)
    again = _window(qapp, tmp_path, monkeypatch, resume=True)
    assert "How to Measure" in fresh["title"]
    assert "Manual Re-measurement" in again["title"]
    for w in (fresh, again):
        assert "calibration_key_list" in w["frames"]
        assert FOOT in w["labels"]


def test_until_approved_the_fresh_window_is_as_it_was(qapp, tmp_path,
                                                     monkeypatch):
    assert not M.M_CAL_DONE_STEPS.approved
    fresh = _window(qapp, tmp_path, monkeypatch, resume=False)
    assert "calibration_steps" not in fresh["frames"]
    assert any("Then proceed strip by strip" in t for t in fresh["labels"])


def test_once_approved_both_windows_number_three_steps(qapp, tmp_path,
                                                       monkeypatch):
    monkeypatch.setattr(M, "M_CAL_DONE_STEPS", dataclasses.replace(
        M.M_CAL_DONE_STEPS, approved=True))
    fresh = _window(qapp, tmp_path, monkeypatch, resume=False)
    again = _window(qapp, tmp_path, monkeypatch, resume=True)
    for w in (fresh, again):
        assert "calibration_steps" in w["frames"]
        assert [t for t in w["labels"] if t in ("1.", "2.", "3.")] == \
            ["1.", "2.", "3."]
    assert M._CAL_DONE_STEP_WHICH in fresh["labels"]
    assert M._CAL_DONE_STEP_FINISH in fresh["labels"]
    assert not any("Then proceed strip by strip" in t for t in fresh["labels"])
