"""A project folder called `Canon-Pro300 [test]` still shows its chart.

WHAT WENT WRONG
    `Run.stem` is the folder name AS IT IS ON DISK (`core/file_manager.py`,
    `return self.dir.parents[1].name`), and every caller pasted it into a
    pattern: `files_matching(run.dir, f"{stem}*.tif")`. `FileManager._sanitise`
    maps `[`, `]`, `*` and `?` to `_`, so ChromIQ cannot CREATE such a folder —
    but `open_project_at()` opens whatever folder the user picked, under the
    name it has on disk, and Finder renames a folder to anything. File → Open
    Project and the restore-last-session path both go through it.

    `[v2]` is then a character class, and `Chart [v2]_01.tif` does not match
    `Chart [v2]*.tif`. `chart_ti2.exists()` said True, `chart_tiffs()` came back
    empty, the Chart tab said "No chart for this profile run yet" with four page
    bitmaps sitting in the folder, and Print was greyed out — the identical
    signature to the HFS+ decomposed-name fault in
    `test_a_decomposed_name_finds_its_files.py`, from a second cause.

    The other half is worse and quieter: `*` and `?` OVER-match. A project
    called `Chart*A` matched `ChartXA_01.tif`, a page belonging to a project
    with a different name — and `duplicate_run_plan` carried that stranger's
    `.ti2` and `.tif` into a duplicate, while `_clear_verify_chart_files`
    ARCHIVES what it matches.

THE FIX
    The literal never reaches the matcher. `core.file_manager.stem_files(folder,
    stem, *tails)` takes the name as its own argument and escapes it with
    `glob_escape`; the tails are the only patterns. Escaping at each of the two
    dozen f-strings would have fixed the same bugs and left the next f-string
    free to bring them back, so the interface changed instead — and
    `test_no_source_file_pastes_a_name_into_a_pattern` below fails if one comes
    back.

WHAT THESE TESTS PROVE
    That each metacharacter is found and nothing extra is; that an ASCII name
    still takes byte-identical the path it took before; that the NFC folding
    survives; that the Windows case-folding branch — dead code on this machine
    and therefore never executed by the gate — works with an escaped literal;
    and that the shape which caused this cannot be written again.
"""
from __future__ import annotations

import ast
import os
import unicodedata as ud
from pathlib import Path

import pytest

import core.file_manager as fm_mod
from core.file_manager import (
    FileManager,
    Project,
    Run,
    files_matching,
    glob_escape,
    stem_files,
)

#: Every character `fnmatch` treats as syntax, in a name a person could type
#: into Finder. `]` is included even though it is only syntax after a `[`.
METACHAR_NAMES = ["Chart [v2]", "Chart]v2[", "Chart*A", "Chart?A",
                  "Canon-Pro300 [test]", "Müller [2026]"]


def _chart_run(root: Path, stem: str, pages: int = 4) -> Run:
    """A run folder holding a whole chart under *stem*."""
    run_dir = root / "runs" / "run1"
    run_dir.mkdir(parents=True, exist_ok=True)
    for ext in (".ti1", ".ti2", ".cht", ".channels.json", ".ti3"):
        (run_dir / f"{stem}{ext}").write_text("x", encoding="utf-8")
    for i in range(1, pages + 1):
        (run_dir / f"{stem}_{i:02d}.tif").write_text("x", encoding="utf-8")
    return Run.for_dir(run_dir)


# ---------------------------------------------------------------------------
# The escape itself
# ---------------------------------------------------------------------------

def test_glob_escape_matches_the_name_and_only_the_name():
    import fnmatch
    for name in ("Chart [v2]", "Chart*A", "Chart?A", "a]b", "plain"):
        assert fnmatch.fnmatchcase(name, glob_escape(name)), name


@pytest.mark.parametrize("name", ["Chart", "Müller-Prüfdruck", "a-b_c.1",
                                  "2026-08-24_15-30"])
def test_a_name_with_no_metacharacter_is_returned_untouched(name):
    """The overwhelming majority of names. If escaping changed these, every
    existing project would take a different code path than it did yesterday."""
    assert glob_escape(name) == name


# ---------------------------------------------------------------------------
# Finding, and not over-finding
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("stem", METACHAR_NAMES)
def test_a_metacharacter_in_the_name_still_finds_the_chart(tmp_path, stem):
    """The on-screen fault: exists() True, the pages invisible."""
    run = _chart_run(tmp_path / stem, stem)
    assert run.stem == stem
    assert run.chart_ti2.exists()
    found = [p.name for p in run.chart_tiffs()]
    assert len(found) == 4, found


