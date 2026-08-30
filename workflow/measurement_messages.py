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


# --- PROPOSED: a CR30 chart while Preferences selects stock chartread ------
M_CR30_STOCK_READER = _m(
    "M-CR30-STOCK-READER",
    "This chart can only be read by ChromIQ",
    "This chart was made for the CR30, and ChromIQ reads that instrument "
    "itself. Standard ArgyllCMS chartread does not know the CR30 at all — it "
    "would refuse the chart before reading a single patch, whichever "
    "instrument you have connected.\n\n"
    "Right now, Preferences → Measurement has “Chart-reading engine” set to "
    "ArgyllCMS chartread. Switch it to ChromIQ's own reader and this chart "
    "measures normally. The setting applies to every chart, and every other "
    "chart reads the same either way.\n\n"
    "Nothing is wrong with the chart, and nothing you have already measured "
    "is affected.",
    approved=False)


# --- PROPOSED: a CR30 read ended and there is no other reader to try -------
#: #159. When the engine run fails on an ordinary chart, ChromIQ restarts on
#: stock ArgyllCMS chartread and tells the user so — see M-ENGINE-FELL-BACK,
#: and the resume variant which promises "every strip you have already
#: measured has been saved and will be kept". Neither promise can be kept for
#: a CR30 chart: stock chartread does not know the name and refuses the file
#: before the first patch. So the fallback is not attempted, and this is what
#: the user is told instead. {reason} is the helper's own sentence.
M_CR30_READ_ENDED = _m(
    "M-CR30-READ-ENDED",
    "The measurement stopped",
    "Reading this chart has stopped before it finished.\n\n"
    "This chart was made for the CR30, and ChromIQ reads that instrument "
    "itself. There is no second reader to try: standard ArgyllCMS chartread "
    "does not know the CR30 and would refuse the chart before reading a "
    "single patch, so ChromIQ has not started it and has ended the "
    "measurement here rather than showing you a second failure.\n\n"
    "Nothing you have already measured is lost — every patch that was read is "
    "on disk, and you can carry on from it by ticking “Refine / resume "
    "existing measurement (-r)” before you press Start again.\n\n"
    "What went wrong: {reason}",
    approved=False)


# --- PROPOSED: calibrate the instrument before the measurement -------------
#: #159. Ruled by the instrument's owner on 2026-08-28: ChromIQ triggers the
#: calibration itself rather than asking for a button press, on both USB and
#: Bluetooth. The wording carries the one thing that actually protects the
#: user, and it is NOT "keep magnets away" -- the magnet is what makes this a
#: calibration rather than a measurement. The hazard is which FACE of the cap
#: is at the aperture: calibrating against the cap's green side is what
#: corrupted the research unit, and the error is one-sided and invisible in
#: every reading afterwards.
#:
#: It must not claim the calibration worked. The device reports the firmware's
#: nominal tile constant whenever the magnet gate engages -- white tile and
#: green face come back bit-identical, max difference 0.0 across all 31 bands
#: -- so there is nothing to check and no threshold that could be defended.
M_CR30_CALIBRATE = _m(
    "M-CR30-CALIBRATE",
    "Calibrate your CR30 before measuring",
    "Your instrument takes a white calibration before it measures a chart. It "
    "takes a couple of seconds and ChromIQ does it for you — there is no "
    "button to press on the instrument.\n\n"
    "Put the magnetic cap on the measuring end, with the WHITE TILE facing "
    "the opening. The cap is reversible and the other side is green, so it is "
    "worth a glance: white towards the instrument.\n\n"
    "Then press “Calibrate now”.\n\n"
    "ChromIQ cannot check the result for you. The instrument reports the same "
    "value whatever is under the cap, so a calibration against the green side "
    "looks exactly like a good one and would quietly shift every reading that "
    "follows. Your eyes are the only check there is.\n\n"
    "If you would rather not calibrate now, press Cancel — nothing has been "
    "changed and any measurement this run already has is untouched.",
    approved=False)


