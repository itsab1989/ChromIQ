"""Shared pytest fixtures.

Neutralise the layout editor's real render path for the whole suite.
``Ti2RelayoutDialog._regenerate`` builds and starts a ``_RegenWorker`` — a
background ``printtarg`` run. On a machine without ArgyllCMS (e.g. a Windows
dev box or CI), that render *fails*, and the worker's ``done`` signal carries an
exception. Because the signal is queued, it is delivered during a *later*
test's event processing (pytest-qt drains the event queue in
``pytest_runtest_setup``), where ``_on_regen_done`` pops a modal
``QMessageBox.warning`` — which blocks the headless suite forever. On macOS with
Argyll installed the render succeeds, so the modal never appears and the leak is
invisible there; this is purely a "passes on Mac, hangs on Windows" hazard.

No test exercises the dialog's real worker (the regenerate logic is covered
directly via ``workflow.ti2_relayout``), and tests that need bespoke behaviour
still override ``_regenerate`` on their own instance. So default it to a no-op
at the class level: no real subprocess, no cross-test signal leak, no modal.
"""
from pathlib import Path



import os
import pathlib
import shutil
import sys
import tempfile

import pytest
# ---------------------------------------------------------------------------
# ONE QApplication PER WORKER, HELD FOR THE WHOLE RUN
# ---------------------------------------------------------------------------
# 179 test files build their own with `QApplication.instance() or
# QApplication([])` inside a MODULE-scoped fixture, and drop the only strong
# reference when that module finishes. Destroying a QApplication does not just
# free the app object: **it sip-deletes every remaining QObject in the
# process**. Python refcounts do not move — the C++ side is deleted underneath
# them — so an object another module still holds becomes a live Python name
# wrapping freed memory.
#
# `ui/widgets.py` publishes the app's AppSettings into a module global
# (`_LOG_SETTINGS`, bound from `ui/main_window.py`) and nothing unbinds it. So
# the first file to tear down its QApplication left every later file with a
# dangling QSettings, and the next panel to size itself raised
# "wrapped C/C++ object of type QSettings has been deleted".
#
# That is the shared state behind the gate's intermittent failures: a different
# victim each run, every one passing alone, because it depends on which file
# happened to tear down first on that worker.
#
# Holding one here fixes all 179 without touching them: they all ask for
# `QApplication.instance()` first, and now always get this one.
_PINNED_QAPP = None


# ---------------------------------------------------------------------------
# A MODAL DIALOG IN A TEST NAMES ITSELF INSTEAD OF HANGING FOR EVER
# ---------------------------------------------------------------------------
# `dlg.exec()` with no user never returns, and NOTHING can break it: a
# `pytest-timeout` thread cannot interrupt a Qt modal event loop, so the run
# stops dead with no attribution. It happened on 2026-08-25 — the gate sat at
# 99 % and only a faulthandler dump named `ui/ti2_loader.py:1190`.
#
# A watchdog, not a ban. A test that legitimately drives a dialog still works,
# because the timer only fires if the dialog is STILL up after the grace
# period; then it closes it and the test fails with the dialog's own title in
# the message. A test that monkeypatches `exec` itself still wins — this only
# wraps what is left.
#
# It must cover the STATIC helpers too: 68 of the ~216 modal entry points in
# this app never touch `QDialog.exec` at all (41 `QMessageBox.warning`, 14
# `.information`, 6 `.critical`, 2 `.question`, 4 `QColorDialog`, 1
# `QInputDialog`), and only 8 lines in the whole suite touch any of them.
MODAL_GRACE_MS = 4000


@pytest.fixture(autouse=True)
def _no_modal_may_hang_the_suite(request):
    """Close any dialog still modal after `MODAL_GRACE_MS` and fail the test."""
    from PyQt6.QtCore import QTimer
    from PyQt6.QtWidgets import QApplication, QDialog, QMessageBox

    stuck: list = []

    def _sweep():
        for w in QApplication.topLevelWidgets():
            if isinstance(w, QDialog) and w.isVisible() and w.isModal():
                stuck.append(w.windowTitle() or type(w).__name__)
                w.reject()
            elif isinstance(w, QMessageBox) and w.isVisible():
                stuck.append(w.windowTitle() or w.text()[:60])
                w.close()

    timer = QTimer()
    timer.setInterval(MODAL_GRACE_MS)
    timer.timeout.connect(_sweep)
    timer.start()
    try:
        yield
    finally:
        timer.stop()
    if stuck:
        raise AssertionError(
            "a modal dialog was left open and would have hung the run: "
            + ", ".join(sorted(set(stuck)))
            + "\nStub it in the test, or fix the code path that opens it with "
              "no project / no user present.")



@pytest.fixture(scope="session", autouse=True)
def _one_qapplication_per_worker():
    """Create the QApplication once, ON THE STYLE THE APP SHIPS, and keep it
    alive for the whole session.

    THE SUITE USED TO PAINT THROUGH A STYLE THE USER NEVER GETS.
    `main.py` line 147 does ``app.setStyle(WinButtonLayoutStyle("Fusion"))``
    before it builds a single window, on every platform. The suite never runs
    `main()`, so until this line it took whatever the platform plugin handed it:
    Fusion under `offscreen`, **QWindows11Style on Windows**, QMacStyle under
    cocoa. Three different styles, none of them the shipped one.

    That is not a detail. Every size, rect and pixel this suite asserts on comes
    out of the style, so a gate on the wrong style can neither catch a real
    styling fault nor be believed about one it reports.

    It may also be why the 2026-09-03 gate on the owner's Windows ARM64 VM
    killed a worker inside a `QStyle::drawControl` call, from
    `WrappingCheckBox.paintEvent`, while the same widgets rendered correctly in
    the running app all evening. **That is a lead, not a finding**, and the one
    thing that would settle it is not recorded: neither the report nor either
    gate log says whether `QT_QPA_PLATFORM=offscreen` was set for those runs. If
    it was — as CLAUDE.md's documented command does — that gate was already on
    Fusion and the style had nothing to do with it. Either way this line is
    right, because a gate should measure what ships.

    So the suite is pinned to **Fusion**, which is the style the app draws with,
    on every platform and every plugin.

    WHY FUSION AND NOT `WinButtonLayoutStyle("Fusion")` ITSELF. The proxy
    overrides exactly one thing — `SH_DialogButtonLayout`, the ORDER of the
    buttons in a QDialogButtonBox. It draws nothing. But it is a Python
    reimplementation of `styleHint`, which Qt asks for constantly, and every one
    of those calls then crosses into Python: measured on the everyday tier,
    2026-09-03, `-n auto`, same machine, back to back —

        platform default (was: whatever the plugin gave)   106.6 s
        setStyle("Fusion")                                 114.5 s
        setStyle(WinButtonLayoutStyle("Fusion"))           133.2 s

    — and the proxy run also turned one unrelated test red that passes on its
    own. 27 s of gate for a button-order hint no test asserts on is the wrong
    trade; the hint deserves its own small test rather than a tax on all ten
    thousand. What matters here is the PAINTING style, and Fusion is that.
    """
    global _PINNED_QAPP
    from PyQt6.QtWidgets import QApplication

    _PINNED_QAPP = QApplication.instance() or QApplication([])

    # ...AND ON THE FONTS THE APP SHIPS, for the same reason and from the same
    # place: this is `main()`'s very next statement after the QApplication, one
    # line above its `setStyle`. Registering them here is not a test fixture
    # inventing an environment — it is the suite finally doing what the program
    # does before it draws anything.
    #
    # WITHOUT IT THE GEOMETRY ASSERTIONS MEASURE A FONT THAT DOES NOT EXIST.
    # Under `QT_QPA_PLATFORM=offscreen` on Windows/ARM64, Qt 6.11,
    # `QFontDatabase.families()` returns an EMPTY LIST — the plugin exposes no
    # font whatever — and Qt then measures every glyph as a square box of
    # pixelSize: `w("i") == w("W") == 13`. "Manuelle Einstellungen" comes out
    # 286 px as tofu against 144 px in real Inter, a 1.99x overestimate, and
    # `ui/styles.py` asks for "Inter" on every widget. Any test that asserts a
    # label fits, a panel does not scroll sideways, or a sheet paginates, is on
    # that plugin asserting against a fiction — in both directions: it cannot
    # catch a real clipping fault and it reports ones that are not there.
    #
    # It is also a source of ORDER-DEPENDENT FLAKES rather than steady failure,
    # because whether a worker has fonts depends on whether some earlier test in
    # it happened to register them.
    try:
        from core.resource_path import resource_path
        from PyQt6.QtGui import QFontDatabase
        for _font_path in resource_path("assets/fonts").glob("*.ttf"):
            QFontDatabase.addApplicationFont(str(_font_path))
    except Exception:                                    # pragma: no cover
        pass          # exactly as main.py does: fonts dir missing is not fatal

    try:
        _PINNED_QAPP.setStyle("Fusion")
    except Exception:                                    # pragma: no cover
        pass          # a Qt build without Fusion: better the platform default
                      # than no QApplication at all
    yield _PINNED_QAPP
    # Deliberately NOT destroyed: tearing it down at session end would delete
    # every QObject still alive during other fixtures' teardown, which is the
    # fault this exists to prevent.



