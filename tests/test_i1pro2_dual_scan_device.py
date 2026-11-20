"""The i1Pro 2 dual scan's instrument part (step 2, 2026-11-18): what the
REAL vendored driver sends to an i1Pro 2, on the fake USB layer
(native/chartread_helper/tests/i1pro2_dual_test.c), held against the shape
of X-Rite i1Profiler's recorded dual sessions (tests/data/
i1pro2_dual_wire_shape.json: codes, flags, clocks and counts only).

No instrument is opened; the readings' processing is skipped in this trace
(the wire is the driver's). What stays unproven without hardware is listed in
docs/design/i1pro2_dual_scan.md section 7.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from tests.test_i1pro3_lights_modes import _build_and_run

ROOT = Path(__file__).resolve().parent.parent
INSTLIB = ROOT / "native" / "instlib"
HELPER = ROOT / "native" / "chartread_helper"
SHAPE = json.loads((ROOT / "tests" / "data" / "i1pro2_dual_wire_shape.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def trace(tmp_path_factory) -> str:
    return _build_and_run(tmp_path_factory, "i1pro2_dual_test")


def _lines(text: str, scn: str) -> "list[str]":
    return [ln.split(" ", 1)[1] for ln in text.splitlines() if ln.startswith(scn + " ")]


def _requests(text: str, scn: str) -> "list[dict]":
    """Every control request of a scenario, triggers decoded."""
    out = []
    for ln in _lines(text, scn):
        m = re.match(r"CTL ([0-9a-f]{2}) (\S+)", ln)
        if not m:
            continue
        req, data = m.group(1), m.group(2)
        d = {"req": "0x" + req.upper()}
        if req == "d4" and len(data) == 28:
            b = bytes.fromhex(data)
            d.update(intclocks=int.from_bytes(b[0:4], "big"), lampclocks=int.from_bytes(b[4:8], "big"),
                     nummeas=int.from_bytes(b[8:12], "big"), flags=int.from_bytes(b[12:14], "big"))
        out.append(d)
    return out


def _value(text: str, scn: str, key: str) -> str:
    return next(ln for ln in _lines(text, scn) if ln.startswith(key))


def test_a_single_scan_sends_exactly_what_it_sent_before(trace):
    """The option on but no reading armed: the same requests as without it,
    byte for byte (the hooks are no-ops). Lamp scans keep 0x0101."""
    a = [ln for ln in _lines(trace, "single") if ln.startswith("CTL")]
    b = [ln for ln in _lines(trace, "single-on") if ln.startswith("CTL")]
    assert a == b and a
    assert [r["flags"] for r in _requests(trace, "single")] == [0x0000, 0x0101]


def test_a_the_dual_calibration_is_the_recorded_tail(trace):
    reqs = _requests(trace, "tile")
    want = SHAPE["dual_calibration_tail"]["after_the_white"]
    assert [r["req"] for r in reqs] == [w["req"] for w in want]
    dark, uv = reqs[0], reqs[1]
    assert (dark["flags"], dark["nummeas"], dark["lampclocks"]) == (0x0000, 10, 0)
    assert (uv["flags"], uv["nummeas"]) == (0x0200, 5)
    assert uv["intclocks"] == dark["intclocks"] == 139           # the white's own exposure
    assert uv["lampclocks"] == 41                                # as recorded (safety review, M3)
    t = _value(trace, "tile", "TILE")
    assert "ev 0 ok 1 lamp_clocks 139 uv_clocks 139" in t and "uv_en 0" in t


def test_b_a_dual_spot_is_one_unit_lamp_then_uv_then_volts(trace):
    reqs = _requests(trace, "spot")
    assert [(r["req"], r.get("flags")) for r in reqs] == [
        ("0xD4", 0x0000), ("0xD4", 0x0100), ("0xD4", 0x0000), ("0xD4", 0x0200), ("0xD8", None)]
    assert {r["intclocks"] for r in reqs if "intclocks" in r} == {517}   # calibration = reading
    assert reqs[3]["lampclocks"] == 41                           # as recorded, not the spot lamp's
    assert reqs[2]["nummeas"] == reqs[3]["nummeas"]
    s = _value(trace, "spot", "SPOTUV")
    assert "ev 0 n 1 clocks 517 triggers 1" in s and "uv_en 0 lit 0" in s


def test_c_a_hand_strip_is_two_passes_in_one_ruler_stream(trace):
    reqs = _requests(trace, "strip")
    shape = SHAPE["dual_strip_by_hand"]["per_strip"]
    assert [(r["req"], r.get("flags")) for r in reqs] == [
        (w["req"], int(w["flags"], 16) if "flags" in w else None) for w in shape]
    lamp, uv = reqs[1], reqs[3]
    assert lamp["intclocks"] == uv["intclocks"] == 139
    assert uv["lampclocks"] == 41                                # as recorded, not the scan lamp's 102
    assert "reader running count 40" in _value(trace, "strip", "AFTER-LAMP")   # the stream runs on
    assert "uv_en 1" in _value(trace, "strip", "ARMED-UV")
    assert "uv_en 0 lit 0" in _value(trace, "strip", "AFTER-UV")
    assert "TAKEUV 1 n 38 triggers 1" in _value(trace, "strip", "TAKEUV")
    r = _value(trace, "strip", "RULER")
    assert "got 1 valid 1 ended 1 readings 38 clocks 139" in r          # ended by a short read
    p = _value(trace, "strip", "POSITIONS")
    assert p.startswith("POSITIONS 1") and "rising 1" in p and "falling 1" in p


def test_d_the_uv_led_is_off_on_every_way_out(trace):
    """A paired UV trigger (0x0209) that fails on the USB: the helper disarms
    on every way out, the driver's UV switch is off, the next strip's lamp
    pass is a plain lamp scan (no "ruler start" over the stream still
    drained) and its UV pass may not be asked for (safety review, M2)."""
    reqs = _requests(trace, "uv-error")
    assert [r["flags"] for r in reqs if r["req"] == "0xD4"] == [0x0000, 0x0105, 0x0209, 0x0101]
    assert "READY-AFTER-LAMP 1" in _value(trace, "uv-error", "READY-AFTER-LAMP")
    assert "uv_en 0 lit 0" in _value(trace, "uv-error", "AFTER")
    assert _value(trace, "uv-error", "READY ") == "READY 0"
    # exactly one UV-LED trigger per armed reading, and none anywhere else
    for scn, n in (("single", 0), ("single-on", 0), ("tile", 1), ("spot", 1), ("strip", 1), ("uv-error", 1),
                   ("uv-unpaired", 0)):
        assert sum(1 for q in _requests(trace, scn) if q.get("flags", 0) & 0x0300 == 0x0200) == n, scn


def test_d2_a_uv_pass_without_its_lamp_pass_is_never_sent(trace):
    """Safety review 2026-11-18, M2: the two ways to an unrecorded 0x0201 (UV scan without
    "ruler end"): the lamp pass's trigger failed, or the previous UV pass was abandoned (Esc)
    and the next lamp pass got no "ruler start". The UV pass is then not ready (the helper does
    not ask for it), and a UV trigger forced anyway is refused by the driver before anything is
    sent: I1PRO_INT_ILLEGALMODE (0x57), no 0xD4 with the UV flag on the wire."""
    reqs = [r for r in _requests(trace, "uv-unpaired") if r["req"] == "0xD4"]
    assert [r["flags"] for r in reqs] == [0x0000, 0x0105, 0x0000, 0x0105, 0x0000, 0x0101]
    v = {k: _value(trace, "uv-unpaired", k) for k in ("READY-1", "READY-2a", "READY-2b",
                                                       "FORCED-1", "FORCED-2", "AFTER-1", "AFTER-2")}
    assert v["READY-1"] == "READY-1 0" and v["READY-2b"] == "READY-2b 0"
    assert v["READY-2a"] == "READY-2a 1"           # the good lamp pass: its UV pass may come
    assert v["FORCED-1"] == "FORCED-1 87" and v["FORCED-2"] == "FORCED-2 87"
    assert "uv_en 0 lit 0" in v["AFTER-1"] and "uv_en 0 lit 0" in v["AFTER-2"]


def test_d3_a_uv_pass_over_4000_readings_is_refused_whole(trace):
    """Safety review 2026-11-18, S3: a UV pass longer than 4000 readings (about 20 s) used to be
    cut to its FIRST 4000 while the ruler positions came from the stream's LAST ones; now it is
    refused whole (the helper says uv_pass_too_long: move a little faster)."""
    t = [ln for ln in _lines(trace, "uv-too-long") if ln.startswith("TAKE")]
    assert t == ["TAKE 1 n 4000 nread 4000", "TAKE 0 n 0 nread 4001"]


def test_h_a_command_held_during_the_uv_wait_sends_nothing_and_m1_m2_go_on(trace):
    """4.3.49: the wait for the UV pass left by a command and armed again (the helper holds the
    command): no request for the held wait, the UV pass is the recorded 0x0209 and ends the
    stream, and the next strip's lamp pass starts its own (0x0105), its UV pass may come."""
    reqs = [r for r in _requests(trace, "uv-held") if r["req"] == "0xD4"]
    assert [r["flags"] for r in reqs] == [0x0000, 0x0105, 0x0000, 0x0209, 0x0000, 0x0105]
    assert reqs[3]["lampclocks"] == 41
    assert _value(trace, "uv-held", "READY-HELD") == "READY-HELD 1 uv_en 0 lit 0"
    assert _value(trace, "uv-held", "RULER") == "RULER got 1 ended 1 reader stopped"
    assert _value(trace, "uv-held", "READY-NEXT") == "READY-NEXT 1"
    lines = _lines(trace, "uv-held")
    held = lines.index("STEP uv-wait-left-by-a-command")
    assert lines[held + 1].startswith("READY-HELD"), "nothing on the wire for the held wait"


