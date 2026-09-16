"""Help text names a control the app actually has, and reaches every language.

Three faults of one shape, found by a tester and then by measuring for the rest
(2026-09-16). All three are user-facing text that was written once and never
looked at again:

1.  The Print Chart tab's **Load image (TIFF)** tooltip, and the status line it
    shows after an image is loaded, both sent the reader to *"the grid button"*
    to load a `.ti2`. That button left this tab in #130, when the app's three
    whole-app actions moved into the masthead; the control is now
    "Open Chart File (.ti2)" at the top left of the window. The tab's own
    source comment recorded the move at the time and the tooltip below it was
    never updated, so the help described a button nobody could find for weeks.

2.  The Measure tab's **averaging-failed** window put its title through `tr()`
    and its body not at all, so eleven of the twelve languages showed the body
    in English. It also carried an em dash, against the house rule.

3.  The Print Chart tab's lp-path print warning, three sentences of it, was
    never wrapped either.

2 and 3 share a mechanism worth keeping named: both were invisible to
`i18n_extract.unwrapped_literals`, which only ever inspected a bare literal
argument. `QLabel("…" + detail + "…")` and
`setText("…" + fallback_sentence)` make the whole argument a `BinOp`, so the
sweep skipped the argument and every literal in it. Measured across the whole
app the day it was fixed: those four sentences were the ONLY ones hidden that
way. The sweep now looks through `+`, and `is_user_facing_text` judges a string
by the words outside its tags rather than refusing anything that opens with
one, which is what let `"<b>The reads could not be averaged.</b>"` pass for
markup.

WHAT THIS FILE CANNOT SEE: it pins the three strings that were wrong, by
content. A fourth tooltip naming a fourth vanished control is not caught here.
The general guard is the widened sweep, checked at the bottom.
"""
from __future__ import annotations

import inspect
import json
import os
import sys
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from ui.tabs import tab_print, tab_measure            # noqa: E402
from i18n_extract import (                            # noqa: E402
    extract_keys, is_user_facing_text, unwrapped_literals,
)

#: The masthead control the tooltip has to send people to, spelled the way the
#: masthead spells it. Taken from the button itself below, not from memory.
THE_CONTROL = "Open Chart File (.ti2)"


def _code_only(src: str) -> str:
    """*src* with its `#` comments removed.

    Needed because this file's own assertions are about what the code DOES, and
    the code it checks explains itself in comments that quote the very shapes
    being banned. Two of these tests passed against a comment on their first
    run, which is the cheapest possible demonstration of why.
    """
    out = []
    for line in src.splitlines():
        stripped = line.lstrip()
        if stripped.startswith("#"):
            continue
        out.append(line)
    return "\n".join(out)


def _catalogue(code: str) -> "dict[str, str]":
    with open(ROOT / "data" / "i18n" / f"{code}.json", encoding="utf-8") as f:
        return json.load(f)


# ---- 1. the tooltip names a control the app has --------------------------

def _load_image_strings() -> "list[str]":
    """The tooltip and the status line, read out of the source that sets them.

    Read from the source rather than from a built tab, because building a
    `TabPrint` is two seconds of Qt and the question is about a literal.
    """
    src = inspect.getsource(tab_print)
    out = []
    for marker in ('"Load image (TIFF).\\n"',
                   '"Image loaded for printing (no colour management). To '
                   'measure a "'):
        assert marker in src, f"the string that starts {marker} is gone"
    for key in extract_keys():
        if key.startswith("Load image (TIFF)."):
            out.append(key)
        elif key.startswith("Image loaded for printing"):
            out.append(key)
    return out


def test_both_load_image_strings_are_still_there():
    """Guard the guard: the two tests below prove nothing about zero strings."""
    assert len(_load_image_strings()) == 2, _load_image_strings()


@pytest.mark.parametrize("which", ("tooltip", "status"))
def test_the_load_image_help_does_not_send_anyone_to_the_grid_button(which):
    """THE FAULT. This tab has had no grid button since #130."""
    s = [t for t in _load_image_strings()
         if t.startswith("Load image" if which == "tooltip"
                         else "Image loaded")][0]
    assert "grid button" not in s, (
        f"the {which} still names a control this tab does not have: {s!r}")


@pytest.mark.parametrize("which", ("tooltip", "status"))
def test_the_load_image_help_names_the_masthead_control(which):
    """…and it names the one that replaced it, spelled the masthead's way."""
    s = [t for t in _load_image_strings()
         if t.startswith("Load image" if which == "tooltip"
                         else "Image loaded")][0]
    assert THE_CONTROL in s, (
        f"the {which} does not say where a .ti2 is opened now: {s!r}")
    assert "at the top left of the window" in s, (
        f"the {which} names the control but not where it is: {s!r}")


