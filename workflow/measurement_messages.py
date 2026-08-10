"""The approved message catalogue — §M of the Unified Measurement Management
model, transcribed and used verbatim.

Knut, #130 beta.125: *"Only approved message text shall be used in any of the
windows. Verify that ALL message windows in the code for the Measurement
Management model conforms with the defined and reviewed Unified Measurement
Management model."*

He was right to ask. The first implementation wrote its own sentences —
better ones in places, but not the reviewed ones — and there was no way to
check the difference short of reading both documents side by side. So the
catalogue now lives **here**, once, and every window takes its text from it.
`tests/test_message_catalogue.py` parses §M out of
`docs/design/unified_measurement_management.md` and fails if the two disagree,
which is what makes "conforms with the model" a fact rather than a claim.

**Changing a message means changing the model.** Edit §M in the design
document and this module together, and say so on the issue — the text is
Knut's to approve, not mine.

Two conventions:

* ``{placeholders}`` are filled by the caller with real numbers. A message is
  never shown with one left in it (``tests/`` check this).
* IDs marked **PROPOSED** below are cases the reviewed model does not cover
  yet. They exist because the alternative was a window that prints something
  false — see ``M_REPLACE_UNCOUNTABLE``. They are flagged in the design
  document too, and listed on the issue for approval.
"""
from __future__ import annotations

from dataclasses import dataclass

from core.i18n import tr


@dataclass(frozen=True)
class Message:
    """One entry of §M: an ID, a headline, and the body under it.

    Where a message states a count it carries **two** bodies. Knut, #130
    2026-08-03: *"Yes, use house rule with real singular and plural. You do not
    need to ask about this."* — so "1 dated verification measurements" never
    reaches the screen, and neither does the bracketed "(s)".
    """

    id: str
    title: str
    body: str
    #: False while the reviewed model does not carry this message yet.
    approved: bool = True
    #: The body used when :attr:`count_key` is exactly 1.
    body_one: "str | None" = None
    #: Which placeholder decides singular from plural.
    count_key: str = ""

    def render(self, **kw) -> "tuple[str, str]":
        """(title, body) with the placeholders filled and nothing left over."""
        body = self.body
        if (self.body_one is not None and self.count_key
                and kw.get(self.count_key) == 1):
            body = self.body_one
        title = tr(self.title).format(**kw) if "{" in self.title else tr(self.title)
        return title, tr(body).format(**kw)


def _m(id_: str, title: str, body: str, *, approved: bool = True,
       body_one: "str | None" = None, count_key: str = "") -> Message:
    return Message(id_, title, body, approved, body_one, count_key)


# ---------------------------------------------------------------------------
# §5 — starting a measurement over an existing one
# ---------------------------------------------------------------------------
M_REPLACE_PARTIAL = _m(
    "M-REPLACE-PARTIAL",
    "This run already holds part of a measurement",
    "{c} of the chart's {a} patches have been read. Starting now without "
    "“Refine / resume existing measurement” replaces them.\n\n"
    "Tick that option to keep what you have and read only the patches that are "
    "still missing. The existing measurement is moved to the run's “old” "
    "folder either way, so nothing is lost.\n\n"
    "The measurement file is:\n{path}",
    count_key="c",
    body_one=
    "One of the chart's {a} patches has been read. Starting now without "
    "“Refine / resume existing measurement” replaces it.\n\n"
    "Tick that option to keep what you have and read only the patches that are "
    "still missing. The existing measurement is moved to the run's “old” "
    "folder either way, so nothing is lost.\n\n"
    "The measurement file is:\n{path}")

M_REPLACE_COMPLETE = _m(
    "M-REPLACE-COMPLETE",
    "This chart is fully measured",
    "All {a} patches have been read, and this run's profile was built from "
    "that measurement.\n\n"
    "Starting a new measurement replaces it. The finished measurement is moved "
    "to the run's “old” folder and nothing is deleted — but the profile in this "
    "run will no longer match the measurement beside it until you build it "
    "again.\n\n"
    "Refine / resume is left exactly as you set it before pressing Start; this "
    "window does not change your choice.\n\n"
    "The measurement file is:\n{path}")

