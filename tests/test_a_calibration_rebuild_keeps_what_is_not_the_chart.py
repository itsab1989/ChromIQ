"""A note left beside a calibration survives Generate Chart.

WHAT WENT WRONG
    `Calibration.chart_files()` is defined by subtraction — everything live in
    `cal/` that is not a result — and the subtraction had no third category.
    `result_files()` is a closed list of four suffixes, so a file that was
    neither chart nor result (a note the person typed, a photograph of the
    printed sheet, a `.bak` of a measurement, a `README` with no extension) was
    classed as CHART. The owner's ruling of 2026-09-02 (option 3) is that an
    unmeasured chart is an experiment and leaves nothing, so the unmeasured
    branch of `reset()` stashes the chart and drops it once a new one exists —
    and it dropped all of that with it. Not archived, not in the Trash,
    nowhere, with a window on screen that spoke only about the chart.

    The ruling is about THE CHART. The code was applying it to everything it
    did not recognise.

    Two smaller faults were the same confusion: a person's SUB-FOLDER survived
    while their FILE was destroyed (because `live_files()` lists files only),
    and `.DS_Store` survived while `notes.txt` did not (because dot-files are
    skipped). One rule had to answer for all three shapes.

THE FIX
    `Calibration.is_ours(name)` — NFC on both sides, a plain `startswith` and
    never a pattern. The rule, in one sentence: only the files ChromIQ named
    after this calibration are the chart, and nothing else in `cal/` is ever
    moved or discarded.

WHAT THESE TESTS PROVE
    That every shape of stranger survives a rebuild; that the chart is still
    dropped, so the ruling is honoured; that a sidecar nobody has invented yet
    is still covered by construction, which is the property subtraction was
    chosen for; that a decomposed name and a name holding glob metacharacters
    both still recognise their own chart; and that the MEASURED branch archives
    exactly what it archived before.
"""
from __future__ import annotations

import unicodedata as ud
from pathlib import Path

import pytest

from core.file_manager import Calibration

CHART_TAILS = (".ti1", ".ti2", ".cht", ".ps", ".channels.json",
               "_01.tif", "_02.tif")


def _cal(root: Path, name: str = "Demo-Project") -> Calibration:
    (root / name).mkdir(parents=True, exist_ok=True)
    cal = Calibration(root / name)
    cal.ensure_dir()
    return cal


def _chart(cal: Calibration, marker: str = "chart") -> None:
    for t in CHART_TAILS:
        (cal.dir / f"{cal.stem}{t}").write_text(marker, encoding="utf-8")


def _strangers(cal: Calibration) -> dict:
    """One of every shape a person's own thing can take in `cal/`."""
    made = {}
    p = cal.dir / "notes about this calibration.txt"
    p.write_text("the paper was still damp", encoding="utf-8")
    made["a note"] = p
    p = cal.dir / "IMG_4821.jpg"
    p.write_bytes(b"a photo of the printed sheet")
    made["a photograph"] = p
    p = cal.dir / "README"
    p.write_text("no extension at all", encoding="utf-8")
    made["no extension"] = p
    p = cal.dir / "second-opinion.ti3.bak"
    p.write_text("a backup of a measurement", encoding="utf-8")
    made["a .bak"] = p
    d = cal.dir / "my measurements"
    d.mkdir()
    (d / "run-a.ti3").write_text("x", encoding="utf-8")
    made["a sub-folder"] = d
    p = cal.dir / ".DS_Store"
    p.write_bytes(b"\x00")
    made["a dot-file"] = p
    return made


def _rebuild(cal: Calibration) -> None:
    """Generate Chart, and the build succeeds — what ChartCreator does."""
    done = cal.reset(stash=True)
    cal.settle_chart_stash(done.stash, built=True)


# ---------------------------------------------------------------------------
# The fault itself
# ---------------------------------------------------------------------------

def test_a_note_left_beside_an_unmeasured_calibration_survives(tmp_path):
    cal = _cal(tmp_path)
    _chart(cal)
    note = cal.dir / "notes about this calibration.txt"
    note.write_text("the paper was still damp", encoding="utf-8")

    _rebuild(cal)

    assert note.is_file(), (
        "the person's note was destroyed by a chart rebuild — the ruling is "
        "about the chart, not about everything the folder holds")
    assert note.read_text(encoding="utf-8") == "the paper was still damp"


