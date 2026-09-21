"""**FOUR FALSE USER-VISIBLE SENTENCES, FOUND BY CHALLENGE ROUND 32.**

Each one was true when it was written and was made false by a change that did
not come back for it. They are different faults with one shape: a sentence that
outlived the behaviour it describes.

1. **The one-page summary claimed a completeness it did not have.** §15 made
   two REQUIRED rows exempt from a column's completeness arithmetic so a first
   measurement would not be demoted for a question one sheet cannot answer.
   The arithmetic was told; the PASS sentence was not. Driven end to end, the
   verdict read ``overall PASS, checked 7, total 9, not_computed 2`` beside
   *"Every value this limit set requires was checked and is within its limit."*
   It contradicted itself inside one dict, on a page (report type T1) that
   carries no row table and so could not correct it, and it was written to
   disk with every report saved.

   **KNUT THEN WIDENED WHEN THAT CAN HAPPEN, 2026-09-21, amending §15.5:**
   *"Not Applicable must not be counted as a fail, so the overall verdict
   should show PASS, not COND, if all others pass. I say, a metric that is not
   applicable should not have verdict conditional because COND does not
   indicate which of the verdicts cause the COND. I would say that the N-A for
   the first measurement instead should have a super-script number, pointing
   to a note, where the note explains why it is N-A for the first measurement.
   When all other metrics PASS, that N-A is not applicable, thus not relevant
   for the verdict, thus overall verdict becomes PASS (or FAIL if some metric
   fails)."* So the rule is general and the carve-out is gone: an N-A row of
   ANY kind reaches PASS, which makes the false sentence reachable far more
   often, not less, and makes "none of them was required" untrue as an
   explanation. Both halves of his ruling are checked below.

2. **The Report type help still named a removed control and promised a removed
   freeze.** B8-590 took away "Show all measurement runs" and the freeze in the
   same commit, reset the list's own tooltip, and missed this string. It is in
   all thirteen catalogues and German is translated, so German readers were
   given a false sentence in German.

3. **The window and the document disagreed about the same chart.**
   ``_mismatch_text`` was corrected to leave out the rows whose population may
   honestly not exist; ``_not_computed``, which feeds the same claim into the
   report BODY and therefore into every PDF, was not. Every clean first
   verification ended under "Not computed on this chart" naming "The same
   chart measured again", which is not a property of a chart.

4. **Four help-card sentences still taught COND as a row word.** Knut retired
   it as one on 2026-09-21; ``row_verdict`` has returned PASS or FAIL ever
   since. The report window's own guide was rewritten that day and the Getting
   Started card was not.

Why the COND guard below is a REGISTER and not a detector: the four false
sentences and the true ones that survive them are not separable by any rule
over the prose. *"a required row your chart could not answer makes it COND"*
appears verbatim in one of the false strings AND in the corrected one, because
that clause was never the fault. A detector fitted to the four known sentences
would be fitted to those four sentences and to nothing else. So the code-side
truth is pinned against the code (``test_a_row_can_never_read_cond`` and
``test_a_missed_recommendation_reads_fail_not_cond``), and the prose is pinned
by a complete register: every user-facing string that names COND, with the
reason it is allowed to. A new one fails; an edit to a pinned one fails.
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))


# =========================================================================
# 1. The PASS sentence and the arithmetic beside it
# =========================================================================
def _bearing(n_pass: int, na_ids=(), should_na=0):
    from workflow.compliance_sets import Limit, N_A, PASS
    rows = [(Limit.value(2.0), PASS, f"row{i}") for i in range(n_pass)]
    rows += [(Limit.value(2.0), N_A, rid) for rid in na_ids]
    rows += [(Limit.should(2.0), N_A, f"should{i}") for i in range(should_na)]
    return rows


def test_a_pass_never_claims_everything_was_checked_when_it_was_not():
    """**THE FAULT, IN ONE ASSERT.** Seven checked of nine, two not computed,
    and the sentence beside it said every required value was checked."""
    from workflow.compliance_sets import (PASS, POPULATION_MAY_BE_ABSENT,
                                          set_summary, summary_text)
    s = set_summary(_bearing(7, sorted(POPULATION_MAY_BE_ABSENT)),
                    set_is_iso=False, graded=True)
    assert s.word == PASS, "the arithmetic itself is §15 and is not what changed"
    assert (s.checked, s.total, s.not_computed) == (7, 9, 2), s
    said = summary_text(s)
    assert "Every value this limit set requires was checked" not in said, said
    # and it says the true thing instead: the numbers, and that nothing left
    # unchecked was required of this chart.
    assert "7 of 9 values checked" in said, said
    assert "could not be worked out" in said, said
    assert "is not counted as a failure" in said, said


def test_the_unqualified_pass_sentence_survives_where_it_is_true():
    """It is not deleted. A column with nothing left over still gets it."""
    from workflow.compliance_sets import PASS, set_summary, summary_text
    s = set_summary(_bearing(9), set_is_iso=False, graded=True)
    assert s.word == PASS and s.not_computed == 0
    assert summary_text(s) == (
        "Every value this limit set requires was checked and is within its "
        "limit.")


def test_one_left_over_is_said_in_the_singular():
    """Count-bearing messages get singular and plural in full, never "(s)"
    (CLAUDE.md). One row not computed must not read "The other 1"."""
    from workflow.compliance_sets import set_summary, summary_text
    s = set_summary(_bearing(8, ["repeat_measurement_de00_max"]),
                    set_is_iso=False, graded=True)
    assert s.not_computed == 1
    said = summary_text(s)
    assert "The one other value" in said, said
    assert "The other 1" not in said, said


def test_a_should_row_left_over_is_covered_by_the_same_sentence():
    """A `should` row reading N-A never demoted a column either, so it lands
    on the same PASS with `not_computed` above zero."""
    from workflow.compliance_sets import PASS, set_summary, summary_text
    s = set_summary(_bearing(8, should_na=1), set_is_iso=False, graded=True)
    assert s.word == PASS and s.not_computed == 1
    assert "Every value this limit set requires was checked" not in summary_text(s)


#: The N-A row ids an ORDINARY chart can produce, one per distinct cause, and
#: the reason each carries. Not a sample: `test_an_n_a_never_demotes_whatever`
#: sweeps it and `test_the_population_can_express_the_movement` proves each of
#: these really did demote a column before Knut's ruling, so a null result
#: cannot come from a population that could not show the difference.
N_A_ROWS_BY_CAUSE = [
    ("grey_de00_avg", False),        # a required row: no grey ramp on the chart
    ("grey_de00_max", False),
    ("paper_white_de00", False),     # a required row: the chart has no white
    ("strip_de00_avg", False),       # a required row: no control strip declared
    ("repeat_patches_de00_max", False),      # the chart repeats no colour
    ("repeat_measurement_de00_max", False),  # first measurement of this chart
    ("best95_de00_avg", True),       # a recommended row, which never demoted
]


@pytest.mark.parametrize("rid,is_should", N_A_ROWS_BY_CAUSE)
def test_an_n_a_never_demotes_whatever_row_it_is_on(rid, is_should):
    """**KNUT'S RULE IS GENERAL AND THIS IS THE POPULATION IT IS GENERAL
    OVER.** What shipped was a frozenset naming two repeatability rows; his
    ruling is about any metric that is N-A. A required grey row on a chart
    with no grey ramp is the case that used to read COND and now reads PASS.
    """
    from workflow.compliance_sets import Limit, N_A, PASS, set_summary
    lim = Limit.should(2.0) if is_should else Limit.value(2.0)
    rows = [(Limit.value(2.0), PASS, f"row{i}") for i in range(4)]
    rows.append((lim, N_A, rid))
    s = set_summary(rows, set_is_iso=False, graded=True)
    assert s.word == PASS, (
        f"an N-A on {rid} demoted a clean column to {s.word}, which Knut "
        "ruled out on 2026-09-21")
    assert s.not_computed == 1


@pytest.mark.parametrize("rid,is_should", N_A_ROWS_BY_CAUSE)
def test_the_population_can_express_the_movement(rid, is_should):
    """**A CLEAN DIFF OVER A POPULATION THAT CANNOT SHOW THE FAULT IS NOT
    EVIDENCE.** Every row above reads PASS after the change. That is worth
    nothing unless these rows can move a verdict at all: a row the arithmetic
    never looks at would pass the test above for the wrong reason.

    So the same row is fed in with FAIL instead of N-A and must take the
    column down with it. Measured against the shipping `set_summary`, not
    against a re-implementation of the rule it used to apply: a fake that
    re-implements the code validates itself.
    """
    from workflow.compliance_sets import FAIL, Limit, PASS, set_summary
    lim = Limit.should(2.0) if is_should else Limit.value(2.0)
    rows = [(Limit.value(2.0), PASS, f"row{i}") for i in range(4)]
    assert set_summary(rows, set_is_iso=False, graded=True).word == PASS
    rows.append((lim, FAIL, rid))
    s = set_summary(rows, set_is_iso=False, graded=True)
    assert s.word == FAIL, (
        f"{rid} cannot move a column's word even when it FAILS, so its N-A "
        "reading PASS proves nothing about the rule")
    assert s.failed == 1


def test_the_exempt_set_no_longer_touches_any_verdict():
    """`POPULATION_MAY_BE_ABSENT` survives, and not as a verdict rule.

    Knut's ruling removed the arithmetic it was carved out of. What it still
    decides is which rows may appear under a message that promises something
    about the CHART, because nothing can be added to a chart to answer whether
    it has been measured twice. `set_summary` must not read it at all.
    """
    import inspect
    from workflow import compliance_sets as cs
    src = inspect.getsource(cs.set_summary)
    # the BODY, not the docstring: the docstring records what the rule used to
    # be and names the set for the reader who goes looking for it.
    src = src.split('"""', 2)[-1]
    assert "POPULATION_MAY_BE_ABSENT" not in src, (
        "set_summary reads the exempt set again; Knut's rule is that an N-A "
        "never demotes a column, whatever row it is on, so there is no row "
        "list for it to consult")
    # and it is still doing its other job
    assert cs.POPULATION_MAY_BE_ABSENT
    from ui.dialogs import measurement_report_dialog as d
    assert "POPULATION_MAY_BE_ABSENT" in inspect.getsource(
        d.MeasurementReportDialog._mismatch_text)


