# Reading charts with a CR30 colorimeter — feasibility (2026-08-20)

Sources, both read as code rather than summary:

- itohi.com, *Reverse engineering CR30* — the protocol write-up.
- `github.com/itohio/color-science` — MIT, 5 commits, 2 stars, last push
  2025-11-26, described by its author as "experiments". The `cr30reader/`
  package is Python: `protocol/`, `driver/`, `color_science/`, `argyll/`.

**Nobody here has a CR30.** Everything below is from source and from the
captured data in `reverse-engineer-c30/protocol.ipynb`; none of it is
hardware-verified, and no verdict should be treated as proven until it is.

## What the device actually is

| | |
|---|---|
| Transport | USB serial, 60-byte packets, `AA`/`BB` start byte + checksum. Their captures show `COM3 at 115200 baud` (one at 9600) |
| Commands | `AA 0A 00` name · `BB 10 00` black cal · `BB 11 00` white cal · `BB 01 00` trigger · `BB 01 10..13` fetch spectral chunks |
| Data | 31 little-endian floats = 400–700 nm at 10 nm (`protocol.py:_parse_spd_data`) |
| Scale | percent reflectance — a near-white patch reads 55–94 in their captures |
| Geometry / illuminant | D65-ish white LEDs; the author says the spectrum "does not quite" match D65. Aperture and geometry are **not documented anywhere** |
| Calibration | white and black tile, cap detected by a hall sensor |
| Reading | **single spot only**, ~1 s per reading. No strip, no XY |
| Author's own caveat | "ΔE for some colors (especially dark) is somewhat high" |

## What ChromIQ already has (the reason this is even close)

1. **The whole ArgyllCMS instrument driver stack is vendored and built here** —
   `native/instlib/` carries `icoms.c`, `inst.c`, `insttypes.c` and the drivers
   (`i1pro.c`, `munki.c`, `dtp41.c`, `ss.c`, …). `icoms.h:89` has
   `icomt_serial`, `icoms.h:322` has `baud_115200`: the exact transport a CR30
   needs already exists.
2. **A chart-reading engine with a spot mode.** `native/chartread_helper/` is
   ChromIQ's fork of `chartread.c`; `chromiq_chartread.c:887` has
   `rmode 0 = spot`, and `:600` emits `spot_ready` events for engine-driven
   patch-by-patch reading.
3. **A clean process boundary.** `workflow/chartread_engine.py` decodes a
   **line-based JSON event/command protocol** on stdout/stdin. The Measure tab
   talks to *that*, not to Argyll.
4. **The instrument travels in the chart.** `workflow/layout_engine/instruments.py:26`
   maps the engine's instrument code to a CGATS name,
   `workflow/layout_engine/ti2_writer.py:80` stamps `TARGET_INSTRUMENT` into the
   `.ti2`, and `ui/ti2_loader.py:33` reads it back. Argyll carries the same
   keyword into the `.ti3`.
5. **A precedent for a device Argyll cannot drive**: `EXTERNAL_INSTRUMENTS`
   (i1iSis, measured in i1Profiler and imported).

## Verdict

**Reading is feasible. Doing it honestly is the hard part, and it is not a
driver problem.**

Point 3 is the finding that matters: because the engine boundary is a JSON
line protocol between processes, a CR30 backend does **not** have to be a C
driver inside Argyll. A separate process that speaks the same events reuses the
entire Measure tab — live preview, sounds, progress, the measurement-ending
rules of `unified_measurement_management.md` — unchanged.

### Two architectures

**A — add a CR30 driver to the vendored Argyll instlib (C).**
Registration surface is ~5 files (`insttypes.c/.h`, `insttypeinst.h`, `inst.c/.h`)
plus a new driver of roughly `dtp41.c` size. Everything downstream then works,
including stock Argyll tools.
*Cost:* `native/instlib/PROVENANCE.md` guarantees the vendored copy is
**unmodified**; this ends that, and every Argyll bump must re-apply the patch.
It is GPLv2-or-later code, so the fork must be published. Their MIT Python is a
reference, not reusable code.

**B — a Python CR30 backend process speaking the engine's JSON protocol
(recommended).**
No fork of vendored Argyll, no licence entanglement, and the Measure UI is
reused rather than rebuilt. `pyserial` is a new dependency (ChromIQ currently
has none for device I/O). It only ever serves the CR30; stock chartread stays
the path for every supported instrument.

## Where it breaks — the gaps that decide whether this ships

