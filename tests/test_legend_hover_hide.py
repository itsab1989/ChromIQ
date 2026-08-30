"""The legend chip gets out of the way when you point at it.

Basti: *"the legend that shows which part of the patch is measured vs expected
sometimes is over the patches. can we make it so it disappears when the mouse
hovers over it so the user can see what is underneath?"*

The chip is meant to sit in the bottom paper margin, and `tiff_preview.py`'s own
comment concedes that on a chart whose patches reach the edge it lands on the
last row instead — "the lesser evil", against a chip clipped off the page. So
overlapping is a known state, and getting out of the way is the remedy.

THE TRAP THESE PIN. The instant the chip is hidden the pointer is over the
PATCHES, not the chip. A hit test against a rectangle computed only when the
chip is drawn would then say "not hovering", bring it straight back, and
flicker. The rectangle is therefore computed on EVERY paint and remembered.

Real `TiffPreview`, real paint, a real image loaded through `load_tiff`.
"""
import pytest
from PIL import Image
from PyQt6.QtCore import QPoint, QRect
from PyQt6.QtGui import QColor

CHIP = QColor(20, 20, 20)          # the chip's background, alpha 190 over paper


@pytest.fixture
def preview(qtbot, tmp_path):
    from ui.tiff_preview import TiffPreview
    p = TiffPreview()
    qtbot.addWidget(p)
    p.resize(700, 700)
    tif = tmp_path / "sheet.tif"
    Image.new("RGB", (600, 600), (245, 245, 245)).save(tif)
    p.load_tiff([tif])
    items = [(QRect(60 + 90 * c, 60 + 90 * r, 80, 80),
              QColor("#3050ff"), QColor("#20c060"), False)
             for r in range(6) for c in range(6)]
    p.set_patch_overlay(0, items, replace_page=True)
    p.show()
    qtbot.waitExposed(p)
    from PyQt6.QtWidgets import QApplication
    QApplication.processEvents()
    return p


def _chip_pixels(p) -> int:
    """Dark pixels INSIDE the chip's own rectangle.

    Scanning the whole widget counts its dark surround too — 2,000 pixels of it
    here, enough to hide the chip's disappearance behind background noise. The
    rectangle is mapped from the image label to the widget, which is the same
    translation the hit test does.
    """
    from PyQt6.QtWidgets import QApplication
    QApplication.processEvents()
    r = p._legend_rect
    if r is None:
        return 0
    label = getattr(p, "_img_label", None)
    off = label.mapTo(p, QPoint(0, 0)) if label is not None else QPoint(0, 0)
    box = r.translated(off).adjusted(-2, -2, 2, 2)
    im = p.grab().toImage()
    n = 0
    for y in range(max(0, box.top()), min(im.height(), box.bottom() + 1)):
        for x in range(max(0, box.left()), min(im.width(), box.right() + 1)):
            c = im.pixelColor(x, y)
            if abs(c.red() - 60) < 34 and abs(c.green() - 60) < 34 \
                    and abs(c.blue() - 60) < 34:
                n += 1
    return n


def _point_at_chip(p, qtbot) -> None:
    """Drive the REAL state machine and let the fade finish.

    The chip fades rather than switching (Basti: *"can be a really fast one
    just not this completely instant on off"*), so a test that sets a flag and
    repaints once measures a chip caught mid-fade. This waits for the animation
    the user actually sees to complete.
    """
    p._apply_legend_pointer(p._legend_rect.center())
    qtbot.waitUntil(lambda: p._legend_opacity < 0.02, timeout=2000)


def _split_pixels(p) -> int:
    """The measured half of the patches. The vacuity guard: if this is zero the
    canvas is empty and 'the chip is gone' means nothing."""
    from PyQt6.QtWidgets import QApplication
    QApplication.processEvents()
    im = p.grab().toImage()
    return sum(1 for y in range(im.height()) for x in range(im.width())
               if im.pixelColor(x, y).green() > 140
               and im.pixelColor(x, y).red() < 120)


def test_the_chip_is_drawn_at_all(preview):
    assert _chip_pixels(preview) > 200, "no chip on screen; the rest proves nothing"


def test_pointing_at_it_takes_it_away_and_leaves_the_patches(preview, qtbot):
    assert preview._legend_rect is not None, "the chip's rectangle was not recorded"
    before = _chip_pixels(preview)
    _point_at_chip(preview, qtbot)
    after = _chip_pixels(preview)
    assert after < before / 4, f"the chip is still there ({after} vs {before})"
    # …and the canvas is NOT simply blank, which would pass the line above.
    assert _split_pixels(preview) > 500, "nothing was drawn; vacuous"


