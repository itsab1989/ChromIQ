"""The "New run" block: where it lives, and what is stripped from it.

Knut's design (#130 §4a): when a target-changing pulldown opens, the loaded
run's settings are copied into a temporary block, so selecting **New run** shows
what is already on screen — *"no visible change for the user"* — which the user
then edits into the specification for the run about to be made.
"""
from pathlib import Path

import pytest

from core.file_manager import Project
from workflow.per_target_settings import (NEW_RUN_FILENAME, new_run_seed_path,
                                          seed_for_new_run)


def test_it_lives_in_the_targets_cache_folder(tmp_path):
    """Knut: "always … in the cache/ folder for the runN/ … or cal/ folders"."""
    proj = Project.create(tmp_path / "Demo", "Demo")
    run = proj.run("run1")
    path = new_run_seed_path(run)
    assert path.name == NEW_RUN_FILENAME
    assert path.parent.name == "cache"
    assert path.parent.parent == run.dir


@pytest.mark.parametrize("kind", ["run", "calibration"])
def test_every_target_kind_has_somewhere_to_put_it(tmp_path, kind):
    proj = Project.create(tmp_path / "Demo", "Demo")
    target = proj.run("run1") if kind == "run" else proj.calibration
    assert new_run_seed_path(target) is not None


def test_a_target_with_no_folder_has_nowhere(tmp_path):
    """Must answer None rather than inventing a path."""
    class Nowhere:
        pass
    assert new_run_seed_path(Nowhere()) is None


def test_the_calibration_owned_rows_are_stripped(tmp_path):
    """§4a N-2 — seeding from a calibration must not poison a profiling run."""
    snapshot = {
        "targen-f": {"enabled": True, "value": 0},
        "targen-s": {"enabled": True, "value": 20},
        "printtarg-r": {"enabled": True, "value": True},
        "targen-g": {"enabled": True, "value": 4},
        "printtarg-i": {"enabled": True, "value": "i1"},
    }
    seed = seed_for_new_run(snapshot)
    assert "targen-s" not in seed, "the calibration's 20 would be inherited"
    assert "targen-f" not in seed
    assert "printtarg-r" not in seed
    # …and everything else survives untouched.
    assert seed["targen-g"] == {"enabled": True, "value": 4}
    assert seed["printtarg-i"] == {"enabled": True, "value": "i1"}


def test_the_stripped_rows_match_the_tab_exactly():
    """A row added to _CAL_VALUES must not silently stop being stripped."""
    import ui.tabs.tab_chart as tc

    from workflow.per_target_settings import _CALIBRATION_OWNED
    tab_owned = {(tool, flag) for tool, flag, _v in tc.TabChart._CAL_VALUES}
    assert tab_owned == _CALIBRATION_OWNED, (
        f"the tab owns {sorted(tab_owned)} but the seed strips "
        f"{sorted(_CALIBRATION_OWNED)}"
    )


def test_an_empty_snapshot_is_harmless():
    assert seed_for_new_run({}) == {}
    assert seed_for_new_run(None) == {}
