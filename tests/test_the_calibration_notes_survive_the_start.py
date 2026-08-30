"""#159: every calibration message was erased milliseconds after being written.

The CR30 calibration runs BEFORE the helper starts, and writes what it did to
the measurement log: the dark-reference reading and how it looks, the note that
a white calibration cannot be verified at all, the note saying which dark
reference a skipped step left in place.

`_on_start` then cleared the log — fifty-one lines after calling the
calibration, in the same method. So none of it was ever readable. **The dark
reference check, the only honest check either calibration has, had been firing
correctly for its whole life and nobody had ever seen its answer.**

Found on 2026-08-30 the only way it could be: the owner ran the black
calibration deliberately wrong, pasted the whole log, and the answer was not in
it. Not the "could not read back" variant either — nothing at all, which is
what says "erased" rather than "never ran".
"""
from __future__ import annotations

import inspect

from ui.tabs.tab_measure import TabMeasure


def _start_source() -> str:
    return inspect.getsource(TabMeasure._on_start)


def test_the_log_is_cleared_before_the_calibration_not_after():
    src = _start_source()
    clear = src.index("self._log.clear()")
    calibrate = src.index("_run_cr30_calibration()")
    assert clear < calibrate, (
        "the log is cleared after the calibration has written to it, so every "
        "calibration message is erased before the user can read it")


def test_it_is_cleared_exactly_once():
    """Two clears would put the bug back with one of them in the wrong place —
    and the second would be the one that ran."""
    assert _start_source().count("self._log.clear()") == 1


def test_the_dark_reference_reading_also_reaches_the_file_log():
    """It was written to the on-screen panel alone, so it never appeared in
    chromiq.log and a report of a bad profile could not be checked against it.

    Asserted on the logger call rather than the text, because the sentence the
    user reads is §M's business and will change; that the number is recorded at
    all is not."""
    src = inspect.getsource(TabMeasure._do_black_calibration)
    assert "log.info" in src and "dark reference read back" in src, (
        "the dark-reference reading is still on-screen-only")
