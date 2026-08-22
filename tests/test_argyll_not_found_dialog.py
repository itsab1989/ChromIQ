"""The first-launch "ArgyllCMS not found" message must name places we LOOK.

THE BUG THIS EXISTS TO PREVENT. The message used to tell every user, on every
platform, to "move the folder to /Applications" — a path that does not exist on
Windows, so the first instruction a new Windows user read was impossible to
follow. The first attempt to fix that then made the same mistake twice more:
it told macOS users to use ``~/Applications`` (only ``/Applications`` gets the
versioned scan — the home arm is the literal ``~/Applications/Argyll/bin``) and
told Linux users to unpack to ``/opt/argyll`` (there is no versioned scan on
Linux at all; the candidate is the literal ``/opt/argyll/bin``). Both would have
sent the user somewhere ChromIQ never looks, which is the same bug wearing a
different hat.

So this does not check the wording. It extracts every filesystem path the
message actually shows and asserts each one is somewhere
``argyll_candidate_dirs()`` searches on that platform — the two lists cannot
drift apart without a test failing.
"""
from __future__ import annotations

import os
import re

import pytest

pytest.importorskip("PyQt6")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from core import platform_paths                                   # noqa: E402
from ui.main_window import (                                      # noqa: E402
    _ARGYLL_NOT_FOUND_MSG,
    _ARGYLL_WHERE_LINUX,
    _ARGYLL_WHERE_MACOS,
    _ARGYLL_WHERE_WINDOWS,
)

#: The monospace spans are the paths the user is told to use. PATH is the
#: environment variable, not a directory, so it is not a claim about a location.
_SPAN = re.compile(r"<span[^>]*>([^<]+)</span>")
_NOT_A_PATH = {"PATH"}


def _paths_named(message: str) -> list[str]:
    return [p for p in _SPAN.findall(message) if p not in _NOT_A_PATH]


#: The directories whose CHILDREN are scanned for a versioned ``Argyll*`` folder
#: (core/platform_paths.py:62-72 for Windows, :86-92 for macOS). Dropping the
#: unpacked ``Argyll_V3.5.0`` folder into one of these works; dropping it
#: anywhere else does not, however plausible the parent looks. Linux has NO
#: versioned scan at all, which is why it has no entry here.
_VERSION_SCANNED_ROOTS = {
    "win32": {"%localappdata%/argyllcms", "c:/program files/argyllcms"},
    "darwin": {"/applications"},
    "linux": set(),
}


def _norm(p: str) -> str:
    return p.replace("\\", "/").rstrip("/").lower()


def _candidates_for(monkeypatch, platform: str) -> list[str]:
    """argyll_candidate_dirs() as it would be on *platform*, normalised."""
    monkeypatch.setattr(platform_paths.sys, "platform", platform)
    return [_norm(str(p)) for p in platform_paths.argyll_candidate_dirs()]


@pytest.mark.parametrize("platform,where", [
    ("win32", _ARGYLL_WHERE_WINDOWS),
    ("darwin", _ARGYLL_WHERE_MACOS),
    ("linux", _ARGYLL_WHERE_LINUX),
])
def test_every_place_the_message_names_is_a_place_we_search(
        monkeypatch, platform, where):
    """Each path named must be somewhere a user can actually put ArgyllCMS.

    Exactly two things qualify, and the distinction is the whole point:

    * the path IS a probed bin directory — the user is told to put the binaries
      themselves there (the Linux ``/opt/argyll/bin`` case); or
    * the path is a root whose children get the versioned scan, so an unpacked
      ``Argyll_V…`` folder inside it is found (the Windows and ``/Applications``
      case).

    ``~/Applications`` satisfies NEITHER — it is not scanned, and the only
    home-directory candidate is the literal ``~/Applications/Argyll/bin``. An
    earlier draft named it anyway, and a looser check here waved it through.
    """
    candidates = _candidates_for(monkeypatch, platform)
    assert candidates, f"no candidate dirs at all for {platform}"
    scanned = _VERSION_SCANNED_ROOTS[platform]

    for named in _paths_named(where):
        probe = _norm(named)
        home = _norm(str(platform_paths.Path.home()))
        expanded = probe.replace("~", home, 1) if probe.startswith("~") else probe

        is_probed_bin = expanded in candidates
        is_scanned_root = probe in scanned or expanded in scanned

        assert is_probed_bin or is_scanned_root, (
            f"[{platform}] the dialog tells the user to use {named!r}, but that "
            f"is neither a directory ChromIQ probes nor a root whose contents "
            f"it scans for a versioned Argyll folder. A user following the "
            f"instructions would restart and be told 'not found' again.\n"
            f"  probed: {candidates}\n  scanned roots: {sorted(scanned)}")


def test_the_message_does_not_pin_an_argyll_version():
    """A version number here would cost 12 retranslations per Argyll release.

    It lives inside a translated key, so bumping 3.5.0 -> 3.6.0 changes the
    English source, every catalogue reports a stale key, and all 12 languages
    need redoing — for a number the download page already keeps current.
    """
    for where in (_ARGYLL_WHERE_WINDOWS, _ARGYLL_WHERE_MACOS,
                  _ARGYLL_WHERE_LINUX):
        assert not re.search(r"\d+\.\d+\.\d+", where), (
            f"the message pins an ArgyllCMS version: {where!r}")


def test_the_message_composes_with_no_placeholder_left_over():
    """Whatever the platform, the user must never see a raw {url} or {where}."""
    for where in (_ARGYLL_WHERE_WINDOWS, _ARGYLL_WHERE_MACOS,
                  _ARGYLL_WHERE_LINUX):
        composed = _ARGYLL_NOT_FOUND_MSG.format(
            url=platform_paths.argyll_download_page(), where=where)
        assert "{" not in composed and "}" not in composed
        assert composed.count("<span") == composed.count("</span>")
        assert composed.count("<b>") == composed.count("</b>")
        assert composed.count("<a ") == composed.count("</a>")


@pytest.mark.parametrize("platform,page", [
    ("win32", "downloadwin.html"),
    ("darwin", "downloadmac.html"),
    ("linux", "downloadlinux.html"),
])
def test_the_download_link_is_this_platforms_page(monkeypatch, platform, page):
    """Step 1 must not send a Windows user to the macOS downloads."""
    monkeypatch.setattr(platform_paths.sys, "platform", platform)
    assert platform_paths.argyll_download_page().endswith(page)
