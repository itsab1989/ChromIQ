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

---

## 2. BLOCKER — the CR30 guard is dead on the commonest path (the `.ti1`)

**This is not part of the reported bug, and it is worse than the reported
bug.** It also decides how A, B and C must be written, so it comes first.

`_blocked_by_stock_chartread_for_cr30` (`ui/tabs/tab_measure.py:4435-4441`)
and the no-swipe-arrow detection (`:4194-4199`) both do:

```python
name = read_target_instrument(self._ti1_path)
```

But `TARGET_INSTRUMENT` is written by the layout stage into the **`.ti2`**,
and it is **not in the `.ti1` at all**. Measured on Basti's own chart:

```
$ grep -c TARGET_INSTRUMENT /Users/Basti/ChromIQ/CR30-Test/runs/run1/CR30-Test.ti1
0
$ grep TARGET_INSTRUMENT      /Users/Basti/ChromIQ/CR30-Test/runs/run1/CR30-Test.ti2
TARGET_INSTRUMENT "CR30"
```

And `_ti1_path` **is** the `.ti1` whenever a project is opened:
`ui/main_window.py:2368-2369`, unconditionally —

```python
if run.chart_ti1.exists():
    self._tab_measure.set_ti1_path(run.chart_ti1)
```

`set_ti1_path` (`:3086-3128`) stores the path as given; it never resolves the
sibling. The tab's own comment at `:4211-4213` says so out loud — *"a real
.ti1 (reopening a saved run passes run.chart_ti1)"* — and that code path is
the only one that then bothers to resolve the sibling.

**Consequences today, before any of A/B/C is built:**

* Close ChromIQ, reopen the CR30 project, leave Preferences on ArgyllCMS
  chartread, press Start → the guard returns False, no window is shown, the
  measurement launches into `Unrecognised chart target instrument 'CR30'`.
  The guard was written specifically to prevent that.
* The swipe arrow comes back on a CR30 chart after a project reopen
  (`set_no_swipe(False)`), because `_spot` is computed from the same dead read.

**There is already a resolver, and it is the right one:**
`TabMeasure._chart_file_for` (`:5184-5195`) — *"Most paths hand this tab the
`.ti2` already; opening a project can hand it the `.ti1` instead, so both are
accepted and resolved to the one file chartread actually reads."* It is what
`set_ti1_path` uses to decide whether Start is even enabled.

**Change 0 (BLOCKER, CR30-specific in effect, pre-existing in shape):** add
one tab method and route *every* CR30 question through it —

```python
def _chart_is_cr30(self) -> bool:
    from ui.ti2_loader import is_cr30, read_target_instrument
    try:
        return is_cr30(read_target_instrument(
            self._chart_file_for(getattr(self, "_ti1_path", None))))
    except Exception:      # noqa: BLE001 — never block a read on this check
        return False
```

then use it at `:4196`, at `:4437`, and for everything A, B and C add. **Do
not add a fourth open-coded `read_target_instrument(self._ti1_path)`** — there
are already two and they are both wrong.

---

## 3. Item C — the mechanics of locking patch-by-patch

The ruling is taken as given: **for a CR30 chart, patch-by-patch is ON and
cannot be turned off, in both Guided and Manual.** Below is only *how*.

### 3.1 The precedent — and it is in this very tab, on the row above

Do not invent an idiom. **`TabMeasure`'s "Strip recognition → Auto" already
does exactly this job, keyed on exactly this fact.** Its three parts:

| Part | Where | What it does |
|---|---|---|
| detect | `_refresh_bidir_autodetect` `:3596-3641` — called from `set_ti1_path` `:3110` | re-reads the chart's `TARGET_INSTRUMENT`, stores `_detected_*` |
| show | `_apply_bidir_auto_state` `:3828-3839` | puts the derived value in the widget and **disables** it — *"the combo is disabled and shows the detected value (so the locked menu reflects the effective setting)"* |
| **decide** | `_resolve_bidir_value` `:3841-3847` | **the command is built from the resolver, never from the widget** — *"its own selection is ignored when the command is built"* |

That third row is the whole answer to "where must the lock live". Copy this
shape; do not copy the checkbox-only half of it.

A second, complementary precedent for the *presentation* is
`TabChart._apply_calibration_knobs` (`ui/tabs/tab_chart.py:5610-5700`): Run
type = Calibration forces a set of controls, **snapshots the previous tick
state *and the previous tooltip*, disables them, and swaps in a sentence that
says why and how to get them back** — then restores both exactly on the way
out. Its comment names the intent: *"so the row reads as 'not yours to set
right now' rather than as an invitation"*.

