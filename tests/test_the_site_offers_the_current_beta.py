"""The public site must not hand people the previous build.

`docs/index.html` IS the published site (GitHub Pages serves `docs/` from
master), and its CR30 section links to a specific beta by tag, because
`/releases/latest` on GitHub EXCLUDES pre-releases and would hand a reader the
last stable one instead — with no CR30 support at all.

A hand-maintained version number in a public page rots the moment somebody tags
without remembering it. This is that reminder, and it fails the gate rather than
the user: the beta-3 review caught the link still pointing at beta 2, one commit
before it would have gone live.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "docs" / "index.html"


def _app_version() -> str:
    ns: dict = {}
    exec((ROOT / "core" / "version.py").read_text(), ns)
    return ns["APP_VERSION"]


def test_the_beta_link_points_at_this_version():
    version = _app_version()
    if "beta" not in version:
        return          # a stable release: the Download buttons cover it
    links = re.findall(r"releases/tag/(v[0-9][^\"']*)", SITE.read_text())
    assert links, "the site names no release tag at all"
    for tag in links:
        assert tag == f"v{version}", (
            f"the site offers {tag} while this build is v{version} — tagging "
            "now would make the live page serve the older build")


def test_the_download_buttons_still_point_at_the_stable_release():
    """The opposite mistake: the main Download buttons must NOT chase a beta."""
    text = SITE.read_text()
    assert text.count("releases/latest") >= 1, (
        "the Download buttons should offer the stable release, not a beta")
