"""The contributor guide for a new instrument must stay true, and findable.

`docs/adding_an_instrument.md` is written for people and, more often, for their
coding agents, who follow it literally. A file path that has moved, a function
that was renamed, or a pointer file that no longer links to the guide would
send them the wrong way without anybody noticing, because no other test reads
these files. So:

* every repository path, test file and ``path::symbol`` the guide, its agent
  prompt and the pointer files name (in backticks or as a link) exists;
* every shared file the FD-9 hooks (``HOOKED_FILES`` in
  `tests/test_fd9_off_changes_nothing.py`) is named in the guide's checklist,
  so a new registration point cannot be added there and forgotten here;
* every pointer file (AGENTS.md, CONTRIBUTING.md, CLAUDE.md, README.md and the
  two files under .github/) links to the guide;
* the guide's own section links resolve;
* none of the new text uses an em dash (house rule for new English text).
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

GUIDE = "docs/adding_an_instrument.md"
PROMPT = "docs/adding_an_instrument_agent_prompt.md"

#: Files written for this guide, checked whole.
NEW_FILES = (
    GUIDE,
    PROMPT,
    "AGENTS.md",
    "CONTRIBUTING.md",
    ".github/copilot-instructions.md",
    ".github/PULL_REQUEST_TEMPLATE.md",
)

#: Long files that carry a pointer section: only that section is checked.
SECTIONS = {
    "CLAUDE.md": "### Adding a measuring instrument",
    "README.md": "### Want to add an instrument?",
}

#: Every file that must lead a reader (or an agent) to the guide.
POINTERS = ("AGENTS.md", "CONTRIBUTING.md", "CLAUDE.md", "README.md",
            ".github/copilot-instructions.md",
            ".github/PULL_REQUEST_TEMPLATE.md", PROMPT)

#: First path components that mean "this is a path in the repository".
_ROOTS = {p.name for p in ROOT.iterdir()}

_TICKED = re.compile(r"`([^`\n]+)`")
_LINK = re.compile(r"\]\(([^)\s]+)\)")
_PATHLIKE = re.compile(r"^[\w./-]+$")
_ROOT_FILE = re.compile(r"^[A-Za-z][\w-]*\.(md|spec|py|ini|txt)$")


def _section(text: str, heading: str) -> str:
    start = text.index(heading)
    level = heading.split(" ", 1)[0]
    rest = text[start + len(heading):]
    stop = re.search(rf"^#{{1,{len(level)}}} ", rest, re.M)
    return heading + (rest[:stop.start()] if stop else rest)


def _texts() -> "dict[str, str]":
    out = {}
    for rel in NEW_FILES:
        out[rel] = (ROOT / rel).read_text(encoding="utf-8")
    for rel, heading in SECTIONS.items():
        out[rel] = _section((ROOT / rel).read_text(encoding="utf-8"), heading)
    return out


def _named() -> "list[tuple[str, str, str | None]]":
    """(where, path, symbol) for every repository path the texts name."""
    found = []
    for where, text in _texts().items():
        for token in _TICKED.findall(text):
            token = token.strip()
            path, _, symbol = token.partition("::")
            if not _PATHLIKE.match(path) or path.startswith("."):
                if not path.startswith(".github/"):
                    continue
            if "/" in path:
                if path.split("/", 1)[0] not in _ROOTS:
                    continue
            elif path.startswith("test_") and path.endswith(".py"):
                path = "tests/" + path
            elif not _ROOT_FILE.match(path):
                continue
            found.append((where, path, symbol or None))
    return found


def test_the_texts_name_paths_at_all():
    """Guard against the parser silently finding nothing."""
    named = _named()
    assert len(named) > 120, len(named)
    assert any(s for _, _, s in named)


def test_every_path_named_exists():
    missing = sorted({f"{w}: {p}" for w, p, _ in _named()
                      if not (ROOT / p).exists()})
    assert not missing, "named but not in the repository:\n  " + \
        "\n  ".join(missing)


def _defines(source: str, name: str) -> bool:
    return bool(re.search(
        rf"^\s*(?:async\s+)?(?:def|class)\s+{re.escape(name)}\b"
        rf"|^\s*{re.escape(name)}\s*[:=]", source, re.M))


def test_every_symbol_named_exists_where_it_is_said_to_be():
    wrong = []
    for where, path, symbol in _named():
        if symbol is None or not (ROOT / path).is_file():
            continue
        name = symbol.split(".")[-1].rstrip("()")
        if not _defines((ROOT / path).read_text(encoding="utf-8"), name):
            wrong.append(f"{where}: {path}::{symbol}")
    assert not wrong, "no such definition:\n  " + "\n  ".join(sorted(set(wrong)))


def test_every_relative_link_resolves():
    dead = []
    for where, text in _texts().items():
        base = (ROOT / where).parent
        for target in _LINK.findall(text):
            if target.startswith(("http://", "https://", "mailto:", "#")):
                continue
            target = target.split("#", 1)[0]
            if not (base / target).resolve().exists():
                dead.append(f"{where}: {target}")
    assert not dead, "dead links:\n  " + "\n  ".join(dead)


def _slug(heading: str) -> str:
    """GitHub's anchor for a heading."""
    s = heading.strip().lower()
    s = re.sub(r"[^\w\- ]", "", s)
    return s.replace(" ", "-")


