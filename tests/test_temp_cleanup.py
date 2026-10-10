"""The suite cleans up after itself — on this machine and on Windows.

Basti, 2026-08-05, after 5.0 GB of leftovers were found: *"can you modify the
tests in a way that they clean the created files up when done (either
successful or failed) and that they also check and clean the files from older
runs so the disk space is freed again?"* — and then: *"i would like to run the
tests on my windows vm again and they should clean up those files there as
well."*

This is deliberately thorough for its size, because the code under test
**deletes folders**. A sweeper that is slightly wrong is worse than no sweeper.
"""
from __future__ import annotations

import os
import time
from pathlib import Path

import pytest

from tests.conftest import (_KEEP_FOREVER, _STALE_AFTER_HOURS,
                            _sweep_stale_temp_dirs)


def _aged(path: Path, hours: float) -> Path:
    """Make a folder look *hours* old, portably (os.utime works on Windows)."""
    path.mkdir(parents=True, exist_ok=True)
    (path / "a-file.txt").write_text("x" * 100, encoding="utf-8")
    when = time.time() - hours * 3600
    # Everything inside too, deepest first: since review D the sweep keeps a
    # folder with ANYTHING in it changed in the last half hour.
    for p in sorted(path.rglob("*"), key=lambda q: len(q.parts), reverse=True):
        os.utime(p, (when, when), follow_symlinks=False)
    os.utime(path, (when, when))
    return path


@pytest.fixture
def fake_temp(tmp_path, monkeypatch):
    """Point the sweeper at a temp folder of our own, never the real one."""
    monkeypatch.setattr("tempfile.gettempdir", lambda: str(tmp_path))
    # Since dsk2 (6e6014aa) the sweep takes the SYSTEM temp folder from
    # `_REAL_TEMP`, not gettempdir (which now names this run's own folder).
    # Patching only gettempdir pointed these tests at the real temp folder:
    # six red in the review gate, and a sweep of the real one (T_review_beta2).
    import tests.conftest as _cf
    monkeypatch.setattr(_cf, "_REAL_TEMP", tmp_path)
    return tmp_path


def test_it_removes_what_an_earlier_run_left(fake_temp):
    old = _aged(fake_temp / "chromiq-test-out-abc123", _STALE_AFTER_HOURS + 1)
    folders, freed = _sweep_stale_temp_dirs()
    assert not old.exists()
    assert folders == 1
    assert freed >= 100


def test_it_leaves_a_run_that_is_still_going(fake_temp):
    """The threshold is what makes this safe under xdist: four workers share a
    temp folder, and deleting a live worker's tree would fail the run."""
    fresh = _aged(fake_temp / "chromiq-test-out-live", 0)
    folders, _ = _sweep_stale_temp_dirs()
    assert fresh.exists(), "a folder from a run in progress was deleted"
    assert folders == 0


def test_it_never_removes_the_demo_project_cache(fake_temp):
    """Rebuilding it costs about four minutes per gate — the whole reason it
    exists. Aged well past the threshold on purpose."""
    cache = _aged(fake_temp / _KEEP_FOREVER[0], _STALE_AFTER_HOURS * 100)
    _sweep_stale_temp_dirs()
    assert cache.exists()


def test_it_honours_a_relocated_cache(fake_temp, monkeypatch):
    """CHROMIQ_DEMO_CACHE moves the cache; the sweeper must follow it there."""
    monkeypatch.setenv("CHROMIQ_DEMO_CACHE",
                       str(fake_temp / "chromiq-somewhere-else"))
    moved = _aged(fake_temp / "chromiq-somewhere-else", _STALE_AFTER_HOURS * 100)
    _sweep_stale_temp_dirs()
    assert moved.exists()


def test_it_ignores_folders_that_are_not_ours(fake_temp):
    """Someone else's temp folder is not the suite's to delete."""
    theirs = _aged(fake_temp / "some-other-tool-cache", _STALE_AFTER_HOURS + 1)
    _sweep_stale_temp_dirs()
    assert theirs.exists()


