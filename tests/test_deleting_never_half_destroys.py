"""F2: "Delete the whole project" destroyed files and then said nothing happened.

Measured on screen, 2026-08-28, through the real Delete button on a real project
with ONE read-only sub-folder (`runs/run1/reports`, `chmod 0555`) and nothing
else touched:

    FILES GONE: 10 of 29
       LOST project.json                    <- the manifest
       LOST runs/run1/Demo-Full-RGB.icc     <- the profile
       LOST runs/run1/Demo-Full-RGB.ti3     <- the measurement
    …and the window said, verbatim:
       "Nothing was changed.  Reason: [Errno 13] Permission denied: …/reports"

`shutil.rmtree` is not atomic: it removes everything it can reach and raises
only at the end. Losing `project.json` is what makes it worse than a partial
delete — `Open Project` refuses any folder without one, so the nineteen
survivors (the shared calibration, both averaging reads, the reports, the
exports) became unreachable through the app, while the person had just been told
their project was untouched.

Basti ruled on 2026-08-28 that deleting moves to the Trash. A Trash move is a
rename, so the unwritable child never gets the chance to defeat it, and when
there is nowhere to put the files nothing is touched at all — which is what
finally makes that sentence true.
"""
from __future__ import annotations

import os
import stat
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PyQt6")

from core.trash import move_to_trash                            # noqa: E402


def _project_with_a_read_only_folder(tmp_path) -> tuple[Path, Path]:
    root = tmp_path / "OneRun"
    run = root / "runs" / "run1"
    run.mkdir(parents=True)
    (root / "project.json").write_text('{"schema_version": 3}')
    for name in ("chart.ti1", "chart.ti2", "chart.ti3", "chart.icc"):
        (run / name).write_text("x" * 64)
    reports = run / "reports"
    reports.mkdir()
    (reports / "Quality_Check_1.txt").write_text("a report")
    os.chmod(reports, 0o555)
    return root, reports


def _files(root: Path) -> int:
    return sum(1 for p in root.rglob("*") if p.is_file()) if root.exists() else 0


def test_an_unwritable_subfolder_no_longer_half_destroys_the_project(tmp_path):
    root, reports = _project_with_a_read_only_folder(tmp_path)
    before = _files(root)
    assert before == 6

    res = move_to_trash(root)

    try:
        if res.ok:
            assert not root.exists(), "the source folder is still there"
            assert res.destination is None or res.destination.exists()
            if res.destination is not None:
                assert _files(res.destination) == before, \
                    "files went missing on the way to the Trash"
                assert (res.destination / "project.json").exists(), \
                    "the manifest was lost, so the rest can never be reopened"
        else:
            # No Trash on this filesystem — then NOTHING may have been touched.
            assert _files(root) == before, (
                "the delete failed and destroyed files anyway, which is the "
                "exact fault this replaced")
            assert (root / "project.json").exists()
            assert res.reason, "a failure has to be able to explain itself"
    finally:
        for p in (reports, res.destination / "runs" / "run1" / "reports"
                  if res.ok and res.destination else None):
            if p is not None and p.exists():
                os.chmod(p, stat.S_IRWXU)
        import shutil
        if res.ok and res.destination is not None:
            shutil.rmtree(res.destination, ignore_errors=True)


def test_a_missing_path_counts_as_already_gone(tmp_path):
    """The caller wanted it gone and it is. Reporting a failure here would make
    a second Delete look broken."""
    assert move_to_trash(tmp_path / "never-existed").ok is True


def test_a_failure_never_reports_success(tmp_path):
    """The whole module exists because an operation reported success for files
    it had not moved. If the folder is still there, the answer is False."""
    import core.trash as trash

    root = tmp_path / "Proj"
    root.mkdir()
    (root / "project.json").write_text("{}")

    class _Lying:
        @staticmethod
        def moveToTrash(_p):
            return True, "/somewhere/that/does/not/matter"

    import sys
    import types
    fake = types.ModuleType("PyQt6.QtCore")
    fake.QFile = _Lying
    real = sys.modules.get("PyQt6.QtCore")
    sys.modules["PyQt6.QtCore"] = fake
    try:
        res = trash.move_to_trash(root)
    finally:
        if real is not None:
            sys.modules["PyQt6.QtCore"] = real
    assert res.ok is False, "success was reported for a folder that never moved"
    assert root.exists()
