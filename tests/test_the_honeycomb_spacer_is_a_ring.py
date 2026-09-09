"""A honeycomb's spacer is a RING around each patch, not a bar between rows.

Basti spotted it in a proof sheet: *"in your proof the spacers look weird for
the hexes"*, and then proposed the fix himself: *"would it make sense to draw
spacers only for hexes around the whole hex?"* It would, and it is better than
any of the three options put to him.

WHAT WAS WRONG, MEASURED, on a CR30 A4 honeycomb with spacers switched on:

* `raster.py` drew every inter-patch spacer as a solid FULL-WIDTH RECTANGLE
  from one slot's bottom to the next slot's top, with no hexagon branch, while
  the patch drawn immediately above it had one. On a honeycomb those two edges
  are APEXES, so the bar was painted straight through the interlock and covered
  **1.300 mm of each 1.732 mm point, 75 % of it**. 22 black rules across a
  sheet.
* And because a bar grows the pitch on ONE axis while a honeycomb interlocks in
  three directions, the diagonals were simply pulled apart: **6.64 % of the
  patch field was paper** showing through slivers nobody chose. Turning the
  honeycomb 30 degrees halved that (2.35 %) and could not remove it, which is
  what showed the mechanism was the problem rather than the orientation.

WHY A RING IS THE ONLY SHAPE THAT WORKS. A bar separates two of a hexagon's six
neighbours. A ring separates all six, and it comes out of the patch's own area
instead of out of the page, so the lattice keeps tessellating and the spacer
costs no patches at all.

EACH SIDE TAKES ITS OWN COLOUR, which was Basti's second ruling: *"maybe each of
the six sides can have different colors. of course should respect the black and
white option we already have."* A side faces exactly one neighbour, so it is
coloured by the ordinary pair rule against that patch, and "Black & white" goes
on meaning what it means. And because that rule is symmetric in its two
arguments, this patch's half-band and the neighbour's half-band come out the
same colour: *"two touching patches should share a spacer on the side that
touches."* They do, and the two halves read as one band.
"""
from __future__ import annotations

import json
import os
import random
import tempfile
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from workflow.layout_engine import chart as le_chart          # noqa: E402
from workflow.layout_engine import geometry as G              # noqa: E402
from workflow.layout_engine import hexagon                    # noqa: E402
from workflow.layout_engine import instruments as I           # noqa: E402
from workflow.layout_engine.contrast import spacer_for_mode    # noqa: E402

A4 = (210.0, 297.0)

# A palette with NO WHITE IN IT. White is a legitimate spacer colour, so on the
# shipped palette a white pixel inside the patch field is ambiguous: paper
# showing through a gap, or a spacer that happened to be white. Removing white
# from the candidates removes the ambiguity, and any white left is a gap.
NO_WHITE = [(0, 0, 0), (255, 0, 0), (0, 160, 0), (0, 0, 255),
            (255, 160, 0), (160, 0, 160)]


def _ti1(d: Path, n: int = 210) -> Path:
    lines = ["CTI1", "", 'DESCRIPTOR "ring"', 'ORIGINATOR "ChromIQ"',
             'KEYWORD "SAMPLE_LOC"', "NUMBER_OF_FIELDS 7", "BEGIN_DATA_FORMAT",
             "SAMPLE_ID RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z", "END_DATA_FORMAT",
             f"NUMBER_OF_SETS {n}", "BEGIN_DATA"]
    for i in range(n):
        lines.append(f"{i+1} {(i*7)%100}.0 {(i*13)%100}.0 {(i*29)%100}.0 40 45 50")
    lines += ["END_DATA", ""]
    p = d / "p.ti1"
    p.write_text("\n".join(lines), encoding="utf-8")
    return p


