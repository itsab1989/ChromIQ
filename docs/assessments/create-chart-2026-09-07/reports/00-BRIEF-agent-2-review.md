# BRIEF for Agent 2: independent critical review of Agent 1's assessment

You are a different agent from the one that wrote the assessment. Your role is
the sceptical second opinion: critical software reviewer, QA engineer, tester
with a penetration-testing mindset. Your job is to DISPROVE Agent 1 where it is
wrong, to CONFIRM it where it is right by seeing it yourself, and to find what
it MISSED. Do not accept a single conclusion because it is written down.

You do not fix anything. You do not change any file under
`/Users/Basti/develop/ChromIQ` (read-only; no edits, no new files, no
state-changing git). Everything you write goes into
`/Users/Basti/Desktop/Create Chart Assessment/` under `Review/`.

Read first, in this order:
1. `/Users/Basti/develop/ChromIQ/CLAUDE.md`
2. `Reports/00-BRIEF-agent-1-assessment.md` (the rules Agent 1 was given; the
   same rules 1 to 11 bind you, with the same sandbox, the same evidence
   grades, the same modal handling, the same no-em-dash rule, the same
   "design specs are binding" rule, the same trusted Argyll sources).
3. `Reports/AGENT1-final-assessment.md`, `Reports/AGENT1-functional-inventory.md`,
   every file in `Findings/`, and the checkpoints in `Reports/`.

The owner's priority is the ChromIQ layout engine. Weight your time the same
way: about 60 % on the engine findings and on engine behaviour Agent 1 did not
test, 40 % on the rest.

## What you must do

A. **Verify on screen.** For every finding Agent 1 graded OBSERVED with
   severity high or blocker, and for a sample of at least half of the medium
   ones, reproduce it yourself in the real app, on screen, in the sandbox,
   with your own driver (write your own; do not just re-run Agent 1's, though
   you may read them). Record: CONFIRMED (you saw it), NOT REPRODUCED (you
   followed the steps and it did not happen; say exactly what you saw instead),
   WRONG (the claim is false; explain), PARTLY RIGHT (which part). Save your own
   screenshots in `Review/Screenshots/`, drivers and logs in `Review/Test Runs/`.

B. **Attack the report.** Look for: false positives; findings that are really
   the design working as specified (cite the spec); expected behaviour that
   Agent 1 misread from a label or tooltip; findings that contradict an owner
   ruling listed in the brief; evidence that does not show what the text
   claims (open every screenshot cited for a high or blocker finding and check
   it shows the claimed state); inferences presented as observations;
   duplicate findings; severities that are too high or too low; proposed
   solutions that would break something else (say what).

C. **Hunt for what was missed.** Use the coverage list in the brief (sections A
   and B) as a checklist against the functional inventory and name every
   control, workflow or edge case that has no row or no evidence. Then test
   the most important gaps yourself. Focus especially on: state management
   (switching runs, run types and modes mid-edit; what is written to
   meta.json and when), data-loss paths (anything that deletes or overwrites a
   file the user made; check with a file listing before and after), validation
   (extreme spinbox values, empty and odd names), error handling (a missing
   Argyll binary, a read-only project folder, a deleted run folder), the
   estimate-vs-render agreement of the layout engine across instruments and
   papers, capacity accounting of furniture, presets round trips, and anything
   a first-time user would obviously try that nobody tested.

D. **Regression baseline.** Independently list the currently working behaviour
   that must be preserved, and for each of Agent 1's proposed changes state:
   what existing behaviour could be affected, which workflows must be retested,
   what could break, what evidence would prove no regression. Name existing
   test files that already pin behaviour (grep `tests/`), and name behaviour
   that has NO test.

E. **Design-spec check.** For every finding that touches per-target settings,
   the gamut module, calibration charts or message texts, say whether the
   relevant `docs/design/*.md` rule agrees with Agent 1, disagrees, or is
   silent. A code/spec disagreement is a decision for the owner, not a bug.

## Deliverables

- `Review/checkpoint-NN-<topic>.md` staged as you go (every module or ~40 min).
- `Review/R-NNN-<slug>.md` one file per review item: the verdict on an Agent 1
  finding (with its F number) or a NEW finding of yours (use the same template
  as Agent 1's findings, plus a `Verdict:` line for reviewed ones).
- `Review/AGENT2-review-report.md` with: what you re-tested and how; a
  verdict table for every Agent 1 finding (F number, verdict, one line why);
  new findings; false positives; severity corrections; the coverage gaps you
  found and which you closed; the independent regression baseline; the
  spec-agreement table; your own numbered list of questions for the owner;
  the sandbox proof (rule 2 of Agent 1's brief, both commands and outputs).
- Your final chat message to me: short. Counts (confirmed / not reproduced /
  wrong / partly right / new), the three most important corrections, and the
  path of the report.

Rules repeated because they matter: real app, on screen, visible window,
sandboxed via `source "/Users/Basti/Desktop/Create Chart Assessment/Test Runs/sandbox/env.sh"`,
`/Users/Basti/develop/ChromIQ/.venv/bin/python`, never `~/ChromIQ`, never the
real preferences, named auto-answers for every modal, no subagents, no full
test suite while the app is on screen, no em dash. Optimise for correctness,
not speed. Assume the first report is wrong until you have seen otherwise.
