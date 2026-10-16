"""#210: a reading from a slipped strip is remembered with the measurement.

Basti's decision of 2026-10-15: a strip the misalignment safety net flags
confirms nothing. In 4.3.5 beta 8 the judge knew that only during the
session (``FlagJudge.judge(slipped=)``, the tab's ``_slipped_locs``): once
the session ended nothing remembered that a stored reading came from a
slipped strip, so a later identical reading in a resumed session confirmed
against it, which the same reading in the session could never do.

The memory beside the measurement (``<stem>.confirmed.json``, valid only for
the ``.ti3`` whose SHA-256 it holds) now lists those patches under
``"slipped"``, and an unsettled patch's earlier readings carry their own
``"slipped"``. Reopened or resumed, a slipped stored reading is judged
exactly as in the session. A file written before has no such field and is
read as before.
"""
from __future__ import annotations

import json

from tests.test_k182_k3_k4_overlay_and_memory import (  # noqa: F401
    _again, _end_session, _flags, _live_session, _reread_route_only, _strip,
    _tab, _write_ti3)
from tests.test_k182_k3_k4_overlay_and_memory import _qapp  # noqa: F401
from workflow import confirmed_patches as cp
from workflow import patch_flags as pf


def _slipped(ev):
    ev["misaligned"] = 1
    return ev


def _session_with_a_slipped_strip_a(tmp_path):
    """Strips A, F and O read; strip A read again, the safety net flags it,
    and its readings are the ones the file keeps."""
    tab = _tab(tmp_path)
    _live_session(tab)
    for c in "AFO":
        tab._on_strip_measured(_strip(c))
    tab._on_strip_measured(_slipped(_again("A")))
    assert _flags(tab)["A17"] is True             # red, never yellow
    assert "A17" in tab._slipped_locs
    ti3 = _write_ti3(tmp_path, scale=1.004)       # the slipped readings
    _end_session(tab, ti3)
    return tab, ti3


def _resume(tmp_path):
    tab = _tab(tmp_path)
    tab._session_resumes = True
    _live_session(tab)
    # the overlay on, so the stored readings are painted and judged first
    # (as in test_rereading_a_strip_from_an_earlier_session_confirms)
    cb = tab._overlay_cb if tab._current_mode() == "guided" else tab._m_overlay_cb
    cb.blockSignals(True)
    cb.setChecked(True)
    cb.blockSignals(False)
    tab._on_session_map([{"strip": c, "read": True} for c in "AFO"])
    assert tab._flag_judge()._history.get("A17"), "the stored reading is judged"
    return tab


def test_the_memory_lists_the_patches_whose_reading_slipped(tmp_path):
    _tab0, ti3 = _session_with_a_slipped_strip_a(tmp_path)
    raw = json.loads(cp.confirmed_path(ti3).read_text(encoding="utf-8"))
    assert raw["ti3_sha256"] == cp.ti3_sha256(ti3)
    assert "A17" in raw["slipped"] and "A23" in raw["slipped"]
    assert not any(loc.startswith(("F", "O")) for loc in raw["slipped"])
    assert "A17" in cp.load(ti3)["slipped"]


def test_the_first_clean_reading_after_a_resume_stays_red(tmp_path):
    """MUTATION: drop the "slipped" seeding in _load_confirmed_memory and
    A17 turns yellow here, against the stored slipped reading.

    The exact gap: the session ends on a slipped strip, the resume reads
    the strip once, cleanly, with the same colour. In the session that is
    red ("a later reading the net did NOT flag that gives the same colour
    stays red"); after the resume it must be red too."""
    _session_with_a_slipped_strip_a(tmp_path)
    tab = _resume(tmp_path)
    assert {"A17", "A23"} <= tab._slipped_locs
    assert _flags(tab)["A17"] is True             # repainted: red, as it was
    ev = _again("A")                              # the stored slip's colour
    tab._on_strip_measured(ev)
    assert _flags(tab)["A17"] is True
    assert "A17" not in tab._flag_judge().confirmed
    assert "A17" not in tab._slipped_locs         # this reading did not slip


def test_control_an_old_memory_without_the_field_still_confirms(tmp_path):
    """Files written before keep working, and their readings are not slipped:
    the same resume against a memory without "slipped" confirms, as it
    always did (tests/test_k182_k3_k4_overlay_and_memory.py)."""
    _tab0, ti3 = _session_with_a_slipped_strip_a(tmp_path)
    raw = json.loads(cp.confirmed_path(ti3).read_text(encoding="utf-8"))
    raw.pop("slipped")
    cp.confirmed_path(ti3).write_text(json.dumps(raw), encoding="utf-8")
    assert cp.load(ti3)["slipped"] == []
    tab = _resume(tmp_path)
    assert tab._slipped_locs == set()
    tab._on_strip_measured(_again("A"))
    assert _flags(tab)["A17"] == pf.FLAG_CONFIRMED


def test_reopening_from_disk_keeps_the_slip_red(tmp_path):
    _session_with_a_slipped_strip_a(tmp_path)
    other = _tab(tmp_path)
    assert other._show_overlay_from_existing_ti3()
    assert _flags(other)["A17"] is True
    assert "A17" in other._slipped_locs


def test_the_slip_is_forgotten_when_the_file_changes(tmp_path):
    """The memory holds only for the .ti3 whose hash it carries."""
    _tab0, ti3 = _session_with_a_slipped_strip_a(tmp_path)
    _write_ti3(tmp_path)                          # another version of the file
    assert cp.load(ti3) is None
    other = _tab(tmp_path)
    assert other._show_overlay_from_existing_ti3()
    assert other._slipped_locs == set()


def test_cleaning_keeps_only_location_names():
    clean = cp._clean_slipped(["A1", 3, None, "", "B2", "A1"])
    assert clean == ["A1", "B2"]
    assert cp._clean_slipped("A1") == []


def test_an_unsettled_patchs_slipped_reading_keeps_its_flag():
    """An unsettled patch stores its earlier flagged readings; one of them
    from a slipped strip must come back as slipped, or a later identical
    reading would settle against it."""
    lab = (50.0, 0.0, 0.0)
    j = pf.FlagJudge()
    j._unsettled["A1"] = (30.0,)
    j._history["A1"] = [pf._Reading((60.0, 1.0, 1.0), 30.0, True),
                        pf._Reading((70.0, 1.0, 1.0), 40.0, True,
                                    slipped=True),
                        pf._Reading((80.0, 1.0, 1.0), 50.0, True)]
    j._last["A1"] = j._history["A1"][-1]
    out = j.export()
    rd = out["A1"]["readings"]
    assert rd[0].get("slipped") is None and rd[1]["slipped"] is True
    clean = cp._clean_entry(out["A1"])
    assert clean["readings"][1]["slipped"] is True
    k = pf.FlagJudge()
    k.load({"A1": clean})
    assert [r.slipped for r in k._history["A1"]] == [False, True]
    del lab