def _render(flat_top: bool, spacer_mode: str, dpi: int = 600,
            palette=None):
    d = Path(tempfile.mkdtemp())
    ti1 = _ti1(d)
    out = d / "out"
    out.mkdir()
    res = le_chart.build_chart(ti1, out / "c", instrument="CR30", paper="A4",
                               hflag=True, hex_flat_top=flat_top, dpi=dpi,
                               randomize=False, spacer_mode=spacer_mode,
                               spacer_palette=palette)
    img = np.asarray(Image.open(sorted(out.glob("*.tif"))[0])
                     .convert("RGB")).astype(int)
    return res, img, out


def _paper_inside_the_field(a: np.ndarray) -> float:
    """Percentage of the patch field that is bare paper."""
    ys, xs = np.nonzero(np.any(a < 250, axis=2))
    y0, y1 = int(np.percentile(ys, 20)), int(np.percentile(ys, 80))
    x0, x1 = int(np.percentile(xs, 20)), int(np.percentile(xs, 80))
    return 100.0 * np.all(a[y0:y1, x0:x1] > 245, axis=2).mean()


# ---------------------------------------------------------------------------
# the sheet
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("flat_top", [False, True])
@pytest.mark.parametrize("spacer_mode", ["none", "colored"])
def test_no_paper_shows_through_a_honeycomb(flat_top, spacer_mode):
    """THE HEADLINE. Both orientations, spacers on and off, no gaps. Before the
    ring this measured 0.00 / 6.64 / 0.00 / 2.35 percent."""
    _res, img, _ = _render(flat_top, spacer_mode, palette=NO_WHITE)
    paper = _paper_inside_the_field(img)
    # 600 dpi, where the sub-pixel seam below does not arise, so this measures
    # the LATTICE rather than the rounding.
    assert paper < 0.05, (
        f"flat_top={flat_top} spacers={spacer_mode}: {paper:.2f} % of the patch "
        "field is bare paper, so the honeycomb is not tessellating"
    )


@pytest.mark.parametrize("flat_top", [False, True])
def test_no_full_width_bar_is_drawn_across_the_sheet(flat_top):
    """The bar itself. 22 of these before the ring, on either orientation's
    pointy case; the rotated one had none only because its patches meet along
    their flat edges, which is luck rather than design."""
    _res, img, _ = _render(flat_top, "colored")
    dark = img.sum(axis=2) < 200
    rules, prev = 0, -9
    for y in np.where(dark.mean(axis=1) > 0.40)[0]:
        if y != prev + 1:
            rules += 1
        prev = y
    assert rules == 0, f"{rules} full-width rules across a honeycomb"


@pytest.mark.parametrize("flat_top", [False, True])
def test_the_ring_costs_no_patches(flat_top):
    """The claim that justified the shape. A bar is added to the pitch; a ring
    comes out of the patch's own area, so switching spacers on must not shrink
    the sheet's capacity."""
    off, _, _ = _render(flat_top, "none", dpi=300)
    on, _, _ = _render(flat_top, "colored", dpi=300)
    assert (on.layout.passes, on.layout.steps_in_pass) == \
           (off.layout.passes, off.layout.steps_in_pass), (
        f"the spacer changed the grid from {off.layout.passes}x"
        f"{off.layout.steps_in_pass} to {on.layout.passes}x"
        f"{on.layout.steps_in_pass}"
    )


# ---------------------------------------------------------------------------
# the geometry of the ring
# ---------------------------------------------------------------------------
def test_the_gap_between_two_patches_is_the_spacer_width():
    """Each patch gives up HALF the spacer, so the two half-bands abut into one
    gap of the full width. Give up the whole width each and the spacer is
    twice what the user asked for."""
    g = I.build("CR30", hflag=True, spacer_on=True)
    assert g.hex_ring_mm == pytest.approx(1.3)
    assert g.pspa == 0.0, "the ring must not also be added to the pitch"
    outer = hexagon.vertices(0, 0, g.pwid, g.plen)
    inner = hexagon.inset(outer, g.hex_ring_mm / 2.0)
    import math
    def apothem(pts):
        n = len(pts)
        cx = sum(x for x, _ in pts) / n
        cy = sum(y for _, y in pts) / n
        return min(math.dist((cx, cy),
                             ((pts[i][0] + pts[(i+1) % n][0]) / 2,
                              (pts[i][1] + pts[(i+1) % n][1]) / 2))
                   for i in range(n))
    assert apothem(outer) - apothem(inner) == pytest.approx(g.hex_ring_mm / 2)


