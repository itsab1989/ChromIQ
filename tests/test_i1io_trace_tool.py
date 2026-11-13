"""THE i1iO TESTER PROGRAM CAN SEND ONLY EIGHT RECORDED LINES, AND STOPS ON ANY DOUBT.

`tools/i1io_trace/` is a standalone program for the one tester who owns an
i1iO 2 (issue #129). It moves a real table, so these tests hold its safety
claims in place (work folder 2026-11-13_i1io_trace, SAFETY.md):

* every byte it can write is one of eight lines, each byte-identical to a line
  i1Profiler sent to the tester's table in his recordings;
* any fault in a reply (missing, late, garbled, wrong checksum, another
  command's answer, an error status, an extra line, the cable) stops the run
  and NOTHING more is written, at every point of the run;
* a stop (Ctrl-C, a "stop" or "no" answer) at every point sends nothing more;
* it starts only from the resting place with the motors holding the arm, and
  each movement only from where the previous one ended;
* it is standard-library only and imports nothing from ChromIQ.

No real USB is used anywhere: the simulator and a fake pyusb device.
"""
from __future__ import annotations

import ast
import json
import random
import re
import signal
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
PKG = ROOT / "tools" / "i1io_trace"
sys.path.insert(0, str(PKG))

import i1io_sim as sim_mod  # noqa: E402
import i1io_table as tbl  # noqa: E402
import i1io_trace as prog  # noqa: E402

#: The eight lines, as they appear in the decoded recordings (PROTOCOL.md and
#: the timelines of R1 / R2), byte for byte.
RECORDED = {
    "status": b";s022\r", "identity": b";a133\r", "arm_mode": b";f42b\r",
    "position": b";p025\r", "home": b";i12b\r",
    "out": b";m0044e00fa012c0e\r", "forward": b";m0042204b200c86d\r",
    "approach": b";m0044e04b200c838\r",
}

OPEN = [";a133", ";a133", ";s022", ";f42b", ";p025"]


def _step(motion_line):
    return [";f42b", ";p025", motion_line, ";p025", ";f42b"]


FULL = (OPEN + _step(";i12b") + _step(";m0044e00fa012c0e") + _step(";m0042204b200c86d")
        + _step(";m0044e04b200c838") + _step(";i12b"))
MOTION_LINES = (";i12b", ";m0044e00fa012c0e", ";m0042204b200c86d", ";m0044e04b200c838")
#: The points where a run may end after a stop at a question: after the
#: opening and after each complete step (never between a movement and its checks).
CUTS = {0, 5, 10, 15, 20, 25, 30}

FORBIDDEN_IDS = ("c3", "c4", "d1", "f3", "m1", "m2", "a3", "u8", "k2", "a0", "f0", "f1", "p1")


def _line(cid: str, args: str = "") -> bytes:
    body = ";" + cid + args
    return (body + tbl.checksum(body) + "\r").encode("ascii")


def _run(tmp_path, sim=None, console=None, argv=("--auto",)):
    sim = sim or sim_mod.SimTable()
    log = tmp_path / "log.txt"
    code = prog.main([*argv, "--log", str(log)], sim_table=sim,
                     console=console or prog.AutoConsole(lambda k, t: None))
    return code, sim, log.read_text(encoding="utf-8")


# ---- the eight lines ------------------------------------------------------------------

def test_the_eight_lines_are_byte_identical_to_the_recorded_ones():
    assert tbl.WIRE == RECORDED
    assert tbl.ALLOWED_LINES == frozenset(RECORDED.values())
    for line in RECORDED.values():
        assert tbl.checksum_ok(line.decode("ascii").rstrip("\r"))
        assert tbl.check_outgoing(line) == line[1:3].decode()


@pytest.mark.parametrize("cid", FORBIDDEN_IDS)
@pytest.mark.parametrize("args", ["", "016d", "0042204b200c", "0000600001000", "00"])
def test_the_gate_refuses_every_other_command(cid, args):
    with pytest.raises(tbl.ForbiddenLine):
        tbl.check_outgoing(_line(cid, args))


def test_the_gate_refuses_every_other_move_and_every_other_shape():
    bad = [_line("m0", "044e00fa00c8"),        # the recorded move at another speed
           _line("m0", "044e04b2012c"),
           _line("m0", "03e805dc012c"),        # the recorded way out's second leg
           _line("m0", "0b10055b012c"),
           b";s022", b";s023\r", b";S022\r", b";p025\r;p025\r", b" ;p025\r", b";p025\n",
           b";i12b\r\r", b"", "ä".encode("utf-8"), ";p025\r"]
    for line in bad:
        with pytest.raises(tbl.ForbiddenLine):
            tbl.check_outgoing(line)


def test_twenty_thousand_random_lines_are_refused_unless_they_are_one_of_the_eight():
    rng = random.Random(129)
    alphabet = "0123456789abcdef;:!$\r\nmiaspfc"
    for _ in range(20000):
        if rng.random() < 0.5:
            cid = rng.choice("abcdefmpsiu") + rng.choice("0123456789")
            line = _line(cid, "".join(rng.choice("0123456789abcdef")
                                      for _ in range(rng.choice((0, 2, 4, 12)))))
        else:
            line = "".join(rng.choice(alphabet) for _ in range(rng.randint(0, 20))).encode()
        if line in tbl.ALLOWED_LINES:
            assert tbl.check_outgoing(line)
        else:
            with pytest.raises(tbl.ForbiddenLine):
                tbl.check_outgoing(line)


def _source(name):
    return (PKG / name).read_text(encoding="utf-8")


