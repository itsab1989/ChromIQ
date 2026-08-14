# Changelog

## v4.0.2-beta.4

### Fixed

- **"All strips read" waits until every patch really is read.** A strip can be
  accepted while one or two patches inside it were never recorded, and the
  finished message still appeared — on a chart that was 97.1% measured. The
  message now waits until nothing is left, and the measurement log says how
  many patches are still missing (reported by soul-traveller).

- **A chart with no measurement is no longer said to belong to another chart.**
  Switching to a run that had never been measured could report that its
  measurement was made for a different chart — about a file that does not
  exist. That claim is gone (reported by soul-traveller).

- **"Skip initial calibration" stays as you set it.** In the Manual module the
  tick was forgotten as soon as a measurement finished. It is now remembered
  from the moment you set it. The Guided module deliberately does not offer this
  option, and does not remember one either (reported by soul-traveller).

- **Pressing "n" moves to the next unread patch.** While measuring patch by
  patch, "n" is meant to jump to the next patch that has no reading yet. It
  looked at the patch you were already standing on — which has no reading, being
  the one you are about to measure — and so stayed where it was (reported by
  soul-traveller).

- **Refining a measurement shows everything measured so far.** Starting a
  refinement drew only the patches read in that session, so the gaps you were
  there to fill were invisible. Every patch already measured is shown from the
  moment the measurement starts (reported by soul-traveller).

- **Switching the progress bar off in Preferences takes effect at once.**
  Unticking **Show measurement progress bar** and pressing OK left the bar on
  screen until the app was restarted (reported by soul-traveller).

## v4.0.2-beta.3

### Fixed

- **A chart you have not measured yet no longer claims to belong to somewhere
  else.** Switching to a run whose chart had never been measured could bring up
  "This measurement was made for a different chart" — a statement about a
  measurement file that does not exist. ChromIQ now says plainly that the chart
  has not been measured yet, and invites you to measure it (reported by
  soul-traveller).

- **When a measurement really does belong to another chart, the message says
  why.** It now tells you how many measured patches the file holds, how many
  patches the chart on screen has, and that none of them could be paired up —
  and it points at **Restore Used Chart**, which puts back the exact chart a
  measurement was taken from. A bare verdict about a chart you printed yourself
  is impossible to check or act on (reported by soul-traveller).

## v4.0.2-beta.2

The second beta, adding the printed ruler markers.

### New

- **Helper markers for lining up a ruler.** Short dashes can now be printed
  along all four edges of the sheet, to lay a ruler against while you measure.
  The dashes along the top and bottom line up with the strips going across the
  page — the start and the middle of every strip, and the end of the last one —
  and those down the left and right line up with the patches going down the
  page in the same way. The rest of each edge is filled at that same spacing,
  right out to the corners.

  Switch them on with **Show helper markers (visible on print)** in the
  **Measured from Preview** frame under the Create Chart preview, and set how
  far in from the paper's edge they sit and how long they are. They are part of
  the printed chart, so they appear on paper as well as on screen, on every kind
  of chart — profiling, calibration and verification alike.

  On a ColorMunki chart, where every second strip is offset down the page, the
  dashes follow the first strip and line up with the shifted strips as well.
  They are not available for a SpectroScan chart with six-sided patches, where
  a honeycomb has no straight rows for a ruler to follow; there the controls are
  greyed out and say why (requested by soul-traveller).

## v4.0.2-beta.1

The first beta of the next version, carrying one new feature for testing.

### New

- **A progress bar while you measure.** The strip just above the chart preview
  now doubles as a progress bar: **"Progress: 42.5%"** on the left, and a
  coloured bar filling that strip from left to right as you work through the
  chart. It uses the Measure tab's own green, so it matches the heading beside
  it.

  It counts **patches**, not strips, and that is the point of it. If you switch
  between reading whole strips and reading single patches — to go back and pick
  up one patch you missed, say — a count of finished strips would quietly tell
  you the wrong thing. Counting the patches that actually have a reading is true
  in both ways of working, and re-reading a patch you have already measured does
  not move the number, because that patch was already counted.

  Opening the Measure tab picks up where you left off, reading the measurement
  your run already holds, so a chart you started yesterday does not start again
  from zero. If there is no measurement yet, or the file is one ChromIQ would
  not trust, no coloured bar is drawn and the percentage simply reads 0.0%.

  You can turn it off with **Show measurement progress bar** in **Preferences ▸
  Measurement**, below "Warn me if a strip looks misaligned". With it off,
  neither the percentage nor the bar appears and no patches are counted at all
  (requested by soul-traveller).


## v4.0.1

Fixes around the very first chart of a new project — found by Knut and
Sebastian testing side by side on one afternoon, all sharing a single root:
what you type before the first Generate had nowhere to live yet — together
with a group of measuring aids that were describing the chart slightly
inaccurately.

