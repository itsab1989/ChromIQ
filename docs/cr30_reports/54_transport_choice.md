# 54 — Transport choice: does the Bluetooth report need a way out?

**Status:** COMPLETE.
**Date:** 2026-08-30
**Constraint:** the CR30 was never touched. No serial or Bluetooth device was opened.
Every transport claim below comes from reading the shipped source, from running the
real `DeviceReader._open()` against a faked transport, or from this machine's real
`chromiq.log`. The app was not driven on screen — see J.3 for why, and for the one
thing that should be checked on screen before implementing.

## Sections

- [x] A. Verifying report 53's finding myself
- [x] B. What the code actually does today (`_open`, `auto`, the address memory)
- [x] C. Q5 — what can the report cheaply and safely KNOW?
- [x] **D. THE CORRECTION — evidence instead of recall** *(added mid-round; the most
      important section, and it displaces the sketch's centre of gravity)*
- [x] E. Q1 — is a preference the right shape at all?
- [x] F. Q2 — where does it belong? (what Preferences → Measurement already has)
- [x] G. Q3 — how does it fail safely? (what Measure does today on a failed open)
- [x] H. Q4 — interaction with the remembered-address repair
- [x] I. Q6 — wording, drafted against the real UI element names
- [x] J. Q7 — scope, verdict, implementation plan, module map, open questions, rating

## The three findings that would change what you build

1. **ChromIQ has already written down the answer.** Its log records every
   Bluetooth attempt and every transport it opened, dated, at a retained level,
   on all three platforms — so the report can say what happened instead of
   asking. Prototyped and run against this machine's real log (D.7).
2. **`transport="ble"` is Bluetooth ONLY, and both non-`auto` branches throw away
   the good error message.** "Prefer Bluetooth" cannot be built as sketched, and
   as sketched it would make failures worse for the user it is meant to help (E.1).
3. **`chromiq.log` names every Bluetooth device around the user, in the clear** —
   7,597 lines, 16 devices, including a television by model — while the report
   right beside it redacts exactly that. Any "send us your log" step is a privacy
   regression against our own standard (D.4).

---

## A. Verifying report 53's finding myself

**All three parts of the finding hold. One of them is stronger than report 53 said.**

### A.1 There is exactly one `DeviceReader` in the whole UI, and it takes the default

```
$ grep -rn "DeviceReader(" --include="*.py" . | grep -v .venv | grep -v ^./tests
ui/tabs/tab_measure.py:7869:            self._cr30_reader = DeviceReader()
```

One construction site, no arguments. `ui/tabs/tab_measure.py::_open_cr30_bridge`
is the only place in the shipped app that builds one; every other hit is a test.

### A.2 The default is `auto`, and `auto` is USB-first with Bluetooth only in the `except`

`workflow/cr30/measure_bridge.py:587`:

```python
def __init__(self, transport: str = "auto", *, port=None, address=None)
```

`workflow/cr30/measure_bridge.py:840-855`:

```python
def _open(self):
    if self._transport == "usb":
        return self._arm_tile_guard(self._open_usb())
    if self._transport == "ble":
        return self._arm_tile_guard(self._open_ble())
    try:
        return self._arm_tile_guard(self._open_usb())
    except Exception as usb_err:
        log.info("CR30: no USB device (%s); trying Bluetooth", usb_err)
        try:
            return self._arm_tile_guard(self._open_ble())
        except Exception as ble_err:
            raise ConnectionError(_no_device_help(usb_err, ble_err)) from ble_err
```

### A.3 RUN, not read — a faked transport, no device opened

`/…/scratchpad/t54.py` replaces `CR30.open_usb` / `CR30.open_ble` with functions
that record their call and return a stub. Nothing serial or Bluetooth is
touched. Output:

```
default transport of DeviceReader(): auto

USB present, BLE present, auto, address remembered
  -> usb      ['CR30.open_usb(port=None)']
USB present, BLE present, auto, NO address
  -> usb      ['CR30.open_usb(port=None)']
USB absent,  BLE present, auto, address remembered
  -> ble      ['CR30.open_usb(port=None)', "CR30.open_ble(address='REMEMBERED-ADDR')", 'identify(ble)']
USB absent,  BLE absent,  auto
  -> RAISED ConnectionError   ['CR30.open_usb(port=None)', 'CR30.open_ble(address=None)']
USB present, transport='ble'
  -> ble      ["CR30.open_ble(address='REMEMBERED-ADDR')", 'identify(ble)']
```

Line 1 is the finding: **with a working USB instrument, `CR30.open_ble` is
never called, and the remembered address is never read.** A user in that state
has never had ChromIQ attempt Bluetooth, whatever they believe. Confirmed.

### A.4 The Windows owner's "the computer says NOOO" — I can support the doubt but not settle it

What I can show is only this: there is no ChromIQ control that asks for
Bluetooth, so if his USB worked at that moment, ChromIQ did not try. What I
cannot show from here is which window he was looking at. **Do not write "he was
in Windows' Add-a-device dialog" into any user-facing text or any spec.** It is
an inference about a person, and §"Only CONFIRMED behaviour" applies to what we
claim about users as much as to what we claim about the app. The report should
describe *this computer's* state and let him recognise it.

### A.5 What report 53 did NOT say, and it matters

There is a second remembered key, and it is the better evidence:

`workflow/cr30/measure_bridge.py:709` — `REMEMBERED_PORT_KEY = "cr30_usb_port"`,
written on every successful USB open (both the fast path and the search), only
after `identify()` has confirmed a CR30 answered.

So `cr30_usb_port` non-empty is **proof that a CR30 has answered over USB on
this computer at some point** — not merely that a cable is in right now. That is
the single cheapest, strongest fact for "your instrument has been working over
the cable, which is why Bluetooth was never reached". The sketch's detection
list (Q5) does not mention it.

---

## B. What the code actually does today

| Thing | Where | Value |
|---|---|---|
| the only reader construction | `ui/tabs/tab_measure.py:7869` | `DeviceReader()` |
| default transport | `workflow/cr30/measure_bridge.py:587` | `"auto"` |
| USB-first order | `measure_bridge.py:845-855` | `_open_usb()`, BLE only in `except` |
| remembered BLE address | `measure_bridge.py:624` | key `cr30_ble_address` |
| remembered USB port | `measure_bridge.py:709` | key `cr30_usb_port` |
| who writes the BLE address | `_remember_address` (on a successful BLE open) **and** `ui/main_window.py:1946` (the repair) | — |
| the repair offer | `ui/main_window.py:1888 _offer_cr30_bluetooth_repair` | 3 buttons |
| the report tool | `ui/tools_popup.py:79`, Tools ▸ **Instruments** ▸ “CR30 Bluetooth report (for when it will not connect)” | — |
| what triggers the CR30 path at all | `ui/tabs/tab_measure.py:5636 _chart_is_cr30()` — the chart's `TARGET_INSTRUMENT "CR30"` | not a user instrument picker |

**Neither `cr30_ble_address` nor `cr30_usb_port` is in `core/settings.py::DEFAULTS`.**
`grep -n cr30 core/settings.py` returns nothing. They are written through
`AppSettings.set` and read with an explicit `""` fallback. That is fine for
`get`, and it has one consequence nobody has written down — see G.3.

**The instrument is opened LAZILY, and the first open is the calibration.**
`DeviceReader._open()` is called from `calibrate()` (`measure_bridge.py:1080`),
from `__call__` (`:869`), from `learn_tile` (`:953`) and from `read_zero`
(`:1033`). In a normal Start the calibration gets there first —
`ui/tabs/tab_measure.py:5834` runs `_run_cr30_calibration()` before the helper
starts, and that calls `_open_cr30_bridge()` then `reader.calibrate()`. This is
the load-bearing fact for Q3 and the sketch does not use it.

---

## C. Q5 — what can the report cheaply and safely KNOW?

Five candidate signals. Two are free, one is cheap and safe but says less than
it looks like it says, one is **not safe**, and one **does not exist**.

### C.1 Is a Bluetooth address remembered — FREE, exact

`AppSettings().get("cr30_ble_address", "")`. One QSettings read. No device.

### C.2 Has a CR30 ever answered over USB on this computer — FREE, and the best signal there is

`AppSettings().get("cr30_usb_port", "")`. Written only after `identify()`
confirmed a CR30 (`measure_bridge.py:761` and `:777`). Non-empty means: this
computer has had a real CR30 answer over the cable. That is exactly the
premise the report wants to state, and it costs one QSettings read.

It is a *hint*, not a live fact — the instrument may be unplugged now. The
report must word it in the past tense.

### C.3 Is a CH340-class device attached right now — CHEAP AND SAFE, but it is not "a CR30"

`workflow.cr30.discovery.candidates()` → `serial.tools.list_ports.comports()`.
**Enumeration only: no port is opened and no byte is written.** Measured just
now on this Mac (instrument off, per the constraint):

```
candidates(only_ch34x=True)  -> []                    in 7.1 ms
candidates(only_ch34x=False) -> 2 serial ports        in 0.3 ms
    /dev/cu.debug-console
    /dev/cu.Bluetooth-Incoming-Port
```

7 ms. Safe to run in the report, and safe to run on every Start.

⚠ **But `1a86:7523` is not a CR30.** `workflow/cr30/discovery.py:6-15` and
`device.py:123` both say so at length: it is the generic CH340 bridge, also
inside Arduinos, 3D printers, CNC controllers and laser cutters. So this signal
answers "is something of the kind your instrument uses plugged in", and the
report's wording must not upgrade it to "your instrument is plugged in". Getting
that wrong is how the report would tell a user with an Arduino that their CR30
is on the cable.

### C.4 Is a CR30 attached right now — NOT SAFE from inside the report

The only honest test is asking. `CR30.open_usb()` with no port opens **every**
CH340 candidate in turn and sends each one an `AA 0A` identify frame
(`device.py:139-170`). The frame is the same one the vendor software sends and
`SerialTransport.open` holds DTR/RTS low so looking cannot reset a board — but
it is still a write to a stranger's device, performed by a *Bluetooth* report
the user did not run for that.

There is a narrower version: if `cr30_usb_port` is remembered **and** that exact
path is in `candidates()`, open only that one and identify it. One frame, to a
port that has already answered as a CR30. Even that has a cost the report should
not pay: a serial port is **exclusive on Windows** (`measure_bridge.py:768`
exists because of it), and the report's whole audience is a Windows user with a
connection problem.

**Recommendation: the report does not open USB. It reports C.2 and C.3 and says
which of them it is saying.**

### C.5 Has a Bluetooth session ever SUCCEEDED — this does not exist, and the sketch assumes it does

`cr30_ble_address` has **two** writers:

* `DeviceReader._remember_address` — after a successful Bluetooth open;
* `ui/main_window.py:1946` — the repair offer, from the report's `confirmed` list.

Both mean "a CR30 answered over Bluetooth on this host once". Neither means "a
measurement ran over Bluetooth", and after the repair ships the second will be
the common one. **The report cannot distinguish them and must not try.**

If we ever want "Bluetooth has worked here", it needs a new key written at the
one place that knows — and I would not add it for this.

The report does not need it anyway: **its own stage 3 answers the live question
better than any stored flag**, because `ble.discover(verify=True)` has just
asked. `Report.confirmed` is that answer.

### C.6 Summary

| Signal | Cost | Safe? | Says exactly |
|---|---|---|---|
| `cr30_ble_address` set | 1 settings read | yes | a CR30 answered over BT here once, or the repair was accepted |
| `cr30_usb_port` set | 1 settings read | yes | **a CR30 answered over the cable here once** |
| `candidates()` non-empty | 7 ms | yes | a CH340-class device is attached — maybe not an instrument |
| a CR30 is on USB right now | seconds | **no** — writes a frame to strangers | — |
| Bluetooth has ever worked | — | — | **not knowable; no such record exists** |

---

## D. THE CORRECTION — evidence instead of recall

Mid-round the owner said: *"i think i told him to just start a measurement
without a cable connected. but don't know if he really did this"*.

That is decisive, and it changes the shape of the answer. If he unplugged and
pressed Start, `_open_usb` raised, `_open()` fell through, and **ChromIQ really
did attempt Bluetooth and fail** — which puts the discovery theories back on the
table. If he did not, A.3 stands. Nobody knows which, and asking him is asking
him to remember.

**Do not ship a diagnostic that asks the user what they did.** Evidence, or
nothing.

### D.1 — the answer already exists, in ChromIQ's own log, dated

`workflow/cr30/measure_bridge.py:851` and `:883/:954/:1081` already record every
one of these, at INFO:

```
CR30: no USB device (%s); trying Bluetooth     ← a Bluetooth attempt, with the USB reason
CR30: opened over usb | ble                    ← the outcome, naming the transport
CR30 BLE: found in %.2f s, connected in %.2f s, notifications in %.2f s   (ble.py:261)
CR30: the device at the remembered Bluetooth address did not answer …    (measure_bridge.py:697)
CR30: %s did not answer as a CR30 (%s); looking at the other serial devices (:774)
```

`core/logger.py:47-58`: the root logger is at DEBUG and the
`RotatingFileHandler` is at DEBUG, so **all of these are retained**. The file is
`log_dir()/chromiq.log` (`core/platform_paths.py:122`):

* Windows — `%LOCALAPPDATA%\ChromIQ\Logs\chromiq.log`
* macOS — `~/Library/Logs/ChromIQ/chromiq.log`
* Linux — `$XDG_STATE_HOME/ChromIQ/logs/chromiq.log`

`maxBytes=5_000_000, backupCount=5` — six files, ~30 MB of history.

**I read this machine's own log to prove the summary is producible.** Extracted
across all six retained files, with nothing added to the app:

```
25   "no USB device …; trying Bluetooth"     — Bluetooth attempts
20   "opened over ble"                       — Bluetooth opens that succeeded
     "opened over usb"                       — cable opens, interleaved and dated

2026-08-30 09:41:50  CR30: /dev/cu.usbserial-10 did not answer as a CR30 …
2026-08-30 09:41:50  CR30: no USB device (no CH34x serial device found); trying Bluetooth
2026-08-30 09:41:51  CR30 BLE: found in 0.04 s, connected in 1.38 s, notifications in …
2026-08-30 09:41:53  CR30: opened over ble
```

That is exactly the sentence the coordinator asked for — *"Bluetooth has been
attempted N times, the last on `<date>`, and this is what happened"* — and it is
already on disk on every machine that has run a CR30 measurement, **including
for attempts made before this feature is written.** No new state, retrospective,
free.

And it can already answer the question in front of us. For the Windows owner,
`grep "trying Bluetooth"` over his six files is the whole of it:

* lines present → he did unplug, ChromIQ did try, and the discovery theories live;
* no lines at all → ChromIQ never attempted Bluetooth on that machine.

### D.2 — one line is missing, and it is the one that matters most

`_open()`'s final failure is **not logged**:

```python
except Exception as ble_err:
    raise ConnectionError(_no_device_help(usb_err, ble_err)) from ble_err
```

So a failed Bluetooth attempt is visible only as an *absence* — a "trying
Bluetooth" with no "opened over ble" after it. I can see that in this machine's
own log (25 attempts, 20 opens: five failures, inferable only by subtraction,
and one of them only because a second attempt 39 s later succeeded).

Inference by absence is exactly the recall problem moved into software. **Add
one `log.warning` there.** It is one line, it changes no behaviour, it makes
every future failure explicit and self-describing, and it is the highest
value-per-byte change in this whole report. (It does not help the attempt he may
already have made — D.1 does that, as far as it can.)

### D.3 — how long the log actually survives, measured, and the two things eating it

On this machine, six files, 170,000 lines, **28 Aug 10:09 → 30 Aug 19:10 — under
three days.** That is a developer's workload, but the reason it is short is not
the workload:

| logger | lines | share |
|---|---|---|
| `ui.tooltip_button` — `TooltipButton created: <title>` | **99,751** | **58.7 %** |
| `bleak.backends.corebluetooth.CentralManagerDelegate` | 7,597 "Discovered device" | 4.5 % |
| `core.argyll_runner` | ~12,600 | 7.4 % |

`ui/tooltip_button.py:78` logs a DEBUG line every time a `TooltipButton` is
constructed — every settings-dialog open, every tab rebuild. **Nearly six of
every ten lines in the user's 30 MB diagnostic budget are that one line**, and it
has never told anyone anything. `core/logger.py:66-72` already documents this
exact failure mode for Pillow ("that noise can evict the very traceback the log
was sent for") and fixed it with `_NOISY_LIBRARIES` — this is the same fault in
ChromIQ's own code. **Removing or gating that one `log.debug` roughly triples the
retrospective reach of every user's log**, which is the reach this whole design
depends on.

### D.4 — ⚠ THE LOG IS NOT SAFE TO SEND, AND THE REPORT IS

`workflow/cr30/bluetooth_report.py:27-30` redacts the names of non-candidate
devices with a comment saying *"a scan is a list of what is switched on around
somebody … and this file is written to be sent to a stranger."*

`chromiq.log` has no such protection. bleak logs every advertisement it sees, by
name, at DEBUG — and the file handler keeps DEBUG. Measured on this machine's
retained files: **7,597 lines naming 16 distinct nearby devices in the clear**,
including the owner's television by make and model.

So: **any design step that reads "ask the user to send chromiq.log" is a privacy
regression against the standard the report already holds itself to.** It also
undoes the redaction the report performs on the very same scan.

The way out is the same move that makes the design good anyway: **the report
reads the log itself, extracts only ChromIQ's own `workflow.cr30` lines, and
writes the summary into the report file.** Those lines contain a port path, a
Bluetooth address, timings and an instrument model — no third-party device names
— and the report is already the artefact we ask people to send. One file, one
redaction policy, one thing to explain.

(Separately, and not part of this design: `bleak` belongs in
`core/logger.py::_NOISY_LIBRARIES`. It is 4.5 % of the log and it is the part
that names the neighbours. I would raise that as its own change — it is one
tuple entry, but it is a source edit outside `tests/` and `scripts/` and it
narrows what a genuine BLE bug report contains, so it is the owner's call.)

### D.5 — the three options, ranked

| | answers the past? | reliable? | new state? | cost |
|---|---|---|---|---|
| **1. Read the existing log** | **YES — including before the feature existed** | as good as the log's reach (D.3) | none | low; pure reading |
| 2. Persist an outcome record | no — starts empty | high, going forward | yes, a new key to maintain | low |
| 3. Attempt it, now, in the report | no — answers *today*, not *that night* | **highest, it is not evidence but a fact** | none | ~20 s, reuses `_open()` |

**Ranking: 1, then 3, then 2. Ship 1 and 3. Do not ship 2.**

* **(1) is the only one that can answer the question actually being asked.** It
  is retrospective, and both of the others are not. It is also free — the lines
  exist, at the right level, dated, on all three platforms.
* **(3) is the most honest evidence there is**, and it is nearly free because
  the report already does most of it. Stage 3 (`ble.discover(verify=True)`)
  scans, connects, subscribes and reads the axis — but it does **not** exercise
  `DeviceReader._open_ble`, so it never tests the remembered-address fast path,
  never calls `dev.identify()`, and never runs the code that a *stale* address
  breaks. A stage 4 that calls `DeviceReader(transport="ble")._open()` and closes
  it tests the exact thing the Measure tab does. Two cautions, both real:
  * a successful `_open_ble` calls `_remember_address` (`measure_bridge.py:645`)
    — **stage 4 would silently perform the repair the next window politely asks
    permission for.** Either read the key before and restore it, or move stage 4
    to *after* `_offer_cr30_bluetooth_repair`. This must be decided, not
    stumbled into.
  * it must `close()` in a `finally`. A held peripheral stops advertising, so a
    leaked handle makes the user's next real attempt fail — the exact fault
    `_open_ble` already guards against at `:687`.
* **(2) earns nothing that (1) does not already give**, and it is the only one
  of the three that adds state to maintain, to migrate, and to reset. Its one
  advantage over (1) — surviving log rotation — is better bought by fixing D.3,
  which costs one deleted `log.debug` and helps every other diagnostic too.
  **Recommend: do not build it.**

### D.6 — what the combination can and cannot answer

| Question | 1 (log) | 3 (attempt now) |
|---|---|---|
| Did ChromIQ ever try Bluetooth on this computer? | **yes, with dates** | no |
| Did that attempt fail, and where? | attempt yes; *why* only after D.2 ships | — |
| Has the cable ever worked here? | **yes** (`opened over usb`, dated) | no |
| Does Bluetooth work **right now**, through the Measure tab's own code? | no | **yes** |
| Is the remembered address stale? | no | **yes** |
| What did he do that night? | if his log still reaches back — otherwise **honestly, "no record"** | no |

The last row is the one to be truthful about. If his log has rotated past it,
the report must say **"ChromIQ has no record of a Bluetooth attempt in the log
it still keeps"** — which is *not* "he never tried". Writing that distinction
into the text is the whole difference between a diagnostic and a rumour.

### D.7 — the log summary, PROTOTYPED AND RUN against this machine's real log

Not a proposal on paper. `/…/scratchpad/logsum.py` implements the summary and
was run against `~/Library/Logs/ChromIQ/chromiq.log{,.1..5}`. Verbatim output:

```
4. What ChromIQ's own record says has happened here before
--------------------------------------------------------------
ChromIQ's record reaches back to 2026-08-28 10:09:22 (it keeps the last
30 MB and then writes over the oldest, so anything before that is
simply no longer kept — not evidence that nothing happened).

Bluetooth attempted : 25   (last 2026-08-30 19:10:38)
Bluetooth succeeded : 20   (last 2026-08-30 09:41:53)
Cable succeeded     : 21   (last 2026-08-30 10:10:40)

The last few entries, most recent last:
  2026-08-30 06:18:19  opened over ble
  2026-08-30 08:53:08  opened over usb
  2026-08-30 09:41:50  /dev/cu.usbserial-10 did not answer as a CR30 ([Errno 2] …
  2026-08-30 09:41:50  no USB device (no CH34x serial device found); trying Bluetooth
  2026-08-30 09:41:51  found in 0.04 s, connected in 1.38 s, notifications in 0.09 s
  2026-08-30 09:41:53  opened over ble
  2026-08-30 10:00:46  opened over usb
  2026-08-30 10:10:40  opened over usb
  2026-08-30 19:10:38  no USB device (no CH34x serial device found); trying Bluetooth
  2026-08-30 19:10:38  no USB device (no CH34x serial device found); trying Bluetooth
```

Sixty lines of parsing, no new state, and it answers the question this round
started with.

**Two honest corrections to my own numbers, and both are findings.**

1. **The last two attempts are MINE.** My fake-transport run (A.3) called the
   real `_open()`, which wrote two real "trying Bluetooth" lines at 19:10:38.
   The genuine history is **23 attempts, 20 successes**. So the log cannot tell a
   test harness from a user — a limit worth knowing, and a reason the *text*
   should present counts as "what ChromIQ recorded", never as "what you did".
2. **Those two lines are also a live demonstration of D.2.** Two attempts, no
   "opened over ble" after either — a Bluetooth failure that exists in the log
   only as an absence. That is precisely the sentence the missing `log.warning`
   would have written, and it is why D.2 is the highest-value line in this
   report.

---

## E. Q1 — is a preference the right shape at all?

**Partly. The sketch's (b) is the second-best half of the answer, and as drawn
it cannot be built. The first-best half is not a preference at all.**

### E.1 Two provable defects in the sketch's option set

**(i) "Prefer Bluetooth" cannot be `transport="ble"`. `"ble"` means Bluetooth
ONLY.** From `_open()` (quoted at A.2) and from the run at A.3 case 5: the
`"usb"` and `"ble"` branches `return` immediately with no fallback. So a user who
picks "Prefer Bluetooth" with a working cable plugged in, whose instrument has
gone to sleep, waits out a full scan (measured 15.42 s find, `measure_bridge.py`
docstring) and is then refused — with a working cable in the socket. That is
strictly worse than today, and it happens to the user who was already confused.

To make "prefer" honest, `_open()` needs a fourth branch. That is an edit to the
one function the brief says be conservative about — but it can be **purely
additive**: a new mode string, the existing `"auto"`, `"usb"`, `"ble"` bodies
untouched. The single Bluetooth user we have is on `"auto"` and cannot be
reached by a branch that tests for a string nothing sets today.

**(ii) Every non-`auto` transport silently loses the good error message.**
`_no_device_help(usb_err, ble_err)` — the two-transport explanation with the
power-cycle advice, the dialout hint, the CH34x driver hint and the "the phone
app is holding it" line — is built **only in the `auto` branch's `except`**. The
`"usb"` and `"ble"` branches raise the raw underlying exception. So the very
setting sold as "a way out" makes the failure message worse, and it makes it
worse for exactly the person who set it because they were already stuck. Any
transport preference MUST come with per-transport help text or it is a net loss.

Neither defect is visible from `__init__`'s signature, which is what "the
machinery already exists" was read off. The machinery exists; the *behaviour* the
labels promise does not.

### E.2 The stronger answer: the first fix is VISIBILITY, not choice

The brief's own framing gives it away: *"why is my instrument connected by cable
when I asked for wireless"*. Look at where the asking happened. There is no
control in ChromIQ to ask with (A.1) — so the user asked **in the operating
system's Bluetooth pane**, paired it there, and formed the reasonable belief that
the instrument is now a wireless instrument. ChromIQ then uses the cable and says
nothing at all about it.

**The mismatch is not that ChromIQ chose wrongly. It is that ChromIQ never said
what it chose.** `measure_bridge.py:883` already knows, at the exact moment:

```python
log.info("CR30: opened over %s", self._dev.kind)
```

That fact reaches a log file the user has never opened. Put it on screen and the
confusion has nowhere left to live — and it costs no new setting, no new state,
and no new failure mode.

This also matters because **`auto`'s preference for the cable is correct, and a
beginner choosing otherwise is choosing worse.** From this repo's own measured
numbers: a Bluetooth open costs a 15.42 s scan plus 2.33 s connect
(`measure_bridge._open_ble` docstring) or, with an address, 0.04 s + 1.38 s
(this machine's log, D.7); a USB open is a port open and one identify frame. And
Bluetooth has an exclusivity failure the cable does not — a merely *connected*
phone app takes the button press silently (`tab_measure.py:5987`). For almost
everybody the cable is the right answer, and the project's rule that the
beginner's model rules the UI is a rule about **making the UI match the model**,
not about handing a beginner a switch that punishes them for a misunderstanding.

So: **say which transport was used, always. Offer the choice second, for the
minority who genuinely need it.**

### E.3 The alternatives in the brief, judged

| Alternative | Verdict | Why — from the code or the spec |
|---|---|---|
| **a per-target setting** | **NO — ruled out by a binding spec** | `docs/design/per_target_settings.md` §1.1: *"everything that describes your setup stays global"*, and the table lists "Preferences → everything \| your setup". A transport describes the computer and the link, not the chart. It would also contradict `cr30_ble_address` / `cr30_usb_port`, which are already per-host. |
| **a choice at Start when both are available** | **NO, and it cannot be built** | Knowing "both are available" needs a USB identify (C.4 — writes a frame to strangers, seconds) **and** a BLE scan (~15 s). The dialog cannot be shown without paying the whole cost it exists to save. It is also a modal on every Start, against which `tab_measure.py:7265` already rules for the black-calibration tick: *"a remembered tick would turn 'occasionally, on purpose' into a second window … on every Start of this target for ever."* |
| **"remember what worked last time", invisible** | **NO** | It already exists in the only form that is safe: `cr30_usb_port` and `cr30_ble_address` remember the *endpoint*, and both are re-identified before being trusted. Remembering the *transport* would make behaviour depend on invisible history — the precise fault the brief names in `auto`. |
| **make `auto` try Bluetooth when USB fails and an address is remembered** | **NO — it is already unconditional** | A.3 case 3: `auto` reaches `_open_ble` on **every** USB failure, address or not. Nothing to change. |

### E.4 What I would ship instead

1. **Always say which transport was used.** No setting, no state.
2. **A preference, with honest labels that match `_open()`'s actual shapes:**
   * **Automatic — try the cable first, then Bluetooth** *(recommended; today's behaviour)*
   * **Try Bluetooth first, then the cable**
   * **Only ever use the cable**

   Three, not the sketch's three. "Prefer Bluetooth" becomes "Bluetooth first,
   **then the cable**" — which is both what a beginner means by "prefer" and
   what fails safely (G). "Only ever use the cable" earns its place on measured
   grounds: a user whose unit has no Bluetooth (a case the report itself already
   names) pays a full ~15 s scan on every failed USB open, for ever.

   I deliberately do **not** offer "Bluetooth only". It buys one thing — never
   writing an identify frame to a stranger's CH340 — and the remembered-port
   fast path (`measure_bridge.py:747`) already reduces that to essentially the
   first run. Flagged as an open question rather than built.

---

## F. Q2 — where it belongs

**Three places, three different jobs, one stored value.** Checked against what
is already on each surface, so nothing duplicates and nothing contradicts.

### F.1 What Preferences → Measurement already contains

`ui/dialogs/settings_dialog.py:1602 _build_measurement_tab`, in order:

1. `self._measure_engine_block` — the reading-engine checkboxes, moved here from
   Beta on 2026-08-13 (`:1622`, `:797`);
2. the pace introduction and “Warn me when I read a strip too fast” (`:1646`);
3. a **“Per instrument”** group box (`:1685`) with a row per instrument —
   including **`"cr30": tr("CR30 (patch by patch)")`** at `:1709`;
4. “Close to the limit” (`:1801`).

So the tab **already has a CR30 row**, and it is about reading *pace*
(`core/measure_pace.py:343,364` — 100 Hz, no strips, shown as “N/A”). A
connection setting neither duplicates it nor contradicts it; it is a different
property of the same instrument and belongs in its own group box beside it.

There is **no CR30 connection setting anywhere in Preferences today** —
`grep -n "cr30\|CR30" ui/dialogs/settings_dialog.py` returns only the pace row,
the margin-threshold instrument list (`:1518`), the notes-band instrument list
(`:3655`) and the WinUSB driver warnings (`:4125-4231`). Nothing to collide with.

### F.2 The three surfaces

| Surface | What goes there | Why there |
|---|---|---|
| **Measure tab** (the run log, where the session narrates itself) | **the statement of which transport was actually used**, on every open | This is where the confusion happens and where the user is already reading. `measure_bridge.py:883` knows it at that instant. No setting, no state. |
| **Preferences → Measurement**, a new group box below “Per instrument” | **the preference itself** | `docs/design/per_target_settings.md` §1.1 puts “your setup” in Preferences, and the neighbouring CR30 pace row establishes the pattern. It is a thing you set once. |
| **Tools ▸ Instruments ▸ “CR30 Bluetooth report (for when it will not connect)”** | **the offer**, when the report has grounds for it | The report is what a stuck user runs. `ui/main_window.py:1888` already proves the shape works — explicit, reversible, still asks for the report. The offer writes the *same key*, so there is one value and one meaning. |

**Not the Measure tab as a control.** The Measure tab has no instrument picker
to hang it on: the CR30 path is chosen by the *chart*, not the user
(`tab_measure.py:5636 _chart_is_cr30()` reads `TARGET_INSTRUMENT "CR30"` from the
.ti2). Putting a transport combo there would be the first control on that tab
that applies only to some charts, and it would be invisible for every other
instrument.

**The one rule this must obey:** the offer and Preferences must never show
different values. They will not, because the settings dialog reads on open — but
if the offer ever changes the key while the dialog is open, the dialog's Save
would write back the stale value. `_offer_cr30_bluetooth_repair` runs from the
main window and the settings dialog is modal, so this cannot happen today; note
it so it stays true.

---

## G. Q3 — how it fails safely

**Today's answer is already good, and it is better than the brief assumes. The
danger the brief names — "stranded mid-chart" — is not the normal failure.**

### G.1 The instrument is opened at the CALIBRATION, before a single patch

`DeviceReader` opens lazily. Every caller of `_open()`:
`calibrate()` (`:1080`), `__call__` (`:869`), `learn_tile` (`:953`),
`read_zero` (`:1033`). In a normal Start the calibration gets there first —
`tab_measure.py:5834` runs `_run_cr30_calibration()` **before** the helper
starts, and that calls `_open_cr30_bridge()` and then `reader.calibrate()`.

So a transport that cannot open fails at the calibration window
(`tab_measure.py:7344`):

> **The calibration did not go through.**
> ChromIQ asked your CR30 to calibrate and it did not answer. Check that the
> instrument is switched on and still connected — over Bluetooth, pressing its
> own button once wakes it — then start the measurement again. Nothing has been
> changed, and any measurement this run already had is untouched.
> What went wrong: `<_plain_instrument_error(...)>`

and `_run_cr30_calibration` returns False, so `tab_measure.py:5846` logs
*"Measurement not started: the instrument was not calibrated. Nothing has been
changed."* and **the measurement never starts.** Nothing is stranded. That is
already a good answer.

### G.2 The one route that IS mid-chart, and it is narrow

`tab_measure.py:5834` guards on `params.external_values and not
params.disable_initial_cal`. In **Manual** mode with “Skip initial calibration”
ticked, no calibration runs, so the first `_open()` happens at the first patch
read — where it becomes `DeviceLost("the instrument could not be opened (…)")`
(`measure_bridge.py:881`) and surfaces as **M-CR30-INSTRUMENT-GONE** with
“Carry on measuring” / “Stop the measurement”
(`tab_measure.py:8173`). Nothing is lost — the helper writes after every patch —
and “Carry on measuring” re-arms and reopens (`_carry_on_after_the_instrument_went`).
In Guided, `disable_initial_cal` is hard-coded False, so this route does not
exist there at all.

### G.3 So the answer to "fall back, refuse, or ask" is: **the existing path, plus two things it cannot say today**

Do not invent a new fallback. Two gaps, both provable:

**(a) The message never mentions the setting.** M-CR30-INSTRUMENT-GONE lists “the
USB cable came out”, “over Bluetooth, out of range”, “the phone app holds it” —
and the calibration window says “switched on and still connected”. Neither can
say *"you have asked ChromIQ to try Bluetooth first, and it could not."* A user
who set the preference weeks ago and forgot has no route back to it from the
failure. **Any transport preference must add a sentence to the failure text
naming the preference and where to change it** — and it must only appear when
the preference is not Automatic.

**(b) The failure text degrades to a raw library error.** E.1(ii): the `"usb"`
and `"ble"` branches never build `_no_device_help`. `_plain_instrument_error`
(`tab_measure.py:7429`) rescues two bleak strings and passes everything else
through. So "Only ever use the cable" on a machine with no CR30 attached yields
`no CH34x serial device found` where `auto` would have produced four paragraphs
of advice. **Fix this in the same change or do not ship the preference.**

**And this is why "Bluetooth first, then the cable" beats "Bluetooth only".** The
fail-safe is free: it is a fallback that already exists in the other direction.
With E.4(1) — always saying which transport was used — the fallback is also not
silent: the user sees *"Bluetooth did not answer, so ChromIQ used the cable"*,
which is the whole of "fall back with a message" and needs no extra window.

Refusing to start, or asking mid-flight, are both worse: refusing punishes a
user for a setting they may not remember making, and asking puts a modal between
an operator and a chart they are standing over.

---

## H. Q4 — interaction with the repair we ship

**Complementary, orthogonal, and — this is the finding — the preference is what
makes the repair reach the person it is offered to.**

### H.1 They answer different questions

* the remembered address answers **which device**, once we are on Bluetooth
  (it skips discovery: `ble.py:192`, `target = self.address`);
* a transport preference answers **whether we get to Bluetooth at all**.

Not redundant, not contradictory.

### H.2 ⚠ For a user whose cable works, the repair we ship is INERT

A.3 case 1, run: with USB present, `_open_ble` is never called and
`cr30_ble_address` is never read. So the repair offer —

> *"ChromIQ can skip it by going straight to this instrument in future"*

promises a future that never arrives for anyone whose cable works. The repair
helps exactly the users whose USB already fails, which is the smaller half of the
audience, and the window gives no hint of the condition.

This is the strongest argument in the whole round **for** the sketch's (b): the
preference is not a nicety beside the repair, it is the thing that lets the
repair mean anything to a cable user. It should be said plainly to the owner.

### H.3 A preference of Bluetooth plus a stale address — what the user sees

Traced through the code, worst case, instrument absent:

| step | code | cost |
|---|---|---|
| connect to the stale address | `ble.py:192,248` — `BleakClient(target, timeout=20.0)` | up to **20 s** |
| caught, closed, logged | `measure_bridge.py:688-698` | — |
| full discovery | `ble.py:215` `discover(timeout=min(20,12))` | up to **12 s** |
| nothing confirmed → one retry | `ble.py:221` | up to **12 s** |
| then, and only then, the cable | new "Bluetooth first" branch | — |

**Up to ~44 seconds before the cable is tried, with nothing on screen.** They are
not stranded — the stale-address fallback is deliberate and commented
(`measure_bridge.py:679-687`), and it works — but `ble.py:253-259` already
records that this wait has no feedback: *"the first connection of a session is
made when he presses Calibrate, and nothing on screen says anything is
happening."*

**So "Try Bluetooth first" must not ship without something on screen during the
wait.** Otherwise we would be shipping a 44-second freeze that the user asked for
and cannot see — and they would report it as a hang, correctly.

### H.4 Two collisions the preference creates, both fixable, both easy to miss

**(a) The repair window's own words become half-false.**
`ui/main_window.py:1927-1928` currently says:

> *"You can undo it at any time: run this report again and choose "Search
> normally". That is the whole of it — **there is nothing to hunt for in
> Preferences**."*

Add a CR30 connection group to Preferences → Measurement and that last clause
stops being true. It must be reworded in the same change. This is exactly the
brief's item 6 — text that describes a UI that no longer exists.

**(b) Preferences → Restore Defaults silently undoes the repair.**
`core/settings.py:1190 reset_to_defaults()` does `self._qs.clear()` and restores
only `manual_presets`. Neither `cr30_ble_address` nor `cr30_usb_port` is in
`DEFAULTS` (B), so both are simply erased — the repair is undone and nobody is
told. That is true **today**, before any of this work. It is not urgent (the
address is a hint and re-discovery recovers it) but it is a second undo route the
repair's text does not mention, and the transport preference will inherit the
same behaviour. For a *preference*, resetting is correct. Worth one sentence to
the owner rather than a change.

---

## I. Q6 — wording

**Two registers, and the codebase already sets the rule.** `bluetooth_report.py`
contains **no `tr()` calls at all** — the report body is deliberately English,
because it is written to be read by us. Every *window* in
`ui/main_window.py::_run_cr30_bluetooth_report` is wrapped in `tr()`. Drafts
below follow that split, and none of them uses Markdown
(`feedback_no_markdown_in_message_strings`).

Every UI element named below is marked ✅ (exists today) or 🆕 (must ship in the
same version, or the sentence must not). **Nothing here names a control that
would not exist.**

### I.1 The report — a new stage 4, "what has happened here before" (English, in the file)

Placed after stage 3, so the live answer comes first and the history explains it.

```
4. What ChromIQ's own record says has happened here before
--------------------------------------------------------------
ChromIQ keeps a note of every time it opened your instrument, and how.
Nothing below was typed by anyone or remembered by anyone — it is what
the program wrote down at the time.

ChromIQ's record reaches back to 2026-08-28 10:09.
It keeps the most recent thirty megabytes and then writes over the
oldest, so anything earlier is simply no longer kept. That is not the
same as nothing having happened.

  It opened your CR30 over the cable            21 times, last on 30 Aug 10:10
  It went on to try Bluetooth                   23 times, last on 30 Aug 19:10
  Bluetooth worked                              20 times, last on 30 Aug 09:41

ChromIQ always tries the cable first and only turns to Bluetooth when
no instrument answers on the cable. So a low number on the middle line
usually means the cable was working, not that Bluetooth was refused.
```

and the two other endings, whole:

```
  ChromIQ has never got as far as trying Bluetooth on this computer in
  the time it still keeps a record of. That is worth knowing: it means
  that whatever happened when Bluetooth would not connect, it did not
  happen inside ChromIQ — ChromIQ was using the cable, and never looked.
```

```
  ChromIQ has tried Bluetooth here and never once got through. That is
  the most useful line in this report, and it is the case we most want
  to see, so please do send it.
```

Then, always, the last few entries verbatim with their timestamps.

**Why it is worded that way, against the brief's rules:**

* it never asks the reader what they did, and never asks them to remember;
* “ChromIQ has no record” is stated as *no record*, never as *it did not
  happen* — the distinction D.6 turns on;
* plural is explicit per line (`1 time` / `N times`), never `time(s)`
  (CLAUDE.md, i18n rules) — even though this text is English-only, the rule is
  about clarity, not translation;
* it says the cable is tried first and why that is normal, without saying either
  transport is better.

### I.2 The report — the two facts about this computer (English, in the file)

Folded into stage 4, only when true, and each one saying exactly what it knows
and no more (C.6):

```
  A CR30 has answered on the cable on this computer before, so the cable
  works here. That is the ordinary reason Bluetooth is never reached.
```

```
  Something is plugged in now that uses the same kind of USB connection
  as your instrument. ChromIQ cannot tell from here whether it IS your
  instrument — that chip is also used by 3D printers and hobby boards —
  so this is only worth mentioning, not a conclusion.
```

```
  ChromIQ has a Bluetooth address remembered for a CR30 on this computer,
  so it will go straight to that instrument instead of searching.
```

The middle one is the wording that keeps C.3 honest. Saying "your instrument is
plugged in" there would be a claim the code cannot make.

### I.3 The offer, when the report has grounds (a window, `tr()`)

Shown after `_offer_cr30_bluetooth_repair`, only when the report **confirmed** an
instrument over Bluetooth **and** the log shows the cable has been working. Both
conditions matter: without the first there is nothing to offer, and without the
second the user is already on Bluetooth and needs nothing.

> **Title:** ChromIQ has been using the cable
>
> Your instrument answered over Bluetooth just now, so Bluetooth is working on
> this computer. ChromIQ has not been using it, and there is a plain reason for
> that: it tries the cable first, and on this computer the cable has been
> answering. It only turns to Bluetooth when nothing answers on the cable.
>
> For most people that is the right way round. The cable is usually quicker to
> start and it cannot be taken away by a phone app, which a Bluetooth connection
> can. So this is not something that has been going wrong.
>
> But it is your choice, and until now you have not had one. If you would rather
> ChromIQ looked for your instrument over Bluetooth first, you can say so.
>
> Before you do, one thing to expect: looking over Bluetooth takes longer than
> opening the cable — up to about half a minute if the instrument is asleep or
> out of range — and ChromIQ waits for that before falling back to the cable. It
> will always fall back; you cannot be left with no instrument by choosing this.
>
> You can change it back whenever you like, in Preferences, under Measurement,
> in “How ChromIQ connects to your CR30”. 🆕
>
> Please send the report either way. It tells us things about your instrument
> and this computer that we cannot find out any other way.
>
> **[ Try Bluetooth first from now on ]  [ Leave it as it is ]**

Prerequisite and outcome are both stated; neither transport is called better;
the cost is given as a number before the button, not after it.

### I.4 Preferences ▸ Measurement ▸ new group box (`tr()`) 🆕

Placed below “Per instrument”, which already carries a CR30 row (F.1).

> **How ChromIQ connects to your CR30**
>
> A CR30 can be reached two ways — over its USB cable, or over Bluetooth.
> ChromIQ normally tries the cable first, because it is usually quicker to start
> and nothing else can take it away while you are measuring. Bluetooth is there
> for when the cable is not, and for working away from the computer.
>
> ( • ) Try the cable first, then Bluetooth *(recommended)*
> (   ) Try Bluetooth first, then the cable
> (   ) Only ever use the cable
>
> Whichever you choose, ChromIQ tells you which one it used when the measurement
> starts. 🆕
>
> “Only ever use the cable” is worth choosing if your instrument has no
> Bluetooth: without it, ChromIQ spends about fifteen seconds looking for one
> every time the cable does not answer.

The third option's justification is stated so it is not a mystery switch. The
recommended one is marked, so a beginner who does not want to decide does not
have to.

### I.5 The Measure tab, on every open (log line, `tr()`) 🆕

The one that removes the confusion, and the cheapest thing in this report:

> ChromIQ is using your CR30 over its USB cable.

> ChromIQ is using your CR30 over Bluetooth.

and, when a preference caused a fallback:

> ChromIQ looked for your CR30 over Bluetooth first, as you asked, and did not
> find it — so it is using the USB cable instead.

That third sentence is the whole of “fall back with a message” from Q3, and it
needs no window.

### I.6 The failure text — §M, so it is PROPOSED, not written

G.3(a): when the preference is not Automatic, the failure must name it.
`M_CR30_INSTRUMENT_GONE` is already `approved=False`, so it already sits in
§M-PROPOSED and an edit stays there. Proposed additional paragraph, to appear
**only** when the preference is not Automatic:

> You have asked ChromIQ to try Bluetooth before the cable. It did, and it could
> not reach your instrument that way either. If you would rather it went back to
> trying the cable first, that setting is in Preferences, under Measurement, in
> “How ChromIQ connects to your CR30”.

The calibration window at `tab_measure.py:7344` needs the same sentence. It is
not in the catalogue today (`UNCATALOGUED_MEASUREMENT_WINDOWS` is pinned at 1 by
`tests/test_message_catalogue.py:441`), so adding wording there must not grow
that list — check which window the one exception is before touching it.

**Correction to I.6:** `_run_cr30_calibration` is in **neither**
`WINDOW_SOURCES` nor `UNCATALOGUED_MEASUREMENT_WINDOWS`
(`tests/test_message_catalogue.py:309,337`) — the pinned count of 1 refers only
to `_on_overlay_toggled`. So adding a sentence to the calibration window does not
trip that test. It is still text the §M model would want to own eventually; that
is a debt to name, not a blocker.

---

## J. Q7 — scope, verdict, plan

### J.1 What ships, in three tiers

**Tier 1 — ships now, answers the question in front of us, near-zero risk**

| # | Change | Files | Risk |
|---|---|---|---|
| 1 | **Report stage 4: the log history** (D.1, D.7, I.1) | `workflow/cr30/bluetooth_report.py` (new function), reads only | none — pure reading |
| 2 | **Report: the two cheap facts** — cable has worked here, address remembered (C.1, C.2, I.2) | same | none — two settings reads |
| 3 | **Report: CH340 attached now**, worded as C.3 allows (I.2) | same, via `workflow.cr30.discovery.candidates()` | none — 7 ms, opens nothing |
| 4 | **One `log.warning` on `_open()`'s final failure** (D.2) | `measure_bridge.py:855` | one line in an `except` that already raises; no behaviour change |
| 5 | **Delete or gate `ui/tooltip_button.py:78`** (D.3) | one line | it is 58.7 % of the user's log budget and has never told anyone anything |

Tier 1 alone would let the Windows owner produce, tonight, a file that says
whether ChromIQ ever attempted Bluetooth on his machine — without anyone
trusting a recollection. **That is the round's actual deliverable.**

**Tier 2 — the way out. Ships together or not at all**

| # | Change | Why it cannot be split |
|---|---|---|
| 6 | **Measure tab says which transport it used** (I.5) | **Ship this first, even alone.** It is the real fix for the stated confusion (E.2), needs no setting, and it is what makes 7 safe. |
| 7 | `_open()` gains an **additive** `"ble-first"` branch | without it "prefer Bluetooth" is a lie (E.1 i) |
| 8 | `_no_device_help` (or equivalent) for the `"usb"` and `"ble-first"` branches | without it the preference makes failures *worse* (E.1 ii, G.3 b) |
| 9 | Settings key + `DEFAULTS` entry + Preferences group (I.4) | the control |
| 10 | `tab_measure.py:7869` passes `transport=` | the only wiring |
| 11 | Something on screen during a Bluetooth wait | H.3: up to 44 s of silence, which would be reported as a hang |
| 12 | Reword `main_window.py:1927` — “nothing to hunt for in Preferences” | H.4(a): it becomes false the moment 9 lands |
| 13 | The offer in the report (I.3) | the sketch's (c), and it is right |

**Tier 3 — do not build**

* the persisted outcome record (D.5 option 2) — bought by 1 and 5 instead;
* a fourth “Bluetooth only” option (E.4) — open question, not built;
* **anything inside `ble.discover` or the existing `"auto"`/`"usb"`/`"ble"`
  branches.** They work for the one Bluetooth user we have. Every Tier-2 change
  above is additive by construction.

### J.2 Module map — reuse vs new

| Concern | Reuse | New |
|---|---|---|
| reading the log | `core/platform_paths.log_dir()`, `core/logger._log_path` | `transport_history()` — prototyped, ~60 lines. **Put it in `workflow/cr30/bluetooth_report.py`**, not in `core/`: it knows CR30 log lines and nothing else needs it |
| USB presence | `workflow/cr30/discovery.candidates()` | none |
| settings reads | `DeviceReader.REMEMBERED_ADDRESS_KEY`, `REMEMBERED_PORT_KEY` | one new key, e.g. `cr30_transport`, **in `DEFAULTS`** (unlike its two neighbours — B) |
| the transport decision | `DeviceReader._open()`, `_open_usb`, `_open_ble` — untouched | one `elif` for `"ble-first"` |
| the failure text | `_no_device_help` | call it from the other branches |
| the preference UI | `_build_measurement_tab`, `TooltipButton`, `NoScrollComboBox` | one group box |
| the offer | `_offer_cr30_bluetooth_repair` — the proven shape | one sibling method |
| the "which transport" line | `tab_measure` log pane; `measure_bridge.py:883` already computes it | a signal or a callback from reader to tab |
| tests | `tests/test_cr30_bluetooth_remembers_the_address.py` already fakes `CR30.open_usb`/`open_ble` | new cases on the same fakes |

⚠ **One layout caution, from the source itself.** `settings_dialog.py:800`:
*"Tighter than the page's 12: seven rows moved in above the pace section, and the
tab should still fit a normal window height."* Preferences → Measurement is
already known to be tight. A new group box there needs an on-screen check for
height before it is called done.

### J.3 What I did NOT do, and why

I did not drive the app on screen, though the brief permits it. Nothing proposed
here exists yet, so there is no new behaviour to observe; everything asserted
above comes from the shipped source, from a run of the real `_open()` against a
faked transport, or from this machine's real log. The one thing an on-screen run
should settle **before implementing** is the Preferences height above. The CR30
was not touched at any point; no serial port was opened and no Bluetooth
connection was made.

### J.4 Open questions — the owner's ruling needed

1. **Should `bleak` join `core/logger.py::_NOISY_LIBRARIES`?** It is 4.5 % of the
   log and it is the part that names the user's neighbours in the clear (D.4).
   Against: a genuine BLE bug report loses its most detailed evidence. **His
   call, and it is a privacy call, not a technical one.**
2. **May report stage 4 attempt a real Bluetooth open** (D.5 option 3)? If yes:
   does it run **before** or **after** `_offer_cr30_bluetooth_repair`, and is it
   allowed to leave `cr30_ble_address` written — which is the repair, performed
   without asking?
3. **Is a fourth option, "Only ever use Bluetooth", wanted?** (E.4.) It protects a
   user's Arduino/3D printer from an identify frame on a first run, at the cost
   of a fourth radio button.
4. **May a measurement message name a Preferences control?** I.6 does. If the §M
   model says a measurement window must not send the user to Preferences
   mid-session, the sentence has to change shape.
5. **Reword `main_window.py:1927` now or with Tier 2?** It is only false once the
   Preferences group exists — but shipping the group and forgetting the sentence
   is exactly the mistake the brief says has been made four times today.
6. **Tier 1 items 4 and 5 are source edits outside `tests/` and `scripts/`.** I
   have written neither. Both are one line. Confirm before I would touch them.

### J.5 Verdict

**Adopt (a) and (c) close to as sketched, with the detection list rebuilt.
Redesign (b): its labels cannot be built as written, and it is the *second* fix,
not the first.**

The sketch's instincts are right in the two places that matter most: the report
should say plainly what the situation is rather than leave the user to infer it,
and the way out should be offered from the report in the proven shape of
`_offer_cr30_bluetooth_repair`. Both survive intact.

Three things change:

1. **The detection is not a settings lookup, it is the log.** The owner's
   correction — that nobody knows whether the Windows user unplugged — is only
   answerable retrospectively, and ChromIQ has been writing that answer down,
   dated, on every platform, since long before this round. The sketch's (a)
   would have reported the *present* state and left the past exactly as
   uncertain as the forum thread.
2. **The first fix is visibility, not choice.** "Why is my instrument on the
   cable when I asked for wireless" is a question ChromIQ can answer in one
   sentence at zero cost, and answering it removes most of the demand for the
   setting. A preference offered *instead* of that sentence lets a beginner opt
   into the slower, more fragile transport for a reason that was a
   misunderstanding.
3. **"Prefer Bluetooth" is not a thing the code can do.** `transport="ble"` is
   Bluetooth *only*, and both non-`auto` branches throw away
   `_no_device_help`. As sketched, (b) ships a label that lies and an error
   message that is worse than the one it replaces, to the user who is already
   stuck.

**Rating of the sketch: 6 / 10.**

Earned: it identified the right reuse target (`_offer_cr30_bluetooth_repair`),
the right constraint (explicit, reversible, still ask for the report), and the
right instinct that the report should *state* rather than imply. It was also
right that the machinery is in `DeviceReader.__init__` — as far as the signature
goes.

Lost: the detection list missed `cr30_usb_port`, the single best free signal, and
assumed a record of "Bluetooth has succeeded" that does not exist and cannot be
reconstructed. "Prefer Bluetooth" cannot be implemented as described. Neither
non-`auto` branch was checked for what it does to the error message — the exact
surface a "way out" is judged on. And the sketch had no answer at all to the
question that turned out to be the round's real one: *what actually happened?*
That came from the correction, not from the design.

Six is a good sketch with a wrong centre of gravity: it designs a control for a
user who mostly needs a sentence, and it designs detection for the present when
the question is about the past.

---

## Appendix — the prototype, kept here because /private/tmp is swept nightly

Run as-is against `~/Library/Logs/ChromIQ/chromiq.log` to produce D.7's output.
This is the proposal for Tier 1 item 1; it belongs in
`workflow/cr30/bluetooth_report.py`.

```python
import re
from pathlib import Path

_WANTED = (
    ("attempt",   "no USB device"),
    ("opened",    "CR30: opened over "),
    ("timing",    "CR30 BLE: found in "),
    ("staleaddr", "the device at the remembered Bluetooth address"),
    ("usbrefuse", "did not answer as a CR30"),
)
_TS = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})")


def _files(base: Path):
    """Oldest first: RotatingFileHandler names them .5 … .1, then the live one."""
    return [base.with_suffix(base.suffix + f".{i}")
            for i in range(5, 0, -1)] + [base]


def transport_history(base: Path):
    """Every CR30 open/attempt ChromIQ recorded, oldest first, with the span.

    Reads ONLY ChromIQ's own `workflow.cr30` lines. bleak's DEBUG chatter names
    every Bluetooth device around the user (see D.4) and must never be copied
    into a file we ask anyone to send.
    """
    events, first_seen, last_seen = [], None, None
    for f in _files(base):
        try:
            text = f.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue                 # a rotation file that does not exist yet
        for line in text.splitlines():
            m = _TS.match(line)
            if m:
                if first_seen is None:
                    first_seen = m.group(1)
                last_seen = m.group(1)
            if "workflow.cr30" not in line and "CR30 BLE" not in line:
                continue
            for kind, needle in _WANTED:
                if needle in line:
                    events.append((kind, m.group(1) if m else "?",
                                   line.split(": ", 2)[-1].strip()))
                    break
    return events, first_seen, last_seen
```

Known limits, both real:

* it cannot tell a test harness from a user (D.7 correction 1);
* a Bluetooth **failure** is visible only as an absence until the `log.warning`
  of Tier 1 item 4 exists (D.2).
