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

