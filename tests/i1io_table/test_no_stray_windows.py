"""NO LITTLE WINDOWS OF ITS OWN (found on screen, 25 Nov 2026; 4.3.65 has it too): a page of the
table's panel that was cleared before the layout had shown its buttons left them without a parent,
and they showed themselves as windows, for as long as a nested event loop (a message box, the print
dialog, a driver's script) kept their deletion waiting."""
from __future__ import annotations

import pytest
from PyQt6.QtCore import QCoreApplication, QEventLoop, QTimer
from PyQt6.QtWidgets import QApplication, QCheckBox, QPushButton

from tests.i1io_table import bed_sim as B
from tests.i1io_table.test_pieces_in_the_window import _window, open_window, settings  # noqa: F401
from tests.i1io_table.test_pieces_measured import chart, four  # noqa: F401


def _strays(known) -> list:
    return [(type(w).__name__, getattr(w, "text", lambda: "")()) for w in
            QApplication.topLevelWidgets()
            if w.isVisible() and w not in known and isinstance(w, (QPushButton, QCheckBox))]


def _inside_an_event_loop(body) -> None:
    """*body* in a slot of a running event loop: what it deletes later is not deleted by the
    events it processes itself, as in a nested loop of the app."""
    loop, out = QEventLoop(), []

    def run():
        try:
            body()
        except BaseException as exc:      # noqa: BLE001 - raised again below
            out.append(exc)
        finally:
            loop.quit()
    QTimer.singleShot(0, run)
    loop.exec()
    if out:
        raise out[0]


@pytest.mark.parametrize("asking", [False, True], ids=["pop-ups", "panel"])
def test_pages_shown_and_cleared_at_once_leave_no_window(qtbot, monkeypatch, tmp_path, settings,
                                                         four, asking):  # noqa: F811
    bed = B.Bed(four.laid(0))
    win, sim, run, p, saved, finished = _window(qtbot, monkeypatch, tmp_path, settings, four, bed,
                                                asking=asking)
    p.drive_until("prepare")
    known = set(QApplication.topLevelWidgets())

    def body():
        for n in range(12):
            win._show("prepare", f"Page {n}", "text " * (3 + 20 * (n % 3)),
                      [(f"answer {n}.{k}", win._next) for k in range(2 + n % 3)],
                      ticks=["a tick", "another tick"] if n % 2 else [])
            if n % 4 == 0:
                win.resize(win.width() + (40 if n % 8 else -40), win.height())
                win._flow_choices()
        for _ in range(5):
            QCoreApplication.processEvents()
        assert _strays(known) == []
        # ...and what the last page shows is there
        assert all(b.isVisibleTo(win if asking else b.window()) for b in win._buttons)
    _inside_an_event_loop(body)


def test_a_whole_measurement_answered_at_once(qtbot, monkeypatch, tmp_path, settings,
                                              four):  # noqa: F811
    bed = B.Bed(four.laid(0))
    win, sim, run, p, saved, finished = _window(qtbot, monkeypatch, tmp_path, settings, four, bed)
    known = set(QApplication.topLevelWidgets())

    def body():
        assert p.drive_until(("next_page", "row_failed_strip")) == "next_page"
        assert _strays(known) == []
    _inside_an_event_loop(body)
