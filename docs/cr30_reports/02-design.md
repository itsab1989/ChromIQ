STATUS: complete (design frozen for beta; open items listed in §9)

# CR30 beta — design

Branch `feature/cr30-instrument-159`. Rulings from Basti, 2026-08-28:
**live backend**, **honest `CR30` name**, **engine-only**, aiming helper is
nice-to-have.

## 1. What the user does (the whole journey)

1. **Settings → Instrument** shows `CR30` alongside i1Pro / ColorMunki / …
2. **Create Chart → Guided** (or Manual): pick `CR30`. The ChromIQ layout engine
   is **forced on** and the printtarg route is unreachable — a CR30 chart is
   always laid out by the engine. Patch grid, no strip furniture.
3. Chart is printed as today. `.ti2` carries `TARGET_INSTRUMENT "CR30"`.
4. **Measure tab**: with a CR30 chart loaded, ChromIQ starts
   `chromiq-chartread -x` (external values). **No instrument is opened by
   Argyll.** ChromIQ opens the CR30 itself (USB or BLE).
5. The engine emits `spot_ready` per patch; ChromIQ highlights the patch and
   waits. The user places the instrument and **presses the CR30's own button**.
   ChromIQ reads the stored measurement, converts to XYZ (D50/2°) and writes the
   value to chartread's stdin. Engine advances. ~2 s per patch.
6. `.ti3` lands in the run folder exactly as today; profile build unchanged.

**Where files land:** unchanged. `runs/runN/<target>.ti2` → `.ti3` → `.icc`.
No new locations, no new folder concepts.

## 2. What already exists — reuse, do not reinvent

| Exists | Where | Used for |
|---|---|---|
| Spot / patch-by-patch mode | `docs/design/measurement_exit_strategy.md:132-140`, `spot_ready`/`patch_read` | **The whole workflow.** We register into it; we do not build it. |
| `-x` external values | `chromiq_chartread.c:2789` (`spot_ready` fires first), `:4096` (`if (!xtern && !cq_replay_active())` — no instrument opened) | The reading path. Hardware-free seam. |
| Per-patch `.ti3` autosave | `chromiq_chartread.c:3098,3120` `cq_write_ti3_atomic()` | Data safety — already built. |
| JSON event/command protocol | `chartread_engine.py:70-83` (stdout), `measure_manager.py:709` (stdin) | Transport between GUI and engine. |
| SpectroScan geometry | `layout_engine/instruments.py:455-469` | **Structural template** — already a spot grid. |
| `TARGET_INSTRUMENT` gate | `chromiq_chartread.c:3626-3633`, `tests/test_target_instrument_gate.py` | Identity enforcement, already tested. |
| CR30 driver | `chromiq-cr30-research/src/cr30/` | Device I/O. Vendored, not rewritten. |

## 3. Why SpectroScan, not ColorMunki, is the geometry template

The survey proposed copying the ColorMunki branch. **That is the wrong base.**
ColorMunki is a *strip* layout: leader space, trailer, inter-patch spacers, rows
per strip, page-label column. A CR30 reads one spot at a time and has none of
that furniture; every strip field would be dead weight the user pays for in
paper.

SpectroScan (`:455-469`) is already the spot-grid shape — `pspa=0.0, tspa=0.0,
lcar=0.0, rpstrip=999, dorspace=False, dopglabel=False`. The CR30 branch is that
shape with its own patch size.

## 4. Geometry — and its honesty

| Field | Value | Basis |
|---|---|---|
| Aperture | 4 mm | manufacturer |
| Patch | **10.0 × 10.0 mm** (provisional) | 2.5× aperture. i1Pro uses 10 mm for a 5 mm aperture (`:370`). Basti read a ColorMunki double-density chart (10.4 × 13.0 mm patches) with a CR30 successfully — 40 patches, 0 misreads (`EXP-SPEC-001a`). |
| Spacers | none | spot device |
| Clip border | **off by default**, offerable | nothing clips onto the sheet |
| Strip furniture | none | no strips |

⚠ **The minimum patch size is NOT measured.** `EXP-MEAS-005` measured
*repeatability* (ΔE 0.215 mean, 0.340 max over six lift-and-replace reads) on a
comfortably large patch — that is not the tolerance envelope. 10 mm is a
defensible provisional value, **labelled provisional in the UI**, not a
measured minimum. Basti has deprioritised measuring it.

