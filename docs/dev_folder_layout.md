# Developer note — the per-run working-folder layout

ChromIQ stores each profiling project as a folder under
`~/ChromIQ/<target-name>/` (or the custom output path). The structure and all
path construction are owned by `core/file_manager.py` via three classes:
`Project`, `Run`, and `Calibration`.

## The layout

```
<target-name>/                       # = sanitised project name (spaces → hyphens)
  project.json                       # manifest (schema_version 2 since #127)
  Where are my files.txt             # folder guide (from ui.file_guide)
  cal/                               # optional; one calibration shared by all runs
    <target-name>-cal.ti1 / .ti2 / .cht / .ps
    <target-name>-cal_NN.tif
    <target-name>-cal.ti3            # calibration measurement
    <target-name>-cal.cal            # printcal output (stem-coupled to -cal.ti3)
    <target-name>-cal.icc
    <target-name>-cal.channels.json
    exports/                         # the cal chart's hand-off sidecars (#127)
    chart/                           # the chart a measurement was taken with
                                     #   (Restore Used Chart reads this)
    old/                             # earlier calibrations — never deleted
      <YYYY-MM-DD_HHMMSS>/           # one folder per rebuild; _2, _3 … if two
                                     #   land in the same second
        <target-name>-cal.ti3 / .cal / .icc    # what cannot be regenerated
        meta.json                    # a COPY; the live one stays in cal/
        chart/                       # the chart that was replaced, whole:
          <target-name>-cal.ti1 / .ti2 / .channels.json / _NN.tif
          exports/                   # …and its hand-off sidecars
    meta.json
  exports/                           # Tools-menu exports (project-wide)
    <target-name>-i1profiler.txt
    <target-name>-i1profiler.pxf
  runs/
    run1/                            # one folder per profile build
      <target-name>.ti1 / .ti2 / .cht / .cie / .ps / .pdf / .channels.json / .strips.json
      <target-name>_NN.tif           # NN = page index (a real ordinal, not state)
      <target-name>.ti3              # the measurement (chartread output)
      <target-name>.icc              # the profile (colprof output)
      preconditioning.ti3 / .icc     # role-named; seeded from a parent run
      merged.ti3 / merged.icc        # role-named; build-time refinement merge
      calibrated.icc                 # role-named; applycal output
      reads/                         # present only when averaging is used
        read1.ti3 / read2.ti3 / …
      reports/                       # #127: things ChromIQ tells the user
        Quality_Check_N_<name>.txt / Refine_Strips_<name>.txt / report_*.json
      exports/                       # #127: hand-off files for other programs
        <name>-colours.txt / <name>-i1profiler.txt / .pxf
      cache/                         # #127: tool intermediates — always safe to delete
        *-patchbox.cht / *-sample.cht / *-diag.tif
      meta.json
    run2/ …
```

**The v2 rule (#127):** everything a user prints, installs or measures stays
at the run root (the Argyll tools are stem+cwd coupled there — chartread runs
with `cwd = ti1.parent`, colprof with `cwd = ti3.parent`, printtarg writes next
to the `.ti1`); the ChromIQ-only paperwork lives in three sub-folders with a
fixed vocabulary: `reports/` (quality checks, refine lists, measurement
reports), `exports/` (hand-off files, same name and meaning as the
project-level folder), `cache/` (intermediates any tool can recreate —
deleting never loses data). External folders (a browsed `.ti3`, a scan
directory) get the same sub-folders via the module-level helpers
`reports_subdir()` / `exports_subdir()` / `cache_subdir()` +
`ensure_subdir()` (which falls back to the parent on read-only volumes).

The **chart's own files** (`.ti1`/`.ti2`/`.ti3`/`.icc`/page TIFFs/`.cht`/`.ps`/
`.channels.json`) carry the sanitised project name as their stem — so
printtarg stamps it on the printed sheet, the built ICC is self-identifying in
ColorSync and Finder, and the install path in the Check tab copies it to the
system folder as `<target-name>.icc`. The **derived/intermediate files** stay
role-named (`reads/readN.ti3`, `preconditioning.*`, `merged.*`,
`calibrated.icc`) — they never go on a printed sheet and the role name is
clearer at a glance than `<target-name>_merged.ti3` would be.

