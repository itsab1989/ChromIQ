"""Temp folders must not accumulate — nothing reclaims them.

`main.py::_hard_exit` calls `os._exit()` and its own docstring notes there are
no atexit hooks, so not even `TemporaryDirectory` finalizers run at quit. There
is no production sweeper (the one in tests/conftest.py is test-only). Anything
not deleted deliberately survives until the OS sweeps $TMPDIR — on macOS, days.

The softproof runner was the expensive one: it reassigned `self._work` to a
fresh mkdtemp on EVERY run and orphaned the previous folder. A proof re-runs on
a 350 ms debounce from the intent combo, the ΔE spinbox, the highlight combo,
the paper-white checkbox and both file pickers, at ~56-70 MB a time.
"""
import pathlib
import tempfile


def _softproof_dirs():
    return set(pathlib.Path(tempfile.gettempdir()).glob("chromiq_softproof_*"))


def test_rerunning_a_proof_does_not_orphan_the_previous_work_dir(qapp,
                                                                tmp_path):
    """Driven through the REAL `SoftproofRunner.run`.

    The previous version of this test did the retire/drop dance by hand on a
    `__new__` object and never called `run()` — so the actual change was
    untested, and restoring the bug (deleting the previous folder up front)
    left every test green.

    Each `run()` here fails early (the image cannot be read), which is the
    important case: seven `error.emit(...); return` paths lie between the
    retire at the top and the drop at the bottom, and a single retire slot
    meant a FAILED proof between two good ones orphaned its predecessor for
    ever.
    """
    from workflow.softproof_runner import SoftproofParams, SoftproofRunner

    class _IdleRunner:
        is_running = False

    before = _softproof_dirs()
    r = SoftproofRunner.__new__(SoftproofRunner)
    r._runner = _IdleRunner()
    r._work = None
    r._retired_work = []
    errors = []
    r.error = type("S", (), {"emit": lambda self, m: errors.append(m)})()

    missing = tmp_path / "not-an-image.tif"
    params = SoftproofParams(
        image_path=missing, printer_profile=tmp_path / "nope.icc",
        source_choice="srgb", custom_source=None, intent="r",
        threshold=2.0, highlight="none", paper_white=False,
        display_profile=None)

    for _ in range(3):
        r.run(params)

    assert errors, "the runs did not fail as this test needs them to"
    made = _softproof_dirs() - before
    assert len(made) == 3, (
        f"expected one work folder per run, found {len(made)}")

    r.cleanup()
    assert not (_softproof_dirs() - before), (
        f"failed proofs orphaned {[p.name for p in _softproof_dirs() - before]}"
        " — nothing sweeps $TMPDIR and main.py exits via os._exit()")


def test_a_proof_that_never_completes_is_still_cleaned_up(qapp):
    """If a run fails, its retired predecessor must still go when the dialog
    closes — otherwise a failed proof strands two folders instead of one."""
    from workflow.softproof_runner import SoftproofRunner

    before = _softproof_dirs()
    r = SoftproofRunner.__new__(SoftproofRunner)
    r._work = pathlib.Path(tempfile.mkdtemp(prefix="chromiq_softproof_"))
    r._retired_work = pathlib.Path(tempfile.mkdtemp(prefix="chromiq_softproof_"))
    assert len(_softproof_dirs() - before) == 2

    r.cleanup()
    assert not (_softproof_dirs() - before), (
        "a failed proof left its predecessor behind")


def test_cleanup_is_safe_to_call_twice_and_with_nothing_to_do(qapp):
    from workflow.softproof_runner import SoftproofRunner

    r = SoftproofRunner.__new__(SoftproofRunner)
    r._work = None
    r._retired_work = None
    r.cleanup()                      # nothing yet
    r._work = pathlib.Path(tempfile.mkdtemp(prefix="chromiq_softproof_"))
    r.cleanup()
    r.cleanup()                      # already gone
    assert r._work is None


def test_the_dialog_drops_its_gamut_html_folders(qapp):
    """Those folders are DELIBERATE while the dialog lives — the wireframe
    toggle re-reads them and the page resolves x3dom.js out of its own
    directory — but garbage once it does not."""
    from ui.dialogs.softproof_dialog import SoftproofDialog

    d = SoftproofDialog.__new__(SoftproofDialog)
    d._softproof = None          # the SOFT-PROOF runner, not the app's
    made = []
    for attr in ("_printer_html", "_image_html", "_combined_html"):
        folder = pathlib.Path(tempfile.mkdtemp(prefix="chromiq_gamuttest_"))
        (folder / "page.html").write_text("<html>")
        setattr(d, attr, str(folder / "page.html"))
        made.append(folder)

    d._drop_temp_work()

    for folder in made:
        assert not folder.exists(), f"{folder.name} survived the dialog"
    for attr in ("_printer_html", "_image_html", "_combined_html"):
        assert getattr(d, attr) is None


def test_the_cleanup_runs_after_the_web_view_is_drained(qapp, monkeypatch):
    """Order matters: the 3D page resolves x3dom.js out of its own folder, so
    deleting before the drain would pull the scene out from under a live view.

    Driven — the previous version compared string offsets in the source and
    would have passed on a comment.
    """
    import ui.dialogs.softproof_dialog as sd

    order = []
    monkeypatch.setattr(sd, "drain_web_view",
                        lambda v: order.append("drain"))

    d = sd.SoftproofDialog.__new__(sd.SoftproofDialog)
    d._closed = False
    d._runner = None
    d._web_view = object()

    class _Timer:
        def isActive(self):
            return False

    d._rerun_timer = _Timer()
    monkeypatch.setattr(sd.SoftproofDialog, "_drop_temp_work",
                        lambda self: order.append("cleanup"))

    d._teardown_webengine()

    assert order == ["drain", "cleanup"], (
        f"teardown ran in the wrong order: {order}")


