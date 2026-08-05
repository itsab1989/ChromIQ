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
    os.utime(path, (when, when))
    return path


@pytest.fixture
def fake_temp(tmp_path, monkeypatch):
    """Point the sweeper at a temp folder of our own, never the real one."""
    monkeypatch.setattr("tempfile.gettempdir", lambda: str(tmp_path))
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
