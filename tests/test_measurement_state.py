"""§T1.1, T1.2 and T1.5 of the Unified Measurement Management specification.

``docs/design/unified_measurement_management.md`` — every row of §3a (what state
a measurement file is in) and §3b (what a session did to it), proved as
arithmetic on real files rather than through a window.

The specification's own rule: *"No section of this specification is implemented
until its row in T1 and T3 is green."* This is that row.
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from workflow.measurement_state import (   # noqa: E402
    SessionVerdict, Ti3State, added_by_session, classify, count_sets,
    expected_patches, judge_session)

HEADER = """CTI3

DESCRIPTOR "Argyll Calibration Target chart information 3"
KEYWORD "SAMPLE_LOC"
NUMBER_OF_FIELDS 5
BEGIN_DATA_FORMAT
SAMPLE_ID SAMPLE_LOC RGB_R RGB_G RGB_B
END_DATA_FORMAT
"""


def _ti3(tmp_path, rows, *, claimed=None, name="m.ti3",
         data_block=True, end=True):
    """A CGATS file with *rows* data lines and whatever header we ask for."""
    n = len(rows) if claimed is None else claimed
    text = HEADER + f"\nNUMBER_OF_SETS {n}\n"
    if data_block:
        text += "BEGIN_DATA\n" + "".join(f"{r}\n" for r in rows)
        if end:
            text += "END_DATA\n"
    p = tmp_path / name
    p.write_text(text, encoding="utf-8")
    return p


def _rows(n, start=1):
    return [f"{i} A{i} 100.0 100.0 100.0" for i in range(start, start + n)]


# ---- T1.5 · counting -----------------------------------------------------
def test_counts_a_normal_file(tmp_path):
    assert count_sets(_ti3(tmp_path, _rows(12))) == (12, 12)


def test_a_missing_file_is_not_a_count(tmp_path):
    assert count_sets(tmp_path / "nope.ti3") is None


def test_blank_lines_in_the_body_are_not_readings(tmp_path):
    p = tmp_path / "m.ti3"
    p.write_text(HEADER + "\nNUMBER_OF_SETS 2\nBEGIN_DATA\n"
                 "1 A1 1 1 1\n\n   \n2 A2 2 2 2\n\nEND_DATA\n", encoding="utf-8")
    assert count_sets(p) == (2, 2)


def test_crlf_is_read_the_same_as_lf(tmp_path):
    lf = _ti3(tmp_path, _rows(5), name="lf.ti3")
    crlf = tmp_path / "crlf.ti3"
    crlf.write_bytes(lf.read_text(encoding="utf-8").replace("\n", "\r\n").encode())
    assert count_sets(crlf) == count_sets(lf)


def test_anything_after_end_data_is_another_table(tmp_path):
    """A CGATS file may carry several tables; the measurement is the first."""
    p = tmp_path / "m.ti3"
    p.write_text(HEADER + "\nNUMBER_OF_SETS 2\nBEGIN_DATA\n1 A1 1 1 1\n"
                 "2 A2 2 2 2\nEND_DATA\n\nBEGIN_DATA\n9 Z9 9 9 9\nEND_DATA\n", encoding="utf-8")
    assert count_sets(p) == (2, 2)


def test_no_data_block_reads_as_none_not_zero(tmp_path):
    """Knut's case: a header and nothing else. 'No block' and 'an empty block'
    are different findings and the caller is entitled to tell them apart."""
    claimed, held = count_sets(_ti3(tmp_path, [], data_block=False, claimed=7))
    assert claimed == 7
    assert held is None


def test_a_block_left_open_still_counts_its_rows(tmp_path):
    """A killed chartread can leave END_DATA unwritten. The rows are still
    readings, and refusing to count them would throw away real work."""
    assert count_sets(_ti3(tmp_path, _rows(4), end=False)) == (4, 4)


# ---- T1.1 · every row of §3a ---------------------------------------------
def test_absent(tmp_path):
    assert classify(tmp_path / "nope.ti3").state is Ti3State.ABSENT


def test_no_data_block(tmp_path):
    f = classify(_ti3(tmp_path, [], data_block=False, claimed=3))
    assert f.state is Ti3State.NO_DATA_BLOCK
    assert not f.has_readings


def test_empty(tmp_path):
    f = classify(_ti3(tmp_path, []))
    assert f.state is Ti3State.EMPTY
    assert not f.has_readings


def test_partial(tmp_path):
    ti2 = _ti3(tmp_path, _rows(50), name="c.ti2")
    f = classify(_ti3(tmp_path, _rows(20)), ti2)
    assert f.state is Ti3State.PARTIAL
    assert (f.held, f.expected) == (20, 50)


def test_complete(tmp_path):
    ti2 = _ti3(tmp_path, _rows(30), name="c.ti2")
    assert classify(_ti3(tmp_path, _rows(30)), ti2).state is Ti3State.COMPLETE


def test_header_disagrees_with_body(tmp_path):
    f = classify(_ti3(tmp_path, _rows(9), claimed=12))
    assert f.state is Ti3State.MISMATCHED
    assert (f.claimed, f.held) == (12, 9)


def test_more_readings_than_the_chart_has_patches(tmp_path):
    ti2 = _ti3(tmp_path, _rows(10), name="c.ti2")
    assert classify(_ti3(tmp_path, _rows(25)), ti2).state is Ti3State.MISMATCHED


def test_unreadable_is_not_empty(tmp_path):
    """Conflating them would delete a file we simply failed to open."""
    p = tmp_path / "m.ti3"
    p.write_bytes(b"\x00\xff" * 40)
    p.chmod(0o000)
    try:
        state = classify(p).state
    finally:
        p.chmod(0o644)
    assert state in (Ti3State.UNREADABLE, Ti3State.NO_DATA_BLOCK)
    assert state is not Ti3State.EMPTY


def test_readings_with_no_chart_to_compare_against(tmp_path):
    f = classify(_ti3(tmp_path, _rows(7)))
    assert f.state is Ti3State.PARTIAL
    assert f.expected is None


# ---- resume is offered for exactly one state -----------------------------
@pytest.mark.parametrize("state,resumable", [
    (Ti3State.PARTIAL, True),
    (Ti3State.COMPLETE, False),
    (Ti3State.EMPTY, False),
    (Ti3State.NO_DATA_BLOCK, False),
    (Ti3State.MISMATCHED, False),
    (Ti3State.ABSENT, False),
    (Ti3State.UNREADABLE, False),
])
def test_only_a_partial_file_may_be_resumed(tmp_path, state, resumable):
    from workflow.measurement_state import Ti3Facts
    assert Ti3Facts(state).can_resume is resumable


def test_a_mismatched_file_is_never_resumed(tmp_path):
    """The specification is explicit: resuming into a mismatch would write
    readings against patch positions that may not be the ones on the paper."""
    ti2 = _ti3(tmp_path, _rows(10), name="c.ti2")
    assert not classify(_ti3(tmp_path, _rows(9), claimed=12), ti2).can_resume


# ---- T1.2 · every row of §3b --------------------------------------------
@pytest.mark.parametrize("before,after,resumed,want", [
    (0,  0,  False, SessionVerdict.NOTHING_TO_DO),
    (0,  0,  True,  SessionVerdict.NOTHING_TO_DO),
    (0,  40, False, SessionVerdict.KEEP),
    (10, 0,  True,  SessionVerdict.DELETE_AND_RESTORE),
    (10, 0,  False, SessionVerdict.DELETE_AND_RESTORE),
    (10, 4,  True,  SessionVerdict.RESTORE_AND_KEEP_BOTH),
    (10, 10, True,  SessionVerdict.KEEP),
    (10, 25, True,  SessionVerdict.KEEP),
    (10, 4,  False, SessionVerdict.KEEP),
])
def test_the_session_verdict_table(before, after, resumed, want):
    assert judge_session(before, after, resumed=resumed) is want


def test_the_case_knut_described(tmp_path):
    """*"If saved ti3 at stop was empty and the ti3 before start was, for ex.
    10 patches, and the session was a Refine/Resume, then we know something
    went wrong, so earlier ti3 should be restored."*"""
    assert judge_session(10, 0, resumed=True) is SessionVerdict.DELETE_AND_RESTORE


def test_a_fresh_measurement_that_replaces_fewer_readings_is_not_a_fault(tmp_path):
    """Not resuming means replacing, and replacing with fewer is a choice the
    user made — the replace warning covers it, not this check."""
    assert judge_session(500, 12, resumed=False) is SessionVerdict.KEEP


@pytest.mark.parametrize("before,after,added", [
    (None, 40, 40), (10, 25, 15), (10, 10, 0), (10, 4, 0), (None, None, 0),
])
def test_how_many_this_session_added(before, after, added):
    assert added_by_session(before, after) == added


# ---- A comes from the chart ---------------------------------------------
def test_expected_patches_reads_the_chart(tmp_path):
    assert expected_patches(_ti3(tmp_path, _rows(64), name="c.ti2")) == 64


def test_expected_patches_prefers_the_body_over_the_header(tmp_path):
    """The rows are the thing; the header is a claim about them."""
    assert expected_patches(
        _ti3(tmp_path, _rows(60), claimed=99, name="c.ti2")) == 60


def test_no_chart_means_no_expectation(tmp_path):
    assert expected_patches(None) is None
    assert expected_patches(tmp_path / "nope.ti2") is None
