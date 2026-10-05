"""Agent 18b (2026-10-05): two on-screen drivers hung on Basti's screen.

* The second hang: the driver answered the "New patch set" window while that
  window was still in its NON-modal, opacity-0 realise phase
  (``_NewChartDialog.exec`` shows itself and pumps events before it enters
  ``QDialog.exec()``). ``accept()`` there only hid it; the override then
  entered ``exec()`` and the window came back, modal, unanswered.
  ``onscreen_capture.in_modal_loop`` is what a driver must wait for.
* Neither driver could end itself: its only time limit was 5 hours.
  ``onscreen_capture.StepGuard`` ends the process per step, from a thread,
  and writes the stacks that name the hang.
* A WINDOW-modal box (a sheet) is not always ``activeModalWidget()``; the
  watchdog now finds it among the top-level windows.
"""
from __future__ import annotations

import subprocess
import sys
import textwrap
import time
from pathlib import Path

import pytest

pytest.importorskip("PyQt6")
from PyQt6.QtCore import Qt, QTimer                                 # noqa: E402
from PyQt6.QtWidgets import (QApplication, QDialog, QMessageBox,    # noqa: E402
                             QWidget)

import scripts.onscreen_capture as oc                              # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


class _RealiseFirst(QDialog):
    """The shape of ``_NewChartDialog.exec``: shown non-modally at opacity 0,
    events pumped, then the real modal loop."""

    seen: list

    def exec(self):  # noqa: A003
        self.setWindowOpacity(0.0)
        self.show()
        for _ in range(5):
            QApplication.processEvents()
            time.sleep(0.01)
        self.setWindowOpacity(1.0)
        return super().exec()


def test_the_realise_phase_is_not_the_modal_loop():
    app = QApplication.instance() or QApplication([])
    dlg = _RealiseFirst()
    states = []

    def look():
        states.append((dlg.isVisible(), oc.in_modal_loop(dlg)))
        if oc.in_modal_loop(dlg):
            dlg.accept()
        else:
            QTimer.singleShot(5, look)

    QTimer.singleShot(0, look)
    result = dlg.exec()
    # it was visible but NOT ready at least once (the realise phase), and the
    # driver answered only inside the loop, so exec() returned its answer
    assert any(vis and not ready for vis, ready in states)
    assert result == QDialog.DialogCode.Accepted
    assert not dlg.isVisible()


def test_answering_in_the_realise_phase_is_lost_which_is_the_hang():
    """The failure itself, kept as a fact: accept() before the loop starts is
    forgotten and the dialog then waits in exec() (ended here by a timer)."""
    app = QApplication.instance() or QApplication([])
    dlg = _RealiseFirst()
    answered_early = []

    def early():
        if dlg.isVisible() and not oc.in_modal_loop(dlg) and not answered_early:
            answered_early.append(True)
            dlg.accept()
    QTimer.singleShot(0, early)
    rescued = []

    def rescue():
        if dlg.isVisible():
            rescued.append(True)
            dlg.reject()
    QTimer.singleShot(400, rescue)
    result = dlg.exec()
    assert answered_early and rescued
    assert result == QDialog.DialogCode.Rejected


def test_a_window_modal_box_is_seen_by_the_watchdog():
    app = QApplication.instance() or QApplication([])
    host = QWidget()
    host.show()
    box = QMessageBox(QMessageBox.Icon.Question, "Sheet", "Really?",
                      QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
                      host)
    box.setWindowModality(Qt.WindowModality.WindowModal)
    box.open()
    app.processEvents()
    assert box in oc.PopupWatchdog._popups()
    plain = QDialog(host)
    plain.setWindowModality(Qt.WindowModality.WindowModal)
    plain.show()
    app.processEvents()
    assert plain in oc.PopupWatchdog._popups()
    box.done(0)
    plain.close()
    host.close()


