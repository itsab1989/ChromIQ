# Every window that can end a measurement, and how it ends it

> **These specifications are binding.** Knut, 2026-08-06: *"These must always be
> consulted on changing code so that behaviour defined is not violated. And if
> faults are found that do not match with the specification [it] must be
> reviewed and approved."* So: read the relevant document before changing code
> in the area it covers, and if you find behaviour that contradicts it, **report
> it and get the change approved** rather than quietly correcting one side to
> match the other.

Issue #130. Knut, beta.150:

> *"List all windows during measurement (separate tables for stock chartread
> and chromIQ chartread, and for each table, separate columns for strip mode
> and patch-by-patch mode) that has a choice to exit/stop/save a measurement
> session, then list the exit command used for each button in each window,
> commenting what each command does. Make also note if any of the exit methods
> does not follow the single exit method for our model."*

Read from the code, not from memory: every row below names the handler it came
from, and the tests in `tests/test_unified_ending.py` and
`tests/test_knut_beta147_batch.py` hold the important ones in place.

---

## The single exit, in one paragraph

**Every way out of a session goes through `_confirm_end_of_session`**, which is
§1/§1a of the model. It asks nothing when nothing has been read — it says
*"Nothing was measured, so nothing was saved"* and ends (**M-END-EMPTY**) — and
otherwise raises **"Keep what you have measured so far?"** with three buttons:

| Button | What it does |
|---|---|
| Save and stop | `send_save_partial_and_quit()` — 'q', then a second 'q' at the give-up prompt, which is what makes chartread write the `.ti3` and exit |
| Discard and stop | `abort()` — kills the reader; the archived measurement is put back by `MeasurementSession.finish()` |
| Keep measuring | nothing; the window closes and the session continues |

A window that ends a session any other way is a second exit, and that is the
thing this document exists to catch.

---

## How the two readers differ

| | Stock ArgyllCMS chartread | ChromIQ chartread (the engine) |
|---|---|---|
| how ChromIQ hears about a prompt | printed prose, matched by regex (`_handle_line`) | typed JSON events (`_handle_engine_line`) |
| what a keystroke is | a character written to stdin | a JSON command, mapped by `KEY_TO_COMMAND` |
| Save Partial | **not available** — `q` at a misread prompt is "give up" and `chartread.c:1654` returns without writing | two `q` commands; the helper calls `cq_write_ti3_atomic()` before giving up |
| a key with no mapping | reaches chartread as itself | **is dropped silently** — see `KEY_TO_COMMAND`; every key a window can send must be in it |

That last row is why the tables list the raw key: on the engine the key is only
a name for a command, and a name with no command behind it is an instrument
that appears to stop responding.

### The rule that follows from all of this

**A window must not depend on which reader is running.** The two parsers are
separate — `_handle_line` for stock, `_handle_engine_line` for the engine — and
a condition recognised by only one of them raises its window for only half the
users. The stock half working is what makes this invisible: the feature is
demonstrably there, and a test at the handler passes either way.

It has now happened four times, and each was found by a user rather than by us:
the unmapped keys in `KEY_TO_COMMAND` (beta.138), the startup failure with no
window (beta.141), the abort window (beta.160, note 4), and — found by auditing
every signal after that last one, rather than by a fifth report — the three
startup failures the beta.141 fix left behind: **wrong instrument capability**,
**CCMX/CCSS load failure** and **instrument mode failure**. All three are
printed as prose by the helper, so all were reachable on the engine, and none
raised a window there.

Anything both readers can produce belongs in code both parsers call;
`_check_startup_failures` is that place for startup failures.
`tests/test_both_readers_raise_the_same_windows.py` enforces it two ways: it
feeds each reader the exact line the helper prints and requires identical
signals out of both, and it fails structurally if one of these signals is
emitted from the stock parser alone. **Ask what raises a handler, not only
whether the handler works.**

---

## Table 1 — ChromIQ chartread (the engine)

