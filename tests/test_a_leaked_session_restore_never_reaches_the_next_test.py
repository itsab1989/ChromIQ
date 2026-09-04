"""B8-43 — "restore the last session" must not survive the test that set it.

`AppSettings` is one store per WORKER PROCESS, so a key a test writes is read by
every file xdist schedules onto that worker afterwards. `restore_last_session`
is the one key where that is not merely untidy: `MainWindow.__init__` reads it
and queues `QTimer.singleShot(0, self._restore_last_session)`, and that deferred
call **replaces whatever project is open** — and closes it outright when the
remembered project is not on disk.

A fixture that opens a project runs no event loop, so the restore is still
pending when setup ends; pytest-qt's `pytest_runtest_setup` wrapper then calls
`QApplication.processEvents()` after its `yield`, the restore fires, and the
test runs against a file manager holding nothing. That is what made
`test_a_cancel_downstream_keeps_what_was_filed.py::
test_a_cross_tab_chart_load_takes_the_130_road` fail in about one full run in
seven while passing every time alone (B8-43).

`tests/conftest.py::_no_leaked_session_restore` clears the three keys before
every test. The order of the tests below is the point: the first one leaks, and
the ones after it must not be able to tell.
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PyQt6")

_GONE = "A-Project-That-Was-Deleted-In-Finder"


def test_a_test_may_switch_the_session_restore_on(qapp):
    """The leak, performed on purpose. `test_no_project_is_ever_invented` does
    exactly this, and is right to: it is testing what happens when the
    remembered project is gone."""
    from core.settings import AppSettings

    s = AppSettings()
    s.set("restore_last_session", True)
    s.set("session_target_name", _GONE)
    s.set("session_project_root", "")

    assert s.get("restore_last_session") is True
    assert s.get("session_target_name") == _GONE


def test_the_next_test_never_inherits_it(qapp):
    """…and the next test in the same worker starts as if nobody had."""
    from core.settings import AppSettings

    s = AppSettings()
    assert s.get("restore_last_session") is False, (
        "the test before this one left 'restore the last session' switched on; "
        "every MainWindow built from here on will queue a deferred restore "
        "that closes whatever project a fixture opens")
    assert s.get("session_target_name") == "", (
        f"a stale session target ({s.get('session_target_name')!r}) reached "
        f"this test")
    assert s.get("session_project_root") == ""


def test_a_project_opened_in_a_fixture_survives_the_first_event_loop_turn(
        qapp, tmp_path):
    """The harm itself, run rather than described.

    A real MainWindow, a real project opened the way `house` opens one, and then
    the `processEvents()` pytest-qt performs between setup and the test body.
    With a leaked session restore in the store this ends with no project open at
    all — which is B8-43 exactly, and which no assertion in the affected test
    could explain, because the deferred restore logs into no captured phase.
    """
    from core.file_manager import FileManager
    from core.settings import AppSettings
    from ui.main_window import MainWindow

    work = tmp_path / "work"
    work.mkdir()
    s = AppSettings()
    s.set("custom_output_path", str(work))

    # A real project on disk, built the way the app builds one.
    maker = FileManager(s)
    maker.set_target_name("Kept-Open")
    maker.project().current_run().ensure_dir()
    manifest = work / "Kept-Open" / "project.json"
    assert manifest.exists(), "the fixture failed to make a project to open"

    win = MainWindow(s)
    try:
        win._tab_chart.open_project_manifest(manifest)
        assert win._target_ctl.project_or_none() is not None, (
            "the project did not open at all")

        for _ in range(5):
            qapp.processEvents()

        proj = win._target_ctl.project_or_none()
        assert proj is not None, (
            "the project the fixture opened was closed by the first turn of the "
            "event loop — a deferred _restore_last_session from a leaked "
            "'restore_last_session' setting")
        assert proj.root == manifest.parent
    finally:
        win.close()
