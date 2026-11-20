"""Final fix round, the owner (4.3.45): "patch by patch being default is ok but the user should
be able to disable the patch by patch option to try strip reading and if it works save it as
default for the device".

* a table chart starts ticked; a saved table default (Save as Defaults with a table chart
  loaded, the offer, Preferences > Beta) comes back for every later table chart, also in a new
  project;
* the hand instruments' and the CR30's "-p" keep their own values, in both directions;
* a target's own stored value ranks first (per_target_settings.md §1.9);
* the offer after a measurement appears only after a clean strip measurement;
* Beta off: nothing of it."""
from __future__ import annotations

import pytest

from tests.i1io_table.test_window import open_window, settings  # noqa: F401
from tests.i1io_table.test_window_in_the_measure_tab import beta, tab, table_run  # noqa: F401
from tests.i1io_table.window_sim import WindowSim
from workflow import measure_settings as MS

KEY = "i1io_table_patch_by_patch"
STRIP = ["-v", "-c", "1", "-S", "chart"]


def _box(tab):
    return tab._pbp_cb if tab._current_mode() == "guided" else tab._m_pbp_cb


def test_a_table_chart_starts_ticked(tab, beta, tmp_path):
    tab._m_pbp_cb.setChecked(False)
    tab._pbp_cb.setChecked(False)
    run, _ = table_run(tmp_path / "a")
    tab.set_ti1_path(run.artefact(".ti1"))
    assert tab._m_pbp_cb.isChecked() and tab._pbp_cb.isChecked()


def test_a_saved_unticked_table_default_comes_back_for_a_new_chart_and_project(tab, beta,
                                                                              tmp_path):
    hand, _ = table_run(tmp_path / "hand", side=False)
    tab.set_ti1_path(hand.artefact(".ti1"))
    _box(tab).setChecked(True)                       # the person's own value for hand charts
    a, _ = table_run(tmp_path / "a")
    tab.set_ti1_path(a.artefact(".ti1"))
    _box(tab).setChecked(False)                       # tries strips
    tab._on_save_defaults()
    assert tab._settings.get(KEY) is False
    tab.set_ti1_path(hand.artefact(".ti1"))
    assert _box(tab).isChecked() is True              # the hand value is back
    b, _ = table_run(tmp_path / "another-project")
    tab.set_ti1_path(b.artefact(".ti1"))
    assert _box(tab).isChecked() is False             # the table's saved default


def test_save_as_defaults_keeps_the_hand_and_table_values_apart(tab, beta, tmp_path):
    s = tab._settings
    hand, _ = table_run(tmp_path / "hand", side=False)
    tab.set_ti1_path(hand.artefact(".ti1"))
    _box(tab).setChecked(False)                       # hand charts: strips (the person's)
    tab._on_save_defaults()
    hand_keys = (s.get("measure_patch_by_patch"), s.get("manual2_chartread_pbp"))
    assert s.get(KEY, True) is True                   # a hand save never touches the table's
    a, _ = table_run(tmp_path / "a")
    tab.set_ti1_path(a.artefact(".ti1"))
    assert _box(tab).isChecked() is True              # the table starts ticked
    tab._on_save_defaults()                           # saves the TABLE's (ticked)
    assert (s.get("measure_patch_by_patch"), s.get("manual2_chartread_pbp")) == hand_keys
    assert s.get(KEY) is True


@pytest.mark.parametrize("order", ["settings_first", "chart_first"])
def test_the_targets_own_value_ranks_above_the_table_default(tab, beta, tmp_path, monkeypatch,
                                                             order):
    tab._settings.set(KEY, False)                     # the table default: strips
    run, _ = table_run(tmp_path / "a")
    snap = MS.snapshot(tab)
    snap["patch_by_patch"] = dict(snap["patch_by_patch"], value=True)
    snap["patch_by_patch_guided"] = dict(snap["patch_by_patch_guided"], value=True)

    class Meta:
        measure_settings = snap

    class Store:
        dir = tmp_path / "a-store"

        def load_meta(self):
            return Meta()
    monkeypatch.setattr("workflow.per_target_settings.store_for_target", lambda ctl: Store())
    if order == "settings_first":
        assert tab.load_target_settings()
        tab.set_ti1_path(run.artefact(".ti1"))
    else:
        tab.set_ti1_path(run.artefact(".ti1"))
        assert tab.load_target_settings()
    assert _box(tab).isChecked() is True              # the target's own (patch by patch)


