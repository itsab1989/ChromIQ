# 53 — A general BLE discovery path for the CR30

**Status:** COMPLETE
**Date:** 2026-08-30
**Context:** `v4.1.5-beta.3` tagged. A CR30 owner on Windows has USB working and
cannot connect over Bluetooth. Bluetooth has only ever worked on the author's
Mac. His unit is a different production batch (different serial prefix) and the
vendor settings window exposes no Bluetooth control, so we cannot establish
whether his unit HAS the radio.

**Constraint honoured:** no CR30, no serial device, no Bluetooth hardware was
touched in producing this report. Every runtime fact below came from reading
installed library source, the research repo's stored captures, or the Bluetooth
Core Specification.

Every claim is tagged **PROVEN** (ran it / cited primary source) or
**INFERENCE**.

## 1. The facts about BLE advertisements

### 1.1 Are service UUIDs optional in an advertisement? YES — explicitly.

**PROVEN (primary source).** Bluetooth *Core Specification Supplement*, Part A,
Data Types Specification (CSS v11, published HTML), on the Service UUID data
types:

> "An omitted Service UUID data type shall be interpreted as an empty
> incomplete-list."

That single sentence settles the load-bearing question. The specification does
not merely permit omission — it *defines the meaning of* omission, and the
meaning is "there may be more services; I have told you about none of them".
The "Incomplete List of …" data types exist precisely because a peripheral is
expected to be unable, or unwilling, to enumerate its services in 31 bytes.

The only AD type with any mandate at all is Flags, and even that is conditional:

> "The Flags data type shall be included when any of the Flag bits are non-zero
> and the advertising packet is connectable, otherwise the Flags data type may
> be omitted."

So: **a conformant BLE peripheral may advertise a name and nothing else, and
expose every one of its services only in the GATT table after connection.**
`ble.py`'s stage-1 filter is therefore not a conservative shortlist — it is a
filter on an *optional* field, and a device that exercises its right to omit
that field is invisible to it.

Source: [CSS Part A, Data Types Specification](https://www.bluetooth.com/wp-content/uploads/Files/Specification/HTML/CSS_v11/out/en/supplement-to-the-bluetooth-core-specification/data-types-specification.html)

### 1.2 What bleak exposes, per backend — they are NOT the same

Read from the installed library, **bleak 3.0.2**, in this project's own venv
(`.venv/lib/python3.14/site-packages/bleak`). All PROVEN by reading the shipped
source.

| Backend | Where `AdvertisementData.service_uuids` comes from | Includes scan response? |
|---|---|---|
| CoreBluetooth (macOS) | `adv_data["kCBAdvDataServiceUUIDs"]` — `backends/corebluetooth/scanner.py:115` | Yes, merged by CoreBluetooth itself before bleak sees it |
| WinRT (Windows) | `args.advertisement.service_uuids`, unioned by bleak across a stored `(adv, scan)` pair — `backends/winrt/scanner.py:52-70, 137-159` | Yes, **but only because bleak does the merge by hand** |
| BlueZ (Linux) | `props["UUIDs"]` — the `org.bluez.Device1` **UUIDs** property — `backends/bluezdbus/scanner.py:187` | Yes, and *more* — see below |

Three backend differences matter to this design:

**(a) Windows is the one platform where the merge is bleak's own problem.**
`backends/winrt/scanner.py` says so in its own docstring, verbatim:

> "Windows does not combine advertising data with type SCAN_RSP with other
> advertising data like other platforms, so we have to do it ourselves."

bleak keeps a `RawAdvData(adv, scan)` pair per address and re-derives the union
on every event. This is correct *once both halves have arrived*. Until then the
union is whichever half arrived. That is a Windows-only window in which
`service_uuids` is legitimately incomplete. **INFERENCE:** if a controller,
driver or environment never completes the SCAN_REQ/SCAN_RSP exchange, that
window never closes and the missing half is missing for the whole scan.

**(b) macOS silently drops "overflow" service UUIDs.** CoreBluetooth defines
`kCBAdvDataOverflowServiceUUIDs`; bleak's CoreBluetooth scanner reads only
`kCBAdvDataServiceUUIDs` and never the overflow key (the constant appears in
`backends/corebluetooth/CentralManagerDelegate.py:68` as a type annotation only,
and is read nowhere). PROVEN by grep across `backends/`. Not a CR30 issue —
overflow is an Apple peripheral-side mechanism — but it is a second, independent
demonstration that `service_uuids` is a lossy view of what a device offers.

**(c) On Linux, `service_uuids` can contain services that were never
advertised.** BlueZ's `Device1.UUIDs` is documented as *"List of 128-bit UUIDs
that represents the available remote services"* — note "available remote
services", not "advertised services". BlueZ populates that property from GATT
discovery once a connection has been made and caches it for known devices.
**INFERENCE (documentation is thin — the BlueZ doc says nothing about the data
source, verified by fetching `doc/org.bluez.Device.rst`):** on Linux, the same
`ble.discover` code can succeed on a device it would have skipped on macOS,
purely because BlueZ had connected to it before. This is the mirror image of the
gap and it makes the current filter's behaviour **host-dependent, not
device-dependent.**

### 1.3 Is there a documented case of services appearing only after connecting?

**PROVEN, by construction:** yes, and it is the normal case, not an exotic one.
Since the Service UUID AD types are optional (§1.1) and GATT service discovery
is the defined way to enumerate a peripheral's services (it is the only
mechanism that is *guaranteed* complete), any peripheral that omits them exposes
its services only after connecting. BlueZ's `Device1.UUIDs` (§1.2c) is a
concrete stack that models exactly this.

