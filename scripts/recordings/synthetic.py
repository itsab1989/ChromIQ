# SPDX-License-Identifier: GPL-3.0-or-later
"""Make a small INVENTED recording of an i1iO 2 table session, to try the recording tools on.

Nothing in it comes from a real device: the positions, the timings, the memory answer and the
instrument bytes are made up here. The host lines are the app's own public lines
(``workflow/i1io/table/session_table.py::WIRE`` and the builder ``geometry.m0_line``), plus one
line the allow-list must refuse, so that every column of the tools' output shows something.

    python scripts/recordings/synthetic.py OUT.pcap [--format darwin|usbmon]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from recordings import capture  # noqa: E402

TABLE_DEV, PRO_DEV = 5, 6
T0 = 1_700_000_000.0             # an arbitrary epoch second


def _frames(tbl, geo):
    """[(seconds after T0, "host"|"device", line bytes)] of the invented session."""
    w = tbl.WIRE

    def ans(kind, cid, data=""):
        body = kind + cid + data
        return (body + tbl.checksum(body) + "\r").encode("ascii")

    def hex16(v):
        return f"{v & 0xFFFF:04X}"

    move = geo.m0_line(1102, 1600, 300)
    refused = b";m0044c064001f4" + tbl.checksum(";m0044c064001f4").encode() + b"\r"  # speed 500
    s = []
    t = 0.10
    for key, cid, data, took in (("identity", "a1", "0123", 0.02),
                                 ("status", "s0", "00", 0.01),
                                 ("memory_a", "u8", "DEADBEEF" * 8, 0.03),
                                 ("position", "p0", hex16(1102) + hex16(0), 0.01)):
        s.append((t, "host", w[key]))
        s.append((t + 0.004, "device", ans(":!", cid)))
        s.append((t + took, "device", ans(":$", cid, "0" + data)))
        t += 0.25
    s.append((t, "host", move))
    s.append((t + 0.004, "device", ans(":!", "m0")))
    s.append((t + 1.40, "device", ans(":$", "m0", "0")))
    t += 1.6
    s.append((t, "host", w["position"]))
    s.append((t + 0.004, "device", ans(":!", "p0")))
    s.append((t + 0.012, "device", ans(":$", "p0", "0" + hex16(1102) + hex16(1600))))
    t += 0.25
    s.append((t, "host", refused))
    s.append((t + 0.004, "device", ans(":#", "m0", "1")))
    return s


def records(fmt: str = "darwin"):
    from workflow.i1io.table import geometry as geo
    from workflow.i1io.table import session_table as tbl
    vid, pid = tbl.VID, tbl.PID
    out, seq = [], 1
    for dt, who, line in _frames(tbl, geo):
        ts = T0 + dt
        if who == "host":
            ep, data = 0x02, line
        else:
            ep = 0x81
            data = b"".join(b"\x01\x60" + line[i:i + 62] for i in range(0, len(line), 62))
        if fmt == "darwin":
            out.append((ts, capture.darwin_record(1, TABLE_DEV, ep, data, seq=seq, vid=vid,
                                                  pid=pid)))
        else:
            out.append((ts, capture.usbmon_record("C" if ep & 0x80 else "S", TABLE_DEV, ep, data,
                                                  uid=seq)))
        seq += 1
    # an invented instrument: one data transfer, never printed by the tools
    if fmt == "darwin":
        out.append((T0 + 0.9, capture.darwin_record(1, PRO_DEV, 0x82, bytes(268), seq=seq,
                                                    vid=0x0971, pid=0x2000)))
    out.sort(key=lambda r: r[0])
    return out


def write(path, fmt: str = "darwin") -> Path:
    recs = records(fmt)
    if fmt == "darwin":
        return capture.write_darwin_pcap(path, recs)
    return capture.write_usbmon_pcap(path, recs)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("out", help="the .pcap file to write (must not exist yet)")
    ap.add_argument("--format", choices=("darwin", "usbmon"), default="darwin")
    a = ap.parse_args(argv)
    out = Path(a.out)
    if out.exists():
        print(f"{out} exists already; give a new file name", file=sys.stderr)
        return 2
    write(out, a.format)
    print(f"wrote an invented recording: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
