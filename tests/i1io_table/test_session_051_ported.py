"""Ported from the tester program chromiq-i1io-session 0.6.0: ``tests/test_i1io_session_051.py`` (branch
tester/i1io-session-0.6.0, 84d30fa1d), the tests that need only the modules that moved into
``workflow/i1io/table/`` and the simulators in ``tests/i1io_table/``. Test bodies are verbatim;
only this header and the imports are new (test_guarantees_in_the_app.py says what stayed).
No hardware: the simulated table and fake readers only.
"""
from __future__ import annotations

import ast  # noqa: F401
import hashlib  # noqa: F401
import inspect  # noqa: F401
import json  # noqa: F401
import math  # noqa: F401
import plistlib  # noqa: F401
import re  # noqa: F401
import signal  # noqa: F401
import subprocess  # noqa: F401
import sys  # noqa: F401
import zipfile  # noqa: F401
from pathlib import Path  # noqa: F401

import pytest  # noqa: F401

from tests.i1io_table import part_c_sim as csim  # noqa: F401
from tests.i1io_table import session_sim as sim_mod  # noqa: F401
from tests.i1io_table._moved import PKG, ROOT  # noqa: F401
from workflow.i1io.table import geometry as geo  # noqa: F401
from workflow.i1io.table import lines as cl  # noqa: F401
from workflow.i1io.table import reader as rd  # noqa: F401
from workflow.i1io.table import scan as sc  # noqa: F401
from workflow.i1io.table import session_table as tbl  # noqa: F401


FAKE_SERIAL = "FAKESERIAL0123"


def _dev(name, vid, pid, loc, rid, children=(), dev_class=0):
    return {"IOObjectClass": "IOUSBHostDevice", "IORegistryEntryName": name,
            "IORegistryEntryID": rid, "idVendor": vid, "idProduct": pid,
            "locationID": loc, "bDeviceClass": dev_class, "USB Serial Number": FAKE_SERIAL,
            "kUSBSerialNumberString": FAKE_SERIAL, "USB Product Name": name,
            "IORegistryEntryChildren": list(children)}


def _intf(name, vid, pid, loc, rid, number=0):
    return {"IOObjectClass": "IOUSBHostInterface", "IORegistryEntryName": name,
            "IORegistryEntryID": rid, "idVendor": vid, "idProduct": pid, "locationID": loc,
            "bInterfaceNumber": number, "bConfigurationValue": 1,
            "IORegistryEntryChildren": [{"IOObjectClass": "AppleUSBHostInterfaceUserClient",
                                         "IORegistryEntryID": rid + 1}]}


def his_mac():
    """The shape of a real i1iO 2 with its i1Pro 2 on a Mac, as `ioreg -a -r -c IOUSBHostDevice
    -l` gives it: a hub (a root of the list) with the table and the i1Pro 2 below it, each
    with one interface entry carrying the device's own ids; plus a keyboard."""
    table = _dev("Eye-One iO", 0x0971, 0x2004, 0x02210000, 100,
                 [_intf("Eye-One iO", 0x0971, 0x2004, 0x02210000, 101)])
    pro = _dev("eye-one", 0x0971, 0x2000, 0x02230000, 200,
               [_intf("IOUSBHostInterface", 0x0971, 0x2000, 0x02230000, 201)])
    hub = _dev("USB2.0 Hub", 0x05E3, 0x0608, 0x02200000, 50, [table, pro], dev_class=9)
    kbd = _dev("Keyboard", 0x05AC, 0x024F, 0x01100000, 60,
               [_intf("Keyboard", 0x05AC, 0x024F, 0x01100000, 61)])
    return [hub, kbd]


def usb_ids_050(roots):
    """0.5.0's counting, kept here verbatim (minus ioreg) to show the fault it had."""
    found = []

    def walk(n):
        if not isinstance(n, dict):
            return
        v, p = n.get("idVendor"), n.get("idProduct")
        if isinstance(v, int) and isinstance(p, int):
            found.append((v, p))
        for c in n.get("IORegistryEntryChildren", []) or []:
            walk(c)
    for r in roots:
        walk(r)
    return found


def test_the_0_5_0_count_saw_two_i1pros_on_his_set_up():
    """The fault, reproduced: one i1Pro 2 counted twice, and 0.5.0's own words for it."""
    ids = usb_ids_050(his_mac())
    assert ids.count(rd.I1PRO_IDS) == 2 and ids.count(rd.TABLE_IDS) == 2
    pros = [i for i in ids if i == rd.I1PRO_IDS]
    assert len(pros) > 1          # 0.5.0: "macOS lists more than one i1Pro. Please connect ..."


