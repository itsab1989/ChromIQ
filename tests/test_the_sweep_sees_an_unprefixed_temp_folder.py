"""The suite's own temp sweep, and the 198 GB it could not see.

`_sweep_stale_temp_dirs` globbed `chromiq[-_]*` and pytest's own trees, so it
removed every temp folder created WITH a prefix and none created without one.
`tempfile.mkdtemp()` with no `prefix=` makes `tmpXXXXXXXX`, twenty-five test
files still call it, and each of those folders holds a chart build.

Measured 2026-09-12, after a day of gate runs: **62,548 such folders, 198 GB**,
while every run printed "[cleanup] removed this run's temp files". A guard on
one door and not the identical door beside it, and the docstring on the sweep
asserted the door was already shut.

`tmp*` is what EVERY application's `tempfile.mkdtemp()` produces, so the sweep
may never go by the name. These tests pin the two halves of that: what must be
recognised, and what must never be touched.
"""
from __future__ import annotations

import pathlib

from tests.conftest import _is_chromiq_temp


def _dir(root: pathlib.Path, name: str) -> pathlib.Path:
    d = root / name
    d.mkdir(parents=True, exist_ok=True)
    return d


# --- what must be recognised ------------------------------------------------

def test_a_measurement_or_chart_file_marks_the_folder(tmp_path):
    for suffix in (".ti1", ".ti2", ".ti3", ".cht", ".cie", ".icc", ".cal"):
        d = _dir(tmp_path, f"tmp{suffix[1:]}")
        (d / f"c{suffix}").write_text("x", encoding="utf-8")
        assert _is_chromiq_temp(d), suffix


def test_it_looks_one_level_down(tmp_path):
    d = _dir(tmp_path, "tmpnested")
    (d / "run1").mkdir()
    (d / "run1" / "m.ti3").write_text("x", encoding="utf-8")
    assert _is_chromiq_temp(d)


def test_a_chart_probe_folder_is_enough_on_its_own(tmp_path):
    """The shape the suffixes miss. The geometry probes name a folder per
    instrument, paper, resolution and flag, and fill it with TIFFs, whose
    suffix is far too common to be a marker."""
    for name in ("41A4150False", "CMLetter300True", "CR30A3600False",
                 "SSA4300False", "p3A5600True"):
        d = _dir(tmp_path, f"tmp{name}")
        probe = d / name
        probe.mkdir()
        (probe / "s.tif").write_text("x", encoding="utf-8")
        assert _is_chromiq_temp(d), name


def test_a_project_manifest_marks_it(tmp_path):
    d = _dir(tmp_path, "tmpproject")
    (d / "project.json").write_text("{}", encoding="utf-8")
    assert _is_chromiq_temp(d)


# --- what must NEVER be touched ---------------------------------------------

def test_another_application_s_temp_folder_is_left_alone(tmp_path):
    d = _dir(tmp_path, "tmpsomebodyelse")
    (d / "Cache.db").write_text("x", encoding="utf-8")
    (d / "notes.txt").write_text("x", encoding="utf-8")
    (d / "session").mkdir()
    assert not _is_chromiq_temp(d)


def test_a_bare_tiff_is_not_proof(tmp_path):
    """Half the machine writes TIFFs. Only a probe FOLDER full of them counts,
    because that folder's name is one nothing else produces."""
    d = _dir(tmp_path, "tmpjustatiff")
    (d / "photo.tif").write_text("x", encoding="utf-8")
    (d / "scan.tiff").write_text("x", encoding="utf-8")
    assert not _is_chromiq_temp(d)


def test_an_empty_folder_is_not_claimed(tmp_path):
    assert not _is_chromiq_temp(_dir(tmp_path, "tmpempty"))


def test_it_gives_up_rather_than_walk_a_big_foreign_tree(tmp_path):
    """A false negative costs disk and is swept later. A false POSITIVE deletes
    somebody's data, so the budget fails CLOSED."""
    d = _dir(tmp_path, "tmpbig")
    for i in range(300):
        (d / f"f{i}.txt").write_text("x", encoding="utf-8")
    assert not _is_chromiq_temp(d)


def test_it_does_not_follow_a_symlink_out_of_the_folder(tmp_path):
    d = _dir(tmp_path, "tmplinked")
    outside = _dir(tmp_path, "real-data")
    (outside / "important.ti3").write_text("x", encoding="utf-8")
    try:
        (d / "link").symlink_to(outside, target_is_directory=True)
    except (OSError, NotImplementedError):
        return                       # no symlinks here; nothing to prove
    assert not _is_chromiq_temp(d)


def test_a_missing_folder_answers_no_rather_than_raising(tmp_path):
    assert not _is_chromiq_temp(tmp_path / "was-never-there")


# --- and the sweep itself asks the question ---------------------------------

def test_the_sweep_considers_unprefixed_folders_at_all():
    """The fault was not in the filter, it was that nothing ever offered an
    unprefixed folder to one."""
    import inspect

    from tests import conftest
    src = inspect.getsource(conftest._sweep_stale_temp_dirs)
    assert 'root.glob("tmp*")' in src, (
        "the sweep is back to globbing only prefixed folders, which is what "
        "left 62,548 of them on the disk")
    assert "_is_chromiq_temp" in src, (
        "an unprefixed folder must be judged by its CONTENTS; `tmp*` belongs "
        "to every application on the machine")
