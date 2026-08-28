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


## Section 2 — partial measurement. The `.ti3` is safe; **"Save and stop" is not.**

The user will read about five patches of 390 and stop. Everything below was
measured against the **real** `native/chartread_helper/build/chromiq-chartread`
over the `-xx` JSON channel, with no hardware.

### 2.1 ✅ The good news, proved: the partial `.ti3` is correct and complete

| question | answer | how |
|---|---|---|
| does the `.ti3` hold the 5 patches? | **yes** — `NUMBER_OF_SETS 5`, one row per read patch, no placeholder rows | `/tmp/p1.py` |
| when is it written? | after **every** patch — `cq_write_ti3_atomic()` runs on the same line as `cq_emit_patch_read` (`chromiq_chartread.c:3178-3179`), and a `{"event":"saved","path":"n.ti3","read_patches":5}` follows | observed |
| is a killed session's file worse than a finished one? | **no — byte-identical.** A 90-patch autosave file and the same run's `save_ti3()` output after `done` `diff` clean | `/tmp/p5.py` |
| is it honest about the instrument? | yes: `TARGET_INSTRUMENT "CR30"`, `COLOR_REP "iRGB_XYZ"`, no `SPECTRAL_*` | observed |
| does "done with unread patches" work over JSON? | **yes** — `{"cmd":"done"}` → `{"event":"unread_confirm","id":…,"loc":…}` → `{"cmd":"yes"}` → `{"event":"done"}`, exit 0 | `/tmp/p1.py` |
| is the run resumable? | **yes** — relaunching with `-r` re-offers `A4`, i.e. the first unread patch, and `session_start` reports the read strips | `/tmp/p9.py` |
| does relaunching *without* `-r` destroy it? | not on startup — the file is only rewritten when a patch is read | `/tmp/p9.py` |

**So no reading is ever lost, and none is invented.** That part of #159 is sound.

### 2.2 🔴 BLOCKER — "Save and stop" cannot end a CR30 measurement

The path the user will take. `_on_stop` → `_confirm_end_of_session(END_STOP)` →
**Save and stop** → `_end_session("save")` → `MeasureManager.send_save_partial_
and_quit()` (`workflow/measure_manager.py:874-915`), which on the engine is the
**two-`q` protocol**: send `q`, wait for the give-up prompt, send `q` again —
*"the second answers the give-up prompt, and THAT is what makes chartread write
the .ti3 and exit."*

**On `-xx` that give-up prompt does not exist.** It is printed at
`chromiq_chartread.c:2916-2918` inside `else if ((rv & inst_mask) ==
inst_user_abort)` — a branch reached only from `it->read_sample`, i.e. only when
an instrument is open. Under `-x` there is no `it`. `q` instead lands on
`chromiq_chartread.c:3049-3062`, which emits **`abort_confirm`** and blocks on
its own y/n.

Measured against the real binary (`/tmp/p7.py`), after three patches:

```
-- first 'q'   -> events: [... 'spot_ready', 'abort_confirm']   alive: True
-- second 'q'  -> alive: True    events: [..., 'spot_ready', 'abort_confirm']
   spot_ready locs: ['A1','A2','A3','A4','A4']
```

and confirmed against the **real `MeasureManager`** fed the real helper's lines
(`/tmp/p8.py`):

```
send_save_partial_and_quit()  ->  commands sent: [{'cmd': 'quit'}]
                                  state: wait_give_up_prompt
after the helper answered:        signals: ['abort_confirm']
                                  commands sent: [{'cmd': 'quit'}]     <- still ONE
                                  _save_partial_state: wait_give_up_prompt
```

`_save_partial_state` is stuck at `wait_give_up_prompt` **for ever**: nothing
clears it, the second `q` never goes out, and the helper never exits.

What the user then sees, from `ui/tabs/tab_measure.py:7027-7104`: the
`abort_confirm` signal opens **"Confirm Abort" — "Stop measuring?"**, a *second*
window immediately after he answered the first one. And clicking **"Yes — Stop"**
does this:

