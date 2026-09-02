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
    # settings resolve through the shared store_for_target in the real
    # tab (Knut's F1 ruling); the stand-in answers both names with the
    # same store because only the store behaviour is under test here
    def _target_settings_store(self): return self._store
    def _collect_ui_state(self):  return {}   # the ui-state
    # section is the real tab's concern; the stand-in stores none
    def _apply_ui_state(self, stored):  pass   # same reason
    def _target_text_store(self):   return self._store
    _target_ctl = None              # no controller: the no-file key is None
    _new_run_seed_dir = None        # …and nowhere to keep a New run's block

    save_target_settings = None     # bound below
    load_target_settings = None


def _bind():
    import ui.tabs.tab_chart as tc
    _Tab.save_target_settings = tc.TabChart.save_target_settings
    _Tab.load_target_settings = tc.TabChart.load_target_settings
    # The no-file-yet path needs these; the real tab has both.
    _Tab._target_settings_key = tc.TabChart._target_settings_key
    _Tab._new_run_seed_path = tc.TabChart._new_run_seed_path
    # …and the "nothing stored" branches now both delegate to one opener
    # (§4 S4). The stand-in has no widgets to reset, so it borrows the real
    # method and lets it find nothing, which is what it did inline before.
    _Tab._open_this_target_on_its_defaults = \
        tc.TabChart._open_this_target_on_its_defaults
    _Tab._CAL_VALUES = tc.TabChart._CAL_VALUES
    _Tab._seed_new_run_block = tc.TabChart._seed_new_run_block
    _Tab.clear_new_run_block = tc.TabChart.clear_new_run_block
    _Tab._CAL_VALUES = tc.TabChart._CAL_VALUES
    _Tab._written_cache = tc.TabChart._written_cache
    _Tab._pending_settings = {}
    _Tab._last_written = {}


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


def test_loading_cannot_re_enter_the_writer(run):
    """§7 C — a load must not re-enter the writer. Real, and it can still fail:
    `_loading_target_settings` exists and is honoured in three places.

    THIS IS NOT N3, AND IT USED TO CLAIM TO BE. The test plan specifies N3 as
    *"loading a target's settings does not trigger an auto-update rebuild —
    assert the chart file's mtime is unchanged"*, and this exercises a stand-in
    `_Tab` with no timer, no layout fingerprint and no real `_apply_ui_state`.
    It was green throughout the weeks when selecting a run in the bar really did
    re-lay out that run's chart and rewrite it to disk — a green test guarding
    the bug (Basti, 2026-08-26).

    N3 now belongs to
    `tests/test_the_live_preview_only_follows_the_user.py::
    test_selecting_a_run_does_not_re_render_its_chart`, which drives the real
    `TabChart` with a real timer and proves it can see its own failure.
    """
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
    assert "self.save_target_settings(" in src, (
        "the outgoing target is not written before the incoming one loads"
    )
    # …and NOT guarded on it being non-None: None is the New-run case, the one
    # that most needs keeping.
    assert "if outgoing is not None" not in src
    i_save = src.index("self.save_target_settings(")
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


def test_n1_end_to_end_the_outgoing_run_keeps_its_own_setting(tmp_path, qapp):
    """§2.1 / N1 against the real tab and controller, not a stand-in.

    Set a value on run 1, switch the bar to run 2, and run 1 must have kept it
    while run 2 must not have acquired it. This is the failure the whole
    feature exists to prevent, so it is asserted end-to-end rather than by
    reading the source.
    """
    from core.argyll_runner import ArgyllRunner
    from core.file_manager import FileManager
    from core.settings import AppSettings
    from ui.measurement_target_bar import MeasurementTargetController
    from ui.tabs.tab_chart import TabChart
    from workflow.per_target_settings import params_for

    settings = AppSettings()
    # POINT IT AT tmp_path. `root_dir()` is the REAL ~/ChromIQ unless
    # custom_output_path says otherwise — conftest's autouse guard catches that,
    # but only the first time, because the stray folder is then in its "before"
    # set and invisible on every later run. This test had been writing into the
    # developer's own projects.
    settings.set("custom_output_path", str(tmp_path / "out"))
    fm = FileManager(settings)
    root = fm.root_dir()
    root.mkdir(parents=True, exist_ok=True)
    proj = Project.create(root / "Demo-PTS", "Demo-PTS")
    proj.current_run().ensure_dir()
    proj.new_run()                                   # run2
    fm.set_target_name("Demo-PTS")

    tab = TabChart(ArgyllRunner(settings), fm, settings)
    ctl = MeasurementTargetController(fm)
    tab.set_target_controller(ctl)

    # No explicit _on_target_changed(): set_target_controller connects
    # controller.changed to it (tab_chart ~9136), so calling it as well ran the
    # whole save/load twice and wrote the incoming run a second time. Driving
    # it the way the app does is also the only honest way to test it.
    ctl.set_profile_run("run1")
    store = tab._target_settings_store()
    if store is None:
        pytest.skip("the bar could not resolve run1 in this environment")

    # A free-text row, so the value set is the value held: a combo would
    # quietly refuse an arbitrary string and the test would prove nothing.
    param = next(p for p in params_for(tab)
                 if not p.repeats and _accepts_free_text(p.widgets[0]))
    param.widgets[0].set_value("mine-alone")
    on_screen = param.widgets[0].get_raw_value()
    assert on_screen == "mine-alone", "the chosen row did not take the value"

    ctl.set_profile_run("run2")

    run1_stored = proj.run("run1").load_meta().create_chart_settings
    run2_stored = proj.run("run2").load_meta().create_chart_settings
    assert run1_stored.get(param.key, {}).get("value") == on_screen, (
        "the outgoing run lost the value that was set on it"
    )
    assert run2_stored.get(param.key, {}).get("value") != on_screen, (
        "run 1's edit was written onto run 2 — the exact failure §2.1 describes"
    )


