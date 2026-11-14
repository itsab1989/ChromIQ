# Adding an instrument: the checklist

The strict companion to [`docs/adding_an_instrument.md`](adding_an_instrument.md).
The guide explains why; this file says what, where, and how it is checked. It is
written for coding agents and for reviewers. Work through the stages in order;
copy the stage lists into your pull request and mark every item **done**,
**not applicable (why)** or **open**.

Most items name the file, the test or the command that checks them. The
others (a plan, a rule about defaults, a property of the commands) are checked
by the reviewer against the evidence in the pull request: the options table,
the command list, the photographs and the comparison output. A path
written as `path::name` is a definition in that file. Where an item names an
existing instrument's code, it is a worked example of that one step, not a
template for the whole instrument.

## Standing rules (hold for every stage)

- **R1. Sandboxed settings.** Before any script imports app code:
  `CHROMIQ_SETTINGS_FILE` (a scratch `.ini`), `CHROMIQ_PRESETS_DIR` and the
  output folder (`custom_output_path`) in scratch locations. Check afterwards
  by value that your real settings are unchanged.
- **R2. On-screen proof in a real window**, never `QT_QPA_PLATFORM=offscreen`
  or `widget.grab()` for proof. Build the `QApplication` like the app
  (`scripts/capture_screens.py::build_app`, or at least
  `core/numeric_locale.py::pin_c_numeric_locale`), start a
  `scripts/onscreen_capture.py::PopupWatchdog`, photograph with
  `scripts/onscreen_capture.py::capture_window` on macOS (elsewhere, the
  system's screenshot tool on the real window), and give the
  keyboard back (`scripts/onscreen_capture.py::FocusGiveBack`).
- **R3. No real printer** from a script, and no command to a real device from
  a script that was not built for it.
- **R4. Specifications are binding** (`docs/design/`). Read the covering one
  before you change code; a conflict is raised on GitHub, not fixed in
  passing; new behaviour goes under "⏳ Awaiting confirmation" with
  `**Confirmed by:** *nobody yet.*` (`tests/test_design_specs_are_binding.py`).
- **R5. §M first.** Every new window: ID and text in §M-PROPOSED of
  `docs/design/unified_measurement_management.md` and in
  `workflow/measurement_messages.py` with `approved=False`, word for word
  (`tests/test_message_catalogue.py`).
- **R6. 13 languages and a second pass.** Every string in `tr()`, in all 13
  `data/i18n/<code>.json` and `data/i18n/parameters.<code>.yaml`; no em dash
  in new English text; an independent translation review
  (`tests/test_i18n.py`, `tests/test_no_new_em_dash_in_user_facing_text.py`).
- **R7. Paths and settings.** Paths only through `Project` / `Run` /
  `Calibration` (`core/file_manager.py`); settings only in
  `core/settings.py::AppSettings` (`tests/test_settings_can_be_sandboxed.py`).
- **R8. No device data** (readings, calibration, memory, recordings, session
  folders) in the repository, its tests or a pull request.
- **R9. The gate.** One green `--runslow` gate on the final tree, exit code
  read from pytest itself (Stage 10).
- **R10. Do not rewrite an existing test to make a change pass**; name any
  guard you had to change, and why.
- **R11. Do not change another instrument's code as a side effect.** Report
  what you notice in an issue; in your work, other instruments only need to
  stay unchanged (their tests green, the file comparison of Stage 10).

## Stage 0. Before any code

- [ ] **0.1** An issue "New instrument: <make and model>" exists
      (`.github/ISSUE_TEMPLATE/feature_request.yml`).
- [ ] **0.2** The facts are collected (guide, section 5): one module holds
      every number about the instrument with its value, source and
      confidence, and the layout code reads only from it. Example:
      `workflow/i1io/table_facts.py`.
      *Check:* `git grep` finds no instrument number outside that module in
      your layout code.
- [ ] **0.3** No fact marked as a guess drives a command, a movement or a
      timing (Stage 8).
- [ ] **0.4** The route is chosen (guide, section 4) and written in the
      issue. It depends on what the driver returns: one reading per patch
      (the external-values route of 7.1), or a whole strip at once (agree a
      design in the issue first).
- [ ] **0.5** The plan covers every stage below, row by row, and has been
      challenged by someone who did not write it; the findings are folded in.

**Done means:** an issue with the facts (sources, confidence), the route and a
challenged plan.

## Stage 1. The Beta switch

- [ ] **1.1** One switch module, nothing heavy imported: setting name,
      `stored_value`, `latch_from`, `<name>_enabled`,
      `set_enabled_for_this_process`. Example: `workflow/i1io/support.py`.
- [ ] **1.2** Default `False` in `core/settings.py::DEFAULTS`, with a comment
      that says what "off" means.
- [ ] **1.3** Latched once in `main.py` when it changes what the window
      offers; otherwise read at every Start
      (`tests/test_i1pro2_lights_beta_option.py::test_the_measure_tab_reads_the_setting_at_every_start`).
- [ ] **1.4** Preferences > Beta row in `ui/dialogs/settings_dialog.py`:
      checkbox, ⓘ (`ui/tooltip_button.py::TooltipButton`), restart hint where
      needed. The ⓘ says what it adds, the limits, how the facts were found,
      whether it was tried on real hardware, what a tester can check and how
      to report, and that off changes nothing.
- [ ] **1.5** Consent window when switched on: no icon, "Keep it off" the
      default, the confirm button marked as the risky choice, own risk said
      plainly; Cancel unticks; switching on again asks again. Examples:
      `ui/dialogs/settings_dialog.py::SettingsDialog._on_i1io_support_clicked`,
      `ui/dialogs/settings_dialog.py::SettingsDialog._on_i1pro2_lights_clicked`.
      *Check:* a test like
      `tests/test_i1pro2_lights_beta_option.py::test_switching_on_asks_and_cancel_keeps_it_off`.
- [ ] **1.6** Every hook in shared code asks the switch before reading any
      file; instrument modules are imported lazily.
- [ ] **1.7** A chart for the instrument opened with the switch off is
      refused at Start with a window naming the option (example
      `workflow/measurement_messages.py::M_I1IO_SUPPORT_OFF`), never
      "corrected" to another instrument.
- [ ] **1.8** Stale settings: saved defaults naming the instrument read as
      "none" while off; a target's stored values are carried back unchanged
      while the user has not changed them, using the shared rules in
      `workflow/beta_chart_carry.py` (`workflow/beta_chart_carry.py::carry_chart_keys`,
      `workflow/beta_chart_carry.py::OffSnapshot`) through thin wrappers
      (example `workflow/i1io/support.py::off_snapshot`). Measure-tab keys
      live in a dict of their own in `workflow/measure_settings.py`, never in
      `workflow/measure_settings.py::MEASURE_CONTROLS`.
- [ ] **1.9** The four nets, each in its own test file or process (examples
      `tests/test_i1io_off_changes_nothing.py`,
      `tests/test_i1io_off_stale_project.py`):
      1. a child process builds the real window and Preferences with the
         switch off, from fresh and from stale settings: the instrument in no
         list, its modules not loaded beyond the switch module;
      2. the Measure tab with the switch off reads no chart to find out
         whether it is the instrument's, and the layout engine refuses the
         instrument's code as unknown;
      3. the shared files that name the instrument are pinned in a
         `HOOKED_FILES` set, and a test compares it with a scan of the
         source tree for the instrument's names;
      4. a real project made with the switch on, opened with it off and its
         tabs changed: `meta.json` byte-identical; a change the user makes is
         kept; another instrument's chart generated into the run leaves no
         trace.
- [ ] **1.10** For a change to an instrument's own commands: with the option
      off, the driver sends exactly what the unchanged upstream driver sends,
      and the helper starts with the previous release's command line
      (`tests/test_i1pro2_lights_driver.py::test_option_off_puts_on_the_wire_exactly_what_argyll_does`,
      `tests/test_i1pro2_lights_beta_option.py::test_off_starts_the_helper_with_exactly_todays_command_line`).

**Done means:** the four nets green, and the file comparison of Stage 10
identical with the switch off.

## Stage 2. Create Chart registration

Lists:

- [ ] **2.1** Guided list: `data/patch_db.py::INSTRUMENT_LABELS`, filtered by
      the switch where the combo is filled in `ui/tabs/tab_chart.py`
      (`data/patch_db.py::EXTERNAL_INSTRUMENTS` only for instruments another
      program lays out).
- [ ] **2.2** Manual's instrument choice: `data/parameters.yaml` (`choices`,
      `labels`, a `tooltip_body` bullet) and all 13
      `data/i18n/parameters.<code>.yaml`; filtered while off
      (`ui/tabs/tab_chart.py::_without_choice`), bullet only while offered
      (example `ui/tabs/tab_chart.py::i1io_instrument_bullet`).
