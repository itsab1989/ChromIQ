"""A question closed without an answer takes the safe way (review W-1).

"Stuck Print Jobs Detected" printed and "Scan doesn't match the chart" built
when their box was closed with no button clicked (``reject()`` from code, the
window torn down): the code asked "was Cancel/Stop clicked?" and treated
anything else as "go ahead". Only the answers that say print / build now do.
A user's Escape key was always safe (it presses the box's own Cancel/Stop);
this closes the other ways a box can end.
"""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402
from PyQt6.QtWidgets import QApplication, QMessageBox, QWidget  # noqa: E402


@pytest.fixture
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def unanswered(monkeypatch):
    """Every QMessageBox ends at once with no button clicked."""
    monkeypatch.setattr(QMessageBox, "exec", lambda self: self.reject() or 0)


class _Fake(QWidget):
    """Just enough of a tab / dialog for the question methods: a real widget
    to parent the box, plus the attributes they read."""


def test_stuck_print_jobs_unanswered_does_not_print(qapp, unanswered):
    from ui.tabs.tab_print import TabPrint

    class _Module:
        cancelled = 0

        def get_stuck_jobs(self, printer):
            return [1, 2]

        def cancel_all_jobs(self, printer):
            self.cancelled += 1
            return 2

    fake = _Fake()
    fake._module = _Module()
    assert TabPrint._handle_stuck_jobs(fake, "Epson") is False
    assert fake._module.cancelled == 0


def test_scan_misalignment_unanswered_does_not_build(qapp, unanswered):
    from ui.dialogs.scanin_dialog import ScannerProfileDialog as ScaninDialog
    fake = _Fake()
    fake._align_warnings = ["page 1 is shifted"]
    stopped = []
    fake._stop_before_colprof = lambda: stopped.append(True)
    assert ScaninDialog._confirm_despite_misalignment(fake) is False
    assert stopped == [True]


def test_scan_read_findings_unanswered_do_not_build(qapp, unanswered):
    from ui.dialogs.scanin_dialog import ScannerProfileDialog as ScaninDialog
    fake = _Fake()
    fake._pages = [object()]
    fake._read_findings = [(1, "Odd reading", "patch A1 looks wrong")]
    fake._page_label = lambda i: f"Page {i + 1}"
    stopped = []
    fake._stop_before_colprof = lambda: stopped.append(True)
    assert ScaninDialog._confirm_despite_read_findings(fake) is False
    assert stopped == [True]
