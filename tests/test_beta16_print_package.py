"""Beta-16 print package (Basti, 2026-10-09).

1. The Print Chart tab's "Possible paper mismatch" warning and its status
   lines are translated; the warning carries no em dash.
2. (ink-set editions: tests/test_printer_paper_tables_beta16.py)
3. PictureMate: the EPIJ_Size row's sizes have dimensions (found through the
   translation PageSize shares), PPD hex labels are decoded, the job carries
   the matching PageSize, and a row left at "Printer Default" whose paper does
   not match the chart is set to the size that does.
4. Dialog route: a page no paper of a Canon IJ printer matches gets the
   driver's minimum margins (``*HWMargins``) unless chart content lies in them.
5. M-PRINT-QUALITY is approved; the help sentence is the approved one.
"""
from __future__ import annotations

import inspect
from pathlib import Path
from types import SimpleNamespace

import pytest

from core import i18n
from workflow import page_geometry as pg

# Real lines of the EPSON PM-400 Series PPD (driver installed 2026-10-09).
PM400_PPD = """*PPD-Adobe: "4.3"
*OpenUI *EPIJ_Size/Paper Size: PickOne
*DefaultEPIJ_Size: 70
*EPIJ_Size 74/10 x 15 cm (4 x 6 in): ""
*EPIJ_Size 76/13 x 18 cm (5 x 7 in): ""
*EPIJ_Size 70/9 x 13 cm (3<2E>5 x 5 in): ""
*EPIJ_Size 97/16<3A>9 wide size (102 x 181 mm): ""
*CloseUI: *EPIJ_Size
*OpenUI *PageSize: PickOne
*DefaultPageSize: EPPhotoPaperLRoll
*PageSize EPKG/10 x 15 cm (4 x 6 in): "<</PageSize[288.00 432.00]/ImagingBBox null>>setpagedevice"
*PageSize EPKG.NMgn/10 x 15 cm (4 x 6 in) (Borderless): "<</PageSize[288.00 432.00]>>setpagedevice"
*PageSize EPPhotoPaper2L/13 x 18 cm (5 x 7 in): "<</PageSize[360.00 504.40]/ImagingBBox null>>setpagedevice"
*PageSize EPPhotoPaperLRoll/9 x 13 cm (3<2E>5 x 5 in): "<</PageSize[252.20 360.00]/ImagingBBox null>>setpagedevice"
*PageSize EPHiVision102x180/16<3A>9 wide size (102 x 181 mm): "<</PageSize[288.00 512.00]>>setpagedevice"
*CloseUI: *PageSize
*ImageableArea EPKG/10 x 15 cm (4 x 6 in): "8.40 8.40 279.60 423.60"
*ImageableArea EPPhotoPaper2L/13 x 18 cm (5 x 7 in): "8.40 8.40 351.60 496.00"
*ImageableArea EPPhotoPaperLRoll/9 x 13 cm (3<2E>5 x 5 in): "8.40 8.40 243.80 351.60"
*PaperDimension EPKG/10 x 15 cm (4 x 6 in): "288.00 432.00"
*PaperDimension EPKG.NMgn/10 x 15 cm (4 x 6 in) (Borderless): "288.00 432.00"
*PaperDimension EPPhotoPaper2L/13 x 18 cm (5 x 7 in): "360.00 504.40"
*PaperDimension EPPhotoPaperLRoll/9 x 13 cm (3<2E>5 x 5 in): "252.20 360.00"
*PaperDimension EPHiVision102x180/16<3A>9 wide size (102 x 181 mm): "288.00 512.00"
"""

# Real lines of the Canon imagePROGRAF PRO-2100 PPD.
PRO2100_PPD = """*PPD-Adobe: "4.3"
*OpenUI *CNIJMediaType/Media Type: PickOne
*CloseUI: *CNIJMediaType
*HWMargins: 8.50 8.50 8.50 8.50
*PaperDimension A4/A4: "595.28 841.89"
*PaperDimension Letter/Letter: "612.00 792.00"
"""


@pytest.fixture
def lang():
    yield i18n.set_language
    i18n.set_language("en")


# ---- 1. translated ----------------------------------------------------------------------------
def test_the_mismatch_warning_is_translated_and_has_no_em_dash(lang):
    en = pg.check_size_mismatch(595.0, 842.0, 252.0, 360.0)
    assert en.startswith("Possible paper mismatch") and "—" not in en
    assert "210 × 297 mm" in en and "89 × 127 mm" in en
    lang("de")
    de = pg.check_size_mismatch(595.0, 842.0, 252.0, 360.0)
    assert de.startswith("Mögliche Papierabweichung") and "210 × 297 mm" in de


@pytest.mark.parametrize("code", ["de", "es", "fr", "it", "ja", "nl", "no", "pl", "pt",
                                  "ru", "sv", "uk", "zh_CN"])