- [ ] **2.3** Layout panel and Preferences > Chart Layout:
      `ui/dialogs/layout_options_panel.py::LayoutOptionsPanel.INSTRUMENTS`, or
      behind the switch the
      `ui/dialogs/layout_options_panel.py::LayoutOptionsPanel.instruments`
      classmethod.
- [ ] **2.4** Preset groups and built-ins, if any:
      `ui/tabs/tab_chart.py::INSTRUMENT_GROUP_LABELS`,
      `ui/tabs/tab_chart.py::BUILTIN_PRESET_GROUPS`, `docs/dev_builtin_presets.md`.
- [ ] **2.5** Margin labels and instrument limits:
      `ui/tabs/tab_chart.py::_MARGIN_INSTR_LABEL`,
      `workflow/layout_engine/instruments.py::_MARGIN_LABEL_TO_KEY`,
      `core/settings.py::THRESHOLD_INSTR_LABEL`,
      `ui/dialogs/settings_dialog.py::SettingsDialog._MARGIN_INSTRUMENTS`,
      `core/settings.py::default_margin_thresholds`. Fixed geometry is
      minimum margins, not "no margins".

Layout:

- [ ] **2.6** Full name for files:
      `workflow/layout_engine/instruments.py::TARGET_INSTRUMENT_NAME` (vendor
      included; a family name where one entry stands for a family).
