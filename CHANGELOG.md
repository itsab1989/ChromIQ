# Changelog

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