Calibration uses `<target-name>-cal` so its printed sheet shows the project
name (you can tell which project the cal target belongs to) AND is
distinguishable from the profiling chart, which lives in `runs/<id>/` under
the bare project name.

## The one rule

**Role is encoded in the filename within a folder; the folder disambiguates
context.** `runs/run1/chart.ti3` and `runs/run2/chart.ti3` are the same role in
different runs. There are no `pre_`/`cal_` prefixes and no
`_readN`/`_average`/`_merged` suffixes — the folder boundary does that work.

This kills several whole bug classes that the old flat-folder + prefix/suffix
scheme allowed:

- **Cross-run averaging collision** — run 2's `reads/` cannot see run 1's, so
  averaged reads can never be double-counted into a refinement merge.
- **Suffix-stem collisions** — no `set_ti3_path` stripping of `_average`/`_readN`
  to recover a `.ti2`; `chart.ti3` sits next to `chart.ti2`.
- **`.json`-as-CGATS confusion** — pre-conditioning data is a real
  `preconditioning.ti3`, not CGATS hidden under a `.json` name.

## Why Argyll-natural stems (`chart.ti3`, `chart.icc`)

chartread and colprof are **stem-coupled**: reading `chart.ti2` writes
`chart.ti3`; reading `chart.ti3` writes `chart.icc`. Naming the measurement
`measurement.ti3` or the profile `profile.icc` would force a rename after every
tool — reintroducing exactly the stem fragility this layout removes. So the
canonical measurement is `chart.ti3` and the profile is `chart.icc`. The
per-run folder supplies the role context the generic stem lacks.

A refinement merge is the exception that proves the rule: `average -m` writes a
throwaway `merged.ti3`, colprof builds `merged.icc` from it, and
`Run.built_profile_icc()` returns `merged.icc` when present (else `chart.icc`).
Check & Refine always works from the clean `chart.ti3` (Architecture D).

## The API

| Class | Responsibility |
|-------|----------------|
| `Project` | `project.json` manifest; `create` / `load` / `create_or_load`; `current_run()`, `new_run(preconditioning_from=…)`, `all_runs()`; `calibration`, `exports_dir` |
| `Run` | every path in a run folder (`chart_ti1`, `measurement_ti3` → `chart.ti3`, `profile_icc` → `chart.icc`, `merged_ti3/_icc`, `calibrated_icc`, `preconditioning_ti3/_icc`); `reads()`, `next_read_path()`, `promote_measurement_to_read()`, `clear_reads()`, `reset_chart_artefacts()`, `built_profile_icc()` |
| `Calibration` | the `cal/` folder (`cal_path`, `ti1/.ti2/.ti3/.icc`, `chart_tiffs()`, `exists()`, `live_files()`, `result_files()`, `chart_files()`, `archive_to_old()`, `reset()`) |

`Calibration.reset()` **archives, it does not delete** — the window shown before
it runs promises exactly that, and for a while it did not keep the promise.
Results go to the top of `cal/old/<date_time>/` and the whole chart goes to
`cal/old/<date_time>/chart/`; see the method's own docstring for why the chart
is one level down. `chart_files()` is defined by subtraction (live, minus
results) so a sidecar nobody has added yet is covered by construction.

Two entry points:

- `FileManager.project()` — the current target's `Project` (created on first
  access, cached until `set_target_name` changes).
