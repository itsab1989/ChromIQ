# 20 — Black calibration challenge [CR30-BLACKCAL]

Status: COMPLETE, 2026-08-29. Findings F1-F9, design, texts, owner questions,
risks. On-screen shots: ~/Desktop/CR30-test-shots/cr30_blackcal_01..04.

## VERDICTS UP FRONT
(a) **The stated blocker is FALSE.** The black-calibration command is fully
recorded in the corpus (F1). What actually blocks shipping it is: never sent
on THIS unit, reply semantics unverified, no verified restore for a corrupted
dark reference, and two standing instructions that only the owner can lift.
One ~10-minute owner-present session closes all of it.
(b) **Needed? Not urgently, and not per-Start.** Zero evidence of dark drift
on this unit across the whole corpus (F6); the warm-up drift is white-side,
not dark. The exposure is long-term drift ChromIQ cannot see — real, slow,
worth an on-demand correction plus a cheap zero check, not double friction on
every Start.
(c) Design below: white-then-black when both run; two clearly different
modals; black on demand (Tools), not per Start; zero check one-sided and its
text must say so; exact §M texts drafted, approved=False.

## F1 — THE STATED BLOCKER IS FALSE: the command IS in the corpus
Brief: "nothing in the corpus records what it sends." Wrong.
`captures/public/PRIORART-001-vendor-usb-frames.json` (second unit, vendor
app, Windows; extraction order-preserving), sequence
**"Calibrate White and Black and Test Target.spm"**, frames 0-13:
```
0  bb 11 00 00 + 54 zero bytes + ff + ck    white cal REQUEST (payload all zero)
1  bb 11 00 00 00 00 01 ...                 reply, 0x01 at frame offset 6
2  bb 10 00 00 + 54 zero bytes + ff + ck    BLACK cal REQUEST (payload all zero)
3  bb 10 00 00 00 00 01 ...                 reply, 0x01 at frame offset 6
4- bb 01 00 trigger + header + chunks       the Test Target measurement
```
No trigger between the cal commands — each command performs its own
acquisition. PROTOCOL.md §5 lists both as CORROBORATED; the brief was written
against a memory of the corpus, not the corpus. There are NO vendor .pklg
files in the repo (BLE vendor capture never happened); the vendor material is
this USB extraction, and it contains the calibration.
Genuinely missing: (i) never sent on THIS unit; (ii) 0x01 reply never
contrasted with a failure (PROTOCOL.md §8.6); (iii) magnet interaction of
bb10/bb11 unknown (does bb10 refuse under magnet? does bb11 need one?);
(iv) NO verified restore path for a corrupted BLACK reference — cap+button
restores WHITE only (EXP-CAL-002); (v) timing of the reply (dedupe stripped
timestamps) — does 0x01 arrive after the acquisition or immediately?

## F2 — THE ORDER CONTRADICTION DISSOLVES: the vendor uses BOTH orders
"Calibrate White and Black...": WHITE then BLACK (frames above).
"param change-and-measure.spm" frames 4-7: BLACK (bb10) then WHITE (bb11),
right after connect frames (bb17/bb13/bb28), before a measurement.
So order is free in the vendor's own traffic. CALIBRATION.md:~340 "black
first, then white — per Pharmacist" vs the app wizard "White step 1, Black
step 2" is not a contradiction to arbitrate: both happen. Consistent with the
device storing raw D and raw W and computing (S−D)/(W−D) at measurement time.
Recommendation for ChromIQ when both run: WHITE then BLACK — see design §2.

## F3 — Confirmations the brief asked for, and one it needed
- EXP-BLE-012 (raw JSON has real 31-band spectra): host trigger with NO
  magnet = ordinary measurement (3.9222 vs button 3.9416 %R). CONFIRMED.
- EXP-BLE-015: host trigger WITH magnet = white calibration (TILE_SIGNATURE
  returned; button-press positive control identical; paper reads real before
  and after). CONFIRMED.
