"""K36, Knut #182 5820871320 (beta 42): an ISO report type and its limit
sets, no ISO type for a calibration run, the three terms of a report's
scope, and the paper-patch note that names the sheet.

Each test names the mutation that turns it red; every one was run.

K36-1 *"I think (a), but a user should only be allowed to select between the
4 ISO options in judged against, and the other options are greyed while
having selected Validation print check or Contract proof check."*

K36-2 *"[Should a Calibration run offer the two ISO types at all?] No, but
the limit sets can still be chosen"*.

K36-3 *"the terms to differentiate between the different reports' scope
could be ... "profile run", "verification run" and "calibration run"? ...
recorded in the help card Dictionary"*; *"Given the above, the message is
accepted."*

K36-4 *"do you mean the "chart sheet" or do you mean "nothing in this
report"? Make sure the text cannot be misunderstood. Then this message is
accepted."*
"""
from __future__ import annotations

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication

from core.i18n import tr
from workflow import compliance_sets as cs
from workflow import measurement_report as mr

ISO4 = {"iso_12647_7", "iso_12647_8", "custom_iso_12647_7",
        "custom_iso_12647_8"}


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def repo_values(monkeypatch):
    from tests.helpers.iso_files import use_repo_iso
    use_repo_iso(monkeypatch)
    yield
    cs.reset_iso_cache()


def _close(dlg):
    dlg.close()
    dlg.deleteLater()
    QApplication.processEvents()


def _dialog(tmp_path, qapp):
    from tests.test_the_report_type_pulldown_stores_on_the_run import _dialog
    return _dialog(tmp_path, qapp)


def _pick(combo, data, qapp):
    i = combo.findData(data)
    assert i >= 0, data
    combo.setCurrentIndex(i)
    qapp.processEvents()


def _set_item(dlg, sid):
    c = dlg._set_combo
    i = c.findData(sid)
    return (c.model().item(i).isEnabled(),
            c.itemData(i, Qt.ItemDataRole.ToolTipRole) or "")


# --------------------------------------------------------------------- K36-1
def test_the_rule_itself():
    """MUTATION: `set_allowed_for_type` returning True -> red."""
    for tid in (mr.REPORT_TYPE_ISO_7, mr.REPORT_TYPE_ISO_8):
        for sid in ISO4:
            assert mr.set_allowed_for_type(tid, sid)
        for sid in ("chromiq_default", "chromiq_tight", "chromiq_quick"):
            assert not mr.set_allowed_for_type(tid, sid)
            assert mr.set_held_to_type(tid, sid) == mr.REPORT_TYPE_ISO_SET[tid]
        assert mr.set_held_to_type(tid, "custom_iso_12647_8") \
            == "custom_iso_12647_8"
    for tid in (mr.REPORT_TYPE_FULL, mr.REPORT_TYPE_GREY,
                mr.REPORT_TYPE_SUMMARY, mr.REPORT_TYPE_RECORD):
        assert mr.set_allowed_for_type(tid, "chromiq_default")
    assert set(mr.ISO_JUDGED_AGAINST) == ISO4


