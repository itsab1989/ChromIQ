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
    assert json.loads(target.read_text()) == {"a": 1, "b": "two"}


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

    assert json.loads(target.read_text()) == {"good": True}, (
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
