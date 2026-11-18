# X-Rite i1Pro 2 dual scan: M0, M1 and M2 from a lamp pass and a UV pass

> **These specifications are binding.** Before changing code in this area, read this document;
> a fault that contradicts it is reported and approved before it is fixed (CLAUDE.md, "The
> design specifications are binding"). Only behaviour a person has confirmed is written as
> confirmed; everything below is **awaiting confirmation**.

Feature owner's order (2026-11-18): the i1Pro 2 can give M0, M1 and M2 from a "dual scan"
(every strip or patch read once with its tungsten lamp and once with its UV LED, after a
calibration that also reads the white tile with the UV LED). ChromIQ offers this for the i1Pro 2
by hand and on the i1iO 2 table, and keeps all three conditions through the EXISTING Beta
"X-Rite i1Pro 3: keep M0, M1 and M2 from every scan" (same files, same choice afterwards).

Step 1 (2026-11-18): the calculation, the stored form, the helper's arithmetic and files,
proved on recorded data. Step 2 (2026-11-18): the independent review's findings (REVIEW_446,
branch 1) and the device side of the helper (section 7). No user interface yet.

## Confirmed behaviour (two decisions only)

**Confirmed by:** Sebastian, 2026-11-18

* **The standard factor 1.156 is accepted as PROVISIONAL.** It is the middle of the two
  instruments' own factors (1.100 and 1.212, fitted on ChromIQ's own lamp readings) in the
  relative sense: their geometric mean, sqrt(1.100 x 1.212) = 1.1547, makes the worst RELATIVE
  error over the two instruments smallest (5.0 % either side). The dE00 a factor error costs is
  proportional to the relative error times the paper's glow, so this middle does not depend on
  the papers measured (a minimax in dE00 on these two papers, about 1.12, would bake the papers
  into the constant; independent review, 2026-11-18). 1.156 and 1.1547 differ by 0.003 dE00. To
  be fitted again when a third instrument, or instrument 2 on its own tile, is measured.
* **Passes from more than one calibration are allowed and recorded**: "Continue Measurement"
  reads the missing passes after a new dual calibration, and the measurement records that its
  passes come from more than one calibration.

## ⏳ Awaiting confirmation

**Confirmed by:** *nobody yet.*

### 1. The calculation (`workflow/dual_scan/model.py`, C twin `native/chartread_helper/chromiq_dualscan.c`)

Per patch and band, with L the lamp reading (= M0), U the UV-LED reading processed with the same
lamp white, W / T the white tile read with the lamp / the UV LED at calibration, EMIS the
calibration's reflectance-to-emission factor, kA / kD the instrument's factory tables (EEPROM
keys 0x2f77 / 0x2f76, 380-550 nm, zero outside 410-550 nm) and s the glow scale:

    Ue = U EMIS;  Te = (T / W) EMIS
    J  = s kA (Ue - Te L) / (1 - s kA Te)
    M2 = L - J;   M1 = L + (kD / kA - 1) J;   outside 410-550 nm M0 = M1 = M2; nothing clipped.

The form is ArgyllCMS's i1Pro 3 computation (`i1pro3_comp_refl_value`) with the i1Pro 2's own
tables. Refused, each with a reason id (`workflow/dual_scan/reasons.py`): no dual-scan
calibration, a calibration at another exposure or in another reading mode, missing or malformed
tables, a UV pass that does not match the lamp pass patch for patch, non-finite values, a scale
outside 0.5-2.0, and a calibration whose UV LED did not light (`uv_tile_dark`: Te averaged over
380-410 nm below 100 emission units; the two recorded instruments gave 207 and 292-295, an LED
that did not fire gives about 0). A single-scan calibration has no UV reading of the tile and
reads the white at the single scan's exposure, so it gives no M1 / M2 at all; its M0 is as good
as ever (`no_dual_calibration`). i1Profiler's own b1 file, 15 % too bright, was the EXPOSURE
mismatch (white at 154 clocks, strip at 139), which `calibration_mismatch` refuses.

### 2. The stored form (`workflow/dual_scan/storage.py`)

* The main `<stem>.ti3` is the lamp pass (M0), as an ordinary i1Pro 2 reading; M1 and M2 go to
  the i1Pro 3 Beta's `conditions/<hash>-M1.ti3` / `-M2.ti3`, written by the engine in the same
  autosave, in exactly that Beta's form. Everything downstream works on them unchanged.
* Every file of the measurement records `CHROMIQ_DUAL_SCAN "i1pro2"`, `CHROMIQ_DUAL_SCALE`,
  `CHROMIQ_DUAL_SCALE_SOURCE` ("standard" or "refined") and `CHROMIQ_DUAL_WHITE` ("instrument" or
  "table"). No serial number and no instrument key in any measurement file.