# Keep the suite off the user's real application log. core.logger's
# configure_logging() installs a RotatingFileHandler on the real
# ~/.../ChromIQ/Logs/chromiq.log and returns early if the root logger already
# has a handler. Pre-install a NullHandler here — BEFORE the first `core` import
# below triggers configure_logging() — so the app never attaches its file
# handler during tests: the real log is left untouched, and nothing is written
# to disk to clean up afterwards. On Windows this also removes ~1000 lines of
# swallowed "PermissionError: [WinError 32]" per gate run — the four xdist
# workers were each rotating that one shared 5 MB file, and Windows refuses to
# rename a file another process still holds open. pytest's own log capture
# (caplog) attaches its handler independently and is unaffected.
import logging as _logging
_root_logger = _logging.getLogger()
if not _root_logger.handlers:
    _root_logger.addHandler(_logging.NullHandler())
    _root_logger.setLevel(_logging.DEBUG)


#: The highest worker count this suite is currently RELIABLE at — see CLAUDE.md
#: for the measurements. Kept here as a fact, not enforced: capping ``-n auto``
#: from a conftest hook does not work, because pytest-xdist has already read
#: the option by the time any hook here can change it (tried, and it silently
#: ran at full parallelism anyway). So the number lives in the documented
#: command instead, where it cannot fail quietly.
SAFE_WORKERS = 4


# Make helper modules that live beside the tests (e.g. ``tests/_fontcheck.py``)
# importable with a bare ``import _fontcheck`` from any test. pytest puts the
# rootdir on sys.path but not reliably this directory, so without it such an
# import fails depending on the import mode.
sys.path.insert(0, str(Path(__file__).resolve().parent))

# On Windows/ARM, make freetype-py find our vendored ARM64 FreeType before any
# test imports `freetype` (e.g. test_vector_pdf collects it at module load), so
# the vector-PDF tests actually run there instead of skipping (#72). No-op on
# every other platform.
from core.freetype_bootstrap import ensure_freetype_library

ensure_freetype_library()


@pytest.fixture(autouse=True)
def _repair_a_leaked_qmessagebox_exec():
    """Undo a `QMessageBox.exec` patch an earlier test failed to restore.

    `exec` is INHERITED from `QDialog`, so the common idiom

        real = QMessageBox.exec
        QMessageBox.exec = _fake
        try: ...
        finally: QMessageBox.exec = real

    does **not** put it back: it installs a plain method object directly on
    `QMessageBox`, which no longer binds. From then on every `box.exec()` **in
    that worker process** is called with no `self` and dies with

        TypeError: first argument of unbound method must have type 'QDialog'

    ...inside whatever file xdist happens to schedule next. So the failure names
    an innocent test and looks exactly like flakiness. It cost two full gates on
    2026-08-08: the tests it broke passed alone AND under `-n 4` alone, and the
    culprit was two files away.

    Exactly TWO tests ever used that idiom (in test_knut_beta74_batch and
    test_knut_beta87_batch); both were migrated to `monkeypatch.setattr` on
    2026-08-08, and every other site — 68 of them — had always used monkeypatch,
    which handles this correctly: it records that the attribute was inherited
    and *deletes* it on undo. This fixture is therefore defence in depth, kept
    because the idiom is an easy one to reach for again.

    **A correction, recorded because it was stated publicly.** An earlier version
    of this comment claimed "about 77 tests still use that idiom". That was
    wrong, and the number came from misreading this fixture's own first draft:
    that draft ran in TEARDOWN, where it raced monkeypatch's undo — it saw the
    attribute still patched for tests that had done everything right, flagged all
    68 of them, and by deleting the attribute made monkeypatch's own undo fail.
    The "77 errors" were the guard breaking correct tests, not 77 bad tests.

    **In setup, deliberately.** Two teardown versions were written and reverted:
    one failed the offending test, turning a single leak into 4,859 errors
    because the attribute stayed patched for everything after it; the other
    produced the 77 errors described above. Nothing here can fail a test — it
    only removes an attribute that should not exist, before the test starts.
    """
    try:
        from PyQt6.QtWidgets import QMessageBox
        if "exec" in QMessageBox.__dict__:
            del QMessageBox.exec
    except Exception:      # noqa: BLE001 — a repair must never fail a test
        pass


@pytest.fixture(autouse=True)
def _no_leaked_session_restore():
    """Start every test with "restore the last session" OFF, whatever the test
    before it left in the store.

    THIS IS THE B8-43 FLAKE, AND IT TOOK THREE DAYS AND FOUR GATE RUNS.
    `test_a_cancel_downstream_keeps_what_was_filed.py::
    test_a_cross_tab_chart_load_takes_the_130_road` failed in roughly one full
    parallel run in seven, passed every time alone, and named nothing: an
    `assert [] == ['#130']` plus a teardown ERROR saying a QMessageBox had been
    left open. Reproduced deterministically in ten seconds as

        pytest tests/test_no_project_is_ever_invented.py \
               tests/test_a_cancel_downstream_keeps_what_was_filed.py

    and in that order only — the other way round, and either file alone, is
    green.

    THE MECHANISM, END TO END.
    `test_no_project_is_ever_invented` legitimately switches
    `restore_last_session` on and points `session_target_name` at a project that
    is not on disk — that is what it is testing. It never puts them back, and
    `AppSettings` is one store per WORKER PROCESS, so both keys survive into
    every file xdist schedules onto that worker afterwards. Which files those
    are changes from run to run under `--dist loadfile`. **That is the whole of
    the intermittency.**

    In a poisoned worker, `MainWindow.__init__` reads the key and queues
    `QTimer.singleShot(0, self._restore_last_session)`. A fixture that then
    opens a project runs no event loop, so the restore is still pending when
    setup ends — and **pytest-qt's `pytest_runtest_setup` is a hook wrapper that
    calls `QApplication.processEvents()` after its `yield`**. The restore fires
    there, calls `set_target_name("Real-Project")` over the project the fixture
    had just opened, finds no such project on disk, and calls `close_project()`.
    The test then runs against a file manager holding nothing:
    `resolve_ti2` sees no loaded project, takes the "this chart belongs to a
    project — open it?" road instead of the #130 one, and opens a modal that
    only the 4-second sweeper above can close.

    AND IT COULD NOT BE READ OFF THE REPORT. Because that all happens in
    pytest-qt's POST-yield wrapper, it is outside the setup phase's log capture
    and before the call phase's — so `Target name set to`,
    `Session restore skipped` and `Project closed` appear in no captured
    section at all. The red report showed a project being opened and never
    closed, which is why the cause was looked for everywhere else.

    IN SETUP, DELIBERATELY, and for the same reason as
    `_repair_a_leaked_qmessagebox_exec` above: a teardown version would race the
    monkeypatch undo of any test that sets these keys properly. Clearing them
    before each test leaves the one file that legitimately turns them on
    working — it sets them in its own body, after setup — and gives every other
    file the state `pytest_configure` created.

    Eleven test files already wrote `restore_last_session = False` into their own
    fixtures by hand. That is eleven authors finding this the hard way and
    immunising one fixture each; the twelfth fixture is the one that failed.
    """
    import core.settings as _cs

    # ONLY when the store has been sandboxed. `pytest_configure` replaces this
    # name with a factory function; if it is still the real `QSettings` class
    # something has gone wrong upstream and this must not write to the
    # developer's own preferences to "repair" anything.
    if isinstance(_cs.QSettings, type):
        return
    try:
        qs = _cs.QSettings("ChromIQ", "ChromIQ")
        for key in ("restore_last_session", "session_target_name",
                    "session_project_root"):
            qs.remove(key)         # → back to DEFAULTS, which is off/empty
    except Exception:      # noqa: BLE001 — a repair must never fail a test
        pass


