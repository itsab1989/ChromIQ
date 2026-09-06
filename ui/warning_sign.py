"""ChromIQ's own message-box signs, drawn for Light, Dark and Neutral.

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

Resolved through `theme.by_mode`, which files an appearance it does not know
under Dark. That was described here for a while as failing loudly, and it never
did: `by_mode` ends `.get(mode or active_mode(), dark)` and
`warning_colours("chartreuse")` returns Dark's amber in silence — measured in
the beta-8 regression sweep, check J33.

The fallback stays, and is now the deliberate answer rather than an accident.
`warn()` already refuses to be the thing that raises: it falls back to a
parentless box rather than throwing from inside a warning (see B8-33, where a
stricter constructor made three tests fail FROM INSIDE THE WARNING). A sign that
raised on an unfamiliar appearance would take the message it was drawn for down
with it, which is the one outcome worse than the wrong amber. Dark's pairing is
also the safe guess: its mark is near-black on amber, so it stays legible on any
ground. `tests/test_warning_sign.py::test_an_unknown_appearance_lands_on_dark`
pins the behaviour, and a test in that same file now pins that this paragraph
and the code still agree.

The pixmap carries a device pixel ratio, so it is drawn at the screen's real
resolution rather than scaled up from 1x — a warning that looks soft is a
warning that looks like a mistake.
"""
from __future__ import annotations

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QColor, QPainter, QPainterPath, QPen, QPixmap

from ui import neutral_styles, theme
from ui.styles import ACCENT, ACCENT_OK, ACCENT_WARN

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


def warn(
    parent,
    title: str,
    text: str,
    buttons: "QMessageBox.StandardButton | None" = None,
    default: "QMessageBox.StandardButton | None" = None,
) -> "QMessageBox.StandardButton":
    """`QMessageBox.warning` with ChromIQ's sign instead of the platform's.

    Same signature shape and same return as the static call it replaces, and
    the same shape as :func:`ui.widgets.confirm`, which already exists for the
    question mark. Written because the sign above was drawn for three
    appearances and then used in exactly one dialog: every other warning in the
    app still showed the macOS caution triangle with the application badged
    into its corner, at whatever size and hue the OS picked — a different
    visual language from every other mark here, carrying the hue Neutral exists
    to remove.
    """
    from PyQt6.QtWidgets import QMessageBox
    # AS FORGIVING ABOUT `parent` AS THE STATIC CALL IT REPLACED.
    # `QMessageBox.warning(parent, …)` is a static helper; this one CONSTRUCTS a
    # QMessageBox, and a constructor is stricter than a static about what it is
    # given. Measured when the 51 call sites were converted: three suite tests
    # that had happily called these code paths with a stand-in `self` — a
    # `types.SimpleNamespace`, and a `Ti2RelayoutDialog` built through
    # `__new__` — turned into `TypeError: argument 1 has unexpected type
    # 'types.SimpleNamespace'` and `RuntimeError: super-class __init__() ... was
    # never called`, raised from inside the warning itself.
    #
    # Those are test scaffolds, but the rule they exercise is a real one: a
    # warning is what the app reaches for when something has ALREADY gone
    # wrong, and it must not be the thing that raises. A parentless box says
    # the same words.
    try:
        box = QMessageBox(parent)
    except (TypeError, RuntimeError):
        box = QMessageBox()
    box.setWindowTitle(title)
    box.setText(text)
    set_warning_icon(box)
    box.setStandardButtons(buttons if buttons is not None
                           else QMessageBox.StandardButton.Ok)
    if default is not None:
        box.setDefaultButton(default)
    # A LONG BODY MUST NOT TAKE THE BUTTONS OFF THE SCREEN WITH IT.
    # `fit_message_box_buttons` widens a box for its BUTTONS and caps nothing;
    # this caps and clamps it against the work area, widens it for its TEXT, and
    # puts an overflowing body behind Qt's own "Show Details". Called BEFORE the
    # button fit so the details button it may add is fitted with the rest.
    from ui.widgets import (fit_message_box_buttons,
                            keep_message_box_inside_the_work_area)
    keep_message_box_inside_the_work_area(box)
    fit_message_box_buttons(box)
    box.exec()
    return box.standardButton(box.clickedButton())


