#!/usr/bin/env python3
"""A SIMULATED i1Pro 2 DUAL-SCAN HELPER, for the Measure tab's tests and the
on-screen proof (UI step, 2026-11-18). Never shipped, never on a real
instrument.

WHY A WRAPPER. The real helper's dual-scan device path (chromiq_dualdev.c)
runs only on a real i1Pro 2; its replay instrument (chromiq_replay.c) has the
step-1 dual path, which writes the real M0 / M1 / M2 files with the real
headers but emits none of the device path's events. This wrapper runs the
REAL helper with its replay instrument (so every file, autosave, resume and
strip event is the helper's own) and adds, on the same JSON channel, exactly
the events the device path emits, with the same names, fields and order:

* ``{"event":"dual_calibration","ok":b,"why":id,"mode":"scan"|"spot",
  "lamp_clocks":n,"uv_clocks":n,"volts":[b,a],"driver":n}`` after every
  calibration, about 2.5 s after ArgyllCMS's calibration returned (the UV
  tile reading's time), and BEFORE ``cal_done`` / a requested calibration's
  ``cal_result`` (chromiq_cal.c:87-90, 204-206);
* ``{"event":"dual_pass","strip":S,"pass":"uv","of":2,"lamp_ok":b}`` after a
  strip's first pass (chromiq_dualdev.c cq_dd_strip), then the engine waits
  for the second pass;
* ``{"event":"dual_pass_result","what":"strip"|"spot","strip":S,"ok":b,
  "why":id,"uv_readings":n,"fewest_per_patch":n,"uv_triggers":n,
  "volts":[b,a],"pairing":"checked"|"pairing_not_checked"|""}`` before the
  strip's ``strip_read`` (or its misread ``error``), as cq_dd_result does;
* ``{"event":"conditions","active":false,"why":"dual_dual_needs_ruler"}``
  when the ruler cannot be used (cq_cond_lose).

Each pass is one ``{"cmd":"swipe"}`` (a person reading it). Extra fields on
the SECOND swipe of a strip: ``"uv_fault": "<reason id>"`` (the pass is
refused: the strip comes back as a misread, both passes again),
``"pairing": "pairing_not_checked"``. On the FIRST swipe: ``"lamp_fault":
"misread"`` (ArgyllCMS did not recognise the first pass: lamp_ok false, the
strip a misread), ``"needs_ruler": true`` (no UV pass can be lined up: M1 /
M2 end for the session, the strip is kept as M0). Patch by patch, one swipe
is one press (lamp + UV); ``"uv_fault": "uv_spot_failed"`` refuses it.
``CHROMIQ_DUAL_SIM_CAL=dark`` makes every calibration ``uv_tile_dark``.

LIMITS (said, not hidden): the replay instrument computes M1 / M2 for every
strip it reads, so after ``needs_ruler`` the files still hold M1 / M2 where
the real helper would hold none; patch by patch the replay has no dual
record, so its conditions end with ``dual_record`` after the first patch.
"""
from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

REAL = Path(os.environ.get("CHROMIQ_DUAL_SIM_REAL") or (
    Path(__file__).resolve().parents[2] / "native" / "chromiq-chartread"))
#: the UV tile reading after ArgyllCMS's calibration (1.5 s lamp-off wait,
#: 10 dark and 5 UV readings): 2 to 3 s on the instrument
TILE_S = float(os.environ.get("CHROMIQ_DUAL_SIM_TILE_S", "2.5"))
#: the person moving the instrument back over the strip
PASS_S = float(os.environ.get("CHROMIQ_DUAL_SIM_PASS_S", "0.4"))


