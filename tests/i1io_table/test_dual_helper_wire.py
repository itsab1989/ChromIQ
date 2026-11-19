"""The i1Pro 2 dual scan on the i1iO 2 table: the INSTRUMENT's wire (2026-11-18).

The volunteer recorded i1Profiler 3.8.6 doing a dual scan on his table (private analysis,
ChromIQ-work 2026-11-18_i1io_owner_first_runs, section 2; recording B, all five accepted rows
alike). Per row the i1Pro 2 got exactly:

* the lamp pass: ``0xD4 0000008b 00000029 <N> 0100`` (lit FIRST), its data, ``0xC9`` (8 bytes
  in), then ``0xD4 0000008b 00000000 00000005 0000`` (5 dark AFTER the pass);
* the UV pass: ``0xD4 0000008b 00000029 <N> 0200`` (the UV LED, 41 lamp clocks), its data,
  5 dark, then ``0xD8`` (the UV LED's volts);
* on the table's tile, after the white: 10 dark + 5 UV-LED readings at 139 clocks, ``0xD8``.

The REAL vendored driver code (native/instlib/cq_i1pro2_dual.h, section (d)) runs on a fake USB
layer (native/chartread_helper/tests/i1io_table_dual_test.c) and must send exactly that, and
nothing when a pass is not allowed: no UV pass before or without this row's lamp pass, none
without a dual tile, none longer than the longest recorded UV-LED time (1,150 readings), none
from an original i1Pro or an i1Pro 2 without a UV LED.
"""
from __future__ import annotations

import pytest

from tests.test_i1pro3_lights_modes import _build_and_run

N550 = "00000226"
REC_LAMP = "0000008b00000029" + N550 + "0100"
REC_UV = "0000008b00000029" + N550 + "0200"
REC_DARK5 = "0000008b00000000000000050000"
REC_DARK10 = "0000008b000000000000000a0000"
REC_TILE_UV = "0000008b00000029000000050200"
REC_LIGHTS = [("CTL", "d6", "00000012"), ("WR", "03", "000000010000000a00000002003640000001")]


@pytest.fixture(scope="module")
def trace(tmp_path_factory) -> str:
    return _build_and_run(tmp_path_factory, "i1io_table_dual_test")


def _scn(text, scn):
    return [ln.split(" ", 1)[1] for ln in text.splitlines() if ln.startswith(scn + " ")]


def _wire(lines):
    out = []
    for ln in lines:
        p = ln.split()
        if p[0] in ("CTL", "WR"):
            out.append((p[0], p[1], p[2]))
        elif p[0] == "RD":
            out.append(("RD", p[1], " ".join(p[2:5])))
    return out


def test_the_tile_is_the_recorded_dual_calibration_and_is_kept_for_this_white_only(trace):
    lines = _scn(trace, "tile")
    assert _wire(lines) == [("CTL", "d4", REC_DARK10), ("RD", "82", "2680 -> 2680"),
                            ("CTL", "d4", REC_TILE_UV), ("RD", "82", "1340 -> 1340"),
                            ("CTL", "d8", "in4")]
    assert "ON 0 ruler=0" in lines            # the table reads no ruler
    restores = [ln for ln in lines if ln.startswith("RESTORE")]
    # nothing kept; kept; another date: no; the date back: yes; SHOULD-3 R9: another white
    # reading of the SAME date (only its checksum differs): no
    assert restores == ["RESTORE 0 uv_clocks=-1", "RESTORE 1 uv_clocks=139",
                        "RESTORE 0 uv_clocks=-1", "RESTORE 1 uv_clocks=139",
                        "RESTORE 0 uv_clocks=-1"]
    assert "SAVED 1" in lines


def test_a_dual_row_is_the_recorded_bytes(trace):
    lines = _scn(trace, "row")
    assert _wire(lines) == REC_LIGHTS + [
        ("CTL", "d4", REC_LAMP), ("RD", "82", "147400 -> 147400"), ("CTL", "c9", "in8"),
        ("CTL", "d4", REC_DARK5), ("RD", "82", "1340 -> 1340"),
        ("CTL", "d4", REC_UV), ("RD", "82", "147400 -> 147400"),
        ("CTL", "d4", REC_DARK5), ("RD", "82", "1340 -> 1340"), ("CTL", "d8", "in4")]


def test_a_uv_pass_only_right_after_its_lamp_pass(trace):
    lines = _scn(trace, "row")
    readies = [ln for ln in lines if ln.startswith("READY")]
    assert readies[0] == "READY uv -1 wait=0 why=the lamp pass of this row did not deliver"
    assert readies[1] == "READY lamp -1 wait=0 why=no dual calibration"
    assert readies[2].startswith("READY lamp -1") and "lights-off" in readies[2]
    assert readies[3] == "READY lamp -1 wait=0 why=reading count out of range"
    assert readies[4] == "READY lamp 1 wait=0 why=-"
    assert readies[5] == "READY uv 1 wait=0 why=-"
    # one UV pass per lamp pass: the second is refused and NOTHING is sent
    assert readies[6] == "READY uv -1 wait=0 why=the lamp pass of this row did not deliver"
    fires = [ln for ln in lines if ln.startswith("FIRE")]
    assert fires[-1].startswith("FIRE rc=-1") and "lit_sent=0 dark_sent=0" in fires[-1]
    assert lines[-2].startswith("FIRE rc=-1") and lines[-3] == "STEP fire uv 550"


def test_a_failed_lamp_pass_allows_no_uv_pass(trace):
    lines = _scn(trace, "lampfail")
    assert [w for w in _wire(lines) if w[2] == REC_UV] == []
    assert "READY uv -1 wait=0 why=the lamp pass of this row did not deliver" in lines


