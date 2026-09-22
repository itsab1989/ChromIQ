"""`setFixedHeight` cannot shrink a button in this app, and a guard that reads
`.height()` off a dialog nobody showed cannot see that.

WHAT WENT WRONG, TWICE
----------------------
Basti asked for the reference-values buttons to be shorter, and then asked
again: *"the three buttons should be reduced in heigth"*, then *"the current
ones are still big ... they could be smaller i think"*.

* beta 26 answered with ``setFixedHeight(22)``.
* its replacement, one door instead of three buttons, answers with
  ``setFixedHeight(18)``.

**Both are 42 px on screen.**  Measured in a real window, round 30,
``scripts/adv30_eighteen_px_is_forty_two.py``::

                              before show()    on screen
    setFixedHeight(18)                   18           42
    setFixedHeight(22)  (beta 26)        22           42
    a plain QPushButton                  30           42
    a per-widget stylesheet              30           22

``ui/styles.py`` sets, for every ``QPushButton`` in the app::

    QPushButton { padding: 6px 18px; min-height: 28px; ... }

28 + 6 + 6 + 1 + 1 = 42.  Qt's stylesheet style folds ``min-height`` and the
box model into ``minimumSizeHint``, and a layout honours a minimum size hint
over a fixed height.  So ``setFixedHeight`` is not merely ignored at some
sizes: it cannot make ANY button in ChromIQ shorter than 42 px.

The idiom that works is already in ``ui/dialogs/thresholds_dialog.py``, on its
"Restore defaults" button, and in three places in ``ui/styles.py``: a
per-widget stylesheet that puts ``min-height`` DOWN as well as capping
``max-height``.

WHY THIS FILE EXISTS RATHER THAN A LINE IN THE OTHER ONE
--------------------------------------------------------
The guard that shipped beside the change asserts
``dlg._iso_values_btn.height() == 18`` on a ``ThresholdsDialog`` that is never
shown, so it reads back the 18 nobody sees and goes green.  That is the same
shape as the guard that read the slots' SOURCE while all three buttons raised
`NameError` (commit ``6d7b265c``), one step further in: it measures a real
widget, but in a state the user never meets.  **A size guard has to lay the
widget out under the app's own stylesheet.**

It styles the DIALOG, never the application (CLAUDE.md: a
``qapp.setStyleSheet()`` in a test re-polishes every widget the suite has
alive and cost 29 s in one run).  That measures the same thing, because the
rule being defeated is an application-wide ``QPushButton`` rule and it applies
to a widget tree just the same.
"""
from __future__ import annotations

import pytest

pytest.importorskip("PyQt6.QtWidgets")

from PyQt6.QtWidgets import (QApplication, QDialog,  # noqa: E402
                             QPushButton, QVBoxLayout)

#: What a default QPushButton comes out at under ChromIQ's own stylesheet.
#: Nothing asserts this number itself; it is the thing a "small" button has to
#: be smaller than, and it is re-derived below rather than trusted.
DEFAULT_BUTTON_PX = 42

#: The ceiling a control called small has to come in under, and it is NOT a
#: number somebody liked the look of: 26 px is what the Report limits window's
#: own "Restore defaults" button has always measured on screen, five of them,
#: built from `min-height: 22px; max-height: 22px` plus 1 px padding and 1 px
#: border either side. `test_the_ceiling_is_the_windows_own_small_button`
#: re-derives it from that button, so the day the house style moves this file
#: says so instead of silently guarding the wrong thing.
SMALL_CEILING_PX = 26


def _app():
    return QApplication.instance() or QApplication([])


def _shown(dlg: QDialog) -> None:
    dlg.show()
    for _ in range(40):
        QApplication.processEvents()


def _sheet() -> str:
    from ui.light_styles import LIGHT_STYLESHEET
    return LIGHT_STYLESHEET


def test_setfixedheight_cannot_shrink_a_button_in_this_app(qapp):
    """The mechanism, stated as a fact so nobody reaches for it again."""
    dlg = QDialog()
    dlg.setStyleSheet(_sheet())
    lay = QVBoxLayout(dlg)
    fixed = QPushButton("setFixedHeight(18)", dlg)
    fixed.setFixedHeight(18)
    lay.addWidget(fixed)
    plain = QPushButton("plain", dlg)
    lay.addWidget(plain)
    try:
        _shown(dlg)
        assert plain.height() >= 36, (
            "a default button under ChromIQ's stylesheet is no longer tall; "
            f"re-derive this file's numbers (got {plain.height()})")
        assert fixed.height() == plain.height(), (
            "setFixedHeight(18) now actually shrinks a button — if the "
            "stylesheet's QPushButton min-height went away, this whole file "
            f"can go (fixed={fixed.height()} plain={plain.height()})")
    finally:
        dlg.close()


