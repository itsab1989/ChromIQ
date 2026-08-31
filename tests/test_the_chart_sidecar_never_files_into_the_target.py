"""Visiting a run must not destroy the setting stored on it (K3/K4).

Reported from beta 5: pick an instrument on run 1, look at run 2, come back,
leave the tab — and run 1's stored instrument has reverted. The store and both
writes were correct all along. What happens is that `_on_target_changed` loads
the target's own settings and then calls `_display_run_chart` ->
`_restore_chart_settings`, which lays the chart sidecar's recipe (instrument,
paper, layout mode, both indicator checkboxes) back over them. The next
write-on-leave then files the CHART's values into the TARGET's store as though
the user had chosen them.

Whether the sidecar may SHOW its own values on a run change is §10's question
and is not settled here. What is settled is §2.1: a write must never record
values their owner never chose.

Driven through the real `_on_target_changed`, with only the chart RENDERING
stood in for — building a real chart needs ArgyllCMS, and the rendering is not
what is under test. The stand-in does exactly what `_restore_chart_settings`
does: it puts the sidecar's value on screen.
"""
import pytest

from core.file_manager import Project


def _accepts_free_text(widget) -> bool:
    """A combo would silently refuse an arbitrary string, proving nothing."""
    try:
        widget.set_value("probe-value")
        return widget.get_raw_value() == "probe-value"
    except Exception:              # noqa: BLE001
        return False


def _tab_on_a_project(tmp_path):
    from core.argyll_runner import ArgyllRunner
    from core.file_manager import FileManager
    from core.settings import AppSettings
    from ui.measurement_target_bar import MeasurementTargetController
    from ui.tabs.tab_chart import TabChart

    settings = AppSettings()
    settings.set("custom_output_path", str(tmp_path / "out"))
    fm = FileManager(settings)
    root = fm.root_dir()
    root.mkdir(parents=True, exist_ok=True)
    proj = Project.create(root / "Demo-Sidecar", "Demo-Sidecar")
    proj.current_run().ensure_dir()
    proj.new_run()                                   # run2
    fm.set_target_name("Demo-Sidecar")

    tab = TabChart(ArgyllRunner(settings), fm, settings)
    ctl = MeasurementTargetController(fm)
    tab.set_target_controller(ctl)
    return tab, ctl, proj


def _a_free_text_row(tab):
    from workflow.per_target_settings import params_for
    for p in params_for(tab):
        if not p.repeats and _accepts_free_text(p.widgets[0]):
            return p
    pytest.skip("no free-text row to carry the value in this build")


def _pretend_a_chart_is_there(tab, monkeypatch, param, chart_value):
    """Make the handler take its chart path, and impose the sidecar's value.

    `_restore_chart_settings` does exactly this and nothing else that matters
    here: it writes the chart's own recipe onto the panel.
    """
    monkeypatch.setattr(tab, "_resolve_target_chart",
                        lambda: (tmpish := None) or ("ti2", [], "ti1"))
    monkeypatch.setattr(tab, "_chart_stamp", lambda _t: None)
    monkeypatch.setattr(
        tab, "_display_run_chart",
        lambda *a, **k: param.widgets[0].set_value(chart_value))


def test_the_stored_value_survives_a_visit(tmp_path, qapp, monkeypatch):
    tab, ctl, proj = _tab_on_a_project(tmp_path)
    ctl.set_profile_run("run1")
    if tab._target_settings_store() is None:
        pytest.skip("the bar could not resolve run1 in this environment")

    param = _a_free_text_row(tab)
    param.widgets[0].set_value("chosen-by-the-user")
    ctl.set_profile_run("run2")                 # W6 files run 1's choice

    stored = proj.run("run1").load_meta().create_chart_settings
    assert stored.get(param.key, {}).get("value") == "chosen-by-the-user", (
        "the value was never filed, so this test cannot say anything")

    # …now come back to run 1, where a chart's sidecar says something else.
    _pretend_a_chart_is_there(tab, monkeypatch, param, "from-the-chart")
    ctl.set_profile_run("run1")
    assert param.widgets[0].get_raw_value() == "from-the-chart", (
        "the stand-in did not impose anything, so nothing is being tested")

    # Leaving the tab writes. It must not write the chart's value.
    tab.save_target_settings()
    kept = proj.run("run1").load_meta().create_chart_settings
    assert kept.get(param.key, {}).get("value") == "chosen-by-the-user", (
        "visiting the run destroyed the setting stored on it: the chart "
        "sidecar's value was filed into the target's own store")