M_TI3_MISMATCH = _m(
    "M-TI3-MISMATCH",
    "This run's measurement and its chart do not match",
    "The measurement file holds {c} readings, and the chart ({stem}.ti2) "
    "describes {a} patches. {extra}\n\n"
    "ChromIQ cannot tell which of the two is the wrong one. A measurement can "
    "be cut short by an interrupted session, and a chart can be replaced or "
    "edited outside ChromIQ — both look the same from here.\n\n"
    "What each button does:\n\n"
    "•  Measure anyway — starts a fresh measurement. The safe choice if this "
    "chart is the one you printed: the existing measurement is moved to the run's “old” folder "
    "and nothing is lost.\n\n"
    "•  Cancel — stops here so you can look at the files first. The run is at {path}. This run's "
    "“chart” folder holds the copy of the chart that was stored when it was "
    "last measured, and “Restore Used Chart” puts that copy back. There is "
    "exactly one; ChromIQ does not keep earlier versions of a chart.\n\n"
    "Resuming is not offered here, because resuming into a mismatch would "
    "write readings against patch positions that may not be the ones on your "
    "paper.",
    count_key="c",
    body_one=
    "The measurement file holds one reading, and the chart ({stem}.ti2) "
    "describes {a} patches. {extra}\n\n"
    "ChromIQ cannot tell which of the two is the wrong one. A measurement can "
    "be cut short by an interrupted session, and a chart can be replaced or "
    "edited outside ChromIQ — both look the same from here.\n\n"
    "What each button does:\n\n"
    "•  Measure anyway — starts a fresh measurement. The safe choice if this "
    "chart is the one you printed: the existing measurement is moved to the run's “old” folder "
    "and nothing is lost.\n\n"
    "•  Cancel — stops here so you can look at the files first. The run is at {path}. This run's "
    "“chart” folder holds the copy of the chart that was stored when it was "
    "last measured, and “Restore Used Chart” puts that copy back. There is "
    "exactly one; ChromIQ does not keep earlier versions of a chart.\n\n"
    "Resuming is not offered here, because resuming into a mismatch would "
    "write readings against patch positions that may not be the ones on your "
    "paper.")

#: The trailing sentence of M-TI3-MISMATCH, only when the file also disagrees
#: with itself (§3a's ``B ≠ C``).
M_TI3_MISMATCH_EXTRA = (
    "The file's own header claims {b} readings, which does not match the {c} "
    "it contains — so this file may be damaged as well as mismatched.")

# --- PROPOSED: cases the reviewed model does not cover yet ------------------
M_REPLACE_UNCOUNTABLE = _m(
    "M-REPLACE-UNCOUNTABLE",
    "This run already holds a measurement file",
    "ChromIQ cannot tell how many readings it contains — the file is there, "
    "but it holds no readable measurement data. That usually means a session "
    "ended before the first patch was read, or the file was changed outside "
    "ChromIQ.\n\n"
    "Starting now writes a new measurement in its place. The file you have is "
    "moved to the run's “old” folder and nothing is deleted, so you can always "
    "look at it afterwards.\n\n"
    "Refine / resume is not offered for this file, because there is nothing in "
    "it to resume from.\n\n"
    "The measurement file is:\n{path}")      # approved by Knut, 2026-08-04

#: **Removed 2026-08-04.** There was a proposed M-REPLACE-NO-CHART for
#: "readings, but no chart beside them to count against". Knut asked whether
#: that condition can arise at all — *"Can a chart read at all be initiated if
#: a ti2 file does not exist? I thought it could not."* Measured: Start
#: Measurement **was** offered without a `.ti2`, because the Measure tab can be
#: loaded from the `.ti1`. That was a bug, not a case needing a message, and it
#: is fixed in `TabMeasure.set_ti1_path`. With Start unavailable the condition
#: cannot occur, so the message is gone rather than unused.
# ---------------------------------------------------------------------------
# §4 — chart integrity
# ---------------------------------------------------------------------------
M_CHART_PROFILING = _m(
    "M-CHART-PROFILING",
    "This run already holds work made with the chart you are about to replace",
    "Replacing the chart in this run means what is here no longer describes "
    "it:\n\n{items}\n\n"
    "Everything is moved to the run's “old” folder and nothing is deleted — "
    "but this run would no longer hold a matching set of files.\n\n"
    "Duplicate the run and make the new chart in the copy if you want a "
    "different chart while keeping this run's work.\n\n"
    "The “old” folder is here:\n{folder}")

