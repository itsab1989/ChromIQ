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
  "volts":[b,a],"pairing":"checked"|"pairing_not_checked"|"",
  "calibrate":b}`` before the strip's ``strip_read`` (or its misread
  ``error``), as cq_dd_result does;
* ``{"event":"dual_pass_held","strip":S,"cmd":C}`` when a command that would
  leave the wait for the second pass (goto, forward, back, next_unread,
  file_as, turn) arrives during it: the helper holds it and goes on waiting
  (4.3.49, cq_dd_strip / cq_dd_held_command); the command never reaches the
  replay;
* ``{"event":"conditions","active":false,"why":"dual_dual_needs_ruler",
  "kept":true}`` when the ruler cannot be used (cq_cond_lose; "kept" since
  helper 2026-11-19d: the record of the strips already read is kept).

Each pass is one ``{"cmd":"swipe"}`` (a person reading it). Extra fields on
the SECOND swipe of a strip: ``"uv_fault": "<reason id>"`` (the pass is
refused: the strip comes back as a misread, both passes again),
``"pairing": "pairing_not_checked"``. On the FIRST swipe: ``"lamp_fault":
"misread"`` (ArgyllCMS did not recognise the first pass: lamp_ok false, the
strip a misread), ``"needs_ruler": true`` (no UV pass can be lined up: M1 /
M2 end for the session, the strip is kept as M0). Patch by patch, one swipe
is one press (lamp + UV); ``"uv_fault": "uv_spot_failed"`` refuses it.
``CHROMIQ_DUAL_SIM_CAL=dark`` makes every calibration ``uv_tile_dark``; then,
as the real helper since 4.3.49, a strip is read as one plain pass (no
``dual_pass``): the first after each calibration is refused with
``"calibrate": true`` (a misread), the next one read without a new
calibration is kept as M0 and M1 / M2 end (``dual_uv_tile_dark``).

AFTER M1 / M2 ENDED, AS THE REAL HELPER (review of 2026-11-18, NOTE: the
simulation used to keep writing M1 / M2, which hid M-1 on screen). With
``CHROMIQ_DUAL_SIM_M0_SUFFIX`` set (the driver writes, beside every strip
``A``, a block ``A~M0`` with the same LAMP lines and no UV lines), the
strip that ends M1 / M2 is read from that block, so the REAL helper's own
conditions record ends there (cq_cond_lose "dual_uv_pass_missing": the
reading has no UV half; chromiq_chartread.c), whose event this simulation
swallows: the real helper emits only its one end. Since 4.3.49 (helper
2026-11-19d, cq_cond_keep) the real helper KEEPS the record, exactly as on
the instrument: the strips already read keep M1 / M2, every strip read
afterwards is M0 only, the files become ``<hash>-Mx.partial.ti3``, and a
later Continue Measurement takes them back (``"partial": true``) and reads
with both passes again; reading an M0-only strip again with both passes
completes it.

THE LIGHTS (4.3.52, helper 2026-11-20c). With ``--i1pro2-lights`` and
``--lights-signals`` the real helper's lights run only on a real i1Pro 2 (its
replay says ``"active": false, "why": "instrument"``). The simulation then
says what the real helper says on an i1Pro 2 (chromiq_chartread.c
cq_lights_for_session, cq_lights_second_pass_*, cq_lights_held2): the
``{"event":"lights","active":true,"instrument":"i1pro2",...,"quiet_ms":Q}``
line (Q from ``--lights-quiet-ms``, else 2100); ``{"event":"lights","sent":
"blue"}`` 0.55 s after a strip's first pass (CQ_LIGHTS_BLUE_AFTER_MS) unless
the second swipe came first, which gives ``{"event":"lights","second_pass":
"skipped","why":"early"}``; at the second swipe after a blue, the driver's
hold until the BLUE's own 370 ms after the blue, whatever Q (CQ_LIGHTS_BLUE_
QUIET_MS, helper 2026-11-20b: ``{"event":"lights","held_ms":n,"after":"blue",
"quiet_ms":370}``, between the button and the beep; only at that strip's second
swipe, helper 2026-11-20c: after an Esc the next strip's first swipe is not
held by the blue); and ``"sent": "green2"`` /
``"red2"`` after the strip.

