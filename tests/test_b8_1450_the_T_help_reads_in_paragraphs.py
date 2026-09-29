"""B8-1450: the -T help of Measure reads in whole paragraphs in every language.

The English source is hard-wrapped at about sixty characters. The translations
kept hard breaks of their own, so the German help window showed one-word lines
("gleichmäßig", "Deshalb", "den") between full ones. Every translation is now
eight paragraphs with no break inside them, except after the two headings
("WHY THAT IS WORTH HAVING", "CHOOSING A VALUE"), and the window wraps them.
The English source is untouched: it is the catalogue key.

MUTATION: put a "\\n" back in the middle of any sentence of any catalogue's
value and the test for that language fails.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
PREFIX = "How much colour variation ChromIQ accepts WITHIN a\nsingle patch."
CATALOGUES = sorted((ROOT / "data" / "i18n").glob("*.json"))
HEADING_PARAGRAPHS = {1 + 1, 1 + 2}   # paragraphs 3 and 4, counted from 1


def _value(path: Path) -> str:
    cat = json.loads(path.read_text(encoding="utf-8"))
    keys = [k for k in cat if k.startswith(PREFIX)]
    assert len(keys) == 1, f"{path.name}: the -T help key is missing"
    return cat[keys[0]]


def test_the_english_source_is_still_the_key():
    src = (ROOT / "ui" / "tabs" / "tab_measure.py").read_text(encoding="utf-8")
    assert "accepts WITHIN a" in src


@pytest.mark.parametrize("path", CATALOGUES, ids=lambda p: p.stem)
def test_no_line_break_inside_a_paragraph(path):
    paragraphs = _value(path).split("\n\n")
    assert len(paragraphs) == 8, (
        f"{path.stem}: the -T help has {len(paragraphs)} paragraphs, not 8")
    for i, para in enumerate(paragraphs):
        allowed = 1 if i in HEADING_PARAGRAPHS else 0
        assert para.count("\n") == allowed, (
            f"{path.stem}: paragraph {i + 1} of the -T help breaks a line "
            f"inside itself: {para[:80]!r}")
