"""Ported from the tester program chromiq-i1io-session 0.6.0: ``tests/test_i1io_session_tool.py`` (branch
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


SPOT_LINES = (";m0fb63067a012c03 ;m0fbba067b012ca8 ;m0fc11067b012c08 ;m0fc68067b012cfc "
              ";m0fcbf067b012ca2 ;m0fd17067b012c01 ;m0fd6e067c012ccd ;m0fdc5067c012cd0 "
              ";m0fe1c067c012cd3 ;m0fe74067c012cfc ;m0fecb067c012ca2 ;m0ff22067d012c01 "
              ";m0ff79067d012cf5 ;m0ffd0067d012cd1 ;m00027067d012c68 ;m0007e067d012c35 "
              ";m000d5067d012c38 ;m0012c067e012c3a ;m00184067e012c63 ;m001db067e012c09 "
              ";m00232067e012c69 ;m00289067e012c5d ;m002e0067f012c38 ;m00338067f012c61 "
              ";m0038f067f012c2e ;m003e6067f012c31 ;m0043d067f012c34 ;m00495067f012c5d").split()


OPEN = sim_mod.REC_OPEN


STEP_KEYS = ("home", "near", "straight", "across", "free", "close")


def test_every_line_has_a_valid_checksum_and_names_where_it_was_recorded():
    for key, line in tbl.WIRE.items():
        assert line.endswith(b"\r") and line.count(b"\r") == 1
        assert tbl.checksum_ok(line[:-1].decode("ascii"))
        assert re.search(r"\b(S1|S2|R1|R2) \d", tbl.RECORDED_AT[key]), key
    assert set(tbl.RECORDED_AT) == set(tbl.WIRE)


def test_the_four_moves_have_their_recorded_targets_and_speed():
    want = {"to_250": (1102, 250), "to_1000": (1000, 1500), "to_1498": (1102, 1498),
            "to_2507": (2507, 1498)}
    for key, (x, y) in want.items():
        line = tbl.WIRE[key].decode()
        assert line[1:3] == "m0"
        assert (int(line[3:7], 16), int(line[7:11], 16), int(line[11:15], 16)) == (x, y, 300)


def test_the_gate_refuses_every_other_line():
    for bad in (b";i02c\r", b";m10b10055b012c43\r", b";c32f\r", b";c42e\r", b";d1016d35\r",
                b";p124\r", b";m0044e00fa00c839\r", b";m0044e00fb012c0d\r", b";a133",
                b";a133\r\r", b";A133\r", b";u8000060000200d0\r", b"", b";f12e\n"):
        with pytest.raises(tbl.ForbiddenLine):
            tbl.check_outgoing(bad)


def test_the_caps_per_step_and_per_session_are_pinned():
    a = {s.key for s in tbl.STEPS}
    assert {k: v for k, v in tbl.STEP_MAX_LINES.items() if k in a} == {
        "home": 4, "near": 21, "straight": 19, "across": 27, "free": 25, "close": 3}
    assert {k: v for k, v in tbl.STEP_MAX_MOTIONS.items() if k in a} == {
        "home": 1, "near": 5, "straight": 4, "across": 6, "free": 3, "close": 0}
    assert tbl.MAX_LINES == 110 and tbl.MAX_MOTIONS == 19
    assert tbl.MAX_LINES == len(tbl.OPEN_KEYS) + sum(tbl.STEP_MAX_LINES[s.key] for s in tbl.STEPS)
    # part B (0.4.0)
    assert {s.key: (tbl.STEP_MAX_LINES[s.key], tbl.STEP_MAX_MOTIONS[s.key])
            for s in tbl.B_STEPS + tbl.near_steps()} == {
        "b_home": (4, 1), "b_align": (19, 3), "b_place": (11, 0), "b_first": (4, 1),
        "b_row": (54, 27), "b_end": (8, 1), "home_from_patch": (8, 1), "close_after_end": (3, 0)}
    assert (tbl.B_MAX_LINES, tbl.B_MAX_MOTIONS) == (114, 33)
    assert tbl.PART_CAPS == {"A": (110, 19), "B": (114, 33)}


def test_a_step_cannot_exceed_its_own_caps_nor_the_session_its_caps():
    sim = sim_mod.SimTable()
    d = tbl.Table(sim_mod.SimTransport(sim))
    d.opening()
    d.current_step, d.step_lines = tbl.STEPS[0], 4
    with pytest.raises(tbl.Doubt):
        d.exchange("status")
    d = tbl.Table(sim_mod.SimTransport(sim_mod.SimTable()))
    d.lines_sent = tbl.MAX_LINES
    with pytest.raises(tbl.Doubt):
        d.exchange("identity")
    d = tbl.Table(sim_mod.SimTransport(sim_mod.SimTable()))
    d.current_step, d.motions_sent = tbl.STEPS[1], tbl.MAX_MOTIONS
    n = len(d.t.writes)
    with pytest.raises(tbl.Doubt):
        d.exchange("to_250", "to_250")
    assert len(d.t.writes) == n


def test_no_movement_outside_a_step():
    d = tbl.Table(sim_mod.SimTransport(sim_mod.SimTable()))
    with pytest.raises(tbl.Doubt):
        d.exchange("home", "home_rest")
    assert d.t.writes == []


def test_the_guard_box_and_its_reasons_are_pinned():
    assert tbl.REST_GUARD == tbl.Box(1101, 1103, -1, 80)
    assert tbl.START_GUARD == tbl.Box(1090, 1115, -1, 250)
    assert not tbl.START_GUARD.contains((1058, 317))    # 32 units left of X 1090, 67 beyond Y 250
    assert tbl.START_GUARD.contains((1104, 110)) and tbl.START_GUARD.contains((1101, 97))
    assert tbl.HOME_FIRST[1] == ("p0", "START_GUARD", "right before the homing")
    assert tbl.HOME_AND_CHECK[2][1] == "REST_GUARD"
    assert tbl.REST_RECORDED == tbl.Box(1101, 1103, -1, 48)
    assert tbl.OUT_START == tbl.Box(1101, 1103, -1, 48)
    xs = [x for x, _ in tbl.RECORDED_REST_STARTS]
    ys = [y for _, y in tbl.RECORDED_REST_STARTS]
    assert tbl.REST_RECORDED == tbl.Box(min(xs) - 1, max(xs) + 1, min(ys) - 1, max(ys) + 1)
    assert not tbl.REST_GUARD.contains((1058, 317))      # the one recorded drive-out case
    assert tbl.TIME_WINDOW["home_rest"] == (0.0, 0.6) and tbl.TIME_WINDOW["home_wide"][1] == 1.1
    assert tbl.TIME_WINDOW["home_far"] == (0.0, 2.0) and tbl.TIME_WINDOW["home_free"] == (0.0, 2.0)


class USBError(Exception):
    def __init__(self, strerror="", errno=None):
        super().__init__(strerror)
        self.strerror, self.errno = strerror, errno


class USBTimeoutError(USBError):
    pass


class FakeCore:
    USBError = USBError
    USBTimeoutError = USBTimeoutError


class FakeUtil:
    def __init__(self):
        self.calls = []

    def claim_interface(self, dev, n):
        self.calls.append(("claim", n))

    def release_interface(self, dev, n):
        self.calls.append(("release", n))

    def dispose_resources(self, dev):
        self.calls.append(("dispose",))


class _EP:
    def __init__(self, addr):
        self.bEndpointAddress, self.bmAttributes, self.wMaxPacketSize = addr, 2, 64


class _Intf:
    bInterfaceClass = bInterfaceSubClass = bInterfaceProtocol = 0xFF

    def endpoints(self):
        return [_EP(0x81), _EP(0x02)]


class FakeDev:
    """Speaks to a SimTable in FTDI packets (2 status bytes + up to 62 bytes),
    with status-only packets between them. Touching the serial number fails."""

    def __init__(self, cold=True, line_status=0x60):
        self.bcdDevice = 0x0400
        self.sim = sim_mod.SimTable(cold=cold)
        self.t = sim_mod.SimTransport(self.sim)
        self.ctrl, self.line_status = [], line_status
        self.pending, self.toggle = b"", False

    def __getattr__(self, name):
        if "serial" in name.lower():
            raise AssertionError("the serial number string must never be read")
        raise AttributeError(name)

    def __getitem__(self, i):
        return [_Intf()]

    def get_active_configuration(self):
        return object()

    def ctrl_transfer(self, rt, req, val, idx, data, timeout):
        self.ctrl.append((rt, req, val, idx, data))

    def write(self, ep, data, timeout):
        assert ep == 0x02
        self.t.write(bytes(data))
        return len(data)

    def read(self, ep, size, timeout_ms):
        assert ep == 0x81 and size == 64
        self.toggle = not self.toggle
        if self.toggle:
            return bytes([0x11, 0x60])
        if not self.pending:
            self.pending = self.t.read(timeout_ms / 1000.0)
        if not self.pending:
            raise USBTimeoutError("Operation timed out", 60)
        out, self.pending = self.pending[:62], self.pending[62:]
        return bytes([0x11, self.line_status]) + out


def _ftdi(dev):
    """The FTDI path on the simulator's VIRTUAL clock (so the movement windows apply)."""
    util = FakeUtil()
    t = tbl.FtdiUsb(dev, FakeCore, util)
    t.now = dev.t.now
    t.setup()
    return util, t


