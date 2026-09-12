# ADVERSARY TWO — the Measurement Report, the demo packs, the log panes, the import

Branch `feature/182-compliance-sets` at `1494986b`, in the worktree
`.claude/worktrees/agent-aacf6e4e87f4094ce`. Nothing committed; `adv2.patch` is
the whole change.

## Mode, and the one thing that could not be done

Everything was driven **on screen, cocoa, in real windows** — a real
`MainWindow`, a real `MeasurementReportDialog`, a real `ThresholdsDialog`, real
tick boxes clicked. Never `QT_QPA_PLATFORM=offscreen` in a driver; that variable
appears only where the test suite runs.

**THE SCREEN WAS LOCKED FOR THE WHOLE RUN** — checked at 08:08, 08:22 and 08:27
CEST on 2026-09-12 with `onscreen_capture.session_is_locked()`, True every time.
`capture_window` therefore REFUSED every photograph rather than keeping
wallpaper. The window state below is read out of the live widgets, which is
real, but **there are no pictures**. Every driver leaves its capture calls in
place: re-run any of them once the screen is unlocked and the shots land in
`onscreen/shots/`.

## The drivers

| file | what it asks |
|---|---|
| `drive_adv2_log_tail.py` | does the Create Chart output pane drag a reader who scrolled up? |
| `drive_adv2_locked_columns.py` | is a hidden limits column remembered on a LOCKED run? |
| `drive_adv2_custom_columns.py` | what do the two Custom ISO columns actually hold, cell by cell? |
| `repro_tail_progress_line.py` | the same as the first, on the bare widget |
| `probe_deviceless_no_chart.py` | what `assess` says about a device-less file with no chart |

Run them with the sandbox set:

```bash
export CHROMIQ_SETTINGS_FILE=/tmp/chromiq-adv2.ini
export CHROMIQ_PRESETS_DIR=/tmp/chromiq-adv2-presets
export CHROMIQ_ADV2_WORK=/tmp/chromiq-adv2-work
```

## The sandbox held

* `defaults read com.chromiq.ChromIQ custom_output_path` → **unset**, the same
  as the baseline in `custom_output_path_before.txt`.
* the real plist mentions `tmp` **0** times.
* `ls ~/ChromIQ` is byte-identical to `home_chromiq_before.txt`: 22 entries,
  nothing added.
* the sandboxed ini holds `custom_output_path=/tmp/chromiq-adv2-work`.

## The gate

`QT_QPA_PLATFORM=offscreen pytest --runslow -n auto -q`, output redirected to
`gate.log` and read from the file:

```
14125 passed, 185 skipped, 4 xfailed in 233.57s (0:03:53)
GATE EXIT=0
```

No `node down`, no `Fatal Python error`, no `Timeout (0:0X:XX)!` in the log.

## The mutations

`mutations.json` is the output of `mutate.py` for all seven. Every one landed.
`prove_the_old_allowlist_was_loose.py` and `prove_the_grep_version_was_blind.py`
show the two weakened tests walking past the mutation that now kills them.
