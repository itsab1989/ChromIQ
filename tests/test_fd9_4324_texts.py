"""4.3.24, review of #214 (M6, L3): the FD-9's texts describe it, credit its
author, say where its controls are, and use the app's own names.
"""
from tests._fd9_beta import fd9_beta_on, fd9_windows  # noqa: F401

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


def test_the_instrument_bullet_describes_the_fd9_and_credits_lessbones():
    from ui.tabs.tab_chart import fd9_instrument_bullet
    text = fd9_instrument_bullet()
    assert text.startswith("  •  FD-9 (Konica Minolta)")
    for words in ("automatic chart reader", "lessbones", "several numbered "
                  "sheets", "6 to 30 mm", "arrow"):
        assert words in text, words


def test_the_panel_note_says_where_the_controls_are():
    from ui.dialogs.fd9_sheet import fd9_layout_note
    text = fd9_layout_note()
    for words in ("“Expert Options”", "“Patches & spacers”", "“Patch size”",
                  "“Inter-patch gap”", "“Strip gap”", "between the rows",
                  "between the columns", "Preferences > Chart Layout"):
        assert words in text, words


def test_the_greyed_tooltip_explains_the_fixed_layout():
    from ui.dialogs.layout_options_panel import fd9_greyed_reason
    text = fd9_greyed_reason().lower()
    for words in ("15 mm", "42 mm", "33 mm", "four small black squares",
                  "page number", "“expert options”"):
        assert words in text, words


def test_the_beta_tooltip_is_complete_again():
    src = (ROOT / "ui" / "dialogs" / "settings_dialog.py").read_text(
        encoding="utf-8")
    start = src.index("Konica Minolta FD-9 support (PR #213")
    block = src[start:start + 9000]
    for words in ("written and contributed by lessbones",
                  "What turning this on adds",
                  "not the FD-9's own firmware version",
                  "The limits of this version",
                  "compares the readings with the colours"):
        assert words in block, words
    for jargon in ("refused before motion", "needs hardware validation"):
        assert jargon not in block


@pytest.mark.parametrize("code,name,wrong", [
    ("de", "Chart erstellen", "Diagramm erstellen"),
    ("fr", "Créer la mire", "Créer une charte")])
def test_german_and_french_use_the_apps_name_for_create_chart(code, name,
                                                              wrong):
    cat = json.loads((ROOT / "data" / "i18n" / f"{code}.json").read_text(
        encoding="utf-8"))
    assert cat["Create Chart"] == name
    fd9 = [v for k, v in cat.items() if "FD-9" in k]
    assert fd9 and not any(wrong in v for v in fd9)


def test_guided_info_line_states_the_fd9s_patches_and_gaps(qapp, qtbot,
                                                           tmp_path):
    from PyQt6.QtCore import QSettings
    from core.argyll_runner import ArgyllRunner
    from core.file_manager import FileManager
    from core.settings import AppSettings
    from ui.tabs.tab_chart import TabChart
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "i.ini"), QSettings.Format.IniFormat)
    s.set("custom_output_path", str(tmp_path / "p"))
    tab = TabChart(ArgyllRunner(s), FileManager(s), s)
    qtbot.addWidget(tab)
    line = tab._engine_info_line("FD9", "A4", 300, dd=False, td=False,
                                 eff_lb=False, nsl=False, pscale=1.0,
                                 margin=6)
    assert "8 × 8 mm" in line and "1 mm gap between the rows" in line
    assert "margin" not in line


def test_the_greyed_strip_recognition_says_what_the_fd9_does(tab):
    combos = [c for c in (getattr(tab, "_bidir_combo", None),
                          getattr(tab, "_m_bidir_combo", None)) if c]
    assert combos
    before = [c.toolTip() for c in combos]
    tab._fd9_explain_reading_direction(True)
    assert all("both directions" in c.toolTip() for c in combos)
    tab._fd9_explain_reading_direction(True)          # idempotent
    tab._fd9_explain_reading_direction(False)
    assert [c.toolTip() for c in combos] == before


from tests.test_fd9_normal_measurement import tab  # noqa: E402,F401