LIMITS (said, not hidden): without that suffix the replay instrument
computes M1 / M2 for every strip it reads, so after ``needs_ruler`` the files
still hold M1 / M2 where the real helper would hold none; patch by patch the
replay has no dual
record, so its conditions end (``record``) after the first patch;
the simulation swallows that event (the device path computes M1 / M2 for a
patch, cq_dd_spot), so the tab behaves as with the real helper while the
files of a patch-by-patch run hold no M1 / M2.
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
#: the replay block of a strip's values without the dual record (see above)
M0_SUFFIX = os.environ.get("CHROMIQ_DUAL_SIM_M0_SUFFIX", "")
#: the person moving the instrument back over the strip
PASS_S = float(os.environ.get("CHROMIQ_DUAL_SIM_PASS_S", "0.4"))
#: the commands the helper holds while the second pass is due (4.3.49)
#: the driver's CQ_LIGHTS_BLUE_QUIET_MS (core/i1pro2_lights_quiet.py BLUE_QUIET_MS)
BLUE_QUIET_MS = 370
#: the helper's CQ_LIGHTS_BLUE_AFTER_MS (4.3.53: --lights-blue-after-ms when the app passes it)
BLUE_AFTER_MS = 550
#: ...and its CQ_LIGHTS_QUIET_MS (core/i1pro2_lights_quiet.py DEFAULT_MS); this script
#: runs on its own, so it holds a copy, pinned by tests/test_lights_quiet_default_is_written_once.py
QUIET_DEFAULT_MS = 2100
HELD = ("goto", "forward", "back", "next_unread", "file_as", "turn")


