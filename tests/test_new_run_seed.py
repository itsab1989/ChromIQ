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


# ---------------------------------------------------------------------------
# The wiring: seeded once, adopted by the run, then gone
# ---------------------------------------------------------------------------
class _Widget:
    def __init__(self, flag, value="", enabled=True):
        self.flag, self._v, self._e = flag, value, enabled

    def get_raw_value(self):        return self._v
    def set_value(self, v):         self._v = v
    @property
    def is_enabled_by_user(self):   return self._e
    def set_user_enabled(self, b):  self._e = b


class _Tab:
    _target_ctl = None
    _new_run_seed_dir = None
    _last_written: dict = {}
    _pending_settings: dict = {}

    def __init__(self, store, widgets):
        self._store, self._widgets = store, widgets
        self._loading_target_settings = False
        self._last_written = {}

    def per_target_widgets(self):   return self._widgets
    def _target_text_store(self):   return self._store
    _target_settings_store = _target_text_store   # same store here: the
    # stand-in tests the seed block, not the run-type store split (F1)


@pytest.fixture
def tab_and_run(tmp_path, qapp):
    import ui.tabs.tab_chart as tc
    for name in ("save_target_settings", "load_target_settings",
                 "_target_settings_key", "_new_run_seed_path",
                 "_seed_new_run_block", "clear_new_run_block",
                 "_adopt_new_run_settings", "_written_cache"):
        setattr(_Tab, name, getattr(tc.TabChart, name))
    _Tab._CAL_VALUES = tc.TabChart._CAL_VALUES
    proj = Project.create(tmp_path / "Demo", "Demo")
    run = proj.run("run1")
    run.ensure_dir()
    return _Tab(run, {"targen": [_Widget("-g", "seeded")]}), run, proj


def test_the_block_is_seeded_when_the_target_is_written(tab_and_run):
    tab, run, _proj = tab_and_run
    assert tab.save_target_settings() is True
    seed = new_run_seed_path(run)
    assert seed.is_file(), "no New-run block was seeded"
    import json
    assert json.loads(seed.read_text())["targen-g"]["value"] == "seeded"


def test_it_is_not_re_seeded_over_the_users_own_edits(tab_and_run):
    """§4a N-1 — the trap in the literal design."""
    import json
    tab, run, _proj = tab_and_run
    tab.save_target_settings()
    seed = new_run_seed_path(run)
    seed.write_text(json.dumps({"targen-g": {"enabled": True, "value": "MINE"}}))

    tab._widgets["targen"][0].set_value("something else")
    tab.save_target_settings()
    assert json.loads(seed.read_text())["targen-g"]["value"] == "MINE", (
        "re-seeding overwrote what the user had set up for the New run"
    )


def test_the_new_run_adopts_it_and_the_block_is_gone(tab_and_run):
    """§4a N-3 — otherwise the run after next inherits a stale copy."""
    tab, run, proj = tab_and_run
    tab.save_target_settings()
    seed = new_run_seed_path(run)
    assert seed.is_file()

    created = proj.new_run()
    assert tab._adopt_new_run_settings(created) is True
    assert created.load_meta().create_chart_settings["targen-g"]["value"] == "seeded"
    assert not seed.exists(), "the block outlived the run it specified"


def test_adopting_when_there_is_no_block_is_harmless(tab_and_run):
    tab, _run, proj = tab_and_run
    assert tab._adopt_new_run_settings(proj.new_run()) is False


def test_a_corrupt_block_does_not_stop_the_run_being_created(tab_and_run):
    """cache/ is safe to delete; a bad block must behave like a missing one."""
    tab, run, proj = tab_and_run
    tab.save_target_settings()
    new_run_seed_path(run).write_text("{ this is not json")
    created = proj.new_run()
    assert tab._adopt_new_run_settings(created) is False
    assert not new_run_seed_path(run).exists(), "the bad block was left behind"