# =========================================================================
# 4. COND is not a row word, and nothing may teach that it is
# =========================================================================
def test_a_row_can_never_read_cond():
    """The code-side truth the prose must match, swept rather than asserted
    on one example: over every limit kind, both `should` states, a value and
    no value, graded and not, `row_verdict` never answers COND."""
    from workflow.compliance_sets import COND, Limit, row_verdict
    limits = [Limit.value(2.0), Limit.should(2.0), Limit.none(),
              Limit.unknown(), Limit.unmeasurable()]
    seen = set()
    for lim in limits:
        for value in (None, 0.0, 2.0, 2.0 + 1e-12, 3.0, 1e6, -1.0):
            for graded in (True, False):
                seen.add(row_verdict(lim, value, graded))
    assert COND not in seen, sorted(str(x) for x in seen)


def test_a_missed_recommendation_reads_fail_not_cond():
    """Knut, 2026-09-21: *"all thresholds tested against are treated the
    same."* The help card used to say a missed recommendation reads COND."""
    from workflow.compliance_sets import FAIL, Limit, row_verdict
    assert row_verdict(Limit.should(2.0), 3.0, True) == FAIL


def test_cond_is_still_an_overall_word():
    """It is retired as a ROW word and nothing else, so a guard that simply
    banned it would be wrong. An ISO-named column is COND at best."""
    from workflow.compliance_sets import COND, Limit, PASS, set_summary
    s = set_summary([(Limit.value(2.0), PASS, "row0")],
                    set_is_iso=True, graded=True)
    assert s.word == COND


