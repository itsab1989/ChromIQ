# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 the ChromIQ authors. Part of ChromIQ (https://github.com/itsab1989/ChromIQ).
"""The instrument side of part C (0.5.0): ChromIQ's own reader, run as a separate program.

Standard library only. The table belongs to this program (its own USB connection to 0971:2004);
the i1Pro 2 (0971:2000) is opened ONLY by the reader, ChromIQ's helper `chromiq-chartread`, which
this package carries in `bin/` (helper build 2026-11-16t, a universal macOS program: Apple silicon
and Intel, macOS 13 or newer, system frameworks only). Two ways of reading, both the helper's:

* SPOT readings: the helper's normal patch-by-patch reading (`--json -v -c 1 -p <chart>`), the same
  code and the same requests to the i1Pro 2 as released ChromIQ 4.3.41's Measure tab reading
  patch by patch (the table-scan mode is compiled in beside it and does nothing unless asked for;
  the helper's tests show its other traffic byte for byte equal to 4.3.41's). Chosen over the
  installed ChromIQ.app's helper so that the volunteer's ChromIQ version does not matter and both
  reading kinds come from one tested file.
* STRIP readings: the helper's table-scan mode (`--json --i1io-table-scan <dir>`), the i1Pro 2's
  part of a row scan exactly as i1Profiler sent it in the recordings (byte audit 44 of 44).

Never used: the lights Beta, the ruler Beta, condition folders, any memory write (the helper's
EEPROM write is compiled out). On a Mac the ArgyllCMS driver inside the helper stops X-Rite's
background service `i1ProDeviceService` when it opens the i1Pro 2 (stock ArgyllCMS behaviour; the
program says so before C1). No reader call is ever made while a table movement is pending, and no
table line is sent while a reader call is pending: both are called from one thread, one at a time.
"""
from __future__ import annotations

import json
import os
import queue
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

HELPER_NAME = "chromiq-chartread"
HELPER_BUILD = "2026-11-16t"
#: The serial-port scan must never open macOS's Bluetooth listener (it can hang in the kernel).
SERIAL_EXCLUDE = "/dev/cu.Bluetooth-Incoming-Port"
#: USB vendors whose instruments ArgyllCMS recognises (any of them besides the i1Pro 2 would
#: change which number "-c 1" means).
OTHER_INSTRUMENT_VENDORS = (0x0765, 0x085C, 0x273F, 0x2457, 0x04D8, 0x1A86)
I1PRO_IDS = (0x0971, 0x2000)
TABLE_IDS = (0x0971, 0x2004)


class ReaderFailed(Exception):
    """The instrument side failed. The TABLE is not touched by this; the stage decides."""


@dataclass
class Reading:
    loc: str
    xyz: "tuple[float, float, float] | None"
    spectrum: "list[float] | None" = None      # filled from the helper's .ti3 at the end
    t: float = 0.0
    event: dict = field(default_factory=dict)


def helper_path(pkg: "Path | None" = None) -> Path:
    pkg = pkg or Path(__file__).resolve().parent
    return pkg / "bin" / HELPER_NAME


def helper_problems(path: Path) -> "list[str]":
    """What stops the bundled reader from starting, in plain words (empty: none). Reads only."""
    out = []
    if sys.platform != "darwin":
        out.append("The reader in this package runs only on a Mac.")
        return out
    if not path.exists():
        out.append(f"The reader {path.name} is missing from the bin folder of this package. "
                   "Please unpack the zip again.")
        return out
    if not os.access(path, os.X_OK):
        out.append(f"The reader is not marked as runnable. In Terminal, in this folder: "
                   f"chmod +x bin/{HELPER_NAME}")
    try:
        r = subprocess.run(["/usr/bin/xattr", "-p", "com.apple.quarantine", str(path)],
                           capture_output=True, text=True, timeout=5)
        if r.returncode == 0:
            out.append("macOS still marks the reader as downloaded from the internet, and then "
                       "refuses to start it. In Terminal, in this folder: xattr -d "
                       f"com.apple.quarantine bin/{HELPER_NAME}  (README, 'Before the first "
                       "run').")
    except (OSError, subprocess.SubprocessError):
        pass
    return out


def usb_ids() -> "list[tuple[int, int]]":
    """(vendor, product) of every USB device, from macOS's own list (ioreg, read only; no device
    is opened and nothing but these two numbers is kept)."""
    import plistlib
    try:
        out = subprocess.run(["/usr/sbin/ioreg", "-a", "-r", "-c", "IOUSBHostDevice", "-l"],
                             capture_output=True, timeout=5).stdout
        roots = plistlib.loads(out) if out.strip() else []
    except Exception:
        return []
    if isinstance(roots, dict):
        roots = [roots]
    found = []

    def walk(n):
        if not isinstance(n, dict):
            return
        v, p = n.get("idVendor"), n.get("idProduct")
        if isinstance(v, int) and isinstance(p, int):
            found.append((v, p))
        for c in n.get("IORegistryEntryChildren", []) or []:
            walk(c)
    for r in roots:
        walk(r)
    return found


