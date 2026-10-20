"""The paper preselected for a chart is never smaller than the chart.

Re-review of fix/4.3.8 (2026-10-20): since 4.3.3 beta 16 (66aaab2fd) a size
row left at "Printer Default" was set to the paper whose full sheet is nearest
the chart image, within the 8 % the mismatch check forgives. A chart image
smaller than its sheet (made without printtarg -M, i.e. a chart from outside
ChromIQ: 561 x 808 pt for A4, 578 x 758 pt for Letter) then got a SMALLER paper,
7.75 x 10.75 in on the HP 5550 and DMSIZE_6GIRI on the Canon PRO-300, and the
direct route, which never scales, cut 12 to 13 mm off the chart.

Now a paper is preselected only if the chart fits on it (either orientation,
within 3 pt of rounding); among those, the nearest. ChromIQ's own -M charts,
whose image IS the sheet, get exactly the paper they got before.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

_HP_LIKE = """*PPD-Adobe: "4.3"
*OpenUI *PageSize/Page Size: PickOne
*DefaultPageSize: Letter
*PageSize Letter/Letter: ""
*PageSize A4/A4: ""
*PageSize 7.75x10.75/Monarch 7.75 x 10.75 in: ""
*PageSize Legal/Legal: ""
*CloseUI: *PageSize
*PaperDimension Letter/Letter: "612 792"
*PaperDimension A4/A4: "595 842"
*PaperDimension 7.75x10.75/Monarch 7.75 x 10.75 in: "558 774"
*PaperDimension Legal/Legal: "612 1008"
*ImageableArea Letter/Letter: "12 12 600 780"
*ImageableArea A4/A4: "12 12 583 830"
*ImageableArea 7.75x10.75/Monarch 7.75 x 10.75 in: "12 12 546 762"
*ImageableArea Legal/Legal: "12 12 600 996"
"""

_CANON_LIKE = """*PPD-Adobe: "4.3"
*OpenUI *PageSize/Page Size: PickOne
*DefaultPageSize: A4
*PageSize A4/A4: ""
*PageSize Letter/Letter 8.5"x11": ""
*PageSize DMSIZE_6GIRI/8"x10" 20x25cm: ""
*CloseUI: *PageSize
*PaperDimension A4/A4: "595 842"
*PaperDimension Letter/Letter 8.5"x11": "612 792"
*PaperDimension DMSIZE_6GIRI/8"x10" 20x25cm: "576 720"
*ImageableArea A4/A4: "9 9 586 833"
*ImageableArea Letter/Letter 8.5"x11": "9 9 603 783"
*ImageableArea DMSIZE_6GIRI/8"x10" 20x25cm: "9 9 567 711"
"""


def _pick(tmp_path, ppd_text, items, chart_pt):
    """Run the real `_preselect_paper_for_chart` on a stub tab."""
    import numpy as np
    import tifffile
    import test_beta16_print_package as T
    from ui.tabs.tab_print import TabPrint
    from workflow import page_geometry as pg
    ppd = tmp_path / "q.ppd"
    ppd.write_text(ppd_text, encoding="latin-1")
    w, h = round(chart_pt[0] / 72 * 300), round(chart_pt[1] / 72 * 300)
    tif = tmp_path / "chart_01.tif"
    tifffile.imwrite(str(tif), np.full((h, w, 3), 255, np.uint8), photometric="rgb",
                     resolution=(300, 300), resolutionunit="INCH")
    size = T._Combo([("Printer Default", "")] + items, 0)
    module = SimpleNamespace(
        get_page_size_points=lambda p, *c: next(
            (d for d in (pg.get_page_size_points(str(ppd), x) for x in c if x) if d), None),
        get_imageable_area_points=lambda p, *c: next(
            (d for d in (pg.get_imageable_area_points(str(ppd), x) for x in c if x) if d), None),
        _find_ppd_path=lambda p: str(ppd))
    stub = SimpleNamespace(_option_combos={"PageSize": size}, _tiff_pages=[tif],
                           _printer_combo=SimpleNamespace(currentData=lambda: "Q"),
                           _module=module, _restoring=False,
                           _refresh_quality_row=lambda keep_current: None)
    stub._ppd_default_page = lambda printer: TabPrint._ppd_default_page(stub, printer)
    TabPrint._preselect_paper_for_chart(stub)
    return size.currentData()


_HP_ITEMS = [("Letter", "Letter"), ("A4", "A4"),
             ("Monarch 7.75 x 10.75 in", "7.75x10.75"), ("Legal", "Legal")]
_CANON_ITEMS = [("A4", "A4"), ('Letter 8.5"x11"', "Letter"),
                ('8"x10" 20x25cm', "DMSIZE_6GIRI")]


def test_an_a4_chart_made_without_minus_m_gets_a4_not_a_smaller_paper(tmp_path):
    """HP 5550: 561 x 808 pt (printtarg -pA4 without -M) got 7.75 x 10.75 in
    (558 x 774 pt), 34 pt shorter than the chart."""
    assert _pick(tmp_path, _HP_LIKE, _HP_ITEMS, (561.0, 808.0)) == "A4"


def test_a_letter_chart_made_without_minus_m_gets_letter(tmp_path):
    """Canon PRO-300: 578 x 758 pt got DMSIZE_6GIRI (576 x 720 pt)."""
    assert _pick(tmp_path, _CANON_LIKE, _CANON_ITEMS, (578.0, 758.0)) == "Letter"


def test_a_landscape_chart_fits_the_paper_turned(tmp_path):
    assert _pick(tmp_path, _HP_LIKE, _HP_ITEMS, (808.0, 561.0)) == "A4"


@pytest.mark.parametrize("ppd, items, sheet, want", [
    (_HP_LIKE, _HP_ITEMS, (612, 792), ""),                 # the default itself
    (_HP_LIKE, _HP_ITEMS, (595, 842), "A4"),
    (_HP_LIKE, _HP_ITEMS, (558, 774), "7.75x10.75"),
    (_CANON_LIKE, _CANON_ITEMS, (595, 842), ""),
    (_CANON_LIKE, _CANON_ITEMS, (612, 792), "Letter"),
    (_CANON_LIKE, _CANON_ITEMS, (576, 720), "DMSIZE_6GIRI"),
])
def test_a_chromiq_chart_the_size_of_its_sheet_gets_that_sheet(tmp_path, ppd, items,
                                                               sheet, want):
    """ChromIQ's own charts carry -M: the image IS the sheet, and gets exactly
    the paper it got before the fix."""
    assert _pick(tmp_path, ppd, items, sheet) == want
