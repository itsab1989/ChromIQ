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
    exec((ROOT / "core" / "version.py").read_text(encoding="utf-8"), ns)
    return ns["APP_VERSION"]


def test_the_beta_link_points_at_this_version():
    version = _app_version()
    if "beta" not in version:
        return          # a stable release: the Download buttons cover it
    links = re.findall(r"releases/tag/(v[0-9][^\"']*)", SITE.read_text(encoding="utf-8"))
    assert links, "the site names no release tag at all"
    for tag in links:
        assert tag == f"v{version}", (
            f"the site offers {tag} while this build is v{version} — tagging "
            "now would make the live page serve the older build")


def test_the_download_buttons_still_point_at_the_stable_release():
    """The opposite mistake: the main Download buttons must NOT chase a beta."""
    text = SITE.read_text(encoding="utf-8")
    assert text.count("releases/latest") >= 1, (
        "the Download buttons should offer the stable release, not a beta")


def test_the_site_says_how_many_presets_there_really_are():
    """The same rot, one number over: the page advertises a preset count by
    hand.

    It has been wrong before. The commit before this one was titled "the site
    said 130 presets and a beta CR30" and moved it to 150; adding a single
    built-in makes it wrong again, silently, because nothing else reads it.
    The registry is the truth, so ask the registry.
    """
    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from ui.tabs.tab_chart import BUILTIN_PRESET_KEYS

    n = len(BUILTIN_PRESET_KEYS)
    text = SITE.read_text(encoding="utf-8")
    claimed = {int(m) for m in re.findall(r"(\d+) ready-made chart presets", text)}
    assert claimed, "the site no longer names a preset count at all"
    assert claimed == {n}, (
        f"docs/index.html advertises {sorted(claimed)} ready-made chart "
        f"presets; the registry holds {n}"
    )
