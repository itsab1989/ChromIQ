"""A crashed xdist worker must cost the run its exit code, and must say so.

WHY THIS FILE EXISTS
--------------------
The release gate is `QT_QPA_PLATFORM=offscreen pytest --runslow -n auto`, and a
release decision is made on whether it came out green. On 2026-09-02 four gate
runs went red without a single assertion failing: an xdist worker segfaulted
each time, and pytest-xdist reported it by picking whichever test that worker
was holding and marking it FAILED — a test that passes on its own, in a file
that passes on its own. An hour went into deciding whether the red was somebody's
change. It was not.

The mirror image is worse and is what this file is really for. In
`xdist/scheduler/loadscope.py`::

    def remove_node(self, node):
        workload = self.assigned_work.pop(node)
        if not self._pending_of(workload):
            return None          # <- nothing is reported

and in `xdist/dsession.py::worker_errordown`, a crashitem of None means no
failure is recorded at all: the worker's death is two lines of prose in the
middle of nine thousand dots, and the run finishes `N passed`, exit 0. A gate
that can print "passed" with a dead process in it is not a gate.

`tests/conftest.py` therefore records every node-down that carries an error,
prints a banner that says in words what it is and what it is not, and sets
`session.exitstatus`. `wrap_session` in `_pytest/main.py` returns
`session.exitstatus` after every `pytest_sessionfinish` hook has run, so that
assignment is what reaches the shell.

WHAT IS TESTED HERE AND WHAT IS NOT
-----------------------------------
These are direct calls into the three hooks with stand-in objects. That is
deliberate: the alternative — spawning a nested `-n 2` pytest session and
segfaulting one of its workers — costs twenty seconds of the gate and brings its
own flakiness, and it exercises pytest-xdist rather than our code. The wiring to
xdist WAS proved separately, by running the real suite with a plugin that
crashes a worker on purpose; see the run recorded in
`.../FIX-GATE/logs/proof-*.txt`. What this file pins is the part that is ours:
that an error-carrying node-down is remembered, is described, and turns the exit
code non-zero.
"""
from __future__ import annotations

import importlib
import sys

import pytest


@pytest.fixture
def hooks():
    """The conftest module itself, with its crash list emptied around the test.

    `tests/conftest.py` is already imported (it IS the conftest); reaching it
    through `sys.modules` avoids importing a second copy with a second list.
    """
    mod = sys.modules.get("conftest") or sys.modules.get("tests.conftest")
    if mod is None:                                  # pragma: no cover
        mod = importlib.import_module("conftest")
    saved = list(mod._CRASHED_WORKERS)
    mod._CRASHED_WORKERS.clear()
    try:
        yield mod
    finally:
        mod._CRASHED_WORKERS[:] = saved


class _FakeGateway:
    def __init__(self, ident):
        self.id = ident


class _FakeNode:
    def __init__(self, ident):
        self.gateway = _FakeGateway(ident)


class _FakeReporter:
    """Enough of TerminalReporter to capture what the banner says."""

    def __init__(self):
        self.lines: list[str] = []

    def write_sep(self, _sep, title="", **_kw):
        self.lines.append(title)

    def write_line(self, line, **_kw):
        self.lines.append(line)


class _FakeConfig:
    pass


class _FakeSession:
    def __init__(self):
        self.config = _FakeConfig()          # no `workerinput` => the master
        self.exitstatus = 0


def test_a_clean_worker_shutdown_is_not_a_crash(hooks):
    """xdist calls the same hook for every worker that goes away. Only the ones
    that carry an error are deaths; recording the clean ones would fail every
    run."""
    hooks.pytest_testnodedown(_FakeNode("gw0"), None)
    assert hooks._CRASHED_WORKERS == []

    session = _FakeSession()
    hooks.pytest_sessionfinish(session, 0)
    assert session.exitstatus == 0, (
        "a worker finishing normally has turned the run red — every green run "
        "in this project would now be red")


