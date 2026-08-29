# 23_live — [CR30-LIVE] challenge after the owner's real-use session
Branch feature/cr30-instrument-159, head 17bda950. Round complete 2026-08-30.
ChromIQ untouched (report file only). Verdict at the end: one BLOCKER (L1
handling), fix is small and contained.

## L1 — THE MAGNET RECALIBRATION. Mechanism verified end to end; the current
## handling is wrong in four distinct ways, and one of them is exactly what
## cost the owner his session.

### The verified chain
1. A gated press makes the device take a WHITE CALIBRATION against whatever
   is under the aperture — corpus CALIBRATION.md:5-11 (VERIFIED, the research
   unit was corrupted this way); EXP-BLE-015 artefact: after a gated trigger
   the stored slot holds the tile constant (first band 70.39 = TILE_SIGNATURE
   byte-for-byte). The MacBook's lid magnets under a sheet of paper are a
   textbook gated press.
2. Detection fires AT that press: `Measurement.check_usable`
   (workflow/cr30/measurement.py:181-190) — USB via `gate_flag` (button
   header offset 24), BLE via the tile signature (OWNER'S UNIT ONLY).
   MeasurementError(MAGNET_MESSAGE) raised.
3. The worker flattens it to exc_type "MeasurementError"
   (measure_bridge.py:163-171) — indistinguishable from "lifted too early" or
   a bit-identical repeat. `_on_read_failed` (measure_bridge.py:430) routes it
   to the ordinary retry branch: `_retries[loc] += 1` (:475),
   `read_failed.emit` (:484), and IMMEDIATELY `self._start_read(loc)` (:486).
4. The tab handler `_on_cr30_read_failed` (ui/tabs/tab_measure.py:7363-7369)
   appends the text to the LOG PANEL and flashes the status bar — that is the
   owner's "very small message on the left" — and its wrapper ENDS WITH
   "Press the button on the instrument again."

PROVEN by executing probe (scratchpad/probes/probe_magnet_rearm.py, real
Cr30MeasureBridge, stub reader): two gated refusals → session never stops, no
gave-up, and the third reading — taken under the now-corrupt reference — is
sent to the helper and written to the .ti3. Output:
  reader called: 3 | signals: [(read_failed, D7), (read_failed, D7)]
  value sent: {'cmd':'value','xyz':'50.0 …'} | session stopped? False
On screen (both themes): cr30_live_04_magnet_refusal_mainwindow_{dark,light}
— the full MAGNET_MESSAGE renders as small text in a 548×154 px log box
inside a 1680×1000 window, tail line "…Press the button on the instrument
again." The owner's account is reproduced to the pixel.

### The four faults
- **F-L1a (the blocker): the session carries on under a corrupt reference.**
  The guard's own text says the reference "may ALREADY have been overwritten",
  then the code re-arms the patch and accepts the next reading. Every reading
  after that is scaled by tile/surface; in the owner's case (paper over a
  MacBook, brighter than the tile) the error direction is DARK, which the
  one-sided bounds guard (measurement.py:79-96) can NEVER catch — its own
  comment says so.
- **F-L1b: the recovery advice is stale and self-defeating.** MAGNET_MESSAGE
  (measurement.py:40-44) says "seat the cap correctly … and press the device
  button" — the OLD side-effect calibration method. Done mid-session, that
  press delivers the gated tile constant to the armed patch → refused with
  the same message again, +1 toward give-up(5). Since 439a8b5c ChromIQ can
  send the maker's own calibration command itself; the message predates that
  and was never updated.
- **F-L1c: no distinct exception type.** DeviceLost got its own class and its
  own signal; the magnet — the worst fault the instrument has — is a plain
  MeasurementError, so the tab cannot treat it specially without
  string-matching (the trap the exc_type argument exists to avoid,
  measure_bridge.py:139-144).
- **F-L1d: on any OTHER unit over Bluetooth there is no detection at all.**
  BLE has no gate flag (device.py:479), TILE_SIGNATURE is one unit's constant
  (measurement.py:150-160 says so itself). First gated press on a foreign
  unit over BLE: the tile constant is ACCEPTED as the patch colour AND the
  reference is corrupted, both silently. USB catches it on every unit.

