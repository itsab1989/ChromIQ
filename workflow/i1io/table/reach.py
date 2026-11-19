# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 the ChromIQ authors. Part of ChromIQ (https://github.com/itsab1989/ChromIQ).
"""4.3.49: THIS TABLE'S REACH, remembered and learned from (FOR THE SAFETY REVIEW).

Basti's ruling of 19 Nov 2026: where recordings happened to take the arm is not a safety fence;
the person who aims at a sheet's points knows the arm can reach them. The targets of a measurement
are bounded by what the person AIMED AT (geometry.aimed_front_y, in the job), not by this module.

What this module keeps, per table, ONLY TO RECORD AND LEARN (nothing here allows or refuses a
move, with one exception below): the extremes of the OPENING positions (``;p025``, p0) this table
has verifiably been at, and how each was learned:

* ``free``   a stable p0 reading of a free arm (two readings within STILL_UNITS, nothing sent
             between that could move it);
* ``motor``  a p0 reading right after a computed move that arrived within the arrival
             tolerance (5 units);
* ``recordings`` the model's defaults (front Y 2773, the frontmost p0 in the recordings before
             19 Nov 2026; X -1434, the smallest X a free arm was read at).

THE ONE USE IN A DECISION: ``motor_front_y``, the frontmost place THIS table's motors brought the
opening to and it arrived there. Beyond it, the first motor visit keeps the careful approach of
4.3.48 (the creep: steps of at most 5 mm, each arrival checked); up to it, the creep is not
repeated in a later sitting. That only spares a repetition; it never lets a target past the aimed
area.

WHERE IT IS STORED. One settings value (``i1io_table_reach``), JSON: a random salt made on this
computer and, per table, a key: the first 16 hex digits of HMAC-SHA256(salt, SHA-256 of the first
88 bytes of the table's memory block u8 0x6000, which hold its serial field). The block is read in
every opening, before anything moves; the table module keeps only that hash, in memory. Neither the
serial nor the unsalted hash is ever written to settings, logs or diagnostics; the diagnostics carry
the salted key only, and the salt never leaves the settings file. A stored value is validated on
load; anything implausible is ignored, never trusted.

NOTHING HERE SENDS ANYTHING.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import math
import secrets
import time
from dataclasses import dataclass, field

from . import geometry as geo

#: the model's defaults ("recordings")
DEFAULT_FRONT_Y = geo.FRONTMOST_Y_REACHED
DEFAULT_RIGHT_END_X = geo.SMALLEST_X_REACHED
#: the frontmost value a stored reach is believed up to (geometry's absolute backstop)
CEILING_Y = geo.REACH_CEILING_Y
#: two readings of a still arm agree within this (session_table.STILL_UNITS, the stillness
#: check before every move of a free arm)
STILL_UNITS = 2
HOW = ("recordings", "free", "motor")
SETTINGS_KEY = "i1io_table_reach"
#: how much memory-block identity the key is made from (bytes 0..87: the block's head and its
#: serial field; the white tile values begin at byte 88)
IDENT_BYTES = 88


def ident_of_memory_block(data_hex: str) -> "str | None":
    """SHA-256 (hex) of the first IDENT_BYTES bytes of the memory block's answer, or None when
    it is not that long or not hex. Called by the table module only; the result stays in memory
    and is salted before it is used as a key (:func:`table_key`)."""
    try:
        raw = bytes.fromhex(str(data_hex)[:2 * IDENT_BYTES])
    except ValueError:
        return None
    if len(raw) != IDENT_BYTES:
        return None
    return hashlib.sha256(raw).hexdigest()


def table_key(ident: "str | None", salt: str) -> "str | None":
    """The table's key: 16 hex digits of HMAC-SHA256(salt, ident). None without an ident."""
    if not ident or not salt:
        return None
    return hmac.new(salt.encode("ascii"), ident.encode("ascii"), hashlib.sha256).hexdigest()[:16]


def _int_or_none(v) -> "int | None":
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(f):
        return None
    return int(round(f))


def _point(v) -> "list[int] | None":
    if not isinstance(v, (list, tuple)) or len(v) != 2:
        return None
    a, b = _int_or_none(v[0]), _int_or_none(v[1])
    return None if a is None or b is None else [a, b]