def test_every_language_has_the_print_tab_texts(code):
    import json
    cat = json.loads((Path(__file__).resolve().parent.parent / "data" / "i18n"
                      / f"{code}.json").read_text(encoding="utf-8"))
    for key in ("Print settings saved as defaults.", "No jobs in the queue to clear.",
                "Cleared 1 job from the queue.", "Cleared {n} jobs from the queue.",
                "No TIFF files found matching the selected .ti2 file."):
        assert cat.get(key), (code, key)
    assert any(k.startswith("Possible paper mismatch") for k in cat), code


def _status_stub(**kw):
    seen = []
    stub = SimpleNamespace(_set_status=seen.append, **kw)
    return stub, seen


def test_the_status_lines_are_translated(lang):
    from ui.tabs.tab_print import TabPrint
    lang("de")
    combo = SimpleNamespace(currentData=lambda: "Q")
    stub, seen = _status_stub(_printer_combo=combo, _option_combos={},
                              _settings=SimpleNamespace(set=lambda *a: None))
    TabPrint._on_save_defaults(stub)
    stub._module = SimpleNamespace(cancel_all_jobs=lambda p: 0)
    TabPrint._on_clear_queue(stub)
    stub._module = SimpleNamespace(cancel_all_jobs=lambda p: 3)
    TabPrint._on_clear_queue(stub)
    assert seen == ["Druckeinstellungen als Standard gespeichert.",
                    "Keine Druckaufträge in der Warteschlange.",
                    "3 Druckaufträge aus der Warteschlange entfernt."]


# ---- 3. PictureMate paper sizes ---------------------------------------------------------------
@pytest.fixture
def pm400(tmp_path):
    p = tmp_path / "pm400.ppd"
    p.write_text(PM400_PPD, encoding="latin-1")
    return str(p)


def test_ppd_hex_labels_are_decoded():
    assert pg.ppd_text_label("9 x 13 cm (3<2E>5 x 5 in)") == "9 x 13 cm (3.5 x 5 in)"
    assert pg.ppd_text_label("16<3A>9 wide size") == "16:9 wide size"
    assert pg.ppd_text_label("A4") == "A4"


def test_an_epson_size_code_finds_its_dimensions_through_the_label(pm400):
    """Beta 16 had none for 10 x 15, 13 x 18, 9 x 13 or 16:9 on the PM-400."""
    assert pg.get_page_size_points(pm400, "10 x 15 cm (4 x 6 in)") == (288.0, 432.0)
    assert pg.get_page_size_points(pm400, "9 x 13 cm (3.5 x 5 in)") == (252.2, 360.0)
    assert pg.get_page_size_points(pm400, "16:9 wide size (102 x 181 mm)") == (288.0, 512.0)
    w, h = pg.get_imageable_area_points(pm400, "13 x 18 cm (5 x 7 in)")
    assert (round(w, 1), round(h, 1)) == (343.2, 487.6)
    assert pg.get_page_size_points(pm400, "74") is None      # a code is not a label


def test_the_labels_shown_are_decoded_and_the_job_carries_the_page_size(pm400, monkeypatch):
    from workflow.print_manager import PrintModule
    monkeypatch.setattr(PrintModule, "_find_ppd_path", staticmethod(lambda p: pm400))
    labels = PrintModule._parse_ppd_labels("Q")
    assert labels["EPIJ_Size"]["70"] == "9 x 13 cm (3.5 x 5 in)"
    m = PrintModule()
    assert m.build_config("Q", {"EPIJ_Size": "74"}).options["PageSize"] == "EPKG"
    assert m.build_config("Q", {"EPIJ_Size": "70"}).options["PageSize"] == "EPPhotoPaperLRoll"
    # a PageSize already chosen stays
    assert m.build_config("Q", {"EPIJ_Size": "74", "PageSize": "X"}).options["PageSize"] == "X"


class _Combo:
    def __init__(self, items, current=0):
        self.items, self.cur = items, current

    def currentData(self):
        return self.items[self.cur][1]

    def count(self):
        return len(self.items)

    def itemData(self, i):
        return self.items[i][1]

    def itemText(self, i):
        return self.items[i][0]

    def setCurrentIndex(self, i):
        self.cur = i

    def findData(self, v):
        return next((i for i, (_t, d) in enumerate(self.items) if d == v), -1)