@pytest.fixture(autouse=True)
def _no_real_usb_device_list(monkeypatch):
    """NO TEST MAY DEPEND ON WHAT IS PLUGGED INTO THE MACHINE RUNNING IT.

    `core.argyll_instruments.usb_devices()` reads the operating system's live
    USB list, and the spot tool decides which reader to use from it. Left
    unstubbed, "is an ArgyllCMS instrument attached?" would be answered by
    whatever happens to be on the developer's desk: the same test would pass on
    CI, fail on the owner's Mac with his ColorMunki plugged in, and nobody
    would be able to tell which answer was the real one.

    Same principle, and the same reason, as the sandboxed `QSettings` in
    `pytest_configure`. A test that wants a device attached says so by
    patching this itself.
    """
    try:
        from core import argyll_instruments
    except Exception:      # noqa: BLE001 — nothing to stub
        return
    monkeypatch.setattr(argyll_instruments, "usb_devices", lambda: (),
                        raising=False)


@pytest.fixture(autouse=True)
def _no_real_editor_render(monkeypatch):
    try:
        from ui.dialogs.ti2_relayout_dialog import Ti2RelayoutDialog
    except Exception:
        # PyQt6 unavailable (or import error) — nothing to stub.
        return
    monkeypatch.setattr(Ti2RelayoutDialog, "_regenerate",
                        lambda self, *a, **k: None, raising=False)


@pytest.fixture(autouse=True)
def _no_native_print_dialog(monkeypatch):
    """Never let a test open the Qt native print dialog — it blocks for ever.

    The same "passes on Mac, hangs on Windows" shape as the editor render above.
    ``TabPrint._print_native_qt`` opens ``QPrintDialog(...).exec()``, a modal
    with no one to click it, so any test that reaches it wedges the headless
    suite until it is killed. And it IS reached on Windows even when a test sets
    ``use_native_print_dialog`` False: ``AppSettings.get`` forces that flag True
    on Windows (there is no ``lp`` there), so ``_on_print_current`` takes the
    native branch, whereas on macOS the same branch goes to the driver-native
    path instead of a Qt modal — which is why it only hangs on Windows (#130,
    beta.221 gate). Tests that care about the print path stub ``_print_pages`` /
    ``_print_native`` themselves and assert on the conversion + record, which
    happen before this call; this only removes the un-clickable window.
    """
    try:
        from ui.tabs.tab_print import TabPrint
    except Exception:
        pass
    else:
        monkeypatch.setattr(TabPrint, "_print_native_qt",
                            lambda self, *a, **k: None, raising=False)
    # The Help cards gained their own Print button (#164), and it opens the same
    # un-clickable modal. `_exec_print_dialog` is one line on its own precisely
    # so it can be replaced here; declining is the safe answer, so nothing is
    # ever actually sent to a printer from a test run.
    try:
        from ui import help_card_print
    except Exception:
        return
    monkeypatch.setattr(help_card_print, "_exec_print_dialog",
                        lambda dlg: False, raising=False)


# ---------------------------------------------------------------------------
# The suite never writes into the user's real ChromIQ folder.
#
# Basti, 2026-08-01: *"some of those tests create files on my machine every time
# they run … until now i deleted them manually"* — 77 project folders named
# `Printer_Paper_Type_Instr_<timestamp>` had accumulated, one per gate run.
#
# The trap is quiet. Overriding a test's QSettings is not enough: with
# `custom_output_path` left at its default of "", the FileManager falls back to
# ~/ChromIQ, and anything that asks where it is working makes
# `get_target_name()` INVENT that name and create the folder. A test can look
# perfectly isolated and still do this.
#
# So it is caught here rather than left to review, and named per test. Nothing
# is ever deleted: the folder holds real projects, and a test suite that tidies
# a developer's data is a worse idea than one that leaves a mess.
# ---------------------------------------------------------------------------
_REAL_CHROMIQ = Path.home() / "ChromIQ"


#: Trees under the real folder that are not projects and are expected to have
#: their own contents change (a cache the suite owns). Nothing today, but the
#: fingerprint below is recursive and this is where an exception would go.
_FINGERPRINT_SKIP: tuple = ()


def _real_chromiq_entries() -> dict:
    """A RECURSIVE fingerprint of the real ~/ChromIQ: relative path → (size, mtime).

    NAMES ALONE WERE NOT ENOUGH, and the gap was not theoretical. Comparing the
    top level only meant that anything written INSIDE a folder that already
    existed produced no new name, so the assert passed and the gate stayed
    green. Measured on 2026-08-28: two consecutive gate runs ran ArgyllCMS
    `scanin` with its working directory set to
    `~/ChromIQ/scanner-test-targets/real` — the owner's own scans — and scanin
    writes beside its input, so a 37 MB `diag.tif` of his from 9 July and both
    `.ti3` files were silently rewritten while this guard reported nothing.

    Size and mtime catch an overwrite as well as a creation. Reading the tree
    costs a fraction of a second on a real folder and runs once per test.
    """
    out: dict = {}
    try:
        for p in _REAL_CHROMIQ.rglob("*"):
            try:
                rel = p.relative_to(_REAL_CHROMIQ)
                if rel.parts and rel.parts[0] in _FINGERPRINT_SKIP:
                    continue
                if p.is_dir():
                    out[str(rel) + "/"] = None
                else:
                    st = p.stat()
                    out[str(rel)] = (st.st_size, st.st_mtime_ns)
            except OSError:
                continue
    except OSError:
        return {}
    return out


#: Only a BACKSTOP now. A run that finishes deletes its own files (see
#: pytest_sessionfinish), so the only trees this can find are from a run that
#: never got that far: a crash, a kill, a power cut. One hour is comfortably
#: longer than the slowest gate, so a run in progress is never touched.
_STALE_AFTER_HOURS = 1

#: Never swept, whatever its age: rebuilding it costs about four minutes per
#: gate, which is the whole reason it exists.
_KEEP_FOREVER = ("chromiq-demo-projects-cache",)


def _folder_size(folder: pathlib.Path) -> int:
    """Bytes under *folder*, ignoring anything unreadable.

    Measured separately from the delete, and never allowed to raise: a file we
    cannot stat is a reason to report a smaller number, not a reason to leave
    the folder on disk.
    """
    total = 0
    for item in folder.rglob("*"):
        try:
            if item.is_file():
                total += item.stat().st_size
        except OSError:
            continue
    return total


