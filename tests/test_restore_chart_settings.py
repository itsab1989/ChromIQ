"""Loading a chart restores the settings it was made with (#mavtop, forum):
an engine chart's ``channels.json`` carries its full layout recipe, so the
Create-Chart panels can show the chart's own patch size, spacers, margins,
seed, notes and patch count instead of stale defaults."""
import json

import pytest

pytest.importorskip("PyQt6")
from PyQt6.QtCore import QSettings  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

from core.argyll_runner import ArgyllRunner  # noqa: E402
from core.file_manager import FileManager  # noqa: E402
from core.settings import AppSettings  # noqa: E402
from ui.tabs.tab_chart import TabChart  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _tab(tmp_path, **prefs):
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "t.ini"), QSettings.Format.IniFormat)
    # These tests exercise the printtarg path explicitly — since 4.0.0
    # the ChromIQ layout engine is the Manual default (schema 18), so
    # the mode under test is pinned rather than inherited.
    s.set("use_chromiq_layout_engine", False)
    s.set("custom_output_path", str(tmp_path / "out"))
    for k, v in prefs.items():
        s.set(k, v)
    return TabChart(ArgyllRunner(s), FileManager(s), s)


def _fake_chart(tmp_path, with_recipe=True, sidecar_extra=None):
    ti2 = tmp_path / "c.ti2"
    ti2.write_text("CTI2\nNUMBER_OF_SETS 546\nBEGIN_DATA\nEND_DATA\n")
    doc = {}
    if with_recipe:
        recipe = {
            "instrument": "CM", "paper": "A3", "dpi": 360,
            "randomize": True, "seed": 142,
            "use_instrument_margins": False,
            "spacer_on": True, "spacer_mode": "bw",
            "margin_top": 12.0, "margin_right": 11.0,
            "margin_bottom": 10.0, "margin_left": 9.0,
            "patch_w_mm": 8.3, "patch_h_mm": 9.5,
            "chart_text": "Epson XP-15000 / Ferrania Optijet",
        }
        patches = [{"loc": "A1", "page": 0, "x": 0, "y": 0, "w": 10, "h": 10},
                   {"loc": "A2", "page": 1, "x": 0, "y": 0, "w": 10, "h": 10}]
        doc["layout"] = {"engine": "chromiq", "recipe": recipe,
                         "patches": patches}
    if sidecar_extra:
        doc.update(sidecar_extra)
    if doc:
        (tmp_path / "c.channels.json").write_text(json.dumps(doc))
    return ti2


def _targen_count(tab):
    for pw in tab._manual_widgets.get("targen", []):
        if pw.flag == "-f":
            return int(pw.get_raw_value())
    return None


def test_engine_chart_restores_everything(qapp, tmp_path):
    tab = _tab(tmp_path)
    tab._manual_btn.setChecked(True)
    ti2 = _fake_chart(tmp_path, with_recipe=True)
    assert tab._restore_chart_settings(ti2) is True
    # Engine came on and the panel took the chart's recipe.
    assert tab._manual_engine_check.isChecked()
    p = tab._manual_layout_panel
    r = tab._current_layout_recipe()
    assert r.instrument == "CM" and r.paper == "A3"
    assert r.seed == 142 and r.randomize is True
    assert (r.margin_top, r.margin_right, r.margin_bottom, r.margin_left) \
        == (12.0, 11.0, 10.0, 9.0)
    assert abs(r.patch_w_mm - 8.3) < 1e-9 and abs(r.patch_h_mm - 9.5) < 1e-9
    # Notes, pages and the pinned patch count follow the chart.
    assert tab._manual_chart_notes_edit.text() == \
        "Epson XP-15000 / Ferrania Optijet"
    assert tab._manual_pages_spin.value() == 2
    assert _targen_count(tab) == 546
    assert not tab._manual_auto_patches_check.isChecked()
    tab.deleteLater()


