"""A Custom column started from an ISO set never prints an unqualified PASS.

Found by an on-screen round on 2026-09-10, driving the route ChromIQ's own
documentation tells a tester to use: you own the standard, so you put its
numbers into a Custom column yourself and ChromIQ distributes nothing. One
number makes `custom_iso_12647_7` selectable, and the report then printed a bold
green **PASS** with "Every value this limit set requires was checked and is
within its limit."

No string claimed anything, which is why the sweep for claim words in
`test_chromiq_never_claims_conformance.py` could not see it. **The claim was
made by juxtaposition**: a column named after a standard, a green PASS, and no
caveat. That is precisely what ChromIQ promised a rights holder in writing it
would never do.

The caveat on an ISO column was never about licensing. A standard's figures are
written for that standard's own control strip on that standard's own chart, and
ChromIQ measures the chart the user printed. Typing the numbers in by hand does
not change what they are applied to.

**AND THE CAP THAT USED TO CARRY IT IS GONE.** Until 2026-09-22 such a column
was held at COND whatever its rows said, and that word was half the answer to
the juxtaposition above. Knut retired it that day, so every assertion in this
file that used to read COND now reads PASS, and the caveat is the whole of the
promise. That makes this file more load-bearing than it was, not less.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

# THE EXTRACTOR, ON THIS FILE'S OWN TERMS. Importing `i18n_extract` bare works
# only if some other test file has already put `scripts/` on the path, which
# under `--dist loadfile` is a different worker's business; run alone, this
# file failed with ModuleNotFoundError. Same note as
# `test_an_absence_never_makes_a_column_conditional.py`.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from workflow.compliance_sets import (COND, PASS, Limit, SETS, SET_BY_ID,
                                      applies_a_standard, set_summary)


_ISO_DERIVED = tuple(s.id for s in SETS
                     if s.kind == "iso"
                     or (s.parent and SET_BY_ID[s.parent].kind == "iso"))
_OWN = tuple(s.id for s in SETS if s.id not in _ISO_DERIVED)


def test_the_two_custom_columns_are_recognised_as_iso_derived():
    assert "custom_iso_12647_7" in _ISO_DERIVED
    assert "custom_iso_12647_8" in _ISO_DERIVED
    for sid in _ISO_DERIVED:
        assert applies_a_standard(sid), sid


def test_chromiqs_own_sets_are_not():
    assert _OWN, "the fixture found no ChromIQ set at all"
    for sid in _OWN:
        assert not applies_a_standard(sid), sid


def test_an_unknown_or_missing_set_is_not_a_standard():
    assert not applies_a_standard(None)
    assert not applies_a_standard("")
    assert not applies_a_standard("no_such_set")


@pytest.mark.parametrize("set_id", _ISO_DERIVED)
def test_every_row_within_its_limit_reads_PASS_and_still_carries_the_caveat(set_id):
    """**THE WORD MOVED; THE PROMISE DID NOT.**

    This used to require COND, because a cap held every ISO column there
    whatever its rows said, and that cap was what stopped the juxtaposition
    this file exists to prevent: a column named after a standard, a green
    PASS, and no caveat.

    Knut retired the cap on 2026-09-22: *"The note is sufficient. Most users
    are just interested in knowing if the measurements passed against the
    criteria set ... ChromIQ's results are only indications that results that
    PASS likely fulfil the standard ... It is not proof that results fulfil the
    standard. The report text notes should explain this detail."*

    So the column now reads PASS, and **the caveat is the only thing left
    holding the promise**. It is asked for here with the same strictness the
    word was, and `measurement_report_dialog` prints `STANDARD_CAVEAT` for
    every column applying a standard, live or saved.

    MUTATION: delete the caveat clause from the ISO reason and this goes red
    for every ISO-derived set, which is the state the challenge round found in
    the first place.
    """
    rows = [(Limit.value(2.0), PASS), (Limit.value(3.0), PASS)]
    sm = set_summary(rows, set_is_iso=applies_a_standard(set_id), graded=True)
    assert sm.word == PASS, (set_id, sm)
    assert "not a test against that standard" in sm.reason, (
        f"{set_id}: an ISO column reads PASS with no caveat in its own "
        f"sentence, which is the claim-by-juxtaposition this file exists to "
        f"prevent"
    )


def test_the_caveat_says_it_is_not_proof():
    """Knut's own words are the substance of the replacement, not a paraphrase.

    He gave the reasoning when he retired the cap, and asked for it to be in
    the report: the charts are not the standard's charts, the metrics are
    ChromIQ's own rather than the standard's methods, and a pass is an
    indication rather than proof. With the word gone, this sentence is what a
    reader has.
    """
    from workflow.compliance_sets import STANDARD_CAVEAT
    for phrase in ("not the standard's chart",
                   "ChromIQ's own rather than the standard's methods",
                   "not proof that it does"):
        assert phrase in STANDARD_CAVEAT, (
            f"the caveat no longer says {phrase!r}, and it is now the only "
            f"place the qualification appears"
        )


@pytest.mark.parametrize("set_id", _OWN)
def test_chromiqs_own_sets_can_still_pass(set_id):
    """The other half, or the test above would pass on a cap applied to all."""
    rows = [(Limit.value(2.0), PASS), (Limit.value(3.0), PASS)]
    sm = set_summary(rows, set_is_iso=applies_a_standard(set_id), graded=True)
    assert sm.word == PASS, (set_id, sm)


# ---- the way in that was still open -------------------------------------
_FORGOTTEN = [
    # (set id a later ChromIQ no longer defines, the label the run stored)
    ("custom_iso_12647_7_v1", "Custom ISO 12647-7"),
    ("iso_12647_8_2021", "ISO 12647-8:2021 values"),
    ("some_old_id", "ISO 12647-7:2016 values"),
    ("fogra51_aim", "Fogra 51 aim values"),
]


@pytest.mark.parametrize("set_id, label", _FORGOTTEN)
def test_a_set_this_version_has_forgotten_still_carries_the_caveat(set_id, label):
    """A run keeps the id and the label of the set it was bound to. When a later
    ChromIQ no longer defines that id, the report shows the stored label marked
    "(historical)" — and this used to answer False, so the column read
    "Custom ISO 12647-7 (historical)" beside a green PASS with no caveat.

    No string claimed anything. The claim was the arrangement, which is exactly
    how the previous one of these was found.
    """
    assert applies_a_standard(set_id, label), (set_id, label)
    rows = [(Limit.value(2.0), PASS), (Limit.value(3.0), PASS)]
    sm = set_summary(rows, set_is_iso=applies_a_standard(set_id, label), graded=True)
    # The word is PASS since Knut retired the cap on 2026-09-22; what this
    # file guards is the CAVEAT, which is now the only thing standing between
    # a column named after a standard and an unqualified green pass.
    assert sm.word == PASS, (set_id, label, sm)
    assert "not a test against that standard" in sm.reason, (set_id, label, sm)


def test_a_forgotten_chromiq_set_can_still_pass():
    """The other half. Capping every unknown id would punish ChromIQ's own
    retired sets, which never applied anybody's published figures."""
    assert not applies_a_standard("chromiq_default_v1", "ChromIQ default (old)")
    rows = [(Limit.value(2.0), PASS)]
    sm = set_summary(rows,
                     set_is_iso=applies_a_standard("chromiq_default_v1",
                                                   "ChromIQ default (old)"),
                     graded=True)
    assert sm.word == PASS, sm