* `CHROMIQ_DUAL_CHOSEN "M0" | "M1" | "M2"`: the condition chosen in the Measure tab's filter
  row (never sent to the instrument as -F). The main file stays PHYSICALLY M0 (the lamp passes:
  the only condition true for every strip at every autosave and resume); the choice is recorded
  in every file's header and in the pass record, and Build Profile's "Build from" is pre-set to
  it once every strip has both passes; until then M0, with the reason
  (`storage.build_from_preset`, `i1pro3_conditions.no_file_reason`'s dual-scan case).
* A dual-scan measurement is never continued by single scans, nor the other way round, and only
  with the factor, its source and the white reference it was started with (refused before START:
  `mixed_scan_kind`, `mixed_factor`; `storage.continuation_choice` gives the measurement's own
  factor to continue with). The engine refuses it again: a dual measurement continued as a single
  scan or with another factor stops before anything is read (error event `mixed_scan_kind` /
  `mixed_factor`, nothing written); a single-scan measurement continued as a dual scan goes on as
  M0 only (`why: "mixed"`). One file never holds values made with two factors. Averaging reads of
  different factors (or dual and single reads) keeps no M1 / M2 for the average.
* A dual reading only after a dual calibration at the same exposure; a change of reading mode
  in either direction needs a new calibration.

### 2a. The two passes of a hand dual scan are two units (the owner, 2026-11-18)

* The lamp pass and the UV pass of a strip are two separately started readings, each with its
  own verdict and data; a failed pass is read again ALONE, the other one is kept; a good pass is
  never repeated silently. A dark reading precedes each pass, as in the recordings.
* Lamp pass: valid by today's single-scan rules (ArgyllCMS's patch recognition; the ruler check
  where it applies).
* UV pass: valid by (a) the ruler: it covered every patch of the lamp pass (`uv_pass_short`), with
  no gap or stall (`uv_pass_stalled`), with at least 3 readings per patch (`uv_pass_too_fast`;
  the recordings had 4-5, slow 9-10); either direction, the ruler says which; and (b) it belongs to
  the strip (`uv_pass_wrong_strip`): at 380-400 nm nothing glows, so the UV reading must follow
  (T/W) x the lamp pass across the strip's patches (correlation >= 0.95 and median ratio error
  <= 0.10). DARK PATCHES (review, M2): the ratio's noise grows as the lamp level falls (median
  0.025 at lamp reflectance 0.1-0.3 at 380-400 nm, 0.107 below 0.02), so a patch takes part only
  when its predicted LED signal reaches that of reflectance 0.05 (or its observed one twice
  that, so a dark lamp pass with a bright strip's UV pass is still judged); with fewer than 2
  such patches the pairing is SKIPPED for the strip: the pass is accepted with the note
  `pairing_not_checked` (the ruler checks still apply). A UV pass that brings back almost no LED
  light (median observed / predicted below 0.3) is refused as `uv_pass_no_uv_light`, whose
  sentence names both causes (LED not lit, or a much darker strip). Measured on the two
  instruments' recordings with these rules (work folder, private): right pairings 14 of 14
  accepted (each strip judged on 18 of its 23 patches), wrong ones 110 of 110 refused; the
  reviewer's re-arrangements (UV pass reversed, shifted by one patch, half of it from another
  row) 12 of 12 refused; the darkest real patches as strips (lamp 0.016-0.047) accepted
  unchecked, as are dark strips paired with each other (20 of 20: nothing to judge); a dark lamp
  pass with a bright UV pass refused, a bright lamp pass with a dark UV pass refused (no LED
  light); a black patch in a strip no longer gives "values that are not numbers". On a paper
  without brightener a mix-up cannot change M1 / M2 (J = 0), so the check may be waived there.
* The ruler cut's alignment measure (within-cell against between-cell variance of the UV signal
  at 400-500 nm) is a gate: above 0.01 the UV pass is refused as `uv_pass_misaligned` (the
  instrument lifted between the passes, the ruler's count lost). Measured: 0.00001-0.00004 in
  place, 0.09-0.35 half a pitch off. Not judged when the strip's patches hardly differ (note
  `alignment_not_checked`).
* A lamp pass read again keeps the strip's UV pass only when the UV pass is proved to belong to
  it; otherwise the UV pass is due again (`lamp_pass_changed`).
* A dual scan by hand needs the ruler: without usable ruler positions the UV pass cannot be
  assigned to patches, the dual scan is refused (`dual_needs_ruler`) and M0 can still be
  measured. The i1Pro 2's existing ruler reader (the "Ruler Check (beta)" code in the helper and
  `cq_ruler.h`) is to be reused, not a second one.
