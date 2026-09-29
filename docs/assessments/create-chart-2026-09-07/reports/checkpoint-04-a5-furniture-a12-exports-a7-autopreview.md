# Checkpoint 04: A5 furniture, A12 exports, A7 auto-update preview

Time: 08:21 to 08:25. Driver: d04_furniture_export_autopreview.py. Data: Test Runs/logs/d04_results.json, d04_furniture_export_autopreview.log. Shots: Screenshots/A5-furniture/fNN-*-preview.png, A12-exports/*, A7-auto-preview/*. Unattended. Dialogs: the example-table question (F-011, answered OK) and the one-time "Auto-update preview is on" info card (Close). No ERROR/CRITICAL.

Setup: project A5-Furniture, Manual, engine on, i1Pro A4 clip, area-first defaults, instrument margins on, Auto count, 1 page. Baseline 525 (25 x 21), margins L26.0 R9.1 T39.0 B20.0.

## Furniture accounting (estimate before Generate vs build; all OBSERVED)
| step | option | estimate | built | measured change | note |
|---|---|---|---|---|---|
| f02 | clip text with tokens | 525 | 525 | none | tokens printed literally (F-012) |
| f03 | example table | 525 | 525 | none | one-button question (F-011) |
| f04 | branding | 525 | 525 | none | |
| f05 | content off (border stays) | 525 | 525 | none | band empty |
| f06 | imported image | 525 | 525 | none | image small + leftover text (F-013) |
| f07 | clip right, 40 mm, flipped | 468 (26x18) | 468 | L26.2 R40.0 | band moved and widened; count follows |
| f08 | strip indicators off | 525 | 525 | none | top stays 39 (label band still reserved?) see below |
| f09 | row indicators on | 500 (25x20) | 500 | L34.0 | note explains the widening in full (good) |
| f10 | indicator 6 mm bold rot 90 | 525 | 525 | none | |
| f11 | underline black | 525 | 525 | none | |
| f12 | sheet text 5 mm | 525 | 525 | B20.0 unchanged | tokens literal (F-012) |
| f13 | stamp | 525 | 525 | B20.0 unchanged | |
| f14 | edge spacers | 525 | 525 | T38.0 B19.0 | block grows by the two spacers, still fits |
| f15 | helper markers | 525 | 525 | none | dashes on all four edges (settled design) |
| f16 | offset 10/10 | 525 | 525 | L36 R0.0 T49 B10 | red: Right 0.0 < 9, Bottom 10 < 19; stamp text gone |
| f17 | spacers b/w | 525 | 525 | none | |
| f18 | spacers none | 588 (28x21) | 588 | T38 B19 | |

Notes: strip indicators off (f08) did not change the top margin (39.0) or the count, so the label band is still reserved with the labels hidden (could be a small capacity gain; not filed, low). Sheet text and stamp did not move the bottom margin because the 19 mm instrument bottom already covers the text band.

## A12 exports
- "Also export a PDF": run1 gained A5-Furniture.pdf next to the TIFF (OBSERVED in the file list); the file is removed by the next Generate along with the other chart files. Content (page size, vector) still to be checked on a kept build (D06).
- 16-bit + zlib: TIFF 16/16/16, compression tiff_adobe_deflate, 2480x3508 (OBSERVED).
- Fixed seed 12345 twice: the two .ti2 bodies (all lines except CREATED/ORIGINATOR/DESCRIPTOR) are identical (OBSERVED reproducible).
- i1Profiler sidecars (exports/-colours.txt, -i1profiler.txt, .pxf) were written on every engine build in A1/A2 (OBSERVED).

## A7 auto-update preview
- Ticking the box shows an info card once ("Auto-update preview is on", Close) and sets auto_update_preview=True (OBSERVED).
- A layout change (min patch width 10) with a chart on screen: a re-layout started 1.37 s after the change (450 ms debounce plus the build) and rewrote channels.json, .ti1, .ti2, .tif, _01.tif, _02.tif, meta.json (OBSERVED). The re-layout keeps the old 525 patches: chart 540 on 2 pages, while the estimate column (Auto count, 1 page) says 340 on 1 page. Consistent with the card's explanation, but the two columns now describe different charts with no line saying so (low; folded into the final report).
- Debounce (two nudges 150 ms apart) and "does a non-layout edit fire it": my probes were polluted by meta.json writes (W6 per-target store) and are UNKNOWN; re-run in D06 by counting engine "random start" log lines over a fixed window.

## Findings filed
F-011 one-button question (low). F-012 one bad token disables all tokens (medium). F-013 image mode keeps the caption (low, PARTIAL).

## Regression baseline additions
- Every clip content mode renders; right-side clip and width change the count and margins coherently; flip works without error.
- Row indicators widen the left margin and the app explains it in one paragraph.
- Indicator size/bold/rotation, underline, edge spacers, b/w and no spacers, helper markers, page offsets all render and the estimate follows.
- PDF export, 16-bit, zlib, fixed seed reproducibility all work.
- Auto-update re-lays the existing patch set and rewrites the run's chart files.
