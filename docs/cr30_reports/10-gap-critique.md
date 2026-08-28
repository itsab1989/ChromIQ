STATUS: in-progress

# 10 — CR30 (#159) gap critique: what is still broken or missing before the beta

**Agent:** CR30-GAP-CRITIC. Branch `feature/cr30-instrument-159`.
Mandate: find what is still broken or missing before the user spends
measurements discovering it. **Report only** — no production code or test
changed.

Sections are appended and committed as they finish. Rankings:
**BLOCKER / SERIOUS / MINOR**, each marked CR30-specific or pre-existing.

Starting point: `09-impl-measure.md`'s open list (items 1-9), plus the
end-to-end path, partial measurement, the three unbuilt features, cross-tab
lifecycle, and anything that could waste a printed chart.

---

## Section 1 — the end-to-end reading path. **It cannot survive patch two.**

### 1.1 🔴 BLOCKER — nothing ever waits for the operator's button press

This is the finding the whole session turns on, and it is not a subtlety: it is
the central premise of the spot workflow, and it is missing.

`DeviceReader.__call__` (`workflow/cr30/measure_bridge.py:340-347`) is:

```python
def __call__(self):
    with self._lock:
        if self._dev is None:
            self._dev = self._open()
        m = self._dev.read_measurement()
    return spectrum_to_xyz(m.values)
```

`CR30.read_measurement` (`workflow/cr30/device.py:120-144`) fetches the device's
**cached** reading and returns immediately. Its own docstring says so, and
`usb_measure.read_stored`'s says it louder
(`workflow/cr30/usb_measure.py:22-25`):

> *"**Reading the stored measurement does NOT require a trigger.** The device
> caches the last reading … so the spot workflow is: the operator presses the
> instrument's own button, we fetch the chunks."*

The half that fetches is built. **The half that waits for the press is not.**
The function that does it exists and is documented as *"the spot workflow's real
trigger"* — `usb_measure.wait_for_button_header` (`:74-82`) — and

```
$ grep -rn --include='*.py' 'wait_for_button_header' ui workflow tests scripts
workflow/cr30/device.py:131:   `usb_measure.wait_for_button_header()` as `button_header`.
```

is its **only** mention outside its own definition. Nothing calls it. `device.py`
is always called as `read_measurement()`, so `button_header` is always `None`.

### 1.2 What that produces, step by step, on the user's real chart

Modelled against the **real** `Cr30MeasureBridge` with a device object that has
the semantics `device.py` documents — one cached reading, replaced only by a
button press, `check_usable(previous)` on every read (`/tmp/p6.py`):

```
--- patch N11 prompt (operator has NOT yet pressed the button) ---
sent:   [{'cmd': 'value', 'xyz': '50.015000 50.015000 50.015000'}]   <- STALE
--- helper prompts the next patch; operator walks over and presses ---
failed: [('A2', 'reading is bit-identical to the previous one. …')]
after the button press, sent: []   failed: (unchanged)
bridge state: awaiting='A2' reading=None
```

1. **The first patch is answered with whatever the instrument last measured.**
   `CR30._previous` is `None` on a freshly-opened device, so `check_usable`'s
   only defence against a stale reading — `identical_to(previous)`
   (`measurement.py:196`) — cannot fire on the first patch of a run. Whatever is
   in the device (yesterday's last patch; the white tile from a calibration; a
   reading taken while the user was checking the instrument works) is written
   into the `.ti3` as patch **N11**, silently, with no event and no warning.
   `looks_like_calibration_tile` catches only the tile case, and only on the one
   unit `TILE_SIGNATURE` came from (`measurement.py:144-165` says so itself).
2. **Every patch after that fails.** The read is fired the instant `spot_ready`
   arrives — milliseconds after the previous value went out, long before a human
   can move a 33 mm barrel to the next patch and press. The device still holds
   the same cached bits, `identical_to(previous)` fires, and the read raises.
3. **Nothing retries.** `_on_read_failed` (`:267-270`) clears `_reading_loc` and
   emits. A read is only ever started from `on_patch_ready` (`:214`), and no
   further `spot_ready` will arrive — the helper is blocked in `cq_wait_line`
   (`native/chartread_helper/chromiq_json.c:343-359`, a 20 ms poll with **no
   timeout**) waiting for a value that is never coming.

