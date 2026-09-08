# F-019 A layout that cannot fit (patch larger than the sheet, margins that leave no room) is not refused before Generate; the failure is reported only in the log, which the owner keeps hidden
Area: layout engine / manual
Grade: OBSERVED
Attended: unattended
Type: UX / bug
Severity: medium
Expected: When the estimate cannot lay out a single strip, Generate is disabled or the estimate frame says why; if Generate is allowed, the failure is shown where the user is looking (a dialog or the status line), not only in the log widget.
Actual: Manual, engine on, i1Pro, Custom 20 x 20 mm, patch-first 60 x 60 mm: the estimate column shows dashes, Generate stays enabled. Pressing it runs targen (a real patch set is generated), then the engine fails: log lines "[ERROR] ChromIQ layout engine: paper too short: a single pass of patches does not fit (8.0 mm available)" and "[ERROR] Chart generation failed." No dialog. The preview shows NO PREVIEW and both frames show their placeholders. The same with Custom 100 x 100 and margins 50/50/50/50: "... does not fit (-11.1 mm available)". The log widget is hidden in the owner's preferences (hide_log_output=1), so on his screen nothing says why the chart did not appear.
Why it matters: A user who mistypes a patch size or a margin sees the chart vanish and no explanation; the message that exists is good ("paper too short ... 8.0 mm available") but lands where it is not seen. The estimate already knows (it shows dashes), so the refusal could happen before targen runs.
Steps to reproduce (click by click): MANUAL, engine on, Paper "Custom...", 20 x 20; Create layout "Prioritise patch size"; Patch size 60 x 60. Note the dashes in the estimate column and the live Generate button. Press Generate. Watch the preview and the frames.
Evidence: Screenshots/A10-extremes/x03-patch-bigger-than-page.png, x04-margins-no-room.png, Test Runs/logs/d07b_results.json (x-patch-bigger-than-page, x-margins-no-room: dialogs [], errors [...]), d07b_extremes_rest.log.
Spec or source cited: workflow/chart_creator.py:_run_engine catches the exception and calls `on_line("[ERROR] ChromIQ layout engine: ...")` then `_finish([])`; tab_chart.py:17235 appends "[ERROR] Chart generation failed." to the log widget; no dialog on this path (the printtarg path has a friendly-error dispatcher). The preflight module that would have caught this headlessly is never called (F-014).
Possible solutions (no code): A. When the estimate returns nothing, grey Generate and print the engine's own reason in the estimate frame ("a single pass does not fit: 8 mm available"). B. On an engine failure, show the same reason in a small dialog or in the status line under the button, as the printtarg path does. C. Keep the previous chart visible after a failed build (see the restore check in checkpoint-08).
Regression risk if changed: Low for B; A needs care so a transient estimate failure does not lock the button.
Needs owner decision: no