def test_it_comes_back_when_the_pointer_leaves(preview, qtbot):
    before = _chip_pixels(preview)
    _point_at_chip(preview, qtbot)
    preview._forget_legend_pointer()
    qtbot.waitUntil(lambda: preview._legend_opacity > 0.99, timeout=2000)
    assert _chip_pixels(preview) == pytest.approx(before, rel=0.15)


def test_the_rectangle_is_refreshed_even_on_the_paint_that_hides_it(preview, qtbot):
    """The anti-flicker property, stated so that only the real implementation
    passes.

    A first version of this test merely asserted the rectangle was still there
    after a hidden paint — which a broken implementation also satisfies, because
    it leaves the STALE rectangle behind rather than clearing it. Proven by
    mutation: storing the rect only when the chip is visible passed that test.

    What actually distinguishes them is a chip whose placement CHANGES while it
    is hidden. The three wordings differ in width by 70 %, so switching the view
    mode moves and resizes the chip. If the rectangle is only recorded on
    visible paints, the pointer is now being tested against a rectangle that no
    longer describes anything on screen.
    """
    from PyQt6.QtWidgets import QApplication
    _point_at_chip(preview, qtbot)
    narrow = QRect(preview._legend_rect)

    preview.set_overlay_mode("measured")      # a much wider wording
    QApplication.processEvents()
    assert preview._legend_rect is not None
    assert preview._legend_rect.width() > narrow.width(), (
        "the chip was re-placed while hidden, but the remembered rectangle "
        "still describes the old one — the pointer is being tested against a "
        "chip that is not there")


def test_pointing_somewhere_else_leaves_it_alone(preview):
    before = _chip_pixels(preview)
    far = QPoint(preview._legend_rect.x(), max(0, preview._legend_rect.y() - 300))
    preview._legend_pointer = far
    assert preview._legend_is_hidden() is False
    preview._repaint_label()
    assert _chip_pixels(preview) == pytest.approx(before, rel=0.15)


# -- the two faults found while designing this ------------------------------

def test_clear_drops_the_previous_charts_patches(preview, tmp_path):
    """`clear()` reset the hover numbers and NOT the painted colours, so after
    loading a new chart the previous chart's measured patches went on painting
    over it."""
    assert preview._patch_overlay, "harness broken: nothing to clear"
    preview.clear()
    assert preview._patch_overlay == {}, (
        "the previous chart's readings would paint over the next one")


def test_the_chip_is_placed_below_the_patches_without_strip_geometry(preview):
    """`_stripe_rects` can be empty while patches are plainly on screen. The
    placement used to consider only strip geometry, so `patch_bottom` stayed at
    the TOP of the sheet and the chip was clamped there — over the column
    letters and the first row."""
    assert not preview._stripe_rects, "harness broken: this needs empty geometry"
    r = preview._legend_rect
    assert r is not None
    assert r.y() > preview.height() * 0.5, (
        f"the chip sits at y={r.y()} of {preview.height()} — at the top, over "
        "the patches, which is the fault this covers")


# -- the fade itself --------------------------------------------------------

def test_it_fades_rather_than_blinking(preview, qtbot):
    """Basti, after using the instant version: *"could we do a fade? can be a
    really fast one just not this completely instant on off"*.

    Proven by catching the chip PART WAY: an instant switch is never partly
    drawn, so a sample strictly between the two states can only come from an
    animation. Sampled through the real animation, not by reading a constant.
    """
    seen = []
    assert preview._legend_opacity == 1.0
    preview._apply_legend_pointer(preview._legend_rect.center())
    from PyQt6.QtWidgets import QApplication
    import time
    end = time.monotonic() + 2.0
    while time.monotonic() < end and preview._legend_opacity > 0.02:
        seen.append(preview._legend_opacity)
        QApplication.processEvents()
        time.sleep(0.005)
    partial = [v for v in seen if 0.05 < v < 0.95]
    assert partial, f"the chip switched rather than faded; samples: {seen[:8]}"
    assert preview._legend_opacity < 0.02, "the fade never finished"


def test_the_fade_is_quick(preview, qtbot):
    """A control getting out of the way, not an effect.

    Rewritten: it used to assert the CONSTANT against a constant, so a two-
    second fade would have passed it as long as nobody edited the number. It
    now times the real animation.
    """
    import time
    assert 60 <= preview.LEGEND_FADE_MS <= 200, "the declared duration drifted"
    began = time.monotonic()
    preview._apply_legend_pointer(preview._legend_rect.center())
    qtbot.waitUntil(lambda: preview._legend_opacity < 0.02, timeout=3000)
    took = (time.monotonic() - began) * 1000
    assert took < 400, f"the fade actually took {took:.0f} ms"


