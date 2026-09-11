"""The README's version badge is the first thing a visitor reads, and nothing
kept it honest.

It said 4.2.2 across two releases while `core/version.py` had moved on, because
a badge is a URL in a block of HTML and nobody looks at it during a release. A
wrong number there is worse than no number: it tells a reader the project is
older and quieter than it is, and it is the one version statement that is
visible without downloading anything.

This is deliberately narrow. It pins the badge to `APP_VERSION` and nothing
else, so a release only has to keep one file right and this file says when it
did not.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _app_version() -> str:
    text = (ROOT / "core" / "version.py").read_text(encoding="utf-8")
    m = re.search(r'APP_VERSION\s*=\s*"([^"]+)"', text)
    assert m, "core/version.py no longer declares APP_VERSION as a literal"
    return m.group(1)


def test_the_badge_and_app_version_agree():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    badges = re.findall(r"badge/version-([0-9][^-\s\"]*)-", readme)
    assert badges, (
        "README.md no longer carries a version badge of the form "
        "'badge/version-X.Y.Z-'. If the badge moved, move this test with it "
        "rather than deleting it.")
    want = _app_version()
    # A pre-release version carries a suffix the badge may render differently;
    # compare the release part, which is the part a reader judges by.
    want_release = want.split("-", 1)[0]
    for got in badges:
        assert got in (want, want_release), (
            f"the README badge says {got!r} and the app says {want!r}. "
            "Bump the badge in the same commit as core/version.py.")
