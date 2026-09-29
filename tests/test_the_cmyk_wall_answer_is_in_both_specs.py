"""The answer about `chartread` and CMYK belongs in BOTH binding documents.

Two design documents asked the same question in almost the same words:

  *"whether `chartread` itself accepts a CMYK chart, i.e. whether the wall is
   at measuring or only at reporting"*

It was answered on 2026-09-04 (issue #182, comment 5545838349) and the answer
never reached either document, through three challenge rounds that each noticed
and each moved on. A question left standing in a binding document is worse than
one that was never asked: the next reader is told nobody knows.

This check does not judge the answer. It pins that (a) neither document still
poses the question as open, (b) both carry the same answer, and (c) each one
says who confirmed it, because a fact established by us and not yet confirmed by
Knut or Sebastian may not be written as settled behaviour (CLAUDE.md, "Only
CONFIRMED behaviour may be written into a specification").
"""
from __future__ import annotations

from pathlib import Path

import pytest

DOCS = Path(__file__).resolve().parents[1] / "docs" / "design"
BOTH = ("verification_printing_and_target.md", "tool_availability.md")

#: The shapes the open question was written in, in each document.
STILL_OPEN = (
    "whether the wall is at measuring or only at reporting",
    "whether the wall is at measuring",
    "is the wall at measuring",
)


@pytest.mark.parametrize("name", BOTH)
def test_the_question_is_no_longer_posed_as_open(name):
    text = (DOCS / name).read_text(encoding="utf-8")
    for phrase in STILL_OPEN:
        assert phrase.lower() not in text.lower(), (
            f"{name} still asks '{phrase}'. It was answered on 2026-09-04: "
            "the wall is at reporting only.")


@pytest.mark.parametrize("name", BOTH)
def test_the_answer_is_written_in_with_where_it_came_from(name):
    text = (DOCS / name).read_text(encoding="utf-8")
    assert "the wall is at REPORTING only" in text, (
        f"{name} does not carry the answer")
    assert "chartread.c" in text, (
        f"{name} states the answer without saying where it was read; a design "
        "document must be checkable, not believed")
    assert "5545838349" in text, (
        f"{name} does not cite the comment the answer was established in")


@pytest.mark.parametrize("name", BOTH)
def test_the_answer_says_who_confirmed_it(name):
    """Nobody has. That has to be visible, not implied by silence."""
    text = (DOCS / name).read_text(encoding="utf-8")
    head, _, tail = text.partition("the wall is at REPORTING only")
    assert tail, name
    # within the same passage, not somewhere else in the document
    assert "**Confirmed by:**" in tail[:2500], (
        f"{name} states the answer without a Confirmed by line near it")
