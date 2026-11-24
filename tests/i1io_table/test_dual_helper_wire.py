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
without a dual tile, none longer than the cap of 1,150 readings (below the recorded UV-LED passes), none
from an original i1Pro or an i1Pro 2 without a UV LED.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from tests.test_i1pro3_lights_modes import _build_and_run

ROOT = Path(__file__).resolve().parents[2]

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


# ---- 2026-11-24: the kept dual tile, taken up by a NEW process (every table row's reader)
#
# The table owner's dual tries of 23 Nov (4.3.58) were all refused at row 1 with
# dual_calibration_not_kept: the calibration's process kept the tile, and every row reader, a
# fresh process, found "none" 2 ms after it opened. The restore compared the integration in
# clocks of m->intclkp, which an i1Pro 2 sets only when a reading is triggered; a fresh reader
# has triggered nothing, so the clock was 0 and every kept tile was refused. The old test above
# keeps and takes up the tile in ONE process, after tile() had triggered: it could not see it.
# "keep" keeps the tile, then runs the test program AGAIN, once per variant, as an opened
# i1Pro 2 that has triggered nothing (intclkp 0, intclkp2 36 us as init sets it).

def test_a_fresh_reader_takes_up_the_tile_the_calibration_kept(trace):
    keep = _scn(trace, "keep")
    assert "SAVED 1" in keep and "END" in keep
    lines = _scn(trace, "fresh_same")
    assert "RESTORE 1 uv_clocks=139" in lines
    assert "WHY kept | lamp 139 / uv 139 clocks" in lines
    assert not [ln for ln in trace.splitlines() if "FRESH-PROCESS-FAILED" in ln]


def test_the_fresh_reader_then_reads_the_recorded_dual_row(trace):
    """the row that 4.3.58 refused before anything moved: now the recorded bytes, the same as
    the in-process row above, and nothing before them (the restore reads only a file)"""
    lines = _scn(trace, "fresh_same")
    assert _wire(lines) == _wire(_scn(trace, "row"))
    i = lines.index("STEP lights_off")
    assert not _wire(lines[:i])
    assert [ln for ln in lines if ln.startswith("READY")] == [
        "READY lamp 1 wait=0 why=-", "READY uv 1 wait=0 why=-"]


@pytest.mark.parametrize("scn, why, detail", [
    ("fresh_int", "other_integration", "kept lamp 139 / uv 139 clocks, now 140"),
    ("fresh_date", "other_white_date", "kept for the white of "),
    ("fresh_white", "other_white", "white checksum kept "),
    ("fresh_scan", "other_scan", "kept scan=1, now scan=0"),
    ("fresh_none", "no_file", "no dual calibration was kept for this mode"),
])
def test_a_fresh_reader_still_refuses_a_tile_of_another_white(trace, scn, why, detail):
    """as strict as before: another integration, white date, white reading or mode, or no
    kept tile at all, and nothing is taken up, nothing reaches the wire, and the reason says
    which and with what values"""
    lines = _scn(trace, scn)
    assert "RESTORE 0 uv_clocks=-1" in lines
    w = [ln for ln in lines if ln.startswith("WHY ")]
    assert len(w) == 1 and w[0].startswith(f"WHY {why} | {detail}"), w
    assert not [x for x in _wire(lines) if x[1] in ("d4", "d8", "c9")]
    assert any(ln.startswith("READY lamp -1") and "no dual calibration" in ln for ln in lines)


def test_the_restore_matches_in_the_clock_a_fresh_process_knows():
    """the clock is the i1Pro 2's own (intclkp2, set when it is opened), not intclkp (set only
    by a trigger); the integration is still compared, in clocks, for both passes"""
    src = (ROOT / "native" / "instlib" / "cq_i1pro2_dual.h").read_text(encoding="utf-8")
    body = src[src.index("int i1pro2_cq_dual_tile_restore(void *pp"):]
    body = body[:body.index("\n}\n")]
    assert "clkp = m->intclkp2 > 0.0 ? m->intclkp2 : m->intclkp;" in body
    assert "s->inttime / clkp" in body and "s->inttime / m->intclkp" not in body
    assert "uc != clk || lc != clk" in body
    for check in ("mode != m->mmode", "cf != (long long)s->cfdate", "ms != s->scan",
                  "sum != (now_sum = cq_tdual_white_sum(m, s))"):
        assert check in body, check


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


def test_one_fire_per_yes_and_a_later_no_clears_the_yes(trace):
    """Re-review 2026-11-19 (planted faults Q5, Q6 passed every test before): the driver's
    second line fires a pass ONCE per ready check that said yes, and a ready check that says
    no afterwards takes the earlier yes back."""
    lines = _scn(trace, "onceper")
    fires = [ln for ln in lines if ln.startswith("FIRE")]
    assert len(fires) == 3, lines
    assert fires[0].startswith("FIRE rc=0")
    assert fires[1].startswith("FIRE rc=-1") and "lit_sent=0 dark_sent=0" in fires[1]
    assert fires[2].startswith("FIRE rc=-1") and "lit_sent=0 dark_sent=0" in fires[2]
    readies = [ln for ln in lines if ln.startswith("READY")]
    assert readies[0].startswith("READY lamp 1") and readies[1].startswith("READY lamp 1")
    assert readies[2].startswith("READY lamp -1")
    assert [x for x in _wire(lines) if x[1] == "d4" and x[2] == REC_LAMP] == [
        ("CTL", "d4", REC_LAMP)]


def test_a_calibration_voids_an_earlier_yes_and_an_earlier_lamp_pass(trace):
    """4.3.48 re-review NOTE-B: after a calibration (i1pro2_cq_tdual_disarm, called by the
    helper's tscan_calibrate), a ready "yes" given before it fires nothing, and a UV pass needs
    a lamp pass of its own after it."""
    lines = _scn(trace, "calreset")
    fires = [ln for ln in lines if ln.startswith("FIRE")]
    assert len(fires) == 3, lines
    assert fires[0].startswith("FIRE rc=-1") and "lit_sent=0 dark_sent=0" in fires[0]
    assert fires[1].startswith("FIRE rc=0")
    assert fires[2].startswith("FIRE rc=-1") and "lit_sent=0 dark_sent=0" in fires[2]
    readies = [ln for ln in lines if ln.startswith("READY")]
    assert readies[2].startswith("READY uv -1") and "did not deliver" in readies[2], readies
    d4 = [x[2] for x in _wire(lines) if x[1] == "d4"]
    assert d4.count(REC_LAMP) == 1 and REC_UV not in d4, d4      # the one allowed lamp pass
    assert set(d4) <= {REC_LAMP, REC_DARK5}, d4


def test_the_helper_clears_the_armed_pass_at_a_calibration():
    """NOTE-B, the helper's side: the tscan_calibrate branch disarms (ts_dd.pass and the
    driver's state) before it calibrates."""
    from pathlib import Path
    src = (Path(__file__).resolve().parents[2] / "native/chartread_helper/chromiq_tablescan.c"
           ).read_text(encoding="utf-8")
    a = src.index("static void ts_dual_disarm(")
    body = src[a:src.index("\n}\n", a)]
    assert "ts_dd.pass = 0;" in body and "i1pro2_cq_tdual_disarm();" in body
    c = src.index('strstr(line, "\\"tscan_calibrate\\"")')
    branch = src[c:src.index("cq_handle_calibrate(", c)]
    assert "ts_dual_disarm();" in branch


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
