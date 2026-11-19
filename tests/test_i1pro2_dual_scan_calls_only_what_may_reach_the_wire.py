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
    # ---- the i1iO 2 table's dual row (2026-11-18, section (d)); each read in i1pro_imp.c:
    # the table scan's own trigger: request 0xD4 from its trigger thread (i1pro2_delayed_trigger)
    "i1pro2_triggermeasure",
    # request 0xC9, 8 bytes IN (the status read after every recorded lamp pass; the table
    # scan sends it after every pass already)
    "i1pro_getmisc",
    # state only, nothing sent: the table scan's ready rules and its instrument check, the
    # read cancel's reset, error mapping, clocks, joining the trigger thread
    "i1pro2_cq_tscan_ready", "cq_tscan_m", "usb_reinit_cancel", "msec_time", "time",
    # 2026-11-19 (SHOULD-1): the lamp pass's dark waits 170 ms after the lamp; a sleep only
    "msec_sleep",
    "m->trig_thread->del",
    # arithmetic on readings already read
    "i1pro_scale_specrd",
    # the dual tile kept beside ArgyllCMS's own calibration file: files, no instrument
    "xdg_bds", "xdg_free", "create_parent_directories", "fopen", "fwrite", "fread", "fclose",
    "memcmp", "sprintf", "strncpy", "CQ_TD_NO",
}