def test_the_masthead_really_spells_it_that_way():
    """The name above is checked against the button, so a rename of the button
    fails here rather than leaving two tabs disagreeing in silence."""
    from ui import masthead_header
    src = inspect.getsource(masthead_header)
    assert f'"{THE_CONTROL}\\n\\n"' in src, (
        f"the masthead no longer opens its tooltip with {THE_CONTROL!r}; the "
        "Print Chart tooltip points at that spelling")


def test_the_tooltip_does_not_repeat_the_run_guard():
    """A DELIBERATE OMISSION, pinned so it is not "fixed" by accident.

    The tester's report also said a profile run should be selected before a
    chart is opened. It should, and the app already says so at the moment it
    matters: `TabPrint._blocked_by_new_run` raises
    `core.measurement_target.new_run_guard_message("print")` when Print is
    pressed with **Profile run** on "New run", in the reviewer's own wording,
    and it names every way to make a run. Repeating that in a tooltip on a
    button that neither opens nor creates a chart would add a paragraph and
    change no outcome, so the tooltip stays about the button.
    """
    from core.measurement_target import new_run_guard_message
    guard = new_run_guard_message("print")
    assert "Profile run" in guard and "print" in guard.lower(), guard
    src = inspect.getsource(tab_print.TabPrint._blocked_by_new_run)
    assert "new_run_guard_message" in src, (
        "the run guard is gone, so the tooltip's omission is no longer safe")
    tip = [t for t in _load_image_strings() if t.startswith("Load image")][0]
    assert "Profile run" not in tip, (
        "the run guard moved into the tooltip; if that is wanted, say so here "
        "rather than in two places")


# ---- 2. the averaging-failed window speaks every language ----------------

AVERAGE_FAILED = (
    "<b>The reads could not be averaged.</b><br><br>{detail}<br><br>Your "
    "individual reads are still saved, you can continue from the Build "
    "Profile tab using one of them."
)


def test_the_averaging_failed_window_is_one_translatable_sentence():
    """Body through `tr()`, and `detail` a PLACEHOLDER rather than a `+`.

    The concatenation is the part that mattered: it hid the string from the
    sweep, and it also handed a translator two fragments to put a runtime
    reason between, in an order English chose for them.
    """
    src = _code_only(
        inspect.getsource(tab_measure.TabMeasure._show_average_failed_dialog))
    assert "{detail}" in src, "the detail is not a placeholder"
    assert 'tr("<b>The reads could not be averaged' in src, \
        "the body does not go through tr()"
    assert '+ detail' not in src, "the body is still concatenated"
    assert AVERAGE_FAILED in extract_keys(), \
        "the body is not a key the catalogues can be checked against"


def test_the_averaging_failed_window_carries_no_em_dash():
    assert "—" not in AVERAGE_FAILED


def test_the_averaging_failed_window_is_german_in_german():
    de = _catalogue("de")
    assert AVERAGE_FAILED in de, "the key never reached the German catalogue"
    assert de[AVERAGE_FAILED] != AVERAGE_FAILED, \
        "the German catalogue still holds the English"
    assert "{detail}" in de[AVERAGE_FAILED], \
        "the German lost the placeholder the reason goes into"
    assert "—" not in de[AVERAGE_FAILED], \
        "the German added an em dash its source does not have"


def test_the_promise_the_window_makes_is_one_the_code_keeps():
    """"Your individual reads are still saved" is a PROMISE, so it is checked.

    It used to be false: every read had already been moved into `reads/` and
    `average` writes its output only on success, so this ending handed back a
    run with no `.ti3` at all under a window saying Build Profile could
    continue from one. Round 5 gave the ending a file back. This test pins the
    two halves the sentence depends on: the newest read is COPIED back (so
    `reads/` keeps everything), and the tab the sentence names is armed.
    """
    src = inspect.getsource(tab_measure.TabMeasure._run_average_and_proceed)
    assert "_put_the_last_read_back" in src, (
        "the failure branch no longer puts a read back, so the window's "
        "closing sentence is a promise the app does not keep")
    assert "measure_finished.emit" in src, \
        "Build Profile is no longer armed on this ending"
    back = inspect.getsource(tab_measure.TabMeasure._put_the_last_read_back)
    assert "shutil.copy2" in back, (
        "the read is moved rather than copied; 'your individual reads are "
        "still saved' stops being true the moment it is a move")


