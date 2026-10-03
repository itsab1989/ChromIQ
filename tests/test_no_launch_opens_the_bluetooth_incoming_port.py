"""No reader is started against a port that is never an instrument.

Review of b3591886 (2026-10-03): ``ARGYLL_EXCLUDE_SERIAL_SCAN`` keeps Argyll's
start-up scan away from ``/dev/cu.Bluetooth-Incoming-Port``, but with nothing
plugged in that port is number 1 in Argyll's list, ChromIQ passes ``-c 1``,
and the tool OPENS it: ``spotread -v`` sat in state U, unkillable, with the
variable set. ``core/instrument_port.py`` resolves the port before a launch,
without opening anything, and the launch paths end the way a reader that
found no instrument ends, so the existing "No instrument found" window opens.

Held here:

* the decision, reproduced from Argyll's own ordering (USB instruments, then
  serial ports sorted identified-first, then by name);
* a real instrument is never refused on a guess (USB, usbserial/usbmodem/JETI,
  a SwatchMate Cube's outgoing Bluetooth port, anything that cannot be read);
* both managers and the runner refuse, and nothing is launched;
* every launch path asks (source scan);
* no test starts a real reader (``tests/conftest.py``).
"""
from __future__ import annotations

import ast
import inspect
import re
import sys
from pathlib import Path

import pytest

from core import instrument_port as IP

REPO = Path(__file__).resolve().parents[1]
BT = "/dev/cu.Bluetooth-Incoming-Port"
DEBUG = "/dev/cu.debug-console"
MODEM = "/dev/cu.usbmodem1101"
FTDI = "/dev/cu.usbserial-A1B2"
CUBE = "/dev/cu.Cube-0A1B"           # a paired device: its own name


@pytest.fixture()
def darwin(monkeypatch):
    monkeypatch.setattr(sys, "platform", "darwin")


def _machine(monkeypatch, usb, serial):
    monkeypatch.setattr(IP, "probe", lambda: (usb, list(serial)))


# ---------------------------------------------------------------------------
# the decision
# ---------------------------------------------------------------------------
def test_nothing_plugged_in_port_1_is_the_bluetooth_port(darwin):
    """The finding itself. MUTATION: drop the marker / the always-excluded
    list from ``is_system_port``."""
    assert IP.system_port_at(1, 0, [DEBUG, BT]) == BT
    # past the end: Argyll says "No instrument at port 2" and opens nothing
    assert IP.system_port_at(2, 0, [DEBUG, BT]) is None


def test_a_usb_instrument_comes_first(darwin):
    assert IP.system_port_at(1, 1, [BT]) is None
    assert IP.system_port_at(2, 1, [BT]) == BT
    assert IP.system_port_at(2, 2, [BT]) is None
    assert IP.system_port_at(3, 2, [BT]) == BT


def test_a_serial_instrument_port_is_never_refused(darwin):
    """A usbmodem/usbserial/JETI port sorts after the Bluetooth port by name,
    but moves ahead of it when the scan identifies an instrument on it, which
    only the scan can know. So neither number is refused."""
    for port in (MODEM, FTDI, "/dev/cu.JETI-1211"):
        assert IP.system_port_at(1, 0, [BT, port]) is None, port
        assert IP.system_port_at(2, 0, [BT, port]) is None, port


def test_a_swatchmate_cube_keeps_its_number(darwin):
    """The Cube is a paired Bluetooth device with its own outgoing port, never
    probed by the scan, so the order is fixed: Bluetooth-Incoming, then Cube."""
    assert IP.system_port_at(2, 0, [BT, CUBE]) is None
    assert IP.system_port_at(1, 0, [BT, CUBE]) == BT


def test_cannot_tell_is_never_a_refusal(darwin):
    assert IP.system_port_at(1, None, [BT]) is None
    assert IP.system_port_at(1, 0, None) is None


def test_the_argyll_ignored_names_take_no_number(darwin):
    """debug-console, IrDA, Dialup and PDA-Sync are dropped by Argyll before
    numbering, so they do not shift the Bluetooth port."""
    assert IP.system_port_at(1, 0, ["/dev/cu.IrDA-x", DEBUG, BT]) == BT


def test_two_identical_instruments_count_twice():
    """`_parse_ioreg` folds them into one kind; the port number needs both."""
    from core.argyll_instruments import _count_ioreg_instruments
    block = ('+-o i1Pro@{loc}\n  "idVendor" = 2417\n  "idProduct" = 8192\n'
             '  "locationID" = {loc}\n')
    text = block.format(loc=1048576) + block.format(loc=2097152)
    text += '+-o Keyboard\n  "idVendor" = 1452\n  "idProduct" = 1\n'
    assert _count_ioreg_instruments(text) == 2


