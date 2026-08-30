# 41 — BLE identity fix: challenge round (pre-implementation)

**Status: COMPLETE — all questions answered, proving test written and run.**

Round rules: no CR30/serial access, no on-screen app, no `--runslow`. Code
reading, offline reasoning, targeted offscreen tests only. No source edits.

The proposal under attack: in `DeviceReader._open_ble`'s remembered-address
branch (`workflow/cr30/measure_bridge.py:655-668`), call `dev.identify()`
after open; on any exception, close and fall back to full discovery. Unlike
the USB twin, do NOT test `is_cr30()` — the BLE branch of `identify()`
returns a dict and raises on mismatch.

First, the proposer's own premise checked: **the dict-vs-Identity point is
correct and PROVEN.** `workflow/cr30/device.py:190-215`: the BLE branch of
`identify()` returns `{"model": "CR30", ...}` (a plain dict) and raises
`MeasurementError` both when no header arrives and when the axis is not
`(400, 10, 31)`. A dict has no `is_cr30` attribute, so the USB call-site
pattern `getattr(ident, "is_cr30", lambda: False)()` evaluates `False` for a
genuine CR30 and would demote every real instrument to the 15 s scan, every
session. Calling `identify()` for its exception is the right shape on BLE.

## Q1 — Is the harm claim true? PROVEN, yes — on the calibrate flow the FIRST application bytes to the remembered address are `bb 11`

Trace, all read from source:

1. `BleTransport.open()` (`workflow/cr30/ble.py:184-260`) with an explicit
   `address` skips the whole discovery/confirm block (`target = self.address`
   is non-None, so the `if target is None:` body never runs). It then does
   `BleakClient(target).connect()` and `start_notify(FFE1, ...)` and returns.
   **It writes no protocol frame at all.** The only writes at the Bluetooth
   layer are the connection itself and the CCCD (notification-enable)
   descriptor write inside `start_notify` — GATT plumbing, not application
   data. PROVEN (code read; there is no `write_gatt_char` on this path).
2. `_open_ble` returns the device; `_remember_address(dev)` re-persists the
   address (`measure_bridge.py:634-643`). No bytes to the device.