def _force_writable(func, path, _exc) -> None:
    """rmtree error handler: clear the read-only bit and try once more.

    Windows refuses to delete a read-only file, and ``ignore_errors=True``
    would simply leave it — which on Basti's VM would mean the sweep reporting
    success while the disk stayed full. Everything else is swallowed, because
    a folder that cannot be removed now is retried by the next run.
    """
    import stat as _stat

    try:
        os.chmod(path, _stat.S_IWRITE)
        func(path)
    except Exception:      # noqa: BLE001 — cleanup must never fail a test run
        pass


def _sweep_stale_temp_dirs() -> "tuple[int, int]":
    """Delete what earlier test runs left in the system temp folder.

    Returns ``(folders, bytes)`` removed. Basti, 2026-08-05, having found 5.0 GB
    of them: *"can you modify the tests in a way that they clean the created
    files up when done (either successful or failed) and that they also check
    and clean the files from older runs so the disk space is freed again?"*

    The leak was ``tempfile.mkdtemp()``, which nothing ever removes — unlike
    pytest's own ``tmp_path``, which is cleaned up whether a test passes or
    fails and keeps only the last few runs. Those call sites now use
    ``tmp_path``; this sweeps the history, and catches any that come back.
    """
    import time

    root = pathlib.Path(tempfile.gettempdir())
    cutoff = time.time() - _STALE_AFTER_HOURS * 3600
    keep = set(_KEEP_FOREVER)
    cache = os.environ.get("CHROMIQ_DEMO_CACHE")
    if cache:
        keep.add(pathlib.Path(cache).name)

    folders = freed = 0
    # pytest's OWN trees, which it is supposed to prune to the last few — but
    # it skips any directory whose .lock file is still there, and a run that
    # CRASHES leaves its lock behind. Measured 2026-08-05: a tree from three
    # days earlier still sitting at 1.0 GB, and this afternoon's segfaulted
    # worker leaving another. So every crash quietly costs a gigabyte, which is
    # how 2.3 GB accumulated without anyone noticing.
    candidates = list(root.glob("chromiq[-_]*"))
    for base in root.glob("pytest-of-*"):
        if base.is_dir():
            candidates += [d for d in base.glob("pytest-*") if d.is_dir()]

    for entry in candidates:
        if entry.name in keep or not entry.is_dir():
            continue
        if entry.name == "pytest-current" or entry.is_symlink():
            continue                         # pytest's pointer at the live run
        try:
            if entry.stat().st_mtime > cutoff:
                continue                     # a run in progress
        except OSError:
            continue                         # vanished between glob and stat
        size = _folder_size(entry)
        shutil.rmtree(entry, onerror=_force_writable)
        if not entry.exists():
            folders += 1
            freed += size
    return folders, freed


# ---------------------------------------------------------------------------
# A WORKER THAT DIES CAN NEVER BE A GREEN RUN
# ---------------------------------------------------------------------------
# When an xdist worker segfaults, pytest-xdist prints two quiet lines in the
# middle of nine thousand dots —
#
#     [gw4] node down: Not properly terminated
#     replacing crashed worker gw4
#
# — and then carries on. What happens after that is decided by nothing anybody
# controls:
#
#   * if the worker was RUNNING a test, `DSession.worker_errordown` asks the
#     scheduler for the first item it had not finished and reports THAT test as
#     FAILED, with "worker 'gwN' crashed while running <nodeid>". That reads
#     exactly like a test failure and is not one. Somebody then spends an hour
#     deciding whether it was their change; that is what happened here on
#     2026-09-02, four times over.
#   * if the worker had nothing left to finish,
#     `LoadScopeScheduling.remove_node` returns None
#     (`if not self._pending_of(workload): return None`), nothing at all is
#     recorded, and the run prints `N passed` and **exits 0 with a dead worker
#     in it**.
#
# The second is the one that matters, because the gate's whole job is to be
# believed when it is green.
#
# So every node-down carrying an error is recorded, said out loud in the summary
# where a human actually looks, and made to cost the run its exit code. Nothing
# here hides or retries anything — a crash still crashes. It can simply no
# longer be mistaken for a test failure, and can no longer be a pass.
_CRASHED_WORKERS: list = []


@pytest.hookimpl(optionalhook=True)
def pytest_testnodedown(node, error):
    """xdist hook, master process only. `optionalhook` so a run without xdist
    (a single file, `pytest tests/test_x.py`) does not fail on an unknown hook.

    `error` is None for a worker that finished cleanly and a message
    ("Not properly terminated") for one whose process DIED.
    """
    if error is None:
        return
    gw = getattr(getattr(node, "gateway", None), "id", "?")
    _CRASHED_WORKERS.append((str(gw), str(error)))


def pytest_terminal_summary(terminalreporter, exitstatus, config):
    """Say it where a human looks: in the summary, in red, in full sentences.

    The two lines xdist prints scroll past mid-run under thousands of dots. And
    a reader who does find a traceback in the log has no way to tell this apart
    from the OTHER multi-thread dump this suite produces — the one
    `faulthandler_timeout` writes when a test is merely slow, which begins
    `Timeout (0:0X:XX)!` and means nothing is wrong. A reviewer read one of
    those, in a green run, as evidence of a crash. So the difference is spelt
    out here instead of being left to be re-derived.
    """
    _skip_census(terminalreporter, config)
    if not _CRASHED_WORKERS:
        return
    w = terminalreporter
    w.write_sep("=", "A WORKER PROCESS DIED — THIS RUN PROVES NOTHING",
                red=True, bold=True)
    for gw, error in _CRASHED_WORKERS:
        w.write_line(f"  {gw}: {error}", red=True)
    w.write_line("")
    w.write_line("  This is NOT an assertion failure. One of the processes "
                 "running the suite crashed")
    w.write_line("  (search the log above for 'Fatal Python error'), and "
                 "pytest-xdist then blamed")
    w.write_line("  whichever test that worker happened to be holding — or "
                 "nothing at all. Any test")
    w.write_line("  in the FAILED list because of this is a bystander: re-run "
                 "it on its own before")
    w.write_line("  you believe it.")
    w.write_line("")
    w.write_line("  It is NOT the same thing as a 'Timeout (0:0X:XX)!' dump. "
                 "That one is pytest.ini's")
    w.write_line("  faulthandler_timeout firing on a slow test, it is "
                 "harmless, and it never reaches")
    w.write_line("  this banner.")
    w.write_line("")
    w.write_line("  The run is reported as FAILED whatever the test counts "
                 "say.", red=True, bold=True)


def pytest_sessionfinish(session, exitstatus):
    """Delete THIS run's temp tree the moment it is over — if it passed.

    Basti, 2026-08-05: *"is this 2 hour safety really required? i don't want
    this much left on my machine. can't there be an automatism that deletes
    this stuff automatically when the test run is done and checked?"* — and he
    is right that an age threshold is the wrong instrument. The run itself
    knows when it is finished, and knowing beats guessing.

    **A green run leaves nothing behind.** A run with failures keeps its tree
    and says where it is, because that tree is the evidence: the chart that
    came out wrong, the .ti3 that would not parse, the profile that was built
    from it. Deleting it would throw away the only copy of what went wrong.

    Master process only — under xdist the workers share one tree, and a worker
    removing it while the others are still writing would fail the run.
    """
    if hasattr(session.config, "workerinput"):
        return

    # THE EXIT CODE. `wrap_session` returns `session.exitstatus` AFTER every
    # `pytest_sessionfinish` hook has run (_pytest/main.py), so setting it here
    # is what actually reaches the shell — and the shell is what a release
    # decision is made on. A dead worker means the run did not do what it
    # claims to have done, whatever the counts say.
    if _CRASHED_WORKERS:
        session.exitstatus = 1
        exitstatus = 1

    factory = getattr(session.config, "_tmp_path_factory", None)
    if factory is None:
        return
    try:
        base = pathlib.Path(factory.getbasetemp())
    except Exception:      # noqa: BLE001 — never fail a run over cleanup
        return
    if exitstatus != 0:
        print(f"\n[cleanup] run did not pass — its files are kept for you at\n"
              f"          {base}")
        return
    freed = _folder_size(base)
    shutil.rmtree(base, onerror=_force_writable)
    # pytest's "newest run" symlink now points at nothing; tidy it away too.
    for link in base.parent.glob("pytest-current*"):
        try:
            if link.is_symlink() and not link.resolve().exists():
                link.unlink()
        except OSError:
            pass
    if not base.exists() and freed:
        print(f"\n[cleanup] removed this run's temp files ({freed / 1e9:.2f} GB)")


