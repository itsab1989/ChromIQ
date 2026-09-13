"""A pack shipped with two of its six projects missing, and the check passed.

Knut, 2026-09-13, on the beta 8 release: *"the last published
ChromIQ-Report-Limit-Demos project collection did not contain all projects as
previous demo package. The complete package should always be published."*

He is right, and the way it happened is the part worth guarding. The zip was
built by hand-listing four project names, taken from the PREVIOUS release
rather than from `PROJECTS`, and the check run against it compared only the
archive's ROOT FOLDER NAME with the previous one. Both matched, so the check
was green over a pack missing `Report-Limits-Set-Compare` and
`Report-Limits-Threshold-Series`.

That is the same shape as comparing a plist against a backup that already holds
the bad value, which CLAUDE.md records costing a day: a baseline is only
evidence if something independent says the baseline was right.

`make_report_limit_demos.verify_pack` asks `PROJECTS`, which is the one place
that knows, and `--verify` is what the release step runs. The generator's own
`--zip` archives the whole folder and cannot omit a project; nothing should ever
assemble that archive by hand again.
"""
from __future__ import annotations

import sys
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))


def _gen():
    import importlib
    return importlib.import_module("make_report_limit_demos")


def _complete(tmp_path: Path) -> Path:
    """A pack-shaped folder holding every project the generator declares."""
    g = _gen()
    d = tmp_path / "ChromIQ-Report-Limit-Demos"
    d.mkdir()
    for name, _plans in g.PROJECTS:
        (d / name).mkdir()
    (d / "README.txt").write_text("x", encoding="utf-8")
    (d / "intended-vs-actual.json").write_text("{}", encoding="utf-8")
    return d


def test_a_complete_folder_passes(tmp_path):
    assert _gen().verify_pack(_complete(tmp_path)) == []


def test_the_exact_pack_that_shipped_is_caught(tmp_path):
    """Reproduced: the two projects that were missing from beta 8."""
    g = _gen()
    d = _complete(tmp_path)
    gone = ["Report-Limits-Set-Compare", "Report-Limits-Threshold-Series"]
    for name in gone:
        if (d / name).exists():
            (d / name).rmdir()
        else:
            pytest.skip(f"{name} is no longer a project of this pack")
    gaps = g.verify_pack(d)
    assert len(gaps) == 2, gaps
    for name in gone:
        assert any(name in x for x in gaps), (name, gaps)


def test_a_missing_readme_is_caught_too(tmp_path):
    d = _complete(tmp_path)
    (d / "README.txt").unlink()
    assert any("README.txt" in x for x in _gen().verify_pack(d))


def test_it_reads_a_zip_the_same_way(tmp_path):
    """The release ships a `.zip`, so that is the thing that has to be checked,
    not the folder it was built from."""
    g = _gen()
    d = _complete(tmp_path)
    z = tmp_path / "pack.zip"
    with zipfile.ZipFile(z, "w") as zf:
        for p in sorted(d.rglob("*")):
            zf.write(p, str(Path(d.name) / p.relative_to(d)))
        # a directory-only entry needs a member inside it to appear in a zip
        for name, _plans in g.PROJECTS:
            zf.writestr(f"{d.name}/{name}/project.json", "{}")
    assert g.verify_pack(z) == []

    z2 = tmp_path / "short.zip"
    drop = g.PROJECTS[-1][0]
    with zipfile.ZipFile(z2, "w") as zf:
        for name, _plans in g.PROJECTS:
            if name == drop:
                continue
            zf.writestr(f"{d.name}/{name}/project.json", "{}")
        zf.writestr(f"{d.name}/README.txt", "x")
        zf.writestr(f"{d.name}/intended-vs-actual.json", "{}")
    assert any(drop in x for x in g.verify_pack(z2))


def test_an_archive_that_is_not_there_is_a_gap_not_a_crash(tmp_path):
    assert _gen().verify_pack(tmp_path / "nope.zip")
    assert _gen().verify_pack(tmp_path / "nope")


def test_the_project_list_is_what_decides(tmp_path):
    """`verify_pack` must read `PROJECTS`, not a list of its own.

    A second copy of the names is how the shipped pack went wrong in the first
    place.
    """
    import inspect
    src = inspect.getsource(_gen().verify_pack)
    assert "PROJECTS" in src, "the verifier has its own idea of what a pack holds"


