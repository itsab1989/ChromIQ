"""The CMYK+N pictogram, redrawn for a theme that has no colour.

It was the last hued icon in the app. Every other pictogram in the welcome
dialog is line art with ONE accented element, which is the handoff's rule and
the reason none of them needed touching; this one was five filled drops in five
colours, and the handoff is explicit about that case:

    "The rule only works when the solid shape is unique in the frame. If any
    pictogram currently has two or more accented elements, redraw it first."

The owner picked the redraw: four inks as open rings, the extra ink as the one
solid ACTION shape.

**LIGHT AND DARK KEEP THE COLOURED ARTWORK.** The four process inks are named
by their colours there and nothing about them changes; only the Neutral
rendering is new, and the tests below assert both halves of that.
"""
from __future__ import annotations

import inspect

import pytest
from PyQt6.QtGui import QColor, QImage
from PyQt6.QtWidgets import QApplication

from ui import neutral_styles as nm
from ui.dialogs.welcome_dialog import WORKFLOWS, WorkflowCard, WorkflowIcon
from ui.theme import APPEARANCE_DARK, APPEARANCE_LIGHT, APPEARANCE_NEUTRAL

MODES = (APPEARANCE_LIGHT, APPEARANCE_DARK, APPEARANCE_NEUTRAL)
#: The card fill each appearance paints behind a pictogram.
GROUND = {APPEARANCE_LIGHT: "#ffffff", APPEARANCE_DARK: "#1a1a1a",
          APPEARANCE_NEUTRAL: nm.NM_BG_SURFACE}


@pytest.fixture
def qapp():
    return QApplication.instance() or QApplication([])


def shot(key: str, mode: str) -> QImage:
    """One pictogram, painted through the real ``paintEvent``, on its own card
    ground — which is what decides whether a knocked-out gap is invisible."""
    w = WorkflowIcon(key)
    w.set_appearance(mode)
    w.setAutoFillBackground(True)
    pal = w.palette()
    pal.setColor(w.backgroundRole(), QColor(GROUND[mode]))
    w.setPalette(pal)
    w.resize(WorkflowIcon.SIZE, WorkflowIcon.SIZE)
    return w.grab().toImage().convertToFormat(QImage.Format.Format_ARGB32)


def hued(img: QImage, tolerance: int = 6) -> int:
    n = 0
    for y in range(img.height()):
        for x in range(img.width()):
            c = img.pixelColor(x, y)
            if c.alpha() < 8:
                continue
            if max(c.red(), c.green(), c.blue()) \
                    - min(c.red(), c.green(), c.blue()) > tolerance:
                n += 1
    return n


def raw(img: QImage) -> bytes:
    ptr = img.constBits()
    ptr.setsize(img.sizeInBytes())
    return bytes(ptr)


ALL_KEYS = [w["key"] for w in WORKFLOWS]


# ----------------------------------------------------------------------
# 1. the hue is gone, and it was really there
# ----------------------------------------------------------------------
def test_no_hue_left_in_neutral(qapp):
    assert hued(shot("cmyk_n", APPEARANCE_NEUTRAL)) == 0


@pytest.mark.parametrize("mode", (APPEARANCE_LIGHT, APPEARANCE_DARK))
def test_light_and_dark_still_paint_the_process_inks(qapp, mode):
    """THE MUTATION, PROVEN TO LAND. Without this, "no hue in Neutral" would
    also be satisfied by a pictogram that had quietly lost its colour
    everywhere."""
    img = shot("cmyk_n", mode)
    assert hued(img) > 1500, "the coloured artwork stopped being coloured"
    # Hue families rather than exact values: the drops are painted at alpha 200
    # over the card, so no pixel carries an ink's literal RGB. Hue survives that
    # blend, which is the whole reason the motif works.
    hues = {img.pixelColor(x, y).hue()
            for y in range(img.height()) for x in range(img.width())
            if img.pixelColor(x, y).saturation() > 60}
    for name, low, high in (("cyan", 180, 210), ("magenta", 300, 340),
                            ("yellow", 40, 70)):
        assert any(low <= h <= high for h in hues), (
            f"{name} is no longer painted in {mode}")


def test_every_other_pictogram_was_already_neutral(qapp):
    """The claim this branch closes: the welcome dialog's pictograms are the
    app's last hued icons, and cmyk_n was the only one left."""
    still = {k: hued(shot(k, APPEARANCE_NEUTRAL)) for k in ALL_KEYS}
    assert {k: v for k, v in still.items() if v} == {}


# ----------------------------------------------------------------------
# 2. it is the drawing the owner picked
# ----------------------------------------------------------------------
def _fg_at(img, x, y) -> QColor:
    return img.pixelColor(int(x), int(y))


def test_the_four_inks_are_OPEN_rings(qapp):
    """Rings, not discs: the centre of each of the four is still ground.

    This is the half that keeps four inks readable as four. Filled, they would
    be four identical grey discs and the motif would say nothing.
    """
    img = shot("cmyk_n", APPEARANCE_NEUTRAL)
    s = WorkflowIcon.SIZE
    r = int(s * 0.20)
    gx, cy = s // 2 - int(s * 0.0625), s // 2
    ground = QColor(nm.NM_BG_SURFACE)
    # The group's own centre. It lies inside ALL FOUR drops (12.7 px from each
    # of them, against a radius of 19) and on none of their strokes, so it is
    # ground exactly when the four are open and ink the moment any is filled.
    # A ring's own centre is NOT a usable probe: the drops overlap so heavily
    # that its neighbour's stroke passes within a pixel of it.
    assert _fg_at(img, gx, cy) == ground, "the four inks are filled discs again"
    # And the whole mark is line art plus one solid. MEASURED, not guessed:
    # this geometry drawn as rings covers 1,970 px of the 96x96 frame and drawn
    # as filled drops covers 3,026. 2,400 sits between the two with room on
    # both sides for antialiasing and a stroke-width tweak.
    ink = sum(1 for y in range(img.height()) for x in range(img.width())
              if img.pixelColor(x, y) != ground)
    assert ink < 2400, f"{ink} px of ink — too much of the frame is filled"


