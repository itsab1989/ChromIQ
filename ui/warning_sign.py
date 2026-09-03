"""ChromIQ's own warning sign, drawn for Light, Dark and Neutral.

Basti, 2026-09-03, on the two new windows in Tools ▸ Read single patches:
*"i don't know if some of those dialogs are new. if they are and you want to
use a warning sign for them — could you create one in our regular style for all
colorschemes — light dark neutral?"*

`QMessageBox.Icon.Warning` is the PLATFORM's sign, not ours. On macOS it is the
system caution triangle with the application badged into its corner, at whatever
size and hue the OS picks; it belongs to a different visual language than every
other mark in this app, and it carries a hue that Neutral exists to remove.

So the sign is drawn here, from the tokens every other accent already uses:

* **Light and Dark** — the app's amber, `ui.styles.ACCENT_WARN`, with the mark
  cut in a near-black that sits on the amber and therefore reads the same on a
  white ground and on a near-black one. One drawing serves both, which is what
  makes them agree.
* **Neutral** — `neutral_styles.NM_ACTION` and `NM_ON_ACTION`, the appearance's
  single accent and its one light-on-dark pairing. Neutral says "warning" with
  the shape and the words, never with a hue (`ui/theme.py`, `ink_for`).

Resolved through `theme.by_mode`, so a fourth appearance fails loudly here
instead of quietly inheriting Dark's amber.

The pixmap carries a device pixel ratio, so it is drawn at the screen's real
resolution rather than scaled up from 1x — a warning that looks soft is a
warning that looks like a mistake.
"""
from __future__ import annotations

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QColor, QPainter, QPainterPath, QPen, QPixmap

from ui import neutral_styles, theme
from ui.styles import ACCENT_WARN

#: The mark inside the triangle. Near-black rather than the window ground:
#: the triangle is what the mark sits on, so one value is right in every
#: appearance and the sign cannot go invisible on an unexpected background.
_MARK_ON_AMBER = "#1c1400"


def warning_colours(mode: "str | None" = None) -> "tuple[str, str]":
    """(the sign's fill, the mark cut into it) for this appearance."""
    return theme.by_mode(
        (ACCENT_WARN, _MARK_ON_AMBER),
        (ACCENT_WARN, _MARK_ON_AMBER),
        (neutral_styles.NM_ACTION, neutral_styles.NM_ON_ACTION),
        mode,
    )


def warning_pixmap(size: int = 48, mode: "str | None" = None,
                   dpr: float = 2.0) -> QPixmap:
    """The warning sign as a transparent pixmap `size` points square."""
    dpr = max(1.0, float(dpr))
    px = QPixmap(int(round(size * dpr)), int(round(size * dpr)))
    px.setDevicePixelRatio(dpr)
    px.fill(Qt.GlobalColor.transparent)

    fill, mark = warning_colours(mode)
    p = QPainter(px)
    try:
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        s = float(size)
        # A triangle with ROUNDED corners, which is how every other drawn mark
        # in this app finishes an edge. Made by stroking the outline with a
        # round join and filling the same path, rather than by three arcs:
        # the join does the rounding exactly and survives any size.
        r = s * 0.10                       # corner radius, via the pen width
        inset = r / 2.0 + s * 0.06
        top = QPointF(s / 2.0, inset)
        left = QPointF(inset, s - inset)
        right = QPointF(s - inset, s - inset)
        tri = QPainterPath(top)
        tri.lineTo(right)
        tri.lineTo(left)
        tri.closeSubpath()
        pen = QPen(QColor(fill), r)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        p.setPen(pen)
        p.setBrush(QColor(fill))
        p.drawPath(tri)

        # The bar and the dot, as rounded rectangles on the triangle's axis.
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(mark))
        w = s * 0.115
        bar = QRectF(s / 2.0 - w / 2.0, s * 0.355, w, s * 0.275)
        p.drawRoundedRect(bar, w / 2.0, w / 2.0)
        dot = QRectF(s / 2.0 - w / 2.0, s * 0.695, w, w)
        p.drawRoundedRect(dot, w / 2.0, w / 2.0)
    finally:
        p.end()
    return px


def set_warning_icon(box, mode: "str | None" = None, size: int = 48) -> None:
    """Give a QMessageBox ChromIQ's warning sign instead of the platform's.

    `setIconPixmap` REPLACES `setIcon`, so the standard triangle never appears
    even for a moment. Called instead of `setIcon(QMessageBox.Icon.Warning)`,
    never as well as it.
    """
    dpr = 2.0
    try:
        handle = box.window().windowHandle()
        if handle is not None and handle.devicePixelRatio() > 0:
            dpr = float(handle.devicePixelRatio())
    except Exception:            # noqa: BLE001 — a sharper icon, never a crash
        pass
    box.setIconPixmap(warning_pixmap(size, mode, dpr))
