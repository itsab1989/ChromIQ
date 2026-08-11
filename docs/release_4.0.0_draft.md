# ChromIQ 4.0.0 — release notes (DRAFT)

> **Draft, not the release.** This replaces the `v3.14.8-beta.*` /
> `v4.0.0-beta.*` sections in `CHANGELOG.md` when 4.0.0 final is cut. It is
> written from those entries — **219 beta tags and 562 commits since
> v3.14.7** — grouped so a user can find what affects them, rather than read
> a diary.
>
> Counts verified 2026-08-11 with `git tag -l 'v3.14.8-beta.*' | wc -l` and
> `git rev-list --count v3.14.7..HEAD`. Re-check them at tag time — they have
> gone stale in this file twice already, and a release note is a bad place to
> publish a number nobody re-derived. (An earlier revision also quoted a
> changelog-entry count; the changelog has since been rotated, so that number
> can no longer be re-derived and is not quoted.)
>
> The tag itself needs Sebastian's explicit go-ahead; betas are cut on the
> assistant's initiative, a stable release never is.

---

## v4.0.0

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

### New — verification, from start to finish

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

- **Import a measurement made in another program.** The Measure tab's
  **IMPORT** module files an i1Profiler (or any .ti3) measurement as a dated
  verification: converted, checked patch-for-patch against this run's chart,
  and stored exactly where a native measurement would go. Your original file
  is never touched.

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

- **The Measurement Report grew into the profile's health record.** It
  gathers every dated check of a run automatically, trends colour accuracy,
  paper white, darkest black and the cube corners over time, lets you
  untick individual runs, warns about mixed instruments and mixed printing
  methods, carries adjustable Pass thresholds, and remembers every option
  you set. **Save report as PDF** produces a print-sharp document (vector
  text, ~300 dpi charts) whose proposed folder always matches what the
  report covers — one dated check, one run's checks, or the whole profile.

### New — the rest

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

- **Calibration is a run type.** Choose **Calibration** in the Run type list
  and the whole app follows: chart, measurement, `.cal` file and its
  description live in the project's `cal/` folder, shared by every run, and
  each profile run records which calibration it was built with.

- **Sounds during measurement** — a strip accepted, a patch misread, a
  session finished — so you can keep your eyes on the chart. **Preferences →
  Sounds.**

- **Twelve languages, complete** — German, Spanish, French, Italian, Dutch,
  Portuguese, Swedish, Norwegian, Polish, Russian, Japanese and Chinese —
  every button, message, tooltip and help text.

- **Demo projects for learning and testing**: a downloadable package
  demonstrating the file-handling rules step by step, and the
  Demo-Report-Matrix package whose thirteen documented cases exercise every
  variation the Measurement Report can meet.

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

- **Existing projects are migrated in place.** A project from 3.13 or an
  earlier 3.14 is reorganised into the new folder shape the first time it is
  opened — every old file kept, the plain-language folder guide ("Where are
  my files?" in the Welcome window) always current.

- **The interface holds still.** Buttons sit in the same place on every tab,
  the log panel ends on the same line shown or hidden, the run bar no longer
  shifts during start-up, and windows placed off-screen by the system are
  nudged back so their bottom row of buttons is always reachable.

- **The windows that ask what to do with a chart read like every other
  window** — explanation in plain text, buttons in a row, Cancel set apart,
  long project names shortened in the middle with the full name given in the
  text.

- **ChromIQ starts a little quicker** — the printer list is fetched when you
  first open Print Chart rather than while the window is being built.

### Fixed

The fixes most likely to have affected you; the per-beta sections carry the
complete record:

- **Checking for updates works again for stable versions.** The check used to
  fail with "No release tag found" whenever the newest releases were all
  betas; it now asks for the latest finished release directly.
- **Pressing Esc during a measurement no longer throws your readings away.**
- **Several measurement windows never appeared at all** when the ChromIQ
  reading engine was in use — all reachable now, verified against a real
  instrument.
- **Patches no longer come back as "inconsistent" for no visible reason** —
  the tolerance sent to the instrument was stricter than the manufacturer's
  own.
- **"This chart was made for a different instrument" could name the wrong
  one**, and **restoring a calibration chart put back a different chart**.
- **A damaged `meta.json` no longer stops a run remembering anything.**
- **Text typed for a "New run" is kept**, and lands on the run you make.
- **The measurement report's PDF paginates cleanly** — headings stay with
  their tables, the trend legend never overlaps the graph, and charts print
  sharp instead of pixelated.
- **Help texts tell the truth.** The verification help card described a
  colour-management print path the app deliberately prevents; the gamut
  check was described as a drift check; "as measured (absolute)" read like a
  rendering intent. All corrected — and every such correction is now guarded
  by a test.

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
