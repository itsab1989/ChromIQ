"""Importing an i1Profiler measurement .txt builds the per-run project layout.

`ui/txt_loader._copy_txt` places the .txt at runs/run1/chart.txt inside a fresh
project, so the subsequent txt2ti3 run produces runs/run1/chart.ti3 (the
canonical measurement). See docs/dev_folder_layout.md.
"""
from __future__ import annotations

from pathlib import Path

from ui.txt_loader import _copy_txt


def test_copy_txt_builds_project_layout(tmp_path: Path) -> None:
    src = tmp_path / "external"
    src.mkdir()
    txt = src / "MyMeasurement.txt"
    txt.write_text("CGATS.5\n", encoding="utf-8")

    working_dir = tmp_path / "ChromIQ"
    new_txt, base = _copy_txt(txt, working_dir, "Imported")

    proj = working_dir / "Imported"
    run1 = proj / "runs" / "run1"
    assert (proj / "project.json").is_file()
    # Files take the project-name stem so the txt2ti3 output is the canonical
    # <stem>.ti3 (= Run.measurement_ti3).
    assert new_txt == run1 / "Imported.txt"
    assert new_txt.is_file()
    assert base == "Imported", "txt2ti3 base must be the project stem"
    # No flat <name>.txt at the project root.
    assert not (proj / "Imported.txt").exists() or (proj / "Imported.txt").parent == run1


def test_copy_txt_overwrite_replaces_existing(tmp_path: Path) -> None:
    working_dir = tmp_path / "ChromIQ"
    txt = tmp_path / "m.txt"
    txt.write_text("NEW\n", encoding="utf-8")

    # Pre-existing project folder with stale content.
    stale = working_dir / "Imported"
    stale.mkdir(parents=True)
    (stale / "stale.txt").write_text("OLD\n", encoding="utf-8")

    new_txt, _ = _copy_txt(txt, working_dir, "Imported", overwrite=True)

    assert new_txt.read_text(encoding="utf-8") == "NEW\n"
    assert not (stale / "stale.txt").exists(), "overwrite must wipe the old folder"
    assert (working_dir / "Imported" / "project.json").is_file()
