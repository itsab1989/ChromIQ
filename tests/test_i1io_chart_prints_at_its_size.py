"""AN i1iO CHART GOES TO THE PRINTER AT ITS OWN SIZE, PORTRAIT, UNSCALED.

No agent prints (the 2026-11-13 incident); printing an i1iO chart is proved
here with the print layer's own document makers and nothing else: no
NSPrintOperation, no subprocess, no queue. For A4 and Letter, one and
several pages, every page of a real i1iO build becomes a PostScript and a
PDF document whose page is the sheet's own size in portrait (the sheet is
laid across the table, so it is printed portrait), and the image is placed
at exactly that size: not scaled to fit.
"""
from __future__ import annotations

import os
import re

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from tests.test_i1io_chart import _ti1  # noqa: E402

SIZES_PT = {"A4": (595.28, 841.89), "Letter": (612.0, 792.0)}


@pytest.fixture(autouse=True)
def i1io_on():
    from workflow.i1io import support
    before = support._latched
    support.set_enabled_for_this_process(True)
    try:
        yield
    finally:
        support._latched = before


@pytest.mark.parametrize("paper,n", [("A4", 300), ("Letter", 900)])
def test_every_page_prints_portrait_at_the_sheets_size(tmp_path, paper, n):
    from workflow.layout_engine import chart
    from workflow.postscript_generator import PdfGenerator, PostScriptGenerator
    result = chart.build_chart(_ti1(tmp_path / "c.ti1", n), tmp_path / "c",
                               instrument="IO2", paper=paper, dpi=100,
                               seed=1, project="P", chart_date="x")
    assert result.tiff_paths
    want_w, want_h = SIZES_PT[paper]
    for tif in result.tiff_paths:
        ps = PostScriptGenerator().generate(tif, dpi=100)
        size = re.search(r"/PageSize \[([\d.]+) ([\d.]+)\]", ps)
        assert size, "no PageSize"
        w, h = float(size.group(1)), float(size.group(2))
        assert (w, h) == pytest.approx((want_w, want_h), abs=1.5)
        assert w < h                                     # portrait
        # drawn at the page's own size: no scaling to fit
        sc = re.search(r"([\d.]+) ([\d.]+) scale", ps)
        assert sc and (float(sc.group(1)), float(sc.group(2))) == \
            pytest.approx((w, h), abs=1.5)
        pdf = PdfGenerator().generate(tif, dpi=100)
        box = re.search(rb"/MediaBox \[\s*0 0 ([\d.]+) ([\d.]+)\s*\]", pdf)
        assert box, "no MediaBox"
        assert (float(box.group(1)), float(box.group(2))) == pytest.approx(
            (want_w, want_h), abs=1.5)