- EXP-BLE-014: magnet alone does nothing announced. CONFIRMED.
=> There is NO trigger-based path to a dark calibration. The path the brief
missed is not a trigger trick; it is that bb 10 was in PRIORART-001 all along.
- ChromIQ's shipped white cal is trigger_unsafe() (bb 01 00) under the magnet
  gate — workflow/cr30/device.py:177 calibrate_white(), owner's deliberate
  reversal 2026-08-28 — NOT bb11. EXP-MEAS-004 RAN
  (captures/raw/EXP-MEAS-004-host-calibration.json; docstring: host-only
  trigger vs green face moved paper 81.10→149.10 %R, restore 81.20): the old
  "which command wrote it" question is settled — the trigger writes under
  magnet. bb 11 remains unsent here and unnecessary for white.

## F4 — EXP-020 CHALLENGED: the probe cannot support the offered reading
Raw: captures/raw/EXP-020-ambient-light.json; probe:
tools/probe_ambient_light.py (trigger_unsafe → sleep 0.4 s →
read_measurement(enforce=False)).
- Phase A (torch): 0.00000 exactly, all 31 bands, ALL FIVE readings.
- Phase B (dark): 0.00017941935483870968 five times BIT-IDENTICAL, the same
  single non-zero band (index 14 = 0.00556) each time.
- Phase C (torch again): 0.034, 0.151, 0.090, 0.000, 0.0007 — the only phase
  whose readings differ from each other.
Challenges, in order of force:
1. **Bit-identical repeats are the corpus's own red flag for "did not
   re-measure"** (EXP-SPEC-001b records "0 identical readings — so the device
   really re-measured" as its validity argument; device.py documents the
   stale-cache dE-60.5 failure). enforce=False + fixed sleep is exactly the
   read-back-the-cache pattern. Phases A and B are probably ONE reading each,
   fetched five times. The probe cannot distinguish its own hypotheses —
   the same fault class as EXP-MEAS-002's first design (SESSION_HANDOFF
   method lesson 2).
2. **The physics is backwards.** Adding torch light cannot read BELOW
   darkness; 0.00000 exact under a torch vs 0.00018 dark. Rivals: sensor
   saturation with S−D clamped to zero (light got in MASSIVELY), or
   zero-filled not-ready replies (the "16 zero bands (truncated reply)"
   failure documented in measure_bridge.py calibrate()). Either kills "no
   light got in at position 1".
3. "Angle-dependent rather than brightness-dependent" — UNSUPPORTED. What is
   supported: at some geometry, light enters at up to ~0.15 %R (phase C).
4. The "≤0.15 %R is below the ~0.5 % his handling introduces" comparison is
   the WRONG YARDSTICK: EXP-BLE-017's −0.47 % is contact repositioning on
   thin paper — irrelevant to free-air readings, and it is per-patch RANDOM
   noise, while a contaminated dark reference is a SYSTEMATIC bias baked into
   every subsequent reading.
Is a re-run worth the owner's time? A freshness-enforced re-run costs ~3
minutes and would also answer whether the firmware subtracts lamp-off per
reading (the question EXP-020 was built for). Cheap; fold it into the same
session that verifies bb 10 (below). The design consequence — "not pointing
at a lamp or a window" — survives regardless, because it costs one line.

## F5 — Does 0.15 %R matter for a ZERO reference? Yes.
D_stored high by 0.15 %R depresses every reading by ~0.15 %R (white-side
correction /(100−0.15) is negligible). On a 2 %R shadow patch: 7.5 % relative,
≈0.5-0.6 L* at L*≈15 — systematic, one-direction, on exactly the patches a
printer profile's shadow behaviour hangs on. Against 0.056 %R worst-band
repeatability that is material. The lighting instruction is needed.

## F6 — Is it NEEDED? No dark drift observed; the warm-up figure is white-side
- Air reads 0.002 %R through the stored calibration (CALIBRATION.md, "Nothing
  indicates it is needed": air 0.002, paper 85.84, repeatability 0.056).
  EXP-020's dark ~0.00018 %R (with F4's caveat) is consistent days later.
- The warm-up drift the brief asks about: EXP-SPEC-001b, 82.538→82.272 %R
  monotonic on paper over 30 readings (≈0.32 % relative — the brief's
  figure). NOT the same phenomenon as dark drift: an absolute dark shift of
  ~0.27 %R would appear in air readings, and air stays ~0.002. It is
  multiplicative (lamp/gain) — the WHITE calibration's territory, already
  per-Start.
