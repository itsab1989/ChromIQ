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
QT_QPA_PLATFORM=offscreen pytest -n auto            # everyday tier, ~10,370 tests, ~1:55
QT_QPA_PLATFORM=offscreen pytest --runslow -n auto  # THE RELEASE GATE, ~10,380 tests, ~3:10
```

The suite is two-tiered: ~20 heavy end-to-end profile-build tests carry
`@pytest.mark.slow` and are skipped by a plain `pytest` run; `--runslow`
includes them. **Any merge/release decision requires a green `--runslow`
run** — the everyday tier alone is not a gate.

**THE SUITE PAINTS THROUGH FUSION, BECAUSE THE APP DOES.** `main.py:147` runs
`app.setStyle(WinButtonLayoutStyle("Fusion"))` before it builds a window, on
every platform. The suite never calls `main()`, so until 2026-09-03 it took
whatever the platform plugin gave: **fusion** under `offscreen`, **macos** under
`cocoa`, **QWindows11Style on Windows**. Three platforms, three styles, none of
them the app's — and every size, rect and pixel this suite asserts on comes out
of the style. `tests/conftest.py::_one_qapplication_per_worker` now pins Fusion.

Not the `WinButtonLayoutStyle` proxy itself: it overrides only
`SH_DialogButtonLayout` and draws nothing, but it is a *Python* `styleHint` in
front of a hint Qt asks for constantly. Everyday tier, `-n auto`, same machine,
back to back: platform default **106.6 s**, `setStyle("Fusion")` **114.5 s**,
`setStyle(WinButtonLayoutStyle("Fusion"))` **133.2 s** — and the proxy run also
turned one unrelated test red that passes alone. `tests/test_the_suite_paints_
with_the_shipped_style.py` pins Fusion, and pins that `main.py` still builds on
it.

This **may** be why the Windows gate crashed in `QStyle::drawControl` while the
running app rendered the same widgets correctly all evening. It is a lead, not a
finding: neither the report nor either gate log records whether
`QT_QPA_PLATFORM=offscreen` was set for those runs, and if it was, that gate was
already on Fusion and the style is innocent. The line is right either way — a
gate should measure what ships.

**A DEAD WORKER MUST END THE RUN — `--max-worker-restart=0` IS IN `addopts`.**
The crash banner below only fires from `pytest_terminal_summary`, so it is worth
nothing if the session never ends, and on 2026-09-03 it did not: on the owner's
Windows ARM64 VM a worker died at 99 %, xdist spawned a replacement, execnet's
bootstrap for that replacement raised `OSError: [Errno 22] Invalid argument`, and
the controller waited for a node that never reported. Two `--runslow` attempts,
no summary, no exit code, both killed by hand. Measured here with a deliberate
`ctypes.string_at(0)`: without the flag **nine** restarts, each re-running the
same crashing test; with it, one FAILED and a clean exit.

**A RED GATE MEANS SOMETHING AGAIN, AND SO DOES A GREEN ONE.** Measured
2026-09-02, on ten gate runs: **four of them crashed a worker**, and what
happened next was decided by nothing anybody controls.

* A worker that died **while running a test** made pytest-xdist mark whatever
  item it was holding as `FAILED` — a bystander that passes on its own — with
  the real cause two quiet lines back in a wall of dots. An hour went into
  deciding whose change it was. It was nobody's.
* A worker that died **after reporting its tests** was recorded as nothing at
  all: `LoadScopeScheduling.remove_node` returns None when the node has no
  pending item, so the run printed `N passed` and **exited 0 with a dead
  process in it**. Reproduced on the real suite (`215 passed`, exit 0) and now
  caught (`215 passed`, exit 1).

`tests/conftest.py` implements xdist's `pytest_testnodedown`: any worker that
goes down with an error is named in a red banner in the summary and **forces a
non-zero exit**. Nothing is retried, skipped or hidden — a crash still crashes;
it simply cannot be read as a test failure, and cannot be a pass.

**TWO DUMPS LOOK ALIKE AND MEAN OPPOSITE THINGS. READ THE FIRST LINE.**

| what you see | what it is |
|---|---|
| `Fatal Python error: …` and `[gwN] node down` | a worker DIED. The banner fires, the run exits non-zero, and any test in the FAILED list is a bystander — re-run it alone before believing it |
| `Timeout (0:0X:XX)!` then a thread dump | `faulthandler_timeout` on a test that was merely slow. Harmless. No banner, no failure |

A reviewer read the second as the first, in a GREEN run, and reported that "the
segfault trace appears in green runs too". It does not. `faulthandler_timeout`
is now **300**, not 90: measured with `--durations=40`, the slowest single test
in the suite is `test_engine_v2_options.py::test_spectral_physics_flag_runs_challenge`
at **83 s**, so 90 left it seven seconds of headroom and the dump fired on any
loaded run — 7 of the 20 gate logs on disk. 300 is 3.6x the slowest test and
still names a genuine hang inside five minutes.

**AND THE CRASH WAS OURS, IN SHIPPED CODE.** `ui/fade_scroll.py` connected a
scroll bar's `rangeChanged` to a lambda capturing `self`. PyQt6 6.11 faults
invoking that closure when the signal is emitted re-entrantly — SIGSEGV,
`EXC_BAD_ACCESS ... address=0x20`, a `Py_INCREF` on a pointer read from
NULL+0x20 inside `_PyEval_EvalFrameDefault`. The re-entrancy comes from
`ButtonFontFilter.relayout_around`, which runs `layout.activate()` inside an
application event filter and makes `QScrollAreaPrivate::updateScrollBars` call
`setRange` inside itself — and `main.py` installs that filter, so **the app runs
this path too**. Bisected on a standalone reproduction that faults on the eighth
widget build: an empty slot body still crashes (so it is not the work), a lambda
capturing nothing does not (so it is the capture), a bound method does not. The
fix is a bound method: 208 builds clean, twice, where the lambda died on build 8.
`tests/test_a_scrollbar_signal_never_takes_a_lambda.py` keeps it that way.

**Do not reach for a self-capturing lambda as a slot on a signal a widget's own
child emits.** Give the class a named method and connect that: PyQt keeps a weak
reference to a bound receiver and lets Qt sever the connection when it dies,
instead of parking a Python closure inside a C++ object on the far side of the
cycle.

`pytest.ini` scopes collection to `tests/` (via `testpaths`). Without it a
bare `pytest` recurses into `.venv/` and — with `pytest-qt` active —
collection appears to hang for many minutes. Anything far beyond the times
above means something is wrong (a test opening a modal dialog `.exec()`, or
`.venv` being scanned again), not just "slow tests".

**Run the gate in parallel — it is the difference between 2.5 minutes and 19.**
`--dist loadfile` keeps each file on one worker, which the session-scoped
fixtures need. Parallel was avoided because a run once hung for 2.5 h; that was
`targen` without a `timeout=`, now fixed.

**Use `-n auto`.** `pytest.ini` caps it at 12 workers (`--maxprocesses=12`),
which is a CEILING and not a pin — on a smaller VM `auto` still wins, so the
same command is right on every host. Measured on the full gate, 2026-08-24,
6953 tests:

| workers | result | wall |
|---|---|---|
| 4 | 7085 passed | 7:48 |
| **auto** | **7085 passed ×3** | **~2:58** |

Measured 2026-08-25 on 7,085 tests, three consecutive runs, zero failures.

Re-measured 2026-09-02 at `-n auto` on 9,713 collected items:

| when | runs | wall | worker crashes |
|---|---|---|---|
| before the fade-scroll fix | 10 | 3:21 – 9:18 | **4** |
| after it | 4 | 3:17 – 3:59 | 0 |
| after the whole change set | **6** | **3:15 – 3:30** | **0** |

Ten post-fix `--runslow` runs in total, every one green and exit 0, and no
`Timeout (0:0X:XX)!` dump in any of the last six either — that is the
`faulthandler_timeout` change. The everyday tier on the same day:
**9,384 passed, 325 skipped, 1:42**.


**THE INTERMITTENT FAILURES ARE FIXED, AND IT WAS NOT THE WORKER COUNT.**
179 test files created their own `QApplication` in a MODULE-scoped fixture and
dropped it at teardown — and destroying a `QApplication` sip-deletes every
remaining QObject in the process, while `ui/widgets.py` held the app's settings
in a module global across that boundary. A different victim each run, every one
passing alone. `tests/conftest.py` now pins one `QApplication` per worker; no
test file needed changing, because they all ask `QApplication.instance()` first. Twelve is the cheapest point on a plateau: `--dist loadfile` cannot
finish faster than its slowest single file (`tests/test_engine_v2_options.py`,
157 s on one worker), and this host has 12 performance cores plus 4 efficiency
ones, so past 12 the extra workers land on slow cores.

**THIS FILE USED TO SAY THE OPPOSITE, AND IT COST FIVE MINUTES A RUN FOR
SIXTEEN DAYS.** It said "use `-n 4`, and do not raise it — more is faster and
NOT reliable", with a table showing 30 failures at 8, 45 at 12, 17 at auto.
That was true when it was written (2026-08-05) and was fixed three days later
by the two commits it was itself asking for:

- `322c3d20` — `tests/conftest.py::pytest_configure` replaces
  `core.settings.QSettings` with a per-process sandboxed `.ini`. That is the
  shared state the old note blamed by name ("101 test files construct
  `AppSettings()`, which is the real `QSettings` store").
- `b30b0ad8` — the leaked `QMessageBox.exec` patch, the other cross-test leak.

Nobody came back to update the numbers. **If you change how the suite is run,
re-measure and rewrite this section in the same commit.**

A cap CAN be applied from configuration, which this file also used to deny.
`--maxprocesses` works from `addopts` and `PYTEST_ADDOPTS` (xdist applies
`min(numprocesses, maxprocesses)` in `pytest_cmdline_main`, after addopts are
parsed), as does `PYTEST_XDIST_AUTO_NUM_WORKERS`. Only the
`pytest_xdist_auto_num_workers` **conftest hook** is too late to help.

`--dist loadfile` keeps each file on one worker, which the module-scoped
fixtures need. Parallel was once avoided because a run hung for 2.5 h; that was
`targen` without a `timeout=`, now fixed.

**Where the time actually goes** (instrumented, 2026-08-24): the gate is purely
CPU-bound — at `-n 4` all four workers finish within 6 s of each other, so there
is no straggler to chase, just four cores of sixteen doing 1,829 s of work.
Argyll subprocesses are **5.6 %** of it (103 s across 376 processes) and
`inspect.getsource` **0.2 %**. The expensive part is **Qt widget construction in
function-scoped fixtures** — `tab` (a real `TabChart`) alone is 221 s over 101
constructions, ~2.15 s each. Module-scoping those would save ~20 s at `-n 12`
and risks exactly the cross-test leakage the two commits above were needed to
fix; not worth it.

**The demo-project cache is worth ~2:00** (measured at `-n 12`: cold 4:54, warm
2:54). Worker count is worth 4:47. Both matter; the cache is not the bigger one.

**Measured on a 16-core M-series (12 performance cores), 4367 tests — HISTORIC,
from when the suite was 40% smaller:**

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

**…and a timeout that is too TIGHT is a phantom red.** The other half of the
same rule, learned 2026-09-02. `test_webengine_shutdown` spawned a subprocess
that builds a real `QWebEngineView` and waited `timeout=60`. Measured idle, that
subprocess costs **1.2 s** — a fifty-fold margin — and the gate still blew
through 60 s, because the gate saturates every core. The run came out red with
`subprocess.TimeoutExpired` and the thing the test actually guards (that the
process exits cleanly) was never evaluated at all. Budget a subprocess for the
loaded machine, not the idle one, and make a timeout say *"did not finish"*
rather than letting a bare `TimeoutExpired` read like a crash.

**Real Argyll builds are expensive individually** (though only 5.6% of a
whole gate — see above). The demo projects in
`scripts/make_demo_projects.py` cost 30-70 s each. There is ONE session-scoped
build for the whole suite — the `demo_projects_root` / `demo_project` fixtures
in `tests/conftest.py`. Use those; a second fixture of your own means the same
projects get built twice per run. Tests copy what they use, because
`Project.load` migrates in place.

**Never call `qapp.setStyleSheet()` in a test.** It re-polishes every widget the
suite has alive — two tests that took 0.2 s alone cost 29 s inside a full run.
Style the widget under test instead; it measures the same thing.

## Driving the app on screen — sandbox the settings FIRST

```bash
export CHROMIQ_SETTINGS_FILE=/tmp/chromiq-driver.ini   # then run the app/driver
```

**A script that drives ChromIQ on screen builds a real `AppSettings`, which is
the real preferences store.** Setting an output path — or merely resizing the
window — writes into the settings the user works with every day. Set
`CHROMIQ_SETTINGS_FILE` and the app physically cannot reach the real store;
unset, nothing changes (`core/settings.py`, `tests/test_settings_can_be_sandboxed.py`).

**Backing the plist up first is NOT enough, and this is the part that cost a
day.** One driver left `custom_output_path` pointing at a temp folder that was
later swept. ChromIQ then looked for every project in a directory that no
longer existed and quietly found none — which reached the owner as "the
already-exists line has stopped appearing", nowhere near the cause. Three
separate runs afterwards reported "no drift" by comparing the plist against a
backup **that already contained the bad value**.

So when a run is over, do not check that the file matches your backup. Check the
VALUE:

```bash
defaults read com.chromiq.ChromIQ custom_output_path   # must be the user's, or unset
```

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
- **No em dash (—) in new or modified user-facing text.** It is one of the
  clearest tells of machine-written prose, and a comma, a colon, a full stop or
  brackets almost always read better anyway. The 1,225 strings that carried one
  before this rule (2026-09-06) are frozen in `tests/data/em_dash_baseline.json`
  and are NOT to be swept; but a string you touch for any reason stops matching
  the baseline, so clean its dash while you are in there.
  `tests/test_no_new_em_dash_in_user_facing_text.py` enforces it over `tr()`
  literals, `data/parameters.yaml` and the §M catalogue, and separately refuses
  a translation that adds an em dash its English source does not have. The en
  dash (–) is deliberately untouched: it is the correct dash in German and
  Norwegian. If one is genuinely unavoidable, put the string in
  `tests/data/em_dash_allowed.json` with a real reason. Never add it to the
  baseline, which only shrinks: `python scripts/em_dash_check.py --report`
  says where it stands, `--prune` tidies it.
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

### The design specifications are binding

`docs/design/` holds the agreed specifications for #130. Knut's rule
(2026-08-06):

> *"These must always be consulted on changing code so that behaviour defined is
> not violated. And if faults are found that do not match with the specification
> [it] must be reviewed and approved."*

Two obligations, and the second is the one that is easy to get wrong:

1. **Before changing code in an area a specification covers, read that
   specification.** Not the memory of it — Knut edits his posts and the
   documents are updated from them, so a remembered version is a stale one.
2. **A fault that contradicts the specification is not simply fixed.** Report
   it, say which rule it breaks, and get the change reviewed and approved
   before implementing it. "The code disagrees with the spec, so I corrected
   the code" is only right when the spec is right; when the *spec* is what
   needs to change, that is Knut's call, not ours.

| Document | Covers |
|---|---|
| `unified_measurement_management.md` | the life of a measurement: endings, `.ti3` states, the §M message catalogue |
| `per_run_description.md` | the description / notes fields, `-D`, and the run lifecycle |
| `measurement_exit_strategy.md` | every window that can end a measurement, and the key each button sends |
| `per_target_settings.md` | which settings belong to a target, and when they are loaded and written |
| `per_target_settings_test_plan.md` | how that is proved — on-screen, every parameter, both states |
| `measurement_window_sounds.md` | which sound each measurement window plays, and when |
| `calibration_run_type.md` | calibration as a run type |
| `tool_availability.md` | which Tools apply to which run-type/profile-run selection, and where each may write (**DRAFT — awaiting confirmation**) |
| `verification_printing_and_target.md` | printing a verification chart through its profile, and #133's profile-tailored target — condition→action tables mapped to code (**DRAFT — awaiting confirmation**) |

New user-facing message text is governed by §M of
`unified_measurement_management.md`: it goes to §M-PROPOSED first and is not
written into a tab until it is approved. `tests/test_message_catalogue.py`
enforces that.

**Only CONFIRMED behaviour may be written into a specification.** Knut,
2026-08-08:

> *"only the behavior that you confirm as correct, after bugs are confirmed
> fixed, should be written into the design specification. Otherwise the
> specification looses its value with lots of trash Claude thinks is correct
> behavior."*

The gate is **a human's confirmation, not your own on-screen run**. A driver
proves what the app *does*; only Knut or Sebastian can say that what it does is
what it *should* do. So behaviour you have verified but nobody has confirmed
goes into an **`⏳ Awaiting confirmation`** section carrying
`**Confirmed by:** *nobody yet.*`, and is promoted to `Confirmed behaviour`
with a `**Confirmed by:** <name>, <date>` line only after they say so.
`tests/test_design_specs_are_binding.py` fails on a "Confirmed" section that
names nobody — because this rule was broken within an hour of being agreed.

MONITOR MODE: before every monitor cycle and after any context
 compaction, re-read MONITOR.md in full and follow it.