```python
self._send_failure_choice("n")                                  # :7099
self._end_session(self._confirm_end_of_session(self.END_ABORT_KEY))   # :7100
```

→ `_confirm_end_of_session` → **"Keep what you have measured so far?"** again →
Save and stop → `send_save_partial_and_quit()` → `q` → `abort_confirm` → …

**A closed loop of two dialogs with no exit but "Discard and stop."**

*(For an i1Pro reading patch-by-patch this works, because there `q` arrives
through the ui-callback during `read_sample`, produces "Spot read stopped at
user request!" and the `strip_interrupted` event, and
`measure_manager.py:1716-1722` sends the second key. `-x` never runs
`read_sample`. So this is **CR30-specific in effect**, even though the shape
lives in shared code.)*

**Rank: BLOCKER, CR30-specific.** Fix: on the external-values path
`send_save_partial_and_quit` must answer `abort_confirm` with `{"cmd":"yes"}` —
which exits cleanly and leaves the autosaved `.ti3` in place (measured: exit 0,
`NUMBER_OF_SETS 3` intact, `/tmp/p2.py` §P3) — or the helper must emit
`strip_interrupted` on the `-x` quit path so the existing chain completes.
Either way `_save_partial_state` must be cleared when `abort_confirm` arrives,
so the state cannot wedge.

### 2.3 🟠 SERIOUS — every answer to a y/n prompt leaves a ghost line that
### silently moves the patch pointer

`cq_handle_line` (`chromiq_json.c:236-269`) sets the pending **key** *and*
mirrors the same character onto the **`-x` line queue**, unconditionally. The
prompts (`cq_prompt_char` → `cq_wait_char`, `chromiq_json.c:328-341`) consume
only the key. **The mirrored line stays in the FIFO and is eaten by the next
`cq_wait_line`.**

Measured (`/tmp/p2.py` §P2 and `/tmp/p7.py`):

* `{"cmd":"done"}` → `unread_confirm` → `{"cmd":"no"}` →
  `spot locs after 'no': ['A4', 'A5']`. The user said *"no, I am not finished"*
  and the helper **skipped to the next unread patch** — because the ghost `"n"`
  line is `-x`'s *next-unread* command.
* the same for the tab's `_send_failure_choice("n")` at `abort_confirm`
  (`/tmp/p7.py`): `['A1','A2','A3','A4','A4','A4','A5']`.

Why it matters on a CR30 specifically: the operator is standing over a physical
patch. If the pointer moves without him asking, `Cr30MeasureBridge` faithfully
answers the *new* `loc` with the reading of the patch he is actually on. The
bridge's `on_patch_measured` pairing check **cannot see this** — the helper's
`loc` and the answered `loc` agree; it is the *paper* that disagrees. The only
warning is the preview highlight moving, which the user is not looking at while
he is reading a patch.

**Rank: SERIOUS, CR30-specific in consequence.** Fix, C side: `cq_wait_char`
should also drain the matching line, or the mirror should not be queued for the
keys that only ever answer a prompt (`y`, `n`, `s`, and `\x1b`/`q` when a
confirm is open).

### 2.4 🟡 MINOR — a partial CR30 read is reported as a **whole strip read**

`session_start` after resume reports `{"strip":"A", …, "read":true}` with only
3 of that pass's 15 patches read (`/tmp/p9.py`). The flag is "has any reading",
which is right for a strip reader and meaningless on a hexagonal 26×15 CR30
chart. It drives `_update_engine_read_map` → `set_stripe_read_map`, so the
preview will show a "read" pass the user has barely touched.

### 2.5 🟠 SERIOUS — nothing stops him building a profile from five patches
### (pre-existing, but #159 is what makes it likely)

There is no completeness check anywhere: the tests are all
`_cgats_has_no_readings` / `has_any_readings` (`tab_measure.py:833`,
`workflow/measurement_state.py:198`) — *any* reading makes the run "measured".
With the 5-patch `.ti3` produced above, ArgyllCMS says:

