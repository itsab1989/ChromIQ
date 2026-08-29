# 19 — [CR30-DESIGN-5] Design challenge round 5

## In progress
Started 2026-08-28. Nothing verified yet.

Read: 17_verify4.md (full), 18_strip_design.md (full), git log (68f2b85b head).
Plan: D1 (Stop from the how-to window — verify _confirm_end_of_session with no
session / double-Stop races), D2 (BT fallback + cancellable wait), D3 (re-verify
F5 table from helper source, esp. -F INSTRUMENT_FILTER stamping), NEW LEAD
(vendor app sniffing — enumerate, map, capture design, verdict), leftovers
ranking, on-screen run.

## D1 — Stop from the how-to window: SAFE with two guards, and one claim in
17_verify4 is WRONG in general.
Verified mechanics (file:line):
- `_confirm_end_of_session` (tab_measure.py:6056-6130): gate is
  `self._manager.has_unsaved_readings` = `bool(self._read_something)`
  (measure_manager.py:971-981). `_read_something` is reset ONLY at session
  START (measure_manager.py:376), never at end. So "called with no live
  session it shows M-END-EMPTY" (17_verify4 F1) is true ONLY when the dead
  session read nothing. After a session that read patches, a stale call shows
  the full 3-button window claiming "You have read N patches … They are not
  in your measurement file yet" — false (they were written), and "Save and
  stop" then writes 'd' into a dead process (`write_stdin` → "no active
  process" warning + keypress_failed, argyll_runner.py:474-477).
- M-END-EMPTY is a LOG line, not a window (tab_measure.py:6071-6077), and
  returns "discard" → `_end_session` → `manager.abort()` → `runner.abort()`
  — kill on a dead/absent process is harmless (argyll_runner.py:467-473).
  So a genuine 0-patch Stop from the window ends cleanly. Verified.
- The window CAN outlive the session today: `_close_measurement_windows`
  (:6016-6033) rejects only `_live_measure_windows` (registered by
  `_exec_measurement_window`, :6001); the modeless `_cr30_how_dlg` (:7278)
  is never registered and never closed. 17_verify4 F1 point re-confirmed.
- Every ending funnels through `_on_measure_done` (:9416) — save exits the
  helper cleanly, discard kills it, done exits; all reach on_finish. So ONE
  close site suffices: `_close_measurement_windows` (called first in
  `_on_measure_done`, :9421).
- Double-Stop race: `_confirm_end_of_session`'s QMessageBox.exec is
  application-modal → the modeless window cannot be clicked while the ending
  window is up, and vice versa. No new race.
- Click-Stop-vs-done race: click processed first, box.exec() open, helper
  finishes → `_on_measure_done` runs inside exec's loop → user answers Save
  into a dead process. PRE-EXISTING with the main Stop button (same code
  path); the how-to Stop adds no new exposure. Same for a device_lost signal
  arriving during the ending window's exec (nested `_confirm_end_of_session`)
  — pre-existing; recommend a cheap re-entrancy guard while touching this.
DESIGN (verified-safe form):
1. Stop handler = `if not self._runner.is_running: return` then
   `self._on_stop()` (watchdog stop + END_STOP ending, parity with :6153).
   The guard replaces the main button's enablement gate.
2. Wire the button by `clicked`, NOT via QDialogButtonBox.rejected — else
   `dlg.reject()` from cleanup would re-enter the ending.
3. Close `_cr30_how_dlg` in `_close_measurement_windows` (and null it);
   `_cr30_how_shown` already resets per start (:5574).
4. X / red light stays dismiss-only (parity with every other how-to window).
5. Exit-table row + §M revision drafted (final message).
Call-site note: on the Calibrate-now path the window shows at :7042 BEFORE
`_manager.start` in code order, but `_on_start` completes before any click can
be processed, so the Stop handler always sees a live (or already-dead) runner —
never a "not yet started" one. If `_manager.start` itself fails the guard
returns quietly. F1's timing argument re-verified.