def test_the_program_has_no_way_to_build_another_command():
    src = _source("i1io_table.py")
    tree = ast.parse(src)
    frames = [n for n in ast.walk(tree) if isinstance(n, ast.Call)
              and getattr(n.func, "id", None) == "_frame"]
    assert len(frames) == 8                    # exactly the eight entries of WIRE
    wire = next(n for n in tree.body if isinstance(n, ast.Assign)
                and getattr(n.targets[0], "id", None) == "WIRE")
    assert all(any(f is c for c in ast.walk(wire)) for f in frames)
    for name in ("i1io_trace.py", "i1io_sim.py"):
        assert "_frame(" not in _source(name)
    # the only writes to a device: Table._write -> transport.write, and the
    # FTDI transport's dev.write, which passes the gate itself first
    assert len(re.findall(r"\.t\.write\(", src)) == 1
    assert len(re.findall(r"self\.dev\.write\(", src)) == 1
    assert "check_outgoing(data)" in src.split("def write(self, data: bytes) -> None:")[2]
    assert len(re.findall(r"ctrl_transfer\(", src)) == 1
    assert "ctrl_transfer" not in _source("i1io_trace.py")
    assert ".write(" not in re.sub(r"(fh|self\.fh)\.write\(", "", _source("i1io_trace.py"))


def test_no_forbidden_command_bytes_anywhere_in_the_package():
    for name in ("i1io_table.py", "i1io_trace.py", "i1io_sim.py"):
        src = _source(name)
        for cid in FORBIDDEN_IDS:
            assert not re.search(rf"[;:][!$]?{cid}[0-9a-f]", src), (name, cid)
            assert f'"{cid}"' not in src and f"'{cid}'" not in src, (name, cid)


STDLIB_OK = {"__future__", "argparse", "datetime", "os", "platform", "signal", "subprocess",
             "sys", "tempfile", "textwrap", "pathlib", "re", "time", "dataclasses", "math",
             "random", "termios", "fcntl"}