def pytest_sessionstart(session):
    """Free what earlier runs left behind, once per run.

    Guarded on the master process: under xdist every worker runs this hook, and
    four of them sweeping the same folders at once would race each other.
    """
    if hasattr(session.config, "workerinput"):
        return                               # an xdist worker, not the master
    _say_it_even_when_quiet(session)
    folders, freed = _sweep_stale_temp_dirs()
    if folders:
        print(f"\n[cleanup] removed {folders} leftover temp folder(s) from "
              f"earlier runs, freeing {freed / 1e9:.2f} GB")


@pytest.fixture(autouse=True)
def _no_leaked_replay_helpers():
    """Kill any chromiq-chartread helper a test left running.

    ``ReplaySession.finish()`` kills it, and the engine tests call that at the
    end of the happy path — so a test that FAILS or raises first leaves the
    helper alive, waiting on stdin, for ever. Measured 2026-08-05 after a day
    of runs that included several failures: **162 alive at once**, which
    starved a gate worker into a segmentation fault at 97% and wedged the run.

    Looked up in ``sys.modules`` rather than imported, so the ~4,400 tests that
    never touch the replay helper do not pay for it.
    """
    yield
    # BOTH names: tests/helpers is on sys.path, so some files import it as
    # ``replay_tools`` and others as ``tests.helpers.replay_tools``. Python
    # then holds two separate module objects with a registry each, and looking
    # up only one of them silently reaped nothing — which is how the first
    # version of this fixture passed while helpers kept leaking.
    leaked = 0
    for name, module in list(sys.modules.items()):
        if name.rsplit(".", 1)[-1] != "replay_tools":
            continue
        reap = getattr(module, "reap_live_sessions", None)
        if callable(reap):
            leaked += reap()
    if leaked:
        print(f"\n[cleanup] killed {leaked} leaked chromiq-chartread "
              f"helper(s) — a session was not finished")


def _real_chromiq_names() -> set:
    """Just the top-level names — cheap enough to run around every test."""
    try:
        return {p.name for p in _REAL_CHROMIQ.iterdir()}
    except OSError:
        return set()


@pytest.fixture(autouse=True)
def _never_touch_the_real_chromiq_folder():
    """Fail a test that CREATES anything in the user's real ~/ChromIQ.

    Names only, because this runs around every one of ~7,700 tests. A write
    INSIDE a folder that already exists produces no new name and is invisible
    here — that is what `_no_gate_run_may_rewrite_the_real_chromiq_folder`
    below is for; this one exists to name the guilty test, which a session-wide
    check cannot do.

    **It only catches a stray once.** The comparison is against what was there
    when the test started, so a folder left behind by an earlier run is already
    in ``before`` and is invisible from then on — the offending test goes green
    while still writing into the developer's own projects. That is not
    hypothetical: a test added on 2026-08-06 did exactly this for several runs
    after its first failure was read as a one-off.

    So when this fires, **delete the folder it names** before re-running.
    Nothing is deleted automatically, because the folder might be a real
    project that a test happened to touch.
    """
    before = _real_chromiq_names()
    yield
    new = sorted(_real_chromiq_names() - before)
    assert not new, (
        "this test wrote into the real ~/ChromIQ folder: "
        f"{new}\n"
        "Point the settings at tmp_path — overriding QSettings alone leaves "
        "custom_output_path at its default, which IS ~/ChromIQ:\n"
        '    s.set("custom_output_path", str(tmp_path / "out"))\n'
        "Nothing has been deleted; remove the stray folder(s) by hand if you "
        "want them gone."
    )


@pytest.fixture
def the_real_default_output_root(monkeypatch):
    """The opt-in for a test that is ABOUT the default output root.

    `pytest_configure` points `CHROMIQ_OUTPUT_ROOT` at a sandbox so no test can
    reach the owner's real `~/ChromIQ` by accident. A handful of tests exist to
    prove what the fallback IS, and they cannot do that with the fallback
    moved. Ask for this fixture and the override is lifted for the one test.

    It lifts the override, not the guards: `_never_touch_the_real_chromiq_
    folder` and `_no_gate_run_may_rewrite_the_real_chromiq_folder` both compute
    the real folder from `Path.home()` directly and still fail a test that
    WRITES there. So this is a licence to look, never to touch.
    """
    monkeypatch.delenv("CHROMIQ_OUTPUT_ROOT", raising=False)
    from core.platform_paths import default_output_root
    return default_output_root()


@pytest.fixture(scope="session", autouse=True)
def _no_gate_run_may_rewrite_the_real_chromiq_folder():
    """Fail the RUN if it changed anything inside the user's real ~/ChromIQ.

    THE PER-TEST GUARD ABOVE COMPARES TOP-LEVEL NAMES, AND THAT WAS NOT ENOUGH.
    Anything written inside a folder that already existed produced no new name,
    so the assert passed and the gate stayed green. Measured on 2026-08-28:
    consecutive gate runs had been rewriting a whole run of the owner's
    "Red River Paper … Letter 2052p 9pages" project — twenty TIFFs, the .ti1,
    the .ti2, the exports — because a built-in preset's default name happens to
    equal that project's folder name and `custom_output_path` fell back to ""
    (which IS ~/ChromIQ); and ArgyllCMS `scanin` was being run with its working
    directory set to his own IT8 scans, rewriting a 37 MB diagnostic image of
    his from July on every run.

    Recursive, so it sees those; session-scoped, so it costs one tree walk at
    each end of the run instead of two per test. Per-test it added forty
    seconds to the gate and perturbed timing-sensitive layout tests.
    """
    before = _real_chromiq_entries()
    yield
    after = _real_chromiq_entries()
    changed = sorted(k for k in set(after) & set(before)
                     if after[k] != before[k])
    created = sorted(set(after) - set(before))
    assert not changed and not created, (
        "THIS RUN WROTE INTO THE REAL ~/ChromIQ FOLDER.\n"
        f"  rewritten: {changed}\n"
        f"  created:   {created}\n"
        "A rewritten file cannot be given back — it holds whatever the test "
        "produced. Find the writer with a tripwire on FileManager.root_dir, "
        "and remember that overriding QSettings alone is not enough: "
        "custom_output_path then falls back to \"\", which IS ~/ChromIQ."
    )


