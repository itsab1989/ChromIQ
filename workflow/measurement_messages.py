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
    #: The headline used when :attr:`count_key` is exactly 1, for a headline
    #: that counts too ("One patch is still not read").
    title_one: "str | None" = None

    def render(self, **kw) -> "tuple[str, str]":
        """(title, body) with the placeholders filled and nothing left over."""
        body = self.body
        head = self.title
        if self.count_key and kw.get(self.count_key) == 1:
            if self.body_one is not None:
                body = self.body_one
            if self.title_one is not None:
                head = self.title_one
        title = tr(head).format(**kw) if "{" in head else tr(head)
        return title, tr(body).format(**kw)


def _m(id_: str, title: str, body: str, *, approved: bool = True,
       body_one: "str | None" = None, count_key: str = "",
       title_one: "str | None" = None) -> Message:
    return Message(id_, title, body, approved, body_one, count_key, title_one)


# --- PROPOSED: a CR30 chart while Preferences selects stock chartread ------
M_CR30_STOCK_READER = _m(
    "M-CR30-STOCK-READER",
    "This chart can only be read by ChromIQ",
    "This chart was made for the CR30, and ChromIQ reads that instrument "
    "itself. Standard ArgyllCMS chartread does not know the CR30 at all: it "
    "would refuse the chart before reading a single patch, whichever "
    "instrument you have connected.\n\n"
    "Right now, “ChromIQ chart-reading engine” in Preferences → Measurement "
    "is switched off, so ArgyllCMS chartread reads your charts. Switch it on "
    "and this chart measures normally. The setting applies to every chart, "
    "and every other chart reads the same either way.\n\n"
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
    "What ChromIQ detected: {reason}",
    approved=False)



# --- PROPOSED: a calibration the user asks for during a measurement -------
#: Knut #182 5965478577 / 5965735823, Basti 5965500670: K, or the optional
#: Calibrate button, takes a new instrument calibration between strips or
#: patches on ChromIQ's own engine. The placement window is not the
#: "Calibration required" one: readings exist, so its Cancel keeps measuring
#: (it sends cal_cancel, never Esc) and it plays no sound (Knut). The
#: instruction for the instrument itself is the existing
#: calibration_instructions_html, shown under this text.
M_CAL_REQUESTED = _m(
    "M-CAL-REQUESTED",
    "Calibrate the Instrument",
    "You asked for a new calibration. Everything you have measured so far "
    "is already saved.\n\n"
    "Place the instrument as described below, then press \u201cStart "
    "Calibration\u201d. When it is done, you carry on with the strip or "
    "patch you were on.\n\n"
    "If you change your mind, press \u201cCancel calibration\u201d: nothing "
    "is measured, and you keep measuring with the calibration the instrument "
    "already has.",
    approved=False)

#: The short "carry on" variant of Calibration complete, after a calibration
#: the user asked for. The long variants explain how to start measuring, which
#: the user is already doing.
M_CAL_REQUESTED_DONE = _m(
    "M-CAL-REQUESTED-DONE",
    "Calibration Complete",
    "The instrument has a new calibration. Carry on measuring from where you "
    "were: the reader is waiting for the same strip or patch as before.",
    approved=False)

#: A calibration the user asked for did not succeed. Reading is LOCKED until
#: one does: an i1Pro measures its white straight into its calibration and
#: checks it afterwards, so after a failure it would read on without an error
#: against a wrong reference (i1pro_imp.c:2230, 2429-2433). {reason} is the
#: instrument's own sentence, or "the calibration was cancelled" when a retry
#: was cancelled at its placement prompt.
M_CAL_REQUESTED_FAILED = _m(
    "M-CAL-REQUESTED-FAILED",
    "The Calibration Did Not Succeed",
    "The instrument could not be calibrated.\n\n"
    "Everything you measured before this is saved. Nothing more is read "
    "until a calibration succeeds, because a calibration that went wrong part "
    "of the way through can leave the instrument holding values that would "
    "make every following reading wrong, without any error to show for "
    "it.\n\n"
    "\u2022  Try again: place the instrument as asked and calibrate once "
    "more.\n\n"
    "\u2022  Save and stop: end the measurement with what you have measured. "
    "You can carry on later with \u201cRefine / resume existing measurement "
    "(-r)\u201d.\n\n"
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
    "pointing DOWNWARD into open space, about a metre above the "
    "floor, with nothing in front of it, and not aimed at a lamp or a "
    "window.\n\n"
    "There is nothing to place it on. Your CR30 has no black tile: it takes "
    "its dark reading from empty air, which is why the picture shows it "
    "pointing at nothing.\n\n"
    "Then press “Calibrate now”. Afterwards ChromIQ reads once more and shows "
    "you the number that came back, so there is a record of it.\n\n"
    "⚠ It cannot check that you pointed it at the right thing. A black "
    "calibration DEFINES what zero means, so whatever the instrument was "
    "looking at becomes the new zero and reads as nothing a moment later. "
    "Measured on a real unit: calibrated against white paper, it read back "
    "0.004 %. Getting this step right is your eyes, not ours.\n\n"
    "If you would rather not, press “Skip this step”. Your white calibration "
    "still stands and the measurement goes ahead with the dark reference the "
    "instrument already had.\n\n"
    "If you have changed your mind about measuring at all, press “Cancel the "
    "measurement”. Nothing has been measured yet and nothing on disk changes, "
    "so the only thing you lose is the white calibration you have just taken, "
    "and you can take that again in a few seconds whenever you like.",
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
    "with a magnet at the opening the instrument stops measuring and hands "
    "back its own white-tile value instead, which ChromIQ refuses. Take the "
    "cap right off and put it aside.\n"
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
    "you can stop and continue later without losing anything.\n\n"
    "You can also press the SPACE BAR, or Enter, to take the reading from "
    "here without touching the instrument. That keeps it perfectly still, "
    "and a reading taken that way is steadier than one taken by pressing the "
    "instrument's own button — pressing it moves the instrument slightly, by "
    "about ten times its own measurement noise. ChromIQ offers this once it "
    "has learned what your instrument's white tile looks like, which it asks "
    "about after calibrating.",
    approved=False)


# --- PROPOSED: teaching this unit its own white-tile value -----------------
#: #159. The magnet guard compares a reading against the instrument's stored
#: tile value, and until now that value was HARD-CODED from one unit. The only
#: other CR30 in evidence reads up to 4.69 %R lower -- 94x the tolerance -- so
#: on anyone else's instrument the guard matched nothing and its owner had no
#: protection at all: a gated reading is the stored constant, which looks like
#: an ordinary patch colour and goes straight into the profile.
#:
#: The value cannot be read from the calibration: after a white calibration the
#: instrument's stored slot is ZERO-FILLED. It comes from a capped press, which
#: is safe to ask for -- measured across three experiments on 2026-08-30, a
#: capped press does not damage the white reference.
M_CR30_LEARN_TILE = _m(
    "M-CR30-LEARN-TILE",
    "Teach ChromIQ your instrument's white tile",
    # TWO presses: the Bluetooth body. `count_key` picks `body_one` when
    # the caller renders with presses=1, so the tab passes the number and
    # writes no prose of its own.
    "This is a one-off, and it makes every measurement afterwards safer.\n\n"
    "If anything magnetic touches the measuring opening, such as a laptop "
    "lid under your paper, a magnetic desk mat, or the instrument's own "
    "cap, the CR30 stops measuring and hands back the value of its white "
    "tile instead. That value looks like a perfectly ordinary patch "
    "colour, so without knowing what it is, ChromIQ cannot tell it from "
    "a real reading.\n\n"
    "Every instrument's tile value is slightly different, so ChromIQ has "
    "to learn yours from your own device.\n\n"
    "LEAVE THE CAP ON, exactly as it is now, and press the button on the "
    "instrument TWICE. This window closes as soon as ChromIQ has both "
    "readings.\n\n"
    "Two presses are needed over Bluetooth, because the instrument does "
    "not tell ChromIQ that the opening was covered. ChromIQ accepts the "
    "value only when two readings come back identical, which real "
    "measurements never do. Over USB the instrument does say, and one "
    "press is enough there.\n\n"
    "The reading is not part of your measurement and nothing is written "
    "to your chart.\n\n"
    "This does not change your calibration. A press with the cap on "
    "reads the tile that is already the instrument's reference, so there "
    "is nothing for it to spoil.\n\n"
    "You can press “Not now” and carry on measuring as usual. Everything "
    "works exactly as before, and ChromIQ will offer this again next time.",
    approved=False,
    count_key="presses",
    body_one=
    "This is a one-off, and it makes every measurement afterwards safer.\n\n"
    "If anything magnetic touches the measuring opening, such as a laptop "
    "lid under your paper, a magnetic desk mat, or the instrument's own "
    "cap, the CR30 stops measuring and hands back the value of its white "
    "tile instead. That value looks like a perfectly ordinary patch "
    "colour, so without knowing what it is, ChromIQ cannot tell it from "
    "a real reading.\n\n"
    "Every instrument's tile value is slightly different, so ChromIQ has "
    "to learn yours from your own device.\n\n"
    "LEAVE THE CAP ON, exactly as it is now, and press the button on the "
    "instrument ONCE. This window closes as soon as ChromIQ has the "
    "reading.\n\n"
    "One press is enough over USB, because the instrument itself tells "
    "ChromIQ that the opening was covered, so a single reading proves "
    "what it is looking at. Over Bluetooth the instrument does not say, "
    "and ChromIQ has to ask for two.\n\n"
    "The reading is not part of your measurement and nothing is written "
    "to your chart.\n\n"
    "This does not change your calibration. A press with the cap on "
    "reads the tile that is already the instrument's reference, so there "
    "is nothing for it to spoil.\n\n"
    "You can press “Not now” and carry on measuring as usual. Everything "
    "works exactly as before, and ChromIQ will offer this again next time.")


# --- PROPOSED: the keyboard trigger, on an instrument not yet learned ------
#: #159. Pressing the instrument's own button shifts the reading by ~0.5 %R,
#: ten times its own repeat noise of 0.05 %R (EXP-TILE-003/004), so taking the
#: reading from the keyboard is measurably steadier. But a host-triggered reply
#: cannot report the magnet gate -- byte 58 marks it solicited and the flag at
#: offset 24 is meaningful only in an unsolicited header -- so the learned tile
#: signature is what replaces the flag. Without one there is no replacement,
#: and the trigger is refused rather than made silently unsafe.
M_CR30_TRIGGER_NOT_ARMED = _m(
    "M-CR30-TRIGGER-NOT-ARMED",
    "Measuring from the keyboard needs one quick setup step",
    "ChromIQ can take each reading for you when you press the space bar, so "
    "the instrument never moves between patches — that makes readings about "
    "ten times steadier than pressing its own button.\n\n"
    "To do that safely, ChromIQ first needs to know what your instrument's "
    "white tile looks like, so it can tell a real patch from a covered "
    "opening. That takes one press: after calibrating, leave the cap on and "
    "press the instrument's button once when ChromIQ asks.\n\n"
    "Until then, keep using the button on the instrument — every reading "
    "still works exactly as before.",
    approved=False)


# --- PROPOSED: two windows reaching for one instrument ---------------------
#: #159, 2026-09-02. Tools ▸ "Read single patches" can now drive the CR30 with
#: ChromIQ's own reader, and that reader is not a process: every "is something
#: measuring?" guard in the app answers from `ArgyllRunner.is_running`, which
#: is process state, so nothing already in the app could see it. Over Bluetooth
#: a CR30 accepts one connection and stops advertising once it is taken; over
#: USB two openers interleave their bytes. The instrument holds its last
#: reading indefinitely, so the failure is not an error, it is a plausible
#: wrong colour recorded under the other window's name.
M_INSTRUMENT_BUSY = _m(
    "M-INSTRUMENT-BUSY",
    "Your instrument is already in use",
    "ChromIQ is measuring in {where}, and your instrument can only answer one "
    "window at a time.\n\n"
    "Finish or stop that measurement, then start this one again.\n\n"
    "Nothing has been changed and nothing has been measured.",
    approved=False)


# --- PROPOSED: the dated report after a measurement could not be written ---
M_REPORT_NOT_SAVED = _m(
    "M-REPORT-NOT-SAVED",
    "The measurement report could not be created",
    "Your measurement is safe. It was read, checked and written to disk "
    "exactly as it always is, and nothing about it has changed. This is only "
    "the dated accuracy report ChromIQ normally saves beside it, and nothing "
    "in your chart, your measurement or your profile depends on that "
    "report.\n\n"
    "What did not happen: ChromIQ was not able to work out and save this "
    "measurement's report just now, so there is no new dated entry for it in "
    "the run's reports folder.\n\n"
    "You do not need to measure anything again. The report is worked out "
    "from the measurement file itself, so you can open it whenever you like "
    "with the Measurement report button, and save it from there.\n\n"
    "If you would like to look into it, the technical detail is on the line "
    "below this message and in ChromIQ's log file. The usual reasons are a "
    "run folder that has been moved, renamed or deleted since the "
    "measurement began, a disk with no room left on it, or a folder ChromIQ "
    "is not allowed to write into. If this keeps happening and you would "
    "rather not be asked about it, you can switch the automatic report off "
    "in Preferences, under Reports.",
    approved=True)


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
# PROPOSED revision (#182, Knut 5964076758 Q4 and 5964384250 Q1): a rebuild
# now archives the profile ONLY, so "Build here anyway" no longer moves the
# dated verifications, and "Each was printed through the profile" was untrue
# for raw and FROM PROFILE GAMUT sheets. "Each was checked against the profile
# this run had at the time" is true for all three, and after a "Keep them".
M_PROFILE_VERIFY = _m(
    "M-PROFILE-VERIFY",
    "This run already has verification measurements",
    "This run holds {n} dated verification measurements, going back to "
    "{date}. Each was checked against the profile this run had at the time.\n\n"
    "Building a new profile here deletes nothing, and the measurements stay "
    "correct readings of their sheets. But they would then belong to an "
    "earlier profile, and comparing them with verification measurements made "
    "afterwards would mean comparing two different profiles.\n\n"
    "What each button does:\n\n"
    "•  Duplicate the run and build there (recommended): copies this run's "
    "chart, measurement and profile into a new run and builds there. This run "
    "keeps its profile, its verification measurements and their reports "
    "exactly as they are.\n\n"
    "•  Build here anyway: replaces this run's profile. The current profile "
    "is moved to the run's “old” folder. The verification measurements, their "
    "reports and the verification chart stay where they are. When you next "
    "choose Verification, ChromIQ offers to move the measurements to the "
    "“old” folder inside “verifications”. Nothing is deleted.\n\n"
    "•  Cancel: changes nothing.{blocked}",
    approved=False,
    count_key="n",
    title_one="This run already has a verification measurement",
    body_one=
    "This run holds one dated verification measurement, made on {date}. It "
    "was checked against the profile this run had at the time.\n\n"
    "Building a new profile here deletes nothing, and the measurement stays a "
    "correct reading of its sheet. But it would then belong to an earlier "
    "profile, and comparing it with verification measurements made afterwards "
    "would mean comparing two different profiles.\n\n"
    "What each button does:\n\n"
    "•  Duplicate the run and build there (recommended): copies this run's "
    "chart, measurement and profile into a new run and builds there. This run "
    "keeps its profile, its verification measurement and its reports exactly "
    "as they are.\n\n"
    "•  Build here anyway: replaces this run's profile. The current profile "
    "is moved to the run's “old” folder. The verification measurement, its "
    "reports and the verification chart stay where they are. When you next "
    "choose Verification, ChromIQ offers to move the measurement to the "
    "“old” folder inside “verifications”. Nothing is deleted.\n\n"
    "•  Cancel: changes nothing.{blocked}")


# ---------------------------------------------------------------------------
# §6f — choosing Verification for a run whose profile was replaced
# ---------------------------------------------------------------------------
# PROPOSED (#182). The behaviour is Knut's: 5964076758, 5964384250 Q1/Q2 and
# 5965626117 (an ordinary chart opens Create Chart too; "Keep" asks again
# after a restart). The wording is ours. One window, three texts, no sound.
# {profile_when} is the current profile's header time, {date} the oldest
# measurement it names (YYYY-MM-DD).

#: A: old measurements, and a FROM PROFILE GAMUT chart from the earlier profile.
M_VERIFY_EARLIER_PROFILE = _m(
    "M-VERIFY-EARLIER-PROFILE",
    "The verification measurements in this run were made with an earlier "
    "profile",
    "This run's profile was replaced on {profile_when}. The {n} dated "
    "verification measurements going back to {date} were made with the "
    "earlier profile, and so was the FROM PROFILE GAMUT verification chart. A "
    "sheet printed from that chart would test the earlier profile, not the "
    "current one.\n\n"
    "What each button does:\n\n"
    "•  Archive them and make a new chart from the current profile "
    "(recommended): moves the {n} measurements and their reports to the "
    "“old” folder inside “verifications”. Nothing is deleted. Create Chart "
    "then opens on FROM PROFILE GAMUT with this run's last settings. When you "
    "press Generate Chart, the old chart is moved to “old” too. Then print the "
    "new chart and measure it.\n\n"
    "•  Keep them: changes nothing. You can look at them, move them or delete "
    "them yourself. ChromIQ asks again the next time you start it.",
    approved=False,
    count_key="n",
    title_one="The verification measurement in this run was made with an "
    "earlier profile",
    body_one=
    "This run's profile was replaced on {profile_when}. The dated "
    "verification measurement from {date} was made with the earlier profile, "
    "and so was the FROM PROFILE GAMUT verification chart. A sheet printed "
    "from that chart would test the earlier profile, not the current one.\n\n"
    "What each button does:\n\n"
    "•  Archive it and make a new chart from the current profile "
    "(recommended): moves the measurement and its reports to the “old” folder "
    "inside “verifications”. Nothing is deleted. Create Chart then opens on "
    "FROM PROFILE GAMUT with this run's last settings. When you press "
    "Generate Chart, the old chart is moved to “old” too. Then print the new "
    "chart and measure it.\n\n"
    "•  Keep it: changes nothing. You can look at it, move it or delete it "
    "yourself. ChromIQ asks again the next time you start it.")

#: B: old measurements, and a chart that can be used as it is.
M_VERIFY_EARLIER_PROFILE_KEEP_CHART = _m(
    "M-VERIFY-EARLIER-PROFILE-KEEP-CHART",
    "The verification measurements in this run were made with an earlier "
    "profile",
    "This run's profile was replaced on {profile_when}. The {n} dated "
    "verification measurements going back to {date} were made with the "
    "earlier profile. The verification chart itself can still be used: print "
    "it again and measure the new sheet.\n\n"
    "What each button does:\n\n"
    "•  Archive them (recommended): moves the {n} measurements and their "
    "reports to the “old” folder inside “verifications”. Nothing is deleted, "
    "and the chart stays. Create Chart then opens on this chart, so you can "
    "check that it is the one you want before you print it.\n\n"
    "•  Keep them: changes nothing. You can look at them, move them or delete "
    "them yourself. ChromIQ asks again the next time you start it.",
    approved=False,
    count_key="n",
    title_one="The verification measurement in this run was made with an "
    "earlier profile",
    body_one=
    "This run's profile was replaced on {profile_when}. The dated "
    "verification measurement from {date} was made with the earlier profile. "
    "The verification chart itself can still be used: print it again and "
    "measure the new sheet.\n\n"
    "What each button does:\n\n"
    "•  Archive it (recommended): moves the measurement and its reports to "
    "the “old” folder inside “verifications”. Nothing is deleted, and the "
    "chart stays. Create Chart then opens on this chart, so you can check "
    "that it is the one you want before you print it.\n\n"
    "•  Keep it: changes nothing. You can look at it, move it or delete it "
    "yourself. ChromIQ asks again the next time you start it.")

#: B without a chart: old measurements, and no verification chart at all (it
#: was deleted or moved by hand). Text B's "The verification chart itself can
#: still be used" and "the chart stays. Create Chart then opens on this chart"
#: would be untrue, so they are left out; nothing else differs.
M_VERIFY_EARLIER_PROFILE_NO_CHART = _m(
    "M-VERIFY-EARLIER-PROFILE-NO-CHART",
    "The verification measurements in this run were made with an earlier "
    "profile",
    "This run's profile was replaced on {profile_when}. The {n} dated "
    "verification measurements going back to {date} were made with the "
    "earlier profile.\n\n"
    "What each button does:\n\n"
    "•  Archive them (recommended): moves the {n} measurements and their "
    "reports to the “old” folder inside “verifications”. Nothing is deleted. "
    "Create Chart then opens.\n\n"
    "•  Keep them: changes nothing. You can look at them, move them or delete "
    "them yourself. ChromIQ asks again the next time you start it.",
    approved=False,
    count_key="n",
    title_one="The verification measurement in this run was made with an "
    "earlier profile",
    body_one=
    "This run's profile was replaced on {profile_when}. The dated "
    "verification measurement from {date} was made with the earlier "
    "profile.\n\n"
    "What each button does:\n\n"
    "•  Archive it (recommended): moves the measurement and its reports to "
    "the “old” folder inside “verifications”. Nothing is deleted. Create "
    "Chart then opens.\n\n"
    "•  Keep it: changes nothing. You can look at it, move it or delete it "
    "yourself. ChromIQ asks again the next time you start it.")

#: C: only the FROM PROFILE GAMUT chart is from the earlier profile.
M_VERIFY_CHART_EARLIER_PROFILE = _m(
    "M-VERIFY-CHART-EARLIER-PROFILE",
    "The verification chart in this run was made from an earlier profile",
    "This run's profile was replaced on {profile_when}, after this FROM "
    "PROFILE GAMUT chart was made from the earlier profile. A sheet printed "
    "from it would test the earlier profile, not the current one.\n\n"
    "What each button does:\n\n"
    "•  Make a new chart from the current profile (recommended): Create Chart "
    "opens on FROM PROFILE GAMUT with this run's last settings. Nothing "
    "changes until you press Generate Chart, which moves the old chart to the "
    "“old” folder inside “verifications”.\n\n"
    "•  Keep it: changes nothing. ChromIQ asks again the next time you start "
    "it.",
    approved=False)

#: The log line after A or B, in the manner of M-CAL-ARCHIVED-HERE.
M_VERIFY_EARLIER_ARCHIVED_HERE = _m(
    "M-VERIFY-EARLIER-ARCHIVED-HERE",
    "The verification measurements made with the earlier profile have moved "
    "to this folder, and nothing in them was deleted:",
    "{folder}",
    approved=False,
    count_key="n",
    title_one="The verification measurement made with the earlier profile "
    "has moved to this folder, and nothing in it was deleted:")

#: The window's buttons. The first is the default; Escape is "Keep".
M_EARLIER_ARCHIVE_NEW_CHART = \
    "Archive them and make a new chart from the current profile"
M_EARLIER_ARCHIVE_NEW_CHART_ONE = \
    "Archive it and make a new chart from the current profile"
M_EARLIER_ARCHIVE = "Archive them"
M_EARLIER_ARCHIVE_ONE = "Archive it"
M_EARLIER_NEW_CHART = "Make a new chart from the current profile"
M_EARLIER_KEEP = "Keep them"
M_EARLIER_KEEP_ONE = "Keep it"
#: The log line when not everything could be moved.
M_EARLIER_NOT_ALL_MOVED = (
    "[WARNING] Not everything made with the earlier profile could be moved: "
    "{error}. What did move is in: {folder}")

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

# --- PROPOSED: an older chart keeps its patch set, unchecked (B8-1460) -----
# A chart made before its sidecar recorded whether its patch set was given
# (beta 44 and earlier) is judged from its files when it is shown again: targen
# is asked whether the settings on screen make exactly its patches. When targen
# cannot be asked (not installed, a failure, a file it needs is gone), nothing
# can tell, so the chart keeps its own patches rather than Generate replacing
# them in silence, and this says so in Create Chart's log.
M_PATCHSET_KEPT_UNCHECKED = _m(
    "M-PATCHSET-KEPT-UNCHECKED",
    "This chart keeps its own patch set",
    "This chart was made by an earlier version of ChromIQ, which did not "
    "record where its patches came from, and ChromIQ could not check whether "
    "the settings on screen make the same patches. So that a sheet you have "
    "already printed still matches, \u201cGenerate Chart\u201d lays out this "
    "chart\u2019s own patches again.\n\n"
    "To make a new set of patches from your settings instead, tick "
    "\u201cEdit patch recipe (override preset)\u201d and change a setting of "
    "the patch recipe. The next \u201cGenerate Chart\u201d then makes a new "
    "set.",
    approved=False)

# --- PROPOSED: a verification chart that cannot carry a control strip ------
# #182, beta 22. ChromIQ now writes a control-strip declaration beside every
# verification chart it creates (`workflow/control_strip.py`), which is what
# makes the three control-strip rows of the Measurement Report computable at
# all. A chart whose patches cannot fill eight rungs of the ladder gets no
# declaration, and Knut asked for that to be said out loud rather than
# discovered later in a report: *"notify the user if a selected/loaded/created
# chart ... does not fulfil the requirements to be able to create the
# control-strip declaration ... The warning must specify what is required when
# selecting a chart for the control-strip declaration to be created, and also
# refer to the button function in Create Chart mentioned above for help in
# selecting a compatible chart."*
#
# {n} is how many of the 29 rungs the chart filled. {button} is the Create
# Chart control that lists the patch sets which can carry a strip: it is a
# placeholder and not a literal precisely because that control is being built
# alongside this message, so the name is settled in ONE place
# (`control_strip.ELIGIBILITY_CONTROL`) rather than transcribed here.
M_VERIFY_NO_CONTROL_STRIP = _m(
    "M-VERIFY-NO-CONTROL-STRIP",
    "This chart cannot carry a control strip",
    "ChromIQ has saved it as this run's verification chart and it is ready to "
    "print. What it cannot do is carry a control strip, so the three "
    "control-strip rows of the Measurement Report will read \u201cthis chart "
    "declares no control strip\u201d for every measurement made on it.\n\n"
    "A control strip is the short run of patches a print is checked on, and "
    "ChromIQ builds one out of the chart's own patches: the bare paper, the "
    "composite black, the cyan, magenta and yellow solids, the red, green and "
    "blue overprints, a 25 %, 50 % and 75 % step of each of those six colours, "
    "and a 25 %, 50 % and 75 % neutral grey. That is 29 patches in all, and a "
    "patch of your chart counts for one of them when its red, green and blue "
    "values are each within 12 units of it.\n\n"
    "This chart supplied {n} of the 29. At least 8 are needed before the "
    "average and the largest patch can be reported, and 20 before the 95th "
    "percentile can.\n\n"
    "What to do: build the verification chart from a patch set with more "
    "patches, or one spread more evenly over the colour cube. "
    "\u201c{button}\u201d on this tab lists every chart preset against the "
    "rows a Measurement Report judges, so you can choose a patch set that "
    "answers more of them.\n\n"
    "Nothing is wrong with the chart itself and nothing has been changed. "
    "Every other row of the Measurement Report is unaffected.",
    approved=True)   # Knut, 2026-09-19: "Yes, message text approved."


# --- PROPOSED: the verification pre-flight, before a single patch is read --
#: #182, Knut, 2026-09-21. Arriving on the Measure tab with a verification run
#: whose chart is built and whose measurement has not started, the reader is
#: told what the Measurement Report will be able to judge on THIS chart, while
#: changing the chart still costs nothing. His words: *"The user is thus
#: informed of both the existence of the measurement report and important info
#: for a verification chart, as well as the need for the 'From Profile Gamut'
#: feature and how to see which profiles are usable for verification with the
#: 'Which presets can be used for verification?' feature, before any
#: verification is started, so that the user can make an informed decision and
#: make changes to the chart before measurement is started."*
#:
#: **WHAT IS AND IS NOT IN THIS BODY.** The list of metrics is NOT: it is
#: built for the chart in front of the reader by
#: `ui.dialogs.preset_verification_dialog.summary_lines`, which is the same
#: function the presets window's own pane uses, because Knut asked for *"the
#: same detailed information"* and two copies of that answer is exactly the
#: fault this project keeps finding. This body is the frame around it.
#:
#: He asked for the wording to be shipped so he can review it as a working
#: example, so it goes in a window while it waits: see the log-rule amendment
#: in §M-PROPOSED.
M_VERIFY_PREFLIGHT = _m(
    "M-VERIFY-PREFLIGHT",
    "Before you measure this verification chart",
    "This run is a verification, so what you read here will be judged by the "
    "Measurement Report. That report checks the print against a set of "
    "metrics, and each metric has a limit the measurement has to stay "
    "inside.\n\n"
    # **"LEFT OUT OF THE REPORT" WAS AN ABSOLUTE AND IT IS NOT TRUE OF EVERY
    # SET** (adversary round 40b, F1 and F2, driven end to end). Whether such a
    # row is left out or shown reading N-A is decided by the limit set: on the
    # five ChromIQ sets those rows carry no limit and really are left out, on
    # the two ISO-derived ones they are shown. The sentence said one of the two
    # everywhere, and the paragraph added below it on 2026-09-22 said the other,
    # six lines apart in one popup that always shows both.
    "Not every chart can answer every metric. Which ones this chart can is "
    "listed below, worked out from its patch set before anything is printed, "
    "so you can still change the chart. A metric the chart cannot supply is "
    "not judged and nothing else is affected, so falling short does not make "
    "the chart wrong.\n\n"
    "To compare patch sets before you settle on one, open “Which presets "
    "can be used for verification” under the preset pulldown in Create "
    "Chart. It judges every preset ChromIQ ships and every one of your own "
    "against these same metrics, and its first line is the chart you have "
    "now.\n\n"
    "For the verification workflow end to end, see the help card “Check a "
    "finished profile (verification run)” behind the question mark at the "
    "top right of the window.",
    approved=True)

