"""Regression tests for core.webengine_shutdown.drain_web_view (issue #38).

PyQt6 + QtWebEngine crash with SIGBUS on *quit* if a web view is still wrapped
when the interpreter finalises. The earlier ``deleteLater()`` + ``processEvents()``
drain did not actually destroy the C++ objects (processEvents never dispatches
DeferredDelete at the same loop level, and at quit the loop never spins again),
so the half-deleted page outlived its profile and crashed. ``drain_web_view``
destroys the view synchronously via ``sip.delete`` instead.

Two layers of test:

* stub-level — the drain calls the right methods, clears nothing it shouldn't,
  and is a no-op for the None / placeholder-label cases;
* a **subprocess** that builds a *real* QWebEngineView, drains it and lets the
  interpreter finalise — exit code 0 proves the SIGBUS is gone. A real view is
  only safe to construct in its own process (it spawns a Chromium child and
  destabilises the shared test interpreter), hence the subprocess.
"""
from __future__ import annotations

import os
import subprocess
import sys
import textwrap

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PyQt6")
from PyQt6.QtWidgets import QApplication  # noqa: E402

from core.webengine_shutdown import drain_web_view  # noqa: E402

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

#: Seconds a subprocess that builds a real QWebEngineView is given.
#
# IT WAS 60, AND 60 IS A PHANTOM RED. That subprocess starts a whole Chromium.
# Measured on an idle machine 2026-09-02, the two tests below cost **1.17 s and
# 0.99 s** — so 60 was already a fifty-fold margin, and the release gate blew
# straight through it anyway, because the gate saturates every core with twelve
# workers. The run came out red with `subprocess.TimeoutExpired`, and the thing
# these tests exist for — that the process exits CLEANLY — was never evaluated
# at all. A budget that depends on how busy the machine is measures the machine.
#
# 300 s is ~250x the idle cost and still catches the only thing a timeout here
# is for: a process that never exits.
WEBENGINE_SUBPROCESS_TIMEOUT = 300


def _run_web_subprocess(script, env):
    """Run *script* in its own interpreter; make a timeout say what it is.

    A bare `subprocess.TimeoutExpired` propagates as a traceback that reads like
    the app crashed. It did not crash — it did not finish. The two need
    different answers from whoever reads the log, so they are said differently.
    """
    try:
        return subprocess.run(
            [sys.executable, "-c", script], capture_output=True, text=True,
            env=env, timeout=WEBENGINE_SUBPROCESS_TIMEOUT, encoding="utf-8",
        )
    except subprocess.TimeoutExpired as exc:
        pytest.fail(
            f"the QtWebEngine subprocess did not finish within "
            f"{WEBENGINE_SUBPROCESS_TIMEOUT} s.\n"
            f"THIS IS NOT THE ISSUE-#38 CRASH: the process never got as far as "
            f"exiting, so nothing about its exit has been tested. Either the "
            f"machine was saturated, or the view genuinely hangs — the log "
            f"below says which.\n"
            f"STDOUT:\n{exc.stdout}\nSTDERR:\n{exc.stderr}")


def _webengine_is_available():
    """…and give the availability probe a timeout of its own.

    CLAUDE.md's rule ("anything that shells out in a test needs a `timeout=`")
    applies to this one too: it was an unbounded `subprocess.run`, and an import
    that wedges would have hung the run with no attribution.
    """
    try:
        return subprocess.run(
            [sys.executable, "-c", "import PyQt6.QtWebEngineWidgets"],
            capture_output=True, timeout=120,
        ).returncode == 0
    except subprocess.TimeoutExpired:
        return False


def test_a_timeout_says_it_did_not_finish_not_that_it_crashed(monkeypatch):
    """Control — the new error path, exercised.

    Raising the budget is only half the change. The other half is that a
    subprocess which runs out of time must not read like the #38 crash: a bare
    `subprocess.TimeoutExpired` traceback is what sent one gate run's reader
    looking for a crash that had not happened. Give the helper a script that
    never finishes and one second to do it in.
    """
    monkeypatch.setattr(sys.modules[__name__],
                        "WEBENGINE_SUBPROCESS_TIMEOUT", 1, raising=True)
    # `pytest.fail` raises `Failed`, which descends from BaseException, not
    # Exception — `pytest.raises(Exception)` would let it straight through and
    # this control would report the very failure it is trying to catch.
    with pytest.raises(pytest.fail.Exception) as caught:
        _run_web_subprocess("import time; time.sleep(60)", dict(os.environ))
    message = str(caught.value)
    assert "did not finish" in message, message
    assert "NOT THE ISSUE-#38 CRASH" in message, message
    assert "crashed at exit" not in message, (
        "a timeout is being reported in the words used for a crash")


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


