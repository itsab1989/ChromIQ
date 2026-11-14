"""THE i1iO TESTER PROGRAM 0.2.0 SENDS ONLY THE TWELVE RECORDED LINES OF BYTES.md,
IN THE RECORDED ORDER, AND STOPS ON ANY DOUBT.

`tools/i1io_open/` is a standalone program for the one tester who owns an i1iO 2
(issue #129). It opens the table the way i1Profiler does (cold: with the start-up
line i0; warm: without), sends the arm to its resting place where it already is,
and closes the table the way i1Profiler does. These tests hold its safety claims:

* BYTES.md and the program's own list agree byte for byte; every write on every
  path, with every injected fault, is in that list;
* the simulated table, which carries its own copy of the recorded sequences,
  never sees a line out of place (it raises on the spot);
* any fault in a reply stops the run and NOTHING more is written;
* a stop (Ctrl-C, "stop"/"no") at every point sends nothing more;
* the table's memory answers (its serial number) never reach the log or screen;
* it is standard-library only and imports nothing from ChromIQ.

No real USB is used anywhere: the simulator and a fake pyusb device.
"""
from __future__ import annotations

import ast
import re
import signal
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
PKG = ROOT / "tools" / "i1io_open"
sys.path.insert(0, str(PKG))

import i1io_open_table as tbl  # noqa: E402
import i1io_open_sim as sim_mod  # noqa: E402
import i1io_open as prog  # noqa: E402

#: The twelve lines, written out here as they appear in the decoded recordings.
RECORDED = {
    ";a133", ";k228", ";u8000060000100d1", ";u8000061000068c3", ";a034", ";i02c",
    ";s022", ";f42b", ";p025", ";i12b", ";f02f", ";f32c",
}
OPEN = [";a133", ";a133", ";k228", ";u8000060000100d1", ";u8000061000068c3", ";a034"]
FOLLOW = [";s022", ";f42b", ";f42b", ";f42b", ";f42b", ";s022", ";p025"]
HOMING = [";i12b", ";s022", ";p025"]
CLOSING = [";s022", ";f02f", ";f32c"]
COLD = OPEN + [";i02c"] + FOLLOW + HOMING + CLOSING
WARM = OPEN + FOLLOW + HOMING + CLOSING
MOTIONS = {";i02c", ";i12b"}
FORBIDDEN_IDS = ("m0", "m1", "m2", "c3", "c4", "d1", "a3", "f1", "p1")


def _bytes_md_lines():
    """The allow-list as BYTES.md states it: line -> hex column."""
    text = (PKG / "BYTES.md").read_text(encoding="utf-8")
    section = text.split("## Lines to the table", 1)[1].split("\n## ", 1)[0]
    rows = re.findall(r"^\| (\d+) \| `([^`]+)` \| `([0-9a-f ]+)` \|", section, re.M)
    return {line: hx for _, line, hx in rows}


ALLOWED = {(line + "\r").encode("ascii") for line in _bytes_md_lines()}


def _run(tmp_path, sim=None, console=None, argv=("--auto",)):
    sim = sim or sim_mod.SimTable(cold=True)
    log = tmp_path / "log.txt"
    code = prog.main([*argv, "--log", str(log)], sim_table=sim,
                     console=console or prog.AutoConsole(lambda k, t: None))
    return code, sim, log.read_text(encoding="utf-8")


def _source(name):
    return (PKG / name).read_text(encoding="utf-8")


SOURCES = ("i1io_open_table.py", "i1io_open.py", "i1io_open_sim.py", "README.md", "BYTES.md")


# ---- the allow-list -------------------------------------------------------------------

def test_bytes_md_lists_exactly_the_programs_twelve_lines():
    listed = _bytes_md_lines()
    assert set(listed) == RECORDED
    assert {v.decode("ascii").rstrip("\r") for v in tbl.WIRE.values()} == RECORDED
    assert tbl.ALLOWED_LINES == ALLOWED
    for line, hx in listed.items():
        assert bytes.fromhex(hx.replace(" ", "")) == (line + "\r").encode("ascii"), line


def test_every_line_has_a_valid_checksum_and_one_cr():
    for line in tbl.WIRE.values():
        assert line.endswith(b"\r") and line.count(b"\r") == 1
        assert tbl.checksum_ok(line[:-1].decode("ascii"))


