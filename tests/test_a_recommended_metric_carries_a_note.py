"""A limit the set RECOMMENDS is reported like any other, and says so in a note.

B8-570. Knut's ruling of 2026-09-21 has two halves and they have to arrive
together:

* **the word goes.** *"it might be better to standardise on all metrics being
  tested against a threshold shows as FAIL or PASS (always, also for the
  standards), and the COND term is retired, all tests that fail or pass are
  handled equally"*;
* **a note takes its place.** *"there should be a note associated with the
  metric its self, like a reference number at the end of the metric label-name,
  pointing to a note below the table in the Report Limits window (and in the
  report text also a number on the metric name, pointing to a note in the report
  text)."*

**AND THE AGGREGATION DOES NOT CHANGE.** His first message asked for a failed
recommendation to leave the overall result PASS. He withdrew it nine minutes
later: *"I recommend that all thresholds tested against are treated the same, so
there is no need to have special handling of the results of a metric with
'should' … If the test is applied the report shall show the result as is, and
the overall result follows as normal."* So a failed recommendation sinks a
column exactly as any other failure does, and
`test_a_failed_recommendation_sinks_the_column_like_any_other_failure` is what
stops the withdrawn version being built by accident later.

**WHY EVERY TEST HERE BUILDS ITS OWN SHOULD-LIMIT.** The same ruling's point 5
took the last recommendation out of ChromIQ's own sets, so nothing this app
ships marks a row "should" and a suite that used the shipped sets would exercise
none of this. The one remaining source is a licence holder's own values file, or
a row marked in an editable Custom column; these tests use the first, through
the real loader. No figure from any standard appears here: 3.0 is ChromIQ
default's own maximum.

MUTATIONS PROVEN TO LAND (each reverted, `__pycache__` purged, re-run):
  1. `row_verdict`: `return COND if limit.is_should else FAIL`
     → test_a_recommendation_that_is_exceeded_reads_FAIL
  2. `_row_notes`: drop the `is_should` clause
     → test_a_recommended_row_carries_the_note_whatever_it_scored
  3. `_row_notes`: attach the note only when the row FAILED
     → the same test's passing half
"""
from __future__ import annotations

import json
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from workflow import compliance_sets as cs                    # noqa: E402
from workflow import measurement_report as mr                 # noqa: E402
from workflow.compliance_sets import (COND, FAIL, INFO, N_A,  # noqa: E402
                                      PASS, Limit, row_verdict,
                                      set_summary)

RID = "grey_balance_neutral_ramp_max"


@pytest.fixture
def a_marked_set(tmp_path, monkeypatch):
    """Custom ISO 12647-7 with ONE row marked a recommendation at 3.0.

    Written in the file's own `[number, "should"]` form and read back through
    the shipping loader, so what is exercised is the path a licence holder's
    file takes and not a fixture that re-implements it.
    """
    f = tmp_path / "iso12647.json"
    f.write_text(json.dumps({"iso_12647_7": {RID: [3.0, "should"]},
                             "iso_12647_8": {}}), encoding="utf-8")
    monkeypatch.setenv(cs.ISO_DATA_ENV, str(f))
    cs.reset_iso_cache()
    yield "custom_iso_12647_7"
    cs.reset_iso_cache()


# ------------------------------------------------------------------ the word
def test_a_recommendation_that_is_exceeded_reads_FAIL():
    should = Limit.should(3.0)
    assert row_verdict(should, 4.4, True) == FAIL
    assert row_verdict(should, 2.0, True) == PASS
    # every other case is untouched by the ruling
    assert row_verdict(should, None, True) == N_A
    assert row_verdict(should, 4.4, False) == INFO


def test_no_limit_of_any_kind_can_produce_COND_any_more():
    """COND survives as an OVERALL word and cannot come out of a row.

    A saved report may still hold it, which is why the token is not deleted;
    nothing computes it.
    """
    words = set()
    for lim in (Limit.value(2.0), Limit.should(2.0), Limit.none(),
                Limit.unknown(), Limit.unmeasurable()):
        for value in (None, 1.0, 9.0):
            for graded in (True, False):
                words.add(row_verdict(lim, value, graded))
    assert COND not in words, sorted(w for w in words if w)


# ------------------------------------------------------------------ the note
def test_a_recommended_row_carries_the_note_whatever_it_scored(a_marked_set):
    """The note says what the STANDARD calls the metric, not what the number did.

    So it is attached to a passing row as well as a failing one. A note that
    appeared only on failures would read as an excuse for the failure, which is
    precisely the reading Knut withdrew.
    """
    lim = cs.factory_limits(a_marked_set)
    assert lim[RID].is_should, "the fixture did not take"

    for value in (4.4, 1.0):
        word = row_verdict(lim[RID], value, True)
        assert word in (PASS, FAIL), word
        notes = mr._row_notes({"value": value}, lim[RID])
        assert mr.NOTE_RECOMMENDED_LIMIT in notes, (value, word, notes)
    # …and an ordinary limit carries no such note
    assert mr.NOTE_RECOMMENDED_LIMIT not in mr._row_notes({}, Limit.value(3.0))
    # …and the measurement's OWN notes are kept, not replaced
    kept = mr._row_notes({"notes": [mr.NOTE_PRINTING_UNRECORDED]}, lim[RID])
    assert kept == [mr.NOTE_PRINTING_UNRECORDED, mr.NOTE_RECOMMENDED_LIMIT]


