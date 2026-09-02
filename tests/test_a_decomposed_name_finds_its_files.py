"""A project restored from an HFS+ volume still finds its chart.

WHAT WENT WRONG
    "Müller" is one character (U+00FC) when a Mac keyboard types it and two
    ("u" + U+0308) when the same name comes back off a Mac OS Extended
    volume: HFS+ stores every filename decomposed, and `shutil.copytree` back
    onto APFS keeps that spelling. Every Time Machine disk and most older
    external drives are Mac OS Extended, so this is the ordinary way a project
    comes home from a backup. (The zip route is clean: `ditto` and `unzip`
    both round-trip composed.)

    `Path.exists()` did not care, because APFS is normalisation-INSENSITIVE:
    `(run.dir / "Müller.ti2").exists()` was True either way. `Path.glob()`
    does care, because it lists the directory and matches in Python, where the
    two spellings are simply different strings. So `chart_ti2.exists()` said
    True while `chart_tiffs()` returned nothing, the Chart tab read
    "No chart for this profile run yet" with four page bitmaps sitting in the
    folder, and Print Current Page was greyed out. Both sentences on screen
    were untrue.

    And following the advice made it worse: `reset_chart_artefacts(stash=True)`
    archived the `.ti1` and the `.ti3` correctly (explicit paths) and archived
    no page TIFFs at all, so the next build wrote four more beside the four it
    could not see. Two charts under one name, and the sheets already printed
    belonged to the invisible one.

THE FIX
    `core.file_manager.files_matching` compares the composed spelling of both
    sides, and every stem pattern in ChromIQ goes through it. It renames
    nothing: on Linux and Windows the filesystem is normalisation-preserving
    and case/spelling-sensitive, so the two spellings are two real files that
    may both exist, and normalising on the way in would have to overwrite one
    with the other.

WHAT THESE TESTS PROVE
    That the decomposed spelling is found; that a name normalisation does not
    change takes exactly the path it took before; that a mixed folder returns
    all of it; and that two genuinely different files are both returned rather
    than one silently standing in for the other.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import unicodedata as ud
from pathlib import Path

import pytest

from core.file_manager import FileManager, Project, Run, files_matching, nfc
from core.settings import AppSettings

NAME = ud.normalize("NFC", "Müller-Prüfdruck")
NFD = ud.normalize("NFD", "Müller-Prüfdruck")
CHART_EXTS = (".ti1", ".ti2", ".cht", ".channels.json", ".ti3")


def _decomposed_run(folder: Path, stem: str = NFD, pages: int = 4) -> Path:
    """A run folder whose every chart file is spelled decomposed."""
    folder.mkdir(parents=True, exist_ok=True)
    for ext in CHART_EXTS:
        (folder / f"{stem}{ext}").write_text("x", encoding="utf-8")
    for i in range(1, pages + 1):
        (folder / f"{stem}_{i:02d}.tif").write_text("x", encoding="utf-8")
    return folder


# ---------------------------------------------------------------------------
# The mechanism, stated as facts rather than assumed
# ---------------------------------------------------------------------------

def test_the_two_spellings_are_different_strings_and_the_same_file(tmp_path):
    """Everything below rests on this pair, so it is asserted, not assumed."""
    assert NAME != NFD                      # different strings…
    assert nfc(NFD) == NAME                 # …one composed spelling
    (tmp_path / f"{NFD}.ti2").write_text("x", encoding="utf-8")
    if os.uname().sysname == "Darwin":      # APFS/HFS+ fold the two spellings
        assert (tmp_path / f"{NAME}.ti2").exists(), (
            "the premise of the bug: existence is normalisation-insensitive")
    # …and a glob is not, on any platform.
    assert list(tmp_path.glob(f"{NAME}*.ti2")) == [], (
        "Path.glob matches in Python, so it cannot see the other spelling")


def test_files_matching_finds_the_decomposed_spelling(tmp_path):
    _decomposed_run(tmp_path)
    assert len(files_matching(tmp_path, f"{NAME}*.tif")) == 4
    assert len(files_matching(tmp_path, f"{NAME}*.ti2")) == 1
    # …and from the other direction too: a composed folder found by a
    # decomposed pattern, which is what a project whose FOLDER came off HFS+
    # while its files were rewritten by ChromIQ looks like.
    other = tmp_path / "composed"
    _decomposed_run(other, stem=NAME)
    assert len(files_matching(other, f"{NFD}*.tif")) == 4


def test_a_mixed_folder_returns_all_of_it(tmp_path):
    """ChromIQ writing one new page beside four restored ones.

    The composed page and the decomposed pages are all pages of this chart,
    and a listing that returned four of five is how the run ends up holding
    two charts under one name.
    """
    _decomposed_run(tmp_path)
    (tmp_path / f"{NAME}_05.tif").write_text("x", encoding="utf-8")
    got = files_matching(tmp_path, f"{NAME}*.tif")
    assert len(got) == 5, [p.name for p in got]
    # Every returned path opens the file it names, whatever its spelling.
    assert all(p.is_file() for p in got)


def test_two_genuinely_different_files_do_not_collide(tmp_path):
    """The Linux/Windows case: nothing is renamed, so nothing is destroyed.

    On a normalisation-preserving and -sensitive filesystem the two spellings
    are two files. Both are returned; neither is overwritten by the other, and
    the bytes of each are still its own. (On macOS the filesystem folds them
    into one file, so there is only ever one to return — which is checked too,
    because "one file" and "one file lost" must not look alike.)
    """
    a = tmp_path / f"{NAME}_01.tif"
    b = tmp_path / f"{NFD}_01.tif"
    a.write_text("composed", encoding="utf-8")
    b.write_text("decomposed", encoding="utf-8")
    on_disk = sorted(os.listdir(tmp_path))
    got = files_matching(tmp_path, f"{NAME}_*.tif")
    assert len(got) == len(on_disk), (
        "every file on disk is returned, and no extra")
    for p in got:
        assert p.read_text(encoding="utf-8") in ("composed", "decomposed")
    if len(on_disk) == 2:                    # a sensitive filesystem
        assert {p.read_text(encoding="utf-8") for p in got} == {
            "composed", "decomposed"}, "one file stood in for the other"


# ---------------------------------------------------------------------------
# The overwhelming majority: a name normalisation does not change
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("stem", [
    "Canon-PRO-300", "chart", "A4_480p", "Demo-Full-RGB",
    "Pro.1000-Photo", "x", "Test-2026-08-24",
])
def test_an_unaffected_name_takes_exactly_the_path_it_took_before(tmp_path, stem):
    """No accents, no change: same matches, same order as `Path.glob`."""
    assert nfc(stem) == stem                 # nothing to normalise
    for i in range(1, 4):
        (tmp_path / f"{stem}_{i:02d}.tif").write_text("x", encoding="utf-8")
    (tmp_path / f"{stem}.ti2").write_text("x", encoding="utf-8")
    (tmp_path / "unrelated.tif").write_text("x", encoding="utf-8")
    for pattern in (f"{stem}_*.tif", f"{stem}*.tif", f"{stem}*", "*.ti2"):
        assert files_matching(tmp_path, pattern) == sorted(
            tmp_path.glob(pattern)), pattern


def test_an_accented_name_that_is_already_composed_is_unchanged_too(tmp_path):
    """The normal Mac case: ChromIQ wrote it, so it is already composed."""
    _decomposed_run(tmp_path, stem=NAME)
    assert files_matching(tmp_path, f"{NAME}*.tif") == sorted(
        tmp_path.glob(f"{NAME}*.tif"))


def test_a_missing_folder_is_no_files_not_an_exception(tmp_path):
    assert files_matching(tmp_path / "not-here", "*.tif") == []
    assert files_matching(None, "*.tif") == []
    # A file where a folder was expected is the same answer.
    f = tmp_path / "a-file"
    f.write_text("x", encoding="utf-8")
    assert files_matching(f, "*.tif") == []


def test_a_multi_segment_pattern_is_refused_rather_than_matching_less(tmp_path):
    """`files_matching` takes one path component. Quietly matching nothing
    would be a listing that shrinks without saying so."""
    with pytest.raises(ValueError):
        files_matching(tmp_path, "chart/*.tif")


def test_case_sensitivity_is_not_changed(tmp_path):
    """The only thing this helper changes anywhere is the accent spelling.

    Callers pass `*.tif`/`*.TIF` pairs because `Path.glob` is case-sensitive
    on POSIX; folding case here would make those pairs return each file twice
    and, on Linux, make two real files look like one.
    """
    (tmp_path / "chart_01.TIF").write_text("x", encoding="utf-8")
    assert files_matching(tmp_path, "chart_*.tif") == sorted(
        tmp_path.glob("chart_*.tif"))


# ---------------------------------------------------------------------------
# Through the real Run / Project layer
# ---------------------------------------------------------------------------

def test_run_chart_tiffs_finds_a_decomposed_chart(tmp_path):
    """The method the Chart tab, the Print tab and the Duplicate button ask.

    This is the on-screen fault: `chart_ti2.exists()` True, `chart_tiffs()`
    empty, "No chart for this profile run yet" with four pages in the folder.
    """
    run_dir = tmp_path / NAME / "runs" / "run1"
    _decomposed_run(run_dir)
    run = Run.for_dir(run_dir)
    assert run.stem == NAME
    assert run.chart_ti2.exists()
    assert len(run.chart_tiffs()) == 4, [p.name for p in run.chart_tiffs()]


def test_reset_chart_artefacts_archives_the_pages_it_could_not_see(tmp_path):
    """"Just create it again" must not leave four invisible bitmaps behind.

    Archived, never deleted: this is the code that protects somebody's chart.
    """
    run_dir = tmp_path / NAME / "runs" / "run1"
    _decomposed_run(run_dir)
    run = Run.for_dir(run_dir)
    stash = run.reset_chart_artefacts(stash=True)
    left = [p.name for p in run_dir.iterdir()
            if p.is_file() and p.name.lower().endswith(".tif")]
    assert left == [], f"pages left invisible in the run folder: {left}"
    assert stash is not None and stash.is_dir()
    archived = [p.name for p in stash.rglob("*")
                if p.is_file() and p.name.lower().endswith(".tif")]
    assert len(archived) == 4, archived


def test_the_verification_guard_protects_the_pages_it_promises(tmp_path):
    """`_clear_verify_chart_files` archives the verify chart, all of it.

    A guard that silently protects less than its docstring promises is worse
    than no guard: it is a promise somebody relies on.
    """
    run_dir = tmp_path / NAME / "runs" / "run1"
    run_dir.mkdir(parents=True)
    vdir = run_dir / "verifications"
    vdir.mkdir()
    vstem = ud.normalize("NFD", f"{NAME}-verify")
    for ext in (".ti1", ".ti2", ".cie"):
        (vdir / f"{vstem}{ext}").write_text("x", encoding="utf-8")
    for i in (1, 2):
        (vdir / f"{vstem}_{i:02d}.tif").write_text("x", encoding="utf-8")
    run = Run.for_dir(run_dir)
    assert len(run.verify_chart_tiffs()) == 2
    run._clear_verify_chart_files()
    left = [p.name for p in vdir.iterdir() if p.is_file()]
    assert left == [], f"the guard left files at risk: {left}"
    archived = [p.name for p in run.verifications_old_dir.rglob("*")
                if p.is_file()]
    assert len(archived) == 5, archived


def test_duplicate_run_copies_the_pages_as_well_as_the_metadata(tmp_path):
    """A duplicate that carries the chart's `.ti2` and none of its pages makes
    a run that contradicts itself."""
    proj = Project.create(tmp_path / NAME, NAME)
    run = proj.new_run()
    _decomposed_run(run.dir)
    proj.save_manifest()
    plan = proj.duplicate_run_plan(run)
    chart = next(files for group, files, _ in plan if group == "chart")
    assert len([p for p in chart if p.suffix.lower() == ".tif"]) == 4, (
        [p.name for p in chart])


def test_the_project_rename_walk_carries_the_accented_files(tmp_path):
    """A rename that skips every accented artefact leaves the chart behind
    under the old name while the project moves on."""
    new_name = ud.normalize("NFC", "Schäfer-Prüfdruck")
    proj = Project.create(tmp_path / NAME, NAME)
    run = proj.new_run()
    _decomposed_run(run.dir)
    proj.save_manifest()
    # `Project.rename` fixes up the CONTENTS; moving the folder is the
    # caller's job and has to happen first (its own docstring says so).
    shutil.move(str(tmp_path / NAME), str(tmp_path / new_name))
    proj = Project.load(tmp_path / new_name)
    proj.rename(new_name)

    new_run = proj.current_run()
    left_behind = [q.name for q in new_run.dir.iterdir()
                   if q.is_file() and nfc(q.name).startswith(NAME)]
    assert left_behind == [], left_behind
    assert new_run.stem == new_name
    assert len(new_run.chart_tiffs()) == 4, [q.name for q in new_run.dir.iterdir()]


# ---------------------------------------------------------------------------
# The route the bug actually travels, with a real HFS+ volume
# ---------------------------------------------------------------------------

@pytest.mark.skipif(os.uname().sysname != "Darwin", reason="hdiutil is macOS")
def test_a_real_hfs_plus_round_trip_produces_the_decomposed_spelling(tmp_path):
    """The measurement behind the whole fix, done for real once.

    `unicodedata.normalize('NFD', name)` is the cheap way to build the case,
    and it is what every test above uses. This one proves the cheap version
    describes the real one: a 20 MB Mac OS Extended disk image, a copy on and
    a copy off, and the names come back decomposed.
    """
    dmg = tmp_path / "hfs.dmg"
    mnt = tmp_path / "mnt"
    made = subprocess.run(
        ["hdiutil", "create", "-size", "20m", "-fs", "HFS+", "-volname",
         "CHROMIQTEST", str(dmg), "-quiet"], timeout=180,
        capture_output=True, text=True, encoding="utf-8")
    if made.returncode != 0:                 # no disk-image support on this host
        pytest.skip(f"hdiutil create failed: {made.stderr.strip()[:120]}")
    att = subprocess.run(
        ["hdiutil", "attach", str(dmg), "-mountpoint", str(mnt), "-quiet",
         "-nobrowse"], timeout=180, capture_output=True, text=True, encoding="utf-8")
    if att.returncode != 0:
        pytest.skip(f"hdiutil attach failed: {att.stderr.strip()[:120]}")
    try:
        src = tmp_path / "src" / NAME
        _decomposed_run(src, stem=NAME)      # written COMPOSED, as ChromIQ does
        shutil.copytree(str(src), str(mnt / NAME))
        assert any(ud.normalize("NFD", n) == n != ud.normalize("NFC", n)
                   for n in os.listdir(mnt / NAME)), "HFS+ stores decomposed"
        back = tmp_path / "back" / NAME
        shutil.copytree(str(mnt / NAME), str(back))
    finally:
        subprocess.run(["hdiutil", "detach", str(mnt), "-quiet"], timeout=180,
                       capture_output=True)
    assert any(ud.normalize("NFD", n) == n != ud.normalize("NFC", n)
               for n in os.listdir(back)), (
        "copytree back onto APFS keeps the decomposed spelling")
    # …and the app finds its chart in it.
    assert len(files_matching(back, f"{NAME}*.tif")) == 4


def test_the_app_finds_the_chart_after_that_round_trip(tmp_path, monkeypatch):
    """End to end through `FileManager`, the way a launch reaches it.

    The folder is built decomposed directly (the HFS+ test above proves that
    is what a round trip leaves); what is exercised here is the app asking for
    it by the COMPOSED name it holds in its manifest and its name box.
    """
    monkeypatch.setenv("CHROMIQ_SETTINGS_FILE", str(tmp_path / "s.ini"))
    work = tmp_path / "work"
    work.mkdir()
    proj = Project.create(work / NAME, NAME)
    run = proj.new_run()
    _decomposed_run(run.dir)                 # decomposed files, composed folder
    proj.save_manifest()

    settings = AppSettings()
    settings.set("custom_output_path", str(work))
    fm = FileManager(settings)
    fm.set_target_name(NAME)
    found = fm.project().current_run()
    assert found.chart_ti2.exists()
    assert len(found.chart_tiffs()) == 4, [p.name for p in found.chart_tiffs()]
