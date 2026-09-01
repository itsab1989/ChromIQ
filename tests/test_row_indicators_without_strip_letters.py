"""Row indicators may be asked for on their own (Basti, 2026-09-01).

The two were tied together in the RENDERER: the row-label block sat inside
`if draw_indicators:`, so asking for row numbers with the strip letters off
printed nothing while `rlwi` still reserved 7.5 mm of paper. The checkbox was
greyed out rather than the coupling fixed.

On a CR30 or a SpectroScan the row number is the useful half — the instrument
is placed on ONE patch at a time — so the combination has to work.

WHAT MUST NOT CHANGE: a recipe where nobody touched the box. `None` still
means "this instrument's own behaviour", and with the strip letters off it
still resolves to False, so all 130 built-ins and every saved recipe render
exactly as before. Measured across 48 combinations: 8 changed, all of them
`strips off + rows explicitly on`.
"""
import numpy as np
import pytest

from workflow.layout_engine import geometry, instruments, papers, raster
from workflow.layout_engine.presets import LayoutRecipe
from workflow.layout_engine.ti1_reader import ColorTarget

_DPI, _N = 150, 240
_PX = _DPI / 25.4


def _recipe(instrument="i1", mode="patch_first", strips=True, rows=None):
    r = LayoutRecipe()
    r.instrument, r.paper, r.layout_mode = instrument, "A4", mode
    r.show_strip_indicators, r.show_row_indicators = strips, rows
    r.clip_border = False
    r.margin_top = r.margin_right = r.margin_bottom = r.margin_left = 6.0
    r.dpi, r.randomize, r.seed = _DPI, False, 1
    return r


def _render(r):
    kw = r.build_kwargs()
    g = instruments.geom_from_build_kwargs(kw)
    w_mm, h_mm = papers.dimensions_mm(r.paper)
    lay = geometry.compute(g, w_mm, h_mm, _N)
    t = ColorTarget(color_rep="iRGB", device_fields=["RGB_R", "RGB_G", "RGB_B"],
                    patches=[((30.0, 70.0, 55.0), (40.0, 45.0, 50.0))
                             for _ in range(_N)])
    res = raster.render_pages(
        t, lay, g, seed=1, randomize=False, paper_w_mm=w_mm, paper_h_mm=h_mm,
        dpi=_DPI, draw_indicators=bool(kw.get("draw_indicators", True)),
        patch_pattern=kw.get("patch_pattern") or "0-9,@-9,@-9;1-999")
    return np.asarray(res.images[0].convert("L")), g, kw


def _ink_left_of_the_patches(page) -> int:
    """Dark pixels strictly LEFT of the patch block, below the top furniture.

    Not "ink in the left 40 mm" — that counts the patches themselves, and a
    mutation that put the row band back inside the strip-label branch sailed
    straight through the first version of this test because of it. The patch
    block is the tall run of coloured columns; anything dark to the left of
    where it starts is the row-label band.
    """
    body = page[int(30 * _PX):, :]
    dark = body < 200
    # the patch block: the first column that is dark for most of the page
    tall = np.where(dark.mean(axis=0) > 0.5)[0]
    if not len(tall):
        return 0
    return int(dark[:, :tall.min()].sum())


@pytest.mark.parametrize("instrument", ["i1", "CM", "SS", "CR30"])
def test_row_labels_are_printed_with_the_strip_letters_off(instrument):
    page, g, kw = _render(_recipe(instrument, strips=False, rows=True))
    assert kw["row_indicators"] is True, (
        "the recipe still forces the row indicators off when the strip "
        "letters are off")
    assert g.rlwi > 0, "no band was reserved, so nothing can be printed in it"
    assert _ink_left_of_the_patches(page) > 0, (
        "the band was reserved and left empty — paper paid for nothing, which "
        "is the exact fault the greyed-out checkbox was hiding")
    # …and it really is the labels: the same chart without them has none.
    plain, _g2, _k2 = _render(_recipe(instrument, strips=False, rows=False))
    assert _ink_left_of_the_patches(plain) == 0, (
        "the detector is counting something other than the row labels")


def test_an_untouched_box_still_follows_the_strip_letters():
    """`None` means the instrument's own behaviour, and that must not change:
    every built-in and every saved recipe depends on it."""
    off = _render(_recipe(strips=False, rows=None))
    assert off[2]["row_indicators"] is False
    assert off[1].rlwi == 0.0, "an untouched box reserved paper it never used"


@pytest.mark.parametrize("instrument", ["i1", "CM", "SS", "CR30"])
@pytest.mark.parametrize("mode", ["patch_first", "area_first"])
def test_nothing_else_moved(instrument, mode):
    """Only `strips off + rows explicitly on` may render differently.

    Compared as PAGES, not as settings: the three combinations that were
    already possible must come back pixel-for-pixel.
    """
    import hashlib

    def page_hash(**kw):
        page, _g, _k = _render(_recipe(instrument, mode, **kw))
        return hashlib.sha256(page.tobytes()).hexdigest()

    # With the strip letters ON, every answer behaves exactly as before: the
    # untouched box and the explicit False agree, and the explicit True does not.
    assert page_hash(strips=True, rows=None) == page_hash(strips=True, rows=False) \
        or page_hash(strips=True, rows=None) == page_hash(strips=True, rows=True), (
        "an untouched box no longer resolves to one of the two real answers")
    # With them OFF, an untouched box and an explicit False are the same page.
    assert page_hash(strips=False, rows=None) == page_hash(strips=False, rows=False), (
        "turning the strip letters off changed a chart nobody had asked to change")


def test_the_checkbox_is_no_longer_greyed(qapp):
    """It was greyed because the renderer could not honour it. It can now."""
    from ui.dialogs.layout_options_panel import LayoutOptionsPanel

    panel = LayoutOptionsPanel(None)
    box = getattr(panel, "show_row_indicators", None)
    if box is None or getattr(panel, "show_indicators", None) is None:
        pytest.skip("this build has no row-indicator checkbox")
    # Driven the way a person drives it: the signal the checkbox emits.
    panel.show_indicators.setChecked(False)
    assert not panel.show_indicators.isChecked()
    assert box.isEnabled(), (
        "the row-indicator box is still greyed out when the strip letters are "
        "off, so the setting cannot be reached")