def test_the_inset_hexagon_is_still_a_regular_hexagon():
    import math
    o = hexagon.vertices(0, 0, 12.0, 12.0 * math.sqrt(3) / 2)
    i = hexagon.inset(o, 0.65)
    sides = [math.dist(i[k], i[(k + 1) % 6]) for k in range(6)]
    assert max(sides) - min(sides) < 1e-9


def test_a_ring_is_six_quads_in_vertex_order():
    o = hexagon.vertices(0, 0, 12.0, 10.39)
    i = hexagon.inset(o, 0.65)
    q = hexagon.ring_quads(o, i)
    assert len(q) == 6 and all(len(x) == 4 for x in q)
    for k in range(6):
        assert q[k][0] == o[k] and q[k][1] == o[(k + 1) % 6]


@pytest.mark.parametrize("flat_top", [False, True])
def test_every_side_names_the_patch_it_actually_faces(flat_top):
    """The neighbour map decides which patch each side is coloured against, so
    an error there gives a plausible-looking sheet whose colours mean nothing.
    Checked against the geometry rather than against the arithmetic that
    produced it: for each side, the nearest other centre to that edge's midpoint
    must be the patch the map names."""
    import math
    w, ph = (12.0, 12.0 * math.sqrt(3) / 2) if not flat_top \
        else (12.0 * math.sqrt(3) / 2, 12.0)

    def centre(p, j):
        if flat_top:
            return (p * w + w / 2, j * ph + ph / 2
                    + (-ph / 4 if p % 2 == 0 else ph / 4))
        dx = -w / 4 if j % 2 == 0 else w / 4
        return (p * w + w / 2 + dx, j * ph + ph / 2)

    checked = 0
    for p in range(2, 6):
        for j in range(2, 6):
            c = centre(p, j)
            pts = hexagon.vertices(c[0] - w / 2, c[1] - ph / 2, w, ph,
                                   flat_top=flat_top)
            for i, nb in enumerate(hexagon.side_neighbours(
                    p, j, flat_top=flat_top)):
                mid = ((pts[i][0] + pts[(i+1) % 6][0]) / 2,
                       (pts[i][1] + pts[(i+1) % 6][1]) / 2)
                nearest = min(((q, k) for q in range(9) for k in range(9)
                               if (q, k) != (p, j)),
                              key=lambda t: math.dist(mid, centre(*t)))
                assert nearest == nb, (
                    f"side {i} of ({p},{j}): map says {nb}, geometry says "
                    f"{nearest}")
                checked += 1
    assert checked == 96


# ---------------------------------------------------------------------------
# the colour of the ring
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("mode", ["bw", "colored"])
def test_the_pair_rule_is_symmetric_so_the_two_halves_agree(mode):
    """THE MECHANISM BEHIND "two touching patches should share a spacer". The
    two half-bands are drawn independently, by two different patches, and they
    read as one band only because the colour rule gives the same answer either
    way round. If it ever stopped being symmetric, every shared side would come
    out two-tone and nothing else in the suite would notice."""
    random.seed(11)
    for _ in range(4000):
        a = tuple(random.randrange(256) for _ in range(3))
        b = tuple(random.randrange(256) for _ in range(3))
        assert spacer_for_mode(mode, a, b) == spacer_for_mode(mode, b, a)


