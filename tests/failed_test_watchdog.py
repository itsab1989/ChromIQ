"""A FAILED TEST KEEPS ITS WATCHDOG (2026-11-22, two silent gate stalls).

pytest's faulthandler plugin and pytest-timeout both cancel their timer in
`pytest_exception_interact`, which pytest calls for every failed test before
its teardown, so a teardown (or module / session finalizer) that blocks after
a failure blocks for ever, unnamed. This re-arms one C-level timer that dumps
every thread and ends the process; the end of the item disarms it.
Diagnosis: ~/Desktop/ChromIQ-work/2026-11-22_gate_stall/findings.txt.
tests/conftest.py imports these hooks; tests/test_a_failed_test_keeps_its_
watchdog.py loads this module as a plugin into a planted run.
"""
import faulthandler

import pytest

_armed = False


@pytest.hookimpl(trylast=True)      # after the two tryfirst cancels
def pytest_exception_interact(node, call, report):
    global _armed
    if not isinstance(node, pytest.Item):
        return
    from _pytest.faulthandler import fault_handler_stderr_fd_key
    fd = node.config.stash.get(fault_handler_stderr_fd_key, None)
    try:
        limit = float(node.config.getini("timeout") or 0)   # pytest-timeout's
    except ValueError:                                       # plugin absent
        limit = 0.0
    limit = limit or 900.0
    if fd is not None:
        faulthandler.dump_traceback_later(limit, exit=True, file=fd)
        _armed = True


def pytest_runtest_logfinish(nodeid, location):
    """The item is over (teardown included): disarm, before the next item's
    own timer is armed by faulthandler's protocol wrapper."""
    global _armed
    if _armed:
        faulthandler.cancel_dump_traceback_later()
        _armed = False
