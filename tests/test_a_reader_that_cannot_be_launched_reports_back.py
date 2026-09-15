"""B8-220 — a reader that cannot be launched must report back, not go quiet.

`ArgyllRunner.run`'s QProcess path has said this for a long time, in its own
words: *"A PROCESS THAT NEVER STARTS MUST STILL REPORT BACK … When the binary is
missing or not executable, QProcess emits `errorOccurred` (FailedToStart) and
NOTHING else — so every caller's `on_finish` was simply never called."*

The three launchers underneath it had no such handler. `_run_pty` — the path
stock chartread ALWAYS takes, because `MeasureManager._launch_stock` passes
`use_pty=True` — calls `subprocess.Popen` bare, and a missing binary raises
`FileNotFoundError` inside the Qt slot that pressed the button. `main.py`
installs a `sys.excepthook`, so the process does not die; the exception is
logged where no user looks and the call simply stops halfway.

WHAT A PERSON SAW, driven on screen with `argyll_bin_path` pointing at a folder
holding no ArgyllCMS and none on PATH (combined round 8, `H-result.json`,
`H8-what-the-person-is-left-with.png`): press **Start Measurement**, answer
*Measure anyway* to "This chart is fully measured", and the Measure tab shows
"Progress: 0.0%", Start greyed, **Stop live**, every option greyed and "Keep
calm! Scan each strip with a slow, steady motion." Nothing is running. The
finished measurement has already been moved into `runs/run1/old/<date>/`, so the
run holds no `.ti3` at all, and the log's last line says only that it was moved.
There is no way back but restarting the app: `_session_live` stays True, so the
app-wide event filter goes on eating arrow keys everywhere in ChromIQ.

And on the averaging door (`I-result.json`) the same press of **Measure again to
average** left the run holding no `.ti3`, the reading stranded in
`reads/read1.ti3`, and **the log completely empty** — one line above the
`_session_live` check round 7 added to put exactly that reading back. The marker
is not wrong; `_on_start` never returns, so it is never read.
"""
from __future__ import annotations

import ast
import inspect
import pathlib
import tempfile

import pytest


@pytest.fixture
def runner_with_no_argyll(qapp, monkeypatch, tmp_path):
    from core.argyll_runner import ArgyllRunner
    from core.settings import AppSettings

    s = AppSettings()
    s.set("argyll_bin_path", str(tmp_path / "a-folder-with-no-argyll-in-it"))
    monkeypatch.setenv("PATH", "")
    return ArgyllRunner(s)


def _pump(qapp, ms=600):
    from PyQt6.QtCore import QEventLoop, QTimer

    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()
    qapp.processEvents()


# ---- the behaviour ------------------------------------------------------
def test_a_pty_reader_that_cannot_start_calls_on_finish(runner_with_no_argyll,
                                                        qapp, tmp_path):
    """The whole fault in one line: chartread goes over a PTY, and on_finish
    was never called, so no ending in the Measure tab ever ran."""
    seen: list[int] = []
    runner_with_no_argyll.run(
        "chartread", ["-v"], tmp_path, on_finish=seen.append, use_pty=True)
    _pump(qapp)
    assert seen == [-1], (
        "chartread could not be launched and the caller was never told, so "
        "`_on_measure_done` never ran: `_session_live` stays True, the Stop "
        f"button stays live and the run keeps no measurement. Got {seen!r}")


def test_the_launch_failure_never_escapes_into_the_caller(runner_with_no_argyll,
                                                          tmp_path):
    """It used to raise `FileNotFoundError` out of `_on_start`, halfway through
    starting a session. Nothing below the raise ever ran."""
    runner_with_no_argyll.run(
        "chartread", ["-v"], tmp_path, on_finish=lambda c: None, use_pty=True)


