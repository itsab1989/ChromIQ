"""#147 (Knut): regenerating a run must not silently replace its patch set.

    *"I duplicated the run 1, and the run 2 had exact same sequence of patches
    as run 1. Seed number 2036994733 was specified on both runs chart settings.
    However, when I then went back to run 1 and renamed the Run 1 Description
    and Run 1 Chart Notes, and then clicked generate chart … then the sequence
    was no longer like it was, even when the seed number has not been changed."*

**The seed was innocent.** Two things establish that from his own files:

* targen is deterministic — the same arguments produce a byte-identical
  ``.ti1`` (measured, ArgyllCMS 3.5.0). A chart built by targen therefore
  already regenerates unchanged.
* the seed only shuffles the *order* of a patch set; it cannot change which
  patches exist.

What actually changed was the patch **set**. In his project:

===== ======================== ======= =====================================
Run   ``.ti1`` ORIGINATOR      Patches What it is
===== ======================== ======= =====================================
run2  ``ChromIQ``              1994    his edited set, duplicated before the
                                       regenerate — still intact
run1  ``Argyll targen``        2002    a fresh targen run, after it
===== ======================== ======= =====================================

run2's sequence matches his ``edited_patch_set.ti1`` exactly, in order. run1's
does not even hold the same colours. His log shows why: the project was opened
at 22:57:03 — which clears the in-memory binding to the edited patch set — and
Generate at 23:02:21 fell through to ``targen -f2002``.

**Why this is worse than an irreproducible chart.** The sheet was already
printed. Its patches no longer match the ``.ti2`` ChromIQ would measure it
against, so every reading would land on the wrong patch and the resulting
profile would be quietly wrong, with nothing on screen to say so.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

TARGEN_TI1 = """CTI1

DESCRIPTOR "Argyll Calibration Target chart information 1"
ORIGINATOR "Argyll targen"
COLOR_REP "iRGB"

NUMBER_OF_FIELDS 4
BEGIN_DATA_FORMAT
SAMPLE_ID RGB_R RGB_G RGB_B
END_DATA_FORMAT

NUMBER_OF_SETS 2
BEGIN_DATA
1 0.0000 0.0000 0.0000
2 100.0000 100.0000 100.0000
END_DATA
"""

# What the patch editor / the colour-set generators write — Knut's 1994-patch
# set was one of these.
EDITED_TI1 = TARGEN_TI1.replace('ORIGINATOR "Argyll targen"',
                                'ORIGINATOR "ChromIQ"')


class _Tab:
    """The attributes and helpers the rebind touches — driving the real method
    without building a whole Create Chart tab."""

    def __init__(self, sig="SIG"):
        self._preset_ti1_path = None
        self._preset_ti1_targen_sig = None
        self._sig = sig
        self.locks_refreshed = 0

    def _targen_signature(self):
        return self._sig

    def _update_preset_locks(self):
        self.locks_refreshed += 1

    _rebind_patch_set_from_run = None      # bound in the fixture


@pytest.fixture
def tab():
    from ui.tabs.tab_chart import TabChart
    t = _Tab()
    # The real method, unbound — no monkeypatching of the code under test.
    t._rebind_patch_set_from_run = (
        TabChart._rebind_patch_set_from_run.__get__(t, _Tab))
    return t


def _write(tmp_path: Path, name: str, body: str) -> Path:
    p = tmp_path / name
    p.write_text(body)
    return p


# --- the bug ----------------------------------------------------------------

def test_an_edited_patch_set_is_reattached(tab, tmp_path):
    """The heart of #147: a run built from the user's own patch set must come
    back attached to it, so Generate re-lays-out those patches."""
    ti1 = _write(tmp_path, "chart.ti1", EDITED_TI1)
    tab._rebind_patch_set_from_run(ti1)
    assert tab._preset_ti1_path == ti1, (
        "the run's own patch set was not re-attached — Generate would run "
        "targen and replace it, which is #147")


def test_the_signature_is_captured_so_the_escape_hatch_survives(tab, tmp_path):
    """Reuse must stay conditional. The signature is what lets a deliberate
    change to a patch-set setting still produce a fresh chart."""
    ti1 = _write(tmp_path, "chart.ti1", EDITED_TI1)
    tab._rebind_patch_set_from_run(ti1)
    assert tab._preset_ti1_targen_sig == "SIG"


def test_the_lock_is_shown_not_just_held(tab, tmp_path):
    """Knut read the missing lock before anyone found the missing binding:

        *"the checkmark 'Edit patch recipe (override preset)' is shown and is
        disabled. This checkmark was missing on both run 1 and run 2 … That
        might be one cause that allowed targen to run after I applied the patch
        set from the editor."*

    ``_ti1_preset_active`` turns true the moment the path is set, and that is
    what puts the box on screen and greys the targen panel. Setting the state
    without refreshing would protect the patch set while the screen still said
    it was unprotected — the exact state that cost him thirteen printed pages.
    """
    ti1 = _write(tmp_path, "chart.ti1", EDITED_TI1)
    tab._rebind_patch_set_from_run(ti1)
    assert tab.locks_refreshed == 1, (
        "the override row and the greying were never refreshed, so the lock "
        "would be invisible")


def test_no_lock_refresh_when_nothing_was_bound(tab, tmp_path):
    """A targen chart changes nothing, so it must not disturb the panels."""
    ti1 = _write(tmp_path, "chart.ti1", TARGEN_TI1)
    tab._rebind_patch_set_from_run(ti1)
    assert tab.locks_refreshed == 0


def test_a_targen_chart_is_not_bound(tab, tmp_path):
    """targen's output is reproducible from its arguments, so binding it would
    add state for no gain — and would wrongly pin a chart the user expects to
    be rebuilt when they change the patch count."""
    ti1 = _write(tmp_path, "chart.ti1", TARGEN_TI1)
    tab._rebind_patch_set_from_run(ti1)
    assert tab._preset_ti1_path is None


# --- robustness -------------------------------------------------------------

def test_a_missing_ti1_changes_nothing(tab, tmp_path):
    tab._rebind_patch_set_from_run(tmp_path / "nope.ti1")
    assert tab._preset_ti1_path is None


def test_none_changes_nothing(tab):
    tab._rebind_patch_set_from_run(None)
    assert tab._preset_ti1_path is None


def test_a_ti1_with_no_originator_is_treated_as_the_users_own(tab, tmp_path):
    """An imported or hand-written patch set may carry no ORIGINATOR. Keeping
    it is the safe reading: the cost of binding a chart needlessly is that it
    is reproduced, while the cost of not binding is silently losing it."""
    ti1 = _write(tmp_path, "chart.ti1",
                 TARGEN_TI1.replace('ORIGINATOR "Argyll targen"\n', ""))
    tab._rebind_patch_set_from_run(ti1)
    assert tab._preset_ti1_path == ti1


def test_an_unreadable_ti1_does_not_raise(tab, tmp_path):
    """Showing a chart must never fail because of this."""
    ti1 = tmp_path / "chart.ti1"
    ti1.write_bytes(b"\xff\xfe\x00binary nonsense")
    tab._rebind_patch_set_from_run(ti1)      # must not raise


def test_originator_is_matched_case_insensitively(tab, tmp_path):
    ti1 = _write(tmp_path, "chart.ti1",
                 TARGEN_TI1.replace("Argyll targen", "ARGYLL TARGEN"))
    tab._rebind_patch_set_from_run(ti1)
    assert tab._preset_ti1_path is None
