"""A refusal that says "nothing has been changed" must not move the project.

Found by the combined adversary round of 2026-09-15 (B8-216), pointed at the
import doors' refusals, which is where rounds 4 and 5 both found their faults.

``Project.duplicate_run`` makes the new run with ``new_run()``, and when the
copy fails it runs its OWN rollback -- ``_discard_run(just_created=True)`` --
which points ``current_run`` at ``runs[-1]`` and then RE-RAISES. So by the time
either import door's handler runs, the manifest has already moved; and
``made_here`` is still ``None``, because it is assigned on the line AFTER the
one that raised.

``_undo_the_run`` exists for exactly this accident. Its own docstring says so:

    *"`_discard_run` restores the manifest to the LAST run in the list, which
    is only right when that is where the person was. Import into a two-run
    project and be refused, and it moved them from run 1 to run 2 under a
    window saying nothing had been changed."*

…and it began ``if made_here is None: return``, which switched the whole
function off at the one refusal that sentence describes. Round 4 found this
same restore dead for a different reason (a field name that does not exist);
this is the second way it read as a fix and did nothing.

WHAT A USER SAW, driven on screen in a real window
(``~/Desktop/ChromIQ-beta18-proof/combined-round-6/``, ``B-result.json``,
``B2-the-refusal-that-moved-the-project.png``): a three-run project standing on
Run 1, an import into Run 1 answered with **Make a new run**, the copy refused
as a full disk refuses it, and afterwards ``project.json`` read
``current_run: run3`` and a fresh open of the project stood on **Run 3** --
under *"Nothing has been imported and nothing has been changed."*
``C-result.json`` is the same drive afterwards: ``current_run: run1``, a fresh
open on Run 1.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest                                              # noqa: E402

from core.file_manager import Project, peek_project        # noqa: E402
from ui.measurement_filing import _undo_the_run, run_the_project_is_on  # noqa: E402


def _three_runs(tmp_path: Path) -> Project:
    proj = Project.create(tmp_path / "P", "P")
    r1 = proj.current_run()
    r1.ensure_dir()
    r1.chart_ti2.write_text("CTI2\nNUMBER_OF_SETS 3\n", encoding="utf-8")
    for _ in range(2):
        r = proj.new_run()
        r.ensure_dir()
        r.chart_ti2.write_text("CTI2\nNUMBER_OF_SETS 3\n", encoding="utf-8")
    proj.set_current_run("run1")
    return proj


def _refuse_the_copy(monkeypatch) -> None:
    """A full disk, or a share that has gone away, at `duplicate_run`'s copy."""
    import core.file_manager as fm

    def boom(*_a, **_k):
        raise OSError(28, "No space left on device")
    monkeypatch.setattr(fm.shutil, "copy2", boom)


def _on_disk(proj: Project) -> str:
    return json.loads((proj.root / "project.json").read_text(
        encoding="utf-8")).get("current_run", "")


# ---------------------------------------------------------------------------
# the fact the doors depend on
# ---------------------------------------------------------------------------

def test_a_refused_duplicate_really_does_move_the_manifest(tmp_path,
                                                           monkeypatch):
    """The premise, measured rather than assumed: without a restore the
    project ends up somewhere the person never chose."""
    proj = _three_runs(tmp_path)
    assert _on_disk(proj) == "run1"
    _refuse_the_copy(monkeypatch)
    with pytest.raises(OSError):
        proj.duplicate_run(proj.current_run(), ("chart",))
    assert _on_disk(proj) == "run3", (
        "duplicate_run's own rollback points current_run at runs[-1]")


# ---------------------------------------------------------------------------
# …and the shared restore now answers it
# ---------------------------------------------------------------------------

def test_undo_the_run_puts_the_project_back_with_no_run_to_discard(
        tmp_path, monkeypatch):
    proj = _three_runs(tmp_path)
    was = run_the_project_is_on(proj.root)
    assert was == "run1"
    _refuse_the_copy(monkeypatch)
    with pytest.raises(OSError):
        proj.duplicate_run(proj.current_run(), ("chart",))
    _undo_the_run(proj, None, was)            # exactly what the doors call
    assert _on_disk(proj) == "run1"
    assert getattr(peek_project(proj.root), "run_id", None) == "run1", (
        "a fresh open must stand where the person left it")


def test_undo_the_run_still_discards_a_run_it_made(tmp_path):
    """Round 5's behaviour is not lost to the change: a run this import made
    and never filled is still removed, and the manifest still goes back."""
    proj = _three_runs(tmp_path)
    made = proj.new_run()
    made.ensure_dir()
    assert _on_disk(proj) == made.id
    _undo_the_run(proj, made, "run1")
    assert not made.dir.exists()
    assert made.id not in json.loads(
        (proj.root / "project.json").read_text(encoding="utf-8"))["runs"]
    assert _on_disk(proj) == "run1"


def test_undo_the_run_with_nothing_to_go_back_to_changes_nothing(tmp_path):
    proj = _three_runs(tmp_path)
    proj.set_current_run("run2")
    _undo_the_run(proj, None, "")
    assert _on_disk(proj) == "run2"


def test_a_run_that_is_gone_is_not_restored_over(tmp_path):
    """`set_current_run` raises on an unknown run; a refusal must not."""
    proj = _three_runs(tmp_path)
    proj.set_current_run("run3")
    _undo_the_run(proj, None, "run9")         # never existed
    assert _on_disk(proj) == "run3"


# ---------------------------------------------------------------------------
# the Measure tab's door, which had no restore at this handler at all
# ---------------------------------------------------------------------------

def test_the_measure_tabs_import_puts_the_project_back(tmp_path, monkeypatch):
    from ui.tabs.tab_measure import TabMeasure
    proj = _three_runs(tmp_path)
    was = run_the_project_is_on(proj.root)
    _refuse_the_copy(monkeypatch)
    with pytest.raises(OSError):
        proj.duplicate_run(proj.current_run(), ("chart",))
    assert _on_disk(proj) == "run3"
    TabMeasure._put_the_project_back(proj, was)
    assert _on_disk(proj) == "run1"


def test_both_of_the_measure_tabs_refusals_call_it():
    """The two handlers that can run AFTER duplicate_run has moved the
    manifest, and which the shared `_undo_the_run` could never reach."""
    import inspect
    from ui.tabs.tab_measure import TabMeasure
    src = inspect.getsource(TabMeasure._import_into_profiling_run)
    assert src.count("_put_the_project_back") == 2, (
        "both refusals around `ask_to_make_a_new_run` / `duplicate_run` must "
        "put the project back before they say nothing has been changed")
    assert "run_the_project_is_on" in src, (
        "the value restored is the MANIFEST's, not the bar's: the bar can be "
        "empty while the manifest is not")
