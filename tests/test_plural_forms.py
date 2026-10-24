"""Russian, Ukrainian and Polish count with three forms, and the app now does too.

English has "1 patch" and "{n} patches", and the code writes both out. Russian
needs more: 1 патч, 2 патча, 5 патчей, but also 21 патч, 22 патча, 101 патч,
111 патчей. A reviewer found about 160 Russian and 80 Ukrainian strings that put
the number straight before a noun in one fixed form, so "21 патчей" and "22
патчей" were on screen. `core/i18n.py` now knows the CLDR categories, and a
catalogue's "@plurals" entry gives one form per category.

What is pinned here:

* the rules themselves, for every number the review named;
* real strings, rendered the three ways the app reaches them (``tr(...,
  count=)``, ``.format()`` with the counting placeholder, ``count_phrase``);
* that every string with forms is reached with its number: a ``tr()`` whose
  result never sees the count would silently show the "many" form;
* and a guard against the fault coming back: a Russian, Ukrainian or Polish
  translation that puts a counting placeholder straight before a counted noun,
  in one form only, fails.
"""
from __future__ import annotations

import ast
import json
import re
import sys
from pathlib import Path

import pytest

from core import i18n

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from i18n_extract import _python_files, extract_keys  # noqa: E402

NUMBERS = (0, 1, 2, 3, 4, 5, 11, 12, 14, 21, 22, 25, 101, 111, 1.5)


@pytest.fixture(autouse=True)
def _reset_language():
    yield
    i18n.set_language("en")


# ----------------------------------------------------------------------
# The rules
# ----------------------------------------------------------------------

_RU_UK = {0: "many", 1: "one", 2: "few", 3: "few", 4: "few", 5: "many",
          11: "many", 12: "many", 14: "many", 21: "one", 22: "few",
          25: "many", 101: "one", 111: "many", 1.5: "other"}
_PL = {**_RU_UK, 21: "many", 101: "many"}


@pytest.mark.parametrize("lang,expected", [("ru", _RU_UK), ("uk", _RU_UK),
                                           ("pl", _PL)])
def test_the_cldr_rules(lang, expected):
    got = {n: i18n.plural_category(n, lang) for n in NUMBERS}
    assert got == expected


@pytest.mark.parametrize("lang", ["en", "de", "fr", "ja"])
def test_every_other_language_counts_like_english(lang):
    assert {n: i18n.plural_category(n, lang) for n in NUMBERS} == {
        n: ("one" if n == 1 else "other") for n in NUMBERS}


def test_a_number_already_written_out_is_read_as_a_number():
    assert i18n.plural_category("21", "ru") == "one"
    assert i18n.plural_category("1\u00a0021", "ru") == "one"
    assert i18n.plural_category("1,5", "ru") == "other"
    assert i18n.plural_category("n/a", "ru") == "other"


def test_a_missing_form_falls_back_to_a_sensible_one():
    forms = {"count": "n", "one": "{n} патч", "few": "{n} патча",
             "many": "{n} патчей"}
    text = i18n.PluralText("{n} патчей", forms, "n")
    # A fraction is "other", which Russian spells like "few" (1,5 патча).
    assert text.format(n=1.5) == "1.5 патча"
    assert i18n.PluralText("{n} x", {"count": "n"}, "n").for_count(3) == "{n} x"


def test_the_languages_with_three_forms_are_the_ones_that_need_them():
    """ru, uk and pl are the shipped languages with more than two forms for
    whole numbers (CLDR). Every other shipped one has English's two. (fr and
    pt put 0 in the singular in CLDR, where the app shows the plural for 0;
    that is accepted usage in both, and a choice, not a missing form.)"""
    assert set(i18n.PLURAL_CATEGORIES) == {"ru", "uk", "pl"}
    for code in ("ru", "uk", "pl"):
        assert json.load(open(ROOT / "data" / "i18n" / f"{code}.json", encoding="utf-8")).get(i18n.PLURALS_KEY), (
            f"{code} has no per-number forms at all")


# ----------------------------------------------------------------------
# Real strings, every number
# ----------------------------------------------------------------------

