# 22_beta — [CR30-BETA] final check before beta
Branch feature/cr30-instrument-159, head 439a8b5c. Round complete 2026-08-30.
Verdict: **DO NOT SHIP** — one proven blocker, one major unverified mechanism. Details below.

## BLOCKER 1 (PROVEN, code + probe + on screen): the bridge's calibrate() takes no `black` —
## EVERY CR30 white calibration now fails, so no CR30 measurement can start
- ui/tabs/tab_measure.py:7049 `reader.calibrate(black=self._black)` and :7156
  `reader.calibrate(black=True)`; `reader` is `workflow.cr30.measure_bridge.DeviceReader`
  (built at tab_measure.py:7290).
- workflow/cr30/measure_bridge.py:630 `def calibrate(self) -> None:` — no `black` parameter.
  Commit 439a8b5c added the flag to `CR30.calibrate` (device.py:185) but never to the bridge
  wrapper the tab actually calls.
- PROOF 1 (real class, no stub): `DeviceReader().calibrate(black=False)` →
  `TypeError: DeviceReader.calibrate() got an unexpected keyword argument 'black'`.
- PROOF 2 (real app, on screen, both themes): clicking "Calibrate now" in the real
  M-CR30-CALIBRATE window produces "The calibration did not go through … What went wrong:
  DeviceReader.calibrate() got an unexpected keyword argument 'black'" and the measurement
  never starts. Shots: cr30_beta_02_white_cal_FAILS_typeerror_{dark,light}.png. Ticked or
  unticked, both transports. The black path fails identically (cr30_beta_04_*).
- The TypeError fires AT THE CALL, before `_open()` — no device I/O ever happens, which is
  also why the on-screen run was safe with the CR30 on the cable.
- Why the gate stayed green: every test that touches this flow is an `inspect.getsource`
  text inspection (tests/test_cr30_black_calibration_flow.py,
  test_cr30_calibrates_before_measuring.py, test_cr30_opens_the_instrument_once.py) —
  nothing EXECUTES `_calibrate_and_confirm` or `_do_black_calibration`. "A green test can
  be guarding the bug", literally. Fix should include one test that calls the flow with a
  stub reader whose calibrate has the bridge's REAL signature (or simply calls the real
  bridge method on a stub device).
- This is the round's "fix that undid the fix": the black-calibration commit broke white
  calibration for every CR30 user.

## MAJOR 1 (mechanism unverified by ANY experiment): read_zero reads the STORED value —
## nobody has shown bb 10 puts its acquisition there
- workflow/cr30/measure_bridge.py:690-708 `read_zero` = `read_measurement(enforce=False)`
  → on USB `usb_measure.read_stored` (device.py:405-407): the device's HELD last reading.
  No trigger, no press. The module's own doctrine (device.py:235-241): "reading without
  waiting returns whatever was already there — instantly, and with every appearance of
  success" — dE 60.5 was the measured cost of exactly this pattern.
- The design said trigger + read (20_blackcal D5). The trigger was dropped, and with it the
  bit-identical-tile cap guard.
- EXP-022 (both runs) verified air-after via a BUTTON PRESS
  (tools/probe_calibration_session.py::press_and_read → wait_for_button_header), never via
  a bare read-back. The vendor captures never read back after a cal either. So whether the
  cal command's own acquisition is readable as the stored measurement is HYPOTHESIS in both
  directions.
- Consequence if it is not stored: read_zero returns the previous stored reading — after
  the white step plausibly the white-tile acquisition (~88 %R → false WARNING on every
  healthy black cal), or a stale 0.0 (false "healthy" after a genuinely botched one).
  Presented at {zero:.3f} % confidence as "the only verification that exists".
- Also: read_zero has no retry for the "16 zero bands (truncated reply)" not-ready state
  the white read-back loops for (measure_bridge.py:668-681) — one early ask → None →
  "could not read back", the weakest message.
- Resolution: either implement the designed trigger+wait+read (cap-off window has just
  ensured no cap; keep the tile heuristic), or one 2-minute owner probe: send bb 10
  correctly, then read-stored WITHOUT pressing anything, and see what comes back.

## What was verified CORRECT (worries a-g from the brief)
- (c) USB frames: `Frame.build(0xBB, 0x11/0x10, 0x00, 0)` matches PRIORART-001
  byte-for-byte, all 60 bytes incl. marker ff and checksums cb/ca — probed against the
  capture file itself, independent of the shipped test. BLE 10-byte frames match the
  pinned trace bytes (ff cc / ff cb). `receive(timeout=6.0)` covers the ~250 ms reply
  (EXP-022: 249-250 ms); no reply → TransportTimeout → caught → honest failure window.
