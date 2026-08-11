"""Build Profile's settings follow the target too (#130 §5).

Built on `_m_collect_preset_data` / `_m_apply_preset_data`, the matched pair the
preset feature already maintains. I had told Knut this tab had no apply-side and
that writing one was the work — that was wrong, and reusing the pair means one
description of what a Build Profile setting is rather than two that can drift.
"""
import pytest

from core.file_manager import CalibrationMeta, Project, RunMeta


class _Store:
    def __init__(self, tmp_path):
        self.dir = tmp_path / "run1"
        self.dir.mkdir(parents=True, exist_ok=True)
        self.id = "run1"
        self._meta = RunMeta()

    def load_meta(self):        return self._meta
    def save_meta(self, m):     self._meta = m


class _Tab:
    """The three tab methods the pair depends on, and nothing else."""

    _profile_written: dict = {}

    def __init__(self, data):
        self._data = dict(data)
        self._restored = []
        self._applied = []
        self._loading_profile_settings = False
        self._profile_written = {}
        self._target_ctl = None

    def _collect_guided_profile_fields(self): return {}   # the
    # guided-module fields are the real tab's concern (Knut beta.3)
    def _apply_guided_profile_fields(self, stored): pass
    def _m_collect_preset_data(self):   return dict(self._data)
    def _m_apply_preset_data(self, d):  self._applied.append(d); self._data = dict(d)
    def _restore_defaults(self):        self._restored.append(True)


@pytest.fixture
def tab_and_store(tmp_path, qapp):
    import ui.tabs.tab_profile as tp
    for name in ("save_target_settings", "load_target_settings",
                 "_profile_written_cache"):
        setattr(_Tab, name, getattr(tp.TabProfile, name))
    return _Tab({"quality": "h", "algorithm": "l"}), _Store(tmp_path)


def test_it_stores_what_the_preset_pair_reads(tab_and_store):
    tab, store = tab_and_store
    assert tab.save_target_settings(store) is True
    assert store.load_meta().profile_settings == {"quality": "h", "algorithm": "l"}


def test_a_repeat_costs_nothing(tab_and_store):
    tab, store = tab_and_store
    assert tab.save_target_settings(store) is True
    for _ in range(3):
        assert tab.save_target_settings(store) is False


def test_a_real_change_still_lands(tab_and_store):
    tab, store = tab_and_store
    tab.save_target_settings(store)
    tab._data["quality"] = "u"
    assert tab.save_target_settings(store) is True
    assert store.load_meta().profile_settings["quality"] == "u"


def test_a_write_never_resurrects_a_deleted_target(tab_and_store):
    """Knut's beta.102 rule — the fourth place this shape has appeared."""
    import shutil
    tab, store = tab_and_store
    tab.save_target_settings(store)
    shutil.rmtree(store.dir)
    assert tab.save_target_settings(store) is False
    assert not store.dir.exists()


def test_loading_is_guarded_against_re_entry(tab_and_store):
    tab, store = tab_and_store
    tab._loading_profile_settings = True
    assert tab.save_target_settings(store) is False


def test_the_written_cache_is_per_tab(tab_and_store):
    tab_a, store = tab_and_store
    tab_a.save_target_settings(store)
    tab_b = _Tab({"quality": "m"})
    assert tab_b.save_target_settings(store) is True, (
        "the second tab inherited the first's 'already written' marks"
    )


def test_a_target_with_nothing_stored_falls_back_to_defaults(tab_and_store, monkeypatch):
    """The Measure tab's bug, not repeated here: an empty target must not keep
    the previous target's values on screen."""
    tab, store = tab_and_store
    monkeypatch.setattr("workflow.per_target_settings.store_for_target",
                        lambda _c: store)
    store.load_meta().profile_settings = {}
    assert tab.load_target_settings() is False
    assert tab._restored, "nothing put the tab back to its defaults"


def test_a_stored_target_is_applied(tab_and_store, monkeypatch):
    tab, store = tab_and_store
    monkeypatch.setattr("workflow.per_target_settings.store_for_target",
                        lambda _c: store)
    meta = store.load_meta()
    meta.profile_settings = {"quality": "u"}
    store.save_meta(meta)
    assert tab.load_target_settings() is True
    assert tab._applied == [{"quality": "u"}]


def test_both_meta_classes_carry_the_field():
    for cls in (RunMeta, CalibrationMeta):
        assert cls().profile_settings == {}
        assert cls.from_dict({"profile_settings": {"quality": "h"}}
                             ).profile_settings == {"quality": "h"}


def test_the_three_tabs_share_one_store_resolver():
    import inspect

    import ui.tabs.tab_chart as tc
    import ui.tabs.tab_measure as tm
    import ui.tabs.tab_profile as tp
    assert "store_for_target" in inspect.getsource(tm.TabMeasure.save_target_settings)
    assert "store_for_target" in inspect.getsource(tp.TabProfile.save_target_settings)
    assert hasattr(tc.TabChart, "save_target_settings")
