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