## D2(a) — verified: the silent Bluetooth continuation is REAL, and it is
silent at UI level.
- `DeviceReader._open` (workflow/cr30/measure_bridge.py:567-582): transport
  "auto" tries USB, falls back to BLE on ANY USB failure, every (re)open. The
  only trace is `log.info("CR30: opened over %s")` (:611) — python logger,
  not the tab's on-screen log. The tab builds a bare `DeviceReader()` (auto).
- After DeviceLost the handle is dropped (:620-627 in __call__), so the next
  read re-opens — this is exactly the Keep-measuring rearm path. Confirmed:
  a session that began on the cable can continue over Bluetooth with nothing
  on screen saying so.
- Integrity check: BLE wait is now EVENT-driven (push frame bb 01 00,
  EXP-BLE-013; device.py:270-326 wait_for_event) — but the METHOD DOCSTRING
  above it (device.py:227-232) still says "the wait is by CHANGE — poll the
  stored reading until it differs". The docstring contradicts the body it
  documents. New hygiene item.
- Magnet safety over BLE: no gate flag exists (device.py:383, :454-455);
  a capped press returns the firmware tile constant and is refused by
  `Measurement.check_usable(self._previous)` (device.py:324-326) — caught,
  but by heuristic, not by protocol.
- BLE reconnect device identity: ble discovery still picks `ok[0]` and falls
  back to UNconfirmed ffe0 devices (17_verify4 open item) — a silent
  reconnect could in principle grab a different device. One more reason the
  switch must be announced (and should name the device), never silent.
Verdict drafted in final message: ALLOWED, never SILENT — banner + log at
switch time, naming transport and device.

## D2(b) — the loop verified again at head; way-out design below.
`_on_cr30_device_lost` (tab_measure.py:7162-7196): Keep measuring → rearm()
→ `_start_read` → worker `__call__` → `_open()`: USB candidates fail fast,
BLE discovery ~12-17 s, ConnectionError → DeviceLost (:602-608) →
`_on_read_failed` DeviceLost arm (measure_bridge.py:452-460) → device_lost →
the SAME window. Loop period 15-20 s, forever. Confirmed unchanged.
Design: patient retry inside the open phase, cancel = the existing Stop
(bridge.stop() → reader.cancel() → the wait's `cancelled` callback →
MeasurementError with `_stopped` set → silent, ending already chosen), plus
the how-to window's new Stop (D1). Banner text + §M revision drafted in
final message. M-CR30-INSTRUMENT-GONE's "start the measurement again with
Refine/resume" (measurement_messages.py:172-175) is now the WORSE advice —
revision required either way.

## D3 — the F5 table re-verified from the helper source. It HOLDS, and the -F
fault is CONFIRMED, with one downstream consumer found.
Method: brace-counted the instrument block myself (awk over
native/chartread_helper/chromiq_chartread.c:918-1457, depth delta 0;
`if (xtern == 0) {` opens :918, closes :1457). Per flag:
- -c: runtime `new_icompaths` at :4219 guarded `if (!xtern && !cq_replay_active())`.
  The other call (:3249) is inside usage(). INERT confirmed.
- -B/-b: disbidi read only at :1896/:2330 (strip paths); spot mode is the
  xtern mode (":2600 Spot mode. This will be used if xtern != 0"). INERT.
- -S: `if (incflag && emit_warnings != 0)` at :3211 in the SPOT branch,
  xyzLabDE vs eXYZ challenge — runs under -xx. HONOURED confirmed.
- -N: nocal consumed instrument-side only; ChromIQ repurposes it to gate its
  own CR30 calibration window. HONOURED-repurposed confirmed.
- -H: highres :1429-1431 inside the block. INERT.
- -T: scan_tol solely :1209-1214 (inst_opt_scan_toll) inside the block. INERT.
- -A: scalstd :975 inside the block; DEVCALSTD written only when
  `ucalstd != xcalstd_none` (:321-324) and ucalstd is never set under xtern.
  INERT, no false record. Confirmed.