#: The {items} of M-CHART-PROFILING. §M: *"{items} lists only what is actually
#: present"*.
M_CHART_ITEM_MEASUREMENT = "•  a measurement of {c} patches"
M_CHART_ITEM_MEASUREMENT_ONE = "•  a measurement of one patch"
M_CHART_ITEM_PROFILE = "•  the profile built from it"
#: PROPOSED — the model's list has no entry for a measurement file with
#: nothing readable in it. Knut, 2026-08-04: *"If the {c}-value is equal to
#: zero … then why not just say the ti3 file is corrupt or empty."* Quite so.
M_CHART_ITEM_MEASUREMENT_UNCOUNTABLE = (
    "•  a measurement file that is corrupt or empty")

# --- PROPOSED: the corrupt-or-empty measurement, and what it costs ---------
M_CHART_CORRUPT = _m(
    "M-CHART-CORRUPT",
    "The measurement file in this run cannot be read",
    "It has no readable measurement data in it — no readings, or a structure "
    "ChromIQ cannot make sense of. That can happen when a session ended before "
    "the first patch was read, or when the file was changed outside "
    "ChromIQ.\n\n"
    # No Markdown here: these windows show plain text, so a **bold** span
    # would reach the screen as asterisks. The document may set the same
    # sentence in bold; the string the user reads may not.
    "It is moved to the run's “old” folder rather than deleted. Look at it "
    "there before you measure again — ChromIQ cannot tell whether it holds "
    "anything you would want to keep, and only you can judge that.")
    # Approved by Knut, 2026-08-04: "Message M-CHART-CORRUPT is accepted. move
    # into model."

#: Appended to M-CHART-CORRUPT when the run also holds a profile. Knut,
#: 2026-08-04: *"the connection between chart and profile built is broken and
#: new measurements may be only way to rebuild the continuity of information."*
M_CHART_CORRUPT_WITH_PROFILE = (
    "\n\nThe profile in this run moves to the “old” folder with it. That "
    "profile was built from a measurement, and the measurement file that "
    "should describe it can no longer be read — so nothing on disk now "
    "connects the profile to the chart it came from. ChromIQ cannot tell "
    "whether the file was always like this or became so later, and it cannot "
    "repair it. Measuring the chart again is the way to get a run whose chart, "
    "measurement and profile describe each other once more.")


M_CHART_W4 = _m(
    "M-CHART-W4",
    "This would undo the whole run, not just its chart",
    "Replacing this run's chart breaks the chain three links deep:\n\n"
    "•  the measurement of {c} patches no longer describes the chart in this "
    "run;\n"
    "•  the profile built from that measurement no longer describes anything "
    "on disk;\n"
    "•  and the {v} dated verification runs under this run were printed "
    "through that profile, so they stop describing a profile that exists.\n\n"
    "Everything is kept in the run's “old” folder and nothing is deleted — but "
    "the run would no longer hold a set of files that belong together, and its "
    "verification history could not be continued.\n\n"
    "Duplicate the run and change the chart in the copy if you want a "
    "different chart while keeping this one's work and its history.\n\n"
    "The “old” folder is here:\n{folder}",
    count_key="v",
    body_one=
    "Replacing this run's chart breaks the chain three links deep:\n\n"
    "•  the measurement of {c} patches no longer describes the chart in this "
    "run;\n"
    "•  the profile built from that measurement no longer describes anything "
    "on disk;\n"
    "•  and the one dated verification run under this run was printed "
    "through that profile, so it stops describing a profile that exists.\n\n"
    "Everything is kept in the run's “old” folder and nothing is deleted — but "
    "the run would no longer hold a set of files that belong together, and its "
    "verification history could not be continued.\n\n"
    "Duplicate the run and change the chart in the copy if you want a "
    "different chart while keeping this one's work and its history.\n\n"
    "The “old” folder is here:\n{folder}")

