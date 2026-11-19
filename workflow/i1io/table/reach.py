# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 the ChromIQ authors. Part of ChromIQ (https://github.com/itsab1989/ChromIQ).
"""4.3.49: THIS TABLE'S REACH, learned once and remembered (FOR THE SAFETY REVIEW).

Basti's ruling of 19 Nov 2026: where recordings happened to take the arm is not a safety fence;
a place the arm reached by hand is a place the arm can be. The catch (the analysis of his first
4.3.48 run, section b): the person aims with the SIGHT, which sits about 31 mm in front of the
MEASURING OPENING, and every move target is an opening position. So the reach is kept in OPENING
terms (``;p025``, p0) and compared with targets directly; no sight offset is applied anywhere.

WHAT IS KEPT, PER TABLE. The extremes of the opening positions this table has verifiably been
at, and how each was learned:

* ``push``   the guided step: the free arm pushed gently to the front by the person, the
             instrument's button (or the page's button) pressed, two p0 readings 0.3 s apart that
             agree within STILL_UNITS (the stillness check every free-arm move already uses);
* ``free``   any other stable p0 reading of a free arm (two readings within STILL_UNITS with
             nothing sent between that could move it);
* ``motor``  a p0 reading right after a computed move that arrived within the arrival
             tolerance (5 units);
* ``recordings`` the model's defaults, used until the table has taught ChromIQ more: front Y
             2773 (the frontmost p0 in every recording before 19 Nov 2026), right end X -1434
             (two independent hand pushes stopped there, R1 272.108 and the volunteer's free arm
             of 19 Nov 2026).

Only the FRONT bounds a target (the analysis, section i: at the back and on the right the
opening always lies beyond the sight, so an aim proves enough there; the left is far from every
chart target). The target area's front is ``front_y - MARGIN`` (5 mm inside), never beyond
geometry's absolute FRONT_CAP_Y, and never behind the measuring area's proven front.

WHERE NOTHING STARTS. No computed move and no homing starts within END_MARGIN of a known END
(the analysis, section i: the one non-zero status in 825 recorded answers, R1 272.124, came from
a homing started at the right stop). The ends are the right end X (the defaults and any p0 read
further right) and, once the guided step ran, the front Y (the person pushed "as far as it goes",
so it is treated as the end, even if it was pressed short).

WHERE IT IS STORED. One settings value (``i1io_table_reach``), JSON: a random salt made on this
computer and, per table, a key: the first 16 hex digits of HMAC-SHA256(salt, SHA-256 of the
first 88 bytes of the table's memory block u8 0x6000), which hold its serial field. The block is
read in every opening, before anything moves (the table module keeps only that hash in memory;
the block itself is never written down). Neither the serial nor the unsalted hash is ever
written to settings, logs or diagnostics; the diagnostics carry the salted key only, and the salt
never leaves the settings file. A stored value is validated on load (numbers inside the
physically possible range, known ways of learning); anything else is ignored, never trusted.

NOTHING HERE SENDS ANYTHING. The job reads p0 and p1 in their recorded forms; this module only
keeps numbers.
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

#: 5 mm inside every learned end (the analysis, section i: encoder drift at rest up to 4.7 mm,
#: arrival tolerance 0.5 mm)
MARGIN = geo.MARGIN
#: A move or homing never STARTS within this of a known end. A target lies at most at the end
#: minus MARGIN and the arm may read up to ARRIVAL_SLACK beyond its target, so an arm the motors
#: put on the frontmost allowed target may still start from there.
END_MARGIN = MARGIN - geo.ARRIVAL_SLACK
#: the model's defaults ("recordings")
DEFAULT_FRONT_Y = geo.FRONTMOST_Y_REACHED
DEFAULT_RIGHT_END_X = geo.SMALLEST_X_REACHED
#: the frontmost value a stored reach may hold (geometry's absolute cap plus the margin); a
#: reading beyond it is kept for the diagnostics but bounds nothing further out
CEILING_Y = geo.FRONT_CAP_Y + MARGIN
#: two readings of a still arm agree within this (session_table.STILL_UNITS, the stillness
#: check before every move of a free arm)
STILL_UNITS = 2
HOW = ("recordings", "push", "free", "motor")
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
    motor_front_y: "int | None" = None
    #: the guided step ran for this table (its front is then treated as the END)
    pushed: bool = False
    push_at: "list[int] | None" = None
    #: the sight's reading on the same press (p1), and p0 - p1 (this table's sight offset)
    push_sight: "list[int] | None" = None
    push_when: "str | None" = None
    #: changed since loaded (the job stores it then)
    dirty: bool = field(default=False, compare=False)

    # ---- the bounds ------------------------------------------------------------------------
    def front_bound(self) -> int:
        """The frontmost Y a computed target may have on this table: the learned front minus
        MARGIN, never beyond geometry's absolute cap, never behind the proven measuring area."""
        fy = min(int(self.front_y), CEILING_Y) - MARGIN
        return max(geo.MEASURING_AREA.ymax, min(fy, geo.FRONT_CAP_Y))

    def front_end(self) -> "int | None":
        """The front END (only once the person pushed the arm to it), else None."""
        return int(self.front_y) if self.pushed else None

    def near_end(self, p) -> "str | None":
        """"front" / "right" when *p* lies within END_MARGIN of a known end (or beyond it)."""
        try:
            x, y = float(p[0]), float(p[1])
        except (TypeError, ValueError, IndexError):
            return None
        end = self.front_end()
        if end is not None and y > end - END_MARGIN:
            return "front"
        if x < self.right_end_x + END_MARGIN:
            return "right"
        return None

    def away_from_end_mm(self, p, side: str) -> int:
        """Whole mm (rounded up, one to spare) by which an arm at *p* must be moved away from
        the *side* end before anything may start there."""
        if side == "front" and self.front_end() is not None:
            over = float(p[1]) - (self.front_end() - END_MARGIN)
        elif side == "right":
            over = (self.right_end_x + END_MARGIN) - float(p[0])
        else:
            return 0
        return int(math.ceil(max(0.0, over) / 10.0)) + 1

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
        if how == "motor" and (self.motor_front_y is None or q[1] > self.motor_front_y):
            self.motor_front_y = q[1]
            grew.append("motor_front")
        if grew:
            self.dirty = True
        return grew

    def learn_push(self, p0, p1=None, when: "str | None" = None) -> "list[str]":
        when = when or time.strftime("%Y-%m-%d %H:%M")
        grew = self.learn(p0, "push", when)
        self.pushed = True
        self.push_at = _point(p0)
        self.push_sight = _point(p1)
        self.push_when = when
        self.dirty = True
        return grew

    # ---- storing ---------------------------------------------------------------------------
    def as_dict(self) -> dict:
        out = {"front_y": self.front_y, "front_how": self.front_how, "front_at": self.front_at,
               "front_when": self.front_when, "right_end_x": self.right_end_x,
               "right_how": self.right_how, "left_x": self.left_x,
               "motor_front_y": self.motor_front_y, "pushed": self.pushed,
               "push_at": self.push_at, "push_sight": self.push_sight,
               "push_when": self.push_when}
        if self.push_at and self.push_sight:
            out["push_sight_offset"] = [self.push_at[0] - self.push_sight[0],
                                        self.push_at[1] - self.push_sight[1]]
        return out

    @classmethod
    def from_dict(cls, key: "str | None", d) -> "Reach":
        """A stored reach, validated: every value that is not a plausible number, or a way of
        learning that is not known, falls back to the model's default (never trusted)."""
        r = cls(key=key)
        if not isinstance(d, dict):
            return r
        fy = _int_or_none(d.get("front_y"))
        if fy is not None and DEFAULT_FRONT_Y < fy <= CEILING_Y + 1000 \
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
        if mf is not None and 0 <= mf <= r.front_y:
            r.motor_front_y = mf
        if d.get("pushed") is True and r.front_how != "recordings":
            r.pushed = True
            r.push_at = _point(d.get("push_at"))
            r.push_sight = _point(d.get("push_sight"))
            r.push_when = str(d.get("push_when") or "")[:20] or None
        return r


class ReachStore:
    """Where the reaches of every table this computer has driven are kept: one JSON value
    behind *load* / *save* (the window's: the app's settings; tests: memory)."""

    def __init__(self, load, save):
        self._load, self._save = load, save

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
            self._write(data)
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
        ok = self._write(data)
        if ok:
            reach.dirty = False
        return ok

    def _write(self, data: dict) -> bool:
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


def settings_store() -> ReachStore:
    """The app's store: one value in ChromIQ's settings (sandboxed by CHROMIQ_SETTINGS_FILE).
    Each load and save makes its own AppSettings, so it may be used from the job's thread."""
    def load() -> str:
        from core.settings import AppSettings
        return str(AppSettings().get(SETTINGS_KEY, "") or "")

    def save(text: str) -> None:
        from core.settings import AppSettings
        AppSettings().set(SETTINGS_KEY, text)
    return ReachStore(load, save)
