# 42 — The learned tile guard and the host trigger: challenge round (pre-implementation)

**Status: COMPLETE.**

Round rules: no CR30/serial access, no on-screen app, no `--runslow`. Code
reading, offline reasoning, targeted offscreen tests only. No source edits.

Inputs treated as PROVEN (measured on the owner's unit 2026-08-30,
EXP-TILE-002/-003/-004, `docs/THE-CAPPED-PRESS-IS-HARMLESS.md` in the
research repo — read in full for this round): repeat noise 0.05–0.25 %R;
button press ~0.5 %R; lift-and-replace 2.36 %R mean / 3.84 %R worst band;
a capped press does NOT damage the white reference (sign-flipping shifts =
repositioning, not a monotonic reference shift); every capped press: gate
flag True, matches TILE_SIGNATURE to 0.000046 %R, presses within a run
bit-identical; TILE_SIGNATURE stored at 4 decimals vs 6 returned;
`button_header_is_gated` returns None for solicited replies.

---

## DESIGN 1 — the learned tile guard

### 1a — BROKEN AS SKETCHED: the calibrate-white read-back does not contain the tile. It contains ZEROS

The sketch: "when the user performs a white calibration ... read back the
resulting spectrum and store it as that unit's learned tile signature."

The codebase itself already proves this cannot work.
`DeviceReader.calibrate` (`workflow/cr30/measure_bridge.py:848-878`)
documents, from the owner's own Bluetooth session of 2026-08-30:

> "⚠ IT IS ZERO-FILLED, AND THAT IS THE ANSWER, NOT A FAILURE. ... After a
> calibration the stored slot IS zeros, and knowing that is precisely what
> this read is for."

The read-back after `CAL_WHITE` needs `allow_dark=True` precisely because
the slot holds zeros — fourteen measured seconds were once lost to
retrying it. So learning from the calibration read-back stores a zero
spectrum (or nothing), and the guard would then "match" zero-filled
truncated replies — which a different guard (`zero_run`) already rejects
for a different reason. **PROVEN from the code's own measured comment.**

What actually returns the tile constant is a **GATED acquisition**: every
capped press in EXP-TILE-002/003/004 returned it (gate True, signature
match), and EXP-BLE-015's capped HOST trigger did the same over BLE. And
the harmlessness of a capped press — today's headline result — was
measured **for exactly this purpose**: the research write-up says "The
tile guard we want to build asks users to press the button with the cap
on, so the answer gates the whole feature."

**Corrected learning moment:** after the app's white calibration, cap
still seated, ask for one capped press (USB: the unsolicited `BB 01 09`
header's gate flag True is the PROVENANCE — we know these values are the
tile, not a patch). Over BLE there is no flag, so ask for TWO capped
presses and require the pair to be **bit-identical** — genuine readings
never are (EXP-TILE-004, EXP-MEAS-001), so a bit-identical pair is itself
proof of gatedness, unit-independent, no flag needed. That provenance rule
falls straight out of the measured data and needs no new hardware fact.

(Also, naming: the entry point is `CR30.calibrate(black=False)`;
`calibrate_white` survives only as a thin compatibility alias,
`device.py:341-343` — "Prefer that". The design should name `calibrate`.)

### 1b — The per-unit key: PROBABLY real, but NOT available on the BLE fast path, and the sketch cites the wrong sub-command with single-unit evidence

Facts from `workflow/cr30/identity.py` and the research repo's
`LOCAL_DEVICE_IDS.md` (both read):

- `AA 0A 00` (SUB_MODEL) carries `device_id` — this unit: a
  `PT…`-shaped string. `AA 0A 01` (SUB_SERIAL) carries `second_id` — a
  `CM…`-shaped string. Two different ids, two different frames.
- The claim "the BLE advertised name is the `AA 0A 01` value" appears in
  `device.py::open_ble`'s docstring; it is a SINGLE-UNIT observation and I
  found no capture pairing the advertisement with the id frames
  byte-for-byte. Which of the two ids the advertisement carries should be
  checked against the owner's unit before keying on it. INFERENCE flagged,
  not disproof.
