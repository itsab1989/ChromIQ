"""Learning one unit's stored tile constant, so every owner gets the guard.

WHY THIS EXISTS. With a magnet at the aperture the CR30 does not measure: it
performs a white calibration and hands back a stored constant. `TILE_SIGNATURE`
in `measurement.py` is THE OWNER'S unit's constant, hard-coded, and the only
other CR30 anyone has data for sits up to 4.69 %R away — 94x the 0.05 tolerance
— so on that unit the tile check returns False for every gated reading and
protects nobody. Learning the constant per unit is the fix the module has been
asking for in a comment since it was written.

WHERE THE VALUE COMES FROM, AND WHY NOT THE OBVIOUS PLACE. The obvious place is
the read-back after a white calibration. That is WRONG and the codebase already
proves it: after `CAL_WHITE` the stored slot is ZERO-FILLED, which is why
`DeviceReader.calibrate`'s read-back passes `allow_dark=True`. Learning there
would store a spectrum of zeros.

What actually returns the constant is a GATED acquisition — a press with the cap
seated. Measured on 2026-08-30 (EXP-TILE-002/003/004): every capped press
returned the constant, and the two presses within a run were bit-identical.

PROVENANCE IS THE WHOLE POINT. A learned signature is a safety check; learning
the wrong thing disarms it silently, and a patch colour learned as "the tile"
would refuse that colour for ever. So a value is only accepted with proof that
it was gated:

  * USB — the unsolicited `BB 01 09` header carries the gate flag at offset 24.
    One press with the flag set is proof.
  * Bluetooth — there is no known flag, so proof comes from the data itself: two
    presses that are BIT-IDENTICAL. Genuine consecutive readings never are, even
    with nothing touched (0.05 %R untouched spread, EXP-TILE-004; 0.056 %
    worst-band SD, EXP-MEAS-001). That rule is unit-independent and needs no
    hardware fact we do not already have.

⚠ A capped press is HARMLESS to the white reference — measured, not assumed
(EXP-TILE-002/003/004: the post-cap paper shifts went -3.43 %R one run and
+4.72 %R the next, and a damaged reference is monotonic; repositioning alone
accounts for 2.36 %R with no cap involved). That is what makes it acceptable to
ask the user for one.
"""
from __future__ import annotations

import json
import logging

log = logging.getLogger(__name__)

#: Per-band agreement required against a LEARNED signature.
#:
#: Not strict bit-equality, deliberately. The learned value and a later gated
#: read pass through the same `round(x, 6)` in both parsers, so they ARE bit-
#: equal on every byte measured so far. But the failure mode of exact equality
#: is a SILENT DISARM: one ulp of drift from a parser tweak or a firmware change
#: and the guard quietly stops existing, which is the worst thing a safety check
#: can do. 0.001 %R is 20x the largest residue ever observed, 50x below the
#: instrument's own noise floor, and ~4,700x below the nearest other unit's tile
#: — so it behaves exactly as bit-equality on real data and cannot be killed by
#: a rounding change.
LEARNED_TOLERANCE = 0.001

#: Where the learned signatures live: a JSON object keyed by unit id, so a
#: second instrument never inherits the first one's constant.
#:
#: Two units sharing the SAME constant is harmless -- each learns its own, the
#: values happen to coincide, and the guard works for both. The case worth
#: keying against is the opposite one: unit B's gated reads would not match unit
#: A's signature (the only two units ever measured sit 4.69 %R apart), so B
#: would be left UNARMED. That is the safe failure direction, and keying removes
#: it entirely for anyone who owns two.
SIGNATURE_KEY = "cr30_tile_signatures"

#: The key used when the unit could not be identified. Over Bluetooth the reply
#: carries only the spectral axis, and the remembered-address fast path never
#: scans, so the advertised name is not available there either.
UNKNOWN_UNIT = ""


def _settings():
    from core.settings import AppSettings
    return AppSettings()


def _load() -> dict:
    try:
        raw = str(_settings().get(SIGNATURE_KEY, "") or "")
        data = json.loads(raw) if raw else {}
        return data if isinstance(data, dict) else {}
    except Exception:                # noqa: BLE001 — a guard, never a hard need
        log.debug("could not read the learned CR30 tile signatures",
                  exc_info=True)
        return {}


def learned_signature(unit_id: str | None = None) -> list[float] | None:
    """The signature to arm this unit's guard with, or None to leave it off.

    * A KNOWN unit gets its own signature and nothing else. Never another
      unit's: applying A's constant to B would leave B unarmed anyway (their
      constants differ), so guessing buys nothing and risks refusing a patch.
    * An UNKNOWN unit -- the Bluetooth fast path -- is armed only when exactly
      one signature has ever been learned on this machine. With two instruments
      and no way to tell them apart, unarmed is the honest answer.
    """
    store = _load()
    if not store:
        return None
    try:
        if unit_id:
            values = store.get(unit_id)
            if values is None:
                log.info("CR30: no tile signature learned for unit %s — the "
                         "magnet guard stays on the built-in constant",
                         unit_id)
                return None
        elif len(store) == 1:
            values = next(iter(store.values()))
        else:
            log.info("CR30: %d instruments have learned signatures and this "
                     "one did not identify itself — leaving the guard unarmed "
                     "rather than guessing which", len(store))
            return None
        if not isinstance(values, list) or not values:
            return None
        return [float(v) for v in values]
    except Exception:                # noqa: BLE001 — a guard, never a hard need
        log.debug("could not read the learned CR30 tile signature",
                  exc_info=True)
        return None


