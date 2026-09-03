"""The measurement overlays - the two the owner named, and the two beside them.

*"in the measure tab for the new neutral colorscheme i would like to have the
arrow stripindicator for strip reading mode and patch highlighter in patch by
patch mode during measurement colorless - neutral."*

Both of those are painted into the preview's canvas, and both exist only once a
strip or a patch has been ARMED - which happens when chartread reports a stripe
or the chart-reading engine reports a patch, i.e. with an instrument in
somebody's hand. Every hued-pixel census the app has run rendered a preview
with no overlay on it at all, which is why five sweeps called the app
colourless while a mint-green arrow was waiting for an instrument.

Two more are drawn in the same green at the same moment and were not named: the
strip hover outline and the patch hover outline, both of which appear under the
pointer while a measurement is running (click-to-jump is armed by the same
code path that arms the ring).

WHAT IS NOT FLATTENED, AND WHY. The alarm red of the aperture warning is left
alone deliberately. It is the only place a patch too small for the instrument
is ever visible, and the code comment beside it records that it was given a
colour of its own precisely because it *"sat invisible under a ring of its own
colour"*. There the hue is the message; taking it out would delete the warning
rather than de-hue it.

THE INSTRUMENT HERE IS A DIFFERENCE, NOT A CENSUS.
`scripts/find_non_neutral_pixels.py` cannot be pointed at this widget: it is
showing a PRINTED CHART, thousands of deliberately coloured patches that the
theme must never touch, and against that the overlay is a rounding error. So
each test grabs the same real preview twice - overlay armed and overlay cleared
- and looks only at the pixels that CHANGED. Those pixels are the overlay and
nothing else; the chart underneath is identical in both frames and cancels.
"""
from __future__ import annotations

import inspect
import time

import pytest
from PyQt6.QtCore import QRect
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QApplication

from ui import neutral_styles as N
from ui import tiff_preview as TP
from ui.styles import SPEC_GREEN

LIGHT, DARK, NEUTRAL = "light", "dark", "neutral"
COLOURED = (LIGHT, DARK)

#: The page the overlays are drawn over. Mid grey, so a green mark and a black
#: one are both plainly a change against it and neither can hide.
PAGE_RGB = (140, 140, 140)


def _preview(qtbot, tmp_path, mode):
    """A real TiffPreview, in `mode`, showing a real page, on screen.

    The appearance is applied BEFORE the page is loaded, the way the app does
    it: `apply_appearance` runs before the window is built, and a component
    that is themed after it has painted keeps what it was born in.
    """
    from PIL import Image
    from ui.tiff_preview import TiffPreview

    p = TiffPreview()
    qtbot.addWidget(p)
    p.set_appearance(mode)
    tif = tmp_path / f"page-{mode}.tif"
    if not tif.exists():
        Image.new("RGB", (600, 600), PAGE_RGB).save(tif)
    p.resize(460, 460)
    p.load_tiff([tif])
    p.show()
    qtbot.waitExposed(p)
    QApplication.processEvents()
    return p


def _settle(p):
    """Let the widget's own debounced repaint actually land.

    `_schedule_refresh` starts an 80 ms single-shot timer, so a grab taken
    straight after arming is of the PREVIOUS frame - the two frames come out
    identical and every count is a vacuous zero. `test_the_overlay_actually_
    draws_something` is the guard that turned this from a green suite into a
    red one when it was first written that way.
    """
    deadline = time.monotonic() + 2.0
    while p._refresh_timer.isActive() and time.monotonic() < deadline:
        QApplication.processEvents()
        time.sleep(0.01)
    for _ in range(3):
        QApplication.processEvents()


def _frame(p):
    _settle(p)
    return p._img_label.grab().toImage()


def _drawn(before, after):
    """{hex: count} over exactly the pixels the overlay changed."""
    from collections import Counter
    assert before.size() == after.size(), "the two frames must be comparable"
    out: Counter = Counter()
    for y in range(after.height()):
        for x in range(after.width()):
            a = before.pixelColor(x, y)
            b = after.pixelColor(x, y)
            if a != b:
                out[b.name()] += 1
    return out


def _hued(counts, tolerance=6):
    """The share of drawn pixels carrying a hue.

    A halo pixel is white blended with whatever is underneath, so on a coloured
    chart the halo itself registers as a hue through no fault of the theme.
    Over the flat grey page used here nothing blends into a hue, so any hue in
    the result was painted deliberately.
    """
    hits = 0
    for hexv, n in counts.items():
        c = QColor(hexv)
        if max(c.red(), c.green(), c.blue()) - min(c.red(), c.green(), c.blue()) > tolerance:
            hits += n
    return hits


def _count(image, value):
    """How many pixels in a whole frame are EXACTLY `value`."""
    want = QColor(value)
    return sum(1 for y in range(image.height()) for x in range(image.width())
               if image.pixelColor(x, y) == want)