# ===========================================================================
# The glossary and the guide stopped teaching the cap, and must not start
# ===========================================================================
#: Everything a reader is told about what an ISO-named column's Overall can
#: read. Swept over the English source strings, because the cap was taught in
#: four separate places and a fix that corrected three of them would look
#: exactly like a fix that corrected all four.
_THE_CAP_IN_PROSE: "tuple[str, ...]" = (
    "can never read better than COND",
    "reads COND at best",
    "is COND at best",
    "Overall can never be better than COND",
)


def test_no_user_facing_string_still_teaches_the_retired_cap():
    """MUTATION: put any of the four clauses back into the glossary, the
    report window's guide or its "how to read this" card, and this goes red
    naming the string it found."""
    from i18n_extract import extract_keys
    hits = [(c, k) for k in extract_keys() for c in _THE_CAP_IN_PROSE if c in k]
    assert not hits, (
        "user-facing text still says an ISO-named column is capped at COND, "
        "which `set_summary` stopped doing on 2026-09-22:\n  "
        + "\n  ".join(f"{c!r} in {k[:120]!r}" for c, k in hits))


def test_the_glossary_says_what_replaced_it():
    """The other direction, and the reason it is here rather than in the COND
    register: the corrected sentence does not contain the word COND at all, so
    a register of COND strings cannot watch it and the cap could be quietly
    replaced by nothing."""
    from i18n_extract import extract_keys
    keys = list(extract_keys())
    want = ("column judged against one of the ISO-named sets reads PASS or "
            "FAIL like any other")
    assert any(want in k for k in keys), (
        "the glossary no longer tells a reader what an ISO-named column's "
        "Overall reads. It used to say COND at best; if that clause is gone "
        "and nothing replaced it, the entry is silent on the one column a "
        "reader is most likely to look it up for.")
