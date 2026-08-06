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
| Unexpected Color Response | Both | Patch reading looks off |
| Strip may be misaligned | Strip reading | Strip read failed |
| Strip read interrupted | Strip reading | Strip read failed |
| Patches still unread | Both | Strip read failed |
| Averaging failed | Both | Strip read failed |
| Calibration required | Both | Instrument error |
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

## 5. Related documents

- [`measurement_exit_strategy.md`](measurement_exit_strategy.md) — the same windows, from the point of view of how each one ends a session
- [`unified_measurement_management.md`](unified_measurement_management.md) — §M, the text each window shows