def test_a_cr30_chart_keeps_its_lock_and_the_table_default_is_untouched(tab, beta, tmp_path,
                                                                         monkeypatch):
    tab._settings.set(KEY, False)
    state = {"cr30": False}
    monkeypatch.setattr(type(tab), "_chart_is_cr30", lambda self: state["cr30"])
    hand, _ = table_run(tmp_path / "hand", side=False)
    tab.set_ti1_path(hand.artefact(".ti1"))
    _box(tab).setChecked(False)
    state["cr30"] = True
    tab._apply_cr30_pbp_lock()
    assert _box(tab).isChecked() and not _box(tab).isEnabled()
    tab._on_save_defaults()                           # a CR30 save: the table's stays
    assert tab._settings.get(KEY) is False
    state["cr30"] = False
    tab._apply_cr30_pbp_lock()
    assert _box(tab).isChecked() is False and _box(tab).isEnabled()


def test_beta_off_a_table_chart_leaves_pbp_alone(tab, tmp_path):
    # 4.3.53: the Beta OFF said, not assumed: with the running value unset, i1io_enabled()
    # reads the worker's settings file, which another file's test may have left with the Beta
    # on (failed 2 of 4 parallel runs, passed every time alone)
    import workflow.i1io.support as sup
    sup.set_enabled_for_this_process(False)
    try:
        _beta_off_leaves_pbp_alone(tab, tmp_path)
    finally:
        sup.set_enabled_for_this_process(None)


def _beta_off_leaves_pbp_alone(tab, tmp_path):
    tab._settings.set(KEY, False)
    tab._m_pbp_cb.setChecked(True)
    run, _ = table_run(tmp_path / "a")
    tab.set_ti1_path(run.artefact(".ti1"))
    assert tab._m_pbp_cb.isChecked() is True and tab._pbp_lock_snapshot is None


# ---- the offer after a clean strip measurement --------------------------------------------------

def _measure(qtbot, monkeypatch, tmp_path, settings, args, sim=None, script=None):
    win, sim, run, p, saved, finished = open_window(qtbot, monkeypatch, tmp_path, settings,
                                                    asking=False, args=args, sim=sim)
    p.script.update({"end_of_session": "Save and stop", "home_offered": "Leave it there",
                     "row_failed_strip": "Read it again as a strip"})
    p.script.update(script or {})
    p.drive_until("done")
    return win, p


def test_the_offer_after_a_clean_strip_measurement(qtbot, monkeypatch, tmp_path, settings):
    settings.set(KEY, True)
    settings.set("i1io_table_strip_offer_declined", False)
    try:
        win, p = _measure(qtbot, monkeypatch, tmp_path, settings, STRIP)
        assert "Reading rows as strips worked for this chart" in win._text.text()
        assert p.labels() == ["Not now", "Yes, make strips the default"]
        assert not any(b.isDefault() or b.autoDefault() for b in win._buttons)
        p.press("Yes, make strips the default")
        assert settings.get(KEY) is False
    finally:
        settings.set(KEY, True)


def test_not_now_is_remembered(qtbot, monkeypatch, tmp_path, settings):
    settings.set(KEY, True)
    settings.set("i1io_table_strip_offer_declined", False)
    try:
        win, p = _measure(qtbot, monkeypatch, tmp_path, settings, STRIP)
        p.press("Not now")
        assert settings.get(KEY) is True
        assert settings.get("i1io_table_strip_offer_declined") is True
    finally:
        settings.set("i1io_table_strip_offer_declined", False)


@pytest.mark.parametrize("case", ["patch_by_patch", "failed_strip"])
def test_no_offer_unless_every_row_was_a_clean_strip(qtbot, monkeypatch, tmp_path, settings,
                                                     case):
    settings.set(KEY, True)
    settings.set("i1io_table_strip_offer_declined", False)
    if case == "patch_by_patch":
        win, p = _measure(qtbot, monkeypatch, tmp_path, settings,
                          ["-v", "-c", "1", "-S", "-p", "chart"])
    else:
        win, p = _measure(qtbot, monkeypatch, tmp_path, settings, STRIP,
                          sim=WindowSim(faults={"scan": {"not_ready": True}, "scan_at": 2}))
    assert "Reading rows as strips worked" not in win._text.text()
    assert p.labels() == ["Close"]
