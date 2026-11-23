# X-Rite i1Pro 2 dual scan: M0, M1 and M2 from a lamp pass and a UV pass

> **These specifications are binding.** Before changing code in this area, read this document;
> a fault that contradicts it is reported and approved before it is fixed (CLAUDE.md, "The
> design specifications are binding"). Only behaviour a person has confirmed is written as
> confirmed; everything below is **awaiting confirmation**.

Feature owner's order (2026-11-18): the i1Pro 2 can give M0, M1 and M2 from a "dual scan"
(every strip or patch read once with its tungsten lamp and once with its UV LED, after a
calibration that also reads the white tile with the UV LED). ChromIQ offers this for the i1Pro 2
by hand and on the i1iO 2 table, and keeps all three conditions through the EXISTING Beta
"X-Rite i1Pro 3 and i1Pro 2: keep M0, M1 and M2 from every scan" (same files, same choice afterwards).

Step 1 (2026-11-18): the calculation, the stored form, the helper's arithmetic and files,
proved on recorded data. Step 2 (2026-11-18): the independent review's findings (REVIEW_446,
branch 1) and the device side of the helper (section 7). No user interface yet.

## Confirmed behaviour (three decisions only)

**Confirmed by:** Sebastian, 2026-11-18

* **The standard factor 1.156 is accepted as PROVISIONAL, with its cost:** on strongly
  brightened papers M2 can differ from i1Profiler's by about 0.1 to 0.25 dE00 on average and up
  to about 0.5 (M1 by less). It is the middle of the two
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

### The Beta option's name names the i1Pro 2 too

**Confirmed by:** Sebastian, 2026-11-18

* The existing Beta option in Preferences > Beta that the dual-scan switch sits under is named
  "X-Rite i1Pro 3 and i1Pro 2: keep M0, M1 and M2 from every scan (beta)" (it was "X-Rite i1Pro 3:
  keep M0, M1 and M2 from every scan"), because the i1Pro 2's dual scan is switched on under it.
  The settings key stays `i1pro3_conditions_beta` (no migration); the label, its help, every text
  that quotes it and all 13 languages say the new name.

## ⏳ Awaiting confirmation

**Confirmed by:** *nobody yet.*

### 0. Two rules for the first Beta, accepted on the coordinator's recommendation

Sebastian accepted these two on the coordinator's recommendation, without a view of his own
(2026-11-18). They are **provisional for the first Beta** and are not confirmed behaviour.

**(a) On a hand strip, a failed pass means both passes of that strip are read again.**

**Confirmed by:** *nobody yet.* Provisional for the first Beta.

On the instrument a UV pass can only be lined up with the lamp pass of the same ruler stream
(the lamp pass's trigger "ruler start" 0x0105, the UV pass's "ruler end" 0x0209: the only
recorded form). Reading the UV pass alone again would need a form that was never recorded. So
the helper makes the strip a misread whenever either pass fails, and every pass refusal's
sentence (`workflow/dual_scan/reasons.py`) says that both passes are read again. Cost: the
person repeats a good lamp pass. This differs from section 2a's "a failed pass is read again
alone", which describes the per-strip record (`record.py`).

**(b) The UV half of a dual spot reading is read at the lamp half's integration (517 clocks on
the table), not at i1Profiler's 1443.**

**Confirmed by:** *nobody yet.* Provisional for the first Beta.

The calibration reads the white tile with the UV LED at the same integration, so calibration and
reading match per light source. The recorded UV-tile level per unit of integration is the same at
139-1443 clocks; the cost is noise: the safety review measured the signal-to-noise of ChromIQ's
3 x 517 average at 0.57-0.96 of i1Profiler's 1 x 1443 (and 1.9-2.9 times the hand scan's
5 x 139, which already gives about 0.05 dE00). 517 lies inside the recorded 139-1443 clocks.

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
  own verdict and data; in the per-strip record a failed pass is read again ALONE, the other one
  is kept; a good pass is never repeated silently. (On the instrument path of the first Beta a
  failed pass on a hand strip means BOTH passes again: section 0 (a).) A dark reading precedes each pass, as in the recordings.
* Lamp pass: valid by today's single-scan rules (ArgyllCMS's patch recognition; the ruler check
  where it applies).
* UV pass: valid by (a) the ruler: it covered every patch of the lamp pass (`uv_pass_short`), with
  no gap or stall (`uv_pass_stalled`), with at least 3 readings per patch (`uv_pass_too_fast`;
  counted, after 4.3.54, over the lamp cell's whole span less a quarter ruler step at each end
  after the UV pass has been lined up with the lamp pass, until 4.3.54 over its central 60 %:
  section 17); either direction, the ruler says which; and (b) it belongs to
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
  `alignment_not_checked`). This measure is taken over the central 60 % of each cell. After
  4.3.54 the UV pass is first lined up with the lamp pass by their 380-400 nm readings: an offset
  above 3 steps is refused as `uv_pass_shifted`; then the same measure over the averaging window
  must also stay at or below 0.001 (section 17). A strip that cannot be lined up (no single
  offset fits clearly, or no lamp readings to line up with) is NOT refused: it is cut uncorrected
  with 4.3.54's central 60 %, with 4.3.54's limits (section 17). The per-patch claim is section
  17's and holds for lined-up strips.
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
  i1Profiler's by about 0.1 to 0.25 dE00 on average and up to about 0.5, M1 by less (this cost
  sentence is confirmed with the factor, see "Confirmed behaviour"). Papers
  without optical brightener should not be affected (expected M0 = M1 = M2; not yet measured on
  such a paper).
* With i1Profiler, the factor can be refined for one instrument, which brought both test
  instruments to about 0.05-0.08 dE00 mean.
* Measuring with dual scan is a first try until a real instrument has shown it.

### 7. The instrument part (step 2, 2026-11-18): built from the recordings, never run on an instrument

* **Where.** Driver side: `native/instlib/cq_i1pro2_dual.h` (ChromIQ's own file, included at the end
  of `i1pro_imp.c`; API and wire summary in `cq_dual.h`) and eight short hooks in `i1pro_imp.c` /
  `.h` (`scripts/vendor_instlib.py` `I1PRO_IMP_H_DUAL` / `I1PRO_IMP_C_DUAL`, PROVENANCE.md), each a
  no-op unless the helper switched the dual scan on. Helper side: `chromiq_dualdev.c`. Capability
  word `i1pro2_dual_scan`, helper build 2026-11-18d (the safety review's fixes; 18c before them).
* **Offered** only for a real i1Pro 2 whose EEPROM reports the UV LED and holds the two tables
  (0x2f77 / 0x2f76, 18 values, read-only from the image read at open); otherwise the conditions
  event says `dual_no_uv_tables` (M0 as always). Refused in high resolution (`dual_high_resolution`:
  the tables exist only at 10 nm).
* **(a) Dual calibration.** After every successful calibration of a dual session (a white
  calibration is always asked for first: a restored one has no UV reading; since 4.3.58 together
  with everything a normal start asks for, the LED wavelength calibration and the dark first,
  section 19), still on the tile: 10
  dark + 5 UV-LED readings at the white calibration's own integration (the reading's), then the UV
  volts. Checked by the arithmetic's rules (tables, the UV LED lit: `uv_tile_dark`). The calibration
  and the reading are made in the same mode and at the same integration, per light source; a
  reading at another one is refused (`calibration_mismatch`, `calibration_mode_changed`).
* **(b) Dual spot.** The lamp reading as always, then dark + UV-LED readings of the same patch at
  the same integration, then the volts: one unit (either half failing = the patch again,
  `uv_spot_failed`). i1Profiler reads the UV half on the table at 1443 clocks against 517 for the
  lamp; ChromIQ uses the lamp's integration for both (provisional for the first Beta: section 0 (b)).
* **(c) Dual strip by hand.** The lamp pass with "ruler start" (0x0105), then the helper asks for
  the UV pass itself (event `dual_pass`) and reads it with "ruler end" (0x0209): one ruler stream,
  as recorded. The UV pass is not put through the patch recogniser; every reading is kept, cut into
  the lamp pass's patches by the ruler (the lamp pass's readings are the stream's first n1 x clocks
  samples, the UV pass's its last n2 x clocks - 5) with the travel and alignment gates, and then
  proved to belong to the strip by the same pairing check as section 2a (`cq_dual_pairing`, the C
  twin of `pairing.check_pairing`: same rule, same thresholds, same "not judged" dark strips; a
  pass over the neighbouring row passes every ruler gate, so only this check refuses it,
  `uv_pass_wrong_strip`; safety review 2026-11-18, M1). A UV pass longer than 4000 readings
  (about 20 s) is refused whole (`uv_pass_too_long`), never half-used. Each pass has its own
  verdict (`dual_pass_result`, which also says whether the pairing was judged). A failed pass
  makes the strip a misread and BOTH passes are read again (provisional for the first Beta:
  section 0 (a)).
* **Only when it can be a recorded form** (safety review, M2). The UV pass is asked for only when
  the lamp pass counted readings in a ruler stream that still runs and the ruler is in use
  (`i1pro2_cq_dual_uv_pass_ready`): then its trigger carries "ruler end" and closes the stream.
  It is asked for also after a lamp pass ArgyllCMS did not recognise (both passes again).
  (Section 18, awaiting confirmation, changes this: after such a lamp pass the person presses once
  in place instead of reading a second pass; this sentence is marked replaced once 18 is confirmed.)
  Otherwise (the lamp pass's trigger or read failed, the ruler was given up, or a UV pass was left
  with Esc so that the next lamp pass could not start a stream) M1 / M2 end for the session
  (`dual_needs_ruler`) and M0 goes on; a stream left running is drained until the close, as the
  ruler check does. The driver also refuses, before anything is sent, every UV-LED trigger that
  is not 0x0200 or 0x0209 with 41 lamp clocks, so 0x0201 (a UV scan without "ruler end") cannot
  go out.
