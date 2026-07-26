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
