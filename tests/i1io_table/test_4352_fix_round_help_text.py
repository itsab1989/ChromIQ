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


def test_s6_every_language_has_the_seven_paragraphs():
    # Six paragraphs at 4.3.52; 4.3.57 (item 11) added a seventh on purpose: the switch needs no
    # restart. A catalogue that has the key must keep every paragraph break the English has.
    # A catalogue still WITHOUT the key falls back to English (whole and correct); that gap is
    # test_i18n::test_catalog_is_complete's to report, not a second red here for the same cause.
    assert HELP.count("\n\n") == 6
    root = Path(__file__).resolve().parents[2] / "data" / "i18n"
    translated = 0
    for path in sorted(root.glob("*.json")):
        cat = json.loads(path.read_text(encoding="utf-8"))
        if HELP not in cat:
            continue
        translated += 1
        assert cat[HELP].count("\n\n") == HELP.count("\n\n"), path.name
        assert "{countdown}" in cat[HELP], path.name
    assert translated >= 1     # German at least (de.json)
