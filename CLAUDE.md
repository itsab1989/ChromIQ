# CLAUDE.md — ChromIQ

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -r requirements-dev.txt   # test-only tools (pytest, pytest-qt)
```

## Run

```bash
source .venv/bin/activate
python main.py
```

## Test

```bash
source .venv/bin/activate
QT_QPA_PLATFORM=offscreen pytest -n auto            # everyday tier, ~4320 tests, ~1 min
QT_QPA_PLATFORM=offscreen pytest --runslow -n auto  # THE RELEASE GATE, ~4370 tests, ~2.5 min
```

The suite is two-tiered: ~20 heavy end-to-end profile-build tests carry
`@pytest.mark.slow` and are skipped by a plain `pytest` run; `--runslow`
includes them. **Any merge/release decision requires a green `--runslow`
run** — the everyday tier alone is not a gate.

`pytest.ini` scopes collection to `tests/` (via `testpaths`). Without it a
bare `pytest` recurses into `.venv/` and — with `pytest-qt` active —
collection appears to hang for many minutes. Anything far beyond the times
above means something is wrong (a test opening a modal dialog `.exec()`, or
`.venv` being scanned again), not just "slow tests".

**Run the gate in parallel — it is the difference between 2.5 minutes and 19.**
`--dist loadfile` keeps each file on one worker, which the session-scoped
fixtures need. Parallel was avoided because a run once hung for 2.5 h; that was
`targen` without a `timeout=`, now fixed.

**`-n auto` asks the machine, so the same command is right everywhere** — 16
workers on the 16-core host, however many a smaller VM has. Measured identical
to a hand-tuned `-n 12` here (gate 151s vs 153s, everyday 69s vs 68s), so
adapting costs this machine nothing and stops the numbers below being a lie on
weaker hardware. `--dist loadfile` is in `pytest.ini`'s `addopts` because it is
not optional: 150 test files use module-scoped fixtures, and distributing
individual tests would scatter a module across workers. A plain serial `pytest`
is unaffected by it.

**Both tiers now sit within ~10s of their structural floor**, which is the
single heaviest FILE — `--dist loadfile` cannot split one:

| tier | total work | ideal split | floor (heaviest file) | actual |
|---|---|---|---|---|
| everyday | 452s | 38s | **57s** `test_scan_alignment_real_targets.py` | 69s |
| release gate | 881s | 73s | **145s** `test_engine_v2_options.py` | 151s |

So more workers cannot help either tier. The only remaining lever is making
those two files faster (the gate's is dominated by one ~90s test), and that is
a test-content change, not a scheduling one.

**Measured on a 16-core M-series (12 performance cores), 4367 tests:**

| | wall time |
|---|---|
| serial | 18:57 |
| `-n 4 --dist loadfile` | 6:25 |
| `-n 12 --dist loadfile` | 4:20 |
| `-n 12` + the demo-project cache, **cold** | 4:06 |
| `-n 12` + the demo-project cache, **warm** | **2:29** |

**Worker count was never the real limit — the demo-project build was.**
"Session-scoped" means *per worker process* under `pytest-xdist`, so every
worker that touched `demo_projects_root` built its own copy: two files need it,
so the gate paid ~4 minutes twice, in parallel, and could not finish faster than
one of them:

```
234.26s setup  tests/test_report_readable_on_dark.py
229.38s setup  tests/test_legacy_migration.py
 89.99s call   <the next slowest thing in the whole suite>
