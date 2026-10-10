"""Review of beta 17 (#182): what the independent review found and fixed.

1. Every number box of Preferences ▸ Measurement's misread table says which
   parameter and which chart type it is (VoiceOver read a bare "95,0 ΔE*ab";
   the strip-test boxes already said so).
2. The new texts of the table, its help, the cards and the presets window use
   each catalogue's OWN word for "chart". Six catalogues brought in a second
   word with beta 17 (Italian "target" for "grafico", Norwegian "testark" for
   "kart", Polish "wzornik" for "wzorzec", Russian "шкала" for "мишень",
   Swedish "testark" for "diagram", Ukrainian "шкала" for "діаграма"), so the
   Preferences column said one thing and "Create Chart" another.
3. Ukrainian "понад межею" (spatially above) is "понад межу" (more than).
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from PyQt6.QtCore import QSettings
from PyQt6.QtWidgets import QAbstractSpinBox

ROOT = Path(__file__).resolve().parents[1]


def _dialog(tmp_path):
    from core.settings import AppSettings
    from ui.dialogs.settings_dialog import SettingsDialog
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    return SettingsDialog(s, None)


def test_every_number_box_of_the_table_names_its_parameter_and_column(
        qapp, tmp_path):
    from ui.dialogs import settings_dialog as sd
    dlg = _dialog(tmp_path)
    spins = dlg._misread_table.findChildren(QAbstractSpinBox)
    assert len(spins) == 13          # 4 + 4 + 4 + the merged tolerance
    names = {sp.accessibleName() for sp in spins}
    assert "" not in names and len(names) == 13
    assert (f"{sd.PATCH_ERROR_LIMIT_NAME}, {sd.KIND_VERIFICATION_NAME}"
            in names)
    assert f"{sd.NEIGHBOUR_RADIUS_NAME}, {sd.KIND_CALIBRATION_NAME}" in names
    assert (f"{sd.SAME_READING_NAME}, {sd.SAME_FOR_ALL_KINDS}"
            == dlg._same_reading_spin.accessibleName())
    dlg.deleteLater()


#: The catalogue's established word for "chart" (Create Chart, Print Chart,
#: verification chart ...), and the stray word beta 17 brought in.
CHART_WORD = {
    "it": (r"grafic", r"\btarget\b"),
    "no": (r"kart", r"testark|(profilerings|verifiserings|kalibrerings)ark"),
    "pl": (r"wzor[cz]", r"wzorni"),
    "ru": (r"мишен", r"шкал"),
    "sv": (r"diagram", r"testark|(profilerings|verifierings|kalibrerings)ark"),
    "uk": (r"діаграм", r"шкал"),
}


def _beta17_texts():
    """The English source of every text beta 17 added for the misread table,
    its help, the cards and the presets window."""
    from ui.dialogs import settings_dialog as sd
    from ui.dialogs import preset_verification_dialog as pv
    from workflow import measurement_messages as M
    out = [sd.KIND_ESTIMATED_NAME, sd.KIND_ACCURATE_NAME,
           sd.KIND_VERIFICATION_NAME, sd.KIND_CALIBRATION_NAME,
           sd.SAME_FOR_ALL_KINDS, sd.PATCH_ERROR_LIMIT_DEFAULT,
           sd.STRIP_TEST_HELP, sd.STRIP_TEST_VERIFICATION_HELP,
           sd.STRIP_TEST_DEFAULT, sd.NEIGHBOUR_CHECK_HELP,
           sd.NEIGHBOUR_CHECK_DEFAULT, sd.SAME_READING_HELP,
           sd.LIMITS_PURPOSE_HELP, pv.TWO_COUNTS_NOTE, pv.OWN_COLOURS_HELP]
    out += list(M.CARD_KIND_PHRASES.values())
    return out


def sd_strip_verification() -> str:
    from ui.dialogs import settings_dialog as sd
    return sd.STRIP_TEST_VERIFICATION_HELP


@pytest.mark.parametrize("code", sorted(CHART_WORD))
def test_the_new_texts_use_the_catalogues_own_word_for_chart(code):
    cat = json.loads((ROOT / "data" / "i18n" / f"{code}.json")
                     .read_text(encoding="utf-8"))
    good, stray = CHART_WORD[code]
    # the established word really is the catalogue's
    assert re.search(good, cat["Create Chart"], re.I), cat["Create Chart"]
    for en in _beta17_texts():
        text = cat.get(en)
        assert text, f"{code}: untranslated {en[:60]!r}"
        if en == sd_strip_verification():
            # its measured part speaks of verification SHEETS ("ark" is
            # the right word there); the heading and the first paragraph
            # speak of the chart
            text = "\n\n".join(text.split("\n\n")[:2])
        hit = re.search(stray, text, re.I)
        assert hit is None, (code, hit.group(0), en[:60])
    # and every chart-type name carries the established word
    from ui.dialogs import settings_dialog as sd
    for en in (sd.KIND_ESTIMATED_NAME, sd.KIND_ACCURATE_NAME,
               sd.KIND_VERIFICATION_NAME, sd.KIND_CALIBRATION_NAME):
        assert re.search(good, cat[en], re.I), (code, cat[en])


def test_ukrainian_says_more_than_the_limit_not_above_it():
    cat = json.loads((ROOT / "data" / "i18n" / "uk.json")
                     .read_text(encoding="utf-8"))
    bad = [k for k, v in cat.items()
           if isinstance(v, str) and "понад межею" in v]
    assert bad == []