## 5. Colour science — stated explicitly

- Device outputs **31 values, 400–700 nm at 10 nm, percent reflectance**.
- **VERIFIED (`EXP-SPEC-001b`): those 31 values carry exactly 8 degrees of
  freedom.** Noise over 30 readings of one unmoved patch collapses to 8
  components carrying 99.99999837 % of variance, with a 2016× drop to the
  float32 floor. 31 independent channels would show a 1.07× drop there.
- **Therefore the beta writes NO `SPECTRAL_*` columns.** Writing 31 `SPEC_*`
  would tell `colprof` it has 31 independent measurements when it has 8.
- ChromIQ converts the spectrum to **XYZ under D50 / CIE 1931 2°** — the
  condition Argyll profiling expects — using the validated converter
  (`cr30/colour.py`, self-checked against published white points and reproducing
  the device's own Lab to ΔE 0.054).
- The device's own display condition is **D65/10°**; that is *its* setting and is
  irrelevant to profiling, which consumes our D50/2° XYZ.

## 6. Robustness — every edge case, and the rule that must hold in all of them

**The rule: a reading that cannot be trusted is never written to the `.ti3`.**

| Case | Behaviour |
|---|---|
| No CR30 found (USB or BLE) | Measure tab refuses to start, names both transports and what to check |
| Two CR30s present | Chooser; remembered by address. USB descriptors cannot distinguish units (no serial number) so identity is always asked of the device |
| Magnet/cap on the instrument | Reading matches the stored tile constant → **rejected, loudly**, user told to remove the cap. ⚠ unit-specific (see §9) |
| Reading identical to previous | Rejected — either no new reading or the device is gated |
| Truncated/short reply | Rejected; candidate reply scan takes the last valid one |
| Reflectance > 130 % | Rejected — the white reference is wrong, not the sample |
| Zero-run ≥ 3 bands | Rejected — truncation, not a dark patch |
| Device unplugged mid-chart | Per-patch `.ti3` autosave already protects everything read so far |
| Chart says CR30, no CR30 connected | Blocked before the engine starts |
| CR30 chart in **stock** chartread | Fatal by design (honest name). UI guard warns at chart creation |
| Old projects | Untouched — a new instrument key adds nothing to existing `.ti2`/`project.json` |

**Nothing is deleted.** No new deletion path is introduced; the run folder model
is unchanged.

## 7. i18n

Beta ships **English placeholders**. New user-facing sentences go to
`§M-PROPOSED` in `unified_measurement_management.md` **and**
`measurement_messages.CATALOGUE` with `approved=False` **and** `AWAITING_APPROVAL`
in `tests/test_message_catalogue.py` — all three in one commit or the suite
fails. **No existing `tr()` key is edited** (editing the Guided tooltip alone
fails `test_i18n.py` 24 times).

## 8. Build order

B1 identity constant + registry · B2 geometry branch · B3 the ~47 registrations ·
B4 engine-only enforcement · B5 `.ti2` chain + instruction text · B6 `-x` reading
path · B7 catalogue stubs.

## 9. Known beta limitations — documented, not hidden

1. **The magnet guard is unit-specific.** `TILE_SIGNATURE` was captured from one
   CR30; a second unit's constant differs by up to 4.69 %R (94× the tolerance),
   so the guard is inert on other hardware. The bit-identical check still fires.
   Frame offset 24 of the *button* header discriminates unit-independently but
   has no BLE equivalent — future work.
2. **Minimum patch size is provisional** (§4).
3. **Colorimetric only** — no spectral `.ti3` (§5). This is correct, not a gap.
4. **Stock ArgyllCMS `chartread` cannot read a CR30 chart** — consequence of the
   honest name, by ruling.

---

## 10. Addendum — Basti, 2026-08-28: connection loss and mandatory calibration

### 10.1 BLE connection lost mid-chart

**Ruling: reconnect automatically for as long as the measurement is running.**

Design:

1. On disconnect the run is **paused, not ended**. The Measure tab shows
   "Bluetooth connection lost — reconnecting…" with the patch count read so far.
2. Reconnect attempts run with backoff (1 s, 2 s, 4 s, then every 5 s), and the
   user always has **Stop**. We never retry silently and never retry forever
   without saying so; after 60 s the message changes to name what to check
   (device asleep, phone app connected, out of range).
3. **Nothing read so far is at risk.** `chromiq_chartread.c:3098,3120` writes the
   `.ti3` atomically after every patch, so a drop costs at most the patch in
   progress.
4. ⚠ **The stale-reading trap.** After reconnecting, the device still holds its
   last stored measurement. Reading it would silently record the pre-disconnect
   patch again, under a new patch id — the exact mislabelling class that
   `beerjongen`'s order-only pairing suffers from. The existing
   **bit-identical guard catches this**: the reading equals the previous one, so
   it is rejected and the user is asked to read the patch again. This is the
   guard earning its place a second time.
5. USB is the more robust transport for a long chart. The Measure tab says so
   when a CR30 chart is started over BLE — as information, not a block.

### 10.2 INSTRUMENT calibration before measurement — REQUIRED by ChromIQ

⚠ **Terminology, corrected by Basti 2026-08-28.** This is **instrument
calibration** — the CR30 reading its own white reference as the first step of a
measurement, exactly as an i1Pro or ColorMunki is set on its white tile before a
chart read. It is **NOT** the **Calibration run type** of #130
(`docs/design/calibration_run_type.md`), which is printer/paper linearisation.
Two unrelated concepts that share a word; the UI must never blur them.
An earlier draft of this design conflated the two, which would have invented a
parallel concept and contradicted a binding spec.

**ChromIQ already has this, and we reuse it — we do not build a second path.**

| Exists | Where |
|---|---|
| `calibration_prompt = pyqtSignal(str, str, bool)` | `workflow/measure_manager.py:200` |
| `calibration_retrying`, `calibration_done` | `:210-211` |
| `sensor_wrong_position` | `:220` |
| Automatic retry of a failed calibration (`CAL_AUTO_RETRIES`) | `:151-155`, `:485-532` |
| Instrument-supplied instruction text, with a sanity filter | `:125-147` |

That subsystem is driven today by Argyll asking for calibration over the JSON
protocol. **In `-x` mode Argyll opens no instrument, so it will never ask.** The
CR30 backend therefore raises the *same* `calibration_prompt` itself and waits
for the same acknowledgement, so a CR30 user sees the **identical dialog and
flow** an i1Pro user sees. No new dialog, no new concept, no new wording where
existing wording fits.

**The device does not insist on calibration. ChromIQ will.**

Justification is not theoretical: this project **corrupted a real unit's white
reference** by presenting a green surface to the sensor, and every subsequent
reading was plausible and wrong (paper read 156.8 %R). Nothing in the protocol
reported it. A profiling run started on a bad reference produces a bad profile
with no visible symptom.

Flow, before the first patch of a chart read (through the existing signals):

1. ChromIQ asks: **"Put the cap on the instrument, white tile facing the
   aperture, and press the instrument's button."**
2. ChromIQ reads the stored measurement and confirms it is a **flat, high,
   tile-shaped spectrum**. That is what a just-calibrated white reference reads
   by definition.
3. ChromIQ asks the user to **remove the cap**, and confirms the next reading is
   *not* the tile constant.
4. Only then does the chart read begin.

**Skip:** offered in **Manual** mode only, with a plain warning that an
uncalibrated or mis-calibrated instrument produces a profile that looks correct
and is not. Guided mode does not offer it. The choice is recorded in the run so
a later report can say whether calibration was confirmed.

### 10.3 This fixes the unit-specific magnet guard — a real gain

`docs/cr30_reports` §9.1 recorded a BLOCKER: `TILE_SIGNATURE` was captured from
one CR30, and a second unit's constant differs by up to 4.69 %R (94× the
tolerance), so the magnet guard was **inert on anyone else's hardware**.

The calibration step removes that by construction: **step 2 above captures the
connected unit's own tile constant**, at the start of every session. The magnet
guard for the rest of that session compares against *that* unit's value, not
ours.

So the guard becomes unit-independent, the hard-coded `TILE_SIGNATURE` drops to
a fallback used only when calibration was skipped, and the blocker is closed by
a feature the user asked for on ergonomic grounds. Recorded because it was not
the reason for the request.
