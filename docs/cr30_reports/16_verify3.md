# CR30 Verify Round 3 — [CR30-VERIFY-3]

## In progress
Started 2026-08-28. Reading 14_protocol.md, 15_verify2.md, git log, 63831d67.

Read: 14_protocol.md, 15_verify2.md, full diff of 63831d67. Desk-trace of the
owner's log scenario matches the implementer's reading so far (A19 re-armed via
asked_for; A24's in-flight worker consumed press 1 → stale_loc; A19 read on
press 2; helper auto-advanced to A20; spot_ready A20 read:true all_done:false →
`on_patch_ready` sets `_awaiting_loc` then returns at the read-and-not-asked_for
gate, measure_bridge.py:256-260 — nothing armed, tab still highlights). To
verify against code: helper's advance-by-index + `n` command, tab highlight
site, worker/lock interleaving.

## FINDING 1 — BLOCKER CONFIRMED (mechanism verified, plus a second way in)
The implementer's reading of the A20 stall is CORRECT, and reproduced against
the real bridge (scratchpad/proof_a20_stall.py):
- click A19 (read) -> asked_for re-arm works (read_calls 1, rearmed [A19], value sent);
- helper records the value and advances BY INDEX (`incflag = 1`,
  chromiq_chartread.c:3181/3199 — spot value + instrument branches), NOT
  next-unread;
- spot_ready A20 read:true all_done:false -> measure_bridge.py:247 sets
  `_awaiting_loc="A20"`, :256-260 returns — 0 new read_calls, 0 signals,
  awaiting_loc='A20', 0 threads. Nothing armed, nothing said, and with no
  worker no wait_for_event pumps the loop so the press notification is not
  even DELIVERED (ble.py wait_for_event is the only pump).
- tab_measure.py:10948-10972 `_on_patch_ready` highlights loc UNCONDITIONALLY
  after bridge.on_patch_ready — the highlight lies.
- Not `_nav_target` (cleared at :246), not `_retries`, not zombie-worker state:
  the A24 drop at log 38781 is A24's still-running worker (holding
  DeviceReader._lock, measure_bridge.py:474/514) consuming press 1 ->
  `_why_not` stale_loc (:441-442), `_reading_loc` untouched ("A19" != "A24",
  :420). It leaves NO state behind; press 2 was accepted normally. The stall
  is purely the traversal-skip.
SECOND WAY IN (new): the helper's dE-sanity branch (chromiq_chartread.c:3211-
3222, werror >= WERR_TH 95, or ACC_WERR_TH 30 with accurate ref) sets
incflag=0 and re-offers the SAME patch — now rr=1 -> read:true, not asked_for
-> same silent stall on a FRESH chart (scratchpad/proof_werror_stall.py:
VERDICT SAME STALL). 14_protocol.md caveat 2 claimed the `_reading_loc == loc`
latch covers this; it does not — `_reading_loc` is cleared in `_on_reading`
(:420-421) before the helper re-offers.
Also: tests/test_cr30_can_re_read_a_patch.py::test_merely_passing_over_a_read_
patch_still_skips_it is a green test guarding exactly this bug's shape.
Helper `n`/next_unread verified: {"cmd":"next_unread"} -> 'n'
(chromiq_json.c:211-212), mirrored onto the -x line queue (:247-268), xtern
parser 'n' -> incflag=3 (chromiq_chartread.c:3097-3099) -> search starts AFTER
current pix, wraps, stops at opix (:2716-2750). all_done=false guarantees an
unread non-padding patch exists (:2802-2806) so next_unread always lands on
one — no loop. ChromIQ already sends it from the keyboard engine map
(workflow/chartread_engine.py:97) but nowhere on the CR30 path.

## Working tree is NOT 63831d67
Three files carry uncommitted changes (git diff HEAD): `_last_seen` dead state
removed (device.py:40-46, tests x2) and the traceback log added to
`_read_when_ready`'s broad except (device.py:320-330). Both are 15_verify2
minors, correctly done. The green-gate claim covers 63831d67 only; targeted
runs here are against the working tree.

## Q1 groundwork (USB)
- usb_measure.py / transport.py / frame.py / session.py / measurement.py /
  discovery.py: EMPTY diff a7516de1..63831d67 — byte-identical since the
  known-good USB session.
