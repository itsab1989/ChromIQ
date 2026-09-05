"""A tool window is PLACED before it is SIZED, and nothing put it back.

`QDialog::showEvent` runs `adjustPosition`: it centres the window on its parent
and then clamps the result against the screen's `availableGeometry` — using the
size the window has **at that moment**. Every dialog in `ui/dialogs/tools_dialogs.py`
is resized a few lines later, once its rows are real and its wrapped labels have
claimed their height, so the clamp is stale before it matters. The window keeps
the top-left corner chosen for a shorter window and grows downward, under the
taskbar.

Traced on the live scanner/camera window (agent BM, 2026-09-05, German, macOS,
work area 994 px tall):

    base.showEvent on entry     y = -28, h = 744
    base.showEvent on exit      y = 137, h = 860
    just after show()           y = 110, h = 894
    settled                     y = 110, h = 922

— 178 px of growth after the position was chosen.

**macOS HIDES THIS AND WINDOWS DOES NOT.** Cocoa's `constrainFrameRect:toScreen:`
shoves the window up again on every one of those growth steps, which is why the
frame lands with its bottom exactly on the work area's edge here and the defect
is invisible. The Windows ARM64 VM reported the same window opening **67 logical
pixels below the usable area, hiding three controls completely** — add a scan for
averaging, save a diagnostic image, and use the .cht's registration marks (W-07,
`Desktop/HANDOVER-to-macos-3.md`). It is the POSITION and not the size: moved to
the top, everything fits.

THE OFFSCREEN SCREEN IS WHY THIS FILE CAN PROVE ANYTHING. CLAUDE.md warns that
its 800x800 screen makes geometry tests pass vacuously; here it is the opposite —
offscreen has no window manager to rescue a badly placed window, so it shows what
Windows shows. Measured on this window under `QT_QPA_PLATFORM=offscreen`, before
the fix: `frame [0, 88, 1244, 724]` against a work area ending at 799, i.e. **12
px below it**. After: `frame [0, 76, ...]`, bottom exactly 799.
"""
from __future__ import annotations

import inspect
import os
import re

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication                     # noqa: E402

from tests.scanner_floor_probe import FakeSettings           # noqa: E402


@pytest.fixture(scope="module")
def _app():
    return QApplication.instance() or QApplication([])


@pytest.fixture(scope="module")
def _out_dir(tmp_path_factory):
    return tmp_path_factory.mktemp("tool-window-placement")


def _make(app, out_dir):
    from ui.dialogs.scanin_dialog import ScannerProfileDialog
    dlg = ScannerProfileDialog(object(), FakeSettings(out_dir))
    dlg.show()
    for _ in range(8):
        app.processEvents()
    dlg.layout().activate()
    app.processEvents()
    return dlg


def _work_area(dlg, app):
    screen = dlg.screen() or app.primaryScreen()
    return screen.availableGeometry()


def test_the_window_opens_with_its_bottom_inside_the_work_area(_app, _out_dir):
    """The whole of W-07 in one line, and it is not a vacuous one.

    The offscreen screen is 800 px tall and this window opens at 724 — so the
    window FITS and only its placement can put it out of the work area. That is
    exactly the Windows report: "it is the POSITION, not the size".
    """
    dlg = _make(_app, _out_dir)
    try:
        work = _work_area(dlg, _app)
        frame = dlg.frameGeometry()
        assert frame.height() <= work.height(), (
            "this test can only speak about placement while the window still "
            f"fits the work area — it is {frame.height()}px tall against "
            f"{work.height()}px, so something else changed and the assertion "
            "below would be measuring the wrong thing")
        assert frame.bottom() <= work.bottom(), (
            f"the window opens {frame.bottom() - work.bottom()}px below the "
            f"usable area (frame {frame}, work area {work}) — on Windows that "
            f"is a band of controls nothing on screen says are there")
        assert frame.top() >= work.top(), (
            f"the window opens {work.top() - frame.top()}px above the usable "
            f"area — its title bar is under the menu bar")
    finally:
        dlg.deleteLater()


