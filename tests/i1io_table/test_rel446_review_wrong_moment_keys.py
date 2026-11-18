"""Release review of 4.3.46 (18 Nov 2026): keys the table's reader sends at the wrong moment.

The 4.3.46 readers send the helper "retry" (key 'r') after a failed reading and Esc chains to
end it. The helper's spot loop treats EVERY key as an instrument trigger at its patch menu
(``inst_set_uih(0x00, 0xff, DUIH_TRIG)``), so a stray "retry" there fires the i1Pro 2. These
tests pin that nothing is STORED from such a key, and that a row whose second try failed too
keeps only its good readings, on the committed helper with its replay instrument.
"""
from __future__ import annotations

import re

import pytest

from tests.i1io_table.test_4346_the_reader_ends_the_real_helper import (  # noqa: F401
    _ended_by_itself, _keep_the_log, _row_with_a_fault_at_a2, _sent)
from tests.i1io_table.test_4346_the_reader_hears_the_real_helper import HELPER_SRC, _real_reader
from workflow.i1io.table import reader as rd

pytestmark = pytest.mark.timeout(120)


def test_the_spot_loop_stores_a_reading_only_for_the_read_keys():
    """chromiq_chartread.c: a triggered spot reading is kept only when the key that triggered
    it is '0' (a good reading), space or Return ("read"). Any other key ('r' = "retry", 'd' =
    "done") goes to "Unrecognised response" and the reading is dropped. If this ever widens,
    a stray "retry" at the patch menu stores whatever lies under the arm."""
    src = (HELPER_SRC / "chromiq_chartread.c").read_text(encoding="utf-8", errors="replace")
    assert re.search(r"xtern == 0 && \(ch == '0' \|\| ch == ' ' \|\| ch == '\\r'\)", src)
    assert "inst_set_uih(0x00, 0xff, DUIH_TRIG);" in src


def test_a_stray_retry_at_the_patch_menu_stores_nothing(tmp_path, monkeypatch):
    r, _log = _real_reader(tmp_path, monkeypatch, calibrate=False, needcal=False, patches=3)
    try:
        r.open(lambda ev: True, timeout=20)
        r.proc.send({"cmd": "retry"})
        assert r.proc.wait(("patch_read", "saved"), 2.0) is None
        assert not r.base.with_suffix(".ti3").exists()
        # the reader still reads the patch it sits on, and only that one
        got = r.read("A1", timeout=10)
        assert got.loc == "A1"
    finally:
        r.close()
    _ended_by_itself(r)


def test_a_patch_that_fails_twice_leaves_only_the_good_readings(tmp_path, monkeypatch):
    """job._patch: a second failure fails the row; the reader is then finished at the helper's
    retry prompt (Esc chain, never "done"). The row file holds A1 only, never A2."""
    r, _a1 = _row_with_a_fault_at_a2(tmp_path, monkeypatch, "misread")
    r.ready_loc = None
    r.proc.send({"cmd": "swipe", "fault": "misread"})     # the replay's next answer: misread
    with pytest.raises(rd.ReaderFailed):
        r.read("A2", timeout=10)
    assert _sent(r).count({"cmd": "retry"}) == 1
    ti3 = r.finish(timeout=10)
    _ended_by_itself(r)
    assert {"cmd": "done"} not in _sent(r)
    assert ti3 is not None and sorted(rd.read_ti3_spectra(ti3)[1]) == ["A1"]
