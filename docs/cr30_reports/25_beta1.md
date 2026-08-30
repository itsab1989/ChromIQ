# 25 — [CR30-B1] challenge of the 4.1.5 beta 1 plan

STATUS: COMPLETE. Round found TWO new blockers in the implementer's own recent commits (6ddae691 placebo; 39499d31 dead resume), verified W9/W5/W3/W6/W7 with corrections, answered the gate question.

## W9 — VERIFIED, with two corrections to the implementer's blast-radius claim
- The bug is real: `native/chartread_helper/chromiq_chartread.c:4245-4248`
  interpolates `inname` raw into the session_start JSON. `cq_json_escape`
  exists (chromiq_json.c:51) and IS used for the only other path emitted
  (`saved`, chromiq_chartread.c:493-495). Windows paths → invalid escapes →
  event dropped. Confirmed by reading, matches the Windows log line.
- Sibling audit (every emit site in chromiq_chartread.c/chromiq_cal.c/
  chromiq_json.c): session_start's `inname` is the ONLY unescaped *path*.
  But a whole CLASS of chart-derived tokens goes in raw: strip labels +
  id/loc (567-591, 603, 622, 2053, 2150, 2453, 2492, 2584, 3116, 1691) and
  chart_refused's TARGET_INSTRUMENT (3732, straight out of the .ti2). None
  can carry a backslash from a chart ChromIQ itself made; a hand-edited .ti2
  with a quote in an id would break those events on ANY platform. Fix the
  path for beta 1; note the class for later.
- CORRECTION 1 to the brief: `_chart_was_complete` and `_session_strips`
  are per-start reset in Python (measure_manager.py:381, :385) — they do
  NOT keep the previous session's values; they stay at False/[] all session.
  What DOES leak across sessions: `_saw_spot_ready`, `_ending_already_answered`,
  `_stop_requested` — initialized once (:326, :333) and reset ONLY in the
  session_start handler (:1190-1193). A session that set
  `_ending_already_answered=True` (:761, :1438, :1445, :1770) leaves it True
  into the NEXT Windows session. That is the sharpest consequence.
- CORRECTION 2: for the CR30 (spot mode) the beta.137 fallback at :1290-1297
  partially compensates — first spot_ready on a resume sets
  `_chart_was_complete`. The cases that actually break on Windows:
  full-re-read completion announcement (`_read_the_whole_chart_this_session`
  can never be True with `_session_strips` empty, :1104-1110), the UI strip
  map, and the stale-flags leak above.
- Rebuild question ANSWERED: released artefacts are safe by construction —
  build-release.yml:186-198 rebuilds the macOS engine in CI; build-windows.yml
  builds both Windows exes from source. The committed macOS Mach-O
  (native/chromiq-chartread) is CURRENT today (refreshed 0c9cb3b4 AFTER the
  last helper-source commit f8cdaf75; `git diff 0c9cb3b4..HEAD -- native/chartread_helper/` empty).
  ⚠ BUT: a W9 fix commit must include a rebuilt committed Mach-O, and NOTHING
  enforces that — tests/test_cr30_packaging.py:48-60
  (`test_the_bundled_helper_is_not_stale`) only greps for b"CR30", which the
  pre-fix binary already contains. The stale-binary test goes green on a
  stale binary for every change after the CR30 marker landed. W6's disease,
  on macOS, waiting.

## Pending
W5, W3, W6, W7, W10, gate question, audit of 39499d31/6ddae691, on-screen.

## NEW BLOCKER — 6ddae691 ("a Bluetooth calibration waited seconds…") is a
## PLACEBO. Zero of its three promised behaviours land; its four tests stub
## the method under test.
Proven with the REAL `BleTransport._ask` + real demux, fake only at the bleak
boundary (scratchpad/probes/probe_ble_done_dead.py). Ack delivered instantly
through the transport's own `_on_notify`:
```
cmd 0x11 (white cal): wall 1.81s, 3 polls, done called 3x (matched 0), buf 10B, events left 0
cmd 0x10 (black cal): wall 1.81s, 3 polls, done called 3x (matched 0), buf 10B, events left 0
cmd 0x01 (trigger)  : wall 2.16s, 4 polls, done called 0x,            buf 0B,  events left 1
```
Why:
- The commit's premise — "the demux routes every well-formed ten-byte command
  frame to the EVENT queue" — is FALSE. `_on_notify` (ble.py:248) routes only
  `b[1] == 0x01` frames to `_events`; a `bb 11`/`bb 10` calibration ack goes
  to `_buf` (ble.py:252). So calibration's `done=lambda _b: saw_event(cmd)`
  scans the queue the ack never enters: the early stop never fires, and the
  stop is the OLD quiet-3 rule. The promised ~1 s saving does not exist.
- The trigger's ack DOES go to `_events`, so `_buf` stays empty — and the
  early-stop guard `if done is not None and self._buf and done(...)`
  (ble.py:374) short-circuits on the empty buffer: `done` is NEVER CALLED.
  All polls run, exactly as before the commit.