def test_i_a_strip_after_an_unusable_calibration_is_a_plain_single_scan(trace):
    """4.3.49: no ruler stream, no UV flag: exactly the single scan's requests."""
    a = [ln for ln in _lines(trace, "single") if ln.startswith("CTL")]
    b = [ln for ln in _lines(trace, "uncal") if ln.startswith("CTL")]
    assert a == b and a
    assert _value(trace, "uncal", "AFTER") == "AFTER reader stopped ready 0 uv_en 0"


def test_e_no_request_beyond_triggers_and_the_volts(trace):
    """No EEPROM write (0xC3), no read of it, no indicator program (0xD6), no
    0xD7, no bulk write: i1Profiler's usage log and light programs are not
    sent. Only 0xD4 and 0xD8."""
    for scn in ("single-on", "tile", "spot", "strip", "uv-error", "uv-unpaired", "uv-too-long",
                "uv-held", "uncal"):
        reqs = {r["req"] for r in _requests(trace, scn)}
        assert reqs <= {"0xD4", "0xD8"}, (scn, reqs)
        assert not [ln for ln in _lines(trace, scn) if ln.startswith("WR ")], scn


def test_g_where_it_is_not_offered_it_says_why(trace):
    codes = [int(ln.split()[1]) for ln in _lines(trace, "refused") if ln.startswith("OPTIONS")]
    # no UV LED, no tables, high resolution, an i1Pro (Rev A-D)
    assert codes == [2, 3, 4, 1]


