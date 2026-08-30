# CR30 beta 1 — challenge round 3 ([CR30-B3])

**Scope:** commits `583dd306..ec2bf4f3` on `feature/cr30-instrument-159`, hostile review before 4.1.5 beta 1 —
**extended to `e7eb81f9`**, which landed mid-review (the tree moved under me; every citation below was re-checked against `e7eb81f9`).
`core/version.py` is committed at 4.1.5-beta.1; by review's end the implementer
session had further uncommitted work in the tree (`ui/widgets.py`).
**Status: COMPLETE.**

> ⚠ A note on a red run that was NOT real: my first run of `tests/test_i18n.py`
> failed 24 tests (6 untranslated CR30 keys, stale keys, every language). That
> was the half-written mid-commit state of `e7eb81f9` being read while the
> implementer session was committing. At `e7eb81f9` the same files pass, alone
> and in the original combination (136 passed, run here twice). Not a finding —
> recorded so nobody chases it.

## Verdict

**No hard blocker. The `--runslow` gate is GREEN at `e7eb81f9`: 8196 passed,
0 failed, 2:50, run here** (everyday tier likewise: 8075 passed, 1:24) — with
one caveat: the implementer session wrote `ui/widgets.py` (a new
`order_message_box_buttons` helper, uncommitted) at 05:32, DURING my gate run.
It passed anyway, but the tree is still moving; the release-process gate at the
actual tag commit remains required and is the one that counts. And
`core/version.py` is committed at 4.1.5-beta.1. The work since 28 is largely
real and holds under attack — the remembered address, `allow_dark`'s
containment, the magnet loop, the read-failure window, the pictograms, and the
driver guards all survived. Field evidence in the owner's own log proves the
address skip (`found in 0.00 s`) and — against the newest commit's own caveat —
the white read-back fix on hardware.

**One regression must be named: `e7eb81f9` reintroduced the "Keep measuring"
dead end at the NEW device-lost window (R1, proven failing with 2/2 scratchpad
tests against the real handler), the very fault class 28 called B2-a and 29
fixed at the magnet window.** With R1 (plus its wording twin R2), the
button-name mismatch E2, and the strips banner E1 fixed — about an hour's work
— beta 1 is ready. Shipping tonight with them named in the notes would also be
defensible; that call is Basti's.

## 1. Remembered Bluetooth address

**The core mechanism holds.** Verified against the real code (`measure_bridge.py:613-673`,
`ble.py:198-231`) and the real tests (`tests/test_cr30_bluetooth_remembers_the_address.py`,
run here, all pass):

* **Migration/existing users:** the key (`cr30_ble_address`) is simply absent →
  `get(..., "")` → `""` → `str("") or None` → None → scan, exactly the old
  behaviour. No migration needed; verified no other writer exists (grep: only
  `_remember_address`).
* **Garbage/non-string stored value:** `str(value) or None` stringifies
  anything; a garbage address fails to connect, falls back to the scan, and the
  scan's success **overwrites** the garbage (`_open_ble` remembers on both
  paths). A raising settings store is caught in both directions
  (`measure_bridge.py:622-626, 637-638`) and there is a test for the
  constructor raising. No loop: `_open_ble` has exactly one fallback level and
  no recursion.
* **Swapped units / another Mac:** falls back and re-remembers — tested
  (`test_a_stale_address_falls_back_to_scanning`,
  `test_the_fallback_replaces_the_stale_address`).
* **`_previous`/baseline unaffected;** the address never touches protocol state.
* **`AppSettings()` per open:** one `QSettings("ChromIQ","ChromIQ")` per
  session open, on the bridge worker thread. QSettings is reentrant and
  documented safe off the main thread; cost is a file parse per open, once per
  session. Not a hazard I could demonstrate.

**Faults found, none blocking:**