```
$ colprof -v -ql -aX n
colprof: Error - 65539, set_icxLuLut: can't handle test points without a white patch
```

and with the default quality/algorithm the first refusal is *"Output profile can
only be a cLUT algorithm"*. Both are raw Argyll text with no ChromIQ sentence in
front of them. **This is exactly what the user's session ends in**: five patches,
then Build Profile.

**Pre-existing** — any instrument can produce a two-patch `.ti3` — but until #159
no workflow encouraged stopping after five patches, and this one does.


## Section 3 — the three things he asked for that are not built

Reported as gaps with a plan, **not built**, as instructed.

### 3.1 (a) The calibration-first flow — first window offers **Calibrate**

**State: nothing exists.** `grep -rn 'calibration_prompt' ui workflow` shows the
signal is raised only from Argyll's JSON protocol, and under `-xx`
`cq_handle_calibrate` is inside `if (xtern == 0)` so it can never fire. The
first — and only — window a CR30 user sees is
`_show_cr30_measuring_window` (`tab_measure.py:6883`), whose button is
**"Start measuring"**, and it is opened *after*
`self._manager.start(...)` and `_open_cr30_bridge()` have already run
(`:5657-5666`). Design `02-design.md` §10.2 specifies a four-step
cap-on → verify → cap-off → verify flow before the first patch. None of it is
written.

**Worse than absent — the window that does exist makes a promise ChromIQ does
not keep.** `patch_measurement_instructions_html("cr30")`
(`ui/ti2_loader.py:305-314`) tells the user:

> *"…press the button on the instrument. **ChromIQ collects the reading by
> itself and moves on to the next patch** — there is nothing to press on
> screen…"*

Section 1.1 is precisely that nothing is listening for the press. The one
sentence a tester will trust is the one that is false.

#### The `EXP-MEAS-004` fork, and what the flow should be in each outcome

`/Users/Basti/develop/chromiq-cr30-research/tools/probe_host_calibration.py`
exists and is unrun. Its discriminator: present the cap's **green** face, send
**only** a host trigger, then measure paper — a reading far above 100 %R means
the host trigger performed the calibration write.

**If EXP-MEAS-004 says YES (the host can calibrate):**

1. Measure tab, CR30 chart, before Start: the primary button is **Calibrate**,
   Start is disabled with the reason on its tooltip.
2. Calibrate opens one window: *"Put the cap on with the white tile facing the
   aperture and seat it until the magnet clicks."* + **Calibrate now**.
3. ChromIQ sends `trigger_frame()` itself (`usb_measure.trigger`) — **USB only;
   `CR30.trigger_unsafe` raises `NotImplementedError` on BLE**
   (`device.py:113-116`), so over Bluetooth this branch does not exist and the
   NO plan below is the only one.
4. Read stored, `validate()` **without** `check_usable`, and require the
   tile shape: flat, high, and — the real prize of §10.3 — **store it as this
   unit's `TILE_SIGNATURE`** for the rest of the session, which is what makes
   the magnet guard work on a unit that is not ours.
5. *"Take the cap off."* Read again; require it is **not** the stored constant.
6. Start becomes enabled. Record `calibrated: true` + the captured constant in
   `meta.json`.

**If EXP-MEAS-004 says NO (only the button calibrates):**

Identical, except step 3 becomes *"…and press the button on the instrument"*,
and ChromIQ **waits** for the new reading — over USB with
`wait_for_button_header` (which is what §1.3 needs anyway); over BLE by polling
until the stored reading changes. The window carries a **Cancel**, because a
user who cannot make the device co-operate must be able to get out.

**Either way the same three things must hold**, and they are the parts to get
right first because they are outcome-independent:

* the calibration reading is taken through a path that does **not** go through
  the chart-read bridge (see 3.2);
