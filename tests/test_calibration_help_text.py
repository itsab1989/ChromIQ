"""#137 Table H — every user-facing string this feature adds.

Principle 6 of the project's own rules: the beginner's mental model rules the
UI. Friendly, extensive, plain language; the exact UI element named; real
singular/plural, never "(s)"; and a Dictionary entry for every new term.
"""
from __future__ import annotations

import pytest


def _catalog_keys():
    import sys
    sys.path.insert(0, ".")
    from scripts.i18n_extract import extract_keys
    return extract_keys()


# ---- A2 / A3 / A4: the bar ------------------------------------------------
def test_the_run_type_tooltip_explains_calibration(qapp):
    from ui.measurement_target_bar import (MeasurementTargetBar,
                                           MeasurementTargetController)
    from core.file_manager import FileManager

    keys = _catalog_keys()
    tip = next(k for k in keys if k.startswith("Are you building the printer"))
    assert "• Calibration" in tip
    assert "one particular profile" not in tip        # that is the run box's job
    assert "optional" in tip, "the user must know they can skip it"
    assert "Preferences" in tip, "say where the option lives"


def test_the_profile_run_tooltip_says_why_it_is_locked():
    keys = _catalog_keys()
    tip = next(k for k in keys if k.startswith("A calibration describes your printer"))
    assert "There is no run to pick here" in tip
    assert "Switch “Run type”" in tip, "name the exact control to use instead"


# ---- A6 / A7: the greyed Auto boxes --------------------------------------
def test_the_greyed_auto_boxes_answer_all_three_questions():
    keys = _catalog_keys()
    tip = next(k for k in keys if k.startswith("A calibration chart is a plain ramp"))
    assert "Single Channel Steps" in tip            # what decides it instead
    assert "switched off here" in tip               # why it is off
    assert "come back exactly as you left them" in tip   # how to get it back


# ---- A1: the preference ---------------------------------------------------
def test_the_preference_tooltip_is_current():
    keys = _catalog_keys()
    tip = next(k for k in keys if "Unlocks the full printer calibration" in k)
    assert "“Run type”" in tip, "it must name the control that replaced the checkbox"
    assert "calibration target option appears in Create Chart" not in tip
    assert "stays in the project" in tip, "reassure that nothing is lost either way"


# ---- C9: the Dictionary ---------------------------------------------------
def test_the_dictionary_defines_the_new_term():
    from ui.dialogs.welcome_dialog import GLOSSARY as _E
    terms = {t for t, _ in _E}
    assert "Calibration run" in terms
    body = next(b for t, b in _E if t == "Calibration run")
    assert "not a profile run" in body, "bound against the thing it resembles"
    assert "cal" in body                              # where the files land


# ---- C10-C13: the file guide ---------------------------------------------
@pytest.mark.parametrize("folder,must_say", [
    ("cal/", "Nothing needs deleting"),
    ("cal/chart/", "Restore Used Chart"),
    ("cal/old/", "rather than deleting"),
])
def test_the_file_guide_answers_where_are_my_files(folder, must_say):
    from ui.file_guide import _folders
    rows = dict(_folders())
    assert folder in rows, f"{folder} is not in the file guide"
    assert must_say in rows[folder], f"{folder}: {must_say!r} missing"


# ---- A9: the -N control ---------------------------------------------------
def test_the_n_channel_tooltip_is_honest():
    """The old text claimed TIFF "only supports up to 4 channels" and that the
    flag preserves the ink values. Neither is true: every ink is written either
    way, and the flag only changes how the extras are labelled."""
    import yaml
    data = yaml.safe_load(open("data/parameters.yaml"))["parameters"]
    n = next(p for p in data["printtarg"] if p["flag"] == "-N")
    body = n["tooltip_body"]
    assert "EVERY INK IS WRITTEN TO THE FILE EITHER WAY" in body
    assert "only supports up to" not in body
    assert n["expert_only"] is False, "decision 8: surface it"
    assert n["default"] is False, "decision 8: never decide it for the user"


# ---- the two new windows --------------------------------------------------
def test_the_replace_windows_promise_nothing_is_deleted():
    keys = _catalog_keys()
    for start in ("This project already has a finished calibration",
                  "You already made a calibration chart for this project"):
        assert any(k.startswith(start) for k in keys), start
    moved = next(k for k in keys if "move to the project" in k)
    assert "nothing is deleted" in moved
    assert "go back to them at any time" in moved


def test_the_affected_runs_line_has_real_singular_and_plural():
    """Never "Run(s)" — the project's own rule."""
    keys = _catalog_keys()
    one = next(k for k in keys if k.startswith("{run} was built using"))
    many = next(k for k in keys if k.startswith("{runs} were built using"))
    assert "It is not changed" in one and "its profile keeps working" in one
    assert "They are not changed" in many and "their profiles keep working" in many
    assert not any("(s)" in k for k in (one, many))
