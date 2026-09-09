# Nelson Lau's 10x15 / 13x18 i1Pro presets — MEASURED FACTS
Session started 2026-09-08. Everything below is measured, not assumed.
Working copies of the unzipped bundles:
  /private/tmp/claude-502/-Users-Basti-develop-ChromIQ/c599dbdd-0819-4163-be45-a4a20e7d4643/scratchpad/nelson/{600p,648p}

## What arrived
Two zips on the Desktop, each a complete prebuilt-files bundle (kind 1 in
docs/dev_builtin_presets.md): `<stem>.ti1` + `<stem>.ti2` + `<stem>_NN.tif`.
No recipe.json, no channels.json.

| | 600p | 648p |
|---|---|---|
| stem | `i1Pro-600p` | `i1Pro-648p` |
| patches | 600 | 648 |
| pages | 4 | 3 |
| STEPS_IN_PASS | 15 | 18 |
| PASSES_IN_STRIPS2 | 10,10,10,10 | 12,12,12 |
| TIFF px | 1417x2126 | 1843x2551 |
| TIFF dpi / unit | 360 / INCH | 360 / INCH |
| sheet | **100.0 x 150.0 mm** | **130.0 x 180.0 mm** |
| bits / compression | 16-bit / ADOBE_DEFLATE | 16-bit / ADOBE_DEFLATE |
| .ti1 ORIGINATOR | ChromIQ | ChromIQ |
| .ti2 ORIGINATOR | Argyll printtarg | Argyll printtarg |
| .ti2 TARGET_INSTRUMENT | GretagMacbeth i1 Pro | GretagMacbeth i1 Pro |
| .ti2 RANDOM_START | 397 | 518 |
| .ti2 PAPER_SIZE | **120.0x195.0** | **135.0x225.0** |

## VERIFICATION 1 — the render agrees with the .ti2, patch by patch
`workflow.layout_from_render.derive_layout_from_render` (the colour-verified,
correct-or-absent derivation `scripts/derive_prebuilt_geometry.py` uses) PASSES
on BOTH bundles: 600 and 648 patches located and colour-matched against the
bundle's own .ti2. So the sheets are faithful to their .ti2. This is the same
gate that once rejected the i1Pro/A4 tc924 bundle.

## VERIFICATION 2 — measured sheet geometry (mm, at 360 dpi)
| | 600p | 648p |
|---|---|---|
| patch width (across strip) | 7.60 | 8.00 |
| patch length (along strip) | 7.27 | 7.62 |
| inter-patch spacer | 0.564 | 0.564 |
| along-strip pitch | 7.832 | 8.184 |
| rows touch (gutter) | 0.000 | 0.000 |
| patches per strip | 15 | 18 |
| strips per page | 10 | 12 |
| strip length | 116.9 | 146.7 |
| leader (sheet top -> 1st patch) | 20.60 | 20.46 |
| trailer (last patch -> sheet bottom) | 12.63 | 12.22 |

## VERIFICATION 3 — spacers are contrast-chosen black/white
Sampled every gap on strips A and B of page 1 on both charts: the spacer is
pure black next to a light patch and pure white next to a dark one, i.e. real
printtarg B&W (`-b`) spacer logic, not a constant rule. chartread's strip
segmentation has the transitions it needs.

## Argyll ground truth (target/printtarg.c v3.5.0, lines 2137-2200)
i1Pro, 5 mm aperture branch:
  plen = pscale * 10.00   /* Patch min length - total 10 mm (absolute limit is 10) */
  pspa = pscale * sscale * 1.00
  pwid = pscale * 8.0     /* Patch min width (absolute limit is 7) */
  lcar = 10.0 ; tspa = 10.0 ; rrsp = pscale * 8.0 ; dorspace = 0
  mxrowl = 260 - lcar - tspa = 240 mm   (the i1 ruler)
Both new charts are BELOW Argyll's stated absolute minimum patch length of
10 mm (7.27 / 7.62 mm) and below the 1 mm nominal spacer (0.564 mm).
Strip lengths (116.9 / 146.7 mm) are well inside the 240 mm ruler.

## THE PRECEDENT THAT SETTLES IT — the shipped charts are already there
Measured the same way on every bundle already in `assets/charts/pharmacist/rgb`:

