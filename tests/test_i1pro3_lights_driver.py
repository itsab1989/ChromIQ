"""The i1Pro 3 indicator lights (Preferences > Beta, 2026-11-13): the driver.

The same Beta as the i1Pro 2's (tests/test_i1pro2_lights_driver.py), for the
i1Pro 3 from one user's recording of X-Rite's i1Profiler 3.8.5
(ChromIQ-work/2026-11-13_i1pro2_lights/LIGHTS_GENERATIONS.md). Proved without
hardware:

* the four sequences it can send: Argyll's own off `00` (unpatched Argyll sends
  it at every open) and three patterns that are, byte for byte, what the
  recording shows; the 0x29 request carries a little-endian length as there;
* the patch adds no other request: no 0x3B, no memory write (0x23), no read;
  Argyll's own i1pro3_indLEDseq stays as it is;
* the off guard sits at the top of i1pro3_do_measure, before its 0x3B and its
  trigger, and every measurement of the driver passes there;
* the real driver on a fake USB layer: with the option off the i1Pro 3 puts
  exactly what Argyll's own unpatched driver puts on the wire; with it on:
  patterns only after a measurement returned, off before every measurement,
  the gates, the failure rule, the close, a pending trigger.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tests.test_i1pro2_lights_driver import (  # noqa: E402
    _added_lines, _scenario, _src, _vendor, _without_never_blocks,
    build_and_run)

#: What the recording shows on bulk OUT 0x02 after request 0x29
#: (ChromIQ-work/2026-11-13_i1pro2_lights/scratch/i1p3_timeline.txt).
RECORDED = {
    "ready": "01fa04120500",   # 8x, after i1Profiler's calibration readings
    "good": "0a1402120500",    # 33x, after every good scan and spot reading
    "bad": "061402120500",     # 4x, after scans rejected as incomplete
}
#: Argyll's own off (i1pro3_imp.c, i1pro3_indLEDoff), sent at every open.
ARGYLL_OFF = "00"

C_ARRAYS = {"ready": "cq3_lights_seq_ready", "good": "cq3_lights_seq_good",
            "bad": "cq3_lights_seq_bad", "off": "cq3_lights_seq_off"}


def _c_array(text: str, name: str) -> bytes:
    m = re.search(r"static const unsigned char " + name +
                  r"\[(\d+)\]\s*=\s*\{(.*?)\};", text, re.S)
    assert m, name
    data = bytes(int(x, 16) for x in re.findall(r"0x([0-9a-fA-F]{2})", m.group(2)))
    assert len(data) == int(m.group(1))
    return data


@pytest.mark.parametrize("which", sorted(RECORDED))
def test_each_pattern_is_the_recorded_bytes(which):
    assert _c_array(_src("i1pro3_imp.c"), C_ARRAYS[which]).hex() == RECORDED[which]


def test_the_off_is_argylls_own():
    text = _src("i1pro3_imp.c")
    assert _c_array(text, C_ARRAYS["off"]).hex() == ARGYLL_OFF
    argyll = text[text.index("i1pro3_indLEDoff(void *pp) {"):]
    argyll = argyll[:argyll.index("\n}\n")]
    assert "unsigned char seq[] = { 0x00 };" in argyll


def test_the_patterns_decode_as_white_green_red():
    """Argyll's format: 3-byte groups type, timing, count (0 = forever)."""
    for name, bytes_hex in RECORDED.items():
        b = bytes.fromhex(bytes_hex)
        groups = [b[i:i + 3] for i in range(0, len(b), 3)]
        assert groups[-1] == bytes.fromhex("120500"), name   # white, forever
        assert groups[0][2] != 0, name                        # first part ends
    assert bytes.fromhex(RECORDED["good"])[0] == 0x0a        # green pulse
    assert bytes.fromhex(RECORDED["bad"])[0] == 0x06         # red (recording)


