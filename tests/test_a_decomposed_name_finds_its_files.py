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
import sys
import unicodedata as ud
from pathlib import Path

import pytest

from core.file_manager import FileManager, Project, Run, files_matching, nfc
from core.settings import AppSettings

#: `os.uname()` DOES NOT EXIST ON WINDOWS, and the skipif below is evaluated
#: while the decorator is built — at import — so asking that question the old
#: way did not skip a macOS-only test, it made the whole FILE fail to collect
#: with `AttributeError: module 'os' has no attribute 'uname'`. `sys.platform`
#: is defined on every platform Python runs on, which is the only reason a
#: guard against a platform may use it.
IS_MACOS = sys.platform == "darwin"

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
    if IS_MACOS:                            # APFS/HFS+ fold the two spellings
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
    if IS_MACOS:
        # The PREMISE, not the fix: only a normalisation-INSENSITIVE volume
        # answers True here, which is exactly why the bug was invisible on a
        # Mac. NTFS is normalisation-sensitive, so on Windows the composed
        # spelling simply is not there — and `files_matching` below is what
        # has to find it on every platform.
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

@pytest.mark.skipif(not IS_MACOS, reason="hdiutil is macOS")
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
    if IS_MACOS:                             # the premise — see above
        assert found.chart_ti2.exists()
    assert len(found.chart_tiffs()) == 4, [p.name for p in found.chart_tiffs()]


# ===========================================================================
# B8-61 — THE NAMED ARTEFACT, which a listing cannot answer
# ===========================================================================
#
# Everything above is about a LISTING: "which files in this folder are pages of
# that chart". `files_matching` answers that on the composed spelling of both
# sides, and has done since the HFS+ round trip was measured.
#
# `<stem>.ti2` is not a listing. It is one file, asked for by name, through
# `Path.exists()` — and `Path.exists()` is the FILESYSTEM's answer, so it
# differs by filesystem. APFS/HFS+ fold the two spellings, which is why the
# tests above guard their premise behind `IS_MACOS`. **NTFS does not**, and
# neither does an ordinary Linux volume: measured on a Windows 11 ARM64 NTFS
# machine, `run.chart_ti2.exists()` answered False with the chart in the folder,
# and `ui/main_window.py:2238` then silently used the `.ti1` instead — a
# different chart, with no message of any kind.
#
# `core.file_manager.resolve_existing` is the fix, and every `Run` /
# `Calibration` / `Verification` artefact goes through it. These tests are
# written so they MEAN SOMETHING ON WINDOWS: not one is guarded by platform, and
# on a normalisation-insensitive volume each still asserts a true thing (it
# passes for the filesystem's reason rather than the resolver's).


def _volume_folds_spellings(tmp_path) -> bool:
    """Whether THIS volume answers `exists()` across the two spellings.

    Measured, never assumed from `sys.platform`: an APFS volume folds, an NTFS
    one does not, and ChromIQ runs on external volumes of both kinds.
    """
    probe = tmp_path / f"{NFD}.probe"
    probe.write_text("x", encoding="utf-8")
    try:
        return (tmp_path / f"{NAME}.probe").exists()
    finally:
        probe.unlink()


def _run_at(root: Path, folder_name: str) -> Run:
    """A `Run` under `<root>/<folder_name>/runs/run1`, folder created."""
    d = root / folder_name / "runs" / "run1"
    d.mkdir(parents=True, exist_ok=True)
    return Run.for_dir(d)


def test_a_named_artefact_resolves_to_the_spelling_that_is_on_disk(tmp_path):
    """The fault, at the accessor: a composed stem and a decomposed file.

    This is a project ChromIQ created (composed folder) into which a chart was
    restored from a Mac OS Extended backup (decomposed files) — the ordinary
    way a chart comes home, and the shape measured on NTFS.
    """
    run = _run_at(tmp_path, NAME)                                      # stem NFC
    (run.dir / f"{NFD}.ti2").write_text("the .ti2", encoding="utf-8")  # file NFD
    assert run.stem == NAME

    assert run.chart_ti2.exists(), (
        "the chart is in the folder and the app cannot see it")
    assert run.chart_ti2.is_file()
    # AND IT OPENS. An accessor that says "yes it is there" and hands back a
    # spelling `open()` refuses would move the failure, not fix it.
    assert run.chart_ti2.read_text(encoding="utf-8") == "the .ti2"