#: **EVERY USER-FACING STRING THAT NAMES COND, AND WHY IT MAY.** Complete: the
#: test below compares this against what the extractor finds, so a new string
#: fails here and an edit to a pinned one fails here. Read the module docstring
#: before changing a line of it.
#:
#: What COND means today: it is a COLUMN's Overall word and nothing else. A row
#: reads PASS, FAIL, INFO or N-A. Reports saved before ChromIQ 4.3.0 still
#: carry COND on rows and the app still has to explain it to whoever opens one.
COND_IS_ALLOWED_TO_APPEAR_HERE: "dict[str, str]" = {
    "the cell label":
        "COND",
    "the glossary heading for the five words":
        "PASS, FAIL, COND, INFO, N-A (the verdict words)",
    "the glossary entry for the row words, which now says it is not one":
        "What a row of a report says about itself. PASS is inside its limit "
        "and FAIL is outside it. INFO means the set puts no limit on that "
        "row, so the number is shown and not graded. N-A means your chart "
        "carries nothing that could answer the row at all. A row the set "
        "cannot express gets no word. COND is not a row word: it belongs to "
        "the column's Overall, below. A report saved before ChromIQ 4.3.0 "
        "may still show COND on a row, where it meant a value over a limit "
        "the set only recommended; such a row reads FAIL today.",
    "the glossary entry for Overall, where the word does belong":
        "The one word for a whole dated check, worked out from its rows: any "
        "FAIL makes it FAIL; a required row your chart could not answer "
        "makes it COND; an ungraded sheet is INFO; otherwise PASS. A column "
        "judged against one of the ISO-named sets can never read better than "
        "COND, because those numbers are being applied to your chart rather "
        "than to the standard's own.",
    "the Getting Started card's result words":
        "Each row reads PASS when it is inside its limit and FAIL when it is "
        "not, INFO when the set puts no limit on that row, and N-A when your "
        "chart carries nothing that could answer it. “Overall” is "
        "the one word for a whole dated check, and the only place COND "
        "appears. A profiling measurement is never graded at all: it is "
        "expected to fall outside accuracy limits, and saying so would be "
        "noise rather than news.",
    "the report window's own guide, rewritten 2026-09-21":
        "COND (short for conditional): a column's Overall word when nothing "
        "failed but the set was only partly checked, either because it holds "
        "rows this chart could not supply or because its values are a "
        "standard's applied to your chart rather than to that standard's "
        "own. Rows do not use this word. A report saved before ChromIQ 4.3.0 "
        "may still show it on a row, where it meant a value over a limit the "
        "set recommended rather than required; such a row reads FAIL today "
        "and carries a numbered note saying the metric is a recommendation.",
    "the tooltip on a COND cell a saved report still carries":
        "CONDITIONAL: this report was saved by an earlier ChromIQ, where a "
        "value over a limit the set recommended rather than required read "
        "CONDITIONAL instead of FAIL. The verdict is shown as it was "
        "recorded. Generate the report again to have it judged by today's "
        "rule.",
}

