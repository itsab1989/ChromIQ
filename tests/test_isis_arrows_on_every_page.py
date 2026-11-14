"""With "Feed arrows" on (the default) the two feed arrows are on EVERY page
of EVERY i1iSis chart, whatever the layout: tight margins, a long header,
the notes band in the header or the trailer, the barcode, the XL models,
every page of a multi-page chart, charts that must be cut, area-first,
strip letters and row numbers (the owner, 2026-11-14: "in some cases it did
not show the arrows on the top of the chart"). Off, there are none. The
same for the dashed outline. Guided always prints both.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from workflow.isis import chart as C
from workflow.isis import chart_facts as F

CASES = {
    "A4 default": (957, 210, 297, {}),
    "Letter": (957, 215.9, 279.4, {}),
    "tight": (957, 210, 297, {C.TIGHT_KEY: True}),
    "header 80, cut": (957, 210, 297, {C.HEADER_KEY: 80.0}),
    "barcode, two pages": (957, 210, 297, {C.BARCODE_KEY: True}),
    "notes band header": (957, 210, 297, {C.BAND_KEY: True,
                                          C.BAND_PLACE_KEY: "header",
                                          C.BAND_HEIGHT_KEY: 24}),
    "notes band trailer": (957, 210, 297, {C.BAND_KEY: True,
                                           C.BAND_PLACE_KEY: "trailer",
                                           C.BAND_HEIGHT_KEY: 48}),
    "XL A3+": (1617, 329, 483, {C.MODEL_KEY: "xl"}),
    "XL, empty columns, 3 pages": (100, 215.9, 279.4,
                                   {C.MODEL_KEY: "xl", "patch_w": 20,
                                    "patch_h": 20}),
    "three pages": (2900, 210, 297, {}),
    "8 mm, two pages": (957, 210, 297, {"patch_w": 8, "patch_h": 8}),
    "area-first": (300, 210, 297, {"layout_mode": "area_first"}),
    "letters top, row numbers": (957, 210, 297,
                                 {"draw_indicators": True,
                                  C.LETTERS_KEY: "top",
                                  "row_indicators": True}),
    "bottom-right, offset (cut)": (300, 210, 297,
                                   {C.ALIGN_KEY: "bottom-right",
                                    "offset_x": 20, "offset_y": 15}),
    "5 x 7 in": (60, 127, 178, {"margins": C.guided_margins("127x178")}),
}


def _sheet(n, w, h, kw):
    return C.layout_for(n, w, h, {**kw, C.COUNT_KEY: n, "paper": f"{w}x{h}"})


def _ink(img, box, s):
    x, y, bw, bh = box
    a = np.asarray(img.convert("L"))[int(y * s):int((y + bh) * s),
                                       int(x * s):int((x + bw) * s)]
    return float((a < 100).mean()) if a.size else 0.0


@pytest.mark.parametrize("case", sorted(CASES))
@pytest.mark.parametrize("on", [True, False])
def test_the_arrows_and_the_outline_on_every_page(case, on):
    n, w, h, kw = CASES[case]
    _o, g, sheet = _sheet(n, w, h, {**kw, C.ARROWS_KEY: on,
                                    C.OUTLINE_KEY: on})
    dpi = 60
    s = dpi / 25.4
    for page in range(g.P):
        items, _off = C.plan_page(sheet, page, name="arrows", title="arrows")
        arrows = [i for i in items if i.kind == "arrow"]
        dashes = [i for i in items if i.kind == "dash"]
        assert len(arrows) == (2 if on else 0), (case, page)
        assert len(dashes) == (1 if on else 0), (case, page)
        assert C.keep_out_violations(sheet, items) == [], (case, page)
        img = Image.new("RGB", (int(round(w * s)), int(round(h * s))),
                        "white")
        C.draw_page(img, None, sheet, items, dpi)
        a0, a1 = F.ARROW_Y_MM.value
        for x in (sheet.left_diamond_x, sheet.right_diamond_x):
            box = (x, sheet.y0 + a0, F.DIAMOND_W_MM.value, a1 - a0)
            # on the paper, in the diamond column, ahead of the bar
            assert box[1] + box[3] <= sheet.bar_y, (case, page)
            assert 0 <= box[0] and box[0] + box[2] <= w, (case, page)
            ink = _ink(img, box, s)
            if on:
                assert ink > 0.25, (case, page, x, ink)
            else:
                assert ink < 0.02, (case, page, x, ink)


def test_guided_always_prints_the_arrows_and_the_outline(tmp_path: Path):
    from workflow.chart_creator import ChartCreator, ChartParams
    from tests.test_chart_creator_engine import (_EngineRunner,
                                                 _EngineSettings,
                                                 _MockFileManager)
    from workflow.isis import support
    before = support._latched
    support.set_enabled_for_this_process(True)
    try:
        creator = ChartCreator(_EngineRunner(),
                               _MockFileManager(tmp_path / "p"),
                               _EngineSettings())
        for extra in ({}, {"isis_model": "xl"}, {"isis_notes_band": True}):
            p = ChartParams(instrument="XRISIS", paper="A4", pages=1)
            for k, v in extra.items():
                setattr(p, k, v)
            kw = creator._engine_build_kwargs(p)
            o = C.options_from(kw)
            assert o.arrows and o.outline, extra
    finally:
        support._latched = before


def test_every_guided_paper_makes_a_chart(tmp_path: Path):
    """Guided offers these sheets for the i1iSis; each must make a chart
    (5 x 7 in was refused: 5 mm margins left 167.8 of the 171 mm needed)."""
    from workflow.chart_creator import ChartCreator, ChartParams
    from tests.test_chart_creator_engine import (_EngineRunner,
                                                 _EngineSettings,
                                                 _MockFileManager)
    from workflow.isis import support
    before = support._latched
    support.set_enabled_for_this_process(True)
    try:
        creator = ChartCreator(_EngineRunner(),
                               _MockFileManager(tmp_path / "p"),
                               _EngineSettings())
        for model, papers in (("", C.GUIDED_PAPERS),
                              ("xl", C.GUIDED_PAPERS_XL)):
            for paper in papers:
                p = ChartParams(instrument="XRISIS", paper=paper, pages=1)
                p.isis_model = model
                kw = creator._engine_build_kwargs(p)
                n = creator._lookup_patches(p)
                assert n and n > 0, (model, paper)
                w, h = __import__("workflow.layout_engine.papers",
                                  fromlist=["x"]).dimensions_mm(paper)
                _o, g, sheet = C.layout_for(n, w, h, {**kw,
                                                      C.COUNT_KEY: n})
                assert sheet.height >= F.CHART_MIN_LENGTH_MM.value
                assert sheet.y0 + sheet.height <= h + 1e-6, paper
    finally:
        support._latched = before
