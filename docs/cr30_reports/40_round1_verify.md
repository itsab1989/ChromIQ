# 40 — Round 1 verification (CR30-R1B)

**Scope:** master @ `2c21d329` — commits `80966c4a` (quit fix, third attempt) and
`2c21d329` (B2-8 BLE refusal + BLE axis check), per the round-1 challenge brief.

**Status: COMPLETE.**

## Verdicts (filled as established)

| # | Area | Verdict |
|---|------|---------|
| 1 | Quit fix reaches `_mark_quit_on_the_measurement` on every quit path | **PROVEN** — window close behaviourally, Cmd-Q on the real app on screen; no bypassing exit path exists |
| 2 | Marking `_user_quit` at quit does not break quit-vs-stop | **PASS** — reset per session (:416); Stop paths set it themselves; straight-line closeEvent |
| 3 | §3b / M-TI3-EMPTY reconciliation still runs | **QUALIFIED** — yes for engine (QProcess) sessions; NO for stock PTY sessions, and never did (F2, pre-existing) |
| 4 | B2-8 retry cost / double probe writes | **PASS** — no retry when nothing advertises; doubling only in the rare stranger case, off the GUI thread (see answers) |
| 5 | B2-8 remembered-address branch vs refusal | **FAIL — F4**: bypasses refusal AND identify(); USB got the check, BLE did not; beta-1-poisoned addresses survive |
| 6 | BLE axis check vs variants / siblings | **PASS with known blind spot** — fail-safe on variants; siblings sharing the axis accepted as CR30 (recorded, defensible) |
| 7 | The tests test the production path | **MOSTLY** — real-window lookup test is genuine (mutation re-proven); ordering was source-only (closed here); no test for the remembered-BLE branch |
| 8 | Gate | **GREEN** — 8253 passed, 141 skipped, 3 xfailed, 1 warning, 171.75s (2:51), `--runslow -n auto`, run once, alone, at the end |

## Findings

(appended below as they are confirmed)

### F1 — `_engine_mode_fallback` relaunch has NO `_user_quit` guard (real, low likelihood)

`workflow/measure_manager.py:430` — the first branch of `_on_finish`:

    if (was_engine and self._engine_mode_fallback
            and not self._stock_reader_cannot_read):
        ...
        self._launch_stock(...)

