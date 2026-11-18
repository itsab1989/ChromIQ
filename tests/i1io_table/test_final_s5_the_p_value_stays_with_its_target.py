"""Final fix round, S-5 (review 13, Part B's probe): a table chart's (or a CR30 chart's) held
"Patch-by-patch mode (-p)" value never overwrites the next target's stored value, whichever
arrives first when the target changes: its stored settings or its chart.

Two targets: A (a table chart, Beta on) and B (another chart, its own -p stored). The main
window loads the visible tab's settings BEFORE the tabs hand over the new chart
(main_window.py), so "settings first, then chart" is what the app does."""
from __future__ import annotations

import pytest

from tests.i1io_table.test_window_in_the_measure_tab import beta, tab, table_run  # noqa: F401
from workflow import measure_settings as MS


def _stored_with_pbp(tab, value):
    snap = MS.snapshot(tab)
    snap["patch_by_patch"] = dict(snap["patch_by_patch"], value=value)
    snap["patch_by_patch_guided"] = dict(snap["patch_by_patch_guided"], value=value)
    return snap


def _load_target_settings(tab, stored, monkeypatch):
    """What load_target_settings does for a target that stores *stored*."""
    class Meta:
        measure_settings = stored

    class Store:
        def load_meta(self):
            return Meta()
    monkeypatch.setattr("workflow.per_target_settings.store_for_target", lambda ctl: Store())
    assert tab.load_target_settings() is True


def _two_targets(tab, tmp_path, own_before):
    tab._m_pbp_cb.setChecked(own_before)
    tab._pbp_cb.setChecked(own_before)
    a, _ = table_run(tmp_path / "a")
    tab.set_ti1_path(a.artefact(".ti1"))
    assert tab._m_pbp_cb.isChecked() and tab._pbp_lock_snapshot is not None
    b, _ = table_run(tmp_path / "b", side=False)
    return a, b


@pytest.mark.parametrize("own_before,stored", [(False, True), (True, False), (False, False)])
def test_table_settings_first_then_the_chart(tab, beta, tmp_path, monkeypatch, own_before,
                                             stored):
    """Failed before this round for (False, True): B showed (and then saved) False."""
    a, b = _two_targets(tab, tmp_path, own_before)
    _load_target_settings(tab, _stored_with_pbp(tab, stored), monkeypatch)
    tab.set_ti1_path(b.artefact(".ti1"))
    assert tab._m_pbp_cb.isChecked() is stored and tab._pbp_cb.isChecked() is stored
    assert MS.snapshot(tab)["patch_by_patch"]["value"] is stored
    assert tab._pbp_lock_snapshot is None


@pytest.mark.parametrize("stored", [True, False])
def test_table_chart_first_then_the_settings(tab, beta, tmp_path, monkeypatch, stored):
    a, b = _two_targets(tab, tmp_path, not stored)
    tab.set_ti1_path(b.artefact(".ti1"))
    _load_target_settings(tab, _stored_with_pbp(tab, stored), monkeypatch)
    assert tab._m_pbp_cb.isChecked() is stored
    assert MS.snapshot(tab)["patch_by_patch"]["value"] is stored


def test_table_to_table_keeps_the_new_targets_own_choice(tab, beta, tmp_path, monkeypatch):
    """B is a table chart too, read as strips (-p unticked, stored)."""
    tab._m_pbp_cb.setChecked(False)
    a, _ = table_run(tmp_path / "a")
    tab.set_ti1_path(a.artefact(".ti1"))
    b, _ = table_run(tmp_path / "b")
    _load_target_settings(tab, _stored_with_pbp(tab, False), monkeypatch)
    tab.set_ti1_path(b.artefact(".ti1"))
    assert tab._m_pbp_cb.isChecked() is False


def test_a_target_without_a_stored_value_keeps_the_persons_own(tab, beta, tmp_path,
                                                               monkeypatch):
    a, b = _two_targets(tab, tmp_path, False)
    stored = _stored_with_pbp(tab, True)
    stored.pop("patch_by_patch")
    stored.pop("patch_by_patch_guided")
    _load_target_settings(tab, stored, monkeypatch)
    tab.set_ti1_path(b.artefact(".ti1"))
    assert tab._m_pbp_cb.isChecked() is False          # the person's own, from before A


@pytest.mark.parametrize("order", ["settings_first", "chart_first"])
def test_cr30_lock_both_orders(tab, tmp_path, monkeypatch, order):
    """The CR30 lock (4.3.44's mechanism) the same way: B's stored False survives."""
    state = {"cr30": True}
    monkeypatch.setattr(type(tab), "_chart_is_cr30", lambda self: state["cr30"])
    tab._m_pbp_cb.setChecked(True)
    tab._pbp_cb.setChecked(True)
    tab._apply_cr30_pbp_lock()                     # a CR30 chart is loaded
    assert tab._pbp_lock_snapshot is not None and not tab._m_pbp_cb.isEnabled()

    def chart_b():
        state["cr30"] = False
        tab._apply_cr30_pbp_lock()                 # what set_ti1_path does for B's chart
    if order == "settings_first":
        _load_target_settings(tab, _stored_with_pbp(tab, False), monkeypatch)
        chart_b()
    else:
        chart_b()
        _load_target_settings(tab, _stored_with_pbp(tab, False), monkeypatch)
    assert tab._m_pbp_cb.isChecked() is False and tab._m_pbp_cb.isEnabled()
    assert tab._pbp_lock_snapshot is None
