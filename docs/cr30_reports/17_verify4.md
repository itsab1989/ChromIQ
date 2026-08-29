# 17_verify4 — [CR30-VERIFY-4]

## In progress
Started 2026-08-28. Reading 16_verify3.md, git log, 0055b857 next. Nothing verified yet.

Read: 16_verify3.md (baseline), git log, 0055b857 full diff for the six code
files. Plan: F0 (captures vs no-beep claim), F1 (uncancellable window), F2
(message placement), F3 (first-press-eaten + generation-counter design), F4
(Keep measuring on disconnect), still-open list, on-screen F1/F2.


## F0 — VERIFIED: the no-beep claim has NO capture evidence. It was inference.
What the corpus actually holds:
- `captures/raw/EXP-BLE-015-trigger-calibrates.json` records means, tile
  matches, `announced: true` (a push FRAME arrived for the trigger) and push
  timestamps. It contains NO field for sound. Nothing audible was ever
  recorded, by any probe, in any capture.
- The probe (`tools/probe_ble_trigger_calibrates.py:220`) tells the human to
  "Watch the lights and listen for a beep" and then NEVER collects the answer
  — no prompt, no stored observation. The other magnet probes
  (`probe_ble_trigger_with_magnet.py:205`, `probe_ble_press_magnet_suite.py:
  216/255`) do ask and store, but they were the UNRUN variants; -015 is the
  one that ran.
