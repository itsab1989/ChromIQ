# 28 — Beta 1, second hostile challenge [CR30-B2]

**Date:** 2026-08-30 · **Branch:** feature/cr30-instrument-159 @ 583dd306 ·
STATUS: COMPLETE.

Method: every claim below was checked against the real code at head, the real
committed binary, the real captures in `~/develop/chromiq-cr30-research`, and —
for the pictograms — the real windows on the real screen in both themes. No
source file was touched; no hardware command was sent; the instrument was never
contacted (all driven windows were dismissed via Cancel/Skip, and bridge/reader
construction is lazy — verified before running anything).

## Verdict, ranked

**Nothing found hard-blocks beta 1.** The two blockers of round 25 are genuinely
fixed, and I could not fault the B2 fix at all. What remains, in order:

1. **B2-a (should fix, small): "Keep measuring" after a magnet stop is a dead
   end.** Magnet window → "Stop the measurement" → ending window → "Keep
   measuring" (or: → "Recalibrate now" → Cancel/failed calibration → ending
   window → "Keep measuring"). `_confirm_end_of_session` returns None,
   `_end_session(None)` is a no-op (tab_measure.py:6222-6223), and
   `_on_cr30_magnet` does nothing after either cancel path (7548-7563). The
   bridge stays `_stopped=True`: `on_patch_ready` returns
   (measure_bridge.py:254), `rearm()` refuses (:371). Every instrument press
   from then on lands nowhere, silently — the silence this branch exists to
   remove — and the ending window explicitly promised "carries on where you
   were". Recoverable (Stop still works), opt-in (two contrarian clicks), so
   not a hard blocker — but it is the headline feature's secondary exit, and
   `_on_cr30_device_lost` already shows the right shape (it `rearm()`s on
   None, 7582-7589). For the magnet the honest None-handler is NOT a plain
   rearm (the white reference is still wrong) — the smallest honest fix is to
   re-show the magnet window, or to say in the log that the session is still
   stopped and how to get back. PROVEN by code reading; not on screen.
   No test covers this path (the new magnet-remedy tests stub
   `_confirm_end_of_session` to return None and record, but assert nothing
   about recovery afterwards).

2. **B2-b (should fix, tiny): after the 6th failure of one patch, the
   read-failure window stands with wrong advice.** `_on_cr30_gave_up`
   (tab_measure.py:7606) neither closes nor updates the window opened at
   failure 1; the give-up path arms nothing (measure_bridge.py:511-516), so
   "Press the button on the instrument again. This window will close by
   itself…" stays on screen describing a patch the bridge has given up on,
   next to the gave-up log line saying the opposite. One line in
   `_on_cr30_gave_up` (close the window) fixes it. PROVEN by code reading.

3. **Process, Basti's call: the version bump has not happened** —
   `core/version.py` still says 4.1.4 at head, and the release process bumps
   BEFORE the gate. Plus the two items 27 already flags: the §M
   proposed-wording-in-windows inconsistency, and the gate = green macOS
   `--runslow` at the tag commit.

Everything further down is minor, an edge, or an assessment.

## 1. B1 — keep_bridge: the fix is real; what remains around it

**The core mechanism is correct — could not fault it.** Verified line by line:
the magnet handler passes `keep_bridge=True` (tab_measure.py:7560);
`_calibrate_and_confirm` skips the close for that caller (7041-7047);
`_open_cr30_bridge`'s guard keeps the standing bridge (7317-7329); the
MagnetGated path sets `_stopped=True` WITHOUT `reader.cancel()`
(measure_bridge.py:483), so the reader — a one-way latch once cancelled —
survives for the recalibration; `resume_after_magnet` pops the retry count and
rearms the still-set `_awaiting_loc` (:348-360, `_awaiting_loc` is untouched by
the magnet path and only cleared by `stop()`). A Start (`keep_bridge=False`)
still drops the previous bridge first. The new tests bind the real TabMeasure
methods over a stand-in and stop a real bridge with a real MagnetGated — the
exact coverage shape round 25 demanded.

Around it:

* **B2-a above** — the cancel paths' dead end.
* **Edge, suspected only (not reproduced):** if the helper dies while the
  magnet window's `box.exec()` is up, `_on_measure_done` closes the bridge;
  the handler then continues, `_open_cr30_bridge` builds a NEW bridge (guard
  sees None), and `resume_after_magnet`'s `if not self._stopped: return True`
  (measure_bridge.py:356-357) is vacuous-True again → "Carrying on" printed
  into a dead session. The old lie, through a much rarer door (helper crash
  during the modal). A cheap hardening: have the magnet handler remember the
  bridge object it stopped and refuse to "resume" a different one.
