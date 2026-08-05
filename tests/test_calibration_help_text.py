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


# ---- the "how do I calibrate?" card (Knut, 2026-08-05) -------------------
# *"You really should make a help card for how to perform a printer
# calibration, also describing for a user how this is different from a printer
# profile."*
def _card():
    from ui.dialogs.welcome_dialog import WORKFLOWS
    return next(w for w in WORKFLOWS if w["key"] == "calibrate_printer")


def test_the_calibration_card_exists():
    card = _card()
    assert "calibrat" in card["title"].lower()
    assert card["steps"], "a card with no steps teaches nothing"


def test_it_explains_how_a_calibration_differs_from_a_profile():
    """The half of the request that is easy to skip: not just HOW, but WHAT it
    is and why it is not the other thing."""
    body = " ".join(str(s[1]) for s in _card()["steps"])
    assert "NOT A PROFILE" in body or "not a profile" in body.lower()
    # The distinction itself, in both directions.
    assert "changes the printer" in body
    assert "changes nothing about the printer" in body
    # Both file endings, so the user can tell them apart on disk.
    assert ".cal" in body and ".icc" in body


def test_it_says_who_actually_needs_this():
    """Most people do not, and the card must say so — advertising a step
    nobody needs is how people end up with worse results, not better."""
    body = " ".join(str(s[1]) for s in _card()["steps"])
    assert "Most people do not" in body


def test_it_names_the_exact_controls():
    """House rule: name the element to click, never "tick the box"."""
    body = " ".join(str(s[1]) for s in _card()["steps"])
    for label in ("Enable calibration options", "Run type", "Generate Chart",
                  "Create Calibration File", "Single Channel Steps",
                  "Apply Calibration File", "Include Calibration File"):
        assert label in body, f"the card never names {label!r}"


def test_it_warns_that_recalibrating_dates_the_profile():
    """The trap that costs real work: a profile describes the printer as it
    was, so a new calibration silently makes old profiles inaccurate."""
    body = " ".join(str(s[1]) for s in _card()["steps"])
    assert "no longer" in body and "Build a fresh profile" in body
    # …and the reassurance that nothing is destroyed while doing it.
    assert "cal/old" in body


def test_it_covers_both_ways_to_apply_a_calibration():
    body = " ".join(str(s[1]) for s in _card()["steps"])
    assert "RIP" in body                      # the printer/RIP applies it
    assert "bake" in body or "Apply" in body  # …or ChromIQ bakes it in


# ---- the folder guide must not drift from the folders that exist ---------
# Knut, beta.141: *"Help card 'Where are my files?' is not fully updated with
# regards to folder locations."* He was right — #137 created cal/chart/ and
# cal/old/ and they reached the descriptions list but not the drawn tree, so
# the card showed a calibration folder with one child instead of three.
def test_the_tree_shows_every_calibration_folder():
    from ui.file_guide import tree_rows

    drawn = {name for _prefix, name, _meaning in tree_rows()}
    for folder in ("cal/", "chart/", "old/", "exports/"):
        assert folder in drawn, f"the folder tree never shows {folder}"


def test_the_tree_and_the_descriptions_agree_about_cal():
    """Two lists describing one layout is how they drift; this ties them."""
    from ui.file_guide import _folders, tree_rows

    described = {path for path, _ in _folders()}
    for path in ("cal/", "cal/chart/", "cal/old/"):
        assert path in described, f"{path} has no description"
    # …and each has a row in the tree (matched by its own last segment).
    drawn = {name for _p, name, _m in tree_rows()}
    assert {"cal/", "chart/", "old/"} <= drawn


def test_both_chart_snapshot_folders_are_real():
    """Knut asked whether run1/chart/ AND verifications/<date>/chart/ both
    exist, or only the one under a verification date. Both do, and they hold
    different charts — this asserts it against the code, not the document."""
    from core.file_manager import CHART_SNAPSHOT_DIRNAME
    from workflow.chart_slot import slot_for_run, slot_for_verification
    import inspect

    assert CHART_SNAPSHOT_DIRNAME == "chart"
    assert "run.dir / CHART_SNAPSHOT_DIRNAME" in inspect.getsource(slot_for_run)
    assert "verification.dir / CHART_SNAPSHOT_DIRNAME" in inspect.getsource(
        slot_for_verification)
