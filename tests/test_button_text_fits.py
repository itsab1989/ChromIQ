"""#130 (Knut, 2026-07-26): no button anywhere in the application may paint its
label clipped, and every button must get its width the same way.

The fault was systemic rather than local. ``ButtonFontFilter`` swaps every
QPushButton to Menlo in capitals as it is polished — a wider label than the one
the button sized itself for — and nothing widened the button afterwards, so the
text was cut at both ends. ``fit_button_width`` is now the single place a button
width is decided, and the filter calls it.

Note: the ``Polish`` event that drives the filter does not fire under the
offscreen platform, so these tests call the filter directly rather than relying
on the app to do it.
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtGui import QFont, QFontMetrics                # noqa: E402
from PyQt6.QtWidgets import QApplication, QPushButton      # noqa: E402

from ui.widgets import ButtonFontFilter, fit_button_width  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _painted_width(btn) -> int:
    """What the label really measures in the font the button paints with."""
    text = btn.text().replace("&&", "\x00").replace("&", "").replace("\x00", "&")
    font = btn.font()
    if font.capitalization() == QFont.Capitalization.AllUppercase:
        text = text.upper()
    return QFontMetrics(font).horizontalAdvance(text)


LABELS = [
    "Replace the stored chart",          # the pop-up Knut reported
    "Cancel",
    "Restore Used Chart",
    "Measure into a new date",
    "Überschreiben und fortfahren",      # a longer translation
]


@pytest.mark.parametrize("label", LABELS)
def test_a_button_is_wide_enough_for_the_font_it_paints_with(qapp, label):
    btn = QPushButton(label)
    ButtonFontFilter.fit(btn)            # what the app does on polish
    assert btn.minimumWidth() >= _painted_width(btn), (
        f"“{label}” needs {_painted_width(btn)}px but the button allows "
        f"{btn.minimumWidth()}px — it will be clipped")


def test_the_uppercase_swap_is_what_the_width_is_measured_against(qapp):
    """The bug in one assertion: sizing against the *pre-swap* font is not
    enough, so a width taken before the filter runs must not be trusted."""
    btn = QPushButton("Replace the stored chart")
    before = QFontMetrics(btn.font()).horizontalAdvance(btn.text())
    ButtonFontFilter.fit(btn)
    after = _painted_width(btn)
    assert after > before, "Menlo in capitals is wider — that was the trap"
    assert btn.minimumWidth() >= after


def test_widening_is_one_way(qapp):
    """A width somebody set deliberately is never reduced."""
    btn = QPushButton("OK")
    btn.setMinimumWidth(400)
    fit_button_width(btn)
    assert btn.minimumWidth() == 400


def test_a_mnemonic_is_not_counted_as_a_character(qapp):
    """"&Cancel" paints as "Cancel"; the ampersand must not inflate the width,
    and "&&" is a real ampersand."""
    plain, mnemonic = QPushButton("Cancel"), QPushButton("&Cancel")
    fit_button_width(plain); fit_button_width(mnemonic)
    assert plain.minimumWidth() == mnemonic.minimumWidth()

    amp = QPushButton("Save && Quit")
    fit_button_width(amp)
    assert amp.minimumWidth() >= _painted_width(amp)


def test_an_empty_button_is_left_alone(qapp):
    btn = QPushButton("")
    fit_button_width(btn)
    assert btn.minimumWidth() == 0


def test_the_pop_up_buttons_fit(qapp):
    """The exact case reported: the verification chart-overwrite warning."""
    from PyQt6.QtWidgets import QMessageBox
    from core.i18n import tr
    box = QMessageBox()
    for label in (tr("Replace the stored chart"),):
        btn = box.addButton(label, QMessageBox.ButtonRole.DestructiveRole)
        ButtonFontFilter.fit(btn)
        assert btn.minimumWidth() >= _painted_width(btn)


def test_the_filter_is_installed_for_the_whole_application():
    """The standardisation only holds if every button really passes through the
    filter — so this pins the wiring in main.py, not just the helper."""
    source = (__import__("pathlib").Path(__file__).resolve().parents[1]
              / "main.py").read_text()
    assert "ButtonFontFilter(app)" in source
    assert "app.installEventFilter(_btn_font_filter)" in source