- [ ] **2.7** Geometry: `workflow/layout_engine/instruments.py::_build_base`
      and `workflow/layout_engine/instruments.py::supported`; with the switch
      off `workflow/layout_engine/instruments.py::build` refuses the code
      (model `tests/test_cr30_registration.py`).
- [ ] **2.8** Settings fixed for the instrument are applied at one chokepoint
      (example `workflow/i1io/chart.py::fixed_build_kwargs`, applied in
      `workflow/layout_engine/instruments.py::geom_from_build_kwargs` and
      `workflow/layout_engine/chart.py::build_chart`).
- [ ] **2.9** Engine routing: `workflow/chart_creator.py::ENGINE_INSTRUMENTS`,
      `workflow/chart_creator.py::ENGINE_ONLY_INSTRUMENTS` when `printtarg`
      cannot lay it out (not in `workflow/ti2_relayout.py::PRINTTARG_INSTRUMENTS`;
      model `tests/test_a_cr30_is_always_an_engine_chart.py`).
- [ ] **2.10** Own drawing only where the engine has nothing (example: marks
      and side file after rendering, `workflow/i1io/chart.py::draw_furniture`,
      `workflow/i1io/chart.py::write_side_file`). Own packing, if truly
      needed, goes through `workflow/layout_engine/geometry.py::compute`,
      `workflow/layout_engine/geometry.py::placement`,
      `workflow/layout_engine/geometry.py::strip_rects_px`,
      `workflow/layout_engine/geometry.py::patch_rects_px`, each branch asking
      the switch.
- [ ] **2.11** A sheet check before any file is written (example
      `workflow/i1io/chart.py::check_sheet`); for a camera or scanner type
      reader, the instrument's own detector on a synthetic scan of every
      page.
- [ ] **2.12** Printer edge note (`workflow/printer_edges.py`): marks the
      instrument needs are never called "text"; advice that can be followed
      (example `workflow/measurement_messages.py::M_I1IO_EDGE_MARKS_NOT_PRINTED`).
- [ ] **2.13** Papers: `workflow/layout_engine/papers.py::list_papers`,
      `workflow/layout_engine/papers.py::ENGINE_EXCLUDED_PAPERS`,
      `data/patch_db.py::EXCLUDED_PAPERS`, `data/patch_db.py::PAPER_FALLBACK`.
- [ ] **2.14** `.ti2` keywords of your own declared through
      `workflow/layout_engine/ti2_writer.py::build_ti2_text`; every other
      chart's `.ti2` byte for byte as before.
- [ ] **2.15** Patch set editor: `workflow/ti2_relayout.py::instrument_to_flag`
      and the label map in `ui/dialogs/ti2_relayout_dialog.py`; a refusal only
      if really needed, recorded in `docs/design/tool_availability.md`.
- [ ] **2.16** A sheet that lies turned on the instrument is shown turned by
      a preview rule (`ui/tiff_preview.py::TiffPreview.set_rotation_rule`,
      example `workflow/i1io/support.py::display_rotation_for`); files never
      turned; no rule for any other chart.
- [ ] **2.17** Capacity from geometry; Guided's count equals what is printed.

**Done means:** a fresh window with the switch on offers the instrument in
Guided, Manual and Preferences > Chart Layout, Generate makes a chart that
passes the sheet check, and the four nets of Stage 1 are still green.

## Stage 3. Options: open, explained, saved everywhere

- [ ] **3.1** An options table in the pull request: every Create Chart,
      Preferences and Measure option, each **works**, **works with limits**
      (which, why) or **unavailable** (why).
- [ ] **3.2** The rule: unavailable only when the option has no meaning for
      the instrument or the chart cannot be built with it; never because a
      careless value could spoil a reading. Where an existing list greys more
      than this, the rule wins. *Check:* every "unavailable" row in 3.1 names
      one of the two reasons.