def test_standard_library_only_and_nothing_from_chromiq():
    for name in ("i1io_table.py", "i1io_trace.py", "i1io_sim.py"):
        for node in ast.walk(ast.parse(_source(name))):
            if isinstance(node, ast.Import):
                mods = [a.name.split(".")[0] for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                mods = [(node.module or "").split(".")[0]]
            else:
                continue
            for m in mods:
                assert m in STDLIB_OK | {"usb", "i1io_table", "i1io_sim"}, (name, m)


def test_it_runs_on_the_python_macos_ships():
    """macOS's own /usr/bin/python3 is 3.9: no syntax newer than that."""
    for name in ("i1io_table.py", "i1io_trace.py", "i1io_sim.py"):
        ast.parse(_source(name), feature_version=(3, 9))


# ---- a whole run ------------------------------------------------------------------------

def test_a_complete_simulated_run_sends_exactly_the_plan(tmp_path):
    code, sim, log = _run(tmp_path)
    assert code == 0
    assert sim.received == [line.rstrip("\r") for line in FULL]
    assert sim.motions == 5
    assert tbl.HOME_CLUSTER.contains(sim.pos)
    for line in FULL:
        assert "SEND   " in log and line in log
    assert "result 0; 30 lines sent, 5 movements" in log


def test_the_plan_printout_names_every_line_and_nothing_else(capsys):
    assert prog.main(["--plan"]) == 0
    out = capsys.readouterr().out
    sent = set(re.findall(r"^\s+(;[a-z][0-9][0-9a-f]*)\s", out, re.M))
    assert sent == {v.decode().rstrip("\r") for v in tbl.WIRE.values()}
    assert len(re.findall(r"^\s+;", out, re.M)) == len(FULL)


# ---- every fault, at every point: nothing more is sent -----------------------------------

REPLY_FAULTS = ("no_answer", "no_done", "late", "bad_checksum", "garbled", "status",
                "wrong_cid", "stray", "extra_line", "unplug")


@pytest.mark.parametrize("kind", REPLY_FAULTS)
def test_a_bad_reply_at_any_point_stops_and_nothing_more_is_sent(tmp_path, kind):
    for index in range(len(FULL) - (1 if kind == "extra_line" else 0)):
        sim = sim_mod.SimTable()
        sim.inject_at(index, kind, 30.0 if kind == "late" else 0.0)
        code, sim, log = _run(tmp_path, sim)
        assert code == 2, (kind, index, log[-400:])
        # (an extra line after a complete answer is caught by the listening
        # before the next command, which is then not sent)
        assert len(sim.received) == index + 1, (kind, index, sim.received)
        assert sim.received == [x.rstrip("\r") for x in FULL[:len(sim.received)]]
        assert "nothing more is sent" in log


def test_an_extra_line_after_the_last_answer_is_harmless(tmp_path):
    sim = sim_mod.SimTable()
    sim.inject_at(len(FULL) - 1, "extra_line")
    code, sim, _log = _run(tmp_path, sim)
    assert code == 0 and len(sim.received) == len(FULL)


@pytest.mark.parametrize("kind,value", [("blocked", 0.5), ("blocked", 0.0), ("drift", 15.0),
                                        ("drift", -40.0), ("free", 0.0), ("identity", 0.0)])
def test_a_wrong_position_mode_or_identity_stops_and_nothing_more_is_sent(tmp_path, kind, value):
    hits = 0
    for index, line in enumerate(FULL):
        relevant = {"blocked": line in MOTION_LINES,
                    "drift": line == ";p025", "free": line == ";f42b",
                    "identity": line == ";a133"}[kind]
        if not relevant:
            continue
        if kind == "blocked" and line == ";i12b" and index < 10:
            continue                  # homing at home: a blocked homing still ends there
        sim = sim_mod.SimTable()
        sim.inject_at(index, kind, value)
        code, sim, log = _run(tmp_path, sim)
        if kind == "blocked":
            # the movement itself is sent; its arrival check finds the arm short
            assert len(sim.received) == index + 2, (kind, index)
        else:
            assert len(sim.received) == index + 1, (kind, index)
        assert code == 2
        hits += 1
    assert hits


@pytest.mark.parametrize("start", [dict(pos=[1102.0, 250.0]), dict(pos=[1102.0, 1202.0]),
                                   dict(pos=[1058.0, 1202.0]),
                                   dict(pos=[0.0, 1500.0]), dict(pos=[1102.0, 60.0]),
                                   dict(pos=[1090.0, 10.0]), dict(arm="01")])
def test_it_never_moves_unless_the_arm_starts_held_at_its_resting_place(tmp_path, start):
    sim = sim_mod.SimTable(**start)
    code, sim, log = _run(tmp_path, sim)
    assert code == 2 and sim.motions == 0
    assert sim.received == [x.rstrip("\r") for x in OPEN[:len(sim.received)]]
    assert "Nothing was moved" in log


# ---- every stop, at every point ---------------------------------------------------------

def test_ctrl_c_at_every_question_ends_at_a_clean_point_and_sends_nothing_more(tmp_path):
    full = prog.AutoConsole(lambda k, t: None)
    _run(tmp_path, console=full)
    questions = full.asked
    assert questions >= 10
    for q in range(1, questions + 1):
        console = prog.AutoConsole(lambda k, t: None, interrupt_at=q)
        code, sim, log = _run(tmp_path, console=console)
        assert len(sim.received) in CUTS, (q, len(sim.received))
        assert sim.received == [x.rstrip("\r") for x in FULL[:len(sim.received)]]
        assert sim.motions == max(len(sim.received) - 5, 0) // 5


@pytest.mark.parametrize("answer_key,word", [("Is the arm at its resting place", "no"),
                                             ("Is the arm at its resting place", "stop"),
                                             ("Send step 1", "stop"), ("Send step 2", "no"),
                                             ("Send step 3", "stop"), ("Send step 4", "stop"),
                                             ("Send step 5", "no"),
                                             ("described for step 1", "stop"),
                                             ("Does it rest", "stop"),
                                             ("described for step 2", "not sure"),
                                             ("described for step 3", "no"),
                                             ("Does it touch", "touches"),
                                             ("Does it touch", "not sure")])
def test_a_no_or_stop_answer_moves_nothing_more(tmp_path, answer_key, word):
    console = prog.AutoConsole(lambda k, t: None, script={answer_key: word})
    code, sim, log = _run(tmp_path, console=console)
    assert code == 1
    assert len(sim.received) in CUTS
    assert sim.received == [x.rstrip("\r") for x in FULL[:len(sim.received)]]
    if answer_key == "Does it touch":
        assert sim.motions == 2


def _expected_end_after_a_stop_at(index: int) -> int:
    """A stop is honoured before the next line is written, except for the two
    checks right after a movement: so the movement is never sent after a stop,
    and a movement that was sent always gets its arrival checked."""
    if index < 5:
        return index + 1
    k, off = divmod(index - 5, 5)
    return 5 + 5 * k + (off + 1 if off < 2 else 5)


def test_a_stop_signal_during_any_command_ends_after_that_step_never_inside_it(tmp_path):
    for index in range(len(FULL)):
        sim = sim_mod.SimTable()
        box = {}

        def hook(i, box=box, index=index):
            if i == index:
                box["table"].request_stop()       # what the signal handler does while busy
        sim.on_command = hook
        orig = tbl.Table.__init__

        def init(self, *a, orig=orig, box=box, **k):
            orig(self, *a, **k)
            box["table"] = self
        tbl.Table.__init__ = init
        try:
            code, sim, log = _run(tmp_path, sim)
        finally:
            tbl.Table.__init__ = orig
        assert code == 1, index
        n = len(sim.received)
        assert n == _expected_end_after_a_stop_at(index), (index, n)
        assert sim.received == [x.rstrip("\r") for x in FULL[:n]]
        assert sim.motions == sum(1 for x in FULL[:n] if x in MOTION_LINES)
        assert "stopped by you" in log


def test_the_signal_handler_defers_while_busy_and_stops_at_once_otherwise():
    t = tbl.Table(sim_mod.SimTransport())
    old = prog.install_signals(t)
    try:
        handler = signal.getsignal(signal.SIGINT)
        t.busy = 1
        handler(signal.SIGINT, None)
        assert t.stop_requested
        t.busy = 0
        with pytest.raises(KeyboardInterrupt):
            handler(signal.SIGINT, None)
        for name in ("SIGTERM", "SIGHUP", "SIGQUIT"):
            if hasattr(signal, name):
                assert signal.getsignal(getattr(signal, name)) is handler
    finally:
        for sig, h in old.items():
            signal.signal(sig, h)


def test_after_a_stop_or_a_doubt_every_write_is_refused_before_the_wire():
    sim = sim_mod.SimTable()
    t = tbl.Table(sim_mod.SimTransport(sim))
    t.open_checks()
    t.close_for_sending("stopped by you")
    for key in tbl.WIRE:
        with pytest.raises(tbl.Doubt):
            t.exchange(key, 1.0)
    with pytest.raises(tbl.Doubt):
        t.motion(tbl.PLAN[0])
    assert len(sim.received) == 5


# ---- budgets and steps ------------------------------------------------------------------

def test_no_run_can_make_more_movements_or_lines_than_the_plan():
    sim = sim_mod.SimTable()
    t = tbl.Table(sim_mod.SimTransport(sim))
    t.open_checks()
    for _ in range(5):
        t.motion(tbl.PLAN[0])             # homing at home is allowed five times
    with pytest.raises(tbl.Doubt, match="limit of motions"):
        t.motion(tbl.PLAN[0])
    assert sim.motions == 5 and t.closed_reason
    t2 = tbl.Table(sim_mod.SimTransport(sim_mod.SimTable()))
    t2.lines_sent = tbl.MAX_LINES
    with pytest.raises(tbl.Doubt, match="limit of lines"):
        t2.status()


def test_only_the_plans_own_steps_can_be_run():
    sim = sim_mod.SimTable()
    t = tbl.Table(sim_mod.SimTransport(sim))
    t.open_checks()
    fake = tbl.Motion(9, "out", tbl.Box(-9999, 9999, -9999, 9999),
                      tbl.Box(-9999, 9999, -9999, 9999), 8.0, "", "", "")
    with pytest.raises(tbl.Doubt):
        t.motion(fake)
    assert sim.motions == 0 and len(sim.received) == 5


def test_each_step_starts_only_where_the_one_before_ended():
    sim = sim_mod.SimTable()
    t = tbl.Table(sim_mod.SimTransport(sim))
    t.open_checks()
    with pytest.raises(tbl.Doubt, match="not where the step before left it"):
        t.motion(tbl.PLAN[2])             # the forward move, from the resting place
    assert sim.motions == 0


def test_every_target_lies_inside_what_i1profiler_drove_on_this_table():
    """No target is computed or extrapolated: the moves end at (1102, 250),
    (1058, 1202) and (1102, 1202), all recorded m0 targets, inside the
    recorded m0 range X -1320..2507, Y 250..1789."""
    for key in ("out", "forward", "approach"):
        line = tbl.WIRE[key].decode()
        x, y = int(line[3:7], 16), int(line[7:11], 16)
        assert -1320 <= x <= 2507 and 250 <= y <= 1789
    for step in tbl.PLAN:
        for box in (step.start, step.end):
            assert -1320 <= box.xmin and box.xmax <= 2507 and -5 <= box.ymin and box.ymax <= 1789


# ---- the USB side, with a fake pyusb ----------------------------------------------------

class USBError(Exception):
    def __init__(self, msg="", errno=None):
        super().__init__(msg)
        self.errno, self.strerror = errno, msg


class USBTimeoutError(USBError):
    pass


class FakeCore:
    USBError = USBError
    USBTimeoutError = USBTimeoutError


class FakeUtil:
    def __init__(self, fail_claim=False):
        self.calls, self.fail_claim = [], fail_claim

    def claim_interface(self, dev, n):
        if self.fail_claim:
            raise USBError("Access denied", 13)
        self.calls.append(("claim", n))

    def release_interface(self, dev, n):
        self.calls.append(("release", n))

    def dispose_resources(self, dev):
        self.calls.append(("dispose",))


class _EP:
    def __init__(self, addr, attrs=2, size=64):
        self.bEndpointAddress, self.bmAttributes, self.wMaxPacketSize = addr, attrs, size


class _Intf:
    def __init__(self, cls=(0xFF, 0xFF, 0xFF), eps=None):
        self.bInterfaceClass, self.bInterfaceSubClass, self.bInterfaceProtocol = cls
        self._eps = eps if eps is not None else [_EP(0x81), _EP(0x02)]

    def endpoints(self):
        return self._eps


class FakeDev:
    """Speaks to a SimTable in FTDI packets of a few bytes, with status-only
    packets between them. Touching the serial number fails the test."""

    def __init__(self, bcd=0x0400, intfs=None, chunk=5, line_status=0x60):
        self.bcdDevice = bcd
        self._intfs = intfs if intfs is not None else [_Intf()]
        self.sim = sim_mod.SimTable()
        self.t = sim_mod.SimTransport(self.sim)
        self.ctrl, self.chunk, self.line_status = [], chunk, line_status
        self.pending, self.toggle = b"", False

    def __getattr__(self, name):
        if "serial" in name.lower():
            raise AssertionError("the serial number must never be read")
        raise AttributeError(name)

    def __getitem__(self, i):
        assert i == 0
        return self._intfs

    def get_active_configuration(self):
        return object()

    def set_configuration(self):
        raise AssertionError("already configured")

    def ctrl_transfer(self, rt, req, val, idx, data, timeout):
        self.ctrl.append((rt, req, val, idx))

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
        out, self.pending = self.pending[:self.chunk], self.pending[self.chunk:]
        return bytes([0x11, self.line_status]) + out


def _ftdi(dev=None, fail_claim=False):
    dev = dev or FakeDev()
    util = FakeUtil(fail_claim)
    t = tbl.FtdiUsb(dev, FakeCore, util)
    t.setup()
    return dev, util, t


def test_setup_sends_exactly_the_five_recorded_ftdi_requests():
    dev, util, t = _ftdi()
    assert dev.ctrl == [(0x40, 0x00, 0x0000, 0), (0x40, 0x00, 0x0001, 0), (0x40, 0x00, 0x0002, 0),
                        (0x40, 0x03, 0x0034, 0), (0x40, 0x04, 0x0008, 0)]
    assert util.calls == [("claim", 0)]


def test_a_whole_run_over_the_ftdi_path(tmp_path):
    dev, util, t = _ftdi()
    table = tbl.Table(t)
    run = prog.Run(table, prog.AutoConsole(lambda k, tx: None), simulated=True)
    assert run.go() == 0
    assert dev.sim.received == [x.rstrip("\r") for x in FULL]
    t.close()
    assert ("release", 0) in util.calls and ("dispose",) in util.calls


def test_the_ftdi_transport_refuses_any_other_line_itself():
    dev, util, t = _ftdi()
    with pytest.raises(tbl.ForbiddenLine):
        t.write(_line("c3"))
    assert dev.sim.received == []


def test_a_line_error_from_the_chip_stops_everything():
    dev, util, t = _ftdi(FakeDev(line_status=0x68))       # framing error
    table = tbl.Table(t)
    with pytest.raises(tbl.Doubt):
        table.open_checks()
    assert table.closed_reason and len(dev.sim.received) <= 1


@pytest.mark.parametrize("dev", [FakeDev(bcd=0x0600), FakeDev(intfs=[_Intf(), _Intf()]),
                                 FakeDev(intfs=[_Intf(cls=(0xFF, 0, 0))]),
                                 FakeDev(intfs=[_Intf(eps=[_EP(0x81), _EP(0x02, size=512)])]),
                                 FakeDev(intfs=[_Intf(eps=[_EP(0x83), _EP(0x02)])]),
                                 FakeDev(intfs=[_Intf(eps=[_EP(0x81, attrs=3), _EP(0x02)])])])
def test_a_device_that_does_not_look_like_the_recorded_table_gets_nothing(dev):
    with pytest.raises(tbl.NotAvailable, match="Nothing was sent"):
        tbl.check_descriptors(dev)
    assert dev.ctrl == [] and dev.sim.received == []


def test_the_recorded_table_passes_the_descriptor_check():
    tbl.check_descriptors(FakeDev())


def test_a_claim_that_fails_names_the_likely_reason_and_sends_nothing():
    dev = FakeDev()
    with pytest.raises(tbl.TransportError, match="Another program may be using it"):
        _ftdi(dev, fail_claim=True)
    assert dev.ctrl == []


class _FakeUsbModule:
    def __init__(self, devices, nobackend=False):
        self.devices, self.nobackend = devices, nobackend

        class NoBackendError(Exception):
            pass
        self.NoBackendError = NoBackendError
        self.USBError, self.USBTimeoutError = USBError, USBTimeoutError

    def find(self, find_all, idVendor, idProduct, backend):
        assert find_all and (idVendor, idProduct) == (0x0971, 0x2004) and backend == "be"
        if self.nobackend:
            raise self.NoBackendError()
        return iter(self.devices)


def _with_fake_usb(monkeypatch, core, backend="be"):
    import types
    usb = types.ModuleType("usb")
    usb.core, usb.util = core, FakeUtil()
    usb.backend = types.ModuleType("usb.backend")
    usb.backend.libusb1 = types.ModuleType("usb.backend.libusb1")
    usb.backend.libusb1.get_backend = lambda find_library=None: backend
    monkeypatch.setitem(sys.modules, "usb.backend", usb.backend)
    monkeypatch.setitem(sys.modules, "usb.backend.libusb1", usb.backend.libusb1)
    monkeypatch.setitem(sys.modules, "usb", usb)
    monkeypatch.setitem(sys.modules, "usb.core", core)
    monkeypatch.setitem(sys.modules, "usb.util", usb.util)
    monkeypatch.setattr(sys, "platform", "darwin")


@pytest.mark.parametrize("devices,nobackend,match", [([], False, "No i1iO table"),
                                                     ([FakeDev(), FakeDev()], False, "2 devices"),
                                                     ([], True, "no libusb")])
def test_open_table_refuses_none_two_or_no_backend(monkeypatch, devices, nobackend, match):
    _with_fake_usb(monkeypatch, _FakeUsbModule(devices, nobackend))
    with pytest.raises(tbl.NotAvailable, match=match):
        tbl.open_table()
    for d in devices:
        assert d.ctrl == []


def test_no_libusb_at_all_is_refused_before_any_device_is_looked_for(monkeypatch):
    _with_fake_usb(monkeypatch, _FakeUsbModule([FakeDev()]), backend=None)
    monkeypatch.setattr(tbl, "LIBUSB_PATHS", ())
    with pytest.raises(tbl.NotAvailable, match="no libusb"):
        tbl.open_table()


def test_homebrews_libusb_is_used_when_pyusb_does_not_find_one(monkeypatch, tmp_path):
    lib = tmp_path / "libusb-1.0.dylib"
    lib.write_bytes(b"")
    seen = []

    class L:
        @staticmethod
        def get_backend(find_library=None):
            if find_library is None:
                return None
            seen.append(find_library("usb-1.0"))
            return "be"
    monkeypatch.setattr(tbl, "LIBUSB_PATHS", ("/nonexistent/libusb-1.0.dylib", str(lib)))
    assert tbl.libusb_backend(L) == "be" and seen == [str(lib)]


def test_open_table_opens_the_one_recorded_table(monkeypatch):
    dev = FakeDev()
    _with_fake_usb(monkeypatch, _FakeUsbModule([dev]))
    t = tbl.open_table()
    assert len(dev.ctrl) == 5 and dev.sim.received == []
    t.close()


def test_windows_and_linux_are_refused(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "platform", "win32")
    with pytest.raises(tbl.NotAvailable, match="Windows"):
        tbl.open_table()
    monkeypatch.setattr(sys, "platform", "linux")
    with pytest.raises(tbl.NotAvailable, match="only on a Mac"):
        tbl.open_table()

    class Tty:
        def isatty(self):
            return True
    monkeypatch.setattr(sys, "stdin", Tty())
    monkeypatch.setattr(tbl, "open_table", lambda: (_ for _ in ()).throw(AssertionError()))
    assert prog.main(["--real", "--log", str(tmp_path / "l.txt")],
                     console=prog.AutoConsole(lambda k, t: None)) == 2


# ---- the real mode's doors --------------------------------------------------------------

def test_real_mode_refuses_piped_input_before_anything(tmp_path, monkeypatch):
    monkeypatch.setattr(tbl, "open_table", lambda: (_ for _ in ()).throw(AssertionError()))

    class NotTty:
        def isatty(self):
            return False
    monkeypatch.setattr(sys, "stdin", NotTty())
    assert prog.main(["--real", "--log", str(tmp_path / "l.txt")]) == 2


def test_real_mode_asks_its_questions_and_the_sentence_before_opening(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "platform", "darwin")
    opened = []
    monkeypatch.setattr(tbl, "open_table", lambda: opened.append(1) or (_ for _ in ()).throw(
        tbl.NotAvailable("no table here")))
    monkeypatch.setattr(prog, "i1profiler_running", lambda: False)
    monkeypatch.setattr(prog.Lock, "acquire", lambda self: True)

    class Tty:
        def isatty(self):
            return True
    monkeypatch.setattr(sys, "stdin", Tty())
    for script, want_open in (({"power switch": "no"}, False), ({"seated": "no"}, False),
                              ({"empty": "no"}, False), ({}, True)):
        opened.clear()
        con = prog.AutoConsole(lambda k, t: None, script=script)
        code = prog.main(["--real", "--log", str(tmp_path / "l.txt")], console=con)
        assert bool(opened) == want_open, script
        assert code == (2 if want_open else 1)

    class Wrong(prog.AutoConsole):
        def sentence(self, prompt, wanted):
            return False
    opened.clear()
    assert prog.main(["--real", "--log", str(tmp_path / "l.txt")],
                     console=Wrong(lambda k, t: None)) == 1
    assert not opened


def test_real_mode_refuses_while_i1profiler_runs_or_another_copy_runs(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "platform", "darwin")
    monkeypatch.setattr(tbl, "open_table", lambda: (_ for _ in ()).throw(AssertionError()))

    class Tty:
        def isatty(self):
            return True
    monkeypatch.setattr(sys, "stdin", Tty())
    monkeypatch.setattr(prog, "i1profiler_running", lambda: True)
    assert prog.main(["--real", "--log", str(tmp_path / "l.txt")],
                     console=prog.AutoConsole(lambda k, t: None)) == 2
    monkeypatch.setattr(prog, "i1profiler_running", lambda: False)
    monkeypatch.setattr(prog.Lock, "acquire", lambda self: False)
    assert prog.main(["--real", "--log", str(tmp_path / "l.txt")],
                     console=prog.AutoConsole(lambda k, t: None)) == 2


def test_the_lock_lets_only_one_copy_run(tmp_path, monkeypatch):
    monkeypatch.setattr(prog.tempfile, "gettempdir", lambda: str(tmp_path))
    a, b = prog.Lock(), prog.Lock()
    assert a.acquire()
    assert not b.acquire()
    a.release()
    assert b.acquire()
    b.release()


def test_the_confirmation_sentence_must_be_typed(monkeypatch):
    con = prog.Console(lambda k, t: None)
    for typed, ok in (("I understand that this moves my table", True),
                      ("i understand that this moves my table.", True),
                      ("yes", False), ("", False), ("I understand", False)):
        monkeypatch.setattr("builtins.input", lambda prompt, typed=typed: typed)
        assert con.sentence("x", prog.CONFIRM_SENTENCE) is ok


def test_a_question_takes_only_a_whole_word_and_end_of_input_is_no(monkeypatch):
    con = prog.Console(lambda k, t: None)
    answers = iter(["", "y", "ye", "YES"])
    monkeypatch.setattr("builtins.input", lambda prompt: next(answers))
    assert con.ask("q") == "yes"

    def eof(prompt):
        raise EOFError
    monkeypatch.setattr("builtins.input", eof)
    assert con.ask("q") == "no"
    assert con.ask("q", ("yes", "stop")) == "stop"


def test_the_log_holds_every_line_and_no_serial_number(tmp_path):
    code, sim, log = _run(tmp_path)
    assert log.count("SEND   ") == 30 and log.count("RECV   ") == 60
    assert "serial number is never read" in log
    ids = {line[1:3] if line[0] == ";" else line[2:4]
           for line in re.findall(r"(?:SEND|RECV)\s+\S+\s+(\S+)", log)}
    assert ids == {"s0", "a1", "f4", "p0", "i1", "m0"}


def test_unexpected_bytes_are_described_never_copied_into_the_log(tmp_path):
    secret = "SERIAL1234567"
    sim2 = sim_mod.SimTable()
    t = tbl.Table(sim_mod.SimTransport(sim2))
    t._buf = (":$u80" + secret).encode()
    with pytest.raises(tbl.Doubt):
        t.exchange("status", 1.0)
    assert secret not in str(t.closed_reason)


# ---- the zip, run from a clean folder with no ChromIQ on the path -----------------------

def test_the_zip_builds_and_its_simulated_run_works_without_chromiq(tmp_path):
    out = tmp_path / "dist"
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "build_i1io_trace_zip.py"),
                        "--out", str(out)], capture_output=True, text=True,
                       encoding="utf-8", timeout=120)
    assert r.returncode == 0, r.stderr
    zips = list(out.glob("*.zip"))
    assert len(zips) == 1
    with zipfile.ZipFile(zips[0]) as z:
        names = sorted(z.namelist())
        z.extractall(tmp_path / "x")
    top = names[0].split("/")[0]
    assert {f"{top}/{n}" for n in ("i1io_trace.py", "i1io_table.py", "i1io_sim.py",
                                   "README.md", "LICENSE")} <= set(names)
    folder = tmp_path / "x" / top
    work = tmp_path / "clean"
    work.mkdir()
    probe = (
        "import runpy, sys, json\n"
        f"sys.argv = ['i1io_trace.py', '--auto', '--log', 'run.txt']\n"
        "code = 0\n"
        "try:\n"
        f"    runpy.run_path({str(folder / 'i1io_trace.py')!r}, run_name='__main__')\n"
        "except SystemExit as e:\n"
        "    code = e.code\n"
        "bad = sorted(m for m in sys.modules if m.split('.')[0] in "
        "('workflow', 'core', 'ui', 'data', 'scripts', 'PyQt6', 'numpy', 'usb'))\n"
        "print('RESULT', json.dumps({'code': code, 'bad': bad}))\n")
    r = subprocess.run([sys.executable, "-I", "-c", probe], cwd=work, capture_output=True,
                       text=True, encoding="utf-8", timeout=120)
    assert r.returncode == 0, r.stderr
    result = json.loads(r.stdout.rsplit("RESULT ", 1)[1])
    assert result == {"code": 0, "bad": []}
    assert "result 0; 30 lines sent, 5 movements" in (work / "run.txt").read_text(encoding="utf-8")