# ----------------------------------------------------------------- the source

def _code(text: str) -> str:
    return re.sub(r"/\*.*?\*/", "", text, flags=re.S)


def test_the_driver_part_sends_nothing_of_its_own():
    """cq_i1pro2_dual.h sends through ArgyllCMS's own functions only: no USB
    call, no EEPROM write, no light program of its own."""
    src = _code((INSTLIB / "cq_i1pro2_dual.h").read_text(encoding="utf-8"))
    for never in ("usb_control(", "usb_write(", "usb_read(", "writeEEProm", "update_log",
                  "0xD6", "0xd6", "0xC3", "0xc3", "0xD7", "0xd7", "indLEDseq"):
        assert never not in src, never
    for own in ("i1pro_trigger_one_measure(", "i1pro_readmeasurement(", "i1pro_dark_measure_1(",
                "i1pro2_getUVvolts(", "i1pro_conv2XYZ(", "i1pro_absraw_to_abswav("):
        assert own in src, own
    # the tables are read from the image the driver read at open, never written
    assert "get_doubles(m->data, &na, 0x2f77)" in src and "get_doubles(m->data, &nd, 0x2f76)" in src


def test_every_hook_is_a_no_op_unless_the_dual_scan_is_on():
    src = _code((INSTLIB / "cq_i1pro2_dual.h").read_text(encoding="utf-8"))
    i = src.index("static cq_dual_state *cq_dual_s(void *pp) {")
    assert "!m->cq_dual_on" in src[i:src.index("\n}\n", i)]
    for fn in ("i1pro2_cq_dual_lamp_delay(", "i1pro2_cq_dual_ruler_bits(", "i1pro2_cq_dual_readings(",
               "i1pro2_cq_dual_keep_lamp(", "i1pro2_cq_dual_ruler_phase("):
        j = src.index(fn)
        body = src[j:src.index("\n}\n", j)]
        assert "cq_dual_s(pp)" in body, fn