#: Two long help texts mention COND once inside pages of other prose. Pinning
#: them whole would pin every unrelated sentence in them, so they are named
#: here by the clause that carries the word and checked for that clause.
COND_INSIDE_A_LONG_HELP_TEXT: "dict[str, str]" = {
    "the Measurement Report window's Help":
        "with the column's Overall word, which may also read COND",
    "the limits window on what an ISO-named column can read":
        "so their Overall reads COND at best",
}


def _cond_keys() -> "set[str]":
    from i18n_extract import extract_keys
    # `\bCOND` and not `\bCOND\b`: the tooltip on a saved report's COND cell
    # spells the word out as CONDITIONAL and has to be pinned too. The leading
    # boundary is what keeps "READINGS PER SECOND" out of the net.
    return {k for k in extract_keys() if re.search(r"\bCOND", k)}


def test_the_register_of_cond_strings_is_complete():
    """Nothing user-facing says COND that is not accounted for above."""
    pinned = set(COND_IS_ALLOWED_TO_APPEAR_HERE.values())
    unpinned = set()
    for k in _cond_keys():
        if k in pinned:
            continue
        if any(frag in k for frag in COND_INSIDE_A_LONG_HELP_TEXT.values()):
            continue
        unpinned.add(k)
    assert not unpinned, (
        "a user-facing string names COND and is not in the register of "
        "strings allowed to. COND is a COLUMN's Overall word and nothing "
        "else; if this string teaches it as a row word it is false, and if "
        "it does not, add it to COND_IS_ALLOWED_TO_APPEAR_HERE with the "
        "reason:\n\n" + "\n\n".join(sorted(repr(u[:400]) for u in unpinned)))


@pytest.mark.parametrize("why", sorted(COND_IS_ALLOWED_TO_APPEAR_HERE))
def test_every_pinned_cond_string_is_still_the_shipped_one(why):
    """The other direction: a register entry that no longer matches anything
    shipped is a register that has stopped checking. One of these is a
    fragment of a longer string, so containment rather than equality."""
    want = COND_IS_ALLOWED_TO_APPEAR_HERE[why]
    assert any(want == k or want in k for k in _cond_keys()), (
        f"the register entry {why!r} matches no shipped string any more:\n"
        + repr(want[:400]))


@pytest.mark.parametrize("why", sorted(COND_INSIDE_A_LONG_HELP_TEXT))
def test_every_pinned_cond_clause_is_still_shipped(why):
    want = COND_INSIDE_A_LONG_HELP_TEXT[why]
    assert any(want in k for k in _cond_keys()), repr(want)


# =========================================================================
# 5. …AND THE GUIDE'S OWN ACCOUNT OF WHEN A COLUMN READS PASS
# =========================================================================
def test_the_guide_does_not_say_pass_needs_every_row_checked(qapp):
    """**A FIFTH FALSE SENTENCE, AND KNUT'S RULING IS WHAT MADE IT FALSE.**

    "How to read this report" said: *"A column's Overall word is PASS only
    when every row the set requires was checked and passed."* True until
    2026-09-21, and false the moment an N-A stopped demoting a column: the
    verdict photographed for finding 1 is a PASS with two required rows
    unchecked, and this paragraph sat four screens above it denying that such
    a thing exists.

    **Nothing found it. A photograph did**, taken of the guide to show the
    COND bullet beside it, with this sentence in frame. No test in the suite
    reads this paragraph, which is why it is read here.
    """
    import re
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    html = MeasurementReportDialog._how_to_read_html(
        MeasurementReportDialog.__new__(MeasurementReportDialog))
    text = re.sub(r"<[^>]+>", " ", html)
    text = text.replace("&#x27;", "'").replace("&quot;", '"')
    text = " ".join(text.split())
    assert "PASS only when every row the set requires was checked" not in text, (
        "the guide still says a column reads PASS only when every required "
        "row was checked; since Knut's ruling of 2026-09-21 a row the chart "
        "cannot answer does not stop a column reading PASS")
    assert "every row that could be checked passed" in text, text[:400]
    assert "is not counted as a failure" in text