def test_printtarg_chart_restores_count_only(qapp, tmp_path):
    tab = _tab(tmp_path)
    tab._manual_btn.setChecked(True)
    engine_before = tab._manual_engine_check.isChecked()
    ti2 = _fake_chart(tmp_path, with_recipe=False)
    assert tab._restore_chart_settings(ti2) is False   # no recipe to restore
    assert tab._manual_engine_check.isChecked() == engine_before
    assert _targen_count(tab) == 546                   # count still recovered
    tab.deleteLater()


def test_notes_and_stamp_survive_the_engine_toggle(qapp, tmp_path):
    """The stamp checkbox resets to its mode default whenever the engine
    toggle flips (unchecked for engine mode) — a restored value must land
    AFTER that flip, or it silently disappears (mavtop, forum)."""
    tab = _tab(tmp_path)
    tab._manual_btn.setChecked(True)
    ti2 = _fake_chart(tmp_path, with_recipe=True,
                      sidecar_extra={"chart_notes": "",
                                     "stamp_commands": True})
    assert tab._restore_chart_settings(ti2) is True
    assert tab._manual_engine_check.isChecked()
    # True survived although the engine flip defaults the box to unchecked.
    assert tab._manual_stamp_cmd_check.isChecked() is True
    # The recorded (empty) notes win over the recipe's on-sheet text.
    assert tab._manual_chart_notes_edit.text() == ""
    assert tab._restored_notes_stamp is True
    tab.deleteLater()


def test_printtarg_chart_restores_notes_and_stamp(qapp, tmp_path):
    """printtarg charts have no recipe, but their sidecar still carries the
    notes + stamp choice — those restore even when the function returns
    False (count-only layout restore)."""
    tab = _tab(tmp_path)
    tab._manual_btn.setChecked(True)
    engine_before = tab._manual_engine_check.isChecked()
    ti2 = _fake_chart(tmp_path, with_recipe=False,
                      sidecar_extra={"ink_channels": ["R", "G", "B"],
                                     "chart_notes":
                                         "Canon Pro-1000 / Photo Rag 308",
                                     "stamp_commands": False})
    assert tab._restore_chart_settings(ti2) is False
    assert tab._manual_engine_check.isChecked() == engine_before
    assert tab._manual_chart_notes_edit.text() == \
        "Canon Pro-1000 / Photo Rag 308"
    assert tab._manual_stamp_cmd_check.isChecked() is False
    assert tab._restored_notes_stamp is True
    tab.deleteLater()


def test_old_sidecar_leaves_notes_and_stamp_untouched(qapp, tmp_path):
    """Charts saved before the chart_notes / stamp_commands keys existed
    keep both fields exactly as they are (backward compatibility)."""
    tab = _tab(tmp_path)
    tab._manual_btn.setChecked(True)
    tab._manual_chart_notes_edit.setText("keep me")
    tab._manual_stamp_cmd_check.setChecked(False)
    ti2 = _fake_chart(tmp_path, with_recipe=False,
                      sidecar_extra={"ink_channels": ["R", "G", "B"]})
    assert tab._restore_chart_settings(ti2) is False
    assert tab._manual_chart_notes_edit.text() == "keep me"
    assert tab._manual_stamp_cmd_check.isChecked() is False
    assert tab._restored_notes_stamp is False
    tab.deleteLater()


def test_channel_sidecar_records_notes_and_stamp(tmp_path):
    """_write_channel_sidecar persists the two fields for every chart kind."""
    from workflow.chart_creator import ChartCreator, ChartParams

    class _S:
        def get(self, key, default=None):
            return default

    cc = ChartCreator(None, None, _S())
    p = ChartParams(chart_notes="Epson / Optijet", stamp_commands=False)
    cc._write_channel_sidecar(tmp_path, "c", p)
    doc = json.loads((tmp_path / "c.channels.json").read_text())
    assert doc["chart_notes"] == "Epson / Optijet"
    assert doc["stamp_commands"] is False
    assert "ink_channels" in doc                       # original payload kept
