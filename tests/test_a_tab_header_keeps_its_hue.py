"""A tab's step stroke must survive an appearance change.

THE FAULT. `TabHeader` stores the accent it is handed and repaints from that
value for the life of the widget; `_paint_accent` asks
`index_rule.use_index_rule()` for itself, so it already substitutes Neutral's
single ACTION value at PAINT time. One tab wrapped its hue in `accent_for`
BEFORE handing it over — so a Create Chart tab built while Neutral was on
screen stored `#101010` and had no hue left to go back to. Preferences ->
Appearance -> Light then repainted the value it was given, and the 22x2 px
stroke before "STEP 01 - GENERATE CHART" stayed black while the other four
tabs got their colour back.

Two assertions, because the fault has two halves:

* the component must give a hue back when the appearance stops being Neutral;
* every one of the five tabs must hand it a HUE, not a value already collapsed.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from ui import neutral_styles as nm
from ui.light_styles import make_light_palette
from ui.neutral_styles import make_neutral_palette
from ui.styles import make_dark_palette

#: The five tabs, and the hue each one's step stroke wears in Light and Dark.
TABS = {
    "ui/tabs/tab_chart.py":        "#ff4573",
    "ui/tabs/tab_print.py":        "#ffb42d",
    "ui/tabs/tab_measure.py":      "#56d6a5",
    "ui/tabs/tab_profile.py":      "#37bcd6",
    "ui/tabs/tab_check_refine.py": "#9f82ff",
}

ROOT = Path(__file__).resolve().parents[1]


def _accent_argument(source: str) -> str:
    """The third positional argument of the file's ``TabHeader(`` call.

    Read from the source rather than from a constructed tab: building all five
    tabs costs ~10 s and this question is about the call, not the widget.
    """
    i = source.index("TabHeader(")
    chunk = source[i + len("TabHeader("):]
    # Whole-line comments out: a hue is written `"#ff4573"`, so a naive `#`
    # split would eat the value itself. Only lines that are NOTHING but a
    # comment are dropped, and a hex literal never starts a line.
    chunk = "\n".join(ln for ln in chunk.splitlines()
                      if not ln.lstrip().startswith("#"))
    depth, out = 0, []
    for ch in chunk:
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            if depth == 0:
                break
            depth -= 1
        elif ch == "," and depth == 0:
            out.append("")
            continue
        if out:
            out[-1] += ch
        else:
            out.append(ch)
    # step_text, title_text, accent, parent, ...
    return out[2].strip()


@pytest.mark.parametrize("path,hue", sorted(TABS.items()))
def test_every_tab_hands_its_header_a_raw_hue(path, hue):
    """Not ``accent_for(hue)`` — the substitution belongs at paint time.

    A value collapsed here cannot be un-collapsed: the header keeps what it is
    given, so the tab loses its colour permanently the moment the window is
    built under Neutral.
    """
    arg = _accent_argument((ROOT / path).read_text(encoding="utf-8"))
    assert arg == f'"{hue}"', (
        f"{path} hands TabHeader {arg!r}; it must hand the bare hue "
        f'"{hue}" and let TabHeader._paint_accent decide what to paint'
    )


def test_a_header_built_under_neutral_gets_its_hue_back(qapp):
    """The whole journey: build in Neutral, switch to Light, then to Dark."""
    from ui.tab_header import TabHeader

    original = qapp.palette()
    try:
        qapp.setPalette(make_neutral_palette())
        header = TabHeader("STEP 01", "Create test chart", "#ff4573")
        assert nm.NM_ACTION in header._bar.styleSheet(), (
            "under Neutral the stroke must be the single ACTION value")

        qapp.setPalette(make_light_palette())
        header.set_appearance("light")
        assert "#ff4573" in header._bar.styleSheet(), (
            "the hue did not come back after switching to Light")

        qapp.setPalette(make_dark_palette())
        header.set_appearance("dark")
        assert "#ff4573" in header._bar.styleSheet(), (
            "the hue did not come back after switching to Dark")

        qapp.setPalette(make_neutral_palette())
        header.set_appearance("neutral")
        assert nm.NM_ACTION in header._bar.styleSheet(), (
            "the stroke did not go back to ACTION on returning to Neutral")
        header.deleteLater()
    finally:
        qapp.setPalette(original)