# Reworked after the 2026-08-10 hardware session (Sebastian): the old text
# claimed the displaced measurements would "no longer have the chart they were
# made with" — untrue since every measured date snapshots its chart — and its
# Duplicate advice contradicted its own "no measurement is touched".
M_CHART_VERIFY = _m(
    "M-CHART-VERIFY",
    "The verification measurements already made in this run used the chart "
    "you are about to replace",
    "The {v} dated verification measurements in this run were made with this "
    "verification chart. Replacing it does not make them wrong — each date "
    "keeps its own stored copy of the chart it was measured with, so every "
    "result stays readable, and “Restore Used Chart” can bring a date's "
    "chart back on screen.\n\n"
    "One thing to keep in mind: a trend across the change compares two "
    "different charts, which is not the same measurement made twice.\n\n"
    "The chart itself moves to the “old” folder inside “verifications”; no "
    "measurement is touched and nothing is deleted. If you would rather keep "
    "measuring the current chart, duplicate the run first — it lives on in "
    "the copy.",
    count_key="v",
    approved=False,
    body_one=
    "The one dated verification measurement in this run was made with this "
    "verification chart. Replacing it does not make it wrong — the date "
    "keeps its own stored copy of the chart it was measured with, so the "
    "result stays readable, and “Restore Used Chart” can bring that chart "
    "back on screen.\n\n"
    "One thing to keep in mind: a trend across the change compares two "
    "different charts, which is not the same measurement made twice.\n\n"
    "The chart itself moves to the “old” folder inside “verifications”; no "
    "measurement is touched and nothing is deleted. If you would rather keep "
    "measuring the current chart, duplicate the run first — it lives on in "
    "the copy.")

M_CHART_NOPAGES = _m(
    "M-CHART-NOPAGES",
    "This chart's printed pages cannot be recreated",
    "This chart has no layout recipe (.channels.json), so ChromIQ cannot "
    "redraw its pages. {pages}\n\n"
    "If you have the printed sheets, keep them — they are the only copy. "
    "Everything is moved to the run's “old” folder rather than deleted.")

M_CHART_NOPAGES_SOME = "The {n} page images in this run are the only ones there will be."
M_CHART_NOPAGES_ONE = "The one page image in this run is the only one there will be."
M_CHART_NOPAGES_NONE = "This run has no page images to lose."

# --- PROPOSED --------------------------------------------------------------
M_PREVIEW_PAUSED = _m(
    "M-PREVIEW-PAUSED",
    "The live preview is not being re-drawn",
    "This run already holds work made with the chart the preview would "
    "replace, so the preview is left as it is rather than re-drawn over it.\n\n"
    "Press “Generate Chart” when you want the new layout. You will be told "
    "exactly what moves to the run's “old” folder first, and nothing is "
    "deleted.\n\n"
    "This window appears once each time you switch “Auto-update preview” on. "
    "While it stays on, the same note goes to the log instead, so your layout "
    "work is not interrupted.")      # approved by Knut, 2026-08-04