def test_0_5_1_counts_each_device_once_and_lets_the_reader_start():
    devs = rd.usb_devices(his_mac())
    ids = [(d["vid"], d["pid"]) for d in devs]
    assert ids.count(rd.I1PRO_IDS) == 1 and ids.count(rd.TABLE_IDS) == 1
    assert len(devs) == 4                        # hub, table, i1Pro 2, keyboard
    pro = next(d for d in devs if (d["vid"], d["pid"]) == rd.I1PRO_IDS)
    assert pro["interfaces"] == 1 and pro["place"] == 0x02230000
    assert rd.instrument_check(devices=devs) is None


def _fake_ioreg(monkeypatch, roots):
    data = plistlib.dumps(roots)

    class R:
        stdout = data
    calls = []

    def run(argv, **kw):
        calls.append(argv)
        assert argv[0] == "/usr/sbin/ioreg"
        return R()
    monkeypatch.setattr(rd.subprocess, "run", run)
    return calls


def test_the_check_reads_macos_s_list_and_logs_exactly_what_it_counted(monkeypatch):
    """Through ioreg's real plist form; the log names every counted device by USB ids and
    place, says how many interface entries were not counted, and never a name or serial."""
    calls = _fake_ioreg(monkeypatch, his_mac())
    logged = []
    assert rd.instrument_check(log=lambda k, t: logged.append((k, t))) is None
    assert calls and calls[0][:4] == ["/usr/sbin/ioreg", "-a", "-r", "-c"]
    (kind, text), = logged
    assert kind == "INST"
    assert "0971:2004 the table at USB place 02210000, 1 interface entry of it not counted" in text
    assert "0971:2000 an i1Pro (counted) at USB place 02230000, 1 interface entry of it not " \
           "counted" in text
    assert "2 other USB devices" in text
    for secret in (FAKE_SERIAL, "Eye-One", "eye-one", "Keyboard", "Hub"):
        assert secret not in text, secret


def test_a_device_listed_twice_at_one_place_is_one_device():
    """Should macOS ever list a nested device again as its own root, it is still one."""
    roots = his_mac()
    pro = roots[0]["IORegistryEntryChildren"][1]
    roots.append(dict(pro))
    assert rd.instrument_check(devices=rd.usb_devices(roots)) is None


@pytest.mark.parametrize("place", [True, False])
@pytest.mark.parametrize("drop", ["class", "number"])
def test_an_interface_is_known_by_its_class_or_by_its_number(drop, place):
    """Each guard on its own: without its USB place the interface cannot be merged into its
    device by the place, so only the interface test keeps it from counting."""
    roots = his_mac()
    intf = roots[0]["IORegistryEntryChildren"][1]["IORegistryEntryChildren"][0]
    if not place:
        intf.pop("locationID")
    if drop == "class":
        intf.pop("IOObjectClass")
    else:
        intf.pop("bInterfaceNumber")
    devs = rd.usb_devices(roots)
    assert [(d["vid"], d["pid"]) for d in devs].count(rd.I1PRO_IDS) == 1
    assert rd.instrument_check(devices=devs) is None


def test_a_driver_entry_with_the_device_s_numbers_is_not_a_device():
    """A driver below a device can carry the device's idVendor and idProduct (its matching
    personality, for example a vendor's driver for the i1Pro): it is not a second device."""
    roots = his_mac()
    pro = roots[0]["IORegistryEntryChildren"][1]
    pro["IORegistryEntryChildren"].append({"IOObjectClass": "SomeVendorI1ProDriver",
                                           "IORegistryEntryID": 777, "idVendor": 0x0971,
                                           "idProduct": 0x2000})
    devs = rd.usb_devices(roots)
    assert [(d["vid"], d["pid"]) for d in devs].count(rd.I1PRO_IDS) == 1
    assert rd.instrument_check(devices=devs) is None


def test_two_real_i1pros_are_still_refused_and_the_text_says_what_was_seen():
    roots = his_mac()
    roots.append(_dev("eye-one", 0x0971, 0x2000, 0x01200000, 300,
                      [_intf("IOUSBHostInterface", 0x0971, 0x2000, 0x01200000, 301)]))
    why = rd.instrument_check(devices=rd.usb_devices(roots))
    assert why.startswith("macOS lists 2 separate i1Pro devices")
    assert "02230000" in why and "01200000" in why
    assert "only after this program has ended" in why
    assert "never the table or the i1Pro 2 in its arm" in why
    assert "connect only the one in the table" not in why


def test_another_instrument_is_refused_but_a_hub_from_such_a_maker_is_not():
    roots = his_mac()
    roots.append(_dev("hub", 0x1A86, 0x8091, 0x01300000, 400, dev_class=9))
    assert rd.instrument_check(devices=rd.usb_devices(roots)) is None
    roots.append(_dev("i1Display", 0x0765, 0x5020, 0x01400000, 500))
    why = rd.instrument_check(devices=rd.usb_devices(roots))
    assert "another measuring instrument (USB 0765:5020)" in why
    assert "only after this program has ended" in why