def test_it_matches_both_naming_styles(fake_temp):
    """The suite has produced both ``chromiq-test-out-*`` and
    ``chromiq_130_drive_*``. Missing one of them was half the leak."""
    dash = _aged(fake_temp / "chromiq-test-out-1", _STALE_AFTER_HOURS + 1)
    under = _aged(fake_temp / "chromiq_130_drive_1", _STALE_AFTER_HOURS + 1)
    _sweep_stale_temp_dirs()
    assert not dash.exists() and not under.exists()


def test_a_file_is_not_mistaken_for_a_folder(fake_temp):
    stray = fake_temp / "chromiq-not-a-folder.txt"
    stray.write_text("x", encoding="utf-8")
    os.utime(stray, (time.time() - _STALE_AFTER_HOURS * 3600 * 2,) * 2)
    _sweep_stale_temp_dirs()
    assert stray.exists(), "a plain file was swept as if it were a run's folder"


def test_an_undeletable_folder_does_not_stop_the_sweep(fake_temp, monkeypatch):
    """Windows will not delete a folder whose files are open, and a locked one
    must not abort the sweep — the next run tries again."""
    import shutil

    locked = _aged(fake_temp / "chromiq-locked", _STALE_AFTER_HOURS + 1)
    other = _aged(fake_temp / "chromiq-fine", _STALE_AFTER_HOURS + 1)
    real_rmtree = shutil.rmtree

    def refuse(path, **kw):
        if Path(path).name == "chromiq-locked":
            return                       # what Windows does with an open file
        real_rmtree(path, **kw)

    monkeypatch.setattr("shutil.rmtree", refuse)
    folders, _ = _sweep_stale_temp_dirs()
    assert locked.exists()
    assert not other.exists(), "one locked folder stopped the whole sweep"
    assert folders == 1, "a folder that survived was counted as removed"


def test_a_read_only_file_is_still_removed(fake_temp):
    """Windows refuses to delete a read-only file, and ignore_errors would
    simply leave it — reporting success while the disk stayed full. The error
    handler clears the bit and retries."""
    import stat

    folder = _aged(fake_temp / "chromiq-readonly", _STALE_AFTER_HOURS + 1)
    victim = folder / "a-file.txt"
    os.chmod(victim, stat.S_IREAD)
    try:
        _sweep_stale_temp_dirs()
        assert not folder.exists(), (
            "a folder with a read-only file in it survived the sweep"
        )
    finally:
        if victim.exists():
            os.chmod(victim, stat.S_IWRITE)


def test_the_sweep_reports_what_it_actually_freed(fake_temp):
    """The number printed at the start of a run has to be true, or it is worse
    than printing nothing."""
    # Write the contents BEFORE ageing the folder: adding a file updates the
    # folder's own mtime, which made it look like a run in progress and the
    # sweep — correctly — left it alone.
    folder = fake_temp / "chromiq-sized"
    folder.mkdir()
    (folder / "big.bin").write_bytes(b"x" * 5000)
    _aged(folder, _STALE_AFTER_HOURS + 1)
    folders, freed = _sweep_stale_temp_dirs()
    assert folders == 1
    assert 5100 <= freed < 6000, f"reported {freed} bytes freed"


# ---- pytest's own trees, which it fails to prune after a crash -----------
def test_it_removes_stale_pytest_trees(fake_temp):
    """pytest keeps the last few numbered trees — but skips any whose .lock is
    still present, and a crashed run leaves its lock behind. That is how a
    1.0 GB tree from three days earlier was still on disk."""
    base = fake_temp / "pytest-of-someone"
    old = _aged(base / "pytest-996", _STALE_AFTER_HOURS + 1)
    (base / "pytest-996" / ".lock").write_text("stale", encoding="utf-8")
    _aged(base / "pytest-996", _STALE_AFTER_HOURS + 1)   # re-age after writing
    folders, _ = _sweep_stale_temp_dirs()
    assert not old.exists()
    assert folders == 1


def test_it_leaves_the_pytest_tree_of_a_run_in_progress(fake_temp):
    base = fake_temp / "pytest-of-someone"
    live = _aged(base / "pytest-1349", 0)
    _sweep_stale_temp_dirs()
    assert live.exists(), "the running gate's own tree was deleted"


