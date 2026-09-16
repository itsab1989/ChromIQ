"""A `B8-NNN` in the code must be the entry it says it is.

WHAT THIS GUARDS, AND HOW IT WAS FOUND
--------------------------------------
Three features were built on three branches at once and merged by hand. Two of
them had numbered their register entries from the same free block, so ten of the
layout branch's entries were renumbered on the merge: `B8-250` … `B8-257` became
`B8-265` … `B8-272`. The merge note in `docs/beta8_open_items.md` says the
references were moved with them. Six were not, and they split into two kinds:

* **Four that point at nothing.** `B8-239` said *"what was implemented is
  B8-255"*, `B8-240` said *"B8-256, and B8-254 then narrowed it"*, `B8-242` said
  *"See B8-257"*. None of those four numbers exists in the merged register at
  all, so the trail from an ANSWERED question to its settlement simply stopped.
* **Two that point at the WRONG entry, which is worse, because they read as
  correct.** `workflow/layout_engine/raster.py` and §R8 of
  `docs/design/row_label_geometry.md` both said the held "Size = auto" decision
  is carried by `B8-250`. After the merge `B8-250` is the Measurement Report's
  "Saved reports" row, and the auto-size decision is `B8-265` — the one entry
  the owner has deliberately left unshipped, because shipping it costs three
  Letter hexagonal presets an extra sheet. A pointer that leads somewhere else
  is how a held decision gets lost.

So this file asks two questions of the whole tree: does every number cited name
an entry that exists, and does the number beside the auto-size decision name the
entry that is actually about it. The second is asked by the entry's HEADING and
not by its number, so a future renumber moves the answer with it instead of
breaking this test.
"""
from __future__ import annotations

import pathlib
import re

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
REGISTER = ROOT / "docs" / "beta8_open_items.md"

#: A note that RECORDS a renumber has to be allowed to write the old numbers
#: down; that is the whole point of it. Two places in the register do that and
#: both are taken out before it is scanned: every HTML comment (where the
#: merge note lives), and any entry whose own HEADING says it is about a
#: renumber (where the fault is written up).
_HTML_COMMENT = re.compile(r"<!--.*?-->", re.S)
_RENUMBER_ENTRY = re.compile(r"^### B8-\d+ · [^\n]*renumber[^\n]*$.*?(?=^### |\Z)",
                             re.S | re.M | re.I)


def _register_text() -> str:
    """The register with the two records of a renumber taken out."""
    t = REGISTER.read_text(encoding="utf-8")
    return _RENUMBER_ENTRY.sub(" ", _HTML_COMMENT.sub(" ", t))

#: `B8-1xx` and friends: a deliberate wildcard, not a citation.
_CITATION = re.compile(r"\bB8-(\d+)\b")

_SEARCHED = ("ui", "workflow", "core", "tests", "scripts", "docs")


def _defined() -> set:
    return set(re.findall(r"^### (B8-\d+)", REGISTER.read_text(encoding="utf-8"),
                          flags=re.M))


#: This file's own prose names the numbers the merge retired, because that is
#: what it is FOR. Same exemption the register's merge note gets, and for the
#: same reason: a record of a renumber has to be allowed to write the old
#: numbers down.
_SELF = pathlib.Path(__file__).resolve()


def _files():
    for d in _SEARCHED:
        for p in sorted((ROOT / d).rglob("*")):
            if p.suffix in (".py", ".md") and p.is_file() and p != _SELF:
                yield p


def _citations():
    """``[(path, id)]`` for every B8 number written anywhere in the tree."""
    out = []
    for p in _files():
        try:
            text = p.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):       # pragma: no cover
            continue
        if p == REGISTER:
            text = _register_text()
        for m in _CITATION.finditer(text):
            out.append((p, f"B8-{m.group(1)}"))
    return out


def test_the_sweep_is_not_vacuous():
    """Guard the guard: a sweep that finds nothing would pass for ever."""
    cites = _citations()
    assert len(cites) > 200, f"only {len(cites)} citations found; the sweep is broken"
    assert len(_defined()) > 200, "the register was not parsed"


