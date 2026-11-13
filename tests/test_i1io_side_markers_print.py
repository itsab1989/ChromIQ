"""RULER HELPER MARKERS ON THE SIDES PRINT ON AN i1iO CHART (review 5, item 1).

"Sides (vertical)" printed nothing on an i1iO chart: its strips step UP the
page (patch 1 at the bottom, `Geom.reverse_steps`), the comb's pitch came out
negative and gave no dash. The i1Pro printed them, and the top/bottom
warning tells people to switch the top/bottom ones off, which then left none.
Now they print, at the same pitch, and keep 1 mm from every patch, cross,
the name line, the letters and the numbers.
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(autouse=True)
def i1io_on():
    from workflow.i1io import support
    before = support._latched
    support.set_enabled_for_this_process(True)
    try:
        yield
    finally:
        support._latched = before


def _apart(a, b, gap):
    return (a[2] + gap <= b[0] or b[2] + gap <= a[0]
            or a[3] + gap <= b[1] or b[3] + gap <= a[1])


@pytest.mark.parametrize("paper,crosses", [("A4", True), ("A4", False),
                                           ("Letter", True)])
def test_side_markers_print_and_keep_clear(paper, crosses):
    from workflow.i1io import chart as C
    from workflow.layout_engine import geometry, instruments, papers
    kw = {"instrument": "IO2", "paper": paper, "dpi": 100,
          "helper_markers": True, "helper_markers_top_bottom": False,
          "helper_markers_sides": True, C.CROSSES_KEY: crosses}
    geom = instruments.geom_from_build_kwargs(kw)
    w, h = (float(v) for v in papers.dimensions_mm(paper))
    layout = geometry.compute(geom, w, h, 528)
    lines = geometry.helper_marker_lines_mm(geom, w, h, layout,
                                            top_bottom=False, sides=True)
    assert lines, "no side markers"
    # same pitch as on any chart: every gap identical
    ys = sorted({round(l[1], 3) for l in lines})
    gaps = {round(b - a, 3) for a, b in zip(ys, ys[1:])}
    assert len(gaps) == 1
    fixed = C.fixed_build_kwargs(kw)
    labels = fixed[C.LABELS_KEY]
    boxes = [c[3:] for c in C.page_patches(geom, layout, w, h, 0)]
    boxes += C.letter_boxes(geom, layout, w, h, 0, 100, labels)
    boxes += C._number_boxes(geom, layout, w, h, 0, 100, labels)
    if crosses:
        boxes.append(C.text_column(w, h))
    zones = [C.mark_zone(m) for m in C.marks(w, h)] if crosses else []
    for (x0, y0, x1, y1) in lines:
        dash = (min(x0, x1), y0 - 0.15, max(x0, x1), y1 + 0.15)
        for b in boxes:
            assert _apart(dash, b, 1.0 - 0.05), (dash, b)
        for z in zones:                 # the zone holds its own clearance
            assert _apart(dash, z, 0.0), (dash, z)
    # and nothing says the side markers are risky
    assert C.option_warnings(fixed) == []


def test_the_build_draws_them(tmp_path):
    import numpy as np
    from PIL import Image
    from tests.test_i1io_chart import _ti1
    from workflow.layout_engine import chart
    r = chart.build_chart(_ti1(tmp_path / "c.ti1", 300), tmp_path / "c",
                          instrument="IO2", paper="A4", dpi=100, seed=1,
                          project="P", chart_date="x", helper_markers=True,
                          helper_markers_top_bottom=False,
                          helper_markers_sides=True)
    im = np.asarray(Image.open(r.tiff_paths[0]).convert("L"))
    s = 100 / 25.4
    left = im[int(0.4 * im.shape[0]):int(0.6 * im.shape[0]),
              int(1.5 * s):int(4.5 * s)]
    assert (left < 128).any()