The user is told (`ui/tabs/tab_measure.py:6855-6857`):

> *"The CR30 could not be read for patch {loc}: … **Press the button on the
> instrument again.**"*

Pressing the button does nothing. There is no code path that notices it. The
session is dead at patch two, with one wrong colour already in the `.ti3` and
a message telling him to keep pressing.

**Rank: BLOCKER. CR30-specific.** This is the whole session.

### 1.3 What the fix has to be (not built here — reported)

The reader must *block until a new reading exists*, on the worker thread, with
a cancel:

* **USB — the mechanism is already written.** `usb_measure.wait_for_button_header
  (transport, timeout=…)` returns the unsolicited `BB 01 09` frame the device
  emits **when the button is pressed** (VERIFIED 3/3 across EXP-MEAS-001/002/003
  per its docstring). Feed it to `read_measurement(button_header=frame)`. Doing
  so also fixes two things this path currently gets wrong for free: the
  **magnet-gate flag** becomes available (`usb_measure.py:56, 147-156`; today
  `gate_flag` is always `None`, so `check_usable`'s only *unit-independent*
  guard — the one `measurement.py:14-17` calls the one that works on the first
  reading — is switched off), and the **spectral axis is read from the device**
  instead of assumed (`usb_measure.py:136-140`, *"This was a live defect until
  2026-08-28"* — it is a live defect again, because ChromIQ never passes the
  header).
* **BLE — no equivalent frame is known** (`device.py:133-135`,
  TRANSPORT_BLE.md). The only available shape is **poll until the cached reading
  changes**: read, compare with the last one, sleep, repeat, until it differs or
  the user cancels. That is exactly `identical_to` used as a *wait condition*
  rather than as an error. It needs a cancel token, because a BLE `ask` is
  ~5 s (see 1.6) and a poll loop must be interruptible by Stop.

Either way, `read_failed` must offer a **retry**, and `on_patch_ready` must not
be the only thing that can start a read.

### 1.4 🟠 SERIOUS — a failed read ends the session with no way back

Independent of 1.1, and it will outlive that fix: **`read_failed` is a dead
end.** Any single device hiccup — a dropped BLE packet, a short serial read, a
`MeasurementError` from any of `check_usable`'s four guards — permanently stops
the run, because only a new `spot_ready` starts a read and only a command
produces a new `spot_ready`.

There is exactly one escape and it is undocumented: clicking another patch in
the preview sends `goto`, `note_goto` re-arms, the helper re-prompts and a read
starts. So "click a different patch, then click back" revives a stalled session
— and nothing tells the user that.

**Rank: SERIOUS, CR30-specific.** Minimum fix: a **Read again** affordance that
calls `bridge._start_read(bridge.awaiting_loc)`, or a `{"cmd":"ok"}` (which
re-emits `spot_ready` for the same patch — measured in report 08 §5.4 and
handled correctly by the `_reading_loc` latch).

### 1.5 🟠 SERIOUS — a device that disappears or never opens stalls the same way

`DeviceReader._open` runs lazily **inside the first read's worker thread**
(`:325-338`). Consequences:

* **Nothing tells the user ChromIQ is connecting.** Over BLE with no `address`
  remembered, `BleTransport.open` → `discover(timeout=min(20,12))` → a scan plus
  a *connect-and-verify* round trip **per candidate** (`ble.py:94-114`, 8 s
  connect timeout + ~1.6 s of polling each). The first patch can take tens of
  seconds with no window, no progress, no spinner, and no cancel.
* **If the open fails, the run is over.** The failure arrives as
  `read_failed(loc, <the whole multi-line `_no_device_help` text>)` — a nicely
  written eight-line paragraph, delivered into a one-line status flash and the
  log — and then nothing retries (1.4). `self._dev` stays `None`, so a *retry*
  would re-open correctly; there is just no retry.
* **A device that disappears mid-run** (unplugged, BLE drop, phone app grabs it)
  is the same: one `read_failed`, then silence. Design §10.1's reconnection is
  not built (report 09 open item 4) and this is what its absence looks like.