- wait_for_event/drop_events: BLE branch only (device.py:256 after the USB
  return at :234). SerialTransport never sees them.
- USB wait loop DID change since the good session: except-classification
  (device.py:222-233, TransportTimeout/ShortFrameError wait, rest DeviceLost)
  — unit-tested (test_cr30_notices_the_device_is_gone.py: 3 USB tests).
- `read_measurement` USB branch now sets `_previous` only under enforce
  (device.py:358-366). Its comment "nothing calls the USB path with
  enforce=False" is FALSE: DeviceReader.calibrate's read-back
  (measure_bridge.py:593) does, on any transport. Consequence: calibrate()'s
  documented seeding of `_previous` ("leaves the reading this takes as the
  device's _previous... the baseline the change-detection needs",
  measure_bridge.py:558-561) NO LONGER HAPPENS — 63831d67's only-accepted-
  readings rule silently defeated it. Residual risk low (first-patch stale
  tile still caught by looks_like_calibration_tile, measurement.py:189), but
  docstring and code now disagree in both files. MINOR.
- The 0.4 s pre-read sleep 15_verify2 said to KEEP was removed in 63831d67;
  bit-identical stays OUTSIDE `_read_when_ready`'s retry (enforce=False at
  device.py:309, check at :292). The stale-complete race now leans on ask()'s
  intrinsic ~1.8-2 s latency alone. If it fires: one press lost, user told to
  press again (not silent). HYPOTHESIS/MINOR; proper fix = check_usable inside
  the retry.
- No unit test exercises the USB SUCCESS path (header -> read_stored ->
  chunks); its proof is the 2026-08-28 hardware session + unchanged bytes.

## Q2 audit (shared code, per item) — desk complete
1. `abort()` sets `_user_quit` (measure_manager.py:983-996): callers are all
   deliberate (decline pre-measure question tab_measure.py:4924, Discard
   :6151, spot_read_dialog.py:285/807). Gates 471/559/594/639/717 all PREDATE
   this change (only the flag-set is new — measure_manager's entire diff since
   a7516de1 is this one hunk). Effect for every instrument: declining/
   discarding no longer triggers the stock-chartread fallback or resume-
   fallback (which could previously RELAUNCH a measurement the user had just
   refused, when no event had been seen). FIX, defensible. Residual: a
   cal_failed racing in after a Discard now emits inst_init_failed directly
   (:559-561) instead of scheduling retries at a dead process — window
   possible post-discard; narrow race, LOW.
2. `_on_instrument_disconnected` (tab_measure.py:7464-7479): abort() replaced
   by `_end_session(_confirm_end_of_session(END_FAILURE_WINDOW))`. BEHAVIOUR
   CHANGE FOR ALL INSTRUMENTS: an i1Pro/ColorMunki disconnect now raises the
   shared ending window (Save/Discard/Keep measuring) instead of killing the
   run — and on stock chartread the old kill LOST the .ti3 (written only on
   clean exit). Defensible per measurement_exit_strategy.md §1 (one exit);
   the owner must be told (new window where the session used to just die).
3. `tab_profile.set_ti3_path` (tab_profile.py:4016-4070): gates Build on
   classify(); disabled only for ABSENT/EMPTY/NO_DATA_BLOCK/UNREADABLE;
   PARTIAL/MISMATCHED/COMPLETE stay enabled. All callers pass existing files
   (main_window.py:924/1655/1671/2411 guarded by exists()). Role-named ti3
   without a sibling ti2 -> expected=None -> PARTIAL/None -> enabled, no
   label (measurement_state.py:158-159). classify/count_sets are the same
   parser resume already trusts. Behaviour change for all instruments
   (defensible); verify on screen with a demo project.
4. Overlay `_show_overlay_from_existing_ti3` (tab_measure.py:11448-11470):
   drawable decided from THIS file's patches before drawing — removes the
   false-positive from a previous chart's accumulated overlay. \
   `_overlay_failure_reason` (:11821-11830) resolves the ti2 — fixes the
   false "no_geometry" on reopened projects. Both all-instrument fixes, low
   risk.
