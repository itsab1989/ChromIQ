# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 the ChromIQ authors. Part of ChromIQ (https://github.com/itsab1989/ChromIQ).
"""The instrument side of part C (0.5.0): ChromIQ's own reader, run as a separate program.

Standard library only. The table belongs to this program (its own USB connection to 0971:2004);
the i1Pro 2 (0971:2000) is opened ONLY by the reader, ChromIQ's helper `chromiq-chartread`.
In the app (2026-11-17) that is ChromIQ's own `native/chromiq-chartread` (build 2026-11-17b: 2026-11-17a,
which carries the table-scan mode of the tester's bundled 2026-11-16t, plus the button wait of round B;
`helper_path`); the tester
program carried its own copy in `bin/`. Two ways of reading, both the helper's:

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
HELPER_BUILD = "2026-11-20a"      # ChromIQ's helper: the table scan (2026-11-17a) + the button wait (17b)
#                                    + the i1Pro 2 dual-scan conditions (18a, nothing for the table)
#                                    + the dual scan's resume rule (18b, nothing for the table)
#                                    + the dual scan's device side (18c, nothing for the table yet)
#                                    + the dual scan's safety fixes (18d, nothing for the table)
#                                    + the dual scan on the table (18e: --i1io-table-dual,
#                                      --dual-table; nothing without them)
#                                    + its fix rounds (19a: the lamp's dark, one fire per yes;
#                                      19b: a calibration clears the armed pass)
#                                    + the hand dual scan's gaps (19c, 4.3.49: nothing for the table)
#                                    + the kept conditions record (19d, 4.3.49: nothing for the table)
#                                    + the lights' quiet time and the dual scan's blue (20a, 4.3.52:
#                                      nothing for the table, which refuses the lights Beta)
#: the build token of the helper's button wait (--i1io-press-wait, round B). A helper without it
#: (2026-11-17a and older) is simply not asked: the panel's Aimed button always works.
PRESS_WAIT_TOKEN = "+i1io-press-wait"
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
    """ChromIQ's own helper, ``native/chromiq-chartread`` (core.resource_path: the source tree,
    or the app bundle). *pkg* names a tester-style folder holding ``bin/`` instead (tests)."""
    from core.resource_path import argyll_binary, argyll_tool_path, resource_path
    if pkg is not None:
        return argyll_tool_path(pkg / "bin", HELPER_NAME)
    return resource_path("native/" + argyll_binary(HELPER_NAME))


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
                           capture_output=True, text=True, encoding="utf-8", timeout=5)
        if r.returncode == 0:
            out.append("macOS still marks the reader as downloaded from the internet, and then "
                       "refuses to start it. In Terminal, in this folder: xattr -d "
                       f"com.apple.quarantine bin/{HELPER_NAME}  (README, 'Before the first "
                       "run').")
    except (OSError, subprocess.SubprocessError):
        pass
    return out


def _usb_tree() -> "list | None":
    """macOS's own list of USB devices (``ioreg``, read only: no device is opened). None when
    it cannot be read."""
    import plistlib
    try:
        out = subprocess.run(["/usr/sbin/ioreg", "-a", "-r", "-c", "IOUSBHostDevice", "-l"],
                             capture_output=True, timeout=5).stdout
        roots = plistlib.loads(out) if out.strip() else []
    except Exception:
        return None
    if isinstance(roots, dict):
        roots = [roots]
    return roots if isinstance(roots, list) else None


def _is_interface(node: dict) -> bool:
    """An interface entry of a device (IOUSBHostInterface): macOS gives it the device's own
    idVendor and idProduct (drivers match on them), so it must never be counted as a device.
    0.5.0 counted it, and saw two i1Pros where one i1Pro 2 was connected."""
    return "bInterfaceNumber" in node or "Interface" in str(node.get("IOObjectClass", ""))


#: the IORegistry classes of a USB DEVICE (ioreg's -c IOUSBHostDevice lists these and their
#: subclasses); interfaces, drivers and user clients below a device are not devices, even when
#: they carry the device's idVendor and idProduct (a driver's matching personality can)
DEVICE_CLASSES = ("IOUSBHostDevice", "IOUSBDevice")


def _is_device(node: dict) -> bool:
    cls = node.get("IOObjectClass")
    if isinstance(cls, str):
        return cls in DEVICE_CLASSES or cls.endswith("USBHostDevice")
    return not _is_interface(node)


def usb_devices(roots=None) -> "list[dict] | None":
    """Every USB DEVICE once, from macOS's list: {"vid", "pid", "place" (macOS's locationID,
    the port path; not a serial number), "hub" (a hub's device class), "interfaces" (how many
    interface entries of that device were seen and NOT counted)}. Only these numbers are kept;
    names and serial numbers are never read. A device that macOS lists twice (same place) is
    counted once. None when macOS's list cannot be read."""
    roots = _usb_tree() if roots is None else roots
    if roots is None:
        return None
    devices: "dict[object, dict]" = {}
    interfaces: "dict[object, int]" = {}
    order = []

    def key_of(n, fallback):
        loc = n.get("locationID")
        if isinstance(loc, int):
            return ("place", loc)
        rid = n.get("IORegistryEntryID")
        return ("id", rid) if isinstance(rid, int) else ("node", fallback)

    def walk(n, parent_key):
        if not isinstance(n, dict):
            return
        v, p = n.get("idVendor"), n.get("idProduct")
        here = parent_key
        if isinstance(v, int) and isinstance(p, int):
            if _is_interface(n):
                k = key_of(n, parent_key) if isinstance(n.get("locationID"), int) else parent_key
                interfaces[k] = interfaces.get(k, 0) + 1
            elif _is_device(n):
                here = key_of(n, len(order))
                if here not in devices:
                    loc = n.get("locationID")
                    devices[here] = {"vid": v, "pid": p,
                                     "place": loc if isinstance(loc, int) else None,
                                     "hub": n.get("bDeviceClass") == 9}
                    order.append(here)
        for c in n.get("IORegistryEntryChildren", []) or []:
            walk(c, here)
    for r in roots:
        walk(r, None)
    out = []
    for k in order:
        d = dict(devices[k])
        d["interfaces"] = interfaces.get(k, 0)
        out.append(d)
    return out