def test_a_crashed_worker_makes_the_run_exit_non_zero(hooks):
    """The whole point: the counts can say `N passed` and the run still fails."""
    hooks.pytest_testnodedown(_FakeNode("gw4"), "Not properly terminated")

    session = _FakeSession()
    hooks.pytest_sessionfinish(session, 0)          # 0 == every test passed
    assert session.exitstatus != 0, (
        "a worker process died and the run still exited 0. That is the exact "
        "failure this guard exists for: somebody reads `9397 passed`, ships, "
        "and the run never executed whatever the dead worker was carrying")


def test_the_summary_names_the_worker_and_says_what_it_is_not(hooks):
    """A banner nobody can misread as a test failure — or as the harmless
    `Timeout (…)!` dump that faulthandler_timeout writes for a slow test, which
    is what one reviewer mistook for a crash in a GREEN run."""
    hooks.pytest_testnodedown(_FakeNode("gw11"), "Not properly terminated")

    rep = _FakeReporter()
    hooks.pytest_terminal_summary(rep, 0, _FakeConfig())
    text = "\n".join(rep.lines)

    assert "gw11" in text, "the banner does not say which worker died"
    assert "Not properly terminated" in text
    assert "NOT an assertion failure" in text, (
        "the banner does not say the thing that costs the hour — that the test "
        "named in the FAILED list is a bystander")
    assert "Timeout" in text, (
        "the banner does not separate itself from faulthandler_timeout's dump, "
        "which is the other multi-thread traceback this suite prints and means "
        "nothing is wrong")
    assert "Fatal Python error" in text, (
        "the banner does not tell the reader what to search the log for")


def test_the_banner_stays_silent_when_nothing_crashed(hooks):
    """It must cost a normal run nothing — not a line, not a colour."""
    rep = _FakeReporter()
    hooks.pytest_terminal_summary(rep, 0, _FakeConfig())
    assert rep.lines == []


def test_a_worker_process_never_reports_its_own_exit_status(hooks):
    """`pytest_sessionfinish` returns early inside a worker (it has
    `workerinput`), so the master stays the only place the exit code is
    decided."""
    hooks.pytest_testnodedown(_FakeNode("gw2"), "Not properly terminated")

    session = _FakeSession()
    session.config.workerinput = {"workerid": "gw2"}
    session.exitstatus = 0
    hooks.pytest_sessionfinish(session, 0)
    assert session.exitstatus == 0


# ---------------------------------------------------------------------------
# ...AND IT MUST NOT BE ABLE TO HANG THE SESSION EITHER
# ---------------------------------------------------------------------------
# The banner above only ever fires from `pytest_terminal_summary`, so it is
# worth exactly nothing if the session never ends. On the owner's Windows ARM64
# VM (2026-09-03) it did not: a worker died at 99 %, xdist spawned a
# replacement, execnet's bootstrap for that replacement raised
# `OSError: [Errno 22] Invalid argument`, and the controller then waited for a
# node that never reported. Two `--runslow` attempts, no summary line, no exit
# code, both killed by hand.
#
# `--max-worker-restart=0` removes the restart, and with it the code path that
# hung. It also stops the restart storm: a reproducible crash is otherwise
# re-run once per replacement (measured: nine).

def _addopts() -> str:
    import configparser
    import pathlib
    ini = pathlib.Path(__file__).resolve().parent.parent / "pytest.ini"
    cp = configparser.ConfigParser()
    cp.read(ini, encoding="utf-8")
    return cp["pytest"].get("addopts", "")


def test_the_gate_never_restarts_a_crashed_worker():
    """Without this flag a dead worker can hang the whole session, and the
    guard above cannot save it — a banner printed at the end of a run that has
    no end is not printed at all."""
    opts = _addopts()
    assert "--max-worker-restart=0" in opts, (
        "pytest.ini no longer passes --max-worker-restart=0. A crashed xdist "
        "worker will be REPLACED, and if that replacement fails to start the "
        "run hangs for ever with no summary and no exit code — which is what "
        "happened on Windows on 2026-09-03. See the comment in pytest.ini.")


def test_the_gate_still_keeps_one_file_per_worker():
    """Guarding the line above must not have dropped what shared it."""
    opts = _addopts()
    assert "--dist loadfile" in opts
    assert "--maxprocesses=12" in opts
