"""The end-of-session cleanup deletes only what our tooling created.

Basti, 2026-10-02: *"just make sure that does never delete any personal data -
only what you added in a session that is considered not needed"*.
scripts/session_cleanup.py runs from a SessionEnd hook, unattended, so its
guard (`is_ours`) is tested directly: every personal place is refused, every
place our tooling writes to is accepted, and `remove` refuses (and leaves in
place) anything the guard refuses, even if a bug put it on the list.
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
import session_cleanup as S  # noqa: E402

HOME = Path.home()
TMP = Path(tempfile.gettempdir())


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
