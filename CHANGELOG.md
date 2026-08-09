# Changelog

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

