# Checkpoint 02 (Agent 2): the engine on my own sample, the medium findings, built-ins, calibration

Time: 10:10 to 10:25. Drivers: r04_engine.py, r05_files_presets_cal.py. Data: Review/Test Runs/logs/r04_results.json, r05_results.json, the two .log files. Shots: Review/Screenshots/R04-engine, R05-files-presets-cal. Unattended; dialogs answered by the armed watcher (hex heads-up -> OK, last-page hint -> OK, "already" -> Continue this project, "Where should this patch set's chart go?" -> Build it as a new run instead, "already has a finished calibration" -> Cancel). No unexpected dialog. One ERROR record per run, both the engine's expected "paper too short" refusal.

## Engine: estimate vs render on my own sample (Auto count)
Six builds, all exact (total, rows, strips, pages; patch size within 0.06 mm): i1 A4 clip 525; p3 A3 landscape 299; CM high A4 landscape 209; SS hex A4 1058 (hex heads-up shown once); CR30 flat custom 200 x 200 195; i1 Letter 462. Agent 1's 55/55 claim is consistent with an independent sample.

## Verdicts
| F | verdict | one line |
|---|---|---|
| F-005 | CONFIRMED | i1 A4, instrument margins ON: clip On 525, Off 525, Left 26.0 both. With OWN 10 mm margins: Off 667 (29 x 23), On 609 (29 x 21): the label is true only when the instrument margins are off |
| F-006 | CONFIRMED | i1 A3 portrait: status label empty and hidden, notes ("Top margin is too small for the strip labels", "Strip length 400 mm exceeds the 240 mm ruler") live only in the frame's (i) hover; screenshot f006-A3-margin-panel.png shows numbers with no verdict at all |
| F-008 | CONFIRMED | A3 area-first, Max strip 200: 43 per strip estimate and build, note still "400 mm exceeds 240"; patch-first 200: 18 per strip; the spin's own tooltip is empty |
| F-012 | CONFIRMED | sheet text "Sheet {project} {date} {patchcount}" prints "Sheet R2-Engine 2026-09-07 525 patches"; "Sheet {project} {patches}" prints literally, both braces intact (crops f012-*.png); the panel's live text preview shows the literal string too, no warning |
| F-014 | PARTLY RIGHT | Create Chart never runs the preflight (true), but "imported only by tests / no caller in ui/" is false: ui/dialogs/settings_dialog.py:5652 runs preflight.check and indicator_width_warning for Preferences > Chart Layout's "≈ N patches per sheet" line, with red/amber messages. The module is wired, to the wrong place for the owner's purpose |
| F-015 | CONFIRMED | after a prebuilt CM A3+ built-in the info line read "printtarg -ii1 -pA4 -t300 -m10 -M10 -R 99999 -c chart" under "targen -f9513" (the previous chart's count); the i1 162p engine built-in reads "printtarg -ii1 -pA4 -t200 -a0.95 ..." with the engine on |
| F-016 | CONFIRMED | prebuilt built-in: engine on -> off, no message; full-layout built-in: off -> on; "none": toggle stays, the panel keeps the built-in's 200 dpi and 38/4/19/26 margins |
| F-017 | CONFIRMED (different built-in) | the ColorMunki A3+ TC9.18 by Pharmacist is red against the CM seeds: "Left margin 5.3 mm is below the 6 mm instrument minimum". So it is not only the i1Pro built-ins |
| F-019 | CONFIRMED, plus one fact | 20 x 20 sheet, 60 mm patch: estimate dashes, Generate live, targen runs (443 patches), engine fails, log only, no dialog. NEW: the app logs "[WARNING] engine patch estimate failed: paper too short ..." BEFORE targen starts, so it knows and runs targen anyway |
| F-021 | CONFIRMED (needs a re-open) | after a 22-page fixed-count build and a real project re-open: both spins 20 (clamped from 22); panel Pages set to 1 -> panel 1, hidden printtarg spin 20. In my run the estimate then still said 1 page (a fixed count was armed), so the visible symptom depends on state; the drift itself is real |
| F-025 | PARTLY RIGHT | preview blank until a run round trip: yes (round trip restored 1 page / 525). "The margin frame keeps a stale Margins: OK": no, both frames show their placeholders (Agent 1's own x10 screenshot shows the same; its driver read a hidden label's text). NEW and worse: the failed build DELETED exports/R2-Engine-colours.txt, -i1profiler.txt and -i1profiler.pxf and did not put them back (9 files before, 6 after, by name); Agent 1 reported "files identical before and after" |
| F-027 | PARTIAL, not closed | the loaded set stays armed, and the next Generate in the run it was loaded into laid out the 304-patch set without targen (R2-Engine run2, 51 pages of 60 mm patches from the panel's own state). The CROSS-PROJECT press did not happen: my project switch (session-restore route, same run id run2 on both sides) left Create Chart on the old project, see checkpoint 03 |
| F-029 | CONFIRMED | Demo-Full-RGB, calibration mode on for the session, Run type Calibration, Generate: the "already has a finished calibration" question (Replace the calibration / Cancel) and the DEBUG line "could not list runs built on the calibration"; every run's meta.json calibration_used is empty, so the list would be empty here anyway |

## New (Agent 2)
- N-1 A failed build destroys the previous chart's exports/ sidecars (see F-025 above). `Run.reset_chart_artefacts` rmtree's exports/ and cache/ before targen and the stash covers chart files only (core/file_manager.py, "exports/ AND cache/ ARE DERIVED"). Re-derivable by a successful rebuild; still a silent loss of files a user may have handed to i1Profiler.
- N-2 "Show strip indicators" off frees nothing: 525 -> 525, Top 39.0 -> 39.0, the label band stays reserved with the labels hidden (Agent 1 noted this in checkpoint 04 and did not file it).
- N-3 `ChartCreator._apply_margin_thresholds` is dead code whose docstring promises a Guided clamp the app does not have (see R-018).
- N-4 The engine's "patch estimate failed" warning fires before targen and is not used to stop the build (F-019 above).
- N-5 With a patch set armed, a project change that lands on the same run id did not refresh Create Chart (name, location, panel stayed on the old project while the file manager and Measure had switched); Generate then followed the stale name back to the old project. Reproduced through the session-restore route only so far; the real Open Project route is tested in checkpoint 03.

## Preset reveal button
Clicked; it is wired to `core.preset_store.reveal_in_file_manager`, which shells out to `open <folder>` on macOS (a Finder window opened on screen; no dialog, no crash). Works.

## Save as Defaults
Pressed with a 60 mm patch-first layout on screen: `manual_engine_recipe` written with every engine key (incl. patch_w_mm 60, layout_mode patch_first), one log line "Chart defaults saved", no dialog and no on-screen confirmation with the log hidden. It also saves `manual_pages`, `manual_auto_black` and other Manual keys. Works; silent.