def adopt_address_key(address: str | None, unit_id: str | None) -> bool:
    """Re-file a signature learned under `ble:<address>` under the unit's id.

    Knut, 2026-09-03: *"in a very short test via usb the read single patches
    tool asked me to learn the white tile of the device via usb again although
    chromiq should already have learned it."*

    He had learned it over Bluetooth. The store is shared, but the KEY was per
    transport: the remembered-address fast path never scans, so it had no unit
    id and filed under the address, and USB -- which does know the unit's
    `second_id` -- looked under a key that was not there.

    The identity of a physical instrument is its own id, never the address. A
    CoreBluetooth UUID is host-local, changes when a pairing database is reset,
    and says nothing about which unit answers at it. So the address is demoted
    to what it always was, a locator, and the legacy key is migrated the ONE
    moment it can be migrated safely: while connected to that address, having
    just heard the device name itself. Same link, same instrument, no guess.

    Deliberately NOT done at a USB open. Nothing there proves which unit an
    `ble:` key belonged to, and adopting the wrong one would make
    `guard_is_armed()` answer True while the guard matched nothing -- a false
    assurance, which is worse than the honest "unarmed" it replaces.
    """
    if not address or not unit_id:
        return False
    legacy = f"ble:{address}"
    if legacy == str(unit_id):
        return False
    try:
        store = _load()
        values = store.get(legacy)
        if values is None:
            return False
        if store.get(str(unit_id)) is not None:
            # The unit already has its own signature. Drop the duplicate rather
            # than leave two keys for one instrument to drift apart.
            store.pop(legacy, None)
            _settings().set(SIGNATURE_KEY, json.dumps(store))
            log.info("CR30: dropped the stale address key %s -- unit %s has "
                     "its own learned signature", legacy, unit_id)
            return False
        store[str(unit_id)] = values
        store.pop(legacy, None)
        _settings().set(SIGNATURE_KEY, json.dumps(store))
        log.info("CR30: the tile signature filed under %s belongs to unit %s, "
                 "which has just said so over that very connection -- re-filed "
                 "under the unit, so USB and Bluetooth now share it",
                 legacy, unit_id)
        return True
    except Exception:                # noqa: BLE001 — a guard, never a hard need
        log.debug("could not re-file the CR30 tile signature", exc_info=True)
        return False


def remember_signature(values, unit_id: str | None = None) -> bool:
    """Store a proven signature under this unit's id. Returns whether it was."""
    try:
        vals = [float(v) for v in values]
        if not vals:
            return False
        store = _load()
        store[str(unit_id or UNKNOWN_UNIT)] = vals
        _settings().set(SIGNATURE_KEY, json.dumps(store))
        log.info("CR30: learned the tile signature of unit %s (%d bands) — "
                 "the magnet guard is now armed for it",
                 unit_id or "(unidentified)", len(vals))
        return True
    except Exception:                # noqa: BLE001 — never fail an open over it
        log.debug("could not store the learned CR30 tile signature",
                  exc_info=True)
        return False


def forget_signature(unit_id: str | None = None) -> None:
    """Disarm one unit, or every unit when no id is given."""
    try:
        store = {} if unit_id is None else _load()
        if unit_id is not None:
            store.pop(str(unit_id), None)
        _settings().set(SIGNATURE_KEY, json.dumps(store))
    except Exception:                # noqa: BLE001 — teardown only
        log.debug("could not clear the learned CR30 tile signature",
                  exc_info=True)


class TileLearner:
    """Collects capped presses and says when the tile constant is PROVEN.

    Feed it every reading taken during the learning step. It returns the proven
    signature exactly once, and None until it has proof. It never guesses: a
    reading with no gate flag and no bit-identical partner is not accepted, no
    matter how tile-like it looks — "looks like the tile" is what the guard is
    for, and using it here would make the guard validate itself.
    """

    def __init__(self) -> None:
        self._candidate: list[float] | None = None
        #: Why the accepted value was believed. Recorded so a log or a report
        #: can say which rule fired rather than merely that one did.
        self.provenance: str = ""

    def offer(self, measurement) -> list[float] | None:
        """Return the proven signature, or None to ask for another press."""
        values = list(getattr(measurement, "values", ()) or ())
        if not values:
            return None
        if getattr(measurement, "gate_flag", None) is True:
            self.provenance = ("the device's own header flagged it gated "
                               "(frame offset 24 = 1)")
            return values
        if self._candidate is not None and values == self._candidate:
            self.provenance = ("two presses were bit-identical, which genuine "
                               "readings never are")
            return values
        self._candidate = values
        return None

    @property
    def needs_another_press(self) -> bool:
        """True once one unproven press is held and a second would settle it."""
        return self._candidate is not None
