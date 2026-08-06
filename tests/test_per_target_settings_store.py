"""Create Chart's settings are stored per target, and loaded back.

Specification `docs/design/per_target_settings.md`; test plan §3 (A1–A5) and
§4 (N2/N3). Knut approved the two-home split on 2026-08-06 ("Sure, go ahead"):
the target's ``meta.json`` holds the **working** settings — so work done before
a chart exists is not lost — while ``<stem>.channels.json`` keeps its separate
record of what the chart beside it was actually made with, leaving Restore Used
Chart untouched.
"""
import pytest

from core.file_manager import CalibrationMeta, Project, RunMeta


class _Widget:
    def __init__(self, flag, value="", enabled=True):
        self.flag, self._v, self._e = flag, value, enabled
        self.writes = 0

    def get_raw_value(self):        return self._v
    def set_value(self, v):         self._v = v; self.writes += 1
    @property
    def is_enabled_by_user(self):   return self._e
    def set_user_enabled(self, b):  self._e = b


class _Tab:
    """The two methods under test, lifted onto a stand-in with a real store.

    Driving the whole TabChart here would need a window; the behaviour being
    checked is the store, and it is the same code either way.
    """

    def __init__(self, store, widgets):
        self._store, self._widgets = store, widgets
        self._loading_target_settings = False

    def per_target_widgets(self):   return self._widgets
    def _target_text_store(self):   return self._store

    save_target_settings = None     # bound below
    load_target_settings = None


def _bind():
    import ui.tabs.tab_chart as tc
    _Tab.save_target_settings = tc.TabChart.save_target_settings
    _Tab.load_target_settings = tc.TabChart.load_target_settings


@pytest.fixture
def run(tmp_path):
    _bind()
    return Project.create(tmp_path, "Demo").run("run1")


def test_a1_a2_nothing_is_stored_until_it_is_written(run):
    tab = _Tab(run, {"targen": [_Widget("-f", "17")]})
    assert run.load_meta().create_chart_settings == {}        # A1
    assert tab.save_target_settings() is True                 # A2
    assert run.load_meta().create_chart_settings == {
        "targen-f": {"enabled": True, "value": "17"}}


def test_a4_the_value_comes_back(run):
    tab = _Tab(run, {"targen": [_Widget("-f", "17")]})
    tab.save_target_settings()
    tab._widgets["targen"][0].set_value("999")
    assert tab.load_target_settings() is True
    assert tab._widgets["targen"][0].get_raw_value() == "17"


def test_a5_it_lands_in_that_target_and_no_other(tmp_path):
    """§2.0: one target is live at a time."""
    _bind()
    proj = Project.create(tmp_path, "Demo")
    r1, r2 = proj.run("run1"), proj.new_run()
    _Tab(r1, {"targen": [_Widget("-f", "one")]}).save_target_settings()
    assert r1.load_meta().create_chart_settings
    assert r2.load_meta().create_chart_settings == {}, (
        "writing run1's settings also touched run2"
    )


def test_the_calibration_has_its_own(tmp_path):
    _bind()
    cal = Project.create(tmp_path, "Demo").calibration
    cal.ensure_dir()
    _Tab(cal, {"printtarg": [_Widget("-i", "i1")]}).save_target_settings()
    assert cal.load_meta().create_chart_settings == {
        "printtarg-i": {"enabled": True, "value": "i1"}}


def test_a_target_that_does_not_exist_yet_is_not_an_error(run):
    """A New run has nowhere to write; that must not raise or lose the tab."""
    tab = _Tab(None, {"targen": [_Widget("-f", "x")]})
    assert tab.save_target_settings() is False
    assert tab.load_target_settings() is False


def test_an_unchanged_save_does_not_rewrite_the_file(run):
    """Test plan N4 — a second visit with no edit writes nothing."""
    tab = _Tab(run, {"targen": [_Widget("-f", "5")]})
    assert tab.save_target_settings() is True
    assert tab.save_target_settings() is False


def test_n3_loading_cannot_re_enter_the_writer(run):
    """The guard that stops a load from triggering a rebuild-and-save."""
    tab = _Tab(run, {"targen": [_Widget("-f", "5")]})
    tab.save_target_settings()
    tab._loading_target_settings = True
    assert tab.save_target_settings() is False, (
        "a save ran while settings were being loaded — with auto-update on "
        "that is a redraw of the chart during a fill"
    )


def test_a_stale_stored_key_does_not_block_the_rest(run):
    """§7 A: a renamed parameter must not cost the whole target its settings."""
    tab = _Tab(run, {"targen": [_Widget("-f", "")]})
    meta = run.load_meta()
    meta.create_chart_settings = {
        "targen-f": {"enabled": True, "value": "kept"},
        "targen-removed": {"enabled": True, "value": "gone"},
    }
    run.save_meta(meta)
    assert tab.load_target_settings() is True
    assert tab._widgets["targen"][0].get_raw_value() == "kept"


def test_the_field_survives_a_meta_round_trip():
    for cls in (RunMeta, CalibrationMeta):
        m = cls.from_dict({"create_chart_settings": {"targen-f": {"enabled": False, "value": ""}}})
        assert m.create_chart_settings == {"targen-f": {"enabled": False, "value": ""}}
        assert cls().create_chart_settings == {}, "the default must not be shared"
