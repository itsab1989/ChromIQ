"""THE TWO PASSES OF A HAND DUAL SCAN ARE TWO UNITS (the owner, 2026-11-18:
"what if one of the 2 passes fails for an instrument on a strip? we would
then need to know that only this pass with or without uv needs to be
repeated").

Per strip this record keeps the state of each pass, the UV pass's
per-patch data (lamp-white units, already cut into the lamp pass's patches)
and which calibration each pass came from, so that:

* a measurement stopped after some strips have only their lamp pass keeps
  a complete, honest M0 for what was read (the main ``.ti3`` is the lamp
  passes, as always);
* M1 / M2 exist only for strips with both passes, and are offered for the
  measurement only when EVERY strip has both (:meth:`PassRecord.complete`);
* "Continue Measurement" asks only for the missing passes, strip by strip
  (:meth:`PassRecord.missing`), after a new dual calibration, and the
  record says when the passes come from more than one calibration;
* a lamp pass read again keeps the strip's UV pass only when that UV pass is
  proved to belong to the new lamp pass (:mod:`workflow.dual_scan.pairing`);
  otherwise the UV pass is marked to be read again (``lamp_pass_changed``).
  A good pass is never silently repeated: only the record says what is due.

WHERE: in the run, beside the conditions folder
(:meth:`core.file_manager.Run.dual_pass_record`), never in a shared file;
no serial number. A spot dual reading (lamp + UV on one patch in one press)
is one unit and does not use this record's split states (a failure reads the
patch again).
"""
from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from workflow.dual_scan.model import DualCalibration
from workflow.dual_scan.reasons import REASONS, DualScanRefused

VERSION = 1
OK, FAILED, MISSING, STALE = "ok", "failed", "missing", "stale"
LAMP, UV = "lamp", "uv"


def _hash(a) -> str:
    b = np.ascontiguousarray(np.round(np.asarray(a, dtype=float), 9)).tobytes()
    return hashlib.sha256(b).hexdigest()[:16]


@dataclass
class PassState:
    state: str = MISSING
    reason: str = ""
    calibration: str = ""
    lamp_hash: str = ""            # lamp: its readings; uv: the lamp pass it was proved against
    data: "list | None" = None     # uv only: [patches][bands]

    def to_json(self) -> dict:
        d = {"state": self.state, "reason": self.reason, "calibration": self.calibration,
             "lamp_hash": self.lamp_hash}
        if self.data is not None:
            d["data"] = self.data
        return d

    @classmethod
    def from_json(cls, d: dict) -> "PassState":
        return cls(str(d.get("state", MISSING)), str(d.get("reason", "")),
                   str(d.get("calibration", "")), str(d.get("lamp_hash", "")), d.get("data"))


