"""Review 2 (2026-11-16): a chart in fixed order leaves nothing of the seed
behind. 4.3.42 took "seed N" off such a sheet (the number decides nothing
there); two places still showed it:

* the Create Chart log line "[ChromIQ layout engine] 612 patches (18x17),
  2 pages, Seed: 1649762225" for a chart in fixed order;
* a user's own text "(seed {seed})" printed "(seed )".
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from core import i18n
from workflow.chart_creator import _engine_summary_log_line
from workflow.layout_engine.raster import resolve_placeholders

ROOT = Path(__file__).resolve().parents[1]
K_FIXED = "[ChromIQ layout engine] {patches} ({steps}×{passes}), {pages}"


@pytest.fixture(autouse=True)
def _english():
    i18n.set_language("en")
    yield
    i18n.set_language("en")


def test_the_log_names_no_seed_for_a_chart_in_fixed_order():
    off = _engine_summary_log_line(612, 18, 17, 2, 1649762225, False)
    assert off == "[ChromIQ layout engine] 612 patches (18×17), 2 pages"
    on = _engine_summary_log_line(612, 18, 17, 2, 1649762225, True)
    assert on.endswith("2 pages, Seed: 1649762225")
    # the old five-argument call is the randomised one, as before
    assert _engine_summary_log_line(612, 18, 17, 2, 7) .endswith("Seed: 7")


def test_the_fixed_order_line_has_every_language():
    for lang in ("de", "es", "fr", "it", "ja", "nl", "no", "pl", "pt", "ru",
                 "sv", "uk", "zh_CN"):
        cat = json.loads((ROOT / "data" / "i18n" / f"{lang}.json")
                         .read_text(encoding="utf-8"))
        v = cat[K_FIXED]
        assert "{seed" not in v and "{pages}" in v and "{patches}" in v, lang
        i18n.set_language(lang)
        assert "1649762225" not in _engine_summary_log_line(
            612, 18, 17, 2, 1649762225, False), lang


def test_the_creator_tells_the_log_whether_the_chart_is_randomised():
    import inspect
    from workflow import chart_creator
    src = inspect.getsource(chart_creator.ChartCreator)
    assert 'result.layout.passes, result.layout.pages, result.seed,\n' \
           '            bool(getattr(result, "randomize", True))))' in src


CTX_OFF = dict(seed="", project="P", page="page 1/2", date="2026-11-16")
CTX_ON = dict(CTX_OFF, seed="seed 42")


@pytest.mark.parametrize("text,expected", [
    ("{project} (seed {seed})", "P"),
    ("{project} ({seed})", "P"),
    ("{project} [Seed: {seed}]", "P"),
    ("{project} (Seed #{seed})", "P"),
    ("{project} ( seed {seed} )", "P"),
    ("{project} (the shuffle seed {seed})", "P"),
    ("(seed {seed}) {project}", "P"),
    ("{project} - (seed {seed}) - {page}", "P - page 1/2"),
    ("{project}\n(seed {seed})\n{page}", "P\n\npage 1/2"),
    ("{project} [Seed: {seed}] - {page}", "P - page 1/2"),
    # what was already handled stays as it was
    ("{project} - {date} - {seed}", "P - 2026-11-16"),
    ("{seed} - {page}", "page 1/2"),
    ("{page}, {seed}", "page 1/2"),
])
def test_an_emptied_bracket_goes_whole(text, expected):
    assert resolve_placeholders(text, CTX_OFF) == expected


# ---- the rule as a table (integration of 4.3.42, review 2's leftovers) ----
# 1. the phrase that only names the seed goes: a bracket of a few words and
#    {seed}, else {seed} with the one word before it when that word labels it
#    ("seed", or a word with ":", "#" or "=" against the token);
# 2. where it stood: an emptied (or unclosed) bracket, the one separator, the
#    doubled or trailing space;
# 3. nothing else is touched.
RULE_TABLE = [
    # review 2's cosmetic leftovers
    ("{project} ((seed {seed}))", "P"),                  # was "P ()"
    ("((seed {seed}))", ""),
    ("{project} (seed {seed}, {page})", "P (page 1/2)"), # was "(seed , page"
    ("{project} ({page}, seed {seed})", "P (page 1/2)"),
    ("seed: {seed}", ""),                                # was "seed"
    ("{project} seed: {seed}", "P"),
    ("{project}, Seed: {seed}", "P"),
    ("(a b c d e {seed})", "(a b c d e)"),               # was "(a b c d e )"
    ("{project} {seed}", "P"),                           # was "P "
    ("{project} (seed {seed}", "P"),                     # was "P (seed "
    # labels
    ("Seed #{seed} - {page}", "page 1/2"),
    ("Datum: {date}, Zufallsstartwert: {seed}", "Datum: 2026-11-16"),
    ("Printed {date}: {seed}", "Printed 2026-11-16"),
    ("{project} | {seed} | {page}", "P | page 1/2"),
    # never touched: text that merely contains the word, other brackets
    ("the seed of doubt {seed}", "the seed of doubt"),
    ("seedling {seed} {project}", "seedling P"),
    ("{project} (seed {seed}) () [x]", "P () [x]"),
    ("{project} (run 2 {seed})", "P (run 2)"),
    ("Seed: {project}", "Seed: P"),
    ("{project} (seed)", "P (seed)"),
    # lines stay lines
    ("{project}\n{seed}\n{page}", "P\n\npage 1/2"),
    ("seed: {seed}\n{page}", "\npage 1/2"),
]


@pytest.mark.parametrize("text,expected", RULE_TABLE)
def test_the_seed_rule_table(text, expected):
    assert resolve_placeholders(text, CTX_OFF) == expected


@pytest.mark.parametrize("text,_", [r for r in RULE_TABLE
                                    if "{seed}" in r[0]
                                    and "seed of" not in r[0]])
def test_no_leftover_of_the_seed_phrase(text, _):
    out = resolve_placeholders(text, CTX_OFF)
    assert "()" not in out.replace("() [x]", "")
    assert "( " not in out and " )" not in out and not out.endswith(" ")
    assert "(seed" not in out.lower() and not out.lower().endswith("seed")
    assert "\0" not in out


def test_text_without_the_token_is_never_rewritten():
    from workflow.layout_engine.raster import drop_the_seed
    for t in ("seed: 12", "(seed)", "a - - b", "x ()", "Seed #"):
        assert drop_the_seed(t) == t


@pytest.mark.parametrize("text", [t for t, _ in RULE_TABLE])
def test_a_randomised_chart_is_untouched_by_the_rule(text):
    ctx = dict(CTX_OFF, seed="seed 42")
    assert resolve_placeholders(text, ctx) == text.format(**ctx)


def test_a_randomised_chart_keeps_its_bracket():
    assert resolve_placeholders("{project} (seed {seed})", CTX_ON) == \
        "P (seed seed 42)"
    assert resolve_placeholders("{project} ({seed})", CTX_ON) == \
        "P (seed 42)"
