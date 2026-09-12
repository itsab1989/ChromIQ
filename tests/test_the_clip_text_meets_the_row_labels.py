"""On the LEFT the clip text meets the ROW LABELS before it meets the patches.

Knut, #182, 2026-09-12, in the edited post:

    "If clip-border text starts overlapping with the row labels (if enabled),
    the warning shall occur too, because the row labels are left of the patch
    area edges and any clip-border text that does not have space enough to fit
    between the clip text-edge distance setting and the patch area left edge or
    the row labels to its left, will overflow and overlap towards the row label
    or the left edge of the patch area (left margin). This situation must be
    caught."

**WHAT IS ACTUALLY TO THE LEFT, IN ORDER**, measured on his own run 2 through
the real window with a 12 mm left band (`scripts/drive_182_sheet_text_fit.py`,
step F5):

| | mm from the page edge | what sets it |
|---|---|---|
| the clip content starts | 2.40 | `min(Clip, a fifth of the band)`, a LIMIT |
| the band's inner edge | 12.00 | "Clip border width" |
| the clip text reaches | 14.25 | the reserve plus what the lines take |
| the row labels' floor | 12.00 | `max(Clip, the band, the instrument's furniture)` |
| the label band's left edge | 13.00 | `floor + 1`, the RESERVATION (§R2) |
| **the leftmost label ink** | **17.22** | the band's right edge less the widest number actually drawn |
| the label band ends | 22.43 | `floor + rlwi` |
| the patch area starts | 22.43 | the left margin, raised to hold the labels |

So the labels sit inside the band and the patch area is beyond it: an overflow
of a few millimetres crosses the labels and may never come near a patch.

**THE RESERVATION IS NOT THE LABEL, and predicting from it warns about blank
paper.** `raster.row_label_band_mm` sizes `rlwi` for the widest label 1 to 99
at the PROVISIONAL geometry's size, deliberately, so on the chart measured here
it reserves 9.43 mm for 3.17 mm of ink. `geometry.row_label_area_mm` measures
the label when it is handed the build kwargs, and the difference is 4.7 mm.

**WHICH CONTROLS MOVE THAT 17.22 mm**, measured over the whole range of each:

* a wider **left margin**, 12 mm to 45 mm: 17.22 mm every time. It is spent
  between the labels and the patches;
* the **clip-border width**: moves it one for one, and shortens the overflow;
* **"Clip"**: moves it one for one ABOVE the band's width, nothing below it;
* the row-indicator **Size**: moves it too, and **the wrong way round**. 4 pt
  puts the ink at 13.86 mm and 28 pt at 18.94, so a SMALLER label sits CLOSER
  to the clip band and collides sooner.

That last line is why the warning does not offer a smaller row-indicator size:
a user following it would make the collision worse.
"""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np                                        # noqa: E402
import pytest                                             # noqa: E402

from workflow import text_edge_fit as tef                 # noqa: E402
from workflow.layout_engine import geometry, instruments, raster  # noqa: E402
from workflow.layout_engine.presets import LayoutRecipe   # noqa: E402
from workflow.layout_engine.ti1_reader import ColorTarget  # noqa: E402

_DEV = (50.0, 50.0, 50.0)
_XYZ = (18.0, 19.0, 21.0)


def _recipe(band_mm: float, lines: int = 4, rows: bool = True,
            clip_mm: float = 4.0, size_pt: float = 0.0) -> LayoutRecipe:
    r = LayoutRecipe()
    r.instrument, r.paper, r.layout_mode = "CM", "A4", "area_first"
    r.clip_border, r.clip_border_width_mm = True, band_mm
    r.clip_side, r.clip_content_mode = "left", "text"
    r.clip_text = "\n".join(f"clip text line {i}" for i in range(1, lines + 1))
    r.clip_text_size_mm = size_pt * 25.4 / 72.0 if size_pt else 0.0
    r.text_edge_clip_mm = clip_mm
    r.show_row_indicators, r.show_strip_indicators = rows, False
    r.helper_markers = False
    r.margin_left = band_mm
    r.margin_top = r.margin_bottom = 10.0
    r.randomize, r.seed_fixed, r.seed = False, True, 5
    return r


def _geom(r):
    return instruments.geom_from_build_kwargs(r.build_kwargs())


# ------------------------------------------------- 1. what is to the left
def _area(r):
    """Where the labels REALLY are: measured, not the reservation."""
    kw = r.build_kwargs()
    return geometry.row_label_area_mm(instruments.geom_from_build_kwargs(kw), kw)


