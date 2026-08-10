"""Regression tests for core.updater version parsing.

The original crash (issue #16) was `_parse_version` doing `int("0-beta")`
when fed a tag like "v3.5.0-beta.3". Pin the SemVer-ish precedence rules
so we don't silently regress them.
"""
from __future__ import annotations

import pytest

from core.updater import _is_prerelease, _parse_version


@pytest.mark.parametrize(
    "lower, higher",
    [
        ("v3.2.8", "v3.5.0"),
        ("v3.5.0-beta.1", "v3.5.0-beta.2"),
        ("v3.5.0-beta.9", "v3.5.0-rc.1"),
        ("v3.5.0-beta.3", "v3.5.0"),
        ("v3.4.0", "v3.5.0-beta.1"),
        ("v3.2.8", "v3.5.0-beta.3"),
    ],
)
def test_precedence(lower: str, higher: str) -> None:
    assert _parse_version(lower) < _parse_version(higher)


def test_v_prefix_optional() -> None:
    assert _parse_version("3.5.0") == _parse_version("v3.5.0")
    assert _parse_version("3.5.0-beta.3") == _parse_version("v3.5.0-beta.3")


def test_unparseable_sorts_below_everything() -> None:
    assert _parse_version("not-a-version") < _parse_version("0.0.1-alpha.1")


def test_build_metadata_is_ignored() -> None:
    assert _parse_version("v3.5.0-beta.3+build.42") == _parse_version("v3.5.0-beta.3")


@pytest.mark.parametrize("tag", ["v3.5.0-beta.3", "3.5.0-rc.1", "v1.0.0-alpha"])
def test_is_prerelease_true(tag: str) -> None:
    assert _is_prerelease(tag)


@pytest.mark.parametrize("tag", ["v3.5.0", "3.2.8", "v1.0.0"])
def test_is_prerelease_false(tag: str) -> None:
    assert not _is_prerelease(tag)


def test_a_destroyed_checker_does_not_raise_from_its_thread():
    """Closing the window during an update check must not throw out of the
    worker thread. The old code raised RuntimeError on the emit and then raised
    again from the error handler, surfacing as an unhandled thread exception."""
    from core.updater import UpdateChecker

    class Gone(UpdateChecker):
        def __getattribute__(self, name):
            if name in ("check_failed", "update_available", "up_to_date"):
                raise RuntimeError(
                    "wrapped C/C++ object of type UpdateChecker has been deleted")
            return super().__getattribute__(name)

    gone = Gone()
    gone._emit("up_to_date")                     # must not raise
    gone._emit("check_failed", "boom")


# ---- #142: a stable build must find the latest FULL release even when the
# ---- releases list starts with pages of beta tags -------------------------
class _Recorder:
    def __init__(self):
        self.events = []

    def hook(self, checker):
        checker.update_available.connect(
            lambda tag: self.events.append(("update_available", tag)))
        checker.up_to_date.connect(
            lambda: self.events.append(("up_to_date",)))
        checker.check_failed.connect(
            lambda msg: self.events.append(("check_failed", msg)))


def _run_sync(checker):
    checker._run()          # the thread wrapper adds nothing to test


def test_stable_build_uses_the_latest_release_endpoint(qapp, monkeypatch):
    """Running v3.13.11 while the list's first page is all betas: the check
    must ask /releases/latest and offer the newest full release (#142)."""
    import core.updater as U
    monkeypatch.setattr(U, "APP_VERSION", "3.13.11")
    urls = []

    def fetch(url):
        urls.append(url)
        assert url == U._LATEST_API, "stable build paged the releases list"
        return {"tag_name": "v3.14.7", "prerelease": False}

    checker = U.UpdateChecker()
    monkeypatch.setattr(checker, "_fetch", fetch)
    rec = _Recorder(); rec.hook(checker)
    _run_sync(checker)
    qapp.processEvents()
    assert rec.events == [("update_available", "v3.14.7")], rec.events


def test_stable_build_on_the_latest_release_is_up_to_date(qapp, monkeypatch):
    import core.updater as U
    monkeypatch.setattr(U, "APP_VERSION", "3.14.7")
    checker = U.UpdateChecker()
    monkeypatch.setattr(checker, "_fetch",
                        lambda url: {"tag_name": "v3.14.7"})
    rec = _Recorder(); rec.hook(checker)
    _run_sync(checker)
    qapp.processEvents()
    assert rec.events == [("up_to_date",)], rec.events


def test_beta_build_still_sees_beta_tags_from_the_list(qapp, monkeypatch):
    import core.updater as U
    monkeypatch.setattr(U, "APP_VERSION", "3.14.8-beta.219")
    checker = U.UpdateChecker()
    monkeypatch.setattr(checker, "_fetch", lambda url: [
        {"tag_name": "v3.14.8-beta.220", "prerelease": True},
        {"tag_name": "v3.14.7", "prerelease": False},
    ])
    rec = _Recorder(); rec.hook(checker)
    _run_sync(checker)
    qapp.processEvents()
    assert rec.events == [("update_available", "v3.14.8-beta.220")], rec.events


def test_stable_build_with_no_full_release_gets_a_plain_answer(qapp, monkeypatch):
    """/releases/latest 404s when only pre-releases exist — the message must
    say so instead of the misleading 'No release tag found'."""
    import io
    from urllib.error import HTTPError
    import core.updater as U
    monkeypatch.setattr(U, "APP_VERSION", "3.13.11")

    def fetch(url):
        raise HTTPError(url, 404, "Not Found", hdrs=None, fp=io.BytesIO(b""))

    checker = U.UpdateChecker()
    monkeypatch.setattr(checker, "_fetch", fetch)
    rec = _Recorder(); rec.hook(checker)
    _run_sync(checker)
    qapp.processEvents()
    assert rec.events == [("check_failed",
                           "No finished release is published yet.")], rec.events
