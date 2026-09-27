"""B8-1419: a test session never writes into the user's real application log.

Found during beta 45: while everyday tiers ran, the real `chromiq.log` (the one
`core.logger._log_path()` names, `~/Library/Logs/ChromIQ/chromiq.log` on a Mac)
gained 20 to 60 "Settings SANDBOXED to .../pytest-of-Basti/pytest-99/popen-gwN/
..." lines per on-screen drive. The suite's own workers were already kept off
it by the NullHandler `tests/conftest.py` installs before the first `core`
import; the lines came from the CHILD processes tests start with
``subprocess.run([sys.executable, "-c", ...])``, which have no conftest in
them, configure logging from scratch and append to the real file.

The fix is the way settings are sandboxed: `tests/conftest.py` sets
`CHROMIQ_LOG_DIR` to a `chromiq-suite-log-*` folder of its own, one per
process, `core.platform_paths.log_dir()` answers it, and a child inherits it.
`pytest_unconfigure` removes it; a crash leaves a `chromiq-` name the sweep
takes.

Each check below writes a marker nobody else can write (it carries this test's
own tmp path or a fresh uuid) and then looks for it in the real log. Nothing
here compares the real log's size or time, because the real app, or an
on-screen drive, may be writing it at the same moment.
"""
from __future__ import annotations

import fnmatch
import logging
import os
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _real_log_path(monkeypatch) -> Path:
    """Where the app writes on this machine when nothing moves it."""
    import core.platform_paths as pp
    monkeypatch.delenv(pp.LOG_DIR_ENV, raising=False)
    return pp.log_dir() / "chromiq.log"


def _real_log_says(path: Path, marker: str) -> bool:
    # Read-only, and only the rotating file and its backups ChromIQ writes.
    for p in [path] + [path.with_name(f"{path.name}.{n}") for n in range(1, 6)]:
        try:
            if marker in p.read_text(encoding="utf-8", errors="replace"):
                return True
        except OSError:
            continue
    return False


def test_the_session_log_is_a_sandbox_the_sweep_recognises(monkeypatch):
    import core.platform_paths as pp
    sandbox = os.environ.get("CHROMIQ_LOG_DIR", "")
    assert sandbox, "tests/conftest.py did not set CHROMIQ_LOG_DIR"
    sandbox = Path(sandbox)
    assert pp.log_dir() == sandbox
    # A folder the sweep may take by NAME (`_sweep_stale_temp_dirs` globs
    # chromiq[-_]* in the system temp folder), never one it has to judge.
    assert sandbox.parent == Path(tempfile.gettempdir())
    assert fnmatch.fnmatch(sandbox.name, "chromiq[-_]*"), sandbox.name
    assert sandbox.is_dir()
    assert _real_log_path(monkeypatch).parent != sandbox


def test_a_child_process_logs_into_the_sandbox_not_the_real_log(
        tmp_path, monkeypatch):
    """The path the fault took: a child with a sandboxed settings file."""
    ini = tmp_path / f"b8-1419-{uuid.uuid4().hex}.ini"
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen",
               CHROMIQ_SETTINGS_FILE=str(ini))
    probe = (
        "import sys; sys.path.insert(0, sys.argv[1])\n"
        "from core.logger import _log_path, get_logger\n"
        "get_logger('b8_1419')\n"
        "from core.settings import AppSettings\n"
        "AppSettings()\n"
        "print('LOG', _log_path())\n")
    r = subprocess.run([sys.executable, "-c", probe, str(ROOT)],
                       capture_output=True, text=True, encoding="utf-8",
                       env=env, timeout=120)       # budgeted for a loaded gate
    line = next((l for l in r.stdout.splitlines() if l.startswith("LOG ")), None)
    assert line, f"the child printed no log path:\n{r.stdout}\n{r.stderr[-2000:]}"
    child_log = Path(line[4:])
    sandbox = Path(os.environ["CHROMIQ_LOG_DIR"])
    assert child_log == sandbox / "chromiq.log"
    # The line that reached the real log in beta 45 now reaches the sandbox.
    assert str(ini) in child_log.read_text(encoding="utf-8"), (
        "the child's 'Settings SANDBOXED' line is not in the sandbox log")
    assert not _real_log_says(_real_log_path(monkeypatch), str(ini)), (
        "a child process of a test wrote into the REAL chromiq.log")


