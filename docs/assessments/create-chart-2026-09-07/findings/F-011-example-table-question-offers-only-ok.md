# F-011 "Replace the current clip-border text with the example table?" is a question with a single OK button
Area: layout engine (Clip-border content)
Grade: OBSERVED
Attended: unattended (the watcher recorded the box and its buttons, then pressed OK)
Type: UX / bug
Severity: low
Expected: A yes/no question offers a way to say no (Cancel), or is not phrased as a question.
Actual: Selecting "Custom text example" in "Clip-border content" while the Text box holds text raised a QMessageBox with text "Replace the current clip-border text with the example table?" and buttons ['OK'] only. The text was replaced.
Why it matters: The user's own clip text is overwritten with no way to decline once the box is up; the question mark promises a choice that does not exist.
Steps to reproduce (click by click): MANUAL, engine on, i1Pro; Clip-border content: "Custom text", type anything in Text; switch Clip-border content to "Custom text example".
Evidence: Test Runs/logs/d04_furniture_export_autopreview.log 08:21:52 ("DIALOG UNEXPECTED [QMessageBox] title='' buttons=['OK'] text='Replace the current clip-border text with the example table?'"), Screenshots/A5-furniture/f03-clip-example-preview.png (result).
Spec or source cited: ui/dialogs/layout_options_panel.py around the clip_content_mode handler (`_on_clip_content_changed`).
Possible solutions (no code): A. Add Cancel and keep the text (revert the combo) when it is pressed. B. Do not ask; insert the example into a separate mode without touching the Text box (the modes are already separate values).
Regression risk if changed: Low.
Needs owner decision: no