def test_an_asterisk_in_the_name_does_not_adopt_a_strangers_page(tmp_path):
    """`Chart*A` used to match `ChartXA_01.tif`, which belongs to a project with
    a different name. Whatever prints or archives that list then handles a page
    it was never given."""
    run = _chart_run(tmp_path / "Chart*A", "Chart*A", pages=2)
    (run.dir / "ChartXA_01.tif").write_text("x", encoding="utf-8")
    found = [p.name for p in run.chart_tiffs()]
    assert "ChartXA_01.tif" not in found, found
    assert len(found) == 2, found


def test_a_question_mark_in_the_name_does_not_adopt_one_either(tmp_path):
    run = _chart_run(tmp_path / "Chart?A", "Chart?A", pages=2)
    (run.dir / "ChartZA_01.tif").write_text("x", encoding="utf-8")
    found = [p.name for p in run.chart_tiffs()]
    assert "ChartZA_01.tif" not in found, found
    assert len(found) == 2, found


def test_the_duplicate_plan_copies_this_project_and_not_the_one_next_to_it(
        tmp_path):
    """`duplicate_run_plan` fills `{stem}` templates, so the folder name lands
    inside a pattern whatever the call looks like. It carried a stranger's
    `.ti2` and `.tif` into the copy."""
    proj = Project.create(tmp_path / "Chart*A", "Chart*A")
    run = proj.new_run()
    for ext in (".ti1", ".ti2", ".ti3", ".icc"):
        (run.dir / f"Chart*A{ext}").write_text("x", encoding="utf-8")
    (run.dir / "Chart*A_01.tif").write_text("x", encoding="utf-8")
    (run.dir / "ChartXA.ti2").write_text("x", encoding="utf-8")
    (run.dir / "ChartXA_01.tif").write_text("x", encoding="utf-8")
    proj.save_manifest()
    picked = sorted(p.name for _g, files, _b in proj.duplicate_run_plan(run)
                    for p in files)
    assert [p for p in picked if p.startswith("ChartXA")] == [], picked
    assert "Chart*A_01.tif" in picked, picked


def test_the_verify_guard_archives_this_charts_pages_and_no_others(tmp_path):
    """`_clear_verify_chart_files` ARCHIVES what it matches, so an over-match
    here moves somebody else's file out from under them."""
    run_dir = tmp_path / "Chart*A" / "runs" / "run1"
    run_dir.mkdir(parents=True)
    vdir = run_dir / "verifications"
    vdir.mkdir()
    for ext in (".ti1", ".ti2"):
        (vdir / f"Chart*A-verify{ext}").write_text("x", encoding="utf-8")
    (vdir / "ChartXA-verify.ti2").write_text("x", encoding="utf-8")
    run = Run.for_dir(run_dir)
    run._clear_verify_chart_files()
    left = sorted(p.name for p in vdir.iterdir() if p.is_file())
    assert left == ["ChartXA-verify.ti2"], left


def test_a_bracket_name_is_found_after_a_rename_to_a_verify_chart(tmp_path):
    """`adopt_run_chart_as_verify` moves `<old>_NN.tif` by the same route."""
    run = _chart_run(tmp_path / "Chart [v2]", "Chart [v2]", pages=3)
    run.adopt_run_chart_as_verify()
    moved = sorted(p.name for p in run.verifications_dir.iterdir()
                   if p.suffix == ".tif")
    assert len(moved) == 3, moved


# ---------------------------------------------------------------------------
# Nothing else changed
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("stem", ["chart", "Chart-2026", "a_b.c"])
def test_an_ascii_name_gives_byte_identical_answers_to_path_glob(tmp_path,
                                                                 stem):
    """The old behaviour, name for name and order for order."""
    for i in range(1, 4):
        (tmp_path / f"{stem}_{i:02d}.tif").write_text("x", encoding="utf-8")
    (tmp_path / f"{stem}.ti2").write_text("x", encoding="utf-8")
    assert stem_files(tmp_path, stem, "_*.tif") == sorted(
        tmp_path.glob(f"{stem}_*.tif"))
    assert stem_files(tmp_path, stem, "*") == sorted(tmp_path.glob(f"{stem}*"))


def test_the_nfc_folding_still_works_through_the_new_call(tmp_path):
    """The fault this helper was written for in the first place. A decomposed
    page name and a composed stem are different strings and the same file."""
    nfd = ud.normalize("NFD", "Müller")
    nfc_name = ud.normalize("NFC", "Müller")
    assert nfd != nfc_name
    (tmp_path / f"{nfd}_01.tif").write_text("x", encoding="utf-8")
    assert len(stem_files(tmp_path, nfc_name, "_*.tif")) == 1


def test_the_nfc_folding_works_for_a_name_that_also_has_a_bracket(tmp_path):
    """Both rules at once — a project off a Time Machine disk, renamed in
    Finder. Escaping must happen on the composed spelling, not instead of it."""
    nfd = ud.normalize("NFD", "Müller [2026]")
    nfc_name = ud.normalize("NFC", "Müller [2026]")
    (tmp_path / f"{nfd}_01.tif").write_text("x", encoding="utf-8")
    assert len(stem_files(tmp_path, nfc_name, "_*.tif")) == 1