* **(d) The UV LED.** It lights only during a trigger with the UV flag, for that trigger's
  readings; no command switches it on persistently. Every UV-LED trigger carries a fixed 41 lamp
  clocks, as i1Profiler sent on all 76 recorded UV-LED triggers of both instruments (tile, table
  spot, hand pass); ArgyllCMS's own lamp time would give 102 in scan mode and 51 in spot mode
  (safety review, M3). A UV scan runs while the button is held and
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
  replayed. After the safety review's fixes (helper 18d) the same numbers, unchanged; the C pairing
  check accepted all 13 recorded strips on the device path and agrees with the Python one on all
  171 recorded cases (14 right, 110 wrong, 12 re-arrangements, dark strips and crossings, whites,
  blacks). The 41 lamp clocks cannot change these numbers: the replayed readings were recorded
  with 41. Everything here is a first try until a real i1Pro 2 has shown it.

### 8. The hand measurement in the Measure tab (UI step, 2026-11-18)

**Confirmed by:** *nobody yet.* Built and driven on screen against a simulated helper (the real
helper's replay instrument plus the device path's events, `tests/helpers/dual_sim_helper.py`);
never on a real instrument. Code: `workflow/dual_scan/session.py` (the rules),
`ui/tabs/tab_measure.py` (the `_dual_*` methods), `ui/tabs/tab_profile.py`
(`_dual_preset_once`), `ui/dialogs/settings_dialog.py`; texts §M-PROPOSED
`M-DUAL-*` of `unified_measurement_management.md`; tests
`tests/test_i1pro2_dual_scan_ui.py`.

* **Where it is switched on.** Preferences > Beta, "X-Rite i1Pro 2: also M1 and M2, by a dual
  scan (beta, first try)", indented under "X-Rite i1Pro 3 and i1Pro 2: keep M0, M1 and M2 from every scan" and
  greyed (keeping its value) while that is off, because the dual scan ends in that Beta's files.
  Turning it on asks for the own-risk confirmation, as the other instrument Betas do. Its (i)
  holds the cost sentence of section 6. Off (either switch): no `--dual-*` argument, no note, no
  window; the Measure tab is as before.
* **Which instrument.** Only ChromIQ's engine, a helper naming both capability words, a chart that
  is not a calibration's, and an instrument known to be an i1Pro 2 or not known to be another
  model (an i1Pro 3 keeps its own `-F`). How the model is known before START: section 9.
* **The filter row chooses the main condition.** With the dual scan on, "Spectral filter type
  (-F)" (off = M0, or M0 / M1 / M2) is not sent as `-F`: it goes out as `--dual-chosen` and is
  recorded; the main file stays M0. The polariser and D65 are refused before START
  (M-DUAL-FILTER-NOT-DUAL). A dual measurement continued as a single scan, or the other way round,
  is refused before START (M-DUAL-START-REFUSED); one started with another factor continues with
  its own (`storage.continuation_choice`). An engine refusal of the same kind is never a fallback
  to stock chartread.
* **Before START.** A line in the Measure tab's own status line (under the log, where the tab
  says what happens next; never a box over the chart, Basti 2026-11-18), one line, the whole
  note on hover and once in the log: each strip read twice,
  the ruler needed (without it only M0), the condition chosen, a first try
  (M-DUAL-BEFORE-START). It follows the row and Preferences and goes while a session runs.
* **Calibration.** The calibration window of a dual session (startup and on request) adds "keep
  the instrument on its white tile ..." (M-DUAL-CAL-TILE); from Start Calibration that sentence
  stays under the chart (amber) and in the status line until the engine's `cal_done` (or a
  requested calibration's result), which come after the tile's UV reading (safety review S5).
  Calibration Complete then says the tile was read with the UV light too and the instrument can be
  lifted (M-DUAL-CAL-DONE), or why this calibration gives no M1 / M2 (M-DUAL-CAL-REFUSED).
* **Each strip, two passes.** In the same status line, as a variant of the strip prompt (a
  flashed line shows for its time and then gives it back): "Strip A, pass 1 of 2
  (lamp)" at every strip prompt, "Strip A, pass 2 of 2 (UV light)" when the engine's `dual_pass`
  asks for the second (M-DUAL-PASS-ONE / -TWO; after a first pass ArgyllCMS did not recognise,
  M-DUAL-PASS-TWO-UNREAD, with its own headline "Strip A: pass 1 did not read. Read pass 2 anyway"
  and the "Strip read failed" sound at that moment, 4.3.52). (Section 18, awaiting confirmation, replaces
  M-DUAL-PASS-TWO-UNREAD with M-DUAL-PASS-ONE-REFUSED: no second pass after a refused first one.) The strip stays highlighted as for any
  strip.
* **A refused pass.** The engine makes the strip a misread; "Strip Read Failed" opens as for any
  misread (its buttons, keys and sound unchanged) and shows "The second pass of strip B failed"
  with the reason's sentence, which says that both passes are read again (provisional, section 0
  (a)); Retry asks for pass 1 of 2 again. Patch by patch the same in "Patch Read Failed"
  (M-DUAL-SPOT-FAILED). A pass accepted with its pairing not judged gets a log line.
* **M1 and M2 ended for the session** (the ruler lost, the calibration, high resolution, no
  factory data): an amber line under the chart until the session ends and a log line
  (M-DUAL-ENDED); never a window; M0 goes on.
* **The pass record.** Written after every save of the engine, beside the conditions folder
  (`Run.dual_pass_record`), from the events: the choice, each dual calibration (its clocks; no
  spectra reach the app), per strip both passes good, a refused second pass with its reason, or
  M0 only with the reason M1 / M2 ended. The engine works M1 / M2 out itself and writes them into
  the i1Pro 3 Beta's files.
