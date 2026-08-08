# Changelog

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

