# 18 — CR30 strip reading: design review [CR30-STRIP]

Status: COMPLETE (2026-08-29). Design round only — nothing built.

## Verdict up front

**Build a reduced version, and only after EXP-019 passes.** The owner's idea
is sound and the strong formulation is indeed sequence alignment, not
white-boundary detection — but one blocker-class fact is unmeasured (whether a
reading taken in motion equals the settled reading of the same surface), the
honest speed gain at the SAFE operating point is ~1.5–2×, not the 2–3× in the
brief's table, and one safety property of the design (press-to-start) turns
out to be mandatory, not optional, because host-trigger streaming with a
capped device silently rewrites the white calibration. EXP-019 is written
(`~/develop/chromiq-cr30-research/tools/probe_strip_feasibility.py`) with
numbered steps for the owner, this session.

---

## 1. The arithmetic, checked

The table's algebra is right: readings/patch = 12/(v·0.315); smear = v·0.315;
window = 4 + smear; clean span = 12 − window; clean reads/patch =
clean span/(v·0.315); 26×12 mm = 312 mm; times check out (24.6 s / 32.7 s /
48.8 s; 390 patches = 15 strips).

Three corrections:

1. **The smear term is a HYPOTHESIS, not a measurement.** smear = v × 0.315
   assumes the optical integration spans the whole 315 ms cycle. Nothing in
   EXP-018 or the protocol corpus says how much of the cycle is integration
   vs processing/transfer. If integration is e.g. 80 ms, the smear at
   12.7 mm/s is 1.0 mm, not 4.0, and the 3-readings/patch row becomes
   comfortable. EXP-019 phase E measures the effective window directly
   (count intermediate samples crossing a sharp edge). Until then the table
   is a worst case, which is the right way round — but say so.
2. **The 3-readings/patch row has ZERO margin and must not be the design
   point.** 1.0 expected clean reads/patch means a patch whose boundary
   phase is unlucky gets 0 clean reads — and with reading starts random
   relative to boundaries that WILL happen, per strip, not per session. The
   design point is ≥4 readings/patch (9.5 mm/s worst-case, faster if phase E
   shrinks the window).
3. **The 6.1/8.2/12.3-minute figures omit per-strip handling** — reposition,
   press, settle, accept/reject, plus re-swipes. At 5–10 s handling per
   strip and a 10% re-swipe rate, the honest end-to-end at the safe point is
   ~10–15 min against ~23. Still a real prize — and the bigger prize is
   tedium: 15 swipes instead of 390 aimed presses. But 2–3× is over-sold.

Also verified against the raw capture (`captures/raw/EXP-018-rate-usb.json`):
phase A 39 cycles, 3.18/s, step ΔE median 0.0037 / max 0.0155, minimum step
0.0006 (never bit-identical — matters for `check_usable`); phase B median
0.2747 / max 6.8123, 15/38 > 1. The numbers in the brief are accurate.

**What EXP-018 phase B does NOT show:** it proves readings *track* the
surface in motion; it does not prove a moving reading *equals* the settled
reading of the same patch — nothing with known ground truth was under the
aperture, and the probe recorded no speed. Contact-instrument optics in
motion (tilt, pressure variation, edge light-leak while sliding) are exactly
where a colorimeter goes quietly wrong. That is the blocker-class unknown,
and it is EXP-019 phases C+D+F.

## 2. The insight, attacked: alignment beats segmentation — with three repairs

The reframing is right, and it has PRECEDENT IN THE HELPER ITSELF:
chartread's strip mode already identifies a swipe by correlation against
expected values — for every candidate strip × both directions × ±1 offset it
computes mean ΔE to `eXYZ`, tracks best-overall vs expected
(`chromiq_chartread.c:2390–2440`), warns `wrong_strip` when another row fits
better (`:2441–2480`, incl. the CHROMIQ F7-R extension for fixed-order
charts), and challenges the worst patch against ACC_WERR_TH=30/WERR_TH=95
(`:70–71`, `:2481`). ChromIQ's alignment layer should MIRROR that decision
structure; only the front half — turning a raw sample stream into per-patch
values — is genuinely new, because for i1Pro-class instruments the
*instrument* does the segmentation and chartread only ever sees one value per
patch.