def test_setup_sends_exactly_the_five_recorded_ftdi_requests(monkeypatch):
    monkeypatch.setattr(tbl.time, "sleep", lambda s: None)
    dev = FakeDev()
    util, t = _ftdi(dev)
    assert dev.ctrl == [(0x40, 0x00, 0x0000, 0, None), (0x40, 0x00, 0x0001, 0, None),
                        (0x40, 0x00, 0x0002, 0, None), (0x40, 0x03, 0x0034, 0, None),
                        (0x40, 0x04, 0x0008, 0, None)]


def test_the_ftdi_transport_refuses_any_other_line_itself(monkeypatch):
    monkeypatch.setattr(tbl.time, "sleep", lambda s: None)
    dev = FakeDev()
    util, t = _ftdi(dev)
    with pytest.raises(tbl.ForbiddenLine):
        t.write(b";c32f\r")
    assert dev.sim.received == []


def test_a_step_runs_at_most_once():
    sim = sim_mod.SimTable()
    d = tbl.Table(sim_mod.SimTransport(sim))
    d.opening()
    home = tbl.STEPS[STEP_KEYS.index("home")]
    d.run_step(home)
    assert not d.can_run(home)
    n = len(d.t.writes)
    with pytest.raises(tbl.Doubt):
        d.run_step(home)
    assert len(d.t.writes) == n


