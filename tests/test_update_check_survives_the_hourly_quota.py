"""The update check must not die because somebody else shares the address.

Reported from the running app on 2026-09-10: "checking for updates in the app
says github answered 403". Reproduced from the same machine at the same moment,
with a request carrying the app's own User-Agent:

    HTTP/2 403
    x-ratelimit-limit: 60
    x-ratelimit-remaining: 0
    {"message":"API rate limit exceeded for <address>. ..."}

That is not a fault in the request. GitHub's REST API answers **60 requests an
hour to a caller with no token, counted against the IP ADDRESS**, so it is
shared by everyone behind it: an office, a school, a household, anyone on a
mobile carrier's shared address, and any machine where the app has been started
many times in an hour.
https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api
(read 2026-09-10)

The releases feed is not on that quota. Measured from the same address in the
same minute: the API answered 403 with ``x-ratelimit-remaining: 0`` while
``releases.atom`` answered 200 and listed every tag. So the check now falls back
to the feed and the user sees an answer instead of a number.
"""
from __future__ import annotations

import email.message
import time
from urllib.error import HTTPError

import pytest

from core.updater import (
    _api_is_blocked,
    _BLOCKED_UNTIL,
    _rate_limit_reset,
    _remember_rate_limit,
    _tags_from_atom,
    UpdateChecker,
)


FEED = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry><link href="https://github.com/o/r/releases/tag/v4.3.0-beta.2"/></entry>
  <entry><link href="https://github.com/o/r/releases/tag/v4.2.2"/></entry>
  <entry><link href="https://github.com/o/r/releases/tag/v4.3.0-beta.1"/></entry>
  <entry><link href="https://github.com/o/r/releases/tag/v4.2.1"/></entry>