def test_it_never_touches_pytest_current(fake_temp):
    """A symlink pytest keeps pointing at the newest run."""
    import os

    base = fake_temp / "pytest-of-someone"
    target = _aged(base / "pytest-1349", 0)
    link = base / "pytest-current"
    try:
        os.symlink(target, link)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks unavailable (Windows without developer mode)")
    _sweep_stale_temp_dirs()
    assert link.exists()


# ---- the run cleans up after ITSELF, which beats guessing from age --------
@pytest.fixture(autouse=True)
def _keep_this_run_s_temp(monkeypatch):
    """The tests below call the REAL ``pytest_sessionfinish``, which since dsk2
    (6e6014aa) also removes this run's ``chromiq-run-*`` folder when called
    with 0 in the process that owns it. Under xdist that is never a worker, so
    the gate stayed green; in a serial run (``-n 0``) it deleted the folder the
    run was still using, and the next test's ``tmp_path`` was gone
    (T_review_beta2)."""
    import tests.conftest as _cf
    monkeypatch.setattr(_cf, "_leave_the_run_temp", lambda passed: None)


def test_the_session_hook_removes_a_passing_run_s_tree(tmp_path, capsys):
    """A green run must leave nothing behind. Driven through the real hook."""
    from tests.conftest import pytest_sessionfinish

    base = tmp_path / "pytest-99"
    (base / "somewhere").mkdir(parents=True)
    (base / "somewhere" / "f.txt").write_text("x" * 1000, encoding="utf-8")

    class _Factory:
        def getbasetemp(self):
            return base

    class _Config:
        _tmp_path_factory = _Factory()

    class _Session:
        config = _Config()

    pytest_sessionfinish(_Session(), 0)
    assert not base.exists()


def test_a_failing_run_keeps_its_files_and_says_where(tmp_path, capsys):
    """That tree IS the evidence — the chart that came out wrong, the .ti3 that
    would not parse. Deleting it would throw away the only copy."""
    from tests.conftest import pytest_sessionfinish

    base = tmp_path / "pytest-98"
    base.mkdir(parents=True)
    (base / "evidence.txt").write_text("what went wrong", encoding="utf-8")

    class _Factory:
        def getbasetemp(self):
            return base

    class _Config:
        _tmp_path_factory = _Factory()

    class _Session:
        config = _Config()

    pytest_sessionfinish(_Session(), 1)
    assert base.exists()
    assert (base / "evidence.txt").exists()
    assert str(base) in capsys.readouterr().out


def test_a_worker_never_deletes_the_shared_tree(tmp_path):
    """Under xdist the workers share one tree; a worker removing it while the
    others are still writing would fail the run."""
    from tests.conftest import pytest_sessionfinish

    base = tmp_path / "pytest-97"
    base.mkdir(parents=True)

    class _Factory:
        def getbasetemp(self):
            return base

    class _Config:
        _tmp_path_factory = _Factory()
        workerinput = {"workerid": "gw2"}    # this makes it a worker

    class _Session:
        config = _Config()

    pytest_sessionfinish(_Session(), 0)
    assert base.exists()


# ---- another session's RUNNING test folder is never swept (review D) ------
# Builder D, 2026-10-07: a start-up sweep deleted a 3.27 GB chromiq-run-*
# folder during a run. The folder's own date moves only when something is
# added directly inside it, so a run writing deep inside for an hour looked
# stale. The sweep now keeps anything in use: changed anywhere inside in the
# last half hour, held open by a live process, or named after a live pytest.
def test_a_folder_written_deep_inside_is_kept(fake_temp):
    run = _aged(fake_temp / "chromiq-run-busy", _STALE_AFTER_HOURS + 2)
    deep = run / "tmpabc" / "chart"
    deep.mkdir(parents=True)
    (deep / "page_01.tif").write_bytes(b"x" * 10)
    old = time.time() - (_STALE_AFTER_HOURS + 2) * 3600
    os.utime(run, (old, old))                # its own date says: stale
    folders, _ = _sweep_stale_temp_dirs()
    assert run.exists() and (deep / "page_01.tif").exists()
    assert folders == 0


def test_a_folder_quiet_for_less_than_half_an_hour_is_kept(fake_temp):
    import tests.conftest as cf
    run = _aged(fake_temp / "chromiq-run-quiet", _STALE_AFTER_HOURS + 2)
    recent = time.time() - (cf._IN_USE_FOR_S - 120)
    os.utime(run / "a-file.txt", (recent, recent))
    _sweep_stale_temp_dirs()
    assert run.exists()