| bundle | plen | gap | pwid |
|---|---|---|---|
| i1pro/letter/extended1944 | 7.48 | 0.85 | 7.49 |
| i1pro/a4/tc918eg | 7.69 | 0.92 | 8.33 |
| i1pro/letter/tc918eg | 7.69 | 0.92 | 8.33 |
| i1pro/a4/extended1944 | 7.76 | 0.85 | 7.49 |
| i1pro/a4/abw1110 | 9.03 | 1.06 | 7.60 |
| **NEW 600p** | **7.27** | **0.564** | **7.60** |
| **NEW 648p** | **7.62** | **0.564** | **8.00** |

So sub-10 mm patch length is Nelson's established house style and has shipped
since 4.0. The new charts sit inside that family on patch length. The ONE
genuinely new outlier is the SPACER: 0.564 mm, 34 % below the smallest that has
ever shipped (0.85 mm) and 47 % below abw1110's 1.06 mm. At 360 dpi that is 8
pixels. Flag it; do not treat it as a blocker on our own authority.

## The PAPER_SIZE mismatch is precedent too, NOT a new defect
Every shipped pharmacist bundle already carries a PAPER_SIZE that disagrees
with its own rendered sheet:
  i1pro/a4/tc918eg      PAPER_SIZE "192.0x360.0"  render 210x297
  i1pro/a4/extended1944 PAPER_SIZE "220.0x320.0"  render 210x297
  colormunki/a3/tc924   PAPER_SIZE "475.0x305.0"  render 420x297
  colormunki/a4/abw702  PAPER_SIZE "292.0x210.0"  render 297x210
  i1pro/a4/abw1110      PAPER_SIZE "210.0x297.0"  render 210x297  (the only match)
The .ti2 does NOT encode patch pixel positions - only SAMPLE_LOC, STEPS_IN_PASS
and PASSES_IN_STRIPS2 - so chartread is unaffected. PAPER_SIZE is read by
`workflow/ti2_relayout.py:193` (maps it to a printtarg `-p`) and nowhere else
that touches measurement.

## TIFF format matches what ChromIQ already ships
16-bit, ADOBE_DEFLATE, 360 dpi, RESUNIT.INCH, RGB, contiguous - byte-for-byte
the same shape as `i1pro/a4/extended1944_01.tif`. No new decoder path.

## VERIFICATION 4 — the .ti1 and the .ti2 are the same patch set
Row-for-row, SAMPLE_ID order preserved. 0 SAMPLE_ID mismatches on either
bundle; max |dRGB| 0.00076 on a 0..100 scale (a formatting rounding artefact:
the .ti1 prints 4 decimals, the .ti2 7 significant digits); max |dXYZ| exactly
0. Device values are inside 0..100 on both.

## VERIFICATION 5 — the strip index is complete and unique
| | 600p | 648p |
|---|---|---|
| SAMPLE_LOC unique | 600/600 | 648/648 |
| strip letters | 40 (A..AN) | 36 (A..AJ) |
| every strip holds exactly 1..STEPS_IN_PASS | yes | yes |
| STEPS x sum(PASSES_IN_STRIPS2) | 15 x 40 = 600 | 18 x 36 = 648 |
No padding patch is needed: both charts fill every slot exactly, so the last
page has no short final strip.
Duplicate device values: exactly 2 white (100,100,100) and 2 black (0,0,0) on
each, matching the .ti1 header's WHITE_COLOR_PATCHES 2 / BLACK_COLOR_PATCHES 2.
Both .ti2 files carry RANDOM_START (397 / 518), so the randomisation gate that
auto-tags fixed-order charts does not apply.

## Where the wrong PAPER_SIZE actually surfaces (measured)
`ChartSpec.from_ti2` -> `workflow.ti2_relayout.paper_to_flag`:
  new 600p -> '120x195'   new 648p -> '135x225'
  shipped i1pro/a4/tc918eg -> '192x360'   shipped i1pro/a4/abw1110 -> 'A4'
`_stamp_chart_meta` writes that into the run's `meta.json` as `meta.paper` for
every prebuilt preset (the no-params branch). So the run records a sheet size
the chart was never printed on. Already true of 8 of the 9 shipped bundles.
Correcting the keyword in the bundled .ti2 to the sheet the render really is
(100.0x150.0 / 130.0x180.0) changes no patch data and cannot affect chartread.

## Bundle size added
1.4 MB for both presets (11 files).

## Built-in preset count today: 150 (9 prebuilt + 141 ti1-based)
ColorMunki 49, i1Pro 45, i1Pro 3 Plus 24, CR30 20, Scanner 6, Red River 6.
`docs/index.html` says "150 ready-made chart presets" at line 292 and line 652.
Adding these two makes it 152.