def test_a_worker_logging_directly_does_not_reach_the_real_log(monkeypatch):
    marker = f"B8-1419 in-process marker {uuid.uuid4().hex}"
    logging.getLogger("chromiq.b8_1419").warning(marker)
    real = _real_log_path(monkeypatch)
    for h in logging.getLogger().handlers:
        name = getattr(h, "baseFilename", None)
        assert name is None or Path(name) != real, (
            f"a handler on the root logger writes the real log: {name}")
    assert not _real_log_says(real, marker)


def test_importing_the_conftest_again_makes_no_second_sandbox(tmp_path):
    """Several test files import `tests.conftest` for its helpers, and a
    second import under another name runs its module code again. Measured on
    the first everyday tier with this fix: one empty `chromiq-suite-log-*`
    left behind by a green run. A process makes ONE sandbox, however often
    the module is imported."""
    tmp = tmp_path / "tmp"
    tmp.mkdir()
    env = dict(os.environ, TMPDIR=str(tmp), TEMP=str(tmp), TMP=str(tmp),
               QT_QPA_PLATFORM="offscreen")
    for k in ("CHROMIQ_LOG_DIR", "CHROMIQ_SUITE_LOG_OWNER"):
        env.pop(k, None)
    probe = (
        "import importlib.util, os, sys\n"
        "sys.path.insert(0, sys.argv[1])\n"
        "seen = []\n"
        "for name in ('conftest_a', 'conftest_b', 'conftest_c'):\n"
        "    spec = importlib.util.spec_from_file_location(\n"
        "        name, os.path.join(sys.argv[1], 'tests', 'conftest.py'))\n"
        "    spec.loader.exec_module(importlib.util.module_from_spec(spec))\n"
        "    seen.append(os.environ['CHROMIQ_LOG_DIR'])\n"
        "print('DIRS', len(set(seen)))\n")
    r = subprocess.run([sys.executable, "-c", probe, str(ROOT)],
                       capture_output=True, text=True, encoding="utf-8",
                       env=env, timeout=120)
    line = next((l for l in r.stdout.splitlines() if l.startswith("DIRS ")),
                None)
    assert line, r.stdout[-2000:] + r.stderr[-2000:]
    made = sorted(p.name for p in tmp.glob("chromiq-suite-log-*"))
    assert line == "DIRS 1" and len(made) == 1, (line, made)


def test_each_process_removes_its_own_sandbox_when_it_ends(tmp_path):
    """A session leaves no log folder behind (and nothing the sweep could not
    recognise). Run with the system temp folder moved to this test's own
    tmp path, so the other workers' sandboxes cannot confuse the count."""
    tmp = tmp_path / "tmp"
    tmp.mkdir()
    env = dict(os.environ, TMPDIR=str(tmp), TEMP=str(tmp), TMP=str(tmp),
               QT_QPA_PLATFORM="offscreen")
    env.pop("CHROMIQ_LOG_DIR", None)
    env.pop("PYTEST_XDIST_WORKER", None)
    env.pop("PYTEST_ADDOPTS", None)
    r = subprocess.run(
        [sys.executable, "-m", "pytest", "-p", "no:xdist",
         "-p", "no:cacheprovider", "-o", "addopts=", "-q", "--co",
         "tests/test_platform_paths.py"],
        cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8",
        env=env, timeout=240)
    assert r.returncode == 0, r.stdout[-2000:] + r.stderr[-2000:]
    left = sorted(p.name for p in tmp.glob("chromiq-suite-log-*"))
    assert not left, f"the session left its log sandbox behind: {left}"
