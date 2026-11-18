# SPDX-License-Identifier: GPL-3.0-or-later
"""pcap / pcapng reading and USB event extraction, standard library only.

A recording made by the recording tool (github.com/itsab1989/chromiq-i1io-probe) is a pcap or
pcapng file of USB traffic. This module turns it into a list of USB EVENTS, each a dict:

* ``{"k": "ctl", "t", "dev", "vid", "pid", "rt", "req", "val", "idx", "wl", "out", "in"}``: one
  control transfer, its setup, the bytes the host sent (``out``) and those it got (``in``);
* ``{"k": "data", "t", "dev", "vid", "pid", "ep", "data"}``: one completed bulk or interrupt
  transfer on endpoint ``ep`` (bit 0x80 set = device to host).

``t`` is seconds (epoch for real recordings). ``vid`` / ``pid`` are known only where the format
carries them (macOS does; USBPcap and usbmon do not, so a plug-in recognises its device by
behaviour there). The plug-in then gives each event a role.

Formats:

* macOS (link type 266, the 40-byte Darwin USB header): tested on real recordings of the i1iO.
* Windows USBPcap (249) and Linux usbmon (189 / 220): implemented as the recording tool reads
  them, but NOT tested on a real recording of a driven device yet. Say so if you rely on them.

``write_darwin_pcap`` and ``write_usbmon_pcap`` write SYNTHETIC recordings in the same layout,
for tests and examples only. A file written by them proves the reader reads what the writer
wrote; it proves nothing about a real recording.
"""
from __future__ import annotations

import struct
from pathlib import Path

LINKTYPE_DARWIN = 266
LINKTYPE_USBPCAP = 249
LINKTYPE_USBMON = 189          # 48-byte header; 220 is the 64-byte "mmapped" form

XFER_CONTROL, XFER_BULK = 2, 3  # usbmon / USBPcap transfer type numbers


class NotARecording(ValueError):
    """The file is not a pcap or pcapng file, or uses a link type this reader does not know."""


# ---- reading ------------------------------------------------------------------------------

def read_capture(path) -> "tuple[int, list[tuple[float, bytes]]]":
    """(link type, [(time in s, record bytes)]) of a pcap or pcapng file."""
    blob = Path(path).read_bytes()
    if blob[:4] == b"\x0a\x0d\x0d\x0a":
        return _read_pcapng(blob)
    magic = blob[:4]
    if magic in (b"\xd4\xc3\xb2\xa1", b"\x4d\x3c\xb2\xa1"):
        e = "<"
    elif magic in (b"\xa1\xb2\xc3\xd4", b"\xa1\xb2\x3c\x4d"):
        e = ">"
    else:
        raise NotARecording(f"{path}: not a pcap or pcapng file")
    nano = magic in (b"\x4d\x3c\xb2\xa1", b"\xa1\xb2\x3c\x4d")
    if len(blob) < 24:
        raise NotARecording(f"{path}: the pcap header is cut short")
    linktype = struct.unpack(e + "I", blob[20:24])[0]
    off, recs = 24, []
    while off + 16 <= len(blob):
        s, frac, incl, _orig = struct.unpack(e + "IIII", blob[off:off + 16])
        off += 16
        if incl > len(blob) - off:
            break
        recs.append((s + frac / (1e9 if nano else 1e6), blob[off:off + incl]))
        off += incl
    return linktype, recs


def _read_pcapng(blob: bytes):
    off, recs, linktype, e, tsdiv = 0, [], None, "<", 1e6
    while off + 12 <= len(blob):
        btype = struct.unpack(e + "I", blob[off:off + 4])[0]
        if btype == 0x0A0D0D0A:
            e = "<" if blob[off + 8:off + 12] == b"\x4d\x3c\x2b\x1a" else ">"
        blen = struct.unpack(e + "I", blob[off + 4:off + 8])[0]
        if blen < 12 or off + blen > len(blob):
            break
        body = blob[off + 8:off + blen - 4]
        if btype == 1 and linktype is None:
            linktype = struct.unpack(e + "H", body[:2])[0]
            opt = 8
            while opt + 4 <= len(body):
                code, olen = struct.unpack(e + "HH", body[opt:opt + 4])
                if code == 0:
                    break
                if code == 9 and olen >= 1:
                    r = body[opt + 4]
                    tsdiv = float(2 ** (r & 0x7F)) if r & 0x80 else float(10 ** r)
                opt += 4 + olen + ((-olen) % 4)
        elif btype == 6 and len(body) >= 20:
            _i, hi, lo, cap = struct.unpack(e + "IIII", body[:16])
            recs.append((((hi << 32) | lo) / tsdiv, body[20:20 + cap]))
        off += blen
    if linktype is None:
        raise NotARecording("pcapng without an interface block")
    return linktype, recs