5. `_try_load_tiffs` no-TIFF branch clears `_patch_boxes` + preview boxes
   (tab_measure.py:4330-4344): stale-geometry fix, right branch, low risk.
6. `_maybe_repair_target_instrument` via `_chart_file_for`
   (tab_measure.py:4698-4712): repair window now REACHABLE on reopened
   projects (.ti1 handed in). CR30 is in KNOWN_INSTRUMENTS
   (ui/ti2_loader.py:49-54) so CR30 charts never trip it. New window
   appearance on reopen for foreign charts = behaviour change, defensible.
7. `_on_patch_measured` no-box message (tab_measure.py:10983-11005): additive,
   once per session; new user-facing text outside §M (same unsettled
   convention as the other engine log lines).
8. `_confirm_end_of_session` plural split (tab_measure.py:6083-6112): the
   spec pins "You have read **{n} patches** in this session." VERBATIM
   (unified_measurement_management.md:259 and :637). The split introduces
   singular variants that are NOT in the catalogue/spec, changing approved
   window text without the §M process; and the n==1 rendering is
   ungrammatical: "You have read 1 patch in this session. They are not in
   your measurement file yet — ChromIQ can write THEM now..." (the second
   sentence stays plural). MINOR defect + process flag.
9. Discard path: `_end_session("discard")` already called abort(); only the
   flag is new — see item 1. Strip-mode Discard still kills the helper (that
   IS discard); no regression.

## The latency item (owner's "a little less of this would be nice")
Re-derived from chromiq.log 38654-38664 (2026-08-29 18:50, THIS build — the
[INFO] "discarded 1 reading(s)" line at 18:49:14,574 is 63831d67's wording,
and the event at 18:50:08,135 arrived 53.6 s after the last write, i.e. the
new event wait was live):
  event 08,135 -> WRITE bb 02 10 08,577 (+442 ms) -> reply notification
  08,857 (+280 ms) -> polls 08,928 / 09,280 / 09,631 -> value 09,985.
  Total 1.850 s.
CORRECTION to the implementer's reading: the 442 ms is NOT the removed
sleep(0.4) — that sleep was already gone in this build. It is `_drain`'s
0.4 s settle (ble.py:317-329), called unconditionally at the top of `_ask`
(ble.py:332), and it is STILL THERE. "Today's figure should already be
~1.4 s" is FALSE; today's figure is the measured 1.85 s.
Budget (source-verified): 0.40 drain + 0.35 first wait (reply lands at
0.28) + 3 x ~0.352 quiet-confirm = 1.85 s. Floor = ~0.28-0.33 s
(write->reply, radio+device) + ~0.05 event pickup. Ours: ~1.5 s.
quiet>=3 / wait=0.35 provenance: introduced whole in 1f40fe0d with no
measurement; TRANSPORT_BLE.md holds no pacing numbers. Guesses, never
revisited.
Predicate-stop critique: SOUND if the predicate is read_measurement's OWN
candidate scan (scan-from-end + validate + zero_run>=3) — in the vendor's
truncated+complete stream the truncated candidate FAILS zero_run, so the
predicate cannot stop on it; it first passes when the complete reply is in.
No corpus case of a valid reply followed by another reply to one request.
`_drain` must STAY (it becomes the safety net for burst tails once the quiet
confirmation is gone). Expected result ~0.85 s/press. USB comparison: no
sleeps anywhere on the USB path (transport.py:166-175 polls at 0.5 ms;
read_stored = 3 transacts) — machine share ~0.05-0.2 s; the observed fastest
full prompt->value cycles in the 22:26 USB session are ~3.5 s INCLUDING the
human. Demux interaction: events never enter `_buf`; early break leaves at
most reply-tail bytes that the next `_drain` clears — same as today.

## Still-open list from 15_verify2 (confirmed against working tree)
- FIXED: `_last_seen` dead state (removed, uncommitted); `_read_when_ready`
  traceback logging (added, uncommitted).
- OPEN: `_retries` not cleared on click-to-retry (only rearm() :311 and
  success :432 pop it); bare `DeviceReader()` (tab_measure.py:7063 — every
  session pays discovery, unconfirmed-ffe0 fallback ble.py:189); ble.py:6-8
  docstring still teaches the disproven poll doctrine; EXPERIMENTS.md still
  lacks EXP-BLE-012..017 entries (TRANSPORT_BLE.md + CALIBRATION.md were
  updated, research repo 44ab7df); the two flash strings still have no §M
  entry; V-17.