def test_nothing_is_left_running_after_a_failed_launch(runner_with_no_argyll,
                                                       qapp, tmp_path):
    runner_with_no_argyll.run(
        "chartread", ["-v"], tmp_path, on_finish=lambda c: None, use_pty=True)
    _pump(qapp)
    assert runner_with_no_argyll.is_running is False


def test_the_failed_tool_is_named_for_the_tab_that_asked(runner_with_no_argyll,
                                                         qapp, tmp_path):
    """The same field the QProcess path sets, so a tab can TELL the user."""
    runner_with_no_argyll.run(
        "chartread", ["-v"], tmp_path, on_finish=lambda c: None, use_pty=True)
    _pump(qapp)
    assert runner_with_no_argyll.last_failed_to_start == "chartread"


def test_the_run_output_says_why_before_the_ending_reads_it(
        runner_with_no_argyll, qapp, tmp_path):
    """The ending the Measure tab reaches says "Measurement failed — see output
    above", and there was nothing above: the reason went to the Python log,
    which no user reads."""
    lines: list[str] = []
    runner_with_no_argyll.run(
        "chartread", ["-v"], tmp_path,
        on_line=lines.append, on_finish=lambda c: None, use_pty=True)
    _pump(qapp)
    joined = "\n".join(lines)
    assert "chartread" in joined and "could not start" in joined.lower(), (
        f"the run's own output never named the tool that would not start: {lines!r}")


def test_the_reason_arrives_before_the_finish(runner_with_no_argyll, qapp,
                                              tmp_path):
    """Order matters: the ending prints "see output above"."""
    order: list[str] = []
    runner_with_no_argyll.run(
        "chartread", ["-v"], tmp_path,
        on_line=lambda t: order.append("line"),
        on_finish=lambda c: order.append("finish"), use_pty=True)
    _pump(qapp)
    assert order and order[0] == "line" and "finish" in order, (
        f"the reason did not reach the log before the ending that points at "
        f"it: {order!r}")


def test_the_pty_is_not_leaked_when_the_launch_fails(runner_with_no_argyll,
                                                     qapp, tmp_path):
    """`pty.openpty()` runs BEFORE the Popen that raises. Both ends have to go
    back, or every failed start costs the process two descriptors."""
    import resource
    import os

    soft, _ = resource.getrlimit(resource.RLIMIT_NOFILE)

    def _open_fds() -> int:
        n = 0
        for fd in range(0, min(soft, 4096)):
            try:
                os.fstat(fd)
            except OSError:
                continue
            n += 1
        return n

    before = _open_fds()
    for _ in range(12):
        runner_with_no_argyll.run(
            "chartread", ["-v"], tmp_path, on_finish=lambda c: None,
            use_pty=True)
        _pump(qapp, 40)
    _pump(qapp)
    after = _open_fds()
    assert after - before < 8, (
        f"twelve failed launches leaked descriptors: {before} -> {after}")


# ---- the shape, so a fourth launcher cannot be added without one --------
def _launcher_bodies():
    """Parsed from the MODULE on disk, not from a dedented class snippet: the
    first version fed `inspect.cleandoc` a class body and every one of these
    tests went red on a correct tree with an IndentationError. A check that
    cannot read the code proves nothing about it."""
    import core.argyll_runner as mod

    tree = ast.parse(pathlib.Path(mod.__file__).read_text(encoding="utf-8"))
    out = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name in (
                "_run_pty", "_run_winpty", "_run_pipe"):
            out[node.name] = node
    return out


def test_all_three_launchers_are_present_to_be_checked():
    assert set(_launcher_bodies()) == {"_run_pty", "_run_winpty", "_run_pipe"}


