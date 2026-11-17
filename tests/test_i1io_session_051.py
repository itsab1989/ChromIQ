# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 the ChromIQ authors. Part of ChromIQ (https://github.com/itsab1989/ChromIQ).
"""chromiq-i1io-session 0.5.1: the fixes after the first real part C sitting with 0.5.0.

1. The instrument check counted the i1Pro 2 twice: macOS lists every USB device's INTERFACE
   entry (IOUSBHostInterface) with the device's own idVendor and idProduct, and 0.5.0 counted
   every entry that carried them. Reproduced here from the shape of a real i1iO 2 with its
   i1Pro 2 (both behind one hub, each with one interface entry; values invented, the shape is
   that of a volunteer's ioreg of 14 November).
2. A lost USB link in part C: a plain text of what happened, the safe way back, no stage
   offered afterwards, nothing more sent, and one question about it.
3. The person agrees to what the reader does to X-Rite's service before the first reader.
4. The strip cut: the move starts 0.372 s after the lamp trigger (measured), not 0.43 s.

No hardware: the simulated table and fake readers of the other part C tests.
"""
from __future__ import annotations

import plistlib
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
PKG = ROOT / "tools" / "i1io_session"
sys.path.insert(0, str(PKG))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import i1io_part_c as pc  # noqa: E402
import i1io_part_c_sim as csim  # noqa: E402
import i1io_reader as rd  # noqa: E402
import i1io_scan as sc  # noqa: E402
import i1io_session as prog  # noqa: E402
import i1io_session_table as tbl  # noqa: E402
from test_i1io_part_c import (REAL_FAKE_READERS, CScript, P0, check_truthful, readers,  # noqa: E402
                              run_c, screen, verdicts)

FAKE_SERIAL = "FAKESERIAL0123"


# ---- 1. the instrument check -------------------------------------------------------------

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


def test_the_real_readers_check_logs_it_too(monkeypatch, tmp_path):
    _fake_ioreg(monkeypatch, his_mac())
    monkeypatch.setattr(rd, "helper_problems", lambda path: [])
    logged = []
    r = pc.Readers(lambda k, t: logged.append((k, t)), helper=tmp_path / "x")
    assert r.check() is None
    assert any("instrument check: macOS lists" in t for _, t in logged)


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


def test_the_wrong_advice_is_gone_everywhere():
    for f in PKG.glob("*.py"):
        assert "connect only the one in the table" not in f.read_text(), f.name
    assert "connect only the one" not in (PKG / "README.md").read_text()


# ---- 3. the reader's consent ---------------------------------------------------------------

def test_the_reader_consent_comes_before_any_reader_and_only_once(tmp_path):
    started_at_question = []
    holder = {}

    def factory(s, lg):
        r = REAL_FAKE_READERS(s, lg)
        holder["r"] = r
        return r

    class Spy(CScript):
        def ask(self, question, choices=("yes", "no")):
            if question == pc.ASK_READER_CONSENT:
                started_at_question.append(list(holder["r"].started))
            return super().ask(question, choices)
    code, sim, log, con, res = run_c(tmp_path, ["c1", "c2"], readers=factory, console_cls=Spy)
    assert verdicts(log) == [("c1", "worked"), ("c2", "worked")]
    assert started_at_question == [[]]           # asked once, before any reader started
    text = screen(con)
    assert text.index(pc.READER_CONSENT) < text.index("Stage C1 worked")
    for needed in ("i1ProDeviceService", "xrdd, is not touched", "What we do not know",
                   "restarting the Mac", "only after this program has ended"):
        assert needed in pc.READER_CONSENT, needed
    assert "part C: start the reader (X-Rite's service)" in log


def test_a_no_to_the_reader_starts_no_reader_and_the_sitting_goes_on(tmp_path):
    holder = {}

    def factory(s, lg):
        holder["r"] = REAL_FAKE_READERS(s, lg)
        return holder["r"]
    code, sim, log, con, res = run_c(tmp_path, ["c1", "d1", "f"], readers=factory,
                                     script={pc.ASK_READER_CONSENT: "no"})
    assert verdicts(log) == [("c1", "stopped by you (clean)"), ("d1", "worked"), ("f", "worked")]
    assert holder["r"].started == []
    assert "you chose not to start the reader" in screen(con)


def test_the_consent_follows_the_check_so_a_refused_check_asks_nothing(tmp_path):
    code, sim, log, con, res = run_c(tmp_path, ["c1"], readers=readers(problem="no i1Pro"))
    assert pc.ASK_READER_CONSENT not in [q for q, *_ in con.seen]
    assert pc.HOLDS_TABLE in screen(con)