def test_the_mirror_shape_resolves_too(tmp_path):
    """A DECOMPOSED folder holding files ChromIQ or a zip wrote composed.

    The stem comes from the folder, so this is the same fault with the two
    spellings swapped — the shape a Windows user hits after copying a project
    folder off a Mac and importing a chart into it.
    """
    run = _run_at(tmp_path, NFD)
    (run.dir / f"{NAME}.ti2").write_text("the .ti2", encoding="utf-8")
    assert run.stem == NFD
    assert run.chart_ti2.read_text(encoding="utf-8") == "the .ti2"


def test_the_ti1_is_not_quietly_substituted_for_a_ti2_that_is_there(tmp_path):
    """`ui/main_window.py:2238`, which is why this is a data fault:

        chart = run.chart_ti2 if run.chart_ti2.exists() else run.chart_ti1

    It does not refuse and it does not warn. On NTFS the `.ti2` "did not
    exist", so the user got the `.ti1` — a different, unlaid-out chart —
    presented as the current one. Both files are put on disk here, spelled
    differently, so a substitution is DETECTABLE rather than inferred.
    """
    run = _run_at(tmp_path, NFD)
    (run.dir / f"{NFD}.ti1").write_text("the .ti1 — the WRONG chart",
                                        encoding="utf-8")
    (run.dir / f"{NAME}.ti2").write_text("the .ti2 — the right chart",
                                         encoding="utf-8")

    chart = run.chart_ti2 if run.chart_ti2.exists() else run.chart_ti1
    assert chart.name.endswith(".ti2"), (
        f"the app used {chart.name!r} — a different chart, silently")
    assert chart.read_text(encoding="utf-8").endswith("the right chart")


def test_the_exact_spelling_always_wins_when_both_are_on_disk(tmp_path):
    """Two files, two spellings, one requested — nothing is swapped.

    On a normalisation-sensitive volume these are two genuinely different
    files. The resolver asks for the path it was GIVEN first, so the answer is
    the one the caller named, exactly as before the fix.
    """
    run = _run_at(tmp_path, NAME)
    (run.dir / f"{NAME}.ti2").write_text("composed", encoding="utf-8")
    (run.dir / f"{NFD}.ti2").write_text("decomposed", encoding="utf-8")
    on_disk = [n for n in os.listdir(run.dir) if n.endswith(".ti2")]
    assert run.chart_ti2.read_text(encoding="utf-8") == "composed", (
        f"the requested spelling must win; {len(on_disk)} .ti2 on disk")


def test_an_absent_artefact_keeps_its_composed_name_so_a_writer_creates_that(
        tmp_path):
    """Nothing on disk: the path comes back untouched.

    That is what keeps ChromIQ writing the composed spelling on a fresh run —
    the fix must not become "normalise names at creation time", which would
    leave every project already on disk spelled the old way.
    """
    run = _run_at(tmp_path, NAME)
    assert run.chart_ti2 == run.dir / f"{NAME}.ti2"
    assert run.chart_ti1 == run.dir / f"{NAME}.ti1"
    assert run.profile_icc == run.dir / f"{NAME}.icc"


def test_a_rewrite_overwrites_the_chart_instead_of_laying_a_second_beside_it(
        tmp_path):
    """The write side, and the reason resolving beats "check at the call site".

    Writing through an unresolved composed path onto a folder holding the
    decomposed one leaves TWO .ti2 files with names that look identical on
    screen — "two charts under one name", the state `files_matching`'s
    docstring was written about.
    """
    run = _run_at(tmp_path, NAME)
    (run.dir / f"{NFD}.ti2").write_text("v1", encoding="utf-8")
    run.chart_ti2.write_text("v2", encoding="utf-8")
    ti2s = [n for n in os.listdir(run.dir) if n.endswith(".ti2")]
    assert len(ti2s) == 1, f"a second chart was laid beside the first: {ti2s}"
    assert run.chart_ti2.read_text(encoding="utf-8") == "v2"