# ---------------------------------------------------------------------------
# §6 — rebuilding the profile under existing verification measurements
# ---------------------------------------------------------------------------
M_PROFILE_VERIFY = _m(
    "M-PROFILE-VERIFY",
    "The verification measurements in this run were made against the profile "
    "you are about to replace",
    "This run holds {n} dated verification measurements, going back to "
    "{date}. Each was printed through the profile in this run and measured "
    "against it, so each records how that profile behaved on that day.\n\n"
    "Building a new profile here does not make those measurements wrong, and "
    "it deletes nothing — but they will no longer say which profile they "
    "belong to, and comparing them with verification measurements made "
    "afterwards means comparing against two different profiles.\n\n"
    "What each button does:\n\n"
    "•  Duplicate the run and build there (recommended) — copies this run's "
    "chart, measurement and profile into a new run and builds there. This run "
    "keeps its profile and its verification measurements exactly as they are, "
    "and the copy starts fresh. This is the clean way to try a different "
    "profile from the same readings.\n\n"
    "•  Build here anyway — replaces this run's profile. The current profile "
    "is moved to the run's “old” folder, and the {n} dated verification "
    "measurements are moved to the “old” folder inside “verifications” with "
    "it, because they describe the profile being replaced. Nothing is "
    "deleted.\n\n"
    "•  Cancel — changes nothing.{blocked}",
    count_key="n",
    body_one=
    "This run holds one dated verification measurement, made on {date}. It "
    "was printed through the profile in this run and measured against it, so "
    "it records how that profile behaved on that day.\n\n"
    "Building a new profile here does not make that measurement wrong, and it "
    "deletes nothing — but it will no longer say which profile it belongs to, "
    "and comparing it with verification measurements made afterwards means "
    "comparing against two different profiles.\n\n"
    "What each button does:\n\n"
    "•  Duplicate the run and build there (recommended) — copies this run's "
    "chart, measurement and profile into a new run and builds there. This run "
    "keeps its profile and its verification measurement exactly as they are, "
    "and the copy starts fresh. This is the clean way to try a different "
    "profile from the same readings.\n\n"
    "•  Build here anyway — replaces this run's profile. The current profile "
    "is moved to the run's “old” folder, and the dated verification "
    "measurement is moved to the “old” folder inside “verifications” with it, "
    "because it describes the profile being replaced. Nothing is deleted.\n\n"
    "•  Cancel — changes nothing.{blocked}")

# --- PROPOSED revisions: the two verification guards, §S1.2 and §S1.3 ------
# The wording Knut approved on 2026-08-04 instructed "(with colour management
# on)" — a setting ChromIQ deliberately locks OFF on every print path
# (postscript_generator, cups_printer, native_print_macos), so the approved
# text told the user to do something the app prevents. Feature A (#130,
# verification_printing_and_target.md §5 A0.1) gives the instruction a real
# control to name: the Print Chart tab's "Colour" row. The revised step is
# proposed in §M-PROPOSED and awaits approval; only that one step changed.
M_VERIFY_NO_PROFILE = _m(
    "M-VERIFY-NO-PROFILE",
    "This run has no profile to verify yet",
    "A verification checks a finished profile — but this profile run doesn't "
    "have a built profile yet.\n\n"
    "To build the profile first:\n"
    "  1. Set “Run type” to “Profiling”.\n"
    "  2. Create, print and measure the profiling chart as normal — its "
    "measurement is stored in the run folder.\n"
    "  3. Build the profile on the Build Profile tab (this makes the profile's "
    ".icc / .icm file).\n\n"
    "Once the profile exists, you can verify it:\n"
    "  4. Set “Run type” back to “Verification”.\n"
    "  5. Create a verification chart in the Create Chart tab.\n"
    "  6. Print that chart from the Print Chart tab with “Colour” set to "
    "“Through the profile” — ChromIQ applies the profile for you and "
    "keeps the printer's own colour management off.\n"
    "  7. Measure it here with “Run type” = “Verification” — the result is "
    "kept in a dated folder under this run's “verifications” folder.",
    approved=False)

M_VERIFY_NO_CHART = _m(
    "M-VERIFY-NO-CHART",
    "No verification chart for this run yet",
    "This run has a finished profile, but you haven't created its "
    "verification chart.\n\n"
    "  1. Go to the Create Chart tab and, with “Run type” = “Verification”, "
    "create the verification chart (a smaller chart is fine).\n"
    "  2. Print it from the Print Chart tab with “Colour” set to "
    "“Through the profile” — ChromIQ applies the profile for you and keeps "
    "the printer's own colour management off.\n"
    "  3. Come back here with “Run type” = “Verification” and measure it — the "
    "result is stored in a dated folder under this run's “verifications” "
    "folder.",
    approved=False)