- **Stability**: both ids are device-stored strings that read like
  serials. No evidence they ever change; no evidence they cannot. On the
  only unit ever probed they have been constant across every session.
  INFERENCE (single unit).
- **Uniqueness**: serial-shaped, so probably unique — but `identity.py`'s
  own preamble warns the FIELD OFFSETS are "PROBABLE where a second unit
  could disagree", and the `suspect_fields` mechanism exists because a
  longer string on another unit runs to the window bound. A second unit
  might yield a truncated or shifted id. INFERENCE, honestly weak.
- **Availability before any reading:**
  - USB: YES — `open_usb` already identifies every candidate
    (`Session.identify` sends the `AA 0A` frames), so the id is in hand
    before the first measurement. PROVEN (code path).
  - BLE discovery path: YES-ish — the advertised local name is captured in
    `discover()`'s candidate dicts before connecting. PROVEN available;
    whether it IS the id string is the single-unit claim above.
  - **BLE remembered-address fast path: NO.** No advertisement is ever
    read (report 41, Q3 — a directly-addressed connection never sees
    one), no `bb`-frame twin of `AA 0A` is known, and whether the module
    answers the standard GAP Device Name characteristic (0x2A00) has
    never been probed. **The sketch's premise fails exactly on the path
    the app prefers.** Hardware question, listed at the end.

**Workable keying despite this:** persist the learned signature keyed by
unit id, AND persist the association `(BLE address → unit id)` at the
moment both are known (discovery, or any USB session). The fast path then
resolves address → id → signature with no extra radio traffic. If a
DIFFERENT CR30 ever occupies the remembered address, the wrong signature
simply never matches (the only other unit we have data for sits 4.69 %R
away — 94× the old tolerance, ~50,000× the proposed one), so the failure
direction is "guard silently unarmed", identical to today, never a false
refusal. And since essentially every user owns one unit, a
single-signature store with the id as a consistency check covers the real
population; the id key is correctness, not load-bearing.

### 1c — Full-precision comparison: bit-equality is sound on the evidence, but give it a hair of tolerance so the guard cannot silently disarm

The sketch's own trap note is confirmed: `TILE_SIGNATURE` is stored at 4
decimals (`measurement.py:70-76`), the device returns 6 (both transports
round to 6: `round(x, 6)` in `ble._parse_reply` and
`usb_measure.assemble` — PROVEN, code read), so bit-equality against the
hard-coded constant can never fire. The existing check survives only
because `looks_like_calibration_tile` uses tol=0.05, which swallows the
≤0.00005 truncation residue.

For a LEARNED 6-decimal signature, is bit-equality right?

- Cross-transport: same float32, same `round(,6)` → bit-equal across
  USB and BLE. PROVEN from code; corroborated by the comment that
  TILE_SIGNATURE was captured over BOTH transports "bit-identical every
  time" (EXP-MEAS-002/003, EXP-BLE-010).
- Across time and across a recalibration: the 2026-08-30 capped presses
  match the 2026-08-28 constant to 0.000046 %R — which is exactly the
  4-decimal rounding residue, i.e. the underlying 6-decimal values are
  **identical**, and the owner recalibrated white in between (EXP-022,
  2026-08-29). So the gated constant is factory-fixed, not the last
  calibration, and bit-stable across days AND across `CAL_WHITE`. PROVEN
  on this unit; single-unit as always.

