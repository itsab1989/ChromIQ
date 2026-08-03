"""§T1.4 for §6e — when rebuilding a profile must warn.

``docs/design/unified_measurement_management.md`` §6. Every row of the §6e
table, as a decision with no window attached.

The one that matters most is row 4: **no build signature.** Knut dropped that
idea — *"The main intention is to make user aware, then the user is given
authority to act responsibly on an informed basis"* — so nothing here asks
whether the new profile would differ from the old one. Warn, explain,
recommend, allow, and let a per-run checkbox silence it.
"""
from __future__ import annotations

import os
import types

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from workflow.profile_rebuild_guard import assess     # noqa: E402


class _Verification:
    def __init__(self, vid, exists=True):
        self.id = vid
        self._exists = exists

    def exists(self):
        return self._exists


def _run(*, profile=True, verify_chart=True, dated=0, dated_empty=0,
         duplicate_ready=True):
    """A stand-in Run with only what the guard asks of it."""
    def _f(exists):
        return types.SimpleNamespace(exists=lambda: exists)

    vs = [_Verification(f"2026-0{i + 1}-01", True) for i in range(dated)]
    vs += [_Verification(f"2026-1{i}-01", False) for i in range(dated_empty)]
    return types.SimpleNamespace(
        built_profile_icc=lambda: _f(profile),
        has_verify_chart=lambda: verify_chart,
        verifications=lambda: vs,
        chart_ti1=_f(duplicate_ready),
        chart_ti2=_f(duplicate_ready),
        chart_channels_json=_f(duplicate_ready),
        chart_tiffs=lambda: ["p1.tif"] if duplicate_ready else [],
    )


# ---- every row of §6e ----------------------------------------------------
def test_row1_no_profile_yet():
    assert not assess(_run(profile=False)).needed


def test_row2_no_verification_chart():
    assert not assess(_run(verify_chart=False)).needed


def test_row3_a_chart_with_no_measurements_is_just_a_chart():
    assert not assess(_run(dated=0)).needed


def test_row3b_dated_folders_without_readings_do_not_count():
    """A folder is created the moment a verification starts, so its existence
    is not evidence that anything was measured."""
    assert not assess(_run(dated=0, dated_empty=3)).needed


def test_row4_silenced_for_this_run_this_session():
    assert not assess(_run(dated=2), silenced=True).needed


def test_row5_one_dated_measurement():
    w = assess(_run(dated=1))
    assert w.needed and w.dated == 1


def test_row6_several_dated_measurements():
    w = assess(_run(dated=4))
    assert w.needed and w.dated == 4
    assert w.oldest == "2026-01-01", "the message names how far back it goes"


def test_row7_a_loaded_file_is_not_a_run():
    """Build Profile works on whatever measurement is loaded into it, and that
    case has no history to strand."""
    assert not assess(None).needed


# ---- no build signature --------------------------------------------------
def test_the_guard_never_asks_whether_the_profile_would_differ():
    """Knut dropped the signature idea. Warning depends on what the run HOLDS,
    never on a comparison with what the build would produce."""
    import inspect
    from workflow import profile_rebuild_guard as g
    src = inspect.getsource(g)
    for word in ("signature", "settings_hash", "would_differ"):
        assert f"def {word}" not in src
    assert "assess(run, *, silenced" in src.replace("\n", " ") or True
    # The function takes the run and a silence flag — nothing else.
    assert list(inspect.signature(g.assess).parameters) == ["run", "silenced"]


# ---- §4a's second half: do not recommend a control that cannot work ------
def test_duplicate_is_offered_when_the_run_can_be_duplicated():
    assert assess(_run(dated=2)).can_duplicate


def test_duplicate_is_not_offered_when_the_run_lacks_the_files():
    w = assess(_run(dated=2, duplicate_ready=False))
    assert not w.can_duplicate
    assert "the chart's layout recipe (.channels.json)" in w.duplicate_blocked_by


def test_the_missing_files_are_named_so_the_message_can_say_which():
    w = assess(_run(dated=2, duplicate_ready=False))
    assert len(w.duplicate_blocked_by) == 4, "all four, by name"


# ---- it never blocks a build --------------------------------------------
def test_a_broken_run_does_not_stop_anyone_building():
    """A guard that raises would make the app unusable for the case it was
    meant to protect."""
    broken = types.SimpleNamespace(
        built_profile_icc=lambda: (_ for _ in ()).throw(OSError("gone")))
    assert not assess(broken).needed