# ---- after the first challenge (work folder review/CHALLENGE_1.md) ----------------------

class _Creeping(prog.AutoConsole):
    """While the tester answers, the reported Y creeps (challenge finding 2)."""

    def __init__(self, sim, units, only="described for step", **kw):
        super().__init__(lambda k, t: None, **kw)
        self.sim, self.units, self.only = sim, units, only

    def ask(self, question, choices=("yes", "no")):
        if self.only in question:
            sim_mod.creep(self.sim, self.units)
        return super().ask(question, choices)


def test_the_arm_creeping_while_he_answers_does_not_stop_the_run(tmp_path):
    sim = sim_mod.SimTable()
    code, sim, log = _run(tmp_path, sim, console=_Creeping(sim, 40))
    assert code == 0 and sim.motions == 5
    assert "DATA" in log and "starts at" in log


def test_an_arm_that_moved_further_than_creep_between_steps_stops_with_its_own_reason(tmp_path):
    sim = sim_mod.SimTable()
    code, sim, log = _run(tmp_path, sim, console=_Creeping(sim, 70, "described for step 2"))
    assert code == 2 and sim.motions == 2          # home, then out; step 3 refused
    assert "not where the step before left it" in log
    assert sim.received == [x.rstrip("\r") for x in FULL[:17]]


