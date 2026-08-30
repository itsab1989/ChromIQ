# 36 — CR30 generality, the Stop false alarm, and manufacturer outreach

**Agent:** [CR30-GEN] · **Started:** 2026-08-30 · **Status: COMPLETE** — Jobs 1 (+2 owner addenda), 2, 3

## Job 1 — Will OTHER CR30 units be found on other people's machines?

Everything below is read from the shipped code (`workflow/cr30/*.py`, master @ v4.1.5-beta.1)
and the research repo (`~/develop/chromiq-cr30-research`), not from memory of either.

### USB — verdict: **very likely found and read, with three named exceptions**

**How it works (proven from code):** `discovery.candidates()` shortlists serial ports by
VID/PID `0x1A86:0x7523` only — no name, no serial (the device's `iSerialNumber` is 0, so
there is nothing unit-specific to depend on). `CR30.open_usb(port=None)` then opens
`found[0]`. The wire protocol carries no unit-specific constant anywhere on the read
path: `read_stored` fetches chunks `BB 01 10/11/12`, the button header `BB 01 09` is a
device firmware behaviour, and the axis is read **from the device's own header** and
refused if it is not 400/10/31. The magnet-gate flag (header offset 24) is a protocol
field, not a stored constant. So for a same-model unit, nothing on the USB path depends
on the owner's device.

**Corroboration beyond his unit exists:** `PRIORART-001` (vendor app driving a *second*
CR30 on Windows) reproduces the same command set, the same `BB 01 09` headers, the same
chunking. That is the strongest unit-independence evidence in the repo.

**Exception 1 — the app never behaviourally identifies over USB.** `Session.identify()`
(`AA 0A` → ASCII "CR30") exists and is sound, but **no ChromIQ user path calls it**:
`DeviceReader._open` → `CR30.open_usb` opens the first CH34x port and goes straight to
waiting for button headers. Grep-proven: `identify(`/`is_cr30(` from the cr30 package are
referenced nowhere in `ui/` or the bridge (the `ui/ti2_loader.is_cr30` hits are a chart
keyword test, unrelated). Consequences on another machine:
  - A **non-CR30 CH340 device alone** (Arduino clone, cheap adapter — `1a86:7523` is the
    most common hobby bridge in existence): it is opened "successfully", the session arms,
    and the user is told to press the instrument's button; each patch dies after the 180 s
    timeout with a misleading message. Nothing is corrupted (the wait is passive; a garbage
    frame that slips through fails the axis check `"device declares an axis this build has
    never seen"`), but the failure blames the user, not the port.
  - A non-CR30 CH340 **plus** the real CR30: whichever enumerates first wins. There is no
    probe-all-candidates loop and no fallback to `found[1]`.
  - Transport **auto**: USB is tried first and an Arduino *opens fine*, so the Bluetooth
    fallback never runs even when the real CR30 is sitting there advertising.
  The fix is cheap and already written: probe each candidate with `Session.identify()`
  (~4 transactions, ~3 ms measured RTT) and keep the port whose reply says CR30. The
  identify probe sends only `AA 0A` reads — nothing that can trigger or calibrate.

**Exception 2 — a CR30 with a different bridge chip.** Apple's DriverKit dext is a
hard-coded allow-list of exactly PIDs `0x7523` and `0x55D4` (verified from the dext
Info.plist, PLATFORM_SUPPORT.md). A CR30 revision shipped with a CH343/CH347 on another
PID would neither match `candidates()` nor even get a serial node on macOS. Whether such
revisions exist is **unknown** (see "series" below).

**Exception 3 — identity offsets are single-unit.** The `AA 0A` field offsets are
VERIFIED on one unit only (PROTOCOL.md §4 marks them so). The failure direction is safe:
a unit whose model string runs past the expected bound is marked suspect and `is_cr30()`
returns False — refusal, not misidentification. But it means the *robust* identification
that Exception 1 asks for could false-negative on a variant unit. Only a second unit's
identity frames settle it.

Also real but already mitigated elsewhere: Argyll's serial scan writes foreign probe
strings to a plugged CR30 (verified **inert**, 32/32 probes, EXP-USB-007), and the
bundled app's Info.plist carries `NSBluetoothAlwaysUsageDescription` (checked in
ChromIQ.spec), so the frozen build will get the CoreBluetooth permission prompt rather
than a silent refusal.

