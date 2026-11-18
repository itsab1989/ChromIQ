"""The i1Pro 2 dual scan: every UV-LED trigger on the wire is a RECORDED form.

Independent safety review, 2026-11-18. The owner's rule for anything sent to an instrument: only
forms recorded from the vendor's software. X-Rite i1Profiler's recorded UV-LED triggers
(tests/data/i1pro2_dual_wire_shape.json) are 0x0200 (the tile, and the table's spot) and 0x0209
(the hand UV pass: scan + ruler end), always with 41 lamp clocks.

The trace of the real driver (native/chartread_helper/tests/i1pro2_dual_test.c, the
measurement-characteristics answer of a real i1Pro 2: 36 us clock, sub-clock divider 136) shows
two deviations, so both tests are strict xfails until they are fixed (they turn XPASS then:
remove the marks):

* lamp clocks 102 on every UV trigger in scan mode (ArgyllCMS's scan lamp time 0.5 s / (136 x
  36 us)) and 51 in spot mode (0.25 s); neither ArgyllCMS's own UV mode (0) nor i1Profiler (41)
  sends either;
* 0x0201, a UV scan WITHOUT "ruler end" (scenario uv-error). On the instrument it is reached when
  the lamp pass's measurement read fails (the ruler is then given up, so the UV pass gets no
  ruler bits) and when a UV pass was abandoned with Esc (the next strip's lamp pass gets no
  "ruler start" over the stream still drained, so its UV pass gets no "ruler end").
"""
from __future__ import annotations

import pytest

from tests.test_i1pro2_dual_scan_device import SHAPE, _requests, trace  # noqa: F401  (fixture)

RECORDED_LAMP_CLOCKS = 41
SCENARIOS = ("tile", "spot", "strip", "uv-error")


def test_the_recorded_shape_says_41_lamp_clocks_and_two_uv_forms():
    """What the tests below hold the trace to (the shape file is the recordings' summary)."""
    tail = SHAPE["dual_calibration_tail"]["after_the_white"]
    strip = SHAPE["dual_strip_by_hand"]["per_strip"]
    spot = SHAPE["dual_spot_on_the_table"]["per_patch"]
    uv = [s for s in tail + strip + spot if int(s.get("flags", "0x0"), 16) & 0x0300 == 0x0200]
    assert {int(s["flags"], 16) for s in uv} == {0x0200, 0x0209}
    assert {s["lampclocks"] for s in strip + spot if "lampclocks" in s and s["lampclocks"]} == {41}


@pytest.mark.xfail(strict=True, reason="safety review 2026-11-18: UV triggers carry ArgyllCMS's "
                   "lamp time (102 / 51 clocks), not the recorded 41")
def test_every_uv_trigger_carries_the_recorded_41_lamp_clocks(trace):  # noqa: F811
    uv = [r for scn in SCENARIOS for r in _requests(trace, scn)
          if r["req"] == "0xD4" and r["flags"] & 0x0300 == 0x0200]
    assert uv
    assert {r["lampclocks"] for r in uv} == {RECORDED_LAMP_CLOCKS}, sorted({r["lampclocks"] for r in uv})


@pytest.mark.xfail(strict=True, reason="safety review 2026-11-18: a UV scan without 'ruler end' "
                   "(0x0201) is reachable and is not a recorded form")
def test_no_uv_trigger_outside_the_recorded_forms(trace):  # noqa: F811
    forms = {r["flags"] for scn in SCENARIOS for r in _requests(trace, scn)
             if r["req"] == "0xD4" and r["flags"] & 0x0300 == 0x0200}
    assert forms <= {0x0200, 0x0209}, sorted(hex(f) for f in forms)
