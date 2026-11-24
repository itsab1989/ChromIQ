# Developer tools: what exists, and where

ChromIQ has grown hundreds of scripts and test helpers: drivers that work the real app on screen,
simulated devices, byte-identity checks, audits, translation tools and the gate tooling. This
page is how a developer, or the coding agent helping one, finds the right one instead of writing
a new one. The top is written by hand, by PURPOSE, and covers the reusable tools. The bottom is
generated from every script's own docstring by `scripts/make_tools_index.py`, and
`tests/test_tools_index_is_current.py` fails when it is out of date, so it cannot rot.

**Before you run anything here, read [`scripts/README.md`](../scripts/README.md)**: set
`CHROMIQ_SETTINGS_FILE` to a scratch file first (a driver builds a real `AppSettings`, which is
the store you work with every day), and give every script a NEW output folder. The project's
general rules are in [`CLAUDE.md`](../CLAUDE.md) and, for agents, [`AGENTS.md`](../AGENTS.md).

**TOOL** means reusable and kept working. **example** means a one-off check from a past round,
kept as a worked pattern: it may need adapting, and some still carry paths of the maintainer's
machine (the listing says so).

## Drive the real app on screen and photograph it

Proof is produced by driving the REAL app in a REAL window
([`CLAUDE.md`](../CLAUDE.md), "On screen is the default").

| tool | what it does | run | needs |
|---|---|---|---|
| `scripts/userdrive.py` | the shared harness: `Drive(out_dir)` builds the fully styled app, sandboxes settings and presets, runs your script as a generator inside the app's own event loop (so real `exec()` windows can be answered), photographs, and always ends | import it: `from userdrive import Drive` (see its docstring) | display, sandbox |
| `scripts/capture_screens.py` | builds the application as `main.py` does (`build_app`, `set_theme`); also refreshes the documentation screenshots | `python scripts/capture_screens.py` | display, sandbox, ArgyllCMS |
| `scripts/onscreen_capture.py` | photographs a window by its id even behind other windows (`capture_window`), wakes the display, keeps it awake for a run, gives the keyboard back (`FocusGiveBack`), and answers unscripted questions safely (`PopupWatchdog`) | import it | macOS, Screen Recording allowed |
| `scripts/onscreen_capture_win.py` | the same idea on Windows | import it | Windows |
| `scripts/driven_instrument_proof_driver.py` | TEMPLATE proof driver for a driven instrument, runnable on the simulated i1iO 2 table | `python scripts/driven_instrument_proof_driver.py NEW_FOLDER --pass first` | display, sandbox, ArgyllCMS |
| `scripts/sweep_every_tab_for_clipping.py` | every tab, heading and button: what is clipped, and by how much | read its docstring | sandbox |
| `scripts/i18n_onscreen_audit.py` | the main window in one language; flags clipped controls | `python scripts/i18n_onscreen_audit.py --help` | ArgyllCMS |
| `scripts/scanner_sweep/run-sweep.sh` | drives the scanner window function by function (its own README) | `scripts/scanner_sweep/README.md` | display |

## Simulate a device

Test support under `tests/`, never shipped. Use them in tests and behind the real panel in a
driver; never let a driver open a real device.

| module | what it simulates |
|---|---|
| `tests/i1io_table/session_sim.py` | the i1iO 2 table as recorded, on a virtual clock; raises on any line it must never get |
| `tests/i1io_table/part_c_sim.py` | the table with computed moves and the measuring area, fake spot and strip readers with faults |
| `tests/i1io_table/reader_sim.py` | ChromIQ's helper process behind the app's own reader code |
| `tests/i1io_table/window_sim.py` | all of the above behind the real panel (`WindowSim.factory` replaces `ui/i1io_table_window.py::JOB_FACTORY`) |
| `tests/i1io_table/window_person.py` | a simulated person pressing the panel's buttons by their labels |
| `tests/i1io_table/job_harness.py` | drives the table's job headless with a scripted person |
| `tests/_fd9_bidirectional_wire.py` | invented FD-9 wire for GUI tests |
| `tests/helpers/live_reader.py` | a real instrument program at the far end of a pty, for windows that send keys |
| `tests/helpers/replay_tools.py` | drives `chromiq-chartread`'s replay mode in tests |
| `tests/i1p_forward.py` | a forward model of i1Profiler's "Measure Chart" on the i1iO table |

## Prove that charts are byte for byte the same

| tool | what it does | run | needs |
|---|---|---|---|
| `scripts/compare_with_release.py` | builds the same charts with a release and with your tree, every instrument, and compares every file | `python scripts/compare_with_release.py v4.3.44 --out NEW_FOLDER` | ArgyllCMS |
| `scripts/examples/charts/byte_identity_every_preset/` | example: every built-in preset generated on screen in two trees, every file hashed and compared (section 9b of [the guide](adding_an_instrument.md)) | its README | display, sandbox, ArgyllCMS |

## Check one instrument against the others

| tool | what it does | run |
|---|---|---|
| `scripts/instrument_parity.py` | the parity rows of `tests/test_instrument_parity.py`, without the suite | `QT_QPA_PLATFORM=offscreen python scripts/instrument_parity.py --only CODE` |
| `scripts/instrument_parity_drive.py` | the same Create Chart sequence for every instrument on screen, side by side | `python scripts/instrument_parity_drive.py NEW_FOLDER --only CODE` |

## Plant faults to test the tests

| tool | what it does | run |
|---|---|---|
| `scripts/planted_faults.py` | copies the tree once per fault into a new folder, plants one change, runs your test selection, reports caught / SURVIVED; never changes your tree, never deletes | `python scripts/planted_faults.py --example`, then `python scripts/planted_faults.py faults.json --out NEW_FOLDER` |

## Analyse recordings of an instrument's own program

| tool | what it does | run |
|---|---|---|
| `scripts/recording_timeline.py` | a USB recording as a timeline, or one row per distinct command with its answer times | `python scripts/recording_timeline.py REC.pcap --commands` |
| `scripts/recording_vs_allowlist.py` | every recorded host line against the app's allow-list; computed lines rebuilt byte for byte | `python scripts/recording_vs_allowlist.py REC.pcap` |
| `scripts/recordings/synthetic.py` | an invented recording to try both on | `python scripts/recordings/synthetic.py NEW_FILE.pcap` |
| `scripts/ptyrun.py` | runs a console tester program in a pseudo-terminal and types each answer after its question, keeping a transcript | `python scripts/ptyrun.py --demo` |
| `scripts/decode_i1profiler_probe.py` | reads i1Profiler's layout off a printed probe chart | read its docstring |