| Window | Button | Sends | What that does | Single exit? |
|---|---|---|---|---|
| **Stop button** (not a window) | — | `_end_session(_confirm_end_of_session(END_STOP))` | the ending itself | ✅ |
| **Keep what you have measured so far?** | Save and stop | `send_save_partial_and_quit()` | `q`, then `q` again at the give-up prompt | ✅ the ending |
| | Discard and stop | `abort()` | kills the reader; the archive is restored | ✅ the ending |
| | Keep measuring | — | returns `None`; the session continues | ✅ |
| **No Instrument Found** (M-NO-INSTRUMENT) | OK | `_end_session(_confirm_end_of_session(END_FAILURE_WINDOW))` | the ending | ✅ *(fixed in beta.154; it used to appear only after the process had already exited)* |
| **Instrument Error** (wrong dial, etc.) | Retry | `\r` → `{"cmd":"ok"}` | try the same read again | ✅ not an exit |
| | Give Up | `GIVE_UP_PENDING` → the ending, then its key | Esc/`q` → `{"cmd":"quit"}`, or the save chain | ✅ |
| **Wrong Strip Read** | Use Anyway | `\r` | keep the reading as the expected strip | ✅ not an exit |
| | Retry | `space` → `{"cmd":"retry"}` | discard and re-scan | ✅ not an exit |
| | Give Up | `GIVE_UP_PENDING` | as above | ✅ |
| **Unexpected Response** | Use Anyway / Retry / Give Up | as Wrong Strip Read | | ✅ |
| **Strip Read Interrupted** | Continue / Give Up | `\r`, `GIVE_UP_PENDING` | | ✅ |
| **Place the sheet** (XY mode) | Continue / Give Up | `\r`, `GIVE_UP_PENDING` | | ✅ |
| **Patch Read Failed** | Retry | `retry` | | ✅ not an exit |
| | Skip Patch | `skip` | | ✅ not an exit |
| | Save Partial & Quit | `send_save_partial_and_quit()` | the two-`q` chain | ⚠️ **note 1 — left as it is, by his ruling** |
| **Unread patches remain** | (three buttons) | `_end_session(choice)` | the ending | ✅ |
| **Abort?** (Esc pressed) | Yes | `n` to chartread, then the ending | chartread leaves its own question; ours runs | ✅ *(beta.156; **unreachable until beta.160** — see note 4)* |
| | No | `n` | keep measuring | ✅ |
| **Calibration required** | OK / Skip / Cancel | `\r` / `s` / `\x1b` | the instrument's own calibration prompt | ⚠️ **see note 3** |
| **Calibrate your CR30 before measuring** (M-CR30-CALIBRATE) | Calibrate now | ChromIQ triggers the instrument's calibration | not an exit — the session has not begun | ✅ *(see note 5)* |
| | Cancel | a bare `return` from `_on_start` | the measurement never starts | ✅ *(see note 5)* |
| **The instrument stopped answering** (M-CR30-INSTRUMENT-GONE) | (three buttons) | `_end_session(choice)` | the ending | ✅ *(see note 6)* |
| **All Strips Read / All Patches Read** | Go to … Tab | `d` | "done" — chartread writes and exits normally; keeps the measurement and moves on | ✅ not a failure exit |
| | Re-read … | — | the window closes; the session continues | ✅ |
| | Close | — | raises **"Keep what you have measured so far?"** — the single exit | ✅ |

**The Close row, corrected 2026-08-14.** It read *"keeps the measurement, goes
nowhere"*, which described the **Go to … Tab** button rather than Close. Knut, on
being asked which of the two was right: *"(A) Close should raise the 'Keep what
you have measured so far?' window. However, the description 'keeps the
measurement, goes nowhere' is still correct, because it is referring to the other
button that says to jump to build profile tab."* So the table was not stale — it
was read against the wrong button, and a message written from that reading would
have told users to press something that does not do what it says.

## Table 2 — stock ArgyllCMS chartread

Same windows, same buttons; three differences, all in what the key means.

| Window | Button | Sends | Difference from the engine |
|---|---|---|---|
| **Keep what you have measured so far?** | Save and stop | the strip-menu route: retry → `d` → `y` | the two-`q` chain would **throw the readings away** here: stock `q` at a misread prompt is "give up" and never writes |
| **Patch Read Failed** | Save Partial & Quit | same | same reason |
| **Instrument Error / Wrong Strip / Interrupted** | Give Up | `\x1b` written to stdin | on the engine it is `{"cmd":"quit"}`; the meaning is the same |
| everything else | | identical | |

### Strip mode vs patch-by-patch — where they genuinely differ

| | Strip mode | Patch-by-patch |
|---|---|---|
| Wrong Strip Read, Strip Read Interrupted | yes | never raised |
| Patch Read Failed (Retry / Skip Patch) | never raised | yes |
| a wrong-dial failure leaves the reader… | **at the strip menu** — so a single quit interrupts the armed read and the reader answers with a *second* prompt | **at a retry prompt** — one quit ends it |
| the completion window | All Strips Read | All Patches Read |

That first difference is the whole of the beta.147/148 faults: the same Give Up
needed one key in one mode and two in the other, and the second key was being
swallowed by the guard that stops the user being asked twice.

---

## Notes — the ones that are not yet the single exit

The first three were put to Knut and he ruled on each (beta.155); the
fourth is new in beta.160 and its open half is with him.

