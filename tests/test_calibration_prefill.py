"""#137 Table F / D4 / D6 / R2 — the .cal prefill offers, it never chooses.

Two faults lived here. ``ParameterWidget.set_value`` **ticks** the enable box
for a ``file_path`` parameter, so filling ``-K`` then ``-I`` left the mutual
exclusion to decide, and the app arrived silently at "-I on, -K off" (D4). And
it did that even with calibration options switched off, inside a group that
preference hides — so a calibration went into the built chart invisibly (D6).
"""
from __future__ import annotations

import pytest

from core.argyll_runner import ArgyllRunner
from core.file_manager import FileManager
from ui.tabs.tab_chart import TabChart


def _build(settings, *, with_cal: bool):
    fm = FileManager(settings)
    fm.set_target_name("Test-Printer")
    proj = fm.project()
    if with_cal:
        cal = proj.calibration
        cal.ensure_dir()
        cal.cal_path.write_text("a calibration", encoding="utf-8")
    tab = TabChart(ArgyllRunner(settings), fm, settings)
    tab._check_for_cal_file("Test-Printer")
    return tab


def _state(pw):
    box = getattr(pw, "_enable_check", None)
    return str(pw.get_raw_value() or ""), (box.isChecked() if box else None)


# ---- Table F -------------------------------------------------------------
@pytest.mark.parametrize("preference,with_cal,fills", [
    (False, False, False),
    (False, True, False),      # D6 — the whole point
    (True, False, False),
    (True, True, True),
])
def test_the_prefill_matrix(cal_home, preference, with_cal, fills, qapp):
    from tests.conftest_calibration import CalSettings

    tab = _build(CalSettings(cal_home, calibration_mode=preference),
                 with_cal=with_cal)
    for pw in (tab._manual_cal_k_pw, tab._manual_cal_i_pw):
        value, enabled = _state(pw)
        assert bool(value) is fills, f"value={value!r} expected fill={fills}"
        assert enabled is False, "ChromIQ switched an option on for the user"


def test_the_preference_off_changes_nothing_at_all(cal_home, qapp):
    """The rule that outranks the feature."""
    from tests.conftest_calibration import CalSettings

    tab = _build(CalSettings(cal_home, calibration_mode=False), with_cal=True)
    for pw in (tab._manual_cal_k_pw, tab._manual_cal_i_pw):
        value, enabled = _state(pw)
        assert value == "" and enabled is False
    assert tab._cal_status_lbl.text() == ""


# ---- D4 / R2 -------------------------------------------------------------
def test_both_fields_are_filled_and_neither_is_switched_on(cal_home, qapp):
    from tests.conftest_calibration import CalSettings

    tab = _build(CalSettings(cal_home, calibration_mode=True), with_cal=True)
    k_value, k_on = _state(tab._manual_cal_k_pw)
    i_value, i_on = _state(tab._manual_cal_i_pw)
    assert k_value.endswith("-cal.cal") and i_value.endswith("-cal.cal")
    assert k_on is False and i_on is False, (
        "the prefill chose for the user — that is D4")


def test_the_status_line_says_neither_is_on(cal_home, qapp):
    """With printtarg laying the chart out, the -K / -I fields are what the
    build reads, so the line names them (decision 7)."""
    from tests.conftest_calibration import CalSettings

    tab = _build(CalSettings(cal_home, calibration_mode=True,
                             use_chromiq_layout_engine=False), with_cal=True)
    text = tab._cal_status_lbl.text()
    assert "Neither is switched on yet" in text
    assert "cannot both be used at once" in text
    # It names what each one actually does, so the choice can be made.
    assert "reprints every patch" in text and "only records it" in text


def test_a_users_own_setting_is_not_switched_off(cal_home, qapp):
    """The helper holds the enable box still — it must restore what was there,
    not force it off. Someone who deliberately switched -K on keeps it."""
    from tests.conftest_calibration import CalSettings

    settings = CalSettings(cal_home, calibration_mode=True)
    fm = FileManager(settings)
    fm.set_target_name("Test-Printer")
    proj = fm.project()
    cal = proj.calibration
    cal.ensure_dir()
    cal.cal_path.write_text("a calibration", encoding="utf-8")
    tab = TabChart(ArgyllRunner(settings), fm, settings)

    tab._manual_cal_k_pw._enable_check.setChecked(True)
    tab._check_for_cal_file("Test-Printer")
    assert tab._manual_cal_k_pw._enable_check.isChecked() is True


# ---- B8-1655: the engine reads its own calibration group -----------------
def test_with_the_engine_the_offer_goes_to_the_engine_panel(cal_home, qapp):
    """An engine build takes its calibration from the engine panel's
    "Printer calibration" group, never from -K / -I, so the offer goes there
    too: the path filled, the Mode left on "None", and the line says where."""
    from tests.conftest_calibration import CalSettings
    from workflow.measurement_messages import M_CAL_FOUND_ENGINE

    tab = _build(CalSettings(cal_home, calibration_mode=True,
                             use_chromiq_layout_engine=True), with_cal=True)
    assert tab._manual_panel_lays_out()
    panel = tab._manual_layout_panel
    assert panel.cal_path_edit.text().endswith("-cal.cal")
    assert panel.cal_mode.currentData() == "off", (
        "the prefill chose a mode for the user")
    path, apply_cal = panel.cal_settings()
    assert path is None or not apply_cal, (
        "with Mode on None the build must not apply the calibration")
    assert tab._cal_status_lbl.text() == M_CAL_FOUND_ENGINE.render(
        name=tab._manual_layout_panel.cal_path_edit.text().rsplit("/", 1)[-1])[1]


def test_with_the_engine_a_path_already_there_is_kept(cal_home, qapp):
    from tests.conftest_calibration import CalSettings

    settings = CalSettings(cal_home, calibration_mode=True,
                           use_chromiq_layout_engine=True)
    fm = FileManager(settings)
    fm.set_target_name("Test-Printer")
    cal = fm.project().calibration
    cal.ensure_dir()
    cal.cal_path.write_text("a calibration", encoding="utf-8")
    tab = TabChart(ArgyllRunner(settings), fm, settings)
    tab._manual_layout_panel.cal_path_edit.setText("/somewhere/else.cal")
    tab._check_for_cal_file("Test-Printer")
    assert tab._manual_layout_panel.cal_path_edit.text() == "/somewhere/else.cal"