- Therefore the ack is NOT consumed ("events left 1"). The third test's
  promise — "the acknowledgement is consumed, not left lying around" — is
  false on the real path. Consequence chain (real code): BLE black-cal runs
  `read_zero` → trigger ack sits in `_events` → first patch armed →
  `drop_events()` (device.py:327) counts it → `on_dropped` → the operator is
  told "One reading was taken before ChromIQ was ready for it" for a press
  nobody made. Pre-existing hazard, but the commit claims it closed and did
  not.
- The four tests (tests/test_cr30_bluetooth_calibration_is_not_slow.py) pass
  because `_Link.ask` RE-IMPLEMENTS the poll loop without the `and self._buf`
  guard and appends the ack to `_events` for every cmd — modelling the
  commit's mistaken premise, not the demux. "Proved to land: with the waits
  restored, all four pins fail" proved only that the stub honours `done=`.
This is the round's recurrence of "tests read the source instead of running
it", one step worse: tests that mock the code under test.
Correct fix shape: calibration `done=` must validate the BUFFER (complete
valid 10-byte frame with `b[1] == cmd` — 23_live L3's own words: "a complete
valid 10-byte echo frame is the honest predicate"); the trigger needs the
guard relaxed to `if done is not None and done(bytes(self._buf))`
(`_parse_reply(b"")` at device.py:25 is safe on empty) so `saw_event(0x01)`
can run AND consume. New tests must drive the real `_ask` with a fake client,
as the probe does.

## SECOND NEW BLOCKER — 39499d31's "Recalibrate now" leads to a DEAD SESSION.
## The magnet window's one remedy destroys the bridge it is meant to resume.
Proven ON SCREEN, real app, both themes (driver
scratchpad/onscreen/drive_b1.py; stub device, sandboxed settings, project a
COPY of CR30-Test). The chain:
1. Magnet refusal → `_on_read_failed(..., "MagnetGated")` stops the bridge and
   emits `magnet_gated` (measure_bridge.py:472-485). Correct.
2. Tab handler `_on_cr30_magnet` (tab_measure.py:7406) shows the window;
   "Recalibrate now" → `_run_cr30_calibration()` → `_calibrate_and_confirm`,
   whose FIRST act is `self._close_cr30_bridge(); self._open_cr30_bridge()`
   (tab_measure.py:7025-7026 — "a previous session's bridge must not be
   inherited"). That STOPS and DISCARDS the live, magnet-stopped bridge —
   `_close_cr30_bridge` calls `bridge.stop()` and `reader.close()`
   (tab_measure.py:7332-7343; over BLE that is a full disconnect mid-recovery)
   — and builds a fresh bridge with `_awaiting_loc=None`.
3. Back in the handler, `bridge = getattr(self, "_cr30_bridge")` is the NEW
   bridge; `resume_after_magnet()` (measure_bridge.py:348) hits
   `if not self._stopped: return True` — vacuously True, nothing re-armed.
4. The tab prints "Carrying on. Read the highlighted patch again — and check
   there is no magnet under your paper this time." Nothing is listening.
Driver output (dark run, identical in light):
```
stopped after resume (OLD bridge): True
same bridge object: False
NEW bridge _awaiting_loc: None | NEW bridge _reading_loc: None
NEW threads alive: [] | OLD threads alive: []
device calls now: ['white', 'white']    ← the recal DID run; the resume is the lie
```
The operator who just hit a magnet — the owner, in his own incident — presses
the offered remedy, sees "Carrying on", presses the instrument's button, and
nothing ever happens again. This is the same dead-end-after-refusal class the
branch fixed for click-re-arm, reintroduced by its own headline fix.
Why the tests missed it: all of tests/test_cr30_magnet_stops_the_session.py
drives the BRIDGE in isolation; `test_there_is_a_way_back_after_recalibrating`
calls `resume_after_magnet()` on the SAME bridge object. The tab flow that
swaps the bridge is untested. Note `_open_cr30_bridge`'s own docstring
(tab_measure.py:7297-7305) says the calibration must reuse the standing
bridge "so the instrument is opened once" — the unconditional close at
`_calibrate_and_confirm`'s top contradicts it for the mid-session call.
Fix shape: `_run_cr30_calibration(keep_bridge=True)` from the magnet handler
(skip the close/open pair when a live bridge exists), plus a test that walks
the TAB path and asserts the same bridge object survives and a reader is
armed for the outstanding patch afterwards.

## ON-SCREEN — done, real app, real styling, BOTH themes
Shots in ~/Desktop/CR30-test-shots/ (looked at):
- cr30_b1_01_howto_survives_session_end_{dark,light}(+fullscreen): W7 CONFIRMED
  ON MACOS — after `_close_measurement_windows()` the how-to window is still
  visible (`registered in _live_measure_windows: False`), and its one button
  "Start measuring" only closes it (nothing starts). Not Windows-specific.
  The fullscreen shot also shows the standing-backlog line live:
  "Chart instrument: CR30 → using Argyll's default strip recognition."
- cr30_b1_02_magnet_window_{dark,light}(+fullscreen): the magnet window
  renders, legible both themes, buttons "Stop the measurement" /
  "Recalibrate now". Nits: `setWindowTitle` text does not appear (macOS
  QMessageBox has no title bar text — cosmetic); the {reason} tail repeats
  the body's STOP/RECALIBRATE advice, so the window says everything twice.
- cr30_b1_03/04: the recal white window after "Recalibrate now", and the main
  window after the false "Carrying on".

## W3 — CONFIRMED, test bug, 2-line fix
tests/test_run_delete.py:205 and :398 assert the literal "Trash"; the branch
made the app say `trash_name()` (core/trash.py:97 — "Trash"/"Recycle Bin"/
"Wastebasket", and translated). Right assertion: import `trash_name()` and
assert THAT in the body — identical on macOS, correct on Windows/Linux.
Fix for beta 1: it is 2 lines and removes 2 of the 3 branch-only Windows
failures.

## W6 — confirmed; a warn-only mtime check is right, refusal is not
helper_path() (workflow/chartread_engine.py:27-50) prefers the dev build on
existence alone. Freshness = dev binary mtime vs newest source in
native/chartread_helper/ AND native/instlib/ (both are compiled in). WARN
loudly (log + UI log pane), do not refuse: a fresh `git checkout` bumps
source mtimes and would brick a perfectly good build behind a hard refusal.
Not a beta-1 gate — it protects developers, not users. Related and CHEAPER to
do now: tests/test_cr30_packaging.py:48-60 pins only b"CR30" in the committed
macOS Mach-O — after the W9 fix that test stays green on a binary WITHOUT the
fix. The W9 commit must ship a rebuilt native/chromiq-chartread, and the
stale-test should learn a new marker (or compare an embedded protocol/version
string) in the same commit.

## W5 — verified; the trap is real but currently unarmed; docs are enough for beta 1
- The button (ui/dialogs/settings_dialog.py:143 → core/usb_driver_installer.py)
  installs WinUSB via wdi-simple keyed on KNOWN_COLORIMETERS (:36-73).
  1a86:7523 is NOT in the table → today the button cannot touch the CR30. The
  "would destroy the COM port" hazard arms only if someone adds the CR30 to
  that table — the module's own exclusion note (:26-29, HID devices) is the
  precedent to extend: vendor-serial devices are a THIRD class needing a
  SECOND mechanism (`pnputil /add-driver` of WCH's signed package), never the
  WinUSB swap. Also mind `launch_zadig()` (:236): the dialog's Zadig fallback
  can WinUSB the CH34x by USER action once CR30 users are steered there.
- What ChromIQ can honestly distinguish on Windows, separably:
  (a) no PnP device with VID_1A86&PID_7523 at all → truly absent;
  (b) the enum key exists but no COM port / a problem code → "connected, but
  Windows has no working driver" — detectable with the same winreg walk
  enumerate_connected() already does, no new dependency;
  (c) a port that opens but does not answer → only separable once the app
  path calls identify() after open (23_live L4 MAJOR 3 — still unbuilt);
  (d) helper refuses the chart → already its own event (chart_refused).
  Each deserves different words; (b) is the cheap, high-value one.
- For beta 1: the 24_windows stopgap changelog section is accurate (its own
  verified/not-verified table is honest) and sufficient. The button extension
  is a Windows-only design change touching §M — Basti's call, after beta 1.

## THE GATE QUESTION
The rule (CLAUDE.md): "Any merge/release decision requires a green --runslow
run" — it names no platform. Precedent: every release to date was gated on
macOS only; 24_windows is the FIRST Windows suite run in the project's
history, and master (3fd11afd, = v4.1.4's lineage) fails 69 of the same tests
there — meaning 4.1.4 shipped, green-gated, with those failures latent. So
"green gate" has only ever meant: green on the platform that cuts the
release, macOS. Reading it as "green on all platforms" would retroactively
un-release 4.1.4 and block this beta on pre-existing font-metric tests that
have nothing to do with #159 — that is a separate work item.
The honest bar for 4.1.5 BETA 1:
1. Green --runslow on macOS at the tag commit (it is green at 583dd306:
   8111/141/3).
2. The 3 branch-only Windows failures reduced to 1: fix W3 (2 lines); W4
   ships open, named in the notes (cosmetic, Windows font metrics, ground
   already soft on master).
3. The 69 pre-existing Windows failures named in the release notes as known
   platform noise, with 24_windows as the reference — NOT silently absorbed.
4. No claim in the changelog that the code does not honour: the BLE
   "calibration is faster" claim (6ddae691) is currently FALSE and must be
   either fixed-for-real or struck.
5. The magnet "Recalibrate now" path must actually resume (blocker above) —
   the beta's headline safety fix otherwise dead-ends its only user.

## STATUS: COMPLETE — ranked verdict in the final message.