* **F1-a (latent, wrong when it activates): an explicit `address=` retries
  itself and lies about it.** `_open_ble` sets
  `remembered = self._address or self._remembered_address()`; on failure it
  logs *"searching for the instrument instead"* and then calls
  `CR30.open_ble(address=self._address)` — the **same** explicit address again,
  not a search (`measure_bridge.py:657-667`). Today `DeviceReader()` is only
  ever built bare (`tab_measure.py:7333`), so this is unreachable — but
  `test_an_explicit_address_still_wins` only checks `calls[0]` and would stay
  green over the doubled failure. Fix when the address ever gets a UI.
* **F1-b (real cost, worth knowing): a stale address is 20 s, not "one failed
  connection".** `BleTransport` default `timeout=20.0`; on macOS
  `BleakClient(uuid)` with an unknown UUID scans for it up to that timeout
  before raising. Swap-units/new-Mac worst case ≈ 20 s + the old 13-15 s scan —
  slower than never having the hint. Recovers correctly (and re-remembers), so
  it is a one-time cost per stale address, but the docstring's "one failed
  connection" reads cheaper than it is.
* **F1-c (edge, pre-existing shape made more reachable): a half-open BLE
  connection can leak on a failed open.** In `BleTransport.open` there is no
  cleanup between `await c.connect()` and `await c.start_notify(...)`
  (`ble.py:206-210`): if `start_notify` raises, the connected `BleakClient` is
  orphaned (never assigned to `self._client`, never disconnected), and — since
  the CR30 accepts one central and stops advertising while held — the fallback
  scan then reports *"No CR30 found over Bluetooth… disconnect the phone app"*,
  blaming the phone for a connection we are holding. Needs connect-success +
  notify-failure, so rare; but the remembered-address path adds a new way in
  (connecting to whatever now answers at the stored address). A
  try/except-disconnect around `start_notify` closes it. The per-failure
  asyncio loop object also leaks (never closed); cosmetic.

## 2. `allow_dark` and the truncated-reply guard

**No patch path can reach it — proven by enumeration.** Every caller of
`read_measurement` at head:

| caller | enforce | allow_dark | path |
|---|---|---|---|
| `device.py:333` (USB button read) | True | False | patch |
| `device.py:409` `_read_when_ready` | False | **False** | patch (BLE) |
| `measure_bridge.py:796` white-cal read-back | False | True | calibration, result **discarded** |
| `measure_bridge.py:860` `_read_after_trigger` (black zero check) | False | True | calibration, mean only |

`allow_dark` defaults False everywhere, `_parse_reply`'s guard is
`not allow_dark and probe.zero_run() >= 3` (`device.py:53`, `:518`) — the
patch-side zero-run rejection is byte-for-byte what it was.

**`self._previous` cannot be poisoned.** `self._previous = m` sits inside
`if enforce:` on both transports (`device.py:477-483`, `:550-554`); both
`allow_dark=True` callers pass `enforce=False`, so a zero-filled read-back
never becomes the bit-identical baseline. Tested this reasoning against the
real code, not the report's memory of it.

**`enforce=False` interaction:** on the BLE patch path the enforcement happens
one level up (`read_next_measurement`: `m.check_usable(self._previous);
self._previous = m`, `device.py:392-393`), so nothing weakened there.

