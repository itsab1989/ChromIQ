"""The lights Beta's two choices on an i1Pro 3 / 3 Plus (2026-11-14), on the wire.

The REAL vendored driver on a FAKE USB layer
(native/chartread_helper/tests/i1pro3_lights_modes_test.c): one whole
instrument life per combination of "what the lights show" and "during a
reading", in the order i1pro3.c and ChromIQ's helper make the calls.

Regression rules (the brief of 2026-11-14):

* with the Beta option off, and with it on and both choices at "as in ChromIQ
  4.3.33", the i1Pro 3's trace is byte for byte the one ChromIQ 4.3.34's own
  driver produced for the same life (tests/data/i1pro3_lights_v4334_trace.txt);
* the i1Pro 2 behaves in all four combinations, on every firmware, and the
  original i1Pro (rev A-D) gets nothing, exactly as with 4.3.34's driver
  (tests/data/i1pro2_lights_v4334_trace.txt); both fixtures are made from the
  v4.3.34 tag by scripts/make_lights_v4334_fixtures.py;
* only the three recorded patterns and Argyll's own off ever go out, through
  0x29 with a little-endian length; never a light command once the button was
  pressed for the next reading;
* a light request that fails (a dead transfer, all its timeout) never fails a
  measurement and delays it at most once by its timeout.
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
FIX3 = ROOT / "tests" / "data" / "i1pro3_lights_v4334_trace.txt"
FIX2 = ROOT / "tests" / "data" / "i1pro2_lights_v4334_trace.txt"

NAMES = {"01fa04120500": "READY", "0a1402120500": "GOOD",
         "061402120500": "BAD", "00": "OFF"}


def _build_and_run(tmp_path_factory, target: str) -> str:
    if sys.platform == "win32":
        pytest.skip("the fake-USB driver test is built on macOS and Linux only")
    cmake = shutil.which("cmake")
    if cmake is None:
        pytest.skip("cmake not available: the helper is not built here")
    build = tmp_path_factory.mktemp(target) / "build"
    subprocess.run([cmake, "-S", str(HELPER_SRC), "-B", str(build),
                    "-DCMAKE_BUILD_TYPE=Release"],
                   check=True, capture_output=True, timeout=600)
    jobs = str(max(2, (os.cpu_count() or 4) // 2))
    r = subprocess.run([cmake, "--build", str(build), "--target", target,
                        "-j", jobs], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=900)
    assert r.returncode == 0, r.stdout[-3000:] + r.stderr[-3000:]
    exe = next(p for p in build.rglob(target + "*")
               if p.is_file() and os.access(p, os.X_OK)
               and p.name in (target, target + ".exe"))
    r = subprocess.run([str(exe)], capture_output=True, text=True,
                       encoding="utf-8", timeout=300)
    assert r.returncode == 0 and r.stdout.rstrip().endswith("ALL DONE"), \
        r.stdout[-2000:] + r.stderr[-2000:]
    return r.stdout


@pytest.fixture(scope="module")
def trace(tmp_path_factory) -> str:
    return _build_and_run(tmp_path_factory, "i1pro3_lights_modes_test")


@pytest.fixture(scope="module")
def trace2(tmp_path_factory) -> str:
    return _build_and_run(tmp_path_factory, "i1pro2_lights_modes_test")


def _lines(text: str, scn: str) -> "list[str]":
    return [ln.split(" ", 1)[1] for ln in text.splitlines()
            if ln.startswith(scn + " ")]


def _comparable(lines):
    """Everything but the timings and the lines only this tree prints."""
    return [ln for ln in lines
            if ln.split(" ", 1)[0] not in ("MEASURE-MS", "CHOICES", "SENT")]


def _fixture(path: Path) -> str:
    return "\n".join(ln for ln in path.read_text(encoding="utf-8").splitlines()
                     if not ln.startswith("#"))


def _sent(lines) -> "list[tuple[str, str]]":
    step, out = None, []
    for ln in lines:
        parts = ln.split(" ")
        if parts[0] == "STEP":
            step = parts[1]
        elif parts[0] == "WR" and parts[1] == "02":
            out.append((step, NAMES.get(parts[2], "UNKNOWN")))
    return out


# ---------------------------------------------------------------------------
# No regression
# ---------------------------------------------------------------------------
def test_the_fixtures_are_4_3_34s():
    tag = subprocess.run(["git", "-C", str(ROOT), "rev-parse",
                          "v4.3.34^{commit}"], capture_output=True, text=True,
                         encoding="utf-8", timeout=60)
    for fix in (FIX2, FIX3):
        head = fix.read_text(encoding="utf-8").splitlines()[0]
        assert "ChromIQ 4.3.34 (" in head
        if tag.returncode == 0:
            assert tag.stdout.strip()[:9] in head
        assert _fixture(fix).rstrip().endswith("ALL DONE")


@pytest.mark.parametrize("scn", ["off", "on_ready_off", "plus_ready_off"])
def test_i1pro3_option_off_and_as_in_4_3_33_are_4_3_34s(trace, scn):
    expected = _comparable(_lines(_fixture(FIX3), scn))
    assert expected, f"{scn} is not in the fixture"
    assert _comparable(_lines(trace, scn)) == expected


def test_the_option_off_sends_no_light_request(trace):
    """Argyll's own open is not in this life; with the option off the patch
    adds nothing at all."""
    lines = _lines(trace, "off")
    assert lines[-1] == "END"
    assert not any(ln.startswith("CTL 29") for ln in lines)
    assert not any(ln.startswith("WR 02") for ln in lines)


def _i1pro2_scenarios() -> "list[str]":
    seen = []
    for ln in _fixture(FIX2).splitlines():
        scn = ln.split(" ", 1)[0]
        if scn != "ALL" and scn not in seen:
            seen.append(scn)
    return seen


def test_the_i1pro2_fixture_has_every_combination():
    scns = _i1pro2_scenarios()
    for needed in ("off_i1pro2", "off_i1pro", "on_ready_off", "on_signals_off",
                   "on_ready_lefton", "on_signals_lefton", "revad_ready_off",
                   "revad_signals_lefton", "fw600_signals_off",
                   "fw700_ready_off"):
        assert needed in scns, needed


@pytest.mark.parametrize("scn", _i1pro2_scenarios())
def test_the_i1pro2_is_4_3_34s_in_every_combination(trace2, scn):
    assert _lines(trace2, scn) == _lines(_fixture(FIX2), scn)


# ---------------------------------------------------------------------------
# The new combinations (DESIGN.md section 2)
# ---------------------------------------------------------------------------
def test_result_signals_with_the_lights_off_during_a_reading(trace):
    assert _sent(_lines(trace, "on_signals_off")) == [
        ("cal-returned", "READY"),
        ("read-dark", "OFF"), ("verdict-good", "GOOD"),        # A
        ("read-dark", "OFF"), ("helper-red", "BAD"),           # B refused
        ("read-dark", "OFF"), ("verdict-bad", "BAD"),          # C asked
        ("read-dark", "OFF"), ("verdict-timeout", "READY"),    # D no verdict
        ("read-dark", "OFF"),                                  # E
        # F read dark; E's verdict came after F was read: dropped
        ("verdict-good-F", "GOOD"),
        ("read-dark", "OFF"),                                  # H: pressed
        ("helper-green", "GOOD"),                              # patch
        ("cal-dark", "OFF"), ("cal-returned", "READY"),
        ("read-dark", "OFF"), ("helper-red", "BAD"),           # G
        ("close", "OFF"),
    ]


def test_as_in_4_3_33_with_the_lights_left_on(trace):
    """The driver's own verdict, sent over the pattern that plays through
    the reading; the calibration still starts dark."""
    assert _sent(_lines(trace, "on_ready_lefton")) == [
        ("cal-returned", "READY"),
        ("strip-A-returned", "GOOD"), ("strip-B-returned", "BAD"),
        ("strip-C-returned", "GOOD"), ("strip-D-returned", "GOOD"),
        ("strip-E-returned", "GOOD"), ("strip-F-returned", "GOOD"),
        ("strip-H-returned", "GOOD"), ("patch-1-returned", "GOOD"),
        ("cal-dark", "OFF"), ("cal-returned", "READY"),
        ("strip-G-returned", "BAD"),
        ("close", "OFF"),
    ]


def test_result_signals_with_the_lights_left_on(trace):
    """The review of 2026-11-14 (item 1): after a reading under "left on" the
    instrument most likely went dark by itself at the press, so the 3-second
    fallback (strip D: no verdict) shows READY, as with the lights off."""
    assert _sent(_lines(trace, "on_signals_lefton")) == [
        ("cal-returned", "READY"),
        ("verdict-good", "GOOD"), ("helper-red", "BAD"),
        ("verdict-bad", "BAD"), ("verdict-timeout", "READY"),
        ("verdict-good-F", "GOOD"), ("helper-green", "GOOD"),
        ("cal-dark", "OFF"), ("cal-returned", "READY"),
        ("helper-red", "BAD"),
        ("close", "OFF"),
    ]


@pytest.mark.parametrize("combo", ["signals_off", "ready_lefton",
                                   "signals_lefton"])
def test_the_i1pro3_plus_gets_the_same(trace, combo):
    assert _comparable(_lines(trace, "plus_" + combo)) == \
        _comparable(_lines(trace, "on_" + combo))


def test_the_firmware_is_only_reported(trace):
    assert "CHOICES 3 FW 123" in _lines(trace, "fw123_signals_lefton")
    assert _sent(_lines(trace, "fw123_signals_lefton")) == \
        _sent(_lines(trace, "on_signals_lefton"))


@pytest.mark.parametrize("scn", ["on_ready_off", "on_signals_off",
                                 "on_ready_lefton", "on_signals_lefton"])
def test_every_calibration_runs_dark(trace, scn):
    """No measurement request of a calibration while a pattern plays."""
    step, lit = None, False
    for ln in _lines(trace, scn):
        parts = ln.split(" ")
        if parts[0] == "STEP":
            step = parts[1]
        elif parts[0] == "WR" and parts[1] == "02":
            lit = NAMES[parts[2]] != "OFF"
        elif parts[0] == "CTL" and parts[1] in ("22", "27") \
                and step in ("cal-dark", "cal-white"):
            assert not lit, (scn, step)


@pytest.mark.parametrize("scn", ["on_signals_off", "on_signals_lefton"])
def test_a_late_verdict_or_one_after_a_press_sends_nothing(trace, scn):
    lines = _lines(trace, scn)
    for marker in ("STEP verdict-late", "STEP verdict-after-press"):
        i = lines.index(marker)
        assert not lines[i + 1].startswith(("CTL", "WR")), marker


def test_a_press_during_a_results_bytes_still_gets_the_off(trace):
    """The challenger's finding 1 (2026-11-14): the switch thread sees a
    press a few ms late, so a result can leave just after it; with "left on"
    that reading's measurements then get the off after all."""
    assert _sent(_lines(trace, "press_during_result")) == [
        ("cal-returned", "READY"),
        ("verdict-good", "GOOD"),
        ("read-dark", "OFF"),          # the press came during GOOD's bytes
        ("verdict-good-B", "GOOD"),
        ("close", "OFF"),              # strip C: left on again, no off
    ]
    lines = _lines(trace, "press_during_result")
    assert lines.index("PRESS") < lines.index("WR 02 00 tout=0.25")


