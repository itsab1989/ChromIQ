"""#145 — closing Read Single Patches must let go of the shared runner.

Knut, 2026-08-13 (critical): his ColorMunki kept dropping off a 2019 MacBook,
spotread exited on its own each time, and after enough tries *"the whole
ChromIQ app crashed fatally"*. His macOS report names the frame:
``PyQtSlotProxy::unislot`` calling ``QObject::deleteLater()`` on a null
object — a queued callback delivered into an object Qt had already destroyed.

The runner is the app-wide singleton and outlives every dialog, so a run's
callbacks (plain closures capturing the window that started them) must be
dropped when that window closes. ``ArgyllRunner.cleanup`` already documented
this failure mode for app shutdown; these tests pin the per-window half.
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtWidgets import QApplication          # noqa: E402

from core.argyll_runner import ArgyllRunner       # noqa: E402
from core.settings import AppSettings             # noqa: E402
from workflow.spot_read_manager import (SpotReadManager,  # noqa: E402
                                        SpotReadParams)


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def test_forget_run_callbacks_drops_both(qapp):
    runner = ArgyllRunner(AppSettings())
    calls = []
    runner._run_on_line = lambda line: calls.append(line)
    runner._run_on_finish = lambda code: calls.append(code)
    # NOTE: nothing is connected here any more. Registering a run's `on_line`
    # IS setting the attribute — see `_dispatch_run_line`. This test used to
    # `connect()` the closure itself, which is the mechanism the 2026-09-02
    # crash came out of; see test_spot_read_slot_proxy.py.

    runner.forget_run_callbacks()

    assert runner._run_on_line is None
    assert runner._run_on_finish is None
    runner.line_received.emit("a line after the window closed")
    assert calls == [], "a dropped callback must not run"


def test_forgetting_twice_is_harmless(qapp):
    """Closing a window that never started a session, or closing it twice,
    must not raise — a close path that can throw is its own crash."""
    runner = ArgyllRunner(AppSettings())
    runner.forget_run_callbacks()
    runner.forget_run_callbacks()


def test_the_manager_detaches_from_the_runner(qapp):
    runner = ArgyllRunner(AppSettings())
    mgr = SpotReadManager(runner)
    fired = []
    mgr.session_ended.connect(lambda code: fired.append(code))

    # start() without a real spotread: stub the run so only the wiring is under
    # test — the callbacks are what the crash was about, not the process.
    stored = {}

    def fake_run(tool, args, cwd, on_line=None, on_finish=None, use_pty=False):
        stored["on_line"], stored["on_finish"] = on_line, on_finish
        runner._run_on_line, runner._run_on_finish = on_line, on_finish

    runner.run = fake_run                     # type: ignore[assignment]
    mgr.start(SpotReadParams(), lambda _line: None)
    assert stored["on_finish"] is not None

    mgr.detach()
    assert runner._run_on_finish is None, "the window let go of the runner"
    assert runner._run_on_line is None


def test_closing_the_dialog_detaches(qapp, tmp_path):
    """The whole point, through the real window: open Read Single Patches,
    close it, and the singleton must hold no callback into it."""
    from PyQt6.QtCore import QSettings

    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    runner = ArgyllRunner(s)
    from ui.dialogs.spot_read_dialog import SpotReadDialog
    dlg = SpotReadDialog(runner, s, None)
    # Whatever a session left behind on the shared runner…
    runner._run_on_line = lambda line: None
    runner._run_on_finish = lambda code: None
    dlg.close()
    assert runner._run_on_line is None
    assert runner._run_on_finish is None
    dlg.deleteLater()


def test_the_close_paths_go_through_one_place():
    """Both routes out of the window must detach, so a future third route is
    an obvious omission rather than a silent one."""
    import inspect

    from ui.dialogs.spot_read_dialog import SpotReadDialog
    for method in (SpotReadDialog.reject, SpotReadDialog.closeEvent):
        assert "_release_instrument" in inspect.getsource(method), method
    assert "detach" in inspect.getsource(SpotReadDialog._release_instrument)