def test_the_labels_sit_inside_the_band_and_short_of_the_patches():
    r = _recipe(12.0)
    g = _geom(r)
    area = _area(r)
    assert area is not None, "this chart has no row labels"
    zone = g.lbord + g.border
    assert area[0] > zone, (
        f"the labels start at {area[0]:.2f} mm, inside the {zone:.2f} mm band")
    assert area[1] <= float(g.margin_l) + 0.001, (
        "the label band reaches past the patch area's edge")


def test_the_reservation_is_wider_than_the_label_and_saying_so_matters():
    """`rlwi` is sized for the worst case; predicting from it warns early.

    Without the build kwargs `row_label_area_mm` can only answer with the
    band's own left edge, and that is several millimetres out from the ink.
    """
    r = _recipe(12.0)
    g = _geom(r)
    reserved = geometry.row_label_area_mm(g)
    measured = _area(r)
    assert reserved is not None and measured is not None
    assert measured[0] > reserved[0] + 2.0, (
        f"the reservation says {reserved[0]:.2f} mm and the measurement "
        f"{measured[0]:.2f}; if they agree this distinction is pointless")


def test_row_labels_off_means_no_label_area_at_all():
    assert _area(_recipe(12.0, rows=False)) is None


@pytest.mark.parametrize("size_pt", [4.0, 6.0, 10.0, 14.0, 20.0, 28.0])
def test_a_smaller_row_indicator_moves_the_labels_TOWARD_the_clip_band(size_pt):
    """The remedy the warning must NOT offer, and why.

    "Set a smaller Size under Row indicators" reads like a way to make room.
    It is the opposite: a smaller number sits closer to the band, because the
    labels are right-aligned against the band's inner edge and the band shrinks
    faster than the number does.
    """
    r = _recipe(12.0)
    r.indicator_size_mm = size_pt * 25.4 / 72.0
    small = _area(r)
    r2 = _recipe(12.0)
    r2.indicator_size_mm = 28.0 * 25.4 / 72.0
    big = _area(r2)
    assert small is not None and big is not None
    if size_pt < 28.0:
        assert small[0] < big[0], (
            f"{size_pt:.0f} pt puts the ink at {small[0]:.2f} mm and 28 pt at "
            f"{big[0]:.2f}; a smaller label must sit closer to the band")


@pytest.mark.parametrize("margin", [12.0, 20.0, 30.0, 45.0])
def test_a_wider_left_margin_does_not_move_the_label_ink(margin):
    r = _recipe(12.0)
    r.margin_left = margin
    area = _area(r)
    assert area is not None
    assert area[0] == pytest.approx(17.22, abs=0.05), (
        f"a {margin:.0f} mm left margin puts the ink at {area[0]:.2f} mm")


@pytest.mark.parametrize("band", [12.0, 16.0, 20.0, 26.0])
def test_the_band_width_moves_the_label_ink_one_for_one(band):
    area = _area(_recipe(band))
    base = _area(_recipe(12.0))
    assert area is not None and base is not None
    assert area[0] == pytest.approx(base[0] + (band - 12.0), abs=0.05)


def test_clip_moves_the_labels_only_above_the_band_width():
    below = _area(_recipe(12.0, clip_mm=8.0))
    at = _area(_recipe(12.0, clip_mm=12.0))
    above = _area(_recipe(12.0, clip_mm=20.0))
    assert below[0] == pytest.approx(at[0], abs=0.01), (
        "Clip moved the labels while it was under the band's width")
    assert above[0] == pytest.approx(at[0] + 8.0, abs=0.05), (
        "Clip above the band's width does not move the labels one for one")


def _label_ink_start_mm(g, npat: int) -> float:
    """Where the row-label ink really begins on a rendered page, in mm."""
    lay = geometry.compute(g, 210.0, 297.0, npat)
    target = ColorTarget(color_rep="iRGB",
                         device_fields=["RGB_R", "RGB_G", "RGB_B"],
                         patches=[(_DEV, _XYZ) for _ in range(npat)])
    res = raster.render_pages(target, lay, g, seed=5, randomize=False,
                              paper_w_mm=210.0, paper_h_mm=297.0, dpi=200,
                              clip_content_mode="off")
    img = np.asarray(res.images[0])
    mm2px = 200 / 25.4
    stop = int(round(float(g.margin_l) * mm2px)) - 2
    cols = np.flatnonzero((img[:, :stop].min(axis=2) < 120).any(axis=0))
    assert len(cols), "no row-label ink on the sheet"
    return float(cols.min()) / mm2px


