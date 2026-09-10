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

The cap on an ISO column was never about licensing. A standard's figures are
written for that standard's own control strip on that standard's own chart, and
ChromIQ measures the chart the user printed. Typing the numbers in by hand does
not change what they are applied to.
"""
from __future__ import annotations

import pytest

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
def test_every_row_within_its_limit_is_still_only_conditional(set_id):
    """The whole point: nothing failing is NOT the same as passing that test."""
    rows = [(Limit.value(2.0), PASS), (Limit.value(3.0), PASS)]
    sm = set_summary(rows, set_is_iso=applies_a_standard(set_id), graded=True)
    assert sm.word == COND, (set_id, sm)
    assert "not a test against that standard" in sm.reason


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
    assert sm.word == COND, (set_id, label, sm)


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
