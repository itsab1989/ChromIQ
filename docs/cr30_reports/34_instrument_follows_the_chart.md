# 34 — Does the instrument choice follow the chart?

**Question (owner's words):** "when chromiq recognizes the chart that is loaded is made for
another instrument it will then not scan for a cr30 right? or at least it should recognize
the correct instrument for the chart. -> can this be proven?"

**Answer: YES — proven on screen, in every direction, with both instruments attached.**

The instrument choice follows the chart's `TARGET_INSTRUMENT`, and it was driven on the real
app with the CR30 **and** the ColorMunki both plugged in over USB:

- A chart made for another instrument **never scans for a CR30** — not over USB, not over
  Bluetooth. The app-log slices for the ColorMunki, i1 Pro and no-instrument charts contain
  zero CR30 lines; the reader opened the ColorMunki and named it on screen.
- A chart made for an i1 Pro, measured with a ColorMunki connected, raises **"This chart was
  made for a different instrument"** naming both, before a patch is read — his fallback wish
  ("it should recognize the correct instrument for the chart") is already the shipped behaviour.
- A CR30 chart takes the CR30 path even when reopened from a project (the `.ti1` trap), and is
  **refused** for stock ArgyllCMS chartread with the M-CR30-STOCK-READER window.
- No case was found where a chart is measured by an instrument it was not made for without the
  user being told. Two cosmetic log-wording items (beta 2 at most) are ranked below.

## Part 1 — The code map (static; every claim here re-proven on screen in Part 2)

**The single decision point.** `TabMeasure._chart_is_cr30()` (ui/tabs/tab_measure.py:5498)
is the only CR30 question in the tab. It resolves whatever file the tab holds through
`_chart_file_for()` — a `.ti1` becomes its sibling `.ti2` — because `TARGET_INSTRUMENT`
is a `.ti2` keyword and a reopened project hands the tab `run.chart_ti1`
(ui/main_window.py:2397). Its docstring records that two open-coded reads existed and
were both wrong; both now route through this one method.

**Every CR30 path is gated on that method:**

| CR30 mechanism | Where | Gate |
|---|---|---|
| `-xx` external values to ChromIQ's chartread fork | `_apply_engine_params` (tab_measure.py:12803): `p.stock_reader_cannot_read = p.external_values = self._chart_is_cr30()` — set BEFORE every early return | the chart |
| The reading bridge `_open_cr30_bridge` | tab_measure.py:5840-5845 (`if params.external_values:`) and `_run_cr30_calibration`:7107-7110 | `params.external_values` → the chart |
| CR30 calibration (`_run_cr30_calibration`) | tab_measure.py:5696 (`if params.external_values and not params.disable_initial_cal`) | `params.external_values` → the chart |
| Device discovery (`workflow/cr30/discovery.py::candidates`) | called ONLY from `workflow/cr30/device.py:113`, reached only through the bridge | the bridge → the chart |
| The Bluetooth fallback scan (`CR30: no USB device …; trying Bluetooth`, measure_bridge.py:679) | inside the bridge's connect | the bridge → the chart |
| Patch-by-patch lock + dead options + no-swipe arrow | `_apply_cr30_pbp_lock` / `_apply_cr30_dead_options` / `set_no_swipe` | the chart |
| Stock-reader refusal `M_CR30_STOCK_READER` | `_blocked_by_stock_chartread_for_cr30` (tab_measure.py:4703), runs FIRST in `_on_start` (5604) | the chart + the selected reader |

**No side doors found.** `workflow/cr30/*` is imported outside its package only by
`ui/tabs/tab_measure.py` (the bridge). The Settings dialog's CR30 mentions are labels
and help text, no device I/O. `core/usb_driver_installer.py` only *names* the CH340
bridge in a table; its own comment refuses to treat "a CH340 exists" as "a CR30 is
attached". `_start_averaging_read` (10812) delegates to `_on_start()`, so re-reads pass
the same guards. All chart-load routes (Check tab, Print tab, project open ti1 AND ti2,
per-target settings restore) converge on `set_ti1_path`.

**The three chart answers, statically:**
- `TARGET_INSTRUMENT "CR30"` → `is_cr30` True → external values, bridge, CR30 calibration;
  stock chartread never gets the chart (with the ArgyllCMS reader selected in Preferences,
  `M_CR30_STOCK_READER` refuses/offers the switch before anything is armed).
- Another known name (e.g. `"GretagMacbeth i1 Pro"`) → False → normal chartread path with
  the user's `-c` instrument; no bridge, no discovery, no Bluetooth.
- No `TARGET_INSTRUMENT` at all (`read_target_instrument` → None) → False → normal path;
  `_blocked_by_unusable_target_instrument` treats absent as fine (ArgyllCMS default).
- An UNKNOWN name → repair window ("This chart names an instrument ArgyllCMS cannot use"),
  which can rewrite near-miss CR30 spellings ("ChnSpec CR30", "CR-30") to the exact "CR30".

**Does the app TELL the user which instrument the chart expects?**
- Proactively, for a CR30 chart: yes, visibly — the patch-by-patch box locks ticked+greyed
  in both modules, incompatible options grey out with a tooltip naming the CR30, and the
  preview loses its swipe arrow.
- For non-CR30 charts: no standing label names the chart's instrument before Start. The
  warning is reactive: when the connected instrument identifies itself, 
  `_warn_if_instrument_does_not_match_chart` (tab_measure.py:4936) raises "This chart was
  made for a different instrument", comparing the CHART's `.ti2` (not the preference —
  fixed 2026-08-08) against the identified model. Measure anyway / Cancel.

_Static analysis is the map, not the proof. Part 2 drives the real app._

## Part 2 — Driven on the REAL app, on screen, with BOTH instruments attached over USB