### Answers to the four questions
**1. Is a modal right, and is it enough?** A modal is right — this is the one
CR30 fault that poisons everything after it, and the log box demonstrably
does not reach the user (measured tonight). But a modal that only says "that
reading was refused" is half the message and the half he already got. It must
say: (a) the reading was refused AND the instrument has probably just
recalibrated itself against the surface it was sitting on; (b) everything
measured BEFORE this moment is safe and stays on disk; (c) nothing more
should be measured until the white calibration is taken again. And it must
OFFER, not instruct:
  [Recalibrate now]  — ChromIQ CAN do this: the maker's-way command
      (reader.calibrate(), the same worker `_calibrate_and_confirm` already
      uses) with the white-tile instruction and pictogram. Feasible because
      the failed read leaves no read in flight, so the reader lock is free —
      PROVIDED the auto-re-arm at measure_bridge.py:486 is suppressed for
      this exception (today a new 180 s wait holds the lock within
      milliseconds). After it, re-arm the patch (bridge.rearm()) and carry on.
  [Stop the measurement]  — the ordinary END_FAILURE window; nothing
      destroyed (project rule kept: readings stay in the .ti3).
  No third "continue anyway" button: continuing without recalibrating is
  never what a user wants once the sentence above is understood, and the
  END window's "Keep measuring" already exists for the stubborn case — but
  if it is kept it must carry the warning explicitly.
