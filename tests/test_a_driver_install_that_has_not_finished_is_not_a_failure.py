"""An install that has not finished is not an install that failed.

Two faults, both in `core/usb_driver_installer.py::install_winusb`, both found by
driving the real app on real hardware on 2026-09-06 — and both reachable only
because the installer had just been made to work at all.

**FAULT 1 — the timeout was eleven seconds away, and firing it was a LIE.**

    kernel32.WaitForSingleObject(sei.hProcess, 60_000)   # return value dropped
    code = wt.DWORD()
    kernel32.GetExitCodeProcess(sei.hProcess, ctypes.byref(code))
    return code.value == 0

A real successful install of an X-Rite i1Studio, measured on an IDLE 2-core
ARM64 VM: `00:41:24.501` to `00:42:13.129` — **48.6 s** against a 60 s budget.
Most of it is libwdi creating a system restore point, which is not our cost.
When that budget did run out, `WaitForSingleObject` returned `WAIT_TIMEOUT`
(258), the code threw it away, `GetExitCodeProcess` answered `STILL_ACTIVE`
(259) for a process that was still installing, `259 != 0`, and the app told the
user the install had **failed** — about an install that was succeeding a second
later, and then sent them to Zadig to repair a machine that was repairing
itself.

CLAUDE.md, in as many words: *"a timeout that is too TIGHT is a phantom red …
budget a subprocess for the loaded machine, not the idle one, and make a timeout
say 'did not finish' rather than letting it read like a crash."*

**FAULT 2 — the wait was on the GUI thread.** Measured on the same run:
`Get-Process ChromIQ` reported `Responding = False` for ~50 s, with no spinner,
no message and no cursor change. The owner's words while it was working
correctly: *"after confirming the uac nothing seems to happen"*, then *"it seems
to be hanging"*. It had never been noticed because every earlier attempt failed
in 2-5 s: a WORKING install is the slow case.

The sibling next door already had all of this right —
`core/ch34x_driver.py::_run_elevated`, 300 s, `WAIT_TIMEOUT` mapped to
`Reason.STILL_RUNNING`, `CloseHandle` in a `finally` — and its comment names
this very function as the pattern it deliberately did NOT copy.
"""
from __future__ import annotations

import ctypes
import os
import time

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import core.usb_driver_installer as inst           # noqa: E402
from core.usb_driver_installer import InstallAttempt   # noqa: E402


# ---------------------------------------------------------------------------
# A kernel32 that is not Windows' — so the wait can be driven anywhere
# ---------------------------------------------------------------------------
class FakeKernel32:
    """Stands in for `ctypes.WinDLL("kernel32")`, and records what was asked.

    `_watch_the_installer` exists as a separate function precisely so this is
    possible: no elevation, no real process, and the test runs on macOS and
    Linux too — where, note, the shipped bug could never have been reproduced
    at all.
    """

    def __init__(self, *, waits, exit_code=0, exit_ok=True):
        self.waits = list(waits)
        self.exit_code = exit_code
        self.exit_ok = exit_ok
        self.wait_calls = 0
        self.exit_calls = 0
        self.closed = 0

    def WaitForSingleObject(self, handle, ms):   # noqa: N802
        self.wait_calls += 1
        return self.waits.pop(0) if self.waits else inst.WAIT_TIMEOUT

    def GetExitCodeProcess(self, handle, ref):   # noqa: N802
        self.exit_calls += 1
        ref._obj.value = self.exit_code
        return 1 if self.exit_ok else 0

    def CloseHandle(self, handle):               # noqa: N802
        self.closed += 1
        return 1


def _watch(k, **kw):
    kw.setdefault("timeout_ms", 1_000)
    return inst._watch_the_installer(k, object(), **kw)


# ---------------------------------------------------------------------------
# FAULT 1 — the shipped bug, and it cannot come back
# ---------------------------------------------------------------------------
def test_a_wait_that_timed_out_is_never_read_as_an_exit_code():
    """THE TEST THIS BRANCH EXISTS FOR.

    The fake answers `WAIT_TIMEOUT` for ever and, if anybody asks, reports
    `STILL_ACTIVE` — which is exactly what Windows does for a process that is
    still installing. The shipped code asked, got 259, compared it to 0 and
    said the install had failed.
    """
    k = FakeKernel32(waits=[], exit_code=inst.STILL_ACTIVE)
    got = _watch(k, timeout_ms=0)
    assert got is InstallAttempt.STILL_RUNNING
    assert k.exit_calls == 0, (
        "GetExitCodeProcess was called after a timeout — 259 is not an exit "
        "code, it is the absence of one")


def test_258_and_259_are_not_the_same_number():
    """They are one apart, and one is a wait result while the other is an exit
    code. Writing them down next to each other is half the fix."""
    assert inst.WAIT_TIMEOUT == 258
    assert inst.STILL_ACTIVE == 259


