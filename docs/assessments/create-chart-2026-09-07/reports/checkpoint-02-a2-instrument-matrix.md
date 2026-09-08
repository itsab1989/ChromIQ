# Checkpoint 02: A2 instrument matrix (55 engine builds)

Time: 07:59 to 08:05. Driver: d02_instrument_matrix.py --full. Data: Test Runs/logs/d02_matrix.json, d02_instrument_matrix.log. Previews: Screenshots/A2-instruments/<instr>-<mode>-<paper>-preview.png (55 files). Unattended; the only dialogs were the two hexagonal heads-ups (SS hex, CR30 hex), each answered OK by the armed watcher; no unexpected dialog; no ERROR/CRITICAL in the log widget or the Python log.

Setup: project A2-Instruments, one run overwritten 55 times, Manual, engine ON, Auto patch count, Pages 1, every other control at its per-instrument default (fresh panel state, i1 clip: area-first / by patch width / instrument margins on).

## Result table (estimate BEFORE Generate vs actual AFTER; all OBSERVED)
All 55 builds succeeded, 1 page each, 8-bit RGB LZW TIFF at 300 dpi (A4 2480x3508, A4R 3508x2480, A3 3508x4961, A3R 4961x3508, 200x200 2362x2362). In all 55 the estimate's total / rows / strips / pages equalled the built chart; patch size agreed within 0.06 mm (pixel snapping). So with Auto count the prediction is exact; F-001 is confined to a FIXED patch count on an area-first recipe.

| instrument mode | A4 | A4R | A3 | A3R (420x297) | 200x200 | patch (A4) |
|---|---|---|---|---|---|---|
| i1 clip | 525 (25x21) | 544 (17x32) | 1376 (43x32) | 1248 (26x48) | 420 (20x21) | 8.3x8.55 |
| i1 noclip | 525 | 544 | 1462 (43x34) | 1248 | 420 | same |
| p3 clip | 120 (12x10) | 128 (8x16) | 336 (21x16) | 299 (13x23) | 90 (9x10) | 17.3x18.5 |
| p3 noclip | 120 | 128 | 357 (21x17) | 299 | 90 | same |
| CM hand-held | 56 (8x7) | 50 (5x10) | 120 (12x10) | 112 (8x14) | 30 (5x6) | 28.3x30.6 |
| CM high | 224 (16x14) | 200 (10x20) | 480 (24x20) | 464 (16x29) | 156 (12x13) | 14.1x14.7 |
| CM extra-high | 399 (21x19) | 351 (13x27) | 837 (31x27) | 819 (21x39) | 270 (15x18) | 10.4x10.7 |
| SS flat | 1080 (40x27) | 1092 (28x39) | 2262 (58x39) | 2280 (40x57) | 676 (26x26) | 7.03x7.03 |
| SS hex | 1242 (46x27) | 1248 (32x39) | 2574 (66x39) | 2622 (46x57) | 750 (30x25) | 6.94x8.13, pitch 6.1 |
| CR30 flat | 345 (23x15) | 368 (16x23) | 782 (34x23) | 759 (23x33) | 210 (15x14) | 12.02x12.02 |
| CR30 hex | 405 (27x15) | 396 (18x22) | 836 (38x22) | 864 (27x32) | 238 (17x14) | 12.02x13.89, pitch 10.41 |

CR30 A4 flat 345 / hex 405 matches the numbers quoted in the Patch shape help text (OBSERVED: help text is accurate here).

## Observations
- Clip Off gains nothing on A4 / A4R / Letter-class / custom papers for i1 and p3 (F-005); it gains only on A3 portrait where the left minimum is 9 mm.
- Margin verdict line was BLANK (not "Margins: OK", not a warning) for i1 A3, i1 custom, p3 A4, p3 A3, p3 A3R, p3 custom, CM custom, i1 noclip A3, p3 noclip A4/A3/A3R/custom. Code: `MarginInspectorPanel._update_status` hides the verdict whenever `text_warnings` is non-empty (strip length over the ruler, or a margin widened for row indicators), and the notes go to a separate label my snapshot did not read. To be re-read with the notes in D03 (candidate finding: a margin verdict that disappears when an unrelated note appears).
- SS and CR30: "Use instrument margins" is ticked by default and the panel says "No instrument margins set for this instrument and paper size"; the recipe shows a fallback left margin (11.1 mm SS, 14.4 mm CR30 = row-indicator band) with the other three at 6. Candidate UX finding (checkbox promises a table that does not exist for that instrument); to be confirmed with a screenshot in D03.
- Helper markers: enabled for every flat shape, greyed for SS hex and CR30 hex (#152 honoured, OBSERVED).
- Hex heads-up fired exactly once per hex pick (SS at 08:03:12, CR30 at 08:04:15), re-armed by the flat CR30 in between (OBSERVED, correct).
- i1 A3 portrait produced 43-patch strips of 399.8 mm and 1376 patches on one page; the engine offers this paper (Guided hides it); whether the ruler note appeared is checked in D03.
- Every build wrote: .channels.json (engine recipe, 1 rect per patch), .ti1, .ti2, .tif, exports/-colours.txt, -i1profiler.txt, -i1profiler.pxf, meta.json, cache/new_run.json. No .cht for any instrument including SS (A13 will check the scanner path separately). No PDF (export_pdf off).

## Regression baseline additions
- Every engine instrument x mode builds on A4, A4R, A3, A3R and a 200x200 custom sheet without error.
- Auto patch count: estimate == build for all 55 combos.
- TIFF dpi and bit depth follow the panel (300 dpi, 8-bit) on every paper.
- The SS list omits 594x420 (A2 landscape) as documented; p3 omits 127x178 and 4x6.