**G1. 400–700 nm is not enough spectrum, and ChromIQ already depends on the
rest.** Argyll's instruments give 380–730 nm (`tests/test_ti2_loader.py:206`
pins `SPECTRAL_BANDS "36"`, `SPECTRAL_START_NM "380.0"`). ChromIQ *uses* that:
`workflow/engine_builder.py:133` turns on FWA compensation through Argyll's
`spec2cie`, and `data/parameters.yaml:1470` offers `D50M2 (D50 + UV filter)`.
FWA needs the near-UV the CR30 cannot see. **Most inkjet papers contain optical
brighteners**, so paper white — the anchor of the whole profile — is exactly
where this device is weakest, and the correction for it is unavailable.

**G2. The "31 bands" are probably not 31 measurements.** The article *estimates*
an OSRAM AS7341/AS7343 — an 11-channel sensor. If that is right, the 31 values
are reconstructed in firmware. Writing them into a `.ti3` as `SPECTRAL_NM_400…`
tells `colprof` it has 31 independent measurements, and it will weight them as
such. That is a fabricated measurement, and principle 8 forbids it. The honest
form is an **XYZ-only `.ti3`** — which then loses the illuminant and FWA
options above. Either way the user must be told which they have.

**G3. Their `.ti3` writer cannot be used.** `argyll/argyll_parser.py:320`
hard-codes `NUMBER_OF_SETS 1`, omits `COLOR_REP`, and writes **no device RGB
columns at all** — only XYZ and Lab. `colprof` cannot build a printer profile
from that. ChromIQ would write its own, pairing each reading with the device
values from the `.ti2`.

**G4. Spot-only meets a UI built for strips.** 154 patches means 154 placements
at ~1 s plus positioning; the ColorMunki reads that in one pass. The layout
engine, the patch-capacity DB (`data/patch_db.py`) and the reading-speed
guidance all assume a strip instrument. A CR30 chart is a **spot grid**, and
patch size must be at least the aperture — **which is undocumented**. Until it
is measured, no safe default patch size can be chosen, which is precisely the
"good defaults" problem you anticipated.

**G5. Stamping an unknown `TARGET_INSTRUMENT` can break other paths.** Argyll
has no CR30 name. A chart stamped e.g. `"Itohi CR30"` is not in
`KNOWN_INSTRUMENTS` (`ui/ti2_loader.py:33`), and a user who later measures that
sheet with a real spectro goes through stock chartread with an instrument
string nothing recognises. Any new value must be added to `ti2_loader`,
`patch_db.INSTRUMENT_LABELS`, `layout_engine/instruments.py` and the paper
exclusions **together**, and the failure mode when the chart and the instrument
disagree must be a clear message, not a silent mismatch.

**G6. Data safety.** `chartread` writes its `.ti3` only on a clean exit, which
is why the engine added per-strip autosave. A Python backend must match that
rule from the first version: a disconnect at patch 150 of 154 must not lose 150
readings. Nothing is deleted; a re-read archives.

**G7. macOS and Linux are unproven.** Every capture in that repo is `COM3` —
Windows. Cheap serial devices of this class usually carry a CH340 or CP210x
bridge, which on macOS needs a kernel extension. `core/usb_driver_installer.py`
is Windows-only and installs *WinUSB for Argyll's own devices*; it does not
cover a CDC serial bridge. ChromIQ ships mac, Windows and Linux — one platform
working is not support.

**G8. Maturity.** Five commits, two stars, one author, "experiments", no
released version, no CI. Their `measure()` retries nothing and the chunk loop
`break`s on a missing chunk, leaving a short SPD that `_parse_spd_data` then
silently drops (`protocol.py`). Anything we ship must own that robustness.

## Plan, if it goes ahead

- **P1** Decide the identity: the instrument code, the `TARGET_INSTRUMENT`
  string, the display name, and every table that must learn it (G5).
- **P2** A `.ti3` writing decision, in the open: XYZ-only (honest, limited) or
  spectral (fuller, only if G2 resolves in its favour).
- **P3** The backend process + protocol conformance tests, driven by a
  **replay fixture** — the same technique `tests/test_chartread_hex_simulation.py`
  already uses, so most of this is testable with no hardware.
- **P4** Measure-tab work for spot grids: what "strip" means when there is none.
- **P5** Chart creation last, once the aperture is known (G4).

## Open questions

1. Do you have, or can you get, a CR30? Nothing here is provable without one.
2. What is the aperture diameter and the measuring geometry (45/0, d/8)?
3. Is the SPD reflectance relative to the white tile — and is white 100.0?
4. Is the sensor really an 11-channel AS7341 (G2)? That single fact decides
   whether we may write spectral data at all.
5. XYZ-only or spectral `.ti3` (G2/P2)?
6. Architecture A (fork Argyll's instlib) or B (Python backend)?
7. Which platforms must work at release — is Windows-only acceptable to start?
8. Is this for profiling, or for verification of small charts only? The answer
   changes the whole UI design (G4).
