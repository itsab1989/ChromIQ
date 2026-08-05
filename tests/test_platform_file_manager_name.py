"""#130 (Knut, 2026-07-29): the file manager must be called by its own name.

*"When 'Finder' is referred to, this applies Mac only. This means that this word
must be made dependant on platform, Windows, Mac and Linux, so correct word for
the program is used."*

Telling a Windows user to look in the Finder names a program that does not exist
on their machine, and "Finder/Explorer" makes every reader work out which half
is theirs. Linux has no single answer, so it gets an honest description rather
than a name that might be wrong.
"""
from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import core.platform_paths as pp                      # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
SCANNED = ("ui", "core", "workflow")


def test_each_platform_gets_its_own_name(monkeypatch):
    monkeypatch.setattr(pp, "is_macos", lambda: True)
    monkeypatch.setattr(pp, "is_windows", lambda: False)
    assert pp.file_manager_name() == "Finder"

    monkeypatch.setattr(pp, "is_macos", lambda: False)
    monkeypatch.setattr(pp, "is_windows", lambda: True)
    assert pp.file_manager_name() == "File Explorer"

    monkeypatch.setattr(pp, "is_windows", lambda: False)
    assert pp.file_manager_name() == "your file manager"


def test_the_name_is_translatable():
    """It is a user-facing word like any other."""
    import inspect
    src = inspect.getsource(pp.file_manager_name)
    assert "from core.i18n import tr" in src
    for name in ("Finder", "File Explorer", "your file manager"):
        assert f'tr("{name}")' in src


def _user_facing_lines():
    """Lines that could actually reach a user.

    Prose inside a module docstring is not user-facing — ``core/file_manager``
    explains the folder layout in English and mentions the Finder in passing,
    which is fine. A line only counts here if it carries a quoted string, and
    ``platform_paths`` is skipped entirely because it is where the names are
    defined and the problem is documented.
    """
    for entry in SCANNED:
        base = ROOT / entry
        for path in sorted(base.rglob("*.py")):
            if "__pycache__" in path.parts or path.name == "platform_paths.py":
                continue
            for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                if '"' not in line and "'" not in line:
                    continue
                yield path, n, line


# Sentences that name BOTH platforms on purpose, because they are explaining a
# cross-platform setting rather than telling one user where to look.
_DELIBERATE = ("Finder's on a Mac",)


def test_no_user_text_says_finder_to_everybody():
    """The whole point: a Windows or Linux user must never be sent to the
    Finder."""
    offenders = []
    for path, n, line in _user_facing_lines():
        if "Finder" not in line:
            continue
        if any(d in line for d in _DELIBERATE):
            continue
        if line.lstrip().startswith("#"):
            continue                     # a comment is not user-facing
        offenders.append(f"{path.relative_to(ROOT)}:{n}: {line.strip()[:80]}")
    assert not offenders, "hard-coded 'Finder' in user text:\n" + "\n".join(offenders)


def test_no_user_text_pairs_them_by_hand():
    """"Finder/Explorer" and "Finder or Explorer" were the old workaround; they
    make the reader do the choosing and still leave Linux out."""
    bad = re.compile(r"Finder\s*(/|or)\s*Explorer", re.I)
    offenders = [f"{p.relative_to(ROOT)}:{n}" for p, n, line in _user_facing_lines()
                 if bad.search(line)]
    assert not offenders, offenders


def test_every_manager_placeholder_is_actually_filled():
    """A ``{manager}`` left unformatted would be shown to the user verbatim."""
    # Scan for the *literal* "{manager}" in Python, not via `grep`: the pattern
    # is a regex to grep, and the two greps disagree — BSD grep (macOS) treats
    # "{manager}" as literal braces, GNU grep (Windows/Linux) matches the bare
    # word "manager", dragging in every file that says "manager" in prose. A
    # plain substring test is deterministic on every platform (and needs no
    # grep on PATH, nor a locale-correct decode of its output).
    files = set()
    for entry in SCANNED:
        for path in (ROOT / entry).rglob("*.py"):
            if "__pycache__" in path.parts:
                continue
            if "{manager}" in path.read_text(encoding="utf-8"):
                files.add(path)
    assert files, "the placeholder has vanished — did the strings change?"
    # every file that mentions the placeholder must also call the helper
    for path in sorted(files):
        text = path.read_text(encoding="utf-8")
        assert "file_manager_name()" in text, \
            f"{path.relative_to(ROOT)} never fills {{manager}}"


@pytest.mark.parametrize("platform_name", ["Finder", "File Explorer",
                                           "your file manager"])
def test_the_rendered_sentence_reads_naturally(monkeypatch, platform_name):
    """Sanity on the wording: the name has to sit in the sentence without an
    article of its own, so "in Finder" and "in your file manager" both work."""
    monkeypatch.setattr(pp, "is_macos", lambda: platform_name == "Finder")
    monkeypatch.setattr(pp, "is_windows", lambda: platform_name == "File Explorer")
    sentence = "Open this chart's folder in {manager}.".format(
        manager=pp.file_manager_name())
    assert sentence.startswith("Open this chart's folder in ")
    assert "  " not in sentence and " ." not in sentence