@dataclass
class Reach:
    """What ChromIQ knows of one table's reach, in opening (p0) units of 0.1 mm."""
    key: "str | None" = None
    front_y: int = DEFAULT_FRONT_Y
    front_how: str = "recordings"
    front_at: "list[int] | None" = None
    front_when: "str | None" = None
    right_end_x: int = DEFAULT_RIGHT_END_X
    right_how: str = "recordings"
    left_x: "int | None" = None
    #: the frontmost Y a computed move of THIS table arrived at (within the tolerance)
    motor_front_y: "int | None" = None
    motor_front_when: "str | None" = None
    #: changed since loaded (the job stores it then)
    dirty: bool = field(default=False, compare=False)

    # ---- learning --------------------------------------------------------------------------
    def learn(self, p, how: str, when: "str | None" = None) -> "list[str]":
        """Extend the extremes by the opening position *p*, learned *how*. Returns what grew."""
        if how not in HOW[1:]:
            raise ValueError(f"unknown way of learning: {how!r}")
        q = _point(p)
        if q is None:
            return []
        when = when or time.strftime("%Y-%m-%d %H:%M")
        grew = []
        if q[1] > self.front_y:
            self.front_y, self.front_how, self.front_at, self.front_when = q[1], how, q, when
            grew.append("front")
        if q[0] < self.right_end_x:
            self.right_end_x, self.right_how = q[0], how
            grew.append("right")
        if self.left_x is None or q[0] > self.left_x:
            self.left_x = q[0]
            grew.append("left")
        if grew:
            self.dirty = True
        return grew

    def learn_motor_target(self, target) -> "list[str]":
        """A computed move to *target* arrived within the tolerance: its target counts as a place
        THIS table's motors reach (the creep is spared up to it in a later sitting)."""
        q = _point(target)
        if q is None or (self.motor_front_y is not None and q[1] <= self.motor_front_y):
            return []
        self.motor_front_y = q[1]
        self.motor_front_when = time.strftime("%Y-%m-%d %H:%M")
        self.dirty = True
        return ["motor_front"]

    # ---- storing ---------------------------------------------------------------------------
    def as_dict(self) -> dict:
        out = {"front_y": self.front_y, "front_how": self.front_how, "front_at": self.front_at,
               "front_when": self.front_when, "right_end_x": self.right_end_x,
               "right_how": self.right_how, "left_x": self.left_x,
               "motor_front_y": self.motor_front_y, "motor_front_when": self.motor_front_when}
        return out

    @classmethod
    def from_dict(cls, key: "str | None", d) -> "Reach":
        """A stored reach, validated: every value that is not a plausible number, or a way of
        learning that is not known, falls back to the model's default (never trusted)."""
        r = cls(key=key)
        if not isinstance(d, dict):
            return r
        fy = _int_or_none(d.get("front_y"))
        if fy is not None and DEFAULT_FRONT_Y < fy <= CEILING_Y \
                and d.get("front_how") in HOW[1:]:
            r.front_y, r.front_how = fy, str(d["front_how"])
            r.front_at = _point(d.get("front_at"))
            r.front_when = str(d.get("front_when") or "")[:20] or None
        rx = _int_or_none(d.get("right_end_x"))
        if rx is not None and DEFAULT_RIGHT_END_X - 300 <= rx < DEFAULT_RIGHT_END_X \
                and d.get("right_how") in HOW[1:]:
            r.right_end_x, r.right_how = rx, str(d["right_how"])
        lx = _int_or_none(d.get("left_x"))
        if lx is not None and -2000 <= lx <= 4000:
            r.left_x = lx
        mf = _int_or_none(d.get("motor_front_y"))
        if mf is not None and 0 <= mf <= CEILING_Y:
            r.motor_front_y = mf
            r.motor_front_when = str(d.get("motor_front_when") or "")[:20] or None
        return r


class ReachStore:
    """Where the reaches of every table this computer has driven are kept: one JSON value
    behind *load* / *save* (the window's: the app's settings; tests: memory)."""

    def __init__(self, load, save):
        self._load, self._save = load, save
        #: the window passes the app's settings (ui.i1io_table_window.reach_store)

    def _all(self) -> dict:
        try:
            raw = self._load()
            data = json.loads(raw) if raw else {}
        except Exception:      # noqa: BLE001 - a broken value is ignored, never trusted
            data = {}
        if not isinstance(data, dict):
            data = {}
        if not isinstance(data.get("tables"), dict):
            data["tables"] = {}
        salt = data.get("salt")
        if not (isinstance(salt, str) and len(salt) == 32
                and all(c in "0123456789abcdef" for c in salt)):
            data["salt"] = secrets.token_hex(16)
            data["tables"] = {}           # entries under another salt can never be found
            data["fresh"] = True
        return data

    def salt(self) -> str:
        """This computer's salt (made and stored the first time it is asked for)."""
        data = self._all()
        if data.get("fresh"):
            self._store_text(data)
        return data["salt"]

    def get(self, key: "str | None") -> Reach:
        if not key:
            return Reach(key=None)
        return Reach.from_dict(key, self._all()["tables"].get(key))

    def put(self, reach: Reach) -> bool:
        """Store *reach* under its key (nothing without a key). True when written."""
        if not reach.key:
            return False
        data = self._all()
        data["tables"][reach.key] = reach.as_dict()
        ok = self._store_text(data)
        if ok:
            reach.dirty = False
        return ok

    def _store_text(self, data: dict) -> bool:
        try:
            self._save(json.dumps({"salt": data["salt"], "tables": data["tables"]},
                                  sort_keys=True))
            return True
        except Exception:      # noqa: BLE001 - never in the way of the measurement
            return False


class MemoryReachStore(ReachStore):
    """A store in memory (tests, and a job built without one)."""

    def __init__(self, text: str = ""):
        self.text = text
        super().__init__(lambda: self.text, self._set)

    def _set(self, text: str) -> None:
        self.text = text