@pytest.mark.parametrize("rel", [GUIDE, PROMPT])
def test_the_section_links_resolve(rel):
    text = (ROOT / rel).read_text(encoding="utf-8")
    anchors = {_slug(h) for h in re.findall(r"^#{1,6} (.+)$", text, re.M)}
    broken = [a for a in re.findall(r"\]\(#([^)]+)\)", text)
              if a not in anchors]
    assert not broken, f"{rel}: links to missing sections: {broken}"


def _hooked_files() -> "set[str]":
    tree = ast.parse((ROOT / "tests" / "test_fd9_off_changes_nothing.py")
                     .read_text(encoding="utf-8"))
    for node in tree.body:
        if (isinstance(node, ast.Assign)
                and any(getattr(t, "id", None) == "HOOKED_FILES"
                        for t in node.targets)):
            return set(ast.literal_eval(node.value))
    raise AssertionError("HOOKED_FILES is no longer in "
                         "tests/test_fd9_off_changes_nothing.py")


def test_the_checklist_names_every_file_the_fd9_hooks():
    """The FD-9's pinned list of hooked shared files is the most complete
    record of where an instrument has to be registered. A file added there
    belongs in the guide's checklist too."""
    guide = (ROOT / GUIDE).read_text(encoding="utf-8")
    missing = sorted(f for f in _hooked_files() if f"`{f}" not in guide)
    assert not missing, f"hooked by the FD-9, not in the guide: {missing}"


@pytest.mark.parametrize("rel", POINTERS)
def test_every_pointer_leads_to_the_guide(rel):
    text = (ROOT / rel).read_text(encoding="utf-8")
    if rel == PROMPT:
        assert "adding_an_instrument.md" in text
    else:
        assert "docs/adding_an_instrument.md" in text, \
            f"{rel} no longer points at the instrument guide"


def test_the_guide_points_at_its_prompt_and_at_claude_md():
    guide = (ROOT / GUIDE).read_text(encoding="utf-8")
    assert PROMPT in guide and "CLAUDE.md" in guide


@pytest.mark.parametrize("rel", list(NEW_FILES) + list(SECTIONS))
def test_no_em_dash_in_the_new_text(rel):
    text = _texts()[rel]
    lines = [f"{n}: {line.strip()}" for n, line in
             enumerate(text.splitlines(), 1) if "—" in line]
    assert not lines, f"{rel} uses an em dash:\n  " + "\n  ".join(lines)


def test_the_gate_command_reads_pytests_own_exit_code():
    """The guide must not teach `pytest | tail; echo $?` (CLAUDE.md)."""
    for rel in (GUIDE, "AGENTS.md", "CONTRIBUTING.md"):
        text = (ROOT / rel).read_text(encoding="utf-8")
        assert "--runslow -n auto" in text, rel
        assert re.search(r"--runslow -n auto -q > \S+ 2>&1", text), rel
