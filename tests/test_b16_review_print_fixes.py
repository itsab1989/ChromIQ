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