**Grade: USB discovery+reading on another same-model unit — very likely** (protocol is
unit-clean by construction and corroborated on a second unit via vendor captures).
**USB identification of the right port — currently weak**, because the sound check exists
and is not wired in.

### Bluetooth — verdict: **likely found, with one real bug and one absent protection**

**How it works (proven from code):** `ble.discover()` shortlists advertisers exposing the
`ffe0` service (never the name), then confirms each by connecting and sending
`READ_MEASUREMENT` (`bb 02 10` — reads the stored value, cannot trigger or calibrate) and
checking the reply's declared axis equals (400 nm, 10 nm, 31 bands). The name is used
only as a label. `BleTransport.open(address=…)` pins a remembered address as a *hint*,
falling back to the scan. This design is genuinely unit-independent: the axis is a
property of the model, the service UUID a property of the firmware.

**Caveats on that verification, honestly graded:**
  1. The two-stage discovery has been exercised end-to-end on **one unit, on macOS
     only** (PLATFORM_SUPPORT.md: BLE untested on Windows/Linux; bleak is cross-platform
     but that is bleak's claim, not ours). All BLE captures in the research repo are of
     the owner's unit. The AXIS itself, however, is corroborated on a second unit over
     USB: PRIORART-001 (a third-party CR30) contains 67 `BB 01 09` headers, every one
     declaring 400 nm / 31 bands (`28 1f` in the USB byte-x10 encoding — checked directly
     in the capture JSON for this report). Since the axis is a device property, the BLE
     confirm criterion holds for at least two units, even though only one has ever been
     seen over BLE at all — advertising behaviour included.
  2. Whether *every* CR30 advertises `ffe0` is inferred from one unit plus the fact that
     the vendor app finds units generically. Very probable, unproven.
  3. A CR30 that has **never stored a measurement** (fresh out of the box) answers the
     confirm step with an unknown reply. If the reply is zero-filled past the header, the
     axis parses as (0,0,0) and the unit is left UNCONFIRMED. Unknown; one experiment on
     a factory-reset or brand-new unit settles it.

**The real bug — the unconfirmed fallback.** In `BleTransport.open()`:
```python
ok = [c for c in cands if c["confirmed"]] or cands
```
If no candidate confirms, the transport connects to the **first unconfirmed `ffe0`
advertiser it can find**. `ffe0` is the generic HM-10 BLE-UART service, shared by
thousands of cheap gadgets — the code's own docstring says so. On another person's
computer with a smart kettle/tracker advertising ffe0 and the CR30 asleep or held by the
phone app, ChromIQ silently connects to the wrong device and every read then fails with
measurement-shaped errors ("measurement header not found in 0 bytes") instead of "no
CR30 found". Combined with caveat 3, a brand-new unit could even lose the coin-toss to a
neighbouring gadget. The honest behaviours would be: only ever auto-connect to a
CONFIRMED candidate; if only unconfirmed ffe0 devices exist, say exactly that.
Ranked **top of the BLE list by user harm** because it converts "device not found" into
an endless, misdirected measurement-failure loop.

**The absent protection — magnet gating on BLE, for anyone who is not the owner.**
Confirmed from code and STATUS.md, as suspected:
  - BLE has **no protocol-level gate flag** (`gate_flag=None`, stated in
    `read_measurement` metadata).
  - The behavioural check, `looks_like_calibration_tile()`, compares against
    `TILE_SIGNATURE`, **his unit's stored constant**, at tol 0.05 %R. The one other unit
    with data (`PRIORART-001`) has a white reference up to 4.69 %R away — 94× the
    tolerance. On any other unit this check returns False for every gated reading.
  - What is left for another owner over BLE: the bit-identical-repeat guard (catches the
    *second* gated reading, never the first) and the coarse >130 %R bound (proven
    porous — a real corrupted reading at 105.47 %R passes).
**Plain consequence for another owner:** over Bluetooth, the first reading taken with a
magnet at the aperture is accepted into the chart, and — worse — the instrument has by
then silently white-calibrated against whatever it sat on, skewing every later reading
by a factor no guard can see. Over USB the button-header flag covers this and is
unit-independent by design, but it too is verified on one unit (3/3) and marked "needs
replication" in the code. The documented fix direction (learn the tile constant per
unit, MEASUREMENT.md) is right; until then CR30-over-BLE for other users should be
described as "no magnet protection" in any support claim.