def test_the_prediction_matches_the_ink_on_a_full_page():
    """§R2's arithmetic against a page the renderer actually produced.

    A second copy of a rule is only worth having while it agrees with the
    original, and this one is a second copy by necessity: the renderer places
    each label in pixels from that label's own width, and the panel has to
    answer before any raster exists.

    ON A FULL PAGE, because that is what the band is sized for. §R1.2 measures
    it from "the widest label a FULL page would print", and
    `raster._rows_that_fit` says so in as many words, so the prediction is the
    band's own left edge and a full sheet is where the widest label reaches it.
    """
    r = _recipe(16.0)
    g = _geom(r)
    full = geometry.patches_per_sheet(g, 210.0, 297.0)
    assert full > 20, full
    got = _label_ink_start_mm(g, full)
    area = _area(r)
    assert area is not None
    # Within a glyph's left side bearing: the prediction is the label's
    # ADVANCE width and the ink starts a fraction inside it, which is the
    # conservative side.
    assert -0.1 < got - area[0] < 0.8, (
        f"the prediction says the labels start at {area[0]:.2f} mm and the "
        f"sheet has their ink at {got:.2f} mm")


def test_a_short_chart_prints_the_labels_in_the_same_place():
    """The band holds the rows a FULL page holds, so a short chart's labels
    land where a full one's do. The prediction does not depend on the patch
    count, and this is why it does not have to."""
    r = _recipe(16.0)
    g = _geom(r)
    area = _area(r)
    for npat in (54, 120, 400):
        got = _label_ink_start_mm(g, npat)
        assert -0.1 < got - area[0] < 0.8, (
            f"{npat} patches put the label ink at {got:.2f} mm against a "
            f"prediction of {area[0]:.2f}")


# --------------------------------------------------- 2. catching the hit
#: Enough lines that the text reaches the labels on THIS geometry and still
#: stops short of the patches. Derived rather than typed: the label position
#: depends on the row count, which depends on the patch size.
_LINES_ON_LABELS = 6
_LINES_ON_BOTH = 10


def test_the_collision_names_the_labels_and_not_the_patches():
    r = _recipe(12.0, lines=_LINES_ON_LABELS)
    g = _geom(r)
    zone = g.lbord + g.border
    area = _area(r)
    hit = tef.clip_text_collision(zone, r.text_edge_clip_mm,
                                  _LINES_ON_LABELS, 0.0,
                                  area[0], float(g.margin_l))
    assert hit.over_labels_mm > 0.05, "this case does not register a hit"
    assert hit.over_patches_mm == 0.0, (
        "the patch area is further on and must not be named")
    assert hit.hits_anything


def test_a_deep_overflow_crosses_both_and_reports_both():
    r = _recipe(12.0, lines=_LINES_ON_BOTH)
    g = _geom(r)
    zone = g.lbord + g.border
    area = _area(r)
    hit = tef.clip_text_collision(zone, r.text_edge_clip_mm,
                                  _LINES_ON_BOTH, 0.0,
                                  area[0], float(g.margin_l))
    assert hit.over_labels_mm > hit.over_patches_mm > 0.05, (
        f"labels {hit.over_labels_mm:.2f}, patches {hit.over_patches_mm:.2f}")


def test_a_band_with_room_hits_nothing():
    r = _recipe(26.0)
    g = _geom(r)
    zone = g.lbord + g.border
    area = _area(r)
    hit = tef.clip_text_collision(zone, r.text_edge_clip_mm, 4, 0.0,
                                  area[0], float(g.margin_l))
    assert not hit.hits_anything
    assert hit.over_labels_mm == 0.0 and hit.over_patches_mm == 0.0


def test_with_the_labels_off_the_patch_area_is_the_first_thing_it_meets():
    r = _recipe(12.0, rows=False)
    g = _geom(r)
    zone = g.lbord + g.border
    assert _area(r) is None
    hit = tef.clip_text_collision(zone, r.text_edge_clip_mm, 4, 0.0,
                                  None, float(g.margin_l))
    assert hit.over_labels_mm == 0.0
    assert hit.over_patches_mm > 0.05, (
        "with no labels the margin sits at the band and the text reaches the "
        "patches")


