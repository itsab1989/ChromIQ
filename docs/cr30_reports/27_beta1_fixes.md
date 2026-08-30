# 4.1.5 beta 1 — what was fixed, and what is knowingly left open

Written after implementing the [CR30-B1] challenge (`25_beta1.md`), 2026-08-30.
Every claim below is backed by a test that was **proved to fail against the
fault** before being kept — the failure mode this round exists to correct is
tests that pass by not running the code.

## The two blockers the challenge found

Both were introduced in the previous 24 hours, and both shipped with green
tests that never executed the path they covered.

### B1 — "Recalibrate now" led into a dead session

The magnet window is the remedy for Basti's own incident. Its "Recalibrate now"
called `_run_cr30_calibration()`, whose first act was
`_close_cr30_bridge(); _open_cr30_bridge()` — so the remedy **destroyed the
stopped session it was rescuing**, closed the instrument mid-recovery, and then
ran `resume_after_magnet()` against a brand-new bridge. That method's first line
is `if not self._stopped: return True`, so it reported success while arming
nothing, under a log line telling him the session had carried on.

**Fix:** a `keep_bridge` flag distinguishing the two callers — a Start must not
inherit a previous run's bridge; the magnet remedy must not discard the current
one.

**Why the tests missed it:** every test in
`test_cr30_magnet_stops_the_session.py` resumes the *same* bridge object, which
is the one thing the tab did not do. The tab path had no test at all. It does
now — `test_cr30_the_magnet_remedy_reaches_the_session.py`, driving the real
`TabMeasure` methods rather than reading their source. **5 of its 7 tests fail
against the fault.**

### B2 — the Bluetooth calibration speed-up was a placebo

None of its three behaviours landed:

* The demux routes a frame to the event queue only when its command byte is
  `0x01`. A calibration acknowledgement is `bb 11` / `bb 10`, so it lands in the
  reply **buffer** — and `saw_event(cmd)` was scanning the queue. Matched
  nothing; the old timing stood.
* A trigger's acknowledgement *does* go to the queue, leaving the buffer empty —
  and the loop's guard `and self._buf` meant the predicate was **never called**.
* So the trigger's own acknowledgement was left in the queue, and the next armed
  patch collected it through `drop_events` as a stray press: the operator was
  warned about pressing too early, for a press ChromIQ had made itself.

**Fix:** `saw_reply(cmd)`, which looks in the buffer, keyed on the three-byte
prefix `bb <cmd> 00` — the shape in every capture held, the vendor's Bluetooth
trace (EXP-BLE-016) and both of our own USB sessions (EXP-022). The `and
self._buf` guard is gone; every predicate is safe on empty input.

**Why the tests missed it:** the fake transport re-implemented `ask` *without*
the guard and delivered the acknowledgement to the queue the fix happened to
read — it validated the assumption rather than the code. The tests now drive the
real `BleTransport._ask` and the real demux, with only the radio and the passage
of time stubbed. **Both mutations were re-applied and proved to fail them.**

> ⚠ **The speed claim must stay narrow.** Basti, testing Bluetooth the same
> evening: *"i don't know if it is much faster"*. His two gaps — the first
> connection being made at the moment he clicks Calibrate, and a wait after the
> instrument has already beeped — are **not** what this fixed, and cannot be.
> The honest claim is that the poll loop no longer waits past the instrument's
> own answer. See `26_basti_ble_timing.md`.

## The Windows findings

* **W9 — the chart path went into JSON unescaped** (`session_start`). A Windows
  path is `C:\Users\…`; `\U` is not a JSON escape, so the parser rejected the
  line and the event was **silently discarded on every measurement**, taking the
  strip map and the patch count with it. The helper already had
  `cq_json_escape` and already used it for the `saved` event.
  Fixed, helper rebuilt, and `test_the_chart_path_survives_json.py` drives the
  real helper from directories named with a backslash, a quote, and both —
  asserting the event arrives *parsed* and that **no line was silently dropped**,
  because that silence is what hid this. **All 9 fail against the unescaped
  build.**
* **The committed helper binary is refreshed**, and its staleness test no longer
  greps for `b"CR30"` — which every build since this branch began contains, so
  it stayed green over a binary of any age. `CQ_HELPER_BUILD` carries a dated
  marker read from the sources. **Proved: the previously committed binary now
  fails it.**
* **W3 — two tests asserted the literal "Trash"**, a macOS word; the app itself
  was already right. They now assert `trash_name()`, and a new
  platform-parametrised test proves all three wordings (Trash / Recycle Bin /
  Wastebasket) **from any host** — this class of failure was previously only
  visible on the VM.
* **W7 — the "how to measure" window outlived its session.** It is modeless, so
  it never passed through `_exec_measure_dialog`, which is what fills the
  registry the ending closes. Registered now (Knut's beta.139 rule, no new
  text). Reproduced on macOS: never platform-specific, only unnoticed.

## Asked for by Basti mid-round

* **A refused reading now opens a window**, not just a log line —
  M-CR30-READ-FAILED (§M-PROPOSED). *"a message like this would be better in a
  pop up so the user is aware of it instead of ruining a whole measurement
  session when this is unnoticed"*. Modeless, because the remedy is to press the
  instrument's button and a modal would stand in front of it; it closes itself
  when the chart moves on; **one window per patch**, not one per refusal, since
  a flaky link can refuse the same patch five times.
* **`1 candidate(s)` is gone.** The same screenshot showed it; the project
  writes singular and plural out. Fixed at source in `device.py` and
  `usb_measure.py`, with a test that fails on any `(s)` reappearing.
* **The calibration graphics are stacked and larger** (`steps_pair`). One
  related thing was deliberately NOT changed — see `26_basti_ble_timing.md`.

## Knowingly open, and why

* **W4** (US Letter help card), **W6** (helper freshness in a source checkout —
  dev-only), and the standing backlog: the how-to window's OK+Stop buttons, the
  patient reconnect wait, the transport-changed announcement, the no-reading
  watchdog banner, M-CR30-INSTRUMENT-GONE's stale advice, V-17, `_retries` on
  click-re-arm, two false docstrings, the `ble.py` poll doctrine, the
  strip-recognition log line. All ship open, as in every prior beta.
* **The 69 Windows test failures that predate this branch.** They are font-metric
  and pagination tests; `master` fails them identically. Documented as known
  platform noise, not fixed here.
* **The TIFF preview legend can cover the last row of patches** when the margin
  is small — Basti, noted as "not a blocker".

## ⚠ A process question that is not mine to settle

§M says a message whose wording is not approved speaks through the **log** until
it is. Three CR30 messages are now shown in windows while `approved=False`:
M-CR30-MAGNET and M-CR30-READ-FAILED (both at Basti's explicit request, both
from faults he hit himself) and M-CR30-CALIBRATE. Meanwhile
M-CR30-INSTRUMENT-GONE stays log-only citing that same rule.

That is inconsistent, and it should be resolved deliberately rather than by
accumulation: **either the rule now reads "proposed wording may be shown in a
window when Basti has asked for that window", or these are exceptions and should
be recorded as such.** Flagged, not decided.

## The gate

`CLAUDE.md`'s rule names no platform, and every release so far has been gated on
macOS. Windows fails 69 of the same tests on `master`, so 4.1.4 shipped with
them latent. **Green gate = green `--runslow` on macOS at the tag commit.**
