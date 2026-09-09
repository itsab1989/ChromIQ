# Checkpoint 03: A3 layout modes, A4 margins, thresholds, strip length

Time: 08:10 to 08:16. Drivers: d03_layout_modes_and_margins.py, d03b_thresholds_and_stripcap.py. Data: Test Runs/logs/d03_results.json, d03b_results.json, the two .log files. Shots: Screenshots/A3-layout-modes/mNN-*.png, Screenshots/A4-margins/*.png. Unattended. D03's generic watcher cancelled the Preferences dialog once (race with the driver's own timer, my tooling, not the app); D03b fixed that with an ignore list and completed the Preferences round trip. No unexpected dialog from the app, no ERROR/CRITICAL.

## A3 layout modes (i1Pro A4 clip, instrument margins on, Auto count, 1 page) - all OBSERVED
| step | mode | estimate before | built | agree |
|---|---|---|---|---|
| m01 | area-first, by width, min auto | 525 25x21 8.33x8.56 | 525 25x21 8.3x8.55 | yes |
| m02 | area-first, min width 12 | 238 17x14 12.49x13.05 | 238 17x14 | yes |
| m03 | by grid, 10 cols, rows auto | 120 12x10 17.49x18.91 | 120 | yes |
| m04 | by grid, cols auto, 20 rows | 300 20x15 11.66x10.95 | 300 | yes |
| m05 | by grid 12x18 pinned | 216 18x12 14.58x12.27 | 216 | yes |
| m06 | area-first, height 150 % | 357 17x21 8.33x13.05 | 357 | yes |
| m07 | patch-first auto | 441 21x21 8x10 | 441 | yes |
| m08 | patch-first 15x15 | 154 14x11 15x15 | 154 | yes |
| m09 | patch-first scale 2.0 | 100 10x10 16x20 | 100 | yes |
| m10 | patch-first align centre | 441; margins L29.5 R12.5 T43 B24 | same | yes |
| m11 | patch-first align bottom-right | 441; margins L33 R9 T47 B20 | same | yes |
| m12 | area-first, FIXED -f 300 | 450 (9 fill) 25x18 8.33x8.56 | 304 (4 fill) 19x16 10.92x11.51 | NO (F-001) |
| m13 | patch-first, FIXED -f 300 | 315 (11 fill) 21x15 | 315 (15 fill) 21x15 | total yes, fill-up NO (F-001 root) |
| m14 | by grid 12x18, FIXED -f 300 | 324 (9 fill) 2 pages | 306 (6 fill) 2 pages | NO (F-001) |

Note for m12: "the estimate after" the build read 325 (21 fill-up): the panel re-pads the padded total again. m13's fill-up 11 before the build = 315 minus the PREVIOUS chart's 304: the estimate feeds the on-screen total, not the designed count.

## A4 margins (own margins, instrument margins off unless stated)
| step | margins T/R/B/L | built | measured L/R/T/B | verdict line | notes |
|---|---|---|---|---|---|
| g01 | 6/6/6/6 | 682 31x22 | 26.0/6.0/7.0/7.7 (left held at 26 by clip) | hidden (F-006) | labels overflow; strip 282 > 240 ruler |
| g02 | 0/0/0/0 | 736 32x23 | 26.0/0.2/1.0/1.0 | hidden | same two notes; chart printed to the paper edge, accepted without refusal |
| g03 | 60/60/60/60 (max) | 209 19x11 | 60/60.1/61/61 | Margins: OK | |
| g04 | 20/20/20 left 5 | 540 27x20 | 26.0/20.2/21/21.1 | hidden | strip 255 > 240 |
| g05 | instrument margins back on | 525 | 26/9.1/39/20 | Margins: OK | boxes restored to 38/9/19/26 |
| g06 | A3 portrait, instr. margins (9/9/9/9) | 1376 43x32 | 26/9.2/10/10.2 | hidden | labels overflow; strip 400 > 240 |
| g07 | A3 + Max strip 200 | 1376 43x32 | same | hidden | same (F-008) |
| g08 | A3 + Don't cap | 1376 43x32 | same | hidden | same (F-008) |

D03b: A3 patch-first Max strip 0 -> 672 (21/strip); 200 -> 576 (18/strip): the cap works in patch-first.

Threshold round trip through the real Preferences dialog (D03b): T 38 -> 50 and ruler 240 -> 200 saved; panel unchanged (38), estimate unchanged (525), build unchanged (Top 39), inspector red against 50 and ruler 200 (F-007). After restoring 38 the panel read 50 (F-007). Own margins + ruler 200: note quoted 240 (F-010).

## Findings filed this checkpoint
F-006 verdict hidden by notes (medium). F-007 Preferences limit change not applied to panel/estimate/build (high). F-008 Max strip and Don't cap ignored in area-first (medium). F-009 "Use instrument margins" ticked and locked where no table exists (low). F-010 configured ruler ignored with own margins (low).

## Regression baseline additions (keep)
- All by-grid / by-width / ratio / min-width / patch-first / scale / alignment settings render exactly what the estimate says with Auto count.
- Patch area alignment moves the measured margins as expected (centre and bottom-right verified).
- Own margins 0..60 are accepted and produce a chart; 0 mm prints to the paper edge with notes but no refusal (design question, see final report).
- "Use instrument margins" off keeps the user's boxes; on restores the table values (38/9/19/26 for i1 A4 portrait).
- The Preferences dialog opens from the main window, saves on OK, and the saved table is what the inspector reads at once.
- Max strip length is honoured in patch-first.
- The ruler note names the strip length and the ruler ("400 mm exceeds the 240 mm instrument ruler").
- A layout answered by the user survives an instrument switch (SS kept area-first after i1 had set it: spec 4c behaviour).