def instrument_check(ids=None) -> "str | None":
    """None when exactly one i1Pro 2 (or i1Pro) and no other measuring instrument is connected,
    so that the reader's port 1 is that i1Pro; otherwise the plain reason."""
    ids = usb_ids() if ids is None else ids
    pros = [i for i in ids if i == I1PRO_IDS]
    others = [i for i in ids if i[0] in OTHER_INSTRUMENT_VENDORS
              or (i[0] == 0x0971 and i not in (I1PRO_IDS, TABLE_IDS))]
    if not pros:
        return ("macOS lists no i1Pro 2 (USB 0971:2000). Is it seated in the arm and its cable "
                "plugged in, as when you use it with i1Profiler?")
    if len(pros) > 1:
        return "macOS lists more than one i1Pro. Please connect only the one in the table."
    if others:
        return ("Another measuring instrument is connected besides the i1Pro 2. Please unplug "
                "it for this run, so the reader cannot open the wrong one.")
    return None


def helper_env() -> dict:
    env = dict(os.environ)
    old = env.get("ARGYLL_EXCLUDE_SERIAL_SCAN", "")
    items = [x for x in old.replace(",", ";").split(";") if x]
    if SERIAL_EXCLUDE not in items:
        items.append(SERIAL_EXCLUDE)
    env["ARGYLL_EXCLUDE_SERIAL_SCAN"] = ";".join(items)
    return env


class _Proc:
    """The helper as a subprocess: JSON lines in and out, every event logged."""

    def __init__(self, argv, log, cwd):
        self.log = log
        self.argv = list(argv)
        # names only: a full path would put the person's user name into the log
        self.log("INST", "start: " + " ".join(Path(a).name if (i == 0 or os.sep in a) else a
                                              for i, a in enumerate(argv)))
        self.p = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                  stderr=subprocess.DEVNULL, text=True, bufsize=1,
                                  cwd=str(cwd), env=helper_env())
        self.q: "queue.Queue[dict]" = queue.Queue()
        self.events: "list[dict]" = []
        threading.Thread(target=self._read, daemon=True).start()

    def _read(self):
        try:
            for line in self.p.stdout:
                line = line.strip()
                if not line.startswith("{"):
                    continue
                try:
                    ev = json.loads(line)
                except ValueError:
                    continue
                self.log("INST", line if len(line) < 600 else line[:600] + "...")
                self.events.append(ev)
                self.q.put(ev)
        except Exception:
            pass
        self.q.put({"event": "helper_gone"})

    def alive(self) -> bool:
        return self.p.poll() is None

    def send(self, obj) -> None:
        self.log("INST", "cmd " + json.dumps(obj))
        try:
            self.p.stdin.write(json.dumps(obj) + "\n")
            self.p.stdin.flush()
        except (OSError, ValueError) as exc:
            raise ReaderFailed(f"the reader stopped listening ({type(exc).__name__})") from None

    def wait(self, names, timeout: float) -> "dict | None":
        end = time.monotonic() + timeout
        while True:
            left = end - time.monotonic()
            if left <= 0:
                return None
            try:
                ev = self.q.get(timeout=min(left, 0.05))
            except queue.Empty:
                continue
            if ev.get("event") in names or ev.get("event") in ("helper_gone", "error"):
                return ev

    def poll(self, name) -> "dict | None":
        try:
            while True:
                ev = self.q.get_nowait()
                if ev.get("event") in (name, "helper_gone"):
                    return ev
        except queue.Empty:
            return None

    def stop(self, quit_cmd: dict) -> None:
        try:
            if self.alive():
                self.send(quit_cmd)
                self.p.wait(timeout=5)
        except Exception:
            pass
        if self.alive():
            self.p.kill()
            try:
                self.p.wait(timeout=5)
            except Exception:
                pass


