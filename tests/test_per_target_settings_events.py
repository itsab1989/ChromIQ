"""§2/§3 event coverage: L-events, and the negatives that get forgotten.

Test plan §4. The negative half is the point of this file — "it writes when it
should" is easy to believe and easy to test; "it writes at no other time" is
what actually keeps a run's settings from being overwritten by another's, and
it is the half nobody writes tests for.

Driven against all three tabs that have a store, because a rule that holds on
one and not the others is how this feature has gone wrong twice already.
"""
import inspect

import pytest

TABS = ("ui.tabs.tab_chart:TabChart",
        "ui.tabs.tab_measure:TabMeasure",
        "ui.tabs.tab_profile:TabProfile")


def _tab_class(path: str):
    mod, name = path.split(":")
    return getattr(__import__(mod, fromlist=[name]), name)


@pytest.mark.parametrize("path", TABS)
def test_every_storing_tab_offers_the_same_two_methods(path):
    """MainWindow calls these by duck-typing; a rename breaks it silently."""
    cls = _tab_class(path)
    for name in ("save_target_settings", "load_target_settings"):
        assert callable(getattr(cls, name, None)), f"{path} has no {name}"


@pytest.mark.parametrize("path", TABS)
def test_n2_nothing_is_written_outside_an_event(path):
    """Typing must not write — settings are recorded when they are USED.

    Asserted structurally: the save is reached from the events in §3, and no
    tab connects it to a widget's `textChanged`/`valueChanged`/`toggled`. A tab
    that did would write on every keystroke, which is what §3 forbids.
    """
    src = inspect.getsource(_tab_class(path))
    for signal in ("textChanged.connect(self.save_target_settings",
                   "valueChanged.connect(self.save_target_settings",
                   "toggled.connect(self.save_target_settings",
                   "currentIndexChanged.connect(self.save_target_settings"):
        assert signal not in src, (
            f"{path} writes on every keystroke — §3 says settings are recorded "
            f"when they are used, not while someone is typing"
        )


@pytest.mark.parametrize("path", TABS)
def test_a_deleted_target_is_never_recreated_by_a_write(path):
    """Knut's beta.102 rule, held on every tab rather than one at a time.

    It has appeared four times: the Create Chart write, the New-run block, and
    both later tabs. Each was found by his test rather than by us, so this
    states the rule where a new tab will trip over it.
    """
    src = inspect.getsource(getattr(_tab_class(path), "save_target_settings"))
    assert "is_dir()" in src, (
        f"{path}'s save does not check the target's folder still exists, so it "
        f"would recreate a project the user deleted"
    )


@pytest.mark.parametrize("path", TABS)
def test_the_written_cache_is_never_shared_between_tabs(path):
    """A bare class-level dict made one tab's writes suppress another's."""
    cls = _tab_class(path)
    src = inspect.getsource(cls)
    caches = [n for n in ("_written_cache", "_measure_written_cache",
                          "_profile_written_cache") if hasattr(cls, n)]
    assert caches, f"{path} has no per-instance write cache accessor"
    for name in caches:
        body = inspect.getsource(getattr(cls, name))
        assert "__dict__" in body, (
            f"{cls.__name__}.{name} does not force an instance dict, so every "
            f"tab would share one and writes would be silently skipped"
        )
    assert src.count("self._last_written = {}") <= 2


@pytest.mark.parametrize("path", TABS)
def test_loading_cannot_re_enter_the_writer(path):
    """§7 B — filling the rows fires their signals; a save then must not run."""
    save = inspect.getsource(getattr(_tab_class(path), "save_target_settings"))
    assert "_loading" in save, (
        f"{path}'s save is not guarded against running during a load"
    )


@pytest.mark.parametrize("path", TABS)
def test_an_empty_target_does_not_keep_the_last_ones_values(path):
    """The fault Measure shipped with, stated for every tab.

    Returning early when a target has nothing stored leaves the PREVIOUS
    target's values on screen — which is a setting leaking between runs, the
    thing this whole feature exists to stop.
    """
    load = inspect.getsource(getattr(_tab_class(path), "load_target_settings"))
    # Comments are not code, and these methods name `_restore_defaults` in
    # their prose. An earlier version of this test matched the comment and went
    # green with the fault re-introduced — the exact "a test can guard the bug"
    # trap this project has been caught by before.
    load = "\n".join(l for l in load.splitlines()
                     if not l.lstrip().startswith("#"))
    assert ("reset_to_default" in load or "_restore_defaults" in load), (
        f"{path} leaves the previous target's values on screen when the new "
        f"one has nothing stored"
    )


def test_l1_and_w6_are_wired_once_in_main_window():
    """The tab being left writes before the tab being entered loads."""
    import ui.main_window as mw
    src = inspect.getsource(mw.MainWindow._on_tab_changed)
    assert src.index("_save_settings_of_tab_left()") < \
           src.index("_load_settings_of_tab_entered(")


def test_w6_quit_writes_the_visible_tab():
    import ui.main_window as mw
    assert "_save_settings_of_tab_left()" in inspect.getsource(mw.MainWindow.closeEvent)


