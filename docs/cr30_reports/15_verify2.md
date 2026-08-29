# 15_verify2 — [CR30-VERIFY-2] check of commit 1658f022 and the two before it

## Status: COMPLETE. The live press-proof ran once; its meaning waits on one
word from the owner (did he press during 18:13:30-18:15:45?). Everything else
is final.
Desk analysis, stub proofs, targeted tests and the on-screen run are done; the
findings below are final. Ranked summary at the end.

## FINDING 1 — BLOCKER, PROVEN: over real BLE no press event can ever arrive during the wait

- bleak delivers every notification by `loop.call_soon_threadsafe(...)`
  (.venv/.../bleak/backends/corebluetooth/PeripheralDelegate.py:145-147 via
  bleak/backends/_utils.py:14-24). Such a callback runs ONLY while the asyncio
  loop is running.
- `BleTransport` runs its loop only inside `_run()` (ble.py:174-177), i.e. during
  `open()`/`ask()`. The new wait loop `device.py:272-292` is a synchronous
  `take_event()` + `time.sleep()` spin that never calls `_run` — so `_on_notify`
  never executes during the wait, `_events` stays empty, and every patch times
  out after 180 s ("no button press within 180 s") no matter how often the
  operator presses.
- Proof stub run: scratchpad/proof_loop_stall.py — callback scheduled from a
  foreign thread onto a non-running loop is NOT seen by the condensed wait loop
  (0 events in 2 s), fires only at the next `run_until_complete` (1 event).
- 14_protocol.md's redesign section SAID this explicitly ("The wait ...
  `_run(wait_for_event(timeout))` ... The loop must be RUNNING for
  bleak/CoreBluetooth to deliver callbacks, which the wait guarantees") — the
  implementation deviated from its own analysis and the deviation is fatal.
- The tests never see it: tests/test_cr30_ble_can_read_a_patch.py:53-81 fakes
  the transport and feeds `_events` directly, bypassing delivery.
- Corollary: `drop_events()` at arm time (device.py:267) is also unsound as
  implemented — an event already delivered by CoreBluetooth but still queued in
  the loop's ready-queue is invisible to `drop_events` and will surface at the
  NEXT `_run` (the read after a future event), i.e. exactly the late
  mis-attribution the drop exists to prevent. The fix must flush the loop
  (e.g. `_run(asyncio.sleep(0))`) before clearing, or better: do the whole
  wait inside the loop as 14_protocol.md designed.

## FINDING 2 — MAJOR (spec deviation): pre-arm presses are discarded with log.debug, not a user-visible line
14_protocol.md's redesign: "Events from before the current patch was armed are
discarded WITH a user-visible line — the honest version of today's silent
stale_loc swallow." device.py:267-270 logs at DEBUG only; nothing reaches the
UI log or status bar. A fast operator's early press vanishes exactly as before.

## FINDING 3 — MINOR: click-to-retry a gave-up patch inherits its exhausted retry budget
`rearm()` pops `_retries` (measure_bridge.py:297); the click path
(`on_patch_ready`, incl. the new asked_for re-arm) does not. A patch at
read_gave_up holds count 6; after the user fixes the cause and clicks it, ONE
new failure trips `tries=7 > MAX_READ_RETRIES` (measure_bridge.py:391-397) and
it gives up instantly instead of allowing 5 fresh tries. Non-fatal (each click
buys one try; success pops the counter) but inconsistent with rearm().

## FINDING 4 — MINOR: `_last_seen` is dead state
Written at device.py:289, never read anywhere (grep over workflow/ui/tests:
only writes and test scaffolding). The change-detection it fed is gone.

## Worry (a) — demux width: SETTLED with capture evidence, one residual
- EXP-BLE-009-att.json: MTU_RSP = 0xf4 = 244; notify value sizes {10:2, 241:1,
  169:1} — a 410-byte double reply fragments at 241, a 200-byte reply fits one
  notification; every observed event (013/014/015) is a lone 10-byte
  notification arriving in silence, which is the only time the new code waits.
- Residual (HYPOTHESIS, low): the BLE module is a UART bridge; two rapid
  presses could coalesce into one 20-byte notification, which fails the
  len==10 test and lands in `_buf` — both presses invisible. Also a stacked
  multi-reply stream whose tail fragment is exactly 10 bytes starting bb 01
  with a valid checksum would be mis-taken as an event (float-data odds ~2^-24,
  ignorable).