def test_the_reach_is_the_reserve_plus_the_text_and_agrees_with_the_overhang():
    for band in (10.0, 12.0, 16.0, 26.0):
        for n in (1, 4, 8):
            reach = tef.clip_text_reach_mm(band, 4.0, n)
            over = tef.clip_text_overhang_mm(band, 4.0, n)
            if over > 0:
                assert reach == pytest.approx(band + over, abs=1e-9), (band, n)
            else:
                assert reach <= band + tef.EPS_MM


def test_the_clip_distance_that_clears_the_labels_really_clears_them():
    """The remedy the warning offers for the label collision, exercised."""
    r = _recipe(12.0, lines=_LINES_ON_LABELS)
    g = _geom(r)
    zone = g.lbord + g.border
    area = _area(r)
    hit = tef.clip_text_collision(zone, r.text_edge_clip_mm,
                                  _LINES_ON_LABELS, 0.0,
                                  area[0], float(g.margin_l))
    assert hit.over_labels_mm > 0.05
    clear = tef.clip_edge_to_clear_labels_mm(hit.reach_mm)
    assert clear > r.text_edge_clip_mm
    r2 = _recipe(12.0, lines=_LINES_ON_LABELS, clip_mm=round(clear + 0.05, 2))
    g2 = _geom(r2)
    area2 = _area(r2)
    hit2 = tef.clip_text_collision(g2.lbord + g2.border, r2.text_edge_clip_mm,
                                   _LINES_ON_LABELS, 0.0, area2[0],
                                   float(g2.margin_l))
    assert hit2.over_labels_mm == 0.0, (
        f"raising Clip to {clear:.1f} mm left {hit2.over_labels_mm:.2f} mm of "
        f"the text still on the labels")


# ------------------------------------- 3. what the overlap costs the labels
def _page(band_mm: float, lines: int):
    r = _recipe(band_mm, lines=lines)
    g = _geom(r)
    lay = geometry.compute(g, 210.0, 297.0, 120)
    target = ColorTarget(color_rep="iRGB",
                         device_fields=["RGB_R", "RGB_G", "RGB_B"],
                         patches=[(_DEV, _XYZ) for _ in range(120)])

    def render(text):
        res = raster.render_pages(target, lay, g, seed=5, randomize=False,
                                  paper_w_mm=210.0, paper_h_mm=297.0, dpi=200,
                                  clip_content_mode="text", clip_text=text,
                                  clip_text_size_mm=0.0, clip_flip_180=False)
        return np.asarray(res.images[0])

    # The control is the same chart with the clip TEXT blanked, so the
    # geometry is identical and every changed pixel is that text's own ink.
    return g, render(""), render(r.clip_text)


def _label_window(g):
    area = geometry.row_label_area_mm(g)
    mm2px = 200 / 25.4
    return int(round(area[0] * mm2px)), int(round(area[1] * mm2px))


def test_the_clip_text_does_not_erase_the_labels_it_lands_on():
    """The trap this round's neighbour found: the strip is an OPAQUE image.

    The row labels are drawn onto the page BEFORE the clip strip is pasted, so
    an unmasked paste would rub them out. Nothing is rubbed out: the labels are
    still there and the clip text is on top of them.
    """
    g, before, after = _page(16.0, 8)
    x0, x1 = _label_window(g)
    lab_before = (before[:, x0:x1].min(axis=2) < 150)
    lab_after = (after[:, x0:x1].min(axis=2) < 150)
    assert lab_before.sum() > 500, "no row-label ink to lose"
    lost = int((lab_before & ~lab_after).sum())
    assert lost / lab_before.sum() < 0.01, (
        f"{lost} of {int(lab_before.sum())} label pixels were erased by the "
        f"clip strip, so it is being pasted over them rather than composited")


def test_the_clip_text_really_is_printed_on_the_labels():
    g, before, after = _page(16.0, 8)
    x0, x1 = _label_window(g)
    changed = (before[:, x0:x1].astype(int)
               != after[:, x0:x1].astype(int)).any(axis=2)
    assert changed.sum() > 100, (
        "no clip-text ink reached the label band, so this file is measuring "
        "a sheet with no collision on it")


