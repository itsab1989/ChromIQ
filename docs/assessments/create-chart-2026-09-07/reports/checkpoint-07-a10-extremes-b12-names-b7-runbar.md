# Checkpoint 07: A10 extremes, B12 names, B7 run bar, A7 settled, A8 fresh-session default

Time: 09:05 to 09:25. Drivers: d07_extremes_names_runbar.py (killed by me at 09:14 after my watcher missed a dialog because of `id()` reuse; fixed in cc_lib), d07b_extremes_rest.py (complete). Data: d07_extremes_names_runbar.log, d07b_results.json, d07b_extremes_rest.log. Shots: Screenshots/A10-extremes, B12-names-files, B7-runbar, A7-auto-preview/a30, A8-presets/q32. One screen capture taken to identify the missed dialog showed only the desktop (with a personal photo) and was deleted at once; it is not evidence.

## Corrections to earlier checkpoints
- A7 auto-update (checkpoints 05 and 06 said "did not fire"): WRONG, my tooling. The Python log shows "chart build (live preview)" 1.5 to 1.9 s after each layout edit, in D06 and D07 alike, including after a named preset was loaded and after "none". Two nudges 150 ms apart gave one build (debounce works). Chart Notes edits and the helper-marker toggle do not trigger it (markers have a preview overlay); spacer colour, sheet text and paper do. The tab's log widget is cleared for a live re-layout, which is why counting its lines saw nothing. A7 = pass.
- A8 Chart Layout default: in a fresh session, Manual i1 / A4 / clip opened with align Centre and patch-first, the values saved in Preferences by D06. The default seeds a fresh panel (spec 4c): pass. The sandbox file i1_A4_clip.json created by D06 was then removed to restore the owner's copy.

## A10 extremes (OBSERVED)
| case | estimate before | result |
|---|---|---|
| -f 1 | 20 (20 x 1 at 12 mm, one strip) | built 20 = 10 patches (1 + whites/blacks/greys from the Auto rows) + 10 fill-up; no refusal, sensible |
| -f 10000 | (fixed count) | targen 27 s, engine 4 s, 36 pages of 20 x 14 = 280, 34 MB TIFF; window unresponsive ~4 s during the draw (the app logs that it will be); then the last-page hint (my watcher missed it) |
| 60 x 60 mm patch on 20 x 20 sheet | dashes, Generate enabled | targen ran, engine failed "paper too short: a single pass of patches does not fit (8.0 mm available)"; log only; preview NO PREVIEW (F-019) |
| margins 50 all round on 100 x 100 | dashes | same failure, "(-11.1 mm available)" (F-019) |
| grid 200 x 500 on A4 | 285 x 174 at 1.0 mm, 20 pages assumed | targen ~6.5 min, 49,590 patches of 1.02 mm on one page, no warning (F-020); estimate pages 20 vs built 1 (F-021) |
| 72 dpi on 100 x 100 | 9 x 7 | built 63, TIFF 283 x 283 px at 72 dpi; estimate assumed 20 pages (F-021) |
| 1200 dpi on 100 x 100 | 10 x 8 | built 80, TIFF 4724 x 4724 at 1200 dpi, 4.9 s (F-021 again) |
| 20 pages, CM hand-held A4 | 960 (8 x 6 x 20) | built 960 on 20 pages, 6.7 s |
| custom 20 x 20 (i1 default patch) | none | fails "8.0 mm available" (F-019) |
| custom 2000 x 2000 | 1,210,300 (247 x 245 x 20 pages) | estimate only; not built |
Every failure produced "[ERROR] ChromIQ layout engine: ..." lines and "Chart generation failed." in the log; no Python traceback, no CRITICAL, no crash.

## B12 names (OBSERVED, project A10-Extremes open unless stated)
| typed | what happened |
|---|---|
| empty | no dialog; Generate builds into the open project (the field being empty means "this project") |
| the open project's own name | no dialog; same |
| another existing project's name (A1-EngineVsPrinttarg) | hint line "You already have a project with this name."; no dialog; the bar switched to that project's run1 and Generate built there (the build failed for an unrelated reason, so its chart survived). Chart-only runs raise no S4.7 window: consistent with the owner's deferred chart-overwrite ruling, but note it crosses projects |
| "Ümläut Äpfel Øre" | "Rename Printer Profile" dialog: Rename the existing / Create and keep / Create and delete / Cancel (umlauts accepted) |
| 250 x "x" | "Give this project a name" prompt (too long) |
| "a/b:c" | prompt (illegal characters) |
| "  trailing  " | Rename dialog offered to create it (not exercised further; whether the folder keeps the spaces is UNKNOWN) |
| "CON" | prompt (Windows reserved name) |
| ".dot" | prompt (leading dot) |

## B7 run bar (OBSERVED)
- Switching runs mid-edit: run1 edits (instrument margins off, top 44, sheet text) were written to run1's meta.json on leaving (W6 confirmed: stored margin_top 44, chart_text "mid-edit"); on returning, the panel showed the chart sidecar's values (38 / on / empty). This conforms to Knut's sidecar-precedence ruling (per_target_settings.md section 10), with the consequence that unbuilt edits are stored but never shown again while the run has a chart; worth a line in the owner's questions, not a finding.
- run2 (printtarg run) restored engine off and margin 6 on selection; run1 restored engine on: per-run restore works.
- Project folder deleted in the file system while open: the bar kept "Run 1 (overwrite)" and the location line; Generate recreated the folder silently (project.json, runs/run1/meta.json, cache/new_run.json, the .ti1 and a "Where are my files.txt" guide), no dialog, no crash; "New run" then offered runs/run2. The build itself failed only because the driver's 20 x 20 paper was still set. Whether a silent recreation is wanted (the code comment in _restore_last_session says the opposite for session restore) is a question for the owner.

## Findings filed
F-019 (medium), F-020 (medium), F-021 (medium).

## Regression baseline additions
- 1, 10,000 and 20-page builds complete; 72 and 1200 dpi honoured; custom 2000 mm estimated.
- Name validation prompts for too long, illegal characters, reserved names and leading dots; umlauts accepted; new names over an open project go through the four-way Rename dialog.
- Per-run restore of engine state and margins on run switch; W6 writes on leaving a run; sidecar precedence on return.
- A deleted project folder does not crash the app.