def test_only_recorded_requests_reach_the_instrument(trace):
    """Every 0x29 carries the length of exactly one of the four sequences
    (little-endian) and is followed by it on 0x02; no other OUT request is
    new; never 0x23 (memory write) and never 0x3b from the lights."""
    lines = trace.splitlines()
    for i, ln in enumerate(lines):
        parts = ln.split(" ")
        if len(parts) > 3 and parts[1] == "CTL" and parts[2] == "29":
            n = int.from_bytes(bytes.fromhex(parts[3]), "little")
            nxt = lines[i + 1].split(" ")
            if nxt[1] == "FAIL":
                continue
            assert nxt[1] == "WR" and nxt[2] == "02" and nxt[3] in NAMES, ln
            assert len(nxt[3]) // 2 == n
        if len(parts) > 2 and parts[1] == "WR":
            assert parts[2] == "02" and parts[3] in NAMES, ln
        if len(parts) > 2 and parts[1] == "CTL":
            assert parts[2] != "23", "no memory write, ever"


@pytest.mark.parametrize("combo", ["ready_off", "signals_off",
                                   "ready_lefton", "signals_lefton"])
def test_a_dead_light_transfer_never_fails_or_holds_a_measurement(trace,
                                                                   combo):
    """Fault injection: the Nth 0x29 (N = 1..12) blocks for its whole timeout
    and fails. Every measurement still runs and returns OK; the lights are
    noted as failed once and never used again; a measurement waits at most
    one timeout (0.25 s) longer, once in the whole life."""
    fired = 0
    for k in range(1, 13):
        lines = _lines(trace, f"fail{k}_{combo}")
        assert lines and lines[-1] == "END"
        assert not any(ln.startswith("MEASURE-RETURNED") for ln in lines)
        if "FAIL 29" not in lines:
            continue
        fired += 1
        i = lines.index("FAIL 29")
        assert sum(ln.startswith("NOTE") for ln in lines) == 1
        assert not any(ln.startswith(("CTL 29", "WR 02")) for ln in lines[i:])
        slow = [int(ln.split(" ")[1]) for ln in lines
                if ln.startswith("MEASURE-MS") and int(ln.split(" ")[1]) > 120]
        assert len(slow) <= 1 and all(ms < 600 for ms in slow), slow
    assert fired >= 4, combo


