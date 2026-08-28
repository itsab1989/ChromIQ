# CR30 implementation — Python side — [CR30-IMPL-PY]

STATUS: in-progress
Branch: `feature/cr30-instrument-159`
Started: 2026-08-28

Companion to `01-surface-map.md` (task list), `02-design.md` (frozen design) and
`03-design-critique.md` (**the corrections; where design and critique disagree,
the critique wins**).

Scope boundary: the C side (`native/**`), the vendored driver
(`workflow/cr30/**`), `workflow/measure_manager.py` and
`workflow/chartread_engine.py` belong to **[CR30-IMPL-C]** and are NOT touched
here. Requests for changes in those files are collected in §R at the end.

---