@pytest.mark.parametrize("tid", [mr.REPORT_TYPE_ISO_8, mr.REPORT_TYPE_ISO_7])
def test_choosing_an_iso_type_sets_its_standards_set_and_greys_the_rest(
        tid, tmp_path, qapp, repo_values):
    """MUTATION: drop the set_id from `_on_type_chosen` -> the set stays
    ChromIQ default (red); drop `_grey_the_sets_the_type_refuses` from
    `_sync_limit_controls` -> ChromIQ's sets stay enabled (red)."""
    dlg, _run = _dialog(tmp_path, qapp)
    try:
        assert dlg._set_combo.currentData() == "chromiq_default"
        _pick(dlg._type_combo, tid, qapp)
        assert dlg._report_type_now() == tid
        assert dlg._set_combo.currentData() == mr.REPORT_TYPE_ISO_SET[tid]
        assert dlg._report_limits().set_id == mr.REPORT_TYPE_ISO_SET[tid]
        for sid in ISO4:
            assert _set_item(dlg, sid)[0], f"{sid} greyed under {tid}"
        for sid in ("chromiq_default", "chromiq_tight", "chromiq_quick"):
            on, tip = _set_item(dlg, sid)
            assert not on, f"{sid} still choosable under {tid}"
            assert tr(mr.report_type_name(tid)) in tip and "ISO" in tip, tip
        # the user may still move among the four
        _pick(dlg._set_combo, "custom_iso_12647_7", qapp)
        assert dlg._report_limits().set_id == "custom_iso_12647_7"
        # and a greyed entry chosen by a keyboard is put back
        dlg._on_set_chosen(dlg._set_combo.findData("chromiq_tight"))
        assert dlg._report_limits().set_id == "custom_iso_12647_7"
        # back to a non-ISO type: every set again, and the set the ISO type
        # replaced is put back (challenge 4 of beta 42, B8-1074)
        _pick(dlg._type_combo, mr.REPORT_TYPE_FULL, qapp)
        assert dlg._report_limits().set_id == "chromiq_default"
        assert _set_item(dlg, "chromiq_tight")[0]
    finally:
        _close(dlg)


def test_a_saved_report_with_the_old_pair_opens_as_saved_and_is_not_generated_again(
        tmp_path, qapp, repo_values):
    """A report written before the rule, Contract proof check judged against
    ChromIQ default: shown as saved; Generate is greyed with the reason and
    the two pulldowns stay live; an ISO set then brings Generate back, and the
    press asks Update / Create New because a setting moved.

    MUTATION: drop the `_type_refuses_the_set` branch from the Generate
    state -> Generate stays enabled (red)."""
    dlg, _run = _dialog(tmp_path, qapp)
    try:
        lim = cs.effective_limits("chromiq_default", {})
        dlg._loaded_doc_id = "doc-old"
        dlg._loaded_doc = {
            "id": "doc-old", "created": "2026-09-01T10:00:00",
            "type": mr.REPORT_TYPE_ISO_7, "detail": False,
            "compliance": {"set_id": "chromiq_default",
                           "set_label": "ChromIQ default (recommended)",
                           "thresholds": cs.limits_to_json(lim)}}
        dlg._doc_settings_moved = False
        dlg._forget_sticky_settings()
        dlg._sync_limit_controls()
        qapp.processEvents()
        # opens as saved
        assert dlg._type_combo.currentData() == mr.REPORT_TYPE_ISO_7
        assert dlg._set_combo.currentData() == "chromiq_default"
        # a new Generate of that pair is refused, with its way out
        assert not dlg._generate_btn.isEnabled()
        assert dlg._generate_btn.toolTip() == dlg._type_refuses_the_set_line()
        assert dlg._type_combo.isEnabled() and dlg._set_combo.isEnabled()
        # an ISO set: Generate is back, and it asks (a setting moved)
        dlg._doc_built_with = dlg._doc_settings()
        _pick(dlg._set_combo, "iso_12647_7", qapp)
        assert dlg._generate_btn.isEnabled(), dlg._generate_btn.toolTip()
        assert dlg._settings_were_modified()
    finally:
        _close(dlg)


def test_a_new_report_starts_on_an_iso_set_when_the_default_type_is_iso(
        tmp_path, qapp, repo_values):
    """Preferences: Contract proof check, and ChromIQ default as the set.
    A new report starts on ISO 12647-7. MUTATION: drop
    `_hold_the_set_to_the_type` from `_load_the_defaults` -> red."""
    dlg, _run = _dialog(tmp_path, qapp)
    s = dlg._settings
    s.set("report_default_type", mr.REPORT_TYPE_ISO_7)
    s.set("compliance_default_set", "chromiq_default")
    try:
        dlg._forget_limits()
        dlg._load_the_defaults()
        dlg._sync_limit_controls()
        qapp.processEvents()
        assert dlg._report_type_now() == mr.REPORT_TYPE_ISO_7
        assert dlg._report_limits().set_id == "iso_12647_7"
        assert dlg._set_combo.currentData() == "iso_12647_7"
    finally:
        s.set("report_default_type", mr.REPORT_TYPE_FULL)
        _close(dlg)