def _preselect_stub(pm400, chart, current=0):
    from ui.tabs.tab_print import TabPrint
    items = [("Printer Default", ""), ("10 x 15 cm (4 x 6 in)", "74"),
             ("13 x 18 cm (5 x 7 in)", "76"), ("9 x 13 cm (3.5 x 5 in)", "70")]
    combo = _Combo(items, current)
    module = SimpleNamespace(
        get_page_size_points=lambda p, *c: next(
            (d for d in (pg.get_page_size_points(pm400, x) for x in c if x) if d), None),
        get_imageable_area_points=lambda p, *c: next(
            (d for d in (pg.get_imageable_area_points(pm400, x) for x in c if x) if d), None),
        _find_ppd_path=lambda p: pm400)
    stub = SimpleNamespace(_option_combos={"EPIJ_Size": combo}, _tiff_pages=[chart],
                           _printer_combo=SimpleNamespace(currentData=lambda: "Q"),
                           _module=module, _restoring=False,
                           _refresh_quality_row=lambda keep_current: None)
    stub._ppd_default_page = lambda printer: TabPrint._ppd_default_page(stub, printer)
    TabPrint._preselect_paper_for_chart(stub)
    return combo


def _chart(tmp_path, w_mm, h_mm):
    import numpy as np
    import tifffile
    w, h = round(w_mm / 25.4 * 100), round(h_mm / 25.4 * 100)
    p = tmp_path / f"c{w_mm}x{h_mm}.tif"
    tifffile.imwrite(str(p), np.full((h, w, 3), 255, np.uint8), photometric="rgb",
                     resolution=(100, 100), resolutionunit="INCH")
    return p


def test_the_size_that_fits_the_chart_is_preselected(pm400, tmp_path):
    """PM-400, Basti 2026-10-09: the driver's default is 9 x 13 cm, so a
    10 x 15 cm chart was taken for one larger than the paper."""
    combo = _preselect_stub(pm400, _chart(tmp_path, 102, 152))
    assert combo.currentData() == "74"
    combo = _preselect_stub(pm400, _chart(tmp_path, 127, 178))
    assert combo.currentData() == "76"


def test_the_drivers_default_and_a_users_choice_stay(pm400, tmp_path):
    # the chart is the default paper's: nothing to change
    assert _preselect_stub(pm400, _chart(tmp_path, 89, 127)).currentData() == ""
    # no size matches an A4 chart: the default stays and the warning will say so
    assert _preselect_stub(pm400, _chart(tmp_path, 210, 297)).currentData() == ""
    # a size the user chose is never touched
    assert _preselect_stub(pm400, _chart(tmp_path, 102, 152), current=2).currentData() == "76"


# ---- 4. custom paper margins on the dialog route ------------------------------------------------
def test_canon_minimum_margins_come_from_the_ppd():
    from workflow import native_print_macos as npm
    assert npm._canon_min_margins(PRO2100_PPD) == (8.5, 8.5, 8.5, 8.5)
    assert npm._canon_min_margins(PM400_PPD) is None           # not a Canon IJ
    assert npm._canon_min_margins(PRO2100_PPD.replace("8.50", "0")) is None


def test_a_named_paper_is_not_made_a_custom_one():
    from workflow import native_print_macos as npm
    assert npm._is_named_paper(PRO2100_PPD, 595.28, 841.89)
    assert npm._is_named_paper(PRO2100_PPD, 841.89, 595.28)      # landscape
    assert not npm._is_named_paper(PRO2100_PPD, 360.0, 504.0)    # 5 x 7 in


def test_content_inside_the_margins_keeps_the_page_as_it_was():
    from workflow import native_print_macos as npm
    m = (8.5, 8.5, 8.5, 8.5)
    page = (360.0, 504.0)
    assert npm.content_inside_margins([(20, 20, 340, 484)], [page], page, m)
    assert not npm.content_inside_margins([(20, 5, 340, 484)], [page], page, m)
    assert not npm.content_inside_margins([(20, 20, 355, 484)], [page], page, m)
    # a smaller page centred in the box has room to spare
    assert npm.content_inside_margins([(0, 0, 300, 400)], [(300.0, 400.0)], page, m)
    assert npm.content_inside_margins([None], [page], page, m)


def test_the_dialog_route_gives_the_page_the_margins_before_and_after_the_panel():
    from workflow import native_print_macos as npm
    src = inspect.getsource(npm.print_frames)
    assert src.count("give_custom_paper_driver_margins(") == 2
    assert src.index("give_custom_paper_driver_margins(") < src.index("runModalWithPrintInfo_")
    assert src.rindex("give_custom_paper_driver_margins(") < src.index("runOperation()")


# ---- 5. approved texts ----------------------------------------------------------------------------
def test_print_quality_is_approved():
    from workflow import measurement_messages as MM
    assert MM.M_PRINT_QUALITY.approved
    assert "M-PRINT-QUALITY" not in MM.PROPOSED


def test_the_help_sentence_is_the_approved_one():
    from ui.tabs import tab_print
    body = tab_print._TT_BODY_PRINT_MACOS_BYPASS
    assert ("On a Canon or Epson the quality row lists the qualities the driver allows "
            "for this paper; ChromIQ preselects the one you last used in the print "
            "dialog for it, otherwise the driver's standard.") in body
    assert "usually an Epson left at" not in body