# ---------------------------------------------------------------------------
# Two-tier suite (#123 follow-up): heavy end-to-end profile builds carry
# @pytest.mark.slow and are skipped in everyday runs — `pytest --runslow`
# includes them, and the release gate always runs with --runslow.
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# THE SETTINGS STORE IS THE DEVELOPER'S OWN. Isolate it before anything runs.
# ---------------------------------------------------------------------------
# `_never_touch_the_real_chromiq_folder` guards the ~/ChromIQ FOLDER. Nothing
# guarded the QSettings STORE, and `AppSettings()` — which 101 test files
# construct — is `QSettings("ChromIQ", "ChromIQ")`, the real one. CLAUDE.md has
# said so for a while: *"a test run also writes to the developer's own
# preferences"*.
#
# It is not theoretical. On 2026-08-07 the user's live `custom_output_path` was
# found pointing at
#     …/pytest-of-Basti/pytest-2/popen-gw0/test_a_healthy_project_says_no0/out
# a sandbox that no longer existed, so his ChromIQ could not see a single one of
# his projects. `chartread_engine` had been flipped to "argyll" too — he had
# reported the engine "disabling itself" more than once and nobody had connected
# the two.
#
# Qt cannot do this for us on macOS. `QSettings("ChromIQ", "ChromIQ")` — the
# two-argument constructor AppSettings uses — resolves to the native plist and
# ignores setDefaultFormat(); only the no-argument form honours it, and
# QSettings.setPath() is documented as having no effect on NativeFormat there:
#
#     QSettings('ChromIQ','ChromIQ') -> ~/Library/Preferences/com.chromiq.ChromIQ.plist
#     QSettings()                    -> the redirected .ini
#
# A first attempt at this used setDefaultFormat + setPath, passed a single-file
# check, and still let the full gate rewrite the user's live custom_output_path
# and flip chartread_engine back to "argyll". So the redirect happens where it
# actually bites: the name `core.settings.QSettings`, which is what
# `AppSettings()` calls.
def pytest_configure(config):
    import tempfile

    _enforce_the_helper(config)

    from PyQt6.QtCore import QSettings

    import core.settings as _cs

    sandbox = pathlib.Path(tempfile.mkdtemp(prefix="chromiq-settings-"))
    ini = sandbox / "ChromIQ.ini"

    # …AND THE FILE-BACKED PRESET STORE, which the QSettings sandbox below does
    # NOT cover. `core.platform_paths.presets_dir()` resolves to the real
    # ~/Library/Preferences/ChromIQ/presets, so any test reaching
    # `save_presets(...)` wrote into the developer's own preferences. Only one
    # test does today and it patches correctly, but nothing enforced that.
    os.environ.setdefault(
        "CHROMIQ_PRESETS_DIR", str(sandbox / "presets"))

    # …AND THE FALLBACK ITSELF, which is the door the two fixes below could
    # never shut.
    #
    # Seeding `custom_output_path` in the ini and moving `DEFAULTS` covers
    # `AppSettings` and every double built from `DEFAULTS`. It does NOT cover a
    # hand-written double whose store is its own dict (`.get("custom_output_
    # path", "")` answers ""), a `settings=None`, or the nineteen places, in
    # fourteen files, that built `Path.home() / "ChromIQ"` for themselves and
    # never asked the settings at all. Each of those was a separate door into the owner's real
    # projects folder, and the suite could only shut them one test at a time.
    #
    # `core.platform_paths.default_output_root()` is now the single definition
    # of that fallback, and `CHROMIQ_OUTPUT_ROOT` moves it. One line, all
    # nineteen, whatever kind of settings object a test happens to hold.
    #
    # A test that genuinely needs the real default asks for the
    # `the_real_default_output_root` fixture, which unsets it for that test
    # only. Nothing else should.
    os.environ.setdefault(
        "CHROMIQ_OUTPUT_ROOT", str(sandbox / "projects"))

    # …AND THE WORKING FOLDER ITSELF, which the QSettings sandbox alone does NOT
    # cover and which is the mechanism that has actually cost data.
    #
    # `custom_output_path` defaults to "", and "" means `~/ChromIQ` — the
    # developer's real projects. A sandboxed ini that has never had the key
    # written still answers "", so every test that builds anything without
    # setting it by hand lands there. Measured on 2026-08-28, with a recursive
    # guard in place: one gate run rewrote a whole run of the owner's
    # "Red River Paper … Letter 2052p 9pages" project — twenty TIFFs, the .ti1,
    # the .ti2, the exports — because a built-in preset's default name happens
    # to equal that project's folder name, and re-provisioned his
    # scanner-test-targets. It had been doing that on every run.
    #
    # Seeding the key here makes the real folder unreachable BY DEFAULT rather
    # than by each test remembering. A test that wants a different root still
    # just sets it.
    # THE DEFAULT ITSELF, not just this ini. Overriding QSettings alone is not
    # enough and never was: dozens of test files build their own
    # `AppSettings()` and then replace `._qs` with a fresh empty ini of their
    # own, and a dozen more use small hand-written doubles seeded from
    # `DEFAULTS`. In every one of those `custom_output_path` answers "", and ""
    # IS `~/ChromIQ`. Moving the DEFAULT makes the real folder unreachable for
    # all of them at once; a test that wants a specific root still just sets it.
    _cs.DEFAULTS["custom_output_path"] = str(sandbox / "projects")
    QSettings(str(ini), QSettings.Format.IniFormat).setValue(
        "custom_output_path", str(sandbox / "projects"))

    def _sandboxed(*_args, **_kwargs):
        return QSettings(str(ini), QSettings.Format.IniFormat)

    _cs.QSettings = _sandboxed
    config._chromiq_settings_sandbox = str(sandbox)

    # …AND THE TRASH. Deleting moves files to the system recycle folder now, so
    # a gate run dropped about fifty items into the developer's own Trash and
    # left them there — which is not merely untidy: it buries whatever was
    # genuinely in there under test litter with names like `run1` and
    # `meta.json`, and someone emptying it by hand can lose their own work by
    # mistake. Measured on 2026-08-28, and it had already happened once.
    #
    # The tests still exercise the real code path; only the destination moves.
    import core.trash as _ct
    _trash = sandbox / "trash"
    _trash.mkdir(parents=True, exist_ok=True)
    _real_move = _ct.move_to_trash

    def _sandboxed_trash(path):
        import shutil
        src = pathlib.Path(path)
        if not src.exists():
            return _ct.TrashResult(True)
        dest = _trash / f"{src.name}-{abs(hash(str(src))) % 10**8}"
        try:
            shutil.move(str(src), str(dest))
        except OSError as exc:
            return _ct.TrashResult(False, reason=str(exc))
        return _ct.TrashResult(True, dest)

    _ct.move_to_trash = _sandboxed_trash
    # Kept reachable so a test ABOUT the Trash can still exercise the real one.
    _ct.real_move_to_trash = _real_move
    config._chromiq_real_move_to_trash = _real_move


def pytest_addoption(parser):
    parser.addoption("--runslow", action="store_true", default=False,
                     help="also run the slow end-to-end build tests")
    parser.addoption("--allow-missing-helper", action="store_true",
                     default=False,
                     help="let a --runslow run continue without the "
                          "chromiq-chartread helper. The run then proves "
                          "nothing about the chart-reading engine.")


# ---------------------------------------------------------------------------
# WHAT A RUN CAN AND CANNOT PROVE - SAID AT THE TOP, EVERY TIME
# ---------------------------------------------------------------------------
# The gate header named the platform, PyQt, the plugins and the worker count,
# and said nothing about the two things that decide how much of the suite
# actually ran. Both had already cost a wrong claim in writing:
#
# * `tests/test_chartread_engine.py` and seven other files carry a MODULE-LEVEL
#   `skipif` on a GITIGNORED build artefact, and an eighth skips part of itself
#   on the same thing. Absent, 85 tests skip. A worktree,
#   a fresh clone and any CI runner are the normal case for that artefact, and
#   the only trace in the log is the total - so "the helper was present so
#   nothing was silently skipped" was an inference from a remembered number,
#   not something the run had said. Measured 2026-09-03 in a worktree of the
#   same commit: 9,867 passed / 227 skipped, against 9,952 / 142 on the machine
#   that had the helper. Same tree, 85 fewer tests, nothing said.
#
# * At least fourteen files skip on BUILD SHAPE - "no engine panel in this
#   build", "this build has no row-indicator checkbox". Those turn a REMOVAL
#   into a pass, which is the one thing a suite must never do quietly.
#
# So the header states the capability facts up front, and the census at the end
# groups every skip the run actually took by reason. Anything the census cannot
# place is reported as UNCATEGORISED rather than folded into a bucket, so the
# categorisation cannot rot without saying so.