def test_case_is_never_folded_by_the_resolver(tmp_path):
    """Accents only. Two names differing by case are two files on a
    case-sensitive volume, and folding them here would make one stand in for
    the other — the fault `_existing_folder_spelling` is careful to avoid for
    folders, for the same reason."""
    from core.file_manager import resolve_existing

    (tmp_path / "Chart.ti2").write_text("upper", encoding="utf-8")
    got = resolve_existing(tmp_path / "chart.ti2")
    assert got.name == "chart.ti2", (
        "the resolver adopted another case; only the accent spelling is its "
        "business")


def test_an_ascii_name_never_lists_the_directory(tmp_path, monkeypatch):
    """The cost guarantee, asserted rather than claimed.

    No ASCII character has a canonical decomposition, so an ASCII name has no
    other spelling to look for. Every project name in this suite, and the
    overwhelming majority of real ones, takes one `stat` and stops — which is
    exactly what it cost before the fix.
    """
    import core.file_manager as fmod

    def _explode(*a, **k):
        raise AssertionError("scandir called for an ASCII name")

    monkeypatch.setattr(fmod.os, "scandir", _explode)
    missing = tmp_path / "Canon-PRO-300.ti2"
    assert fmod.resolve_existing(missing) == missing


def test_a_hit_never_lists_the_directory_either(tmp_path, monkeypatch):
    """An accented name whose exact spelling IS on disk — the macOS case, and
    every chart ChromIQ wrote itself — also stops at the first `stat`."""
    import core.file_manager as fmod

    (tmp_path / f"{NAME}.ti2").write_text("x", encoding="utf-8")

    def _explode(*a, **k):
        raise AssertionError("scandir called when the exact spelling was there")

    monkeypatch.setattr(fmod.os, "scandir", _explode)
    assert fmod.resolve_existing(tmp_path / f"{NAME}.ti2").is_file()


def test_an_unreadable_parent_is_the_path_unchanged_not_an_exception(tmp_path):
    """A resolver that raises where `exists()` used to answer False would turn
    a missing chart into a crash."""
    from core.file_manager import resolve_existing

    p = tmp_path / "nowhere" / f"{NAME}.ti2"
    assert resolve_existing(p) == p
    a_file = tmp_path / "a-file"
    a_file.write_text("x", encoding="utf-8")
    q = a_file / f"{NAME}.ti2"
    assert resolve_existing(q) == q


def test_the_whole_chart_chain_and_the_verify_chart_resolve(tmp_path):
    """Not just the `.ti2`. A run whose `.ti2` is found and whose `.cht` is not
    is a run that half works — scanin would refuse a chart the tab shows."""
    run = _run_at(tmp_path, NAME)
    for ext in (".ti1", ".ti2", ".cht", ".ps", ".channels.json", ".ti3", ".icc"):
        (run.dir / f"{NFD}{ext}").write_text(ext, encoding="utf-8")
    for got in (run.chart_ti1, run.chart_ti2, run.chart_cht, run.chart_ps,
                run.chart_channels_json, run.measurement_ti3, run.profile_icc):
        assert got.is_file(), f"{got.name} not found"

    vdir = run.verifications_dir
    vdir.mkdir(parents=True)
    vstem = ud.normalize("NFD", run.verify_stem)
    for ext in (".ti1", ".ti2", ".cht"):
        (vdir / f"{vstem}{ext}").write_text(ext, encoding="utf-8")
    assert run.has_verify_chart(), "the verify chart is there and unseen"
    assert run.verify_chart_ti2.is_file() and run.verify_chart_ti1.is_file()
    assert run.verify_chart_cht.is_file()