#: The paragraph M-VERIFY-PREFLIGHT carries only when a metric is missing that
#: nothing but FROM PROFILE GAMUT can supply. Knut asked the reader to be
#: *"instructed that some of the metrics' requirements can only be met using
#: the 'From Profile Gamut' feature on a chart in Create Chart tab"* and, in
#: the same breath, said he was *"not sure about all the required conditions
#: for 'From Profile Gamut' feature to be visible"*. They were measured for
#: B8-613 and this says what they are.
#:
#: **ITS FIRST PARAGRAPH IS A REVISION KNUT ACCEPTED (B8-1374, #182
#: 5848287278: "Accepted.").** It said the metrics "are judged against a
#: colorimetric reference, and ChromIQ writes one only beside a chart built
#: with FROM PROFILE GAMUT", which K49 and K51 made untrue: the two solid rows
#: are compared with the profile's prediction, and a raw print answers them.
#: What really withholds them from a verification is that it is printed
#: through its profile, which converts the solid patches. His words, verbatim;
#: the second paragraph is the one he approved in 5816565326, unchanged.
M_VERIFY_PREFLIGHT_GAMUT = (
    "Some of the metrics listed above can be answered by a verification in "
    "only one way: its solid patches must be printed as they are, and a chart "
    "printed through its profile converts them. A chart built with FROM "
    "PROFILE GAMUT in the Create Chart tab prints them as they are.\n\n"
    "That button sits beside GUIDED and MANUAL whenever Run type is "
    "Verification. Before it can choose any colours the run must already hold "
    "a built profile, and it lays the sheet out again from scratch.")


# --- APPROVED: why a chart cannot answer the two solid rows (challenge 8,
# C5; B8-1373; Knut, #182 5848287278: "Approved.") -------------------------
#: The reason line under "Maximum ΔE00, solid colours" and "Maximum ΔH*ab,
#: cyan, magenta and yellow solids", in the presets window and in the Measure
#: tab's pre-flight (M-VERIFY-PREFLIGHT's metric list). Only the BODY is
#: shown; the title is its name in the review queue.
#:
#: It said "This chart carries no colorimetric reference.", which K49 and K51
#: made untrue as a reason: those two rows are compared with the profile's
#: prediction, not with a reference file, and a sheet printed raw is judged
#: on them (Knut, #182 5846167083, K50-1). What really withholds them is how
#: a verification is printed: through its profile, which converts the solid
#: patches. Neither window can know yet how the sheet will be printed, so
#: the line says both cases.
M_VERIFY_SOLIDS_REASON = _m(
    "M-VERIFY-SOLIDS-REASON",
    "Why this chart cannot answer the solid colour metrics",
    "Printed through its profile, as a verification normally is, the chart's "
    "solid patches become other ink amounts, not the printer's own solids, so "
    "the report cannot judge them. Printed without a profile, its solids are "
    "judged against the profile and its other metrics are shown for "
    "information only.",
    # Knut, #182 5848287278, 2026-09-26: "Regarding 'For your approval
    # (M-VERIFY-SOLIDS-REASON)' Answer: Approved."
    approved=True)


#: The one line the PRE-FLIGHT carries, where the full paragraph below is what
#: the presets window shows. Knut asked for both windows to say this; he also
#: asked, in the same specification, that this popup not *"become too long"*,
#: and the two requirements collided.
#:
#: **MEASURED ON SCREEN** by adversary round 40b, the real popup, before and
#: after the paragraph was appended: English frame 826 to 986 px, German 826 to
#: 1002, with `minimumHeight()` 798 to 974. A `QMessageBox` has no scroll area
#: and that height is a hard minimum, so on a 13-inch MacBook Air (usable about
#: 918 px) the OK button and Knut's "do not show this again" tick fall off the
#: bottom of the screen. This line is about a fifth of the paragraph's length
#: and leaves the popup inside that budget, and it points at the window that
#: carries the rest, which this popup already sends the reader to by name.
M_VERIFY_PREFLIGHT_UNCHECKED = (
    "A metric this chart cannot answer is never judged and can never make the "
    "report fail. Whether it is shown at all is decided by the limit set, and "
    "the window named above says how to change that.")


# --- PROPOSED: a metric the chart cannot answer, and the lever for it ------
# Knut, 2026-09-22, on #182: a report that judges metrics the chart cannot
# calculate carries a warning for each of them, and he asked that the reader
# be told, before printing, that those metrics can be turned off in Report
# limits by setting the threshold to "-", so that what is handed to a customer
# holds only the metrics that were actually checked.
#
# **THIS IS NOT REPORT TEXT, WHICH IS WHY IT MAY NAME A CONTROL.** His other
# ruling of the same day is that no report text explains how to use ChromIQ.
# This paragraph is shown in the pre-flight popup and in the "Which presets can
# be used for verification" window, both of which exist to help somebody decide
# what to print, so naming the lever is the whole point of them.
#
# **AND THE TWO OUTCOMES ARE NOT THE SAME, WHICH THE FIRST DRAFT PROMISED THEY
# WERE.** Measured, on the real `row_verdict`, both states of one row:
#
#   chart cannot answer it,  threshold 1.5  ->  N-A  (row drawn, with a note)
#   chart cannot answer it,  threshold "-"  ->  no word at all, row not drawn
#   chart CAN answer it,     threshold "-"  ->  INFO (row drawn, not graded)
#
# So "-" removes the row only in the case Knut is asking about, and shows it
# ungraded in the other. A sentence promising it disappears either way would be
# false on half the rows the reader might try it on, so the text says both.
# **THE FIRST VERSION OF THIS WAS FALSE IN MOST STATES**, and adversary round
# 40b measured every one of them by driving the app. It said a metric the chart
# cannot supply "is listed in the report all the same, reading N-A with a
# numbered note", and that the threshold is set to "-". Four separate things
# were wrong:
#
#  * **the set decides, not ChromIQ.** Only the two ISO-derived sets put a real
#    limit on those rows; the five ChromIQ sets put none, so the rows are left
#    out and the sentence described 2 of 7 selectable sets. On the other five
#    the remedy was also a no-op, because the threshold is already "no limit".
#  * **the report TYPE decides too.** Measured on one run, four buildable
#    types: the numbered note exists on T2 only (T4 is ungraded, so
#    `_note_the_absences` returns early), T3 does not carry those rows at all,
#    and T1 carries no metric rows. The pre-flight cannot know the type, so an
#    unconditional sentence about notes was wrong on three of the four.
#  * **you cannot type "-" into the box.** One row, both states: typing it
#    leaves `hasAcceptableInput()` False and the cell silently reverts on
#    focus-out. The gesture is setting the spin box to ZERO, which it displays
#    as "–" via `setSpecialValueText`. The message also spelled that mark as a
#    hyphen while the app writes an en dash everywhere.
#  * **the lever is often not there.** The two ISO columns are read-only in
#    every state. (Until K31 a locked run's column was read-only too; the
#    lock is gone and the lever is now the REPORT's own column.)
#
# So this says what is invariant, names what decides the rest, and qualifies
# the instruction rather than promising it works everywhere.
M_VERIFY_UNCHECKED_METRICS = _m(
    "M-VERIFY-UNCHECKED-METRICS",
    "What the report does with a metric this chart cannot answer",
    "It is never judged, and it can never make the report fail.\n\n"
    "Whether it appears at all is decided by the limit set the report is "
    "judged against. Where the set puts a real limit on the metric, the "
    "metric is shown reading N-A, and on a report type that carries notes it "
    "also carries one saying what it needed. Where the set puts no limit on "
    "it, the metric is left out; that is what ChromIQ's own sets do with the "
    "metrics above.\n\n"
    "To leave a metric out yourself, set its threshold to zero in the "
    "report's own limits, the first column of Edit limits… in the "
    "Measurement Report window. The box shows zero as “–”.",
    approved=False)


# --- PROPOSED: one report, sheets with different numbers of patches --------
# Knut, 2026-09-22, on #182. Not an error and it must not read as one: a
# report is allowed to hold measurements of charts with different patch
# counts, and the only honest thing to say is that a metric worked out over
# more patches is not worked out over quite the same population as the same
# metric over fewer, so small differences between the columns, and steps in
# the trend graphs, can come from the charts rather than from the printer.
# **IT SAYS "READINGS", BECAUSE READINGS ARE WHAT IS COUNTED.** The first
# version was headed "taken from charts with different numbers of patches", and
# `report_scope` counts `r["patches"]`, which is `data.n_patches`: the number of
# readings in the `.ti3`, not the chart's patch count. Adversary round 40b drove
# the difference on one variable, twelve measurements of ONE chart: with the
# twelfth read in full the note stayed silent, and with the same read ended
# early at 168 of 210 patches the report printed "taken from charts with
# different numbers of patches (210, 167)" directly under a Report Scope block
# naming one chart and twelve runs. Ending a measurement early is a supported
# ending (`save_partial_and_quit`), so that is not an exotic state.
#
# Saying "readings" makes the sentence true in both cases, and the second
# paragraph names both causes, so the note stays useful exactly where it was
# lying: a metric over 167 readings really is not over the same colours as the
# same metric over 210.
M_REPORT_PATCH_COUNTS_DIFFER = _m(
    "M-REPORT-PATCH-COUNTS-DIFFER",
    "These measurements do not all hold the same number of readings",
    "The sheets in this report do not all carry the same number of measured "
    "patches ({counts}). Every metric is worked out over the patches a sheet "
    "actually holds, so a figure taken over more of them is not measured over "
    "quite the same set of colours as the same figure taken over fewer, and "
    "the two can differ a little for that reason alone. It shows in the trend "
    "graphs as well as in the table.\n\n"
    "That can be because the charts differ, or because a measurement was ended "
    "before its last strip. Either way it is not a fault and nothing here is "
    "wrong, but a small change between such sheets is not necessarily a "
    "change in the printer.",
    approved=True)


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

# --- PROPOSED: the import has to take the device values from the chart -----
# A measurement made in i1Profiler's measure tool, on a chart i1Profiler did
# not generate, carries the colour of every patch and no device values at all:
# the tool has no colour space to express them in and will not let you ask for
# them. ChromIQ pairs such a file with the chart by the patch NAME each reading
# carries and takes the device values from the chart, which is what chartread
# does. What it cannot then do is check that this is a measurement of THIS
# chart, because that check compares device values, and the file has none. So
# the person is told exactly that, and decides.
M_IMPORT_DEVICE_FROM_CHART = _m(
    "M-IMPORT-DEVICE-FROM-CHART",
    "Only you can confirm this is a measurement of this chart",
    "This file holds the colour of every patch and no record of the ink that "
    "made it. i1Profiler writes it that way when it measures a chart it did "
    "not generate itself: there is no colour space for it to put device "
    "values in, so it puts none.\n\n"
    "ChromIQ can still file it. All {count} readings name a patch of "
    "{chart}, and the chart knows what was printed at each of those names, so "
    "the chart supplies the device values, exactly as it does for a "
    "measurement made here.\n\n"
    "What ChromIQ cannot do is check the file against the chart. That check "
    "compares the device values in the measurement with the chart's, and this "
    "file has none. The names all belong to this chart, which is as far as "
    "names can go: another chart laid out the same way carries the same "
    "names.\n\n"
    "Import it only if this is the measurement of the sheet printed from "
    "{chart}. Cancel changes nothing.",
    body_one=(
        "This file holds the colour of its patch and no record of the ink "
        "that made it. i1Profiler writes it that way when it measures a chart "
        "it did not generate itself: there is no colour space for it to put "
        "device values in, so it puts none.\n\n"
        "ChromIQ can still file it. Its one reading names a patch of "
        "{chart}, and the chart knows what was printed at that name, so the "
        "chart supplies the device values, exactly as it does for a "
        "measurement made here.\n\n"
        "What ChromIQ cannot do is check the file against the chart. That "
        "check compares the device values in the measurement with the "
        "chart's, and this file has none. The name belongs to this chart, "
        "which is as far as a name can go: another chart laid out the same "
        "way carries the same names.\n\n"
        "Import it only if this is the measurement of the sheet "
        "printed from {chart}. Cancel changes nothing."),
    count_key="count",
    approved=False)

M_IMPORT_DONE_PROFILING = _m(
    "M-IMPORT-DONE-PROFILING",
    "The measurement was imported",
    "It is filed as the measurement of {run}, in:\n{folder}\n\n"
    "A copy of the chart it was measured against is stored with the run, so "
    "the result stays interpretable even if the chart is replaced later.\n\n"
    "You can build a profile from it now on the Build ICC profile tab, or "
    "open Tools \u25b8 \u201cMeasurement report\u201d first to see the "
    "colour-accuracy figures.",
    approved=False)

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
#: B7 / C1 (#182 5958466861, behaviour approved by Sebastian in 5959070209):
#: the printer calibration a chart was printed with. PROPOSED wording.
M_CM_K_CHART_THROUGH = _m(
    "M-CM-K-CHART-THROUGH",
    "This chart cannot be printed through the profile",
    "This verification chart was made with the printer calibration applied "
    "(-K), so its pages already hold calibrated ink amounts instead of the "
    "colours the chart describes. Printing it through the profile would read "
    "those ink amounts as colours and calibrate them a second time, and the "
    "measurement would not describe your profile. Nothing has been printed."
    "\n\n"
    "To check the profile: make the verification chart again with the "
    "printer calibration set to None or to embed only (-I), and print it "
    "through the profile. When the run's own chart was printed with the "
    "calibration applied, ChromIQ applies that calibration itself as it "
    "prints through the profile.\n\n"
    "To check the printer instead: choose “Raw” in the Colour row above and "
    "print this chart as it is.",
    approved=False)

M_CM_RAW_UNCALIBRATED = _m(
    "M-CM-RAW-UNCALIBRATED",
    "This sheet will print without the printer calibration",
    "This run's chart was printed with the printer calibration applied (-K), "
    "so its profile describes your printer with that calibration in front of "
    "it. Printed raw, this verification chart goes to the printer without the "
    "calibration, and its measurement describes a printer the profile was not "
    "made for.\n\n"
    "To check the profile, choose “Through the profile” in the Colour row "
    "above: ChromIQ then applies the profile and the run's calibration. To "
    "check the printer exactly as the run's chart was printed, make the "
    "verification chart again with the calibration applied (-K) and print "
    "that raw.",
    approved=False)

M_CAL_APPLIED_TWICE = _m(
    "M-CAL-APPLIED-TWICE",
    "The calibration would be applied twice",
    "This profile was built from a chart that an earlier version of "
    "ChromIQ's layout engine made with the printer calibration applied (-K). "
    "That version also wrote the calibrated values into the chart file, so "
    "the profile already describes your printer without the calibration. "
    "Applying the calibration to it now would apply it a second time, and "
    "prints made with the result would be wrong. Nothing has been changed "
    "yet.\n\n"
    "Use this profile as it is, without the calibration. To work with the "
    "calibration, build the chart again with this version of ChromIQ, then "
    "print and measure it again.",
    approved=False)

M_CAL_CALIBRATED_TWICE = _m(
    "M-CAL-CALIBRATED-TWICE",
    "This calibrated profile applies the calibration twice",
    "This calibrated profile was made from a profile whose chart an earlier "
    "version of ChromIQ's layout engine built with the printer calibration "
    "applied (-K). That profile already describes your printer without the "
    "calibration, so this file applies the calibration a second time, and "
    "checking it measures that mistake rather than your profile.\n\n"
    "Check the run's own profile instead, without the calibration. To work "
    "with the calibration, build the chart again with this version of "
    "ChromIQ, then print and measure it again.",
    approved=False)


# --- PROPOSED: a measurement's damaged calibration table, put back ---------
#: Beta 7, the CMYK/CR30 forum report (2026-10-03). ChromIQ's measuring engine
#: wrote the printer calibration into every -K/-I measurement as nan, so
#: colprof refused the file. Basti ruled that existing measurements are
#: repaired in place from their chart, the original kept in old/ and the
#: yellow confirmed marks kept (workflow/cal_repair.py). Shown once per
#: action, however many files it repaired. {folder} is the old/<date-time>
#: folder, {files} one CAL_REPAIRED_LINE per file.
M_CAL_TABLE_REPAIRED = _m(
    "M-CAL-TABLE-REPAIRED",
    "ChromIQ repaired these measurement files",
    "These measurements carry a copy of the printer calibration their chart "
    "was made with. An earlier version of ChromIQ wrote that copy damaged, so "
    "ArgyllCMS could not read them:\n\n{files}\n\n"
    "ChromIQ has put the calibration back from the chart, which holds it "
    "intact. The readings themselves were not changed, and patches you "
    "confirmed stay confirmed. You do not need to measure again.",
    body_one=(
        "The measurement {file} carries a copy of the printer calibration its "
        "chart was made with. An earlier version of ChromIQ wrote that copy "
        "damaged, so ArgyllCMS could not read the file.\n\n"
        "ChromIQ has put the calibration back from the chart, which holds it "
        "intact. The readings themselves were not changed, and patches you "
        "confirmed stay confirmed. You do not need to measure again.\n\n"
        "The file as it was is kept in:\n{folder}"),
    count_key="count",
    title_one="ChromIQ repaired a measurement file",
    approved=False)

#: One line of M-CAL-TABLE-REPAIRED's {files}.
CAL_REPAIRED_LINE = "•  {file}  (as it was: {folder})"


def cal_table_repaired_texts(repairs) -> "tuple[str, str]":
    """(title, body) of M-CAL-TABLE-REPAIRED for one or more
    :class:`workflow.cal_repair.CalRepair`. Paths are shown from the project
    folder down when the file is in a project, else in full."""
    def shown(p) -> str:
        from pathlib import Path as _P
        p = _P(p)
        for d in p.parents:
            if (d / "project.json").is_file():
                return str(p.relative_to(d.parent))
        return str(p)

    reps = list(repairs)
    if len(reps) == 1:
        r = reps[0]
        return M_CAL_TABLE_REPAIRED.render(
            count=1, file=shown(r.ti3), folder=shown(r.archive.parent),
            files="")
    files = "\n".join(
        tr(CAL_REPAIRED_LINE).format(file=shown(r.ti3),
                                     folder=shown(r.archive.parent))
        for r in reps)
    return M_CAL_TABLE_REPAIRED.render(count=len(reps), files=files,
                                       file="", folder="")


#: The build-failed window, when what colprof could not read is that table
#: and no chart could be proved to be the one measured, so nothing was
#: repaired. It replaces "Make sure the file isn't open in another app,
#: hasn't been edited by hand" for this one cause: ChromIQ wrote the file.
M_CAL_TABLE_DAMAGED = _m(
    "M-CAL-TABLE-DAMAGED",
    "The measurement's copy of the calibration is damaged",
    "ArgyllCMS could not read {file}: the copy of the printer calibration "
    "inside it is damaged. An earlier version of ChromIQ's measuring engine "
    "wrote it that way. Nothing you did caused it, and the readings in the "
    "file are fine.\n\n"
    "ChromIQ puts that copy back from the chart before it builds, but it could "
    "not find the chart this measurement was made with: a .ti2 with the same "
    "patches and the same device values, and a calibration table of the same "
    "size, in the run folder. Put that chart back "
    "into the run folder and build again, or print and measure the chart "
    "again with this version of ChromIQ.",
    approved=False)


# --- PROPOSED: a bound patch set the printer calibration does not fit ------
#: Beta 7, the CMYK/CR30 forum report (2026-10-03). A preset or loaded patch
#: set carries its own inks (every built-in is RGB), and a calibration for
#: other inks cannot be applied to or embedded in it. The older refusal told
#: the person to "set Device Type", which the preset's locked targen panel
#: does not allow; the way there is the override box. Asked before anything
#: is built, so nothing has moved. {source} is the preset's name or the
#: patch-set file's, {chart_space} and {cal_space} colour_space_name()s.
M_PATCHSET_CAL_INKS = _m(
    "M-PATCHSET-CAL-INKS",
    "This patch set does not fit the printer calibration",
    "The patch set of “{source}” is {chart_space}, but the printer "
    "calibration was made for a {cal_space} chart. A calibration can only be "
    "applied to (-K) or embedded in (-I) a chart with the same inks, so the "
    "chart was not built.\n\n"
    "To build a {cal_space} chart with this layout, tick “Edit patch recipe "
    "(override preset)”, set “Device Type” to {cal_space} and press Generate "
    "Chart. ChromIQ then makes a new {cal_space} patch set with targen.\n\n"
    "To use the {chart_space} patch set of “{source}” as it is, set the "
    "printer calibration to “None”.",
    approved=False)


# --- PROPOSED: a view that reads RGB measurements only -------------------------
#: Beta 7, the CMYK/CR30 forum report (2026-10-03). CMYK and multi-ink charts
#: are measured, imported and profiled, but the Measurement Report, its
#: patch-identity check and the measurement details read RGB device values
#: only. They said "No device RGB columns", "carries no device values" or
#: nothing at all; this is the one line every such view shows instead.
#: {space} is colour_space_name() of the measurement's COLOR_REP.
M_VIEW_RGB_ONLY = _m(
    "M-VIEW-RGB-ONLY",
    "This view supports RGB charts only for now",
    "This is a {space} measurement. ChromIQ measures, imports and builds "
    "profiles from {space} and other multi-ink charts, but this view supports "
    "RGB charts only for now. Nothing is wrong with the measurement.",
    approved=False)


# --- PROPOSED: the colour range on a flagged patch's card (#182 k10) --------
#: The rule was approved (Knut 5961180259, Sebastian, on 5961078418): a red
#: patch may only turn yellow from confirmed patches of its own colour range,
#: once that range has three of them. Beta 9 (Knut 5979886227, awaiting
#: confirmation): similar patches read in other strips confirm each other too,
#: and the ΔE 6 spacing between the three is gone. The post
#: gave one line of card text ("Blue: 2 of 3 spaced confirmations so far");
#: the lines below are that line split so the range name stands on its own
#: (a nominative line, which every language can say), plus the sentences the
#: yellow and red cards need. No sentence counts anything but the fixed 3, so
#: no language needs plural forms. The card (ui/tiff_preview.py) breaks its
#: lines by hand, which is why each is a line of its own.
_CARD_RANGE = "Colour range: {range}"
_CARD_RANGE_SO_FAR = "{k} of 3 confirmations so far"
_CARD_RANGE_SAME = "Confirmed: {locs}"
_CARD_RANGE_LEARNED_1 = "Its range has learned: three patches"
_CARD_RANGE_LEARNED_2 = "of it were confirmed."
_CARD_RANGE_LEARNED_3 = "This one is off in the same way,"
_CARD_RANGE_LEARNED_4 = "so it is taken as real too."
_CARD_RANGE_RED_LEARNED_1 = "This range has learned, but this"
_CARD_RANGE_RED_LEARNED_2 = "one is off in a different way."
_CARD_RANGE_CONFIRMED_LEARNED = "This range has learned."
#: Beta 10 (Knut, #182 5982206917, answer 1 of 5982058944): a red patch of a
#: LEARNED range says WHICH test ruled it out against the confirmed patches of
#: its range, with the numbers, instead of "one is off in a different way"
#: (kept only for a card that has no numbers to show). The first reason
#: finishes _CARD_RANGE_RED_LEARNED_1's sentence ("...but this one's error is
#: smaller:"); a further reason, when one test does not rule out every
#: confirmed patch, starts a sentence of its own. {own} and {ref} are ΔE
#: values or _CARD_DE_SPAN; "some of" is said when that test ruled out only
#: some of the confirmed patches (another reason on the card rules out the
#: rest). Knut kept the size test, waived when the reading lands within
#: ΔE 15 of a confirmed patch's reading (5982600086, approving 5982339631),
#: so the "smaller" reason goes on to say that it did not land there: {own}
#: in _CARD_MISFIT_LANDED_DE is how far its reading is from theirs, {tol}
#: workflow.patch_flags.LANDING_DE.
_CARD_MISFIT_SMALLER = "one's error is smaller: ΔE {own} here,"
_CARD_MISFIT_SMALLER_NEXT = "Its error is also smaller: ΔE {own} here,"
_CARD_MISFIT_SMALLER_LIMIT = "(at most ΔE {tol} smaller allowed),"
_CARD_MISFIT_LANDED = "and its reading did not land near theirs"
_CARD_MISFIT_LANDED_DE = "(ΔE {own} away, at most ΔE {tol})."
_CARD_MISFIT_SIDEWAYS = "one's error points another way:"
_CARD_MISFIT_SIDEWAYS_NEXT = "Its error also points another way:"
_CARD_MISFIT_SIDEWAYS_DE = "ΔE {own} sideways"
_CARD_MISFIT_SIDEWAYS_LIMIT = "(at most ΔE {tol} allowed)."
_CARD_MISFIT_STANDOUT = "one stands out from its strip more:"
_CARD_MISFIT_STANDOUT_NEXT = "It also stands out from its strip more:"
_CARD_MISFIT_STANDOUT_DE = "ΔE {own} above its strip,"
_CARD_MISFIT_STANDOUT_LIMIT = "(at most ΔE {tol} more allowed)."
_CARD_MISFIT_REFS = "ΔE {ref} on its confirmed patches"
_CARD_MISFIT_REFS_SOME = "ΔE {ref} on some of its confirmed patches"
_CARD_DE_SPAN = "{lo} to {hi}"
#: The same ruling, on a yellow card: a patch judged like a confirmed patch
#: only because the size test was waived says why (between the range's
#: "...of it were confirmed." and "This one is off in the same way,").
_CARD_RANGE_LANDED_1 = "Its reading landed where its"
_CARD_RANGE_LANDED_2 = "confirmed patches' readings did."
#: A VERIFICATION judged against the run profile's prediction (Knut, #203
#: 5982702169; proposed in 5982715730, these ten lines APPROVED by Knut in
#: 5982788316, the message as a whole stays proposed): a large difference there does not
#: mean a colour the printer cannot reach, it means the profile is inaccurate
#: there (or the printer has changed), and a verification never goes into the
#: profile. These replace the profiling card's "this printer and paper cannot
#: reach" and "keep it for the profile" lines on such a card; the profiling
#: cards are unchanged.
_CARD_VERIFY_RED_1 = "Far from what the profile predicts."
_CARD_VERIFY_RED_2 = "Either a misread, or a place where"
_CARD_VERIFY_RED_3 = "the profile is inaccurate."
_CARD_VERIFY_SAME_1 = "it is real, and counts against"
_CARD_VERIFY_SAME_2 = "the profile's accuracy."
_CARD_VERIFY_YELLOW_1 = "A real difference, not a misread:"
_CARD_VERIFY_YELLOW_2 = "the profile does not predict this"
_CARD_VERIFY_YELLOW_3 = "colour well here (or the printer has"
_CARD_VERIFY_YELLOW_4 = "changed since the profile was made)."
_CARD_VERIFY_LEARNED = "The profile is off in the same way here,"
#: A VERIFICATION whose profile was made after the sheet was printed, so the
#: card compares with the chart's own estimate instead of the profile's
#: prediction (workflow/verify_expected.py, ``profile_newer``). The first six
#: lines are Knut's sentence, APPROVED in #182 5983480953, broken for the
#: card; they replace "Either a misread, or a colour / this printer and paper
#: cannot reach." and "Read it again to find out." on a red card. The last
#: four are ours and wait: two after "Same value after a re-read:" instead of
#: "it is real, keep it for the profile.", two on a yellow card instead of
#: "A real difference this printer and / paper cannot reach, not a
#: misread." and "Keep it for the profile.".
_CARD_LATER_PROFILE_1 = "Far from the chart's estimate."
_CARD_LATER_PROFILE_2 = "The profile was made after this"
_CARD_LATER_PROFILE_3 = "sheet was printed, so its"
_CARD_LATER_PROFILE_4 = "prediction is not used."
_CARD_LATER_PROFILE_5 = "Either a misread, or a real difference:"
_CARD_LATER_PROFILE_6 = "read it again to find out."
_CARD_LATER_PROFILE_SAME_1 = "it is real: the print differs from"
_CARD_LATER_PROFILE_SAME_2 = "the chart's estimate here."
_CARD_LATER_PROFILE_YELLOW_1 = "A real difference from the chart's"
_CARD_LATER_PROFILE_YELLOW_2 = "estimate, not a misread."
#: Beta 9 (Knut, #182 5979886227): a flagged patch confirmed by flagged
#: patches of other strips that were expected nearly the same colour and are
#: off in the same way. The card's counterpart of "Yellow outline: confirmed
#: by a re-read". (Beta 8's three "Patches closer than ΔE 6 ..." lines are
#: gone with the spacing they explained.)
_CARD_PEER_1 = "Yellow outline: confirmed by similar patches"
_CARD_PEER_2 = "Read alike in other strips: {locs}"
#: Knut, #182 5980576263: every card says what to do. A red card tells the
#: user to read the patch again; every yellow card (re-read, similar patches,
#: learned) that there is no need to.
_CARD_RED_READ_AGAIN = "Read it again to find out."
_CARD_YELLOW_NO_NEED = "No need to read it again."
#: The twelve ranges' names, as the post named them (purple/violet was
#: merged into blue in beta 11, Knut #182 5983470377).
_RANGE_GREY_DARK = "dark grey"
_RANGE_GREY_MID = "mid grey"
_RANGE_GREY_LIGHT = "light grey"
_RANGE_PINK = "pink/rose"
_RANGE_RED = "red"
_RANGE_ORANGE = "orange/brown"
_RANGE_YELLOW = "yellow"
_RANGE_YELLOW_GREEN = "yellow-green"
_RANGE_GREEN = "green"
_RANGE_CYAN = "cyan/turquoise"
_RANGE_BLUE = "blue"
_RANGE_MAGENTA = "magenta"
#: workflow.patch_flags.RANGES -> the name the card shows (through tr()).
RANGE_NAMES = {
    "grey_dark": _RANGE_GREY_DARK, "grey_mid": _RANGE_GREY_MID,
    "grey_light": _RANGE_GREY_LIGHT, "pink": _RANGE_PINK, "red": _RANGE_RED,
    "orange": _RANGE_ORANGE, "yellow": _RANGE_YELLOW,
    "yellow_green": _RANGE_YELLOW_GREEN, "green": _RANGE_GREEN,
    "cyan": _RANGE_CYAN, "blue": _RANGE_BLUE,
    "magenta": _RANGE_MAGENTA,
}
M_PATCH_COLOUR_RANGE = _m(
    "M-PATCH-COLOUR-RANGE",
    _CARD_RANGE,
    "\n".join((_CARD_RANGE_SO_FAR, _CARD_RANGE_SAME,
               _CARD_RANGE_LEARNED_1, _CARD_RANGE_LEARNED_2,
               _CARD_RANGE_LEARNED_3, _CARD_RANGE_LEARNED_4,
               _CARD_RANGE_RED_LEARNED_1, _CARD_RANGE_RED_LEARNED_2,
               _CARD_RANGE_CONFIRMED_LEARNED, _CARD_PEER_1, _CARD_PEER_2,
               _CARD_RED_READ_AGAIN, _CARD_YELLOW_NO_NEED,
               _CARD_MISFIT_SMALLER, _CARD_MISFIT_SMALLER_NEXT,
               _CARD_MISFIT_SMALLER_LIMIT, _CARD_MISFIT_SIDEWAYS,
               _CARD_MISFIT_SIDEWAYS_NEXT, _CARD_MISFIT_SIDEWAYS_DE,
               _CARD_MISFIT_SIDEWAYS_LIMIT,
               _CARD_MISFIT_STANDOUT, _CARD_MISFIT_STANDOUT_NEXT,
               _CARD_MISFIT_STANDOUT_DE, _CARD_MISFIT_STANDOUT_LIMIT,
               _CARD_MISFIT_REFS, _CARD_MISFIT_REFS_SOME, _CARD_DE_SPAN,
               _CARD_MISFIT_LANDED, _CARD_MISFIT_LANDED_DE,
               _CARD_RANGE_LANDED_1, _CARD_RANGE_LANDED_2,
               _CARD_VERIFY_RED_1, _CARD_VERIFY_RED_2, _CARD_VERIFY_RED_3,
               _CARD_VERIFY_SAME_1, _CARD_VERIFY_SAME_2,
               _CARD_VERIFY_YELLOW_1, _CARD_VERIFY_YELLOW_2,
               _CARD_VERIFY_YELLOW_3, _CARD_VERIFY_YELLOW_4,
               _CARD_VERIFY_LEARNED,
               _CARD_LATER_PROFILE_1, _CARD_LATER_PROFILE_2,
               _CARD_LATER_PROFILE_3, _CARD_LATER_PROFILE_4,
               _CARD_LATER_PROFILE_5, _CARD_LATER_PROFILE_6,
               _CARD_LATER_PROFILE_SAME_1, _CARD_LATER_PROFILE_SAME_2,
               _CARD_LATER_PROFILE_YELLOW_1, _CARD_LATER_PROFILE_YELLOW_2)),
    approved=False)

