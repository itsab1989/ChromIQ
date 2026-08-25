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
    """Create the QApplication once and keep it alive for the whole session."""
    global _PINNED_QAPP
    from PyQt6.QtWidgets import QApplication

    _PINNED_QAPP = QApplication.instance() or QApplication([])
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


def _real_chromiq_entries() -> set:
    try:
        return {p.name for p in _REAL_CHROMIQ.iterdir()}
    except OSError:
        return set()


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


@pytest.fixture(autouse=True)
def _never_touch_the_real_chromiq_folder():
    """Fail a test that creates anything in the user's real ~/ChromIQ.

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
    before = _real_chromiq_entries()
    yield
    new = sorted(_real_chromiq_entries() - before)
    assert not new, (
        "this test wrote into the real ~/ChromIQ folder: "
        f"{new}\n"
        "Point the settings at tmp_path — overriding QSettings alone leaves "
        "custom_output_path at its default, which IS ~/ChromIQ:\n"
        '    s.set("custom_output_path", str(tmp_path / "out"))\n'
        "Nothing has been deleted; remove the stray folder(s) by hand if you "
        "want them gone."
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

    from PyQt6.QtCore import QSettings

    import core.settings as _cs

    sandbox = pathlib.Path(tempfile.mkdtemp(prefix="chromiq-settings-"))
    ini = sandbox / "ChromIQ.ini"

    def _sandboxed(*_args, **_kwargs):
        return QSettings(str(ini), QSettings.Format.IniFormat)

    _cs.QSettings = _sandboxed
    config._chromiq_settings_sandbox = str(sandbox)


def pytest_addoption(parser):
    parser.addoption("--runslow", action="store_true", default=False,
                     help="also run the slow end-to-end build tests")


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
        (staging / ".complete").write_text(_demo_cache_key())
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