@pytest.mark.parametrize("shape", ["a note", "a photograph", "no extension",
                                   "a .bak", "a sub-folder", "a dot-file"])
def test_every_shape_of_the_persons_own_thing_survives(tmp_path, shape):
    """ONE rule for every shape. A file used to die while a folder beside it
    lived, and `.DS_Store` outlived `notes.txt`."""
    cal = _cal(tmp_path)
    _chart(cal)
    made = _strangers(cal)

    _rebuild(cal)

    assert made[shape].exists(), f"{shape} did not survive the rebuild"


def test_nothing_of_the_persons_reaches_the_stash_at_all(tmp_path):
    """Not "restored afterwards" — never touched. A stash is where files go to
    be dropped, so a stranger must not be in one even for a moment."""
    cal = _cal(tmp_path)
    _chart(cal)
    made = _strangers(cal)

    done = cal.reset(stash=True)
    assert done.stash is not None
    stashed = sorted(p.name for p in done.stash.iterdir())
    for label, path in made.items():
        assert path.name not in stashed, f"{label} was set aside to be dropped"
        assert path.exists(), f"{label} left cal/"


# ---------------------------------------------------------------------------
# …and the ruling is still honoured
# ---------------------------------------------------------------------------

def test_the_unmeasured_chart_itself_is_still_replaced(tmp_path):
    """The owner ruled the chart is an experiment and leaves nothing. It must
    still leave nothing — the fix must not become "keep everything"."""
    cal = _cal(tmp_path)
    _chart(cal)
    _strangers(cal)

    _rebuild(cal)

    for t in CHART_TAILS:
        assert not (cal.dir / f"{cal.stem}{t}").exists(), (
            f"{t} outlived the rebuild — an unmeasured chart is not kept")
    assert not cal.old_dir.exists(), (
        "an unmeasured calibration made a dated archive folder; Knut ruled at "
        "beta.148 that a dated folder holding no measurement "
        "'reads like a kept calibration and is not one'")


def test_a_sidecar_nobody_has_invented_yet_is_still_the_chart(tmp_path):
    """The property subtraction was chosen for. A stem test keeps it, because
    everything ChromIQ writes flat into cal/ is named after the calibration."""
    cal = _cal(tmp_path)
    _chart(cal)
    future = cal.dir / f"{cal.stem}.something-nobody-has-written-yet.json"
    future.write_text("{}", encoding="utf-8")

    assert future in cal.chart_files()
    _rebuild(cal)
    assert not future.exists(), (
        "a future sidecar named after the calibration was left behind, so the "
        "next chart sits beside the last one's metadata")


def test_a_cal_folder_of_only_the_persons_things_is_left_alone(tmp_path):
    """No chart, no measurement — nothing is being replaced, so nothing moves."""
    cal = _cal(tmp_path)
    made = _strangers(cal)

    done = cal.reset(stash=True)

    assert done.archive is None and done.stash is None
    assert not done, "reset() claimed it kept something over a folder of notes"
    for label, path in made.items():
        assert path.exists(), f"{label} was touched"


def test_a_build_that_fails_does_not_sweep_away_the_persons_things(tmp_path):
    """The restore path sweeps "what the unfinished build left". A stranger is
    not what the build left."""
    cal = _cal(tmp_path)
    _chart(cal, "OLD")
    made = _strangers(cal)

    done = cal.reset(stash=True)
    # the dead build got as far as a half-written page
    (cal.dir / f"{cal.stem}_09.tif").write_text("HALF", encoding="utf-8")
    cal.settle_chart_stash(done.stash, built=False)

    for label, path in made.items():
        assert path.exists(), f"{label} was swept away by the restore"
    assert (cal.dir / f"{cal.stem}.ti2").read_text(encoding="utf-8") == "OLD"
    assert not (cal.dir / f"{cal.stem}_09.tif").exists()