def test_the_automatic_report_holds_the_set_to_the_type(repo_values):
    """The report written after a measurement, and the verification
    pre-flight, use the same starting pair. MUTATION: `limits_held_to_type`
    returning *lim* -> red."""
    from workflow.run_compliance import limits_held_to_type, run_limits
    lim = run_limits(None, {}, "chromiq_tight")
    held = limits_held_to_type(lim, mr.REPORT_TYPE_ISO_8, {})
    assert held.set_id == "iso_12647_8"
    assert limits_held_to_type(lim, mr.REPORT_TYPE_FULL, {}) is lim
    import inspect
    from ui.tabs.tab_measure import TabMeasure
    assert "limits_held_to_type" in inspect.getsource(
        TabMeasure._report_limits_for)
    assert "set_held_to_type" in inspect.getsource(
        TabMeasure._preflight_selection)


def test_the_limits_window_greys_the_radios_the_type_refuses(qapp, repo_values):
    """"Used for this report" pairs with the report's type; "Default for new
    reports" with the Preferences type. MUTATION: `_hold_radio_to_type`
    returning at once -> red."""
    from core.settings import AppSettings
    from ui.dialogs.thresholds_dialog import (ReportLimitsColumn,
                                              ThresholdsDialog)
    from workflow.run_compliance import run_limits
    s = AppSettings()
    col = ReportLimitsColumn(run_limits(None, {}, "iso_12647_7"))
    dlg = ThresholdsDialog(s, None, run=col, run_editable=True,
                           report_type=mr.REPORT_TYPE_ISO_7,
                           default_type=mr.REPORT_TYPE_ISO_8)
    try:
        for radios in (dlg._run_set_radios, dlg._default_radios):
            assert radios, "no radios to check"
            for sid, rb in radios.items():
                assert rb.isEnabled() == (sid in ISO4), sid
                if sid not in ISO4:
                    assert "ISO" in rb.toolTip()
    finally:
        dlg.deleteLater()
    plain = ThresholdsDialog(s, None, run=col, run_editable=True,
                             report_type=mr.REPORT_TYPE_FULL,
                             default_type=mr.REPORT_TYPE_FULL)
    try:
        assert all(rb.isEnabled() for rb in plain._run_set_radios.values())
        assert all(rb.isEnabled() for rb in plain._default_radios.values())
    finally:
        plain.deleteLater()


def test_preferences_move_the_default_set_with_an_iso_default_type(
        qapp, repo_values):
    """MUTATION: disconnect `_on_default_type_chosen` -> the buffered
    default set stays ChromIQ default (red)."""
    from core.settings import AppSettings
    from ui.dialogs.settings_dialog import SettingsDialog
    s = AppSettings()
    s.set("compliance_default_set", "chromiq_default")
    dlg = SettingsDialog(s, None)
    try:
        c = dlg._report_type_default_combo
        i = c.findData(mr.REPORT_TYPE_ISO_8)
        c.setCurrentIndex(i)
        c.activated.emit(i)
        assert dlg._compliance_buffer["default_set"] == "iso_12647_8"
    finally:
        dlg.deleteLater()


def test_the_presets_window_follows_the_same_rule(qapp, repo_values):
    """MUTATION: connect the type pulldown to `_on_choice_changed` again ->
    the set stays on All metrics and ChromIQ's sets stay enabled (red)."""
    from ui.dialogs.preset_verification_dialog import PresetVerificationDialog
    from workflow import preset_eligibility as PE
    dlg = PresetVerificationDialog([])
    try:
        assert dlg.current_set() == PE.ALL_METRICS
        _pick(dlg._type_combo, mr.REPORT_TYPE_ISO_7, qapp)
        assert dlg.current_set() == "iso_12647_7"
        m = dlg._set_combo.model()
        for i in range(dlg._set_combo.count()):
            sid = dlg._set_combo.itemData(i)
            if sid in cs.SET_BY_ID:
                assert m.item(i).isEnabled() == (sid in ISO4), sid
        # All metrics stays choosable
        assert m.item(dlg._set_combo.findData(PE.ALL_METRICS)).isEnabled()
    finally:
        dlg.deleteLater()