The other three relaunch/refuse branches all consult `_user_quit`
(`_engine_should_fall_back` measure_manager.py:639, `_engine_should_resume_fallback`
:717, the #159 refusal :471). This one does not. If the user quits while the
helper is alive after emitting `{"event":"mode_fallback"}` (measure_manager.py:1350-1353)
— normally a sub-second window, but unbounded if the helper wedges instead of
exiting — `closeEvent` → `cleanup()` kills the QProcess, `waitForFinished`
delivers `_on_finish(9)` synchronously, and this branch relaunches stock
chartread **during shutdown**: exactly the orphan-relaunch the fix was written
to kill, alive in the one branch without the guard. Fix is one `and not
self._user_quit`. (Same class as the bug fixed; evidence: code cited above,
no assumption beyond Qt's documented synchronous `waitForFinished` delivery,
which the commit itself relies on.)

### F2 — "the finish handler still runs and still reconciles" is true ONLY for engine (QProcess) sessions

`core/argyll_runner.py::cleanup` disconnects `self._pty_done` (line ~534)
**before** killing `self._pty_proc`, and PTY completion is delivered only via
`_pty_done` → `_on_pty_finished` (emit at :773/:786/:859; sole connection made
at :333 and severed by the blanket `sig.disconnect()`). There is no
`waitForFinished` on the PTY path. So for a **stock-chartread session (PTY,
`use_pty=True`, measure_manager.py:541)** the per-run finish handler — and with
it the §3b / M-TI3-EMPTY reconciliation (`_finish_session_guard`,
ui/tabs/tab_measure.py:10317) — does NOT run at quit. Only the **engine helper
session (QProcess pipes)** reconciles at quit, via
`_process.finished→_on_finished` (argyll_runner.py:402), a connection the
disconnect loop never touches.

This asymmetry is PRE-EXISTING (identical disconnects in `fa8c79c0`, before all
three attempts) — **not a regression of this commit** — but the new comment in
`cleanup()` ("THE SESSION'S FINISH HANDLER STILL RUNS FROM HERE, ON PURPOSE")
and the test file's docstring state it unqualified, and the brief's question
"does the reconciliation genuinely still run" must be answered: **for stock
chartread at quit it does not, and never did**. An empty `.ti3` from a
quit-killed stock session is caught later only by `_archive_empty_measurement`-
style checks on next open, not by the session guard. Recommend: qualify the
comment; decide whether PTY quit should reconcile (guard state is otherwise
left un-finished — `MeasurementSession.begin()` ran, `finish()` never does).

### F3 — closeEvent→mark ordering is still proven only by reading source

`test_the_window_can_actually_REACH_its_manager` genuinely runs the production
lookup (`win._mark_quit_on_the_measurement()`) on a real MainWindow — that part
is sound and I could not fault it. But whether **closeEvent calls it before
cleanup** is asserted by `inspect.getsource` string-position checks
(`test_close_event_still_calls_it`,
`test_the_window_says_so_before_it_kills_anything`) — the same instrument that
passed over three broken fixes this week. A behavioural version exists cheaply:
the fixture's own teardown already calls `win.close()`; assert on
`mgr._user_quit` after a real `close()` instead of (or besides) reading source.

### Minor M1 — closeEvent does slow teardown BEFORE marking the quit

`ui/main_window.py::closeEvent` runs `_save_settings_of_tab_left()`, geometry
writes, `hide()`, `shutdown_webengine()`, `_tab_print.shutdown()` before
`_mark_quit_on_the_measurement()`. If any of those spins the event loop (the
WebEngine drain is the suspect), a helper that dies at that instant delivers
its finish with `_user_quit` still False — the old warning, by race. Marking
the quit FIRST in closeEvent costs nothing and closes the window. (Inference:
depends on whether shutdown_webengine processes events — not proven here.)

### Could NOT fault (quit fix)
- The lookup names now resolve: `MainWindow._tab_measure` (ui/main_window.py:239),
  `TabMeasure._manager` (ui/tabs/tab_measure.py:899),
  `MeasureManager.note_app_quitting` (workflow/measure_manager.py:883). Verified
  against code, not docstrings.
- Exactly ONE MeasureManager exists (tab_measure.py:899 is the only
  construction); spot reads use SpotReadManager whose own dialog close handles
  quit — the single-target lookup is not missing a second manager.
- No code path exits the event loop without closeEvent: no
  `QApplication.quit()/exit()` calls anywhere in production code; language
  change is manual-restart; `_hard_exit` runs only after `app.exec()` returns.
- Marking `_user_quit` at quit cannot corrupt a later session: it is reset at
  session start (measure_manager.py:416), and between the mark and the kill
  closeEvent is straight-line code — no Stop path behaviour changes (Stop paths
  set the flag themselves at :771/:1021/:1564).

## On-screen and behavioural evidence (quit paths)

- **Window close, behavioural:** plain script (offscreen), real `MainWindow`
  from sandboxed settings, `mgr._user_quit = False`, then a genuine
  `win.close()` — `_user_quit` flipped True and `close()` returned True.
  Condition distinguishing this from a harness: the REAL `closeEvent` ran
  end-to-end (WebEngine shutdown, settings writes, `_runner.cleanup()`), not a
  re-implementation of the lookup. Exit code 0 of the probe is the record.
- **Cmd-Q, on the real app on screen:** launched `python main.py` (settings
  plist backed up first, restored byte-identical after, `cmp -s` verified),
  sent a real Cmd-Q via System Events to the running process (pid 1144). The
  app exited, and `~/Library/Logs/ChromIQ/chromiq.log` shows closeEvent's OWN
  write sequence — `window_maximized`/`window_fullscreen`/`active_tab`/
  `session_target_name`/`session_project_root` — followed by
  "ArgyllRunner: cleanup complete" (08:54:40). `_mark_quit_on_the_measurement()`
  sits between those writes and `cleanup()` in the source, so Cmd-Q reaches it.
  The macOS menu Quit item is this same Cocoa terminate path. There is no
  second MainWindow anywhere in the app (single construction in `main.py`).

## Findings — B2-8 / BLE (commit 2c21d329)

### F4 — the remembered BLE address bypasses BOTH the refusal AND identify(); USB got this check, BLE did not (the biggest gap this round)

`workflow/cr30/measure_bridge.py::_open_ble` (:658-668): the remembered branch
does `CR30.open_ble(address=remembered)` → `BleTransport.open()` takes
`target = self.address` and **never enters the confirmed-only block** — then
`_open_ble` returns the device with **no `identify()` call anywhere on the BLE
path** (verified: the only production `identify()` callers are device.py:154
inside `open_usb` and measure_bridge.py:719 inside `_open_usb`'s remembered
branch). `calibrate()` (measure_bridge.py:805-840) then writes calibration
frames to whatever answered at that address.

This is exactly the persisted-misfire scenario the commit message names as the
worse consequence — and it is still open. It is REACHABLE IN THE WILD: the
`or cands` fallback shipped in **v4.1.5-beta.1** (introduced in `1f40fe0d`,
`git tag --contains` confirms), so a stranger's address may already sit in
`cr30_ble_address` on a user's Mac; the fix removes the way NEW poison gets in
but never re-validates what beta 1 may have left behind, and each "successful"
open re-persists it (`_remember_address`, :629).

The USB twin was fixed in 408f25d7 for precisely this shape — `_open_usb`'s
remembered branch identifies, checks `is_cr30()`, closes and falls back
(measure_bridge.py:714-739), and `test_the_remembered_port_is_checked_the_same_way`
pins it. **No BLE equivalent exists, in code or tests.** The partial mitigation
that DOES exist: a gadget lacking the ffe1 characteristic fails
`start_notify` → exception → fall back to the (now refusing) scan. But the
ffe0/ffe1 HM-10 class — the commit's own threat model — passes that.

Fix shape: after a remembered-address `open_ble`, run `dev.identify()` (one
READ_MEASUREMENT exchange, the same axis check `discover(verify=True)` does);
on failure close, clear/overwrite the remembered key, fall back to the scan.

### Answers to the brief's B2-8 questions

- **Retry cost in the common no-device case: NONE.** The retry is gated
  `if not ok and cands:` (ble.py:213) — an empty scan skips it. Doubling
  happens only when something advertises ffe0 and none of it confirms:
  worst case ≈ 2 × (12 s scan + ~1.6 s/device probe) ≈ 27 s before the
  refusal. That path runs off the GUI thread (tab_measure.py:7185-7214 runs
  `reader.calibrate` in a QThread worker), so nothing freezes; the cost is a
  longer wait for an error message in a rare case. Acceptable.
- **Is discover(verify=True) safe to run twice?** It doubles the unsolicited
  READ_MEASUREMENT + up to 4 POLL writes to every unconfirmed ffe0 advertiser.
  For a real CR30 these are read-only (TRIGGER_UNSAFE is honoured; the probe
  never triggers or calibrates). For a stranger they are arbitrary UART bytes —
  but that exposure exists in the FIRST probe by design; the retry doubles a
  risk already accepted, bounded, and smaller than the old behaviour (adopting
  the stranger and then calibrating it). Defensible; noted, not a defect.
- **Is refusing correct when the user explicitly chose a device?** An explicit
  choice arrives as `address=` and bypasses the refusal entirely (ble.py:188,
  `target = self.address`), so the refusal never overrides a user's pick. The
  refusal applies only to auto-discovery, which is right.
- **Does the remembered branch bypass the refusal?** YES — see F4.

### F5 — BLE axis check (device.py:205-213): correct as far as evidence goes, with a documented blind spot

- A **genuine CR30 variant with a different axis**: the vendor's own brochure
  (already on record, docs/cr30_reports/36_generality_and_outreach.md:265-279)
  advertises no CR30 sub-variant with a different range/interval. If firmware
  ever reported one, ChromIQ now refuses WITH the observed axis in the message
  — fail-safe, and the message names what to fix. Right behaviour.
- **CR10/CR20 siblings**: all three share 400–700 nm / 10 nm (31 bands) per the
  same brochure, so a sibling that answers the same READ_MEASUREMENT frame is
  pronounced "CR30" and driven as one. That is acceptable: the acceptance test
  is exactly the capability the session needs (measurement header + spectral
  axis); a sibling that cannot serve spectra never produces the header and is
  refused. The residue is a possibly wrong model label in logs/UI — known,
  recorded, and the vendor has been asked (Job 3 draft). Not a blocker.
- The error message's range arithmetic (`400-550 nm` for 16 bands) is correct:
  start + step × (bands − 1).

## The tests (question 4)

- `test_the_window_can_actually_REACH_its_manager`: **exercises the production
  method** (`win._mark_quit_on_the_measurement()`) on a real MainWindow — not a
  re-implementation. Mutation re-proven here: re-applying the wrong name
  (`tab_measure`) fails exactly this test (1 failed, 7 passed), and the
  source-reading tests all pass over the broken code — the commit's claim is
  true. Gap: closeEvent→method ordering was only source-checked; my behavioural
  probe (above) closes it for window-close, and Cmd-Q is proven on screen.
  Recommend adding the `win.close()` assertion as a real test (F3).
- `fake_ble` in `test_bluetooth_does_not_greenlight_any_gadget.py`:
  monkeypatches `ble.discover` wholesale, so the tests prove `open()`'s
  selection/retry/refusal logic — the right unit — while `discover()`'s own
  verify loop remains proven only against real hardware. The fake `BleakClient`
  mirrors the installed bleak's constructor (`BleakClient(target, timeout=)`)
  and async connect/start_notify shapes. Adequate as evidence FOR open();
  it says nothing about discover() internals, and doesn't claim to.
  One test (`test_nothing_at_all_keeps_the_old_advice`) supplies a second
  empty round that the code never consumes — it cannot detect whether an empty
  scan is (pointlessly) retried; the code plainly skips it, but the test would
  pass either way. Cosmetic.
  The axis fixtures pack `>HBB` big-endian, matching `BleAxis.parse`
  (ble.py:148-151, `unpack_from(">H", hdr, 4)`, step/bands single bytes).
- **No test covers the remembered-address BLE branch** — consistent with F4
  being an un-fixed hole rather than an untested fix.
- Settle-rule enforcement (`test_every_test_here_that_resumes_also_settles`):
  mutation-probed twice. First probe removed the FIRST `h.settle()` occurrence
  in the file — which is inside the fixture's DOCSTRING — and the test stayed
  green: the probe had answered a question it wasn't asking (the recurring
  trap, caught this time). Second probe removed the real call on line 176:
  the enforcement test FAILED, naming the offender. So it does catch a new
  offender of the shape past offenders had. Known weaknesses, documented not
  faulted: (a) the literal string `h.settle()` in a comment inside a test body
  would pacify it; (b) triggers are literal (`bridge.rearm(` misses a
  differently-named receiver); (c) it polices one file only.