def test_a_stop_noticed_inside_write_before_the_wire_writes_nothing(monkeypatch):
    sim = sim_mod.SimTable()
    d = tbl.Table(sim_mod.SimTransport(sim))
    real_hold = tbl.hold_stop_signals

    def hold():
        d.request_stop()            # a Ctrl-C arriving between the checks and the write
        return real_hold()
    monkeypatch.setattr(tbl, "hold_stop_signals", hold)
    with pytest.raises(tbl.Stopped):
        d.exchange("identity")
    assert d.t.writes == []


def test_the_stop_signals_are_held_while_a_line_is_written():
    sim = sim_mod.SimTable()
    t = sim_mod.SimTransport(sim)
    seen = []
    real_write = t.write

    def write(data):
        seen.append(signal.SIGINT in signal.pthread_sigmask(signal.SIG_BLOCK, []))
        real_write(data)
    t.write = write
    d = tbl.Table(t)
    d.exchange("identity")
    assert seen == [True]
    assert signal.SIGINT not in signal.pthread_sigmask(signal.SIG_BLOCK, [])


def _drive(sim, lines):
    t = sim_mod.SimTransport(sim)
    for line in lines:
        t.write((line + "\r").encode())
        while t.table.next_time() is not None or t.table.moving:
            t.read(1.0)
    return t


@pytest.mark.parametrize("y", [251, 300, 317, -2])
def test_the_simulator_refuses_a_homing_outside_its_own_guard(y):
    sim = sim_mod.SimTable(pos=[1102.0, float(y)], jitter=False)
    t = _drive(sim, OPEN + [";s022", ";p025"])
    with pytest.raises(sim_mod.SimViolation, match="not a place this copy allows"):
        t.write(b";i12b\r")


def test_the_simulator_refuses_a_move_with_the_arm_free_and_f1_away_from_rest():
    sim = sim_mod.SimTable()
    sim.free_arm = True
    with pytest.raises(sim_mod.SimViolation, match="while the arm is free"):
        sim._physics(";m0044e00fa012c0e")
    sim = sim_mod.SimTable(pos=[1102.0, 1498.0])
    with pytest.raises(sim_mod.SimViolation, match="away from the resting place"):
        sim._physics(";f12e")


