"""A code comment must not say a message is unapproved once it is approved.

WHAT THIS CAUGHT. Six comments in the two import loaders read

    # M-IMPORT-REPLACE-FOLDER-FAILED, awaiting approval.

about four messages Basti approved on 2026-09-02 — the same day
`tests/test_message_catalogue.py:237` recorded that they "never sat in this set
for longer than one branch". `M_IMPORT_REPLACE_FOLDER_FAILED.approved` is True,
and the notes beside every call site said otherwise.

WHY IT IS WORTH A TEST. `test_message_catalogue.py` guards the one direction
that can reach a user: an unapproved message must not be shown. Nothing guarded
the other one, and the other one is what the next reader acts on. "Awaiting
approval" is the note that stops an agent touching a string; left standing over
an approved message it either freezes work that is free to proceed, or — worse —
teaches the reader that these notes are decoration and can be ignored, which is
how the real ones stop working.

The scan is over `ui/`, `workflow/` and `core/`: a comment about a message can
live anywhere a message is used.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from workflow import measurement_messages as M

ROOT = Path(__file__).resolve().parent.parent
SCAN = ("ui", "workflow", "core")

#: `M-SOMETHING … awaiting approval`, on one line, with the id first. Kept
#: tight (60 characters between the two) so a paragraph that happens to mention
#: an id and, four sentences later, some other message's approval status does
#: not read as one claim.
_NOTE = re.compile(r"(M-[A-Z0-9][A-Z0-9-]*)[^\n]{0,60}?awaiting approval",
                   re.IGNORECASE)


def _files():
    for entry in SCAN:
        for path in sorted((ROOT / entry).rglob("*.py")):
            if "__pycache__" in path.parts:
                continue
            yield path


def test_the_probe_matches_the_shape_it_is_looking_for():
    """THE MUTATION HAS TO BE PROVEN TO LAND.

    After the fix there are no such comments left, so the real test below
    passes over an empty set and would go on passing if the pattern were
    broken to match nothing at all. This is the pattern's own control: it must
    still find the comment in the exact form the six of them had, and must not
    fire on a line that merely mentions a message id.
    """
    hit = _NOTE.search(
        "        # M-IMPORT-REPLACE-FOLDER-CONFIRM, awaiting approval.\n")
    assert hit is not None, "the pattern no longer matches the comment it exists for"
    assert hit.group(1) == "M-IMPORT-REPLACE-FOLDER-CONFIRM"

    assert _NOTE.search("# M-IMPORT-DONE is rendered from the catalogue.") is None
    # …and it must not reach across a paragraph to pair an id with an unrelated
    # sentence about approval.
    assert _NOTE.search(
        "# M-IMPORT-DONE is rendered from the catalogue, like every other "
        "window in this module, and the reason it has to be is written out in "
        "full above. Something else entirely is awaiting approval.") is None


def test_no_comment_calls_an_approved_message_unapproved():
    offenders = []
    for path in _files():
        text = path.read_text(encoding="utf-8")
        for i, line in enumerate(text.splitlines(), 1):
            hit = _NOTE.search(line)
            if hit is None:
                continue
            mid = hit.group(1).upper()
            msg = M.CATALOGUE.get(mid)
            if msg is not None and msg.approved:
                offenders.append(
                    f"{path.relative_to(ROOT).as_posix()}:{i} says {mid} is "
                    f"awaiting approval; it is approved.\n      {line.strip()}")
    assert not offenders, (
        "a comment claims an approved message is still unapproved:\n  "
        + "\n  ".join(offenders))


@pytest.mark.parametrize("mid", ["M-IMPORT-NOT-OPENED", "M-IMPORT-FOLDER-EXISTS",
                                 "M-IMPORT-REPLACE-FOLDER-CONFIRM",
                                 "M-IMPORT-REPLACE-FOLDER-FAILED"])
def test_the_four_from_round_two_really_are_approved(mid):
    """The premise of the test above, stated so it cannot rot silently."""
    assert mid in M.CATALOGUE
    assert M.CATALOGUE[mid].approved
