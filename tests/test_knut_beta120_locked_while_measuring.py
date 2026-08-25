"""#130 (Knut, beta.120): the profile bar stayed live during a measurement.

    *"Serious bug: While measuring in measure tab: It is possible to change
    Profile run and Run type, as well as press duplicate. Also a strange thing
    If duplicate is done (which should not be available), the duplication
    completes and Profile run changes to last run (all while in measuring
    mode), then all colors disappear from window preview… Make all the Profile
    bar input boxes and Duplicate, as well as Tools menu icon and Preferences
    icon locked and greyed out while measuring… Help button can be active
    still."*

The machinery was half there. ``MeasurementTargetController.set_measuring`` had
existed since the Restore work and MainWindow already called it — but the bar
only ever consulted ``self._locked``, the *tab* lock used on Build Profile and
Check & Refine. So `_measuring` reached the Delete plan and nothing else, and
every control on the bar stayed clickable with an instrument mid-read.

The two reasons are kept apart on purpose: the tab lock says "this selection
isn't used here", measuring says "not right now". Either disables; they explain
themselves differently.
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtCore import QSettings                            # noqa: E402
from PyQt6.QtWidgets import QApplication                      # noqa: E402

from core.file_manager import FileManager                     # noqa: E402
from core.settings import AppSettings                         # noqa: E402
from ui.measurement_target_bar import (MeasurementTargetBar,  # noqa: E402
                                       MeasurementTargetController)

#: Every control on the bar that can change which chart is being worked on.
BAR_CONTROLS = ("_run_combo", "_type_combo", "_verify_combo",
                "_duplicate_btn", "_restore_btn", "_delete_btn")


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def bar(qapp, tmp_path):
    """A bar over a real project, so the controls are genuinely enabled to
    begin with — a bar with no project greys everything anyway and would prove
    nothing."""
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    root = tmp_path / "ChromIQ"
    root.mkdir(exist_ok=True)
    s.set("custom_output_path", str(root))
    fm = FileManager(s)
    fm.set_target_name("Demo")
    fm.project()                      # create-or-load
    ctl = MeasurementTargetController(fm)
    b = MeasurementTargetBar(ctl, show_verification=True)
    qapp.processEvents()
    return b, ctl


def test_the_selection_boxes_are_live_before_a_measurement(bar):
    """The premise. If these were already dead the rest would prove nothing."""
    b, _ctl = bar
    assert b._run_combo.isEnabled()
    assert b._type_combo.isEnabled()


@pytest.mark.parametrize("name", BAR_CONTROLS)
def test_every_bar_control_goes_dead_while_measuring(bar, qapp, name):
    b, ctl = bar
    ctl.set_measuring(True)
    qapp.processEvents()
    assert not getattr(b, name).isEnabled(), f"{name} stayed clickable"


def test_duplicate_in_particular(bar, qapp):
    """The one that actually caused damage: it completed, moved the selection
    to the new run and emptied the preview mid-read."""
    b, ctl = bar
    ctl.set_measuring(True)
    qapp.processEvents()
    assert not b._duplicate_btn.isEnabled()


def test_they_all_come_back_afterwards(bar, qapp):
    b, ctl = bar
    ctl.set_measuring(True)
    qapp.processEvents()
    ctl.set_measuring(False)
    qapp.processEvents()
    assert b._run_combo.isEnabled() and b._type_combo.isEnabled()


def test_the_reason_given_is_the_measurement_not_the_tab(bar, qapp):
    """A control greyed for the wrong reason is worse than one greyed for
    none: the tab-lock note tells you to go and change it on another tab,
    which during a measurement is simply wrong."""
    b, ctl = bar
    ctl.set_measuring(True)
    qapp.processEvents()
    tip = b._run_combo.toolTip()
    assert "Not while a measurement is running" in tip
    assert "Build Profile" not in tip, "that is the tab-lock note, not this one"


def test_the_note_says_the_selection_is_kept(bar, qapp):
    """Otherwise "everything is greyed" reads as "I have lost my place".

    It opens with the phrase the app already uses for this state, so every
    greyed control reads alike — Knut: *"All of them should have the same
    tool-tip … (as others do)."*"""
    b, ctl = bar
    ctl.set_measuring(True)
    qapp.processEvents()
    assert "Your place is kept" in b._run_combo.toolTip()


def test_the_tooltip_is_restored_not_overwritten(bar, qapp):
    b, ctl = bar
    before = b._run_combo.toolTip()
    ctl.set_measuring(True)
    qapp.processEvents()
    ctl.set_measuring(False)
    qapp.processEvents()
    assert b._run_combo.toolTip() == before


# ---- the masthead: Tools and Preferences, but not Help -------------------
def test_tools_and_preferences_are_locked_but_help_is_not(qapp):
    from ui.masthead_header import MastheadHeader
    m = MastheadHeader()
    # `set_availability` replaced `set_measuring` in #164 — one source of truth
    # for the whole masthead, and a profile build now locks it the same way.
    m.set_availability(MastheadHeader.BUSY_MEASURING, has_project=True)
    assert not m._tools_btn.isEnabled(), "Tools can rewrite files under the run"
    assert not m._btn.isEnabled(), "Preferences can switch the reading engine"
    assert not m._load_project_btn.isEnabled()
    assert not m._load_ti2_btn.isEnabled()
    help_btn = getattr(m, "_help_btn", None)
    if help_btn is not None:
        assert help_btn.isEnabled(), 'Knut: "Help button can be active still"'
    m.set_availability(None, has_project=True)
    assert m._tools_btn.isEnabled() and m._btn.isEnabled()


def test_a_profile_build_locks_the_masthead_the_same_way(qapp):
    """Basti, #164: *"should be locked the same way"*. colprof writes into the
    loaded run, so opening another project mid-build is no safer than doing it
    mid-measurement."""
    from ui.masthead_header import MastheadHeader
    m = MastheadHeader()
    m.set_availability(MastheadHeader.BUSY_BUILDING, has_project=True)
    for name in ("_tools_btn", "_btn", "_load_project_btn", "_load_ti2_btn",
                 "_close_project_btn"):
        assert not getattr(m, name).isEnabled(), f"{name} stayed live in a build"
    help_btn = getattr(m, "_help_btn", None)
    if help_btn is not None:
        assert help_btn.isEnabled(), 'Knut: "Help button can be active still"'
    # …and the reason on screen must name the build, not a measurement.
    assert "profile is being built" in m._tools_btn.toolTip().lower()


def test_the_main_window_actually_calls_it(qapp):
    """The bar and masthead can be perfect and still never be told."""
    import inspect
    from ui.main_window import MainWindow
    src = inspect.getsource(MainWindow._on_measurement_active)
    assert "_refresh_masthead_availability" in src
    refresh = inspect.getsource(MainWindow._refresh_masthead_availability)
    assert "set_availability" in refresh and "_masthead" in refresh
