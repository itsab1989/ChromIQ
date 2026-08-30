# Basti's Bluetooth timing observation — 2026-08-30, for the next agent

Reported while the beta-1 fixes were being made. **Not addressed by them**, and
the distinction matters, so it is written down before it is acted on.

> *"i just tried blutooth again and i don't know if it is much faster. when i
> click the button to calibrate against white i think this is the first time my
> mac tries to connect to the device and thus it takes a while. in that time the
> pop up window is gone and nothing indicates something is still going on —
> something we might have to change later. however once white is finished and i
> calibrate black the click on calibrate immediately makes the device beep two
> times in a row but then it takes some time again until the next pop up appears
> that tells me to start the measurement"*

## Why this is not the thing that was just fixed

The BLE speed fix (blocker B2) removes polling that ran *after* the instrument
had already answered — about 1.5 s per calibration. His two gaps are somewhere
else entirely:

1. **Before the first command**: the Mac's BLE connection is established at the
   moment he clicks Calibrate, and that is the first connection of the session.
   No poll loop is involved; nothing has been sent yet.
2. **After the device has finished**: the instrument beeps twice — it is done —
   and the next window still takes noticeable time to appear.

**So the fix cannot have removed either gap, and a beta note claiming Bluetooth
calibration is now fast would be false.** The honest claim is narrower: the poll
loop no longer waits past the instrument's own answer.

## The interface fault, which is the more serious half

> *"in that time the pop up window is gone and nothing indicates something is
> still going on"*

The window closes on the click, and then nothing. For as long as the connection
takes, the app shows a user who has just acted an interface that looks idle —
and the instrument has not beeped yet either, so there is no cue anywhere. He
cannot distinguish "connecting" from "the click did nothing", which is the
condition under which a user clicks again.

## To establish before designing a remedy

- **Where does the time actually go?** Instrument each phase separately —
  connect, write, first notification, device beep, window shown. Guessing which
  of the two gaps dominates is how the last round produced a placebo.
- **Is the second gap ours or the device's?** The beep is the instrument saying
  it has finished acquiring; whether the remaining wait is our poll budget, the
  BLE stack, or the device still writing is unmeasured.
- **Would connecting earlier help?** If the connection is made when the
  instrument is selected rather than when Calibrate is clicked, the first gap
  moves off the critical path — but it moves onto something else, so check what.
- Any progress indication is new user-facing text and goes through §M-PROPOSED
  before it is written into a tab.

⚠ Do not report a timing improvement to him without a measurement taken on his
own unit over Bluetooth. The last Bluetooth speed claim was made from reasoning
and was wrong.

---

# Second observation, same session: the calibration graphics

> *"in this window and the black calibration window can you make the two
> graphics placed on top of each other instead of next to each other? and make
> them a little bigger in the process?"*

**Done** — `ui/cr30_pictograms.py::steps_pair` now stacks the two steps
vertically and each is about a quarter larger. The text beside them is a tall,
narrow column, so the wide pair left the picture small and the space beneath it
empty; stacked, the pair fills the height the text already occupies, and reading
downwards matches the order the steps are taken in.

## One thing NOT changed, for him to rule on

The current step is marked by a solid underline beneath it. For step 1 that
doubles as the surface the instrument is resting on, which is why it sits where
it does. For step 2 — "pointing at nothing", drawn as a dashed line — the solid
underline lands just below the dashes and can read as a surface, which is the
opposite of what that step means.

This is **pre-existing**: it is equally true of the side-by-side version now on
his screen, and he has already approved that graphic ("i like the step pairs
from the mockups"). So it was left alone rather than redesigned in passing. If
it should change, the cheap fix is to move the current-step marker somewhere it
cannot be read as ground — a short accent bar down the left of the current cell,
for instance.
