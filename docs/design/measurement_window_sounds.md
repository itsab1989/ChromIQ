# Measurement windows and their sounds

> **These specifications are binding.** Knut, 2026-08-06: *"These must always be
> consulted on changing code so that behaviour defined is not violated. And if
> faults are found that do not match with the specification [it] must be
> reviewed and approved."*

Issue #130 / #131. Knut, 2026-08-06:

> *"Also make sure all the warning messages implemented for ChromIQ chartread
> engine have the correct defined sound before/upon loading the window. Sounds
> used for messages are specified in list in help icon in preferences sounds
> tab. These tables to be added in the design specification."*

**These tables are generated from `core/measure_windows.py`, which is also what
the Preferences → Sounds help card renders.** One source, so the specification,
the help card and the code cannot drift apart — an earlier version of the help
card was a hand-written second copy and the two disagreed.

Sound names are the ones in Preferences → Sounds, never the internal
identifiers.

## 1. Windows

| Window | Reading mode | Sound |
|---|---|---|
| Strip read failed | Strip reading | Slow down, or Strip read failed — ChromIQ reads Argyll's own wording and picks the one that fits (see the third table) |
| Patch read failed | Patch by patch | Strip read failed |
| Strip read quickly | Strip reading | Slow down |
| Wrong strip read | Strip reading | Strip read failed |
| Unexpected Colour Response | Both | Patch reading looks off |
| Strip may be misaligned | Strip reading | Strip read failed |
| Strip read interrupted | Strip reading | Strip read failed |
| Patches still unread | Both | Strip read failed |
| Averaging failed | Both | Strip read failed |
| Some patches are still not read | Both | Instrument error |
| Strip read twice | Strip reading | Instrument error |
| Calibration required | Both | Instrument error |
| Calibrate the instrument (K or Calibrate) | Both | No sound |
| The calibration did not succeed (K or Calibrate) | Both | Instrument error |
| Confirm abort | Both | Instrument error |
| Instrument disconnected | Both | Instrument error |
| No instrument found | Both | Instrument error |
| Instrument Not Available (in use by another program) | Both | Instrument error |
| Instrument in Wrong Position | Both | Instrument error |
| Instrument Not Accessible (claimed by a virtual machine) | Both | Instrument error |
| Instrument Failed to Initialize | Both | Instrument error |
| Instrument Type Mismatch | Both | Instrument error |
| Correction File Failed to Load | Both | Instrument error |
| Instrument Mode Rejected | Both | Instrument error |
| Instrument Error (anything else the instrument reports) | Both | Instrument error |
| All strips read / All patches read | Both | Measurement finished |

### 1a. The calibration the user asks for (#182, 2026-10-03)