- [ ] **3.3** Behaves as the other instruments do: allowed, with a warning
      where they warn. Example of such a warning: a margin below the
      instrument's minimum from Preferences is still built, and the
      "Measured from Preview" panel flags that edge
      (`workflow/margin_inspector.py::check_violations`).
- [ ] **3.4** Defaults are the safest values; the pull request says why for
      each.
- [ ] **3.5** An unavailable control's tooltip starts with its own reason
      (example `ui/dialogs/layout_options_panel.py::i1io_greyed_why`), and the
      control shows the value the instrument uses; every control gets its
      value back when the user leaves the instrument
      (example `ui/dialogs/layout_options_panel.py::LayoutOptionsPanel._i1io_show_what_applies`).
      Every input type is covered; the test finds inputs independently.
      Model test:
      `tests/test_i1io_layout_options.py::test_the_unfreed_controls_are_live_and_the_rest_say_why`.
- [ ] **3.6** Existing controls reused (patch size, inter-patch gap, strip
      gap, Pages, Custom paper, Resume, strip recognition); no duplicates.
- [ ] **3.7** Every working option survives Save as Defaults (Guided and
      Manual, across a restart), presets
      (`workflow/layout_engine/presets.py::PresetStore`), a target's own
      settings (`docs/design/per_target_settings.md`) and the chart's record
      (`workflow/layout_engine/presets.py::LayoutRecipe.from_channels_json`).
- [ ] **3.8** **One table-driven test over every recipe field** through all
      four places, failing for a field added later without persistence.
      Model: `tests/test_layout_presets.py::test_all_fields_persist_through_named_dict`
      with `tests/test_layout_presets.py::test_the_full_recipe_really_is_full`.
      An instrument-only field added to that test's skip list names the test
      of your own that covers it.
- [ ] **3.9** Instrument-only fields are written only for that instrument
      (`workflow/layout_engine/presets.py::LayoutRecipe.to_dict`); every other
      recipe's dict unchanged
      (`tests/test_i1io_aiming_crosses_ui.py::test_a_recipe_and_a_preset_keep_the_answer`).
- [ ] **3.10** Choosing the instrument loads its own stored or default
      values; a chosen value is never overwritten
      (`docs/design/per_target_settings.md` §4c, D-1 to D-4). Guided never
      reads Manual's widgets. Another instrument's built-in preset switches the
      instrument (`ui/tabs/tab_chart.py::TabChart._leave_engine_only_for_builtin`).

- [ ] **3.11** **The parity test is green with your instrument in it**:
      `QT_QPA_PLATFORM=offscreen pytest tests/test_instrument_parity.py -q`.
      It finds your instrument by itself (Guided's list, printtarg's `-i`
      choices, the layout panel, `data/patch_db.py::INSTRUMENT_LABELS`, every
      Beta switch on) and compares it with the reference (`i1`) in Guided,
      Manual and Manual with the engine off: controls shown, greyed (with a
      visible reason) and their defaults; every option kept by Save as
      Defaults, the preset bar, a named preset, the target's own settings and a
      new project after Save as Defaults; options the reference's panel keeps
      and yours does not;
      switching instruments there and back; every run type; Preferences'
      label style. *Check:* do not edit the test or
      `scripts/instrument_parity.py` to make your instrument pass.
- [ ] **3.12** Every difference it reports is in
      `tests/data/instrument_parity_allowlist.json` with a reason in one plain
      sentence: under `"intended"` when it is your design, under
      `"known_to_review"` (what you saw) when you are not sure. *Check:* the
      pull request lists the entries you added or changed, and no entry of
      another instrument was edited except where your change really changed
      that instrument (and then the pull request says why).

**Done means:** the options table complete, every "unavailable" justified by
3.2, the table-driven test green, and tests/test_instrument_parity.py green.

## Stage 4. Every run type

