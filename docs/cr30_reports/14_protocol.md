# 14 — PROTOCOL (round 4): the BLE reliability collapse, taken apart

Evidence base: the owner's real sessions of 2026-08-28 22:32 and 2026-08-29
16:56 (`~/Library/Logs/ChromIQ/chromiq.log` — bleak DEBUG was on, so every GATT
write and notification is timestamped), the capture corpus, the helper source,
and tonight's TWO hardware runs (EXP-BLE-013, EXP-BLE-014). ChromIQ read-only;
probe scripts written (uncommitted) in `~/develop/chromiq-cr30-research/tools/`.

## STATUS: complete.

---

## F-1 [SETTLED ON HARDWARE — EXP-BLE-013 + -014] A button press IS an unsolicited event over Bluetooth, and the driver has been throwing it away

Three independent lines of evidence, converging:

**(a) His own log, 2026-08-28 22:32** — last host write of any kind was a poll
at 22:32:46,552 (chromiq.log:21488); notifications then arrived at
22:32:57,394 / 22:33:15,035 / 22:33:17,735 (:21490-21492), +10.8/+28.5/+31.2 s,
with ZERO intervening writes. Every solicited reply in both sessions arrives
250–400 ms after its command.

**(b) EXP-BLE-013** — passive listener, zero writes ever: 10 s control silent,
then his three presses produced exactly three notifications
(`captures/raw/EXP-BLE-013-button-notification.json`, t = 26.866 / 33.827 /
42.528 s, spacings 7.0 and 8.7 s), each the same 10-byte frame:

```
bb 01 00 00 01 90 0a 1f ff 75
   cmd 01 sub 00 | axis: 0x0190=400 nm BE, 0x0a=10 nm, 0x1f=31 bands | ff | cs
```

Checksum verified: sum(bytes[0:9]) = 629 → mod 256 = 0x75. ✔

⚠ EXP-BLE-013's own verdict line says INCONCLUSIVE — an artifact of its
`input()` blocking the asyncio loop (phase arithmetic meaningless; events
arriving during a block are stamped late). The raw data stands.

**(c) EXP-BLE-014's positive control** — one press, one frame (t = 63.667,
`captures/raw/EXP-BLE-014-magnet-event.json`), **pressed in MID-AIR, not on a
patch, and the frame still arrived**. So the event is emitted on the PRESS
itself, not conditioned on a successful or plausible measurement — it is a
press event, not a "measurement complete" signal.

**Identity of the frame**: byte-identical to the row TRANSPORT_BLE.md's vendor
table labels *"(device → host) hello / axis announcement"*. That label is
wrong or incomplete — EXP-BLE-013/-014's post-connect controls were silent, so
connecting alone does not emit it; a press does. Note the trigger's SOLICITED
reply has the same shape — context (a write outstanding), not content,
distinguishes them.

**Where the pushes have been going**: `BleTransport._on_notify` appends to
`_buf` (`ble.py:221-222`); the next command's `_drain()` clears the buffer
unread (`ble.py:224-236`). The fact the whole design needed was received and
deliberately discarded.

**Doctrine correction**: in both his sessions the reply to a command arrived
BEFORE the first `0x01` poll (:21481→:21483 320 ms; :30226→:30228 347 ms;
:30235→:30237 251 ms). TRANSPORT_BLE.md's "the device answers a poll, not a
command-and-wait" is contradicted by this firmware; the poll is at most
sometimes-necessary, and unsolicited pushes are entirely unacknowledged there.

## F-2 [VERIFIED, step by step from his log] "Wrong patches" is the change-detector attributing unarmed presses to whatever gets armed next

Afternoon session 2026-08-29 16:56 (chromiq.log line numbers):

1. :30244 16:57:16,759 — calibrate read-back rejected (F-3) → device baseline
   (`_previous`/`_last_seen`) stays None.
2. :30278 spot_ready A18 armed; :30487 16:58:00,434 value sent for A18,
   **ΔE 60.37** (:30491). 43 s of "nothing happening" first.
