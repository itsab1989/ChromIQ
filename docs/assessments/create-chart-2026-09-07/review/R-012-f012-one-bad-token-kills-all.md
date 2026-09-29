# R-012 F-012 one unknown token leaves every token unexpanded
Verdict: CONFIRMED, with the missing baseline supplied
Grade: OBSERVED. Agent 1 only tested texts that contained a bad token; I built "Sheet {project} {date} {patchcount}" first: it prints "Sheet R2-Engine 2026-09-07 525 patches" (crop f012-valid-tokens-bottom.png), so expansion works. "Sheet {project} {patches}" prints literally (f012-bad-token-bottom.png). The panel's own live text preview shows the literal string without a warning.
Code: agree (workflow/layout_engine/raster.py _resolve_with: str.format inside try, returns the whole text on KeyError).
Severity: medium (agree).
