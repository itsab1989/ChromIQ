"""No test may ask GitHub anything, and for a while four of them did.

A gate on 2026-09-10 came out red with four `test_updater.py` failures whose
recorder held **the real current release**, `v4.2.3`, where the test's own fake
`_fetch` returns `v3.14.7`. They passed when the file was run alone.

The cause is a leak with two halves, and neither alone would have done it.
`_api_is_blocked()` reads `update_check_blocked_until` out of `AppSettings`,
which `pytest_configure` sandboxes per WORKER PROCESS rather than per test. A
test that exercises the spent-quota path leaves that key behind. The next test
in the same worker then takes the other branch of `_run`: it skips the API,
never calls the `_fetch` that test patched, and falls through to the releases
feed, which opens a real connection to github.com and answers truthfully.

So a unit test was quietly answered by the internet. On this machine that made
it fail; on a machine with no route out it would have waited for a ten-second
timeout instead, and on a machine where `v3.14.7` happened to be current it
would have PASSED while proving nothing.

`tests/conftest.py::_the_update_check_never_reaches_the_network` clears the key
around every test and makes `_open` raise. This file proves both halves bite.
"""
from __future__ import annotations

import pytest


def test_the_feed_cannot_be_opened_for_real():
    """MUTATION: drop the `_open` patch from the conftest fixture and this
    stops raising, because the call reaches urllib. Watched."""
    from core import updater as U

    with pytest.raises(AssertionError) as exc:
        U.UpdateChecker._open("https://github.com/itsab1989/ChromIQ/releases.atom")
    assert "for real" in str(exc.value)
    assert "update_check_blocked_until" in str(exc.value), (
        "the refusal does not name the usual cause, so the next person to hit "
        "it learns nothing from it")


def test_no_test_inherits_another_test_s_spent_quota():
    """The half that actually caused the red gate.

    This test DELIBERATELY leaves the key behind, exactly as the rate-limit
    tests do. The one below must not see it.

    MUTATION: drop the `_forget()` calls from the conftest fixture and the
    second test fails. Watched, in both orders.
    """
    import time

    from core import updater as U
    U._remember_rate_limit(int(time.time()) + 3600)
    assert U._api_is_blocked(), "the fixture cannot be tested; nothing was set"


def test_the_quota_is_clear_again_here():
    from core import updater as U
    assert not U._api_is_blocked(), (
        "this test inherited the spent quota the previous one left behind, so "
        "the update check would skip the API and answer from the network")
