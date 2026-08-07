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
