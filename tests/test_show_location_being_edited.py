"""#130: "Show the location being edited" — Preferences → General.

Sebastian asked (2026-07-31) whether the "Location being edited" line under the
Profile-run bar could be optional, to simplify the interface for people who
never run verifications. Knut agreed, and settled both the wording and the
polarity — his sentence *"I would prefer to have that OFF as default"* was
ambiguous, since OFF means opposite things for a "Hide…" box and a "Show…" box,
so it was put to him rather than guessed:

    "I prefer 'Show the location being edited', enabled shows. I agree with the
     tool-tip, but the tool tip for the actual 'Location being edited' path and
     label should also mention that it can be hidden in Preferences -> General
     tab."

Default ON: when file handling goes wrong that line is the first thing anyone
looks at, so hiding it by default would cost the one detail that usually
explains the problem.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtCore import QSettings                        # noqa: E402
from PyQt6.QtWidgets import QApplication                  # noqa: E402

from core.file_manager import FileManager, Project        # noqa: E402
from core.settings import DEFAULTS, AppSettings           # noqa: E402
from ui.measurement_target_bar import (                   # noqa: E402
    MeasurementTargetBar, MeasurementTargetController)


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def bar(qapp, tmp_path):
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    s.set("custom_output_path", str(tmp_path))
    Project.create(tmp_path / "Demo", "Demo")
    fm = FileManager(s)
    fm.set_target_name("Demo")
    ctl = MeasurementTargetController(fm)
    b = MeasurementTargetBar(ctl, show_verification=True)
    ctl.set_profile_run("run1")
    b.refresh()
    return b, s


# ---- the default ---------------------------------------------------------
def test_the_line_is_shown_by_default():
    """Knut's polarity: enabled shows, and it ships enabled."""
    assert DEFAULTS["show_location_being_edited"] is True


def test_a_fresh_bar_shows_the_line(bar):
    b, _s = bar
    assert not b._location.isHidden()
    assert "Location being edited" in b._location.text()


# ---- the toggle ----------------------------------------------------------
def test_turning_it_off_hides_the_line(bar):
    b, s = bar
    s.set("show_location_being_edited", False)
    b.refresh()
    assert b._location.isHidden()


def test_turning_it_back_on_restores_the_line(bar):
    b, s = bar
    s.set("show_location_being_edited", False)
    b.refresh()
    s.set("show_location_being_edited", True)
    b.refresh()
    assert not b._location.isHidden()
    assert "Location being edited" in b._location.text()


def test_hiding_the_line_changes_nothing_else(bar):
    """"Nothing changes except that the line is hidden" — the folder ChromIQ
    works in must be identical either way."""
    b, s = bar
    before = b._ctl.location_being_edited()
    s.set("show_location_being_edited", False)
    b.refresh()
    assert b._ctl.location_being_edited() == before


def test_the_line_stays_hidden_with_no_project_even_when_enabled(qapp, tmp_path):
    """The preference must not override the older rule: an empty app shows no
    half-formed path."""
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    s.set("custom_output_path", str(tmp_path))
    s.set("show_location_being_edited", True)
    b = MeasurementTargetBar(MeasurementTargetController(FileManager(s)),
                             show_verification=True)
    b.refresh()
    assert b._location.isHidden()


def test_a_missing_setting_shows_the_line(bar):
    """A lookup that fails must not silently hide the thing that answers
    "where are my files?"."""
    b, _s = bar
    b._ctl._fm = object()          # no settings at all
    assert b._settings_show_location() is True


# ---- Knut's extra requirement -------------------------------------------
def test_the_line_says_where_it_can_be_turned_off(bar):
    """His words: the tooltip on the line itself "should also mention that it
    can be hidden in Preferences -> General tab"."""
    b, _s = bar
    tip = b._location.toolTip()
    assert "Preferences" in tip and "General" in tip
    assert "Show the location being edited" in tip


# ---- the Preferences control --------------------------------------------
def test_preferences_carries_the_checkbox_and_a_tooltip(qapp, tmp_path):
    import inspect
    from ui.dialogs import settings_dialog
    src = inspect.getsource(settings_dialog)
    assert 'QCheckBox(\n            tr("Show the location being edited")' in src \
        or 'tr("Show the location being edited")' in src
    assert "_show_location_check" in src
    # loaded, saved, and placed on the General page
    assert 's.get("show_location_being_edited", True)' in src
    assert 's.set("show_location_being_edited"' in src
    assert "_bh_cell(self._show_location_check, show_location_tip)" in src


def test_the_preferences_tooltip_explains_both_choices(qapp):
    """House rule: friendly, extensive, and it must say what happens either
    way rather than only naming the switch."""
    import inspect
    from ui.dialogs import settings_dialog
    src = inspect.getsource(settings_dialog)
    i = src.index("Show the Location Being Edited")
    body = src[i:i + 2000]
    assert "WHY YOU MIGHT WANT IT ON" in body
    assert "WHY YOU MIGHT WANT IT OFF" in body
    assert "runs/run2" in body, "a concrete example of the path it shows"


def test_closing_preferences_refreshes_the_bar(qapp):
    """#130 (Knut, beta.120): *"Preferences → General 'Show the location being
    edited' OFF still shows the 'Location being edited' label, path and whole
    row."*

    The reading side was right all along — ``_update_location`` consults the
    preference on every refresh. Nothing refreshed the bar when Preferences
    closed, though, so the change only appeared once the run selection happened
    to move. MainWindow refreshes a long list of widgets there; the bar simply
    was not on it.
    """
    import inspect
    from ui.main_window import MainWindow
    # Read the WHOLE method that opens Preferences, not a fixed slice of it.
    # A 3000-character window was fine until the method grew — adding one more
    # widget to the refresh list pushed the call being asserted out of view and
    # failed a test whose subject had not changed at all.
    src = None
    for name in ("_open_settings", "_open_settings_dialog"):
        fn = getattr(MainWindow, name, None)
        if fn is not None:
            src = inspect.getsource(fn)
            break
    assert src is not None and "SettingsDialog(" in src, \
        "could not find the method that opens Preferences"
    assert "_target_bar.refresh()" in src, \
        "closing Preferences must refresh the bar, or the setting appears dead"
