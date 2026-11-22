"""The ⓘ of "Suppress warning messages (-S)" names what -S really turns off
(4.3.57, item 15).

It named calibration notices, dark-patch range warnings and strip timing;
-S touches none of them. ArgyllCMS's chartread manual: -S suppresses the
"wrong strip" and "unexpected value" warnings, and in the reading helper
`emit_warnings` gates exactly those.
"""
import re
from pathlib import Path

from ui.tabs.tab_measure import suppress_warnings_help

HELPER = Path(__file__).resolve().parent.parent / "native" / \
    "chartread_helper" / "chromiq_chartread.c"


def test_the_help_names_the_two_warnings_and_nothing_else():
    text = suppress_warnings_help()
    assert "Seem to have read strip" in text
    assert "very unexpected response" in text
    for wrong in ("calibration has changed", "timing", "dark patches"):
        assert wrong not in text


def test_the_helper_still_gates_only_those_warnings_on_minus_s():
    """If the helper ever gates another message on -S, the help is wrong
    again: three places, the wrong strip and the unexpected response of a
    strip and of one patch."""
    src = HELPER.read_text(encoding="utf-8", errors="replace")
    uses = re.findall(r"if \(.*emit_warnings != 0", src)
    assert len(uses) == 3, uses


def test_both_measure_modes_use_it():
    import inspect
    from ui.tabs import tab_measure
    assert inspect.getsource(tab_measure).count("suppress_warnings_help(),") == 2
