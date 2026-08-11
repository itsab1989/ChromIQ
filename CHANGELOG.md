# Changelog

## v4.0.0-beta.3

> All three per-target settings defects are **fixed in this beta**: the two
> announced in beta.2, and a third the follow-up testing found the same day.
> The automated switching drive now passes every one of its 74 checks, and
> the `ChromIQ-Switching-Demo.zip` download on this release carries the
> test cases that prove the fixes, ready for a manual pass.

### Fixed

- The six chart settings a Calibration run manages for itself (patch
  count, ink limit, single-channel steps, grey axis, row spacing) no
  longer follow you out: visiting a Calibration run and then another run
  used to write the calibration's values for those six rows into that
  run. Each run now keeps — and reopens on — its own values, and the
  calibration still gets exactly the chart it needs while it is selected.

- 🗂️ **Every run type now keeps its own settings — verification included.**
  Switching Run type between Profiling and Verification on the same run
  used to share one set of chart / measure / print settings, each
  overwriting the other. A verification now stores its settings in its own
  place, they are backed up together with the chart when a measurement
  starts, and Restore Used Chart brings them back (whatever it replaces is
  archived, never deleted).
- **The tab you are looking at follows the run switch.** Changing Profile
  run or Run type while standing on the Measure or Build Profile tab used
  to leave the previous run's values on screen — and then save them onto
  the run you had just switched to. Every tab now reloads the moment the
  selection changes, exactly the way Create Chart always did — including
  switches the app makes for you, such as after duplicating a run.
- 📏 **The log panel can be made bigger again.** Dragging its top edge
  could only ever shrink it — the ceiling was measuring the panel's own
  wrapper instead of the space the tab really has. It now grows to
  whatever the window allows, on every tab, and hiding and re-showing it
  in Preferences keeps it resizable.
- With calibration options on, the Create Chart tab no longer locks
  every run onto a module you cannot leave: a Profiling or Calibration
  run opens on MANUAL, and a Verification run offers MANUAL and FROM
  PROFILE GAMUT — with FROM PROFILE GAMUT as the default.
- The Create Calibration File module had a second load-measurement icon
  inside its Measurement Data section; the one in the tab's header now
  serves that module too (its tooltip says so), and the duplicate is gone.

### Changed

- The "Getting started" card's interface tour speaks today's language:
  the Options-panel row explains the module buttons (GUIDED, MANUAL and
  when FROM PROFILE GAMUT appears), and the five-tabs row says when tab 4
  is called "Calibration & Profiling".

### Internal

- The switching demo package (`ChromIQ-Switching-Demo.zip`) now documents
  four targets including a verification, and its RT1/RT2/VT1 cases are
  machine-verified through a full app restart at package build time.
- The per-target settings specification records the 2026-08-11 rulings
  (§10) with the implementation in an awaiting-confirmation section.

## v4.0.0-beta.2

> Fixes from the first round of 4.0 beta feedback — thank you! Two known
> defects in per-target settings (found by our own testing on 2026-08-11)
> are **under review and not yet fixed** in this beta: switching Run type
> between Profiling and Verification on the same run shares one set of
> settings, and the Measure / Build Profile tabs do not refresh their
> settings while they are the visible tab during a run switch. The new
> `ChromIQ-Switching-Demo.zip` download demonstrates both.

### New

- 📖 **The "Getting started" help card has been rebuilt**: it now opens with
  a short index, walks from first start to a finished profile in chapters,
  gains its own chapter on checking a finished profile (the three ways, and
  which to pick), ends with a plain-language overview of where your files
  are stored, and links to the other help cards along the way — in all
  twelve languages.
- The strip reading times under the chart preview now explain themselves:
  the frame's tooltip says what a time with an **✕** after it means (that
  strip was swiped faster than your instrument can reliably measure — read
  it again, more slowly).

### Changed

- The "Check a finished profile (verification run)" help card's subtitle no
  longer describes only printing through the profile — it now covers what
  every verification gives you, whichever of the three ways you print the
  chart.
- The Create Chart tab's help icon now introduces the **FROM PROFILE
  GAMUT** module: when it appears, what it is for, and where its own help
  lives.

### Fixed

- 📏 **The strip reading times sit exactly under their strips again.** They
  used to drift further right of their strips the further along the sheet
  they sat, because their positions were captured once and went stale when
  the preview re-fitted. They are now placed live at every paint, follow
  every window resize immediately, and on a small window they split into
  two staggered rows so every time stays readable — a time flagged ✕ is
  never dropped, however tight the space.
- The measurement report's trend charts label the dotted Avg / Max
  threshold lines again. On a large value range the two lines sit almost on
  top of each other and the words used to be dropped; now they move inside
  the chart, one above its line and one below, so they can never overlap.

### Internal

- The on-screen switching drive the per-target settings test plan called
  for (`scripts/drive_per_target_settings.py`) now exists — it found both
  defects above — and `scripts/make_switching_demo.py` builds the
  downloadable **Demo-Switching** package with the documented values and
  the manual test cases (`ChromIQ-Switching-Demo.zip` on this release).