@pytest.mark.parametrize("name", ["_run_pty", "_run_winpty", "_run_pipe"])
def test_every_launcher_guards_the_call_that_starts_the_process(name):
    """A bare `subprocess.Popen` here is the whole fault. Windows and the pipe
    launcher have the identical shape and were fixed with it."""
    node = _launcher_bodies()[name]
    guarded = False
    for sub in ast.walk(node):
        if not isinstance(sub, ast.Try):
            continue
        calls_popen = any(
            isinstance(c, ast.Call) and isinstance(c.func, ast.Attribute)
            and c.func.attr == "Popen"
            for b in sub.body for c in ast.walk(b))
        reports = any(
            isinstance(c, ast.Call) and isinstance(c.func, ast.Attribute)
            and c.func.attr == "_the_tool_never_started"
            for h in sub.handlers for c in ast.walk(h))
        if calls_popen and reports:
            guarded = True
    assert guarded, (
        f"{name} starts a process without reporting a launch that fails; a "
        "missing binary then raises inside the Qt slot that pressed the button "
        "and the call simply stops halfway")


def test_the_reporter_does_not_re_enter_its_caller():
    """Delivered through a zero-delay timer, like the refused-run branch of
    `run()`: the caller is still standing inside `_on_start`, one line past
    `_session_live = True`, and must finish starting before any ending runs."""
    from core.argyll_runner import ArgyllRunner

    body = inspect.getsource(ArgyllRunner._the_tool_never_started)
    assert "singleShot" in body, (
        "the failure is reported synchronously, so `_on_measure_done` runs "
        "while `_on_start` is still half way through starting the session")


# ---- the start path holds no bare launch at all -------------------------
def test_the_start_path_launches_nothing_without_a_guard():
    """The last bare launch in `_on_start` after the fix above: the sweep for a
    stray chartread. Same shape, same consequence — `_on_start` stops halfway,
    with the previous measurement already archived by the question above it and
    the session guard already begun, so nothing ever puts it back.

    UNDRIVEN and recorded as such: `killall` and `taskkill` are system binaries
    and this round could not make either one missing. Guarded because the
    consequence is B8-220, not because a failure was measured.
    """
    import ui.tabs.tab_measure as mod

    tree = ast.parse(pathlib.Path(mod.__file__).read_text(encoding="utf-8"))
    start = next(n for n in ast.walk(tree)
                 if isinstance(n, ast.FunctionDef) and n.name == "_on_start")
    guarded, bare = set(), []
    for n in ast.walk(start):
        if isinstance(n, ast.Try):
            for b in n.body:
                for c in ast.walk(b):
                    if isinstance(c, ast.Call):
                        guarded.add(id(c))
    for n in ast.walk(start):
        if (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                and n.func.attr in ("run", "Popen", "call", "check_call")
                and isinstance(n.func.value, ast.Name)
                and n.func.value.id == "subprocess"
                and id(n) not in guarded):
            bare.append(n.lineno)
    assert bare == [], (
        f"_on_start launches a process without a guard at line(s) {bare}; a "
        "launch that raises stops the method halfway, with the measurement "
        "already archived and nothing left to put it back")


def test_every_early_return_in_on_start_is_above_the_marker():
    """Round 7's marker, re-derived rather than taken on trust: `_session_live`
    is set at `_on_start`'s point of no return, so every one of its early
    returns has to be ABOVE it or the restore in `_start_averaging_read` would
    decline for a read that never happened."""
    import ui.tabs.tab_measure as mod

    text = pathlib.Path(mod.__file__).read_text(encoding="utf-8")
    tree = ast.parse(text)
    start = next(n for n in ast.walk(tree)
                 if isinstance(n, ast.FunctionDef) and n.name == "_on_start")
    returns = [n.lineno for n in ast.walk(start) if isinstance(n, ast.Return)]
    marker = [n.lineno for n in ast.walk(start)
              if isinstance(n, ast.Assign)
              and any(getattr(t, "attr", None) == "_session_live"
                      for t in n.targets)]
    assert len(marker) == 1, f"the marker is assigned {len(marker)} times here"
    assert returns and max(returns) < marker[0], (
        f"an early return at line {max(returns)} sits BELOW the marker at "
        f"{marker[0]}: it would leave `_session_live` True for a read that "
        "never started, and the averaging restore would decline")
