"""B8-1521 (beta 45 challenge 3b): six parameter helps write emphasis the
markdown way, ``*surface*``, and the help window showed the asterisks as text,
next to the ``**...**`` lead-ins B8-1490 renders in bold.

The emphasis is now shown in italic, and nowhere else is a word's asterisk
shown. Rendered, not rewritten: the texts are grandfathered under the em dash
rule and translated in twelve languages, and a change of slant is not a change
of their prose. The rule for ``*word*`` has to keep ``L*``, ``a*``, ``b*`` and
file filters like ``(*.cal)`` out, because they sit in the same texts.

OFFSCREEN: a check of the renderer's output; the window is photographed on
screen by `scripts/drive_b8_1521_italic.py`.
"""
from __future__ import annotations

import glob
import re
from pathlib import Path

import pytest

from core.help_markup import escape_bold, has_markup, strip_bold, strip_markup, to_html

ROOT = Path(__file__).resolve().parents[1]
_FILES = [ROOT / "data" / "parameters.yaml"] + sorted(
    Path(p) for p in glob.glob(str(ROOT / "data" / "i18n" / "parameters.*.yaml")))
# the six emphasised runs as the challenge found them (English)
_ENGLISH = ("*perceived*", "*inside*", "*in addition to*", "*surface*",
            "*step counter*", "*entire*")


def test_an_emphasised_run_is_italic_and_loses_its_asterisks():
    """MUTATION, proven red: drop `_escape_emph` from `escape_bold`."""
    s = "**Note:** this is the *step counter* form, on the *surface*."
    out = escape_bold(s)
    assert out == ("<b>Note:</b> this is the <i>step counter</i> form, on the "
                   "<i>surface</i>.")
    assert "*" not in to_html(s)
    assert strip_markup(s) == "Note: this is the step counter form, on the surface."


@pytest.mark.parametrize("s", [
    "L*a*b* values", "ΔL*, Δa*, Δb* against its aim", "a* and b* stay",
    "files (*.cal);;All files (*)", "5 * 3 = 15", "the CIE L* scale",
])
def test_colour_axes_and_file_filters_are_not_emphasis(s):
    """MUTATION, proven red: `_EMPH_RE` without its letter lookarounds (``L*a*b*``
    loses an asterisk)."""
    assert escape_bold(s) == s.replace("&", "&amp;").replace("<", "&lt;") \
        .replace(">", "&gt;")
    assert strip_markup(s) == s
    assert not has_markup(s)


def test_the_em_dash_rule_still_reads_the_frozen_string():
    """The em dash baseline froze these helps WITH their asterisks, so the rule
    reads them with only the bold marks removed."""
    s = "**When:** on the *surface* of the cube — N steps"
    assert strip_bold(s) == "When: on the *surface* of the cube — N steps"


def test_the_six_english_runs_are_all_rendered():
    text = (ROOT / "data" / "parameters.yaml").read_text(encoding="utf-8")
    for run in _ENGLISH:
        assert run in text, run
        assert f"<i>{run[1:-1]}</i>" in escape_bold(text), run


@pytest.mark.parametrize("path", _FILES, ids=lambda p: p.name)
def test_no_help_shows_a_single_asterisk_round_a_word(path):
    """Every help of every language, rendered: no ``*word*`` survives."""
    rendered = escape_bold(path.read_text(encoding="utf-8"))
    left = re.findall(r"(?<![*\w])\*[^\W\d_][^*\n]{0,40}?[^\W_]\*(?![*\w])",
                      rendered)
    assert not left, left
