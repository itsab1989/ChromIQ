# The waits around an i1Pro / i1Pro 2 reading

Since 4.3.53 every wait below is a value the app passes to the chart-reading
helper at Start. Changing one needs no native rebuild.

| Wait | Default | Settings key (s) | Helper argument (ms) | Compiled fallback | What it protects | i1Profiler recorded |
|---|---|---|---|---|---|---|
| after a light change (lights Beta) | 2.1 s | `i1pro2_lights_quiet_s` | `--lights-quiet-ms` | `CQ_LIGHTS_QUIET_MS` 2100 | the first (dark) reading after a light write (lost 2 in 3 at 1-14 ms, 14 Nov) | 0.37 s least, 0.46 s typical by hand; 0.01 s before a calibration |
| after the dual scan's blue light | 0.37 s | `i1pro2_blue_quiet_s` | `--lights-blue-quiet-ms` | `CQ_LIGHTS_BLUE_QUIET_MS` 370 | the return pass's first reading (lost = M1/M2 end for that measurement) | 0.37-1.39 s from the write's start; 0.31 s from its end |
| first pass's end to the blue light | 0.55 s | `i1pro2_blue_after_s` | `--lights-blue-after-ms` | `CQ_LIGHTS_BLUE_AFTER_MS` 550 | nothing; only when the light goes out | 0.53-0.68 s after pass 1's last data |
| ArgyllCMS's lamp wait before a dark reading, original i1Pro (rev A to D, rebadged ones such as the ES-1000) | 1.5 s | `i1pro_lamp_off_s` | `--lamp-off-ms` | `LAMP_OFF_TIME` 1500 | the dark reading: lamp afterglow would make it too high, and every patch slightly too dark, unnoticed | no recording of this instrument evaluated |
| the same for the i1Pro 2 (also ES-2000, i1Basic Pro 2), after 4.3.54 | 1.10 s | `i1pro2_lamp_off_s` | `--lamp-off-ms-i1pro2` (caps `lamp_off_i1pro2`) | `CQ_LAMP_OFF_TIME_I1PRO2` 1100 | the same | 1.059 s from lamp off to the next dark reading (i1iO table spot readings, an i1Pro 2) |

## The two lamp waits (after 4.3.54, the owner's decision of 2026-11-21)

Until 4.3.54 one field (default 1.5 s, ArgyllCMS's value) served the original i1Pro and the
i1Pro 2. The i1Pro 2 now has its own, default **1.10 s**: i1Profiler was recorded waiting 1.059 s
from lamp off to the next dark reading of an i1Pro 2 (`RECORDED_LAMP_OFF_S`), rounded UP on the
fields' 0.05 s grid. On real hardware (a tester's i1Pro 2, 21 Nov 2026) dual scans with real
lamp-off to dark gaps of 1.03 to 2.24 s showed no effect (the UV effect flat within 1 %, the
darkest patches unchanged, two runs 0.11 dE00 apart; work folder 2026-11-21_nelson_bluelight_confirm,
analysis sections 7 to 9). At 1.5 s the wait held the person back on 20 of 34 strips by about
0.24 s. The physical reason for a wait at all stays: lamp afterglow in the dark reading. The
original i1Pro keeps 1.5 s; no vendor recording of it has been evaluated for this wait (the
private i1Profiler recording of an i1Pro rev A, 2026-11-13, states no lamp-off to dark time).

**Who gets it:** every user of ChromIQ's own reading engine with an i1Pro 2, Beta options or
not (the field sits in Preferences > Beta beside the other waits). Not the i1Pro 3 or any other
instrument: the wait lives in the i1Pro / i1Pro 2 driver only, which picks the value by the
model it opened (`CQ_LAMP_OFF_TIME`, `p->dtype`).

**The i1iO table** (second fix round): its window passes both fields to every patch by patch
reader (`--lamp-off-ms` and, to a helper with the build token `lamp-off-i1pro2`,
`--lamp-off-ms-i1pro2`), so the table's i1Pro 2 follows the i1Pro 2 field. Its strip rows keep
the table's own scan waits; the row speed and the table's speed answer do not depend on this wait.

**Old and new together:** a helper without the caps word gets `--lamp-off-ms` alone and applies
it to the i1Pro 2 too (as 4.3.54). A new helper given only `--lamp-off-ms` (an app of 4.3.53 /
4.3.54) does the same; given neither, the i1Pro 2 waits 1100 ms and the i1Pro 1500 ms.

**Migration (settings schema 36):** a stored `i1pro_lamp_off_s` other than 1.5 is copied to
`i1pro2_lamp_off_s` (somebody's choice); a stored 1.5 is the old default (Preferences writes
every field when it is closed with OK), so the i1Pro 2 then gets 1.10; nothing stored: nothing
to do. Once, at the first start of the new version. A typed value always wins.

**In the log:** the start line's `lamp_off_s=` and `lamp_off_i1pro2_s=`; the helper's
`helper waits: lamp_off_ms=... lamp_off_i1pro2_ms=...`; and once the instrument has reported
itself, `lamp wait: instrument=... applied=i1pro2|i1pro|i1pro2(i1pro_value) lamp_off_s=...`.

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
  two lamp waits, i1Pro and i1Pro 2, on their own lines).
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

The i1iO table's strip rows use the table's own compiled scan waits (below); its patch by patch
readers get the two lamp waits (above). The table's
own scan waits (`cq_tscan.h` `CQ_TSCAN_LAMPOFF_MS` 1070,
`CQ_TSCAN_LIGHTSOFF_MS` 680, `cq_i1pro2_dual.h` `CQ_TDUAL_DARK_AFTER_LAMP_MS`
170) are still compiled.
