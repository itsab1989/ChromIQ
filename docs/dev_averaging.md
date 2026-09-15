# Developer note — averaging repeated measurements

Lets a user read the **same printed chart several times** and average the
measurement sets to cut instrument noise. Triggered from the Measure tab's
completion dialog.

## Status — implemented (beta branch)

Phases 1–4 below are **done** and unit-tested (`tests/test_average_runner.py`):

- `workflow/average_runner.py` — wraps `average` (mean, or median via `-e`).
- `core/file_manager.py` — read naming lives on `Run`: `reads()` /
  `next_read_path()` / `promote_measurement_to_read()` / `clear_reads()`
  (reads/readN.ti3 inside the run folder; see `docs/dev_folder_layout.md`).
- `core/settings.py` — `averaging_enabled` (master switch, default **False**)
  and `average_method` ("mean" | "median", default mean).
- `ui/dialogs/settings_dialog.py` — "Enable measurement averaging" checkbox in
  the Behaviour group, with an extensive tooltip.
- `ui/tabs/tab_measure.py` — when `averaging_enabled`, the averaging choice is
  presented **in the "All Stripes Read" dialog itself** for a normal full read
  (`_show_all_stripes_averaging_dialog`): first read → *Re-read Stripes* /
  *Measure again to average* / *Build Profile →*; mid-set → *Use last read only* /
  *Measure again to average* / *Average all reads & build →* (with a mean/median
  combo). The choice is stashed in `_pending_avg_action`; once chartread writes
  the final `chart.ti3`, `_on_measure_done` promotes it (`_promote_completed_read`
  → `Run.promote_measurement_to_read`) and carries out the action
  (`_apply_completion_action`). "Measure again" accumulates `reads/readN.ti3`,
  "Average" runs `average reads/*.ti3` back into `chart.ti3` then Build Profile.
  Manual mode (or any case where the all-rows-read dialog never fired) falls back
  to the post-process `_handle_measure_complete` → `_show_completion_dialog`.
