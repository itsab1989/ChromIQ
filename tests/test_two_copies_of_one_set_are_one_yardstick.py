"""Two stored copies ChromIQ itself changed are ONE yardstick, not two.

MEASURED, 2026-09-22, on screen: one project, two profile runs, both bound to
**ChromIQ default (recommended)**, neither showing "(edited)" and both printing
the same set name. A report over that project kept **11 measurements and left
11 out**, and said *"This report covers 11 of the 30 measurements recorded for
this project"* with nothing on the page explaining why.

The two copies differed only where ChromIQ had changed itself underneath the
user the day before:

* the two repeatability rows did not exist in the older copy, so they are
  simply absent from it;
* the grey balance pair is stored in the older copy as ``[1.5, "should"]`` and
  in the newer one as ``1.5``, because the bracket was retired from ChromIQ's
  own sets that day. Same number, different kind.

Knut ruled it the same day: *"I would say one and the same yardstick ... It
does not matter if one report uses a metric as recommendation ('should') and
the other report uses required ('shall'), those reports are separate."*

**THE POINT IS THAT THIS PREDICATE AND `is_edited` MUST AGREE.** The window
derives "(edited)" from one and decides which measurements share a document
from the other. A user told that two runs are not edited, who then watches half
their measurements vanish from the report, has been told two different things
about one fact. `db6030ec` fixed `is_edited`; this is its twin catching up.

Genuinely different SETS still separate, which is Knut's earlier ruling of
2026-09-16 and the reason the split exists at all.
"""
from __future__ import annotations

from workflow.compliance_sets import Limit, same_limits


def _copy(**rows) -> dict:
    return {rid: (Limit.value(v) if isinstance(v, (int, float))
                  else Limit.should(v[0]) if isinstance(v, tuple)
                  else v) for rid, v in rows.items()}


def test_a_row_the_older_copy_never_had_is_not_a_difference():
    """The repeatability pair, absent before 2026-09-21.

    MUTATION: drop the `if rid not in a or rid not in b: continue` line from
    `same_limits` and this goes red.
    """
    old = _copy(de00_avg=2.0, de00_max=5.0)
    new = _copy(de00_avg=2.0, de00_max=5.0,
                repeat_patches_de00_max=0.5,
                repeat_measurement_de00_max=0.5)
    assert same_limits(old, new), (
        "a row the older copy never defined is being read as an edit, which is "
        "what made every run bound by an earlier ChromIQ read '(edited)'"
    )


def test_should_versus_shall_is_not_a_difference():
    """Knut's sentence, as a test: same number, different kind.

    MUTATION: compare `kind` instead of `is_numeric` and the number, and this
    goes red.
    """
    recommended = _copy(grey_balance_neutral_ramp_avg=(1.5,))
    required = _copy(grey_balance_neutral_ramp_avg=1.5)
    assert same_limits(recommended, required)


def test_a_stored_question_mark_is_not_a_difference():
    """Nothing a user can do produces one; it is what the set gave that row."""
    unknown = {"de00_avg": Limit.unknown()}
    numeric = _copy(de00_avg=2.0)
    assert same_limits(unknown, numeric)
    assert same_limits(numeric, unknown)


def test_a_different_NUMBER_really_is_a_different_yardstick():
    """The half that must keep working, or the split stops protecting anyone.

    Without this the test above could be satisfied by a predicate that always
    returns True, which would mix measurements judged against genuinely
    different limits into one document.
    """
    loose = _copy(de00_avg=3.0)
    tight = _copy(de00_avg=2.0)
    assert not same_limits(loose, tight)


def test_a_row_present_on_both_sides_but_removed_on_one_is_a_difference():
    """`limits_to_json` writes a removed limit as null, so it is PRESENT and
    reads `none`. That is a user's own edit and must still separate."""
    kept = _copy(de00_avg=2.0)
    removed = {"de00_avg": Limit.none()}
    assert not same_limits(kept, removed)
