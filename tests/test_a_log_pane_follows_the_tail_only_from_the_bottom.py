"""A log pane follows its newest line only while the reader is at the bottom.

WHAT THIS GUARDS
----------------
A user verifying a profile, on 4.3.0-beta.4, 2026-09-11:

    "if you scroll up the output pane while its calculating, it forces it back
     down to the bottom every time the % goes up. Not a big deal at all, just a
     minor annoyance. Often programs fix this by only auto-scrolling if the
     scroll bar is already at the bottom."

REPRODUCED ON SCREEN, on a real ``colprof`` build in a real window
(``proof_printpath/drive_p1_output_pane_scroll.py``, Build Profile tab,
210-patch measurement, ArgyllCMS 3.5.0):

    before   parked the view at the TOP mid-build; one ``processEvents`` later
             it was back at value 20 of a maximum of 21, and it stayed pinned:
             1837 of 1840 samples sat at the bottom across 71 appends, ending
             at value 244 == maximum 244.
    after    parked at the top: value 0 of 22, and it STAYED at 0 through 81
             appends while the maximum grew to 256. Nought of 2222 samples sat
             at the bottom.
    both     with the view left at the bottom, the pane still followed every
             line: value == maximum at the end of the build.

WHAT A PLAIN QPlainTextEdit DOES ON ITS OWN, MEASURED
----------------------------------------------------
Because it turned out to matter, and because two of the first mutations run
against this file did not land until it was measured:

    parked at the bottom, one-line append           value 198 == maximum 198
    parked at the bottom, two-block append          value 200 == maximum 200
    parked ONE line up, a 4000-char wrapped append  value stays 196, max -> 288
    parked at the bottom, insertPlainText at pos 0  value 197, maximum 201
    append + ensureCursorVisible                    lands exactly on maximum

So the base class already follows the tail only from the bottom, for appends.
Three things follow, and they are what these tests pin:

* the bug was ours, in the 89 unconditional ``ensureCursorVisible()`` calls;
* "at the bottom" gets NO tolerance, because a reader at ``maximum - 1`` is a
  reader Qt itself leaves alone (``test_a_reader_one_line_up_is_not_at_the
  _bottom``);
* "am I at the bottom?" must still be asked BEFORE the text arrives, because
  ``insertPlainText`` is a door where the two moments give opposite answers
  (``test_an_insert_at_the_top_keeps_the_reader_at_the_bottom``).

The other trap is the guard-on-one-door one. There are EIGHT log panes in this
app, not one, and 89 ``ensureCursorVisible()`` calls between them —
``test_no_log_pane_is_a_bare_QPlainTextEdit`` refuses a ninth built the old way.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


@pytest.fixture()
def pane(qapp):
    """A real pane, sized so a handful of lines overflows it."""
    from ui.widgets import TailFollowLog
    w = TailFollowLog()
    w.setReadOnly(True)
    w.resize(320, 60)
    w.show()
    for i in range(200):
        w.appendPlainText(f"line {i}")
    qapp.processEvents()
    assert w.verticalScrollBar().maximum() > 10, \
        "the fixture must produce a pane that can actually be scrolled"
    yield w
    w.close()


# ---------------------------------------------------------------------------
# The behaviour she asked for
# ---------------------------------------------------------------------------

def test_a_pane_the_reader_scrolled_up_is_left_alone(pane, qapp):
    sb = pane.verticalScrollBar()
    sb.setValue(0)
    qapp.processEvents()
    before_max = sb.maximum()

    for i in range(20):
        pane.appendPlainText(f"progress {i} %")
        pane.ensureCursorVisible()          # the 89 call sites, faithfully
    qapp.processEvents()

    assert sb.maximum() > before_max, "the document did not actually grow"
    assert sb.value() == 0, (
        f"the view was dragged from 0 to {sb.value()} while the reader was "
        f"reading further up")
    assert pane.is_following_tail() is False


def test_a_pane_at_the_bottom_keeps_following(pane, qapp):
    sb = pane.verticalScrollBar()
    sb.setValue(sb.maximum())
    qapp.processEvents()

    for i in range(20):
        pane.appendPlainText(f"progress {i} %")
        pane.ensureCursorVisible()
    qapp.processEvents()

    assert pane.is_following_tail() is True
    assert sb.value() == sb.maximum(), (
        f"the pane stopped following its own tail: value {sb.value()} of "
        f"maximum {sb.maximum()}")


def test_an_append_with_no_ensure_cursor_visible_still_holds_the_bottom(pane,
                                                                       qapp):
    """Not every call site remembers the tail call, and it must not matter.

    If the bottom were held only by ``ensureCursorVisible()``, one append that
    skipped it would leave the view a line short, and the NEXT append would read
    that as the reader having scrolled away — latching the following off for
    good, with nobody having touched anything.
    """
    sb = pane.verticalScrollBar()
    sb.setValue(sb.maximum())
    qapp.processEvents()

    pane.appendPlainText("a line whose call site forgot the tail call")
    qapp.processEvents()
    assert sb.value() == sb.maximum()

    pane.appendPlainText("and the line after it")
    pane.ensureCursorVisible()
    qapp.processEvents()
    assert pane.is_following_tail() is True
    assert sb.value() == sb.maximum()


def test_a_reader_one_line_up_is_not_at_the_bottom(pane, qapp):
    """No tolerance, and the measurement that rules one out.

    A plain ``QPlainTextEdit`` parked at ``maximum - 1`` and handed a
    4000-character append does not move: Qt reads that reader as having
    scrolled up. A slack of even a single line here would read them as being at
    the bottom and drag them down, which is her complaint again in a smaller
    font.
    """
    sb = pane.verticalScrollBar()
    sb.setValue(sb.maximum() - 1)
    qapp.processEvents()
    parked = sb.value()

    assert pane.is_at_bottom() is False
    pane.appendPlainText("a" * 4000)
    pane.ensureCursorVisible()
    qapp.processEvents()

    assert sb.value() == parked, (
        f"a reader one line off the bottom was dragged from {parked} to "
        f"{sb.value()}")


def test_an_insert_at_the_top_keeps_the_reader_at_the_bottom(pane, qapp):
    """The door where "before" and "after" give OPPOSITE answers.

    Measured on a plain ``QPlainTextEdit``: parked at the bottom of a 200-line
    document, ``insertPlainText`` of four lines at position 0 leaves the value
    at 197 while the maximum becomes 201. Qt does not hold the bottom here, so
    a pane that asked the question after the text arrived would conclude the
    reader had scrolled up — about a reader who had not moved — and stop
    following.
    """
    from PyQt6.QtGui import QTextCursor
    sb = pane.verticalScrollBar()
    cur = pane.textCursor()
    cur.setPosition(0)
    pane.setTextCursor(cur)
    sb.setValue(sb.maximum())
    qapp.processEvents()
    assert pane.is_at_bottom() is True

    pane.insertPlainText("inserted\nat\nthe\ntop\n")
    qapp.processEvents()

    assert pane.is_following_tail() is True, (
        "the pane read a reader who had not moved as having scrolled up")
    assert sb.value() == sb.maximum(), (
        f"the reader was left at {sb.value()} of {sb.maximum()} after text "
        f"appeared above them")


def test_scrolling_back_to_the_bottom_resumes_following(pane, qapp):
    sb = pane.verticalScrollBar()
    sb.setValue(0)
    qapp.processEvents()
    pane.appendPlainText("while away")
    qapp.processEvents()
    assert sb.value() == 0

    sb.setValue(sb.maximum())               # the reader scrolls back down
    qapp.processEvents()
    pane.appendPlainText("back at the bottom")
    qapp.processEvents()

    assert pane.is_following_tail() is True
    assert sb.value() == sb.maximum()


def test_clearing_the_pane_starts_following_again(pane, qapp):
    sb = pane.verticalScrollBar()
    sb.setValue(0)
    qapp.processEvents()
    pane.appendPlainText("x")
    assert pane.is_following_tail() is False

    pane.clear()                            # a new run begins
    qapp.processEvents()
    assert pane.is_following_tail() is True
    for i in range(200):
        pane.appendPlainText(f"fresh {i}")
    qapp.processEvents()
    assert sb.value() == sb.maximum()


def test_set_plain_text_starts_following_again(pane, qapp):
    sb = pane.verticalScrollBar()
    sb.setValue(0)
    qapp.processEvents()
    pane.appendPlainText("x")
    assert pane.is_following_tail() is False

    pane.setPlainText("[ERROR] No input .ti3 file selected.")
    qapp.processEvents()
    assert pane.is_following_tail() is True


def test_a_cursor_handed_to_the_pane_does_not_drag_the_view(pane, qapp):
    """Create Chart rewrites its progress line in place through the cursor.

    ``TabChart._set_progress_line`` selects the last line, replaces it and calls
    ``setTextCursor`` — and Qt scrolls to a cursor it is handed. That is a
    second door onto the same room.
    """
    from PyQt6.QtGui import QTextCursor
    sb = pane.verticalScrollBar()
    sb.setValue(0)
    qapp.processEvents()
    pane.appendPlainText("Arranging colour patches: 10%")
    qapp.processEvents()
    assert sb.value() == 0

    cur = pane.textCursor()
    cur.movePosition(QTextCursor.MoveOperation.End)
    cur.select(QTextCursor.SelectionType.LineUnderCursor)
    cur.removeSelectedText()
    cur.insertText("Arranging colour patches: 40%")
    pane.setTextCursor(cur)
    pane.ensureCursorVisible()
    qapp.processEvents()

    assert sb.value() == 0, (
        f"handing the pane a cursor at the end dragged the view to "
        f"{sb.value()}")


def test_a_short_document_that_cannot_scroll_still_follows(qapp):
    """maximum == 0 means every position is the bottom, and must read as one."""
    from ui.widgets import TailFollowLog
    w = TailFollowLog()
    w.resize(400, 300)
    w.show()
    w.appendPlainText("one line")
    qapp.processEvents()
    assert w.verticalScrollBar().maximum() == 0
    assert w.is_at_bottom() is True
    assert w.is_following_tail() is True
    w.close()


# ---------------------------------------------------------------------------
# Every door, not one of them
# ---------------------------------------------------------------------------

#: Every log pane in the app, as (module path, attribute). Eight panes: the
#: five tab panes, the two extra Build Profile modules, the shared Tools-dialog
#: status pane (ten dialog classes inherit it) and the Spot Read notes.
LOG_PANES = [
    ("ui/tabs/tab_chart.py", "_log"),
    ("ui/tabs/tab_measure.py", "_log"),
    ("ui/tabs/tab_profile.py", "_log"),
    ("ui/tabs/tab_profile.py", "_pc_log"),
    ("ui/tabs/tab_profile.py", "_ac_log"),
    ("ui/tabs/tab_check_refine.py", "_log"),
    ("ui/dialogs/tools_dialogs.py", "_log"),
    ("ui/dialogs/spot_read_dialog.py", "_log"),
]


def _log_pane_constructions(path: Path) -> "list[tuple[str, str, int]]":
    """Every ``self.<something-log> = <Class>(...)`` in *path*."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    out: list[tuple[str, str, int]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign) or not isinstance(node.value,
                                                              ast.Call):
            continue
        func = node.value.func
        cls = func.id if isinstance(func, ast.Name) else (
            func.attr if isinstance(func, ast.Attribute) else "")
        for tgt in node.targets:
            if (isinstance(tgt, ast.Attribute)
                    and isinstance(tgt.value, ast.Name)
                    and tgt.value.id == "self"
                    and tgt.attr.endswith("log")):
                out.append((tgt.attr, cls, node.lineno))
    return out