def test_how_unreadable_the_labels_become_is_bounded_and_recorded():
    """WHAT IT COSTS, and it is a different cost from ink on a patch.

    A patch with ink on it is still measured and returns a wrong number. A
    label with ink on it is read by a person, who either can or cannot pick out
    the digits, so the measure is how much of the WHITE SPACE inside a label's
    own box the other text fills in.

    Measured on the sheets the app wrote, on Knut's run 2:

    | overlap | fills the white inside a label box | label ink erased |
    |---|---|---|
    | 1.25 mm (12 mm band, 4 lines) | 4.1 % | 0.00 % |
    | 9.91 mm (16 mm band, 8 lines) | 21.7 % | 0.02 % |

    So at the shallow overlap the numbers are still clear, and at the deep one
    a fifth of the space between the strokes carries another text. This test
    pins the shape of that, not the exact percentages, so it stays true when
    the fonts move.
    """
    shallow = _fill_fraction(*_page(12.0, 4))
    deep = _fill_fraction(*_page(16.0, 8))
    assert shallow < 0.10, (
        f"a 1.25 mm overlap already fills {shallow:.1%} of the label boxes")
    assert deep > shallow * 2, (
        f"a 9.9 mm overlap fills {deep:.1%} and a 1.25 mm one {shallow:.1%}, "
        f"so this is not measuring depth at all")


def _fill_fraction(g, before, after) -> float:
    """The worst label's share of its own white space filled by the clip text."""
    x0, x1 = _label_window(g)
    lab = (before[:, x0:x1].min(axis=2) < 150)
    clip = (before[:, x0:x1].astype(int) != after[:, x0:x1].astype(int)).any(axis=2)
    rows = np.flatnonzero(lab.any(axis=1))
    if not len(rows):
        return 0.0
    groups: list[list[int]] = [[int(rows[0])]]
    for y in rows[1:]:
        if int(y) - groups[-1][-1] <= 2:
            groups[-1].append(int(y))
        else:
            groups.append([int(y)])
    worst = 0.0
    for gp in groups:
        y0, y1 = gp[0], gp[-1] + 1
        white = ~lab[y0:y1]
        if white.sum():
            worst = max(worst, float((white & clip[y0:y1]).sum() / white.sum()))
    return worst


def test_the_clip_that_clears_the_labels_uses_THIS_chart_s_gap():
    """Not the 1 mm §R2 reserves, which overshoots by the band's over-allowance.

    The mutation this catches is `reach - 1` instead of `reach - gap`: it still
    clears the labels, so "does it clear them" cannot see it. What it costs is
    left margin the user does not have to spend, so the test is that the answer
    tracks the gap.
    """
    r = _recipe(12.0, lines=_LINES_ON_BOTH)
    g = _geom(r)
    area = _area(r)
    gap = area[1] - area[0]
    assert gap > 2.0, (
        f"this chart's label gap is {gap:.2f} mm, so a 1 mm assumption would "
        f"not be visibly wrong and this test proves nothing")
    reach = tef.clip_text_reach_mm(g.lbord + g.border, r.text_edge_clip_mm,
                                   _LINES_ON_BOTH, 0.0)
    assert tef.clip_edge_to_clear_labels_mm(reach, gap) == pytest.approx(
        reach - gap, abs=1e-9)
    # …and the 1 mm answer really is bigger, which is what makes it wrong.
    assert tef.clip_edge_to_clear_labels_mm(reach, 1.0) > \
        tef.clip_edge_to_clear_labels_mm(reach, gap) + 1.0


def test_the_patch_clamp_on_the_label_band_cannot_bind_on_a_real_chart():
    """Recorded rather than tested, because it is true BY CONSTRUCTION.

    `row_label_area_mm` mirrors §R2's ``band right = min(floor + band,
    patch x0 - 1 mm)``. The right-hand term never wins:
    `raster.apply_row_label_geometry` sets
    ``margin_l = max(asked, floor + measured + 1)`` and stores that same
    `measured` as `rlwi`, so ``margin_l - 1 >= floor + rlwi`` on every geometry
    the app builds. The clamp is kept because the renderer has it and the two
    must not drift; this test is what says a mutation to it is EQUIVALENT
    rather than uncaught.
    """
    for band in (10.0, 12.0, 16.0, 26.0):
        for margin in (0.0, band, band * 3):
            r = _recipe(band)
            r.margin_left = margin
            g = _geom(r)
            floor = float(getattr(g, "row_label_floor", 0.0) or 0.0)
            rlwi = float(getattr(g, "rlwi", 0.0) or 0.0)
            assert float(g.margin_l) - 1.0 >= floor + rlwi - 1e-9, (
                f"band {band}, margin {margin}: the patch clamp binds, so the "
                f"two terms of §R2's min() are not equivalent after all")
