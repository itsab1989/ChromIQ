# CR30 design critique — [CR30-DESIGN-CRITIC]

STATUS: in-progress
Branch: `feature/cr30-instrument-159`
Target: `docs/cr30_reports/02-design.md`
Started: 2026-08-28

Method: every finding carries `file:line` verified by reading the surrounding
code, or is marked **NOT VERIFIED** with the experiment that would settle it.
Rank: **BLOCKER** (beta cannot ship) / **SERIOUS** (ship with a documented
limitation) / **MINOR**.

---

## A. BLOCKERS

### A1 — `chromiq-chartread -x --json` DOES NOT WORK. The design's entire reading path is unbuildable as written. **BLOCKER**

The design (§1 steps 4-5, §2 row 2, §8 B6) has ChromIQ run
`chromiq-chartread -x` under the JSON protocol and push XYZ values to the
helper's **stdin**. **stdin is already owned by the JSON command thread.**

- `native/chartread_helper/chromiq_json.c:190-205` — `cq_reader()` is a detached
  thread running `while (fgets(line, sizeof(line), stdin) != NULL) cq_handle_line(line);`
- started unconditionally in JSON mode at `chromiq_chartread.c:3331` (`cq_cmd_start()`)
- the `-x` value prompt at `chromiq_chartread.c:2805` calls
  `con_fgets(buf, 200)` on **the same stdin**, with **no `cq_json` branch** —
  unlike every other console read in the file, which are all routed through
  `cq_prompt_char()` → `cq_wait_char()` (`:737-741`, and `:2132, 2149, 2202,
  2230, 2435, 2473`).
- the source says so itself: `chromiq_chartread.c:736` *"stdin belongs to the
  command channel in JSON mode"*, and `:767` *"The console is never polled in
  JSON mode — stdin belongs to the command channel."*

**What actually happens** — reproduced against the shipped binary
`native/chromiq-chartread`, a 12-patch engine-written `.ti2`:

```
printf '95.1 100.0 108.8\n' | chromiq-chartread -xx --json t
→ {"event":"session_start",...}
→ {"event":"spot_ready","id":"3","loc":"A1",...}   ×  ~200,000 in 14 s
```

`con_fgets` never sees the line (the reader thread ate it), returns NULL, hits
`printf("Error - unrecognised input\n"); continue;` (`:2806-2808`) and loops
with no delay. **A tight infinite loop writing unbounded JSON to stdout** —
which in ChromIQ means `QProcess` readyReadStandardOutput firing forever and
`parse_engine_line` (`workflow/chartread_engine.py:70`) parsing hundreds of
thousands of events per second. The GUI would lock up, not merely fail.

Second, independent half of the same blocker: **there is no JSON command that
can carry a measurement.** `chromiq_json.c:130-179` enumerates the whole
vocabulary — `goto / next_unread / forward / back / read / done / save / retry /
accept / ok / yes / no / skip / quit` — every one mapping to a single key char.
A line that is not a `{"cmd":…}` object is dropped at `cq_handle_line`. So even
without the race, XYZ values have no slot in the protocol.

**Verified working without `--json`:** `-xx --autosave` behaves exactly as the
design describes (values accepted, patch named, `.ti3` autosaved per patch). It
is only `--json` that is incompatible — and `--json` is what the whole Measure
tab is built on.

**What must change before code:** a C change to `chromiq_chartread.c` /
`chromiq_json.c` adding an external-value command to the JSON vocabulary
(e.g. `{"cmd":"value","xyz":[X,Y,Z]}` queued alongside `cq_pending_key`) and
routing `:2805`'s read through it in JSON mode. This is **not** in the design's
§8 build order at all — B6 is described as "the `-x` reading path", implying
wiring, not a protocol extension. It is the single largest piece of unplanned
work in the design.

### A2 — Aborting an `-x` session SEGFAULTS. **BLOCKER**

`inst *it = NULL;` (`chromiq_chartread.c:883`) and the only three assignments
(`:910, :915, :917`) are inside `if (xtern == 0)` (`:897`). In `-x` mode `it`
stays NULL for the whole run. The spot loop's command dispatch is **shared**
between the instrument and external branches, and three of its exits call
`it->del(it)` unguarded:

