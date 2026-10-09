"""Review of the beta-16 print package (2026-10-09): three weak spots fixed.

1. Dialog route, Canon imagePROGRAF: a page no named paper matches gets the
   driver's minimum margins only when no chart content lies inside them, and
   "content" was every ink pixel. printtarg prints its info line rotated along
   the chart's side, and on a 4 x 6 in chart made with -M6 it runs from the
   top edge to the bottom edge, so such a chart kept no margins and the
   Canon alert the package was made to prevent came back. Only SOLID ink
   (patches, scan markers) now counts; the driver's band may clip the line.
2. PictureMate PM-400/PM-520: the tab showed two "Borderless" rows, the
   synthetic one from EPIJ_PSrc and the PPD's own EPIJ_Bdls.
3. The M-PRINT-QUALITY note showed while the quality row stood at "Printer
   Default", where "this quality" names nothing.
"""
from __future__ import annotations

import subprocess
from types import SimpleNamespace

import numpy as np
import pytest

from workflow import native_print_macos as npm


# ---- 1. solid ink ---------------------------------------------------------------
def _page(w_mm=101.6, h_mm=152.4, dpi=300):
    w, h = int(round(w_mm / 25.4 * dpi)), int(round(h_mm / 25.4 * dpi))
    return np.full((h, w, 3), 255, np.uint8), dpi


def _mm(v, dpi=300):
    return int(round(v / 25.4 * dpi))


def test_a_text_line_from_edge_to_edge_does_not_count_as_content():
    a, dpi = _page()
    a[_mm(20):_mm(140), _mm(25):_mm(75)] = (200, 30, 30)        # the patches
    a[:, _mm(90):_mm(90) + 3] = 0                                # a 0.25 mm line, edge to edge
    size = (a.shape[1] * 72 / dpi, a.shape[0] * 72 / dpi)
    every = npm._content_box_pt(a, dpi, dpi)
    solid = npm._solid_box_pt(a, dpi, dpi)
    m = (8.5, 8.5, 8.5, 8.5)
    assert not npm.content_inside_margins([every], [size], size, m)
    assert npm.content_inside_margins([solid], [size], size, m)
    # the box is the patches', give or take a cell
    x0, y0, x1, y1 = (v * 25.4 / 72 for v in solid)
    assert abs(x0 - 25) < 0.7 and abs(y0 - 20) < 0.7
    assert abs(x1 - 75) < 0.7 and abs(y1 - 140) < 0.7


def test_a_patch_inside_the_band_still_keeps_the_page_without_margins():
    a, dpi = _page()
    a[_mm(1):_mm(140), _mm(25):_mm(75)] = (200, 30, 30)         # 1 mm from the top
    size = (a.shape[1] * 72 / dpi, a.shape[0] * 72 / dpi)
    solid = npm._solid_box_pt(a, dpi, dpi)
    assert not npm.content_inside_margins([solid], [size], size, (8.5,) * 4)


def test_a_page_of_text_only_has_no_solid_box():
    a, dpi = _page()
    a[_mm(1):_mm(1) + 6, :] = 0                                  # 0.5 mm, a hairline rule
    assert npm._solid_box_pt(a, dpi, dpi) is None


def test_the_dialog_route_judges_the_solid_box():
    import inspect
    src = inspect.getsource(npm.print_frames)
    assert "_solid_box_pt(rgb, dpi_x, dpi_y)" in src


# ---- 2. one Borderless row on a PictureMate -------------------------------------
_PM_LPOPTIONS = """EPIJ_PSrc/Page Setup: *2 3
EPIJ_Size/Paper Size: 74 76 *70
EPIJ_Medi/Media Type: *13 12
EPIJ_Qual/Print Quality: *305 306
EPIJ_Bdls/Borderless: *0 1
"""


@pytest.fixture()
def pm(monkeypatch):
    from workflow import print_manager as PMod
    monkeypatch.setattr(PMod, "CUPS_AVAILABLE", True)
    monkeypatch.setattr(PMod, "run_text", lambda cmd, **kw: subprocess.CompletedProcess(
        cmd, 0, _PM_LPOPTIONS, ""))
    monkeypatch.setattr(PMod.PrintModule, "_parse_ppd_labels", lambda self, p: {
        "EPIJ_PSrc": {"2": "Standard", "3": "Borderless"},
        "EPIJ_Bdls": {"0": "Off", "1": "On"}})
    m = PMod.PrintModule.__new__(PMod.PrintModule)
    m._borderless_state = {}
    return PMod, m