def test_a_calibration_finds_its_own_restored_chart(tmp_path):
    """`cal/` is stem-named too, and a calibration comes home from the same
    backup as the project it belongs to."""
    proj = Project.create(tmp_path / NAME, NAME)
    cal = proj.calibration
    cal.dir.mkdir(parents=True, exist_ok=True)
    cstem = ud.normalize("NFD", cal.stem)
    for ext in (".ti1", ".ti2", ".ti3", ".cal", ".icc"):
        (cal.dir / f"{cstem}{ext}").write_text(ext, encoding="utf-8")
    for got in (cal.ti1, cal.ti2, cal.ti3, cal.cal_path, cal.icc):
        assert got.is_file(), f"{got.name} not found"


def test_adopting_a_restored_chart_as_a_verify_chart_moves_it(tmp_path):
    """The guard and the move have to agree.

    `adopt_run_chart_as_verify` clears the old verify chart and THEN moves the
    new one. Its guard is `chart_ti2.exists()`; the move was a raw f-string. A
    guard that now passes over a move that still cannot see the files would
    clear a chart for a move that moves nothing.
    """
    run = _run_at(tmp_path, NAME)
    for ext in (".ti1", ".ti2", ".cht"):
        (run.dir / f"{NFD}{ext}").write_text(ext, encoding="utf-8")
    moved = run.adopt_run_chart_as_verify()
    assert moved is not None and moved.is_file(), (
        "the guard passed and the move moved nothing")
    assert moved.read_text(encoding="utf-8") == ".ti2"
    assert run.verify_chart_ti1.is_file() and run.verify_chart_cht.is_file()
    left = [n for n in os.listdir(run.dir)
            if n.endswith((".ti1", ".ti2", ".cht"))]
    assert left == [], f"left behind under the profiling stem: {left}"


def test_the_volume_this_ran_on_is_recorded_rather_than_assumed(tmp_path):
    """Not an assertion about the fix — a RECORD of which filesystem ran it.

    On a folding volume the tests above pass for the filesystem's reason; on a
    sensitive one they pass for the resolver's. Which it was is worth knowing
    when a failure is read months later, so it is measured and printed rather
    than inferred from `sys.platform`.
    """
    folds = _volume_folds_spellings(tmp_path)
    if IS_MACOS:
        assert folds, "a Mac volume that does not fold spellings — say so"
    print(f"\nnormalisation-insensitive volume: {folds} "
          f"(sys.platform={sys.platform})")


# ---------------------------------------------------------------------------
# Through the real UI resolution — the path `ui/main_window.py:2238` takes
# ---------------------------------------------------------------------------

def test_the_ui_resolves_the_restored_chart_and_not_its_ti1(cal_settings, qapp):
    """`TabChart._resolve_target_chart`, which is what `:2238` asks.

    The offscreen GUARD for the on-screen proof: an NFD-named project whose
    `.ti2` is spelled composed and whose `.ti1` is spelled like the folder, so
    the substitution has somewhere to go. A `MainWindow` cannot be built under
    `QT_QPA_PLATFORM=offscreen` without segfaulting, so this drives the real
    `TabChart` + `FileManager` through the same duck-typed host
    `tests/test_patch_set_editor_opens_the_selected_target.py` uses.
    """
    from core.argyll_runner import ArgyllRunner
    from core.measurement_target import RUN_TYPE_PROFILING
    from ui.main_window import MainWindow
    from ui.measurement_target_bar import MeasurementTargetController
    from ui.tabs.tab_chart import TabChart

    class _Host:
        def __init__(self, fm, tab):
            self._file_mgr, self._tab_chart = fm, tab

    fm = FileManager(cal_settings)
    fm.open_project_at(Path(cal_settings.get("custom_output_path")) / NFD)
    proj = fm.project()
    run = proj.current_run()
    assert run.stem == NFD, run.stem

    (run.dir / f"{NFD}.ti1").write_text("the .ti1 — the WRONG chart",
                                        encoding="utf-8")
    (run.dir / f"{NAME}.ti2").write_text("the .ti2 — the right chart",
                                         encoding="utf-8")
    (run.dir / f"{NAME}_01.tif").write_text("page", encoding="utf-8")

    tab = TabChart(ArgyllRunner(cal_settings), fm, cal_settings)
    ctl = MeasurementTargetController(fm)
    tab.set_target_controller(ctl)
    ctl.set_run_type(RUN_TYPE_PROFILING)
    ctl.set_profile_run(run.id)

    resolved = tab._resolve_target_chart()
    assert resolved is not None, (
        "the tab found no chart at all — 'No chart for this profile run yet' "
        "with the chart in the folder")
    ti2, tiffs, ti1 = resolved
    chart = ti2 if ti2.exists() else ti1          # the `:2238` expression
    assert chart.read_text(encoding="utf-8").endswith("the right chart"), (
        f"the patch cube would draw {chart.name!r}")
    assert len(tiffs) == 1
    assert MainWindow._current_chart_ti2(_Host(fm, tab)) == ti2


