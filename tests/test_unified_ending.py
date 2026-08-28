"""§T3 of the Unified Measurement Management specification.

``docs/design/unified_measurement_management.md`` §1, §1a, §2 and §S2: every way
a measurement can end reaches **one** window with the same three choices.

The fault this closes was found by generalising Knut's own question. He asked
for rows 10 and 11 of the ending table to cover "all failure messages… that also
contain Save Partial and Quit" — and the answer turned out to be that only three
of eight windows had it. The other five offered **Give Up**, which sends Esc:
quit without saving. They were honest about it, and they still asked the user to
choose between retrying and losing the session when saving was available all
along.
"""
from __future__ import annotations

import inspect
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from ui.tabs.tab_measure import TabMeasure      # noqa: E402

#: Every window that can end a session and used to offer only Give Up.
GIVE_UP_WINDOWS = ("Strip may be misaligned", "Wrong Strip Read",
                   "Unexpected Color Response", "Instrument Error")


# ---- one window, every route --------------------------------------------
def test_stop_asks_through_the_shared_window():
    src = inspect.getsource(TabMeasure._on_stop)
    assert "_confirm_end_of_session" in src
    assert "QMessageBox" not in src, "the window belongs to the shared method"


def test_the_done_key_asks_the_same_question():
    """Knut: *"These two ways of stopping should have same window."*"""
    whole = inspect.getsource(TabMeasure)
    i = whole.index("_confirm_end_of_session(self.END_DONE_KEY)")
    assert i > 0, "the 'd' key must route through the shared window"


def test_patches_still_unread_is_no_longer_a_separate_window():
    """Its Save Partial became Save and stop, and the patch it named in its
    title moved into the body of the shared window."""
    whole = inspect.getsource(TabMeasure)
    i = whole.index("_confirm_end_of_session(self.END_DONE_KEY)")
    j = whole.index('setWindowTitle(tr("Patches Still Unread"))')
    assert i < j, "the shared window must be reached before the old one"


def test_every_give_up_offers_to_save():
    """The five that did not. `Give Up` now asks first.

    The question is asked AFTER the window has closed, not from inside the
    button handler — otherwise it opens on top of the window it belongs to
    (Knut, beta.141). So each button records a pending decision and the caller
    resolves it once ``exec()`` has returned; both halves are asserted here,
    because either one alone would let the other rot.
    """
    whole = inspect.getsource(TabMeasure)
    assert whole.count("chosen[0] = self.GIVE_UP_PENDING") == 5, \
        "a Give Up button no longer defers its question"
    assert whole.count("self._resolve_give_up(chosen[0])") >= 5, \
        "a deferred Give Up is never resolved"
    assert "self._give_up_or_save()" in inspect.getsource(
        TabMeasure._resolve_give_up), "Give Up stopped offering to save"
    assert 'chosen[0] = "\\x1b"' not in whole, \
        "no window may still send Esc straight from a button"


def test_give_up_maps_the_three_answers_correctly():
    src = inspect.getsource(TabMeasure._give_up_or_save)
    assert "END_SAVE" in src, "saving is a protocol, not a keystroke"
    assert '"\\x1b"' in src, "discard is still Esc"
    assert '"\\r"' in src, "keep measuring means retry at a failure prompt"


def test_saving_is_not_sent_as_a_keystroke():
    """Which protocol saves depends on the engine — two 'q' for ChromIQ's
    reader, 'r'/'d'/'y' or 'd'/'y' for stock. A single key cannot express it."""
    src = inspect.getsource(TabMeasure._send_failure_choice)
    assert "send_save_partial_and_quit" in src
    assert "send_key" in src


def test_a_saved_ending_counts_as_an_ending():
    """The guard that decides whether measuring continues must not treat
    save-and-quit as "still going" just because it is not Esc."""
    whole = inspect.getsource(TabMeasure)
    assert whole.count('chosen[0] not in ("\\x1b", self.END_SAVE)') == 5
    assert 'if chosen[0] != "\\x1b":' not in whole


# ---- the window itself ---------------------------------------------------
def test_the_window_offers_exactly_three_choices():
    src = inspect.getsource(TabMeasure._confirm_end_of_session)
    for label in ("Save and stop", "Discard and stop", "Keep measuring"):
        assert label in src


def test_the_safe_choice_is_the_default():
    src = inspect.getsource(TabMeasure._confirm_end_of_session)
    assert "setDefaultButton(save)" in src


def test_it_says_how_many_are_at_stake():
    src = inspect.getsource(TabMeasure._confirm_end_of_session)
    assert "readings_this_session" in src
    assert "{n} patches" in src


def test_the_previous_measurement_is_only_mentioned_when_there_is_one():
    """Knut: the sentence assumed a measurement was already there.

    Asserted on the BEHAVIOUR, not on the spelling of the conditional: this
    used to pin the exact substring "if not had else", which broke the moment
    the branch grew a singular variant — while the rule it guards was still
    perfectly honoured. A rule worth a test is worth testing where it is true.
    """
    src = inspect.getsource(TabMeasure._confirm_end_of_session)
    assert "had = self._readings_before_session()" in src
    i = src.index("had = self._readings_before_session()")
    branch = src[i:i + 900]
    assert "if not had" in branch, "nothing checks whether there IS a previous one"
    # The sentence itself must sit on the far side of that check.
    assert branch.index("if not had") < branch.index("is put back exactly"), (
        "the previous-measurement sentence is built before anything asks "
        "whether there is a previous measurement")


def test_ending_with_nothing_read_still_says_so():
    """M-END-EMPTY. Silence after pressing Stop is what has to be interpreted."""
    src = inspect.getsource(TabMeasure._confirm_end_of_session)
    assert "Nothing was measured, so nothing was saved" in src
    i = src.index("has_unsaved_readings")
    assert "return \"discard\"" in src[i:i + 500]


# ---- the count it quotes -------------------------------------------------
def test_the_manager_counts_readings_as_they_happen():
    """The file cannot answer "how much is at stake" while the question is
    being asked: chartread holds its readings until it exits."""
    from workflow.measure_manager import MeasureManager
    src = inspect.getsource(MeasureManager)
    assert "_readings_count += 1" in src
    assert "def readings_this_session" in src


def test_the_count_resets_between_sessions():
    from workflow.measure_manager import MeasureManager
    src = inspect.getsource(MeasureManager)
    assert "self._readings_count = 0" in src
