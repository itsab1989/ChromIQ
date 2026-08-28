# 11 — SKEPTIC REVIEW

Read-only critique of the CR30 work on `feature/cr30-instrument-159`, against
Basti's session of 2026-08-28 22:10–22:14 (`11_EVIDENCE.md`) and handovers #1–#4.

Status: **COMPLETE for this round** — see the final ranked summary at the end.

---

# PART 1 — F3, the beachball

## S1 [BLOCKER] The freeze is a `threading.Lock` on the main thread, and `cancel()` is DEAD CODE

**CLAIM A is right about the 180 s and wrong about the mechanism.** The claim
was "the quit path blocks on that thread … which is inside its 180 s poll loop
and is never cancelled". The blocking primitive is not a thread join — it is a
`threading.Lock` acquired on the **Qt main thread**:

- `workflow/cr30/measure_bridge.py:360` — the worker thread takes
  `DeviceReader._lock` and holds it for the whole of
  `read_next_measurement(timeout=self.button_timeout_s)` (lines 364–365).
- `workflow/cr30/measure_bridge.py:377` — `DeviceReader.close()` opens with
  `with self._lock:`. Called from the main thread it blocks until the worker's
  180 s deadline expires.
- `ui/tabs/tab_measure.py:6823–6834` — `_close_cr30_bridge()` calls
  `bridge.stop()` then `reader.close()`. **It never calls `reader.cancel()`.**
- `workflow/cr30/measure_bridge.py:240–243` — `Cr30MeasureBridge.stop()` sets
  `_stopped` and clears three locs. It does **not** touch the reader, does not
  cancel it, and does not quit or wait its worker threads.

**`DeviceReader.cancel()` (measure_bridge.py:369) has ZERO production callers.**
Verified repo-wide (`grep -rn "\.cancel()"`): the only caller is
`tests/test_cr30_waits_for_the_button.py:113`. The `cancelled=` hook plumbed
through `device.py:150` (USB) and `device.py:168` (BLE) is never armed in the
shipping app. The test that "proves" cancellation works exercises a path the
app cannot reach — *a green test guarding the bug*.

### The chain, matched line-by-line to the log

```
ui/main_window.py:2432  _save_settings_of_tab_left()  → 22:11:36,794 "measure settings written for run1"
ui/main_window.py:2437  saveGeometry                  → 22:11:36,794 window_geometry
ui/main_window.py:2447  active_tab / session_*        → 22:11:37,025
ui/main_window.py:2455  self._runner.cleanup()        → ENTERED ~22:11:37,025
core/argyll_runner.py:520-521  kill(); waitForFinished(2000)
                                              → 22:11:37,026 "finished with code 9"
   (nested) MeasureManager                    → 22:11:37,027 "not falling back"
   (nested) TabMeasure._on_measure_done
ui/tabs/tab_measure.py:9065  _close_cr30_bridge()     → *** 162 s BEACHBALL ***
        reader.close() blocks on _lock until the worker's deadline
        (22:11:19,339 + 180.0 = 22:14:19,339)
   rest of _on_measure_done                   → 22:14:19,872 … ,889
core/argyll_runner.py:536  "cleanup complete"         → 22:14:19,890
```

The lines that resume at 22:14:19,872–,889 are **exactly the tail of
`_on_measure_done`** — the layout-engine settings restore, `Build Profile:
measurement follows the bar`, `measurement report saved`,
`sound measurement_finished` — all of which are only reachable *after*
`_close_cr30_bridge()` returns. That pins the block to `tab_measure.py:9065`.

**There is no other 180 s timeout in the codebase.** Grepped `workflow/`, `ui/`,
`core/` for `180`; every other hit is colour maths (hue wrap, CIE tables, the
0.1805 matrix coefficient). The arithmetic is not a coincidence.

### Aggravating detail the implementer did not mention

The whole of `_on_measure_done` ran **re-entrantly inside
`QProcess.waitForFinished(2000)`** (`core/argyll_runner.py:521`), which is
itself inside `MainWindow.closeEvent`. A 162 s blocking lock acquisition
happened inside a nested wait inside a close event; `waitForFinished`'s own
2000 ms budget was overrun by a factor of 81. Any fix that only shortens
`button_timeout_s` leaves this shape intact — it just makes the beachball
shorter.

### Reproduction (no 3-minute wait needed to see the shape)

Start a CR30 patch-by-patch read, let it arm a patch, do **not** press the
instrument button, press ⌘Q. Beachball for `button_timeout_s` minus the elapsed
wait. The tab's own **Stop** reaches the same `_close_cr30_bridge`.

### Fix direction (not applied — read-only review)

1. `Cr30MeasureBridge.stop()` should cancel its reader itself, so **every** stop
   path gets it, not only the one that remembers to.
2. `DeviceReader.close()` must not need the lock for the cancel case: set
   `_cancel`, then acquire with a bounded timeout and hard-close the transport
   if it is not granted within, say, 2 s.
3. Cancellation latency after that is ≤1 s on USB (`device.py:160`,
   `timeout=min(left, 1.0)`) and ≤0.25 s on BLE (`poll`). Acceptable.
4. Consider whether `_close_cr30_bridge` should run on the quit path at all
   *before* the process is killed, rather than nested inside `cleanup()`.

## S2 [MAJOR] `read_failed` fires after `stop()` — the app tells a user who just quit to press the instrument button

`workflow/cr30/measure_bridge.py:267–270` — `_on_read_failed` has **no
`_stopped` guard**, unlike `_on_reading` (line 276, `if self._stopped: return`).
After a user Stop, the in-flight worker's cancellation/timeout error still
reaches `ui/tabs/tab_measure.py:6855`, which appends to `self._log` and flashes
the status bar with:

> "The CR30 could not be read for patch A4: cancelled while waiting for the
> instrument's button. Press the button on the instrument again."

Failure scenario: user presses Stop → sees an error naming a patch and telling
them to press a button on an instrument whose session has ended. On the **quit**
path it is worse — the target widgets are mid-teardown behind a hidden window.
Once S1 is fixed and `cancel()` actually fires, **this message will appear on
every single Stop**, so fixing S1 without fixing S2 turns a rare confusion into
a guaranteed one.

## S3 [MINOR] F4 confirmed — a clean user quit is reported as an instrument failure

`22:11:37,027 [WARNING] workflow.measure_manager: the chart's instrument is one
stock chartread cannot read (unknown error) — not falling back`. Nothing failed;
the user quit and the process was killed with exit code 9. "(unknown error)" is
the exit code being interpreted as a diagnosis.

## S4 [REFUTED] "the app still is not really closed"

The log's **last line is 22:14:19,890 "ArgyllRunner: cleanup complete"** and
nothing follows. `main.py:371` exits via `os._exit`. There is no evidence of a
second hang. What Basti saw is fully explained by S1: `ui/main_window.py:2444`
`self.hide()`s the window at 22:11:36.8, but the process does not exit until
22:14:19.9 — so for 2 m 43 s there is a live, beachballing ChromIQ in the Dock
with no window. That *is* "not really closed". **Do not go hunting a second
hang.**

Ruled out as second-hang candidates while verifying: no `atexit` hooks of our
own (`main.py:356` says so and `grep atexit` confirms), `os._exit` skips
interpreter finalisation, the PTY reader thread is joined with a 2 s timeout
(`argyll_runner.py:532–534`), and the QProcess is killed with a 2 s wait.

---

# PART 2 — F2, the missing split-patch overlay

## S5 [PROVEN INNOCENT] The preview's paint path works on Basti's exact chart

I did not take this on trust. Loading his real `CR30-Test.tif` into a real
`TiffPreview`, with the real per-patch geometry and hex mode on, then setting a
4-patch overlay and diffing the rendered pixmap:

```
current page 0 · overlay keys [0] · n items 4 · hex True
changed sampled pixels: 1414
```

And end-to-end through the real `TabMeasure` with his real files:

```
tiff_pages: [.../CR30-Test.tif]
patch_boxes pages: 1 [390]
locate A1: (0, QRect(159, 200, 142, 122))
chart_is_cr30: True · hex_zigzag: True
after ready:    active box QRect(159,200,142,122) page 0 current 0 spot_click_on True
after measured: overlay {0: 1} · info {0: 1}
```

So `patch_boxes_from_sidecar`, `_locate_patch`, `_on_patch_ready`,
`_on_patch_measured`, `set_patch_overlay` and `_draw_cq_overlay` all work on the
real artefacts. Independently reproduces the implementer's RESULT 1.

### Structural refutation of handover #1's candidate (b)

`ui/tabs/tab_measure.py:10589–10595`:

```python
for page, boxes in enumerate(self._patch_boxes):
    if loc in boxes:
        return page, boxes[loc]
return -1, None
```

`_locate_patch` returns either `(-1, None)` or `(page, <a QRect>)`. It **cannot**
return `page >= 0` with `box is None` unless the dict itself holds a `None`, and
`patch_boxes_from_sidecar` (tab_measure.py:418–423) only ever stores `QRect`.
So the "working indicator + silently missing overlay" asymmetry is **not
reachable through `_locate_patch`**. Candidate (b) is dead on the code, not just
on the probe.

