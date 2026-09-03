"""`Chart` and `chart`: what really happens, on the filesystem under this run.

Finding G of the first Windows verification (2026-09-03,
`WINDOWS-VM-REPORT.md`): *"two project names differing only by case merge into
one folder on Windows … a macOS user copying two such projects to Windows loses
one."*

THE PREMISE IS HALF WRONG, AND THE HALF THAT IS WRONG IS THE INTERESTING ONE.
A **default macOS APFS volume is case-insensitive too**, so the merge is not
something that happens on the way to Windows — the owner's own Mac cannot hold
`Chart` and `chart` as two projects either. That is measured here, on whatever
volume the suite is running on, rather than assumed, because APFS *can* be
formatted case-sensitive and every ordinary Linux volume is.

So the merge itself is the filesystem's, not ChromIQ's, and there is nothing to
fix about it. What WAS ChromIQ's, and is fixed, is subtler and worse: the typed
spelling became the project's name even when the folder on disk spells it the
other way. `Run.stem` is the project folder's name, so a run inside `Chart/`
whose target name was `chart` built `chart.ti2` beside the `Chart.ti2` already
there — two chart chains in one run, each invisible to the other, because
`stem_files` compares spellings.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

from core.file_manager import (FileManager, Project, _existing_folder_spelling,
                               stem_files)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def _case_insensitive(d) -> bool:
    """Whether THIS volume treats two spellings as one folder. Asked of the
    filesystem, never inferred from `sys.platform`."""
    probe = d / "CaseProbe"
    probe.mkdir()
    try:
        return (d / "caseprobe").is_dir()
    finally:
        probe.rmdir()


class _Settings(dict):
    def get(self, k, default=None):
        return dict.get(self, k, default)

    def set(self, k, v):
        self[k] = v


def _fm(root):
    return FileManager(_Settings(custom_output_path=str(root)))


# ---------------------------------------------------------------------------
# What the filesystem does — measured, and reported either way
# ---------------------------------------------------------------------------

def test_the_volume_answers_for_itself(tmp_path):
    """A statement of fact about the machine this ran on, so a reader of a
    failure elsewhere in this file knows which world they are in."""
    insensitive = _case_insensitive(tmp_path)
    # Both are legitimate; the point is that the answer is READ, not assumed.
    assert insensitive in (True, False)
    if sys.platform == "darwin" and not insensitive:
        pytest.skip("this Mac's volume is formatted case-sensitive — the "
                    "default is not, and the rest of this file says so")


def test_two_spellings_are_one_folder_when_the_volume_says_so(tmp_path):
    """The merge, reproduced. It is the filesystem, not ChromIQ: nothing in
    ChromIQ is involved in these four lines."""
    if not _case_insensitive(tmp_path):
        pytest.skip("case-sensitive volume: Chart and chart really are two")
    (tmp_path / "Chart").mkdir()
    with pytest.raises(FileExistsError):
        (tmp_path / "chart").mkdir()
    assert os.path.samefile(tmp_path / "Chart", tmp_path / "chart")
    # …and it is case-PRESERVING, which is what makes the ChromIQ half possible:
    # the folder answers to `chart` and goes on being called `Chart`.
    assert [p.name for p in tmp_path.iterdir()] == ["Chart"]


# ---------------------------------------------------------------------------
# What ChromIQ does about it
# ---------------------------------------------------------------------------

def test_the_folders_own_spelling_wins_over_the_typed_one(tmp_path):
    """The fault, and the fix.

    Before: the second project's stem was `chart` while its folder was `Chart`,
    so the run held `Chart.ti2` AND `chart.ti2` and each was invisible to the
    other. Now the typed spelling is dropped for the one on disk.
    """
    if not _case_insensitive(tmp_path):
        pytest.skip("case-sensitive volume: the two are genuinely two projects")
    first = _fm(tmp_path)
    first.set_target_name("Chart")
    run = first.project().current_run()
    run.chart_ti2.write_text("the first chart", encoding="utf-8")

    second = _fm(tmp_path)
    second.set_target_name("chart")
    assert second.get_target_name() == "Chart"
    run2 = second.project().current_run()
    assert run2.stem == "Chart"
    assert run2.chart_ti2 == run.chart_ti2
    assert run.chart_ti2.read_text(encoding="utf-8") == "the first chart"
    # ONE chart chain in the folder, not two.
    assert sorted(f.name for f in run.dir.glob("*.ti2")) == ["Chart.ti2"]


def test_a_case_sensitive_volume_keeps_them_apart(tmp_path):
    """The other half, and the reason the check asks the filesystem rather than
    the platform: where `Chart` and `chart` really are two folders, ChromIQ
    must not quietly move somebody's project into the other one."""
    if _case_insensitive(tmp_path):
        pytest.skip("case-insensitive volume: they cannot be kept apart here")
    (tmp_path / "Chart").mkdir()
    fm = _fm(tmp_path)
    fm.set_target_name("chart")
    assert fm.get_target_name() == "chart"
    assert fm.working_dir() == tmp_path / "chart"