### ⚠ ADDENDUM A (raised to the top of Job 1 by the owner): what ChromIQ does to a CH340 that is NOT a CR30

`1a86:7523` is the generic CH340/CH55x bridge, in millions of Arduinos, 3D
printers, CNC and laser controllers, GPS modules and adapters. The owner's rule
— "ChromIQ must not greenlight any and every device connected via USB" — audited
against the real code:

**A1. Does ChromIQ ever *call* a device a CR30 on VID/PID alone?** No text
does: `discovery.candidates()` has exactly one consumer, `CR30.open_usb`
(device.py), and every on-screen instrument name comes from the chart's
`TARGET_INSTRUMENT` keyword or the instrument's own report
(`_on_instrument_detected`, tab_measure.py:3890/4716) — never from the port
list. **But the behavioural greenlight is worse than a label**: starting a CR30
measurement opens `found[0]` — the first CH34x port — and *treats it as the
instrument for the whole session* without ever sending `AA 0A`. `identify()` /
`is_cr30()` are wired into nothing on the user path (grep-proven, Job 1
Exception 1).

**A2. What gets WRITTEN to the unidentified device — the ranked harm list.**

1. **Opening the port itself asserts DTR (and RTS).** `SerialTransport.open`
   passes `rtscts=False, dsrdtr=False` — those only disable *flow control*;
   pyserial still raises DTR on open, and a DTR edge is exactly the auto-reset
   line on Arduino-style boards, which includes most consumer 3D-printer and
   CNC/laser controller boards. Concrete worst case: a printer running a
   standalone SD-card job with its USB idle-but-plugged — ChromIQ starting a
   CR30 measurement **resets the board and kills the job**. (A port another
   program holds open is safe — the open fails EBUSY and ChromIQ falls through
   to Bluetooth.) This is the highest-harm finding of the addendum: it damages
   the user's OTHER equipment, silently, and needs no bad luck beyond port
   ordering. Proven at the code level; not yet demonstrated on hardware.
2. **A 60-byte binary calibration frame is written at measurement start.**
   The CR30 flow runs an initial calibration unless disabled
   (`params.external_values and not params.disable_initial_cal`,
   tab_measure.py:5696) → `CR30.calibrate()` USB branch →
   `send(Frame.build(0xBB, 0x11, 0x00, 0))` — fifty-plus bytes including 0xBB,
   0xFF and a checksum — to a device nobody has identified, at 115200 baud
   (`NOMINAL_BAUD`). Checked against the two most common firmware families:
   Marlin-style line parsers buffer it as a garbage line (the frame contains no
   0x0A) and GRBL v1.1's real-time command set contains none of the frame's
   bytes — so on THOSE it is inert, **by luck, not by design**, and the claim
   cannot be extended to Klipper/Smoothie/proprietary controllers without
   checking each. A further write (`BB 01 10/11/12` chunk fetches) happens only
   if 60 bytes arrive that pass the frame checksum — unlikely per frame
   (~0.4%) but a continuously chatty device gets many tries across a 180 s
   patch wait.
3. **The port is held open for the entire failed session** while the reader
   re-arms every 180 s telling the user to press a button on a device that has
   none. Misleading, and it keeps the user's other tool unusable meanwhile.

**A3. The safest identification available.** Read-only narrowing exists but is
thin: the CR30's bridge reports USB product string `CH554_CDC`
(one-unit observation), where garden-variety CH340 adapters report
"USB2.0-Serial"/"USB Serial" — usable for *ranking*, never for gating.
There is no read-only positive identification: the CR30 is silent when idle,
descriptors carry no serial. So the honest position is **"we must write to find
out"** — and then the mitigation has to be procedural:
  - probe with `AA 0A` (identify) FIRST — four short frames, the least
    invasive write we know (though on unknown firmware still a write), and
    never the calibration frame;
  - suppress DTR/RTS on open (`serial.Serial(dsrdtr=None…)` /
    construct-unopened, set `ser.dtr = False`, then `open()`) so the probe
    cannot reset an auto-reset board — pyserial supports this and the CR30
    needs no DTR (no UART is even in its path, EXP-USB-005);
  - remember the confirmed port (device node + product string) and try it
    first next time;
  - with several candidates and none confirmed, say so and ask — never spray
    frames across every serial port.
