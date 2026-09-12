"""Reproduce: the Create Chart progress line drags a scrolled-up reader down.

Run ON SCREEN (no QT_QPA_PLATFORM).  It builds the real `TailFollowLog` from
`ui/widgets.py` and drives it exactly as `TabChart._set_progress_line` does.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PyQt6.QtWidgets import QApplication            # noqa: E402
from PyQt6.QtGui import QTextCursor                 # noqa: E402
from ui.widgets import TailFollowLog                # noqa: E402


def set_progress_line(log, text):
    """Verbatim from ui/tabs/tab_chart.py::TabChart._set_progress_line."""
    cur = log.textCursor()
    cur.movePosition(QTextCursor.MoveOperation.End)
    cur.select(QTextCursor.SelectionType.LineUnderCursor)
    cur.removeSelectedText()
    cur.insertText(text)
    log.setTextCursor(cur)
    log.ensureCursorVisible()


def main() -> int:
    app = QApplication(sys.argv)
    w = TailFollowLog()
    w.setWindowTitle("TailFollowLog - progress line")
    w.resize(520, 80)
    w.show()
    app.processEvents()
    for i in range(200):
        w.appendPlainText(f"line {i}")
    app.processEvents()
    sb = w.verticalScrollBar()
    print("filled:          value=%d max=%d following=%s"
          % (sb.value(), sb.maximum(), w.is_following_tail()))

    sb.setValue(0)                      # the reader scrolls up to read something
    app.processEvents()
    print("reader at top:   value=%d max=%d following=%s"
          % (sb.value(), sb.maximum(), w.is_following_tail()))

    for pct in (10, 20, 30):
        set_progress_line(w, f"Arranging colour patches: {pct}%")
        app.processEvents()
        print("  after %3d%%:    value=%d max=%d" % (pct, sb.value(), sb.maximum()))

    dragged = sb.value() >= sb.maximum() and sb.maximum() > 0
    print("VERDICT:", "DRAGGED TO THE BOTTOM (bug)" if dragged else "stayed put (ok)")
    return 1 if dragged else 0


if __name__ == "__main__":
    sys.exit(main())