def test_a_folder_held_open_by_a_live_process_is_kept(fake_temp):
    import subprocess
    import sys
    run = _aged(fake_temp / "chromiq-run-held", _STALE_AFTER_HOURS + 2)
    if sys.platform == "win32":
        pytest.skip("lsof is the check; Windows refuses the delete itself")
    held = run / "a-file.txt"
    child = subprocess.Popen(
        [sys.executable, "-c",
         "import sys,time; f=open(sys.argv[1], encoding='utf-8'); "
         "print('ok', flush=True); "
         "time.sleep(60)", str(held)],
        stdout=subprocess.PIPE, text=True, encoding="utf-8")
    try:
        assert child.stdout.readline().strip() == "ok"
        old = time.time() - (_STALE_AFTER_HOURS + 2) * 3600
        os.utime(held, (old, old))
        os.utime(run, (old, old))
        import tests.conftest as cf
        if not any(p.endswith("/chromiq-run-held/a-file.txt")
                   for p in cf._held_open_paths()):
            pytest.skip("lsof is unavailable here")
        _sweep_stale_temp_dirs()
        assert run.exists(), "a folder a live process holds open was deleted"
    finally:
        child.kill()
        child.wait(timeout=30)
    _sweep_stale_temp_dirs()
    assert not run.exists(), "once nobody holds it, the stale folder goes"


def test_a_run_folder_of_a_live_pytest_is_kept_and_of_a_dead_one_goes(
        fake_temp):
    import subprocess
    import sys
    parent = os.getppid() or 1               # alive, and not this process
    live = _aged(fake_temp / f"chromiq-run-{parent}-abcd", _STALE_AFTER_HOURS + 2)
    gone = subprocess.Popen([sys.executable, "-c", "pass"])
    gone.wait(timeout=30)
    dead = _aged(fake_temp / f"chromiq-run-{gone.pid}-efgh",
                 _STALE_AFTER_HOURS + 2)
    _sweep_stale_temp_dirs()
    assert live.exists(), "the folder of a pytest still running was deleted"
    assert not dead.exists()


def test_this_run_s_folder_names_its_controller():
    import tempfile
    import tests.conftest as cf
    name = Path(tempfile.gettempdir()).name
    m = cf._RUN_TMP_PID.match(name)
    assert m, name
    owner = os.environ.get("CHROMIQ_SUITE_RUN_TMP_OWNER")
    assert m.group(1) == owner


# A file dated in the FUTURE is not a change. One test dates a report in 2096
# to stand for "changed later"; every red or killed run holding it then looked
# "changed 0 min ago" for ever, and 34 run folders (45 GB) were never swept
# (2026-10-10).
def test_a_file_dated_in_the_future_does_not_keep_a_dead_run(fake_temp):
    run = _aged(fake_temp / "chromiq-run-99999999-future", _STALE_AFTER_HOURS + 2)
    deep = run / "pytest-of-x" / "report.json"
    deep.parent.mkdir(parents=True)
    deep.write_text("{}", encoding="utf-8")
    future = time.time() + 70 * 365 * 86400
    os.utime(deep, (future, future))
    old = time.time() - (_STALE_AFTER_HOURS + 2) * 3600
    os.utime(deep.parent, (old, old))
    os.utime(run, (old, old))
    folders, _ = _sweep_stale_temp_dirs()
    assert not run.exists()
    assert folders == 1


def test_a_file_dated_an_hour_ahead_still_keeps_its_folder(fake_temp):
    """The other side of the rule above (review of beta 18): a clock put back
    dates recent work in the future, and that work is still in use. Only a
    date more than a day ahead is ignored."""
    from tests.conftest import _FUTURE_SLACK_S
    assert _FUTURE_SLACK_S >= 3600
    run = _aged(fake_temp / "chromiq-run-99999999-clock", _STALE_AFTER_HOURS + 2)
    soon = time.time() + 3600
    os.utime(run / "a-file.txt", (soon, soon))
    folders, _ = _sweep_stale_temp_dirs()
    assert run.exists()
    assert folders == 0