def test_turning_back_mid_fade_does_not_snap(preview, qtbot):
    """Sweeping the pointer on and off quickly must turn round from where the
    fade had got to, not jump to the far end and start again."""
    preview._apply_legend_pointer(preview._legend_rect.center())
    # Wait for the animation's FIRST tick — a single processEvents can run
    # before the timer has fired, and then there is nothing to interrupt and
    # the test would be measuring its own impatience.
    qtbot.waitUntil(lambda: preview._legend_opacity < 1.0, timeout=2000)
    mid = preview._legend_opacity
    assert 0.0 < mid < 1.0, f"caught at {mid}, not mid-fade"
    preview._forget_legend_pointer()          # reverse before it finishes
    from PyQt6.QtWidgets import QApplication
    QApplication.processEvents()
    # IT MUST CONTINUE FROM WHERE IT WAS, not restart from the far end. The
    # only assertion here used to be `<= 1.0`, which a snapping implementation
    # satisfies trivially — so it proved nothing at all.
    assert preview._legend_opacity < 0.999, (
        "the reversal jumped straight to fully visible instead of easing back")
    assert preview._legend_opacity >= mid - 0.05, (
        f"the reversal restarted from below where it had got to "
        f"({preview._legend_opacity:.3f} against {mid:.3f})")
    qtbot.waitUntil(lambda: preview._legend_opacity > 0.99, timeout=2000)


# -- the three faults the verification round found --------------------------

def test_flicking_off_and_straight_back_on_still_hides_it(preview, qtbot):
    """F1. Leave the chip and return before the show-fade finishes.

    The re-hide used to be dropped: `_start_legend_fade` returned early when the
    opacity was already near its target, WITHOUT stopping the show fade that was
    running the other way — so that fade carried on to fully drawn while the
    state said hidden, and no further movement could produce a transition. The
    chip sat under the pointer and wiggling on it did not recover it.
    """
    centre = preview._legend_rect.center()
    preview._apply_legend_pointer(centre)
    qtbot.waitUntil(lambda: preview._legend_opacity < 0.02, timeout=2000)
    # off the chip, and back on before the show fade can finish
    preview._apply_legend_pointer(QPoint(centre.x(), max(0, centre.y() - 400)))
    preview._apply_legend_pointer(centre)
    # WAIT PAST THE WHOLE FADE BEFORE JUDGING. A first version asserted
    # immediately, when the opacity was still 0.0 from the previous hide — so it
    # passed while the dropped show-fade was quietly running underneath, and the
    # mutation went uncaught. What matters is where it ENDS UP.
    import time
    from PyQt6.QtWidgets import QApplication
    end = time.monotonic() + (preview.LEGEND_FADE_MS * 3) / 1000.0
    while time.monotonic() < end:
        QApplication.processEvents()
        time.sleep(0.005)
    assert preview._legend_hidden is True
    assert preview._legend_opacity < 0.05, (
        f"the chip faded back in to {preview._legend_opacity:.2f} while the "
        "pointer sat on it")
    assert _chip_pixels(preview) < 60, "the chip is drawn under the pointer"


def test_resizing_under_a_still_pointer_brings_it_back(preview, qtbot):
    """F2. The chip moves; the pointer does not. Nothing used to re-decide, so
    the legend vanished and stayed gone until the mouse left the widget."""
    _point_at_chip(preview, qtbot)
    preview.resize(preview.width() + 160, preview.height() + 160)
    qtbot.waitUntil(lambda: preview._legend_opacity > 0.99, timeout=2000)
    assert preview._legend_hidden is False
    assert _chip_pixels(preview) > 200, "the legend never came back"


def test_a_new_chart_gets_its_legend_back(preview, qtbot, tmp_path):
    """F3. Clearing while pointing at the chip carried the hover state into the
    next chart, which then opened with no legend at all."""
    _point_at_chip(preview, qtbot)
    preview.clear()
    assert preview._legend_hidden is False
    assert preview._legend_opacity == 1.0
    assert preview._legend_pointer is None


# -- cover for what the mutation audit found untested -----------------------

def test_the_pointer_is_mapped_through_the_image_label(preview):
    """The commit's headline subtlety, and it had no test. A raw widget
    position tested against a canvas rectangle is off by the label offset."""
    label = getattr(preview, "_img_label", None)
    assert label is not None
    off = label.mapFrom(preview, QPoint(0, 0))
    inside = preview._legend_rect.center()
    preview._legend_pointer = inside
    assert preview._legend_is_hidden() is True
    # the SAME point expressed in widget coordinates must NOT be treated as a hit
    # unless the offset happens to be zero
    if off != QPoint(0, 0):
        preview._legend_pointer = inside - off
        assert preview._legend_is_hidden() is False, (
            "widget and label coordinates are being confused")