# --- PROPOSED: the expected colour is the profile's prediction --------------
#: #182, 2026-10-03. Knut approved the idea in 5964173774 (answer 4: Show
#: "expected: profile prediction" on the patch hover card for these charts?
#: "Yes."); the exact words wait here. The card's "Expected" label becomes
#: this line on a verification chart judged against the run profile's
#: prediction (workflow/verify_expected.py). One line, so the body is the
#: headline itself.
_CARD_EXPECTED_PREDICTED = "Expected: profile prediction"
M_PATCH_EXPECTED_PREDICTED = _m(
    "M-PATCH-EXPECTED-PREDICTED",
    _CARD_EXPECTED_PREDICTED,
    _CARD_EXPECTED_PREDICTED,
    approved=True)

# --- APPROVED: the neighbour check on a patch's hover card (beta 17) -------
#: Knut's four steps (#182 6071673457, adopted in 6078174421) and his card
#: wording, 6078174421 ("This should be clear enough"), drawn in the k56
#: mock-ups and approved in 6084176226 (Question 5, "Are these the cards you
#: want?" "Yes, good."). Whole sentences: the card wraps them to its width
#: (``ui.tiff_preview.card_wrap``), so a translation is one sentence too.
#: {d}: ΔE*ab, one decimal, never negative (the sign is the word: further /
#: closer; at 0.0 no value is shown); {n}: 2 to 4, never fewer (a patch with
#: fewer neighbours is not judged), so no language needs a singular form;
#: {limit}: the Neighbour limit of the chart type, one decimal.
#:
#: Line 1, 2 or 3 stand on EVERY card of a patch with at least 2 neighbours,
#: under "Measured". The headline is the red card's, under the separator,
#: followed by the two re-read lines and "Same value after a re-read:". Line 4
#: replaces "ΔE*ab ... reached the patch error limit ..." on the yellow card
#: of a patch its re-read confirmed. Lines 7 and 8 (strips) or 7b and 8
#: (patch by patch) end EVERY card (Knut 6071004702, 6082015002).
_CARD_NB_RED_S = ("Red outline: ΔE {d} further from its expected colour than "
                  "the {n} patches nearest in colour (median), passing the "
                  "neighbour limit ({limit}).")
#: The red card's second sentence, on a line of its own as in the mock-up.
_CARD_NB_MISREAD_S = "Probably a misread: read it again."
_CARD_NBC_FURTHER_S = ("This patch is ΔE {d} further from its expected colour "
                       "than the {n} patches nearest in colour (median).")
_CARD_NBC_CLOSER_S = ("This patch is ΔE {d} closer to its expected colour "
                      "than the {n} patches nearest in colour (median).")
_CARD_NBC_EQUAL_S = ("This patch has equal distance from its expected colour "
                     "as the {n} patches nearest in colour (median).")
_CARD_NB_YELLOW_S = ("Red before: ΔE {d} further from its expected colour "
                     "than the {n} patches nearest in colour (median), passing "
                     "the neighbour limit ({limit}).")
#: Knut, #182 5984174575: "The neighbour check needs a re-read to confirm";
#: similar patches and a learned colour range apply only to the patch error
#: limit. Two lines, as the card has always shown them.
_CARD_NB_REREAD_1 = "Only its own re-read can turn it yellow,"
_CARD_NB_REREAD_2 = "not similar patches or its colour range."
_CARD_LATER_STRIP_S = ("Checked again after each strip is read: a patch can "
                       "turn red later, when patches near it in colour are "
                       "read.")
_CARD_LATER_PATCH_S = ("Checked again after each patch is read: a patch can "
                       "turn red later, when patches near it in colour are "
                       "read.")
_CARD_SEE_PREFS_S = "See Preferences ▸ Measurement for threshold values."
#: The headline names the block in the model; the card never shows it.
_CARD_NB_HEADLINE = "Neighbour check on the patch card"
M_PATCH_NEIGHBOUR = _m(
    "M-PATCH-NEIGHBOUR",
    _CARD_NB_HEADLINE,
    "\n".join((_CARD_NB_RED_S, _CARD_NB_MISREAD_S, _CARD_NBC_FURTHER_S, _CARD_NBC_CLOSER_S,
               _CARD_NBC_EQUAL_S,
               _CARD_NB_YELLOW_S, _CARD_NB_REREAD_1, _CARD_NB_REREAD_2,
               _CARD_LATER_STRIP_S, _CARD_LATER_PATCH_S, _CARD_SEE_PREFS_S)),
    approved=True)

# --- PROPOSED: the neighbour check's lines the mock-ups did not show -------
#: Beta 17, ours. Text approved by Basti, 2026-10-10; waiting for Knut,
#: so still PROPOSED. Line 1 (the headline): a patch past the patch
#: error limit that ALSO fails the neighbour check, after the limit's lines.
#: Line 2: a patch with fewer than 2 read patches within the colour-neighbour
#: radius, instead of line 1, 2 or 3 of M-PATCH-NEIGHBOUR.
_CARD_NB_ALSO_S = ("It is also ΔE {d} further from its expected colour than "
                   "the {n} patches nearest in colour (median), passing the "
                   "neighbour limit ({limit}).")
_CARD_NBC_FEW_S = ("Not compared with the patches nearest in colour yet: "
                   "fewer than 2 within the colour-neighbour radius are read.")
_CARD_NB_VARIANTS_HEADLINE = "Neighbour check on the patch card, two more lines"
M_PATCH_NEIGHBOUR_VARIANTS = _m(
    "M-PATCH-NEIGHBOUR-VARIANTS",
    _CARD_NB_VARIANTS_HEADLINE,
    "\n".join((_CARD_NB_ALSO_S, _CARD_NBC_FEW_S)),
    approved=False)

# --- APPROVED: the patch error limit on a patch's hover card (beta 17) -----
#: The k56 mock-ups card_red_patch_error_limit and card_red_verification_limit,
#: approved by Knut in #182 6084176226 ("Yes, good."): the limit is named by
#: its proper name, with its value and the chart type it belongs to, and the
#: strip test by its name. {de}: the patch's ΔE*ab, {limit}: the Patch error
#: limit, one decimal each; {kind}: one of the four chart-type phrases below.
#: Line 1 or 2 follows the headline; line 1 alone also stands on a yellow
#: card instead of the old "reached your limit".
_CARD_LIMIT_HEAD = "Red outline: a large difference"
_CARD_LIMIT_S = "ΔE*ab {de} reached the patch error limit ({limit}, {kind})."
_CARD_LIMIT_FENCED_S = ("ΔE*ab {de} reached the patch error limit ({limit}, "
                        "{kind}), and it stands out from its strip (strip "
                        "test).")
_CARD_KIND_ESTIMATED = "profiling charts with estimated colours"
_CARD_KIND_ACCURATE = "profiling charts made with a pre-conditioning profile"
_CARD_KIND_VERIFICATION = "verification charts"
_CARD_KIND_CALIBRATION = "calibration charts"
CARD_KIND_PHRASES = {
    "estimated": _CARD_KIND_ESTIMATED, "accurate": _CARD_KIND_ACCURATE,
    "verification": _CARD_KIND_VERIFICATION,
    "calibration": _CARD_KIND_CALIBRATION,
}
M_PATCH_LIMIT = _m(
    "M-PATCH-LIMIT",
    _CARD_LIMIT_HEAD,
    "\n".join((_CARD_LIMIT_S, _CARD_LIMIT_FENCED_S, _CARD_KIND_ESTIMATED,
               _CARD_KIND_ACCURATE, _CARD_KIND_VERIFICATION,
               _CARD_KIND_CALIBRATION)),
    approved=True)

# --- APPROVED: the green outline of a misread a re-read corrected ----------
#: Knut, #182 5984277558 ("Ok") to our 5984237879: "Green outline: corrected
#: by a re-read. The first reading (ΔE 58 off) did not fit; the new one does.
#: It replaces the misread." and "2 misreads corrected by a re-read: patches
#: Y6, AE8." Approved line by line; the card breaks its lines by hand. {de}:
#: the first reading's ΔE*ab from the expected colour, a whole number.
_CARD_GREEN_HEAD = "Green outline: corrected by a re-read"
_CARD_GREEN_1 = "The first reading (ΔE {de} off)"
_CARD_GREEN_NB = "did not fit; the new one does."
_CARD_GREEN_END = "It replaces the misread."
_SUM_CORRECTED = "{n} misreads corrected by a re-read: patches {locs}."
M_PATCH_CORRECTED = _m(
    "M-PATCH-CORRECTED",
    _CARD_GREEN_HEAD,
    "\n".join((_CARD_GREEN_1, _CARD_GREEN_NB, _CARD_GREEN_END,
               _SUM_CORRECTED)),
    approved=True)
# --- PROPOSED: its two variants -----------------------------------------------
#: Not in Knut's example, so ours and waiting: the middle line when the LIMIT
#: flagged the first reading (his line is the neighbour check's), and the
#: closing window's line for one patch.
_CARD_GREEN_LIMIT = "reached the patch error limit; the new one is below it."
_SUM_CORRECTED_ONE = "1 misread corrected by a re-read: patch {locs}."
M_PATCH_CORRECTED_VARIANTS = _m(
    "M-PATCH-CORRECTED-VARIANTS",
    _CARD_GREEN_HEAD,
    "\n".join((_CARD_GREEN_LIMIT, _SUM_CORRECTED_ONE)),
    approved=False)

# --- PROPOSED: a re-read past the limit that agrees with no earlier reading ---
#: Knut, #182 6045500910 (beta 12), answer 2: a patch red by the limit read
#: again, past the limit again and not the same as its earlier reading (more
#: than ΔE 3 apart), stays red, "and message should say that the two
#: measurements were not similar and both above error threshold, and needs
#: another measurement to confirm what is the reoccurring and correct value
#: for the patch." The rule is his and CONFIRMED (10.10a); the words are ours
#: and wait here. The card breaks its lines by hand. {de}: this reading's
#: ΔE*ab, {prevs}: the earlier readings past the limit, in the order read,
#: each with one decimal, joined by ", "; {limit}: the limit, one decimal;
#: {n}: how many readings, 3 or more (the "two" line covers 2).
_CARD_UNSETTLED_HEAD = "Red outline: the readings do not agree"
_CARD_UNSETTLED_DE = "ΔE*ab {de} now; before: {prevs}"
_CARD_UNSETTLED_TWO_1 = "The two readings are not similar,"
_CARD_UNSETTLED_TWO_2 = "and both are past the patch error limit ({limit})."
_CARD_UNSETTLED_MANY_1 = "The {n} readings are not similar,"
_CARD_UNSETTLED_MANY_2 = "and all are past the patch error limit ({limit})."
_CARD_UNSETTLED_3 = "Read it again: a reading that matches"
_CARD_UNSETTLED_4 = "one of them shows which value is real."
M_PATCH_UNSETTLED = _m(
    "M-PATCH-UNSETTLED",
    _CARD_UNSETTLED_HEAD,
    "\n".join((_CARD_UNSETTLED_DE, _CARD_UNSETTLED_TWO_1,
               _CARD_UNSETTLED_TWO_2, _CARD_UNSETTLED_MANY_1,
               _CARD_UNSETTLED_MANY_2, _CARD_UNSETTLED_3,
               _CARD_UNSETTLED_4)),
    approved=False)

# --- PROPOSED: the misread summary in the window that closes a measurement --
#: #182 beta 11, Knut 5983470377 answer 5: "The Measurement Completed window,
#: which today has a summary of some things (like the reading speeds) should
#: also hold a short summary of the detected suspected misreads from the
#: neighbour-test method and (if active) the strip misreading test." Shown
#: under the reading-time summary, on every profiling and calibration
#: measurement's closing window, never on a verification's. The neighbour
#: lines only where the check applies (a profiling chart with estimated
#: expected colours); the strip lines only when "Was a strip read twice?" ran
#: (strips read with ChromIQ's engine, outside guided refinement). {locs}:
#: the patches in chart order, the first ten and then "…". {list}: the
#: strips, each with its item line.
#: The headline names the block in the model; the window shows its lines
#: under the reading-time summary without it.
_SUM_HEADLINE = "Suspected misreads"
_SUM_NB_NONE = "Neighbour check: no suspected misreads."
_SUM_NB_RED_ONE = ("Neighbour check: 1 suspected misread, patch {locs}. "
                   "Read it again before you build the profile.")
_SUM_NB_RED = ("Neighbour check: {n} suspected misreads, patches {locs}. "
               "Read them again before you build the profile.")
_SUM_NB_KEPT_ONE = ("1 patch it flagged was read again with the same "
                    "result, so it is taken as real.")
_SUM_NB_KEPT = ("{n} patches it flagged were read again with the same "
                "result, so they are taken as real.")
#: Instead of "no suspected misreads" when not one patch could be checked (a
#: small chart, or one read only in part): nothing was found because nothing
#: could be looked at (review of beta 11).
_SUM_NB_NONE_CHECKED = ("Neighbour check: none of the {total} patches had "
                        "enough patches near in colour to be checked.")
_SUM_NB_PARTLY = ("{checked} of {total} patches had enough patches near in "
                  "colour to be checked.")