| Line | Path | Reached in `-x`? |
|---|---|---|
| `:2986` | `q` / Esc / `^C` → `abort_confirm` → `y` | **YES — this is Stop/abort** |
| `:3002` | `k` → `cq_handle_calibrate(it, …)` | **YES if a `k` ever arrives** |
| `:3044` | `d` with unread patches → Esc | **YES** |

The normal exit at `:3152-3153` *is* guarded (`if (it != NULL)`); these three
are not.

**Proven** against the shipped binary:
`printf '95.1 100.0 108.8\n…\nq\ny\n' | chromiq-chartread -xx t` → **exit 139
(SIGSEGV)**.

This is the *abort* path — the one `docs/design/measurement_exit_strategy.md`
governs and which the Measure tab exposes as **Stop**. Every CR30 measurement a
user stops early would crash the helper. Autosave means the readings survive on
disk, but the `aborted`/`done` event never arrives, so the Measure tab's
end-of-run state machine gets a process crash instead of an ending — exactly the
class of thing `measurement_exit_strategy.md` exists to prevent.

Also note `:3002`: §10.2's new calibration flow must **never** route through
the `k` (calibrate) command in `-x` mode.

### A3 — the `.ti3` says `TARGET_INSTRUMENT "Unknown Instrument"`, not `CR30`. **BLOCKER**

The survey flagged this as NOT VERIFIED (§3.5, R10). **Now verified, by running
it.** Output of `chromiq-chartread -xx --autosave` on an engine `.ti2`:

```
DEVICE_CLASS "OUTPUT"
COLOR_REP "iRGB_XYZ"
TARGET_INSTRUMENT "Unknown Instrument"
```

Mechanism, all read:
- `chromiq_chartread.c:3239` `instType atype = instUnknown;`
- `:968` is the only assignment (`*atype = it->get_itype(it)`), inside
  `if (xtern == 0)` — never reached in `-x`
- `:317-318` `if (ocg->find_kword(ocg,0,"TARGET_INSTRUMENT") < 0)
  ocg->add_kword(…, inst_name(atype), …)`
- **the `.ti2`'s `TARGET_INSTRUMENT` is never copied into `ocg`** — `:3636-3650`
  copies only `SINGLE_DIM_STEPS`, `COMP_GREY_STEPS`, `MULTI_DIM_STEPS`,
  `FULL_SPREAD_PATCHES`. So the keyword is always absent and always written.
- `native/instlib/insttypes.c:207` `inst_name()` has no `instUnknown` case →
  falls through to the default → `"Unknown Instrument"`.

**Consequences, each verified in the Python:**
1. `ui/tabs/tab_profile.py:766,4059` and `ui/tabs/tab_check_refine.py:200,223`
   read `TARGET_INSTRUMENT` **from the `.ti3`** into `_detected_instrument`.
   It will read `"Unknown Instrument"` for every CR30 run.
2. `tab_profile.py:4095` / `tab_check_refine.py:248` gate the UV/FWA options on
   `is_colormunki(self._detected_instrument)`. `is_colormunki("Unknown
   Instrument")` is False → **`colprof -f` (FWA) is OFFERED for a CR30
   measurement that has no spectral data at all.** The survey (§11) already
   flagged that a CR30 must land on the ColorMunki side of this gate; the `.ti3`
   identity makes it land on the *wrong* side even if `is_cr30` is written.
3. `ui/dialogs/tools_dialogs.py:1461-1463` displays
   `"Instrument: Unknown Instrument"`.

`colprof` itself does **not** read `TARGET_INSTRUMENT` (the only Argyll consumer
is `xicc/mpp.c:418`, a different tool), so the *profile build* is unaffected —
but ChromIQ's own identity chain is broken end to end.

**Fix required before code:** either copy the `.ti2`'s `TARGET_INSTRUMENT` into
`ocg` at `:3636` (one line, correct for every mode, and arguably a bug fix
independent of the CR30), or set `atype` explicitly in `-x` mode.

### A4 — the honest `CR30` name is fatal in **our own fork** too, and §8 does not plan the C change. **BLOCKER**

`inst_enum()` (`native/instlib/insttypes.c:306+`) is a table of exact string
compares; `"CR30"` is not in it and returns `instUnknown`, so
`chromiq_chartread.c:3626-3633` raises
`error("Unrecognised chart target instrument 'CR30'")` — **in `chromiq-chartread`,
not only in stock chartread**. The design's §2 table lists the gate as something
that *exists and is tested*, and §9.4 mentions only the stock-chartread
consequence. §8's build order (B1 "identity constant + registry", B5 "`.ti2`
chain") never names a `chromiq_chartread.c` change. The survey did
(§12: `chromiq_chartread.c` 1 touch point, line 3629); the design dropped it.