## Q-A: remembering the device address (owner's question)
1. STALE ADDRESS TODAY IS FATAL, NOT A FALLTHROUGH. `BleTransport.open`
   (ble.py:182-202): with `address` set it never scans — `BleakClient(target,
   timeout=20).connect()` waits the full 20 s for a unit that is not there,
   raises, and `DeviceReader._open` reports "no device". No fallback to
   discovery exists. A remembered-but-absent unit is therefore SLOWER than no
   memory (20 s vs ~17 s) and finds nothing, where bare discovery would have
   found the second unit. Design: try the remembered address with a SHORT
   timeout (~5 s), on failure run discovery, use what it finds, UPDATE the
   memory, and say in the log which unit was used.
2. TWO UNITS: today `ok[0]` (ble.py:189) picks arbitrarily, and with zero
   confirmed candidates it will connect an UNCONFIRMED ffe0 device (any
   BLE-UART gadget). Identity: the ADVERTISED NAME is the unit's own id
   string (discover() docstring :95-97, TRANSPORT_BLE.md) — a genuine
   per-unit label; the ADDRESS on macOS is a host-local CoreBluetooth UUID
   (stable per Mac, NOT portable, can be invalidated by a BT cache reset).
   So remember BOTH; match by address, display/confirm by name. With >1
   confirmed candidate and no remembered match: ask (a chooser fed by
   discover()'s list). With exactly one: use it and log which.
3. WHERE: app-wide AppSettings (the instrument is bench property, not target
   property; a per-target address strands every new target). Self-healing on
   replacement: failed remembered connect -> discovery -> overwrite memory.
   No stale-memory support case remains.
4. CALIBRATION: units do not share a white reference, but ChromIQ calibrates
   at every session start (M-CR30-CALIBRATE) unless Skip is ticked, and a
   transport is opened once per session — so a switch cannot happen
   mid-session. The one hole: Skip-calibration ticked + a different unit
   found. The unit-changed log/banner line ("measuring with 'CR30-xxxx',
   last time this project used 'CR30-yyyy'") closes it.

## Q-B: shortening the read wait (owner's question)
1. VALID-THEN-BETTER: no case in the corpus. The only multi-reply stream ever
   captured (vendor, EXP-BLE-009 ATT) is truncated+complete, and the
   truncated half FAILS zero_run — the predicate cannot stop on it. A second
   VALID reply after a first valid one has never been observed on any unit.
2. quiet>=3 @ 0.35 is INHERITED GUESSWORK: introduced whole in 1f40fe0d, no
   measurement, none in TRANSPORT_BLE.md. Measured worst intra-reply gap:
   the 243/171 fragment pair in EXP-BLE-009 is 180 ms apart; every other
   reply in the corpus is ONE notification (EXP-BLE-010: 200 bytes in one).
   1.05 s guards a 0.18 s worst case.
3. COMPLETENESS IS DECIDABLE: for the axis the device declares, a reply has
   a known size — observed exactly 200 bytes for 31 bands (EXP-BLE-010),
   MIN_REPLY 196 = LAB_AT+12. Predicate = read_measurement's own scan
   (find HDR from end, length >= MIN_REPLY, axis parse, validate, zero_run<3)
   — not a length test alone.
4. SAFE SAVING: 1.85 -> ~0.85 s/press (drop the 3x0.35 quiet-confirm ≈1.05 s
   and the ~70 ms first-wait tail; keep _drain's 0.4 s and the 0.28 s radio
   floor). ~1 s x 390 patches ≈ 6.5 min per chart. A compromise without any
   early break — quiet>=1 with wait 0.25 (covers 180 ms measured gap) —
   saves ~0.8 s and needs no predicate; the predicate version is better and
   no less safe because validation is the same code the slow path runs.
5. THE EXISTING DEFENCES ARE UNTOUCHED: the calibration read-back's zero-fill
   rejection happens AFTER ask() returns, in read_measurement's candidate
   scan; a zero-filled reply never satisfies the predicate, so ask() then
   simply falls back to the quiet rule (unchanged) and returns it to be
   rejected+retried exactly as on 2026-08-29 16:57.
   RECOMMENDATION: predicate-stop with the full validation, quiet rule kept
   as fallback, `_drain` untouched. Expected ~0.85 s press-to-recorded.

## ON-SCREEN (part A complete)
Real MainWindow + real helper + real styling on the live display; sandboxed
QSettings + sandboxed working folder holding COPIES of CR30-Test and the
i1Studio project (real ~/ChromIQ and real settings untouched; plists backed
up to scratchpad/backup anyway). Device layer replaced by a scripted
stand-in (the hardware ground truth for the same sequence is the owner's own
log). Screenshots ~/Desktop/cr30_verify3_01..06 so far.
- Session resumed; first prompt A24 (A1-A23 read) — the session-start
  next-unread skip works.
- Click A5 (read) -> re-arm fired, reader started (calls>=1,
  reading_loc=A5) -> scripted press with A5's exyz -> value recorded ->
  helper advanced BY INDEX to A6 (read, all_done false).
- STALL REPRODUCED ON SCREEN: nothing armed (reading_loc None,
  awaiting=A6, no new reader), A6 HIGHLIGHTED in the preview
  (_active_patch_box == A6's box) — shot 04 shows the highlight ring on A6
  with "Ready to read patch '159' at 'A6' (Already read)" in the log and NO
  message about it.
- BONUS, faithfully the owner's experience: a further press in the stall
  state was consumed by the still-alive A24 worker (armed at session start,
  never cancelled by the goto) and dropped with "That reading arrived when
  ChromIQ was not waiting for one..." — visible in shot 04's status line.
  After that worker dies, presses are not even delivered (no wait_for_event
  pumping).
- Recovery: clicking A6 re-armed it (reader started) — the H7 fix itself
  works; shot 05.
- Stop went through the ending window cleanly (watcher answered
  "Yes — Stop" / "Discard and stop"); shot 06.

## ON-SCREEN part B (Q2 evidence) + a NEW defect found by it
Real i1Studio project copy (Pro300_EpsonPremSG_i1Studio_Jun26 — complete
measurement, shipped profile). Shots 07/08.
- Build Profile ENABLED, guided panel normal, "Detected instrument:
  ColorMunki / i1Studio / CCStudio (spectral data present)". PASS.
- Overlay: 0 patches painted — CORRECT for this chart (old printtarg layout,
  no engine geometry); the M-window "Your measurement is fine — this chart
  just can't display it on the patches" appeared with the RIGHT reason (the
  _overlay_failure_reason fix working as intended on a reopened project).
  My driver's assertion was miswired for this project, not the app.
- NEW DEFECT (MAJOR), on screen in shot 08: the file label reads
  "…Jun26.ti3 — 924 of 940 patches measured" for a COMPLETE measurement.
  Cause: `expected_patches` (workflow/measurement_state.py:121-131) counts
  ALL ti2 rows, but printtarg pads the last row — this ti2 has 16 padding
  rows (SAMPLE_ID "0"), and chartread writes only the 924 real patches. So
  classify() returns PARTIAL 924/940 (verified directly) and
  tab_profile.set_ti3_path (tab_profile.py:4040-4046, 4055-4063) prints the
  partial label AND a tooltip advising "go back to Measure and tick Refine /
  resume" — wrong statement, wrong advice, on every padded chart, for every
  established instrument. The helper's own all_done ignores padding
  (chromiq_chartread.c:2802-2806); expected_patches must too. CR30's hex
  chart has 0 padding, which is why the CR30 flow never showed it.
- Driver notes: two windows were answered by hand mid-run via keystroke
  (the existing-measurement offer and the no-geometry window) — they only
  gated navigation, no assertion depended on them.

## Owner's mid-round observation: "argyll default strip recognition" on a
patch-only device — CONFIRMED, mechanism found
tab_measure.py:3810-3825: the "Chart instrument: {label} → {detail}" line
special-cases only `is_spectroscan(instr)` for per-patch instruments; a CR30
falls into the strip branch and logs "using Argyll's default strip
recognition" — a strip-direction note about a session that reads single
patches (and under -xx no Argyll strip recognition runs at all). Fix shape:
give CR30 the SpectroScan treatment (plain "Chart instrument: CR30.").
MINOR, misleading wording only. (The greyed "Strip recognition:" combo in
the options panel is the generic panel, pre-existing.)

## THE FIX DESIGN (challenge items 2 and 3 of the brief)
Recommended behaviour when the helper offers an ALREADY-READ patch:
- `read:true, not asked_for, all_done:false` (traversal on a resumed chart,
  or the dE-sanity re-offer): the bridge sends `{"cmd":"next_unread"}` and
  arms nothing. Verified safe: the helper maps it to 'n'
  (chromiq_json.c:211-212, mirrored to the -x line queue :247-268), incflag=3
  searches from AFTER the current patch and all_done:false guarantees an
  unread non-padding target (chromiq_chartread.c:2716-2750, 2802-2806) — no
  loop possible, one command per prompt. This matches what "Refine / resume"
  promises (read only what is missing) and the beginner's model (the
  highlight moves to the next patch that needs measuring). ChromIQ already
  speaks this command from the keyboard map (chartread_engine.py:97).
  Caveat to say in the log: keyboard 'f'/'b' navigation onto a read patch
  will now bounce to the next unread instead of stalling silently; click-
  to-jump (which sets asked_for) remains the way to deliberately visit a
  read patch.
- `read:true, asked_for`: keep the re-arm (works, on hardware and here).
- `all_done:true, not asked_for` (complete chart, after a re-read): nothing
  to arm — but the UI must then show an "all patches measured — click a
  patch to re-read, or Stop" state, not a highlighted patch. next_unread
  must NOT be sent here (it would return to the same patch).
INVARIANT (item 3): "the preview never highlights a patch the bridge did
not arm." Expressible and testable: `on_patch_ready` already runs BEFORE the
highlight (tab_measure.py:10963-10965 vs :10966-10972), so either return the
decision from on_patch_ready or have the tab consult
`bridge._reading_loc == loc` / a new `patch_armed` signal, and highlight
ONLY armed patches (unarmed -> highlight_patch(-1, None) + the banner
below). Unit-testable at both levels; the existing green test
test_merely_passing_over_a_read_patch_still_skips_it guards the skip and
should gain the companion assertion that a skip is VISIBLE (signal or
command), never silent.

## UI feedback ruling (his "popup would be better")
Recommend the PREVIEW BANNER, not a popup: TiffPreview already has
`set_banner` (ui/tiff_preview.py:1089-1096, 1815-1827 — "advisory banner
above the image", used today only by tab_chart:12954). Put the re-arm /
dropped / discarded texts there (they are already translated), keep the log
line, keep or drop the status flash. Against a modal: (a) the app's own
stated rationale — "a modal would sit between the user and the preview they
are meant to be watching" (_show_cr30_measuring_window, tab_measure.py:
7236-7238); (b) Knut's once-only rule for mid-measurement popups
(unified_measurement_management.md:350, :802); (c) measurement_exit_
strategy.md enumerates every window during a measurement with its keys — a
new window means §M approval + that table + test_both_readers parity, while
a banner is not a window; (d) practically, a popup per dropped press demands
a click with the instrument in the user's hand. §M note: these texts are
already outside the catalogue (unsettled convention, flagged since
15_verify2) — moving them to a banner does not worsen that, but the owner
should rule on the convention.

## Spec-compliance gaps found this round (process)
- The disconnect ending-window route (Q2 item 2) is in NO spec:
  measurement_exit_strategy.md contains no mention of a disconnect raising
  the END_FAILURE_WINDOW. CLAUDE.md's rule 2 requires this behaviour change
  in a spec-covered area to be reported and approved; it also belongs in
  that doc's window table once confirmed.
- The ending-window text change (plural split) rewrites wording the spec
  pins verbatim (unified_measurement_management.md:259/:637) without §M; and
  its n==1 rendering is ungrammatical ("You have read 1 patch … They are not
  in your measurement file yet — ChromIQ can write them now").
- The two new discard strings are translated in German only; 11 catalogues
  carry English values (test-green; consistent with translate-before-final
  policy, needs the sweep before a final).

## STATUS: COMPLETE — ranked summary in the final message.