#: chromiq_dualdev.c (the helper side): the instrument only through the dual API and read_strip
HELPER_MAY_CALL = _LIBC | {
    "it->read_strip",                  # the UV pass: ArgyllCMS's own scan (0xD4 + reads)
    "i1pro2_cq_dual_options", "i1pro2_cq_dual_tile", "i1pro2_cq_dual_arm",
    "i1pro2_cq_dual_spot_uv", "i1pro2_cq_dual_take_uv", "i1pro2_cq_dual_take_lamp",
    "i1pro2_cq_dual_conv", "i1pro2_cq_dual_lamp_count", "i1pro2_cq_ruler_take",
    "i1pro2_cq_dual_uv_pass_ready",    # reads the driver's state, sends nothing (M2 fix)
    # the i1iO 2 table (--dual-table, 2026-11-18): the dual tile kept / taken up again, files only
    "i1pro2_cq_dual_tile_save", "i1pro2_cq_dual_tile_restore",
    # arithmetic and output, no instrument
    "cq_dual_check", "cq_dual_cut", "cq_dual_patch", "cq_dual_positions", "cq_cx_from_ipatch",
    "cq_dual_pairing",                 # the pairing check (M1 fix), arithmetic only
    "cq_emit_raw", "cq_json_escape", "cq_ruler_rec_clear",
    # the conditions event "active: false" (chromiq_chartread.c); its only instrument call is
    # the i1Pro 3's own conditions switch, never reached for an i1Pro 2
    "cq_cond_lose",
    # 4.3.49 (the hand dual scan's gaps): state only, nothing sent. The calibration gate is a
    # flag (chromiq_json.c), closed during the wait for the UV pass so a requested calibration
    # waits for the next prompt; cq_dd_held_command (chromiq_chartread.c) reads and clears the
    # waiting key of the uicallback's context (no instrument call); cq_dd_fits is arithmetic on
    # the last calibration
    "cq_cal_gate_set", "cq_dd_held_command",
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
    own = _own(DRIVER, ("i1pro2_cq_dual_", "cq_dual_", "i1pro2_cq_tdual_", "cq_tdual_"))
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


# --------------------------------------------- the allow-list as THE rule (safety fix, S1)
#
# The two tests above allow a function by name; this one follows every allowed function into
# ArgyllCMS's driver (i1pro_imp.c, i1pro.c and the dual file itself, function references
# included, so a trigger THREAD counts as reached) and collects every USB request any of them
# can send. The result must be exactly the table below; a new request anywhere on these paths
# fails here until someone has read what it sends.

INSTLIB = ROOT / "native" / "instlib"

#: every USB sender reachable from the dual scan's entry points: (function, kind, code) -> why
REACHABLE_SENDERS = {
    ("i1pro2_delayed_trigger", "control", "0xD4"): "the i1Pro 2 measurement trigger (recorded)",
    ("i1pro2_getUVvolts", "control", "0xD8"): "the UV LED's volts, read only (recorded)",
    ("i1pro_readmeasurement", "read", "0x82"): "the readings of a trigger",
    ("cq_ruler_thread", "read", "0x85"): "the ruler stream, read only (the ruler check's reader)",
    ("i1pro_waitfor_switch_th", "read", "0x84"): "the instrument's button, read only",
    # the i1iO 2 table's dual row (2026-11-18): the status read after every recorded lamp pass
    # (the table scan sends it already)
    ("i1pro_getmisc", "control", "0xC9"): "the status, 8 bytes in, read only (recorded)",
    # the lights Beta's own recorded light program, before a trigger, only with that Beta on
    ("cq_lights_send", "control", "0xD6"): "lights Beta only: its recorded OFF_SLOW",
    ("cq_lights_send", "write", "0x03"): "lights Beta only: its recorded OFF_SLOW",
    # the i1Pro Rev A-D's own path; the dual scan is offered only for an i1Pro 2
    ("i1pro_delayed_trigger", "control", "0xC0"): "Rev A-D trigger (p->dtype != instI1Pro2)",
    ("i1pro_getmcmode", "control", "0xD1"): "Rev A-D clock mode (the else of dtype == instI1Pro2)",
    ("i1pro_setmcmode", "control", "0xCF"): "Rev A-D clock mode (the else of dtype == instI1Pro2)",
    ("i1pro_setmeasparams", "control", "0xC1"): "Rev A-D parameters (p->dtype != instI1Pro2)",
}


def _driver_defs() -> "dict[str, str]":
    src = ""
    for f in ("i1pro_imp.c", "i1pro.c", "cq_i1pro2_dual.h"):
        t = (INSTLIB / f).read_text(encoding="latin-1")
        src += re.sub(r"/\*.*?\*/", "", t, flags=re.S)
    defs = {}
    for m in re.finditer(r"^(?:[A-Za-z_][\w\*]*[ \t\*]+)*\**(\w+)\s*\(([^;{}()]*(?:\([^()]*\)[^;{}()]*)*)\)\s*\{",
                         src, flags=re.M):
        defs[m.group(1)] = src[m.end():src.find("\n}\n", m.end())]
    return defs


def _reachable(defs, start) -> "set[str]":
    seen, todo = set(), list(start)
    while todo:
        f = todo.pop()
        if f in seen or f not in defs:
            continue
        seen.add(f)
        todo += [n for n in re.findall(r"\b([A-Za-z_]\w*)\b", defs[f]) if n in defs]
    return seen


def _senders(defs, names) -> "set[tuple[str, str, str]]":
    out = set()
    for f in names:
        for kind, args in re.findall(r"usb_(control|read|write)\s*\(([^;]*?)\)\s*\)?\s*[;!=<>]", defs[f],
                                     flags=re.S):
            a = [x.strip() for x in args.split(",")]
            code = a[2] if kind == "control" else a[2]
            out.add((f, kind, "0x%02X" % int(code, 16)))
    return out


def test_every_request_the_dual_scan_can_reach_is_one_we_have_read():
    defs = _driver_defs()
    api = set(re.findall(r"\b(i1pro2_cq_t?dual_\w+)\s*\(", (INSTLIB / "cq_dual.h").read_text(encoding="utf-8")))
    assert api and api <= set(defs), sorted(api - set(defs))
    drv = {n for n in DRIVER_MAY_CALL if n in defs}
    start = api | drv | {"i1pro_read_strip"}     # the helper's it->read_strip is ArgyllCMS's
    found = _senders(defs, _reachable(defs, start))
    assert found == set(REACHABLE_SENDERS), (
        f"new: {sorted(found - set(REACHABLE_SENDERS))}; gone: {sorted(set(REACHABLE_SENDERS) - found)}")
    # never an EEPROM write, an indicator program of i1Profiler's, a ruler stop
    reach = _reachable(defs, start)
    for never in ("i1pro_writeEEProm", "i1pro2_indLEDseq", "i1pro2_indLEDoff", "i1pro2_stop_ruler",
                  "i1pro_update_log"):
        assert never not in reach, never


def test_the_rev_a_to_d_senders_hang_only_off_the_rev_a_to_d_branches():
    """0xC0 / 0xC1 / 0xCF / 0xD1 are reachable by name only: each is called from
    i1pro_trigger_one_measure (or its Rev A-D trigger) behind ``p->dtype != instI1Pro2`` or in the
    ``else`` of ``p->dtype == instI1Pro2``, and the dual scan refuses anything but an i1Pro 2
    (i1pro2_cq_dual_options)."""
    defs = _driver_defs()
    reach = _reachable(defs, {"i1pro_read_strip"} | {n for n in DRIVER_MAY_CALL if n in defs})
    rev_ad = {"i1pro_delayed_trigger", "i1pro_getmcmode", "i1pro_setmcmode", "i1pro_setmeasparams",
              "i1pro_triggermeasure"}
    parents = {s: {f for f in reach if f != s and re.search(r"\b" + s + r"\b", defs[f])} for s in rev_ad}
    assert parents["i1pro_delayed_trigger"] == {"i1pro_triggermeasure"}
    for s in ("i1pro_getmcmode", "i1pro_setmcmode", "i1pro_setmeasparams", "i1pro_triggermeasure"):
        assert parents[s] == {"i1pro_trigger_one_measure"}, (s, parents[s])
    body = defs["i1pro_trigger_one_measure"]
    rev_e = body.index("if (p->dtype == instI1Pro2) {")
    other = body.index("} else {", rev_e)
    for s in ("i1pro_getmcmode", "i1pro_setmcmode"):
        assert all(m.start() > other for m in re.finditer(r"\b" + s + r"\(", body)), s
        assert s not in body[rev_e:other]
    for s in ("i1pro_setmeasparams", "i1pro_triggermeasure"):
        for m in re.finditer(r"\b" + s + r"\(", body):
            assert "p->dtype != instI1Pro2" in body[max(0, m.start() - 200):m.start()], s
    opts = defs["i1pro2_cq_dual_options"]
    assert "p->dtype != instI1Pro2" in opts.split("if (!on)")[0]


# ---- the i1iO 2 table's dual row, the helper's side (chromiq_tablescan.c, 2026-11-18)

TABLESCAN = ROOT / "native" / "chartread_helper" / "chromiq_tablescan.c"

#: what the table scan's dual functions (ts_dual_*) may call: the dual API, arithmetic, files
TABLE_HELPER_MAY_CALL = _LIBC | {
    "i1pro2_cq_tdual_on", "i1pro2_cq_dual_tile_restore", "i1pro2_cq_dual_tile",
    "i1pro2_cq_dual_tile_save", "i1pro2_cq_tdual_fire",
    "cq_dual_check", "cq_dual_pairing", "cq_dual_patch",
    "cq_emit_raw", "msec_time", "snprintf", "ts_get", "atof", "fopen", "fclose", "fscanf",
    "fprintf", "ts_emit_fired", "ts_dual_take_tile",
    # 4.3.48 re-review NOTE-B: a calibration clears the driver's ready "yes" and delivered lamp
    # pass (cq_i1pro2_dual.h: two assignments, nothing sent)
    "i1pro2_cq_tdual_disarm",
}


def _function_bodies(path: Path, prefix: str) -> str:
    t = path.read_text(encoding="utf-8", errors="replace")
    t = re.sub(r"/\*.*?\*/", "", t, flags=re.S)
    out = ""
    for m in re.finditer(r"^static [^\n(]*\b(" + prefix + r"\w*)\s*\([^)]*\)\s*\{", t, flags=re.M):
        out += t[m.end():t.find("\n}\n", m.end())] + "\n"
    return out


def test_the_table_dual_helper_reaches_the_instrument_only_through_the_dual_api():
    body = _function_bodies(TABLESCAN, "ts_dual_")
    assert "i1pro2_cq_tdual_fire" in body and "cq_dual_pairing" in body
    body = re.sub(r'"(\\.|[^"\\])*"', '""', body)
    calls = {re.sub(r"\s+", "", n) for n in re.findall(
        r"([A-Za-z_]\w*(?:\s*->\s*[A-Za-z_]\w*)*)\s*\(", body)} - _KEYWORDS
    extra = calls - TABLE_HELPER_MAY_CALL
    assert not extra, f"chromiq_tablescan.c's dual part calls {sorted(extra)}"
