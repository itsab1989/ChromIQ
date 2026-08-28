STATUS: in-progress

# 08 — Measure-tab wiring critique (CR30)

**Agent:** CR30-MEASURE-CRITIC
**Branch:** `feature/cr30-instrument-159`
**Started:** 2026-08-28

Scope: attack the proposed diagnosis of Basti's live failure

```
[WARNING] workflow.measure_manager: engine could not use the instrument (unknown error) — restarting on stock chartread
```

and the three intended fixes (A: no stock fallback for CR30, B: pass `-x`,
C: pre-select patch-by-patch). Report only — no production file is edited.

Sections are appended as they are proved. Nothing below is written from
memory; every claim carries a `file:line` or a command whose output is quoted.

---

## 1. The diagnosis: verdict step by step

**Overall: the diagnosis is correct in every step.** It is not merely
plausible — the live log records the whole sequence, and I reproduced it
outside the app. `fast_instrument_connect` is exonerated.

### The real log

`~/Library/Logs/ChromIQ/chromiq.log` (`core/platform_paths.py:122-127`
resolves it). Two runs, 20:15:24 and 20:15:49, lines 8567-8591 and
8608-8632. The first, verbatim:

```
8567 [INFO]  workflow.measure_manager: chromiq-chartread: --json -v -c 1 -S -T 0.7 …/CR30-Test  [cwd=…/runs/run1]
8583 [DEBUG] core.argyll_runner: [argyll] chromiq-chartread: Error - The chart was made for 'CR30',
                which ChromIQ reads itself. Measure it in ChromIQ, or use -x to supply values.
8586 [WARNING] workflow.measure_manager: engine could not use the instrument (unknown error) — restarting on stock chartread
8588 [INFO]  workflow.measure_manager: chartread: -v -c 1 -S -T 0.7 …/CR30-Test
8590 [DEBUG] core.argyll_runner: [argyll-pty] chartread: Error - Unrecognised chart target instrument 'CR30'
```

That is the *entire* failure. Note what the command line does **not**
contain: no `-x`, and no `-p` either — patch-by-patch was off, as reported.

### Step 1 — "ChromIQ never passes `-x`". **TRUE.**

`MeasureManager._build_args` (`workflow/measure_manager.py:882-912`) is the
only place chartread's arguments are assembled, and its whole vocabulary is
`-v -c <inst>` plus `-B/-b/-S/-N/-p/-H/-r`, the user's free-text extras, and
the base name. There is no `-x` branch and nothing consults the chart's
`TARGET_INSTRUMENT`. `grep -n '"-x"' workflow/measure_manager.py
ui/tabs/tab_measure.py` returns nothing. Confirmed by log line 8567.

### Step 2 — "the C gate fires and exits non-zero with no events". **TRUE.**

The gate is `native/chartread_helper/chromiq_chartread.c:3710-3714`, inside
the CGATS-reading block:

```c
if (itype == instUnknown
 && (ti = icg->find_kword(icg, 0, "TARGET_INSTRUMENT")) >= 0
 && cq_is_external_instrument(icg->t[0].kdata[ti])) {
        if (xtern == 0)
                error("The chart was made for '%s', which ChromIQ reads itself. …");
```

`error()` is Argyll's `numsup` fatal: stderr, then exit. **Reproduced** on
Basti's own chart, byte-for-byte the command from line 8567:

```
$ cd /Users/Basti/ChromIQ/CR30-Test/runs/run1
$ …/build/chromiq-chartread --json -v -c 1 -S -T 0.7 ./CR30-Test
chromiq-chartread: Error - The chart was made for 'CR30', which ChromIQ reads itself. …
EXIT=1
```

One line on stderr, **zero JSON events**, exit 1.

### Step 3 — "`_engine_should_fall_back` then returns True". **TRUE.**

`workflow/measure_manager.py:537-558`. With `code == 1`,
`_engine_progress == False`, `_user_quit == False`,
`_engine_fallback_used == False`, the return is
`self._engine_fatal is not None or not self._engine_saw_event`. The gate
emitted no JSON, so `_engine_saw_event` is False → **True**. It is the
*second* disjunct that fires, and that is exactly why the log says
`(unknown error)`: `_engine_fatal` is still `None` (line 8586). The
diagnosis' own wording — "no progress" — is right, but the operative clause
is the never-spoke-at-all clause, not the fatal clause.

And the fallback is indeed guaranteed fatal: stock chartread has no
`cq_is_external_instrument`, so it takes the plain branch at `:3722-3730`
and `inst_enum("CR30")` returns `instUnknown` →
`error("Unrecognised chart target instrument 'CR30'")`. Log line 8590 is
that error. **Two failures, the second more confusing than the first.**

### Step 4 — "`fast_instrument_connect` is not the cause". **TRUE, twice over.**

*Ordering:* the gate at `:3710` is in the chart-reading block; the instrument
is only opened at `:4194`, `if (!xtern && !cq_replay_active())`. The process
exits ~470 lines of control flow before `new_icompaths()` is reached.
Measured: 52 ms from launch (8567) to error (8583), and the same 50 ms in my
standalone run — no port scan happened.

*Mechanism:* the preference does exactly one thing —
`ArgyllRunner._serial_exclusion_value` (`core/argyll_runner.py:335-345`)
sets `ARGYLL_EXCLUDE_SERIAL_SCAN` in the child's environment. It cannot
change an argument, a chart, or a CGATS keyword.

**So: should it be ignored for a CR30?** No — there is nothing to ignore.
Once `-x` is passed the helper opens no instrument at all, and ChromIQ's own
CR30 transport is GATT-over-BLE via `bleak` (`workflow/cr30/ble.py`,
`transport.py`) plus a USB path (`usb_measure.py`) — neither is a serial port
Argyll would ever have enumerated. **Do not add a CR30 special case to this
preference.** Doing so would be a change that provably cannot affect the bug,
in a setting that exists for a different instrument class entirely.

