"""X-Rite i1Pro 3: keep M0, M1 and M2 from every scan (Preferences > Beta):
the owner's four rulings of 2026-11-15 (Basti).

1. A profile built from the M1 or M2 readings says so in its default
   Profile Description ("-M1", "-M2"); the user's own text is untouched.
2. (verification, see test_i1pro3_conditions_verification.py)
3. (averaging, see test_i1pro3_conditions_averaging.py)
4. "Build from" is part of a Manual preset and of Save as Defaults, and is
   IGNORED while the Beta is off: off is exactly today's behaviour, also
   when a preset or a saved default carries a value.
"""
from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("PyQt6")

from workflow import i1pro3_conditions as C  # noqa: E402

from tests.test_i1pro3_conditions_files import _sibling, _write  # noqa: E402
from tests.test_engine_v2_options import _tab  # noqa: E402


def _loose(tmp_path, *conds) -> Path:
    main = _write(tmp_path / "loose" / "chart.ti3")
    for c in conds:
        _sibling(main, c)
    return main


def _pick(tab, cond):
    combo = tab._cond_combo
    tab._on_build_from_chosen(combo.findData(cond))


# ---------------------------------------------------------------------------
# 1. the description names the condition
# ---------------------------------------------------------------------------

def test_a_profile_built_from_m1_or_m2_says_so(tmp_path, qtbot):
    tab = _tab(tmp_path, **{C.SETTING: True})
    qtbot.addWidget(tab)
    main = _loose(tmp_path, "M1", "M2")
    tab.set_ti3_path(main, propagate=False)
    assert tab._desc_edit.text() == "chart"
    _pick(tab, "M1")
    assert tab._desc_edit.text() == "chart-M1"
    assert tab._m_desc_edit.text() == "chart-M1"
    _pick(tab, "M2")
    assert tab._desc_edit.text() == "chart-M2"
    _pick(tab, "M0")
    assert tab._desc_edit.text() == "chart"


def test_the_users_own_description_is_untouched(tmp_path, qtbot):
    tab = _tab(tmp_path, **{C.SETTING: True})
    qtbot.addWidget(tab)
    main = _loose(tmp_path, "M1", "M2")
    tab.set_ti3_path(main, propagate=False)
    tab._desc_edit.setText("My own name")
    tab._m_desc_edit.setText("My own name")
    _pick(tab, "M1")
    assert tab._desc_edit.text() == "My own name"


def test_the_composed_default_ends_with_the_condition(tmp_path, qtbot,
                                                      monkeypatch):
    """<project>-<run description>-M1: the condition is the last part, and
    an empty part still drops out with its hyphen (T6.17)."""
    tab = _tab(tmp_path, **{C.SETTING: True})
    qtbot.addWidget(tab)
    from core.file_manager import Project
    proj = Project.create(tmp_path / "out" / "Paper", "Paper")
    run = proj.current_run()
    meta = run.load_meta()
    meta.description = "Glossy"
    run.save_meta(meta)

    class _Target:
        def is_calibration(self):
            return False

    class _Ctl:
        target = _Target()

        def project_or_none(self):
            return proj

    import core.measurement_target as mt
    monkeypatch.setattr(mt, "resolve_run", lambda _p, _t: run)
    tab._target_ctl = _Ctl()
    monkeypatch.setattr(tab, "_build_from_suffix", lambda: "M1")
    assert tab._compose_profile_description() == "Paper-Glossy-M1"
    monkeypatch.setattr(tab, "_build_from_suffix", lambda: "")
    assert tab._compose_profile_description() == "Paper-Glossy"


def test_off_the_description_is_todays(tmp_path, qtbot):
    tab = _tab(tmp_path)
    qtbot.addWidget(tab)
    main = _loose(tmp_path, "M1", "M2")
    tab._build_from = "M1"            # a value left by a preset or a target
    tab.set_ti3_path(main, propagate=False)
    assert tab._build_from_suffix() == ""
    assert tab._desc_edit.text() == "chart"
    assert not tab._cond_combo.isVisible()


# ---------------------------------------------------------------------------
# 4. presets and Save as Defaults
# ---------------------------------------------------------------------------

def test_a_preset_carries_build_from_with_the_beta_on(tmp_path, qtbot):
    tab = _tab(tmp_path, **{C.SETTING: True})
    qtbot.addWidget(tab)
    main = _loose(tmp_path, "M1", "M2")
    tab.set_ti3_path(main, propagate=False)
    _pick(tab, "M2")
    data = tab._m_collect_preset_data()
    assert data[C.BUILD_FROM_KEY] == "M2"
    data[C.BUILD_FROM_KEY] = "M1"
    tab._m_apply_preset_data(data)
    assert tab._build_from == "M1"
    assert tab._cond_combo.currentData() == "M1"
    assert tab._desc_edit.text() == "chart-M1"
    # a preset saved before (or with the Beta off) leaves the choice alone
    data.pop(C.BUILD_FROM_KEY)
    tab._m_apply_preset_data(data)
    assert tab._build_from == "M1"


def test_off_a_preset_neither_saves_nor_applies_it(tmp_path, qtbot):
    tab = _tab(tmp_path)
    qtbot.addWidget(tab)
    main = _loose(tmp_path, "M1", "M2")
    tab.set_ti3_path(main, propagate=False)
    data = tab._m_collect_preset_data()
    assert C.BUILD_FROM_KEY not in data
    data[C.BUILD_FROM_KEY] = "M1"
    tab._m_apply_preset_data(data)
    assert tab._build_from == ""
    assert tab._build_from_file() is None