# --- PROPOSED: a magnet recalibrated the instrument mid-measurement ---------
#: #159, and it happened for real on 2026-08-30: the owner rested his paper on
#: a MacBook, whose magnets reached through the sheet. The old behaviour refused
#: the reading, told him to press the button again, and let the session carry
#: on — so every patch after it was measured against a white reference that had
#: just been overwritten with the colour of whatever the instrument was sitting
#: on. He noticed only because the numbers looked wrong.
#:
#: The refused reading is the least of it and the window says so. What matters
#: is that the instrument has already recalibrated itself, that nothing more may
#: be measured until that is put right, and that ChromIQ can put it right on the
#: spot rather than describing a procedure.
#:
#: Nothing measured BEFORE this moment is affected: the refusal happens before
#: any reading is accepted, so there is no suspect data to mark or throw away.
#: The window says that too, because "your calibration is wrong" invites a user
#: to bin work that is perfectly sound.
#:
#: ⚠ Prevention is impossible and the text does not pretend otherwise. The only
#: signal a magnet is present arrives IN the reading it has already ruined, and
#: a probe reading would itself be the calibration.
M_CR30_MAGNET = _m(
    "M-CR30-MAGNET",
    "Your CR30 has just recalibrated itself",
    "Something magnetic was against the measuring opening, and that changes "
    "what the instrument does: instead of measuring your patch, it takes a "
    "white calibration from whatever it is resting on.\n\n"
    "The usual culprit is not obvious. A laptop has magnets in its lid and "
    "body, and they reach straight through a sheet of paper; so do fridge "
    "doors, magnetic desk mats, tool trays and the instrument's own cap.\n\n"
    "EVERYTHING YOU MEASURED BEFORE THIS IS SAFE, and is already saved. "
    "ChromIQ refused this reading before using it, so nothing wrong has gone "
    "into your measurement file.\n\n"
    "But nothing more can be measured until the white calibration is taken "
    "again — until then every reading would be wrong by an amount nothing "
    "afterwards could detect.\n\n"
    "Move your chart onto something non-magnetic — a book, a pad of paper, a "
    "wooden desk — then press “Recalibrate now” and ChromIQ will take the "
    "white calibration for you and carry on from the patch you were on.\n\n"
    "What the instrument reported: {reason}",
    approved=False)



# --- PROPOSED: a reading that did not come through --------------------------
#: #159. The owner, 2026-08-30, with a screenshot of it in the log panel:
#: *"a message like this would be better in a pop up so the user is aware of it
#: instead of ruining a whole measurement session when this is unnoticed"*.
#:
#: The failure itself is recoverable and costs one button press — the patch is
#: armed again automatically. What is NOT recoverable is not noticing: the
#: instrument is waiting, the operator believes they have pressed it, and the
#: session sits there. A log line at the bottom of the window did not carry
#: that.
#:
#: It is MODELESS and closes itself as soon as the chart moves on, because the
#: remedy is to press the instrument's button — a window the user must dismiss
#: first would be standing between them and the only thing that fixes it.
#:
#: {reason} is the instrument's own words, which are technical. They stay: the
#: sentence above them says what to do, and the detail is what makes a report
#: worth reading when somebody sends one in.
M_CR30_READ_FAILED = _m(
    "M-CR30-READ-FAILED",
    "That reading did not come through",
    "The reading for patch {loc} did not arrive complete, so ChromIQ has not "
    "used it — nothing wrong has gone into your measurement file.\n\n"
    "Press the button on the instrument again, with it resting on patch "
    "{loc}. This window will close by itself when the reading comes "
    "through.\n\n"
    "What the instrument reported: {reason}",
    approved=False)


