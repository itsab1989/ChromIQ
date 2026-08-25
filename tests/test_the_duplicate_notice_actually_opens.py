"""The "Your duplicated run is ready" window must actually build its text.

It never once opened. `announce_duplicated_run` (`ui/tabs/tab_chart.py`)
formatted its BODY with `.format(name=…)` while that string also contains
`{source}`, so every call raised `KeyError: 'source'` — from 2026-08-01, through
GA, to today.

Five existing tests guard this window by reading the source with
`inspect.getsource`, and one asserts `"{source}" in src` — which passes
*because* the placeholder is never substituted. They were pinned to the broken
state.

THIS TEST CHECKS EACH `.format()` CALL AGAINST ITS OWN STRING. An earlier
version of it searched the whole method for `source=`, found the one in the
HEADING, and passed while the body was still broken — the same class of mistake
as the tests it replaces.
"""
from __future__ import annotations

import ast
import inspect
import textwrap

import pytest

from ui.tabs import tab_chart


def _format_calls():
    """Every `<str>.format(**kw)` in the method, as (placeholders, keywords).

    Parsed with `ast`, not regex: a regex cannot tell which `.format()` a given
    keyword belongs to, which is exactly how the first version of this test
    fooled itself.
    """
    src = textwrap.dedent(inspect.getsource(tab_chart.TabChart.announce_duplicated_run))
    tree = ast.parse(src)
    out = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "format"):
            continue
        # the string being formatted — tr("…") or a bare literal
        target = node.func.value
        if isinstance(target, ast.Call):                 # tr("…")
            parts = [a for a in target.args if isinstance(a, ast.Constant)]
            text = "".join(str(p.value) for p in parts)
        elif isinstance(target, ast.Constant):
            text = str(target.value)
        else:
            continue
        if not text:
            continue
        fields = {f for _lit, f, _s, _c
                  in __import__("string").Formatter().parse(text) if f}
        keywords = {k.arg for k in node.keywords if k.arg}
        out.append((text, fields, keywords))
    return out


def test_the_test_is_reading_both_strings():
    """Positive control: the window has a heading AND a body."""
    calls = _format_calls()
    assert len(calls) >= 2, (
        f"only {len(calls)} .format() call(s) found — the parser is not seeing "
        "the window's strings, so the checks below would prove nothing")


@pytest.mark.parametrize("i", range(4))
def test_each_format_call_supplies_every_placeholder(i):
    """Each string's own placeholders must be covered by its OWN keywords."""
    calls = _format_calls()
    if i >= len(calls):
        pytest.skip("fewer format calls than the parametrisation covers")
    text, fields, keywords = calls[i]
    missing = fields - keywords
    assert not missing, (
        f"{sorted(missing)} used in “{text[:60]}…” but not passed to that "
        f"call's .format() — the window raises KeyError and never opens")
    # and prove it really substitutes
    text.format(**{f: f"<{f}>" for f in fields})