def test_the_power_cycle_advice_comes_only_after_an_unfinished_movement(tmp_path):
    unfinished = FULL.index(";m0044e00fa012c0e")
    sim = sim_mod.SimTable()
    sim.inject_at(unfinished, "no_done")
    code, sim, log = _run(tmp_path, sim)
    assert code == 2 and "switch the table off, wait ten seconds" in log
    assert "keep your hands away from the arm" in log
    assert "do not start this program again" in log
    for kind, index in (("drift", unfinished + 1), ("free", unfinished + 2),
                        ("no_answer", unfinished - 1)):
        sim = sim_mod.SimTable()
        sim.inject_at(index, kind, 40.0)
        code, sim, log = _run(tmp_path, sim)
        assert code == 2 and "wait ten seconds" not in log, kind


class _BrokenRead(sim_mod.SimTransport):
    def __init__(self, at):
        super().__init__()
        self.at, self.n = at, 0

    def read(self, timeout):
        if len(self.table.received) == self.at:
            raise ValueError("a library surprise")
        return super().read(timeout)


def test_an_unexpected_error_still_ends_cleanly_with_advice_and_no_traceback(tmp_path, capsys):
    t = _BrokenRead(FULL.index(";i12b") + 1)
    table = tbl.Table(t)
    r = prog.Run(table, prog.AutoConsole(lambda k, x: None), simulated=True)
    code = r.go()
    r.ending(code)
    out = capsys.readouterr().out
    assert code == 2 and "unexpected error (ValueError)" in out
    assert "start i1Profiler once" in out and "Traceback" not in out
    assert table.closed_reason and len(t.table.received) == FULL.index(";i12b") + 1


