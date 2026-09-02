"""The Tools speech bubble keeps its rounded corners at every scroll position.

The owner, 2026-09-02: *"the tools buttons speechbubble overlay has rounded
corners but depending on how far its content is scrolled some corners shine
through. don't know if only in neutral colorscheme or others as well."*

It was all three. The two scroll fades are full-width `fillRect`s 18 px tall
against the top and bottom edges, drawn AFTER the row clip is restored, and
`CORNER_R` is 10 - so they painted panel colour into the corner arcs. The top
fade is only drawn once you have scrolled down and the bottom one only while
there is more below, which is why WHICH corners looked wrong changed as he
scrolled.
"""
from __future__ import annotations

import pytest

from ui.theme import APPEARANCE_DARK, APPEARANCE_LIGHT, APPEARANCE_NEUTRAL


def _popup(qapp, mode):
    from ui.tools_popup import ToolsPopup
    pop = ToolsPopup(None)
    if hasattr(pop, "set_appearance"):
        pop.set_appearance(mode)
    pop.resize(320, 300)
    pop.show()
    qapp.processEvents()
    if not pop.is_scrollable():
        pytest.skip("this build's tool list fits without scrolling")
    return pop


def _corner_alphas(pop, qapp):
    """Alpha at the four points just inside the panel's bounding box.

    Those points lie OUTSIDE the rounded edge, so the bubble itself may not
    paint there. They are not required to be EMPTY: the soft shadow is the
    bubble path translated down 3 px, so it legitimately reaches the bottom
    two, measured at alpha 10. The fade that caused the fault arrives at
    alpha 235, so the two are not close and the threshold below separates
    them without pretending the shadow is a bug.
    """
    pop.update()
    qapp.processEvents()
    px = pop.grab()
    d = px.devicePixelRatio() or 1.0
    img = px.toImage()
    r = pop._panel_rect()
    pts = {
        "top-left":     (r.left() + 1,  r.top() + 1),
        "top-right":    (r.right() - 1, r.top() + 1),
        "bottom-left":  (r.left() + 1,  r.bottom() - 1),
        "bottom-right": (r.right() - 1, r.bottom() - 1),
    }
    return {k: img.pixelColor(int(x * d), int(y * d)).alpha()
            for k, (x, y) in pts.items()}


@pytest.mark.parametrize("mode", [APPEARANCE_LIGHT, APPEARANCE_DARK,
                                  APPEARANCE_NEUTRAL])
@pytest.mark.parametrize("where", ["top", "bottom"])
def test_no_corner_is_filled_at_either_end_of_the_scroll(qapp, mode, where):
    """Both ends, because each end draws a different fade.

    Scrolled to the bottom the TOP fade is on; scrolled to the top the BOTTOM
    one is. Testing one position would have passed with half the bug in place.
    """
    pop = _popup(qapp, mode)
    pop._scroll = pop._max_scroll() if where == "bottom" else 0
    SHADOW_CEILING = 60          # shadow measures 10; the fade measures 235
    filled = {k: a for k, a in _corner_alphas(pop, qapp).items()
              if a > SHADOW_CEILING}
    assert not filled, (
        f"{mode}, scrolled to the {where}: {sorted(filled)} painted into the "
        f"rounded corner (alpha {filled})")


def test_the_indicators_are_clipped_to_the_bubble_not_its_bounding_box(qapp):
    """The mechanism, named, so a future edit cannot quietly undo it.

    A pixel test alone would go green again the moment somebody made the
    fades shorter than the corner radius for an unrelated reason.
    """
    import inspect

    from ui.tools_popup import ToolsPopup
    src = inspect.getsource(ToolsPopup.paintEvent)
    after_restore = src.split("p.restore()", 1)[1]
    assert "setClipPath" in after_restore, (
        "the scroll indicators are drawn with no rounded clip in force")
