"""#164 (Knut, 2026-08-23): which edges carry the dashes, and the overlay that
counted two combs as one.

Two separate things he reported in the same message.

**"Show markers for"** — *"for some layouts, it might be an idea to have
checkbox choice: 'Show markers for:' 'Top/bottom (horizontal):' and 'Sides
(vertical):'. Then a user can choose to turn off the ones not needed, especially
as the strip markers are the most useful for measuring."*

**The count that could not happen** — *"When 4, then there are actually 5, and
the three within the patch area are not distributed evenly … When 6, then there
are 7."* The geometry cannot draw those numbers, and does not: it draws exactly
the count asked for, every gap identical, which is the design he confirmed on
2026-08-23 (*"I designed the vertical patch edge markers to always be centred in
the spacer … It is only the markers between the spacers that are added for
increased number of markers"*). What produced his counts was the PREVIEW: the
sheet on screen carries the dashes it was generated with, and the live overlay
drew the current spin-box value on top, so the screen showed the union of two
combs. 3 printed + 4 on the spin box = 5 dashes per patch, unevenly spaced;
3 + 6 = 7. Every number he reported falls out of that.
"""
from __future__ import annotations

import pytest

from workflow.layout_engine import geometry, instruments, papers
from workflow.layout_engine.presets import LayoutRecipe


def _setup(instrument: str = "CM", paper: str = "A4", patches: int = 480):
    geom = instruments.geom_from_build_kwargs(
        {"instrument": instrument, "paper": paper})
    w_mm, h_mm = papers.dimensions_mm(paper)
    lay = geometry.compute(geom, w_mm, h_mm, patches)
    return geom, w_mm, h_mm, lay


def _lines(**kw):
    geom, w, h, lay = _setup()
    opts = {"edge_mm": 2.0, "length_mm": 4.0, "per_patch": 4}
    opts.update(kw)
    return geometry.helper_marker_lines_mm(geom, w, h, lay, **opts)


def _top_bottom(lines):
    """Dashes on the top and bottom edges — drawn as VERTICAL strokes."""
    return [ln for ln in lines if abs(ln[0] - ln[2]) < 1e-9]


def _sides(lines):
    """Dashes on the left and right edges — drawn as HORIZONTAL strokes."""
    return [ln for ln in lines if abs(ln[1] - ln[3]) < 1e-9]


# --- which edges carry dashes ---------------------------------------------

def test_both_edges_by_default():
    lines = _lines()
    assert _top_bottom(lines) and _sides(lines)


def test_turning_the_sides_off_leaves_only_the_top_and_bottom():
    lines = _lines(sides=False)
    assert not _sides(lines)
    assert _top_bottom(lines), "the set he kept was thrown away too"


def test_turning_the_top_and_bottom_off_leaves_only_the_sides():
    lines = _lines(top_bottom=False)
    assert not _top_bottom(lines)
    assert _sides(lines)


def test_both_off_prints_nothing():
    assert _lines(top_bottom=False, sides=False) == []


def test_the_survivor_keeps_its_corners():
    """The corner trim exists only because the two sets would collide. With one
    of them off there is nothing to collide with, so the other runs the full
    length of its edge — trimming it then would open a gap in the very rhythm
    the ruler is laid against."""
    both = len(_top_bottom(_lines()))
    alone = len(_top_bottom(_lines(sides=False)))
    assert alone > both, (
        f"the lone set was still trimmed for a set that is not there "
        f"({alone} dashes vs {both} with both on)")

    both_s = len(_sides(_lines()))
    alone_s = len(_sides(_lines(top_bottom=False)))
    assert alone_s > both_s


def test_the_names_are_the_edge_not_the_axis():
    """Knut named the EDGES; the code draws top/bottom dashes as vertical
    strokes and side dashes as horizontal ones. Anyone matching his word
    "horizontal" to a horizontal segment gets the two sets backwards, and both
    the tests and the UI then look self-consistent while doing the opposite of
    what he asked for."""
    only_tb = _lines(sides=False)
    assert all(abs(ln[0] - ln[2]) < 1e-9 for ln in only_tb), (
        "top/bottom dashes must be vertical strokes")
    only_sides = _lines(top_bottom=False)
    assert all(abs(ln[1] - ln[3]) < 1e-9 for ln in only_sides), (
        "side dashes must be horizontal strokes")