**Note 1 · "Save Partial & Quit" on the Patch Read Failed window** calls
`send_save_partial_and_quit()` directly rather than going through
`_confirm_end_of_session`, so it never offers Discard or Keep measuring. **His
ruling: leave it.** *"As long as 'Save Partial & Quit' calls the save chain
directly, that is ok, since we know it works today. We do not want to touch
anything what works right now, unless it is dangerous."* Recorded as a known
second door rather than changed. (He also noted that Retry on these windows is
the same thing as "Keep measuring", which it is.)

**Note 2 · the "Abort?" confirm** (`_on_abort_confirm`) answered chartread's own
question with `y`, which ends the session **without** the ending window — so
readings could be lost with no offer to save them. **His ruling: replace it**,
*"with calling the 'Keep what you have measured so far?' chain"*, and his
warning with it: the keys differ between the two modes, so each Abort must use
the chain belonging to ITS mode.

**Fixed in beta.156, and the warning is what shaped the fix:** chartread is told
**`n`** — it leaves its own question and returns to the prompt it came from —
and our ending runs instead. That way this path sends **no mode-specific key of
its own**; `_end_session` delegates to `send_save_partial_and_quit()` or
`abort()`, which already know which mode and which reader they are in. Engine
only; stock chartread's chain is different and works.

**Note 4 · the window could not be reached on the engine at all.** Knut, #130:
*"How can I reach the window during measurement session that have an abort
button?"* He could not, and the answer is not a documentation gap — it was a
defect this table had already declared fixed.

Esc goes out as `{"cmd":"quit"}`; the helper registers that as an abort
(`chromiq_chartread.c:2642`), prints `Abort ? - Are you sure ? [y/n]` and emits
an `abort_confirm` event. **Neither was dispatched on the engine path** —
`_ABORT_CONFIRM_RE` is matched only in `_handle_line`, which is stock chartread's
handler — so nothing appeared on screen and the helper sat at its own prompt
waiting for an answer that could not be given. The same shape as an unmapped key
in `KEY_TO_COMMAND`: an instrument that appears to stop responding.

The consequence for this document is worse than the bug: **the beta.156 fix
recorded in note 2 was never reachable on the engine**, so the row above claimed
a single exit that no user could ever take. Fixed in beta.160 by dispatching the
event, with `tests/test_abort_window_is_reachable.py` holding both readers level
— the stock path working is what hid this.

**Open, and Knut's to rule on:** the window says *"Stop measuring without
saving?"*. That is true on stock chartread, where Yes sends `y` and the readings
are gone. On the engine Yes now routes to *"Keep what you have measured so
far?"*, which **offers** to save — so the question and the outcome disagree on
the default reader. Proposed on the issue rather than changed here, because the
text belongs to §M.

**Note 3 · the calibration prompt** (`_on_calibration_prompt`) sends `\x1b` for
Cancel, which ends the session before any reading exists. **His ruling:** *"The
calibration prompt's Cancel is ok. Leave it."* Recorded here rather than
pretended away.

## Note 5 — the CR30 calibration window is not an exit, and that is why it is safe

⏳ **Awaiting confirmation.** **Confirmed by:** *nobody yet.*

M-CR30-CALIBRATE opens inside `TabMeasure._on_start`, **before the helper is
started and before anything irreversible has happened** — after the user has
agreed to replace the measurement, and before the run's existing `.ti3` is moved
to `old/`. So its Cancel is not an ending at all: no session exists to end, and
the correct behaviour is a bare `return`. That is exactly why it sits there. One
line later it would be a genuine exit, and a Cancel would have cost the user the
measurement that run was holding for a measurement that never began.

The one thing already done that the Cancel must undo is the armed per-patch
sound (#131: sounds must not be live outside a read).

Verified on screen, 2026-08-29: after Cancel the run's `.ti3` was byte-identical,
`old/` had not grown, no file in the run folder had changed, Start was enabled
again and the session was not live.

## Note 6 — a lost instrument ends through the one exit, and may also be resumed

⏳ **Awaiting confirmation.** **Confirmed by:** *nobody yet.*

When ChromIQ loses contact with a CR30 mid-measurement it does **not** call
`abort()`. `abort()` is a second exit, which §1 forbids, and on any instrument
that is not a CR30 it destroys the session outright, because stock chartread
writes its `.ti3` only on a clean exit. The window's OK therefore routes into
`_end_session(_confirm_end_of_session(...))` like every other ending.

Nothing is at risk either way for a CR30: the helper writes the measurement file
after **every** patch, so a session that dies still has every reading that was
taken.

"Keep measuring" remains offered, and it is honest: the handle to the vanished
instrument is released when contact is lost, so a reconnected instrument can be
opened, and the outstanding patch is armed again. Without both of those the
button would leave a live session with nothing listening — the dead end this
work removed everywhere else.
