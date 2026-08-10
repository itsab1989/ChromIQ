"""Pin a dialog's minimum height to its layout floor so resizing never overlaps.

Word-wrapped ``QLabel``s report a tiny ``minimumSize`` height (they can wrap
down to a single word), so a layout's own ``minimumSize`` under-reports the
space its rows actually need at the dialog's real width — which is what lets a
window be dragged short enough for rows to slide over each other.

:func:`pin_min_height` mirrors the floor logic in
:class:`ui.dialogs.tools_dialogs._ToolDialogBase` (which keeps its own copy for
historical reasons) so the *standalone* tool dialogs get the same guarantee:

  1. pin each wrapping label's height to its true ``heightForWidth`` at the
     content width, then
  2. ``layout.activate()`` and read ``layout.minimumSize()`` — the floor below
     which widgets can no longer shrink — and pin the dialog's minimum height to
     it (never below it, so rows can't overlap), and
  3. open at the natural fit, clamped to 90 % of the screen height.

Call it once from ``showEvent`` and again after revealing/hiding optional rows.
"""
from __future__ import annotations

from PyQt6.QtCore import QMargins
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtWidgets import QDialog, QLabel


def pin_min_height(
    dialog: QDialog,
    *,
    min_width: int = 0,
    min_height: int = 0,
    wrap_labels: tuple[QLabel, ...] | list[QLabel] = (),
    inner_margins: QMargins | None = None,
    resize_width: bool = False,
) -> int:
    """Pin ``dialog``'s minimum height to its no-overlap layout floor.

    ``wrap_labels`` are word-wrapping labels whose height must be pinned to
    their ``heightForWidth`` at the content width before the floor is read;
    ``inner_margins`` is the side inset those labels sit inside (so the
    available width is computed correctly). When ``resize_width`` is True the
    dialog is also widened to its natural width (use on first show); otherwise
    only the height is adjusted (use on dynamic refits).

    ``min_height`` is a platform-independent hard floor: the dialog is never
    pinned below it even when font metrics make the layout's own floor come out
    a few pixels shorter (e.g. Windows vs macOS).

    Returns the height the dialog was resized to.
    """
    layout = dialog.layout()
    if layout is None:
        return dialog.height()

    target_w = max(min_width, layout.sizeHint().width())
    if inner_margins is not None and wrap_labels:
        avail = target_w - inner_margins.left() - inner_margins.right()
        for lbl in wrap_labels:
            lbl.setMinimumHeight(max(0, lbl.heightForWidth(avail)))

    # Recompute the floor *after* the labels' heights are pinned, or
    # minimumSize() still reflects the un-wrapped (one-line) height.
    layout.activate()
    hint = layout.sizeHint()
    floor = layout.minimumSize()
    floor_h = max(floor.height(), min_height)

    screen = dialog.screen() or QGuiApplication.primaryScreen()
    cap_h = (int(screen.availableGeometry().height() * 0.9)
             if screen is not None else hint.height())

    # Never below the floor (overlap-free); only the opening size is capped to
    # the screen so the floor itself stays overlap-free even on small screens.
    dialog.setMinimumHeight(floor_h)
    open_h = max(floor_h, min(hint.height(), cap_h))
    if resize_width:
        dialog.resize(target_w, open_h)
    else:
        dialog.resize(dialog.width(), open_h)

    # resize() never moves a window, and Qt's initial placement is not
    # guaranteed to fit a size chosen only afterwards — the Measurement info
    # window opened at its default position with its bottom off-screen
    # (Sebastian, 2026-08-10). Nudge the frame back inside the available
    # area; a window that already fits stays exactly where it is, so dynamic
    # refits never yank the dialog around under the user.
    if screen is not None:
        area = screen.availableGeometry()
        frame = dialog.frameGeometry()
        x = max(area.left(), min(frame.x(), area.right() - frame.width() + 1))
        y = max(area.top(), min(frame.y(), area.bottom() - frame.height() + 1))
        if (x, y) != (frame.x(), frame.y()):
            dialog.move(x, y)
    return open_h