# ---------------------------------------------------------------------------
# …AND EVERY MEASUREMENT IN IT CARRIES ITS VERDICT
#
# Knut, same comment: *"Make sure all verdicts exist in the demo package"* and
# *"Why is the verdict and measurements not kept as part of the demo data
# created, so that it is a real test?"*. The pack saved a report under each
# dated verification and none beside the sheet a profile was built from, so
# opening a run's own measurement reached the report window's last-resort
# branch and the page told the reader the verdict had been lost.
#
# The two tests below are an adversary round's reproductions, kept because both
# passed a pack that was broken.
# ---------------------------------------------------------------------------
import json                                                    # noqa: E402


_MADE = [0]


def _run_with(tmp_path: Path, verdict, *, extra=()) -> Path:
    """A pack-shaped folder with one project, one run, one measurement and one
    saved report carrying *verdict*. *extra* names further files to drop in.

    Each call gets its OWN folder: two calls in one test shared `tmp_path/pack`
    and the second raised FileExistsError, which is a fixture bug pretending to
    be a finding.
    """
    _MADE[0] += 1
    root = tmp_path / f"pack{_MADE[0]}"
    run = root / "Proj" / "runs" / "run1"
    (run / "reports").mkdir(parents=True)
    (run / "Proj.ti3").write_text("x", encoding="utf-8")
    (run / "reports" / "report_2026-01-01_00-00-00.json").write_text(
        json.dumps({"verdict": verdict} if verdict is not None else {}),
        encoding="utf-8")
    for rel in extra:
        f = root / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text("x", encoding="utf-8")
    return root


def _zip_of(folder: Path) -> Path:
    z = folder.parent / f"{folder.name}.zip"
    with zipfile.ZipFile(z, "w") as zf:
        for f in folder.rglob("*"):
            if f.is_file():
                zf.write(f, str(Path(folder.name) / f.relative_to(folder)))
    return z


_ROWS = [{"row_id": "all_de00_avg", "word": "PASS"}]


def test_a_pack_with_no_verdict_beside_a_measurement_is_incomplete(tmp_path):
    """The fault Knut hit: a measurement with no saved report at all."""
    g = _gen()
    root = tmp_path / "pack"
    run = root / "Proj" / "runs" / "run1"
    run.mkdir(parents=True)
    (run / "Proj.ti3").write_text("x", encoding="utf-8")
    gaps = g._verdicts_missing(root)
    assert gaps and "Proj/runs/run1/Proj.ti3" in gaps[0], gaps


def test_a_verdict_with_no_rows_in_it_does_not_count(tmp_path):
    """ADVERSARY REPRODUCTION. `recorded_verdict` requires only that `rows` is
    a list, so `{"verdict": {"rows": []}}` satisfied it and a pack whose every
    verdict was hollow was reported complete."""
    g = _gen()
    assert g._verdicts_missing(_run_with(tmp_path, {"rows": []})), (
        "an empty verdict block counts as a verdict")
    assert g._verdicts_missing(_run_with(tmp_path, {"rows": _ROWS})) == []


def test_the_zip_and_the_folder_are_the_same_check(tmp_path):
    """ADVERSARY REPRODUCTION. The folder branch skipped the role-named
    intermediates and the zip branch skipped nothing, so any pack holding a run
    that used measurement averaging passed as a folder and failed as a zip."""
    g = _gen()
    folder = _run_with(tmp_path, {"rows": _ROWS},
                       extra=("Proj/runs/run1/reads/read1.ti3",
                              "Proj/runs/run1/cache/scratch.ti3",
                              "Proj/runs/run1/merged.ti3"))
    assert g._verdicts_missing(folder) == [], "the intermediates are judged"
    assert g._verdicts_missing(_zip_of(folder)) == g._verdicts_missing(folder)


def test_the_zip_and_the_folder_agree_when_something_really_is_missing(tmp_path):
    """The control: if both branches were simply returning [] the test above
    would pass with the check deleted."""
    g = _gen()
    folder = _run_with(tmp_path, None)          # a report with no verdict key
    gaps = g._verdicts_missing(folder)
    assert gaps, "a report with no verdict block was accepted"
    assert g._verdicts_missing(_zip_of(folder)) == gaps


def test_a_calibration_measurement_is_judged_like_any_other(tmp_path):
    """`cal/` is deliberately NOT on the skip list. A calibration measurement
    is a measurement, and a pack that ships one should carry its verdict."""
    g = _gen()
    root = _run_with(tmp_path, {"rows": _ROWS})
    cal = root / "Proj" / "cal"
    cal.mkdir(parents=True)
    (cal / "Proj-cal.ti3").write_text("x", encoding="utf-8")
    assert any("cal" in g_ for g_ in g._verdicts_missing(root)), (
        "a calibration measurement with no verdict passed unnoticed")
