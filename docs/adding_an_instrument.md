# Adding a measuring instrument to ChromIQ

Thank you for wanting to bring another instrument to ChromIQ. This guide is for
you, and just as much for the coding agent you may be working with (Codex,
Claude Code, Copilot, Cursor and others). It collects what the project learned
from the two instruments ChromIQ already drives with its own code, the ChnSpec
**CR30** and the Konica Minolta **FD-9**, so that your first pull request is
close to finished when you open it.

If you are an agent: read this whole file and [`CLAUDE.md`](../CLAUDE.md)
before you change anything, then plan your work against the
[registration checklist](#5-the-registration-checklist). A ready-made prompt
for your agent is in
[`docs/adding_an_instrument_agent_prompt.md`](adding_an_instrument_agent_prompt.md).

**Contents**

1. [Who this is for, and what you bring](#1-who-this-is-for-and-what-you-bring)
2. [Talk to us first](#2-talk-to-us-first)
3. [What kind of instrument is it?](#3-what-kind-of-instrument-is-it)
4. [Behind a Beta option, and off means no change](#4-behind-a-beta-option-and-off-means-no-change)
5. [The registration checklist](#5-the-registration-checklist)
6. [Creating a chart for the instrument](#6-creating-a-chart-for-the-instrument)
7. [Measuring](#7-measuring)
8. [Files and settings](#8-files-and-settings)
9. [The driver and the device](#9-the-driver-and-the-device)
10. [Text the user reads](#10-text-the-user-reads)
11. [Design specifications and the message catalogue](#11-design-specifications-and-the-message-catalogue)
12. [Tests and the release gate](#12-tests-and-the-release-gate)
13. [Checking in the real app, on screen](#13-checking-in-the-real-app-on-screen)
14. [Opening the pull request](#14-opening-the-pull-request)
15. [Common mistakes we have seen](#15-common-mistakes-we-have-seen)
16. [Where to read more](#16-where-to-read-more)

---

## 1. Who this is for, and what you bring

ChromIQ is a PyQt6 GUI for ArgyllCMS printer profiling
(`targen > printtarg > print > chartread > colprof`). Most instruments reach it
through ArgyllCMS. This guide is about the rest: an instrument ChromIQ has to
talk to itself, or one ArgyllCMS knows but ChromIQ does not offer yet.

**Please bring:**

- [ ] **A working driver or connection.** Code that already talks to the
      instrument and returns readings (spectra or XYZ/Lab), outside ChromIQ if
      need be. Building a driver from nothing inside a ChromIQ pull request is
      too much for one review.
- [ ] **The instrument in your hands**, for as long as the review takes.
- [ ] **Tests that use invented data only.** No readings, calibration bytes,
      scans or network transcripts from a real unit go into the repository
      (see [section 9](#9-the-driver-and-the-device)).
- [ ] **Willingness to test on the hardware** when reviewers ask a question
      only the device can answer, and to report what you saw with photos,
      screenshots and short log lines.

**Why the hardware part matters so much:** the maintainers cannot test hardware
they do not own. Everything that depends on the device is verified by you. That
is also why a new instrument ships behind a Beta option
([section 4](#4-behind-a-beta-option-and-off-means-no-change)), and why your
pull request description says clearly what was and was not tested on the
device ([section 14](#14-opening-the-pull-request)).

Nothing in this guide is a promise that a pull request will be merged. It is
the list of things a review will look for, written down so you can do them
first.

## 2. Talk to us first

Open a
[feature request](https://github.com/itsab1989/ChromIQ/issues/new?template=feature_request.yml)
titled "New instrument: <make and model>" before you write much code. Say which instrument it is, how it connects (USB serial, USB HID,
Bluetooth, Ethernet), what your driver can already do, its licence, and which
existing integration you plan to model it on (next section). The maintainers
may know of constraints this guide does not cover yet.

Ask on GitHub, too, whenever your plan would **contradict a design
specification** in `docs/design/` or the text of an existing message. Those
documents are binding (see [section 11](#11-design-specifications-and-the-message-catalogue)),
and changing them is the maintainers' decision, not something to settle inside
a pull request.

## 3. What kind of instrument is it?

| Kind | Examples | Model it on | Route |
|---|---|---|---|
| **ArgyllCMS already drives it**, ChromIQ does not offer it yet | a strip reader in ArgyllCMS's list | the i1Pro / ColorMunki entries | Registration only ([section 5](#5-the-registration-checklist)): labels, layout engine geometry, pace row. ArgyllCMS does the reading. |
| **Handheld spot or strip instrument** with its own driver | ChnSpec CR30 (USB serial and Bluetooth) | **CR30**: the measure bridge | ChromIQ's own `chromiq-chartread` (in `native/`) runs the session with external values (`-xx`: it opens no instrument and asks ChromIQ for each patch's XYZ over a JSON channel, `workflow/measure_manager.py::MeasureParams.external_values`). `workflow/cr30/measure_bridge.py::Cr30MeasureBridge` answers each prompt with a reading from the device. chartread keeps the session, the `.ti3` and all the measurement logic. |
| **Scanning strip reader** with its own driver | a motorised or hand-swept strip reader ArgyllCMS does not know | usually **CR30**, if the driver can hand over patch by patch | Open an issue first. If readings can be delivered patch by patch, the bridge works and you get resume, re-reading and the end-of-session windows for free. A new third route needs the maintainers' agreement. |
| **Automatic chart reader or XY table** | Konica Minolta FD-9 (Ethernet) | **FD-9**: its own path | An autonomous reader that pre-scans the sheet and returns whole rows. A per-patch prompt protocol would only add a translation layer, so it has its own worker (`ui/fd9_measurement.py::FD9Job`), its own chart generator (`workflow/fd9/chart.py`) and its own `.ti3` writer, and shares everything else with the other instruments: the Start preflight, the instrument lease, the end-of-session window, the archiving of a replaced measurement. |
| **Scanner or camera** | a flatbed scanner, a camera on a copy stand | the existing scanner route | Not an instrument in this sense. ChromIQ already reads charts from a scan with ArgyllCMS `scanin` (`workflow/scanin_runner.py`, Tools > "Build profile with scanner or camera"). Open an issue if that route does not fit your device. |

**The CR30 in short.** Device code lives in `workflow/cr30/` (frames,
transport, session, Bluetooth, discovery, colour). The Measure tab opens the
bridge in `ui/tabs/tab_measure.py::_open_cr30_bridge`; calibration windows are
`ui/cr30_calibration.py::Cr30CalibrationMixin`; the M-CR30-* messages are in
`workflow/measurement_messages.py`. Its chart carries the honest name the
device reports (`TARGET_INSTRUMENT "CR30"`), which stock ArgyllCMS chartread
refuses, so `ui/tabs/tab_measure.py::_blocked_by_stock_chartread_for_cr30`
offers to switch to ChromIQ's own reader. Provenance notes are in
`workflow/cr30/PROVENANCE.md`. The CR30 predates the Beta rule below and is not
behind an option; a new instrument is.

**The FD-9 in short.** Written and contributed by **lessbones** in pull request
#213, which is the reason this guide exists in the form it does: it was a large,
careful piece of work, and the review rounds that followed taught us exactly
which places a new instrument touches. The vendored driver is
`vendor/fd9-independent/`; ChromIQ's glue is `workflow/fd9/` (chart, sessions,
measurement, export, preview), `ui/fd9_measurement.py::FD9MeasureMixin` (the
Measure tab part). Its sheet and patch sizes, gaps and page count use the
shared `ui/dialogs/layout_options_panel.py` and ordinary layout recipes;
`ui/dialogs/fd9_sheet.py` supplies only the instrument note. The switch is `workflow/fd9/support.py`. Read
`workflow/fd9/README.md` for its own overview.

## 4. Behind a Beta option, and off means no change

A new instrument goes behind a checkbox in **Preferences > Beta**, off by
default. **With it off, ChromIQ behaves exactly as it did before your pull
request**, for every user, in every list, window and file. This is what lets
the maintainers ship something they cannot test themselves.

### How to build the switch

Copy the FD-9's pattern; it was reviewed twice.

- [ ] **One module is the switch.** `workflow/fd9/support.py` holds the setting
      name, `workflow/fd9/support.py::fd9_enabled`,
      `workflow/fd9/support.py::latch_from` and, for tests,
      `workflow/fd9/support.py::set_enabled_for_this_process`. It imports
      nothing heavy, so asking it costs nothing.
- [ ] **Restart to apply.** Instrument lists are built when the window is
      built, so a live switch would leave half the app on the old answer.
      `main.py` latches the value once before the window exists, and the
      Preferences row shows "Takes effect after you restart ChromIQ." while the
      checkbox differs from the value this run of ChromIQ is using
      (`ui/dialogs/settings_dialog.py::_fd9_support_toggled`).
- [ ] **The setting lives in `core/settings.py::DEFAULTS`**, default `False`.
- [ ] **The Preferences row** sits on the Beta tab of
      `ui/dialogs/settings_dialog.py`: a checkbox, an ⓘ
      (`ui/tooltip_button.py::TooltipButton`) that explains what the
      instrument is, what turning the option on adds and where, the limits of
      this first version, and who contributed it, plus the restart hint.
- [ ] **Every hook in shared code asks the switch first**, and asks it before
      reading any file. Import your instrument's modules lazily, inside the
      functions that need them, so with the option off they are never loaded.
- [ ] **A chart made for your instrument, opened with the option off**, is
      refused at Start with a friendly window that names the Preferences
      option (the FD-9's is `workflow/measurement_messages.py::M_FD9_SUPPORT_OFF`,
      shown by `ui/tabs/tab_measure.py::_fd9_support_off_window`). It is not
      "corrected" to another instrument's name.
- [ ] **Stale settings are harmless.** A user can turn the option on, make a
      chart, then turn it off again. Saved instrument choices and saved layout
      recipes that name your instrument must then read as "none". Per-target
      settings that name it stay in the store as they are, for the day the
      option is on again, but only for a value the user has not changed: the
      tab shows a fallback instrument, and that fallback is not the user's
      choice, so it is never filed into the target. A value the user changes
      is the user's and is written. See
      `ui/tabs/tab_chart.py::_stored_defaults_recipe`,
      `workflow/measure_settings.py::carry_fd9_keys` (Measure) and
      `workflow/fd9/support.py::carry_fd9_chart_keys` (Create Chart target
      settings). The Create Chart carry follows four rules:
      a stored value is carried only while the value on screen is still the
      one the target opened with and the user has never had another one
      written (the stored values are those read when the target was opened,
      `workflow/fd9/support.py::Fd9OffSnapshot`, never the file as it reads
      at write time, because by then it can hold the user's own earlier
      change); nothing is carried after the user generates into the run
      (`ui/tabs/tab_chart.py::_forget_fd9_off_screen`); and nothing is
      carried once the run's `.ti2` `TARGET_INSTRUMENT` is not your
      instrument's (`workflow/fd9/support.py::chart_names_fd9`); and once the
      user changes a block's instrument, the whole block is theirs and none
      of its stored values are carried again, so no margin or gap of your
      instrument ends up beside another one. Opening your
      project with the option off and changing tabs must leave its
      `meta.json` byte-identical.

### How to prove it

`tests/test_fd9_off_changes_nothing.py` and
`tests/test_fd9_off_stale_project.py` are the model; write the same four nets
for your instrument.

1. **A child process builds the real main window and Preferences with the
   option off** and reports every combo box entry, every widget object name
   and every loaded module. Your instrument anywhere, or your modules loaded at
   all, fails. Run it twice: from fresh settings and from stale settings that
   name your instrument
   (`tests/test_fd9_off_changes_nothing.py::test_the_real_window_offers_no_fd9_and_loads_none_of_its_code`).
2. **In process, the Measure tab with the option off**: your chart and an
   ordinary chart are loaded and started, your chart detector is never called,
   and no target's stored settings gain a key.
3. **The list of shared files that mention your instrument is pinned**
   (`tests/test_fd9_off_changes_nothing.py::HOOKED_FILES`,
   `tests/test_fd9_off_changes_nothing.py::test_the_files_that_name_the_fd9_are_the_known_ones`).
   A new hook is then a deliberate act that shows in the diff, and comes with a
   test that it does nothing while the option is off.
4. **A real project, on then off**: make a chart with the option on, restart
   with it off, open the project and change tabs; `meta.json` is
   byte-identical and none of your modules load
   (`tests/test_fd9_off_stale_project.py::test_an_fd9_project_opened_with_the_beta_off_is_left_as_it_was`).
   The same file also proves that a change the user makes with the option off
   is kept, also when they change a value and back with a write in between
   (`tests/test_fd9_off_stale_project.py::test_a_change_the_user_makes_with_the_beta_off_is_kept`,
   `tests/test_fd9_off_stale_project.py::test_a_change_back_after_a_write_without_a_reload_is_kept`),
   and that Generate with the option off, which makes an i1Pro chart in
   the run, leaves no trace of your instrument in its `meta.json`
   (`tests/test_fd9_off_stale_project.py::test_generating_an_i1pro_chart_into_the_fd9_run_leaves_no_fd9`).
   Each half runs in its own process, because the switch is read once per
   process. `tests/test_fd9_review_r4.py` proves the carry rules over random
   sequences of edits, writes and Generate.

Tests of the instrument itself turn the option on for their process with an
autouse fixture like `tests/_fd9_beta.py::fd9_beta_on`.

## 5. The registration checklist

Every place an instrument has to be known, with the test that holds it. Not
every row applies to every kind of instrument; for each one you skip, say why
in the pull request. The FD-9 short code is `FD9` and the CR30's is `CR30`;
yours will be a similar short code.

### Create Chart: the lists

- [ ] **Guided's instrument list**: `data/patch_db.py::INSTRUMENT_LABELS`
      (code to label). Filter it with your switch where the combo is filled in
      `ui/tabs/tab_chart.py` (look for `INSTRUMENT_LABELS.items()`).
      `data/patch_db.py::EXTERNAL_INSTRUMENTS` is only for instruments another
      program lays out.
- [ ] **Manual's printtarg `-i` choice**: `data/parameters.yaml` (`choices`,
      `labels`, and a bullet for your instrument in `tooltip_body`) and the
      labels in all 13 `data/i18n/parameters.<code>.yaml` overlays. Filter the
      choice while the option is off, as the FD-9 does with
      `ui/tabs/tab_chart.py::_without_choice`, and add its ⓘ bullet only while
      it is offered (`ui/tabs/tab_chart.py::fd9_instrument_bullet`).
      Enforced by `tests/test_i18n.py` (overlays cover every parameter).
- [ ] **The layout panel** (also used by Preferences > Chart Layout):
      `ui/dialogs/layout_options_panel.py::LayoutOptionsPanel.INSTRUMENTS` for
      an always-offered instrument, or, behind the switch, the
      `ui/dialogs/layout_options_panel.py::LayoutOptionsPanel.instruments`
      classmethod that adds it, as the FD-9 does.
- [ ] **Preset groups and built-in presets**, if you ship any:
      `ui/tabs/tab_chart.py::INSTRUMENT_GROUP_LABELS`,
      `ui/tabs/tab_chart.py::BUILTIN_PRESET_GROUPS`, and read
      `docs/dev_builtin_presets.md` first.
- [ ] **Margin labels and Preferences instrument limits**:
      `ui/tabs/tab_chart.py::_MARGIN_INSTR_LABEL`,
      `workflow/layout_engine/instruments.py::_MARGIN_LABEL_TO_KEY`,
      `core/settings.py::THRESHOLD_INSTR_LABEL` and
      `ui/dialogs/settings_dialog.py::SettingsDialog._MARGIN_INSTRUMENTS` (the
      CR30 is in all of them), with seed thresholds in
      `core/settings.py::default_margin_thresholds`. The FD-9 is deliberately
      absent: its geometry is fixed, so there is no margin to choose.

### Create Chart: the layout

- [ ] **Full name for files**:
      `workflow/layout_engine/instruments.py::TARGET_INSTRUMENT_NAME`
      (see [section 6](#6-creating-a-chart-for-the-instrument) for the naming
      rule).
- [ ] **Geometry**: `workflow/layout_engine/instruments.py::_build_base`, and
      `workflow/layout_engine/instruments.py::supported` if the engine should
      list it. Model: `tests/test_cr30_registration.py`.
- [ ] **Engine routing**: `workflow/chart_creator.py::ENGINE_INSTRUMENTS`, and
      `workflow/chart_creator.py::ENGINE_ONLY_INSTRUMENTS` when printtarg
      cannot lay the instrument out (anything not in
      `workflow/ti2_relayout.py::PRINTTARG_INSTRUMENTS`). Enforced for the CR30
      by `tests/test_a_cr30_is_always_an_engine_chart.py`.
- [ ] **An own chart generator** (only if the engine cannot draw your chart,
      as for the FD-9): the engine hands over in
      `workflow/layout_engine/chart.py::build_chart`, and capacity, placement
      and the preview's rectangles come from your code through
      `workflow/layout_engine/geometry.py::compute`,
      `workflow/layout_engine/geometry.py::placement`,
      `workflow/layout_engine/geometry.py::strip_rects_px` and
      `workflow/layout_engine/geometry.py::patch_rects_px`; the edge spacers
      in `workflow/layout_engine/presets.py` and the capacity in
      `workflow/chart_creator.py` branch too. Each of these branches asks the
      switch as well as the key (an old chart or a stored recipe can still
      hand them the key while the option is off): with the option off the
      engine must refuse your instrument as unknown, as
      `workflow/layout_engine/instruments.py::build` and
      `workflow/layout_engine/geometry.py` do for the FD-9
      (`tests/test_fd9_off_changes_nothing.py::test_the_layout_engine_knows_no_fd9_while_off`).
- [ ] **Papers**: `workflow/layout_engine/papers.py::list_papers`,
      `workflow/layout_engine/papers.py::ENGINE_EXCLUDED_PAPERS`,
      `data/patch_db.py::EXCLUDED_PAPERS`, `data/patch_db.py::PAPER_FALLBACK`.
- [ ] **Recipes**: `workflow/layout_engine/presets.py::LayoutRecipe` and
      `workflow/layout_engine/presets.py::default_recipe` for any field of your
      own.
- [ ] **Patch set editor** (Tools > Edit / create chart patch set):
      `workflow/ti2_relayout.py::instrument_to_flag` and the label map in
      `ui/dialogs/ti2_relayout_dialog.py`, or, if the editor cannot lay your
      chart out, a refusal like `ui/main_window.py::_refuse_editor_for_fd9`
      plus a row in `docs/design/tool_availability.md`.

### Loading a chart and its files

- [ ] **Instrument names a chart can carry**:
      `ui/ti2_loader.py::KNOWN_INSTRUMENTS`, a check that a chart is yours,
      behind the switch and lazily imported (the FD-9's are
      `workflow/fd9/support.py::is_fd9_instrument_name` and
      `workflow/fd9/measurement.py::is_fd9_chart`; the CR30's, which is not
      gated, is `ui/ti2_loader.py::is_cr30`), and
      `ui/ti2_loader.py::instrument_family` for instruction wording. Related tests:
      `tests/test_target_instrument_gate.py`,
      `tests/test_instrument_matches_chart.py`,
      `tests/test_chart_instrument_comes_from_the_chart.py`.
- [ ] **FWA compensation (-f)**: `workflow/fwa_gate.py` is the one place
      that answers whether FWA can be used for a measurement, and why not.
      ArgyllCMS applies -f only to the exact instrument names in
      `workflow/fwa_gate.py::ARGYLL_FWA_INSTRUMENTS` (measured with
      `spec2cie -f`); a measurement without spectra, under any other name, or
      taken under M1/M2 has the option greyed with a reason and -f left out.
      A new instrument gets its own `FwaRefusal` kind only if it needs its
      own text (the FD-9 has one). Also look at
      `workflow/profile_engine/fwa.py::instrument_supports_fwa` (ChromIQ's
      engine) and `ui/ti2_loader.py::spectral_options_unavailable` (the
      illuminant and observer).
- [ ] **Sidecar files** (if your chart has one, like `.fd9.json`):
      `core/file_manager.py::CHART_COMPANION_SUFFIXES` and
      `workflow/chart_import.py::_CHART_EXTS`, so copy, rename, import and
      reset keep it with the chart.

### Measure tab

- [ ] **Routing at Start**: `ui/tabs/tab_measure.py::_on_start`. Either the
      chartread route (CR30), or a branch at the top of `_on_start` to your own
      start method, which then runs the same preflight steps in the same order
      ([section 7](#7-measuring)).
- [ ] **Controls that do not apply** are greyed with a reason, not hidden in
      silence: `ui/tabs/tab_measure.py::_apply_cr30_dead_options`,
      `ui/tabs/tab_measure.py::_apply_cr30_pbp_lock`.
- [ ] **Pace row** (Preferences > Measurement, minimum reading speed):
      `core/measure_pace.py::MODEL_DEFAULTS`,
      `core/measure_pace.py::ESTIMATE_PATCHES`,
      `core/measure_pace.py::model_key` and
      `core/measure_pace.py::_OTHER_MODEL_KEYS` (needed for an instrument
      ArgyllCMS does not name), plus the pace table in
      `ui/dialogs/settings_dialog.py` (see `PACE_LOCKED_ROWS` and its
      `key == "cr30"` branch). Instruments that do not swipe strips
      are listed in
      `tests/test_b202_every_offered_instrument_has_its_pace_row.py::NO_STRIPS`;
      strip readers go in
      `tests/test_b202_every_offered_instrument_has_its_pace_row.py::DEVICES`.
      That test fails for any entry of `INSTRUMENT_LABELS` that is in none of
      these and not in `EXTERNAL_INSTRUMENTS`.
- [ ] **Per-target Measure settings** of your own: an instrument-only dict like
      `workflow/measure_settings.py::FD9_CONTROLS`, not
      `workflow/measure_settings.py::MEASURE_CONTROLS`, so no other target's
      `meta.json` changes ([section 8](#8-files-and-settings)).
- [ ] **The instrument lease**: `core/instrument_lease.py::acquire`,
      `core/instrument_lease.py::release`,
      `core/instrument_lease.py::held_by_other`
      ([section 7](#7-measuring)).
- [ ] **USB presence** (ArgyllCMS instruments only):
      `core/argyll_instruments.py::ARGYLL_USB_IDS`. A device ChromIQ drives
      itself has its own discovery, like `workflow/cr30/discovery.py`.
- [ ] **Tools > Read single patches**, only for a spot instrument:
      `ui/dialogs/spot_read_dialog.py`. An automatic reader is not offered
      there (`docs/design/tool_availability.md`). A spot instrument ChromIQ
      drives itself also needs a spot manager like
      `workflow/cr30_spot_manager.py`.
- [ ] **User calibration**, for a handheld instrument that needs a white or
      black calibration from the user: windows like
      `ui/cr30_calibration.py::Cr30CalibrationMixin`, with their own message
      IDs (the CR30's are M-CR30-*).
- [ ] **Platform and operating system drivers** (USB serial, Bluetooth): the
      Python packages in `requirements.txt` (the CR30 uses pyserial and bleak),
      a driver installer for a USB bridge that needs one on Windows
      (`core/usb_driver_installer.py`, `core/ch34x_driver.py`), and a platform
      note like `docs/cr30_platform_support.md`.
- [ ] **Optional: connection diagnostics**, such as Tools > "CR30 Bluetooth
      report" (`ui/tools_popup.py`, `scripts/cr30_bluetooth_report.py`).
- [ ] **Optional: aiming help in the preview**: `ui/tiff_preview.py` draws the
      CR30's body and aperture to scale
      (`ui/tiff_preview.py::TiffPreview.set_aim_overlay`).

### Messages, text, settings, packaging, docs

- [ ] **Windows and their text**: entries in
      `workflow/measurement_messages.py` with `approved=False`, the same text
      in §M-PROPOSED of `docs/design/unified_measurement_management.md`, the
      IDs in `tests/test_message_catalogue.py::AWAITING_APPROVAL` and the
      window methods in `tests/test_message_catalogue.py::WINDOW_SOURCES`
      ([section 11](#11-design-specifications-and-the-message-catalogue)).
- [ ] **Translations** in all 13 `data/i18n/<code>.json` catalogues
      ([section 10](#10-text-the-user-reads)). Enforced by `tests/test_i18n.py`.
- [ ] **Settings** in `core/settings.py::DEFAULTS`.
- [ ] **The switch** latched in `main.py`, and its Preferences row.
- [ ] **Packaging** in `ChromIQ.spec`, `ChromIQWin.spec` and
      `ChromIQLinux.spec`, and the licence notice in `THIRD-PARTY-NOTICES.md`,
      `ui/licences.py::NOTICE_SECTIONS` and the
      `ui/licences.py::BUNDLED_LICENCE_FILES` tuple, which
      `tests/test_fd9_review_r3.py` checks against the specs
      ([section 9](#9-the-driver-and-the-device)).
- [ ] **Optional**: the welcome dialog (`ui/dialogs/welcome_dialog.py`) and the
      keyboard help (`ui/keyboard_help.py`) mention the CR30; mention yours
      only if it adds something a first-time user needs.
- [ ] **Docs**: `CHANGELOG.md` under `## Unreleased`, an "Awaiting
      confirmation" block in each design specification your instrument
      touches (one current block per topic: replace your earlier block rather
      than stacking a second one that contradicts it), and `docs/dev_folder_layout.md` for any new folder.
- [ ] **The pin of hooked files** (`HOOKED_FILES`, see
      [section 4](#4-behind-a-beta-option-and-off-means-no-change)) lists every
      shared file above that now names your instrument.

## 6. Creating a chart for the instrument

- **Names.** In every list a person reads (Guided, Manual, the layout panel,
  Preferences) use the **short model name without the vendor in front**: the
  review of the FD-9 changed "FD-9 (Konica Minolta)" to "FD-9". Put the vendor
  and a sentence about the instrument in the ⓘ instead. In the files, the
  `.ti2` and `.ti3` `TARGET_INSTRUMENT` carry the **full name**, vendor
  included, like the ArgyllCMS instruments ("GretagMacbeth i1 Pro", "X-Rite
  ColorMunki") and the FD-9 ("Konica Minolta FD-9"). The CR30 writes "CR30"
  by an explicit ruling, because that is what the device reports for itself.
  If an older spelling is already out in the world, keep reading it
  (`workflow/fd9/support.py::TARGET_INSTRUMENT_NAMES`), and recognise the name
  in any letter case and quoting
  (`workflow/fd9/support.py::is_fd9_instrument_name`).
- **Header lines.** A `.ti2` carries what the layout engine writes for every
  chart: `DESCRIPTOR`, `CREATED`, `APPROX_WHITE_POINT`, quoted `SAMPLE_LOC`
  values, and the run description (`docs/design/per_run_description.md`).
  Reuse `workflow/layout_engine/ti2_writer.py::build_ti2_text` rather than
  writing headers by hand, declare any keyword of your own with `KEYWORD`, and
  stamp the TIFF like other charts
  (`workflow/chart_creator.py::_stamp_tiff_metadata`). A `.ti3` you write
  yourself carries `CREATED`, or Inspect a measurement cannot say when it was
  measured. Prove that `colprof` accepts your `.ti3` with a test on synthetic
  data (the FD-9's is
  `tests/test_fd9_beta_option.py::test_colprof_builds_a_profile_from_an_fd9_measurement`).
- **Reading charts safely.** Any check that opens a chart file to decide
  whether it is yours reads it with `core/text_io.py::read_text` (projects
  made on a German Windows are cp1252), never raises, answers "not mine" on any
  error, and caches its answer per path and modification time. Measured case:
  `tests/test_fd9_beta_option.py::test_a_cp1252_chart_is_simply_not_an_fd9_chart`.
- **Patch sizes and apertures.** Size patches from the instrument's measuring
  opening plus a margin for placement. Strip readers record their opening in
  `workflow/layout_engine/instruments.py::STRIP_READ_APERTURE_MM`. Document
  where every number comes from (a datasheet, or your measurement), in a
  comment next to it.
- **Papers.** Offer the sheets the instrument can really take, landscape
  included where it fits, and a custom size if the instrument allows a range.
- **Markers, arrows and other furniture.** If the instrument needs fiducial
  marks or a feed arrow, draw them in your generator and update every text that
  describes them (the ⓘ, the measuring windows, greyed-control tooltips, the
  CHANGELOG, the specification). Think about orientation: the FD-9's four
  marks look the same after a 180° turn, so a reversed sheet cannot be
  detected, and the texts have to say so.
- **Help the user tell sheets apart.** Print the chart's name on the sheet,
  outside the area the instrument reads, and, if the instrument allows it,
  make a reversed or wrong sheet detectable rather than measuring it.
- **Synthetic patches use D50.** Any padding or synthetic patch your
  generator adds aims at D50, like every other ChromIQ chart, not D65.
- **Create Chart options your layout does not use** are greyed with a tooltip
  that says why (`ui/dialogs/layout_options_panel.py::fd9_greyed_reason`), and
  stay greyed after a recipe load and after the panel's own rules run
  (`ui/dialogs/layout_options_panel.py::_hold_fd9_greying`). When the user
  leaves your instrument, every control gets back what it had before,
  including values your instrument forced (for example the page count).
- **Capacity.** `data/patch_db.py` holds empirical printtarg capacities for
  ArgyllCMS instruments; an engine-laid instrument computes its own (the FD-9:
  `workflow/fd9/chart.py`). Either way, Guided's patch count must match what is
  printed.

## 7. Measuring

- **The same Start preflight as every instrument.** Before any device work,
  your Start runs what `ui/tabs/tab_measure.py::_on_start` runs: autosave
  recovery (`ui/tabs/tab_measure.py::_recover_engine_autosave`), the new-run
  and missing-chart guards, the instrument lease check, the misfit check
  (`ui/tabs/tab_measure.py::_blocked_by_a_misfitting_measurement`), the
  verification guard (`ui/tabs/tab_measure.py::_verification_guard`), the
  verification snapshot (`ui/tabs/tab_measure.py::_snapshot_verification_chart`),
  the replace warnings of §5
  (`ui/tabs/tab_measure.py::_confirm_replacing_measurement`) and resume
  staging (`ui/tabs/tab_measure.py::_stage_verification_for_resume`), in that
  order. `_on_start` branches to your start method at its very top, so your
  method runs every one of these steps itself.
  `ui/fd9_measurement.py::FD9MeasureMixin._start_fd9_measurement` is the worked
  example, and
  `tests/test_fd9_beta_option.py::test_the_start_runs_the_preflight_every_instrument_gets`
  proves it.
- **The parameter lock is never lifted during a read.**
  `ui/tabs/tab_measure.py::_set_settings_enabled` greys the options while a
  measurement runs. If your instrument greys controls of its own, keep that as
  a second lock combined with the first, and change enabling only when your
  state really changes. Never call `setEnabled(True)` on a shared control
  because "it is not my chart".
- **Patch by patch, strip arrows, the preview.** Grey the reading modes that do
  not apply with a reason, hide swipe arrows for an instrument that does not
  swipe (`ui/tiff_preview.py::set_no_swipe`), and make the preview light the
  unit the instrument actually reads (rows for the FD-9:
  `tests/test_fd9_beta_option.py::test_the_preview_lights_rows_not_columns`).
- **Resume and partial measurements.** ChromIQ resumes by patch location, and a
  replaced measurement is archived, never destroyed
  (`workflow/measurement_session.py::MeasurementSession`). A partial result
  waiting for the user's decision belongs to **its own chart only**: loading
  another chart must not let it take over that chart's Stop, quit question or
  end window (`ui/fd9_measurement.py::_fd9_engaged`). A verification
  re-measure must not get its stored chart back while your instrument still
  reads (`ui/tabs/tab_measure.py::_settle_the_replaced_chart`), and every
  ending of yours settles it. Bind a resumable session to the **device's
  identity** (for example its serial number), not to its network address: an
  address the network hands out can change between two sittings, and that once
  made a partial FD-9 run impossible to resume.
- **Endings.** Reuse the end-of-session window and its texts
  (`ui/tabs/tab_measure.py::_confirm_end_of_session`, M-END) with your counts;
  read `docs/design/measurement_exit_strategy.md` first. For multi-page charts
  look at `ui/tabs/tab_measure.py::_show_page_pause` before inventing a new
  window.
- **The instrument lease.** Ask
  `core/instrument_lease.py::held_by_other` right after the new-run and chart
  guards, and show `ui/tabs/tab_measure.py::_instrument_busy_window`
  (M-INSTRUMENT-BUSY) if another window has the instrument. Take the lease
  with `core/instrument_lease.py::acquire` and the label
  `core/instrument_lease.py::MEASURE_TAB` when you start, and release it on
  every ending, including failures.
- **Threads, and the Qt rules that keep the process alive.**
  - Device I/O never runs on the GUI thread.
  - Every worker `QThread` calls `core/thread_stack.py::roomy`
    (`tests/test_every_worker_qthread_has_a_roomy_stack.py`).
  - A worker is **not parented** to a widget and is kept in a module-level
    list until it has finished (`ui/fd9_measurement.py::_LIVE_JOBS`,
    `workflow/cr30/measure_bridge.py::_LIVE`): destroying a parent with a
    running `QThread` kills the process.
  - Connect signals to **bound methods**, never to a lambda that captures
    `self` (`tests/test_a_scrollbar_signal_never_takes_a_lambda.py`).
  - Never switch automatic garbage collection on (`core/gc_guard.py`,
    `tests/test_b8_1392_no_collection_inside_event_delivery.py`).
  - Stop is cooperative: set an event the worker checks, close the
    connection, and tell the user what state the device is in (for example a
    sheet still inside).
  - Hold `core/keep_awake.py::keep_awake` while measuring and release it
    symmetrically.
- **Errors in friendly windows.** A user never meets a raw exception such as
  `[ERROR] timed out`. Each failure the user can act on gets a window from the
  message catalogue that says what happened, what to do, and that nothing they
  already measured is lost (if true). Keep the technical reason as a detail
  line for diagnosis. **Classify failures by exception type first**, then by
  words: the FD-9 once called every `OSError` (a missing file included) "could
  not reach the FD-9", and a Windows "actively refused" message matched no
  keyword (`ui/fd9_measurement.py::fd9_exception_kind`). Faults before the
  worker starts get the generic failure window, not the connection one.
- **Log lines** are user-facing too: wrap them in `tr()` and write them for a
  person.

## 8. Files and settings

- **Settings live in `core/settings.py::AppSettings`**, never in a separate
  `QSettings` domain. Only then does `CHROMIQ_SETTINGS_FILE` sandbox them for
  drivers and tests (`tests/test_settings_can_be_sandboxed.py`). Store an
  address or port there; never a path to code that the app would import.
- **Write your keys only when your instrument is used.** Chart keys only when
  a chart for your instrument is generated; Measure keys only for your charts
  while the option is on. With the option off, keys already stored are
  carried over the fallback the tab shows
  (`workflow/measure_settings.py::carry_fd9_keys` for Measure,
  `workflow/fd9/support.py::carry_fd9_chart_keys` for Create Chart), so an
  untouched project's `meta.json` is not rewritten. On Create Chart a key is
  carried only while the user has not changed its value since the target was
  opened, never after a Generate into the run, and never once the run's
  `.ti2` `TARGET_INSTRUMENT` is not your instrument's
  (`workflow/fd9/support.py::chart_names_fd9`); a value the user changes is
  written as theirs, and once the user changes a block's instrument, the
  whole block is theirs
  ([section 4](#4-behind-a-beta-option-and-off-means-no-change)). Record new
  per-target keys in
  `docs/design/per_target_settings.md` in an "Awaiting confirmation" block
  (the FD-9's is §1.4).
- **All paths go through `Project` / `Run` / `Calibration`** in
  `core/file_manager.py`. A new folder is a property on `Run`, like
  `core/file_manager.py::Run.fd9_sessions_dir`, and is documented in
  `docs/dev_folder_layout.md`. Never build a stem pattern elsewhere.
- **Session data has a retention rule.** If each Start records evidence (raw
  data, scans, transcripts), keep what produced the filed measurement or can
  still be resumed, and delete the rest
  (`workflow/fd9/sessions.py::prune_sessions`). Previews and other
  regenerable files go in the run's `cache/` folder.
- **No device data in the repository**: see the next section.

## 9. The driver and the device

- **Licence.** ChromIQ is GPL-3.0. Vendored code must be compatible with it
  (GPL-3.0-or-later, LGPL, MIT, BSD and Apache-2.0 are; GPL-2.0-only and
  anything proprietary are not). A manufacturer SDK or binary library cannot
  be bundled. If in doubt, ask in the issue before you write the code.
- **Vendoring.** A driver of your own goes under `vendor/<name>/` with its
  `LICENSE`, a README and a provenance note like
  `vendor/fd9-independent/docs/PROVENANCE.md` (or, for code inside
  `workflow/`, `workflow/cr30/PROVENANCE.md`): how the protocol was learned
  (documentation, traffic observation, other analysis), what was deliberately
  left out, and that no vendor files, tables or captured data are included.
  The vendored folder holds source and docs only; the FD-9's test allows only
  `.py`, `.md`, `.toml` and the `LICENSE`
  (`tests/test_fd9_packaging.py::test_bundled_source_is_self_contained_and_licensed`).
  Its own unit tests run from ChromIQ's suite
  (`tests/test_fd9_packaging.py::test_vendored_library_suite_runs_without_private_research_tools`).
- **Packaging.** Add the driver's path, data files and **every module as a
  hidden import** to all three spec files (`ChromIQ.spec`, `ChromIQWin.spec`,
  `ChromIQLinux.spec`): lazy imports are invisible to PyInstaller. Third-party
  packages go in `requirements.txt`. Enforced by
  `tests/test_fd9_packaging.py::test_all_platform_specs_include_the_driver_and_its_license`
  and `tests/test_cr30_packaging.py`. Ship the licence beside the app, add a
  section to `THIRD-PARTY-NOTICES.md`, name it in
  `ui/licences.py::NOTICE_SECTIONS`, and add the bundled licence to the
  licence window's Reveal list: add its paths to the
  `ui/licences.py::BUNDLED_LICENCE_FILES` tuple, as the FD-9 driver's
  `ui/licences.py::FD9_DRIVER_LICENCE` paths are. `tests/test_fd9_review_r3.py`
  fails on a licence file a platform spec ships that the tuple leaves out.
  Name both the bundled and the source-tree location in
  `THIRD-PARTY-NOTICES.md`.
- **Ship only what the app runs.** The bundle holds the driver code the GUI
  uses and nothing else: no research code, no developer command-line tools,
  and no option that loads Python from a folder.
- **Read-only towards the device, and as few commands as possible.**
  - Send only the commands a measurement needs. List every command the driver
    can send in the pull request or the provenance note, with what it does
    (read, measurement, motion, display) and where it is built.
  - No writes to device memory, settings, calibration or firmware. No firmware
    updates.
  - A write that is not a measurement but is part of operating the device is
    allowed only when the session needs it, and is listed and documented with
    what it changes and whether it persists after a disconnect or a power
    cycle. The FD-9's example is the display image it shows on the
    instrument's own screen (command 0x0005, see
    `vendor/fd9-independent/docs/PROTOCOL.md`).
  - Keep the generic send primitive private, and call it only from fixed
    serialisers, one per command (the FD-9's is
    `vendor/fd9-independent/src/fd9_independent/client.py::Instrument._exchange`).
  - No address, length, flag or command number taken from user input or from
    a file.
  - Refuse an unknown firmware or sensor version **before** anything moves, and
    put the version found into the refusal so users can report it.
  - Do not add a command "just to look", for example to read a version or reset
    a screen. If something seems to need a new command, ask the maintainers on
    GitHub first.
- **Robust towards the device's replies.**
  - Every wait has a timeout: connecting, each exchange, sheet insertion, a
    scan.
  - Check every reply's length and echo before you use it, and cap message
    and buffer sizes. Never size an allocation from a length the device sent.
  - No discovery broadcasts and nothing that phones home; validate an address
    the user types before you connect to it.
- **No device data in the repository or the pull request.** Never commit or
  attach readings, calibration or model bytes, scans, session folders or
  network transcripts from a real unit. The session folders ChromIQ writes on
  your disk (`core/file_manager.py::Run.fd9_sessions_dir` for the FD-9) hold your
  unit's calibration and model bytes: never copy one into the repository as a
  test fixture. Tests use invented values and
  synthetic scans and never open a network connection or a real port.
  Evidence for reviewers is photos of the device, ChromIQ screenshots, the
  steps you took and short log lines.

## 10. Text the user reads

- **Friendly, extensive, easy to understand and correct.** Explain what is
  happening, what to do and why, in plain words: instruction first, then the
  reason. Avoid jargon and internal terms ("factory characterization",
  "clients", raw exception text). Every new control that is not obvious gets
  an ⓘ.
- **Every user-facing literal is wrapped in `tr()`**, log lines included
  (`tests/test_i18n.py::test_no_user_facing_literal_skips_tr`). Runtime values
  use `tr("... {name} ...").format(name=...)`. Messages with a count get real
  singular and plural variants, never "(s)".
- **All 13 translations.** Every new or changed string goes into every
  `data/i18n/<code>.json`, and parameter texts into every
  `data/i18n/parameters.<code>.yaml`. Use the register the catalogue already
  uses (informal: German "du", French "tu"). `python scripts/i18n_extract.py
  --missing <code>` lists what is missing. Have a second pass check the
  translations (a native speaker, or a separate review), and say in the pull
  request which languages you are unsure of.
- **No em dash (U+2014) in new or changed English text.** Use a comma, a
  colon, a full stop or brackets. In translations follow the language: German
  and Norwegian use the en dash; Japanese, Russian, Ukrainian and Simplified
  Chinese use the em dash natively and are exempt; any other translation may
  not add an em dash its English does not have. Never add a
  string to `tests/data/em_dash_baseline.json`;
  `python scripts/em_dash_check.py --report` shows where things stand.
  Enforced by `tests/test_no_new_em_dash_in_user_facing_text.py`.
- **Short labels stay short**: a translation of a short English label (up to
  24 characters) may grow only by about 60 %, or it is clipped on a button
  (`tests/test_i18n.py::test_short_labels_stay_compact`).

## 11. Design specifications and the message catalogue

- **The specifications in `docs/design/` are binding.** Read the ones your
  change touches before you change code:
  `docs/design/unified_measurement_management.md`,
  `docs/design/measurement_exit_strategy.md`,
  `docs/design/per_target_settings.md`, `docs/design/tool_availability.md`,
  `docs/design/chart_load_and_generate_paths.md` and the others listed in
  `CLAUDE.md`. The FD-9 sections in them are good examples of an instrument's
  entry.
- **A conflict with a specification is reported, not fixed in passing.** If
  your instrument needs behaviour a specification rules out, describe it on
  GitHub and wait for the maintainers' answer before you build it.
- **New behaviour is written as awaiting confirmation.** Add it in a block
  headed "⏳ Awaiting confirmation" with the line
  `**Confirmed by:** *nobody yet.*`. Only a maintainer's confirmation moves it
  to a confirmed section (`tests/test_design_specs_are_binding.py`).
- **Every measurement window has a message ID.** Add it to §M-PROPOSED of
  `docs/design/unified_measurement_management.md` and to
  `workflow/measurement_messages.py` with word-for-word the same title and
  body and `approved=False`. Proposed texts are shown in the app right away;
  the maintainers approve them afterwards. Add the ID to
  `tests/test_message_catalogue.py::AWAITING_APPROVAL` and the method that
  shows the window to `tests/test_message_catalogue.py::WINDOW_SOURCES`.
  Name IDs after the instrument (M-FD9-*, M-CR30-*). Changing the wording of
  an existing message is a proposal too.

## 12. Tests and the release gate

- **Every behaviour change gets a test that fails before it and passes after
  it.** Run the new test against the code without your change once, and say so
  in the pull request.
- **Use fakes.** A scripted socket, a fake serial port or an injected reading
  function; invented values; synthetic scans. No test opens a network
  connection or a real device, and no test runs only when private captures or
  an IP address are present: a test that skips everywhere but your desk
  proves nothing to anyone else.
- **Do not rewrite an existing test to make your change pass.** If a guard
  really has to change, say which one and why in the pull request, so the
  reviewers can decide.
- **House rules for tests** (see `CLAUDE.md`): anything that runs ArgyllCMS or
  a subprocess has a `timeout=` sized for a fully loaded machine; no test calls
  a modal `.exec()` or `qapp.setStyleSheet()`; use pytest-qt's `qapp` fixture
  (`tests/conftest.py` pins one `QApplication` per worker) and never create
  or destroy a `QApplication` of your own.
- **Set up first.** The "Setup" section of `CLAUDE.md` creates the `.venv`
  and installs `requirements.txt` and `requirements-dev.txt`. Install
  ArgyllCMS 3.5.0 as well: the slow tier of the gate runs the real tools.
- **Run, inside the project's `.venv`:**

  ```bash
  QT_QPA_PLATFORM=offscreen pytest tests/test_i18n.py tests/test_no_new_em_dash_in_user_facing_text.py tests/test_message_catalogue.py tests/test_design_specs_are_binding.py -q
  QT_QPA_PLATFORM=offscreen pytest -n auto -q                      # everyday tier
  QT_QPA_PLATFORM=offscreen pytest --runslow -n auto -q > /tmp/chromiq-gate.txt 2>&1
  echo "exit=$?"                                                   # the gate
  ```

  On Windows PowerShell the gate is
  `$env:QT_QPA_PLATFORM='offscreen'; pytest --runslow -n auto -q > $env:TEMP\chromiq-gate.txt 2>&1; echo "exit=$LASTEXITCODE"`.

  **Read the exit code from pytest itself, not through a pipe**:
  `pytest | tail` reports `tail`'s exit code, which is 0 however red the run
  was. The count line is the second check: `N passed` with no `failed` in it.
  Write the gate log outside the repository, and **do not edit any file while
  the gate runs**: many tests read source with `inspect.getsource`.
- **A failure you did not cause**: run the same test on unchanged master
  before you change anything for it, and report both results. The FD-9 pull
  request saw five such failures that passed for the maintainers; they turned
  out to be environmental.

## 13. Checking in the real app, on screen

Unit tests do not show what a person sees. Before you open the pull request,
drive the real app in a **real window** (not `QT_QPA_PLATFORM=offscreen` and
not `widget.grab()`), with the Beta option **on and off** (it takes effect
after a restart).

- **Sandbox first.** Set `CHROMIQ_SETTINGS_FILE` to a scratch `.ini` and
  `CHROMIQ_PRESETS_DIR` to a scratch folder, and point the output folder
  (`custom_output_path`) at a scratch folder too, so no test project lands
  among your real ones. Afterwards check your real settings by value, not by
  comparing with a backup.
- A script that drives the app builds its `QApplication` the way the app does
  (`scripts/capture_screens.py::build_app`, or at least
  `core/numeric_locale.py::pin_c_numeric_locale` right after it) and starts a
  `scripts/onscreen_capture.py::PopupWatchdog` so an unexpected question never
  hangs it. On macOS, `scripts/onscreen_capture.py::capture_window`
  photographs a window even when it is behind others; elsewhere, use the
  system's screenshot tool on the real window.
- **Never print to a real printer from a script**, and never steal the
  keyboard focus while a person is typing
  (`scripts/onscreen_capture.py::FocusGiveBack`).
- Put screenshots in the pull request, with no personal paths or names in
  them, and delete the scratch projects afterwards.

`CLAUDE.md` describes the maintainer's own machine in places (his Desktop
report folders, his display, the people who review, his session hooks). Follow
the intent of those parts, not the paths: sandboxed settings, a real window,
no files left behind, and no keyboard stealing. Where it says Knut or Basti
must approve something, read "the ChromIQ maintainers".

## 14. Opening the pull request

- **One topic per pull request.** The instrument itself is one. A fix you
  found on the way that affects other instruments is another, with its own
  description; the FD-9 pull request carried an unrelated Print tab change
  that had to be split out. Large work can come in steps (for example: the
  Beta switch and chart creation, then measuring).
- **Base it on the current `master`** and keep your commits; do not squash
  someone else's authorship away.
- **The description says:**
  - what the instrument is, how it connects, and which route it uses (CR30-style
    bridge or FD-9-style own path);
  - what changed in shared files, and that the Beta option off changes nothing
    (name the tests that prove it);
  - **what was tested on the device and what was not**: operating systems,
    firmware or sensor versions, connection types, Stop and Resume, a full
    chart, a failure case (cable pulled, device off);
  - the new message IDs and any specification blocks awaiting confirmation;
  - the translations you are unsure of;
  - the commands the driver sends, and the licence and provenance of the
    driver;
  - the test counts and the gate's count line and exit code;
  - screenshots from the real app, option on and option off.
- **Review your own diff in a separate pass** against
  [the checklist](#5-the-registration-checklist) and
  [the common mistakes](#15-common-mistakes-we-have-seen) before you open the
  pull request, and put the result in the description as a table: one line
  per row of section 5 and section 15, each marked done, not applicable (with
  the reason) or open.

## 15. Common mistakes we have seen

These come from the review rounds of the FD-9 pull request. They are not
anyone's fault: most of them are invisible until somebody knows to look, which
is why they are written down here. Each one has a test now, and each is easy to
avoid from the start.

| Mistake | What happened | Do this instead |
|---|---|---|
| Ungated changes | The instrument appeared in every list for every user, and per-target settings changed for people without the device. | Put everything behind the Beta switch, and pin it with the four nets of [section 4](#4-behind-a-beta-option-and-off-means-no-change). |
| A chart check that crashes | Detecting "is this my chart?" read every `.ti2` as strict UTF-8, so a cp1252 chart from a German Windows broke the Measure tab for every instrument. | `core/text_io.py::read_text`, never raise, cache, and only when the option is on. |
| Lifting the parameter lock | Refreshing the instrument panel set shared option groups enabled on every chart load, which could unlock options in the middle of another instrument's read. | Change enabling only when your state changes, as a second lock. |
| Skipping the Start preflight | The instrument's own Start skipped the replace warnings of §5, the misfit check, autosave recovery and verification staging. | Run every step of the shared preflight, in the same order, before any device work ([section 7](#7-measuring)). |
| Rewriting `meta.json` | New Measure keys in the shared settings dict made every target's `meta.json` change; later, a Create Chart save rewrote an instrument project's keys while the option was off. | Instrument-only keys, written only for your charts, carried through unchanged when off. |
| Settings outside `AppSettings` | A separate `QSettings` domain escaped the sandbox, and a hidden key could load Python from any folder. | `AppSettings` only; no code paths in settings. |
| English-only log messages | The instructions that guide the physical work and every error were English log lines nobody was shown in a window. | `tr()` everywhere, and windows from the catalogue for what the user must act on. |
| Missing §M entries | New windows had no message IDs, and a proposed text in the specification contradicted the code. | ID in §M-PROPOSED and in `workflow/measurement_messages.py`, word for word. |
| Errors classified by words | Any `OSError` (even a missing file) was shown as a connection problem; a Windows connection message matched nothing. | Classify by exception type first. |
| Vendor-prefixed labels | "FD-9 (Konica Minolta)" in the lists. | Short model name in lists, full name in the files. |
| Missing `.ti2` header lines | No `DESCRIPTOR`, `CREATED`, `APPROX_WHITE_POINT`, unquoted `SAMPLE_LOC`, no run description. | `workflow/layout_engine/ti2_writer.py::build_ti2_text`. |
| Ungrounded session folders | Every Start created a session folder outside `Run`, kept forever. | A `Run` property, a retention rule, `docs/dev_folder_layout.md`. |
| Stale settings with the option off | A saved instrument choice and layout recipe from before the option was turned off changed Guided's paper list and loaded instrument code. | Read them as "none" while off; test from stale settings. |
| A result that wandered | A paused result could take over the Stop and end window of a different chart loaded afterwards. | A pending result belongs to its own chart. |
| Greying that did not stick | Loading a recipe re-enabled controls the instrument does not use. | Re-apply your greying after every recipe load and panel rule. |
| Packaging and licence gaps | The licence window and the bundle did not agree on where the vendored licence lives. | Spec files, `THIRD-PARTY-NOTICES.md`, `ui/licences.py`, and a test. |
| An unrelated change inside | A Print tab behaviour change for every printer rode along. | One topic per pull request. |
| Parent-owned worker thread | A `QThread` parented to the tab risks a fatal abort if the tab goes while it runs. | Unparented and held in a module list until finished. |
| Research code in the bundle | Developer tools, research modules and an option to load Python from a folder were on their way into the shipped app. | Ship only what the GUI runs ([section 9](#9-the-driver-and-the-device)). |
| Resume tied to an address | A new network address from the router made a partial run impossible to resume. | Bind resume to the device's identity. |
| A test rewritten to pass | An existing guard test was changed to fit the new code without saying so. | Leave existing tests alone, or name the change and the reason in the pull request. |
| Tests only the author can run | A test needed private captures or a reachable instrument, so it skipped for everybody else. | Invented data only; every test runs anywhere. |
| Stacked specification blocks | A second "Awaiting confirmation" block was added beside an older one that said something else. | One current block per topic; replace your earlier one. |

And a positive one to copy: the FD-9 driver kept a strict read-only stance
towards the device, refused unknown sensor versions before anything moved, and
documented where its protocol knowledge came from. Thanks to **lessbones** for
that care and for the whole contribution.

## 16. Where to read more

- `CLAUDE.md`: the project's general rules (tests, Qt crash rules,
  translations, specifications, on-screen checks).
- `docs/dev_folder_layout.md`: projects, runs and their files.
- `docs/dev_builtin_presets.md`: built-in Create Chart presets.
- `workflow/fd9/README.md` and `vendor/fd9-independent/docs/PROTOCOL.md`: the
  FD-9 integration and its protocol notes.
- `docs/cr30_platform_support.md`: the CR30 on each platform.
- `CONTRIBUTING.md`: contributing in general.