## VERIFICATION 6 — what Argyll's own i1 layout would do with the same patches
`printtarg -v -ii1 -p100x150 -t300 -a0.95 -m10 -M10 -L` on the bundled 600-patch
.ti1, real Argyll 3.5.0:
    Paper chosen is custom 100.0 x 150.0 mm
    Test patches per row = 10 ; Rows per page = 9 ; patches per page = 90
    Total pages needed = 7
So Argyll fits 90 patches on a 10x15 card; Nelson fits 150. His sheet is 67 %
denser, bought with a 7.27 mm patch length (Argyll's floor is 10 mm) and a
0.564 mm spacer (Argyll's is 1 mm). That is the whole trade, stated plainly.
Consequence for the override path: unlock the layout panel, re-generate, and
the same colours come back as SEVEN sheets, not four. Correct, but a surprise
worth a word in the UI.

## `query_patches` has no row for either sheet (confirmed)
  100x150 -> None    130x180 -> None    4x6 -> 100    127x178 -> 169    A4 -> 504

## VERIFICATION 7 — the randomisation gate (the app's own `analyze_randomisation`)
  photocard600  safe=True  40 strips  min_symmetry 53.03  min_confusability 45.85
  photocard648  safe=True  36 strips  min_symmetry 63.83  min_confusability 46.53
Both "Layout is well mixed."
UNRELATED FINDING, PRE-EXISTING, worth its own look: the SHIPPED
`colormunki/a4/abw702` bundle reports safe=False on the same gate
("Two strips look almost identical, so chartread can't reliably tell which
strip is which", min_symmetry 42.9, min_confusability 35.9). Every other
shipped bundle passes. Not this task's business; do not fold it in silently.

## VERIFICATION 8 — ink reaches the sheet edge, so these sheets want BORDERLESS
Non-white bounding box per page, measured at 360 dpi:
  600p pages 1-4   top 2.96-3.88  bottom 4.02-5.01  left 1.34-1.62  right 1.34-1.62 mm
  648p pages 1-3   top 1.20-1.55  bottom 0.99-1.55  left 1.83-2.19  right 2.05-2.26 mm
  shipped A4 extended1944 (for scale)  top 16.58  bottom 12.77  left 2.26  right 4.09 mm
The PATCHES are safe either way (648p: left 26.95, right 6.95, top 20.46,
bottom 12.08 mm), so a bordered print stays measurable; what a ~3.4 mm
unprintable edge would trim is the crop marks and part of the identification
text. Nelson prints the instruction on the sheet itself ("print with borderless
setting / NO expansion, retain size, color management: OFF"). ChromIQ should
say it too, at the point where the chart is chosen.

## FINDING (mine) — the chart and the app give OPPOSITE printing advice
Nelson prints on every sheet: *"print with borderless setting / NO expansion,
retain size, color management: OFF"*.
ChromIQ's Print tab, `ui/tabs/tab_print.py:1604 _confirm_borderless`, raises a
warning dialog the moment a borderless option is selected:
  "Borderless printing enlarges the page by a few percent ... A profiling chart
   must print at exactly 100%: enlarging it shifts every patch ... Switch
   borderless off and print with borders instead, the chart's white margins are
   made for that."
Both are defensible and they are about different things: ChromIQ warns about
borderless WITH the driver's expansion, Nelson asks for borderless WITHOUT it
(Epson/Canon drivers expose an expansion slider that can be set to none).
But "the chart's white margins are made for that" is not true of THESE two
sheets: their ink stops 1.0 to 1.6 mm from the edge (VERIFICATION 8), and the
last patch row ends 12.1 / 12.6 mm from the bottom and 7.0 / 4.9 mm from the
right, which some printers' unprintable bottom margin would reach.
This wants a ruling from Basti (and a word to Nelson), not a unilateral rewrite
of a shipped, translated warning. For 4.2.1 I propose only an added line in the
preset's own tooltip that does not contradict the Print tab.

## ⛔ A PRINTED TYPO ON ALL THREE PAGES OF THE 13x18 CHART
The header band of `photocard648_01/02/03.tif` reads:
    "... photo card -print wiith borderless setting / NO expansion, ..."
"wiith" for "with", and no space after the hyphen. Read off the rendered band
at 2x on each of the three pages; confirmed on all three.
The 10x15 chart's header is CLEAN: "... photo card - print with borderless
setting / NO expansion, ...".
It is baked into the raster, so nothing on our side can fix it. Only a
regenerated 648p bundle from Nelson fixes it. It goes on paper, under the
ChromIQ logo, on a chart credited to him.
