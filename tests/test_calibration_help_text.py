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
    tip = next(k for k in keys if k.startswith("Are you preparing the printer"))
    assert "• Calibration" in tip
    assert "one particular profile" not in tip        # that is the run box's job
    assert "optional" in tip, "the user must know they can skip it"
    assert "Preferences" in tip, "say where the option lives"
    # The bullets follow the dropdown, which follows the order of the work
    # (Basti, beta.142). A help text that lists them in a different order than
    # the list it explains is a help text that has to be read twice.
    assert (tip.index("• Calibration") < tip.index("• Profiling")
            < tip.index("• Verification")), "the bullets must match the list"
    assert "already selected" in tip, (
        "say that Profiling is still the default, or being first reads as "
        "being the normal choice"
    )


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
    data = yaml.safe_load(open("data/parameters.yaml", encoding="utf-8"))["parameters"]
    n = next(p for p in data["printtarg"] if p["flag"] == "-N")
    body = n["tooltip_body"]
    assert "EVERY INK IS WRITTEN TO THE FILE EITHER WAY" in body
    assert "only supports up to" not in body
    assert n["expert_only"] is False, "decision 8: surface it"
    assert n["default"] is False, "decision 8: never decide it for the user"


# ---- the two new windows --------------------------------------------------
def test_the_replace_windows_say_what_each_one_really_does():
    """The two windows now promise DIFFERENT things, and that is the point.

    The owner ruled on 2026-09-02 that an unmeasured calibration chart is
    replaced rather than kept, the way a profile run's chart is, because
    somebody trying layouts is experimenting and not building an archive. So
    the measured window still promises the archive and the unmeasured one must
    NOT - saying "you can go back to it" about a chart that has just been
    discarded is exactly the fault this whole area was fixed for.

    THIS TEST USED TO PICK ITS TARGET WITH `next(...)` on "move to the
    project", which both windows now contain, so it read whichever key came
    first and passed or failed on iteration order - it failed inside the gate
    and passed alone on the same tree. Each window is addressed by its own
    headline now.
    """
    keys = _catalog_keys()
    measured_head = "This project already has a finished calibration"
    unmeasured_head = "You already made a calibration chart for this project"
    for start in (measured_head, unmeasured_head):
        assert any(k.startswith(start) for k in keys), start

    # The measured window keeps the promise, and keeps it in full.
    kept = [k for k in keys
            if "move to the project" in k and "nothing is deleted" in k]
    assert kept, "no window promises the archive any more"
    assert any("go back to them at any time" in k for k in kept), (
        "the measured window stopped promising you can go back to it")

    # The unmeasured window says the opposite, and says it plainly.
    body = next((k for k in keys
                 if "the chart you have now is not kept" in k), None)
    assert body is not None, (
        "the unmeasured window no longer says the chart is not kept")
    # THE PROMISE, NOT THE PHRASE. A first version of this asserted that
    # "go back to" was absent, and the approved text legitimately contains
    # "treats it as an attempt rather than as work to go back to" - the same
    # words used to say the opposite thing. What must be absent is the
    # PROMISE, so the promise is what is named.
    for promise in ("you can go back to it at any time",
                    "go back to them at any time"):
        assert promise not in body, (
            f"the unmeasured window still promises {promise!r} about a chart "
            f"it discards")


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


# ---- help text must name the tab correctly in BOTH states ----------------
def test_no_help_text_assumes_the_calibration_tab_name(qapp):
    """Tab 4 is called “Build Profile” — and “Calibration & Profiling” only
    while calibration options are switched on (``ui/main_window.py``).

    Basti, beta.144: *"the run descriptions tooltip mentions the calibration
    and profiling tab. but without calibration options enabled in preferences
    the tab is called build profile."* Any text that names one of those two
    without saying so sends half the users looking for a tab they do not have.

    Text that is only ever SHOWN with calibration on may name it freely; this
    checks the two that are shown either way.
    """
    from ui.dialogs.welcome_dialog import GLOSSARY
    from ui.tabs.tab_chart import TabChart

    both_names = ("Build Profile", "Calibration & Profiling")

    entry = next(body for term, body in GLOSSARY if term == "Run description")
    assert all(n in entry for n in both_names), (
        "the Dictionary's “Run description” entry names one tab name but not "
        "the other, and it is read whether or not calibration is switched on"
    )

    tip = TabChart._run_description_tooltip(None)
    assert all(n in tip for n in both_names), (
        "the “Run N Description” tooltip names one tab name but not the other"
    )
    assert "Preferences" in tip, (
        "say WHY the tab has two names, or the reader is left guessing which "
        "one they should be seeing"
    )


