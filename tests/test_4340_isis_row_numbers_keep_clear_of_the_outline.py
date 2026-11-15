"""4.3.40, F1: an i1iSis chart's row numbers lie fully inside the dashed
outline, with ROW_NUMBER_GAP_MM of clear paper before its line.

Found on screen 2026-11-15 (XL, A3 portrait, 8 mm patches, 20 mm side
margins, notes band in the header): "10" to "39" printed 0.17 mm from the
right dashes and read as sitting on them. The numbers were planned against
the line's inner edge with only their box's 0.1 mm spare.

A sweep over papers x models x patch sizes x side margins (and tight
margins, the barcode, a pushed-out offset, few and full-page patch counts):
every printed number's box, and the ink the renderer really drew at 300 dpi,
ends at least the gap before the outline's inner edge, starts inside the
outline, stays in its own row, and overlaps no diamond (with its 3 mm), no
patch, no other label and no other text. Where there is no room the numbers
are left off, the side file says so and the build says
M-ISIS-ROW-NUMBERS-NO-ROOM. Every printed number is the layout's own row
name.
"""
from __future__ import annotations

import pytest
from PIL import Image

from workflow.isis import chart as C
from workflow.isis import chart_facts as F
from workflow.layout_engine import papers

DPI = 300
S = DPI / 25.4
#: One pixel at 300 dpi: what rounding may take from the drawn gap.
PX = 1.0 / S

PAPERS = list(C.GUIDED_PAPERS_XL) + ["60x200", "100x660"]
PATCHES = (6.0, 8.0, 12.0, 20.0)
SIDES = ((5.0, 5.0), (20.0, 20.0), (0.0, 0.0), (10.0, 30.0))


def _cases():
    out = []
    for paper in PAPERS:
        for model in ("standard", "xl"):
            for patch in PATCHES:
                for left, right in SIDES:
                    out.append((paper, model, patch, (5.0, right, 5.0, left),
                                {}))
    # tight margins, the barcode, the notes band, a pushed-out number
    for paper in ("A4", "A3", "Letter"):
        out += [(paper, "xl", 6.0, (5.0, 5.0, 5.0, 5.0),
                 {C.TIGHT_KEY: True}),
                (paper, "standard", 8.0, (5.0, 5.0, 5.0, 5.0),
                 {C.BARCODE_KEY: True, "isis_notes_band": True}),
                (paper, "xl", 8.0, (5.0, 20.0, 5.0, 20.0),
                 {"strip_label_offset_x_mm": 2.0}),
                (paper, "xl", 8.0, (5.0, 20.0, 5.0, 20.0),
                 {"indicator_size_mm": 4.0})]
    return out


_IMAGES: dict = {}


def _blank(w: float, h: float) -> Image.Image:
    key = (int(round(w * S)), int(round(h * S)))
    img = _IMAGES.get(key)
    if img is None:
        img = _IMAGES[key] = Image.new("RGB", key, "white")
    return img


def _intersects(a, b) -> bool:
    return (a[0] < b[0] + b[2] - 1e-6 and b[0] < a[0] + a[2] - 1e-6
            and a[1] < b[1] + b[3] - 1e-6 and b[1] < a[1] + a[3] - 1e-6)