_EXPECT = {
    ("ru", "{n} patches"): {
        0: "0 патчей", 1: "1 патч", 2: "2 патча", 3: "3 патча", 4: "4 патча",
        5: "5 патчей", 11: "11 патчей", 12: "12 патчей", 14: "14 патчей",
        21: "21 патч", 22: "22 патча", 25: "25 патчей", 101: "101 патч",
        111: "111 патчей", 1.5: "1.5 патча"},
    ("uk", "{n} patches"): {
        0: "0 патчів", 1: "1 патч", 2: "2 патчі", 3: "3 патчі", 4: "4 патчі",
        5: "5 патчів", 11: "11 патчів", 12: "12 патчів", 14: "14 патчів",
        21: "21 патч", 22: "22 патчі", 25: "25 патчів", 101: "101 патч",
        111: "111 патчів"},
    ("pl", "{n} patches"): {
        0: "0 pól", 1: "1 pole", 2: "2 pola", 3: "3 pola", 4: "4 pola",
        5: "5 pól", 11: "11 pól", 12: "12 pól", 14: "14 pól", 21: "21 pól",
        22: "22 pola", 25: "25 pól", 101: "101 pól", 111: "111 pól"},
    ("ru", "{n} pages"): {
        1: "1 страница", 2: "2 страницы", 5: "5 страниц", 11: "11 страниц",
        21: "21 страница", 22: "22 страницы", 25: "25 страниц",
        111: "111 страниц"},
    ("uk", "{n} pages"): {
        1: "1 сторінка", 4: "4 сторінки", 12: "12 сторінок",
        21: "21 сторінка", 22: "22 сторінки", 25: "25 сторінок"},
    ("pl", "{n} pages"): {
        1: "1 strona", 2: "2 strony", 12: "12 stron", 21: "21 stron",
        22: "22 strony", 25: "25 stron"},
    ("ru", "Removed {n} patches."): {
        21: "Удалён 21 патч.", 22: "Удалено 22 патча.", 25: "Удалено 25 патчей.",
        101: "Удалён 101 патч.", 111: "Удалено 111 патчей."},
    ("uk", "Removed {n} patches."): {
        21: "Вилучено 21 патч.", 22: "Вилучено 22 патчі.",
        25: "Вилучено 25 патчів."},
    ("pl", "Removed {n} patches."): {
        21: "Usunięto 21 pól.", 22: "Usunięto 22 pola.", 25: "Usunięto 25 pól."},
    ("ru", " across {pages} pages"): {
        2: " на 2 страницах", 21: " на 21 странице", 22: " на 22 страницах"},
    ("pl", " across {pages} pages"): {
        2: " na 2 stronach", 21: " na 21 stronach"},
    ("ru", "{n} strips"): {
        21: "21 полоса", 22: "22 полосы", 25: "25 полос", 12: "12 полос"},
    ("pl", "{n} strips"): {
        1: "1 pasek", 21: "21 pasków", 22: "22 paski", 25: "25 pasków"},
}


@pytest.mark.parametrize("lang,key", sorted(_EXPECT))
def test_real_strings_read_right_for_every_number(lang, key):
    i18n.set_language(lang)
    field = i18n.placeholders(key).pop()
    for n, want in _EXPECT[(lang, key)].items():
        assert i18n.tr(key).format(**{field: n}) == want, (lang, key, n)
        assert i18n.tr(key, count=n).format(**{field: n}) == want, (lang, key, n)


@pytest.mark.parametrize("lang", ["ru", "uk", "pl"])
def test_count_phrase_picks_the_form_too(lang):
    """The app's own singular/plural helper, as tab_chart and the preset
    window call it."""
    i18n.set_language(lang)
    for n, want in _EXPECT[(lang, "{n} pages")].items():
        assert i18n.count_phrase(n, i18n.tr("1 page"), i18n.tr("{n} pages")) == want


def test_a_sentence_with_two_numbers_follows_the_one_it_counts():
    i18n.set_language("ru")
    key = "{n} of {total} patches"
    # "патчи: 1 из 21" — Russian keeps its colon form here, which reads
    # right for every number.
    assert i18n.tr(key).format(n=1, total=21) == "патчи: 1 из 21"
    i18n.set_language("uk")
    assert i18n.tr(key).format(n=3, total=21) == "3 із 21 патча"
    assert i18n.tr(key).format(n=3, total=22) == "3 із 22 патчів"


def test_english_and_german_do_not_change():
    i18n.set_language("en")
    assert i18n.count_phrase(21, i18n.tr("1 page"), i18n.tr("{n} pages")) == "21 pages"
    assert i18n.tr("{n} patches").format(n=21) == "21 patches"
    i18n.set_language("de")
    assert not isinstance(i18n.tr("{n} patches"), i18n.PluralText)
    assert i18n.tr("{n} patches").format(n=21) == i18n._catalog["{n} patches"].format(n=21)


# ----------------------------------------------------------------------
# Every string with forms is reached with its number
# ----------------------------------------------------------------------

def _plural_fields() -> "dict[str, set[str]]":
    out: "dict[str, set[str]]" = {}
    for code in i18n.PLURAL_CATEGORIES:
        with open(ROOT / "data" / "i18n" / f"{code}.json", encoding="utf-8") as f:
            for key, forms in json.load(f).get(i18n.PLURALS_KEY, {}).items():
                out.setdefault(key, set()).add(forms["count"])
    return out