def _guard_script(tmp_path: Path, body: str) -> subprocess.CompletedProcess:
    script = tmp_path / "drv.py"
    script.write_text(textwrap.dedent(f"""
        import sys, time
        sys.path.insert(0, {str(ROOT)!r})
        from scripts.onscreen_capture import StepGuard
        g = StepGuard({str(tmp_path)!r}, step_s=1.0, total_s=60.0, log=lambda m: None).start()
    """) + textwrap.dedent(body))
    return subprocess.run([sys.executable, str(script)], capture_output=True,
                          text=True, timeout=120)


def test_a_step_past_its_budget_ends_the_process_and_names_the_line(tmp_path):
    t0 = time.monotonic()
    r = _guard_script(tmp_path, """
        g.step("stuck step", 1.0)
        def waits_for_ever():
            while True:
                time.sleep(0.05)
        waits_for_ever()
    """)
    assert r.returncode == 3, r.stderr
    # budgeted for a loaded machine: it must not wait anywhere near for ever
    assert time.monotonic() - t0 < 60
    hang = (tmp_path / "hang-stuck_step.txt").read_text()
    assert "ran past its budget" in hang and "waits_for_ever" in hang


def test_a_step_that_finishes_in_time_is_left_alone(tmp_path):
    r = _guard_script(tmp_path, """
        for i in range(4):
            g.step(f"s{i}", 2.0)
            time.sleep(0.3)
        g.stop()
        print("finished")
    """)
    assert r.returncode == 0 and "finished" in r.stdout
    assert not list(tmp_path.glob("hang-*.txt"))


def test_the_total_budget_ends_a_run_whose_steps_keep_renewing(tmp_path):
    script = tmp_path / "drv.py"
    script.write_text(textwrap.dedent(f"""
        import sys, time
        sys.path.insert(0, {str(ROOT)!r})
        from scripts.onscreen_capture import StepGuard
        g = StepGuard({str(tmp_path)!r}, step_s=5.0, total_s=1.5, log=lambda m: None).start()
        while True:
            g.step("renewing", 5.0)
            time.sleep(0.1)
    """))
    r = subprocess.run([sys.executable, str(script)], capture_output=True, text=True,
                       timeout=120)
    assert r.returncode == 3
    assert "total budget" in (tmp_path / "hang-renewing.txt").read_text()


def test_the_watchdog_photographs_outside_its_own_tick(monkeypatch, tmp_path):
    """Third hang (2026-10-05 02:20): capture_window pumps events, the
    watchdog photographed INSIDE its tick, the driver's next steps ran inside
    that tick, and Qt never fired the watchdog's timer again, so the "Apply or
    save" question was never answered. The photo must come after the tick."""
    app = QApplication.instance() or QApplication([])
    dog = oc.PopupWatchdog(tmp_path, photograph=True, policy="dismiss", grace_s=0.2,
                           interval_ms=50, log=lambda m: None)
    calls = []
    looks = []
    real_popups = oc.PopupWatchdog._popups
    monkeypatch.setattr(oc.PopupWatchdog, "_popups",
                        staticmethod(lambda: (looks.append(1), real_popups())[1]))

    def fake_capture(w, path, **kw):
        # what capture_window does: pump events for a while. The watchdog
        # must keep looking meanwhile (it cannot if this runs in its tick).
        before = len(looks)
        end = time.monotonic() + 0.5
        while time.monotonic() < end:
            QApplication.processEvents()
            time.sleep(0.01)
        calls.append(len(looks) > before)
        return False, "test"
    monkeypatch.setattr(oc, "capture_window", fake_capture)
    host = QWidget()
    box = QMessageBox(QMessageBox.Icon.Question, "Q1", "First?",
                      QMessageBox.StandardButton.Cancel, host)
    dog.start()
    QTimer.singleShot(5000, box.reject)          # safety net, never needed
    t0 = time.monotonic()
    box.exec()
    dog.stop()
    assert calls and all(calls)
    # answered by the watchdog (Escape), well before the safety net
    assert dog.events and dog.events[0]["action"].startswith("pressed")
    assert time.monotonic() - t0 < 4.0
