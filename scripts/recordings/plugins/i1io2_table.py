# SPDX-License-Identifier: GPL-3.0-or-later
"""Plug-in for the X-Rite i1iO 2 table (USB 0971:2004) with an i1Pro 2 (0971:2000) in its arm.

Everything device-specific here is taken from the app's own public code in
``workflow/i1io/table/`` and is IMPORTED from there, never copied, so the tools always compare
with the allow-list the app really has:

* the line format (``session_table``'s module docstring): host to table ``;`` + id + hex
  arguments + checksum + CR on bulk endpoint 0x02; the table answers on 0x81 through an FTDI
  chip (two status bytes before every 64-byte packet, ``session_table.strip_ftdi``) with
  ``:!`` (accepted), ``:$`` (done, with a status and data) or ``:#`` (refused);
* the allow-list and the area check: ``lines.classify``;
* the only builders of computed moves: ``geometry.m0_line`` / ``geometry.m2_line``.

What it never prints: the data of a memory answer (``:$u8``), which holds the table's serial
number, and any data the i1Pro 2 sends (its readings and its stored memory). For the instrument
it prints request numbers and byte counts only.
"""
from __future__ import annotations

import re

from . import DevicePlugin, Line, Verdict

_COMPUTED = re.compile(r";(m[02])[0-9a-f]{12}[0-9a-f]{2}")


def _table():
    # imported late, so that --help works without the app's tree on sys.path
    from workflow.i1io.table import geometry as geo
    from workflow.i1io.table import lines as allow
    from workflow.i1io.table import reader
    from workflow.i1io.table import session_table as tbl
    return geo, allow, tbl, reader