@dataclass
class PassRecord:
    strips: "list[str]"
    calibrations: "dict[str, dict]" = field(default_factory=dict)
    lamp: "dict[str, PassState]" = field(default_factory=dict)
    uv: "dict[str, PassState]" = field(default_factory=dict)
    _lamp_values: "dict[str, list]" = field(default_factory=dict)

    def __post_init__(self):
        for s in self.strips:
            self.lamp.setdefault(s, PassState())
            self.uv.setdefault(s, PassState())

    # ---- calibrations
    def add_calibration(self, cal_id: str, calibration: DualCalibration) -> None:
        """A dual calibration (the UV-LED tile reading included); its values
        are kept so M1 / M2 of a strip can be worked out with the calibration
        its UV pass came from."""
        cal = calibration.checked(len(np.asarray(calibration.white).ravel()))
        self.calibrations[cal_id] = {
            "white": np.asarray(cal.white).tolist(), "uv_tile": np.asarray(cal.uv_tile).tolist(),
            "emis": np.asarray(cal.emis).tolist(),
            "lamp_clocks": cal.lamp_clocks, "uv_clocks": cal.uv_clocks}

    def calibration(self, cal_id: str) -> DualCalibration:
        c = self.calibrations.get(cal_id)
        if c is None:
            raise DualScanRefused("no_dual_calibration", cal_id)
        return DualCalibration(np.array(c["white"]), np.array(c["uv_tile"]), np.array(c["emis"]),
                               c.get("lamp_clocks"), c.get("uv_clocks"))

    # ---- the passes
    def _strip(self, strip: str) -> None:
        if strip not in self.lamp:
            raise KeyError(strip)

    def lamp_read(self, strip: str, lamp, cal_id: str) -> str:
        """A good lamp pass of *strip* (ArgyllCMS's recognition passed).
        Returns the UV pass's state afterwards."""
        self._strip(strip)
        h = _hash(lamp)
        old = self.lamp[strip]
        self.lamp[strip] = PassState(OK, "", cal_id, h)
        self._lamp_values[strip] = np.asarray(lamp, dtype=float).tolist()
        u = self.uv[strip]
        if u.state == OK and u.lamp_hash != h:
            try:
                from workflow.dual_scan.pairing import check_pairing
                check_pairing(lamp, u.data, self.calibration(u.calibration))
                u.lamp_hash = h                  # proved to belong to the new lamp pass
            except DualScanRefused:
                self.uv[strip] = PassState(STALE, "lamp_pass_changed", u.calibration, "", None)
        del old
        return self.uv[strip].state

    def pass_failed(self, strip: str, which: str, reason: str) -> None:
        """A pass that failed: only that pass is to be read again; the other
        one is kept."""
        self._strip(strip)
        if reason not in REASONS and which == UV:
            raise KeyError(reason)
        st = PassState(FAILED, reason)
        if which == LAMP:
            if self.lamp[strip].state != OK:
                self.lamp[strip] = st
            else:
                # a failed re-read keeps the good lamp pass
                pass
        elif which == UV:
            if self.uv[strip].state != OK:
                self.uv[strip] = st
        else:
            raise ValueError(which)

    def uv_read(self, strip: str, uv, cal_id: str, *, glowing: bool = True) -> str:
        """A UV pass of *strip*, already cut into its patches. Refused (state
        ``failed`` with the reason, previous good UV pass kept) when there is
        no good lamp pass, no dual calibration, or it does not belong to the
        lamp pass. Returns its state."""
        from workflow.dual_scan.pairing import check_pairing
        self._strip(strip)
        if self.lamp[strip].state != OK:
            raise DualScanRefused("uv_pass_missing", "no lamp pass for this strip")
        try:
            cal = self.calibration(cal_id)
            check_pairing(self._lamp_values[strip], uv, cal)
        except DualScanRefused as e:
            if not glowing and e.reason == "uv_pass_wrong_strip":
                pass                     # no glow: a mix-up cannot change M1 / M2
            else:
                if self.uv[strip].state != OK:
                    self.uv[strip] = PassState(FAILED, e.reason, cal_id)
                return FAILED
        self.uv[strip] = PassState(OK, "", cal_id, self.lamp[strip].lamp_hash,
                                   np.asarray(uv, dtype=float).tolist())
        return OK

    # ---- what the record says
    def missing(self) -> "list[tuple[str, str]]":
        """Every pass still due, strip by strip, lamp before UV."""
        out = []
        for s in self.strips:
            if self.lamp[s].state != OK:
                out.append((s, LAMP))
            if self.uv[s].state != OK:
                out.append((s, UV))
        return out

    def complete(self) -> bool:
        """M1 / M2 are offered for the measurement only when every strip has
        both passes."""
        return not self.missing()

    def strips_with_both(self) -> "list[str]":
        return [s for s in self.strips if self.lamp[s].state == OK and self.uv[s].state == OK]

    def calibrations_used(self) -> "list[str]":
        used = []
        for s in self.strips:
            for p in (self.lamp[s], self.uv[s]):
                if p.state == OK and p.calibration and p.calibration not in used:
                    used.append(p.calibration)
        return used

    def more_than_one_calibration(self) -> bool:
        return len(self.calibrations_used()) > 1

    # ---- on disk
    def to_json(self) -> dict:
        return {"version": VERSION, "strips": list(self.strips), "calibrations": self.calibrations,
                "lamp": {s: p.to_json() for s, p in self.lamp.items()},
                "uv": {s: p.to_json() for s, p in self.uv.items()},
                "lamp_values": self._lamp_values}

    @classmethod
    def from_json(cls, d: dict) -> "PassRecord":
        if int(d.get("version", 0)) != VERSION:
            raise ValueError("unknown pass record version")
        r = cls(list(d["strips"]), dict(d.get("calibrations") or {}))
        for s, p in (d.get("lamp") or {}).items():
            r.lamp[s] = PassState.from_json(p)
        for s, p in (d.get("uv") or {}).items():
            r.uv[s] = PassState.from_json(p)
        r._lamp_values = dict(d.get("lamp_values") or {})
        return r

    def save(self, path: "str | Path") -> None:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_name(p.name + ".tmp")
        tmp.write_text(json.dumps(self.to_json()), encoding="utf-8")
        os.replace(tmp, p)

    @classmethod
    def load(cls, path: "str | Path") -> "PassRecord":
        return cls.from_json(json.loads(Path(path).read_text(encoding="utf-8")))