* **Build Profile.** "Build from" is set to the chosen condition as soon as every strip has both
  passes (`storage.build_from_preset`), kept in the target's settings, and only once (the pass
  record's `preset_done`), so a later choice of the person's stands. Until then it stays at M0 and
  a line under the measurement says why: strips not read yet ("... not every strip has been read.
  Continue Measurement, with the dual scan still switched on, reads the strips still missing (B, C)
  with both passes ..."), or M1 and M2 ended during the measurement ("... Continue Measurement
  cannot add M1 and M2 to it; for M1 and M2, measure the chart again as a new measurement"). See
  section 9.
* **The ending, the lock, Continue Measurement, sounds and lights** are the hand path's, unchanged.
* **Known difference from i1Profiler (the coordinator's decision, 2026-11-18):** a strip's LAMP
  pass carries ArgyllCMS's own lamp clocks (102 in scan mode), where i1Profiler sends 41; that is
  identical to every single scan ChromIQ makes today. Only the UV-LED triggers carry the recorded
  41 (section 7 (d)).
* **Not built in this step:** refining the factor from an i1Profiler file (the core has it; a
  window needs the instrument's serial, which the app does not get from the engine today; the
  standard factor makes the feature fully usable without it), distinct sounds per pass (a row in
  `measurement_window_sounds.md` first), and the i1iO 2 table.

### 9. Fix round after the independent UI review (2026-11-18)

**Confirmed by:** *nobody yet.* Built and tested against the simulated helper and on screen; never
on a real instrument. Tests: `tests/test_i1pro2_dual_scan_ui_fix.py`,
`tests/test_i1pro2_dual_scan_ui_review.py`. Texts §M-PROPOSED (M-DUAL-CONTINUE-M0,
M-DUAL-NOCAL-REFUSED, M-DUAL-PASS-ONE-NO-CAL, M-DUAL-PASS-TWO-NO-CAL, M-DUAL-MODEL-ASK,
M-DUAL-MODEL-CORRECTED, M-DUAL-MODEL-NOTED, M-DUAL-FILTER-OFF-PARENT; M-DUAL-ENDED changed).

* **Which instrument, before START (Sebastian asked for this on 2026-11-18; he has not seen the
  result).** Nothing is sent to an instrument to find out
  (`workflow/dual_scan/instrument_model.py`). Only with the dual scan on; with it off nothing of
  this runs, nothing is read and nothing is written.
  1. The USB connection (the system's own list, `core/argyll_instruments.usb_devices`): one
     ArgyllCMS instrument attached that is an i1Pro 3 (0765:6009, the i1Pro 3 Plus has the same id)
     or any other instrument: measured as without the Beta. 0971:2000 is "an i1Pro or an i1Pro 2":
     ArgyllCMS tells the two apart only by the number of USB pipes, which this list does not give,
     so USB alone never says "i1Pro 2". Nothing attached, several, or no list: USB cannot tell.
  2. What is remembered across app runs: the model the instrument itself reported at the last
     measurement with the dual scan on (the helper's `instrument` event, ArgyllCMS's "Instrument
     Type:" line), or the person's answer. A remembered i1Pro 2 stands when USB says "i1Pro
     family"; a remembered report of another family (an instrument changed since) does not.
  3. When neither tells: one window before START, "Which instrument do you measure with?"
     (M-DUAL-MODEL-ASK) with "i1Pro 2", "Another instrument", "Not sure" (the default: START as for
     an i1Pro 2 and let the instrument's report correct it, nothing remembered) and "Cancel"
     (nothing starts). The answer is remembered.
  4. Preferences > Beta, under the dual-scan switch: "Instrument for the dual scan:" with "Ask
     before the next measurement" (forgets), "i1Pro 2", "Another instrument (not an i1Pro 2)", and
     a line saying what is remembered and where it came from. Written only when changed there, so
     a reported model stays as the instrument reported it.
  5. The instrument's own report at the start always wins. It is remembered, and when it
     contradicts what START assumed, the engine is ended before the first reading and the same
     read is started again the right way, as one session (`MeasureManager.relaunch_before_reading`:
     the first engine's remaining output is not read, the tab sees no ending): an i1Pro 3 or any
     other instrument gets exactly the read it gets without the Beta (the row's `-F`, no `--dual-*`,
     so an i1Pro 2 refusing a filter still gets M-FILTER-REFUSED); an i1Pro 2 found after a start
     without the dual scan gets the dual read when the plan applies. One sentence says so in the
     log and under the chart until the first strip is read (M-DUAL-MODEL-CORRECTED). When it cannot start again (something was
     read), it goes on as started and says that (M-DUAL-MODEL-NOTED).
* **How a person tells the instruments apart: verified, with sources.** ArgyllCMS 3.5.0
  (`doc/instruments.html` of the release, read 2026-11-18; the vendored sources in
  `native/instlib`): the i1Pro 2 is "AKA Eye-One Pro Rev E"; "There have been four revisions of the
  Eye-One Pro, Rev. A, B, D and E (AKA Eye-One Pro2)"; the EFI ES-1000 is "a re-badged Eye-One
  Pro"; the retail i1Pro 2 has the part number EO2-XR-ULZW, and "a number of OEM Eye-One Pro2's
  (i.e. The EFI ES-2000) that appear from time to time with the part number EO2-XR-UF" are "fitted
  with an Ultra Violet filter", "missing the UV illumination LED" and "the Zebra stripe ruler
  sensor". **Corrected 2026-11-19 (table safety review, MUST-B1):** this ties the missing UV light
  and ruler to the part number EO2-XR-UF, not to every ES-2000 (a tester's ES-2000, issue 216,
  firmware 634, reported itself as "i1Pro2" and gave a clean ruler stream on 80 of 80 swipes). The
  texts now say: an OEM i1Pro 2 such as the EFI ES-2000 usually works like an i1Pro 2; a few OEM
  units were built without the UV light, and ChromIQ notices that by itself (at the start, from the
  factory data, or at the calibration, from the dark UV tile) and keeps M0 only; the 4.3.45 text
  "neither has the OEM i1Pro 2 sold as the EFI ES-2000 ... Choose Another instrument" is gone; the i1Pro 3 and i1Pro 3 Plus, and OEM i1Pro 3s such as the EFI ES-3000; the cheapest
  package was named i1Basic Pro 2. `insttypes.c` (USB ids, above; `inst_name`: "i1Pro", "i1Pro2",
  "i1Pro3"), `i1pro_imp.h` (firmware 629 = Rev E), `i1pro_imp.c` / `i1pro3_imp.c` ("Instrument
  Type:" line, " Plus" from the aperture). NOT verified, and the window says so: what is printed
  on the instrument's label, and the product names shown by the vendor's software.
* **Continue Measurement after M1 / M2 ended (review M-1).** The engine's resume takes M1 / M2 up
  again only when the condition files still belong to the readings (`cq_cond_resume`); after M1 /
  M2 ended they never do. So before START the status line says "Dual scan: this measurement
  continues as M0 only" (M-DUAL-CONTINUE-M0; `session.ended_before`), the dual arguments are still
  passed (the engine refuses a dual measurement continued without them), the engine's
  `why: "resume"` arrives as M-DUAL-ENDED with its own sentence, and no text promises M1 / M2 back
  ("For M1 and M2, measure the chart again as a new measurement"). A measurement stopped early
  with its files in step continues with both passes for the strips not read yet. Measured on
  screen: after such a Continue the engine writes the main file again WITHOUT its dual record; the
  measurement is still known as an ended dual scan by its pass record (`session.ended_before`),
  so a later START is not refused as "started as a single scan" (the engine then says "mixed",
  shown with the same sentence as "resume"), and Build Profile does not call it an i1Pro 3 matter.
* **A new measurement into the same file starts a fresh pass record (review M-2)**; only Continue
  Measurement (`-r`) takes the old one up again.
* **Texts (review M-3).** The calibration and session-level reason sentences say what happened and
  no action; M-DUAL-CAL-REFUSED adds "calibrate again before the next strip" (true: a good dual
  calibration before the next strip's UV pass keeps M1 / M2), M-DUAL-ENDED adds that M0 goes on,
  one pass per strip, and that M1 / M2 come back only with a new measurement. Every reason the
  engine can give has a sentence; an unknown one gets a plain sentence without its id
  (review S-4).
* **"Skip initial calibration (-N)" with the dual scan is refused before START**
  (M-DUAL-NOCAL-REFUSED, review S-5): on the hand path -N is the person's own choice, so it is not
  overridden by a calibration they switched off, and the dual scan cannot work without it (a kept
  calibration has no UV reading of the tile; M1 / M2 would end at the first strip).
* **After a dual calibration that cannot give M1 / M2** the pass prompts say so
  (M-DUAL-PASS-ONE-NO-CAL: calibrate again now; M-DUAL-PASS-TWO-NO-CAL: this pass only closes the
  strip). Not asking for that pass at all needs a helper change.
* **The pass line** in the status line is bold, in the text colour, one point above the app's body
  size, only while a dual line is up.
* **The simulated helper** ends M1 / M2 as the real one does: the strip that ends them is read
  without its UV half, so the real helper's record is lost and its condition files go out of step,
  and a later Continue Measurement gets the real helper's own `why: "resume"`.

### 10. The dual scan on the i1iO 2 table (2026-11-18, a first try)

**Confirmed by:** *nobody yet.* Built, tested against the simulated table and helper, and driven
on screen against them; never run on a real table. Why both modes are built: the owner's ruling
of 18 Nov 2026, "you have the commands so you will do patch by patch and strip mode so it can be
tried. as long as there is no chance for physical harm of the table this is ok so we can collect
data".

* **Where it applies.** The Measure tab's table START with both Beta switches of section 8 on and
  a helper that names `i1io_table_dual` (helper 2026-11-18e). The plan is the hand dual scan's
  (`workflow/dual_scan/session.plan_for`): the filter row's choice is recorded, never sent as
  `-F`; never mixed with single-scan readings or another factor; `-N` and `-H` are refused before
  anything is opened. Off: the table job is the released one, line for line.
* **Patch by patch.** No new table line. Each patch is read by the helper's dual spot reading
  (section 7 (b)): the lamp reading, then on the same spot dark + UV-LED readings at the lamp's
  integration (accepted provisionally by the safety review, NOTE (a)), then the volts. Every row is
  read by a reader of its own under `-N`, so the dual tile reading of the calibration is kept
  beside ArgyllCMS's own calibration file and taken up again ONLY for the same white (its date
  and a checksum of the white); a row whose reader finds none moves nothing and asks for a new
  calibration.
* **Rows.** Each row twice on the same line, exactly the recorded dual row: the lamp pass forward
  at 132 (d1 365), then straight back with the UV LED at 132 (a zero-length m0, c4, d1 210, p0,
  the scan move back, a3, c3; the same one path to the fire). Every row from its -X end. 132 and
  d1 210 are allowed only in the dual row's matching pass. The table's position log (y1-y5) is not
  asked for: both passes are cut by position (1.5 mm clean edge, 1.0 mm when 1.5 mm leaves a patch too few readings, as on ChromIQ's own 10 mm patches; lamp motion start 0.372 s, first
  reading 0.370 s; UV 0.236 s / 0.231 s), at least three readings per patch per pass; a row that
  cannot give that, or would need more than 1,150 readings (the cap a dual row may ask for, below
  the recorded UV-LED passes, which reach 1,820 readings by hand), is
  read patch by patch with the dual scan. M1 / M2 are worked out by the helper from the app's cut
  (the factory tables never leave it), after the hand dual scan's pairing check: a UV pass that
  does not belong to the row fails the row, which is offered again as a row or patch by patch (no
  slow repeats, unlike i1Profiler).
* **Calibration.** The spot white and, for rows, the strip white each read the tile with the UV
  LED right after (10 dark + 5 UV-LED readings, the volts; on the table's tile, as recorded).
* **Files.** M1 and M2 are assembled from the same rows as M0 (each patch from its M0 row) and
  filed beside the run's measurement as the i1Pro 3 Beta's files, with the pass record, so Build
  Profile starts at the person's choice as after a hand dual scan. Every reading of both passes,
  the cut and the helper's input and output stay in the session folder.
* **Proof on the recordings** (private, statistics only; table work folder `proof/out/replay.txt`):
  the five accepted recorded rows through this cut: M0 0.082 mean / 0.218 p95 / 0.317 max dE00
  against i1Profiler's own file (in its table white reference); with i1Profiler's M0 as the base,
  M2 0.015 / 0.054 / 0.149 and M1 0.007 / 0.024 / 0.076 at the instrument's own factor (0.027 and
  0.011 means at the standard 1.156); every wrong row's UV pass (8 of 8) refused by the pairing.
  With the 1.0 mm edge alone the same rows give M0 0.104 / 0.254 / 1.326 (one patch at the edge)
  and, on i1Profiler's M0, M2 0.013 and M1 0.006 means.

### 10a. Fix round after the table safety review (2026-11-19)

**Confirmed by:** *nobody yet.* Built, tested against the simulated table (4.3.47's less ideal
one) and the real helper's replay instrument, and driven on screen; never run on a real table.

* **On 4.3.47's table rules.** The branch carries v4.3.46 and v4.3.47. The UV pass is preceded
  by one more position reading when a question was answered (or the arm let go) after the lamp
  pass's last reading; a held arm that moved more than 5 units stops the step before anything
  moves. The UV pass's start beside its target by 6 to 10 units fails the row cleanly (read it
  again, or patch by patch); further off stays a doubt. A dual row's front-zone row ends follow
  the strip row's arrival rule. Caps: the UV pass 10 lines (8 recorded + 1 read-again + 1 own
  reading), 2 movements; a dual row 29 / 6.
* **The lamp pass's dark** is taken at least 170 ms after the lamp went out (i1Profiler: 131 to
  180 ms on the volunteer's table); the UV pass's dark follows at once, as recorded.
* **The UV pass's timing is checked against the chart.** Its 380-400 nm readings are laid over
  the chart's patches for every motion start within 6 readings; a pass whose best start is 1
  reading (about 0.7 mm) or more from the assumed one, with a clear gain, fails the row
  (`uv_pass_timing_off`). Both passes' best-fitting motion starts are written into every dual
  row's record and the session log. On the recorded rows: every correct pass accepted, every
  pass 2 or more readings off refused.
* **The driver fires only the pass its last ready check allowed**, once (behind the helper's own
  arm step).
* **Texts.** The ES-2000 is no longer said to lack the UV light or ruler (ArgyllCMS ties that to
  part number EO2-XR-UF); the model question sends ES-2000 owners to "i1Pro 2" and says ChromIQ
  notices a unit without the UV light by itself. A button whose label is an i1 product name keeps
  its case. After Stop while a step ran, the report page says the arm does not go on. The failed
  row's message says ChromIQ uses none of the row's values (its raw readings stay in the session
  folder).

### 10b. Fix round after the re-review (2026-11-19, for 4.3.48)

**Confirmed by:** *nobody yet.* Built and tested against the simulated table and helper, and
driven on screen; never run on a real table.

* **The lamp pass of a dual row is judged too** (SHOULD-A). The same fit as the UV pass's, over
  the lamp pass's readings at 380-730 nm. A lamp pass whose best start lies 1.75 readings or more
  LATE of the assumed one, or 2.5 or more EARLY, with the same gain gate, fails the row
  (`lamp_pass_timing_off`: "the first pass, with the lamp, did not lie over the patches where
  ChromIQ expected it (it was off by about 1.2 mm or more) ..."), and the row is offered again
  as a row or patch by patch. The window is uneven because the recorded data are: the five
  recorded lamp passes (driven by the vendor's software) fit 0.25 to 2.25 readings early and
  read well, and moving them costs little up to 2.75 early but 1.5 to 1.95 dE00 at 2.25 to 2.75
  late. On the recorded rows, every recorded pass accepted; every accepted shift within 0.44
  dE00 (max) of the vendor's M0; every shift that cost 0.6 dE00 or more refused. The released
  single-scan strip rows are not judged (unchanged). The verdict goes into the row's record
  (`lamp_checked`, `lamp_refuse`) and the session log.
* **Every page of the table's panel that waits for an answer keeps its answers in view** (also
  a fix of 4.3.47): in a small main window the failed row's answers could be out of view while
  the arm stood over the sheet. A text longer than the room now scrolls above the answers.
* **OEM wording** (SHOULD-B, NOTE-D): an OEM i1Pro 2, such as an EFI ES-2000, "may or may not
  have the UV light" (ArgyllCMS names the part number EO2-XR-UF for the units built without it;
  a tester's ES-2000 reports itself as an i1Pro 2 with a working ruler). Such a unit has a UV
  filter in place of the light, so its plain result is not called "M0 as always": it measures
  "as always, without the dual scan". In the model question, the Preferences text, the
  `not_available` and `no_uv_tables` reasons and the table's `dual_no_uv_tables`, 13 languages.
* **The UV pass's cap is 9 lines** (NOTE-A; 10 before): the job's read-again after a question
  and the pass's own reading exclude each other (the lamp pass's last motion is confirmed when
  the UV pass starts, and every motion clears the kept reading). A dual row: 28 lines, 6
  movements. A tenth line is refused by the step's cap.

### 11. The hand dual scan's gaps (2026-11-19, for 4.3.49)

**Confirmed by:** *nobody yet.* Built from the desk analysis `DUAL_GAPS.md` (work folder
2026-11-19_dual_gaps), tested against the simulated helper, the real helper's replay instrument
and the fake-USB trace of the real driver (`tests/test_i1pro2_dual_gaps_4349.py`, scenarios
`uv-held` and `uncal` of `i1pro2_dual_test.c`), and driven on screen against the simulated
helper; never run on a real instrument. Changes what sections 7 (c), 8 and 9 describe, as listed.

* **While the second pass (UV light) of a hand strip is due, nothing moves the reader.** A jump
  (a click on the chart preview), a navigation key, "I read strip B" and "turn round" are held:
  the app does not send them (`MeasureManager._dual_pass_holds`) and says so in the status line
  and once in the log (M-DUAL-PASS-HELD); the helper holds such a command too if one reaches it
  (`cq_dd_held_command`) and goes on waiting for the UV pass (event `dual_pass_held`). The wait
  is left before any trigger (ArgyllCMS returns before its dark reading on an abort), so holding
  sends nothing; the UV pass that follows is the recorded 0x0209 and closes the stream. The
  helper closes its calibration gate during the wait, so a calibration asked for then runs at
  the next strip prompt, never over the open ruler stream (the app held it already). Esc, quit,
  done and the finishing window's hold leave the wait as before; Esc still ends M1 / M2 for the
  session (section 7 (c)). Why not "discard the first pass and jump": the first pass's ruler
  stream is closed only by the UV pass's trigger ("ruler end", the one recorded form); nothing
  else may close it.
  After the review of 2026-11-19 the app holds such a command also while the strip's FIRST pass
  is being read (the instrument has fired, `scan_started`, with a usable dual calibration): the
  helper would only take it at the UV wait and hold it there, and the tab had logged "Jumping to
  strip C" for a jump never made. M-DUAL-PASS-HELD is said when the `dual_pass` event comes; a
  first pass that ends without one (a misread, M1 / M2 ended) drops the held command silently.
* **A calibration that cannot give M1 / M2 asks for a new one instead of ending them** (replaces
  section 9's "the pass prompts say so ... not asking for that pass at all needs a helper
  change"). The strip after it is read as a plain lamp scan (no "ruler start", so no second
  pass is due: the single scan's requests, byte for byte) and refused once per calibration with
  `dual_pass_result` `"calibrate": true` (a misread; M-DUAL-CAL-AGAIN in Strip Read Failed); a
  new calibration then gives M1 / M2 again. Read again without a new calibration, the strip is
  kept as M0 and M1 / M2 end for the session as before (the way out, so a broken UV light never
  loops). Once that one refusal has come, the strip prompt says that the next reading without a
  calibration is kept as M0 and ends M1 / M2 (M-DUAL-PASS-ONE-NO-CAL-KEPT), whether it is the
  same strip (Retry) or another one (Skip Strip); M-DUAL-CAL-AGAIN tells the person to press
  Retry first and calibrate before reading, because the Calibrate button is behind that window
  (review of 2026-11-19, M1 and S1). The reasons: `no_dual_calibration`, `uv_tile_dark`, `calibration_mode_changed`
  (known before the strip) and `calibration_mismatch` (known after the UV pass; that strip had
  both passes). Patch by patch the same, without the UV half. M-DUAL-PASS-TWO-NO-CAL is
  withdrawn; M-DUAL-PASS-ONE-NO-CAL and M-DUAL-CAL-REFUSED say the new rule.
* **A refused Continue keeps the measurement's identity.** When the engine refuses to take M1 /
  M2 up again on a Continue Measurement (`why: "resume"`), the main file keeps
  `CHROMIQ_DUAL_SCAN` and the factor keywords, plus `CHROMIQ_DUAL_ENDED "resume"` (section 9 said
  it was written without them). A later Continue is then the engine's "resume" again, not
  "mixed".
* **"High resolution spectral mode (-H)" with the dual scan by hand is refused before START**
  (M-DUAL-HIGHRES-REFUSED), as the table already refused it; before, the note promised a dual
  scan and the engine ended it at once.
* Not changed in this section: Continue Measurement still could not bring M1 / M2 back after
  they ended (gap 3 of the analysis; done since, section 12), high resolution itself, the i1iO table, the FD-9.


### 12. The other conditions of strips already read are kept (2026-11-19, for 4.3.49)

**Confirmed by:** *nobody yet.* Built on Sebastian's ruling of 2026-11-19 ("i think we should do
this because it also touches the way we use check and refine. if the tab tells and guides users
to remeasure certain strips then it would be an annoyance if this then makes them loose the
other condition files"; and, the same day, "the dual scan agent shall fix any faults it finds
for the i1pro 3 as well"). Tested on the real helper's replay instrument (dual scan and i1Pro 3),
against the simulated helper, and across helper versions (4.3.48 and this one, both ways);
never on a real instrument. Changes what sections 2, 2a, 7 (c), 8, 9 and 11 say about M1 / M2
ending, as listed. Tests: `tests/test_conditions_kept_4349.py`; the paths: work folder
2026-11-19_dual_continue, `paths.txt`.

* **The fault.** One strip read without its other conditions (a dual strip without its UV pass:
  the ruler lost, a UV pass left with Esc, a strip kept as M0 after an unusable calibration, an
  instrument without the UV light; or an i1Pro 3 reading the driver gave without them) ended the
  conditions for the sitting; no file matched the readings any more, and the session-end
  housekeeping deleted the last pair: every strip lost its M1 and M2, and Continue Measurement
  could not bring them back. The same happened when Check & Refine's list, a click on the chart
  preview or a misread's way out read a strip again without its UV pass. Reproduced on 4.3.48.
* **The rule (one for every path, and the same for the i1Pro 3).** The engine keeps the record
  (`chromiq_chartread.c` cq_cond_keep). A strip read without its other conditions has the main
  condition only from then on: its old M1 / M2 go with its old reading, never left beside a new
  M0. Every other strip keeps its own. A strip read again with all three replaces all three
  together. Why this rule: it is the only one that never mixes two readings of one strip and
  never throws away a good one; the alternative (keep the old M1 / M2 beside a new M0) would pair
  values of two different readings.
* **The files.** While every read patch has all three: the complete pair
  `conditions/<hash>-Mx.ti3`, exactly as before (byte for byte; Build Profile offers it). While
  some have the main condition only: `conditions/<hash>-Mx.partial.ti3`, holding only the patches
  that have all three (Build Profile never offers it; the housekeeping keeps it while a
  measurement holds its readings, and deletes it otherwise, as a pair). ChromIQ 4.3.48 and
  earlier neither read nor delete a partial file: they continue such a measurement as M0 only,
  as they always did after an end (fails safe).
* **Continue Measurement** takes the complete pair back, else the partial one. A dual
  measurement without either (its M1 / M2 already lost, for example by 4.3.48) is continued with
  every strip read before as M0 only. The strips not read yet are read with all three (a dual
  scan: both passes, after the fresh dual calibration that every start asks for), and the strips
  with the main condition only are read again when the person reads them. A dual measurement
  continued where the UV pass cannot be read (an instrument without the UV light) is continued
  as M0 only with its record kept: nothing is armed, the strips read then are M0 only, the
  header stays a dual one (M-DUAL-ENDED-KEPT with the reason). The only ends that keep nothing
  are a file that cannot be written and memory (M-DUAL-ENDED, unchanged).
* **The Measure tab offers to fill the gaps** (no new window). Before START, the status line
  names the strips with the main condition only: with "Refine / resume" ticked,
  M-DUAL-CONTINUE-FILL (i1Pro 3: M-COND-CONTINUE-FILL); without it, how to complete them instead
  of measuring everything again (M-DUAL-FILL-OFFER / M-COND-FILL-OFFER). At Continue Measurement
  in strip mode with ChromIQ's engine, the refinement guide takes the reader to those strips and
  to every strip not read yet, in chart order (together with a ticked refinement list), so the
  guide ends when the chart is complete. Patch by patch the guide is not used for this (its
  sentences speak of patches "above the limit"); the note and Build Profile's line still name the
  strips.
* **Build Profile** offers only conditions every strip has; until then it says which strips have
  the main condition only and how to complete them.
* **Section 11's "a refused Continue keeps the measurement's identity"** remains in the engine,
  but a dual measurement is no longer refused on a Continue; only a measurement whose header
  4.3.48 rewrote without the dual record (after such a refusal) continues as M0 only
  (M-DUAL-CONTINUE-M0, `session.ended_before`).
* **Not changed:** what is sent to an instrument (`safety_brief.txt` of the work folder); the
  complete files; the i1iO table's own condition files; averaging (a condition is averaged only
  when every read has its complete pair, so a read with partial files gives the average none, as
  before); a measurement made with the Beta off and continued with it on (still the main
  condition only, `why: "resume"`).

### 13. On the i1iO 2 table too: M1 and M2 are kept per row (2026-11-19, for 4.3.50)

**Confirmed by:** *nobody yet.* Built on Sebastian's ruling of 2026-11-19 (section 12), brought
to the table, which until 4.3.49 kept M1 / M2 only when every patch had them and otherwise none
(section 10, "Files"; 4.3.49's known issue). Tested against the simulated table and helper, and
driven on screen against them; never on a real table. Tests:
`tests/i1io_table/test_4350_dual_m1_m2_per_row.py`. Nothing new is sent to the table or the
instrument: no helper change, no new line, no new order (the rows are read exactly as before).

* **A row whose second pass failed or was refused keeps M0 only.** When the lamp pass of a dual
  row ran to its end and only the UV pass could not be used (it could not be started, did not
  belong to the row, lay off the patches, or the helper could not work out M1 / M2 from it), the
  lamp pass is cut on its own, by position, with the dual row's own windows and checks (the
  widest clean edge leaving every patch its readings, one colour per window, plausible values,
  the lamp pass's own timing check; `dual_rows.cut_lamp_only`). If that cut holds, the row keeps
  it as its M0 readings and has no M1 / M2; if not, the row stays unread, as before. Patch by
  patch, a row whose reading program wrote no M1 / M2 keeps its M0 readings likewise. In both
  cases the row still counts as failed, so the person is asked as before (read it again, patch
  by patch, skip, end), on a page that says the row keeps M0 only (M-I1IO-DRIVE-ROW-M0-ONLY-STRIP,
  M-I1IO-DRIVE-ROW-M0-ONLY). A Stop pressed between the passes is the person's choice, not a
  failure: that row's values are still not used (unchanged).
* **The files, as by hand (section 12).** Each patch's M1 / M2 come from the same reading as its
  M0 (the reading that M0 assembly takes, `measurement.m0_sources`; the base's complete pair, else
  its partial pair, for a patch from the run's earlier measurement). Every read patch has them:
  the complete pair `conditions/<hash>-Mx.ti3`, as before. Some have: the partial pair
  `conditions/<hash>-Mx.partial.ti3` with only the patches that have all three, in the main
  file's order (Build Profile never offers it and says which strips have M0 only). None has: no
  pair (every read patch M0 only, as a hand dual scan whose M1 / M2 never started). The pass
  record names a row with M0 only "lamp pass good, second pass due".
* **Completed by reading again.** Reading the row again in the same sitting takes M0, M1 and M2
  from the new reading together. **Continue Measurement** with the dual scan on (Refine / resume
  ticked) also reads again every patch of the run's dual measurement that has M0 only, together
  with the patches still missing; with the dual scan off it never does (and a single-scan
  session never continues a dual measurement, as before). An average is never completed (as by
  hand).

### 14. The lights in a dual scan: the blue "second pass due", and the quiet time as a setting (2026-11-20, for 4.3.52)

**Confirmed by:** *nobody yet.* Built on the owner's words of 2026-11-20: *"yes build the blue
light, are we too cautious with our waiting time at the moment?"* and *"could we allow the user
to set the timing himself with recommendations of what was measured inside i1profiler and leave
more room than that to the bottom end?"*, and on his rule of the same day that ChromIQ does what
the vendor's software does unconditionally (memory: i1io-table-more-commands-ruling, rule 4).
Tested on the fake USB layer through the real driver, against 4.3.51's driver, and driven on
screen against the simulated helper; never on a real instrument. Tests:
`tests/test_i1pro2_dual_blue_and_quiet_time.py`. Study: ChromIQ-work
`2026-11-20_pulse452b/quiet_study.txt`.

* **The blue.** With the lights Beta on ("X-Rite i1Pro 2 and i1Pro 3: show the instrument's state
  with its lights", with "Ready light and result signals") AND the dual scan on, an i1Pro 2 gets
  i1Profiler's own blue after the first pass of a strip by hand: the left LED pulsing blue
  (0.63 s per pulse) until the next light command; byte for byte the 702 bytes all 23 recorded
  writes of 6 i1Profiler 3.8.6 sessions sent (request 0xD6, then bulk 0x03), the only blue form
  ever recorded. It is sent 0.55 s after pass 1's data is in (recorded: 0.53 to 0.67 s at normal
  speed, 0.81 to 0.97 s in the slow steps; 0.55 s is the early end, which leaves the most time
  before the person presses), from the wait for the return pass's button press, with no arming
  command added or moved; also after a first pass ArgyllCMS did not recognise (as recorded:
  i1Profiler shows blue there too and red only after the return pass). Green or red follows the
  return pass as before and replaces it.
* **What it means, in the texts.** "The second pass of this strip is due". Never a direction:
  the recorded blue is always on the left, and ChromIQ lets the return pass be read either way.
  The Measure log says "blue. The second pass of this strip is due."; the app log says
  `lights: sent=blue meaning=second_pass_due quiet_ms=...`.
* **Never late, never twice.** If the button is pressed before the blue is due (faster than any
  recorded case: i1Profiler's presses came 0.33 to 1.35 s after it), the blue is skipped for that
  strip, never sent during or after the trigger (app log `lights: second_pass=skipped
  why=early`). The driver refuses it outside the return pass's wait, in a lamp pass, in a single
  scan, once the button was pressed, while a trigger is pending, without result signals, and a
  second time in one wait. With "Ready light only" nothing would replace the blue after the
  return pass, so it is not sent then.
* **The blue has its own quiet time: 0.37 s (fix round of 2026-11-20).** The blue follows
  i1Profiler's timing, and so does the wait after it: when the last light write was the blue (it
  went out, nothing was written after it), the return pass's trigger waits 0.37 s after the blue
  (`CQ_LIGHTS_BLUE_QUIET_MS`), whatever the quiet time below is set to. i1Profiler triggered the
  return pass 0.372 to 1.389 s after this very program, 15 of 15, every reading came; 0.37 s is
  never closer than that. Any later light write (the OFF_SLOW before a calibration after an
  abandoned return pass, an off during the hold) gives the quiet time below back, and so does
  leaving the return pass: the 0.37 s applies only while that strip's return pass is the one
  waiting, so after an Esc in the second pass the next strip's first pass waits the quiet time
  below (4.3.52 release, helper 2026-11-20c, re-review S2). A hold after
  the blue goes to the app log only (`lights: held_ms=... after=blue quiet_ms=370`). Before the
  fix round the return pass waited the full quiet time after the blue (0.7 to 1.7 s of keeping
  still at the default, review S1). Why this is judged safe enough for a Beta, and what stays
  unproved (ChromIQ's driver submits the data read before the trigger, i1Profiler after it):
  ChromIQ-work `2026-11-20_pulse452_fix/decisions.txt`.
* **Off means off.** With the lights Beta or the dual scan off, nothing new is sent and the
  driver's path is 4.3.51's: proved request for request on the fake USB layer against 4.3.51's
  driver. The change is in ChromIQ's copy of ArgyllCMS's instrument code (the lights block of
  `native/instlib/i1pro_imp.c`, re-applied by `scripts/vendor_instlib.py`); the option's help
  says so.
* **The quiet time as a setting.** Preferences > Beta, under the lights option and greyed while
  it is off: "i1Pro 2, wait after a light change", 0 to 10 s in steps of 0.05 s with two
  decimals (comma or point typed, the mark of ChromIQ's language shown; a text that cannot be
  taken is said under the field), default **2.1 s** (4.3.37's value;
  the study found i1Profiler waiting 0.37 s at the least and about 0.46 s as a rule before a
  hand-held reading, and 0.01 s before a calibration, every reading arriving, but nothing
  measured with ChromIQ's own driver between 25 ms, where two readings in three were lost, and
  2.1 s). Beside it: the default, i1Profiler's numbers, what a too-short value can do (a reading
  lost, "The instrument lost communication with the computer", the strip read again; a
  calibration retried, and if it keeps failing the measurement ends and is started again,
  Continue Measurement keeping the strips already read; in a dual scan a lost second pass ends M1
  and M2 for the rest of that measurement), that the wait is in ChromIQ's copy of ArgyllCMS's
  instrument code, and that ChromIQ writes the value into the app log. It changes only how long
  a trigger waits, never a byte (proved on the fake USB layer). Not 2.1 s: the helper gets
  `--lights-quiet-ms`; 2.1 s: the command line stays as it was. The value is in the measurement's
  start line (`i1pro2_lights_quiet_s=`: at Start the instrument is not known yet), the
  session's lights line (`quiet_ms=`, `blue_quiet_ms=`), and the session header's list of Beta
  settings (`i1pro2_lights_quiet_s`). The i1Pro 3 has no quiet time: its session line says
  `lights: instrument=i1pro3 quiet=not_used`.

### 15. ⏳ Awaiting confirmation: the blue light's side, and the Auto strip recognition (2026-11-20, for 4.3.53)

**Confirmed by:** *nobody yet.*

The source: the tester's report on a real i1Pro 2 of 20 Nov 2026 (4.3.52): after a first pass from
right to left the LEFT blue light still blinked; *"it should be the right light blinking towards
the direction of the return scan"*. Decided by the coordinator for the owner (he delegates technical
decisions; the lights are a Beta option and a light cannot harm anything).

* After a first pass from left to right: the recorded left blue (mask 0x20), byte for byte.
* After a first pass from right to left: the same 702-byte program with its side bytes 0x04
  (ArgyllCMS's "Blue Right"); never seen alone in a recording (all 23 recorded first passes ran
  left to right).
* The direction is the ruler stream's net count when the blue is due; not known (fewer than 100
  steps, no stream): the left blue. Timing, the 0.37 s, the skip when the button comes first:
  unchanged.
* Strip recognition, Auto: a chart that names no i1 Pro is decided from the instrument the
  measurement is made with (its report this session, the one this app run has seen, or the dual
  scan's instrument); an i1 Pro reads both directions (-b). Auto off: the person's choice, always.
  The app log says what Auto decided from at every start.

### 16. When the dual scan runs: "always" or "only for M1 or M2" (2026-11-20, for 4.3.54)

**Confirmed by:** *nobody yet.* Built on the owner's words of 2026-11-20, quoted as given:
*"for the dual scan i think this could be nice to leave it always on but then at least
selectable in a combobox as part of this option one should be able to choose whether to only
use the dual scan when choosing another measurement condition then m0. so choosing m0 would
only do the regular scan and m1 or m2 would do the 2 pass dual scan and save all conditions.
that way the user does not always have to spend time for something he does not need and has to
set one option less in case he does need it at some point"*, and *"that second option can
already be built before leaving the beta so it is more what we expect"* (the option stays a
Beta option in Preferences > Beta; leaving the Beta is not part of this). On the layout: *"i hope
the combobox does not need an extra line in the beta section and fits right within the line of
the main option"*. On the note: *"for the message shown before the first strip the user shall be
able to choose to never show this again or something. because once you know this the message
every time gets annoying"*. Asked whether it affects the i1iO 2 table: yes (the coordinator,
the same day). Tested against the simulated helper and the simulated table; never on a real
instrument or table. Tests: `tests/test_4354_dual_scan_mode.py`, `tests/test_4354_dual_scan_notes.py`,
`tests/test_4354_dual_scan_mode_row.py`, `tests/i1io_table/test_4354_dual_mode_on_the_table.py`.

* **Where.** A box in the dual scan switch's own row (right of its label, left of its (i)), with
  "always" and "only for M1 or M2"; greyed with the switch, as the other sub-controls are. Settings
  key `i1pro2_dual_scan_mode` ("always" / "m1_m2"), named in the app log's session header.
* **The rule, ONE function for the hand path and the table** (`workflow/dual_scan/session.plan_for`;
  the table's START `TabMeasure._table_dual_setup` asks it, the table window and job never read
  the option). "always" = 4.3.53, argument for argument. "only for M1 or M2": M0 chosen (the
  filter row off, or "M0: no filter") = the ordinary single scan: no `--dual-*`, and the row's
  "-F n" is not sent (an i1Pro 2 refuses every -F; with no -F in the row the command line is
  exactly the one with the dual scan off); M1 or M2 chosen = the dual scan of "always", every
  condition saved. Checked first, in both modes, as before: the switches, the engine, an
  instrument known to be another model, the polariser / D65.
* **Guided** has no condition row (`GUIDED_CHARTREAD_KEYS`). The owner's decision of 2026-11-21
  (replacing the builder's first choice, which ran the dual scan there as with "always"): *"i would
  have leaned to make it single pass in guided only and leave the condition choice and in turn the
  dual scan to manual module"*. So under "only for M1 or M2" GUIDED reads a single pass (no choice =
  M0; `why_not` "guided") and its note says that M1 and M2 are read from MANUAL by choosing M1 or M2
  there (M-DUAL-GUIDED-SINGLE, dismissible like the others); under "always" GUIDED keeps the dual
  scan (always means always; testers who have the option on today keep it). The i1iO table uses
  the filter row of the module it is started from, so the same rule holds there.
* **A continued measurement keeps the kind it was started with** (`session.started_as`, the
  run's own record: the main file's dual record, or its pass record): under "only for M1 or M2"
  a dual measurement continues as a dual scan whatever is chosen now; a single-scan measurement
  continues as a single scan (M0 only, the row not sent as -F), never refused and never mixed.
  This holds for Continue Measurement, Check & Refine's re-reads, the next page of a multi-page
  chart read as a Continue, and the table's rows and re-reads. After the review of 2026-11-21
  (S1, "a run continues the way it was started") the same holds under "always": a one-pass run
  is continued with one pass per strip (4.3.53 refused it at START, `mixed_scan_kind`). A
  re-read inside a sitting is the sitting's own (decided once at START).
* **After the review of 2026-11-21 (M3): a note that takes away a dual scan the person asked
  for is never hidden.** With mode "always", or M1 / M2 chosen, the notes for a one-pass
  measurement being continued, an instrument known as another model, a reading program or an
  engine that cannot do the dual scan, and an older reading program with the run's one-pass file
  in the way, have no "Don't show this again" and show at every start, also when an earlier
  build had hidden that kind (nothing else says it before the readings: no --dual-* is passed,
  so no M-DUAL-ENDED comes). Every other note stays dismissible as built.
* **Default and migration** (the coordinator's decision): a new store reads "only for M1 or M2";
  a store whose dual scan switch was already on when 4.3.54 first runs is given "always" once
  (settings schema 35, `_migrate_dual_scan_mode_keep_4353`), so nothing changes silently for the
  testers who use it. Decided once (the schema step), never again at a later start.
* **The note before START** (status line under the log, one line, the whole note on hover and
  once in the log; texts §M-PROPOSED M-DUAL-GUIDED-SINGLE, M-DUAL-OLD-FILE, M-DUAL-M0-CHOSEN, -SINGLE-CONTINUES, -NOT-I1PRO2,
  -NOT-THIS-CHART, -NO-ENGINE, -HIGHRES-NOTE, -NOCAL-NOTE, -FILTER-NOTE, -CANNOT-CONTINUE,
  -LAST-CANNOT, -BEFORE-START-TABLE beside the existing M-DUAL-BEFORE-START and
  M-DUAL-CONTINUE-M0). Every reason the code has for not running the dual scan has its sentence:
  M0 chosen; GUIDED under "only for M1 or M2"; a single-scan measurement continued (its own
  sentence: "You are continuing a measurement that was read with one pass per strip ...",
  `mixed_single_continued`, also in the START refusal and the session's end line); a reading
  program older than 4.3.54 with the run's one-pass file beside the chart (`mixed_new`, issue
  217's R1); the instrument not an i1Pro 2; a calibration
  chart, or a chart for another instrument (FD-9, CR30); the chart-reading engine off, or one
  without the dual scan; "-H"; "-N"; the polariser / D65; a measurement that cannot be continued
  with it (another factor, or single under "always"); and what the LAST measurement found about
  the instrument or its calibration (no UV light, no factory data, the tile reading with the UV
  light failed: `dual_scan_last_cannot`, forgotten at the next good dual calibration). A note for
  a chart the table reads speaks of rows, not of the ruler.
* **"Don't show this again"** beside the note (a link in the same line; the app's existing
  wording and its existing pattern of a stored bool per kind, here one key
  `dual_scan_notes_hidden` holding the kinds): per kind, "will_run", "m0_chosen", and
  "cannot:<reason>" per reason, so a new reason shows again once. Restore Factory Defaults brings
  them back (the app has no other reset for "don't show again"; none was invented). Not the
  self-retiring pattern of the table's row note (4.3.52): that note retires after a completed
  measurement because it warns about something unproved; these notes are information the person
  decides to stop seeing. The note that M1 / M2 stopped during a measurement (M-DUAL-ENDED) is an
  event of the running measurement and is unchanged.
* **The app log** says the decision at every START with the dual scan on, also when the note is
  switched off: `dual scan decision: where=hand|table mode=... kind=... hidden=... why="..."`.
* **Texts.** The filter row's (i) says what the row does with the dual scan in each mode, and
  "You measure the chart once, not once for each condition"; Build Profile's reason for an
  i1Pro 2 measurement without the dual scan no longer reads "Only an X-Rite i1Pro 3 gives all
  three conditions from one scan" (it says the measurement was read without the dual scan, and
  how to get M1 / M2); the dual scan's (i) states the trade-off of "only for M1 or M2" (a chart
  measured with M0 chosen has no M1 or M2 later without measuring it again).
* **Not changed:** what is sent to the instrument or the table in a dual scan or a single scan;
  Build Profile's offer (an M0-only run behaves as any i1Pro 2 run without the dual scan).

### 17. ⏳ Awaiting confirmation: the UV pass counted over the whole clean middle, and the pace after each strip (2026-11-21, after 4.3.54)

**Confirmed by:** *nobody yet.*

Built on the owner's words of 2026-11-21, *"yes do it as suggested 1 and 2"* (the study of the
refused UV passes, work folder 2026-11-21_uv_pass_refusals: a tester's i1Pro 2 refused 27 of 87
UV passes as too fast). He approved the change, not the result below. Tested on the replay of
instrument 1's recorded hand dual sessions (private, numbers only: work folder
2026-11-21_uv_pass_build, `proof.txt`), against the simulated helper, and driven on screen against
it; never on a real instrument. Tests: `tests/test_uv_pass_rule.py`, `tests/test_dual_scan_pace.py`.
Helper 2026-11-21b; lined up from helper 2026-11-21e (second fix round). Changes what section 2a
says about the UV pass's window.

* **The UV readings of a patch.** The cells are ArgyllCMS's own, already trimmed to the clean
  middle 66 % of each patch it found in the lamp pass (it accepts a lamp patch from 4 readings
  there). Until 4.3.54 the UV readings of a patch were those whose ruler position lay in the
  central 60 % of the cell's span (first to last lamp reading), so the UV pass needed about 1.5
  times slower movement than the lamp pass. Now, first, the UV pass is LINED UP with the lamp
  pass (below), and then a patch's UV readings are those in the whole span less a quarter ruler
  step at each end (`CQ_DUAL_EDGE_STEPS` / `cut.EDGE_STEPS` 0.25); at least 3 readings per patch
  as before.
* **Lined up first (second fix round of 2026-11-21, the verification's V1).** The UV pass's
  ruler positions are off the lamp pass's by an offset that differs per strip: the count labels
  one stripe edge one count apart in the two directions, and the hand adds to that (13 recorded
  strips: -1.0 to +1.45 steps). The first version left half a step at each end and relied on an
  alignment measure averaged over the strip (`uv_pass_shifted` at 0.001); the verification showed,
  patch by patch, accepted strips with single patch ends up to 0.48 dE00 worse in M2 at an extra
  1 to 1.5 steps, and already 0.34 at 1.25 times the speed within the recorded offsets. A larger
  fixed margin does not hold either (1.5 steps: patches up to 0.64 worse at +1.25 to +3 steps, the
  speed gain gone: first refusal at 1.05 times). So the offset is MEASURED per strip: at 380-400
  nm nothing glows, so the UV pass reads there (T / W) x the lamp reflectance at the same place;
  the helper keeps the lamp pass's own 380-400 nm readings, and the offset is the shift (-6.5 to
  +6.5 steps in 0.05) that best lines the two up, one gain, least squares
  (`cq_dual_align` / `cut.estimate_offset`). The UV positions are corrected by it, then cut.
  Refused as `uv_pass_shifted` (M-DUAL-PASS-SHIFTED: both passes again, section 0 (a)) when the
  offset is above 3 steps (beyond anything recorded: the instrument moved between the passes).
  The averaging window's measure (0.001) stays as a second check; it is an average over the strip
  and does not by itself hold a single patch.
* **When a strip cannot be lined up: 4.3.54's window, not a refusal (third round of 2026-11-21,
  decided by the coordinator: "we do not block what can be measured today").** Two cases: (1) no
  single offset fits clearly (the residual one step either side below 1.15 times the best: patches
  alike at 380-400 nm, or an offset that changes by several steps along the pass); (2) the helper
  has no lamp readings to line up with (a lamp pass over 4000 readings, a failed allocation). The
  strip is then cut UNCORRECTED with 4.3.54's central 60 % window and 4.3.54's gate, exactly
  4.3.54's behaviour and exposure, not a new one: measured on the replay, fine up to about 2 steps
  of real offset (at most 0.095 dE00 per patch at the recorded offsets), beyond that up to 1.2
  dE00 for a uniform offset and up to 3.9 dE00 when the offset jumps by 3 steps or more in mid
  pass (the pairing check does not catch that). On such a strip the speed gain is lost too: the
  readings are counted in the central 60 %, and the pace line and the "too fast" advice are
  computed from those counts (the window actually used), so they ask for the slower pace again.
  The narrow window is used ONLY on lined-up positions (`cq_dd_edge`). The app log says per strip
  which way was taken: `align=lined_up offset_steps=... offset_rise=... window=span_less_edge`, or
  `align=not_lined_up` / `not_measured` with `window=central_60` and `edge_steps=-1`.
* **The tester's own chart (480 patches on Action, an OBA paper).** At 380-400 nm its
  patch-to-patch contrast is about 0.39 times that of instrument 1's 13 recorded strips (also
  Action and Moab, both strongly brightened). Simulated with the recordings' geometry and noise
  and their measured mismatch between the passes (checked against the replay), all 20 of his
  strips line up (720 of 720 passes, 1x and 1.25x, shifts -1 to +1). The margin to the "not clear"
  line is smaller than on the recordings; a strip falls back only far below his contrast (about
  0.15 times the recordings'). Work folder `proof4/`.
* **Why a quarter step (the physical reason).** After the correction what is left is the
  estimate's own scatter: replayed at up to 1.5 times the speed and with up to 5 times the noise,
  median 0.05, at most 0.20 steps; rounded up to the next quarter step. Readings beyond the span
  stay inside ArgyllCMS's own trimmed-off sixth of the patch.
* **The claim, per patch (replayed, instrument 1's 13 recorded strips; work folder
  `proof3/out_final.txt`).** With the UV positions shifted -6 to +6 steps by 0.25 beyond their own
  offset, at 1, 1.1, 1.25 and 1.5 times the speed: on every strip accepted, EVERY patch within 0.09
  dE00 in M2 and 0.02 in M1 of the same patch read at the recorded alignment with 4.3.54's window
  (the largest, +0.087, is one patch whose difference is reading noise, the same at every shift).
  Shifts that leave an offset above 3 steps are refused. No good pass refused (recorded alignment,
  2 to 5 times the noise, 234 passes). C and Python give the same offset on all 13 strips. This
  claim is for strips that were lined up, with an offset that holds along the pass; an offset that
  changes by up to 1 step in mid pass stays within about 0.14 dE00 per patch; strips that cannot
  be lined up have 4.3.54's limits (above).
* **What it changes, replayed (at the recorded alignment).** M1 / M2 against i1Profiler unchanged
  within noise. The simulated speed of the first refusal rises from about 1.05 to about 1.7 times
  the recorded i1Profiler pace (median of 13 strips, least 1.25; the lamp pass's own limit is about
  1.67): of the 13 recorded strips, 4.3.54's rule refused 4 at the recorded pace, the new rule none.
  The earlier private proofs had cut with the cells before ArgyllCMS's trim and over-counted; with
  the cells the helper uses, the recorded vendor pace already sat on 4.3.54's limit.
* **What is not shown:** a real chart that falls back (none of the recorded strips, none of the
  tester's simulated ones), and a second instrument.
* **The pace after each strip** (no new window). The helper's `dual_pass_result` of a hand strip
  carries, after the cut, `pace: true` with each pass's seconds (its readings x their integration
  time), readings, ruler travel in counts and direction, the readings per patch of both passes
  (`lamp_cells`, `uv_counts`), `need` (3), `edge_steps`, and when the lamp went out, the dark
  reading before the UV pass, the UV trigger and its end (`lamp_off_ms`, `uv_dark_ms`,
  `uv_trigger_ms`, `uv_done_ms`, after the lamp pass's readings). No speed in mm/s: the ruler's mm
  scale is not measured for the i1Pro 2.
  * Accepted strip: the Measure log and the reading-speed line under the chart say both passes'
    seconds of reading and the emptiest patch's readings against the 3 needed (M-DUAL-PASS-PACE,
    green from 5; M-DUAL-PASS-PACE-CLOSE, amber, at 3 or 4); the time under the strip is the
    second pass's seconds of reading, the same number.
  * ONE VERDICT PER DUAL STRIP (fix round, review M2). The reading-speed check of #131 times a
    strip from the SECOND pass's beep against ArgyllCMS's lamp-pass rule (samples per patch),
    which decides nothing about the UV pass; at i1Profiler's own normal pace (2.2 to 3.4 s) it said
    "Too fast" and offered to read again while the readings per patch left room. A hand dual strip
    whose engine gives the pace is judged by the dual check alone: no #131 line or prompt.
  * A second pass refused as too fast: "Strip Read Failed" (M-DUAL-PASS-FAILED) gives, as its
    reason, how many readings the emptiest patch got and how many are needed, and (fix round,
    review M3 / m1): when half of the patches got twice that or more, that one stretch was fast and
    to move evenly (M-DUAL-PASS-TOO-FAST-UNEVEN, no time named); otherwise a little longer than its
    seconds x (3 + 0.5) / readings, rounded up to half a second (M-DUAL-PASS-TOO-FAST); never a
    time at or above 0.8 x the longest pass taken (4000 readings, about 19.6 s): then only the
    limit (M-DUAL-PASS-TOO-FAST-EVEN). The reading-speed line says the numbers only, in red
    (M-DUAL-PASS-TOO-FAST-LINE). A pass refused as not lined up: M-DUAL-PASS-SHIFTED, its headline
    as the line.
  * The app log: `dual pass:` per verdict with these numbers (minimum and median per patch, both
    alignment measures and the window's limit, the advice case, slower factor, target and the
    pass limit on a refusal), `dual pass patches:` with both lists in full at DEBUG. No serial, no
    path. The seconds use the driver's integration clock, the i1Pro 2's 36 us once a calibration
    has run (always before a dual strip): replayed, 5.004 ms per reading at i1Profiler's 139
    clocks.
  * "Ruler (beta)": with the ruler check on, the opening line of a dual measurement says that the
    ruler lines the two passes up and that each strip's pace line is shown instead of the distance
    and speed (it promised per-strip ruler lines that a dual strip never gets).
  * An older helper sends none of this; then the texts are 4.3.54's.
* **Not changed:** what is sent to the instrument (the driver only notes times); the lamp pass's
  rules; the pairing check; spot readings; the i1iO table's dual rows (their own cut,
  `dual_rows.py`); a single scan.


