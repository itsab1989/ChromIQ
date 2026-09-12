# proof_printpath — the build output pane, and the verification printing path

Everything here was produced by driving the REAL ChromIQ window on screen
(`QT_QPA_PLATFORM` never set), against
`CHROMIQ_SETTINGS_FILE=/tmp/chromiq-printpath.ini`,
`CHROMIQ_PRESETS_DIR=/tmp/chromiq-printpath-presets` and a working folder under
`/tmp`. Nothing was sent to a printer at any point.

**The login session's screen was LOCKED for the whole round**, so
`scripts/onscreen_capture.capture_window()` refused every photograph, by design:
macOS hands a locked session the desktop wallpaper while the permission check
still answers True. Every `capture_*` field in the JSON records that refusal
rather than a picture. The measurements below are numbers read off the live
widgets and the real files, which the lock does not affect.

## P1 — the output pane no longer fights the reader

`drive_p1_output_pane_scroll.py` runs two REAL `colprof` builds on a real
210-patch `.ti3`, on the Build Profile tab, in a real window.

| | build 1: the reader scrolls to the TOP mid-build | build 2: the view left at the bottom |
|---|---|---|
| **before** (`onscreen/before_p1_result.json`) | parked at 0, back at **value 20 of max 21** within one `processEvents`; **1837 of 1840** samples sat at the bottom across 71 appends; ended value 244 == max 244 | followed every line, ended value 249 == max 249 |
| **after** (`onscreen/after_p1_result.json`) | parked at 0 and **stayed at 0** through **83 appends** while the maximum grew to 254; **0 of 2144** samples sat at the bottom | followed every line, ended value 251 == max 251 |

## P2 — the two questions

* `ANSWERS-for-the-user.md` — written to be sent to her.
* `drive_p2_through_the_profile.py` → `onscreen/p2_through_the_profile.json`
  drives all five states of the Colour row in the real window and records what
  the control and the notice say in each.
* `drive_p2_is_the_notice_seen.py` → `onscreen/p2_notice_visibility.json`
  measures whether the "why it is greyed" notice is actually painted: it sits
  100 px below the radio and is fully on screen at 1620x1049 and 1620x1051, and
  partly clipped (54000 of 68040 px) at 1280x800.
* `drive_p2_which_run_owns_the_profile.py` →
  `onscreen/p2_which_run_owns_the_profile.json` proves the likeliest state she
  hit: a project with a profile in run 1 greys the option the whole time the
  bar's Profile run is on run 2.
* `measure_verification_tiff.py` → `onscreen/p2_tiff_measurement.json` answers
  the TIFF question by measuring the file: 99 of 99 `.ti2` device values are
  painted verbatim in the chart ChromIQ files under `verifications/`, and 9 of
  99 after `cctiff` through the run's profile.

## Mutations

`run_mutations.py` → `mutations.json`. Thirteen mutations, applied one at a time
to the tree that would be committed, `__pycache__` purged between every step,
and every one proven to turn its test red. Two earlier mutations MISSED and are
the reason the design changed: see the class docstring in `ui/widgets.py` and
the module docstring of the test file.
