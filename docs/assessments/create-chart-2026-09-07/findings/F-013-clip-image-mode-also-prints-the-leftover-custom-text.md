# F-013 "Imported image" clip mode also prints whatever is left in the Custom text box
Area: layout engine (Clip-border content)
Grade: PARTIAL (the print is OBSERVED; whether the Text box is greyed in image mode was not captured)
Attended: unattended
Type: inconsistency / UX
Severity: low
Expected: The Clip-border content selector offers "Custom text" and "Imported image" as alternatives; picking the image prints the image. If a caption is intended, the Text box should be visibly live in image mode and labelled as a caption.
Actual: After typing custom text (step f02) and switching to "Imported image" (f06) with a 600x200 PNG, the band shows the image as a small stamp (fit to the 26 mm band width, so 26 x 8.7 mm) AND the earlier custom text running the full band height. "Off" (f05) removes the text, so the text is tied to the image mode, not simply always printed.
Why it matters: A user who moves from text to a logo gets both, and the only way to clear the text is to switch back to "Custom text" and delete it.
Steps to reproduce (click by click): Clip-border content "Custom text", type a line; switch to "Imported image", browse to a PNG; Generate.
Evidence: Screenshots/A5-furniture/f06-clip-image-preview.png, f02-clip-text-preview.png, f05-clip-off-preview.png.
Spec or source cited: workflow/layout_engine/raster.py:render_clip_strip, `mode == "image"` branch draws the logo, then `lines = clip_text_lines(text)` and overlays them (deliberate in code, undocumented in the UI).
Possible solutions (no code): A. In image mode ignore the Text box, or B. keep the caption but show the Text box enabled and labelled "Caption" in that mode, and say so in the mode's help.
Regression risk if changed: Low.
Needs owner decision: yes (is image + caption the intended behaviour?)
