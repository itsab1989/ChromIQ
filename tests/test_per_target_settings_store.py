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


# ---------------------------------------------------------------------------
# The events (§2 L1, §3 W6) and the two hazards that gate the build
# ---------------------------------------------------------------------------
def test_n1_a_target_change_writes_the_outgoing_target_first():
    """§2.1 — the hazard, asserted the way it would actually break.

    `_on_target_changed` runs *after* the bar has switched, so writing "the
    current target" there would record the old target's edits onto the new one.
    The outgoing store is remembered and passed explicitly.
    """
    import inspect

    import ui.tabs.tab_chart as tc
    src = inspect.getsource(tc.TabChart._on_target_changed)
    assert "self.save_target_settings(outgoing)" in src, (
        "the outgoing target is not written before the incoming one loads"
    )
    i_save = src.index("save_target_settings(outgoing)")
    i_load = src.index("self.load_target_settings()")
    assert i_save < i_load, "the load runs before the write — N1 is violated"
    assert src.index("self._settings_store = ") > i_load, (
        "the remembered store is replaced before the load, so the next change "
        "would write to the wrong target"
    )


def test_save_accepts_an_explicit_store():
    """Without this, N1 cannot be implemented at all."""
    import inspect

    import ui.tabs.tab_chart as tc
    sig = inspect.signature(tc.TabChart.save_target_settings)
    assert "store" in sig.parameters


def test_w6_the_tab_being_left_is_written_and_the_one_entered_is_loaded():
    import inspect

    import ui.main_window as mw
    src = inspect.getsource(mw.MainWindow._on_tab_changed)
    i_save = src.index("_save_settings_of_tab_left()")
    i_load = src.index("_load_settings_of_tab_entered(")
    assert i_save < i_load, "the entering tab loads before the leaving one writes"


def test_w6_app_quit_counts_as_leaving_the_visible_tab():
    """Qt raises no tab-change on quit, so it is wired explicitly."""
    import inspect

    import ui.main_window as mw
    assert "_save_settings_of_tab_left()" in inspect.getsource(mw.MainWindow.closeEvent)


def test_a_tab_out_of_scope_is_not_asked():
    """Print Chart and Check & Refine have no store; asking must not raise."""
    import inspect

    import ui.main_window as mw
    src = inspect.getsource(mw.MainWindow._load_settings_of_tab_entered)
    assert 'hasattr(widget, "load_target_settings")' in src


def test_a_write_never_resurrects_a_deleted_target(tmp_path):
    """Knut's beta.102 sequence: delete the project, and it stays deleted.

    `save_meta()` creates what it needs, and both "leaving a tab" and "quitting"
    fire immediately after a delete — so without this guard the folder came
    straight back with a meta.json in it. His existing test caught it the moment
    the events were wired; this one states the rule where the code is.
    """
    import shutil

    _bind()
    run = Project.create(tmp_path, "Demo").run("run1")
    tab = _Tab(run, {"targen": [_Widget("-f", "5")]})
    assert tab.save_target_settings() is True

    shutil.rmtree(run.dir)
    assert tab.save_target_settings() is False, "the write recreated the target"
    assert not run.dir.exists(), "the deleted run came back"