## Worry (d)/(d2) — calibration's own event, and no trigger on connect: OK
- Only calibrate_white -> trigger_unsafe sends bb 01 00 (grep). identify() and
  discovery verify use READ_MEASUREMENT only (ble.py:119, device.py:113).
- Ordering: calibrate runs to completion (tab_measure.py:6985 wait loop) with
  the reader lock held before any patch read; the trigger's announcement (and
  its byte-identical solicited reply — the demux CANNOT tell them apart, both
  land in `_events`) is delivered during calibrate's own ask()/read-back loop
  runs, and the first patch's drop_events (device.py:267) clears them. A press
  during the calibration window is likewise dropped at first arm. Correct BY
  DESIGN — but only once Finding 1 is fixed WITH a loop flush before
  drop_events; today an event still queued in loop._ready survives the drop.
- Side effect: with the demux, trigger_unsafe's ask() gets nothing in `_buf`
  (its 10-byte reply is routed to `_events`), so it always burns its full
  4-poll cycle (~1.8 s) before returning. Harmless latency, worth a comment.

## Worry (e) — USB isolation: CONFIRMED untouched
take_event/drop_events referenced only in device.py's BLE branch (after the
USB early-return at device.py:214-241). SerialTransport never sees them; the
"cannot report button presses" MeasurementError is unreachable on USB.

