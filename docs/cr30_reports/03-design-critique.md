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

---

## B. SERIOUS

### B1 — SpectroScan is the **wrong** template, for the opposite reason the design gives. **SERIOUS**

§3 justifies SS over ColorMunki with *"SpectroScan is already the spot-grid
shape — `pspa=0.0, tspa=0.0, lcar=0.0, rpstrip=999, dorspace=False,
dopglabel=False`."*

**Three of those six fields are shared with ColorMunki and prove nothing.**
Read `workflow/layout_engine/instruments.py:354-509`: `rpstrip=999`,
`dorspace=False`, `dopglabel=False` are set identically on the i1/p3 branch
(`:383-385`), the CM extra-high branch (`:427-429`) and the CM normal branch
(`:444-446`). Only `pspa`, `tspa` and `lcar` actually separate SS from CM.

And those three are the ones that **must not** be copied. The SpectroScan is a
**motorised flatbed XY table**: the head is machine-positioned to the patch
centre, so `pspa = 0.0` (`:463`) and `rrsp == pwid` (`:463`) put every patch
edge-to-edge with its four neighbours — and `raster.py:1236-1245` deliberately
tiles them *seamlessly* ("Tying the spacer's bottom to the next patch's top
tiles them seamlessly"). Zero separation is a **consequence of machine
positioning**. A CR30 is hand-placed.

The design's own evidence contradicts it. `EXP-SPEC-001a` — the one successful
hardware read it cites — was a **ColorMunki double-density chart, 10.4 × 13.0 mm
patches**. That is `instruments.py:414-436`, and that branch sets
`pspa_e = pscale * 1.3` (`:433`) — **a 1.3 mm spacer between patches along the
pass**. §4 then specifies "Spacers: **none**". So the design removes the one
geometric feature present in the only layout a CR30 has been proven to read.

Two further consequences nobody has costed:

- **`build()` silently ignores the spacer control on an SS-shaped geom.**
  `instruments.py:218-219`: `if spacer_width is not None and geom.pspa > 0`.
  With `pspa == 0` the Manual "spacer width" box does nothing. `inter_patch`
  (`:220-221`) still works, so there *is* a route — but the obvious control is
  dead and nobody will find that out until a beta tester tries.
- **The notes / clip band cannot be turned on at all.**
  `instruments.geom_from_build_kwargs:311-315` gates the band on a hard-coded
  `("CM", "SS")` tuple. Measured on a simulated CR30 registration:
  `clip_content_mode="notes"` → `lbord = 0.0`, `has_clip_border = False`
  (SS under the same kwargs → `lbord = 20.0`, `True`). §4 says the clip border
  is *"off by default, **offerable**"*. **As designed it is not offerable, it is
  silently inert**, and three more `("CM","SS")` tuples in
  `ui/dialogs/layout_options_panel.py:1857, 1946, 2289` gate the UI half.

**What the SS branch has that the design never mentions, and should keep:**
`rlwi = 7.5` (`:466`) reserves a left band in which `raster.py:1212-1234` draws
**row numbers** down the side, giving the chart a 2-D `A1 / A2 / B1` coordinate.
For a human hunting one patch in a 513-patch grid that is the single most useful
piece of furniture on the sheet, and it exists only on the SS branch. It is a
much better argument for the SS template than the six fields §3 cites — and it
is the one the design does not make.

**Recommendation:** a CR30 branch of its own — SS's `rlwi`, `padlrow=False`,
`ruler_mm=0.0` and `lcar=0.0`; CM's non-zero `pspa` (a real white gutter a hand
must aim inside); the CM/SS clip-band gate extended to CR30 in all four places.

### B2 — the design does not choose `layout_mode`, and the default is not the SS one. **SERIOUS**

`presets.LayoutRecipe.layout_mode` defaults to `"area_first"` (`presets.py:75`)
with `area_method = "by_width"` (`:78`). `default_recipe` sets
`r.layout_mode = "patch_first"` **only for `"SS"`** (`:408-409`), with a comment
explaining why a device with no fixed strip length needs it. A new `"CR30"` key
gets neither branch. Measured on a simulated registration:

| mode | patch | grid | capacity/A4 |
|---|---|---|---|
| `patch_first` | 10.00 × 10.00 | 19 × 27 | **513** |
| `area_first` (default) | 10.02 × 10.17 | 19 × 28 | **532** |

