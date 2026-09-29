"""Knut's N-A ruling, held against the CODE and against the app's own prose.

Knut, 2026-09-21, amending §15.5 of
``docs/design/measurement_report_limits.md``:

    *"Not Applicable must not be counted as a fail, so the overall verdict
    should show PASS, not COND, if all others pass. I say, a metric that is
    not applicable should not have verdict conditional because COND does not
    indicate which of the verdicts cause the COND."*

`set_summary` was changed for it and the two-row carve-out deleted. Two
user-facing sentences were not, and challenge round 33 photographed both:

* the Getting Started glossary entry for **Overall (verdict)** still said
  *"a required row your chart could not answer makes it COND"*, in thirteen
  languages and translated into German, so a German reader was given a false
  sentence in German;
* the report window's own guide, **rewritten on the day of the ruling**, still
  opened its COND bullet with *"the set was only partly checked, either
  because it holds rows this chart could not supply"* — four lines above its
  own paragraph saying *"a row this chart could not answer is not counted as a
  failure"*. One document, two rules, and the wrong one first.

Both were inside the register `test_the_report_words_say_what_the_code_does`
built for exactly this class of string, pinned there as true. A register is
only as good as the reading that filled it, so this file adds the two things a
register cannot do: it MEASURES the rule over every shape a column can have,
and it sweeps the catalogue for the two clauses the ruling killed.
"""
from __future__ import annotations

import itertools
import sys
from pathlib import Path

import pytest

# THE EXTRACTOR, ON THIS FILE'S OWN TERMS. The sibling register imports
# `i18n_extract` bare and only works because another test file put `scripts/`
# on the path first, which under `--dist loadfile` is a different worker's
# business. Asked for here so this file passes when it is run alone.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from workflow.compliance_sets import (COND, FAIL, INFO, N_A, PASS,
                                      SUMMARY_REASONS, Limit,
                                      recorded_reason, set_summary)

# The limit kinds a bearing row can have. `none` / `unknown` / `unmeasurable`
# are not bearing at all, so they cannot reach the clause under test; both
# numeric kinds can, and the `should` one is the kind the deleted carve-out
# was originally written around.
_LIMITS = {"value": Limit.value(2.0), "should": Limit.should(2.0)}
_WORDS = (PASS, FAIL, COND, INFO, N_A)


def _shapes(n: int):
    for combo in itertools.product(itertools.product(_LIMITS, _WORDS),
                                   repeat=n):
        yield [(_LIMITS[k], w, f"row{i}") for i, (k, w) in enumerate(combo)]


# ===========================================================================
# 1. The rule, measured rather than asserted on one example
# ===========================================================================
def test_no_absence_anywhere_makes_a_column_conditional():
    """Over every shape of up to three bearing rows: with no ISO-named set and
    no row carrying a saved COND, the column never reads COND.

    THE POPULATION IS PROVED TO BE ABLE TO SHOW THE FAULT by the companion
    test below, which reaches COND from the two causes that remain. A sweep
    that cannot produce the word at all would pass this by saying nothing.

    MUTATION: put the deleted clause back in `compliance_sets.set_summary` --

        required_missing = sum(1 for lim, w, rid in bearing if w == N_A
                               and not lim.is_should)
        if cond or required_missing:

    -- and this goes red naming the first shape that moves.
    """
    bad = []
    for n in (1, 2, 3):
        for rows in _shapes(n):
            if any(w == COND for _l, w, _r in rows):
                continue            # a report saved before 4.3.0
            s = set_summary(rows, set_is_iso=False, graded=True)
            if s.word == COND:
                bad.append([(l.kind, w) for l, w, _r in rows])
    assert not bad, (
        f"{len(bad)} column shapes read COND with no ISO set and no saved "
        f"COND row, first {bad[0]}: Knut's ruling of 2026-09-21 is that an "
        "N-A never demotes a column, whatever row it is on")


def test_and_the_one_cause_that_does_remain_still_reaches_it():
    """The control for the sweep above: COND is still reachable, once.

    It was twice until 2026-09-22, when Knut retired the ISO cap. An
    ISO-named column now reads PASS or FAIL like any other and carries
    `STANDARD_CAVEAT` as a note instead, so a guard that banned COND outright
    would still be wrong, and for one reason rather than two.
    """
    iso = set_summary([(Limit.value(2.0), PASS, "row0")],
                      set_is_iso=True, graded=True)
    assert iso.word == PASS, "the ISO cap is retired; the note carries it now"
    saved = set_summary([(Limit.value(2.0), COND, "row0")],
                        set_is_iso=False, graded=True)
    assert saved.word == COND, "a row a pre-4.3.0 report saved with the word"
    # …and an ISO column holding such a row is COND too, with the sentence
    # that names the recommended value, not the `iso*` one that would have
    # said "all within this limit set's values" over the top of it.
    from workflow.compliance_sets import SUMMARY_REASONS
    both = set_summary([(Limit.value(2.0), PASS, "row0"),
                        (Limit.should(1.5), COND, "row1")],
                       set_is_iso=True, graded=True)
    assert both.word == COND, both
    assert both.reason == SUMMARY_REASONS["cond_recommended"], both.reason


# ===========================================================================
# 2. …and nothing the user reads may still teach the deleted rule
# ===========================================================================
#: The two clauses Knut's ruling killed, verbatim as they shipped in
#: 4.3.0-beta.30. Exact text, not a pattern: the corrected sentences say
#: "a row this chart could not answer does not make a column COND", which
#: names both halves and which a looser rule would flag.
CLAUSES_THE_RULING_KILLED: "tuple[str, ...]" = (
    "could not answer makes it COND",
    "either because it holds rows this chart could not supply",
)