# ===========================================================================
# ROUND 2 — WHAT THE FIRST FIX ACTIVATED
# ===========================================================================
#
# THE SHAPE OF THE WHOLE SECTION, because it is one fault wearing four hats:
# **the guard learned to resolve and the work behind it did not.** Before
# `resolve_existing`, `chart_ti2.exists()` was False on NTFS for a restored
# project, so everything behind that guard was DEAD CODE. Making the guard
# truthful runs that code for the first time — and it was still building its own
# names with f-strings and asking bare `.exists()`, so it acts on files that are
# not there. Fixing a broken guard is exactly when previously-unreachable code
# runs for the first time, and it is the moment to go and read it.
#
# Two of these shipped in round 1 and were found by review, not by me.


def _restored_chart(run: Run, *exts: str, pages: int = 0,
                    single_page: bool = False) -> None:
    """A chart in *run* spelled the way a Mac OS Extended backup hands it back."""
    for ext in exts:
        (run.dir / f"{NFD}{ext}").write_text(f"OLD{ext}", encoding="utf-8")
    for i in range(1, pages + 1):
        (run.dir / f"{NFD}_{i:02d}.tif").write_text("page", encoding="utf-8")
    if single_page:
        (run.dir / f"{NFD}.tif").write_text("the only page", encoding="utf-8")


# ---- DEFECT 1: the single page that stayed behind -------------------------

def test_a_single_page_verify_chart_takes_its_page_with_it(tmp_path):
    """`adopt_run_chart_as_verify` moved the chart and ORPHANED its only page.

    A one-page chart's TIFF is `<stem>.tif` with no `_NN`, so the `_*.tif` glob
    misses it and a second block used to catch it — built from a raw f-string,
    which finds nothing when the file came off an HFS+ volume. On master the
    outer guard was False and the method did nothing at all; the moment the
    guard started resolving, this ran for the first time, moved the chart into
    `verifications/` and left the page in the run root.

    Two things go wrong at once, and both are asserted: the verify chart has no
    page and never previews (Knut #130, "Run type = Verification shows no
    preview"), and the run root is left holding a page with no `.ti2` — the very
    contradiction this whole change removes everywhere else.
    """
    run = _run_at(tmp_path, NAME)
    _restored_chart(run, ".ti1", ".ti2", ".cht", single_page=True)

    moved = run.adopt_run_chart_as_verify()
    assert moved is not None and moved.is_file()

    assert len(run.verify_chart_tiffs()) == 1, (
        "the verify chart has no page bitmap, so it never previews")
    left = [p.name for p in run.dir.iterdir()
            if p.is_file() and p.name.lower().endswith(".tif")]
    assert left == [], f"the page was orphaned in the run root: {left}"
    assert run.chart_tiffs() == [] and not run.chart_ti2.exists(), (
        "the run root is left in the 'pages but no chart' state")