- `ui/tabs/tab_profile.py` — `set_ti3_path` needs no suffix-stripping: the
  averaged result reuses the canonical `chart.ti3` stem, so its `chart.ti2`
  sits right beside it (edge case #1 dissolved by the per-run layout).

The whole flow is **off by default**, gated behind the `averaging_enabled`
Preferences toggle — with it off, a finished full read proceeds straight to
Build Profile exactly as before (the classic `elif ti3_exists:` branch in
`_on_measure_done`).

**Deferred:** Phase 5 (auto-offer on re-entering a project with prior reads).
**Resolved (was a UX wrinkle):** a full strip read used to show the "All Stripes
Read" dialog and then a second completion dialog. The averaging choice is now
folded into the "All Stripes Read" dialog itself (primary action on the right), so
there is a single dialog and no redundant second popup.

---

## Decision: use ArgyllCMS `average`, don't port the scanner tool

A user pointed at `average_ti3s_rgbgeom.py`
(https://github.com/soul-traveller/average_ti3s_rgbgeom). **Do not adopt it.** It
is built for **scanner** profiling: it takes the geometric median of the
`RGB_*` columns (the scanner's response, the noisy axis there) and copies
`XYZ`/`LAB` unchanged from the first file. It also ignores spectral data.

ChromIQ is the mirror image — a **printer** (`DEVICE_CLASS "OUTPUT"`,
`COLOR_REP "iRGB_XYZ"`):

| Column | Printer (ChromIQ) | Scanner (the tool's target) |
|--------|-------------------|------------------------------|
| `RGB_*` | device values *sent to print* — **identical** every read | scanner response — **noisy** |
| `XYZ_*` / `SPEC_*` | instrument measurement — **noisy** | reference values — **fixed** |

Run on a ChromIQ `.ti3` the tool would median a column that never changes (no-op)
and copy the measurements from read #1 only — discarding the averaging we want,
and dropping the 36 spectral bands. The colleague's *limitation* ("Argyll can't
average repeated scans because it keys on identical device+label") is **scanner-
specific**; for a re-read printed chart the device values and order are identical
and only the measurement varies — exactly the case Argyll's `average` handles.

## What Argyll 3.5.0 `average` actually does (verified against `spectro/average.c`)

Traced for an OUTPUT / `iRGB_XYZ` file in the multi-file path (`average.c:636+`):

- **Averages every real-valued field that is not a device channel**
  (`:737–744` skips the `RGB_*` columns) → `XYZ_X/Y/Z` **and all 36 `SPEC_*`
  bands**, via plain arithmetic mean (`average()`, `:759`/`:850`).
- **Leaves device RGB and the header untouched** — file 1's data is copied
  wholesale (`:264–267`); only measured fields are overwritten. All keywords
  (`SPECTRAL_BANDS`, `TARGET_INSTRUMENT`, `COLOR_REP`, …) and field defs are
  duplicated from file 1 (`:246–255`).
- **Matches patches by position, validating device values** (`:684–695`): for
  OUTPUT files it requires the `RGB_*` values to agree within 0.001 across files
  and patch counts to match (`:661`). `SAMPLE_ID` labels are **not** required to
  match. Re-reading the same chart passes; feeding two *different* charts errors
  out (correct).

Smoke-tested: `average -X realfile.ti3 copy.ti3 out.ti3` reported it averaged
`XYZ_X/Y/Z` + 36 `SPEC_*` bands, and `out.ti3` kept 36 bands / 44 fields.

### Flags — and why geometric median is the wrong tool here

```
-e   Median rather than average (per-component)
-g   Geometric Median of PCS in encoded space
-L   Geometric Median of PCS in L*a*b*
-X   Geometric Median of PCS in XYZ
-m   Merge rather than average
```

Two findings that shaped the plan:

1. **`-X` / `-L` / `-g` only rewrite the `XYZ_*` / `LAB_*` 3-vector** (`:786–824`);
   they never touch the `SPEC_*` bands. When spectral data is present, Argyll
   derives colorimetry **from the spectral bands and recomputes XYZ** — the
   stored XYZ is effectively ignored by colprof. So a geometric median applied
   only to XYZ is **a no-op for ChromIQ's spectral workflow.** → **Don't offer
   `-X`/`-L`.**
2. **With only 2 reads, every method equals the mean.** `median()` returns the
   plain average when `nvals < 3` (`:864`), and Weiszfeld on 2 points degenerates
   to the midpoint. Robust methods only diverge at **≥3 reads.**

The only robust option that reaches spectral is **`-e` (per-component median)** —
it medians every non-device field including each `SPEC_*` band (`:756`). Still
per-band, still needs ≥3 reads to differ from the mean.

**Conclusion:** default to plain `average` (mean). It correctly averages the
spectral data the profile is actually built from, and for the common 2-read case
it's the only thing that matters. Optionally expose a `mean`/`median` toggle where
`median` (`-e`) only does anything at ≥3 reads — but v1 can ship without it.

---

## File-naming scheme (per-run layout)

Averaging lives entirely inside one run folder (`runs/<id>/`, see
`docs/dev_folder_layout.md`):

- Per-read snapshots: `reads/read1.ti3`, `reads/read2.ti3`, … (**accumulate**)
- Averaged result: written back to the canonical `chart.ti3` (the averaged
  measurement *is* the canonical one — colprof builds from it).

There are no prefix/suffix conventions and no cross-run lookup: `Run.reads()`
lists exactly one folder (`reads/`), so a different run's reads can never be
picked up. This is what makes the old "averaged reads double-counted into a
refinement merge" bug impossible — the reads of run 1 sit in
`runs/run1/reads/`, run 2 averages `runs/run2/reads/`, and the merge only ever
sees `chart.ti3` + `preconditioning.ti3`.

`Run` owns the naming: `reads_dir`, `reads()`, `next_read_path()`,
`promote_measurement_to_read()` (moves `chart.ti3` → `reads/readN.ti3`),
`clear_reads()`.

---

## Implementation phases

> **Historical — superseded by the per-run folder layout.** The phases and
> edge cases below describe the *original* design, which used flat
> `<base>_readN.ti3` / `<base>_average.ti3` files and the now-removed
> `FileManager.read_variant_path` / `existing_read_variants` helpers. The
> shipped implementation moves the per-read snapshots into `runs/<id>/reads/`
> and averages back into `chart.ti3` (see the **Status** and **File-naming
> scheme** sections above, and `docs/dev_folder_layout.md`). Edge case #1
> (matching `.ti2`) and the cleanup concern (#5) dissolve under the per-run
> layout; the planning text is kept for provenance only.

### Phase 1 — `average` wrapper
**New `workflow/average_runner.py`** (mirror `workflow/printcal_runner.py`):
- `@dataclass AverageParams`: `inputs: list[Path]`, `output: Path`,
  `method: str` (`"mean"` | `"median"`).
- `_build_args()` → `average [-e] in1.ti3 in2.ti3 … out.ti3` (`-e` only for
  `median`; no `-X`/`-L`).
- `run(params, on_finish)` dispatched through the singleton `ArgyllRunner.run()`
  (respects the `is_running` guard).
- Small error-pattern list à la `_PRINTCAL_ERROR_PATTERNS` for the failure modes
  the source can raise: field count/type mismatch (`average.c:642–649`), patch
  count mismatch (`:661`), device value differs across files (`:691`), CGATS read
  error (`:202`). Map each to a friendly message.

### Phase 2 — FileManager naming helpers
**`core/file_manager.py`** static helpers (keep naming in one place):
- `read_variant_path(base_ti3, n) -> <base>_read{n}.ti3`
- `average_path(base_ti3) -> <base>_average.ti3`
- `existing_read_variants(work_dir, base_stem) -> list[Path]` — sorted `_readN`
  files whose stem does **not** start with `pre_`/`cal_`.
- `next_read_index(...)` → max existing N + 1.

### Phase 3 — Success dialog + "Measure again" flow (core)
**`ui/tabs/tab_measure.py`, `_on_measure_done` (`:3287`, full-success branch).**
Today that branch only writes `[OK]` to the log and auto-proceeds. Change **only**
the full-success, non-cal, non-partial case
(`ti3_exists and self._all_done_shown and not is_cal`); leave the partial-resume
and `cal_` paths exactly as they are.

New `QDialog`, sized to fit (`setMinimumWidth(~560)`, word-wrapped body),
styled via `tint_dialog_primary(dlg, _TAB_COLOR)`. Contents branch on how many
reads exist:

- **Only the base read so far (no `_readN`):**
  - *Continue to Build Profile* — current default action.
  - *Measure again to average* — explains noise reduction; on click: rename
    `<base>.ti3 → <base>_read1.ti3`, set `self._averaging_active = True`, re-run
    the normal measurement (same ti1/ti2/settings via the existing start path).
    Next completion writes `<base>.ti3`, renamed to `<base>_read2.ti3`.
- **≥2 `_readN` files exist:**
  - *Average all reads & build* → `average_runner` over all `_readN` →
    `<base>_average.ti3`, then proceed with that file.
  - *Use last read only & build* → proceed with `<base>_read{N}.ti3`.
    **Amended 2026-09-15 (B8-213).** In the per-run layout the reads live in
    `reads/readN.ti3`, where `measurement_report._find_reference_ti2` cannot
    see the run's chart, so this ending left the run holding no measurement at
    all: no row in the Measurement Report window, a dated report filed into
    `reads/reports/` against a device reference, and an unmeasured run after a
    restart. The chosen read is now COPIED back to `Run.measurement_ti3` and
    that is what is proceeded with, exactly as the *Average* ending does with
    its result; `reads/` still keeps every read. Edge case 1 below is what this
    realises, by placing the file rather than by stripping a suffix.
  - *Measure again* → accumulate one more (`_read{N+1}`).
  - (Optional) a `mean`/`median` toggle, with median greyed/annotated "needs 3+
    reads".

State to add: `self._averaging_active: bool`; the read count is **recomputed**
from `existing_read_variants()` (not just held) so re-entering a project stays
consistent.

**"Proceed with X" = `measure_finished.emit(X)`.** Routing already exists:
`measure_finished → main_window._on_measure_done (ui/main_window.py:342) →
_tab_profile.set_ti3_path(...)`. Whichever path is emitted becomes the profile's
active `.ti3`. No profile-tab change needed for the happy path.

### Phase 4 — averaging method setting (only if the toggle ships)
Add `"average_method": "mean"` to `core/settings.py` DEFAULTS so the dialog
remembers the last choice. Skip if v1 ships mean-only.

### Phase 5 — detect prior reads on entering a project (follow-up)
When a project already holds ≥2 `_readN.ti3` and no `_average.ti3`, offer to
average. Lightest hook: in the measure tab's `set_ti1_path` (or when the working
dir is established) call `existing_read_variants()`; if ≥2, surface a non-modal
prompt: *"Found N prior reads — average them, or add another?"* Build after
Phase 1–3 are proven.

---

## Edge cases
1. **Matching `.ti2` for the chosen file.** The profile tab emits `ti2_found`
   only when `<stem>.ti2` sits next to the `.ti3` (`ui/tabs/tab_profile.py:230`).
   `<base>_average.ti2` won't exist → "print again" / refinement linkage breaks.
   **Fix:** make the ti2 lookup strip a trailing `_readN`/`_average` suffix
   (preferred), or copy `<base>.ti2 → <base>_average.ti2`.
2. **Profile output name** becomes `<base>_average.icc` (colprof uses the `.ti3`
   stem). Descriptive — recommend keeping it for traceability rather than forcing
   `<base>.icc`.
3. **`is_running` guard** — "Measure again" must wait for chartread to fully exit
   before relaunching. Naturally satisfied: the dialog only appears post-
   `_on_measure_done`.
4. **Field / patch / device-value mismatch** between reads — `average` errors
   (`average.c:642–695`); surface it and do not emit success.
5. **Cleanup** — `_readN`/`_average` files should survive `clean_folder` between
   steps but be removable on a true "start over". Check against the extension-
   based cleanup in `workflow/chart_creator.py`.

## Verify before shipping
- Two **real** back-to-back reads of one chart → confirm `average` produces sane
  averaged XYZ/spectral and the profile builds from `_average.ti3`.
- (If the toggle ships) a 3-read `-e` median sanity check vs. mean.