## Worry (c) — sleep(0.4): keep it, and it is NOT sufficient (HYPOTHESIS)
The retry in _read_when_ready only covers the ZERO-FILLED busy signature. If
the device announces the press BEFORE the stored value is rewritten and the
read wins the race, the reply is the complete, valid, PREVIOUS reading —
zero_run passes, _read_when_ready returns it, and check_usable then refuses it
as bit-identical (device.py:290) -> the press is lost and the user is told to
press again. The 0.4 s sleep is the only mitigation. Cleaner: run check_usable
INSIDE the retry loop (an event proves a press, so bit-identical = "not stored
yet"; real repeatability is 0.056%-class, never bit-identical). Event->storage
latency is unmeasured — a 30 s probe (press, read immediately, compare) would
settle it.

## Worry (h) — the 0.9927 paper ratio: NOT handling, and the owner's own capture already says so
EXP-BLE-017-repeatability.json (2026-08-29 15:54 UTC): untouched re-reads
spread 0.24 %, lift-and-reseat re-reads spread 0.22 % — neither reaches the
0.73 % shift observed across the two calibrations. Its own verdict: "NOT
EXPLAINED BY HANDLING … do not measure a chart for real until it is
understood." The implementer's "probably handling" is REFUTED by evidence
already on disk. The owner should do the verified restore (cap correctly
seated, white face, button press) and re-check the paper ratio before any
real chart.

## FINDING 5 — MINOR (process): the research-repo corrections owed by 14_protocol.md are not done
No committed doc mentions EXP-BLE-013/-014/-015/-017 (grep over *.md);
captures/raw/ is gitignored (serial number), so the hardware facts this whole
rework rests on exist only in ignored local JSON and a ChromIQ commit message.
TRANSPORT_BLE.md still carries the wrong "hello/axis announcement" label and
the overstated poll doctrine that ble.py's own header comment (ble.py:5-8)
still repeats.

## FINDING 6 — MINOR: ble.py's module docstring still teaches the disproven doctrine
ble.py:6-8: "the host must write a single 0x01 byte to POLL; the device
answers a poll, not a command-and-wait." 14_protocol.md F-1 doctrine
correction: replies preceded the first poll in both of the owner's sessions,
and unsolicited pushes exist. The file that implements the event demux opens
by asserting the model the demux disproves.

## §M / catalogue status of the two new strings
- Both are translated in all catalogues (de.json:2343, :4004 checked).
- Neither "Patch {loc} was already measured…" nor "Your CR30 has been
  calibrated." has a §M entry; they are inline tr() in tab_measure.py
  (:7129, :7030), consistent with the OTHER CR30 flash/log lines
  (_on_cr30_dropped, _on_cr30_read_failed) which are also inline and
  uncatalogued. test_message_catalogue.py governs windows rendering from the
  catalogue, not status flashes — so no test fails, but by the letter of
  CLAUDE.md ("new user-facing message text … goes to §M-PROPOSED first")
  these two (and the earlier flash lines) are outside the process. Flag for
  the owner rather than a defect: the convention for non-window text is
  genuinely unsettled.

## 13_verify residue — confirmed still open
- V-8 (_on_chart_measured drops patches silently), V-17 (gave-up message
  omits click-to-retry, which H7 just made the BEST recovery — and Finding 3
  hobbles it), V-18 (cancelled/failed calibration leaves reader+transport
  open until the next Start; tab_measure.py:6941 is the only cleanup),
  V-19 (pace panel still says "Scan each strip with a slow, steady motion",
  tab_measure.py:1753), V-20 ("Calibrate now" still the default button,
  tab_measure.py:6955), V-11b (`self._sound.disarm()` unguarded,
  tab_measure.py:5586), V-24 (overlay legibility), B-5/S29(3) (bridge.is_reading).
- V-2/V-3 (calibrate signature) FIXED — no timeout/cancel params, 12 s bounded
  retry (measure_bridge.py:532-581). V-14 done per brief. V-15: exit-strategy
  doc was extended in 8045da7e.

## FINDING 7 — MAJOR, PROVEN: on a COMPLETE chart the H7 re-arm is unreachable
`on_patch_ready` returns on `all_done` (measure_bridge.py:240-241) BEFORE the
asked_for/read re-arm branch. The helper sets all_done on EVERY spot prompt
once no unread patch remains (chromiq_chartread.c:2802-2810), so on a fully
read chart — exactly the chart with one ΔE-73 patch the user wants to repair —
clicking a patch lands the goto, arms nothing, and says nothing: the same
dead silence H7 was fixed for. Re-reading patches of a finished measurement is
an intended workflow (measure_manager.py:1306-1310 exists precisely for it).
Proof stub scratchpad/proof_all_done_gate.py:
  chart incomplete: rearmed=['A17'] read_started=True
  chart COMPLETE:   rearmed=[]     read_started=False

## FINDING 8 — MINOR: the spot-mode status flash gives CR30 users keyboard advice, and may clobber the re-arm flash
`_on_spot_ready` (tab_measure.py:7338-7347) flashes "Press Enter to read, f/b
to navigate" — advice for the keyboard spot mode; under -xx a CR30 user reads
with the instrument's button. The helper prints the "Ready to read patch" line
right AFTER its JSON spot_ready (chromiq_chartread.c:2810 then :2813), so when
the regex path also fires, the 10 s spot flash lands after the 8 s
patch_rearmed flash and may overwrite it in the status bar (HYPOTHESIS until
the on-screen run answers which flash survives — checking).

## ON-SCREEN RESULTS (real app, real settings, real CR30 over BLE; project COPY ~/ChromIQ/CR30-Verify2 of CR30-Test)
Screenshots on ~/Desktop: cr30_verify2_01..09.
- M-CR30-CALIBRATE window renders with CALIBRATE NOW / CANCEL (03). Pressing
  it calibrated over REAL BLE and the session went live; the confirmation
  "Your CR30 has been calibrated." shows in the status area (06). The app's
  PATCH_OK confirmation sound could NOT be verified: this project has "Play
  sounds during measurement" off, so whether the calibration sound respects
  that switch is untested.
- OWNER OBSERVATION during the run (Basti, live): when "Calibrate now" fired
  with the CAP OFF and the device SITTING ON A PATCH, the CR30 BEEPED. That
  refines EXP-BLE-015 (silent trigger — measured CAP-ON only): the host
  trigger is silent when gated, audible when it takes a real measurement.
  tab_measure.py:7018-7024's comment ("stays silent when the host asks") and
  the M-CR30-CALIBRATE flow's premise overgeneralise the cap-on result. Not a
  defect — the confirmation is still needed for the capped case — but the
  research docs should record the distinction.
- H7 on screen: clicking measured patch A17 during the session produced the
  log line AND status flash "Patch A17 was already measured. Read it again
  now to replace that reading — press the button on the instrument." with
  A17 highlighted (08). Finding 8's flash-clobber HYPOTHESIS is REFUTED on
  screen — the re-arm flash survives.
- Split-patch overlay still paints: rows A1-A20 draw expected/measured
  diagonal splits (A19's near-white mispair visible), unread patches solid
  (07, 08 + zoom).
- The copied project's .ti3 kept its 20 sets after start/stop cycles; archives
  landed in runs/run1/old/. Original CR30-Test untouched.
- Stop with no new readings prints M-END-EMPTY "Nothing was measured, so
  nothing was saved." and then "[ERROR] Measurement failed — see output
  above." (tab_measure.py:9653-9668: helper exits non-zero, ti3 not fresh →
  failed). A deliberate Stop reported as an ERROR is pre-existing, not this
  commit's, but a CR30 resume session hits it every time (MINOR).
- Driver notes for the next round: the run-combo raises "This chart already
  has a measurement" (OK/Cancel) BEFORE Start; QMessageBox windowTitle() is
  empty on macOS (identify the calibration box by its buttons); the tab log
  is CLEARED at session start; the how-to window's only button is
  "Start measuring" and it stays open across Stop.

## Hardware press-proof (Finding 1) — IN PROGRESS
Observe-mode session running; the owner was asked live to press the button on
an armed patch. Expectation per Finding 1: nothing recorded, no reaction.

## Remaining small items
- trigger_unsafe()'s ask() now always burns its full poll cycle (~1.8 s): the
  demux routes its 10-byte reply to `_events`, so `_buf` never satisfies the
  quiet-break (ble.py:285-297). Latency only; deserves a comment or polls=1.
- `_events` maxlen=64 and single-thread access are fine; deque ops safe.
- `_read_when_ready`'s blanket `except Exception -> DeviceLost`
  (device.py:315-323) also converts programming errors (struct.error,
  TypeError) into "the Bluetooth link dropped" with no traceback logged
  anywhere (the worker only forwards str(e)). Add a log.debug(exc_info) before
  raising. MINOR.
- The failed-goto residue: a goto whose target the helper cannot find re-offers
  the CURRENT patch; loc != _nav_target keeps the bridge navigating and every
  reading drops as NAVIGATING until the user clicks something else
  (measure_bridge.py:234-237, chromiq_chartread.c:2785-2797). Unreachable from
  the preview (valid locs only) — HYPOTHESIS, low.
- A goto while a read is in flight leaves the OLD worker holding the reader
  lock until its 180 s timeout or the next press (which it consumes and drops
  as stale_loc, with a message). One press lost, told about; pre-existing
  design family (F-5), not a regression.
- No remembered unit: the tab always builds `DeviceReader()` bare
  (tab_measure.py:7063) although reader/device/transport all plumb `address=`.
  Every session runs full discovery (~15-30 s before the calibration window's
  work begins), and `ok = [confirmed] or cands` (ble.py:189) will connect to an
  UNCONFIRMED ffe0 device when protocol confirmation failed — a foreign
  BLE-UART device would then surface as DeviceLost on the first read. MINOR.

## Press-proof run 1 (18:13:16-18:15:48) — awaiting the owner's word
Session live on A21, observe window 150 s. chromiq.log (bleak DEBUG on) shows
ZERO `peripheral_didUpdateValueForCharacteristic_error_` lines in the window —
that delegate line is logged on the CoreBluetooth dispatch queue the moment a
notification arrives (PeripheralDelegate.py:140), independent of the stalled
asyncio loop. So either the owner did not press during the window (asked), or
no notification arrived at all — which would be a SECOND, deeper fault beyond
Finding 1 (Finding 1 predicts the delegate line WITH no app reaction).
Also confirmed live: "archived CR30-Verify2.ti3 (20 readings) ... before
measuring" and the helper resumed with -r; the stop cancelled A21's wait
cleanly ("read for A21 ended by the stop").

---

# RANKED SUMMARY

## BLOCKER
| # | finding | where | proof |
|---|---|---|---|
| **1** | Over real BLE the wait loop can never see a press: bleak delivers every notification via `call_soon_threadsafe` onto the transport's asyncio loop (PeripheralDelegate.py:145-147, CBCentralManager on its own dispatch queue:213-215), and that loop runs ONLY inside `_run()` (ble.py:174-177). The wait (device.py:272-292) is a plain `take_event()`/`time.sleep` spin with no `_run` — events queue in the stopped loop for ever, every patch times out at 180 s. `drop_events()` is equally blind to queued-but-undelivered events, so the drop cannot be trusted either. 14_protocol.md's own redesign section demanded `_run(wait_for_event(timeout))` for exactly this reason; the implementation deviated from its own analysis. The tests cannot see it: they feed `_events` directly (test_cr30_ble_can_read_a_patch.py:53-86). | device.py:272-292, ble.py:174-177 | scratchpad/proof_loop_stall.py (0 events during the wait, 1 after the next `_run`); bleak source. Hardware run 1 recorded zero incoming notifications — owner's press confirmation pending. |

Fix shape: run the wait inside the loop as 14_protocol.md specified, and flush
the loop (`_run(asyncio.sleep(0))`) before `drop_events()` at arm time.

## MAJOR
| # | finding | where |
|---|---|---|
| 2 | On a COMPLETE chart every prompt carries `all_done` and `on_patch_ready` returns before the re-arm branch — H7's fix is unreachable exactly when a finished chart needs one bad patch replaced. Proven: scratchpad/proof_all_done_gate.py. | measure_bridge.py:240-247 |
| 3 | Pre-arm presses are discarded with log.debug only — 14_protocol.md required a user-visible line ("the honest version of today's silent stale_loc swallow"). | device.py:267-270 |
| 4 | The 0.9927 paper ratio is NOT handling: EXP-BLE-017 (owner's unit, same evening) measures untouched spread 0.24%, lift-reseat 0.22% — neither reaches 0.73%. Its verdict: do not measure a real chart until understood. The white reference may genuinely have shifted; verified restore + re-check before real use. | captures/raw/EXP-BLE-017-repeatability.json |

## MINOR
- `_retries` not cleared when a gave-up patch is re-armed by click (rearm() clears it, on_patch_ready doesn't) — one new failure re-trips read_gave_up (measure_bridge.py:297 vs :391-397).
- `_last_seen` is dead state (written device.py:289, read nowhere).
- `_read_when_ready`'s blanket except swallows programming errors into "the Bluetooth link dropped", tracebackless (device.py:315-323).
- trigger_unsafe's ask() burns its full ~1.8 s poll cycle since the demux routes its reply to `_events` (ble.py:285-297).
- No remembered unit: `DeviceReader()` built bare (tab_measure.py:7063); every session pays discovery; unconfirmed-ffe0 fallback at ble.py:189.
- ble.py:5-8 module docstring still teaches the disproven poll doctrine.
- Research-repo doc corrections owed by 14_protocol.md not done; no committed doc records EXP-BLE-013/014/015/017.
- §M: "Patch {loc} was already measured…" and "Your CR30 has been calibrated." are inline tr() with no catalogue entry (translated in all languages though; consistent with earlier flash lines — process call for the owner).
- Coalesced double-press (one 20-byte notification) would fail the len==10 demux and vanish — HYPOTHESIS, low odds.
- Keep the 0.4 s sleep (it guards the stale-complete-read race retry cannot catch); better: run check_usable inside the retry loop. Event→storage latency unmeasured.
- Stop with no new readings prints M-END-EMPTY then "[ERROR] Measurement failed" (pre-existing, tab_measure.py:9653-9668) — every CR30 resume session ends on an ERROR line.
- 13_verify residue still open: V-8, V-17 (click-to-retry missing from the gave-up message — now the BEST recovery), V-18, V-19 (seen live on a CR30 chart), V-20, V-11b, V-24, B-5.
- Owner observation (live): the calibrate trigger BEEPS when it takes a real measurement (cap off, on a patch) — EXP-BLE-015's "silent trigger" was cap-on only; tab_measure.py:7018-7024 overgeneralises.

## VERIFIED GOOD
- Demux vs fragmentation: MTU 244 (EXP-BLE-009 MTU_RSP f4 00), replies fragment at 241 (410→241+169), events are lone 10-byte notifications in idle; the only time the demux matters the link is idle.
- d/d2: only calibrate_white sends the trigger; identify()/discovery use READ_MEASUREMENT; calibration's own event is dropped at first arm — seen LIVE: "CR30: discarded 1 reading(s) taken before this patch was armed" (18:13:16).
- USB path untouched; take_event/drop_events unreachable there.
- V-2/V-3/V-14/V-15 fixed as claimed; i18n complete for the two new strings.
- ON SCREEN (real app, real CR30, project copy): M-CR30-CALIBRATE window; real BLE calibration + "Your CR30 has been calibrated."; re-arm log line AND surviving status flash on clicking measured A17; split overlay painting (A19's near-white mispair visible); .ti3 20 sets preserved through start/stop; archives to old/ before measuring. Screenshots ~/Desktop/cr30_verify2_01..09.