### A5 — `ui/tabs/tab_measure.py:4397` will refuse to start every CR30 measurement, and "fixing" it makes the message a lie. **BLOCKER (design decision missing)**

`_blocked_by_unusable_target_instrument` reads the chart's `TARGET_INSTRUMENT`
and, if it is not in `ui/ti2_loader.KNOWN_INSTRUMENTS` (`:35`), shows a modal
saying *"ArgyllCMS matches that name exactly, and it does not know this one — so
it would refuse the measurement before reading a single patch"* and offers to
rewrite it. `_repair_target_instrument` (`:4459-4497`) can only map
colormunki / spectroscan / i1pro; `"CR30"` matches none, so the user gets
*"ChromIQ cannot tell which instrument this chart is for"* and **the measurement
is refused outright**.

Adding `"CR30"` to `KNOWN_INSTRUMENTS` silences the modal — but the guard's
whole claim then becomes false for the one case where it is still true: with
**Preferences → chart-reading engine set to `argyll`** (`core/settings.py:189`,
a real user-selectable setting read at `ui/tabs/tab_measure.py:9397`), a CR30
chart hits stock chartread and fatals with *exactly* the abrupt cut-off Knut
complained about and this guard was written to prevent (its docstring quotes
him, `:4400-4408`).

**The design has no answer for the `chartread_engine = "argyll"` + CR30 chart
combination.** §9.4 states the consequence but no UI behaviour. This needs a
ruling and a guard (refuse with a clear message, or force the ChromIQ engine for
CR30 charts the same way the layout engine is forced).

### A6 — §10.2's calibration confirmation is **theatre**, and the flow it mandates is the operation that destroyed a unit. **BLOCKER**

§10.2 step 2: *"ChromIQ reads the stored measurement and confirms it is a flat,
high, tile-shaped spectrum. That is what a just-calibrated white reference reads
by definition."*

The research repo says, verified and twice re-derived, that this confirms
**nothing**:

- `chromiq-cr30-research/CALIBRATION.md:26-33` — pressing the button with a
  magnet present *"is performing a white calibration against whatever is under
  the aperture, and reporting the nominal tile value as confirmation."*
- `CALIBRATION.md:340-347` — the returned value is **bit-identical before and
  after the unit's calibration was destroyed with green**, and identical again
  after the restore (`EXP-MEAS-002/003`, `EXP-BLE-010`). *"A value that survives
  having the stored white reference overwritten with green is not derived from
  the stored white reference. It is the tile's nominal characterisation, held in
  firmware."*
- `MEASUREMENT.md:396-401` — *"the gated reading is a stored constant with no
  dependence whatsoever on the optical input."*

So the value §10.2 inspects is a **firmware constant returned regardless of what
the reference was just calibrated against**. It is flat, high and tile-shaped
when the calibration is perfect and *equally* flat, high and tile-shaped when
the user has just calibrated against a green cap the wrong way round. **The
check cannot fail in the case it exists to catch** — which is exactly the
incident §10.2 cites as its justification (`CALIBRATION.md:7-15`, paper reading
156.8 %R afterwards).

Worse: §10.2 makes that operation **mandatory before every chart read**, and
Guided mode cannot skip it. ChromIQ would be instructing the user, every single
session, to perform the one action that can silently destroy their white
reference — cap on backwards, cap on a coloured surface, cap missing — and would
then report success.

Step 3 ("remove the cap, confirm the next reading is not the tile constant") is
sound as far as it goes: it catches "user forgot to remove the cap". It does not
and cannot detect a bad reference.

**The real check exists in the research and the design does not use it.**
`CALIBRATION.md:354-358`: *"If the firmware holds the nominal tile values, then
measuring the actual tile with the gate disengaged and comparing against them is
a real calibration test."* That is: capture the firmware constant (gated, cap
on), then measure the tile **with the gate disengaged** and compare. A
mismatch means the reference is wrong. That check has real discriminating power
and needs no new command. It is a hardware experiment away, and it is what
§10.2 should be doing.

The plausibility bound (`workflow/cr30/measurement.py:95`,
`MAX_REFLECTANCE = 130.0`) is the only working defence today, and the file
itself records its limit at `:73-95`: *"A corruption factor below 130/96.4 =
1.35 never breaches MAX on paper."* The observed corruption was 1.83×; anything
milder is invisible.