- HYPOTHESIS (general instrument physics, unverified on this device): dark
  reference drifts with detector temperature and electronics age; slow at
  room temperature. The firmware may subtract lamp-off per reading anyway
  (EXP-020 was meant to test this and failed, F4). Already-built profiles are
  not impugned: this unit's zero is healthy now and was healthy throughout.

## F7 — The zero check is real but ONE-SIDED, and the blind side likely exists
Post-cal air reading detects D_stored too LOW (air reads high). If D_stored
is too HIGH, S−D is negative; if the firmware clamps at zero — EXP-020's
exact 0.00000s suggest clamping exists — air reads exactly 0.0 and looks
perfect. Mirrors MEASUREMENT.md Hole 4 (bounds blind to the deflating half).
Any shipped check must therefore report "nothing wrong was seen", never
"verified". Threshold from the corpus, not invented: healthy observed
≤0.002 %R; ambient contamination observed to 0.151 %R (under a torch, F4
caveats). Proposed WARN at ≥0.05 %R mean — 25× the healthy signal, below the
worst observed contamination — PROVISIONAL until EXP-020 is re-run.
⚠ The zero check itself sends bb 01 00. With a cap accidentally ON, that
trigger IS a white calibration against whatever face is presented
(EXP-BLE-015 / EXP-MEAS-004). The owner's trigger reversal covered the
calibration window only; using the trigger for a zero check is a NEW use he
has not ruled on. It also must be refused while a measurement session is
live (it would collide with the bridge's reads). So even the "shippable
today" half needs his ruling — it is cheap, but it is not free.

## F8 — What already exists on screen (verified, real app, real styling)
Driver: scratchpad/onscreen/drive_blackcal.py (sandboxed settings, COPY of
CR30-Test, modal never left waiting; QMessageBox.exec patched to
screenshot-and-return so no device I/O occurred).
- cr30_blackcal_01/_02: M-CR30-CALIBRATE from the real
  `_run_cr30_calibration` path — modal, "Put the magnetic cap ON …
  WHITE TILE", Cancel / Calibrate now.
- cr30_blackcal_03/_04: M-CR30-HOW-TO-MEASURE from the real
  `_show_cr30_measuring_window` — modeless, "Take the magnetic cap OFF".
The existing pair ALREADY makes the user do opposite things in consecutive
windows (cap ON, then cap OFF), differentiated by bold/CAPS action lines.
That is the house style a black window must match. Agreed-but-unbuilt
revisions that must not be contradicted (17_verify4 F1 + 19_design5 D1):
how-to gains OK rename, a Stop button, a calibration-led first line, close in
`_close_measurement_windows`. A black step, if it ever runs at Start, slots
BETWEEN the calibrate modal and the how-to window — it does not touch them.

## F9 — Corpus hygiene found on the way
- EXPERIMENTS.md still has no entries for EXP-BLE-012..018 (19_design5
  leftover 6) and NONE for EXP-020 either — the raw JSON and the probe are
  its only record.
- The brief circulated "we do not know the black-calibration command" while
  PROTOCOL.md §5 and two capture sequences say otherwise: a memory-of-corpus
  error of exactly the kind CLAUDE.md's spec rule warns about. Cite files,
  not memories.

# THE DESIGN (if the owner's session verifies bb 10)

## D1. Order: WHITE then BLACK
Order is physically free (F2). White-first wins on choreography: cap ON →
white cal → cap OFF + point at nothing → black cal → cap stays off → measure.
Cap state changes exactly twice, monotonically, and the black step hands the
user to the how-to window already in the right state (its first instruction —
take the cap off — becomes a confirmation). It also matches the vendor wizard
the user may know (White step 1, Black step 2).

## D2. Two windows, not one mutating window
Two sequential modals in the existing QMessageBox style, titles carrying
"Step 1 of 2" / "Step 2 of 2", each with ONE bold/CAPS action line stating
the opposite actions (cap ON white tile / cap OFF pointing at nothing).
Against a single window that swaps its content: (i) the owner's own stated
worry — the user does not notice the change; (ii) §M architecture is
one-message-one-window (a mutating window has no single §M identity;
test_message_catalogue.py); (iii) no precedent in ChromIQ. Modal-fatigue is
answered by D3, not by merging windows.

## D3. Frequency: black is ON DEMAND, never per-Start — this is the ruling
that dissolves the two-popup problem
Grounds: no observed dark drift (F6); warm-up drift is white-side; the vendor
buries black in a wizard the user invokes, not per measurement; ChromIQ can
know NOTHING about the device's dark state between sessions (whether cal
survives a power cycle is an open corpus question, so a ChromIQ-side
timestamp would be a guess about device state); double friction on every
Start is real cost for a correction with no observed need.
Placement: Tools menu, "CR30: black calibration and zero check", enabled for
CR30 charts, refused while a session is live. tool_availability.md is DRAFT —
adding the row needs the owner (spec rule). The per-Start white flow is
UNCHANGED. Optional later step, only after the zero check has field history:
offer black cal when a zero check fails.

