# BRIEF for Agent 1: Create Chart assessment (layout engine first)

You are the most demanding tester ChromIQ has. Your job is to find out what the
Create Chart tab ACTUALLY does today, in the real running app, on screen, with
the owner's real look and settings, and to write it down with evidence. You do
not fix anything. You do not change any file under the repository
`/Users/Basti/develop/ChromIQ` (no edits, no new files there, no git commands
that change state). Read-only on the repo. Everything you produce goes into
`/Users/Basti/Desktop/Create Chart Assessment/`.

The owner's steer, verbatim: "i mainly want to improve the layout engine". So
the ChromIQ layout engine (the alternative to Argyll's printtarg; package
`workflow/layout_engine/`, its UI in `ui/dialogs/layout_options_panel.py`,
`ui/margin_inspector_panel.py`, `ui/chart_layout_info_panel.py`, the Manual
module's engine toggle and the Preferences tabs "Chart Layout", "Default Patch
Sizes", "Instrument Limits", "Margin Thresholds") gets the deepest attention.
Everything else in Create Chart is still in scope, but budget your time: roughly
60 % layout engine, 40 % the rest.

He also said: you may create demo projects to expose issues, and you may produce
MOCKUP screenshots of features you suggest (a mockup must be labelled as a
mockup in the filename and inside the image or its sidecar note, never
presented as the app's current state).

## Absolute rules

1. **On screen, real app, real look.** Build the app the way `main()` does
   (fonts, `WinButtonLayoutStyle("Fusion")`, `apply_appearance`,
   `CompositeAppFilter` installed on the QApplication). The proven recipe is
   `build_app()` in `scripts/drive_dg_create_chart_frame_gaps.py`; copy its
   approach into your own driver files. Never `QT_QPA_PLATFORM=offscreen`.
   You have standing permission to drive the app on screen, click real
   controls, open real dialogs, save and LOOK at screenshots (the Read tool
   opens a PNG). If a step is blocked, report exactly what failed, do not
   conclude "on screen is blocked".
2. **Sandbox, always.** Before any Python that imports the app:
   `source "/Users/Basti/Desktop/Create Chart Assessment/Test Runs/sandbox/env.sh"`.
   That points the settings store at a sandbox .ini that mirrors the owner's
   real preferences (appearance = neutral, language = en, log hidden, Argyll at
   /Applications/Argyll/bin) with `custom_output_path=/Users/Basti/ChromIQ-assessment`,
   and points the presets folder at a COPY of his presets. Run the app from the
   repo's venv: `/Users/Basti/develop/ChromIQ/.venv/bin/python`.
   The owner's real projects live in `/Users/Basti/ChromIQ`. Never open, write
   or point the app at them. At the end of your work, prove the sandbox held:
   `diff <(find ~/ChromIQ -maxdepth 1 | sort) "/Users/Basti/Desktop/Create Chart Assessment/Evidence/baseline-before-assessment/chromiq_home_dirs.txt"`
   must be empty, and `defaults read com.chromiq.ChromIQ custom_output_path`
   must still print an empty string. Put both results in your final report.
3. **Modal dialogs.** A driver that blocks on a modal gets clicked by the owner
   himself, which contaminates every result after it. For every step that can
   open a dialog, install a `QTimer.singleShot` auto-answer that first asserts
   the dialog is the one you expected (by title or text), then clicks a NAMED
   button and logs which one. An unexpected dialog is a finding, not an
   obstacle. Never patch `QMessageBox.exec` globally with a default return.
   Mark every finding "unattended" or "human-assisted".
4. **Evidence grades.** Every claim carries one of: OBSERVED (seen on screen in
   the running app), PARTIAL (some aspects seen, some not), INFERRED (from code
   or files, not shown in the UI), UNKNOWN. Never upgrade an inference.
5. **Staged reports so nothing is lost if you are killed.** Write
   `Reports/checkpoint-NN-<topic>.md` after every module or every ~40 minutes,
   whichever comes first. Write one file per finding in
   `Findings/F-NNN-<slug>.md` as soon as you have it (template below). Save
   screenshots in `Screenshots/<module>/<NN>-<what>.png`; drivers and their
   logs in `Test Runs/drivers/` and `Test Runs/logs/`. Do not wait for the end.
6. **No em dash (—) anywhere in what you write.** Use a comma, colon, full stop
   or brackets. The en dash (–) is allowed.
7. **Design specs are binding.** Before judging behaviour in an area a spec
   covers, read the spec: `docs/design/per_target_settings.md`,
   `docs/design/verification_printing_and_target.md` (the From Profile Gamut
   module), `docs/design/calibration_run_type.md`, `docs/dev_builtin_presets.md`,
   `docs/dev_folder_layout.md`, `docs/dev_margin_inspector.md`, and §M of
   `docs/design/unified_measurement_management.md` for message texts. When code
   contradicts a spec, the finding names the rule; it is not "obviously a bug".
8. **Trusted sources for Argyll behaviour:** `/Applications/Argyll/doc/targen.html`,
   `/Applications/Argyll/doc/printtarg.html`, and the source at
   `/Users/Basti/Downloads/Argyll_V3.5.0_orig/target/printtarg.c` and
   `targen.c`. When a help text or tooltip explains an Argyll flag, check it
   against these. When the engine claims printtarg parity, you may run
   printtarg yourself (with `timeout=`) and compare.
9. **Do not run the whole test suite while the app is on screen.** Targeted
   `pytest tests/test_x.py` runs are fine as supporting evidence. Never let a
   subprocess run without a timeout.
10. **One agent.** Do not spawn subagents.
11. **The owner's measurements and projects are developer test data**, never
    ground truth for colour. Judge layout and behaviour, not his colour results.

## Where things are

- Repo: `/Users/Basti/develop/ChromIQ` (branch master, version 4.2.0). Create
  Chart is `ui/tabs/tab_chart.py` (19,469 lines). Modes are Guided, Manual and
  From Profile Gamut (the third button appears only while Run type =
  Verification). The gamut module is embedded in the Manual panel (it replaces
  the targen section; the layout half is shared).
- Layout engine: `workflow/layout_engine/` (instruments, geometry, area_fit,
  margins_fit, raster, presets/LayoutRecipe, cht_writer, ti2_writer,
  vector_pdf, preflight, calibration). Consumers: `workflow/chart_creator.py`
  (`_engine_build_kwargs`, `_engine_kwargs`, `_should_use_engine`),
  `workflow/margin_inspector.py`, `workflow/layout_from_render.py`,
  `workflow/hex_support.py`, `workflow/ti2_relayout.py`.
- Preferences: `ui/dialogs/settings_dialog.py` (tabs Chart Layout ~line 4984,
  Instrument Limits ~3246, Margin Thresholds ~3349, Default Patch Sizes).
- Demo projects (already built, synthetic but schema-faithful) in
  `/Users/Basti/ChromIQ-assessment/`: Demo-Full-RGB, Demo-Verify-History,
  Demo-Legacy-v1, Demo-Legacy-v2. Check the build finished:
  `tail -1 "/Users/Basti/Desktop/Create Chart Assessment/Test Runs/sandbox/make_demo_projects.log"`
  should say `exit 0`. Create as many further projects there as you need. Never
  drive against a project in `~/ChromIQ`.
- Existing on-screen drivers you may copy patterns from (read, do not edit):
  `scripts/drive_dg_create_chart_frame_gaps.py` (app build, pump, grab),
  `scripts/drive_130_test_plan.py`, `scripts/drive_per_target_settings.py`,
  `scripts/drive_preset_reload_real.py`, `scripts/drive_hex_overlay.py`,
  `scripts/drive_helper_markers_move.py`, `scripts/drive_target_ui_restore_clobber.py`,
  `scripts/drive_guided_ss_4x6.py`, `scripts/capture_screens.py`
  (`open_the_project()` shows how to open a project the way the app does, via
  `session_target_name` + `win._restore_last_session()`).
- Tests that describe intended behaviour (read for expectations, they are not
  evidence of behaviour): `tests/test_layout_*.py`, `tests/test_chart_creator_engine.py`,
  `tests/test_helper_markers.py`, `tests/test_engine_info_line*.py`,
  `tests/test_per_target_settings*.py`, `tests/test_clip_example_table.py`.

## Already known and ruled on (verify status briefly, do not re-derive)

These have owner rulings. Record their CURRENT observed state in one line each,
do not spend an hour on them, and do not propose to overturn a ruling. You may
still list them in the regression baseline.

- Chart overwrite with no warning (generating over a chart-only run destroys
  the TIFFs and .ti2 silently; with Auto-update preview on, one spinbox nudge
  does it): DEFERRED by the owner 2026-09-02, "leave it as it is". Do not
  re-analyse. Analysis exists at `~/Desktop/beta7/review/CHART-OVERWRITE/`.
- Helper-marker geometry (markers centred in spacers, minimum 2): SETTLED, do
  not propose changes.
- i1Pro 19 mm bottom margin on A4 portrait / A3 landscape: DELIBERATE (jig
  240 mm limit).
- Guided always uses the engine; the engine toggle governs Manual only; the
  page-label column is reclaimed in the engine (capacity may exceed printtarg):
  accepted design.
- Build-in-flight clobber (a stored `create_chart_ui` overwriting the panel
  after a build): fixed in `_apply_ui_state` via `_layout_owned_by_build`; the
  deeper ordering cause (save runs after the bar defaults to the run) is open
  and awaiting the owner. Worth ONE reproduction attempt with a project whose
  run1 stores a different mode, as in `scripts/drive_target_ui_restore_clobber.py`.

## What to cover (inventory, expected vs actual, edge cases)

Work module by module. For each control or workflow record: name, location,
purpose, inputs, expected result (from label, tooltip, help card, spec, Argyll
doc, or convention), actual result, status (pass / fail / partial), evidence
file, grade. Compare like-for-like functions across Guided, Manual and Gamut and
say whether a difference is intentional, inconsistent, or a bug.

### A. The layout engine (the priority)

1. Manual with engine ON vs engine OFF (printtarg): same instrument, paper,
   patch count; compare page count, patches per page, patch size, margins, the
   info panels, the files written (.ti2, .cht, channels.json, TIFF dpi and bit
   depth, PDF if any). Where printtarg parity is claimed (patch size, spacing,
   stagger, clip border, leader), measure it.
2. Every instrument the engine offers (i1Pro, i1Pro3+, ColorMunki at each
   density, SpectroScan flat and hexagonal, CR30, scanner) on at least A4 and
   one large or custom paper, portrait and landscape.
3. Layout modes: area-first vs patch-first, by-grid with auto columns/rows,
   by-width; min height; patch area alignment. Does the estimate equal the
   rendered count every time? When not, is it explained on screen?
4. Margins: per-edge boxes, "Use instrument margins", the Preferences margin
   thresholds, Instrument Limits (strip length limit), Default Patch Sizes. Do
   they interact as their help text says? Does a threshold change move the
   chart AND the estimate?
5. Furniture: clip border and its content modes (notes box, custom text,
   example table), strip labels and indicator size/font/rotation, underline,
   sheet text, stamp, edge spacers, helper markers (as an overlay proposal vs
   printed), page X/Y. Does each consume the space it draws (capacity accounting)?
6. "Measured from Preview" and "Chart layout information": are the numbers
   right against the render and channels.json? Do they update when they should?
   What happens on a printtarg chart, a loaded external .ti2, an empty run?
7. Auto-update preview: what triggers it, debounce, and what it writes.
8. Presets that carry a layout: Chart Layout defaults per instrument × paper ×
   mode (Preferences), Manual named presets (save, overwrite, delete, undo,
   reload after restart, stale detection), built-in presets (do they switch the
   engine off, and do they say so?). Round trip: save, restart the app, load,
   compare every value.
9. The patch set editor (New patch set / Edit patch set, reached from the
   "last page not full" hint and elsewhere): does the layout survive the round
   trip both ways?
10. Extremes: minimum and maximum of every spinbox, 1 patch, 10,000 patches,
    patch size larger than the page, margins that leave no room, zero rows or
    columns, custom paper at its limits, a strip longer than the ruler. Does the
    app refuse clearly, warn, or produce a broken chart or an exception (check
    the log for `[CRITICAL]`)?
11. Preflight (`workflow/layout_engine/preflight.py` and
    `ui/dialogs/preflight_dialog.py`): when does it run, what does it say, is it right?
12. Vector PDF export and the i1Profiler export sidecars for an engine chart.
13. Scanner path: an engine chart's .cht and hexagons, the sample area cap.

### B. The rest of Create Chart

Guided module (instrument, paper, patch count and quality steps, preconditioning
profile, density options, the name field and its prefix, the estimate column vs
the on-screen count, Generate, the Transfer-to-Manual behaviour), Manual module
(every targen parameter row and expert row, the command preview, the name
fields, the Presets bar, Load existing profile), From Profile Gamut (Run type =
Verification, with and without a profile, the no-profile info box, the count
default), Calibration run type charts, the header icons (load, preset, reveal),
the TIFF preview (zoom, pages, overlays), the run bar (Profile run, New run,
switching runs mid-edit, per-target settings load and write, deleted project
folder), hand-off sidecars and exports, help cards and tooltips (accuracy
against Argyll docs, no history, beginner tone, singular/plural), keyboard
navigation and focus order where observable, window at 1280x800 and at full
width, language de for label overflow (one pass, screenshots only), and the
appearance modes (neutral is his; take one pass in light and dark for
readability only).

Names: empty, duplicate, accents and umlauts, very long, with a slash or
colon, trailing spaces. Files: project folder deleted while open, run folder
missing files, a .ti1 loaded from outside, a legacy project (Demo-Legacy-v1
before and after migration).

## Finding file template (Findings/F-NNN-<slug>.md)

```
# F-NNN <one line>
Area: layout engine | guided | manual | gamut | presets | preview | run bar | help | other
Grade: OBSERVED | PARTIAL | INFERRED | UNKNOWN
Attended: unattended | human-assisted
Type: bug | missing feature | UX | inconsistency | regression risk | unclear requirement | spec conflict
Severity: blocker | high | medium | low
Expected: ...
Actual: ...
Why it matters: ...
Steps to reproduce (click by click): ...
Evidence: Screenshots/... , Test Runs/logs/... , code refs file:line
Spec or source cited: ...
Possible solutions (no code): A ..., B ...
Regression risk if changed: ...
Needs owner decision: yes | no, and the question in one sentence
```

## Final deliverable of this agent

`Reports/AGENT1-final-assessment.md` with these sections, in plain language:
1. What was tested (modules, workflows, how many drivers, how long).
2. What works correctly (the regression baseline: behaviour that must be preserved).
3. Confirmed problems (OBSERVED), likely problems (PARTIAL/INFERRED), areas
   needing further investigation, product decisions, feature suggestions.
4. Inconsistencies between Guided, Manual and Gamut.
5. Fragile areas and regression risks.
6. For each significant issue: problem, what was tested, what was observed,
   why it matters, solution options with pros and cons, your recommendation,
   whether the owner must decide.
7. Questions requiring the owner's decision, numbered.
8. Evidence index (every screenshot and log, one line each).
9. The sandbox proof (rule 2).
Also produce `Reports/AGENT1-functional-inventory.md` (the table from section 3
of the task) and keep `Findings/` complete. Your final chat message to me is a
short summary with counts and the paths; the files are the deliverable.

Optimise for correctness, evidence and completeness, not speed. Try to break
the app. Assume nothing works until you have seen it work.