**Whether DTR-less open works against the real CR30 is unverified** — one
plug-in test on the owner's unit settles it and must precede the change.

**A4. Interaction with the serial-over-USB idea (Addendum B):** any stored
"this is my CR30's id" record must only ever be written from a device that has
answered `AA 0A` with model CR30. Persisting an id learned from an unconfirmed
CH34x port would pin both transports to a device that is not an instrument.

**A5. Two CH340 devices attached today:** first in enumeration order wins,
the other is never tried, and if the loser is the CR30 the session dies with
per-patch timeouts (Job 1, Exception 1). What SHOULD happen: rank candidates
(remembered port, then product string), identify-probe in order with
DTR suppressed, use the first confirmed CR30, and report "N serial devices,
none answered as a CR30" otherwise.

### ADDENDUM B (owner's idea, challenged): learn the BLE name over USB

The idea: `identify()` over USB returns `second_id`, and on his unit the BLE
advertised name IS that string — so store it once and connect by name later.

1. **The premise is a single-unit observation.** TRANSPORT_BLE.md marks
   "advertised name = the AA 0A 01 string" VERIFIED on his unit only. Nothing
   in the vendor corpus corroborates it: PRIORART-001 is USB-only, and every
   BLE capture is of his device. It is *plausible* (that is presumably how the
   vendor app pairs), but building unit-independence on it would repeat the
   exact mistake Job 1 exists to catch. It also composes badly with the fact
   that the identity field OFFSETS are themselves single-unit (PROTOCOL.md §4)
   — the id we would store is read from offsets another unit may not honour.
2. **What it buys, honestly:** almost nothing that the shipped address cache
   does not already give. The cache (measure_bridge `cr30_ble_address`,
   beta 1) removes the 15.4 s scan for every repeat connection. The name could
   help only: (a) the very first BLE connection of a USB-only user — but
   finding-by-name still requires the same scan (the measured 15.42 s WAS
   `find_device_by_name`), so it saves no time, it only skips the
   connect-and-confirm probe of non-CR30 ffe0 devices; (b) telling two CR30s
   apart — real but rare, and the user-facing chooser (`discover()` already
   returns name+rssi per candidate) solves it more honestly; (c) a changed
   host address — the scan fallback already covers that.
3. **Storage:** `cr30_ble_address` is already an app-wide single key; adding an
   app-wide "serial" key doubles down on a one-instrument assumption. Anything
   stored should be an **instrument record** (id, axis, address, product
   string, learned-from), created only after a confirmed identify (A4), listed
   and deletable, never a hidden pin.
4. **What it could break:** any use of the stored name as a discovery FILTER
   makes Bluetooth worse for exactly the users Job 1 worries about — a variant
   unit advertising differently would become undiscoverable. ble.py already
   codifies the right rule ("the name is a hint and a label, never a test");
   the idea is only safe if it obeys that rule, at which point it adds little.
