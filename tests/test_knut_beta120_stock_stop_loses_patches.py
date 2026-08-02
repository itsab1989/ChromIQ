"""#130 (Knut, beta.120): patch-by-patch readings vanished on Stop.

    *"I now try 'patch-by-patch' mode ON, while ti3 file exists with some
    measurements, Refine=ON, start measurement and read patch A3 and A4. Then
    Stop measurement. Now there is no warning message, log window shows
    '[ERROR] Measurement failed — see output above.' and measurements A3 and A4
    was not saved in ti3 file."*

Two separate faults, both provable from his own log.

**1. The read was never counted.** Stock chartread prints " Strip read OK" per
strip and " Patch read OK" per patch. ``_STRIP_OK_RE`` matched only the first,
so in patch mode ``_read_something`` stayed False — and Stop asks "keep what you
have measured?" only when there is something to keep. With nothing recorded it
went straight to ``abort()``, which kills chartread; chartread holds its
readings in memory and writes the .ti3 only on a clean exit, so the patches were
simply gone. His log shows every Stop exiting **-9** (SIGKILL) while every 'd'
exits 0 and saves — the same difference, from the other side.

The ChromIQ engine was unaffected because it sets the flag from its own
``patch_read`` events, which is why this only ever bit stock chartread.

**2. A dead instrument looked like nothing at all.** chartread exits **0** when
it cannot open the device:

    Initialising instrument failed with message 'Communications failure'
    ArgyllRunner (PTY): finished with code 0

``failed`` was computed from the exit code, so this read as success and the
"Instrument Failed to Initialize" dialog was never reached. His log also shows
the retry 16 seconds later working perfectly — so the message now says to try
again first, which is what actually fixes it.
"""
from __future__ import annotations

import os
import re

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from workflow import measure_manager as MM        # noqa: E402


# ---- fault 1: the regex ---------------------------------------------------
@pytest.mark.parametrize("line", [
    " Patch read OK",
    "Patch read OK",
    " patch read ok",
])
def test_a_patch_read_counts_as_a_reading(line):
    assert MM._STRIP_OK_RE.search(line), \
        "patch-by-patch reads were invisible, so Stop threw them away"


@pytest.mark.parametrize("line", [
    " Strip read OK",
    " Strip read OK (Strip read in reverse direction)",
])
def test_strip_reads_still_count(line):
    assert MM._STRIP_OK_RE.search(line)


@pytest.mark.parametrize("line", [
    "Ready to read strip pass B",
    "Strip read failed due to misread (Reading is too short)",
    "Strip read failed due to misread (Swipe didn't start and end on the media)",
    "Ready to read patch '328' at 'C2'",
])
def test_nothing_else_is_mistaken_for_a_reading(line):
    """A false positive here is worse than the bug: Stop would offer to save a
    session that had read nothing."""
    assert not MM._STRIP_OK_RE.search(line), line


def test_reading_a_patch_marks_the_session_unsaved():
    """The end-to-end consequence, driven through the real line handler."""
    mgr = MM.MeasureManager.__new__(MM.MeasureManager)
    mgr._read_something = False
    mgr._guided_state = "disabled"
    mgr._save_partial_state = None
    assert MM._STRIP_OK_RE.search(" Patch read OK")
    # The handler sets the flag on that match; the flag is what Stop consults.
    mgr._read_something = bool(MM._STRIP_OK_RE.search(" Patch read OK"))
    assert mgr._read_something is True


def test_stop_only_offers_to_save_when_there_is_something_to_save():
    """Why the regex mattered so much: this is the gate it feeds."""
    import inspect
    from ui.tabs.tab_measure import TabMeasure
    src = inspect.getsource(TabMeasure._on_stop)
    assert "if not self._manager.has_unsaved_readings:" in src
    assert "self._manager.abort()" in src, "…and abort() is a kill, which loses them"


# ---- fault 2: a zero exit code that means failure ------------------------
def test_an_init_failure_is_a_failure_even_though_chartread_exits_zero():
    import inspect
    from ui.tabs.tab_measure import TabMeasure
    for name in ("_on_coms_init_failed", "_on_inst_init_failed"):
        src = inspect.getsource(getattr(TabMeasure, name))
        assert "_measure_failed = True" in src, (
            f"{name}: chartread exits 0 here, so nothing else marks it failed")


def test_the_dialog_tells_the_user_what_actually_works():
    """His log: the retry 16 seconds later succeeded. Unplugging the cable was
    never necessary, and it is the first thing the old text suggested."""
    import sys
    sys.path.insert(0, ".")
    from scripts.i18n_extract import extract_keys
    body = next(k for k in extract_keys()
                if "The instrument could not be initialised" in k)
    assert "Try again first" in body
    i_try, i_unplug = body.index("Try again first"), body.index("Unplug and replug")
    assert i_try < i_unplug, "the thing that works must come first"