3. :30496 A19 armed; its worker waits on the button.
4. :30618 16:58:24 he clicks A17 → goto → spot_ready A17 **`read:true`** → the
   bridge arms nothing (F-5/H7). His presses on A17 are caught by A19's
   still-waiting worker instead: :30708 16:58:41 "reading for A19 dropped
   (stale_loc)". Press consumed, nothing recorded, A17 still unreadable.
5. :30710 16:59:03 he clicks A18 (`read:true`) → dead end again — now NO
   worker runs at all; further presses vanish without even a log line.
6. :30728 16:59:16 he clicks A19 (`read:false` — never recorded) → a read IS
   armed → :30754 16:59:18,231, **1.8 s later = one ask() cycle**, a value
   goes out for A19: 78.19/81.58/71.20 — near-white, ΔE 50.55. That is the
   stored reading from a press made in step 5 while nothing was armed,
   mistaken for a fresh press because `_last_seen` was stale
   (`device.py:308`: `m.values != prev` is the entire evidence of a press).
7. :30763 A20 armed; :30805 16:59:24 value 44.84/36.38/15.37 recorded for A20
   (ΔE 73.40) — **A19's expected colour [43.87, 39.04, 13.64] to within a few
   units**. The off-by-one shift in plain sight: A19's real colour landed on
   A20; A19 got white.
8. From :30855 the loop repeats around A19/A21 until he gives up. Three
   patches in ~3 minutes, ΔE 50–73 — likely all mispaired.

"Nothing for a while, then a few at once, for the wrong patches" is literally
the mechanism: presses made while no read is armed collapse into ONE stored
value (the device holds only the last), then surface instantly, mis-attributed,
the moment a read is armed. Cycle cost while armed: ~2.06 s per
`read_measurement` over BLE (measured, :30292→:30301→:30310…).

## F-3 [VERIFIED] The calibration read-back was rejected correctly; it was sent once, too early, and given up on

Trigger written 16:57:13,543 (:30226), answered 13,890; read-back 15,351 —
1.8 s after the trigger — returned 200 bytes with **16 zero bands**: the
device's zero-filled partial buffer. `zero_run() >= 3` (device.py:381-384)
rejected it exactly as designed; `calibrate()` (measure_bridge.py:536-541)
treats the failure as informational — no retry, no baseline → part of why
patch one took 43 s.

* **H2 verdict**: not a fixed delay — **retry until a complete
  31-non-zero-band reply** (bounded, ~10 s). The busy state is
  self-announcing. No busy flag is known; the vendor capture contains no
  calibration to imitate (TRANSPORT_BLE.md).
* **Upgrade for TRANSPORT_BLE.md**: the zero-filled truncated reply,
  reconstructed from two concatenated PacketLogger records with a stated
  caveat, has now been observed live in one notification stream on our unit
  (16:57:15,602 → 16,759). Caveat retired; the shipped defences
  (scan-from-end + zero-run, device.py:361-392) both fired and worked.

## F-4 [RESOLVED] H4 — all seven gotos were the user, and they were rational

`goto_patch` has exactly one caller: `_on_preview_patch_clicked`
(`ui/tabs/tab_measure.py:11802-11813`), which calls `bridge.note_goto` first.
Nothing else navigates patches; the owner confirmed the clicks. The churn
(A17, A18, A19, A19, A20, A21, A19) was him trying to repair H1's mispairings
— and F-5 made that impossible.

## F-5 / H7 [CONFIRMED — BLOCKER] An already-read patch can never be re-read, and the helper is NOT the obstacle

The gate is entirely the bridge's (`measure_bridge.py`, `on_patch_ready`):
`if ev.get("read"): return` — no reader armed, `_awaiting_loc` set, session
looks alive, presses go nowhere.