def test_the_target_change_trigger_reaches_every_tab():
    """One signal, so a tab added later is covered without new wiring."""
    import ui.main_window as mw
    src = inspect.getsource(mw.MainWindow)
    assert "about_to_change_target.connect(" in src
    assert "_save_settings_of_visible_tab" in src


def test_f3_the_calibration_knobs_run_before_the_load():
    """F3 (ruled by Sebastian, 2026-08-11): a setting's owner is the SELECTED
    target. The knobs must run BEFORE the load in _on_target_changed, so the
    incoming target's own six rows always have the last word — with the old
    order the pre-calibration restore clobbered the freshly loaded values and
    the next write filed the calibration's rows into the first run visited."""
    from ui.tabs.tab_chart import TabChart
    src = inspect.getsource(TabChart._on_target_changed)
    assert src.index("_apply_calibration_knobs(") < \
        src.index("self.load_target_settings()")


def test_f3_the_six_rows_are_only_skipped_on_the_calibration_itself():
    """The nothing-stored reset skips the calibration-owned rows only while
    the calibration IS the selected target; a run with nothing stored opens
    on ALL its defaults (§4 S4/S5), six rows included."""
    from ui.tabs.tab_chart import TabChart
    src = inspect.getsource(TabChart.load_target_settings)
    assert "if on_calibration else set()" in src


def test_l3_l4_the_visible_tab_reloads_on_a_target_change():
    """Knut, 2026-08-11 (approving fault F2): every tab reloads the moment a
    new target is selected, the same central way — Measure and Build Profile
    used to keep the OLD target's values on screen while visible, and then
    filed them onto the new target when the tab was left (the §2.1
    corruption, from the load side)."""
    import ui.main_window as mw
    src = inspect.getsource(mw.MainWindow)
    assert "changed.connect(self._load_settings_of_visible_tab)" in src
    loader = inspect.getsource(mw.MainWindow._load_settings_of_visible_tab)
    assert "load_target_settings" in loader


# ---------------------------------------------------------------------------
# A BUILD'S OWN ROWS SURVIVE THE RUN-CHANGE THAT THE BUILD ITSELF CAUSED
# ---------------------------------------------------------------------------
# Shipped in 4.1.2 GA and found by Knut in 4.1.3-beta.5 (#164):
#
#   *"Loading preset from icon button 'built-in presets' in Create Chart tab …
#   When Clicking Generate Chart the following message comes in log window,
#   while preview is empty: [ERROR] Nothing for targen to generate. … This
#   should not happen, as targen was never used to generate patches for the
#   preset."*
#
# Loading a built-in preset builds its own .ti1 and then puts the bar on the
# new run. On a FRESH project that is a change of run, so §4 S4's "a target
# with nothing stored opens on its defaults" fired and reset targen's rows —
# and the factory default for "Total Patch Count (-f)" is ZERO. The preset's
# signature no longer matched, the next Generate abandoned the preset's patch
# set and fell through to targen, and the pre-flight guard refused.
#
# On the prebuilt-file presets it was worse: Auto is on there, so no error
# appeared and a DIFFERENT chart was built in silence.


def _chart_tab_with_an_empty_target(qapp):
    """A TabChart whose selected target has nothing stored — the branch §4 S4
    describes, and the one that used to wipe the build."""
    from core.argyll_runner import ArgyllRunner
    from core.file_manager import FileManager
    from core.settings import AppSettings
    from ui.tabs.tab_chart import TabChart

    st = AppSettings()
    tab = TabChart(ArgyllRunner(st), FileManager(st), st)

    class _Meta:
        create_chart_settings = None

    class _Store:
        def load_meta(self):
            return _Meta()

        def save_meta(self, meta):
            pass

    tab._target_settings_store = lambda: _Store()
    tab._target_settings_key = lambda: "test-target"
    return tab


def _targen_f(tab):
    from workflow.per_target_settings import params_for

    for prm in params_for(tab):
        if (prm.tool, prm.flag) == ("targen", "-f"):
            return prm.widgets[0]
    raise AssertionError("targen -f is not among the per-target rows")


def test_a_preset_build_is_not_reset_by_the_run_it_created(qapp):
    """The row the preset's binding depends on must survive."""
    tab = _chart_tab_with_an_empty_target(qapp)
    _targen_f(tab).set_value(84)
    tab._layout_owned_by_build = True          # the chart on screen is the build's
    tab.load_target_settings()
    assert _targen_f(tab).get_value() == "84", (
        "the build's own patch count was reset by the run change it caused — "
        "the next Generate abandons the preset and falls through to targen")


def test_a_plain_target_switch_still_opens_on_the_defaults(qapp):
    """§4 S4 is not weakened: with no build owning the rows, a target that has
    nothing stored still opens on its defaults."""
    tab = _chart_tab_with_an_empty_target(qapp)
    _targen_f(tab).set_value(84)
    tab._layout_owned_by_build = False
    tab.load_target_settings()
    assert _targen_f(tab).get_value() == "0", (
        "a target with nothing stored no longer opens on its defaults")