def write_ti2(path: Path, patches) -> None:
    """A chart file for the reader: one patch per (sample_id, loc), in reading order. The values
    are placeholders (the reader only needs the patch list); no colour is assumed."""
    rows = list(patches)
    head = ['CTI2', '', 'DESCRIPTOR "Argyll Calibration Target chart information 2"',
            'ORIGINATOR "chromiq-i1io-session"', 'TARGET_INSTRUMENT "X-Rite i1 Pro 2"',
            'APPROX_WHITE_POINT "50.000000 50.000000 50.000000"', 'COLOR_REP "RGB"',
            f'STEPS_IN_PASS "{len(rows)}"', 'PASSES_IN_STRIPS2 "1"',
            'STRIP_INDEX_PATTERN "A-Z, A-Z"', 'PATCH_INDEX_PATTERN "0-9,@-9,@-9;1-999"',
            'INDEX_ORDER "STRIP_THEN_PATCH"', '', 'NUMBER_OF_FIELDS 8', 'BEGIN_DATA_FORMAT',
            'SAMPLE_ID SAMPLE_LOC RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z ', 'END_DATA_FORMAT', '',
            f'NUMBER_OF_SETS {len(rows)}', 'BEGIN_DATA']
    body = [f'{sid} "{loc}" 50.00000 50.00000 50.00000 50.00000 50.00000 50.00000 '
            for sid, loc in rows]
    path.write_text("\n".join(head + body + ["END_DATA", ""]), encoding="ascii")


def read_ti3_spectra(path: Path) -> "tuple[list[float], dict]":
    """(wavelengths, {loc: (sample_id, xyz, spectrum)}) from a reader's .ti3."""
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    fields, data, wl, mode = [], {}, [], None
    for ln in lines:
        s = ln.strip()
        if s == "BEGIN_DATA_FORMAT":
            mode = "f"
            continue
        if s == "END_DATA_FORMAT":
            mode = None
            continue
        if s == "BEGIN_DATA":
            mode = "d"
            continue
        if s == "END_DATA":
            mode = None
            continue
        if mode == "f":
            fields += s.split()
        elif mode == "d" and s:
            vals = s.replace('"', " ").split()
            if len(vals) < len(fields):
                continue
            row = dict(zip(fields, vals))
            spec_keys = [f for f in fields if f.startswith("SPEC_")]
            wl = [float(k[5:]) for k in spec_keys]
            xyz = tuple(float(row[k]) for k in ("XYZ_X", "XYZ_Y", "XYZ_Z") if k in row)
            data[row.get("SAMPLE_LOC", "")] = (row.get("SAMPLE_ID", ""), xyz,
                                               [float(row[k]) for k in spec_keys])
    return wl, data


class SpotReader:
    """One spot-reading session of the helper over a small chart file (the stage's patches)."""

    def __init__(self, helper: Path, workdir: Path, name: str, patches, log, calibrate: bool,
                 extra_args=()):
        self.workdir = Path(workdir)
        self.workdir.mkdir(parents=True, exist_ok=True)
        self.base = self.workdir / name
        self.patches = list(patches)
        write_ti2(self.base.with_suffix(".ti2"), self.patches)
        args = [str(helper), "--json", *extra_args, "-v", "-c", "1"]
        if not calibrate:
            args.append("-N")
        args += ["-p", self.base.name]
        self.proc = _Proc(args, log, self.workdir)
        self.log = log
        self.readings: "dict[str, Reading]" = {}
        self.ready_loc: "str | None" = None
        self.calibrated = False

    def open(self, place, timeout: float = 45.0) -> None:
        """Until the reader sits on its first patch. *place(event)* is asked at every
        calibration request (returns True when the person has put the instrument where it
        must be); a request that is not answered True ends the reader."""
        end = time.monotonic() + timeout
        while True:
            ev = self.proc.wait(("spot_ready", "cal_required", "cal_result", "instrument"),
                                max(0.0, end - time.monotonic()))
            if ev is None:
                raise ReaderFailed("the reader did not get ready within "
                                   f"{timeout:.0f} s")
            k = ev.get("event")
            if k == "spot_ready":
                self.ready_loc = ev.get("loc")
                return
            if k == "cal_required":
                if not place(ev):
                    raise ReaderFailed("the calibration was not done")
                self.proc.send({"cmd": "ok"})
                end = time.monotonic() + 60.0
            elif k == "cal_result":
                if ev.get("result") != "done":
                    raise ReaderFailed(f"the calibration ended with '{ev.get('result')}'")
                self.calibrated = True
            elif k in ("helper_gone", "error"):
                raise ReaderFailed(f"the reader reported {ev}")

    def read(self, loc: str, timeout: float = 15.0) -> Reading:
        """One spot reading of patch *loc* (the arm stands still on it)."""
        if self.ready_loc != loc:
            self.proc.send({"cmd": "goto", "patch": loc})
            ev = self.proc.wait(("spot_ready",), 5.0)
            if ev is None or ev.get("event") != "spot_ready" or ev.get("loc") != loc:
                raise ReaderFailed(f"the reader did not go to patch {loc} ({ev})")
            self.ready_loc = loc
        t0 = time.monotonic()
        self.proc.send({"cmd": "read"})
        ev = self.proc.wait(("patch_read", "cal_required"), timeout)
        if ev is None:
            raise ReaderFailed(f"no reading of {loc} within {timeout:.0f} s")
        if ev.get("event") != "patch_read" or ev.get("loc") != loc:
            raise ReaderFailed(f"the reader answered {ev} instead of a reading of {loc}")
        xyz = tuple(float(v) for v in ev.get("xyz", []))
        if len(xyz) != 3:
            raise ReaderFailed(f"a reading of {loc} without values")
        r = Reading(loc, xyz, t=time.monotonic() - t0, event=ev)
        self.readings[loc] = r
        nxt = self.proc.wait(("spot_ready",), 5.0)
        self.ready_loc = nxt.get("loc") if nxt and nxt.get("event") == "spot_ready" else None
        return r

    def finish(self, timeout: float = 20.0) -> "Path | None":
        """Save (the helper writes <name>.ti3 with the spectra) and end. Returns the .ti3."""
        try:
            self.proc.send({"cmd": "done"})
            end = time.monotonic() + timeout
            while time.monotonic() < end:
                ev = self.proc.wait(("saved", "unread_confirm"), end - time.monotonic())
                if ev is None or ev.get("event") in ("helper_gone", "error"):
                    break
                if ev.get("event") == "unread_confirm":
                    self.proc.send({"cmd": "yes"})
                    continue
                break
        except ReaderFailed:
            pass
        self.proc.stop({"cmd": "quit"})
        ti3 = self.base.with_suffix(".ti3")
        if ti3.exists():
            try:
                _wl, data = read_ti3_spectra(ti3)
                for loc, (_sid, _xyz, spec) in data.items():
                    if loc in self.readings:
                        self.readings[loc].spectrum = spec
            except Exception:
                pass
            return ti3
        return None

    def close(self) -> None:
        self.proc.stop({"cmd": "quit"})