def test_every_line_names_where_it_was_recorded():
    assert set(tbl.RECORDED_AT) == set(tbl.WIRE)
    for key, where in tbl.RECORDED_AT.items():
        assert re.search(r"\b(S1|R1|R2)\b", where), key


def test_the_gate_refuses_every_other_line():
    for bad in (b";m0044e00fa012c0e\r", b";c32f\r", b";c42e\r", b";d1016d35\r", b";f12e\r",
                b";a133", b";a133\r\r", b";A133\r", b";i12b\n", b"", b";p124\r",
                b";u8000060000200d0\r"):
        with pytest.raises(tbl.ForbiddenLine):
            tbl.check_outgoing(bad)


def test_no_move_or_unknown_command_exists_anywhere_in_the_package():
    for name in ("i1io_open_table.py", "i1io_open.py", "i1io_open_sim.py"):
        src = _source(name)
        for cid in FORBIDDEN_IDS:
            assert f";{cid}" not in src, (name, cid)
            assert f'_frame("{cid}"' not in src, (name, cid)
    frames = re.findall(r'_frame\("([a-z][0-9])"', _source("i1io_open_table.py"))
    assert sorted(set(frames)) == sorted({"a1", "k2", "u8", "a0", "i0", "s0", "f4", "p0", "i1",
                                          "f0", "f3"})
    # nothing builds a line from numbers: _frame is only called at import, in WIRE
    tree = ast.parse(_source("i1io_open_table.py"))
    calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call)
             and getattr(n.func, "id", None) == "_frame"]
    assert all(all(isinstance(a, ast.Constant) for a in c.args) for c in calls)
    assert len(calls) == 12


def test_the_program_writes_only_in_one_place_and_through_the_gate():
    src = _source("i1io_open_table.py")
    assert src.count("self.t.write(") == 1
    assert src.count("self.dev.write(") == 1
    assert len(re.findall(r"ctrl_transfer\(", src)) == 1
    assert "ctrl_transfer" not in _source("i1io_open.py")
    assert ".write(" not in _source("i1io_open.py").replace("fh.write(", "")