def _module_constants() -> "dict[str, str]":
    out = {}
    for f in _python_files():
        for stmt in ast.parse(f.read_text(encoding="utf-8")).body:
            if (isinstance(stmt, ast.Assign) and len(stmt.targets) == 1
                    and isinstance(stmt.targets[0], ast.Name)
                    and isinstance(stmt.value, ast.Constant)
                    and isinstance(stmt.value.value, str)):
                out[stmt.targets[0].id] = stmt.value.value
    return out


def _reaches_its_number(node, parents, fields) -> bool:
    if any(kw.arg == "count" for kw in node.keywords):
        return True
    p = parents.get(node)
    while isinstance(p, (ast.IfExp, ast.BoolOp)):
        p = parents.get(p)
    if isinstance(p, ast.Call) and getattr(p.func, "id", "") == "count_phrase":
        return True
    if isinstance(p, ast.Attribute) and p.attr == "format":
        call = parents.get(p)
        if isinstance(call, ast.Call) and any(
                kw.arg in fields or kw.arg is None for kw in call.keywords):
            return True
    # Kept in a variable and formatted further down (`one if n == 1 else
    # many`, then `.format(n=n, total=total)`): the function that holds the
    # tr() must format with the counting placeholder somewhere.
    fn = p
    while fn is not None and not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
        fn = parents.get(fn)
    if fn is not None:
        for sub in ast.walk(fn):
            if (isinstance(sub, ast.Call) and isinstance(sub.func, ast.Attribute)
                    and sub.func.attr == "format"
                    and any(kw.arg in fields for kw in sub.keywords)):
                return True
    return False


def test_every_string_with_forms_is_formatted_with_its_number():
    fields_of = _plural_fields()
    consts = _module_constants()
    unreached = []
    for f in _python_files():
        tree = ast.parse(f.read_text(encoding="utf-8"))
        parents = {ch: node for node in ast.walk(tree)
                   for ch in ast.iter_child_nodes(node)}
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                    and node.func.id == "tr" and node.args):
                continue
            a = node.args[0]
            key = (a.value if isinstance(a, ast.Constant)
                   else consts.get(a.id) if isinstance(a, ast.Name)
                   else consts.get(a.attr) if isinstance(a, ast.Attribute)
                   else None)
            if key in fields_of and not _reaches_its_number(node, parents, fields_of[key]):
                unreached.append(f"{f.relative_to(ROOT)}:{node.lineno}  {key[:60]!r}")
    assert not unreached, (
        "these strings have per-number forms in ru/uk/pl, but the code never "
        "formats them with the counting placeholder, so they would always "
        "show the \"many\" form. Pass the number: tr(text, count=n), or "
        ".format(<placeholder>=n):\n  " + "\n  ".join(unreached))


# ----------------------------------------------------------------------
# The guard: a number before a counted noun, in one form only
# ----------------------------------------------------------------------

#: English nouns that are counted after a placeholder ("{n} patches",
#: "of {total} measurements", "{n} paper-white patches").
_EN_COUNTED = re.compile(
    r"\{(\w+)(?:[:!][^}]*)?\}(?:</?b>)?[ \u00a0]+"
    r"(?:(?!(?:of|the|a|an|its|their|this|that|these|those|and|or|to|in|on|at|"
    r"for|from|with|by|per|is|are|was|were|has|have|fit|match|read)\b)"
    r"[a-z][\w-]*[ \u00a0]+){0,2}?"
    r"(patches|pages|strips|readings|reads|measurements|colours|values|metrics|"
    r"rows|files|characters|channels|seconds|spacers|phrases|verifications|"
    r"scans|sheets|bytes|items|attempts|steps|bands|slots|profiles|jobs|lists|"
    r"reversals|repeats|things|boxes|squares|aims)\b")

#: The same nouns in the three languages, as stems. A number right before one
#: of them is the fault this file is about.
_COUNTED = {
    "ru": r"патч|страниц|полос|цвет|измерени|показани|значени|файл|символ|ряд|"
          r"разделител|скан|канал|лист|секунд|провер|байт|элемент|чтени|слот|"
          r"попыт|фраз|клет|пол[еяй]|инверси|задани|ступен|повтор",
    "uk": r"патч|сторін|смуг|колі?р|кольор|вимірюван|показ|значен|файл|символ|"
          r"ряд|розпір|скан|канал|аркуш|секунд|перевір|байт|елемент|зчитуван|"
          r"слот|спроб|фраз|рам|завдан|інверсі|крок|повтор",
    "pl": r"pól|pole\b|pola\b|stron|pas(?:ek|ki|ków)|kolor|pomiar|odczyt|plik|"
          r"znak|rzęd|rząd|separator|skan|kanał|arkusz|sekund|weryfikacj|bajt|"
          r"element|fraz|miejsc|metryk|odwróce|zada|stop(?:ień|nie|ni)|powtórze",
}

