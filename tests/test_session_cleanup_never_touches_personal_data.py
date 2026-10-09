"""The end-of-session cleanup deletes only what our tooling created.

Basti, 2026-10-02: *"just make sure that does never delete any personal data -
only what you added in a session that is considered not needed"*.
scripts/session_cleanup.py runs from a SessionEnd hook, unattended, so its
guard (`is_ours`) is tested directly: every personal place is refused, every
place our tooling writes to is accepted, and `remove` refuses (and leaves in
place) anything the guard refuses, even if a bug put it on the list.
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
import session_cleanup as S  # noqa: E402

#: `scripts/session_cleanup.py` is the SessionEnd hook of Basti's Mac
#: (CLAUDE.md "DISK HYGIENE"): its roots and names are macOS ones, and it never
#: runs anywhere else.
pytestmark = pytest.mark.skipif(sys.platform != "darwin",
                                reason="a macOS-only dev tool (the Mac's session hook)")

HOME = Path.home()
TMP = Path(tempfile.gettempdir())

#: `os.utime` on Windows has no `follow_symlinks=False` (NotImplementedError);
#: these fixtures hold no symlink for it to matter, so it is only asked for
#: where the platform has it.
_NO_FOLLOW = ({"follow_symlinks": False}
              if os.utime in os.supports_follow_symlinks else {})


@pytest.mark.parametrize("path", [
    HOME / "Pictures" / "holiday.jpg",
    HOME / "ChromIQ" / "my-printer-project",
    HOME / "Desktop" / "ChromIQ-work" / "2026-10-01_session",
    HOME / "Documents",
    HOME / ".Trash" / "chromiq-something",
    REPO / "dist" / "ChromIQ-Demo-Projects_v4.3.0",
    REPO / "build",
    REPO / "assets",
    Path("/cores") / "core.123",
    TMP / "chromiq-demo-projects-cache",          # kept on purpose
    TMP / "com.adobe.something",                  # another app's temp
    TMP / "tmp1234abcd",                          # anonymous, could be anyone's
    TMP / "chromiq-x" / "nested",                 # only top-level folders of ours
    REPO / ".claude" / "worktrees" / "someone-elses",
    Path("/private/tmp") / "notours",
])
def test_personal_and_foreign_places_are_refused(path):
    assert not S.is_ours(path)


@pytest.mark.parametrize("path", [
    TMP / "chromiq-test-abc",
    TMP / "chromiq-settings-xyz",
    TMP / "chromiq_warmup_44100_1.wav",
    TMP / "pytest-of-Basti",
    Path("/private/tmp") / "chromiq-driver.ini",
    # the MAIN checkout's worktrees, also when the suite runs in a worktree
    S.main_checkout() / ".claude" / "worktrees" / "agent-a1b2c3",
])
def test_what_our_tooling_writes_is_accepted(path):
    assert S.is_ours(path)


def test_only_a_session_scratch_shaped_path_counts_as_scratch():
    assert S.is_ours(Path("/private/tmp/claude-502/-Users-Basti-develop-ChromIQ/abc-123"),
                     "this session's scratch")
    assert not S.is_ours(HOME / "Pictures", "this session's scratch")
    assert not S.is_ours(Path("/private/tmp/claude-502"), "this session's scratch")


def test_own_scratch_refuses_a_session_id_that_is_a_path():
    for bad in ("", "..", ".", "../x", "a/b"):
        assert S.own_scratch(bad) == []


def test_remove_refuses_and_leaves_a_personal_file(tmp_path, monkeypatch):
    personal = tmp_path / "MyProject" / "important.ti3"
    personal.parent.mkdir()
    personal.write_text("measurements", encoding="utf-8")
    assert S.remove(personal.parent, "$TMPDIR chromiq-* folders") is False
    assert personal.read_text(encoding="utf-8") == "measurements"


def test_the_checkout_it_runs_from_is_never_a_merged_worktree(monkeypatch):
    """Run inside an agent worktree, the worktree's own branch is always
    contained in HEAD; it was planned for removal from under itself. Every
    worktree is taken as clean here, so uncommitted work cannot hide it."""
    import subprocess
    real = subprocess.run

    def _run(cmd, *a, **k):
        if isinstance(cmd, list) and "status" in cmd and "--porcelain" in cmd:
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")
        return real(cmd, *a, **k)
    monkeypatch.setattr(S.subprocess, "run", _run)
    here = S.REPO.resolve()
    assert all(p.resolve() != here for p, _b in S.merged_worktrees())


def test_everything_planned_passes_the_guard():
    for why, path, _size in S.plan(""):
        assert S.is_ours(path, why), (why, path)


# ---- review K_review_beta1: worktrees ----------------------------------------

def _git(*args, cwd):
    import subprocess
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True,
                          encoding="utf-8", check=True)


@pytest.fixture
def repo_with_worktree(tmp_path, monkeypatch):
    """A throw-away repo with one merged agent worktree, made to look old."""
    import os
    import time
    repo = tmp_path / "repo"
    repo.mkdir()
    _git("init", "-q", "-b", "master", cwd=repo)
    _git("config", "user.email", "t@t", cwd=repo)
    _git("config", "user.name", "t", cwd=repo)
    (repo / ".gitignore").write_text("ignored/\n", encoding="utf-8")
    (repo / "a.txt").write_text("a", encoding="utf-8")
    _git("add", ".", cwd=repo)
    _git("commit", "-q", "-m", "a", cwd=repo)
    wt = repo / ".claude" / "worktrees" / "agent-x"
    _git("worktree", "add", "-q", "-b", "agent-x", str(wt), cwd=repo)
    old = time.time() - 7200
    for p in [wt, *wt.rglob("*")]:
        os.utime(p, (old, old), **_NO_FOLLOW)
    monkeypatch.setattr(S, "REPO", repo)
    return repo, wt


def _age(path):
    import os
    import time
    old = time.time() - 7200
    for p in [path, *path.rglob("*")]:
        os.utime(p, (old, old), **_NO_FOLLOW)


def test_a_clean_merged_old_worktree_is_offered(repo_with_worktree):
    _repo, wt = repo_with_worktree
    assert [p.name for p, _b in S.merged_worktrees()] == [wt.name]


def test_a_worktree_with_ignored_work_is_kept(repo_with_worktree):
    _repo, wt = repo_with_worktree
    (wt / "ignored").mkdir()
    (wt / "ignored" / "project.ti3").write_text("measurements", encoding="utf-8")
    _age(wt)
    assert S.merged_worktrees() == []


def test_caches_alone_do_not_keep_a_worktree(repo_with_worktree):
    _repo, wt = repo_with_worktree
    (wt / "__pycache__").mkdir()
    (wt / "__pycache__" / "a.cpython-314.pyc").write_bytes(b"x")
    _age(wt)
    assert [p.name for p, _b in S.merged_worktrees()] == [wt.name]


def test_a_locked_or_fresh_worktree_is_kept(repo_with_worktree):
    repo, wt = repo_with_worktree
    _git("worktree", "lock", str(wt), cwd=repo)
    assert S.merged_worktrees() == []
    _git("worktree", "unlock", str(wt), cwd=repo)
    (wt / "a.txt").write_text("touched", encoding="utf-8")   # fresh AND dirty
    assert S.merged_worktrees() == []


def test_a_worktree_touched_within_the_hour_is_kept_even_when_clean(repo_with_worktree):
    import os
    _repo, wt = repo_with_worktree
    os.utime(wt / "a.txt", None)            # in use right now, content unchanged
    assert S.merged_worktrees() == []


def test_a_worktree_never_plans_its_own_removal(tmp_path, monkeypatch):
    """Run from inside a clean worktree, HEAD is that worktree's own branch,
    so "contained in the current branch" was always true and the worktree
    planned to remove itself (found by the gate run in agent worktrees,
    2026-10-02, N_impl_inspect). Another merged worktree is still listed."""
    import subprocess
    me = tmp_path / ".claude" / "worktrees" / "agent-me"
    other = tmp_path / ".claude" / "worktrees" / "agent-other"
    for d in (me, other):
        d.mkdir(parents=True)
        _age(d)                 # old enough that only the self rule decides
    monkeypatch.setattr(S, "REPO", me)
    listing = (f"worktree {me}\nHEAD 1\nbranch refs/heads/mine\n\n"
               f"worktree {other}\nHEAD 2\nbranch refs/heads/theirs\n")

    def _git(*args):
        out = listing if args[:2] == ("worktree", "list") else ""
        return subprocess.CompletedProcess(args, 0, out, "")
    monkeypatch.setattr(S, "_git", _git)
    monkeypatch.setattr(S.subprocess, "run",
                        lambda *a, **k: subprocess.CompletedProcess(a, 0, "", ""))
    planned = [p for p, _b in S.merged_worktrees()]
    assert me not in planned
    assert other in planned


def test_a_dry_run_with_an_open_stdin_does_not_wait_for_it():
    """An agent's shell hands the script a stdin that is open and never ends.
    Reading it waited for ever, so the dry run looked hung (2026-10-04)."""
    import subprocess, sys
    from pathlib import Path
    script = Path(__file__).resolve().parents[1] / "scripts" / "session_cleanup.py"
    proc = subprocess.Popen([sys.executable, str(script), "--quiet"],
                            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, text=True,
                            encoding="utf-8")
    try:
        # Not communicate(): it closes stdin, which is exactly what an
        # agent's shell does not do. Keep it open and wait for the exit.
        rc = proc.wait(timeout=120)
    except subprocess.TimeoutExpired:
        proc.kill()
        raise AssertionError("the dry run waited on an open stdin")
    finally:
        proc.stdin.close()
    assert rc == 0 and "systemMessage" in proc.stdout.read()


# ---- beta 12: another session's RUNNING work is in use, and kept ------------
#
# Every test run keeps its temp files in one `chromiq-run-*` folder, and two
# sessions run tests side by side. Unless a process pattern matched, the
# cleanup of one session took the other's running folder from under it.
# Anything changed in the last 30 minutes, or held open by a live process, is
# now kept and reported "in use, kept".

@pytest.fixture
def three_folders(monkeypatch):
    """In the temp root the planner scans: an old idle folder, a fresh one,
    and an old one this process holds a file open in."""
    import shutil
    root = Path(tempfile.gettempdir())
    made = []

    def mk(name):
        p = root / name
        p.mkdir()
        (p / "f.txt").write_text("x", encoding="utf-8")
        made.append(p)
        return p

    idle = mk(f"chromiq-run-idle{os.getpid()}")
    fresh = mk(f"chromiq-run-fresh{os.getpid()}")
    held = mk(f"chromiq-run-held{os.getpid()}")
    _age(idle)
    _age(held)
    monkeypatch.setattr(S, "something_running", lambda: [])
    monkeypatch.setattr(S, "merged_worktrees", lambda: [])
    # Only these three are ever planned, so a run with --yes below can touch
    # nothing else on the machine (no real /private/tmp sandbox, no prune).
    monkeypatch.setattr(S.disk_report, "_rows", lambda: [
        ("$TMPDIR chromiq-* folders", 3, 0, "", True, [idle, fresh, held])])
    monkeypatch.setattr(S, "_git", lambda *a: S.subprocess.CompletedProcess(a, 0, "", ""))
    fh = open(held / "f.txt", encoding="utf-8")
    try:
        yield idle, fresh, held
    finally:
        fh.close()
        for p in made:
            shutil.rmtree(p, ignore_errors=True)


def test_a_folder_changed_in_the_last_half_hour_is_in_use(three_folders):
    import time
    _idle, fresh, _held = three_folders
    assert S.in_use(fresh, time.time(), []).startswith("changed ")


def test_an_old_folder_a_live_process_holds_open_is_in_use(three_folders):
    import time
    idle, _fresh, held = three_folders
    open_paths = S.held_open_paths()
    assert S.in_use(held, time.time(), open_paths) == "held open by a live process"
    assert S.in_use(idle, time.time(), open_paths) == ""


def test_the_plan_keeps_what_is_in_use_and_names_it(three_folders):
    idle, fresh, held = three_folders
    items, kept = S.plan_and_kept("")
    planned = {p for _w, p, _s in items}
    kept_paths = {p: reason for _w, p, reason in kept}
    assert idle in planned
    assert fresh not in planned and held not in planned
    assert kept_paths[fresh].startswith("changed ")
    assert kept_paths[held] == "held open by a live process"


def test_a_run_reports_in_use_kept_and_leaves_them(three_folders, capsys):
    idle, fresh, held = three_folders
    S.main(["--yes"])
    out = capsys.readouterr().out
    assert "in use, kept (held open by a live process)" in out
    assert str(held) in out and str(fresh) in out
    # The summary line, wherever it falls: with a disk baseline on the machine
    # the "since baseline" lines follow it (gate 1 of beta 12 on Basti's Mac).
    summary = [ln for ln in out.splitlines() if ln.startswith("ChromIQ cleanup:")]
    assert summary and "in use, kept" in summary[-1]
    assert fresh.is_dir() and held.is_dir()
    assert not idle.exists()


def test_a_run_folder_named_after_a_live_pytest_is_in_use(tmp_path):
    """Review D: a test run's folder is ``chromiq-run-<controller pid>-*``, so
    it is kept for as long as that pytest lives, however quiet it has been."""
    import subprocess
    import sys
    import time
    live = tmp_path / f"chromiq-run-{os.getppid() or 1}-abcd"
    live.mkdir()
    _age(live)
    gone = subprocess.Popen([sys.executable, "-c", "pass"])
    gone.wait(timeout=30)
    dead = tmp_path / f"chromiq-run-{gone.pid}-efgh"
    dead.mkdir()
    _age(dead)
    assert "still running" in S.in_use(live, time.time(), [])
    assert S.in_use(dead, time.time(), []) == ""


def test_a_file_dated_in_the_future_is_not_a_recent_change(three_folders):
    """One test dates a file in 2096; a folder holding it read as "changed
    0 min ago" for ever, and 45 GB of dead run folders were kept as in use
    (2026-10-10)."""
    import time
    idle, _fresh, _held = three_folders
    future = time.time() + 70 * 365 * 86400
    os.utime(idle / "f.txt", (future, future))
    assert S.in_use(idle, time.time(), []) == ""
