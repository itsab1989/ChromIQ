"""The verification chart's "All Strips Read" window carries the same
"Summary:" as a profiling chart's (Knut, #182 6154440320, 4.3.5 beta 3).

    *"This All Strips Read window is missing the same Summary that profiling
    chart gets when reading is finished. Should not the worst measurement
    errors be summarised too, so that I can better decide if I want to
    re-read patches or finish?"*

It showed the reading times only (``_measurement_summary``), as plain text;
the profiling window shows ``_completion_summary`` (reading times and the
suspected misreads, M-MEASURED-SUSPECTS) as the bullet list under "Summary:".
Measured on screen with his run 2 (beta 4 report, M4).
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtWidgets import QApplication, QDialog, QLabel  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def test_the_verification_window_shows_the_summary(qapp, tmp_path,
                                                   monkeypatch):
    from core.argyll_runner import ArgyllRunner
    from core.settings import AppSettings
    from ui.tabs.tab_measure import TabMeasure
    s = AppSettings()
    tab = TabMeasure(ArgyllRunner(s), s)
    tab._verify_run = True
    tab._guided_refinement_active = False
    tab._ti1_path = Path(tmp_path) / "verifications" / "P-verify.ti2"
    monkeypatch.setattr(tab, "_measurement_summary",
                        lambda: "Total measuring time: 00:01:00")
    monkeypatch.setattr(tab, "_misread_summary",
                        lambda: "Neighbour check: no suspected misreads.")
    monkeypatch.setattr(tab, "_play_measurement_finished_once", lambda: None)
    seen = {}

    def grab(dlg):
        seen["title"] = dlg.windowTitle()
        seen["labels"] = [lb.text() for lb in dlg.findChildren(QLabel)]
        return int(QDialog.DialogCode.Rejected.value)
    monkeypatch.setattr(QDialog, "exec", grab)
    try:
        tab._show_all_stripes_done()
    finally:
        tab.deleteLater()
    assert "Verification" in seen["title"]
    text = "\n".join(seen["labels"])
    assert "Summary:" in text
    assert "<li>Total measuring time: 00:01:00</li>" in text
    assert "<li>Neighbour check: no suspected misreads.</li>" in text