@pytest.mark.parametrize("paper,model,patch,margins,extra", _cases())
@pytest.mark.parametrize("count", ("few", "full"))
def test_row_numbers_lie_inside_the_outline_with_a_gap(paper, model, patch,
                                                       margins, extra,
                                                       count):
    w, h = papers.dimensions_mm(paper)
    kw = {C.MODEL_KEY: model, "paper": paper, "patch_w": patch,
          "patch_h": patch, "margins": margins, "row_indicators": True,
          **extra}
    try:
        n = 40 if count == "few" else C.capacity(kw)
        kw[C.COUNT_KEY] = n
        _o, g, sheet = C.layout_for(n, w, h, kw)
    except C.IsisSheetRefused:
        return      # a sheet the i1iSis refuses: nothing is printed on it
    items, off = C.plan_page(sheet, 0, name="rows")
    numbers = [i for i in items if i.role == "row_number"]
    side = C.side_doc(sheet, paper=paper, name="rows", title="rows")
    if not numbers:
        # no room: left off, and said
        assert "row_numbers" in off
        assert side["row_numbers"] == "left_off"
        assert C.keep_out_message("row_numbers")
        return
    assert side["row_numbers"] == "printed"
    assert "row_numbers" not in off
    assert len(numbers) == g.R
    # every number printed is the layout's own row name
    assert [i.text for i in numbers] == [C.row_name(r) for r in range(g.R)]

    line = F.OUTLINE_LINE_MM.value
    inner_right = sheet.x0 + sheet.width - line
    inner = (sheet.x0 + line, sheet.y0 + line,
             sheet.width - 2 * line, sheet.height - 2 * line)
    keep = sheet.keep_out()
    others = [i for i in items if i.role != "row_number"
              and i.kind in ("text", "rect", "diamond", "wordmark", "band")]
    for r, it in enumerate(numbers):
        x, y, bw, bh = it.box
        # inside the outline, the gap before its right line
        assert x + bw <= inner_right - C.ROW_NUMBER_GAP_MM + 1e-6, \
            (paper, model, patch, margins, it.text, x + bw, inner_right)
        assert x >= inner[0] and y >= inner[1] \
            and y + bh <= inner[1] + inner[3], (paper, it.text, it.box)
        # in its own row
        top = sheet.grid_y + r * sheet.opts.ph
        assert top - 1e-6 <= y and y + bh <= top + sheet.opts.ph + 1e-6
        # no diamond (with its 3 mm), no patch, nothing else
        for name, zone in keep:
            if name in ("diamond", "grid"):
                assert not _intersects(it.box, zone), (paper, it.text, name)
        for o in others:
            assert not _intersects(it.box, o.box), (paper, it.text, o.role)
    assert C.keep_out_violations(sheet, items) == []

    # the ink the renderer really drew, at 300 dpi
    img = _blank(w, h)
    boxes: list = []
    C.draw_page(img, None, sheet, numbers, DPI, ink_boxes=boxes)
    img.paste((255, 255, 255), (0, 0, img.width, img.height))
    inks = [b for role, b in boxes if role == "row_number"]
    assert len(inks) == g.R
    for b in inks:
        assert b[2] / S <= inner_right - C.ROW_NUMBER_GAP_MM + PX, \
            (paper, model, patch, margins, b[2] / S, inner_right)
        assert b[0] / S >= sheet.right_marker_edge \
            + F.DIAMOND_CLEAR_MM.value - PX


def test_the_reported_chart_keeps_its_numbers_with_the_gap():
    """The exact chart of the finding: XL, A3 portrait, 8 mm patches,
    20 mm side margins, the notes band in the header, 1092 patches."""
    kw = {C.MODEL_KEY: "xl", "paper": "A3", "patch_w": 8.0, "patch_h": 8.0,
          "margins": (5.0, 20.0, 5.0, 20.0), "row_indicators": True,
          "isis_notes_band": True, C.COUNT_KEY: 1092}
    _o, g, sheet = C.layout_for(1092, 297.0, 420.0, kw)
    items, off = C.plan_page(sheet, 0, name="Showcase-iSis-XL")
    numbers = [i for i in items if i.role == "row_number"]
    assert (g.C, g.R) == (28, 39) and len(numbers) == 39 and not off
    img = _blank(297.0, 420.0)
    boxes: list = []
    C.draw_page(img, None, sheet, numbers, DPI, ink_boxes=boxes)
    img.paste((255, 255, 255), (0, 0, img.width, img.height))
    inner_right = sheet.x0 + sheet.width - F.OUTLINE_LINE_MM.value
    gap = min(inner_right - b[2] / S for _r, b in boxes)
    # before the fix: 0.17 mm; the outline's own line width at least now
    assert gap >= F.OUTLINE_LINE_MM.value, gap


@pytest.mark.parametrize("paper", ["A4", "Letter"])
def test_the_default_a4_and_letter_charts_still_print_their_numbers(paper):
    """The gap must not bring back 4.3.38's fault ("Show row indicators"
    had no effect on a default chart): Guided's default A4 and Letter
    charts, full page, still print them."""
    w, h = papers.dimensions_mm(paper)
    for model in ("standard", "xl"):
        kw = {C.MODEL_KEY: model, "paper": paper, "row_indicators": True}
        gm = C.guided_margins(paper)
        if gm is not None:
            kw["margins"] = gm
        n = C.capacity(kw)
        kw[C.COUNT_KEY] = n
        _o, _g, sheet = C.layout_for(n, w, h, kw)
        items, off = C.plan_page(sheet, 0, name="x")
        assert any(i.role == "row_number" for i in items), (paper, model)
        assert "row_numbers" not in off