def test_the_vendor_script_reapplies_the_hooks():
    text = (ROOT / "scripts" / "vendor_instlib.py").read_text(encoding="utf-8")
    assert "I1PRO_IMP_C_TSCAN + I1PRO_IMP_C_DUAL" in text and "I1PRO_IMP_H_TOL + I1PRO_IMP_H_DUAL" in text
    assert '#include \\"cq_i1pro2_dual.h\\"' in text
    prov = (INSTLIB / "PROVENANCE.md").read_text(encoding="utf-8")
    assert "the i1Pro 2 dual scan" in prov and "No EEPROM write" in prov


def test_the_helper_reports_the_device_word_and_the_new_build():
    src = (HELPER / "chromiq_chartread.c").read_text(encoding="utf-8", errors="replace")
    assert '\\"i1pro2_dual_conditions\\",\\"i1pro2_dual_scan\\",' in src
    h = (HELPER / "chromiq_ext.h").read_text(encoding="utf-8")
    # 2026-11-20a (4.3.52): + the lights' quiet time and the dual scan's blue; 20b: + the
    # blue's own quiet time (fix round); 20c: that floor only before the strip's return pass;
    # 20d (4.3.53): the waits as values the app passes
    assert "chromiq-chartread 2026-11-20e " in h and "+i1pro2-dual-device+i1pro2-dual-safety+" in h


def test_a_failed_pass_is_read_again_and_a_session_failure_keeps_m0():
    """chromiq_dualdev.c: a failing PASS makes the strip (or patch) a misread
    (read again), anything else ends M1 / M2 for the session and M0 goes on;
    the UV switch is disarmed right after the UV read whatever it returned."""
    src = _code((HELPER / "chromiq_dualdev.c").read_text(encoding="utf-8"))
    i = src.index("static int cq_dd_pass_level(")
    body = src[i:src.index("\n}\n", i)]
    for w in ("uv_pass_short", "uv_pass_stalled", "uv_pass_too_fast", "uv_pass_misaligned",
              "uv_pass_missing", "lamp"):
        assert f'"{w}"' in body
    for w in ("no_dual_calibration", "calibration_mismatch", "uv_tile_dark", "dual_needs_ruler"):
        assert f'"{w}"' not in body
    j = src.index("rv2 = it->read_strip(")
    assert src.index("i1pro2_cq_dual_arm(it, CQ_DUAL_PHASE_OFF);", j) < src.index("(void)i1pro2_cq_dual_take_uv(", j)


# ------------------------------------------- the safety review's fixes (2026-11-18, helper side)

