"""Beta 12: a string that sends the user to a tab names it as the tab bar does.

Polish called the Print Chart tab "Drukuj wzorzec" in 35 strings while the tab
itself reads "Wydrukuj wzorzec", and the Measure tab "Pomiar" while it reads
"Zmierz". Russian, Ukrainian and Dutch had the same drift for Build Profile
(the tab title is a noun or a different verb from the button of the same English
name). A user who is told to go to a tab that does not exist has to guess.

The button "Build Profile" may keep its own wording: only references to the TAB
are checked here.
"""
import json
import re
from pathlib import Path

import pytest

I18N = Path(__file__).resolve().parent.parent / "data" / "i18n"
LANGS = sorted(p.stem for p in I18N.glob("*.json"))
TAB_KEYS = ["1. Create Chart", "2. Print Chart", "3. Measure",
            "4. Build Profile", "5. Check & Refine"]


def _cat(lang):
    return json.loads((I18N / f"{lang}.json").read_text(encoding="utf-8"))


def _title(cat, key):
    return re.sub(r"^\d\.\s*", "", cat[key])


@pytest.mark.parametrize("lang", LANGS)
def test_the_go_to_tab_shortcut_lists_the_real_titles(lang):
    cat = _cat(lang)
    key = ("Go to a tab (1 Create Chart · 2 Print Chart · 3 Measure · "
           "4 Build Profile · 5 Check & Refine)")
    value = cat[key]
    for tab in TAB_KEYS:
        assert _title(cat, tab) in value, (lang, tab, value)


@pytest.mark.parametrize("lang", LANGS)
def test_the_bare_tab_names_match_the_tab_bar(lang):
    """file_guide.py and the help cards show tr("Print Chart") etc. as tab names."""
    cat = _cat(lang)
    for bare in ("Create Chart", "Print Chart", "Check & Refine"):
        full = next(t for t in TAB_KEYS if t.endswith(bare))
        assert cat[bare] == _title(cat, full), (lang, bare, cat[bare])


# Old names that drifted, and the phrase that introduces a tab in that language.
STALE = {
    "pl": (r"\bkar(?:ta|cie|ty|tę|tach)\s+[„“]?", ["Drukuj wzorzec", "Pomiar", "Utwórz profil"]),
    "ru": (r"[Вв]кладк\w*\s+[«]?", ["Собрать профиль", "Создать профиль"]),
    "uk": (r"(?:[Вв]кладк\w*|[Вв]кладц\w*)\s+[«]?",
           ["Побудувати профіль", "Створення профілю", "Вимірювання", "Друк діаграми",
            "Build Profile", "Print Chart"]),
    "nl": (r"tabblad\s+[‘“]?", ["Profiel bouwen"]),
}


@pytest.mark.parametrize("lang", sorted(STALE))
def test_no_string_sends_the_user_to_a_tab_by_an_old_name(lang):
    intro, names = STALE[lang]
    offenders = []
    for key, value in _cat(lang).items():
        if not isinstance(value, str):
            continue
        for name in names:
            if re.search(intro + re.escape(name), value):
                offenders.append((name, key[:60]))
    assert not offenders, offenders


def test_polish_never_says_drukuj_wzorzec():
    for key, value in _cat("pl").items():
        assert not re.search(r"(?<!Wy)Drukuj wzorzec", value), key[:60]