# ---------------------------------------------------------------------------
# reading a launch
# ---------------------------------------------------------------------------
def test_the_port_number_is_read_as_argyll_reads_it(darwin, monkeypatch):
    _machine(monkeypatch, 1, [BT])
    assert IP.refused_port("spotread", ["-v", "-c", "2"]) == BT
    assert IP.refused_port("spotread", ["-v", "-c2"]) == BT
    assert IP.refused_port("spotread", ["-v", "-c", "1"]) is None
    _machine(monkeypatch, 0, [BT])
    assert IP.refused_port("spotread", ["-v"]) == BT          # default 1
    assert IP.refused_port("/a/b/chromiq-chartread",
                           ["--json", "-v", "-c", "1", "/r/chart"]) == BT
    assert IP.refused_port("chartread.exe", ["-c", "1", "/r/chart"]) == BT


def test_launches_that_open_no_port_are_left_alone(darwin, monkeypatch):
    _machine(monkeypatch, 0, [BT])
    assert IP.refused_port("chartread", ["-v", "-c", "1", "-xx", "/c"]) is None
    assert IP.refused_port("chromiq-chartread",
                           ["--json", "--replay", "r.json", "-c", "1", "/c"]) is None
    assert IP.refused_port("chartread", ["-?"]) is None
    assert IP.refused_port("chartread", []) is None
    # spotread's -x is "show Yxy", not external values: still refused
    assert IP.refused_port("spotread", ["-v", "-x"]) == BT
    # not an instrument tool
    assert IP.refused_port("colprof", ["-c", "1", "x"]) is None


def test_a_probe_that_fails_never_blocks_a_launch(darwin, monkeypatch):
    def boom():
        raise OSError("no ioreg")
    monkeypatch.setattr(IP, "probe", boom)
    assert IP.refused_port("spotread", ["-v", "-c", "1"]) is None


# ---------------------------------------------------------------------------
# the launch paths
# ---------------------------------------------------------------------------
class _Runner:
    def __init__(self):
        self.calls = []
        self.is_running = False

    def run(self, tool, args, cwd, on_line=None, on_finish=None, use_pty=False):
        self.calls.append((str(tool), list(args)))


def _pump(qapp, ms=50):
    from PyQt6.QtCore import QEventLoop, QTimer
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()


def _measure(tmp_path, instrument="1", **kw):
    from workflow.measure_manager import MeasureManager, MeasureParams
    runner = _Runner()
    m = MeasureManager(runner)
    seen = {"no_instrument": 0, "finish": []}
    m.no_instrument.connect(lambda: seen.__setitem__(
        "no_instrument", seen["no_instrument"] + 1))
    p = MeasureParams(ti1_path=tmp_path / "chart.ti1", instrument=instrument, **kw)
    m.start(p, lambda _l: None, seen["finish"].append)
    return runner, seen


@pytest.mark.parametrize("engine", [False, True])
def test_start_measurement_with_nothing_plugged_in_launches_nothing(
        qapp, tmp_path, darwin, monkeypatch, engine):
    """Stock chartread and the engine alike: no launch, "no instrument", and
    the session's finish with a failure code, as a reader that found no
    instrument ends. MUTATION: remove the guard in ``MeasureManager.start``."""
    _machine(monkeypatch, 0, [DEBUG, BT])
    kw = {"engine_helper": tmp_path / "chromiq-chartread"} if engine else {}
    runner, seen = _measure(tmp_path, **kw)
    # nothing inside start: the tab clears its flag once start has returned
    assert seen["no_instrument"] == 0 and seen["finish"] == []
    _pump(qapp)
    assert runner.calls == []
    assert seen["no_instrument"] == 1
    assert seen["finish"] == [1]


def test_a_serial_instrument_port_still_measures(qapp, tmp_path, darwin,
                                                 monkeypatch):
    _machine(monkeypatch, 0, [BT, MODEM])
    runner, seen = _measure(tmp_path, instrument="2")
    _pump(qapp)
    assert runner.calls and runner.calls[0][0] == "chartread"
    assert seen["no_instrument"] == 0 and seen["finish"] == []


def test_a_usb_instrument_still_measures(qapp, tmp_path, darwin, monkeypatch):
    _machine(monkeypatch, 1, [DEBUG, BT])
    runner, seen = _measure(tmp_path, engine_helper=tmp_path / "chromiq-chartread")
    _pump(qapp)
    assert len(runner.calls) == 1
    assert seen["no_instrument"] == 0


def test_the_replay_instrument_still_measures(qapp, tmp_path, darwin,
                                              monkeypatch):
    _machine(monkeypatch, 0, [BT])
    runner, seen = _measure(tmp_path, engine_helper=tmp_path / "chromiq-chartread",
                            engine_replay=tmp_path / "replay.json")
    _pump(qapp)
    assert len(runner.calls) == 1 and "--replay" in runner.calls[0][1]
    assert seen["no_instrument"] == 0


