# The waits around an i1Pro / i1Pro 2 reading

Since 4.3.53 every wait below is a value the app passes to the chart-reading
helper at Start. Changing one needs no native rebuild.

| Wait | Default | Settings key (s) | Helper argument (ms) | Compiled fallback | What it protects | i1Profiler recorded |
|---|---|---|---|---|---|---|
| after a light change (lights Beta) | 2.1 s | `i1pro2_lights_quiet_s` | `--lights-quiet-ms` | `CQ_LIGHTS_QUIET_MS` 2100 | the first (dark) reading after a light write (lost 2 in 3 at 1-14 ms, 14 Nov) | 0.37 s least, 0.46 s typical by hand; 0.01 s before a calibration |
| after the dual scan's blue light | 0.37 s | `i1pro2_blue_quiet_s` | `--lights-blue-quiet-ms` | `CQ_LIGHTS_BLUE_QUIET_MS` 370 | the return pass's first reading (lost = M1/M2 end for that measurement) | 0.37-1.39 s from the write's start; 0.31 s from its end |
| first pass's end to the blue light | 0.55 s | `i1pro2_blue_after_s` | `--lights-blue-after-ms` | `CQ_LIGHTS_BLUE_AFTER_MS` 550 | nothing; only when the light goes out | 0.53-0.68 s after pass 1's last data |
| ArgyllCMS's lamp wait before a dark reading | 1.5 s | `i1pro_lamp_off_s` | `--lamp-off-ms` | `LAMP_OFF_TIME` 1500 | the dark reading: lamp afterglow would make it too high, and every patch slightly too dark, unnoticed | about 1.06 s on the i1iO table |

## Where the default lives

`core/instrument_waits.py`, the `default_s` of each `Wait`. That is the only
place. Settings `DEFAULTS`, the Preferences fields, the command line and the
log all read it. `tests/test_instrument_waits.py` fails on a second copy.

The compiled fallbacks are used only when the helper is not given the
argument (an older app, stock use). They are 4.3.52's values and should not
change.

## How to change one

* Developer: change `default_s` in `core/instrument_waits.py`. Nothing else.
  The app passes every wait that applies, also at its default, to a helper
  whose `--caps` names `instrument_waits`.
* User: Preferences > Beta (the fields under the i1Pro 2 lights, and the
  lamp wait on its own line).
* Tester without the window: one line in the settings file, in seconds, for
  example `i1pro_lamp_off_s=1.06` (macOS:
  `defaults write com.chromiq.ChromIQ i1pro_lamp_off_s -float 1.06`).

A value that is not a number from 0 to the maximum (10 s, 10 s, 5 s, 5 s) is
replaced by the default and the app log says so; the helper refuses one too
and names it in its `waits` event.

## Where a tester's log shows it

* `session: beta_options ... i1pro2_blue_quiet_s=0.37 ...` (session header);
* `measure start: ... lights_quiet_s=2.1 blue_quiet_s=0.37 blue_after_s=0.55
  lamp_off_s=1.5` (`(changed)` after one that is not the default);
* `helper waits: lamp_off_ms=... blue_quiet_ms=... blue_after_ms=...` (what
  the helper took; -1 = its compiled value).

## Not covered yet

The i1iO table reader (`workflow/i1io/table/reader.py`) starts its own helper
and passes no waits, so table readings use the compiled values. The table's
own scan waits (`cq_tscan.h` `CQ_TSCAN_LAMPOFF_MS` 1070,
`CQ_TSCAN_LIGHTSOFF_MS` 680, `cq_i1pro2_dual.h` `CQ_TDUAL_DARK_AFTER_LAMP_MS`
170) are still compiled.
