<!-- Regenerate the whole set with:
       python scripts/make_scan_align_demos.py            <outdir>   # 01-26
       python scripts/make_scan_align_demos_symmetric.py  <outdir>   # the symmetric charts
       python scripts/make_scan_align_demos_ambiguous.py  <outdir>   # 27-31
       python scripts/make_scan_align_demos_photos.py     <outdir>   # 32-38
     The seed is fixed, so the same bytes come back every time. -->

# Auto align — the challenge set

38 cases built to **expose shortcomings**, not to demonstrate success. Every
folder is self-contained and self-describing:

| file | what it is |
|---|---|
| `scan.tif` | the image the tool is given |
| `chart.cht` | the chart's patch geometry (ArgyllCMS format, written by ChromIQ's own `workflow/layout_engine/cht_writer.py`) |
| `chart.cie` | the reference values |
| `truth.json` | ground-truth corners of the patch area in `scan.tif` |
| `NOTE.txt` | what this case is, how it was made, and what SHOULD happen |
| `colors.json` | the colours actually painted, where a correct read is defined |

## The chart

A 20 x 26 grid of 7 mm patches on A4 at 300 dpi, 520 patches, laid out the way
the ChromIQ engine lays one out: **patches edge to edge**
(`inter_patch_mm = 0.0`), a printed title line above and a strip-label rule
below. Colours are a coarse RGB cube walk with a neutral every 17th patch, so
neighbours are sometimes identical — real charts have that too.

## Provenance and licence

Everything here is **generated**, by `scripts/make_scan_align_demos.py` and its three companions beside
this one. Nothing is scanned, photographed, downloaded or copied from any other
source; there is no third-party material and no personal data of any kind. The
generator is deterministic (fixed seeds), so the whole set can be rebuilt
byte-for-byte:

    python exp/make_demo.py <output folder>

It needs only Pillow, numpy and ChromIQ's own `cht_writer`.

## Cases 27-31: which way up is the sheet?

| case | size | what it attacks |
|---|---|---|
| 27-square-chart | 15 MB | a SQUARE chart: geometry cannot tell 0 from 90, only colour can |
| 28-symmetric-180 | 15 MB | colours symmetric under a half turn — **no correct answer exists** |
| 29-symmetric-4-fold | 15 MB | symmetric under all four turns — four answers, three wrong |
| 30-symmetric-180-turned | 15 MB | case 28 physically upside down — must refuse the same way |
| 31-square-chart-turned-90 | 15 MB | the square chart a quarter turn on the glass |

28, 29 and 30 have no right answer. Anything except a refusal is a guess, and
a guess reads every patch as another patch.

## Cases 32-38: PHOTOGRAPHS, which are a different problem

Each of these also carries `region.json`: the rough rectangle a user would drag
round the chart (its bounding box grown 12 % and jittered), for measuring
whether narrowing the search rescues the case.

| case | size | what it attacks |
|---|---|---|
| 32-photo-handheld | 18 MB | keystone + barrel + shake + lighting gradient |
| 33-photo-cluttered-desk | 40 MB | sixteen other rectangles round the sheet |
| 34-photo-half-in-shadow | 55 MB | one side 60 % down, softly graded |
| 35-photo-steep-angle | 50 MB | 10 % keystone — photographed from well off to one side |
| 36-photo-second-colour-grid | 48 MB | a SECOND grid of colour patches in the frame |
| 37-photo-chart-small-in-frame | 4.7 MB | the chart about a fifth of the frame, with clutter |
| 38-photo-careful | 19 MB | the best a phone on a tripod would do |

## Sizes

1.0 GB in total for all 38. One case dominates: `14-dpi-1200` is 254 MB on its own
(9920 x 14032). Without it the set is 495 MB; without the three resolution
cases it is 431 MB.

| case | size | what it attacks |
|---|---|---|
| 01-baseline-300dpi | 17 MB | the control, not a challenge |
| 02-rotated-90 | 16 MB | sheet a quarter turn on the glass |
| 03-rotated-180 | 17 MB | upside down — the most dangerous mistake available |
| 04-rotated-270 | 16 MB | the other quarter turn |
| 05-skew-2deg | 18 MB | the everyday case: laid down slightly crooked |
| 06-skew-5deg | 18 MB | visibly crooked |
| 07-skew-0.4deg | 18 MB | barely crooked, which is the hardest for a symmetric chart |
| 08-perspective-2pct | 17 MB | mild keystone |
| 09-perspective-6pct | 16 MB | keystone meant to break it |
| 10-crop-loses-right-edge | 13 MB | a column cut off mid-patch |
| 11-crop-loses-bottom | 13 MB | a row cut off mid-patch |
| 12-dpi-150 | 4.3 MB | below any sensible scan resolution |
| 13-dpi-600 | 64 MB | ChromIQ's recommended resolution |
| 14-dpi-1200 | 254 MB | ChromIQ's preferred resolution |
| 15-sixteen-bit | 50 MB | 16 bits per channel — the path that once nulled A4 scans outright |
| 16-colour-cast | 20 MB | a warm lamp |
| 17-blown-highlight | 16 MB | light patches clipped to paper white |
| 18-dark-scan | 21 MB | badly under-exposed |
| 19-dust-and-hairs | 17 MB | 400 specks and a dozen hairs, some across patch borders |
| 20-heavy-noise | 22 MB | four times a real scan's noise |
| 21-photographed | 19 MB | phone camera: barrel distortion, lighting gradient, shake |
| 22-photographed-mild | 19 MB | the same within reason |
| 23-wrong-chart | 16 MB | a different chart handed in with this reference |
| 24-two-charts-one-sheet | 14 MB | two copies of the chart on one sheet |
| 25-damaged-corner | 17 MB | a torn corner of the patch block |
| 26-fold-line | 17 MB | a crease straight through a row |

## Running the whole set

    python exp/run_module.py <folder containing the cases>

prints one JSON line per case and writes `module-results.json`. It reads each
accepted placement back through the REAL `scanin -F`, twice — once at the
ground-truth corners and once at the corners auto align chose — and compares the
two `.ti3` files, so the verdict measures REGISTRATION and not the colour
degradation the case applies.
