"""The i1Pro 2 lights Beta with its two choices (2026-11-13), on the wire.

The REAL vendored driver on a FAKE USB layer
(native/chartread_helper/tests/i1pro2_lights_modes_test.c): one whole
instrument life per combination of "result signals" and "lights during a
reading", in the order i1pro.c and ChromIQ's helper make the calls.

The owner's regression rule (2026-11-13): "with the new options off
everything should stay as it was before". So:

* with the Beta option off, and with it on but both choices off, the trace is
  byte for byte the one ChromIQ 4.3.33's own driver produced for the same life
  (tests/data/i1pro2_lights_v4333_trace.txt, made from commit ee661dc65 by
  scripts/make_lights_v4333_fixture.py);
* an original i1Pro (rev A-D) gets no light request in any combination;
* another firmware than the recorded 634 gets 4.3.33's lights whatever was
  chosen;
* the three new combinations send exactly the programs the design names, in
  the order it names (DESIGN.md 2a), and never one after the button was
  pressed for the next reading.
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
INSTLIB = ROOT / "native" / "instlib"
HELPER_SRC = ROOT / "native" / "chartread_helper"
FIXTURE = ROOT / "tests" / "data" / "i1pro2_lights_v4333_trace.txt"


def _c_array(text: str, name: str) -> str:
    m = re.search(r"static const unsigned char " + name +
                  r"\[(\d+)\] = \{(.*?)\};", text, re.S)
    body = re.sub(r"/\*.*?\*/", "", m.group(2), flags=re.S)
    return bytes(int(x, 16) for x in
                 re.findall(r"0x([0-9a-fA-F]{2})", body)).hex()


def _programs() -> "dict[str, str]":
    imp = (INSTLIB / "i1pro_imp.c").read_text(encoding="utf-8",
                                              errors="surrogateescape")
    hdr = (INSTLIB / "cq_i1pro2_programs.h").read_text(encoding="utf-8")
    return {_c_array(imp, "cq_lights_seq_white"): "WHITE",
            _c_array(imp, "cq_lights_seq_off_slow"): "OFF_SLOW",
            _c_array(imp, "cq_lights_seq_off_now"): "OFF_NOW",
            _c_array(hdr, "cq_lights_seq_pulse"): "PULSE",
            _c_array(hdr, "cq_lights_seq_green2"): "GREEN2",
            _c_array(hdr, "cq_lights_seq_red2"): "RED2"}


@pytest.fixture(scope="module")
def trace(tmp_path_factory) -> str:
    if sys.platform == "win32":
        pytest.skip("the fake-USB driver test is built on macOS and Linux only")
    cmake = shutil.which("cmake")
    if cmake is None:
        pytest.skip("cmake not available: the helper is not built here")
    build = tmp_path_factory.mktemp("lights_modes") / "build"
    subprocess.run([cmake, "-S", str(HELPER_SRC), "-B", str(build),
                    "-DCMAKE_BUILD_TYPE=Release"],
                   check=True, capture_output=True, timeout=600)
    jobs = str(max(2, (os.cpu_count() or 4) // 2))
    r = subprocess.run([cmake, "--build", str(build), "--target",
                        "i1pro2_lights_modes_test", "-j", jobs],
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=900)
    assert r.returncode == 0, r.stdout[-3000:] + r.stderr[-3000:]
    exe = next(p for p in build.rglob("i1pro2_lights_modes_test*")
               if p.is_file() and os.access(p, os.X_OK)
               and p.name in ("i1pro2_lights_modes_test",
                              "i1pro2_lights_modes_test.exe"))
    r = subprocess.run([str(exe)], capture_output=True, text=True,
                       encoding="utf-8", timeout=120)
    assert r.returncode == 0 and r.stdout.rstrip().endswith("ALL DONE"), \
        r.stdout[-2000:] + r.stderr[-2000:]
    return r.stdout


def _lines(text: str, scn: str) -> "list[str]":
    return [ln.split(" ", 1)[1] for ln in text.splitlines()
            if ln.startswith(scn + " ")]


def _wire(lines):
    return [ln for ln in lines if ln.split(" ", 1)[0] in ("CTL", "WR", "RD")]


def _fixture() -> str:
    return "\n".join(ln for ln in FIXTURE.read_text(encoding="utf-8").splitlines()
                     if not ln.startswith("#"))


def _programs_by_step(lines) -> "list[tuple[str, str]]":
    names, step, out = _programs(), None, []
    for ln in lines:
        parts = ln.split(" ")
        if parts[0] == "STEP":
            step = parts[1]
        elif parts[0] == "WR" and parts[1] == "03":
            out.append((step, names.get(parts[2], "UNKNOWN")))
    return out


# ---------------------------------------------------------------------------
# No regression
# ---------------------------------------------------------------------------
def test_the_fixture_is_4_3_33s():
    head = FIXTURE.read_text(encoding="utf-8").splitlines()[0]
    assert "ee661dc65" in head
    assert _fixture().rstrip().endswith("ALL DONE")


@pytest.mark.parametrize("scn", ["off_i1pro2", "off_i1pro", "on_ready_off",
                                 "revad_ready_off"])
def test_with_the_choices_off_the_wire_is_4_3_33s(trace, scn):
    expected = _lines(_fixture(), scn)
    assert expected, f"{scn} is not in the fixture"
    assert _lines(trace, scn) == expected


@pytest.mark.parametrize("scn", ["revad_ready_off", "revad_signals_off",
                                 "revad_ready_lefton", "revad_signals_lefton",
                                 "off_i1pro2", "off_i1pro"])
def test_no_light_request_without_the_option_or_on_an_original_i1pro(trace, scn):
    lines = _lines(trace, scn)
    assert lines and lines[-1] == "END"
    assert not any(ln.startswith("CTL d6") for ln in lines)
    assert not any(ln.startswith("WR 03") for ln in lines)


def test_another_firmware_gets_4_3_33s_lights_whatever_was_chosen(trace):
    assert _wire(_lines(trace, "fw600_signals_lefton")) == \
        _wire(_lines(trace, "on_ready_off"))


# ---------------------------------------------------------------------------
# The new combinations
# ---------------------------------------------------------------------------
def test_signals_with_the_lights_off_during_a_reading(trace):
    assert _programs_by_step(_lines(trace, "on_signals_off")) == [
        ("begin", "WHITE"),
        ("cal-dark", "OFF_SLOW"), ("cal-returned", "PULSE"),
        ("read-dark", "OFF_SLOW"), ("verdict-good", "GREEN2"),      # A
        ("read-dark", "OFF_SLOW"), ("helper-red", "RED2"),          # B
        ("read-dark", "OFF_SLOW"), ("verdict-bad", "RED2"),         # C
        ("read-dark", "OFF_SLOW"), ("verdict-timeout", "PULSE"),    # D
        ("read-dark", "OFF_SLOW"),                                  # E
        ("verdict-good-F", "GREEN2"),                               # F
        ("read-dark", "OFF_SLOW"),                                  # H
        # H's verdict came after the next press: refused, so the patch's
        # reading finds the lights already dark and needs no off
        ("helper-green", "GREEN2"),                                 # patch
        ("cal-dark", "OFF_SLOW"), ("cal-returned", "PULSE"),
        ("read-dark", "OFF_SLOW"), ("helper-red", "RED2"),          # G
        ("eeprom", "OFF_NOW"),
    ]


def test_ready_light_left_on_during_a_reading(trace):
    """i1Profiler's hand-held way without result signals: the open's steady
    WHITE never runs through a measurement; the calibration starts dark; the
    pulse is left running through every reading (dark and lit parts)."""
    assert _programs_by_step(_lines(trace, "on_ready_lefton")) == [
        ("begin", "WHITE"),
        ("cal-dark", "OFF_SLOW"), ("cal-returned", "PULSE"),
        ("cal-dark", "OFF_SLOW"), ("cal-returned", "PULSE"),
        ("eeprom", "OFF_NOW"),
    ]


def test_signals_with_the_lights_left_on(trace):
    assert _programs_by_step(_lines(trace, "on_signals_lefton")) == [
        ("begin", "WHITE"),
        ("cal-dark", "OFF_SLOW"), ("cal-returned", "PULSE"),
        ("verdict-good", "GREEN2"), ("helper-red", "RED2"),
        ("verdict-bad", "RED2"),
        ("verdict-good-F", "GREEN2"), ("helper-green", "GREEN2"),
        ("cal-dark", "OFF_SLOW"), ("cal-returned", "PULSE"),
        ("helper-red", "RED2"),
        ("eeprom", "OFF_NOW"),
    ]


@pytest.mark.parametrize("scn", ["on_signals_off", "on_signals_lefton"])
def test_a_late_verdict_or_one_after_a_press_sends_nothing(trace, scn):
    lines = _lines(trace, scn)
    for marker in ("STEP verdict-late", "STEP verdict-after-press"):
        i = lines.index(marker)
        assert lines[i + 1] == "STEP poll-nothing-owed" or \
            not lines[i + 1].startswith(("CTL", "WR")), marker


@pytest.mark.parametrize("scn", ["on_signals_off", "on_ready_lefton",
                                 "on_signals_lefton", "on_ready_off"])
def test_every_calibration_runs_dark(trace, scn):
    """The recording: OFF_SLOW 14 ms before the first calibration trigger.
    In every combination the calibration's first trigger is preceded by an
    off (or the lights are already dark)."""
    lines = _lines(trace, scn)
    lit = False
    for ln in lines:
        if ln.startswith("WR 03"):
            name = _programs()[ln.split(" ")[2]]
            lit = name not in ("OFF_SLOW", "OFF_NOW")
        if ln == "STEP cal-white":
            assert not lit, scn


def test_only_recorded_requests_reach_the_instrument(trace):
    """Every light request is 0xD6 with a 4-byte length, followed by exactly
    one of the six programs on 0x03; nothing else new appears on the wire."""
    names = _programs()
    lines = trace.splitlines()
    for i, ln in enumerate(lines):
        parts = ln.split(" ")
        if len(parts) > 2 and parts[1] == "CTL" and parts[2] == "d6":
            nxt = lines[i + 1].split(" ")
            assert nxt[1] == "WR" and nxt[2] == "03"
            assert nxt[3] in names
            assert int(parts[3], 16) == len(nxt[3]) // 2
        if len(parts) > 2 and parts[1] == "WR":
            assert parts[2] == "03" and parts[3] in names, ln
        if len(parts) > 2 and parts[1] == "CTL":
            assert parts[2] != "c3", "no EEPROM write, ever"