@pytest.mark.parametrize("rel,attr", LOG_PANES)
def test_every_named_log_pane_is_a_tail_follow_log(rel, attr):
    hits = [(a, c, ln) for a, c, ln in _log_pane_constructions(ROOT / rel)
            if a == attr]
    assert hits, f"{rel} no longer builds self.{attr}"
    for a, cls, ln in hits:
        assert cls == "TailFollowLog", (
            f"{rel}:{ln} builds self.{a} as {cls}, which does not know whether "
            f"the reader is at the bottom")


def test_no_log_pane_is_a_bare_QPlainTextEdit():
    """A ninth pane must not arrive built the old way.

    ``ui/dialogs/scanin_dialog.py`` is exempt by inheritance, not by exception:
    ``ScannerProfileDialog`` extends ``_ToolDialogBase`` and writes into the
    pane built there.
    """
    offenders: list[str] = []
    for path in sorted((ROOT / "ui").rglob("*.py")):
        for attr, cls, ln in _log_pane_constructions(path):
            if cls == "QPlainTextEdit":
                offenders.append(
                    f"{path.relative_to(ROOT)}:{ln} self.{attr} = {cls}(...)")
    assert not offenders, (
        "these log panes drag the reader back to the bottom on every line; "
        "build them with ui.widgets.TailFollowLog instead:\n  "
        + "\n  ".join(offenders))