### 3.2 Q1 — ticked-and-disabled, not hidden. Three reasons, all from this file

1. **This tab's own written rule forbids hiding it.** `:1243-1262`, in
   `_collect_guided`, in capitals: **"NEVER FROM A CONTROL THE USER CANNOT
   SEE."** A hidden `_nocal_cb` whose value was still sent ran every Guided
   measurement uncalibrated for a whole beta. `-p` would be the same shape:
   invisible control, live flag. The comment at `:1930-1938` records that
   `_pbp_cb` was made visible in Guided (#160) for precisely this reason.
2. **Hiding it is not even mechanically available in Manual.** `_bool_row`
   returns `(cb, tip)` (`:1854-1863`) but `_bool_row_m` returns only `cb`
   (`:2335-2343`) — the Manual tooltip button is never stored, and neither row
   is kept as a widget. Hiding the Manual row cleanly means new plumbing;
   disabling it is one line.
3. **A ticked-and-disabled box is not a dead control.** The complaint the
   coordinator cites is about controls that *do nothing*. This one does
   something — it reports the mode the read is actually in. That is the same
   thing the greyed Auto combo does one row above and nobody has complained
   about that.

**Wording** must go through §M (`workflow/measurement_messages.py`) if it is a
window; a **tooltip is not a window**, and `_apply_calibration_knobs` puts its
explanation in `tr()` at the call site with an explicit note as to why (the
i18n extractor cannot see `tr(variable)` — `feedback_i18n_extractor_blind_spot`).
Follow that: the literal goes inline in `tr()`, and it must say what to do to
get the control back (in this case: nothing — load a chart made for a
different instrument).

### 3.3 Q2 — every reader of "patch by patch". There are **nine**, and the
brief names one

The brief names `measure_patch_by_patch` at `:11354`. That is the Guided
global default only. The full set:

| # | Reader | File:line | Kind |
|---|---|---|---|
| 1 | `_pbp_cb.isChecked()` → `MeasureParams.patch_by_patch` (Guided) | `tab_measure.py:11262` | **decides the read** |
| 2 | `_m_pbp_cb.isChecked()` → same (Manual) | `:11280` | **decides the read** |
| 3 | `_is_pbp_checked()` → `_spot_session` | `:1308-1311`, set at `:5383` | decides ~10 downstream UI behaviours (`:4786, 6870, 6903, 6925, 6989, 7210, 7213, 7622, 7703, 9616`) |
| 4 | `MeasureParams.patch_by_patch` → `-p` | `measure_manager.py:906` | the actual flag |
| 5 | `MeasureParams.patch_by_patch` → `_spot_mode` | `measure_manager.py:348`, used `:789` | key routing in spot mode |
| 6 | global default `measure_patch_by_patch` | `:11354` (read), `:11305` (**written by Save as Defaults**) | preference |
| 7 | global default `manual2_chartread_pbp` | `:11397`/`:2690` (read), `:11327` (**written by Save as Defaults**) | preference |
| 8 | per-target `patch_by_patch` / `patch_by_patch_guided` | `workflow/measure_settings.py:48` and `:71` | per-run store |
| 9 | Manual **preset** key `"pbp"` | `:2623` (**written**), `:2650` (read) | named preset |

Plus `_LINKED_PAIRS` (`:10766`) mirrors `_pbp_cb` ↔ `_m_pbp_cb` in both
directions, so **whichever box you lock, the other must be locked too** — an
unlocked partner is a live back door that writes straight through the mirror.

**So the lock must be a resolver, exactly like `_resolve_bidir_value`:**

```python
def _resolve_patch_by_patch(self, mode: str) -> bool:
    if self._chart_is_cr30():
        return True                     # a CR30 reads one patch at a time
    return (self._pbp_cb if mode == "guided" else self._m_pbp_cb).isChecked()
```

…called from `_collect_guided` (#1), `_collect_manual` (#2) **and**
`_is_pbp_checked` (#3). Readers 4 and 5 then follow for free, because they are
downstream of `MeasureParams`. Locking only the checkbox leaves #3 correct by
accident and every stale-state path (#6-#9) wrong.

### 3.4 Q3 — the per-target store. It is a real hazard, but not where expected

`patch_by_patch` **is** per-target: `workflow/measure_settings.py:48`
(`_m_pbp_cb`) and `:71` (`_pbp_cb`), stored in the run's `meta.json` under
`measure_settings`. `snapshot()` (`:107-113`) reads the widget's
`isChecked()` with no notion of "forced", so a forced tick **will** be
written.

Three findings, in order of severity:

* **Writing `true` into the CR30 run's own `meta.json` is harmless.** The store
  is per **run** (`store_for_target`, `per_target_settings.py:210-240`:
  profiling → `runs/runN/meta.json`, verification → `runs/runN/verifications/`,
  calibration → `cal/`). A run's chart does not change instrument, so the value
  it stores stays true of it. Specification §5 W8 (`per_target_settings.md:189`)
  says Start Measurement writes the Measure tab's settings *by design*, and
  `_on_start` does it at `:5429`.
* **The New-run seed is NOT a hazard.** I checked, because §4a N-2 strips
  calibration-owned rows from the seed for exactly this reason. `new_run.json`
  is written and read only by `tab_chart.py` (`:13303, 13407, 13602-13609,
  13619, 13651`); the Measure tab does not participate. Nothing to strip.
* **⚠ THE REAL LEAK IS THE TWO *GLOBAL* WRITERS.** Both read the widget
  directly and both are reachable with a CR30 chart loaded:
  * **"Save as Defaults"** — `_on_save_defaults` writes `measure_patch_by_patch`
    (`:11305`) and `manual2_chartread_pbp` (`:11327`). Those globals are what
    `_restore_defaults` (`:11354`, `:11397`) puts on screen for **every target
    that has nothing stored** (`load_target_settings`, `:1258-1278`). Press
    Save as Defaults once on a CR30 chart and **every future non-CR30 run opens
    in patch-by-patch**, which is a slow, wrong read the user never asked for.
  * **The Manual preset** — `_m_collect_preset_data` stores `"pbp"` (`:2623`).
    A preset saved on a CR30 chart carries patch-by-patch into whatever chart
    it is later applied to (`:2650`).

  This is the "a lock that silently rewrites saved user state" failure the
  coordinator is worried about, and it lands on the *global* store, not the
  per-target one — the opposite of the expectation.

  **The fix follows the calibration-knobs precedent: snapshot the user's own
  value, and write the snapshot, not the forced value.** Keep
  `self._pbp_user_value: dict[str, bool]` (per mode) captured at the moment the
  lock engages, restore it when the lock releases, and have `_on_save_defaults`
  and `_m_collect_preset_data` write `self._pbp_user_value[...]` while locked.
  The per-target `snapshot()` may keep writing the forced value (it is true of
  that run) — but if you would rather it did not, the same field answers it.

### 3.5 Q4 — key off the CHART, and only the chart. There is nothing else to key off

There is **no "selected instrument" in the Measure tab**. The two Instrument
spin boxes (`_instr_spin` / `_m_instr_spin`) are chartread's `-c` **comms port
number**, not a device choice (`_build_args`, `measure_manager.py:891`). The
instrument is chosen in the **Create Chart** tab and is recorded in the chart
it produces (log line 5516: `engine kwargs {'instrument': 'CR30', …}`). The
only app-wide preference, `chart_instrument`, is explicitly rejected as a
source in this tab already — `_chart_instrument_code` (`:4603-4612`): *"the
preference this used to consult says nothing about the sheet in the user's
hand."*

So Q4's mixed-project case resolves itself, **provided Change 0 is done**:

* CR30 chart loaded, any other device connected → locked on. Correct: the
  sheet in the hand is a CR30 sheet.
* Non-CR30 chart loaded, CR30 connected → **not** locked; the user's own
  value comes back. This is the case that makes the restore in §3.4
  mandatory rather than cosmetic — without it the user's unticked box never
  returns.
* Chart changed while the tab is open (`set_ti1_path` fires on project open,
  Profile-run change, Run-type change, and cross-tab loads — see `:3115-3118`)
  → the lock must be re-evaluated **there**, in the same place
  `_refresh_bidir_autodetect` is called (`:3110`).

**And it must be re-asserted after every settings load**, or a stored `false`
will land on screen after the lock has been applied. `load_target_settings`
already has the hook for precisely this class of problem —
`_reassert_guided_refinement()`, called on **both** branches (`:1278` and
`:1287`). Add the pbp re-assert beside it, and in `_restore_defaults` and
`_m_apply_preset_data` too.

---

## 4. Item A — no stock fallback for a chart stock chartread cannot read

**Agreed in principle, and the proposed scope is too narrow in two ways.**

### 4.1 There are THREE places that launch stock chartread, not one

`_engine_should_fall_back` is the one that fired on 2026-08-28. The other two
are just as reachable and one of them is worse:

| # | Site | Condition | Why it matters for a CR30 |
|---|---|---|---|
| 1 | `measure_manager.py:383-393` `_engine_mode_fallback` | helper says XY/chart mode and the Beta opt-in is off | unreachable **once B lands** (no instrument is opened under `-x`, so no mode can be reported) — but free to gate |
| 2 | `:398-421` `_engine_should_resume_fallback` | engine failed **after** reading patches, resumable `.ti3` exists | **the dangerous one.** It fires exactly when the user has already measured half the chart, and it relaunches stock chartread with `-r` on a CR30 chart, which refuses it. The reassuring "every strip you have already measured has been saved and will be kept" message is emitted **first**, so the user is told they are continuing and then watches it die |
| 3 | `:423-437` `_engine_should_fall_back` | the reported case | as diagnosed |

Gating only #3 leaves #2 to produce the same double failure with a much more
misleading message attached. **Gate all three.**

### 4.2 The predicate — do not re-derive it, and do not import `ui` from `workflow`

The brief asks which predicate. Answers, in order of preference:

* **NOT `_blocked_by_stock_chartread_for_cr30`.** It is the right *question* but
  the wrong *object*: it is a `TabMeasure` method that shows a modal, mutates
  `chartread_engine`, and returns "should Start be refused". `MeasureManager`
  must not call anything that can open a window from inside a finished-callback.
* **NOT `params.instrument`.** That is chartread's `-c` **comms port number**
  (`_build_args:891`, and log line 8567 shows `-c 1`). It says nothing about
  the device.
* **NOT re-reading the chart inside `measure_manager`.** `ui/ti2_loader.is_cr30`
  lives in `ui/`; `workflow/` imports `ui/` in exactly two places in the whole
  tree (`chart_creator.py:1643`, `ti2_relayout.py:255`), both lazy, both for one
  helper. Adding a third for a policy decision inverts the layering.
* **✅ A new `MeasureParams` field, set by the tab — the way every other
  engine decision already travels.** `engine_helper`, `engine_safenet`,
  `engine_xy_chart`, `cal_auto_retries` all reach the manager this way
  (`_apply_engine_params`, `tab_measure.py:11180-11200`). Add:

  ```python
  #: This chart names an instrument stock ArgyllCMS chartread refuses
  #: (#159 CR30). A fallback to it can only fail, so it must not happen.
  stock_reader_cannot_read: bool = False
  ```

  set in `_apply_engine_params` from `self._chart_is_cr30()` (Change 0), and
  checked at all three sites above.

  **⚠ `workflow/measure_settings.py:26-41` `NOT_A_SETTING` must gain an entry
  for it, or `tests/test_measure_settings.py` fails the drift guard.** That
  test exists precisely to catch a new `MeasureParams` field nobody mapped.
  The reason line writes itself: *"a property of the chart, not a preference"*.

### 4.3 Say it once, and say the true thing

With the fallback gated, the run ends on the helper's own exit. Today the user
sees, in order: a `[WARNING]` about "the instrument", a translated paragraph
promising ArgyllCMS chartread will take over, and then a second failure. All
three are wrong — **no instrument was involved at any point**, and the
suggested remedy cannot work.

* `_engine_fatal` is `None` here, so the reason renders as `unknown error`. The
  helper *did* say exactly what was wrong; it said it on **stderr**, outside the
  JSON channel, and nothing captured it (log line 8583 proves ChromIQ received
  the text and dropped it on the floor). **Change:** when
  `stock_reader_cannot_read` is set and the engine exits non-zero having emitted
  no event, surface the helper's own last stderr line rather than
  `unknown error`. (A broader fix — have the C side emit
  `{"event":"error","kind":"chart_refused"}` before `error()` at `:3712` — is
  cleaner still, and the C side is already the owner of that text.)
* The user-facing sentence must come from **§M**, not from a `tr()` at the
  fallback site. `M_CR30_STOCK_READER` already exists
  (`workflow/measurement_messages.py:73-86`) and is `approved=False` —
  §M-PROPOSED. **A second CR30 message will need the same treatment**; do not
  write new wording straight into `measure_manager.py`, or
  `tests/test_message_catalogue.py` will fail and Knut's §M rule is broken.

**Finally — A is not a substitute for B.** With A alone the user gets one clean
failure instead of two confusing ones, and still cannot measure their chart.