def test_a_failed_uv_trigger_still_ends_the_pass_as_recorded(trace):
    w = _wire(_scn(trace, "uvfail"))
    i = w.index(("CTL", "d4", REC_UV))
    assert w[i + 1] == ("RD", "82", "147400 -> TIMEOUT")
    assert w[i + 2:] == [("CTL", "d4", REC_DARK5), ("RD", "82", "1340 -> 1340"),
                         ("CTL", "d8", "in4")]


@pytest.mark.parametrize("scn", ["revad", "nouv"])
def test_nothing_without_an_i1pro2_that_has_the_uv_led(trace, scn):
    lines = _scn(trace, scn)
    assert not [w for w in _wire(lines) if w[1] in ("d4", "d8", "c9")]
    assert any(ln.startswith("READY lamp -1") and "not a table dual session" in ln for ln in lines)


def test_every_uv_trigger_is_a_recorded_form_with_41_lamp_clocks(trace):
    uv = [w for w in _wire(trace.splitlines() and [" ".join(ln.split(" ")[1:])
                                                    for ln in trace.splitlines() if " CTL d4 " in ln])
          if w[2][-4:] == "0200"]
    assert uv and all(w[2][8:16] == "00000029" for w in uv)
    assert all(w[2][-4:] in ("0000", "0100", "0200")
               for w in _wire([" ".join(ln.split(" ")[1:]) for ln in trace.splitlines()
                               if " CTL d4 " in ln]))


def _ms(line: str) -> int:
    return int(line.rsplit("+", 1)[1])


def test_the_lamp_pass_dark_waits_as_long_as_i1profiler_did(trace):
    """SHOULD-1 (table safety review, 2026-11-19): i1Profiler took the 5 dark readings 131 to 180
    ms after a lamp pass's last data (the volunteer's table, five dual rows); ChromIQ took them
    about 20 ms after. The dark now comes at least 170 ms after the lamp went out."""
    lines = _scn(trace, "row")
    i = next(k for k, ln in enumerate(lines) if ln.startswith("CTL d4 " + REC_LAMP))
    data = next(ln for ln in lines[i:] if ln.startswith("RD 82 147400 -> 147400"))
    dark = next(ln for ln in lines[i:] if ln.startswith("CTL d4 " + REC_DARK5))
    assert lines.index(data) < lines.index(dark)
    assert _ms(dark) - _ms(data) >= 169, (data, dark)
    # the UV pass's dark is not delayed (recorded: 6 ms after its data)
    j = next(k for k, ln in enumerate(lines) if ln.startswith("CTL d4 " + REC_UV))
    udata = next(ln for ln in lines[j:] if ln.startswith("RD 82 147400 -> 147400"))
    udark = next(ln for ln in lines[j:] if ln.startswith("CTL d4 " + REC_DARK5))
    assert _ms(udark) - _ms(udata) < 100, (udata, udark)


def test_a_fire_the_last_ready_check_did_not_allow_sends_nothing(trace):
    """SHOULD-3 R10: the helper's arm step refuses a fire when no pass was armed; behind it the
    driver itself fires only the pass its last ready check said yes to, once."""
    lines = _scn(trace, "unarmed")
    fires = [ln for ln in lines if ln.startswith("FIRE")]
    assert len(fires) == 4
    assert fires[0].startswith("FIRE rc=-1") and "lit_sent=0 dark_sent=0" in fires[0]
    assert fires[1].startswith("FIRE rc=-1") and "lit_sent=0 dark_sent=0" in fires[1]
    assert fires[2].startswith("FIRE rc=0")
    assert fires[3].startswith("FIRE rc=-1") and "lit_sent=0 dark_sent=0" in fires[3]
    w = _wire(lines)
    assert [x for x in w if x[2] == REC_UV] == []
    assert [x for x in w if x[1] == "d4"] == [("CTL", "d4", REC_LAMP), ("CTL", "d4", REC_DARK5)]


def test_the_helper_fires_only_an_armed_pass_and_keeps_only_a_checked_tile():
    """SHOULD-3 R10 / R14, pinned in chromiq_tablescan.c itself (its static functions run only
    inside the helper's table-scan mode, which opens a real instrument): the pass fired is the
    one armed, never another; and the dual tile is saved only inside the branch where its check
    passed."""
    import re
    from pathlib import Path
    src = (Path(__file__).resolve().parents[2] / "native/chartread_helper/chromiq_tablescan.c"
           ).read_text(encoding="utf-8")
    a = src.index("static int ts_dual_fire(")
    fire = src[a:src.index("\n}\n", a)]
    assert "\tint pass = ts_dd.pass, rc, vb = -1, va = -1;" in fire
    assert len(re.findall(r"(?<![.\w])pass\s*=[^=]", fire)) == 1   # the declaration only
    i_guard = fire.index("if (pass != CQ_TDUAL_PASS_LAMP && pass != CQ_TDUAL_PASS_UV) {")
    assert i_guard < fire.index("i1pro2_cq_tdual_fire(")
    assert "return -2;" in fire[i_guard:fire.index("i1pro2_cq_tdual_fire(")]
    b = src.index("static void ts_dual_after_cal(")
    cal = src[b:src.index("\n}\n", b)]
    assert cal.count("i1pro2_cq_dual_tile_save(") == 1
    k = cal.index("if ((why = cq_dual_check(&ts_dd.cal)) == NULL) {")
    block = cal[k:cal.index("}", k)]
    assert "i1pro2_cq_dual_tile_save(" in block