But plain DTW against 26 expected colours has three failure modes the brief
does not name:

1. **Boundary samples are MIXTURES, not members of either patch.** A sample
   whose window straddles a boundary reads a blend; DTW will assign it to
   the nearer patch and, if the patch value is the mean of its assigned
   samples, corrupt it. Repair: a **garbage/transition state between every
   pair of consecutive patches** (fixed cost τ), so mixtures can be assigned
   to nothing; per-patch value = median of the assigned interior samples,
   and a patch with 0 interior samples after trimming REJECTS the strip.
2. **Low-contrast neighbourhoods (grey ramps, near-duplicate patches) give
   arbitrary boundary placement.** For exact expected-duplicates that is
   harmless (same colour either way, and monotonicity keeps counts sane
   given a dwell prior — bound each patch's dwell to ~0.5–2× the median,
   which the uniform 315 ms cadence makes meaningful: sample index IS time
   IS distance at steady speed). For ΔE 1–3 neighbours the residual error is
   of the same order — real but small. The confidence gate (below) must
   include per-patch *identifiability*, and a row that cannot be aligned
   confidently falls back to pressing. This will genuinely happen on
   neutral-ramp rows; say so in the UI rather than accepting weakly.
3. **A backup/hesitation violates monotonicity.** A monotonic aligner cannot
   represent "went back two patches"; it will produce a poor fit. That is
   the correct outcome — REJECT and re-swipe — provided rejection is cheap
   (§5). Do not attempt non-monotonic repair.

**Wrong strip / reversed strip — detected BEFORE anything is written.** This
is the decisive property and the design must guarantee it structurally:
identification (all not-yet-read candidate rows × both directions, mirror of
`:2390`) and the confidence gate both run on the completed sample stream, and
**no value is fed to the helper until the strip as a whole is accepted**. A
reversed swipe of the right row appears as the reversed template fitting
best; a wrong row appears as another candidate fitting best — both surface
as chartread-style warnings ("this looks like row F read backwards"), cost
one swipe, write nothing. Compare: the helper's own per-patch dE challenge
fires only at ΔE≥30 with accurate expected values (`:3216`) and only AFTER
the value is written and autosaved (`:3176–3179` precede the check) — it can
never be the alignment safety net.