class ScanReader:
    """The helper in its table-scan mode (one instrument session for all strip stages)."""

    def __init__(self, helper: Path, outdir: Path, log, extra_args=()):
        self.outdir = Path(outdir)
        self.outdir.mkdir(parents=True, exist_ok=True)
        self.proc = _Proc([str(helper), "--json", *extra_args, "--i1io-table-scan",
                           str(self.outdir)], log, self.outdir)
        self.log = log

    def opened(self, timeout=45.0) -> dict:
        ev = self.proc.wait(("tscan_instrument",), timeout)
        if ev is None or ev.get("event") != "tscan_instrument":
            raise ReaderFailed(f"the reader did not open the i1Pro 2 for strip readings ({ev})")
        return ev

    def calibrate(self, place, timeout=120.0) -> None:
        self.proc.send({"cmd": "tscan_calibrate"})
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            ev = self.proc.wait(("tscan_calibrated", "cal_required", "cal_message"),
                                end - time.monotonic())
            if ev is None or ev.get("event") in ("helper_gone", "error"):
                raise ReaderFailed(f"the strip calibration did not finish ({ev})")
            if ev["event"] == "cal_required":
                if not place(ev):
                    raise ReaderFailed("the strip calibration was not done")
                self.proc.send({"cmd": "ok"})
            elif ev["event"] == "tscan_calibrated":
                if not ev.get("ok"):
                    raise ReaderFailed("the strip calibration failed")
                return
        raise ReaderFailed("the strip calibration took too long")

    def alive(self) -> bool:
        return self.proc.alive()

    def lights_off(self) -> dict:
        try:
            self.proc.send({"cmd": "tscan_lights_off"})
        except ReaderFailed as exc:
            return {"event": "failed", "why": str(exc)}
        return self.proc.wait(("tscan_lights_off",), 2.0) or {"event": "timeout"}

    def arm(self, n: int, wait_ms: int = 3000) -> dict:
        try:
            self.proc.send({"cmd": "tscan_arm", "n": n, "wait_ms": wait_ms})
        except ReaderFailed as exc:
            return {"event": "failed", "why": str(exc)}
        return self.proc.wait(("tscan_armed",), wait_ms / 1000.0 + 2.0) or {"event": "timeout"}

    def fire(self, n: int, patches: int, name: str) -> None:
        """Never raises: called on the one path after the scan move."""
        try:
            self.proc.send({"cmd": "tscan_fire", "n": n, "patches": patches, "name": name})
        except Exception as exc:          # noqa: BLE001 - the path must not break
            self.log("INST", f"could not send the fire: {exc!r}")

    def poll(self, name) -> "dict | None":
        return self.proc.poll(name)

    def wait(self, names, timeout) -> "dict | None":
        return self.proc.wait(names, timeout)

    def close(self) -> None:
        self.proc.stop({"cmd": "tscan_quit"})