- (a) Guard coverage: `_run_cr30_black_calibration`'s only caller is
  `_calibrate_and_confirm`:7097, whose only caller is the guarded try at :6983 — the black
  window and its worker run entirely inside the Start/Stop-disabled region. On screen:
  Start AND Stop disabled while the white modal is up (printed False/False). The modal
  exec blocks window re-entry.
- (b) The lock: read_zero's `with self._lock` runs on the worker thread strictly after
  calibrate released it (sequential in _BlackWorker.run, tab_measure.py:7154-7158). The
  GUI thread never touches `_lock` in this flow; close() keeps its 2 s bounded acquire.
  No deadlock path found. (At calibration time the helper has not started, so no patch
  read can hold the lock either.)
- (d) Pictogram: `setIcon(NoIcon)` BEFORE `setIconPixmap` is the CORRECT order — probed
  both ways: the reverse order blanks the pixmap; both windows use icon-first
  (tab_measure.py:7010-7011, :7243-7244). steps_pair survives widget=None, 72 pt fonts,
  and a windowText==window palette (invisible ink, no crash — the theme's own text is
  equally invisible then). Crashes only with no QApplication at all (unreachable in-app).
  Looked at in both themes: legible, current step clearly marked, no black tile drawn.
- (e) PROVEN: a QCheckBox set via box.setCheckBox survives box.exec() (accept and reject)
  and holds its value — offscreen probe on a real QMessageBox. `want_black` is safe.
- (f) Skip and failure paths: verified on screen. Skip → True + the exact skip NOTE in the
  log; black failure → True + "Your white calibration is unaffected…" window; white
  failure → False + "Measurement not started" would follow (:5645-5650). `_cal_thread`
  nulled after every loop; how-to window shown on every True path. The failed-open device
  handle situation is the pre-existing white-cal shape, nothing new.
- (g) Threshold 0.05 %R: the SPEC note carries "a starting point, not a measured limit"
  (unified_measurement_management.md:1107) and the one-sidedness is in the on-screen NOTE
  ("not the same as verified"). But the code comment tab_measure.py:195-198 claims it
  "says so on screen" — the provisional status is NOT on screen. False comment (MINOR).
  The threshold itself: healthy unit reads 0.000; 25× above healthy, below worst observed
  contamination; defensible as a provisional WARN line given the message never claims
  proof — provided MAJOR 1 is resolved so the number is about the right reading at all.
- §M: M_CR30_CALIBRATE_BLACK approved=False; catalogue + spec entry present with the
  prudence and provisional clauses 21_design6 C1 required; test_message_catalogue extended.
- i18n: spot-checked keys present in de.json; budget 62→70 carries a dated reasoned
  comment.
- 967917a6 on screen: with the CR30 chart loaded, all four dead options greyed +
  suppressed (args=[] including -T); with a non-CR30 chart everything re-enabled and
  emitting again. The suppression test is behavioural (executes build_args), unlike the
  calibration tests.
- Non-CR30 charts: `_run_cr30_calibration` is reachable only via
  `params.external_values` (tab_measure.py:5634-5644) — untouched, and on screen the
  ChromIQ-Test-Chart project loads, previews and keeps its options.