# --- PROPOSED: the dark reference, taken against air ------------------------
#: #159. The second calibration, and it asks for the OPPOSITE of the first —
#: cap OFF, opening pointing at nothing. Both windows carry the same
#: pair-of-steps picture with the current step marked, because the owner's
#: worry was that two similar windows would have someone do the same thing
#: twice; showing the pair makes the difference visible rather than remembered.
#:
#: THERE IS NO BLACK TILE. This unit has none and the vendor's own app
#: calibrates black against open air, port downward. The text says "pointing at
#: nothing" and never "put something in front of it", because the nearest dark
#: thing to hand is the cap's GREEN face — the surface that silently corrupted
#: this instrument's white reference during the research.
#:
#: The lamp-and-window clause is PRUDENCE, not a measured threshold: it follows
#: from the arithmetic of a dark reference and from the vendor's own
#: port-downward instruction. The one experiment that tried to measure it was
#: compromised and is filed as such.
M_CR30_CALIBRATE_BLACK = _m(
    "M-CR30-CALIBRATE-BLACK",
    "Now the dark reference",
    "This second step is the opposite of the first one, so it is worth a "
    "glance at the picture above.\n\n"
    "TAKE THE CAP OFF and put it aside. Hold the instrument with the opening "
    "pointing DOWNWARD into open space — about a metre above the "
    "floor, with nothing in front of it, and not aimed at a lamp or a "
    "window.\n\n"
    "There is nothing to place it on. Your CR30 has no black tile: it takes "
    "its dark reading from empty air, which is why the picture shows it "
    "pointing at nothing.\n\n"
    "Then press “Calibrate now”. Afterwards ChromIQ reads once more and shows "
    "you the number that came back, so there is a record of it.\n\n"
    "⚠ It cannot check that you pointed it at the right thing. A dark "
    "calibration DEFINES what zero means, so whatever the instrument was "
    "looking at becomes the new zero and reads as nothing a moment later — "
    "measured on a real unit: calibrated against white paper, it read back "
    "0.004 %. Getting this step right is your eyes, not ours.\n\n"
    "If you would rather not, press “Skip this step”. Your white calibration "
    "still stands and the measurement goes ahead with the dark reference the "
    "instrument already had.\n\n"
    "If you have changed your mind about measuring at all, press “Cancel the "
    "measurement”. Nothing has been measured yet and nothing on disk changes, "
    "so the only thing you lose is the white calibration you have just taken "
    "— and you can take that again in a few seconds whenever you like.",
    approved=False)


# --- PROPOSED: the instrument went away mid-measurement --------------------
#: #159, and the fault the owner hit twice on 2026-08-28: he unplugged the
#: CR30 mid-session and the app said nothing at all, then froze for three
#: minutes when he tried to stop. ChromIQ now knows the difference between an
#: instrument that has not been pressed yet — the normal state of this
#: workflow, for minutes at a time — and one that has GONE. This is what it
#: says about the second. {reason} is the underlying failure, verbatim.
#:
#: It deliberately does NOT say "press the button again": that is the advice
#: for a refused reading, and it is the wrong advice for an instrument that is
#: not there. Nothing is lost, and the message says so, because the helper
#: writes the measurement file after every single patch.
M_CR30_INSTRUMENT_GONE = _m(
    "M-CR30-INSTRUMENT-GONE",
    "The instrument stopped answering",
    "ChromIQ has lost contact with your CR30 while measuring patch {loc}.\n\n"
    "This is not something you did wrong, and nothing you have measured is "
    "lost — every patch you have already read is written to your measurement "
    "file as it is read, so all of it is safe on disk.\n\n"
    "The usual causes, in the order worth checking:\n\n"
    "•  The USB cable came out, or the instrument was switched off.\n"
    "•  Over Bluetooth, the instrument moved out of range or its battery "
    "ran down.\n"
    "•  Something else took the instrument — the phone app holds it "
    "exclusively while it is connected.\n\n"
    "Plug it back in or switch it on, then press “Carry on measuring” and "
    "ChromIQ will pick up from the patch you were on. If it is still not "
    "there, you will simply land back here.\n\n"
    "If you would rather stop, press “Stop the measurement”. Everything you "
    "have read is saved either way, and you can come back to the rest later "
    "by starting the measurement again with “Refine / resume existing "
    "measurement (-r)” ticked — ChromIQ will then offer you only the patches "
    "that are still missing.\n\n"
    "What went wrong: {reason}",
    approved=False)