Method: the real `MainWindow`, real fonts/style/theme, the REAL settings store
(`com.chromiq.ChromIQ` — exported first, re-imported byte-identical afterwards), and every
project entered through the **session-restore path** (`main_window.py:2397`), which hands the
Measure tab `run.chart_ti1` — the documented `.ti1` trap, deliberately chosen as the entry for
every case. Four projects were cloned from `CR30-Test` (his original untouched) with only the
`.ti2`'s `TARGET_INSTRUMENT` edited per case; both his CR30 and his ColorMunki were physically
attached over USB throughout. Driver: `34_shots/drive_proof34.py`; screenshots + full UI logs
in `34_shots/`. The CR30 was sent nothing: `DeviceReader` opens the device on first use, and in
every case Cancel was taken before any first use — confirmed by the app-log slices, which
contain **zero device I/O lines** for the CR30 in all five runs.

| # | Case (chart says) | Reader pref | What the app did on screen |
|---|---|---|---|
| A | `"CR30"`, reopened via `.ti1` | ChromIQ | `_chart_is_cr30()` → **True** through the trap. Patch-by-patch locked ticked+greyed, tooltip names the CR30; log announces `Chart instrument: CR30 → …` before Start. Start → **"Calibrate your CR30 before measuring"** window (shot `cr30_engine-02`). Cancel → "[STOPPED] You cancelled the calibration…"; no reader process, no device I/O. |
| B | `"CR30"` | stock ArgyllCMS | Start → **M-CR30-STOCK-READER** refusal (shot `cr30_stock-02`): "Standard ArgyllCMS chartread does not know the CR30 at all…", offering the one-click switch. Cancel → nothing armed, nothing started. The chart is never handed to stock chartread. |
| C | `"X-Rite ColorMunki"`, both instruments attached | ChromIQ | No CR30 anything. The reader opened the **ColorMunki** — live log: `Instrument Type: ColorMunki`, serial 4009154 (shot `munki-03`), then the ColorMunki dial-calibration window naming "your ColorMunki / i1Studio" (shot `munki-02`). Cancelled → "Measurement stopped — no measurement (.ti3) file was created." **App-log slice: 0 CR30 lines** — no USB probe, no `trying Bluetooth`. |
| D | `"GretagMacbeth i1 Pro"`, ColorMunki attached | ChromIQ | **The owner's exact scenario.** The connected instrument was opened and identified, and ChromIQ raised **"This chart was made for a different instrument"** (shot `i1pro-02`): "laid out for: i1Pro / i1Pro 2 / i1Pro 3 — but the instrument connected is: ColorMunki / i1Studio / ColorChecker Studio", with Measure anyway / Cancel. Cancel stopped it. 0 CR30 lines. |
| E | *(no `TARGET_INSTRUMENT` at all)* | ChromIQ | Normal path, no CR30 scan (0 CR30 lines), ColorMunki opened and named. One oddity, see finding 2 below. |

What a user concludes from the screens: in A they are unmistakably in a CR30 flow before
anything runs; in B they are told plainly why the measurement will not start and given the fix;
in C the right one of the two attached instruments is opened and named twice on screen; in D
they are stopped with both instrument names side by side before a patch is read.

## Findings, ranked by user harm (none blocks anything; owner routed all of this to beta 2)

1. **Nothing silently measures with the wrong instrument.** In all five driven cases the
   routing followed the chart and the app said what it was doing. The one crossing that could
   *look* like a working measurement on the wrong device (D) raises a named, two-sided warning
   — and "Measure anyway" there is the documented, deliberate design (a warning, not a
   refusal: the measurement is the user's to make).
2. **Merely confusing (beta-2 wording candidate):** a chart with NO `TARGET_INSTRUMENT`
   produces Argyll's own line `Warning: chart is for GretagMacbeth i1 Pro, using instrument
   X-Rite ColorMunki` in the log — chartread *assumes* i1 Pro when the keyword is absent, and
   the raw line makes it look as if the file names an instrument it does not. Verified the
   clone contains no `TARGET_INSTRUMENT` anywhere (grep, exit 1). ChromIQ's own window is
   correctly silent here (its rule: absent is fine). Cosmetic.
3. **Only untidy:** with no `TARGET_INSTRUMENT` there is no load-time "Chart instrument: …"
   line (there is nothing to announce) — the user first learns which instrument will be used
   when it identifies itself after Start. A "chart names no instrument — using the connected
   one" line would close the last gap in "the app tells you", but no behaviour is wrong.

## Not driven, and what it would take

- **The unknown-name repair window** ("This chart names an instrument ArgyllCMS cannot use")
  — statically mapped (tab_measure.py:4782) and covered by `tests/test_target_instrument_gate.py`;
  driving it needs a fifth clone with a nonsense name. Low value: it cannot route to any
  instrument, only repair or refuse.
- **Verification and calibration run types** — not driven separately. Statically, every
  chart-load route converges on `set_ti1_path` and every start on `_on_start()` (averaging
  re-reads included), so they pass the same guards; but that equivalence is proved by reading,
  not by driving. Driving them needs a verification chart / cal chart in a clone.
- **The Bluetooth-discovery negative** was proven by absence in the app log while the CR30 sat
  attached; the *positive* (that the log line fires when a CR30 chart is started with no USB
  device) was not re-driven tonight — it needs the CR30 unplugged.

## Cleanup

Settings re-imported and verified (`chartread_engine=chromiq`, `restore_last_session=0`,
`session_target=CR30-Test`); presets dir byte-identical (rsync dry-run: no diffs); the four
`Proof34-*` clone projects moved out of `~/ChromIQ` into the session scratchpad;
`~/ChromIQ/CR30-Test` never written to.