The recording itself is made by an owner with the separate recording tool,
[github.com/itsab1989/chromiq-i1io-probe](https://github.com/itsab1989/chromiq-i1io-probe).
How these fit together: [`docs/adding_an_instrument.md`](adding_an_instrument.md), section 12b.

## Translations and texts

| tool | what it does | run |
|---|---|---|
| `scripts/i18n_extract.py` | every `tr()` string, and what a catalogue is missing | `python scripts/i18n_extract.py --missing de` |
| `scripts/i18n_sync.py` | brings every catalogue back in step with the source | read its docstring |
| `scripts/i18n_check_name_widths.py` | translated parameter names against the label column | read its docstring |
| `scripts/i18n_agent/new_language.py` | the complete prompt for a translation agent for a new language | `python scripts/i18n_agent/new_language.py CODE "English" "Native"` |
| `scripts/em_dash_check.py` | where user-facing text carries an em dash | `python scripts/em_dash_check.py --report` |

## Audits of the code

| tool | what it does |
|---|---|
| `scripts/audit_tool_file_placement.py` | where every Tool saves its files, and whether it asks the run type |
| `scripts/audit_default_buttons.py` | which button is filled and which one Return presses, in every window |
| `scripts/audit_interaction_state_rules.py` | the colours of every interaction-state stylesheet rule |

## Release, gates and packaging

| tool | what it does | run |
|---|---|---|
| `scripts/gate_tier.py` | which gate a change needs (normal or full) | `python scripts/gate_tier.py` |
| `scripts/run_release_gates.sh` | N consecutive `--runslow` gates on this checkout, each with its commit, clean status, pytest's own exit code and count line; stops at the first red | `scripts/run_release_gates.sh NEW_FOLDER 3` |
| `scripts/run_tests.sh` | the suite, hardened against a wedged helper process | `scripts/run_tests.sh` |
| `scripts/release_notes.py` | a release note people can scan, from `CHANGELOG.md` | read its docstring |
| `scripts/make_release_demo_package.py` | the demo package attached to a release | read its docstring |
| `scripts/make_demo_projects.py` | demo projects for tests (the suite caches them) | read its docstring |
| `scripts/check_bundle_load_paths.py`, `scripts/check_bundle_min_macos.py` | checks of a built `ChromIQ.app` | read their docstrings |
| `scripts/vendor_instlib.py` | vendors ArgyllCMS's instrument library into `native/instlib` | read its docstring |

The gate commands themselves are in [`CLAUDE.md`](../CLAUDE.md) ("Test"): read pytest's own exit
code, never through a pipe, and never edit a file while any tier runs.

## Disk hygiene

| tool | what it does | run |
|---|---|---|
| `scripts/disk_report.py` | every place ChromIQ work writes to, with sizes; read only | `python scripts/disk_report.py` |
| `scripts/session_cleanup.py` | removes only ChromIQ tooling's own leftovers; a dry run first | `python scripts/session_cleanup.py`, then `--yes` |

## Templates for driven-instrument work

[`docs/driven_instrument_checklist.md`](driven_instrument_checklist.md), and in
`docs/templates/`: [`questions_table.md`](templates/questions_table.md),
[`safety_brief.md`](templates/safety_brief.md),
[`safety_review_brief.md`](templates/safety_review_brief.md),
[`review_brief.md`](templates/review_brief.md),
[`tester_program_step.md`](templates/tester_program_step.md),
[`release_notes_honest_limits.md`](templates/release_notes_honest_limits.md).

## Every script, by topic (generated)

The one-off drivers and probes below are worked examples of past checks: find one about the area
you are changing, read it, and copy its pattern. Their names say the round they came from
(`adv*` adversarial review probes, `drive_*` on-screen drivers, `probe_*` measurements,
`make_*` fixture and demo builders).

<!-- BEGIN GENERATED: python scripts/make_tools_index.py -->

Every file in `scripts/` (569 in all), by topic. TOOL: reusable, kept working. example: a one-off check kept as a worked pattern; it may need adapting, and one marked "maintainer's paths" will not run unchanged on another machine. "needs" is read from the source by a heuristic. Read a script before you run it, and set CHROMIQ_SETTINGS_FILE first (scripts/README.md).

### Driven instruments and recordings (13)

| file | kind | what it does | needs |
|---|---|---|---|
| `scripts/decode_i1profiler_probe.py` | TOOL | Read i1Profiler's layout straight off a printed probe chart (#120). | - |
| `scripts/drive_before_stable_b8_504_757_1342.py` | example | Before 4.3.0 stable: B8-504, B8-757 and B8-1342, driven ON SCREEN. | display, settings sandbox |
| `scripts/drive_stable_fixes_a.py` | example | On-screen proof for B8-638, B8-756 and B8-1078, in REAL windows. | display, settings sandbox |
| `scripts/driven_instrument_proof_driver.py` | TOOL | TEMPLATE: an on-screen proof driver for an instrument ChromIQ drives itself. | display, settings sandbox, ArgyllCMS |
| `scripts/make_i1profiler_probe.py` | example | Build a self-identifying probe patch set for i1Profiler (#120). | - |
| `scripts/planted_faults.py` | TOOL | Test the tests: plant small faults in COPIES of the tree, one at a time, and see which a chosen test selection catches. | - |
| `scripts/recording_timeline.py` | TOOL | Turn a USB recording of an instrument's own program into a timeline and a command list. | - |
| `scripts/recording_vs_allowlist.py` | TOOL | Compare every line a recording shows the maker's program sending with the APP's allow-list. | - |
| `scripts/recordings/__init__.py` | example | Read USB recordings of an instrument's own program, for a driven-instrument integration. | - |
| `scripts/recordings/capture.py` | example | pcap / pcapng reading and USB event extraction, standard library only. | - |
| `scripts/recordings/plugins/__init__.py` | example | The plug-in interface for one driven device, and the registry. | - |
| `scripts/recordings/plugins/i1io2_table.py` | example | Plug-in for the X-Rite i1iO 2 table (USB 0971:2004) with an i1Pro 2 (0971:2000) in its arm. | - |
| `scripts/recordings/synthetic.py` | TOOL | Make a small INVENTED recording of an i1iO 2 table session, to try the recording tools on. | - |

### Release, gates and packaging (20)

| file | kind | what it does | needs |
|---|---|---|---|
| `scripts/adv17c_the_route_gate_one_names.py` | example | Adversary 17c: the OTHER sentence in the same message, which nothing asks the sheet about. | display, settings sandbox |
| `scripts/adv17d_the_gates_assume_monotonicity.py` | example | Adversary 17d, probe 2: both new gates assume "B at the bottom of its range is the best B", and the code's own docstring says it is not. | display, settings sandbox |
| `scripts/adv17e_the_gates_the_ceiling_and_the_markers.py` | example | Adversary 17e / P4-P6, driven in a real window. | display, settings sandbox |
| `scripts/build_icons.py` | example | Generate platform icons from assets/app_icon.png. | - |
| `scripts/check_bundle_load_paths.py` | TOOL | Fail when a binary in ChromIQ.app loads a library that is not in the app. | - |
| `scripts/check_bundle_min_macos.py` | TOOL | Fail when any binary in ChromIQ.app needs a newer macOS than the app says. | - |
| `scripts/check_pdf_export_windows.py` | example | On-screen smoke check for the measurement-report PDF export. | - |
| `scripts/compare_with_release.py` | TOOL | Does this tree still build the charts a release built? Byte for byte. | settings sandbox, ArgyllCMS |
| `scripts/drive_182_combined_round2_two_windows.py` | example | Combined round 2: can the dated-verification protection be walked around? | display, settings sandbox |
| `scripts/drive_205_windows_print.py` | example | #205 on screen, Windows: both print routes of the real app, photographed. | display, settings sandbox |
| `scripts/drive_209_txt_import_with_windows_tool_names.py` | example | #209 on screen: the i1Profiler .txt import with ArgyllCMS's Windows names. | display, settings sandbox, ArgyllCMS |
| `scripts/drive_50_beta3_gate.py` | example | On-screen gate checks for v4.1.5-beta.3. | settings sandbox |
| `scripts/gate_tier.py` | TOOL | Which gate does this change need: the NORMAL one or the FULL one? | - |
| `scripts/make_release_demo_package.py` | TOOL | Build the ONE demo package attached to every ChromIQ release (#182 K29). | ArgyllCMS, maintainer's paths: adapt first |
| `scripts/make_tools_index.py` | TOOL | Write the generated part of docs/dev_tools_index.md: every script in scripts/, by topic. | - |
| `scripts/release_notes.py` | TOOL | Build a release note a user can actually scan, from CHANGELOG.md. | - |
| `scripts/run_release_gates.sh` | TOOL | Run the release gate N times in a row on this checkout, and read pytest's OWN exit code. | - |
| `scripts/run_tests.sh` | TOOL | Run the ChromIQ test suite robustly. | - |
| `scripts/update_homebrew_tap.py` | example | Point the Homebrew tap's casks at a new ChromIQ release. | - |
| `scripts/vendor_instlib.py` | TOOL | Vendor Argyll's standalone instrument library into native/instlib. | ArgyllCMS, maintainer's paths: adapt first |

### Disk hygiene (2)

| file | kind | what it does | needs |
|---|---|---|---|
| `scripts/disk_report.py` | TOOL | How much disk space ChromIQ development is holding, and where. Read-only. | settings sandbox |
| `scripts/session_cleanup.py` | TOOL | Remove what ChromIQ work left on the disk, and say what it freed. | ArgyllCMS |

### Languages and texts (30)

| file | kind | what it does | needs |
|---|---|---|---|
| `scripts/adv17_auto_text_is_shrunk_to_the_floor.py` | example | Adversary 17: the new height term in the auto-shrink loop can never be true. | - |
| `scripts/adv17_bottom_text_quiet_and_colliding.py` | example | Adversary 17: hunt the DANGEROUS direction of the new bottom-text check. | display, settings sandbox |
| `scripts/adv17_german_names_the_wrong_set.py` | example | Adversary 17: the German help sends a German reader to a set that is not there. | display, settings sandbox |
| `scripts/adv23d_the_report_help_in_three_languages.py` | example | Adversary 23d: the Report type and Judged against help, read on screen. | display, settings sandbox |
| `scripts/adv27b_german_and_demo13.py` | example | Round 27b, the last two border conditions, on screen. | settings sandbox |
| `scripts/adv29_the_german_window.py` | example | Adversary round 29: the re-laid-out Measurement Report window in GERMAN. | display, settings sandbox |
| `scripts/drive_182_bottom_text_alignment.py` | example | a maintainer's three bottom-text alignments, driven in the REAL Create Chart tab. | display, settings sandbox, ArgyllCMS |
| `scripts/drive_182_knut_bottom_text_height.py` | example | a maintainer's beta 15 bottom-text case, in the REAL Create Chart tab. | display, settings sandbox |
| `scripts/drive_182_preset_text_overlap_sweep.py` | example | Every built-in Create Chart preset against the new margin and text rules. | display, settings sandbox |
| `scripts/drive_182_sheet_text_fit.py` | example | On-screen reproduction / proof for a maintainer's #182 comment of 2026-09-11T21:23:10Z. | display, settings sandbox |
| `scripts/drive_182_text_shrink_floor.py` | example | On-screen reproduction / proof for a maintainer's #182 comment of 2026-09-11T15:06:22Z. | display, settings sandbox |
| `scripts/drive_209_converter_errors_in_the_users_language.py` | example | #209, second half, on screen: the converter's reason in the user's language, and a calibration's i1Profiler export loaded with ArgyllCMS's Windows names. | display, settings sandbox, ArgyllCMS |
| `scripts/drive_a11_certificate_text.py` | example | A11: drive the real driver window ON SCREEN and read the certificate text. | settings sandbox |
| `scripts/drive_b17_texts_on_screen.py` | example | Beta 17: the new texts photographed in REAL windows (#182). | display, settings sandbox |
| `scripts/drive_panel_overflow_per_language.py` | example | Does the Create Chart panel FIT its viewport, in every shipped language? | display, settings sandbox |
| `scripts/drive_uk_language_on_screen.py` | example | Ukrainian on screen: the real app, in a real window, in uk. | display, settings sandbox |
| `scripts/em_dash_check.py` | TOOL | Where ChromIQ's user-facing text lives, and which of it carries an em dash. | - |
| `scripts/i18n_agent/new_language.py` | TOOL | Generate the translation-agent prompt for a new ChromIQ language. | - |
| `scripts/i18n_agent/uk_wrong_sense_fixes.py` | example | Correct the Ukrainian strings whose current wording means something else. | - |
| `scripts/i18n_check_name_widths.py` | TOOL | Check translated parameter names against the manual-mode label column. | - |
| `scripts/i18n_extract.py` | TOOL | Extract tr() source strings and check catalog completeness. | ArgyllCMS |
| `scripts/i18n_merge_batch.py` | example | Merge a batch of translations into data/i18n/<code>.json, keyed by PREFIX. | - |
| `scripts/i18n_onscreen_audit.py` | TOOL | Offscreen render of the full main window in a given language; flags clipped buttons/checkboxes (incl. multi-line) and horizontally overflowing scroll panes. | ArgyllCMS |
| `scripts/i18n_sync.py` | TOOL | Bring every data/i18n/<code>.json back in step with the source. | - |
| `scripts/i18n_tone_audit.py` | example | Audit every user-facing English string against ChromIQ's own writing rules. | - |
| `scripts/i18n_verify_batch.py` | example | Accept (or reject) a batch of translation work, one language at a time. | - |
| `scripts/i18n_wrap.py` | example | Wrap user-facing string literals in tr(): one-shot retrofit tool. | - |
| `scripts/pdf_pages_and_text.py` | example | Read a saved report PDF back: its text per page, and each page as a PNG. | - |
| `scripts/txt_round_challenge.py` | example | Challenge my own three fixes in a real window. Assume each one broke something. | display, settings sandbox |
| `scripts/txt_round_onscreen_proof.py` | example | Photograph the three fixed strings in a REAL window, English and German. | display, settings sandbox |

### Calibration (5)

| file | kind | what it does | needs |
|---|---|---|---|
| `scripts/drive_beta39_calibration.py` | example | #182 beta 39, driven ON SCREEN: Run type Calibration makes reports. | display, settings sandbox |
| `scripts/drive_cal_keeps_the_persons_files.py` | example | ON SCREEN: a note and a photograph left in cal/ survive Generate Chart. | ArgyllCMS |
| `scripts/drive_cal_patch_set_editor.py` | example | Does the patch set editor act on the CALIBRATION chart in a calibration run? | ArgyllCMS |
| `scripts/drive_calibration_run_type.py` | example | Drive the REAL app through the #137 calibration Run type and check each step. | ArgyllCMS |
| `scripts/mockup_calibration_run_type.py` | example | Mockups for the "Calibration as a Run type" design draft (#130). | ArgyllCMS |

### Reports and verification (69)

| file | kind | what it does | needs |
|---|---|---|---|
| `scripts/adv14_report_waits_attack.py` | example | ADVERSARY round 14: the Measurement Report window's "wait for Generate". | display, settings sandbox |
| `scripts/adv17_report_help_claims.py` | example | Adversary round 17: the three checkable claims in the new type/pairing help. | display, settings sandbox |
| `scripts/adv_b20r4_saved_reports_and_delete.py` | example | The saved-report selector and the delete rule, on a real project: round 4. | display, settings sandbox |
| `scripts/adv_b20r5_drive_the_reported_projects.py` | example | Round 5: drive the REAL ChromIQ window over copies of four reported projects. | display, settings sandbox, maintainer's paths: adapt first |
| `scripts/adversary15_limits_window_layout.py` | example | ADVERSARY 15: thirty new icons in the Report limits window, ON SCREEN. | display, settings sandbox |
| `scripts/capture_report_limit_demo_shots.py` | example | Open the limit demo projects in the REAL Measurement Report window and photograph a crossed limit and the same row recovered on a later date (#182). | display, settings sandbox |
| `scripts/capture_report_shots.py` | example | Capture Measurement Report screenshots for the forum showcase. | display |
| `scripts/cr30_bluetooth_report.py` | example | CR30 Bluetooth diagnostic: run this and send us the file it writes. | - |
| `scripts/drive_130_verify_plan.py` | example | Drive the REAL ChromIQ app through the #130 verification-chart rows of a maintainer's test plan (posted on the issue 2026-07-26). | - |
| `scripts/drive_182_combined_round1_report.py` | example | Combined round 1: a full sitting in the Measurement Report window. | display, settings sandbox |
| `scripts/drive_182_combined_round1_verify.py` | example | Combined round 1: the delete rule on a dated verification, end to end. | display, settings sandbox |
| `scripts/drive_182_limits_radio_case.py` | example | a maintainer's beta 12 report: the Edit-limits radios, in the REAL windows. | display, settings sandbox |
| `scripts/drive_182_metric_help_icons.py` | example | a maintainer's per-metric help icons, in the REAL Report limits window. | display, settings sandbox |
| `scripts/drive_182_preset_verification_window.py` | example | #182, beta 22: the preset eligibility window, driven in a REAL window. | display, settings sandbox |
| `scripts/drive_182_report_type_help.py` | example | a maintainer's help text for "Report type" and "Judged against", read on screen. | display, settings sandbox |
| `scripts/drive_182_saved_reports.py` | example | B8-250: select and delete saved reports, in a REAL Measurement Report window. | display, settings sandbox, maintainer's paths: adapt first |
| `scripts/drive_182_saved_reports_challenge.py` | example | The challenge round against B8-250: assume the Saved reports row broke something a user can see, in a REAL window. | display, settings sandbox, maintainer's paths: adapt first |
| `scripts/drive_46_aiming_overlay_report.py` | example | Drive the REAL ChromIQ window for report 46 (aiming overlay design review). | - |
| `scripts/drive_47_aiming_overlay_verify.py` | example | Adversarial on-screen verification of the CR30 aiming overlay (6b879c6e). | settings sandbox |
| `scripts/drive_49_legend_hover_verify.py` | example | Adversarial on-screen verification of the legend hover-hide (29c1a7c6). | settings sandbox |
| `scripts/drive_52_bt_report_verify.py` | example | Live verification of the in-app CR30 Bluetooth report (final beta-3 review). | display, settings sandbox |
| `scripts/drive_b22_knuts_five_report_defects.py` | example | a maintainer's five Measurement Report defects, 2026-09-18, driven in a real window. | display, settings sandbox |
| `scripts/drive_b29_report_review.py` | example | Drive a maintainer's beta-29 Measurement Report review ON SCREEN, in a real window. | display, settings sandbox |
| `scripts/drive_b384_the_older_reports.py` | example | B8-384's remainder: what changing "Judged against" does to a saved report that was written before this beta, driven in a REAL window on a REAL screen. | display, settings sandbox |
| `scripts/drive_b388_the_report_defaults.py` | example | B8-388 / B8-391 / B8-392: a maintainer's Measurement Report defaults, on screen. | display, settings sandbox |
| `scripts/drive_b42_all_metrics.py` | example | B42, a maintainer #182 5814820283: "All metrics" in "Which presets can be used for verification?", driven ON SCREEN. | display, settings sandbox |
| `scripts/drive_b4_limit_edges.py` | example | Every misread limit, exactly at its edge, on every chart type, ON SCREEN (#182, a maintainer 6154440320, 4.3.5 beta 4). | display, settings sandbox |
| `scripts/drive_b8_1476_evenness.py` | example | B8-1476 (a maintainer, #182 5855259490 and 5855780690): the evenness filter, the new limits, the converted ISO figures and their note, the help texts and the presets window's "can be judged" line, driven ON SCREEN in ... | display, settings sandbox |
| `scripts/drive_b8_1653_report_limits_headings.py` | example | B8-1653 on screen: the Report Limits column headings keep to their columns. | display, settings sandbox |
| `scripts/drive_beta38_evenness_60.py` | example | #182 beta 38, E2 at 60 % (a maintainer, 5792912682) and E4, driven ON SCREEN. | display, settings sandbox |
| `scripts/drive_beta38_evenness_followups.py` | example | #182 beta 38, E2 and E4 (B8-828, B8-829), driven ON SCREEN as a user. | display, settings sandbox |
| `scripts/drive_evenness.py` | example | #182, evenness across the sheet (B8-814), driven ON SCREEN as a user. | display, settings sandbox |
| `scripts/drive_f10_ink_limit_corner.py` | example | F-10 (#182 5985477496): Create Chart with Total Ink Limit 300 and grey steps, ON SCREEN. | display, settings sandbox, ArgyllCMS |
| `scripts/drive_k23_report_folders.py` | example | K23 on screen: where every kind of report lives, and what "Report shown" and "Already generated" list and count, on Report-Limits-Report-Folders. | display, settings sandbox |
| `scripts/drive_k25_bug3_every_metric_explained.py` | example | a maintainer's beta-25 bug 3, measured in a REAL window. | display, settings sandbox |
| `scripts/drive_k25_report_list.py` | example | K25 on screen: "Report shown" grouped by run and project, the names kept, every run's Printing records on a Profiling window. | display, settings sandbox |
| `scripts/drive_k25_report_window_bugs.py` | example | a maintainer's beta-25 Measurement Report bugs, reproduced in a REAL window. | display, settings sandbox |
| `scripts/drive_k25_trend_graphs.py` | example | #182 K25, the trend graphs explain themselves, driven ON SCREEN. | display, settings sandbox |
| `scripts/drive_k26_new_report_defaults.py` | example | a maintainer, beta 26: "New report…" must start from Preferences ▸ Reports. | display, settings sandbox |
| `scripts/drive_k28b_report_rendering.py` | example | #182 K28b (beta 39): the report-rendering half of a maintainer's K28 rulings, driven ON SCREEN. | display, settings sandbox |
| `scripts/drive_k31_metrics.py` | example | #182 K31 (beta 40): metrics, names and texts, driven ON SCREEN. | display, settings sandbox |
| `scripts/drive_k32_report_rows_and_switch.py` | example | #182 K32 (a maintainer on beta 41, 5813851807), driven ON SCREEN. | display, settings sandbox |
| `scripts/drive_k40_presets_and_every_metric.py` | example | K40 (a maintainer, #182 5832026677), driven ON SCREEN, on any tree. | display, settings sandbox, ArgyllCMS |
| `scripts/drive_k47_graph_limits.py` | example | K47 (a maintainer, #182 5840152058): every limited row has a data line, a limit line and a sentence, and a graph with no limit says so. Driven ON SCREEN, on any tree, so the same cases run before and after the change. | display, settings sandbox |
| `scripts/drive_k49_metric_help.py` | example | a maintainer, #182 5841606710 (2026-09-26): the metric help says how the rows of a family relate ("Maximum ΔE00, lowest 95 % (P95)" can never be higher than "Maximum ΔE00, all patches"), and both Custom columns put ... | display, settings sandbox |
| `scripts/drive_k51_report_cases.py` | example | K51 (a maintainer, #182 5846167083): a raw print judged on its paper and solid rows, "–" taken out of the graphs, a limit line shown for information where the report judges nothing. Driven ON SCREEN, on any tree, so ... | display, settings sandbox |
| `scripts/drive_k61_presets_evenness.py` | example | K61 (a maintainer, #182 5851645723): "Which presets can be used for verification", judged against ISO 12647-7, and the i1Pro presets of 648 and 783 patches on one page, which the window said have "too few patches in ... | display, settings sandbox |
| `scripts/drive_k61_report_labels.py` | example | K61 (a maintainer, #182 5851645723): every metric name the Measurement Report quotes is EXACTLY the name the Report Limits window shows, and "within gamut" stands outside it. Driven ON SCREEN, on any tree, so the ... | display, settings sandbox |
| `scripts/drive_one_page_report.py` | example | Drive the one-page colour summary (T1) in the real window, on screen. | display, settings sandbox |
| `scripts/drive_r27_the_report_follows_the_selection.py` | example | Adversary round 27: the Measurement Report window, driven in a real window. | display, settings sandbox |
| `scripts/drive_r27_type_crossed_with_limit_set.py` | example | Adversary round 27, part three: the report text crossed against its TYPE and its LIMIT SET, in a real window. | display, settings sandbox |
| `scripts/drive_report_defects_onscreen.py` | example | Drive the two Measurement Report defects in the real widgets, on screen. | settings sandbox, maintainer's paths: adapt first |
| `scripts/drive_report_demo_onscreen.py` | example | Drive the Measurement Report against Demo-Report-Matrix: every case, every option, one PDF per case (a maintainer's report test package, 2026-08-10). | - |
| `scripts/drive_report_types_onscreen.py` | example | Drive the Measurement Report over every report type and every limit set. | display, settings sandbox |
| `scripts/drive_the_verification_preflight.py` | example | Drive a maintainer's verification pre-flight and the presets window's first line, ON SCREEN, in a real window, and photograph what a user would see. | display, settings sandbox |
| `scripts/drive_trend_graphs.py` | example | #182 K20/K21, the trend graphs for the judged metrics, driven ON SCREEN. | display, settings sandbox |
| `scripts/drive_verification_measurement_import.py` | example | On-screen reproduction and proof for the Measure tab's IMPORT module. | display, settings sandbox |
| `scripts/drive_verification_print_a.py` | example | T10: drive the real Print Chart tab through feature A, end to end on disk. | - |
| `scripts/make_evenness_demo.py` | example | A demo project for evenness across the sheet (#182, a maintainer, 2026-09-22). | - |
| `scripts/make_every_metric_demo.py` | example | A demo project whose one chart answers every metric. | ArgyllCMS |
| `scripts/make_limit_edge_demo.py` | example | Measurement data that lands EXACTLY on every misread limit, per chart type (#182, a maintainer 6154440320, 4.3.5 beta 4). | - |
| `scripts/make_report_demo.py` | example | Build Demo-Report-Matrix: the measurement-report test project (a maintainer). | ArgyllCMS |
| `scripts/make_report_limit_demos.py` | example | Build the Measurement Report limit demo projects (#182, a maintainer 2026-09-08). | ArgyllCMS |
| `scripts/make_scan_align_demos_symmetric.py` | example | Charts built to have NO answer, so the rotation check can be caught guessing. | - |
| `scripts/make_verification_master_set.py` | example | Generate the PROVISIONAL master colour set for #133's gamut verification. | ArgyllCMS |
| `scripts/make_verification_preset_demos.py` | example | Create Chart presets, TWO PER REQUIREMENT, one each side of its line (#182). | ArgyllCMS |
| `scripts/measure_no_strip_limit_capacity.py` | example | Measure per-sheet patch capacity with -P (no strip-length limit) for i1/p3. | ArgyllCMS |
| `scripts/mockup_cm_verification_print.py` | example | Mockups for colour-managed verification printing (#130). | - |
| `scripts/probe_182_right_edge_report.py` | example | Print the K1 / K5 measurement JSON in a readable shape (no app, no window). | - |

### Presets and recipes (42)

| file | kind | what it does | needs |
|---|---|---|---|
| `scripts/adv17e_the_panel_after_a_preset_switch.py` | example | Adversary 17e / P7: the bottom-text notice across a preset switch. | display, settings sandbox |
| `scripts/adv21i_is_the_swept_recipe_reachable.py` | example | Adversary 21i: is 21f's two-point island a sheet the PANEL can produce? | settings sandbox |
| `scripts/adv27b_presets_group_height.py` | example | Round 27b: how much vertical space the presets group really takes, on screen. | settings sandbox |
| `scripts/adv27b_the_demo_presets_as_a_user_gets_them.py` | example | Round 27b: the 14 demo presets, installed from the SHIPPED pack, on screen. | settings sandbox |
| `scripts/adv27b_the_preset_button.py` | example | Adversary round 27b: the "Which presets can be verified?" button, ON SCREEN. | settings sandbox |
| `scripts/adv27b_the_window_opens_on_your_preset.py` | example | Round 27b: the window opens on the preset you chose, and the button's height. | settings sandbox |
| `scripts/drive_182_autosize_and_hex_presets.py` | example | The auto-size ruling and the eight CR30 hexagonal presets, driven on screen. | display, settings sandbox |
| `scripts/drive_182_custom_defaults.py` | example | B8-670: a maintainer's researched industry figures, in the REAL Report limits window. | display, settings sandbox |
| `scripts/drive_182_preset_margin_verdicts.py` | example | R5: load every built-in Create Chart preset in a REAL window and record what the "Measured from Preview" panel says about its margins. | display, settings sandbox |
| `scripts/drive_182_straight_presets.py` | example | a maintainer's six straight-strip CR30 presets, loaded one by one in a REAL window. | display, settings sandbox |
| `scripts/drive_182_survey_every_builtin_preset.py` | example | Load and GENERATE every built-in preset, and write down what it says. | display, settings sandbox |
| `scripts/drive_182_the_demo_presets_that_fail.py` | example | #182, beta 23: the demo presets built to fail one metric each, ON SCREEN. | settings sandbox |
| `scripts/drive_182_why_some_presets_say_nothing.py` | example | Why a loaded preset shows no "Margins: OK" and no warning either. | display, settings sandbox |
| `scripts/drive_b8_1097_presets_ok_close.py` | example | B8-1097 on screen: the gear window's OK and Close (the owner, 2026-09-25). | display, settings sandbox |
| `scripts/drive_b8_1228_custom_defaults_restart.py` | example | B8-1228: "Save as Defaults" on a paper, then a NEW SESSION, on screen. | display, settings sandbox, ArgyllCMS |
| `scripts/drive_b8_1319_preset_list_scroll_bar.py` | example | B8-1319: the open "Select preset" list's scroll bar, pressed with a REAL mouse. ON SCREEN, real window, real pointer (Quartz CGEvents posted to the HID tap), nothing patched out of the app. | display, settings sandbox |
| `scripts/drive_b8_1620_pharmacist_presets.py` | example | B8-1620 on screen: the "by Pharmacist" charts with a page layout. | display, settings sandbox |
| `scripts/drive_cr30_builtin_presets.py` | example | Drive the REAL ChromIQ window over a maintainer's twenty CR30 built-in presets. | settings sandbox |
| `scripts/drive_cr30_default_vs_preset.py` | example | a maintainer's journey and the from-scratch journey, driven in the REAL window. | settings sandbox, ArgyllCMS |
| `scripts/drive_i1pro_photocard_presets.py` | example | Drive the REAL ChromIQ window over a maintainer's nineteen i1Pro photo-card presets. | display, settings sandbox |
| `scripts/drive_k1_i1pro_maximised_presets.py` | example | K1 (a maintainer, beta 34): his eight 7.5 mm i1Pro "Maximised - No Clip-border" presets, driven ON SCREEN as a user picks them. | display, settings sandbox |
| `scripts/drive_k26_preset_button_geometry.py` | example | a maintainer's beta 26 review of the "Which presets can be used for verification?" button, MEASURED AND PHOTOGRAPHED IN A REAL WINDOW. | display, settings sandbox |
| `scripts/drive_k35_curated_presets.py` | example | K35 on screen: the gear, the window, the arrow rows (a maintainer, #182 5818659478). | display, settings sandbox |
| `scripts/drive_k39_preset_list_export_import.py` | example | K39-7 on screen: Export list and Import list in the gear window (a maintainer, #182 5831246553, beta 43, B8-1101 to B8-1104). | display, settings sandbox |
| `scripts/drive_k41_preset_paper_filter.py` | example | K41 on screen: the paper filter in the gear window (a maintainer, #182 5832303551, beta 43, B8-1131 to B8-1134). | display, settings sandbox, ArgyllCMS |
| `scripts/drive_k43_larger_demo_presets.py` | example | K43 (a maintainer, #182 5833695633), driven ON SCREEN: the larger demo presets in "Which presets can be used for verification?". | display, settings sandbox |
| `scripts/drive_k48_preset_lists.py` | example | K48 (a maintainer, #182 5840677938 and 5840692243), on screen. | display, settings sandbox |
| `scripts/drive_k50_presets_window.py` | example | K50 (a maintainer, #182 5845519118, B8-1321): "Which presets can be used for verification" groups the metrics that carry identical messages. Driven ON SCREEN, on any tree, so the same steps run before and after the ... | display, settings sandbox |
| `scripts/drive_photocard_presets.py` | example | Drive the REAL ChromIQ window over a contributor's two photo-card built-ins. | settings sandbox, ArgyllCMS |
| `scripts/drive_preset_button_overlap.py` | example | the owner, 2026-09-22 (German screenshot): "WELCHE PRESETS SIND FÜR DIE VERIFIZIERUNG VERWENDBAR?" overlaps its own ⓘ in Create Chart. | display, settings sandbox |
| `scripts/drive_preset_reload.py` | example | Drive the REAL ChromIQ window and watch what a built-in preset actually builds. | - |
| `scripts/drive_preset_reload_real.py` | example | Drive the real ChromIQ window with the owner's own settings and project. | - |
| `scripts/drive_preset_save_new_patch_set.py` | example | a maintainer, #182 5872273862: after saving a preset under a new name, "New Patch Set…" in the patch set editor shows a previously used setup, not the preset's. | display, settings sandbox |
| `scripts/drive_preset_stale_proof.py` | example | On-screen proof for fix/preset-goes-stale. | settings sandbox |
| `scripts/drive_r27_generate_delete_and_defaults.py` | example | Adversary round 27, part two: generate, delete, regenerate, and the Preferences defaults, driven in a real window. | display, settings sandbox |
| `scripts/examples/charts/byte_identity_every_preset/compare_identity.py` | example | EXAMPLE (kept as a pattern; may need adapting): compare two identity_driver.py runs, preset by preset and file by file. | - |
| `scripts/examples/charts/byte_identity_every_preset/identity_driver.py` | example | EXAMPLE (kept as a pattern; may need adapting): generate EVERY built-in preset in the real app, on screen, and record a SHA-256 of every file each build writes. | display, settings sandbox, ArgyllCMS |
| `scripts/examples/charts/byte_identity_every_preset/masked_compare.py` | example | EXAMPLE (kept as a pattern; may need adapting): compare two kept build folders file by file, with wall-clock instants and the checkout and output folder names masked. | - |
| `scripts/import_knut_presets.py` | example | Import a maintainer's exported chart families as bundled built-in presets. | ArgyllCMS |
| `scripts/import_pharmacist_presets.py` | example | Import the "by Pharmacist" built-ins a maintainer sent on #182 (5860041950). | ArgyllCMS |
| `scripts/make_preset_certificates.py` | example | Write the built-in presets' metric certificates (#182, a maintainer 6045500910, answer 5). RUN AT EVERY RELEASE, after the version bump: | settings sandbox, ArgyllCMS |
| `scripts/make_preset_defaults.py` | example | Write data/preset_defaults.json: the built-in presets ChromIQ SHIPS ticked. | - |

### Measurement (39)

| file | kind | what it does | needs |
|---|---|---|---|
| `scripts/adv17d_two_rebuilds_where_one_is_read.py` | example | Adversary 17d, probe 4: what the two new gates cost per turn of the box. | settings sandbox |
| `scripts/adv21c_the_two_levers_measured_properly.py` | example | Adversary 21c: the two lever gates, with the anchor MOVED. | display, settings sandbox |
| `scripts/adversary15_read_the_icons_on_screen.py` | example | ADVERSARY 15: READ three of the new help icons on a real screen. | display, settings sandbox |
| `scripts/analyse_b21_show_only_measured.py` | example | Count the chart left showing inside a column the user was told is hidden. | - |
| `scripts/drive_182_scan_brightness_checks.py` | example | Drive the REAL *Build profile with scanner or camera* window, printer mode, and photograph the brightness warning appearing and not appearing. | display, settings sandbox, ArgyllCMS |
| `scripts/drive_b17_misread_protocol.py` | example | Beta 17, a maintainer's test plan (#182 6084756743), ON SCREEN in the real app. | display, settings sandbox |
| `scripts/drive_b21_show_only_measured.py` | example | Does "Show only measured patches" blank exactly the unread strips? | display, settings sandbox, maintainer's paths: adapt first |
| `scripts/drive_cr30_hex_demo_both_scans.py` | example | Walk the ChromIQ-CR30-hex-demo pack through the REAL scanner window, twice. | display, settings sandbox, ArgyllCMS |
| `scripts/drive_hex_patch_size_readout.py` | example | Drive the REAL ChromIQ window for a maintainer's hexagonal "Patch size (mm)" report. | settings sandbox |
| `scripts/drive_honeycomb_ruler_markers.py` | example | Drive the REAL window: a honeycomb can now carry ruler markers. | settings sandbox |
| `scripts/drive_i1profiler_measurement_import.py` | example | On-screen reproduction and proof for the profile-build measurement import. | display, settings sandbox |
| `scripts/drive_k26_included_measurements.py` | example | a maintainer, beta 26: what a report STORES is not what was ticked when Generate was pressed, and the date tag in its name does not follow it either. | display, settings sandbox |
| `scripts/drive_profiling_import_on_the_measure_tab.py` | example | Drive the real ChromIQ window: import an i1Profiler measurement into a PROFILING run from the Measure tab, then build a profile from it. | display, settings sandbox, ArgyllCMS |
| `scripts/drive_real_measurement.py` | example | Set a real measurement up to the point a human has to swipe, then watch. | ArgyllCMS |
| `scripts/drive_scanner_window_steadiness.py` | example | AGENT DF: does Tools ▸ Build profile with scanner or camera sit still? | settings sandbox, maintainer's paths: adapt first |
| `scripts/drive_the_control_strip_declaration.py` | example | File a verification chart with the app, on screen, and photograph what it says. | display, settings sandbox, ArgyllCMS |
| `scripts/drive_the_control_strip_demos.py` | example | B8-393 / B8-405: drive the control-strip rows of the demo package on screen. | display, settings sandbox |
| `scripts/make_hex_scanner_sample.py` | example | Build the "try the hexagonal scanner path yourself" sample pack. | - |
| `scripts/make_misread_demo.py` | example | Demo data that triggers every kind of misread on every chart type (#182, beta 17, a maintainer's test plan 6084756743). | ArgyllCMS |
| `scripts/make_ruler_base_fixtures.py` | example | Make the ruler check's base fixture: what the i1Pro driver of the base branch (feat/lights-i1pro3-signals 6de402163, before the ruler check Beta) puts on the (fake) USB wire for hand-held strip scans of an i1Pro 2 ... | - |
| `scripts/make_scan_align_demos.py` | example | Build the Auto-align CHALLENGE SET. | ArgyllCMS |
| `scripts/make_scan_align_demos_ambiguous.py` | example | Cases 27-31: which way up is the sheet, and when is that unknowable? | - |
| `scripts/make_scan_align_demos_photos.py` | example | Cases 32-38: PHOTOGRAPHS, which are a different problem from scans. | ArgyllCMS |
| `scripts/make_scanner_test_target.py` | example | Render a known-good test scan + reference (.cie) for a bundled scanner target. | - |
| `scripts/measure_a2_landscape_capacity.py` | example | Measure per-sheet patch capacity for A2 Landscape (594x420 mm) across every instrument + option combination already represented in data/patch_db.py. | ArgyllCMS |
| `scripts/measure_margin10_capacity.py` | example | Measure per-sheet patch capacity at margin=10mm for i1 and p3 instruments. | ArgyllCMS |
| `scripts/measure_photo_paper_capacity.py` | example | Measure the per-sheet patch capacity of the two named photo papers added for 4 x 6 in printers that print 10 x 15 cm or postcard size (jctay, forum 149803; the owner 2026-10-23): "10x15cm" (100 x 150 mm) and ... | ArgyllCMS |
| `scripts/measure_scale095_capacity.py` | example | Measure per-sheet patch capacity at patch-scale -a 0.95 for i1 and p3. | ArgyllCMS |
| `scripts/measure_scale095_cm_capacity.py` | example | Measure per-sheet patch capacity at -a 0.95 for ColorMunki (CM), both -h states. | ArgyllCMS |
| `scripts/measure_ss_capacity.py` | example | Measure per-sheet patch capacity for SpectroScan across all paper sizes. | ArgyllCMS |
| `scripts/measure_ss_hex_capacity.py` | example | Measure per-sheet capacity for SpectroScan in HEX mode (-h) across all papers. | ArgyllCMS |
| `scripts/measure_triple_density_capacity.py` | example | Measure per-sheet patch capacity for triple-density ColorMunki mode. | ArgyllCMS |
| `scripts/offscreen_font_probe/measure.py` | example | Measurement harness for the offscreen-font-metrics question (Windows gate). | - |
| `scripts/scanner_edge_study.py` | example | Empirical calibration of the scanner misalignment check (a maintainer, #119). | ArgyllCMS |
| `scripts/scanner_sweep/enumerate_controls.py` | example | AGENT-J step 1: enumerate every control of the scanner/camera window FROM THE RUNNING APP (widget tree walk of the live dialog), in every mode. | maintainer's paths: adapt first |
| `scripts/scanner_sweep/make_table.py` | example | Regenerate TABLE.md from the sweep's results: never hand-edited. | maintainer's paths: adapt first |
| `scripts/scanner_sweep/run-sweep.sh` | example | B8-22: the scanner/camera window regression sweep, re-runnable before every beta. | settings sandbox, maintainer's paths: adapt first |
| `scripts/scanner_sweep/scanner_window_sweep.py` | example | AGENT-J: B8-22 regression sweep of the scanner/camera window. | settings sandbox, ArgyllCMS, maintainer's paths: adapt first |
| `scripts/shot_strip_error.py` | example | Pop the real Strip-Read-Failed dialog on screen so you can see it live. | display, ArgyllCMS |

### Instruments (22)

| file | kind | what it does | needs |
|---|---|---|---|
| `scripts/audit_default_buttons.py` | TOOL | K44 audit: in every window, which button is FILLED and which one Return presses (a maintainer, #182 5833983335: one standard for every window and pop-up). | settings sandbox |
| `scripts/cr30_devinfo.py` | example | CR30 device-info test (stage 2 of the firmware research, 2026-10-09). | - |
| `scripts/drive_182_c3_fold_buttons.py` | example | Challenge 3: attack round two's button check on the margin-warning fold. | display, settings sandbox |
| `scripts/drive_a10_libusb_only.py` | example | A10: drive the real driver window ON SCREEN and photograph what it says. | settings sandbox |
| `scripts/drive_a_run_reopens_on_its_own_instrument.py` | example | Drive the REAL window: does a CR30 project reopen as a CR30? | settings sandbox, ArgyllCMS |
| `scripts/drive_b22_knut_warnings_two_instruments.py` | example | a maintainer's beta-21 report, driven: his chart warns on CR30 and says nothing on SpectroScan. | display, settings sandbox, ArgyllCMS |
| `scripts/drive_b22_two_instruments_at_the_divergence.py` | example | The one state a maintainer describes: CR30 warns, SpectroScan says nothing. | display, settings sandbox |
| `scripts/drive_b8_1652_standard_buttons.py` | example | B8-1652 on screen: the standard buttons of Preferences in another language. | display, settings sandbox |
| `scripts/drive_b8_1680_knut_i1pro_names.py` | example | B8-1680 on screen: a maintainer's new i1Pro and i1Pro 3 Plus preset names. | display, settings sandbox |
| `scripts/drive_cr30_hz_and_density_tick.py` | example | Drive the REAL window over both of the owner's 2026-09-08 reports. | settings sandbox |
| `scripts/drive_cr30_left_margin_and_flag_rings.py` | example | Drive the REAL ChromIQ window for two CR30 faults the owner found on screen. | - |
| `scripts/drive_guided_instrument_leaks_between_projects.py` | example | Does a project's stored Guided instrument survive opening another project? | settings sandbox |
| `scripts/drive_k51_i1pro_group.py` | example | K51-E (a maintainer, #182 5846297769, K50-5; B8-1336): Preferences > Chart Layout, the i1Pro group, ON SCREEN, with the ChromIQ layout engine ON. | display, settings sandbox |
| `scripts/drive_youtube_cr30_shows_colormunki.py` | example | Reproduce, on screen: a CR30 chart whose Guided panel says ColorMunki. | settings sandbox |
| `scripts/i1profiler_to_ti1.py` | example | CLI wrapper around workflow.i1profiler_import. | - |
| `scripts/instrument_parity.py` | TOOL | Does every instrument behave like the others on the Create Chart tab? | settings sandbox, ArgyllCMS |
| `scripts/instrument_parity_drive.py` | TOOL | Drive the same Create Chart sequence for every instrument ON SCREEN, and lay the photographs side by side. | display, settings sandbox, ArgyllCMS |
| `scripts/make_cr30_hex_demo.py` | example | Build the ChromIQ-CR30-hex-demo pack: a two-page CR30 honeycomb, scans of both pages, and REAL measurements read off those scans. | ArgyllCMS |
| `scripts/make_lights_v4333_fixture.py` | example | Make tests/data/i1pro2_lights_v4333_trace.txt: what ChromIQ 4.3.33 put on the (fake) USB wire in one whole i1Pro 2 life, with the lights Beta option off and on. | - |
| `scripts/make_lights_v4334_fixtures.py` | example | Make the ChromIQ 4.3.34 lights fixtures: what 4.3.34's own drivers put on the (fake) USB wire in one whole i1Pro 2 life and one whole i1Pro 3 life. | - |
| `scripts/probe_print_chart_buttons.py` | example | The four Print Chart buttons, measured in a real window, in one language. | settings sandbox |
| `scripts/ti1_to_i1profiler.py` | example | CLI wrapper around workflow.i1profiler_export. | - |

### Printing (23)

| file | kind | what it does | needs |
|---|---|---|---|
| `scripts/adv17d_the_bottom_check_on_a_custom_paper.py` | example | Adversary 17d, probe 6: the bottom-text check on a CUSTOM paper. | display, settings sandbox |
| `scripts/adv17e_a_larger_paper_does_help.py` | example | Adversary 17e / P1: "A larger paper does not help": driven on screen. | display, settings sandbox |
| `scripts/adv20d_the_larger_paper_denial.py` | example | Adversary 20d, in a REAL window. | display, settings sandbox |
| `scripts/adv21b_the_lock_the_paper_and_the_levers.py` | example | Adversary 21b: the tick, the paper sentence and the two levers. | display, settings sandbox |
| `scripts/drive_b22_the_pdf_door_on_screen.py` | example | B8-364 on screen: the PDF door closes while the red line is up. | display, settings sandbox |
| `scripts/drive_b8_1221_paper_filter_matrix.py` | example | B8-1221: the paper filter's MATRIX, on screen (a maintainer, #182 5838170697 to 5838625234, beta 43). | display, settings sandbox, ArgyllCMS |
| `scripts/drive_b8_1490_help_headings.py` | example | B8-1490 (a maintainer, #182 5856723428): the help windows show their topic lead-ins and headings in bold, driven ON SCREEN in the real app. | display, settings sandbox |
| `scripts/drive_b8_1640_paper_orientation.py` | example | B8-1640 on screen: the Create Chart paper list in another language. | display, settings sandbox |
| `scripts/drive_beta14_paper_white.py` | example | On screen: Simulate paper white inside the preview's indicator (beta 14). | display, settings sandbox |
| `scripts/drive_cr_help_cards.py` | example | Drive the real ChromIQ Help window, on screen, and prove the scanner cards. | settings sandbox |
| `scripts/drive_help_cards_onscreen.py` | example | Open the real Welcome window on screen and photograph help cards. | display, settings sandbox |
| `scripts/drive_k45_pdf_layout.py` | example | K45 (a maintainer, #182 5834422633): the Measurement Report's PDF layout, driven ON SCREEN, on any tree, so the same cases run before and after a change. | display, settings sandbox |
| `scripts/drive_k5_paper_white_line.py` | example | K5 (a maintainer, beta 34): "White (1) - L* 100.0" beside a light blue swatch. | display, settings sandbox |
| `scripts/drive_k9_pdf_folder.py` | example | K9 (a maintainer, beta 34): "Save Report as PDF" did not open at the correct reports/ folder. *"Make sure this is tested on screen on working app for all the levels the report feature should save reports and pdfs in."* | display, settings sandbox |
| `scripts/drive_pdf_export_timing.py` | example | #182 beta 38: WHEN is "Save report as PDF…" on disk? Driven ON SCREEN. | display, settings sandbox |
| `scripts/k45_compare_pdfs.py` | example | Compare the before and after PDFs of drive_k45_pdf_layout.py, page by page. | - |
| `scripts/k47_compare_pdfs.py` | example | Compare the before and after PDFs of drive_k47_graph_limits.py. | - |
| `scripts/pdf_colour_passthrough_probe.py` | example | Does a chart file still hold its own numbers after macOS has drawn it? (#133) | - |
| `scripts/printer_paper_tables.py` | example | Write and check data/printer_paper_profiles.json: per printer model, the paper profile (and the other keys) its macOS print dialog writes for each medium in application colour matching ("Photoshop manages colours"). | display, settings sandbox |
| `scripts/proof_help_card_prints.py` | example | Print every Help card to PDF and render the pages, so they can be LOOKED at. | - |
| `scripts/proof_help_cards_through_the_real_printer.py` | example | Prove a help card prints WHOLE and at FULL SIZE, through the real print path. | - |
| `scripts/survey_ppd_no_cm.py` | example | Survey vendor PPDs for "no colour management" options. | - |
| `scripts/uia_print_dialog.ps1` | example | The Windows 11 print dialog (the WinUI "modern" one Windows shows for a Win32 app's PrintDlgEx since 24H2), read and answered by UI Automation (#205). It is a window of its own (ApplicationFrameWindow, hosted outside ... | - |

### Charts and layout (60)

| file | kind | what it does | needs |
|---|---|---|---|
| `scripts/adv17b_patch_first_false_warning.py` | example | Adversary 17b: is the lifted patch-first height check ever WRONG? | display, settings sandbox |
| `scripts/adv19a_the_margin_box_has_two_names.py` | example | Adversary 19a, in a REAL window. | display, settings sandbox |
| `scripts/adv20c_no_margin_clears_it_except_36_5.py` | example | Adversary 20c, in a REAL window, PHOTOGRAPHED. | display, settings sandbox |
| `scripts/adv21f_the_top_two_grid_points.py` | example | Adversary 21f: does any denial still have a clear margin under it? NO. | display, settings sandbox, maintainer's paths: adapt first |
| `scripts/adv21g_two_clear_margins_and_a_flat_denial.py` | example | Adversary 21g: RETRACTED. The two-point island was my own arithmetic. | display, settings sandbox |
| `scripts/adv22d_the_margin_where_the_panel_says_nothing.py` | example | Adversary 22d: the right margins where the panel is silent and the sheet still cuts the note, and the ones where its number is simply wrong. | display, settings sandbox, ArgyllCMS |
| `scripts/adv22e_the_predicted_layout_name_on_every_route.py` | example | Adversary 22e: the predicted stamp line, on every route Generate can take. | display, settings sandbox, ArgyllCMS |
| `scripts/adv27b_the_declaration_on_a_profiling_chart.py` | example | Round 27b: a maintainer's declaration rule on a PROFILING chart, through the doors. | settings sandbox |
| `scripts/adv_b20r4_cube_corners_on_screen.py` | example | B8-290 reproduced and then re-measured in a REAL Measurement Report window. | display, settings sandbox |
| `scripts/b8_matrix_demo.py` | example | Demo data that triggers every combination of the two misread tests (#182, 4.3.5 beta 8, UMM 10.12), for the on-screen verifier scripts/drive_b8_matrix.py. | ArgyllCMS |
| `scripts/derive_margin_seeds.py` | example | Derive empirical margin-threshold seeds from the shipped ColorMunki presets. | ArgyllCMS |
| `scripts/drive_182_c2_margin_fold.py` | example | Challenge 2, target 3: the collapsible margin warnings, driven ON SCREEN. | display, settings sandbox, ArgyllCMS |
| `scripts/drive_182_combined_round1_chart.py` | example | Combined round 1: the chart panel's bottom-text promise, driven on screen. | display, settings sandbox |
| `scripts/drive_182_knut_beta19_layout_faults.py` | example | A tester's five beta-19 layout findings, driven in the REAL Create Chart tab. | display, settings sandbox, ArgyllCMS |
| `scripts/drive_182_label_frames_and_marker_help.py` | example | The renamed label frames and the marker help, photographed in a real window. | display, settings sandbox |
| `scripts/drive_182_layout_rulings.py` | example | a maintainer's three layout rulings of 2026-09-13, measured on the app's own sheets. | display, settings sandbox |
| `scripts/drive_adversary_padded_chart_refusal.py` | example | A COMPLETE verification measurement of a padded chart: taken, or turned away? | display, settings sandbox |
| `scripts/drive_b21_edge_spacers.py` | example | Does "Show only measured patches" hide BOTH edge spacers? | display, settings sandbox, maintainer's paths: adapt first |
| `scripts/drive_b21_hex_overlay_shape.py` | example | Does the split overlay follow a HEXAGON, on a real honeycomb chart? | display, settings sandbox, maintainer's paths: adapt first |
| `scripts/drive_b393_the_demo_package.py` | example | B8-393: drive EVERY project of the demo package in a real window. | display, settings sandbox |
| `scripts/drive_b8_1540_layout_mode_leak.py` | example | B8-1540 (a maintainer, #182 5857405680): a patch size typed in "Prioritise patch size, then fit to page" still ruled the preview after switching to "Prioritise chart area, then fit patches to it", driven ON SCREEN. | display, settings sandbox |
| `scripts/drive_b8_1541_layout_estimate.py` | example | B8-1541: in "Prioritise chart area" the Chart layout information's estimate column disagreed with the chart on screen. Driven ON SCREEN. | display, settings sandbox |
| `scripts/drive_b8_1590_patch_scale.py` | example | B8-1590 on screen: the patch scale in "Prioritise chart area". | display, settings sandbox |
| `scripts/drive_b8_1650_output_labels_fit.py` | example | B8-1650 on screen: the Output labels of Create Chart fit their text. | display, settings sandbox |
| `scripts/drive_b8_run6_similar_patches.py` | example | a maintainer's run 6 replayed ON SCREEN in the real app (#182, 4.3.5 beta 8). | display, settings sandbox |
| `scripts/drive_barbieri_chart_onscreen.py` | example | Drive the Barbieri Spectro 100xy chart Beta ON SCREEN, in the real window. | display, settings sandbox |
| `scripts/drive_beta147_labels.py` | example | On-screen check of a maintainer's beta.144 report: the two label rules and the help card. | - |
| `scripts/drive_beta39_demo_package.py` | example | #182 K29, driven ON SCREEN: a sample of the release demo package. | display, settings sandbox |
| `scripts/drive_chal35_a_newer_row_leaks_between_targets.py` | example | Challenge round 35: a per-target setting the stored blob has never heard of. | display, settings sandbox, ArgyllCMS |
| `scripts/drive_demo_09.py` | example | Walk Demo-09-Run-Descriptions in the REAL app, step by step. | - |
| `scripts/drive_demo_package.py` | example | Walk the demo package's own steps in the REAL app and check each one. | - |
| `scripts/drive_dg_create_chart_frame_gaps.py` | example | AGENT DG: the two info frames under the Create Chart TIFF preview. | settings sandbox, maintainer's paths: adapt first |
| `scripts/drive_hex_locks_the_inert_controls.py` | example | Drive the REAL ChromIQ window for a maintainer's hexagon report (4.1.5-beta.10). | settings sandbox |
| `scripts/drive_hex_overhang.py` | example | Drive the REAL ChromIQ window over a SpectroScan HEX chart at CR30 sizes. | - |
| `scripts/drive_hex_overlay.py` | example | Drive the REAL ChromIQ window over a hexagonal chart and photograph the overlay, so the geometry can be judged by eye as well as by number. | - |
| `scripts/drive_hex_overlay_matrix.py` | example | Does the patch overlay land on the patch: across every case that matters? | maintainer's paths: adapt first |
| `scripts/drive_hex_sample_clamp.py` | example | Drive the REAL Scanner-profile dialog over a hexagonal chart and photograph the Sample area control, so the cap can be seen rather than believed. | ArgyllCMS |
| `scripts/drive_imported_chart_pages.py` | example | Import a chart file on its own, on screen, and check the run can be printed. | display, settings sandbox, ArgyllCMS |
| `scripts/drive_k15_demo_pack.py` | example | K15 (a maintainer, beta 34): the rebuilt demo pack, opened as a user opens it. | display, settings sandbox |
| `scripts/drive_k25_layout_against_the_mockup.py` | example | a maintainer's beta-25 mockup, measured, and the real window measured beside it. | display, settings sandbox |
| `scripts/drive_k50_create_chart.py` | example | K50 (a maintainer, #182 5845519118 and 5845588201): Create Chart, ON SCREEN. | display, settings sandbox, ArgyllCMS |
| `scripts/drive_k61_demo_thresholds.py` | example | K61 (a maintainer, #182 5851645723): *"Test the demo projects on-screen on real app and via simulations, and compare the results"*. The ON-SCREEN half. | display, settings sandbox |
| `scripts/drive_layout_estimate_chart_unchanged.py` | example | Same preset in, same chart out: the byte-for-byte half of the fix. | settings sandbox, maintainer's paths: adapt first |
| `scripts/drive_layout_estimate_columns.py` | example | The Chart-layout-information panel's two columns, audited in the REAL window. | settings sandbox, maintainer's paths: adapt first |
| `scripts/drive_per_target_settings.py` | example | Are chart / measure / build-profile / print settings kept INDIVIDUAL between runs, a verification and the calibration?: a maintainer, 2026-08-11: | ArgyllCMS |
| `scripts/drive_restore_used_chart.py` | example | Press Restore Used Chart for real, on every target that ships one. | ArgyllCMS |
| `scripts/drive_seed_field_shows_the_chart.py` | example | Drive the REAL ChromIQ window through the owner's exact seed-field sequence. | ArgyllCMS, maintainer's paths: adapt first |
| `scripts/drive_target_ui_restore_clobber.py` | example | the owner's report, reproduced: Guided + SpectroScan + 4x6 + Generate lands in Manual with ColorMunki selected. | ArgyllCMS |
| `scripts/drive_the_gamut_chart_faults.py` | example | Build a FROM PROFILE GAMUT chart with the app and read its report on screen. | display, settings sandbox, ArgyllCMS |
| `scripts/hex_page_manifest.py` | example | Hash every rendered page of a hexagon matrix, so pooling can be proved inert. | - |
| `scripts/make_demo_package.py` | example | Build the #130 demo package: one project per case in the model, plus a step-by-step document, zipped. | ArgyllCMS |
| `scripts/make_demo_projects.py` | TOOL | Build demo / dummy ChromIQ projects for testing (#130, a maintainer 2026-07-28). | ArgyllCMS |
| `scripts/make_margin_fixtures.py` | example | Make tests/data/margin_fixtures.json from a tester's ruler diagnostics files (the margin tolerance Beta, 2026-11-16). | - |
| `scripts/make_notes_demo.py` | example | A demo project that reaches every N-A reason the report can print (#182 G12). | - |
| `scripts/make_sample_projects.sh` | example | Generate nicely-named sample profiling projects for documentation screenshots. Output goes to .sample_data/ (gitignored). Requires ArgyllCMS + a reference profile to simulate measurements off of. | ArgyllCMS |
| `scripts/make_screenshot_charts.py` | example | Generate A3 i1Pro test charts whose patches secretly spell a word (pixel art). | ArgyllCMS |
| `scripts/make_switching_demo.py` | example | Build the downloadable per-target-settings SWITCHING demo package. | ArgyllCMS |
| `scripts/make_targen_device_types.py` | example | Regenerate workflow/targen_device_types.py's table from targen itself. | ArgyllCMS |
| `scripts/probe_182_which_column_is_the_patch_edge.py` | example | Which column _detect_writable_band believes the patch area ends at. | - |
| `scripts/render_50_layout_reference.py` | example | Build one FIXED engine chart and hash the result, so the same build can be run from two commits and compared byte for byte. | - |

### Profiles and colour (18)

| file | kind | what it does | needs |
|---|---|---|---|
| `scripts/adv21d_the_gamut_module_hears_nothing.py` | example | Adversary 21d: FROM PROFILE GAMUT and the panel that goes silent. | display, settings sandbox, ArgyllCMS |
| `scripts/adv22a_the_gamut_module_now_speaks.py` | example | Adversary 22a: the FROM PROFILE GAMUT module now speaks; is it telling the truth there? | display, settings sandbox |
| `scripts/drive_162_gamut_count_default.py` | example | Drive the REAL ChromIQ window through #162: the in-gamut colour count. | ArgyllCMS |
| `scripts/drive_182_no_profile_notice.py` | example | Drive the REAL Print Chart tab and read the notice under a greyed-out "Through the profile", in a project whose profile is in ANOTHER run. | display, settings sandbox |
| `scripts/drive_adversary_stale_cie_scale.py` | example | Does a measurement ALREADY ON DISK on the 0..1 CIE scale reach a profile? | display, settings sandbox |
| `scripts/drive_bz_cmyk_preview_profile.py` | example | Drive the REAL ChromIQ window and show what the bundled CMYK profile does. | settings sandbox |
| `scripts/drive_colprof_algorithm_lists.py` | example | AGENT CQ: drive the REAL windows, and build a REAL profile from every entry. | settings sandbox, ArgyllCMS, maintainer's paths: adapt first |
| `scripts/drive_neutral_appearance.py` | example | Drive the REAL ChromIQ window in Light, Dark and Neutral, and record it. | settings sandbox, maintainer's paths: adapt first |
| `scripts/drive_neutral_chrome.py` | example | Measure the chrome's non-neutral pixels, screen by screen, before and after. | settings sandbox |
| `scripts/drive_neutral_controls.py` | example | Open every CONTROL surface in Neutral and count the pixels that still carry a hue. | settings sandbox, ArgyllCMS, maintainer's paths: adapt first |
| `scripts/drive_neutral_icons.py` | example | Census of every non-grey pixel in the Neutral appearance, icon-first. | settings sandbox |
| `scripts/drive_neutral_states.py` | example | Photograph the ChromIQ modules that only exist in SOME configuration, or only WHILE something is happening. | settings sandbox, ArgyllCMS |
| `scripts/drive_neutral_viewers.py` | example | Photograph every ChromIQ VIEWER: empty and with the user's own work in it. | settings sandbox |
| `scripts/find_non_neutral_pixels.py` | example | Find every pixel in the Neutral appearance that is not a grey, and name the widget that painted it. | - |
| `scripts/gen_cie_data.py` | example | One-time generator: extract CIE reference tables from ArgyllCMS's xspect.c into workflow/cie_data.py. | maintainer's paths: adapt first |
| `scripts/hash_neutral_controls.py` | example | Grab every control surface in ONE appearance and hash it. | settings sandbox |
| `scripts/prove_neutral_control_faults.py` | example | The three faults the owner reported by eye: pictured and MEASURED. | settings sandbox |
| `scripts/prove_neutral_icons.py` | example | Grab, at REAL SIZE, every icon this branch changed -- and hash whole windows. | settings sandbox |

### Driving and photographing the app (138)

| file | kind | what it does | needs |
|---|---|---|---|
| `scripts/adv17f_three_faults_on_screen.py` | example | Adversary 17f: three faults in the bottom/top sheet-text notice block, driven in a REAL window. | display, settings sandbox |
| `scripts/adv23c_the_sheet_the_app_built_re_rendered.py` | example | Adversary 23c: the bottom text's own ink on the sheet the app built. | display, settings sandbox |
| `scripts/adv_b20r4_autosize_on_screen.py` | example | §R8 "Size = auto" driven in a REAL window, twice in a row: combined round 4. | display, settings sandbox |
| `scripts/adv_b20r6_drive_the_colliding_names.py` | example | Combined round 6: confirm round 5's two fixes by DRIVING the real window. | display, settings sandbox, maintainer's paths: adapt first |
| `scripts/capture_landing_extras.py` | example | Two extra landing-page shots that capture_screens.py does not take. | display |
| `scripts/capture_screens.py` | TOOL | Capture ChromIQ documentation screenshots from the real, running app. | display, settings sandbox, ArgyllCMS |
| `scripts/capture_showcase_40.py` | example | Capture the ChromIQ 4.0 showcase screenshots: the NEW features, from the real running app, version shown as plain 4.0.0 (no beta suffix). | - |
| `scripts/drive_130.py` | example | The single on-screen runner for issue #130 (a maintainer agreed to the merge, 2026-07-26). | - |
| `scripts/drive_130_test_plan.py` | example | Drive the REAL ChromIQ app through the #130 verification-runs test plan against the load-test fixtures (scripts/make_load_test_data.py). | - |
| `scripts/drive_160_guided_does_not_touch_manual.py` | example | Drive the REAL ChromIQ window: Guided must never write into Manual (#160). | ArgyllCMS |
| `scripts/drive_163_clip_branding.py` | example | Drive the REAL ChromIQ window through #163: the clip-border branding. | - |
| `scripts/drive_164_after_shots.py` | example | Screenshots of everything #164 changed, taken from the REAL window. | - |
| `scripts/drive_182_add_window_counts.py` | example | a maintainer's Patch Set editor batch (#182), reproduced and re-photographed in the REAL app, in a REAL window. | display |
| `scripts/drive_182_bottom_stamp_warning.py` | example | a maintainer's bottom-stamp case, in the REAL Create Chart tab. | display, settings sandbox, ArgyllCMS |
| `scripts/drive_182_challenge_four.py` | example | #182 FOURTH CHALLENGE ROUND: the export nobody measured, and the state that survives. | display, settings sandbox |
| `scripts/drive_182_challenge_four_edges.py` | example | #182 CHALLENGE ROUND against the four-edge text specification. | display, settings sandbox |
| `scripts/drive_182_challenge_three.py` | example | #182 THIRD CHALLENGE ROUND: the fifth copy, the second page, and the extremes. | display, settings sandbox, ArgyllCMS |
| `scripts/drive_182_challenge_two.py` | example | #182 SECOND CHALLENGE ROUND: the fourth copy, the centred band, Guided, four edges at once. | display, settings sandbox |
| `scripts/drive_182_combined_round1_dpi.py` | example | Combined round 1: the highest resolution the box offers, in a real window. | display, settings sandbox |
| `scripts/drive_182_combined_round1_freeze.py` | example | Combined round 1: what the restored rise search costs the READER, in the real panel, at the resolutions the Resolution box offers. | display, settings sandbox |
| `scripts/drive_182_combined_round1_promises.py` | example | Combined round 1: every remedy the bottom-text notices name, APPLIED. | display, settings sandbox |
| `scripts/drive_182_combined_round1_scope.py` | example | Combined round 1, the seam: can the "Saved reports" pulldown (B8-250) silently change which measurements the document covers (B8-246)? | display, settings sandbox |
| `scripts/drive_182_combined_round2_delete.py` | example | Combined round 2: what does a user lose when the only saved report of a PROFILING measurement is deleted? | display, settings sandbox |
| `scripts/drive_182_combined_round2_freeze_breakdown.py` | example | Combined round 2: the 5.9-second repaint round 1 could not explain. | display, settings sandbox |
| `scripts/drive_182_combined_round2_freeze_order.py` | example | Combined round 2: the 5.9-second repaint, and whether it is memory. | display, settings sandbox |
| `scripts/drive_182_combined_round2_seams.py` | example | Combined round 2: the seams round 1 did not reach. | display, settings sandbox |
| `scripts/drive_182_combined_round3_delete.py` | example | Combined round 3: drive the saved-report DELETE path until it breaks. | display, settings sandbox |
| `scripts/drive_182_declaration_lifecycle.py` | example | B8-409: the control-strip declaration's lifecycle, in the REAL app. | settings sandbox, ArgyllCMS |
| `scripts/drive_182_final_sweep.py` | example | The last challenge round: the shapes the earlier ones did not touch. | display, settings sandbox, maintainer's paths: adapt first |
| `scripts/drive_182_four_side_symmetry.py` | example | SYMMETRY AUDIT: what the REAL window says about each of the four sides. | display, settings sandbox |
| `scripts/drive_182_generate_waits.py` | example | The Generate-report button, in the REAL Measurement Report window. | display, settings sandbox |
| `scripts/drive_182_grey_rows_are_graded.py` | example | The grey rows are graded and the note is numbered, in a REAL report window. | display, settings sandbox |
| `scripts/drive_182_half_point_sizes.py` | example | Every Size box steps half a point, in the REAL window. | display, settings sandbox |
| `scripts/drive_182_knut_beta9_case.py` | example | a maintainer's beta 9 report, reproduced in the REAL window and on a REAL sheet. | display, settings sandbox |
| `scripts/drive_182_mixed_sets.py` | example | Reproduce: a report whose red line says the reports were not all judged against the same limit set, on a REAL window, from the pack the design authority supplied. | display, settings sandbox, maintainer's paths: adapt first |
| `scripts/drive_182_mixed_sets_add.py` | example | Two GRADED verification histories, judged against different limit sets, in one window: the shape D9 named ("two projects") and the one the red line was written for. Driven in a REAL window. | display, settings sandbox, maintainer's paths: adapt first |
| `scripts/drive_182_one_set_challenge.py` | example | The challenge round against B8-246: assume the one-limit-set fix broke something a user can see, and try to prove it in a REAL window. | display, settings sandbox, maintainer's paths: adapt first |
| `scripts/drive_182_profiling_sheet_verdict.py` | example | What the report window says about a run's OWN profiling measurement. | display, settings sandbox |
| `scripts/drive_182_right_edge_k1_k5.py` | example | K1 and K5 from a maintainer's beta 7 report, measured by driving the REAL window. | display, settings sandbox |
| `scripts/drive_182_right_left_edges.py` | example | #182 RIGHT AND LEFT PAGE EDGES: driven in the REAL window, on screen. | display, settings sandbox |
| `scripts/drive_182_round3_capture_probe.py` | example | Why did ONE capture of round 3's delete run refuse, twice, in the same place? | display, settings sandbox |
| `scripts/drive_182_the_five_rows.py` | example | B8-397: the five limit rows that had no detection, in the REAL windows. | display, settings sandbox |
| `scripts/drive_182_top_bottom_edges.py` | example | On-screen proof for the TOP and BOTTOM page edges of #182 (a maintainer, 2026-09-12). | display, settings sandbox, ArgyllCMS |
| `scripts/drive_182_warning_gaps.py` | example | K2 / K3 / K4 (#182, a maintainer, beta 7): the truncations that say nothing. | display, settings sandbox, ArgyllCMS |
| `scripts/drive_55_transport_note.py` | example | Report 55: does the transport note actually appear on screen, and read well? | - |
| `scripts/drive_adversary_align_undo.py` | example | Does the Auto align undo let go when the PICTURE changes, or only when the Patch sample area does? | display, settings sandbox |
| `scripts/drive_b21_split_overlay_gap.py` | example | Photograph the split-patch overlay against the chart it is drawn on. | display, settings sandbox, maintainer's paths: adapt first |
| `scripts/drive_b22_the_document_record.py` | example | B8-383/382/381/380 after the document record, driven in a real window. | display, settings sandbox |
| `scripts/drive_b385_the_blank_sheet.py` | example | B8-385: "Show only measured patches" in the two reading modes that are not strips, driven in a REAL window on a REAL screen. | display, settings sandbox |
| `scripts/drive_b385_the_default_path.py` | example | B8-385 on the DEFAULT path: a chart that already HAS its measurement. | display, settings sandbox |
| `scripts/drive_b3_run_type_switch_never_hangs.py` | example | a maintainer's beta-2 hang, driven ON SCREEN in the real window (#182 6144104040). | display, settings sandbox |
| `scripts/drive_b42_c2_fixes.py` | example | Beta 42, the fixes for challenge round 2, driven ON SCREEN. | display, settings sandbox |
| `scripts/drive_b42_c5_fixes.py` | example | Challenge 5 of beta 42, the fixes (B8-1091 to B8-1095), ON SCREEN. | display, settings sandbox |
| `scripts/drive_b42_k33.py` | example | B42, a maintainer #182 5816565326 (K33), driven ON SCREEN. | display, settings sandbox |
| `scripts/drive_b42_k34.py` | example | B42, a maintainer #182 5817809396 (K34, section A of 5802027116), driven ON SCREEN. | display, settings sandbox |
| `scripts/drive_b42_k36.py` | example | B42, a maintainer #182 5820871320 (K36), driven ON SCREEN. | display, settings sandbox |
| `scripts/drive_b42_k37.py` | example | B42, a maintainer #182 5822758830 answer 1 (K37), driven ON SCREEN. | display, settings sandbox |
| `scripts/drive_b42_x_and_prefs.py` | example | B42, a maintainer #182 5815435713 and 5815501486, driven ON SCREEN. | display, settings sandbox |
| `scripts/drive_b43_k39.py` | example | K39 (a maintainer, #182 5831246553), driven ON SCREEN, on any tree. | display, settings sandbox |
| `scripts/drive_b8556_guided_stamp.py` | example | B8-556: drive Guided / CR30 / A4 / hexagon in a REAL window and keep proof. | display, settings sandbox |
| `scripts/drive_b8570_the_verdict_ruling.py` | example | B8-570: a maintainer's verdict ruling, DRIVEN ON SCREEN in a real window. | display, settings sandbox |
| `scripts/drive_b8_1226_pinned_note.py` | example | B8-1226 on screen: the paper-filter note PINNED under both preset lists (a maintainer, #182 5839478031: *"not visible before scrolling to the bottom. Can the message be made to always stay visible at the bottom"*). | display, settings sandbox |
| `scripts/drive_b8_1260_to_1263_fixes.py` | example | B8-1260, B8-1262 and B8-1263 (beta 44 challenge F1, F6, F7), on screen. | display, settings sandbox, ArgyllCMS |
| `scripts/drive_b8_1285_preferences_and_restart.py` | example | B8-1284 to B8-1287: Preferences, the i1Pro Chart Defaults preset and the saved engine recipe, ON SCREEN. | display, settings sandbox, ArgyllCMS |
| `scripts/drive_b8_1392_gc_inside_events.py` | example | B8-1392: does the APP collect garbage inside Qt's event delivery, and can that crash it? ON SCREEN, real window, the app built as main() builds it. | display, settings sandbox |
| `scripts/drive_b8_1500_saved_vs_new.py` | example | B8-1500 and B8-1503 (a maintainer, #182 5857473253): a saved report is shown exactly as it was saved; a new report works every date out again. Driven ON SCREEN in the real app. | display, settings sandbox |
| `scripts/drive_b8_1521_italic.py` | example | B8-1521: a parameter help's *surface* shows in italic, not as asterisks, driven ON SCREEN in the real app. | display, settings sandbox, ArgyllCMS |
| `scripts/drive_b8_1571_photo_card_estimate.py` | example | B8-1571 on screen: a maintainer's 10 x 15 cm photo card, selected in Create Chart, Manual (it generates on selection). After Generate, Chart layout information's "on screen" and "estimate" patch sizes must read the ... | display, settings sandbox |
| `scripts/drive_b8_1591_nothing_moves_before_generate.py` | example | B8-1591 (a maintainer, #182 5858874320): no setting of the Measurement Report window changes the page before Generate Report is pressed. Driven ON SCREEN in the real app. | display, settings sandbox |
| `scripts/drive_b8_1700_pharmacist_431.py` | example | B8-1700 on screen: the five "by Pharmacist" charts of 4.3.1. | display, settings sandbox, ArgyllCMS |
| `scripts/drive_b8_matrix.py` | example | Every combination of the two misread tests, ON SCREEN in the real app (#182, 4.3.5 beta 8; UMM 10.12 and its 35-row table). | display, settings sandbox |
| `scripts/drive_barbieri_import_onscreen.py` | example | Drive the Barbieri Beta's Spectro32 IMPORT ON SCREEN, in the real window. | display, settings sandbox |
| `scripts/drive_beta12_c_preview_switch.py` | example | On screen: the preview's indicator as a switch (beta 12 build C, the owner). | display, settings sandbox |
| `scripts/drive_beta29_the_window_fits.py` | example | B8-547 and B8-548 on screen: the window fits, and the ISO half says a sentence. | display, settings sandbox, maintainer's paths: adapt first |
| `scripts/drive_beta39_g7.py` | example | #182 beta 39, G7, driven ON SCREEN: Generate report across profile runs and across projects, in Verification, Profiling and Calibration. | display, settings sandbox |
| `scripts/drive_beta39_k28a.py` | example | #182 beta 39, K28a, driven ON SCREEN as a user (scripts/userdrive.py). | display, settings sandbox |
| `scripts/drive_border_visual_proof.py` | example | Visual proof for the content-aware preview frame, at every point it touches. | ArgyllCMS |
| `scripts/drive_chal34b_the_yardstick_split.py` | example | Challenge round 34b: two runs the window calls the same set, one document. | display, settings sandbox |
| `scripts/drive_chal36_restore_reverts_the_whole_meta.py` | example | Challenge round 36: Restore Used Chart reverts the run's WHOLE meta.json. | display, settings sandbox |
| `scripts/drive_clip_says_when_overridden.py` | example | On-screen proof for fix/clip-says-when-overridden. | settings sandbox |
| `scripts/drive_d23_update_archives.py` | example | D23 on the Update path, driven as a user on Report-Limits-Threshold-Series. | display, settings sandbox |
| `scripts/drive_delete_plan.py` | example | On-screen test plan for the #130 Delete button (a maintainer, 2026-07-28). | - |
| `scripts/drive_feature_b_onscreen.py` | example | Drive features A + B in the real widgets, end to end, with real Argyll. | ArgyllCMS |
| `scripts/drive_final_round_fc2_fc3.py` | example | Final round before beta 36: FC-2 (a profiling sheet beside dated verifications is refused, and says why), FC-3 (the guide explains no ChromIQ mechanics) and FC-8 (Unlock after Clear list), on screen on the project a ... | display, settings sandbox |
| `scripts/drive_fogra_reference_values_onscreen.py` | example | The Reference values window with Fogra in it, driven on screen. | display, settings sandbox, maintainer's paths: adapt first |
| `scripts/drive_g12_notes.py` | example | #182 G12: every N-A note, and the Printing record's detailed sections, driven ON SCREEN. | display, settings sandbox |
| `scripts/drive_guided_mode_jump.py` | example | Find what moves Create Chart off Guided when a chart is generated. | ArgyllCMS |
| `scripts/drive_guided_ss_4x6.py` | example | Reproduce the owner's log: Create Chart in Guided, SpectroScan, 4x6, Generate. | ArgyllCMS |
| `scripts/drive_helper_markers_move.py` | example | Drive the REAL ChromIQ window through the #158 helper-marker move. | - |
| `scripts/drive_import_module_onscreen.py` | example | Drive the Measure tab's IMPORT module in the real widgets, with real Argyll. | - |
| `scripts/drive_iso_values_ship.py` | example | #182 S-2 (§23): the ISO 12647 values PREPARED to ship, driven ON SCREEN. | display, settings sandbox |
| `scripts/drive_k13_types_by_run_type.py` | example | K13 (a maintainer, beta 34): which report types each run type offers. | display, settings sandbox |
| `scripts/drive_k14_coverage_count.py` | example | K14 (a maintainer, beta 34): "This report covers 1 of the 18 measurements recorded for this project" on a Printing record of a project with three profile runs. | display, settings sandbox |
| `scripts/drive_k16_two_of_three.py` | example | K16 (a maintainer, beta 34): 2 of 3 measurements ticked, Generate, Create New, and the new report was flagged "One date" with the ticks collapsed to one. | display, settings sandbox |
| `scripts/drive_k17_two_runs_type.py` | example | K17 (a maintainer, beta 34): Verification, measurements from two runs ticked, and the report type could not be chosen at all. | display, settings sandbox |
| `scripts/drive_k25_bug2_mechanism.py` | example | a maintainer's beta-25 bug 2, driven to its MECHANISM in a real window. | display, settings sandbox |
| `scripts/drive_k25_restore_and_generate.py` | example | a maintainer's two beta-25 rulings about a SELECTED report, driven in a REAL window. | display, settings sandbox |
| `scripts/drive_k26.py` | example | #182 K26 (a maintainer 5792484060, 5792576954), driven ON SCREEN. | display, settings sandbox |
| `scripts/drive_k2_preflight_with_history.py` | example | a maintainer, #182 on beta 34 (K2): the pre-flight still opens on a run with history. | settings sandbox |
| `scripts/drive_k3_standard_note.py` | example | K3 (a maintainer, beta 34): run 3 of Report-Limits-Threshold-Series, Full colour check against "Quick check", carried note 1) "The standard calls this metric recommended rather than required" on the two grey balance ... | display, settings sandbox |
| `scripts/drive_k42.py` | example | #182 K42 (a maintainer on beta 42, 5832746557), driven ON SCREEN. | display, settings sandbox, ArgyllCMS |
| `scripts/drive_k46.py` | example | #182 K46 (a maintainer, 5834773589), driven ON SCREEN. | display, settings sandbox, ArgyllCMS |
| `scripts/drive_k49_reference_rows.py` | example | K49 (a maintainer, #182 5841092535): the paper row and the two solid rows compared with the profile ((b2)), and a graph of a row with values but no limit shown with its own sentence. Driven ON SCREEN, on any tree, so ... | display, settings sandbox |
| `scripts/drive_k4_generate_unchanged.py` | example | K4 (a maintainer, beta 34): Generate report on a selected report with no setting changed created a new report without asking. | display, settings sandbox |
| `scripts/drive_k51_star.py` | example | K51 (a maintainer, #182 5846167083, analysis 3): the verification star under rule (4) with his modifications. Driven ON SCREEN, on any tree, so the same steps run before and after the change. | display, settings sandbox |
| `scripts/drive_k59_raw_sheets.py` | example | K59 (a maintainer, #182 5849392788): sheets printed raw, option C, and no "drift". Driven ON SCREEN, real windows, photographs by onscreen_capture. | display, settings sandbox |
| `scripts/drive_k60_raw_openings.py` | example | K60 (a maintainer, #182 5850164956, D1 to D3): the raw openings and a raw sheet's repeatability rows. Driven ON SCREEN, real windows, photographs by onscreen_capture. | display, settings sandbox |
| `scripts/drive_k_feedback_repro.py` | example | Reproduce a maintainer's 2026-08-23 batch in the REAL window, before anything is fixed. | - |
| `scripts/drive_marker_overlay_union.py` | example | Prove what a maintainer counted: the preview draws TWO combs at once. | - |
| `scripts/drive_name_accents.py` | example | Drive the REAL ChromIQ window to prove a project name keeps its accents. | display, settings sandbox, ArgyllCMS, maintainer's paths: adapt first |
| `scripts/drive_nelson_split_overlay.py` | example | Proof for Nelson Lau: the expected-vs-measured split on his own 10x15 cm chart, with and without the chart's geometry sidecar. | - |
| `scripts/drive_new_run_seeding.py` | example | Does "New run" really start from the last selected run's chart settings? | ArgyllCMS |
| `scripts/drive_onscreen_e2e.py` | example | End-to-end ON-SCREEN run of the real ChromIQ app (the owner, #130 2026-07-29). | - |
| `scripts/drive_pairing3_onscreen.py` | example | Drive the pairing-3 batch in the real widgets, on screen, with real Argyll. | - |
| `scripts/drive_pre_runs_migration.py` | example | Drive the REAL ChromIQ window over a tester's pre-redesign project. | display, settings sandbox |
| `scripts/drive_profiling_import_round4.py` | example | Challenge round 4 for the Measure tab's profiling import: the roads rounds 1 to 3 did not take. | display, settings sandbox |
| `scripts/drive_profiling_import_round5.py` | example | Challenge round 5: the path this change was NOT supposed to touch. | display, settings sandbox |
| `scripts/drive_profiling_import_round6.py` | example | Challenge round 6: the doors that REFUSE. | display, settings sandbox |
| `scripts/drive_r27_photograph_the_open_state.py` | example | R27-F3, photographed: the window names one report and draws another. | display, settings sandbox |
| `scripts/drive_r4_note_box.py` | example | R4 (a maintainer, 2026-09-22): the "different numbers of readings" note must be a clear information note, not body text. Driven as a user: Verification run1, Tools > Measurement Report, "Add profile's ... | display, settings sandbox |
| `scripts/drive_repeatability_rows.py` | example | ChromIQ's own two repeatability rows, on screen, in a real window. | display, settings sandbox |
| `scripts/drive_restore_seed.py` | example | Drive the REAL ChromIQ app to prove a restored chart comes back unchanged. | - |
| `scripts/drive_set_appearance_takes_three.py` | example | Drive the REAL ChromIQ window and record what every appearance-taking component decides, in Light and in Dark. | settings sandbox, maintainer's paths: adapt first |
| `scripts/drive_square_corners_b8_650.py` | example | B8-650: photograph the three bare-StyledPanel frames, on screen. | display, settings sandbox |
| `scripts/drive_the_bar_on_every_tab.py` | example | What the target bar ACTUALLY does on each of the five tabs, measured. | display, settings sandbox |
| `scripts/drive_the_turn_is_saved_and_restored.py` | example | Drive the REAL window: is "Straight strips" saved and honoured everywhere? | settings sandbox |
| `scripts/drive_the_unapplied_change_warning.py` | example | Drive the REAL window: when does the "you have not built this yet" line show? | settings sandbox, ArgyllCMS |
| `scripts/drive_theme_is_asked.py` | example | Drive the REAL ChromIQ window and ask the seven sites what they decide. | settings sandbox, maintainer's paths: adapt first |
| `scripts/fix32_onscreen.py` | example | ON SCREEN: every user-visible sentence the round-32 fix set changed. | display, settings sandbox |
| `scripts/mockup_acc133_panel.py` | example | Redraw docs/mockups/acc133/acc_1_panel.png: the #133 Create Chart panel. | - |
| `scripts/onscreen_capture.py` | TOOL | Photograph a real window, or say plainly that it could not be done. | display, settings sandbox, ArgyllCMS |
| `scripts/onscreen_capture_win.py` | TOOL | Photographing real windows on WINDOWS, for on-screen drivers (#205). | - |
| `scripts/probe_182_c3_capture_guard.py` | example | Challenge round 3: attack _window_captures, the capture guard. | display |
| `scripts/probe_182_c3_capture_guard_sweep.py` | example | Challenge round 3, second sweep: is there a spelling the guard STILL misses? | display |
| `scripts/probe_182_c3_mutate_capture_guard.py` | example | Prove the third round's two capture-guard fixes actually land. | - |
| `scripts/render_49_reference.py` | example | Render one FIXED TiffPreview scene to a PNG, so the same scene can be rendered from two commits and diffed. Imports only ui.tiff_preview, so it runs unchanged inside a git worktree of an older commit. | - |
| `scripts/splice_landing_shots.py` | example | Put freshly captured screenshots into the landing page (docs/index.html). | - |
| `scripts/userdrive.py` | TOOL | Drive ChromIQ ON SCREEN the way a user does, and read the log afterwards. | display, settings sandbox |

### Other one-off checks (88)

| file | kind | what it does | needs |
|---|---|---|---|
| `scripts/adv14_alignment_attack.py` | example | ADVERSARY round 14: the bottom-text Alignment control, attacked on screen. | display, settings sandbox |
| `scripts/adv14_alignment_doors.py` | example | ADVERSARY 14: a maintainer's doors for the new Alignment parameter, on screen. | display, settings sandbox |
| `scripts/adv17_the_lower_b_lever.py` | example | Adversary 17: does *"lower “B” under “Text distance from edge (mm)”"* work? | display, settings sandbox |
| `scripts/adv17b_how_long_the_panel_takes.py` | example | Adversary 17b: what the bisection costs while a spin box is being turned. | display, settings sandbox |
| `scripts/adv17b_the_lever_and_the_rise.py` | example | Adversary 17b: the two NEW sentences, driven in a real window. | display, settings sandbox |
| `scripts/adv17b_the_lever_offer_is_kept.py` | example | Adversary 17b: where the lever IS still offered, pulling it must clear it. | display, settings sandbox |
| `scripts/adv17b_the_lever_that_stops_at_the_markers.py` | example | Adversary 17b: "lowering B buys the same room" is false above the markers. | display, settings sandbox |
| `scripts/adv17b_what_a_spin_box_step_costs.py` | example | Adversary 17b: what ONE step of the bottom-margin spin box really costs. | display, settings sandbox |
| `scripts/adv17c_the_rise_applied_in_the_window.py` | example | Adversary 17c: type the number the message names into the box it names. | display, settings sandbox |
| `scripts/adv17d_raise_bottom_by_0_0_mm.py` | example | Adversary 17d, probe 3: two states the new ceiling created, photographed. | display, settings sandbox |
| `scripts/adv17d_the_line_under_the_pulldown.py` | example | Adversary 17d, probe 5: "the line under the pulldown says why". | display, settings sandbox |
| `scripts/adv17d_the_new_sentence.py` | example | Adversary 17d: the sentence round 3 left behind, and the box it names. | display, settings sandbox |
| `scripts/adv17e_the_greyed_entry_itself.py` | example | Adversary 17e / P3: "the greyed entry itself says why when you open the list". | display, settings sandbox |
| `scripts/adv17e_the_rise_named_through_a_locked_box.py` | example | Adversary 17e / P2: the rise is worked out in a state the reader must leave. | display, settings sandbox |
| `scripts/adv17f_pointing_at_the_greyed_entry.py` | example | Adversary 17f / P4: _WHEN_HELP's THIRD wording. | display, settings sandbox |
| `scripts/adv17f_the_top_check_and_a_marker_box_typed_zero.py` | example | Adversary 17f / P3b: the TOP strip-letter check with the marker boxes at 0. | display, settings sandbox |
| `scripts/adv17g_the_overlay_and_the_note.py` | example | Adversary 17g, driven in a REAL window. | display, settings sandbox |
| `scripts/adv18a_the_overlay_crossed.py` | example | Adversary round 18a, driven in a REAL window. | display, settings sandbox |
| `scripts/adv18b_the_caption_that_cannot_be_cleared.py` | example | Adversary 18b, in a REAL window. | display, settings sandbox |
| `scripts/adv18c_the_guided_branch_on_a_manual_sheet.py` | example | Adversary 18c, in a REAL window. | display, settings sandbox |
| `scripts/adv18d_the_honeycomb_and_a_build_in_flight.py` | example | Adversary 18d, in a REAL window. | display, settings sandbox |
| `scripts/adv18e_unticking_the_master_box.py` | example | Adversary 18e, in a REAL window. | display, settings sandbox |
| `scripts/adv1_count_glyphs.py` | example | Count the glyphs actually printed in a band, off the sheet the app wrote. | - |
| `scripts/adv1_four_sides_attack.py` | example | ADVERSARY ONE: the sheet's four sides, on screen, measured off the TIFF. | display, settings sandbox |
| `scripts/adv1_remedies_attack.py` | example | ADVERSARY ONE: do what every warning says, and see whether it goes away. | display, settings sandbox |
| `scripts/adv20a_the_untried_bottom_states.py` | example | Adversary 20a, in a REAL window. | display, settings sandbox |
| `scripts/adv20b_the_ceiling_claim_on_a_buildable_sheet.py` | example | Adversary 20b, in a REAL window. | display, settings sandbox |
| `scripts/adv21a_the_rise_walk_at_both_ends.py` | example | Adversary 21a: the rise search, attacked at BOTH ends, in a REAL window. | display, settings sandbox |
| `scripts/adv21e_what_a_held_arrow_key_costs.py` | example | Adversary 21e: the cost of the rise walk with an arrow key HELD DOWN. | display, settings sandbox |
| `scripts/adv21h_the_two_point_island_named_exactly.py` | example | Adversary 21h: the state named exactly, and the error found in the prober. | display, settings sandbox |
| `scripts/adv21j_clears_warns_or_cannot_be_built.py` | example | Adversary 21j: three answers, not two, at every margin on the box. | display, settings sandbox |
| `scripts/adv22b_the_stamp_line_the_two_modes_predict.py` | example | Adversary 22b: 33 characters in MANUAL, 55 in FROM PROFILE GAMUT, one sheet. | display, settings sandbox |
| `scripts/adv22c_press_generate_twice_and_the_warning_changes.py` | example | Adversary 22c: press Generate twice, change nothing, and the warning reports a different number of cut characters. | display, settings sandbox, ArgyllCMS |
| `scripts/adv22f_the_states_no_sweep_reached.py` | example | Adversary 22f: the bottom-text warning in the states no sweep has reached. | display, settings sandbox |
| `scripts/adv23a_the_panel_against_the_sheet.py` | example | Adversary 23a: the bottom-text warning against the sheet the app builds. | display, settings sandbox |
| `scripts/adv23b_the_rise_by_the_arrow_keys.py` | example | Adversary 23b: the rise the message names, typed with the ARROW KEYS. | display, settings sandbox |
| `scripts/adv23e_the_notice_after_every_gesture.py` | example | Adversary 23e: is the notice ON THE PANEL the notice this state has earned? | display, settings sandbox |
| `scripts/adv23f_what_a_panel_refresh_costs.py` | example | Adversary 23f: what one "Measured from Preview" refresh costs. | settings sandbox |
| `scripts/adv23g_the_stamp_prediction_on_the_untried_routes.py` | example | Adversary 23g: the predicted stamp line on the routes no round has driven. | display, settings sandbox, ArgyllCMS |
| `scripts/adv23h_the_markers_a_box_typed_zero_draws.py` | example | Adversary 23h: the overlay's marker-reserve convention, photographed. | display, settings sandbox |
| `scripts/adv29_a_project_that_moved.py` | example | Adversary round 29: a saved #182 report, opened from a project that MOVED. | display, settings sandbox |
| `scripts/adv29_the_generate_popup.py` | example | Adversary round 29: Generate report's new three-button question, pushed. | display, settings sandbox |
| `scripts/adv29_two_doors.py` | example | Adversary round 29, focused: the two Generate doors the round never opened. | display, settings sandbox |
| `scripts/adv30_eighteen_px_is_forty_two.py` | example | Round 30: setFixedHeight(18) gives a 42 px button under ChromIQ's stylesheet. | display |
| `scripts/adv30_press_every_new_control.py` | example | Adversary round 30: press every control beta 26 added, in a real window. | display, settings sandbox |
| `scripts/adv30_the_door_and_the_lie.py` | example | Adversary round 30: through the REAL door, and what the grey line then says. | display, settings sandbox |
| `scripts/adv30_the_reference_values_window.py` | example | Adversary round 30: the Reference values window, pressed on screen. | display, settings sandbox |
| `scripts/adv30_what_happens_when_a_slot_raises.py` | example | Adversary round 30, job 2: what does ChromIQ DO when a slot raises? | settings sandbox |
| `scripts/adv_b20r5_attack_the_flat_migration.py` | example | Round 5 adversary: the flat-project migration, attacked as DATA. | settings sandbox, maintainer's paths: adapt first |
| `scripts/adv_b20r6_attack_the_shared_name_rule.py` | example | Beta 20 round 6 attack: flat legacy projects whose folder name collides with their own files, migrated and compared file by file (one-off example; its output paths are the maintainer's). | settings sandbox, maintainer's paths: adapt first |
| `scripts/analyse_b21_mono_leak.py` | example | the owner's detector: with a monochrome chart and a grey overlay, colour = leak. | - |
| `scripts/analyse_b21_split_overlay_gap.py` | example | Measure the split overlay against the chart image it is drawn on. | - |
| `scripts/audit_interaction_state_rules.py` | TOOL | Audit the colours in every INTERACTION-STATE stylesheet rule, from source. | - |
| `scripts/audit_tool_file_placement.py` | TOOL | Where does every Tool put the files it saves: and does it ask the run type? | - |
| `scripts/b8_matrix_verdicts.py` | example | VERDICTS.md from the on-screen run of scripts/drive_b8_matrix.py. | - |
| `scripts/chal31_the_reference_values_window.py` | example | Challenge round 31: the Reference values window, driven in a REAL window. | display, settings sandbox |
| `scripts/check_issue_133_numbers.py` | example | Re-derive every checkable claim in issue #133 from the code. | ArgyllCMS |
| `scripts/derive_prebuilt_geometry.py` | example | Generate scan-recognition geometry for the prebuilt chart bundles. | ArgyllCMS |
| `scripts/diag_native_cm.py` | example | No-ink diagnostic for the macOS native-print colour-management-off path. | - |
| `scripts/install_iso_12647_values_into_repo.py` | example | Copy ISO 12647 values into the repository's own data file, PRINTING NONE. | - |
| `scripts/iso_values_template.py` | example | Write a file a licence holder can fill in with ISO 12647 tolerance values. | - |
| `scripts/issue_new_comments.py` | example | Say what is new on a GitHub issue since the last time this was asked. | - |
| `scripts/k61_compare.py` | example | K61: the SIMULATION half of drive_k61_demo_thresholds.py, and the comparison of the two. Offscreen, data only: the same charts and sheets of the demo pack through the same functions, no window. | - |
| `scripts/k61_threshold_matrix.py` | example | K61 (a maintainer, #182 5851645723): every requirement of every metric, one notch either side of its line, asked of the presets WINDOW and of the REPORT, and the two answers compared. A SIMULATION: the app's own ... | ArgyllCMS |
| `scripts/make_default_sounds.py` | example | Generate ChromIQ's default measurement-sound pack (#131, Phase 1). | - |
| `scripts/make_load_test_data.py` | example | Generate downloadable dummy test projects for the #130 load-function test plan. | ArgyllCMS |
| `scripts/make_workflow_diagram.py` | example | Generate the Getting Started example-workflow diagrams, one SVG per language. | - |
| `scripts/preview_card_icons.py` | example | Five icon proposals for each of the two new help cards (#130, a maintainer). | - |
| `scripts/probe_182_c2_mutate_raster.py` | example | Put d6512a18's two raster edits BACK the way they were, one at a time. | - |
| `scripts/probe_182_c2_raster_matrix.py` | example | Challenge 2, target 1: the turned strip letter, measured across the matrix. | - |
| `scripts/probe_182_c2_rotation_ink.py` | example | Challenge 2: is a TURNED strip letter really the same ink as an upright one? | - |
| `scripts/probe_182_leading_from_the_font.py` | example | What "the normal distance between two lines" is, from the renderer's font. | - |
| `scripts/probe_182_note_gap_internals.py` | example | Where tiff_metadata._stamp_one actually puts the chart note, and why. | - |
| `scripts/probe_182_note_gap_whatif.py` | example | What the chart note would look like if the band detector saw the real gap. | - |
| `scripts/probe_182_pair_diff.py` | example | How two chart pages differ, column by column. Used to check that a control/variant pair really differs by one thing only. | - |
| `scripts/probe_182_right_edge_crop.py` | example | Crop the right-hand band of a chart TIFF to a PNG so it can be LOOKED at. | - |
| `scripts/probe_48_legend_placement.py` | example | On-screen probe for report 48: legend chip placement + event plumbing. | maintainer's paths: adapt first |
| `scripts/probe_50_geometry.py` | example | Engine geometry facts for a set of cases, so two commits can be compared. margins is (top, right, bottom, left) -- instruments.build's own order. | - |
| `scripts/probe_50_row_numbers.py` | example | Render the owner's area-first CR30 hex chart at a range of LEFT margins and crop the left edge, so the clamped row numbers can be looked at. | - |
| `scripts/probe_b202_mutations.py` | example | Mutation probe for the #202 fix: put back each fault (or its most likely wrong variant) one at a time, run the #202 tests, require RED, restore. | - |
| `scripts/probe_dialog_exit_after_reentrant_pump.py` | example | Does a dialog's exec() return when it is accepted from a timer and the same callback then keeps calling processEvents()? On screen (cocoa), no Qt but plain widgets, no ChromIQ. | settings sandbox |
| `scripts/probe_popup_watchdog_mutations.py` | example | Mutation probes for PopupWatchdog: each mutation is applied to a COPY of scripts/onscreen_capture.py, the test file is run against the copy, and the result must be RED. The repo file is never touched. | - |
| `scripts/probe_tab_headings.py` | example | Every tab heading, measured as INK rather than as advance, in a real window. | settings sandbox |
| `scripts/prove_tooltip_icon.py` | example | The Preferences ⓘ icon, at real size, with its contrast measured. | settings sandbox |
| `scripts/ptyrun.py` | TOOL | Run a console program in a pseudo-terminal, answer its questions in turn, keep a transcript. | - |
| `scripts/real_settings_copy.py` | example | A throw-away COPY of the user's real ChromIQ preferences, for seeding sandboxes. | - |
| `scripts/repro_bug_d.py` | example | Reproduce (or rule out) #130 Bug D: with the Profile-run bar set to "Overwrite run 1", selecting a preset builds into run 2 instead of run 1. | ArgyllCMS |
| `scripts/sweep_every_tab_for_clipping.py` | TOOL | Every tab, every heading, every button: what is CLIPPED, and by how much. | settings sandbox |

<!-- END GENERATED -->