def _setup_ok(p: bytes) -> bool:
    return len(p) >= 8 and ((p[0] >> 5) & 3) <= 2 and (p[0] & 0x1F) <= 3


def _ctl(ts, dev, vid, pid, setup):
    rt, req, val, idx, wl = struct.unpack("<BBHHH", setup[:8])
    return {"k": "ctl", "t": ts, "dev": dev, "vid": vid, "pid": pid, "rt": rt, "req": req,
            "val": val, "idx": idx, "wl": wl, "out": b"", "in": b""}


def events_darwin(recs):
    """macOS: a 40-byte header. Byte 2 header length, 3 submit (0) / completion (1), [4:8] data
    length, [0x10:0x14] request id, 29 device address, 30 endpoint, [0x24:0x28] VID / PID. OUT
    and IN data of bulk transfers travel in the completion record; a control submit carries the
    8-byte setup (and an OUT data stage)."""
    out, pend = [], {}
    for ts, d in recs:
        if len(d) < 40:
            continue
        hl = d[2] if 40 <= d[2] <= len(d) else 40
        direction = d[3]
        dlen = struct.unpack("<I", d[4:8])[0]
        seq = struct.unpack("<I", d[0x10:0x14])[0]
        dev, ep = d[29], d[30]
        vid, pid = struct.unpack("<HH", d[0x24:0x28])
        p = d[hl:]
        if direction == 0 and (ep & 0x7F) == 0 and _setup_ok(p):
            wl = struct.unpack("<H", p[6:8])[0]
            if len(p) in (8, 8 + wl):
                ev = _ctl(ts, dev, vid, pid, p)
                ev["out"] = bytes(p[8:])
                pend[seq] = ev
                out.append(ev)
                continue
        if direction == 1 and seq in pend:
            ev = pend.pop(seq)
            body = bytes(p[:dlen] if dlen else p)
            if ev["rt"] & 0x80:
                ev["in"] = body
            elif body:
                ev["out"] = body
            continue
        if direction != 1:
            continue
        data = bytes(p[:dlen] if dlen else p)
        if data:
            out.append({"k": "data", "t": ts, "dev": dev, "vid": vid, "pid": pid, "ep": ep,
                        "data": data})
    return out


def events_usbpcap(recs):
    """Windows USBPcap (NOT tested on a real recording of a driven device)."""
    out, pend = [], {}
    for ts, d in recs:
        if len(d) < 27:
            continue
        hlen, irp, _st, _fn, info, bus, dev, ep, xfer, dlen = struct.unpack_from(
            "<HQIHBHHBBI", d, 0)
        if hlen < 27 or hlen > len(d):
            continue
        data = d[hlen:hlen + dlen]
        done = bool(info & 1)
        if xfer == XFER_CONTROL:
            stage = d[27] if hlen >= 28 else None
            key = (bus, irp)
            if stage == 0 and not done and _setup_ok(data):
                ev = _ctl(ts, (bus << 8) | dev, None, None, data)
                ev["out"] = bytes(data[8:])
                pend[key] = ev
                out.append(ev)
                continue
            ev = pend.get(key)
            if ev is None:
                continue
            if not done and stage == 1 and not ev["rt"] & 0x80:
                ev["out"] += bytes(data)
            elif done:
                if ev["rt"] & 0x80 and data and not ev["in"]:
                    ev["in"] = bytes(data)
                if stage in (2, 3, None):
                    pend.pop(key, None)
            continue
        if data and bool(ep & 0x80) == done:
            out.append({"k": "data", "t": ts, "dev": (bus << 8) | dev, "vid": None,
                        "pid": None, "ep": ep, "data": bytes(data)})
    return out