* **Not a regression, noted:** a CANCELLED Start calibration leaves
  bridge+reader standing (instrument open, over BLE connected) until the next
  Start or `_on_measure_done`; nothing closes it on app quit either. Behaviour
  predates keep_bridge. A skip-calibration Start then reuses that idle bridge
  via the guard (5787) — harmless state-wise (fresh flags, empty retries),
  stale transport handle at worst (recovers through the device-lost flow).
* **Cosmetic stacking, reachable:** bridge signals delivered inside another
  window's nested exec (e.g. a magnet event or read failure arriving while the
  ending window is up) stack a second window over the first. Rare, transient,
  the registry still closes everything at the ending.

## 2. B2 — saw_reply / removed guard: could not fault it

* **The 3-byte prefix is capture-verified.** research repo EXPERIMENTS.md:664-667:
  `bb 11 00 11 …`, `bb 10 00 1c …`, second runs `bb 11 00 0a …` / `bb 10 00 0f …`;
  CALIBRATION.md:230 (USB): `BB 11 00 00`. Byte 2 = 00 in every capture held,
  byte 3 varies — exactly what the code comment claims.
* **False positive from float data: not reachable in the workflow.** `saw_reply`
  is only ever a `done=` for `calibrate` (device.py:244). `_ask` drains `_buf`
  before writing (ble.py:377-379); during a calibration exchange the only
  reply-buffer traffic is the calibration reply itself — presses route to the
  event queue (ble.py:248-252) and no measurement reply can be in flight
  because the reader lock serializes calibrate against patch reads
  (measure_bridge.py:626, :698). Even a freak match would only end the wait
  early: `calibrate` discards the returned bytes, and the late ack is flushed
  by the next exchange's drain.
* **The removed `and self._buf` guard cannot stop a predicate early on a
  partial reply.** The only buffer-validating predicate is `_parse_reply`
  itself (device.py:445), which requires a complete MIN_REPLY=196-byte
  candidate from a header, parses, validates, and rejects zero-run ≥ 3
  (device.py:25-53); a trailing partial second copy is skipped by the length
  check (:39). The trigger's predicate is queue-based and safe on empty. There
  are no other `done=` callers (grepped). `_parse_reply(b"")` is None.
* **`saw_event(0x01)` cannot consume a press an armed patch is waiting on.**
  `trigger_unsafe` runs only inside `read_zero` (measure_bridge.py:758), under
  the same reader lock every patch read holds; and any event predating an arm
  is deliberately dropped at arming (`drop_events`, device.py:330). Worst
  reachable case: the user presses the button during the black-calibration
  zero check and `read_zero` reads paper — landing in the existing "something
  was in front of the opening" warning. No mis-attribution path exists.
* The new tests drive the real `_ask` and the real `_on_notify` demux with
  only the bleak client and `asyncio.sleep` stubbed, and vary reply byte 3 as
  the captures do. This is the probe design 25 asked for. 17/17 pass here.
* **One honest residual (suspect, hardware-only):** the early stop removes
  ~1.05 s of post-press margin before reading the stored slot. The evidence
  says a busy device zero-fills (which `_parse_reply` rejects, so polling
  continues); if it ever instead serves the stale previous reading, the
  bit-identical guard refuses it and the user pays one visible press — never
  silent corruption. Same exposure class existed before the change.

## 3. W9 — verified, including on the committed binary

* **Fix verified in code and by running it.** `cesc` is
  `6*(MAXNAMEL+16)+8 = 6248` bytes for an `inname` of at most 1034 chars ×6 =
  6204 worst case (chromiq_chartread.c:4259, :3344; MAXNAMEL=1024,
  sa_config.h:57), and `cq_json_escape`'s `o + 6 < dstlen` loop guard cannot
  overrun any buffer regardless (chromiq_json.c:60-73). All 9 tests of
  `test_the_chart_path_survives_json.py` pass, run here.
* **The committed binary is covered.** `native/chromiq-chartread` and the dev
  build the tests drive are byte-identical (`cmp`) and git-clean, so today's
  green tests prove the committed bytes. The marker
  `chromiq-chartread 2026-08-30 json-path-escape` is present in the committed
  Mach-O (`strings`), and the binary at 0c9cb3b4 (pre-fix) contains `CR30` but
  NOT the marker — the old grep passes on it, the new test fails it. **The
  implementer's "previously committed binary now fails it" claim is proven.**
* **The staleness test still has a hole, and 27 oversells it slightly:** the
  marker moves only by hand. A helper-source edit that does not bump
  `CQ_HELPER_BUILD` leaves a stale committed binary green — the companion test
  (test_cr30_packaging.py:83-88) only checks the marker CONTAINS a date, not
  that it moved with the sources. W6 reduced, not removed. Not a beta matter;
  hashing the sources into the marker (or a CI check) closes it properly.