def main(argv: "list[str]") -> int:
    if "--caps" in argv:
        os.execv(str(REAL), [str(REAL), *argv])
    child = subprocess.Popen([str(REAL), *argv], stdin=subprocess.PIPE,
                             stdout=subprocess.PIPE, bufsize=0)
    out_lock = threading.Lock()
    st = {"dual": False, "strip": "", "phase": "lamp", "spot": False,
          "pending": None, "lamp_fault": "", "lamp_reason": "",
          "mode": "spot" if "-p" in argv else "scan"}

    def emit(obj) -> None:
        line = (json.dumps(obj) if isinstance(obj, dict) else obj) + "\n"
        with out_lock:
            sys.stdout.buffer.write(line.encode("utf-8"))
            sys.stdout.buffer.flush()

    def to_child(obj) -> None:
        try:
            child.stdin.write((json.dumps(obj) + "\n").encode("utf-8"))
            child.stdin.flush()
        except (BrokenPipeError, OSError):
            pass

    def result(what, strip, ok, why="", pairing="checked") -> dict:
        return {"event": "dual_pass_result", "what": what, "strip": strip,
                "ok": ok, "why": why, "uv_readings": 96 if ok else 0,
                "fewest_per_patch": 4 if ok else -1,
                "uv_triggers": 1, "volts": [1310, 1302],
                "pairing": pairing if ok else ""}

    def calibration() -> dict:
        dark = os.environ.get("CHROMIQ_DUAL_SIM_CAL") == "dark"
        return {"event": "dual_calibration", "ok": not dark,
                "why": "uv_tile_dark" if dark else "", "mode": st["mode"],
                "lamp_clocks": 139, "uv_clocks": 139, "volts": [1310, 1304],
                "driver": 0}

    def pump_child() -> None:
        for raw in iter(child.stdout.readline, b""):
            text = raw.decode("utf-8", "replace").rstrip("\n")
            ev = None
            if text.startswith("{"):
                try:
                    ev = json.loads(text)
                except ValueError:
                    ev = None
            kind = (ev or {}).get("event")
            if kind == "conditions" and ev.get("active") and ev.get("dual"):
                st["dual"] = True
            if kind == "conditions" and not ev.get("active"):
                st["dual"] = False
            if kind == "strip_ready":
                st["strip"], st["phase"], st["spot"] = (
                    str(ev.get("strip") or ""), "lamp", False)
            if kind == "spot_ready":
                st["spot"] = True
                st["strip"] = str(ev.get("patch") or ev.get("id") or "")
            if st["dual"] and (kind == "cal_done" or (
                    kind == "cal_result" and ev.get("result") == "done")):
                time.sleep(TILE_S)          # the tile under the UV light
                emit(calibration())
            if kind in ("strip_read", "patch_read", "error") and st["pending"]:
                emit(st["pending"])
                st["pending"] = None
            emit(text)

    reader = threading.Thread(target=pump_child, daemon=True)
    reader.start()

    def stop(_sig, _frm):
        try:
            child.terminate()
        except OSError:
            pass
    signal.signal(signal.SIGTERM, stop)

    for raw in iter(sys.stdin.buffer.readline, b""):
        text = raw.decode("utf-8", "replace").strip()
        try:
            cmd = json.loads(text) if text.startswith("{") else None
        except ValueError:
            cmd = None
        if not (cmd and cmd.get("cmd") == "swipe" and st["dual"]):
            if cmd is not None:
                cmd = {k: v for k, v in cmd.items()
                       if k not in ("uv_fault", "lamp_fault", "pairing",
                                    "needs_ruler")}
                to_child(cmd)
            else:
                try:
                    child.stdin.write(raw)
                    child.stdin.flush()
                except (BrokenPipeError, OSError):
                    pass
            continue
        plain = {k: v for k, v in cmd.items()
                 if k in ("cmd", "as", "reversed", "fault", "reason")}
        if st["spot"]:
            if cmd.get("uv_fault"):
                st["pending"] = result("spot", "", False, cmd["uv_fault"])
                to_child({"cmd": "swipe", "fault": "misread",
                          "reason": "Misread"})
            else:
                st["pending"] = result("spot", "", True, pairing="")
                to_child(plain)
            continue
        strip = st["strip"]
        if st["phase"] == "lamp":
            emit({"event": "scan_started"})
            time.sleep(PASS_S)
            if cmd.get("needs_ruler"):
                emit(result("strip", strip, False, "dual_needs_ruler"))
                emit({"event": "conditions", "active": False,
                      "why": "dual_dual_needs_ruler"})
                st["dual"] = False
                to_child(plain)
                continue
            st["lamp_fault"] = str(cmd.get("lamp_fault") or "")
            st["lamp_reason"] = str(cmd.get("reason") or "Misread")
            emit({"event": "dual_pass", "strip": strip, "pass": "uv",
                  "of": 2, "lamp_ok": not st["lamp_fault"]})
            st["phase"] = "uv"
            continue
        # the second pass
        st["phase"] = "lamp"
        emit({"event": "scan_started"})
        time.sleep(PASS_S)
        if st["lamp_fault"]:
            st["pending"] = result("strip", strip, False, "lamp")
            to_child({"cmd": "swipe", "fault": "misread",
                      "reason": st["lamp_reason"]})
        elif cmd.get("uv_fault"):
            st["pending"] = result("strip", strip, False, str(cmd["uv_fault"]))
            to_child({"cmd": "swipe", "fault": "misread", "reason": "Misread"})
        else:
            st["pending"] = result("strip", strip, True,
                                   pairing=str(cmd.get("pairing") or "checked"))
            to_child(plain)
        st["lamp_fault"] = ""
    try:
        child.stdin.close()
    except OSError:
        pass
    code = child.wait()
    reader.join(timeout=5)
    return code


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
