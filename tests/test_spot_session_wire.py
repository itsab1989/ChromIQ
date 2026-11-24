"""Item 43 steps 2-3 (2026-11-24): what Read single patches' spot session
(``--spot-session``) puts on the wire to an i1Pro 2, held against the chart's
patch-by-patch reader, request for request.

BOTH ARE THE REAL HELPER. ``native/chartread_helper/tests/spot_session_wire_
test.c`` links chromiq_chartread.c (compiled with ``CQ_FAKE_USB_TEST``: its
main renamed, its instrument the test's) with the REAL vendored i1Pro 2
driver on a fake USB layer that prints every request. The same presses go to
both readers over the helper's own JSON channel; the traces must be the same.

What is proved here, for the safety review:

* a fresh session (start calibration with the wavelength LED, the dual tile,
  presses, a calibration asked for in the middle, Esc): identical requests;
* an unplugged instrument in the middle of a dual spot and Esc at the
  calibration prompt: identical requests, and the UV switch off at the close
  on every way out (``WIRE STATE uv_en 0 lit 0``);
* every request is one of the recorded forms
  (``tests/data/i1pro2_dual_wire_shape.json``): no EEPROM write, no light
  program, the UV LED only with the recorded flags and 41 lamp clocks;
* a session ArgyllCMS opened with a restored calibration: identical
  requests too (the session's dual start-up branch, the dual strip reader's
  ``cq_dual_startup_calt``, asks for what patch by patch asks for);
* the one designed difference: with -N or -H the session's dual part is off
  before anything is sent, and no UV request is ever sent.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
HELPER_SRC = ROOT / "native" / "chartread_helper"
SHAPE = json.loads((ROOT / "tests" / "data" / "i1pro2_dual_wire_shape.json")
                   .read_text(encoding="utf-8"))
ARGYLL = Path("/Applications/Argyll/bin")
DUAL = ["--dual-scale", "1.1560", "--dual-scale-source", "standard",
        "--dual-white", "instrument", "--dual-chosen", "M1"]

pytestmark = pytest.mark.skipif(sys.platform == "win32",
                                reason="the fake-USB helper test is built on macOS and Linux")


@pytest.fixture(scope="module")
def exe(tmp_path_factory) -> Path:
    cmake = shutil.which("cmake")
    if cmake is None:
        pytest.skip("cmake not available: the helper is not built here")
    build = tmp_path_factory.mktemp("spot_session_wire") / "build"
    subprocess.run([cmake, "-S", str(HELPER_SRC), "-B", str(build),
                    "-DCMAKE_BUILD_TYPE=Release"],
                   check=True, capture_output=True, timeout=600)
    jobs = str(max(2, (os.cpu_count() or 4) // 2))
    r = subprocess.run([cmake, "--build", str(build), "--target",
                        "spot_session_wire_test", "-j", jobs],
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=900)
    assert r.returncode == 0, r.stdout[-3000:] + r.stderr[-3000:]
    return next(p for p in build.rglob("spot_session_wire_test")
                if p.is_file() and os.access(p, os.X_OK))


@pytest.fixture(scope="module")
def chart(tmp_path_factory) -> Path:
    targen = shutil.which("targen") or str(ARGYLL / "targen")
    printtarg = shutil.which("printtarg") or str(ARGYLL / "printtarg")
    if not Path(targen).exists() or not Path(printtarg).exists():
        pytest.skip("Argyll targen/printtarg not available")
    d = tmp_path_factory.mktemp("chart")
    base = d / "chart"
    subprocess.run([targen, "-v0", "-d2", "-G", "-e4", "-B4", "-f30", str(base)],
                   check=True, capture_output=True, cwd=d, timeout=120)
    subprocess.run([printtarg, "-v0", "-ii1", "-pA4", "-r", str(base)],
                   check=True, capture_output=True, cwd=d, timeout=120)
    return base


class Run:
    def __init__(self, events, wire, code):
        self.events, self.wire, self.code = events, wire, code

    def kinds(self, name):
        return [e for e in self.events if e.get("event") == name]

    @property
    def requests(self):
        """The requests alone (the close's state line and the failure mark kept)."""
        return [w for w in self.wire]


def run(exe: Path, cache: Path, mode: str, *, chart: "Path | None" = None,
        presses: int = 3, calibrate_after: "int | None" = None,
        restored: bool = False, fail_at: "int | None" = None,
        quit_at_cal: bool = False, extra=(), dual: bool = True,
        timeout: float = 90.0) -> Run:
    """One life of the helper. *mode* "session" (--spot-session) or "patch"
    (the chart's patch-by-patch reader). The person's part is scripted the
    same way for both: put the instrument on its tile when asked, press
    *presses* times, ask for a calibration before press *calibrate_after*,
    then Esc. A misread is read again (patch by patch answers the retry
    prompt; the session goes on by itself)."""
    cache.mkdir(parents=True, exist_ok=True)
    args = [str(exe), str(cache)]
    if restored:
        args.append("restored")
    args += ["--", "--json"]
    work = cache / f"work-{mode}-{time.monotonic_ns()}"
    work.mkdir()
    if mode == "session":
        args += ["--spot-session", "--spot-conditions"] + (DUAL if dual else []) + list(extra)
    else:
        for suf in (".ti1", ".ti2"):
            shutil.copy(chart.with_suffix(suf), work / ("chart" + suf))
        cdir = work / "cond"
        cdir.mkdir()
        args += (["--condition-dir", str(cdir)] + DUAL if dual else []) + list(extra) \
            + ["-p", str(work / "chart")]
    env = dict(os.environ)
    env.pop("CQ_WIRE_FAIL_AT", None)
    if fail_at:
        env["CQ_WIRE_FAIL_AT"] = str(fail_at)
    p = subprocess.Popen(args, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE, text=True, cwd=work, env=env)
    events: list = []
    wire: list = []
    lock = threading.Lock()

    def _out():
        for ln in p.stdout:
            ln = ln.strip()
            if ln.startswith("{"):
                try:
                    with lock:
                        events.append(json.loads(ln))
                except ValueError:
                    pass

    def _err():
        for ln in p.stderr:
            if ln.startswith("WIRE "):
                wire.append(ln.rstrip()[5:])

    t1 = threading.Thread(target=_out, daemon=True)
    t2 = threading.Thread(target=_err, daemon=True)
    t1.start()
    t2.start()

    def send(**kw):
        try:
            p.stdin.write(json.dumps(kw) + "\n")
            p.stdin.flush()
        except (BrokenPipeError, OSError):
            pass

    seen = 0
    reads = 0
    sent = 0
    cal_sent = False
    want_cal = False
    end = time.monotonic() + timeout
    while p.poll() is None and time.monotonic() < end:
        with lock:
            new = events[seen:]
            seen = len(events)
        for e in new:
            k = e.get("event")
            if k == "cal_required":
                if quit_at_cal and not e.get("requested"):
                    send(cmd="quit")
                else:
                    send(cmd="ok")
            elif k in ("spot_reading", "patch_read"):
                reads += 1
            elif k == "dual_pass_result" and e.get("calibrate"):
                want_cal = True                 # what the app does: calibrate, then again
            elif k == "spot_ready":
                if want_cal:
                    want_cal = False
                    send(cmd="calibrate")
                elif calibrate_after is not None and reads == calibrate_after and not cal_sent:
                    cal_sent = True
                    send(cmd="calibrate")
                elif reads < presses and sent < presses + 4:
                    sent += 1
                    send(cmd="read")
                else:
                    send(cmd="quit")
            elif k == "error" and e.get("kind") == "misread" and mode == "patch":
                send(cmd="retry")
            elif k == "error" and e.get("kind") == "coms" and mode == "patch":
                send(cmd="quit")
            elif k == "strip_interrupted":
                send(cmd="quit")
            elif k == "abort_confirm":
                send(cmd="yes")
        time.sleep(0.02)
    if p.poll() is None:
        p.kill()
        p.wait(10)
        pytest.fail(f"{mode} did not end: {events[-5:]}")
    t1.join(5)
    t2.join(5)
    return Run(events, wire, p.returncode)


def _triggers(wire):
    out = []
    for w in wire:
        t = w.split()
        if t[:2] == ["CTL", "d4"] and len(t) == 3 and len(t[2]) == 28:
            b = bytes.fromhex(t[2])
            out.append(dict(intclocks=int.from_bytes(b[0:4], "big"),
                            lampclocks=int.from_bytes(b[4:8], "big"),
                            nummeas=int.from_bytes(b[8:12], "big"),
                            flags=int.from_bytes(b[12:14], "big")))
    return out


def _uv_free(wire):
    return all((t["flags"] & 0xff00) != 0x0200 for t in _triggers(wire))


# --------------------------------------------------------------- the same wire

def test_a_fresh_session_sends_exactly_what_patch_by_patch_sends(exe, chart, tmp_path):
    """Start calibration (wavelength LED, dark, white), the dual tile, two
    presses, a calibration asked for, a press, Esc: the same requests."""
    s = run(exe, tmp_path / "s", "session", presses=3, calibrate_after=2)
    p = run(exe, tmp_path / "p", "patch", chart=chart, presses=3, calibrate_after=2)
    assert len(s.kinds("spot_reading")) == 3 and len(p.kinds("patch_read")) == 3
    assert s.kinds("dual_calibration") and all(e["ok"] for e in s.kinds("dual_calibration"))
    assert len(s.kinds("dual_calibration")) == 2          # the start and the one asked for
    assert all(e["ok"] for e in s.kinds("dual_pass_result"))
    assert s.wire == p.wire
    assert s.wire[-2:] == ["STATE uv_en 0 lit 0", "CLOSE"]
    # every press is the recorded dual spot: dark + lamp, dark + UV (41), volts
    assert sum(1 for w in s.wire if w == "CTL d8 in4") == 3 + 2   # 3 spots + 2 tiles


def test_b_every_reading_keeps_m0_m1_and_m2(exe, tmp_path):
    s = run(exe, tmp_path / "s", "session", presses=2)
    for e in s.kinds("spot_reading"):
        assert e["main"] == "M0" and e["dual"] is True
        assert set(e["conditions"]) == {"M1", "M2"}
        for c in ("M1", "M2"):
            assert len(e["conditions"][c]["XYZ"]) == 3
            assert len(e["conditions"][c]["spec"]["v"]) == 36
        assert len(e["spec"]["v"]) == 36


def test_c_unplugged_in_the_middle_of_a_dual_spot(exe, chart, tmp_path):
    """The 12th trigger is the second spot's UV-LED one: it fails as an
    unplugged instrument's would. Same requests up to there, nothing after,
    and the UV switch is off at the close."""
    s = run(exe, tmp_path / "s", "session", presses=3, fail_at=12)
    p = run(exe, tmp_path / "p", "patch", chart=chart, presses=3, fail_at=12)
    assert "D4-FAILED" in s.wire
    assert s.wire == p.wire
    assert s.wire[-2:] == ["STATE uv_en 0 lit 0", "CLOSE"]
    assert [e["why"] for e in s.kinds("spot_session_end")] in (["coms"], ["stopped"])


def test_d_esc_at_the_calibration_prompt(exe, chart, tmp_path):
    s = run(exe, tmp_path / "s", "session", quit_at_cal=True)
    p = run(exe, tmp_path / "p", "patch", chart=chart, quit_at_cal=True)
    assert s.wire == p.wire
    assert _uv_free(s.wire)
    assert s.wire[-2:] == ["STATE uv_en 0 lit 0", "CLOSE"]
    assert s.kinds("spot_session_end")[-1]["why"] == "stopped"


def test_e_only_recorded_request_forms(exe, tmp_path):
    """Nothing but triggers (0xD4), the UV volts (0xD8) and the readings'
    bulk reads: no EEPROM read or write (0xC3 / 0xC4), no light program
    (0xD6 / bulk 0x03). Every UV-LED trigger carries the recorded 0x0200 and
    41 lamp clocks; the wavelength LED pair is the recorded one."""
    s = run(exe, tmp_path / "s", "session", presses=3, calibrate_after=1)
    for w in s.wire:
        t = w.split()
        assert t[0] in ("CTL", "RD", "STATE", "CLOSE"), w
        if t[0] == "CTL":
            assert t[1] in ("d4", "d8"), w
        if t[0] == "RD":
            assert t[1] == "82", w
    flags = SHAPE["flags"]
    allowed = {int(flags[k], 16) for k in ("dark", "lamp", "uv_led", "wl_led")}
    for tr in _triggers(s.wire):
        assert tr["flags"] in allowed, tr
        if tr["flags"] == int(flags["uv_led"], 16):
            assert tr["lampclocks"] == 41, tr
        if tr["flags"] == int(flags["wl_led"], 16):
            want = SHAPE["wavelength_led_in_the_calibration"]["requests"][1]
            assert (tr["nummeas"], tr["intclocks"], tr["lampclocks"]) == \
                (want["nummeas"], want["intclocks"], want["lampclocks"])
    # the dual tile is the recorded tail: 10 dark, 5 UV at the white's clocks, volts
    tr = _triggers(s.wire)
    tails = [i for i, t in enumerate(tr) if t["flags"] == 0x0200 and t["nummeas"] == 5]
    assert len(tails) == 2
    for i in tails:
        assert tr[i - 1]["flags"] == 0 and tr[i - 1]["nummeas"] == 10
        assert tr[i - 1]["intclocks"] == tr[i]["intclocks"]


def test_f_a_restored_calibration_changes_nothing(exe, chart, tmp_path):
    """ArgyllCMS opened the instrument with the calibration an earlier
    session saved (i1pro_restore_calibration). Its i1Pro 2 driver still
    wants the start calibration of a session (want_calib / want_dcalib), so
    both readers calibrate at the start, and the spot session's dual branch
    (cq_dual_startup_calt, the dual strip reader's) asks for exactly what
    patch by patch asks for: the same requests. Each reader restores the
    same file (a copy of one seed session's)."""
    seed = tmp_path / "seed"
    run(exe, seed, "session", presses=1)            # saves ArgyllCMS's calibration file
    cs, cp = tmp_path / "cs", tmp_path / "cp"
    shutil.copytree(seed / "ArgyllCMS", cs / "ArgyllCMS")
    shutil.copytree(seed / "ArgyllCMS", cp / "ArgyllCMS")
    s = run(exe, cs, "session", presses=2, restored=True)
    p = run(exe, cp, "patch", chart=chart, presses=2, restored=True)
    assert s.kinds("dual_calibration") and s.kinds("dual_calibration")[0]["ok"]
    assert all(e["ok"] for e in s.kinds("dual_pass_result"))
    assert s.wire == p.wire
    assert s.wire[-2:] == ["STATE uv_en 0 lit 0", "CLOSE"]


@pytest.mark.parametrize("flag", ["-N", "-H"])
def test_g_skip_calibration_or_high_resolution_keep_the_uv_light_off(exe, tmp_path, flag):
    s = run(exe, tmp_path / "s", "session", presses=2, extra=[flag])
    off = s.kinds("conditions")[0]
    assert off["active"] is False
    assert off["why"] == ("dual_nocal" if flag == "-N" else "dual_high_resolution")
    assert _uv_free(s.wire)
    assert "CTL d8 in4" not in s.wire
    assert s.wire[-2:] == ["STATE uv_en 0 lit 0", "CLOSE"]
    assert all(not e["conditions"] for e in s.kinds("spot_reading"))
    assert s.kinds("spot_session_end")[-1]["why"] == "stopped"


def test_h_without_the_dual_scan_a_session_is_a_plain_spot_reader(exe, chart, tmp_path):
    """No --dual-scale: the session and patch by patch without the dual scan
    send the same plain lamp readings, and never the UV light."""
    s = run(exe, tmp_path / "s", "session", presses=2, dual=False)
    p = run(exe, tmp_path / "p", "patch", chart=chart, presses=2, dual=False)
    assert s.wire == p.wire
    assert _uv_free(s.wire)
    assert s.kinds("conditions")[0]["active"] is False