def test_a_missing_folder_is_no_files_not_an_exception(tmp_path):
    assert stem_files(tmp_path / "nope", "Chart [v2]", "*.tif") == []
    assert stem_files(None, "Chart", "*.tif") == []


def test_a_multi_segment_tail_is_still_refused(tmp_path):
    with pytest.raises(ValueError):
        stem_files(tmp_path, "Chart", "/x.tif")


# ---------------------------------------------------------------------------
# The Windows branch, which this machine never executes
# ---------------------------------------------------------------------------

def test_the_windows_case_folding_branch_handles_an_escaped_literal(
        tmp_path, monkeypatch):
    """`_NAME_CASEFOLD` is `os.name == "nt"`, so on macOS and Linux this branch
    is dead and the whole gate has always run past it. It lowercases the PATTERN
    as well as the name, which would mangle a character range — so the escaped
    literals it now receives are exactly the thing worth checking.

    Rebinding the module global is the only way to reach it here; the branch
    reads it at call time on purpose.
    """
    monkeypatch.setattr(fm_mod, "_NAME_CASEFOLD", True)
    (tmp_path / "Chart [v2]_01.TIF").write_text("x", encoding="utf-8")
    (tmp_path / "Chart [v2]_02.tif").write_text("x", encoding="utf-8")
    (tmp_path / "ChartXv2X_03.tif").write_text("x", encoding="utf-8")
    found = sorted(p.name for p in stem_files(tmp_path, "Chart [v2]", "*.tif"))
    assert found == ["Chart [v2]_01.TIF", "Chart [v2]_02.tif"], found


def test_the_windows_branch_does_not_over_match_on_an_asterisk(
        tmp_path, monkeypatch):
    monkeypatch.setattr(fm_mod, "_NAME_CASEFOLD", True)
    (tmp_path / "Chart*A_01.tif").write_text("x", encoding="utf-8")
    (tmp_path / "ChartXA_01.tif").write_text("x", encoding="utf-8")
    found = sorted(p.name for p in stem_files(tmp_path, "Chart*A", "*.tif"))
    assert found == ["Chart*A_01.tif"], found


def test_the_posix_branch_is_still_case_sensitive(tmp_path):
    """`files_matching` reproduces `Path.glob`, which is case-sensitive here.
    That is why callers pass `*.tif`/`*.TIF` pairs, and it must not change."""
    if os.name == "nt":
        pytest.skip("case-insensitive filesystem semantics")
    (tmp_path / "Chart_01.TIF").write_text("x", encoding="utf-8")
    assert stem_files(tmp_path, "Chart", "_*.tif") == []
    assert len(stem_files(tmp_path, "Chart", "_*.tif", "_*.TIF")) == 1


# ---------------------------------------------------------------------------
# The shape cannot come back
# ---------------------------------------------------------------------------

SOURCE_DIRS = ("core", "workflow", "ui")


def _source_files() -> "list[Path]":
    root = Path(__file__).resolve().parent.parent
    out: list[Path] = []
    for d in SOURCE_DIRS:
        out += sorted((root / d).rglob("*.py"))
    assert len(out) > 20, out
    return out


def _interpolating_fstring(node: ast.AST) -> bool:
    return (isinstance(node, ast.JoinedStr)
            and any(isinstance(v, ast.FormattedValue) for v in node.values))


def _matcher_call(node: ast.AST) -> "tuple[str, ast.AST | None, list]":
    """(function name, the stem argument, the pattern arguments) for a call to
    the matcher, in EITHER form.

    The module functions take the folder first (`stem_files(d, stem, *tails)`);
    the `Run` / `Calibration` methods do not (`run.stem_files(stem, *tails)`),
    because the folder is the object. Counting arguments without that
    distinction reads the first TAIL as the stem, which is how the first draft
    of this test reported seven offenders that were all correct code.
    """
    if not isinstance(node, ast.Call):
        return "", None, []
    is_method = isinstance(node.func, ast.Attribute)
    name = node.func.attr if is_method else getattr(node.func, "id", "")
    if name not in ("files_matching", "stem_files"):
        return "", None, []
    args = node.args if is_method else node.args[1:]
    if name == "stem_files":
        return name, (args[0] if args else None), list(args[1:])
    return name, None, list(args)


