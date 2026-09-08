# F-012 One unknown placeholder in sheet text or clip text leaves EVERY placeholder in that text unexpanded, with no warning
Area: layout engine (Sheet text, Clip-border content)
Grade: OBSERVED (printed sheets) + INFERRED (cause read in code)
Attended: unattended
Type: bug
Severity: medium
Expected: Known placeholders ({project}, {date}, {paper}, {instrument}, {patchcount}, {pages}, {seed}, {dpi}, {page}, {rundescription}) are expanded; an unknown one is either left literal on its own or flagged in the panel's live text preview.
Actual: Clip text "Custom {project} {date} {instrument} {paper} {patches}" printed exactly like that in the band, braces and all (four valid names and one invalid). Sheet text "Sheet {project} · {date} · {patches} patches · {rundescription}" printed literally at the bottom of the sheet. No message anywhere.
Why it matters: A typo such as {patches} instead of {patchcount}, or a literal brace in a note, silently wipes the project name and date off a printed sheet whose whole purpose is to identify itself. The panel offers an Insert-token menu, but a typed token is legal too.
Steps to reproduce (click by click): MANUAL, engine on. Sheet text: type "Sheet {project} {patches}". Generate. Read the bottom of the sheet: literal text.
Evidence: Screenshots/A5-furniture/f02-clip-text-preview.png (band), f12-sheet-text-preview.png (bottom line), f06-clip-image-preview.png (same text still literal).
Spec or source cited: workflow/layout_engine/raster.py:1292 `_resolve_with`: `t.format(**ctx)` inside `try`, and on KeyError/IndexError/ValueError `return t` ("leave unknown placeholders literal"), which leaves ALL placeholders literal, not the unknown one. ui/dialogs/layout_options_panel.py:51 SHEET_TOKENS is the legal list.
Possible solutions (no code): A. Substitute token by token (a regex over {name}) so unknown names stay literal individually. B. In addition, mark unknown tokens in the panel's live "text preview" line so the mistake is visible before Generate. C. Escape stray braces instead of failing.
Regression risk if changed: Low; the token set is small and fixed.
Needs owner decision: no
