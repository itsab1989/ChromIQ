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
    """The approved M-REPLACE-PARTIAL names the option and says what ticking it
    does. Saying where the control lives was an addition of mine, and the model
    is Knut's — it is raised on the issue rather than added here."""
    _t, body = _msg(Ti3State.PARTIAL, held=38, expected=400)
    assert "Refine / resume existing measurement" in body
    assert "read only the patches that are still missing" in body


def test_a_complete_measurement_warns_about_the_profile():
    """The consequence a user would not think of: the profile beside it stops
    matching until it is built again."""
    title, body = _msg(Ti3State.COMPLETE, held=400, expected=400)
    assert "fully measured" in title
    assert "All 400 patches" in body
    assert "the profile in this run will no longer match" in body


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
    # A chart whose patch count cannot be read (defensive — Start is blocked
    # without a .ti2 since beta.128).
    (Ti3State.PARTIAL, {"held": 5, "expected": None}),
    # …and a measurement with nothing readable in it at all.
    (Ti3State.EMPTY, {"held": 0, "expected": 9}),
]


@pytest.mark.parametrize("state,kw", ALL_MESSAGES)
def test_every_message_explains_its_buttons(state, kw):
    """The approved catalogue spells the buttons out in M-TI3-MISMATCH; the
    other messages describe the choice in prose instead, which is the model's
    wording and therefore the wording that ships."""
    _t, body = _msg(state, **kw)
    assert "Starting" in body or "What each button does" in body


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
    """Defensive path: since beta.128 Start Measurement needs a `.ti2`, so a
    missing patch count means a chart file that cannot be parsed. It must never
    print a fraction with a missing denominator."""
    _t, body = _msg(Ti3State.PARTIAL, held=5, expected=None)
    assert "None" not in body and "{a}" not in body
    assert "cannot tell how many readings" in body


# ---- how it reaches the screen ------------------------------------------
def test_the_headline_is_bold_and_the_explanation_is_not():
    """These messages run to a screenful. All of it in QMessageBox's bold
    ``setText`` is a wall nobody reads, so the headline goes there and the
    explanation goes in ``setInformativeText`` at normal weight — the pattern
    the rest of the app already uses."""
    src = inspect.getsource(TabMeasure._confirm_replacing_measurement)
    assert "box.setText(title)" in src
    assert "setInformativeText" in src


class _Tab(__import__("PyQt6.QtWidgets", fromlist=["QWidget"]).QWidget):
    """A real QWidget (the window needs a parent) carrying the real methods.

    Everything about *choosing* and *rendering* the message is TabMeasure's own
    code; only the surroundings a measurement tab would provide are stubbed.
    """

    _confirm_replacing_measurement = TabMeasure._confirm_replacing_measurement
    _replace_message = TabMeasure._replace_message

    def __init__(self, ti3, ti1):
        super().__init__()
        self._ti3, self._ti1_path = ti3, ti1
        self._replace_warning_silenced = set()

    def _measurement_at_risk(self):     return self._ti3
    def _read_builds_on_existing(self):  return False
    def _replace_warning_scope(self):    return None


def _shown(monkeypatch, tmp_path, *, held, expected):
    """Drive the real window and return what it actually put on screen."""
    from PyQt6.QtWidgets import QMessageBox

    ti1 = tmp_path / "chart.ti1"
    ti1.write_text("x", encoding="utf-8")
    (tmp_path / "chart.ti2").write_text(
        "CGATS.17\nNUMBER_OF_SETS %d\nBEGIN_DATA\n%s\nEND_DATA\n"
        % (expected, "\n".join(f"P{i+1} 100 100 100" for i in range(expected))), encoding="utf-8")
    ti3 = tmp_path / "chart.ti3"
    ti3.write_text(
        "CTI3\nNUMBER_OF_SETS %d\nBEGIN_DATA\n%s\nEND_DATA\n"
        % (held, "\n".join(f"P{i+1} 100 100 100 50 50 50" for i in range(held))), encoding="utf-8")

    seen = {}

    def _capture(self):
        seen["title"] = self.text()
        seen["body"] = self.informativeText()
        return QMessageBox.StandardButton.Ok

    monkeypatch.setattr(QMessageBox, "exec", _capture)
    _Tab(ti3, ti1)._confirm_replacing_measurement()
    return seen


def test_the_window_shows_the_whole_message(qapp, monkeypatch, tmp_path):
    """What reaches the screen is the catalogue's body, from its first word.

    The test that stood here asserted the *opposite* — it required the body to
    be sliced by ``len(title)``, which was right when ``render()`` returned one
    string with the headline on the front and wrong from the moment it returned
    the two separately. Nothing noticed, and two messages shipped in beta.128
    with their opening sentence cut off: Knut got *". Starting now without …"*
    and *"ad, and this run's profile was built …"*. A test that reads the
    source cannot see that; this one reads the window.
    """
    shown = _shown(monkeypatch, tmp_path, held=38, expected=400)
    assert shown["title"] == "This run already holds part of a measurement"
    assert shown["body"].startswith("38 of the chart's 400 patches have been read")


def test_the_window_shows_the_whole_message_for_a_finished_one(
        qapp, monkeypatch, tmp_path):
    shown = _shown(monkeypatch, tmp_path, held=400, expected=400)
    assert shown["title"] == "This chart is fully measured"
    assert shown["body"].startswith("All 400 patches have been read")


def test_the_headline_is_not_repeated_in_the_body(qapp, monkeypatch, tmp_path):
    """The reason the slice existed in the first place — the headline must not
    appear twice on screen."""
    shown = _shown(monkeypatch, tmp_path, held=38, expected=400)
    assert shown["title"] not in shown["body"]
