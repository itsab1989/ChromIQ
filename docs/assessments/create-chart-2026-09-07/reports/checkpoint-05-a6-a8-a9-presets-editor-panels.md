# Checkpoint 05: A6 info frames, A8 presets, A9 patch-set editor, A11 preflight, F-003 re-check

Time: 08:27 to 08:53. Drivers: d05_presets_editor_panels.py (aborted by me at 08:40 after my own watcher mis-handled the editor's "Apply or save this patch set" box; nothing was clicked by a human, the process was killed), d05b_presets_editor_recheck.py (complete). Data: d05_presets_editor_panels.log, d05b_results.json, d05b_presets_editor_recheck.log. Shots: Screenshots/A6-info-panels, A8-presets, A9-patch-editor, A7-auto-preview.

Driver lessons recorded so the next agent does not repeat them: the Save Preset dialog defaults all three boxes ON (descriptive prefix, generate immediately, attach .ti1); a preset must be picked through the combo's `activated` signal, `setCurrentIndex` alone does nothing; the editor's Apply opens a second modal; results must be saved after every block.

## A6 info frames (OBSERVED)
- Run switch in A1-EngineVsPrinttarg: run1 (engine) shows actual + estimate (estimate still the F-001 425); run2 (printtarg) shows actual only, estimate column dashes, patch size dash. Both correct for their kind.
- A run folder that never received a build ("New run") is not listed after reopening the project (only run1, run2 appear): a New run is created on the first build, not on selection (baseline).
- Reflected external chart (the signal Print/Measure emit after Load .ti2, fed with A2-Instruments run1): an info card "Loaded chart is now shown in Create Chart" (OK) appears; the frames show the loaded chart's numbers (238, 17x14 hexagons, 12.02x13.89); estimate equals actual; the engine panel is disabled; Generate stays enabled and, when pressed, shows "This chart is loaded from elsewhere" with Close (no build). Baseline.
- Typing a different project name while a project is open and pressing Generate raises "Rename Printer Profile" with four choices (Rename the existing / Create and keep / Create and delete / Cancel). Baseline (S4.7 family).

## A8 presets (OBSERVED)
- Save (prefix off): AssessPresetA.json + AssessPresetA.ti1 written to the presets folder; combo lists it and selects it. With the default boxes on, the saved name becomes "i1Pro-A4-525p-3pages-Landscape-AssessPresetA" (the prefix is derived from the on-screen chart: 525 patches / 3 pages, while the recipe was A4 landscape 12 mm patches; PARTIAL, not filed).
- Reload after changing seven values: every key restored (diff {}); with "Generate immediately" on it rebuilt (532 patches, 2 pages).
- Overwrite: a box "A preset named X already exists. Overwrite it, or cancel" with Overwrite / Cancel (title is not shown on macOS sheets).
- Delete: "Delete Preset" dialog with Cancel / Delete; the selected entry and its files go; the panel keeps the values (recipe unchanged after delete).
- Built-ins: TC9.18 by Pharmacist loads prebuilt pages, greys targen and printtarg under two override boxes, unticks the engine silently (F-016), is judged red by the i1Pro minimums (F-017), and the info line is stale (F-015). Full-layout i1Pro 162p: engine on, 162 (27x6) built, estimate equal. CR30 153p hexagonal: engine on, 153 (17x9) hexagons with row numbers, estimate equal, own margins 13/26/13/13 shown as minimums. Scanner 3430p: engine on, 3430 (49x70) at 4 mm, estimate equal. "none": toggle unchanged, panel keeps the last preset's instrument and margins.
- Restart round trip: AssessPresetB saved (recipe in Test Runs/logs/d05b_presetB_recipe_saved.json); compared after a real process restart in D06.

## A9 patch-set editor (OBSERVED)
- The last-page hint's "Edit patch set..." opens "Edit / create chart patch set" full-window with the run's 300 patches preloaded (e02 shot). Tools route: same dialog; its engine panel recipe equals the tab's (diff {}). Apply -> "Apply or save this patch set" (Overwrite / Save As... / Cancel) -> Overwrite rebuilt the same 304-patch chart (19x16); tab recipe unchanged; a further Generate gives the same chart. The layout survives the round trip.

## A11 preflight (INFERRED)
- workflow/layout_engine/preflight.py has no caller in the app (F-014). The Print tab's preflight is a pre-send summary (printer, media, duplex, colour management, paper mismatch).

## F-003 re-check (OBSERVED)
- Fresh run, engine off: widgets -L False / -a 1.0 / -m 6, preview `printtarg -ii1 -pA4 -t300 -M6 -r -c chart`; at the click -L became True; runner executed `printtarg -ii1 -pA4 -t300 -L -M6 A5-Furniture`; meta.json and both sidecar records now say -L True. Added to F-003.

## A7 debounce
- Still open: forcing the setting without the checkbox's own handler produced no auto builds; the real checkbox click (D04) did. Re-test in D06 with a real click.

## Findings filed
F-014 (medium), F-015 (medium), F-016 (low), F-017 (medium); F-003 extended.