**2. Can ChromIQ tell WHICH readings are suspect?** In the .ti3: no — spot
rows carry no timestamps, and the corruption survives sessions until a real
white cal. In the live session: yes — the bridge answers prompts serially,
so "every loc answered after the gated refusal" is knowable. But the DESIGN
makes the question moot: detection fires at the corrupting press, BEFORE any
further reading is accepted (proven above — the refusal path sends nothing).
A blocking modal at that moment leaves the suspect set EMPTY: everything
already in the .ti3 predates the corruption and is sound; nothing after it
exists until the user has recalibrated or stopped. That is the whole win,
and it costs no marking/discarding machinery and destroys nothing.
(Only the F-L1d case — foreign unit, BLE — escapes this, because there the
first gated reading is not detected at all. See the probe below.)
**3. Can it be PREVENTED? No — plainly.** The only magnet observable is
offset 24 of the BUTTON-press header, i.e. the frame announcing the press
that has already calibrated. Host-triggered frames read 0x00 with a magnet
present (0/20+, MEASUREMENT.md), a probe trigger would itself calibrate
(TRIGGER_UNSAFE, ble.py:60-74), and a passively seated magnet emits nothing
(EXP-BLE-014; CALIBRATION.md: "the magnet does not reach the wire"). There is
no pre-read magnet query anywhere in the corpus. Detection at the press IS
the earliest possible moment; what can be prevented is the CONSEQUENCE
lasting past that moment — the corruption is fully repairable by one
maker's-way white calibration (device.py calibrate docstring: "Doing it
again correctly is the whole restore procedure").
**4. Warn up front?** Yes, one line, in the how-to-measure window: measuring
on a laptop, a metal desk, or anything magnetic under the sheet makes the
instrument recalibrate itself and silently ruin every later reading. This is
now a MEASURED ordinary-use failure (the owner's desk tonight), which is the
bar 21_design6 D3 set and the phone-line did not meet. The §M body of
M-CR30-HOW-TO-MEASURE takes the line (revision of a PROPOSED message =
normal path). The watchdog-banner reasoning is unaffected.
**Bonus, HYPOTHESIS worth one 2-minute owner probe:** if the read-back that
`DeviceReader.calibrate` already takes after a white cal
(measure_bridge.py:672-686) returns the same canned constant a gated press
stores, ChromIQ can LEARN the per-unit signature at every calibration and
close F-L1d for Bluetooth units. Probe: white cal via ChromIQ, read stored,
compare to a gated reading's bytes. If they differ, F-L1d stands and the
answer for BLE foreign units is honestly "USB is the protected transport".

## L2 — "Keep measuring" did not reconnect on its own. Established.
Path: _on_cr30_device_lost (tab_measure.py:7405-7438) → Keep measuring →
bridge.rearm() → _start_read → DeviceReader.__call__ finds _dev None (the
handle is dropped on DeviceLost, measure_bridge.py:617-627) → _open() →
"auto": USB fails fast → BleTransport.open → discover() scan of up to 12 s
(ble.py:186-198). NEW DEVICE FACT from his session (single observation, so
mechanism HYPOTHESIS, instruction safe either way): after a link drop the
CR30 does not re-advertise until its button is pressed once — the corpus only
documents "stops advertising while HELD" (TRANSPORT_BLE.md:27-31). His press
landed inside the scan window, the connect succeeded, and the next press
measured — exactly his account ("one press … then the B indicator … the next
press really took a measurement").
What the app says today (verified on screen, cr30_live_06_carrying_on_*):
"Carrying on: reconnect the instrument and read the highlighted patch again."
(tab_measure.py:7434-7436) — no word about the button. And the GONE window
the §M body would explain it in is unapproved, so the explanation sits in the
log; the window he actually saw is the generic "Keep what you have measured
so far?" (shot cr30_live_05) — instrument never mentioned. If his press had
come 13 s later the scan would have failed and dumped him into a SECOND gone
window: a modal loop.
**Design consequence for the patient-reconnect backlog item (19_design5 D2):
upgraded, not replaced.** A quiet single retry cannot work here — the device
will not be found until the user acts. The wait must (a) SAY "press the
instrument's button once to wake it — then press again on the patch", and
(b) keep RE-SCANNING (each scan is the window in which the wake can be
caught) with the visible waiting line, rather than one 12 s attempt per trip
through a modal. The wake sentence also belongs in M-CR30-INSTRUMENT-GONE's
Bluetooth bullet when its wording goes for approval — and that message still
carries the known-bad "start the measurement again with Refine/resume"
recovery (measurement_messages.py:220-222).

## L3 — Bluetooth calibration IS slower, and most of the gap is OURS.
Probed with the REAL BleTransport polling code and a stub client tuned to the
measured device latencies (reply 0.31 s, acquisition budget 1.2 s):
  CR30.calibrate(white) over BLE          2.16 s   (device's share: 0.31 s)
  same ask with an early-stop done=       1.10 s   (saves 1.06 s)
  DeviceReader.calibrate white, e2e       3.26 s
  black + read_zero, e2e                  5.42 s
  one stored read, device idle            1.10 s
USB floor: reset_input+send+receive returns on arrival (~0.25 s, no poll
cadence, no drain) + a transact read-back ≈ 0.6-1 s total — "near instant",
as he says.
Where the BLE overhead lives, per ask: `_drain` 0.4 s (ble.py:341-350) + the
quiet-3 confirmation ≈ 1.05 s when no `done=` is given. **The early-stop rule
that fixed the patch read (done=_parse_reply, device.py:441) applies here and
is simply missing in three places:** the calibration ask (device.py:229,
polls=6, no done — a complete valid 10-byte echo frame is the honest
predicate), identify (device.py:137) and trigger_unsafe (device.py:175) —
the last is the worst: over BLE the trigger's ack is classified as an EVENT
by _on_notify (cmd 0x01 → _events, never _buf), so the reply buffer stays
empty, the quiet-stop can never fire, and ALL polls always run: 2.15 s of
pure waiting inside every read_zero. Fixes are one predicate each; ~2 s off
a white cal, ~4 s off white+black. The remaining gap (one drain per ask) is
the price of offset safety and is defensible.

## L4 — will ChromIQ work with a DIFFERENT CR30? Answer below, and two of the
## briefed claims needed correcting.
Verified:
- USB: `candidates()` filters only VID 0x1A86 / PID 0x7523
  (discovery.py:21-22,34-35,47); `open_usb` takes `found[0].device`
  (device.py:111). Nothing unit-specific. **CORRECTION to my brief: "identity
  is then confirmed over the protocol" is FALSE on the app path** — no call to
  identify() exists anywhere in the measure/calibrate flow (grep: zero call
  sites; `Session.identify` is real but unreached). The first CH34x port is
  opened and USED: calibration frames are written to whatever it is, and with
  transport "auto" a successful USB OPEN also shadows a real CR30 on
  Bluetooth (the BLE fallback fires only when USB open RAISES,
  measure_bridge.py:570-577). Any CH340 Arduino/adapter — the most common
  hobby serial chip there is — triggers this.
- BLE: discover() shortlists the generic FFE0 service and confirms the model
  by its spectral axis 400/10/31 (ble.py:84-136, EXPECTED_AXIS) — a property
  of the MODEL, works on any unit; the unit-specific advertised name is used
  only as an optional hint, never a test (ble.py:76-79, device.py:80-92).
  BUT ble.py:189: `ok = [c for c in cands if c["confirmed"]] or cands` —
  when NOTHING confirms, it falls back to UNCONFIRMED candidates (any HM-10
  gadget), and ok[0] picks arbitrarily when several match. Two CR30s in
  range: first confirmed wins, no user say (as briefed).
- TILE_SIGNATURE: used only by looks_like_calibration_tile; on a foreign
  unit it silently contributes nothing (no false positives at tol 0.05).
  Consequence is F-L1d above, not a blocker to measuring.
- The app pins nothing: `DeviceReader()` bare (tab_measure.py:7312) — no
  port, no address, no name.

## Backlog status at 17bda950 (each grep/read-confirmed this round)
FIXED since 22_beta: BLOCKER 1 (bridge calibrate(black=) + six EXECUTING
tests, tests/test_cr30_calibration_actually_runs.py); MAJOR 1 (read_zero now
triggers and waits, measure_bridge.py:702-737); double beep (single
confirmation after the black step); "arm's length" → "about a metre".
STILL OPEN, unchanged ranking: how-to window OK/"Stop the measurement"/
close-with-session (its one button today is "Start measuring" — verified on
screen); patient reconnect + transport-changed announcement (L2 upgrades its
design); no-reading watchdog banner (phone fact still only a log NOTE at
session start, tab_measure.py:5803); M-CR30-INSTRUMENT-GONE Refine/resume
advice (measurement_messages.py:220-222); V-17; `_retries` not popped on the
click-re-arm path (on_patch_ready's re-arm falls to _start_read at
measure_bridge.py:317 with no pop — rearm() at :348 does pop); the false
`_previous` docstring (measure_bridge.py:640-644 — read_measurement(
enforce=False) never sets _previous, device.py:461-466); the false
wait-by-CHANGE docstring (device.py:251-253 vs the event wait at :311-319);
ble.py poll doctrine overstatement (ble.py:6-8 — events arrive unsolicited);
"using Argyll's default strip recognition" logged for a CR30
(tab_measure.py:3885); the "1 patch … They are not" wording; no §M entries
for the flash texts.
NEW MINORS this round: the refusal wrapper produces ".." (message ends "."
+ wrapper adds ". Press …" — visible in cr30_live_04 shots); MAGNET_MESSAGE
stale advice (F-L1b); comment in _do_black_calibration says the white step's
sound played "a moment earlier" while it actually plays after (cosmetic).

## ON-SCREEN — done, real app, real styling, BOTH themes, stub device only
Driver: scratchpad/onscreen/drive_live23.py. Sandboxed QSettings→ini, presets
dir, output path, trash no-op; PROJECT COPIES of CR30-Test (partial, 4 sets,
fresh from disk), CR30-Verify2 (complete, 20 sets), CR30-NoTiff (built to
expose: all TIFFs deleted), ChromIQ-Test-Chart (non-CR30 control); ~/ChromIQ
untouched (backups at scratchpad/backup/round23/). DeviceReader._open patched
to a stub device — NO byte reached the real CR30; every window, worker,
thread, signal and log path above the transport was the real code.
Shots in ~/Desktop/CR30-test-shots/ (looked at):
- cr30_live_01_white_window_{dark,light}(+fullscreen): the real white window,
  pictogram, checkbox unticked by default; both themes legible.
- cr30_live_02_black_window_{dark,light}: pair pictogram, current step
  marked; "about a metre" text confirmed on screen.
- cr30_live_03_howto_window_*: shown after a SUCCESSFUL calibration
  (first time this flow completes on screen since the TypeError round);
  single button "Start measuring". Zero-check NOTE in the log: "came back at
  0.000 % … not the same as verified."
- cr30_live_04_magnet_refusal_mainwindow_{dark,light}_fullscreen: the L1
  evidence — the owner's view, tiny log text + "Press the button … again."
- cr30_live_05/06: the GONE flow: generic Keep-what-you-have window, then
  "Carrying on: reconnect the instrument…" with no wake instruction.
- cr30_live_07/08/09: completed chart loads; no-TIFF project loads without
  crash (chart_is_cr30 True, preview empty); non-CR30 control: all four dead
  options re-enabled, chart_is_cr30 False.
Calibration order at the device: ['white', 'black', 'trigger'] — trigger is
read_zero's, matching the designed sequence.

## VERDICT — ranked
**BLOCKER (for shipping this beta to the person who just hit it):**
1. F-L1a+b+c as one item: a magnet-gated refusal must STOP arming, raise a
   window, and offer ChromIQ's own recalibration; the stale MAGNET_MESSAGE
   advice must go. Scope: one exception subclass, one bridge signal, one tab
   handler + §M-PROPOSED window text, suppression of the auto-re-arm for that
   type. Everything else in the incident (log-only visibility, contradictory
   advice, silent corrupt continuation) falls out of it. Rationale: it
   happened in ordinary use, to the only user, and it silently invalidates
   whole sessions; the one-sided bounds guard cannot catch the common
   direction.
**MAJOR:**
2. L2: the keep-measuring path must say "press the instrument's button once
   to wake it", and the reconnect must re-scan patiently instead of one 12 s
   attempt per modal trip (upgraded 19_design5 D2 design above).
3. L4-USB: first-CH34x-open with no protocol confirmation, shadowing BLE on
   "auto" — one identify() after open (it exists, unused) closes it.
4. L4-BLE: the `or cands` fallback to UNCONFIRMED candidates at ble.py:189.
**MINOR:** the three missing done= predicates (L3, ~2-4 s per calibration
over BLE); F-L1d learn-the-tile probe (2 min of owner time, closes the BLE
foreign-unit hole or proves it unclosable); the ".." grammar; the how-to
laptop/metal warning line (§M revision, rides with the L1 batch); the
standing hygiene list (false docstrings etc., unchanged).
**Can this ship as a beta?** Not to the owner as-is: item 1 is his exact
incident and the current behaviour actively advises continuing. With item 1
done (it is small), YES — items 2-4 and every minor can ship open, as they
did in every previous beta, with the L2 wake sentence in the release notes
until the reconnect work lands.
