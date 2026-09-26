"""Preferences' OK wears Restore Factory Defaults' colour, in every appearance.

Basti, 2026-09-26, on OK turning blue after K44 (the button Return presses is
filled in the window's accent, and Preferences, opened from no tab, fell back
to the application's accent, a blue nothing else in the window uses): "if it
gets any color than restore factory settings had before". So OK takes the
rule Restore Factory Defaults has in each sheet, whatever colour that is.

MUTATION: drop ``QPushButton#prefs_ok`` from one sheet, or the objectName in
the dialog, and this goes red.
"""
import inspect
import re

import pytest


@pytest.mark.parametrize("module", ["ui.styles", "ui.light_styles",
                                    "ui.neutral_styles"])
def test_every_sheet_styles_ok_like_restore(module):
    import importlib
    src = inspect.getsource(importlib.import_module(module))
    assert re.search(r"QPushButton#reset_defaults, QPushButton#prefs_ok \{\{",
                     src), module
    assert re.search(r"QPushButton#reset_defaults:hover, "
                     r"QPushButton#prefs_ok:hover \{\{", src), module


def test_the_dialog_names_its_ok_button():
    from ui.dialogs import settings_dialog
    src = inspect.getsource(settings_dialog)
    assert ('bb.button(QDialogButtonBox.StandardButton.Ok)'
            '.setObjectName("prefs_ok")') in src


def test_the_dialog_pins_ok_in_its_own_sheet():
    """Opened from the Create Chart tab (Edit layout defaults) the dialog is
    the tab's child, and the tab's sheet beat the application sheet: OK came
    out magenta (Basti, 2026-09-26). The dialog's own sheet is nearer.

    MUTATION: drop ``buttons_qss`` from the dialog's setStyleSheet and this
    goes red."""
    from ui.dialogs import settings_dialog
    src = inspect.getsource(settings_dialog.SettingsDialog._apply_indicator_theme)
    assert "QPushButton#prefs_ok:default" in src
    assert "+ buttons_qss" in src
