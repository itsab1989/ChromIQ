"""THE i1iO TESTER PROGRAM CAN SEND ONLY FIVE RECORDED LINES, MOVES ONLY BY ONE
HOMING AT THE RESTING PLACE, AND STOPS ON ANY DOUBT.

`tools/i1io_trace/` is a standalone program for the one tester who owns an
i1iO 2 (issue #129). Version 0.1.0 is the reduced plan decided after the
independent safety review (work folder 2026-11-13_i1io_trace, SAFETY.md): a
read-only opening and one homing (`;i12b`) while the arm is already at rest.
These tests hold its safety claims in place:

* every byte it can write is one of five lines, each byte-identical to a line
  i1Profiler sent to the tester's table; no move command exists in the package;
* any fault in a reply stops the run and NOTHING more is written, at every point;
* a stop (Ctrl-C, "stop"/"no") at every point, including during the listening
  just before a line, sends nothing more except the arrival checks of a
  movement already sent;
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

#: The five lines, as they appear in the decoded recordings, byte for byte.
RECORDED = {
    "identity": b";a133\r", "status": b";s022\r", "arm_mode": b";f42b\r",
    "position": b";p025\r", "home": b";i12b\r",
}

OPEN = [";a133", ";a133", ";s022", ";f42b", ";p025"]
STEP = [";f42b", ";p025", ";i12b", ";p025", ";f42b"]
FULL = OPEN + STEP
MOTION_LINES = (";i12b",)
#: Where a run may end after a stop at a question.
CUTS = {0, 5, 10}

FORBIDDEN_IDS = ("m0", "m1", "m2", "c3", "c4", "d1", "f3", "a3", "u8", "k2", "a0", "f0",
                 "f1", "p1")
#: The plan-A lines of the earlier draft: they must not be anywhere in the package.
PLAN_A_LINES = (";m0044e00fa012c0e", ";m0042204b200c86d", ";m0044e04b200c838")


def _line(cid: str, args: str = "") -> bytes:
    body = ";" + cid + args
    return (body + tbl.checksum(body) + "\r").encode("ascii")


def _run(tmp_path, sim=None, console=None, argv=("--auto",)):
    sim = sim or sim_mod.SimTable()
    log = tmp_path / "log.txt"
    code = prog.main([*argv, "--log", str(log)], sim_table=sim,
                     console=console or prog.AutoConsole(lambda k, t: None))
    return code, sim, log.read_text(encoding="utf-8")


def _source(name):
    return (PKG / name).read_text(encoding="utf-8")


SOURCES = ("i1io_table.py", "i1io_trace.py", "i1io_sim.py", "README.md")


# ---- the five lines -------------------------------------------------------------------

def test_exactly_these_five_lines_can_ever_be_written():
    assert tbl.WIRE == RECORDED
    assert tbl.ALLOWED_LINES == frozenset(RECORDED.values())
    assert tbl.MOTION_LINES == frozenset({b";i12b\r"})
    assert tbl.MAX_MOTIONS == 1 and tbl.MAX_LINES == 12
    for line in RECORDED.values():
        assert tbl.checksum_ok(line.decode("ascii").rstrip("\r"))
        assert tbl.check_outgoing(line) == line[1:3].decode()


@pytest.mark.parametrize("cid", FORBIDDEN_IDS)
@pytest.mark.parametrize("args", ["", "016d", "044e00fa012c", "044e04b200c8", "00"])
def test_the_gate_refuses_every_other_command(cid, args):
    with pytest.raises(tbl.ForbiddenLine):
        tbl.check_outgoing(_line(cid, args))


def test_the_gate_refuses_the_plan_a_moves_and_every_other_shape():
    bad = [x.encode() + b"\r" for x in PLAN_A_LINES] + [
        b";s022", b";s023\r", b";S022\r", b";p025\r;p025\r", b" ;p025\r", b";p025\n",
        b";i12b\r\r", b"", "ä".encode("utf-8"), ";p025\r"]
    for line in bad:
        with pytest.raises(tbl.ForbiddenLine):
            tbl.check_outgoing(line)


def test_twenty_thousand_random_lines_are_refused_unless_they_are_one_of_the_five():
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


def test_the_program_has_no_way_to_build_another_command():
    src = _source("i1io_table.py")
    tree = ast.parse(src)
    frames = [n for n in ast.walk(tree) if isinstance(n, ast.Call)
              and getattr(n.func, "id", None) == "_frame"]
    assert len(frames) == 5                    # exactly the five entries of WIRE
    for f in frames:
        assert len(f.args) == 1 and isinstance(f.args[0], ast.Constant)   # no arguments at all
    wire = next(n for n in tree.body if isinstance(n, ast.Assign)
                and getattr(n.targets[0], "id", None) == "WIRE")
    assert all(any(f is c for c in ast.walk(wire)) for f in frames)
    for name in ("i1io_trace.py", "i1io_sim.py"):
        assert "_frame(" not in _source(name)
    assert len(re.findall(r"\.t\.write\(", src)) == 1
    assert len(re.findall(r"self\.dev\.write\(", src)) == 1
    assert "check_outgoing(data)" in src.split("def write(self, data: bytes) -> None:")[2]
    assert len(re.findall(r"ctrl_transfer\(", src)) == 1
    assert "ctrl_transfer" not in _source("i1io_trace.py")
    assert ".write(" not in re.sub(r"(fh|self\.fh)\.write\(", "", _source("i1io_trace.py"))


def test_no_move_command_and_no_forbidden_bytes_anywhere_in_the_package():
    for name in SOURCES:
        src = _source(name)
        for line in PLAN_A_LINES:
            assert line not in src, (name, line)
        for cid in FORBIDDEN_IDS:
            assert not re.search(rf"[;:][!$]?{cid}[0-9a-f]", src), (name, cid)
            if name != "README.md":
                assert f'"{cid}"' not in src and f"'{cid}'" not in src, (name, cid)


STDLIB_OK = {"__future__", "argparse", "datetime", "os", "platform", "signal", "subprocess",
             "sys", "tempfile", "textwrap", "pathlib", "re", "time", "dataclasses", "math",
             "random", "termios", "fcntl", "ctypes"}


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
    for name in ("i1io_table.py", "i1io_trace.py", "i1io_sim.py"):
        ast.parse(_source(name), feature_version=(3, 9))


# ---- a whole run ------------------------------------------------------------------------

def test_a_complete_simulated_run_sends_exactly_the_plan(tmp_path):
    code, sim, log = _run(tmp_path)
    assert code == 0
    assert sim.received == FULL
    assert sim.motions == 1
    assert tbl.HOMED.contains(sim.pos)
    assert "result 0; 10 lines sent, 1 movements" in log


def test_the_plan_printout_names_every_line_and_nothing_else(capsys):
    assert prog.main(["--plan"]) == 0
    out = capsys.readouterr().out
    sent = set(re.findall(r"^\s+(;[a-z][0-9][0-9a-f]*)\s", out, re.M))
    assert sent == {v.decode().rstrip("\r") for v in tbl.WIRE.values()}
    assert len(re.findall(r"^\s+;", out, re.M)) == len(FULL)


def test_the_two_looks_are_separate_questions_and_the_holder_look_comes_after(tmp_path):
    asked = []

    class Rec(prog.AutoConsole):
        def ask(self, question, choices=("yes", "no")):
            asked.append(question)
            return super().ask(question, choices)
    _run(tmp_path, console=Rec(lambda k, t: None))
    rest = next(i for i, q in enumerate(asked) if "resting place (where" in q)
    empty = next(i for i, q in enumerate(asked) if "completely empty" in q)
    assert rest < empty and "empty" not in asked[rest]
    assert "Does it rest on the white tile" in asked[-1]


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
        assert len(sim.received) == index + 1, (kind, index, sim.received)
        assert sim.received == FULL[:len(sim.received)]
        assert "nothing more is sent" in log


def test_an_extra_line_after_the_last_answer_is_harmless(tmp_path):
    sim = sim_mod.SimTable()
    sim.inject_at(len(FULL) - 1, "extra_line")
    code, sim, _log = _run(tmp_path, sim)
    assert code == 0 and len(sim.received) == len(FULL)


@pytest.mark.parametrize("kind,value", [("blocked", 0.5), ("drift", 15.0), ("drift", -40.0),
                                        ("free", 0.0), ("identity", 0.0)])
def test_a_wrong_position_mode_or_identity_stops_and_nothing_more_is_sent(tmp_path, kind, value):
    hits = 0
    for index, line in enumerate(FULL):
        relevant = {"blocked": line == ";i12b", "drift": line == ";p025",
                    "free": line == ";f42b", "identity": line == ";a133"}[kind]
        if not relevant:
            continue
        sim = sim_mod.SimTable()
        sim.inject_at(index, kind, value)
        code, sim, log = _run(tmp_path, sim)
        if kind == "blocked":
            assert len(sim.received) == index + 2, (kind, index)   # its arrival check
        else:
            assert len(sim.received) == index + 1, (kind, index)
        assert code == 2
        hits += 1
    assert hits


@pytest.mark.parametrize("start", [dict(pos=[1102.0, 250.0]), dict(pos=[1102.0, 1202.0]),
                                   dict(pos=[1058.0, 1202.0]), dict(pos=[0.0, 1500.0]),
                                   dict(pos=[1102.0, 60.0]), dict(pos=[1090.0, 10.0]),
                                   dict(arm="01")])
def test_it_never_moves_unless_the_arm_starts_held_at_its_resting_place(tmp_path, start):
    sim = sim_mod.SimTable(**start)
    code, sim, log = _run(tmp_path, sim)
    assert code == 2 and sim.motions == 0
    assert sim.received == OPEN[:len(sim.received)]
    assert "Nothing was moved" in log


# ---- every stop, at every point ---------------------------------------------------------

def test_ctrl_c_at_every_question_ends_at_a_clean_point_and_sends_nothing_more(tmp_path):
    full = prog.AutoConsole(lambda k, t: None)
    _run(tmp_path, console=full)
    assert full.asked >= 6
    for q in range(1, full.asked + 1):
        console = prog.AutoConsole(lambda k, t: None, interrupt_at=q)
        code, sim, log = _run(tmp_path, console=console)
        assert len(sim.received) in CUTS, (q, len(sim.received))
        assert sim.received == FULL[:len(sim.received)]
        assert sim.motions == (1 if len(sim.received) == 10 else 0)


@pytest.mark.parametrize("answer_key,word", [("Is the arm at its resting place", "no"),
                                             ("Is the arm at its resting place", "stop"),
                                             ("completely empty", "no"),
                                             ("completely empty", "stop"),
                                             ("Send step 1", "stop"), ("Send step 1", "no"),
                                             ("described for step 1", "stop"),
                                             ("described for step 1", "not sure"),
                                             ("Does it rest", "stop")])
def test_a_no_or_stop_answer_moves_nothing_more(tmp_path, answer_key, word):
    console = prog.AutoConsole(lambda k, t: None, script={answer_key: word})
    code, sim, log = _run(tmp_path, console=console)
    assert code == 1
    assert len(sim.received) in CUTS
    assert sim.received == FULL[:len(sim.received)]
    if answer_key in ("Is the arm at its resting place", "completely empty", "Send step 1"):
        assert sim.motions == 0


def _expected_end_after_a_stop_at(index: int) -> int:
    """A stop is honoured before the next line is written, except for the two
    checks right after a movement."""
    if index < 5:
        return index + 1
    off = index - 5
    return 5 + (off + 1 if off < 2 else 5)


def test_a_stop_signal_during_any_command_ends_after_that_command(tmp_path, monkeypatch):
    for index in range(len(FULL)):
        sim = sim_mod.SimTable()
        box = {}
        sim.on_command = lambda i, box=box, index=index: (
            box["table"].request_stop() if i == index else None)
        orig = tbl.Table.__init__

        def init(self, *a, orig=orig, box=box, **k):
            orig(self, *a, **k)
            box["table"] = self
        monkeypatch.setattr(tbl.Table, "__init__", init)
        code, sim, log = _run(tmp_path, sim)
        monkeypatch.setattr(tbl.Table, "__init__", orig)
        assert code == 1, index
        n = len(sim.received)
        assert n == _expected_end_after_a_stop_at(index), (index, n)
        assert sim.received == FULL[:n]
        assert "stopped by you" in log


class _StopAtRead(sim_mod.SimTransport):
    """The safety reviewer's stop fuzz (safety_review/scripts/fuzz_stop.py):
    the stop the signal handler makes arrives during the n-th read, which
    includes every read of the 50 ms listening right before each line."""

    def __init__(self, table, n):
        super().__init__(table)
        self.n, self.reads, self.ref, self.at = n, 0, None, None

    def read(self, timeout):
        self.reads += 1
        if self.reads == self.n and self.ref is not None:
            self.ref.request_stop()
            self.at = len(self.writes)
        return super().read(timeout)


def test_a_stop_during_the_listening_before_a_line_lets_no_line_out():
    """Safety review MAJOR 1: no line may follow a noticed stop, except the
    two arrival checks of a movement that was already sent."""
    n, checked = 1, 0
    while True:
        st = sim_mod.SimTable()
        tr = _StopAtRead(st, n)
        table = tbl.Table(tr)
        tr.ref = table
        r = prog.Run(table, prog.AutoConsole(lambda a, b: None), simulated=True, sim=st)
        code = r.go()
        if tr.at is None:
            break
        after = tr.writes[tr.at:]
        last = tr.writes[tr.at - 1] if tr.at else None
        allowed = []
        if last in tbl.MOTION_LINES:
            allowed = [tbl.WIRE["position"], tbl.WIRE["arm_mode"]]
        elif tr.at >= 2 and tr.writes[tr.at - 2] in tbl.MOTION_LINES \
                and last == tbl.WIRE["position"]:
            allowed = [tbl.WIRE["arm_mode"]]
        assert after == allowed[:len(after)], (n, tr.at, after)
        assert code != 0, n
        n, checked = n + 1, checked + 1
    assert checked >= 20


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
        for name in ("SIGTSTP", "SIGTTIN", "SIGTTOU"):
            if hasattr(signal, name):
                assert signal.getsignal(getattr(signal, name)) == signal.SIG_IGN
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


def test_a_stop_during_the_opening_sends_no_further_read():
    sim = sim_mod.SimTable()
    t = tbl.Table(sim_mod.SimTransport(sim))
    sim.on_command = lambda i: t.request_stop() if i == 1 else None
    with pytest.raises(tbl.Stopped):
        t.open_checks()
    assert len(sim.received) == 2


# ---- budgets and steps ------------------------------------------------------------------

def test_no_run_can_make_more_than_one_movement_or_twelve_lines():
    sim = sim_mod.SimTable()
    t = tbl.Table(sim_mod.SimTransport(sim))
    t.open_checks()
    t.motion(tbl.PLAN[0])
    t.lines_sent = 0                   # so that the movement cap, not the line cap, is hit
    with pytest.raises(tbl.Doubt, match="limit of motions"):
        t.motion(tbl.PLAN[0])
    assert sim.motions == 1 and t.closed_reason
    t2 = tbl.Table(sim_mod.SimTransport(sim_mod.SimTable()))
    t2.lines_sent = tbl.MAX_LINES
    with pytest.raises(tbl.Doubt, match="limit of lines"):
        t2.status()


def test_only_the_plans_own_step_can_be_run():
    sim = sim_mod.SimTable()
    t = tbl.Table(sim_mod.SimTransport(sim))
    t.open_checks()
    fake = tbl.Motion(9, "home", tbl.Box(-9999, 9999, -9999, 9999),
                      tbl.Box(-9999, 9999, -9999, 9999), 8.0, "", "", "")
    with pytest.raises(tbl.Doubt):
        t.motion(fake)
    assert sim.motions == 0 and len(sim.received) == 5


def test_the_homing_is_sent_only_from_the_resting_place_and_must_end_there():
    step = tbl.PLAN[0]
    assert step.key == "home" and step.start == tbl.HOME_CLUSTER
    assert step.end.ymin >= -3 and step.end.ymax <= 5 and step.end.xmin >= 1099
    sim = sim_mod.SimTable()
    sim.inject_at(7, "blocked", 0.5)                 # stops halfway (Y 15)
    t = tbl.Table(sim_mod.SimTransport(sim))
    t.open_checks()
    with pytest.raises(tbl.Doubt, match="not where it was sent"):
        t.motion(step)


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


def test_setup_sends_exactly_the_five_recorded_ftdi_requests_a_few_ms_apart(monkeypatch):
    sleeps = []
    monkeypatch.setattr(tbl.time, "sleep", lambda s: sleeps.append(s))
    dev, util, t = _ftdi()
    assert dev.ctrl == [(0x40, 0x00, 0x0000, 0), (0x40, 0x00, 0x0001, 0), (0x40, 0x00, 0x0002, 0),
                        (0x40, 0x03, 0x0034, 0), (0x40, 0x04, 0x0008, 0)]
    assert util.calls == [("claim", 0)]
    assert sleeps == [tbl.SETUP_GAP_S] * 4 and 0.002 <= tbl.SETUP_GAP_S <= 0.005


def test_a_whole_run_over_the_ftdi_path():
    dev, util, t = _ftdi()
    table = tbl.Table(t)
    run = prog.Run(table, prog.AutoConsole(lambda k, tx: None), simulated=True)
    assert run.go() == 0
    assert dev.sim.received == FULL
    t.close()
    assert ("release", 0) in util.calls and ("dispose",) in util.calls


def test_the_ftdi_transport_refuses_any_other_line_itself():
    dev, util, t = _ftdi()
    with pytest.raises(tbl.ForbiddenLine):
        t.write(_line("m0", "044e00fa012c"))
    assert dev.sim.received == []


def test_a_line_error_from_the_chip_stops_everything():
    dev, util, t = _ftdi(FakeDev(line_status=0x68))
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
    usb.__version__ = "1.2.1"
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


def test_no_libusb_at_all_is_refused(monkeypatch):
    _with_fake_usb(monkeypatch, _FakeUsbModule([FakeDev()]), backend=None)
    monkeypatch.setattr(tbl, "LIBUSB_PATHS", ())
    with pytest.raises(tbl.NotAvailable, match="no libusb"):
        tbl.open_table()
    with pytest.raises(tbl.NotAvailable, match="no libusb"):
        tbl.check_usb_available()


def test_check_usb_available_reports_versions_and_opens_nothing(monkeypatch):
    dev = FakeDev()
    _with_fake_usb(monkeypatch, _FakeUsbModule([dev]))
    info = tbl.check_usb_available()
    assert info.startswith("pyusb 1.2.1; libusb ") and dev.ctrl == []


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


def test_ctrl_c_during_the_ftdi_setup_releases_the_device(monkeypatch):
    class Interrupted(FakeDev):
        def ctrl_transfer(self, *a):
            raise KeyboardInterrupt
    dev = Interrupted()
    core = _FakeUsbModule([dev])
    _with_fake_usb(monkeypatch, core)
    util = sys.modules["usb.util"]
    with pytest.raises(KeyboardInterrupt):
        tbl.open_table()
    assert ("release", 0) in util.calls and ("dispose",) in util.calls


def test_windows_and_linux_are_refused(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "platform", "win32")
    with pytest.raises(tbl.NotAvailable, match="Windows"):
        tbl.open_table()
    with pytest.raises(tbl.NotAvailable, match="Windows"):
        tbl.check_usb_available()
    monkeypatch.setattr(sys, "platform", "linux")
    with pytest.raises(tbl.NotAvailable, match="only on a Mac"):
        tbl.check_usb_available()


# ---- the real mode's doors --------------------------------------------------------------

class _Tty:
    def isatty(self):
        return True


def _real_doors(monkeypatch, opened, usb_ok=True, xrite=()):
    monkeypatch.setattr(sys, "platform", "darwin")
    monkeypatch.setattr(sys, "stdin", _Tty())
    monkeypatch.setattr(prog.Lock, "acquire", lambda self: True)
    monkeypatch.setattr(prog, "xrite_running", lambda: list(xrite))

    def usb():
        if not usb_ok:
            raise tbl.NotAvailable("The real table needs the Python package pyusb")
        return "pyusb 1.2.1; libusb 1.0.29"
    monkeypatch.setattr(tbl, "check_usb_available", usb)
    monkeypatch.setattr(tbl, "open_table", lambda: opened.append(1) or (_ for _ in ()).throw(
        tbl.NotAvailable("no table here")))


def test_real_mode_refuses_piped_input_before_anything(tmp_path, monkeypatch):
    monkeypatch.setattr(tbl, "open_table", lambda: (_ for _ in ()).throw(AssertionError()))

    class NotTty:
        def isatty(self):
            return False
    monkeypatch.setattr(sys, "stdin", NotTty())
    assert prog.main(["--real", "--log", str(tmp_path / "l.txt")]) == 2


def test_real_mode_checks_pyusb_before_any_question(tmp_path, monkeypatch):
    opened = []
    _real_doors(monkeypatch, opened, usb_ok=False)
    con = prog.AutoConsole(lambda k, t: None)
    assert prog.main(["--real", "--log", str(tmp_path / "l.txt")], console=con) == 2
    assert con.asked == 0 and not opened


def test_real_mode_asks_its_questions_and_the_sentence_before_opening(tmp_path, monkeypatch):
    opened = []
    _real_doors(monkeypatch, opened)
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


@pytest.mark.parametrize("name", prog.XRITE_NAMES)
def test_real_mode_refuses_while_an_xrite_program_runs_and_says_how_to_quit_it(
        tmp_path, monkeypatch, name):
    opened = []
    _real_doors(monkeypatch, opened, xrite=(name,))
    con = prog.AutoConsole(lambda k, t: None)
    log = tmp_path / "l.txt"
    assert prog.main(["--real", "--log", str(log)], console=con) == 2
    text = log.read_text(encoding="utf-8")
    assert not opened and con.asked == 0
    assert name in text and "restart your Mac" in text and "Nothing was sent" in text


def test_the_xrite_names_are_the_ones_i1profiler_installs():
    assert prog.XRITE_NAMES == ("i1Profiler", "i1ProfilerTray", "xrdd")
    assert "com.xrite.device.xrdd.plist" in prog.XRITE_HOWTO
    assert "com.xrite.i1Profiler.tray.plist" in prog.XRITE_HOWTO


def test_real_mode_refuses_while_another_copy_runs(tmp_path, monkeypatch):
    opened = []
    _real_doors(monkeypatch, opened)
    monkeypatch.setattr(prog.Lock, "acquire", lambda self: False)
    assert prog.main(["--real", "--log", str(tmp_path / "l.txt")],
                     console=prog.AutoConsole(lambda k, t: None)) == 2
    assert not opened


def test_an_xrite_program_started_during_the_run_stops_it_before_the_homing(tmp_path):
    calls = []
    sim = sim_mod.SimTable()
    t = tbl.Table(sim_mod.SimTransport(sim))
    r = prog.Run(t, prog.AutoConsole(lambda k, x: None), simulated=True, sim=sim,
                 other_program=lambda: calls.append(1) or True)
    assert r.go() == 1
    assert sim.motions == 0 and len(sim.received) == 5 and calls


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


def test_a_question_takes_only_a_whole_word_and_end_of_input_is_the_last_choice(monkeypatch):
    con = prog.Console(lambda k, t: None)
    answers = iter(["", "y", "ye", "YES"])
    monkeypatch.setattr("builtins.input", lambda prompt: next(answers))
    assert con.ask("q") == "yes"

    def eof(prompt):
        raise EOFError
    monkeypatch.setattr("builtins.input", eof)
    assert con.ask("q") == "no"
    assert con.ask("q", ("yes", "stop")) == "stop"


def test_every_question_offers_stop(tmp_path):
    seen = []

    class Recorder(prog.AutoConsole):
        def ask(self, question, choices=("yes", "no")):
            seen.append(tuple(choices))
            return super().ask(question, choices)
    _run(tmp_path, console=Recorder(lambda k, t: None))
    assert seen and all("stop" in c for c in seen)


# ---- texts and the log --------------------------------------------------------------------

def test_the_stop_promise_is_worded_truthfully_everywhere():
    for text in (prog.STOP_PROMISE, _source("README.md")):
        assert "never starts a movement" in text or "never start" in text
        assert "only the power switch or plug" in text.replace("\n", " ") or \
            "Only the power switch or plug" in text.replace("\n", " ")
    assert "never cuts a movement in half" not in _source("README.md")
    assert "USB" in prog.PLUG and "does not" in prog.PLUG


def test_the_short_power_switch_line_comes_right_before_the_homing_question(tmp_path):
    code, sim, log = _run(tmp_path)
    lines = log.splitlines()
    ask = next(i for i, x in enumerate(lines) if "Send step 1 now?" in x)
    assert prog.PLUG_SHORT in lines[ask - 1]


def test_the_homing_text_names_the_lines_it_leaves_out():
    text = tbl.PLAN[0].recorded
    for word in ("k2", "two u8", "a0", "error reply", "harmless stop"):
        assert word in text
    assert "in this same situation" not in text


def test_the_log_holds_every_line_and_no_serial_number(tmp_path):
    code, sim, log = _run(tmp_path)
    assert log.count("SEND   ") == 10 and log.count("RECV   ") == 20
    assert "serial number is never read" in log
    ids = {line[1:3] if line[0] == ";" else line[2:4]
           for line in re.findall(r"(?:SEND|RECV)\s+\S+\s+(\S+)", log)}
    assert ids == {"s0", "a1", "f4", "p0", "i1"}


def test_unexpected_bytes_are_described_never_copied_into_the_log():
    secret = "SERIAL1234567"
    t = tbl.Table(sim_mod.SimTransport(sim_mod.SimTable()))
    t._buf = (":$u80" + secret).encode()
    with pytest.raises(tbl.Doubt):
        t.exchange("status", 1.0)
    assert secret not in str(t.closed_reason)


def test_the_power_cycle_advice_comes_only_after_an_unfinished_movement(tmp_path):
    homing = FULL.index(";i12b")
    sim = sim_mod.SimTable()
    sim.inject_at(homing, "no_done")
    code, sim, log = _run(tmp_path, sim)
    assert code == 2 and "switch the table off, wait ten seconds" in log
    assert "keep your hands away from the arm when you switch it on again" in log
    for kind, index in (("drift", homing + 1), ("free", homing + 2), ("no_answer", homing - 1)):
        sim = sim_mod.SimTable()
        sim.inject_at(index, kind, 40.0)
        code, sim, log = _run(tmp_path, sim)
        assert code == 2 and "wait ten seconds" not in log, kind


@pytest.mark.parametrize("kind", ["no_answer", "bad_checksum", "garbled"])
def test_a_failed_arrival_check_never_reports_the_arm_at_rest(tmp_path, kind):
    homing = FULL.index(";i12b")
    sim = sim_mod.SimTable()
    sim.inject_at(homing + 1, kind)
    code, sim, log = _run(tmp_path, sim)
    assert code == 2 and len(sim.received) == homing + 2
    assert "last reported at its resting place" not in log
    assert "where it stopped is not known" in log and "start i1Profiler once" in log


class _BrokenRead(sim_mod.SimTransport):
    def __init__(self, at):
        super().__init__()
        self.at = at

    def read(self, timeout):
        if len(self.table.received) == self.at:
            raise ValueError("a library surprise")
        return super().read(timeout)


def test_an_unexpected_error_still_ends_cleanly_with_advice_and_no_traceback(capsys):
    t = _BrokenRead(FULL.index(";i12b") + 1)
    table = tbl.Table(t)
    r = prog.Run(table, prog.AutoConsole(lambda k, x: None), simulated=True)
    code = r.go()
    r.ending(code)
    out = capsys.readouterr().out
    assert code == 2 and "unexpected error (ValueError)" in out
    assert "start i1Profiler once" in out and "Traceback" not in out


class _Ticking:
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
    with pytest.raises(tbl.Doubt, match="nobody asked for"):
        tbl.Table(t).exchange("status", 1.0)
    assert t.writes == [] and t.clock >= 0.04
    t2 = _Ticking(stray_after=99)
    tbl.Table(t2)._quiet_check()
    assert 0.05 <= t2.clock < 0.1


class _Suspended(sim_mod.SimTransport):
    """The clock jumps 60 s during the first read after the homing line."""

    def __init__(self):
        super().__init__()
        self.jumped = False

    def read(self, timeout):
        data = super().read(timeout)
        if self.writes and self.writes[-1] == RECORDED["home"] and not self.jumped:
            self.jumped = True
            self.table.clock += 60.0
        return data


def test_an_answer_already_waiting_is_read_before_a_timeout_is_declared():
    t = _Suspended()
    table = tbl.Table(t)
    table.open_checks()
    assert table.motion(tbl.PLAN[0])
    assert t.jumped


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
    t.motions_sent, t.arrival_unknown, t.heading_to = 1, True, (1102, 0)
    prog.Run(t, Interrupting(lambda k, x: None), simulated=True).ending(2)


def test_the_main_program_puts_back_the_interrupt_handler_it_found(tmp_path):
    before = signal.getsignal(signal.SIGINT)
    _run(tmp_path)
    assert signal.getsignal(signal.SIGINT) is before


def test_the_terminal_never_shows_the_full_log_path(tmp_path, capsys, monkeypatch):
    monkeypatch.chdir(tmp_path)
    prog.main(["--auto"], sim_table=sim_mod.SimTable(),
              console=prog.AutoConsole(lambda k, t: None))
    out = capsys.readouterr().out
    assert str(tmp_path) not in out and "The log is in: i1io-trace-" in out


def test_the_simulator_refuses_any_move_and_a_second_homing():
    with pytest.raises(sim_mod.SimViolation):
        sim_mod.SimTable().receive(_line("m0", "044e00fa012c"))
    with pytest.raises(sim_mod.SimViolation):
        sim_mod.SimTable(pos=[1102.0, 250.0]).receive(RECORDED["home"])
    t = sim_mod.SimTable()
    t.receive(RECORDED["home"])
    t.clock = 5
    with pytest.raises(sim_mod.SimViolation, match="second i1"):
        t.receive(RECORDED["home"])


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
        blob = b"".join(z.read(n) for n in names)
        z.extractall(tmp_path / "x")
    for line in PLAN_A_LINES:
        assert line.encode() not in blob
    top = names[0].split("/")[0]
    assert {f"{top}/{n}" for n in ("i1io_trace.py", "i1io_table.py", "i1io_sim.py",
                                   "README.md", "LICENSE")} <= set(names)
    folder = tmp_path / "x" / top
    work = tmp_path / "clean"
    work.mkdir()
    probe = (
        "import runpy, sys, json\n"
        "sys.argv = ['i1io_trace.py', '--auto', '--log', 'run.txt']\n"
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
    assert "result 0; 10 lines sent, 1 movements" in (work / "run.txt").read_text(encoding="utf-8")
