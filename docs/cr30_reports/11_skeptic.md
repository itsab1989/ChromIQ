# 11 — SKEPTIC REVIEW (in progress)

Read-only review of the CR30 work on `feature/cr30-instrument-159`, against
Basti's session of 2026-08-28 22:10–22:14 (`11_EVIDENCE.md`).

Status: **IN PROGRESS** — findings appended as they are verified.

---

## S1 [BLOCKER] F3: the freeze is a `threading.Lock`, not a thread join — and `cancel()` is dead code

**CLAIM A is right about the 180 s and wrong about the mechanism.** The
implementer wrote "the quit path blocks on that thread ... which is inside its
180 s poll loop and is never cancelled". The blocking primitive is a
`threading.Lock` acquired on the **Qt main thread**:

- `workflow/cr30/measure_bridge.py:360` — the worker thread takes
  `DeviceReader._lock` and holds it for the whole of
  `read_next_measurement(timeout=180.0)` (line 364–365).
- `workflow/cr30/measure_bridge.py:377` — `DeviceReader.close()` starts with
  `with self._lock:`. Called from the main thread, it blocks until the worker's
  180 s deadline expires.
- `ui/tabs/tab_measure.py:6823–6834` — `_close_cr30_bridge()` calls
  `bridge.stop()` then `reader.close()`. **It never calls `reader.cancel()`.**
- `workflow/cr30/measure_bridge.py:240–243` — `Cr30MeasureBridge.stop()` sets
  `_stopped` and clears three locs. It does **not** touch the reader, does not
  cancel it, and does not quit or wait its worker threads.

**`DeviceReader.cancel()` (measure_bridge.py:369) has ZERO production callers.**
Verified repo-wide: the only call site is `tests/test_cr30_waits_for_the_button.py:113`.
So the `cancelled=` hook plumbed through `device.py:150` and `device.py:168` is
never armed in the shipping app. The test that "proves" cancellation works is
testing a path the app cannot reach — this is the classic *green test guarding
the bug*.

### The exact call chain, matched line-by-line against Basti's log

```
ui/main_window.py:2432  _save_settings_of_tab_left()      → 22:11:36,794 "measure settings written for run1"
ui/main_window.py:2437  saveGeometry                      → 22:11:36,794 window_geometry
ui/main_window.py:2447  active_tab / session_*            → 22:11:37,025
ui/main_window.py:2455  self._runner.cleanup()            → ENTERED 22:11:37,025
core/argyll_runner.py:520-521 _process.kill(); waitForFinished(2000)
                                                          → 22:11:37,026 "finished with code 9"
                        (nested) MeasureManager.on_finished → 22:11:37,027 "not falling back"
                        (nested) TabMeasure._on_measure_done
ui/tabs/tab_measure.py:9065  self._close_cr30_bridge()    → *** 162 s BEACHBALL ***
                        reader.close() blocks on _lock until the worker's
                        deadline (22:11:19,339 + 180.0 = 22:14:19,339)
ui/tabs/tab_measure.py (rest of _on_measure_done)         → 22:14:19,872 …,889
core/argyll_runner.py:536 log "cleanup complete"          → 22:14:19,890
```

The resumed lines at 22:14:19,872–,889 are *exactly* the tail of
`_on_measure_done` (layout-engine settings restore, "Build Profile: measurement
follows the bar", `measurement report saved`, `measurement_finished` sound) —
which is only reachable **after** `_close_cr30_bridge()` returns. That pins the
block to `tab_measure.py:9065`, not to some other 180 s wait.

**There is no other 180 s timeout in the codebase.** Grepped `workflow/`, `ui/`,
`core/` for `180`; every other hit is colour maths (hue wrap, CIE tables,
0.1805 matrix coefficients). The arithmetic is not a coincidence.

### Aggravating detail the implementer did not mention

The whole of `_on_measure_done` ran **re-entrantly inside `QProcess.waitForFinished(2000)`**
(`core/argyll_runner.py:521`), which itself is inside `MainWindow.closeEvent`.
So a 162 s blocking lock acquisition happened inside a nested wait inside a
close event. `waitForFinished`'s own 2000 ms budget was blown by a factor of 81.
Any fix that only shortens `button_timeout_s` leaves this shape intact.

### Concrete failure scenario (reproducible without a 3-minute wait)

Start a CR30 patch-by-patch read, let it arm a patch, do **not** press the
instrument button, press ⌘Q. Beachball for `button_timeout_s` seconds minus the
elapsed wait. Same thing on the tab's own **Stop** button — `_on_stop` reaches
the same `_close_cr30_bridge`.

### Fix direction (not applied — read-only review)

1. `_close_cr30_bridge` must call `reader.cancel()` **before** `reader.close()`.
2. Better: `Cr30MeasureBridge.stop()` should cancel its reader itself, so every
   stop path gets it, not just the one that remembers.
3. `DeviceReader.close()` should not need the lock at all for the cancel case —
   set `_cancel`, then acquire with a bounded timeout and hard-close the
   transport if it is not granted.
4. `device.py:160` — `wait_for_button_header(..., timeout=min(left, 1.0))` means
   cancellation latency is up to 1 s on USB and `poll`=0.25 s on BLE. Acceptable.

## S2 [MINOR→MAJOR] `read_failed` fires after `stop()`

`workflow/cr30/measure_bridge.py:267–270` — `_on_read_failed` has **no
`_stopped` guard**, unlike `_on_reading` (line 276). After a user Stop, the
in-flight worker's cancellation/timeout error still reaches
`ui/tabs/tab_measure.py:6855`, which appends to `self._log` and flashes the
status bar with *"The CR30 could not be read for patch A4: cancelled while
waiting for the instrument's button. Press the button on the instrument
again."* — telling a user who just pressed Stop to press the instrument button.
On the quit path it is worse: the target widgets may be mid-teardown.

## S3 [MINOR] F4 confirmed — exit code 9 on a user quit is reported as an instrument failure

22:11:37,027 `workflow.measure_manager`: *"the chart's instrument is one stock
chartread cannot read (unknown error) — not falling back"*. Nothing failed; the
user quit. See section on measure_manager below (pending).

## S4 [REFUTED] "the app still is not really closed"

The log's **last line is 22:14:19,890 "ArgyllRunner: cleanup complete"** and
nothing follows. `main.py:371` exits via `os._exit`. There is no evidence of a
second hang; what Basti saw is consistent with one 162 s beachball on a window
that had already been `hide()`-den at `ui/main_window.py:2444` — the window
vanishes at 22:11:36.8 but the process does not exit until 22:14:19.9, so the
Dock icon stays bouncing/present for ~2.7 minutes with no window. That *looks*
exactly like "not really closed". Do not go hunting a second hang.