def test_black_and_white_mode_only_ever_draws_black_or_white():
    """Basti: *"of course should respect the black and white option we already
    have."* Measured off the rendered sheet, not off the colour function: the
    ring must not quietly fall back to the coloured palette."""
    _res, img, _ = _render(False, "bw", dpi=300)
    ys, xs = np.nonzero(np.any(img < 250, axis=2))
    y0, y1 = int(np.percentile(ys, 25)), int(np.percentile(ys, 75))
    x0, x1 = int(np.percentile(xs, 25)), int(np.percentile(xs, 75))
    box = img[y0:y1, x0:x1].reshape(-1, 3)
    # the patches themselves are the ti1's colours; the RING pixels are whatever
    # the mode chose. Saturated non-grey pixels that are not a patch colour
    # would mean the coloured palette leaked in. Every ring pixel must be one of
    # pure black or pure white.
    from workflow.layout_engine.contrast import _COLOURED_PALETTE
    leaked = [c for c in _COLOURED_PALETTE if c not in ((0, 0, 0), (255, 255, 255))
              and np.any(np.all(box == np.array(c), axis=1))]
    assert not leaked, f"black & white mode drew {leaked}"


# ---------------------------------------------------------------------------
# what must NOT have changed
# ---------------------------------------------------------------------------
def test_a_rectangular_chart_still_gets_a_bar():
    """The ring is for honeycombs. Every strip reader still gets the spacer it
    has always had, in the pitch, between consecutive patches."""
    for key in ("i1", "p3", "CM", "41", "51"):
        g = I.build(key, spacer_on=True)
        assert g.pspa > 0, f"{key} lost its spacer"
        assert g.hex_ring_mm == 0.0, f"{key} was given a ring"
    g = I.build("CR30", hflag=False, spacer_on=True)
    assert g.pspa > 0 and g.hex_ring_mm == 0.0


def test_the_spectroscan_honeycomb_is_untouched():
    """It never had a spacer to convert (pspa = 0), so nothing about it moves.
    That is what confines this change to the CR30."""
    for ft in (False, True):
        g = I.build("SS", hflag=True, spacer_on=True, hex_flat_top=ft)
        assert g.hex_ring_mm == 0.0
        assert g.pspa == 0.0


def test_switching_spacers_off_leaves_no_ring():
    g = I.build("CR30", hflag=True, spacer_on=False)
    assert g.hex_ring_mm == 0.0


def test_the_users_spacer_width_still_reaches_the_ring():
    """The Spacer size box must go on meaning the gap between two patches. The
    hand-off happens after the override, so a typed width becomes the ring."""
    g = I.build("CR30", hflag=True, spacer_on=True, spacer_width=2.5)
    assert g.hex_ring_mm == pytest.approx(2.5)
    assert g.pspa == 0.0


# ---------------------------------------------------------------------------
# ...measured off the SHEET, because the two tests above did not catch these
# ---------------------------------------------------------------------------
#
# Both of the following were added after a mutation round: doubling the ring's
# width and colouring every side against the patch alone BOTH passed the tests
# above. The geometric tests computed the inset themselves instead of reading
# what the renderer drew, and the colour tests checked the rule rather than the
# sheet. A guard has to look at the ink.

def _patch_colour_run(img, p0, p1, samples=1200):
    """Walk the straight line from *p0* to *p1* across two neighbouring patches
    and return ``(colour at p0, colour at p1, pixels that are neither)``."""
    import math
    a = tuple(img[int(round(p0[1])), int(round(p0[0]))])
    b = tuple(img[int(round(p1[1])), int(round(p1[0]))])
    n = 0
    length = math.dist(p0, p1)
    for k in range(samples + 1):
        t = k / samples
        x = int(round(p0[0] + (p1[0] - p0[0]) * t))
        y = int(round(p0[1] + (p1[1] - p0[1]) * t))
        c = tuple(img[y, x])
        if c != a and c != b:
            n += 1
    return a, b, n * length / samples


