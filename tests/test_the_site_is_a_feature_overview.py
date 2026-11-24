"""The public site is an overview of what ChromIQ can do today.

Feedback of 24 Nov 2026, agreed by the owner: a promotional page shows the
current capabilities, not a history of bugs and corrections and not
instructions. The history lives in CHANGELOG.md and the release notes, the
instructions in the README and docs/. Before this rework the page carried
eighteen "New in 4.3.x" sentences and the faults of earlier versions.

MUTATION: a "New in 4.3.64: ..." sentence on the page -> red.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "docs" / "index.html"


def _text() -> str:
    html = SITE.read_text(encoding="utf-8")
    html = re.sub(r'src="data:[^"]+"', 'src=""', html)
    return re.sub(r"\s+", " ", html)


def test_the_site_carries_no_version_history():
    text = _text()
    assert not re.search(r"\bNew in \d+\.\d+", text)
    assert not re.search(r"\b(?:since|from) (?:ChromIQ )?\d+\.\d+\.\d+", text)


def test_the_site_names_every_beta_instrument():
    text = _text()
    for name in ("Konica Minolta FD-9", "i1iO 2", "i1iSis", "Barbieri Spectro 100xy",
                 "dual scan", "ChnSpec CR30"):
        assert name in text, name


def test_the_site_marks_beta_features_and_says_where_they_are_switched_on():
    text = _text()
    assert text.count('class="beta"') >= 8
    assert "Preferences &rsaquo; Beta" in text


def test_the_site_links_the_guide_and_the_changelog_instead_of_repeating_them():
    text = _text()
    assert "github.com/itsab1989/ChromIQ#readme" in text
    assert "CHANGELOG.md" in text