- -l/-L: dolab consumed in save_ti3 at write time (:369, :420-437). HONOURED.
- -n: spectral written only if `cols[vpix].sp.spec_n > 0` (:373); external
  values carry no spectrum. Inert by nature.
- **-F: CONFIRMED WORSE THAN DEAD.** fe parsed at :3616-3629; the instrument
  application (inst_opt_set_filter :1177) is inside the xtern block — but
  save_ti3 stamps INSTRUMENT_FILTER for pol/D65/UVCut at :325-332 with NO
  xtern guard, and the per-patch autosave passes cq_sctx.fe (:477), so every
  mid-session .ti3 carries it too. D50 (-F5) and none stamp nothing.
  ChromIQ really emits it: `_ChartreadOption.build_args` (tab_measure.py:
  814-823) reads isChecked() only, and the filter row (key="filter",
  flag="-F", :3056-3057) feeds extra_args. Downstream consumer found:
  Argyll spec2cie.c:495-498 consumes INSTRUMENT_FILTER=="POLARIZED"
  (sets calpol) — computational damage is limited (colprof does not read the
  keyword; spec2cie needs spectra a CR30 file lacks), so the fault is a FALSE
  PROVENANCE RECORD in a data file others export/read. Ruling: grey the row
  AND drop -F from the emitted args when `_chart_is_cr30` (with a log line);
  the one place where emission itself does damage. Everything else: disable
  only, never re-tick — verified save paths read isChecked()/value()
  regardless of enabled state, so per-target saves keep the user's values.
- per_target_settings.md: R3's "empty/disabled" is the CHECKBOX state, not
  widget-enabled state; disabling rows changes no stored vocabulary. No spec
  breach; add the one-line note to the spec only after owner approval
  (confirmed-only rule). 17_verify4 §4/§5 stand.
- 18_strip_design §3 note stands: if strip mode is ever built, -T's spinbox
  un-greys with a new ChromIQ-computed meaning — the greying tooltip should
  not hard-code "meaningless for this instrument" as a forever-fact. Wording
  drafted accordingly (final message).

### PROOF-D5-F — the false INSTRUMENT_FILTER stamp, reproduced on the real helper
scratchpad/fproof/drive_fproof.py: real chromiq-chartread, `--json -v -c 1
-xx -p -F 6`, CR30-Test.ti2 (390 patches), ONE value answered for A1, per-patch
autosave fired ({"event":"saved"}). The written .ti3:
    7:TARGET_INSTRUMENT "CR30"
    9:INSTRUMENT_FILTER "D65"
No instrument was opened; no filter exists on any CR30. The false-provenance
fault is fact, not reading-of-source. (Downstream: Argyll spec2cie consumes
POLARIZED; colprof ignores the keyword — so damage = false record + any
third-party reader, not profile numbers.)