def test_the_clamp_brings_a_window_back_from_under_the_taskbar(_app, _out_dir):
    """Move it out deliberately, then ask — the fix must actually move it.

    A test that only ever sees a window already in the right place cannot tell
    a working clamp from a missing one.
    """
    dlg = _make(_app, _out_dir)
    try:
        work = _work_area(dlg, _app)
        dlg.move(work.x(), work.bottom() - 50)      # 50 px of it left on screen
        _app.processEvents()
        moved_to = dlg.frameGeometry().top()
        dlg._keep_inside_the_work_area()
        _app.processEvents()
        frame = dlg.frameGeometry()
        assert frame.top() < moved_to, (
            "the window was left where it was put, hanging off the bottom")
        assert frame.bottom() <= work.bottom(), (
            f"still {frame.bottom() - work.bottom()}px below the work area")
    finally:
        dlg.deleteLater()


def test_the_clamp_never_pushes_the_title_bar_off_the_top(_app, _out_dir):
    """A window taller than the work area cannot be shown whole, and the end
    to keep is the one with the title bar and the first row on it."""
    dlg = _make(_app, _out_dir)
    try:
        work = _work_area(dlg, _app)
        dlg.setMinimumHeight(0)
        dlg.resize(dlg.width(), work.height() + 300)
        _app.processEvents()
        dlg.move(work.x(), work.y() + 40)
        _app.processEvents()
        dlg._keep_inside_the_work_area()
        _app.processEvents()
        assert dlg.frameGeometry().top() >= work.top(), (
            "a window too tall for the screen was pushed up until its title "
            "bar was off it — the bottom cannot be rescued and the top can")
    finally:
        dlg.deleteLater()


def test_a_window_that_already_fits_is_left_where_the_user_put_it(_app, _out_dir):
    """The clamp is a rescue, not a placement policy.

    VERTICALLY ONLY, and that is not a hedge. This window is 1244 px wide and
    the offscreen screen is 800, so the horizontal half of the clamp is doing
    its job when it pulls x back to the left edge — asserting that x did not
    move would be asserting that the clamp is broken. Height is the dimension
    W-07 is about and the one where the window genuinely fits here.
    """
    dlg = _make(_app, _out_dir)
    try:
        work = _work_area(dlg, _app)
        # The window opens as tall as the work area can hold it, so it is made
        # shorter here first — otherwise there is nowhere inside the work area
        # to put it and the question cannot be asked at all.
        dlg.setMinimumHeight(0)
        dlg.resize(dlg.width(), max(200, dlg.height() - 120))
        _app.processEvents()
        room = work.height() - dlg.frameGeometry().height()
        assert room > 20, (
            f"no room to move the window inside the work area "
            f"(frame {dlg.frameGeometry().height()}px, work {work.height()}px)")
        dlg.move(dlg.frameGeometry().x(), work.y() + min(room, 25))
        _app.processEvents()
        before = dlg.frameGeometry().top()
        dlg._keep_inside_the_work_area()
        _app.processEvents()
        assert dlg.frameGeometry().top() == before, (
            f"a window whose whole height was inside the work area was moved "
            f"from y={before} to y={dlg.frameGeometry().top()} anyway")
    finally:
        dlg.deleteLater()