def test_m2_the_uv_pass_is_asked_for_only_when_its_trigger_can_carry_ruler_end():
    """cq_dd_strip asks the driver (i1pro2_cq_dual_uv_pass_ready) BEFORE it announces or arms
    the UV pass; when it may not come, M1 / M2 end for the session (M0 goes on) and nothing more
    is read for the strip."""
    src = _code((HELPER / "chromiq_dualdev.c").read_text(encoding="utf-8"))
    i = src.index("static void cq_dd_strip(")
    body = src[i:src.index("\n}\n", i)]
    ready = body.index("if (!i1pro2_cq_dual_uv_pass_ready(it)) {")
    assert ready < body.index('\\"event\\":\\"dual_pass\\"') < body.index("i1pro2_cq_dual_arm(it, CQ_DUAL_PHASE_UV);")
    block = body[ready:body.index("return;", ready)]
    for w in ("i1pro2_cq_dual_arm(it, CQ_DUAL_PHASE_OFF);", "cq_dd.on = 0;",
              'cq_cond_lose("dual_dual_needs_ruler");'):
        assert w in block, w
    # the driver side: the same rule gives "ruler end", and the gate refuses anything else
    drv = _code((INSTLIB / "cq_i1pro2_dual.h").read_text(encoding="utf-8"))
    j = drv.index("int i1pro2_cq_dual_ruler_bits(")
    assert "cq_dual_uv_ready(p, st)" in drv[j:drv.index("\n}\n", j)]
    c = (INSTLIB / "i1pro_imp.c").read_text(encoding="utf-8", errors="replace")
    k = c.index("measmodeflags2 |= i1pro2_cq_dual_ruler_bits(p, mmodif);")
    assert c.index("if (i1pro2_cq_dual_form_refused(p, measmodeflags2, lampclocks))", k) \
        < c.index("m->c_measmodeflags2 = measmodeflags2;", k)       # before anything is sent


def test_m3_the_uv_lamp_clocks_are_the_recorded_41_and_never_touch_the_lamp_time():
    h = (INSTLIB / "cq_dual.h").read_text(encoding="utf-8")
    assert re.search(r"#define CQ_DUAL_UV_LAMPCLOCKS 41\b", h)
    c = (INSTLIB / "i1pro_imp.c").read_text(encoding="utf-8", errors="replace")
    i = c.index("\tif (s->reflective && (mmodif & 0x10)) {\n\t\tdlampclocks = floor(s->lamptime")
    block = c[i:c.index("\tif (nummeas > 65535)", i)]
    # ArgyllCMS's own lamp branch is upstream's again; the hook sits only where it gives 0
    assert "i1pro2_cq_dual_lamp_delay" not in block.split("} else {")[0]
    assert "lampclocks = i1pro2_cq_dual_lamp_delay(p, mmodif);" in block.split("} else {")[1]


def test_s3_a_too_long_uv_pass_is_its_own_pass_failure():
    src = _code((HELPER / "chromiq_dualdev.c").read_text(encoding="utf-8"))
    assert "u.nread > CQ_DUAL_MAX_UV_READINGS" in src and '"uv_pass_too_long"' in src


def test_every_reason_the_device_side_gives_has_a_sentence():
    from workflow.dual_scan.reasons import REASONS
    internal = {"lamp", "record", "memory", "conversion", "checked", "pairing_not_checked", "strip",
                "spot", "uv", "scan", "true", "false", "STRIP", "dual_dual_needs_ruler",
                # 4.3.49: the names of the commands held while the UV pass is due
                # (event dual_pass_held), not reasons
                "goto", "file_as", "turn", "next_unread", "back", "forward"}
    text = (HELPER / "chromiq_dualdev.c").read_text(encoding="utf-8")
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    ids = set(re.findall(r'"([a-z][a-z0-9_]+)"', text)) - internal
    ids |= set(re.findall(r'return "([a-z_]+)"', (HELPER / "chromiq_dualscan.c").read_text(encoding="utf-8")))
    missing = sorted(i for i in ids if i not in REASONS and not i.startswith("dual_") and i != "ok")
    assert not missing, missing


def test_s2_every_pass_refusal_says_what_the_instrument_path_does():
    """Safety review S2: on a hand strip a failed pass makes the strip a misread and BOTH passes
    are read again (provisional for the first Beta, spec section 0 (a)), so no pass refusal may
    say "the first pass is kept"; each says both passes come again."""
    from workflow.dual_scan.reasons import REASONS
    src = _code((HELPER / "chromiq_dualdev.c").read_text(encoding="utf-8"))
    i = src.index("static int cq_dd_pass_level(")
    ids = set(re.findall(r'"([a-z_]+)"', src[i:src.index("\n}\n", i)])) - {"lamp"}
    assert {"uv_pass_wrong_strip", "uv_pass_too_long", "uv_spot_failed"} <= ids
    for rid in ids:
        text = REASONS[rid]
        assert "first pass is kept" not in text, rid
        if rid == "uv_spot_failed":
            assert "both readings are made again" in text
        elif rid != "no_ruler":
            assert "both passes" in text and "the first pass is read again too" in text, rid