- [ ] **4.1** Profiling, Verification and Calibration
      (`core/measurement_target.py::RUN_TYPES`; Calibration while "Enable
      calibration options" is ticked) each make charts for the instrument in
      Guided and Manual. Model: `tests/test_i1io_run_types.py`.
- [ ] **4.2** Their files land where the run type keeps them
      (`docs/dev_folder_layout.md`), side files included.
- [ ] **4.3** Whatever does not work yet for a run type is said in a visible
      window (§M), never by silent absence.
- [ ] **4.4** `docs/design/calibration_run_type.md` and the Verification
      parts of `docs/design/per_target_settings.md` read; conflicts raised.
- [ ] **4.5** The parity test's `run_type` rows show nothing for your
      instrument (every run type is offered and builds), or each row is on
      the allow-list together with the visible window of 4.3 that explains it.

**Done means:** a test per run type, and an on-screen photograph of each.

## Stage 5. Old saves build as they were built

- [ ] **5.1** A field that changes how old recipes lay out has a "new
      version" mark, set by default for everything made now and read as old
      only for an unmarked dict from disk. Model:
      `workflow/layout_engine/presets.py::LayoutRecipe.clip_border_free_space`
      (`LayoutRecipe.from_dict` versus `LayoutRecipe.from_build_kwargs`).
- [ ] **5.2** Each in-memory path is tested as new: Guided to Manual, Guided's
      build, Save as Defaults after loading an old preset, a new project.
- [ ] **5.3** A default that may change later is stored explicitly once
      chosen.
- [ ] **5.4** Panel, record and print agree after load, after Generate and
      after reopening.
- [ ] **5.5** Checks and warnings for an existing chart read that chart's
      recorded recipe.
- [ ] **5.6** The chart records what it was made with; a missing record
      reads as "unknown" (example `workflow/i1io/chart.py::aim_recorded`).
- [ ] **5.7** Recipes, presets and a project saved by the previous release
      build byte-identical charts with the branch (Stage 10).

**Done means:** 5.1 to 5.6 each covered by a test, and 5.7 shown by the
comparison output in the pull request.

## Stage 6. Loading charts and their files

- [ ] **6.1** Recognising the chart reads only header bytes (or
      `core/text_io.py::read_text`), never raises, answers "not mine" on any
      error, and runs only while the switch is on (example
      `workflow/i1io/support.py::chart_names_i1io`). Always-offered
      instruments: `ui/ti2_loader.py::KNOWN_INSTRUMENTS`,
      `ui/ti2_loader.py::instrument_family`. Tests:
      `tests/test_target_instrument_gate.py`,
      `tests/test_instrument_matches_chart.py`,
      `tests/test_chart_instrument_comes_from_the_chart.py`.
- [ ] **6.2** FWA: `workflow/fwa_gate.py` (`workflow/fwa_gate.py::ARGYLL_FWA_INSTRUMENTS`);
      illuminant and observer: `ui/ti2_loader.py::spectral_options_unavailable`.
- [ ] **6.3** Side files: `core/file_manager.py::CHART_COMPANION_SUFFIXES`
      and `workflow/chart_import.py::_CHART_EXTS`.
- [ ] **6.4** `.ti2` header lines through the engine's writer; a `.ti3` of
      your own carries `CREATED`, and a test proves `colprof` accepts it.
      TIFF stamped like other charts
      (`workflow/chart_creator.py::_stamp_tiff_metadata`).

**Done means:** a chart for the instrument is recognised, copied, imported
and restored with all its files, and a `.ti3` of your own is accepted by
`colprof` in a test.

## Stage 7. Measure tab

- [ ] **7.1** Routing at `ui/tabs/tab_measure.py::_on_start`: either the
      chartread route (for a driver that returns one reading per patch,
      chartread with external values, `-xx`,
      `workflow/measure_manager.py::MeasureParams.external_values`, answered by
      a bridge like `workflow/cr30/measure_bridge.py::Cr30MeasureBridge`),
      which gets the whole preflight by itself, or a start method of your own
      that runs every guard `_on_start` runs, in its order. Today that is
      `ui/tabs/tab_measure.py::_recover_engine_autosave`,
      `ui/tabs/tab_measure.py::_blocked_by_new_run`,
      `ui/tabs/tab_measure.py::_blocked_by_missing_chart_file`,
      `ui/tabs/tab_measure.py::_blocked_by_unreadable_locations`,
      `ui/tabs/tab_measure.py::_blocked_by_the_instrument_being_in_use` (the
      instrument lease),
      `ui/tabs/tab_measure.py::_blocked_by_unusable_target_instrument`,
      `ui/tabs/tab_measure.py::_blocked_by_a_misfitting_measurement`,
      `ui/tabs/tab_measure.py::_blocked_by_a_differing_condition`, then
      `ui/tabs/tab_measure.py::_verification_guard`,
      `ui/tabs/tab_measure.py::_snapshot_verification_chart`,
      `ui/tabs/tab_measure.py::_confirm_replacing_measurement` and
      `ui/tabs/tab_measure.py::_stage_verification_for_resume`, with the
      instrument-specific guards in between where they apply to yours. Read
      `_on_start` itself before you copy this list: it is the source of
      truth. A test proves your start runs them in that order.
- [ ] **7.2** A chart that cannot be measured yet is answered at the top of
      Start with a window (example `ui/tabs/tab_measure.py::_refused_as_an_i1io_chart`,
      `workflow/measurement_messages.py::M_I1IO_NOT_YET`).
- [ ] **7.3** Controls that do not apply are greyed with a reason
      (`ui/tabs/tab_measure.py::_apply_cr30_dead_options`); the parameter lock
      (`ui/tabs/tab_measure.py::_set_settings_enabled`) is never lifted
      during a read.
- [ ] **7.4** Pace row: `core/measure_pace.py::MODEL_DEFAULTS`,
      `core/measure_pace.py::ESTIMATE_PATCHES`, `core/measure_pace.py::model_key`,
      `core/measure_pace.py::_OTHER_MODEL_KEYS`, the pace table in
      `ui/dialogs/settings_dialog.py`;
      `tests/test_b202_every_offered_instrument_has_its_pace_row.py::NO_STRIPS`
      or `tests/test_b202_every_offered_instrument_has_its_pace_row.py::DEVICES`.
- [ ] **7.5** Instrument lease: `core/instrument_lease.py::acquire` with
      `core/instrument_lease.py::MEASURE_TAB`, `core/instrument_lease.py::release`
      on every ending; busy window `ui/tabs/tab_measure.py::_instrument_busy_window`.
- [ ] **7.6** Endings: `ui/tabs/tab_measure.py::_confirm_end_of_session`,
      `ui/tabs/tab_measure.py::_show_page_pause`; replaced measurements
      archived (`workflow/measurement_session.py::MeasurementSession`); a
      partial result belongs to its own chart only; resume bound to the
      device's identity, never to a network address;
      `docs/design/measurement_exit_strategy.md`,
      `docs/design/measurement_window_sounds.md`.
- [ ] **7.7** Qt rules: device I/O off the GUI thread;
      `core/thread_stack.py::roomy` (`tests/test_every_worker_qthread_has_a_roomy_stack.py`);
      workers unparented and held in a module list
      (example `workflow/cr30/measure_bridge.py::_LIVE`); bound methods, never
      self-capturing lambdas (`tests/test_a_scrollbar_signal_never_takes_a_lambda.py`);
      `core/gc_guard.py` (`tests/test_b8_1392_no_collection_inside_event_delivery.py`);
      `core/keep_awake.py::keep_awake` held while measuring.
- [ ] **7.8** A state a crash can leave on the device is recorded and asked
      about at the next Start (example `core/i1pro2_lights_marker.py`).
- [ ] **7.9** USB presence (`core/argyll_instruments.py::ARGYLL_USB_IDS`) or
      own discovery (example `workflow/cr30/discovery.py`); Read single
      patches only for a spot instrument (`ui/dialogs/spot_read_dialog.py`,
      `workflow/cr30_spot_manager.py`, `docs/design/tool_availability.md`);
      user calibration windows (example
      `ui/cr30_calibration.py::Cr30CalibrationMixin`); platform drivers
      (`requirements.txt`, `core/usb_driver_installer.py`,
      `core/ch34x_driver.py`, a note like `docs/cr30_platform_support.md`);
      aiming help reuses `ui/tiff_preview.py::TiffPreview.set_aim_overlay`;
      swipe arrows hidden for a non-swiping instrument
      (`ui/tiff_preview.py::TiffPreview.set_no_swipe`).
- [ ] **7.10** Every failure the user can act on is a window from the
      catalogue (what happened, what to do, what is kept), classified by
      exception type before words, with the technical reason as a detail
      line; log lines in `tr()`.
- [ ] **7.11** Instrument button shortcuts (Preferences > Measurement): map
      the instrument's model or code to its family in
      `workflow/button_gestures.py::family_of`, and add the family to
      `workflow/button_gestures.py::SUPPORTED_FAMILIES` only if the instrument
      really reports its button presses the way that feature needs.

**Done means:** Start runs the whole preflight for the instrument (a test),
every ending releases the lease and settles the chart (tests), and a session
with the simulator or the real device reaches the end window on screen.

## Stage 8. Hardware

- [ ] **8.1** Every command the code can send is listed (what it does, where
      it is built) in the provenance note and the pull request, each with its
      source and confidence; none is a guess.
- [ ] **8.2** Commands sent only in the situations they were recorded in;
      a test pins the bytes (model
      `tests/test_i1pro2_lights_driver.py::test_each_sequence_is_the_recorded_bytes`)
      and that nothing else is sent
      (`tests/test_i1pro2_lights_driver.py::test_the_patch_adds_no_other_request`).
- [ ] **8.3** Unknown model, generation, firmware or sensor version refused
      before anything is sent or moves; the refusal names what was found.
- [ ] **8.4** No write to the instrument's memory, settings, calibration or
      firmware. *Check:* the command list of 8.1 holds none.
- [ ] **8.5** Nothing that could reach the sensor differs from "without the
      feature" during a reading.
- [ ] **8.6** No movement on a guess: known commands, limits from the
      recordings, a timeout and an arrival check per move.
- [ ] **8.7** Fixed serialisers only; the generic send is private; no command
      field from user input or a file; every reply length-checked; every wait
      has a timeout.
- [ ] **8.8** A simulator built from the recordings, with faults, and the
      full session tested against it (building blocks:
      `native/chartread_helper/chromiq_replay.c`, the fake USB layer of
      `tests/test_i1pro2_lights_driver.py::test_option_on_a_whole_i1pro2_session`).
- [ ] **8.9** Licence compatible with GPL-3.0; provenance note (examples
      `workflow/cr30/PROVENANCE.md`, `native/instlib/PROVENANCE.md`, patches in
      `scripts/vendor_instlib.py`); packaging in `ChromIQ.spec`,
      `ChromIQWin.spec`, `ChromIQLinux.spec` (every lazily imported module a
      hidden import; model `tests/test_cr30_packaging.py`);
      `THIRD-PARTY-NOTICES.md`, `ui/licences.py::NOTICE_SECTIONS`,
      `ui/licences.py::BUNDLED_LICENCE_FILES`. Only code the app runs is
      shipped.
- [ ] **8.10** Testers: the consent window, the ⓘ's list of checks, small
      steps each ending with a report.

**Done means:** the command list is in the pull request with a source and
level for every command, the byte and "nothing else is sent" tests are green,
and the full session runs against the simulator.

## Stage 9. Text, messages, specifications, docs

- [ ] **9.1** R5 and R6 for every new or changed string;
      `python scripts/i18n_extract.py --missing <code>` empty for all 13;
      `python scripts/em_dash_check.py --report` shows nothing new; short
      labels within `tests/test_i18n.py::test_short_labels_stay_compact`.
- [ ] **9.2** Window IDs in `tests/test_message_catalogue.py::AWAITING_APPROVAL`,
      showing methods in `tests/test_message_catalogue.py::WINDOW_SOURCES`.
- [ ] **9.3** One "Awaiting confirmation" block per touched specification and
      topic (replace your earlier block, never stack), and a specification of
      the instrument's own if needed (example
      `docs/design/i1io_table_support.md`).
