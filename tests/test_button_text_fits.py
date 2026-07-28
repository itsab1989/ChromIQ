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


def test_both_completion_dialogs_offer_close_and_the_renamed_button():
    """Knut (#131) asked for this once and I changed only the averaging dialog;
    he then met the other one. Both paths are pinned here so a rename can never
    again land in one place only."""
    import pathlib
    src = (pathlib.Path(__file__).resolve().parents[1]
           / "ui" / "tabs" / "tab_measure.py").read_text()
    # Three dialogs offer this step: the two All-Stripes-Read variants
    # (averaging on and off) and the post-measurement averaging dialog.
    assert src.count('tr("Go to Build Profile Tab →")') == 3, \
        "every dialog offering the step must use the renamed button"
    assert src.count('tr("Close")') >= 3, "each must also offer Close"
    assert "Continue to Build Profile" not in src, "old wording left behind"
    assert 'QPushButton(tr("Build Profile →")' not in src


def test_a_stylesheet_min_width_cannot_hold_a_button_narrow(qapp):
    """#131 (Knut, 2026-07-27): "I thought you made a global rule … why did it
    now happen?"

    Because a stylesheet's own ``min-width`` decides the minimum size hint and
    beats ``setMinimumWidth``. The app sheet sets 72 px on every QPushButton, so
    pop-up buttons kept collapsing to it and clipping their labels. The fit now
    answers in the same language, and this test fails if it stops doing so.
    """
    from PyQt6.QtWidgets import QPushButton

    from ui.widgets import ButtonFontFilter, fit_button_width
    btn = QPushButton("Replace stored chart")
    btn.setStyleSheet("QPushButton { min-width: 72px; }")
    ButtonFontFilter.fit(btn)

    assert "min-width" in btn.styleSheet()
    fit_button_width(btn)
    # The minimum the widget will actually report — the number the layout uses.
    from PyQt6.QtGui import QFontMetrics
    needed = QFontMetrics(btn.font()).horizontalAdvance(btn.text().upper())
    assert btn.minimumSizeHint().width() >= needed, (
        f"{btn.minimumSizeHint().width()}px reported for {needed}px of text")


def test_fitting_twice_does_not_pile_up_rules(qapp):
    """It runs on every polish, so it must stay idempotent in effect."""
    from PyQt6.QtWidgets import QPushButton

    from ui.widgets import ButtonFontFilter
    btn = QPushButton("Keep stored chart")
    for _ in range(4):
        ButtonFontFilter.fit(btn)
    first = btn.minimumSizeHint().width()
    ButtonFontFilter.fit(btn)
    assert btn.minimumSizeHint().width() == first


def test_a_two_line_label_is_measured_line_by_line(qapp):
    """#131 (Knut, 2026-07-28): the Print Chart buttons suddenly looked wrong.

    Their labels are written over two lines, and the fit was measuring the whole
    string as if it were one — so "Print\\nCurrent Page" asked for the width of
    "PrintCurrent Page" and the buttons were forced far too wide, throwing their
    text out of alignment.
    """
    from PyQt6.QtGui import QFontMetrics
    from PyQt6.QtWidgets import QPushButton

    from ui.widgets import ButtonFontFilter
    two_line = QPushButton("Print\nCurrent Page")
    ButtonFontFilter.fit(two_line)
    one_line = QPushButton("PrintCurrent Page")
    ButtonFontFilter.fit(one_line)

    assert two_line.minimumSizeHint().width() < one_line.minimumSizeHint().width(), \
        "a wrapped label must not ask for the width of its lines end to end"

    # …and it is still wide enough for its widest line.
    fm = QFontMetrics(two_line.font())
    widest = max(fm.horizontalAdvance(l.upper()) for l in two_line.text().split("\n"))
    assert two_line.minimumSizeHint().width() >= widest


def test_the_print_chart_buttons_are_not_forced_oversized(qapp):
    """The property that actually broke: whatever minimum the fit asks for, it
    must be a width the label needs — not the width of its lines end to end.

    (Whether a style sheet is written at all depends on what the application
    sheet already provides; with it applied these four need nothing extra, which
    was confirmed on screen.)
    """
    from PyQt6.QtGui import QFontMetrics
    from PyQt6.QtWidgets import QPushButton

    from ui.widgets import ButtonFontFilter
    for label in ("Print\nCurrent Page", "Print All\nPages",
                  "Save as\nDefaults", "Clear\nPrint Queue"):
        btn = QPushButton(label)
        ButtonFontFilter.fit(btn)
        fm = QFontMetrics(btn.font())
        widest = max(fm.horizontalAdvance(l.upper())
                     for l in btn.text().split("\n"))
        joined = fm.horizontalAdvance(btn.text().replace("\n", "").upper())
        asked = btn.minimumSizeHint().width()
        assert widest <= asked < joined + 36, (
            f"{label!r}: asked for {asked}px; its widest line needs {widest}px "
            f"and its lines end to end would be {joined}px")


def test_the_accent_tint_cannot_wipe_a_button_s_width(qapp):
    """#131 (Knut, 2026-07-28), the third report of clipped pop-up buttons.

    `fit_button_width` writes a `min-width` rule into the button's own style
    sheet — the only thing the application sheet's own `min-width` respects —
    and `tint_dialog_primary` used to REPLACE that sheet with the accent
    colours, throwing the width away. The button then collapsed to 72 px and
    clipped its label again.
    """
    from PyQt6.QtGui import QFontMetrics
    from PyQt6.QtWidgets import QDialog, QPushButton, QVBoxLayout

    from ui.widgets import ButtonFontFilter, tint_dialog_primary
    dlg = QDialog()
    lay = QVBoxLayout(dlg)
    btn = QPushButton("Go to Build Profile Tab →", dlg)
    btn.setObjectName("primary")
    lay.addWidget(btn)
    ButtonFontFilter.fit(btn)
    before = btn.minimumSizeHint().width()

    tint_dialog_primary(dlg, "#1FB7C7")

    needed = QFontMetrics(btn.font()).horizontalAdvance(btn.text().upper())
    assert btn.minimumSizeHint().width() >= needed, "the tint clipped it again"
    # The width RULE must survive the tint — that is what used to be thrown
    # away. (The resolved hint may shift by a few pixels as the tint changes
    # the border, which is why the rule is what is asserted, not the number.)
    assert "min-width" in btn.styleSheet()
    assert before > 0
    # …and the tint itself still applied.
    assert "1fb7c7" in btn.styleSheet().lower()


def test_a_button_is_refitted_when_something_restyles_it(qapp):
    """Belt and braces for the same failure: whatever resets a button later,
    showing or restyling it puts the width back."""
    import inspect

    from ui.widgets import ButtonFontFilter
    src = inspect.getsource(ButtonFontFilter.eventFilter)
    assert "QEvent.Type.Show" in src and "QEvent.Type.StyleChange" in src
    assert "_fitting" in src, "re-entry must be guarded"
