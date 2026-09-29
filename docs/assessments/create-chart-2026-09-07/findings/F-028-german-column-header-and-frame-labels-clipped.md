# F-028 German: the "auf dem Bildschirm" column header is clipped to "dem Bildschirm" at every window size, and the measured-frame row labels clip at 1280 x 800
Area: help / preview frames (language de)
Grade: OBSERVED
Attended: unattended
Type: UX (layout, one language pass as the brief asked)
Severity: low
Expected: Column headers and row labels fit or elide with a tooltip in every catalogue language.
Actual: Language de, project A1-EngineVsPrinttarg. The "Chart-Layout-Informationen" frame's first column header needs 93 px and has 72 at both 1280 x 800 and 1700 x 1050, so it prints "dem Bildschirm" with the first word cut. At 1280 x 800 the "Aus Vorschau gemessen" row labels ("Links (bis zum ersten Feld)" needs 167 px, has 129; "Feldbreite (in Streifen-Leserichtung)" needs 224, has 129) are cut by the number columns, worse than in English (F-026). No clipped control was found in the Guided or Manual panes at either size (automatic check over every visible label, check box and button), and none in the nine Preferences tabs.
Why it matters: The two frames are the engine's readout; German is the owner's second language catalogue.
Steps to reproduce (click by click): Preferences > Language: Deutsch, restart. Open a project with a chart, read the header of the right-hand frame.
Evidence: Screenshots/B10-lang-de/de-1700-manual-top.png, de-1280-manual-top.png, de-1280-guided.png, de-prefs-*.png; Test Runs/logs/d09_results.json (clipped-frames-1280, clipped-frames-1700).
Spec or source cited: ui/chart_layout_info_panel.py header labels; ui/margin_inspector_panel.py row labels.
Possible solutions (no code): elide the row labels with a tooltip, or give the header column a minimum width computed from the translated text.
Regression risk if changed: Low.
Needs owner decision: no
