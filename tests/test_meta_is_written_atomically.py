"""A meta.json is never left half-written.

Knut, #130 (2026-08-06), specifying how the settings files must be handled:

    "Write the updated JSON data to a temporary file in the same directory,
    then rename (replace) the original file with the temporary one. This
    prevents file corruption if the process crashes mid-write."

These files carry a run's description, its chart notes and — once the store is
finished — its Create Chart settings. A truncated one loses all of it, and the
loader would read the wreck as "this target has nothing stored".
"""
import json

import pytest

from core.file_manager import Project, write_json_atomically


def test_it_writes_what_it_was_given(tmp_path):
    target = tmp_path / "meta.json"
    write_json_atomically(target, {"a": 1, "b": "two"})
    assert json.loads(target.read_text(encoding="utf-8")) == {"a": 1, "b": "two"}


def test_it_leaves_no_scratch_file_behind(tmp_path):
    target = tmp_path / "meta.json"
    write_json_atomically(target, {"a": 1})
    assert [p.name for p in tmp_path.iterdir()] == ["meta.json"]


def test_a_failed_write_keeps_the_previous_file_intact(tmp_path, monkeypatch):
    """The whole point: a crash mid-write must not destroy what was there."""
    target = tmp_path / "meta.json"
    write_json_atomically(target, {"good": True})

    def boom(*_a, **_k):
        raise OSError("disk full")

    monkeypatch.setattr("core.file_manager.os.fsync", boom)
    with pytest.raises(OSError):
        write_json_atomically(target, {"good": False})

    assert json.loads(target.read_text(encoding="utf-8")) == {"good": True}, (
        "the previous contents were lost by a write that failed"
    )
    assert not list(tmp_path.glob("*.tmp")), "a scratch file was left behind"


def test_the_temp_file_is_in_the_same_directory(tmp_path, monkeypatch):
    """Across a filesystem boundary os.replace stops being atomic."""
    seen = []
    real_replace = __import__("os").replace

    def spy(src, dst):
        seen.append((str(src), str(dst)))
        return real_replace(src, dst)

    monkeypatch.setattr("core.file_manager.os.replace", spy)
    target = tmp_path / "deep" / "meta.json"
    write_json_atomically(target, {"x": 1})
    src, dst = seen[0]
    from pathlib import Path
    assert Path(src).parent == Path(dst).parent


@pytest.mark.parametrize("which", ["run", "calibration"])
def test_both_meta_writers_use_it(tmp_path, which):
    proj = Project.create(tmp_path / "Demo", "Demo")
    store = proj.run("run1") if which == "run" else proj.calibration
    store.ensure_dir()
    meta = store.load_meta()
    meta.chart_notes = "written atomically"
    store.save_meta(meta)
    assert store.load_meta().chart_notes == "written atomically"
    assert not list(store.dir.glob("*.tmp"))


# ---- B8-225: what ELSE was true of the file before ----------------------
#
# `os.replace` SWAPS THE NAME, NOT THE FILE, and this project has been bitten by
# that once already (the ICC accented-name fix, 2026-09-02). Combined round 9
# measured the same three losses on this helper, on a real `project.json`:
#
#   mode 0600 -> 0644, the Finder tag destroyed, and a symlinked manifest
#   replaced by a regular file with the real file left holding the old text.
#
# Two are fixed below. The third is stated rather than hidden: extended
# attributes are not carried on macOS, because `shutil.copystat` copies them
# only where `os.listxattr` exists, which is Linux.
def test_the_write_goes_through_a_symlink_rather_than_replacing_it(tmp_path):
    """`write_text` wrote THROUGH the link. `os.replace` deleted it and left
    every other reader of the real file seeing the old contents."""
    import os

    real = tmp_path / "somewhere-else.json"
    real.write_text('{"old": true}', encoding="utf-8")
    link = tmp_path / "meta.json"
    link.symlink_to(real)

    write_json_atomically(link, {"new": True})

    assert link.is_symlink(), "the symlink was eaten and left a regular file"
    assert json.loads(real.read_text(encoding="utf-8")) == {"new": True}, (
        "the real file behind the link still holds the old contents")
    assert os.path.realpath(link) == os.path.realpath(real)


def test_the_file_keeps_the_permissions_it_had(tmp_path):
    """A manifest the user (or a restore) made read-only came back writable,
    and one written 0600 came back 0644 — the new inode carries the process's
    umask and nothing of the file it replaced."""
    import os

    target = tmp_path / "meta.json"
    write_json_atomically(target, {"a": 1})
    os.chmod(target, 0o600)

    write_json_atomically(target, {"a": 2})

    assert os.stat(target).st_mode & 0o777 == 0o600, (
        "the replacement carries the process's mode, not the file's")
    assert json.loads(target.read_text(encoding="utf-8")) == {"a": 2}


def test_a_volume_that_refuses_the_properties_still_gets_the_write(
        tmp_path, monkeypatch):
    """Carrying the properties across must never be the thing that loses the
    write: what it protects is a property of the file, not the file."""
    import core.file_manager as fm

    target = tmp_path / "meta.json"
    write_json_atomically(target, {"a": 1})
    monkeypatch.setattr(fm.shutil, "copystat",
                        lambda *a, **k: (_ for _ in ()).throw(
                            OSError("this volume has no such thing")))
    write_json_atomically(target, {"a": 2})
    assert json.loads(target.read_text(encoding="utf-8")) == {"a": 2}


def test_the_project_manifest_gets_all_of_this_too(tmp_path):
    """`project.json` went through `write_json_atomically` in combined round 8,
    so it inherits the losses as well as the atomicity."""
    import os

    proj = Project.create(tmp_path, "B8225")
    os.chmod(proj.manifest_path, 0o600)
    proj.save_manifest()
    assert os.stat(proj.manifest_path).st_mode & 0o777 == 0o600
