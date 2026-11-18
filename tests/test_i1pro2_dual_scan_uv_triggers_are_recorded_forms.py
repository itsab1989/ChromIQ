"""The i1Pro 2 dual scan: every UV-LED trigger on the wire is a RECORDED form.

Independent safety review, 2026-11-18. The owner's rule for anything sent to an instrument: only
forms recorded from the vendor's software. X-Rite i1Profiler's recorded UV-LED triggers
(tests/data/i1pro2_dual_wire_shape.json) are 0x0200 (the tile, and the table's spot) and 0x0209
(the hand UV pass: scan + ruler end), always with 41 lamp clocks.

The trace of the real driver (native/chartread_helper/tests/i1pro2_dual_test.c, the
measurement-characteristics answer of a real i1Pro 2: 36 us clock, sub-clock divider 136) showed
two deviations, both strict xfails until the safety fix round of 2026-11-18 removed them:

* lamp clocks 102 on every UV trigger in scan mode (ArgyllCMS's scan lamp time 0.5 s / (136 x
  36 us)) and 51 in spot mode (0.25 s); neither ArgyllCMS's own UV mode (0) nor i1Profiler (41)
  sends either. Now a fixed 41 (``CQ_DUAL_UV_LAMPCLOCKS``) on every UV-LED trigger;
* 0x0201, a UV scan WITHOUT "ruler end". On the instrument it was reached when the lamp pass's
  measurement read failed (the ruler is then given up, so the UV pass gets no ruler bits) and
  when a UV pass was abandoned with Esc (the next strip's lamp pass gets no "ruler start" over
  the stream still drained, so its UV pass gets no "ruler end"). Now the helper asks for a UV
  pass only when ``i1pro2_cq_dual_uv_pass_ready`` says so, and the driver refuses any UV-LED
  trigger outside the recorded forms before it is sent (scenario uv-unpaired).
"""
from __future__ import annotations

import pytest

from tests.test_i1pro2_dual_scan_device import SHAPE, _requests, trace  # noqa: F401  (fixture)

RECORDED_LAMP_CLOCKS = 41
SCENARIOS = ("tile", "spot", "strip", "uv-error", "uv-unpaired")


def test_the_recorded_shape_says_41_lamp_clocks_and_two_uv_forms():
    """What the tests below hold the trace to (the shape file is the recordings' summary)."""
    tail = SHAPE["dual_calibration_tail"]["after_the_white"]
    strip = SHAPE["dual_strip_by_hand"]["per_strip"]
    spot = SHAPE["dual_spot_on_the_table"]["per_patch"]
    uv = [s for s in tail + strip + spot if int(s.get("flags", "0x0"), 16) & 0x0300 == 0x0200]
    assert {int(s["flags"], 16) for s in uv} == {0x0200, 0x0209}
    assert {s["lampclocks"] for s in strip + spot if "lampclocks" in s and s["lampclocks"]} == {41}


def test_every_uv_trigger_carries_the_recorded_41_lamp_clocks(trace):  # noqa: F811
    uv = [r for scn in SCENARIOS for r in _requests(trace, scn)
          if r["req"] == "0xD4" and r["flags"] & 0x0300 == 0x0200]
    assert uv
    assert {r["lampclocks"] for r in uv} == {RECORDED_LAMP_CLOCKS}, sorted({r["lampclocks"] for r in uv})


def test_no_uv_trigger_outside_the_recorded_forms(trace):  # noqa: F811
    forms = {r["flags"] for scn in SCENARIOS for r in _requests(trace, scn)
             if r["req"] == "0xD4" and r["flags"] & 0x0300 == 0x0200}
    assert forms <= {0x0200, 0x0209}, sorted(hex(f) for f in forms)