def usb_ids() -> "list[tuple[int, int]]":
    """(vendor, product) of every USB device, each device once (interface entries are not
    devices). [] when macOS's list cannot be read."""
    return [(d["vid"], d["pid"]) for d in (usb_devices() or [])]


def _place(d) -> str:
    return f"{d['place']:08x}" if isinstance(d.get("place"), int) else "unknown"


def _is_other_instrument(d) -> bool:
    if d.get("hub"):
        return False
    ids = (d["vid"], d["pid"])
    return d["vid"] in OTHER_INSTRUMENT_VENDORS or (d["vid"] == 0x0971
                                                    and ids not in (I1PRO_IDS, TABLE_IDS))


def seen_text(devices) -> str:
    """What the check saw, for the log (numbers only: USB ids and macOS's USB place; never a
    name or a serial number)."""
    if devices is None:
        return "macOS's list of USB devices could not be read"
    parts = []
    for d in devices:
        ids = (d["vid"], d["pid"])
        if ids == TABLE_IDS:
            what = "the table"
        elif ids == I1PRO_IDS:
            what = "an i1Pro (counted)"
        elif _is_other_instrument(d):
            what = "a measuring instrument (counted)"
        else:
            continue
        extra = f", {d['interfaces']} interface entr{'y' if d['interfaces'] == 1 else 'ies'} " \
                "of it not counted" if d["interfaces"] else ""
        parts.append(f"{d['vid']:04x}:{d['pid']:04x} {what} at USB place {_place(d)}{extra}")
    rest = len(devices) - len(parts)
    parts.append(f"{rest} other USB device{'' if rest == 1 else 's'} (hubs, keyboards and the "
                 "like; not counted)")
    return "; ".join(parts)


AFTER_END = ("Please do this only after this program has ended (type end at the next question): "
             "never unplug anything while it runs, and never the table or the i1Pro 2 in its arm.")