* **The deliberately-left raw `%s` sites: leaving them was right for beta 1.**
  Strip labels/locs come from `paix->aix` (a generated alphabet), ids from the
  chart file; hostile content needs a hand-edited or foreign .ti2, and the
  blast radius is one dropped JSON line. The worst of the class is
  `chart_refused`'s raw `TARGET_INSTRUMENT` (chromiq_chartread.c:3732-3736): a
  quoted name makes the refusal reason invisible to the GUI — ironic, since
  that emit exists to explain a refusal. Sweep the class after beta.
* **New nit, same class, pre-existing:** the `saved` event escapes `realname`
  into a 512-byte buffer (chromiq_chartread.c:468, :493) for a path that can
  be ~1044 chars — a very long path is silently truncated in the event, the
  exact fault shape the W9 comment condemns. `cq_emit_error` likewise. For the
  class sweep, not for beta.

## 4. The read-failure pop-up — solid, two edges

Could not fault the mechanism: teardown-safe (worker signals are queued but
`_on_read_failed`'s stopped guard, measure_bridge.py:454, silences everything
after `_on_measure_done` stops the bridge BEFORE closing windows,
tab_measure.py:9848-9849); no stacking (one reference, previous closed before a
new one opens, 7427); modeless so the bridge's re-arm (:520-521) is never
blocked; the ending closes it (registered, 7448); `_gone` clears both the
reference and the per-patch flag on every close path (7451-7459); and the 6th
failure emits `read_gave_up` INSTEAD of `read_failed`, so there is no
two-window case. Ten behavioural tests cover it.

* **B2-b above** — gave-up leaves the standing window's advice wrong.
* **Suspect, needs one live check:** "This window will close by itself when the
  reading comes through" (M-CR30-READ-FAILED) rides on `_on_patch_ready` with
  a DIFFERENT loc (11388-11391). On the chart's LAST patch the helper re-offers
  the same loc with `all_done`, so the promise may not hold there until the
  session ends. Not proven on hardware.
* Cosmetic race: a real failure racing a click-to-jump can flash the window for
  the patch being left (the emit at :519 fires whenever the exception is not
  ReadAbandoned, even with `_awaiting_loc` already None); the next prompt
  closes it. Self-healing.
* "Once per patch" strictly means once per patch *while the window stands*: a
  user who closes it by hand gets a fresh window on that patch's next refusal
  (and there is a test pinning exactly that). Reasonable UX; noting because 27
  words it more absolutely.

## 5. W7 — could not fault

Registered (7695); `_close_measurement_windows` iterates a COPY and catches
RuntimeError (6112-6117), so no mutation-during-iteration and no
deleted-C++-object crash; no `WA_DeleteOnClose`, parent = tab, so wrappers stay
alive; double-close is idempotent (`_forget_measure_window` swallows
ValueError). The magnet remedy cannot re-show it mid-session (`_cr30_how_shown`
guard, 7655; reset only at Start, 5637) — which also fixes the shown-twice
sequence the Start comment describes. Nit only: `_cr30_how_dlg` keeps
referencing the closed dialog until the next Start.

## 6. W3 — could not fault

The parametrised test (test_run_delete.py:699-725) monkeypatches
`trash.sys.platform` and `trash.os.name` and asserts both the expected word AND
the absence of the other two. If the name were frozen at import, the
win32/linux rows would fail on this macOS host — passing IS the proof of the
dynamic lookup. Remaining literal "Trash" occurrences are developer log lines
only (measurement_target_bar.py:2014, file_manager.py:2566/2568,
run_delete.py:632/652). One adjacent find: **`settings_dialog.py:4110` shows
"device(s)" in the driver dialog** — the exact wording pattern Basti flagged;
the new (s)-ban test only scans `workflow/cr30`. Two-line fix, any time.

## 7. steps_pair — on the real screen, both themes, looked at

Shots (real `_calibrate_and_confirm` / `_run_cr30_black_calibration` windows,
sandboxed settings, no device I/O):
`scratchpad/shots/b2_cal_{white,black}_{light,dark}.png`.

* Both themes fully legible; the ink is palette-derived and nothing disappears
  on either ground. The stacked pair fills the text column as intended, the
  black window still reads correctly overall (title + emphasised step 2 +
  faint capped step 1), and the white-tile-as-outline trick works on both
  grounds.
