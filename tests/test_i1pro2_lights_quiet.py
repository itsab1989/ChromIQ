"""4.3.37: the i1Pro 2's lights in i1Profiler's hand-held order, on the wire.

A tester's log (his own i1Pro 2, Windows, ChromIQ 4.3.34 to 4.3.36): ANY light
write that ended 10-25 ms before a measurement trigger lost the strip's first
reading about 2 times in 3, and none was lost without one (0 of 79). So the
REAL vendored driver now (native/instlib/i1pro_imp.c, CHROMIQ PATCH):

* RULE A: writes nothing between the button press and the reading's data:
  a reading's triggers send nothing, and a result is never written once the
  button is pressed again;
* RULE B: lets no trigger go out earlier than CQ_LIGHTS_QUIET_MS (2100) after
  the END of the last light write, by waiting;
* sends only the six recorded sequences, in recorded contexts.

Proved on a FAKE USB layer with a "slow instrument": a trigger that comes
within W ms of the end of a light write is lost with probability P
(native/chartread_helper/tests/i1pro2_lights_modes_test.c). The same lives
built against 4.3.36's driver lose triggers in every combination (W = 700,
P = 1.0, and P = 0.68 with a fixed seed); the new driver loses none with the
window one ms short of the quiet time, on every path, and once with the real
2100 ms. With the option off the driver is untouched (the fixture tests in
tests/test_i1pro2_lights_modes.py).
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
HELPER_SRC = ROOT / "native" / "chartread_helper"
INSTLIB = ROOT / "native" / "instlib"


@pytest.fixture(scope="module")
def runs(tmp_path_factory) -> "dict[str, str]":
    if sys.platform == "win32":
        pytest.skip("the fake-USB driver tests are built on macOS and Linux only")
    cmake = shutil.which("cmake")
    if cmake is None:
        pytest.skip("cmake not available: the helper is not built here")
    tmp = tmp_path_factory.mktemp("quiet")
    old = tmp / "v4336"
    old.mkdir()
    for f in ("i1pro.c", "i1pro_imp.c", "i1pro_imp.h"):
        r = subprocess.run(["git", "-C", str(ROOT), "show",
                            f"v4.3.36:native/instlib/{f}"],
                           capture_output=True, timeout=60)
        if r.returncode != 0:
            pytest.skip("the v4.3.36 tag is not in this checkout")
        (old / f).write_bytes(r.stdout)
    build = tmp / "build"
    subprocess.run([cmake, "-S", str(HELPER_SRC), "-B", str(build),
                    "-DCMAKE_BUILD_TYPE=Release", f"-DCQ_V4336_I1PRO_DIR={old}"],
                   check=True, capture_output=True, timeout=600)
    jobs = str(max(2, (os.cpu_count() or 4) // 2))
    targets = ("i1pro2_lights_modes_test", "i1pro2_lights_modes_test_v4336")
    r = subprocess.run([cmake, "--build", str(build), "--target", *targets,
                        "-j", jobs], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=1500)
    assert r.returncode == 0, r.stdout[-3000:] + r.stderr[-3000:]
    out = {}
    for t in targets:
        exe = next(p for p in build.rglob(t + "*")
                   if p.is_file() and os.access(p, os.X_OK)
                   and p.name in (t, t + ".exe"))
        rr = subprocess.run([str(exe)], capture_output=True, text=True,
                            encoding="utf-8", timeout=600)
        assert rr.returncode == 0 and rr.stdout.rstrip().endswith("ALL DONE"), \
            t + "\n" + rr.stdout[-2000:] + rr.stderr[-2000:]
        out[t] = rr.stdout
    return out


def _lines(text: str, scn: str) -> "list[str]":
    return [ln.split(" ", 1)[1] for ln in text.splitlines()
            if ln.startswith(scn + " ")]


def _scenarios(text: str, prefix: str) -> "list[str]":
    seen = []
    for ln in text.splitlines():
        s = ln.split(" ", 1)[0]
        if s.startswith(prefix) and s not in seen:
            seen.append(s)
    return seen


def _programs():
    from tests.test_i1pro2_lights_modes import _programs as p
    return p()


COMBOS = ("ready_off", "signals_off", "ready_lefton", "signals_lefton")
NEW_LIVES = (["new_q150_" + c for c in COMBOS]
             + ["paths_ready", "paths_signals", "full_signals"])


# ---------------------------------------------------------------------------
# The fault model reproduces the tester's fault with the old sequence
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("combo", COMBOS)
def test_4_3_34_to_4_3_36_lose_triggers_under_the_slow_instrument(runs, combo):
    """4.3.36 sent the i1Pro 2 "ready light only, off during a reading"
    (ready_off); 4.3.34 / 4.3.35 sent the stored choice (signals_off by
    default). Every one of them puts a light write right before a trigger."""
    old = runs["i1pro2_lights_modes_test_v4336"]
    det = _lines(old, f"old_p100_{combo}")
    assert sum(ln.startswith("LOST") for ln in det) >= 5
    stat = _lines(old, f"old_p068_{combo}")
    lost = sum(ln.startswith("LOST") for ln in stat)
    tried = sum(ln.startswith("GAPMS") and int(ln.split()[1]) < 700
                for ln in stat)
    assert tried >= 10 and 0.3 <= lost / tried <= 0.95, (lost, tried)


# ---------------------------------------------------------------------------
# The new sequence
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("scn", NEW_LIVES)
def test_nothing_is_lost_with_the_new_sequence(runs, scn):
    lines = _lines(runs["i1pro2_lights_modes_test"], scn)
    assert lines and lines[-1] == "END"
    assert not [ln for ln in lines if ln.startswith("LOST")]
    gaps = [int(ln.split()[1]) for ln in lines if ln.startswith("GAPMS")]
    quiet = 2100 if scn.startswith("full") else 150
    assert gaps and min(gaps) >= quiet, (scn, min(gaps))


def test_the_quiet_time_is_one_named_constant_of_2100_ms():
    src = (INSTLIB / "i1pro_imp.c").read_text(encoding="utf-8",
                                              errors="surrogateescape")
    assert len(re.findall(r"#define CQ_LIGHTS_QUIET_MS\s+(\d+)", src)) == 1
    assert re.search(r"#define CQ_LIGHTS_QUIET_MS\s+2100\b", src)
    assert src.count("CQ_LIGHTS_QUIET_MS") >= 2


def _by_step(lines):
    names, step, out = _programs(), None, []
    for ln in lines:
        p = ln.split(" ")
        if p[0] == "STEP":
            step = p[1]
        elif p[0] == "WR" and p[1] == "03":
            out.append((step, names.get(p[2], "UNKNOWN")))
        elif p[0] == "CTL" and p[1] == "d4":
            out.append((step, "TRIGGER"))
    return out


@pytest.mark.parametrize("scn", NEW_LIVES + ["on_" + c for c in COMBOS])
def test_no_light_write_between_a_press_and_its_data(runs, scn):
    """RULE A: inside a reading (from its start to its return) no light
    program is written; only a calibration starts with the recorded off."""
    seq = _by_step(_lines(runs["i1pro2_lights_modes_test"], scn))
    for step, what in seq:
        if step and step.startswith("read-"):
            assert what == "TRIGGER", (scn, step, what)
        if what == "OFF_SLOW":
            assert step == "cal-dark", (scn, step)


@pytest.mark.parametrize("scn", NEW_LIVES + ["on_" + c for c in COMBOS])
def test_only_recorded_bytes_and_no_0xc3_or_0xd7(runs, scn):
    lines = _lines(runs["i1pro2_lights_modes_test"], scn)
    names = _programs()
    for ln in lines:
        p = ln.split(" ")
        if p[0] == "WR" and p[1] == "03":
            assert p[2] in names, (scn, ln[:80])
        if p[0] == "CTL":
            assert p[1] not in ("c3", "d7"), (scn, ln)


def test_the_new_ready_order_as_recorded(runs):
    seq = [w for _s, w in _by_step(_lines(runs["i1pro2_lights_modes_test"],
                                          "on_signals_off")) if w != "TRIGGER"]
    assert seq[:3] == ["WHITE", "OFF_SLOW", "PULSE"]
    assert "WHITE" not in seq[1:]          # WHITE only at open now
    seq0 = [w for _s, w in _by_step(_lines(runs["i1pro2_lights_modes_test"],
                                           "on_ready_off")) if w != "TRIGGER"]
    # ready light only: nothing after a reading, PULSE after a calibration
    assert seq0 == ["WHITE", "OFF_SLOW", "PULSE", "OFF_SLOW", "PULSE",
                    "OFF_NOW"]


def test_retry_and_no_verdict_send_nothing_any_more(runs):
    lines = _lines(runs["i1pro2_lights_modes_test"], "on_signals_off")
    seq = _by_step(lines)
    assert not [s for s, w in seq
                if s in ("helper-prompt", "verdict-timeout") and w != "TRIGGER"]


def test_the_two_reading_choices_are_the_same_on_an_i1pro2(runs):
    t = runs["i1pro2_lights_modes_test"]

    def wire(scn):
        return [ln for ln in _lines(t, scn) if ln.split(" ")[0] in
                ("CTL", "WR", "RD")]
    assert wire("on_ready_off") == wire("on_ready_lefton")
    assert wire("on_signals_off") == wire("on_signals_lefton")


def test_the_wait_is_said_to_the_helper(runs):
    lines = _lines(runs["i1pro2_lights_modes_test"], "full_signals")
    assert lines.count("HELD") >= 3
    src = (HELPER_SRC / "chromiq_chartread.c").read_text(
        encoding="utf-8", errors="surrogateescape")
    assert "i1pro2_cq_lights_held = cq_lights_held2;" in src
    assert '{\\"event\\":\\"lights\\",\\"held_ms\\":%d}' in src


def test_option_off_never_waits_or_writes():
    src = (INSTLIB / "i1pro_imp.c").read_text(encoding="utf-8",
                                              errors="surrogateescape")
    body = src[src.index("void i1pro2_cq_lights_trigger(void *pp) {"):]
    body = body[:body.index("\n}\n")]
    first = body.index("m->cq_lights == CQ_LIGHTS_UNUSED)")
    assert first < body.index("cq_lights_quiet(m)")
    assert first < body.index("cq_lights_send(")


# ---------------------------------------------------------------------------
# Stop during a hold (4.3.37 review, M3)
# ---------------------------------------------------------------------------
def test_stop_during_a_hold_switches_the_lights_off_at_once(runs):
    """ChromIQ asks the helper to switch the lights off and end, and kills it
    1 s later; a hold lasts up to 2.1 s. The hold now asks the helper every
    20 ms, so the off goes out during the hold, the lights are reported off
    (the app then removes its "lights may still be on" marker), and a
    trigger after it still waits the quiet time."""
    lines = _lines(runs["i1pro2_lights_modes_test"], "stop_in_hold")
    i = lines.index("STEP stop-requested")
    j = lines.index("STEP read-dark", 0)
    assert j < i                              # inside the strip's hold
    assert lines[i + 1].startswith("CTL d6 0000000f")      # OFF_NOW
    assert lines[i + 3] == "LIGHTS-END 1"     # known off: the marker goes
    gaps = [int(ln.split()[1]) for ln in lines[i:] if ln.startswith("GAPMS")]
    assert gaps and min(gaps) >= 150


def test_the_helper_carries_out_a_stop_during_a_hold():
    src = (HELPER_SRC / "chromiq_chartread.c").read_text(
        encoding="utf-8", errors="surrogateescape")
    assert "i1pro2_cq_lights_hold_poll = cq_lights_take_pending;" in src
    js = (HELPER_SRC / "chromiq_json.c").read_text(encoding="utf-8")
    take = js[js.index("int cq_cmd_take_key(void) {"):]
    assert take.index("cq_lights_take_pending();") < take.index("cq_lock_take();")
    drv = (INSTLIB / "i1pro_imp.c").read_text(encoding="utf-8",
                                              errors="surrogateescape")
    body = drv[drv.index("static void cq_lights_quiet(i1proimp *m) {"):]
    body = body[:body.index("\n}\n")]
    assert "msec_sleep(quiet - since < 20 ? quiet - since : 20);" in body
    assert "i1pro2_cq_lights_hold_poll();" in body


def test_the_provenance_note_is_written_by_the_vendor_script():
    """4.3.37 review nit: scripts/vendor_instlib.py writes PROVENANCE.md
    from its own text, so a paragraph kept only in the file would be lost
    on the next re-vendor. Every prose line of the file's patch notes is in
    the script."""
    root = INSTLIB.parent.parent
    prov = (INSTLIB / "PROVENANCE.md").read_text(encoding="utf-8")
    notes = prov.split("## ChromIQ patches", 1)[1].split("| patched file", 1)[0]
    script = (root / "scripts" / "vendor_instlib.py").read_text(encoding="utf-8")
    for ln in notes.splitlines():
        if ln.strip():
            assert ln.replace("\\", "\\\\").replace('"', '\\"') in script, ln
