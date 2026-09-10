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
    def _collect_ui_state(self):  return {}   # ui-state: real tab's concern
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
    assert json.loads(seed.read_text(encoding="utf-8"))["targen-g"]["value"] == "seeded"


def test_it_is_not_re_seeded_over_the_users_own_edits(tab_and_run):
    """§4a N-1 — the trap in the literal design."""
    import json
    tab, run, _proj = tab_and_run
    tab.save_target_settings()
    seed = new_run_seed_path(run)
    seed.write_text(json.dumps({"targen-g": {"enabled": True, "value": "MINE"}}), encoding="utf-8")

    tab._widgets["targen"][0].set_value("something else")
    tab.save_target_settings()
    assert json.loads(seed.read_text(encoding="utf-8"))["targen-g"]["value"] == "MINE", (
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
    new_run_seed_path(run).write_text("{ this is not json", encoding="utf-8")
    created = proj.new_run()
    assert tab._adopt_new_run_settings(created) is False
    assert not new_run_seed_path(run).exists(), "the bad block was left behind"


# ---------------------------------------------------------------------------
# §4a N-3, the half that was missing: WHAT the new run adopts
# ---------------------------------------------------------------------------
# The block is seeded once (N-1) and nothing between choosing "New run" and
# pressing Generate Chart is a write trigger, so the block a run carries is
# in practice a snapshot taken during the PREVIOUS run's build. Measured on
# screen, 2026-09-10: run 2's sheet was a SpectroScan chart and run 2's store
# said ColorMunki — run 1's instrument — and the next New run started from
# that, producing a two-page ColorMunki sheet where run 2 had one SpectroScan
# page, for the same 132 patches.
#
# THE FIXTURE BUILDS THAT FAILING SHAPE ON PURPOSE. Run 1 passes today, because
# run 1 is the one run whose block was seeded from its own build; a test built
# on run 1 would be green with the bug in place.
class _Target:
    def __init__(self, profile_run=""):
        self.profile_run = profile_run
        self.run_type = "profiling"

    def is_new_run(self):        return not self.profile_run
    def is_calibration(self):    return False
    def is_verification(self):   return False


class _Ctl:
    def __init__(self, project):
        self._project, self.target = project, _Target("")
        self.selected = None

    def project_or_none(self):        return self._project
    def set_profile_run(self, rid):   self.selected = rid


@pytest.fixture
def tab_with_a_stale_block(tmp_path, qapp):
    """A run whose ``cache/new_run.json`` holds ANOTHER run's settings."""
    import ui.tabs.tab_chart as tc
    for name in ("save_target_settings", "load_target_settings",
                 "_target_settings_key", "_new_run_seed_path",
                 "_seed_new_run_block", "clear_new_run_block",
                 "_adopt_new_run_settings", "_written_cache",
                 "_align_current_run_to_target"):
        setattr(_Tab, name, getattr(tc.TabChart, name))
    _Tab._CAL_VALUES = tc.TabChart._CAL_VALUES
    _Tab._write_target_text_into = lambda self, run: None   # #130 §9, not this

    proj = Project.create(tmp_path / "Demo", "Demo")
    run1 = proj.run("run1")
    run1.ensure_dir()

    # What the user has on screen for the run about to be made.
    tab = _Tab(run1, {"printtarg": [_Widget("-i", "SS")]})
    tab._target_ctl = _Ctl(proj)
    tab._new_run_seed_dir = run1.dir

    # …and the stale block, holding a DIFFERENT instrument.
    seed = new_run_seed_path(run1)
    seed.parent.mkdir(parents=True, exist_ok=True)
    seed.write_text(
        __import__("json").dumps({"printtarg-i": {"enabled": True,
                                                  "value": "CM"}}),
        encoding="utf-8")
    return tab, run1, proj, seed


def test_a_new_run_records_the_screen_not_the_stale_block(
        tab_with_a_stale_block):
    """§4a N-3, and Knut 2026-08-06: the settings *"copied into the new runs
    parameter slot"* are the ones the user generated with."""
    tab, _run1, proj, _seed = tab_with_a_stale_block

    tab._align_current_run_to_target()          # what Generate Chart does

    made = proj.run(tab._target_ctl.selected)
    got = made.load_meta().create_chart_settings["printtarg-i"]["value"]
    assert got == "SS", (
        f"the new run recorded {got!r} — the stale block's value — instead of "
        f"'SS', which is what was on screen when Generate Chart was pressed"
    )


def test_the_refresh_writes_the_block_and_never_another_runs_meta(
        tab_with_a_stale_block):
    """The refresh must land in ``cache/new_run.json``.

    `store_for_target` answers None for "New run" and `set_profile_run` runs
    afterwards, so the store really is None here — but the call passes None
    explicitly, and this pins that it cannot become a write of the run the bar
    still points at.
    """
    tab, run1, _proj, seed = tab_with_a_stale_block
    before = run1.load_meta().create_chart_settings

    tab._align_current_run_to_target()

    assert run1.load_meta().create_chart_settings == before, (
        "the refresh wrote into run1's meta.json instead of its New-run block"
    )
    assert not seed.exists(), "the block outlived the run it specified (N-3)"


def test_the_block_is_still_never_re_seeded_from_a_run(tab_with_a_stale_block):
    """N-1 is untouched: only the New run's own screen may overwrite a block,
    and `_seed_new_run_block` still refuses to."""
    import json
    tab, run1, _proj, seed = tab_with_a_stale_block
    tab._seed_new_run_block(run1, {"printtarg-i": {"enabled": True,
                                                   "value": "ELSEWHERE"}})
    assert json.loads(seed.read_text(encoding="utf-8"))[
        "printtarg-i"]["value"] == "CM"
