# Checkpoint 01: launch, inventory, A1 engine vs printtarg

Time: 2026-09-07 07:46 to 07:55. Drivers: d00_launch_inventory.py, d01_engine_vs_printtarg.py (Test Runs/drivers). Logs: Test Runs/logs/d00_*.json, d01_*.json, *.log. Everything unattended; one unexpected dialog (the "last page not full" hint) was closed with OK by the watcher and logged.

## Environment proof
- App built the way main() does (fonts, WinButtonLayoutStyle("Fusion"), CompositeAppFilter, apply_appearance), on screen, 1700x1050 window, appearance neutral, English, log hidden. Settings file = sandbox ini; presets dir = sandbox copy; projects root = /Users/Basti/ChromIQ-assessment.
- Serious log records (ERROR/CRITICAL) during both drivers: none.

## Inventory facts (OBSERVED)
- Modes: GUIDED, MANUAL; FROM PROFILE GAMUT appears only with Run type = Verification (confirmed).
- Engine instruments in Manual: i1, p3, CM, SS, CR30. Modes: i1/p3 clip|noclip ("Clip border: On / Off, more patches"), CM freehand|high|extrahigh (Density), SS and CR30 flat|hex (Patch shape).
- Engine paper list (i1): A2, 594x420, 329x483, 483x329, A3, 420x297, 11x17, Legal, A4, A4R, Letter, LetterR, 203x254, 127x178, 4x6, Custom. p3 drops 127x178 and 4x6; SS drops 594x420. Guided (i1) list drops A2 portrait, A3 portrait and 329x483 although Guided always builds with the engine (candidate F-005).
- Layout panel spin bounds: margins 0..60 mm (0.5 step), patch size 0..60 mm (auto at 0), pscale/sscale 0.5..3.0, dpi 72..1200, pages 1..20, area_cols 0..200, area_rows 0..500, area_ratio 10..1000 %, min patch 0..100 mm, max strip 0..2000 mm, offsets 0..300, clip width 10..100, custom paper 20..2000 mm, helper markers edge/len 0..60, per patch 2..12, text edges 0..30, chart/clip text size 0..72, clip image scale 1..50000 %, seed 0..2^31-1.
- Font combos (indicator, chart text, clip text) list "JetBrains Mono, Inter, Instrument Serif, <empty>, .Apple Symbols Fallback, .AppleSystemUIFont, .Times Fallback, Academy Engraved LET, ..." (candidate F-006: dot-prefixed hidden system fonts offered).
- Run bar: Profile run items "Run N (overwrite)" + "New run"; Run type Profiling | Verification.
- Demo-Full-RGB is a synthetic project: its meta.json stores an i1 Manual recipe while the run3 chart sidecar is a ColorMunki chart. Guided opened on the sidecar's instrument (CM), Manual on the stored recipe (i1). Not counted as a finding (the data is self-inconsistent), noted as a thing to try on a real project later (which module wins when sidecar and store disagree).

## A1 results (OBSERVED)
Fresh project A1-EngineVsPrinttarg, Manual, i1Pro, A4 portrait, clip on, targen -f 400.
| | engine ON (run1) | printtarg (run2) | printtarg by hand -M6 on run1's .ti1 |
|---|---|---|---|
| total / fill-up | 418 / 18 | 420 / 20 | 420 / 20 |
| per strip x strips | 22 x 19 | 21 x 20 | 21 x 20 (441 capacity) |
| pages | 1 | 1 | 1 |
| patch size | 9.23 x 9.82 mm (area-first grew it) | width 8.0 (printtarg default) | same as printtarg |
| margins L/R/T/B | 26.0 / 9.0 / 39.0 / 20.1 | 26.0 / 23.9 / 41.0 / 24.0 | n/a |
| TIFF | 2480x3508, RGB 8-bit, LZW, 300 dpi | same, dpi 300.0000036 | |
| files | channels.json (layout with 418 rects, recipe), ti1, ti2, tif, exports (colours.txt, i1profiler.txt/.pxf), meta.json, cache/new_run.json. No .cht, no PDF | same set, channels.json layout has only cht_pages/engine/locs | |
| info panel | actual + estimate (estimate wrong, F-001) | actual only, estimate shows dashes, patch size dash | |

So "same settings" is not the same chart: the engine defaults to instrument margins (T38/B19) and area-first sizing, printtarg to -m10 -M10 and its fixed 8 x 10 patch. That is by design (Manual is the user's recipe); Guided parity is tested separately.

## Findings filed
F-001 estimate/hint disagree with an area-first build (high). F-002 info frames describe a chart that is not on screen (medium). F-003 printtarg panel + per-target store diverge from the built chart after Generate (high, known family). F-004 engine toggle flips the stamp box (low).

Offline confirmation for F-001 (engine API, no GUI):
- recipe from run1 sidecar, n=400 without area_target_count: 25 x 16 = 400 at 8.33 x 8.56, per sheet 525
- same with n=418 (what the estimate feeds): 25 x 17 = 425, padding 7  (= the estimate column)
- same with area_target_count=400 (what build_chart passes): 22 x 19 = 418 at 9.21 x 9.86 (= the chart)

Files quoted for F-003 (run2): channels.json create_chart_settings printtarg-L False / printtarg-a 1.0; channels.json printtarg_fields -L True / -a 0.95; meta.json create_chart_settings -L True / -a 0.95; stamp on sheet: printtarg -ii1 -pA4 -t300 -m10 -M10 -c.

## Regression baseline so far (works, keep)
- App starts to Create Chart / GUIDED with no project, Generate enabled, no dialog.
- Project open by session restore puts the run bar on the project's current run and shows the run's chart.
- Guided restores per-run instrument/pages; per-instrument controls swap correctly (CR30 shows "Hexagon patches", CM shows Double/Triple density, i1/p3 show clip and strip-limit boxes).
- Manual engine build: targen + engine, log lines with patch count, fill-up explanation, low-contrast note, sidecars written, i1Profiler exports written; Pages greys when -f is fixed.
- Manual printtarg build: command preview matches the stamped command; no -L when the box is unticked.
- Margin inspector reads engine geometry from channels.json and judges against the i1|A4 Portrait thresholds (26/9/38/19).
- Fresh project name needs no dialog; no S4.7 or S4 window for a run with nothing to lose.
- New run: "Location being edited" advances to runs/runN before any build.

## Next
A2 instrument matrix (every engine instrument x A4 + A3/custom x portrait/landscape), then A3 layout modes, A4 margins, then a dedicated re-check of F-003's trigger.