def test_a_value_the_user_changes_afterwards_is_still_theirs(tmp_path, qapp,
                                                             monkeypatch):
    """The shield protects the store, it does not freeze it."""
    tab, ctl, proj = _tab_on_a_project(tmp_path)
    ctl.set_profile_run("run1")
    if tab._target_settings_store() is None:
        pytest.skip("the bar could not resolve run1 in this environment")

    param = _a_free_text_row(tab)
    param.widgets[0].set_value("chosen-by-the-user")
    ctl.set_profile_run("run2")

    _pretend_a_chart_is_there(tab, monkeypatch, param, "from-the-chart")
    ctl.set_profile_run("run1")
    param.widgets[0].set_value("changed-my-mind")     # the user, afterwards
    tab.save_target_settings()

    kept = proj.run("run1").load_meta().create_chart_settings
    assert kept.get(param.key, {}).get("value") == "changed-my-mind", (
        "a value the user set after the chart imposed one was not written")


def test_nothing_is_shielded_when_no_chart_imposed_anything(tmp_path, qapp):
    """A run with no chart writes exactly what is on screen, as before."""
    tab, ctl, proj = _tab_on_a_project(tmp_path)
    ctl.set_profile_run("run1")
    if tab._target_settings_store() is None:
        pytest.skip("the bar could not resolve run1 in this environment")

    param = _a_free_text_row(tab)
    ctl.set_profile_run("run2")
    ctl.set_profile_run("run1")
    assert not getattr(tab, "_chart_imposed", None), (
        "a run with no chart recorded an imposition that never happened")
    param.widgets[0].set_value("plainly-mine")
    tab.save_target_settings()
    kept = proj.run("run1").load_meta().create_chart_settings
    assert kept.get(param.key, {}).get("value") == "plainly-mine"


def test_a_row_that_reports_a_change_is_written_even_if_it_agrees(
        tmp_path, qapp, monkeypatch):
    """A reported change is the user's, whatever the value happens to be.

    The shield needs two conditions, and this is the one the value test alone
    gets wrong: a control that reports a change is no longer the sidecar's,
    even if what it now holds is what the sidecar put there. (Through the UI a
    combo does not re-emit for the same entry, so this drives the signal the
    way the control would.)
    """
    tab, ctl, proj = _tab_on_a_project(tmp_path)
    ctl.set_profile_run("run1")
    if tab._target_settings_store() is None:
        pytest.skip("the bar could not resolve run1 in this environment")

    param = _a_free_text_row(tab)
    param.widgets[0].set_value("chosen-by-the-user")
    ctl.set_profile_run("run2")

    _pretend_a_chart_is_there(tab, monkeypatch, param, "from-the-chart")
    ctl.set_profile_run("run1")
    assert param.key in (tab._chart_imposed or {}).get("params", {}), (
        "the chart's change was not recorded, so nothing is being tested")
    param.widgets[0].value_changed.emit()      # the control reports a change
    assert param.key not in (tab._chart_imposed or {}).get("params", {}), (
        "a row that reported a change is still being treated as the "
        "sidecar's, so the user's own edit can be thrown away")

    tab.save_target_settings()
    kept = proj.run("run1").load_meta().create_chart_settings
    assert kept.get(param.key, {}).get("value") == "from-the-chart"
