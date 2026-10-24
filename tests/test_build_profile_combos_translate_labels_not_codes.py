"""The Build Profile tab's viewing-condition and rendering-intent combos.

Until 4.3.12 these two lists were added without tr(), so every language showed
them in English. They are translated now, and this file pins the one thing a
translation must never touch: the code each entry hands to colprof (-c / -d,
-t / -T) and stores in a per-target preset. The combos are filled with
addItem(label, code) and read back with currentData() / findData(), so a
preset saved in English must load in Ukrainian onto the same entries and save
back identically, and every visible label keeps its Argyll code in brackets,
because that code is what people look up in the ArgyllCMS documentation.
"""
from __future__ import annotations

import os
import re

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication                         # noqa: E402

from core import i18n                                            # noqa: E402
from core.argyll_runner import ArgyllRunner                      # noqa: E402
from core.settings import AppSettings                            # noqa: E402
import ui.tabs.tab_profile as tp                                 # noqa: E402

_INTENT_CODES = ["", "p", "pa", "lp", "r", "rl", "ms", "s", "a", "aw", "aa",
                 "al"]
_VIEW_CODES = ["", "pe", "pc", "pp", "mt", "mb", "md", "jm", "jd", "pcd",
               "ob", "cx"]
_LANGS = [code for code, _name in i18n.available_languages()]


@pytest.fixture
def language():
    previous = i18n.current_language()
    yield
    i18n.set_language(previous)


@pytest.mark.parametrize("lang", _LANGS)
def test_every_language_keeps_the_codes_and_shows_them(lang, language):
    i18n.set_language(lang)
    intents = tp._intents()
    views = tp._viewing_conditions()
    assert [c for _l, c in intents] == _INTENT_CODES
    assert [c for _l, c in views] == _VIEW_CODES
    for label, code in intents + views:
        assert label.strip(), (lang, code)
        if code:
            assert re.search(r"\(" + re.escape(code) + r"\)\s*$", label), (
                f"{lang}: the label for Argyll code {code!r} must still end "
                f"in “({code})”, got {label!r}")


def test_the_labels_are_translated(language):
    i18n.set_language("uk")
    labels = [l for l, _c in tp._intents() + tp._viewing_conditions()]
    i18n.set_language("en")
    english = [l for l, _c in tp._intents() + tp._viewing_conditions()]
    changed = [e for e, u in zip(english, labels) if e != u]
    assert len(changed) == len(english), (
        "every entry of both lists is shown in Ukrainian, none is left in "
        "English: " + ", ".join(e for e, u in zip(english, labels) if e == u))


def _tab(tmp_path, lang):
    from PyQt6.QtCore import QSettings
    QApplication.instance() or QApplication([])
    i18n.set_language(lang)
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / f"{lang}.ini"),
                      QSettings.Format.IniFormat)
    return tp.TabProfile(ArgyllRunner(s), s)


def test_a_preset_saved_in_english_loads_and_saves_the_same_in_ukrainian(
        tmp_path, language):
    en = _tab(tmp_path, "en")
    en._m_src_viewing_combo.setCurrentIndex(
        en._m_src_viewing_combo.findData("md"))
    en._m_dst_viewing_combo.setCurrentIndex(
        en._m_dst_viewing_combo.findData("pp"))
    en._m_perc_intent_combo.setCurrentIndex(
        en._m_perc_intent_combo.findData("lp"))
    en._m_sat_intent_combo.setCurrentIndex(
        en._m_sat_intent_combo.findData("aw"))
    saved = en._m_collect_preset_data()
    assert (saved["src_viewing"], saved["dst_viewing"],
            saved["perc_intent"], saved["sat_intent"]) == ("md", "pp", "lp",
                                                            "aw")

    uk = _tab(tmp_path, "uk")
    uk._m_apply_preset_data(saved)
    assert uk._m_src_viewing_combo.currentData() == "md"
    assert uk._m_dst_viewing_combo.currentData() == "pp"
    assert uk._m_perc_intent_combo.currentData() == "lp"
    assert uk._m_sat_intent_combo.currentData() == "aw"
    assert uk._m_src_viewing_combo.currentText().endswith("(md)")
    assert uk._m_src_viewing_combo.currentText() != (
        en._m_src_viewing_combo.currentText())
    again = uk._m_collect_preset_data()
    for key in ("src_viewing", "dst_viewing", "perc_intent", "sat_intent"):
        assert again[key] == saved[key], key
