"""§4 on the verify chart: replacing it ARCHIVES it, never deletes it.

Found on hardware (Sebastian, 2026-08-10): regenerating the verification
chart deleted the gamut chart and its colorimetric reference outright while
the replace window promised "moved to the 'old' folder … nothing is deleted".
"""
from __future__ import annotations

from pathlib import Path

from core.file_manager import Project


def _run(tmp_path):
    p = Project.create(tmp_path / "P", "P")
    run = p.current_run()
    run.ensure_dir()
    return run


def test_replacing_the_verify_chart_archives_it(tmp_path):
    run = _run(tmp_path)
    vdir = run.verifications_dir
    vdir.mkdir(parents=True)
    # The previous (gamut) chart, its reference, a page, and a sidecar.
    (vdir / f"{run.verify_stem}.ti2").write_text("CTI2 old\n")
    (vdir / f"{run.verify_stem}-reference.ti3").write_text("CTI3 ref\n")
    (vdir / f"{run.verify_stem}.tif").write_bytes(b"II*\x00old")
    exp = vdir / "exports"
    exp.mkdir()
    (exp / f"{run.verify_stem}-colours.txt").write_text("colours\n")
    # A measured dated verification must never be touched.
    dated = vdir / "2026-08-10_113503"
    dated.mkdir()
    (dated / f"{run.verify_stem}.ti3").write_text("CTI3 measured\n")

    # The new chart at the run root, about to be adopted.
    run.chart_ti2.write_text("CTI2 new\n")
    (run.dir / f"{run.stem}.ti1").write_text("CTI1 new\n")

    moved = run.adopt_run_chart_as_verify()
    assert moved == run.verify_chart_ti2
    assert run.verify_chart_ti2.read_text() == "CTI2 new\n"

    # The displaced chart is in verifications/old/<date>/ — complete.
    archives = [d for d in run.verifications_old_dir.iterdir() if d.is_dir()]
    assert len(archives) == 1
    names = sorted(p.name for p in archives[0].iterdir())
    assert f"{run.verify_stem}.ti2" in names
    assert f"{run.verify_stem}-reference.ti3" in names
    assert f"{run.verify_stem}.tif" in names
    assert f"{run.verify_stem}-colours.txt" in names
    assert (archives[0] / f"{run.verify_stem}.ti2").read_text() == "CTI2 old\n"

    # The dated measurement folder is untouched.
    assert (dated / f"{run.verify_stem}.ti3").read_text() == "CTI3 measured\n"


def test_adopting_over_nothing_archives_nothing(tmp_path):
    run = _run(tmp_path)
    run.verifications_dir.mkdir(parents=True)
    run.chart_ti2.write_text("CTI2 new\n")
    run.adopt_run_chart_as_verify()
    old = run.verifications_old_dir
    assert not old.exists() or not any(old.iterdir())