def test_a_picturemate_shows_one_borderless_row(pm):
    PMod, m = pm
    opts = m.query_options("PM")
    assert "EPIJ_Bdls" not in opts
    assert PMod._BORDERLESS_SYNTH in opts
    assert sum(1 for _k, (label, _v) in opts.items() if label == "Borderless") == 1


def test_the_borderless_row_sets_both_keys_of_the_picturemate(pm):
    PMod, m = pm
    m.query_options("PM")
    on = m._resolve_synthetic_options("PM", {PMod._BORDERLESS_SYNTH: "True"})
    assert on == {"EPIJ_PSrc": "3", "EPIJ_Bdls": "1"}
    off = m._resolve_synthetic_options("PM", {PMod._BORDERLESS_SYNTH: "False"})
    assert off == {"EPIJ_PSrc": "2", "EPIJ_Bdls": "0"}
    # left at "Printer Default": nothing is sent
    assert m._resolve_synthetic_options("PM", {PMod._BORDERLESS_SYNTH: ""}) == {}


# ---- 3. the quality note at "Printer Default" -----------------------------------
def test_the_quality_note_is_hidden_at_printer_default(qapp):
    from PyQt6.QtWidgets import QComboBox, QLabel
    from ui.tabs.tab_print import TabPrint
    from workflow import measurement_messages as MM

    class _Stub:
        pass
    stub = _Stub()
    quality = QComboBox()
    quality.addItem("Printer Default", "")
    quality.addItem("Photo", "305")
    stub._option_combos = {"EPIJ_Qual": quality}
    stub._quality_note = QLabel()
    from types import SimpleNamespace
    stub._quality_choices = SimpleNamespace(learned=None)   # the driver lists qualities
    TabPrint._update_quality_note(stub)
    assert stub._quality_note.isHidden()
    quality.setCurrentIndex(1)
    TabPrint._update_quality_note(stub)
    assert not stub._quality_note.isHidden()
    assert MM.M_PRINT_QUALITY.title in stub._quality_note.text()


# ---- 4. the paper size preselection keeps the rows after it ---------------------
def test_the_preselected_size_keeps_the_media_type_and_refreshes_quality(tmp_path):
    """Measured on screen (ET-8550 capture queue): Epson Ultra Glossy chosen,
    then an A3 chart loaded; the preselection set "A3" and the media and
    quality rows fell back to "Printer Default", so the job went out without
    the paper the user had chosen."""
    from types import SimpleNamespace
    import test_beta16_print_package as T
    from ui.tabs.tab_print import TabPrint
    ppd = tmp_path / "pm400.ppd"
    ppd.write_text(T.PM400_PPD, encoding="latin-1")
    size = T._Combo([("Printer Default", ""), ("10 x 15 cm (4 x 6 in)", "74"),
                     ("13 x 18 cm (5 x 7 in)", "76")], 0)
    media = T._Combo([("Printer Default", ""), ("Photo Paper Glossy", "13")], 1)
    real_set = size.setCurrentIndex

    def refill(i):                  # what _on_option_changed does to the rows after it
        real_set(i)
        media.setCurrentIndex(0)
    size.setCurrentIndex = refill
    refreshed = []
    from workflow import page_geometry as pg
    module = SimpleNamespace(
        get_page_size_points=lambda p, *c: next(
            (d for d in (pg.get_page_size_points(str(ppd), x) for x in c if x) if d), None),
        get_imageable_area_points=lambda p, *c: next(
            (d for d in (pg.get_imageable_area_points(str(ppd), x) for x in c if x) if d), None),
        _find_ppd_path=lambda p: str(ppd))
    stub = SimpleNamespace(_option_combos={"EPIJ_Size": size, "EPIJ_Medi": media},
                           _tiff_pages=[T._chart(tmp_path, 102, 152)],
                           _printer_combo=SimpleNamespace(currentData=lambda: "Q"),
                           _module=module, _restoring=False,
                           _refresh_quality_row=lambda keep_current: refreshed.append(keep_current))
    stub._ppd_default_page = lambda printer: TabPrint._ppd_default_page(stub, printer)
    TabPrint._preselect_paper_for_chart(stub)
    assert size.currentData() == "74"
    assert media.currentData() == "13", "the user's media type was dropped"
    assert refreshed == [True], "the quality row was not refreshed for the new size"


