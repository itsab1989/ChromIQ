## In progress

[CR30-VERIFY] started Fr 28 Aug 2026 23:51:35 CEST

# 13 — VERIFY (round 3)

Branch `feature/cr30-instrument-159`, HEAD `73882a59`. Read-only on the repo.
V-numbers are mine; T/A/B/C/D/S numbers are 12_skeptic2 / 11_skeptic.

## STATUS
- [x] read 12_skeptic2, 11_skeptic, git log, diffs since 6295c91a
- [ ] retry-loop attack (worry a)
- [ ] calibration event loop (worry b)
- [ ] placement (worry c) / double-show (d) / _user_quit (e) / Build Profile (f) / i18n (g)
- [ ] on-screen run + screenshots

---

## FINDINGS (running, unordered until the end)

### V-1 [BLOCKER — worry (a), PROVEN BELOW] the re-arm burns all five retries instantly on BLE after a magnet-gate refusal

`workflow/cr30/device.py:271-301`, the BLE wait loop:

```python
accepted = self._previous            # :235 — captured BEFORE the loop
prev = accepted.values if accepted else None
...
m = self.read_measurement(enforce=False)   # :281 — does NOT store _previous
if m.values != prev:
    m.check_usable(accepted)               # :298 — RAISES on the magnet gate
    self._previous = m                     # :299 — only on acceptance
```

`read_measurement(enforce=False)` never assigns `self._previous`
(`device.py:324-331` assigns only under `enforce`), and `check_usable` raises
*before* `:299`. So a refused reading leaves `self._previous` untouched.

The re-arm (`measure_bridge.py:359-360`) then calls `read_next_measurement`
again. `accepted` is the same as before, `prev` is the same, and the device is
still holding the **same offending reading**. `m.values != prev` is still True,
`check_usable(accepted)` raises the identical error — **with no button press
and no wait**. Five retries, five instant raises, `read_gave_up`.

Time cost per retry is one BLE `ask()` round trip. The user's window to take
the cap off is ~1 second, not "five presses".

**It only bites once one patch has been accepted** (`accepted is not None`).
On the very first patch of a session `accepted` is None, the baseline probe at
`:245-269` makes the offending reading the baseline, and the retry then waits
properly. So the exact case B-1 named — *cap on at patch A1* — happens to be
the ONE case that behaves; every magnet-gate refusal from patch A2 onward is
the burn.

USB is not affected: `read_next_measurement`'s USB branch waits for the
unsolicited button header (`:216`) before it reads at all, so a retry blocks on
the next press.

### V-2 [MAJOR] `DeviceReader.calibrate(timeout=30.0)` — the timeout is DEAD

`workflow/cr30/measure_bridge.py:464-496`. `timeout` is accepted, documented by
its default, and **never referenced in the body**. Neither `calibrate_white()`
nor the read-back `read_measurement(enforce=False)` is bounded.

### V-3 [MAJOR] `calibrate`'s `cancelled` is checked ONCE, before any work

Same function, `:484-485`. After that single check the call does
`self._dev.calibrate_white()` and a read-back with no further cancel test. A
Cancel pressed while the frame is in flight does nothing at all; the predicate
can only win the race before the transport is even opened. A-4 asked for the
modal's close to be "routed to the calibration's own cancel" — it is routed to
a predicate that is no longer consulted.

### V-4 [MAJOR] `calibrate`'s docstring claims a baseline it does not set

`:471-474`: *"Sharing the handle also leaves the reading this takes as the
device's `_previous`, which is exactly the baseline the Bluetooth
change-detection needs, so the first patch no longer has to establish one."*

The read-back is `read_measurement(enforce=False)` (`:493`), and
`device.py:324` assigns `_previous` **only under `enforce`**. So `_previous`
stays None and patch A1 still runs the baseline probe. The stated benefit of
sharing the handle (A-2's "bonus for free") is not delivered. Harmless in
behaviour, but it is a false claim in a docstring written to be authoritative,
and the next reader will trust it.