* **The brief's worry is confirmed visible:** in the BLACK window the
  current-step underline sits directly below the dashed "nothing" line — same
  width band, ~17 logical px apart — and the picture alone reads as
  "instrument, dashed gap, solid FLOOR". The drawing suggests a surface under
  the emptiness that the text then has to argue away ("There is nothing to
  place it on"). In the WHITE window the same underline harmlessly reads as a
  table under the capped instrument. Reporting only, per the brief; if a
  remedy is wanted, the current-step mark should leave the horizontal axis the
  floor metaphor uses (a side bar or a frame, not another horizontal line).

## 8. Windows driver help for the CR30 — assessment only (nothing implemented)

**Today the button cannot touch the CR30** — 1a86:7523 is not in
`KNOWN_COLORIMETERS` (usb_driver_installer.py:36-73), confirmed at head. But
the dialog around it already carries two live hazards for 4.1.5's new Windows
CR30 users, no code change needed:

* The dialog's Zadig guidance says, generically: *"Options → List All Devices →
  select your colorimeter → choose WinUSB → Install Driver"*
  (settings_dialog.py:4125 and 4211, reached via 4200-4204). A CR30 owner with driver trouble
  who follows that on the CH340's row **replaces CH341SER with WinUSB and the
  COM port is gone** — the instrument goes dark in ChromIQ and every other
  serial app, until a by-hand rollback in Device Manager. This is reachable
  today by user action alone.
* `targets = needs_install or devices` (4171) — the "Reinstall" path batch-runs
  `install_winusb` over EVERY detected device. If anyone ever adds the CR30 to
  `KNOWN_COLORIMETERS`, a user repairing their i1 Pro silently WinUSBs the
  CR30 in the same click. The batch amplifies a one-line table mistake into a
  brick.

**Safest shape (design, for Basti to approve):**

1. A structurally SEPARATE table in the module —
   `VENDOR_SERIAL_DEVICES = {("1a86","7523"): ("CR30 (USB-serial)", "CH341SER")}`
   — never merged into `KNOWN_COLORIMETERS`, so no existing code path can feed
   it to `install_winusb`. The module's own HID-exclusion note (:26-29) is the
   precedent: vendor-serial is a third class with a different mechanism.
2. `install_winusb` REFUSES vendor-serial ids defensively (belt and braces
   against a future table edit; the batch loop then cannot brick it either).
3. Enumeration grows a status for the class, reusing the same winreg walk:
   key `VID_1A86&PID_7523` present + `Service` == `CH34*` + a COM port → OK;
   key present, no working service → **"connected, but Windows has no working
   driver"** — the cheap, high-value state (25's (b)) that today reads as "the
   instrument is not there".
4. The dialog lists the CR30 row with NO WinUSB button: text says Windows
   normally installs this driver itself (it is on Windows Update), and a
   "Get the CH340 driver…" action that either runs `pnputil /add-driver` on a
   bundled SIGNED WCH package (license to be checked before bundling) or opens
   the vendor page. Never auto-install: 1a86:7523 is the generic CH340 chip on
   millions of unrelated serial devices, so VID/PID alone cannot say "this is
   a CR30" — wording must hedge, and identification stays behavioural
   (identify() over the opened port, which needs the driver first).
5. Whenever a 1a86:7523 device is present, every Zadig-steering text gains one
   warning line: do NOT pick the USB-serial device in Zadig — that disables
   the CR30.

**Bricking vectors to keep named:** adding the CR30 to `KNOWN_COLORIMETERS`
(one-line mistake, amplified by the batch); the Zadig path by user action
(live today); wdi-simple ghost-instance misdirection (already documented at
:216-224) — a ghosted CH340 instance is one more reason install_winusb must
refuse the id outright. Windows-only, touches §M — after beta 1, Basti's call,
as 25 already concluded.

## 9. What still blocks 4.1.5 beta 1

**Nothing hard.** The honest checklist, in order:

1. Bump `core/version.py` (still 4.1.4), then a green macOS `--runslow` at the
   tag commit — the standing release process.
2. Decide B2-a (magnet "Keep measuring" dead end): fix (small) or ship named
   in the notes. My view: fix — it is the headline flow's own exit and the
   device-lost handler already shows the pattern.
3. B2-b (close the read-failed window on gave-up): one line, do it with #2.
4. The two items 27 already put to Basti: the §M windows-while-proposed
   inconsistency, and the Windows release-note section naming the 69
   pre-existing failures + W4.

## What I could not fault, plainly

The B2 fix (saw_reply, the guard removal, the trigger consumption) — attacked
from captures, threading, predicate totality, and workflow reachability, and it
held everywhere. The keep_bridge core. W9's fix, sizing and binary discipline
this round (marker proven present, old binary proven failing, tests proven to
run the committed bytes). W3's parametrised test, which really proves all three
wordings from any host. W7's registration. The read-failure window's lifecycle
except the two edges above. The pictograms' theme behaviour. And 27's own
account is accurate on every point I could test — the one soft spot is that the
staleness test's guarantee is manual-discipline-deep, and the one visual it
could not have seen is the black window's floor-line ambiguity, which needed a
screen and eyes.
