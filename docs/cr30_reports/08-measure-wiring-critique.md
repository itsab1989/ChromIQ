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

---

## 5. Item B — passing `-x`, and the two silent-corruption traps in the protocol

The **good news first, and it is substantial**: I drove the real helper with
`-xx --json` against Basti's own CR30 `.ti2` and the whole spot-mode UI layer
already works. The helper emits `session_start` (15 strips), `spot_ready`
(`{"id":"384","loc":"A1","read":false,"all_done":false,"exyz":[…]}`), then
`patch_read` and `saved` per value. Those are exactly the events
`MeasureManager` already routes to `patch_ready` / `patch_measured`
(`measure_manager.py:1141-1186`) and the tab already renders
(`_on_patch_ready:10235`, `_on_patch_measured:10255`). **No new UI is needed.**

### 5.1 Where the args are built, and what `-x` implies

`MeasureManager._build_args` (`:882-912`) — the single site. `-x` takes its
letter as the option argument (`chromiq_chartread.c:3559-3569`), so `-xx`
(XYZ) or `-xl` (L\*a\*b\*). ChromIQ should send **`-xx`**: `workflow/cr30/`
produces XYZ, and `-xl` would make the helper apply `icmLab2XYZ(&icmD50,…)`
(`:3157-3161`), a conversion ChromIQ would be doing twice.

**Three flags become inert and one becomes unnecessary — none is harmful:**

* `-c <port>`, `-N`, `-B`/`-b`, `-T` — all instrument-side. `new_icompaths`
  is skipped entirely (`:4194`), and calibration lives inside `if (xtern == 0)`
  (`:2610-2628`).
* **`-p` is not needed at all.** `xtern != 0` takes the spot branch
  unconditionally (`:2600-2601`, *"Spot mode. This will be used if xtern != 0"*).
  I verified it: `-xx --json` with **no `-p`** went straight to
  `Ready to read patch '384' at 'A1'`. So B and C are independent — `-x` alone
  guarantees the read mode.

  **But `params.patch_by_patch` must still be True**, because
  `MeasureManager.start:348` derives `self._spot_mode` from it, and
  `skip_current_strip` (`:789`) branches on `_spot_mode` to decide whether
  "skip" means `forward` or a strip key. With `-x` on and `patch_by_patch`
  off, the helper is in spot mode and the manager thinks it is in strip mode.
  **This is the concrete reason C is a correctness requirement for B, not a
  convenience.**

### 5.2 🔴 BLOCKER — a second `value` silently destroys the first

`chromiq_json.c:172-184` writes `cq_pending_line` **unconditionally**. The key
path directly below it (`:226-239`) is guarded by `if (!cq_line_ready)`. The
`value` path is not. **Measured**, two values sent back to back with no wait:

```
send {"cmd":"value","xyz":"10 10 10"}
send {"cmd":"value","xyz":"20 20 20"}
→ patch_read A1 [20.0, 20.0, 20.0]      ← the 10s are gone. No event. No error.
```

The first reading is not rejected, not queued, not reported — it never
happened. **A lost patch is invisible; a *mis-paired* patch is a wrong colour
in the `.ti3` that nothing downstream can detect.** The brief's "wait for
`spot_ready`" is therefore not a style note: it is the only thing standing
between a user and quietly wrong profile data.

**Change:** enforce it in Python, do not merely document it. One latch:

```python
self._awaiting_loc: str | None = None      # set on patch_ready, cleared on patch_measured
```

