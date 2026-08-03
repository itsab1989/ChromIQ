"""§T3 for §5 — starting a measurement over an existing one.

``docs/design/unified_measurement_management.md`` §5: three different messages,
chosen by what the measurement file actually holds. The numbers are the point —
"a measurement" tells the user nothing they can weigh; "38 of 400 patches" does.

Knut's ruling on the resume setting is pinned here too: *"the Resume setting
should be as the user set it before pressing start measurement, and the message
should not show a separate Resume checkbox to change the users choice."*
"""
from __future__ import annotations

import inspect
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from ui.tabs.tab_measure import TabMeasure                      # noqa: E402
from workflow.measurement_state import Ti3Facts, Ti3State       # noqa: E402


def _msg(state, held=None, expected=None, claimed=None):
    facts = Ti3Facts(state, claimed=claimed, held=held, expected=expected)
    return TabMeasure._replace_message(None, facts, "/tmp/x.ti3")


# ---- the three messages --------------------------------------------------
def test_a_partial_measurement_says_how_far_it_got():
    title, body = _msg(Ti3State.PARTIAL, held=38, expected=400)
    assert "part of a measurement" in title
    assert "38 of the chart's 400 patches" in body


def test_a_partial_measurement_points_at_resume():
    _t, body = _msg(Ti3State.PARTIAL, held=38, expected=400)
    assert "Refine / resume existing measurement" in body
    assert "options panel" in body, "say where the option is, not just its name"


def test_a_complete_measurement_warns_about_the_profile():
    """The consequence a user would not think of: the profile beside it stops
    matching until it is built again."""
    title, body = _msg(Ti3State.COMPLETE, held=400, expected=400)
    assert "fully measured" in title
    assert "All 400 patches" in body
    assert "profile built from it will no longer match" in body


def test_a_mismatch_refuses_to_resume_and_says_why():
    title, body = _msg(Ti3State.MISMATCHED, held=9, expected=400)
    assert "do not match" in title
    assert "9 readings" in body and "400 patches" in body
    assert "Resuming is not offered" in body
    assert "may not be the ones on your paper" in body


def test_a_mismatch_does_not_claim_to_know_the_cause():
    """ChromIQ can see two numbers disagree; it cannot see why."""
    _t, body = _msg(Ti3State.MISMATCHED, held=9, expected=400)
    assert "cannot tell which of the two is the wrong one" in body
    assert "is damaged" not in body, "that would be a verdict, not a finding"


def test_a_file_that_disagrees_with_itself_says_so_as_well():
    _t, body = _msg(Ti3State.MISMATCHED, held=9, expected=400, claimed=12)
    assert "claims 12 readings" in body
    assert "may be damaged" in body, "cautious: 'may', not 'is'"


def test_a_file_that_only_disagrees_with_the_chart_does_not(tmp_path):
    _t, body = _msg(Ti3State.MISMATCHED, held=9, expected=400, claimed=9)
    assert "may be damaged" not in body


def test_the_mismatch_names_where_the_stored_chart_is():
    """Knut: only facts. There is exactly one copy and it is in chart/."""
    _t, body = _msg(Ti3State.MISMATCHED, held=9, expected=400)
    assert "“chart” folder" in body
    assert "Restore Used Chart" in body


# ---- Knut's ruling on the resume setting --------------------------------
def test_no_message_offers_a_resume_checkbox():
    src = inspect.getsource(TabMeasure._replace_message)
    assert "QCheckBox" not in src
    for state, kw in ((Ti3State.PARTIAL, {"held": 5, "expected": 9}),
                      (Ti3State.COMPLETE, {"held": 9, "expected": 9}),
                      (Ti3State.MISMATCHED, {"held": 5, "expected": 9})):
        _t, body = _msg(state, **kw)
        assert "Tick this to resume" not in body


def test_the_reason_is_recorded_where_someone_would_change_it_back():
    src = inspect.getsource(TabMeasure._confirm_replacing_measurement)
    assert "should not show a separate" in src or "Resume is deliberately NOT" in src


# ---- every message keeps the house rules --------------------------------
ALL_MESSAGES = [
    (Ti3State.PARTIAL, {"held": 5, "expected": 9}),
    (Ti3State.COMPLETE, {"held": 9, "expected": 9}),
    (Ti3State.MISMATCHED, {"held": 5, "expected": 9}),
    # A measurement with readings but no chart to count patches from…
    (Ti3State.PARTIAL, {"held": 5, "expected": None}),
    # …and one with nothing readable in it at all.
    (Ti3State.EMPTY, {"held": 0, "expected": 9}),
]


@pytest.mark.parametrize("state,kw", ALL_MESSAGES)
def test_every_message_explains_its_buttons(state, kw):
    _t, body = _msg(state, **kw)
    assert "What each button does" in body
    assert "Cancel — nothing is measured and nothing is written" in body


@pytest.mark.parametrize("state,kw", ALL_MESSAGES)
def test_every_message_says_nothing_is_deleted(state, kw):
    """The rule the whole specification serves: archive, never delete."""
    _t, body = _msg(state, **kw)
    assert "“old” folder" in body


@pytest.mark.parametrize("state,kw", ALL_MESSAGES)
def test_no_placeholder_reaches_the_screen(state, kw):
    title, body = _msg(state, **kw)
    for text in (title, body):
        assert "{" not in text and "}" not in text


def test_an_unknown_patch_count_does_not_print_none():
    _t, body = _msg(Ti3State.PARTIAL, held=5, expected=None)
    assert "None" not in body


# ---- how it reaches the screen ------------------------------------------
def test_the_headline_is_bold_and_the_explanation_is_not():
    """These messages run to a screenful. All of it in QMessageBox's bold
    ``setText`` is a wall nobody reads, so the headline goes there and the
    explanation goes in ``setInformativeText`` at normal weight — the pattern
    the rest of the app already uses."""
    src = inspect.getsource(TabMeasure._confirm_replacing_measurement)
    assert "box.setText(title)" in src
    assert "setInformativeText" in src


def test_the_headline_is_not_printed_twice():
    src = inspect.getsource(TabMeasure._confirm_replacing_measurement)
    assert "body[len(title):]" in src, "the body repeats its own title"