def events_usbmon(recs, hdr: int):
    """Linux usbmon, 48- or 64-byte header (NOT tested on a real recording of a driven
    device)."""
    out, pend = [], {}
    for ts, d in recs:
        if len(d) < hdr:
            continue
        (uid, typ, xfer, epn, devn, busn, fsetup, _fd, _s, _u, _st, _ln, cap,
         setup) = struct.unpack_from("<QcBBBHccqiiII8s", d, 0)
        data = d[hdr:hdr + cap]
        key = (busn, uid)
        if xfer == XFER_CONTROL:
            if typ == b"S" and fsetup == b"\x00" and _setup_ok(setup):
                ev = _ctl(ts, (busn << 8) | devn, None, None, setup)
                ev["out"] = bytes(data)
                pend[key] = ev
                out.append(ev)
            elif typ == b"C":
                ev = pend.pop(key, None)
                if ev is not None and ev["rt"] & 0x80:
                    ev["in"] = bytes(data)
            continue
        if data and (typ == b"C") == bool(epn & 0x80):
            out.append({"k": "data", "t": ts, "dev": (busn << 8) | devn, "vid": None,
                        "pid": None, "ep": epn, "data": bytes(data)})
    return out


def capture_events(linktype: int, recs) -> list:
    if linktype == LINKTYPE_DARWIN:
        return events_darwin(recs)
    if linktype == LINKTYPE_USBPCAP:
        return events_usbpcap(recs)
    if linktype in (189, 220):
        return events_usbmon(recs, 48 if linktype == 189 else 64)
    raise NotARecording(f"link type {linktype} is not a USB recording this reader knows")


def read_events(path) -> "tuple[float, list]":
    """(time of the first record, events) of a recording file."""
    linktype, recs = read_capture(path)
    if not recs:
        raise NotARecording(f"{path}: the recording holds no records")
    return recs[0][0], capture_events(linktype, recs)


# ---- writing SYNTHETIC recordings (tests and examples only) ----------------------------------

def _pcap(linktype: int, records) -> bytes:
    head = struct.pack("<IHHiIII", 0xA1B2C3D4, 2, 4, 0, 0, 65535, linktype)
    body = b""
    for ts, data in records:
        s = int(ts)
        us = int(round((ts - s) * 1e6))
        body += struct.pack("<IIII", s, us, len(data), len(data)) + data
    return head + body


def darwin_record(direction: int, dev: int, ep: int, data: bytes, *, seq: int = 0,
                  vid: int = 0, pid: int = 0, xfer: int = XFER_BULK) -> bytes:
    """One Darwin USB record in the layout ``events_darwin`` reads (synthetic)."""
    h = bytearray(40)
    h[2] = 40
    h[3] = direction
    h[4:8] = struct.pack("<I", len(data))
    h[0x10:0x14] = struct.pack("<I", seq)
    h[29], h[30], h[31] = dev, ep, xfer
    h[0x24:0x28] = struct.pack("<HH", vid, pid)
    return bytes(h) + data


def write_darwin_pcap(path, records) -> Path:
    """Write ``[(time, darwin_record(...))]`` as a pcap of link type 266 (synthetic)."""
    path = Path(path)
    path.write_bytes(_pcap(LINKTYPE_DARWIN, records))
    return path


def usbmon_record(kind: str, dev: int, ep: int, data: bytes, *, uid: int = 0, bus: int = 1,
                  xfer: int = XFER_BULK, setup: bytes = b"\x00" * 8) -> bytes:
    """One 48-byte-header usbmon record (``kind`` "S" submit or "C" completion), synthetic."""
    flag_setup = b"\x00" if xfer == XFER_CONTROL and kind == "S" else b"-"
    head = struct.pack("<QcBBBHccqiiII8s", uid, kind.encode(), xfer, ep, dev, bus, flag_setup,
                       b"=", 0, 0, 0, len(data), len(data), setup)
    return head + data


def write_usbmon_pcap(path, records) -> Path:
    """Write ``[(time, usbmon_record(...))]`` as a pcap of link type 189 (synthetic)."""
    path = Path(path)
    path.write_bytes(_pcap(LINKTYPE_USBMON, records))
    return path