def test_standard_library_only_and_nothing_from_chromiq():
    allowed = {"__future__", "argparse", "datetime", "platform", "signal", "subprocess", "sys",
               "tempfile", "textwrap", "pathlib", "re", "time", "dataclasses", "math", "random",
               "os", "ctypes", "termios", "fcntl", "usb", "i1io_open_table", "i1io_open_sim"}
    for name in ("i1io_open_table.py", "i1io_open.py", "i1io_open_sim.py"):
        tree = ast.parse(_source(name))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                mods = [a.name.split(".")[0] for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                mods = [(node.module or "").split(".")[0]]
            else:
                continue
            for m in mods:
                assert m in allowed, (name, m)


def test_the_simulator_does_not_import_the_programs_sequences():
    src = _source("i1io_open_sim.py")
    assert "WIRE" not in src and "from i1io_open_table import TransportError, checksum, checksum_ok" in src
    assert sim_mod.REC_COLD == COLD and sim_mod.REC_WARM == WARM


# ---- the two clean paths -----------------------------------------------------------------

def test_a_cold_table_gets_the_recorded_cold_open_start_homing_and_close(tmp_path):
    code, sim, log = _run(tmp_path, sim_mod.SimTable(cold=True))
    assert code == 0
    assert sim.received == COLD and len(COLD) == tbl.MAX_LINES
    assert sim.motions == 2
    assert "result 0; table cold; 20 lines sent, 2 movements; closed yes" in log


def test_a_warm_table_gets_no_i0(tmp_path):
    code, sim, log = _run(tmp_path, sim_mod.SimTable(cold=False), argv=("--auto", "--sim", "warm"))
    assert code == 0
    assert sim.received == WARM and ";i02c" not in sim.received
    assert "result 0; table warm; 19 lines sent, 1 movements; closed yes" in log


def test_i0_waits_for_the_persons_yes(tmp_path):
    con = prog.AutoConsole(lambda k, t: None, script={"Send it now": "no"})
    code, sim, log = _run(tmp_path, sim_mod.SimTable(cold=True), console=con)
    assert code == 1 and sim.received == OPEN
    assert "The table has not been started" in log


def test_the_homing_on_a_warm_table_waits_for_the_persons_yes(tmp_path):
    con = prog.AutoConsole(lambda k, t: None, script={"Send it now": "stop"})
    code, sim, _ = _run(tmp_path, sim_mod.SimTable(cold=False), console=con)
    assert code == 1 and sim.received == OPEN + FOLLOW


def test_a_cold_table_whose_arm_was_not_parked_would_be_caught_by_the_simulator():
    # the program relies on the person's answer here; the simulator proves the
    # rule is enforced on its side (and that the tests would see a violation)
    sim = sim_mod.SimTable(cold=True, parked=False)
    t = sim_mod.SimTransport(sim)
    for line in OPEN:
        t.write((line + "\r").encode())
    with pytest.raises(sim_mod.SimViolation):
        t.write(b";i02c\r")


def test_the_arm_not_seen_at_rest_means_no_closing(tmp_path):
    con = prog.AutoConsole(lambda k, t: None, script={"Is the arm at": "no"})
    code, sim, _ = _run(tmp_path, sim_mod.SimTable(cold=True), console=con)
    assert code == 1 and sim.received == COLD[:-3]


# ---- every fault stops everything ------------------------------------------------------------

#: Faults that only make sense on one command (anything else ignores them).
ONLY_FOR = {"identity": "a1", "k2_other": "k2", "a0_other": "a0", "memory_short": "u8",
            "memory_bad_start": "u8", "free": "f4",
            "drift": "p0", "blocked": "i", "slow_motion": "i"}
VALUES = {"drift": 200.0, "blocked": 0.5, "late": 30.0, "status": 3.0, "refuse": 1.0}


def _applies(kind, line):
    cid = line[1:3]
    want = ONLY_FOR.get(kind)
    if want is None:
        return True
    if kind == "memory_bad_start":
        return line == ";u8000060000100d1"
    return cid.startswith(want)


@pytest.mark.parametrize("cold", (True, False), ids=("cold", "warm"))
@pytest.mark.parametrize("kind", sim_mod.FAULT_KINDS)
def test_any_fault_at_any_line_stops_with_nothing_more_sent(tmp_path, cold, kind):
    seq = COLD if cold else WARM
    for index, line in enumerate(seq):
        sim = sim_mod.SimTable(cold=cold, seed=index)
        sim.inject_at(index, kind, VALUES.get(kind, 0.0))
        code, sim, log = _run(tmp_path, sim, argv=("--auto", "--sim", "cold" if cold else "warm"))
        assert all((r + "\r").encode() in ALLOWED for r in sim.received)
        assert sim.received == seq[:len(sim.received)]
        if _applies(kind, line):
            assert code == 2, (kind, index, line)
            # a movement that ends in the wrong place is seen at the next p0
            stop_at = seq.index(";p025", index) if kind == "blocked" else index
            assert len(sim.received) == stop_at + 1, (kind, index, line, sim.received)
            if index < len(seq) - 1:
                assert "closed yes" not in log
        else:
            assert code == 0, (kind, index, line)
            assert sim.received == seq
        assert sim_mod.FAKE_SERIAL not in log
        assert sim_mod.FAKE_SERIAL.encode().hex().upper() not in log


def test_a_reply_that_comes_slowly_but_in_time_is_fine(tmp_path):
    sim = sim_mod.SimTable(cold=True)
    sim.inject("late", "s0", 0.5)                 # 0.5 s, the limit is 1 s
    code, sim, _ = _run(tmp_path, sim)
    assert code == 0 and sim.received == COLD


def test_a_start_up_that_takes_far_longer_than_recorded_stops_before_anything_else(tmp_path):
    sim = sim_mod.SimTable(cold=True)
    sim.inject("slow_motion", "i0")
    code, sim, log = _run(tmp_path, sim)
    assert code == 2 and sim.received == OPEN + [";i02c"]
    assert "i0 took" in log


def test_an_unknown_a0_answer_stops_right_after_a0(tmp_path):
    sim = sim_mod.SimTable(cold=True)
    sim.inject("a0_other", "a0")
    code, sim, log = _run(tmp_path, sim)
    assert code == 2 and sim.received == OPEN
    assert "120000" in log


def test_the_refusal_seen_on_the_tester_table_stops_with_a_plain_message(tmp_path):
    sim = sim_mod.SimTable(cold=False)
    sim.inject("refuse", "s0", 1)
    code, sim, log = _run(tmp_path, sim, argv=("--auto", "--sim", "warm"))
    assert code == 2 and sim.received == OPEN + [";s022"]
    assert "refused the line ;s022 (code 1)" in log


def test_the_cable_pulled_after_every_line(tmp_path):
    for cold, seq in ((True, COLD), (False, WARM)):
        for index in range(len(seq)):
            sim = sim_mod.SimTable(cold=cold)
            sim.inject_at(index, "unplug")
            code, sim, _ = _run(tmp_path, sim)
            assert code == 2 and len(sim.received) == index + 1


# ---- stopping --------------------------------------------------------------------------------

@pytest.mark.parametrize("cold", (True, False), ids=("cold", "warm"))
def test_ctrl_c_during_any_exchange_sends_nothing_more(tmp_path, cold):
    seq = COLD if cold else WARM
    for index in range(len(seq)):
        sim = sim_mod.SimTable(cold=cold)

        def hook(i, index=index):
            if i == index:
                signal.raise_signal(signal.SIGINT)
        sim.on_command = hook
        code, sim, log = _run(tmp_path, sim, argv=("--auto", "--sim", "cold" if cold else "warm"))
        assert len(sim.received) == index + 1, (index, sim.received)
        if index < len(seq) - 1:
            assert code == 1, index
            assert "stopped by you" in log
        else:
            assert code in (0, 1)      # after the last line there is nothing left to stop


@pytest.mark.parametrize("cold", (True, False), ids=("cold", "warm"))
def test_stop_or_ctrl_c_at_every_question_sends_nothing_more(tmp_path, cold):
    for n in range(1, 8):
        sim = sim_mod.SimTable(cold=cold)
        con = prog.AutoConsole(lambda k, t: None, interrupt_at=n)
        code, sim, _ = _run(tmp_path, sim, console=con,
                            argv=("--auto", "--sim", "cold" if cold else "warm"))
        sent = len(sim.received)
        if code == 0:
            assert sim.received == (COLD if cold else WARM)
            continue
        assert code == 1
        # the run ends at a question: right before a movement, or before the closing
        assert sim.received == (COLD if cold else WARM)[:sent]
        assert sent in ((6, 17) if cold else (13, 16))


# ---- privacy ---------------------------------------------------------------------------------

def test_the_memory_answers_never_reach_the_log_or_the_screen(tmp_path, capsys):
    code, sim, log = _run(tmp_path, sim_mod.SimTable(cold=True))
    out = capsys.readouterr().out
    for text in (log, out):
        assert sim_mod.FAKE_SERIAL not in text
        assert sim_mod.FAKE_SERIAL.encode().hex().upper() not in text
        assert "not written down" in text
    assert "6801000056312E31" not in log


def test_a_damaged_memory_answer_is_described_never_echoed(tmp_path):
    for kind in ("bad_checksum_memory", "memory_short", "memory_bad_start"):
        sim = sim_mod.SimTable(cold=True)
        sim.inject(kind, "u8")
        code, sim, log = _run(tmp_path, sim)
        assert code == 2
        assert sim_mod.FAKE_SERIAL.encode().hex().upper() not in log
        assert sim_mod.FAKE_SERIAL not in log


def test_show_never_echoes_long_or_memory_lines():
    assert tbl.show(":$s00CF") == "':$s00CF'"
    assert "bytes" in tbl.show(":$u80" + "AB" * 30)
    assert "bytes" in tbl.show(":$u80AB")
    assert "bytes" in tbl.show("X" * 40)


# ---- plan and dry run ------------------------------------------------------------------------

def test_plan_and_dry_run_show_every_line_and_send_nothing(capsys):
    assert prog.main(["--plan"]) == 0
    plan = capsys.readouterr().out
    assert prog.main(["--dry-run"]) == 0
    dry = capsys.readouterr().out
    for line in RECORDED:
        assert line in plan and line in dry
        assert (line + "\r").encode().hex(" ") in dry
    shown = set(re.findall(r";[a-z][0-9][0-9a-f]*", plan + dry))
    assert shown == RECORDED


# ---- the USB layer (a fake pyusb device; no real USB) ---------------------------------------

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
    util = FakeUtil()
    t = tbl.FtdiUsb(dev, FakeCore, util)
    t.setup()
    return util, t


def test_setup_sends_exactly_the_five_recorded_ftdi_requests(monkeypatch):
    monkeypatch.setattr(tbl.time, "sleep", lambda s: None)
    dev = FakeDev()
    util, t = _ftdi(dev)
    assert dev.ctrl == [(0x40, 0x00, 0x0000, 0, None), (0x40, 0x00, 0x0001, 0, None),
                        (0x40, 0x00, 0x0002, 0, None), (0x40, 0x03, 0x0034, 0, None),
                        (0x40, 0x04, 0x0008, 0, None)]
    assert util.calls == [("claim", 0)]


@pytest.mark.parametrize("cold", (True, False), ids=("cold", "warm"))
def test_a_whole_run_over_the_ftdi_path_with_the_long_memory_answer_in_packets(monkeypatch, cold):
    monkeypatch.setattr(tbl.time, "sleep", lambda s: None)
    dev = FakeDev(cold=cold)
    util, t = _ftdi(dev)
    table = tbl.Table(t)
    run = prog.Run(table, prog.AutoConsole(lambda k, tx: None), simulated=True)
    assert run.go() == 0
    assert dev.sim.received == (COLD if cold else WARM)
    t.close()
    assert ("release", 0) in util.calls and ("dispose",) in util.calls


def test_the_ftdi_transport_refuses_any_other_line_itself(monkeypatch):
    monkeypatch.setattr(tbl.time, "sleep", lambda s: None)
    dev = FakeDev()
    util, t = _ftdi(dev)
    with pytest.raises(tbl.ForbiddenLine):
        t.write(b";m0044e00fa012c0e\r")
    assert dev.sim.received == []


def test_a_line_error_from_the_chip_stops_everything(monkeypatch):
    monkeypatch.setattr(tbl.time, "sleep", lambda s: None)
    dev = FakeDev(line_status=0x68)
    util, t = _ftdi(dev)
    table = tbl.Table(t)
    with pytest.raises(tbl.Doubt):
        table.opening()
    assert table.closed_reason and len(dev.sim.received) <= 1


def test_the_real_run_needs_a_person_at_the_keyboard(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "stdin", open(__file__, encoding="utf-8"))
    log = tmp_path / "real.txt"
    assert prog.main(["--real", "--log", str(log)]) == 2
    assert "typed by a person" in log.read_text(encoding="utf-8")


# ---- the package --------------------------------------------------------------------------

def test_the_zip_is_reproducible_and_runs_from_a_clean_folder(tmp_path):
    build = ROOT / "scripts" / "build_i1io_open_zip.py"
    a = subprocess.run([sys.executable, "-I", str(build), "--out", str(tmp_path / "a")],
                       capture_output=True, text=True, encoding="utf-8", timeout=60)
    b = subprocess.run([sys.executable, "-I", str(build), "--out", str(tmp_path / "b")],
                       capture_output=True, text=True, encoding="utf-8", timeout=60)
    assert a.returncode == 0 and b.returncode == 0, a.stderr
    za = next((tmp_path / "a").glob("*.zip"))
    zb = next((tmp_path / "b").glob("*.zip"))
    assert za.read_bytes() == zb.read_bytes()
    with zipfile.ZipFile(za) as z:
        names = sorted(n.split("/", 1)[1] for n in z.namelist())
        assert names == sorted(["README.md", "BYTES.md", "i1io_open.py", "i1io_open_table.py",
                                "i1io_open_sim.py", "LICENSE"])
        z.extractall(tmp_path / "x")
    folder = next((tmp_path / "x").iterdir())
    for sim in ("cold", "warm"):
        r = subprocess.run([sys.executable, "-I", "i1io_open.py", "--auto", "--sim", sim,
                            "--log", f"run-{sim}.txt"], cwd=folder, capture_output=True,
                           text=True, encoding="utf-8", timeout=60, stdin=subprocess.DEVNULL)
        assert r.returncode == 0, r.stdout + r.stderr
        assert "Traceback" not in r.stdout + r.stderr


def test_the_readme_names_every_line_and_the_two_movements():
    readme = _source("README.md")
    for line in RECORDED:
        assert line in readme, line
    assert "power switch" in readme and "Ctrl-C" in readme and "--plan" in readme
    assert "—" not in readme
