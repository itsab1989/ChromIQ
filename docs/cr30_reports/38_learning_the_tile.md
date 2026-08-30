# 38 — Learning the tile: can the magnet guard work on other people's CR30s?

**Status: COMPLETE.**
Agent: [CR30-TILE], 2026-08-30. Design analysis only; nothing implemented, no device touched.

## The question
`TILE_SIGNATURE` in `workflow/cr30/measurement.py` is hard-coded from the owner's unit;
the only other unit in the corpus differs by up to 4.686 %R (94x the 0.05 tolerance), so
no other owner has magnet protection over BLE (backlog B2-9). Owner's idea: learn the
unit's own white-calibration value during the calibration step (cap on = magnet present)
and use that as the per-unit signature.

**Recommendation in one line: build the NARROW version — learn only under a
proof of gatedness (bit-exact repeat behind a zero-fill freshness check), match
at bit-equality (tighter than today's 0.05), warn-only until two independent
learns agree, key per device-id — and never the naive version.**

---
## 1. The premise, checked against the captures

**The owner's mechanism is real, but his description of it needs one correction.**

What is PROVEN in the corpus (owner's unit):

- A magnet-gated reading returns a stored constant with **zero dependence on the
  optical input**: `EXP-MEAS-002` (white tile under aperture) and `EXP-MEAS-003`
  (cap reversed, GREEN face under aperture) returned **bit-identical** 31-band
  spectra — max abs difference 0.0 (`MEASUREMENT.md` §EXP-MEAS-003, VERIFIED).
- The same constant came back over BOTH transports (`EXP-BLE-010`, `EXP-BLE-015`)
  and in `EXP-MEAS-004` (`captures/public/EXP-MEAS-004-host-calibration.json`,
  step `host_trigger_capped` = `TILE_SIGNATURE` to the last digit).
- **The constant does NOT track the calibration just performed.** In
  `EXP-MEAS-003`/`004` the gated trigger performed a white calibration against
  the WRONG surface (readings afterwards inflated ~1.84–1.96x), yet the gated
  value returned was still the unchanged constant. And after the reference was
  RESTORED (`EXP-MEAS-004` step `restored`, ratio 1.0012) the constant was
  again unchanged.

So the value is **not "the value the device read on a white calibration"** in
the live sense — it is a stored *characterisation of that unit's tile*
(plausibly factory-set), stable across calibration corruption and restore.
**That stability is good news for learning**: a learned constant does not go
stale when the user recalibrates.

**Is there a second unit's gated reading?** Effectively yes, at CORROBORATED
strength. `PRIORART-001` ("Calibrate White and Black and Test Target.spm" and
"Test Sample white.spm", two separate vendor sessions on a third-party unit)
both contain host-triggered reads whose spectrum chunks are **byte-identical
across the two sessions** (frames `bb 01 11 00 00 00 c7 ef …` etc. identical in
both captures). Genuine repeats are never bit-identical (0.056 %R worst-band SD
on our unit, `EXP-MEAS-001`; the vendor corpus itself shows byte-identical
repeats only in stored/gated contexts). Same flat-with-400nm-rolloff shape,
different numbers (mean 76.70 vs our 78.93, worst band 4.69 %R apart —
`MEASUREMENT.md` Hole 1). **Inference, not proof**: no capture records whether
the cap was on at those triggers; bit-identity across sessions plus the tile
shape is the evidence. Verdict: the per-unit stored-constant mechanism
replicates on the only other unit we can see.

## 2. The zero-fill complication — WHEN the value can be read

PROVEN (owner's hardware, 2026-08-30, `workflow/cr30/measure_bridge.py::calibrate`):
after a `bb 11` white calibration the stored measurement slot is **zero-filled**;
the read-back loop retried to its 12 s deadline every time until `allow_dark=True`
accepted the zeros. So "read the stored value right after calibrating" returns
ZEROS, never the tile.

**The resolution is in the vendor's own frame order** (`PRIORART-001`,
"Calibrate White and Black and Test Target.spm"):

```
bb 11 (white cal) → bb 10 (black cal) → bb 01 00 (TRIGGER) → bb 01 09 header
                                       → bb 01 10/11/12/13 (spectrum read)
```

The vendor app refills the slot by sending a **host trigger after the
calibrations**. With the cap seated that trigger is magnet-gated
(`EXP-BLE-015`, VERIFIED: cap on, host trigger → stored value = tile constant;
paper readings before 88.33 / after 87.68 %R, i.e. the redundant gated
calibration against the correctly-seated tile is harmless). So the learnable
moment is: **cap seated → one host trigger → read back the stored constant.**
Not "after bb 11" (zeros), and not from the bb 11 reply itself.

⚠ Two caveats the design must carry:
- The gated trigger IS a white calibration against whatever is under the
  aperture. Cap correctly seated = harmless (that is the tile). Cap reversed or
  absent = it corrupts the white reference (`EXP-MEAS-003`: green face, later
  readings 1.96x ± 0.38). Learning must therefore happen BEFORE the user's real
  calibration is trusted, and be followed by (or ordered before) a fresh
  `bb 11` white calibration — or simply ordered: learn-trigger FIRST, then
  bb 11 white + bb 10 black, so any corruption the learn could cause is wiped
  by the calibration that follows.
- If NO magnet is present at the trigger (cap not actually on), the trigger
  takes a REAL measurement of whatever is there and no calibration occurs —
  this is the wrong-learn hazard of §3.

---
## 3. The wrong-learn failure mode, attacked first

**The naive version of this feature is exactly as dangerous as feared, and the
corpus proves it.** If ChromIQ learns a reading taken with no magnet present, it
stores a REAL measurement of some surface as "the tile". Report 37 §"B2-10"
re-measurement: adjacent repeats of the same surface span **0.035–2.71 %R
worst-band, some pairs BELOW the 0.05 tolerance**. So a later genuine reading of
that same colour (e.g. paper white, if the instrument sat on the chart while the
user thought the cap was on) CAN fall inside the tolerance — and `MagnetGated`
does not merely skip a patch, it halts the session and tells the user their
calibration is corrupt. Repeatably, on every chart, forever. Strictly worse
than the current honest gap.

**The property that defuses it: a gated reading is bit-exact, a real one never
is.** The stored constant comes back with **max abs difference 0.0** across
runs, days, transports and optical inputs (EXP-MEAS-002/003/004, EXP-BLE-010/015);
the second unit's two sessions are byte-identical too. Real repeats always
differ in the low bits (0.056 %R worst-band SD held still, EXP-MEAS-001; zero
bit-identical genuine pairs in our unit's corpus). A learn is therefore
PROVABLE, not guessed:

- **Freshness proof**: `bb 11` zero-fills the stored slot (PROVEN 2026-08-30).
  A non-zero read after it proves a new acquisition happened after the
  calibration — the stale-cache confound (EXP-020, EXP-MEAS-002's own trap,
  and MEASUREMENT.md's note that unit 2's vendor repeats were byte-identical
  *because of caching*) cannot survive a verified zero-fill.
- **Gatedness proof, within a session**: two triggers, two reads, bit-identical
  → gated. (Residual hole: trigger 2 silently ignored → stale re-read of V1.
  Cannot be fully excluded over BLE.)
- **Gatedness proof, across sessions — the one that closes it**: two
  INDEPENDENT learns, each behind its own zero-fill proof, on different
  calibrations. Bit-exact agreement of two real measurements taken on
  different days is not a thing this instrument does; bit-exact agreement of
  two gated reads is what it always does. **Arm the hard-refuse behaviour only
  after two independent learns agree bit-exactly. Until then, the learned
  value may only WARN.**
- **Sanity envelope** (gross filter only, never the proof): both known tile
  constants sit at min 69.1–70.4, max 78.7–80.7, range 9.5–10.3 %R, 400 nm
  rolloff. Envelope: every band in 60–90 %R, range ≤ 15 %R, mean 70–85 %R.
  Plain paper fails it (EXP-MEAS-004 `before`: min 63.1, max 89.6, range 26.5).
  A flat neutral ~78 %R object could pass it — which is why the envelope
  alone must never arm the guard.
- **Over USB, a protocol proof exists**: a BUTTON press with the cap on carries
  offset 24 = 0x01 (2/2 gated, 0/20+ ungated — corroborated). A learn taken
  from a flagged button frame is proven gated by the device itself. The
  constant is transport-independent (bit-identical over both, our unit), so a
  USB-learned value protects later BLE sessions.

With bit-exact matching (§5) a wrongly-learned value is additionally almost
harmless even if it slips through: a real reading essentially never re-matches
another real reading to the last bit of all 31 float32 bands. The catastrophic
version of this feature requires BOTH a wrong learn AND a widened tolerance.
The design must therefore never widen the tolerance (§5).

## 4. Storage and keying

- **Key: the unit's device-id string.** Over USB `identity.py` yields
  `device_id` (+ `second_id`); over BLE the advertised name IS the device's own
  device-id string (`workflow/cr30/ble.py:79`). Same key both transports —
  a USB learn serves BLE sessions on the same unit.
- **Never an app-wide single value.** The existing `cr30_ble_address` /
  USB-port keys are explicitly hints, "never an identity"
  (`measure_bridge.py:651`), and per-host besides (macOS randomises BLE
  addresses per host). A signature stored like them would follow the machine,
  not the instrument. Store a map: `cr30/tile_signatures/<device_id>` →
  {31 float32 values at FULL precision (hex or repr — not 4-dp rounding, which
  the current `TILE_SIGNATURE` constant uses and which forces the 0.05
  tolerance), learn timestamps, transport, confirmation count, armed flag}.
- **Two instruments / swapped unit**: distinct ids → distinct entries; an
  unknown id simply has no signature yet (guard degrades to today's state, and
  should SAY so once per session, per B2-9's "it must be said").
- **Settings store failing / cleared**: guard degrades to inert, never to
  wrong. The owner's own unit keeps the compiled-in `TILE_SIGNATURE` as a
  pre-confirmed entry keyed to his device id.
- **Re-learn policy**: every white calibration is a free re-learn opportunity.
  A re-learn that disagrees bit-exactly with a CONFIRMED signature is itself
  information (stale-cache, cap-off, or a rewritten characterisation) — log it,
  warn, require re-confirmation; never silently overwrite a confirmed entry.

## 5. Tolerance — the arithmetic

- **Correctly learned (gated) constant: tolerance can be ~0** (bit-equality on
  float32, or ≤ 1e-3 %R to survive serialisation). Evidence: gated repeats are
  bit-identical (max diff 0.0) across days, transports, and optical inputs.
  This is TIGHTER than today's 0.05 — the learned guard, done right, is
  STRONGER than the shipped one, not looser.
- **Learned from a real (ungated) tile measurement instead**: each of learn and
  test carries ~0.056 %R per-band SD → difference SD ~0.079 %R; the expected
  worst of 31 bands ≈ 0.19 %R, so a reliable trigger needs tol ≈ 0.3 %R —
  **6x looser than today**, and B2-10 warns that anything much above 0.05
  begins to admit real readings (adjacent repeats reach down to 0.035).
  **So: if the learn cannot be proven gated, the honest answer is that learning
  makes the guard looser and riskier — and it must not hard-refuse.** This is
  the quantitative form of the brief's worry, and it is why the design stands
  or falls on the gatedness proof, not on tolerance tuning.

## 6. Alternatives compared

1. **Do nothing** (current): honest, zero risk, zero protection over BLE for
   everyone else (B2-9). The baseline any build must beat on SAFETY, not just
   coverage.
2. **Warn-only learned guard**: strictly safer than refusing; but the hazard is
   not the one reading — the gated event has ALREADY recalibrated the device,
   so a warning the user clicks through leaves every later reading silently
   wrong. Right as the UNCONFIRMED tier, wrong as the end state.
3. **Rolling bit-identity window** (no learning at all): keep the last N
   spectra of the run; refuse a reading bit-identical to ANY of them. Unit-
   independent, closes Hole 2's interleaved-gating gap and needs no learn step.
   Misses only the first gated reading of a run. **Cheap, safe, and worth
   doing regardless of the learned guard.**
4. **Prefer USB / button path**: `gate_flag` already gives every unit
   protection there; the gap is BLE-only. Saying "for chart reads, use USB"
   in the docs is a legitimate partial answer.
5. **Detect the magnet some other way**: none exists host-side — the magnet
   alone announces nothing (EXP-BLE-014), the BLE button frame has no room for
   a flag, and the gated host reply is indistinguishable by protocol
   (EXP-MEAS-003).

## 7. Recommendation

**Build the narrow version.** The owner's idea is mechanically sound — with his
description corrected (the learnable value is the unit's stored tile
characterisation, obtained by a cap-on TRIGGER, not by/after `bb 11`, whose
slot is zero-filled) — and, done narrowly, it produces a guard STRONGER than
the shipped one (bit-equality vs 0.05) with a worst case no worse than today
(inert, and saying so). The naive version (learn whatever the calibration step
reads, match at a widened tolerance, hard-refuse) must NOT be built.

The narrow version, in one paragraph: during the white-calibration step (cap
already on), after `bb 11`, verify the slot reads zeros, send one trigger, read
back; value must be non-zero and inside the sanity envelope; store it keyed to
the device id as UNCONFIRMED (warn-only). When a second independent learn
agrees bit-exactly, mark CONFIRMED (hard-refuse via `MagnetGated`, matching at
bit-equality). Over USB, a gate-flagged button frame confirms in one step.
Also implement the rolling bit-identity window (alternative 3) independently.

### Decisions needed before code
1. **Run the composed sequence once on real hardware** (owner present):
   `bb 11` → read zeros → trigger (cap on) → read. PREDICTION: the read equals
   `TILE_SIGNATURE` bit-exactly. The sequence is composed from three separate
   proofs (zero-fill; EXP-BLE-015; PRIORART-001's vendor order) and has never
   run end-to-end on our unit. If the prediction fails, the design fails.
2. **Ordering vs the real calibration**: learn-trigger before or after the
   user's `bb 11`? (After = simplest; the gated event recalibrates against the
   correctly-seated tile, harmless per EXP-BLE-015 — but confirm the black-cal
   step's position so the learn's own calibration cannot land on open air.)
3. **UX for the unconfirmed tier**: wording of the warn, and whether the user
   may manually confirm ("the cap was on") to skip the second session.
   Recommendation: no manual confirm — the app believing a user's answer about
   cap state is the seeded-widget trap in another coat.
4. **What the app says on an unknown unit** (B2-9 disclosure) and on a
   confirmed-signature MISMATCH at re-learn.
5. Whether the owner's compiled-in constant migrates into the store keyed to
   his device id (recommended: yes, marked confirmed, full-precision values
   re-captured once).

### Claim status
- PROVEN (captures/hardware): gated value is a stored, optically-independent,
  transport-independent, calibration-independent per-unit constant; `bb 11`
  zero-fills the slot; a cap-on host trigger refills it with the constant;
  real repeats are never bit-identical on our unit; adjacent repeats can fall
  below 0.05 %R.
- CORROBORATED (inference from vendor corpus): the second unit shows the same
  stored-constant behaviour (byte-identical across two sessions, tile shape);
  the vendor app itself uses trigger-after-calibrate; gate_flag discrimination
  (3 button frames, one unit).
- INFERENCE (not yet run): the composed learn sequence end-to-end (decision 1);
  cap state during the vendor's captured triggers; persistence of the constant
  across firmware/vendor-app recharacterisation (unknown — hence re-learn
  policy).

**Status: COMPLETE.**