def test_the_multi_page_case_still_works_and_is_not_double_moved(tmp_path):
    """The `_NN` pages kept working throughout; merging the two blocks into one
    `stem_files` call must not have changed that, or moved anything twice."""
    run = _run_at(tmp_path, NAME)
    _restored_chart(run, ".ti1", ".ti2", pages=3)
    run.adopt_run_chart_as_verify()
    assert len(run.verify_chart_tiffs()) == 3
    assert [p.name for p in run.dir.iterdir() if p.is_file()] == []


# ---- DEFECT 2: the chart chain a Replace did not archive ------------------

def test_a_replace_archives_the_whole_restored_chart_chain(tmp_path):
    """`workflow.chart_import.archive_run_for_replace`, and the worst of the two.

    The `.ti3`, `.icc` and the page TIFFs went through resolving accessors; the
    `.ti1`, `.ti2` and every `_CHART_EXTS` sidecar were raw f-strings. So a
    Replace archived half a chart, the new one landed beside what was left, and
    `run.chart_cht` — which resolves — handed the scanner the OLD chart's
    recognition file for the NEW `.ti2`. A silent wrong result, and "two charts
    under one name" produced by the very commit that claims to prevent it.
    """
    from workflow.chart_import import archive_run_for_replace

    run = _run_at(tmp_path, NAME)
    _restored_chart(run, ".ti1", ".ti2", ".cht", ".channels.json", ".cie",
                    pages=1)
    (run.dir / f"{NFD}.ti3").write_text("OLD ti3", encoding="utf-8")

    archive = archive_run_for_replace(run, verification=False)
    assert archive is not None
    left = sorted(p.name for p in run.dir.iterdir() if p.is_file())
    assert left == [], f"the Replace left the old chart in place: {left}"

    archived = sorted(p.suffix for p in archive.rglob("*") if p.is_file())
    for ext in (".ti1", ".ti2", ".cht", ".cie", ".ti3", ".tif"):
        assert ext in archived, f"{ext} was not archived: {archived}"

    # …and now the new chart is written, composed, as ChromIQ writes it.
    run.chart_ti2.write_text("NEW ti2", encoding="utf-8")
    assert not run.chart_cht.exists(), (
        "chart_cht answers with the OLD chart's recognition file for the NEW "
        ".ti2 — the scanner would read the wrong chart and say nothing")


def test_a_regenerate_does_not_leave_a_second_chart_under_one_name(tmp_path):
    """`reset_chart_artefacts`, the same shape inside `Run`.

    `partial_ti3` beside these already resolved, so a restored run archived the
    engine partial and left the measurement it belongs to — and the drop loop
    could not see the chart either, so the next build wrote a second one.
    """
    run = _run_at(tmp_path, NAME)
    _restored_chart(run, ".ti1", ".ti2", ".cht", ".channels.json", pages=2)
    (run.dir / f"{NFD}.ti3").write_text("the measurement", encoding="utf-8")
    (run.dir / f"{NFD}.icc").write_text("the profile", encoding="utf-8")

    run.reset_chart_artefacts()
    left = sorted(p.name for p in run.dir.iterdir() if p.is_file())
    assert left == [], f"a regenerate would write beside these: {left}"
    old = list((run.dir / "old").rglob("*")) if (run.dir / "old").is_dir() else []
    kept = sorted(p.suffix for p in old if p.is_file())
    assert ".ti3" in kept and ".icc" in kept, (
        f"the measurement and the profile must be archived, not dropped: {kept}")


# ---- A-1: the resolver and the listing must agree on case -----------------

def test_the_accessor_finds_whatever_the_listing_finds(tmp_path):
    """The fix must not switch itself off when a folder is renamed by case.

    `files_matching` folds case on Windows (`_NAME_CASEFOLD`) because NTFS does;
    the resolver did not. So an upper-cased folder over decomposed files left
    `stem_files` finding the chart and `chart_ti2.exists()` denying it —
    the fix off, silently, on the platform it was written for.

    ONE-WAY, and deliberately: the accessor may find MORE than the listing (on a
    case-insensitive APFS volume `exists()` folds case where `Path.glob` does
    not, and that is the filesystem's answer, not ours). It may never find less.
    """
    run = _run_at(tmp_path, NAME.upper())
    (run.dir / f"{NFD}.ti2").write_text("the chart", encoding="utf-8")
    if run.stem_files(run.stem, ".ti2"):
        assert run.chart_ti2.is_file(), (
            "the listing sees a chart the accessor denies")
        assert run.chart_ti2.read_text(encoding="utf-8") == "the chart"