def test_return_never_replaces_a_calibration_chart():
    """The app's own rule, written at three other doors: *"Return must never
    be a replace"*.

    This window was the exception, and since the owner's 2026-09-02 ruling its
    accept button DISCARDS an unmeasured chart that is kept nowhere, so a
    stray Return was the cheapest possible way to lose it.
    """
    import inspect

    from ui.tabs.tab_chart import TabChart
    src = inspect.getsource(TabChart._confirm_replacing_calibration)
    assert "box.setDefaultButton(cancel)" in src, (
        "Return activates the button that replaces the chart")
    assert "box.setDefaultButton(ok)" not in src


#: Windows allowed to make their accept button the Return default, each with
#: the reason. An entry here is a decision, not an oversight.
_RETURN_DEFAULT_ALLOWED = {
    # The profiling-chart overwrite question. Its whole area - when it warns,
    # what it keeps - is DEFERRED by the owner (2026-09-02: "defer this for
    # now and leave it as it is"), so its Return default is not ours to change
    # while that stands. Recorded rather than silently skipped, so it comes
    # back the moment the deferral lifts.
    ("ui/tabs/tab_chart.py", "_ask_chart_question"),
}


def test_every_destructive_window_keeps_return_safe():
    """The rule is app-wide, so it is checked app-wide rather than at one door.

    TWO WRONG VERSIONS CAME FIRST, and both are worth recording. The first
    matched the button's NAME and walked past `go = box.addButton(go_label,
    ...)`. The second flagged every window that correctly defaults to Cancel,
    twelve false alarms, because `cancel`, `keep`, `back` and `_stop` are
    exactly what SHOULD be the default. The question is the button's ROLE: a
    default carrying AcceptRole is the button that does the thing.
    """
    import pathlib
    import re

    bad = []
    for path in sorted(pathlib.Path("ui").rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        for dm in re.finditer(r"setDefaultButton\(\s*(\w+)\s*\)", text):
            name = dm.group(1)
            am = None
            for cand in re.finditer(
                    rf"\n\s*{re.escape(name)}\s*=\s*(?:box|_box)\.addButton\(",
                    text[:dm.start()]):
                am = cand
            if am is None:
                continue                       # built some other way
            call = text[am.end():am.end() + 300]
            if "AcceptRole" not in call.split(")")[0] + ")":
                continue                       # not the button that acts
            window = text[am.start():dm.start() + 200]
            if "Cancel" not in window and "Go back" not in window:
                continue                       # no safe alternative offered
            before = text[:am.start()]
            fn = re.findall(r"\n    def (\w+)\(", before)
            owner = (str(path), fn[-1] if fn else "?")
            if owner in _RETURN_DEFAULT_ALLOWED:
                continue
            bad.append(f"{path}:{before.count(chr(10)) + 2} ({owner[1]}) "
                       f"makes {name!r}, an AcceptRole button, the Return default")
    assert not bad, (
        'Return activates a destructive button - the app\'s own rule is '
        '"Return must never be a replace":\n  ' + "\n  ".join(bad))


def test_the_allowed_list_is_not_a_way_to_hide_new_ones():
    """A guard with an exemption list is only honest if the list is checked.

    Proves the scanner still SEES the exempt window, so the entry cannot
    quietly become dead while the pattern drifts past it.
    """
    import inspect
    import re

    from ui.tabs.tab_chart import TabChart
    src = inspect.getsource(TabChart._ask_chart_question)
    m = re.search(r"(\w+)\s*=\s*box\.addButton\(", src)
    assert m, "the exempt window no longer builds its button that way"
    assert f"setDefaultButton({m.group(1)})" in src, (
        "the exempt window no longer makes its accept button the default - "
        "remove it from _RETURN_DEFAULT_ALLOWED")