def _helper_path() -> "pathlib.Path | None":
    """Where the chart-reading helper is, through the app's own search order."""
    sys.path.insert(0, str(pathlib.Path(__file__).parent / "helpers"))
    try:
        from replay_tools import HELPER
    except Exception:                      # noqa: BLE001
        return None
    return HELPER if HELPER and HELPER.exists() else None


#: Reason-text patterns, most specific first. `None` marks the bucket a reason
#: has to be placed in by hand; everything unmatched is reported as
#: UNCATEGORISED so this table cannot silently go stale.
_SKIP_BUCKETS: tuple = (
    ("BUILD SHAPE - a removed feature would pass as a skip", (
        "in this build", "this build", "not available in this build",
        "no engine panel", "no layout panel", "no manual printtarg widgets",
        "no row-indicator checkbox", "no free-text row", "panel shape",
        "not shown in this state", "does not open the dialog itself",
        "no target controller", "no picker for this target type",
        "toggle not present", "could not resolve run1",
    )),
    ("the helper is not built", (
        "chromiq-chartread helper not built", "bundled helper not present",
        "helper source not in this checkout", "no pinned helper source line",
    )),
    # BEFORE the Argyll bucket, and this order was earned. The census's first
    # real run reported 121 of its 155 skips as "ArgyllCMS is not installed
    # here" - on a machine where Argyll IS installed - because
    # "engine-built preset - printtarg not used" contains the word `printtarg`.
    # It is not a missing tool, it is a parametrised case that does not apply,
    # and it is the single largest reason in the whole run. The census caught
    # its own mislabelling the first time it was looked at, which is the
    # argument for printing it at all.
    ("the case does not arise for this input", (
        "engine-built preset", "the list fits", "does not fit this page",
        "nothing to scroll", "not translated in this catalogue",
        "no recorded count",
    )),
    ("ArgyllCMS is not installed here", (
        "argyll", "targen", "printtarg", "colprof", "scanin", "colverify",
        "ref/",
    )),
    ("the platform cannot show it", (
        "offscreen", "windows", "macos", "symlink", "case-insensitive",
        "webengine", "freetype", "font", "no print queue", "hdiutil",
    )),
    ("a data file is not on this machine", (
        "not available (see module docstring)", "fixture missing",
        "not present on this machine", "not on this machine",
        "example not present", "example incomplete", "not present",
        "not in ref/", "not found under",
    )),
    ("the slow tier was not asked for", ("use --runslow",)),
)


def _skip_bucket(reason: str) -> str:
    low = (reason or "").lower()
    for name, needles in _SKIP_BUCKETS:
        for n in needles:
            if n in low:
                return name
    return "UNCATEGORISED - nobody has said what this one means"


def _skip_census(terminalreporter, config) -> None:
    """Every skip this run took, grouped by what it means.

    A number on its own ("142 skipped") is the thing that let a removal hide:
    it is the same number whether the suite chose not to test something or
    could not find the feature to test. Grouping says which.
    """
    # `getattr`, because tests build reporter doubles: the census is a
    # courtesy and must never be the reason a summary hook explodes.
    reports = (getattr(terminalreporter, "stats", None) or {}).get(
        "skipped", [])
    if not reports:
        return
    buckets: dict = {}
    for rep in reports:
        reason = ""
        lr = getattr(rep, "longrepr", None)
        if isinstance(lr, tuple) and len(lr) == 3:
            reason = str(lr[2])
        reason = reason.replace("Skipped: ", "").strip()
        where = ""
        if isinstance(lr, tuple) and len(lr) == 3:
            where = str(lr[0])
        buckets.setdefault(_skip_bucket(reason), []).append((reason, where))

    w = terminalreporter
    total = sum(len(v) for v in buckets.values())
    w.write_sep("=", f"WHAT THIS RUN DID NOT TEST - {total} skips", bold=True)
    shape = next((k for k in buckets if k.startswith("BUILD SHAPE")), None)
    unknown = next((k for k in buckets if k.startswith("UNCATEGORISED")), None)
    order = sorted(buckets, key=lambda k: (k is not shape, k is not unknown,
                                           -len(buckets[k])))
    for name in order:
        rows = buckets[name]
        loud = name is shape or name is unknown
        w.write_line(f"  {len(rows):4d}  {name}", red=loud, bold=loud)
        seen: dict = {}
        for reason, where in rows:
            seen[reason] = seen.get(reason, 0) + 1
        for reason, n in sorted(seen.items(), key=lambda kv: -kv[1])[:8]:
            w.write_line(f"          {n:3d} x {reason[:96]}")
        if len(seen) > 8:
            w.write_line(f"          … and {len(seen) - 8} more distinct "
                         f"reasons")
    if shape:
        w.write_line("")
        w.write_line("  A BUILD-SHAPE skip asks whether a widget is there and "
                     "steps aside when it is not,", red=True)
        w.write_line("  so deleting the feature turns its test green. Those "
                     f"{len(buckets[shape])} are not evidence of anything.",
                     red=True)
    if unknown:
        w.write_line("")
        w.write_line("  An UNCATEGORISED skip is one nobody has classified. "
                     "Add it to _SKIP_BUCKETS", red=True)
        w.write_line("  in tests/conftest.py, or fix the test.", red=True)
    w.write_line("")


def pytest_report_header(config):
    helper = _helper_path()
    gate = bool(config.getoption("--runslow"))
    out = ["", "what this run can and cannot prove:"]
    if helper is not None:
        out.append(f"  chart-reading engine: helper PRESENT at {helper}")
    else:
        out.append("  chart-reading engine: helper ABSENT - 8 files SKIP "
                   "WHOLESALE and 1 more skips in")
        out.append("      part (85 tests when this was last measured, "
                   "2026-09-03), and a chart-reading")
        out.append("      engine deleted outright would still pass. The "
                   "census at the end of this run")
        out.append("      says how many it actually was.")
        out.append("      Build it: cmake -S native/chartread_helper "
                   "-B native/chartread_helper/build && \\")
        out.append("                cmake --build native/chartread_helper/build")
    out.append(f"  tier: {'--runslow (THE RELEASE GATE)' if gate else 'everyday (the slow tier is skipped, this is NOT a gate)'}")
    out.append(f"  output root: {os.environ.get('CHROMIQ_OUTPUT_ROOT', 'NOT SANDBOXED - the real ~/ChromIQ')}")
    out.append("  a census of every skip this run took, grouped by reason, "
               "is printed at the end.")
    return out


def _say_it_even_when_quiet(session):
    """…and say it under `-q` too, which is how the gate is actually run.

    `pytest_report_header` is the canonical place and pytest DISCARDS it at
    `-q`: the hook is called and nothing is printed. The 41 gate logs on the
    Desktop were all run at normal verbosity and so WOULD have shown it - that
    much I checked rather than assumed - but `-q` is an ordinary way to drive
    this suite and is how every run in this task was driven. A header that
    disappears depending on a flag is not a header anyone can rely on.

    It also has to fire under xdist, and that is why this hangs off
    `pytest_sessionstart` rather than `pytest_collection_finish` - the first
    version used the latter, printed perfectly at `-n0`, and printed NOTHING in
    the `-n auto` gate, because the xdist controller does not run that hook.
    Which is the same failure as the one this whole file is about: a check that
    is absent exactly where it was needed, and looks fine everywhere else.

    Controller only: a worker has no `terminalreporter` plugin, so `get_plugin`
    answers None there and this is not printed twelve times over.
    """
    tr = session.config.pluginmanager.get_plugin("terminalreporter")
    if tr is None or getattr(tr, "verbosity", 0) >= 0:
        return                       # the header hook has already shown it
    for line in pytest_report_header(session.config):
        tr.write_line(line)


