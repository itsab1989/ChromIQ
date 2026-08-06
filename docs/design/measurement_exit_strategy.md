# Every window that can end a measurement, and how it ends it

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
| | Save Partial & Quit | `send_save_partial_and_quit()` | the two-`q` chain | ⚠️ **see note 1** |
| **Unread patches remain** | (three buttons) | `_end_session(choice)` | the ending | ✅ |
| **Abort?** (Esc pressed) | Yes / No | `y` / `n` | chartread's own confirm | ⚠️ **see note 2** |
| **Calibration required** | OK / Skip / Cancel | `\r` / `s` / `\x1b` | the instrument's own calibration prompt | ⚠️ **see note 3** |
| **All Strips Read / All Patches Read** | Go to … Tab | `d` | "done" — chartread writes and exits normally | ✅ not a failure exit |
| | Re-read … | — | the window closes; the session continues | ✅ |
| | Close | — | keeps the measurement, goes nowhere | ✅ |

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

## Notes — the three that are not yet the single exit

**Note 1 · "Save Partial & Quit" on the Patch Read Failed window** calls
`send_save_partial_and_quit()` directly rather than going through
`_confirm_end_of_session`. In practice it lands in the same place, because the
button *is* the "save and stop" answer — but it is a second door to the same
room, and it does not offer Discard or Keep measuring. **Recommendation:** route
it through the ending like Give Up does, so the model has exactly one exit.
Behaviour would change only in that the user is asked.

**Note 2 · the "Abort?" confirm** (`_on_abort_confirm`) is chartread's own
question, answered `y`/`n`, and `y` ends the session **without** the ending
window — so readings can be lost with no offer to save them. This is the one
that most clearly breaks the single exit. **Recommendation:** answer `n` to
chartread and run our own ending instead, so Esc behaves exactly like Stop.

**Note 3 · the calibration prompt** (`_on_calibration_prompt`) sends `\x1b` for
Cancel, which ends the session before any reading exists. Harmless today —
there is nothing to lose at that point — but it is still a direct exit.
**Recommendation:** leave it, and record the exception here rather than pretend
it does not exist.

Notes 1 and 2 are **not implemented**: they change behaviour in the measurement
path, which is Knut's specification to rule on. They are listed here as the
answer to *"Make also note if any of the exit methods does not follow the single
exit method for our model."*