def instrument_check(ids=None, devices=None, log=None) -> "str | None":
    """None when exactly one i1Pro 2 (or i1Pro) DEVICE and no other measuring instrument is
    connected, so that the reader's port 1 is that i1Pro; otherwise the plain reason, which says
    what macOS listed. *ids* (a list of (vendor, product), one per device) is for tests; *log*
    gets exactly what was counted."""
    if devices is None:
        devices = ([{"vid": v, "pid": p, "place": None, "hub": False, "interfaces": 0}
                    for v, p in ids] if ids is not None else usb_devices())
    if log is not None:
        log("INST", "instrument check: macOS lists " + seen_text(devices))
    if devices is None:
        return ("The program could not read macOS's list of USB devices, so it did not start "
                "the reader. Nothing was sent to the instrument.")
    pros = [d for d in devices if (d["vid"], d["pid"]) == I1PRO_IDS]
    others = [d for d in devices if _is_other_instrument(d)]
    if not pros:
        return ("macOS lists no i1Pro 2 (USB 0971:2000). Is it seated in the arm and its cable "
                "plugged in, as when you use it with i1Profiler? The reader was not started.")
    if len(pros) > 1:
        return (f"macOS lists {len(pros)} separate i1Pro devices (USB 0971:2000, at USB places "
                + ", ".join(_place(d) for d in pros) + "). The reader needs exactly one, the "
                "i1Pro 2 in the table's arm, so it was not started. If another i1Pro is plugged "
                "into this Mac, please unplug that other one. " + AFTER_END)
    if others:
        return ("Besides the i1Pro 2, macOS lists another measuring instrument (USB "
                + ", ".join(f"{d['vid']:04x}:{d['pid']:04x}" for d in others) + "), so the "
                "reader was not started: it could open the wrong one. Please unplug that other "
                "instrument for this run. " + AFTER_END)
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
                                  stderr=subprocess.DEVNULL, text=True, encoding="utf-8", bufsize=1,
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
                shown = line.replace(str(Path.home()), "~")      # never the user's name
                self.log("INST", shown if len(shown) < 600 else shown[:600] + "...")
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


#: 4.3.46 (fix round 2 of the first real-table run): the helper's events after which it waits
#: for ONE key at a prompt of its own, outside the patch menu (chromiq_chartread.c's spot loop,
#: chromiq_cal.c): a calibration it asks for (any key but Esc STARTS the calibration, on
#: whatever lies under the instrument), a failed calibration (any key but Esc tries again), a
#: failed reading ("Hit Esc or 'q' to give up, any other key to retry"), and the stop at a patch
#: (Esc there gives "strip_interrupted" and asks once more).
KEY_PROMPTS = ("cal_required", "error", "strip_interrupted")
#: 4.3.47 (release review NOTE of 4.3.46): only THESE "error" kinds leave the helper waiting for
#: a key, checked against its C sources: "misread" and "coms" (chromiq_chartread.c's spot loop,
#: "Hit Esc or 'q' to give up, any other key to retry", cq_prompt_char), "cal_failed"
#: (chromiq_cal.c, "Wait for retry (any command) or quit", cq_wait_char) and "read_error"
#: (ierror(), cq_wait_char; not reached in spot mode, kept for safety). Every other kind is said
#: and the helper carries on without a key: "autosave_rename" (the save after a reading could
#: not replace the .ti3; Windows, a virus scanner holding the file), "patch_not_found" (a goto
#: it could not follow). Before, any "error" counted as a prompt, so a failed autosave that was
#: the newest event when a row ended made finish() send Esc instead of "done" and skipped the
#: helper's final save.
KEY_PROMPT_ERROR_KINDS = ("misread", "coms", "cal_failed", "read_error")
#: the events after which the helper is back at its patch menu (or has ended)
AT_THE_MENU = ("spot_ready", "cal_done", "cal_result", "patch_read", "saved", "unread_confirm",
               "done")
