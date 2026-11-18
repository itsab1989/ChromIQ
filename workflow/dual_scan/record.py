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

WHAT IT KEEPS, AND NOTHING MORE (review of 2026-11-18, S5: run folders are
what people zip and send, and a calibration's white, UV-tile and emission
vectors would fingerprint an instrument across shared projects). Recomputing
M1 / M2 of a strip, and proving a UV pass belongs to a lamp pass, needs only:

* per calibration ``Te = (T / W) * EMIS`` at 380-550 nm (18 numbers; beyond
  550 nm the tables are zero and nothing is computed), and its clocks;
* per UV pass the UV readings already in the same emission units
  (``U * EMIS``) at 380-550 nm, per patch;
* per lamp pass its readings (M0, which the main file holds anyway).

The formula is unchanged by this: with ``W = 1`` and ``EMIS = 1`` in the
compact calibration, ``Ue`` and ``Te`` are exactly the stored numbers
(:meth:`PassRecord.strip_conditions`). The white (W), the tile under the UV
LED (T) and EMIS are never written; the full calibration lives only in
memory for the sitting that made it, because a UV pass must be converted
with the calibration it was read after.

THE PERSON'S CHOICE (the coordinator's decision of 2026-11-18): the main file
stays physically M0 (the lamp passes); the condition chosen in the Measure
tab's filter row is recorded here (:attr:`PassRecord.chosen`) and in the
files' header (``CHROMIQ_DUAL_CHOSEN``, :mod:`workflow.dual_scan.storage`).
"""
from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

import numpy as np

from workflow.dual_scan.model import WAVELENGTHS, DualCalibration
from workflow.dual_scan.reasons import NOTES, REASONS, DualScanRefused

VERSION = 2
#: the bands the record keeps (380-550 nm: the LED bands and the glow bands)
KEPT_NM = (380, 550)
_KEPT = (WAVELENGTHS >= KEPT_NM[0]) & (WAVELENGTHS <= KEPT_NM[1])
CHOICES = ("M0", "M1", "M2")


def _pad(v) -> np.ndarray:
    """A kept 380-550 nm vector (or rows) back on the 36 bands, zeros beyond."""
    a = np.asarray(v, dtype=float)
    if a.ndim == 1:
        out = np.zeros(WAVELENGTHS.size)
        out[_KEPT] = a
        return out
    out = np.zeros((a.shape[0], WAVELENGTHS.size))
    out[:, _KEPT] = a
    return out
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
    data: "list | None" = None     # uv only: [patches][380-550 nm], emission units (U * EMIS)
    notes: "list[str]" = field(default_factory=list)   # NOTES ids: what could not be checked

    def to_json(self) -> dict:
        d = {"state": self.state, "reason": self.reason, "calibration": self.calibration,
             "lamp_hash": self.lamp_hash}
        if self.data is not None:
            d["data"] = self.data
        if self.notes:
            d["notes"] = list(self.notes)
        return d

    @classmethod
    def from_json(cls, d: dict) -> "PassState":
        return cls(str(d.get("state", MISSING)), str(d.get("reason", "")),
                   str(d.get("calibration", "")), str(d.get("lamp_hash", "")), d.get("data"),
                   [str(n) for n in (d.get("notes") or []) if str(n) in NOTES])


@dataclass
class PassRecord:
    strips: "list[str]"
    calibrations: "dict[str, dict]" = field(default_factory=dict)
    lamp: "dict[str, PassState]" = field(default_factory=dict)
    uv: "dict[str, PassState]" = field(default_factory=dict)
    _lamp_values: "dict[str, list]" = field(default_factory=dict)
    #: the condition chosen in the Measure tab (the main file stays M0)
    chosen: str = "M0"
    #: Build Profile's "Build from" was pre-set to :attr:`chosen` once (the
    #: UI step): never again, so a later choice of the person's stands
    preset_done: bool = False
    #: this sitting's full calibrations, in memory only (never saved)
    _full: "dict[str, DualCalibration]" = field(default_factory=dict)

    def __post_init__(self):
        for s in self.strips:
            self.lamp.setdefault(s, PassState())
            self.uv.setdefault(s, PassState())
        if self.chosen not in CHOICES:
            raise ValueError(self.chosen)

    # ---- the person's choice
    def choose(self, cond: str) -> None:
        """The condition chosen in the Measure tab (M0, M1 or M2)."""
        c = str(cond).upper()
        if c not in CHOICES:
            raise ValueError(cond)
        self.chosen = c

    # ---- calibrations
    def add_calibration(self, cal_id: str, calibration: DualCalibration) -> None:
        """A dual calibration (the UV-LED tile reading included). Kept: Te at
        380-550 nm and the clocks (see the module docstring); the full
        calibration stays in memory for this sitting's UV passes."""
        cal = calibration.checked(len(np.asarray(calibration.white).ravel()))
        if np.asarray(cal.white).size != WAVELENGTHS.size:
            raise DualScanRefused("no_dual_calibration", "bands")
        self._full[cal_id] = cal
        self.calibrations[cal_id] = {
            "te": np.asarray(cal.te())[_KEPT].tolist(),
            "lamp_clocks": cal.lamp_clocks, "uv_clocks": cal.uv_clocks}

    def calibration(self, cal_id: str) -> DualCalibration:
        """The COMPACT calibration (W = 1, T = Te, EMIS = 1): what the stored
        UV passes (emission units) are computed and checked with."""
        c = self.calibrations.get(cal_id)
        if c is None or "te" not in c:
            raise DualScanRefused("no_dual_calibration", cal_id)
        n = WAVELENGTHS.size
        return DualCalibration(np.ones(n), _pad(c["te"]), np.ones(n),
                               c.get("lamp_clocks"), c.get("uv_clocks"))

    def strip_conditions(self, strip: str, tables, s: float):
        """M0, M1, M2 of *strip* from the record alone (both passes good),
        with the calibration its UV pass came from."""
        from workflow.dual_scan.model import compute
        self._strip(strip)
        if self.lamp[strip].state != OK or self.uv[strip].state != OK:
            raise DualScanRefused("uv_pass_missing", strip)
        u = self.uv[strip]
        return compute(self._lamp_values[strip], _pad(u.data), self.calibration(u.calibration),
                       tables, s)

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
                ev = check_pairing(lamp, _pad(u.data), self.calibration(u.calibration))
                if not ev.checked:
                    raise DualScanRefused("lamp_pass_changed", "too dark to prove")
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

    def uv_read(self, strip: str, uv, cal_id: str, *, glowing: bool = True,
                aligned_checked: bool = True) -> str:
        """A UV pass of *strip*, already cut into its patches, in lamp-white
        units, read after calibration *cal_id* of THIS sitting. Refused
        (state ``failed`` with the reason, previous good UV pass kept) when
        there is no good lamp pass, no dual calibration, or it does not
        belong to the lamp pass. Accepted with a note when the pairing or the
        alignment could not be judged (*aligned_checked* False: the cut's
        ``CutResult.aligned_checked``). Returns its state."""
        from workflow.dual_scan.pairing import check_pairing
        self._strip(strip)
        if self.lamp[strip].state != OK:
            raise DualScanRefused("uv_pass_missing", "no lamp pass for this strip")
        notes: "list[str]" = [] if aligned_checked else ["alignment_not_checked"]
        try:
            full = self._full.get(cal_id)
            if full is None:
                raise DualScanRefused("no_dual_calibration", f"{cal_id}: not of this sitting")
            ue = np.atleast_2d(np.asarray(uv, dtype=float)) * np.asarray(full.emis)[None, :]
            ev = check_pairing(self._lamp_values[strip], ue, self.calibration(cal_id))
            if not ev.checked:
                notes.insert(0, "pairing_not_checked")
        except DualScanRefused as e:
            if not glowing and e.reason in ("uv_pass_wrong_strip", "uv_pass_no_uv_light"):
                ue = np.atleast_2d(np.asarray(uv, dtype=float)) * np.asarray(full.emis)[None, :]
            else:
                if self.uv[strip].state != OK:
                    self.uv[strip] = PassState(FAILED, e.reason, cal_id)
                return FAILED
        self.uv[strip] = PassState(OK, "", cal_id, self.lamp[strip].lamp_hash,
                                   ue[:, _KEPT].tolist(), notes)
        return OK

    # ---- the instrument path (the UI step, 2026-11-18): the helper works
    # M1 / M2 out itself and writes them into the conditions files; the app
    # hears only its events (dual_calibration, dual_pass_result), which carry
    # no spectra. So the record keeps the states, reasons and calibrations of
    # the passes, never data it was not given.
    def helper_calibration(self, cal_id: str, lamp_clocks=None,
                           uv_clocks=None) -> None:
        """A dual calibration the helper reported (event dual_calibration,
        ok). No Te: the helper keeps it."""
        self.calibrations[cal_id] = {"te": [], "lamp_clocks": lamp_clocks,
                                     "uv_clocks": uv_clocks}

    def helper_strip(self, strip: str, ok: bool, reason: str = "",
                     cal_id: str = "", notes: "Iterable[str]" = ()) -> None:
        """A strip the helper read as a dual scan. *ok*: both passes good
        (the conditions files hold its M1 / M2). Not ok: the strip was a
        misread and BOTH passes are read again (provisional for the first
        Beta, docs/design/i1pro2_dual_scan.md section 0 (a)); a strip read
        well before keeps its good passes, as its readings stay in the file."""
        self._strip(strip)
        if ok:
            self.lamp[strip] = PassState(OK, "", cal_id)
            self.uv[strip] = PassState(OK, "", cal_id, "", None,
                                       [n for n in notes if n in NOTES])
            return
        if self.uv[strip].state != OK:
            self.uv[strip] = PassState(FAILED, reason if reason in REASONS
                                       else "uv_pass_missing", cal_id)

    def helper_lamp_only(self, strip: str, reason: str, cal_id: str = "") -> None:
        """A strip read as M0 only, after M1 / M2 ended for the session
        (*reason*, e.g. ``dual_needs_ruler``): its first pass is good, its
        second is due."""
        self._strip(strip)
        self.lamp[strip] = PassState(OK, "", cal_id)
        self.uv[strip] = PassState(MISSING, reason if reason in REASONS else "")

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
        return {"version": VERSION, "strips": list(self.strips), "chosen": self.chosen,
                "preset_done": bool(self.preset_done),
                "calibrations": self.calibrations,
                "lamp": {s: p.to_json() for s, p in self.lamp.items()},
                "uv": {s: p.to_json() for s, p in self.uv.items()},
                "lamp_values": self._lamp_values}

    @classmethod
    def from_json(cls, d: dict) -> "PassRecord":
        if int(d.get("version", 0)) != VERSION:
            raise ValueError("unknown pass record version")
        cals = {k: {"te": list(v["te"]), "lamp_clocks": v.get("lamp_clocks"),
                    "uv_clocks": v.get("uv_clocks")}
                for k, v in dict(d.get("calibrations") or {}).items()
                if isinstance(v, dict) and "te" in v}
        r = cls(list(d["strips"]), cals, chosen=str(d.get("chosen") or "M0").upper(),
                preset_done=bool(d.get("preset_done", False)))
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