# --- PROPOSED: one patch could not be read, again and again ----------------
#: #159. A reading can be refused for good reasons — the magnetic cap left on
#: (the instrument's resting state, and the likeliest first-run mistake), the
#: instrument lifted before it finished, a reading identical to the last one.
#: ChromIQ re-arms and lets the user simply press again, so a refusal is no
#: longer the end of the session. This is the message for when that has been
#: tried several times over and is still not working, so the user is not left
#: pressing a button for ever with nothing on screen changing.
M_CR30_PATCH_GAVE_UP = _m(
    "M-CR30-PATCH-GAVE-UP",
    "That patch could not be read",
    "ChromIQ has tried several times to read patch {loc} and each attempt was "
    "refused, so it has stopped asking rather than leave you pressing the "
    "button with nothing changing on screen.\n\n"
    "Everything you have already measured is safe on disk.\n\n"
    "The two things that cause this, and both are quick to check:\n\n"
    "•  The magnetic cap is still on the instrument. That is where the cap "
    "lives when the CR30 is not in use, so it is an easy one to miss — and "
    "with a magnet at the opening the instrument does not measure at all. "
    "Take the cap right off and put it aside.\n"
    "•  The instrument was lifted before it had finished. Hold it flat on the "
    "patch until it has beeped.\n\n"
    "When you have checked those, end this session with “Save and stop” and "
    "start it again with “Refine / resume existing measurement (-r)” ticked "
    "— you "
    "will be offered only the patches that are still missing.\n\n"
    "What the instrument reported: {reason}",
    approved=False)


# --- PROPOSED: how to measure, for a reader ChromIQ drives itself ---------
#: #159. Every other instrument reaches its "how to measure" window through
#: `calibration_done` (`tab_measure._on_calibration_done`), which is the ONLY
#: route to `patch_measurement_instructions_html`. Under `-x` the helper opens
#: no instrument, `cq_handle_calibrate` is inside `if (xtern == 0)`, and that
#: signal can never fire — so a CR30 user was given a spot session with no
#: on-screen instruction at all. This window replaces it, and it says the two
#: things a CR30 user needs that no other instrument's user does: take the cap
#: OFF, and nothing on screen has to be pressed. {how} is the instrument's own
#: steps from `ui.ti2_loader.patch_measurement_instructions_html`.
M_CR30_HOW_TO_MEASURE = _m(
    "M-CR30-HOW-TO-MEASURE",
    "Ready to measure, patch by patch",
    "ChromIQ reads your CR30 itself, so the measurement is driven from here "
    "rather than by ArgyllCMS.\n\n"
    "{how}\n\n"
    "The patch to read is highlighted in the preview, and the highlight moves "
    "on by itself as each reading arrives. You can click any patch in the "
    "preview to jump to it, and ChromIQ keeps every reading as it is taken, so "
    "you can stop and continue later without losing anything.",
    approved=False)


# ---------------------------------------------------------------------------
# §5 — starting a measurement over an existing one
# ---------------------------------------------------------------------------
M_REPLACE_PARTIAL = _m(
    "M-REPLACE-PARTIAL",
    "This run already holds part of a measurement",
    "{c} of the chart's {a} patches have been read. Starting now without "
    "“Refine / resume existing measurement (-r)” replaces them.\n\n"
    "Tick that option to keep what you have and read only the patches that are "
    "still missing. The existing measurement is moved to the run's “old” "
    "folder either way, so nothing is lost.\n\n"
    "The measurement file is:\n{path}",
    count_key="c",
    body_one=
    "One of the chart's {a} patches has been read. Starting now without "
    "“Refine / resume existing measurement (-r)” replaces it.\n\n"
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

# --- PROPOSED: the two Create Chart patch-set endings ----------------------
# Both existed as SILENCE. When the loaded patch set had gone from disk the app
# wrote one line to the log and built a different chart; when the user edited
# the recipe under "Edit patch recipe (override preset)" it said nothing at all
# — three assignments and a fall-through. Knut reported the resulting surprise
# against 4.1.3-beta.13; Basti approved adding both, 2026-08-25.
M_PATCHSET_MISSING = _m(
    "M-PATCHSET-MISSING",
    "The patch set you loaded is no longer there",
    "ChromIQ was going to lay out the patch set you opened earlier, but that "
    "file cannot be found any more — it may have been moved, renamed or "
    "deleted since you loaded it:\n\n"
    "{path}\n\n"
    "Nothing has been changed. The chart already in this run is untouched, "
    "and no new chart has been made.\n\n"
    "To carry on, choose one of these:\n"
    "  \u2022  Open the patch set again with the patch-grid icon at the top "
    "right of this tab, and pick the file from wherever it is now.\n"
    "  \u2022  Choose a ready-made patch set from the \u201cPresets\u201d list.\n"
    "  \u2022  Or let ChromIQ work out a fresh set of colour patches for you: "
    "tick \u201cEdit patch recipe (override preset)\u201d and click "
    "\u201cGenerate Chart\u201d.",
    approved=False)

# --- PROPOSED: the how-was-this-sheet-printed question ---------------------
# Asked once, at measure time, ONLY for a verification sheet that has no
# print record — i.e. a sheet ChromIQ did not print itself. The answer decides
# which yardstick the report may fairly use, and is stored with the dated
# measurement (pairing 3; Knut/Sebastian, 2026-08-10).
M_HOW_PRINTED = _m(
    "M-HOW-PRINTED",
    "How was this sheet printed?",
    "ChromIQ did not print this sheet itself, so it does not know whether a "
    "profile took part — and the measurement report needs to know, because "
    "the two kinds of sheet are judged differently.\n\n"
    "Raw — no profile: the chart's own numbers went straight to the printer, "
    "with every colour setting off. Measuring it checks the printer, not a "
    "profile.\n\n"
    "With colour management: the sheet was printed from another application "
    "(for example Photoshop) with this run's profile applied. Measuring it "
    "checks your whole everyday printing chain, and the report judges it "
    "relative to the sheet's own paper white — so the paper is not counted "
    "against the profile.\n\n"
    "Not sure is always safe: the report simply notes that the printing "
    "method is not recorded, and judges the colours as they are. Your answer "
    "is stored with this measurement only — it changes nothing else.",
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
    approved=True)   # Sebastian, 2026-08-10: "if you think the text ... is
                     # correct, friendly, extensive and easy to understand
                     # then use it"

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
    "•  Close anything else that may be holding the instrument: another "
    "profiling program, or a virtual machine.\n\n"
    "Nothing has been lost. The measurement you already had is put back "
    "exactly as it was if this session ends without reading anything, and you "
    "can keep waiting instead if you would rather.")