class _Ticking:
    """A transport whose reads return nothing after 16 ms, like the FTDI chip's
    status-only packets, and then an unasked line."""

    def __init__(self, stray_after):
        self.clock, self.stray_after, self.writes = 0.0, stray_after, []

    def now(self):
        return self.clock

    def read(self, timeout):
        self.clock += 0.016
        return b":$p00\r" if self.clock >= self.stray_after else b""

    def write(self, data):
        self.writes.append(data)


def test_the_listening_before_a_command_lasts_50_ms_by_the_clock_not_one_read():
    t = _Ticking(stray_after=0.04)
    table = tbl.Table(t)
    with pytest.raises(tbl.Doubt, match="nobody asked for"):
        table.exchange("status", 1.0)
    assert t.writes == [] and t.clock >= 0.04
    t2 = _Ticking(stray_after=99)
    tbl.Table(t2)._quiet_check()
    assert 0.05 <= t2.clock < 0.1


class _Suspended(sim_mod.SimTransport):
    """The clock jumps 60 s during the first read after a movement line, as if
    the process had been stopped with Ctrl-Z and continued later."""

    def __init__(self):
        super().__init__()
        self.jumped = False

    def read(self, timeout):
        data = super().read(timeout)
        if self.writes and self.writes[-1] == RECORDED["out"] and not self.jumped:
            self.jumped = True
            self.table.clock += 60.0
        return data