def test_nothing_is_adopted_when_there_is_no_folder(tmp_path):
    """A fresh name is the name that was typed, whatever else is on disk."""
    (tmp_path / "Chart").mkdir()
    assert _existing_folder_spelling(tmp_path, "Something-Else") == \
        "Something-Else"
    assert _existing_folder_spelling(tmp_path, "") == ""
    assert _existing_folder_spelling(tmp_path / "nope", "Chart") == "Chart"


def test_the_exact_spelling_is_never_touched(tmp_path):
    """The common case must cost nothing and change nothing."""
    (tmp_path / "Chart").mkdir()
    (tmp_path / "chart-2").mkdir()
    assert _existing_folder_spelling(tmp_path, "Chart") == "Chart"
    assert _existing_folder_spelling(tmp_path, "chart-2") == "chart-2"


def test_only_case_is_adopted_and_not_accent_spelling(tmp_path):
    """CASE ONLY, on purpose.

    A folder whose accents are DECOMPOSED — what an HFS+ volume hands back —
    is `nfc`'s problem and `files_matching`'s, and adopting that spelling here
    would change what `test_project_name_keeps_its_accents.py` pins. So a
    decomposed folder is left alone even though the volume opens it under the
    composed name.
    """
    import unicodedata
    decomposed = unicodedata.normalize("NFD", "Müller")
    composed = unicodedata.normalize("NFC", "Müller")
    assert decomposed != composed
    (tmp_path / decomposed).mkdir()
    if not (tmp_path / composed).exists():
        pytest.skip("this volume does not normalise filenames")
    assert _existing_folder_spelling(tmp_path, composed) == composed


# ---------------------------------------------------------------------------
# The `_NAME_CASEFOLD` branch, and the asymmetry that is deliberately kept
# ---------------------------------------------------------------------------

def test_stem_files_is_case_sensitive_here_and_that_is_recorded(tmp_path):
    """macOS gets Windows' filesystem with Linux's matching rule.

    `_NAME_CASEFOLD` keys on `os.name == "nt"`, so a file whose name differs
    from the stem only by case is found on Windows and NOT on a case-
    insensitive Mac. Left as it is — lowering both sides everywhere would
    change matching on the case-sensitive volumes ChromIQ also runs on — but
    written down, because the comment above that flag used to read as "macOS is
    case-sensitive", which is false and is exactly the shape of trap finding E
    is about.
    """
    (tmp_path / "chart_01.tif").write_text("x", encoding="utf-8")
    found = [f.name for f in stem_files(tmp_path, "Chart", "_*.tif")]
    if os.name == "nt":                    # pragma: no cover — not this machine
        assert found == ["chart_01.tif"]
    else:
        assert found == []
    # …and the right spelling always finds it, which is the case ChromIQ itself
    # is ever in: it writes these files from the folder's own name.
    assert [f.name for f in stem_files(tmp_path, "chart", "_*.tif")] == \
        ["chart_01.tif"]


def test_the_project_created_under_either_spelling_is_one_project(tmp_path):
    """End to end, through `Project`, which is what a copied folder meets."""
    if not _case_insensitive(tmp_path):
        pytest.skip("case-sensitive volume")
    a = Project.create_or_load(tmp_path / "Chart", "Chart")
    b = Project.create_or_load(tmp_path / "chart", "chart")
    assert os.path.samefile(a.root, b.root)
    assert [p.name for p in tmp_path.iterdir()] == ["Chart"]


def test_the_filesystems_answer_is_what_decides(tmp_path, monkeypatch):
    """The guard that cannot be reached on a case-insensitive machine.

    `_existing_folder_spelling` adopts a folder's spelling only when
    `(parent / name).exists()` — the filesystem saying the two names are one
    folder. On a case-SENSITIVE volume that is False and nothing is adopted,
    which is the whole reason the check asks the filesystem instead of testing
    `sys.platform`. This suite runs on a case-insensitive Mac, where that
    branch is never taken, so it is forced: `exists` is made to answer the way
    a case-sensitive volume would, and nothing else changes.
    """
    (tmp_path / "Chart").mkdir()
    assert _existing_folder_spelling(tmp_path, "chart") in ("Chart", "chart")

    real_exists = Path.exists

    def case_sensitive_exists(self, *a, **kw):
        # `<tmp>/chart` is not there on a volume that tells the two apart.
        if self == tmp_path / "chart":
            return False
        return real_exists(self, *a, **kw)

    monkeypatch.setattr(Path, "exists", case_sensitive_exists)
    assert _existing_folder_spelling(tmp_path, "chart") == "chart", (
        "a case-sensitive volume holds two different projects, and moving one "
        "into the other is exactly what must not happen")