5. **Recommendation:** do not build it as designed. If anything, build the
   instrument record of (3): USB identify populates it, BLE discovery uses it
   to LABEL and RANK confirmed candidates ("this is CM…, the unit you used
   over USB") and to pick between two CONFIRMED CR30s. Decisions needed before
   any code: (i) second unit confirms name==second_id, or the record treats the
   name as unverified; (ii) record schema + where multi-instrument UI lives;
   (iii) the rule "rank, never filter" written into the design spec;
   (iv) forgetting/expiry when a unit is gone. Plainly: **the address cache
   already covers the real cases; this adds a unit-specific assumption and a
   second cache to go stale, for a rare-case gain.**

### The CR30 "series" — what is known vs guessed

Known from device evidence: two units total have ever been observed (his, and the
vendor-capture unit), both model "CR30", both 400/10/31, both on the same command set.

The manufacturer's own brochure (fetched for Job 3 — CHNSpec "Spectral Colorimeter CR
series", en.chnspec.com) adds marketing-level facts that cut both ways:
  - The series is **CR10 / CR20 / CR30**, and ALL THREE share 45/0 geometry,
    **400–700 nm at 10 nm** — i.e. the exact 31-band axis the BLE confirm step keys on —
    and all three list "USB, Bluetooth" as interfaces. So **the BLE axis check cannot
    distinguish a CR30 from its own siblings** (if a CR10/CR20 answers the same read
    command). Only the CR30's spec lists "Spectral reflectance" among its outputs, which
    *suggests* the lower models may not serve spectra — unknown, and exactly the kind of
    thing the manufacturer can answer (asked in the Job 3 draft).
  - No CR30 sub-variant with a different range or interval is advertised, which is
    mildly reassuring for the axis assumption across CR30 units.
On USB the model-string check would refuse a CR10/CR20 (model != "CR30"); over BLE
nothing would. The code otherwise fails *safe* on an unknown variant (axis refusal,
suspect-field refusal) — it will not mislabel bands — but "found and usable" is only
established for units matching the observed fingerprint.

### Cheapest experiments that raise confidence
1. **Wire `Session.identify()` into `open_usb` candidate selection** and test with a $3
   CH340 Arduino clone plugged in beside nothing, then beside the CR30. No second CR30
   needed; kills Exception 1 and proves the non-CR30 behaviour. (Code change + one
   hardware afternoon on hardware already owned.)
2. **A $3 HM-10 module** advertising ffe0: run `ble.discover()` against it. Proves the
   unconfirmed-fallback bug and validates the fix. No CR30 involvement.
3. **One volunteer with any other CR30** running two scripts from the research repo
   (USB identify dump + BLE discover): settles identity offsets, advertising, the axis,
   and the gate flag on a second unit in ~15 minutes. This is the single highest-value
   experiment, and the Job 3 email is a legitimate place to ask the manufacturer to
   confirm the model string, axis and bridge chip across the family.
4. **Factory-fresh/reset unit** (or the manufacturer's answer): what does
   `READ_MEASUREMENT` return before any measurement exists?

## Job 2 — The B2-1 false alarm: FOUND, and it is not a Stop at all

**The route is proven from the owner's own logs plus the code — no guessing.**

### What actually happens

The warning does not fire on any Stop-button ending. It fires on **quitting the
app while a CR30 spot session is open.** Every occurrence in
`~/Library/Logs/ChromIQ/chromiq.log` (seven on 2026-08-30 alone: 00:39:37,
04:43:07, 04:47:45, 04:51:44, 06:09:22, 06:14:55, 06:22:10) has the identical
signature:

1. immediately before it, `settings.set window_geometry` and
   `settings.set active_tab` — the writes `MainWindow.closeEvent`
   (ui/main_window.py:2424) makes as the app closes;
2. `ArgyllRunner: finished with code 9`;
3. **no** `ArgyllRunner: process killed` line anywhere near — and that line is
   logged unconditionally by `ArgyllRunner.abort()` (argyll_runner.py:470/473),
   so `abort()` (the only path that sets `_user_quit` before a kill) provably
   never ran. Two of the seven even have the NEXT app instance's startup banner
   printed just before the dying instance's warning (04:51:39, 06:22:07 — the
   two ChromIQ processes share one log file).

### The mechanism, line by line

- `closeEvent` saves geometry, then calls `self._runner.cleanup()`
  (main_window.py:2455). Nothing in the close path touches
  `MeasureManager._user_quit`, which is set only by the q/Q/Esc keys
  (measure_manager.py:771), `abort()` (:995), and the helper's `aborted` event
  (:1538).
- `cleanup()` (argyll_runner.py:503) disconnects **the runner's own signals**
  (`line_received`, `finished`, `_pty_done`) "so no callbacks fire during
  teardown" — but NOT the `self._process.finished → self._on_finished`
  connection made in `run()` (:402). Then it calls `self._process.kill()` and
  `waitForFinished(2000)`.
- `kill()` is SIGKILL; Qt reports a signalled child's signal number as the exit
  code (CrashExit), hence **9**. `waitForFinished` delivers the `finished`
  signal synchronously, so `_on_finished(9)` runs *inside* `cleanup()`, picks up
  `self._run_on_finish` — the measure session's `_on_finish` closure — and calls
  it with 9.
- In `_on_finish(9)`: `was_engine` True, `_stock_reader_cannot_read` True (a
  CR30 chart, tab_measure.py:12803), `code != 0`, `_user_quit` False → the #159
  branch at measure_manager.py:471 logs the warning and emits
  `engine_fallback_refused` — during shutdown, about a helper the app itself
  just killed.

Why B2-1 read as "a deliberate Stop": from the owner's chair, quitting the app
IS how he deliberately stopped working — but no measurement-ending route was
involved. Every actual Stop route was traced and none can produce this:
the M-END window's "Discard and stop" goes through `abort()` (flag set), and
"Save and stop" on a CR30 chart goes 'd' → `unread_confirm` → 'y', after which
the helper saves and `main` returns **0** (chromiq_chartread.c:3103-3131, 4286-4297 —
every in-protocol ending, quit included, exits 0).

### The correct fix

Make `cleanup()` do what its own comment already promises: before killing,
clear the per-run callbacks and disconnect the QProcess connections —

- `self._run_on_finish = None` / `self._run_on_line = None` (the existing
  `release_run_callbacks()` (:480) does half of this already and can be reused);
- disconnect `self._process.finished` from `_on_finished` and
  `readyReadStandardOutput` from `_on_ready_read`.

That silences every shutdown-time session callback at the source, for every
manager that uses the runner, with no UI knowledge needed.

### What the fix must NOT break — checked

- **The #159 refusal branch itself is right and stays.** A genuine engine
  failure on a CR30 chart (code != 0 while the app lives) still refuses
  fallback and warns; nothing in the fix touches `_on_finish`.
- **Chained runs** (targen→printtarg; engine→stock fallback) rely on
  `_on_finished` capturing callbacks before invoking — untouched.
- **No readings are lost by the quit itself**: the helper autosaves every patch
  (`cq_write_ti3_atomic()` after each accepted value, chromiq_chartread.c:3177+),
  so SIGKILL at app close loses nothing on a CR30 chart. The fix changes only
  who gets told about the kill.
- The PTY (stock chartread) path is already silenced by cleanup's `_pty_done`
  disconnect — keep that.

### Can the same false alarm fire for a non-CR30 chart?

- **Stock (PTY) sessions: no.** cleanup() disconnects `_pty_done`, so the
  completion never reaches `_on_pty_finished` at shutdown.
- **Engine sessions for other instruments: no warning line, but something
  worse is latent.** The same leaked `_on_finish(9)` runs with
  `_stock_reader_cannot_read` False. With any engine event already seen it does
  nothing. But if the app is quit in the first instants of an engine session —
  before the helper emits a single event — `_engine_should_fall_back(9)`
  (:639) returns True and `_launch_stock` spawns stock chartread **during
  shutdown**, over a PTY via `subprocess.Popen`, which the dying app never
  kills: a potential orphaned interactive chartread holding the instrument
  after quit. Code-derived, not observed in any log; the same cleanup fix
  removes it. (`_engine_should_resume_fallback` needs `_engine_fatal`, which a
  shutdown kill never sets, so the with-progress resume relaunch cannot fire.)

**Ranked by user harm:** the warning itself is noise that teaches the user to
ignore a real refusal one day (B2-1's point, unchanged); the latent
orphan-chartread relaunch is small-window but worse in kind; both fall to the
one cleanup() fix.

## Job 3 — Manufacturer outreach: DONE, draft on the Desktop

**Maker, verified from the vendor's own sites (not assumed):** CHN Spec Technology
(Zhejiang) Co., Ltd. — "CHNSpec" — and the CR30 is the Enhanced Edition of their CR
series (brochure: en.chnspec.com, "Spectral Colorimeter CR series", CR10/20/30).

**Address, HIGH confidence:** `chnspec@colorspec.cn` — the one contact email published
on BOTH vendor-owned sites, https://en.chnspec.com/ (homepage and /Contact/index.aspx)
and https://www.chnspec.net/. Secondary channel from the same sources:
WhatsApp/phone +86 13732210605. The regional service centres on the contact page
(Russia/India/Turkey/Iran) are distributors and were not proposed for first contact.
No plausible-but-unverified sales@ alias was invented — a wrong address is worse than
none, and this one is corroborated twice.

**The draft** is at `~/Desktop/CR30-manufacturer-email.txt`: sources + confidence at the
top, a subject line, and a complete send-as-is draft. It introduces ChromIQ, links
v4.1.5-beta.1, carries a clearly marked `[YOUTUBE LINK — to be added]` placeholder with
the honest note that the video shows a pre-beta-1 build, states plainly that the
integration was reverse engineered without vendor documentation on a self-bought unit
(no apology, nothing copied or redistributed), and asks three concrete questions that
serve Job 1 directly: protocol/SDK documentation, variants across the series
(CR10/CR20 answering the same commands?), and a technical contact. No device serial
appears in the draft.

**Judgement call, made and explained:** the public research repo
(github.com/itsab1989/chromiq-cr30-research — verified PUBLIC via the GitHub API before
claiming so) IS linked in the draft. Reasoning: the draft already says the findings are
public, and saying so without the link would read as coy; the repo is one click from the
ChromIQ release link anyway; and openness is the tone that makes the three questions
answerable. If the owner prefers a softer first contact, deleting that one line and the
sentence before it is the entire edit — the draft still stands without it.


## Proven vs inference

**Proven (read from code, captures, vendor documents, or the owner's real logs):**
- USB discovery is VID/PID-only; `identify()`/`is_cr30()` are wired into no user path;
  `open_usb` takes `found[0]` with no multi-candidate probe (workflow/cr30/device.py,
  discovery.py; grep of ui/ and the bridge).
- The BLE unconfirmed-candidate fallback (`ok = [confirmed] or cands`,
  ble.py `BleTransport.open`).
- `TILE_SIGNATURE` is inert on the one other unit with data (4.69 %R off, 94× tol —
  code comment + STATUS.md + PRIORART-001); BLE carries no protocol gate flag.
- The second unit's axis is 400 nm/31 bands: 67 `BB 01 09` headers in
  PRIORART-001, checked directly in the capture JSON for this report.
- SerialTransport opens with pyserial defaults (`dsrdtr=False` disables flow control
  only) and a 60-byte calibration frame is written at CR30 measure start before any
  identification (transport.py, device.py.calibrate, tab_measure.py:5696).
- Job 2 end to end: all seven B2-1 warnings sit immediately after closeEvent's
  geometry/tab settings writes, none is preceded by `abort()`'s "process killed" line,
  and the leak is cleanup() killing the QProcess while `_process.finished →
  _on_finished` is still connected (chromiq.log; argyll_runner.py:503-521, 402;
  main_window.py:2424/2455). Every in-protocol helper ending exits 0
  (chromiq_chartread.c).
- CHNSpec is the maker; chnspec@colorspec.cn is published on two vendor-owned sites;
  CR10/20/30 all specify 400–700 nm / 10 nm / 45/0 / USB+Bluetooth (vendor brochure);
  the research repo is public (GitHub API).

**Inference (stated as such in the body):**
- That QProcess reports a SIGKILLed child as exit code 9 — consistent with Qt's Unix
  implementation and with every observed log line, but not proven from Qt source here.
- The DTR-reset harm to auto-reset boards (Arduino/Marlin-style): code-level certain
  that DTR is asserted; the reset consequence is standard behaviour of those boards,
  not demonstrated on hardware in this round.
- The shutdown-time orphan-chartread relaunch for a non-CR30 engine session that has
  emitted no event yet — derived from `_engine_should_fall_back` + `_launch_stock`,
  never observed.
- Marlin/GRBL treating our frames as inert — analysed against their command sets, not
  tested; unknown firmwares are unbounded.
- That every CR30 advertises `ffe0`, that a factory-fresh unit confirms, and that
  BLE name == `second_id` beyond his unit — single-unit observations, flagged as the
  cheapest experiments to run.