def test_an_answer_already_waiting_is_read_before_a_timeout_is_declared():
    t = _Suspended()
    table = tbl.Table(t)
    table.open_checks()
    table.motion(tbl.PLAN[0])
    assert table.motion(tbl.PLAN[1])               # no "no answer" after the jump
    assert t.jumped


def test_job_control_stops_are_ignored_while_the_program_runs():
    old = prog.install_signals(tbl.Table(sim_mod.SimTransport()))
    try:
        for name in ("SIGTSTP", "SIGTTIN", "SIGTTOU"):
            if hasattr(signal, name):
                assert signal.getsignal(getattr(signal, name)) == signal.SIG_IGN
    finally:
        for sig, h in old.items():
            signal.signal(sig, h)


def test_a_stop_during_the_opening_sends_no_further_read():
    sim = sim_mod.SimTable()
    t = tbl.Table(sim_mod.SimTransport(sim))
    sim.on_command = lambda i: t.request_stop() if i == 1 else None
    with pytest.raises(tbl.Stopped):
        t.open_checks()
    assert len(sim.received) == 2


def test_set_configuration_only_for_an_unconfigured_device():
    class Unconfigured(FakeDev):
        def get_active_configuration(self):
            raise USBError("Configuration not set")

        def set_configuration(self):
            self.ctrl.append("set_configuration")

    dev, util, t = _ftdi(Unconfigured())
    assert dev.ctrl[0] == "set_configuration" and len(dev.ctrl) == 6

    class Odd(FakeDev):
        def get_active_configuration(self):
            raise USBError("Pipe error")
    dev = Odd()
    with pytest.raises(tbl.TransportError, match="Nothing was sent"):
        _ftdi(dev)
    assert dev.ctrl == []