- [ ] **9.4** New per-target keys recorded in `docs/design/per_target_settings.md`;
      new folders in `docs/dev_folder_layout.md`; `CHANGELOG.md` under
      `## Unreleased` (add the heading if it is missing).
- [ ] **9.5** Optional: `ui/dialogs/welcome_dialog.py`, `ui/keyboard_help.py`,
      only if a first-time user needs it.
- [ ] **9.6** The other places that may need to name the instrument, each
      behind the switch: a note on the Print tab when such a chart is loaded,
      for example how the sheet is printed and laid down
      (`ui/tabs/tab_print.py`); the instrument named in the Measurement
      Report (`workflow/measurement_report.py`); and the i1Profiler hand-off
      files (`workflow/i1profiler_turned.py`), which say plainly when no
      matching file can be written for the instrument's chart.
- [ ] **9.7** The `HOOKED_FILES` pin lists every shared file that now names
      the instrument.

**Done means:** the language, em dash, message catalogue, specification and
guide tests of 10.7 pass, and the translation review is named in the pull
request.

## Stage 10. Proof

- [ ] **10.1** Every behaviour change has a test that failed before it and
      passes after it (run once against the unchanged code).
- [ ] **10.2** Extremes tested: smallest and largest sizes, every paper, each
      option on and off, full and part-filled sheets; the chart's name and
      page number print on every page.