# --- PROPOSED: building from a measurement that is not in the selected run --
# Knut, beta.132, Demo-08 step 10: *"going to run 5, Build Profile tab. The
# measurement data field does not have the file pre-selected for that run, it
# has a file with path to run 6 … Pressing Build Profile starts building
# without any warning. The icc file was then placed in the run6 folder. What
# happened here? I created a profile for run 6 via standing in run 5. A guard
# for this should be made."* His wording for what it must say is followed
# closely: where the profile will go, that it is not the selected run, and the
# two buttons.
M_BUILD_ELSEWHERE = _m(
    "M-BUILD-ELSEWHERE",
    "This measurement is not in the run you have selected",
    "The bar shows {run}, but the measurement loaded here comes from:\n"
    "{folder}\n\n"
    "A profile is always built beside the measurement it is built from, so "
    "pressing Build Profile now writes the profile into that folder — not into "
    "{run}. The run you have selected would be left exactly as it is.\n\n"
    "What each button does:\n\n"
    "•  Build anyway — builds from this measurement and puts the profile beside "
    "it. Choose this when you meant to work on that run.\n\n"
    "•  Cancel — changes nothing. To build into {run}, load that run's own "
    "measurement first: switching “Profile run” in the bar loads it for you "
    "when the run has one.")
    # Approved by Knut, 2026-08-04: "Message M-BUILD-ELSEWHERE accepted".

#: The checkbox on M-PROFILE-VERIFY (§6d) and its tooltip. In the catalogue
#: because it is text the window shows, and the window shows nothing that is
#: not here.
M_SILENCE_LABEL = "Don't show this again for this run"
M_SILENCE_TOOLTIP = (
    "Only for this one run, and only until you close ChromIQ. Every other run "
    "keeps asking, and so does this one the next time you start the program.")

M_DUPLICATE_BLOCKED = (
    "\n\nDuplicating this run is not offered right now: a duplicate carries "
    "the run's own chart along, and this run's chart files are not complete "
    "on disk (missing: {missing}).")


# --- PROPOSED: feature B (#133), the From-profile-gamut module -------------
# Both texts were agreed VERBATIM with Sebastian on #133 (2026-08-02), before
# the §M-PROPOSED governance existed — they are listed here so the formal
# record is complete, not because the wording is in doubt.
M_VERIFY_CREATE_NO_PROFILE = _m(
    "M-VERIFY-CREATE-NO-PROFILE",
    "There's no finished profile in this run yet",
    "You can go ahead and create the chart — the files will be ready and "
    "waiting for you. Printing and measuring it will have to wait for the "
    "profile, though: a verification chart is printed through your finished "
    "profile, and that's the whole point of it. Measuring one without a "
    "profile is turned off for the same reason.\n\n"
    "To get there: set Run type to Profiling, then create, print and measure "
    "the profiling chart as usual and build the profile on the Build Profile "
    "tab. Come back here afterwards and everything will be ready for you.",
    approved=False)

M_GAMUT_NO_PROFILE = _m(
    "M-GAMUT-NO-PROFILE",
    "This run needs a finished profile first",
    "This way of making a chart asks your profile which colours it believes "
    "your printer can produce, and then tests exactly those. {run} doesn't "
    "have a profile yet, so there's nothing to ask.\n\n"
    "How to get one:\n"
    "  1. Set Run type to Profiling.\n"
    "  2. Create, print and measure the profiling chart as usual.\n"
    "  3. Build the profile on the Build Profile tab.\n"
    "  4. Come back here and set Run type to Verification again.\n\n"
    "GUIDED and MANUAL can still build you a chart in the meantime, so the "
    "files are ready. Printing and measuring any verification chart waits for "
    "the profile either way.",
    approved=False)