3. The first thing a real session does with the reader is **calibrate**, not
   read: `ui/tabs/tab_measure.py:7077` ("The bridge FIRST, and calibrate
   through its reader") → `DeviceReader.calibrate` (`measure_bridge.py:805`)
   → `self._open()` → `self._dev.calibrate(black=black)` →
   `CR30.calibrate` BLE arm sends `frame(0xBB, 0x11/0x10, ...)`
   (`device.py`, CAL_WHITE=0x11 / CAL_BLACK=0x10). So on the normal user
   journey the **first application frame the unidentified stranger receives
   is a white-calibration command.** On a real CR30 that is the reference-
   overwriting command — EXP-022 (research repo) proved it really sets the
   reference (~250 ms answer, paper reading moved 83.95 → 88.37 %R).
   PROVEN by code path + the research repo's own measurement.
4. On the measurement flow (`DeviceReader.__call__`), the first writes are
   `read_next_measurement`'s: `drop_events()` (writes nothing) then
   `wait_for_event` (writes nothing — it only pumps the loop) then, after an
   event, `read_measurement` → `READ_MEASUREMENT` polls. So the measurement
   path sends only reads; **calibration is the harmful one and it is also
   the one that runs first in a session.**

Is `identify()`'s first write really `READ_MEASUREMENT`, and is that safe?
`device.py:196`: `raw = self._t.ask(ble.READ_MEASUREMENT, polls=4)`;
`BleTransport._ask` writes the request frame then 1-byte `POLL`s (0x01 —
note: a bare poll byte, NOT the 10-byte `bb 01 00` trigger frame; the
trigger is `frame(0x01, 0x00)` = `bb 01 00 00 ... ff cs`, ten bytes, and
EXP-BLE-012 fired it as a frame). So identify writes: `bb 02 10 00 00 00 00
00 ff <cs>` plus up to 4 × `0x01`. PROVEN (code read).

Is `bb 02 10` genuinely incapable of triggering a measurement or
calibration? **INFERENCE, with strong support, not a dedicated
experiment.** Evidence: (a) EXP-BLE-012's raw capture and the vendor phone
trace show the vendor app itself using `bb 02 10` as its read after a
measurement (`EXPERIMENTS.md:647`); (b) the entire stale-cache hazard this
module documents ("the CR30 holds its last reading indefinitely, so a plain
read returns instantly with the previous value" — the ΔE 60.5 patch-A1
incident) exists precisely because repeated reads return the stored slot
unchanged; (c) EXP-BLE-012's own method read the slot before and after the
trigger and attributed the change to the trigger — the experiment's logic
requires the read to be non-mutating, and the numbers cohere. A dedicated
"read twice, press, read twice" experiment would close it (listed at the
end); the risk of it being wrong is very low.

**Verdict on Q1: the harm claim stands.** And the beta.1 exposure is real:
report 40 confirmed `or cands` shipped in v4.1.5-beta.1 (`1f40fe0d`), so a
stranger's address can already sit in `cr30_ble_address`.

## Q2 — The fix narrows the harm to exactly the exposure discovery already accepts. That is a genuine close, not a fig leaf

First byte sequence written to an unidentified stranger under the fix:
GATT connect + CCCD enable, then `bb 02 10 00 00 00 00 00 ff <cs>` (10
bytes) + up to four `0x01` polls. PROVEN (code read, Q1).

- To a real CR30 belonging to someone else: a stored-slot read. Harmless to
  its references (Q1's inference), and identical to what the vendor's own
  app sends. It would then PASS identify — see Q3 for what that means.
- To an arbitrary `ffe0`/HM-10 gadget: 14 opaque bytes reaching an unknown
  MCU. Irreducible — identification requires asking a question — and it is
  **byte-for-byte the same probe `discover(verify=True)` already sends to
  every unconfirmed ffe0 advertiser** (`ble.py:120-133`), an exposure report
  40 already examined and accepted ("the retry doubles a risk already
  accepted, bounded, and smaller than the old behaviour"). The fix adds no
  new class of write; it removes the `bb 11`/`bb 10` class.

So: the calibration-write harm is CLOSED for every device that fails the
axis check; the residual is the minimal probe, already accepted elsewhere.
The one device the fix does NOT protect is a device that passes the axis
check — Q3.

## Q3 — Is the axis check worth calling? Yes — and the "echoing gadget passes" claim in F-BLE-ID is STALE

**F-BLE-ID is out of date.** It says `identify()`'s BLE branch "never
compares the axis". It does now — `device.py:204-210` compares
`(start_nm, step_nm, bands)` against `ble.EXPECTED_AXIS` and raises on
mismatch (the comment "COMPARE IT. This parsed the axis and then ignored
it" records the fix). And an **echoing gadget is REJECTED** by the current
code: the echo of `READ_MEASUREMENT` does contain `MEASUREMENT_HDR`
(`bb 02 10 00` are the frame's own first four bytes), so `raw.find` hits at
offset 0 and the 10-byte echo satisfies `len(raw) - i >= 8` — but bytes
4..7 of the echoed frame are `00 00 00 00`, parsing to axis `(0, 0, 0)`,
which fails the compare. PROVEN by desk-check of the byte layout
(`frame()` builds `bb 02 10 00 00 00 00 00 ff cs`; `BleAxis.parse` reads
offsets 4..7). Also proven by running it — see Q7's test run, which feeds
a literal echo through the real parser.

The honest weakness is B2-7: the axis identifies "a CHNSpec CR-series
colorimeter", not "a CR30" — a CR10/CR20 answers identically
(`35_beta2_backlog.md:136`). Both sides:

*It is theatre:* the check cannot name the model; a deliberate emulator, or
a sibling instrument, passes; a passing device still receives calibration
frames afterwards.

*It is not theatre:* (1) the threat model that motivated all of this —
generic HM-10 hobby gadgets at a generic address — is exactly what the
axis check rejects, including the echo case; (2) the remembered address is
itself a strong prior (stable per host, written only after a confirmed
discovery once Q6's ordering is fixed), so the combined test is "the device
at the address my own confirmed CR30 used, still answering with a CR-series
spectral reply" — the population that passes this and is not the user's
instrument is nearly empty; (3) a sibling CR10/CR20 that passes speaks the
same protocol, and report 39 already leans toward "reading them may simply
work — a feature, not a bug"; the damage of misidentifying a sibling is a
calibration performed on an instrument the user is deliberately using with
ChromIQ, i.e. the same thing they asked for. **Verdict: net-positive,
implement; not theatre.** It is the same discriminator `discover(verify=
True)` uses, so the shortcut is exactly as strong as the search it skips —
which is the standard the USB twin's test states in words
(`tests/test_usb_does_not_greenlight_any_ch340.py:203`, "The shortcut must
not be weaker than the search it skips").

A real discriminator does not exist over BLE today: USB has the `AA 0A 01`
id string; over BLE that string is only visible as the ADVERTISED NAME
(`ble.py` docstring), and a directly-addressed connection never sees an
advertisement. Whether a `bb`-frame equivalent of the id query exists over
BLE is a hardware question (listed at the end). Remembering the expected
unit NAME alongside the address and checking it during discovery would
help discovery, not the fast path.

## Q4 — A poisoned address SELF-HEALS, provided the fix closes the stranger. An upgrade-time clear is unnecessary — with one caveat

Trace with the fix in place, `cr30_ble_address` poisoned by beta.1:

1. `_open_ble`: `remembered` = poisoned address → `CR30.open_ble(address=
   remembered)` connects (or fails to — either way continue) →
   `dev.identify()` raises (no reply within 4 polls, or wrong axis) →
   close, fall through.
2. Fallback: `CR30.open_ble(address=self._address)`. In production
   `self._address` is always `None` — the only constructor call is
   `DeviceReader()` at `ui/tabs/tab_measure.py:7612` (PROVEN by grep) — so
   this is full discovery, which since the beta.2 fix accepts **confirmed
   candidates only** (`ble.py:196-236`, one retry, then refusal).
3. On success `BleTransport.open` sets `self.address = target` (the
   confirmed device's address, `ble.py:241`) and `_open_ble` calls
   `_remember_address(dev)`, which reads `dev._t.address`
   (`measure_bridge.py:636`) and **overwrites the poisoned key with the
   good address.** Healed.
4. If the real CR30 is absent that session: discovery raises, nothing is
   overwritten, the poisoned key survives — but it is now inert, because
   every future use of it passes through identify. Sticks harmlessly, heals
   on the first session where the real instrument is present.

So report 40's suggested "clear/overwrite the remembered key" upgrade step
is NOT needed as a separate migration: overwrite happens naturally, and
clearing without a replacement would only throw away a key that might be
the user's real instrument (beta.1 users with a real CR30 have their GOOD
address stored; clearing it would cost them a 15 s scan for nothing).
**Caveat that makes this true:** the stranger must be CLOSED on identify
failure (Q5a) — a leaked connection can prevent step 2 from finding the
real instrument when the "stranger" was actually the CR30 failing
transiently. And Q6's ordering must be fixed, or step 1 re-persists the
poison before testing it (harmless once the fix exists everywhere, but
wrong on its face).

All PROVEN from code paths; the only inference is bleak's behaviour on
connect-to-absent-address (raises after timeout — bleak's documented
contract).

## Q5 — Failure modes of the fix itself

### 5a — Yes, close on failure, and for a BLE-specific reason stronger than the Windows one

A connected BLE peripheral **stops advertising** — the codebase itself
states and relies on this ("the device stops advertising while another
central holds it", `ble.py:230`; "a peripheral that accepts one connection
at a time", `tab_measure.py:7078`). So if identify fails transiently on the
REAL CR30 and the handle leaks, the fallback scan is looking for a device
that our own leaked connection has made invisible: discovery fails,
the user is told to "disconnect the phone app" — a wrong and misleading
message — and the session is dead until process exit. Leaking a stranger's
gadget is also rude (its owner cannot connect to it) but the self-DoS is
the decisive reason. **`dev.close()` in a try/except is mandatory**, exactly
mirroring the USB branch's close-with-teardown-guard
(`measure_bridge.py:726-733`). `BleTransport.close()` disconnects and is
itself capable of raising if the link already died — hence the guard.
PROVEN (code + the module's own measured statements about advertising).

### 5b — `self.model` side effect: no downstream behaviour change. PROVEN

`identify()` sets `self.model = "CR30"` on success (`device.py:213`). The
only consumers are `device.py:541` and `:605`, both reading
`self.model or "CR30"` — identical output whether model is `""` or
`"CR30"`. Grep found no other production consumer.

### 5c — Fast-path latency: +1.8 s to +2.15 s per session, against a 15.4 s scan saved. Quantified from the code's constants

`identify()` → `ask(READ_MEASUREMENT, polls=4)` with default `wait=0.35`
and **no `done` predicate** (`device.py:196`). Walking `_ask`
(`ble.py:428-460`): `_drain` ≥ 0.4 s (buffer is empty right after open, so
one round); request write + 0.35 s; then the poll loop — with `done=None`
the only early exit is `quiet >= 3 and buf`, which needs three consecutive
no-growth rounds, so the minimum is 3 polls (reply completed during the
initial wait) and the maximum is all 4: **1.80–2.15 s, essentially fixed**
— the loop cannot exit sooner by design. Today's fast path is ~2.4 s
(connect 2.33 + notify 0.06, measured 2026-08-30, quoted in
`_open_ble`'s docstring). The fix therefore roughly DOUBLES the fast path
to ~4.2–4.6 s, still 11+ s better than the scan it replaces. Given the
owner's explicit sensitivity to this exact delay, worth reclaiming: pass a
`done` predicate that stops at the first poll carrying the axis —
`done=lambda b: (i := b.find(ble.MEASUREMENT_HDR)) >= 0 and len(b) - i >= 8`
— cutting identify to ~1.1 s (drain 0.4 + 0.35 + one poll 0.35). That
predicate is exactly the condition identify itself tests, so it cannot
accept less than identify needs. Numbers PROVEN from the constants;
the 15.42/2.33/0.06 s figures are the code's own measured comments.

### 5d — Transient failure on a genuine CR30: demotion to the scan, never refusal — IF 5a's close is done

Ways a real CR30 could fail identify: reply fragments not delivering 8
bytes past the header within 4 polls (unlikely — header+axis fit in the
first ~20-byte MTU chunk); the link dying mid-exchange; a user pressing
the button mid-identify (harmless — the `bb 01` press frame is routed to
the EVENT queue by `_on_notify`, not the reply buffer, so it cannot
corrupt the reply; PROVEN, `ble.py:300-310`). A zero-filled stored slot
(fresh after calibration) still PASSES — identify checks header+axis only,
never the spectrum, and "a zero-filled slot still carries its header"
(`ble.py:224`). Consequence of a false negative: close + 12–27 s discovery
(which re-confirms the same unit) — a latency wart, not a refusal, and the
same worst case the USB twin accepted. Without the close it becomes a hard
failure (5a). INFERENCE on fragment timing; everything else code-read.

## Q6 — Yes: `_remember_address` must move AFTER identification on the remembered branch. The discovery branch is fine as it stands

Current remembered branch persists BEFORE any check
(`measure_bridge.py:663`) — with the fix left that way, a poisoned address
is re-persisted milliseconds before identify rejects it. Mostly cosmetic
(it was already persisted), but it re-stamps the key on every attempt and
reads as an endorsement. Order: open → identify → remember → return.

Discovery branch: `CR30.open_ble(address=self._address)` with
`self._address=None` only returns devices that passed
`discover(verify=True)`'s confirm — the same axis test — so remembering
there without a second identify is sound (identifying twice would double
the latency for nothing).

**Latent hole, production-unreachable today:** if `self._address` is ever
non-None (constructor arg; no production caller passes it — PROVEN by
grep, only `DeviceReader()` at `tab_measure.py:7612`), the remembered
branch tries that address, and on identify failure the fallback
`CR30.open_ble(address=self._address)` reconnects to the SAME address
**blind** and remembers it — the fix's check circumvented by its own
fallback. Cheap hardening while in the file: make the fallback
`CR30.open_ble(address=None)` when the address it would pass is the one
that just failed, or identify on both branches when `self._address` is
set. Should be noted even if deferred; a future chooser dialog would
arrive exactly through that parameter.

Can a stranger's address be persisted even with the fix? Only a device
that PASSES the axis check (CR-series sibling or deliberate emulator) —
accepted as irreducible in Q3.

## Q7 — The proving test: WRITTEN AND RUN. It detects the fault, passes under the proposed fix, and catches the dict-trap variant

The test drives the REAL `DeviceReader → CR30 → BleTransport` stack and
fakes only the `bleak` module (`sys.modules["bleak"]`) — the outermost
edge, exactly where the radio is. Two fake peripherals: an HM-10-style
echo gadget at the remembered address, and a CR30 whose identify reply is
a **hex literal spliced from a capture** (`bb 02 10 00` header +
`01 90 0a 1f`, the axis field of EXP-BLE-013's frame) — never built with
`ble.frame()`, so the stub cannot re-implement the code it checks. The
settings store is faked per test (same shape as
`tests/test_cr30_bluetooth_remembers_the_address.py` — note that existing
test stubs `CR30.open_ble` wholesale and therefore CANNOT see this fault;
it must be kept, not extended).

Three tests (staged at
`scratchpad/test_ble_remembered_address_is_identified.py`, ready to move
into `tests/`):

1. `test_a_stranger_at_the_remembered_address_is_refused` — remembered key
   points at the echo gadget; asserts the returned transport's address is
   the discovered CR30's, that no `bb 11`/`bb 10` frame ever reached the
   stranger, that the stranger was DISCONNECTED, and that the remembered
   key was overwritten with the good address (the Q4 self-heal, asserted).
2. `test_a_genuine_cr30_at_the_remembered_address_skips_the_scan` — the
   fake scanner RAISES if consulted; a genuine reply must be accepted on
   the fast path. **This is the dict-trap detector**: a fix that copies
   `getattr(ident, "is_cr30", lambda: False)()` treats the dict as a
   stranger, falls into the forbidden scan, and fails.
3. `test_the_stranger_only_ever_receives_the_identity_probe` — the byte
   set written to an unidentified device must be ⊆ {READ_MEASUREMENT,
   0x01} (the Q2 bound).

The condition that distinguishes the real system from the harness: the
accept/refuse decision is taken by the real `CR30.identify()` parsing
literal capture bytes, and the assertions are on which ADDRESS the
returned transport holds and which BYTES each peripheral logged — neither
of which the stub computes.

**Runs performed (offscreen, `-p no:randomly`):**

- Against unfixed HEAD: test 1 **FAILS** with "the device at the
  remembered address was accepted without identification" — the fault is
  proven to land; the mutation-must-land rule satisfied by construction
  (the fault IS current HEAD).
- Against the proposed fix (the exact replacement body, monkeypatched onto
  `DeviceReader._open_ble` in a dry-run file — no source edited): stranger
  refused, disconnected, key healed, fast path kept scan-free — **all
  green** (`scratchpad/test_ble_fix_dry_run.py`).
- Against the known-wrong `is_cr30` variant: the genuine CR30 is demoted
  to the forbidden scan and the test **fails** — the trap is caught.

After implementation, re-running test 1 against a deliberate revert of the
`identify()` call is the standing re-proof.

One measured side-effect from the run: the fixed dry-run pair took ~4 s of
its 7.2 s wall in identify's poll sleeps — the Q5c latency estimate
observed live in the harness.

## Q8 — Other findings in `_open_ble` / `_open_usb` neither report caught

1. **The stale-address worst case is ~20 s of connect timeout, then the
   scan.** `BleTransport.__init__` defaults `timeout=20.0` and passes it to
   `BleakClient(target, timeout=...)`. A remembered address whose unit is
   off/away costs up to ~20 s failing to connect before the fallback scan
   even starts — the "fast path" becomes the SLOWEST path precisely when
   the instrument is off, which is a state every session starts near.
   Not this fix's fault, and the fix does not worsen it, but the owner's
   latency sensitivity says it deserves a lower connect timeout for the
   remembered attempt (the measured connect is 2.33 s; 6–8 s would be
   generous). INFERENCE on bleak semantics, constants PROVEN.
2. **`BleTransport.close()` never closes `self._loop`** — each open creates
   an event loop (`asyncio.new_event_loop()` in `_run`) that is left
   behind on close. One reader per session makes this slow leakage, but
   the fix adds a new close-and-reopen path, making two loops per session
   the NORMAL poisoned-recovery case. Minor; worth a line.
3. **The fallback log line will lie once the fix lands.** "the remembered
   Bluetooth address did not answer" (`measure_bridge.py:666`) will also be
   printed when the address DID answer but as something else — the USB twin
   distinguishes ("did not answer as a CR30 (%s)"). Include the exception
   in the message.
4. `_open_usb`'s explicit-port fallback (`CR30.open_usb(self._port)` with a
   non-None `self._port`) opens blind AND remembers the port
   (`measure_bridge.py:737-738`) — a never-identified port becomes the
   remembered one. Self-correcting next session (the remembered branch
   identifies), and production passes no port; latent only.
5. Duplicated persistence helpers: `_remembered_address`/`_remember_address`
   vs the generic `_remembered`/`_remember` pair — the BLE pair predates the
   generic one. Cosmetic consolidation opportunity while in the file.

## VERDICT — implement, with four named changes

The proposal survives the attack. The harm is real and reachable (Q1), the
fix closes it to the already-accepted discovery-probe exposure (Q2), the
discriminator is the same one the scan it skips uses and is NOT defeated
by an echoing gadget (Q3 — F-BLE-ID is stale on that point), and a
beta.1-poisoned address self-heals with no migration (Q4). The
dict-vs-Identity reasoning is verified correct and the wrong variant is
provably caught by the test (Q7).

Named changes to the proposal as stated:

1. **Close the device on identify failure** (Q5a) — not optional; without
   it a transient failure on the real CR30 makes it undiscoverable to its
   own fallback. The proposal said "close and fall back"; this confirms it
   and pins the reason in a test assertion.
2. **Move `_remember_address` after `identify()`** on the remembered
   branch (Q6); leave the discovery branch's placement alone.
3. **Neutralise the explicit-address fallback hole** (Q6): fall back with
   `address=None` when the address that failed is `self._address`, so the
   check cannot be bypassed by its own fallback if a chooser ever passes
   an address.
4. **Recommended, latency:** give identify's ask an early-exit `done`
   predicate (or a BLE-side equivalent) so the fast path pays ~1.1 s
   instead of ~2.15 s (Q5c). If deferred, say so knowingly — the owner has
   complained about exactly this delay twice.

The exact replacement body (dry-run-proven in
`scratchpad/test_ble_fix_dry_run.py::_proposed_open_ble`):

```python
def _open_ble(self):
    from .device import CR30
    remembered = self._address or self._remembered_address()
    if remembered:
        dev = None
        try:
            dev = CR30.open_ble(address=remembered)
            # CHECK WHAT ANSWERED, not merely that something did. On BLE
            # identify() RAISES for a stranger (and returns a dict, which
            # has no is_cr30()), so the exception is the whole test —
            # copying the USB is_cr30() expression here would refuse every
            # genuine CR30.
            dev.identify()
            self._remember_address(dev)
            return dev
        except Exception as exc:        # noqa: BLE001 — fall back to discovery
            # CLOSE IT, OR THE SCAN CANNOT FIND IT: a connected peripheral
            # stops advertising, so a transiently-failing real CR30 would
            # be invisible to the very fallback meant to recover it.
            if dev is not None:
                try:
                    dev.close()
                except Exception:       # noqa: BLE001 — teardown only
                    log.debug("could not close %s", remembered, exc_info=True)
            log.info("CR30: the device at the remembered Bluetooth address "
                     "did not answer as a CR30 (%s); searching for the "
                     "instrument instead", exc)
    dev = CR30.open_ble(
        address=None if self._address == remembered else self._address)
    self._remember_address(dev)
    return dev
```

Plus: move `scratchpad/test_ble_remembered_address_is_identified.py` into
`tests/` (it needs only the module docstring's path note removed); keep
the existing `test_cr30_bluetooth_remembers_the_address.py` untouched —
its stub sits above the seam this fault lives in.

No upgrade-time clearing of `cr30_ble_address` (Q4): it self-heals, and
clearing would punish every beta.1 user whose stored address is their own
instrument.

## Unproven — needs hardware or an on-screen run

- **`READ_MEASUREMENT` (`bb 02 10`) never mutates device state.** Strongly
  supported (vendor app uses it as a read; the stored-slot staleness the
  codebase measures depends on it; EXP-BLE-012's method presumes it) but
  no dedicated experiment exists. 30-second hardware check: read twice,
  button press, read twice — the first pair must be bit-identical.
- **Whether a BLE frame exists that returns the unit id string** (the
  `AA 0A 01` twin) — would upgrade the axis check to a real per-unit
  identity. Hardware probe, or the manufacturer email's question list.
- **Real-world identify latency over the radio** — the 1.8–2.15 s figure
  is from the code's constants and the offline harness; the owner's unit
  answers a poll in ~250 ms, so the estimate should hold, but only a live
  session shows it inside his "takes a while" budget.
- **bleak's connect-timeout behaviour to an absent remembered address on
  macOS** (Q8-1) — asserted from bleak's contract, not measured.