# ---- 2. a lost USB link --------------------------------------------------------------------

FIRST = ["c1", "c2", "e1", "c3", "c4", "f"]


def _clean_lines(tmp_path):
    code, sim, log, con, res = run_c(tmp_path / "clean", FIRST)
    assert code == 0 and sim.violations == []
    return sim.received


def check_lost_link(sim, con, log, writes_at_loss):
    text = screen(con)
    assert sim.violations == []
    assert "The table's USB connection was lost" in text, text[-2000:]
    if pc.PENDING in text or pc.UNFINISHED in text:
        # a move may be waiting: switch off first, never a re-plug, i1Profiler only after
        assert pc.LINK_WAY_BACK_SWITCH_OFF in text
        assert pc.LINK_WAY_BACK not in text
    else:
        assert pc.LINK_WAY_BACK in text
    assert prog.ASK_LINK_LOST in [q for q, *_ in con.seen]
    # nothing more was even tried on the wire
    assert len(sim.received) == writes_at_loss
    # no stage offered once the link was lost
    qs = [q for q, *_ in con.seen]
    i = qs.index(prog.ASK_LINK_LOST)
    assert not any(q.startswith("Which stage now?") or q.startswith("Run stage")
                   for q in qs[i:])
    assert "held when last checked" not in "\n".join(con.said[-12:])
    check_truthful(sim, con, log)


@pytest.mark.slow       # exhaustive: every line of the first stages (--runslow)
def test_a_lost_link_at_every_line_of_part_c_ends_truthfully(tmp_path):
    lines = _clean_lines(tmp_path)
    for i in range(len(lines)):
        sim = csim.CSimTable(part_c=False)
        sim.inject_at(i, "unplug")
        code, sim, log, con, res = run_c(tmp_path / f"u{i}", FIRST, sim=sim)
        assert code == 2, (i, lines[i])
        check_lost_link(sim, con, log, i + 1)
        if i >= len(sim_open()):
            last = [ln for ln in log.splitlines() if ln.startswith("RESULT") and '"verdict"'
                    in ln][-1]
            assert '"verdict": "stopped"' in last, (i, last)
            assert ("the USB link failed" in last or "a scan move may be pending" in last), \
                (i, last)
            assert "the USB link failed" in log or "the USB link was lost" in log, i


def sim_open():
    import i1io_session_sim as sm
    return sm.REC_OPEN


def test_a_lost_link_at_a_few_lines_ends_truthfully(tmp_path):
    lines = _clean_lines(tmp_path)
    picks = sorted({0, len(sim_open()), len(sim_open()) + 1,
                    next(k for k, ln in enumerate(lines) if ln.startswith(";m0")),
                    next(k for k, ln in enumerate(lines) if ln.startswith(";m2")),
                    len(lines) - 1})
    for i in picks:
        sim = csim.CSimTable(part_c=False)
        sim.inject_at(i, "unplug")
        code, sim, log, con, res = run_c(tmp_path / f"u{i}", FIRST, sim=sim)
        assert code == 2, (i, lines[i])
        check_lost_link(sim, con, log, i + 1)
        if lines[i].startswith(";m0"):
            assert "never reported that its last movement" in screen(con) or \
                "may still be moving" in screen(con)
        if lines[i].startswith(";m2"):
            assert "SWITCH THE TABLE OFF" in screen(con)


class Unplugs(CScript):
    """His run 3: the table goes from the bus while the program waits at a question."""
    at_question = "Which stage now?"
    nth = 3

    def ask(self, question, choices=("yes", "no")):
        if question.startswith(self.at_question):
            self.nth -= 1
            if self.nth == 0:
                self.sim.unplugged = True
                self.at_loss = len(self.sim.received)
        return super().ask(question, choices)


def test_his_run_3_the_table_gone_between_two_stages(tmp_path):
    """C1 and C2 fail cleanly at the instrument check (as on his Mac), the table goes from
    the bus while the program waits, he chooses C1 again: the program finds the link gone
    at its first read, before any line, and says what that means and the way back."""
    code, sim, log, con, res = run_c(tmp_path, ["c1", "c2", "c1", "c3"],
                                     readers=readers(problem="(no reader in this test)"),
                                     console_cls=Unplugs)
    v = verdicts(log)
    assert v[:2] == [("c1", "failed cleanly (instrument)"), ("c2", "failed cleanly (instrument)")]
    assert v[2] == ("c1", "stopped")
    lines_before = con.at_loss
    stop = [ln for ln in log.splitlines() if ln.startswith("STOP")][0]
    assert "the USB link failed" in stop
    # nothing was sent in run 3: the STOP comes before any SEND of it
    after_start = log[log.index("start c1 run 2"):]
    assert "SEND" not in after_start[:after_start.index("STOP")]
    check_lost_link(sim, con, log, lines_before)
    text = screen(con)
    assert "Nothing was moved in this sitting." in text
    assert "s before the connection was lost" in text
    assert "This program has let go of the table's USB connection" in text
    assert pc.HOLDS_TABLE in text                # said after each clean failure


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