### 1.4 The finding that changes the risk assessment: the author's OWN unit may already be relying on the scan response

This was not in the brief and it matters more than the batch hypothesis.

From `captures/raw|public/EXP-BLE-001-scan.json`, the CR30's advertisement as
CoreBluetooth reported it (PROVEN, read from the capture):

* `local_name`: 10 characters
* `service_uuids`: `ffe0`, `fee7` (two 16-bit UUIDs)
* `manufacturer_data`: one company ID, 8 bytes of data
* `service_data`: empty

Encoding that per CSS Part A (each AD structure = 1 length octet + 1 AD type
octet + data):

| AD structure | octets |
|---|---|
| Flags | 3 |
| Complete Local Name (10 chars) | 12 |
| Complete List of 16-bit Service UUIDs (2 × 2) | 6 |
| Manufacturer Specific Data (2 company + 8 data) | 12 |
| **total** | **33** |

The legacy advertising payload is **0–31 octets**
([Silicon Labs, Advertising Data Basics](https://docs.silabs.com/bluetooth/latest/bluetooth-fundamentals-advertising-scanning/advertising-data-basics),
citing the Core Spec). 33 > 31.

**INFERENCE (strong, arithmetic; assumptions stated):** if this unit uses legacy
advertising and is connectable-and-discoverable — it is connectable, we connect
to it, and a connectable advertiser with non-zero flag bits *must* carry Flags
(§1.1) — then **its advertising data does not fit in one packet and at least one
element is carried in the SCAN RESPONSE.** Drop Flags and the remaining 30
octets just fit, which is the one escape; the other is BT 5.0 extended
advertising, unlikely in an HM-10-class module and untested.

The consequence is uncomfortable: **ChromIQ's stage-1 filter may already depend,
on the author's own unit, on a successful scan-response exchange** — an
active-scanning, controller-dependent, per-host behaviour. That is a far more
likely Windows failure mode than "his batch has no radio", and it needs no
second batch to explain anything.

### 1.5 The gap, demonstrated on the real code

**PROVEN — I ran it.** `workflow.cr30.ble.discover` was driven against a faked
`bleak` (no radio touched; `ble.py` imports bleak *inside* the function, so
`sys.modules` substitution reaches it). Two worlds, each containing one CR30
that answers the protocol identically and one bystander:

```
--- A: the CR30 advertises ffe0
    shortlisted : ['AA:00']      connected to: ['AA:00']   confirmed: ['AA:00']
--- B: the SAME CR30, advertising a name and no service UUIDs
    shortlisted : []             connected to: []          confirmed: []
```

Driver: `scratchpad/fake_ble.py` (throwaway; reproduced in §7.4).

So the gap is real and exactly as described: a name-only CR30 is dropped before
any protocol confirmation runs. Worse, the user is then routed to the *wrong*
advice — with `cands` empty, `BleTransport.open` raises the "the device stops
advertising while another central holds it, so disconnect the phone app" message
(`ble.py`, the second `raise ConnectionError`), which sends a user with a
perfectly idle instrument hunting for a phone app that is not there.

**Verdict on the brief's central claim: it is CORRECT.** The rest is not moot.


## 2. Evidence for and against the CR30 advertising without service UUIDs

### 2.1 What we actually know about CR30 advertisements: n = 1, one scan, one host

**PROVEN.** The research repo contains exactly **one** BLE scan capture:
`captures/{raw,public}/EXP-BLE-001-scan.json`, 2026-08-28T14:20:05Z, macOS,
30 devices. In it, one device advertises `ffe0`:

```
service_uuids : 0000ffe0-…, 0000fee7-…
manufacturer_data : {one company id: 8 bytes}
rssi : -60
```

Every other BLE capture in the repo (`-002`, `-003`, `-006`, `-008` … `-017`)
records protocol traffic, not advertisement contents. Two of them record the
peripheral's CoreBluetooth address; the three captures that do are all inside a
**74-second window** on one afternoon.

So the honest statement of what is established:

* **"the author's unit advertised `ffe0` once, on one Mac, on 2026-08-28"** —
  PROVEN.
* **"CR30s advertise `ffe0`"** — NOT established. One unit, one observation.
* **"the author's unit advertises `ffe0` on Windows"** — NOT established; nobody
  has ever run a BLE scan for a CR30 on Windows. `PLATFORM_SUPPORT.md` says so
  in its own words: *"Windows Bluetooth is still tested by nobody, and remains
  the largest untested area in this repository."*

The distinction the brief asked for is therefore sharp and it is uncomfortable:
**we know one unit advertises `ffe0` on one operating system. We know nothing
about all units, and nothing about Windows.**

### 2.2 Is there anything that says it would differ elsewhere?

Nothing direct. Three indirect things, and one is stronger than it looks.

1. **INFERENCE (weak).** `fee7` is Tencent's assigned 16-bit UUID and
   `TRANSPORT_BLE.md` ties it to the vendor's advertised *WeChat mini program*
   support. A WeChat feature is a plausible thing to differ by firmware, region
   or batch. If it were dropped the advertisement gets *smaller*, which helps —
   but it shows the advertisement contents are tied to a feature set that is
   not guaranteed constant.
2. **INFERENCE (weak).** `PLATFORM_SUPPORT.md` already records that the two
   batches differ in the USB bridge PID space (Apple's dext allow-lists exactly
   two PIDs) and that a differently-bridged CR30 "would not bind". Batches
   demonstrably differ in hardware; that is not evidence about the radio, but it
   removes any presumption of uniformity.
3. **The strong one, and it is not about batches at all — see §1.4.** The
   author's own advertisement does not fit in one legacy packet, so at least one
   element rides in the SCAN RESPONSE. Which element is in which packet is a
   *firmware layout choice we have never observed*, and whether the scan
   response ever arrives is a *host* property. If `ffe0` is in the scan response
   on his unit too, and Windows never completes the exchange, ChromIQ's filter
   fails on a unit that is behaving perfectly.

### 2.3 What would settle it

* A BLE scan on a Windows host, near a CR30, printing every device's
  `service_uuids`, `local_name`, `rssi`. Needs *his* hardware — but ChromIQ's
  Bluetooth diagnostic already is that scan (`workflow/cr30/bluetooth_report.py`
  stage 1). Nothing new needs to be written for it.
* A raw HCI capture separating ADV_IND from SCAN_RSP. Needs Linux + `btmon`, or
  a sniffer. Nobody has one.

**Bottom line for the design: the batch hypothesis is unfalsified and
unsupported. The scan-response hypothesis is unfalsified and arithmetically
supported. Both are repaired by the same fix — stop treating the advertisement
as the identity — so the design does not need to choose between them.**


## 3. The widened probe — and the case against it

The sketch: when the normal path finds nothing, connect to devices that
advertise no service UUIDs, read the GATT table, look for `ffe0`/`ffe1`, ask the
axis. I am the critic here, so I will make the case against it first and then
say what survives.

### 3.1 THE BLAST RADIUS, MEASURED

**PROVEN, from `EXP-BLE-001-scan.json` — a real 30-device scan in a real
household, on the machine this feature works on:**

| population | count |
|---|---|
| devices seen in one scan | **30** |
| advertising **no** service UUIDs at all | **26** |
| advertising some service UUID | 4 (one of which is the CR30) |

So the naive widening does not add "a few" probes. **It adds 26, and 26 of 30 is
87 % of everything switched on in the house.** With RSSI gating:

| RSSI floor | no-UUID devices to probe |
|---|---|
| ≥ −50 | 1 |
| ≥ −55 | 3 |
| ≥ −60 | 5 |
| **≥ −65** | **8** |
| ≥ −70 | 10 |
| ≥ −75 | 13 |

The CR30 itself read **−60** in that scan.

### 3.2 THE TIME COST KILLS IT AS A FALLBACK OUTRIGHT

Measured numbers already in the codebase (`measure_bridge._open_ble` docstring,
owner's Mac, 2026-08-30): **find 15.42 s, connect 2.33 s.** `ble.discover` uses
`BleakClient(..., timeout=8.0)`, so a device that refuses or ignores us costs
the full 8 s.

Worst case, unbounded: 15 s scan + 26 × 8 s = **223 seconds**, on the code path
taken when the user presses *Calibrate*. The owner has complained twice that
Bluetooth is slow at 15 s. Even the −65 dBm gate gives 15 + 8 × 8 = **79 s**.

**INFERENCE, and it is not close: a widened probe must never run inside
`ble.discover`, and never on a Measure-tab open.** Any version of this that a
user meets by accident is unshippable.

### 3.3 WHAT A CONNECTION ACTUALLY DOES TO A STRANGER'S DEVICE

Ranked by how bad, and I want the medical one taken seriously:

1. **It can occupy the peripheral's only link slot.** The CR30 itself is
   single-connection and *stops advertising while held* (`TRANSPORT_BLE.md`,
   VERIFIED). That is not a CR30 quirk, it is the common case for cheap
   peripherals. While we hold a stranger's device, **its owner's phone cannot
   reconnect to it.** For a continuous glucose monitor, a hearing aid, or a
   fall-detector, "cannot reconnect for 8 seconds" is not nothing.
2. **It costs battery on a coin cell.** A beacon or tracker that expects to
   never be connected wakes a full connection event sequence.
3. **It can raise a pairing prompt.** A peripheral that requires encryption for
   service discovery will trigger the OS pairing flow. On Windows that is a
   system toast the user did not ask for; on macOS a dialog. INFERENCE — not
   tested, and untestable here without touching somebody's device.
4. **It is unsolicited.** BLE connectable advertising is an invitation, so this
   is not an attack and not unlawful; but "the specification permits it" is not
   the same as "an ICC profiling application should do it silently".

**The mitigation that does most of the work: never write.** GATT service
discovery is enough to decide. For a non-CR30 the sequence is connect → discover
→ disconnect, with **zero application bytes written**. `ble.discover` today
writes `READ_MEASUREMENT` and four `POLL` bytes to every shortlisted device;
under a widened probe that must become conditional on `ffe0` **and** an `ffe1`
with the notify property actually being present in the discovered tree.

One favourable asymmetry worth stating: **a peripheral that is currently
connected to its owner is usually not advertising**, so it does not appear in
our list at all. The widened probe mostly meets *idle* devices. That reduces
harm; it does not eliminate it (multi-link peripherals keep advertising).

### 3.4 SHOULD WE ALSO PROBE DEVICES ADVERTISING *OTHER* UUIDs?

**No.** Strictly, the spec permits it to be necessary — an "Incomplete List of
16-bit Service UUIDs" may legitimately omit `ffe0` (§1.1). But a device that
advertised a list and did not include `ffe0` has at least *tried* to describe
itself, and including that class roughly doubles the blast radius for a case
nobody has ever observed. Restrict to the **empty** case, which the CSS itself
defines as "an empty incomplete-list" — the device that told us nothing.

### 3.5 WHAT SURVIVES: the bounded, opt-in, diagnostic-only probe

Not a fallback. A **tool**, in the Bluetooth diagnostic, behind an explicit
consent step that says in plain words what it will do. Bounds, and why each one:

| bound | value | why |
|---|---|---|
| trigger | only from the Bluetooth diagnostic, after an explicit "yes" | §3.2 makes it unshippable anywhere else; §3.3 makes silent operation wrong |
| candidates | advertisers with an **empty** service-UUID list only | §3.4 |
| RSSI floor | **−65 dBm** | the CR30 read −60 on a desk; an instrument you are about to measure with is in the room. Cuts 26 → 8 in the one real scan we have |
| count cap | **8**, strongest RSSI first | matches the −65 population; a hard stop independent of the floor |
| connect timeout | **3 s**, not 8 | a device on your desk connected in 2.33 s; 8 s buys nothing and costs 5 s per miss |
| total budget | **45 s**, hard wall-clock | bounded, statable to the user up front, abortable |
| writes | **none** unless the discovered tree has `ffe0` *and* an `ffe1` with notify | §3.3 |
| teardown | disconnect in a `finally`, always | a held peripheral stops advertising — for the CR30 that would hide it from the next scan |
| memory | never write `cr30_ble_address` from a probe that did not CONFIRM | the existing rule in `ble.py`'s big comment; do not weaken it |
| repetition | once per invocation; never automatic, never retried | it is a diagnostic, not a search strategy |

**And it must show the user what it is about to do**: "ChromIQ will briefly
connect to up to 8 nearby Bluetooth devices to ask whether any of them is your
instrument. It will not send them any commands. This takes up to 45 seconds."
That sentence is the whole ethical difference between this and a scanner.

### 3.6 The honest assessment of this half

It is the *right principle* — "the advertisement is a hint, the protocol is the
truth" — carried to its conclusion. It is also the half that helps the smallest
population (users with no working USB, §4.6.6) at the highest cost. **It should
ship second, and only as a diagnostic.**


## 4. The USB-assist chain — evaluated end to end

The proposed chain: USB works → read the id string over USB → that string IS the
BLE advertised name → plain scan matches the name without needing `ffe0` →
yields the address → store in `cr30_ble_address` → `_open_ble` goes straight
there for ever after.

**Verdict: the chain is SOUND, and it is the right thing to ship first — but
step 2 as written is WRONG and would have shipped a feature that never matches
anything. See §4.1.**

### 4.1 ⚠ STEP 2/3 — THE LOAD-BEARING LINK IS *`second_id`*, NOT `device_id`

**PROVEN. I ran the comparison on the same physical unit, in one process, using
ChromIQ's own parser.**

The research repo holds unredacted captures locally (`captures/raw/`,
gitignored). I parsed the USB identity reply with
`workflow.cr30.identity.parse_identity` and compared it byte-for-byte against
the `local_name` recorded in the BLE scan of the same unit:

| comparison | result |
|---|---|
| advertised `local_name` == `Identity.second_id` (`AA 0A **01**`) | **True** |
| advertised `local_name` == `Identity.device_id` (`AA 0A **00**`) | **False** |
| `Identity.device_id` == `Identity.second_id` | **False** |

Both fields are 10 characters. Both look like serials. **They are different
strings**, and only the second one is the Bluetooth name. `LOCAL_DEVICE_IDS.md`
in the research repo has said so all along, in the only place nobody reads:

```
Device name field (AA 0A 00, payload[5:30]):   <DEVICE-ID-1>
Second id field   (AA 0A 01, payload[15:25]):  <DEVICE-ID-2>
```

…and `TRANSPORT_BLE.md:9` records the advertised name as `<DEVICE-ID-2>`.

`ble.py`'s own comment is self-contradictory and is the source of the error:

> "The advertised name is the device's OWN **device-id** string (the value
> **AA 0A 01** returns over USB)"

It names ChromIQ's `device_id` attribute while citing the sub-command that
produces `second_id`. Anyone implementing from that comment — as the brief
did — reaches for `Identity.device_id` and gets a string that will never match
an advertisement.

**So: step 3 is CONFIRMED, on one unit, with the correction that the field is
`Identity.second_id`.** The comparison has been made on the same unit; the chain
does not rest on an unverified assumption. It rests on an **n = 1** verification,
which is a different and much weaker complaint — see §4.6.

### 4.2 ⚠ A LIVE BUG FALLS OUT OF THE SAME FINDING

**PROVEN by reading `workflow/cr30/device.py`:**

```
device.py:227   self.unit_id = getattr(self._t, "name", None) or None      # BLE  -> <DEVICE-ID-2>
device.py:238   self.unit_id = (getattr(ident, "device_id", "") or "")…    # USB  -> <DEVICE-ID-1>
```

`unit_id` is the key `MeasureBridge._signature_key` hands to
`tile_learning.learned_signature` (`measure_bridge.py:808-812, 833`). So **the
same physical instrument has two different tile-signature keys depending on how
it is plugged in.** A user who performs the tile-learning step over USB and then
measures over Bluetooth gets `learned_signature` → `None` and **the magnet guard
silently does not arm.**

The failure direction is safe (unarmed, never "a real patch refused" — the
docstring's reasoning holds), so this is not a data-corruption bug. It is a
protection that quietly is not there, and it is exactly the sort of thing that
"a green test can be guarding the bug" describes. Fixing §4.1 fixes this too,
because `second_id` is the string both transports can see.

### 4.3 STEP 4 — is matching a USB-learned name categorically different from guessing?

**Yes, and the rule in `ble.py` is not violated. It is honoured.**

Read what the rule actually forbids:

> "Hard-coding one unit's name works only on that unit. Discovery must go by
> SERVICE UUID and then confirm over the protocol; the name is a hint and a
> label, never a test."

The prohibition is against a name that came from *us* — a constant in our
source, a pattern, a substring, a user's typing. `TRANSPORT_BLE.md` records the
author's own name-heuristic failing in precisely that way: it flagged a
television because the string contained "cr", and missed the instrument.

A name read out of *that instrument*, over a channel that has already
authenticated it (`Identity.is_cr30()` requires `model == "CR30"` and a
non-suspect field), is a different object. It is not a hypothesis about what
CR30s are called; it is a fact the device stated about itself. The right frame:
**the name is not being used as a test of identity — it is being used as an
ADDRESS LOOKUP.** The identity test is still the protocol, and it still runs.

That last point is what makes this safe, and it is already implemented:
`measure_bridge._open_ble` calls `dev.identify()` on the remembered address
every single open, and on failure closes the link and falls back to discovery
(`measure_bridge.py:668-704`). So a wrong name match cannot lead to calibration
bytes reaching a stranger — it leads to one connect, one `READ_MEASUREMENT`, an
axis mismatch, a disconnect, and a scan. **The design is fail-safe by
construction, and that is the difference from the fallback in §3.**

One caveat to write into the code: **match the name EXACTLY, not loosely.**
`bluetooth_report._looks_like` is deliberately fuzzy (`a in b or b in a` after
alphanumeric folding) because it compares against a *human-typed* serial that
may not be the same string. The USB-learned name needs no such tolerance — it is
the device's own bytes — and fuzziness here would reintroduce the "65\" Crystal
UHD" class of false positive. **Exact, case-sensitive equality.**

### 4.4 STEP 6 — does the stored address rot, and does the user get stuck?

**The rot is real; the app already handles it correctly. PROVEN by reading
`measure_bridge.py:650-704`.**

* **macOS:** the address is a per-host CoreBluetooth UUID. It is stable for a
  given Mac and peripheral, and changes if the Bluetooth pairing database is
  reset — `_signature_key`'s docstring already says exactly this.
* **Windows:** `backends/winrt/scanner.py:_format_bdaddr` produces a
  `AA:BB:CC:DD:EE:FF` MAC string. **If the CR30 advertises with a resolvable
  private address it rotates (typically ~15 min) and the stored value rots on
  every session.** Which address type the CR30 uses is **NOT ESTABLISHED** —
  no capture in the repo records it, and CoreBluetooth hides it behind the
  per-host UUID. INFERENCE (moderate): an HM-10-class module that requires no
  pairing and no encryption (EXP-BLE-002/009: unauthenticated ATT writes
  succeed) almost certainly uses a static address, because privacy/RPA in
  practice presumes bonding. **Testable only on his machine, or on Linux with
  `btmon`.**
* **Address stability over time is UNPROVEN in the repo.** The three captures
  that record the address span 74 seconds.

None of that blocks the design, because the fast path is already
self-correcting: a stale address produces a failed `identify()`, the link is
closed *(deliberately — a held peripheral stops advertising and would be
invisible to the very scan meant to recover it)*, and discovery runs. A user
cannot get stuck. **The one thing to add is that a name-based rediscovery must
be in that fallback too**, otherwise a rotted address on a name-only advertiser
falls back into the `ffe0` filter that cannot see it — i.e. the fast path would
paper over the gap until the day the address rotted, and then fail
mysteriously.

### 4.5 WHERE IT SHOULD LIVE

**Recommendation: learn it silently on every successful USB `identify()`, and
surface it nowhere.**

Reasoning:

* The owner's constraint is *"a general solution … nothing the user has to
  know"*. A button labelled "learn my instrument's Bluetooth identity" fails
  that on its face — it asks a user to understand a transport hand-off.
* It costs **nothing**. `identify()` already runs on every USB open and already
  parses sub-command `0x01`; `second_id` is already in the `Identity` object.
  Writing one settings key is microseconds and no extra device traffic.
* It is not privacy-sensitive beyond what ChromIQ already stores: `cr30_usb_port`
  and `cr30_ble_address` are already persisted per host.
* **What it must NOT do is auto-connect.** Learning the name is free; using it
  should happen only when a Bluetooth open is actually attempted.

Concretely: a new key `cr30_ble_name`, written by the USB path; read by
`_open_ble` as a second hint after `cr30_ble_address`. The Bluetooth diagnostic
should *report* whether a name has been learned (it is diagnostic gold: "ChromIQ
knows your instrument is called X and did not see X in the scan" is a far
better finding than "no CR30 found"), but must not be the place it is acquired.

### 4.6 WHAT IT DOES NOT FIX — and this list is the honest part

1. **A unit with no Bluetooth radio.** Nothing here helps, and the report must
   still be able to say so. With a learned name the diagnostic can say it much
   more sharply than today: *"ChromIQ knows this instrument's Bluetooth name.
   In a 20-second scan seeing N devices, nothing advertised that name and
   nothing advertised the CR30's service. Either the radio is off/absent, the
   instrument is asleep, or something else holds it."* That is a real, general
   finding a user can act on and a report we can act on. Today's report cannot
   distinguish "not advertising" from "advertising and filtered out".
2. **A unit whose BLE name is not `second_id`.** n = 1. If his firmware names
   the radio from `device_id`, or from a fixed model string, or leaves it
   unnamed, the chain silently finds nothing. **Cheap mitigation: match against
   BOTH `device_id` and `second_id`** — two exact strings, both device-stated,
   no extra risk, and it costs one more comparison. Do this.
3. **A unit that advertises no name either.** The Local Name AD type is as
   optional as the Service UUID one (§1.1). Then only §3 helps.
4. **Windows Bluetooth being broken at the stack/permission level.** A scan that
   returns zero devices defeats every design in this report equally.
5. **The instrument asleep, or held by the phone app.** Already covered by the
   existing message, and still the most common real cause.
6. **A user with no working USB.** The whole chain is unavailable. That is the
   population §3 exists for, and it is smaller than it looks: pharmacist has USB,
   and anyone using ChromIQ's CR30 support at all today reached it over USB.

### 4.7 "Should it stay fixed after a restart?" — yes, PROVEN

`DeviceReader.REMEMBERED_ADDRESS_KEY = "cr30_ble_address"` is written through
`core.settings.AppSettings().set(...)` (`measure_bridge.py:638-648`), i.e. a
`QSettings` store, which persists across restarts. `_open_ble` reads it before
scanning. So: learned once, used at every launch, surviving restarts — **yes**,
with the two honest qualifications that (a) a stale address self-corrects by
falling back to a scan rather than by being trusted, and (b) whether the address
survives *days* has never been measured on any host.


## 5. What else could explain his failure

Ranked by likelihood given everything above. **T** = testable without his
hardware, **H** = needs him.

### 5.1 ⚠ H0 — ChromIQ NEVER TRIES BLUETOOTH WHEN HIS USB WORKS. **T, and PROVEN.**

This was not on anyone's list and it may be the whole answer.

* `DeviceReader.__init__(self, transport: str = "auto", …)` —
  `measure_bridge.py:588`.
* `_open()` with `transport == "auto"` calls `_open_usb()` **first**, and
  reaches `_open_ble()` only inside `except Exception` — `measure_bridge.py:842-855`.
* There is exactly **one** construction of `DeviceReader` in the entire UI:
  `ui/tabs/tab_measure.py:7869`, `DeviceReader()`, **no arguments**.
* `grep` across `core ui workflow` finds **no** CR30 transport setting. The only
  CR30 keys that exist are `cr30_ble_address`, `cr30_usb_port`,
  `cr30_tile_signatures`.

**There is no way, anywhere in ChromIQ, for a user to ask for Bluetooth.** The
only route to the BLE path is for USB to *fail* — i.e. unplug the cable — and
nothing on screen says so.

So "I cannot connect over Bluetooth" from a user whose USB works is, on the
evidence, most likely one of:

* he is trying to pair the CR30 in the **Windows Settings → Bluetooth** pane.
  That is "the computer says NOOO" almost verbatim: Windows' *Add a device*
  flow routinely refuses a BLE peripheral that requires no pairing, and
  **ChromIQ does not need it paired at all.** No amount of discovery work in
  ChromIQ changes that dialog.
* he pressed Start with the cable in and got USB, which worked, and concluded
  Bluetooth was broken.

**This is the first thing to establish, it costs one question, and every other
hypothesis below is downstream of it.** It also changes what §4 is worth: a
learned Bluetooth name is useless until there is a way to *choose* Bluetooth.

### 5.2 H1 — the instrument is asleep, or held by another central. **H.**

Still the most common genuine cause, and already covered by the existing
message. `TRANSPORT_BLE.md` (VERIFIED): the CR30 **stops advertising while a
central holds it**. The owner also records that the instrument's own display
shows an indicator when a connection is requested — a free host-vs-device
discriminator that costs nothing to ask about.

### 5.3 H2 — `ffe0` rides in the SCAN RESPONSE and his host never gets it. **H, but with code we already ship.**

§1.4: the author's advertisement does not fit in 31 octets, so something is in
the scan response. §1.2a: Windows is the one platform where bleak must pair
ADV and SCAN_RSP by hand. If the exchange does not complete on his controller,
`service_uuids` is short and the stage-1 filter drops a perfectly healthy
instrument. **This needs no new code to test** — the diagnostic's stage 1 already
prints every device with its `service_uuids`.

### 5.4 H3 — his unit does not advertise `ffe0` (different firmware, or no radio). **H.**

Unfalsified and unsupported (§2). With a USB-learned name (§4) the diagnostic
can finally *distinguish* these two, which today it cannot.

### 5.5 H4 — Windows Bluetooth adapter, driver or privacy setting. **H.**

Presents as stage 1 returning zero devices or raising. The diagnostic already
says the right thing for this case.

### 5.6 H5 — apartment threading (STA) on Windows. **T — AUDITED, and it holds.**

bleak's own Windows docs: *"Bleak will hang forever if the current thread is not
MTA - unless there is a Windows event loop running that is properly integrated
with asyncio."* `backends/winrt/scanner.py:242` calls `assert_mta()`, which
raises `BleakError("Thread is configured for Windows GUI but callbacks are not
working.")` after 0.5 s on an STA thread whose message loop is blocked. Qt's
Windows platform plugin `OleInitialize`s the GUI thread, and
`BleTransport._run` blocks it with `run_until_complete`.

**I audited every bleak entry point in ChromIQ. All three are off the GUI
thread:**

| path | thread | evidence |
|---|---|---|
| Measure reads | `QThread` via `_ReadWorker` | `measure_bridge.py:436-448` |
| Calibrate | `QThread` via `_Worker` | `tab_measure.py:7308-7325` |
| Bluetooth diagnostic | `threading.Thread` | `main_window.py:1813-1834`, with the hazard documented in the comment |

So H5 is **not** his fault — but note one real residual: `assert_mta` is called
by the **scanner only**. `winrt/client.py` has no such guard, so a
`BleakClient.connect` on a blocked STA thread would *hang*, not raise. That is a
constraint on any new code: **anything added in §4 or §6 that calls
`BleakScanner` or `BleakClient` must stay on a worker thread.**

### 5.7 H6 — a rotting Bluetooth address (RPA) on Windows. **H.**

§4.4. Would produce intermittent failure; he reports consistent failure. Low as
a primary cause, real as a maintenance issue.

### 5.8 H7 — a stale `cr30_ble_address` pointing at a stranger. **T — ruled out.**

`_open_ble` re-runs `dev.identify()` on the remembered address every open and
falls back to discovery on failure (`measure_bridge.py:668-704`). It cannot
strand a user.

## 6. What should ship, in what order

The dividing line: **`ble.discover` is the code path every Bluetooth measurement
takes and it works for the one user we have. It gets only additive, bounded,
fail-safe changes. The diagnostic is a tool a user runs deliberately and can
carry everything else.**

### Tier 1 — costs nothing, risks nothing, answers the biggest question

1. **Ask him whether he was pairing in Windows Settings** (§5.1). One message.
   Do this before writing any code.
2. **Fix the `device_id` / `second_id` confusion** (§4.1, §4.2). Correct the
   comment in `ble.py`, and change `device.py:238` to key `unit_id` on the
   field the two transports share. This repairs a live bug (the tile guard not
   arming across transports) independently of everything else.

### Tier 2 — the USB-assist chain, diagnostic first

3. **Learn `second_id` (and `device_id`) into settings on every successful USB
   `identify()`.** Free, silent, no device traffic.
4. **Teach the Bluetooth diagnostic to use it**: report the learned names, and
   flag any scanned device whose `local_name` matches one **exactly**. This
   turns the existing optional serial box from a user-supplied aid into a
   general one, and it is the first thing that can tell "not advertising" from
   "advertising and filtered out".
5. **Only then, into `ble.discover`:** a name hint, tried *after* the `ffe0`
   shortlist, exact match only, still protocol-confirmed before use.

### Tier 3 — the widened probe, diagnostic only

6. The bounded, opt-in, consented probe of §3.5. Never in `ble.discover`.

### Tier 4 — the thing all of this presupposes

7. **A way to choose Bluetooth.** Without it (§5.1) Tiers 2 and 3 are unreachable
   for exactly the user they were written for.


## 7. Recommendation, plan, open questions, rating

### 7.1 Recommendation

**Ship the USB-assist chain (§4) first, and ship the widened probe (§3) only as
a consented diagnostic tool, if at all.**

The two solutions are not equal. The USB-assist chain is:

* **general** in the owner's sense — nothing typed, nothing guessed, no
  knowledge of the unit;
* **fail-safe by construction** — a wrong name match costs one connect and one
  `READ_MEASUREMENT`, then `identify()` rejects it and discovery runs
  (`measure_bridge.py:668-704`);
* **free** — the string is already parsed on every USB open;
* **persistent** — `cr30_ble_address` is a `QSettings` key, so yes, it stays
  fixed across restarts, with the honest caveat that a stale address
  self-corrects rather than being trusted;
* **touches nobody else's hardware.**

The widened probe is none of those. It connects to strangers' devices, it costs
tens of seconds, it helps only users with no working USB, and its ethical
defensibility depends entirely on bounds that a future edit can quietly remove.

**But do §5.1 first.** If he has been fighting the Windows *Add a device*
dialog, or if ChromIQ simply never attempted Bluetooth because his USB worked,
then none of this is his bug and building it first would be building the wrong
thing well. One question settles it.

### 7.2 Numbered implementation plan

1. **Ask the user two questions** (no code): *were you trying to add the CR30 in
   Windows' own Bluetooth settings?* and *when ChromIQ was looking, did anything
   appear on the instrument's own screen?* (§5.1, §5.2).
2. **Correct `ble.py`'s comment** — the advertised name is `Identity.second_id`
   (`AA 0A 01`), not `device_id` (`AA 0A 00`). PROVEN §4.1.
3. **Fix `device.py:238`** so `unit_id` is the same string over both transports.
   Repairs the tile guard not arming across transports (§4.2). This is a
   behaviour change to a shipped feature — it should carry a test that a unit
   learned over USB arms over BLE.
4. **Add `cr30_ble_name`** (and `cr30_ble_name_alt`), written silently on every
   successful USB `identify()` from `second_id` and `device_id`.
5. **Diagnostic:** report the learned names; flag any scanned device whose
   `local_name` matches one **exactly** (case-sensitive); keep the existing
   fuzzy match for the user-typed serial and keep the two visibly distinct in
   the text.
6. **Diagnostic:** when nothing matches, say the sharper thing — *"ChromIQ knows
   this instrument's Bluetooth name. In N seconds it saw M devices and none of
   them was called that, and none advertised the CR30's service."*
7. **`ble.discover`:** accept an optional `names: set[str]`. Shortlist =
   `ffe0` advertisers **∪** exact-name matches. Protocol confirmation unchanged
   and still mandatory. Purely additive — with an empty set the behaviour is
   byte-for-byte today's.
8. **`_open_ble`:** pass the learned names into both the initial discovery and
   the post-failure fallback (§4.4 — otherwise a rotted address falls back into
   the filter that cannot see the device).
9. **A way to choose Bluetooth** (§5.1, Tier 4). Design question, not mine.
10. **Only then**, the §3.5 bounded probe, in the diagnostic, behind consent.

Steps 2–8 are all `workflow/cr30/` and `ui/` — outside my remit per the
constraints, so these are proposals, not edits.

### 7.3 Open questions needing the owner's ruling

1. **Does a user have any way to choose Bluetooth today, and should they?**
   (§5.1). If the intended workflow is "unplug USB", that needs saying on
   screen. This is the biggest one and it is a design decision.
2. **Is the widened probe acceptable at all?** Connecting to bystanders' devices
   is a product-values question, not a technical one. My recommendation is: only
   with explicit per-invocation consent, in a diagnostic, with the §3.5 bounds
   stated to the user in words.
3. **Should a name learned over USB be persisted per host indefinitely?** It is
   a device identifier. `cr30_usb_port` and `cr30_ble_address` are already
   persisted, so this is consistent, but it is his call.
4. **Is `second_id` documented anywhere as the vendor's "serial number"?** The
   diagnostic's serial box asks the user for a serial; if the vendor's window
   prints `device_id` and the radio advertises `second_id`, that box is asking
   for the wrong string and its fuzzy matching is hiding the mismatch.
5. **Do the §M message-catalogue rules apply** to the new diagnostic text? Per
   `CLAUDE.md`, new user-facing message text goes to §M-PROPOSED first.

### 7.4 Reproducing the §1.5 demonstration

`workflow.cr30.ble.discover` imports `bleak` *inside* the function, so a fake
installed in `sys.modules` reaches it. No radio required. The driver used is in
the session scratchpad as `fake_ble.py`; it substitutes a `BleakScanner` whose
`discover()` returns a scripted world, and a `BleakClient` that answers
`READ_MEASUREMENT` with a synthetic 200-byte reply carrying `bb 02 10 00`,
`>H`=400, step 10, bands 31. Worth promoting into `tests/` as a regression test
for step 7 above: **with `names` empty the shortlist must be unchanged.**

### 7.5 Rating of the sketch: **7 / 10**

**What is right, and it is the important part (this is why it is not lower):**

* The diagnosis is correct and it is the load-bearing claim. Service UUIDs are
  optional — the CSS defines the meaning of their *absence* (§1.1) — and the
  code really does drop such a device before any protocol confirmation runs.
  I proved that against the real function (§1.5).
* "The advertisement is a hint, the protocol is the truth" is the right
  principle, and the observation that the code only half-implements it is
  exactly right.
* Refusing to ship the serial box as the solution was correct. It is a
  diagnostic aid and the owner is right that it is not general.
* The instinct to attack the bystander problem before building was right; the
  numbers (§3.1, 26 of 30) justify it more strongly than the sketch assumed.

**What costs it three points:**

* **−1, the biggest: the sketch reaches for the fallback and treats USB-assist
  as a side idea.** The ranking is the wrong way round. USB-assist is general,
  free, fail-safe and touches nobody; the widened probe is none of those and
  serves a smaller population. The owner's re-framing corrects this, and it is
  the correction that matters most.
* **−1: it did not check whether Bluetooth is even reachable in the UI.** §5.1
  — `DeviceReader()` is constructed with no arguments and `_open` is USB-first,
  so a user whose USB works never reaches the BLE path at all. A whole design
  was built for a path the user may never have taken. *"Reproduce with the
  user's real layout before saying 'not reproducible'"* cuts both ways: check
  the user's real path before designing for it.
* **−1: the load-bearing second-hand claim was accepted at the wrong field.**
  The chain named `Identity.device_id`; the advertised name is
  `Identity.second_id`, and the two are different strings on the one unit in
  evidence (§4.1). Implemented as briefed it would have matched nothing, and it
  would have looked like "his unit does not advertise its name" — confirming a
  false hypothesis. The brief was right to insist the claim be verified; the
  sketch was one field away from being unbuildable.

**Not counted against it, but worth saying:** the widened-probe half is not
wrong, it is *second*. Bounded and consented as in §3.5 it is a good tool. It is
just not the answer to this user's problem, and probably not to anyone's until
someone appears who has Bluetooth and no USB.

---

**Status: COMPLETE.**