- [ ] **10.3** Fakes only: no network, no real port, no test that needs
      private recordings or a device. House rules from `CLAUDE.md`
      (`timeout=` on subprocesses, no modal `.exec()`, no
      `qapp.setStyleSheet()`, the shared `qapp`, `tests/conftest.py`).
- [ ] **10.4** **File comparison**:
      `python scripts/compare_with_release.py <latest tag> --out <folder>`
      and again with `--betas on` (latest tag:
      `git tag --sort=-v:refname`). With the switch off every chart is the
      same; with it on (every Beta, not only yours) every other instrument
      is the same, and each difference in your own instrument's files is
      explained. It covers layout-engine charts from the default recipes,
      not Guided, printtarg, presets or saved projects: those are covered by
      3.11 and 10.5. A changed `default_recipe()` value is caught here, not
      by the parity test. Only the
      `.ti2` `CREATED` line is normalised (the script does it). If you
      changed recipes, presets or saved projects, also build some saved by
      the previous release in both trees (Stage 5). Both `<folder>/compare.txt`
      tables go in the pull request.
- [ ] **10.5** **On screen, side by side** (R1, R2):
      `python scripts/instrument_parity_drive.py <folder> --only <your code>`
      runs one fixed sequence (Guided generate, Manual, three options, Save
      as Defaults, new project, preset, reopen, every run type) for your
      instrument and the reference in the real app, sandboxed, and writes
      `<folder>/contact/<step>.png` and `<folder>/summary.txt`. The contact sheets for the
      steps you touched, plus your own photographs of the switch off and on
      and of the Stage 3 options at their extremes, go in the pull request.
      On Windows and Linux the drive writes `<folder>/summary.txt` only; add your own
      screenshots of the real window.
