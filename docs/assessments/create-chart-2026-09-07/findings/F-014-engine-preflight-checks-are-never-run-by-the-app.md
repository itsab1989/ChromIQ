# F-014 The layout engine's preflight checks (patch-size floor, inter-patch contrast, fit) are never run by the app
Area: layout engine (preflight)
Grade: INFERRED (no caller in ui/, workflow/ or main.py outside the module itself; nothing on screen ever showed such a badge in 100+ builds)
Attended: n/a
Type: missing feature / dead code
Severity: medium
Expected: `workflow/layout_engine/preflight.py` describes "Headless checks (no ArgyllCMS needed) that power the in-app green/red badge before printing: patch-size reliability floor, inter-patch contrast, and that the layout actually fits. These protect Design priority #1." The brief's A11 asks when it runs and what it says.
Actual: The module is imported only by tests. The only "preflight" in the app is `ui/dialogs/preflight_dialog.py`, opened by the Print tab before sending a job; its rows are printer, media, duplex, colour management, plus a paper-size mismatch warning built in `tab_print._show_preflight`. It does not call the engine module and knows nothing about patch size or contrast. Create Chart shows no green/red badge. The engine does log "note: low patch/spacer contrast in N strips" after a build (seen in most D02 to D04 builds), which is a different, weaker channel: a log line, hidden when the log is collapsed (the owner's default is log hidden).
Why it matters: A CR30 chart at the 4 mm aperture, a ColorMunki extra-high chart with 10 mm patches, or an area-first chart squeezed to 7 mm patches passes silently; the instrument reads it or does not. The module that was written to catch this exists and is tested but is not wired.
Steps to reproduce: Build any chart; look for a readability verdict anywhere in Create Chart or before printing: none.
Evidence: grep results in Test Runs/logs (see checkpoint-05), workflow/layout_engine/preflight.py docstring, ui/tabs/tab_print.py:1703 `_show_preflight`, the D02 to D04 logs showing "low patch/spacer contrast" only as a log line.
Spec or source cited: none of the binding specs mentions preflight; the module docstring is the only statement of intent.
Possible solutions (no code): A. Run the headless checks after every build and surface them in the "Measured from Preview" frame as a third line (green/amber). B. Also run them in the Print tab's preflight dialog for engine charts. C. If the owner does not want it, delete the module so the promise is not misleading.
Regression risk if changed: Low for A/B (read-only checks); the thresholds inside the module have never faced real charts, so expect false alarms to tune.
Needs owner decision: yes (wire it, or drop it).
