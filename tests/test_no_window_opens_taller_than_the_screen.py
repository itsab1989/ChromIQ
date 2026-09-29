"""No window may open taller than the work area. Not even a message box.

Knut, v4.1.5-beta.10, on the patch editor and a CR30 chart. MEASURED on the
real screen, in the real app, driving his own journey (agent CM, 2026-09-06):

    body                 51 lines / 3055 characters of printtarg usage text
    work area            QRect(0, 38, 1728, 1079)
    QMessageBox frame    QRect(620, 38, 420, 1433)
    overflow                                  354 px
    OK button, bottom    global y 1451   ->   ON SCREEN = False

**macOS could not rescue it.** Cocoa's `constrainFrameRect:toScreen:` normally
shoves a grown window up so its bottom lands on the work area's edge; there is
no position at which a 1433 px window fits a 1079 px work area, so it parked the
top on the work area's top and let the rest hang off. Knut's 1920x1080 screen
has a work area of at most 1055 px, so his overflow was larger than the one
measured here. His only way out was Esc or Return, and the window said nothing
about that.

B8-72 fixed this class of fault for the windows in `ui/dialogs/tools_dialogs.py`
and only for those: the arithmetic was two METHODS OF `_ToolDialogBase`.
`Ti2RelayoutDialog` is a plain QDialog with a hard-coded `resize(1280, 820)`,
and a `QMessageBox` is Qt's class and can inherit nothing of ours. Both are
covered here, and the arithmetic now lives in `ui.widgets.WorkAreaClamped` so
there is one copy of it.

THE OFFSCREEN SCREEN IS WHY THIS FILE CAN PROVE ANYTHING, and here it is
harsher than the real one: 800x800, so a 3055-character message and an 820 px
dialog are both genuinely too big for it, and there is no window manager to
paper over a bad answer.
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication, QMessageBox, QPushButton  # noqa: E402
from PyQt6.QtCore import QPoint                                     # noqa: E402


#: The body Knut's box carried, in shape: printtarg's banner, its one useful
#: line, and fifty of usage written for an 80-column terminal.
PRINTTARG_DUMP = (
    "printtarg failed (1): Generate Target PostScrip file, Version 3.5.0\n"
    "  Diagnostic: Argument to -i wasn't recognised\n"
    "usage: printtarg [-v] [-i instr] [-p paper] [-t dpi] outfile\n"
    + "\n".join(
        f" -{c}  something          a line of usage text about {c}, written "
        f"for an eighty column terminal"
        for c in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWX")
)


@pytest.fixture(scope="module")
def _app():
    return QApplication.instance() or QApplication([])


def _show_and_measure(app, box):
    box.show()
    for _ in range(8):
        app.processEvents()
    work = (box.screen() or app.primaryScreen()).availableGeometry()
    frame = box.frameGeometry()
    buttons = [
        (b.text(),
         box.geometry().top() + b.mapTo(box, QPoint(0, b.height())).y())
        for b in box.findChildren(QPushButton)]
    return work, frame, buttons


def _warn_without_blocking(app, monkeypatch, text, seen):
    """Run the real `warn()` but measure the box instead of blocking on it.

    `monkeypatch.setattr`, never the `real = QMessageBox.exec` idiom: `exec` is
    INHERITED from QDialog, so restoring it by assignment leaves an unbound
    method on QMessageBox and every later `box.exec()` in the worker dies. See
    `conftest._repair_a_leaked_qmessagebox_exec`.
    """
    from ui import warning_sign

    def fake_exec(self):
        seen.append(_show_and_measure(app, self) + (self,))
        self.hide()
        return 0

    monkeypatch.setattr(QMessageBox, "exec", fake_exec)
    warning_sign.warn(None, "Render failed", text)


# ---------------------------------------------------------------------------
# the message box
# ---------------------------------------------------------------------------
def test_a_message_box_with_a_tool_dump_in_it_still_fits_the_work_area(
        _app, monkeypatch):
    seen: list = []
    _warn_without_blocking(_app, monkeypatch, PRINTTARG_DUMP, seen)
    assert seen, "warn() never opened a box"
    work, frame, _buttons, _box = seen[0]
    assert frame.height() <= work.height(), (
        f"the box opens {frame.height() - work.height()}px taller than the "
        f"work area ({frame} against {work}) — there is no position at which "
        f"it fits, which is exactly what Knut photographed")
    assert frame.bottom() <= work.bottom(), (
        f"the box hangs {frame.bottom() - work.bottom()}px below the usable "
        f"area")


def test_every_button_of_that_box_is_on_the_screen(_app, monkeypatch):
    """The height is the mechanism; THIS is the harm.

    A box that overflows takes its buttons with it, and a message box's buttons
    are at the bottom.
    """
    seen: list = []
    _warn_without_blocking(_app, monkeypatch, PRINTTARG_DUMP, seen)
    work, _frame, buttons, _box = seen[0]
    assert buttons, "the box has no buttons at all"
    off = [(t, y) for t, y in buttons if y > work.bottom()]
    assert not off, (
        f"buttons below the work area (bottom {work.bottom()}): {off}")


def test_the_overflow_goes_behind_show_details_rather_than_being_lost(
        _app, monkeypatch):
    """Capping a window must not cost the user the text.

    The split is mechanical — a prefix stays in the body, the WHOLE original
    goes into the detail pane — so nothing is truncated away and no sentence is
    invented.
    """
    seen: list = []
    _warn_without_blocking(_app, monkeypatch, PRINTTARG_DUMP, seen)
    _work, _frame, _buttons, box = seen[0]
    assert box.detailedText() == PRINTTARG_DUMP, (
        "the tool's output is not recoverable from the window")
    assert box.text() and box.text() in PRINTTARG_DUMP, (
        "the shown body is not a prefix of what was passed — something was "
        "rewritten rather than moved")


def test_a_short_message_is_left_exactly_as_it_was(_app, monkeypatch):
    """The cap is a rescue, not a policy.

    A one-line warning must not grow a "Show Details" button, and must not be
    cut about. This is the mutation control for the three tests above: if it
    ever fails, the fix has started rewriting messages that were fine.
    """
    seen: list = []
    short = "The chart folder is read only."
    _warn_without_blocking(_app, monkeypatch, short, seen)
    _work, _frame, _buttons, box = seen[0]
    assert box.text() == short
    assert not box.detailedText()


def test_the_helper_is_what_does_it_and_warn_calls_it(_app):
    """Read off the source: three call paths share `warn` / `inform` / `ask`,
    and a fix applied to one of them is not a fix."""
    import inspect
    from ui import warning_sign
    for fn in (warning_sign.warn, warning_sign._boxed):
        src = inspect.getsource(fn)
        assert "keep_message_box_inside_the_work_area" in src, (
            f"{fn.__name__} does not cap its box against the work area")


def test_the_cap_is_not_a_round_fraction_of_the_screen():
    """B8-39's lesson, applied to the new code before it can be forgotten: a
    round fraction of a work area is a number with nothing behind it, and the
    missing tenth is never spare."""
    import inspect
    import re
    from ui import widgets
    src = inspect.getsource(widgets.keep_message_box_inside_the_work_area)
    bad = [ln.strip() for ln in src.splitlines()
           if re.search(r"availableGeometry\(\)[^#]*\*\s*0\.", ln)]
    assert not bad, "the height is a fraction of the screen again: " + "; ".join(bad)


# ---------------------------------------------------------------------------
# the patch editor's own window (CK-13)
# ---------------------------------------------------------------------------
class _Settings(dict):
    def get(self, key, default=None):      # noqa: A003
        return dict.get(self, key, default)

    def set(self, key, value):
        self[key] = value


@pytest.fixture
def _editor(_app, tmp_path):
    from ui.dialogs.ti2_relayout_dialog import Ti2RelayoutDialog
    dlg = Ti2RelayoutDialog(object(), _Settings({
        "argyll_bin_path": "/Applications/Argyll/bin",
        "custom_output_path": str(tmp_path),
    }))
    yield dlg
    dlg.deleteLater()


def test_the_patch_editor_opens_inside_the_work_area(_app, _editor):
    """`resize(1280, 820)` with no reference to the screen at all.

    A 1366x768 laptop's work area is about 728 px, so the window opened 92 px
    taller than the screen — and Apply / Save… and Close sit at the very bottom
    of its right-hand column. The offscreen screen is 800 px, so the same
    arithmetic bites here.
    """
    _editor.show()
    for _ in range(8):
        _app.processEvents()
    work = (_editor.screen() or _app.primaryScreen()).availableGeometry()
    frame = _editor.frameGeometry()
    assert frame.height() <= work.height(), (
        f"the editor opens {frame.height() - work.height()}px taller than the "
        f"work area ({frame} against {work})")
    assert frame.bottom() <= work.bottom(), (
        f"the editor hangs {frame.bottom() - work.bottom()}px below the "
        f"usable area, where its Apply / Save and Close buttons live")
    assert frame.top() >= work.top(), (
        "the editor's title bar is above the usable area")


def test_the_editor_inherits_the_clamp_rather_than_restating_it(_editor):
    """One copy of the arithmetic, and a window that cannot opt out of it.

    The whole shape of this defect was a rule enforced in one place and read in
    another. `_ToolDialogBase` had these two methods and every window that was
    not one of its subclasses was outside the fix for three weeks.
    """
    from ui.widgets import WorkAreaClamped
    from ui.dialogs.tools_dialogs import _ToolDialogBase
    assert isinstance(_editor, WorkAreaClamped)
    assert issubclass(_ToolDialogBase, WorkAreaClamped)
    assert _editor._keep_inside_the_work_area.__func__ is \
        WorkAreaClamped._keep_inside_the_work_area
    assert _ToolDialogBase._keep_inside_the_work_area is \
        WorkAreaClamped._keep_inside_the_work_area


def test_the_clamp_brings_the_editor_back_from_under_the_taskbar(_app, _editor):
    """Move it out deliberately, then ask — a test that only ever sees a window
    already in the right place cannot tell a working clamp from a missing one.
    """
    _editor.show()
    for _ in range(8):
        _app.processEvents()
    work = (_editor.screen() or _app.primaryScreen()).availableGeometry()
    _editor.move(work.x(), work.bottom() - 40)
    _app.processEvents()
    moved_to = _editor.frameGeometry().top()
    _editor._keep_inside_the_work_area()
    _app.processEvents()
    frame = _editor.frameGeometry()
    assert frame.top() < moved_to, "the window was left hanging off the bottom"
    assert frame.bottom() <= work.bottom()
