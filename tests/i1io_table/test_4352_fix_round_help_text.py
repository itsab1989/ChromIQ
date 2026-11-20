"""4.3.52 fix round, S-2 and S-6 of the independent safety review: the help text beside
"Guided, step by step measurement" says plainly what the person gives up with it off."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from workflow import measurement_messages as M

HELP = M.M_I1IO_GUIDED_HELP.body


@pytest.mark.parametrize("words", [
    "Nobody is asked before the arm moves.",                          # what is given up
    "set the arm's height for your paper",                            # S-2: the first page's
    "take everything off the bed except your sheet",                  # reminders
    "parts of the table it has not visited before without asking",    # S-6 (b)
    "when not every patch was read",                                  # S-6 (c)
    "After a Stop, a problem report or a fault, ChromIQ asks every question again",  # MUST-1
    "Keep that power switch in reach.",
    "press Stop first, then End measurement",                         # N-1
    "Please stay beside the table",
])
def test_s6_the_help_text_says_it(words):
    assert words in HELP


def test_s6_every_language_has_the_six_paragraphs():
    root = Path(__file__).resolve().parents[2] / "data" / "i18n"
    for path in sorted(root.glob("*.json")):
        cat = json.loads(path.read_text(encoding="utf-8"))
        assert HELP in cat, path.name
        assert cat[HELP].count("\n\n") == HELP.count("\n\n") == 5, path.name
        assert "{countdown}" in cat[HELP], path.name