The helper is willing: its xtern loop sits on any patch, `rr` set or not, and
**accepts a value for it — overwriting `scols[pix]->XYZ` in place, setting
`rr = 1`, emitting `patch_read`, autosaving atomically**
(`chromiq_chartread.c:3135-3181`: `scols[pix]->XYZ[i] = atof(bp)` …
`scols[pix]->rr = 1` … `cq_write_ti3_atomic()`). No append, no duplicate, no
extra command. A goto to a read patch and passive arrival are
indistinguishable to the helper; the bridge is the only place that knows the
difference — and it does: `_nav_target` holds the destination the user asked
for.

**The proposed fix is right and safe**: when the landing prompt equals
`_nav_target`, arm the read even if `read:true`; passive traversal keeps
today's behaviour. Caveats:

1. After a re-read the helper auto-advances to the next patch **by index**
   (`incflag = 1`), not next-unread — usually `read:true`, so the bridge
   idles again. Correct, but the UI must show where the session now sits.
2. The helper's ΔE sanity branch (`werror >= 75` → stay) re-offers the same
   loc; the duplicate-prompt latch (`_reading_loc == loc`) already covers it.
3. The user must be TOLD the patch is armed again — today a re-read attempt
   is pixel-identical to a dead session. If re-arming is ever refused, say
   so; silence is the one unacceptable outcome.

**stale_loc is the same family**: the drop is the correct half (mispairing
prevented, `_why_not`), but the press is consumed silently (`_last_seen`
updated, device.py:314) and nothing on screen says "that press went nowhere".
Under the F-1 event redesign both problems collapse: events carry timestamps,
and an event from before the current patch was armed is visibly stale and can
be reported as such.

## F-6 / H6 (O1) [REFUTED on hardware — EXP-BLE-014; one labelled residual] The magnet alone does NOT act, and the Calibrate button STAYS

**EXP-BLE-014** (passive, zero writes, timed phases, no prompts on the loop):
seating the cap (white tile in), letting it rest, and removing it produced
**zero frames** across all three phases; both silence controls were silent;
the positive control (one press) produced its frame — so the listener was
demonstrably alive. `captures/raw/EXP-BLE-014-magnet-event.json`:
`phase_counts {A:0,B:0,C:0,D:0,E:0,F:1}`, event t = 63.667.

**The corpus check that preceded it still stands and matters**: no earlier
capture could decide this — EXP-MEAS-003 had magnet + trigger + press all
present before its damaged after-reading (verified from the raw spectra:
~35–66 %R before, ~76–105 %R after); EXP-MEAS-004's "the HOST TRIGGER
performed the calibration" assumed the answer (cap attach preceded the
trigger, uncontrolled); EXP-MEAS-002's tile-face write would be invisible.
EXP-BLE-014 now removes the magnet-alone candidate: **the calibration needs a
press or a trigger. M-CR30-CALIBRATE's premise holds; do not rip it out — and
do not over-correct the other way either: whether the BLE *trigger* actually
calibrates is still unproven (F-7).**

**The labelled residual (inference, not measurement)**: EXP-BLE-014 proves no
*announced* action. A calibration that is silent on the wire AND skips the
stored buffer would look identical. Unlikely — a press announces, so a
magnet-driven measurement presumably would too — but that is an inference.
Cheap closure, priced: it cannot be fully passive (comparing readings needs
`bb 02 10`, a read-only command); EXP-BLE-015's cap phases close it in ~5–7
min of his time — stored-value read during cap-on, a read right after cap-off
(E0), and the paper-ratio write-detector (a fresh white cal leaves the 1–3 %
neutral seating signature of EXP-CAL-002; no write leaves 0.056 %-class
repeatability).

## F-7 / H3 + O2 [NARROWED — now the highest-value open question] Does the BLE trigger calibrate under a magnet? And the lights are not a cue

EXP-BLE-014 eliminated story (ii) (magnet had already calibrated). Remaining:

