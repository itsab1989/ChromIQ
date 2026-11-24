"""4.3.58, item 40: the hand i1Pro 2 / ES-2000 dual scan's start-up calibration includes the LED
wavelength calibration, as every normal session's does.

4.3.48 to 4.3.57 asked ArgyllCMS for a white calibration ALONE when a dual session started
(chromiq_chartread.c, the strip branch's dual case: ``inst_calt_ref_white``). ArgyllCMS runs the
i1Pro 2's wavelength-LED fit only when the request contains ``inst_calt_wavelength``
(i1pro_imp.c, i1pro_imp_calibrate), so every dual reading (M0, M1, M2) kept the factory or a
stale wavelength offset: about 1 nm on a tester's 616 patches, most of the 0.49 dE00 to
i1Profiler. The dark before the white
was skipped too.

The dual branch now asks for what a normal start asks for (``inst_calt_needed``: wavelength,
dark, white at the first calibration) and the white in any case
(chromiq_dualcal.h, ``cq_dual_startup_calt``). Proved on the wire through the REAL driver on the
fake USB layer (native/chartread_helper/tests/i1pro2_startcal_test.c): the dual start sends
exactly the normal start's requests, then exactly the dual tile it sent before, and the
wavelength-LED pair has the same command form as X-Rite i1Profiler's, at the exposure stored in
the instrument (16104 clocks in the recordings and in the test harness)
(tests/data/i1pro2_dual_wire_shape.json, ``wavelength_led_in_the_calibration``).
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from tests.test_i1pro2_dual_scan_device import SHAPE, _lines, _requests
from tests.test_i1pro3_lights_modes import _build_and_run

ROOT = Path(__file__).resolve().parent.parent
HELPER = ROOT / "native" / "chartread_helper"


@pytest.fixture(scope="module")
def trace(tmp_path_factory) -> str:
    # ArgyllCMS saves its calibration after each one: the program writes it here (XDG_CACHE_HOME),
    # never into the person's cache
    cache = tmp_path_factory.mktemp("startcal_cache")
    return _build_and_run(tmp_path_factory, "i1pro2_startcal_test", args=(cache,))


def _d4(text: str, scn: str) -> "list[tuple]":
    """Every trigger of a scenario: (flags, intclocks, lampclocks, nummeas)."""
    return [(r["flags"], r["intclocks"], r["lampclocks"], r["nummeas"])
            for r in _requests(text, scn) if r["req"] == "0xD4"]


def _calibration(text: str, scn: str) -> "list[str]":
    """The control requests between the placement on the tile and the end of the calibration."""
    out, on = [], False
    for ln in _lines(text, scn):
        if ln == "STEP on-the-tile":
            on = True
        elif ln.startswith("CALIBRATED"):
            break
        elif on and ln.startswith("CTL"):
            out.append(ln)
    return out


def _tile(text: str, scn: str) -> "list[str]":
    out, on = [], False
    for ln in _lines(text, scn):
        if ln == "STEP dual-tile":
            on = True
        elif ln == "STEP close":
            break
        elif on and ln.startswith("CTL"):
            out.append(ln)
    return out


def _value(text: str, scn: str, key: str) -> str:
    return next(ln for ln in _lines(text, scn) if ln.startswith(key))


WL = [(0x0000, 16104, 0, 1), (0x0300, 16104, 0, 1)]     # the recorded pair


def test_the_recorded_wavelength_pair_is_what_the_shape_file_says():
    want = SHAPE["wavelength_led_in_the_calibration"]["requests"]
    assert [(int(w["flags"], 16), w["intclocks"], w["lampclocks"], w["nummeas"]) for w in want] == WL


def test_a_normal_start_sends_the_wavelength_led_before_the_white(trace):
    d4 = _d4(trace, "normal")
    assert d4[:2] == WL
    assert [f for f, *_ in d4].index(0x0100) > 1                 # the white comes after it
    assert "NEEDED 0x70 ASKED 0x2" in _value(trace, "normal", "NEEDED")   # inst_calt_needed
    assert "wl_valid 1 wl_offset 0.300" in _value(trace, "normal", "CALIBRATED")


def test_the_old_dual_start_sent_no_wavelength_led(trace):
    """What 4.3.48 to 4.3.57 did (kept as a scenario so the fault stays visible): no 0x0300,
    no dark before the white, and the factory wavelength offset left in place."""
    d4 = _d4(trace, "dual-4357")
    assert all(f & 0x0300 != 0x0300 for f, *_ in d4)
    assert d4[0][0] == 0x0100                                    # the white, without a dark first
    assert "wl_valid 0 wl_offset 0.000" in _value(trace, "dual-4357", "CALIBRATED")


def test_the_dual_start_sends_the_normal_start_then_the_same_dual_tile(trace):
    assert _calibration(trace, "dual") == _calibration(trace, "normal")
    assert _d4(trace, "dual")[:2] == WL
    assert "wl_valid 1 wl_offset 0.300" in _value(trace, "dual", "CALIBRATED")
    # the dual white (the tile read with the UV LED) exactly as before, and as recorded
    assert _tile(trace, "dual") == _tile(trace, "dual-4357") and _tile(trace, "dual")
    tile = [r for r in _requests(trace, "dual") if r["req"] in ("0xD4", "0xD8")][-3:]
    want = SHAPE["dual_calibration_tail"]["after_the_white"]
    assert [r["req"] for r in tile] == [w["req"] for w in want]
    assert (tile[0]["flags"], tile[0]["nummeas"]) == (0x0000, 10)
    assert (tile[1]["flags"], tile[1]["nummeas"], tile[1]["lampclocks"]) == (0x0200, 5, 41)
    assert "TILE ev 0 ok 1 lamp_clocks 139 uv_clocks 139" in _value(trace, "dual", "TILE")


def test_the_dual_request_is_the_normal_one_and_the_white(trace):
    """At a session's start ArgyllCMS needs wavelength + dark + white (0x70): asked whole, by the
    helper's own function (the old branch asked 0x20, the white alone)."""
    assert "NEEDED 0x70 ASKED 0x70" in _value(trace, "dual", "NEEDED")
    assert "NEEDED 0x70 ASKED 0x20" in _value(trace, "dual-4357", "NEEDED")


def test_the_helper_asks_for_it_in_the_dual_branch():
    src = (HELPER / "chromiq_chartread.c").read_text(encoding="utf-8", errors="replace")
    i = src.index("if (nocal == 0 && cq_dd.on && !cq_dd.cal.have_uv_tile) {")
    branch = src[i:src.index("} else if (nocal == 0 && (it->needs_calibration(it)", i)]
    assert "cq_handle_calibrate(it, cq_dual_startup_calt(it->needs_calibration(it))," in branch
    assert "inst_calt_ref_white" not in re.sub(r"/\*.*?\*/", "", branch, flags=re.S)
    assert '#include "chromiq_dualcal.h"' in src
    h = (HELPER / "chromiq_dualcal.h").read_text(encoding="utf-8")
    assert "(needed & inst_calt_n_dfrble_mask) | inst_calt_ref_white" in h


def test_the_bundled_helper_is_this_build():
    ext = (HELPER / "chromiq_ext.h").read_text(encoding="utf-8")
    assert '"chromiq-chartread 2026-11-25a ' in ext and "+dual-startup-wavelength" in ext
    exe = ROOT / "native" / "chromiq-chartread"
    if not exe.is_file():
        pytest.skip("no bundled helper in this checkout")
    data = exe.read_bytes()
    assert b"chromiq-chartread 2026-11-25a " in data and b"+dual-startup-wavelength" in data