### 18. ⏳ Awaiting confirmation: a refused first pass asks for no second pass (2026-11-23, for 4.3.58)

**Confirmed by:** *nobody yet.* Approved as a direction by Basti, 23 Nov 2026 ("when the first
pass is refused, refuse at once, do not ask for the second pass, and ask the person to read the
first pass again"). He approved the direction, not the details below. Built and tested against
the simulated helper and the real helper's replay instrument, and driven on screen against them;
never on a real instrument. Tests: `tests/test_dual_refused_pass_one_asks_no_second.py`. Helper
2026-11-23a. Texts §M-PROPOSED: M-DUAL-PASS-ONE-REFUSED, M-DUAL-PASS-ONE-AGAIN. When this section
is confirmed, it replaces what sections 7 (c) and 8 say about the second pass "asked for also
after a lamp pass ArgyllCMS did not recognise" (M-DUAL-PASS-TWO-UNREAD, "Read pass 2 anyway").

* **Why.** Until 4.3.57 a first pass ArgyllCMS refused was followed by the request for the
  second pass (M-DUAL-PASS-TWO-UNREAD), the person read it, and only then did "Strip Read
  Failed" open and both passes were read again. A tester read 10 such second passes in one
  morning (22 Nov 2026), each thrown away.
* **What counts as refused.** Only a first pass that ArgyllCMS's patch recognition refused
  (`dual_pass` with `lamp_ok` false: "not enough patches", "too many patches", "swipe did not
  start and end on the media", "not enough samples per patch", an inconsistent reading). Nothing
  else is known at the end of the first pass: the ruler, the cut, the pairing check, ArgyllCMS's
  "wrong strip" / "unexpected value" question (Use Anyway) and ChromIQ's slip check (Keep it) all
  come after both passes, so a first pass that was accepted, doubtful or not, still gets its
  second pass, and those choices are unchanged.
* **What the person sees.** At once: the status line says "Strip A: pass 1 did not read. Press
  the button once, then read pass 1 again" (M-DUAL-PASS-ONE-REFUSED, the whole sentence on hover
  and in the log), with the "Strip read failed" sound as since 4.3.52. No second pass is asked
  for. After the press, no "Strip Read Failed" window: the tab answers the misread with Retry
  itself, and the strip prompt asks for "Strip A, pass 1 of 2 again (lamp)"
  (M-DUAL-PASS-ONE-AGAIN), with ArgyllCMS's own reason in its sentence. The strip then goes on as
  always: pass 1, then pass 2. Skip, Stop and the navigation keys stay where they always are; a
  Stop under way keeps its own window (`ui/tabs/tab_measure.py` `_on_dual_pass`,
  `_dual_lamp_refused_misread`, `_dual_pass_one`). The failed strip is timed by its lamp pass, not
  by the press (`_report_failed_strip_pace`).
* **A connection lost during the press shows its window one step later.** After a refused first
  pass the helper reports the FIRST pass's error whatever the press returned
  (`chromiq_dualdev.c` `cq_dd_strip`: with `lamp_ok` false it sets `why = "lamp"` and keeps the
  lamp pass's code), so a connection lost during the press reaches the tab as the lamp's misread
  text, never as a connection error. The tab sends Retry as for any refused first pass; the
  helper's next lamp pass then fails on the lost connection, and that misread opens "Strip Read
  Failed" with the lost-connection advice: at the Retry, not at once. Nothing is lost by the
  delay (the strip was not read either way). The helper is deliberately not changed for this,
  since a helper change needs its own safety review (review of 4.3.58-a, finding 3).
* **Why one press is still needed (the limit, said plainly).** The lamp pass opens the
  instrument's ruler stream ("ruler start", 0x0105); the only recorded form that closes it is the
  UV trigger with "ruler end" (0x0209), which goes out when the button is pressed. ChromIQ sends
  only recorded forms (section 7 (c), safety review M2), so the helper still waits for that
  trigger exactly as before; the person presses once without moving the instrument, and nothing
  of that reading is used (`why: "lamp"`). A tap is the same trigger, only shorter; a tap is an
  ordinary short scan on the instrument (the button-gesture Beta relies on it). Not asking for
  the press at all would need a form that was never recorded (a programmed trigger, or a lamp
  trigger sent over an open stream): it needs a recording and a safety review first.
* **The lights Beta.** After a refused first pass the blue "second pass due" (section 14) is not
  sent: one light write fewer, nothing new on the wire; the app log says `second_pass=skipped
  why=lamp_refused` (`chromiq_chartread.c` `cq_lights_second_pass_due(lamp_ok)`). The red after
  the misread is unchanged.
* **Not changed.** Patch by patch (a spot reading is one unit: when the lamp half fails, the UV
  half is never read, `cq_dd_spot`). The i1iO 2 table: the UV pass of a dual row is part of the
  row's recorded movement and a lamp pass refused for its timing (section 10b) is judged after
  both passes; it costs table time, not the person's, and table command sequences need their own
  safety review, so it stays as it is. A refused SECOND pass: "Strip Read Failed" as before.
  What is sent to the instrument.

### 19. ⏳ Awaiting confirmation: the start-up calibration of a hand dual scan includes the LED wavelength calibration (2026-11-23, for 4.3.58)

**Confirmed by:** *nobody yet.* Item 40 of 4.3.58. Built and tested on the fake USB layer through
ArgyllCMS's own calibration code; never run on an instrument. Tests:
`tests/test_i1pro2_dual_startup_calibration.py` (trace: `native/chartread_helper/tests/
i1pro2_startcal_test.c`). Helper 2026-11-23b (`+dual-startup-wavelength`).

* **The fault.** From 4.3.48 (helper 2026-11-18c) to 4.3.57 the start of a hand dual scan in
  strips asked ArgyllCMS for a white calibration ALONE (`chromiq_chartread.c`, the strip branch's
  dual case, `inst_calt_ref_white`), where a normal start asks for what the instrument needs
  (`inst_calt_needed`). ArgyllCMS runs the i1Pro 2's wavelength-LED fit only when the request
  names it (`i1pro_imp.c` `i1pro_imp_calibrate`, the "Wavelength calibration" block), and the
  dark before the white only when the request names the dark. So every reading of a dual session
  (M0, M1 and M2) kept the factory wavelength offset, or one restored from ArgyllCMS's calibration
  file of an earlier session, and its white was taken against an earlier dark.
* **What it did to the numbers.** About 1 nm towards the red on one tester's i1Pro 2 in every
  dual session from 20 to 22 Nov 2026 (0.70 to 1.02 nm; 0.98 nm on 616 patches), most of the
  0.49 mean dE00 between ChromIQ's dual M0 and i1Profiler's on the same sheet; largest on greys
  built from inks and on colours with a steep spectral edge, smallest on paper white
  (`~/Desktop/ChromIQ-work/2026-11-23_item40/analysis.txt`, private data: conclusions only).
  Not yet re-measured with the fix on an instrument.
* **What changes.** The dual case asks for everything a normal start asks for and the white in
  any case (`chromiq_dualcal.h`, `cq_dual_startup_calt`: the needed set masked as a normal start
  masks it, plus `inst_calt_ref_white`). ArgyllCMS orders the work itself (wavelength, dark,
  white), so on the wire a dual start is now a normal start's calibration, byte for byte, followed
  by the dual tile exactly as before (10 dark + 5 UV-LED readings at the white's integration, the
  volts: section 7 (a)). The wavelength-LED pair it adds (a dark, then the LED, one reading each at
  the EEPROM's wavelength exposure, flags 0x0000 / 0x0300, no lamp clocks) is the pair every
  normal ChromIQ start sends and the one i1Profiler's recorded calibrations before a dual scan
  send (`tests/data/i1pro2_dual_wire_shape.json`, `wavelength_led_in_the_calibration`).
* **What the person sees.** Nothing new on screen: the same request to put the instrument on its
  tile, about a second longer (the LED reading is about 0.6 s). The readings move by about 1 nm.
* **Not changed.** Patch by patch and the i1iO 2 table already asked for the normal set
  (`inst_calt_needed`) and are untouched. A calibration asked for during the session (the
  Calibrate button) already asked for everything available. A session started with "no
  calibration" (`-N`) still does not calibrate.
