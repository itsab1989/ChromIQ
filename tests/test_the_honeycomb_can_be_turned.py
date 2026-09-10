"""The CR30 honeycomb, turned 30 degrees so its strips run straight (#159).

Basti asked for it after a CR30 user's report: *"currently the rows are
staggered ... if those hexagons would be rotated by 60 degree I think this would
change"*. Measured, the turn that straightens a strip is 30 degrees, and he
settled the label at that (*"the let it say 30° if this is right"*).

WHAT THE OPTION IS, IN ONE LINE: the same hexagon, stood on a flat side instead
of on a point. Not a different shape, not a stretched one. His ruling of
2026-09-09 is explicit -- *"the rotation should not stretch them"* -- so the
first test here measures six equal sides off the pooled geometry and the second
measures the drawn ink.

THE FOUR REGRESSION SHAPES. Four faults were fixed on 2026-09-08 in the same
family of per-instrument controls, and every one of them would apply to this
option unchanged. `ff3d1b2b`'s commit message is the reason they are all here:
**"NOTHING CAUGHT IT. The review's mutation, memory always wins, passed the
whole gate: 11980 passed, exit 0. The hole was that every test asserted on the
widget."** So these assert on the built `Geom` and on the stored recipe, and the
widget only where the guarantee is about the widget.

  1. `ff3d1b2b` a per-instrument MEMORY restored a value on an app-driven
     instrument change. This feature has no memory; the test exists so that
     adding one later goes red.
  2. `ca0f639c` a hidden control reached the build through a neighbour. NOT
     hypothetical here: gating the turn on `hflag` alone -- which is the obvious
     implementation -- lets a tick made on a CR30 build a flat-top SpectroScan
     chart from a box that instrument never showed.
  3. `e1aeaf2f` `setChecked(False)` on an already-false box emits nothing, so a
     round trip has to be run in BOTH directions.
  4. `d1adbe31` a saved default overwrote a run's stored answer.
"""
from __future__ import annotations

import dataclasses
import json
import math
import os

import types
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from workflow.layout_engine import geometry as G          # noqa: E402
from workflow.layout_engine import hexagon                # noqa: E402
from workflow.layout_engine import instruments as I       # noqa: E402
from workflow.layout_engine.presets import LayoutRecipe   # noqa: E402

A4 = (210.0, 297.0)
DPI = 300


def _rects(flat_top: bool, key: str = "CR30", n: int = 300):
    g = I.build(key, hflag=True, hex_flat_top=flat_top)
    lay = G.compute(g, *A4, n)
    return g, lay, [r for r in G.patch_rects_px(g, *A4, lay, DPI)
                    if r["page"] == 0]


# ---------------------------------------------------------------------------
# the shape: turned, never stretched
# ---------------------------------------------------------------------------
def test_a_turned_hexagon_is_still_a_regular_hexagon():
    """Ruling 3's only mechanical defence. A stretched hexagon is the exact
    fault `area_fit` already carries a comment about (+17 % on a SpectroScan,
    +20 % on a CR30), and it is invisible in a thumbnail."""
    g = I.build("CR30", hflag=True, hex_flat_top=True)
    pts = hexagon.vertices(0, 0, g.pwid, g.plen, flat_top=True)
    sides = [math.dist(pts[i], pts[(i + 1) % 6]) for i in range(6)]
    assert max(sides) - min(sides) < 1e-9, f"not regular: {sides}"

    flat = I.build("CR30", hflag=True, hex_flat_top=False)
    ppts = hexagon.vertices(0, 0, flat.pwid, flat.plen)
    psides = [math.dist(ppts[i], ppts[(i + 1) % 6]) for i in range(6)]
    assert sides[0] == pytest.approx(psides[0]), (
        "the turned hexagon is a different SIZE from the one it replaces; the "
        "turn must not resize the patch"
    )


def test_the_bounding_box_transposes_exactly():
    """Same hexagon, turned: width and height swap and nothing else moves."""
    g = I.build("CR30", hflag=True, hex_flat_top=True)
    f = I.build("CR30", hflag=True, hex_flat_top=False)
    assert g.pwid == pytest.approx(f.plen)
    assert g.plen == pytest.approx(f.pwid)


# ---------------------------------------------------------------------------
# the point of the feature: a straight strip
# ---------------------------------------------------------------------------
def test_the_turned_lattice_has_a_straight_strip():
    """THE FEATURE'S WHOLE VALUE, asserted on geometry rather than on a picture.

    A strip must be one column of x, and adjacent strips must be offset by half
    a patch so the honeycomb still interlocks. Without the second half it is not
    a honeycomb any more, it is a grid.
    """
    g, lay, rects = _rects(True)
    steps = lay.steps_in_pass
    strip0 = rects[:steps]
    assert len({r["x"] for r in strip0}) == 1, (
        "the strip still zigzags: " + str(sorted({r["x"] for r in strip0}))
    )
    if len(rects) > steps:
        a, b = rects[0], rects[steps]
        assert b["y"] != a["y"], "adjacent strips do not interlock at all"
        assert abs(b["y"] - a["y"]) == pytest.approx(
            round(a["h"] / 4) * 2, abs=2), \
            "adjacent strips are not offset by half a patch"


def test_the_untouched_orientation_still_zigzags():
    """The control. If the pointy lattice had quietly straightened too, the test
    above would pass for the wrong reason."""
    g, lay, rects = _rects(False)
    strip0 = rects[:lay.steps_in_pass]
    assert len({r["x"] for r in strip0}) == 2, \
        "the pointy honeycomb stopped staggering"