- Worse: the no-beep claim is baked into the probe's PREMISE (docstring line
  4-5: "the owner's report that ChromIQ's Calibrate button produces no beep")
  and into its canned SUCCESS verdict ("the missing beep is a separate
  matter", :271) — a string composed before the experiment ran. The capture
  then "confirmed" wording the experiment never tested.
So CALIBRATION.md:292-295 ("The device does not beep for a host trigger with
the cap on") is supported ONLY by the owner's original impression, which he
has now corrected: it beeps on both transports, BLE was just slow (~1.85 s
cycle, since fixed). The claim must be corrected as an inference error, and
the "(A later observation: it DOES beep ... cap off ...)" parenthesis goes
with it — that distinction (gated=silent vs measuring=beep) was built on the
same unrecorded impression.
CODE COMMENT REPEATING IT: tab_measure.py:7016-7025 — "The CR30 beeps when
its own button is pressed and stays silent when the host asks — measured on
the owner's unit, EXP-BLE-015 ... he heard nothing". EXP-BLE-015 measured no
such thing. The comment's justification is false; the FEEDBACK ITSELF
(sound + confirmation) is still right — the owner liked it — only the
rationale must change from "the device is silent" to "the device's beep over
BLE came ~2 s late and the app said nothing meanwhile".
Corrected CALIBRATION.md wording: drafted below (final message too).


## F1 — VERIFIED mechanics; design below. MAJOR (honesty), not a spec breach.
Facts:
- `_show_cr30_measuring_window` (tab_measure.py:7226-7273): modeless QDialog,
  ONE button "Start measuring" (AcceptRole) wired to dlg.accept() only. No
  reject wiring, no closeEvent: X / red light = QDialog.reject() = close and
  nothing else. Never programmatically closed at session end either —
  `_cr30_how_dlg` is only ever ASSIGNED (:7272); nothing hides it in
  `_on_measure_done`, so it can outlive the session it describes (MINOR).
- Timing: shown at the end of the calibration flow (:7036) BEFORE
  `_manager.start` (:5714) in code order — but `_on_start` runs to completion
  before any user event is processed, so BY THE TIME A CLICK CAN LAND the
  helper is live. "Cancel before it starts" is not a state a button can ever
  observe; a Cancel here is necessarily an EXIT from a live session.
- Spec: measurement_exit_strategy.md's single-exit rule catches windows that
  END a session a second way; this window ends nothing, so it is not a §1
  breach — it is a lying gate. The window is NOT in the exit table at all.
- PARITY: every other instrument's post-calibration how-to window
  (`_on_calibration_done`, :7881-8127) has an OK button and closing it does
  not cancel either — identical dismiss semantics. What differs is the LABEL:
  theirs says "Calibration complete. You are ready to…" + OK (informational,
  honest); the CR30's says "Start measuring" (reads as a gate, and the §M
  entry itself promises "nothing on screen has to be pressed").
Design (recommend, needs §M-PROPOSED revision — the message is PROPOSED, so
revising it is the normal path, not a re-approval):
1. Rename the button OK (parity with :8118) — nothing is being started.
2. Body says the session is already running: the highlighted patch can be
   read the moment this window is up.
3. ADD a second button "Stop the measurement" (RejectRole) routed to
   `_on_stop` → `_end_session(_confirm_end_of_session(END_STOP))` — the
   single exit. With 0 patches read that shows M-END-EMPTY ("Nothing was
   measured, so nothing was saved") and ends cleanly, which IS the "never
   started" outcome the owner expected; with patches read it asks the
   three-button question. Both spec-correct with zero new exit machinery.
4. X / red light: keep as dismiss (parity with every other how-to window and
   with "the window is a reference card"), BUT only once the text stops
   claiming to be a gate. Wiring X to the ending question would punish
   dismissing instructions and has no precedent on the how-to windows (the
   All-Patches-Read Close→ending precedent is a COMPLETION window, different
   role).
5. Close `_cr30_how_dlg` in `_on_measure_done` / `_end_session` so it cannot
   outlive its session.
Exit-table addition needed once approved (new row: this window, Stop button →
the ending; OK/X → not an exit).

## F2 — VERIFIED placement. The flash renders at the BOTTOM OF THE LEFT
COLUMN, below the log — nowhere near where the user is looking.
- `_flash_status` (tab_measure.py:6276-6284) writes `_status_bar_lbl`,
  created at :1876-1879: last widget in `left_container`'s layout, directly
  BELOW `log_outer` ("Status bar (replaces main-window status bar)"). With
  the log VISIBLE it sits under the log (the owner's own correction); with
  the log HIDDEN (the hide-log switch) the label rises to sit just under the
  Start/Stop button container — which is exactly his first description
  ("over the start measurement button"). Both his reports are the same label
  in the log's two states.
- Sequence at calibration success (:7027-7036): sound → `_flash_status`
  ("Your CR30 has been calibrated.", 6 s) → `_show_cr30_measuring_window()`.
  The instructions window pops centre-screen at the same instant the flash
  appears bottom-left; the user reads the window and the flash expires.
Recommendation (answers 16_verify3's open visibility question too):
- CALIBRATION CONFIRMATION: put it IN the instructions window — that window
  IS the calibration flow's confirmation step, and the established
  instruments' equivalent (`_on_calibration_done`) already leads with
  "Calibration complete. You are ready to measure…" in title and body
  (:7926, :8081-8084). Parity fix: M-CR30-HOW-TO-MEASURE gains a
  calibration-led variant ("Your CR30 has been calibrated — ready to measure
  patch by patch") when reached via Calibrate now. §M-PROPOSED revision.
  Keep the log NOTE line; the status flash on this path becomes redundant
  (keep or drop — owner's call, recommend drop to avoid two voices).
- MID-MEASUREMENT messages (re-arm, dropped press, discarded readings):
  preview BANNER, not popup — `TiffPreview.set_banner` (ui/tiff_preview.py:
  1089-1096) exists, renders above the image the user is watching, is not a
  window (no exit-strategy table entry, no once-only-popup rule conflict).
  This is 16_verify3's ruling; F2's evidence confirms the status label is
  the wrong place because it is pinned to the bottom-left corner regardless
  of where the action is. Keep log lines as the durable record.


## F3 — mechanism VERIFIED from code (probe to follow); the generation fix is
RIGHT IN SHAPE but needs three corrections or it ships two new faults.
MECHANISM (file:line):
- While patch X is armed, its `_ReadWorker` is blocked in
  `DeviceReader.__call__` -> `read_next_measurement` HOLDING `self._lock`
  (measure_bridge.py:545, device.py:242/:300 wait loops).
- Click Y: `note_goto` (measure_bridge.py:345-354) sets `_nav_target=Y`,
  `_awaiting_loc=None` — and cancels NOTHING. The goto goes to the helper;
  spot_ready Y arrives; `on_patch_ready` -> `_start_read(Y)` (:373) sets
  `_reading_loc=Y` and starts W_Y, which immediately blocks on the LOCK W_X
  still holds (:545).
- First press: satisfies W_X (the only one actually reading). W_X returns,
  emits done(X, xyz) -> `_on_reading` (:451): `_reading_loc`==Y != X so left
  alone; `_why_not(X)` (:468-475): `_awaiting_loc`==Y != X -> DROPPED_STALE_LOC.
  Press eaten, reported. W_X releases the lock; W_Y starts waiting; press 2
  lands. Exactly the owner's 20:02:28 log and 16_verify3's shot 04.
- This costs the first press on EVERY goto while a read is armed — and a read
  is armed at all times during a session, so: every click, every time.
THE PROPOSED FIX (generation counter) — critique:
1. RIGHT: cancel the in-flight read on `note_goto`; never touch the one-way
   `_cancel` latch (12_skeptic2 A-3 stands; `stop()`/`close()` keep it).
2. CORRECTION 1 — the token must be captured at ARM time on the main thread
   (in `_start_read`, passed into the worker), NOT read inside
   `DeviceReader.__call__`. If the worker snapshots the generation at call
   entry, a second click before W_Y enters `__call__` (rapid double-click,
   trivially reachable — W_Y is parked at the lock for up to a second) gives
   W_Y a POST-bump generation: it is never cancelled, waits up to 180 s
   holding the lock, blocks W_Z behind it, and eats the next press —
   the F3 bug resurrected with a zombie in front of it. Duck-typed:
   `_start_read` asks `reader.begin_read()` for a token when the reader has
   one and hands the worker a closure that calls `reader(token)`; a plain
   injected callable (every existing test) is called as today.
3. CORRECTION 2 — a cancelled read MUST be distinguishable in
   `_on_read_failed`. Today a cancelled wait raises plain
   MeasurementError("cancelled while waiting…") (device.py:246-248/:304-306);
   only the `_stopped` guard (:404) keeps that quiet on Stop. A goto-cancel
   arrives with `_stopped` False and falls into the retry arm: `_retries[X]`
   +=1 (:437) and `read_failed.emit` puts "The CR30 could not be read for
   patch X … Press the button on the instrument again" on screen — a
   spurious failure flash on EVERY click, and 5 clicks near one patch reach
   MAX_READ_RETRIES-adjacent state. Fix: a dedicated exception
   (`ReadCancelled(MeasurementError)`) raised on the cancelled() paths, and
   `_on_read_failed` returns silently (log.debug) on that exc_type, touching
   neither `_retries` nor any signal. (`_reading_loc` is already safe: the
   `== loc` guard at :403 leaves Y's value alone.)
4. CORRECTION 3 — cancel LATENCY differs by transport and the design must
   say so: BLE `wait_for_event` polls `cancelled` every 0.05 s (ble.py:270-
   294); USB checks it only per outer iteration, i.e. up to 1.0 s inside
   `transport.receive(min(left,1.0))` (device.py:242-249) which has no
   cancel hook. A press within that window is still consumed by W_X and
   dropped WITH the existing message — the failure shrinks from "always" to
   "pressed within ~1 s of the click", which is acceptable and honest.
5. RACES EXAMINED: (a) read completes just before the click — the value is
   already past the cancelled() checks; `_on_reading` drops it
   DROPPED_NAVIGATING exactly as today; consistent. (b) press lands between
   W_X's cancellation and W_Y's arm — BLE: `drop_events()` at arm
   (device.py:288-296) discards it and reports it; USB: NO equivalent drain
   exists, the BB 01 09 header waits in the OS serial buffer and W_Y
   collects it instantly — a press made before the instrument could have
   been on Y is attributed to Y. That window is sub-second and PRE-EXISTS
   this fix (same gap after every normal value-send today); noted as an
   adjacent gap, not a regression. HYPOTHESIS: a `reset_input_buffer()`
   before the USB wait would close it; needs its own look (it must not eat
   a legitimate press after a fast highlight move).
6. Deadlock: none — `cancel_current()` only increments an int under the GIL;
   it takes no lock.
SHOULD THE PRESS BE DISCARDED AT ALL? With the fix the question mostly
dissolves: the cancel fires at CLICK time, so the ordinary first press now
lands in W_Y and is RECORDED for the patch the user pressed on. The only
discarded presses left are (a) within ~0.05-1 s of the click — physically the
instrument cannot yet be ON the new patch (the hand is on the mouse/trackpad),
so crediting the new patch risks exactly the invisible mispairing this module
exists to prevent (its own founding rule, measure_bridge.py:14-18) — drop,
with the message; (b) a press moments BEFORE the click (DROPPED_NAVIGATING):
by then the goto is already on the helper's stdin, so a value sent would land
on the NEW prompt and be recorded against the new patch — mispairing by
construction. Drop is not a default here; it is the only correct answer. Both
remain reported on screen.

## F4 — verified, and the hole is REAL: "Keep measuring" with the cable still
out is a window loop with a 15-20 s period.
Verified path (transport-independent, bridge level): choice None ->
tab_measure.py:7178-7189 `bridge.rearm()` -> outstanding `_awaiting_loc` ->
`_start_read` -> worker -> `DeviceReader.__call__`: `_dev` is None (the
DeviceLost handler at measure_bridge.py:568-576 closed and dropped the
handle) -> `_open()` (:530-541, transport "auto": USB first, then BLE).
- RECONNECTED: open succeeds (USB in ~a second), wait resumes on the SAME
  patch; the log already says "Carrying on: reconnect the instrument…".
  This is what the owner saw work.
- STILL OUT: USB candidates() fails fast, BLE discovery burns ~12-17 s
  (ble.py:189 discover timeout 12 s), ConnectionError -> wrapped DeviceLost
  (measure_bridge.py:556-561) -> `_on_read_failed` exc DeviceLost (:417-424)
  -> `device_lost.emit` -> `_on_cr30_device_lost` AGAIN: fault sound, log
  block, and the SAME ending window. So: window -> Keep measuring -> ~15-20 s
  of silence (log line only) -> fault sound + window again, for ever until
  the user picks Save/Discard or reconnects. Each round is escapable, so it
  is a nuisance loop, not a trap — but the silence between rounds and the
  re-appearing window are not honest about what ChromIQ is doing.
- WRINKLE worth telling the owner: with transport "auto", pulling the USB
  cable and choosing Keep measuring can reconnect the same instrument over
  BLUETOOTH if it is advertising — it works, but reads get slower and the
  only trace is the log's "opened over ble".
- TEXT CONTRADICTION: M-CR30-INSTRUMENT-GONE's own body
  (measurement_messages.py:158-175) advises "Reconnect it, then START THE
  MEASUREMENT AGAIN with Refine/resume" — written before Keep-measuring
  could survive a reconnect. The window now offers a better path than its
  own text recommends. §M revision needed when the batch goes for approval.
DESIGN RECOMMENDATION: "Keep measuring" should enter a patient reconnect
wait instead of one 15-s attempt per window: the re-arm's open, on failure,
retries quietly (say every 3 s, honouring cancel) while a banner/log line
says "ChromIQ is waiting for the instrument to come back — plug it in or
switch it on; everything measured is safe"; the window returns only on Stop
or a generous overall timeout. That turns the loop into one wait state and
makes Keep measuring mean what it says. Until then the behaviour is
survivable but should be described to the owner honestly (paragraph in the
final message).


## F5 — the options audit (owner's new question + ruling)
Method: every control read from `_make_manual_chartread_options`
(tab_measure.py:2997-3252) + the module-level controls in `_collect_guided`/
`_collect_manual` (:12029-12079), followed into `MeasureManager._build_args`
(measure_manager.py:1000-1040) and then into the HELPER SOURCE. The decisive
brace-count fact: the instrument-setup block `if (xtern == 0) {` opens at
chromiq_chartread.c:918 and CLOSES AT :1457 (counted, not inferred) — every
flag consumed only inside it is dead under `-xx`. `new_icompaths` is skipped
at :4218 (`if (!xtern …)`). Spot mode is FORCED by xtern (:2600).

### The table — control → flag → honoured on a CR30? → evidence
| Control (module) | Flag | CR30? | Evidence |
|---|---|---|---|
| Instrument number spin (G+M) | -c N | INERT | :4218 skips new_icompaths under xtern |
| Strip recognition combo + Auto (G+M) | -B/-b | INERT | disbidi read only in strip paths :1896/:2330; xtern forces spot :2600; CR30 is pbp-locked anyway |
| Suppress warnings (G+M) | -S | **HONOURED** | emit_warnings gates the SPOT-mode unexpected-response check :3211 — under -xx this branch runs; -S off ⇒ wildly-off readings are challenged for a CR30 too |
| Skip initial calibration (M only) | -N | **HONOURED — by ChromIQ, repurposed** | helper-inert (nocal :1187/:1907/:2617 all instrument-side) but gates ChromIQ's own CR30 calibration window, tab_measure.py:5575 (`external_values and not disable_initial_cal`); log wording already explains the changed meaning |
| Patch-by-patch (G+M) | -p | moot — forced + already locked | xtern forces spot :2600; `_apply_cr30_pbp_lock` :1394 |
| Refine/resume (G+M) | -r | **HONOURED** | file-level; hardware-proven (the owner resumed CR30-Test) |
| High resolution (M) | -H | INERT | highres :1429 — inside 918-1457 |
| Spectral filter (M) | -F | INERT, and WORSE | fe is instrument-side, but save_ti3 stamps INSTRUMENT_FILTER into the .ti3 for D65/UVCut/Pol regardless of xtern (:325-333) — a false record of a filter no CR30 has (the D50 default writes nothing) |
| **Patch consistency tolerance (G+M)** | -T | INERT | scan_tol consumed ONLY at :1209-1214 (`inst_opt_scan_toll`, gated on `inst2_has_scan_toll`), inside 918-1457. Goes to the INSTRUMENT (CLAUDE.md memory agrees) |
| Save L*a*b* (M) | -l | **HONOURED** | dolab consumed in save_ti3 at write time, OUTSIDE read_strips: icmXYZ2Lab conversion :420-437 — works on the XYZ the bridge supplies |
| Save L*a*b* AND XYZ (M) | -L | **HONOURED** | same, dolab==2 |
| Don't save spectral (M) | -n | inert BY NATURE | external values carry no spectrum (:3135-3183 parses numbers only); save_ti3 writes spectral fields only if `sp.spec_n > 0` (:373) — there is nothing to omit |
| XRGA correction (M) | -A | INERT | scalstd :975 — inside 918-1457. (DEVCALSTD keyword: written from ucalstd "actually used", which never gets set under xtern — no false record) |
| Overlay group, sounds, averaging UI | — | ChromIQ-side | not chartread flags; work as themselves (averaging on a CR30 chart NOT audited this round — one line to check next) |
(The `parameters.yaml` chartread section (-B/-b/-S/-N/-p/-H/-T, data/
parameters.yaml:1097-1200) is NOT rendered on the Measure tab — the tab
hard-codes its rows; the yaml text is catalogue/tooltip-only material there.)

### 2 — patch consistency tolerance, his named case
It is chartread's `-T`: a MULTIPLIER on the instrument's own within-patch
consistency threshold, applied via `inst_opt_scan_toll` to instruments that
take MANY samples per patch during a strip swipe and compare them (the row's
own tooltip already ends "Only some instruments support this (the i1 Pro and
ColorMunki families do); on others it is quietly ignored", tab_measure.py:
3129-3130). A CR30 press yields ONE sample per patch — there are no
within-patch repeats to compare, on any transport, under any flag. So it is
not merely unplumbed; the quantity it tolerances DOES NOT EXIST for this
instrument. Category (c): meaningless by nature. Could ChromIQ do its own
check? Not -T's check. What already exists in its place, honestly: (i) the
bridge refuses tile constants and bit-identical repeats
(Measurement.check_usable, device.py:394/:456); (ii) the helper's
dE-vs-expected sanity challenge DOES run for a CR30 when Suppress warnings is
unticked (:3211 — that is an accuracy check against expected values, the
nearest genuine safety net, and it is live TODAY); (iii) true repeat-reading
consistency would mean pressing every patch twice — that is the measurement-
averaging feature's territory, not a tolerance spinbox. Recommendation: GREY
checkbox+label+spinbox for a CR30 chart, tooltip saying the instrument reads
each patch once so there is no within-patch consistency to tolerance, and
pointing at Suppress-warnings-off as the check that does apply.

### 3 — fixable vs inert by nature
(a) fixable in the bridge: NOTHING on this list — the honoured ones already
work. (b) fixable only in the helper: none worth it (-T/-H/-F/-A configure
instrument hardware the CR30 does not have). (c) meaningless for this
instrument: -c, -B/-b, -H, -F, -T, -A, -n(trivially). The one REAL
"make it work" item is not on this panel at all: the remembered
address/port (Q-A, designed in 16_verify3, unimplemented) is what the -c
spinbox pretends to be for a CR30.
### 4 — greying design (his ruling: checkbox + LABEL + spinbox, CR30 only,
no regressions)
- Reuse `_chart_is_cr30` (tab_measure.py:5392 — docstring forbids a second
  open-coded read) and COPY THE EXISTING PATTERN: `_apply_cr30_pbp_lock`
  (:1394-1460) already does snapshot-value+tooltip → disable → explain →
  restore-on-chart-change, and is re-asserted from `set_ti1_path` (:3290)
  and both settings-load sites (:1284/:1294). A sibling
  `_apply_cr30_option_locks` called from the same three sites covers rows
  in BOTH modules (Guided owns only -T; Manual owns all seven) plus the
  instrument spin and the bidir row. `_ChartreadOption.row_widget` exists —
  disabling the row widget greys checkbox+label+value widget together,
  which is exactly his framing.
- DO NOT force-tick or untick — unlike the pbp lock, these are "not used",
  not "forced on": disable only, leave the checked state alone. Then
  `save_target_settings`/W8 and `_on_save_defaults` (:12090-12140) store
  the user's own value untouched (they read isChecked()/value() regardless
  of enabled state), and switching back to an i1Pro chart restores exactly
  what the user left — no `_pbp_user_value`-style shim needed. Verified:
  build_args (:815-823) also ignores enabled-state, so emission is
  unchanged = zero behavioural regression for other instruments by
  construction. One exception to consider: -F checked+non-default writes
  the false INSTRUMENT_FILTER keyword (table above) — the only row where
  emission itself does damage; recommend `_build_args` (or the option
  row) drop -F under external_values, called out to the owner as the one
  behaviour change.
- Tooltip on the disabled row = the pbp lock's exact voice ("…not yours to
  set right now… comes back exactly as you had it"), tr() with literals
  in-code (the i18n extractor cannot see tr(var) — same note as :1447).
  A section-level note is NOT needed if every disabled row explains
  itself; Guided's fixed-options info box (`_update_guided_fixed_info`)
  already covers what Guided does not offer.
- Grey: instrument spin, bidir row, -H, -F, -T, -A, -n. LEAVE ALIVE: -S,
  -N (Manual), resume/refine, -l, -L — they work (table). For -n the
  tooltip should say "a CR30 measurement has no spectral data to leave
  out" (greying something that is trivially satisfied needs its own one
  sentence or it looks broken).
### 5 — process
New user-facing strings = tooltips only; tooltips have not gone through §M
historically (the pbp lock's tooltip did not), but they DO go to the i18n
catalogues (extract + German). per_target_settings.md: no vocabulary change
(values still stored/loaded per target; only enabled-state changes) — a note
in the spec's Measure section that CR30 charts disable the inert rows is
worth adding WHEN the owner approves the design, per the confirmed-only rule.

## Still-open list from 16_verify3 — re-confirmed against 0055b857
- OPEN `_retries` not cleared on the click-re-arm path: on_patch_ready's
  asked_for branch (:299-313) emits patch_rearmed and falls to `_start_read`
  without `self._retries.pop(loc)`; only rearm() (:341) and success (:462)
  pop. F3's fix touches the same lines — do both together.
- OPEN bare `DeviceReader()` (tab_measure.py:7064): no remembered
  address/port; Q-A design unimplemented; ble.py:189-196 still picks
  `ok[0]` and still falls back to UNconfirmed ffe0 devices (`or cands`).
- OPEN ble.py:1-14 docstring still teaches "the device answers a poll, not
  a command-and-wait. This is the single reason every earlier attempt
  failed" — overstated per EXP-BLE-013 (unsolicited events exist; replies
  beat the first poll in both captured sessions).
- OPEN calibrate()'s docstring (measure_bridge.py:586-591) still claims the
  read-back seeds `_previous`; device.py:358-366/:456-462 gate `_previous`
  on enforce, and the read-back passes enforce=False. Docstring false.
- OPEN EXPERIMENTS.md has no EXP-BLE-012..017 entries (grep empty).
- OPEN no §M entries for the flash texts ("Your CR30 has been calibrated.",
  re-arm, dropped, discarded) — all tr() literals in tab_measure.
- OPEN ending-window n==1 text ungrammatical and off-spec: "You have read 1
  patch in this session." + "They are not in your measurement file yet —
  ChromIQ can write them now" (:6101-6106); spec pins the plural sentence
  verbatim (unified_measurement_management.md:259/:637).
- OPEN V-17: M-CR30-PATCH-GAVE-UP (measurement_messages.py:187-205) still
  omits click-the-patch-to-re-arm — the best recovery — and advises only
  Save-and-stop + resume.
- OPEN "using Argyll's default strip recognition" for a CR30
  (tab_measure.py:3813-3824: only is_spectroscan is special-cased).
- FIXED (in 0055b857): the traversal stall (next_unread + armed_for
  highlight guard), the padded-chart PARTIAL mislabel, the quiet-confirm
  second per patch (predicate stop, done= in ble.ask).
RANKING now that USB works and the stall is fixed: F3's first-press cost is
the biggest daily irritant (MAJOR, every navigation); then F5's greying
(MAJOR by owner ruling, visible honesty); F1/F2 window+message placement
(MAJOR UX, small code); F4's window loop (MAJOR when it happens, rare);
V-17 + gave-up wording (MINOR-plus: it advises the disruptive recovery);
Q-A remembered address (17 s/session, MINOR-plus); the docstring/EXPERIMENTS
/§M/plural items are hygiene (MINOR) but two of them are FALSE STATEMENTS in
code comments and must not survive into a release the next agent trusts.


## F3 probe — mechanism PROVEN on the real bridge
scratchpad/proof_f3_first_press_eaten.py, real Cr30MeasureBridge, reader with
DeviceReader's lock semantics: arm A24 -> note_goto/on_patch_ready A20 (W_A20
queues behind the lock) -> press 1 -> `dropped = [('A24','stale_loc')]`, no
value sent -> press 2 -> exactly one value sent. Matches the owner's 20:02:28
log line for line.

## ON-SCREEN (F1 + F2) — done, real app, real styling
Driver: scratchpad/drive_f1f2b.py. Sandboxed exactly as tests/conftest
322c3d20 does (QSettings->ini, CHROMIQ_PRESETS_DIR, custom_output_path,
trash all redirected into the scratchpad sandbox); the project is a COPY of
CR30-Test staged into the sandbox; the real ~/ChromIQ, plist and presets
were never touched (backups taken to scratchpad/backup anyway; nothing to
restore). NOTE for the next round: plain `screencapture -x` returned bare
wallpaper — the shell lacks the screen-recording permission — so the shots
are Qt window grabs composited with the modeless dialog at its true
relative position (red rings mark the dialog and the status label).
Because they are grabs, the macOS TITLE BAR (where the traffic lights live)
is not in the picture; the X-close behaviour is proven by state, below.
- ~/Desktop/cr30_verify4_01_window_and_flash.png: the M-CR30-HOW-TO-MEASURE
  window CENTRED OVER THE CHART PREVIEW (covering the patches its own text
  says to watch), one button, "Start measuring", no Cancel — while the flash
  "Your CR30 has been calibrated." renders at the FAR BOTTOM-LEFT (label top
  y=974 in a 1000-px window, below the log whose bottom is y=962) — and at
  this window height the text is partly CLIPPED by the bottom edge.
- ~/Desktop/cr30_verify4_02_after_x_close.png: after dlg.close() (what the
  red traffic light does) the dialog is gone and NOTHING else changed
  (start/stop states identical, no signal fired, nothing cancelled) — the
  owner's report verified: closing does not cancel. Console: "dialog visible
  after X-close: False | start: True stop: False".
- Bonus, on screen in both shots: the log's "Chart instrument: CR30 → using
  Argyll's default strip recognition." — the still-open wording defect,
  live.
- The log-hidden variant of the flash position was NOT captured (the
  driver's hide-log toggle didn't take; the layout code at :1846-1879 is
  the evidence for that state instead).

## F0 — corrected CALIBRATION.md wording (drop-in replacement for the
paragraph at "The device does not beep…", CALIBRATION.md:292-295)
> ⚠ **CORRECTED 2026-08-29 — the "no beep" claim was an inference, and it
> was wrong.** This section previously stated: *"The device does not beep
> for a host trigger with the cap on."* No capture supports that:
> EXP-BLE-015 recorded frames, spectra and push timestamps but has no field
> for sound, and the probe told the operator to "listen for a beep" without
> ever recording the answer (`tools/probe_ble_trigger_calibrates.py` — its
> pre-written success verdict even carried "the missing beep" as a
> premise). The sentence restated the owner's earlier impression ("the
> Calibrate button does nothing"), which he has since corrected: **the
> device beeps for a host-triggered calibration on BOTH transports.** What
> differed was LATENCY — over BLE the full trigger-to-confirmation cycle
> measured ~1.85 s, long enough to read as nothing happening; over USB it
> is near-instant. The button was never dead and never silent; it was slow,
> and the app said nothing during the wait. ERRORS.md's lesson — a beep is
> not an acknowledgement — now cuts both ways: the ABSENCE of a beep must
> not be recorded unless the absence itself was observed and written down.
(Leave the EXP-BLE-015 JSON capture untouched — captures are immutable; its
verdict string's "missing beep" phrase is annotated by the correction above.)

CODE COMMENT (tab_measure.py:7016-7025) — replacement wording for the
implementer (ChromIQ is read-only for me):
> SAY IT HAPPENED, because the instrument's own confirmation can lag.
> Over Bluetooth the full calibrate-and-confirm cycle measured ~1.85 s on
> the owner's unit, and with nothing on screen meanwhile the button read as
> dead (his first report). The beep does come — on both transports (owner,
> 2026-08-29) — but ChromIQ must not leave a silent gap between the click
> and the device's answer, and it cannot check the RESULT either way (the
> instrument reports the same value whatever is under the cap). So ChromIQ
> confirms in its own voice, with the sound it already uses for "that
> worked".

## STATUS: COMPLETE — ranked summary in the final message.