def test_the_patch_adds_no_other_request():
    code = "\n".join(_added_lines("i1pro3_imp.c") + _added_lines("i1pro3.c")
                     + _added_lines("i1pro3_imp.h"))
    code = re.sub(r"/\*.*?\*/", "", code, flags=re.S)
    assert code.count("usb_control(") == 1 and code.count("usb_write(") == 1
    assert "i1p3cc_set_ind" in code
    assert "0x02, (unsigned char *)seq" in code
    for never in ("usb_read(", "0x23", "0x3B", "0x3b", "setscanstartind",
                  "i1p3cc_set_scan_ind", "EEProm", "i1pro3_indLEDseq",
                  "i1pro3_indLEDoff", "trigger_measure(", "i1p3cc_meas"):
        assert never not in code, never


def test_argylls_own_light_functions_are_unchanged_and_the_only_other_sender():
    live = _without_never_blocks(_src("i1pro3_imp.c"))
    assert len(re.findall(r"i1p3cc_set_ind\b", live)) == 3   # enum + Argyll + ours
    assert len(re.findall(r"\bi1pro3_indLEDoff\s*\(", live)) == 2   # def + init


def test_the_off_comes_first_in_every_measurement():
    text = _src("i1pro3_imp.c")
    body = text[text.index("i1pro3_code i1pro3_do_measure(\n"):]
    body = body[:body.index("\n}\n")]
    hook = body.index("i1pro3_cq_lights_measure(p);")
    for later in ("i1pro3_setscanstartind(", "i1pro3_trigger_measure(",
                  "i1pro3_settintmult(", "i1pro3_setledcurrents("):
        assert hook < body.index(later), later
    live = _without_never_blocks(text)
    # i1pro3_do_measure is the only caller of the trigger
    assert len(re.findall(r"\bi1pro3_trigger_measure\(p,", live)) == 1
    dl = text[text.index("void del_i1pro3imp(i1pro3 *p) {"):]
    dl = dl[:dl.index("\n}\n")]
    assert dl.index("i1pro3_cq_lights_end(p);") < dl.index("i1pro3_terminate_event(p)")
    assert dl.index("if (p->m != NULL) {") < dl.index("i1pro3_cq_lights_end(p);")


def test_patterns_follow_every_measure_and_calibrate_in_i1pro3_c():
    text = _src("i1pro3.c")
    for call, hook in (
            ("rv = i1pro3_imp_measure(p, vals, npatch, instClamp);\n",
             "i1pro3_cq_lights_after_read(p, rv);"),
            ("rv = i1pro3_imp_measure(p, val, 1, clamp);\n",
             "i1pro3_cq_lights_after_read(p, rv);"),
            ("rv = i1pro3_imp_calibrate(p, calt, calc, idtype, id);\n",
             "i1pro3_cq_lights_after_cal(p, rv);")):
        i = text.index(call) + len(call)
        assert text[i:].lstrip("\t").startswith(hook)
    assert text.count("i1pro3_cq_lights_") == 3


def test_every_entry_asks_dtype_first_and_the_sender_holds_the_lock():
    text = _src("i1pro3_imp.c")
    block = text[text.index("CHROMIQ PATCH: the i1Pro 3 indicator lights"):]
    helper = block[block.index("static i1pro3imp *cq3_lights_m(i1pro3 *p) {"):]
    helper = helper[:helper.index("\n}\n")]
    assert helper.index("p->dtype != instI1Pro3") < helper.index("p->m")
    for fn in ("void i1pro3_cq_lights_measure(void *pp) {",
               "static void cq3_lights_show(i1pro3 *p, int which) {",
               "void i1pro3_cq_lights_end(void *pp) {"):
        body = block[block.index(fn):]
        assert "cq3_lights_m(p)" in body[:body.index("\n}\n")], fn
    send = block[block.index("static void cq3_lights_send("):]
    send = send[:send.index("\n}\n")]
    assert send.index("amutex_lock(m->lock);") < send.index("usb_control(") \
        < send.index("usb_write(") < send.index("amutex_unlock(m->lock);")
    begin = block[block.index("int i1pro3_cq_lights_begin(void *pp) {"):]
    begin = begin[:begin.index("\n}\n")]
    for gate in ("p->dtype != instI1Pro3", "!p->inited", "I1PRO3_CAP_IND_LED"):
        assert gate in begin
    assert "cq3_lights_send" not in begin          # begin sends nothing