- `scripts/capture_showcase_40.py` captures the ten 4.0 showcase
  screenshots from the real app in one run.

## v4.0.0-beta.1

> **This entry covers everything that changed since v3.14.7, the last stable release** — 219 betas' worth of work, grouped so you can find what affects you instead of reading a diary. Later 4.0.0 betas add their own entries above this one; the individual beta histories remain in the repository.

**If you only read one paragraph:** ChromIQ 4.0 looks after your work — every
run keeps its own chart, measurement and settings, nothing you made is ever
deleted, and checking how good a finished profile really is has become a
guided, honest, repeatable workflow. Your existing projects are picked up
exactly as they are: ChromIQ migrates them in place the first time it opens
them, keeps every old file, and there is nothing you need to do first.

Two headlines in more detail. **ChromIQ now keeps track of your work for
you**: a profile run
holds its own chart, its own measurement, its own settings and its own
description; nothing you made is ever deleted, only archived; and every window
that could cost you something says exactly what it is about to do. And
**checking a finished profile is now a first-class workflow**: three clearly
explained ways to verify, honest statistics for each of them, and a
measurement report that keeps the whole dated history of a profile's health.

*(New words along the way — "gamut", "drift check", "judged as measured" —
each have a plain-language Dictionary entry: open the Welcome window's
"Dictionary and terminology" card. The card "Check a finished profile
(verification run)" walks the whole workflow step by step.)*

### New

**🎯 Verification, from start to finish:**

- **Three ways to check a profile, clearly told apart.** A chart built from
  the profile's own gamut (the everyday accuracy check), a chart printed
  through the profile (the strict whole-path check), and a sheet printed from
  your own application with the profile applied (the everyday-chain check).
  The Dictionary entry *"Which verification should I use? (the three ways)"*
  compares them, and the report records which way every sheet was made so
  they are never mixed silently.

- **A verification chart built from your profile's own gamut.** The **FROM
  PROFILE GAMUT** module on Create Chart asks the profile which colours it
  can actually print — from a fixed, published reference set — and builds the
  chart out of exactly those, so no patch is wasted on a colour that was
  never possible on this paper. Repeated checks of one profile always get the
  same colours, so this month's figures compare patch by patch with last
  month's. The chart already carries the profile, the Print Chart tab selects
  Raw for it by itself, and for a verification run with a built profile this
  module is the one Create Chart opens on.

- **A verification chart can be printed THROUGH its profile.** The Print
  Chart tab's **Colour** row chooses "Through the profile" (ChromIQ converts
  every patch itself — the printer's own colour management stays off, so
  nothing is ever converted twice) or "Raw — no profile". The choice, the
  profile file and the rendering intent are written into a print record
  beside the chart, and the report states them for every sheet.

- **Sheets ChromIQ did not print are asked about, once.** Measuring or
  importing a verification sheet that has no print record raises *"How was
  this sheet printed?"* — Raw / With colour management / Not sure (always
  safe, stores nothing). The answer is kept with that one measurement.

- **Import a measurement made in another program.** With **Run type** set to
  **Verification**, the Measure tab shows an **IMPORT** module (it exists
  only for verification runs): it files an i1Profiler (or any .ti3)
  measurement as a dated verification — converted, checked patch-for-patch
  against this run's chart, and stored exactly where a native measurement
  would go. Your original file is never touched.

- **The report judges every sheet by the fair yardstick.** A print that
  mapped white to the paper — through the profile with relative intent, or
  another application's colour management — is judged **relative to its own
  paper white**; everything else is judged **as measured — no white
  adjustment** (a way of comparing, not a rendering intent). The report says
  which was used, per sheet, and physical readings like paper white and
  deepest black always stay as measured.

- **Colour accuracy is split into within / beyond the profile's gamut.**
  Some design colours are simply not printable on a given paper; their
  distance describes the gamut, not a mistake of the profile. The report
  shows both groups — side-by-side columns in the detail chapters, row
  blocks in the Overview so dated columns stay comparable — and Pass/Fail
  judges the within-gamut figures. Every patch stays counted and visible.

- **Raw sheets get a drift figure instead of an unfair verdict.** A sheet
  printed raw is not expected to match the design, so it is never graded
  Pass/Fail against the profile thresholds. Instead the report compares it
  with your **previous raw check of the same chart** — print against print,
  patch by patch. The first raw check becomes the baseline; checks made with
  different charts are refused rather than mispaired.

- 📈 **The Measurement Report grew into the profile's health record.** It
  gathers every dated check of a run automatically, trends colour accuracy,
  paper white, darkest black and the cube corners over time, lets you
  untick individual runs, warns about mixed instruments and mixed printing
  methods, carries adjustable Pass thresholds, and remembers every option
  you set. **Save report as PDF** produces a print-sharp document (vector
  text, ~300 dpi charts) whose proposed folder always matches what the
  report covers — one dated check, one run's checks, or the whole profile.

**🧰 And the rest:**