def test_the_step_texts_say_what_is_true():
    by = {s.key: s for s in tbl.STEPS}
    for key in ("near", "straight"):
        assert "X 1102, Y 1202" in by[key].beyond and "X 1050, Y 1492" not in by[key].beyond
        assert "holding the arm" in by[key].beyond
    for key in ("straight", "across"):
        assert "seven measuring sessions" in by[key].explain
        assert "without a calibration" in by[key].explain
    free = " ".join(by["free"].beyond.split())
    assert "recorded three times" in free and "twice it worked" in free
    assert "two milliseconds after a button" in free and "status 3 means is not known" in free
    assert "still in the hand-alignment mode" in free
    assert "switches the hand-alignment mode off again" in by["free"].explain
    assert "X 1090 to 1115 and Y up to 250 (up to 25 mm out" in by["home"].beyond
    assert "longer than 2 s" in by["home"].beyond


@pytest.mark.parametrize("y,ok", [(80, True), (81, False), (120, False)])
def test_the_simulator_allows_f1_only_inside_its_own_rest_box(y, ok):
    """The simulator's own REST_GUARD copy (Y -1..80) is what it allows f1 from (planted
    faults widening it survived the first 0.3.1 pass)."""
    sim = sim_mod.SimTable(pos=[1102.0, float(y)], jitter=False)
    if ok:
        sim._physics(";f12e")
    else:
        with pytest.raises(sim_mod.SimViolation, match="away from the resting place"):
            sim._physics(";f12e")
    for x in (1100, 1104):
        with pytest.raises(sim_mod.SimViolation, match="away from the resting place"):
            sim_mod.SimTable(pos=[float(x), 20.0], jitter=False)._physics(";f12e")


def test_the_check_homing_at_rest_from_y49_to_80_keeps_1_1_s(tmp_path):
    d = tbl.Table(sim_mod.SimTransport(sim_mod.SimTable()))
    seen = []
    d._move = lambda key, window: seen.append(window)
    for y, want in ((48, "home_rest"), (49, "home_wide"), (80, "home_wide"), (81, "home_far"),
                    (250, "home_far")):
        d.position_now = (1102, y)
        d._home_from_rest()
        assert seen[-1] == want, y
    assert tbl.TIME_WINDOW["home_wide"] == (0.0, 1.1)


S0, F4, P0, I1, F0, F3, F1 = ";s022", ";f42b", ";p025", ";i12b", ";f02f", ";f32c", ";f12e"


M1498, M2507, M1 = ";m0044e05da012c0b", ";m009cb05da012cda", ";m10b10055b012c42"


B_HF = [S0, P0, I1, S0]


B_ALIGN = [F4, F4, P0, M1498, P0, M2507, P0, M1, P0, S0, F4, F4, F3, F4, F4, F1, F4, F4, P0]


B_PLACE1 = [S0, F4, F4, F4, F4, P0]


B_FIRST = [P0, P0, SPOT_LINES[0], P0]


B_ROW = [x for k in range(1, 28) for x in (P0, SPOT_LINES[k])]


B_PRE_ROW = OPEN + B_HF + B_ALIGN + B_PLACE1 + B_FIRST


def test_part_b_lines_in_the_program_are_the_recorded_ones():
    assert [tbl.WIRE[k].decode().rstrip("\r") for k in tbl.SPOT_KEYS] == SPOT_LINES
    assert tbl.WIRE["m1"] == (M1 + "\r").encode()
    assert sim_mod.SPOTS == SPOT_LINES and sim_mod.M1L == M1
    for line in SPOT_LINES + [M1]:
        assert line[11:15] == "012c"                      # speed 300, as recorded
        assert tbl.checksum_ok(line)
    assert tbl.SPOT_TARGETS[0] == (-1181, 1658) and tbl.SPOT_TARGETS[-1] == (1173, 1663)
    # every target lies inside the area the arm visited in the recordings (m0 envelope
    # X -1320..2507, Y 250..2543; PROTOCOL_v2 5)
    for x, y in tbl.SPOT_TARGETS:
        assert -1320 <= x <= 2507 and 250 <= y <= 2543
    steps = [(b[0] - a[0], b[1] - a[1]) for a, b in zip(tbl.SPOT_TARGETS, tbl.SPOT_TARGETS[1:])]
    assert all(86 <= dx <= 89 and 0 <= dy <= 1 for dx, dy in steps)