def test_the_tail_follow_pane_connects_nothing_to_a_scroll_bar_signal():
    """The fade-scroll SIGSEGV, in the one class most tempted to repeat it.

    ``CLAUDE.md`` records the crash: a scroll bar's ``rangeChanged`` connected
    to a lambda capturing ``self``. The obvious way to write this class is to
    listen to ``valueChanged``. It does not, and must not start.
    """
    src = (ROOT / "ui" / "widgets.py").read_text(encoding="utf-8")
    start = src.index("class TailFollowLog")
    end = src.index("\nLOG_GAP_TOTAL", start)
    body = src[start:end]
    assert ".connect(" not in body, (
        "TailFollowLog connected something to a signal; it is supposed to ASK "
        "the scroll bar, never to subscribe to it")


def test_the_spot_read_results_table_follows_the_same_rule():
    """The one non-text tail-follower in the app, and the same annoyance."""
    src = (ROOT / "ui" / "dialogs" / "spot_read_dialog.py").read_text(
        encoding="utf-8")
    fn = src[src.index("def _append_row"):]
    fn = fn[:fn.index("\n    def ")]
    assert "scrollToBottom()" in fn
    assert re.search(r"at_bottom\s*=.*sb\.value\(\)\s*>=\s*sb\.maximum\(\)", fn), \
        "the table no longer asks whether the reader is at the bottom"
    assert fn.index("at_bottom =") < fn.index("insertRow"), (
        "the table asks AFTER inserting the row, which makes the maximum grow "
        "and a reader who has not moved look as though they had")
    assert "if at_bottom:" in fn