# --- stub level ------------------------------------------------------------
class _FakeSignal:
    def disconnect(self):
        pass


class _FakePage:
    def __init__(self):
        self.reparented = False
        self.deleted = False

    def setParent(self, parent):
        self.reparented = parent is None

    def deleteLater(self):
        self.deleted = True


class _FakeView:
    def __init__(self):
        self.loadFinished = _FakeSignal()
        self.stopped = False
        self.url = None
        self._page = _FakePage()
        self.reparented = False
        self.deleted = False

    def stop(self):
        self.stopped = True

    def setUrl(self, url):
        self.url = url

    def page(self):
        return self._page

    def setParent(self, parent):
        self.reparented = parent is None

    def deleteLater(self):
        self.deleted = True


def test_drain_stops_blanks_and_disposes(qapp):
    view = _FakeView()
    drain_web_view(view)
    assert view.stopped
    assert view.url is not None and "about:blank" in view.url.toString()
    # A non-sip stub falls back to the deferred-delete path.
    assert view.reparented and view.deleted
    assert view._page.reparented and view._page.deleted


def test_drain_none_and_placeholder_are_noops(qapp):
    drain_web_view(None)  # WebEngine absent → caller holds None

    class _Label:  # a QLabel placeholder has no setUrl
        pass

    drain_web_view(_Label())  # must not raise


# --- real view, real process exit ------------------------------------------
def test_real_view_drained_then_exit_is_clean():
    """A genuine QWebEngineView drained via drain_web_view lets the process
    finalise without the issue-#38 SIGBUS."""
    if not _webengine_is_available():
        pytest.skip("PyQt6-WebEngine not available")

    script = textwrap.dedent(
        """
        import sys
        from PyQt6.QtWidgets import QApplication
        from PyQt6.QtCore import QUrl, QEventLoop, QTimer
        from PyQt6.QtWebEngineWidgets import QWebEngineView
        from core.webengine_shutdown import drain_web_view

        app = QApplication(sys.argv)
        view = QWebEngineView()
        view.setHtml("<html><body><h1>x</h1></body></html>")
        loop = QEventLoop(); QTimer.singleShot(600, loop.quit); loop.exec()
        drain_web_view(view)
        print("CLEAN EXIT", flush=True)
        # fall off the end -> _Py_Finalize, exactly as on app quit
        """
    )
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen", PYTHONPATH=REPO_ROOT)
    proc = _run_web_subprocess(script, env)
    assert proc.returncode == 0, (
        f"process crashed at exit (rc={proc.returncode}):\n"
        f"STDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"
    )
    assert "CLEAN EXIT" in proc.stdout


def test_undrained_view_exits_clean_via_hard_exit():
    """The belt-and-braces guarantee (issue #38, second recurrence): even with
    a web view left fully alive — the WebEngine-global state that no per-view
    drain can reach — ``main._hard_exit`` reaches the OS without the SIGSEGV,
    because it skips CPython finalization (and thus SIP's cleanup_on_exit walk
    of the dangling Chromium wrapper graph) entirely.

    Mirrors Knut's reproduction: a process that has used a web view and then
    quits. Run in a subprocess because a real QWebEngineView destabilises the
    shared offscreen test interpreter."""
    if not _webengine_is_available():
        pytest.skip("PyQt6-WebEngine not available")

    script = textwrap.dedent(
        """
        import sys
        from PyQt6.QtWidgets import QApplication
        from PyQt6.QtCore import QEventLoop, QTimer
        from PyQt6.QtWebEngineWidgets import QWebEngineView
        from main import _hard_exit

        app = QApplication(sys.argv)
        view = QWebEngineView()
        view.setHtml("<html><body><h1>x</h1></body></html>")
        loop = QEventLoop(); QTimer.singleShot(600, loop.quit); loop.exec()
        # Deliberately do NOT drain/destroy the view: this is the global-state
        # case that crashed on quit in 3.9.16. _hard_exit must still be clean.
        print("CLEAN EXIT", flush=True)
        _hard_exit(0)
        print("UNREACHABLE", flush=True)  # os._exit never returns
        """
    )
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen", PYTHONPATH=REPO_ROOT)
    proc = _run_web_subprocess(script, env)
    assert proc.returncode == 0, (
        f"process crashed at exit (rc={proc.returncode}):\n"
        f"STDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"
    )
    assert "CLEAN EXIT" in proc.stdout
    assert "UNREACHABLE" not in proc.stdout  # os._exit really bypassed finalize