def test_the_spacing_is_untouched_by_switching_an_edge_off():
    """Turning one set off must not disturb the other's comb — his #152 pass
    criterion still applies to whatever is printed."""
    ys = sorted({ln[1] for ln in _sides(_lines(top_bottom=False))})
    gaps = [round(b - a, 6) for a, b in zip(ys, ys[1:])]
    assert len(set(gaps)) == 1, f"gaps stopped being identical: {sorted(set(gaps))}"


@pytest.mark.parametrize("field,value", [
    ("helper_markers_top_bottom", False),
    ("helper_markers_sides", False),
])
def test_the_choice_survives_a_preset(field, value):
    """A new option is worth nothing if a preset forgets it — and the recipe has
    two different serialisations, so both have to carry it."""
    r = LayoutRecipe()
    setattr(r, field, value)
    assert getattr(LayoutRecipe.from_dict(r.to_dict()), field) is value
    assert getattr(LayoutRecipe.from_build_kwargs(r.build_kwargs()), field) is value


def test_the_engine_is_asked_for_them_by_name():
    """`build_kwargs` feeds `chart.build_chart` by keyword, so a key that does
    not match a parameter name is silently dropped rather than raising."""
    import inspect

    from workflow.layout_engine import chart as le_chart
    params = inspect.signature(le_chart.build_chart).parameters
    for key in LayoutRecipe().build_kwargs():
        assert key in params, f"build_kwargs sends {key!r}, which build_chart drops"


# --- the two combs the preview added up ------------------------------------

def test_the_geometry_draws_the_count_it_is_asked_for():
    """No configuration produces n+1. This is the claim behind "when 4, then
    there are actually 5" and it is not true of the printed sheet."""
    geom, w, h, lay = _setup()
    place = geometry.placement(geom, w, h, lay)
    top = place.y_of(1)
    pitch = place.y_of(1) - place.y_of(0)
    for n in (2, 3, 4, 5, 6, 7, 8):
        ys = sorted({ln[1] for ln in _sides(_lines(per_patch=n))})
        # one patch's worth: from the spacer centre above it to the one below
        lo = top - (pitch - place.plen) / 2 - 1e-6
        hi = lo + pitch + 2e-6
        here = [y for y in ys if lo <= y <= hi]
        assert len(here) == n, f"asked for {n} dashes per patch, drew {len(here)}"


def test_a_sheet_printed_at_three_plus_an_overlay_at_four_shows_five():
    """The bug, stated as arithmetic: this is what his eyes were counting.

    Kept as a test because the fix is a PRESENTATION fix — the overlay says when
    it is showing something the sheet does not have — and nothing stops a future
    change from quietly drawing both combs in the same black again.
    """
    geom, w, h, lay = _setup()
    place = geometry.placement(geom, w, h, lay)
    pitch = place.y_of(1) - place.y_of(0)
    lo = place.y_of(1) - (pitch - place.plen) / 2 - 1e-6
    hi = lo + pitch + 2e-6

    def per_patch(n):
        return {round(ln[1], 6) for ln in _sides(_lines(per_patch=n))
                if lo <= ln[1] <= hi}

    printed = per_patch(3)
    assert len(printed | per_patch(4)) == 5, "the 4 case did not come to 5"
    assert len(printed | per_patch(5)) == 5, "the 5 case must stay at 5"
    assert len(printed | per_patch(6)) == 7, "the 6 case did not come to 7"

    # …and the 4 case is the uneven one, the 5 case is not — which is exactly
    # the distinction he drew.
    def gaps(n):
        seq = sorted(printed | per_patch(n))
        return {round(b - a, 3) for a, b in zip(seq, seq[1:])}

    assert len(gaps(4)) > 1, "the union at 4 should NOT be evenly spaced"
    assert len(gaps(5)) == 1, "the union at 5 should be evenly spaced"


# --- every output path, not just the TIFF -----------------------------------

