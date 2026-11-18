"""The developer tools catalogue stays current, findable and true.

`docs/dev_tools_index.md` lists every file in `scripts/` from its own docstring; a script added
without running `python scripts/make_tools_index.py` fails here, so the catalogue cannot rot.
And the documents written with it (the catalogue, `scripts/README.md`, the driven-instrument
checklist, the templates) name only paths that exist, link only to files that exist, carry no
em dash, and name no home folder.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import make_tools_index as mti  # noqa: E402

DOCS = ("docs/dev_tools_index.md", "scripts/README.md", "docs/driven_instrument_checklist.md",
        "docs/templates/questions_table.md", "docs/templates/safety_brief.md",
        "docs/templates/safety_review_brief.md", "docs/templates/review_brief.md",
        "docs/templates/tester_program_step.md",
        "docs/templates/release_notes_honest_limits.md")

_TICKED = re.compile(r"`([^`\n]+)`")
_LINK = re.compile(r"\]\(([^)\s#]+)(?:#[^)]*)?\)")
_ROOTS = ("scripts/", "tests/", "docs/", "ui/", "core/", "workflow/", "native/", "data/")


def _hand_written(rel: str) -> str:
    text = (ROOT / rel).read_text(encoding="utf-8")
    return text.split(mti.BEGIN)[0]


def test_the_generated_listing_is_current():
    assert mti.main(["--check"]) == 0, \
        "run: python scripts/make_tools_index.py, and commit docs/dev_tools_index.md"


def test_every_script_is_listed_once():
    text = (ROOT / "docs" / "dev_tools_index.md").read_text(encoding="utf-8")
    generated = text[text.index(mti.BEGIN):]
    for p in mti.files():
        rel = p.relative_to(ROOT).as_posix()
        assert generated.count(f"| `{rel}` |") == 1, rel


def test_every_listed_tool_exists_and_says_what_it_does():
    for rel in sorted(mti.TOOLS):
        p = ROOT / rel
        assert p.is_file(), rel
        assert mti.describe(p) != "(no description in the file)", rel


def test_the_check_mode_writes_nothing(tmp_path):
    before = (ROOT / "docs" / "dev_tools_index.md").read_bytes()
    proc = subprocess.run([sys.executable, str(ROOT / "scripts" / "make_tools_index.py"),
                           "--check"], cwd=tmp_path, capture_output=True, text=True,
                          timeout=300)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert (ROOT / "docs" / "dev_tools_index.md").read_bytes() == before


@pytest.mark.parametrize("rel", DOCS)
def test_every_path_named_exists(rel):
    missing = []
    for token in _TICKED.findall(_hand_written(rel)):
        path = token.split("::", 1)[0].strip()
        if not path.startswith(_ROOTS) or " " in path or "<" in path or "*" in path:
            continue
        if not (ROOT / path).exists():
            missing.append(path)
    assert not missing, f"{rel} names paths that do not exist: {missing}"


@pytest.mark.parametrize("rel", DOCS)
def test_every_relative_link_resolves(rel):
    base = (ROOT / rel).parent
    dead = [t for t in _LINK.findall(_hand_written(rel))
            if not t.startswith(("http://", "https://", "mailto:"))
            and not (base / t).exists()]
    assert not dead, f"{rel}: dead links {dead}"


@pytest.mark.parametrize("rel", DOCS + ("docs/adding_an_instrument.md",))
def test_no_em_dash_and_no_home_folder(rel):
    text = (ROOT / rel).read_text(encoding="utf-8")
    assert "—" not in text, f"{rel} carries an em dash"
    assert not re.search("/" + "Users" + r"/\w|/home/\w", text), f"{rel} names a home folder"


def test_the_index_is_linked_from_where_people_look():
    for rel in ("README.md", "AGENTS.md", "scripts/README.md", "docs/adding_an_instrument.md"):
        assert "dev_tools_index.md" in (ROOT / rel).read_text(encoding="utf-8"), rel


def test_the_driven_instrument_checklist_is_linked_from_the_guide_and_agents():
    for rel in ("docs/adding_an_instrument.md", "AGENTS.md", "docs/dev_tools_index.md"):
        assert "driven_instrument_checklist.md" in (ROOT / rel).read_text(encoding="utf-8"), rel