### 1.6 🟠 SERIOUS — over BLE, every read costs ~5 s, and it is spent before
### the user has even reached the patch

`BleTransport._ask` (`ble.py:216-230`) is `_drain()` — up to `3 × 0.4 s` — then
the write, then up to `10 × 0.35 s` of polling. **~1.2 s + ~3.5 s ≈ 4.7 s per
reading, floor.** Because the read starts on `spot_ready` rather than on the
button, that whole window is spent *before* the operator has placed the
instrument. It also sets the scale of 1.7 and 1.8 below.

### 1.7 🟠 SERIOUS — Stop can freeze the Qt main thread on the reader's lock

`_close_cr30_bridge` (`ui/tabs/tab_measure.py:6823-6834`) runs on the **main
thread** and calls `reader.close()`, which takes `DeviceReader._lock`
(`:349-351`). `__call__` holds that lock for the entire read (`:341-345`).
`bridge.stop()` on the line above sets flags only — it does not join anything.

So pressing **Stop** while a read is outstanding blocks the UI until the read
returns: **~5 s over BLE** (1.6), and over USB up to **15 s** if the device has
gone away (`read_stored` does three `transact`s at `timeout=5.0` each,
`usb_measure.py:142-145`). During that the window is unresponsive and macOS may
show the spinning wheel. A `bleak` disconnect then runs `run_until_complete` on
the main thread too (`ble.py:178-190`), adding more.

**Rank: SERIOUS, CR30-specific.** Fix: close the device on a worker, or make
`close()` non-blocking (a flag the read loop checks) rather than lock-held.

### 1.8 🟠 SERIOUS — quitting the app mid-read is a `QThread` destroyed while
### running

`_close_cr30_bridge` has exactly two callers: `_open_cr30_bridge` and
`_on_measure_done` (`:9065`). Neither is a `closeEvent`. The bridge is parented
to the tab and each `QThread` is parented to the bridge (`:248`), so quitting
ChromIQ while a read is in flight destroys a running `QThread` — Qt's
`Destroyed while thread is still running` → `std::terminate`. With a ~5 s BLE
read (1.6) that window is not small. `feedback_qthread_reference_lifetime` is
honoured *within* a run; it is not honoured across application shutdown.

### 1.9 ⚠ UNSETTLED — `bleak`'s loop is reused across a **new thread per patch**

Report 09 open item 2 names this and it is real: `_start_read` creates a fresh
`QThread` for **every** reading (`:246-260`), while `BleTransport._loop` is
created once, on the first of them, and reused by `run_until_complete` from all
the others (`ble.py:150-153`).

What I could settle without hardware: **plain asyncio is fine** — a loop created
in one thread and driven by `run_until_complete` from two later threads works on
this Python (3.14.6, verified). What I cannot settle: whether bleak's
CoreBluetooth backend, whose delegate callbacks are marshalled onto that loop
from Apple's dispatch queue, tolerates the loop's *running thread* changing 390
times. **The cheap way to make the question go away is to stop asking it**: one
long-lived reader thread with a queue, instead of one thread per patch. That is
also what 1.3's blocking wait wants, and what 1.7's non-blocking close wants.

### 1.10 What the bridge gets RIGHT, and should not be touched

Everything report 09 claims for the protocol layer holds up on reading, and two
of them I re-derived from the C source rather than the report:

* `cq_wait_line` (`chromiq_json.c:343-359`) genuinely blocks, so a value sent
  ahead of its prompt lands in a 16-deep FIFO **in order** — the `_awaiting_loc`
  latch is about *pairing*, not ordering, exactly as 09 says.
* `{"cmd":"ok"}`/`{"cmd":"retry"}` really do re-emit `spot_ready` for the same
  `loc`, and the `_reading_loc` latch really is the thing that stops three
  values going out for one patch.
* A jump's label travels on `cq_goto_target`, not on the line queue
  (`chromiq_chartread.c:2843-2852`), so `note_goto` before `goto_patch`
  (`tab_measure.py:11455-11462`) is the right order and is what it says it is.

