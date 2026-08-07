"""One switch hides the log panel on every tab (Basti, 2026-08-07).

The panels are found by object name rather than listed, because there are six
of them and Build Profile alone has three — one per module. A hand-written list
would miss the next one added, and the symptom would be a log that stubbornly
stays visible with no clue why.
"""
import inspect

import pytest

from PyQt6.QtWidgets import QPlainTextEdit


def test_the_setting_exists_and_defaults_to_showing_the_log():
    """Opt-out, not opt-in: the log is where a failure explains itself."""
    from core.settings import DEFAULTS
    assert DEFAULTS["hide_log_output"] is False


def test_it_finds_the_panels_by_name_not_by_a_list():
    import ui.main_window as mw
    src = inspect.getsource(mw.MainWindow._apply_log_visibility)
    assert 'findChildren(QPlainTextEdit, "log")' in src, (
        "the panels are listed by hand, so the next tab's log will be missed"
    )
    for tab in ("_tab_chart", "_tab_measure", "_tab_profile", "_tab_check"):
        assert tab not in src, f"{tab} is named explicitly — that list will rot"


def test_a_wrapper_that_only_holds_a_log_is_hidden_too():
    """Otherwise the Measure tab keeps a blank strip where its margins were."""
    import ui.main_window as mw
    src = inspect.getsource(mw.MainWindow._apply_log_visibility)
    assert '"log_container"' in src
    import ui.tabs.tab_measure as tm
    assert 'setObjectName("log_container")' in inspect.getsource(tm.TabMeasure)


def test_it_is_applied_at_startup_and_when_preferences_close():
    import ui.main_window as mw
    src = inspect.getsource(mw.MainWindow)
    assert src.count("self._apply_log_visibility()") >= 2, (
        "the preference is applied in only one place; it must hold both at "
        "startup and when Preferences is closed"
    )


def test_preferences_offers_it_with_a_tooltip():
    import ui.dialogs.settings_dialog as sd
    src = inspect.getsource(sd)
    assert "_hide_log_check" in src
    assert 'tr("Hide the Log Panel")' in src, "the switch has no tooltip"
    assert 's.set("hide_log_output"' in src, "the switch is never saved"
    assert 's.get("hide_log_output"' in src, "the switch never loads its state"


def test_the_tooltip_says_what_is_lost_and_what_is_not():
    """Friendly and complete, per the standing rule for user-facing text."""
    import ui.dialogs.settings_dialog as sd
    src = inspect.getsource(sd)
    body = src[src.index('tr("Hide the Log Panel")'):][:2600]
    for phrase in ("WHY YOU MIGHT WANT IT ON", "WHY YOU MIGHT WANT IT OFF",
                   "written to disk", "Print Chart", "Default:"):
        assert phrase in body, f"the tooltip never mentions {phrase!r}"


# The behaviour itself is NOT tested here: constructing a MainWindow under
# QT_QPA_PLATFORM=offscreen segfaults, and a crashed worker takes the gate with
# it. It is driven on screen instead — scripts are in the scratchpad, and the
# result is recorded on the issue. The checks above hold the wiring that the
# on-screen run proves.
