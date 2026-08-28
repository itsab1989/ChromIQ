"""F1: typing 0.7 into any number field gave 7.0 on a German machine.

ChromIQ never touched `QLocale`, so every spin box ran on the SYSTEM locale —
comma on any European one. But the app writes its numbers the English way
everywhere else: the tooltips say 0.7, the ArgyllCMS flag documentation says 0.7,
and the live command preview directly under the field says -T0.70. Type what you
are told to type and the "." keystroke is rejected by the validator, the digits
close up, and 0.7 becomes 07 — which is 7.0. In range, no warning, and nothing
on screen disagreeing with anything else.

Measured on screen 2026-08-28 on a real de_DE machine: 14 of 14 fields. The
expensive one is `chartread -T`, where the app really sent `-T7.00` instead of
`-T0.70`: the instrument is told to accept a strip ten times further out of
agreement than the person asked for, which is a measurement that looks fine and
is not. The dE re-measurement threshold mirrors it — ask for 0.7, get 7.0, and
no strip is ever flagged for re-measurement.

Basti ruled on 2026-08-28: accept both separators, and a comma is ALWAYS a
decimal point, never a thousands separator.
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtCore import QLocale                                # noqa: E402
from PyQt6.QtTest import QTest                                  # noqa: E402
from PyQt6.QtWidgets import QApplication                        # noqa: E402

from ui.widgets import NoScrollDoubleSpinBox                    # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _typed(qapp, locale_name: str, text: str, *, decimals=2, hi=2000.0):
    """TYPE it, one key at a time. `lineEdit().insert(whole_string)` is not the
    same thing and answers a different question: an intermediate state that the
    validator rejects wholesale leaves the field empty, so `1,250` "became" 0.0
    there while a person typing the same five keys gets 1.25. The bug being
    fixed is about keystrokes, so the test has to use them."""
    box = NoScrollDoubleSpinBox()
    box.setLocale(QLocale(locale_name))
    box.setDecimals(decimals)
    box.setRange(0.0, hi)
    box.show()
    box.lineEdit().setText("")
    QTest.keyClicks(box.lineEdit(), text)
    box.interpretText()
    return box.value(), box.text()


# Every locale ChromIQ's thirteen languages can land on, both ways round.
@pytest.mark.parametrize("locale_name", ["de_DE", "C", "en_US", "fr_FR",
                                         "sv_SE", "pl_PL", "ru_RU"])
@pytest.mark.parametrize("text,expected", [("0.7", 0.7), ("0,7", 0.7),
                                           ("12.5", 12.5), ("12,5", 12.5)])
def test_both_separators_mean_the_same_number(qapp, locale_name, text, expected):
    value, _shown = _typed(qapp, locale_name, text)
    assert value == pytest.approx(expected), (
        f"{locale_name}: typing {text!r} gave {value}, not {expected}")


def test_the_tolerance_field_really_sends_what_was_asked_for(qapp):
    """The measured fault, in the field that costs the most. `-T` is the patch
    consistency tolerance: 7.00 accepts a strip ten times further out of
    agreement than 0.70 does."""
    value, _ = _typed(qapp, "de_DE", "0.7", decimals=2, hi=10.0)
    assert f"{value:.2f}" == "0.70", \
        "the app would send -T%.2f to chartread" % value


def test_a_comma_is_a_decimal_point_never_a_thousands_separator(qapp):
    """Basti's ruling, 2026-08-28. The alternative — refusing anything ambiguous
    — interrupts typing to prevent a case that barely exists: of the fourteen
    fields only two have a range that reaches four digits."""
    value, _ = _typed(qapp, "en_US", "1,250")
    assert value == pytest.approx(1.25), \
        "a comma was read as a thousands separator, which the ruling forbids"


def test_a_plain_integer_is_untouched_in_every_locale(qapp):
    for loc in ("de_DE", "en_US", "C"):
        value, _ = _typed(qapp, loc, "600")
        assert value == pytest.approx(600.0), loc


def test_the_box_still_shows_the_locale_the_person_uses(qapp):
    """Accepting both is an INPUT fix. Forcing the display to C was the first
    idea and is measurably worse: under C, typing 0,7 gives 7.0, which does not
    fix the bug but aims it at everyone whose keyboard habit is the comma."""
    _v, shown = _typed(qapp, "de_DE", "0.7")
    assert shown == "0,70", "the German user's own separator stopped being shown"
    _v, shown = _typed(qapp, "en_US", "0,7")
    assert shown == "0.70"


def test_every_float_row_in_the_app_is_one_of_these(qapp):
    """The fix is at one chokepoint, so it has to BE the chokepoint."""
    import inspect

    import ui.parameter_widget as pw
    src = inspect.getsource(pw)
    assert "NoScrollDoubleSpinBox" in src, \
        "parameter rows no longer build their float fields from this class"
    assert "QDoubleSpinBox(" not in src, \
        "a float row is being built from a raw QDoubleSpinBox, which bypasses the fix"