def test_every_resize_the_base_class_performs_is_followed_by_the_clamp():
    """The class of bug, not the one instance of it.

    `_ToolDialogBase` resizes in two places — `showEvent` and `_refit_height` —
    and each of them invalidates the position Qt chose. A third one added later
    would reintroduce W-07 in a window nobody thought to re-check, so the rule
    is read off the source instead of trusted to memory.
    """
    from ui.dialogs import tools_dialogs
    src = inspect.getsource(tools_dialogs._ToolDialogBase)
    lines = src.splitlines()
    # The clamp's OWN resize — the one that brings a frame taller than the work
    # area down to it — is exempt, and only that one: it IS the clamp, and a
    # rule that made it call itself would be a loop rather than a guard.
    clamp = inspect.getsource(tools_dialogs._ToolDialogBase._keep_inside_the_work_area)
    exempt = {ln.strip() for ln in clamp.splitlines() if "self.resize(" in ln}
    resizes = [i for i, ln in enumerate(lines)
               if re.search(r"\bself\.resize\(", ln) and ln.strip() not in exempt]
    assert len(resizes) >= 2, (
        "the base class no longer resizes itself — this test is measuring "
        "nothing and the placement rule it guards may have moved with it")
    for i in resizes:
        following = "\n".join(lines[i:i + 4])
        assert "_keep_inside_the_work_area" in following, (
            "a resize with no work-area clamp after it:\n"
            + "\n".join(lines[max(0, i - 2):i + 4]))


def test_the_opening_height_is_capped_by_the_work_area_not_nine_tenths_of_it(
        _app, _out_dir):
    """The missing tenth was not spare — it was the bottom of the right pane.

    `_ToolDialogBase` used to open at ``min(hint, 0.9 * available.height())``.
    Measured on the Windows ARM64 VM (B8-39), on a 1032 px work area, that held
    this window **41 px (German) / 25 px (English) shorter than its own
    sizeHint while 75 px of screen sat unused** — and the pixels it gave up
    carry *add another scan to average*, *save a diagnostic image* and *use
    fiducial marks*. Re-measured here with the Dock shown (work area 994 px):
    894 px opened against a 952 px sizeHint in German and Spanish, i.e. 58 px,
    in the same direction. With the work-area cap those three come back:
    Spanish went from 136 px of right pane below the fold to 78, German from
    95 to 37, English from 49 to 7.
    """
    dlg = _make(_app, _out_dir)
    try:
        work = _work_area(dlg, _app)
        cap = dlg._work_area_cap(0)
        chrome = dlg.frameGeometry().height() - dlg.height()
        assert cap == work.height() - max(0, chrome), (
            f"the cap is {cap}px on a {work.height()}px work area with "
            f"{chrome}px of chrome — it is not the work area any more")
        assert cap > int(work.height() * 0.9), (
            f"the cap ({cap}px) is no better than the nine-tenths rule "
            f"({int(work.height() * 0.9)}px) it replaced")
    finally:
        dlg.deleteLater()


def test_a_frame_taller_than_the_work_area_is_brought_down_to_it(_app, _out_dir):
    """The cap cannot know the caption's height before the window is mapped, so
    it over-asks by exactly the caption. This is what takes it back — and it is
    the only reason the cap is allowed to be optimistic."""
    dlg = _make(_app, _out_dir)
    try:
        work = _work_area(dlg, _app)
        dlg.setMinimumHeight(0)
        dlg.resize(dlg.width(), work.height() + 120)
        _app.processEvents()
        assert dlg.frameGeometry().height() > work.height(), (
            "could not make the window taller than the work area, so the "
            "assertion below would be measuring nothing")
        dlg._keep_inside_the_work_area()
        _app.processEvents()
        assert dlg.frameGeometry().height() <= work.height(), (
            f"the frame is still {dlg.frameGeometry().height()}px on a "
            f"{work.height()}px work area")
    finally:
        dlg.deleteLater()


def test_no_tool_dialog_still_sizes_itself_to_a_fraction_of_the_screen():
    """A round fraction of a screen is a number with nothing behind it.

    Read off the source rather than trusted to memory: the rule is that the
    opening height is bounded by what the work area can actually hold, and the
    way it came back last time would be somebody reaching for `* 0.9` again.
    """
    import re as _re
    from ui.dialogs import tools_dialogs
    src = inspect.getsource(tools_dialogs._ToolDialogBase)
    bad = [ln.strip() for ln in src.splitlines()
           if _re.search(r"availableGeometry\(\)[^#]*\*\s*0\.", ln)]
    assert not bad, (
        "the opening height is a fraction of the screen again: " + "; ".join(bad))