# --- PROPOSED: the verification-saved window offers both doors -------------
# Proposed by Basti during the 2026-08-10 hardware session: the completion
# window promised "colour accuracy" but only offered the inspector — the
# accuracy analysis lives in the measurement report. Both doors, explained.
M_VERIFY_SAVED = _m(
    "M-VERIFY-SAVED",
    "Verification Measurement Saved",
    "Your verification measurement has been saved as {name}, in its own "
    "dated folder.\n\n"
    "This file checks a print against a profile — do not build a profile "
    "from it. Two ways to look at it:\n\n"
    "Measurement report — the colour-accuracy analysis: how close each "
    "printed colour landed to what the profile expected, the worst patches, "
    "your printer's reach at the cube corners, and — once you have several "
    "dated verifications — how the profile holds up over time.\n\n"
    "Measurement inspector — the physical portrait of this one print: paper "
    "white, contrast, grey cast, and how it behaves under different light.",
    approved=False)

# --- PROPOSED: the Measure tab's IMPORT module (verification runs) ---------
# A measurement made in i1Profiler enters the run through the same doors a
# native measurement uses; these are the three windows that flow can show.
M_IMPORT_MISMATCH = _m(
    "M-IMPORT-MISMATCH",
    "This file does not match the verification chart",
    "Before filing anything, ChromIQ checks that the measurement really "
    "belongs to this run's verification chart — and this one does not:\n\n"
    "{reason}\n\n"
    "Nothing has been imported and nothing has been changed.\n\n"
    "The two usual causes: the file belongs to a different chart, or the "
    "patches came back in a different order than they were sent — that can "
    "happen when the shuffled i1Profiler export was used for measuring. Use "
    "the chart's normal export (the file without “shuffled” in its name), "
    "measure again, and import that.",
    approved=False)

M_IMPORT_DATE_TAKEN = _m(
    "M-IMPORT-DATE-TAKEN",
    "This verification already holds a measurement",
    "The verification from {when} already has its measurement, and importing "
    "over it would replace a result you may still need.\n\n"
    "Nothing has been imported and nothing has been changed.\n\n"
    "To file this measurement as a new check, set the “Verification” field "
    "in the bar above to “New verification” and press Import Measurement "
    "again — it gets its own dated folder, and the earlier result stays "
    "exactly as it is.",
    approved=False)

M_IMPORT_DONE = _m(
    "M-IMPORT-DONE",
    "The measurement was imported",
    "It is filed as this run's verification from {when}, in its own dated "
    "folder:\n{folder}\n\n"
    "A copy of the chart it was measured against is stored with it, so the "
    "result stays interpretable even if the chart is replaced later.\n\n"
    "To see the colour-accuracy figures, open Tools ▸ “Measurement report” — "
    "the imported measurement is already in place there.",
    approved=True)   # Sebastian, 2026-08-10: seen live, "messages were good"

# --- PROPOSED: feature A, printing a verification chart through its profile -
# The two failure windows of the print-time conversion (#130,
# verification_printing_and_target.md §3.2 rows A10/A11 and §6 S9/S10). Both
# await review in §M-PROPOSED. They exist for the same reason
# M_REPLACE_UNCOUNTABLE did: the alternative is a window that prints a raw
# tool error, which for a beginner is indistinguishable from a broken app.
M_CM_NO_CCTIFF = _m(
    "M-CM-NO-CCTIFF",
    "ChromIQ cannot find the tool that applies your profile",
    "To print this chart through your profile, ChromIQ uses a program called "
    "cctiff, which comes with ArgyllCMS. It is not in the ArgyllCMS folder "
    "ChromIQ is set to use.\n\n"
    "You can still print this sheet raw — choose “Raw — no profile” above "
    "— but measuring it will tell you about your printer rather than "
    "about your profile.\n\n"
    "To fix it: open Preferences and check that the ArgyllCMS folder is the "
    "one you installed, then come back to this tab.",
    approved=False)

