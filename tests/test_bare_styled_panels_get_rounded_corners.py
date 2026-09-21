"""B8-650: the three bare `QFrame(StyledPanel)` instances stay rounded.

Sebastian photographed square corners on the section frames in the Reference
values window while every other panel in ChromIQ is rounded
(`~/Desktop/ChromIQ-knut-beta29-batch/basti-square-corners-2026-09-20.png`).
The cause: `QFrame.setFrameShape(QFrame.Shape.StyledPanel)` with no
stylesheet, so Fusion draws its native square bevel. `ui/styles.py` has no
app-wide `QFrame` rule at all, and adding one is not the fix: a dozen other
`QFrame` instances in the app are `HLine`/`VLine` dividers, and the instant a
stylesheet rule matches `QFrame`, Qt stops drawing their native sunken bevel
in favour of the stylesheet's box model, which specifies no border of its own
-- every divider in the app would flatten. So each of the three frames opts in
explicitly via `ui.theme.panel_border_qss`, which this test also exercises.

**This asserts on PAINTED PIXELS, not stylesheet text.** A frame that carries
"border-radius" in a stylesheet string a test never renders proves nothing a
user can see; grabbing the widget and reading its corner is the same check
`tests/test_tools_popup_corners_stay_round.py` uses for the same shape of bug.

The signal: for ANY frame with a border, the pixel at the exact corner (0,0)
lies inside a rounded corner's clipped-away arc for every legitimate radius,
so it shows whatever is behind the frame -- never the border colour a pixel
at the middle of an edge shows. Measured with the fix reverted (`git stash`,
this file's own history): corner and edge colours are IDENTICAL, because an
unstyled Fusion `StyledPanel` paints its bevel unbroken into every corner.
With the fix, they differ in both Light and Dark.
"""
from __future__ import annotations

import pytest
from PyQt6.QtWidgets import QFrame

from ui.styles import WinButtonLayoutStyle
from ui.theme import APPEARANCE_DARK, APPEARANCE_LIGHT, apply_appearance


def _styled_panels(widget):
    return [f for f in widget.findChildren(QFrame)
            if f.frameShape() == QFrame.Shape.StyledPanel]


def _corner_and_edge(frame) -> tuple[str, str]:
    """The frame's own painted corner colour vs. its edge colour.

    Grabbed alone (not the whole window), so the coordinates are the frame's
    own -- (0, 0) is always its corner, whatever dialog it lives in.
    """
    if frame.width() < 8 or frame.height() < 8:
        frame.resize(max(frame.width(), 40), max(frame.height(), 40))
    pix = frame.grab()
    dpr = pix.devicePixelRatio() or 1.0
    img = pix.toImage()
    w = frame.width()
    corner = img.pixelColor(0, 0)
    edge = img.pixelColor(int(w * dpr // 2), 0)
    return corner.name(), edge.name()


def _reference_values_frames(qapp):
    from ui.dialogs.reference_values_dialog import ReferenceValuesDialog
    dlg = ReferenceValuesDialog(None)
    dlg.resize(900, dlg.sizeHint().height())
    dlg.show()
    qapp.processEvents()
    frames = _styled_panels(dlg)
    assert frames, "no StyledPanel frame found in the Reference values window"
    return dlg, frames


def _preflight_frames(qapp):
    from ui.dialogs.preflight_dialog import PreflightDialog
    dlg = PreflightDialog([("Printer", "X"), ("Media size", "A4")], [], 1, None)
    dlg.show()
    qapp.processEvents()
    frames = _styled_panels(dlg)
    assert frames, "no StyledPanel frame found in the Preflight dialog"
    return dlg, frames


def _add_patches_frames(qapp):
    from ui.dialogs.ti2_relayout_dialog import _AddPatchesDialog
    dlg = _AddPatchesDialog(None, None)
    dlg.resize(680, dlg.sizeHint().height())
    dlg.show()
    qapp.processEvents()
    frames = _styled_panels(dlg)
    assert frames, "no StyledPanel frame found in the Add patches dialog"
    return dlg, frames


_WINDOWS = {
    "reference_values": _reference_values_frames,
    "preflight": _preflight_frames,
    "add_patches_swatch": _add_patches_frames,
}


@pytest.mark.parametrize("mode", [APPEARANCE_LIGHT, APPEARANCE_DARK])
@pytest.mark.parametrize("window", list(_WINDOWS))
def test_every_bare_styled_panel_is_rounded_not_square(qapp, window, mode):
    apply_appearance(qapp, None, mode)
    dlg, frames = _WINDOWS[window](qapp)
    try:
        square = []
        for f in frames:
            corner, edge = _corner_and_edge(f)
            if corner == edge:
                square.append((f.objectName() or repr(f), corner, edge))
        assert not square, (
            f"{window} ({mode}): {square} -- the frame's own corner pixel "
            "matches its edge pixel, meaning the border/bevel was painted "
            "unbroken into the corner (square), not clipped by a radius")
    finally:
        dlg.close()


def test_the_app_still_has_no_blanket_qframe_rule(qapp):
    """Pins the chosen approach: per-widget opt-in, not a global `QFrame` rule.

    `ui/styles.py`'s docstring for `panel_border_qss` explains why -- roughly
    a dozen `HLine`/`VLine` dividers across the app rely on Fusion's native
    sunken-bevel painting, which a matching `QFrame` stylesheet rule replaces
    app-wide the instant it exists. If this ever starts failing because
    somebody added `QFrame { ... }` to an appearance stylesheet, that change
    needs the wider look CLAUDE.md asked for (every `QFrame` it would touch),
    not a quiet edit here.
    """
    from ui import light_styles, neutral_styles, styles
    for mod in (styles, light_styles, neutral_styles):
        src = mod.__dict__.get("APP_STYLESHEET") or mod.__dict__.get(
            "LIGHT_STYLESHEET") or mod.__dict__.get("NEUTRAL_STYLESHEET")
        assert src is not None
        assert "QFrame {" not in src and "QFrame{" not in src, (
            f"{mod.__name__} gained a blanket QFrame rule -- this would "
            "flatten every HLine/VLine divider in the app; see "
            "ui.theme.panel_border_qss's docstring")