## D4. Skippable
On demand = inherently skippable; nothing to rule. IF the owner instead
orders black bundled into every Start: then it follows white's ruling as a
pair (mandatory in Guided; Manual's existing "Skip initial calibration" tick
governs both — one tick, not two). Recommend against bundling (D3).

## D5. Verification: the black flow checks itself; white stays uncheckable
After bb 10's reply, take ONE air reading (trigger + read, port still down)
and compare to the threshold (F7). Report:
- mean < 0.05 %R: "nothing wrong was seen" (never "verified" — one-sided).
- ≥ 0.05 %R: zero reads high — stale reference or light getting in; repeat
  away from bright light.
The zero check is also available alone (same Tools entry) as the read-only
"is my dark reference healthy" answer — and it is the only part of all this
that needs no bb 10 at all, just the owner's ruling on the new trigger use
(F7 caveat).

## D6. Exact window texts (§M-PROPOSED, approved=False, appended to the
PROPOSED set in measurement_messages.py ~:1090)

M-CR30-CALIBRATE-BLACK — modal, buttons [Cancel] [Calibrate now]:
Title: "Black calibration — point the instrument at nothing"
Body:
"Your CR30 can also take a black calibration. It is rarely needed — the white
calibration before each measurement is the one that matters day to day — but
the instrument's zero can drift slowly, and that shows most in the darkest
patches of a chart.

Take the magnetic cap OFF and put it aside. Hold the instrument in the open
air with the measuring opening pointing DOWNWARD, about a metre above the
floor and well away from anything — walls, your desk, your own hand. Do it
away from bright light: not pointing at a lamp or a window.

Then press "Calibrate now". ChromIQ afterwards takes one reading of the empty
air to check the zero — a healthy zero reads as good as nothing at all. That
check can catch a zero that reads too high; it cannot prove everything is
right.

If you would rather not, press Cancel — nothing has been changed."

M-CR30-ZERO-CHECK — modal, buttons [Cancel] [Read now]:
Title: "Check the instrument's zero"
Body:
"ChromIQ reads the empty air and checks that your CR30 sees darkness where
there is nothing to see. Nothing is calibrated or changed — this is a reading
only.

Take the magnetic cap right OFF first — with a cap on, the instrument
calibrates itself instead of measuring, so this check must never run capped.
Hold the instrument with the opening pointing DOWNWARD, about a metre above
the floor and well away from anything, and away from bright light: not
pointing at a lamp or a window.

Then press "Read now"."