# ---------------------------------------------------------------------------
# Information and Question
# ---------------------------------------------------------------------------
# Same objection as the triangle, same answer. `Icon.Information` and
# `Icon.Question` are the PLATFORM's marks; on macOS they are the system badges
# at the OS's own hue and size. The question mark in particular was removed from
# this app once already, on Basti's word — `ui.widgets.confirm` exists because
# of it — and removing a sign is not the same as having one.
#
# THE SHAPE CARRIES THE MEANING, NOT THE COLOUR. A warning is a TRIANGLE, which
# is the one shape in this app that means "be careful"; information and a
# question are CIRCLES, which is what every other round badge here already is.
# So the two of them share a shape and differ only by the mark, and neither
# competes with the warning for attention.
#
# The circle is the app's own ACCENT (SPEC_CYAN) rather than a new hue: adding a
# colour to a five-colour spectrum to say "this is a notice" would say it louder
# than a notice deserves. Amber stays the only sign that means careful.
#
# In Neutral all three are NM_ACTION on NM_ON_ACTION, exactly as the warning is.
# That is the appearance's whole rule — it says what a sign means with the shape
# and the words, never with a hue — so the three differ there by shape and mark
# alone, which is the test of whether the shapes were doing the work all along.
_MARK_ON_ACCENT = "#08222a"


def _circle_colours(mode: "str | None" = None) -> "tuple[str, str]":
    """(the circle's fill, the mark cut into it) for this appearance."""
    return theme.by_mode(
        (ACCENT, _MARK_ON_ACCENT),
        (ACCENT, _MARK_ON_ACCENT),
        (neutral_styles.NM_ACTION, neutral_styles.NM_ON_ACTION),
        mode,
    )


#: Information is ChromIQ's GREEN (ACCENT_OK / SPEC_GREEN), asked for by Basti
#: on 2026-09-04. That leaves each sign its own voice: amber says BE CAREFUL,
#: green says HERE IS SOMETHING, and the app's cyan accent says THIS IS WAITING
#: ON YOUR ANSWER. Three of the spectrum's own five, no new hue invented.
#:
#: Neutral is untouched and stays hueless — his words, "neutral colorscheme of
#: course stays neutral". It gives all three signs its one accent pairing, so
#: there the shapes carry the whole meaning, which is that appearance's rule.
_MARK_ON_GREEN = "#08251b"


def information_colours(mode: "str | None" = None) -> "tuple[str, str]":
    """(the disc's fill, the mark cut into it) for this appearance."""
    return theme.by_mode(
        (ACCENT_OK, _MARK_ON_GREEN),
        (ACCENT_OK, _MARK_ON_GREEN),
        (neutral_styles.NM_ACTION, neutral_styles.NM_ON_ACTION),
        mode,
    )


def question_colours(mode: "str | None" = None) -> "tuple[str, str]":
    """(the disc's fill, the mark cut into it) for this appearance.

    A question keeps the app's own ACCENT: it is the one notice that is waiting
    on the user, and the accent is what this app already uses for the thing you
    are meant to act on."""
    return _circle_colours(mode)


def _disc(p: QPainter, s: float, fill: str) -> None:
    """The badge both circle signs sit on, inset like the triangle is."""
    inset = s * 0.06
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(fill))
    p.drawEllipse(QRectF(inset, inset, s - 2 * inset, s - 2 * inset))


def information_pixmap(size: int = 48, mode: "str | None" = None,
                       dpr: float = 2.0) -> QPixmap:
    """The information sign — a dot over a bar, the warning's mark inverted."""
    dpr = max(1.0, float(dpr))
    px = QPixmap(int(round(size * dpr)), int(round(size * dpr)))
    px.setDevicePixelRatio(dpr)
    px.fill(Qt.GlobalColor.transparent)
    fill, mark = information_colours(mode)
    p = QPainter(px)
    try:
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        s = float(size)
        _disc(p, s, fill)
        p.setBrush(QColor(mark))
        w = s * 0.115
        dot = QRectF(s / 2.0 - w / 2.0, s * 0.255, w, w)
        p.drawRoundedRect(dot, w / 2.0, w / 2.0)
        bar = QRectF(s / 2.0 - w / 2.0, s * 0.435, w, s * 0.31)
        p.drawRoundedRect(bar, w / 2.0, w / 2.0)
    finally:
        p.end()
    return px