## Gate

`QT_QPA_PLATFORM=offscreen pytest --runslow -n auto`, run ONCE, alone, after all
probes were reverted (`git status` clean but this report):
**8253 passed, 141 skipped, 3 xfailed, 1 warning in 171.75s (0:02:51)** — the
same 8253/141/3 the commit under review reported. The one warning is a
PytestUnraisableExceptionWarning, present in the commit's runs too (it reported
"Gate green" at identical counts).

## ANSWER 1 — Does anything block tagging 4.1.5 beta 2?

Ranked. My judgement: **nothing here is a regression against beta 1 — every
finding is a gap the fixes did not reach, not damage they did** — so this is a
"fix-first or tag-with-eyes-open" list, and F4 is the only one I would not tag
past silently.

1. **F4 — the remembered BLE address is trusted blind** (measure_bridge.py:658-668).
   The fix's own problem statement ("the address is REMEMBERED, so one misfire
   persists, and the next frames written to that stranger are calibration
   commands") is still true for any address v4.1.5-beta.1 already persisted,
   and for the branch generally. USB got exactly this check in the same review
   cycle; BLE did not. Small fix (identify-after-remembered-open + clear the
   key on failure), same shape as the USB one, testable the same way. **I would
   fix this before beta 2** — it is the stated point of B2-8.
