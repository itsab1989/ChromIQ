"""A saved measurement report is written whole or not at all.

`save_report` and `rewrite_report` wrote with `Path.write_text`, which is not
atomic: a process killed mid-write leaves a truncated file with a real report's
name. That is not hypothetical here. Combined round 3 drove a dated
verification holding one good report and one truncated file and photographed
what the window did with it: Delete came up enabled with no reason beside it,
the confirmation said "0 saved reports of it are left afterwards", and the
press left the date with no verdict the window could read
(`~/Desktop/ChromIQ-beta20-proof/combined-round-3/`). The dialog was hardened
to count only files it can actually read; the file that should never have
existed on disk was left for later, and this is later.

`core.file_manager.write_json_atomically` already exists and already pays for
every trap this project has hit with `os.replace`: it resolves a symlink first
(the rename swaps the NAME, and pointed at a link it would delete the link and
leave the real file stale), it fsyncs before the rename, it carries mode, times
and flags across, and it drops the immutable bits from the scratch file so a
locked target cannot leave an undeletable `.tmp` behind.
"""
from __future__ import annotations

import inspect
import json
import os
from pathlib import Path

import pytest


def _reports_dir(run_dir: Path) -> Path:
    from core.file_manager import reports_subdir
    return Path(reports_subdir(run_dir))


def test_both_report_writers_go_through_the_atomic_helper():
    """Source, so a future edit cannot quietly go back to write_text."""
    import workflow.measurement_report as mr
    for fn in (mr.save_report, mr.rewrite_report):
        src = inspect.getsource(fn)
        assert "write_json_atomically" in src, (
            f"{fn.__name__} does not use write_json_atomically; a report "
            f"written with write_text can be left half on disk")
        assert ".write_text(" not in src, (
            f"{fn.__name__} still writes with write_text")


def test_a_failed_save_leaves_the_previous_report_untouched(tmp_path,
                                                            monkeypatch):
    import workflow.measurement_report as mr
    run = tmp_path / "run1"
    run.mkdir()
    first = mr.save_report({"kind": "first", "rows": [1, 2, 3]}, run)
    before = first.read_text(encoding="utf-8")

    real_replace = os.replace

    def boom(src, dst):
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(os, "replace", boom)
    with pytest.raises(OSError):
        mr.rewrite_report(first, {"kind": "second", "rows": [9]})
    monkeypatch.setattr(os, "replace", real_replace)

    assert first.read_text(encoding="utf-8") == before, (
        "a failed rewrite changed the report that was already on disk")
    leftovers = sorted(p.name for p in first.parent.iterdir()
                       if p.name.endswith(".tmp"))
    assert not leftovers, f"a scratch file was left behind: {leftovers}"
    assert json.loads(first.read_text(encoding="utf-8"))["kind"] == "first"


def test_a_write_that_dies_mid_payload_leaves_nothing_readable_behind(
        tmp_path, monkeypatch):
    """The scratch file is made before the payload is written, so the kill
    that matters is during the dump, not during the rename."""
    import workflow.measurement_report as mr
    run = tmp_path / "run1"
    run.mkdir()
    good = mr.save_report({"kind": "good"}, run)

    def half_written(obj, fh, **kw):
        fh.write('{"kind": "tru')
        raise KeyboardInterrupt

    monkeypatch.setattr(json, "dump", half_written)
    with pytest.raises(KeyboardInterrupt):
        mr.save_report({"kind": "truncated"}, run)
    monkeypatch.undo()

    on_disk = sorted(p.name for p in good.parent.glob("report_*.json"))
    assert on_disk == [good.name], (
        f"a killed write left a file with a report's name: {on_disk}")
    assert not list(good.parent.glob("*.tmp"))
    for p in good.parent.glob("report_*.json"):
        json.loads(p.read_text(encoding="utf-8"))   # every one still parses


def test_a_read_only_report_still_refuses_the_write(tmp_path):
    """Atomicity must not quietly take away a refusal.

    `write_text` on a file the user had made read-only raised, and the window
    told them the file could not be written. `os.replace` needs write
    permission on the DIRECTORY, not on the target, so the rename succeeds and
    the content changes without a word, with `copystat` carrying the 0444 back
    so the file still looks protected. That hole was already open for
    `project.json` and `meta.json`, which use the same helper; it is closed for
    all three.
    """
    import workflow.measurement_report as mr
    run = tmp_path / "run1"
    run.mkdir()
    p = mr.save_report({"kind": "locked"}, run)
    before = p.read_text(encoding="utf-8")
    p.chmod(0o444)
    try:
        with pytest.raises(PermissionError):
            mr.rewrite_report(p, {"kind": "overwritten"})
        assert p.read_text(encoding="utf-8") == before
        assert not list(p.parent.glob("*.tmp"))
    finally:
        p.chmod(0o644)


def test_every_saved_report_parses(tmp_path):
    import workflow.measurement_report as mr
    run = tmp_path / "run1"
    run.mkdir()
    written = [mr.save_report({"kind": f"r{i}", "pad": "x" * 50_000}, run)
               for i in range(4)]
    from workflow.measurement_report import list_reports
    found = list_reports(run)
    assert len(found) == len(written)
    for p in found:
        json.loads(p.read_text(encoding="utf-8"))