# ---- 3. the lp-path print warning ----------------------------------------

PRINT_WARNING = (
    "⚠  Verify that all print settings above match the media you are printing "
    "on.\n\nWrong media type or quality settings will cause incorrect ink "
    "laydown and invalid colour measurements. Allow pigment inks to dry fully "
    "before measuring (at least 1 h; 24 h for best accuracy).\n\nColour "
    "management is disabled automatically. ChromIQ converts the chart to "
    "PostScript and sends it via lp, bypassing ColorSync entirely. {fallback}"
)

FALLBACKS = (
    "If CUPS rejects PostScript (e.g. AirPrint or Driverless drivers), it "
    "automatically retries by sending the TIFF directly with "
    "colour-space-aware raster options.",
    "If CUPS rejects PostScript (most non-PostScript printers), it "
    "automatically retries with an exact-size PDF that keeps the chart at "
    "100% scale (edges beyond the printable area are clipped, never shrunk).",
)


@pytest.mark.parametrize("text", (PRINT_WARNING,) + FALLBACKS)
def test_every_sentence_of_the_lp_print_warning_is_translatable(text):
    assert text in extract_keys(), f"never reaches tr(): {text[:60]!r}"


@pytest.mark.parametrize("text", (PRINT_WARNING,) + FALLBACKS)
def test_every_sentence_of_the_lp_print_warning_is_german_in_german(text):
    de = _catalogue("de")
    assert text in de, f"missing from the German catalogue: {text[:60]!r}"
    assert de[text] != text, f"still English in German: {text[:60]!r}"


def test_the_fallback_sentence_is_a_placeholder_not_a_concatenation():
    """So a translator is handed the warning whole, and can put the fallback
    where their language wants it."""
    src = _code_only(inspect.getsource(tab_print.TabPrint))
    assert "{fallback}" in src, "the fallback is not a placeholder"
    assert "+ fallback_sentence" not in src, \
        "the warning is still built by concatenation"


# ---- the general guard: the sweep that could not see any of this ---------

def test_the_sweep_looks_through_concatenation():
    """The mechanism, not the three strings. A `+` in the argument used to make
    every literal in it invisible."""
    import ast
    from i18n_extract import _literal_leaves
    node = ast.parse('"one sentence " + detail + " and another"',
                     mode="eval").body
    assert [n.value for n in _literal_leaves(node)] == \
        ["one sentence ", " and another"]
    # …and a tr() call inside the sum yields nothing: it is already translated.
    node = ast.parse('tr("already") + detail', mode="eval").body
    assert [n.value for n in _literal_leaves(node)] == []
    # AND THE SWEEP ACTUALLY CALLS IT. Proving the helper alone proves nothing:
    # a mutation that put the old `isinstance(arg, ast.Constant)` test back at
    # the call site left this test green, because narrowing the sweep can only
    # ever make it report FEWER hits and no assertion anywhere could see that.
    from i18n_extract import unwrapped_literals as _sweep
    assert "_literal_leaves" in inspect.getsource(_sweep), (
        "the sweep no longer looks through concatenation; every literal in a "
        "`\"…\" + value` argument is invisible again")


def test_a_sentence_that_opens_with_a_tag_is_still_a_sentence():
    """`^\\s*<` used to read "markup" and wave the whole string through, which
    is every rich-text window this app opens."""
    assert is_user_facing_text("<b>The reads could not be averaged.</b>")
    assert is_user_facing_text("<b>Done.</b><br>Nine patches were read.")
    # …while pure markup, a key and a stylesheet are still not text.
    assert not is_user_facing_text("<br><br>")
    assert not is_user_facing_text("area_first")
    assert not is_user_facing_text("QLabel { color: #ffffff; }")


def test_the_widened_sweep_finds_nothing_left():
    hits = unwrapped_literals()
    assert hits == [], (
        f"{len(hits)} user-facing literals never reach tr():\n"
        + "\n".join(f"    {f}:{ln}  {sink}(arg{i})  {text[:60]!r}"
                    for f, ln, sink, i, text in hits[:10]))


def test_the_comment_stripper_actually_strips():
    """Guard the guard: without this, two tests above pass against a comment."""
    assert _code_only("    # + detail\n    x = 1\n") == "    x = 1"
    assert "+ detail" not in _code_only("# a note about + detail\ny = 2\n")
    assert "keep" in _code_only('s = "keep this"  # + detail\n')