def test_read_single_patches_with_nothing_plugged_in_launches_nothing(
        qapp, darwin, monkeypatch):
    from workflow.spot_read_manager import SpotReadManager, SpotReadParams
    _machine(monkeypatch, 0, [BT])
    runner = _Runner()
    m = SpotReadManager(runner)
    order = []
    m.no_instrument.connect(lambda: order.append("no_instrument"))
    m.session_ended.connect(lambda code: order.append(("ended", code)))
    m.start(SpotReadParams(), lambda _l: None)
    assert order == []                 # after start has returned, not inside it
    _pump(qapp)
    assert runner.calls == []
    assert order == ["no_instrument", ("ended", 1)]

    _machine(monkeypatch, 1, [BT])
    m.start(SpotReadParams(), lambda _l: None)
    assert runner.calls and runner.calls[0][0] == "spotread"


def test_the_runner_is_the_last_door(qapp, tmp_path, darwin, monkeypatch):
    """Any path that skipped the managers' check is refused by the runner
    itself, and its caller still hears back. (The suite makes this door
    stricter; the app's own rule is put back here.)"""
    from core.argyll_runner import ArgyllRunner
    from core.settings import AppSettings
    monkeypatch.setattr(IP, "runner_refuses",
                        lambda _r, tool, args: IP.refused_port(tool, args))
    _machine(monkeypatch, 0, [BT])
    r = ArgyllRunner(AppSettings())
    done = []
    r.run("spotread", ["-v", "-c", "1"], tmp_path, on_finish=done.append,
          use_pty=True)
    r.run("chartread", ["-v", "-c", "1", str(tmp_path / "c")], tmp_path,
          on_finish=done.append)
    _pump(qapp)
    assert done == [1, 1]
    assert r._pty_proc is None and r._process is None
    assert not r.is_running


# ---------------------------------------------------------------------------
# every launch path asks
# ---------------------------------------------------------------------------
def _calls(func) -> "list[str]":
    """The names of the calls in *func*, in source order."""
    import textwrap
    tree = ast.parse(textwrap.dedent(inspect.getsource(func)))
    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            f = node.func
            name = f.attr if isinstance(f, ast.Attribute) else getattr(f, "id", "")
            found.append((node.lineno, node.col_offset, name))
    return [n for *_, n in sorted(found)]


def test_every_launch_asks_first():
    """MUTATION: move a launch above its check, or delete a check."""
    from core.argyll_runner import ArgyllRunner
    from workflow.measure_manager import MeasureManager
    from workflow.spot_read_manager import SpotReadManager

    # MeasureManager.start: the launches above the check sit in the nested
    # finish handler, which runs only after a launch; the two that start a
    # session (engine, stock) come after it.
    m = [n for n in _calls(MeasureManager.start)
         if n in ("_refuse_system_port", "run", "_launch_stock")]
    assert m[-3:] == ["_refuse_system_port", "run", "_launch_stock"], m

    s = _calls(SpotReadManager.start)
    assert s.index("refused_port") < s.index("run")

    r = _calls(ArgyllRunner.run)
    assert r.index("runner_refuses") < r.index("_run_pty")
    assert r.index("runner_refuses") < r.index("QProcess")


def test_no_reader_is_started_outside_the_runner():
    """chartread, spotread and the helper reach the machine only through
    ArgyllRunner.run, so its door covers them all. MUTATION: a
    ``subprocess.Popen([... "spotread" ...])`` anywhere in the app."""
    launch = re.compile(r"subprocess\.(run|Popen|call|check_call|check_output)"
                        r"|QProcess\.startDetached|os\.(system|spawn|exec)")
    reader = re.compile(r"[\"'/](spotread|chartread|chromiq-chartread)"
                        r"(\.exe)?[\"']|helper_path\(\)")
    bad = []
    for top in ("core", "workflow", "ui"):
        for py in (REPO / top).rglob("*.py"):
            lines = py.read_text(encoding="utf-8").splitlines()
            for i, line in enumerate(lines):
                code = line.split("#", 1)[0]
                if not launch.search(code):
                    continue
                window = " ".join(x.split("#", 1)[0] for x in lines[i:i + 4])
                if reader.search(window) and "killall" not in window \
                        and "taskkill" not in window:
                    bad.append(f"{py.relative_to(REPO)}:{i + 1}: {line.strip()}")
    assert not bad, "a reader launched outside ArgyllRunner:\n" + "\n".join(bad)


def test_the_suite_refuses_a_real_reader():
    """The conftest door is what keeps this machine's port 1 out of every
    test; it must stay in place."""
    src = (REPO / "tests" / "conftest.py").read_text(encoding="utf-8")
    assert "def _no_test_opens_a_real_instrument_port" in src
    assert '"runner_refuses", runner_refuses' in src
    assert '"probe", lambda: (None, None)' in src


def test_no_new_message_text():
    """The refusal shows the existing windows (M-NO-INSTRUMENT in the Measure
    tab, "No instrument detected" in Read Single Patches); the module itself
    says nothing to the user."""
    src = (REPO / "core" / "instrument_port.py").read_text(encoding="utf-8")
    assert not re.search(r"\btr\(", src)