* **(i) The trigger calibrated, silently — the beep is button-only
  feedback.** Still supported by the O2 observation that the 2026-08-28
  build sent `bb 01 00` at every BLE open (22:32:42,003, :21376 — the old
  identify, since fixed, device.py:104-115): silent host-triggered
  measurements would flash the lamp with no beep and no press.
* **(iii) The BLE trigger with a magnet does nothing.** EXP-BLE-012 never
  ran with one; nobody has.

**EXP-BLE-016 is written** (`tools/probe_ble_trigger_with_magnet.py`) to
separate them with a NUMBER: paper baseline (2 button reads) → cap on, WHITE
tile in, ONE `bb 01 00`, operator notes beep/lamp, stored read → cap off,
paper re-read → ratio ≈1.000 = trigger wrote nothing (Calibrate button
ineffective over BLE → the UI must instruct a button press instead); neutral
1–3 % shift = trigger calibrated silently (button works; the UI must stop
implying a beep). It is the ONE experiment that can touch the white
reference, so: white face only, hard confirmation prompt, and it ends with
the verified restore (cap correct + button press, EXP-CAL-002) plus a
confirmation reading either way.

**O2, settled as far as tonight allows**: the lights DID flash — at cap
REMOVAL in EXP-BLE-014's phase D — **with no frame**. So the flashing is real
and is decoupled from the notification channel. The corpus supports none of
the candidate readings specifically (nothing in it records lamp behaviour;
EXP-MEAS-001's USB passive phase saw no wire traffic on cap events either).
**Flag for the owner and the UI: the lights are not a reliable indicator of
anything the host can observe.** EXP-BLE-015's E0 read (stored value
immediately after cap-off, before any press) tests the one testable variant —
a hidden measurement taken on leaving the gated state.

## F-8 / H5 [SUPERSEDED BY F-1] Enter-to-read: no longer the fix, at most a convenience later

With a real button event, event-driven reads deliver everything his
suggestion was for — device-side beep, one press = one reading, immediate app
reaction — with the hand staying on the instrument. Enter-as-trigger still
carries the magnet hazard (a trigger under a cap may calibrate — F-7), has no
BLE gate detection, and on USB would *abandon* the button path's gate flag
(host-triggered frames carry none — 0/20+, MEASUREMENT.md).
**Recommendation: do not build it now.**

## F-9 [VERIFIED] `-T 0.7` is inert on the CR30 path

`scan_tol` is consumed only in the `xtern == 0` instrument setup
(`chromiq_chartread.c:918` opens the block; use at :1209-1214 via
`it->get_set_opt(inst_opt_scan_toll, …)`); under `-xx` no instrument exists
(`it == NULL`). Harmless dead weight. (The "-T goes to the instrument"
finding applies to real-instrument runs — precisely why it is a no-op here.)

## F-10 [VERIFIED] The last-valid-candidate scan and 16-zero-band rejection are right — and now battle-tested

device.py:361-392 implements the skeptic's requested scan-from-end and
trailing-zero rejection, and rejected a live truncated reply correctly (F-3).
`zero_run >= 3` is well-founded (air reads 0.002 %R, never 0.0). Still open,
unchanged: `LAB_AT`/`MIN_REPLY` hard-coded for 31 bands; only `bb 02 10`'s
reply layout known; no checksum/length verification over the 200-byte reply.

---

## THE REDESIGN — event-driven BLE reads

**Demultiplex on notification boundaries, not on buffer content.** ATT
notifications arrive one callback each: the press event is one 10-byte
notification; a `bb 02 10` reply is one ~200-byte notification (MTU 244). So
in `_on_notify`:

* a notification of exactly 10 bytes, `b[0] == 0xBB`, checksum-valid →
  append `(monotonic_ts, bytes)` to a **dedicated event deque** — never to
  `_buf`, never touched by `_drain`;
* everything else → `_buf` as today (reply assembly).

This avoids scanning reply payloads for the event pattern (31 float32s could
coincidentally contain it; a standalone notification cannot), and works
whether or not an `ask()` is in flight.