### Fixed

- **"Close to the limit" is only said when a strip really is close.** While you
  measure, the message under the chart preview tells you how your reading speed
  is doing. It was calling a strip "close to the limit" when it was as much as
  35% clear of it — so a ColorMunki strip read at 521 ms per patch was warned
  about even though the limit is 400 ms. How close is close enough to mention
  is now yours to choose, in **Preferences ▸ Measurement ▸ Close to the
  limit**, and it starts at 10%. At that setting the 521 ms strip in the report
  is simply called a good reading speed, which is what it was. Set it to 0% if
  you would rather only ever be told when a strip is genuinely too fast
  (reported by soul-traveller).

- **The reading-speed message now tells you the whole-strip time as well.**
  Milliseconds per patch is a hard thing to picture while you are holding an
  instrument. The message now also gives the figure you can actually feel — the
  seconds a whole strip should take — so instead of just "400 ms or more per
  patch" you get "400 ms or more per patch — 6.0 sec. or more per strip". If
  the window is narrow the message wraps onto another line and the area grows
  to fit it, rather than cutting the end off (reported by soul-traveller).

- **The ColorMunki gets more room at the top of the page.** The top margin
  ChromIQ warns below is now 33 mm for every paper size, instead of 30 mm. The
  reason is mechanical rather than optical: the two knobs on the underside of a
  ColorMunki catch on the edge of the sheet as you start a strip, so the
  instrument needs a little more paper in front of the first patch than the
  light path alone would suggest. If you had already set a margin of your own
  for a page size, your value is kept exactly as it is (reported by
  soul-traveller).

- **Loading a patch set tells you how many patches arrived.** The **Edit /
  Create Chart Patch Set** window now says, for example, "Loaded MyChart.ti1 —
  2002 patches", so you can check the number against the file you chose
  (reported by soul-traveller).

- **A chart keeps the patch set it was built from.** If you built a chart from
  a patch set of your own — one you made with the patch generators, edited in
  the Patch Set editor, or loaded from a file — and later pressed **Generate
  Chart** again, ChromIQ could quietly build a completely different chart with
  a fresh set of patches. It happened once the project had been closed and
  opened again, which is easy to do without thinking about it: the link between
  the chart and your patch set was only remembered while the app stayed open.
  This mattered most when the chart had already been printed, because the
  sheets on your desk then no longer matched the chart ChromIQ would measure
  them against, and nothing on screen said so. A run now keeps its own patch
  set, so generating again lays out the very same patches. Changing something
  that defines the patch set itself — the patch count, the grey steps, the
  white or black patches — still gives you a fresh chart, because that is what
  asking for different patches means. You can also see that your patches are
  protected: the **"Edit patch recipe (override preset)"** box is shown with
  the patch settings greyed out behind it, and you tick that box on the
  occasions when you do want a brand-new set of patches (reported by
  soul-traveller).

- **Loading a patch set no longer adds patches that are not there.** In **Edit /
  Create Chart Patch Set**, choosing **Load Patch Set…** and picking a `.ti1`
  file added more patches than the file contains — 2019 instead of 2002 for a
  typical chart. A `.ti1` file holds three tables, and only the first one is
  the patches to print; the two after it hold reference values that ArgyllCMS
  needs, such as the corners of the colour cube. Those were being read in as
  though they were patches. Only the patch table is loaded now (reported by
  soul-traveller).

- **The colour list handed to a print shop is no longer empty.** Every chart
  writes a `-colours.txt` file into its run's `exports` folder — a plain list
  of the chart's colours you can pass to a print shop or another program. That
  file was being written completely empty, for every chart, because of the same
  misreading of the three tables described above. It now contains the full list
  of colours again. Any file you exported before this will still be empty, so
  generate the chart again if you need one of them.

- **The measurement sounds are heard again.** Many of the short sounds went
  missing entirely — the tick for each patch, the thump for a patch that is
  off-colour, and ding, click, chime, buzz, bump and ding-hi — and longer ones
  could lose their opening, which is what stopped the bell sounding like a
  bell. The sound files were never at fault. On a Mac the sound hardware is
  allowed to go to sleep when nothing has been played for a while, and whatever
  wakes it up loses its own beginning while the hardware starts. A short sound
  can be over before the hardware is properly awake, so it is never heard at
  all. ChromIQ now wakes the sound hardware quietly in advance — when a
  measurement starts, and when you press **Play** in **Preferences ▸ Sounds** —
  so the sound you actually want to hear arrives into hardware that is already
  running. During a measurement the cues follow each other closely enough to
  keep it awake by themselves (reported by soul-traveller).

