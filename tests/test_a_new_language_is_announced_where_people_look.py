"""A language that ships and is announced nowhere is a language nobody finds.

**FOUND BY CHALLENGE ROUND 32.** Ukrainian landed as `data/i18n/uk.json`, a
complete 6,008-row catalogue contributed by LackiUA on issue #198, and the
commit that brought it touched exactly two files: the catalogue and its
parameters overlay. `grep -i ukrain` over the CHANGELOG, the README and the
site returned **zero hits**, the README still said "Twelve languages", the site
still said "Thirteen languages" (its count includes English), and the person
who wrote 5,425 rows of it was named in no file a user or a reader of the
repository would ever open.

Every one of those is a COUNT or a LIST that somebody has to remember to
update, which is the shape CLAUDE.md already records the cost of: *"Nobody came
back to update the numbers."* So this file takes the count out of anybody's
memory. It reads the catalogue directory and asks the three places that state a
number to agree with it, and it asks the four places that enumerate the
languages to name every one that ships.

It deliberately does NOT check the app's own language menu: that is discovered
from the same directory at runtime (`core.i18n.available_languages`) and cannot
go stale. What goes stale is prose.

**Two different counts, both correct.** The app's own convention counts English
as a language it speaks, so "N languages" is `len(catalogues) + 1`; the site's
feature card also says "English plus M complete translations", which is
`len(catalogues)`. Both are checked, against the same directory, so neither can
be quietly changed into the other.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parent.parent
I18N = ROOT / "data" / "i18n"

#: How an English number word is written in this project's prose. Only as far
#: as it needs to go; a twentieth language can extend it.
_WORDS = {2: "two", 3: "three", 4: "four", 5: "five", 6: "six", 7: "seven",
          8: "eight", 9: "nine", 10: "ten", 11: "eleven", 12: "twelve",
          13: "thirteen", 14: "fourteen", 15: "fifteen", 16: "sixteen",
          17: "seventeen", 18: "eighteen", 19: "nineteen", 20: "twenty"}


def _codes() -> "list[str]":
    """Every shipped catalogue's code. English is the source and has none."""
    return sorted(p.stem for p in I18N.glob("*.json"))


def _english_names() -> "dict[str, str]":
    """``{code: the name this project writes in English prose}``.

    NOT read from the catalogue's own `@language_name`, which is the NATIVE
    name ("Українська"), and not what an English sentence says. This is the
    only hand-kept table in the file, and it is small, complete and checked:
    a catalogue with no entry here fails, so a new language cannot slip past
    by being unnameable.
    """
    return {
        "de": "German", "es": "Spanish", "fr": "French", "it": "Italian",
        "nl": "Dutch", "pt": "Portuguese", "sv": "Swedish",
        "no": "Norwegian", "pl": "Polish", "ru": "Russian",
        "uk": "Ukrainian", "ja": "Japanese", "zh_CN": "Chinese",
    }


def test_the_catalogue_directory_is_the_source_and_it_is_not_empty():
    """The control. Every assertion below is measured against this list, so if
    it were empty they would all pass for nothing."""
    codes = _codes()
    assert len(codes) >= 12, codes
    for c in codes:
        assert (I18N / f"{c}.json").is_file()
        assert json.loads((I18N / f"{c}.json").read_text(encoding="utf-8")
                          ).get("@language_name"), f"{c} has no @language_name"


def test_every_shipped_catalogue_has_an_english_name():
    missing = sorted(set(_codes()) - set(_english_names()))
    assert not missing, (
        f"{missing} ships as a catalogue and this file cannot name it in "
        "English, so the prose checks below cannot look for it. Add it to "
        "`_english_names`.")
    stale = sorted(set(_english_names()) - set(_codes()))
    assert not stale, f"{stale} is named here and ships no catalogue"


# ---------------------------------------------------------------------------
# The three places that state a NUMBER
# ---------------------------------------------------------------------------
def test_the_readme_states_the_right_number_and_names_every_language():
    """It said **Twelve** with Ukrainian shipping."""
    txt = (ROOT / "README.md").read_text(encoding="utf-8")
    want = _WORDS[len(_codes()) + 1]          # English included
    m = re.search(r"\*\*(\w+) languages, complete\*\*", txt)
    assert m, "the README no longer states a language count in that form"
    # **ONE CONVENTION, AND THIS GUARD IS WHAT FOUND THERE WERE TWO.** The
    # README used to say "Twelve languages" beside a list of the twelve
    # NON-English catalogues while the site said "Thirteen", counting English.
    # Two numbers for one product, each right by its own rule and neither
    # checkable. The README now counts English and names it in the list, which
    # is the site's rule and the app's own.
    assert m.group(1).lower() == want, (
        f"the README says {m.group(1)!r} languages and {len(_codes())} "
        f"catalogues ship, so it should say {want!r}")
    line = txt[m.start():txt.index("\n\n", m.start())]
    assert "English" in line, (
        "the README counts English in its total and does not name it in the "
        "list, which is the ambiguity this rule exists to remove")
    for code, name in sorted(_english_names().items()):
        if code in _codes():
            assert name in line, f"the README's list does not name {name}"


