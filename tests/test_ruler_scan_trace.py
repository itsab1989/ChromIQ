"""The ruler check Beta (2026-11-14), on the wire: hand-held strip scans of an
i1Pro 2 and of the original i1Pro through the REAL vendored driver on a FAKE
USB layer (native/chartread_helper/tests/i1pro_ruler_scan_test.c).

With the option off, every scan's trace is byte for byte the base branch's
(tests/data/i1pro_ruler_base_trace.txt, made from 6de402163 by
scripts/make_ruler_base_fixtures.py): the same 0xD4 flags (0x0101), nothing
on 0x85. The ruler scenarios join this file with the driver part.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from tests.test_i1pro3_lights_modes import _build_and_run

FIX = Path(__file__).resolve().parent / "data" / "i1pro_ruler_base_trace.txt"


@pytest.fixture(scope="module")
def trace(tmp_path_factory) -> str:
    return _build_and_run(tmp_path_factory, "i1pro_ruler_scan_test")


def _scn(text: str, scn: str) -> "list[str]":
    return [ln for ln in text.splitlines() if ln.startswith(scn + " ")]


@pytest.mark.parametrize("scn", ["off_i1pro2", "off_i1pro"])
def test_option_off_is_the_base_branch_byte_for_byte(trace, scn):
    base = FIX.read_text(encoding="utf-8")
    got = _scn(trace, scn)
    assert got, f"no {scn} lines"
    assert got == _scn(base, scn)


def test_off_never_touches_the_ruler_channel(trace):
    for ln in _scn(trace, "off_i1pro2") + _scn(trace, "off_i1pro"):
        assert " RD 85 " not in ln and " CANCEL" not in ln
    d4 = [ln for ln in _scn(trace, "off_i1pro2") if " CTL d4 " in ln]
    assert d4 and all(ln.split()[3].endswith("0101") for ln in d4)


# ---- the option on (the helper switched the ruler on and arms each strip) --

def _ruler(trace: str, scn: str) -> "list[dict]":
    out = []
    for ln in _scn(trace, scn):
        parts = ln.split()
        if parts[1] != "RULER":
            continue
        if parts[2] == "none":
            out.append({"none": True, "state": int(parts[3].split("=")[1])})
        else:
            out.append({k: (int(v, 0) if k == "err" else int(v))
                        for k, v in (p.split("=") for p in parts[2:])})
    return out


def _d4(trace: str, scn: str) -> "list[str]":
    return [ln.split()[3][-4:] for ln in _scn(trace, scn) if " CTL d4 " in ln]


def test_on_only_the_two_bits_are_new_and_the_reads_are_4096(trace):
    assert _d4(trace, "on_clean") == ["010d"] * 3          # i1Profiler's flags
    assert f"on_clean READS85 1 max=4096" in trace
    # nothing else differs from an unarmed scan of the same strip
    on = [ln.split(" ", 1)[1] for ln in _scn(trace, "on_clean")
          if " RD 82 " in ln]
    assert on == ["RD 82 1072000 -> 32160 tout=21.78"] * 3
    r = _ruler(trace, "on_clean")
    assert all(x["ended"] == 1 and x["bytes"] == 120 * 136 - 5 and x["nch"] == 300
               and x["giveup"] == 0 for x in r)


def test_no_sensor_or_an_original_i1pro_never_get_the_ruler(trace):
    assert _d4(trace, "on_nosensor") == ["0101"] * 3
    assert "on_nosensor READS85 0 max=0" in trace
    assert "on_revad READS85 0 max=0" in trace
    assert not any(" CTL d4 " in ln for ln in _scn(trace, "on_revad"))
    assert all(x.get("none") for x in _ruler(trace, "on_revad"))


@pytest.mark.parametrize("scn,why", [("on_error", 1), ("on_zero", 2),
                                     ("on_late", 3), ("on_noend", 3),
                                     ("on_rate", 5)])
def test_anything_unusual_gives_the_ruler_up_and_the_scans_go_on(trace, scn, why):
    r = _ruler(trace, scn)
    assert r[0].get("giveup") == why
    assert all(x.get("none") and x["state"] == why for x in r[1:])
    d4 = _d4(trace, scn)
    assert d4[0] == "010d" and all(f == "0101" for f in d4[1:])
    # every measurement still read all its readings
    assert all(ln.endswith("readings=120") for ln in _scn(trace, scn)
               if " RESULT " in ln)
    assert all(" RESULT ev=0x0 " in ln for ln in _scn(trace, scn)
               if " RESULT " in ln)


def test_a_stream_that_does_not_end_is_drained_never_stopped_by_request(trace):
    for scn in ("on_late", "on_noend"):
        assert _ruler(trace, scn)[0]["notend"] == 1
        # only ever a host-side cancel at the close; no request was sent
        assert not any(" CTL d7 " in ln for ln in _scn(trace, scn))
    assert "on_noend CLOSED cancels=1" in trace


def test_no_ruler_short_and_garbled_streams_are_recorded_as_they_are(trace):
    assert _ruler(trace, "on_none")[0]["nch"] == 0
    assert _ruler(trace, "on_short")[0]["bytes"] < 120 * 136 // 2 + 10
    assert _ruler(trace, "on_garbled")[0]["nch"] == 301
    for scn in ("on_none", "on_short", "on_garbled"):
        assert _ruler(trace, scn)[0]["giveup"] == 0


def test_the_lights_and_the_ruler_work_together(trace):
    lines = _scn(trace, "on_clean_lights")
    assert "on_clean_lights LIGHTS 1" in lines
    assert _d4(trace, "on_clean_lights") == ["010d"] * 3
    assert all(x["giveup"] == 0 for x in _ruler(trace, "on_clean_lights"))
    # the lights' own requests are unchanged: 0xD6 then the bytes on 0x03
    assert any(" CTL d6 " in ln for ln in lines)


def test_the_recogniser_gives_identical_values_with_the_record_open(trace):
    assert "extract EXTRACT ev=0x0 identical=1 ncut=16 ntrace=560" in trace


def test_never_0xd7_nor_any_new_request(trace):
    reqs = {ln.split()[2] for ln in trace.splitlines() if " CTL " in ln}
    assert reqs <= {"d4", "c1", "c0", "d6"}


# ---- the i1Pro 3: copies only (native/chartread_helper/tests/i1pro3_ruler_test.c)

@pytest.fixture(scope="module")
def trace3(tmp_path_factory) -> str:
    return _build_and_run(tmp_path_factory, "i1pro3_ruler_test")


def test_i1pro3_hooks_record_only_an_armed_strip(trace3):
    lines = trace3.splitlines()
    assert "off REC none" in lines and "off STATE -1" in lines
    assert "unarmed REC none" in lines
    armed = next(ln for ln in lines if ln.startswith("armed REC"))
    for part in ("gen=3", "ended=6", "samples=103200", "nch=343", "readings=600",
                 "clocks=172", "used=1", "ncut=16", "domain=1", "ntrace=100"):
        assert part in armed, part
    # one-shot: the second scan of the same strip was not recorded over it
    assert next(ln for ln in lines if ln.startswith("oneshot REC")).count(
        "samples=103200") == 1
    assert next(ln for ln in lines if ln.startswith("failed REC")).startswith(
        "failed REC gen=3 ended=4")


# ---- review round 1 (2026-11-14): items 2, 3 and 5 ------------------------

@pytest.mark.parametrize("scn", ["on_late", "on_noend", "on_stall", "on_stallnc",
                                 "on_huge", "on_gone", "on_late200", "on_fail82",
                                 "on_failstart", "on_clean", "on_error", "on_zero"])
def test_no_clear_halt_request_before_the_close(trace, scn):
    """On macOS an aborted or timed-out read is followed by a clear-halt
    request; a ruler read never times out before the close, so the request
    can only come when the instrument is let go (review item 2)."""
    assert f"{scn} CLEARHALTS before close 0" in trace


@pytest.mark.parametrize("scn", ["on_noend", "on_stall", "on_stallnc"])
def test_the_close_is_bounded_even_when_a_cancel_cannot_abort(trace, scn):
    assert f"{scn} CLOSED cancels=1 within2600=1" in trace      # review item 3


def test_the_reviewers_faults_change_no_reading(trace):
    for scn, why in (("on_stall", 3), ("on_stallnc", 3), ("on_gone", 1),
                     ("on_fail82", 4)):
        r = _ruler(trace, scn)
        assert r[0]["giveup"] == why
        assert _d4(trace, scn)[1:] == ["0101", "0101"]
    for scn in ("on_stall", "on_stallnc", "on_gone", "on_huge", "on_late200"):
        assert all(" RESULT ev=0x0 readings=120" in ln for ln in _scn(trace, scn)
                   if " RESULT " in ln)
    huge = _ruler(trace, "on_huge")[0]
    assert huge["giveup"] == 0 and huge["bytes"] > 3 * 1024 * 1024
    assert _ruler(trace, "on_late200")[0]["giveup"] == 0


def test_a_reader_that_cannot_start_sends_no_ruler_bits(trace):
    """Review item 5: the bits never go out with nobody reading 0x85."""
    assert _d4(trace, "on_failstart") == ["0101"] * 3
    assert _ruler(trace, "on_failstart")[0]["giveup"] == 6
