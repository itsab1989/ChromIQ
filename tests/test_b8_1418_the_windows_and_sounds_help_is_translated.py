"""B8-1418: the "Measurement windows and their sounds" help is in the catalogue.

Preferences > Sounds, (i) "Measurement windows and their sounds" showed in
English in the German app (beta 45, photographed). `core/measure_windows.py`
wrote its paragraphs and column headings as ``_esc("...")``; `_esc` passes its
argument to `tr()`, but `scripts/i18n_extract.py` sweeps only ``tr("...")``
literals, so none of those texts was a key in any catalogue and
`tests/test_i18n.py` could not see them missing.

The rule checked here is about the RENDERED help, not about how its source is
spelled, so a text added later by any route is caught: every piece of text the
English help shows is a key the extractor finds and German translates.
"""
from __future__ import annotations

import html as _html
import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import i18n_extract                                        # noqa: E402

from core import i18n                                      # noqa: E402
from core.measure_windows import windows_and_sounds_html  # noqa: E402

#: Text that is the same in every language: the row numbers, the number
#: column's heading and the dash of a row with no reading mode.
_NOT_WORDS = re.compile(r"^(\d+|#|—)$")


def _texts(markup: str) -> "list[str]":
    """Every run of text between tags, as the reader sees it."""
    out = []
    for piece in re.split(r"<[^>]+>", markup):
        piece = _html.unescape(piece).strip()
        if piece and not _NOT_WORDS.match(piece):
            out.append(piece)
    return out


@pytest.fixture
def german():
    was = i18n.current_language()
    i18n.set_language("de")
    try:
        yield
    finally:
        i18n.set_language(was)


def _de() -> "dict[str, str]":
    return json.loads((ROOT / "data/i18n/de.json").read_text(encoding="utf-8"))


def test_every_text_the_help_shows_is_a_key_the_extractor_finds():
    english = _texts(windows_and_sounds_html())
    assert len(english) > 40, english            # the guard sees the help
    keys = i18n_extract.extract_keys()
    missing = sorted(t for t in set(english) if t not in keys)
    assert not missing, (
        f"{len(missing)} text(s) of the windows-and-sounds help are no "
        f"tr() key (write them as tr(\"...\")):\n  " + "\n  ".join(missing))


def test_every_text_the_help_shows_has_its_german():
    de = _de()
    english = set(_texts(windows_and_sounds_html()))
    untranslated = sorted(t for t in english if t not in de)
    assert not untranslated, "\n  ".join(["no German for:"] + untranslated)


def test_the_german_app_shows_the_help_in_german(german):
    shown = _texts(windows_and_sounds_html())
    de = _de()
    english = set(de)                     # every English source text
    # Only a text whose German IS its English may stay English.
    still_english = sorted(t for t in set(shown)
                           if t in english and de.get(t) != t)
    assert not still_english, (
        "the German app shows these in English:\n  "
        + "\n  ".join(still_english))
    body = " ".join(shown)
    for german_text in ("Jedes Fenster, das eine Messung öffnen kann",
                        "Töne ohne eigenes Fenster.", "Zeile 1 im Einzelnen.",
                        "Zwei Dinge, die du wissen solltest.",
                        "Was ArgyllCMS meldet", "Ton beim Öffnen"):
        assert german_text in body, german_text


def test_the_texts_it_added_carry_no_em_dash():
    """The CLAUDE.md rule for a touched text; the rows' own older texts are
    in the em-dash baseline and are not this item's."""
    src = (ROOT / "core/measure_windows.py").read_text(encoding="utf-8")
    fn = src[src.index("def windows_and_sounds_html"):]
    assert "—" not in fn.split('"""', 2)[2], (
        "an em dash in the help's own paragraphs or headings")
