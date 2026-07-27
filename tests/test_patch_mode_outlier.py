"""#131 (Knut, 2026-07-27): the two reading modes judge patches differently, and
the help texts have to say so.

He asked how "standing out" could be judged from a handful of patches, I offered
three answers, and his ruling was **option (a)**: patch by patch keeps the plain
ΔE limit — *"but make sure to describe the differences in the help text icons for
strip mode and patch-to-patch mode. in the help text for patch-to-patch mode
compare with the solution used in strip mode and why the results then behave
differently."*

So the code is the simple half, and these tests mostly guard the explanation:
a user who sees more red outlines patch by patch than in a strip must be able to
find out why without asking.
"""
from __future__ import annotations

import inspect

from ui.tabs.tab_measure import TabMeasure, _strip_outlier_fence


# ---- the rule itself -------------------------------------------------------
def test_patch_mode_uses_the_limit_alone():
    """Option (a): no comparison against anything, because there is nothing to
    compare against."""
    src = inspect.getsource(TabMeasure._on_patch_measured)
    assert "de_p >= warn_de)" in src
    assert "_use_outlier_fence" not in src, \
        "patch mode must not consult the strip comparison"
    assert "_spot_des" not in src, \
        "the running-population idea was withdrawn on Knut's ruling"


def test_strip_mode_still_compares_within_the_strip():
    src = inspect.getsource(TabMeasure._on_strip_measured)
    assert "_use_outlier_fence()" in src
    assert "_strip_outlier_fence(" in src


def test_the_comparison_needs_a_population_to_be_meaningful():
    """Which is exactly why it cannot be used patch by patch."""
    assert _strip_outlier_fence([]) == 0.0
    assert _strip_outlier_fence([10.0, 12.0, 11.0]) == 0.0
    des = [8.0, 9.0, 8.5, 9.5, 10.0, 8.2, 9.1, 8.8, 9.3, 8.6, 70.0]
    assert 10.0 < _strip_outlier_fence(des) < 70.0


def test_a_uniformly_bad_strip_flags_nothing_extra():
    """Knut's deliberately-wrong chart: everything far off together, so nothing
    stands out — which is what the switch exists to turn off."""
    des = [55.0, 58.0, 60.0, 57.0, 56.0, 59.0, 61.0, 54.0]
    fence = _strip_outlier_fence(des)
    assert all(d < fence for d in des), fence


# ---- the explanations ------------------------------------------------------
def test_the_patch_mode_help_explains_the_difference():
    """His requirement: compare with the strip-mode solution, and say why the
    results differ."""
    src = inspect.getsource(TabMeasure)
    i = src.index("RED OUTLINES WORK DIFFERENTLY HERE")
    section = src[i:i + 2200]
    assert "no strip to compare against" in section
    assert "flags MORE patches" in section or "flags MORE" in section
    assert "raise the limit" in section, "tell the user what to do about it"


def test_the_patch_mode_help_is_in_both_modules():
    """Guided and Manual each have their own copy of the box."""
    src = inspect.getsource(TabMeasure)
    assert src.count("RED OUTLINES WORK DIFFERENTLY HERE") == 2


def test_the_settings_help_names_both_modes():
    import pathlib
    src = (pathlib.Path(__file__).resolve().parents[1]
           / "ui" / "dialogs" / "settings_dialog.py").read_text()
    assert "PATCH-BY-PATCH MODE IS DIFFERENT, ON PURPOSE" in src
    assert "when you read STRIPS" in src


def test_the_switch_says_it_is_strip_only():
    """It governs strip reading alone now, and must not imply otherwise."""
    import pathlib
    src = (pathlib.Path(__file__).resolve().parents[1]
           / "ui" / "dialogs" / "settings_dialog.py").read_text()
    assert "When reading strips, only flag a patch" in src
    assert "applies to strip reading only" in src