def test_the_site_states_the_right_number_everywhere_it_states_one():
    """Four places on one page, and they used to be able to disagree."""
    txt = (ROOT / "docs" / "index.html").read_text(encoding="utf-8")
    with_english = _WORDS[len(_codes()) + 1]
    translations = _WORDS[len(_codes())]

    said = re.findall(r"in (\w+) languages", txt) + \
        re.findall(r"available in (\w+) languages", txt)
    assert said, "the site no longer states a language count in prose"
    for word in said:
        assert word.lower() == with_english, (
            f"the site's prose says {word!r} languages; {len(_codes())} "
            f"catalogues ship, so it should say {with_english!r}")

    card = re.search(r"<h4>(\w+) languages</h4>", txt)
    assert card, "the site's language feature card has gone"
    assert card.group(1).lower() == with_english, card.group(1)

    plus = re.search(r"English plus (\w+) complete translations", txt)
    assert plus, "the site no longer says how many translations there are"
    assert plus.group(1).lower() == translations, (
        f"the site says English plus {plus.group(1)!r} translations; "
        f"{len(_codes())} catalogues ship")

    spec = re.search(r"<dt>Languages</dt><dd>(\d+),", txt)
    assert spec, "the site's spec row no longer gives a language count"
    assert int(spec.group(1)) == len(_codes()) + 1, spec.group(1)


def test_the_site_feature_card_names_every_language_that_ships():
    txt = (ROOT / "docs" / "index.html").read_text(encoding="utf-8")
    k = txt.index("<h4>")
    card = txt[txt.index("languages</h4>", k):]
    card = card[:card.index("</p>")]
    for code, name in sorted(_english_names().items()):
        if code in _codes():
            assert name in card, f"the site's card does not name {name}"


# ---------------------------------------------------------------------------
# The CHANGELOG, which is where a user looks for what is new
# ---------------------------------------------------------------------------
def test_every_shipped_language_is_announced_in_the_changelog():
    """Not a count: a NAME, somewhere in the file. A language that arrived
    without a line here arrived in silence, which is what happened."""
    txt = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    names = _english_names()
    silent = sorted(names[c] for c in _codes()
                    if c in names and names[c] not in txt)
    assert not silent, (
        f"{silent} ships and the CHANGELOG never names it, so nobody reading "
        "the release notes learns it exists")


# ---------------------------------------------------------------------------
# And the person who wrote one is credited IN the app they gave it to
# ---------------------------------------------------------------------------
#: ``{code: the contributor named for it}``. Only languages contributed from
#: outside are here; a language translated in-house has nobody to credit and
#: this file must not invent one.
CONTRIBUTED: "dict[str, str]" = {
    "uk": "LackiUA",      # issue #198, 2026-09-21, 5,425 rows
}


@pytest.mark.parametrize("code", sorted(CONTRIBUTED))
def test_a_contributed_translation_is_credited_in_the_app(code):
    """**A CREDIT IN A FILE THE USER NEVER OPENS IS NOT A CREDIT.** The same
    rule `test_a_credit_nobody_can_read_is_not_a_credit.py` applies to bundled
    reference data: the source is named where the thing is used. A translation
    is used in the running app, so the name belongs in the running app.
    """
    import sys
    sys.path.insert(0, str(ROOT / "scripts"))
    from i18n_extract import extract_keys
    who = CONTRIBUTED[code]
    assert code in _codes(), f"{code} is credited here and ships no catalogue"
    named = [k for k in extract_keys() if who in k]
    assert named, (
        f"{who} contributed the {_english_names()[code]} translation and is "
        "named in no user-facing string in the app")


@pytest.mark.parametrize("code", sorted(CONTRIBUTED))
def test_a_contributed_translation_is_credited_in_the_repository(code):
    who = CONTRIBUTED[code]
    for name in ("README.md", "CHANGELOG.md"):
        txt = (ROOT / name).read_text(encoding="utf-8")
        assert who in txt, f"{who} is not named in {name}"