- **The instrument's own "ready" beep is back.** When you press the button on
  your instrument to start reading, it plays a short beep to tell you it is
  ready for you to move. That beep comes from ArgyllCMS rather than from
  ChromIQ's own sounds, which is why it does not appear in the list on
  **Preferences ▸ Sounds** — and it had gone quiet on macOS. It sounds again
  (reported by soul-traveller).

- **Three sounds start out better chosen.** A patch that reads off-colour now
  starts as **bump**, a finished measurement as **chime-long**, and a finished
  profile as **applause**. If you had already chosen your own sound for any of
  these, your choice is kept exactly as it is (chosen by soul-traveller).

- **The pointer ruler measures the chart you are looking at.** With "Show
  measurement coordinates on pointer" ticked, the readout used the Resolution
  setting rather than the resolution the chart on screen was actually made at.
  On a 200 dpi chart every reading came out at two thirds of the truth — an A4
  sheet's far corner read 140.0 × 198.3 mm instead of 210 × 297, and the ruler
  disagreed with the margins listed right below it. Both now read the page's
  own resolution, so they always agree, on any paper size and either
  orientation (reported by Knut).

- **The expected-vs-measured overlay sits exactly on its patches.** During a
  measurement the coloured split could leave a thin rim of the real patch
  showing along an edge. Four separate causes, all fixed: the patch boxes were
  rounded in a way that shifted them up and to the left; on a hexagonal
  SpectroScan chart the honeycomb offset was missing entirely; on a Retina
  screen an edge could land half a pixel off; and the strips were not always
  kept inside the page. The corrected patch rounding also makes the patch
  boxes in a scanner or camera target exact for rectangular charts. Scanner
  and camera work stays unavailable for hexagonal SpectroScan charts, as it
  always has been — a CHT recognition file cannot describe a hexagon, so
  those charts are measured with the SpectroScan itself.

- **The overlay legend keeps clear of the chart.** It could overlap the last
  row of patches, the edge spacer or the scan arrow, depending on the layout.
  On a ColorMunki chart with staggered strips it sat across the last patches
  of the lower strips: every second strip is offset down the page, and its
  recorded position did not include that offset. The strip highlight and the
  click-to-jump target on the Measure tab were off by the same amount on those
  charts, and are now exact.

- **"No spacers" now means bare paper.** Choosing no spacer still drew black
  bars between the patches and the strips; the gaps are left blank, as asked
  for.

- **Your run description survives the first Generate.** Typing a description
  for a brand-new project and pressing Generate Chart cleared the field and
  lost the text; it is now written into the freshly created run, exactly as
  it already was when adding a run to an existing project.

- **The project name is one value in Guided and Manual.** A name typed in
  Guided now appears in Manual immediately (and the other way round) — before,
  the two fields only agreed once a project existed, so a fresh start showed
  the name in one mode only.

- **The first chart of a new project keeps your settings.** After the first
  Generate, the screen could snap back to factory defaults — the instrument
  jumped from ColorMunki to i1Pro by itself, and a re-layout could redraw the
  chart with the wrong instrument's geometry, leaving the page half filled.
  A new project's first run is now born with the exact settings its chart was
  built from.

- **Save as Defaults no longer stores the project name.** Every other row on
  the tab is a preference; the name identifies a project — saving it seeded
  every future fresh start with an old project's name, one Generate away from
  building into it. The saved name from older versions is cleared too.

- **The app no longer crashes when an instrument keeps dropping off the USB
  bus.** Closing Read Single Patches now lets go of the measuring engine
  properly. Before, a session that ended by itself could report back a moment
  later, into a window that had already closed, and the app died outright
  (reported by Knut with a ColorMunki on a 2019 MacBook).

- **"No instrument found" now names the likeliest cause and offers the fix.**
  On some computers, older Macs in particular, the "Faster instrument
  connection" shortcut is what stops an instrument being seen at all. Both the
  measurement window and Read Single Patches now explain this and carry a
  **Turn off faster connection** button, so you do not have to go hunting
  through Preferences in the middle of a measurement; the text also says where
  the option lives (Preferences ▸ Measurement) for switching it back on. The
  option's own help text says when turning it off is the right move.

## v4.0.0

> **This entry covers everything that changed since v3.14.7, the last stable release** — 224 betas' worth of work, grouped so you can find what affects you instead of reading a diary. The individual beta histories remain in the repository.

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
  never possible on this paper. White, black and evenly spaced grey steps
  take about one patch in eight — enough of a grey wedge to catch a
  drifting printer, without swallowing a small chart. Repeated checks of
  one profile always get the same colours, so this month's figures compare
  patch by patch with last month's. The chart already carries the profile, the Print Chart tab selects
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
  and Build Profile each remember their own settings per run — and per run
  type, verification included; switching run, opening a project or changing
  run type loads them, leaving a tab saves them — without a dialog. This
  holds before any chart exists, and a generated chart's own file records
  the complete recipe that made it, so returning to a run always shows the
  options its sheet was really built with. A brand-new run starts from the
  values of the run you were on — by design, so "make another run like this
  one, with one change" needs no preset.

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
  and each profile run records which calibration it was built with — one
  run can keep an older calibration with "Include" while another applies
  the new one.