def test_hiding_the_widget_restores_the_chip(preview, qtbot):
    """`hideEvent` had no cover. A widget hidden under the pointer gets no
    leaveEvent, so without it the chip stays hidden when it comes back."""
    _point_at_chip(preview, qtbot)
    preview.hide()
    assert preview._legend_hidden is False
    assert preview._legend_opacity == 1.0


def test_a_narrow_pane_elides_rather_than_clipping(preview, qtbot):
    """The elision had no cover either. The widest wording used to run past the
    paper edge and be cut off mid-word."""
    from PyQt6.QtWidgets import QApplication
    preview.set_overlay_mode("measured")
    preview.resize(300, 700)
    QApplication.processEvents()
    r = preview._legend_rect
    assert r is not None
    assert r.right() <= preview.width() + 2, (
        f"the chip runs to x={r.right()} in a {preview.width()} px pane")


# ── AN ADMITTED GAP ────────────────────────────────────────────────────────
#
# F1 -- `_start_legend_fade` returning early WITHOUT stopping the fade running
# the other way -- has NO regression test here, and I could not write one.
#
# Two attempts failed, and both passed with the fault deliberately re-applied
# (mutation verified to land, bytecode cleared, randomisation off):
#
#   * the scenario version, flicking off the chip and straight back on: by the
#     time it can assert, the state has settled to the same place either way;
#   * the invariant version, asserting the countermanded animation is no longer
#     running towards the old target: it is not running in either build, so the
#     assertion is satisfied without the fix.
#
# A test that passes under the fault is worse than no test: it reads as cover
# and is not. So this says so instead. The fix is a strict improvement and the
# behaviour was confirmed on screen in the beta-3 gate round (report 49), but
# nothing here would stop it coming back — if you touch `_start_legend_fade`,
# check by hand: point at the chip, move off it and straight back on, and it
# must stay hidden.
#
# UPDATE (beta-3 final review): a discriminating test now exists below —
# `test_a_countermanding_hide_stops_the_running_show_fade`. Proven both ways:
# with the fault re-applied (early return moved back above the stop, mutation
# verified in the diff, bytecode cleared) it fails on the synchronous
# assertion; on the fixed code it passes, five runs. The paragraph above is
# kept because its diagnosis is right: END-state assertions cannot see this
# fault. The new test looks at the moment the re-hide call RETURNS instead.


# ── F1, caught at last ─────────────────────────────────────────────────────
#
# The two deleted attempts (see the note above) both judged the END state, and
# the event loop had settled it to the same place either way by the time they
# could look. The discriminating moment is SYNCHRONOUS: the instant the
# re-hide call returns, the countermanded show fade must already be stopped —
# under the fault the early return leaves it Running towards 1.0, and nothing
# has had a chance to settle anything yet. Two rules from the gate reviews
# apply: the setup self-verifies (a show fade PROVEN to be running towards
# 1.0, so an off-point that never left the chip fails loudly instead of
# passing vacuously — the shipped scenario test above has exactly that hole),
# and the assertion runs before a single event is processed.
def test_a_countermanding_hide_stops_the_running_show_fade(preview, qtbot):
    """F1. The re-hide arrives while the show fade has only just begun."""
    import time
    from PyQt6.QtCore import QAbstractAnimation
    from PyQt6.QtWidgets import QApplication
    Running = QAbstractAnimation.State.Running

    centre = preview._legend_rect.center()
    preview._apply_legend_pointer(centre)              # hide the chip…
    qtbot.waitUntil(lambda: (preview._legend_fade is not None
                             and preview._legend_fade.state() != Running
                             and preview._legend_opacity < 0.01),
                    timeout=2000)                      # …completely: opacity 0

    # Leave the chip: a show fade starts from ~0.0 — which is still inside the
    # "close enough to 0" window the faulty early return tested against.
    off = preview._legend_rect.bottomRight() + QPoint(200, 200)
    preview._apply_legend_pointer(off)
    anim = preview._legend_fade
    assert anim is not None and anim.state() == Running \
        and float(anim.endValue()) == 1.0, (
        "setup failed: leaving the chip did not start a show fade — the "
        "off-point never left the chip, so this test would prove nothing")

    # Flick straight back on. SYNCHRONOUS assertion, before any event runs:
    preview._apply_legend_pointer(centre)
    assert not (anim.state() == Running and float(anim.endValue()) == 1.0), (
        "the re-hide returned without stopping the show fade running the "
        "other way — the chip will fade in under the pointer and stick")

    # And the behavioural half: pump past the whole fade; it must END hidden.
    end = time.monotonic() + preview.LEGEND_FADE_MS * 3 / 1000.0
    while time.monotonic() < end:
        QApplication.processEvents()
        time.sleep(0.005)
    assert preview._legend_hidden is True
    assert preview._legend_opacity < 0.05, (
        f"the chip faded back in to {preview._legend_opacity:.2f} while the "
        "pointer sat on it")