# ---------------------------------------------------------------------------
# The real driver on a fake USB layer
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def traces3(tmp_path_factory):
    return build_and_run(tmp_path_factory, "i1pro3_lights_test")


def _d29(lines):
    return [ln for ln in lines if ln.startswith(("CTL 29", "WR 02"))]


def _wire(lines):
    return [ln for ln in lines if ln.split(" ", 1)[0] in ("CTL", "WR", "RD")]


def _pat(seq_hex, tout):
    n = len(bytes.fromhex(seq_hex))
    return [f"CTL 29 {n:02x}000000 tout={tout}", f"WR 02 {seq_hex} tout={tout}"]


READY, GOOD, BAD = (_pat(RECORDED[k], "1.00") for k in ("ready", "good", "bad"))
OFF_MEASURE = _pat("00", "0.25")
OFF_CLOSE = _pat("00", "0.50")


def test_option_off_puts_on_the_wire_exactly_what_argyll_does(traces3):
    patched = _scenario(traces3["patched"], "off_i1pro3")
    upstream = _scenario(traces3["upstream"], "off_i1pro3")
    assert upstream and patched == upstream
    assert _d29(patched) == []


@pytest.mark.parametrize("scn", ["on_no_led_bit", "on_not_inited", "cross_dtype"])
def test_option_on_sends_nothing_to_anything_but_a_ready_i1pro3(traces3, scn):
    lines = _scenario(traces3["patched"], scn)
    assert lines and _d29(lines) == []
    assert "BEGIN 1" not in lines


def test_option_on_a_whole_session(traces3):
    lines = _scenario(traces3["patched"], "on_i1pro3")
    assert _d29(lines) == (READY          # after the calibration returned OK
                           + OFF_MEASURE + GOOD   # a reading
                           + OFF_MEASURE + BAD    # one the instrument could not take
                           + OFF_MEASURE)         # an aborted one: nothing after
    # nothing lights between the off and the end of its measurement
    w = _wire(lines)
    lit = False
    for ln in w:
        if ln.startswith("WR 02"):
            lit = ln.split()[2] != "00"
        elif ln.startswith(("CTL 3b", "CTL 27", "CTL 22")):
            assert not lit, ln
    # the off with the patched driver equals today's session minus the lights
    off = _wire(_scenario(traces3["patched"], "off_i1pro3"))
    assert [ln for ln in w if not ln.startswith(("CTL 29", "WR 02"))] == off


def test_a_failed_request_is_noted_once_and_ends_the_lights(traces3):
    lines = _scenario(traces3["patched"], "fail_off")
    assert [ln for ln in lines if ln.startswith("NOTE")] == ["NOTE seq=4 err=0x200"]
    assert _d29(lines) == READY + ["CTL 29 01000000 tout=0.25"]
    assert sum(ln.startswith("CTL 27") for ln in lines) == 5    # measuring went on


def test_the_end_paths(traces3):
    assert _d29(_scenario(traces3["patched"], "end_cmd")) == READY + OFF_CLOSE
    plus = _scenario(traces3["patched"], "close_lit_plus")
    assert "BEGIN 1" in plus and _d29(plus) == READY + OFF_CLOSE


def test_no_pattern_while_a_trigger_is_pending(traces3):
    lines = _scenario(traces3["patched"], "trigger_pending")
    i0 = lines.index("STEP trigger-held")
    i1 = lines.index("STEP trigger-released")
    assert _d29(lines[i0:i1]) == []
    assert any(ln.startswith("CTL 27") for ln in lines[i1:])
