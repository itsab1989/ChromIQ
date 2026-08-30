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

## B2-6 · The CH340 hazard — DONE, and it was worse than misidentification

The owner: *"we just have to make sure that chromiq does not greenlight any and
every device that is connected via usb this way"*. Two faults, both fixed and
both verified against his instrument:

* **`open_usb()` took `candidates()[0]` and trusted it.** With any other CH340
  device enumerating first, ChromIQ would treat a stranger's board as the
  instrument and write a calibration frame to it. Every candidate is now
  identified before it is accepted; one that does not answer `CR30` is closed
  and left alone, and the error names what was tried and why a CH340 may not be
  an instrument at all.
* **Opening the port asserted DTR and RTS.** `dsrdtr=False` is flow control
  only — pyserial still raises both lines on open. Most maker boards AUTO-RESET
  on DTR; that is how their bootloaders are entered. So merely LOOKING for an
  instrument restarted somebody's Arduino, 3D printer or CNC controller. On a
  printer mid-job that is a ruined print.

Measured on his Mac, 2026-08-30: ChromIQ's own open reported `dtr True, rts
True`. Held low before opening, his CR30 identified normally (`CR30`, V11.3) —
so the safe form costs the instrument nothing. Verified again through the real
`CR30.open_usb()` path.

**Residual, and honest:** finding a CR30 on a serial port still requires WRITING
to it — one `AA 0A` request, the same frame the vendor's own software sends. A
board that mistakes four bytes for a command could still be disturbed. Removing
the reset was the large half; the remaining half needs either a read-only
discriminator (none is known) or a remembered confirmed port, which is worth
building next.

## B2-7 · The BLE axis check cannot tell a CR30 from its own siblings

From the vendor's brochure, found while drafting the manufacturer email: the
**CR10, CR20 and CR30 all share 45/0 geometry and 400–700 nm at 10 nm**. The
Bluetooth confirmation shortlists on the `ffe0` service and confirms on that
axis — so it identifies "a CHNSpec CR-series colorimeter", not "a CR30".

Not necessarily a fault: if the siblings answer the same protocol, reading them
may simply work, and supporting them would be a feature rather than a bug. But
ChromIQ currently claims CR30 specifically, and **nobody has ever seen a CR10 or
CR20**. Say what is true, and put the question to the manufacturer — it is
already question 2 in the draft email.

## B2-8 · `BleTransport.open()` falls back to unconfirmed ffe0 devices

Reported by review: when the confirmed shortlist is empty, `open()` accepts any
device advertising `ffe0` — a service UUID shared with the common HM-10 module
and countless hobby gadgets. Same shape as the CH340 fault on the other
transport, and it should get the same answer: do not accept what has not
identified itself.

## B2-9 · Over Bluetooth, no other owner has magnet protection at all

`TILE_SIGNATURE` is the owner's own unit's constant, and on the only other unit
with captures it is 94x outside tolerance. USB catches a magnet on every unit
via the device's own gate flag; Bluetooth has no equivalent frame, so for
anybody else the first magnet-spoiled reading over Bluetooth is undetectable.

Not fixable without other units. **It must be SAID**, plainly, wherever the
Bluetooth path is documented — a silent gap in a data-integrity guard is the
worst kind. Currently only in the research repo.


## B2-10 · Could a real patch be mistaken for the calibration tile? — MEASURED: no

Basti's question, and a fair one: *"what if one happens to measure a patch that
has the same value as the tile? this could even happen to me myself."* The tile
is a light neutral around 79 %R — not far from paper white — so the worry is
that a near-white patch would be rejected as magnet-spoiled.

Measured against the public corpus (103 readings):

| | worst-band distance to `TILE_SIGNATURE` |
|---|---|
| the guard's tolerance | **0.05 %R, on all 31 bands at once** |
| closest GENUINE reading | **4.686 %R** — 94x the tolerance |
| readings inside the guard | **3 of 103**, all of them the magnet/calibration cases it exists to catch |

The margin is not the real reason it is safe. **Two readings of the same real
surface on his own unit differ by 1.41–6.38 %R on their worst band** — his own
measurement noise is 28x to 128x the tolerance. So even measuring the actual
white tile WITHOUT a magnet cannot match: noise alone pushes it out. This is not
a colour comparison that a similar-looking patch could satisfy; it is a
bit-pattern match against one specific 31-band curve.

**A false positive would need a tolerance loose enough to swallow measurement
noise. At 0.05 it cannot be reached.** Anyone tempted to relax it should read
this entry first.

⚠ **The 4.686 %R figure is the OTHER unit in the corpus** — that is how far its
white reference sits from his constant, and precisely why the guard does not
work on anybody else's device. The risk is inverted from the one Basti feared:
not false alarms for him, but no protection at all for them. See B2-9.