- 🧭 **The run bar — one place that says what you are working on.** Above the
  tabs, on every tab: **Profile run**, **Run type** (Profiling,
  Verification — and Calibration, once its options are enabled in
  Preferences) and — for verifications — which dated check,
  each with its own ⓘ explanation. Beside them sit the run actions:
  duplicate a run, restore the chart a measurement was made with, and
  delete — with a window first that says exactly what would happen. The
  whole app follows the bar: Create Chart, Print, Measure and Build Profile
  always show the run it points at, and when no project is loaded the bar
  says so instead of guessing.

- 📦 **Ready-made Red River Paper charts.** Four built-in starting points in
  Create Chart carry Red River's own 2052-patch Standard Patch Set v25 —
  byte-identical to their published file — laid out and verified for i1Pro
  (A4 and Letter, with the clip-border record) and ColorMunki. The patch
  set is fixed so results stay comparable; every layout control (paper,
  margins, branding) stays yours to change.

- **Every setting belongs to the run you set it on.** Create Chart, Measure
  and Build Profile each remember their own settings per run; switching run,
  opening a project or changing run type loads them, leaving a tab saves
  them — without a dialog.

- **Runs have descriptions.** "Matte paper, second attempt" appears in the
  run bar, the measurement report and on the printed chart
  (`{rundescription}`); verifications and the calibration have one too. The
  profile description writes itself from project, run and date — editable,
  or off. And the installed copy of a profile can be **named after its
  description** (a checkbox on Build Profile), so the profile picker in your
  editor reads like your own words.

- **Calibration is a run type.** Once **"Enable calibration options"** is
  ticked in Preferences, **Calibration** appears in the Run type list —
  choose it and the whole app follows: chart, measurement, `.cal` file and
  its description live in the project's `cal/` folder, shared by every run,
  and each profile run records which calibration it was built with.

- 🔔 **Sounds during measurement** — a strip accepted, a patch misread, a
  session finished — so you can keep your eyes on the chart. **Preferences →
  Sounds.**

- **A gentle warning when you swipe a strip too fast.** Every instrument
  takes a fixed number of readings per second, so a strip has a minimum
  time it needs — swipe faster and patches get too few readings, even when
  ArgyllCMS still accepts the strip. ChromIQ knows the pace for your
  instrument, shows a live verdict while you measure, and mentions it when
  a strip was read quicker than the minimum, so you can re-read it before
  it costs you accuracy. Tune or switch it off under **Preferences →
  Measurement** ("Warn me when I read a strip too fast").

- 🌍 **Twelve languages, complete** — German, Spanish, French, Italian, Dutch,
  Portuguese, Swedish, Norwegian, Polish, Russian, Japanese and Chinese —
  every button, message, tooltip and help text.

