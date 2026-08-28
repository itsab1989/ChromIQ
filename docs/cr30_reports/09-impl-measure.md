STATUS: in-progress

# 09 — Measure-tab wiring implementation (CR30, #159)

**Agent:** CR30-IMPL-MEASURE
**Branch:** `feature/cr30-instrument-159`
**Started:** 2026-08-28

Specification: `08-measure-wiring-critique.md` §8 (Change 0, A, B, C) plus
the sections it references, `02-design.md` §10, `01-surface-map.md`.

Appended as each change set lands. Every claim carries a `file:line` or a
command whose output is quoted.

---

## Change 0 — one CR30 predicate, resolved through `_chart_file_for` (F3, F5)

**Landed in two commits, deliberately.**

### 0.1/0.2/0.5 — the CR30 half

`TabMeasure._chart_is_cr30()` added immediately after `_chart_file_for`
(`ui/tabs/tab_measure.py:5197`). It resolves the sibling `.ti2`, checks it
exists, and swallows every exception — a detection check must never be the
thing that stops a measurement.

Both open-coded reads are gone:

* `_setup_stripe_rects` — the no-swipe arrow. Nine lines became
  `self._preview.set_no_swipe(self._chart_is_cr30())`.
* `_blocked_by_stock_chartread_for_cr30` — six lines became
  `if not self._chart_is_cr30(): return False`.

`grep -n 'read_target_instrument(self._ti1_path)' ui/tabs/tab_measure.py` now
returns nothing.

**Tests** (`tests/test_cr30_registration.py`, section 12, six new):
`_ti1_with_ti2_sibling()` writes the pair the app really produces — the
keyword in the `.ti2` only — and returns the **`.ti1`**, i.e. what opening a
project hands the tab. The premise itself is pinned first
(`test_the_ti1_really_does_not_carry_the_keyword`), so if a future chart
writer starts emitting `TARGET_INSTRUMENT` into the `.ti1` the suite says so
rather than the resolver quietly becoming redundant.

**Mutation proved to land.** Reverting the resolver to
`chart = getattr(self, "_ti1_path", None)` fails exactly 3 of the new tests
(`..._resolves_the_ti2_when_handed_a_ti1`,
`..._stock_chartread_guard_fires_after_a_project_reopen`,
`..._swipe_arrow_stays_off_after_a_project_reopen`); restored, 75 pass.

### 0.3/0.4 — the half that is **not** a CR30 change (F5), own commit

`_refresh_bidir_autodetect` and `_pace_config` made the same unresolved read.
Consequences after any project reopen, all instruments:

| | before | after |
|---|---|---|
| `_detected_instrument` for an i1Pro chart | `None` | `"GretagMacbeth i1 Pro"` |
| `_detected_force_bidir` (the automatic `-b`) | `False` | `True` |
| `_detected_randomized` on a randomised chart | `False` | `True` |
| `_pace_config().min_samples` for a CR30 chart | 20 (the i1Pro row) | 0 |

`RANDOM_START` is printtarg's and is written into the `.ti2`; `is_randomized`
on an existing `.ti1` returns `False` rather than its missing-file `True`,
which is why the flip was silent.

**Tests** (section 13, three new) discriminate on real values, not on the call:
`defaults_for("cr30") == (100.0, None)` vs `defaults_for("i1pro") == (100.0, 20)`.
**Mutation proved to land** — reverting both call sites fails exactly those 3.

Regression: `pytest -k "measure or ti2_loader or cr30 or pace or bidir"`,
**1099 passed**.