# --------------------------------------------------------------------- K36-2
def test_a_calibration_run_offers_no_iso_type_but_every_set(
        tmp_path, qapp, repo_values):
    """MUTATION: put the ISO types back into `report_types_for_kind` for a
    calibration -> red."""
    assert mr.REPORT_TYPE_ISO_7 not in mr.report_types_for_kind(
        mr.KIND_CALIBRATION)
    assert mr.REPORT_TYPE_ISO_8 not in mr.report_types_for_kind(
        mr.KIND_CALIBRATION)
    assert mr.REPORT_TYPE_ISO_7 in mr.report_types_for_kind(
        mr.KIND_VERIFICATION)
    from tests.test_calibration_reports import (_project_with_cal, _settings,
                                                _window)
    _p, ti3 = _project_with_cal(tmp_path, "P")
    dlg = _window(_settings(), ti3, qapp, "calibration")
    try:
        m = dlg._type_combo.model()
        for tid in (mr.REPORT_TYPE_ISO_7, mr.REPORT_TYPE_ISO_8):
            assert not m.item(dlg._type_combo.findData(tid)).isEnabled()
        for sid in ISO4 | {"chromiq_default", "chromiq_tight"}:
            assert _set_item(dlg, sid)[0], f"{sid} greyed for a calibration"
    finally:
        _close(dlg)


# --------------------------------------------------------------------- K36-3
def test_the_dictionary_defines_the_three_terms():
    """MUTATION: remove the "Verification run" entry -> red."""
    from ui.dialogs.welcome_dialog import GLOSSARY
    terms = dict(GLOSSARY)
    for t in ("Profile run", "Verification run", "Calibration run"):
        assert tr(t) in terms, t
    assert "run 1, run 2" in terms[tr("Profile run")]
    assert "verification run" in terms[tr("Profile run")]
    assert "“verifications” folder" in terms[tr("Verification run")]
    assert "calibration run" in terms[tr("Calibration run")]
    for t in ("Profile run", "Verification run", "Calibration run"):
        assert "—" not in terms[tr(t)]


def test_the_report_scope_uses_the_terms(tmp_path, qapp, repo_values):
    """MUTATION: the old "profile verification run" heading -> red."""
    import re
    dlg, _run = _dialog(tmp_path, qapp)
    try:
        runs = dlg._runs_for_report()[:1]
        txt = " ".join(re.sub("<[^>]+>", " ", dlg._scope_html(runs)).split())
        assert "The following verification run is included:" in txt, txt
        assert "profile verification" not in txt
    finally:
        _close(dlg)


def test_the_scope_run_deleted_message_is_approved():
    from workflow import measurement_messages as M
    assert M.M_REPORT_SCOPE_RUN_DELETED.approved
    assert "profile run" in M.M_REPORT_SCOPE_RUN_DELETED.render(
        count=1, runs="run 2")[1]


# --------------------------------------------------------------------- K36-4
def test_the_no_paper_patch_note_names_the_sheet_not_the_report():
    """MUTATION: the old body ("nothing on this sheet") -> red.

    Reworded again for Knut, #182 5824834975 (B8-1096): "sheet" was still
    unclear, so the note names the MEASUREMENT, as the report does, and says
    the report's other measurements are judged as usual. Approval kept."""
    from workflow import measurement_messages as M
    msg = M.M_REPORT_NO_PAPER_PATCH
    assert msg.approved
    body = msg.render()[1]
    assert "The chart of this measurement" in body
    assert "the report's other measurements are judged as usual" in body
    assert "sheet" not in body
    assert "absolute Lab" in body
