"""Nothing found for beta 8 may be quietly forgotten.

`docs/beta8_open_items.md` is the register of everything this round turned up.
It is only worth having if something enforces it, so:

* **the everyday tier** fails when the register is internally dishonest — a
  `FIXED` item naming a test that does not exist, or a `DEFERRED` item with
  nobody's name against it. Those are the two ways a register rots into a
  comfort blanket;
* **the release tier** (`pytest --runslow`, which CLAUDE.md calls THE RELEASE
  GATE) fails while any item marked `blocks release: yes` is still `OPEN`. So
  the gate itself refuses to go green on a beta that still has known holes,
  and nobody has to remember to check.

Why this exists at all: CLAUDE.md already records what a stale document costs
here. The "use `-n 4`, and do not raise it" note was true when written, wrong
three days later, and nobody came back to it for sixteen days. A list that is
only read by people is a list that goes quietly out of date; a list the suite
reads cannot.
"""
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
REGISTER = ROOT / "docs" / "beta8_open_items.md"
TESTS = ROOT / "tests"

_STATUSES = {"FIXED", "DEFERRED", "OPEN", "VERIFIED"}
#: `VERIFIED` exists for the one kind of item a test cannot guard: the release
#: evidence itself. "A green --runslow and a clean sweep were produced on the
#: final tree" is an ACT, not a property, and demanding a test name for it would
#: only invite a fake one. So it is held to a stricter bar instead — it must
#: name the COMMAND that was run and carry the NUMBERS that came back, so the
#: claim can be re-run and contradicted rather than believed.
_ITEM = re.compile(r"^### (B8-\d+)\s*·\s*(.+)$")


def _field(block: str, name: str) -> str:
    m = re.search(rf"^- {re.escape(name)}:\s*(.*?)(?=\n- |\Z)", block,
                  re.M | re.S)
    return (m.group(1).strip() if m else "")


def _items():
    """Every ``### B8-nn`` block, as ``(id, title, body)``."""
    text = REGISTER.read_text(encoding="utf-8")
    out, cur = [], None
    for line in text.splitlines(keepends=True):
        m = _ITEM.match(line.rstrip("\n"))
        if m:
            if cur:
                out.append(cur)
            cur = [m.group(1), m.group(2), ""]
        elif cur:
            cur[2] += line
    if cur:
        out.append(cur)
    return out


def _all_test_names() -> set[str]:
    names = set()
    for p in TESTS.rglob("test_*.py"):
        names |= set(re.findall(r"^def (test_\w+)", p.read_text(
            encoding="utf-8", errors="replace"), re.M))
    return names


def test_the_register_exists_and_has_items():
    assert REGISTER.is_file(), f"{REGISTER} is gone — the register IS the checklist"
    assert len(_items()) >= 20, "the register has lost most of its items"


def test_no_two_items_share_an_identifier():
    """Two items with the same id is a register that quietly loses one of them.

    It happened: three agents worked in parallel on 2026-09-04, two of them
    claimed **B8-53**, and nothing noticed — not the suite, not the review. The
    id is how every other document, every evidence list and every cross-
    reference points at an item, so a duplicate does not merely look untidy: a
    sentence saying "superseded by B8-53" stops having one meaning, and the
    later block silently inherits the earlier one's references.

    The fix is cheap and the failure mode is expensive, which is exactly the
    kind of thing this file exists for.
    """
    seen: dict[str, str] = {}
    dupes = []
    for ident, title, _body in _items():
        if ident in seen:
            dupes.append(f"{ident} used twice: {seen[ident]!r} and {title!r}")
        else:
            seen[ident] = title
    assert not dupes, (
        "\n  " + "\n  ".join(dupes)
        + "\n\nGive the LATER item the next free id and update anything that "
          "points at it. Do not renumber the earlier one — other documents may "
          "already cite it.")


def test_every_item_has_a_status_we_understand():
    bad = []
    for ident, title, body in _items():
        st = _field(body, "status")
        if st not in _STATUSES:
            bad.append(f"{ident} ({title}): status {st!r} not in {sorted(_STATUSES)}")
        if _field(body, "blocks release") not in ("yes", "no"):
            bad.append(f"{ident}: 'blocks release' must be yes or no")
    assert not bad, "\n  " + "\n  ".join(bad)


def test_nothing_is_called_fixed_without_a_test_that_proves_it():
    """A fix with no guard is a fix that comes back. "I checked it by hand" is
    not evidence — this session alone produced two fixture bugs that nearly
    became filed faults, and a library-level result that the user disproved by
    running the real app."""
    known = _all_test_names()
    bad = []
    for ident, title, body in _items():
        if _field(body, "status") != "FIXED":
            continue
        named = re.findall(r"test_\w+", _field(body, "evidence"))
        if not named:
            bad.append(f"{ident} ({title}): FIXED but names no test")
            continue
        missing = [n for n in named if n not in known]
        if missing:
            bad.append(f"{ident} ({title}): names tests that do not exist: {missing}")
    assert not bad, "\n  " + "\n  ".join(bad)


def test_a_verified_item_names_the_command_it_ran_and_what_came_back():
    """`VERIFIED` is for the release evidence, which no test can guard. It buys
    its exemption by being MORE specific, not less: the command has to be there
    so anyone can re-run it, and the numbers have to be there so a later run can
    disagree with it."""
    bad = []
    for ident, title, body in _items():
        if _field(body, "status") != "VERIFIED":
            continue
        ev = _field(body, "evidence")
        if "pytest" not in ev and ".sh" not in ev:
            bad.append(f"{ident} ({title}): VERIFIED but names no command")
        if not re.search(r"\d{3,}\s+passed|\d+\s+PASS", ev):
            bad.append(f"{ident} ({title}): VERIFIED but carries no result numbers")
    assert not bad, "\n  " + "\n  ".join(bad)


def test_nothing_is_deferred_without_somebody_deciding_it_and_saying_why():
    """A deferral nobody owns is an item that has been forgotten with extra
    steps. Basti's standing rule is that design calls are his, so a DEFERRED
    row has to name the person and carry the reasoning that person needs."""
    bad = []
    for ident, title, body in _items():
        if _field(body, "status") != "DEFERRED":
            continue
        if not _field(body, "decided by"):
            bad.append(f"{ident} ({title}): DEFERRED but nobody decided it")
        if len(_field(body, "because")) < 40:
            bad.append(f"{ident} ({title}): DEFERRED with no real reason given")
    assert not bad, "\n  " + "\n  ".join(bad)


@pytest.mark.slow
def test_no_release_blocking_item_is_still_open():
    """THE GATE. `pytest --runslow` is what must be green before anything ships
    (CLAUDE.md), so this is where "beta 8 still has known holes" belongs. It is
    not in the everyday tier deliberately: day-to-day work should not be red
    just because the release is not ready yet."""
    open_blockers = [
        f"{ident}  {title}"
        for ident, title, body in _items()
        if _field(body, "blocks release") == "yes"
        and _field(body, "status") == "OPEN"
    ]
    assert not open_blockers, (
        f"\n{len(open_blockers)} release-blocking item(s) still OPEN in "
        f"docs/beta8_open_items.md:\n  " + "\n  ".join(open_blockers)
        + "\n\nFix them, or move them to DEFERRED with a name and a reason. "
          "Do not delete the row.")