#: The same moment, but while "Faster instrument connection" is switched on.
#: Knut, 2026-08-13: his ColorMunki was found on a 2023 MacBook Pro and not on
#: a 2019 one, in every mode — turning that option off was the whole fix, and
#: he asked for the window to say so: *"Maybe the No Instrument detected
#: message could warn about this setting?"* … *"warning about this setting not
#: working on all computers, especially some older hardware, might be good.
#: And suggesting to also test connecting without that setting."* Sebastian
#: added that the window should carry the switch itself, and say where the
#: option lives for later. Knut's own text above is kept word for word; this
#: variant only adds the paragraph about the shortcut.
#: APPROVED by Knut, 2026-08-14 — *"Text approved. Make Sure to use the
#: guideline used for other messages, if relevant."* (#155). Switching to a run
#: that had never been measured showed
#: M-TI3-MISMATCH's claim — that the measurement belongs to a different chart —
#: about a file that does not exist. Stopping that false claim was the bug fix;
#: this is the window that replaces it. Approved by Knut, 2026-08-14 — *"Text
#: approved."* — together with his ruling on where such things belong: *"all
#: events shall have windows, and not hidden in a log where user will not see
#: it."*
M_OVERLAY_NO_MEASUREMENT = _m(
    "M-OVERLAY-NO-MEASUREMENT",
    "This chart has not been measured yet",
    "There is no measurement file beside this chart, so there is nothing to "
    "draw on the patches.\n\n"
    "Read the chart with your instrument and the overlay will fill in as you "
    "go, showing what you measured against the colour each patch was meant to "
    "be.")