So `area_first` is not the disaster the SS comment fears (the "grow from the
instrument's natural width" rule at `area_fit.py:110-115` saves it) — but the
patch size stops being 10 mm and becomes whatever fills the page, which flatly
contradicts §4's "10.0 × 10.0 mm (provisional), labelled provisional in the UI".
**Pick one, deliberately, and say so.**

### B3 — 513 patches per A4 page at ~2 s each. The design has no answer for the session length. **SERIOUS**

Measured (`geometry.compute` on the SS-templated 10 mm geom, A4 portrait):
**513 test patches per sheet**. A routine ChromIQ RGB profiling target is
several hundred to ~1000 patches. At the design's own "~2 s per patch" that is
**17 minutes per sheet** and **~30 minutes for a 900-patch chart**, every one of
them a hand placement and a button press.

The design says nothing about:
- a recommended patch count for a CR30 (the Guided patch-count advice comes from
  `data/patch_db.py`, which will have no CR30 rows);
- resting and resuming a session — **`-r` resume does work on the `-x` path**
  (verified: read A1/A2, killed, re-ran `-xx --autosave -r`, it resumed at A3 and
  appended correctly), so this is a documentation/UI gap, not a code one;
- instrument drift over a 30-minute session, which is the one thing §10.2's
  once-per-session calibration cannot cover.

### B4 — every key-sending exit in `measurement_exit_strategy.md` Table 1 is inert on the `-x` path. **SERIOUS → BLOCKER if A1 is not fixed**

`docs/design/measurement_exit_strategy.md:85-112` is binding and specifies, for
each window, the exact key sent. In `-x` mode the value prompt reads with
`con_fgets` (`chromiq_chartread.c:2805`) and never touches `cq_pending_key`, so
**every one of those keys is queued and never consumed**:

| Table-1 row | Sends | On the `-x` path |
|---|---|---|
| Keep what you have measured so far? → Save and stop | `q`, `q` | queued, inert — the session does not end |
| Instrument Error → Retry | `\r` | inert |
| Patch Read Failed → Retry / Skip Patch | `retry` / `skip` | inert |
| Calibration required → OK / Skip / Cancel | `\r` / `s` / `\x1b` | inert (see A7) |
| All Patches Read → Go to … Tab | `d` | inert — the measurement never closes normally |
| Discard and stop | kills the process | works (SIGKILL) |
| Stop / Give Up (`{"cmd":"quit"}`) | `\x1b` | inert **or**, if it ever reaches the dispatch, SIGSEGV (A2) |

So the *only* working ending on the `-x` path is killing the process. That
violates the spec's whole premise — it exists so that every window has one
honest ending. Fixing A1 (route the `-x` read through the command queue) fixes
this row for row; nothing else will.

### B5 — the colour-science section describes a converter that does not exist yet, and the one on disk defaults to the wrong condition. **SERIOUS**

§5 states ChromIQ converts to XYZ under **D50 / CIE 1931 2°** *"using the
validated converter (`cr30/colour.py`, self-checked against published white
points and reproducing the device's own Lab to ΔE 0.054)"*.

Read `workflow/cr30/colour.py`:
- the module default is **D65 / CIE 1964 10°** — `XBAR, YBAR, ZBAR = OBS["10"]`
  (`:90`), `spectrum_to_xyz(refl, illum=D65)` (`:102`), `OBSERVER = "CIE 1964 10
  degree (device default)"` (`:91`);
- the only way to get D50/2° is `use_observer("2")` (`:93-99`) — a **process-wide
  mutable global**, plus passing `illum=D50` at every call site;
- **the ΔE 0.054 figure validates the D65/10° decode, not the D50/2° output.**
  The module docstring (`:16-26`) is explicit: the vendor-Lab agreement is
  `D65/10 → ΔE 0.02`, and `D50/2 → ΔE 2.79`. §5 cites a number earned under one
  condition as validation of a different one.
- nothing in `workflow/cr30/` calls `spectrum_to_xyz` yet (grep: no callers
  outside `colour.py`). The conversion the design specifies is unwritten.

A module-level observer global that any Tool or report could flip mid-session,
silently changing what lands in a `.ti3`, is exactly the class of defect
`CLAUDE.md` records having cost this project a week (module globals across a
boundary). **Make the observer/illuminant an explicit argument at the call
site; never a global.**

**What IS right, and verified by running the helper:** the *scale* is correct.
`chromiq_chartread.c:3083` takes `-xx` values verbatim (`scols[pix]->XYZ[i] =
atof(bp)`), and `save_ti3` writes them unchanged into `XYZ_X/Y/Z`
(`:420-424`, `nn = {1,1,1}` for a reflective chart). The `-xl` path proves the
expected scale: it does `icmLab2XYZ(&icmD50, …)` then `×100` (`:3088-3093`). So
**`-xx` wants D50-relative XYZ on a 0–100 scale**, and
`colour.spectrum_to_xyz` already normalises to `k = 100 / Σ(illum·ȳ)` (`:104`),
i.e. Y=100 for a perfect diffuser. That matches. Confirmed output:
`COLOR_REP "iRGB_XYZ"`, `DEVICE_CLASS "OUTPUT"`, no `SPECTRAL_*`.

One residual, **NOT VERIFIED**: ChromIQ's other instruments produce XYZ through
Argyll's own observer (CIE 2012 2°, per `colour.py:26`). A CR30 profile and an
i1Pro profile of the same printer will therefore differ by the observer, not
only by the instrument. Whether that difference is material for print profiling
would be settled by converting one measured spectrum both ways and comparing
ΔE — worth doing before the beta claims parity.

### B6 — the BLE-first framing of §10.1 is contradicted by the research's own conclusion. **SERIOUS**

§10.1 makes automatic BLE reconnection a first-class designed behaviour and
relegates USB to *"the more robust transport for a long chart … as information,
not a block"*. The research says something stronger:

`chromiq-cr30-research/MEASUREMENT.md:662-666`: *"Over BLE there is no
equivalent. The device's BLE button announcement is a 10-byte frame with no room
for it, and the BLE read path is a poll. **BLE spot reading has no
protocol-level magnet detection at all** — which is a real argument for
preferring USB in a shipping backend, and cuts against the enthusiasm in
`STATUS.md`."*

So over BLE the *only* magnet defences are the tile-constant match (unit-specific
per §9.1, and see A6) and the bit-identical check. §6's table lists the magnet
row without saying it is USB-only. **The design must state, per transport, which
guards are live** — and given A6, "BLE + magnet" is a data-integrity hole, not a
convenience note.

### B7 — "reading identical to previous" is not a guard, it is the **trigger mechanism**, and the design never says so. **SERIOUS**

ChromIQ has no way to know the user pressed the button. It polls the device's
*stored* measurement. `MEASUREMENT.md:516-520` is explicit: *"A backend reads the
stored measurement, so it must know when a new one has arrived — and 'the reading
did not change' is also the magnet-gated signature. **No counter has been
found.**"*

So `Measurement.identical_to` (`workflow/cr30/measurement.py:167-177`) is doing
two jobs at once: it is the **only** signal that a new reading exists, and it is
listed in §6 as a *rejection rule*. The design presents only the second. The
consequences it therefore never addresses:

- **What does ChromIQ do while nothing has changed?** Poll forever? At what
  interval? Over BLE, at what battery cost? There is no timeout, no "still
  waiting" state, no cancel semantics in §6.
- **Two genuinely identical consecutive readings hang the run.** Unlikely given
  the measured noise (`EXP-SPEC-001b`), but there is no escape hatch: the user
  cannot force-accept, and §6's rule says reject.
- §10.1.4 claims the bit-identical guard catches the post-reconnect stale
  reading. **It does** — but only because it is the same mechanism that detects
  *any* new reading. The design should say that once, plainly, rather than
  presenting it as a defence earning its place twice.

### B8 — `chartread_engine = "argyll"` has no CR30 behaviour, and `patch_by_patch` becomes a lie. **SERIOUS**

Two related gaps:

1. **The stock-chartread fallback.** Covered under A5. Additionally,
   `measure_manager._engine_should_fall_back` (`:537+`) can **automatically**
   relaunch a failed engine run on stock chartread. For a CR30 chart that means
   automatically relaunching into a fatal `Unrecognised chart target instrument`.
   The design does not exclude CR30 from the fallback.
2. **`-p` is irrelevant in `-x` mode.** `read_strips` initialises `rmode = 0`
   (spot) at `chromiq_chartread.c:887` and every assignment that could change it
   (`:1209-1402`) is inside `if (xtern == 0)`. So an `-x` run is *always* spot,
   whatever `patch_by_patch` says. But `patch_by_patch` is a visible per-target
   checkbox in both Guided and Manual (`ui/tabs/tab_measure.py:11157, 11175`,
   stored at `workflow/measure_settings.py:48, 71`). For a CR30 chart it will
   show unticked while the read is patch-by-patch regardless. Force it, hide it,
   or explain it.
