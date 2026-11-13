"""THE i1iO TABLE BETA WITH THE OPTION ON: the Preferences row and its
consent window, the Guided entry, the Measure tab's notice, and what the
Beta keeps out of the rest of Create Chart (Basti, 2026-11-13).
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(autouse=True)
def i1io_on():
    from workflow.i1io import support
    before = support._latched
    support.set_enabled_for_this_process(True)
    try:
        yield
    finally:
        support._latched = before


def _chart(tmp_path, name="X-Rite i1iO"):
    ti2 = tmp_path / "iochart.ti2"
    ti2.write_text(
        "CTI2\n\n"
        'DESCRIPTOR "Argyll Calibration Target chart information 2"\n'
        f'TARGET_INSTRUMENT "{name}"\nCOLOR_REP "RGB"\n'
        "NUMBER_OF_FIELDS 8\nBEGIN_DATA_FORMAT\n"
        "SAMPLE_ID SAMPLE_LOC RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z\n"
        "END_DATA_FORMAT\nNUMBER_OF_SETS 1\nBEGIN_DATA\n"
        '1 "A1" 100 100 100 95 100 108\nEND_DATA\n', encoding="utf-8")
    ti2.with_suffix(".ti1").write_text(ti2.read_text(encoding="utf-8")
                                       .replace("CTI2", "CTI1", 1),
                                       encoding="utf-8")
    return ti2


@pytest.fixture
def measure_tab(qapp, tmp_path):
    from PyQt6.QtCore import QSettings
    from core.argyll_runner import ArgyllRunner
    from core.settings import AppSettings
    from ui.tabs.tab_measure import TabMeasure
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "app.ini"), QSettings.Format.IniFormat)
    s.set("custom_output_path", str(tmp_path / "out"))
    t = TabMeasure(ArgyllRunner(s), s)
    yield t
    t.close()
    t.deleteLater()


def test_start_on_an_i1io_chart_says_it_cannot_measure_yet_and_starts_nothing(
        measure_tab, tmp_path, monkeypatch):
    """Before anything is recovered, armed or written: the very top of
    Start, and only the window and a log line."""
    tab = measure_tab
    shown = []
    monkeypatch.setattr(tab, "_i1io_not_yet_window",
                        lambda: shown.append("M-I1IO-NOT-YET"))
    tab.set_ti1_path(_chart(tmp_path).with_suffix(".ti1"))
    monkeypatch.setattr(tab, "_recover_engine_autosave", lambda: pytest.fail(
        "Start went past the i1iO notice"))
    tab._on_start()
    assert shown == ["M-I1IO-NOT-YET"]
    assert "not available in this version" in tab._log.toPlainText()


def test_an_ordinary_chart_is_not_taken_for_an_i1io_one(measure_tab, tmp_path):
    tab = measure_tab
    tab.set_ti1_path(_chart(tmp_path, "GretagMacbeth i1 Pro")
                     .with_suffix(".ti1"))
    assert tab._refused_as_an_i1io_chart() is False


def test_the_notice_names_the_route_that_works_today():
    from workflow import measurement_messages as M
    title, body = M.M_I1IO_NOT_YET.render()
    assert "not available yet" in title
    for part in ("exports", "Convert i1Profiler → TI3", "3.8.6", ".mxf",
                 "print the chart again"):
        assert part in body
    assert "—" not in title + body
    assert M.M_I1IO_NOT_YET.approved is False
    assert M.M_I1IO_SUPPORT_OFF.approved is False


def test_preferences_has_the_row_and_switching_on_asks_first(qapp, tmp_path,
                                                             monkeypatch):
    from PyQt6.QtCore import QSettings
    from PyQt6.QtWidgets import QMessageBox
    from core.settings import AppSettings
    from ui.dialogs.settings_dialog import SettingsDialog
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "app.ini"), QSettings.Format.IniFormat)
    dlg = SettingsDialog(s)
    try:
        box = dlg._i1io_support_check
        assert box.text() == "X-Rite i1iO support (beta)"
        asked = []

        def answer(result):
            def _exec(self):
                asked.append(self.text())
                return result
            return _exec

        # Cancel (the default) leaves it off.
        monkeypatch.setattr(QMessageBox, "exec",
                            answer(QMessageBox.StandardButton.Cancel))
        box.click()
        assert not box.isChecked() and len(asked) == 1
        assert "own risk" in asked[0]
        # Confirm turns it on.
        monkeypatch.setattr(QMessageBox, "exec",
                            answer(QMessageBox.StandardButton.Ok))
        box.click()
        assert box.isChecked() and len(asked) == 2
        # Switching off asks nothing; switching on again asks again.
        box.click()
        assert not box.isChecked() and len(asked) == 2
        box.click()
        assert box.isChecked() and len(asked) == 3
    finally:
        dlg.deleteLater()


def test_the_help_and_the_consent_say_what_this_step_is():
    from ui.dialogs.settings_dialog import i1io_consent_text, i1io_support_help
    for text in (i1io_support_help(), i1io_consent_text()):
        assert "sends nothing at all to a table" in text
        assert "i1iO 2 with an i1Pro 2" in text
        assert "—" not in text
    assert "3.8.7" in i1io_support_help()
    assert "GitHub" in i1io_support_help()


@pytest.fixture
def chart_tab(qapp, tmp_path):
    from PyQt6.QtCore import QSettings
    from core.argyll_runner import ArgyllRunner
    from core.settings import AppSettings
    from core.file_manager import FileManager
    from ui.tabs.tab_chart import TabChart
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "app.ini"), QSettings.Format.IniFormat)
    s.set("custom_output_path", str(tmp_path / "out"))
    t = TabChart(ArgyllRunner(s), FileManager(s), s)
    yield t
    t.close()
    t.deleteLater()


def test_guided_offers_the_i1io_with_its_own_sheets_only(chart_tab):
    tab = chart_tab
    i = tab._instr_combo.findData("IO2")
    assert i >= 0 and tab._instr_combo.itemText(i) == "i1iO 2 + i1Pro 2"
    tab._instr_combo.setCurrentIndex(i)
    papers = [tab._paper_combo.itemData(k)
              for k in range(tab._paper_combo.count())]
    # every sheet inside the table's reach, A4 and Letter first (review 5,
    # item 7)
    from workflow.i1io.chart import GUIDED_PAPERS
    assert papers == list(GUIDED_PAPERS) and papers[:2] == ["A4", "Letter"]
    p = tab._collect_guided()
    assert (p.instrument, p.paper) == ("IO2", "A4")
    # the engine's own count for that sheet
    assert tab._creator._engine_total_patches(p) == 528


def test_manual_offers_the_i1io_and_greys_what_it_does_not_read(chart_tab):
    """Manual: the i1iO in the -i list and in the layout panel; choosing it
    greys every control the i1iO layout does not read (each with the
    reason), keeps the patch size, the labels, the sheet text, the
    resolution, the paper and the pages live, and holds the patch size inside
    the table's limits. Leaving it gives everything back."""
    from ui.dialogs.layout_options_panel import i1io_greyed_reason
    tab = chart_tab
    params = tab._load_yaml_params()
    i = next(p for p in params["printtarg"] if p["flag"] == "-i")
    assert "IO2" in i["choices"] and "i1iO 2 + i1Pro 2" in i["tooltip_body"]
    tab._init_manual_layout_panel()
    panel = tab._manual_layout_panel
    k = panel.instr.findData("IO2")
    assert k >= 0
    before = {id(c): c.isEnabled() for c in panel._i1io_greyable_controls()}
    panel.instr.setCurrentIndex(k)
    greyed = list(panel._i1io_greyable_controls())
    assert greyed and all(not c.isEnabled() for c in greyed)
    assert all(c.toolTip() == panel._i1io_reason_for(c) for c in greyed)
    assert all(c.toolTip().endswith(i1io_greyed_reason()) for c in greyed)
    clip_content = set(panel._i1io_clip_controls()) - {panel.clip_enable}
    for c in panel._i1io_live_controls():
        if c in panel._spacer_swatches:
            continue           # live, and enabled by "Custom spacer colours"
        if c in clip_content:
            continue           # live, and enabled by "Clip border" On
        if c in (panel.ind_italic, panel.ct_italic, panel.ind_bold,
                 panel.ct_bold):
            # live, and enabled exactly where the typeface has that style
            from workflow.layout_engine.raster import font_supports
            combo = (panel.indicator_font
                     if c in (panel.ind_bold, panel.ind_italic)
                     else panel.chart_text_font)
            has_bold, has_italic = font_supports(combo.currentData() or "")
            want = has_bold if c in (panel.ind_bold, panel.ct_bold) \
                else has_italic
            assert c.isEnabled() == want, (c.text(), combo.currentData())
            continue
        if c in (panel.underline_thickness, panel.underline_gap):
            continue           # live, enabled by an underline
        if c in (panel.helper_marker_edge, panel.helper_marker_len,
                 panel.helper_marker_per_patch,
                 panel.helper_markers_top_bottom,
                 panel.helper_markers_sides, panel.max_strip):
            continue           # live, enabled by their own switch
        assert c.isEnabled(), c.objectName() or type(c).__name__
    panel.custom_spacer_cb.setChecked(True)
    assert all(b.isEnabled() for b in panel._spacer_swatches)
    panel.custom_spacer_cb.setChecked(False)
    assert [panel.paper.itemData(j) for j in range(panel.paper.count())][:2] \
        == ["A4", "Letter"]
    # width across a strip, height along it (the scan)
    assert (panel.patch_y.minimum(), panel.patch_y.maximum()) == (8.9, 20.0)
    assert (panel.patch_x.minimum(), panel.patch_x.maximum()) == (7.0, 20.0)
    assert (panel.patch_x.value(), panel.patch_y.value()) == (8.0, 10.0)
    assert panel.spacer_mode.currentData() == "colored"
    assert panel.spacer_mode.isEnabled()
    panel.patch_y.setValue(12.0)
    r = panel.get_recipe()
    assert r.instrument == "IO2" and r.patch_h_mm == 12.0
    from workflow.layout_engine import instruments
    g = instruments.geom_from_build_kwargs(r.build_kwargs())
    assert g.plen == 12.0 and g.pspa == 1.0
    panel.instr.setCurrentIndex(panel.instr.findData("i1"))
    after = {id(c): c.isEnabled() for c in panel._i1io_greyable_controls()}
    assert after == before


