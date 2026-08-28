
# 13 — VERIFY (round 3)

Branch `feature/cr30-instrument-159`, HEAD **`578c2014`**. Read-only on the repo.

> ⚠ **The tree moved under me twice.** HEAD was `73882a59` when I started;
> `578c2014` landed at 23:54 while I was reading, and it swept this report file
> into itself — twice, at 3 lines and then at 85 (the MEMORY hazard *"never
> `git add -A` while an agent is writing"*, for the third night running).
> Nothing was lost. Every line number below was re-verified against `578c2014`
> after that commit; `_run_cr30_calibration` at `:5585`,
> `_archive_measurement_before_replacing` at `:5603`, the second
> `_open_cr30_bridge` at `:5724`, `processEvents` at `:6956`,
> `_on_instrument_disconnected` at `:7343`, `MAX_READ_RETRIES` at
> `measure_bridge.py:311`.
V-numbers are mine; T/A/B/C/D/S numbers are 12_skeptic2 / 11_skeptic.

## STATUS
- [x] read 12_skeptic2, 11_skeptic, git log, diffs since 6295c91a
- [x] retry-loop attack (worry a) — V-1, PROVEN
- [x] calibration event loop (worry b) — V-13, PROVEN on screen
- [x] placement (c) V-11 ✔ · double-show (d) V-10 ✔ · _user_quit (e) V-6 · Build Profile (f) V-9/V-14 · i18n (g) V-12 ✔
- [x] on-screen run + 11 screenshots on ~/Desktop

---

## FINDINGS (running, unordered until the end)

### V-1 [BLOCKER — worry (a), PROVEN BELOW] the re-arm burns all five retries instantly on BLE after a magnet-gate refusal

`workflow/cr30/device.py:271-301`, the BLE wait loop:

```python
accepted = self._previous            # :235 — captured BEFORE the loop
prev = accepted.values if accepted else None
...
m = self.read_measurement(enforce=False)   # :281 — does NOT store _previous
if m.values != prev:
    m.check_usable(accepted)               # :298 — RAISES on the magnet gate
    self._previous = m                     # :299 — only on acceptance
```

`read_measurement(enforce=False)` never assigns `self._previous`
(`device.py:324-331` assigns only under `enforce`), and `check_usable` raises
*before* `:299`. So a refused reading leaves `self._previous` untouched.

The re-arm (`measure_bridge.py:359-360`) then calls `read_next_measurement`
again. `accepted` is the same as before, `prev` is the same, and the device is
still holding the **same offending reading**. `m.values != prev` is still True,
`check_usable(accepted)` raises the identical error — **with no button press
and no wait**. Five retries, five instant raises, `read_gave_up`.

Time cost per retry is one BLE `ask()` round trip. The user's window to take
the cap off is ~1 second, not "five presses".

**It only bites once one patch has been accepted** (`accepted is not None`).
On the very first patch of a session `accepted` is None, the baseline probe at
`:245-269` makes the offending reading the baseline, and the retry then waits
properly. So the exact case B-1 named — *cap on at patch A1* — happens to be
the ONE case that behaves; every magnet-gate refusal from patch A2 onward is
the burn.

USB is not affected: `read_next_measurement`'s USB branch waits for the
unsolicited button header (`:216`) before it reads at all, so a retry blocks on
the next press.

### V-2 [MAJOR] `DeviceReader.calibrate(timeout=30.0)` — the timeout is DEAD

`workflow/cr30/measure_bridge.py:464-496`. `timeout` is accepted, documented by
its default, and **never referenced in the body**. Neither `calibrate_white()`
nor the read-back `read_measurement(enforce=False)` is bounded.

### V-3 [MAJOR] `calibrate`'s `cancelled` is checked ONCE, before any work

Same function, `:484-485`. After that single check the call does
`self._dev.calibrate_white()` and a read-back with no further cancel test. A
Cancel pressed while the frame is in flight does nothing at all; the predicate
can only win the race before the transport is even opened. A-4 asked for the
modal's close to be "routed to the calibration's own cancel" — it is routed to
a predicate that is no longer consulted.

### V-4 [MAJOR] `calibrate`'s docstring claims a baseline it does not set

`:471-474`: *"Sharing the handle also leaves the reading this takes as the
device's `_previous`, which is exactly the baseline the Bluetooth
change-detection needs, so the first patch no longer has to establish one."*

The read-back is `read_measurement(enforce=False)` (`:493`), and
`device.py:324` assigns `_previous` **only under `enforce`**. So `_previous`
stays None and patch A1 still runs the baseline probe. The stated benefit of
sharing the handle (A-2's "bonus for free") is not delivered. Harmless in
behaviour, but it is a false claim in a docstring written to be authoritative,
and the next reader will trust it.

### V-1 PROVEN — two probes

**Device level** (`scratchpad/probe_v1.py`): a `CR30(kind="ble")` with one
accepted `_previous`, whose `read_measurement` returns the tile constant:

```
attempt 1: raised after 0.01 ms  reads so far=1  _previous unchanged=True
attempt 2: raised after 0.01 ms  reads so far=2  _previous unchanged=True
...
attempt 6: raised after 0.00 ms  reads so far=6  _previous unchanged=True
```

**Bridge level** (`scratchpad/probe_v1b.py`), the real `Cr30MeasureBridge`
with a reader that raises `MeasurementError(MAGNET_MESSAGE)`:

```
('read_failed',  'A2', 0.3 ms)
('read_failed',  'A2', 0.4 ms)
('read_failed',  'A2', 0.5 ms)
('read_failed',  'A2', 0.5 ms)
('read_failed',  'A2', 0.6 ms)
('read_gave_up', 'A2', 0.8 ms)
```

**0.8 milliseconds from the first refusal to giving up.** Five
`_on_cr30_read_failed` status flashes and five log lines the user cannot read,
then M-CR30-PATCH-GAVE-UP — whose text says *"ChromIQ has tried several times
to read patch {loc} and each attempt was refused"*. The user pressed the button
**once**. The message is not true of what happened.

In the real BLE case each retry costs one `ask()` round trip rather than 0 ms,
so the whole burn is a fraction of a second to a couple of seconds — still far
inside one human reaction.

**Fix direction (mine, not a ruling):** the retry counter is the wrong
instrument. Re-arm on *evidence of a new attempt*, not on a schedule — for BLE
that means making the refused reading the new `prev` baseline before re-arming,
so the next raise can only come from a genuinely new reading. A minimum
inter-retry delay would hide the symptom without fixing it.

---

### V-5 [BLOCKER] `_open_cr30_bridge()` runs TWICE per Start, and the second one CLOSES the instrument the calibration just opened

`ui/tabs/tab_measure.py:5585` → `_run_cr30_calibration` → `_open_cr30_bridge()`
(`:6913`) builds `DeviceReader` R1 and bridge B1; `R1.calibrate()` opens the
transport (`measure_bridge.py:486-488`) and calibrates.

`_on_start` then continues and reaches `:5719-5724`:

```python
if params.external_values:
    self._open_cr30_bridge()          # ← unconditional, second time
    self._show_cr30_measuring_window()
```

`_open_cr30_bridge` starts with `self._close_cr30_bridge()` (`:7001`), which
calls `B1.stop()` (latching `R1._cancel`) and `R1.close()` — and `close()`
**closes the device** (`measure_bridge.py:528-531`). A fresh R2/B2 is built, and
patch A1 re-opens the instrument from scratch.

So the whole of **A-2** — *"the transport must be OWNED at that moment; over BLE
a second handle means a full disconnect and reconnect of a single-connection
peripheral"* — is defeated by the caller. `DeviceReader.calibrate`'s own
docstring (`:467-474`) argues at length for sharing the handle; the code then
throws the handle away one screen later. On USB this costs seconds; on BLE it is
a disconnect and a rediscovery scan of a peripheral that stops advertising while
anything holds it, immediately after a write.

It also discards the `CR30` object, so any `_previous` baseline the calibration
established (see V-4 — there is none, but the intent was there) cannot survive.

**Fix:** guard the second call, e.g. `if self._cr30_bridge is None:`, or move the
calibration's `_open_cr30_bridge()` out of `_run_cr30_calibration` and call it
once before both.

### V-6 [MAJOR] B-3 and B-4 are NOT closed — the shared disconnect handler is untouched

The brief says *"Disconnect now routes through `_end_session(...)` not
`abort()` (B-3)"*. That is true only of the **new** CR30-only
`_on_cr30_device_lost` (`:7061-7081`). B-3's actual subject,
`_on_instrument_disconnected` (`:7343-7363`) — the handler wired to
`MeasureManager.instrument_disconnected` at `:1030`, shared by **every**
instrument — is byte-for-byte unchanged:

```python
7358	        self._log.appendPlainText(
7359	            "\n[ERROR] Instrument disconnected — stopping measurement."
7360	        )
7362	        self._manager.abort()
```

* still a **second exit**, forbidden by `measurement_exit_strategy.md:27-40`;
* the `[ERROR]` line at `:7359` is **still not `tr()`-wrapped** (B-4);
* `_show_instrument_disconnected_window` (`:7400-7403`) still says *"Please
  check the **USB** connection"* to a user whose Bluetooth link dropped (B-4);
* it is still absent from `measurement_exit_strategy.md` and from §M.

And it now interacts with the `_user_quit` change (worry e): a genuine
disconnect sets `_user_quit = True`, which suppresses
`_engine_should_fall_back` (`measure_manager.py:639`) and
`_engine_should_resume_fallback` (`:717`). The `abort()` docstring names this
caller deliberately, so it is a considered change — but it is a behaviour
change on the path shared with **i1Pro, i1iSis, ColorMunki and every other
instrument**, made in a CR30 commit, and it is not covered by any test I can
find in the diff (`tests/test_unified_ending.py` gained 16 lines; none of them
is about a disconnected non-CR30 instrument falling back).

### V-7 [MAJOR] the device-lost window offers **“Keep measuring”** on an instrument that is gone

`_on_cr30_device_lost` (`:7081`) ends with
`self._end_session(self._confirm_end_of_session(self.END_FAILURE_WINDOW))`.
`_confirm_end_of_session` (`:6060+`) adds three buttons unconditionally — the
`how` argument does not change them — and `_end_session(None)` is *"the user is
carrying on"*.

So on a CR30 whose Bluetooth link has dropped, the user is shown
M-CR30-INSTRUMENT-GONE in the log (*"Reconnect it, then start the measurement
again"*) and then a window whose third button is **“Keep measuring — closes
this window and carries on where you were.”** Pressing it returns to a session
where `_awaiting_loc` is still set, nothing is armed, and no `spot_ready` can
ever arrive again — the exact dead-session shape B-1 was raised to remove,
rebuilt by the handler written to close it.

### V-8 [MINOR] S7 was fixed on the path that already spoke

12_skeptic2's S7 row is explicit: *"`_on_chart_measured` still `continue`s
silently … Note `_on_patch_measured` (the LIVE path) does say so once per
session — so the two paths disagree, and **the static one is the quiet one**."*

The diff improves `_on_patch_measured` (`:10867-10891`) — the live path — and
leaves `_on_chart_measured` unchanged: it still `continue`s in silence when a
patch resolves to no box. A reopened project whose stored `.ti3` paints 389 of
390 patches is still silent about the one it dropped. Only the all-or-nothing
case is now caught, by S24's `drawable` count in
`_show_overlay_from_existing_ti3`.

### V-9 [OK, verified] worry (f): `{expected}` never renders as `None`

`classify` returns `PARTIAL` with `expected=None` when there is no readable
`.ti2` (`measurement_state.py:159`). `tab_profile.py:4043` guards with
`facts.expected` (truthy), so the None case falls to the `else` branch and the
tooltip is cleared. ✔

And a wrong/absent `.ti2` **cannot** cause a false *disable*: every disabling
state (`ABSENT`, `EMPTY`, `NO_DATA_BLOCK`, `UNREADABLE`) is decided from the
`.ti3` alone (`:137-149`). So `merged.ti3`, `reads/readN.ti3`, a scanner `.ti3`
and an imported i1Profiler measurement all stay buildable. ✔

One residue: `_reset_build_ui` (`tab_profile.py:4969`) still does
`self._build_btn.setEnabled(True)` unconditionally after any build, so the gate
is a load-time decision rather than a property of the file. Not reachable as a
fault today (a build requires the button to have been enabled), but it means a
second `set_ti3_path` is the only thing that can ever re-apply the gate.

### V-10 [OK, verified] worry (d): the instructions window is shown exactly once, on every route

`_cr30_how_shown` is reset at `:5574`, above the calibration block, and
`_show_cr30_measuring_window` (`:7132-7134`) sets it on entry.

| route | shown by | second call at :5725 |
|---|---|---|
| Guided / Manual, calibration accepted | `_run_cr30_calibration` (`:6990`) | returns early ✔ |
| `disable_initial_cal` ticked (Manual) | `:5725` | — ✔ |
| calibration **cancelled** | nobody | unreachable (`return` at `:5591`) ✔ |
| calibration **failed** | nobody | unreachable ✔ |
| no reader could be built | `:5725` (`_run_cr30_calibration` returns True) | ✔ |
| resume / refine | same as above — resume is a checkbox inside `_collect_params` | ✔ |

### V-11 [OK, verified] worry (c): the placement is right

`_confirm_replacing_measurement()` at `:5551`, the calibration at `:5575`,
`_archive_measurement_before_replacing()` at `:5603`. Nothing irreversible sits
between them, and the Cancel path (`:5586-5591`) disarms the sound before
returning — A-1 satisfied.

Two caveats:
* `_snapshot_verification_chart()` at `:5545` runs **before** the calibration
  and *can* replace this run's stored verification chart after asking. A user
  who says yes there and then cancels the calibration has changed the run.
  Narrow (verification runs only) and it asked first, so MINOR.
* `self._sound.disarm()` at `:5586` is unguarded while `:5508` guards
  `getattr(self, "_sound", None) is not None`. `_sound` is assigned
  unconditionally at `:1066`, so this cannot fire today — but the two lines
  disagree about whether it can be None.

### V-12 [OK, verified] worry (g): i18n

* `pytest tests/test_i18n.py tests/test_message_catalogue.py
  tests/test_design_specs_are_binding.py` → **123 passed**.
* `scripts/i18n_extract.py --missing de` → `# 0 missing of 4578`; same for `fr`.
* Every new string is a `tr("literal")`, including the two arms of the
  conditional `-N` NOTE at `:5742-5758`, so none is invisible to the extractor.
* Layering holds, proven: `python -c "import workflow.cr30"` →
  `Qt modules: []`, `serial/bleak: []`. `_no_device_help`'s
  `from core.i18n import tr` is function-local and `core/i18n.py` imports only
  `json/re/string/pathlib/typing/core.logger/core.resource_path`.
  `_no_device_help("usbX","bleY")` renders correctly with no `QApplication`.

---

### V-13 [BLOCKER — worry (b), PROVEN] the `processEvents` loop lets the user start a SECOND measurement, and lets the transport be closed under a running calibration

`ui/tabs/tab_measure.py:6963-6968`:

```python
thread.start()
self._cal_thread, self._cal_worker = thread, worker
while not thread.isFinished():
    QApplication.processEvents()
    thread.wait(20)
```

The calibration correctly runs off the GUI thread (A-4 satisfied — the worker
thread shows as `Dummy-1` in the trace below). But the loop it waits in is a
**nested event loop with no modality**, and at that point in `_on_start` the
Start button has not yet been disabled (that happens at `:5691`, far below).

**Proven with the real window, real settings, his own CR30-Test chart**
(`scratchpad/drive_reentrancy.py`; the calibration is a 3-second no-op stub —
no hardware command was sent):

```
 0.72s  _run_cr30_calibration ENTER
 0.74s  MODAL  "Calibrate your CR30 before measuring"
 0.96s  calibrate ENTER                     (thread Dummy-1 — off the GUI thread ✔)
 1.21s  --- user presses START again  start_enabled=True  stop_enabled=False
 1.22s  MODAL  "This run already holds part of a measurement"   ← A SECOND START
 1.74s  --- mid-calibration: user clicks things  start_enabled=True
 1.76s  MODAL  "This run already holds part of a measurement"
 1.98s  reader.close()                      ← THE TRANSPORT IS CLOSED
 3.97s  calibrate EXIT                      ← the frame was still in flight
 4.01s  _run_cr30_calibration returned True
```

Three separate faults in one trace:

1. **Start is live during the calibration.** `_on_start`'s only re-entry guard
   is `if self._runner.is_running: return` (`:5485`) — and the helper has not
   been started yet, so it does not fire. A second `_on_start` runs to
   completion: if the user accepts the replace question it will
   `_archive_measurement_before_replacing()` and `_manager.start()` **while the
   first calibration is still writing to the instrument**.
2. **`reader.close()` at 1.98 s closed the transport two seconds before the
   calibration finished.** That is A-4's named risk, reached here by
   `_close_cr30_bridge()` — which is what closing the tab does, what quitting
   does, and what `_open_cr30_bridge()` does every time it is called. `close()`
   sets `_cancel` (which `calibrate` does not consult — V-3) and takes the lock
   with `timeout=2.0`; it does not wait, it closes anyway.
3. **The calibration window itself is gone by then.** `box.exec()` has already
   returned; there is no window to be modal, and nothing on screen says a
   calibration is in progress. The user sees an idle tab with a live Start
   button for 2-30 seconds.

**Fix direction:** disable Start (and ideally the whole tab) for the duration,
or keep a modal progress window up while the worker runs and route its close to
a cancel the worker actually checks. The `while processEvents()` idiom itself is
the wrong shape here — `QEventLoop` with the window as its only interaction
point would be the standard one.

### V-14 [MAJOR] S16/C-2 landed as a TOOLTIP and nothing else — the count is invisible

Verified on screen (`~/Desktop/cr30_verify_5_build_profile_tooltip_window.png`
and `_9_build_profile_tooltip.png`). On a 17-of-390 measurement the Build
Profile tab shows:

> **Ready to build?** · *Awaiting your command.* · **[ BUILD PROFILE ]** (enabled)

and the file row shows only the path. The "17 of 390" fact exists **only in the
button's tooltip**, which requires the user to hover and wait.

12_skeptic2's C-2 asked for two things this does not do:

* *"the file label carries the count: **'217 of 390 patches measured'**"* — it
  does not; `self._file_lbl.setText(str(path))` (`tab_profile.py:4018`) is
  unchanged.
* *"Pressing Build raises a §M confirmation naming both numbers … with
  **Measure the rest / Build anyway / Cancel**"* — there is none. `grep` in
  `_on_build` finds no `classify`, no `QMessageBox`, no use of the facts.

And `self._ti3_facts = facts` (`:4033`) is **dead state**: nothing anywhere
reads it. The refusal half (EMPTY → disabled) is implemented; the *informing*
half, which is the half C-2 exists for, reaches the user only if they hover.

The tooltip wording itself is good and the numbers are right:

> *"This measurement holds 17 of the chart's 390 patches. You can build a
> profile from it, but a profile made from part of a chart describes your
> printer only where it was measured. To fill in the rest, go back to Measure
> and tick 'Refine / resume existing measurement'."*

### V-15 [MAJOR] `docs/design/measurement_exit_strategy.md` was not touched

`git diff 6295c91a..HEAD -- docs/design/` → **only**
`unified_measurement_management.md` (109 insertions). A-9 required
`measurement_exit_strategy.md` to be *extended* for the new window; B-4 required
the disconnect window to be added to its table. `grep -i "cr30\|calibrate"` on
that file returns nothing.

So a document whose stated job is *"every window that can end a measurement, and
the key each button sends"* now omits: M-CR30-INSTRUMENT-GONE (which routes into
`_confirm_end_of_session` — unambiguously an ending window), the pre-existing
"Instrument Disconnected" window (B-4, still missing), and the new calibration
window (whose Cancel prevents a session rather than ending one — arguably out of
scope, but that is a judgement someone should record).

The §M side, by contrast, IS done properly: M-CR30-CALIBRATE,
M-CR30-INSTRUMENT-GONE and M-CR30-PATCH-GAVE-UP are all in §M-PROPOSED with
`approved=False`, in the awaiting-review header, with their evidence. ✔

### V-16 [MINOR] two of the new tests pass *because of* the faults above

* `tests/test_cr30_calibrates_before_measuring.py::test_it_calibrates_through_the_session_reader`
  asserts `_open_cr30_bridge` and `_cr30_reader` appear in
  `_run_cr30_calibration` and that it does not call `CR30.open`. All true — and
  it says nothing about the bridge being torn down and rebuilt 40 lines later
  (V-5). The test asserts the intent and misses the defeat.
* `tests/test_cr30_measure_bridge.py::test_a_refused_reading_re_arms_so_the_session_survives`
  uses a harness whose `_read` raises **instantly**, asserts
  `len(h.read_calls) > 1` and `h.gave_up`, and passes. That is exactly the
  V-1 burn — the test encodes the instant five-retry sequence as correct.
  A `time.monotonic()` assertion, or a reader that only fails N times and then
  succeeds, would separate "re-armed" from "re-armed usefully".

### V-17 [CORRECTED — I was wrong] a patch that gave up is NOT permanently dead

I hypothesised the retry counter would make an abandoned patch unreadable for
the rest of the session. **Disproved** (`scratchpad/probe_v1c.py`):

```
1) A2 armed, reader refusing → 5×read_failed + gave_up, retries {'A2': 6}
2) reader now works; a duplicate spot_ready for A2 → value sent, retries {}
3) goto B1 → B1 reads fine
4) jump BACK to A2 → value sent, retries {}
```

`_on_reading` clears the counter on success (`measure_bridge.py:376`), and
`on_patch_ready`'s duplicate-prompt guard (`:239`) does not block a re-prompt
after a failure because `_reading_loc` was cleared. So **click-to-jump on the
preview is a working way back**, and so is any command that makes the helper
re-prompt.

**But M-CR30-PATCH-GAVE-UP does not mention it.** It says *"end this session
with 'Save and stop' and start it again with 'Refine / resume existing
measurement' ticked"* — the most disruptive of the available answers, when
clicking the patch in the preview would have done. Worth one sentence.

### V-18 [MINOR] a cancelled calibration leaves the bridge and the reader standing

`_run_cr30_calibration` calls `_open_cr30_bridge()` before the window and never
undoes it on any of its three exits (Cancel, calibration failed, no reader). So
after a Cancel the tab sits idle with `self._cr30_bridge` and
`self._cr30_reader` non-None. Proven on screen: TEST B's first
`_close_cr30_bridge` closed a reader left over from TEST A's Cancel (2 closes
for 2 constructions in one Start).

Harmless today because `DeviceReader` opens lazily — **except on the calibration
FAILED path**, where the device was opened, the trigger failed, and the
transport stays held until the next Start. On BLE that means the instrument
keeps advertising as taken.

### V-19 [MINOR, seen on screen] E-3 is still open: the pace panel tells a CR30 user to swipe

`~/Desktop/cr30_verify_1_window_measure_tab.png`, bottom-left of the panel, on a
CR30 chart:

> **Keep calm!** · *Scan each strip with a slow, steady motion.*

Unchanged since 12_skeptic2 filed it. The preview already suppresses the arrow
for exactly this reason (`tiff_preview.py:1490`).

### V-20 [MINOR] "Calibrate now" is the DEFAULT button

`tab_measure.py:6942` `box.setDefaultButton(go)`. The window's whole argument is
*"Your eyes are the only check there is"*, and the accident it warns about
(calibrating against the cap's green face) is invisible afterwards and corrupts
the unit. Making the irreversible action the Enter-key default is the wrong
default for a window that exists to make the user look first. `DialogFocusFilter`
protects the space bar, not Return.

### V-21 [OK] A-6's consequences 2 and 3 ARE addressed — the brief's own open list is stale

* The `-N` log NOTE now branches on `params.external_values` (`:5734-5758`) and
  the CR30 arm no longer mentions a chartread prompt.
* Both Skip tooltips (`:2051-2056` guided, `:2532-2537` manual) gained a
  paragraph naming the CR30 case.

Both were listed as still open in the brief. They are not.

### V-22 [OK] S19 is as narrow as believed

`_save_partial_state` is cleared in `_on_finish` (`measure_manager.py:427`), and
its only consumer is `_on_instrument_disconnected`'s deferral (`:7350`). So the
stuck-latch window is "from `d` until the process exits", and during it the
handler correctly defers rather than killing the save chain. Not worth fixing.

### V-23 [OPEN, unchanged] B-5 (`bridge.is_reading`) and S29(3) were not implemented

`grep -n "is_reading"` in `measure_bridge.py` and `tab_measure.py` → nothing.
There is no watchdog. Of B-5's three silences the branch now covers two by
signal (`DeviceLost` → `device_lost`; a failed read → re-arm), and leaves the
third — *the instrument was switched off BEFORE Start* — going through the
generic re-arm path, where `_open()`'s `ConnectionError` (`measure_bridge.py:444`)
is not a `DeviceLost`, so it burns five retries and reports
M-CR30-PATCH-GAVE-UP: *"the magnetic cap is still on the instrument"*, to a user
whose instrument is switched off. **That is a wrong message on a reachable
path**, and it is the direct cost of routing every non-`DeviceLost` failure
through the retry arm.

`save_partial_and_quit` during an outstanding `goto` (S29 state 3) is still
unguarded and untested.

### V-24 [UNCHANGED] D: the live overlay is correct, and at 17 of 390 it is still barely legible

Re-proved on screen with his own chart and his own 17-patch `.ti3`:
`_show_overlay_from_existing_ti3()` → True, `overlay={0: 17}`, 5,174 sampled
pixels changed, `boxes=390`. `~/Desktop/cr30_verify_6_overlay_preview.png` shows
the splits, clustered in column A. In the full window
(`_7_window_with_overlay.png`) they are hard to find. 12_skeptic2's D-2 stands
and is still unaddressed.

### V-23 PROVEN — an instrument that is switched OFF is told its cap is on

`scratchpad/probe_v23.py`, real `Cr30MeasureBridge`, reader raising the real
`ConnectionError(_no_device_help(...))` that `DeviceReader._open` raises
(`measure_bridge.py:444`):

```
routed to device_lost?  False
routed to read_gave_up? True after 2428 ms

WHAT THE USER IS TOLD:
  That patch could not be read
  ChromIQ has tried several times to read patch A1 and each attempt was refused…
  The two things that cause this, and both are quick to check:
  •  The magnetic cap is still on the instrument…
  •  The instrument was lifted before it had finished…
```

**Neither is true.** The instrument is not connected. The correct advice — the
excellent `_no_device_help` text, which leads with *"Switch the instrument off
and on again"* — is present, but only as `{reason}` at the very bottom, after
two confident wrong causes.

`ConnectionError` is not `DeviceLost`, so it goes down the retry arm. This is the
S28 fault ("the wrong message for an instrument that is not there") re-created
one layer up by the fix for B-1. `DeviceReader.__call__` should wrap `_open`'s
failure in `DeviceLost` — the module's own docstring already calls that "the
instrument is not there".

---

# RANKED SUMMARY

## BLOCKER

| # | finding | file:line | proof |
|---|---|---|---|
| **V-1** | the re-arm burns all five retries in **0.8 ms** after one magnet-gate refusal on BLE, then says *"ChromIQ has tried several times"* to a user who pressed once. Bites from patch A2 onward (patch A1 is the one case that behaves). | `device.py:271-301`, `measure_bridge.py:349-360` | 2 probes |
| **V-13** | the calibration's `processEvents` loop leaves **Start enabled and clickable**; a second `_on_start` runs to completion during the calibration, and `reader.close()` closes the transport under a running frame (A-4's named risk) | `tab_measure.py:6955-6959`, `:5485` | on-screen trace |
| **V-5** | `_open_cr30_bridge()` runs **twice per Start** — the second call closes the instrument the calibration just opened and builds a new `DeviceReader`, defeating all of A-2 | `tab_measure.py:5585`, `:5724`, `:7001` | on screen: 2 readers, 2 closes |
| **V-23** | an instrument that is **switched off before Start** is told its magnetic cap is on. `ConnectionError` is not `DeviceLost`, so it takes the retry arm. | `measure_bridge.py:444`, `:326` | probe |

## MAJOR

| # | finding | file:line |
|---|---|---|
| **V-6** | B-3/B-4 are **not closed**: `_on_instrument_disconnected` still calls `abort()` (a second exit), still has an untranslated `[ERROR]` line, still says "check the USB connection". A new CR30-only route was added beside it. And it now sets `_user_quit`, suppressing the engine fallback for every instrument. | `tab_measure.py:7343-7363`, `:7400`, `measure_manager.py:639,717` |
| **V-7** | the device-lost window offers **"Keep measuring"** on an instrument that is gone; choosing it leaves `_session_live = True` with nothing armed | `tab_measure.py:7081`, `:6060+` |
| **V-14** | S16/C-2's *informing* half is a **tooltip only** — no file-label count, no build-time confirmation, and `_ti3_facts` is dead state | `tab_profile.py:4018,4033,4043` |
| **V-2** | `DeviceReader.calibrate(timeout=30.0)` — `timeout` is never used; the call is unbounded | `measure_bridge.py:464-496` |
| **V-3** | `calibrate`'s `cancelled` is checked once before the work; the only caller passes none at all (`reader.calibrate()`), so there is no cancel once it starts | `measure_bridge.py:484`, `tab_measure.py:6947` |
| **V-15** | `measurement_exit_strategy.md` untouched — A-9 and B-4 both required it | `docs/design/` |
| **V-4** | `calibrate`'s docstring claims it leaves a `_previous` baseline; `read_measurement(enforce=False)` does not set one | `measure_bridge.py:471-474` vs `device.py:324` |

## MINOR

| # | finding |
|---|---|
| V-16 | two new tests pass *because of* V-1 and V-5 — they assert the intent and miss the defeat |
| V-8 | S7 was fixed on `_on_patch_measured` (which already spoke); `_on_chart_measured`, the path skeptic2 named, still drops patches in silence |
| V-17 | M-CR30-PATCH-GAVE-UP omits the working recovery (click the patch in the preview) and offers only the most disruptive one |
| V-18 | a cancelled or failed calibration leaves the bridge and reader standing; on the failed path the transport stays open |
| V-19 | E-3 still open — the pace panel tells a CR30 user to "scan each strip with a slow, steady motion" |
| V-20 | "Calibrate now" is the default button in a window whose point is "look before you press" |
| V-11b | `self._sound.disarm()` (`:5586`) is unguarded while `:5508` guards `_sound` for None |
| V-11c | `_snapshot_verification_chart()` (`:5545`) can change a verification run before the calibration window opens |

## VERIFIED GOOD

* **A-1 — the placement is right, and Cancel costs nothing.** Proven on screen
  against a copy of his own CR30-Test: `.ti3` md5 identical, `old/` 3 → 3,
  **no file in the run folder changed**, Start still enabled, Stop still
  disabled, `_session_live` not set, instructions window not shown. (V-11)
* **A-4's threading requirement** — the calibration runs on a real QThread
  (`Dummy-1` in the trace), not on the GUI thread.
* **A-3 — the one-way latch is respected.** `calibrate` takes its own
  `cancelled` and never touches `_cancel`. (Its cancel is then useless — V-3 —
  but the latch is safe.)
* **A-6 — `params.disable_initial_cal`, never the widget.** Verified in source
  and by test. Consequences 2 and 3 also done (V-21).
* **The instructions window is shown exactly once on every route** (V-10),
  proven on screen.
* **§M discipline** — three new messages, all `approved=False`, all in
  `unified_measurement_management.md`'s awaiting-review header with their
  evidence. `tests/test_message_catalogue.py` and
  `test_design_specs_are_binding.py` pass.
* **i18n** — 123 tests pass, `--missing de` and `--missing fr` both 0 of 4578,
  every new string a literal, layering intact (`import workflow.cr30` pulls in
  no Qt and no pyserial). (V-12)
* **T-2** — the `except DeviceLost: raise` guard is correctly placed in the BLE
  baseline probe (`device.py:254-259`), and the main BLE loop's
  `except MeasurementError: raise` covers it by construction.
* **Build Profile gating cannot false-disable** a merged / averaged / scanner /
  imported `.ti3`, and never renders `{expected}` as `None`. (V-9)
* **The split-patch overlay still paints** — 17 patches, 5,174 pixels, on his
  own reopened project. (V-24)
* **S19** is as narrow as believed. (V-22)

## ON-SCREEN RUN — method and safety

Real `QApplication` with the real fonts, `WinButtonLayoutStyle("Fusion")`,
`CompositeAppFilter`, `apply_appearance`, his real plist copied into a sandbox
`.ini`, real `MainWindow`, real `TabMeasure` / `TabProfile`, and
`~/ChromIQ/CR30-Test` **copied** into a sandbox `custom_output_path`. Captured
with `widget.grab()`. `DeviceReader.calibrate` and `__call__` were replaced with
recorders **before** any window opened, so no byte ever reached the instrument.
Every modal was answered by the driver; none was left waiting.

* `~/Library/Preferences/com.chromiq.ChromIQ.plist` md5
  `ad1496831bc929ba9acf01e21c68a8da` **before and after all four runs**.
* `~/ChromIQ/CR30-Test` byte-identical before and after (full recursive md5).

Screenshots on `~/Desktop`, prefixed `cr30_verify_`:

| file | what it shows |
|---|---|
| `1_window_measure_tab.png` | the whole window, CR30-Test loaded, 390 hexagons, Progress 4.4 % — and the "scan each strip" caption (V-19) |
| `modal_1_QMessageBox.png` | **the calibration window**, rendered |
| `2_after_cancel.png` | the tab after Cancel — unchanged, Start live |
| `3_after_calibrate_now.png` | after "Calibrate now" |
| `8_how_to_measure_window.png` | M-CR30-HOW-TO-MEASURE, shown once |
| `4_build_profile_partial.png` | Build Profile enabled on 17 of 390, "Ready to build?" |
| `9_build_profile_tooltip.png` | the tooltip that carries the only visible count |
| `10_device_lost_window.png` | **the device-lost window offering "Keep measuring"** (V-7) |
| `6_overlay_preview.png`, `7_window_with_overlay.png` | the split-patch overlay, 17 of 390 |
| `notes.txt` | the PASS/FAIL table |

## STATUS
Complete.