**The wait**: `read_next_measurement`'s BLE branch becomes
`_run(wait_for_event(timeout))` — an async wait on the deque with periodic
`cancelled()` checks. The loop must be RUNNING for bleak/CoreBluetooth to
deliver callbacks, which the wait guarantees; events arriving between `_run`
calls are delivered (late-stamped) at the next call, so arming timestamps are
taken before the wait starts. On event: drain the deque (multiple queued
events = multiple presses; use the LAST — the stored value only holds the
last anyway — and log the count), then `read_stored` with retry-until-complete
(F-3's fix), then `check_usable(accepted)`, return. Events from before the
current patch was armed are discarded WITH a user-visible line — the honest
version of today's silent `stale_loc` swallow.

**Keep as backstops**: the bit-identical guard, tile-signature, zero-run —
the event says a reading exists, not that it is good. **Fallback**: if a wait
sees no event but the stored value HAS changed (delivery loss), the old
change-detection may serve as a logged second-class fallback — never the
primary path again.

---

# VERDICTS

| # | claim | verdict |
|---|---|---|
| **H1** | no button event on BLE; polling inference causes "wrong patches" | Mechanism **CONFIRMED** (F-2). "No event exists" **DISPROVEN on hardware** (F-1): `bb 01 00`+axis pushed per press, 4/4 across two runs, silent controls, zero writes; fires on the press itself (mid-air). Redesign above. |
| **H2** | read-back after calibrating too early | **CONFIRMED** (F-3). Retry-until-complete, not a fixed delay; the zero-filled buffer IS the busy signal. |
| **H3** | missing beep ⇒ BLE trigger does not calibrate | **NARROWED, still open** (F-7): silent-calibration vs does-nothing. EXP-BLE-016 (written) measures it with a paper ratio and ends in the verified restore. |
| **H4** | navigation churn is its own bug | **REFUTED as an app bug** — all 7 gotos were the user (F-4), reacting to H1 and trapped by H7. |
| **H5** | Enter-to-read | **Superseded by the button event** (F-8); do not build now. |
| **H6/O1** | magnet alone calibrates | **REFUTED on hardware** (F-6, EXP-BLE-014, positive control fired). Calibrate button STAYS. Residual (silent, unannounced write) is labelled inference; EXP-BLE-015 closes it for ~5 min of read-only commands. |
| **H7** | a read patch can never be re-read | **CONFIRMED — BLOCKER** (F-5). Helper overwrites cleanly; fix in the bridge via `_nav_target`; the user must SEE the re-arm. |

Fix order: **H7** (corruption unrepairable) → **F-1 redesign** (corruption
stops happening) → **H2 + calibrate baseline** → messaging (stale-press and
gave-up texts; stop implying a beep until F-7 answers) → H3 wording once
EXP-BLE-016 lands.

---

# THE EXPERIMENT SCRIPT FOR THE OWNER

Two runs already done tonight (EXP-BLE-013, -014 — thank you). What remains is
~15 minutes. Before starting: **quit ChromIQ**, phone app disconnected,
instrument ON and awake, **cap OFF**, one sheet of plain paper. Terminal in
`~/develop/chromiq-cr30-research`.

Note: re-reading an already-measured patch inside ChromIQ is currently broken
(H7) — nothing below asks you to do it; if you try anyway, the silence is that
bug, not your instrument.

### Experiment 1 — THE BIG ONE (~7 min): does ChromIQ's Calibrate actually calibrate over Bluetooth?

1. Run: `.venv/bin/python tools/probe_ble_trigger_with_magnet.py`
2. It will ask you to type WHITE first — that is the safety check: the cap
   only ever goes on **white tile toward the opening. Never the green face.**
3. In plain words it has you: press the button twice on the paper; seat the
   cap correctly; the script sends the same command ChromIQ's Calibrate
   button sends while you **watch the aperture and listen**; cap off, press
   twice on the same paper spot; then — regardless of result — seat the cap
   correctly and press the button once (your normal calibration, it should
   beep) and take one last paper reading as the health check.
4. What the printed number means:
   * paper ratio ≈ 1.000 → the command wrote nothing: the Calibrate button
     does not work over Bluetooth and the app must tell you to press the
     button yourself;
   * an even 1–3 % shift → the command DID calibrate, silently: the button
     works, and the missing beep was only missing feedback.
   Either way you also learn whether the trigger beeps or flashes at all.
5. If anything ever seems off afterwards: seat the cap correctly and press
   the button once — that is the known-good restore, and the script's last
   reading confirms it worked.

### Experiment 2 — closing the last magnet gap + a possible cap-detector (~8 min)

6. Run: `.venv/bin/python tools/probe_ble_press_magnet_suite.py`
7. It repeats the cap-on window from tonight's passive run but now also READS
   the instrument's stored value at each step (read-only commands) and
   compares two paper readings taken around the cap window. That catches a
   calibration that happens silently — the one case the passive listener
   cannot see — and its final phase (one press WITH the cap on, white tile
   in) checks whether the Bluetooth message for a gated press differs in any
   byte from a normal one. If it does, the app gains the cap-detector
   Bluetooth has been missing.
8. When you take the cap off, watch the lights — tonight they flashed at
   exactly that moment with no Bluetooth message. The script reads the
   stored value right then to see whether the flash is a hidden measurement.

### Experiment 3 — optional (~2 min): how long is the instrument busy after a calibration?

9. Seat the cap correctly, press the button (your normal calibration, with
   the beep), and immediately run
   `.venv/bin/python tools/probe_ble_live.py`. If it reports retries before
   the first complete answer, that measures the wait ChromIQ must apply
   after Calibrate (your 16:57 log shows it asked after 1.8 s and got a
   half-written answer).

### Throughout

The lights are, on tonight's evidence, NOT a reliable signal — they flashed
with no Bluetooth message and no beep. Until we map them, trust the beep and
the app, not the lamp. Still note when they flash and what had just happened;
every timestamped observation narrows them down.

---

## Probe scripts (research repo tools/, uncommitted per the rules)

* `probe_ble_button_notification.py` — EXP-BLE-013, pre-existed; RUN. I
  removed my duplicate of it and patched it in place (full payload hex +
  per-press timestamp marks). Its `input()`-on-the-loop bug is superseded by
  the suite; keep for the record.
* `probe_ble_magnet_event.py` — EXP-BLE-014, by the parallel session; RUN
  (magnet-alone refuted, positive control fired).
* `probe_ble_press_magnet_suite.py` — EXP-BLE-015 (renumbered from 014 when
  the parallel script appeared): the corrected interactive run — prompts via
  `asyncio.to_thread`, notification-boundary event tagging, stored reads
  with busy-retry, an E0 read right after cap-off (the lights hypothesis),
  paper-ratio calibration-write detector, gated-press byte comparison.
* `probe_ble_trigger_with_magnet.py` — EXP-BLE-016, new: the trigger WITH a
  magnet, measured by paper ratio, with the confirmation gate, white-face
  rule, and the verified restore built in.

## Corrections owed to the research docs once the experiments land

* TRANSPORT_BLE.md: unsolicited pushes exist (EXP-BLE-013/-014) — the
  "hello / axis announcement" label is wrong/incomplete; the poll doctrine is
  overstated (replies precede polls in the owner's logs); the zero-fill
  hazard is live-confirmed on our unit.
* MEASUREMENT.md / EXPERIMENTS.md: log EXP-BLE-013/-014 formally; record
  EXP-MEAS-004's confound as historical ("trigger-or-magnet" — now resolved
  back toward the trigger/press by EXP-BLE-014, pending EXP-BLE-016).
* CALIBRATION.md §skeptic-1: magnet-alone was a third candidate writer the
  captures could not exclude; EXP-BLE-014 excludes its announced form.