def _exactly(counts, value):
    """How many drawn pixels are EXACTLY `value`.

    Not "the commonest colour": the ring and the aiming circle are casings -
    a 6 px white halo carrying a 2 px accent stroke - so the halo outnumbers
    the accent three to one and the commonest drawn colour is the halo in
    every appearance. What matters is that the accent stroke itself is the
    right value, and that it is there in quantity rather than as a stray
    antialiased pixel.
    """
    want = QColor(value)
    return sum(n for hexv, n in counts.items() if QColor(hexv) == want)


#: A stroke, not a rounding artefact. The thinnest of these overlays (the patch
#: hover outline at 2.5 px) draws ~1,000 px on this page; 100 is well clear of
#: antialiasing and well under every real figure.
ENOUGH = 100


# ======================================================================
# the four decoration overlays, armed the way the app arms them
# ======================================================================

def _arm_strip_arrow(p, bidirectional=False):
    p.set_no_swipe(False)
    p.set_stripe_rects([QRect(120, 160, 90, 300),
                        QRect(240, 160, 90, 300)], "base")
    p.set_bidirectional(bidirectional)
    p.highlight_stripe(0)


def _clear_strip_arrow(p):
    p.set_bidirectional(False)
    p.highlight_stripe(-1)


def _arm_patch_ring(p):
    p._current = 0
    p.highlight_patch(0, QRect(220, 220, 120, 120))


def _clear_patch_ring(p):
    p.highlight_patch(-1, None)


def _arm_aim_body(p):
    _arm_patch_ring(p)
    p.set_aim_overlay(True, 0.0, 260.0)


def _clear_aim_body(p):
    p.set_aim_overlay(False)
    _clear_patch_ring(p)


def _arm_strip_hover(p):
    p.set_no_swipe(False)
    p.set_stripe_rects([QRect(120, 160, 90, 300)], "base")
    p.set_stripe_click_enabled(True, {})
    p._hover_stripe = 0
    p._schedule_refresh()


def _clear_strip_hover(p):
    p._hover_stripe = -1
    p.set_stripe_click_enabled(False)


def _arm_patch_hover(p):
    p._current = 0
    p.set_patch_click_enabled(True, [{"A1": QRect(220, 220, 120, 120)}])
    p._hover_patch_loc = "A1"
    p._schedule_refresh()


def _clear_patch_hover(p):
    p._hover_patch_loc = ""
    p.set_patch_click_enabled(False)


#: name, arm, clear, and the green it is drawn in in Light and Dark.
DECORATION = [
    ("strip arrow", _arm_strip_arrow, _clear_strip_arrow, SPEC_GREEN),
    ("strip arrow, both ways",
     lambda p: _arm_strip_arrow(p, True), _clear_strip_arrow, SPEC_GREEN),
    ("patch highlighter ring", _arm_patch_ring, _clear_patch_ring, "#1f8f6b"),
    ("aiming body circle", _arm_aim_body, _clear_aim_body, "#1f8f6b"),
    ("strip hover outline", _arm_strip_hover, _clear_strip_hover, SPEC_GREEN),
    ("patch hover outline", _arm_patch_hover, _clear_patch_hover, SPEC_GREEN),
]
IDS = [d[0] for d in DECORATION]


def _census(qtbot, tmp_path, mode, arm, clear):
    p = _preview(qtbot, tmp_path, mode)
    clear(p)
    before = _frame(p)
    arm(p)
    after = _frame(p)
    return _drawn(before, after)


@pytest.mark.parametrize("name,arm,clear,green", DECORATION, ids=IDS)
def test_the_overlay_actually_draws_something(qtbot, tmp_path, name, arm, clear, green):
    """THE GUARD AGAINST A VACUOUS PASS.

    Every test below asks "and none of it is a hue". A harness that draws
    nothing answers that perfectly and proves nothing - the failure mode that
    has shipped green here twice. This one fails instead.
    """
    counts = _census(qtbot, tmp_path, NEUTRAL, arm, clear)
    assert sum(counts.values()) > 50, f"{name} drew nothing at all"


@pytest.mark.parametrize("name,arm,clear,green", DECORATION, ids=IDS)
def test_no_hue_survives_in_neutral(qtbot, tmp_path, name, arm, clear, green):
    counts = _census(qtbot, tmp_path, NEUTRAL, arm, clear)
    assert _hued(counts) == 0, (
        f"{name} painted {_hued(counts)} hued px in Neutral: "
        f"{counts.most_common(4)}")


@pytest.mark.parametrize("name,arm,clear,green", DECORATION, ids=IDS)
def test_neutral_paints_the_one_accent(qtbot, tmp_path, name, arm, clear, green):
    """Not merely "a grey" - the theme's single ACTION value, which is what
    every other accent in Neutral collapses to."""
    counts = _census(qtbot, tmp_path, NEUTRAL, arm, clear)
    assert _exactly(counts, N.NM_ACTION) >= ENOUGH, (
        f"{name} painted only {_exactly(counts, N.NM_ACTION)} px of NM_ACTION: "
        f"{counts.most_common(4)}")