# ---- 5. an Epson job with its PageSize goes as the exact-size PDF -------------------
@pytest.mark.parametrize("opts, pdf_setting, want", [
    ({"EPIJ_Size": "1", "PageSize": "A4"}, False, ".pdf"),
    ({"EPIJ_Size": "1", "PageSize": "A4"}, True, ".pdf"),
    ({}, False, ".tif"),                                 # Printer Default: as beta 15
    ({"CNIJMediaType": "42", "PageSize": "A4"}, False, ".tif"),   # Canon: unchanged
])
def test_the_reference_job_is_sent_one_to_one(tmp_path, monkeypatch, opts, pdf_setting, want):
    """Measured on ET-8550, SC-P900, R3000 and XP-15000 capture queues: an A4
    chart on "A4" came out at 97 % as a TIFF once the job carried PageSize
    (beta 15: 100 %); the exact-size PDF places it 1:1."""
    from workflow import cups_printer as CP
    icc = tmp_path / "p.icc"
    icc.write_bytes(b"icc")
    sent = []
    monkeypatch.setattr(CP.CupsRawPrinter, "_run_lp_result",
                        lambda self, cmd: (sent.append(cmd) or (0, "")))
    monkeypatch.setattr(CP, "write_tagged_tiff", lambda src, dst, icc: dst.write_bytes(b"t"))
    monkeypatch.setattr(CP.PdfGenerator, "generate", lambda self, *a, **k: b"%PDF")
    pp = SimpleNamespace(icc_path=str(icc), option="X", value="1", label="L",
                         keys=lambda: {})
    monkeypatch.setattr(CP.CupsRawPrinter, "reference_options",
                        staticmethod(lambda cfg, p: dict(cfg.options)))
    pr = CP.CupsRawPrinter.__new__(CP.CupsRawPrinter)
    cfg = CP.PrintConfig(printer_name="Q", options=dict(opts))
    pr._print_job_reference(tmp_path / "c.tif", cfg, pp, None, 3, (595.2, 841.8), pdf_setting)
    assert sent and sent[0][-1].endswith(want)


# ---- 6. a default paper the chart only "matches" within the tolerance -------------
_LETTER_DEFAULT_PPD = """*PPD-Adobe: "4.3"
*OpenUI *PageSize/Page Size: PickOne
*DefaultPageSize: Letter
*PageSize Letter/US Letter: ""
*PageSize A4/A4: ""
*CloseUI: *PageSize
*OpenUI *EPIJ_Size/Paper Size: PickOne
*DefaultEPIJ_Size: 4
*EPIJ_Size 4/US Letter: ""
*EPIJ_Size 1/A4: ""
*CloseUI: *EPIJ_Size
*PaperDimension Letter/US Letter: "612.00 792.00"
*PaperDimension A4/A4: "595.20 841.80"
*ImageableArea Letter/US Letter: "9.00 9.00 603.00 783.00"
*ImageableArea A4/A4: "9.00 9.00 586.20 832.80"
"""


def _letter_stub(tmp_path, chart_mm, current=0):
    import test_beta16_print_package as T
    from ui.tabs.tab_print import TabPrint
    from workflow import page_geometry as pg
    ppd = tmp_path / "r3000.ppd"
    ppd.write_text(_LETTER_DEFAULT_PPD, encoding="latin-1")
    size = T._Combo([("Printer Default", ""), ("US Letter", "4"), ("A4", "1")], current)
    module = SimpleNamespace(
        get_page_size_points=lambda p, *c: next(
            (d for d in (pg.get_page_size_points(str(ppd), x) for x in c if x) if d), None),
        get_imageable_area_points=lambda p, *c: next(
            (d for d in (pg.get_imageable_area_points(str(ppd), x) for x in c if x) if d), None),
        _find_ppd_path=lambda p: str(ppd))
    stub = SimpleNamespace(_option_combos={"EPIJ_Size": size},
                           _tiff_pages=[T._chart(tmp_path, *chart_mm)],
                           _printer_combo=SimpleNamespace(currentData=lambda: "Q"),
                           _module=module, _restoring=False,
                           _refresh_quality_row=lambda keep_current: None)
    stub._ppd_default_page = lambda printer: TabPrint._ppd_default_page(stub, printer)
    TabPrint._preselect_paper_for_chart(stub)
    return size.currentData()


def test_an_a4_chart_on_a_letter_default_gets_a4(tmp_path):
    """Measured on the R3000 capture queue: an A4 chart at "Printer Default"
    went onto US Letter at 95 % (beta 15 and the package alike), because
    the mismatch check forgives 8 %."""
    assert _letter_stub(tmp_path, (210, 297)) == "1"


def test_a_letter_chart_on_a_letter_default_stays(tmp_path):
    assert _letter_stub(tmp_path, (216, 279)) == ""


def test_a_chosen_letter_stays_for_an_a4_chart(tmp_path):
    assert _letter_stub(tmp_path, (210, 297), current=1) == "4"
