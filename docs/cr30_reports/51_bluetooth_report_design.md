# 51 — The CR30 Bluetooth report, challenged and redesigned

**Task**: break the diagnostic tool built in `6e78ce62`, then redesign it so ONE run by a
remote Windows user extracts the most information possible. Every claim below is from
real code (cited by path), a named trusted source (bleak's own source in `.venv`, or a
fetched page), or something actually run here. Transport faked throughout — no real
Bluetooth touched.

## Status

- [ ] 0. Ground truth read: `collect()`, UI wiring, `ble.py`, script, tests
- [ ] 1. WinRT vs CoreBluetooth — what genuinely differs (from bleak's source)
- [ ] 2. What is missing from the report
- [ ] 3. Extended tests / user questions — designed and pruned
- [ ] 4. Breaking the tool as built
- [ ] 5. Redaction and privacy judgment
- [ ] 6. The seven tests judged
- [ ] 7. The standalone script — keep or kill
- [ ] 8. Implementation plan, questions list, cuts, rating

---

## 0. Ground truth read

Code read in full: `workflow/cr30/bluetooth_report.py` (170 lines),
`ui/main_window.py::_run_cr30_bluetooth_report` (+ `_launch_tool`, `_open_tools_menu`,
`_on_measurement_active`, `_refresh_masthead_availability`),
`workflow/cr30/ble.py` (`discover`, `BleTransport.open`, `_on_notify`),
`workflow/cr30/measure_bridge.py` (`DeviceReader`, `_open_ble`, `REMEMBERED_ADDRESS_KEY`),
`scripts/cr30_bluetooth_report.py` (current state, incl. the owner's pairing rewrite),
`tests/test_cr30_bluetooth_report.py`. Trusted sources used: **bleak 3.0.2's own
installed source** at `.venv/lib/python3.14/site-packages/bleak/` (the very code the
bundle ships — `ChromIQ.spec` packages winrt/dbus backends per its own comments),
CPython 3.14's `platform.py`, Qt's `qwindowscontext.cpp` (code.qt.io), Microsoft's
`OleInitialize` reference (learn.microsoft.com), and bleak's troubleshooting page
(bleak.readthedocs.io). Everything dynamic was run here with the transport faked;
no scanner or client ever touched real radio.

---

## 1. WinRT vs CoreBluetooth — what genuinely differs (from bleak 3.0.2's source)

### 1.1 THE HEADLINE: WinRT requires an MTA thread, and the tool runs on Qt's main thread

The chain, every link cited:

1. `bleak/backends/winrt/scanner.py::BleakScannerWinRT.start` calls `await assert_mta()`
   before anything else ("Callbacks for WinRT async methods will never happen in STA
   mode if there is nothing pumping a Windows message loop").
2. `bleak/backends/winrt/util.py::assert_mta`: on an STA thread it sets a Win32 timer
   and waits **0.5 s** for the callback; if no Windows message loop dispatches it, it
   raises `BleakError("Thread is configured for Windows GUI but callbacks are not
   working.")`. A thread whose COM is *uninitialized* is fine ("All is OK if not
   initialized yet. WinRT will initialize it." — as MTA).
3. Qt's Windows platform plugin calls `OleInitialize(nullptr)` in the
   `QWindowsContextPrivate` constructor (qtbase,
   `src/plugins/platforms/windows/qwindowscontext.cpp`) — i.e. on the GUI thread at
   QApplication start.
4. Microsoft, `OleInitialize` reference: *"OleInitialize calls CoInitializeEx
   internally to initialize the COM library on the current apartment. Because OLE
   operations are not thread-safe, OleInitialize specifies the concurrency model as
   single-thread apartment."* So **ChromIQ's Qt main thread on Windows is STA.**
5. `ui/main_window.py::_run_cr30_bluetooth_report` runs
   `asyncio.new_event_loop().run_until_complete(collect())` **on that main thread**,
   with Qt's message pump blocked for the duration (the dialog even says "The window
   will be unresponsive while it looks").

Consequence: on the pharmacist's Windows machine, the diagnostic AS BUILT almost
certainly dies at stage 1 within ~0.5 s with `BleakError: Thread is configured for
Windows GUI but callbacks are not working.` — and the report's own advice for a failed
scan then **misdirects him** to "check that Bluetooth is switched on … a privacy
setting". The tool built for the one untested platform is itself broken on that
platform, and lies about why.

Two corollaries, both important:

* **This is NOT the cause of his original failure.** The Measure tab's BLE open runs
  on the bridge's worker thread, never the Qt main thread
  (`measure_bridge.py::DeviceReader` docstring: "Both the open and the read happen on
  whichever worker thread the bridge is using, never on the Qt main thread"), and a
  fresh Python thread is COM-uninitialized, which `assert_mta` documents as safe. His
  bug is still unexplained — which is exactly why the report must survive on Windows.
* **The fix is a worker thread, not `allow_sta()`.** bleak's troubleshooting page
  offers `allow_sta()` only "for graphical applications properly integrated with
  asyncio" — ours is not integrated; the Qt loop is *blocked* during
  `run_until_complete`, so STA callbacks would still never arrive. Running `collect()`
  on a `threading.Thread`/`QThread` fixes the STA hazard AND the frozen GUI in one
  move. (CoreBluetooth has no apartment concept; the cb backend contains no
  counterpart check — which is why one Mac never saw any of this.)

### 1.2 Pairing: WinRT does NOT require it — the incompatibility theory is unsupported

* Front-end (`bleak/__init__.py`): `BleakClient(..., pair: bool = False)`;
  `connect()` passes `self._pair_before_connect`. Pairing is **opt-in**.
* `bleak/backends/winrt/client.py::connect(pair: bool)`: `if pair: await
  self.pair(**kwargs)` — nothing pairs unless asked. The connect itself is:
  `BleakScanner.find_device_by_address(...)` → `BluetoothLEDevice.
  from_bluetooth_address_async(...)` → `GattSession.from_device_id_async(...)` with
  `maintain_connection = True`, under the source comment *"Windows does not support
  explicitly connecting to a device. Instead it has the concept of a GATT session
  that is owned by the calling program."* No `DeviceInformation` enumeration, no
  pairing ceremony, no bonding precondition anywhere on the path.
* The only way pairing enters uninvited is authenticated characteristics: bleak's
  front-end `pair()` docstring — *"This method is not available on macOS. Instead …
  the user will be prompted to pair the device the first time that a characteristic
  that requires authentication is read or written."* The CR30's `ffe1` has been
  written and notified unpaired on the Mac with **no pairing prompt ever appearing**
  — so it requires no authentication, and Windows has no reason to demand a bond
  either.
* The owner: *"i don't see how you would actively pair the device"* — no pairing UI
  exists on the instrument. Consistent with all of the above: a plain
  advertise-and-connect BLE peripheral.

Verdict: our "you do not need to pair" line is right; "WinRT needs pairing and the
CR30 cannot pair" is dead as a root-cause theory. **What WinRT does require is a live
advertisement at connect time** (`find_device_by_address` is a scan;
`BleakDeviceNotFoundError` if it never advertises within the timeout) — so every
connection-shaped failure on Windows collapses back into "was it advertising, and
did we see it", which the report's stage 1/2 already target. That also kills the
"type in an address to try directly" probe idea: **no backend can connect without
first sighting an advertisement** (WinRT cited above; CoreBluetooth needs the
CBPeripheral from a scan — `BleakClient(address_string)` triggers one).

### 1.3 The rest of the genuine differences, judged

| Difference (cited) | Add to report? |
|---|---|
| **Typed unavailability.** Both backends raise `BleakBluetoothNotAvailableError` with a `reason`: `NO_BLUETOOTH`, `NO_BLE_CENTRAL_ROLE` ("classic-only adapters", the enum's own words), `POWERED_OFF` (winrt/scanner.py checks `BluetoothAdapter.get_default_async()`, `is_central_role_supported`, `RadioState`); CoreBluetooth adds `DENIED_BY_USER` / `DENIED_BY_SYSTEM` (CentralManagerDelegate.py). | **ADD** — catch it, print `reason.name`, branch the advice. This answers "does the machine have BLE at all vs Classic only" and "was permission refused" *from bleak itself*, no questionnaire needed. |
| **Windows build gates features.** winrt/scanner.py: `transmit_power_level_in_dbm` "introduced in Windows build 19041" (fallback in source); `allow_extended_advertisements` logs "not available in this OS Version" on AttributeError. CPython 3.14 `platform.py` maps build ≥22000 → release "11" — so `platform.release()` hides the build. | **ADD** `platform.version()` (e.g. `10.0.22631`) to the header. One line, zero cost. |
| **Address format.** WinRT: MAC, `":".join(f"{x:02X}")` (`_format_bdaddr`). CoreBluetooth: `peripheral.identifier().UUIDString()` — a per-Mac UUID. | **ADD** the *remembered* `cr30_ble_address` value to the header. The setting is per-host (QSettings), so a Mac UUID can never poison a Windows install — but the report should show what is stored, because `_open_ble` tries it first and the reader of the report needs to know which path ran. No code copes badly today: `_open_ble` falls back to discovery on any failure and re-identifies whatever answers. |
| **ADV/SCAN_RSP split.** Windows "does not combine advertising data with type SCAN_RSP with other advertising data like other platforms, so we have to do it ourselves" (RawAdvData docstring) — bleak merges; names may arrive only via scan response, active mode default covers it. | No action — bleak handles it. Worth one report line only if a candidate shows `(no name)`. |
| **No OS-level UUID filter on WinRT** (scanner source: "we can't make use of the service_uuids filter here"). We filter in Python anyway. | Noise. |
| **UUID string form.** bleak's base scanner lowercases the *filter* but compares advertised UUIDs raw (`backends/scanner.py::is_allowed_uuid`) — bleak itself banks on backends delivering lowercase canonical strings. Our `startswith("0000ffe0")` and `ble.discover`'s exact match inherit that bet. Unverifiable from here (pywinrt Guid projection not fetchable). | **Covered by a report change**: print the raw `service_uuids` strings for EVERY device (names still redacted). Today a form mismatch would file the CR30 under `(named device, hidden) services=1` — the redaction would hide the one field that could prove our matcher wrong. |
| **Connect timeout.** bleak front-end default is 30 s, and the changelog note in source says "Changed default connect timeout from 10 to 30 seconds" (2.1.1) — upstream learned 10 was too short. `ble.discover(verify=True)` uses `BleakClient(entry["address"], timeout=8.0)`. | **ADD (small)**: raise the verify connect timeout toward bleak's default on the diagnostic path, and record per-candidate connect duration. Not a settings change — a diagnostic-path constant. |
| **Longer `discover` timeout on Windows.** bleak's own default is 5.0 s (front-end overloads); we already scan 20 s. No source says Windows needs more. | Noise as a blind change. Instead: **timestamp each candidate's first sighting** (a `detection_callback` is supported on all backends) — then a future report *shows* whether a shorter/longer window matters, and any timeout change is evidence-based. |
| **MTU.** WinRT exposes `max_pdu_size` via GattSession events (client.py). Our BLE frames are 10 bytes; the default ATT payload is larger, and bulk replies are already reassembled from fragments (`ble.py` module docstring). | Noise. Do not add. |
| **Packaged-app capability.** The `bluetooth` appx capability applies to packaged (MSIX/UWP) apps; ChromIQ ships as a plain PyInstaller executable. No bleak source or doc reachable from here makes a desktop-app permission check; CoreBluetooth's `DENIED_*` reasons and the captured exception text cover whatever the OS actually refuses. | Noise — speculation. The typed-reason branch (above) is the honest version of this. |

---

## 2. What is missing from the report — the verdicts in one list

**Add (each earns its place):**
1. `platform.version()` — the Windows build (S1.3). `platform.release()` says "10"/"11"
   only; the build gates WinRT behaviour bleak itself branches on.
2. **Typed failure reasons** — catch `BleakBluetoothNotAvailableError`, print
   `exc.reason.name`, branch advice: `NO_BLUETOOTH` → adapter/driver question becomes
   legitimate; `NO_BLE_CENTRAL_ROLE` → "your adapter is Bluetooth Classic only, a
   USB BLE dongle fixes this" (the enum's own doc: "classic-only adapters");
   `POWERED_OFF` → the on/off advice we currently give for *everything*;
   `DENIED_BY_USER`/`DENIED_BY_SYSTEM` (macOS) → System Settings → Privacy →
   Bluetooth.
3. **Origin + environment line**: `frozen` vs source (`getattr(sys, "frozen", False)`),
   and which bleak backend module actually loaded — the whole point of the in-app
   tool is "the app's own stack"; the report should prove which stack ran.
4. **Remembered address**: the stored `cr30_ble_address` value (or "none"), because
   `_open_ble` tries it before scanning and a report reader must know which path the
   real app would have taken.
5. **Raw service UUID strings for every device** (names stay redacted) — otherwise a
   UUID-form mismatch on WinRT is invisible behind `services=1` (S1.3).
6. **Per-candidate first-sighting timestamps and connect durations** — turns every
   future timing argument into data.
7. **Stage-3 per-entry truth**: print `confirmed`, `axis`, `error` per candidate,
   and fix the verdict logic (§4.1 — it is wrong today).

**Do not add (noise):** MTU, blind timeout increases, appx-capability speculation,
pairing-state queries (§1.2 — nothing to pair), a manual "type an address" probe
(§1.2 — no backend connects without a sighted advertisement), asking the user
anything a Python call answers (OS version, radio state, adapter LE support).

---

## 3. The extended tests and user questions

Design rule applied, hardest: *a question whose answer changes nothing is not asked.*
Every question below is gated — it appears only in the branch where its answer forks
our next action — and its answer is written into the report as a `USER ANSWERS`
section, so one run carries both machine facts and human observations.

### Questions that survive (three, gated)

**Q1 — the indicator.** Asked after every scan that involved a connect attempt (a
candidate existed), as a three-way choice recorded verbatim:
> "While ChromIQ was looking, did the connection indicator appear on the
> instrument's display? — Yes / No / I was not watching"

Why it earns its place: it is the only observation that splits the link at the
instrument's end. Candidate seen + we refused + **indicator shown** → our request
arrived and the failure is in the exchange (our bug or the OS GATT layer): we go read
our own protocol code. Indicator **not** shown while we connected → the connect never
reached the radio link (driver/stack): we stop suspecting our protocol. "Not
watching" → the closing window asks him to run it once more, watching — the tool
explicitly supports a second run for exactly this. (The current tool already tells
him to watch but never collects the answer — the observation evaporates.)

**Q2 — the Windows device list, worded passively.** Asked ONLY when stage 1 failed
or found no ffe0 advertiser, and only on Windows:
> "Without clicking anything in it: open Windows Settings → Bluetooth & devices →
> Add device → Bluetooth, wait ten seconds, and tell me — does any device appear
> whose name you do not recognise as one of your own? You do not need to select or
> add it; just look and close the window."

Why: it is an independent scanner owned by the OS. Our scan empty + Windows list
shows it → the advertisement reaches the adapter and the fault is in *our* stack
(bleak/backend/threading) — gold, because that is the case only we can fix. Both
empty → the advertisement is not arriving (held/asleep/range/radio) and we stop
auditing our code. The wording never says "pair": per the owner there is nothing to
pair, and an instruction to do an impossible thing is the failure already fixed twice
(`2c29945d`). If he volunteers that he tried to add it and what happened, the free
text goes in the report — but the tool does not request it.

**Q3 — the phone app, as an action not a survey.** Offered ONLY when stage 2 found
nothing, phrased as the rescan it enables:
> "If the CR30's phone app is installed on a phone nearby, switch that phone's
> Bluetooth off — the instrument accepts one connection at a time and stops
> advertising while the app holds it. Then press the instrument's button once and
> choose Scan again."

Why: "is the app installed?" alone changes nothing — the *action plus rescan* does.
First scan empty + post-action scan finds it → root cause identified (held), report
says so, no code change needed anywhere. Both empty → holding is eliminated and the
remaining suspects shrink to sleep/range/radio. The rescan loop (a "Scan again"
button on the results window) is the mechanism; Q3 is just its best script.

### Questions REJECTED, with reasons
* "Pair it in Windows settings and see" — nothing to pair on this device (owner,
  quoted above); would instruct the impossible.
* "Which Windows version / is Bluetooth on / does your adapter support LE" — the
  program answers all three better (§2 items 1–2).
* "What does Device Manager say about your adapter" — asked blind it is noise; it
  becomes legitimate only inside the `NO_BLUETOOTH` branch, where the report itself
  can print one line of advice ("if Device Manager shows no Bluetooth adapter, this
  computer needs a BLE dongle") — advice, not a question the tool waits on.
* "Does it work on another machine / with nRF Connect on your phone" — high effort,
  and the answer forks nothing we do next that Q2 does not already fork more cheaply.
  Kept as one closing-advice sentence for the both-scans-empty dead end, not a
  question.

### Extended opt-in probes (tool-driven, no user knowledge needed)

**P1 — the deep probe** (the standalone script already does this; the app must too):
for each candidate, connect and record the full service/characteristic table with
properties, the first 32 reply bytes in hex, and the parsed axis. This is the
highest-information probe for the "Windows sees it, ChromIQ refuses it" case — it
distinguishes "wrong characteristic layout" from "no reply" from "reply in an
unexpected shape", which stage 3's boolean cannot. Opt-in behind one button
("Look closer at the device that answered"), same safety envelope: `READ_MEASUREMENT`
only (never `TRIGGER_UNSAFE` — `ble.py`'s own warning: a trigger under the cap
rewrites the white reference).

**P2 — rescan loop** with situational instructions (Q3/press-the-button), replacing
the current single-shot run.

**REJECTED probe: manual address entry / direct connect without a sighting.** Cited
in §1.2: `find_device_by_address` is itself a scan on WinRT, and CoreBluetooth needs
the peripheral object from a scan — a "direct" connect cannot bypass advertisement
on either backend, so the probe can never learn more than a rescan does.

---

## 3b. "Use the finding as a fix for THIS user" — the repair step (owner's addition)

### R1 — remember the confirmed address (OFFER IT; the only repair worth having today)

When stage 3 **confirms** a candidate (axis 400/10/31 answered), the tool offers to
write its address to `cr30_ble_address` — the exact key
`DeviceReader._remembered_address()` reads (`measure_bridge.py`). What that repairs,
honestly: the app then skips the discovery scan at open (`_open_ble` tries the
remembered address first — measured on the owner's Mac: find 15.42 s vs connect
2.33 s, so it removes the whole slow/flaky part), which rescues precisely the
installs where scanning is unreliable or slow but connection works.

The five constraints, checked:
1. *Never silently* — it is a button with its own explanation (wording below).
2. *Reversible and visible* — the wording names the undo. There is no Settings UI
   for this key today; until one exists the honest undo is the tool itself: a
   "Forget the remembered instrument" button shown whenever the key is set. (One
   more reason the tool should print the key's current value, §2 item 4.)
3. *Does not bury the bug* — the offer and the confirmation share one window and
   one breath (wording below): applying the repair does not close the report flow,
   and the saved report records that the repair was applied.
4. *Honest about proof* — "answered as a CR30 just now", not "will always work".
5. *Does not weaken safety* — doubly guarded: the tool only offers an address it
   has itself protocol-confirmed, AND `_open_ble` re-runs `dev.identify()` on every
   open of a remembered address regardless (measure_bridge.py — the check added in
   `1de3f3af`), falling back to discovery when it fails. A wrong stored address can
   cost seconds, never a calibration frame to a stranger.

Proposed wording (§M rules apply — this goes to §M-PROPOSED, not into a tab, until
approved):

> **"A CR30 answered at address {address}."**
> ChromIQ can remember this address so it connects there directly next time instead
> of searching. This helped just now; if the instrument ever stops answering there,
> ChromIQ searches again by itself, and you can undo this by running this tool again
> and choosing "Forget the remembered instrument".
> Even if you use this, please still send the report — it is how the underlying
> problem gets fixed for everyone.
> [ Remember it ]  [ Not now ]

### R2 — persist a longer discovery timeout (REJECT, for now)

There is no such setting to write: `BleTransport.open` calls
`discover(timeout=min(self.timeout, 12.0))` — a hard-coded cap, no settings key.
Inventing one on zero evidence is a blind knob. The evidence-first path: the
first-sighting timestamps (§2 item 6). If a report ever shows the candidate first
seen at, say, 14 s — beyond the app's 12 s cap but inside the tool's 20 s window —
THEN a setting (or simply a bigger cap) is justified, the report having proved it.
I propose the timestamps now and the setting never-until-proven.

### R3 — "a candidate answers correctly while `ble.discover` rejects it" (KEEP, as a loud line)

With stage 3 fixed (§4.1) and P1 in place this becomes detectable: deep probe parses
the right axis while `ble.discover`'s 1.6 s poll window missed it. The report prints,
in capitals, that this is OUR bug, and R1 is offered as the workaround in the same
window — the workaround and the bug report physically inseparable.

### The net-loss question, answered plainly

R1 can only be offered when the tool's own scan+confirm SUCCEEDED — so the
"install works by accident and hides the fault" case is narrow: it hides at most a
*flaky-scan* fault, and only from the user's daily experience, not from us — the
report he is asked to send in the same window records both the flakiness and the
repair. The one genuinely dangerous variant would be offering to remember an
UNCONFIRMED address (it would bypass nothing today thanks to `_open_ble`'s identify,
but it would normalise trusting `ffe0`, which `ble.py`'s history comment exists to
forbid). The design therefore never offers R1 from stage 2, only from a stage-3
confirmation. With that line held, I see no path to net loss.

---

## 4. Breaking the tool as built

### 4.1 PROVEN: stage 3 inverts its own verdict — twice

`collect()` reads `accepted = await ble.discover(timeout=15.0, verify=True)` and
branches on emptiness. But `ble.discover` appends every `ffe0` advertiser to its
result **before** verification and sets a `confirmed` flag per entry (`ble.py`) —
`BleTransport.open` filters on `c["confirmed"]`; `collect()` never looks at it.
Driven here with the transport faked (script in this session, real `collect()`):

* **Case A** — one advertiser, `confirmed: False, error: TimeoutError` (a hobby
  HM-10 that answered nothing — a device the real app would REFUSE). The report
  printed: `ChromIQ ACCEPTED 1 device(s) … So the instrument is reachable over
  Bluetooth from this computer.` **The central conclusion, inverted.**
* **Case B** — stage-3's rescan returns `[]` (device went to sleep or got grabbed
  between the 20 s stage-1 scan and the separate 15 s stage-3 scan). The report
  printed `ChromIQ REFUSED every candidate` — nothing was refused; the device
  vanished between two scans, a completely different diagnosis.

Fix: three verdicts from the flags — confirmed (name it, offer R1) / seen but not
confirmed (print per-entry `axis`/`error`, this is the "our bug or a stranger"
case) / not seen on the second scan (say THAT, and offer the rescan loop instead of
a verdict). Also print each entry's fields deliberately rather than `say(f"  {c}")`
dumping a raw dict.

### 4.2 The scenario table

| Scenario | What actually happens (cited/run) | Verdict |
|---|---|---|
| No adapter at all | bleak raises `BleakBluetoothNotAvailableError(NO_BLUETOOTH)` (winrt scanner start / CB CentralManagerDelegate); stage-1 `except` catches, prints type+msg. Works, advice generic. | Improve via reason branch (§2.2). |
| Bluetooth off | Same, `POWERED_OFF`, message "Turn on Bluetooth and try again" from bleak itself. | OK; branch makes it cleaner. |
| Permission refused | macOS: `DENIED_BY_USER`/`DENIED_BY_SYSTEM` typed; caught. Windows: no permission concept surfaces in the winrt backend for a desktop app — whatever the OS throws is captured as text. | OK. |
| **Windows, at all** | **Dies in ~0.5 s at `assert_mta` with the "Thread is configured for Windows GUI" BleakError (full chain §1.1), then misadvises "check Bluetooth is on".** | **The tool's worst defect. Thread it.** |
| 40 devices nearby | 40 redacted lines; report stays sendable; loop is O(n) prints. | OK. |
| ffe0 device that is not a CR30 and hangs on connect | Bounded: `BleakClient(..., timeout=8.0)` per candidate + ≤1.6 s poll (`ble.discover`); exception lands in `entry["error"]`. But §4.1 then reports it as ACCEPTED. | Bounded; verdict wrong. |
| Scan outlasts patience | No cancel, no progress; worst case ≈ 20 + 15 + N×9.6 s of frozen GUI with a wait cursor, while the dialog promised "about half a minute". | Thread + progress lines + cancel button. |
| 35 s frozen GUI, acceptable? | No. On macOS it merely beachballs; on Windows the same blocking *causes* §1.1. The freeze is not a cosmetic tradeoff, it is the bug. | **Must be threaded.** |
| Save dialog cancelled | `if not path: return` — the whole report, 35+ s of scanning and any user answers, is **discarded silently**. | Real flaw. Keep the text, reoffer, and always also write a fallback copy next to the app log; add "Copy to clipboard". |
| Read-only location | `write_text` raises → warning box → `return` — text lost the same way. | Same fix: loop back to the dialog with the text intact. |
| Running it twice | Works. Each run leaks one never-closed asyncio loop (`asyncio.new_event_loop()` without `close()`); harmless at this scale. | Cosmetic; the threaded rewrite should close its loop. |
| During a live measurement | **Locked, verified in code**: `tab_measure.measurement_active.emit(True)` (line 6057, in `_on_start`, which is also the path that opens the CR30 bridge at 5983) → `_on_measurement_active` sets `_measuring` → `_refresh_masthead_availability` sets `BUSY_MEASURING` → masthead greys Tools with the "Not while a measurement is running" tooltip, and `_open_tools_menu` returns when the button is disabled — explicitly also for the ⌘T shortcut (its own docstring, #164). | Holds. |
| Chart/profile build running | Same mechanism, `BUSY_CHART`/`BUSY_BUILDING`. | Holds. |
| bleak returns a list not a dict | Dead code: bleak 3's `discover(return_adv=True)` is typed `dict[str, tuple[BLEDevice, AdvertisementData]]` (front-end overloads). The `isinstance(found, dict)` fallback can never run and is untested by construction. | Delete or leave; it is noise either way. |

---

## 5. Redaction and privacy, judged

**What it does right.** Non-candidate names → `(named device, hidden)`; addresses
truncated to the last 6 characters (≈1.5 octets of a MAC on Windows, 6 hex digits of
a per-Mac UUID on macOS — neither re-identifies a neighbour); the save dialog's
closing text says why it must travel privately; both artefacts instruct a DM/email,
matching the project's no-personal-data-published rule. The report contains no
username, no hostname, no paths.

**What still travels, and whether it should:**
* The **candidate's advertised name** — which `ble.py` documents as the unit's OWN
  device-id string, i.e. effectively a serial. Correct to include (we need it), but
  the closing window should say "the report names your instrument's own id" so the
  sender is not surprised. One sentence.
* **Counts and RSSI of bystanders** — fine; a count is not an identity.
* **Exception text** is printed verbatim in both stages. bleak's own messages carry
  addresses at most (`BleakDeviceNotFoundError` embeds the address we targeted — a
  candidate, so already disclosed). `BleTransport.open`'s ConnectionError DOES embed
  bystander candidate names ("Seen: …") — but `collect()` never calls `open`, so no
  leak today. The redesigned tool must keep that property: exceptions from
  `ble.discover` only.
* Proposed change §2 item 5 (print every device's raw service UUIDs) trades a sliver
  of fingerprintability (a device's advertised services) for the ability to catch a
  matcher bug. Service UUIDs are standard identifiers, not names; with names and
  addresses still redacted I judge it acceptable, and it should be called out in the
  same closing sentence.
* P1's hex dump contains the instrument's own last reading — a colour. Harmless;
  say so in the probe's opt-in text.

Verdict: adequate as built; keep the two-sentence disclosure additions when the
report grows.

---

## 6. The seven tests, judged (run: `7 passed in 0.22s`; three mutations driven)

Mutations were applied to `workflow/cr30/bluetooth_report.py` with a landing
assertion, run, and restored (`git checkout`, tree verified clean):

| Mutation | Result | Meaning |
|---|---|---|
| M1: invert the stage-3 verdict (`if not accepted:` → `if accepted:`) | **7 passed — SURVIVES** | The tool's single most important conclusion has no test. Nothing pins ACCEPTED to `confirmed=True`, REFUSED to anything, or the empty-rescan case. §4.1's two proven misdiagnoses were sitting behind this hole. |
| M2: print bystander names (`shown = name`) | 1 failed — caught | The redaction IS guarded, by behaviour, on the real `collect()`. Good test. |
| M3: `_bleak_version()` → constant `"x"` | 1 failed (the ImportError test) — caught | `test_it_reports_bleak_as_present` alone is near-vacuous (green under M3); it is honest only as a pair with test 2. Acceptable, worth a comment. |

Other findings against the day's checklist:
* **Vacuous assertion**: test 7's closing `assert "ChromIQ's own discovery" in text
  or "discovery" in text.lower()` — the stage-3 *header* always contains
  "discovery", so the disjunction can never fail. The test's real teeth are the
  `_Forbidden` BleakClient (good, and a behaviour test by design — its docstring
  even explains why the grep-the-source version was rejected). Drop the trailing
  assert or pin it to the specific line.
* **Stand-ins vs real types**: `_Scanner.discover` returns
  `dict[addr, (dev, adv)]` — exactly bleak 3's shape (front-end overloads), with
  `local_name`/`service_uuids`/`rssi` attributes mirroring `AdvertisementData`.
  Faithful. The `_run` helper monkeypatches `ble.discover` with a coroutine-shaped
  lambda — also faithful to the call site.
* **Uncovered**: stage 3's exception branch; every UI behaviour
  (`_run_cr30_bluetooth_report` has zero tests — the save-cancel data loss of §4.2
  ships unguarded); the per-entry `confirmed`/`axis`/`error` rendering; redaction
  inside exception text (currently a non-issue, becomes one if anyone ever calls
  `open`).
* Each `_run` creates an event loop and never closes it — six leaked loops per run.
  Cosmetic under pytest, but the suite's own hygiene rules would want
  `asyncio.run()` here.

---

## 7. The standalone script — keep or kill

**Keep — it is now a diagnostic instrument in its own right, because §1.1 exists.**
The script runs on a console thread: COM uninitialized, WinRT initializes it MTA
(`util.py`'s own comment), so on the pharmacist's machine **the script would work
where the in-app tool as built fails**. "Script sees the instrument, app does not"
is not drift — it is the single cleanest way to localise a fault to ChromIQ's side
(bundled bleak, threading, packaging) versus the machine's. The commit message's
argument (the bundle's bleak is the suspect, so the app must test itself) and this
one are complements, not rivals: each report should carry an `origin:` line
(`app-bundle` / `standalone-script`, plus versions) so the pair can be diffed.

Second argument: the script reaches people before or without the app (the
printerknowledge audience includes ArgyllCMS-manual users who run ChromIQ nowhere),
and it is currently the *richer* probe (characteristics dump, hex bytes) — P1 ports
that INTO the app rather than deleting it from the script.

The drift cost is real but cheap to cap: one parity test in `tests/` asserting the
script's constants equal the library's (`READ_MEASUREMENT == ble.frame(0x02, 0x10)`
— byte-identical today, checked by eye against `ble.frame`'s checksum rule; `FFE0`
string == `ble.FFE0_SERVICE`; the redaction marker; the scan window), so the script
cannot silently disagree about the one frame it is allowed to send. The script's
free-standing docstring already carries the owner's corrected pairing text; the
in-app dialog should be brought to the same wording in the same commit.

---

## 8. Implementation plan, the questions, the cuts, the rating

### The plan (ordered; 1–3 are the ones that decide whether his one run is worth anything)

1. **Move `collect()` off the GUI thread.** A worker thread with its own asyncio
   loop (created and closed there), progress relayed by signal into a small
   non-modal window with a live line ("scanning… 12 s, 9 devices, 0 candidates")
   and a Cancel. This simultaneously fixes the Windows STA failure (§1.1), the
   frozen GUI, and the impatience scenario. Do NOT reach for `allow_sta()` — wrong
   tool here (§1.1).
2. **Fix stage-3 semantics** (§4.1): three verdicts driven by `confirmed`/presence;
   per-entry `name/address/rssi/axis/error/confirmed` lines; never a verdict from
   mere list-emptiness.
3. **Typed-reason branch** for `BleakBluetoothNotAvailableError` with per-reason
   advice (classic-only adapter finally becomes diagnosable, §2 item 2).
4. **Header additions**: `platform.version()`, frozen/source origin, bleak backend
   module, remembered `cr30_ble_address` (or "none"), report format version.
5. **Stage-1 detail**: raw service-UUID strings for every device (names still
   redacted); first-sighting timestamp per candidate via a detection callback.
6. **The rescan loop**: results window with "Scan again", carrying the situational
   instructions (press the button now; switch the phone's Bluetooth off).
7. **The three questions** (below), asked in their gates, answers written into a
   `USER ANSWERS` section of the report.
8. **P1 deep probe**, opt-in, ported from the script: services/characteristics
   table, first 32 bytes hex, parsed axis; `READ_MEASUREMENT` only; loud OUR-BUG
   line when it succeeds where `ble.discover` refused (R3).
9. **R1 repair offer** on a stage-3 confirmation: write `cr30_ble_address` with the
   §3b wording (via §M-PROPOSED first); "Forget the remembered instrument" button
   whenever the key is set; the applied repair is recorded in the report.
10. **Save flow that cannot lose the report**: keep the text; on cancel or write
    failure return to the dialog; always write a fallback copy beside the app log;
    add Copy-to-clipboard.
11. **Tests**: kill M1 (verdict pinned to `confirmed` in all three branches);
    UI-level test that a cancelled save keeps the text reachable; parity test for
    the script twins; a test that `collect()` runs to completion off the main
    thread; fix test 7's vacuous tail.
12. **Script**: keep; add the `origin:` line; align the app dialog's pairing wording
    with the script's corrected text; nothing else.

I implement none of this outside `tests/`/`scripts/` — items 1–10 are proposals for
the owner to implement or approve; item 11's new tests and item 12's script line I
can write on request.

### The questions, final (three, gated — §3 has full wording and forks)
1. **Indicator on the instrument's display?** (after any connect attempt) — splits
   instrument-end arrival from non-arrival; forks which side of the link we debug.
2. **Windows "Add device" list, looked at passively?** (only when our scan failed or
   saw nothing, Windows only) — an independent scanner; forks "our stack" vs "the
   radio path". Never words it as pairing; there is nothing to pair.
3. **Phone's Bluetooth off, button pressed, scan again** (only when nothing was
   seen) — an action wrapped around the rescan; forks "held" vs "asleep/absent".

### The cuts
Pairing anything (instruction or question); MTU; blind timeout knobs (R2 rejected
until the timestamps prove a need); manual address entry (§1.2 — cannot work);
appx-capability speculation; questions the program can answer itself; the dead
non-dict branch in `collect()`.

### Rating: 6/10

What earns the 6: the architecture is genuinely right — three stages that separate
"the machine", "the radio neighbourhood" and "our own code" is exactly the shape a
one-shot remote diagnostic needs; redaction was designed in from the first line, not
bolted on; the empty-scan text refuses to blame a nonexistent setting (a lesson
already paid for twice); the in-app-plus-script pairing is, accidentally, a real A/B
instrument; and the honest little touches (import-is-the-test for bleak, the
never-calibrate guarantee stated and behaviour-tested) are the project's house style
at its best.

What holds it at 6: the tool would very likely fail on the exact machine it was
built for — a cited, deterministic chain (Qt STA + blocked pump + `assert_mta`),
after which its own text misdirects the user; its central verdict is inverted in
two driven cases (ACCEPTED for a device the app would refuse; REFUSED for a device
that merely fell asleep), and the mutation that inverts that verdict outright
survives all seven tests; and a cancelled save silently discards everything the run
learned. Three defects, all in the load-bearing path of "one run by a remote user".
Each is cheap to fix, none was caught by the tests, and the first two would have
cost the one thing this tool cannot afford: the pharmacist's single data point,
spent on a report that pointed the wrong way.

## Status (final)

- [x] 0. Ground truth read
- [x] 1. WinRT vs CoreBluetooth (cited: bleak 3.0.2 source, Qt source, MS docs)
- [x] 2. Missing from the report — add/noise verdicts
- [x] 3. Extended tests / user questions — 3 kept, gated; rejects reasoned
- [x] 3b. Repair offers (owner's addition) — R1 offer, R2 reject, R3 loud line
- [x] 4. Breaking the tool — STA chain; two verdict inversions PROVEN by driving collect()
- [x] 5. Redaction judged adequate; two disclosure sentences proposed
- [x] 6. Tests judged; M1 survives, M2/M3 caught; mutations proven to land and restored
- [x] 7. Script: KEEP as the MTA-side of an A/B instrument; parity test proposed
- [x] 8. Plan (12 items), 3 questions, cuts, rating 6/10

---

## Addendum — found on disk during this round

`scripts/cr30-bluetooth-report.txt` (untracked, 2026-08-30 15:08, not produced by
this session) is a **real scan of the development Mac's surroundings**, sitting
inside the repository because the script writes its report "next to this script"
(`REPORT = Path(__file__).resolve().parent / ...`). Two consequences:

1. It confirms the tool live: 43 devices, every name redacted, no candidate — the
   redaction and the 40-devices scenario both hold on a real run.
2. It is one `git add -A` away from publishing a neighbourhood scan — the exact
   thing both artefacts tell the USER never to post publicly, and the project's
   no-personal-data-on-GitHub rule. Proposed (owner to approve): the script should
   write to the user's Desktop or home directory like the in-app tool does, and
   `cr30-bluetooth-report.txt` should be gitignored as a backstop. The file on disk
   should not be committed.
