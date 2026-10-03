"""Every ArgyllCMS tool and the chart-reading helper start with
ARGYLL_EXCLUDE_SERIAL_SCAN naming the macOS Bluetooth incoming port.

2026-10-03, macOS 27: Argyll's serial scan opens every "fast serial" port to
ask what is on it, any name with "Bluetooth" in it included, and that open
blocked in the kernel on ``/dev/cu.Bluetooth-Incoming-Port``. The helper sat
in state U, unkillable, and measuring could hang at start. Argyll's own remedy
is the variable; ``core/argyll_env.py`` has the details. These tests hold:

* the value merges onto the user's own and never drops it;
* the stuck port is excluded on macOS whatever the preference says, and a
  real instrument port (usbserial, usbmodem, JETI) never is;
* every place ChromIQ starts a tool uses the one helper, either explicitly or
  through the process environment that ``main()`` sets up.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

import core.argyll_env as AE

REPO = Path(__file__).resolve().parents[1]
STUCK = "/dev/cu.Bluetooth-Incoming-Port"
VAR = "ARGYLL_EXCLUDE_SERIAL_SCAN"


@pytest.fixture()
def darwin(monkeypatch):
    monkeypatch.setattr(sys, "platform", "darwin")
    # the machine's own phantom ports are not what these tests are about
    monkeypatch.setattr(AE, "argyll_serial_exclusion_ports", lambda: [])


# ---------------------------------------------------------------------------
# the value
# ---------------------------------------------------------------------------
def test_the_stuck_port_is_excluded_on_macos_with_the_preference_off(darwin):
    """MUTATION: ``DARWIN_ALWAYS_EXCLUDED = ()``."""
    assert AE.serial_exclusion_value(None, phantoms=False) == STUCK
    assert AE.argyll_env({}, phantoms=False) == {VAR: STUCK}


def test_the_user_value_is_kept_and_ours_appended(darwin):
    """MUTATION: replace the user's value instead of merging onto it."""
    assert AE.argyll_env({VAR: "COM9"})[VAR] == f"COM9;{STUCK}"
    # commas are Argyll separators too, and are normalised
    assert AE.argyll_env({VAR: "/dev/cu.a,/dev/cu.b"})[VAR] == \
        f"/dev/cu.a;/dev/cu.b;{STUCK}"
    # already listed: not repeated
    assert AE.argyll_env({VAR: STUCK})[VAR] == STUCK
    # nothing else in the environment is touched
    env = AE.argyll_env({"PATH": "/x", VAR: "u"})
    assert env == {"PATH": "/x", VAR: f"u;{STUCK}"}


def test_the_phantom_list_is_added_when_the_preference_is_on(monkeypatch):
    monkeypatch.setattr(sys, "platform", "darwin")
    monkeypatch.setattr(AE, "argyll_serial_exclusion_ports",
                        lambda: [STUCK, "/dev/cu.debug-console"])
    assert AE.serial_exclusion_value("u", phantoms=True) == \
        f"u;{STUCK};/dev/cu.debug-console"


def test_elsewhere_nothing_is_forced(monkeypatch):
    for plat in ("linux", "win32"):
        monkeypatch.setattr(sys, "platform", plat)
        assert AE.always_excluded_ports() == []
        assert AE.argyll_env({"PATH": "/x"}, phantoms=False) == {"PATH": "/x"}
        assert AE.argyll_env({VAR: "COM9"}, phantoms=False) == {VAR: "COM9"}


def test_no_real_instrument_port_is_ever_excluded():
    """Argyll treats usbserial, usbmodem and JETI ports as instruments
    (spectro/icoms_ux.c). None of them may be in either list."""
    for port in AE.always_excluded_ports("darwin"):
        low = port.lower()
        assert not any(h in low for h in ("usbserial", "usbmodem", "jeti"))
    real = ["/dev/cu.usbserial-1420", "/dev/cu.usbmodem14201",
            "/dev/cu.JETI-specbos"]
    assert AE._phantom_serial_ports(real + [STUCK]) == [STUCK]


def test_installing_into_the_process_keeps_the_user_value(darwin, monkeypatch):
    monkeypatch.setenv(VAR, "COM9")
    assert AE.install_in_process_environment() == f"COM9;{STUCK}"
    # idempotent: a second call does not grow it
    assert AE.install_in_process_environment() == f"COM9;{STUCK}"
    assert os.environ[VAR] == f"COM9;{STUCK}"


@pytest.mark.skipif(sys.platform != "darwin", reason="macOS only")
def test_this_test_process_has_it():
    """The suite's own launches of the helper and Argyll tools inherit it,
    because ``tests/conftest.py::pytest_configure`` installs it as main()
    does."""
    assert STUCK in os.environ.get(VAR, "").split(";")