@pytest.mark.parametrize("flat_top", [False, True])
def test_the_drawn_gap_is_the_width_the_user_asked_for(flat_top):
    """CATCHES A RING DRAWN TWICE AS WIDE. Each patch gives up HALF the spacer,
    so the gap measured across a shared side is the FULL width once. Inset by
    the whole width at each patch and the user gets 2.6 mm where they asked for
    1.3, at the cost of a quarter of every patch's area."""
    dpi = 600
    _res, img, out = _render(flat_top, "colored", dpi=dpi, palette=NO_WHITE)
    pats = [p for p in json.loads((out / "c.strips.json")
                                  .read_text(encoding="utf-8"))["patches"]
            if p.get("page", 0) == 0]
    by_loc = {p["loc"]: p for p in pats}
    g = I.build("CR30", hflag=True, hex_flat_top=flat_top, spacer_on=True)

    # two patches that share a FLAT side: across the page on a pointy sheet,
    # down a strip on a rotated one. Walk centre to centre.
    steps = _res.layout.steps_in_pass
    pairs = []
    for k, p in enumerate(pats):
        if flat_top:
            q = pats[k + 1] if (k + 1) % steps and k + 1 < len(pats) else None
        else:
            q = pats[k + steps] if k + steps < len(pats) else None
        if q is not None:
            pairs.append((p, q))
    assert len(pairs) > 20

    px_per_mm = dpi / 25.4
    gaps = []
    for p, q in pairs[:40]:
        c0 = (p["x"] + p["w"] / 2, p["y"] + p["h"] / 2)
        c1 = (q["x"] + q["w"] / 2, q["y"] + q["h"] / 2)
        _a, _b, run_px = _patch_colour_run(img, c0, c1)
        gaps.append(run_px / px_per_mm)
    med = sorted(gaps)[len(gaps) // 2]
    assert med == pytest.approx(g.hex_ring_mm, abs=0.25), (
        f"the drawn gap between two touching patches is {med:.2f} mm, and the "
        f"spacer is {g.hex_ring_mm:.2f} mm"
    )


@pytest.mark.parametrize("flat_top", [False, True])
def test_each_side_is_coloured_against_the_patch_it_faces(flat_top):
    """CATCHES A RING PAINTED ONE COLOUR ALL ROUND. Basti asked for six sides
    that can differ; colouring them all against the patch alone gives a sheet
    that looks plausible and means nothing, and every other test here passes.

    Sample the ink just outside each side's midpoint and require it to be the
    pair colour for the neighbour the map names.
    """
    dpi = 600
    _res, img, out = _render(flat_top, "colored", dpi=dpi, palette=NO_WHITE)
    pats = [p for p in json.loads((out / "c.strips.json")
                                  .read_text(encoding="utf-8"))["patches"]
            if p.get("page", 0) == 0]
    steps = _res.layout.steps_in_pass
    by_idx = {(k // steps, k % steps): p for k, p in enumerate(pats)}

    def rgb_of(p):
        return tuple(img[int(p["y"] + p["h"] / 2), int(p["x"] + p["w"] / 2)])

    seen, checked = set(), 0
    for (strip, step), p in list(by_idx.items()):
        if strip == 0 or step == 0 or strip > 4 or step > 6:
            continue          # keep well inside the field, away from the paper
        outer = hexagon.vertices(p["x"], p["y"], p["w"], p["h"],
                                 flat_top=flat_top)
        inner = hexagon.inset(outer, 0.5 * _res_ring_px(dpi))
        nbs = hexagon.side_neighbours(strip, step, flat_top=flat_top)
        me = rgb_of(p)
        for i, nb in enumerate(nbs):
            q = by_idx.get(nb)
            if q is None:
                continue
            # a point in the band: midway between the outer and inner edge
            mo = ((outer[i][0] + outer[(i+1) % 6][0]) / 2,
                  (outer[i][1] + outer[(i+1) % 6][1]) / 2)
            mi = ((inner[i][0] + inner[(i+1) % 6][0]) / 2,
                  (inner[i][1] + inner[(i+1) % 6][1]) / 2)
            sx, sy = (mo[0] + mi[0]) / 2, (mo[1] + mi[1]) / 2
            drawn = tuple(img[int(round(sy)), int(round(sx))])
            want = spacer_for_mode("colored", me, rgb_of(q), NO_WHITE)
            if drawn == want:
                seen.add(want)
            checked += 1
            assert drawn == want, (
                f"({strip},{step}) side {i} facing {nb}: drawn {drawn}, the "
                f"pair rule against that neighbour says {want}"
            )
    assert checked > 40, f"only {checked} sides sampled"
    assert len(seen) > 1, (
        "every sampled side came out the same colour, so the per-side "
        "neighbour is not reaching the colour rule"
    )


def _res_ring_px(dpi: int) -> float:
    g = I.build("CR30", hflag=True, spacer_on=True)
    return g.hex_ring_mm * dpi / 25.4


# ---------------------------------------------------------------------------
# the outside of the sheet, and the seams
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("flat_top", [False, True])
def test_edge_spacers_reach_the_ring(flat_top):
    """Basti: *"is the option for edge spacers respected if on or off?"* It was
    not. The first ring painted all six sides whatever the box said, so the
    control did nothing on a honeycomb, which is the quietest kind of broken."""
    a = _render(flat_top, "colored", dpi=300, palette=NO_WHITE)[1]
    d = Path(tempfile.mkdtemp())
    ti1 = _ti1(d)
    out = d / "on"
    out.mkdir()
    le_chart.build_chart(ti1, out / "c", instrument="CR30", paper="A4",
                         hflag=True, hex_flat_top=flat_top, dpi=300,
                         randomize=False, spacer_mode="colored",
                         spacer_palette=NO_WHITE, edge_spacers=True)
    b = np.asarray(Image.open(sorted(out.glob("*.tif"))[0])
                   .convert("RGB")).astype(int)
    assert not np.array_equal(a, b), \
        "edge spacers changed nothing on a honeycomb"
    ink_off = int(np.any(a < 250, axis=2).sum())
    ink_on = int(np.any(b < 250, axis=2).sum())
    assert ink_on > ink_off, \
        f"edge spacers added no ink ({ink_off} -> {ink_on})"


@pytest.mark.parametrize("flat_top", [False, True])
def test_the_outside_band_is_a_full_width_spacer(flat_top):
    """Basti: *"the spacers on the outside should probably be double if turned
    on."* A side between two patches carries half the spacer from each, so the
    gap is one full width. A side facing the paper has nobody to share with, so
    on its own it must be the full width too, reaching outward past the hexagon
    rather than eating into the patch. Every patch stays the same size either
    way, which is what keeps the instrument reading the same area everywhere."""
    dpi = 600
    g = I.build("CR30", hflag=True, hex_flat_top=flat_top, spacer_on=True)
    d = Path(tempfile.mkdtemp())
    ti1 = _ti1(d)
    out = d / "on"
    out.mkdir()
    res = le_chart.build_chart(ti1, out / "c", instrument="CR30", paper="A4",
                               hflag=True, hex_flat_top=flat_top, dpi=dpi,
                               randomize=False, spacer_mode="colored",
                               spacer_palette=NO_WHITE, edge_spacers=True)
    img = np.asarray(Image.open(sorted(out.glob("*.tif"))[0])
                     .convert("RGB")).astype(int)
    pats = [p for p in json.loads((out / "c.strips.json")
                                  .read_text(encoding="utf-8"))["patches"]
            if p.get("page", 0) == 0]

    # MEASURED OFF THE SHEET, not recomputed from the same arithmetic that drew
    # it: an earlier version of this test derived the band from `inset` and so
    # stayed green when the renderer stopped growing the outer edge at all.
    #
    # Walk LEFT from the centre of a patch in the leftmost strip. On a pointy
    # sheet that side is a flat vertical one; on a rotated sheet the leftmost
    # column is still the outermost, and the ray leaves through its left apex.
    steps = res.layout.steps_in_pass
    leftmost = min(p["x"] for p in pats)
    edge = [p for p in pats if p["x"] == leftmost]
    px_per_mm = dpi / 25.4
    bands = []
    for p in edge[2:10]:
        cy = int(p["y"] + p["h"] / 2)
        cx = int(p["x"] + p["w"] / 2)
        patch_rgb = tuple(img[cy, cx])
        x = cx
        while x > 0 and tuple(img[cy, x]) == patch_rgb:      # cross the patch
            x -= 1
        band = 0
        while x > 0 and not np.all(img[cy, x] > 245):        # cross the band
            band += 1
            x -= 1
        bands.append(band / px_per_mm)
    assert len(bands) >= 5
    med = sorted(bands)[len(bands) // 2]
    assert med == pytest.approx(g.hex_ring_mm, abs=0.3), (
        f"the band on the outside of the sheet measures {med:.2f} mm, and a "
        f"shared gap between two patches is {g.hex_ring_mm:.2f} mm; with "
        "nobody to share with, the outer one has to be the full width by itself"
    )


@pytest.mark.parametrize("flat_top", [False, True])
@pytest.mark.parametrize("spacer_mode", ["none", "colored"])
@pytest.mark.parametrize("dpi", [
    pytest.param(300, marks=pytest.mark.xfail(strict=True, reason=(
        "KNOWN, MEASURED, PRE-EXISTING, NOT FIXED HERE. A honeycomb leaves bare "
        "paper along the seams between its patches. Three hexagons meet at every "
        "apex and each rounds its vertices independently, from slot bounds that "
        "are themselves rounded per strip: at 300 dpi a 12.0000 mm pitch comes "
        "out 142 px on most strips and 141 on some, so one hexagon's right edge "
        "lands on x=566 and its neighbour's left edge on 567. It is IDENTICAL "
        "with spacers off, so the ring did not cause it; a dark ring only made "
        "it visible, which is how Basti found it. "
        "IT IS NOT A '300 DPI' PROBLEM, and an earlier note here said it was. "
        "Swept over 150/200/300/360/400/600/720 dpi on a 300-patch A4, seam "
        "pixels: SS pointy 80/0/0/0/81/54/372; CR30 pointy 78/192/365/1222/48/"
        "0/0; CR30 rotated 0/40/250/214/0/0/0. It is arbitrary in the "
        "resolution, every hex-capable instrument has it at some resolutions, "
        "and NO resolution is clean for all of them, so 'render higher' is not "
        "a workaround. "
        "THREE FIXES WERE TRIED AND ALL COST MORE THAN THEY PAID: growing every "
        "hexagon half a pixel closed it but made neighbours visibly overlap and "
        "widened an SS patch by 3 px, breaking the measured four-thirds "
        "relation; deriving one stagger for the whole page closed the vertical "
        "seams and opened more diagonal ones, 270 -> 714; drawing each polygon's "
        "own outline in its fill colour took 270 -> 264. The real fix is a "
        "shared vertex lattice, where neighbouring hexagons take the SAME "
        "rounded coordinates for the edge they share, and that is its own piece "
        "of work.")), id="300"),
    600,
])
def test_a_honeycomb_has_no_seams_between_its_patches(flat_top, spacer_mode, dpi):
    """No bare paper between the patches of a honeycomb.

    Green at 600 dpi and an expected failure at 300, which is the DEFAULT a
    chart is built at (`chart.build_chart`, `LayoutRecipe.dpi`), so this is a
    defect a user meets and not a curiosity. Strict, so the day somebody fixes
    it this test says so instead of quietly passing.
    """
    _res, img, _ = _render(flat_top, spacer_mode, dpi=dpi, palette=NO_WHITE)
    ys, xs = np.nonzero(np.any(img < 250, axis=2))
    y0, y1 = int(np.percentile(ys, 20)), int(np.percentile(ys, 80))
    x0, x1 = int(np.percentile(xs, 20)), int(np.percentile(xs, 80))
    seams = int(np.all(img[y0:y1, x0:x1] > 245, axis=2).sum())
    assert seams == 0, (
        f"{seams} pixels of bare paper inside the patch field at {dpi} dpi"
    )
