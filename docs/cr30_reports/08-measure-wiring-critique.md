STATUS: in-progress

# 08 — Measure-tab wiring critique (CR30)

**Agent:** CR30-MEASURE-CRITIC
**Branch:** `feature/cr30-instrument-159`
**Started:** 2026-08-28

Scope: attack the proposed diagnosis of Basti's live failure

```
[WARNING] workflow.measure_manager: engine could not use the instrument (unknown error) — restarting on stock chartread
```

and the three intended fixes (A: no stock fallback for CR30, B: pass `-x`,
C: pre-select patch-by-patch). Report only — no production file is edited.

Sections are appended as they are proved. Nothing below is written from
memory; every claim carries a `file:line` or a command whose output is quoted.