#: Ukrainian earlier "fixed" the fault by moving the number behind the noun
#: without a colon ("Патчі {n}", "Сторінки {n}"), which reads as "patches 5".
_UK_NOUN_FIRST = re.compile(
    r"(?i)\b(патчі|сторінки|смуги|кольори|файли|перевірки|розпірки|фрази|"
    r"елементи|канали|слоти|показання|показники|предмети|коробки)[ \u00a0]+\{(\w+)\}")

#: After these Polish prepositions the noun is genitive, locative or
#: instrumental, whose plural is the same for every number from 2 up
#: ("z 21 pól", "przy 22 polach"); only 1 differs, and the code says 1 in a
#: key of its own.
_PL_CASE_PREPS = {"z", "ze", "do", "od", "dla", "około", "spośród", "wśród",
                  "bez", "u", "niż", "przy", "po", "na", "w", "o"}

#: Keys that are only ever shown for one, so one fixed form is right.
_ONLY_EVER_ONE = {
    "{n} patch": "ti2_relayout_dialog: tr('{n} patch') if n == 1",
    "{n} measurement": "measurement_report_dialog: used only when n == 1",
}


def _guard_offences() -> "list[str]":
    out = []
    for code, stems in _COUNTED.items():
        with open(ROOT / "data" / "i18n" / f"{code}.json", encoding="utf-8") as f:
            cat = json.load(f)
        with_forms = cat.get(i18n.PLURALS_KEY, {})
        noun = re.compile(r"(?:</?b>)?[ \u00a0]+(?:</?b>)?(?:[^\W\d_]+(?:ых|их|ый|ий|"
                          r"ой|ая|ые|ие|ні|і|их|ych|ich|e|y|i)[ \u00a0]+)?(" + stems + ")",
                          re.I)
        for key in sorted(extract_keys()):
            value = cat.get(key)
            if not isinstance(value, str) or key in with_forms or key in _ONLY_EVER_ONE:
                continue
            counts = {m.group(1) for m in _EN_COUNTED.finditer(key)}
            for m in re.finditer(r"\{(\w+)(?:[:!][^}]*)?\}", value):
                if m.group(1) not in counts:
                    continue
                if code == "pl":
                    # "z co najmniej {k} paskami": the preposition governs.
                    head = re.sub(r"[ \u00a0]+co[ \u00a0]+(?:najmniej|najwyżej)[ \u00a0]*$",
                                  " ", value[:m.start()])
                    before = re.search(r"(\w+)[ \u00a0]+$", head)
                    if before and before.group(1).lower() in _PL_CASE_PREPS:
                        continue
                if noun.match(value, m.end()):
                    out.append(f"[{code}] …{value[max(0, m.start() - 30):m.end() + 30]}…"
                               f"   (key {key[:50]!r})")
            if code == "uk":
                for m in _UK_NOUN_FIRST.finditer(value):
                    if m.group(2) in counts:
                        out.append(f"[uk] …{m.group(0)}…   (key {key[:50]!r})")
    return out


def test_no_number_sits_before_a_counted_noun_in_one_form_only():
    bad = _guard_offences()
    assert not bad, (
        f"{len(bad)} Russian/Ukrainian/Polish translation(s) put a counting "
        "placeholder straight before a counted noun in one fixed form, which "
        "is wrong for 21, 22 or 101 (21 патчей, 22 патчей). Give the string "
        "its per-number forms under \"@plurals\" (one / few / many), or word "
        "it so the number does not govern the noun (\"патчей: {n}\"):\n  "
        + "\n  ".join(bad[:25]))


def test_the_guard_catches_the_fault_it_is_for(monkeypatch, tmp_path):
    """Planted: the exact fault the review found, in each language."""
    planted = {"ru": "{n} патчей", "uk": "Патчі {n}", "pl": "{n} pól"}
    real_open = open

    def fake_open(path, *a, **kw):
        p = Path(path)
        if p.parent == ROOT / "data" / "i18n" and p.stem in planted:
            data = json.load(real_open(path, encoding="utf-8"))
            data.get(i18n.PLURALS_KEY, {}).pop("{n} patches", None)
            data["{n} patches"] = planted[p.stem]
            fake = tmp_path / p.name
            fake.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            return real_open(fake, *a, **kw)
        return real_open(path, *a, **kw)

    monkeypatch.setattr("builtins.open", fake_open)
    bad = _guard_offences()
    for code in planted:
        assert any(b.startswith(f"[{code}]") and "{n} patches" in b for b in bad), code