def test_no_i1pro_and_an_unreadable_list_are_said_as_such(monkeypatch):
    roots = his_mac()
    roots[0]["IORegistryEntryChildren"].pop(1)
    assert "macOS lists no i1Pro 2" in rd.instrument_check(devices=rd.usb_devices(roots))
    monkeypatch.setattr(rd, "_usb_tree", lambda: None)
    logged = []
    why = rd.instrument_check(log=lambda k, t: logged.append(t))
    assert "could not read macOS's list" in why
    assert "could not be read" in logged[0]


def test_a_lost_link_text_does_not_reach_parts_a_and_b():
    t = tbl.Table(None)
    t.part = "B"
    t.t = type("C", (), {"now": staticmethod(lambda: 1.0)})()
    d = t._doubt("the USB link failed: USB read failed (x)")
    assert d.plain is None and t.link_lost_at is None
    t2 = tbl.Table(None)
    t2.part = "C"
    t2.t = t.t
    d2 = t2._doubt("the USB link failed: USB read failed (x)")
    assert d2.plain.startswith("The table's USB connection was lost (USB read failed (x))")
    assert t2.link_lost_at == 1.0


def test_the_move_starts_with_the_first_reading():
    """Measured: the recorded moves start 0.3718 s after the lamp trigger (sd 0.0027 s), with
    the first reading (0.370 s), within one reading. 0.43 was 12 readings late."""
    assert abs(sc.MOTION_START_AFTER_LAMP_S - sc.FIRST_READING_AFTER_LAMP_S) < sc.READING_S
    assert sc.CUT_REFINE_READINGS == 0
    import inspect
    assert inspect.signature(sc.cut_by_position).parameters["refine_readings"].default == 0


def test_the_simulator_keeps_its_own_motion_start():
    import inspect
    src = inspect.getsource(csim)
    assert "MOTION_START_AFTER_LAMP_S" not in src.replace("TABLE_MOTION_START_AFTER_LAMP_S", "")
    assert "+ 0.43" not in src and "- 0.43" not in src
    assert abs(csim.TABLE_MOTION_START_AFTER_LAMP_S - 0.372) < 0.003


def _stream(plan, true_start, gap=0.5):
    """A reading stream as the instrument gives it along *plan*: the table starts the move
    *true_start* s after the lamp trigger, the first reading comes FIRST_READING_AFTER_LAMP_S
    after it; each patch has its own flat spectrum, the gaps between patches another."""
    import random
    rng = random.Random(7)
    truth = {q.loc: [rng.uniform(0.05, 0.9)] * 36 for q in plan.patches}
    L = plan.dist / 10.0

    def s_at(t):
        if t <= 0:
            return 0.0
        lo, hi = 0.0, L
        for _ in range(60):
            mid = (lo + hi) / 2
            if sc.time_at(plan, mid) < t:
                lo = mid
            else:
                hi = mid
        return lo
    rows = []
    for k in range(plan.N):
        t = sc.FIRST_READING_AFTER_LAMP_S + (k + 0.5) * sc.READING_S - true_start
        pos = s_at(t)
        q = next((q for q in plan.patches if abs(pos - q.along_mm) <= q.half_mm), None)
        rows.append(list(truth[q.loc]) if q else [gap] * 36)
    return truth, rows


@pytest.mark.parametrize("start", [0.372, 0.43])
def test_the_cut_follows_the_table_not_its_own_guess(monkeypatch, start):
    """The recorded row (8 mm patches at 118 mm/s) on a table that starts at the measured
    0.372 s is cut right with the default; had the program kept 0.43 (12 readings late), the
    same stream would come out wrong, and the uniformity says so (port of study/i1io-scan
    9f01e8acd's test onto this package's cut)."""
    plan = sc.recorded_row_plan()
    truth, rows = _stream(plan, csim.TABLE_MOTION_START_AFTER_LAMP_S)
    monkeypatch.setattr(sc, "MOTION_START_AFTER_LAMP_S", start)
    # the motion-start constant is the subject here, with tester 0.6.0's 0.5 mm border (4.3.53
    # fix round 2: the release's border grows with the speed, tests/i1io_table/
    # test_4353_fix2_cut_at_speed.py; at 118 mm/s it leaves no reading in these 8 mm patches)
    vals, info = sc.cut_by_position(plan, rows, edge_mm=0.5)
    err = max(max(abs(a - b) for a, b in zip(v, truth[q.loc]))
              for q, v in zip(plan.patches, vals))
    assert info["motion_start_after_lamp_s"] == round(start, 4)
    if start == 0.372:
        assert err < 0.01
        assert max(info["uniformity"]) < 0.02
    else:
        assert err > 0.05                       # the old constant cuts across patches
        assert max(info["uniformity"]) > 0.05   # ... and the uniformity says so

