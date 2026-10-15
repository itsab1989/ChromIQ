"""#210: a strip the misalignment safety net flags must never confirm anything.

On the forum user's SELPHY chart strips 8 and 13 were read one patch out, read
again, slipped the same way again, and the Measure tab marked the patches
"confirmed": the re-read agreed with the first reading, which is the rule for
a confirmation. A repeat of the same slip is not a confirmation.

The engine now carries the safety net's verdict in the strip_read event itself
(``"misaligned": <offset>``), so the tab knows while it judges the patches.
Ordinary identical re-reads still confirm (the first test is the control).

The judge itself keeps the verdict on the reading
(``FlagJudge.judge(slipped=)``, Basti's decision 2026-10-15): a later reading
the safety net did NOT flag is never compared with a slipped one, so it
cannot confirm against it either (the gap the first #210 change left), and a
slipped reading is nobody's similar patch. The judge-level cases are in
``tests/test_210_a_slipped_reading_confirms_nothing_in_the_judge.py``.
"""
from __future__ import annotations

from tests.test_neighbour_check_in_the_measure_tab import (  # noqa: F401
    _flags, _info, _read_all, _strip, _tab, qapp)
from workflow import patch_flags as pf

SETTINGS = {"patch_read_warn_de_estimated": 8.0,
            "patch_strip_test_estimated": False,
            "patch_neighbour_limit_estimated": 50.0}


def _slipped(letter, bad=None):
    ev = _strip(letter, bad)
    ev["misaligned"] = 1
    return ev


def test_control_an_ordinary_identical_re_read_still_confirms(qapp, tmp_path):
    tab = _tab(tmp_path, settings=SETTINGS)
    _read_all(tab, {"B3": 0.6})
    assert _flags(tab)["B3"] is True
    tab._on_strip_measured(_strip("B", {"B3": 0.6}))
    assert _flags(tab)["B3"] == pf.FLAG_CONFIRMED


def test_a_re_read_repeating_a_flagged_slip_does_not_confirm(qapp, tmp_path):
    """MUTATION: drop `slipped=` from the strip judging and this goes red."""
    tab = _tab(tmp_path, settings=SETTINGS)
    _read_all(tab)
    tab._on_strip_measured(_slipped("B", {"B3": 0.6}))
    assert _flags(tab)["B3"] is True
    tab._on_strip_measured(_slipped("B", {"B3": 0.6}))
    assert _flags(tab)["B3"] is True, "a repeated slip was taken as a confirmation"
    assert "B3" not in tab._flag_judge().confirmed
    info = _info(tab, "B3")
    assert info["flag"] == "" and info["reread_only"] is False


def test_a_correct_re_read_after_a_slip_is_judged_normally(qapp, tmp_path):
    tab = _tab(tmp_path, settings=SETTINGS)
    _read_all(tab)
    tab._on_strip_measured(_slipped("B", {"B3": 0.6}))
    tab._on_strip_measured(_strip("B"))
    assert _flags(tab).get("B3") in (False, None, pf.FLAG_CORRECTED)
    assert "B3" not in tab._slipped_locs


def test_the_engine_puts_the_verdict_in_the_strip_read_event():
    """The C side: the field is in the event the tab judges from."""
    from pathlib import Path
    src = (Path(__file__).resolve().parent.parent / "native" / "chartread_helper"
           / "chromiq_chartread.c").read_text(encoding="utf-8", errors="replace")
    assert '\\"misaligned\\":%d' in src
    i_emit = src.index("cq_emit_strip_read(scb, stipa")
    i_det = src.index("mis = cq_detect_misalign(")
    assert i_det < i_emit, "worked out after the event that needs it"


def test_an_unflagged_re_read_never_confirms_against_the_slip(qapp, tmp_path):
    """The gap: the slipped reading and a later reading the net did NOT flag
    give the same colour. MUTATION: let the judge's earlier readings keep the
    slipped ones and this turns yellow."""
    tab = _tab(tmp_path, settings=SETTINGS)
    _read_all(tab)
    tab._on_strip_measured(_slipped("B", {"B3": 0.6}))
    assert _flags(tab)["B3"] is True
    tab._on_strip_measured(_strip("B", {"B3": 0.6}))
    assert _flags(tab)["B3"] is True, "confirmed against a slipped reading"
    assert "B3" not in tab._flag_judge().confirmed
    # ... and a third, ordinary reading that agrees with that second one
    # confirms as always.
    tab._on_strip_measured(_strip("B", {"B3": 0.6}))
    assert _flags(tab)["B3"] == pf.FLAG_CONFIRMED