def test_the_vector_pdf_carries_the_markers_too(tmp_path):
    """"Also export a PDF" produced a chart with no dashes on it.

    Every other element on the sheet appends to the render's display list, which
    is the only thing `vector_pdf` can see; the markers were drawn straight onto
    the raster and nowhere else. The TIFF had them, the PDF silently did not —
    and both come out of the same tick of Generate Chart.
    """
    import re
    import zlib

    from workflow.layout_engine import chart as le_chart
    from workflow.layout_engine.presets import default_recipe

    def black_rules(markers: bool) -> int:
        rec = default_recipe("CM", "A4", mode="freehand")
        rec.helper_markers = markers
        rec.helper_marker_len_mm = 4.0
        kw = rec.build_kwargs()
        kw["export_pdf"] = True
        out = tmp_path / ("on" if markers else "off")
        res = le_chart.build_chart(
            "tests/fixtures/charts/cm_a4_480p_2pages.ti1", out, **kw)
        assert res.pdf_path is not None
        data = res.pdf_path.read_bytes()
        total = 0
        for stream in re.findall(rb"stream\n(.*?)\nendstream", data, re.S):
            try:
                total += zlib.decompress(stream).count(b"0.0000 0.0000 0.0000 rg")
            except zlib.error:
                continue
        return total

    off, on = black_rules(False), black_rules(True)
    assert on > off + 100, (
        f"the PDF gained {on - off} black rules when the markers were switched "
        f"on — it is still exporting a chart without them")


def test_the_pdf_rules_land_exactly_on_the_tiff_dashes(tmp_path):
    """Counting rules is not enough — they have to be in the right PLACE.

    The first version of the PDF fix assumed PIL centres a line on its
    coordinates. It does not: a width-w line inks rows ``y-(w-1)//2`` through
    ``y+w//2`` inclusive, and runs from x0 to x1 inclusive. Taking it as centred
    put every PDF rule half a pixel above its TIFF dash and made it a pixel
    short — invisible on paper, but the kind of "close enough" that stops being
    close enough the next time somebody builds on it.
    """
    import re
    import zlib

    import numpy as np
    from PIL import Image

    from workflow.layout_engine import chart as le_chart
    from workflow.layout_engine.presets import default_recipe

    rec = default_recipe("CM", "A4", mode="freehand")
    rec.helper_markers = True
    rec.helper_marker_len_mm = 4.0
    kw = rec.build_kwargs()
    kw["export_pdf"] = True
    res = le_chart.build_chart(
        "tests/fixtures/charts/cm_a4_480p_2pages.ti1", tmp_path / "s", **kw)

    arr = np.asarray(Image.open(res.tiff_paths[0]).convert("L"))
    rows = np.where(arr[:, 20:60].min(axis=1) < 128)[0]
    runs: list[list[int]] = []
    for y in rows:
        if runs and y - runs[-1][-1] <= 1:
            runs[-1].append(int(y))
        else:
            runs.append([int(y)])
    tiff = [(r[0], r[-1] + 1) for r in runs][:5]
    assert tiff, "the TIFF has no left-edge dashes to compare against"

    pt_per_px = 72.0 / rec.dpi
    page_h_pt = 297.0 * 72 / 25.4
    rects = []
    for stream in re.findall(rb"stream\n(.*?)\nendstream",
                             res.pdf_path.read_bytes(), re.S):
        try:
            content = zlib.decompress(stream)
        except zlib.error:
            continue
        for m in re.finditer(
                rb"0\.0000 0\.0000 0\.0000 rg\n([\d.]+) ([\d.]+) ([\d.]+) ([\d.]+) re f",
                content):
            x, y, w, h = (float(v) for v in m.groups())
            if w > h and x < 60 * pt_per_px:
                rects.append((y, h))
        break                                   # first page only
    rects.sort(key=lambda r: -r[0])
    assert len(rects) >= len(tiff), "the PDF is missing left-edge rules"

    for (y, h), (top, bottom) in zip(rects, tiff):
        pdf_top = (page_h_pt - (y + h)) / pt_per_px
        pdf_bottom = (page_h_pt - y) / pt_per_px
        assert abs(pdf_top - top) < 0.05, (
            f"PDF rule starts at {pdf_top:.3f}, the TIFF dash at {top}")
        assert abs(pdf_bottom - bottom) < 0.05, (
            f"PDF rule ends at {pdf_bottom:.3f}, the TIFF dash at {bottom}")