def test_case_folding_is_still_not_invented_where_the_volume_has_none(tmp_path):
    """On a case-SENSITIVE volume two names differing by case are two files.

    Asked which it is by writing both and counting, rather than by asking
    `sys.platform`.
    """
    from core.file_manager import resolve_existing

    (tmp_path / "Chart.ti2").write_text("upper", encoding="utf-8")
    (tmp_path / "chart.ti2").write_text("lower", encoding="utf-8")
    if len([p for p in tmp_path.iterdir() if p.suffix == ".ti2"]) == 2:
        assert resolve_existing(tmp_path / "chart.ti2").read_text(
            encoding="utf-8") == "lower"
        assert resolve_existing(tmp_path / "Chart.ti2").read_text(
            encoding="utf-8") == "upper"


# ---- M5: the tie-break is the sort, not the directory order ---------------

#: Three spellings of one name, all canonically equivalent, all distinct
#: strings: the composed form, the decomposed form, and the decomposed form
#: with its two combining marks written in the other order.
_TIED = ("ǭ", "ǭ")          # macron-first, ogonek-first
_TIED_NFC = "ǭ"                                 # ǭ


def test_which_of_several_spellings_wins_is_not_the_listing_order(tmp_path,
                                                                  monkeypatch):
    """`sorted` is what decides, and dropping it must fail.

    The docstring promises a deterministic answer when a folder holds more than
    one canonically equivalent spelling. Without this the promise was untested:
    the entries usually arrive in sorted order anyway, so removing `sorted` left
    every test green. `os.scandir` is made to hand them back REVERSED, so a
    version that takes "the first one listed" gets the other file.
    """
    import core.file_manager as fmod

    assert all(nfc(v) == _TIED_NFC for v in _TIED), "the premise of this test"
    assert len(set(_TIED)) == 2
    for v in _TIED:
        (tmp_path / f"{v}.ti2").write_text(v.encode("unicode_escape").decode(),
                                           encoding="utf-8")
    if len([p for p in tmp_path.iterdir() if p.suffix == ".ti2"]) != 2:
        pytest.skip("this volume folds the two orderings into one file")

    real = fmod.os.scandir

    class _Reversed:
        def __init__(self, path):
            self._entries = list(real(path))[::-1]

        def __enter__(self):
            return iter(self._entries)

        def __exit__(self, *exc):
            return False

    monkeypatch.setattr(fmod.os, "scandir", _Reversed)
    got = fmod.resolve_existing(tmp_path / f"{_TIED_NFC}.ti2")
    assert got.name == f"{min(_TIED)}.ti2", (
        f"the listing order decided, not the sort: got {got.name!r}")
    # …and it is the same answer every time it is asked.
    assert {fmod.resolve_existing(tmp_path / f"{_TIED_NFC}.ti2").name
            for _ in range(5)} == {got.name}


# ---- the cheap exit is about spellings, not about ASCII -------------------

@pytest.mark.parametrize("stem", [
    "Δοκιμη-χαρτι",   # Greek, unaccented
    "Проба-печати",        # Cyrillic, no marks
    "テスト-用紙",           # Japanese
    "打印测试",             # Chinese
    "Test-📄-chart",        # emoji
    "Yazıcı-testi",        # Turkish dotless i
])
def test_a_name_with_no_other_spelling_never_lists_the_directory(
        tmp_path, monkeypatch, stem):
    """`str.isascii()` was the wrong question.

    It is the right ANSWER for ASCII, but it made every non-ASCII name pay for
    a directory scan that could not possibly match — a name has another spelling
    only if something in it decomposes or if two combining marks could be
    reordered, and none of these has either.
    """
    import core.file_manager as fmod

    assert not stem.isascii(), "this test is about the non-ASCII fast exit"

    def _explode(*a, **k):
        raise AssertionError(f"scandir called for {stem!r}, which has no "
                             "other spelling")

    monkeypatch.setattr(fmod.os, "scandir", _explode)
    missing = tmp_path / f"{stem}.ti2"
    assert fmod.resolve_existing(missing) == missing