* the captured tile constant is kept for the session (§10.3's real gain);
* **Skip is offered in Manual only, never Guided**, per §10.2, with the warning
  that an uncalibrated instrument produces a profile that looks correct and is
  not.

### 3.2 (b) The calibration reading must not be counted as a measurement

**State: not built, and the current architecture would count it.** There is
exactly one reader (`DeviceReader`) and exactly one consumer
(`Cr30MeasureBridge`), and every reading the bridge accepts is sent as
`{"cmd":"value"}` for whatever `loc` is outstanding. A calibration reading taken
while a chart session is running would be answered into the chart.

Three consequences that must be designed for, not discovered:

1. **`CR30._previous` is shared.** `check_usable(self._previous)`
   (`device.py:142, 198`) compares against *the last reading this device object
   took*, whoever asked for it. Calibrate immediately before the first patch and
   the first patch's read is bit-identical to the tile reading → rejected → and
   by §1.4 the session is then stuck before it starts. **The calibration flow
   as specified will break the chart read unless `_previous` is handled.**
2. `_awaiting_loc` must be `None` throughout calibration. `Cr30MeasureBridge.stop()`
   is one-way (`:240-243`) — there is no `pause`. Cleanest: do calibration
   **before** `MeasureManager.start`, so no session exists.
3. Nothing must reach the `.ti3`: `cq_write_ti3_atomic` runs on `patch_read`
   only, so as long as no `{"cmd":"value"}` goes out, nothing does.

**Recommended shape:** calibration owns its own `DeviceReader` call path (or a
`reader.calibrate()` that bypasses `check_usable` and does **not** update
`_previous`), and it runs **before** the helper is launched. Then (b) is true by
construction rather than by a flag.

### 3.3 (c) BLE reconnection (§10.1)

**State: not built.** A drop surfaces as one `read_failed(loc, message)` and,
per §1.4, the session then stalls with no reconnect, no pause, no backoff and no
message that names Bluetooth. §10.1's five points map to nothing in the tree.

What the current code gives §10.1 for free, and what it does not:

| §10.1 | today |
|---|---|
| 1. pause, do not end, and show the count | ✗ — no pause state exists |
| 2. backoff 1/2/4/5 s, Stop always available, 60 s message change | ✗ — nothing retries at all |
| 3. nothing read is at risk | ✅ **true and measured** (§2.1) |
| 4. the stale-reading trap is caught by the bit-identical guard | ✅ the guard is live … |
| | ⚠ … but it is *also* the thing that makes every second read fail today (§1.1), so a reconnection design must not be built on top of the current reader |
| 5. say that USB is more robust for a long chart | ✗ — nothing mentions the transport anywhere in the UI |

There is also **no way to choose or remember a unit**: `DeviceReader()` is
constructed bare (`tab_measure.py:6809`), so `transport="auto"`, `port=None`,
`address=None`. `CR30.discover_ble` (`device.py:46-51`) exists as a chooser API
and has no caller. Reconnection wants a remembered address — otherwise every
reconnect re-runs a 12 s scan with a connect-and-verify per candidate.

**Prerequisite ordering.** (c) should not be attempted before §1.3 (a reader
that waits and can be cancelled) and §1.4 (a retry path). Reconnection is a
*retry policy*; there is nothing to hang it on yet.


## Section 4 — report 09's open list, verified and ranked

**A real CR30 turned out to be attached to this machine** (`/dev/cu.usbserial-10`;
`identify()` → `model='CR30', device_id='PT694D01E7', version 'V11.3.'`), so
several items that 09 could only reason about are now **measured on hardware**.
Nothing was ever sent to it but `read_stored`, which sends **no trigger** and
cannot cause a calibration write (`usb_measure.py:22-25, 171-179`).

| 09's item | verdict | rank |
|---|---|---|
| 1. `M-CR30-READ-ENDED` is a log line, not a window | real, and correct as it stands | MINOR |
| 2. `DeviceReader` has never met hardware | **it has now, and it fails** — §1 is hardware-confirmed | **BLOCKER** |
| 3. calibration flow not built | real | **BLOCKER for a useful beta** (§3.1) |
| 4. BLE reconnection not built | real | SERIOUS (§3.3) |
| 5. C-before-B ordering | not a defect | — |
| 6. F13 no-instrument window | still unreachable under `-x`; unchanged | MINOR |
| 7. F14 `_saw_instrument` dead | confirmed dead: set at `:1083`, `:4582`, `:5686`, read nowhere | MINOR |
| 8. the one-off write into the real `~/ChromIQ` | **09's guess is wrong — see 4.2** | SERIOUS |
| 9. `-p` under `-x` | deliberate and correct | — |

### 4.1 Item 2 — measured on the attached unit

```
$ python /tmp/hw.py
opened over usb in 0.02s
identify: Identity(model='CR30', device_id='PT694D01E7', … version_a='V11.3.')
read 0: 0.00s mean 81.198%R peak 89.642 gate=None axis=ASSUMED 400/31/10 -- no header was fetched
     XYZ: [77.634, 80.7851, 70.5674] tile? False
read 1: 0.00s RAISED: reading is bit-identical to the previous one. …
read 2: 0.00s RAISED: reading is bit-identical to the previous one. …
two unenforced reads 1s apart identical: True
```

* **`read_measurement()` returns in 0.00 s.** It does not wait for anything.
* The second and third reads raise. Exactly §1.2.
* `gate=None` and `axis=ASSUMED 400/31/10 — no header was fetched`: §1.3's two
  side-effects are live on this unit.
* `tile? False` — the stale reading is *not* the tile constant, so even the
  unit-specific tile check would not have caught it.

**And then the real app did it, on his real project.** Driving the real
`MainWindow` on a **copy** of `~/ChromIQ/CR30-Test` (offscreen, sandboxed
settings — the real folder was never touched), pressing **Start** on the Measure
tab produced, in the tab's own log:

```
Ready to read patch '384' at 'A1'
 Got XYZ value 77.633986 80.785143 70.567372
Ready to read patch '103' at 'A2'
The CR30 could not be read for patch A2: reading is bit-identical to the
previous one. … Press the button on the instrument again.
```

and wrote this `.ti3`:

```
NUMBER_OF_SETS 1
384 "A1" 81.59335 56.76003 87.60663 77.63399 80.78514 70.56737
```

Patch A1's device value is RGB **(81.6, 56.8, 87.6)** — a saturated lavender,
expected XYZ `49.997 39.551 75.274`, **Lab (69.2, +34.7, −47.2)**. What was
recorded is the instrument's stale cache, **Lab (92.0, −0.5, −3.6)** — near-white
paper. **ΔE76 = 60.5**, written into the measurement file with no warning, no
event, and no way for anything downstream to tell.

The helper did not catch it either: its plausibility gate is `WERR_TH 95.0`
(`chromiq_chartread.c:71`), and 60.5 sails through.

**Nothing about this needed Bluetooth, a flaky cable or bad luck. It is what
happens every time.**

### 4.2 Item 8 — the mystery write is explained, and 09's guess was wrong

09 recorded a write into `~/ChromIQ/CR30-Test/runs/run1/meta.json` at 21:00:58,
copied both files to `/tmp/chromiq-meta-backup/`, and concluded *"the likeliest
explanation is that Basti's own app touched his own project"*.

**The backed-up copy settles it, and it is the other way round.** Diffing the
21:03 backup against the live file:

```
-   "value": "i1"          +   "value": "CR30"        (printtarg -i)
-   "value": 0             +   "value": 390           (targen -f  — the patch count)
-   "engine_on": false     +   "engine_on": true
-   "dpi": 72,             +   "dpi": 300,
-   "seed": null,          +   "seed": 1800742635,
-   "hflag": false,        +   "hflag": true,
-   "layout_mode": "area_first"  + "patch_first"
    … 14 more, all of the same kind
```

The **backup is the damaged version**. It cannot be a state this project was
ever in: `targen -f = 0` and `dpi 72` cannot have produced the 390-patch,
300 dpi, hexagonal chart that was generated at 20:14 and whose `.ti2` carries
`RANDOM_START "1800742635"` — the seed the *live* file holds and the backup does
not. So at 21:00:58 the run's stored Create Chart recipe was **replaced by an
unpopulated tab's defaults**, and something put the right values back at 21:05.

That is a **project-settings clobber**, the same shape as the two earlier ones,
and for four minutes the printed chart's recipe did not exist on disk. Had
anyone pressed Generate in that window, a different chart would have been built
over the one on paper.

**What I could and could not reproduce.** I drove the real `MainWindow` against a
copy, with `restore_last_session` on, for `active_tab` = Create Chart and
= Print Chart, then left the tab (the §3 W6 write):

* Create Chart: `md5` **unchanged**. `TabChart` reloads on the target change, so
  the ordering hazard I expected (`_load_settings_of_tab_entered` runs at
  `main_window.py:420`, `_restore_last_session` only at the following
  `singleShot(0)`, `:423`) does **not** bite for that tab.
* Print Chart: the file **was** rewritten, but benignly — `"print_settings": {}`
  → `{"intent": "relative", "route": "chromiq"}`.

**So the writer is still unidentified.** It is not the startup path, and it is
not (as 09 assumed) benign. Two practical consequences, both for the user:

1. **`/private/tmp` is swept nightly.** `/tmp/chromiq-meta-backup/` — the only
   copy of the damaged file, and the evidence — will be destroyed. It has been
   copied to `~/chromiq-cr30-test-backup-20260828-215034/`, together with the
   whole project and both `com.chromiq*.plist` files, before anything else in
   this session was done.
2. **Do not run the gate, or any driver, while his CR30-Test project matters.**
   The tripwire (`tests/conftest.py:552`) is what caught this; it only catches
   a stray **once** per name.

**Rank: SERIOUS, pre-existing (not #159's), and unresolved.**


## Section 5 — cross-tab and lifecycle after a partial CR30 measurement

Driven on the real app, offscreen, against a **copy** of `~/ChromIQ/CR30-Test`
carrying a realistic **5-of-390** CR30 `.ti3` (produced by answering the real
helper's first five prompts). `/tmp/drive_tabs.py`.

### 5.1 🟠 SERIOUS — Build Profile offers to build from five patches, silently

```
tab: 4. Build Profile
ti3 path: …/CR30-Test/runs/run1/CR30-Test.ti3          (NUMBER_OF_SETS 5)
  _build_btn: text='Build Profile' enabled=True
MODALS on entering: []
  visible labels mentioning patches: []
```

No window, no note, no disabled button. And the build cannot succeed:

```
$ colprof -v -ql -aX <that ti3>
colprof: Error - 65539, set_icxLuLut: can't handle test points without a white patch
```

This is §2.5 seen from the tab. **It is the last thing the user will do in his
session**, and what he will get is a raw ArgyllCMS sentence.

Minimum fix: compare the `.ti3`'s `NUMBER_OF_SETS` with the chart's
`NUMBER_OF_SETS` and say *"5 of 390 patches are measured — a profile needs the
whole chart"* before `colprof` is run. There is no completeness check anywhere
in the tree today (§2.5).

### 5.2 ✅ Check & Refine is inert and correct

`_ti3_path` and `_icc_path` are both `None` and no window opens — there is no
profile, so there is nothing to check. Nothing claims otherwise.

### 5.3 🟡 MINOR — the measurement report renders, and calls a lavender patch
### "paper white"

`measurement_report.build_report()` runs cleanly on a colorimetric-only CR30
`.ti3` (schema 7, `instrument: "CR30"`, `patches: 5`, ΔE00 mean 5.28) — the
colour side does not need spectra, which is the right answer for #159.

But the cube-corner block substitutes the nearest patch it has:

```
corners[0] = {"name": "W", "loc": "A1", "rgb": [81.6, 56.8, 87.6],
              "hex": "#c392fd", "present": false, …}
```

`present: false` is carried, so the data is honest; whether every *renderer* of
this block says so is the question, and a report that labels a lavender patch
"W" is exactly the kind of thing a tester reads as a fault in the instrument.
**Pre-existing** (any partial measurement does it), surfaced by #159.

### 5.4 ✅ A second run of the same target is clean

`Project.new_run` gives run2 its own folder, and §2.1 showed a relaunch does not
touch an existing `.ti3` until a patch is read. The cross-run isolation
CLAUDE.md describes holds; I found nothing CR30-specific here.

### 5.5 🟡 MINOR — "You have read **1 patches** in this session"

Observed verbatim in the driven run's ending window
(`ui/tabs/tab_measure.py:6013-6014`). CLAUDE.md's i18n rules are explicit:
*"Count-bearing messages get explicit singular/plural variants, never `(s)`."*
A CR30 session that ends after one patch is not a corner case — it is what
happens today (§1.2), and it is the **first** window the user will see.

### 5.6 🟠 SERIOUS — the helper is left running when the tab goes away

The driven run ended with:

```
QProcess: Destroyed while process ("…/chromiq-chartread") is still running.
```

That is §2.2 seen from the other end: the `-xx` helper never exits on `quit`, so
it outlives whatever kills the window. On a real quit this leaves an orphaned
`chromiq-chartread` holding the run folder. Combined with §1.8 (a `QThread`
destroyed while a read is in flight) the shutdown path for a CR30 measurement is
the least-tested part of the feature.


## Section 6 — what would waste his time or his paper

He has **one printed 390-patch hexagonal A4 sheet**. Taken from the real chart's
own `channels.json`:

| | |
|---|---|
| cells | 390 hexagons, **12.02 mm across the flats**, slot 10.33 mm (hexagon height 13.8 mm) |
| aperture clearance | 4 mm aperture in a 12 mm cell — **4 mm to the nearest edge**, as report 07 measured |
| patch area | x 13.5 … 199.6 mm, y 16.9 … 287.0 mm on 210 × 297 |
| first patch offered | `A1` = `.ti2` id **384**, RGB (81.6, 56.8, 87.6) — a saturated lavender |

**The paper itself is fine.** The geometry is measurable by this instrument, the
33 mm barrel overhangs the sheet edge by at most ~10 mm on a flat table, and
nothing in the layout makes a patch unreachable. I tried to find a reason the
sheet could not be read and could not.

**What can make a measurement silently wrong, ranked by how likely he is to
meet it:**

1. **Every reading is one patch late, and the first is not a reading at all**
   (§1.1, §4.1). Hardware-confirmed, ΔE76 = 60.5 on his own chart's A1. **This is
   certain, not probable.**
2. **A ghost line moves the patch pointer** after any y/n answer (§2.3). He
   answers "no, keep measuring", the pointer steps to the next patch, and the
   patch he then reads is filed under the wrong name. The bridge's pairing check
   cannot see it, because the helper and the bridge agree — the *paper* is what
   disagrees.
3. **"Save and stop" cannot end the session** (§2.2) — a two-dialog loop whose
   only exit is "Discard and stop".
4. **A single failed read ends the run** (§1.4), with the one escape (click
   another patch, then click back) undocumented — and the message telling him to
   press the instrument's button again, which does nothing.
5. **Build Profile is enabled on five patches** (§5.1) and fails in ArgyllCMS's
   words.
6. **The magnet hazard is unguarded on this path.** `gate_flag` is always `None`
   because the button header is never fetched (§4.1), and
   `looks_like_calibration_tile()` measured **False** against this unit's own
   cached reading — so of `check_usable`'s four guards, only *bit-identical* and
   the physical-range bound are actually live. If he seats the cap while the
   instrument is awake, the unit's white reference can be overwritten and
   **nothing here will say so** (`measurement.py:67-96` is explicit that the
   range bound is one-sided and cannot see a *deflating* mis-calibration).

**And one that costs nothing but is worth saying:** the how-to window promises
*"ChromIQ collects the reading by itself and moves on to the next patch — there
is nothing to press on screen"* (`ui/ti2_loader.py:305-314`). It is the one
sentence in the feature that is flatly untrue today, and it is shown to the user
**after** `MeasureManager.start` and `_open_cr30_bridge` have already run
(`tab_measure.py:5657-5666`), so the first patch's read has fired before he has
finished reading it.