def test_the_recorded_boxes_still_describe_where_the_ink_is():
    """The 2026-08-13 fault, re-run for the new orientation: the recorded box
    and the drawn ink drifting apart is a half-patch mis-registration in every
    consumer (the Measure highlight, the margin inspector, scanin_target) rather
    than a visible bug. Rendered and measured, not reasoned."""
    import tempfile
    from pathlib import Path

    import numpy as np
    from PIL import Image

    from workflow.layout_engine import chart as le_chart

    d = Path(tempfile.mkdtemp())
    N = 300

    def col(i):
        return (i // 100) * 30 + 5, ((i // 10) % 10) * 10 + 3, (i % 10) * 10 + 3

    lines = ["CTI1", "", 'DESCRIPTOR "turn"', 'ORIGINATOR "ChromIQ"',
             'KEYWORD "SAMPLE_LOC"', "NUMBER_OF_FIELDS 7", "BEGIN_DATA_FORMAT",
             "SAMPLE_ID RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z", "END_DATA_FORMAT",
             f"NUMBER_OF_SETS {N}", "BEGIN_DATA"]
    for i in range(N):
        r, g_, b = col(i)
        lines.append(f"{i+1} {r}.0 {g_}.0 {b}.0 40 45 50")
    lines += ["END_DATA", ""]
    ti1 = d / "p.ti1"
    ti1.write_text("\n".join(lines), encoding="utf-8")

    import json
    sub = d / "out"
    sub.mkdir()
    le_chart.build_chart(ti1, sub / "c", instrument="CR30", paper="A4",
                         hflag=True, hex_flat_top=True, dpi=DPI,
                         randomize=False, spacer_mode="none")
    a = np.asarray(Image.open(sorted(sub.glob("*.tif"))[0])
                   .convert("RGB")).astype(int)
    pats = [p for p in json.loads((sub / "c.strips.json").read_text(encoding="utf-8"))["patches"]
            if p.get("page", 0) == 0]
    worst, checked = 0.0, 0
    for r in pats:
        cx, cy = r["x"] + r["w"] // 2, r["y"] + r["h"] // 2
        if not (0 <= cy < a.shape[0] and 0 <= cx < a.shape[1]):
            continue
        centre = tuple(a[cy, cx])
        if centre == (255, 255, 255):
            continue
        pad = max(r["w"], r["h"])
        y0, y1 = max(0, cy - pad), min(a.shape[0], cy + pad)
        x0, x1 = max(0, cx - pad), min(a.shape[1], cx + pad)
        m = np.all(a[y0:y1, x0:x1] == np.array(centre), axis=2)
        ys, xs = np.nonzero(m)
        if len(xs) < 50:
            continue
        worst = max(worst, ((xs.mean() + x0 - cx) ** 2
                            + (ys.mean() + y0 - cy) ** 2) ** 0.5)
        checked += 1
    assert checked > 200, f"only {checked} patches measured; this proves little"
    assert worst < 6.0, (
        f"the recorded box centre is {worst:.1f} px from the ink centroid on a "
        f"{pats[0]['w']}x{pats[0]['h']} px patch"
    )


# ---------------------------------------------------------------------------
# the ruler comb follows the turn
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("flat_top", [False, True])
def test_the_comb_that_survives_is_the_one_that_lands(flat_top):
    """Basti: *"but will markers on top and bottom also be allowed?"* -- *"those
    are the ones that make sense once the honeycomb is rotated."* They are, and
    the axes invert with the turn, so a gate that only asked `is_hexagonal`
    would keep the wrong comb on a turned sheet: the same fault `9ec5e921`
    corrected, one orientation along."""
    mm = 25.4 / DPI
    g, lay, rects = _rects(flat_top)
    cx = sorted({round((r["x"] + r["w"] / 2) * mm, 4) for r in rects})
    cy = sorted({round((r["y"] + r["h"] / 2) * mm, 4) for r in rects})

    real = I.is_hexagonal
    I.is_hexagonal = lambda _g: False       # measure BOTH, refusal bypassed
    try:
        tb = sorted({round(l[0], 4) for l in G.helper_marker_lines_mm(
            g, *A4, lay, top_bottom=True, sides=False)})
        sd = sorted({round(l[1], 4) for l in G.helper_marker_lines_mm(
            g, *A4, lay, top_bottom=False, sides=True)})
    finally:
        I.is_hexagonal = real
    err_tb = max(min(abs(c - m) for m in tb) for c in cx)
    err_sd = max(min(abs(c - m) for m in sd) for c in cy)

    kept_tb = bool(G.helper_marker_lines_mm(g, *A4, lay, top_bottom=True,
                                            sides=False))
    kept_sd = bool(G.helper_marker_lines_mm(g, *A4, lay, top_bottom=False,
                                            sides=True))
    assert kept_tb != kept_sd, "a honeycomb kept both combs or neither"
    kept_err, dropped_err = (err_tb, err_sd) if kept_tb else (err_sd, err_tb)
    assert kept_err < 0.2, (
        f"the surviving comb misses a patch centre by {kept_err:.4f} mm"
    )
    assert dropped_err > 1.0 and kept_err < dropped_err / 10.0, (
        f"kept {kept_err:.4f} mm vs dropped {dropped_err:.4f} mm -- the "
        "surviving comb is not clearly the better one"
    )


# ---------------------------------------------------------------------------
# the four regression shapes
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("key", ["SS", "CM", "i1", "p3", "41", "51"])
@pytest.mark.parametrize("hflag", [False, True])
def test_the_turn_cannot_reach_any_other_chart(key, hflag):
    """`ca0f639c`, AND IT IS NOT HYPOTHETICAL. Hiding must never untick, so a
    tick made on a CR30 stays in the recipe when the user moves to a SpectroScan
    honeycomb. If `build()` gated the turn on `hflag` alone, that recipe would
    build a flat-top SpectroScan chart from a box its owner was never shown.

    Generated over every instrument and both flags, so a new hex-capable
    instrument is covered the day it is added.
    """
    on = dataclasses.asdict(I.build(key, hflag=hflag, hex_flat_top=True))
    off = dataclasses.asdict(I.build(key, hflag=hflag, hex_flat_top=False))
    assert on == off, (
        f"{key} hflag={hflag}: the turn changed a chart it was never offered on"
    )


def test_the_turn_is_inert_on_a_rectangular_cr30():
    """The other half of the same rule: the flag must not act when the honeycomb
    itself is off, or a user who turns hexagons off keeps a silent change."""
    on = dataclasses.asdict(I.build("CR30", hflag=False, hex_flat_top=True))
    off = dataclasses.asdict(I.build("CR30", hflag=False, hex_flat_top=False))
    assert on == off
    assert I.build("CR30", hflag=False, hex_flat_top=True).hex_flat_top is False


def test_only_the_cr30_honeycomb_carries_it():
    assert I.build("CR30", hflag=True, hex_flat_top=True).hex_flat_top is True
    for key in ("SS", "CM", "i1"):
        assert I.build(key, hflag=True, hex_flat_top=True).hex_flat_top is False


def test_the_key_is_in_the_capacity_chokepoint():
    """`GEOM_BUILD_KEYS` is the filter `geom_from_build_kwargs` applies. A field
    missing from it is dropped silently, and every capacity readout in the app
    then disagrees with the render."""
    assert "hex_flat_top" in I.GEOM_BUILD_KEYS
    kw = {"instrument": "CR30", "paper": "A4", "hflag": True,
          "hex_flat_top": True}
    assert I.geom_from_build_kwargs(kw).hex_flat_top is True


@pytest.mark.parametrize("value", [True, False])
def test_the_recipe_round_trips_in_both_directions(value):
    """`e1aeaf2f`: `setChecked(False)` on an already-false box emits no signal,
    so an implementation that depended on the emit would drop exactly one of
    these two directions. Both are asserted."""
    r = LayoutRecipe(instrument="CR30", paper="A4", hflag=True,
                     hex_flat_top=value)
    back = LayoutRecipe.from_dict(r.to_dict())
    assert back.hex_flat_top is value
    assert r.build_kwargs()["hex_flat_top"] is value


def test_a_recipe_written_before_this_field_loads_with_the_turn_off():
    """`d1adbe31`'s neighbourhood: every chart built before #159 must open
    exactly as it did, and an absent key is the only signal there is."""
    d = LayoutRecipe(instrument="CR30", paper="A4", hflag=True).to_dict()
    d.pop("hex_flat_top", None)
    assert LayoutRecipe.from_dict(d).hex_flat_top is False


# ---------------------------------------------------------------------------
# what an adversarial review found afterwards
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("flat_top", [False, True])
def test_resizing_a_patch_keeps_the_right_overhang_on_the_right_axis(flat_top):
    """P6, AND IT PRINTED OUTSIDE THE USER'S MARGIN.

    `build()` re-derives the two overhangs whenever a patch size is set, and it
    restated only the pointy-top halves: `hxeh = plen/6`, `hxew = 0.25*pwid`. On
    a rotated chart those are the wrong way round, so the STAGGER reserve came
    out 2.0200 mm where 3.0300 was needed and the APEX reserve 2.6241 where
    1.7494 was.

    Under-reserving the stagger is ink outside the margin: measured on a sheet
    with all four margins set to 20 mm, the rotated chart reached 19.050 mm top
    and 18.965 mm bottom. Over-reserving the apex threw away 0.9 mm of page on
    the other axis.

    It fires on EVERY area-first build, because `geom_from_build_kwargs` derives
    `patch_w`/`patch_h` and feeds them straight back in, and on every Manual
    patch size. Which is to say: almost always.
    """
    base = I.build("CR30", hflag=True, hex_flat_top=flat_top)
    g = I.build("CR30", hflag=True, hex_flat_top=flat_top,
                patch_w=base.pwid * 1.01, patch_h=base.plen * 1.01)
    if flat_top:
        assert g.hxeh == pytest.approx(g.plen / 4.0), "the stagger reserve"
        assert g.hxew == pytest.approx(g.pwid / 6.0), "the apex reserve"
    else:
        assert g.hxeh == pytest.approx(g.plen / 6.0)
        assert g.hxew == pytest.approx(0.25 * g.pwid)


def test_a_resized_rotated_chart_stays_inside_its_margins():
    """The same fault measured where the user meets it: on paper."""
    import tempfile
    from pathlib import Path

    import numpy as np
    from PIL import Image

    from workflow.layout_engine import chart as le_chart

    d = Path(tempfile.mkdtemp())
    lines = ["CTI1", "", 'DESCRIPTOR "m"', 'ORIGINATOR "ChromIQ"',
             'KEYWORD "SAMPLE_LOC"', "NUMBER_OF_FIELDS 7", "BEGIN_DATA_FORMAT",
             "SAMPLE_ID RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z", "END_DATA_FORMAT",
             "NUMBER_OF_SETS 200", "BEGIN_DATA"]
    for i in range(200):
        lines.append(f"{i+1} 20.0 20.0 20.0 40 45 50")
    lines += ["END_DATA", ""]
    ti1 = d / "p.ti1"
    ti1.write_text("\n".join(lines), encoding="utf-8")

    M, dpi = 20.0, 600
    for flat_top in (False, True):
        out = d / f"ft{flat_top}"
        out.mkdir()
        le_chart.build_chart(ti1, out / "c", instrument="CR30", paper="A4",
                             hflag=True, hex_flat_top=flat_top, dpi=dpi,
                             randomize=False, spacer_mode="none",
                             margins=(M, M, M, M), patch_w=12.12, patch_h=14.0,
                             draw_indicators=False)
        a = np.asarray(Image.open(sorted(out.glob("*.tif"))[0])
                       .convert("RGB")).astype(int)
        ys, xs = np.nonzero(np.any(a < 250, axis=2))
        mm = 25.4 / dpi
        edges = {"top": ys.min() * mm, "left": xs.min() * mm,
                 "bottom": (a.shape[0] - 1 - ys.max()) * mm,
                 "right": (a.shape[1] - 1 - xs.max()) * mm}
        outside = {k: v for k, v in edges.items() if v < M - 0.1}
        assert not outside, (
            f"flat_top={flat_top}: ink printed outside a {M} mm margin: "
            f"{ {k: round(v, 3) for k, v in outside.items()} }"
        )


def test_a_row_number_sits_on_the_patch_it_names():
    """P8, FOUND BY EYE IN A RENDERED SHEET. The row label's y was the
    UNSTAGGERED slot centre, which is right for every chart whose leftmost strip
    does not move -- true of the ColorMunki rig stagger, which shifts only ODD
    strips while the labels sit beside strip 0. A rotated honeycomb staggers
    EVERY strip, strip 0 upward by a quarter patch, so each number was drawn
    3.006 mm below the patch it names, on every row of every page.

    MEASURED OFF THE RENDERED SHEET. A first version of this test recomputed the
    label's position from the same expression the renderer uses and so stayed
    green under a mutation that put the bug straight back -- the third time in
    this work that recomputing instead of reading the ink produced a test that
    could not fail. It compares the CENTROID of all row-label ink against the
    centroid of the patch centres it labels, which a uniform offset moves and
    which needs no fragile per-glyph grouping.
    """
    import tempfile
    from pathlib import Path

    import numpy as np
    from PIL import Image

    from workflow.layout_engine import chart as le_chart

    d = Path(tempfile.mkdtemp())
    lines = ["CTI1", "", 'DESCRIPTOR "r"', 'ORIGINATOR "ChromIQ"',
             'KEYWORD "SAMPLE_LOC"', "NUMBER_OF_FIELDS 7", "BEGIN_DATA_FORMAT",
             "SAMPLE_ID RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z", "END_DATA_FORMAT",
             "NUMBER_OF_SETS 200", "BEGIN_DATA"]
    for i in range(200):
        lines.append(f"{i+1} 40.0 40.0 40.0 40 45 50")
    lines += ["END_DATA", ""]
    ti1 = d / "p.ti1"
    ti1.write_text("\n".join(lines), encoding="utf-8")

    dpi = 600
    mm = 25.4 / dpi
    offs: dict[bool, float] = {}
    for flat_top in (False, True):
        out = d / f"ft{flat_top}"
        out.mkdir()
        le_chart.build_chart(ti1, out / "c", instrument="CR30", paper="A4",
                             hflag=True, hex_flat_top=flat_top, dpi=dpi,
                             randomize=False, spacer_mode="none")
        img = np.asarray(Image.open(sorted(out.glob("*.tif"))[0])
                         .convert("RGB")).astype(int)
        # THE SIDECAR'S OWN RECTS, not a geometry rebuilt here. `build_chart`
        # goes through `geom_from_build_kwargs`, which reserves a 9.4 mm row
        # band and moves the left margin with it; rebuilding from
        # `instruments.build` gives a different sheet entirely, and a probe that
        # did that reported the labels 50 mm out of place on BOTH orientations.
        strips = json.loads((out / "c.strips.json").read_text(encoding="utf-8"))
        rects = [r for r in strips["patches"] if r.get("page", 0) == 0]
        steps = strips["steps_in_pass"]
        # STRIP 0 BY SLOT INDEX, not by "leftmost x": on a pointy sheet the
        # patches zigzag, so the leftmost x belongs to alternating steps of two
        # different strips and is not the column the labels name.
        col = sorted(rects[:steps], key=lambda r: r["y"])
        left_x = min(r["x"] for r in rects)

        # THE ROW-LABEL BAND ONLY, which is the ~7.5 mm strip immediately left
        # of the patches. "Everything left of the patch field" also catches the
        # CR30's clip/notes band, whose rotated text runs most of the page
        # height and dragged the centroid 50 mm on both orientations.
        band_px = int(round(9.0 * dpi / 25.4))
        x1 = max(1, left_x - 6)
        x0 = max(0, x1 - band_px)
        band = np.all(img[:, x0:x1] < 60, axis=2)
        ys = np.nonzero(band.any(axis=1))[0]
        assert len(ys), "no row-label ink found at all"
        # only the rows this column spans, so the strip letters along the top
        # cannot drag the centroid
        lo = min(r["y"] for r in col)
        hi = max(r["y"] + r["h"] for r in col)
        ys = ys[(ys >= lo) & (ys <= hi)]
        assert len(ys) > 50, f"only {len(ys)} rows of label ink in range"
        label_centre = float(ys.mean())
        patch_centre = float(np.mean([r["y"] + r["h"] / 2.0 for r in col]))
        offs[flat_top] = (label_centre - patch_centre) * mm

    # COMPARE THE TWO ORIENTATIONS, do not judge either alone. A centroid over
    # digit ink carries a systematic bias of about 1.5 mm, because "1" and "18"
    # are not the same shape and the top and bottom rows are clipped
    # differently. That bias is identical on both sheets, so it cancels -- and
    # the fault this guards is a 3.006 mm shift of ONE of them.
    drift = abs(offs[True] - offs[False])
    assert drift < 1.0, (
        f"the row numbers sit {drift:.3f} mm further from their patches on a "
        f"rotated sheet than on a pointy one (pointy {offs[False]:+.3f} mm, "
        f"rotated {offs[True]:+.3f} mm): the labels are not following the "
        "strip's stagger"
    )


@pytest.mark.parametrize("key", ["SS", "i1", "CM"])
@pytest.mark.parametrize("hflag", [True, False])
def test_the_sidecar_flag_is_resolved_and_not_read_raw(key, hflag):
    """P7, AND IT IS THE ca0f639c SHAPE ONE LEVEL UP. The Geom is protected by a
    single writer, but the SIDECAR records the recipe, and hiding the control
    must never untick it -- so a tick made on a CR30 is still in the recipe
    after the user moves to a SpectroScan. Every reader that asked the recipe
    directly answered True for a SpectroScan honeycomb, and for a rectangular
    chart, and the Measure overlay then drew flat-top hexagons over pointy ink.
    """
    from workflow.hex_support import recipe_is_flat_top
    rec = {"instrument": key, "hflag": hflag, "hex_flat_top": True}
    assert recipe_is_flat_top(rec) is False
    assert recipe_is_flat_top(
        {"instrument": "CR30", "hflag": False, "hex_flat_top": True}) is False
    assert recipe_is_flat_top(
        {"instrument": "CR30", "hflag": True, "hex_flat_top": True}) is True


# ---------------------------------------------------------------------------
# the gaps the pentest found in these very tests
# ---------------------------------------------------------------------------
def _multipage(flat_top: bool, patches: int = 1400, dpi: int = 150,
               edge_spacers: bool = True):
    """A real multi-page rotated build, with its sidecar rects."""
    import tempfile
    from pathlib import Path

    from workflow.layout_engine import chart as le_chart

    d = Path(tempfile.mkdtemp())
    lines = ["CTI1", "", 'DESCRIPTOR "mp"', 'ORIGINATOR "ChromIQ"',
             'KEYWORD "SAMPLE_LOC"', "NUMBER_OF_FIELDS 7", "BEGIN_DATA_FORMAT",
             "SAMPLE_ID RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z", "END_DATA_FORMAT",
             f"NUMBER_OF_SETS {patches}", "BEGIN_DATA"]
    for i in range(patches):
        lines.append(f"{i+1} {(i*7)%100}.0 {(i*13)%100}.0 {(i*29)%100}.0 40 45 50")
    lines += ["END_DATA", ""]
    ti1 = d / "p.ti1"
    ti1.write_text("\n".join(lines), encoding="utf-8")
    out = d / "o"
    out.mkdir()
    res = le_chart.build_chart(ti1, out / "c", instrument="CR30", paper="A4",
                              hflag=True, hex_flat_top=flat_top, dpi=dpi,
                              randomize=False, spacer_mode="colored",
                              edge_spacers=edge_spacers)
    strips = json.loads((out / "c.strips.json").read_text(encoding="utf-8"))
    return res, strips, out


def test_the_stagger_is_indexed_by_the_GLOBAL_strip_across_pages():
    """E7, AND IT IS THE WORST OF THE SIX THE PENTEST FOUND.

    `patch_rects_px` indexes the rotated stagger by `(first // steps) + p`, the
    strip's position on the SHEET, not by `p`, its position on the page. Where a
    page holds an odd number of strips those two disagree from page 1 onward,
    and the mutation moves every recorded box on the odd pages by half a patch
    pitch WHILE LEAVING THE PRINTED SHEET BYTE-IDENTICAL -- the renderer already
    uses the global index. Nothing in the suite noticed: the whole everyday tier
    stayed green at 12,395 passed.

    That is exactly the "the recorded box describes a place no ink is" fault the
    code comments warn about twice, and it is invisible to any test that renders
    one page or asserts on pixels.

    Asserted on the LATTICE rather than on the index: within a page, and across
    the page boundary, consecutive strips must alternate their offset. If a page
    starts on the wrong parity, two neighbouring strips end up staggered the
    same way and the honeycomb stops interlocking there.
    """
    res, strips, _ = _multipage(True)
    assert res.layout.pages >= 3, f"only {res.layout.pages} pages"
    steps = strips["steps_in_pass"]
    rects = strips["patches"]
    per_page = res.layout.patches_per_page
    assert per_page // steps % 2 == 1, (
        "this fixture must have an ODD number of strips per page, or the page "
        "index and the sheet index agree and the mutation is invisible"
    )
    # the y of step 0 of every strip, in sheet order
    firsts = [rects[k * steps]["y"] for k in range(len(rects) // steps)]
    base = min(firsts)
    parities = [round((y - base) / max(1, (max(firsts) - base) or 1)) for y in firsts]
    for k in range(len(firsts) - 1):
        assert firsts[k] != firsts[k + 1], (
            f"strips {k} and {k+1} sit at the same height, so the honeycomb "
            "stops interlocking there (this is the page-boundary parity)"
        )


def test_the_ring_neighbour_lookup_is_page_scoped():
    """E10. The neighbour a ring side is coloured against must be looked up
    WITHIN the page: a patch at the bottom of page 1 has paper below it, not the
    patch that happens to follow it in the sheet's numbering. Getting this wrong
    changes only the page seam, which is why no single-page test can see it."""
    _res, strips, out = _multipage(True)
    import numpy as np
    from PIL import Image
    tifs = sorted(out.glob("*.tif"))
    assert len(tifs) >= 3
    # The LAST strip of a page must have paper (or an edge band) beyond it, not
    # a neighbour's colour: measured as the sheet ending in white on every page.
    for t in tifs:
        a = np.asarray(Image.open(t).convert("RGB")).astype(int)
        assert np.all(a[-2] > 245), f"{t.name} does not end in paper"


@pytest.mark.parametrize("flat_top", [False, True])
def test_the_base_geometry_reserves_the_right_overhangs(flat_top):
    """E3, missed by the whole everyday tier. `_build_base` sets both overhangs
    for a rotated CR30 and the two are NOT interchangeable: `hxeh` is the
    STAGGER (a quarter) and `hxew` the APEX (a sixth), and the turn swaps which
    sits on which axis. The resized case is guarded above; this is the
    unresized one, which is what every default build uses."""
    g = I.build("CR30", hflag=True, hex_flat_top=flat_top)
    if flat_top:
        assert g.hxeh == pytest.approx(g.plen / 4.0)
        assert g.hxew == pytest.approx(g.pwid / 6.0)
    else:
        assert g.hxeh == pytest.approx(g.plen / 6.0)
        assert g.hxew == pytest.approx(0.25 * g.pwid)
    assert g.hxeh != pytest.approx(g.hxew), \
        "the two reserves collapsed onto one value, so a swap is undetectable"


def test_the_row_label_band_clears_the_apex_and_not_the_stagger():
    """E9. The row numbers are pushed left to clear whatever of the leftmost
    patch sticks out past its slot. On a pointy sheet that is the STAGGER, a
    quarter of the width; on a rotated one it is the APEX, a sixth. Using a
    quarter on a rotated sheet reserves 3.0 mm where 1.73 is needed and pushes
    every number away from its patch.

    Measured off the rendered sheet: the gap between the right edge of the
    label ink and the leftmost patch ink.
    """
    import tempfile
    from pathlib import Path

    import numpy as np
    from PIL import Image

    from workflow.layout_engine import chart as le_chart

    d = Path(tempfile.mkdtemp())
    lines = ["CTI1", "", 'DESCRIPTOR "e9"', 'ORIGINATOR "ChromIQ"',
             'KEYWORD "SAMPLE_LOC"', "NUMBER_OF_FIELDS 7", "BEGIN_DATA_FORMAT",
             "SAMPLE_ID RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z", "END_DATA_FORMAT",
             "NUMBER_OF_SETS 200", "BEGIN_DATA"]
    for i in range(200):
        lines.append(f"{i+1} 40.0 40.0 40.0 40 45 50")
    lines += ["END_DATA", ""]
    ti1 = d / "p.ti1"
    ti1.write_text("\n".join(lines), encoding="utf-8")

    dpi = 600
    gaps = {}
    for flat_top in (False, True):
        out = d / f"f{flat_top}"
        out.mkdir()
        le_chart.build_chart(ti1, out / "c", instrument="CR30", paper="A4",
                             hflag=True, hex_flat_top=flat_top, dpi=dpi,
                             randomize=False, spacer_mode="none")
        img = np.asarray(Image.open(sorted(out.glob("*.tif"))[0])
                         .convert("RGB")).astype(int)
        strips = json.loads((out / "c.strips.json").read_text(encoding="utf-8"))
        left_x = min(r["x"] for r in strips["patches"])
        band_px = int(round(9.0 * dpi / 25.4))
        x1 = max(1, left_x - 2)
        x0 = max(0, x1 - band_px)
        dark = np.all(img[:, x0:x1] < 60, axis=2)
        cols = np.nonzero(dark.any(axis=0))[0]
        assert len(cols), f"flat_top={flat_top}: no row-label ink found"
        label_right = x0 + int(cols.max())
        # MEASURE TO THE INK, NOT TO THE RECT. A rotated hexagon's apex sticks
        # out a sixth of the width LEFT of its recorded box, so a gap measured
        # to `left_x` is overstated by 1.73 mm on a rotated sheet and by nothing
        # on a pointy one -- which is how a first version of this test decided
        # the rotated labels were further away when the clearance to ink is the
        # same 1.45 mm on both.
        row = np.any(img < 250, axis=2)
        patch_cols = np.nonzero(row[:, label_right + 1:].any(axis=0))[0]
        assert len(patch_cols), "no patch ink to the right of the labels"
        gaps[flat_top] = float(patch_cols.min() + 1) * 25.4 / dpi

    # The labels must clear the leftmost INK by about the same distance either
    # way: the band is sized to whatever sticks out, and that is a quarter of
    # the width on a pointy sheet and a sixth on a rotated one. Reserving the
    # quarter on both pushes the rotated numbers 1.3 mm further from their
    # patches for nothing.
    assert abs(gaps[True] - gaps[False]) < 0.6, (
        f"the row numbers clear {gaps[True]:.2f} mm of ink on a rotated sheet "
        f"and {gaps[False]:.2f} mm on a pointy one; the band is reserving the "
        "wrong overhang on one of them"
    )


@pytest.mark.parametrize("key", ["SS", "i1", "CM"])
def test_the_reported_patch_size_resolves_the_flag_too(key):
    """F1. `recipe_is_flat_top` was added and two readers in Create Chart kept
    asking the recipe raw, so a SpectroScan honeycomb carrying a stale CR30
    tick was REPORTED as 10.67 x 6.93 mm on a "column pitch" when it prints
    8.00 x 9.24 mm on a row pitch. The number a user reads off the panel and
    the sheet in their hand disagreed."""
    from ui.tabs.tab_chart import _panel_patch_size_mm
    from workflow.hex_support import recipe_is_flat_top

    rec = {"instrument": key, "hflag": True, "hex_flat_top": True}
    assert recipe_is_flat_top(rec) is False
    g = I.build(key, hflag=True)
    # what the panel must show for this chart: the POINTY correction
    pw, ph, pitch = _panel_patch_size_mm(g.pwid, g.plen, True,
                                         recipe_is_flat_top(rec))
    assert pw == pytest.approx(g.pwid), \
        "the width was corrected, so the flag reached a chart that is not turned"
    assert ph > g.plen, "the height was not corrected, so nothing was applied"


def test_no_reader_outside_the_engine_asks_the_flag_raw():
    """The guard on the guard. `hex_flat_top` may be read raw in exactly three
    places: the dataclass that stores it, the builder that resolves it, and the
    checkbox that shows it. Anywhere else is a reader that can be handed a tick
    made on a different instrument.

    A WRITER INSIDE A RESOLVED BRANCH IS NOT A READER. Guided sets the flag for
    its own charts in two places -- the build and the estimate that must mirror
    it -- and both sit inside `if instr == "CR30" and guided:` / the CR30 branch
    of `_engine_build_kwargs`, which is the resolution this test exists to
    demand. They are matched below by their exact text, so a bare read in
    either file is still an offender.
    """
    import pathlib
    import re

    root = pathlib.Path(__file__).resolve().parents[1]
    allowed = {"workflow/layout_engine/instruments.py",
               "workflow/layout_engine/presets.py",
               "workflow/layout_engine/geometry.py",
               "workflow/layout_engine/area_fit.py",
               "workflow/layout_engine/chart.py",
               "workflow/hex_support.py",
               "ui/dialogs/layout_options_panel.py",
               # The scanner marquee holds the orientation as its OWN state, on
               # the GridSpec, the way the preview holds `_hex_flat_top`. It is
               # fed from `recipe_is_flat_top` at the one call site, which the
               # next test pins so this allowance cannot become a hole.
               "ui/scan_grid_marquee.py"}
    offenders = []
    for path in list(root.glob("ui/**/*.py")) + list(root.glob("workflow/**/*.py")):
        rel = path.relative_to(root).as_posix()
        if rel in allowed:
            continue
        text = path.read_text(encoding="utf-8")
        for m in re.finditer(r'^.*hex_flat_top.*$', text, re.M):
            line = m.group(0)
            if line.lstrip().startswith("#"):
                continue          # a comment naming the field is not a read
            if ("recipe_is_flat_top" in line or "chart_is_flat_top" in line
                    or "geom" in line or "Geom" in line
                    # a widget's OWN state, which is fed by a resolver: the
                    # preview's `_hex_flat_top` comes from `chart_is_flat_top`
                    or "self._hex_flat_top" in line
                    or "flat_top=flat_top" in line
                    # Guided's own two writers, already inside a branch that
                    # names the instrument and the patch shape. Matched
                    # exactly, so this is not a licence for that file.
                    or 'kw["hex_flat_top"] = bool(kw.get("hflag"))' in line):
                continue          # the RESOLVED value is fine
            offenders.append(f"{rel}: {line.strip()[:90]}")
    assert not offenders, (
        "these read the flag without resolving it against the instrument and "
        "the patch shape:\n  " + "\n  ".join(offenders)
    )


def test_the_scanner_mesh_is_told_the_orientation_by_a_resolver(monkeypatch):
    """The allowance above is only safe while the mesh's own state is FED by a
    resolver. H5: `GridSpec` had no orientation at all and `_cell_uv` called
    `hexagon.vertices()` with no `flat_top`, so the alignment guide drew pointy
    cells 30 degrees off the ink on every turned honeycomb. scanin still read
    the right area -- the sampled box is rectangular and comes from the
    recorded rects -- but the picture the user aligns BY was wrong, which is
    the one job that overlay has."""
    import inspect

    from ui.dialogs import scanin_dialog
    from ui.scan_grid_marquee import GridSpec, ScanGridMarquee

    assert "hex_flat_top" in {f.name for f in __import__("dataclasses")
                              .fields(GridSpec)}, \
        "GridSpec cannot carry the orientation at all"
    # NOT A SUBSTRING. The version this replaces asserted `"flat_top=_flat" in
    # src`, which is satisfied by `_flat = False` sitting anywhere above it:
    # setting that line's right-hand side to False restored the whole defect --
    # pointy cells 30 degrees off the ink on every turned chart, photographed --
    # and the full everyday gate stayed green at 12,475 passed. That is the
    # seventh self-validating test in this feature.
    #
    # So drive the real dialog instead and read what it produced: the mesh's own
    # orientation, and the sample cap, both of which come from the same resolved
    # value. A `_flat` stuck at False fails both.
    dlg = _scanner_dialog_over_a_turned_chart(monkeypatch)
    assert dlg is not None, "could not open the scanner dialog over a chart"
    grid = dlg._marquee._grid
    assert getattr(grid, "hex_flat_top", None) is True, (
        "the dialog built its mesh without the orientation, so the alignment "
        "guide draws pointy cells over flat-top ink"
    )
    # K12: THE ORIENTATION IS NOT THE ONLY THING THE MESH CAN GET WRONG. The
    # two assertions here were load-bearing for the orientation and nothing
    # else: mutating `_cell_uv`'s aspect correction made the drawn READ BOX
    # 14.2 % too wide and 47 tests, then 387, then the whole everyday tier
    # stayed green.
    #
    # The invariant is Knut's equal-margin rule (#119), which is what scanin
    # reads with: the box is the slot inset by the SAME DISTANCE on all four
    # sides, in real units. Dropping the aspect correction insets the two axes
    # by different amounts, so comparing the two insets catches it exactly,
    # where a ratio-of-the-cell bound is too loose to notice 14 %.
    _u, _v, _stride = dlg._marquee._cell_uv()
    _asp = dlg._marquee._grid.aspect or 1.0
    _su, _sv, _sw, _sh = dlg._marquee._grid.rects[0]
    _bx = [_u[_stride - 4 + k] * _asp for k in range(4)]
    _by = [_v[_stride - 4 + k] for k in range(4)]
    _inset_w = (_sw * _asp) - (max(_bx) - min(_bx))
    _inset_h = _sh - (max(_by) - min(_by))
    assert _inset_w == pytest.approx(_inset_h, rel=0.02), (
        f"the read box is inset {_inset_w:.6f} horizontally and {_inset_h:.6f} "
        "vertically; scanin insets equally on all four sides"
    )
    # ...AND EQUAL IS NOT ENOUGH. Dropping the aspect correction keeps the two
    # insets equal and simply makes them SMALLER, so the box grew 14.2 % while
    # staying square-shouldered. What pins it is the DEFINITION: the box covers
    # `sample_frac` of the slot's AREA, which is the number the user set.
    _area = ((max(_bx) - min(_bx)) * (max(_by) - min(_by))) / (_sw * _asp * _sh)
    assert _area == pytest.approx(dlg._sample_area.value() / 100.0, rel=0.03), (
        f"the drawn read box covers {_area:.4f} of the patch where the Sample "
        f"area setting says {dlg._sample_area.value() / 100.0:.4f}; the mesh is "
        "showing the user an area scanin will not read"
    )
    assert dlg._sample_area.maximum() == 64, (
        f"the sample cap is {dlg._sample_area.maximum()} %; 63 is the pointy "
        "formula on a transposed slot, so the orientation did not reach it"
    )
    # ...and the mesh really does change shape with it
    pats = [{"page": 0, "loc": f"A{i}", "x": 100 + (i % 5) * 120,
             "y": 100 + (i // 5) * 100, "w": 118, "h": 98} for i in range(15)]
    out = {}
    for flat in (False, True):
        g = GridSpec.from_patches(pats, hexagonal=True, flat_top=flat)
        m = ScanGridMarquee.__new__(ScanGridMarquee)
        m._grid, m._cell_uv_cache, m._sample_frac = g, None, 0.5
        u, v, _stride = m._cell_uv()
        asp = g.aspect or 1.0
        cell = list(zip(u[:6], v[:6]))
        xs = [c[0] * asp for c in cell]
        ys = [c[1] for c in cell]
        out[flat] = (max(xs) - min(xs), max(ys) - min(ys))
    assert out[False][0] < out[False][1], "the pointy cell is not taller than wide"
    assert out[True][0] > out[True][1], "the turned cell is not wider than tall"


def _scanner_dialog_over_a_turned_chart(monkeypatch):
    """A real ScannerProfileDialog over a real rotated honeycomb, or None.

    Built rather than faked: the point of the test above is that the value
    reaches the dialog through the app's own wiring, so anything short of the
    dialog would be testing the wiring's replacement.
    """
    import json
    import tempfile
    from pathlib import Path

    from PyQt6.QtWidgets import QDialog, QMessageBox

    from workflow.layout_engine import chart as le_chart

    d = Path(tempfile.mkdtemp())
    lines = ["CTI1", "", 'DESCRIPTOR "mesh"', 'ORIGINATOR "ChromIQ"',
             'KEYWORD "SAMPLE_LOC"', "NUMBER_OF_FIELDS 7", "BEGIN_DATA_FORMAT",
             "SAMPLE_ID RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z", "END_DATA_FORMAT",
             "NUMBER_OF_SETS 150", "BEGIN_DATA"]
    for i in range(150):
        lines.append(f"{i+1} {(i*7)%90+5}.0 {(i*13)%90+5}.0 {(i*29)%90+5}.0 40 45 50")
    lines += ["END_DATA", ""]
    ti1 = d / "p.ti1"
    ti1.write_text("\n".join(lines), encoding="utf-8")
    out = d / "o"
    out.mkdir()
    le_chart.build_chart(ti1, out / "c", instrument="CR30", paper="A4",
                         hflag=True, hex_flat_top=True, dpi=300,
                         randomize=False, spacer_mode="none")
    strips = json.loads((out / "c.strips.json").read_text(encoding="utf-8"))
    (out / "c.channels.json").write_text(json.dumps({
        "ink_channels": ["r", "g", "b"], "layout": {
            "engine": "chromiq", "engine_version": 1, "dpi": 300,
            "paper_mm": [210.0, 297.0], "patches": strips["patches"],
            # spacer_mode MUST match how the chart was built. Left out, the
            # recipe defaults to spacers ON, `ring_mm_of` returns 1.3 mm and
            # the cap correctly drops to 49 % for the ring -- which is the code
            # behaving, and a fixture saying something the sheet does not.
            "recipe": {"instrument": "CR30", "paper": "A4", "hflag": True,
                       "hex_flat_top": True, "spacer_mode": "none"}}}),
        encoding="utf-8")

    # MONKEYPATCH, NEVER A BARE setattr. These two are process-global, and a
    # test file that stubs them without undoing it hands every file scheduled
    # after it on the same xdist worker a UI with no modal dialogs. Measured:
    # `test_a_new_project_name_goes_through_one_door.py` is 40 passed on its
    # own and 25 FAILED when this file runs before it, and the release gate
    # flipped between 12620 passed and 25 failed on an unchanged tree
    # depending only on how xdist happened to schedule the files.
    #
    # `conftest.py::_repair_a_leaked_qmessagebox_exec` repairs only
    # `QMessageBox.exec`, which is why the leak survived it, and the project's
    # own note on this says saving and restoring these by hand does NOT restore
    # them. `monkeypatch` undoes it at teardown and is the only thing that does.
    monkeypatch.setattr(QDialog, "exec", lambda self: 1, raising=False)
    for m in ("warning", "critical", "information", "question"):
        monkeypatch.setattr(QMessageBox, m, staticmethod(lambda *a, **k: 0),
                            raising=False)
    try:
        from core.argyll_runner import ArgyllRunner
        from core.settings import AppSettings
        from PyQt6.QtCore import QSettings
        from ui.dialogs.scanin_dialog import ScannerProfileDialog
        s = AppSettings()
        s._qs = QSettings(str(d / "s.ini"), QSettings.Format.IniFormat)
        dlg = ScannerProfileDialog(ArgyllRunner(s), s, None)
        dlg._layout = json.loads((out / "c.channels.json").read_text(encoding="utf-8"))["layout"]
        dlg._load_page_grid()
        return dlg
    except Exception as exc:      # noqa: BLE001
        import os
        if os.environ.get("CHROMIQ_TEST_LOUD"):
            raise
        print(f"scanner dialog could not be opened: {type(exc).__name__}: {exc}")
        return None


def test_the_pitch_row_never_names_an_axis_the_two_columns_disagree_on(qapp):
    """J7, AND THE THIRD RECURRENCE OF THE SAME FAULT.

    The "Chart layout information" panel has two columns: the chart ON DISK on
    the left, and what the current settings would build on the right. One row
    NAME serves both. With "Auto-update preview" off -- the state the two-column
    panel exists for -- those columns routinely describe different charts, and
    whichever path ran last overwrote the other's label. The panel then printed
    "Patch size 13.89 x 12.02" above "Row pitch 10.41" for a sheet whose rows
    are 12.02 mm apart.

    Naming it from ONE column is wrong whichever column is picked. When they
    disagree there is no true answer to print, so it says neither.
    """
    from ui.chart_layout_info_panel import ChartLayoutInfoPanel
    p = ChartLayoutInfoPanel()
    name = p._row_names["pitch"]

    p.set_pitch_axis(False, column="actual")
    p.set_pitch_axis(False, column="estimate")
    assert "Row" in name.text(), name.text()

    p.set_pitch_axis(True, column="actual")
    p.set_pitch_axis(True, column="estimate")
    assert "Column" in name.text(), name.text()

    # ...and the case that made this a bug three times over
    p.set_pitch_axis(True, column="actual")
    p.set_pitch_axis(False, column="estimate")
    txt = name.text()
    assert "Row" not in txt and "Column" not in txt, (
        f"the row is called {txt!r} while the two columns describe charts of "
        "different orientations, so it is wrong for one of them"
    )

    # the estimate arriving last must not win either
    p.set_pitch_axis(False, column="actual")
    p.set_pitch_axis(True, column="estimate")
    txt = name.text()
    assert "Row" not in txt and "Column" not in txt, txt


def test_an_empty_panel_claims_no_orientation(qapp):
    """A column that has never been filled must not vote. Otherwise a fresh
    panel would read as a pointy chart before anything is loaded, and the first
    turned chart would look like a disagreement."""
    from ui.chart_layout_info_panel import ChartLayoutInfoPanel
    p = ChartLayoutInfoPanel()
    p.set_pitch_axis(True, column="actual")
    assert "Column" in p._row_names["pitch"].text(), (
        "the untouched estimate column voted, so one filled column cannot name "
        "the axis"
    )


def test_a_column_with_no_pitch_does_not_veto_the_row_name(qapp):
    """K1(b). The vote is the chart's ORIENTATION, but a rectangular chart has
    no interlocking pitch at all: the panel prints "--" in that column. Its
    `flat_top=False` was still counted, so a turned honeycomb beside a
    rectangular estimate read as a disagreement and the row fell back to the
    neutral "Patch pitch (mm)" -- refusing to name the axis of the only pitch
    on the panel. Photographed in Manual and in Guided, where the estimate is
    an i1-style rectangular layout with no pitch.

    Driven through the panel's own public API with the numbers the tab feeds
    it, and read off the visible label, so the test cannot pass by agreeing
    with the implementation.
    """
    from ui.chart_layout_info_panel import ChartLayoutInfoPanel
    p = ChartLayoutInfoPanel()
    name = p._row_names["pitch"]

    # A turned honeycomb on screen (a COLUMN pitch of 10.41 mm) and a
    # rectangular estimate, which carries no pitch.
    p.set_actual(total=690, rows=23, cols=30, pages=2,
                 patch_w=13.89, patch_h=12.02, row_pitch=10.41)
    p.set_pitch_axis(True, column="actual")
    p.set_estimate(total=525, rows=21, cols=25, pages=1,
                   patch_w=12.0, patch_h=12.0, row_pitch=0.0)
    p.set_pitch_axis(False, column="estimate")
    assert p._estimate_labels["pitch"].text() in ("—", "-", "--"), (
        "the estimate is showing a pitch, so this is not the state K1(b) is "
        f"about: {p._estimate_labels['pitch'].text()!r}"
    )
    assert "Column" in name.text(), (
        f"the row is called {name.text()!r} while the only pitch shown, "
        "10.41 mm, is unambiguously a column pitch across a turned sheet"
    )

    # ...and the mirror image: the pitchless column on the left.
    p2 = ChartLayoutInfoPanel()
    p2.set_actual(total=525, rows=21, cols=25, pages=1,
                  patch_w=12.0, patch_h=12.0, row_pitch=0.0)
    p2.set_pitch_axis(False, column="actual")
    p2.set_estimate(total=690, rows=23, cols=30, pages=2,
                    patch_w=13.89, patch_h=12.02, row_pitch=10.41)
    p2.set_pitch_axis(True, column="estimate")
    assert "Column" in p2._row_names["pitch"].text(), (
        f"the row is called {p2._row_names['pitch'].text()!r}; the chart on "
        "disk has no pitch to disagree with"
    )

    # The veto is still there when BOTH columns really do carry a pitch of
    # opposite axes -- that is J7, and this fix must not undo it.
    p3 = ChartLayoutInfoPanel()
    p3.set_actual(total=150, rows=10, cols=15, pages=1,
                  patch_w=12.0, patch_h=16.0, row_pitch=8.0)
    p3.set_pitch_axis(False, column="actual")
    p3.set_estimate(total=690, rows=23, cols=30, pages=2,
                    patch_w=13.89, patch_h=12.02, row_pitch=10.41)
    p3.set_pitch_axis(True, column="estimate")
    txt = p3._row_names["pitch"].text()
    assert "Row" not in txt and "Column" not in txt, (
        f"the row is called {txt!r} while two shown pitches run on different "
        "axes, so it is wrong for one of them"
    )


def test_clearing_a_column_withdraws_its_vote_on_the_row_name(qapp):
    """K1(a). `clear_actual` reset the vote; `clear_estimate` and
    `show_placeholder` did not. Both are reached constantly -- `clear_estimate`
    every time the user unticks "Use the ChromIQ layout engine", in Manual and
    in Guided -- so an emptied column went on voting, and the row kept saying
    the neutral "Patch pitch (mm)" because it still believed two columns
    disagreed when only one was left.
    """
    from ui.chart_layout_info_panel import ChartLayoutInfoPanel

    def _panel():
        p = ChartLayoutInfoPanel()
        p.set_actual(total=150, rows=10, cols=15, pages=1,
                     patch_w=12.0, patch_h=16.0, row_pitch=8.0)
        p.set_pitch_axis(False, column="actual")          # pointy: row pitch
        p.set_estimate(total=690, rows=23, cols=30, pages=2,
                       patch_w=13.89, patch_h=12.02, row_pitch=10.41)
        p.set_pitch_axis(True, column="estimate")         # turned: column pitch
        return p, p._row_names["pitch"]

    p, name = _panel()
    assert "Row" not in name.text() and "Column" not in name.text(), (
        f"two shown pitches on different axes should name neither: {name.text()!r}"
    )

    p.clear_estimate()
    assert "Row" in name.text(), (
        f"the row is called {name.text()!r} after the estimate was cleared; "
        "the only pitch left, 8 mm, is a row pitch down a strip"
    )

    p2, name2 = _panel()
    p2.show_placeholder()
    p2.set_actual(total=150, rows=10, cols=15, pages=1,
                  patch_w=12.0, patch_h=16.0, row_pitch=8.0)
    p2.set_pitch_axis(False, column="actual")
    assert "Row" in name2.text(), (
        f"the row is called {name2.text()!r}; the placeholder emptied both "
        "columns, so the estimate's old vote must not have survived it"
    )

    p3, name3 = _panel()
    p3.clear_actual()
    assert "Column" in name3.text(), (
        f"the row is called {name3.text()!r} after the chart was cleared; the "
        "only pitch left, 10.41 mm, is a column pitch across a turned sheet"
    )


def _turned_chart_sidecar(tmp_path, *, turned, n=345, paper="A4", scale=1.0,
                          align="top-left", spacer_mode="colored", **over):
    """Build one chart the way Create Chart does and return its geometry record.

    Through `default_recipe` -> `build_from_recipe`, NOT through
    `chart.build_chart`'s own defaults: those lay the same 345 patches out as 16
    strips of 22 where the app produces 15 of 23, and the fault this covers only
    appears on the tighter sheet. The numbers come back from the sidecar the
    renderer writes, so the test reads what was drawn rather than recomputing it.
    """
    import json
    from dataclasses import replace

    from workflow.layout_engine import chart as le_chart
    from workflow.layout_engine.presets import default_recipe

    src = tmp_path / f"c{n}.ti1"
    lines = ["CTI1", "", 'DESCRIPTOR "band"', 'ORIGINATOR "ChromIQ"',
             'KEYWORD "SAMPLE_LOC"', "NUMBER_OF_FIELDS 7",
             "BEGIN_DATA_FORMAT",
             "SAMPLE_ID RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z",
             "END_DATA_FORMAT", f"NUMBER_OF_SETS {n}", "BEGIN_DATA"]
    for i in range(n):
        lines.append(f"{i+1} {(i*37)%101}.0 {(i*71)%101}.0 {(i*13)%101}.0 "
                     "40.0 45.0 50.0")
    lines += ["END_DATA", ""]
    src.write_text("\n".join(lines), encoding="utf-8")

    r = replace(default_recipe("CR30", paper), hflag=True, hex_flat_top=turned,
                randomize=False, pscale=scale, patch_area_align=align,
                spacer_mode=spacer_mode, spacer_on=(spacer_mode != "none"),
                **over)
    out = tmp_path / ("out_%s_%s_%s_%s_%s_%s" % (
        turned, n, paper, scale, align,
        "_".join(f"{k}{v}" for k, v in sorted(over.items())) or "plain"))
    out.mkdir()
    le_chart.build_from_recipe(src, out / "c", r)
    return json.loads((out / "c.strips.json").read_text(encoding="utf-8"))


def _pale_ti1(path, n):
    """A patch set light enough that black label ink is unambiguous.

    A random-coloured chart puts dark patches under the letters, and four probes
    in this series read one as text. Pale patches remove the question.
    """
    lines = ["CTI1", "", 'DESCRIPTOR "pale"', 'ORIGINATOR "ChromIQ"',
             'KEYWORD "SAMPLE_LOC"', "NUMBER_OF_FIELDS 7",
             "BEGIN_DATA_FORMAT",
             "SAMPLE_ID RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z",
             "END_DATA_FORMAT", f"NUMBER_OF_SETS {n}", "BEGIN_DATA"]
    for i in range(n):
        lines.append(f"{i+1} {88+(i%5)}.0 {90+(i%4)}.0 {92+(i%3)}.0 "
                     "80.0 85.0 90.0")
    lines += ["END_DATA", ""]
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def _letter_heights(tmp_path, *, turned, n=345, paper="A4", **over):
    """The drawn height of every strip letter, measured from the PAGE.

    THE SIDECAR CANNOT ANSWER THIS AND A REVIEWER PROVED IT. Comparing the
    recorded patch box against `label_band_bottom_px` is circular: the reserve
    that moves the box IS that number plus half a millimetre, and both come from
    `ind_px`. Drawing the labels 20 px lower -- letters visibly beheaded, "A"
    into a lambda, "C" into a gamma -- left all six of those assertions green.

    So this reads ink. A patch is painted after its label, so a letter it covers
    comes out SHORTER, and the height of the topmost dark run above each strip
    is what a reader would call "is the letter whole".
    """
    import json
    from dataclasses import replace

    import numpy as np
    import tifffile

    from workflow.layout_engine import chart as le_chart
    from workflow.layout_engine.presets import default_recipe

    src = _pale_ti1(tmp_path / f"pale{n}.ti1", n)
    r = replace(default_recipe("CR30", paper), hflag=True, hex_flat_top=turned,
                randomize=False, spacer_mode="none", spacer_on=False, **over)
    out = tmp_path / ("h_%s_%s_%s_%s" % (
        turned, n, paper,
        "_".join(f"{k}{v}" for k, v in sorted(over.items())) or "plain"))
    out.mkdir()
    le_chart.build_from_recipe(src, out / "c", r)
    side = json.loads((out / "c.strips.json").read_text(encoding="utf-8"))
    page = np.asarray(tifffile.imread(str(sorted(out.glob("*.tif"))[0])))
    g = page[..., :3].max(axis=2) if page.ndim == 3 else page
    dark = g < 120

    # The first patch of EVERY strip, raised and lowered alike: taking only the
    # boxes at the very top selects the raised half of a turned sheet, and the
    # alternation is the whole symptom.
    first: dict = {}
    for p in sorted((q for q in side["patches"] if q["page"] == 0),
                    key=lambda q: (q["x"], q["y"])):
        first.setdefault(p["x"], p)

    heights = []
    for p in first.values():
        col = dark[:p["y"] + p["h"], p["x"]:p["x"] + p["w"]]
        rows = np.flatnonzero(col.any(axis=1))
        if not len(rows):
            heights.append(0)
            continue
        top = int(rows[0])
        r_ = top
        while r_ < col.shape[0] and col[r_].any():
            r_ += 1
        heights.append(r_ - top)
    return heights


def _letters_are_whole(tmp_path, *, turned, label, **over):
    """Assert no strip letter is shorter than on a sheet with room to spare.

    The control is the same chart with a 30 mm top margin, where nothing can
    reach the letters. It is a second render, not a recomputation, so the two
    sides of the comparison share no arithmetic.
    """
    real = _letter_heights(tmp_path, turned=turned, **over)
    roomy = _letter_heights(tmp_path, turned=turned, margin_top=30.0, **over)
    assert real and roomy, "no strip letters were drawn at all"
    assert min(real) >= min(roomy) - 2, (
        f"{label}: the shortest strip letter is {min(real)} px where the same "
        f"chart with room to spare draws {min(roomy)} px, so a patch is "
        f"printed over it. Heights: {sorted(real)}"
    )


def test_a_turned_honeycomb_never_prints_a_strip_letter_on_a_patch(tmp_path):
    """The raised strips of a turned honeycomb climbed into the label band.

    The block is shifted down by `hxeh` so a hexagon's apex clears the top
    reserve. On a pointy sheet `hxeh` is the apex overshoot (plen/6) and the
    slot's own top is that far below the patch-area top -- the slack the strip
    letters have always sat in. On a TURNED sheet `hxeh` is the STAGGER reserve
    (plen/4), and every even strip comes straight back up through it, so the
    topmost ink landed exactly ON the patch-area top. Reported by the owner from
    a real sheet and reproduced from the app's own record: label band bottom 74
    px, topmost patch box 71 px, at 150, 345 and 690 patches alike.

    Read off the sidecar the renderer writes, with the pointy sheet as the
    control, because an absolute clearance says nothing on its own.
    """
    for n in (150, 345, 690):
        for name, turned in (("turned", True), ("pointy", False)):
            # The measurement that matters: the letters themselves.
            _letters_are_whole(tmp_path, turned=turned,
                               label=f"{name} chart of {n} patches", n=n)
            # ...and the recorded geometry, as a second leg. On its own this is
            # circular -- see `_letter_heights` -- but it names the millimetre.
            side = _turned_chart_sidecar(tmp_path, turned=turned, n=n)
            band = side["label_band_bottom_px"]
            top = min(p["y"] for p in side["patches"] if p["page"] == 0)
            mm = 25.4 / side["dpi"]
            assert top >= band, (
                f"{name} chart of {n} patches: the strip letters end at "
                f"{band} px and the first patch box starts at {top} px, so "
                f"{(band - top) * mm:.2f} mm of letter is printed on the ink"
            )


def test_the_turn_does_not_move_a_pointy_honeycomb(tmp_path):
    """The reserve above is for the turn ALONE.

    A pointy honeycomb is shipped behaviour and its sheets must come out where
    they always did, so the guard is keyed on the orientation and this pins that
    the control sheet's own numbers are untouched: patch-area top 91 px and band
    bottom 83 px at 300 dpi on A4, which is what the tree produced before the
    reserve existed.
    """
    side = _turned_chart_sidecar(tmp_path, turned=False, n=345)
    assert side["dpi"] == 300
    assert side["label_band_bottom_px"] == 83, side["label_band_bottom_px"]
    top = min(p["y"] for p in side["patches"] if p["page"] == 0)
    assert top == 91, (
        f"the pointy patch area starts at {top} px where it has always started "
        "at 91; the turn's reserve reached a chart that is not turned"
    )
    assert side["steps_in_pass"] == 27, (
        f"a pointy strip now holds {side['steps_in_pass']} patches, not 27; "
        "the reserve cost capacity on a chart it must not touch"
    )


def test_the_reserve_reaches_capacity_as_well_as_placement(tmp_path):
    """The same reserve lives in TWO functions and both are load-bearing.

    `placement` puts the ink on the page and `compute` decides how many patches
    fit. Giving the label band its room in `placement` alone moves the block
    down without shortening it, and the last row walks off the bottom: measured
    across paper sizes, scales, spacer modes and alignments, the worst case is
    A4 Rotated at scale 1.0, where the lowered strips end 0.978 mm OUTSIDE the
    bottom margin. Margins are law, so this pins the bottom, which the label
    test above cannot see.
    """
    from dataclasses import replace

    from workflow.layout_engine import instruments
    from workflow.layout_engine.presets import default_recipe

    for paper, align in (("A4R", "top-left"), ("A4", "top-left"),
                         ("A3", "bottom-left")):
        side = _turned_chart_sidecar(tmp_path, turned=True, n=150, paper=paper,
                                     align=align, spacer_mode="none")
        g = instruments.geom_from_build_kwargs(
            replace(default_recipe("CR30", paper), hflag=True,
                    hex_flat_top=True, patch_area_align=align,
                    spacer_mode="none", spacer_on=False).build_kwargs())
        mm = 25.4 / side["dpi"]
        page_h = side["paper_mm"][1]
        bottom = page_h - max(p["y"] + p["h"] for p in side["patches"]
                              if p["page"] == 0) * mm
        assert bottom >= g.margin_b - 0.1, (
            f"{paper} {align}: the lowest ink sits {bottom:.3f} mm from the "
            f"page edge where the margin asked for is {g.margin_b:.3f} mm, so "
            f"the sheet prints {g.margin_b - bottom:.3f} mm outside it"
        )


@pytest.mark.parametrize("label,over", [
    ("an explicit 6 mm label", {"indicator_size_mm": 6.0}),
    ("a label pushed down 3 mm", {"strip_label_offset_mm": 3.0}),
    ("an underlined label", {"underline_mode": "segments"}),
    ("patch scale 1.5", {"pscale": 1.5}),
    ("patch scale 2.0", {"pscale": 2.0}),
])
def test_the_letters_clear_the_ink_however_they_are_styled(tmp_path, label, over):
    """Reserving the label BAND is not enough; the band is not what is drawn.

    A first fix reserved `label_band_mm`, and a reviewer measured four ordinary
    Expert-Options settings that still printed letters on patches:

    | setting | letter cut into the ink |
    |---|---|
    | an explicit 6 mm label | 1.44 mm -- the reserve measures the ink bbox of "W8", the renderer draws the font's full pixel size |
    | a strip-label offset of +3 mm | 2.46 mm -- the reserve never knew the offset existed |
    | an underline | 0.25 mm |
    | patch scale 1.5 or 2.0 | 0.00 mm, the two exactly level |

    So the reserve now uses where the labels' ink actually ENDS, which only the
    renderer can say. Each row here is one of those settings, and each is read
    off the sidecar rather than recomputed.
    """
    _letters_are_whole(tmp_path, turned=True, label=f"with {label}", **over)
    scale = over.pop("pscale", 1.0)
    side = _turned_chart_sidecar(tmp_path, turned=True, n=345, scale=scale,
                                 **over)
    band = side["label_band_bottom_px"]
    top = min(p["y"] for p in side["patches"] if p["page"] == 0)
    mm = 25.4 / side["dpi"]
    assert top > band, (
        f"with {label} the strip letters end at {band} px and the first patch "
        f"box starts at {top} px, so {(band - top) * mm:.2f} mm of letter is "
        "printed on the ink"
    )


# ---------------------------------------------------------------------------
# GUIDED TURNS THE HONEYCOMB TOO, so every user gets the straight strips
# without having to know the option exists (Basti, 2026-09-10: "i want this
# layout for guided module as well so every user automatically benefits").
# ---------------------------------------------------------------------------

def _guided_kw(instrument, *, hexes, manual=False):
    """The build kwargs Guided hands the engine, from the real builder."""
    from dataclasses import fields, is_dataclass

    from workflow.chart_creator import ChartCreator, ChartParams

    # BUILT FROM THE REAL DATACLASS, not from a hand-made stand-in. A namespace
    # with the handful of fields this test happens to know about goes stale the
    # moment `ChartParams` gains one, and it did within minutes of being
    # written (`bw_spacers`).
    assert is_dataclass(ChartParams) and fields(ChartParams)
    params = ChartParams()
    params.instrument = instrument
    params.double_density = hexes
    params.is_manual = manual
    params.paper = "A4"
    params.layout_recipe = None
    return ChartCreator._engine_build_kwargs(
        types.SimpleNamespace(_settings=None), params)


@pytest.mark.parametrize("instrument,hexes,turned", [
    ("CR30", True, True),      # the case the owner asked for
    ("CR30", False, False),    # a square CR30 chart is never turned
    ("SS", True, False),       # the SpectroScan is excluded by his own ruling
])
def test_guided_turns_only_a_cr30_honeycomb(instrument, hexes, turned):
    kw = _guided_kw(instrument, hexes=hexes)
    assert bool(kw.get("hex_flat_top")) is turned, (
        f"Guided {instrument} with hexagons={hexes} came out "
        f"{'turned' if kw.get('hex_flat_top') else 'not turned'}"
    )


def test_a_manual_chart_is_left_alone_by_the_guided_writer():
    """Manual keeps its own tick in Expert Options. A Manual chart WITHOUT a
    layout recipe reaches the same branch, and it must not be turned behind the
    user's back: that would be a second writer for the flag, which is the
    mistake `d1adbe31` made once already."""
    kw = _guided_kw("CR30", hexes=True, manual=True)
    assert not kw.get("hex_flat_top"), (
        "the Guided writer reached a Manual chart and turned it"
    )


def test_the_guided_estimate_and_the_guided_build_agree():
    """The Calculated Patches figure is worked out by a different function from
    the one that builds the sheet, and the file says in capitals that the two
    must mirror each other. A turn in one and not the other makes the figure a
    lie, which is a bug that file records being fixed once before."""
    from workflow.layout_engine import instruments
    from ui.tabs.tab_chart import TabChart

    build = _guided_kw("CR30", hexes=True)
    geom = TabChart._engine_geom(
        None, "CR30", "A4", dd=True, td=False, eff_lb=False, nsl=False,
        pscale=1.0, margin=6.0, guided=True)
    built = instruments.geom_from_build_kwargs(build)
    assert bool(geom.hex_flat_top) is bool(built.hex_flat_top) is True, (
        f"estimate turned={geom.hex_flat_top}, build turned={built.hex_flat_top}"
    )


def test_an_old_recipe_without_the_key_rebuilds_untouched():
    """THE REPRINT HAZARD, and the most important test here. Somebody rebuilding
    a chart to replace a lost sheet must get the sheet they printed. A recipe
    saved before the turn existed has no key for it, and an absent key must
    read False, not "whatever Guided would choose today"."""
    from workflow.layout_engine.presets import LayoutRecipe
    old = {"instrument": "CR30", "paper": "A4", "hflag": True}
    r = LayoutRecipe.from_build_kwargs(old)
    assert r.hex_flat_top is False, (
        "an old recipe came back turned, so a reprint would not match the sheet"
    )
