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


## Change A — no stock fallback for a chart stock chartread refuses (F4)

`MeasureParams.stock_reader_cannot_read: bool = False`
(`workflow/measure_manager.py:190`), set in `TabMeasure._apply_engine_params`
**before every early return** — it is a property of the chart, not of the
engine, so the manager needs it whichever reader runs.
`NOT_A_SETTING["stock_reader_cannot_read"]` added
(`workflow/measure_settings.py:41`); `tests/test_measure_settings.py`'s drift
guard is green.

**All three relaunch sites gated**, as A.3 requires:

| site | how |
|---|---|
| `_engine_mode_fallback` (`:389`) | `and not self._stock_reader_cannot_read` |
| `_engine_should_resume_fallback` (`:401`) | the whole `if was_engine:` block |
| `_engine_should_fall_back` (`:427`) | a new block **above** it that ends the run |

The new block ends on the helper's own exit — `on_finish(code)` — and emits
`engine_fallback_refused(reason)`. It is placed above the third site rather
than inside `_engine_should_fall_back` so a refused chart cannot reach *any*
`_launch_stock`, including a future fourth caller.

**A.4 — the C-side request is in §"Requests for the C side" below.** Meanwhile
the reason is as informative as Python can make it: `_engine_fatal` is only
ever set from a typed JSON event, so a helper that dies before emitting one
left the log saying `(unknown error)` while its own sentence sat one line above
it, on stderr, as prose (log 8583 vs 8586). `_HELPER_FATAL_RE` captures
`…chartread: Error - <sentence>` into **`_engine_error_prose`**, and
`_engine_failure_reason()` prefers `_engine_fatal`, then the prose, then
`"unknown error"`.

⚠ **It is deliberately a separate field.** `self._engine_fatal is not None` is
a fallback *trigger* in both `_engine_should_fall_back` and
`_engine_should_resume_fallback`. Folding captured prose into it would silently
change when an ordinary i1Pro chart falls back — mavtop's rescue. Pinned by
`test_prose_capture_never_sets_the_fallback_trigger`.

**A.5 — §M.** `M_CR30_READ_ENDED` / `M-CR30-READ-ENDED`, `approved=False`, in
`CATALOGUE`, in `AWAITING_APPROVAL`, and defined in §M-PROPOSED of
`docs/design/unified_measurement_management.md` (both the header list and a
defining heading) — all in the one commit, as the rule requires.
Rendered by `TabMeasure._on_engine_fallback_refused`. i18n: the two new keys
are in all 12 catalogues; `de` carries a real translation (Du-Form), because
`test_the_catalogue_is_actually_translated_into_german` rejects a placeholder.

**Tests** (`tests/test_engine_fallback.py`, 12 new). Normal: the reported bug —
one launch, `finished == [1]`, no "ArgyllCMS" sentence. Boundary: exit 0 is
untouched; a user-stopped run raises no failure message. Error: the resume
site with a genuinely resumable `.ti3` (`has_any_readings` asserted as the
premise) still does not relaunch, and its reassurance is never printed.
Guard against over-reach: `test_an_ordinary_chart_still_falls_back` keeps
mavtop's i1Pro1 rescue.

**Mutation proved to land.** Removing all three gates fails 5 of the new tests
and no others; restored, 45 pass. Regression across
`-k "measure or engine or cr30 or message_catalogue or ti2_loader"`:
**1392 passed, 23 skipped**.

### Deviation from the change list

**A is not a window.** A.5 says only "the user-facing sentence goes to
§M-PROPOSED", and the two neighbouring handlers (`_on_engine_fell_back`,
`_on_engine_fell_back_resumed`) write to the measurement log and flash the
status bar rather than opening a modal. This one follows them. If Basti wants
a modal for a run that has *ended* rather than switched readers, the text is
already a §M `Message` and `_on_engine_fallback_refused` is the single place to
change. **Listed as open item 1.**


## Change C — patch-by-patch locked on for a CR30 chart (F6)