#: PROPOSED (#156). Knut: *"the 'All Strips Read' message comes, despite that
#: the progress percentage shows 97.1% … This message must come only when all
#: patches are read."* Suppressing the finished message while patches are
#: unread is the bug fix and is in the code; announcing it in a window is new
#: wording, so it waits for approval. Until then the count goes to the log.
M_ALL_STRIPS_PATCHES_LEFT = _m(
    "M-ALL-STRIPS-PATCHES-LEFT",
    "Some patches are still unread",
    "Every strip has been read, but {n} patches still have no reading. "
    "Everything you have read so far is safe.\n\n"
    "This usually happens when some patches were read one at a time in "
    "“Patch-by-patch mode” and a few were stepped over.\n\n"
    "To finish them, start measuring again with “Patch-by-patch mode” ticked "
    "and “Refine / resume existing measurement (-r)” ticked. ChromIQ picks up where "
    "the readings stop, so you only measure the patches that are still missing "
    "rather than the whole chart again.\n\n"
    "•  Re-read Individual Strips — stay in this session and read a strip "
    "again now. Use “f” and “b” to move between strips, “n” to jump to the next "
    "unread one, and “d” when you are done.\n\n"
    "•  Close — finish here. ChromIQ asks whether to keep what you have "
    "measured so far, so nothing is decided behind your back.",
    approved=False,
    count_key="n",
    body_one=
    "Every strip has been read, but one patch still has no reading. "
    "Everything you have read so far is safe.\n\n"
    "This usually happens when some patches were read one at a time in "
    "“Patch-by-patch mode” and one was stepped over.\n\n"
    "To finish it, start measuring again with “Patch-by-patch mode” ticked "
    "and “Refine / resume existing measurement (-r)” ticked. ChromIQ picks up where "
    "the readings stop, so you only measure the patch that is still missing "
    "rather than the whole chart again.\n\n"
    "•  Re-read Individual Strips — stay in this session and read a strip "
    "again now. Use “f” and “b” to move between strips, “n” to jump to the next "
    "unread one, and “d” when you are done.\n\n"
    "•  Close — finish here. ChromIQ asks whether to keep what you have "
    "measured so far, so nothing is decided behind your back.")

#: PROPOSED (#148). Asked for by Knut, 2026-08-14: *"there should be a defined
#: and approved instrument error message in the design specification for this
#: error, is there not? I think there should be a warning message so the user
#: knows."* He is right that there is none — the fallback is announced only in
#: the measurement log, which is easy to miss mid-measurement.
#:
#: The second paragraph is the one that matters for #148. Falling back also
#: silences ChromIQ's per-patch and per-strip sounds, because stock chartread
#: beeps for itself and cannot be quietened (his own ruling, #131). That
#: suppression is correct and stays; what was missing is saying so, which left a
#: user with every reason to report the sound feature as broken.
M_ENGINE_FELL_BACK = _m(
    "M-ENGINE-FELL-BACK",
    "Measuring with ArgyllCMS instead",
    "ChromIQ's own measuring engine could not use your instrument this time, "
    "so the measurement has been started again using ArgyllCMS's chartread. "
    "Carry on measuring exactly as you would normally — nothing you have "
    "already read is lost.\n\n"
    "One thing changes while this is running: ChromIQ's measurement sounds are "
    "silent. ArgyllCMS makes its own beeps as it reads, and playing ChromIQ's "
    "sounds on top would double every one of them. The beeps you hear are "
    "coming from ArgyllCMS.\n\n"
    "Reason: {reason}", approved=False)

M_NO_INSTRUMENT_FAST = _m(
    "M-NO-INSTRUMENT-FAST",
    "No Instrument Found",
    "ChromIQ has started the measurement and asked your instrument to wake "
    "up, and it has not replied for {n} seconds. A working instrument answers "
    "almost at once, so something is in the way.\n\n"
    "This is nearly always the connection rather than anything you did. Try "
    "these in order:\n\n"
    "•  Unplug the instrument's USB cable and plug it back in.\n"
    "•  Use a different USB port, and plug straight into the computer rather "
    "than through a hub.\n"
    "•  Close anything else that may be holding the instrument: another "
    "profiling program, or a virtual machine.\n\n"
    "One more thing is worth trying, and it is the likeliest cause on an "
    "older computer. ChromIQ is using a shortcut called “Faster instrument "
    "connection”: it skips the ports an instrument is never plugged into, so "
    "the calibration prompt appears sooner. On some computers that shortcut "
    "is what stops the instrument being found at all. The button below turns "
    "it off straight away. Start the measurement again afterwards, and "
    "your instrument will very likely be found. Nothing else about your "
    "measurements changes, and you can switch it back on whenever you like "
    "in Preferences ▸ Measurement, where it is called “Faster instrument "
    "connection”.\n\n"
    "Nothing has been lost. The measurement you already had is put back "
    "exactly as it was if this session ends without reading anything, and you "
    "can keep waiting instead if you would rather.",
    approved=False)