def main(argv: "list[str]") -> int:
    if "--caps" in argv:
        os.execv(str(REAL), [str(REAL), *argv])
    lights_sim = "--i1pro2-lights" in argv and "--lights-signals" in argv
    quiet_ms = QUIET_DEFAULT_MS
    if "--lights-quiet-ms" in argv:
        try:
            q = int(argv[argv.index("--lights-quiet-ms") + 1])
            if 0 <= q <= 10000:
                quiet_ms = q
        except (ValueError, IndexError):
            pass
    # 4.3.53: the blue's own wait as the app passes it (the helper's rule)
    blue_quiet_ms = BLUE_QUIET_MS
    if "--lights-blue-quiet-ms" in argv:
        try:
            q = int(argv[argv.index("--lights-blue-quiet-ms") + 1])
            if 0 <= q <= 10000:
                blue_quiet_ms = q
        except (ValueError, IndexError):
            pass
    blue_after_ms = BLUE_AFTER_MS
    if "--lights-blue-after-ms" in argv:
        try:
            q = int(argv[argv.index("--lights-blue-after-ms") + 1])
            if 0 <= q <= 5000:
                blue_after_ms = q
        except (ValueError, IndexError):
            pass
    child = subprocess.Popen([str(REAL), *argv], stdin=subprocess.PIPE,
                             stdout=subprocess.PIPE, bufsize=0)
    out_lock = threading.Lock()
    ready = threading.Event()        # the replay's ready-to-scan beep
    st = {"dual": False, "strip": "", "phase": "lamp", "spot": False,
          "ended": False,
          "pending": None, "lamp_fault": "", "lamp_reason": "",
          # with "dark" the session starts as after a dark calibration (the
          # replay reports no start-up calibration of its own)
          "cal_ok": os.environ.get("CHROMIQ_DUAL_SIM_CAL") != "dark",
          "asked": False,
          "mode": "spot" if "-p" in argv else "scan",
          # 4.3.52: the blue before the second pass (see THE LIGHTS above)
          "blue_due": None, "blue_at": None}

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

    def result(what, strip, ok, why="", pairing="checked",
               calibrate=False, pace=None) -> dict:
        ev = {"event": "dual_pass_result", "what": what, "strip": strip,
              "ok": ok, "why": why, "uv_readings": 96 if ok else 0,
              "fewest_per_patch": 4 if ok else -1,
              "uv_triggers": 1, "volts": [1310, 1302],
              "pairing": pairing if ok else "", "calibrate": calibrate}
        if pace is not None:
            ev.update(pace)
            ev["uv_readings"] = pace["uv_readings"]
            ev["fewest_per_patch"] = min(pace["uv_counts"])
        return ev

    def pace_of(cmd, why="") -> dict:
        """After 4.3.54 (helper 2026-11-21b): the pace fields cq_dd_result
        adds after the cut. On the second swipe: "uv_fewest" (the emptiest
        patch's UV readings; default 5, 2 for uv_pass_too_fast), "uv_s",
        "lamp_s" (the passes' seconds), "patches" (default 12)."""
        n = int(cmd.get("patches") or 12)
        few = int(cmd.get("uv_fewest") or (2 if why == "uv_pass_too_fast" else 5))
        uv_s = float(cmd.get("uv_s") or 4.1)
        lamp_s = float(cmd.get("lamp_s") or 3.7)
        rms = 4.896
        counts = [few + 2 + (k % 3) for k in range(n)]
        counts[n // 2] = few
        return {"pace": True, "need": 3, "edge_steps": 0.5, "reading_ms": rms,
                "lamp_readings": int(round(lamp_s * 1000 / rms)), "lamp_s": lamp_s,
                "lamp_travel": 515, "lamp_dir": -1,
                "uv_readings": int(round(uv_s * 1000 / rms)), "uv_s": uv_s,
                "uv_travel": 512, "uv_dir": 1,
                "lamp_off_ms": 2, "uv_dark_ms": 1150, "uv_trigger_ms": 1190,
                "uv_done_ms": int(1190 + uv_s * 1000),
                "lamp_cells": [c + 3 for c in counts], "uv_counts": counts}

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
            if (lights_sim and kind == "lights" and ev.get("active") is False
                    and ev.get("why") == "instrument"):
                emit({"event": "lights", "active": True, "instrument": "i1pro2",
                      "signals": True, "during_reading": "off", "firmware": 634,
                      "quiet_ms": quiet_ms, "blue_quiet_ms": blue_quiet_ms})
                continue
            if kind == "scan_ready":
                ready.set()
            if kind == "conditions" and ev.get("active") and ev.get("dual"):
                st["dual"] = True
            if (kind == "conditions" and not ev.get("active") and st["spot"]
                    and ev.get("why") in ("record", "dual_record")):
                # the replay has no dual record for a patch; the device path
                # works M1 / M2 out for it (cq_dd_spot): the session goes on
                continue
            if kind == "conditions" and not ev.get("active") and st["ended"]:
                continue      # the real helper ends M1 / M2 once, not twice
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
                cal = calibration()
                st["cal_ok"], st["asked"] = cal["ok"], False
                emit(cal)
            verdict = None
            if kind in ("strip_read", "patch_read", "error") and st["pending"]:
                verdict = bool(st["pending"].get("ok"))
                emit(st["pending"])
                st["pending"] = None
            emit(text)
            if lights_sim and verdict is not None and st["dual"]:
                emit({"event": "lights", "sent": "green2" if verdict else "red2"})
        # the real helper has ended: so does the simulation, with its code
        code = child.wait()
        try:
            sys.stdout.buffer.flush()
        except OSError:
            pass
        os._exit(code)

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
        if (cmd and st["dual"] and not st["spot"] and st["phase"] == "uv"
                and cmd.get("cmd") in HELD):
            # the second pass is due: the helper holds the command and goes
            # on waiting (cq_dd_held_command); the replay never sees it
            emit({"event": "dual_pass_held", "strip": st["strip"],
                  "cmd": cmd.get("cmd")})
            continue
        if not (cmd and cmd.get("cmd") == "swipe" and st["dual"]):
            if cmd is not None:
                cmd = {k: v for k, v in cmd.items()
                       if k not in ("uv_fault", "lamp_fault", "pairing",
                                    "needs_ruler", "uv_fewest", "uv_s", "lamp_s",
                                    "patches")}
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
            # patch by patch the replay reads on {"cmd":"read"}; a fault is
            # armed by a swipe first (chromiq_replay.c cq_read_sample)
            if cmd.get("uv_fault"):
                st["pending"] = result("spot", "", False, cmd["uv_fault"])
                to_child({"cmd": "swipe", "fault": "misread",
                          "reason": "Misread"})
            else:
                st["pending"] = result("spot", "", True, pairing="")
            to_child({"cmd": "read"})
            continue
        strip = st["strip"]
        if st["phase"] == "lamp" and not st["cal_ok"]:
            # 4.3.49: a plain lamp pass (no ruler stream, no second pass)
            emit({"event": "scan_started"})
            time.sleep(PASS_S)
            if not st["asked"]:
                st["asked"] = True
                st["pending"] = result("strip", strip, False, "uv_tile_dark",
                                       calibrate=True)
                to_child({"cmd": "swipe", "fault": "misread",
                          "reason": "Misread"})
                continue
            emit(result("strip", strip, False, "uv_tile_dark"))
            emit({"event": "conditions", "active": False,
                  "why": "dual_uv_tile_dark", "kept": True})
            st["dual"] = False
            st["ended"] = True
            if M0_SUFFIX and not plain.get("as"):
                plain = {**plain, "as": strip + M0_SUFFIX}
            to_child(plain)
            continue
        if st["phase"] == "lamp":
            emit({"event": "scan_started"})
            time.sleep(PASS_S)
            if cmd.get("needs_ruler"):
                emit(result("strip", strip, False, "dual_needs_ruler"))
                emit({"event": "conditions", "active": False,
                      "why": "dual_dual_needs_ruler", "kept": True})
                st["dual"] = False
                st["ended"] = True
                if M0_SUFFIX and not plain.get("as"):
                    # the strip is kept as M0 and the real helper's record
                    # ends here: no more condition files from now on
                    plain = {**plain, "as": strip + M0_SUFFIX}
                to_child(plain)
                continue
            st["lamp_fault"] = str(cmd.get("lamp_fault") or "")
            st["lamp_reason"] = str(cmd.get("reason") or "Misread")
            emit({"event": "dual_pass", "strip": strip, "pass": "uv",
                  "of": 2, "lamp_ok": not st["lamp_fault"]})
            st["phase"] = "uv"
            if lights_sim:
                token = object()
                st["blue_due"], st["blue_at"] = token, None
                # 4.3.53 (helper 2026-11-20e): the blue's side follows pass 1's
                # direction: a pass 1 read right to left ("reversed") gets the
                # right blue; the event says the side and the ruler's net count
                rtl = bool(cmd.get("reversed"))

                def _blue(tok=token, rtl=rtl):
                    time.sleep(blue_after_ms / 1000.0)
                    if st["blue_due"] is tok and st["phase"] == "uv":
                        st["blue_due"] = None
                        st["blue_at"] = time.monotonic()
                        emit({"event": "lights",
                              "sent": "blue_right" if rtl else "blue",
                              "side": "right" if rtl else "left",
                              "ruler_net": 400 if rtl else -400,
                              "direction_known": True})
                threading.Thread(target=_blue, daemon=True).start()
            continue
        # the second pass: the instrument's button, its beep, then the slide
        # at a hand's pace (the tab times a strip from the beep)
        st["phase"] = "lamp"
        emit({"event": "scan_started"})  # the button ...
        if lights_sim:
            if st["blue_due"] is not None:
                st["blue_due"] = None
                emit({"event": "lights", "second_pass": "skipped", "why": "early"})
            elif st["blue_at"] is not None:
                # the driver's hold (RULE B): after the blue alone it is the
                # blue's own quiet time, not the user's (fix round, 20b)
                wait = blue_quiet_ms / 1000.0 - (time.monotonic() - st["blue_at"])
                if wait > 0:
                    time.sleep(wait)
                    emit({"event": "lights", "held_ms": int(wait * 1000),
                          "after": "blue", "quiet_ms": blue_quiet_ms})
            st["blue_at"] = None
        emit({"event": "scan_ready"})    # ... the beep, then the slide
        time.sleep(PASS_S)
        if st["lamp_fault"]:
            st["pending"] = result("strip", strip, False, "lamp")
            to_child({"cmd": "swipe", "fault": "misread",
                      "reason": st["lamp_reason"]})
        elif cmd.get("uv_fault"):
            why = str(cmd["uv_fault"])
            # the cut ran for these (the pace is known), not for the others
            pc = pace_of(cmd, why) if why in (
                "uv_pass_too_fast", "uv_pass_misaligned", "uv_pass_wrong_strip",
                "uv_pass_stalled", "uv_pass_short") else None
            st["pending"] = result("strip", strip, False, why, pace=pc)
            to_child({"cmd": "swipe", "fault": "misread", "reason": "Misread"})
        else:
            st["pending"] = result("strip", strip, True,
                                   pairing=str(cmd.get("pairing") or "checked"),
                                   pace=pace_of(cmd))
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