# ---------------------------------------------------------------------------
# the launches
# ---------------------------------------------------------------------------
def _src(rel: str) -> str:
    return (REPO / rel).read_text(encoding="utf-8")


@pytest.mark.parametrize("rel", ["main.py", "scripts/capture_screens.py",
                                 "tests/conftest.py"])
def test_the_process_environment_is_set_up_where_the_app_starts(rel):
    """A ``subprocess.run`` with no ``env=`` (the Settings dialog's tool check,
    xicclu, targen, colprof, ...) inherits ``os.environ``; these are the three
    places a ChromIQ process is born. MUTATION: drop the call from main()."""
    assert "install_in_process_environment()" in _src(rel), rel


def test_every_runner_launch_adds_the_exclusion():
    """ArgyllRunner starts the measurement (stock chartread over a PTY, the
    engine helper over QProcess). Each of its four launches merges the
    exclusion in through `environment_additions`."""
    import inspect

    from core.argyll_runner import ArgyllRunner
    for name in ("run", "_run_pty", "_run_winpty", "_run_pipe"):
        body = inspect.getsource(getattr(ArgyllRunner, name))
        assert "environment_additions(" in body, name
        assert ("setProcessEnvironment" in body) or ("env=_env" in body), name


def test_no_launch_builds_an_environment_that_drops_it():
    """An explicit ``env=`` replaces the inherited one, so every one in the
    app must come from this module (directly, through printtarg_env, or as the
    runner's merged ``_env``). MUTATION: ``env={"PATH": ...}`` in a launch."""
    allowed = re.compile(r"env=(_env|printtarg_env\(|argyll_env\(|helper_env\()")
    bad = []
    for top in ("core", "workflow", "ui"):
        for py in (REPO / top).rglob("*.py"):
            for i, line in enumerate(py.read_text(encoding="utf-8").splitlines(), 1):
                code = line.split("#", 1)[0]
                for m in re.finditer(r"(?<![\w.`])env=", code):
                    if not allowed.match(code[m.start():]):
                        bad.append(f"{py.relative_to(REPO)}:{i}: {line.strip()}")
    assert not bad, "a launch with its own environment:\n" + "\n".join(bad)


def test_printtarg_env_carries_it(darwin):
    from core.printtarg_env import printtarg_env
    env = printtarg_env({"PATH": "/x"})
    assert env[VAR] == STUCK
    assert env["MallocLargeCache"] == "0"


class _Off:
    def get(self, key, default=None):
        return False if key == "fast_instrument_connect" else default


def test_the_pty_launch_really_passes_it(qapp, darwin, monkeypatch, tmp_path):
    """Behaviour, not source: stock chartread's PTY launch, preference OFF,
    is handed the exclusion. MUTATION: drop ``env=_env`` from `_run_pty`."""
    if sys.platform == "win32":
        pytest.skip("POSIX PTY path")
    import core.argyll_runner as AR
    seen = {}

    def fake_popen(cmd, **kw):
        seen.update(kw)
        raise OSError("stand-in chartread")

    monkeypatch.setattr(AR.subprocess, "Popen", fake_popen)
    monkeypatch.delenv(VAR, raising=False)
    runner = AR.ArgyllRunner(_Off())
    runner.run("chartread", ["-?"], tmp_path, use_pty=True)
    assert seen["env"][VAR] == STUCK


def test_the_replay_harness_passes_it():
    """The suite's helper harness starts the helper as the app does."""
    src = _src("tests/helpers/replay_tools.py")
    assert "env=helper_env()" in src
    assert "argyll_env()" in src


@pytest.mark.skipif(sys.platform != "darwin", reason="macOS only")
def test_the_helper_answers_with_the_app_environment():
    """The real helper, no arguments, in the app's environment: its usage
    lists the instruments, which scans the serial ports. With the stuck port
    excluded it answers at once; measured 2026-10-03 with the port stuck, it
    hung for ever without. Never ``wait()`` after a timeout: a process stuck
    in the kernel cannot be killed."""
    sys.path.insert(0, str(REPO / "tests" / "helpers"))
    from replay_tools import HELPER, helper_env
    if not HELPER.exists():
        pytest.skip("chromiq-chartread helper not built")
    proc = subprocess.Popen([str(HELPER)], stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, text=True,
                            encoding="utf-8", env=helper_env())
    try:
        so, se = proc.communicate(timeout=120)
    except subprocess.TimeoutExpired:
        proc.kill()
        pytest.fail("the helper did not answer within 120 s even with "
                    f"{VAR}={helper_env().get(VAR)}")
    assert "usage: chartread" in so + se
