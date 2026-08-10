# Changelog

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