Refuse to send a value while `_awaiting_loc` is None, and **verify the pairing
after the fact** — `patch_read` carries `loc`, so assert it equals the `loc`
answered and abort the read loudly if not. (`project_patch_identity_check`
found a real mispairing in Basti's own project once already.)

**And ask the C side to add the same `if (!cq_line_ready)` guard**, returning a
`{"event":"error","kind":"value_dropped"}` instead of overwriting. Defence
belongs on both sides of a channel that can silently corrupt data.

### 5.3 🔴 BLOCKER — click-to-jump silently swallows a `goto`

Worse, because it needs no race the user can see. `_on_patch_ready` turns on
click-to-jump for the whole chart and *advertises it*
(`tab_measure.py:10240-10245`: *"Tip: click any patch in the preview to jump
straight to it"*). A click sends `{"cmd":"goto","patch":…}`. **Measured**:

```
A) send goto B1, then value      → patch_read A1 [11,11,11]   (goto LOST)
B) send value, then goto B1      → patch_read A1 [22,22,22]   (goto LOST)
```

In **both orders the jump is discarded** and the reading lands on the patch
the user was trying to leave. In order A the key is dropped by the guard at
`:226`; in order B it is dropped because the value is consumed first and the
`goto` then finds nothing to attach to. Either way: **the user clicked B1 and
B1's reading went into A1.**

**Change:** the backend must hold values while a navigation command is
outstanding, and must not consider `_awaiting_loc` settled until the
`spot_ready` for the *new* loc has arrived. Simplest correct rule: **only ever
send a value in response to the `spot_ready` that is currently outstanding, and
drop (with a log line) any device reading that arrives while a navigation is
in flight** — the operator can simply read the patch again.

### 5.4 Inert commands re-emit `spot_ready` for the same patch

Also measured: under `-x`, `{"cmd":"ok"}` (Return) and `{"cmd":"retry"}` are
not recognised by the external-value parser and simply loop the prompt — each
producing a **duplicate `spot_ready` for the same `loc`**:

```
start                    → spot_ready A1
send {"cmd":"ok"}        → spot_ready A1     (again)
send {"cmd":"retry"}     → spot_ready A1     (again)
```

A naive "one value per `spot_ready`" backend sends three values for A1 and
loses two of them to §5.2. **The latch must be keyed on `loc` and on
transitions, not on the event count.** Note also that `send_post_retry_key`
(`measure_manager.py:748-750`) sends `{"cmd":"ok"}` on the engine path — so
this is reached by the existing failure-recovery UI, not only by a hypothetical
backend.

### 5.5 What else assumes an instrument was opened

Everything in the brief's list checks out as safe, and two things do not:

| Assumption | Verdict under `-x` |
|---|---|
| calibration prompts | **safe** — `cq_handle_calibrate` is inside `if (xtern == 0)` (`:2610-2628`); `calibration_prompt`/`calibration_done`/`calibration_retrying` cannot fire |
| `no_instrument` | **safe** — `cq_emit_error("no_instrument")` is at `:941`, inside the same block |
| `sensor_wrong_position` | **safe** — parsed from an instrument-driven line that is never printed |
| 12 s key watchdog (`_arm_key_watchdog`, `:5871`) | **safe** — armed only after a dialog sends a key, and any command still produces output |
| `spot_ready` handling | **safe and already correct** — `:1141-1176` is mode-agnostic |
| JSON command channel | **NOT safe** — §5.2, §5.3, §5.4 |
| ⚠ **`instrument_detected`** | **never fires.** `{"event":"instrument"}` is emitted at `:998`, inside `if (xtern == 0)`. So `_detected_instrument` keeps whatever `_refresh_bidir_autodetect` put there — and that reads `self._ti1_path`, so after a project reopen it is `None` (Change 0 again) |
| ⚠ **the "how to measure" window** | **never appears.** `_on_calibration_done` (`tab_measure.py:7170`) is the *only* route to `patch_measurement_instructions_html`, and it is wired to `calibration_done` (`:999`), which cannot fire under `-x`. A CR30 user gets a spot session with **no on-screen instruction at all** |
| ⚠ `patch_measurement_instructions_html` | has **no `cr30` branch** (`ui/ti2_loader.py:288-317`) — it would fall through to the generic *"take a single reading as described in its manual"* even if it were reached. `instrument_family` **does** return `"cr30"` (`:170-171`), and `calibration_instructions_html` and `core/measure_pace.py:689-698` both have CR30 branches, so this one is simply missing |
| `_saw_instrument` (`:1081`) | set at `:4403`, never read anywhere. Dead state — not a bug, but do not build on it |

### 5.6 The Python side of B does not exist yet

For the record: `grep` for a sender of `{"cmd":"value"}` across the whole tree
returns **nothing**. `workflow/cr30/` is a complete device layer (frame,
session, transport, BLE, USB measure, colour) with **no bridge to the measure
flow** — no code opens a CR30, waits on `patch_ready`, or answers it. B is
entirely unbuilt above the C line, and the two traps above are the first thing
the bridge has to get right.

One architectural note, because it is the kind of thing that gets found late:
`patch_ready` is delivered on the Qt main thread from the process's stdout
reader. Obtaining a CR30 reading is a BLE (`bleak`, asyncio) or serial round
trip that waits on a human pressing the device's own button. **It must not run
on the main thread**, and `feedback_qthread_reference_lifetime` applies — the
worker must stay referenced until it finishes.

---

## 6. Things nobody has raised that will bite a real user

### 6.1 The `.ti1` blindness is not only a CR30 bug — it costs an i1Pro user `-b`

`_refresh_bidir_autodetect` (`tab_measure.py:3596-3641`) and `_pace_config`
(`:4341-4348`) make the **same** unresolved `read_target_instrument(self._ti1_path)`
call as the two CR30 sites. Measured on Basti's project:

```
.ti1  instr=None  cr30=False  force_b=False  disable_B=False  randomised=False
.ti2  instr='CR30' cr30=True  force_b=False  disable_B=False  randomised=True
```

`randomised` flips **False → True** and `instr` **None → 'CR30'**. So after
*any* project reopen:

* **an i1Pro chart silently loses its auto `-b`** (`force_bidir_for_instrument`
  returns True only for the i1Pro family), which is the flag that lets a strip
  be swiped either way — a documented cause of repeated re-reads;
* `_detected_randomized` is False, so the preview's bidirectional arrow and the
  "Chart instrument: … → using Argyll's default strip recognition" log line are
  both wrong;
* the CR30 pace row falls back to the i1Pro key instead of `"cr30"`
  (`core/measure_pace.py:343, 364, 689`), so the strip-pace panel is judged
  live on a chart that can never produce a strip.

**SERIOUS, pre-existing, not CR30-specific.** One `_chart_file_for` call fixes
all of it; Change 0 should cover these two sites as well as the two CR30 ones.

### 6.2 A developer's message is being shown to the user, and §M never saw it

Log lines 8584-8585 show the tab printing the helper's own stderr into the
user's measurement log:

> `chromiq-chartread: Error - The chart was made for 'CR30', which ChromIQ reads itself. Measure it in ChromIQ, or use -x to supply values.`

Read that as a user: they *are* measuring it in ChromIQ, and they have no way
to "use `-x`". It is a command-line author's sentence shown to someone who has
just pressed Start. `tests/test_message_catalogue.py` cannot catch it — §M
polices Python message constants, and this string lives in
`chromiq_chartread.c:3712`. **MINOR on its own, SERIOUS as a class**: every
`error()` in the fork can reach the user's log the same way.

### 6.3 The teardown fix in `3abf6c40` did not land — it renamed the error

`3abf6c40` set out to stop `test_cr30_external_values.py` leaking a
`BrokenPipeError` at teardown. Run today, on that commit:

```
$ QT_QPA_PLATFORM=offscreen pytest tests/test_cr30_external_values.py … -q
…PytestUnhandledThreadExceptionWarning: Exception in thread Thread-5 (_pump)
  File "tests/test_cr30_external_values.py", line 58, in _pump
    for line in self.p.stdout:
ValueError: I/O operation on closed file
82 passed, 3 warnings
```

`Reader.kill` now closes `self.p.stdout` **while the `_pump` thread is still
iterating it**. The unraisable exception is still there under a different name.
Fix: kill the process, `wait()`, let the pump see EOF, **join the thread**, and
only then close. (`feedback_a_mutation_must_be_proven_to_land` — a fix that is
not observed is not a fix.) **MINOR, CR30-specific.**

### 6.4 `test_cr30_external_values.py` is pinned to a path in Basti's home

`tests/test_cr30_external_values.py:34`:

```python
SRC_TI2 = pathlib.Path("/Users/Basti/ChromIQ/ttestitest/ttestitest.ti2")
```

with `pytestmark = pytest.mark.skipif(not BIN.is_file() or not SRC_TI2.is_file())`.
On any other machine — CI, a second developer, a fresh clone, or Basti after he
deletes that project — the file **skips silently** and the four blockers it
pins go unguarded. The suite has a session-scoped `demo_projects_root` fixture
for exactly this (CLAUDE.md: *"There is ONE session-scoped build for the whole
suite"*), or the chart can be generated in `tmp_path`. **SERIOUS, CR30-specific**
— it is the only regression guard the `-x` path has.

### 6.5 The no-instrument window would tell a CR30 user to change an unrelated setting

`_show_no_instrument_window` (`:6014-6075`) picks `M_NO_INSTRUMENT_FAST` and
offers a **"Turn off faster connection"** button whenever
`fast_instrument_connect` is on. Under `-x` the helper cannot raise
`no_instrument`, so this is safe **today** — but the moment ChromIQ's own CR30
backend gets a "the device did not answer" path and reuses this window, a BLE
failure will be met with an offer to change an ArgyllCMS serial-port
preference. **MINOR, forward-looking** — but it is the direct answer to Basti's
question: the setting must not be *ignored* for a CR30, it must simply never be
*mentioned* to one.

### 6.6 The engine default means the existing CR30 guard almost never runs

`core/settings.py:189` — `"chartread_engine": "chromiq"`, with a migration at
`:901-909` that resets an older stored value. So `_engine_selected()` is True
for essentially everyone, and `_blocked_by_stock_chartread_for_cr30` returns
False at its first line (`:4433`). That is by design; it is worth stating
because it means **the guard is not what protected Basti, and nothing did.**