</feed>"""


def _headers(**kv) -> email.message.Message:
    m = email.message.Message()
    for k, v in kv.items():
        m[k.replace("_", "-")] = str(v)
    return m


def _http_error(code: int, hdrs) -> HTTPError:
    return HTTPError("https://api.github.com/x", code, "no", hdrs, None)


# ---- telling a spent quota from every other 403 -------------------------
def test_a_spent_quota_is_recognised_and_dated():
    reset = int(time.time()) + 1800
    assert _rate_limit_reset(_headers(x_ratelimit_remaining=0,
                                      x_ratelimit_reset=reset)) == reset


def test_a_403_that_is_not_a_quota_is_not_treated_as_one():
    """A proxy refusing the request, or a repository gone private, still has
    requests left. Reading it as a quota would tell the user to wait for
    something that is never going to change."""
    assert _rate_limit_reset(_headers(x_ratelimit_remaining=59)) is None
    assert _rate_limit_reset(_headers()) is None
    assert _rate_limit_reset(None) is None


def test_a_spent_quota_with_no_reset_time_is_still_a_spent_quota():
    """Zero means "rate limited, time unknown", which is not None."""
    assert _rate_limit_reset(_headers(x_ratelimit_remaining=0)) == 0
    assert _rate_limit_reset(
        _headers(x_ratelimit_remaining=0, x_ratelimit_reset="soon")) == 0


# ---- the feed ------------------------------------------------------------
def test_every_tag_is_read_from_the_feed():
    assert _tags_from_atom(FEED) == [
        "v4.3.0-beta.2", "v4.2.2", "v4.3.0-beta.1", "v4.2.1"]


# ---- end to end ----------------------------------------------------------
class _Spy(UpdateChecker):
    def __init__(self):
        super().__init__()
        self.seen: list[tuple] = []

    def _emit(self, name, *args):        # no Qt signal needed to observe this
        self.seen.append((name, args))


def _quota_is_spent(monkeypatch, reset: int):
    def boom(*a, **k):
        raise _http_error(403, _headers(x_ratelimit_remaining=0,
                                        x_ratelimit_reset=reset))
    monkeypatch.setattr(UpdateChecker, "_fetch", staticmethod(boom))


def test_a_spent_quota_still_finds_the_newest_release(monkeypatch):
    """The whole point: what used to be "GitHub answered 403." is an answer."""
    reset = int(time.time()) + 600
    _quota_is_spent(monkeypatch, reset)
    monkeypatch.setattr(UpdateChecker, "_fetch_tags_from_feed",
                        classmethod(lambda cls: _tags_from_atom(FEED)))
    monkeypatch.setattr("core.updater.APP_VERSION", "4.2.1")

    spy = _Spy()
    spy._run()

    assert spy.seen == [("update_available", ("v4.2.2",))], spy.seen


def test_a_beta_build_over_the_quota_is_offered_the_newest_beta(monkeypatch):
    _quota_is_spent(monkeypatch, int(time.time()) + 600)
    monkeypatch.setattr(UpdateChecker, "_fetch_tags_from_feed",
                        classmethod(lambda cls: _tags_from_atom(FEED)))
    monkeypatch.setattr("core.updater.APP_VERSION", "4.3.0-beta.1")

    spy = _Spy()
    spy._run()

    assert spy.seen == [("update_available", ("v4.3.0-beta.2",))], spy.seen


def test_a_stable_build_over_the_quota_is_not_offered_a_beta(monkeypatch):
    """4.2.2 is current and a newer BETA exists. The fallback must say up to
    date, exactly as the API path does, and never hand a stable user a beta."""
    _quota_is_spent(monkeypatch, int(time.time()) + 600)
    monkeypatch.setattr(UpdateChecker, "_fetch_tags_from_feed",
                        classmethod(lambda cls: _tags_from_atom(FEED)))
    monkeypatch.setattr("core.updater.APP_VERSION", "4.2.2")

    spy = _Spy()
    spy._run()

    assert spy.seen == [("up_to_date", ())], spy.seen


def test_both_routes_shut_says_so_with_the_time_it_frees(monkeypatch):
    reset = int(time.time()) + 900
    _quota_is_spent(monkeypatch, reset)

    def no_feed(cls):
        raise OSError("no network")
    monkeypatch.setattr(UpdateChecker, "_fetch_tags_from_feed",
                        classmethod(no_feed))

    spy = _Spy()
    spy._run()

    assert spy.seen == [("rate_limited", (reset,))], spy.seen


def test_a_403_that_is_not_a_quota_is_still_reported_as_an_error(monkeypatch):
    def boom(*a, **k):
        raise _http_error(403, _headers(x_ratelimit_remaining=42))
    monkeypatch.setattr(UpdateChecker, "_fetch", staticmethod(boom))
    called = []
    monkeypatch.setattr(UpdateChecker, "_fetch_tags_from_feed",
                        classmethod(lambda cls: called.append(1) or []))

    spy = _Spy()
    spy._run()

    assert [n for n, _ in spy.seen] == ["check_failed"], spy.seen
    assert not called, "a 403 with requests left is not a reason to use the feed"


# ---- not asking again before the hour is up ------------------------------
def test_a_spent_quota_is_written_down_and_skips_the_api_next_time(monkeypatch):
    reset = int(time.time()) + 1200
    _quota_is_spent(monkeypatch, reset)
    monkeypatch.setattr(UpdateChecker, "_fetch_tags_from_feed",
                        classmethod(lambda cls: _tags_from_atom(FEED)))
    monkeypatch.setattr("core.updater.APP_VERSION", "4.2.1")

    _Spy()._run()
    assert _api_is_blocked(), "the wait was not recorded, so the API is asked again"

    # …and the next check goes straight to the feed without touching the API.
    def must_not_be_called(*a, **k):
        raise AssertionError("the API was asked while the quota is known spent")
    monkeypatch.setattr(UpdateChecker, "_fetch", staticmethod(must_not_be_called))

    spy = _Spy()
    spy._run()
    assert spy.seen == [("update_available", ("v4.2.2",))], spy.seen


def test_the_block_expires(monkeypatch):
    _remember_rate_limit(int(time.time()) - 1)
    assert not _api_is_blocked()


@pytest.fixture(autouse=True)
def _clear_the_block():
    from core.settings import AppSettings
    AppSettings().set(_BLOCKED_UNTIL, 0)
    yield
    AppSettings().set(_BLOCKED_UNTIL, 0)