def test_save_as_defaults_and_their_use_with_the_beta_on(tmp_path, qtbot):
    from ui.tabs.tab_profile import BUILD_FROM_DEFAULT_KEY
    tab = _tab(tmp_path, **{C.SETTING: True})
    qtbot.addWidget(tab)
    main = _loose(tmp_path, "M1", "M2")
    tab.set_ti3_path(main, propagate=False)
    _pick(tab, "M1")
    tab._on_save_defaults()
    assert tab._settings.get(BUILD_FROM_DEFAULT_KEY) == "M1"
    # a target with nothing stored takes the saved default
    tab._build_from = ""
    tab._load_build_from(None)
    assert tab._build_from == "M1"
    # ...and so does "none" in the preset list
    tab._build_from = ""
    tab._on_m_preset_selected(0)
    assert tab._build_from == "M1"
    # a target that stored its own choice keeps it
    tab._load_build_from({C.BUILD_FROM_KEY: "M2"})
    assert tab._build_from == "M2"


def test_off_save_as_defaults_writes_nothing_and_a_default_is_ignored(
        tmp_path, qtbot):
    from ui.tabs.tab_profile import BUILD_FROM_DEFAULT_KEY
    tab = _tab(tmp_path)
    qtbot.addWidget(tab)
    tab._on_save_defaults()
    assert tab._settings.get(BUILD_FROM_DEFAULT_KEY) is None
    tab._settings.set(BUILD_FROM_DEFAULT_KEY, "M1")   # left from a Beta-on day
    tab._load_build_from(None)
    assert tab._build_from == ""
    tab._on_m_preset_selected(0)
    assert tab._build_from == ""
    tab._on_save_defaults()
    assert tab._settings.get(BUILD_FROM_DEFAULT_KEY) == "M1"   # untouched


def test_a_default_with_no_file_for_this_run_refuses_the_build_and_says_why(
        tmp_path, qtbot):
    """No silent fallback: a saved default of M1 on a measurement with no M1
    readings is shown greyed with its reason, and Build waits for a choice."""
    from ui.tabs.tab_profile import BUILD_FROM_DEFAULT_KEY
    tab = _tab(tmp_path, **{C.SETTING: True, BUILD_FROM_DEFAULT_KEY: "M1"})
    qtbot.addWidget(tab)
    main = _loose(tmp_path)                  # no condition files at all
    tab.set_ti3_path(main, propagate=False)
    tab._load_build_from(None)
    assert tab._build_from == "M1"
    assert tab._cond_combo.currentData() == "M1"
    assert not tab._build_btn.isEnabled()
    assert "M1" in tab._build_btn.toolTip()
    assert tab._build_from_file() is None
    assert tab._desc_edit.text() == "chart"     # not built from M1: not said


# ---------------------------------------------------------------------------
# the (i) of "Build from" (Basti, 2026-11-15: "friendly extensive easy to
# understand and correct")
# ---------------------------------------------------------------------------

def test_build_from_has_its_info_button_in_both_modes(tmp_path, qtbot):
    from ui.tabs.tab_profile import build_from_help
    from ui.tooltip_button import TooltipButton
    tab = _tab(tmp_path, **{C.SETTING: True})
    qtbot.addWidget(tab)
    tab.show()
    main = _loose(tmp_path, "M1", "M2")
    tab.set_ti3_path(main, propagate=False)
    assert isinstance(tab._cond_tip, TooltipButton)
    for mode in ("guided", "manual"):
        tab._switch_mode(mode)
        assert tab._cond_combo.isVisible() and tab._cond_tip.isVisible(), mode
    text = build_from_help()
    for word in ("**M0**", "**M1**", "**M2**", "FWA", "-M1",
                 "M0 and M2 values have not been compared", "greyed"):
        assert word in text, word
    assert "—" not in text


def test_off_the_info_button_is_hidden_with_the_row(tmp_path, qtbot):
    tab = _tab(tmp_path)
    qtbot.addWidget(tab)
    tab.show()
    tab.set_ti3_path(_loose(tmp_path, "M1"), propagate=False)
    assert not tab._cond_tip.isVisible() and not tab._cond_combo.isVisible()


def test_the_info_button_is_made_like_its_neighbours(tmp_path, qtbot):
    """The same class, made the same way, as the other (i) of the tab, with
    the object name the style sheet's flat, borderless rule is keyed on
    (``QToolButton#tooltip_btn``). An own object name once dropped that rule
    and drew the button in a box (Basti, 2026-11-15)."""
    from ui.tooltip_button import TooltipButton
    tab = _tab(tmp_path, **{C.SETTING: True})
    qtbot.addWidget(tab)
    tab.show()
    tab.set_ti3_path(_loose(tmp_path, "M1"), propagate=False)
    me = tab._cond_tip
    others = [w for w in tab.findChildren(TooltipButton)
              if w is not me and w.isVisible()]
    assert len(others) >= 2
    ref = others[0]
    assert type(me) is type(ref) is TooltipButton
    assert me.objectName() == ref.objectName() == "tooltip_btn"
    assert me.size() == ref.size()
    assert me.focusPolicy() == ref.focusPolicy()
    assert me.styleSheet() == ref.styleSheet() == ""
    assert getattr(me, "_color_override", None) is None   # the tab's accent
    from ui.widgets import NoScrollComboBox
    assert isinstance(tab._cond_combo, NoScrollComboBox)


def test_the_preferences_row_info_button_is_made_like_its_neighbours(qapp):
    from tests.test_the_new_profile_engine_is_one_switch import _Fake
    from core.settings import DEFAULTS
    from ui.dialogs.settings_dialog import SettingsDialog
    dlg = SettingsDialog(_Fake(DEFAULTS))
    try:
        me = dlg._i1pro3_conditions_tip
        from ui.tooltip_button import TooltipButton
        assert type(me) is TooltipButton
        assert me.objectName() == "tooltip_btn"
    finally:
        dlg.deleteLater()
