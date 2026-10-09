#!/usr/bin/env python3
"""Point the Homebrew tap's casks at a new ChromIQ release.

The tap (github.com/itsab1989/homebrew-chromiq) has two casks:

* ``chromiq``      - the newest STABLE release; a plain
  ``brew install --cask itsab1989/chromiq/chromiq`` never installs a beta.
* ``chromiq@beta`` - the newest release of either kind.

Called by the release workflow (``build-release.yml``, job ``homebrew``) once
every macOS DMG of the release is uploaded::

    python3 scripts/update_homebrew_tap.py --tap <checkout> --tag v4.3.3 \
        --arm-sha <sha256 of the arm64 DMG> --intel-sha <sha256 of the x86_64 DMG>

A stable tag updates ``chromiq`` and, when it is newer than the beta the beta
cask carries, ``chromiq@beta`` too, so beta users are never left on a beta
older than the stable release. A pre-release tag (``-alpha``, ``-beta``,
``-rc``, ``-pre``) updates ``chromiq@beta`` only. A cask is never moved to an
older version (a hotfix of an older line leaves it alone). A cask already AT
the tag's version gets the checksums it is given: re-running a release
rebuilds and re-uploads its DMGs (``gh release upload --clobber``), and a
cask left with the first build's checksums would refuse to install. When the
DMGs did not change, the rewrite is identical and the workflow commits
nothing.

Homebrew downloads its own copy of each DMG, ``ChromIQ-macOS-<arch>_v<ver>
_homebrew.dmg``: the same bytes as the normal DMG (so the same checksum),
uploaded under a second name so the download statistics can tell a Homebrew
install from a download by hand. Releases before 4.3.3-beta.17 have no such
files, so the casks keep the plain name until this script writes a newer
version into them: it rewrites the url line to the ``_homebrew`` name at the
same time as the version and the checksums, never earlier.

Pure standard library: the version order is the same as ``core/updater.py``'s
``_parse_version`` (SemVer precedence, a final release above its betas), kept
here as a copy because that module needs Qt; a test holds the two equal.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

_VERSION_RE = re.compile(
    r"^v?(\d+(?:\.\d+)*)(?:-([0-9A-Za-z.-]+))?(?:\+[0-9A-Za-z.-]+)?$"
)
_SHA_RE = re.compile(r"^[0-9a-f]{64}$")


def parse_version(tag: str) -> tuple:
    """Sort key for a tag: the same order as ``core.updater._parse_version``."""
    m = _VERSION_RE.match(tag.strip())
    if not m:
        return ((-1,),)
    base, pre = m.groups()
    base_nums = tuple(int(x) for x in base.split("."))
    if pre is None:
        return (base_nums, 1)
    pre_parts = tuple(
        (0, int(p)) if p.isdigit() else (1, p) for p in pre.split(".")
    )
    return (base_nums, 0, pre_parts)


def is_prerelease(tag: str) -> bool:
    m = _VERSION_RE.match(tag.strip())
    return bool(m and m.group(2))


def cask_version(text: str) -> str:
    m = re.search(r'^\s*version "([^"]+)"', text, re.M)
    if not m:
        raise ValueError("no version line in cask")
    return m.group(1)


# The DMG the cask downloads: the plain name (releases before the Homebrew
# copies existed) or the Homebrew copy. Group 1 is everything up to the
# version stamp, so a rewrite keeps the host, the tag path and the arch.
_URL_RE = re.compile(
    r'^(\s*url "https://github\.com/itsab1989/ChromIQ/releases/download/'
    r'v#\{version\}/ChromIQ-macOS-#\{arch\}_v#\{version\})(?:_homebrew)?(\.dmg")',
    re.M)
HOMEBREW_SUFFIX = "_homebrew"


def rewrite_cask(text: str, version: str, arm_sha: str, intel_sha: str) -> str:
    """The cask with its version, both checksums and its url replaced.

    The url always ends up on the ``_homebrew`` copy of the DMG, which the
    release workflow uploads for every release it hands to this script.
    """
    new, n = re.subn(r'^(\s*version ")[^"]+(")', rf"\g<1>{version}\g<2>",
                     text, count=1, flags=re.M)
    if n != 1:
        raise ValueError("no version line in cask")
    new, n = re.subn(r'(sha256 arm:\s+")[0-9a-f]{64}(")', rf"\g<1>{arm_sha}\g<2>",
                     new, count=1)
    if n != 1:
        raise ValueError("no arm sha256 in cask")
    new, n = re.subn(r'(intel:\s+")[0-9a-f]{64}(")', rf"\g<1>{intel_sha}\g<2>",
                     new, count=1)
    if n != 1:
        raise ValueError("no intel sha256 in cask")
    new, n = _URL_RE.subn(rf"\g<1>{HOMEBREW_SUFFIX}\g<2>", new, count=1)
    if n != 1:
        raise ValueError("no ChromIQ DMG url line in cask")
    return new


def casks_to_update(tag: str, stable_now: str, beta_now: str) -> list[str]:
    """Which casks a release *tag* moves forward, given their current versions."""
    new = parse_version(tag)
    out = []
    if not is_prerelease(tag) and new >= parse_version(stable_now):
        out.append("chromiq")
    if new >= parse_version(beta_now):
        out.append("chromiq@beta")
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--tap", required=True, type=Path)
    ap.add_argument("--tag", required=True)
    ap.add_argument("--arm-sha", required=True)
    ap.add_argument("--intel-sha", required=True)
    a = ap.parse_args(argv)

    for name, sha in (("--arm-sha", a.arm_sha), ("--intel-sha", a.intel_sha)):
        if not _SHA_RE.match(sha):
            ap.error(f"{name} is not a SHA-256 hex digest: {sha!r}")
    # The casks download .../download/v<version>/...: a tag without the
    # leading "v" would point them at a release that does not exist.
    if parse_version(a.tag) == ((-1,),) or not a.tag.strip().startswith("v"):
        ap.error(f"not a release tag like v4.3.3: {a.tag!r}")
    version = a.tag.strip().removeprefix("v")

    paths = {name: a.tap / "Casks" / f"{name}.rb"
             for name in ("chromiq", "chromiq@beta")}
    texts = {name: p.read_text(encoding="utf-8") for name, p in paths.items()}
    todo = casks_to_update(a.tag, cask_version(texts["chromiq"]),
                           cask_version(texts["chromiq@beta"]))
    for name in todo:
        paths[name].write_text(
            rewrite_cask(texts[name], version, a.arm_sha, a.intel_sha),
            encoding="utf-8")
        print(f"{name}: {cask_version(texts[name])} -> {version}")
    if not todo:
        print(f"nothing to update for {a.tag}: the casks are already past it")
    return 0


if __name__ == "__main__":
    sys.exit(main())
