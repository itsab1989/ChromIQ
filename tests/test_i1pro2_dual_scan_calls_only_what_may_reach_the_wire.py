"""The i1Pro 2 dual scan (step 2): an ALLOW-LIST of every function its new code calls.

Independent safety review, 2026-11-18. The existing pins
(tests/test_i1pro2_dual_scan_device.py) ban a list of words ("0xD7", "indLEDseq",
"usb_control(" ...) in cq_i1pro2_dual.h and watch the wire of the paths the fake-USB trace
runs. Planted in copies of the tree, three faults passed all of them:

* ``i1pro2_stop_ruler(p, 0)`` (request 0xD7) on the spot UV half's error path;
* ``i1pro2_indLEDoff(p)`` (request 0xD6 + a bulk write) on the tile reading's error path;
* ``p->set_opt(p, inst_opt_set_led_state, ...)`` in chromiq_dualdev.c (helper side, which no
  wire test runs).

ArgyllCMS's driver has many functions that send other requests, so a ban list cannot be
complete. This test turns it round: the dual scan's own C may call only the functions named
here, each of which sends nothing but 0xD4 / 0xD8 or nothing at all. A new call fails this test
until someone has looked at what it sends and added it on purpose.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DRIVER = ROOT / "native" / "instlib" / "cq_i1pro2_dual.h"
HELPER = ROOT / "native" / "chartread_helper" / "chromiq_dualdev.c"

_KEYWORDS = {"if", "for", "while", "switch", "return", "sizeof", "int"}
_LIBC = {"calloc", "malloc", "free", "memset", "memcpy", "floor", "strcmp"}

#: cq_i1pro2_dual.h: what each ArgyllCMS function sends (i1pro_imp.c)
DRIVER_MAY_CALL = _LIBC | {
    # requests: 0xD4 (trigger) and the 0x82 read of its readings, nothing else
    "i1pro_trigger_one_measure", "i1pro_readmeasurement", "i1pro_dark_measure_1",
    # request 0xD8 (read only)
    "i1pro2_getUVvolts",
    # arithmetic on readings already read: no USB
    "i1pro_dark_measure_2", "i1pro_sens_to_absraw", "i1pro_sub_absraw", "i1pro_absraw_to_abswav",
    "i1pro_conv2XYZ", "i1pro_comp_nummeas", "dmatrix", "free_dmatrix", "dvectorz", "free_dvector",
    "m->data->get_doubles",            # the EEPROM image read at open, in memory
    # the ruler check's switch: sets a flag, sends nothing (cq_ruler.h block)
    "i1pro2_cq_ruler_options",
    # its own functions
    "cq_dual_s", "cq_dual_volts", "cq_dual_uv_readings",
}

#: chromiq_dualdev.c (the helper side): the instrument only through the dual API and read_strip
HELPER_MAY_CALL = _LIBC | {
    "it->read_strip",                  # the UV pass: ArgyllCMS's own scan (0xD4 + reads)
    "i1pro2_cq_dual_options", "i1pro2_cq_dual_tile", "i1pro2_cq_dual_arm",
    "i1pro2_cq_dual_spot_uv", "i1pro2_cq_dual_take_uv", "i1pro2_cq_dual_take_lamp",
    "i1pro2_cq_dual_conv", "i1pro2_cq_dual_lamp_count", "i1pro2_cq_ruler_take",
    "i1pro2_cq_dual_uv_pass_ready",    # reads the driver's state, sends nothing (M2 fix)
    # arithmetic and output, no instrument
    "cq_dual_check", "cq_dual_cut", "cq_dual_patch", "cq_dual_positions", "cq_cx_from_ipatch",
    "cq_dual_pairing",                 # the pairing check (M1 fix), arithmetic only
    "cq_emit_raw", "cq_json_escape", "cq_ruler_rec_clear",
    # the conditions event "active: false" (chromiq_chartread.c); its only instrument call is
    # the i1Pro 3's own conditions switch, never reached for an i1Pro 2
    "cq_cond_lose",
}


def _calls(path: Path) -> "set[str]":
    t = path.read_text(encoding="utf-8", errors="replace")
    t = re.sub(r"/\*.*?\*/", "", t, flags=re.S)
    t = re.sub(r"//[^\n]*", "", t)
    t = re.sub(r'"(\\.|[^"\\])*"', '""', t)
    names = set(re.findall(r"([A-Za-z_]\w*(?:\s*->\s*[A-Za-z_]\w*)*)\s*\(", t))
    return {re.sub(r"\s+", "", n) for n in names} - _KEYWORDS


def _own(path: Path, prefix: "tuple[str, ...]") -> "set[str]":
    """Functions the file defines itself (their calls are checked by this same test)."""
    t = path.read_text(encoding="utf-8", errors="replace")
    return {m for m in re.findall(r"^(?:static\s+)?[A-Za-z_][\w \*]*?\b(\w+)\s*\(", t, flags=re.M)
            if m.startswith(prefix)}


def test_the_driver_part_calls_only_functions_that_send_d4_or_d8_or_nothing():
    own = _own(DRIVER, ("i1pro2_cq_dual_", "cq_dual_"))
    extra = _calls(DRIVER) - DRIVER_MAY_CALL - own
    assert not extra, (
        f"cq_i1pro2_dual.h calls {sorted(extra)}: find out what each sends to the instrument "
        "(i1pro_imp.c) before allowing it here; only 0xD4 and 0xD8 are recorded for the dual scan")


def test_the_helper_part_reaches_the_instrument_only_through_the_dual_api():
    own = _own(HELPER, ("cq_dd_",))
    extra = _calls(HELPER) - HELPER_MAY_CALL - own
    assert not extra, (
        f"chromiq_dualdev.c calls {sorted(extra)}: the helper side may reach the instrument only "
        "through the dual API and read_strip (no set_opt, no lights, no ruler stop)")


def test_the_allow_list_holds_no_function_that_sends_anything_else():
    """The allow-list itself: none of ArgyllCMS's senders of other requests is in it."""
    senders = {"i1pro2_indLEDseq", "i1pro2_indLEDoff", "i1pro2_stop_ruler", "i1pro_writeEEProm",
               "i1pro_update_log", "i1pro_readEEProm", "i1pro_setmcmode", "i1pro_reset",
               "i1pro_setmeasparams", "i1pro2_cq_lights_begin", "i1pro2_cq_lights_end",
               "i1pro2_cq_lights_trigger", "it->set_opt", "p->set_opt", "it->calibrate"}
    assert not (senders & (DRIVER_MAY_CALL | HELPER_MAY_CALL))


def test_the_check_is_not_empty():
    """Guards the regex: the calls the review read are found."""
    d = _calls(DRIVER)
    assert {"i1pro_trigger_one_measure", "i1pro2_getUVvolts", "i1pro_readmeasurement"} <= d
    h = _calls(HELPER)
    assert {"it->read_strip", "i1pro2_cq_dual_tile", "i1pro2_cq_dual_spot_uv"} <= h
