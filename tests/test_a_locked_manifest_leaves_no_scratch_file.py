"""A manifest the user LOCKED must not leave an undeletable scratch file.

`core.file_manager.write_json_atomically` says, in a comment above its own
cleanup, *"Never leave the scratch file behind to be mistaken for real data."*
Combined round 9 added `shutil.copystat` so a manifest's mode survived the
rename, and on macOS `copystat` carries `st_flags` as well - so a
``project.json`` the user had **Locked** in the Finder's Get Info panel
(``UF_IMMUTABLE``) made the SCRATCH file immutable too. The rename over a
locked file fails either way and always did; what changed is that the cleanup
could no longer delete what it had just made, and a ``project.json.tmp`` was
left in the project folder that neither the Finder, nor ``unlink``, nor
``rm -f`` would remove.

Measured A/B against the helper as it stood before that change (combined round
10): no scratch file before, an undeletable one after.

These tests pin BOTH sides: the lock bits never reach a scratch file that is
about to be cleaned up, and round 9's actual gains (the mode, and writing
through a symlink) are still there.
"""
from __future__ import annotations

import json
import os
import stat
import subprocess

import pytest

from core.file_manager import write_json_atomically

pytestmark = pytest.mark.skipif(
    not hasattr(os, "chflags"),
    reason="file flags (chflags) exist only on the BSD/macOS family",
)

_UF_IMMUTABLE = getattr(stat, "UF_IMMUTABLE", 0x00000002)


def _locked_manifest(tmp_path):
    p = tmp_path / "project.json"
    p.write_text('{"old": true}', encoding="utf-8")
    os.chflags(p, _UF_IMMUTABLE)
    return p


def _unlock_everything(tmp_path):
    for q in tmp_path.rglob("*"):
        try:
            os.chflags(q, 0)
        except OSError:
            pass


def test_a_locked_manifest_leaves_no_scratch_file(tmp_path):
    """The whole finding, in one assertion nobody can misread."""
    p = _locked_manifest(tmp_path)
    try:
        with pytest.raises(PermissionError):
            write_json_atomically(p, {"schema_version": 2, "name": "new"})
        left = sorted(q.name for q in tmp_path.iterdir()
                      if q.name.endswith(".tmp"))
        assert left == [], (
            "the write failed on a locked manifest and left "
            f"{left} in the project folder"
        )
    finally:
        _unlock_everything(tmp_path)


def test_a_scratch_file_left_behind_would_be_undeletable(tmp_path):
    """Why the assertion above matters: the leftover could not be removed.

    This does not test the helper - it establishes, on this machine, that an
    immutable file really does refuse ``unlink``. Without it, "no scratch file"
    reads like tidiness rather than the difference between a file the user can
    delete and one they cannot.
    """
    q = tmp_path / "scratch.tmp"
    q.write_text("x", encoding="utf-8")
    os.chflags(q, _UF_IMMUTABLE)
    try:
        with pytest.raises(PermissionError):
            q.unlink()
        assert subprocess.run(["rm", "-f", str(q)], capture_output=True,
                              timeout=30).returncode != 0
        assert q.exists()
    finally:
        _unlock_everything(tmp_path)


def test_the_locked_manifest_itself_is_never_overwritten(tmp_path):
    """The lock is honoured: the user's text survives, and so does the lock."""
    p = _locked_manifest(tmp_path)
    try:
        with pytest.raises(PermissionError):
            write_json_atomically(p, {"schema_version": 2, "name": "new"})
        assert json.loads(p.read_text(encoding="utf-8")) == {"old": True}
        assert p.stat().st_flags & _UF_IMMUTABLE
    finally:
        _unlock_everything(tmp_path)


def test_the_mode_is_still_carried_across(tmp_path):
    """Combined round 9's gain, kept: a 0600 manifest does not come back 0644."""
    p = tmp_path / "project.json"
    p.write_text('{"old": true}', encoding="utf-8")
    os.chmod(p, 0o600)
    write_json_atomically(p, {"schema_version": 2, "name": "new"})
    assert stat.S_IMODE(p.stat().st_mode) == 0o600
    assert json.loads(p.read_text(encoding="utf-8"))["name"] == "new"


def test_a_symlinked_manifest_is_still_written_through(tmp_path):
    """Combined round 9's other gain, kept: the link survives the write."""
    real = tmp_path / "elsewhere.json"
    real.write_text('{"old": true}', encoding="utf-8")
    link = tmp_path / "project.json"
    link.symlink_to(real)
    write_json_atomically(link, {"schema_version": 2, "name": "new"})
    assert link.is_symlink()
    assert json.loads(real.read_text(encoding="utf-8"))["name"] == "new"


def test_an_ordinary_write_keeps_the_flags_it_was_given(tmp_path):
    """The unlock is aimed at the SCRATCH file, never at the user's own.

    A flag that does not block a rename (``UF_HIDDEN``) must still cross, or
    the repair would have quietly undone what `copystat` is there for.
    """
    hidden = getattr(stat, "UF_HIDDEN", 0x00008000)
    p = tmp_path / "project.json"
    p.write_text('{"old": true}', encoding="utf-8")
    os.chflags(p, hidden)
    try:
        write_json_atomically(p, {"schema_version": 2, "name": "new"})
        assert p.stat().st_flags & hidden, (
            "a flag that does not block the rename was dropped")
        assert json.loads(p.read_text(encoding="utf-8"))["name"] == "new"
    finally:
        _unlock_everything(tmp_path)