def test_the_part_gate_refuses_a_line_of_the_other_part_without_writing():
    d = tbl.Table(sim_mod.SimTransport(sim_mod.SimTable()))
    d.current_step = tbl.B_STEPS[1]
    with pytest.raises(tbl.Doubt):
        d.exchange("m1", "m1")
    assert d.t.writes == []
    d = tbl.Table(sim_mod.SimTransport(sim_mod.SimTable()))
    d.part, d.current_step = "B", tbl.STEPS[1]
    with pytest.raises(tbl.Doubt):
        d.exchange("to_250", "to_250")
    assert d.t.writes == []
    assert all(tbl.WIRE[k] not in tbl.PART_LINES["A"] for k in ("m1",) + tbl.SPOT_KEYS)


def test_part_b_time_windows_are_pinned_from_the_recorded_times():
    w = tbl.TIME_WINDOW
    assert w["m1"] == (0.25, 0.80) and w["first_patch"] == (1.0, 2.4)
    assert w["patch"] == (0.35, 0.70) and w["end_home"] == (1.6, 4.5)
    assert w["home_patch"] == (1.0, 6.0)
    for rec, key in ((0.400, "m1"), (1.456, "first_patch"), (0.431, "patch"), (0.432, "patch"),
                     (2.559, "end_home"), (2.559, "home_patch"), (3.711, "home_patch")):
        lo, hi = w[key]
        assert lo < rec < hi and hi <= 2.0 * rec + 1.5


def test_the_simulator_s_hand_never_pushes_a_held_arm():
    sim = sim_mod.SimTable()
    with pytest.raises(sim_mod.SimViolation, match="the motors hold"):
        sim.hand_to(-1290, 2660)


def _b_sim_at_row(k):
    """A simulator driven by hand (own copy of the lines) to patch k of row 1."""
    sim = sim_mod.SimTable(jitter=False)
    lines = B_PRE_ROW + B_ROW[:2 * (k - 1)]
    t = sim_mod.SimTransport(sim)
    for i, line in enumerate(lines):
        if line == SPOT_LINES[0]:
            pass
        t.write((line + "\r").encode())
        while sim.next_time() is not None or sim.moving:
            t.read(1.0)
        if i == len(OPEN + B_HF + B_ALIGN) - 1:
            sim.hand_to(-1290, 2660)
    return sim, t


def test_the_simulator_refuses_a_patch_move_from_anywhere_but_the_previous_patch():
    sim, t = _b_sim_at_row(3)
    sim.pos = [float(tbl.SPOT_TARGETS[2][0]) + 30, float(tbl.SPOT_TARGETS[2][1])]
    t.write(b";p025\r")
    t.read(1.0)
    with pytest.raises(sim_mod.SimViolation, match="not the previous patch"):
        t.write((SPOT_LINES[3] + "\r").encode())


@pytest.mark.parametrize("x,y", [(-1361, 2650), (-1199, 2650), (-1280, 2599), (-1280, 2701)])
def test_the_simulator_refuses_the_first_patch_move_from_outside_its_own_box(x, y):
    sim = sim_mod.SimTable(jitter=False, pos=[float(x), float(y)])
    sim.free_arm = True
    with pytest.raises(sim_mod.SimViolation, match="not a recorded start"):
        sim._physics(SPOT_LINES[0])
    sim = sim_mod.SimTable(jitter=False, pos=[-1290.0, 2660.0])
    sim.free_arm = True
    sim._physics(SPOT_LINES[0])


@pytest.mark.parametrize("x,y", [(2496, 1498), (2507, 1510), (1102, 1498)])
def test_the_simulator_refuses_m1_from_anywhere_but_the_far_side(x, y):
    sim = sim_mod.SimTable(jitter=False, pos=[float(x), float(y)])
    with pytest.raises(sim_mod.SimViolation, match="not the recorded start"):
        sim._physics(M1)
    sim_mod.SimTable(jitter=False, pos=[2507.0, 1498.0])._physics(M1)


def test_the_simulator_s_part_b_grammar_ends_the_row_at_patch_28():
    states = sim_mod._b_closure({(0, 0, 0)})
    for line in B_PRE_ROW + B_ROW:
        states = sim_mod._b_step(states, line)
        assert states, line
    assert not sim_mod._b_step(states, P0) or not sim_mod._b_step(sim_mod._b_step(states, P0),
                                                                   SPOT_LINES[27])
    for bad in (SPOT_LINES[5], M1, ";m0044e00fa012c0e"):
        assert not sim_mod._b_step(states, bad), bad