# ---------------------------------------------------------------------------
# The measured branch is UNTOUCHED
# ---------------------------------------------------------------------------

def test_the_measured_branch_archives_what_it_archived_before(tmp_path):
    """`_not_a_result()` IS the expression `chart_files()` used to be."""
    cal = _cal(tmp_path)
    _chart(cal)
    _strangers(cal)
    cal.ti3.write_text("a measurement", encoding="utf-8")

    before_fix = [p for p in cal.live_files()
                  if p not in set(cal.result_files())]
    assert cal._not_a_result() == before_fix
    assert sorted(cal.chart_files() + cal.stranger_files()) == before_fix


def test_a_measured_calibration_still_keeps_everything_in_its_archive(tmp_path):
    cal = _cal(tmp_path)
    _chart(cal)
    made = _strangers(cal)
    cal.ti3.write_text("a measurement", encoding="utf-8")
    cal.cal_path.write_text("the curves", encoding="utf-8")

    done = cal.reset(stash=True)

    assert done.archive is not None and done.stash is None
    archived = {p.name for p in done.archive.rglob("*")}
    assert f"{cal.stem}.ti3" in archived and f"{cal.stem}.cal" in archived
    for t in CHART_TAILS:
        assert f"{cal.stem}{t}" in archived
    # the person's FILES travel into the archive on this branch, as they did
    # before — nothing is lost, and this branch is deliberately unchanged
    for label, path in made.items():
        if path.is_dir() or path.name.startswith("."):
            assert path.exists(), f"{label} should have been left in cal/"
        else:
            assert path.name in archived, f"{label} is not in the archive"


# ---------------------------------------------------------------------------
# `is_ours` is a NAME test, not a pattern, and it folds accents
# ---------------------------------------------------------------------------

def test_a_decomposed_chart_file_is_still_recognised_as_its_own(tmp_path):
    """A project restored from an HFS+ volume spells its files decomposed while
    the folder name it is reached by is composed. Compared raw, the calibration
    would not recognise a single one of its own files."""
    cal = _cal(tmp_path, ud.normalize("NFC", "Müller-Baryta"))
    for t in CHART_TAILS:
        (cal.dir / ud.normalize("NFD", f"{cal.stem}{t}")).write_text(
            "chart", encoding="utf-8")
    note = cal.dir / "notes.txt"
    note.write_text("mine", encoding="utf-8")

    names = sorted(p.name for p in cal.chart_files())
    assert len(names) == len(CHART_TAILS), (
        f"the calibration did not recognise its own decomposed files: {names}")
    assert note not in cal.chart_files()


@pytest.mark.parametrize("name", ["Canon-Pro300 [test]", "Chart*A", "Chart?A",
                                  "Chart]v2["])
def test_a_name_holding_glob_syntax_is_a_name_not_a_pattern(tmp_path, name):
    """`is_ours` must never reach `fnmatch`: `Chart*A` would then adopt another
    project's file, and `Canon-Pro300 [test]` would disown its own chart."""
    cal = _cal(tmp_path, name)
    _chart(cal)
    stranger = cal.dir / "ChartXA-cal.ti2"      # what `Chart*A` would adopt
    stranger.write_text("another project's", encoding="utf-8")

    ours = sorted(p.name for p in cal.chart_files())
    assert len(ours) == len(CHART_TAILS), f"{name}: disowned its chart: {ours}"
    assert stranger.name not in ours, f"{name}: adopted a stranger's file"

    _rebuild(cal)
    assert stranger.exists(), f"{name}: another project's file was destroyed"


def test_meta_json_is_neither_a_stranger_nor_the_chart(tmp_path):
    """It carries no stem, so a stem test alone would call it a stranger.
    `live_files()` keeps it out of both lists, which is what makes the
    calibration's description survive a rebuild."""
    from core.file_manager import CalibrationMeta

    cal = _cal(tmp_path)
    _chart(cal)
    cal.save_meta(CalibrationMeta(description="my calibration"))

    assert cal.meta_path not in cal.chart_files()
    assert cal.meta_path not in cal.stranger_files()
    _rebuild(cal)
    assert cal.load_meta().description == "my calibration"
