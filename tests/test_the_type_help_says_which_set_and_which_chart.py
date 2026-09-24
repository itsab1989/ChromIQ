"""The Report type and Judged against help answers Knut's four questions.

Knut, 2026-09-14::

    the help text for the report type and judged against must describe properly
    what each option are, when they are normally used, and which Judged against
    limit sets are normally matched with which report type. It should also be
    explained how report type and limit sets depend on selection of the right
    chart / preset to be used and how the colors in that chart is selected for
    verification.

Four questions, and the tests below are one per question plus the two traps
this help can fall into.

**The list of types is DATA.** It is built from `REPORT_TYPE_MENU`, so a
seventh type cannot appear in the pulldown and be missing from the help. The
test adds one and looks for it, which is the only way to tell a data-driven
list from a hand-written one that happens to agree today.

**And every control it names must be named as the READER sees it.** The set
names are English in eleven of the twelve catalogues and German in the twelfth;
the "Report limits" window is untranslated everywhere but German; and the
Create Chart tab and the FROM PROFILE GAMUT button ARE translated, differently,
in all twelve. A help text that says "the Report limits window" to a French
reader sends them looking for a window whose title bar says something else. A
first draft did exactly that in eleven languages, in five different places.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest                                                   # noqa: E402

ROOT = Path(__file__).resolve().parents[1]

#: The names each paragraph has to carry, by the English key of the control.
#: Read out of the catalogues, never out of the paragraph.
NAMES_IN = {
    "when": ("Full colour check", "Colour summary (one page)",
             "Grey and tone check", "Printing record (not graded)"),
    "pair": ("ChromIQ default (recommended)", "ChromIQ tight", "Quick check",
             "Custom ISO 12647-7", "Custom ISO 12647-8",
             "Full colour check", "Colour summary (one page)",
             "Grey and tone check", "Printing record (not graded)"),
    "chart": ("FROM PROFILE GAMUT", "1. Create Chart", "Report limits"),
}


def _helps():
    from ui.dialogs.measurement_report_dialog import (_CHART_HELP,
                                                      _PAIRING_HELP,
                                                      _WHEN_HELP)
    return {"when": _WHEN_HELP, "pair": _PAIRING_HELP, "chart": _CHART_HELP}


def _as_prose(name: str) -> str:
    """A control's name the way a sentence carries it.

    No "1. " off the front of a tab, no bracketed aside off the end, and no
    standard number off a limit set: the paragraph says "the matching Custom
    ISO set" where the pulldown offers two of them. The German catalogue calls
    those "Eigene ISO 12647-7" and "Eigene ISO 12647-8", and the first draft
    said "Custom-ISO-Satz" to a reader whose window says neither.
    """
    core = re.sub(r"\s*[（(][^）)]*[）)]\s*$", "", name.split(". ", 1)[-1]).strip()
    return re.sub(r"\s*\d{4,}-\d+$", "", core).strip()


def test_the_help_lists_every_type_the_pulldown_offers():
    """The six in the menu today, by name and by their own description.

    MUTATION: replace the comprehension in `_types_and_pairing_help` with a
    hand-written list of the six and this still passes, which is why the next
    test exists.
    """
    from core.i18n import tr
    from ui.dialogs.measurement_report_dialog import _types_and_pairing_help
    from workflow.measurement_report import REPORT_TYPE_MENU
    body = _types_and_pairing_help()
    for _tid, name, blurb, _built in REPORT_TYPE_MENU:
        assert tr(name) in body, f"the help does not name {name!r}"
        assert tr(blurb) in body, f"the help does not describe {name!r}"


def test_a_seventh_type_cannot_be_missing_from_the_help(monkeypatch):
    """The list is built from the menu, so adding to the menu adds to the help.

    MUTATION: hand-write the six lines in `_types_and_pairing_help` and this
    goes red, which is the whole point of it being data.
    """
    from ui.dialogs.measurement_report_dialog import _types_and_pairing_help
    from workflow import measurement_report as mr
    monkeypatch.setattr(mr, "REPORT_TYPE_MENU", mr.REPORT_TYPE_MENU + (
        ("t9_invented", "Seventh kind of report",
         "Invented by a test, and it has to show up.", True),), raising=True)
    body = _types_and_pairing_help()
    assert "Seventh kind of report" in body
    assert "Invented by a test, and it has to show up." in body


def test_both_icons_answer_the_pairing_and_the_chart_question():
    """A reader opens whichever icon they are standing on, so both carry both.

    MUTATION: drop `_CHART_HELP` from either tooltip and this goes red.
    """
    src = (ROOT / "ui/dialogs/measurement_report_dialog.py").read_text(
        encoding="utf-8")
    # The Report type icon takes both through `_types_and_pairing_help`.
    assert src.count("+ _types_and_pairing_help()") == 1
    # …and the Judged against icon appends the same two paragraphs itself.
    assert src.count(
        '+ "\\n\\n" + tr(_PAIRING_HELP) + "\\n\\n" + tr(_CHART_HELP)') == 2


def test_the_help_says_the_things_a_reader_came_for():
    """What it must say, and what it must NOT claim.

    These are LITERALS on purpose. A test that asks the constant what the
    constant says passes every rewrite, including one that promises the wrong
    thing: an adversary round proved that on this very file by rewriting a
    sentence to promise everything and watching the suite stay green.

    The forbidden list is the more valuable half. Every phrase in it was in a
    draft of this help and was MEASURED to be false:

    * "the set beside it changes nothing in the document" — the Printing
      record still names the set at the top and in Report Scope;
    * "every row of it reads INFO whichever set is beside it" — a row the
      chart cannot supply stays N-A, and under a ChromIQ set the paper and
      solid rows are not drawn at all;
    * "an ordinary test chart has none and the rows read N-A" — they read N-A
      only under a Custom ISO set; a ChromIQ set puts no limit on them, so
      they are dropped from the table;
    * "The report names every row it could not compute and why" — the note is
      EMPTY in the ChromIQ-set case, because there is no row there to name;
    * "half those numbers" / "twice them" said of the sets as a whole — true
      of the five colour difference rows, not of the grey rows (1.5 goes to
      1.0 and 3.0 to 2.0, and Quick check puts the grey maximum at 7.0);
    * "the choice of set matters less there" said of Grey and tone check — it
      matters more: no ChromIQ set limits the mid-tone ramp at all, so that
      row is shown for information whichever set is beside it. (Until
      2026-09-21 the other two were recommendations that could only reach
      COND; Knut retired both the bracket and the word, so the grey rows are
      now judged like any other and the help says so.)
    """
    h = _helps()
    must = {
        # which set goes with which type, and what the numbers really are
        "pair": ("2.0 average and 3.0 maximum", "halves those two",
                 "doubles them",
                 "judges the two grey rows like any other row",
                 "no limit on the mid-tone ramp",
                 "every row it can compute reads INFO", "still names the set",
                 "Custom ISO", "not rules"),
        # when a reader reaches for each type
        "when": ("you keep", "hand over with the job", "neutral problem",
                 # K13: the Printing record is a profiling measurement's
                 # report now, not a job documented without grading
                 "report of a profiling measurement",
                 # …and where the reason for the greyed ISO rows really lives.
                 # Measured on screen across all six demo projects, in both
                 # states: the line under the pulldown says "Already generated
                 # for this run: …" or "No report has been generated for this
                 # run yet." and never mentions the ISO types. The reason is
                 # the disabled row's own tooltip, inside the open list.
                 # K33: the ISO types can be chosen now; the reason for
                 # one that is greyed is still the entry's own tooltip.
                 "if one is greyed, pointing at it says why"),
        # how the chart decides what can be said at all
        "chart": ("eight grey steps from white to black, spread roughly evenly", "single-ink or grey ramp",
                  "FROM PROFILE GAMUT", "aim value", "N-A",
                  "left out of the table",
                  # …and the two scoping words a second round asked for: the
                  # grey and tone rows ARE judged from an ordinary chart's own
                  # design values, so only the aim values THOSE rows need are
                  # missing; and three rows carry no advice at all, so the icon
                  # promises what a row needs rather than a change for each.
                  "no such aim values", "where anything can be"),
    }
    forbidden = {
        "pair": ("changes nothing in the document",
                 "every row of it reads INFO whichever",
                 "half those numbers", "twice them",
                 "matters less there",
                 # …and the qualifier that shipped in its place. Quick check
                 # takes the grey MAXIMUM from 3.0 to 7.0 while the colour
                 # maximum goes 3.0 to 6.0, so that row moves by MORE, both as
                 # a ratio and in millimetres. See the test below.
                 "move with them, by less"),
        "chart": ("has none and the rows read N-A",
                  "names every row it could not compute",
                  "carries no aim values, and",
                  "window says what to change"),
        "when": ("the line under the pulldown says why",
                 # …and the second attempt, which was also not what a reader
                 # sees: the greyed row's own TEXT is just the type's name, and
                 # the reason arrives as a tooltip when you point at it.
                 "greyed entry itself says why when you open the list"),
    }
    for which, phrases in must.items():
        for phrase in phrases:
            assert phrase in h[which], f"{which} help no longer says {phrase!r}"
    for which, phrases in forbidden.items():
        for phrase in phrases:
            assert phrase not in h[which], (
                f"{which} help says {phrase!r} again, which was measured false")
    for which, body in h.items():
        assert "—" not in body, f"{which} help has an em dash in it"


def test_the_numbers_in_the_help_are_the_numbers_in_the_sets():
    """The three figures the pairing paragraph quotes, read out of the sets.

    MUTATION: change any of the six numbers in `compliance_sets.SETS` and this
    goes red, naming the row.
    """
    from workflow.compliance_sets import effective_limits
    lim = {sid: effective_limits(sid, {}) for sid in
           ("chromiq_default", "chromiq_tight", "chromiq_quick")}
    avg = {s: lim[s]["all_de00_avg"].number for s in lim}
    mx = {s: lim[s]["all_de00_max"].number for s in lim}
    assert (avg["chromiq_default"], mx["chromiq_default"]) == (2.0, 3.0), (
        "the help says 2.0 average and 3.0 maximum")
    assert (avg["chromiq_tight"], mx["chromiq_tight"]) == (1.0, 1.5), (
        "the help says ChromIQ tight halves those two")
    assert (avg["chromiq_quick"], mx["chromiq_quick"]) == (4.0, 6.0), (
        "the help says Quick check doubles them")
    # …and the claims about Grey and tone check's own three rows.
    #
    # THE FIRST TWO CHANGED SIDES ON 2026-09-21. The help used to say the grey
    # rows were recommendations that could only reach COND, and it was checked
    # against `is_should`; Knut ruled the brackets off ChromIQ's own sets and
    # retired the word, so the sentence now says they are judged like any other
    # row and this is what holds it to that.
    for sid in lim:
        assert not lim[sid]["grey_balance_neutral_ramp_avg"].is_should, (
            "the help says a ChromIQ set judges the grey rows like any other")
        assert not lim[sid]["grey_balance_neutral_ramp_max"].is_should
        assert lim[sid]["grey_balance_neutral_ramp_avg"].is_numeric, (
            "…and that means judged, so the row must still carry a number")
        assert lim[sid]["ramps_30_70_dl_max"].kind == "none", (
            "the help says no ChromIQ set limits the mid-tone ramp")
    # …AND THE ONE CLAIM ABOUT THE GREY ROWS THAT WAS NOT CHECKED.
    #
    # The paragraph used to end that sentence "; the grey rows move with them,
    # by less." Read out of the sets, that is true three times and false once,
    # and the false one is the row a Quick check reader is most likely to look
    # at: the grey MAXIMUM goes 3.0 -> 7.0 where the colour maximum goes
    # 3.0 -> 6.0. So the grey row moves by 4.0 mm against 3.0, and by a factor
    # of 2.33 against 2.0 -- more on both readings, not less. The qualifier is
    # gone and this is what keeps it gone.
    #
    # MUTATION: put ", by less" back and the forbidden list above goes red;
    # change 7.0 to 6.0 here and this assertion does.
    cq = lim["chromiq_quick"]["grey_balance_neutral_ramp_max"].number
    cd = lim["chromiq_default"]["grey_balance_neutral_ramp_max"].number
    assert (cd, cq) == (3.0, 7.0), (
        "the grey maximum no longer moves further than the colour maximum "
        "does; re-measure before letting the help say 'by less' again")
    assert cq / cd > mx["chromiq_quick"] / mx["chromiq_default"], (
        "Quick check's grey maximum moves by a SMALLER factor than its colour "
        "maximum after all, so 'by less' would be true; re-measure")
    # …AND THAT THERE REALLY ARE THREE OF THEM, WHICH NOTHING ASKED.
    #
    # Round 21: the sentence "Grey and tone check keeps three rows, the two
    # grey balance ones and the mid-tone ramp" is TRUE on 2026-09-15, and the
    # three assertions above only check what those three rows' LIMITS are.
    # Add a fourth row to `REPORT_TYPE_ROWS[t3_grey_and_tone]` and the help
    # goes on telling every reader in twelve languages that the document keeps
    # three, which is the same shape as the "eight grey steps" claim.
    #
    # MUTATION: add a row id to that tuple, or drop one, and this goes red.
    from workflow.measurement_report import (REPORT_TYPE_GREY,
                                             rows_for_report_type)
    assert rows_for_report_type(REPORT_TYPE_GREY) == (
        "grey_balance_neutral_ramp_avg", "grey_balance_neutral_ramp_max",
        "ramps_30_70_dl_max"), (
        "the help says Grey and tone check keeps three rows, the two grey "
        "balance ones and the mid-tone ramp; the document now keeps "
        f"{rows_for_report_type(REPORT_TYPE_GREY)}")
    assert "keeps three rows" in _helps()["pair"]
    # …and that a filled-in Custom ISO set judges all three, which is the
    # sentence right after it.
    custom = effective_limits("custom_iso_12647_7", {})
    for rid in ("grey_balance_neutral_ramp_avg", "grey_balance_neutral_ramp_max",
                "ramps_30_70_dl_max"):
        assert custom[rid].kind in ("value", "should"), rid


def test_the_chart_paragraph_matches_what_a_missing_row_really_does():
    """"Left out of the table" under a ChromIQ set, "N-A" under a Custom ISO one.

    `row_verdict` is the function the report asks, and it answers None for a
    row with no limit and no value, which is what drops the row; N-A is what a
    row with a limit and no value gets.
    """
    from workflow.compliance_sets import N_A, effective_limits, row_verdict
    chromiq = effective_limits("chromiq_default", {})["substrate_de00_max"]
    custom = effective_limits("custom_iso_12647_7", {})["substrate_de00_max"]
    assert row_verdict(chromiq, None, graded=True) is None, (
        "a ChromIQ set would show the paper row rather than drop it")
    assert row_verdict(custom, None, graded=True) == N_A


@pytest.mark.parametrize("code", sorted(
    p.stem for p in (ROOT / "data/i18n").glob("*.json")
    if not p.stem.startswith("parameters")))
def test_every_language_names_the_controls_as_that_language_shows_them(code):
    """The translated help points at names that are on that reader's screen.

    MUTATION: put "la fenêtre Limites du rapport" back into the French chart
    paragraph, where the window's own title bar reads "Report limits", and this
    goes red for fr alone.
    """
    cat = json.loads((ROOT / "data/i18n" / f"{code}.json").read_text(
        encoding="utf-8"))
    for which, english in _helps().items():
        body = cat.get(english)
        assert body, f"{code} has no translation of the {which} help"
        # A BODY THAT IS ITS OWN ENGLISH SOURCE IS NOT TRANSLATED YET, and this
        # guard could not tell that from the fault it was written for.
        #
        # Under the beta rule (German by hand, the eleven others carry the
        # English until a translation round before the final), a help text that
        # has just been reworded sits in eleven catalogues as its English
        # source. Such a body of course names "Custom ISO" rather than "Eigene
        # ISO", and failing on it says "this translation points at the wrong
        # control" about a translation that does not exist. Untranslated
        # strings are COUNTED, in `test_i18n.py::_IDENTICAL_TO_KEY` and in
        # `test_help_cards_untranslated_are_tracked.py::_BUDGET`, and neither
        # count may rise unnoticed -- so nothing is hidden by skipping here.
        #
        # The fault this test exists for is untouched: a body that HAS been
        # translated must still name the controls that language shows.
        if body == english:
            continue
        for name in NAMES_IN[which]:
            want = _as_prose(cat.get(name, name))
            assert want in body, (
                f"{code}: the {which} help does not name {want!r}, which is "
                f"what this language calls {name!r}")


# ---- adversary round 10 -----------------------------------------------------
def test_the_three_claims_nothing_was_reading_out_of_the_code():
    """Three of this help's claims were checked as PHRASES and not as facts.

    `test_the_help_says_the_things_a_reader_came_for` asks that the words
    "eight grey steps" appear; nothing tied the eight to the constant that
    decides it, so a chart rule loosened to six would leave the help telling
    every reader in twelve languages to print eight. Same for "the two ISO
    types … are greyed today", which stops being true the day one of them is
    built, and for the sentence that says a Printing record grades nothing.

    All three are TRUE on 2026-09-15. This is what makes them stay true, or
    say so.

    MUTATION: set `GREY_MIN_LEVELS = 6`, or flip `t5_validation_print`'s
    built flag to True, and this goes red naming which claim went stale.
    """
    from workflow.compliance_sets import INFO, effective_limits, row_verdict
    from workflow.measurement_report import GREY_MIN_LEVELS, REPORT_TYPE_MENU
    h = _helps()

    # 1. "at least eight grey steps from white to black for the grey rows"
    assert GREY_MIN_LEVELS == 8, (
        f"the grey rows now need {GREY_MIN_LEVELS} steps and the chart "
        "paragraph still says eight")
    assert "eight grey steps from white to black, spread roughly evenly" in h["chart"]

    # 2. "The two ISO types … Either can be chosen while that standard's
    #    values are loaded" (K33, B8-994; until then "greyed today")
    from workflow.measurement_report import report_type_is_built
    unbuilt = [name for tid, name, _b, _x in REPORT_TYPE_MENU
               if not report_type_is_built(tid)]
    assert unbuilt == [], (
        f"the help says the ISO types can be chosen; the menu greys {unbuilt}")
    assert "The two ISO types" in h["when"]
    assert "greyed today" not in h["when"]
    assert "while that standard's values are loaded" in h["when"]

    # 3. "Printing record grades nothing: every row it can compute reads INFO"
    lim = effective_limits("chromiq_default", {})
    for rid in ("all_de00_avg", "all_de00_max",
                "grey_balance_neutral_ramp_avg"):
        assert row_verdict(lim[rid], 1.0, graded=False) == INFO, (
            f"{rid} does not read INFO on an ungraded sheet after all")
    assert "every row it can compute reads INFO" in h["pair"]
