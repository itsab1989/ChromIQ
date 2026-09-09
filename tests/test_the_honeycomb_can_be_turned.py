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
import math
import os

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
