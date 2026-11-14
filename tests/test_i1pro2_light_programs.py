"""The i1Pro 2 lights Beta's three newer programs (PULSE, GREEN2, RED2;
2026-11-13), in native/instlib/cq_i1pro2_programs.h.

Nobody on the project owns an i1Pro 2. What may be sent to one is limited to
byte sequences X-Rite's i1Profiler 3.8.6 was recorded sending to a user's own
i1Pro 2 (hand-held, Windows; ChromIQ-work 2026-11-13_pharmacist_recording,
RESULTS.md section 3). This pins each program to that recording by sha256,
decodes it independently of the C code, and checks the facts the design
relies on: PULSE is Argyll's own `b3`; GREEN2 and RED2 differ only in the
colour; all three end in the same forever white pulse; the only colours are
the recorded ones; and nothing in the driver can send anything else.
"""
from __future__ import annotations

import hashlib
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
INSTLIB = ROOT / "native" / "instlib"

#: sha256 of the bytes as recorded (RESULTS.md section 3 gives the first 12
#: hex digits: a3422646626c / b1e84c7bd4d0 / 813a0add3948).
RECORDED_SHA256 = {
    "cq_lights_seq_pulse":
        "a3422646626c1117e7cbecc80e1de3b73f1759440f95e4156b403c38115f6c53",
    "cq_lights_seq_green2":
        "b1e84c7bd4d09e18591a22162630a2e8ecbed8b8956af0fce4ed3c5fa47479ba",
    "cq_lights_seq_red2":
        "813a0add3948ef6183105f9351e7808d8d625f0ee520eb991e9a0d6ef9374ea6",
}
SIZES = {"cq_lights_seq_pulse": 2306, "cq_lights_seq_green2": 2990,
         "cq_lights_seq_red2": 2990}


def _c_array(text: str, name: str) -> bytes:
    m = re.search(r"static const unsigned char " + name +
                  r"\[(\d+)\] = \{(.*?)\};", text, re.S)
    assert m, f"{name} not found"
    body = re.sub(r"/\*.*?\*/", "", m.group(2), flags=re.S)
    data = bytes(int(x, 16) for x in re.findall(r"0x([0-9a-fA-F]{2})", body))
    assert len(data) == int(m.group(1)), f"{name}: declared size differs"
    return data


def _header() -> str:
    return (INSTLIB / "cq_i1pro2_programs.h").read_text(encoding="utf-8")


def _decode(seq: bytes) -> "list[tuple[int, list[tuple[int, int]]]]":
    """Argyll's format (comment above i1pro2_indLEDseq): u32 block count;
    per block u32 byte count (repeat word included), u32 repeat, then 3-byte
    steps (LED mask, u16 clocks). Raises on anything inconsistent."""
    def u32(i):
        return int.from_bytes(seq[i:i + 4], "big")
    n, i, blocks = u32(0), 4, []
    for _ in range(n):
        nbytes, rep = u32(i), u32(i + 4)
        raw = seq[i + 8:i + 4 + nbytes]
        assert (nbytes - 4) % 3 == 0 and len(raw) == nbytes - 4
        blocks.append((rep, [(raw[k], int.from_bytes(raw[k + 1:k + 3], "big"))
                             for k in range(0, len(raw), 3)]))
        i += 4 + nbytes
    assert i == len(seq), "trailing bytes"
    return blocks


@pytest.mark.parametrize("name", sorted(RECORDED_SHA256))
def test_each_program_is_the_recorded_bytes(name):
    data = _c_array(_header(), name)
    assert len(data) == SIZES[name]
    assert hashlib.sha256(data).hexdigest() == RECORDED_SHA256[name]


def test_pulse_is_argylls_own_b3():
    text = (INSTLIB / "i1pro_imp.c").read_text(encoding="utf-8",
                                               errors="surrogateescape")
    i = text.index("/* Makes it pulsing white */")
    m = re.search(r"unsigned char b3\[\] = \{(.*?)\};", text[i:], re.S)
    b3 = bytes(int(x, 16) for x in re.findall(r"0x([0-9a-fA-F]{2})", m.group(1)))
    assert b3 == _c_array(_header(), "cq_lights_seq_pulse")