@pytest.mark.parametrize("mode", COLOURED)
@pytest.mark.parametrize("name,arm,clear,green", DECORATION, ids=IDS)
def test_light_and_dark_still_paint_their_green(qtbot, tmp_path, mode,
                                                name, arm, clear, green):
    """THE HALF THAT MUST NOT MOVE. `accent_for` hands its argument straight
    back outside Neutral, so these two appearances keep the exact literal they
    had before the door was put in front of them."""
    counts = _census(qtbot, tmp_path, mode, arm, clear)
    assert _exactly(counts, green) >= ENOUGH, (
        f"{name} in {mode} painted only {_exactly(counts, green)} px of "
        f"{green}: {counts.most_common(4)}")
    assert _exactly(counts, N.NM_ACTION) == 0, (
        f"{name} in {mode} painted the NEUTRAL accent")


# ======================================================================
# the door itself
# ======================================================================

def test_the_door_hands_light_and_dark_the_value_untouched(qtbot):
    p = TP.TiffPreview()
    qtbot.addWidget(p)
    for mode, expected in ((LIGHT, SPEC_GREEN), (DARK, SPEC_GREEN)):
        p.set_appearance(mode)
        assert p._overlay_accent(p._OVERLAY_ARROW) == QColor(expected)
        assert p._overlay_accent(p._OVERLAY_RING) == QColor("#1f8f6b")
    p.set_appearance(NEUTRAL)
    assert p._overlay_accent(p._OVERLAY_ARROW) == QColor(N.NM_ACTION)
    assert p._overlay_accent(p._OVERLAY_RING) == QColor(N.NM_ACTION)


def test_every_overlay_accent_goes_through_the_door():
    """No site may hand a literal green straight to a pen or a fill again.

    Read from the source, so a new overlay that reintroduces one is caught even
    though no test would ever have armed it - which is exactly how these four
    survived five sweeps.
    """
    src = inspect.getsource(TP)
    for literal in ('QColor("#56d6a5")', 'QColor("#1f8f6b")'):
        assert literal not in src, f"{literal} is painted without the theme door"
    # …and the two values still exist, once each, as the named constants the
    # door is a door for.
    assert src.count('_OVERLAY_ARROW = SPEC_GREEN') == 1
    assert src.count('_OVERLAY_RING  = "#1f8f6b"') == 1


# ======================================================================
# what is deliberately NOT flattened
# ======================================================================

def test_the_aperture_alarm_keeps_its_red_in_neutral(qtbot, tmp_path):
    """A DECISION, NOT AN OVERSIGHT.

    The 4 mm aperture circle appears only when the opening does not fit inside
    the patch - the one place ChromIQ ever says a chart's patches are too small
    for the instrument, because nothing refuses such a chart. The comment
    beside it records that it was moved out of the accent and given an alarm
    colour because it *"sat invisible under a ring of its own colour"*. Making
    it the accent again in Neutral would restore precisely that.
    """
    p = _preview(qtbot, tmp_path, NEUTRAL)
    p._current = 0
    p.highlight_patch(0, QRect(220, 220, 40, 40))
    p.set_aim_overlay(False)
    before = _frame(p)
    p.set_aim_overlay(True, 70.0, 260.0)      # aperture wider than the patch
    after = _frame(p)
    counts = _drawn(before, after)
    red = QColor("#ff2b2b")
    hits = sum(n for hexv, n in counts.items()
               if abs(QColor(hexv).red() - red.red()) < 45
               and QColor(hexv).green() < 100 and QColor(hexv).blue() < 100)
    assert hits > 0, "the aperture alarm lost its colour in Neutral"


# ======================================================================
# the switch must reach a canvas that is already painted
# ======================================================================

def test_an_appearance_switch_repaints_the_overlay_already_on_screen(qtbot, tmp_path):
    """Preferences can be opened DURING a measurement.

    The overlays are painted into a pixmap and handed to a label. Nothing in
    `set_appearance` used to touch that pixmap, so switching to Neutral with a
    strip armed left the previous appearance's green arrow on screen until the
    next strip came up - which on the last strip of a chart is for ever.
    """
    p = _preview(qtbot, tmp_path, DARK)
    _arm_strip_arrow(p)
    dark = _frame(p)
    # the arrow really is green before the switch, or this proves nothing
    green_before = _count(dark, SPEC_GREEN)
    assert green_before >= ENOUGH, "no green arrow to begin with"

    p.set_appearance(NEUTRAL)
    after = _frame(p)
    # THE ASSERTION HAS TO BE ABOUT THE ARROW, not about "something changed".
    # `_apply_mode_styles` restyles the label's own background and border, so a
    # switch moves pixels around the sheet whether or not the canvas is
    # repainted - and a test that only counted changed pixels stayed green with
    # the repaint removed. Measured: it did.
    assert _count(after, SPEC_GREEN) == 0, (
        f"{_count(after, SPEC_GREEN)} px of the previous appearance's green "
        f"arrow are still on screen after switching to Neutral")
    assert _count(after, N.NM_ACTION) >= ENOUGH, (
        "the arrow was not repainted in the neutral accent")