- 🔔 **Sounds during measurement** — a strip accepted, a patch misread, a
  session finished — so you can keep your eyes on the chart. **Preferences →
  Sounds** — pick a sound per event, or point ChromIQ at your own sounds.

- **A gentle warning when you swipe a strip too fast.** Every instrument
  takes a fixed number of readings per second, so a strip has a minimum
  time it needs — swipe faster and patches get too few readings, even when
  ArgyllCMS still accepts the strip. ChromIQ knows the pace for your
  instrument, shows a live verdict while you measure, and mentions it when
  a strip was read quicker than the minimum, so you can re-read it before
  it costs you accuracy — the strip reading times under the chart preview
  mark such a strip with an **✕**. Tune or switch it off under
  **Preferences → Measurement** ("Warn me when I read a strip too fast").

- 📖 **The "Getting started" help card was rebuilt**: a clickable chapter
  index, chapters that walk from first start to a finished profile, its own
  chapter on checking a finished profile (the three ways, and which to
  pick), and a plain-language overview of where your files are stored — in
  all twelve languages.

- 🌍 **Twelve languages, complete** — German, Spanish, French, Italian, Dutch,
  Portuguese, Swedish, Norwegian, Polish, Russian, Japanese and Chinese —
  every button, message, tooltip and help text.

- **Demo projects for learning and testing**, attached to this release as
  downloads:
  [ChromIQ-demo-projects.zip](https://github.com/itsab1989/ChromIQ/releases/download/v4.0.0/ChromIQ-demo-projects.zip)
  demonstrates the file-handling rules step by step (including projects in
  the old 3.13 layout, to watch the migration happen),
  [Demo-Report-Matrix.zip](https://github.com/itsab1989/ChromIQ/releases/download/v4.0.0/Demo-Report-Matrix.zip)
  holds thirteen documented Measurement Report cases with one ready-made
  PDF per case, and
  [ChromIQ-Switching-Demo.zip](https://github.com/itsab1989/ChromIQ/releases/download/v4.0.0/ChromIQ-Switching-Demo.zip)
  demonstrates the per-run settings rules with documented test cases.

- **Preferences → "Hide the log panel on every tab"**, for when the chart
  preview deserves the room. The full log is still written to disk.

### Changed

- **The ChromIQ layout engine is the default for new charts** — in Manual
  mode too, where printtarg stays one untick away (Guided has used the
  engine all along). A saved echo of the old off-default is migrated once;
  a choice you make yourself is never touched, and charts that exist keep
  the layout recipe recorded in their own file.

- **The chart-reading engine has left the Beta tab.** It and its
  companion options (patch flagging, calibration retries, faster
  connection, the misalignment warning) now live at the top of
  Preferences ▸ Measurement, and the engine no longer carries a beta
  label — only the profile engine is still experimental.

- **The measurement report explains its own limits.** *How to read this
  report* now says what the one ΔE figure bundles — the profile's
  conversion of each colour, the printer's behaviour on the day, the
  instrument's own small uncertainty — and points to Check & Refine ▸
  **Analyse Profile Quality** as the check that looks at the profile
  alone. It also says plainly what the figures are for: comparing a
  profile with itself over time, not ranking papers or printers against
  each other. The coverage line in Create Chart and the report's
  within-gamut note now carry percentages besides the counts.

- **Preferences links the ChromIQ website.** The "Created by" line above
  the buttons carries a **Website** link in the app's accent colour — one
  click to the showcase page.

- **The measurement report breathes, and its PDF prints the same
  everywhere.** A small gap under every section headline, after the intro
  lines, and between the four trend charts; each section starts on its own
  PDF page, and a table always keeps its headline beside it. Headline sizes
  are pinned, so a saved report renders identically wherever it is made.
  The report window opens a little wider, and the console warning about a
  missing "Sans-serif" font is gone.

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
  the log panel ends on the same line shown or hidden — and can be dragged
  as large as the window allows — the run bar no longer shifts during
  start-up, and windows placed off-screen by the system are nudged back so
  their bottom row of buttons is always reachable.

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

Two hundred and twenty-four betas fixed far more than fits a list — the
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
- **The strip reading times sit exactly under their strips** — they used to
  drift right of their strips as the preview re-fitted; they are placed
  live at every paint now, and on a small window they split into two
  staggered rows so every time stays readable.

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
  four-location design again. The report window itself keeps its run list
  to five lines, its charts readable and its buttons on screen at every
  window size.
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