def test_what_each_program_shows():
    h = _header()
    pulse = _decode(_c_array(h, "cq_lights_seq_pulse"))
    green = _decode(_c_array(h, "cq_lights_seq_green2"))
    red = _decode(_c_array(h, "cq_lights_seq_red2"))
    # PULSE: about 1 s dark once, then white (all six LEDs, 0x3f) forever
    assert [r for r, _ in pulse] == [1, 0xFFFFFFFF]
    assert {m for m, _ in pulse[0][1]} == {0x00}
    assert {m for m, _ in pulse[1][1]} == {0x00, 0x3F}
    # GREEN2 / RED2: a coloured pulse played twice, then PULSE's forever block
    for prog, mask in ((green, 0x12), (red, 0x09)):
        assert [r for r, _ in prog] == [2, 0xFFFFFFFF]
        assert {m for m, _ in prog[0][1]} == {0x00, mask}
        assert prog[1] == pulse[1]
    # the same shape, only the colour differs
    assert [(m != 0, c) for m, c in green[0][1]] == [(m != 0, c) for m, c in red[0][1]]


def test_no_unrecorded_colour_and_never_forever_colour():
    """Masks: 0x3f white (recorded at open), 0x12 green, 0x09 red. No blue,
    no single side; a colour never repeats forever (only white does)."""
    h = _header()
    for name in RECORDED_SHA256:
        for rep, steps in _decode(_c_array(h, name)):
            masks = {m for m, _ in steps}
            assert masks <= {0x00, 0x3F, 0x12, 0x09}, name
            if rep == 0xFFFFFFFF:
                assert masks <= {0x00, 0x3F}, name


def test_the_header_is_included_once_and_only_by_the_driver():
    hits = [p.name for p in list(INSTLIB.glob("*.c")) + list(INSTLIB.glob("*.h"))
            + list((ROOT / "native" / "chartread_helper").rglob("*.[ch]"))
            if '#include "cq_i1pro2_programs.h"' in p.read_text(
                encoding="utf-8", errors="surrogateescape")]
    assert hits == ["i1pro_imp.c"]


def test_the_send_function_knows_exactly_six_programs():
    text = (INSTLIB / "i1pro_imp.c").read_text(encoding="utf-8",
                                               errors="surrogateescape")
    block = text[text.index("static void cq_lights_send(i1pro *p, int which"):]
    block = block[:block.index("\n}\n")]
    used = set(re.findall(r"seq = (cq_lights_seq_\w+);", block))
    assert used == {"cq_lights_seq_white", "cq_lights_seq_off_slow",
                    "cq_lights_seq_off_now", "cq_lights_seq_pulse",
                    "cq_lights_seq_green2", "cq_lights_seq_red2"}
    # one request (0xD6) and its bulk write on 0x03, nothing else
    assert block.count("usb_control(") == 1 and block.count("usb_write(") == 1
    assert "0xD6" in block and "0x03" in block


def test_no_firmware_condition_beyond_argylls_own():
    """2026-11-14: no exact-firmware gate (4.3.33 has none, Argyll's light code
    has none). Below firmware 600 Argyll runs the instrument as a rev A-D
    (dtype instI1Pro), which every entry refuses."""
    text = (INSTLIB / "i1pro_imp.c").read_text(encoding="utf-8",
                                               errors="surrogateescape")
    assert "CQ_LIGHTS_RECORDED_FW" not in text
    begin = text[text.index("int i1pro2_cq_lights_begin(void *pp) {"):]
    begin = begin[:begin.index("\n}\n")]
    assert "fwrev" not in begin
    assert "if (p->dtype == instI1Pro2 && m->fwrev < 600) {" in text