def test_every_b8_citation_names_an_entry_that_exists():
    """MUTATION: change any `B8-265` below back to `B8-250` and this stays
    green (250 exists) — which is exactly why the next test is also here.
    Change one to `B8-999` and this goes red."""
    defined = _defined()
    dangling = sorted({(p.relative_to(ROOT).as_posix(), i)
                       for p, i in _citations() if i not in defined})
    assert not dangling, (
        "these cite a register entry that does not exist:\n"
        + "\n".join(f"    {f}: {i}" for f, i in dangling))


def _entry_id_whose_heading_contains(needle: str) -> str:
    text = REGISTER.read_text(encoding="utf-8")
    hits = [m.group(1) for m in
            re.finditer(r"^### (B8-\d+) · (.*)$", text, flags=re.M)
            if needle in m.group(2)]
    assert len(hits) == 1, (
        f"{len(hits)} register headings contain {needle!r}: {hits}")
    return hits[0]


#: Where the held "Size = auto" decision is written down outside the register:
#: the code that implements the un-changed behaviour, and §R8 of the design
#: document that records the proposal. Both are prose ABOUT that decision.
_AUTO_SIZE_FILES = (
    pathlib.Path("workflow") / "layout_engine" / "raster.py",
    pathlib.Path("docs") / "design" / "row_label_geometry.md",
)

#: A line that is talking about the held decision. Neither file cites only
#: this entry (`row_label_geometry.md` also cites B8-38 and B8-14), so the
#: lines are picked by what they SAY.
_ABOUT_THE_HELD_DECISION = re.compile(
    r"carries the measurement|carries$|auto.{0,60}size|size.{0,60}auto",
    re.I)


def test_the_held_auto_size_decision_points_at_its_own_entry():
    """The number beside the held decision must be the entry ABOUT it.

    Asked by the entry's HEADING, so a future renumber moves the expected
    answer with it instead of breaking this test.

    MUTATION: put `B8-250` back in either file and this goes red, and says
    which entry it really landed on ("There was no way to see, or to remove,
    any saved report but the newest").
    """
    want = _entry_id_whose_heading_contains("Size = auto")
    reg = REGISTER.read_text(encoding="utf-8")
    defined = _defined()
    found, bad = 0, []
    for rel in _AUTO_SIZE_FILES:
        for line in (ROOT / rel).read_text(encoding="utf-8").splitlines():
            if not (_CITATION.search(line)
                    and _ABOUT_THE_HELD_DECISION.search(line)):
                continue
            found += 1
            for m in _CITATION.finditer(line):
                got = f"B8-{m.group(1)}"
                if got == want:
                    continue
                head = next((mm.group(0) for mm in re.finditer(
                    rf"^### {got} · .*$", reg, flags=re.M)), "")
                bad.append(
                    f"{rel.as_posix()} cites {got} for the held "
                    f"“Size = auto” decision, which is {want}. "
                    + (head or f"{got} is not an entry at all")
                    if got in defined or True else "")
    assert found >= 3, (
        f"only {found} line(s) about the held decision carry a citation; "
        f"the locator has stopped finding them")
    assert not bad, "\n".join(bad)


def test_a_superseded_entry_points_forward_to_a_real_settlement():
    """`superseded by: B8-N` must name an entry, and a later one.

    The three ANSWERED entries this round repaired had a CORRECT
    `superseded by:` line and a BODY that still named the number the merge
    retired, so the forward pointer on its own never proved the trail whole —
    which is why the sweep above exists as well as this.
    """
    text = _register_text()
    defined = _defined()
    bad = []
    for b in re.split(r"^### ", text, flags=re.M):
        m = re.match(r"(B8-\d+)", b)
        if not m:
            continue
        here = m.group(1)
        for s_id in re.findall(r"superseded by:\s*(B8-\d+)", b):
            if s_id not in defined:
                bad.append(f"{here} is superseded by {s_id}, which does not exist")
            elif int(s_id[3:]) <= int(here[3:]):
                bad.append(f"{here} is superseded by {s_id}, which is not later")
    assert not bad, "\n".join(bad)