- Split-patch overlay: visible and correct on the CR30 hex chart
  (cr30_beta_05_measure_tab_cr30_dark.png, "Expected & measured (split)", progress 6.7%
  from the copied project's real partial measurement).

## MINOR findings
1. Double confirmation on a successful black cal: _do_black_calibration plays PATCH_OK and
   flashes "Your CR30 has been calibrated." (:7194-7218), then _calibrate_and_confirm does
   both again (:7113-7119). Two beeps back-to-back.
2. tests/test_cr30_calibrates_the_makers_way.py:66-69 pins only `[:4]` + len for the USB
   frames despite "pinned byte-for-byte" in the commit; payload/marker/checksum unasserted
   (my probe proves them correct today; the test would miss a regression).
3. `CR30.calibrate` USB branch (device.py:222-223) uses send+receive without
   `reset_input()` — unlike every other exchange (transact). A stale unsolicited press
   frame in the buffer (a user pressing the button at the calibrate window) is consumed as
   the "reply", returning early while the acquisition still runs; bounded consequence
   (read_stored transacts and flushes), but it can make read_zero ask too early.
4. ui/cr30_pictograms.py:78 `_draw_cross` never called — the "green face crossed" half of
   the designed cue was dropped; dead code.
5. tab_measure.py:195-198 false comment ("says so on screen") — see (g).
6. M-CR30-CALIBRATE-BLACK body says "about an arm's length above the floor"; the vendor's
   own wizard (and 20_blackcal D6) says about a metre. An arm's length is ~2/3 of that.
7. steps_pair with widget=None and no QApplication raises AttributeError
   (ui/cr30_pictograms.py:115-116) where _ink guards the same case.
8. In the non-current step the pictogram's dashed floor line is drawn at alpha 110 while
   the dimmed instrument is alpha 70 — the "nothing" line outglows its own instrument.
   Cosmetic.

## STILL-OUTSTANDING backlog — confirmed present at head, ranked for the beta
Confirmed by grep/read this round: the false `_previous` claim
(measure_bridge.py calibrate docstring, count 1); the false BLE wait-by-CHANGE docstring
(device.py:248-252); M-CR30-INSTRUMENT-GONE still advising "start the measurement again
with Refine/resume" (measurement_messages.py:210); "using Argyll's default strip
recognition" logged for a CR30 (tab_measure.py:3881); the "1 patch … They are not" region
(:6146-6160 — the 1-patch wording exists; the stale-window fault is the known one);
ble.py poll doctrine (ble.py:6, :320); `_retries` not popped on the click-re-arm branch
(on_patch_ready's read+asked_for path falls to _start_read without popping); no §M entries
for the flash texts; how-to window OK/Stop/close-with-session unbuilt; Keep-measuring
reconnect wait + transport-changed announcement unbuilt; no-reading watchdog banner
unbuilt; V-17 unchanged.
- NONE of these blocks a beta on its own; they are the same open list 21_design6 ranked,
  and previous betas shipped with them.
- The PHONE-THIEF fact changes the ranking, not the gate: with the owner's direct A/B the
  idle-cable rival is dead, and a vendor-app user gets a silently dead session TODAY with
  nothing anywhere in the app saying so. For a BETA whose testers are told, that is
  ship-with-caveat, not do-not-ship — but the caveat is mandatory: the fact belongs in the
  beta's release notes NOW, and the no-reading watchdog banner (21_design6 D3) becomes the
  top post-beta item, with a cheap immediate mitigation available (one log NOTE at CR30
  session start naming the symptom and the phone app). Shipping with nothing written
  anywhere would be negligent of a KNOWN silent failure.
- Next after the watchdog: the owner-agreed how-to window work (item 1), the reconnect
  cluster (item 2), then the hygiene batch (false docstrings must not reach a release).

## ON-SCREEN (required) — done, real app, real styling, both themes
Driver: scratchpad/onscreen/drive_beta.py (sandboxed QSettings→ini, presets dir, output
path, trash no-op; project = COPY of ~/ChromIQ/CR30-Test; ~/ChromIQ untouched; 180 s hard
watchdog; no modal left waiting; chart loaded via the app's own session-restore path
main_window.py:2396-2397). No device I/O occurred (TypeError precedes open — proven).
Shots in ~/Desktop/CR30-test-shots/, looked at, both themes:
- cr30_beta_01_white_window_{dark,light}(.png/_fullscreen): the REAL white window with
  pictogram + unticked checkbox; Start/Stop disabled while it is up.
- cr30_beta_02_white_cal_FAILS_typeerror_{dark,light}: BLOCKER 1 on screen.
- cr30_beta_03_black_window_{dark,light}: the real M-CR30-CALIBRATE-BLACK window with the
  pair pictogram, current step marked; legible in both themes.
- cr30_beta_04_black_cal_FAILS_typeerror_*: black failure path returns True, honest text.
- cr30_beta_05_measure_tab_cr30_dark: CR30 hex chart, split overlay, greyed options,
  partial-measurement progress.
- cr30_beta_06_noncr30_untouched_*, cr30_beta_07_build_profile_*: non-CR30 project loads,
  options live, Build Profile tab reachable.
Skip path verified live: returns True and writes the skip NOTE.

## THE VERDICT: DO NOT SHIP this as a beta.
The branch head cannot measure with a CR30 at all — the feature the branch exists for.
Shortest path to a YES:
1. Fix BLOCKER 1: give `DeviceReader.calibrate` the `black: bool = False` parameter and
   forward it to `self._dev.calibrate(black=black)` (the white read-back loop stays
   white-only or moves under `if not black`), OR call through a properly routed path.
   Add ONE executing test of `_calibrate_and_confirm` (stub reader, real signature) so a
   green gate means the flow runs.
2. Resolve MAJOR 1 before the checkbox is offered: either make read_zero trigger+wait+read
   as designed, or prove read-stored-after-bb10 on the owner's unit (2 minutes). If
   neither is possible tonight, shipping with the zero check reporting "could not read
   back" would be dishonest given the alternative is one code change — fix it.
3. Put the phone-thief fact in the beta's release notes (and ideally one log NOTE at CR30
   session start). The watchdog banner can follow.
With 1 and 2 done and the gate re-run (plus one real-hardware white cal to confirm the
restored flow), this is a shippable beta; the minors and the ranked backlog can ship open
as they did in every previous beta.