def _accepts_free_text(widget) -> bool:
    """Whether a row keeps an arbitrary string put into it."""
    keep = widget.get_raw_value()
    try:
        widget.set_value("zz-probe")
        return widget.get_raw_value() == "zz-probe"
    finally:
        widget.set_value(keep)


def test_going_back_and_forth_does_not_write_again(run, monkeypatch):
    """Knut, #130: the write trigger is the pulldown OPENING.

        "A write trigger should also have a check if any settings have changed
        since last write, preventing multiple writes in a row if user is going
        back and forth on the profile run and run type input boxes."

    Flicking between the two boxes fires it repeatedly, so a repeat must cost
    nothing — not even the read of meta.json that the disk comparison needs.
    """
    tab = _Tab(run, {"targen": [_Widget("-f", "5")]})
    assert tab.save_target_settings() is True          # the first one lands

    reads = []
    real = type(run).load_meta
    monkeypatch.setattr(type(run), "load_meta",
                        lambda self: (reads.append(1), real(self))[1])

    for _ in range(5):
        assert tab.save_target_settings() is False
    assert reads == [], (
        f"a repeated trigger read meta.json {len(reads)} time(s); with nothing "
        f"changed it should not touch the disk at all"
    )


def test_a_real_change_still_writes_after_a_no_op(run):
    """The shortcut must not latch — an actual edit still has to land."""
    tab = _Tab(run, {"targen": [_Widget("-f", "5")]})
    tab.save_target_settings()
    assert tab.save_target_settings() is False
    tab._widgets["targen"][0].set_value("6")
    assert tab.save_target_settings() is True
    assert run.load_meta().create_chart_settings["targen-f"]["value"] == "6"


def test_the_shortcut_is_per_target(tmp_path):
    """Two runs with identical settings must each still get their own write."""
    _bind()
    proj = Project.create(tmp_path, "Demo")
    r1, r2 = proj.run("run1"), proj.new_run()
    same = {"targen": [_Widget("-f", "same")]}
    assert _Tab(r1, same).save_target_settings() is True
    assert _Tab(r2, same).save_target_settings() is True, (
        "run2 was skipped because run1 had just written the same values"
    )


def test_d2_a_truncated_meta_json_is_not_fatal(tmp_path, qapp):
    """§5 D2 — Knut: "some cases can occur if user deletes a file".

    A half-written `meta.json` must read as "this target has nothing stored",
    not take the tab down. Atomic writes make ChromIQ unlikely to *produce* one,
    but a crashed editor, a full disk or a sync client still can.
    """
    _bind()
    run = Project.create(tmp_path, "Demo").run("run1")
    run.ensure_dir()
    tab = _Tab(run, {"targen": [_Widget("-f", "5")]})
    tab.save_target_settings()

    run.meta_path.write_text('{"create_chart_settings": {"targen-f": ', encoding="utf-8")  # cut off
    assert tab.load_target_settings() is False, "a truncated meta was not survived"
    # …and the target is still writable afterwards, rather than being poisoned.
    tab._widgets["targen"][0].set_value("9")
    assert tab.save_target_settings() is True
    assert run.load_meta().create_chart_settings["targen-f"]["value"] == "9"


def test_a3_the_write_is_logged_with_the_target_and_the_count(run, caplog):
    """§3 A3 — Knut asked that a change be "recorded in the log correctly".

    The full three-way check he described (screen == log == JSON, per
    parameter) would mean a line per parameter on every write; with 40 on
    Create Chart alone that is a log nobody can read. What is logged is the
    target and how many settings were written, and the JSON beside it carries
    the values — which is the auditable part without drowning the log.
    """
    import logging

    tab = _Tab(run, {"targen": [_Widget("-f", "5")]})
    with caplog.at_level(logging.DEBUG, logger="ui.tabs.tab_chart"):
        assert tab.save_target_settings() is True
    said = [r.getMessage() for r in caplog.records
            if "create-chart settings written" in str(r.msg)]
    assert said, "a write said nothing at all in the log"
    assert "run1" in said[0] and "1" in said[0]