#: the error kinds of a failed READING, whose prompt takes "retry" (any other key) back to the
#: same patch (chromiq_chartread.c: cq_emit_error("misread"), cq_emit_coms_error)
RETRY_PROMPT_KINDS = ("misread", "coms")


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
            ev = self.proc.wait(("spot_ready", "cal_required", "cal_done", "cal_result",
                                 "instrument"),
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
            elif k == "cal_done":
                # 4.3.46 (the first run of the drive on a real table, 18 Nov 2026): the
                # calibration the instrument asks for when a session starts ends with the
                # helper's "cal_done" (native/chartread_helper/chromiq_cal.c). This reader
                # waited only for "cal_result", which the helper sends for a calibration the
                # PERSON asked for, so on a real i1Pro 2 no white ever counted and every table
                # measurement ended at the calibration (the job's "not confirmed" refusal). The
                # simulated reader sent "cal_result", which is why no test saw it.
                self.calibrated = True
            elif k == "cal_result":
                if ev.get("result") != "done":
                    raise ReaderFailed(f"the calibration ended with '{ev.get('result')}'")
                self.calibrated = True
            elif k == "error" and ev.get("kind") == "cal_failed":
                # the helper's own word for a calibration that failed at the start of a session
                raise ReaderFailed("the calibration ended with 'failed'")
            elif k in ("helper_gone", "error"):
                raise ReaderFailed(f"the reader reported {ev}")

    def _prompt(self) -> "dict | None":
        """The helper's own prompt it waits at for one key (the newest event that says where
        the helper is, when it is one of :data:`KEY_PROMPTS`), else None (at its patch menu,
        ended, or nothing said yet)."""
        for ev in reversed(list(getattr(self.proc, "events", []) or [])):
            k = ev.get("event")
            if k in KEY_PROMPTS:
                if k == "error" and ev.get("kind") == "patch_not_found":
                    return None            # a goto it could not follow: back at the menu
                if k == "error" and ev.get("kind") not in KEY_PROMPT_ERROR_KINDS:
                    continue               # said, no key waited for: where it was before
                return ev
            if k in AT_THE_MENU:
                return None
        return None

    def _quit(self, step: float = 3.0) -> None:
        """End the helper through its own way out, so that it closes the instrument itself
        (``it->del``) and ends: Esc ("quit"), and Esc once more whenever it asks again. At a
        patch the first Esc only stops the reading ("strip_interrupted", then "Hit Esc or 'q'
        to give up", chromiq_chartread.c's spot loop); at a calibration request, a failed
        calibration, a failed reading or the unread-patches question one Esc ends it. Never
        "done" or any other key at those prompts: there they mean "carry on". Every reading
        the helper accepted is already in its .ti3 (it saves after every reading), so nothing
        is lost by this ending. Before 4.3.46 close() sent one Esc and, at a patch, waited
        5 s and killed the helper with the i1Pro 2 open."""
        for _ in range(4):
            if not self.proc.alive():
                return
            try:
                self.proc.send({"cmd": "quit"})
            except ReaderFailed:
                return
            if not self.proc.alive():
                return
            ev = self.proc.wait(("strip_interrupted", "unread_confirm", "abort_confirm",
                                 "done"), step)
            if ev is None or ev.get("event") in ("helper_gone", "done"):
                return
            if ev.get("event") == "abort_confirm":
                try:
                    self.proc.send({"cmd": "yes"})
                except ReaderFailed:
                    pass
                self.proc.wait(("done",), step)
                return
            # strip_interrupted / unread_confirm / an error prompt: it asks once more

    def _wait_gone(self, timeout: float = 5.0) -> None:
        end = time.monotonic() + timeout
        while self.proc.alive() and time.monotonic() < end:
            time.sleep(0.01)

    def read(self, loc: str, timeout: float = 15.0) -> Reading:
        """One spot reading of patch *loc* (the arm stands still on it)."""
        prompt = self._prompt()
        if (prompt is not None and prompt.get("event") == "error"
                and prompt.get("kind") in RETRY_PROMPT_KINDS):
            # 4.3.46: after a failed reading the helper waits at "Hit Esc or 'q' to give up,
            # any other key to retry" and DROPS a goto there (cq_wait_char takes it and waits
            # on), so the job's second try of a patch ended "did not go to patch" on the real
            # helper every time. "retry" is that other key: it offers the same patch again
            # (spot_ready) and reads nothing until "read".
            self.proc.send({"cmd": "retry"})
            ev = self.proc.wait(("spot_ready",), 5.0)
            if ev is None or ev.get("event") != "spot_ready":
                raise ReaderFailed(f"the reader did not go to patch {loc} ({ev})")
            self.ready_loc = ev.get("loc")
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
        if self._prompt() is not None:
            # 4.3.46: the helper waits at a prompt of its own (a calibration it asks for in the
            # middle of a row, a failed reading or calibration), where "done" is "any other
            # key": at a calibration request the i1Pro 2 then CALIBRATED on the patch under it
            # (measured with the real helper: cal_done after "done", then 25 s and a kill).
            # Its own way out is Esc; the .ti3 it saved after its last reading is the row's.
            self._quit()
        else:
            try:
                self.proc.send({"cmd": "done"})
                end = time.monotonic() + timeout
                while time.monotonic() < end:
                    ev = self.proc.wait(("saved", "unread_confirm", "done"),
                                        end - time.monotonic())
                    if ev is None or ev.get("event") in ("helper_gone", "error"):
                        break
                    if ev.get("event") == "unread_confirm":
                        self.proc.send({"cmd": "yes"})
                        continue
                    break
            except ReaderFailed:
                pass
            self._wait_gone(2.0)
            self._quit()           # only when it is still there: its own way out first
        self._wait_gone()
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
        """End the reader without saving anything more (its own way out, :meth:`_quit`; what
        it saved after each reading stays in its .ti3). A helper that does not end within
        5 s is still ended by force, as before."""
        self._quit()
        self._wait_gone()
        self.proc.stop({"cmd": "quit"})


def helper_build(path: "Path | None" = None, timeout: float = 5.0) -> str:
    """The helper's build string, from ``--caps`` (opens nothing: it prints one line and ends).
    Empty when it cannot be asked."""
    try:
        # the app's own question to its helper (workflow.chartread_engine: --caps, cached per
        # binary, opens nothing)
        from workflow.chartread_engine import helper_build as engine_build
        return str(engine_build(Path(path) if path is not None else helper_path()) or "")
    except Exception:          # noqa: BLE001 - not offered, nothing breaks
        return ""


def press_wait_supported(build: "str | None" = None) -> bool:
    """True when the helper can wait for the instrument's button (round B). An older helper
    (no token in its build string) is never started for it."""
    b = helper_build() if build is None else build
    return (PRESS_WAIT_TOKEN + "+") in (b + "+")


class PressWaiter:
    """The helper in its button-wait mode (``--json --i1io-press-wait -c 1``, round B): it opens
    the i1Pro 2 as every reading does and reports ONE press of its button per arm. It takes no
    reading, sets no measuring mode and never opens the table. Never started without the
    job's own instrument check (exactly one i1Pro 2, nothing else)."""

    def __init__(self, helper: Path, workdir: Path, log, extra_args=()):
        self.workdir = Path(workdir)
        self.workdir.mkdir(parents=True, exist_ok=True)
        self.proc = _Proc([str(helper), "--json", *extra_args, "--i1io-press-wait", "-c", "1"],
                          log, self.workdir)

    def alive(self) -> bool:
        return self.proc.alive()

    def arm(self, token: str, wait_ms: int = 600000, min_ms: int = 600) -> bool:
        try:
            self.proc.send({"cmd": "press_arm", "id": token, "wait_ms": str(int(wait_ms)),
                            "min_ms": str(int(min_ms))})
            return True
        except ReaderFailed:
            return False

    def disarm(self) -> None:
        try:
            if self.alive():
                self.proc.send({"cmd": "press_disarm"})
        except ReaderFailed:
            pass

    def events(self) -> "list[dict]":
        return list(self.proc.events)

    def close(self) -> None:
        self.proc.stop({"cmd": "press_quit"})


class ScanReader:
    """The helper in its table-scan mode (one instrument session for all strip stages)."""

    def __init__(self, helper: Path, outdir: Path, log, extra_args=()):
        self.outdir = Path(outdir)
        self.outdir.mkdir(parents=True, exist_ok=True)
        self.proc = _Proc([str(helper), "--json", *extra_args, "--i1io-table-scan",
                           str(self.outdir)], log, self.outdir)
        self.log = log
        #: the dual row (2026-11-18): the helper's tdual_calibration event of the last
        #: calibration (None: none, or not a dual session)
        self.dual_calibration: "dict | None" = None
        #: a "tscan_calibrate" was sent and its "tscan_calibrated" has not come: the helper is
        #: inside its calibration, where it waits for keys, not for tscan_* lines
        self._in_calibration = False

    def opened(self, timeout=45.0) -> dict:
        ev = self.proc.wait(("tscan_instrument",), timeout)
        if ev is None or ev.get("event") != "tscan_instrument":
            raise ReaderFailed(f"the reader did not open the i1Pro 2 for strip readings ({ev})")
        return ev

    def calibrate(self, place, timeout=120.0) -> None:
        self._in_calibration = True
        self.proc.send({"cmd": "tscan_calibrate"})
        self.dual_calibration = None
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            ev = self.proc.wait(("tscan_calibrated", "cal_required", "cal_message",
                                 "tdual_calibration"), end - time.monotonic())
            if ev is None or ev.get("event") in ("helper_gone", "error"):
                raise ReaderFailed(f"the strip calibration did not finish ({ev})")
            if ev["event"] == "tdual_calibration":
                self.dual_calibration = ev     # only a dual session's helper says this
                continue
            if ev["event"] == "cal_required":
                if not place(ev):
                    raise ReaderFailed("the strip calibration was not done")
                self.proc.send({"cmd": "ok"})
            elif ev["event"] == "tscan_calibrated":
                self._in_calibration = False
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

    def arm(self, n: int, wait_ms: int = 3000, pass_: "str | None" = None) -> dict:
        """*pass_* ("lamp" / "uv"): a dual row's pass (only a helper started with
        --i1io-table-dual knows it, and then it fires exactly the pass it was armed for)."""
        cmd = {"cmd": "tscan_arm", "n": n, "wait_ms": wait_ms}
        if pass_ is not None:
            cmd["pass"] = pass_
        try:
            self.proc.send(cmd)
        except ReaderFailed as exc:
            return {"event": "failed", "why": str(exc)}
        return self.proc.wait(("tscan_armed",), wait_ms / 1000.0 + 2.0) or {"event": "timeout"}

    # ---- the dual row (2026-11-18; only with --i1io-table-dual) ---------------------------
    def dual_state(self, timeout: float = 5.0) -> dict:
        """The helper's tdual_state event (the dual session on; the dual tile of this white
        kept or not), which comes right after tscan_instrument."""
        return self.proc.wait(("tdual_state",), timeout) or {"event": "timeout"}

    def dual_compute(self, name: str, scale: float, timeout: float = 10.0) -> dict:
        """M1 / M2 of a dual row from <name>.dual_in.txt (the app's cut): the helper checks
        that the UV pass belongs to the lamp pass and writes <name>.dual_out.txt."""
        try:
            self.proc.send({"cmd": "tscan_dual_compute", "name": name,
                            "scale": f"{float(scale):.4f}"})
        except ReaderFailed as exc:
            return {"event": "failed", "why": str(exc)}
        return self.proc.wait(("tscan_dual_computed",), timeout) or {"event": "timeout"}

    def fire(self, n: int, patches: int, name: str) -> bool:
        """Never raises: called on the one path after the scan move. False when the trigger
        could not even be handed to the reader (it had stopped): then nothing can start the
        waiting move, and the caller says SWITCH THE TABLE OFF at once."""
        try:
            if not self.alive():
                self.log("INST", "could not send the fire: the reader has stopped")
                return False
            self.proc.send({"cmd": "tscan_fire", "n": n, "patches": patches, "name": name})
            return True
        except Exception as exc:          # noqa: BLE001 - the path must not break
            self.log("INST", f"could not send the fire: {exc!r}")
            return False

    def poll(self, name) -> "dict | None":
        return self.proc.poll(name)

    def wait(self, names, timeout) -> "dict | None":
        return self.proc.wait(names, timeout)

    def close(self) -> None:
        """End the table-scan session: "tscan_quit" lets the instrument go (it->del) and ends
        the helper. 4.3.46: while the helper is still inside its calibration (a request not
        answered, a failed white: chromiq_cal.c waits there for ONE key, cq_wait_char), a
        tscan_* line only goes to the table-scan queue (chromiq_json.c), which it reads after
        the calibration has returned, so tscan_quit alone waited 5 s and the helper was killed
        with the i1Pro 2 open. Esc ("quit", the key) ends the calibration first
        (tscan_calibrated ok:false, nothing measured), then tscan_quit is taken."""
        if self._in_calibration:
            self._in_calibration = False
            try:
                if self.proc.alive():
                    self.proc.send({"cmd": "quit"})
            except ReaderFailed:
                pass
        self.proc.stop({"cmd": "tscan_quit"})