def test_the_helper_dispatches_both_generations_the_same_way():
    src = (HELPER_SRC / "chromiq_chartread.c").read_text(
        encoding="utf-8", errors="surrogateescape")
    body = src[src.index("static int cq_lights_signals_on(void) {"):]
    body = body[:body.index("\n}\n")]
    assert "cq_lights_gen == 2 || cq_lights_gen == 3" in body
    sess = src[src.index("static void cq_lights_for_session("):]
    sess = sess[:sess.index("\n}\n")]
    assert "i1pro3_cq_lights_options(it, cq_lights_signals, cq_lights_left_on);" in sess
    assert "i1pro2_cq_lights_options(it, cq_lights_signals, cq_lights_left_on);" in sess
    # the i1Pro 3's off never reaches the helper's log callback
    imp = (ROOT / "native" / "instlib" / "i1pro3_imp.c").read_text(
        encoding="utf-8", errors="surrogateescape")
    assert re.search(r"which != CQ3_LIGHTS_OFF && i1pro3_cq_lights_sent != NULL",
                     imp)


def test_a_keyboard_started_reading_gets_the_off_even_when_left_on(trace):
    """The review of 2026-11-14 (item 2): i1Profiler was only recorded
    measuring with a pattern playing after a press of the instrument's
    button, when the instrument goes dark by itself. A reading started from
    the keyboard (no press) gets the off as in 4.3.34; the next one, started
    by the button, does not."""
    assert _sent(_lines(trace, "keyboard_spot_lefton")) == [
        ("cal-returned", "READY"),
        ("read-dark", "OFF"), ("patch-key-returned", "GOOD"),
        ("patch-button-returned", "GOOD"),
        ("close", "OFF"),
    ]