**Order deviation, deliberate:** C was implemented before B. §5.1 of the
critique proves C is a *correctness* requirement for B —
`MeasureManager.start` derives `self._spot_mode` from `params.patch_by_patch`,
and `skip_current_strip` branches on it, so `-x` with `patch_by_patch` False
puts the helper in spot mode while the manager believes it is in strip mode.
Landing B first would have created a commit with that defect in it.

### The resolver is the authority

`_resolve_patch_by_patch(mode)` (`ui/tabs/tab_measure.py:1319`) — a CR30 chart
is always True, otherwise the module's own box. Called from all three live
readers: `_collect_guided`, `_collect_manual`, and `_is_pbp_checked` (which was
rewritten to delegate; it drives ~10 downstream behaviours through
`_spot_session`). Readers 4 and 5 in the manager follow for free.
`grep -n '_pbp_cb\.\|_m_pbp_cb\.' ui/tabs/tab_measure.py` now returns nothing
outside the three new helpers.

⚠ **This is where the first mutation attempt failed, and it is worth
recording.** Deleting the `if self._chart_is_cr30(): return True` branch left
all 89 tests green — because the widget lock had ticked the boxes, so a test
that reads the resolver cannot tell the resolver from the widget. That is the
exact "correct by accident" failure §3.3 warns about. Two tests were added that
separate them (`test_the_resolver_decides_and_not_the_widget`, and the same
through the real store via `measure_settings.apply`), and the mutation then
fails both. **The suite would have shipped a widget-only lock.**

### Presentation, and the write-guards

`_apply_cr30_pbp_lock()` follows `TabChart._apply_calibration_knobs`:
snapshot the tick **and the tooltip** once (`_pbp_lock_snapshot`, with the #137
R1 `is None` guard so engaging twice cannot capture the forced values), tick,
`setEnabled(False)`, swap in a `tr()` literal that names the reason and how to
get the control back, and restore all three exactly on release. Both members of
`_LINKED_PAIRS` are locked, with signals blocked so the mirror stays out of the
snapshot's way. **Not hidden** — `_bool_row_m` does not even keep a handle, and
`tab_measure.py:1243` forbids reading a control the user cannot see.

`_pbp_user_value(mode)` is what every *saved* copy is written from — the two
global keys in `_on_save_defaults` and `"pbp"` in `_m_collect_preset_data`
(F6). `_set_pbp_user_value(mode, value)` is what every *load* writes through —
`_restore_defaults`, the Manual restore, and `_m_apply_preset_data` — so a
preset applied while locked lands in the snapshot and becomes what the user
gets back, instead of showing an unticked box over a ticked read.

Re-asserted at every point the chart or the settings change (C.5): in
`set_ti1_path` beside `_refresh_bidir_autodetect`, and beside
`_reassert_guided_refinement()` on **both** exits of `load_target_settings`.

### Tests and mutations

13 new in `tests/test_cr30_registration.py` §14, covering C.7 (a)-(d) plus the
resolver-authority pair, the round trip with a *ticked* box, double engagement,
`chart_instrument` being ignored (C.6), and `-p` actually reaching
`MeasureManager._build_args`.

| mutation | result |
|---|---|
| resolver ignores the chart | **2 fail** (after the two new tests; 0 before) |
| global writers read the widget again | 2 fail |
| no restore on unlock | 3 fail |
| snapshot retaken on every call | 1 fail |

### One existing test needed a stub extended (not weakened)

`tests/test_measure_settings.py`'s `wired` fixture copies selected real methods
onto `_WiredTab`. `load_target_settings` now re-asserts the lock on both exits,
so `_apply_cr30_pbp_lock`, `_chart_is_cr30` and `_chart_file_for` joined
`_reassert_guided_refinement` in that list — the same reason the comment
already there gives for `_reassert_guided_refinement`. The stub has no
`_ti1_path`, so the lock answers "not a CR30" and does nothing.

Regression: `-k "measure or engine or cr30 or preset or target_settings or
i18n or message"`, **2090 passed, 199 skipped**.

