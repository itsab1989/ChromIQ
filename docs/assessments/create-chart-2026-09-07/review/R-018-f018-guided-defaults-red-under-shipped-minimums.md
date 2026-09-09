# R-018 F-018 Guided i1Pro 3 Plus A4 landscape red out of the box
Verdict: PARTLY RIGHT. The observation is exact; the stated cause and the scope are wrong; the "expected" contradicts a shipped test.
Area: guided / layout engine / margin inspector
Grade: OBSERVED (screen) + code and test read
Attended: unattended
Severity: high as a user-visible state (agree), but it is a design question, not a broken clamp
Reproduced (R2-Guided, Guided, nothing changed but instrument, paper, 1 page):
- p3 A4 landscape: 112 (7 x 16), Left 26.0 < 28, Top 33.4 < 40, red. (Agent 1's case, identical numbers.)
- p3 A4 PORTRAIT: 99 (9 x 11), Left 26.0 < 28, Right 8.0 < 9, red. NEW.
- i1 A4 LANDSCAPE: 544 (16 x 34), Top 29.5 < 38, red. NEW. Shot R02/04-guided-i1-A4R.png.
- i1 Letter LANDSCAPE: 544, Top 27.2 < 38, red. NEW.
- Green: i1 A4 portrait 484, i1 A4 portrait 2 pages 968, CM A4 portrait 105, CM A4 landscape 100.
What is wrong in F-018: "ChartCreator._apply_margin_thresholds promises to raise the layout's margins ... on the non-recipe (Guided) path" and "the clamp works for those (i1, CM)". `_apply_margin_thresholds` (workflow/chart_creator.py:1394) has no caller anywhere in ui/, workflow/, core/ or main.py; no build logged a clamp note; every Guided recipe carries 6/6/6/6. And tests/test_chart_creator_engine.py:232 `test_guided_does_not_enforce_margin_thresholds` pins that Guided must NOT clamp ("Guided behaves like before the #93 threshold feature"). i1 A4 portrait and CM A4 pass because the 10 mm (i1) / 6 mm (CM) border plus the label band happen to exceed the seeds, not because anything raised them. The "clip logic overrides the clamp" theory is therefore moot.
Spec: docs/dev_margin_inspector.md says the seeds are "editable starting points, not physical minima" and records (#171) that Guided is "barely checked" by design decision of 2026-08-26; it does not say Guided must satisfy the table. The i1Pro A4 portrait 19 mm bottom is a ruling; the landscape T 38 rows are seeds. Code and test agree with each other and disagree with Agent 1's expectation. Decision for the owner: (a) Guided honours the table for the instrument (the dead `_apply_margin_thresholds` is the obvious hook, and the test above would have to be inverted), or (b) the seeds for the landscape rows (and p3 portrait L 28 / R 9) are reviewed, or (c) Guided's verdict is presented as advisory. Any of these changes shipped geometry or shipped seeds.
Also file: `_apply_margin_thresholds` is dead code with a docstring that promises behaviour the app does not have (see R-101).
Agent 1's solution A ("make the clamp win over the clip-band floor") would change every Guided p3 and i1 landscape sheet and break the test named above; it must not be done without the owner.
