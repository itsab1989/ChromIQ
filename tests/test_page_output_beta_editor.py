"""THE PATCH SET EDITOR AND A PAGE TYPED IN PIXELS (#215, review F2).

The patch set editor ("Edit / create chart patch set") builds Create Chart's
layout panel HIDDEN, and still renders the chart hidden at 150 dpi
(`Ti2RelayoutDialog._do_engine_preview`): that render feeds the Pages box and
its "Filled to {p} pages" top-up, the patch counts and the page flipping. With
the page-output Beta a chart's page can be a pixel count (4096 x 2730 at 2731
ppi). Kept beside the forced 150 dpi, that count laid out a page of 4096 px at
150 dpi: 693.6 x 462.3 mm with 6144 patch slots instead of the 38.1 x 25.4 mm
frame. Pinned here:

(a) what reads the hidden render (its page count, its patch count, the
    capacity the Pages top-up uses) is the TRUE page's;
(b) the hidden render is a small 150 dpi picture of the true millimetre page,
    never the typed pixel count;
(c) what the editor saves for Create Chart keeps `page_size` and
    `tiff_res_unit` unchanged, and the saved chart is pixel-exact.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QSettings                            # noqa: E402
from PyQt6.QtWidgets import QApplication                      # noqa: E402

from workflow.page_output import support as po               # noqa: E402

FRAME_4K = {"w": [4096, "px"], "h": [2730, "px"], "ppi": 2731}


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def beta_on():
    before = po._latched
    po.set_enabled_for_this_process(True)
    try:
        yield
    finally:
        po._latched = before


def _recipe() -> dict:
    from dataclasses import replace
    from workflow.layout_engine.presets import default_recipe
    w, h = po.page_mm(FRAME_4K, 2731)
    r = replace(default_recipe("SS", po.paper_code(w, h)), dpi=2731,
                page_size=FRAME_4K, tiff_res_unit="in", compression="none",
                seed=7, patch_w_mm=4.0, patch_h_mm=4.0, margin_top=1.0,
                margin_right=1.0, margin_bottom=1.0, margin_left=1.0,
                show_strip_indicators=False, show_row_indicators=False,
                spacer_mode="none", spacer_on=False,
                use_instrument_margins=False, chart_text="",
                stamp_command=False, clip_content_mode="off",
                layout_mode="patch_first")
    return r.to_dict()


def _chart(tmp_path: Path, n: int = 12) -> Path:
    rows = "\n".join(
        f'{i} "A{i}" {(i * 37) % 101}.0 {(i * 53) % 101}.0 {(i * 71) % 101}.0 '
        f"50.0 50.0 50.0" for i in range(1, n + 1))
    ti2 = tmp_path / "chart.ti2"
    ti2.write_text(f'''CTI2

ORIGINATOR "test"
TARGET_INSTRUMENT "SpectroScan"
COLOR_REP "iRGB"
PAPER_SIZE "38.1x25.4"
APPROX_WHITE_POINT "95.1 100.0 108.8"

NUMBER_OF_FIELDS 8
BEGIN_DATA_FORMAT
SAMPLE_ID SAMPLE_LOC RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z
END_DATA_FORMAT

NUMBER_OF_SETS {n}
BEGIN_DATA
{rows}
END_DATA
''', encoding="utf-8")
    (tmp_path / "chart.channels.json").write_text(json.dumps({
        "layout": {"engine": "chromiq", "seed": 7, "recipe": _recipe()},
    }), encoding="utf-8")
    return ti2


@pytest.fixture
def editor(qapp, beta_on, tmp_path, monkeypatch):
    import ui.dialogs.ti2_relayout_dialog as M
    from core.argyll_runner import ArgyllRunner
    from core.settings import AppSettings
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "app.ini"), QSettings.Format.IniFormat)
    s.set("use_chromiq_layout_engine", True)
    ed = M.Ti2RelayoutDialog(ArgyllRunner(s), s)
    monkeypatch.setattr(ed, "_regenerate", lambda **k: None)
    src = tmp_path / "src"
    src.mkdir()
    assert ed._load_chart_from(_chart(src)) is True
    assert ed._engine_active() is True
    yield ed
    ed.deleteLater()


def test_the_hidden_panel_holds_the_pixel_page(editor):
    r = editor._engine_panel.get_recipe()
    assert r.page_size == FRAME_4K and r.tiff_res_unit == "in"
    assert r.dpi == 2731 and r.paper == "38.0953x25.3907"


def test_b_the_hidden_render_is_the_true_page_at_150_dpi(editor, monkeypatch):
    from workflow.layout_engine import chart as le_chart
    seen = {}
    real = le_chart.build_chart

    def spy(ti1, out, **kw):
        seen.update(kw)
        res = real(ti1, out, **kw)
        seen["result"] = res
        return res
    monkeypatch.setattr(le_chart, "build_chart", spy)
    editor._do_engine_preview()
    assert "page_size" not in seen and "tiff_res_unit" not in seen
    assert seen["dpi"] == 150
    import tifffile
    tiffs = editor._engine_tiffs
    assert tiffs
    for p in tiffs:
        with tifffile.TiffFile(str(p)) as t:
            pg = t.pages[0]
            # 38.0953 x 25.3907 mm at 150 dpi: 225 x 150 px, not 4096 x 2730
            assert (pg.imagewidth, pg.imagelength) == (
                po.pixels_of(38.0953, 150), po.pixels_of(25.3907, 150))


def test_a_what_reads_the_hidden_render_counts_the_true_page(editor,
                                                            monkeypatch):
    from workflow.layout_engine import chart as le_chart, geometry
    from workflow.layout_engine.chart import build_from_recipe  # noqa: F401
    results = []
    real = le_chart.build_chart
    monkeypatch.setattr(le_chart, "build_chart",
                        lambda *a, **k: results.append(real(*a, **k))
                        or results[-1])
    editor._do_engine_preview()
    lay = results[-1].layout
    # the true page's capacity, as the Pages top-up computes it
    recipe = editor._engine_panel.get_recipe()
    geom, w_mm, h_mm = editor._engine_geom_from_recipe(recipe)
    assert (w_mm, h_mm) == pytest.approx((38.0953, 25.3907))
    cap = geometry.patches_per_sheet(geom, w_mm, h_mm)
    assert editor._engine_cap_per_page() == cap
    assert cap < 100, cap            # 693 x 462 mm held 6144
    assert lay.patches_per_page == cap
    assert len(editor._engine_tiffs) == lay.pages
    assert editor._engine_panel.pages is None or \
        editor._engine_panel.pages.value() == lay.pages
    # the status line counts the true layout
    assert str(lay.total_patches) in editor._status.text()
    # "Filled to {p} pages": two pages of the true capacity
    before = editor._grid.count()
    editor._on_engine_pages_changed(2)
    assert editor._grid.count() >= 2 * cap - 2 or \
        editor._grid.count() == max(before, 2 * cap)


def test_c_the_saved_chart_keeps_its_page_and_is_pixel_exact(editor,
                                                            tmp_path):
    from workflow.layout_engine.presets import LayoutRecipe
    out = tmp_path / "saved"
    out.mkdir()
    editor._write_engine_chart_into(out, "film")
    doc = json.loads((out / "film.channels.json").read_text(encoding="utf-8"))
    back = LayoutRecipe.from_dict(doc["layout"]["recipe"])
    assert back.page_size == FRAME_4K and back.tiff_res_unit == "in"
    assert back.dpi == 2731 and back.paper == "38.0953x25.3907"
    import tifffile
    pages = sorted(out.glob("film*.tif"))
    assert pages
    for p in pages:
        with tifffile.TiffFile(str(p)) as t:
            pg = t.pages[0]
            assert (pg.imagewidth, pg.imagelength) == (4096, 2730)
            assert tuple(pg.tags["XResolution"].value) == (2731, 1)
            assert int(pg.tags["ResolutionUnit"].value) == 2


def test_d_the_status_line_names_the_true_page(editor):
    """Re-review: the status line said "on 38.1x25.4" for a page typed as
    4096 x 2730 pixels at 2731; it says the pixels and the resolution."""
    editor._readout_instrument = "SpectroScan"
    editor._refresh_info()
    text = editor._info.text()
    assert "4096 x 2730 pixels at 2731 pixels per inch" in text, text
    assert "38.1x25.4" not in text


def test_e_a_page_that_cannot_be_made_is_not_drawn_hidden(editor,
                                                          monkeypatch):
    """Leftover b of 4.3.43: a side typed in pixels that makes more than
    2000 mm at the chart's resolution is refused by Generate and the build;
    the hidden 150 dpi render used to lay it out anyway (metres of page,
    drawn and thrown away). It is not drawn, and the status line says why."""
    from dataclasses import replace
    from workflow.layout_engine import chart as le_chart
    calls = []
    monkeypatch.setattr(le_chart, "build_chart",
                        lambda *a, **k: calls.append(k))
    panel = editor._engine_panel
    big = {"w": [18001, "px"], "h": [15001, "px"], "ppi": 72}
    w, h = po.page_mm(big, 72)
    r = replace(panel.get_recipe(), dpi=72, page_size=big,
                paper=po.paper_code(w, h))
    panel.set_recipe(r)
    assert po.size_problem(panel.get_recipe().page_size, 72)
    editor._do_engine_preview()
    assert calls == []
    assert "between 229 and 6000" in editor._status.text()
    # a page that fits is drawn as before
    panel.set_recipe(replace(r, dpi=2032,
                             paper=po.paper_code(*po.page_mm(big, 2032))))
    editor._do_engine_preview()
    assert len(calls) == 1


def test_f_the_editor_has_no_units_choice(editor):
    """The Units choice is Create Chart's own: the editor's hidden copy of
    the panel keeps 4.3.43's three rows and plain boxes."""
    from ui.dialogs.length_units import LengthSpinBox
    panel = editor._engine_panel
    assert not hasattr(panel, "units") and panel._units_choice is False
    assert not panel.findChildren(LengthSpinBox)
    assert set(panel._page_in) == {"w", "h"}
