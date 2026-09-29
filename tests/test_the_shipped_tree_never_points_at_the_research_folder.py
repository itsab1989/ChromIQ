"""What ships must not advertise what does not.

ChromIQ is public, GPL, and its source is read by anyone who wants to read it.
The research folder beside it is not public: it holds the working notes for
#182, including the transcription work behind the ISO limit sets. Basti's
standing rule is that no ISO 12647-7 or -8 VALUE appears anywhere in what
ships; standard NAMES and clause citations are allowed.

A comment that says "see the research folder's THE-MATRIX.md", sitting directly
beneath a list of ISO clause references, keeps the letter of that rule and
breaks its point: it tells a reader that a private file of that name exists and
what it contains. A binding design document did the same with
`CS-METRICS-SPEC.md`, which is not tracked, so it cited a source nobody on the
project can open.

Both are removed. This keeps them out.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

#: Where a reader of the shipped tree could follow a pointer.
SHIPPED = ["workflow", "ui", "core", "scripts", "data", "docs", "README.md"]

#: Phrases that name the private folder or a file that lives only in it.
FORBIDDEN = (
    "research folder",
    "THE-MATRIX",
    "CS-METRICS-SPEC",
)


def _files():
    for name in SHIPPED:
        p = ROOT / name
        if p.is_file():
            yield p
        elif p.is_dir():
            for f in p.rglob("*"):
                if f.is_file() and f.suffix in {".py", ".md", ".json", ".yaml", ".yml"}:
                    yield f


#: The ONE place the phrase may stand, and why.
#:
#: `issue_182_answers.md` quotes Basti's own written answers verbatim, and one
#: of them says where a source bundle was preserved. Editing a quotation to
#: tidy the tree would falsify the record of what he actually decided, which is
#: worse than the thing the rule is guarding against: the document is a design
#: record read by this project, not a comment in the source a stranger reads
#: beside ISO clause numbers. Anything else needs a reason as good as this one.
ALLOWED = {
    ("docs/design/issue_182_answers.md", "research folder"),
}


@pytest.mark.parametrize("phrase", FORBIDDEN)
def test_no_shipped_file_points_at_the_research_folder(phrase):
    hits = []
    for f in _files():
        try:
            text = f.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for n, line in enumerate(text.splitlines(), 1):
            rel = str(f.relative_to(ROOT))
            if phrase.lower() in line.lower() and (rel, phrase) not in ALLOWED:
                hits.append(f"{rel}:{n}: {line.strip()}")
    assert not hits, (
        f"{len(hits)} shipped line(s) name {phrase!r}. What ships must not "
        "advertise the private research folder or a file that lives only in "
        "it, least of all beside ISO clause citations:\n  "
        + "\n  ".join(hits))


def test_the_iso_rows_still_cite_the_standards_themselves():
    """The REMEDY IS NOT SILENCE. Citing the standard by name and clause is
    allowed and is how a reader checks our structure; only the pointer at the
    private folder had to go. If this ever goes red because the citations were
    stripped too, put them back rather than deleting this test."""
    text = (ROOT / "workflow" / "compliance_sets.py").read_text(encoding="utf-8")
    assert re.search(r"ISO 12647-7:2016[\s#:]+Table", text), (
        "the ISO 12647-7 clause citation is gone from the row structure")
    assert "ISO 12647-8:2021" in text