### A7 — the §10.2 acknowledgement has nowhere to go on the `-x` path. **BLOCKER**

The existing calibration subsystem does work, and the design is right to reuse
it — but every exit of the dialog replies **to the helper process**, not to a
backend:

`ui/tabs/tab_measure.py:7046-7062` —
```
skip     → self._manager.send_key("s")     → {"cmd":"skip"}  → key 's'
accept   → self._manager.send_key("\r")    → {"cmd":"accept"}→ key 0x0d
dismiss  → self._manager.send_key("\x1b")  → {"cmd":"quit"}  → key 0x1b
```
Each lands in `cq_pending_key` (`chromiq_json.c:181-188`) and is consumed only
by `cq_wait_char()` (`:250-258`). **The `-x` value prompt does not call
`cq_wait_char` — it calls `con_fgets` (`chromiq_chartread.c:2805`).** So the
acknowledgement is queued and never consumed: the CR30 backend, which raised the
prompt, never learns the user answered.

Answers to the four questions put to me:

1. **Can a non-Argyll backend drive `calibration_prompt`?** The *signal* yes —
   `workflow/measure_manager.py:200` is a plain `pyqtSignal`, and the tab
   connects it at `ui/tabs/tab_measure.py:998`. Nothing about raising it is
   Argyll-specific. Today it is raised only from the `cal_required` engine event
   (`measure_manager.py:1373-1375`) and once synthetically at `:1549`. **The
   reply half is what is hard-wired**: `_on_calibration_prompt` has no callback,
   it writes to the child process's stdin. A CR30 backend needs a distinct reply
   route, and the tab must know which one to use.
2. **What does "retry" mean, and can it deadlock?** `_handle_cal_failed`
   (`measure_manager.py:484-533`) sends `{"cmd":"retry"}` (`:531-535`) into the
   same dead channel. Its own docstring at `:487-491` is the warning: *"The
   engine blocks waiting for a reply here (`cq_wait_char`), so this must ALWAYS
   send something — otherwise the run deadlocks."* In `-x` mode the engine is
   **not** blocked in `cq_wait_char`, it is spinning in the A1 loop, so nothing
   deadlocks — it burns CPU instead. Either way the retry never reaches the
   CR30. And for a CR30 "retry" has no meaning at all: there is no host-issued
   calibration command, only "ask the human to press the button again."
   **`CR30.trigger_unsafe` must not be used for it** — `workflow/cr30/device.py:95-118`
   and `CALIBRATION.md:42-48, 335-338` ban a host trigger with a magnet present,
   and the calibration step is by definition performed with a magnet present.
3. **`sensor_wrong_position`** (`measure_manager.py:220`, consumed at
   `tab_measure.py:1035` → `_on_sensor_wrong_position` `:6151`) is **advisory
   only** — nothing gates on it, it raises a warning window. A CR30 simply never
   emits it. No downstream requires it. **Not a problem.**
4. **Does the reused wording fit?** The dialog body comes from
   `calibration_instructions_html(instrument_family(self._detected_instrument))`
   (`tab_measure.py:6994-6998`). Two faults:
   - `_detected_instrument` is set from the `instrument` engine event
     (`measure_manager.py:1179-1181` ← `chromiq_chartread.c:977`), which is
     **inside the instrument-open block and never fires in `-x` mode**. So the
     family resolves to `None` and the user gets the *generic* text.
   - A CR30 branch **has already been written** into `ui/ti2_loader.py`
     (`is_cr30` `:110`, `instrument_family` `:121`, `calibration_instructions_html`
     and the patch/strip instruction texts) — good text, and correct about the
     magnetic cap. But it is unreachable until `_detected_instrument` is set from
     something other than the engine event. **The design must say where the CR30
     family comes from in `-x` mode** (the chart's `TARGET_INSTRUMENT`, since the
     `.ti3`'s says "Unknown Instrument" — see A3).

   The dialog's own chrome is still wrong for a CR30: title *"Calibration
   Required"*, button *"Start Calibration"* (there is nothing for ChromIQ to
   start — the human presses the instrument's button), and the optional-step
   note *"You can skip it and carry on measuring, but your readings may be a
   little less accurate without it"* — which for a CR30 is a **material
   understatement** given A6. All three are §M-governed text.