* Per strip, the state of each pass, the UV pass's per-patch data and the calibration each came
  from are kept in the run (`dual_scan/<stem>.passes.json`, `workflow/dual_scan/record.py`), never
  in a shared file, no serial. Privacy (review, S5): it keeps only what recomputing needs: per
  calibration Te = (T/W) x EMIS at 380-550 nm (18 numbers) and its clocks; per UV pass the UV
  readings already in those emission units at 380-550 nm; per lamp pass its readings (M0). The
  white, the tile under the UV LED and EMIS are never written. A measurement stopped early keeps an honest M0 of what was read;
  M1 / M2 exist only for strips with both passes and are offered for the measurement only when
  every strip has both; "Continue Measurement" asks only for the missing passes after a new dual
  calibration and records that the passes come from more than one calibration.
* A spot dual reading (lamp + UV on one patch in one press) is one unit: if either reading fails
  the patch is read again. On the table: patch by patch as spot; strips = the whole chart with the
  lamp, then with the UV light, a failed row of the second pass repeated alone, by position.

### 3. The scale s (`workflow/dual_scan/scale.py`)

* Built in: a standard factor, 1.156, PROVISIONAL (see "Confirmed behaviour": why it is the
  middle of 1.100 and 1.212, the geometric mean 1.1547, independent of the papers). M1 / M2 work
  for every i1Pro 2 without vendor software (owner's ruling 2026-11-18).
* Optional: "refine the factor for my instrument" from one i1Profiler measurement of the same
  strip with the same instrument, plus ChromIQ's dual scan of it; checked (same strip, same
  instrument by its factory M1 ratio, enough brightener, a clean fit, the file's conditions not
  swapped: `refine_conditions_swapped`); stored per instrument under a key made with a secret that
  is random per installation (an HMAC of model and serial; the serial is never stored, and the
  key cannot be traced back to it without that installation's secret). The "same instrument"
  check (a(lambda) within 0.02 of the instrument's own kD/kA - 1) is one number from two
  instruments (they differ by up to 0.32; 1 % accepted, 3 % refused): the UI shows the
  difference with the evidence.
* Each measurement records which factor it used.

### 4. What is established, on two instruments (private recordings, conclusions only)

* The formula reproduces X-Rite i1Profiler's M1 and M2: given i1Profiler's own M0, to
  0.017-0.047 dE00 mean (hand-held scans, instrument 1) and 0.002-0.004 (dual spot on an i1iO 2
  table, instrument 2). `M1 - M0 = (kD/kA - 1)(M0 - M2)` holds in every i1Profiler file of both
  instruments to 1e-6.
* With ChromIQ's own processing of the lamp reading and each instrument's own factor (ChromIQ's
  Python module and, through the replay instrument, the helper's own C path and files, on the
  recorded readings): instrument 1 M2 0.053-0.075 / M1 0.050-0.063 mean dE00 (sessions B2 and C,
  factor fitted on B3 only), instrument 2 M2 0.063 / M1 0.072. The remaining error is ChromIQ's M0
  (0.05-0.07), as in the analyses.
* With the standard factor: M2 0.21-0.23 mean / 0.41-0.47 max (instrument 1), 0.083 / 0.215
  (instrument 2); M1 0.08-0.09 / 0.35-0.41 and 0.063 / 0.204. For scale: M0 used as M2 is
  0.95-3.6 mean dE00 off.
* The factor differs between the two instruments by 10 %; nothing in their memories or
  calibration readings was found to predict it (instrument and tile are confounded: one used
  its own tile, the other the table's).

### 5. What is NOT established

* **ChromIQ's own UV reading has never run on a real instrument.** Step 2 built the
  instrument commands from the recordings (section 7); they were tested only on a fake USB layer
  and with recorded readings. Every instrument step (the dual calibration, the UV pass, the volts query, the
  ruler across both passes, the dual spot reading on the table) is to be built from the
  recordings and is a first try until a real i1Pro 2 has shown it.
* s on a third instrument; s on instrument 2 with its own tile; the creep of s within a
  session (0.6 % over four rows on instrument 1); a paper without brightener (expected
  M0 = M1 = M2, untested on hardware).

### 6. Honest limits for the release notes (draft)

* M1 and M2 from an i1Pro 2 are calculated with a standard factor found on two instruments (the
  second on the i1iO 2 table's tile); on strongly brightened papers M2 can differ from
  i1Profiler's by about 0.1 to 0.25 dE00 on average and up to about 0.5, M1 by less. Papers
  without optical brightener should not be affected (expected M0 = M1 = M2; not yet measured on
  such a paper).
* With i1Profiler, the factor can be refined for one instrument, which brought both test
  instruments to about 0.05-0.08 dE00 mean.
* Measuring with dual scan is a first try until a real instrument has shown it.

### 7. The instrument part (step 2, 2026-11-18): built from the recordings, never run on an instrument

* **Where.** Driver side: `native/instlib/cq_i1pro2_dual.h` (ChromIQ's own file, included at the end
  of `i1pro_imp.c`; API and wire summary in `cq_dual.h`) and seven one-line hooks in `i1pro_imp.c` /
  `.h` (`scripts/vendor_instlib.py` `I1PRO_IMP_H_DUAL` / `I1PRO_IMP_C_DUAL`, PROVENANCE.md), each a
  no-op unless the helper switched the dual scan on. Helper side: `chromiq_dualdev.c`. Capability
  word `i1pro2_dual_scan`, helper build 2026-11-18c.
* **Offered** only for a real i1Pro 2 whose EEPROM reports the UV LED and holds the two tables
  (0x2f77 / 0x2f76, 18 values, read-only from the image read at open); otherwise the conditions
  event says `dual_no_uv_tables` (M0 as always). Refused in high resolution (`dual_high_resolution`:
  the tables exist only at 10 nm).
* **(a) Dual calibration.** After every successful calibration of a dual session (a white
  calibration is always asked for first: a restored one has no UV reading), still on the tile: 10
  dark + 5 UV-LED readings at the white calibration's own integration (the reading's), then the UV
  volts. Checked by the arithmetic's rules (tables, the UV LED lit: `uv_tile_dark`). The calibration
  and the reading are made in the same mode and at the same integration, per light source; a
  reading at another one is refused (`calibration_mismatch`, `calibration_mode_changed`).
* **(b) Dual spot.** The lamp reading as always, then dark + UV-LED readings of the same patch at
  the same integration, then the volts: one unit (either half failing = the patch again).
  i1Profiler reads the UV half on the table at 1443 clocks against 517 for the lamp; ChromIQ uses
  the lamp's integration for both (the recorded UV-tile level per unit of integration is the same
  at 139-1443 clocks, so the formula does not depend on it; the UV signal is weaker).
* **(c) Dual strip by hand.** The lamp pass with "ruler start" (0x0105), then the helper asks for
  the UV pass itself (event `dual_pass`) and reads it with "ruler end" (0x0209): one ruler stream,
  as recorded. The UV pass is not put through the patch recogniser; every reading is kept, cut into
  the lamp pass's patches by the ruler (the lamp pass's readings are the stream's first n1 x clocks
  samples, the UV pass's its last n2 x clocks - 5) with the travel and alignment gates; each pass
  has its own verdict (`dual_pass_result`). A failed pass makes the strip a misread and BOTH passes
  are read again, because on the instrument a UV pass can only be lined up with the lamp pass of
  the same ruler stream (no other form was recorded): this differs from section 2a's "a failed pass
  is read again alone" and is **for the owner to decide**. After a lamp pass that triggered, the UV
  pass is always asked for (it closes the ruler stream).
* **(d) The UV LED.** It lights only during a trigger with the UV flag, for that trigger's
  readings; no command switches it on persistently. A UV scan runs while the button is held and
  the instrument ends it on release, as every scan. ArgyllCMS's own UV switch (`uv_en`) is set
  only for an armed UV reading and cleared on every way out.
* **(e) Not sent:** i1Profiler's indicator-light programs (18 / 2,306 bytes at calibration, 702 /
  2,990 bytes around the UV pass) and its usage-log EEPROM writes. With the lights Beta on, its own
  recorded OFF_SLOW goes before every trigger exactly as for a single scan.
* **(f) Conversions.** M1 and M2 are computed on the lamp reading's spectra before ArgyllCMS's
  output conversion and then go through the same `i1pro_conv2XYZ` as M0 (XRGA when asked for, the
  observer, the clamp).
* **What it took to prove, without an instrument:** a trace of the real driver on a fake USB layer
  (`tests/test_i1pro2_dual_scan_device.py`: the requests, flags, clocks and counts against the
  recorded shape, `tests/data/i1pro2_dual_wire_shape.json`; a single scan's requests unchanged); and
  privately, instrument 1's recorded sessions through the same functions (the dual calibration, the
  UV pass's readings, the ruler record, the cut, the formula): M2 0.055-0.079 mean dE00 with its own
  factor and 0.209-0.230 with the standard one, as in step 1. Instrument 2's spot path was not
  replayed. Everything here is a first try until a real i1Pro 2 has shown it.