def test_the_editor_reads_an_i1io_chart_as_one():
    from workflow.ti2_relayout import instrument_to_flag
    assert instrument_to_flag("X-Rite i1iO") == "IO2"
    assert instrument_to_flag("i1iO 2") == "i1"    # i1Profiler's own name


def test_other_charts_get_no_keyword_declarations(tmp_path):
    """The writer declares only ChromIQ's own keywords: a SpectroScan
    honeycomb's HEXAGON_PATCHES is written exactly as before."""
    from tests.test_i1io_chart import _ti1
    from workflow.layout_engine import chart
    r = chart.build_chart(_ti1(tmp_path / "s.ti1", 30), tmp_path / "s",
                          instrument="SS", paper="A4", dpi=100, hflag=True)
    text = r.ti2_path.read_text(encoding="utf-8")
    assert 'HEXAGON_PATCHES "True"' in text and "KEYWORD" not in text


def test_the_i1io_style_boxes_follow_the_typeface(chart_tab):
    """Review F6: Bold and Italic are live for the i1iO wherever the chosen
    typeface has the style, for the labels and for the sheet text."""
    from workflow.layout_engine.raster import font_supports
    tab = chart_tab
    tab._init_manual_layout_panel()
    panel = tab._manual_layout_panel
    panel.instr.setCurrentIndex(panel.instr.findData("IO2"))
    for face in ("JetBrains Mono", "Inter", "Instrument Serif"):
        for combo, bold, italic in (
                (panel.indicator_font, panel.ind_bold, panel.ind_italic),
                (panel.chart_text_font, panel.ct_bold, panel.ct_italic)):
            combo.setCurrentIndex(combo.findData(face))
            has_bold, has_italic = font_supports(face)
            assert bold.isEnabled() == has_bold, (face, bold.text())
            assert italic.isEnabled() == has_italic, (face, italic.text())
