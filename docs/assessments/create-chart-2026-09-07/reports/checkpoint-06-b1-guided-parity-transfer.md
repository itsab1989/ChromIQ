# Checkpoint 06: B1 Guided, A1 parity, transfer to Manual, preset restart, Chart Layout defaults

Time: 09:00 to 09:02. Driver: d06_guided_parity_transfer.py. Data: d06_results.json, d06_guided_parity_transfer.log. Shots: Screenshots/B1-guided, A7-auto-preview/a20*, A8-presets/q20*, q30*, q31*. Unattended; only the "Auto-update preview is on" card appeared (armed, Close). No ERROR/CRITICAL. printtarg by hand: timeout 180 s each, all finished in seconds.

## Guided (project B1-Guided) - OBSERVED
| build | headline | estimate | built | printtarg by hand with the creator's own args | parity |
|---|---|---|---|---|---|
| i1 A4 1 page | 484! | 484 (22x22) | 484, 22x22, 1 page | `-ii1 -pA4 -t300 -a0.95 -m10 -M10`: 484, 22x22, 1 page | exact |
| CM A4 1 page | 105! | 105 (15x7) | 105, 15x7, 1 page | `-iCM -pA4 -t300 -M6`: 105, steps 15, passes 6+1, 2 pages | engine fits the 7th strip on page 1 (accepted design: page-label column reclaimed) |
| p3 A4R 1 page | 112! | 112 (7x16) | 112, 7x16, 1 page | `-i3p -pA4R -t300 -M6`: 112, 7x16, 1 page | exact |
| i1 A4 2 pages | 968! | 968 (22x22) | 968, 22x22 x2 | same flags: 968, 22,22, 2 pages | exact |

- The headline count equalled the built count in all five Guided builds (the "!" headline is honest).
- Guided margins: i1 A4 26/16.8/41.6/24.6 -> OK; CM A4 6/8/39.5/31.5 -> OK; p3 A4R 26/15/33.4/20.4 -> RED (F-018). Guided writes 6/6/6/6 into the recipe with `margins_chosen_by_user` False (the known, decided gap #171 in dev_margin_inspector.md; not re-filed).
- Guided fixed settings line: i1 "margin 10 mm · patch x0.95 · clip border on"; CM "margin 6 mm · hand-held"; p3 "margin 6 mm · clip border on".
- Guided boxes: "Suppress left clip border (-L)" 484 -> 550 (22x25); "Don't limit strip length (-P)" 484 -> 528 (24x22). Both move the headline and the estimate together. Contrast with Manual: Clip Off gains nothing there (F-005, updated in the final report).
- Guided per-instrument controls: i1/p3 show the two boxes; CM shows Double/Triple density; SS shows Double density; CR30 shows "Hexagon patches"; the Refinement profile row is always present.

## Transfer to Manual (OBSERVED)
After a Guided CM A4 build, clicking MANUAL shows CM / A4 / Hand-held, patch-first, margins 6/6/6/6 (instrument margins off), align centre-left; the estimate equals the Guided chart (105, 15x7, 28x14) and Generate in Manual without touching anything rebuilds the identical chart. The #79 exact-seed transfer works.

## Presets after a real restart (OBSERVED)
AssessPresetB (saved in D05b) picked in this new process: every recipe key identical to the saved JSON except the seed (excluded by design), engine on. Round trip holds.

## Auto-update preview (PARTIAL, still open)
Real checkbox click, card closed, project B1-Guided, chart on screen: no re-layout fired for min patch nudges, notes, helper markers, spacer colour, sheet text, nor a paper change (0 builds in 6 s windows). In D04 (project A5-Furniture, no preset ever loaded in that session) the same nudge fired in 1.37 s. Both sessions in which nothing fired had loaded a named preset earlier. Hypothesis: a preset load leaves a guard set (build-in-flight or layout-owned-by-build) that silences the live preview for the rest of the session. D07 tests this in a clean order: build, tick, nudge (expect fire), load preset, nudge (expect?).

## Chart Layout default via Preferences (PARTIAL)
Preferences > Chart Layout, i1 / A4 / clip: hint "Showing the layout you saved for this combination. Other paper sizes have layouts saved too." (a saved file i1_A4R_clip.json existed in the owner's copy); calc "≈ 462 patches per sheet". Changed align to Centre and layout to patch-first, OK: presets/Chart Layout/i1_A4_clip.json written. Manual, same session, i1/A4/clip re-picked: align centre-left, area-first (unchanged), consistent with spec 4c (controls already answered in this session are not overwritten). Fresh-session check in D07.

## Findings filed
F-018 (high). F-005 gains the Guided contrast.

## Regression baseline additions
- Guided headline == built count (5/5); Guided i1 and p3 layouts equal printtarg's for the same flags; Guided CM gains one strip per page over printtarg by design.
- Guided -> Manual transfer reproduces the built chart exactly.
- Named presets survive a restart with every key intact.
