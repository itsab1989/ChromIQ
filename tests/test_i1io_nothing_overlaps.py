"""NOTHING ON AN i1iO SHEET OVERLAPS UNLESS A PERSON ASKED FOR IT, AND THEN
IT IS SAID (the owner, watching the whole-workflow drive, 2026-11-13).

For a matrix of charts at values the panel offers without a warning (A4 and
Letter, crosses on and off, clip border on and off, underline on and off,
one and several pages), every printed element keeps at least 1 mm from every
other: the patches, the strip letters and their underline, the patch numbers,
the aiming crosses with their digits, the clip border's content and the line
with the chart's name. And a chart offset that pushes the last strip, its
letter and the underline onto the name line is said, in the build's log and
under "Measured from Preview" alike.
"""
from __future__ import annotations

import itertools
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from tests.test_i1io_letters_and_numbers_are_held_or_said import (  # noqa
    _build, i1io_on)

DPI = 100
CLEAR = 1.0 - 0.05          # 1 mm, less a twentieth for pixel rounding


def _apart(a, b, gap=CLEAR) -> bool:
    return (a[2] + gap <= b[0] or b[2] + gap <= a[0]
            or a[3] + gap <= b[1] or b[3] + gap <= a[1])


def _sheet(paper, crosses, clip, underline, n):
    from workflow.i1io import chart as C
    from workflow.layout_engine import geometry, instruments, papers
    kw = {"instrument": "IO2", "paper": paper, "dpi": DPI,
          C.CROSSES_KEY: crosses, C.CLIP_KEY: clip,
          "underline_mode": "black" if underline else "off"}
    if clip:
        kw["clip_content_mode"] = "notes"
    fixed = C.fixed_build_kwargs(kw)
    geom = instruments.geom_from_build_kwargs(kw)
    w, h = (float(v) for v in papers.dimensions_mm(paper))
    layout = geometry.compute(geom, w, h, n)
    return C, kw, fixed, geom, layout, w, h


MATRIX = list(itertools.product(("A4", "Letter"), (True, False),
                                (True, False), (True, False), (528, 1200)))


@pytest.mark.parametrize("paper,crosses,clip,underline,n", MATRIX)
def test_every_element_keeps_1_mm_from_every_other(paper, crosses, clip,
                                                   underline, n):
    C, kw, fixed, geom, layout, w, h = _sheet(paper, crosses, clip,
                                              underline, n)
    labels = fixed[C.LABELS_KEY]
    # warning-free values: the checks say nothing
    assert C.furniture_warnings(geom, layout, w, h, DPI, labels,
                                crosses) == []
    band = C.clip_area(geom, w, h)
    content = None
    if band is not None:
        reach = float(getattr(geom, "clip_content_reach_mm", -1.0))
        content = (band[0], band[1], reach if reach >= 0 else band[2],
                   band[3])
    for page in range(layout.pages):
        cells = [c[3:] for c in C.page_patches(geom, layout, w, h, page)]
        letters = C.letter_boxes(geom, layout, w, h, page, DPI, labels)
        unders = [r for r, _rgb in C.underline_rects(geom, layout, w, h,
                                                     page, labels)]
        numbers = C._number_boxes(geom, layout, w, h, page, DPI, labels)
        zones = ([C.mark_zone(m) for m in C.marks(w, h)]
                 if C.on_page(crosses, page) else [])
        line = [C.text_column(w, h)] if zones else []
        groups = {"patches": cells, "letters": letters + unders,
                  "numbers": numbers, "crosses": zones, "name line": line,
                  "clip content": [content] if content else []}
        names = list(groups)
        for i, a in enumerate(names):
            for b in names[i + 1:]:
                # a cross's zone already holds its own clearance; the clip
                # border's content and the numbers, and the name line and the
                # strips with their letters, keep 2 mm (the owner read 1 mm
                # as touching on the preview)
                pair = {a, b}
                gap = (0.0 if "crosses" in pair
                       else 2.0 - 0.05 if pair in (
                           {"clip content", "numbers"},
                           {"name line", "letters"},
                           {"name line", "patches"})
                       else CLEAR)
                for x in groups[a]:
                    for y in groups[b]:
                        assert _apart(x, y, gap), (page, a, x, b, y)


def test_a_chart_offset_onto_the_name_line_is_said():
    """The drive's chart 3: chart offset X 2 and "Label offset" X 1 put the
    last strip, its letter and the underline on the logo, silently. Said by
    `furniture_warnings`, which the build's log and "Measured from Preview"
    both use (`preview_checks`)."""
    from workflow.i1io import chart as C
    base = {"instrument": "IO2", "paper": "Letter", "dpi": DPI,
            "area_target_count": 900}
    _s, notes = C.preview_checks(dict(base, offset_x=2.0, max_strip=200.0,
                                      nolimit=False,
                                      strip_label_offset_x_mm=1.0,
                                      underline_mode="black"))
    assert any("would touch the line with the chart's name" in w
               for w in notes), notes
    _s, quiet = C.preview_checks(base)
    assert quiet == []


def test_a_name_line_with_no_paper_is_said(tmp_path):
    """Crosses off, a 5 mm right margin and a strip cap leave no paper beside
    the last strip: the line is left off, and that is said."""
    from workflow.i1io import chart as C
    result = _build(tmp_path, n=420, **{C.CROSSES_KEY: False,
                                        C.CLIP_KEY: True,
                                        "clip_content_mode": "notes",
                                        "margins": (12.0, 5.0, 27.8, 32.0),
                                        "max_strip": 230.0, "nolimit": False,
                                        "edge_spacers": True,
                                        "spacer_mode": "bw"})
    assert any("is left off" in w and "name" in w for w in result.warnings)