```

`tests/conftest.py` now caches that tree on disk, keyed by the generator
(`scripts/make_demo_projects.py`) **and** the ArgyllCMS binaries that built it,
so an Argyll upgrade or a generator edit rebuilds it and nothing else does.
Delete `$TMPDIR/chromiq-demo-projects-cache`, or point `CHROMIQ_DEMO_CACHE`
elsewhere, to force a rebuild. Every consumer still copies what it uses, because
`Project.load` migrates in place.

**Do not edit source files while a gate is running.** Many tests asserts on
`inspect.getsource(...)`, which reads from disk — an edit mid-run shifts line
offsets and produces dozens of failures that look like real regressions and are
not. It cost one full run to learn.

**Anything that shells out to Argyll in a test needs a `timeout=`.** A
`subprocess.run` without one waits for ever, and `targen -G` can wedge: the
suite once sat on that single call for two and a half hours with no output.
When a run does appear stuck, `pytest --timeout=300 --timeout-method=thread`
(pytest-timeout) makes the stack name the test instead of guessing.

**Real Argyll builds are the expensive part.** The demo projects in
`scripts/make_demo_projects.py` cost 30-70 s each. There is ONE session-scoped
build for the whole suite — the `demo_projects_root` / `demo_project` fixtures
in `tests/conftest.py`. Use those; a second fixture of your own means the same
projects get built twice per run. Tests copy what they use, because
`Project.load` migrates in place.

**Never call `qapp.setStyleSheet()` in a test.** It re-polishes every widget the
suite has alive — two tests that took 0.2 s alone cost 29 s inside a full run.
Style the widget under test instead; it measures the same thing.

## Build distributable

```bash
source .venv/bin/activate
pip install pyinstaller
pyinstaller ChromIQ.spec
# Result: dist/ChromIQ.app
```

## Architecture

ChromIQ is a PyQt6 GUI for RGB printer ICC profiling with ArgyllCMS 3.5.0.

**Workflow**: `targen → printtarg → [print] → chartread → colprof`

### Module map

| Directory | Purpose |
|-----------|---------|
| `core/` | Settings, ArgyllRunner (QProcess), FileManager, logging, resource_path |
| `data/` | Patch capacity database, parameters.yaml (all CLI flags + tooltips) |
| `ui/` | All Qt widgets — main window, 4 tabs, shared TIFF preview, settings dialog |
| `workflow/` | Business logic — chart creation, PS generation, CUPS printing, measure, profile |

### Data flow

`parameters.yaml` → `ParameterWidget` rows in panels → `workflow/*.py` builds CLI args
→ `ArgyllRunner.run()` → `QProcess` → line_received signal → LogWidget + stripe detection

### Working-folder layout (Project / Run)

Every project is a folder under `~/ChromIQ/<target-name>/` owned by the
`Project` / `Run` / `Calibration` classes in `core/file_manager.py`:

```
<target-name>/             # = sanitised project name (spaces → hyphens)
  project.json             # manifest: schema_version (2), current_run, runs[]
  cal/                     # optional, shared across runs
    <target-name>-cal.*    # cal.ti1/.ti2/.ti3/.cal/.icc/_NN.tif
    exports/               # the cal chart's hand-off sidecars
  exports/                 # Tools-menu i1Profiler exports (project-wide)
  runs/run1/, run2/, …     # one folder per profile build
    <target-name>.*        # chart.ti1/.ti2/.cht/.ps/.channels.json + _NN.tif
    <target-name>.ti3      # the measurement (chartread output; averaged result reuses this stem)
    <target-name>.icc      # the profile (colprof output)
    reads/readN.ti3        # role-named, only when averaging is used
    reports/               # #127: Quality_Check_N/Refine_Strips + report_*.json
    exports/               # #127: -colours.txt + -i1profiler.txt/.pxf sidecars
    cache/                 # #127: tool intermediates (scanin working copies, diags) — always safe to delete
    preconditioning.ti3/.icc   # role-named, seeded by Project.new_run when refining
    merged.ti3/.icc        # role-named, build-time refinement-merge outputs
    calibrated.icc         # role-named, applycal output
    meta.json
```

Projects written before #127 (schema_version 1, everything flat in the run
folder) are migrated in place by `Project.load` — see the Migration section
of `docs/dev_folder_layout.md`.

**The chart's own files carry the sanitised project name as their stem**
(so printtarg stamps it on the printed sheet, the ICC is self-identifying,
Finder shows it). Derived/intermediate files (`reads/readN.ti3`,
`preconditioning.*`, `merged.*`, `calibrated.icc`) stay role-named — they
never go on paper. **The per-run folder still removes the need for any
prefix/suffix state encoding**, so the `pre_`/`cal_` prefixes and the
`_readN`/`_average`/`_merged` suffixes are gone. File stems follow
ArgyllCMS's natural coupling (`<name>.ti2` → `<name>.ti3` → `<name>.icc`),
so no post-tool renames are needed.

**All path construction goes through `Project` / `Run` / `Calibration`.**
Adding a new artefact = add a property/method to `Run`, never a stem pattern
elsewhere. `FileManager.project()` returns the current target's project;
`Run.for_dir(dir)` gives a project-less Run for path ops on a known folder.
Cross-run isolation makes the old "averaging reads double-counted into a
refinement merge" bug impossible by construction. See
`docs/dev_folder_layout.md`.

### Key patterns

**ArgyllRunner** is a singleton `QObject` injected into all workflow classes.
Only one process runs at a time — `is_running` guard checked before each operation.

**resource_path()** in `core/resource_path.py` resolves asset paths for both
development and PyInstaller frozen bundles.

**parameters.yaml** drives `ParameterWidget` creation automatically — add a new
parameter there and it appears in the UI without code changes.

**Patch capacity DB** in `data/patch_db.py` — empirical values from Argyll 3.1/3.5
measured with `printtarg -i<instr> -p<paper> -t300 -L`.  Unknown combos fall back
to binary search in `workflow/chart_creator.py`.

### Printing pipeline

TIFF → `PostScriptGenerator` (hex RGB, PS Level 2, exact PageSize, no scaling)
→ tempfile → `lp -d <printer> -o raw` — bypasses ColorSync and CUPS filters.

### ArgyllCMS binaries

Default path: `/Applications/Argyll/bin`  
Configurable in Settings dialog. The app shows a statusbar warning if binaries are missing.

### Translations (i18n)

UI language is a Settings option (restart-to-apply). `core/i18n.py` provides
`tr("English text")` — a plain string-catalog lookup against
`data/i18n/<code>.json` (key = exact English source string, miss = English).
`data/parameters.yaml` is translated separately by a
`data/i18n/parameters.<code>.yaml` overlay merged in `translate_parameters()`.

Rules when touching UI code:
- Wrap every new user-facing literal in `tr()`; runtime values use
  `tr("… {name} …").format(name=…)` (placeholders are part of the key).
- Count-bearing messages get explicit singular/plural variants, never `(s)`.
- After string changes run `python scripts/i18n_extract.py --missing de`
  and add the German translations — `tests/test_i18n.py` fails CI on missing
  keys, stale keys, placeholder mismatches, and over-long short labels.
- Adding a language = new `data/i18n/<code>.json` (with `@language_name`)
  + `parameters.<code>.yaml`; the Settings combobox discovers it automatically.
  `python scripts/i18n_agent/new_language.py <code> "<English>" "<Native>"`
  prints a complete, self-validating translation-agent prompt (style contract,
  hard rules, validation commands). Partial work staged in
  `data/i18n/staging/<code>.partial.json` is picked up automatically.

### Adding a parameter

1. Add entry to `data/parameters.yaml` with `tool`, `flag`, `type`, `default`, `tooltip_title`, `tooltip_body`.
2. Set `no_space: true` if value must be appended directly to flag (e.g. `-il` not `-i l`).
3. Set `expert_only: true` to hide in collapsed "Expert" section.
4. No code changes needed — `ParameterWidget` picks it up automatically.

### Adding a built-in (non-deletable) Create Chart preset

The Create Chart → Manual **Presets** dropdown can host hard-coded presets that
the user can't delete (e.g. "TC9.18 by Pharmacist", which loads a bundled `.ti1`
and runs printtarg only). The full mechanism, file/function map, gotchas, and a
step-by-step recipe are in **`docs/dev_builtin_presets.md`** — read it before
adding another.

MONITOR MODE: before every monitor cycle and after any context
 compaction, re-read MONITOR.md in full and follow it.