@pytest.mark.parametrize("stem", [
    NAME,                        # composes: ü -> u + U+0308
    NFD,                         # already decomposed
    "한글-chart",        # Hangul: every syllable decomposes
    "ǭ-chart",       # two marks that could be reordered
    # Greek WITH accents: ή is U+03AE and decomposes to η + U+0301. This test
    # is where it belongs — the first version of the list above had it as a
    # name with "no other spelling", and the assertion caught that, which is
    # the whole reason the pair of tests exists.
    "Δοκιμή-χαρτί",
])
def test_a_name_that_really_has_another_spelling_is_still_looked_for(
        tmp_path, monkeypatch, stem):
    """The other half, or the cheap exit would silently switch the fix off.

    A guard that skips too much is the same bug wearing the opposite sign, so
    the scan is asserted to HAPPEN for every name that could have a twin.
    """
    import core.file_manager as fmod

    seen: list[str] = []
    real = fmod.os.scandir

    def _noted(path):
        seen.append(str(path))
        return real(path)

    monkeypatch.setattr(fmod.os, "scandir", _noted)
    fmod.resolve_existing(tmp_path / f"{stem}.ti2")
    assert seen, f"{stem!r} has another spelling and was not looked for"


# ---- E-1: named, measured, and NOT fixed here ----------------------------

def test_a_typed_composed_name_does_not_yet_find_a_decomposed_project_folder(
        tmp_path, monkeypatch):
    """A KNOWN GAP, PINNED SO IT IS A FACT RATHER THAN A SURPRISE.

    Every route that reaches a project through the FOLDER — the picker,
    `open_project_at`, session restore — takes the folder's own spelling and
    works. The Create Chart NAME BOX does not: `_sanitise` normalises to NFC,
    `_existing_folder_spelling` adopts a differently-CASED folder but
    deliberately not a differently-ACCENTED one, and on NTFS the composed path
    simply is not there — so `project()` creates a SECOND, empty folder that is
    drawn identically to the first by every font on the machine.

    It is not fixed here because fixing it means changing either the "a folder
    name is always NFC" invariant or `working_dir`'s re-clean-and-compare, both
    of which are pinned behaviour with a documented reason
    (`test_project_name_keeps_its_accents`). See `_existing_folder_spelling`'s
    docstring. **This test asserts what ChromIQ does today, not what it should
    do** — when that decision is taken, this test is the one to change.
    """
    from core.file_manager import FileManager
    from core.settings import AppSettings

    monkeypatch.setenv("CHROMIQ_SETTINGS_FILE", str(tmp_path / "s.ini"))
    work = tmp_path / "work"
    work.mkdir()
    Project.create(work / NFD, NFD)

    s = AppSettings()
    s.set("custom_output_path", str(work))
    fm = FileManager(s)
    fm.set_target_name(NAME)                 # the user TYPES the composed name
    fm.project()

    folders = sorted(p.name for p in work.iterdir() if p.is_dir())
    if len(folders) == 1:
        # A normalisation-INSENSITIVE volume (APFS) folds the two spellings
        # into one folder, so the gap cannot happen there. Recorded, not
        # skipped — which volume ran this is the interesting half.
        assert nfc(folders[0]) == NAME
        return
    assert set(folders) == {NFD, NAME}, folders
    assert list((work / NAME).glob("**/*.ti2")) == [], (
        "the new folder is the empty one — the user's chart is in the "
        "other, and the two are drawn identically by every font")
