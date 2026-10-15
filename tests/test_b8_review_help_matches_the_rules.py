"""Review of 4.3.5 beta 8: the help says what the outlines now do.

Beta 8 changed two rules and left the help describing the old ones:

* SIMILAR PATCHES (Knut, #182 6196599132, §10.12): a patch of the same
  colour range, read in another strip, with its expected colour within the
  chart type's colour-neighbour radius and an error within the same-reading
  tolerance, for EACH test. The Measure tab's help and Preferences still said
  "expected colours less than ΔE 6 apart", and the neighbour check's help
  still said "Only its own re-read does that here: similar patches ... do not
  count for this check", which is no longer true.
* A SLIPPED STRIP (#210, Basti 2026-10-15): a reading from a strip the
  misalignment warning flagged confirms nothing and does not end an earlier
  re-read's confirmation. The help said a confirmation "ends only when you
  read that patch once more and the new reading is not outlined or gives a
  different colour", which a slipped reading is and does not end it.
"""
from __future__ import annotations

import inspect
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from workflow.patch_flags import FLAG_CONFIRMED, FLAG_RED, FlagJudge  # noqa: E402


def _src(mod) -> str:
    return inspect.getsource(mod)


def test_no_help_describes_the_retired_similar_patch_rule():
    from ui.dialogs import settings_dialog
    from ui.tabs import tab_measure
    for mod in (settings_dialog, tab_measure):
        src = _src(mod)
        assert "ΔE 6 apart" not in src, mod.__name__
        assert "Only its own re-read does that here" not in src, mod.__name__


def test_the_help_names_the_rule_knut_approved():
    from ui.dialogs import settings_dialog as sd
    from ui.tabs import tab_measure as tm
    assert "within the colour-neighbour radius" in sd.RED_AND_YELLOW_HELP
    assert "same-reading tolerance" in sd.RED_AND_YELLOW_HELP
    nb = sd.NEIGHBOUR_CHECK_HELP
    assert "similar patches are off in the same way" in nb
    assert "A learned colour range" in nb and "does not count" in nb
    assert "patches of its colour range" in _src(tm.TabMeasure)


def test_the_help_says_a_slipped_strip_does_not_end_a_confirmation():
    from ui.tabs import tab_measure as tm
    from ui.dialogs import settings_dialog as sd
    want = "“Warn me if a strip looks misaligned” flagged does not end it"
    assert want in tm._OVERLAY_TIP_LIMITS
    # Preferences carries the same paragraph inline, one translation
    assert want in _src(sd).replace('"\n            "', "")


def test_what_the_help_says_is_what_the_judge_does():
    """Confirmed by a re-read; a slipped reading of the same colour is red
    and ends nothing; the next ordinary reading of that colour is yellow
    again."""
    j = FlagJudge()
    exp, meas = (50.0, 0.0, 0.0), (50.0, 30.0, 0.0)
    j.judge("A1", exp, meas, 30.0, True, live=False, strip="A", limit=10.0)
    v = j.judge("A1", exp, meas, 30.0, True, strip="A", limit=10.0)
    assert v.flag is FLAG_CONFIRMED
    v = j.judge("A1", exp, meas, 30.0, True, strip="A", limit=10.0,
                slipped=True)
    assert v.flag is FLAG_RED
    v = j.judge("A1", exp, meas, 30.0, True, strip="A", limit=10.0)
    assert v.flag is FLAG_CONFIRMED


def test_the_closing_summary_ends_a_cut_list_with_one_stop():
    """"113 misreads corrected by a re-read: patches A9, …, B12…." (seen on
    screen in the review of beta 8): the "…" ends the sentence."""
    import types
    from ui.tabs.tab_measure import TabMeasure
    fixed = [f"A{i}" for i in range(1, 14)]
    stub = types.SimpleNamespace(
        _is_verification_run=lambda: False,
        _expected_is_predicted=lambda: False,
        neighbour_summary_facts=lambda: None,
        corrected_locs=lambda: fixed,
        _strips_read_again=[],
        _read_twice_was_active=lambda: False)
    text = TabMeasure._misread_summary(stub)
    assert "A10…" in text and "…." not in text and text.endswith("…")
