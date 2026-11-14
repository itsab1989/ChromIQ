"""Nothing printed in an i1iSis chart's text band collides (the owner,
2026-11-14: on smaller papers the name line ran into the corner labels "A1"
and "N1"), and nothing leaves its zone.

A sweep over every paper the i1iSis entry offers (both models, Guided's
short-sheet margins), the narrowest custom sheet (60 mm), the narrowest
chart (a few columns), two-letter columns, 1 to 9+ pages, long and wide
and non-Latin chart names, tight margins, the barcode, strip letters at the
top or in the trailer, row numbers and trailer notes. The boxes are the
RENDERER's, at 300 dpi: the ink each text run, label and the wordmark
really took on the page.
"""
from __future__ import annotations

import itertools

import pytest
from PIL import Image

from workflow.isis import chart as C
from workflow.isis import chart_facts as F
from workflow.layout_engine import papers

DPI = 300
S = DPI / 25.4

NAMES = {
    "none": "",
    "short": "iSis",
    "long wide": "WWWW-MMMM-Canon-PRO-1000-Hahnemuehle-Photo-Rag-Baryta-315-gsm-Matte",
    "non-Latin": "Ångström-Тестовая-таблица-校准图表-チャート-Ελληνικά-ÆØÅ-Ünïcödé-x",
}

PAPERS = (list(C.GUIDED_PAPERS_XL) + ["60x200", "80x250", "100x660"])

TEXT_ROLES = {"name_line", "wordmark", "corner", "strip_letter", "row_number",
              "notes", "stamp"}


def _cases():
    out = []
    for paper in PAPERS:
        for model in ("", "xl"):
            if model == "" and paper in ("A3", "279x432", "329x483"):
                continue
            for n in (3, 40, 957):
                out.append((paper, model, n, {}))
    # narrow sheets over many pages; two-letter columns
    out += [("60x200", "", 600, {}), ("60x200", "", 1200, {}),
            ("A4", "", 2900, {}), ("329x483", "xl", 3000, {}),
            ("329x483", "xl", 1617, {"draw_indicators": True,
                                     C.LETTERS_KEY: "top"}),
            ("60x200", "", 40, {C.TIGHT_KEY: True, C.BARCODE_KEY: True}),
            ("127x178", "", 40, {"draw_indicators": True,
                                 C.LETTERS_KEY: "top",
                                 "row_indicators": True}),
            ("80x250", "", 300, {"draw_indicators": True,
                                 C.LETTERS_KEY: "bottom",
                                 C.NOTES_LINES_KEY: ("a" * 120,
                                                     "settings line")}),
            ("A4", "", 957, {C.TIGHT_KEY: True, C.BARCODE_KEY: True,
                             C.HEADER_KEY: 80.0})]
    return out


def _intersect(a, b) -> bool:
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


@pytest.mark.parametrize("paper,model,n,extra", _cases())
@pytest.mark.parametrize("name", sorted(NAMES))
def test_no_text_collides_and_all_stays_in_its_zone(paper, model, n, extra,
                                                    name):
    w, h = papers.dimensions_mm(paper)
    kw = {**extra, C.MODEL_KEY: model or "standard", C.COUNT_KEY: n,
          "paper": paper}
    gm = C.guided_margins(paper)
    if gm is not None:
        kw["margins"] = gm
    try:
        _o, g, sheet = C.layout_for(n, w, h, kw)
    except C.IsisSheetRefused:
        pytest.skip("a sheet the i1iSis refuses")
    img = Image.new("RGB", (int(round(w * S)), int(round(h * S))), "white")
    pages = sorted({0, g.P - 1, min(1, g.P - 1)})
    for page in pages:
        items, _off = C.plan_page(sheet, page, name=NAMES[name],
                                  title=NAMES[name],
                                  stamp_text="ChromIQ engine · i1iSis")
        assert C.keep_out_violations(sheet, items) == [], (paper, page)
        if g.P > 1:
            line = [i for i in items if i.role == "name_line"][0]
            assert f"{page + 1}/{g.P}" in line.text, (paper, page,
                                                      line.text)
        boxes: list = []
        C.draw_page(img, None, sheet, items, DPI, ink_boxes=boxes)
        boxes = [(r, b) for r, b in boxes if r in TEXT_ROLES
                 and b[2] > b[0] and b[3] > b[1]]
        # corner labels are always drawn while their option is on
        assert sum(r == "corner" for r, _b in boxes) == 4
        top_band = (sheet.x0 * S, sheet.y0 * S,
                    (sheet.x0 + sheet.width) * S,
                    (sheet.bar_y - F.CLEAR_ABOVE_BAR_MM.value) * S)
        for (ra, a), (rb, b) in itertools.combinations(boxes, 2):
            if ra == rb and ra in ("strip_letter", "row_number", "notes", "stamp"):
                continue        # a row of their own kind, checked below
            assert not _intersect(a, b), (paper, model, n, name, page,
                                          ra, a, rb, b)
        for r, b in boxes:
            if r in ("name_line", "wordmark") or (
                    r == "corner" and b[1] < top_band[3]):
                assert top_band[0] - 1 <= b[0] and b[2] <= top_band[2] + 1, \
                    (paper, r, b, top_band)
                assert top_band[1] - 1 <= b[1] and b[3] <= top_band[3] + 1, \
                    (paper, r, b, top_band)
        # letters (and numbers) of one row never overlap each other
        for role in ("strip_letter", "row_number"):
            row = sorted(b for r, b in boxes if r == role)
            for a, b in zip(row, row[1:]):
                assert not _intersect(a, b), (paper, role, a, b)
        img.paste((255, 255, 255), (0, 0, img.width, img.height))


def test_the_name_is_shortened_in_its_middle():
    assert C.mid_ellipsis("Canon-PRO-1000-Baryta", 9) == "Cano…ryta"
    assert C.mid_ellipsis("short", 9) == "short"