**Confirmed by:** Knut, 2026-10-03 (#182 5965735823), for the first of the two
rows: a calibration the user asked for during a measurement, with K or the
optional Calibrate button, is not an error, so its placement window
(M-CAL-REQUESTED) plays **no sound**. "Calibration required" keeps Instrument
error, because that one interrupts the user. `tests/test_every_window_sounds.py`
holds both.

⏳ **Awaiting confirmation.** **Confirmed by:** *nobody yet.* The second row,
the window for such a calibration that did not succeed
(M-CAL-REQUESTED-FAILED), plays **Instrument error**: reading is locked until
a calibration succeeds, so it is a failure the user has to act on. Knut's
ruling covered the request, not its failure, so this value is ours until he
names one.

## 2. Sounds that mark an event rather than a window

| Event | Reading mode | Sound |
|---|---|---|
| A patch was read and looks right | Patch by patch | Patch read OK |
| A patch was read and looks off | Patch by patch | Patch reading looks off |
| A strip was accepted | Strip reading | Strip read OK |
| A strip was accepted but read quickly | Strip reading | Slow down |
| The measurement finished | Both | Measurement finished |
| A profile finished building | — | Profile build finished |

## 3. How a strip failure is classified

Row 1 of §1 broken out. Which of the two sounds a failed strip earns depends on
what ArgyllCMS says went wrong, because telling somebody to slow down when the
fault was positioning sends them the wrong way.

| What the reader reports | What it means | Sound |
|---|---|---|
| Not enough samples per patch - Slow Down! | Too fast — ArgyllCMS says so itself | Slow down |
| Reading is too short | Too fast — the whole swipe was over too quickly | Slow down |
| Not enough patches | Too fast — the patches were too short in readings to tell apart | Slow down |
| Too many patches | Hesitant, not hurried — extra transitions were found, so telling you to slow down would be exactly the wrong advice | Strip read failed |
| Swipe didn't start and end on the media | Positioning, not speed | Strip read failed |
| Light level is too low / too high | The instrument or the sheet, not speed | Strip read failed |
| Reading is inconsistent | Uneven rather than simply quick — blaming speed could send you the wrong way | Strip read failed |

## 3a. The ending window is NOT here, on purpose, and one window is MISSING

⏳ **Awaiting confirmation.** **Confirmed by:** *nobody yet.*

**MISSING, and not fixed here.** `TabMeasure._show_cr30_read_failed_window`
("That reading did not come through") is a measurement window with **no row and
no sound**, measured on screen 2026-09-18. It is the one window in the app built
*because* a failure was going unnoticed: the owner, 2026-08-30, *"a message like
this would be better in a pop up so the user is aware of it instead of ruining a
whole measurement session when this is unnoticed"*. A CR30 session is spent
looking at the sheet and the instrument, so a silent window is that same failure
in a new shape.

The fix is one row in `core/measure_windows.py` plus one `_cue_window` call, and
it was built and driven (the window sounded once per patch, and stayed silent on
the suppressed second refusal of the same patch, keeping rule W-2). It was then
**withdrawn**, because the row is a new user-facing string and translating it
into thirteen languages was not something that round could finish; an untranslated
row would have raised every language's ledger by one. The nearest existing row is
2, *Patch read failed → Strip read failed*, and a CR30 chart is read patch by
patch, so that is the likely value — **but which sound it plays is Knut's to
name**, and that is the open question here.

**The window that is NOT here, on purpose.** *"Keep what you have measured so
far?"* (M-END) has no row, and it plays nothing. Until 2026-09-18 it cued
*Strip read failed* on **every** ending: Stop, Cmd-Q, Give Up, a disconnection,
a CR30 loss, the magnet warning, No Instrument Found, Confirm Abort and
*"Patches still unread"*. Two things were wrong with that.

* It said *Strip read failed* when no strip had failed. On the Stop and Cmd-Q
  routes nothing has failed at all: the user pressed a button.
* It played the row-8 sound **twice**. *"Patches still unread"* cues
  *Strip read failed* from the top of its own slot and then reaches M-END two
  lines later; `play_window` has no de-duplication (`core/sound.py`), so the
  second play restarts the same `QSoundEffect` and truncates the first. On the
  eight routes that arrive from a failure window, that window's own cue and
  M-END's played back to back.

Every route into M-END comes either from a window that has already sounded or
from a button the user has just pressed, so the removal leaves nothing
unannounced. **If a sound of its own is wanted for the ending window, that is a
new row here and Knut's to name.**

## 4. The rules these tables imply

**W-1 · The sound plays as the window opens, not after it closes.** `_cue_window`
is called from the **top** of the slot that raises the window. A modal dialog
runs its own event loop inside the slot, so a cue placed after `.exec()` is not
heard until the user has already dismissed the window — which is how a cue once
ended up playing on the next button press instead (beta.35, beta.43).

**W-2 · A window that is suppressed makes no sound.** Only one measurement
window is allowed at a time; when a second failure is swallowed by that guard,
the cue must be swallowed with it. So the cue goes **after** the
one-window-at-a-time check, never before.

**W-3 · The cue is not gated on a read being in progress.** Several of these
windows — the instrument ones especially — are raised only after the reader has
exited, by which time a gated `play()` would drop the sound. `play_window` is
the same sound without that gate.

**W-4 · A cue that names a sound `core.sound` does not define is silent, not a
crash.** `_cue_window` swallows the error so a missing sound can never block a
window. That makes a typo invisible at runtime, so it is a test instead.

**W-5 · Every row here is checked against the code.**
`tests/test_every_window_sounds.py` maps each handler to the sound this table
promises and fails if it is missing, wrong, stranded behind the modal, or names
a sound that does not exist. The audit that produced it found two windows
opening in silence — **Instrument in Wrong Position** and **Instrument Error
(anything else the instrument reports)** — both fixed in beta.164.

## 4a. Confirmed behaviour: the instrument's ready beep and the strip clock (#202)

**Confirmed by:** Knut, 2026-10-02 (#202 5943245399 / 5943350639)

After the instrument's button is pressed, the instrument warms its lamp and then
beeps; the beep is the moment it starts measuring. Knut's rulings:

- **R-202-1 · The beep stays ArgyllCMS's own.** It is not one of ChromIQ's
  sounds and is not in the tables above (Q2: *"keep current design"*). It plays
  at ArgyllCMS's own moment, about 0.7 s after the press on an i1Pro (200 ms
  plus the 0.5 s lamp time), not earlier (5943350639).
- **R-202-2 · A strip is timed from the beep** (Q3: *"the timing should start at
  the beep, as this is when measurement start happens"*). The lamp warm-up
  between the press and the beep is not counted. With stock ArgyllCMS chartread
  there is no strip timing at all, as before: it reports no start.
- **R-202-3 · The help says so.** Preferences ▸ Measurement explains that a
  strip is timed from the beep, and mentions the lamp warm-up between the
  button press and the beep (Q3).
- **R-202-4 · No other message changes** (Q1: *"current wording is good
  enough"*).
- **R-202-5 · Every instrument in the Instrument selection is timed by its own
  row** in Preferences ▸ Measurement ▸ Per instrument, except the SpectroScan
  and the CR30.
- **R-202-6 · The SpectroScan and CR30 rows are locked.** They do not read
  strips, so their "Readings per second", "Patches per strip" and "Minimum
  readings per patch" fields are disabled, showing their current values, to
  show that they are not configurable.

## 4b. "Strip read twice" plays Instrument error

**Confirmed by:** Knut, 2026-10-03 (#182 [5963903650](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5963903650) Q5 approved the window; [5963044182](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5963044182) ruled its sound for the first such window: *"When the window appears it is supposed to get the attention of the user, so the 'Instrument error' sound can be also used as a 'attention' sound. Use this sound."*)

The window *"Was a strip read twice?"* (M-STRIP-READ-TWICE, unified
measurement management §11b) interrupts a read to ask the user something, like
*"Some patches are still not read"*, so it plays **Instrument error** as it
opens (`TabMeasure._strip_read_twice_window`, row "Strip read twice" in §1).
Rules W-1 and W-2 apply: the cue is at the top of the slot, and a question that
is never opened (the measurement ended first) plays nothing.

## 4c. The earlier-profile window plays nothing

**Confirmed by:** Knut, 2026-10-03 (#182 [5964076758](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5964076758) Q5, *"OK"* to "No sound").

The window that opens when Verification is chosen for a run whose profile was
replaced (M-VERIFY-EARLIER-PROFILE, M-VERIFY-EARLIER-PROFILE-KEEP-CHART,
M-VERIFY-EARLIER-PROFILE-NO-CHART, M-VERIFY-CHART-EARLIER-PROFILE; unified measurement management §6f) is not a
measurement window and plays no sound (`ui/earlier_profile_offer.py`).

## 5. Related documents

- [`measurement_exit_strategy.md`](measurement_exit_strategy.md) — the same windows, from the point of view of how each one ends a session
- [`unified_measurement_management.md`](unified_measurement_management.md) — §M, the text each window shows
