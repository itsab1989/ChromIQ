"""4.3.50, two leftovers of the earlier 4.3.50 round, in the table's own words:

* the Measure tab's "the i1iO table cannot measure this chart" window said "This chart has no such
  file beside it, or ChromIQ cannot read it" also when the side file IS there and readable (the
  chart only lies outside a project's run folder, or names another table): it now has its own
  first paragraph then (M-I1IO-NOT-YET-SIDE-FILE / -BY-HAND);
* the dual scan's fill note before Continue Measurement said "takes you back to strip A for a new
  reading", the hand path's words: on a chart the table reads, the TABLE reads the rows again
  (M-I1IO-DRIVE-DUAL-CONTINUE-FILL / -FILL-OFFER, rows named as the chart prints them).
"""
from __future__ import annotations

import inspect
from types import SimpleNamespace

import pytest

from ui.tabs import tab_measure as TM
from workflow import i1pro3_conditions as C
from workflow import measurement_messages as M


def test_the_side_file_window_never_says_the_file_is_missing():
    for msg in (M.M_I1IO_NOT_YET_SIDE_FILE, M.M_I1IO_NOT_YET_SIDE_FILE_BY_HAND):
        first = msg.render()[1].split("\n\n")[0]
        assert "is beside it" in first and "no such file" not in first
        assert "—" not in msg.render()[1]
    # the rest of each is its sibling's, word for word
    assert M.M_I1IO_NOT_YET_SIDE_FILE.body.split("\n\n", 1)[1] == \
        M.M_I1IO_NOT_YET.body.split("\n\n", 1)[1]
    assert M.M_I1IO_NOT_YET_SIDE_FILE_BY_HAND.body.split("\n\n", 1)[1] == \
        M.M_I1IO_NOT_YET_BY_HAND.body.split("\n\n", 1)[1]
    src = inspect.getsource(TM.TabMeasure._i1io_not_yet_window)
    assert "M_I1IO_NOT_YET_SIDE_FILE" in src and "_i1io_side_file_readable()" in src


def _fake(table: bool, resuming: bool):
    return SimpleNamespace(
        _fill_main=lambda: "main.ti3", _fill_strips=lambda main: ["A", "C"],
        _fill_instrument=lambda main, dual: "yes",
        _measurement_to_continue=lambda: ("x" if resuming else None),
        _table_chart_loaded=lambda: table)


@pytest.mark.parametrize("resuming", [True, False], ids=["continue", "offer"])
@pytest.mark.parametrize("table", [True, False], ids=["table", "by hand"])
def test_the_dual_fill_note_is_the_tables_on_a_table_chart(monkeypatch, table, resuming):
    from workflow.dual_scan import storage
    monkeypatch.setattr(storage, "read_dual_record", lambda main: SimpleNamespace(dual=True))
    monkeypatch.setattr(C, "no_pair_kept", lambda main: False)
    monkeypatch.setattr(C, "file_condition", lambda main: "M0")
    title, body = TM.TabMeasure._fill_note_text(_fake(table, resuming))
    if table:
        assert "rows A, C" in title + body and "the table" in body
        assert "takes you back" not in body and "strip" not in body
    else:
        assert "strips A, C" in body
    assert C.rows_phrase(["A"]) == "row A" and C.rows_phrase(["A", "C"]) == "rows A, C"