def test_a_process_that_exited_zero_is_an_install():
    k = FakeKernel32(waits=[inst.WAIT_OBJECT_0], exit_code=0)
    assert _watch(k) is InstallAttempt.INSTALLED


def test_a_process_that_exited_nonzero_failed():
    k = FakeKernel32(waits=[inst.WAIT_OBJECT_0], exit_code=2)
    assert _watch(k) is InstallAttempt.FAILED


def test_a_wait_that_ended_some_other_way_says_nothing_about_the_install():
    k = FakeKernel32(waits=[inst.WAIT_ABANDONED])
    assert _watch(k) is InstallAttempt.LOST_TRACK
    assert k.exit_calls == 0


def test_an_exit_code_that_could_not_be_read_is_not_a_success():
    """`GetExitCodeProcess` leaves `code.value` at 0 when it fails, and 0 is
    the success code — so an unchecked call turns "we could not ask" into "it
    worked". (`core/ch34x_driver.py:1561` still has this one.)"""
    k = FakeKernel32(waits=[inst.WAIT_OBJECT_0], exit_code=0, exit_ok=False)
    assert _watch(k) is InstallAttempt.LOST_TRACK


@pytest.mark.parametrize("waits, expected", [
    ([inst.WAIT_OBJECT_0], InstallAttempt.INSTALLED),
    ([inst.WAIT_ABANDONED], InstallAttempt.LOST_TRACK),
    ([], InstallAttempt.STILL_RUNNING),
])
def test_the_handle_is_closed_however_it_ends(waits, expected):
    k = FakeKernel32(waits=waits)
    assert _watch(k, timeout_ms=0) is expected
    assert k.closed == 1


def test_the_handle_is_closed_even_if_the_progress_callback_raises():
    k = FakeKernel32(waits=[])

    def _boom(_secs):
        raise ZeroDivisionError("the window went away")

    with pytest.raises(ZeroDivisionError):
        _watch(k, timeout_ms=1_000, progress=_boom)
    assert k.closed == 1


# ---------------------------------------------------------------------------
# Stopping the WATCHING is not stopping the INSTALL
# ---------------------------------------------------------------------------
def test_the_user_can_stop_the_wait_and_it_is_still_not_a_failure():
    k = FakeKernel32(waits=[])
    seen = []

    def _stop(secs):
        seen.append(secs)
        return False

    assert _watch(k, timeout_ms=60_000, progress=_stop) \
        is InstallAttempt.STILL_RUNNING
    assert len(seen) == 1, "it kept waiting after being told to stop"


def test_nothing_here_ever_tries_to_kill_the_installer():
    """Not a wording test: a half-installed driver is the one outcome worse
    than a slow window, and the only way to get one from here would be to
    terminate an elevated installer in the middle of a driver install."""
    import inspect
    src = inspect.getsource(inst)
    for hostile in ("TerminateProcess", "taskkill", "kill("):
        assert hostile not in src, f"{hostile} has no business in this module"


def test_the_deadline_is_wall_clock_and_not_a_count_of_slices():
    """A slice costs `_WAIT_SLICE_MS` of waiting PLUS however long `progress`
    takes — and `progress` is the Qt event pump, which can spin a nested modal
    loop for minutes. Counting slices would make "five minutes" mean anything.

    This fake answers instantly, so the two readings are not close: counting
    slices gives EXACTLY three ticks and returns in microseconds, while a clock
    spins for the whole 300 ms. Measured here: 741,709.
    """
    k = FakeKernel32(waits=[])
    calls: list = []
    started = time.monotonic()
    got = _watch(k, timeout_ms=300, progress=lambda s: calls.append(s))
    elapsed = time.monotonic() - started
    assert got is InstallAttempt.STILL_RUNNING
    assert elapsed >= 0.25, (
        f"it gave up after {elapsed:.3f} s of a 0.300 s budget — the deadline "
        "is being counted, not measured")
    assert len(calls) > 1000, (
        f"only {len(calls)} ticks in 300 ms against an instant wait — "
        "`timeout_ms / _WAIT_SLICE_MS` would give exactly 3")


# ---------------------------------------------------------------------------
# The enum, and why it is not a bool
# ---------------------------------------------------------------------------
def test_an_attempt_is_not_a_yes_or_no():
    """`all(install_winusb(d) for d in targets)` is the shape that caused the
    bug: every ending squeezed through one yes/no, and the ending that is
    neither came out as "no"."""
    for member in InstallAttempt:
        with pytest.raises(TypeError):
            bool(member)
    with pytest.raises(TypeError):
        all(a for a in [InstallAttempt.STILL_RUNNING])


def test_the_things_that_are_not_truthiness_still_work():
    """The trap must not be a landmine: an enum you cannot log or compare is
    worse than a bool."""
    m = InstallAttempt.STILL_RUNNING
    assert repr(m) and str(m) and f"{m}"
    assert m in list(InstallAttempt)
    assert {m: 1}[m] == 1
    assert m is InstallAttempt.STILL_RUNNING
    assert m != InstallAttempt.INSTALLED