def test_the_note_is_numbered_and_the_number_is_shared(a_marked_set):
    """Knut asked for "a number on the metric name, pointing to a note in the
    report text". One function computes the numbering and the cell and the list
    both ask it, so the marker and the item cannot disagree."""
    rows = [{"row_id": RID, "word": FAIL,
             "notes": [mr.NOTE_RECOMMENDED_LIMIT]},
            {"row_id": "all_de00_avg", "word": PASS, "notes": []}]
    numbering = mr.numbered_notes(rows)
    assert numbering == [(1, mr.NOTE_RECOMMENDED_LIMIT, [RID])]
    assert mr.note_numbers_for(rows[0], numbering) == [1]
    assert mr.note_numbers_for(rows[1], numbering) == []
    assert mr.note_label(1) == "1)"


def test_the_note_text_is_one_catalogue_entry_rendered_in_both_places():
    """The Report limits window and the report must say the SAME thing.

    Knut asked for the note in both, so two hand-written copies would be two
    documents that drift. Both renderers call the catalogue.
    """
    from ui.dialogs.measurement_report_dialog import _recommended_limit_note
    from ui.dialogs.thresholds_dialog import _recommended_note_text
    from workflow.measurement_messages import M_LIMIT_RECOMMENDED

    a, b = _recommended_limit_note(), _recommended_note_text()
    assert a == b and a
    assert "recommended rather than required" in a
    assert "may be applied optionally" in a
    # …AND IT DOES NOT PROMISE WHAT KNUT WITHDREW. The first draft of this note
    # ended "but does not affect the overall result of the ISO 12647
    # verification"; he struck it, and a note that said so would now be false
    # of the code as well as against the ruling.
    low = a.lower()
    for forbidden in ("does not affect", "overall result", "excluded",
                      "still pass", "ignored"):
        assert forbidden not in low, (forbidden, a)
    assert not M_LIMIT_RECOMMENDED.approved, \
        "the wording has not been reviewed; it belongs in §M-PROPOSED"


# ------------------------------------------------------------ the aggregation
def test_a_failed_recommendation_sinks_the_column_like_any_other_failure():
    """THE TRAP IN THIS RULING, pinned so the withdrawn version cannot return.

    At 00:46 local Knut asked for a failed recommendation to leave the overall
    result PASS. At 00:55 he withdrew it: *"If the test is applied the report
    shall show the result as is, and the overall result follows as normal."*

    MUTATION: make `set_summary` skip should-rows when counting failures and
    this goes red.
    """
    sh, v = Limit.should(3.0), Limit.value(2.0)
    s = set_summary([(v, PASS), (sh, FAIL)], set_is_iso=False, graded=True)
    assert s.word == FAIL, "a failed recommendation must sink the column"
    assert s.failed == 1
    # identical to the same shape with an ordinary limit: no special handling
    ordinary = set_summary([(v, PASS), (v, FAIL)], set_is_iso=False, graded=True)
    assert (s.word, s.failed, s.checked, s.total) == (
        ordinary.word, ordinary.failed, ordinary.checked, ordinary.total)


def test_a_recommendation_that_passes_leaves_the_column_PASS():
    sh, v = Limit.should(3.0), Limit.value(2.0)
    s = set_summary([(v, PASS), (sh, PASS)], set_is_iso=False, graded=True)
    assert s.word == PASS and s.failed == 0


# ------------------------------------------------- reports saved before today
def test_a_stored_COND_verdict_is_still_a_word_the_app_defines():
    """An old report must open and read sensibly.

    COND stays in `WORDS` and in `word_label` for exactly this: a report saved
    before 2026-09-21 carries the token on rows, and the reader of such a
    report is owed the word explained rather than a blank cell or a raw token.
    The verdict itself is NOT rewritten -- a saved verdict is the record §5
    keeps comparable across dates.
    """
    assert COND in cs.WORDS
    assert cs.word_label(COND)
    # and the report guide still explains it, naming it as an Overall word and
    # as something an old report may show on a row. Read off the SOURCE, the
    # way every other guide check in this suite does: the bullet is built
    # inside a method that needs a whole report to call.
    import inspect

    from ui.dialogs import measurement_report_dialog as mrd
    guide = inspect.getsource(mrd)
    assert "COND (short for conditional)" in guide
    assert "Rows do not use this word" in guide, \
        "the guide must say the word is not a row verdict any more"
    # K18 (Knut, 2026-09-23) OVERRULED the history this used to require: *"A
    # report text shall never explain something in the past, only the current
    # functionality ... Only explain what the meaning of COND is and how to
    # understand it when it occurs."* The report may reach a customer, who
    # has no use for which ChromIQ version wrote it.
    assert "saved before ChromIQ 4.3.0" not in guide, \
        "the guide explains ChromIQ's history to a report's reader"
    # THE CLAUSE THAT WAS TRUE UNTIL TODAY AND IS NOW THE ONE THING IT CANNOT
    # MEAN. It read "For a row it means the row is a recommendation rather than
    # a requirement and the value is over it."
    assert "For a row it means the row" not in guide