# --- PROPOSED: the typed project name that already exists ------------------
# Knut, 2026-08-27: *"if I name project name 'test' which also exists
# before … there is no warning message that this project already exists, with
# choice to overwrite or cancel, and message to change to a different name …
# Nothing shall ever be lost and user shall always be notified if there is a
# risk of overwriting a project."*
#
# NO SPECIFICATION COVERS THIS. §4 governs what a RUN holds; nothing governs
# which PROJECT a typed name lands on. Until now nothing did: typing the name
# of a project you already have adopted it in silence, and the build went into
# its current run. The window below is new behaviour and new text, so it waits
# here for approval — see §M-PROPOSED and §S4 in the design document.
M_PROJECT_EXISTS = _m(
    "M-PROJECT-EXISTS",
    "There is already a project called \u201c{name}\u201d",
    "ChromIQ found it here:\n{folder}\n\nThat name is already taken, so building now would carry on inside that project rather than start a new one. A project keeps its work in runs, and each run holds one finished profile. This one has {runs}.{cal}\n\nYou can choose below which run the new chart goes into. {chosen} holds:\n\n{holds}\n\nNothing has been changed yet. Choose what you would like to do:\n\n•  Continue this project: the new chart is made in the run named in the box below. Anything that chart replaces is moved to that run’s “old” folder first, with today’s date on it, so you can always get it back. Choosing a new run adds a fresh, empty one and leaves everything already in the project exactly as it is.\n\n•  Replace it: everything the project holds now is moved into its own “old” folder, with today’s date, and a new, empty project of the same name is started. Nothing is deleted, and ChromIQ asks you to confirm before it does it.\n\n•  Use a different name: nothing is touched, and ChromIQ takes you back to the name box so you can type another one.\n\n•  Cancel: stops here and changes nothing.",
    approved=False)

#: The one sentence M-PROJECT-EXISTS uses to say what is already in there. It
#: is a FRAGMENT of that message rather than a message of its own, and every
#: form it can take is written out in §M-PROPOSED so a reviewer sees all of
#: them. The parts live here, in the catalogue, so the tab holds no prose —
#: and each is its own module constant, because the extractor resolves
#: ``tr(NAME)`` only for those (a dict of them would ship untranslated).
_HOLDS_NOTHING = "•  nothing yet: no chart, no measurement and no profile"
_HOLDS_CHART = "a chart"
_HOLDS_MEASUREMENT = "a measurement"
_HOLDS_PROFILE = "a built profile"
_HOLDS_VERIFICATION_ONE = "one dated verification check"
_HOLDS_VERIFICATION_MANY = "{n} dated verification checks"
#: A calibration belongs to the PROJECT, not to one run — it lives in `cal/`
#: and every run shares it. A project holding only a calibration used to read
#: as empty, so no window appeared and a build could replace it in silence.
#:
#: AND IT IS NOT A LINE OF `{holds}`. Listing it under "A new run holds:" said
#: something plainly false about a run that does not exist yet. It is a fact
#: about the PROJECT, so it goes in the sentence about the project.
_ALSO_CALIBRATION = "It also has a calibration of its own, shared by every run."
#: The ``{runs}`` fragment of M-PROJECT-EXISTS, and the ``{chosen}`` one. Both
#: live here rather than in the tab, so every sentence the window can show is
#: written down in one reviewable place.
_RUNS_ONE = "one run"
_RUNS_MANY = "{n} runs"
_RUNS_MANY_SOME_USED = "{n} runs, {f} of them with work in them"
_RUNS_MANY_ONE_USED = "{n} runs, one of them with work in it"
_CHOSEN_NEW = "A new run"


def runs_phrase(total: int, finished: int) -> str:
    """The ``{runs}`` fragment: how many runs this project has, and how many of
    them hold anything. Count-aware, per the house rule."""
    if total <= 1:
        return tr(_RUNS_ONE)
    if finished == 1 and total > 1:
        return tr(_RUNS_MANY_ONE_USED).format(n=total)
    if finished and finished < total:
        return tr(_RUNS_MANY_SOME_USED).format(n=total, f=finished)
    return tr(_RUNS_MANY).format(n=total)


def chosen_phrase(run_label: "str | None") -> str:
    """The ``{chosen}`` fragment: the run the picker is on, or a new one."""
    if not run_label:
        return tr(_CHOSEN_NEW)
    # Already translated by the caller ("Run 1"); wrapping it again would only
    # create a `tr("{run}")` key that means nothing to a translator.
    return run_label