def test_no_user_facing_string_teaches_the_deleted_rule():
    """Swept over every English source string the extractor can see.

    MUTATION: put either clause back into `ui/dialogs/welcome_dialog.py` or
    `ui/dialogs/measurement_report_dialog.py` and this goes red naming it.
    """
    from i18n_extract import extract_keys
    hits = [(c, k) for k in extract_keys()
            for c in CLAUSES_THE_RULING_KILLED if c in k]
    assert not hits, (
        "user-facing text still says an unanswered row makes a column COND, "
        "which `set_summary` stopped doing on 2026-09-21:\n  "
        + "\n  ".join(f"{c!r} in {k[:90]!r}" for c, k in hits))


@pytest.mark.parametrize("code", ("de", "uk", "no", "nl", "fr", "es", "it",
                                  "ja", "pl", "pt", "ru", "sv", "zh_CN"))
def test_no_catalogue_still_carries_the_deleted_rule(code):
    """A stale key in a catalogue is a sentence a reader of that language is
    still shown. German is translated, so a stale German row is a false
    sentence IN GERMAN, which is how this class of fault has been found twice.
    """
    from i18n_extract import load_catalog
    cat = load_catalog(code)
    hits = [k for k in cat for c in CLAUSES_THE_RULING_KILLED if c in k]
    assert not hits, (
        f"{code}.json still carries the deleted rule as a key: {hits[:2]}")


# ===========================================================================
# 3. A SAVED sentence that its own saved counts deny is not replayed
# ===========================================================================
def test_a_recorded_completeness_claim_is_not_replayed_over_its_own_counts():
    """B8-710. The word and the counts are the record; the sentence is prose.

    Beta 29 wrote ``"pass"`` -- "Every value this limit set requires was
    checked and is within its limit." -- beside a recorded ``not_computed`` of
    2, because the two repeatability rows were exempt from its arithmetic by
    name. Beta 30 fixed the live path and went on replaying the saved
    sentence.

    MUTATION: make `compliance_sets.recorded_reason` return *reason* unchanged
    and this goes red on the first case.
    """
    claim = SUMMARY_REASONS["pass"]
    assert recorded_reason(claim, 7, 9, 2) == SUMMARY_REASONS["pass_partial"]
    assert recorded_reason(claim, 8, 9, 1) == SUMMARY_REASONS["pass_partial_one"]
    # …and a claim its counts DO support is the record and stays untouched
    assert recorded_reason(claim, 9, 9, 0) == claim
    # …as does every other saved sentence, whatever the counts
    for key in ("fail", "iso", "not_graded", "nothing_checked", "empty"):
        assert recorded_reason(SUMMARY_REASONS[key], 1, 9, 8) == \
            SUMMARY_REASONS[key], key


def test_the_report_window_does_not_print_a_saved_completeness_claim(tmp_path,
                                                                     qapp):
    """The same thing at the other end: a report SAVED the way the app saves
    one, then rewritten into the shape beta 29 left on disk, opened in the real
    window on the one page that carries no table to contradict it.

    The report is saved through `stamp_verdict` and only its `summary.reason`
    is put back to the old sentence, because that is the single field beta 29
    wrote differently; nothing else about the file is invented.

    MUTATION: drop the `recorded_reason` call from `_column_summary` in
    `ui/dialogs/measurement_report_dialog.py` and this goes red.
    """
    import json

    from tests.test_a_saved_report_does_not_leak_its_verdict_into_another_type \
        import _as, _saved
    from workflow.compliance_sets import summary_text
    from workflow.measurement_report import REPORT_TYPE_SUMMARY

    dlg, run, path = _saved(tmp_path, qapp)
    doc = json.loads(path.read_text(encoding="utf-8"))
    sm = doc["verdict"]["summary"]
    assert sm["not_computed"] > 0, (
        "the fixture has nothing unchecked, so it cannot show the fault: "
        "the two repeatability rows are what a first verification leaves N-A")
    # exactly what beta 29 wrote into this field, and nothing else
    sm["reason"] = SUMMARY_REASONS["pass"]
    doc["verdict"]["overall"] = PASS
    path.write_text(json.dumps(doc), encoding="utf-8")

    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    dlg2 = MeasurementReportDialog(dlg._settings, None,
                                   initial_ti3=run.verifications()[0].measurement_ti3)
    dlg2.show()
    qapp.processEvents()
    _as(dlg2, run, REPORT_TYPE_SUMMARY)
    shown = summary_text(dlg2._column_summary(dlg2._report))
    body = dlg2._report_body_html(dlg2._runs_for_report(), for_pdf=False)
    pdf = dlg2._report_body_html(dlg2._runs_for_report(), for_pdf=True)
    dlg2.close()
    dlg.close()
    qapp.processEvents()
    claim = "Every value this limit set requires was checked"
    assert claim not in shown, (
        f"the one-page summary prints {shown!r} beside a recorded "
        f"not_computed of {sm['not_computed']}")
    assert claim not in body and claim not in pdf, \
        "and it reaches the window body and the PDF"


def test_the_false_sentence_is_still_a_live_string(qapp):
    """The control. The three assertions above would also pass if the sentence
    had simply been deleted from the catalogue, which would break every report
    saved before today instead of correcting one of them."""
    assert SUMMARY_REASONS["pass"] in SUMMARY_REASONS.values()
    from workflow.compliance_sets import Summary, summary_text
    s = Summary(PASS, 9, 9, 0, 0, 0, SUMMARY_REASONS["pass"])
    assert "Every value this limit set requires was checked" in summary_text(s)