2. **F1 — `_user_quit` missing from the `_engine_mode_fallback` branch**
   (measure_manager.py:430). One-line fix; the orphan-relaunch the quit fix
   was written to kill survives in this branch. Narrow window in practice —
   could ride to beta 3 if beta 2 must go out now, but it is a one-liner.
3. **F2 — reconciliation-at-quit never happens for stock PTY sessions**
   (pre-existing, not introduced here). Blocker only for the CLAIM, not the
   tag: the cleanup() comment and test docstring should stop saying the finish
   handler runs unqualified. Behavioural decision (should PTY quit reconcile?)
   can wait.
4. Not blockers: F3 (ordering test is source-shape; my behavioural probe
   passed), F5/siblings (recorded, defensible), M1 (theoretical race).

## ANSWER 2 — What did the implementer miss?

- **The persistence half of B2-8** (F4) — the commit fixed discovery and left
  the remembered branch, after writing in three places that the remembered
  branch is where the harm compounds. The USB/BLE asymmetry makes it an
  oversight rather than a decision: the same person added the USB remembered-
  port check hours earlier.
- **The fourth fallback branch** (F1) — three of four `_launch_stock`/refuse
  branches got the `_user_quit` guard; `_engine_mode_fallback` did not.
- **The PTY/QProcess asymmetry** (F2) — "the finish handler still runs" was
  verified on the engine path and asserted for both.
- And in my own probing, the same class of error the week kept producing: my
  first settle-rule mutation removed a DOCSTRING mention of `h.settle()` and
  reported the enforcement useless; only re-targeting the real call on line 176
  produced the true answer (it fails, naming the offender). The probe that
  finds its answer somewhere else remains the trap.

## What I could NOT fault

- The quit-fix lookup itself: every name resolves, proven on a real window and
  on the real app on screen (window close AND Cmd-Q); the mutation behaves
  exactly as the commit claims (1 real-window failure, 7 source tests blind).
- The `or cands` removal and the refusal logic: behaviourally tested at the
  right seam, no retry in the empty case, refusal message names what it saw,
  explicit user choice still honoured.
- The axis check: fail-safe on unknown axes, message arithmetic correct,
  endianness of code and fixtures consistent (`>H` both sides).
- The settle-rule enforcement: catches a genuinely removed settle.
- The gate: green at the commit's own numbers, reproduced independently.
- Tree hygiene: both commits touch only what their messages claim.