def test_a_per_widget_stylesheet_is_the_idiom_that_works(qapp):
    """And the one that does work, so the fix is named and not just the fault."""
    dlg = QDialog()
    dlg.setStyleSheet(_sheet())
    lay = QVBoxLayout(dlg)
    b = QPushButton("small", dlg)
    b.setStyleSheet("QPushButton { padding: 1px 6px; font-size: 10px;"
                    " min-height: 18px; max-height: 18px; min-width: 0; }")
    lay.addWidget(b)
    try:
        _shown(dlg)
        assert b.height() <= SMALL_CEILING_PX, b.height()
    finally:
        dlg.close()


def test_the_report_limits_door_is_short_where_a_reader_sees_it(qapp, tmp_path):
    """THE DOOR ITSELF, laid out, under the app's stylesheet.

    Basti asked twice. The guard that shipped with the change reads
    ``.height()`` off an unshown dialog and gets the 18 that was asked for;
    this one shows the window and gets what he gets.
    """
    from PyQt6.QtCore import QSettings

    from core.settings import AppSettings
    from ui.dialogs.thresholds_dialog import ThresholdsDialog

    s_ = AppSettings()
    s_._qs = QSettings(str(tmp_path / "t.ini"), QSettings.Format.IniFormat)
    dlg = ThresholdsDialog(s_)
    dlg.setStyleSheet(_sheet())
    try:
        _shown(dlg)
        h = dlg._iso_values_btn.height()
        assert h <= SMALL_CEILING_PX, (
            f"the Reference values door is {h} px on screen. He asked for it "
            f"to be short twice. setFixedHeight cannot do it here — see this "
            f"file's docstring for the idiom that can.")
    finally:
        dlg.close()


def test_the_reference_values_buttons_are_short_where_a_reader_sees_them(qapp):
    """All three in the new window, same measurement."""
    from ui.dialogs.reference_values_dialog import ReferenceValuesDialog

    dlg = ReferenceValuesDialog()
    dlg.setStyleSheet(_sheet())
    try:
        _shown(dlg)
        tall = {b.text(): b.height() for b in dlg.findChildren(QPushButton)
                if b.text() and b.height() > SMALL_CEILING_PX
                and b.text() != "Close"}
        assert not tall, (
            f"these are not small on screen: {tall}. Close is a normal "
            f"button and is left alone.")
    finally:
        dlg.close()


def test_the_ceiling_is_the_windows_own_small_button(qapp, tmp_path):
    """SMALL_CEILING_PX is re-derived, not remembered.

    "Restore defaults" predates all of this and is the Report limits
    window's own footnote-sized button. If the house style moves, this fails
    here, naming the new number, rather than leaving the guards above
    measuring against a stale one.

    It was called "Restore this column" until 2026-09-22. Knut: *"Since the
    button exists for most of the columns it is understood that the button
    restores defaults for the specific column the button belong to."* The
    button sits under the column it acts on, so naming the column in the label
    was spending width on what the position already says. The MATCH below is
    on the new text, and this note is here so a reader of the old name in a
    screenshot can find it.
    """
    from PyQt6.QtCore import QSettings

    from core.settings import AppSettings
    from ui.dialogs.thresholds_dialog import ThresholdsDialog

    s_ = AppSettings()
    s_._qs = QSettings(str(tmp_path / "t.ini"), QSettings.Format.IniFormat)
    dlg = ThresholdsDialog(s_)
    dlg.setStyleSheet(_sheet())
    try:
        _shown(dlg)
        restore = {b.height() for b in dlg.findChildren(QPushButton)
                   if "Restore defaults" in b.text()}
        assert restore, "the Report limits window has no Restore defaults button"
        assert restore == {SMALL_CEILING_PX}, (
            f"the window's own small button is {sorted(restore)} px, not "
            f"{SMALL_CEILING_PX}. Re-derive SMALL_CEILING_PX from it.")
    finally:
        dlg.close()


def test_this_file_can_see_the_fault_it_guards(qapp):
    """THE MUTATION, run rather than described.

    A button built exactly the way the shipped code builds it — 18 px through
    ``setFixedHeight`` — must fail the ceiling the three guards above apply.
    If this ever passes, those three are measuring nothing.
    """
    dlg = QDialog()
    dlg.setStyleSheet(_sheet())
    lay = QVBoxLayout(dlg)
    b = QPushButton("as the shipped code builds it", dlg)
    b.setFixedHeight(18)
    lay.addWidget(b)
    try:
        _shown(dlg)
        assert b.height() > SMALL_CEILING_PX, (
            "the shipped idiom now produces a short button, so the guards "
            "above cannot fail and this file is dead weight")
    finally:
        dlg.close()