### An exception in the slot is also refuted

PyQt6 routes an unhandled Python exception raised in a slot invoked from C++ to
`sys.excepthook` and then aborts the process. `main.py:21–29` installs
`_log_excepthook`, which logs `CRITICAL "Uncaught exception"`. Basti's log has
no such line **and the app kept running** — it read A2 and A3 after A1. So
`_on_patch_measured` did not raise.

### What that leaves — and what it does NOT leave

The highlighter ring and the split items are drawn by the **same function**
(`ui/tiff_preview.py:2323 _draw_cq_overlay`), from the **same page index**
(`self._current`), using boxes from the **same** `_patch_boxes` map. The ring is
at line 2620, the splits at 2504/2556. There is no gate that can turn one off
and leave the other on. **If Basti saw the ring, the overlay data was there and
the paint ran.** This is the crux the implementer has not yet explained, and it
is why I do not accept any explanation that only affects one of the two.

Remaining live candidates, none yet eliminated:
* the ring he saw was not `highlight_patch` at all (some other on-screen "which
  patch" indicator), in which case `_patch_boxes` was empty and BOTH failed;
* `_show_only_measured` was on — `ui/tiff_preview.py:2348` blanks every strip
  the `_stripe_read_map` does not mark read, and `_update_engine_read_map`
  (tab_measure.py:11467) is only fed from `_engine_strips`, which
  patch-by-patch never populates. That would blank the **whole chart to white**
  and leave three coloured patches in it;
* it drew and 3 patches out of 390 were not noticed (each patch is ~142×122 of
  2480×3508 image px — roughly 28×24 logical px at fit-to-window on a 900 px
  tall preview, so this is *unlikely* but not impossible for a pale patch).

**Open. Do not close it with a mechanism that would also have killed the ring.**

## S6 [MAJOR] `_try_load_tiffs`'s no-TIFF branch leaves the PREVIOUS chart's patch geometry in place

`ui/tabs/tab_measure.py:4324–4332` — when no TIFF matches, the else-branch
resets `_tiff_pages`, `_page_stripe_rects` and `_strips_per_page`, and clears
the preview. It does **not** reset `self._patch_boxes`. The same shape exists at
`_setup_stripe_rects`'s own guard, `tab_measure.py:4349` (`if not
self._tiff_pages: return`) — which returns *before* line 4356 assigns
`_patch_boxes`, again leaving the previous chart's map.

Failure scenario: load chart A (has TIFFs) → `_patch_boxes` = A's 390 boxes.
Load chart B in the same session with no TIFF alongside it → preview cleared,
but `_patch_boxes` still holds **A's** geometry. `_locate_patch("A1")` now
returns A's rectangle for B's patch. Nothing downstream re-checks. This is a
silent cross-chart geometry leak of exactly the class #159 is otherwise careful
about.

## S7 [MINOR] The overlay can vanish for one patch with no message at all

`ui/tabs/tab_measure.py:10633–10641` — when `_locate_patch` fails, the
explanatory log line is gated on `not any(self._patch_boxes)`. So the case "the
map is populated but **this** loc is missing from it" returns silently: no
overlay for that patch, no message, nothing in the log. Reachable whenever a
chart's `channels.json` `layout.patches` covers fewer patches than its `.ti2`
(a partial or regenerated layout). Independent of F2's root cause, and worth
fixing on its own: the user must never lose the overlay with zero explanation.

---

# PART 3 — F1 / CLAIM C, the calibration-first flow

Research facts below are cited from the separate repo
`/Users/Basti/develop/chromiq-cr30-research`.

## S8 [BLOCKER for the design] 11_EVIDENCE.md's calibration premise is FACTUALLY WRONG

> *"(d) … they'd calibrate against paper — F-evidence: paper reads 81 %R, white
> tile ~149 %R"*

That is backwards on both halves.

| quantity | value | cite |
|---|---|---|
| the white tile (`TILE_SIGNATURE`, our unit) | **78.93 %R mean** | `MEASUREMENT.md:554`, floats at `src/cr30/measurement.py:47-53` |
| a second CR30's tile | 76.70 %R mean | `MEASUREMENT.md:552-558` |
| plain paper, healthy calibration | **85.84 %R mean** | `CALIBRATION.md:69` |
| paper in EXP-MEAS-004 | 81.10 %R mean | `captures/raw/EXP-MEAS-004-host-calibration.json` |
| **149.10 %R** | the SAME PAPER re-measured after the white reference had been overwritten against the cap's **green** face | EXP-MEAS-004 `after` step |

So **paper reads HIGHER than the white tile**, and 149 %R is not the tile — it
is corrupted paper. Any threshold built on "the tile is bright, paper is dim" is
built on an inverted fact.

Worse for the plan: `src/cr30/measurement.py:75-87` records that the guard is
**one-sided**. Calibrating against a surface *brighter* than the tile (paper at
85.8 % vs tile at 78.9 %) makes every later reading ~8 % dark "forever, with no
symptom at all". The dangerous mistake is exactly the one that is invisible.

## S9 [BLOCKER for the design] The host CANNOT judge a calibration — the device returns a canned constant

`MEASUREMENT.md:381-397`: two runs, **white tile** vs **green surface** under
the aperture, gave **bit-identical** 31-band spectra — *"max absolute difference
across all 31 float32 bands : 0.0"*. Whenever the magnet gate engages, the
device performs a white calibration against whatever is there and **returns the
firmware's nominal tile constant** as its "reading". EXP-MEAS-004's
`host_trigger_capped` step matches `TILE_SIGNATURE` to 4.6 × 10⁻⁵ %R.

`INTEGRATION.md:495-499`, verbatim:
> *"**ChromIQ cannot tell a well-calibrated CR30 from a badly-calibrated one,
> and neither can we.**"*

Consequences for Basti's question (d), "how do we detect the cap is NOT on":

* **At calibration time: impossible.** The reading you get back is a constant.
  There is no read-back command; the eight-command vocabulary
  (`SAFETY_ENVELOPE.md:35-36`) contains no status query. The only candidate flag
  is `0x01` at offset 6 of a calibration reply, and `CALIBRATION.md:229-238`
  says plainly it *"has never been contrasted with anything"* — no failed
  calibration has ever been captured.
* **The magnet-gate flag does NOT help here.** `src/cr30/usb_measure.py:41-57`:
  the flag at frame offset 24 is set **only on the operator's own button press**
  and reads `0x00` on **every host-triggered read**, gated or not (20+/20+).
  A host-triggered calibration therefore reports *no cap present* even when the
  cap is on. So it cannot be used to confirm the cap IS on either.
* **After the fact: only a behavioural check, and no defensible threshold.**
  The repo's own numbers are `SUSPICIOUS_REFLECTANCE = 110.0` /
  `MAX_REFLECTANCE = 130.0` (`src/cr30/measurement.py:99-101`) and
  `EXPERIMENTS.md:627-628` says both were *"asserted … on no evidence at all"*.
  A real corrupted reading in the corpus peaks at **105.47 %R and passes every
  guard** (`ERRORS.md:150`). OBA papers can legitimately exceed 100 %R by an
  unknown amount (`EXP-MEAS-006`, specified, never run).

**Recommendation:** do not ship a "we checked your calibration" claim. There is
no evidence to back one, and a false reassurance is worse than none. See S13.

## S10 [BLOCKER] A host-triggered Calibrate button sends the ONE command both repos forbid, and cannot work over Bluetooth

Basti's ruling: *"the calibration button should trigger the calibration on the
instrument without the user pressing a button"*. The only known way to do that
is `BB 01 00` with the magnet engaged (`src/cr30/usb_measure.py:171-183`;
EXP-MEAS-004 confirms it, 81.098 → 149.103 %R, ratio 1.8386, restore 1.0012).

Two hard obstacles:

1. **`INTEGRATION.md:475-487` states the absolute rule that a ChromIQ CR30
   backend NEVER sends `BB 01 00`**, and this repo implements that rule
   deliberately: `workflow/cr30/device.py:95-118`, `trigger_unsafe()` —
   *"Deliberately not called `trigger`, and deliberately not part of the
   recommended integration surface… The host CANNOT see whether a magnet is
   near the aperture, so the rule 'do not trigger with a magnet present' is
   unenforceable in software."* A Calibrate button makes ChromIQ send it **on
   purpose, with a magnet deliberately present**. That is a reversal of a
   documented safety decision and needs to be taken as such, not slipped in.
2. **Over BLE there is no host trigger at all.** `TRANSPORT_BLE.md:282`:
   *"**No BLE host trigger is known**"*; the BLE command set is only
   `READ_MEASUREMENT` and `STATUS` (`src/cr30/ble.py:55-56`).
   `DeviceReader._open` (`measure_bridge.py:336-349`) falls back to BLE
   automatically. **So the button would be dead on a Bluetooth-connected CR30**
   and the flow must say so rather than appear to work.

Also note the vendor's dedicated `BB 10` (black cal) / `BB 11` (white cal) exist
in captured traffic but **have never been sent to this unit**
(`CALIBRATION.md:112`), and `SESSION_HANDOFF.md:73` carries a standing "do not
send them" instruction.

## S11 [BLOCKER] Calibrating while a patch read is armed DEADLOCKS — the same lock as F3

This is the answer to Basti's question (a) *"the helper is already armed on
patch A1 when this window shows — if the user calibrates, does anything reach
the helper?"* and to (c) *"should there be a Calibrate button during the
measurement?"*.

`Cr30MeasureBridge.on_patch_ready` (`measure_bridge.py:214`) calls `_start_read`
**immediately** on the first `spot_ready`. `_start_read` → `_ReadWorker.run` →
`DeviceReader.__call__` → `with self._lock:` → opens the device and sits in
`read_next_measurement`, **holding the lock and the serial port**, for up to
180 s. Basti's log shows exactly this: `CR30: opened over usb` at 22:10:18,466,
one second after the run started.

Therefore:

* A host-triggered calibration needs the same transport. It cannot have it —
  `DeviceReader._lock` is held, and there is no second handle. A Calibrate
  button implemented naively will **block the UI thread on that lock**, i.e.
  reproduce F3 on demand.
* If instead the user presses the instrument's own button with the cap on, that
  press **is** the pending A1 read. On USB the `BB 01 09` header comes back with
  the gate flag set, `Measurement.check_usable` raises `MAGNET_MESSAGE`, and the
  user is told *"The CR30 could not be read for patch A1: … Press the button on
  the instrument again"* (`tab_measure.py:6855`) — precisely the wrong advice
  during a calibration. Over BLE there is **no gate detection at all**
  (`INTEGRATION.md:502-504`), so the calibration would be silently accepted as
  patch A1's colour, guarded only by the value-change heuristic.

**Design consequence:** the calibration window must exist **before the helper is
started**, or the bridge must be told to hold off (`on_patch_ready` must not
call `_start_read`) until the calibration is finished and the reader has been
released. There is currently no such hold: `_open_cr30_bridge`
(`tab_measure.py:6797`) and the helper launch are back-to-back, and
`_show_cr30_measuring_window` (6884) is **modeless** (`dlg.setModal(False)`,
line 6928) precisely so it does not sit between the user and the preview — so it
cannot gate anything.

## S12 [ANSWERED] (a) The calibration cannot be counted as a measurement — and that is free

The count has exactly two sources and neither can see a calibration:

* `workflow/measure_manager.py:1306-1310` — `_readings_count` increments only on
  a `patch_read` event from the helper.
* the helper's own `{"event":"saved","read_patches":N}` (log 22:11:09,874).

Under `-xx` the helper opens no instrument at all: `'k' to calibrate` exists
only in the `xtern == 0` branch of the spot menu
(`native/chartread_helper/chromiq_chartread.c:2875`), and every
`cq_handle_calibrate` call site is inside `if (xtern == 0)` (lines 918, 1907,
2610-2623). **Nothing reaches the helper when a CR30 user calibrates**, so no
`patch_read` and no `read_patches` increment can occur. The `cal_*` JSON events
and `MeasureManager.calibration_prompt` / `calibration_done`
(`measure_manager.py:220, 236`) are likewise unreachable on this path — which is
the finding `measurement_messages.py:115-117` already records as the reason
M-CR30-HOW-TO-MEASURE had to exist.

The real risk is not double-counting; it is **S11**, the reading being consumed
as patch A1.

## S13 [ANSWERED, with a warning] (b) mandatory or skippable?

* **What the CR30 does if never calibrated: NOT ANSWERED IN THE RESEARCH REPO.**
  It is an explicitly open question — `CALIBRATION.md:251` and `EXPERIMENTS.md:533`
  (EXP-CAL-001 phase 2, "⏸ READY, NEEDS THE HUMAN", never run). So **no claim
  about uncalibrated behaviour may be written into a spec or a message.**
* What *is* known: on a **mis**-calibrated device the CR30 returns plausible,
  correctly framed, wrong values — it does not refuse, does not error, sets no
  status byte (`src/cr30/measurement.py:1-17`).
* There is also a standing instruction in the research repo,
  `CALIBRATION.md:93-117`: *"⚠ DO NOT recalibrate this unit"*, with
  *"Nothing indicates it is needed"* and *"If a genuine drift is ever
  demonstrated, recalibration becomes a designed experiment with a recorded
  before-state — not a remedy applied on suspicion."*

**Recommendation:** offer it, do not force it, and do not claim it succeeded.
Mandatory calibration on this instrument is a bigger risk than skipping it: the
only calibration failure mode we have ever observed on this hardware was
*caused* by calibrating (against the green face), and it is undetectable
afterwards. A mandatory step that can silently corrupt the instrument, on a
device whose uncalibrated behaviour has never been measured, is not defensible
on the evidence.

## S14 [ANSWERED] (c) re-calibration mid-session — the drift data does not support it

The only drift number in the repo: `MEASUREMENT.md:800-801`, EXP-SPEC-001b —
30 consecutive readings of one un-moved paper white drifted **82.538 → 82.272 %R**
monotonically, i.e. **−0.266 %R ≈ −0.32 % relative**, and the shape is a warm-up,
not a walk. Elapsed time is not recorded (the capture stores no per-reading
timestamps), but the script's own delays put it in the low minutes
(`tools/probe_noise_rank.py:58,67`). Short-term repeatability is 0.056 %R
worst-band SD (`MEASUREMENT.md:314`).

**Hours-scale drift: NOT MEASURED. A recommended re-calibration interval: NOT
ANSWERED IN REPO.**

So: there is **no evidence** that a 390-patch run needs a mid-session
re-calibration, and there IS a standing instruction not to recalibrate on
suspicion. Combined with S11 (a mid-run Calibrate button deadlocks the reader
and steals the armed patch), my recommendation is **no Calibrate button during
the measurement** in the first cut. If one is ever added it must first stop the
bridge, release the reader, calibrate, and re-arm — and that sequencing must be
designed, not bolted on.

## S15 [DISAGREEMENT] (e) The ΔEs are NOT evidence of an uncalibrated instrument

11_EVIDENCE.md asserts: *"(Large because the instrument was never calibrated —
see F1. Do not chase the dE magnitude as a separate bug.)"* The conclusion (don't
chase it) is right; **the stated reason is unsupported and the evidence points
the other way.**

A corrupted white reference produces a roughly **uniform multiplicative** shift:
EXP-MEAS-004 measured 81.098 → 149.103, ratio 1.8386; `CALIBRATION.md:69-71`
measured 85.84 → 156.78. Basti's three readings, against their nominal
expectations, show **no such inflation and no common factor**:

| loc | measured Y | expected Y | ratio |
|---|---|---|---|
| A1 | 36.4965 | 39.5511 | 0.923 |
| A2 | 33.7597 | 73.0362 | 0.462 |
| A3 | 28.1945 | 42.2424 | 0.667 |

Values *below* expectation, with a 2× spread in the ratio. That is a normally
behaving instrument reading a real print against **targen's nominal XYZ** — the
explanation the implementer already established — not a corrupted reference.
Delete the "never calibrated" clause from the evidence file; it is the kind of
unverified causal claim the project's own rules exist to keep out.

---

# PART 4 — faults nobody reported

## S16 [MAJOR] Build Profile is armed by ANY .ti3, including a 3-of-390 one — and it happened in this session

`ui/tabs/tab_profile.py:4013-4019` — `set_ti3_path` sets `self._ti3_path` and
then `self._build_btn.setEnabled(True)` **unconditionally**. There is no
completeness check anywhere in the tab: `grep -n "partial\|incomplete\|NUMBER_OF_SETS\|too few\|not enough" ui/tabs/tab_profile.py`
returns nothing.

It fired in Basti's own session: `22:14:19,882 [INFO] ui.tabs.tab_profile: Build
Profile: measurement follows the bar → …/CR30-Test.ti3`
(`tab_profile.py:4674-4677`). That file holds **3 sets out of 390**:

```
NUMBER_OF_SETS 3
103 "A2" … / 342 "A3" … / 384 "A1" …
```

Failure scenario: read 3 patches, save-and-stop, switch to Build Profile, press
the primary button. `colprof` on 3 patches either dies with an Argyll message
the user cannot act on, or produces a profile that is garbage and is then
installed. Not CR30-specific in principle — but #159 makes "stopped after a
handful of patches" the **normal** case, because patch-by-patch on 390 patches
is a long job people will abandon and resume.

## S17 [MAJOR] The plural bug is real, in the window a CR30 user hits first

`ui/tabs/tab_measure.py:6014`:

```python
"You have read {n} patches in this session. They are not in your "
```

and `:6011` `"Your previous measurement of {m} patches is put back exactly as it was."`

Neither has a singular form. With `n == 1` the user reads *"You have read 1
patches in this session."* CLAUDE.md's i18n rule is explicit: *"Count-bearing
messages get explicit singular/plural variants, never `(s)`."* The project
already knows how — 118 lines below, `tab_measure.py:6131-6132`:

```python
patches = (tr("one patch") if n == 1
           else tr("{n} patches").format(n=n))
```

This is the **Save-and-stop / Discard-and-stop / Keep-measuring** window, which
is exactly where a patch-by-patch CR30 user ends up, and `n == 1` is a
completely ordinary case there (arm the first patch, read it, decide to stop).
Note that changing this text is §M-governed — see S21.

## S18 [MAJOR] Save-and-stop with ZERO patches read writes an empty measurement over the run

The new `-x` path (`workflow/measure_manager.py`, commit `7fa9bf2d`) sends `d`
then answers the "at least one unread patch, are you sure" prompt with `y`
itself. With **zero** patches read that still runs: the helper writes a `.ti3`
with `NUMBER_OF_SETS 0` and exits 0.

Consequences to check:
* `tab_measure.py:11440-11453` `_cgats_has_no_readings` exists precisely for
  this state, so the tab can say it — good.
* But **S16 still arms Build Profile**, because `set_ti3_path` does not look
  inside the file.
* And the file now exists, so `Run.measurement_ti3.is_file()` is true and the
  run counts as measured for every "follows the bar" consumer
  (`tab_profile.py:4674`).

Scenario: user starts a CR30 read, realises the cap is on / the chart is wrong,
presses Stop → "Save and stop" (the **first**, accept-role button, and the one
whose label reads as the safe choice). An empty `.ti3` lands in the run. Verify
whether the guard at 6014's window prevents offering "Save and stop" at n == 0 —
it does not appear to.

## S19 [MINOR] `_save_partial_state` is never cleared when the confirmation does not come

`measure_manager.py` save-partial: `self._save_partial_state = "wait_are_you_sure"`
then `send_key("d")`. If the chart happens to be **complete**, the helper's `d`
produces no `unread_confirm` at all — it just saves and exits. The state string
is left set. Harmless today because the run ends, but it is a latch with one
setter and one clearer on a path that has a second exit.

## S20 [i18n] The new CR30 strings ARE wrapped, with one caveat

Spot-checked every user-facing literal added on this branch in
`ui/tabs/tab_measure.py:6836-6930` (`_on_cr30_dropped`,
`_on_cr30_read_failed`, `_on_cr30_mispaired`, `_show_cr30_measuring_window`) —
all are `tr()`-wrapped or come from `workflow/measurement_messages.py`.

**The exception is `_no_device_help` (`workflow/cr30/measure_bridge.py:63-116`)**
— roughly 15 sentences of user-facing text with **no `tr()` at all**, including
platform-specific instructions ("add yourself with sudo usermod -aG dialout
$USER", "Check Device Manager → Ports"). It is raised as a `ConnectionError`
message and surfaces to the user through `_on_cr30_read_failed`'s
`{message}` placeholder (`tab_measure.py:6855-6858`), i.e. it is definitely
shown. That is a wall of untranslated English inside an otherwise translated
message, and `scripts/i18n_extract.py` cannot see it because it is not in a
`tr()`.

## S21 [BINDING SPEC] §M applies to every string the calibration flow adds

CLAUDE.md and `docs/design/unified_measurement_management.md:48` are explicit:
*"§M is the complete message catalogue: every window, with its ID and text"*, and
`measurement_exit_strategy.md:7`: *"A new message goes to §M-PROPOSED first, and
`tests/test_message_catalogue.py` fails if one is added to the code without it."*

The branch already follows this correctly — `M-CR30-STOCK-READER`,
`M-CR30-READ-ENDED` and `M-CR30-HOW-TO-MEASURE` are all listed in the
awaiting-review header of `unified_measurement_management.md:4`, dated
2026-08-28. **The calibration flow's windows must go the same way, and must NOT
be written into `tab_measure.py` as bare `tr()` calls first.** That includes:
the calibrate-first window, its confirmation window, any refusal message, and
any "we could not check your calibration" wording (see S9 — it must not claim to
have checked).

Two further spec obligations the calibration flow touches:

* `measurement_exit_strategy.md:107` already maps a **"Calibration required"**
  window with OK / Skip / Cancel → `\r` / `s` / `\x1b`, and note 3 (line 201)
  records Knut's ruling on its Cancel. That is the *instrument's* prompt on the
  Argyll path. A CR30 calibration window is a **new** ending/entry that this
  document does not cover, so the document must be extended, not silently
  contradicted.
* CLAUDE.md's confirmation rule: whatever the calibration flow is found to do
  on screen goes into an **`⏳ Awaiting confirmation`** section with
  `**Confirmed by:** *nobody yet.*` — an on-screen run by an agent is not a
  confirmation.

---

# RANKED SUMMARY (so far)

| # | rank | finding | file:line |
|---|---|---|---|
| S1 | **BLOCKER** | quit/stop blocks on `DeviceReader._lock`; `cancel()` has no production caller | `measure_bridge.py:377`, `tab_measure.py:6823-6834` |
| S10 | **BLOCKER** (design) | host-triggered calibrate = `BB 01 00`, forbidden by `INTEGRATION.md:475-487` and by `device.py:95-118`; impossible over BLE | `device.py:95`, `TRANSPORT_BLE.md:282` |
| S11 | **BLOCKER** (design) | calibrating while a read is armed deadlocks on the same lock, or is eaten as patch A1 | `measure_bridge.py:214,360` |
| S8/S9 | **BLOCKER** (design) | the "detect a bad calibration" premise is factually inverted and the device returns a canned constant | `MEASUREMENT.md:381-397,554` |
| S2 | MAJOR | `read_failed` fires after `stop()`; will fire on EVERY stop once S1 is fixed | `measure_bridge.py:267-270` |
| S6 | MAJOR | stale `_patch_boxes` survive a chart with no TIFF | `tab_measure.py:4324-4332,4349` |
| S16 | MAJOR | Build Profile armed by a 3-of-390 `.ti3` — happened in this session | `tab_profile.py:4019` |
| S17 | MAJOR | "You have read 1 patches" in the Save-and-stop window | `tab_measure.py:6014` |
| S18 | MAJOR | save-and-stop at zero patches writes an empty measurement into the run | `measure_manager.py` (7fa9bf2d) |
| S20 | MAJOR | `_no_device_help`'s ~15 user-facing sentences are not `tr()`-wrapped | `measure_bridge.py:63-116` |
| S3 | MINOR | a clean quit is logged as an instrument failure | `measure_manager.py` |
| S7 | MINOR | one missing box loses the overlay with no message | `tab_measure.py:10633` |
| S19 | MINOR | `_save_partial_state` latch has an unhandled exit | `measure_manager.py` |
| S4 | REFUTED | "still not really closed" — one beachball, no second hang | log 22:14:19,890 |
| S5 | REFUTED | the preview/geometry/handler are innocent; F2's cause is still open | measured |
| S15 | DISAGREE | the ΔEs do not indicate an uncalibrated instrument | `.ti3` ratios |

*(Sections on the `_ti1_path` audit, the reopened-project fix review, and the
on-screen verification follow.)*

---

# PART 5 — the `_ti1_path` audit, and a review of commit `a7516de1`

## S22 [MAJOR] `_maybe_repair_target_instrument` is the open-coded read the CR30 docstring forbids

`ui/tabs/tab_measure.py:4687`:

```python
name = read_target_instrument(self._ti1_path)     # ← the RAW path
```

`_chart_is_cr30`'s own docstring (`tab_measure.py:5374-5385`) states the rule in
as many words:

> *"``TARGET_INSTRUMENT`` … is not in the `.ti1` at all — while opening a project
> hands this tab ``run.chart_ti1``. Every open-coded
> ``read_target_instrument(self._ti1_path)`` therefore read ``None`` after a
> reopen and silently answered "not a CR30". … **Never add a second open-coded
> read; there were two and they were both wrong.**"*

There is still one, and it is on the Start path. Verified on Basti's real files:

```
read_target_instrument(CR30-Test.ti1) → None
```

Failure scenario: reopen a project whose chart carries a `TARGET_INSTRUMENT`
ArgyllCMS cannot use → `name is None` → `return False` at line 4690 → **the
"This chart names an instrument ArgyllCMS cannot use" window never appears**, the
repair is never offered, and chartread refuses the chart before the first patch.
That is precisely the failure this guard exists to prevent, and the docstring at
4676-4681 says so: *"a run that cannot possibly succeed should never begin."*

Secondary: line 4720 then calls `_repair_target_instrument(self._ti1_path, name)`
— on the reopened path it would rewrite the `.ti1`, which is not the file
chartread reads.

**Fix:** `chart = self._chart_file_for(self._ti1_path)` and use `chart` for both
the read and the repair. One line each.

## S23 [MAJOR] `_overlay_failure_reason` has the SAME bug — and `a7516de1` just made it reachable

`ui/tabs/tab_measure.py:11448`:

```python
matched = bool(per_patch_overlay(ti3, self._ti1_path))    # ← the RAW path
```

Measured (the implementer's own numbers, which I accept):
`per_patch_overlay(ti3, .ti1)` returns rows named by `SAMPLE_ID` ("103"), not by
chart location ("A2"). `bool(non-empty list)` is **True**, so `matched = True`,
so the method falls through to `return "no_geometry"`.

Before `a7516de1`, `_show_overlay_from_existing_ti3` returned True
unconditionally, so `_on_overlay_toggled` (11317) never reached
`_overlay_failure_reason` on this path. **The fix makes False reachable, and this
is what False now leads to** — `tab_measure.py:11374-11392`, a four-paragraph
modal that asserts, confidently and wrongly:

> *"This chart doesn't record where its patches are … this chart does not carry
> that information. Charts made by older versions of ChromIQ — before the
> ChromIQ layout engine — were laid out by ArgyllCMS's printtarg…"*

…about a chart with 390 recorded patch boxes in its `channels.json`. That is the
exact class of wrong-diagnosis message Knut objected to twice already (#130,
#155 — both quoted in the comments right above this code).

**This is the direct answer to handover #2's Q4: yes, the change turns a silent
no-op into a WRONG message, on a reopened project.** Fix `11448` in the same
commit as `a7516de1`, or the fix ships a regression.

## S24 [MAJOR] `a7516de1`'s new success test measures the wrong thing

```python
return any(self._preview._patch_overlay.get(pg)
           for pg in range(max(1, len(self._patch_boxes))))
```

`_on_chart_measured` **accumulates** into the preview — `set_patch_overlay` is
called with `replace_page=False` (`tiff_preview.py:1350-1370`), and
`_show_overlay_from_existing_ti3` does **not** clear first. So this expression
answers *"is anything on the preview?"*, not *"did this call paint anything?"*.

Failure scenario: a patch-by-patch session paints 3 live patches
(`_on_patch_measured` → `set_patch_overlay`). The user then ticks
**"Show overlay from existing measurement"** while a genuinely foreign `.ti3`
sits in the run. `per_patch_overlay` returns rows, none of them place, nothing
new is painted — but the 3 live items are still in `_patch_overlay`, so the
method returns **True** and `_on_overlay_toggled:11318` prints *"Showing the
expected vs. measured colours from this chart's existing measurement."* The user
is told the file was shown when it was not. That is the same silent-lie shape the
commit set out to remove, moved one step along.

**Fix:** have `_on_chart_measured` return the number of patches it placed
(it already builds `items` per page — `sum(len(v) for v in items.values())`),
and return that. It removes the private-attribute reach at the same time.

### On the private attribute (handover #2 Q3)

There **is** a public accessor: `ui/tiff_preview.py:1654 has_patch_overlay()`.
It is weaker (`bool(self._patch_overlay)` — true for `{0: []}`), so it is not a
drop-in. The page range itself is **correct** for multi-page:
`len(self._patch_boxes)` is the page count, and the guard two lines above
(`not any(self._patch_boxes)`) means it is only reached with ≥1 page. But per
S24 the whole expression should be replaced rather than tidied.

## S25 [ANSWER to handover #2 Q1] Neither layer alone closes the class — there are at least two more live sites

The tab-level fix in `a7516de1` is **correct and I would keep it** —
`_chart_file_for` documents the `.ti1` as a supported input, so the tab is
genuinely responsible for resolving it, and fixing only `main_window.py:2397`
would leave every other caller free to hand in a `.ti1` again.

But it does not close the bug class, and the audit proves it: **S22 (line 4687)
and S23 (line 11448) are still broken after `a7516de1`.** Fixing
`main_window.py:2397` would not reach them either — a `set_ti1_path(.ti1)` can
arrive from anywhere.

The durable fix is to **normalise once, in the setter**: `set_ti1_path` stores
`_chart_file_for(path)` when that file exists, and the given path otherwise.
Evidence it is safe:

* every site that genuinely wants the `.ti1` already derives it by suffix swap
  (`tab_measure.py:10793 Path(_ti1).with_suffix(".ti1")`), so it keeps working;
* `_try_load_tiffs` globs by stem (4311-4317) — unaffected;
* `patch_boxes_from_sidecar` finds its sidecar by `with_suffix` — unaffected
  (I verified both `.ti1` and `.ti2` give 390 boxes on Basti's chart);
* `_blocked_by_missing_chart_file` (3789) already resolves through
  `_chart_file_for` and checks `.exists()`.

The one thing to check before doing it: `_chart_identity()` (11103-11108) keys
the refinement arming on `str(self._ti1_path)`, so normalising changes that key.
It would make it *more* stable across a reopen, but it is a behaviour change and
belongs in its own commit with its own test.

**Sites audited and found CORRECT** (they already resolve, and each says why in
a comment): 4521-4525 (pace defaults), 4790-4800 (`_chart_instrument_code`,
tries the `.ti2` first), 4838+ (instrument-mismatch window), 5389
(`_chart_is_cr30`), 5789 (`per_patch_overlay` with an explicit `.with_suffix(".ti2")`),
4386-4393 (`ti2_for_counts`), 10494 (`_progress_files` returns both), 10793,
10846, 11626 (`can_resume`, derives both).
**Sites found BROKEN:** 4687 (S22), 11448 (S23).

---

# PART 6 — incident 2 (22:26–22:30): the freeze mechanism, NAMED and PROVEN

## S26 [CORRECTION] The 180 s claim was RIGHT. Handover #3 measured the wrong interval.

Handover #3 says *"Incident 2 … gap … = 71.07 s. NOT 180 s"* and concludes the
180 s is "a ceiling, not the mechanism". **That measured the user's reaction
time, not the freeze.** 22:27:53,770 → 22:29:04,841 is the interval between the
patch being armed and Basti getting round to pressing Stop and clicking through
the Save-and-stop window. The helper answered instantly (`unread_confirm` at
22:29:04,852, `done` at ,878, exit 0 at ,878). Nothing was blocked in that
window.

**The freeze in incident 2 is 22:29:04,878 → 22:30:53,748 = 108.87 s**, and it
sits exactly where incident 1's does: after the run ends, inside
`_on_measure_done` → `_close_cr30_bridge`. Measured:

| | patch armed | resume | armed → resume | the freeze itself |
|---|---|---|---|---|
| incident 1 | 22:11:19,339 (A4) | 22:14:19,872 | **180.533 s** | 162.85 s |
| incident 2 | 22:27:53,769 (A16) | 22:30:53,748 | **179.979 s** | 108.87 s |

Two independent reproductions, both landing on `button_timeout_s = 180.0` to
within 0.3 %. The *visible* freeze differs (162.8 s vs 108.9 s) only because the
user pressed Stop at a different point in the 180 s window. **The 180 s is the
mechanism.** Restore the claim.

## S27 [BLOCKER] The exact blocking primitive, proven by experiment

**The GUI thread waits at `workflow/cr30/measure_bridge.py:377` — `with
self._lock:` at the top of `DeviceReader.close()` — called from
`ui/tabs/tab_measure.py:6829`.** The lock is held by the worker thread from
`measure_bridge.py:360` until `read_next_measurement` returns or raises.

It is **not** a `QThread.wait()` (nothing calls it), **not** the QProcess
(exit 0 arrived at 22:29:04,878, before the freeze), and **not** a bleak event
loop (the transport was USB).

Proven, not inferred. Real `DeviceReader`, real `close()`, a stub device whose
poll loop has the exact shape of `device.py:147-164` with a dead port, ceiling
lowered to 4 s:

```
A: close() with NO cancel  (what _close_cr30_bridge does today)
   main thread blocked in DeviceReader.close(): 3.58 s
   worker ended with: RuntimeError('no button press')       ← ran to the ceiling
B: cancel() THEN close()   (the proposed fix)
   main thread blocked: 0.0000 s
   worker ended with: RuntimeError('cancelled')
```

### Why the read did NOT fail on the unplug — and why it never can

`workflow/cr30/device.py:159-163`:

```python
try:
    hdr = usb_measure.wait_for_button_header(self._t, timeout=min(left, 1.0))
except Exception:
    continue                      # nothing yet; keep waiting
```

**`except Exception: continue` swallows the disconnect.** Every failure mode of
a removed USB serial device arrives as an exception here:

* `SerialTransport._read` (`transport.py:166-176`) touches `ser.in_waiting`,
  which raises `serial.SerialException` on a removed device on macOS;
* if it instead returns 0 bytes, `Transport.receive` (`transport.py:97-104`)
  raises `TransportTimeout`;
* if the port has been closed, `_require()` (`transport.py:149-152`) raises
  `TransportError`.

All three are `Exception`. All three `continue`. So handover #3's revised claim —
*"released either by the read failing or by the 180 s timeout, whichever comes
first"* — is **REFUTED**: with this `except` clause the read can never fail, so
the ceiling is the only exit. Incident 2 proves it: the device was physically
gone for ~71 s before Stop and the wait still ran the full 180 s.

Worse, on the raising branch the loop spins with **no sleep at all** — every
iteration raises immediately and `continue`s — so an unplugged CR30 burns a core
for three minutes.

### The correct fix, named

1. **`Cr30MeasureBridge.stop()` must call `self._reader.cancel()`**
   (`measure_bridge.py:240`). Every stop path then gets it, not only the one
   that remembers. Latency: ≤1 s on USB (`device.py:160`, `min(left, 1.0)`),
   ≤0.25 s on BLE (`device.py:181`, `poll`).
2. **`DeviceReader.close()` must not block unboundedly**
   (`measure_bridge.py:376-383`): set `_cancel`, then
   `self._lock.acquire(timeout=2.0)`, and close the transport whether or not
   the lock was granted.
3. **Do NOT rely on "close the transport to force the read to return".** It does
   not work here — a closed port makes `_require()` raise, which
   `device.py:162` swallows, so the loop would spin instead of unblocking.
4. **`device.py:159-163` must stop swallowing everything.** Only "no frame yet"
   (`TransportTimeout` / `ShortFrameError`) is a reason to keep waiting.
   `TransportError` and `serial.SerialException` mean the instrument is gone and
   must be raised. This is simultaneously the fix for S28.

Do **not** just shorten `button_timeout_s`. It would only shorten the beachball,
and (2)–(4) are what actually make Stop responsive.

## S28 [BLOCKER] Unplugging the CR30 mid-measurement produces NOTHING — and `instrument_disconnected` is a dead signal

Basti: *"i unplugged the device and forgot to stop measurement — no warning"*.
The log confirms complete silence between 22:27:53,769 and 22:30:53,748.

Handover #3's three questions, answered:

**(a) Does the read fail on unplug?** **No.** `device.py:162` swallows it (S27).
The reader polls a dead handle until the 180 s ceiling and then reports *"no
button press within 180 s. Place the instrument on the highlighted patch and
press its own button."* (`device.py:155-158`) — a wrong diagnosis delivered three
minutes late. In this session it never even got that far: the run had already
ended, so the failure was consumed by the teardown.

**(b) Is `failed` emitted, and does anything visible listen?** `_ReadWorker.failed`
→ `Cr30MeasureBridge._on_read_failed` (`measure_bridge.py:267`) → `read_failed`
→ `tab_measure.py:6855`, which writes to the in-app log and flashes the status
bar. So there IS a listener — but it only fires **after** the 180 s ceiling, and
it says the wrong thing. See also S2: it has no `_stopped` guard, so on a Stop
it fires *after* the session ended.

**(c) Is `instrument_disconnected` reachable on the CR30 route?** **It is not
reachable on ANY route.** `MeasureManager.instrument_disconnected` is
**declared at `workflow/measure_manager.py:238` and emitted nowhere.** Verified
repo-wide (`grep -rn instrument_disconnected`, excluding `.venv`/`__pycache__`):
the only `.emit()` is `workflow/spot_read_manager.py:211`, on a *different*
manager used by `ui/dialogs/spot_read_dialog.py:274`. There is no dynamic signal
dispatch in `MeasureManager` (checked).

So `ui/tabs/tab_measure.py:1029` connects a signal that nothing can raise. Behind
it sit a full handler (`_on_instrument_disconnected`, 7109-7123), a window
(`_show_instrument_disconnected_window`, 7150), a sound cue, a
save-partial offer and end-of-session handling (9205-9209) — **an entire feature
that cannot fire.** Six test files exercise it (`test_measure_disconnect_save_partial.py`,
`test_streaming_instrument_error.py`, `test_measure_sound_wiring.py`,
`test_every_window_sounds.py`, `test_window_sounds_actually_play.py`,
`test_measurement_window_sounds.py`) — every one of them either calls the handler
directly or emits the signal by hand, so the suite is green and the feature is
dead. Textbook *"a green test can be guarding the bug"*.

### What SHOULD happen (recommendation)

* **The reader must notice within ~1 s.** Fix (4) in S27: raise on
  `TransportError` / `SerialException` instead of `continue`.
* **The bridge must escalate, not just log.** A device-gone failure is not the
  same as "that reading was refused". It needs its own signal
  (`device_lost`), distinct from `read_failed`, and a window — CLAUDE.md quotes
  Knut: *"all events shall have windows, and not hidden in a log where user will
  not see it."*
* **Reuse the existing machinery rather than inventing one.** Emitting
  `MeasureManager.instrument_disconnected` from the CR30 bridge would light up
  the handler, window, sound and save-partial offer that already exist and are
  already §M-approved — and would fix the dead signal at the same time. This is
  the "reusing beats inventing" answer.
* **The user must not be able to keep "measuring" into a void.** Today the
  preview still highlights A16 and the helper still shows its prompt; nothing on
  screen says the instrument is gone.

### The 15 patches were safe — and yes, that IS the guarantee we rely on

The helper writes the `.ti3` after **every** patch — `{"event":"saved",…,
"read_patches":N}` appears 15 times in this session, the last at 22:27:53,769.
So the data on disk was already complete before the unplug. **Say this out loud
in any design document: patch-by-patch durability rests entirely on the helper's
per-patch save, not on anything ChromIQ does.** Note the contrast with strip
mode, where CLAUDE.md records that *"chartread writes .ti3 ONLY on clean exit —
kill = data loss"*. If the per-patch save were ever made conditional, an unplug
would cost the whole session.

## S29 [CONFIRMED] Save-and-stop under `-x` works on real hardware — but three states are still untested

`7fa9bf2d` is confirmed by incident 2 end to end: `done` → `unread_confirm` →
`yes` → `done` → exit 0, 15 patches on disk. I accept that and did not re-derive
it. The states that are **not** covered by that run, in order of risk:

1. **Zero patches read** — see S18. `d` still produces `unread_confirm`, `y`
   still saves, and a `NUMBER_OF_SETS 0` `.ti3` lands in the run and arms Build
   Profile (S16).
2. **All patches read** — the helper's `d` then produces **no** `unread_confirm`
   at all, so `_save_partial_state` is left latched at `"wait_are_you_sure"`
   (S19). Benign today only because the run ends.
3. **During an outstanding `goto`** — `Cr30MeasureBridge.note_goto`
   (`measure_bridge.py:229`) clears `_awaiting_loc` and sets `_nav_target`;
   `save_partial_and_quit` sends `d` regardless. The helper is mid-jump. Not
   exercised by any test I can find.
4. **Device absent from the start** — `_open` raises `ConnectionError`
   (`measure_bridge.py:349`), `_on_read_failed` fires, the session is still
   running with no reader. Save-and-stop then writes an empty `.ti3` (case 1).

---

# PART 7 — the Bluetooth session (22:32:45–22:33:28)

## S30 [BLOCKER] The BLE read compares a measurement to ITSELF and raises every single time. The Bluetooth path can never return a reading.

`workflow/cr30/device.py:166-181`, the BLE branch of `read_next_measurement`:

```python
prev = self._previous.values if self._previous else None
while True:
    ...
    m = self.read_measurement(enforce=False)     # ← device.py:262 sets self._previous = m
    if prev is None or m.values != prev:
        m.check_usable(self._previous)           # ← self._previous IS m
```

`read_measurement` assigns `self._previous = m` **unconditionally** at
`device.py:262` — the `enforce` flag only gates the *check*, not the
bookkeeping. So by the time `check_usable(self._previous)` runs, `previous`
**is the very measurement being checked**, and
`Measurement.identical_to` (`measurement.py:167-176`) does
`self.values == other.values` → `True` → `check_usable` raises at
`measurement.py:196-200`:

> *"reading is bit-identical to the previous one. Either no new measurement was
> taken, or a magnet is gating the device. Genuine repeats differ in the low
> bits."*

**Proven, not argued.** Real `CR30.read_next_measurement`, real `Measurement`,
real `check_usable`, with a stub `read_measurement` that returns a *genuinely
different* spectrum on every call:

```
RAISED after 1 read(s): reading is bit-identical to the previous one. …
```

There is no input for which the BLE branch can succeed: either the stored value
has not changed (`m.values == prev`, so it sleeps and loops) or it has changed —
and then it compares the new reading against itself and raises. **A CR30 over
Bluetooth cannot measure a single patch.** This is device-independent logic, not
a transport fault: the USB branch takes a different code path
(`device.py:147-164`) and is unaffected, which is why the same evening's USB
session read 15 patches.

### This explains handover #4's whole timeline, exactly

* **22:32:45,496** `bb 02 10 00 00 00 00 00 ff cc` — this is
  `ble.READ_MEASUREMENT = frame(0x02, 0x10)` (`ble.py:55`). I recomputed the
  BLE checksum by hand from `ble.py:40,43-52`:
  `sum(BB,02,10,00,00,00,00,00,FF) = 460`, `460 % 256 = 204 = 0xCC`. **The
  command and its checksum are correct**, under the 10-byte BLE rule and not
  the USB one. Handover #4's question 4 is answered: this frame is right.
* **22:32:45,848 / :46,200 / :46,552** — three `b'\x01'` poll bytes at 352 ms.
  That is `BleTransport.ask(..., wait=0.35)` (`ble.py:232`) and its drain loop
  (`ble.py:224-230`), which stops after **three quiet polls**
  (`if quiet >= 3 and self._buf: break`). Exactly three, exactly 0.35 s apart.
  So this is **one complete `read_measurement()`** — not a truncated loop, not
  a retry cap, not a handshake. Handover #4's question 1 is answered: the poll
  loop did not stop, it *finished*, and the read then raised.
* **Polling never resumes** because nothing re-arms it.
  `Cr30MeasureBridge._on_read_failed` (`measure_bridge.py:267-270`) clears
  `_reading_loc` and emits `read_failed` — and that is all. No retry, no new
  `_start_read`. A new read only begins on the next `spot_ready`
  (`measure_bridge.py:214`), and the helper only re-prompts after it receives a
  command. **The session is dead from that instant on**, with the helper still
  showing "Ready to read patch '…'".
* **The message the user got is actively misleading.**
  `tab_measure.py:6855-6860`: *"The CR30 could not be read for patch X: … Press
  the button on the instrument again."* Pressing the button cannot help —
  nothing is reading. That is what Basti did, twice.
* **22:32:57 / 22:33:15 / 22:33:17 notifications** — handover #4's question 2:
  the notification handler is still installed (it is a `bleak` callback bound at
  connect), and `BleTransport._on_notify` (`ble.py:202`) appends every frame to
  `self._buf`. **Nobody drains it**, because `ask()` is only called from inside
  a read and no read is running. So his button presses were received into a
  buffer and discarded. Worse: they are still in `_buf` when the next `ask()`
  runs — `ask` calls `reset_input`/`_buf.clear()` (`ble.py:212-216`) first, so
  they are dropped rather than mis-paired, which is the one piece of luck here.
* **22:33:27,994 `ArgyllRunner: process killed`** *then* **22:33:28,059
  disconnect** — handover #4's question 5: **the user initiated it.** The BLE
  link dropped 65 ms after the kill, as `_close_cr30_bridge` → `reader.close()`
  → `dev.close()`. The app did not drop the link on its own.
* **And note what did NOT happen: no beachball.** 22:33:27,994 → 22:33:28,086 is
  **92 ms**. Because no read was in flight, `DeviceReader.close()` took the lock
  immediately. That is an independent confirmation of S27's mechanism: the
  freeze happens precisely when a read is waiting, and not otherwise.

### The first BLE read is ALSO unguarded — a second, hidden fault behind the first

`prev = self._previous.values if self._previous else None` and then
`if prev is None or …`. On the **first** read of a session `self._previous` is
`None`, so the branch is taken **without any wait at all**: the BLE path is
designed to return the device's *already stored* reading instantly on patch 1.
That is exactly the hazard `measure_bridge.py:352-359` documents in capitals —
*"patch A1 received the stale white-tile cache at delta E 60.5, silently"*. It is
currently masked by S30 (the self-comparison raises first). **Fixing S30 alone
would expose it.** Both must be fixed together, and the fix for the first read
over BLE has to be a real change-detection baseline (take one throwaway read to
establish `prev`, and say on screen that the device is being primed), not
`prev = None`.

### The fix

In `device.py:176-180`, capture the previous measurement **before** the read:

```python
prior = self._previous
m = self.read_measurement(enforce=False)   # this reassigns self._previous
if prior is None or m.values != prior.values:
    m.check_usable(prior)                  # ← compare against the PRIOR one
```

…plus a real baseline for the first read. Note the same `self._previous = m`
side effect at `device.py:262` makes `read_measurement(enforce=False)`
*silently mutate* the change-detection state that its own caller depends on;
that coupling is the root of this bug and is worth removing outright.

### Why no test caught it

`tests/test_cr30_waits_for_the_button.py` is the file that owns this behaviour.
Whatever it asserts, it cannot be driving the BLE branch with a `Measurement`
that goes through `read_measurement`'s `self._previous = m` assignment — because
if it did, it would fail. **A test that stubs `read_measurement` without
reproducing its side effect proves nothing about the real path.** This belongs
on the same shelf as S28's six tests for a signal nothing emits.

## S31 [MAJOR] Two independent faults, one missing mechanism: nothing notices that the instrument has gone quiet

Three of tonight's four incidents are the same shape:

| incident | what happened | what the user saw |
|---|---|---|
| unplug (22:27) | reader polled a dead port for 180 s (S27/S28) | nothing |
| Bluetooth (22:32) | reader failed once and stopped for ever (S30) | one line in the in-app log telling him to press a button that does nothing |
| dead signal | `instrument_disconnected` is never emitted (S28) | nothing, ever, on any path |

Handover #4 asks whether one mechanism should cover both. **Yes, and it should be
the one that already exists.** `MeasureManager.instrument_disconnected`
(`measure_manager.py:238`) already has a handler, an approved window, a sound
cue, a save-partial offer and end-of-session handling in `tab_measure.py`
(7109-7123, 7150, 9205-9209) — all dead code today. Emitting it from the CR30
bridge would:

* light up an existing, already-§M-approved user journey rather than inventing a
  new window (which would need §M-PROPOSED review first — see S21);
* fix the dead-signal defect at the same time;
* cover both the unplug and the BLE-failure cases from one place.

Add to it a **liveness watchdog** — "nothing has arrived from the instrument
since the last prompt, and it has been N seconds" — surfaced in the UI. The
value of N is a design decision, but note it cannot simply be
`button_timeout_s`: 180 s of silence is currently *indistinguishable* from a
user taking their time, which is precisely why nothing warned him.

## S32 [NEW FACT for the research repo — proposed, not written]

Basti: *"the device did not show the bluetooth indicator (the B) on its screen.
after pressing the button once the B appeared."* I checked
`/Users/Basti/develop/chromiq-cr30-research/TRANSPORT_BLE.md` — it documents the
advertised name (`:6-14`), single-connection behaviour and the stop-advertising
rule (`:27-36`, `:158`), but **says nothing about the device's own on-screen
indicator**. So this is **new** and does not contradict anything written.

Proposed wording for that repo (yours to place; I have written nothing there):

> **The device's "B" indicator does not track the GATT connection — OPERATOR
> REPORT, 2026-08-28.** A central connected, resolved services and enabled
> notifications on `ffe1` at 22:32:45, and the CR30's own screen showed no "B".
> It appeared only after the operator pressed the instrument's button. So the
> indicator reports *the device having sent something over BLE*, not *a central
> being attached* — and its absence must not be read by an operator (or
> documented as) "not connected".

Practical consequence for ChromIQ: an instruction that says *"wait for the B to
appear before measuring"* would be wrong, and one that says *"if there is no B,
you are not connected"* would be wrong too.

---

# PART 8 — the on-screen run: attempted, NOT achieved. Do not treat it as evidence.

Per the ON-SCREEN mandate I backed up `runs/run1/meta.json`, `project.json` and
`com.chromiq.ChromIQ.plist` to the scratchpad `backup2/`, then launched the real
app (`python main.py`) twice. Both instances started, but the captured screen
showed only the desktop — the windows were not on the captured display/Space,
and hunting for them would have meant pulling focus around on a machine where
**the user's own ChromIQ instance (pid 25723, started 22:31:27) was still
running** and had just been used for the Bluetooth test. I stopped rather than
disturb it.

Cleanup, verified: my two instances (26570, 26605) were killed with SIGKILL
(deliberately, so no `closeEvent` could write settings); pid 25723 was left
alone; `runs/run1/meta.json` and `com.chromiq.ChromIQ.plist` both `diff` clean
against the backups. Nothing of the user's was changed.

**So there is no on-screen confirmation of the reopened-project overlay in this
report.** Everything I claim about it is from code and from probes against the
real files, and I say so. Someone with the screen in front of them still has to
look — and per CLAUDE.md that person's word, not an agent's run, is what may be
written into a design specification.

One thing the settings DID settle, which is on-screen state without needing the
screen. From `~/Library/Preferences/com.chromiq.ChromIQ.plist` and
`~/ChromIQ/CR30-Test/runs/run1/meta.json`:

```
measure_only_measured            = False      (global)
measure_settings/only_measured_guided/value = False   (this run)
measure_settings/show_overlay/value         = True    (this run)
measure_settings/patch_by_patch/value       = True    (this run)
measure_overlay_mode             = "both"
```

**"Show only measured patches" was OFF**, so my S5 candidate — the whole chart
blanked white by `tiff_preview.py:2348` — is **eliminated**. And **"Show overlay
from existing measurement" was ON**, which means `a7516de1`'s bug (the `.ti1`
reference) was live in exactly this session, on exactly this checkbox. F2's live
symptom remains unexplained, but the search space is now one candidate smaller.

---

# PART 9 — the calibration-first flow: a design that survives the evidence

Basti's ruling, verbatim (11_EVIDENCE.md), with what the evidence does to each
clause:

| his words | verdict |
|---|---|
| *"i'd rather have this button being a calibration button and instructions to put the cap with the white tile on"* | **Do it.** Nothing blocks this half. |
| *"then the calibration confirmation window should appear and explain to take the cap off again and how to navigate"* | **Do it** — and note it replaces the modeless M-CR30-HOW-TO-MEASURE window, which currently cannot gate anything (`tab_measure.py:6928`, `setModal(False)`). |
| *"the calibration reading in the first window should not be counted as a measurement"* | **Already guaranteed and free** (S12). Nothing reaches the helper. |
| *"the calibration button should trigger the calibration on the instrument without the user pressing a button"* | **This is the hard one.** It requires `BB 01 00` — forbidden by `INTEGRATION.md:475-487` and by `device.py:95-118`, and impossible over BLE (S10). It also deadlocks against the armed read (S11). |

## The shape I recommend

**1. The calibration window comes BEFORE the helper is started, not after.**
Today `_open_cr30_bridge` and the helper launch are back-to-back
(`tab_measure.py:5665-5666`), and the bridge arms a read on the first
`spot_ready` within a second (Basti's log: `CR30: opened over usb` at
22:10:18,466, one second after Start). Until the calibration is finished and the
reader has released the port, **nothing may be armed**. This removes S11
entirely and is the only sequencing that is safe on both transports.

**2. USB: offer the host trigger. BLE: do not pretend.** Over BLE there is no
host trigger (`TRANSPORT_BLE.md:282`), so the button must either be absent or
say plainly that this instrument, on this connection, has to be calibrated with
its own button. Do not ship a button that silently does nothing on half the
transports — that is the same class of fault as S28 and S30.

**3. Do NOT claim to have checked the calibration.** S9 is decisive: the device
returns the firmware's canned tile constant whenever the gate engages, white
tile and green face **bit-identically** (`MEASUREMENT.md:381-397`, max abs
difference 0.0), the magnet-gate flag reads `0x00` on every host-triggered read,
there is no status query and no read-back. `INTEGRATION.md:495-499` says it in
the repo's own words: *"ChromIQ cannot tell a well-calibrated CR30 from a
badly-calibrated one, and neither can we."* Any threshold would be invented, and
the numbers in 11_EVIDENCE.md that were going to justify one are inverted (S8:
tile 78.93 %R, paper 85.84 %R — **paper is brighter than the tile**).

What you *can* honestly say to the user, and should: **"ChromIQ cannot check
this for you — the instrument reports the same value whatever is under the cap.
Make sure the white tile is facing the aperture."** That is a true sentence and
it puts the check where the only sensor is: the operator's eyes.

**4. Optional, and never mandatory** (S13). The CR30's uncalibrated behaviour has
never been measured (`CALIBRATION.md:251`, `EXPERIMENTS.md:533` — EXP-CAL-001
phase 2, never run), so no message may assert what happens without calibration;
and the only calibration failure ever observed on this hardware was *caused by
calibrating*, against the green face, undetectably. A Skip must exist.

**5. No Calibrate button during the measurement, in this cut** (S14). The drift
evidence is a single warm-up of −0.32 % relative over a few minutes
(`MEASUREMENT.md:800-801`); hours-scale drift is unmeasured and no interval is
recommended anywhere. Against that: S11 says a mid-run calibrate deadlocks or
eats the armed patch. If it is ever added, the sequence must be stop the bridge
→ release the reader → calibrate → re-arm, designed and tested as a unit.

**6. Every string goes to §M-PROPOSED first** (S21), and
`measurement_exit_strategy.md` must be extended for the new window rather than
silently contradicted — its existing "Calibration required" row (`:107`) is the
*Argyll* prompt and does not cover this. Whatever it does on screen goes into
`⏳ Awaiting confirmation` with `**Confirmed by:** *nobody yet.*` until Basti
says otherwise.

**7. Take the safety reversal to Basti explicitly.** Sending `BB 01 00`
deliberately, with a magnet deliberately present, reverses a documented decision
in two repositories. It is very probably the right call — it is his instrument,
his ruling, and EXP-MEAS-004 shows it works and is reversible (restore ratio
1.0012). But it must be *decided*, not slipped in under a UI change. That is the
project's own rule about the specifications, applied to a safety rule.

---

# FINAL RANKED SUMMARY

## BLOCKER

| # | finding | file:line |
|---|---|---|
| S30 | **The BLE read compares a measurement to itself and raises every time — a CR30 over Bluetooth cannot read one patch.** Proven with the real code. | `device.py:176-180` + `device.py:262` |
| S1/S27 | Stop/quit blocks the GUI thread on `DeviceReader._lock` for up to `button_timeout_s`; `cancel()` has **no production caller**. Reproduced twice on hardware (180.5 s, 180.0 s) and proven with a stub (3.58 s vs 0.0000 s). | `measure_bridge.py:377`, `tab_measure.py:6823-6834` |
| S28 | Unplug is silent: `except Exception: continue` swallows the dead port, and `MeasureManager.instrument_disconnected` is **declared and emitted nowhere** — a whole feature (handler + window + sound + save-partial) that cannot fire, with six tests that call it by hand. | `device.py:159-163`, `measure_manager.py:238` |
| S10/S11 | The calibration design as ruled needs `BB 01 00` (forbidden in two repos, impossible on BLE) and deadlocks against the read armed one second after Start. | `device.py:95-118`, `measure_bridge.py:214,360` |
| S8/S9 | The "detect a bad calibration" premise is factually inverted, and the device returns a canned constant — no defensible check exists. | `MEASUREMENT.md:381-397,554`, `INTEGRATION.md:495-499` |

## MAJOR

| # | finding | file:line |
|---|---|---|
| S2 | `read_failed` has no `_stopped` guard — will fire on **every** Stop once S1 is fixed, telling the user to press a button on an ended session. | `measure_bridge.py:267-270` |
| S22 | `_maybe_repair_target_instrument` reads `TARGET_INSTRUMENT` from the raw `_ti1_path` — the exact open-coded read `_chart_is_cr30`'s docstring forbids. On a reopened project the repair window never appears. | `tab_measure.py:4687` |
| S23 | `_overlay_failure_reason` has the same bug — and `a7516de1` just made it reachable, producing a confident four-paragraph *"this chart doesn't record where its patches are"* about a chart with 390 boxes. | `tab_measure.py:11448` |
| S24 | `a7516de1`'s new success test reads the accumulated preview state, not what this call painted — it can still report success when nothing from the file was shown. | `tab_measure.py` (new return) |
| S16 | Build Profile is armed by any `.ti3` — it was armed on a 3-of-390 measurement in this session. | `tab_profile.py:4019` |
| S6 | `_try_load_tiffs`'s no-TIFF branch leaves the previous chart's `_patch_boxes` in place. | `tab_measure.py:4324-4332,4349` |
| S17 | *"You have read 1 patches"* — the Save-and-stop window, the one a CR30 user reaches first. | `tab_measure.py:6014,6011` |
| S18 | Save-and-stop at zero patches writes an empty `.ti3` into the run, which then counts as measured. | `measure_manager.py` (7fa9bf2d) |
| S20 | `_no_device_help`'s ~15 user-facing sentences are not `tr()`-wrapped and are invisible to the extractor. | `measure_bridge.py:63-116` |
| S31 | Three incidents, one missing mechanism: nothing notices the instrument has gone quiet. | design |

## MINOR

S3 (a clean quit logged as an instrument failure) · S7 (one missing box loses
the overlay silently) · S19 (`_save_partial_state` latch has an unhandled exit) ·
S29 states 1–4 (save-and-stop at zero / complete / mid-goto / device absent).

## WHERE I DISAGREE WITH THE IMPLEMENTER

* **S26** — the 180 s claim was **right**, not "partially wrong". Handover #3
  measured the user's reaction time. Both incidents land on 180 s to within
  0.3 %.
* **S15** — *"Large because the instrument was never calibrated"* is unsupported
  and the evidence points the other way (the ratios show no uniform inflation).
  Take it out of `11_EVIDENCE.md`.
* **S8** — *"paper reads 81 %R, white tile ~149 %R"* is inverted. Take it out.
* **S25** — the tab-level fix in `a7516de1` is right, but it does not close the
  class; S22 and S23 are still broken.
* **S5** — F2's live symptom is **still unexplained**, and no explanation may be
  accepted that would also have killed the patch highlighter: the ring and the
  splits are drawn by the same function, from the same page, from the same
  boxes.

## STATUS

Complete for this round, except: F2's live symptom (open, needs the screen) and
the on-screen verification (attempted, not achieved — PART 8).