class I1io2Table(DevicePlugin):
    name = "i1io2-table"
    description = "X-Rite i1iO 2 table with an i1Pro 2 (allow-list: workflow/i1io/table/lines.py)"

    #: host lines that are polls, hidden by --brief
    ROUTINE = ("s0", "f4", "p0")

    def __init__(self):
        geo, allow, tbl, reader = _table()
        self.geo, self.allow, self.tbl = geo, allow, tbl
        self.table_ids = (tbl.VID, tbl.PID)
        self.instrument_ids = tuple(reader.I1PRO_IDS)

    # ---- roles ---------------------------------------------------------------------------
    def assign_roles(self, events) -> None:
        table, pro = set(), set()
        for ev in events:
            ids = (ev.get("vid"), ev.get("pid"))
            if ids == self.table_ids:
                table.add(ev["dev"])
            elif ids == self.instrument_ids:
                pro.add(ev["dev"])
            elif ev["k"] == "ctl" and ev["rt"] == 0x40 and ev["req"] in (0x03, 0x04):
                table.add(ev["dev"])          # FTDI baud rate / data format: the table's chip
            elif ev["k"] == "data" and ev["ep"] == 0x02 and ev["data"][:1] == b";":
                table.add(ev["dev"])
        for ev in events:
            ev["role"] = ("device" if ev["dev"] in table
                          else "instrument" if ev["dev"] in pro else None)

    # ---- lines ---------------------------------------------------------------------------
    def lines(self, events, t0: float) -> "list[Line]":
        buf = {0x81: bytearray(), 0x02: bytearray()}
        first = {0x81: None, 0x02: None}
        out = []
        for ev in events:
            if ev["k"] != "data" or ev.get("role") != "device" or ev["ep"] not in buf:
                continue
            ep = ev["ep"]
            payload = self.tbl.strip_ftdi(ev["data"]) if ep == 0x81 else ev["data"]
            for b in payload:
                if first[ep] is None:
                    first[ep] = ev["t"]
                if b == 0x0D:
                    text = buf[ep].decode("latin1")
                    line = Line(first[ep] - t0, ev["t"] - t0,
                                "host" if ep == 0x02 else "device", text)
                    line.text = self.redact(line)
                    out.append(line)
                    buf[ep].clear()
                    first[ep] = None
                elif b != 0x0A:
                    buf[ep].append(b)
        return out

    def redact(self, line: Line) -> str:
        t = line.text
        if line.who == "device" and t.startswith(":$u8"):
            return f"{t[:5]}<memory answer, {max(0, len(t) - 7)} characters, not shown>"
        return t

    def command_id(self, line: Line) -> str:
        t = line.text
        return t[1:3] if line.who == "host" else t[2:4]

    def answer_to(self, line: Line) -> "str | None":
        if line.who == "device" and line.text[:2] in (":$", ":#"):
            return line.text[2:4]
        return None

    def is_routine(self, line: Line) -> bool:
        return self.command_id(line) in self.ROUTINE

    # ---- meaning -------------------------------------------------------------------------
    def describe(self, line: Line) -> str:
        t = line.text
        if line.who == "device":
            kind = {":!": "accepted", ":$": "done", ":#": "REFUSED"}.get(t[:2], "")
            if t[:2] == ":$" and len(t) >= 5 and t[4] != "0":
                kind += f", status {t[4]} (not 0)"
            if t[:2] == ":$" and self.command_id(line) in ("p0", "p1") and len(t) == 15:
                x, y = self._s16(t[5:9]), self._s16(t[9:13])
                kind += f", X {x} Y {y} (0.1 mm)"
            return kind
        if _COMPUTED.fullmatch(t) or t.startswith(";m1"):
            if t.startswith(";m1"):
                return "m1, the recorded move to the alignment start"
            cid, x, y, v = self.geo.decode_xyv((t + "\r").encode("ascii"))
            what = "move" if cid == "m0" else "scan move"
            return f"{cid} {what} to X {x} Y {y} (0.1 mm) at speed {v}"
        if t.startswith(";u8") and len(t) == 17:
            return f"memory READ, address 0x{int(t[3:11], 16):X}, {int(t[11:15], 16)} bytes"
        v = self.check(line)
        return v.label if v.allowed else ""

    def describe_instrument(self, ev) -> "str | None":
        if ev["k"] == "ctl":
            n = len(ev["in"]) or len(ev["out"])
            return f"instrument control request 0x{ev['req']:02X}, {n} bytes (not shown)"
        if ev["ep"] & 0x80:
            return f"instrument data on endpoint 0x{ev['ep']:02X}, {len(ev['data'])} bytes (not shown)"
        return None

    # ---- the app's allow-list -------------------------------------------------------------
    def check(self, line: Line) -> Verdict:
        raw = (line.text + "\r").encode("latin1")
        try:
            cid, motion, label = self.allow.classify(raw)
        except self.tbl.ForbiddenLine as exc:
            return Verdict(False, reason=str(exc))
        notes = []
        if label in ("computed m0", "scan move"):
            _c, x, y, _v = self.geo.decode_xyv(raw)
            try:
                self.geo.check_target((x, y), "target", None)
            except Exception as exc:  # noqa: BLE001 - the geometry's own refusal, reported
                notes.append(f"only inside the front zone, after a creep confirmed it: {exc}")
            notes.append("the app also needs a fresh position reading and checks the swept "
                         "rectangle from it (lines.make_gate); a recording alone cannot show that")
        return Verdict(True, label=label, motion=motion, notes=notes)

    def rebuild(self, line: Line) -> "str | None":
        t = line.text
        if not _COMPUTED.fullmatch(t):
            return None
        cid, x, y, v = self.geo.decode_xyv((t + "\r").encode("ascii"))
        build = self.geo.m0_line if cid == "m0" else self.geo.m2_line
        try:
            return build(x, y, v).decode("ascii").rstrip("\r")
        except self.geo.AreaRefused as exc:
            raise ValueError(str(exc)) from exc

    @staticmethod
    def _s16(h: str) -> int:
        v = int(h, 16)
        return v - 0x10000 if v & 0x8000 else v