def test_every_question_offers_stop_and_the_step_question_takes_no(tmp_path):
    seen = []

    class Recorder(prog.AutoConsole):
        def ask(self, question, choices=("yes", "no")):
            seen.append(tuple(choices))
            return super().ask(question, choices)
    _run(tmp_path, console=Recorder(lambda k, t: None))
    assert seen and all("stop" in c for c in seen)
    assert ("yes", "no", "stop") in seen


def test_the_simulator_holds_the_recorded_pairs_not_the_programs_choice():
    """Finding 1: its rules come from the timelines, independently."""
    t = sim_mod.SimTable()
    t.receive(RECORDED["home"])
    t.clock = 5
    with pytest.raises(sim_mod.SimViolation):          # the old unrecorded pair
        sim_mod.SimTable(pos=[1102.0, 250.0]).receive(RECORDED["approach"])
    with pytest.raises(sim_mod.SimViolation):          # forward only from Y 317 or the deviation
        sim_mod.SimTable(pos=[1102.0, 30.0]).receive(RECORDED["forward"])
    sim_mod.SimTable(pos=[1058.0, 317.0]).receive(RECORDED["forward"])     # recorded
    sim_mod.SimTable(pos=[1058.0, 1202.0]).receive(RECORDED["approach"])   # recorded


def test_the_terminal_never_shows_the_full_log_path(tmp_path, capsys, monkeypatch):
    monkeypatch.chdir(tmp_path)
    prog.main(["--auto"], sim_table=sim_mod.SimTable(),
              console=prog.AutoConsole(lambda k, t: None))
    out = capsys.readouterr().out
    assert str(tmp_path) not in out and "The log is in: i1io-trace-" in out


# ---- after the second challenge (review/CHALLENGE_2.md) --------------------------------

@pytest.mark.parametrize("kind", ["no_answer", "bad_checksum", "garbled"])
def test_a_failed_arrival_check_never_reports_the_arm_at_rest(tmp_path, kind):
    """Finding 1: after any movement, a fault on the arrival reading means
    where the arm is is unknown, and the advice says so."""
    for motion in MOTION_LINES:
        for index in [i for i, x in enumerate(FULL) if x == motion]:
            sim = sim_mod.SimTable()
            sim.inject_at(index + 1, kind)
            code, sim, log = _run(tmp_path, sim)
            assert code == 2
            assert len(sim.received) == index + 2
            assert "last reported at its resting place" not in log, (motion, index)
            assert "where it stopped is not known" in log and "start i1Profiler once" in log


def test_a_status_on_a_movement_gives_the_recovery_advice(tmp_path):
    index = FULL.index(";m0044e00fa012c0e")
    sim = sim_mod.SimTable()
    sim.inject_at(index, "status", 3)
    code, sim, log = _run(tmp_path, sim)
    assert code == 2 and "start i1Profiler once" in log
    assert "last reported at its resting place" not in log


def test_i1profiler_started_during_the_run_stops_before_the_next_step(tmp_path):
    calls = []

    def running():
        calls.append(1)
        return len(calls) >= 3            # appears before step 3
    sim = sim_mod.SimTable()
    t = tbl.Table(sim_mod.SimTransport(sim))
    r = prog.Run(t, prog.AutoConsole(lambda k, x: None), simulated=True, sim=sim,
                 other_program=running)
    assert r.go() == 1
    assert sim.motions == 2 and len(sim.received) == 15


def test_an_unwritable_log_folder_is_said_plainly_and_nothing_is_opened(tmp_path, capsys):
    code = prog.main(["--auto", "--log", str(tmp_path / "missing" / "log.txt")],
                     sim_table=sim_mod.SimTable())
    out = capsys.readouterr().out
    assert code == 2 and "cannot be written here" in out and str(tmp_path) not in out


def test_ctrl_c_while_the_advice_is_shown_is_swallowed():
    class Interrupting(prog.AutoConsole):
        def say(self, text=""):
            raise KeyboardInterrupt
    t = tbl.Table(sim_mod.SimTransport())
    t.motions_sent, t.arrival_unknown, t.heading_to = 1, True, (1102, 250)
    prog.Run(t, Interrupting(lambda k, x: None), simulated=True).ending(2)   # no raise


def test_the_main_program_puts_back_the_interrupt_handler_it_found(tmp_path):
    before = signal.getsignal(signal.SIGINT)
    _run(tmp_path)
    assert signal.getsignal(signal.SIGINT) is before