def test_no_source_file_pastes_a_name_into_a_pattern():
    """`files_matching(d, f"{stem}*.tif")` is the shape that caused all of this.

    Two dozen of them existed; escaping each one would have left the next one
    free to reappear. `stem_files` takes the literal as its own argument, so the
    rule is simply that no f-string is handed to the pattern matcher — which is
    something a test can check, unlike "remember to escape".
    """
    offenders = []
    for path in _source_files():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            name, _stem, patterns = _matcher_call(node)
            if not name:
                continue
            for arg in patterns:
                if _interpolating_fstring(arg):
                    offenders.append(f"{path.name}:{node.lineno}")
    assert offenders == [], (
        "a name interpolated into a glob pattern — use stem_files(folder, "
        f"stem, *tails) instead: {offenders}")


def test_the_stem_argument_of_stem_files_is_never_a_pattern():
    """The mirror rule. `stem_files(d, f"{stem}*", ".tif")` would put the
    wildcard back on the literal side and undo the whole thing."""
    offenders = []
    for path in _source_files():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            name, stem_arg, _patterns = _matcher_call(node)
            if name != "stem_files" or stem_arg is None:
                continue
            if (isinstance(stem_arg, ast.Constant)
                    and isinstance(stem_arg.value, str)
                    and any(c in stem_arg.value for c in "*?[")):
                offenders.append(f"{path.name}:{node.lineno}")
    assert offenders == [], offenders


def test_sanitise_still_cannot_produce_a_metacharacter():
    """Half of why this was survivable: ChromIQ never MAKES such a folder, so
    only a hand-renamed or restored one is affected. Worth pinning, because it
    decides how many entry points have to be defended."""
    for ch in "*?[]":
        assert ch not in FileManager._sanitise(f"a{ch}b"), ch
    assert FileManager._sanitise("Chart [v2]") == "Chart-_v2"


# ---------------------------------------------------------------------------
# The two lookups the behavioural half missed
#
# A challenge agent re-broke `Run.verify_chart_tiffs` SEVEN ways that the ast
# guard cannot see - a pattern in a local variable, `.format`, `%`, `+`,
# `"".join`, and `Path.glob`, which the guard does not look at - and all 29
# tests stayed green while the method adopted a stranger's page. The static
# guard only sees f-strings, so the behavioural tests are what actually
# protect these; `verify_chart_tiffs` and `Calibration.chart_tiffs` had none.
# ---------------------------------------------------------------------------

def _verify_chart(root: Path, stem: str, pages: int = 2) -> Run:
    """A run holding a VERIFICATION chart under *stem*."""
    run_dir = root / "runs" / "run1"
    run_dir.mkdir(parents=True, exist_ok=True)
    run = Run.for_dir(run_dir)
    vdir = run.verifications_dir
    vdir.mkdir(parents=True, exist_ok=True)
    for i in range(1, pages + 1):
        (vdir / f"{run.verify_stem}_{i:02d}.tif").write_text("x", encoding="utf-8")
    return run


@pytest.mark.parametrize("stem", METACHAR_NAMES)
def test_a_metacharacter_name_still_finds_its_verification_pages(tmp_path, stem):
    run = _verify_chart(tmp_path / stem, stem)
    found = [p.name for p in run.verify_chart_tiffs()]
    assert len(found) == 2, found


def test_a_verification_chart_does_not_adopt_a_strangers_page(tmp_path):
    """The destructive half: whatever prints or ARCHIVES that list then
    handles a page belonging to a project with a different name."""
    run = _verify_chart(tmp_path / "Chart*A", "Chart*A")
    stranger = run.verifications_dir / run.verify_stem.replace("*", "X")
    (Path(str(stranger) + "_01.tif")).write_text("x", encoding="utf-8")
    found = [p.name for p in run.verify_chart_tiffs()]
    assert len(found) == 2, found
    assert not any("ChartXA" in n for n in found), found


@pytest.mark.parametrize("stem", METACHAR_NAMES)
def test_a_metacharacter_name_still_finds_its_calibration_pages(tmp_path, stem):
    from core.file_manager import Calibration
    root = tmp_path / stem
    (root / "cal").mkdir(parents=True)
    cal = Calibration(root)               # the project root, as the app does
    cal_dir = cal.dir
    for i in range(1, 3):
        (cal_dir / f"{cal.stem}_{i:02d}.tif").write_text("x", encoding="utf-8")
    found = [p.name for p in cal.chart_tiffs()]
    assert len(found) == 2, found


def test_a_calibration_does_not_adopt_a_strangers_page(tmp_path):
    from core.file_manager import Calibration
    root = tmp_path / "Chart*A"
    (root / "cal").mkdir(parents=True)
    cal = Calibration(root)
    cal_dir = cal.dir
    for i in range(1, 3):
        (cal_dir / f"{cal.stem}_{i:02d}.tif").write_text("x", encoding="utf-8")
    (cal_dir / f"{cal.stem.replace('*', 'X')}_01.tif").write_text("x", encoding="utf-8")
    found = [p.name for p in cal.chart_tiffs()]
    assert len(found) == 2, found
