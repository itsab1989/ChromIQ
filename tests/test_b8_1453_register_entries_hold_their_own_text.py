"""B8-1453 (beta 45 challenge 1, F7): an entry of the register held another
entry's text. c96a5519 wrote B8-1414's old OPEN body under B8-1417's heading
and appended B8-1417's own "found by" to B8-1448; 2bfe8bea repaired it by
hand. Nothing would have caught it a second time.

An entry's account of itself (what found it, why it happened, what was
changed, what it guards) is its own. Two entries may share a list of tests or
a proof folder, and several superseded entries share the sentence that
superseded them, so those lines are allowed to repeat; these are not.
"""
from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path

REGISTER = Path(__file__).resolve().parent.parent / "docs" / "beta8_open_items.md"

#: the lines that tell an entry's own story
OWN = ("- found by:", "- cause", "- fix", "- guard:", "- answered:",
       "- rates,", "- on screen:")


def _entries() -> "list[tuple[str, list[str]]]":
    """``(key, bullets)`` per entry; a bullet wrapped over several lines is
    one bullet (older entries wrap theirs)."""
    text = REGISTER.read_text(encoding="utf-8")
    out = []
    for part in re.split(r"(?m)^### ", text)[1:]:
        head, _sep, body = part.partition("\n")
        bullets: "list[str]" = []
        for line in body.splitlines():
            if line.startswith("  ") and bullets:
                bullets[-1] += " " + line.strip()
            else:
                bullets.append(line)
        out.append((head.split(" ", 1)[0], bullets))
    return out


def test_no_entry_tells_another_entrys_story():
    """MUTATION, proven red: copy B8-1414's "found by" line under B8-1417
    (what c96a5519 did)."""
    seen = defaultdict(set)
    for key, lines in _entries():
        for line in lines:
            if line.startswith(OWN) and len(line) > 60:
                seen[line].add(key)
    shared = {line[:90]: sorted(keys) for line, keys in seen.items()
              if len(keys) > 1}
    assert not shared, shared


def test_no_entry_carries_a_second_story():
    """An entry has one "found by" and one "where". c96a5519
    appended B8-1417's found-by and where to B8-1448, which then carried two
    of each; and B8-1417's own body was B8-1414's OLD text, which had been
    reworded since, so no line of it matched B8-1414 exactly and only this
    shape shows it.

    MUTATION, proven red: the register of c96a5519 in place of this one."""
    bad = []
    for key, bullets in _entries():
        for lead in ("- found by:", "- where:"):
            n = sum(1 for b in bullets if b.startswith(lead))
            if n > 1:
                bad.append((key, lead, n))
    assert not bad, bad


def test_every_entry_is_listed_once():
    """MUTATION, proven red: a second "### B8-1417" heading."""
    keys = [k for k, _lines in _entries() if k.startswith("B8-")]
    dup = sorted({k for k in keys if keys.count(k) > 1})
    assert not dup, dup
