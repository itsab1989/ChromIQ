"""Translation faults that `test_i18n.py` cannot see.

That file guards the things a *missing* translation breaks: completeness, stale
keys, `{placeholder}` parity, and the length budget for short labels. This one
guards the things a *present but damaged* translation breaks — the quiet faults,
which are the ones that survived into shipped releases:

* **Log prefixes rendered inconsistently.** Found 2026-08-07 in **every one of
  the twelve languages**, with the same 16/2 split, so it dated from the original
  pass: 16 strings kept `[ERROR]` and 2 translated it. One log would print
  `[ERROR]` on one line and `[FOUT]` on the next. Nothing failed; it just looked
  broken.

* **A dropped HTML tag.** `<b>`/`<i>` are how these help texts mark a button's
  name. Losing one silently un-marks it, and Qt renders the rest fine, so no
  test notices.

* **Glossary drift.** Dutch carried 61 occurrences of "patch/patches" against
  441 correct "meetveld/meetvelden" — including a help text naming a control
  "Patches" when the Dutch UI labels it "Meetvelden", so the reader was told to
  look for something that is not on screen.

`scripts/i18n_verify_batch.py` is the same logic as a report, for use while
translating. These tests are the gate.

**Why the exclusions below are exclusions and not oversights.** Four checks were
tried first and removed, each after it flagged correct work:

* comparing `{placeholder}` *multisets* — English saying `{side}` twice where a
  translation says it once is a better sentence, and `str.format` does not mind;
* HTML-entity parity — `"Printers &amp; Scanners"` becoming `"Printers en
  scanners"` is the actual Dutch name of that macOS pane;
* `&&` preservation — `"Apply && save"` becoming `"Applica e salva"` is Italian
  using the word, correctly;
* newline parity — a longer sentence gaining a manual break is re-wrapping, and
  it fires 18–53 times per language, essentially all benign.

A check that reports correct work as a fault is worse than no check: it trains
whoever reads it to skip the whole list.
"""
from __future__ import annotations

import difflib
import json
import os
import re
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

I18N = Path(__file__).resolve().parent.parent / "data" / "i18n"

CODES = sorted(p.stem for p in I18N.glob("*.json")
               if not p.name.startswith("parameters"))

_HTML = re.compile(
    r"</?(?:b|i|u|br|p|span|div|font|sub|sup|small|big|hr|ul|ol|li|table|tr|td|th|a|code|pre)"
    r"(?:\s[^>]*)?/?>", re.I)
_LOGP = re.compile(r"^\[(?:INFO|OK|WARN|ERROR)\]")
_BRACE = re.compile(r"\{[^}]*\}")
_QUOTED = re.compile(r"'[^'\n]{0,80}'|\"[^\"\n]{0,80}\"|„[^“”\n]{0,80}[“”]"
                     # Curly quotes too. Missing them made the check flag the
                     # run's literal “chart” folder as Dutch glossary drift —
                     # it is a filesystem path, not the word "chart". The
                     # translator worked around it by switching to straight
                     # quotes, which is the check dictating the prose; the
                     # dominant Dutch style is curly (283 against 75).
                     r"|“[^”\n]{0,80}”|‘[^’\n]{0,80}’"
                     # A short parenthetical glosses the English term on
                     # purpose: „Feldsatz (Patch-Set)“. Bounded so a full
                     # English sentence in brackets is still caught.
                     r"|\([^()\n]{0,30}\)")

#: Japanese and Chinese mark a UI element's name with corner brackets 「…」 where
#: English uses <i>…</i>. That is the correct convention in those languages, so
#: an <i> missing from a translation that uses them is not a lost tag.
_CJK_QUOTE = re.compile(r"[「」『』]")
_CJK = {"ja", "zh_CN"}

#: Terms a language has settled on. The English word inside a translation means
#: the glossary drifted. Only languages with a recorded decision are listed.
#: A translation can be almost entirely English and still count as done, because
#: the placeholder scan only catches value == key. One German entry was 95%
#: identical to its source — a stale copy of an OLDER English text, still telling
#: the user to reopen a chart "from Print or Measure" long after the English had
#: replaced that wording. Coverage read 100% and nothing flagged it.
_NEAR_ENGLISH = 0.85
_MIN_LEN = 80