Results (log NOTE + the window per house style TBD):
healthy: "The zero looks healthy: the empty air read {mean} %R. Nothing wrong
was seen — this check catches a zero that reads too high, so a clean result
is not a guarantee of everything else."
high: "The empty air read {mean} %R, which is higher than an empty reading
should be. Either light was getting into the opening — try again pointing
somewhere darker — or the instrument's black calibration is stale. A black
calibration resets it."
(If the reading comes back bit-identical to the tile constant this session
has seen: "That looks like the cap is still on the instrument. Take it off
and try again." — heuristic, per-unit, same one the bridge already uses.)
NOTE for the owner: "the instrument's zero can drift slowly" is general
instrument knowledge, NOT verified on his unit (F6) — he may want it softened.

## D7. Spec obligations (both specs BINDING; nothing written until approved)
- unified_measurement_management.md §M: the messages above enter §M-PROPOSED
  first; test_message_catalogue.py enforces. Nothing into a tab before
  approval.
- measurement_exit_strategy.md: new rows — M-CR30-CALIBRATE-BLACK: not an
  exit, session not begun (mirror of the existing M-CR30-CALIBRATE row :108
  + note 5); M-CR30-ZERO-CHECK: not an exit, AND the Tools entry is disabled
  while a session lives (its trigger would collide with the bridge's reads).
- tool_availability.md (DRAFT): a row for the Tools entry — owner approval
  required twice over (spec is draft AND unconfirmed behaviour).
- 19_design5's owed rows (how-to Stop) are untouched by this design.

# WHAT NEEDS THE OWNER (write to him in these terms)
1. One ~10-minute session on his unit, him present, to make black calibration
   real. He must explicitly lift, for this one designed session, the standing
   "never send bb 10 / bb 11" instruction (SESSION_HANDOFF.md,
   SAFETY_ENVELOPE.md carve-out). Procedure: record baseline (air, paper);
   cap off, port down, dim light; send bb 10 once; re-read air and paper;
   compare to baseline; then a white cal (cap + button, the verified
   procedure) and re-read once more. If anything looks wrong, the verified
   white restore is in hand — the honest caveat: there is no PROVEN restore
   for a bad dark reference other than bb 10 itself behaving as understood.
   Alternative, zero-risk, also already planned (19_design5 ranking #1):
   sniff the vendor app doing its calibration wizard on THIS unit first, and
   only replay what it is seen to send.
2. The frequency ruling: black on demand from Tools, never per Start (D3).
   This is the design decision he asked about; the two-popups-every-Start he
   feared is the option we recommend AGAINST.
3. The trigger's new use: may ChromIQ send a measurement trigger for the
   zero check (cap off, with the wrong-cap hazard stated in the window)?
   His earlier reversal covered the calibration window only.
4. The window texts in D6 (and whether "drift slowly" should be softened,
   since his unit has shown none).
5. Three minutes of the same session to re-run EXP-020 with per-reading
   freshness enforced (F4) — settles the lighting threshold honestly.

# RANKED RISKS
1. Shipping bb 10 unverified: a calibration WRITE with untested reply
   semantics and no proven dark-reference restore. Closed only by the owner
   session (or the vendor-app sniff first).
2. Zero check with a cap on = silent white calibration against the presented
   face (EXP-BLE-015). Mitigations: window text, bit-identical heuristic —
   but the heuristic is per-unit (TILE_SIGNATURE, MEASUREMENT.md Hole 1).
3. One-sidedness misread as verification — the check's wording must carry its
   own limits (D5/D6), or it becomes the next "green test guarding the bug".
4. The 0.05 %R threshold rests partly on EXP-020, whose data is compromised
   (F4). Provisional until the re-run.
5. If the owner bundles black per-Start anyway: modal fatigue on every
   measurement, for a correction with no observed need — say so once,
   plainly, then build what he rules.
6. EXPERIMENTS.md holes (F9) — the next agent will repeat tonight's
   memory-of-corpus error if 012-018 and 020 stay unrecorded.

# F10 — OWNER OBSERVATION (2026-08-29, late): USB and BLE links CONCURRENT
His report: the phone app connects over Bluetooth while USB is plugged in;
the device shows the U and B indicators at once. Consequences checked:

## F10.1 Claims in our own documents, checked verbatim
- TRANSPORT_BLE.md:158-159: "the device stops advertising while a central
  holds it, so THE PHONE APP AND CHROMIQ CANNOT BOTH BE CONNECTED" — now
  WRONG as phrased. True only for BLE-vs-BLE; ChromIQ over USB + phone over
  BLE evidently CAN both be connected. Needs the DISPROVEN-in-place marking
  (research repo hygiene rule).
- TRANSPORT_BLE.md:36-37: "if the device is advertising, nothing holds it;
  if it is not, something does" — the first half is now DISPROVEN as a state
  signal: a USB host can hold the device while it still advertises (that is
  exactly how the owner's phone found it). Any probe using advertising as
  "device is free" gets a false positive.
- workflow/cr30/measure_bridge.py:63 `_no_device_help`: "A CR30 stops being
  visible over Bluetooth while another device holds it — disconnect there
  and try again." NOT misleading: it explains a BLE open failure, and a
  phone holding BLE still blocks ChromIQ's BLE regardless of USB. The hint
  stands. (Its docstring's "on every platform: the CR30 stops advertising
  while a phone app holds it" is likewise still true — phone = BLE central.)
- measure_bridge.py:636 (calibrate docstring): "one connection at a time —
  the CR30 stops being visible while anything holds it" — "anything" is too
  broad (USB does not stop advertising); the engineering conclusion (reuse
  the session's handle, don't open twice) is unaffected. Wording fix only.

## F10.2 The hazard: a phone-side action underneath a USB session
Mechanism, from the code: the USB wait is
`usb_measure.wait_for_button_header` — ANY unsolicited BB 01 09 header
arriving on the serial link is taken as "the operator pressed the button"
and the reading is fetched and attributed to the highlighted patch
(workflow/cr30/device.py read_next_measurement, usb branch). So:
- IF the device mirrors measurement events to both links, a phone-app
  trigger (or a phone-side button-notification echo) lands in ChromIQ's USB
  session as a patch reading — silently mis-attributed. Marker byte 58 would
  not save us: the wait does not know which host asked.
- A phone-side CALIBRATION (bb 10/bb 11 over BLE) mid-session would rewrite
  the references under a running chart with, most likely, NO unsolicited USB
  traffic at all — every patch after it on a different calibration,
  invisible.
- Vendor "Sync to Instrument" mid-session: the only setting suspected of
  changing measurement data is Average (19_design5 R3, uncaptured); same
  silent-under-session shape.
WHETHER events mirror across links is UNKNOWN — concurrency itself was only
discovered tonight. It is a 2-minute passive test: ChromIQ-style USB listener
open, owner triggers from the phone over BLE, watch for the unsolicited
header. Add it to the owner session (it sends NOTHING).

## F10.3 Judgment on warning text: NOT YET
Do not add "close the phone app" to the how-to window or the no-device help
now: the interaction is unverified, the how-to window is already long, and
warning every user on every Start about an interaction never observed is
exactly the §M inflation the catalogue exists to prevent. Decision rule: if
the 2-minute listen shows cross-link mirroring, the line EARNS its place in
M-CR30-HOW-TO-MEASURE (it is then a real silent-data hazard); if not, a
sentence in the troubleshooting help at most.

## F10.4 The capture procedure: quit ChromIQ anyway
The concurrency makes the vendor-app capture EASIER (no unplugging), but the
procedure should still say: quit ChromIQ and any probe first. Reasons that
survive the convenience: (i) an armed USB reader consumes unsolicited frames
— if events mirror, ChromIQ would EAT the very calibration/measurement
traffic the capture exists to observe, or interleave its own chunk fetches
with the vendor's; (ii) the capture must show the vendor's traffic alone to
be replayable evidence; (iii) a passive open is PROBABLY inert (transport
rules: device silent when idle, no settle writes) but "probably inert" is
not a property a capture's provenance should rest on.

# RANKED RISKS (amended)
1. (unchanged) Shipping bb 10 unverified.
2. NEW, and now #2: cross-link interference — a phone-app trigger or
   calibration landing under a live USB session, mis-attributed or silently
   recalibrating mid-chart (F10.2). Unverified mechanism, 2-minute passive
   test, decision rule in F10.3.
3. Zero check with a cap on = silent white calibration (was #2).
4. One-sidedness misread as verification (was #3).
5. 0.05 %R threshold provisional on EXP-020 re-run (was #4).
6. Modal fatigue if black is bundled per-Start (was #5).
7. Corpus hygiene: EXPERIMENTS.md holes + the two TRANSPORT_BLE.md claims
   F10.1 now disproves — mark in place before the next agent trusts them.

# OWNER SESSION — procedure consolidated (one sitting, ~15 min)
0. Quit ChromIQ and all probes (F10.4). Baseline: air ×3, paper ×3 (probe,
   freshness-enforced).
1. PASSIVE cross-link listen (~2 min, sends nothing): USB listener open,
   phone connects over BLE, one phone-app trigger, one phone-app disconnect.
   Record whether ANY unsolicited USB frame appears. (F10.2)
2. EITHER vendor-app calibration wizard over BLE with PacketLogger capturing
   (zero-risk path — but note USB listener CLOSED for the capture proper,
   F10.4), OR — if he lifts the standing instruction — send bb 10 once, cap
   off, port down, dim light; re-read air + paper; compare.
3. Re-run EXP-020 with per-reading freshness enforcement (~3 min). (F4)
4. Finish: cap + button white cal (the verified procedure), final air +
   paper read-back.