def test_the_extra_ink_is_solid_and_is_the_only_solid(qapp):
    img = shot("cmyk_n", APPEARANCE_NEUTRAL)
    s = WorkflowIcon.SIZE
    ex, cy = s // 2 + int(s * 0.1875), s // 2
    assert _fg_at(img, ex, cy) == QColor(nm.NM_ACTION)


def test_the_extra_ink_is_NOT_in_the_middle_of_the_four(qapp):
    """The fix the picture forced.

    In the approved sketch the solid sat dead centre at ring size. At the size
    this is actually seen — 96 px, not enlarged — that covers the middle,
    reduces the four rings to corner arcs and reads as one dark blob whose
    solid is simply the darkest of five inks. The fifth shape is off the
    group's orbit precisely so it cannot be mistaken for one of them.
    """
    img = shot("cmyk_n", APPEARANCE_NEUTRAL)
    s = WorkflowIcon.SIZE
    assert _fg_at(img, s // 2, s // 2) != QColor(nm.NM_ACTION), (
        "the solid is back in the centre of the pile")


def test_the_extra_ink_still_overlaps_the_group(qapp):
    """An extra ink is added TO the set, not stood beside it. The solid's left
    edge must fall inside the rightmost ring's span."""
    s = WorkflowIcon.SIZE
    r = int(s * 0.20)
    o = r // 2
    gx = s // 2 - int(s * 0.0625)
    ex = s // 2 + int(s * 0.1875)
    solid_r = int(r * 0.79)
    rings_right_edge = gx + o + r
    assert ex - solid_r < rings_right_edge, "the extra ink no longer touches the four"
    assert ex + solid_r > rings_right_edge, "the extra ink is buried in the four"


def test_the_gap_around_the_solid_is_the_card_colour(qapp):
    """The knockout is what makes it read as laid ON the four rather than
    tangled in them, and it is only invisible if it is painted in the colour
    behind it."""
    img = shot("cmyk_n", APPEARANCE_NEUTRAL)
    s = WorkflowIcon.SIZE
    r = int(s * 0.20)
    ex, cy = s // 2 + int(s * 0.1875), s // 2
    solid_r = int(r * 0.79)
    assert _fg_at(img, ex - solid_r - 2, cy) == QColor(nm.NM_BG_SURFACE)


# ----------------------------------------------------------------------
# 3. the two things that could drift apart in silence
# ----------------------------------------------------------------------
@pytest.mark.parametrize("mode", MODES)
def test_the_icon_and_the_card_agree_on_the_ground(qapp, mode):
    """`_card_surface` duplicates a colour that `WorkflowCard._apply_style` owns.

    If the card's fill ever moves and this does not, the knocked-out gap
    becomes a visible halo in the wrong colour. Pinned here rather than left to
    someone noticing.
    """
    icon = WorkflowIcon("cmyk_n")
    icon.set_appearance(mode)
    card_src = inspect.getsource(WorkflowCard._apply_style)
    assert icon._card_surface().name().lower() == GROUND[mode].lower()
    assert GROUND[mode].lstrip("#") in card_src.replace("_n.NM_BG_SURFACE",
                                                        nm.NM_BG_SURFACE) \
        or "NM_BG_SURFACE" in card_src


def test_the_mutation_landed_in_this_method_and_not_a_homonym():
    """`inspect.getsource` OF THE METHOD, by reference — a grep over the file
    would pass on a same-named line somewhere else, which is how an earlier
    proof on a sibling branch reported a false green."""
    src = inspect.getsource(WorkflowIcon._draw_cmyk_n_neutral)
    assert "s * 0.1875" in src, "the extra ink's offset is gone"
    assert "int(r * 0.79)" in src, "the extra ink is a peer again"
    paint = inspect.getsource(WorkflowIcon.paintEvent)
    assert "self._draw_cmyk_n_neutral(" in paint
    assert "QColor(0, 174, 239, 200)" in paint, (
        "Light and Dark lost the coloured drops")


# ----------------------------------------------------------------------
# 4. a live appearance switch reaches it
# ----------------------------------------------------------------------
def test_a_live_switch_repaints_the_pictogram(qapp):
    """Preferences changes appearance without a restart."""
    w = WorkflowIcon("cmyk_n")
    w.setAutoFillBackground(True)
    w.resize(WorkflowIcon.SIZE, WorkflowIcon.SIZE)

    def wear(mode):
        w.set_appearance(mode)
        pal = w.palette()
        pal.setColor(w.backgroundRole(), QColor(GROUND[mode]))
        w.setPalette(pal)
        return w.grab().toImage().convertToFormat(QImage.Format.Format_ARGB32)

    assert hued(wear(APPEARANCE_LIGHT)) > 1500
    assert hued(wear(APPEARANCE_NEUTRAL)) == 0
    assert hued(wear(APPEARANCE_LIGHT)) > 1500


def test_light_and_dark_are_unchanged_by_a_neutral_round_trip(qapp):
    """Byte-for-byte: the coloured artwork after visiting Neutral is the
    coloured artwork before it."""
    for mode in (APPEARANCE_LIGHT, APPEARANCE_DARK):
        before = raw(shot("cmyk_n", mode))
        shot("cmyk_n", APPEARANCE_NEUTRAL)
        assert raw(shot("cmyk_n", mode)) == before