#: The two keys that are legitimately near-identical in every language, listed
#: explicitly rather than detected. A heuristic was tried — "mostly punctuation
#: and placeholders" — and it is exactly the kind of clever rule that quietly
#: stops matching. Both are dominated by things that must not be translated:
_NEAR_ENGLISH_OK = (
    "{name}.ti1, {name}.ti2",          # a file listing: placeholders + extensions
    "Built on ArgyllCMS by Graeme Gill",   # the credits line: proper nouns
)

_GLOSSARY = {
    "nl": ("patch", "patches", "spacer", "spacers", "chart", "charts"),
    "de": ("patch", "patches", "spacer", "spacers"),
}


def _pairs(code: str):
    j = json.loads((I18N / f"{code}.json").read_text())
    return [(k, v) for k, v in j.items() if not k.startswith("@") and v != k]


@pytest.mark.parametrize("code", CODES)
def test_log_prefixes_are_handled_the_same_way_throughout(code):
    """All kept in English, or all translated — never a mix in one language."""
    kept, changed = [], []
    for k, v in _pairs(code):
        if _LOGP.match(k):
            (kept if _LOGP.match(v) else changed).append(k)
    assert not (kept and changed), (
        f"{code}: {len(kept)} strings keep the English log prefix and "
        f"{len(changed)} translate it, so one log prints two different tags. "
        f"The project rule is to keep [INFO]/[OK]/[WARN]/[ERROR] as they are. "
        f"First offender: {changed[0][:70]!r}"
    )


@pytest.mark.parametrize("code", CODES)
def test_html_markup_survives_translation(code):
    """A dropped <b> or <i> silently un-marks a button name."""
    bad = []
    for k, v in _pairs(code):
        want, got = _HTML.findall(k.lower()), _HTML.findall(v.lower())
        if want == got:
            continue
        if code in _CJK and _CJK_QUOTE.search(v):
            continue      # corner brackets stand in for <i> — see the note above
        bad.append(f"{k[:60]!r}: {want} -> {got}")
    assert not bad, (
        f"{code}: {len(bad)} translation(s) changed their HTML markup:\n  "
        + "\n  ".join(bad[:5])
    )


@pytest.mark.parametrize("code", sorted(_GLOSSARY))
def test_the_agreed_terminology_is_used_throughout(code):
    """An English term left in a translation that has decided on its own word.

    Quoted English and `{placeholders}` are skipped: a gloss („patches“) teaches
    the reader the English word on purpose, ArgyllCMS's own messages
    ('not enough patches read') stay English whatever the interface language,
    and `{patches}` is a variable name that must never be translated.
    """
    terms = _GLOSSARY[code]
    pattern = re.compile(rf"\b(?:{'|'.join(re.escape(t) for t in terms)})\b", re.I)
    bad = []
    for k, v in _pairs(code):
        prose = _QUOTED.sub(" ", _BRACE.sub(" ", v))
        m = pattern.search(prose)
        if m:
            bad.append(f"{k[:55]!r} still says {m.group(0)!r}")
    assert not bad, (
        f"{code}: {len(bad)} translation(s) use an English term this language "
        f"has replaced:\n  " + "\n  ".join(bad[:5])
    )


@pytest.mark.parametrize("code", CODES)
def test_no_translation_is_still_english(code):
    """A value nearly identical to its key is a stale copy, not a translation.

    It passes every other check: the key exists, the placeholders match, and
    because ``value != key`` the coverage report counts it as done. The one real
    case was German text describing behaviour the English had already replaced.
    """
    bad = []
    for k, v in _pairs(code):
        if len(k) < _MIN_LEN or k.startswith(_NEAR_ENGLISH_OK):
            continue
        if difflib.SequenceMatcher(None, k, v).ratio() > _NEAR_ENGLISH:
            bad.append(k[:70])
    assert not bad, (
        f"{code}: {len(bad)} entr(y/ies) are still essentially the English "
        f"source:\n  " + "\n  ".join(bad[:5])
    )
