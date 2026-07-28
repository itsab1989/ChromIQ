"""#131 (Knut, 2026-07-27): button labels must never be clipped, in any language.

*"When buttons have text beyond its visible width, the button width must
automatically adapt, right? And when the buttons change, the position and
distance between each button should be kept, and the window width should follow
the change of the button size. If this is not done correctly, this may be a
reoccurring problem for all languages. Do extensive testing to verify that this
happens correctly and that visible label area in a button is always bigger than
the defined button text width."*

So: every button label ChromIQ puts in a pop-up, measured in **every** language
it ships, in the font that will actually paint it.

Note on where this runs. `ButtonFontFilter` swaps buttons to Menlo in capitals
at polish, and polish does not happen offscreen — so an offscreen grab renders
the *narrower* font and would report "fine" while the real application clips.
These tests therefore measure the widths the fit computes rather than a rendered
window, and the on-screen check that goes with them lives in the scratchpad
harness described in the #131 comment.
"""
from __future__ import annotations

import json
import os
import pathlib

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtGui import QFontMetrics                 # noqa: E402
from PyQt6.QtWidgets import QApplication, QPushButton  # noqa: E402

import core.i18n as I                                # noqa: E402
from ui.widgets import ButtonFontFilter              # noqa: E402

_I18N = pathlib.Path(__file__).resolve().parents[1] / "data" / "i18n"


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _languages():
    """Every language the Settings combobox offers, English included."""
    return ["en"] + sorted(p.stem for p in _I18N.glob("*.json")
                           if "." not in p.stem)


#: The buttons of the pop-ups a measurement can raise. English source strings —
#: the catalogue lookup turns them into each language in turn.
_POPUP_BUTTONS = [
    "Replace stored chart",
    "Keep stored chart",
    "Replace the stored chart",
    "Re-read Strip",
    "Continue Anyway",
    "Re-read Individual Strips",
    "Save Partial && Quit",      # && is a literal ampersand on a button
    "Save Partial",
    "Skip Strip",
    "Go to Build Profile Tab →",
    "Close",
    "Cancel",
]


def _fitted(label: str) -> "tuple[QPushButton, int]":
    """A button through the app's own fit, and the width its text needs."""
    btn = QPushButton(label)
    ButtonFontFilter.fit(btn)
    text = btn.text().replace("&&", "\x00").replace("&", "").replace("\x00", "&")
    from PyQt6.QtGui import QFont
    if btn.font().capitalization() == QFont.Capitalization.AllUppercase:
        text = text.upper()
    return btn, QFontMetrics(btn.font()).horizontalAdvance(text)


@pytest.mark.parametrize("lang", _languages())
def test_every_popup_button_fits_its_label(qapp, lang):
    """The requirement in his words: the visible label area is always bigger
    than the text it has to show."""
    I.set_language(lang)
    try:
        too_small = []
        for source in _POPUP_BUTTONS:
            label = I.tr(source)
            btn, needed = _fitted(label)
            room = btn.minimumSizeHint().width()
            if room < needed:
                too_small.append((source, label, room, needed))
        assert not too_small, too_small
    finally:
        I.set_language("en")


def test_the_longest_translation_of_each_button_is_the_one_that_decides(qapp):
    """A label that fits in English can be half again as long in German or
    Dutch — which is exactly how this reaches users and not us."""
    longest = {}
    for lang in _languages():
        I.set_language(lang)
        for source in _POPUP_BUTTONS:
            label = I.tr(source)
            if len(label) > len(longest.get(source, ("", ""))[1]):
                longest[source] = (lang, label)
    I.set_language("en")

    for source, (lang, label) in longest.items():
        btn, needed = _fitted(label)
        assert btn.minimumSizeHint().width() >= needed, (
            f"{source!r} in {lang} ({label!r}) needs {needed}px but reports "
            f"{btn.minimumSizeHint().width()}px")


def test_a_long_label_makes_the_button_wider_not_the_text_smaller(qapp):
    """Adapting means growing. A button must never answer a long label by
    keeping its width."""
    short, _ = _fitted("Close")
    long_, _ = _fitted("Measure without changing the stored chart")
    assert long_.minimumSizeHint().width() > short.minimumSizeHint().width()


def test_the_style_sheet_minimum_cannot_win(qapp):
    """The actual defect behind his report: the app sheet sets min-width 72px on
    every button, and a style sheet's minimum beats setMinimumWidth."""
    btn = QPushButton("Replace stored chart")
    btn.setStyleSheet("QPushButton { min-width: 72px; }")
    ButtonFontFilter.fit(btn)
    _b, needed = _fitted("Replace stored chart")
    assert btn.minimumSizeHint().width() >= needed


def test_the_catalogues_carry_these_buttons(qapp):
    """A guard on the test itself: if a label is renamed and the catalogue key
    goes stale, every language would silently fall back to English and this
    file would stop testing anything."""
    missing = []
    for lang in _languages():
        if lang == "en":
            continue
        cat = json.loads((_I18N / f"{lang}.json").read_text(encoding="utf-8"))
        for source in _POPUP_BUTTONS:
            if source not in cat:
                missing.append((lang, source))
    assert not missing, f"not in the catalogues: {missing}"
