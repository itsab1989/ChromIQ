"""Round B of the i1iO table drive (2026-11-17): the instrument's button as "Aimed".

The helper's ``--i1io-press-wait`` mode (native/chartread_helper/chromiq_presswait.c) opens the
i1Pro 2 as every reading does and reports ONE press of its button per arm. Nobody on the project
owns the table, and no real i1Pro 2 is attached here, so this is proved on the helper's own
replay instrument (``--replay``, CHROMIQ_REPLAY_INSTRUMENT=i1pro2; ``{"cmd":"switch"}`` is a
press, as the i1Pro's switch thread reports it) and by reading the source:

* a press is reported only while armed, once per arm, never sooner than min_ms after the arm;
  a press while nothing is armed is reported as ignored; a timeout and a disarm end the wait;
* the mode takes no reading, sets no mode, calibrates nothing and never opens the table: its
  file calls only the instrument's open, type, event callback and close;
* without the switch nothing of it runs: "press_*" commands are ignored by every other mode,
  and --caps is unchanged (tests/test_i1io_table_scan.py);
* the app's ``reader.PressWaiter`` speaks to the real helper; ``press_wait_supported`` says no
  for a helper without the token (2026-11-17a and older).

What only a real i1Pro 2 in a real table can show: that the driver's switch thread reports the
press there as it does by hand (Preferences' "Try it" has relied on it since 4.3.13). The
session log's "button press received" lines will say so on the first real session.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent / "helpers"))
from replay_tools import HELPER, helper_env  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "native" / "chartread_helper"

needs_helper = pytest.mark.skipif(not HELPER.exists(), reason="chromiq-chartread not built")


def _replay(tmp: Path) -> Path:
    p = tmp / "replay.txt"
    p.write_text("PATCHES 1\nSTRIP A\n50 50 50\n", encoding="utf-8")
    return p


class _Helper:
    def __init__(self, tmp: Path, model: "str | None" = "i1pro2"):
        env = helper_env()
        env["CHROMIQ_ENGINE_MUTE"] = "1"
        if model:
            env["CHROMIQ_REPLAY_INSTRUMENT"] = model
        else:
            env.pop("CHROMIQ_REPLAY_INSTRUMENT", None)
        self.p = subprocess.Popen([str(HELPER), "--json", "--replay", str(_replay(tmp)),
                                   "--i1io-press-wait"], stdin=subprocess.PIPE,
                                  stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True,
                                  encoding="utf-8", bufsize=1, env=env)
        self.events: list = []
        self._lock = threading.Lock()
        threading.Thread(target=self._pump, daemon=True).start()

    def _pump(self):
        for line in self.p.stdout:
            if line.startswith("{"):
                try:
                    ev = json.loads(line)
                except ValueError:
                    continue
                with self._lock:
                    self.events.append(ev)

    def send(self, **cmd):
        self.p.stdin.write(json.dumps(cmd) + "\n")
        self.p.stdin.flush()

    def wait(self, name, after=0, timeout=8.0):
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            with self._lock:
                for ev in self.events[after:]:
                    if ev.get("event") == name:
                        return ev
            time.sleep(0.01)
        raise AssertionError(f"no {name} after {after}: {self.events}")

    def n(self):
        with self._lock:
            return len(self.events)

    def names(self, after=0):
        with self._lock:
            return [e.get("event") for e in self.events[after:]]

    def end(self):
        try:
            self.send(cmd="press_quit")
        except OSError:
            pass
        try:
            return self.p.wait(timeout=10)
        finally:
            if self.p.poll() is None:
                self.p.kill()


@needs_helper
def test_one_press_per_arm_and_only_while_armed(tmp_path):
    h = _Helper(tmp_path)
    try:
        h.wait("press_wait_ready")
        i = h.n()
        h.send(cmd="switch")                                  # nothing armed
        assert h.wait("press_ignored", i)["why"] == "not_armed"
        i = h.n()
        h.send(cmd="press_arm", id="p1-m1-1", wait_ms="60000", min_ms="0")
        h.wait("press_armed", i)
        h.send(cmd="switch")
        ev = h.wait("press", i)
        assert ev["id"] == "p1-m1-1"
        i = h.n()
        h.send(cmd="switch")                                  # the arm was used up
        assert h.wait("press_ignored", i)["why"] == "not_armed"
        assert "press" not in h.names(i)
    finally:
        assert h.end() == 0
    assert h.names()[-1] == "press_wait_end"


@needs_helper
def test_a_press_too_soon_after_the_arm_is_not_an_answer(tmp_path):
    h = _Helper(tmp_path)
    try:
        h.wait("press_wait_ready")
        i = h.n()
        h.send(cmd="press_arm", id="p1-m2-2", wait_ms="60000", min_ms="1500")
        h.wait("press_armed", i)
        h.send(cmd="switch")
        ev = h.wait("press_ignored", i)
        assert ev["why"] == "too_soon" and ev["id"] == "p1-m2-2"
        time.sleep(1.6)
        h.send(cmd="switch")
        assert h.wait("press", i)["id"] == "p1-m2-2"
    finally:
        h.end()


@needs_helper
def test_the_wait_times_out_and_a_disarm_cancels_it(tmp_path):
    h = _Helper(tmp_path)
    try:
        h.wait("press_wait_ready")
        i = h.n()
        h.send(cmd="press_arm", id="t1", wait_ms="1000", min_ms="0")
        assert h.wait("press_timeout", i, timeout=6)["id"] == "t1"
        i = h.n()
        h.send(cmd="switch")
        assert h.wait("press_ignored", i)["why"] == "not_armed"
        i = h.n()
        h.send(cmd="press_arm", id="t2", min_ms="0")
        h.wait("press_armed", i)
        h.send(cmd="press_disarm")
        ev = h.wait("press_disarmed", i)
        assert ev["id"] == "t2" and ev["was_armed"] is True
        h.send(cmd="switch")
        assert h.wait("press_ignored", i)["why"] == "not_armed"
        assert "press" not in h.names(i)
    finally:
        h.end()


@needs_helper
def test_the_wait_ends_on_quit_and_on_the_end_of_stdin(tmp_path):
    h = _Helper(tmp_path)
    h.wait("press_wait_ready")
    h.send(cmd="quit")
    assert h.p.wait(timeout=10) == 0
    assert h.names()[-1] == "press_wait_end"
    h2 = _Helper(tmp_path)
    h2.wait("press_wait_ready")
    h2.p.stdin.close()
    assert h2.p.wait(timeout=10) == 0
    assert h2.names()[-1] == "press_wait_end"


@needs_helper
def test_only_an_i1pro2_is_opened_for_it(tmp_path):
    h = _Helper(tmp_path, model=None)               # the replay instrument is an i1Pro
    assert h.p.wait(timeout=10) == 1
    ev = h.wait("error")
    assert ev["kind"] == "press_instrument"
    assert "press_wait_ready" not in h.names()


@needs_helper
def test_the_app_side_press_waiter_speaks_to_the_real_helper(tmp_path, monkeypatch):
    from workflow.i1io.table import reader as rd
    monkeypatch.setenv("CHROMIQ_REPLAY_INSTRUMENT", "i1pro2")
    monkeypatch.setenv("CHROMIQ_ENGINE_MUTE", "1")
    log = []
    w = rd.PressWaiter(HELPER, tmp_path / "button", lambda k, m: log.append((k, m)),
                       extra_args=("--replay", str(_replay(tmp_path))))
    try:
        assert w.proc.wait(("press_wait_ready",), 10)["event"] == "press_wait_ready"
        assert w.arm("p1-m1-1", 60000, 0)
        assert w.proc.wait(("press_armed",), 5)["id"] == "p1-m1-1"
        w.proc.send({"cmd": "switch"})                      # the replay's press
        assert w.proc.wait(("press",), 5)["id"] == "p1-m1-1"
        assert any(e.get("event") == "press" for e in w.events())
    finally:
        w.close()
    assert not w.alive()
    # the log names the program, never a path with the person's name in it
    assert all(str(Path.home()) not in m for _k, m in log)


def test_press_wait_supported_reads_the_token():
    from workflow.i1io.table import reader as rd
    old = ("chromiq-chartread 2026-11-17a legacy-labels+margin-accounted+i1io-table-scan")
    new = old.replace("17a", "17b") + "+i1io-press-wait"
    assert rd.press_wait_supported(new)
    assert not rd.press_wait_supported(old)
    assert not rd.press_wait_supported("")
    assert not rd.press_wait_supported(old + "+i1io-press-waiting")


@needs_helper
def test_the_committed_helper_carries_the_button_wait():
    from workflow.i1io.table import reader as rd
    if sys.platform != "darwin":
        pytest.skip("the committed helper is the macOS build")
    assert rd.press_wait_supported(rd.helper_build(HELPER))


# ---- the source: what the mode may touch -------------------------------------------------------

def _code(text: str) -> str:
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    return re.sub(r"//[^\n]*", "", text)


def test_the_mode_takes_no_reading_and_never_reaches_the_table():
    code = _code((SRC / "chromiq_presswait.c").read_text(encoding="utf-8"))
    calls = set(re.findall(r"it->(\w+)\(", code))
    assert calls == {"set_event_callback", "init_coms", "init_inst", "interp_error", "del",
                     "get_itype"}, calls
    for word in ("read_sample", "read_strip", "read_chart", "set_mode", "calibrate",
                 "get_set_opt", "i1pro2_cq_tscan", "usb_read", "usb_write", "usb_control",
                 "->icom", "0x2004", "fopen"):
        assert word not in code, word
    # the driver's switch thread only counts here; nothing is emitted from it
    cb = code[code.index("static void pw_event("):code.index("static int pw_take_presses(")]
    assert "cq_emit" not in cb and "pw_presses++" in cb


def test_without_the_switch_nothing_of_it_runs():
    js = (SRC / "chromiq_json.c").read_text(encoding="utf-8")
    assert "void (*cq_presswait_line_hook)(const char *line) = NULL;" in js
    assert 'cq_presswait_line_hook != NULL && strncmp(cmd, "press_", 6) == 0' in js
    pw = (SRC / "chromiq_presswait.c").read_text(encoding="utf-8")
    assert pw.count("cq_presswait_line_hook = pw_push;") == 1
    main = (SRC / "chromiq_chartread.c").read_text(encoding="utf-8")
    assert main.count("cq_run_press_wait(") == 1
    assert "if (cq_presswait)\n\t\treturn cq_run_press_wait(comport, fc, cq_guard_inst);" in main
    for f in SRC.glob("*.c"):
        if f.name != "chromiq_presswait.c":
            assert "pw_push" not in f.read_text(encoding="utf-8", errors="replace"), f


@needs_helper
def test_press_commands_are_ignored_by_a_hand_reading(tmp_path):
    """A spot session (the reading a table row uses) does not know press_*: nothing answers."""
    from test_chartread_engine import _make_chart
    from replay_tools import write_replay_script
    base = _make_chart(tmp_path, randomised=False)
    replay = tmp_path / "r.txt"
    write_replay_script(base.with_suffix(".ti2"), replay, noise=0.2)
    env = helper_env()
    env["CHROMIQ_ENGINE_MUTE"] = "1"
    p = subprocess.Popen([str(HELPER), "--json", "--replay", str(replay), "-N", "-p",
                          str(base)], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                         stderr=subprocess.DEVNULL, text=True, encoding="utf-8", bufsize=1,
                         env=env, cwd=str(tmp_path))
    try:
        p.stdin.write('{"cmd":"press_arm","id":"x","min_ms":"0"}\n{"cmd":"switch"}\n'
                      '{"cmd":"quit"}\n')
        p.stdin.flush()
        out, _ = p.communicate(timeout=20)
    finally:
        if p.poll() is None:
            p.kill()
    assert '"press' not in out
