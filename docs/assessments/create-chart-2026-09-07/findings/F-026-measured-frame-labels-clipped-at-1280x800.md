# F-026 At 1280 x 800 the "Measured from Preview" row labels are clipped by the number columns
Area: preview (info frames) / window
Grade: OBSERVED
Attended: unattended
Type: UX (layout)
Severity: low
Expected: At the smallest supported window the frame either elides its labels visibly or wraps them; no text is cut by a neighbouring column.
Actual: Window 1280 x 800 (Manual, engine on, A1-EngineVsPrinttarg run1): "Bottom (to first patch)" is cut to "Bottom (to first patch]" by the mm column and "Patch width (in strip reading direction)" to "Patch width (in strip r". The three checkbox captions wrap correctly. The preview shrinks to about 245 x 330 px at this size (still usable). At 1700 x 1050 and maximised (1728 x 1051) nothing is clipped.
Why it matters: The frame is the engine's readout; a clipped label cannot be read at the size a 13-inch laptop offers.
Steps to reproduce (click by click): Resize the window to 1280 x 800 with a chart on screen; read the left frame.
Evidence: Screenshots/B9-window/w-1280x800-manual.png, w-1280x800-guided.png; Test Runs/logs/d08b_results.json (b9-1280x800: left pane 548 px, preview 696 x 282 px, frames 311 px tall).
Spec or source cited: none.
Possible solutions (no code): give the label column an elide mode with the full text as tooltip, or let the two frames stack when the width falls under a threshold.
Regression risk if changed: Low.
Needs owner decision: no