The residual risk of strict bit-equality is not false positives (a real
patch matching 31 floats to 6 decimals against 0.05 %R noise is
effectively impossible — this check is strictly TIGHTER than today's, so
B2-10's near-white worry shrinks, never grows) — it is a **silent
disarm**: any future change in the float path (a parser tweak, a
different rounding, a firmware update) makes the learned value miss by an
ulp and the guard quietly stops existing, which is the worst failure mode
a safety check can have. Recommendation: compare at a tolerance of
0.001 %R per band (20× the observed residue, 50× below the instrument's
own noise floor, 4,690× below the nearest other unit's tile). It behaves
as bit-equality on all measured data and cannot be killed by an ulp.
Keep the hard-coded 0.05-tol check for unlearned units, stated honestly:
it protects the owner's unit and contributes nothing on the only other
unit ever measured (`measurement.py:170-181` says so itself).

### 1d — The rolling bit-identity window ALREADY EXISTS, at N=2, raising — do not build it again

House rule, learned the hard way: *check it does not exist before
building it.* It exists. `Measurement.identical_to` +
`check_usable(previous)` (`workflow/cr30/measurement.py:188-224`) raise
`MeasurementError` on the FIRST bit-identical repeat — that is a rolling
window with N=2 and a hard stop, already wired into every reading path
(`read_next_measurement` calls `m.check_usable(self._previous)`,
`device.py:456-459`). PROVEN.

Is N=2 justified by the data? Yes: genuine consecutive readings always
differ — untouched, host-triggered repeat noise is 0.05–0.25 %R
(EXP-TILE), worst-band SD 0.056 % (EXP-MEAS-001), and EXP-TILE-004's
untouched groups never produced a bit-identical pair. So N=2 has no
false-positive cost on any measured evidence, and any larger N only
delays the alarm by (N−2) accepted-wrong patches. **N=2, and it is
already shipped.**

What the window genuinely cannot do — and no window can:

- the FIRST reading of a session (`identical_to(None)` is False): a gated
  first patch is caught only by the gate flag (USB button) or the
  signature. This is B2-9's hole, and the learned signature is the fix —
  the window is not.
- `self._previous` lives on the `CR30` object and resets when a
  `DeviceLost` reopen builds a new one (`measure_bridge.py` __call__),
  so the reading either side of a reconnect is not compared. Minor;
  worth one line in the implementation, not a mechanism.

One obligation this places on Design 2: a host-triggered reading must
flow through the SAME `check_usable(previous)` gate, or the trigger path
silently loses the only unit-independent guard unlearned units have.

### Design 1 verdict — build, with three named corrections

1. Learning source: a capped GATED acquisition after calibration (USB:
   one press, gate-flag provenance; BLE: two presses, bit-identical-pair
   provenance) — NOT the calibrate-white read-back, which is zeros.
2. Key: unit id where obtainable, plus a persisted address→id
   association for the BLE fast path; verify WHICH id the advertisement
   carries before trusting the docstring's `AA 0A 01` claim. Single
   global signature is an acceptable v1 for a one-instrument world.
3. Comparison: 0.001 %R per-band tolerance (bit-equality with an ulp
   guard), hard-coded 0.05 check kept for unlearned units.
4. Item (d): do not build — already exists at N=2 with a raise. Spend
   the effort on the two real holes (first reading; `_previous` across
   reopen).

---

## DESIGN 2 — the host trigger

### 2-1 — Post-hoc detection is acceptable ONLY for units with an armed tile guard; and the "implausible" damage scenario has already happened once in the wild

The narrowing is real: with the cap on, the surface under the aperture IS
the tile, so a gated trigger's calibration write is a correct calibration
(today's finding, PROVEN). Real damage needs a magnet WITHOUT the tile —
and the codebase records precisely that happening in a real session:

> "It happened for real on 2026-08-30: a sheet of paper on a MacBook,
> whose magnets reached through it." (`MagnetGated` docstring,
> `measurement.py:44-52`; also `_on_cr30_magnet`, `tab_measure.py:7823`)

Laptops, magnetic desk mats, tool trays — the magnet-with-paper state is
a normal desk, not a contrivance. So "how plausible is it in a
chart-reading session" is answered: it has a confirmed occurrence in the
first month of real use. The MacBook case is exactly the case today's
finding does NOT narrow.

Does the host trigger write in that state? EXP-BLE-015 proved the host
trigger performs the calibration when a magnet is present (capped case),
and the device cannot distinguish the cap's magnet from a MacBook's —
so INFERENCE, strong: yes, against paper. Paper is ~8 %R brighter than
the tile, and calibrating against a brighter surface DEFLATES every later
reading — the direction `measurement.py`'s own skeptic note calls
invisible ("~8 % DARK, forever, with no symptom at all"). That is the
stake.

Given that, post-hoc is acceptable where the RESULT is recognisable:
a gated trigger returns the tile constant, an armed signature catches it
on that very reading, the existing `_on_cr30_magnet` loop stops the
session and performs the recalibration (proven to restore, EXP-022), and
the damage window is one write that the recovery fully undoes. For an
UNLEARNED unit over any transport (and the owner-constant check on any
other unit), the first gated trigger reading is ACCEPTED — wrong colour
in the .ti3 AND a corrupted reference, both invisible until the second
trigger trips the bit-identity guard, and the reference stays wrong until
someone recalibrates. That is not an acceptable ship state. Hence 2-3.

Note also: the BUTTON path already lives with the same post-hoc model —
EXP-MEAS-003 could not attribute the write to trigger vs press, so a
gated button press may also have already written by the time the gate
flag is read. The host trigger does not introduce post-hoc-ness; it
removes the one unit-independent detector (the flag). The honest framing
is "the trigger must bring its own detector", which is the tile guard.

### 2-2 — The experiment that settles EXP-MEAS-004 (specified, not run)

**Question.** With a magnet present and a NON-tile surface under the
aperture, which of {host trigger, button press} performs the calibration
write?

**Safety envelope.** Only the WHITE reference is at risk, and the capped
white calibration provably restores it (EXP-022; and today's result —
capped calibration is a correct calibration). `CAL_BLACK` is never sent.
Recovery is rehearsed between arms, so no state outlives a step.

**Setup.** USB, the owner's unit. A green surface (the known-worst
reference corruptor, EXP-CAL-002/EXP-MEAS-003) over the MacBook spot that
gated through paper on 2026-08-30 — a magnet source that needs no cap
near the aperture. A fixed paper spot P marked so re-placement is
repeatable. All paper reads HOST-TRIGGERED with the instrument left in
place (repeat noise 0.05–0.25 %R; avoids the 2.36 %R repositioning term
for the within-group comparison).

**Protocol.**
1. Calibrate white properly (cap seated, app's own flow).
2. Baseline: place on P, host-trigger 3 reads → R0 (untouched, so
   spread should be ≤0.25 %R — this is the run's negative control).
3. Move to the green-over-magnet spot. Send ONE host trigger. Record the
   returned spectrum (expected: tile constant — that is the positive
   control that gating actually occurred; if it is NOT the tile
   constant, the spot was not gated and the arm is void, not negative).
4. Back on P: host-trigger 3 reads → R1.
5. Recover: capped white calibration; re-read P → must return to R0
   within ~1 %R before proceeding.
6. Repeat 2–5 with a BUTTON PRESS in step 3 instead of the trigger.

**Decision rule.** "The write happened" = R1 differs from R0 by a
systematic, same-signed shift well above the repositioning band —
expect tens of %R with a green reference (EXP-CAL-002 showed paper at
156 %R mean after green corruption), against ≤0.25 %R untouched noise
and ≤4.7 %R repositioning; a spectrally structured shift (green-shaped)
is corroboration. "No write" = R1−R0 mean below ~2 %R with mixed signs.
The two arms attribute the write: trigger-arm shift ⇒ the trigger
writes; press-arm shift only ⇒ only the button writes; both ⇒ both.

**Recovery step**, stated for the operator: seat the cap, run Calibrate
White in the app, confirm P reads back at R0 ± ~1 %R. Repeat if not.

Time: ~10 minutes. Every phase carries its own control, per the
positive-control house rule.

### 2-3 — Yes: gate the host trigger on an armed tile guard, on BOTH transports

Argued for above (2-1). The extra points that decide it:

- On USB the host trigger is exactly as blind as on BLE: the gate flag
  lives only in the unsolicited `BB 01 09` button header; a solicited
  reply has 0xFF at byte 58 and `button_header_is_gated` returns None
  (PROVEN by the owner's run and by `usb_measure.py:59-71`). So there is
  no "safe transport" for the feature.
- The refusal costs nothing real: the fallback is the button — today's
  only path — and the arming action (one capped press after
  calibration) is a ten-second step the calibration flow can offer.
- Refuse with an explanation, not silently: see the dialog section for
  proposed wording. Space/Enter falling back to "nothing happens" would
  repeat the discoverability hole this design exists to fill.

### 2-4 — Cheaper moves, judged

- **"One button-pressed reading first to establish gate=False":
  REJECT as a safety basis.** The magnet state is dynamic — the MacBook
  event arose mid-session from where the paper happened to lie. A
  gate=False at patch 1 proves nothing about patch 40. (Fine as a
  smoke-test UX nicety; worthless as the guard.)
- **"Check the result against the signature before accepting AND before
  allowing the next trigger": ACCEPT — this IS the armed-guard flow**,
  and it bounds exposure to at most one questionable write between
  checks, which the recalibration flow fully recovers. It should be
  stated in the design that the check runs before the reading is
  accepted (i.e. inside `check_usable`, where the signature check
  already lives) so the trigger path cannot bypass it.
- **Backstop nobody named: the existing N=2 bit-identity guard already
  catches a gated trigger on the SECOND trigger** even on an unlearned
  unit (gated readings are bit-identical). Insufficient alone — the
  first reading is still poisoned — but it means the worst case on an
  unlearned unit is bounded at one bad patch plus an un-flagged
  reference write, which is why 2-3's refusal matters more than any
  extra mechanism.
- **Implementation trap to carry into the design (BLE):** a host trigger
  makes the instrument emit the same `bb 01` event a button press emits
  (EXP-BLE-015: "our own trigger produced one too"), and
  `trigger_unsafe`'s `done=saw_event(0x01)` CONSUMES it. The clean
  integration is the opposite: send the trigger and let the existing
  wait-for-event → read → `check_usable` pipeline treat the event as if
  it were a press — every guard is then inherited for free, including
  bit-identity and the signature. If the trigger path instead consumes
  the event and reads directly, it must re-implement the guard chain,
  which is how guard gaps are made. On USB the equivalent care: the
  trigger's solicited header is not a button header, so `read_stored`
  gets `button_header=None` and records `axis_source` as ASSUMED —
  `usb_measure.trigger` returns the parsed axis from its own reply, so
  the design should extend `read_stored` (or the caller) to carry that
  axis and an `origin: host-trigger` marker instead of shipping an
  "assumed axis" reading. (ERRORS.md's read-the-axis rule.)

### Design 2 verdict — build only WITH the guard requirement, and hold the trigger-near-magnet question open until EXP-MEAS-004

Build the plumbing (keys → bridge → reader.trigger), but:
1. The trigger is refused unless the tile guard is armed for the
   connected unit (learned signature; the hard-coded constant arms the
   owner's unit). Friendly refusal window naming the button fallback and
   the ten-second arming step.
2. The trigger path reuses the event→read→`check_usable` pipeline
   (BLE) / carries the solicited axis honestly (USB).
3. EXP-MEAS-004 is run before the feature leaves beta — if the trigger
   turns out NOT to write, the safety story simplifies to post-hoc
   detection with zero damage, and the refusal could later be softened
   to a warning; if it DOES write, the guard requirement stays
   permanent. Either answer is buildable; the DEFAULT posture until it
   is known must be the conservative one.

---

## DIALOG TEXT

§M discipline (docs/design/unified_measurement_management.md, enforced by
`tests/test_message_catalogue.py`): every text below goes to §M-PROPOSED
with `approved=False` first. None of it is final wording; it is drafted to
the owner's stated bar — "correct, friendly, extensive and easy to
understand".

### A real shortfall in an existing dialog: the magnet window tells its story twice, once kindly and once shouting

`M_CR30_MAGNET`'s body (`measurement_messages.py:167-186`) is good —
concrete culprits (laptop lids, fridge doors, desk mats), reassurance
about saved work, a physical remedy, and the app doing the recalibration.
But it ends with `What the instrument reported: {reason}` — and the
`reason` the bridge passes is the raised exception's text, which for a
gated reading is the ENTIRE `MAGNET_MESSAGE` paragraph
(`measurement.py:56-63`):

> "this reading was taken with a magnet at the aperture. The CR30 does
> not measure in that state -- it performs a WHITE CALIBRATION against
> whatever is under the aperture ... STOP: remove the cap and any magnet,
> and RECALIBRATE before reading anything else. ..."

So the user reads the same explanation twice — the window's friendly
version, then a telegraphic ALL-CAPS version with `--` dashes presented
as "what the instrument reported", which it is not (the instrument
reported a flag bit; the paragraph is ours). Proposal: raise `MagnetGated`
with a SHORT technical tail suitable for the `{reason}` slot — e.g.
`"the device's own header flagged the reading (gate flag set)"` or
`"the reading matches this unit's stored tile value exactly"` — and keep
the long teaching paragraph out of the exception text (the window already
teaches). Also worth a pass: the body's ALL-CAPS sentence ("EVERYTHING
YOU MEASURED BEFORE THIS IS SAFE") — the reassurance is right, the
shouting is a style call for the owner.

Related routing gap that Design 1 happens to fix: the bit-identical
refusal text ("reading is bit-identical to the previous one. Either no
new measurement was taken, or a magnet is gating the device. Genuine
repeats differ in the low bits.", `measurement.py:218-222`) reaches the
user through `M_CR30_READ_FAILED`, whose remedy is "Press the button on
the instrument again" — which is the WRONG advice for the magnet half of
its own diagnosis (pressing again while gated produces another identical
reading, and possibly another calibration write). Once the learned
signature exists, the gated case is caught as `MagnetGated` before the
bit-identity check, and the leftover bit-identical case really is "no new
reading was taken", for which the retry advice is correct. Until then,
"bit-identical" and "low bits" are jargon in a user-facing window; a
plainer sentence is proposed below.

### Proposed §M-PROPOSED texts (all `approved=False`)

**M-CR30-TILE-GUARD** — the guard refuses a reading (signature match,
no gate flag available; the gate-flag case stays with M-CR30-MAGNET):

> Title: "That was the instrument's white tile, not your patch"
>
> "The reading for patch {loc} is an exact copy of the instrument's own
> white-tile value, and no real patch ever reads exactly like that. It
> means something magnetic was against the measuring opening — the CR30
> then reports its stored tile value instead of measuring, and it may
> also have retaken its white calibration from whatever it was resting
> on.\n\nEverything you measured before this is safe and already
> saved — ChromIQ refused this reading before using it.\n\nThe usual
> culprit is hidden: a laptop has magnets in its lid and body that reach
> straight through a sheet of paper, and so do magnetic desk mats and
> the instrument's own cap lying nearby.\n\nMove the chart onto
> something non-magnetic, then press “Recalibrate now” —
> ChromIQ takes the white calibration for you and carries on from the
> patch you were on."

(Deliberately reuses M-CR30-MAGNET's vocabulary and its two-button flow;
it should feed the same `_on_cr30_magnet` loop, because the state and the
remedy are identical — only the evidence differs.)

**M-CR30-STALE-REPEAT** — replacement for the bit-identical refusal's
user-visible sentence (the technical text stays in the log):

> "The instrument returned exactly the same numbers as last time, down
> to the last digit. Real readings always differ a little, so this
> means no new measurement was taken. Press the instrument's button
> once, firmly, with it resting on patch {loc}."

**M-CR30-REFERENCE-SUSPECT** — if a host trigger was sent and only
afterwards was gating detected (the post-hoc case Design 2 accepts):

> Title: "Your CR30's white calibration needs to be taken again"
>
> "ChromIQ asked the instrument to measure, and the answer shows a
> magnet was against the measuring opening at that moment. When that
> happens the CR30 may retake its white calibration from whatever it
> was resting on — and a wrong white calibration quietly changes every
> reading after it.\n\nNothing measured before this moment is affected,
> and it is all saved.\n\nPress “Recalibrate now”: ChromIQ
> seats the calibration properly and checks the result, then carries on
> from the patch you were on. This takes a few seconds."

**M-CR30-TRIGGER-NOT-ARMED** — the host trigger refused on an unlearned
unit (Design 2 item 1):

> Title: "Measuring from the keyboard needs one quick setup step"
>
> "ChromIQ can take each reading for you when you press the space bar,
> so the instrument never moves between patches — that makes readings
> about ten times steadier than pressing its button.\n\nTo do that
> safely, ChromIQ first needs to know what your instrument's white tile
> looks like, so it can tell a real patch from a covered opening. That
> takes one press: after calibrating, leave the cap on and press the
> instrument's button once when ChromIQ asks.\n\nUntil then, keep using
> the button on the instrument — every reading still works exactly as
> before."

**Discoverability of the trigger** — where the Space hint lives: the one
window every CR30 spot session already shows is `M_CR30_HOW_TO_MEASURE`
("Ready to measure, patch by patch", `measurement_messages.py:343-353`,
shown modeless once per measurement, `tab_measure.py:8050`). Add one
sentence to its body:

> "You can also press the space bar (or Enter) to take the reading from
> here, without touching the instrument — that keeps it perfectly still
> and makes the readings steadier."

plus the same line in `patch_measurement_instructions_html("cr30")`
(`ui/ti2_loader.py`) so the strip/how-to card agrees, and the existing
keyboard-shortcuts help card (the a11y round's) gains a row. The key
routing itself: `tab_measure.py:10972`'s handler currently forwards
Space/Enter to `self._manager.send_key(" "/"\r")`, which a CR30 session
ignores (no Argyll process reads them) — so the design must intercept
BEFORE that forward when a CR30 bridge is live; that is where the
armed/not-armed branch (and M-CR30-TRIGGER-NOT-ARMED) hangs.

### Other existing CR30 texts checked against "correct, friendly, extensive, easy to understand"

- `M_CR30_CALIBRATE_BLACK` — strong; one line worth the owner's eye:
  "Getting this step right is your eyes, not ours." — charming or too
  casual, his call.
- `M_CR30_READ_FAILED`, `M_CR30_INSTRUMENT_GONE`, `M_CR30_PATCH_GAVE_UP`
  — read; no correctness fault found; `{reason}` appending raw technical
  text is deliberate and documented (kept for bug reports), and unlike
  the magnet case the technical tail there is short.
- `validate()`'s out-of-range message (`measurement.py:147-151`) still
  ends "recalibrate against the white tile (seat the cap correctly,
  press the device button)" — the SIDE-EFFECT method the project has
  stopped recommending; `measurement.py`'s own note under
  MAGNET_MESSAGE says the app now recalibrates with the instrument's
  command instead. Same fix as the magnet `{reason}`: shorten, point at
  the app's Recalibrate flow.

---

## What must be settled on hardware first

1. **EXP-MEAS-004** (specified above) — does the host trigger write the
   calibration with a magnet + non-tile surface? Decides whether Design
   2's guard requirement is permanent or relaxable.
2. **Which id string the BLE advertisement carries** (`AA 0A 00`'s or
   `AA 0A 01`'s value) — one scan next to `LOCAL_DEVICE_IDS.md` settles
   it; decides the key field for 1b.
3. **Whether any id is readable over a direct BLE connection** (GAP
   0x2A00, or an undiscovered `bb` frame) — decides whether the BLE fast
   path can ever verify the unit, or must rely on the address→id map.
4. **The learning flow itself on the real unit**: one capped press after
   calibration returns the tile constant at 6 decimals, twice,
   bit-identically — expected from EXP-TILE, but the learning moment as
   a UI flow should be walked once on hardware before it ships.
5. (Carried over from report 41): a dedicated proof that `bb 02 10`
   never mutates state — 30 seconds, read-read-press-read-read.
