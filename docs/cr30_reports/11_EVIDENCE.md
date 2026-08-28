# Evidence for report 11 — Basti's session of 2026-08-28 22:10–22:14

Source: ~/Library/Logs/ChromIQ/chromiq.log (tail). Project: CR30-Test/runs/run1,
390 patches, guided, CR30, patch-by-patch, external values (-xx --json).

## F1 — no calibration instruction at start
Not implemented. The design Basti ruled (verbatim, earlier in this session):
  "i'd rather have this button being a calibration button and instructions to
   put the cap with the white tile on for this. then the calibration
   confirmation window should appear and explain to take the cap off again and
   how to navigate. of course the calibration reading in the first window
   should not be counted as a measurement and the calibration button should
   trigger the calibration on the instrument wthout the user pressing a button"
EXP-MEAS-004 (research repo) CONFIRMED the host can trigger a calibration:
paper moved 81.10 -> 149.10 %R from a host-only trigger against the green face;
restore returned 81.20, ratio 1.0012.

## F2 — no expected-vs-measured overlay in patch-by-patch
The data is present in every patch_read event:
  {"event":"patch_read","id":"384","loc":"A1","xyz":[45.2193,36.4965,44.9748],
   "exyz":[49.9972,39.5511,75.2743],"de":27.05}
Three patches read: dE 27.05, 69.64, 22.23. (Large because the instrument was
never calibrated - see F1. Do not chase the dE magnitude as a separate bug.)
The patch highlighter DOES work. The overlay does not appear.

## F3 — beachball on quit mid-measurement  [ROOT CAUSE, arithmetic]
22:11:19.339  last "spot_ready" printed (patch A4 armed) -> DeviceReader starts
              its button wait, button_timeout_s = 180.0
22:11:36.794  user quits; measure settings written, window geometry saved
22:11:37.026  ArgyllRunner: finished with code 9
22:11:37.027  WARNING measure_manager: "the chart's instrument is one stock
              chartread cannot read (unknown error) - not falling back"
   ... 162 SECONDS OF NOTHING - the beachball ...
22:14:19.872  app resumes, settings writes continue, cleanup completes
22:11:19.339 + 180.0 = 22:14:19.339, and the app came back at 22:14:19.872.
The quit path blocks on the reader thread, which is inside its 180 s poll loop
and is never cancelled.

Basti also reports the app "still is not really closed" some minutes later.
No ChromIQ process was alive when checked at ~22:20 (ps aux, pgrep: nothing).

## F4 (mine, not reported) - a misleading warning on a clean user quit
Exit code 9 on a user-initiated stop is reported as an instrument failure
("unknown error"). Nothing failed; the user quit.
