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
    if "-" in want:
        # A PRE-RELEASE DOES NOT OWN THE BADGE, and the first version of this
        # test assumed it did. The badge is the first thing a visitor reads and
        # it advertises the STABLE release; a CI job syncs it when one is
        # tagged. On a beta branch `APP_VERSION` is ahead of that on purpose,
        # so demanding they agree turns the badge into a lie about what a
        # visitor can download. Measured on `feature/182-compliance-sets`: the
        # app said 4.3.0-beta.3 and the badge, correctly, said 4.2.4.
        #
        # What still has to hold is that the badge names a real version.
        for got in badges:
            assert re.fullmatch(r"\d+\.\d+\.\d+", got), (
                f"the README badge says {got!r}, which is not a released "
                "version number")
        return
    for got in badges:
        assert got == want, (
            f"the README badge says {got!r} and the app says {want!r}. "
            "Bump the badge in the same commit as core/version.py.")