## NEW LEAD — vendor app screenshots folded in (owner supplied; serial REDACTED
per standing rule — model/series only)
R1 BLACK CALIBRATION — corpus checked:
- CALIBRATION.md:119-130 (op report, no black TILE) remains TRUE. What the app
  DISPROVES is the corpus HYPOTHESIS at :147-149 ("not a user action with a
  black tile at all — may be performed internally"): the vendor's flow IS a
  user action — "measuring port downward, 1 m from the ground" = calibration
  against AIR. The missing black reference was never a tile; it is air.
- ORDER CONTRADICTION: CALIBRATION.md:340 says "black first, then white — per
  Pharmacist"; the app's wizard is White (step 1) then Black (step 2). One of
  them is wrong or order is free; the capture settles it.
- bb 10 = black cal is CORROBORATED vendor-capture knowledge (PROTOCOL.md:153,
  CALIBRATION.md:230) but NEVER sent here and the reply's 0x01 "success" byte
  has never been contrasted (CALIBRATION.md:233-238). Capture, never replay.
- Colour science (answer for the owner in final message): black cal is the
  dark/zero reference; reflectance = (S-D)/(W-D), so a stale D biases DARK
  patches most — shadow L* errors, smooth and invisible downstream. BUT the
  session evidence says THIS unit's zero is currently healthy: air reads
  0.002 % THROUGH the stored calibration (CALIBRATION.md:109) — i.e. current
  dark signal ≈ stored dark. So profiles already built are not impugned by
  this evidence; the exposure is DRIFT that ChromIQ can neither correct nor
  see. A read-only zero CHECK (trigger a normal air reading port-down and
  compare to ~0) is available TODAY without knowing bb 10; the CALIBRATION
  step itself is blocked on the capture.
R2 LIGHT SOURCE/ANGLE — verified display-only for our data path:
- ChromIQ converts the 31-band reflectance spectrum itself:
  spectrum_to_xyz defaults D50/CIE-1931-2° (workflow/cr30/colour.py:130-133,
  PROFILING_OBSERVER), which is what -xx/colprof expect. DeviceReader passes
  spectra only (measure_bridge.py:631-632).
- The device's own Lab (computed under its display setting, D65/10) IS parsed
  from the reply but consumed only by range sanity checks and metadata
  (measurement.py:137-141/:226); it never reaches the .ti3.
- Residual HYPOTHESIS to close in the capture session: that "Sync to
  Instrument" of a different illuminant does not alter the SPECTRAL reply.
  Test is free: change 1st light source to A, sync, re-read same patch —
  spectrum must be unchanged (embedded Lab may change). Until run, our
  independence claim rests on spectra-are-reflectance decoding evidence
  (air/paper %, vendor-Lab match at D65/10 from OUR recomputation).
R3 AVERAGE Single|Average — the one device setting that could change our data;
  worth capturing (it is what a real per-press quality control would be, and
  the 315 ms cycle is the budget). Unknown until captured whether it averages
  per trigger, changes timing, or is display-app-side despite the sync button.
R4 Tolerance tables / dE formulae / naming / find-similar — app-side QC
  display; ChromIQ computes its own dE from spectra. Nothing to mine. Agreed,
  with the one caveat that anything behind "Sync to Instrument" nominally
  touches device state — irrelevant to our data path either way (R2).

## NEW LEAD, part 2 — full submenu lists (owner). Coordinator's M1-M5 checked.
- M1 HOLDS with one caveat. Every listed item (colour spaces incl. densities/
  whiteness/opacity/metamerism, dE formulae, 25+ light sources, 2/10 observer,
  tolerances) is computable FROM the 31-band reflectance; none names an
  acquisition parameter (no integration time, gain, aperture, geometry, lamp,
  UV). Caveat: the Parameter screen's "Reflectance/Transmittance" field would
  be an acquisition mode if it were settable — on a CR30 it is identity
  (reflectance-only hardware), listed read-only. So: only Average could change
  what the sensor delivers. The principled "mostly no" stands.
- M2 HOLDS and PROOF-D5-F above already turned the -F consequence from
  reading-of-source into a reproduced artefact: INSTRUMENT_FILTER "D65" in a
  real .ti3 from an -xx run. No device counterpart exists to make -F honest.
  Grey the row AND stop emitting -F for a CR30 chart.
- M3: one sentence, in the greyed filter row's tooltip only ("the CR30's own
  display shows D65/10-deg numbers; ChromIQ computes profile values as
  D50/2-deg from the same spectrum, so the two read differently and both are
  right"). Anywhere more prominent is noise. Never touch the device setting.
- M4 agreed — Average is the one capturable device setting that could change
  measurement data; also the only honest cousin of the greyed consistency
  tolerance (device-side repeats per press).
- M5 agreed and stated plainly: tolerance tables, naming rules, find-similar
  formula are the phone app's own QC display. Nothing for ChromIQ to mine.
Capture plan shortened to 3 targets (black cal, white cal, Average toggle) +
one free R2 confirmation read. Steps in final message.

## ON-SCREEN — done (real app, real styling, sandboxed)
Driver: scratchpad/onscreen/drive_design5.py. Sandbox mirrors
tests/conftest 322c3d20 (QSettings→ini, DEFAULTS custom_output_path,
CHROMIQ_PRESETS_DIR, trash no-op); the project is a COPY of CR30-Test staged
into the sandbox; the real ~/ChromIQ untouched (backups from the earlier
round still at scratchpad/backup/).
- ~/Desktop/CR30-test-shots/cr30_design5_01_manual_options_live.png — full
  window, Manual module, CR30 chart loaded (`_chart_is_cr30()` printed True).
- ~/Desktop/CR30-test-shots/cr30_design5_02_options_closeup.png — the
  Additional Options group: High resolution (-H), Spectral filter (-F) set to
  D65, Patch consistency tolerance (-T) 0.7, XRGA (-A) all TICKED and LIVE;
  the option rows' build_args emitted `-H -F 6 -T 0.7 -A N` for this CR30
  chart. This is the state D3's greying removes, and the -F 6 shown is the
  exact input PROOF-D5-F turned into a false INSTRUMENT_FILTER "D65" keyword.
- Incident worth recording: the driver's first attempt hung on a REAL modal
  ("This chart already has a measurement") raised by set_ti1_path over the
  copied project — killed within the safety rule, re-run with modal
  suppression + a 60 s hard watchdog. No modal was left waiting on screen.

## Leftovers from 17_verify4 — status at 68f2b85b and ranking
CLOSED since 17_verify4: none of the minor list (68f2b85b closed the
navigation-press cost = F3, via abandon_current/ReadAbandoned — verified in
measure_bridge.py:359-384/:441-448 — but not the minors).
STILL OPEN, re-verified at head:
1. `_retries` not popped on the click-re-arm branch: on_patch_ready's
   already-read path (measure_bridge.py:296-313) emits patch_rearmed and
   falls to `_start_read` without `_retries.pop(loc)`; only rearm() (:355)
   and success (:502) pop.
2. Bare `DeviceReader()` (tab_measure.py:7069) — Q-A remembered address/port
   unimplemented; ble.py:189/:196 still `ok[0]` + unconfirmed-ffe0 fallback.
   D2 RAISES this one: a silent BLE reconnect with no pinned address is how a
   wrong device gets grabbed mid-session.
3. ble.py:1-14 poll-doctrine docstring still overstated.
4. calibrate() docstring still claims the read-back seeds `_previous`
   (measure_bridge.py, "leaves the reading this takes as the device's
   _previous") while the read-back passes enforce=False and device.py gates
   `_previous` on enforce. FALSE STATEMENT in code.
5. NEW: device.py:227-232 read_next_measurement docstring says the BLE wait
   "is by CHANGE — poll the stored reading" while the body waits on push
   events (EXP-BLE-013). FALSE STATEMENT in code.
6. EXPERIMENTS.md: zero entries for EXP-BLE-012..018 (grep count 0).
7. No §M entries for the flash texts (rearmed/dropped/discarded/calibrated —
   tr() literals in tab_measure:7103-7161).
8. Ending-window n==1 wording still "1 patch … They are not…"
   (tab_measure.py:6101-6106 region; read this round at :6099-6116).
9. V-17: M_CR30_PATCH_GAVE_UP still omits click-to-re-arm and advises
   Save-and-stop+resume (measurement_messages.py:187-205).
10. "using Argyll's default strip recognition" still logged for a CR30
   (tab_measure.py:3822).
RANKING (with the new lead): the black-calibration capture first (potential
correctness exposure ChromIQ can neither set nor see; also the cheapest path
to the long-wanted command, by observation); then the D1+D2+D3 build (already
scheduled — D3 now carries a PROVEN data fault, -F); then M-CR30-INSTRUMENT-
GONE text + V-17 (both advise the disruptive recovery); then Q-A remembered
address (17 s/session + wrong-device risk); then the two FALSE code
docstrings (4,5) which must not survive to release; then 1, 8, 7, 6, 10, 3.

## STATUS: COMPLETE — designs + answers in the final message.