M_CM_PROFCHECK_CONVERTED = _m(
    "M-CM-PROFCHECK-CONVERTED",
    "This measurement came from a sheet printed through the profile",
    "This check pushes the chart's own numbers through the profile and "
    "compares the answer with what you measured. That only means something "
    "when the chart's numbers are what was actually sent to the printer.\n\n"
    "This sheet was printed with “Colour” = “Through the profile”, so "
    "ChromIQ converted the numbers before printing — the chart file still "
    "holds the unconverted ones. The check would run without complaint and "
    "produce confident figures, but they would not describe your profile or "
    "your printer.\n\n"
    "To judge this measurement, use the Measurement Report instead — it "
    "compares against the right reference. To use this check, print the "
    "verification chart raw and measure that sheet.\n\n"
    "What each button does:\n\n"
    "•  Run the check anyway — runs the check on these files unchanged.\n\n"
    "•  Cancel — changes nothing.",
    approved=False)

M_CM_CONVERT_FAILED = _m(
    "M-CM-CONVERT-FAILED",
    "This sheet could not be prepared",
    "ChromIQ was working out the ink amounts your profile predicts for page "
    "{n} of {total}, and that did not finish. Nothing has been printed and "
    "nothing has been changed.\n\n"
    "The most common reason is that the profile file is damaged or is not a "
    "printer profile. Rebuilding the profile on the Build Profile tab usually "
    "fixes it.\n\n"
    "Details: {reason}",
    approved=False)

# ---------------------------------------------------------------------------
#: Knut wrote this text himself (beta.150) to replace the original "No
#: Instrument Found" bullet list, and asked for the window I had added at ten
#: seconds to go: *"I prefer your more detailed message, but the original 'No
#: Instrument Found' had a few bullets to add … Then, remove the window 'Your
#: instrument is not answering' that you added after 10 seconds."* Approved by
#: authorship — the words below are his, unedited.
M_NO_INSTRUMENT = _m(
    "M-NO-INSTRUMENT",
    "No Instrument Found",
    "ChromIQ has started the measurement and asked your instrument to wake "
    "up, and it has not replied for {n} seconds. A working instrument answers "
    "almost at once, so something is in the way.\n\n"
    "This is nearly always the connection rather than anything you did. Try "
    "these in order:\n\n"
    "•  Unplug the instrument's USB cable and plug it back in.\n"
    "•  Use a different USB port, and plug straight into the computer rather "
    "than through a hub.\n"
    "•  Close anything else that may be holding the instrument — another "
    "profiling program, or a virtual machine.\n\n"
    "Nothing has been lost. The measurement you already had is put back "
    "exactly as it was if this session ends without reading anything, and you "
    "can keep waiting instead if you would rather.")


CATALOGUE = {m.id: m for m in (
    M_REPLACE_PARTIAL, M_REPLACE_COMPLETE, M_TI3_MISMATCH,
    M_REPLACE_UNCOUNTABLE,
    M_CHART_PROFILING, M_CHART_W4, M_CHART_VERIFY, M_CHART_NOPAGES,
    M_CHART_CORRUPT,
    M_PREVIEW_PAUSED, M_PROFILE_VERIFY,
    M_VERIFY_NO_PROFILE, M_VERIFY_NO_CHART, M_BUILD_ELSEWHERE,
    M_CM_NO_CCTIFF, M_CM_CONVERT_FAILED, M_CM_PROFCHECK_CONVERTED,
    M_VERIFY_CREATE_NO_PROFILE, M_GAMUT_NO_PROFILE,
    M_IMPORT_MISMATCH, M_IMPORT_DATE_TAKEN, M_IMPORT_DONE,
    M_VERIFY_SAVED,
    M_NO_INSTRUMENT,
)}

#: Paragraphs appended to another message rather than shown on their own.
#: They have an ID in the model and are quoted in the demo guide, so they are
#: listed here too — a lookup that missed them would call a real ID unknown.
FRAGMENTS = {
    "M-DUPLICATE-BLOCKED": M_DUPLICATE_BLOCKED,
}

#: Every ID the model defines, message or fragment.
ALL_IDS = tuple(sorted(set(CATALOGUE) | set(FRAGMENTS)))

#: The IDs the reviewed model has not approved yet — listed on the issue.
PROPOSED = tuple(sorted(m.id for m in CATALOGUE.values() if not m.approved))