- **Demo projects for learning and testing**, both attached to this
  release as downloads:
  [ChromIQ-demo-projects.zip](https://github.com/itsab1989/ChromIQ/releases/download/v4.0.0-beta.1/ChromIQ-demo-projects.zip)
  demonstrates the file-handling rules step by step (including projects in
  the old 3.13 layout, to watch the migration happen), and
  [Demo-Report-Matrix.zip](https://github.com/itsab1989/ChromIQ/releases/download/v4.0.0-beta.1/Demo-Report-Matrix.zip)
  holds thirteen documented Measurement Report cases with one ready-made
  PDF per case.

- **Preferences → "Hide the log panel on every tab"**, for when the chart
  preview deserves the room. The full log is still written to disk.

### Changed

- **The measurement model is consistent everywhere.** Replacing a chart,
  rebuilding one, measuring over an existing measurement, deleting a run —
  each has one window, one wording and one outcome, whichever tab you reach
  it from. The rules live in `docs/design/` and the app is tested against
  them.

- **Nothing is deleted, only archived.** Replaced measurements, regenerated
  charts, redone calibrations and replaced verification charts all move to a
  dated `old/` folder — and the windows say so before you commit.

- **Every measurement keeps a copy of the chart it was measured with**, saved
  the moment measuring starts — profile runs, dated verifications and the
  calibration alike — and **Restore Used Chart** puts it back. A dated
  verification is always judged against the chart *it* was measured with,
  even if the shared chart was replaced later.

- **File dialogs are ChromIQ's own everywhere** — with the sidebar shortcuts
  to your working folder — instead of the bare system dialogs.

- 🗂️ **Existing projects are migrated in place.** A project from 3.13 or an
  earlier 3.14 is reorganised into the new folder shape the first time it is
  opened — every old file kept, the plain-language folder guide ("Where are
  my files?" in the Welcome window) always current.

- **The interface holds still.** Buttons sit in the same place on every tab,
  the log panel ends on the same line shown or hidden, the run bar no longer
  shifts during start-up, and windows placed off-screen by the system are
  nudged back so their bottom row of buttons is always reachable.

- **The icons were drawn for the job.** Load Project and Load chart have
  their own recognisable icons, the Duplicate and Calibration actions got
  purpose-made marks, and the run bar's action marks were aligned optically
  — reviewed on screen, in light and dark mode, before being adopted.

- **The windows that ask what to do with a chart read like every other
  window** — explanation in plain text, buttons in a row, Cancel set apart,
  long project names shortened in the middle with the full name given in the
  text.

- **ChromIQ starts a little quicker** — the printer list is fetched when you
  first open Print Chart rather than while the window is being built.

### Fixed

Two hundred and nineteen betas fixed far more than fits a list — the
per-beta histories in the repository carry the complete record. What users
met most sat in measuring and in chart handling, so those come first:

**While measuring:**

- **Pressing Esc during a measurement no longer throws your readings away.**
- **Patches no longer come back as "inconsistent" for no visible reason** —
  the tolerance sent to the instrument was stricter than the manufacturer's
  own default.
- **Several measurement windows never appeared at all** when the ChromIQ
  reading engine was in use — the abort confirmation, failure windows, and
  two that opened in silence. All reachable now, verified against a real
  instrument, and the sound tables for every window are written down as
  specification.
- **A resume no longer archives the measurement it resumes from**, a
  finished re-measurement of a whole chart announces its completion, and a
  good measurement is no longer called foreign while guided refinement
  loses its ticks.
- **The "this chart already has a measurement" window opens showing what
  the panel actually says** — its old answers could quietly switch an armed
  refinement off and turn the next read into a replacement.
- **"No instrument found" fired once per app run** instead of every
  attempt, and the abort window wording was reworked.
- **Text typed for a "New run" is kept**, and lands on the run you make.

**Charts and previews:**

- **"This chart was made for a different instrument" could name the wrong
  instrument** — it compared your connected device against a setting rather
  than against the chart itself.
- **Restoring a calibration chart put back a completely different chart**,
  and a calibration restore redrew the selected run's chart.
- **The chart patch-set editor and the 3D patch view opened the run's
  chart, not the chart you had selected.**
- **The windows that ask what to do with a loaded chart were rebuilt** —
  explanation in plain text, buttons on one row, Cancel set apart, long
  project names shortened without clipping ("JSE AS BASE FOR A NEW
  PROFILE" is gone: windows widen to fit their buttons, everywhere).
- **The auto-update preview judged the wrong chart** after switching
  modules, and a switched-off option now looks switched off in both
  themes.
- **printtarg margins were applied in the wrong order** (top/right/bottom/
  left confusion) — charts now sit where the instrument minimums say.

**Reports, projects and the app around them:**

- **Checking for updates works again for stable versions.** The check used
  to fail with "No release tag found" whenever the newest releases were all
  betas; it now asks for the latest finished release directly.
- **The measurement report's PDF paginates cleanly** — headings stay with
  their tables, the trend legend never overlaps the graph, and charts print
  sharp instead of pixelated. The proposed save folder follows the
  four-location design again.
- **A damaged `meta.json` no longer stops a run remembering anything**, and
  runs write their metadata atomically.
- **Help texts tell the truth.** The verification help card described a
  colour-management print path the app deliberately prevents; the gamut
  check was described as a drift check; "as measured (absolute)" read like
  a rendering intent. All corrected — and every such correction is now
  guarded by a test.

### Internal

- The test suite no longer writes to your own ChromIQ preferences.
- `docs/design/` holds the agreed, binding specifications: the measurement
  model, the message catalogue, per-target settings, the measurement windows
  and their sounds, calibration as a run type, and verification printing;
  the suite fails when code and specification disagree.
- Two purpose-built demo generators (`scripts/make_demo_projects.py`,
  `scripts/make_report_demo.py`) build test projects entirely from the real
  Argyll pipeline, and on-screen drivers verify the app against them —
  54 automated expectations for the Measurement Report alone.

## v3.14.8-beta.222

### New

- **Raw drift sheets get a real drift figure instead of an unfair verdict.**
  A sheet printed raw is not expected to match the design, so Pass/Fail
  against the profile thresholds would fail a healthy printer forever. Raw
  sheets now show "drift" in Report Results, and the detailed chapter
  compares each raw check with the PREVIOUS raw check of the same chart —
  print against print, patch by patch (the model of Argyll's own colverify).
  The first raw check becomes the baseline; a pair made with different
  charts is refused rather than mispaired. Through-profile and gamut checks
  keep their Pass/Fail.
- **Several checks on one day are tellable apart**: table columns and trend
  labels carry the time whenever two share a calendar date.

### Fixed

- **The gamut-chart run's report section no longer calls it a drift check.**
  That chart carries the profile from the moment it is built, so it IS the
  accuracy check — the report now says so, its run row reads "gamut check —
  profile applied at build", and the mixed-methods warning treats it as its
  own method. A gamut chart whose stored targets are missing says exactly
  that.
- The Dictionary's "Which verification should I use?" entry no longer claims
  a through-profile chart is always judged as measured — with the everyday
  relative intent it is judged against the sheet's own paper white, and the
  entry now says so.
- The note under the split accuracy table reads correctly for any patch
  count.

## v3.14.8-beta.221

### New

- **The report splits colour accuracy into within / beyond the profile's
  gamut** (Knut). Where the reference is the chart's design, the report asks
  the run's profile which colours it can actually print: the Overview gains
  three row blocks (within / beyond / all patches — dated columns stay side
  by side), the detail chapters show the three groups as columns, and
  Pass/Fail judges the within-gamut figures — a colour the profile could
  never print is not counted against it. Every patch stays visible; runs
  without Argyll or a profile show the report exactly as before. Saved
  history reports gain the split automatically.
- **Verification runs open Create Chart on FROM PROFILE GAMUT** when the run
  has a built profile; a module you pick by hand wins for the session.
- **The Measurement Report remembers its options** — both checkboxes and the
  Pass thresholds come back as last set.
- **Demo-Report-Matrix** — the report test package (Knut): 
  `scripts/make_report_demo.py` builds a two-run project with thirteen
  documented cases from the real Argyll pipeline;
  `scripts/drive_report_demo_onscreen.py` checks 43 expectations against the
  real window and exports one PDF per case.

### Fixed

- **"Save report as PDF" proposes the folder from the four-tier design
  again** ("Where are my files?" card): one dated check → its own reports/;
  several checks of one run → verifications/reports/; a profiling run → the
  run's reports/; several runs → the project's reports/ — derived from the
  runs actually selected.
- **Opening the report on a dated measurement (single-run view) now shows
  that date**, not silently the history's newest.
- **A CHROMIQ_MEASURED keyword with a full timestamp is honoured** instead
  of being discarded for the file's modification time.

## v3.14.8-beta.220

### Fixed

- **The PDF report's "Worst patches" heading no longer strands at the bottom
  of a page** with its table on the next — a table pushed to the next page
  now takes its heading along. Verified across six generated report
  configurations (1/2/4/10 dates, summary-only, profiling) with a
  page-by-page scan: no orphaned headings, no margin overflow, no
  overlapping text, a footer on every page.
- **The trend chart's legend can no longer be painted across the graph** —
  when its labels wrap to a second row (as the five Colour-accuracy labels
  do at PDF width, or on screen in a narrow window), the plot now starts
  below the whole legend.
- **The PDF's trend charts are sharp** (~300 dpi) instead of stretched
  96-dpi screenshots next to vector text.

## v3.14.8-beta.219

### Fixed

- **Switching Welcome cards can no longer leave the previous card's rows
  painting over the new one** — removed step rows are hidden the moment
  they leave the layout, instead of only after Qt's deferred cleanup, so
  not even a one-frame bleed-through between cards is possible.

## v3.14.8-beta.218

### New

- **The measurement report says how each verification sheet was judged.**
  A sheet whose printing mapped white to the paper — printed through the
  profile with relative intent, or in another application with colour
  management — is scored **relative to its own paper white**, so the paper is
  no longer counted against the profile. Every other sheet stays absolute.
  A new "How the colours were judged" row in the report names the yardstick,
  and the physical paper-white / deepest-black readouts always stay as
  measured.
- **"How was this sheet printed?"** — measuring or importing a verification
  sheet ChromIQ did not print itself now asks once: Raw — no profile /
  With colour management / Not sure (default, stores nothing). The answer is
  stored beside that dated measurement only, marked as answered at measure
  time. (M-HOW-PRINTED, awaiting review in §M-PROPOSED.)
- Sheets answered "With colour management" are their own method in the
  report: run rows, the "How this verification was produced" block and the
  mixed-methods trend warning all say "printed in another app with colour
  management".
- **"Which verification should I use? (the three ways)"** — a new Dictionary
  entry compares the three checks (a chart from the profile's gamut, a chart
  through the profile, a sheet from your own application), with a second
  entry explaining media-relative judging; the Print Chart tab's Colour ⓘ
  and the From-profile-gamut ⓘ gained matching paragraphs.

### Fixed

- **The Welcome card "Check a finished profile (verification run)" described
  a workflow the app prevents**: its print step said "WITH colour management
  ON — assign/convert to that .icc in your print path". It now names the
  Print Chart tab's Colour row, explains the verification chart's
  archive-on-replace and per-date snapshots, and points at the
  From-profile-gamut module, the IMPORT module and the exact Tools entry
  ("Measurement report (accuracy & drift)").
- **Tool windows opening with their bottom off screen** — a window the
  window manager placed too low stayed there even at the right size. Every
  standalone tool dialog is now nudged fully back inside the screen
  (reported on the Measurement info window).
- All new and changed text translated in all 12 languages.

## v3.14.8-beta.217

### Fixed

- **"Save report as PDF…" opens ChromIQ's own save dialog** — with the
  sidebar shortcuts, including your working folder — instead of the bare
  system dialog. A file name typed without an extension now reliably comes
  out as a .pdf.
- **The IMPORT module's green folder button opens ChromIQ's own file
  dialog too** — the same sidebar shortcuts when picking the i1Profiler
  measurement to import. These were the last two file dialogs in the app
  still using the bare system one.
- **The PDF's trend charts sit on a white ground.** The exported report was
  already light throughout, but the charts were grabbed with the app's dark
  palette showing through their transparent background — light lines on a
  black slab. The window's dark-mode charts are unchanged.

## v3.14.8-beta.216

### Fixed

Measurement Report window polish, each item confirmed on screen with
Sebastian (2026-08-10):

- The five housekeeping buttons (Add/Remove Profile's Measurements, Clear
  List, Save report as PDF, Reveal folder) are now compact (30 px); Close
  keeps its full height as the window's primary action.
- Clear air above the Close button (12 px) and the same 13 px below it
  that the main window's tabs give their bottom-most buttons.
- The trend's Avg/Max threshold words appear only where they fit cleanly
  in the left margin; on a crowded scale they stay away entirely — the
  dotted lines remain, and the Pass-threshold controls above the chart
  name their values.
- The two new info buttons carry the window's green accent.

## v3.14.8-beta.215

### New

- **Leave individual runs out of the measurement report.** The list of runs
  in the Measurement Report window now shows one checkable row per dated
  verification. Untick a run to leave it out of the trend, the tables and
  the exported PDF — nothing on disk changes, and ticking it brings it
  straight back. When runs are hidden, the report says so plainly, so a
  filtered report can never be mistaken for the complete history — useful
  when the "not all printed the same way" warning fires and you want to
  compare only the runs printed the same way.
- **Name the installed copy of a profile after its description** (Knut,
  2026-08-10). A new checkbox above Profile Description in the Build
  Profile tab — "Profile file name same as description for installed
  copy" — makes the Install button name the copy it places in the system
  profile folder after the description, so it is as easy to find there as
  in an app's colour-management menu. Only that installed copy is renamed;
  the project's own file, and everything else in ChromIQ, is unaffected.
  Applies to profiling runs only, as calibration produces no installable
  profile of its own.

### Fixed

- **The Measurement Report window's bottom could land off-screen**, and on
  a shorter display the run list showed only about three rows even with
  several runs recorded. The window is now sized and centred to fit the
  actual screen (respecting the list's own space needs), and the run list
  shows at least five rows before it needs its own scrollbar.

Verified on screen against a staged copy of a real project (15/15 checks):
window fits the screen, the run list sizes correctly, unticking removes
exactly one run and the hidden-runs note appears, and the install checkbox
derives and sanitises the file name correctly end to end.

## v3.14.8-beta.214

### Fixed

- **Tools ▸ Measurement report now opens on the loaded project's reports.**
  The window seeded itself from the current target, but the Tools menu never
  handed it the project — so it still opened empty while the Measure tab's
  report button worked (Sebastian, 2026-08-10).

### Approved

- **The verification-saved window's text is now approved** (Sebastian,
  2026-08-10, after using it live) — the window that offers the measurement
  report and the measurement inspector, each explained.

## v3.14.8-beta.213

Everything in this beta came out of the first real hardware session
(2026-08-10): a gamut chart and a two-sheet Raw/Through proof printed on a
real printer and measured with a ColorMunki, guided live.

### Fixed

- **Replacing a verification chart now archives it — it was deleted.** The
  replace window promised "moved to the 'old' folder … nothing is deleted",
  but the displaced chart files (including a gamut chart's colour reference)
  were removed outright; only the measured dates' snapshots preserved them.
  They now go to `verifications/old/<date>/`, complete.
- **A dated verification's report names how ITS sheet was printed.** The
  report read the chart's shared print record — which describes only the
  *last* print — so the moment the second sheet was printed through the
  profile, the first (raw) sheet's report claimed "through-profile". The
  date's own snapshotted record now outranks the shared one.
- **The measurement report opens tall and gathers the whole history.** It
  opened at its 640 px minimum, squeezing the report text into a strip a few
  lines high, and it loaded only the one measurement it was opened on. It now
  opens at the screen's height and, for a dated verification, loads **all**
  of that run's dates — so the trend over time draws even when report-saving
  is off.
- **The Measurement-info window fits the screen.** Its details area demanded
  a fixed 720 px, so on smaller displays the window's bottom sat off-screen
  and nothing scrolled; the details now take what the screen affords and
  scroll for the rest.
- **The chart-replace window's text tells the truth about snapshots.** It
  claimed the displaced measurements would "no longer have the chart they
  were made with" — every measured date keeps its own stored copy, and the
  new wording says so (awaiting review in §M-PROPOSED). The note shown when
  Duplicate is unavailable lost its file-extension jargon.
- **The verification-saved window offers both doors.** After a verification
  measurement it now explains and offers the measurement report (the
  colour-accuracy analysis) alongside the measurement inspector, with the
  report as the default (proposed by Sebastian mid-session).
- Quieter, truthful logs: the native-print "no default output intent" case is
  reported as information in plain words, and the splash no longer asks Qt
  for a font family that does not exist.

### Confirmed on hardware (Sebastian, 2026-08-10)

§3.1a forced-Raw for converted charts · the Q3 raw default with history ·
feature A's conversion proven on paper (9.5 ΔE00 sheet separation) ·
feature B's report against the colorimetric reference (mean 2.80 ΔE00,
corners excluded) · the IMPORT module end to end. Recorded in
`docs/design/verification_printing_and_target.md` and the unified model's §I.

## v3.14.8-beta.212

### Changed

- **FROM PROFILE GAMUT parks the two header shortcuts that bring their own
  patches** (Basti, 2026-08-10). "Load patch set" and the built-in presets
  button grey out while the module is active — a loaded patch set would be
  silently ignored by Generate, and a preset would switch the module away and
  replace the chart. Their tooltips say why and where to go instead, and both
  come back the moment you switch to GUIDED or MANUAL.

### Fixed

- **"Auto-update preview" works again while experimenting with a
  verification chart's layout** (Basti, 2026-08-10). The pause guard asked
  about the run's *profiling* chart, so once a run had its profiling
  measurement the preview was paused forever — every knob turn answered with
  the paused note. It now judges the chart the re-layout actually touches:
  the verification chart, and only a measured dated verification that
  describes the chart currently on disk pauses it. Dates whose stored chart
  snapshot differs (e.g. after you knowingly regenerated the chart) protect
  nothing that a re-layout could strand, so the live update keeps working —
  and it pauses again as soon as a verification is measured with the new
  chart.

## v3.14.8-beta.211

### Fixed

- **A chart from FROM PROFILE GAMUT could be printed through the profile a
  second time** (Basti, 2026-08-10). Generating — or loading — a chart handed
  the Print tab only the page images, never the chart file itself, so the
  "Colour" row judged the previously loaded chart and offered (and even
  defaulted to) "Through the profile" for a chart that already has the
  profile applied. The Print tab is now told which chart it is holding on
  every path a chart can arrive by (generated, loaded from a project,
  switched to in the bar, renamed), forces "Raw — already converted" for it
  as designed, and re-reads the state every time the tab is entered.
- **The chart-file tooltip over the preview no longer inherits the size of a
  previous tooltip** (Basti, 2026-08-10). Moving the mouse straight from a
  long tooltip — e.g. the Run-type box's — into the preview showed the small
  folder/filename tooltip inside the previous tooltip's much larger box.

## v3.14.8-beta.210

### New

- **Import a measurement made in i1Profiler** (#133). The Measure tab gains a
  third mode for verification runs — **IMPORT** — for charts that were printed
  and measured outside ChromIQ (typically on an i1iO table). Choose the file
  with the green folder button — i1Profiler's own measurement (.mxf/.cxf),
  its CGATS text export (.txt), or a ready .ti3 — and press **Import
  Measurement**: ChromIQ converts it, checks patch for patch that it really
  belongs to this run's verification chart, and files a copy in its own dated
  verification folder together with a snapshot of the chart — exactly where a
  measurement made in ChromIQ would go. The original file is never moved or
  changed, an import never replaces an existing dated result, and a file that
  does not match the chart is refused before anything is written. A green
  info box in the module says up front what will be checked and where the
  measurement will land.
- The Dictionary gains an entry for the IMPORT module, and all twelve
  languages are translated.

### Fixed

- **Measure tab: the preview's Prev/Next row now ends level with the action
  buttons.** The empty reading-pace area under the preview reserved its gap
  even before a strip was read, holding the page buttons ~10 px higher than
  the buttons on the left; it now only takes room once it has something to
  show (Basti, 2026-08-09).

## v3.14.8-beta.209

### New

- **A verification chart built from your profile's own gamut** (#133,
  feature B). Create Chart gains a third module for verification runs —
  **FROM PROFILE GAMUT** — which asks the run's profile which colours of
  ChromIQ's reference set it can print, and tests exactly those. Choose how
  many colours, whether to stay safely inside the printable range or use all
  of it, and the rendering intent (absolute colorimetric by default); the
  panel shows live how many reference colours are printable and roughly how
  many sheets the chart needs with your current Manual layout. The sheet
  itself is laid out by printtarg or the ChromIQ layout engine exactly as in
  Manual.
- **The reference colour set ships with ChromIQ** — 5 960 colours, spread
  perceptually with extra weight on the greys, published with its full
  generation recipe in the file header and marked PROVISIONAL. Smaller charts
  test the first colours of the same list, so a quick check stays comparable
  with a thorough one.
- **The eight cube corners are always added**, outside the gamut filter, and
  reported in their own section — they measure how far your ink and paper
  reach, which is not the profile's doing, so they never distort the accuracy
  figures.
- **The measurement report gains a third reference.** A gamut chart is judged
  against its stored colorimetric targets ("what the profile promised"), the
  report names the set version and coverage, and when the stored reference is
  missing the report deliberately shows no ΔE at all rather than comparing
  against the wrong yardstick.
- **Everything fits feature A automatically**: a gamut chart already carries
  the profile, so the Print Chart tab forces "Raw" for it, and the report says
  which reference produced its figures.
- **Create Chart now explains the no-profile state** for verification runs —
  a friendly note in Guided/Manual (nothing is blocked), and the gamut module
  shows what to do instead of its options. New Dictionary entries: "From
  profile gamut", "Reference colour set", "Coverage".

## v3.14.8-beta.208

### New

- **A verification chart can now be printed THROUGH its profile** (#130,
  feature A). The Print Chart tab gains a "How this chart is printed" section
  for verification runs: **Colour** chooses between "Through the profile" —
  ChromIQ works out the ink amounts the profile predicts for every patch,
  prints exactly those, and keeps the printer's colour management off — and
  "Raw — no profile", which remains the printer drift check it always was. A
  **Rendering intent** control (relative colorimetric by default) and a
  **Route** row ("Print here" / "In another application", which hands over the
  finished sheets instead of printing) complete the section. Converted sheets
  land in the chart's `cache/` folder, always safe to delete.
- **The report now says how each verification sheet was produced.** Every
  print writes a record beside the chart — through the profile or raw, which
  intent, which profile file, who printed it — and the measurement report
  shows a "How this verification was produced" block naming the question the
  figures answer. A profile rebuilt after printing is flagged, and a report
  mixing differently-printed verifications warns that the trend changes
  meaning where the method changed.
- **Existing projects keep their meaning.** A run that already has
  verification history keeps printing raw by default, so its trend stays
  comparable; new work defaults to printing through the profile. The choice is
  stored per target, like Create Chart's settings.
- **A chart whose colours were already converted when it was made** (the
  planned From-profile-gamut charts of #133) forces Raw and disables the other
  option — applying the profile twice would be undetectable afterwards.
- **Check & Refine now warns before checking a measurement whose sheet was
  converted at print time** — the check would produce confident figures that
  describe neither the profile nor the printer.

### Fixed

- Two approved guidance texts instructed printing "with colour management on",
  which ChromIQ deliberately prevents on every print path. They now name the
  real control (revisions await review in §M-PROPOSED).
- The Print Chart tab's info boxes and options now share one scrolling area,
  so a tall section no longer squeezes Print Options to a sliver; in
  macOS-dialog mode the warning is no longer pushed out of view behind the
  overlay scrollbar.

## v3.14.8-beta.207

### Fixed

- **A switched-off radio button now looks switched off.** Options that ChromIQ
  had turned off were drawn exactly like the ones you can still choose, so
  there was no way to tell them apart — you could click one and simply nothing
  would happen. They are now greyed, the way switched-off tick boxes always
  have been.

## v3.14.8-beta.206

### New

- **The measurement report now checks that your readings really belong to the
  chart they are compared with.** Every patch is checked against the colour the
  chart asked the printer for, and if a lot of them come back as completely
  different colours the report says so, in plain words, above the figures. That
  can happen when a measurement is paired with the wrong chart, or when a chart
  measured in another program came back with its patches in a different order.
  Nothing is changed or hidden — the figures are still worked out in the usual
  way, and the note simply tells you to treat them with care.

## v3.14.8-beta.205

### Fixed

- **"Show patch distribution (3D)" now shows the chart you have selected.**
  With "Run type" set to Verification or Calibration it drew the profile run's
  chart instead, while calling it "Current chart" — the same mix-up the chart
  patch set editor had.

## v3.14.8-beta.204

### Fixed

- **A calibration no longer becomes the starting point for a new run.** When
  you pick "New run", ChromIQ starts you from the settings of the run you last
  had selected — a quick way to make a chart "like the last one, with one
  change", without saving a preset first. Visiting "Run type: Calibration"
  could quietly make the calibration sheet that starting point instead, handing
  a new profiling run the calibration's paper, instrument, margins and layout.
  New runs now only ever start from a profiling or a verification run.

## v3.14.8-beta.203

### Fixed

- **The chart patch set editor now opens the chart you actually have selected.**
  With "Run type" set to Calibration, Tools ▸ "Chart patch set editor" opened
  the profile run's chart instead of the calibration chart — on a real project
  it showed 400 patches under the profiling chart's name while the calibration
  chart beside it held 64. Editing from there and applying it laid the profile
  run's colours out and wrote them over the calibration chart, because a
  calibration build writes into the "cal" folder. Verification runs had the
  same fault: the editor opened the profiling chart rather than the
  verification chart. All three run types now open their own chart, and the
  editor's save name follows.

## v3.14.8-beta.202

### Fixed

- **Using a profile as pre-conditioning now shows that it will build a new
  run.** Choosing it from Build Profile or Check & Refine takes you to Create
  Chart, where the bar still read "Run 1 (overwrite)" — while generating the
  chart would in fact create a fresh run. It always did the right thing; the
  bar simply promised the opposite, which read as though it were about to
  replace the very run the profile came from.

## v3.14.8-beta.201

### Fixed

- **Guided refinement moves on to the next strip again after the "read a
  little fast" message.** Answering that message let the app miss the moment
  it was supposed to move, so it sat on the strip you had just read and
  waited for something that was never going to happen. It now makes the move
  itself.

### Changed

- **What the measurement log shows is now written to the log file as well.**
  Previously only ArgyllCMS's own output was saved, so with the log panel
  hidden there was no record of what ChromIQ decided during a measurement.

## v3.14.8-beta.200

### Fixed

- **The "this chart already has a measurement" window no longer contradicts the
  options behind it.** Asking Check & Refine to guide you through a refinement
  switches "Refine / resume" on, but the window still opened with it off — and
  pressing OK applies the window's choices, so it would quietly have switched
  the refinement back off and turned your next read into a replacement of the
  measurement you meant to keep. The window now opens showing what the panel
  actually says.