def _enforce_the_helper(config):
    """A release gate that quietly drops 85 tests is not a gate.

    Judgement, and it is a judgement: a plain `pytest` stays GREEN without the
    helper, because a fresh clone and a CI runner are the normal case for a
    gitignored build artefact and a hard failure there would only teach people
    to delete the check. `--runslow` is different - CLAUDE.md defines it as the
    thing a merge or release decision rests on, no CI runs it, and the helper
    is now resolved through the app's own search order, so on a healthy tree it
    is found even when nothing has been built. Missing it therefore means the
    tree is broken, not that the machine is ordinary.

    `--allow-missing-helper` still lets a gate run finish, loudly.
    """
    if not config.getoption("--runslow"):
        return
    if _helper_path() is not None:
        return
    if config.getoption("--allow-missing-helper"):
        return
    raise pytest.UsageError(
        "--runslow is the release gate, and the chromiq-chartread helper is "
        "not here.\n"
        "Eight files would skip WHOLESALE in silence and one more in part "
        "(85 tests when\n"
        "this was last measured), and a chart-reading engine deleted outright "
        "would pass.\n"
        "Build it:\n"
        "    cmake -S native/chartread_helper -B native/chartread_helper/build\n"
        "    cmake --build native/chartread_helper/build\n"
        "or pass --allow-missing-helper to run the gate knowing it cannot "
        "prove that part."
    )


def pytest_collection_modifyitems(config, items):
    if config.getoption("--runslow"):
        return
    skip = pytest.mark.skip(reason="slow end-to-end build — use --runslow")
    for item in items:
        if "slow" in item.keywords:
            item.add_marker(skip)

# ---------------------------------------------------------------------------
# Demo projects: built once, then CACHED ON DISK across workers and runs.
# ---------------------------------------------------------------------------
def _demo_cache_key() -> str:
    """What the built projects actually depend on.

    Two things decide whether a cached tree is still the right answer: the
    generator that produced it, and the ArgyllCMS that did the work. Anything
    else changing (a test, the app) does not alter these files, so the cache
    survives it — which is the whole point.
    """
    import hashlib

    h = hashlib.sha256()
    h.update(_DEMO_GENERATOR.read_bytes())
    # The Argyll binaries: identity by size + mtime, so an upgrade invalidates
    # the cache rather than silently testing yesterday's output.
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    try:
        from make_demo_projects import _argyll
        for tool in ("targen", "colprof", "printtarg", "fakeread"):
            try:
                st = Path(_argyll(tool)).stat()
                h.update(f"{tool}:{st.st_size}:{int(st.st_mtime)}".encode())
            except Exception:            # noqa: BLE001 — a missing tool is
                h.update(f"{tool}:missing".encode())   # itself part of the key
    except Exception:                    # noqa: BLE001
        h.update(b"argyll-unresolvable")
    return h.hexdigest()[:16]


#: Where the cache lives. Beside the repo rather than in it, so it is never
#: committed and never confuses a `git status` before a release.
_DEMO_GENERATOR = Path(__file__).resolve().parents[1] / "scripts" / "make_demo_projects.py"
_DEMO_CACHE_HOME = Path(
    os.environ.get("CHROMIQ_DEMO_CACHE",
                   Path(tempfile.gettempdir()) / "chromiq-demo-projects-cache"))


def _build_demo_projects(into: Path) -> None:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    from make_demo_projects import (build_full, build_legacy_v1,
                                    build_legacy_v2, build_verify_history)
    for build in (build_full, build_verify_history,
                  build_legacy_v1, build_legacy_v2):
        build(into)


def _publish_demo_cache(staging: Path, cached: Path, ready: Path) -> bool:
    """Move a finished build onto the key path. True if the cache is usable after.

    ``os.replace`` **cannot replace an existing directory on Windows** — it
    raises ``PermissionError`` (WinError 5), where POSIX simply swaps the two.
    Reading that as "another worker got there first" is right only when what
    already sits there is COMPLETE. When it is not, the old code deleted its own
    good build and left the marker-less tree in place, so the next run repeated
    the entire four-minute build — and so did the run after that.

    Measured on the Windows gate before this fix: *every* cache entry ever
    written on that machine was marker-less, the demo projects were rebuilt on
    two xdist workers on every single run, and the gate cost 22 minutes instead
    of four. macOS never saw it, because there the replace succeeds and the
    cache repairs itself on the next run.

    So the two cases are separated. A complete tree already there wins — ours is
    thrown away. A marker-less one is moved aside under a **unique** name and
    the replace retried; unique because two workers can be doing this at the
    same moment, and rmtree-then-replace leaves a window in which a third finds
    no tree at all.
    """
    for attempt in range(3):
        try:
            os.replace(staging, cached)
            return True
        except OSError:
            if ready.is_file():
                # A complete tree beat us to it — theirs is as good as ours.
                shutil.rmtree(staging, ignore_errors=True)
                return True
            # A marker-less tree is squatting on the key path.
            aside = cached.with_name(f"{cached.name}.stale-{os.getpid()}-{attempt}")
            try:
                os.replace(cached, aside)
            except OSError:
                pass          # another worker is clearing it; look again
            else:
                shutil.rmtree(aside, ignore_errors=True)
    shutil.rmtree(staging, ignore_errors=True)
    return ready.is_file()


@pytest.fixture(scope="session")
def demo_projects_root(tmp_path_factory):
    """Every demo project, built once and then reused.

    Each builder shells out to real ArgyllCMS (targen, colprof) and costs
    30-70 seconds; the four together are around **four minutes**, and that
    setup is the single longest thing in the whole suite.

    "Session-scoped" is not enough on its own. Under ``pytest-xdist`` a session
    is **per worker process**, so every worker that touches this fixture built
    its own copy: with ``--dist loadfile`` and two files needing it, the gate
    paid for the same four minutes twice, in parallel, and could never finish
    faster than one of them. Measured on the beta.141 tree:

        234.26s setup  tests/test_report_readable_on_dark.py
        229.38s setup  tests/test_legacy_migration.py
         89.99s call   <the next slowest thing in the entire suite>

    So the tree is cached on disk instead, keyed by the generator and the
    ArgyllCMS that built it (see :func:`_demo_cache_key`). The first run after
    either changes pays the four minutes; every run after that starts with the
    projects already there. Delete the folder, or point ``CHROMIQ_DEMO_CACHE``
    somewhere else, to force a rebuild.

    Tests must still COPY what they use: ``Project.load`` migrates in place, so
    a shared tree would let one test's migration change what the next one sees.
    That is also why the cache is only ever READ from — every consumer copies.
    """
    cached = _DEMO_CACHE_HOME / _demo_cache_key()
    ready = cached / ".complete"
    if ready.is_file():
        return cached

    # Build into a private folder and move it into place atomically, so a
    # half-built tree can never be picked up — by another worker racing us, or
    # by a later run after this one was interrupted.
    cached.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix="demo-build-", dir=str(cached.parent)))
    try:
        _build_demo_projects(staging)
        (staging / ".complete").write_text(_demo_cache_key(), encoding="utf-8")
        _publish_demo_cache(staging, cached, ready)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    if ready.is_file():
        return cached
    # Cache unusable for some reason: fall back to a throwaway build rather
    # than failing the suite over an optimisation.
    root = tmp_path_factory.mktemp("demo-projects")
    _build_demo_projects(root)
    return root


@pytest.fixture
def demo_project(demo_projects_root, tmp_path):
    """Give this test its own copy of a demo project, by name."""
    import shutil

    def _copy(name: str) -> Path:
        dst = tmp_path / name
        if not dst.exists():
            shutil.copytree(demo_projects_root / name, dst)
        return dst

    return _copy


# ---- #137 calibration run type -------------------------------------------
# Imported so every calibration test file gets them without repeating the
# temp-folder isolation, which is the one thing they must not get wrong.
from tests.conftest_calibration import (      # noqa: E402,F401
    CalSettings, cal_home, cal_settings, cal_project)