- [ ] **10.6** Independent review by someone who did not build it, given the
      diff and not the conclusions; repeated until it finds nothing that
      matters.
- [ ] **10.7** The gate, inside the project's `.venv`:

  ```bash
  QT_QPA_PLATFORM=offscreen pytest tests/test_i18n.py tests/test_no_new_em_dash_in_user_facing_text.py tests/test_message_catalogue.py tests/test_design_specs_are_binding.py tests/test_adding_an_instrument_guide_stays_true.py -q
  QT_QPA_PLATFORM=offscreen pytest -n auto -q                      # everyday tier
  QT_QPA_PLATFORM=offscreen pytest --runslow -n auto -q > /tmp/chromiq-gate.txt 2>&1
  echo "exit=$?"                                                   # the gate
  ```

  Windows PowerShell:
  `$env:QT_QPA_PLATFORM='offscreen'; pytest --runslow -n auto -q > $env:TEMP\chromiq-gate.txt 2>&1; echo "exit=$LASTEXITCODE"`.
  *Done:* `N passed` with no `failed`, `exit=0` read from pytest itself, not
  through a pipe, and no file edited while it ran. A failure you did not
  cause is run on unchanged `master` too, and both results are reported.
- [ ] **10.8** The parity test is part of the gate (10.7) and green there;
      run it alone first, it takes about a minute and prints any new
      difference ready to paste.

**Done means:** 10.1 to 10.8 all done, with their evidence in the pull
request.

## Stage 11. The pull request

- [ ] **11.1** One topic; based on current `master`; others' authorship kept.
- [ ] **11.2** The description holds everything listed in the guide's
      section 15, and this checklist with every item marked.
- [ ] **11.3** Self-review against the table below, every row marked.

| Mistake seen in review | Caught by |
|---|---|
| Chart designed from a `printtarg` layout | 0.2, 2.10 |
| Options greyed "for safety" | 3.2 |
| Option lost after Save as Defaults, preset or reopen | 3.8 |
| Run type left out in silence | 4.1, 4.3 |
| Change visible with the switch off | 1.9, 10.4 |
| In-memory recipe treated as old | 5.2 |
| Chart checked against the panel's recipe | 5.5 |
| Name or page number dropped at extremes | 10.2 |
| Commands reused across generations | 8.3 |
| Copied behaviour that could change a reading | 8.5 |
| Values inherited from the previous instrument | 3.10 |
| Duplicated controls | 3.6 |
| Chart check that crashes on a cp1252 file | 6.1 |
| Parameter lock lifted during a read | 7.3 |
| Start preflight skipped | 7.1 |
| Every target's `meta.json` rewritten | 1.8, 1.9 |
| Settings outside `AppSettings` | R7 |
| English-only logs, raw errors | R6, 7.10 |
| Missing §M entries | R5, 9.2 |
| Errors classified by words, not by exception type | 7.10 |
| Resume tied to a network address | 7.6 |
| Parent-owned worker thread | 7.7 |
| Research code in the bundle | 8.9 |
| Tests only the author can run | 10.3 |
| A test rewritten to pass | R10 |
| Stacked specification blocks | 9.3 |
| Unrelated change inside | 11.1 |

## Maintenance of these documents

- `tests/test_adding_an_instrument_guide_stays_true.py` checks that every path
  and `path::name` in the guide, this checklist, the agent prompt and the
  pointer files exists, that every shared file an instrument hook pin lists is
  named here, and that no em dash creeps in.
- **The owners' section of the guide (section 2) must be re-checked whenever
  the recording tool
  ([chromiq-i1io-probe](https://github.com/itsab1989/chromiq-i1io-probe)) gets
  a release**: which instruments and systems it covers, the choices it
  offers, what it needs installed, what the report hides (serial numbers,
  other devices), what a recording still contains (including what it may
  still hold of other USB devices, and how older files are cleaned), and
  where to send it. The guide itself names no current version; this note
  does. Last checked against version 1.6.3.