_SUM_TWICE_NONE = "Strip read twice: none found."
_SUM_TWICE_ONE = "Strip read twice: 1 strip looked like another, {list}."
_SUM_TWICE = "Strip read twice: {n} strips looked like another, {list}."
_SUM_TWICE_REREAD = "{strip} (like {like}, read again)"
_SUM_TWICE_WAS_LIKE = "{strip} (like {like}, set aside)"
_SUM_TWICE_KEPT = "{strip} (like {like}, kept)"
M_MEASURED_SUSPECTS = _m(
    "M-MEASURED-SUSPECTS",
    _SUM_HEADLINE,
    "\n".join((_SUM_NB_NONE, _SUM_NB_RED_ONE, _SUM_NB_RED, _SUM_NB_KEPT_ONE, _SUM_NB_KEPT,
               _SUM_NB_PARTLY, _SUM_NB_NONE_CHECKED, _SUM_TWICE_NONE, _SUM_TWICE_ONE, _SUM_TWICE,
               _SUM_TWICE_REREAD, _SUM_TWICE_WAS_LIKE, _SUM_TWICE_KEPT)),
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

# --- PROPOSED: was a strip read twice? (#182, the live check while measuring)
#: Knut, #182 5963903650, question 5, answered "Yes." to the check and to its
#: question as written in 5963737221: *"Strip D looks very like strip C, which
#: you already measured. Did you read strip C again?"* with the buttons
#: *Re-read strip D* / *Keep, it is strip D*. Those words are his approval's;
#: the two lines saying what each button does are ours, so the message waits
#: in §M-PROPOSED. The check: workflow/strip_read_twice.py.
_READ_TWICE_REREAD = "Re-read strip {strip}"
_READ_TWICE_KEEP = "Keep, it is strip {strip}"
#: The third answer, beta 8 (Knut, #182 5969949735: he read strip B on purpose
#: with the reader on A, and the window had no way to say so). The engine
#: cannot move a reading to another strip, so the reading is set aside and B
#: is read again where it belongs; A counts as unread until it is read.
_READ_TWICE_WAS = "I read strip {like}"
M_STRIP_READ_TWICE = _m(
    "M-STRIP-READ-TWICE",
    "Was a strip read twice?",
    "Strip {strip} looks very like strip {like}, which you already measured. "
    "Did you read strip {like} again?\n\n"
    "•  Re-read strip {strip}: the reader goes back to strip {strip}. Read it "
    "again and the new reading replaces this one.\n\n"
    "•  I read strip {like}: the reader goes to strip {like}. Read it there "
    "again, then read strip {strip}, which still has to be measured.\n\n"
    "•  Keep, it is strip {strip}: this reading stays as strip {strip}, and "
    "measuring goes on.",
    approved=False)

# --- PROPOSED: the Check & Refine result window (#182, the redesign) -------
#: Knut approved the design on the pictures (#182 5963903650 on 5963737221):
#: two lists, worst first, a reason for each strip listed first, the choice
#: "strips listed first" (the default) / "all strips above your limit"; start
#: over advised only above half of all patches, refinement still offered. The
#: sentences below are the ones the pictures showed, word for word, and a few
#: the pictures needed but did not show (the singulars, a single list, no
#: patch above the limit). Shown is not approved, so they wait in §M-PROPOSED.
#: workflow/refine_plan.py decides; ui/tabs/tab_check_refine.py renders both
#: the window and the saved report from these, so the two say one thing.
_CR_NUMBERS = "Average {de} {avg:.2f}  |  Largest {de} {peak:.2f}"
_CR_OVER_ONE = "1 of {total} patches is above your limit of {de} {limit:.1f}."
_CR_OVER_MANY = ("{n} of {total} patches ({pct}%) are above your limit of "
                 "{de} {limit:.1f}.")
_CR_OVER_NONE = ("No patch is above your limit of {de} {limit:.1f}. Nothing "
                 "needs re-measuring.")
_CR_START_OVER = (
    "<b>More than half of your patches are above your limit ({n} of {total}, "
    "{pct}%).</b> Re-measuring strips is unlikely to fix all of this: printing "
    "and measuring a fresh chart is recommended. You can still re-measure the "
    "strips below first, to rule out reading mistakes. If your limit is very "
    "strict, a higher one may suit this printer better.")
_CR_FIRST_HEAD = (
    "<b>Re-measure these strips first</b> (worst first). Each has a patch that "
    "may have been misread, and a re-read shows whether it was:")
_CR_STRIP = "Strip {strip}"
_CR_WHY_OUTLIER = ("Patch {patch} ({de} {value:.2f}) stands out clearly from "
                   "the rest of this check.")
_CR_WHY_BLEND = (
    "Patch {patch} ({de} {value:.2f}) looks partly like its neighbour "
    "{neighbour}, as if the instrument was moved unevenly. Move it steadily "
    "over strip {strip}.")
_CR_N_IN_STRIP = "{n} patches in this strip are above your limit."
_CR_REST_HEAD_MORE_ONE = (
    "<b>1 more strip has at least one patch above {de} {limit:.1f}</b> "
    "(worst patch, and how many are above):")
_CR_REST_HEAD_MORE_MANY = (
    "<b>{n} more strips have patches above {de} {limit:.1f}</b> "
    "(worst first; worst patch, and how many are above):")
_CR_REST_HEAD_ONE = (
    "<b>1 strip has at least one patch above {de} {limit:.1f}</b> "
    "(worst patch, and how many are above):")
_CR_REST_HEAD_MANY = (
    "<b>{n} strips have patches above {de} {limit:.1f}</b> "
    "(worst first; worst patch, and how many are above):")
_CR_CHOICE_FIRST_ONE = "Re-measure the strip listed first"
_CR_CHOICE_FIRST_MANY = "Re-measure the {n} strips listed first"
_CR_CHOICE_ALL = "Re-measure all {n} strips above your limit"
_CR_ORDER = ("The guide takes you through the chosen strips in chart order "
             "(A, B, C ...), the order the instrument reads them in.")
M_CR_STRIPS = _m(
    "M-CR-STRIPS",
    "Re-measure these strips first",
    "\n".join((_CR_NUMBERS, _CR_OVER_ONE, _CR_OVER_MANY, _CR_OVER_NONE,
               _CR_FIRST_HEAD, _CR_STRIP, _CR_WHY_OUTLIER, _CR_WHY_BLEND,
               _CR_N_IN_STRIP, _CR_REST_HEAD_MORE_ONE, _CR_REST_HEAD_MORE_MANY,
               _CR_REST_HEAD_ONE, _CR_REST_HEAD_MANY, _CR_CHOICE_FIRST_ONE,
               _CR_CHOICE_FIRST_MANY,
               _CR_CHOICE_ALL, _CR_ORDER)),
    approved=False)
M_CR_START_OVER = _m(
    "M-CR-START-OVER",
    "More than half of your patches are above your limit",
    _CR_START_OVER,
    approved=False)
#: Knut, 5963903650 Q6, "OK" to this text as the pictures showed it. It
#: describes what ArgyllCMS targen -c does (patches spread evenly by how
#: colours look, not aimed at the colours that measured badly), so it is never
#: "recommended" as a fix. Used by Check & Refine and by Profile Built.
_CR_PRECOND = (
    "<b>Use as pre-conditioning profile</b>: start a new chart whose patches "
    "are spread evenly by how colours look on this printer and paper, using "
    "this profile as a guide, instead of evenly by RGB numbers. This often "
    "gives a better second profile. It does not aim the new patches at the "
    "colours that measured badly here, so it does not replace re-measuring. "
    "This profile and its measurements stay in their own run folder.")
M_CR_PRECONDITIONING = _m(
    "M-CR-PRECONDITIONING",
    "Use as pre-conditioning profile",
    _CR_PRECOND,
    approved=False)

# --- PROPOSED: after a read, the next strip/patch is not the unread one ---
#: Knut, #182 5958921500, Q2, and the text is his: *"If strips still unread,
#: then re-reading a read strip should not jump to next unread, but instead ask
#: with a popup that appears only one time per started measurement … 'Some
#: patches / strips are still not read. What do you want to do? 1. Continue to
#: next: position to read jumps to next patch / strip from current position,
#: even if previously measured. 2. Jump to unread: position to read jumps to
#: closest unread patch / strip to complete the measurement.'"* His own words
#: went through §M-PROPOSED and were APPROVED by Knut, 2026-10-03 (5962907586).
#: Two variants because the unit differs: strip mode and patch-by-patch.
M_UNREAD_NEXT_OR_JUMP_STRIP = _m(
    "M-UNREAD-NEXT-OR-JUMP-STRIP",
    "Some patches are still not read",
    "{n} patches on this chart have no reading yet. What would you like to do "
    "next?\n\n"
    "•  Continue to next: the reader moves to the strip after the one you "
    "have just read, even if that strip was measured before.\n\n"
    "•  Jump to unread: the reader moves forward to the next strip that "
    "still has patches without a reading (after the last strip it carries "
    "on from the first), so you can complete the measurement.\n\n"
    "ChromIQ asks once. Your choice stays for the rest of this measurement, "
    "and f, b, n or a click on the preview still take you anywhere.",
    approved=True,
    count_key="n",
    title_one="One patch is still not read",
    body_one=
    "One patch on this chart has no reading yet. What would you like to do "
    "next?\n\n"
    "•  Continue to next: the reader moves to the strip after the one you "
    "have just read, even if that strip was measured before.\n\n"
    "•  Jump to unread: the reader moves forward to the strip that still "
    "has a patch without a reading (after the last strip it carries on "
    "from the first), so you can complete the measurement.\n\n"
    "ChromIQ asks once. Your choice stays for the rest of this measurement, "
    "and f, b, n or a click on the preview still take you anywhere.")

M_UNREAD_NEXT_OR_JUMP_PATCH = _m(
    "M-UNREAD-NEXT-OR-JUMP-PATCH",
    "Some patches are still not read",
    "{n} patches on this chart have no reading yet. What would you like to do "
    "next?\n\n"
    "•  Continue to next: the reader moves to the patch after the one you "
    "have just read, even if that patch was measured before.\n\n"
    "•  Jump to unread: the reader moves forward to the next patch that has "
    "no reading yet (after the last patch it carries on from the first), so "
    "you can complete the measurement.\n\n"
    "ChromIQ asks once. Your choice stays for the rest of this measurement, "
    "and f, b, n or a click on the preview still take you anywhere.",
    approved=True,
    count_key="n",
    title_one="One patch is still not read",
    body_one=
    "One patch on this chart has no reading yet. What would you like to do "
    "next?\n\n"
    "•  Continue to next: the reader moves to the patch after the one you "
    "have just read, even if that patch was measured before.\n\n"
    "•  Jump to unread: the reader moves forward to the patch that has no "
    "reading yet (after the last patch it carries on from the first), so "
    "you can complete the measurement.\n\n"
    "ChromIQ asks once. Your choice stays for the rest of this measurement, "
    "and f, b, n or a click on the preview still take you anywhere.")


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

# --- PROPOSED: a strip or patch pattern the readers cannot use -----------
#: Forum report, 2026-10-03: the strip pattern "0-9" made a 14-strip chart
#: that neither ArgyllCMS chartread nor ChromIQ's engine could read, because
#: ChromIQ printed "10", "11" ... while Argyll's "0-9" stops at 9. Create Chart
#: now refuses such a pair for a NEW layout: the box turns red, this sentence
#: stands under the preview, and Generate Chart is unavailable. {reason} is
#: one sentence from `workflow.layout_engine.alphix.check_patterns`. Not a
#: window: it changes on every keystroke.
M_CHART_PATTERN_REFUSED = _m(
    "M-CHART-PATTERN-REFUSED",
    "This strip or patch pattern cannot be used",
    "{reason} Generate Chart stays unavailable until the pattern is changed.",
    approved=False)

# --- PROPOSED: a printed chart whose locations its patterns cannot read ----
#: The same fault seen from the Measure tab, on a sheet already printed with
#: such a pair. Checked before any reader starts
#: (`alphix.chart_locations_problem`), because both readers parse the
#: locations the same way and the fallback to stock chartread could only fail
#: a second time. {detail} names the first location that does not fit.
M_CHART_LOCATIONS_UNREADABLE = _m(
    "M-CHART-LOCATIONS-UNREADABLE",
    "This chart cannot be measured",
    "This chart's patch locations do not fit its strip and patch patterns: "
    "{detail}.\n\n"
    "ArgyllCMS chartread would refuse the chart before the first patch, or "
    "file the readings under the wrong patches, and ChromIQ's own measuring "
    "engine reads it the same way. So ChromIQ has not started a measurement, "
    "and nothing has been changed.\n\n"
    "The chart was laid out with a strip or patch pattern that ArgyllCMS "
    "reads differently from the labels printed on the sheet. To measure, "
    "generate the chart again with the default patterns (A-Z, A-Z for "
    "strips and 0-9,@-9,@-9;1-999 for patches) and print it again.",
    approved=False)

# --- PROPOSED: a sheet only ChromIQ's engine can read, on stock chartread ----
#: Knut, #182 5965589190 Q2: a sheet printed with ChromIQ's labels from
#: before 4.3.3-beta.7 is read by ChromIQ's own engine as printed, and a user
#: of ArgyllCMS chartread is told plainly that chartread cannot read it.
M_CHART_LEGACY_STOCK = _m(
    "M-CHART-LEGACY-STOCK",
    "ArgyllCMS chartread cannot read this chart",
    "This chart's patch locations do not fit its strip and patch patterns: "
    "{detail}.\n\n"
    "The labels were printed by an earlier version of ChromIQ, and ArgyllCMS "
    "chartread reads them differently from the sheet, so it would refuse the "
    "chart or file the readings under the wrong patches. ChromIQ's own "
    "measuring engine reads the labels as they are printed.\n\n"
    "Right now, “ChromIQ chart-reading engine” in Preferences → Measurement "
    "is switched off, so ArgyllCMS chartread reads your charts. Switch it on "
    "and this chart measures normally. Nothing has been started or changed.",
    approved=False)

# --- PROPOSED: that sheet's engine run ended, and there is no second reader ---
M_CHART_LEGACY_ENDED = _m(
    "M-CHART-LEGACY-ENDED",
    "The measurement stopped",
    "Reading this chart has stopped before it finished.\n\n"
    "This chart's labels were printed by an earlier version of ChromIQ in a "
    "way ArgyllCMS chartread cannot read, so there is no second reader to "
    "try, and ChromIQ has not started it.\n\n"
    "Nothing you have already measured is lost: every patch that was read is "
    "on disk, and you can carry on from it by ticking “Refine / resume "
    "existing measurement (-r)” before you press Start again.\n\n"
    "What went wrong: {reason}",
    approved=False)

# --- PROPOSED: no instrument is connected at all -------------------------
#: Knut, #182 5969949735 (beta 7): when ChromIQ refuses to start because no
#: instrument is attached (the only serial port is the computer's own, see
#: core/instrument_port.py), the window came after about one second and still
#: said the instrument "has not replied for 5 seconds" and suggested turning
#: off "Faster instrument connection". Asked whether that case should be
#: reworded, he answered "yes". Nothing was asked of an instrument here and
#: the shortcut has nothing to do with it, so this variant says only what is
#: true: none is connected, connect it, press Start again. M-NO-INSTRUMENT and
#: M-NO-INSTRUMENT-FAST stay as they are for the case where a reader really
#: did wait for an instrument that did not answer.
M_NO_INSTRUMENT_NONE = _m(
    "M-NO-INSTRUMENT-NONE",
    "No Instrument Connected",
    "ChromIQ cannot find a measuring instrument connected to this computer, "
    "so the measurement has not started.\n\n"
    "Connect your instrument with its USB cable, give the computer a moment "
    "to recognise it, and press Start again.\n\n"
    "Nothing has been lost: any measurement you already had is kept exactly "
    "as it was.",
    # Approved in full by Knut, #182 5979780372 ("all are ok", question 1 of
    # 5979436912).
    approved=True)

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

# --- PROPOSED (#182 K26, Knut 2026-09-23): a project whose folder is not
# called what its files are called ---------------------------------------------
#
# Knut, 5792484060 (Q5): *"If a project is opened where the root project folder
# is different than the defined name in 'Printer profile project name' field,
# then the user should be given the option, with a popup window, to rename the
# project. This interface and function should already exist and just has to
# be modified a tiny bit to allow this case."* The window is the existing
# rename chooser (`TargetChangeDialog`); its heading and introduction for this
# case are new wording and wait here. {folder} is the folder as it is on disk,
# {name} the name its files and project.json carry, {new} what the project
# becomes (the name the "Printer profile project name" field shows).
M_PROJECT_FOLDER_RENAMED = _m(
    "M-PROJECT-FOLDER-RENAMED",
    "This project's folder is called \u201c{folder}\u201d, but its files are "
    "named \u201c{name}\u201d",
    "ChromIQ finds a project's charts, measurements, profiles and reports by "
    "the name of its folder, so until the two match it finds none of them. "
    "This happens when a project folder is copied, duplicated or renamed "
    "outside ChromIQ.\n\n"
    "\u2022  Rename the project to \u201c{new}\u201d: every file that carries "
    "the name \u201c{name}\u201d is renamed to carry \u201c{new}\u201d, and "
    "the folder too when its name has a space or a character a file name "
    "cannot carry. Nothing is deleted.{built}\n\n"
    "\u2022  Choose another name: you type the name the project is to have, "
    "and its folder and files are renamed to it in the same way.\n\n"
    "\u2022  Cancel: nothing is changed, and the project is closed.",
    approved=True)

#: #182, Knut 5794078008: the window offers exactly three choices, each
#: explained by a bullet in its text, and no "Leave it as it is". ``{built}``
#: in the body is empty, or this sentence (with a space before it) when a
#: run of the project has a built profile, which is still offered the rename
#: ("Yes", same comment).
_FOLDER_RENAMED_BUILT = ("A profile already built keeps the name written "
                         "inside it, \u201c{name}\u201d, which is what "
                         "ColorSync Utility and other programs show.")
#: The three buttons, in the order the bullets name them.
_FOLDER_RENAMED_RENAME = "Rename the project to \u201c{new}\u201d"
_FOLDER_RENAMED_OTHER = "Choose another name\u2026"
_FOLDER_RENAMED_CANCEL = "Cancel"
#: The name window's line when "Choose another name" opens it (the existing
#: project-name window, `name_prompt.ask_for_project_name`).
_FOLDER_RENAMED_NAME_BODY = (
    "Type the name this project is to have. Its folder, and every file that "
    "carries the name \u201c{name}\u201d, are renamed to it.")


def folder_renamed_texts(*, folder: str, name: str, new: str,
                         built: bool) -> dict:
    """Every piece of text of the folder-renamed window, rendered (#182,
    Knut 5794078008): ``title``, ``body``, the three buttons ``rename``,
    ``other``, ``cancel``, and ``name_body`` for the name window."""
    extra = (" " + tr(_FOLDER_RENAMED_BUILT).format(name=name)) if built \
        else ""
    title, body = M_PROJECT_FOLDER_RENAMED.render(
        folder=folder, name=name, new=new, built=extra)
    return {"title": title, "body": body,
            "rename": tr(_FOLDER_RENAMED_RENAME).format(new=new),
            "other": tr(_FOLDER_RENAMED_OTHER),
            "cancel": tr(_FOLDER_RENAMED_CANCEL),
            "name_body": tr(_FOLDER_RENAMED_NAME_BODY).format(name=name)}

#: …and the window for when that rename cannot be done.
M_PROJECT_FOLDER_RENAME_FAILED = _m(
    "M-PROJECT-FOLDER-RENAME-FAILED",
    "The project could not be renamed",
    "ChromIQ could not rename the project \u201c{name}\u201d to "
    "\u201c{new}\u201d.\n\n"
    "What went wrong: {error}\n\n"
    "Nothing was changed, and the project is open as it was. Its files still "
    "carry the name \u201c{name}\u201d, so ChromIQ does not find them in the "
    "folder \u201c{folder}\u201d.",
    approved=True)

#: What M-PROJECT-FOLDER-RENAME-FAILED says went wrong, in words (#182 beta
#: 38, F6). The window printed the exception, which for the commonest cause
#: (the new name is taken) was a bare path. Each is its own module constant,
#: because the extractor resolves ``tr(NAME)`` only for those.
_RENAME_WHY_TAKEN = ("A folder called \u201c{name}\u201d is already there, "
                     "beside this one.")
_RENAME_WHY_NOT_ALLOWED = ("ChromIQ is not allowed to change this folder or "
                           "the files in it.")
_RENAME_WHY_GONE = ("A file of the project was no longer where ChromIQ "
                    "expected it.")
_RENAME_WHY_OTHER = "The system refused it ({reason})."


def rename_failure_reason(exc: BaseException) -> str:
    """The ``{error}`` of M-PROJECT-FOLDER-RENAME-FAILED for *exc*: a plain
    sentence, never a bare path (#182 beta 38, F6)."""
    from pathlib import Path as _P
    reason = getattr(exc, "reason", None)
    if isinstance(reason, str) and reason:
        return reason                        # already a sentence (tr'd)
    if isinstance(exc, FileExistsError):
        where = (getattr(exc, "filename", None)
                 or (exc.args[0] if exc.args else ""))
        name = _P(str(where)).name
        return tr(_RENAME_WHY_TAKEN).format(name=name)
    if isinstance(exc, PermissionError):
        return tr(_RENAME_WHY_NOT_ALLOWED)
    if isinstance(exc, FileNotFoundError):
        return tr(_RENAME_WHY_GONE)
    why = (getattr(exc, "strerror", None) or type(exc).__name__)
    return tr(_RENAME_WHY_OTHER).format(reason=why)

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


# --- PROPOSED: an IMPORT lands on a name that is already a project ----------
# The loaders asked this question in their own words and, until 2026-08-31, with
# their own consequence: `txt_loader` said "Overwrite existing folder" and ran
# `shutil.rmtree`, while `ti2_loader` said "Replace existing" and archived. Same
# act, opposite outcome, decided by which file type the person happened to load.
#
# Basti ruled (2026-08-31) that the CONSEQUENCE and the VOCABULARY are shared
# with §S4.7 while the window stays the loaders' own — theirs has a name box and
# a live "this name is taken" line, which §S4.7's has no room for.
#
# "Continue this project" is deliberately absent: two of the three routes have
# no machinery for it (`_copy_txt` and `_copy_ti3_only` always call
# `Project.create` and always make run1), so offering it would be a button that
# cannot keep its promise.
#
# {subject} is "the measurement" for an i1Profiler .txt and a bare .ti3, and
# "the chart" for a .ti2.
M_IMPORT_REPLACE_CONFIRM = _m(
    "M-IMPORT-REPLACE-CONFIRM",
    "Start \u201c{name}\u201d again from empty?",
    "Everything this project holds is about to be moved into its own \u201cold\u201d folder, with today\u2019s date on it:\n\n{folder}\n\nNothing is deleted. That \u201cold\u201d folder stays inside the project, so you can open it at any time and take anything back out of it: the charts, the measurements, the profiles, all of it.\n\nAfter that, a new and completely empty project of the same name is started in the same place, and {subject} you are importing is put into its first run.",
    approved=False)

# --- PROPOSED: where the replaced project went -----------------------------
# Report 10, finding 9: nothing anywhere recorded it — no window, no log line,
# no tab log. "Nothing is deleted" is only true if the person can find it.
# --- PROPOSED: the second look before "Copy the whole project in" replaces --
# This route archived a whole project on ONE CLICK with no confirmation at all,
# while its own error line named a button ("Replace it") that was not on the
# window ("Replace existing"). It needs its own wording because what arrives is
# a whole project with its own runs, not a single file landing in run 1.
M_IMPORT_REPLACE_PROJECT_CONFIRM = _m(
    "M-IMPORT-REPLACE-PROJECT-CONFIRM",
    "Start \u201c{name}\u201d again from empty?",
    "Everything the project here holds is about to be moved into its own \u201cold\u201d folder, with today\u2019s date on it:\n\n{folder}\n\nNothing is deleted. That \u201cold\u201d folder stays in place, so you can open it at any time and take anything back out of it: the charts, the measurements, the profiles, all of it.\n\nThe project you are copying in then takes its place, with everything it brings of its own.",
    approved=False)

M_IMPORT_REPLACED_KEPT = _m(
    "M-IMPORT-REPLACED-KEPT",
    "The earlier \u201c{name}\u201d has been kept",
    "It has been moved into its own \u201cold\u201d folder:\n\n{folder}\n\nNothing was deleted. You can open that folder at any time and take anything back out of it.",
    approved=False)

# --- APPROVED: replacing the calibration chart, both branches -------------
# Basti, 2026-09-02, approving the wording that had to follow his option-3
# ruling on `RULING-calibration-old-charts.txt`. The BEHAVIOUR changed first —
# an unmeasured calibration chart is an experiment and is not kept — and until
# these words landed the window went on promising the opposite, which is the
# fault the whole thread came out of. Two strict xfails held the branch shut
# until this commit.
#
# The two windows have a window TITLE and a bold first line, which is one more
# string than `Message` carries, so the bold line is its own module constant
# beside the message it belongs to. It is not prose in the tab: the tab passes
# the NAME, so every sentence either window can show is written down here.
M_CAL_CHART_HEADLINE = (
    "You already made a calibration chart for this project, but it has not "
    "been measured yet.")

M_CAL_REPLACE_CHART = _m(
    "M-CAL-REPLACE-CHART",
    "Replace this project's calibration chart?",
    "Generating a new one replaces it, and the chart you have now is not kept. "
    "Nothing has been measured from it, so ChromIQ treats it as an attempt "
    "rather than as work to go back to. This is what a profile run does with a "
    "chart you have not measured.\n\n"
    "Once a calibration has been measured it is never replaced this way: the "
    "measurement, the calibration file made from it and the chart that "
    "produced them all move to the project's “cal/old” folder, "
    "and nothing is deleted.\n\n"
    "If you want to keep this chart, press Cancel and copy the “cal” "
    "folder somewhere else first.")

#: The bold first line of M-CAL-REPLACE-MEASURED. UNCHANGED wording — this
#: message was drafted at `docs/design/calibration_run_type_plan.md:240` and
#: the ruling did not touch the measured branch. It moves into the catalogue
#: with the other one so the whole window is governed in one place rather than
#: half of it.
M_CAL_MEASURED_HEADLINE = (
    "This project already has a finished calibration, and generating a new "
    "chart starts that work again from the beginning.")

M_CAL_REPLACE_MEASURED = _m(
    "M-CAL-REPLACE-MEASURED",
    "Replace this project's calibration?",
    "You would need to print the new chart and measure it before this project "
    "has a calibration once more.\n\n"
    "These move to the project's “cal/old” folder, in a folder "
    "named with today's date — nothing is deleted, and you can go "
    "back to them at any time:\n"
    "  •  the calibration chart\n"
    "  •  its measurement\n"
    "  •  the calibration file (.cal) made from it{runs_line}")

#: The {runs_line} fragment of M-CAL-REPLACE-MEASURED: the runs whose profiles
#: were built on the calibration about to be replaced. Real singular and
#: plural, never "(s)" — the house rule.
_CAL_RUNS_ONE = ("{run} was built using this calibration. It is not changed, "
                 "and its profile keeps working, but it was made with the "
                 "calibration you are about to replace.")
_CAL_RUNS_MANY = ("{runs} were built using this calibration. They are not "
                  "changed, and their profiles keep working, but they were "
                  "made with the calibration you are about to replace.")


def calibration_runs_phrase(names: "list[str]") -> str:
    """The ``{runs_line}`` fragment, already joined and already a paragraph.

    Empty when no run recorded this calibration — *absent means unknown*, and
    a run built before ChromIQ recorded it simply does not say, so guessing
    would be worse than staying quiet. *names* are display labels the caller
    has already translated ("Run 3"), so they are not wrapped again.
    """
    if not names:
        return ""
    if len(names) == 1:
        return "\n\n" + tr(_CAL_RUNS_ONE).format(run=names[0])
    head = ", ".join(names[:-1])
    joined = tr("{head} and {last}").format(head=head, last=names[-1])
    return "\n\n" + tr(_CAL_RUNS_MANY).format(runs=joined)


# --- APPROVED: where a replaced calibration went --------------------------
# Basti, 2026-09-02. `Calibration.reset()` returned the archive folder and
# every caller discarded it, so the window promised "a folder named with
# today's date" and the app then named it nowhere — true and unfindable, which
# fails "the user must always be able to answer where are my files". Found by
# the adversarial round. It is written into the log the build is already
# streaming into, beside the tool output, because that is where a person is
# looking when it happens.
M_CAL_ARCHIVED_HERE = _m(
    "M-CAL-ARCHIVED-HERE",
    "The calibration that was here has moved to this folder, and nothing in "
    "it was deleted:",
    "{folder}")

# --- the copy is filed and ChromIQ is NOT in the project --------------------
# APPROVED by Basti, 2026-09-02.
# Round 2 of the import-door review (2026-09-02), findings T1-A, T1-B and T1-C.
#
# `make_new_project_and_file` has three ways to end with the measurement copied
# to disk and the app still standing outside the project it was copied into: no
# manifest above the copy, an open that was attempted and failed, and no Create
# Chart tab to perform the open with. All three ended in a `log.warning` and a
# bar that said "Load a profile project" about a project ChromIQ had just made,
# which is the exact fault the door was rewritten to remove.
#
# The person is told the one thing they cannot work out for themselves: WHERE
# THE FILE IS. Driven: a truncated project.json left the bar saying "Load a
# profile project" and "Location being edited: out/Broken-One/runs/run1/" at the
# same time, with no window at all.
M_IMPORT_NOT_OPENED = _m(
    "M-IMPORT-NOT-OPENED",
    "The measurement is filed, but the project could not be opened",
    "Nothing has been lost. Your own file is untouched where it is, and the "
    "copy ChromIQ made is here:\n\n{folder}\n\nChromIQ could not open that "
    "project afterwards, so it is not the project you are working in, and the "
    "bar at the top still shows the one you were on.\n\nThe reason: "
    "{reason}.\n\nThat folder is an ordinary folder. Everything ChromIQ put "
    "in it, including the measurement you have just imported, is there and can "
    "be opened like any other folder on your computer. Once the reason "
    "above is dealt with, use "
    "\u201cOpen Project\u201d at the top left of the window to go there.",
    approved=True)

#: The three ``{reason}`` fragments of M-IMPORT-NOT-OPENED. They live here, in
#: the catalogue, so the door holds no prose of its own, and each is its own
#: module constant because the extractor resolves ``tr(NAME)`` only for those.
_NOT_OPENED_NO_PROJECT = ("there is no project.json in that folder or above "
                          "it, so ChromIQ has nothing to open")
_NOT_OPENED_UNREADABLE = "the project could not be read ({error})"
_NOT_OPENED_NO_TAB = ("the Create Chart tab, which performs the Open Project "
                      "step, is not open")


#: THE FRAGMENTS ARE READ THROUGH FUNCTIONS, NOT REACHED ACROSS THE IMPORT.
#: `scripts/i18n_extract.py` resolves ``tr(NAME)`` only for a constant in the
#: module the call is written in, so ``tr(M._NOT_OPENED_NO_TAB)`` written in a
#: tab is invisible to it and would ship untranslated in silence — the blind
#: spot that has cost this project before. Same shape as `runs_phrase` below.
def not_opened_no_project() -> str:
    """{reason}: there is no manifest anywhere above the copy."""
    return tr(_NOT_OPENED_NO_PROJECT)


def not_opened_unreadable(error: str) -> str:
    """{reason}: the manifest is there and will not read."""
    return tr(_NOT_OPENED_UNREADABLE).format(error=error)


def not_opened_no_tab() -> str:
    """{reason}: there is no Create Chart tab to perform the open with."""
    return tr(_NOT_OPENED_NO_TAB)


# --- the typed name is a FOLDER, and not a project -------------------------
# APPROVED by Basti, 2026-09-02.
# Round 2, finding T1-D. `_ask_profile_name` decided "already a project" from
# `(working_dir / name).exists()`, which is true of any folder. So the one
# window the import door still opens for a plain folder arrived asserting, in
# red, that the folder is a project - about the folder whose NOT being one is
# the only reason that window opened at all. Driven, 2026-09-02:
# `shots/repro-folder-win03.png`.
#
# The consequence and the vocabulary follow M-IMPORT-REPLACE-CONFIRM, which
# Basti ruled on for the project case (2026-08-31); only the claim about what
# is there is different, because what is there is different.
M_IMPORT_FOLDER_EXISTS = _m(
    "M-IMPORT-FOLDER-EXISTS",
    "There is already a folder called \u201c{name}\u201d",
    "ChromIQ found it here:\n\n{folder}\n\nIt is not a ChromIQ project: "
    "there is no project.json in it. Nothing has been changed yet.\n\n"
    "\u2022  Type a different name, and ChromIQ starts a new project under "
    "that name instead. Nothing in the folder above is touched.\n\n"
    "\u2022  Replace it: everything in that folder is moved into its own "
    "\u201cold\u201d folder, with today\u2019s date on it, and a new and "
    "empty project of the same name is started in its place, with what you "
    "are importing in its first run. Nothing is deleted, and ChromIQ asks you "
    "to confirm before it does it.\n\n"
    "\u2022  Cancel: stops here and changes nothing.",
    approved=True)

#: The live line under the name box, which is the form this message actually
#: takes today: the window is the loader's own, with a name box and a line that
#: follows what is typed. It is a fragment of M-IMPORT-FOLDER-EXISTS above, and
#: the twin of the sentence used when the name really is a project.
_FOLDER_TAKEN_LINE = ("\u201c{name}\u201d is a folder you already have, and "
                      "it is not a ChromIQ project. Choose a different name, "
                      "or click \u201cReplace it\u201d.")

#: The line the same window shows when the name points at the folder the file
#: being imported is IN. Its twin, for a real project, says "That project";
#: this one exists because the twin was shown for a plain folder too.
_SELF_COLLISION_FOLDER = ("That folder holds the file you are importing, so "
                          "replacing it would take the file with it. Please "
                          "pick a different name.")

def folder_taken_line(name: str) -> str:
    """The live line under the name box for a folder that is not a project."""
    return tr(_FOLDER_TAKEN_LINE).format(name=name)


def self_collision_folder_line() -> str:
    """…and the line for when that folder holds the file being imported."""
    return tr(_SELF_COLLISION_FOLDER)


M_IMPORT_REPLACE_FOLDER_CONFIRM = _m(
    "M-IMPORT-REPLACE-FOLDER-CONFIRM",
    "Move everything in \u201c{name}\u201d aside?",
    "That folder is not a ChromIQ project, and everything in it is about to "
    "be moved into its own \u201cold\u201d folder, with today\u2019s date "
    "on it:\n\n{folder}\n\nNothing is deleted. That \u201cold\u201d "
    "folder stays where the files were, so you can open it at any time and "
    "take anything back out of it.\n\nAfter that, a new and completely "
    "empty ChromIQ project of the same name is started in the same place, and "
    "{subject} you are importing is put into its first run.",
    approved=True)

M_IMPORT_REPLACE_FOLDER_FAILED = _m(
    "M-IMPORT-REPLACE-FOLDER-FAILED",
    "That folder could not be moved aside",
    "ChromIQ was going to move everything in this folder into its own "
    "\u201cold\u201d folder before starting a project of the same name in "
    "its place, and it could not:\n\n{folder}\n\nNothing has been changed. "
    "Anything that had already been moved has been put back, and nothing has "
    "been imported.\n\nThe reason given was:\n{reason}\n\nThis usually "
    "means the folder is read-only, is on a disk or a share that is no longer "
    "available, or holds a file another program still has open. Close "
    "anything that might be using it and try again, or type a different name "
    "and leave that folder alone.",
    approved=True)

# --- PROPOSED: the file picked as a chart has no chart in it ---------------
#
# #182, 2026-09-11. "Open chart file" filters on *.ti2 and its list hides
# everything else, but a file dialog also has a name box, and a name typed,
# pasted or dragged into it is accepted whatever it ends in. The import copied
# whatever it was handed into a new project as that project's chart, so a page
# bitmap became `<project>.ti2` with `II` as its first two bytes: a project
# that cannot be printed, measured or built from, made in silence. The guard is
# `workflow.chart_import.holds_a_chart`; the WORDING waits here.
M_IMPORT_NOT_A_CHART = _m(
    "M-IMPORT-NOT-A-CHART",
    "That file holds no chart",
    "“{name}” was opened as a chart file, and there is no patch "
    "list inside it. A chart file, “.ti2”, holds the colours "
    "ChromIQ prints and measures. A page image, “.tif”, is a "
    "picture of the printed sheet and holds none of them.\n\nNothing has "
    "been created and nothing has been copied. Your file is where it was, "
    "unchanged.\n\nOpen the “.ti2” file that sits beside the page "
    "images instead. It carries the same name as they do, without the page "
    "number.",
    approved=True)

# --- PROPOSED: the two ways a spot-read session can be thrown away --------
#
# Knut, 2026-09-03, reporting the spacebar: the window had no guard on either
# route. Clear emptied the list with no question and no way back, and closing,
# rejecting or pressing Escape discarded a whole measuring session in silence.
# The mechanism is in `ui/dialogs/spot_read_dialog.py`; the WORDING waits here.
M_SPOT_CLEAR = _m(
    "M-SPOT-CLEAR",
    "Clear every reading in this list?",
    "This window holds {n} readings, and none of them are saved to a file "
    "yet.\n\nClearing empties the list. Nothing is written to disk and "
    "nothing is asked of the instrument, so if you clear by mistake press "
    "\u201cUndo clear\u201d and every reading comes straight back. The next "
    "reading you take replaces what Undo would restore.\n\nTo keep them, "
    "choose Cancel and use Save first.",
    body_one="This window holds one reading, and it is not saved to a file "
             "yet.\n\nClearing empties the list. Nothing is written to disk "
             "and nothing is asked of the instrument, so if you clear by "
             "mistake press \u201cUndo clear\u201d and the reading comes "
             "straight back. The next reading you take replaces what Undo "
             "would restore.\n\nTo keep it, choose Cancel and use Save "
             "first.",
    count_key="n",
    approved=False)

M_SPOT_UNSAVED = _m(
    "M-SPOT-UNSAVED",
    "These readings are not saved yet",
    "This window holds {n} readings that are not written to any file. They "
    "live in this window only, so closing it lets them go.\n\nSave writes "
    "them as a CSV and an ArgyllCMS .ti3 beside the run you are working on, "
    "and then the window closes. Discard closes the window and loses the "
    "readings. Cancel leaves the window open exactly as it is, with every "
    "reading still in the list.",
    body_one="This window holds one reading that is not written to any file. "
             "It lives in this window only, so closing it lets it go.\n\n"
             "Save writes it as a CSV and an ArgyllCMS .ti3 beside the run "
             "you are working on, and then the window closes. Discard closes "
             "the window and loses the reading. Cancel leaves the window open "
             "exactly as it is, with the reading still in the list.",
    count_key="n",
    approved=False)

# --- APPROVED: the CR30 stopped answering during a spot session ------------
#
# Basti, beta 16 (2026-10-09): the CR30 switched itself off during a session
# in Tools ▸ Read single patches, Stop did nothing, and once it was on again
# nothing happened until the window was closed. The session now pauses, keeps
# every reading, and asks. The mechanism is in `ui/dialogs/spot_read_dialog.py`
# and `workflow/cr30_spot_manager.py`. Wording approved by Basti, 2026-10-10,
# who also confirmed that one short press of the button switches a CR30 on.
M_SPOT_CR30_GONE = _m(
    "M-SPOT-CR30-GONE",
    "Your CR30 is not answering",
    "ChromIQ has lost the connection to your CR30. Usually it has switched "
    "itself off to save its battery, its USB cable has come out, or it is out "
    "of Bluetooth range.\n\nEvery reading in this window is kept.\n\n"
    "Switch the instrument on again (press its button once) or plug it back "
    "in, then choose \u201cReconnect\u201d. ChromIQ looks for it and you carry "
    "on reading. If it is still not there, this window comes back.\n\n"
    "To finish instead, choose \u201cStop session\u201d. Your readings stay in "
    "the list either way.",
    approved=True)

# --- APPROVED: presses from before Ready were not used in a spot session ---
#
# Beta 17 review (2026-10-09): a press of the CR30's button right after the
# spot window said Ready was thrown away, with only a log line to show for it.
# Fixed: the window now says Ready only once the read is really listening, and
# every press after that is taken. A press the instrument announced BEFORE
# Ready (typically while the calibration's last window, which says to press the
# button, was still open) is still not used; this is what the window's log
# says then, so nobody waits for a row that will not come. Our words;
# approved by Basti, 2026-10-10 (both variants).
M_SPOT_CR30_EARLY_PRESS = _m(
    "M-SPOT-CR30-EARLY-PRESS",
    "A reading taken before Ready was not used",
    "{n} readings were taken before this window was ready for them, so they "
    "were not used. Take the reading again.",
    body_one="One reading was taken before this window was ready for it, so "
             "it was not used. Take the reading again.",
    count_key="n",
    approved=True)

# --- PROPOSED: the reference file covers only part of the target -----------
#: Review 5, 2026-09-03, finding D. A reference file holding the first 48 rows
#: of the target's own correct 288-row reference builds a profile from a sixth
#: of the sheet with every indicator green: "Ready, 288 patches", the alignment
#: tick, and a colprof self-check of 0.185/0.076 -- BETTER than the correct
#: build's 0.620/0.098, because forty-eight points fit a matrix beautifully.
#: The 288 on screen is the .cht's count and nothing ever compared it with the
#: reference's own rows. Counting is the only thing that sees this, so it is
#: counted the moment the reference is picked, where the user can still fix it
#: by choosing another file, rather than after a read.
M_SCAN_REF_SHORT = _m(
    "M-SCAN-REF-SHORT",
    "This reference file covers only part of the target",
    "The reference file you picked gives colours for {covered} of the {total} "
    "patches on this target. ChromIQ can only use the patches the reference "
    "names, so the other {missing} would be read from your scan and then "
    "thrown away, and the profile would describe your scanner from a fraction "
    "of the sheet.\n\n"
    "Nothing later would show it. A profile built from fewer patches passes "
    "its own quality check more easily, not less.\n\n"
    "In the \u201c{ref_row}\u201d row, pick the full reference file that "
    "came with this target. That file lists every patch, so it has about as "
    "many rows as the target has patches.",
    approved=False,
    body_one=(
        "The reference file you picked gives colours for {covered} of the "
        "{total} patches on this target. ChromIQ can only use the patches the "
        "reference names, so the remaining one would be read from your scan "
        "and then thrown away.\n\n"
        "In the \u201c{ref_row}\u201d row, pick the full reference file that "
        "came with this target. That file lists every patch, so it has about "
        "as many rows as the target has patches."),
    count_key="missing")


# --- PROPOSED: what was read does not match the reference ------------------
#: Review 5, findings B2 and B4. `scan_reference_correlation` reads +0.94 to
#: +0.97 on every good read and -0.60 to +0.14 on every broken one, and the
#: window computed it only to decide whether to run a FURTHER check -- then
#: printed a green tick from the geometric ladder, which never looks at the
#: reference at all. An upside-down scan is the ordinary case: the patch block
#: maps onto itself, so every geometric check passes and every patch reads its
#: opposite number's colour.
M_SCAN_REF_DISAGREES = _m(
    "M-SCAN-REF-DISAGREES",
    "What was read does not match this reference",
    "ChromIQ compared how light each patch came out of your scan with how "
    "light the reference says that patch is. On a good scan the two run "
    "together closely. Here they hardly agree at all: {rho}, where a good "
    "read is above 0.9.\n\n"
    "That is what happens when the scan is upside down or a quarter turn out, "
    "or when the reference belongs to a different target from the one you "
    "scanned. A profile built from this read would be wrong, and nothing "
    "later would tell you.\n\n"
    "Check that the scan is the right way up, and that the file in the "
    "\u201c{ref_row}\u201d row is the one that came with this target.",
    approved=False)


# --- PROPOSED: the scan has run out of scale -------------------------------
#: Review 5, finding B3. A scan with every value lifted 55 % built a clean
#: profile in silence: 39.2 % of patches read at the top of the device scale,
#: rank agreement +0.943 (so the agreement check cannot see it), and colprof's
#: self-check passed. Measured across an exposure ladder, profcheck against the
#: read's own data goes 0.098 -> 0.286 -> 1.097 -> 5.967 average dE as the
#: clipped share goes 0 % -> 6 % -> 16 % -> 39 %. Clipping is the one scan
#: fault that cannot be profiled around: the values are gone, not shifted.
M_SCAN_CLIPPED = _m(
    "M-SCAN-CLIPPED",
    "Part of this scan has no colour left in it",
    "{pct} of the patches were read at the very end of the scan's brightness "
    "range, where there is nothing left to record. Their real colours are "
    "gone, not merely shifted, so ChromIQ cannot tell those patches apart and "
    "the profile would treat \u201cas far as this scanner goes\u201d as a "
    "measurement.\n\n"
    "Scan the target again with the automatic brightness and contrast turned "
    "off in your scanner software, so that no patch reaches either end of the "
    "scale.",
    approved=False)


# --- PROPOSED: the scan never reached the top of the scale -----------------
#: beta 8, B8-01. The opposite twin of M-SCAN-CLIPPED, and the one nothing could
#: see. Every other guard in this window is SCALE-INVARIANT and an exposure slip
#: is PURE SCALE: darkening Knut's own Wolf Faust sheet by 30 % leaves coverage
#: unchanged, rank agreement unchanged to three decimals (+0.9839 -> +0.9838)
#: and the clipped share unmoved to the patch, so the build is silent -- while
#: the profile it produces is 21.7 dE out against a correctly exposed read. At
#: x0.18 it is 177.9 dE out and still silent. colprof's self-check cannot see it
#: either: it is computed against the same dark data, and across the whole
#: ladder it moves only 1.93 -> 2.59 against limits of 30 and 12.
M_SCAN_DARK = _m(
    "M-SCAN-DARK",
    "This scan came out darker than it should be",
    "The white patches on this target came out at {pct} of your "
    "scanner\u2019s brightness range. On a scan exposed for this target they "
    "sit just under the top of that range, and getting them there is what the "
    "brightness or exposure setting in your scanning software is for.\n\n"
    "Nothing later in ChromIQ would tell you. A dark scan is not harder to "
    "describe than a bright one: it passes every other check in this window, "
    "and the quality number you are shown at the end of the build is worked "
    "out from this same dark reading, so it comes out looking just as good. "
    "What changes is the profile itself \u2014 it would describe your scanner "
    "in a state you are unlikely to set up again, so it would not match your "
    "everyday scans.\n\n"
    "Scan the target again with the brightness or exposure turned back up in "
    "your scanner\u2019s own software \u2014 not in ChromIQ, which never "
    "changes your scan \u2014 so that the white patches sit just below the "
    "top of the scale without touching it.\n\n"
    "One exception: if you are scanning a transparency or a negative, a low "
    "reading here can be normal for that medium. Check the exposure before you "
    "go on, but you may find nothing is wrong.",
    approved=False)


# --- PROPOSED: the reference gives too few colours to fit a profile to -----
#: beta 8, B8-03, the pre-build half. colprof's self-check is measured against
#: the very rows it was fitted to, so it is SMALLEST exactly when there is least
#: to fit. A reference whose every SAMPLE_ID reads "A1" leaves one row and
#: scores peak 0.007339 / avg 0.007339 -- a perfect mark, and the log ends
#: "Install it as your scanner's input profile". A reference whose every value
#: reads "0.00" leaves 288 rows of ONE colour, sends colprof's Powell fit to
#: "residual error = nan" and lands a profile whose white point is nan nan nan.
#: An error FLOOR cannot separate these: the app's own ColorChecker demo build
#: scores avg 0.059311, only eight times the degenerate case. Counting the
#: distinct colours can -- 1 against 21 for the smallest target anybody ships.
M_SCAN_FIT_UNSUPPORTED = _m(
    "M-SCAN-FIT-UNSUPPORTED",
    "This reference file describes too few colours to build a profile from",
    "The reference file names only {support} different colours for this "
    "target. A profile describes how your scanner answers to colour, and that "
    "cannot be worked out from so few.\n\n"
    "ChromIQ can still build one, and it would pass its own quality check "
    "easily \u2014 when there is almost nothing to match against, almost any "
    "answer matches. The quality number you are shown at the end of the build "
    "would look better than a correct profile\u2019s, and it would mean "
    "nothing at all.\n\n"
    "In the \u201c{ref_row}\u201d row, choose the reference file that came "
    "with your target. It lists a different colour for every patch on the "
    "sheet.",
    approved=False,
    body_one=(
        "The reference file names the same colour for every patch it lists. A "
        "profile describes how your scanner answers to colour, and that cannot "
        "be worked out from a single one.\n\n"
        "ChromIQ can still build one, and it would pass its own quality check "
        "perfectly \u2014 when there is nothing to match against, any answer "
        "matches. The quality number you are shown at the end of the build "
        "would look better than a correct profile\u2019s, and it would mean "
        "nothing at all.\n\n"
        "In the \u201c{ref_row}\u201d row, choose the reference file that "
        "came with your target. It lists a different colour for every patch on "
        "the sheet."),
    count_key="support")


# --- PROPOSED: colprof's own quality check produced no number --------------
#: beta 8, B8-03, the post-build half. `_PROFCHECK_RE` matched only digits and
#: dots, so colprof's "avg err = nan" line did not match at all, `found` came
#: back empty and the verdict returned on its "if not found" line -- the one
#: case where the check had the most to say was the one case it could not read.
#: Even parsed, `0.0 <= 30.0` would have short-circuited the "or". The build
#: then wrote "[OK] Scanner profile saved" and "Install it as your scanner's
#: input profile" over a profile whose white point is nan nan nan.
M_SCAN_SELFCHECK_UNUSABLE = _m(
    "M-SCAN-SELFCHECK-UNUSABLE",
    "This profile could not be checked",
    "After building a profile, ChromIQ asks how closely it matches the colours "
    "it was built from, and shows you the answer as a quality number. This "
    "time no number came back at all \u2014 the answer was "
    "\u201c{raw}\u201d, which is what happens when the measurements handed "
    "over had nothing in them to match against.\n\n"
    "So the file on disk is a profile in name only, and nothing has confirmed "
    "that it describes your scanner. Treat it as unchecked: read the warnings "
    "above, put right what they name, and build again before you use it for "
    "anything.",
    approved=False)


# --- PROPOSED: where the profile this build replaced went ------------------
#: Review 5, finding B5. Building twice wrote over the first profile in place:
#: no copy, no question, and not a word in the log -- and it may be one the
#: user has installed and been working against. The app's habit everywhere else
#: is to archive, so the build now moves the previous profile and measurement
#: into old/<date>/ first. That much needs no new wording. Saying WHERE does,
#: and the adversarial round of 2026-09-02 already established that moving
#: something and naming the folder nowhere is its own fault -- see
#: M-CAL-ARCHIVED-HERE, whose shape this follows deliberately.
M_SCAN_PROFILE_ARCHIVED = _m(
    "M-SCAN-PROFILE-ARCHIVED",
    "The profile that was here has moved to this folder, and nothing in it "
    "was deleted:",
    "{folder}",
    approved=False)


# --- PROPOSED: the scanner white-point default moved, and said so ----------
#: 2026-09-05, Basti. The white-point handling a scanner/camera profile is
#: built with moved from "Map chart white to white" to "Scale white to a
#: perfect white surface" (colprof `-u -R`), and he ruled that EXISTING
#: remembered settings adopt it too: *"our user base is not very big at the
#: moment so i want the better default"*. That is the right call and it is also
#: a change of meaning nothing else in the app would explain — somebody who
#: re-profiles a scanner they have profiled before gets a visibly different
#: profile. So the migration says so, once, the first time the window opens
#: after it has happened.
#:
#: It is announced in the LOG, not a window: §M's rule is that wording which
#: has not been reviewed speaks through the log until it is approved, and
#: nobody asked for a window here.
M_SCAN_WP_DEFAULT = _m(
    "M-SCAN-WP-DEFAULT",
    "The white point setting for new scanner profiles has changed",
    "ChromIQ used to build scanner and camera profiles so that the white "
    "patch of your test chart became pure white. It now scales white to a "
    "perfect white surface instead — the entry “Scale white to a perfect "
    "white surface (-u -R)” under Advanced… ▸ White Point ▸ White point "
    "handling. Your remembered settings for this window have been moved to "
    "it, which is why you are reading this.\n\n"
    "Why it moved. Under the old setting, anything you scanned that was "
    "lighter than your chart's own white board came out as flat white with "
    "no detail left in it, and no amount of editing afterwards could bring "
    "that detail back. A test chart's white board is not very white: on the "
    "scan this was measured from it is 84 % as bright as a perfect white "
    "surface, so that board, a brighter paper, a very bright paper and a "
    "perfect white surface all came out as exactly the same white. The new "
    "setting keeps them apart. It is just as accurate as the old one, and it "
    "keeps whites just as neutral.\n\n"
    "What this does not change. Every profile you have already built is a "
    "file on disk and is untouched. So is every measurement, every chart and "
    "every project. Nothing has been rebuilt, converted, moved or deleted, "
    "and no profile changes unless you build it again.\n\n"
    "What you will notice. A profile you build from now on makes scans open a "
    "little darker — a white board lands at about 93 out of 100 in lightness "
    "rather than at 100 — so a scan wants one levels or curves step to "
    "finish. Nothing has been lost by that: the highlight detail that used to "
    "be flattened is now there for you to work with.\n\n"
    "If you preferred the old behaviour, it has not gone anywhere. Open "
    "Advanced…, and under White Point set “White point handling” back to "
    "“Map chart white to white”. That is exactly what ChromIQ did before. "
    "Press “Save as Defaults” and it will stay that way.",
    approved=False)


# --- PROPOSED: the window said nothing at all when a scan was loaded -------
#: beta 8, B8-16 (Agent B, reproduced by Agent I). Loading a scan under the
#: wrong Target type produced an EMPTY log, a live Run button and a 288-cell
#: mesh drawn across 24 patches. Pressing Run does fire two guards, so it is
#: not a silent wrong profile -- but for as long as the user cares to look the
#: window is authoritative about a placement that cannot be right, and it
#: invites them straight past it.
#:
#: The honest fix is not a mismatch detector: at load time the app has not read
#: anything and cannot know. It is to stop being silent -- to say what was
#: loaded, what it will be read AS, and that nothing has been checked yet.
M_SCAN_LOADED = _m(
    "M-SCAN-LOADED",
    "Scan loaded",
    "{file} \u2014 {w} \u00d7 {h} pixels. It will be read as \u201c{target}\u201d, "
    "which has {n} patches.\n"
    "Nothing has been checked yet. Place the grid over the patch area, then "
    "press Check alignment \u2014 that reads the scan and says whether the grid "
    "is really on the patches.",
    approved=False)


# --- PROPOSED: a diagnostic image offered as a scan ------------------------
#: beta 8, B8-15. Knut did this in his own beta.7 log at 15:30: he picked
#: `diagnosticReadLSTarget01.tif` -- a scanin -dipn OUTPUT -- as the scan, the
#: app took it without a word, and the alignment check then reported a
#: misplacement that was not real ("sample boxes sit on patch edges, worst
#: 73.80 %") about a read that had been fine. The picture is recognised from
#: its pixels, not its name, because his file was written by his own scanin
#: command (`workflow/scan_diagnostic_image.py` carries the measurements).
M_SCAN_DIAGNOSTIC = _m(
    "M-SCAN-DIAGNOSTIC",
    "This looks like a diagnostic image, not a scan",
    "ChromIQ writes one of these after every read: your scan turned grey, with "
    "the colour painted back only where ArgyllCMS sampled it, and the patch "
    "names drawn on top. It is a picture of a read, not something that can be "
    "read again.\n\n"
    "The grid cannot line up on it, and the alignment check will report a "
    "misplacement that is not real. Load the original scan of your target "
    "instead \u2014 diagnostic images live in the \u201ccache\u201d folder "
    "beside it and are safe to delete.",
    approved=False)


# --- PROPOSED: an averaging slot that was left empty -----------------------
#: beta 8, B8-32 (sweep finding F-7). Press "＋ Add another scan to average",
#: stop there, and the window shows "Scan 1 / Scan 2" while `_page_ready` asks
#: only `any(...)`: the Run button stays live, the build reads ONE scan, runs
#: no averaging step, and ends "[OK] Scanner profile saved" as though one scan
#: had been asked for. Driven end to end in the real window (sweep check J32):
#: 2 slots, 1 file, exactly 1 scanin call, and nothing said anywhere.
#:
#: It says so rather than refusing, which is this window's rule elsewhere
#: (B8-15): what happens is a legitimate build from fewer scans, not a wrong
#: profile, and a Run button that greys out with no reason attached is a new
#: silence rather than the end of one.
#:
#: Every count in it is a bare number in a sentence that does not inflect
#: around it, so there is one message rather than a singular and a plural.
M_SCAN_SHOT_EMPTY = _m(
    "M-SCAN-SHOT-EMPTY",
    "An empty scan slot was skipped",
    "This page has {slots} scan slots, and a file has been picked for "
    "{filled} of them. An empty slot is not read and nothing is averaged with "
    "it, so this build uses only the scans that are there.\n"
    "If you meant to average repeated scans of this page, pick a file for "
    "each empty slot and build again. If a slot was added by mistake, "
    "\u201cRemove this scan\u201d takes it away.",
    approved=False)


# --- PROPOSED: the scan a target-type change throws away -------------------
#: beta 8, B8-32 (sweep finding F-9). Load a scan, place the grid, change
#: "Target type": the scan, its four corners and every other shot on the page
#: are dropped by `_set_std_targets` -> `_reset_shots`, and the log — which is
#: cleared in the same block — said nothing about any of it.
#:
#: The discard itself is right and is not being changed: a different target has
#: a different grid, so a placement made on the old one is meaningless on the
#: new one, and a demo scan belongs to the target that generated it. What was
#: missing is the sentence saying it happened.
M_SCAN_TARGET_CHANGED = _m(
    "M-SCAN-TARGET-CHANGED",
    "Target type changed \u2014 the loaded scan was cleared",
    "A scan is read through the target\u2019s own recognition file, and a "
    "different target has a different grid, so a placement made on the old one "
    "would not mean anything on this one. The scan that was loaded, its four "
    "corners and any further scans on this page have been dropped.\n"
    "Nothing on disk was touched. Pick the scan again \u2014 or press "
    "\u201cTry with a demo scan\u201d \u2014 for the target now selected.",
    approved=False)


# --- Auto align, in the scanner window's preview ---------------------------
# APPROVED by Basti, 2026-09-03.
#
# Auto align hands the scan to ArgyllCMS's own chart recogniser, checks the
# answer against this chart's reference, and either places the grid on it or
# changes nothing (`workflow/scan_auto_align.py`). The module answers with a
# machine-readable REASON -- "below-floor", "no-usable-candidate" and four
# more -- which is what the log file and the tests want, and is exactly what a
# user must never be shown. The first implementation printed it in brackets in
# the middle of the sentence. These messages are those reasons in the user's
# own terms, and `scan_align_refusal` below is the only place the two meet, so
# a reason with no message of its own falls back to words rather than reaching
# a window as a code (`tests/test_scan_auto_align.py` proves it cannot).
#
# All six refusals open with the same headline, because after a refusal the
# first thing the user needs to know is that they have lost nothing: the four
# corners they placed are untouched, and the button they pressed was safe to
# press.
_ALIGN_KEPT = "Auto align left your corners exactly where they are"

#: {ref_row} and {chart_row} name the row on screen the user should look at,
#: and there are three of them: a standard target is chosen in "Target type"
#: with its colours in "Target reference data", while a ChromIQ chart takes
#: both from one picker -- "Measured chart (.ti3)", or "Chart you printed
#: (.ti2)" in printer mode. The window fills them in from the labels it is
#: actually showing, so a message never names a row that is hidden.
M_SCAN_ALIGN_AMBIGUOUS = _m(
    "M-SCAN-ALIGN-AMBIGUOUS",
    _ALIGN_KEPT,
    "This chart's patches look the same whichever way round it is turned, so "
    "ChromIQ cannot work out which way your scan was made. If you know it "
    "needs turning, use the “⟳ Rotate 90°” button below "
    "the preview. Otherwise drag the four corners onto the chart yourself, "
    "which always works.")

M_SCAN_ALIGN_NO_MATCH = _m(
    "M-SCAN-ALIGN-NO-MATCH",
    _ALIGN_KEPT,
    "It found the chart, but what your scan shows does not match the "
    "reference closely enough to rely on. That usually means the reference "
    "file belongs to a different target, or the scan is of a different chart. "
    "Check the file in the “{ref_row}” row above and try again.")

M_SCAN_ALIGN_NOT_FOUND = _m(
    "M-SCAN-ALIGN-NOT-FOUND",
    _ALIGN_KEPT,
    "ChromIQ could not find this chart anywhere in the picture. That usually "
    "happens when the picture shows a lot more than the chart, or when one "
    "edge of the chart is missing. Drag the four corners roughly around the "
    "chart and press Auto align again: it will then search only inside them.")

#: THE SAME REFUSAL, WHEN THE CHART IS A HONEYCOMB AND THE ADVICE CANNOT WORK.
#:
#: Measured on screen 2026-09-11 on Knut's own CR30 hexagonal chart, from three
#: different starting placements: the search returns "not recognised" with ZERO
#: candidates every time, while the two stages after it work on a honeycomb and
#: separate a right placement from a wrong one by 0.969 against 0.514. So the
#: refusal itself is right and nothing is moved. What was wrong is that the
#: user was sent to drag the corners roughly around the chart and press the
#: button again, which narrows the search -- and on a honeycomb a narrower
#: search finds nothing either, because the step that fails is scanin's own
#: recogniser and it looks for the straight horizontal patch edges a grid of
#: rectangles has. A hexagon has none. Same ending, same safety, an instruction
#: the user can actually follow.
M_SCAN_ALIGN_NOT_FOUND_HEX = _m(
    "M-SCAN-ALIGN-NOT-FOUND-HEX",
    _ALIGN_KEPT,
    "Auto align cannot find a hexagonal chart. The search looks for the "
    "straight edges of a grid of rectangles, and a honeycomb has none, so "
    "pressing the button again will not help however the corners are placed. "
    "Drag the four corners onto the chart yourself: put each one on the "
    "outermost patch of its corner. Everything else in this window works "
    "normally on a honeycomb, including “Check alignment”, which will tell "
    "you whether what you placed is reading the right patches.",
    approved=False)

M_SCAN_ALIGN_NO_FIT = _m(
    "M-SCAN-ALIGN-NO-FIT",
    _ALIGN_KEPT,
    "ChromIQ found something chart-shaped in the picture, but no way of "
    "fitting this target's patches onto it. Check that the chart chosen in "
    "the “{chart_row}” row above is the one you actually scanned.")

M_SCAN_ALIGN_NO_GEOMETRY = _m(
    "M-SCAN-ALIGN-NO-GEOMETRY",
    _ALIGN_KEPT,
    "The chart definition for this target does not record where its patches "
    "sit, and that is what Auto align needs to work. Place the four corners "
    "yourself; everything else in this window works normally.")

#: REVISED for B8-42, so back in the review queue with the headline unchanged.
#: It used to be the recogniser's ending alone -- "it searched, and your own
#: placement is already the closer match" -- and the merged button reaches it
#: only when BOTH halves declined: the search had nothing better and the
#: reshaping found nothing worth moving the corners for. The second half of the
#: body is the part that matters and is new: this ending is a statement about
#: what was SEARCHED, never a statement that the placement is right, and a grid
#: exactly one patch out is indistinguishable from the right answer to
#: everything measured inside the sample boxes. So it names the one check in
#: this window that can tell the difference, which the old wording did not.
M_SCAN_ALIGN_NO_BETTER = _m(
    "M-SCAN-ALIGN-NO-BETTER",
    _ALIGN_KEPT,
    "ChromIQ searched the picture for the chart, and then looked around the "
    "four corners you placed for a better place to put the grid. Neither "
    "found one worth moving them for \u2014 what you have is already the "
    "closest match it can see.\n"
    "That is not the same as saying the grid is on the right patches: a grid a "
    "whole patch out reads every patch as its neighbour and looks just as even. "
    "Press \u201cCheck alignment\u201d below \u2014 that reads the scan and "
    "can tell the difference.",
    approved=False)

M_SCAN_ALIGN_DONE = _m(
    "M-SCAN-ALIGN-DONE",
    "Auto align put the grid on the patches",
    "What the grid reads now agrees with this chart's own reference to {rho}, "
    "on a scale where 1.00 is a perfect match and anything below 0.80 is "
    "refused. Press “Check alignment” below to look at the read "
    "before you build anything. Nothing else has changed, and you can still "
    "drag any corner by hand.")

M_SCAN_ALIGN_NO_INPUT = _m(
    "M-SCAN-ALIGN-NO-INPUT",
    "Auto align has nothing to look at yet",
    "Load a scan for this page and choose the chart it was made from, then "
    "press Auto align again.")

# --- PROPOSED: the photograph path (beta 8, agent L) -----------------------
#: A camera writes JPEG and ``scanin`` reads TIFF and nothing else, so a
#: photograph picked through the file dialog's "All files" entry decoded
#: happily into the preview, aligned happily under the marquee, and then made
#: Argyll exit with `Not a TIFF or MDI file, bad magic number` at the very end
#: of the job. ChromIQ now converts it and says so, because a file the app
#: substituted for the one that was chosen must never be a silent substitution.
M_SCAN_CONVERTED = _m(
    "M-SCAN-CONVERTED",
    "This photograph was converted for reading",
    "ArgyllCMS reads TIFF images only, and {file} is not one. ChromIQ made a "
    "TIFF copy of it and will read that; your own file is not changed. The "
    "copy holds the same pixels \u2014 nothing has been sharpened, resized or "
    "colour-managed.",
    approved=False)

#: Measured on Knut's own Wolf Faust scan through a bow x camera x lens matrix
#: of 48 conditions: a 5.5 % bow alone costs nothing, a 15-degree compound tilt
#: alone costs nothing, and the two TOGETHER put 102 patches over 1 dE00 and 44
#: over 3 -- read at the best quad four corners can express. The same quad
#: moved a little, to balance the residual across the block instead of pinning
#: its ends, reads it with none over 1 dE00.
#: THE ONE ENDING WHERE THE REFINEMENT'S REASON IS ALL THERE IS TO SAY.
#: Reached when the recogniser had no diagnosis of its own -- it answered only
#: "your own placement scored as well as mine" -- and the refinement then found
#: its best placement further away than
#: :data:`workflow.photo_fit.CLAMP_PITCHES` allows it to move. Measured over
#: 290 starting placements, 2 of them end here.
#:
#: The arithmetic in the first version of this was wrong twice over: it said
#: "more than half a patch" of a limit that is three quarters, and "half a
#: patch further and the grid would be reading the neighbouring patch" of a
#: distance that is a quarter. A sentence with a number in it is a sentence
#: somebody will check.
M_SCAN_FIT_TOO_FAR = _m(
    "M-SCAN-FIT-TOO-FAR",
    _ALIGN_KEPT,
    "ChromIQ looked around the four corners you placed for a better place to "
    "put the grid, and the best one it found is further than three quarters of "
    "a patch away from them. That is as far as it will move your corners by "
    "itself: one whole patch and the grid would be reading the neighbouring "
    "squares, which looks just as convincing and is completely wrong.\n"
    "Drag the four corners onto the chart\u2019s patch area, as close to the "
    "real patches as you can get them, and press Auto align again.",
    approved=False)


M_SCAN_ALIGN_NOT_SEATED = _m(
    "M-SCAN-ALIGN-NOT-SEATED",
    _ALIGN_KEPT,
    "ChromIQ worked out where the grid would have to go, then looked at the "
    "picture once more to check it \u2014 and the patches are not where that "
    "placement puts them. Towards one edge of the sheet the grid would read "
    "part of the neighbouring patch, and a profile built from that is wrong "
    "without looking wrong. Nothing has been moved.\n\n"
    "This is what a photograph taken at a slight angle does \u2014 the end of "
    "the sheet further from the camera comes out smaller, so no single shape "
    "fits both ends of it. A flatbed scan does not have the problem at all.\n\n"
    "Scan the sheet, or photograph it square-on with the camera above the "
    "middle of it \u2014 or drag the four corners onto the chart yourself, "
    "which always works and is what the grid is for.",
    approved=False)


# --- PROPOSED (#182, Knut 2026-09-11): the grid IS placed, and was not
# trusted --------------------------------------------------------------------
#
# He was asked whether Auto align, when it cannot place the grid well enough to
# trust, should leave the corners alone and say so, or place its best attempt
# and tell the user to check it. *"place its best attempt and tell user to
# check it."*
#
# So the two endings that HAVE a best attempt -- the seating check refused it,
# or it does not agree with the chart's reference -- stop being refusals. The
# grid moves, the one-press undo is armed exactly as it is after a success, and
# these two messages are what is said instead of `_ALIGN_KEPT`. The other
# endings keep their refusals: there is nothing to place in any of them, and a
# window that claimed to have placed something would be lying.
#
# The headline is shared, because from the user's side there is one state: the
# grid moved and nobody is vouching for it. It deliberately does NOT open with
# the word "done" -- the approved M-SCAN-ALIGN-DONE owns that, and these two
# must not read like it at a glance.
_ALIGN_UNCHECKED = "Auto align placed the grid and could not confirm it"

M_SCAN_ALIGN_PLACED_UNCHECKED = _m(
    "M-SCAN-ALIGN-PLACED-UNCHECKED",
    _ALIGN_UNCHECKED,
    "ChromIQ found the chart and has put the grid on its best reading of it, "
    "so you can see what it found. What the grid reads there does not agree "
    "with this chart's own reference closely enough to rely on, which usually "
    "means the reference file belongs to a different target, or the scan is of "
    "a different chart.\n\n"
    "Check it before you build anything. Look at the file in the "
    "\u201c{ref_row}\u201d row above, press \u201cCheck alignment\u201d "
    "below to read the scan and see which patches it is really taking, and "
    "drag any corner by hand. \u201cUndo auto align\u201d puts your own "
    "corners back.",
    approved=False)

M_SCAN_ALIGN_PLACED_NOT_SEATED = _m(
    "M-SCAN-ALIGN-PLACED-NOT-SEATED",
    _ALIGN_UNCHECKED,
    "ChromIQ worked out where the grid would have to go and has put it there, "
    "then looked at the picture once more to check it, and the patches are not "
    "where that placement puts them. Towards one edge of the sheet the grid "
    "reads part of the neighbouring patch, and a profile built from that is "
    "wrong without looking wrong.\n\n"
    "This is what a photograph taken at a slight angle does: the end of the "
    "sheet further from the camera comes out smaller, so no single shape fits "
    "both ends of it. A flatbed scan does not have the problem at all.\n\n"
    "Check it before you build anything. Press \u201cCheck alignment\u201d "
    "below, and drag the corners that are off onto the patches by hand. "
    "\u201cUndo auto align\u201d puts your own corners back.",
    approved=False)


#: The two endings that now PLACE rather than refuse, and what each is told in.
#: `scan_align_refusal` still answers for every ending with nothing to place --
#: including these two, which can still be reached with no candidate when the
#: search itself ended on them and the user had placed no grid to refine from.
SCAN_ALIGN_UNCHECKED = {
    "below-floor": M_SCAN_ALIGN_PLACED_UNCHECKED,
    "not-seated": M_SCAN_ALIGN_PLACED_NOT_SEATED,
}


def scan_align_unchecked(reason: str) -> Message:
    """The message for a placement that was applied without being vouched for.

    An ending with no message of its own falls back to the reference wording
    rather than putting its name on screen, exactly as
    :func:`scan_align_refusal` does -- adding an ending and forgetting the
    message must cost a slightly wrong sentence, never a code in front of a
    user.
    """
    return SCAN_ALIGN_UNCHECKED.get(reason, M_SCAN_ALIGN_PLACED_UNCHECKED)


#: Auto align's internal refusal reasons, and the message each one is told in.
#: The reasons stay machine-readable -- they go to the log file and the tests
#: read them -- and this map is the ONLY place they turn into words.
SCAN_ALIGN_REFUSALS = {
    "ambiguous-orientation": M_SCAN_ALIGN_AMBIGUOUS,
    "below-floor": M_SCAN_ALIGN_NO_MATCH,
    "not-seated": M_SCAN_ALIGN_NOT_SEATED,
    "not-recognised": M_SCAN_ALIGN_NOT_FOUND,
    "no-usable-candidate": M_SCAN_ALIGN_NO_FIT,
    "no-chart-geometry": M_SCAN_ALIGN_NO_GEOMETRY,
    "no-better": M_SCAN_ALIGN_NO_BETTER,
    # ...and the one ending that belongs to the second half of the operation
    # rather than the first. It is in the same map, and answered by the same
    # function, because from the user's side there is one button and one
    # ending: nothing moved, and here is what to do about it.
    "too-far": M_SCAN_FIT_TOO_FAR,
}


def scan_align_refusal(reason: str, *, hexagonal: bool = False) -> Message:
    """The message for an Auto align refusal, by its internal reason.

    A reason with no message of its own gets the "could not find this chart"
    wording rather than putting its own name on screen -- so adding a reason
    to :mod:`workflow.scan_auto_align` and forgetting the message costs a
    slightly wrong sentence, never a code in front of a user. The test that
    pins the set of reasons is what stops it staying wrong.

    *hexagonal* says the chart on screen is a honeycomb, which changes ONE
    ending: "not recognised" then has a cause the generic advice cannot
    address, so it gets its own wording. It is a property of the CHART and not
    of the search, which is why the caller supplies it and the ladder's set of
    endings is untouched; and it stays here, because this function is the only
    place an ending turns into words.
    """
    if hexagonal and reason == "not-recognised":
        return M_SCAN_ALIGN_NOT_FOUND_HEX
    return SCAN_ALIGN_REFUSALS.get(reason, M_SCAN_ALIGN_NOT_FOUND)


# --- PROPOSED (#182, Knut D25): the chart cannot supply a row the limit set
# limits — Measurement Report window, the strip under "Judged against", and
# repeated in the report text -------------------------------------------------
M_REPORT_CHART_MISMATCH = _m(
    "M-REPORT-CHART-MISMATCH",
    "Some limits cannot be checked on this chart",
    "The limit set {set} puts a limit on values this chart cannot supply, so "
    "these rows read N-A (not applicable):\n{rows}\n\n"
    "A row that was not computed says nothing about the printer. Each reason "
    "above names what that row needs: most want patches added to the chart in "
    "Create Chart (for the grey balance: “Neutral grey ramp” with 16 steps), "
    "and the control strip wants the chart to declare one. Make the change, "
    "print the chart again and measure it.",
    approved=True)

# --- PROPOSED (#182, 2026-09-24, beta 40 challenge B): the same strip when no
# row it lists is a grey row a device grey ramp answers -----------------------
#
# The closing above names a lever for the grey balance, "Neutral grey ramp"
# with 16 steps, and it was printed whatever the list held: under a list with
# no grey row in it, and on a FROM PROFILE GAMUT chart, whose grey steps are
# its neutral aims and whose lever is a larger chart, never grey steps
# (§26.5 of `measurement_report_limits.md`). Same headline, same {set} and
# {rows}; the closing names no grey lever.
M_REPORT_CHART_MISMATCH_NO_GREY = _m(
    "M-REPORT-CHART-MISMATCH-NO-GREY",
    "Some limits cannot be checked on this chart",
    "The limit set {set} puts a limit on values this chart cannot supply, so "
    "these rows read N-A (not applicable):\n{rows}\n\n"
    "A row that was not computed says nothing about the printer. Each reason "
    "above names what that row needs: most want patches added to the chart in "
    "Create Chart, and the control strip wants the chart to declare one. Make "
    "the change, print the chart again and measure it.",
    approved=False)

# --- PROPOSED (#182, 2026-09-23): the same strip when only evenness is short --
#
# Round B before beta 37, M7: under a list holding only the two evenness rows
# the closing above sent the reader to add patches in Create Chart "(for the
# grey balance: “Neutral grey ramp” with 16 steps)". Evenness is judged over
# nine areas of ONE page, so what those rows lack is strips and rows on a
# page, which is the chart's layout. Same headline, same {set} and {rows}.
M_REPORT_CHART_MISMATCH_LAYOUT = _m(
    "M-REPORT-CHART-MISMATCH-LAYOUT",
    "Some limits cannot be checked on this chart",
    "The limit set {set} puts a limit on values this chart cannot supply, so "
    "these rows read N-A (not applicable):\n{rows}\n\n"
    "A row that was not computed says nothing about the printer. Evenness is "
    "judged over nine areas of one page, so these rows want a chart laid out "
    "with more strips and more rows on a page, and with patches that cover "
    "most of the page. Make the change, print the chart again and measure it.",
    approved=True)

# M-REPORT-NOT-FOR-CALIBRATION (#182 K26, beta 38) is WITHDRAWN, never having
# been approved: Knut retracted the ruling it spoke for (5794078008, "The run
# type set to calibration should be able to make a report after all"), so the
# window has no red line to show under Run type Calibration (beta 39).

# --- PROPOSED (#182, 2026-09-16): deleting one saved report ------------------
#
# The design authority asked for this before a non-beta: *"the selection and
# deletion of reports with a selector input box is needed and should be made
# first"*. Nothing in this model governs deleting a report, and §5 of
# `measurement_report_limits.md` governs only the archive-then-recalculate
# rule, which is about rewriting a report rather than removing one. So the
# window says exactly what goes and what stays, and the WORDING waits here.
# REVISED 2026-09-18 for Knut's L.7, which says what the button DOES: *"which
# then creates a dated report folder in the old/ folder where the files for
# that report is moved to."* The wording it replaces described an unlink and
# ended "ChromIQ cannot undo this", which was true of the old button and is
# false of this one. It also spoke of one FILE, and an entry in the list is now
# one DOCUMENT, which may be one file per measurement it covers (B8-383). Still
# PROPOSED: neither wording has been approved.
# REVISED 2026-09-23 for Knut's K25 answer (5789263863, Q5): the one-file body
# said "the measurement it describes" about a report of several dates, because
# since K23 a report of several measurements is ONE document file. {n} counts
# FILES, not measurements, so it cannot choose the word; his own words do:
# *"You could say 'the measurement(s) it describes', to make it simple."*
M_REPORT_DELETE = _m(
    "M-REPORT-DELETE",
    "Delete this report from the list?",
    "This report is taken out of the list of generated reports:\n\n{what}\n\n"
    "Its {n} files are moved here:\n\n{where}\n\n"
    "Nothing is destroyed. The files stay on your disk in that folder, and "
    "the measurement(s) it describes are not touched.",
    body_one=(
        "This report is taken out of the list of generated reports:\n\n"
        "{what}\n\n"
        "Its file is moved here:\n\n{where}\n\n"
        "Nothing is destroyed. The file stays on your disk in that folder, "
        "and the measurement(s) it describes are not touched."),
    count_key="n",
    approved=True)

# --- PROPOSED (#182, Knut 2026-09-19): Generate report with a selected report
# whose settings have been changed --------------------------------------------
#
# Knut wrote the text himself and ended it *"(or similar)"*, so it is his
# wording and it still goes through §M-PROPOSED: *"When Generate Report is then
# clicked, the user must be shown a popup message with following text (or
# similar): Settings were modified for the selected report. / What do you want
# to do? / 1. Update selected report with selected settings. / 2. Create new
# report with selected settings. / 3. Cancel. The window must then have three
# buttons: Update, Create New and Cancel."*
#
# THE NUMBERED LINES STAY IN THE BODY even though the buttons carry the same
# three words, because that is what he specified and because the numbered list
# is what says which button does what: "Update" alone does not say that the
# SELECTED report is what gets updated.
M_REPORT_UPDATE_OR_NEW = _m(
    "M-REPORT-UPDATE-OR-NEW",
    # HIS SENTENCE WITHOUT ITS FULL STOP: the house rule is that a
    # headline is not a sentence (`tests/test_message_catalogue.py`),
    # and he ended the whole block "(or similar)". Nothing else moved.
    "Settings were modified for the selected report",
    # K32 (Knut, #182 5813851807, beta 41): Create New comes FIRST, in the
    # list as on the buttons, because it is the safe answer and the default.
    "What do you want to do?\n\n"
    "1. Create new report with selected settings.\n"
    "2. Update selected report with selected settings.\n"
    "3. Cancel",
    approved=True)

# --- PROPOSED (#182, K4 of Knut's beta-34 batch, 2026-09-22) -----------------
# Generate report pressed with a saved report selected and NOTHING changed. It
# wrote a new report and asked nothing (four presses in nine seconds, 44 files,
# in his log), because the question above is asked only when a setting moved.
# His sentence for that one is a statement of fact ("Settings were modified"),
# so the unchanged case cannot borrow it; the three buttons are the same.
M_REPORT_UNCHANGED_UPDATE_OR_NEW = _m(
    "M-REPORT-UNCHANGED-UPDATE-OR-NEW",
    "Nothing was changed for the selected report",
    # K32: the same order as M-REPORT-UPDATE-OR-NEW's, Create New first.
    "What do you want to do?\n\n"
    "1. Create new report with the same settings.\n"
    "2. Update selected report, worked out again by this version of ChromIQ.\n"
    "3. Cancel",
    approved=True)

# --- PROPOSED (#182 K39-2, Knut 5831246553): Generate report pressed with a
# saved report selected and NOTHING changed, where this version works that
# report out differently from the version that saved it, so an Update changes
# its results (B8-1093: "Nothing was changed" was followed by FAIL turning
# into PASS). Asked of "Should that question have its own wording for this
# case, for example 'This version works the selected report out
# differently'?", Knut answered "Yes." The window decides by comparing the
# rows an Update would write with the page (`_update_would_change_the_report`).
# The same three buttons, in the same order, Create New first and the default.
M_REPORT_WORKED_OUT_DIFFERENTLY_UPDATE_OR_NEW = _m(
    "M-REPORT-WORKED-OUT-DIFFERENTLY-UPDATE-OR-NEW",
    "This version works the selected report out differently",
    "Nothing was changed in the settings of the selected report, but this "
    "version of ChromIQ works it out differently from the version that "
    "saved it: an update changes some of its results, or the notes that "
    "explain them.\n\n"
    "What do you want to do?\n\n"
    "1. Create new report with the same settings.\n"
    "2. Update selected report, worked out again by this version of ChromIQ.\n"
    "3. Cancel",
    approved=True)

# --- PROPOSED (#182 K39-3, Knut 5831246553): the red line under the settings
# after "New report…" is chosen. His rule: choosing it does NOT change the
# report on the page; the defaults of a new report are loaded into the
# controls, and a red line tells the user to change the settings as wanted and
# then press Generate report to make the new report. Window text, so it may
# name the button. Only the body is shown, after a warning sign.
M_REPORT_NEW_REPORT_SETTINGS = _m(
    "M-REPORT-NEW-REPORT-SETTINGS",
    "Settings loaded for a new report",
    "New report: change the settings as wanted, then press “Generate "
    "report” to make it. The report shown stays as it is until then.",
    approved=True)

# --- PROPOSED (#182, Knut D11/D24): the note at the foot of the Report limits
# window ----------------------------------------------------------------------
M_THRESHOLDS_NOT_CERTIFICATION = _m(
    "M-THRESHOLDS-NOT-CERTIFICATION",
    "ChromIQ measures against published values; it does not certify",
    # THE THIRD COPY OF A SENTENCE CORRECTED TWICE ELSEWHERE, and the one in
    # the window that actually draws the columns. It read "The columns named
    # after a standard hold that standard's published tolerance values", which
    # is false of the two Custom columns (they start from ChromIQ's own numbers
    # where nobody has supplied a standard's) and false of the two read-only
    # ones as ChromIQ ships (the data file is empty by design). The report's
    # guide was corrected for each half in turn; this copy was corrected
    # neither time, and `_notes_text` prints it two lines below its own correct
    # sentence, so one panel said both things at once.
    # …AND THE CORRECTION ITSELF WENT HALF-STALE ON 2026-09-21, when Knut's
    # researched industry figures became the two Custom columns' starting
    # values (#182). "ChromIQ's own numbers" then described nineteen of the
    # thirty-six cells and not the other seventeen. Both sources are named.
    # …AND AGAIN FOR #182 S-2 (§23 of the limits record): a set whose values
    # SHIP judges its read-only column with them while the Custom column
    # beside it keeps Knut's figures, so "where nobody has supplied them" no
    # longer divides the columns correctly. Each column is described by what
    # it starts from, as a condition, so the one sentence is true whether a
    # set ships, is supplied, or holds nothing.
    "A read-only column named after a standard is judged against that "
    "standard's published tolerance values, where ChromIQ ships them or a "
    "licence holder has supplied them. Such a column reads “–” for a row "
    "ChromIQ can measure that the standard puts no limit on, and ? where it "
    "limits the row but no "
    "number has been supplied for it. A "
    "Custom column starts from limits researched from industry practice and "
    "ChromIQ's own numbers, neither of which is that standard's, and no "
    "values file changes that. "
    "Either way the values are "
    "applied to the chart you printed and not to that standard's own control "
    "strip and chart, so a report can never say that a print conforms to a "
    "standard. What ChromIQ does is measure as many of the standard's values "
    "as your chart allows, say which it checked and which it did not, and let "
    "you follow them over time.\n\n"
    "Rows marked ✕ are requirements ChromIQ cannot measure at all; they stay in "
    "the table so you can see what the standard asks: {rows}",
    approved=False)

# --- PROPOSED (#182, Knut 2026-09-21): the note a bracketed limit points at -
#
# THE HALF OF THE RULING THAT IS NOT THE VERDICT WORD. Knut retired COND as a
# row word and asked, in the same message, for what replaces it: *"there should
# be a note associated with the metric its self, like a reference number at the
# end of the metric label-name, pointing to a note below the table in the
# Report Limits window (and in the report text also a number on the metric
# name, pointing to a note in the report text)."* One text, rendered in both
# places, because two copies are two documents that can drift apart.
#
# WHAT IT MAY NOT SAY. His first version of this note ended *"but does not
# affect the overall result of the ISO 12647 verification"*, and he WITHDREW
# that nine minutes later: *"all thresholds tested against are treated the
# same … If the test is applied the report shall show the result as is, and the
# overall result follows as normal."* So the note says what the standard calls
# the metric and stops. A sentence excusing the row from the Overall would be
# false of the code and against the ruling that replaced it.
M_LIMIT_RECOMMENDED = _m(
    "M-LIMIT-RECOMMENDED",
    "The standard recommends this metric rather than requiring it",
    "The standard calls this metric recommended rather than required, so it "
    "may be applied optionally. Its limit is shown in brackets. It was applied "
    "here, and the result is reported the same way as every other row.",
    approved=True)

# --- PROPOSED (#182, Knut B8-591): the one-page summary covers ONE
# measurement, and a user who has ticked several must be TOLD rather than
# corrected behind his back.
#
# Knut, 2026-09-20, in the same comment that removed "Show all measurement
# runs": *"color summary only allows one measurement date ticked, and if
# several is selected, user must be informed as mentioned above, and make a
# choice which to include"* — and, of the general shape: *"Upon generate
# report clicked, the user should be informed … Then the user can close that
# message and do the changes, and then click generate report again."*
#
# So it INFORMS and stops. It does not choose a measurement, and it does not
# untick anything: correcting the ticks silently is the fault he reported
# twice ("This unselected all but the last measurement without a warning" and
# "the measurement I had ticked was unticked and the last measurement in the
# list was automatically ticked (I did not ask for that)").
M_REPORT_ONE_PAGE_ONE_DATE = _m(
    "M-REPORT-ONE-PAGE-ONE-DATE",
    "A colour summary is one page about one measurement",
    "{count} measurements are ticked in “Included Measurements in report”, "
    "and this report type has room for one.\n\n"
    "Close this, untick the measurements you do not want on the page, and "
    "click “Generate report” again. “Deselect all” clears them all if that is "
    "quicker. To keep every measurement you have ticked, choose another "
    "report type instead.",
    approved=True)

# --- PROPOSED (challenge C, beta 39, #1): an Update that would narrow a
# report to what this side can find ------------------------------------------
#
# Update rewrites a report about every measurement it covers (§13.13). From a
# side that could not find one of them (a project renamed or moved, measured
# with the demo pack's Report-Limits-Renamed), it archived the whole report
# and rewrote it about the one date it found. No rule lets an Update drop a
# covered measurement it cannot find, so it refuses and says which and why.
# {missing} is one `report_gone_line` per measurement.
M_REPORT_UPDATE_NOT_FOUND = _m(
    "M-REPORT-UPDATE-NOT-FOUND",
    "This report cannot be updated from here",
    "The selected report covers measurements that ChromIQ cannot find:\n\n"
    "{missing}\n\n"
    "Updating it now would rewrite the report without them, so nothing was "
    "changed. Put the project back in the folder beside this one, or open "
    "the report from a project that can reach them, and try again. "
    "“Create New” writes a new report of what is ticked and leaves "
    "this one as it is.",
    approved=True)

# --- PROPOSED (challenge C, beta 39, #11): the Update leaves out
# measurements that are no longer on disk, and asks first --------------------
#
# §13.11 leaves out a folder that no longer holds its measurement. An Update
# did that in silence, and one such date was enough to retire a report across
# projects into a one-date report. The question names them; the user chooses.
M_REPORT_UPDATE_LEAVES_OUT = _m(
    "M-REPORT-UPDATE-LEAVES-OUT",
    "Some measurements of this report are no longer on disk",
    "The selected report covers measurements that are no longer on disk:\n\n"
    "{missing}\n\n"
    "Updating it now leaves them out, and the report then covers only what "
    "is still there. The report as it is now is kept in the old folder "
    "first.\n\n"
    "What do you want to do?",
    approved=True)

# --- PROPOSED (re-challenge R1, beta 39, #4): an Update that would leave a
# report of nothing ----------------------------------------------------------
#
# "Update without them" on a report whose EVERY measurement was gone wrote
# `measurements: []` under the report's old verdict and old scope, and the
# list and the page went on showing it as the report it had been. Nothing
# would be left to update, so the press is refused before anything is
# written and the window names the two buttons that do something.
M_REPORT_UPDATE_NOTHING_LEFT = _m(
    "M-REPORT-UPDATE-NOTHING-LEFT",
    "Nothing of this report is left to update",
    "None of the measurements the selected report covers is on disk any "
    "more:\n\n{missing}\n\n"
    "Updating it would leave a report that covers nothing, so nothing was "
    "changed and the report stays as it was written. "
    "“Delete Selected Report” moves it to the old folder, and "
    "“Create New” writes a new report of what is ticked.",
    approved=False)

# --- PROPOSED (B8-1655, 2026-09-28): a calibration file found while the
# ChromIQ layout engine lays the chart out -------------------------------
#
# The prefill of decision 7 (calibration_run_type.md, 2026-08-05) fills the
# printtarg -K and -I fields and says so. An engine build does not read those
# fields: it takes its calibration from the engine panel's own "Printer
# calibration" group (``LayoutOptionsPanel.cal_settings``). With the engine the
# default, the found .cal went where the build ignores it, and the status line
# told the user to switch on a field that does nothing. The engine panel's path
# is now offered the same way (filled only when empty, Mode left on "None"),
# and this is the status line for that case. The words are ours.
M_CAL_FOUND_ENGINE = _m(
    "M-CAL-FOUND-ENGINE",
    "Calibration file found",
    "Calibration file found: {name}. It is filled into “Printer calibration” "
    "in the ChromIQ layout section below, with Mode still on “None”: choose "
    "the mode you want there. “Apply & embed (-K)” reprints every patch "
    "through the calibration; “Embed only (-I)” only records it in the chart "
    "file.",
    approved=True)   # Knut, #182 5865088296, 2026-09-28: "Message 1 is ok"

# --- PROPOSED (challenge C, beta 39, #7): Delete Selected Report could not
# move the report ----------------------------------------------------------
#
# In a read-only folder the move copied the report into old/ and left the
# original, so the report existed twice, and the window showed Python's own
# "[Errno 13] Permission denied: '/Users/…'". The move is now all or nothing.
M_REPORT_DELETE_FAILED = _m(
    "M-REPORT-DELETE-FAILED",
    "The report could not be moved to the old folder",
    "ChromIQ could not change this folder:\n\n{folder}\n\n"
    "Nothing was moved, and the report is still in the list. The usual "
    "reason is that the folder is read-only. {remedy}",
    approved=False)

# --- PROPOSED (challenge C, beta 39, #8): an Update or a new report in a
# folder ChromIQ may not write in --------------------------------------------
#
# The press was already all or nothing; the window said only "Nothing could
# be written. The log says why." It now names the folders and the remedy.
M_REPORT_NOT_WRITABLE = _m(
    "M-REPORT-NOT-WRITABLE",
    "The report was not written",
    "ChromIQ is not allowed to write in:\n\n{folders}\n\n"
    "A report is written whole or not at all, so nothing was changed. Give "
    "yourself permission to change those folders, or copy the project "
    "somewhere you may write, and try again.",
    body_one="ChromIQ is not allowed to write in:\n\n{folders}\n\n"
    "A report is written whole or not at all, so nothing was changed. Give "
    "yourself permission to change that folder, or copy the project "
    "somewhere you may write, and try again.",
    count_key="count",
    approved=False)

# --- PROPOSED (re-challenge R2 of beta 39, #1): a run delete refused
# because the saved reports that name the later runs cannot be renumbered ----
#
# The refusal was a bare paragraph under the heading "This is what ChromIQ
# tried to remove:", followed by <project>/reports. ChromIQ never tried to
# remove that folder: it is where the reports it would have to CHANGE live.
# The window now has a headline and says what the folders are.
# {folders} is one folder per line; {count} is how many.
M_RUN_DELETE_REPORTS_LOCKED = _m(
    "M-RUN-DELETE-REPORTS-LOCKED",
    "Profile run {n} was not deleted",
    "Nothing was deleted. Deleting this run renumbers the runs after it, and "
    "the saved reports that name those runs by number must be renumbered "
    "with them. ChromIQ is not allowed to change the reports in these "
    "folders:\n\n{folders}\n\n"
    "Make them writable, or move the project somewhere you may write, and "
    "try again.",
    body_one="Nothing was deleted. Deleting this run renumbers the runs "
    "after it, and the saved reports that name those runs by number must be "
    "renumbered with them. ChromIQ is not allowed to change the reports in "
    "this folder:\n\n{folders}\n\n"
    "Make it writable, or move the project somewhere you may write, and try "
    "again.",
    count_key="count",
    approved=False)

# --- APPROVED (#182 A6, Knut 5817809396; words approved in 5820871320):
# Report Scope names a profile run the report covered that has since been
# deleted ------------------------------------------------------------------
#
# Knut, 5820871320: *"Given the above, the message is accepted"*, the above
# being that "profile run", "verification run" and "calibration run" are
# defined in the Dictionary help card and used the same way everywhere
# (K36-3). "Profile run" here is that defined term: the numbered run (run 2),
# whichever of its measurements the report covered.
#
# The bar's Delete renumbers the later runs and turns a saved report's
# reference to the deleted run into ``runs/runN.deleted``, which no folder
# ever answers. The report then shows fewer measurements than it was written
# about, and only an Update said why. Report text (window and PDF), so it is
# written for a reader of the document: nothing about ChromIQ's buttons.
# ``{runs}`` is `deleted_runs_label`'s: "run 2", "run 2 and run 4", or with
# the project's name when the report covers more than one project.
M_REPORT_SCOPE_RUN_DELETED = _m(
    "M-REPORT-SCOPE-RUN-DELETED",
    "Part of this report has since been deleted",
    "This report also covered {count} profile runs that have since been "
    "deleted ({runs} when the report was written). Their measurements are no "
    "longer in the report.",
    body_one="This report also covered a profile run that has since been "
    "deleted ({runs} when the report was written). Its measurements are no "
    "longer in the report.",
    count_key="count",
    approved=True)   # Knut, #182 5820871320

#: How `M_REPORT_SCOPE_RUN_DELETED` names one deleted run (A6). Module
#: constants, because the extractor resolves ``tr(NAME)`` only for those.
_DELETED_RUN = "run {n}"
_DELETED_RUN_OF = "{project}, run {n}"
_DELETED_RUNS_JOIN = "{first} and {last}"


def deleted_runs_label(entries: "list[tuple[str, str]]",
                       several_projects: bool) -> str:
    """``{runs}`` of M-REPORT-SCOPE-RUN-DELETED for ``[(project, n)]``."""
    names = [tr(_DELETED_RUN_OF).format(project=p, n=n) if several_projects
             else tr(_DELETED_RUN).format(n=n) for p, n in entries]
    if len(names) <= 1:
        return "".join(names)
    return tr(_DELETED_RUNS_JOIN).format(first=", ".join(names[:-1]),
                                         last=names[-1])


# --- APPROVED (#182 A10, Knut 5817809396; words approved in 5820871320): a
# chart with no paper patch -------------------------------------------------
#
# "Paper white" was the lightest measured patch; on a chart with no patch
# printed with no ink that is a light colour or grey, which was printed as
# the paper, drawn in its graph and divided into the readings. It now reads
# N-A with this numbered note. Report text: for a reader of the document.
#
# **PER MEASURED SHEET, NOT PER REPORT (K36-4).** Knut, 5820871320: *"do you
# mean the "chart sheet" or do you mean "nothing in this report"? Make sure
# the text cannot be misunderstood. Then this message is accepted."* The code
# decides it per measurement: `build_report` finds the paper patch and
# chooses the yardstick for each measured sheet on its own, and the note is
# attached to that sheet's "Paper white" line. A report can hold sheets of
# several charts, so the words name the sheet and say that the rest of the
# report is not affected.
#
# **"SHEET" WAS STILL UNCLEAR (Knut, 5824834975, on the four K37 notes that
# share these words).** Reworded 2026-09-25 in the report's own vocabulary:
# the measurement ("Detailed data per measurement"), which is what the note is
# decided for. The approval above is kept; §M records the rewording.
M_REPORT_NO_PAPER_PATCH = _m(
    "M-REPORT-NO-PAPER-PATCH",
    "This chart has no paper patch",
    "The chart of this measurement has no patch printed with no ink, so "
    "this measurement has no paper white of its own. Every colour of this "
    "measurement is therefore judged as measured, in absolute Lab, and none "
    "relative to the paper. Only the measurements that carry this note are "
    "judged this way; the report's other measurements are judged as usual.",
    approved=True)   # Knut, #182 5820871320


# --- PROPOSED (#182 K37, Knut 5822758830, answer 1): a sheet printed with an
# intent that maps white to the paper, whose chart has no paper patch -------
#
# Knut: *"Recommendation: (e), with a numbered note on the sheet, and (b)
# only when no profile can be read."* (§32.6 and §33 of
# `docs/design/measurement_report_limits.md`.)
#
# (e) The sheet is judged relative to the paper white of the profile it was
# printed through (else the run's own profile). M-REPORT-NO-PAPER-PATCH says
# "every colour on this sheet is therefore judged as measured, in absolute
# Lab", which is FALSE on such a sheet, so this note takes its place on that
# sheet's "Paper white" line and says both things: why the paper white reads
# N-A, and where the paper white the colours were judged against came from.
# The approved message stays on every sheet where its words are true.
M_REPORT_PAPER_WHITE_FROM_PROFILE = _m(
    "M-REPORT-PAPER-WHITE-FROM-PROFILE",
    "Paper white taken from the profile",
    "The chart of this measurement has no patch printed with no ink, so "
    "this measurement has no paper white of its own. The chart was printed "
    "with an intent that maps white to the paper, so the colours of this "
    "measurement are judged relative to the paper white recorded in the "
    "profile {profile} (L* {L}, a* {a}, b* {b}), which is the paper that "
    "profile was made for. If the measured paper differs from it (another "
    "batch, or paper that has aged), the results can be off by a little. "
    "Only the measurements that carry this note are judged this way; the "
    "report's other measurements are judged as usual.",
    approved=True)   # Knut, #182 5824834975 ("sheet" reworded)

# (b) No profile could be read, so the sheet stays in absolute Lab. The note
# travels with every row whose verdict that moves (the colour-difference,
# control-strip, gamut, grey-balance, tone-ramp and evenness rows of that
# sheet), so a reader of a FAIL sees why it may not be the print's fault.
# M-REPORT-NO-PAPER-PATCH stays on the sheet's "Paper white" line: on this
# sheet its words are true.
M_REPORT_JUDGED_ABSOLUTE_NO_PAPER_WHITE = _m(
    "M-REPORT-JUDGED-ABSOLUTE-NO-PAPER-WHITE",
    "Judged without a paper white",
    "The chart of this measurement was printed with an intent that maps "
    "white to the paper, so its colours should be judged relative to its "
    "paper white. The chart has no patch printed with no ink, and no "
    "profile could be read to take the paper white from, so these rows of "
    "this measurement are judged as measured, in absolute Lab. The paper's "
    "own lightness and tint then count against every colour, so these "
    "results can read worse than the print is (on typical papers by about "
    "1.5 to 3 ΔE00 on the averages), and a limit can fail for that reason "
    "alone. Only the measurements that carry this note are judged this way; "
    "the report's other measurements are judged as usual.",
    approved=True)   # Knut, #182 5824834975 ("sheet" reworded)

# --- PROPOSED (#182 K37 (i), Knut 5823088098 "Yes do so", on our
# 5823015844): on a FROM PROFILE GAMUT chart the control strip's seven ink
# and black corner rungs are compared with the profile's prediction; the
# cube-corner table keeps the ideal values. The note on the three
# control-strip rows says a corner patch has two comparisons. ---------------
M_REPORT_STRIP_CORNERS_PREDICTED = _m(
    "M-REPORT-STRIP-CORNERS-PREDICTED",
    "A corner patch is compared two ways",
    "In this measurement the chart's solid ink, overprint and black patches "
    "are compared two ways. In the cube-corner table each is compared with "
    "its ideal value, which shows how far this printer's colour is from the "
    "ideal one. In the control-strip rows each is compared with the colour "
    "the profile predicts for it, like every other patch of this chart, "
    "which shows how accurately it was printed. Only the measurements that "
    "carry this note are judged this way; the report's other measurements "
    "are judged as usual.",
    approved=True)   # Knut, #182 5824834975 ("sheet" reworded)

# ...and when no profile can be read to ask: today's comparison stays.
M_REPORT_STRIP_CORNERS_IDEAL = _m(
    "M-REPORT-STRIP-CORNERS-IDEAL",
    "Corner patches compared with their ideal values",
    "No profile could be read to predict the colours of this measurement's "
    "solid ink, overprint and black patches, so in the control-strip rows "
    "they are compared with their ideal values, as in the cube-corner "
    "table. That difference is mostly how far this printer's colours are "
    "from the ideal ones, not a printing error, so these rows can read "
    "worse than the print is. Only the measurements that carry this note "
    "are judged this way; the report's other measurements are judged as "
    "usual.",
    approved=True)   # Knut, #182 5824834975 ("sheet" reworded)

# --- APPROVED (#182 K49, (b2), Knut 5841092535: "Should (b2) be built?
# Answer: Yes."): the paper row and the two solid rows compare the
# measurement with its profile's own description of the printing condition.
# The cube-corner table keeps the ideal values (§32.5 reversed for the two
# solid rows only), so a row and the table can read very differently about
# the same patch; the note on the row says why. Both notes APPROVED by Knut
# in 5845588201: *"Messages "M-REPORT-SOLIDS-PREDICTED" and
# "M-REPORT-PAPER-AGAINST-PROFILE" accepted."* ------------------------------
M_REPORT_SOLIDS_PREDICTED = _m(
    "M-REPORT-SOLIDS-PREDICTED",
    "Solid colours compared with the profile's prediction",
    "In this measurement the solid cyan, magenta, yellow and black patches "
    "are compared with the colours the profile predicts for them, which "
    "shows how accurately they were printed. The cube-corner table compares "
    "the same patches with their ideal values, which shows how far this "
    "printer's colours are from the ideal ones, so the two can differ a lot.",
    approved=True)   # Knut, #182 5845588201: "accepted"

# --- PROPOSED: a sheet printed through its profile, judged twice (beta 12) ---
#: Knut, #182 6045500910, answer 1 ("OK" to question 1 of 6044584365): the
#: profile's accuracy against its own prediction, and colour fidelity against
#: the TRUE source colour on in-gamut patches only. The ruling is CONFIRMED
#: (verification_printing_and_target.md B3, measurement_report_limits.md §58);
#: the words are ours and wait here. {profile}: the source profile's file name
#: (sRGB.icm); {intent}: the intent's name as the report prints it
#: ("relative colorimetric").
_REPORT_PROFILE_ACCURACY_HEADING = (
    "Profile accuracy (ΔE00 against the profile's own prediction)")
_REPORT_SOURCE_HEADING = (
    "Colour accuracy (ΔE00 against the colours the sheet was converted from)")
_REPORT_SOURCE_REFERENCE = (
    "the colours the sheet was converted from: the chart's colours in "
    "{profile}, {intent}. Only the colours inside the profile's gamut "
    "({intent}) are judged; the others are shown beyond the gamut, for "
    "information.")
_REPORT_SOURCE_MEASURED = (
    "two things: how faithfully the colours inside the profile's gamut were "
    "reproduced, and how accurate the profile is against its own prediction")
#: k40 (Knut 6059912998, answer 1): a failed table fails the sheet, so the
#: beta-12 line ("these words do not change the sheet's verdict") is revised.
#: The beta-12 line, kept for a report SAVED by beta 12 to 14 and shown as
#: it was saved (§53): its Overall word did not count the table (review of
#: beta 15). The beta-12 line 4 of M-REPORT-THROUGH-PROFILE, unchanged.
_REPORT_PROFILE_ACCURACY_NOTE_BEFORE_K40 = (
    "Every patch, inside the gamut or not, compared with what the profile "
    "predicts for the ink amounts that were really printed. Judged with the "
    "same limits; these words do not change the sheet's verdict.")
_REPORT_PROFILE_ACCURACY_NOTE = (
    "Every patch, inside the gamut or not, compared with what the profile "
    "predicts for the ink amounts that were really printed. Judged with the "
    "same limits, and a value over its limit here also fails the sheet's "
    "overall verdict.")
#: k41 (Knut 6059912998, answer 2): a sheet printed through the perceptual
#: or saturation intent. Its source comparison is shown for information and
#: the profile accuracy table judges it (`measurement_report.
#: RE_RENDERING_INTENTS`). Line 6 replaces line 2, line 7 replaces line 3;
#: lines 8 and 9 are the note on its five colour-accuracy rows.
_REPORT_SOURCE_REFERENCE_INFO = (
    "the colours the sheet was converted from: the chart's colours in "
    "{profile}, {intent}. The sheet was printed with a rendering intent that "
    "changes colours on purpose, so this comparison is shown for information "
    "only and is not judged.")
_REPORT_SOURCE_MEASURED_INFO = (
    "how accurate the profile is against its own prediction. The rendering "
    "intent changed the colours on purpose, so how closely they match the "
    "original colours is shown for information only")
_REPORT_INTENT_PERCEPTUAL_INFO = (
    "This sheet was printed with the perceptual rendering intent, which "
    "changes colours on purpose so that all of them fit inside the printer's "
    "gamut. So this value compares the print with the original colours for "
    "information only and is not judged against a limit. The sheet is judged "
    "on its profile accuracy instead: every patch against what the profile "
    "predicts for the ink amounts that were really printed.")
_REPORT_INTENT_SATURATION_INFO = (
    "This sheet was printed with the saturation rendering intent, which "
    "changes colours on purpose to make them as vivid as the printer allows. "
    "So this value compares the print with the original colours for "
    "information only and is not judged against a limit. The sheet is judged "
    "on its profile accuracy instead: every patch against what the profile "
    "predicts for the ink amounts that were really printed.")
_REPORT_PROFILE_ACCURACY_NONE = (
    "The profile's prediction of this sheet could not be worked out, so the "
    "profile's accuracy is not shown.")
M_REPORT_THROUGH_PROFILE = _m(
    "M-REPORT-THROUGH-PROFILE",
    _REPORT_PROFILE_ACCURACY_HEADING,
    "\n".join((_REPORT_SOURCE_HEADING, _REPORT_SOURCE_REFERENCE,
               _REPORT_SOURCE_MEASURED, _REPORT_PROFILE_ACCURACY_NOTE,
               _REPORT_PROFILE_ACCURACY_NONE, _REPORT_SOURCE_REFERENCE_INFO,
               _REPORT_SOURCE_MEASURED_INFO, _REPORT_INTENT_PERCEPTUAL_INFO,
               _REPORT_INTENT_SATURATION_INFO)),
    approved=False)

# --- PROPOSED: the chart preview shows the sheet as it will print (beta 12) -
#: Knut, #182 6045500910 answer 4: "preview should always look as paper would
#: look printed, assuming normal printing path"; Basti 6045468325: show the
#: soft-proofed version and "a little indicator that gives this information
#: without being a distraction". The behaviour is theirs, the words are ours.
#: The headline is the indicator over a page shown through the run's profile
#: (printed raw); line 1 the indicator of a page printed through the profile;
#: lines 2 to 4 the indicator of a page shown as its device values (no
#: profile yet, pages carrying the printer calibration, a conversion that
#: failed). Lines 5 to 9 are the indicator's tooltips, in the same order.
#: {profile}: the run profile's file name; {source}: the source profile's
#: file name; {intent}: the print's intent ("relative colorimetric").
_PREVIEW_AS_PRINTED_RAW = "As on paper, via the run's profile"
_PREVIEW_AS_PRINTED_THROUGH = "As on paper, printed through the profile"
_PREVIEW_DEVICE_NO_PROFILE = "Device values, no profile yet"
_PREVIEW_DEVICE_CALIBRATED = "Device values, calibrated pages"
_PREVIEW_DEVICE_FAILED = "Device values, profile not applied"
_PREVIEW_TIP_RAW = (
    "The preview shows this chart as it prints: the ink amounts in the file, "
    "as the run's profile {profile} predicts them on paper, with the paper "
    "shown as white. What is printed does not change.")
_PREVIEW_TIP_THROUGH = (
    "The preview shows this chart as it prints through the profile: its "
    "colours converted from {source} to {profile} ({intent}), as ChromIQ "
    "converts them when printing, then as the profile predicts them on "
    "paper, with the paper shown as white. What is printed does not change.")
_PREVIEW_TIP_NO_PROFILE = (
    "The preview shows the ink amounts in the file as screen colours, so it "
    "can look lighter or more colourful than the print. Once this run has a "
    "profile, the preview shows the chart as it prints.")
_PREVIEW_TIP_CALIBRATED = (
    "The pages of this chart carry the printer calibration, which the "
    "profile does not describe, so the preview shows the ink amounts in the "
    "file as screen colours.")
_PREVIEW_TIP_FAILED = (
    "ArgyllCMS could not convert this page through {profile}, so the "
    "preview shows the ink amounts in the file as screen colours.")
#: Basti, 2026-10-08: the indicator is also the SWITCH between the two views,
#: and stays small: collapsed an icon, on hover a short line. Line 10 and 11
#: are that line's view, lines 12 and 13 what a click does (shown beside it);
#: line 14 closes the tooltip of a page shown as on paper, line 15 is the
#: tooltip of a page shown as device values by choice, line 16 closes the
#: tooltip of a page that has no view on paper (lines 7 to 9). {keys}: the
#: platform's spelling of the shortcut (⌘Y, Ctrl+Y).
_PREVIEW_CHIP_PAPER = "As on paper"
_PREVIEW_CHIP_DEVICE = "Device values"
_PREVIEW_CHIP_TO_DEVICE = "click: device values"
_PREVIEW_CHIP_TO_PAPER = "click: as on paper"
_PREVIEW_TIP_CLICK_DEVICE = (
    "Click here, or press {keys}, to see the ink amounts in the file as "
    "screen colours instead. ChromIQ remembers your choice in Create Chart, "
    "Print Chart and Measure.")
_PREVIEW_TIP_DEVICE_CHOSEN = (
    "You chose to see the ink amounts in the file as screen colours, so the "
    "preview can look lighter or more colourful than the print. Click here, "
    "or press {keys}, to see the chart as it prints through {profile} again. "
    "What is printed does not change.")
_PREVIEW_TIP_NO_SWITCH = (
    "This page cannot be shown as on paper, so a click changes nothing here.")
M_PREVIEW_AS_PRINTED = _m(
    "M-PREVIEW-AS-PRINTED",
    _PREVIEW_AS_PRINTED_RAW,
    "\n".join((_PREVIEW_AS_PRINTED_THROUGH, _PREVIEW_DEVICE_NO_PROFILE,
               _PREVIEW_DEVICE_CALIBRATED, _PREVIEW_DEVICE_FAILED,
               _PREVIEW_TIP_RAW, _PREVIEW_TIP_THROUGH, _PREVIEW_TIP_NO_PROFILE,
               _PREVIEW_TIP_CALIBRATED, _PREVIEW_TIP_FAILED,
               _PREVIEW_CHIP_PAPER, _PREVIEW_CHIP_DEVICE,
               _PREVIEW_CHIP_TO_DEVICE, _PREVIEW_CHIP_TO_PAPER,
               _PREVIEW_TIP_CLICK_DEVICE, _PREVIEW_TIP_DEVICE_CHOSEN,
               _PREVIEW_TIP_NO_SWITCH)),
    approved=False)

# --- APPROVED (Sebastian, 2026-10-08): Simulate paper white, inside the preview's indicator (beta 14)
#: Basti, 2026-10-08: "when the user hovers the label icon and it extends and
#: the proof view is active could then there be also a button inside that
#: activates and deactivates simulate paper white? ... the choice should also
#: be remembered." The behaviour is his, the words are ours. The headline is
#: the small button's label inside the open indicator (only while a page is
#: shown as on paper); line 1 is the button's name for a screen reader,
#: line 2 the indicator's name while the paper white is simulated; lines 3
#: and 4 the button's tooltip when off and when on; lines 5 and 6 replace
#: the indicator's explanation (M-PREVIEW-AS-PRINTED lines 5 and 6) while
#: the paper white is simulated. Placeholders as in M-PREVIEW-AS-PRINTED.
_PREVIEW_PAPER_WHITE = "Paper white"
_PREVIEW_PAPER_WHITE_NAME = "Simulate paper white"
_PREVIEW_CHIP_PAPER_WHITE_ON = "As on paper, paper white simulated"
_PREVIEW_PAPER_WHITE_TIP_OFF = (
    "Simulate paper white is off: the paper is shown as the screen's white. "
    "Click, or press Space, to show the paper in its own tone, as the run's "
    "profile describes it. ChromIQ remembers your choice.")
_PREVIEW_PAPER_WHITE_TIP_ON = (
    "Simulate paper white is on: the paper is shown in its own tone, as the "
    "run's profile describes it (absolute colorimetric), and every colour "
    "sits on it as on the sheet. Click, or press Space, to show the paper as "
    "white again.")
_PREVIEW_TIP_RAW_PAPER = (
    "The preview shows this chart as it prints: the ink amounts in the file, "
    "as the run's profile {profile} predicts them on paper, with the paper "
    "in its own tone (paper white simulated). What is printed does not "
    "change.")
_PREVIEW_TIP_THROUGH_PAPER = (
    "The preview shows this chart as it prints through the profile: its "
    "colours converted from {source} to {profile} ({intent}), as ChromIQ "
    "converts them when printing, then as the profile predicts them on "
    "paper, with the paper in its own tone (paper white simulated). What is "
    "printed does not change.")
M_PREVIEW_PAPER_WHITE = _m(
    "M-PREVIEW-PAPER-WHITE",
    _PREVIEW_PAPER_WHITE,
    "\n".join((_PREVIEW_PAPER_WHITE_NAME, _PREVIEW_CHIP_PAPER_WHITE_ON,
               _PREVIEW_PAPER_WHITE_TIP_OFF, _PREVIEW_PAPER_WHITE_TIP_ON,
               _PREVIEW_TIP_RAW_PAPER, _PREVIEW_TIP_THROUGH_PAPER)),
    approved=True)  # Sebastian, 2026-10-08

# --- PROPOSED: the slow-chart window of a build with no profile (beta 12) ---
#: The window that offers the faster patch layout (ui/dialogs/
#: slow_chart_dialog.py) was written for a refinement chart: "with certain
#: pre-conditioning profiles", "the same profile", "for a refinement chart".
#: A plain chart (no targen -c) shows this text instead; a build with a
#: profile keeps the window's own text. Headline and buttons are unchanged.
M_CHART_SLOW_NO_PROFILE = _m(
    "M-CHART-SLOW-NO-PROFILE",
    "This chart is taking longer than usual",
    "ChromIQ hasn't frozen: your chart is still being built in the "
    "background. On larger (multi-page) charts, Argyll's standard way of "
    "arranging the colour patches can slow down dramatically, and that's "
    "what's happening here.\n\n"
    "You have three choices:\n\n"
    "• Keep waiting: let it finish with the highest-quality patch layout. Be "
    "aware this may take a very long time, and there's no reliable way to "
    "predict how long.\n\n"
    "• Rebuild with the faster layout (recommended): ChromIQ stops this "
    "attempt and immediately rebuilds the same chart, with the same number "
    "of patches, using a different patch-arrangement method that doesn't "
    "suffer from this slowdown. The patches are still spread evenly through "
    "the colour space, and it usually finishes in under a second.\n\n"
    "• Cancel: stop building the chart. Nothing is saved.",
    approved=False)

M_REPORT_PAPER_AGAINST_PROFILE = _m(
    "M-REPORT-PAPER-AGAINST-PROFILE",
    "Paper compared with the profile's paper",
    "In this measurement the paper is compared with the paper white recorded "
    "in the profile (the one the chart was printed through, or else the "
    "profile of its run), which is the paper that profile was made for. The "
    "cube-corner table compares the same patch with the chart's own aim for "
    "white, an ideal white, so the two can differ.",
    approved=True)   # Knut, #182 5845588201: "accepted"

# --- APPROVED: a saved report worked out by an earlier version (challenge 5
# of beta 42, M1, B8-1091). Its verdicts are kept (§6); a rule introduced since
# (K34's paper patch, K37's paper white from the profile and the strip corners
# against the profile's prediction) would work some of its rows out
# differently, and the rebuilt notes would contradict the kept words. The page
# shows the report as it was saved and says so, once.
# K39-1 (Knut, #182 5831246553): approved except "Update works the report out
# again.", because report text never names a feature, an action or a button of
# the app. The last sentence now speaks of the topic in general terms.
M_REPORT_WORKED_OUT_EARLIER = _m(
    "M-REPORT-WORKED-OUT-EARLIER",
    "Worked out by an earlier version",
    "This report was worked out by an earlier version of ChromIQ and is "
    "shown as it was saved. This version works some of its rows out "
    "differently. A newer report of the same measurements would be worked "
    "out the current way.",
    approved=True)   # Knut, #182 5831246553 (the UI reference removed)

# --- PROPOSED: a new report with a date whose measurement is gone (B8-1500) --
# Knut, #182 5857473253: a new or updated report is made entirely by the
# current version, every date worked out again from its measurement. Where a
# date's measurement is no longer on disk as it was measured, nothing can be
# worked out again, and its figures are the ones an earlier report saved. The
# report says so, rather than mixing them silently with this version's.
M_REPORT_NOT_WORKED_OUT = _m(
    "M-REPORT-NOT-WORKED-OUT",
    "Figures an earlier report saved",
    "The measurements of {dates} are no longer on disk as they were "
    "measured, so they could not be worked out again. Their figures are the "
    "ones an earlier report saved, worked out by the version of ChromIQ that "
    "saved it.",
    count_key="n",
    body_one=
    "The measurement of {dates} is no longer on disk as it was measured, so "
    "it could not be worked out again. Its figures are the ones an earlier "
    "report saved, worked out by the version of ChromIQ that saved it.",
    approved=True)   # Knut, #182 5858874320, 2026-09-27: "Approved."

# --- APPROVED (K59, Knut #182 5849392788; approved in 5850164956): A SHEET PRINTED RAW, OPTION C ---
# *"use recommended option C"*, with *"The word drift is not used at all ...
# Use the word "Change" instead of "Drift""* and, on the cell word, *"can we
# use the INFO but also have a numbered reference to a note that explains the
# issue, where that is relevant?"*. His answer to "I will propose the
# reworded sentence under the results, the guide entry and the "Judged
# against" text for your approval before they ship": *"Ok"*.
#
# Every text below replaced one that is false under his ruling (a cell or a
# sentence that says "drift" of a single sheet, a "Judged against" of "—"
# beside a column that says nothing about how it was printed). All fourteen
# were APPROVED by Knut in #182 5850164956: *"All messages under "B.
# PROPOSED, FOR YOUR APPROVAL (14 texts, all shown before approval)" are
# approved."*
# `tests/test_k59_no_drift_in_the_report.py` pins which one is used where.

#: The numbered note on a value of a raw sheet shown for information. Only on
#: the rows that compare the print with the chart's design colours
#: (`measurement_report.ROWS_COMPARED_WITH_THE_DESIGN`), which is where it is
#: "relevant": a repeatability row compares readings with readings, and the
#: paper and solid rows are compared with the profile.
M_REPORT_RAW_PRINT_INFO = _m(
    "M-REPORT-RAW-PRINT-INFO",
    "A value of a sheet printed raw, shown for information",
    "This sheet was printed raw, without the profile, so this value is shown "
    "for information only and is not judged: it compares the print with the "
    "chart's design colours, which a sheet printed without the profile is not "
    "expected to match closely.",
    approved=True)   # Knut, #182 5850164956

#: "Judged against" of a raw sheet's column, where it judged its paper or
#: solid rows ({set} is the limit set's name, as every other column shows it).
M_REPORT_RAW_JUDGED_AGAINST = _m(
    "M-REPORT-RAW-JUDGED-AGAINST",
    "Judged against, a sheet printed raw",
    "{set} (printed raw)",
    approved=True)   # Knut, #182 5850164956

#: ...and where it judged nothing (every value INFO or N-A).
M_REPORT_RAW_NOT_JUDGED = _m(
    "M-REPORT-RAW-NOT-JUDGED",
    "Judged against, a sheet printed raw that judged nothing",
    "not judged (printed raw)",
    approved=True)   # Knut, #182 5850164956

#: The Overall word's sentence (tooltip, one-page summary) of a raw column
#: that judged nothing. It replaces the profiling sheet's "It was measured to
#: build a profile rather than to check one", which is false of a
#: verification sheet; the same sentence is `compliance_sets.
#: SUMMARY_REASONS["raw_print"]`.
M_REPORT_RAW_OVERALL = _m(
    "M-REPORT-RAW-OVERALL",
    "Overall, a sheet printed raw that judged nothing",
    "This sheet was printed raw, without the profile, so its values are shown "
    "for information only and nothing on it was judged.",
    approved=True)   # Knut, #182 5850164956

#: The sentence under Report Results where a raw column judged ALL THREE of
#: its paper and solid rows, in every raw column: Knut's approved K51 clause
#: ("the paper and the solid colours are judged against the profile; the
#: other colours are compared with the chart's design colours for
#: information") is exactly true there and kept verbatim. Only the first
#: sentence, which named the "drift" cells, is new.
M_REPORT_RAW_RESULTS_JUDGED = _m(
    "M-REPORT-RAW-RESULTS-JUDGED",
    "Under the results, sheets printed raw that judged their paper and solids",
    "Columns marked “printed raw” under “Judged against” are sheets printed "
    "without the profile. On them the paper and the solid colours are judged "
    "against the profile; the other colours are compared with the chart's "
    "design colours for information, because a sheet printed raw is not "
    "expected to match the design closely, and PASS or FAIL there would be "
    "unfair to a perfectly healthy printer. For those sheets the detailed "
    "chapter shows how far the printer has moved since the previous raw "
    "check.",
    approved=True)   # Knut, #182 5850164956

#: ...where a raw column judged some of those rows but not all (a set that
#: limits the paper only, as ISO 12647-8 does; a row that read N-A). Challenge
#: 9 of beta 44: the clause must be true of exactly the rows judged.
M_REPORT_RAW_RESULTS_SOME = _m(
    "M-REPORT-RAW-RESULTS-SOME",
    "Under the results, sheets printed raw that judged some of their paper and "
    "solid rows",
    "Columns marked “printed raw” under “Judged against” are sheets printed "
    "without the profile. On them the paper and the solid colours are judged "
    "against the profile where the limit set has a limit for them and the "
    "measurement can answer them; the other colours are compared with the "
    "chart's design colours for information, because a sheet printed raw is "
    "not expected to match the design closely, and PASS or FAIL there would "
    "be unfair to a perfectly healthy printer. For those sheets the detailed "
    "chapter shows how far the printer has moved since the previous raw "
    "check.",
    approved=True)   # Knut, #182 5850164956

#: ...and where no raw column judged anything.
M_REPORT_RAW_RESULTS = _m(
    "M-REPORT-RAW-RESULTS",
    "Under the results, sheets printed raw that judged nothing",
    "Columns marked “printed raw” under “Judged against” are sheets printed "
    "without the profile. They are not expected to match the design closely, "
    "and PASS or FAIL would be unfair to a perfectly healthy printer, so their "
    "values are shown for information. For those sheets the detailed chapter "
    "shows how far the printer has moved since the previous raw check.",
    approved=True)   # Knut, #182 5850164956

#: "How to read this report": the paragraph about a raw column. The last
#: sentence, about the Overall word, is the one the guide carried before.
M_REPORT_RAW_GUIDE_JUDGED = _m(
    "M-REPORT-RAW-GUIDE-JUDGED",
    "How to read this report, a sheet printed raw",
    "A column marked “printed raw” under “Judged against” is a sheet printed "
    "without the profile. Its paper and solid colour rows are judged against "
    "the profile where the limit set has a limit for them; its values that "
    "compare the print with the chart's design colours read INFO, with a "
    "numbered note that says so. A column's Overall word is PASS when every "
    "row that could be checked passed; a row the test chart used could not "
    "answer is not counted as a failure, and the sentence under the word says "
    "how many there were.",
    approved=True)   # Knut, #182 5850164956

#: ...in a document whose raw columns judged nothing.
M_REPORT_RAW_GUIDE = _m(
    "M-REPORT-RAW-GUIDE",
    "How to read this report, a sheet printed raw that judged nothing",
    "A column marked “printed raw” under “Judged against” is a sheet printed "
    "without the profile. Its values that compare the print with the chart's "
    "design colours read INFO, with a numbered note that says so. A column's "
    "Overall word is PASS when every row that could be checked passed; a row "
    "the test chart used could not answer is not counted as a failure, and "
    "the sentence under the word says how many there were.",
    approved=True)   # Knut, #182 5850164956

#: The detailed chapter, under a raw sheet's table (Knut: "Change", not
#: "Drift"). The first raw sheet of a chart:
M_REPORT_RAW_BASELINE = _m(
    "M-REPORT-RAW-BASELINE",
    "The first raw check of a chart",
    "This sheet was printed raw, without the profile, and it is the first raw "
    "check of this chart: it is the baseline that later raw checks of this "
    "chart are compared with.",
    approved=True)   # Knut, #182 5850164956

#: ...a raw sheet whose previous raw check used another chart:
M_REPORT_RAW_INCOMPARABLE = _m(
    "M-REPORT-RAW-INCOMPARABLE",
    "A raw check after one of a different chart",
    "This sheet was printed raw, without the profile. The previous raw check "
    "used a different chart, so the change from print to print cannot be "
    "measured for this pair; the next raw check of THIS chart will start a "
    "fresh comparison.",
    approved=True)   # Knut, #182 5850164956

#: ...the print-to-print comparison with the previous raw check. Knut: "A
#: Comparison against another value cannot conclude that it is a drift. It is
#: better that a person looks at the trend to diagnose this."
M_REPORT_RAW_CHANGE = _m(
    "M-REPORT-RAW-CHANGE",
    "Change since the previous raw check",
    "Change since the previous raw check ({prev}): average {avg} ΔE00, "
    "maximum {max}: this print measured against that print, patch by patch, "
    "{n} patches. Small numbers mean the printer still behaves as it did "
    "then; larger numbers mean it has changed since. Whether it keeps "
    "changing in one direction can be read from the trend graphs, across all "
    "the dated checks. (PASS and FAIL against the report's limit set are not "
    "shown here: a raw sheet is not expected to match the design closely, so "
    "it would fail even a perfectly healthy printer.)",
    approved=True)   # Knut, #182 5850164956

#: ...a raw sheet with no comparison record at all:
M_REPORT_RAW_SHEET = _m(
    "M-REPORT-RAW-SHEET",
    "A sheet printed raw",
    "This sheet was printed raw, without the profile. Its figures compared "
    "with the chart's design colours describe the distance from the design, "
    "and what matters is how they change between dated checks, not their "
    "size.",
    approved=True)   # Knut, #182 5850164956

#: The opening of a report whose sheets were printed both ways (B8-1380).
#: Knut: *"The use of the word “drift” for a chart printed raw is not a good
#: wording ... When that is resolved and the message reworded, the rest of
#: the message is ok."* Only "marked “drift”" is reworded: the others are now
#: marked "printed raw" under "Judged against". Shown because
#: the approved sentence it replaces ("It was verified by printing a chart
#: through that profile") is false of the raw sheets.
M_REPORT_MIXED_OPENING = _m(
    "M-REPORT-MIXED-OPENING",
    "The opening of a report of sheets printed both ways",
    "This report judges the profile built in {where}. Some of its sheets were "
    "printed through that profile and compared with the chart's own aim "
    "values; the others, marked “printed raw”, were printed without it. The "
    "measurements it covers are listed under Report Scope.",
    approved=True)   # Knut, #182 5850164956

#: The opening of a report ACROSS RUNS whose sheets were printed both ways
#: (B8-1397). Knut, #182 5850164956, D2: *"Accepted."*, verbatim.
M_REPORT_MIXED_OPENING_RUNS = _m(
    "M-REPORT-MIXED-OPENING-RUNS",
    "The opening of a report across runs of sheets printed both ways",
    "This report judges the profiles built in {where}. Some of their sheets "
    "were printed through their profiles and compared with the charts' own "
    "aim values; the others, marked “printed raw”, were printed without them. "
    "The measurements it covers, and the profile run each comes from, are "
    "listed under Report Scope.",
    approved=True)   # Knut, #182 5850164956 (D2, "Accepted.")

#: The K59 texts as one tuple, in the order PROPOSALS.txt lists them (all
#: fourteen approved by Knut in #182 5850164956).
K59_TEXTS = (
    M_REPORT_RAW_PRINT_INFO, M_REPORT_RAW_JUDGED_AGAINST,
    M_REPORT_RAW_NOT_JUDGED, M_REPORT_RAW_OVERALL,
    M_REPORT_RAW_RESULTS_JUDGED, M_REPORT_RAW_RESULTS_SOME,
    M_REPORT_RAW_RESULTS, M_REPORT_RAW_GUIDE_JUDGED, M_REPORT_RAW_GUIDE,
    M_REPORT_RAW_BASELINE, M_REPORT_RAW_INCOMPARABLE, M_REPORT_RAW_CHANGE,
    M_REPORT_RAW_SHEET, M_REPORT_MIXED_OPENING,
)

#: The two remedies of M-REPORT-DELETE-FAILED (re-challenge R2, #8). "Copy
#: the project" is only a remedy for a report that lives in a project; a
#: report across projects lives in the folder that holds them, and copying
#: one project would leave it behind.
_DELETE_REMEDY_PROJECT = ("Give yourself permission to change it, or copy "
                          "the project somewhere you may write, and try "
                          "again.")
_DELETE_REMEDY_OUTSIDE = ("This report is not kept in a project but beside "
                          "the projects it covers. Give yourself permission "
                          "to change it, or copy {place}, the folder that "
                          "holds those projects, somewhere you may write, "
                          "and try again.")


def report_delete_remedy(report_file, stop=None) -> str:
    """The ``{remedy}`` of M-REPORT-DELETE-FAILED for a report at
    *report_file*: the project's remedy when a folder above it holds a
    ``project.json``, otherwise the one that names the folder holding the
    projects (``<ChromIQ folder>/reports/`` or a ``reports/`` beside the
    projects)."""
    from pathlib import Path
    p = Path(str(report_file))
    for up in list(p.parents)[:6]:
        if (up / "project.json").is_file():
            return tr(_DELETE_REMEDY_PROJECT)
    place = p.parent.parent if p.parent.name == "reports" else p.parent
    return tr(_DELETE_REMEDY_OUTSIDE).format(place=str(place))


#: The reasons `report_gone_line` gives, one module constant each so the
#: extractor resolves ``tr(NAME)`` (challenge C, beta 39).
_GONE_PROJECT = "ChromIQ cannot find this project"
_GONE_RUN = "its profile run was deleted"
_GONE_FOLDER = "its folder is no longer in the project"
_GONE_FILE = "its measurement file is no longer in its folder"
_GONE_PLACE_RUN = "{project}, run {run}, {when}: {why}"
_GONE_PLACE_CAL = "{project}, calibration, {when}: {why}"


def report_gone_line(entry: dict) -> str:
    """One line of M-REPORT-UPDATE-NOT-FOUND's or M-REPORT-UPDATE-LEAVES-OUT's
    ``{missing}``: where the measurement was, when it was measured, and why
    it is not there (an entry of `workflow.measurement_report.update_losses`).
    """
    from pathlib import PurePath
    from core.report_refs import DELETED_RUN_SUFFIX
    reason = str(entry.get("reason") or "")
    if reason == "project":
        why = tr(_GONE_PROJECT)
    elif reason == "run_deleted":
        why = tr(_GONE_RUN)
    elif reason == "file":
        why = tr(_GONE_FILE)
    else:
        why = tr(_GONE_FOLDER)
    parts = list(PurePath(str(entry.get("dir") or "")).parts)
    when = str(entry.get("created") or "").replace("T", " ")[:16]
    if parts and parts[-1] == "cal":
        project = parts[-2] if len(parts) >= 2 else ""
        return "•  " + tr(_GONE_PLACE_CAL).format(
            project=project, when=when, why=why)
    run, project = "", ""
    if "runs" in parts:
        i = len(parts) - 1 - parts[::-1].index("runs")
        project = parts[i - 1] if i >= 1 else ""
        run = parts[i + 1] if i + 1 < len(parts) else ""
    if run.endswith(DELETED_RUN_SUFFIX):
        run = run[:-len(DELETED_RUN_SUFFIX)]
    num = run[3:] if run.startswith("run") else run
    return "•  " + tr(_GONE_PLACE_RUN).format(
        project=project, run=num, when=when, why=why)


# --- APPROVED (Sebastian, 2026-10-08): printing in the state a Photoshop print gets (beta 15)
#: Basti, 2026-10-08: a profiling chart must print in exactly the printer state
#: his image prints from Photoshop get ("Photoshop manages colours"). For a
#: Canon IJ or Epson queue the Print Chart tab now sends that job, and the
#: confirmation window says so instead of "Colour management: Off (forced)",
#: which was not true of a Canon on photo paper. Lines 1 to 5 are the window's
#: rows: three row names and three values (the third row is shown for a Canon
#: only, whose own colour processing depends on the paper profile).
_PRINT_ROW_COLOUR = "Colour management"
_PRINT_ROW_COLOUR_BY_CHROMIQ = "By ChromIQ, as when Photoshop manages colours"
_PRINT_ROW_PAPER_PROFILE = "Paper profile"
_PRINT_ROW_PRINTER_COLOUR = "Printer's own colour processing"
_PRINT_ROW_PRINTER_COLOUR_OFF = "Off for this paper"
_PRINT_ROW_PRINTER_COLOUR_ON = "On for this paper type, as for prints from Photoshop"
M_PRINT_COLOUR_CONFIRM = _m(
    "M-PRINT-COLOUR-CONFIRM",
    _PRINT_ROW_COLOUR,
    "\n".join((_PRINT_ROW_COLOUR_BY_CHROMIQ, _PRINT_ROW_PAPER_PROFILE,
               _PRINT_ROW_PRINTER_COLOUR, _PRINT_ROW_PRINTER_COLOUR_OFF,
               _PRINT_ROW_PRINTER_COLOUR_ON)),
    approved=True)  # Sebastian, 2026-10-08 (DECISIONS_print_fix_beta15, A1)

#: After every print, on both routes, ChromIQ reads the job back from the
#: printing system (CUPS) and says what it carries, in the Print Chart tab's
#: status line. Until beta 14 the macOS dialog route "verified" its colour
#: setting by reading back its own dictionary, which could not fail.
_PRINT_JOB_SENT_PROFILE = (
    "Sent as job {job}. The printing system confirms it carries application "
    "colour matching and the paper profile {profile}.")
_PRINT_JOB_SENT_PLAIN = (
    "Sent as job {job}. The printing system confirms it carries application "
    "colour matching.")
_PRINT_JOB_SENT_TAGGED = (
    "The chart went with that same profile attached, so macOS leaves its "
    "colours unchanged.")
_PRINT_JOB_UNREAD = (
    "Sent. ChromIQ could not read the job back from the printing system, so "
    "its colour settings are not confirmed.")
M_PRINT_JOB_CONFIRMED = _m(
    "M-PRINT-JOB-CONFIRMED",
    "Print job sent",
    "\n".join((_PRINT_JOB_SENT_PROFILE, _PRINT_JOB_SENT_PLAIN,
               _PRINT_JOB_SENT_TAGGED, _PRINT_JOB_UNREAD)),
    approved=True)  # Sebastian, 2026-10-08 (DECISIONS_print_fix_beta15, A2)

# --- PROPOSED: the job read back from CUPS is not what ChromIQ sent (beta 15)
#: The window when the job read back from CUPS does not carry what ChromIQ
#: sent. Replaces the beta 14 window "Colour Management Lock Not Verified".
#: {details} is one line per key, built from the first line below; the second
#: line is added when, besides, the chart could not be given the job's paper
#: profile. Sebastian, 2026-10-08, did not approve it: its opening sentence is
#: wrong when the paper profile is the only problem, which now has its own
#: window, M-PRINT-JOB-UNTAGGED.
_PRINT_JOB_DIFFERS_LINE = "{key}: {got} (ChromIQ sent {want})"
_PRINT_JOB_UNTAGGED_LINE = (
    "The chart could not be given the job's own paper profile, so macOS may "
    "convert its colours.")
M_PRINT_JOB_NOT_AS_SENT = _m(
    "M-PRINT-JOB-NOT-AS-SENT",
    "The print job is not what ChromIQ sent",
    "The job was sent, but the printing system shows other colour settings "
    "on it than ChromIQ asked for:\n\n{details}\n\n"
    "The sheet may not carry the chart's own colours, and a measurement of it "
    "would not describe your printer. If it has not printed yet, cancel it in "
    "the printer's queue and print again.",
    approved=False)

# --- PROPOSED: the chart could not be given the job's paper profile (beta 15)
#: The macOS dialog route tags the chart with the paper profile the job prints
#: with, so macOS leaves its colours alone. When that profile could not be read,
#: or the job read back from CUPS uses another one, and nothing else on the job
#: differs, this window says so (review 2026-10-08: the M-PRINT-JOB-NOT-AS-SENT
#: wording, "other colour settings than ChromIQ asked for", was wrong here).
M_PRINT_JOB_UNTAGGED = _m(
    "M-PRINT-JOB-UNTAGGED",
    "The chart may not print with its own colours",
    "The job was sent, but ChromIQ could not give the chart the paper profile "
    "this job prints with. macOS may therefore change the chart\u2019s colours "
    "on the way to the printer, and a measurement of that sheet would not "
    "describe your printer.\n\n"
    "If it has not printed yet, cancel it in the printer\u2019s queue and print "
    "again. If this message comes back, turn off \u201cUse default macOS printer "
    "dialog\u201d in Preferences and print from the Print Chart tab directly.",
    approved=False)

# --- PROPOSED: a printer whose paper profiles ChromIQ does not know (beta 15)
#: Basti, 2026-10-08: on the direct route ChromIQ sends the paper profile the
#: vendor's print dialog would choose for the medium. It knows that for the
#: models whose driver tables it reads or which it has measured, and learns it
#: from the user's own prints through the macOS dialog. For any other Canon or
#: Epson model it must not guess silently: this window says so before printing
#: and offers the dialog. {printer} is the queue, {medium} the paper type as the
#: driver names it, {profile} the driver's standard setting for the paper profile (the PPD's
#: default; Epson names it "None"), which a print sent
#: anyway carries. The three buttons are the lines after the body.
_PRINT_UNKNOWN_BTN_DIALOG = "Use the macOS Print Dialog"
_PRINT_UNKNOWN_BTN_ANYWAY = "Print Anyway"
M_PRINT_PAPER_PROFILE_UNKNOWN = _m(
    "M-PRINT-PAPER-PROFILE-UNKNOWN",
    "ChromIQ does not know this printer\u2019s paper profiles yet",
    "ChromIQ does not know which paper profile the driver of {printer} chooses "
    "for the paper type \u201c{medium}\u201d. A print from Photoshop gets that "
    "paper profile from the printer\u2019s own print dialog, and the chart has "
    "to print in the same state.\n\n"
    "Print this chart through the macOS print dialog and pick the same paper "
    "type there. The driver then chooses the paper profile itself, and ChromIQ "
    "remembers its choice, so later charts for this printer and paper type can "
    "go straight to the printer.\n\n"
    "If you print straight to the printer anyway, the chart goes with the "
    "driver\u2019s standard setting for the paper profile ({profile}), which "
    "may not be what your prints from Photoshop get on this paper.",
    approved=False)

# --- APPROVED: the quality row of the Print Chart tab (beta 16) ---------------
#: Basti, 2026-10-09: he prints his photos at the highest quality the Canon print
#: dialog allows for the paper (its Custom slider at the top). The direct route
#: sent the dialog's standard quality and the tab had no Canon quality row. It
#: now offers the qualities the driver allows for the chosen paper, preselects
#: the one his last print through the macOS dialog used on that paper (else the
#: dialog's standard), and says, under the row, that photos must be printed at
#: the same quality. Line 1 follows the bold headline; line 2 is added when the
#: preselection came from his last dialog print; lines 3 and 4 mark the
#: qualities in the list ({quality} is the driver's own name for it).
_PRINT_QUALITY_WHY = (
    "The profile fits only prints made at the quality its chart was printed with.")
_PRINT_QUALITY_LEARNED = (
    "Chosen as in your last print on this paper through the macOS print dialog.")
_PRINT_QUALITY_HIGHEST = "{quality} (highest)"
_PRINT_QUALITY_STANDARD = "{quality} (standard)"
M_PRINT_QUALITY = _m(
    "M-PRINT-QUALITY",
    "Print your photos at this quality too",
    "\n".join((_PRINT_QUALITY_WHY, _PRINT_QUALITY_LEARNED,
               _PRINT_QUALITY_HIGHEST, _PRINT_QUALITY_STANDARD)),
    approved=True)  # Sebastian, 2026-10-09 (DECISIONS_beta16_quality.md, rows 1-4)

CATALOGUE = {m.id: m for m in (
    M_LIMIT_RECOMMENDED,
    M_CAL_FOUND_ENGINE,
    M_REPORT_CHART_MISMATCH, M_REPORT_CHART_MISMATCH_LAYOUT,
    M_REPORT_CHART_MISMATCH_NO_GREY,
    M_THRESHOLDS_NOT_CERTIFICATION, M_REPORT_DELETE,
    M_REPORT_UPDATE_OR_NEW, M_REPORT_UNCHANGED_UPDATE_OR_NEW,
    M_REPORT_WORKED_OUT_DIFFERENTLY_UPDATE_OR_NEW,
    M_REPORT_NEW_REPORT_SETTINGS,
    M_REPORT_ONE_PAGE_ONE_DATE,
    M_REPORT_UPDATE_NOT_FOUND, M_REPORT_UPDATE_LEAVES_OUT,
    M_REPORT_UPDATE_NOTHING_LEFT,
    M_REPORT_DELETE_FAILED, M_REPORT_NOT_WRITABLE,
    M_RUN_DELETE_REPORTS_LOCKED,
    M_REPORT_SCOPE_RUN_DELETED, M_REPORT_NO_PAPER_PATCH,
    M_REPORT_PAPER_WHITE_FROM_PROFILE,
    M_REPORT_JUDGED_ABSOLUTE_NO_PAPER_WHITE,
    M_REPORT_STRIP_CORNERS_PREDICTED, M_REPORT_STRIP_CORNERS_IDEAL,
    M_REPORT_SOLIDS_PREDICTED, M_REPORT_PAPER_AGAINST_PROFILE,
    M_REPORT_THROUGH_PROFILE,
    M_PREVIEW_AS_PRINTED, M_PREVIEW_PAPER_WHITE,
    M_REPORT_WORKED_OUT_EARLIER, M_REPORT_NOT_WORKED_OUT,
    *K59_TEXTS, M_REPORT_MIXED_OPENING_RUNS,
    M_REPLACE_PARTIAL, M_REPLACE_COMPLETE, M_TI3_MISMATCH,
    M_REPLACE_UNCOUNTABLE,
    M_PRINT_COLOUR_CONFIRM, M_PRINT_JOB_CONFIRMED, M_PRINT_JOB_NOT_AS_SENT,
    M_PRINT_JOB_UNTAGGED, M_PRINT_PAPER_PROFILE_UNKNOWN, M_PRINT_QUALITY,
    M_IMPORT_REPLACE_CONFIRM, M_IMPORT_REPLACE_PROJECT_CONFIRM,
    M_IMPORT_REPLACED_KEPT,
    M_IMPORT_NOT_OPENED, M_IMPORT_FOLDER_EXISTS,
    M_IMPORT_REPLACE_FOLDER_CONFIRM, M_IMPORT_REPLACE_FOLDER_FAILED,
    M_IMPORT_NOT_A_CHART,
    M_CHART_PROFILING, M_CHART_W4, M_CHART_VERIFY, M_CHART_NOPAGES,
    M_CHART_CORRUPT,
    M_PREVIEW_PAUSED, M_PROFILE_VERIFY,
    M_VERIFY_EARLIER_PROFILE, M_VERIFY_EARLIER_PROFILE_KEEP_CHART,
    M_VERIFY_EARLIER_PROFILE_NO_CHART,
    M_VERIFY_CHART_EARLIER_PROFILE, M_VERIFY_EARLIER_ARCHIVED_HERE,
    M_VERIFY_NO_PROFILE, M_VERIFY_NO_CHART, M_BUILD_ELSEWHERE,
    M_CM_NO_CCTIFF, M_CM_CONVERT_FAILED, M_CM_PROFCHECK_CONVERTED,
    M_CM_K_CHART_THROUGH, M_CM_RAW_UNCALIBRATED,
    M_CAL_APPLIED_TWICE, M_CAL_CALIBRATED_TWICE,
    M_CAL_TABLE_REPAIRED, M_CAL_TABLE_DAMAGED,
    M_PATCHSET_CAL_INKS, M_VIEW_RGB_ONLY,
    M_PATCH_COLOUR_RANGE,
    M_PATCH_EXPECTED_PREDICTED,
    M_PATCH_NEIGHBOUR, M_PATCH_NEIGHBOUR_VARIANTS, M_PATCH_LIMIT,
    M_MEASURED_SUSPECTS,
    M_PATCH_CORRECTED, M_PATCH_CORRECTED_VARIANTS, M_PATCH_UNSETTLED,
    M_VERIFY_CREATE_NO_PROFILE, M_GAMUT_NO_PROFILE,
    M_IMPORT_MISMATCH, M_IMPORT_DATE_TAKEN, M_IMPORT_DONE,
    M_IMPORT_DONE_PROFILING,
    M_IMPORT_DEVICE_FROM_CHART,
    M_VERIFY_SAVED, M_HOW_PRINTED,
    M_NO_INSTRUMENT, M_NO_INSTRUMENT_FAST, M_NO_INSTRUMENT_NONE,
    M_OVERLAY_NO_MEASUREMENT, M_ALL_STRIPS_PATCHES_LEFT,
    M_UNREAD_NEXT_OR_JUMP_STRIP, M_UNREAD_NEXT_OR_JUMP_PATCH,
    M_STRIP_READ_TWICE,
    M_CR_STRIPS, M_CR_START_OVER, M_CR_PRECONDITIONING,
    M_ENGINE_FELL_BACK,
    M_CHART_PATTERN_REFUSED, M_CHART_LOCATIONS_UNREADABLE,
    M_CHART_LEGACY_STOCK, M_CHART_LEGACY_ENDED,
    M_PATCHSET_MISSING,
    M_PATCHSET_KEPT_UNCHECKED,
    M_VERIFY_NO_CONTROL_STRIP, M_VERIFY_PREFLIGHT,
    M_VERIFY_UNCHECKED_METRICS, M_VERIFY_SOLIDS_REASON,
    M_REPORT_PATCH_COUNTS_DIFFER,
    M_PROJECT_EXISTS,
    M_PROJECT_REPLACE_CONFIRM,
    M_PROJECT_REPLACE_FAILED,
    M_PROJECT_FOLDER_RENAMED, M_PROJECT_FOLDER_RENAME_FAILED,
    M_CR30_STOCK_READER,
    M_CR30_READ_ENDED, M_CR30_INSTRUMENT_GONE, M_CR30_PATCH_GAVE_UP,
    M_CR30_CALIBRATE, M_CR30_CALIBRATE_BLACK, M_CR30_MAGNET,
    M_CR30_HOW_TO_MEASURE, M_CR30_READ_FAILED,
    M_CR30_LEARN_TILE, M_CR30_TRIGGER_NOT_ARMED,
    M_INSTRUMENT_BUSY,
    M_CAL_REQUESTED, M_CAL_REQUESTED_DONE, M_CAL_REQUESTED_FAILED,
    M_REPORT_NOT_SAVED,
    M_CAL_REPLACE_CHART, M_CAL_REPLACE_MEASURED, M_CAL_ARCHIVED_HERE,
    M_SPOT_CLEAR, M_SPOT_UNSAVED, M_SPOT_CR30_GONE, M_SPOT_CR30_EARLY_PRESS,
    M_SCAN_REF_SHORT, M_SCAN_REF_DISAGREES, M_SCAN_CLIPPED,
    M_SCAN_LOADED, M_SCAN_DIAGNOSTIC,
    M_SCAN_SHOT_EMPTY, M_SCAN_TARGET_CHANGED,
    M_SCAN_DARK, M_SCAN_FIT_UNSUPPORTED, M_SCAN_SELFCHECK_UNUSABLE,
    M_SCAN_ALIGN_AMBIGUOUS, M_SCAN_ALIGN_NO_MATCH,
    M_SCAN_ALIGN_NOT_FOUND, M_SCAN_ALIGN_NOT_FOUND_HEX, M_SCAN_ALIGN_NO_FIT,
    M_SCAN_ALIGN_NO_GEOMETRY, M_SCAN_ALIGN_NO_BETTER, M_SCAN_ALIGN_NOT_SEATED,
    M_SCAN_ALIGN_PLACED_UNCHECKED, M_SCAN_ALIGN_PLACED_NOT_SEATED,
    M_SCAN_ALIGN_DONE, M_SCAN_ALIGN_NO_INPUT,
    M_SCAN_CONVERTED, M_SCAN_FIT_TOO_FAR,
    M_SCAN_PROFILE_ARCHIVED,
    M_SCAN_WP_DEFAULT,
    M_CHART_SLOW_NO_PROFILE,
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
