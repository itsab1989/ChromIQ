"""A standard button reads the word ChromIQ's own texts use for it.

4.3.12: the Measure tab's instrument-choice window explained "•  Гаразд:
applies the choice above to this chart" above a button that read "OK". The
text was ChromIQ's catalogue (tr("OK") is «Гаразд»); the button was Qt's own
standard button, translated by qtbase_uk.qm, which keeps the Latin "OK". The
same split ran through other languages: Russian texts said "ОК" (Cyrillic)
above a Latin "OK", Swedish "OK" above "Ok", Polish and Portuguese named a
Save button that read "Zachowaj" and "Salvar", and Spanish told people to press
<b>OK</b> on a button that reads "Aceptar".

`core.i18n.install_qt_translator` now puts a small translator in front of
Qt's, so every standard button whose word the catalogue has reads exactly
tr(word). This file pins both halves: the buttons follow the catalogue in
every language, and a text that tells someone to press OK, Cancel or Close
names it the way the button reads.

It also pins the Norwegian fallback's own fault, found on the way: it answered
"" (an empty string, which Qt takes as the answer) for every Qt string it did
not hold, so the line-edit context menu read blank.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from core import i18n

ROOT = Path(__file__).resolve().parent.parent
LANGS = sorted(p.stem for p in (ROOT / "data" / "i18n").glob("*.json"))


@pytest.fixture
def in_language(qapp):
    previous = i18n.current_language()

    def switch(code: str) -> None:
        i18n.remove_qt_translators(qapp)
        i18n.set_language(code)
        i18n.install_qt_translator(qapp)

    yield switch
    i18n.remove_qt_translators(qapp)
    i18n.set_language(previous)


@pytest.mark.parametrize("code", LANGS)
def test_every_standard_button_reads_the_catalogue_word(code, in_language):
    from PyQt6.QtWidgets import QDialogButtonBox
    in_language(code)
    sb = QDialogButtonBox.StandardButton
    kinds = {"OK": sb.Ok, "Cancel": sb.Cancel, "Close": sb.Close,
             "Save": sb.Save, "Discard": sb.Discard, "Apply": sb.Apply,
             "Retry": sb.Retry, "Open": sb.Open, "Help": sb.Help,
             "Reset": sb.Reset}
    box = QDialogButtonBox()
    wrong = []
    for word, kind in kinds.items():
        want = i18n.tr(word)
        if want == word and code != "en":
            # the catalogue has no word of its own: Qt's stays, unjudged
            continue
        got = box.addButton(kind).text().replace("&", "")
        if got != want:
            wrong.append(f"{word}: the button reads {got!r}, the texts say "
                         f"{want!r}")
    box.deleteLater()
    assert not wrong, f"{code}: " + "; ".join(wrong)


@pytest.mark.parametrize("code", ["uk", "ru", "no"])
def test_a_qt_string_the_catalogue_lacks_is_still_there(code, in_language):
    """Qt's own words keep coming from Qt: the line-edit menu is not blank."""
    from PyQt6.QtCore import QCoreApplication
    in_language(code)
    for source in ("&Undo", "&Copy", "Select All"):
        assert QCoreApplication.translate("QLineEdit", source).strip(), (
            code, source)
    # and a button word the catalogue does not hold still comes from Qt
    assert QCoreApplication.translate("QPlatformTheme", "&Yes").strip()


def test_the_choice_window_bullet_and_its_button_agree(in_language):
    """The window the fault was seen in: Measure tab, instrument choice."""
    from PyQt6.QtWidgets import QDialogButtonBox
    in_language("uk")
    box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok
                           | QDialogButtonBox.StandardButton.Cancel)
    ok = box.button(QDialogButtonBox.StandardButton.Ok).text()
    cancel = box.button(QDialogButtonBox.StandardButton.Cancel).text()
    box.deleteLater()
    cat = json.loads((ROOT / "data/i18n/uk.json").read_text(encoding="utf-8"))
    bullet = cat["What each button does:\n\n"
                 "•  OK — applies the choice above to this chart. Nothing is "
                 "measured and nothing is written yet; you still press Start "
                 "Measurement when you are ready.\n\n"
                 "•  Cancel — changes nothing at all. The chart stays loaded, "
                 "your existing measurement is untouched, and the setting "
                 "stays as it was. You can set it later in the options panel."]
    assert f"•  {ok} —" in bullet or f"•  {ok}:" in bullet, (ok, bullet[:120])
    assert f"•  {cancel} —" in bullet or f"•  {cancel}:" in bullet, cancel


#: "press OK", "click <b>OK</b>", "or “Cancel” to …": a text sending someone
#: to a standard button by its word. Multi-word buttons ("Cancel the
#: measurement", "Close Project") are their own controls and are not matched.
_WORDS = ("OK", "Cancel", "Close")


def _mentions(word: str):
    w = re.escape(word)
    return re.compile(
        r"<b>" + w + r"</b>|“" + w + r"”|\"" + w + r"\"|«" + w + r"»"
        r"|(?:[Cc]lick|[Pp]ress|[Hh]it|[Tt]ap)\s+" + w
        + r"(?=[.,;:)]|\s+(?:and|to|or|then|again|—)\b)")


@pytest.mark.parametrize("code", [c for c in LANGS if c != "en"])
def test_a_text_names_a_standard_button_as_it_reads(code):
    cat = json.loads((ROOT / "data" / "i18n" / f"{code}.json")
                     .read_text(encoding="utf-8"))
    bad = []
    for key, value in i18n.catalog_texts(cat):
        for word in _WORDS:
            loc = cat.get(word)
            if not loc or not _mentions(word).search(key):
                continue
            if loc not in value:
                bad.append(f"  {word} reads {loc!r}, but the text says "
                           f"{value[:90]!r}")
    assert not bad, f"{code}:\n" + "\n".join(bad)
