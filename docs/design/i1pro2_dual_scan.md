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

Step 1 (this document's code, 2026-11-18): the calculation, the stored form, the helper's
arithmetic and files, proved on recorded data; no user interface, no instrument commands yet.

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
outside 0.5-2.0.

### 2. The stored form (`workflow/dual_scan/storage.py`)

* The main `<stem>.ti3` is the lamp pass (M0), as an ordinary i1Pro 2 reading; M1 and M2 go to
  the i1Pro 3 Beta's `conditions/<hash>-M1.ti3` / `-M2.ti3`, written by the engine in the same
  autosave, in exactly that Beta's form. Everything downstream works on them unchanged.
* Every file of the measurement records `CHROMIQ_DUAL_SCAN "i1pro2"`, `CHROMIQ_DUAL_SCALE`,
  `CHROMIQ_DUAL_SCALE_SOURCE` ("standard" or "refined") and `CHROMIQ_DUAL_WHITE` ("instrument" or
  "table"). No serial number and no instrument key in any measurement file.
* A dual-scan measurement is never continued by single scans, nor the other way round (refused
  before START, reason `mixed_scan_kind`; the engine refuses it again, `why: "mixed"`).
* A dual reading only after a dual calibration at the same exposure; a change of reading mode
  in either direction needs a new calibration.

### 3. The scale s (`workflow/dual_scan/scale.py`)

* Built in: a standard factor, 1.156, the middle of the two instruments measured (1.100 and
  1.212). M1 / M2 work for every i1Pro 2 without vendor software (owner's ruling 2026-11-18).
* Optional: "refine the factor for my instrument" from one i1Profiler measurement of the same
  strip with the same instrument, plus ChromIQ's dual scan of it; checked (same strip, same
  instrument by its factory M1 ratio, enough brightener, a clean fit); stored per instrument
  under a one-way key.
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

* **ChromIQ's own UV reading has never run on a real instrument.** Step 1 contains no
  instrument command for the UV LED; the helper's dual path is fed only by its replay
  instrument. Every instrument step (the dual calibration, the UV pass, the volts query, the
  ruler across both passes, the dual spot reading on the table) is to be built from the
  recordings and is a first try until a real i1Pro 2 has shown it.
* s on a third instrument; s on instrument 2 with its own tile; the creep of s within a
  session (0.6 % over four rows on instrument 1); a paper without brightener (expected
  M0 = M1 = M2, untested on hardware).

### 6. Honest limits for the release notes (draft)

* M1 and M2 from an i1Pro 2 are calculated with a standard factor found on two instruments; on
  strongly brightened papers M2 can differ from i1Profiler's by about 0.1-0.2 dE00 on average
  and up to about 0.5, M1 by less. Papers without optical brightener are not affected.
* With i1Profiler, the factor can be refined for one instrument, which brought both test
  instruments to about 0.05-0.08 dE00 mean.
* Measuring with dual scan is a first try until a real instrument has shown it.