def test_closing_softproof_does_not_deafen_the_whole_app(qapp, tmp_path):
    """Closing the Soft-proof dialog must not touch the app-wide ArgyllRunner.

    `SoftproofDialog._runner` is the APPLICATION-WIDE singleton; the soft-proof
    runner is `_softproof`. `ArgyllRunner.cleanup()` disconnects
    `line_received`, `finished` and `_pty_done` for the whole process and kills
    any running tool — it exists for app shutdown. Calling it from this dialog
    meant closing Soft-proof silently deafened ChromIQ: the next measurement's
    chartread (a PTY run) would finish and nobody would hear it, so every tab
    and the masthead stayed greyed until restart.

    A duck-typed `getattr(runner, "cleanup", None)` is what made the wrong
    object look right — ArgyllRunner has a `cleanup()` too. This test uses the
    REAL runner; the earlier version set `_runner = None`, which is precisely
    why it could not catch this.
    """
    from core.settings import AppSettings
    from ui.dialogs.softproof_dialog import SoftproofDialog
    from ui.main_window import MainWindow

    s = AppSettings()
    s.set("custom_output_path", str(tmp_path / "out"))
    s.set("session_project", "")
    s.set("restore_last_session", False)
    w = MainWindow(s)
    try:
        qapp.processEvents()
        r = w._runner
        before = (r.receivers(r.finished), r.receivers(r.line_received),
                  r.receivers(r._pty_done))
        assert before[0] > 0, "no baseline observers — this test proves nothing"

        d = SoftproofDialog(r, s, w)
        qapp.processEvents()
        d.reject()
        qapp.processEvents()

        after = (r.receivers(r.finished), r.receivers(r.line_received),
                 r.receivers(r._pty_done))
        assert after == before, (
            f"closing Soft-proof disconnected the app-wide runner: "
            f"{before} -> {after}. The next measurement would never report.")
    finally:
        w.close()


def test_a_second_patch_set_load_does_not_delete_the_first(qapp, tmp_path,
                                                          monkeypatch):
    """The converted .ti1 must outlive the NEXT load.

    `_import_tmp` was a single attribute, reassigned on every patch-set load.
    The previous `TemporaryDirectory` lost its last reference and its finalizer
    deleted the folder — while `_preset_ti1_path` still pointed inside it.
    Generate then logged one line and silently built a fresh targen chart
    instead of the patch set the user had loaded (driven: 2 patches in, 525
    out). Any second load reaches it: a cancelled prompt, a parse failure, a
    file that fails validation.

    DRIVEN THROUGH THE REAL LOADER. An earlier version of this test built the
    holders itself and passed even with the single-attribute bug restored.
    """
    import gc

    from core.settings import AppSettings
    from ui.main_window import MainWindow

    pxf = (pathlib.Path(__file__).resolve().parent / "golden" / "project_v1"
           / "Golden-Printer" / "runs" / "run1" / "Golden-Printer-i1profiler.pxf")
    if not pxf.is_file():
        import pytest as _pytest
        _pytest.skip(f"fixture missing: {pxf}")

    s = AppSettings()
    s.set("custom_output_path", str(tmp_path / "out"))
    s.set("session_project", "")
    s.set("restore_last_session", False)
    w = MainWindow(s)
    try:
        qapp.processEvents()
        # A project must be open, or the loader asks where to copy it to and
        # that modal would hang the run.
        w._file_mgr.set_target_name("Patch Set Load")
        w._file_mgr.project().current_run().ensure_dir()
        w._target_ctl.changed.emit()
        qapp.processEvents()

        tc = w._tab_chart
        monkeypatch.setattr("ui.tabs.tab_chart.open_file_dialog",
                            lambda *a, **k: str(pxf))
        monkeypatch.setattr("ui.tabs.tab_chart.InfoDialog",
                            lambda *a, **k: type("D", (), {"exec": lambda s: 0})())
        # Every confirmation this path can raise, answered as a user would:
        # yes, go ahead. Left unstubbed they hang the run.
        from PyQt6.QtWidgets import QMessageBox
        monkeypatch.setattr(
            QMessageBox, "exec",
            lambda self: (self.setResult(QMessageBox.StandardButton.Yes)
                          or QMessageBox.StandardButton.Yes),
            raising=False)
        monkeypatch.setattr(QMessageBox, "clickedButton",
                            lambda self: (self.buttons() or [None])[0],
                            raising=False)

        tc._on_load_ti1()
        qapp.processEvents()
        holders = getattr(tc, "_import_tmps", [])
        assert len(holders) == 1, (
            f"the real loader did not convert the patch set ({len(holders)} "
            "temp folders) — this test would prove nothing")
        first = pathlib.Path(holders[0].name)
        assert first.is_dir()
        converted = list(first.glob("*.ti1"))
        assert converted, "the conversion produced no .ti1"

        tc._on_load_ti1()          # a SECOND load, through the real loader
        qapp.processEvents()
        gc.collect()

        assert len(getattr(tc, "_import_tmps", [])) == 2, (
            "the second load replaced the first holder instead of keeping it")
        assert first.is_dir() and converted[0].is_file(), (
            "the second load deleted the first load's converted patch set — "
            "`_preset_ti1_path` would point at a file that no longer exists, "
            "and Generate would silently build a fresh targen chart instead")
    finally:
        w.close()