- `Run.for_dir(run_dir)` — a project-less `Run` bound to an explicit folder, for
  path operations where threading the whole `Project` through isn't worth it
  (e.g. the Measure tab deriving the run from the chart's `.ti1` parent).

**Never build a working-folder path by string concatenation outside these
classes.** Adding a new artefact means adding a property to `Run` (and, if it
should be wiped on chart regeneration, listing it in `reset_chart_artefacts`).

## Key flows

- **First profile** — `Project.create` makes `run1`; chart_creator runs in
  `runs/run1/` with stem `chart`; chartread writes `chart.ti3`; colprof writes
  `chart.icc`.
- **Calibration target** — `cal_target=True` routes chart_creator to `cal/`
  with stem `calibration`; detection elsewhere is "ti3 lives in `cal/`".
- **Averaging** — "Measure again" moves `chart.ti3` → `reads/readN.ti3`;
  "Average all reads" runs `average reads/*.ti3` back into `chart.ti3`.
- **Pre-conditioning refinement** — "Use as pre-conditioning profile" makes
  tab_chart capture the parent run id; at Generate-click,
  `Project.new_run(preconditioning_from=parent)` copies the parent's
  `chart.ti3`/`chart.icc` into the new run as `preconditioning.ti3`/`.icc` and
  makes it current. Build-time merge → `merged.ti3` → `merged.icc`.
- **External `-c` profile** — `chart_creator._import_external_preconditioning`
  copies a vendor `.icc` (and sibling `.ti3` when refinement is on) into the
  run as `preconditioning.*`.
- **Session restore** — only `session_target_name` is persisted; every artefact
  path is re-derived from `project.current_run()`.

## Migration

`project.json` carries a `schema_version`; the current format is **2**
(`SCHEMA_VERSION` in `core/file_manager.py`).

- **1 → 2** (#127): `Project.load` migrates in place — creates the
  `reports/` / `exports/` / `cache/` sub-folders per run (and `cal/exports/`)
  and moves only files matching the exact patterns ChromIQ itself writes
  (`_MIG_REPORTS` / `_MIG_CACHE` + the exact sidecar names). User files are
  never touched, nothing is renamed or deleted, the chart chain is explicitly
  protected (even for project names ending in a pattern tail, e.g.
  "X-sample"). Idempotent: a crash mid-migration is healed by loading again.
  The README is regenerated (the one deliberate overwrite). In-place loads
  from a `.ti2`/`.txt` also migrate — `_handle_inside`'s Continue branch runs
  `Project.load`.
- **Too-new schema**: the project opens normally with
  `Project.schema_too_new = True` (valuables sit in the same place in every
  format), and the main window shows a "please update ChromIQ" note at
  session restore. Never downgrade `schema_version`.
- **Pre-project-json folders** (the pre-redesign flat layout): still no
  migration — session restore skips them (the `project.json` existence check
  bails); the user starts fresh.

The full migration matrix is tested in `tests/test_folder_layout_v2.py`
against the frozen schema-1 fixture in `tests/golden/project_v1/` (generated
by `make_v1_fixture.py` against the pre-#127 code — do not regenerate it with
current code). The golden folder-manifest tests in
`tests/test_folder_layout_e2e.py` pin the complete v2 tree per workflow
stage.

## Known edge cases (deferred, not bugs yet)

1. ~~README backfill doesn't run on in-place loads.~~ **Fixed in #127** —
   the "Continue" branch of `_handle_inside` (both loaders) now calls
   `Project.load` on the discovered root, which also runs the v1→v2
   migration for in-place loads.

2. **`.txt` saved into a project's `exports/` folder.** If a user saves
   an i1Profiler measurement `.txt` directly into `<project>/exports/`
   (instead of somewhere outside that ChromIQ then imports), `resolve_txt`
   sees it as "inside the project" and "Continue" runs `txt2ti3` in
   `exports/` — producing `<stem>.ti3` and (via Build Profile) `<stem>.icc`
   in `exports/`, *outside* the runs structure. Unlikely workflow
   (i1Profiler doesn't default to writing into ChromIQ's `exports/`), but
   if it ever bites, the fix is to special-case `parent.name == "exports"`
   in `_handle_inside` and route to the import flow instead.
