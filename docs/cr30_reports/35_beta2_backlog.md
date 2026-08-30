# Beta 2 backlog — found after 4.1.5-beta.1 was tagged

## B2-1 · A deliberate Stop logs a WARNING about an unknown error

Reported by Basti from his terminal, 2026-08-30, seen three times:

```
[WARNING] workflow.measure_manager: the chart's instrument is one stock
chartread cannot read (unknown error) — not falling back
```

**It fires on a NORMAL stop of a CR30 measurement.** Confirmed against his log:
at 06:09:22 the helper exited with code 9 and `_user_quit` was False, so the
branch at `measure_manager.py:470` was taken — the branch meant for an engine
FAILURE on a chart stock chartread cannot read. The next lines show the session
ending cleanly and his measurement being restored.

`_user_quit` is set from exactly three places: the `q`/`Q`/Esc key
(`:771`), `abort()` (`:995`), and the engine's own `aborted` JSON event
(`:1538`). Whatever ending the Stop button took for this spot session reached
none of them before the finish handler ran.

**Nothing is broken.** No fallback happens, which is the correct outcome for a
CR30 chart; nothing is lost; the ending is clean. `(unknown error)` is honest —
there was no error to name.

**Why it still matters:** a warning that fires on the normal path cannot be used
to notice the abnormal one. A genuine engine failure on a CR30 chart would print
an identical line, and by then the user has learned to ignore it. That is the
whole cost, and it is the reason to fix it rather than to leave it.

**Do not fix by guessing which ending route it was.** Instrument the endings
first and find which one reaches `_on_finish` with `_user_quit` False —
Stop → the shared ending window offers several answers and they do not all take
the same path. Every wrong answer tonight came from reasoning about a path
instead of watching it.

## B2-2 · Does the instrument follow the chart? — ANSWERED: YES

Proven on screen with both a CR30 and a ColorMunki attached over USB. Full
report and screenshots: `34_instrument_follows_the_chart.md`.

* A chart for another instrument **never scans for a CR30** — zero CR30 lines
  in the log for a ColorMunki chart, an i1 Pro chart, and a chart naming no
  instrument, each started with the CR30 plugged in.
* An i1 Pro chart with a ColorMunki connected **warns before a patch is read**:
  "laid out for: i1Pro… but the instrument connected is: ColorMunki…". The
  owner's fallback wish is already shipped.
* A CR30 chart takes the CR30 path **even through the `.ti1` reopen trap**, and
  stock ArgyllCMS refuses it as designed (M-CR30-STOCK-READER).
* **No case measures with the wrong instrument silently.** That was the one
  that mattered.

### What it left for beta 2 (both cosmetic)

**B2-2a · A chart naming no instrument is described as an i1 Pro.** Argyll's own
log line claims "chart is for GretagMacbeth i1 Pro" — its internal default, not
anything in the file, which was verified to name no instrument. ChromIQ passes
that line through, so the user is told something about their chart that is not
true. Harm: a user could believe their chart is committed to an instrument it is
not, and choose hardware to match.

**B2-2b · A chart naming no instrument gets no load-time announcement.** Charts
that DO name one announce it ("Chart instrument: CR30"); this case is silent, so
there is nothing to correct the false line above.

### Not driven, and worth naming rather than assuming

* the unknown-instrument-name repair window (test-covered, not driven);
* verification and calibration run types (statically they converge on the same
  `set_ti1_path` / `_on_start`, but that is inference, not observation);
* the positive Bluetooth-scan line — proving a scan DOES happen for a CR30 chart
  needs the CR30 unplugged, which was not done while it was attached for other
  work.

## B2-3 · Two places still quote the resume checkbox without its flag

`ui/tabs/tab_profile.py:4049` and `ui/tabs/tab_chart.py:10703` say
"Refine / resume existing measurement" where the widget reads
"…existing measurement **(-r)**" (`tab_measure.py:2199,2664`).
`getting_started.py:142` and `main_actions.py:98,127` already quote it in full,
as do all the CR30 messages now. Left alone deliberately: outside CR30, and the
owner asked to be told before other areas are edited.

## B2-4 · A real check for the dark reference

The current one is circular — proved on hardware, 0.00410 %R against white
paper. Reading the WHITE TILE after the black calibration would show up a dark
reference taken against the wrong surface. It costs the user another step with
the cap and **needs measuring before it is promised**. Recorded in
`unified_measurement_management.md` as a possibility, explicitly not a plan.

## B2-5 · Still open from earlier rounds

* W4 — help cards print with US Letter measurements on Letter paper.
* W6 — no freshness check on the helper in a source checkout (dev-only).
* The in-app Windows driver help: the design is in
  `28_beta1_challenge2.md` §8, with the two live hazards already mitigated
  (the Zadig warning, and `install_winusb` refusing vendor-serial devices).
* The 69 pre-existing Windows test failures, which also fail on `master`.
* §M: six CR30 messages appear in windows while their wording is unapproved.
  Recorded as a discrepancy with a proposed amendment, `Confirmed by: nobody
  yet` — Basti's or Knut's call.
* Bluetooth on Windows, and Linux entirely, have never been run on hardware.
