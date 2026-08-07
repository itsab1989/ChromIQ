# ChromIQ 4.0.0 — release notes (DRAFT)

> **Draft, not the release.** This replaces the 184 `v3.14.8-beta.*` sections in
> `CHANGELOG.md` when 4.0.0 is cut. It is written from those entries — 467
> commits, 446 individual changes since v3.14.7 — grouped so a user can find
> what affects them, rather than read a diary.
>
> The tag itself needs Sebastian's explicit go-ahead; betas are cut on the
> assistant's initiative, a stable release never is.

---

## v4.0.0

The headline of this release is that **ChromIQ now keeps track of your work for
you**. A profile run holds its own chart, its own measurement, its own settings
and its own description, and the app is careful with all of them: nothing you
made is deleted, only archived, and every window that could cost you something
says exactly what it is about to do.

### New

- **Every setting belongs to the run you set it on.** Create Chart, Measure and
  Build Profile each remember their own settings per run, so going back to an
  older run shows the settings that run was made with — not the last ones you
  happened to type. Switching run, opening a project or changing run type loads
  them; leaving a tab or quitting saves them, without a dialog.

- **Runs have descriptions.** Give a run a name in your own words —
  "matte paper, second attempt" — and it appears in the run bar, in the
  measurement report and on the printed chart. Verifications and the
  calibration have one too, and `{rundescription}` can be placed on the chart
  itself.

- **The profile description writes itself.** ChromIQ fills it from the project,
  the run and the date, and you can edit it or turn it off.

- **Calibration is a run type.** Choose **Calibration** in the Run type list and
  the whole app follows: the chart, the measurement, the `.cal` file and its
  own description live in the project's `cal/` folder, shared by every run.
  Each profile run records which calibration it was built with. You can pick
  Calibration before a project exists.

- **Verification runs, kept as history.** Measure a chart printed *through* a
  finished profile and the result is filed by date under the run, with its own
  report. Earlier checks are never overwritten, so you can watch a profile drift
  over months.

- **Sounds during measurement.** Each measurement event — a strip accepted, a
  patch misread, a session finished — can play a sound, so you can keep your
  eyes on the chart instead of the screen. Choose a pack or your own files under
  **Preferences → Sounds**.

- **Twelve languages, complete.** German, Spanish, French, Italian, Dutch,
  Portuguese, Swedish, Norwegian, Polish, Russian, Japanese and Chinese — every
  button, message, tooltip and help text, including the long explanations.
  **Preferences → Appearance**, applied after a restart.

- **A printable demo project package** with a `README.pdf`, so the file-handling
  rules can be followed step by step on real projects.

- **Preferences → "Hide the log panel on every tab"**, for when the chart
  preview deserves the room. The full log is still written to disk.

### Changed

- **The measurement model is consistent everywhere.** Replacing a chart,
  rebuilding one, starting a measurement over an existing one, deleting a run —
  each has one window, one wording and one outcome, whichever tab you reach it
  from. The rules are written down in `docs/design/` and the app is tested
  against them.

- **Nothing is deleted, only archived.** A measurement you replace, a chart you
  regenerate and a calibration you redo all move to an `old/` folder with the
  date. The windows say so before you commit.

- **Every run keeps a copy of the chart it was measured with**, saved the moment
  measuring starts, and **Restore Used Chart** puts it back — for profile runs,
  verifications and the calibration alike.

- **The interface holds still.** Buttons sit in the same place on every tab, the
  log panel ends on the same line whether it is shown or hidden, and the run bar
  no longer shifts about while the app is starting.

- **ChromIQ starts a little quicker** — the printer list is fetched when you
  first open Print Chart rather than while the window is being built.

### Fixed

Fifty-two fixes, of which the ones most likely to have affected you:

- **Pressing Esc during a measurement no longer throws your readings away.**
- **Several measurement windows never appeared at all** when the ChromIQ reading
  engine was in use — the abort confirmation, three failure windows and two that
  opened in silence. All reachable now, and verified against a real instrument.
- **"This chart was made for a different instrument" could name the wrong one.**
  It compared your connected device against a setting rather than against the
  chart, so a chart made for a ColorMunki could be announced as an i1Pro chart.
- **Restoring a calibration chart put back a completely different chart.**
- **A damaged `meta.json` no longer stops a run remembering anything.**
- **Patches no longer come back as "inconsistent" for no visible reason** — the
  tolerance sent to the instrument was stricter than the manufacturer's own.
- **Text typed for a "New run" is kept**, and lands on the run you make.
- **Windows that named a tab or a button that was not on screen** — including
  the completion window, which named a tab that does not exist when calibration
  options are switched on.

### For developers

- The test suite no longer writes to your own ChromIQ preferences.
- `docs/design/` holds the agreed specifications for the measurement model, the
  message catalogue, per-target settings, the measurement windows and their
  sounds, and calibration as a run type. They are binding: the suite fails if
  the code and the specification disagree.