def question_pixmap(size: int = 48, mode: "str | None" = None,
                    dpr: float = 2.0) -> QPixmap:
    """The question sign — a hook and a dot, STROKED rather than set in type.

    Drawn as geometry for the same reason the triangle is: a glyph would come
    from whatever face the platform hands us, at whatever weight, and would not
    match the rounded finish every other mark in this app has.
    """
    dpr = max(1.0, float(dpr))
    px = QPixmap(int(round(size * dpr)), int(round(size * dpr)))
    px.setDevicePixelRatio(dpr)
    px.fill(Qt.GlobalColor.transparent)
    fill, mark = question_colours(mode)
    p = QPainter(px)
    try:
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        s = float(size)
        _disc(p, s, fill)
        w = s * 0.105                       # stroke weight, as the bar's width
        pen = QPen(QColor(mark), w)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        # the hook: three quarters of a circle, opening at the bottom right,
        # then down into the stem — one path, so the joins are round.
        r = s * 0.135
        cx, cy = s / 2.0, s * 0.365
        hook = QPainterPath()
        hook.arcMoveTo(QRectF(cx - r, cy - r, 2 * r, 2 * r), 200.0)
        hook.arcTo(QRectF(cx - r, cy - r, 2 * r, 2 * r), 200.0, -260.0)
        hook.lineTo(QPointF(cx, s * 0.62))
        p.drawPath(hook)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(mark))
        dot = QRectF(cx - w / 2.0, s * 0.715, w, w)
        p.drawRoundedRect(dot, w / 2.0, w / 2.0)
    finally:
        p.end()
    return px


def _set_pixmap(box, pixmap_fn, mode, size) -> None:
    dpr = 2.0
    try:
        handle = box.window().windowHandle()
        if handle is not None and handle.devicePixelRatio() > 0:
            dpr = float(handle.devicePixelRatio())
    except Exception:            # noqa: BLE001 — a sharper icon, never a crash
        pass
    box.setIconPixmap(pixmap_fn(size, mode, dpr))


def set_information_icon(box, mode: "str | None" = None, size: int = 48) -> None:
    """Give a QMessageBox ChromIQ's information sign, not the platform's."""
    _set_pixmap(box, information_pixmap, mode, size)


def set_question_icon(box, mode: "str | None" = None, size: int = 48) -> None:
    """Give a QMessageBox ChromIQ's question sign, not the platform's."""
    _set_pixmap(box, question_pixmap, mode, size)


def inform(
    parent,
    title: str,
    text: str,
    buttons: "QMessageBox.StandardButton | None" = None,
    default: "QMessageBox.StandardButton | None" = None,
) -> "QMessageBox.StandardButton":
    """`QMessageBox.information` with ChromIQ's sign. Same shape as :func:`warn`."""
    return _boxed(parent, title, text, buttons, default, set_information_icon)


def ask(
    parent,
    title: str,
    text: str,
    buttons: "QMessageBox.StandardButton | None" = None,
    default: "QMessageBox.StandardButton | None" = None,
) -> "QMessageBox.StandardButton":
    """`QMessageBox.question` with ChromIQ's sign. Same shape as :func:`warn`.

    :func:`ui.widgets.confirm` shows no sign at all and stays that way: it is
    the everyday Yes/No, and a badge on every routine confirmation is noise.
    This is for the question that genuinely needs marking as a question.
    """
    return _boxed(parent, title, text, buttons, default, set_question_icon)


def _boxed(parent, title, text, buttons, default, set_icon):
    from PyQt6.QtWidgets import QMessageBox
    # AS FORGIVING ABOUT `parent` AS THE STATIC CALL IT REPLACED.
    # `QMessageBox.warning(parent, …)` is a static helper; this one CONSTRUCTS a
    # QMessageBox, and a constructor is stricter than a static about what it is
    # given. Measured when the 51 call sites were converted: three suite tests
    # that had happily called these code paths with a stand-in `self` — a
    # `types.SimpleNamespace`, and a `Ti2RelayoutDialog` built through
    # `__new__` — turned into `TypeError: argument 1 has unexpected type
    # 'types.SimpleNamespace'` and `RuntimeError: super-class __init__() ... was
    # never called`, raised from inside the warning itself.
    #
    # Those are test scaffolds, but the rule they exercise is a real one: a
    # warning is what the app reaches for when something has ALREADY gone
    # wrong, and it must not be the thing that raises. A parentless box says
    # the same words.
    try:
        box = QMessageBox(parent)
    except (TypeError, RuntimeError):
        box = QMessageBox()
    box.setWindowTitle(title)
    box.setText(text)
    set_icon(box)
    box.setStandardButtons(buttons if buttons is not None
                           else QMessageBox.StandardButton.Ok)
    if default is not None:
        box.setDefaultButton(default)
    # A LONG BODY MUST NOT TAKE THE BUTTONS OFF THE SCREEN WITH IT.
    # `fit_message_box_buttons` widens a box for its BUTTONS and caps nothing;
    # this caps and clamps it against the work area, widens it for its TEXT, and
    # puts an overflowing body behind Qt's own "Show Details". Called BEFORE the
    # button fit so the details button it may add is fitted with the rest.
    from ui.widgets import (fit_message_box_buttons,
                            keep_message_box_inside_the_work_area)
    keep_message_box_inside_the_work_area(box)
    fit_message_box_buttons(box)
    box.exec()
    return box.standardButton(box.clickedButton())