# ---- 2b. the way back after a lost link (REVIEW 0.5.1) ------------------------------------

def _lost(kind):
    d = tbl.Table(None)
    d.link_lost_at = 10.0
    d.motions_sent = 3
    d.last_read, d.last_read_t = (1102, 1498), 8.0
    if kind == "pending move":
        d.closed_reason = "a scan move may be pending"
        d.motion_unconfirmed = True
        d.last_move = ("scan move", None)
    elif kind == "unconfirmed movement":
        d.motion_unconfirmed = True
        d.last_move = ("move", None)
    return d


def _no_open_while_on(text):
    """No sentence may send him to i1Profiler before the table was off and on again."""
    first_off = text.find("switch the table off")
    first_off = min(i for i in (first_off, text.find("SWITCH THE TABLE OFF")) if i >= 0)
    assert first_off < text.find("i1Profiler")


@pytest.mark.parametrize("kind", ["pending move", "unconfirmed movement"])
def test_a_waiting_move_gets_the_switch_off_way_back_and_no_replug(kind):
    out = pc.where_text(_lost(kind))
    assert out[0] == (pc.PENDING if kind == "pending move" else pc.UNFINISHED)
    assert out[-1] == pc.LINK_WAY_BACK_SWITCH_OFF
    assert pc.LINK_WAY_BACK not in out
    way = pc.LINK_WAY_BACK_SWITCH_OFF
    assert way.startswith("First switch the table off with its power switch")
    assert "plug it in again" not in way and "or unplug" not in way
    # off, then this program ends, then on, and only then i1Profiler
    assert (way.index("switch the table off") < way.index("let this program end")
            < way.index("switch the table on again") < way.index("open i1Profiler"))
    for text in out:
        _no_open_while_on(text)


def test_nothing_pending_keeps_the_way_back_with_the_replug():
    out = pc.where_text(_lost("nothing pending"))
    assert out[-1] == pc.LINK_WAY_BACK
    assert pc.LINK_WAY_BACK_SWITCH_OFF not in out
    assert "or unplug the table's USB cable from the Mac and plug it in again" in pc.LINK_WAY_BACK
    assert pc.PENDING not in out and pc.UNFINISHED not in out


@pytest.mark.parametrize("kind", ["pending move", "unconfirmed movement", "nothing pending"])
def test_holds_table_always_allows_the_power_switch(kind):
    """HOLDS_TABLE is one text for every case: it must never forbid the power switch."""
    assert ("switching the table off at its power switch is still always allowed"
            in pc.HOLDS_TABLE)
    assert pc.HOLDS_TABLE.index("do not unplug or switch off anything") < pc.HOLDS_TABLE.index(
        "always allowed")
    assert pc.where_text(_lost(kind))      # the state text is still produced


def test_the_consent_says_a_restart_should_help_not_will():
    assert "restarting the Mac should." in pc.READER_CONSENT
    assert "restarting the Mac will" not in pc.READER_CONSENT


# ---- 4. the strip cut ----------------------------------------------------------------------

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
    vals, info = sc.cut_by_position(plan, rows)
    err = max(max(abs(a - b) for a, b in zip(v, truth[q.loc]))
              for q, v in zip(plan.patches, vals))
    assert info["motion_start_after_lamp_s"] == round(start, 4)
    if start == 0.372:
        assert err < 0.01
        assert max(info["uniformity"]) < 0.02
    else:
        assert err > 0.05                       # the old constant cuts across patches
        assert max(info["uniformity"]) > 0.05   # ... and the uniformity says so


def test_a_sitting_s_strip_cut_carries_the_uniformity(tmp_path):
    import json
    code, sim, log, con, res = run_c(tmp_path, ["c1", "d1", "e2", "f"])
    assert ("e2", "worked") in verdicts(log)
    info = json.loads(sorted(res.rglob("*.cut.json"))[0].read_text())
    assert info["motion_start_after_lamp_s"] == 0.372
    assert len(info["uniformity"]) == len(info["windows"])


# ---- the version ------------------------------------------------------------------------------

def test_the_version_is_0_5_1():
    assert tbl.TOOL_VERSION == "0.5.1"
    assert "0.5.1" in prog.TITLE