**Expected-value quality caveat:** on a first-pass chart `eXYZ` comes from
targen's model, not measurement; absolute errors of ΔE 5–20 are possible.
Identification is robust to that because it is RELATIVE (margin over
second-best, exactly why chartread's own wrong-strip logic works pre-profile)
— but absolute residual thresholds must be loose unless `accurate_expd`
(chartread already distinguishes this, `:70–71`).

**Confidence gate (all must pass, else reject with a stated reason):**
- every patch has ≥1 interior sample; median interior count ≥2;
- expected row+direction is the best candidate AND beats the second-best
  by a margin (chartread's xbcorr/bcorr structure, `:2410–2424`);
- mean aligned residual under a loose bound (tightened when accurate_expd);
- per-patch within-segment spread ≤ the consistency tolerance (§4);
- stream book-ends match paper white (the press's own sample) at the start
  and white-or-air at the end.
Never silently accept — a wrong colour in a `.ti3` is invisible downstream
(the brief is right about that, and `measure_bridge.py`'s whole docstring is
the same doctrine for spot mode).

## 3. What already exists — reuse map (nothing new proposed where something exists)

| Need | Exists | Where |
|---|---|---|
| Feed 26 aligned values into the `.ti3` | YES — goto-by-loc + value, patch-at-a-time | helper `-x` path is spot-only by construction (`chromiq_chartread.c:2600` forces spot; one value per `spot_ready`, `:2812–3183`); cursor steerable by loc: 'g' goto with JSON stash (`:2837–2847`); `MeasureManager.goto_patch(loc)` (`workflow/measure_manager.py:801`); `{"cmd":"value"}` (`chromiq_json.c:191`, `measure_bridge.py:504`) |
| Randomised chart order vs physical order | NON-ISSUE | goto is by loc label, not index; `spot_ready` echoes id+loc+`exyz` (`:600–608`); `patch_read` echoes loc so pairing is verified (`measure_bridge.py` doctrine) |
| Strip identity / direction / offset validation | YES as a PATTERN to mirror, not callable for us | chartread strip branch `:2390–2480` — operates on per-patch `vals[]` an instrument delivers; our stream never reaches it |
| `-T` consistency tolerance | NOT usable — instrument-side only | `scan_tol` consumed solely via `inst_opt_scan_toll` at `:1209–1214`, inside the `xtern==0` block (`:918`); 17_verify4 already ruled it INERT for CR30. The tolerance must be REIMPLEMENTED in ChromIQ on the aligned segments — which resurrects the greyed spinbox 17_verify4 recommended, with a new, honest meaning (spread of in-patch samples, ChromIQ-computed). The greying design in 17_verify4 §4 should note this future un-grey condition rather than hard-coding "meaningless" |
| Physical geometry (patch length, spacers, rows, hex) | YES for engine charts | `workflow/layout_engine/geometry.py` — `Placement.x_of/y_of` (`:183–186`), `patch_rects_px` (`:453`), `spacer_rects_px` (`:528`), `strip_rects_px` (`:407`) |
| Live pace feedback | YES | `core/measure_pace.py` — built for exactly "samples/patch ≈ time × rate" (#131 Phase 2); CR30's rate is a measured constant, 3.18/s |
| Button-press as an event, with cap-off proof | YES, USB | unsolicited `BB 01 09` header, VERIFIED 3/3 (`usb_measure.wait_for_button_header`); gate flag at offset 24 exists ONLY there (`usb_measure.py:50–58`) |
| Per-sample sanity | YES | `Measurement.check_usable` (`measurement.py:178–201`): tile constant, zero-run, bit-identical (EXP-018 phase A min step 0.0006 says streams won't false-trip) |
| Resume / autosave / `.ti3` writing | YES — comes free through the helper | per-patch autosave `cq_write_ti3_atomic` (`:3179`), `-r` resume, `save_ti3` |
| Failed strip costs one swipe | BY CONSTRUCTION | nothing fed until accepted; a feed interrupted mid-way half-writes only CORRECT values, which resume + re-feed (goto overwrites) already handle — same recovery as spot mode today |

**What is genuinely new:** (a) a stream-trigger loop in `workflow/cr30/`
(trigger + fetch at 3.18/s with start/end logic), (b) the aligner + confidence
gate (pure Python, fully unit-testable against synthetic and EXP-019 streams),
(c) the feed loop goto→value→verify over the existing bridge, (d) UI: a
per-row "swipe" affordance with accept/reject display. Nothing in the helper
needs changing. That is the correct shape: the helper stays byte-identical.

## 4. The hard questions, answered

1. **Can it measure while sliding?** UNKNOWN in the decisive sense. EXP-018-B
   proves tracking, not accuracy; nothing else in the corpus touches motion
   (all repeatability work is settled-press). EXP-019 §6 settles it.
2. **Is a hand steady enough at ~9 mm/s over 312 mm?** Unknown; laterally the
   budget is ±4 mm (12 mm row, 4 mm aperture), which freehand over ~35 s is
   doubtful but WITH A RULER laid along the row is routine — i1Pro operators
   do exactly this. No chart change for v1: require a straightedge in the
   instructions. The helper markers are print-side aids for other purposes
   (`project_helper_markers_design_settled` — SETTLED, do not touch). The
   device's own beeps at 3.18 Hz are a free metronome IF it beeps per host
   trigger — record that observation in EXP-019 (F0 of 17_verify4 warns:
   never assert a beep fact without asking and storing the answer).
3. **Start/end.** Press-on-white is CORRECT and MANDATORY, for a reason the
   owner didn't have: the press's unsolicited header is the only place the
   magnet-gate flag exists; host triggers report 0x00 gated or not, and a
   gated trigger performs a silent WHITE CALIBRATION against whatever is at
   the aperture (`device.py:149–176`, EXP-MEAS-004 — the corruption that
   actually happened to this unit). So: press on paper white → header proves
   cap off → the press's own stored reading is sample 1 AND the live
   paper-white reference → streaming starts. END: primary = sustained
   paper-white/air after the aligner has plausible coverage; secondary =
   sample cap/timeout → reject. A second button press as an end signal is
   attractive but its unsolicited header would interleave with solicited
   chunk traffic mid-stream — the transport does not today tolerate that
   (risk R5); design it as an optional later refinement, not a dependency.
   Lift-off reads a distinctive signature (EXP-019 phase A measures it) and
   is likely the cleanest terminator: white-then-gone.
4. **Failed strip.** Reject before feed = zero writes; feed-after-accept
   failures half-write only correct values and re-feed overwrites (§3 table).
   One swipe lost, never a session; identical guarantee to today's spot flow.
5. **Scope honesty.** Genuinely good idea IF motion accuracy holds; the
   speed prize is honestly ~1.5–2× but the tedium prize (15 guided swipes vs
   390 aimed presses) is what the owner is really asking for. It WILL be
   fragile on neutral-ramp rows and for shaky hands — so v1 must be per-row
   opt-in with per-row fallback to pressing, never a mode switch, never the
   default. BLE stays out of scope: 0.85 s/cycle gives <0.5 clean
   reads/patch at any speed that finishes a row.

## 5. Ranked risks

R1 (blocker until measured): motion reading ≠ settled reading. EXP-019 C/D/F.
R2: effective integration window unknown — sets the safe speed. EXP-019 E.
R3: low-contrast rows unalignable → rejected swipes erode trust. Mitigate:
    confidence gate says WHY, per-row fallback, and honest docs.
R4: human speed/lateral control without a guide. Mitigate: ruler + beep
    metronome + measure_pace-style live feedback; EXP-019 F rehearses it.
R5: unsolicited frames (button press mid-stream) can desync the solicited
    trigger/fetch loop. Mitigate: stream reader must resync on frame
    signatures (BB 01 09 vs 10/11/12) and treat a mid-stream button header
    as "operator ended the swipe", or at minimum discard it safely.
R6: 100+ host triggers/strip × cap-on = calibration rewrite. CLOSED by
    press-to-start gate-flag check (§4.3); ALSO require: stream never starts
    except within ~1 s of an ungated button header.
R7: beeping at 3.18 Hz may be unacceptable to the operator (or a feature).
    Ask the owner during EXP-019; there is no known beep-off command
    (PROTOCOL.md §5 negative result: no parameter command exists in ten
    vendor sessions).
R8: hex charts, spacer-bearing engine layouts — v1 excludes hex; spacers are
    actually helpful (extra template states) but only with engine-known
    geometry; printtarg-made charts have printtarg-known patch pitch. v1:
    engine rectangular rows only.

## 6. EXP-019 — motion feasibility, for the owner, THIS session

Probe: `~/develop/chromiq-cr30-research/tools/probe_strip_feasibility.py`
(USB, cap OFF throughout, no calibration commands ever sent; phases are
delimited by keyboard Return or the instrument's own button — no timers on
human actions; every phase has its control; raw JSON written after every
phase so a killed run loses nothing).

Human steps are printed by the probe itself and repeated in §7 below.

Decision rules, fixed BEFORE the data exists:
- D (slide on plain paper vs settled presses on the same paper): median ΔE of
  mid-slide samples to the settled median ≤ 0.5 → motion reading is valid;
  0.5–1.5 → marginal, strips only with widened tolerances and owner's
  sign-off; > 1.5 → DON'T BUILD (report says so and stops).
- E (edge crossing): intermediate samples per crossing ≤ 1 at the rehearsal
  speed → window ≈ aperture (integration is short); ≥ 2 → size the safe
  speed from the measured window, recompute §1's table with it.
- F (real row rehearsal, optional but decisive): per-patch ΔE aligned-vs-
  pressed, median ≤ 1.0 and max ≤ 3.0 with zero misassignments → green-light
  v1. Analysis is offline (`--analyse` mode), owner only swipes.
- Controls: phase A (in-air signature) is the negative control and the end-
  detector's training sample; phase C (static stream on the same spot as the
  settled presses) is the positive control that streaming itself is unbiased
  AND that the probe can tell still from moving (C vs D must differ).

## 7. Owner instructions (also printed by the probe)

1. Plug the CR30 in over USB. Take the cap OFF and leave it off.
2. In a terminal: `cd ~/develop/chromiq-cr30-research && python3
   tools/probe_strip_feasibility.py`
3. Have ready: a printed ChromIQ chart on its paper, a ruler or straight
   edge, and a clear desk.
4. The probe asks for each step in plain words and waits for you — either
   press Return on the keyboard, or press the instrument's own button, as
   the step says. Nothing is timed; take as long as you like.
5. When a step says "slide", hold the instrument like a pen, lean it against
   the ruler's edge, and move it steadily — about one centimetre per second,
   slower than feels natural. If it beeps while you slide, aim for two or
   three beeps per patch.
6. At the end it prints PASS / MARGINAL / FAIL for each question and saves
   everything under `captures/raw/EXP-019-*.json`.

## 8. What the v1 design is (if EXP-019 passes)

Per-row, USB only, engine rectangular charts, opt-in:
1. UI offers "Swipe this row" beside the existing per-patch flow.
2. Operator places instrument on the paper margin BEFORE the row's first
   patch, presses the instrument button once. ChromIQ verifies the header's
   gate flag is 0 and takes the stored reading as the paper-white reference.
3. ChromIQ stream-triggers at 3.18/s; live pace feedback via measure_pace;
   samples pass check_usable(previous=last sample).
4. End on sustained white/air (or cap/timeout → reject).
5. Align: template [paper]+patches+[paper] with transition states; identify
   over all unread rows × both directions; confidence gate (§2). Reject →
   one message with the reason, nothing written, swipe again or press.
6. Accept → feed each patch: goto(loc) → await spot_ready(loc) → value →
   verify patch_read(loc). Helper autosaves per patch; its own dE challenge
   and Suppress-warnings behaviour apply unchanged.
7. Consistency tolerance spinbox un-greys for CR30 with its new meaning
   (in-patch sample spread, ChromIQ-computed) — supersedes 17_verify4's
   "meaningless by nature" for strip mode only; spot mode stays grey.

Design-spec obligations: this touches measurement flow, so before any build
the relevant `docs/design/` specs (`unified_measurement_management.md`,
`measurement_exit_strategy.md`, `measurement_window_sounds.md`) must be
consulted and any new user-facing text goes through §M-PROPOSED. Nothing in
this report has been confirmed by a human; per the spec rules it is all
⏳ awaiting confirmation.

## 9. Probe self-check (mutation-proven, run 2026-08-29)

The `--analyse` aligner in `probe_strip_feasibility.py` was exercised on a
synthetic swipe (6 well-separated patches, 3 jittered samples each plus one
deliberate boundary MIXTURE sample per patch, white bookends): every patch
recovered its 3 clean samples (mixtures fell into the transition states),
per-patch dE to truth ≤ 0.23; and the REVERSED template cost 288.7 against
the correct template's 47.6 (6.1×) — so a broken aligner cannot report a
green phase F, and a reversed swipe is provably distinguishable before any
value is written. (This proves the analysis tool, not the instrument — the
instrument questions are phases A–F themselves.)