def calibration_phrase(calibration: bool) -> str:
    """The ``{cal}`` fragment of :data:`M_PROJECT_EXISTS` — empty, or the one
    sentence saying the project has a calibration of its own."""
    return (" " + tr(_ALSO_CALIBRATION)) if calibration else ""


def holds_phrase(run: str, *, chart: bool = False, measurement: bool = False,
                 profile: bool = False, verifications: int = 0) -> str:
    """The ``{holds}`` sentence of :data:`M_PROJECT_EXISTS`.

    A LIST, NOT A SENTENCE, deliberately: joining the parts with commas and a
    final "and" would need the comma and the conjunction themselves to be
    translatable, and word order differs enough between the thirteen languages
    that the result would be wrong somewhere. One bullet per thing is right
    everywhere. Count-aware, per the house rule \u2014 "1 dated verification
    checks" never reaches a user.
    """
    items = []
    if chart:
        items.append(tr(_HOLDS_CHART))
    if measurement:
        items.append(tr(_HOLDS_MEASUREMENT))
    if profile:
        items.append(tr(_HOLDS_PROFILE))
    if verifications == 1:
        items.append(tr(_HOLDS_VERIFICATION_ONE))
    elif verifications > 1:
        items.append(tr(_HOLDS_VERIFICATION_MANY).format(n=verifications))
    if not items:
        return tr(_HOLDS_NOTHING)
    return "\n".join(f"\u2022  {i}" for i in items)


# --- PROPOSED: are you sure you want to replace the whole project? ----------
# Basti, 2026-08-27: "Keep it but require a second confirmation". Three of the
# six data-loss faults found in the first implementation were about this one
# button, and it is the only control in the app that clears a whole project from
# the Create Chart tab. So it is never one click away from a window somebody
# opened by accident.
M_PROJECT_REPLACE_CONFIRM = _m(
    "M-PROJECT-REPLACE-CONFIRM",
    "Start \u201c{name}\u201d again from empty?",
    "Everything this project holds is about to be moved into its own “old” folder, with today’s date on it:\n\n{folder}\n\nNothing is deleted. That “old” folder stays inside the project, so you can open it at any time and take anything back out of it: the charts, the measurements, the profiles, all of it.\n\nAfter that, a new and completely empty project of the same name is started in the same place, and your new chart is made in its first run.\n\nIf what you wanted was to ADD to this project rather than start it again, go back and choose “Continue this project” instead. That leaves everything where it is.",
    approved=False)

# --- PROPOSED: the Replace that could not be carried out -------------------
# "Replace it" promises that everything is moved into the project's own "old"
# folder and nothing is deleted. When the move cannot be made — a read-only
# folder, a network share that has gone away, a file another program is holding
# open — the promise is not kept, and the old code said so in one line of the
# tab's log, which nobody reads. Everything is put back before this is shown.
M_PROJECT_REPLACE_FAILED = _m(
    "M-PROJECT-REPLACE-FAILED",
    "The existing project could not be moved aside",
    "ChromIQ was going to move everything in this project into its own “old” folder before starting a fresh one of the same name, and it could not:\n\n{folder}\n\nNothing has been changed. Anything that had already been moved has been put back, and no new chart has been made.\n\nThe reason given was:\n{reason}\n\nThis usually means the folder is read-only, is on a disk or a share that is no longer available, or holds a file another program still has open. Close anything that might be using it and try again, or choose “Use a different name” and leave this project alone.",
    approved=False)


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
    M_VERIFY_SAVED, M_HOW_PRINTED,
    M_NO_INSTRUMENT, M_NO_INSTRUMENT_FAST,
    M_OVERLAY_NO_MEASUREMENT, M_ALL_STRIPS_PATCHES_LEFT,
    M_ENGINE_FELL_BACK,
    M_PATCHSET_MISSING,
    M_PROJECT_EXISTS,
    M_PROJECT_REPLACE_CONFIRM,
    M_PROJECT_REPLACE_FAILED,
    M_CR30_STOCK_READER,
    M_CR30_READ_ENDED, M_CR30_INSTRUMENT_GONE, M_CR30_PATCH_GAVE_UP,
    M_CR30_CALIBRATE, M_CR30_CALIBRATE_BLACK, M_CR30_MAGNET,
    M_CR30_HOW_TO_MEASURE, M_CR30_READ_FAILED,
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