**The one sharp edge, honestly stated (cannot be settled from this desk):**
in `read_zero` the accepted zero IS the check's datum. The commit's safety
argument ("a truncated reply reads zero, the passing direction") covers the
white read-back, whose result is discarded — but for the black zero check a
zero accepted **too early** (the device's known "not finished yet" zero-fill,
the very thing `_read_when_ready`'s docstring documents) would pass the check
in exactly the obstruction case it exists to catch. Two mitigations are real:
`trigger_unsafe` waits for the instrument's own "I acted" event before the
read (`device.py:181-182`), and EXP-BLE-012 shows ack-then-read returning the
real moved value. And the check's messages hedge correctly ("Nothing wrong was
seen — that is not the same as verified", `tab_measure.py:7250`). But the
warning branch — obstruction present, warning fires — **has never run on any
hardware**: before this commit the read-back always failed (check dead), and
the commit itself says the read-back fix is unexercised. **Owner's log evidence (read, not run — no hardware command was sent):** the
04:51:28 session postdates ec2bf4f3 (04:49:55): white answered 04:51:28.9,
black 04:51:33.9 — 5.0 s apart, into which the old 12 s failure loop cannot
fit — and the helper started 2.2 s after the black, so `read_zero` returned
promptly too. **Both happy paths are hardware-proven.** What has never run on
any hardware is the WARNING branch — a deliberate obstruction during the black
calibration. Until someone does that and sees the [WARNING], the honest claim
is "the check now runs and passes on air", not "the check catches the fault it
exists for". One five-second hardware test closes this.

**Stale docstring found:** `DeviceReader.calibrate` still promises the shared
handle "leaves the reading this takes as the device's `_previous`, which is
exactly the baseline the Bluetooth change-detection needs"
(`measure_bridge.py:745-751`). False on two counts at head: the read-back is
`enforce=False` so `_previous` is never set from it, and BLE no longer waits by
change-detection at all (event-based since EXP-BLE-013). Pre-existing (the
enforce=False was already there at 583dd306), harmless today, but it is
precisely the "false docstring" class the backlog names — and the white
read-back loop's own comment ("so the device's stored value is known to us")
describes a purpose the code no longer delivers: the value is discarded.
The loop's remaining effect is a liveness probe of one exchange.

## 3. White read-back loop / 12 s deadline

* **Was the deadline load-bearing?** No. The loop's result was always discarded
  (`enforce=False` predates these commits), so nothing consumed the time it
  bought; the 12 s was pure waiting for a rejection that was structural. The
  deadline now only bounds the pathological retry case.
* **Termination on an absent device:** the loop is unreachable with a dead
  link — `self._dev.calibrate(black=black)` raises first
  (`measure_bridge.py:772`) and the exception propagates to the tab's error
  window. If the link dies between calibrate and read-back, every raise is
  caught and the `monotonic() > deadline` check breaks the loop
  (`measure_bridge.py:798-803`). Bounded either way. Could not fault it.

## 4. Magnet loop and `resume_after_magnet`

**28's B2-a is really fixed.** The handler is now a loop
(`tab_measure.py:7611-7648`): "Keep measuring" (choice None from the ending
window) logs "still stopped: nothing can be read until the white calibration
has been taken again" and re-shows the magnet window. Two exits only —
recalibrate (break → resume) or a real ending (return). The dead end is gone.

**The non-vacuous return is honest in both directions.** Not stopped →
`self._awaiting_loc is not None and self.armed_for(self._awaiting_loc)`
(`measure_bridge.py:366-368`): a rebuilt bridge has `_awaiting_loc=None` →
False → no false "Carrying on" line. Stopped → `rearm()`, and `rearm` cannot
lie "already reading it" over a dead read because `_on_read_failed` clears
`_reading_loc` before emitting `magnet_gated` (`measure_bridge.py:464-465`).
28's suspected helper-dies-during-modal edge is closed at the source, as 29
claims.

**Spin/re-entry/stacking — attacked, holds:**
* Each loop iteration requires a click (`box.exec()`); no unattended spin.
* No re-entrant `magnet_gated` is possible while the box is up: the bridge is
  `_stopped`, only one read exists at a time, and the recovery calibration path
  never runs `check_usable` (enforce=False), so nothing can raise MagnetGated
  during it.
* Windows are sequential (magnet box closes before the ending window opens
  before the magnet box returns), not stacked.
* A cancelled recovery calibration falls into `_end_after_magnet()` rather than
  silently looping — deliberate, and the log line covers the None case.

**Two honest residuals, not blockers:**
* Closing the magnet window via the red traffic light / Esc
  (`clickedButton()` None → not `again`) drops the user into the
  end-of-session window. Defensible under "two doors only", but note the same
  team ruled at the black-calibration window that *"closing a window is a
  withdrawal, never a consent"* — here a withdrawal is answered with the
  ending offer. Consistent enough (declining that returns to the magnet
  window; nothing is consented on the user's behalf), so recorded as a
  design observation, not a fault.
* If `resume_after_magnet()` returns False after a successful recalibration
  (only reachable when the bridge was rebuilt underneath, i.e. the session
  already ended through `_on_measure_done`), the user gets no line at all.
  Honest silence over a session whose ending they already saw; acceptable.

## 5. Read-failure window and `_close_read_failed_window_if_moved_on`

**28's B2-b is fixed:** `_on_cr30_gave_up` now closes the window first
(`tab_measure.py:7716-7722`), so the "press the button again" advice cannot
outlive the give-up.

**The close-on-moved-on predicate (`tab_measure.py:7511-7538`) — attacked at
the edges:**
* Chart end: same loc + `all_done` → closes. ✔
* Goto: the next prompt names a different loc → closes; a goto BACK to the very
  patch (same loc, no flags) keeps the window — correct, the reading is still
  owed. ✔
* Stop/ending: registered in `_live_measure_windows`, closed by the ending
  (`tab_measure.py:7496`), and `_gone` clears both the reference and the
  per-patch flag on every close path so the once-per-patch latch cannot leak
  across windows. ✔
* A `patch_ready` with `read` set for the same loc → closes — right, the
  reading exists.
* Degenerate event without a loc would close it (`waiting_for != ""`);
  reachable only from a malformed helper event, and closing is the safe
  direction.

**27's held-back rich-text fix is applied and correct:** the body is
`html.escape`d BEFORE the `\n\n → <br><br>` substitution
(`tab_measure.py:7477-7484`). Order is right; a `<` or `&` in a future
instrument sentence renders as text.

Could not fault this area.

## 6. Driver guards (Windows-only, read on macOS)

All claims here are code-reading plus tests run on macOS — no Windows host.

**Could not fault the structure.** `VENDOR_SERIAL_DEVICES` is a separate table
(`usb_driver_installer.py:91-93`), never merged; `is_vendor_serial` lowercases
both ids; `install_winusb` refuses BEFORE `_wdi_simple_path()` is consulted —
and that ordering is the load-bearing, host-independent test
(`test_the_refusal_comes_before_anything_is_launched`), with the direct-refusal
test honestly documenting that it passes for the wrong reason off-Windows. The
two-table overlap test makes the guarantee structural. All three Zadig steers
carry the CR30 warning; the `(s)` plurals in the driver dialog are fixed and
pinned by a test.

**Two soft spots, neither blocking:**
* The steer-counting test counts two exact phrases ("List All Devices",
  "Select your colorimeter, choose WinUSB"). A fourth steer that paraphrases is
  not counted — 29's "a fourth cannot be added silently" holds only for
  copy-paste additions.
* The refusal returns plain `False`, indistinguishable from a failed install;
  in the dialog's batch loop a refused CR30 would surface as "install failed"
  rather than "refused for your own protection". Cosmetic, Windows-only,
  unverifiable from here.

## 7. Pictograms — on the real screen, both themes, looked at

Rendered the real windows (real `M_CR30_CALIBRATE` / `M_CR30_CALIBRATE_BLACK`
text, real `steps_pair`, the app's own stylesheet via `apply_appearance`) in
dark and light, and drove the REAL white window in the real app (shot
`b3v2_0_msgbox.png`). Looked at every shot.

* **Tick: gone.** No checkmark in any window. (`_draw_tick` is now dead code in
  `ui/cr30_pictograms.py` — harmless, but it is the corpse of the removed
  feature; delete at leisure.)
* **Bar: proven by pixel, not by eye.** Sampled the marker bar from the
  rendered pixmap in both themes: exactly `#56d6a5` (dark) and `#0f7a5a`
  (light) — the Measure tab's own greens, as 29 claims.
* **The floor ambiguity 28 found is fixed:** the solid line is drawn only under
  step 1 (resting on the tile); step 2 has only the dashed "nothing" — the
  current-step marker is a side bar that cannot be read as a floor.
* **Legibility:** both themes fully legible; the outlined-white-tile trick
  holds on both grounds; the non-current step reads clearly fainter.
* One false alarm, resolved: an early render of mine lacked the "Also take the
  black calibration afterwards" checkbox — that was my harness letting the
  PyQt wrapper be collected, not the app; the app keeps `also_black`
  referenced and the checkbox renders (verified in a corrected render AND in
  the real app's own window on screen).

Could not fault the pictograms.

## 8. On-screen end-to-end

**Safety note that changed the plan:** the brief assumed "no hardware — the
reader will fail to open". False on this machine: the owner's unit is ALIVE in
BLE range, and the real settings already hold `cr30_ble_address =
FFB32AD2-…` (field evidence the remember-path worked on his Mac). `DeviceReader()`
is always auto-transport (`tab_measure.py:7379`, no UI to choose) — so any
"Calibrate now" click here would have connected to his instrument in ~0 s and
sent `bb 11`. **No calibrate/measure click was ever made**; the no-device
user experience therefore remains verified by code + tests only, not on screen.

**Driven for real** (sandboxed settings copied from the real plist, the owner's
CR30-Test project rsync-copied into the sandbox, real `MainWindow` on screen):
Load profile → CR30-Test opens, `_chart_is_cr30()` True, the Measure tab shows
the hex chart with the resume state ("Continue Measurement") — Start → the real
white-calibration window (correct pictogram, checkbox, Calibrate now/Cancel) →
dismissal → the new `[STOPPED] You cancelled the calibration…` message lands in
the log. The withdrawal fix works in the shipped app.

**Faults found on screen:**

* **E1 — "Keep calm! Scan each strip with a slow, steady motion." on a CR30
  chart.** The banner (`tab_measure.py:1807-1815`) is shown for every Guided
  chart and was never made CR30-aware — but a CR30 has no strips and no
  scanning motion; the user seats a barrel and presses a button per patch. On
  the shipped Measure tab this stands directly above the Start button of the
  headline feature, giving instructions for a different instrument class.
  Screenshot: `b3v2_measure_tab.png`.
* **E2 — the cancel message names a button that is not there.** In the resume
  state the button says "Continue Measurement" (`tab_measure.py:4319`), but the
  new [STOPPED] text says *"Press "Start Measurement" whenever you are ready to
  begin"* (and the dark-reference sibling says the same). Small, but it is
  precisely the told-to-press-a-button-that-does-not-exist shape. Two stopped
  lines also stack (the new [STOPPED] + the pre-existing "Measurement not
  started: the instrument was not calibrated"), saying the same thing twice.
* Observation, not a fault: "Strip recognition" and its "Auto" tick render
  enabled beside the greyed CR30-dead options; `CR30_DEAD_OPTIONS` covers only
  `highres/filter/tolerance/xrga`. With `-p` locked on, strip recognition is
  moot for this chart — a candidate for the same greying, already adjacent to
  the standing "strip-recognition log line" backlog item.
* Harness note for future drivers: with the real cocoa platform, a `QTimer`
  watcher (persistent or singleShot) stopped firing inside the #134
  already-measured offer's `dlg.exec()` in the app, while an identical
  minimal control kept ticking — cause not established, ~90 min of forensics
  not spent; the driver wraps `QMessageBox.exec` instead (show → pump → grab →
  close → return dismissal), which exercises the real windows and the real
  dismissal branch.

## NEW in `e7eb81f9`: the device-lost window — one real regression, one honesty gap

The commit is right to put M-CR30-INSTRUMENT-GONE in a window (Basti's ruling),
and the black-calibration close-means-skip fix is real (I verified the
`clickedButton() is None` handling for the black window at
`tab_measure.py:7328-7350`, with its own Cancel button and a mutation-proven
test). But:

**R1 — REGRESSION, proven failing against the real handler: "Keep measuring"
after the gone-window is a dead end again.** New flow
(`tab_measure.py:7719-7731`): any answer that is not "Carry on measuring" —
including "Stop the measurement" AND a dismissal — goes to
`_confirm_end_of_session`; if the user there chooses "Keep measuring"
(choice None), `_end_session(None)` is a no-op and the handler `return`s:
**no `rearm()`, no log line, nothing on screen.** The pre-`e7eb81f9` code
handled exactly this (`if choice is None: bridge.rearm()` + "Carrying on:
reconnect the instrument…"); the rewrite dropped it. This is 28's B2-a shape —
fixed at the magnet window one commit earlier with a loop twenty lines up —
reintroduced at the neighbouring window. Proven with a scratchpad test binding
the real `TabMeasure._on_cr30_device_lost` (same harness shape as the shipped
tests): with `_confirm_end_of_session` → None, `rearm` is never called and the
log gains only the initial announcement. **2/2 parametrisations fail** (Stop
first, dismissal first). The shipped tests never exercise the None answer —
their `_confirm_end_of_session` stub returns `"give_up"` only.
Proof: `scratchpad/proof/test_gone_keep_measuring_dead_end.py`.

**R2 — the code, the commit message, the spec and the new test disagree about
dismissal.** Commit message: *"a dismissal there carries on instead."* Spec
(`unified_measurement_management.md`, M-CR30-INSTRUMENT-GONE, REVISED
2026-08-30): *"a dismissal takes the option that changes nothing."* Code:
`if box.clickedButton() is not again:` routes a dismissal **exactly like
"Stop the measurement"** — into the ending offer (`tab_measure.py:7719-7722`).
The option that changes nothing is "Carry on measuring", and a dismissal does
not take it. Meanwhile `test_closing_the_window_does_not_end_the_session`
asserts the ending flow IS entered on close — pinning the behaviour that the
commit message and spec both deny. One of the three is right; today none of
them agree. (Defensible reading: a dismissal only *offers* the ending, and the
ending window is where the real consent happens — but then the spec sentence
is still wrong as written, and R1 makes the "Keep measuring" answer there a
trap.) Fixing R1 with the magnet-style loop would make R2 mostly moot.

## Overstatements in 27/29 — and one stale claim in ec2bf4f3

* **27, "one window per patch"** — 28 already softened this to "once per patch
  while the window stands"; still accurate at head. No further drift.
* **29, "a test counts the steers against the warnings so a fourth cannot be
  added silently"** — only for a steer that reuses one of the two counted
  phrases ("List All Devices" / "Select your colorimeter, choose WinUSB"); a
  paraphrased steer is invisible to it. Overstated, mildly.
* **29, "It now answers honestly in both directions"** (resume_after_magnet) —
  accurate, verified. No fault.
* **ec2bf4f3's commit message: "The white read-back fix is NOT yet exercised on
  hardware: every run in his log predates it" — provably stale within two
  minutes of the commit.** ec2bf4f3 landed 04:49:55; the owner's 04:51:28 log
  session postdates it, and its white→black gap of 5.0 s excludes the 12 s
  failure loop — the read-back succeeded. An UNDER-claim rather than an
  over-claim, but a reader would order a hardware test that has already
  happened. (26/29's "the scan is the whole of it" also rounds away a 1–4 s
  connect that remains — `connected in 4.08 s` at 04:47:12 in the same log.)
* **29/`e7eb81f9`'s own account of the gone window** — the commit message's
  "a dismissal there carries on instead" and the spec's "a dismissal takes the
  option that changes nothing" both misdescribe the shipped code; see R2.

## §M: it is four now, and the rule is dead letter for CR30

27 asked about three unapproved messages shown in windows; `e7eb81f9` added a
fourth (M-CR30-INSTRUMENT-GONE, on Basti's explicit ruling — *"this should be
in a pop up windows with benefitial options"*). Every CR30 message Basti has
seen and cared about now has a window while `approved=False`; none speaks
"through the log until approved" any more. That is not an accumulation of
exceptions — it is the rule no longer describing practice.

My answer to the standing question: **record it, once, as a rule amendment, not
as four exceptions.** The honest wording is roughly: *"proposed wording may be
shown in a window when Basti has asked for that window; the WORDING stays
§M-PROPOSED and unapproved either way."* His rulings are approvals of the
window, never of the text — the distinction §M actually exists to protect is
intact, and pretending the log rule still holds only means the fifth message
will break it silently. One paragraph in
`unified_measurement_management.md` §M, Basti's sign-off, done.

## What still blocks beta 1 (ranked)

**Nothing hard-blocks.** The suite is green at `e7eb81f9` (everyday tier:
8075 passed, 0 failed, run here; `--runslow` gate result recorded below), the
version is bumped, and every fault found is recoverable or cosmetic. Ranked:

1. **R1 (should fix before tagging, small): the gone-window's "Keep measuring"
   dead end** (`tab_measure.py:7719-7731`). Proven failing against the real
   handler, both routes in. It is the exact fault class this branch exists to
   remove, in the headline feature's own recovery window, and the fix is the
   pattern already applied twenty lines up (the magnet loop) or the one line
   the old code had (`if choice is None: bridge.rearm()` + the log line). A
   shipped test suite that stubs `_confirm_end_of_session` to `"give_up"` only
   will stay green over it — add the None case.
2. **R2 (do with R1, wording/one-line): dismissal at the gone window** — make
   the code, the commit story, and the spec sentence agree. If R1 is fixed
   with a rearm-on-None, the cheapest honest dismissal is the same rearm.
3. **E2 (tiny): the two cancel messages name "Start Measurement"** while the
   resume state's button says "Continue Measurement". Wording only.
4. **E1 (small, embarrassing rather than harmful): the "Scan each strip"
   banner on a CR30 chart.** A CR30 owner's very first Measure screen
   instructs a scanning motion their instrument does not have.
5. **Process, Basti's call:** the §M rule amendment above, and the standing
   items 27/29 already keep open (W4, W6, the backlog, the 69 pre-existing
   Windows failures). Plus one five-second hardware test when convenient:
   black-calibrate once with something in front of the opening and confirm the
   [WARNING] appears — the only branch of the new zero check no hardware has
   ever exercised.

None of 1-4 corrupts data, loses measurements, or misleads about stored
results; 1 is reachable only through two contrarian clicks after an instrument
loss and is recoverable with Stop. If Basti wants beta 1 out tonight, shipping
with 1-4 named in the notes is defensible; my view is 1-3 are an hour's work
including tests and should go in first.

## What I could NOT fault, plainly

* **The remembered-address mechanism** — migration-free for existing users,
  garbage-tolerant, self-healing, loop-free, single-fallback, and now proven on
  the owner's own hardware (`found in 0.00 s` at 04:47:12 and 04:51:28, the key
  present in his real plist). The faults around it (F1-a/b/c) are latent or
  cost-only.
* **`allow_dark`'s reachability containment** — no patch path can reach it,
  `_previous` cannot be poisoned, enforce interactions are sound. Proven by
  caller enumeration, not by trusting the docstring.
* **The 12 s deadline removal** — nothing else was load-bearing on it;
  termination on a dead device holds.
* **The magnet loop and `resume_after_magnet`** — 28's B2-a genuinely fixed;
  no spin, no re-entry, no stacking; the non-vacuous return is honest in both
  directions including the rebuilt-bridge edge.
* **The read-failure window** — B2-b fixed, the moved-on predicate correct at
  chart end, on goto, and on stop; the escape-then-break fix applied in the
  right order.
* **The driver guards' structure** — separate table, ordering-proven refusal,
  honest tests about their own macOS limits.
* **The pictograms** — every asked-for change is there, proven on screen and
  by pixel sample.
* **The black-calibration window's withdrawal fix** (`e7eb81f9`) — verified in
  the real app on screen: dismissal cancels, says so in the log, and costs
  nothing.
* **The suite at head** — everyday tier fully green, run here.
