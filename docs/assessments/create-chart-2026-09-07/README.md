# Create Chart assessment, 2026-09-07

An on-screen assessment of the whole Create Chart tab, with the ChromIQ layout
engine first and the rest of the tab second, run against ChromIQ 4.2.0
(master `80975e65`). Two agents worked one after the other: the first assessed,
the second reviewed the first's findings independently and probed the gaps.

**No app code was changed by the assessment.** Everything here is evidence and
analysis. The decision document ends in 16 questions that are still unanswered.

## Start here

| File | What it is |
|---|---|
| [`final-assessment-and-decisions.txt`](final-assessment-and-decisions.txt) | The whole thing in plain English: Part 1 method, Part 2 the problems P1-P12, **Part 3 the 16 decisions with blank lines**, Part 4 the summary lists |
| [`final-report/IMPLEMENTATION-READINESS.md`](final-report/IMPLEMENTATION-READINESS.md) | File-and-line plan per item, the test to write first, the driver to re-run. Written so a later fix is easy and safe; it is not a change |
| [`final-report/CHALLENGE-of-the-decision-document.md`](final-report/CHALLENGE-of-the-decision-document.md) | An adversarial pass over the decision document itself |
| [`review/AGENT2-review-report.md`](review/AGENT2-review-report.md) | The reviewer's verdict on all 29 findings plus its own 10 new items |
| [`reports/AGENT1-final-assessment.md`](reports/AGENT1-final-assessment.md) | The first agent's report, 29 findings |
| [`reports/AGENT1-functional-inventory.md`](reports/AGENT1-functional-inventory.md) | Control-by-control inventory of the tab |

## How it was driven

Both agents drove the real app on the real screen, unattended, through scripts.
No human clicked anything. Agent 1: 15 drivers, 150 chart builds, 261
screenshots, 29 findings. Agent 2: 10 drivers, ~45 builds, 60 screenshots,
20 findings confirmed / 5 partly right / 0 wrong / 4 not re-tested, plus 10 new.

Everything ran against a sandbox: `CHROMIQ_SETTINGS_FILE` pointed at a copy of
the preferences and `CHROMIQ_PRESETS_DIR` at a copy of the preset folder, with
projects built under `~/ChromIQ-assessment` (see
[`evidence/env.sh`](evidence/env.sh) and
[`evidence/sandbox_proof.txt`](evidence/sandbox_proof.txt)). The real
preferences, preset folder and `~/ChromIQ` were byte-identical afterwards.

## Layout of this folder

```
findings/      F-001 .. F-029   one file per finding of the first agent
review/        AGENT2-review-report.md, R-001..R-108, its checkpoints
reports/       both agent briefs, the first agent's reports, 8 checkpoints
final-report/  the implementation plan and the challenge of the decisions
drivers/       every driver script that drove the app (drivers/review/ = agent 2)
logs/          every run log and JSON result (logs/review/ = agent 2)
evidence/      code map of the layout engine, sandbox proof, test fixtures
screenshots/   the 57 shots cited by the findings, in their original folders
```

The other ~270 screenshots, the copied preference/preset sandbox and the
before-snapshot of the real machine stayed off the repository: they are personal
data or unreferenced duplicates. Nothing here is packaged into `ChromIQ.app`,
which bundles only `assets/` and named `data/` paths.

## The problems, and where each one is written up

| # | Problem | Grade | Finding files |
|---|---|---|---|
| P1 | "New run" + Generate stores the pre-edit seed block, not the screen | HIGH | `findings/F-003`, `review/R-003`, `review/R-105` |
| P2 | Four default Guided sheets are flagged red by the app's own instrument limits | HIGH (design) | `findings/F-018`, `review/R-018`, `review/R-101` |
| P3 | Fixed-count estimate and the "last page not full" hint disagree with the build | HIGH | `findings/F-001`, `review/R-001` |
| P4 | An Instrument Limits change does not reach the panel, the estimate or the build | HIGH | `findings/F-007`, `review/R-007` |
| P5 | One visit to From Profile Gamut without a profile disables Generate everywhere | HIGH | `findings/F-024`, `findings/F-023`, `review/R-024`, `review/R-023` |
| P6 | A failed build deletes the previous chart's `exports/` files, preview goes blank | MED | `findings/F-025`, `review/R-102` |
| P7 | The estimate reads a hidden printtarg Pages spin, not the panel's | MED | `findings/F-021`, `review/R-021` |
| P8 | Impossible layouts are not refused; the reason lands only in the hidden log | MED | `findings/F-019`, `review/R-019` |
| P9 | No patch-size floor, and the engine's preflight is not shown in Create Chart | MED | `findings/F-020`, `findings/F-014`, `review/R-014` |
| P10 | Margins: what the 26 mm left minimum owns, the ignored strip cap, tables that do not exist | MED-LOW | `findings/F-005`, `F-008`, `F-009`, `F-010`, `review/R-103` |
| P11 | Built-in presets: wrong info line, silent engine toggle, red under the shipped minimums | MED | `findings/F-015`, `F-016`, `F-017` |
| P12 | The smaller confirmed problems | MED-LOW | `findings/F-002`, `F-004`, `F-006`, `F-011`, `F-012`, `F-013`, `F-022`, `F-026`, `F-027`, `F-028`, `F-029`, `review/R-104`, `R-106`, `R-107`, `R-108` |

## What the assessment did NOT cover

The scanner path end to end from an engine hexagonal chart; the Demo-Legacy-v2
project; a read-only run folder; a missing Argyll binary at Generate time; light
and dark appearance beyond readability; German at sizes other than 1280x800 and
1700x1050. One sub-claim of the first agent (that a printtarg command carried
`-L` against the preview) could not be reproduced and is graded UNKNOWN.

## What must be protected when any of this is fixed

The regression net is named in Part 4 of the decision document: the 55-build
instrument matrix and the 11 layout-mode builds (`drivers/d02_instrument_matrix.py`,
`drivers/d03_layout_modes_and_margins.py`), the two per-target seeding drivers,
Guided parity with printtarg on four combos, and the shipped test that pins
"Guided does not clamp", which is to be changed deliberately or not at all.
