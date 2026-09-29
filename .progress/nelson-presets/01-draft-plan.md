# DRAFT PLAN (to be challenged before any code is written)

## Verdict on the presets
ACCEPT both, as **prebuilt-files** built-ins (kind 1, docs/dev_builtin_presets.md).
See 00-facts-measured.md. Two things to report to Basti/Nelson rather than
silently "fix": the 0.564 mm spacer (smallest ever shipped) and the .ti2
PAPER_SIZE that disagrees with the sheet (already true of 8 of 9 shipped
bundles, so not new).

## Open design question 1 — THE PAPER SIZE (the real one)
The sheets are 100x150 mm and 130x180 mm. `data/patch_db.PAPER_SIZES` has
neither. Its nearest entries are the INCH sizes:
   "4x6"     = 4x6"  = 101.6 x 152.4 mm
   "127x178" = 5x7"  = 127.0 x 177.8 mm
`_prebuilt_paper_code(key)` maps the asset paper folder to a printtarg `-p`
that is written into the layout panel, so that if the user ticks the "Edit
layout" override and re-generates, printtarg starts from the right sheet.
Its fallback for an unknown folder is a silent `"A4"`.

Options:
  (a) Add "100x150" and "130x180" to PAPER_SIZES/PAPER_LABELS (and to
      EXCLUDED_PAPERS["p3"], since an i1Pro 3 Plus needs 20 mm patches).
      Honest; helps every user; but it widens the Create Chart paper dropdown,
      the layout-engine paper list and the TI2 relayout dialog for everyone,
      and the capacity DB has no entry so it falls back to a live printtarg
      binary search.
  (b) Map to 4x6 / 127x178. A re-layout would then silently build for a sheet
      1.6 mm wider (4x6) or 3 mm narrower (5x7) than the bundle. Dishonest.
  (c) Leave the fallback, i.e. A4. Worst.
Recommendation: (a).

## Open design question 2 — asset folder + stem
Convention: assets/charts/<creator>/<colorspace>/<instrument>/<paper>/<target>/<stem>.*
Proposed:
  assets/charts/pharmacist/rgb/i1pro/10x15/photocard600/photocard600.{ti1,ti2}
  assets/charts/pharmacist/rgb/i1pro/13x18/photocard648/photocard648.{ti1,ti2}
plus photocard600_01..04.tif / photocard648_01..03.tif.

## Open design question 3 — labels
Convention: "★  <instr> · <paper>-<N>p-<M>pages <name> by Pharmacist  ·  built-in"
Proposed:
  ★  i1Pro · 10x15cm-600p-4pages photo card by Pharmacist  ·  built-in
  ★  i1Pro · 13x18cm-648p-3pages photo card by Pharmacist  ·  built-in
Overlay short labels (instrument omitted): "10x15 cm photo card by Pharmacist" etc.
Default target names:
  i1Pro-10x15cm-600p-4pages-photo card by Pharmacist
  i1Pro-13x18cm-648p-3pages-photo card by Pharmacist

## Steps
1. Stage assets, rename to the leaf stem.
2. Constants + PREBUILT_PRESETS + BUILTIN_PRESET_LABELS + BUILTIN_PRESET_GROUPS
   (i1Pro group).
3. `_prebuilt_paper` + `_prebuilt_paper_code` new folder entries.
4. Paper sizes per question 1.
5. `python scripts/derive_prebuilt_geometry.py` -> channels.json sidecars.
6. Tests: extend the pinned counts; add a dedicated test file that pins the
   measured sheet size / patch count / page count / patch geometry.
7. i18n: check whether any new user-facing string needs tr() + de.
8. Docs: dev_builtin_presets.md table; CHANGELOG; the website's preset count.
9. Drive the real app on screen end to end.
10. --runslow gate.

## Branch / release plan (Basti's ask)
- master is at 4.2.1-beta.1? (verify) -> branch `feature/nelson-photocard-presets`
  off master, land the presets, merge to master, bump to 4.2.1, tag, release.
- feature/182-compliance-sets: merge master in so it inherits the presets,
  then its next beta is 4.2.2-beta.1.
