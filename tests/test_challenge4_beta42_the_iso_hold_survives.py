"""Challenge 4 of beta 42 (B8-1071 to B8-1076), and Knut's refinement of
K36-1 (#182 5822758830, answer 4).

* B8-1071: editing any number in Report limits / Edit limits re-enabled the
  "Default for new reports" radios an ISO default type had greyed.
* B8-1072: nothing may WRITE an ISO default type beside a non-ISO default
  set, and a pair already on disk is repaired when read.
* B8-1073 / B8-1074: walking a Report type pulldown past an ISO type (wheel
  or arrow keys) replaced the limit set for good. The set an ISO type moved
  is remembered and put back when the type leaves the ISO types.
* B8-1075 (Knut, 5822758830): *"Keep whatever was in the "Judged against",
  as long as it is one of the 4 that are allowed. If selected "Judged
  against" are one of the other types not allowed, then the "Judged
  against" is set to the matching ISO 12647 type that belongs to the Report
  type (not the custom ISO)."*
* B8-1076: the README and the landing page.

Each test names the mutation that turns it red; every one was run.
"""
from __future__ import annotations

import re
from pathlib import Path
from types import SimpleNamespace

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication

from workflow import compliance_sets as cs
from workflow import measurement_report as mr

ROOT = Path(__file__).resolve().parent.parent
ISO4 = {"iso_12647_7", "iso_12647_8", "custom_iso_12647_7",
        "custom_iso_12647_8"}
CHROMIQ3 = ("chromiq_default", "chromiq_tight", "chromiq_quick")


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


def _edit_one_number(dlg, qapp):
    """Nudge one editable number of a ChromIQ column, as a user would."""
    from ui.dialogs.thresholds_dialog import RUN_COLUMN
    from ui.widgets import NoScrollDoubleSpinBox
    for (col, _rid), w in dlg._cells.items():
        if col != RUN_COLUMN and col in CHROMIQ3 \
                and isinstance(w, NoScrollDoubleSpinBox) and w.isEnabled() \
                and w.value() > 0:
            w.setValue(w.value() + 0.1)
            qapp.processEvents()
            return col
    raise AssertionError("no editable number in a ChromIQ column")


def _assert_held(radios, label):
    assert radios, f"no {label} radios to check"
    for sid, rb in radios.items():
        assert rb.isEnabled() == (sid in ISO4), f"{label}: {sid}"


# -------------------------------------------------------------- B8-1071
@pytest.mark.parametrize("door", ["preferences", "report window"])
def test_an_edited_number_leaves_the_iso_hold_on_every_default_radio(
        door, qapp, repo_values):
    """MUTATION: drop `_hold_radio_to_type` from `_write_overrides` -> the
    three ChromIQ "Default for new reports" radios come back live (red)."""
    from core.settings import AppSettings, compliance_overrides_of
    from ui.dialogs.thresholds_dialog import (ReportLimitsColumn,
                                              ThresholdsDialog)
    from workflow.run_compliance import run_limits
    s = AppSettings()
    s.set("report_default_type", mr.REPORT_TYPE_FULL)
    s.set("compliance_default_set", "chromiq_default")
    if door == "preferences":
        buf = {"overrides": compliance_overrides_of(s),
               "default_set": "iso_12647_7"}
        dlg = ThresholdsDialog(s, None, buffer=buf,
                               default_type=mr.REPORT_TYPE_ISO_7)
    else:
        s.set("report_default_type", mr.REPORT_TYPE_ISO_7)
        col = ReportLimitsColumn(run_limits(None, {}, "iso_12647_7"))
        own_run = SimpleNamespace(load_meta=lambda: SimpleNamespace(
            compliance_set_id=""))
        dlg = ThresholdsDialog(s, None, run=col, run_editable=True,
                               report_column=True, run_default=own_run,
                               report_type=mr.REPORT_TYPE_ISO_7,
                               default_type=mr.REPORT_TYPE_ISO_7)
    try:
        _assert_held(dlg._default_radios, "Default for new reports")
        _edit_one_number(dlg, qapp)
        _assert_held(dlg._default_radios, "Default for new reports")
        if door == "report window":
            _assert_held(dlg._run_default_radios, "Default for this run")
            _edit_one_number(dlg, qapp)
            _assert_held(dlg._run_default_radios, "Default for this run")
            # a greyed radio switched on from code is not recorded either
            dlg._run_default_radios["chromiq_quick"].setChecked(True)
            assert dlg.run_default_chosen != "chromiq_quick"
        # and a greyed radio switched on from code writes nothing
        dlg._default_radios["chromiq_quick"].setChecked(True)
        qapp.processEvents()
        if door == "preferences":
            assert buf["default_set"] == "iso_12647_7"
        else:
            assert s.get("compliance_default_set") in ISO4
    finally:
        s.set("report_default_type", mr.REPORT_TYPE_FULL)
        s.set("compliance_default_set", "chromiq_default")
        _close(dlg)


# -------------------------------------------------------------- B8-1072
def test_the_settings_store_never_writes_an_iso_type_beside_another_set(
        repo_values):
    """MUTATION: drop the guard from `AppSettings.set` -> Quick check is
    stored beside Contract proof check (red); drop the repair from
    `AppSettings.get` -> the bad pair on disk reads back as it is (red)."""
    from core.settings import AppSettings
    s = AppSettings()
    try:
        s.set("report_default_type", mr.REPORT_TYPE_ISO_7)
        s.set("compliance_default_set", "chromiq_quick")
        assert s._qs.value("compliance_default_set") == "iso_12647_7"
        assert s.get("compliance_default_set") == "iso_12647_7"
        # an allowed ISO set stays, the other standard's included (Knut)
        s.set("compliance_default_set", "custom_iso_12647_8")
        assert s.get("compliance_default_set") == "custom_iso_12647_8"
        # a type written beside a refused set moves the set
        s.set("report_default_type", mr.REPORT_TYPE_FULL)
        s.set("compliance_default_set", "chromiq_tight")
        assert s.get("compliance_default_set") == "chromiq_tight"
        s.set("report_default_type", mr.REPORT_TYPE_ISO_8)
        assert s._qs.value("compliance_default_set") == "iso_12647_8"
        # a bad pair already on disk is repaired when read
        s._qs.setValue("report_default_type", mr.REPORT_TYPE_ISO_7)
        s._qs.setValue("compliance_default_set", "chromiq_default")
        assert s.get("compliance_default_set") == "iso_12647_7"
        assert s._qs.value("compliance_default_set") == "iso_12647_7"
    finally:
        s.set("report_default_type", mr.REPORT_TYPE_FULL)
        s.set("compliance_default_set", "chromiq_default")


# -------------------------------------------------------------- B8-1073
def _walk(combo, key, n, qapp):
    combo.setFocus()
    for _ in range(n):
        QTest.keyClick(combo, key)
        qapp.processEvents()


def _choose(combo, data, qapp):
    i = combo.findData(data)
    assert i >= 0, data
    combo.setCurrentIndex(i)
    combo.activated.emit(i)
    qapp.processEvents()


def test_walking_the_preferences_type_past_an_iso_type_changes_nothing(
        qapp, repo_values):
    """MUTATION: drop the put-back from `_on_default_type_chosen` -> the
    walk leaves ISO 12647-8 as the default set (red); always move the set
    under an ISO type -> the Custom ISO set is replaced (red)."""
    from core.settings import AppSettings
    from ui.dialogs.settings_dialog import SettingsDialog
    s = AppSettings()
    s.set("report_default_type", mr.REPORT_TYPE_FULL)
    s.set("compliance_default_set", "chromiq_tight")
    dlg = SettingsDialog(s, None)
    dlg.show()
    qapp.processEvents()
    c = dlg._report_type_default_combo
    try:
        buf = dlg._compliance_buffer
        before = (c.currentData(), buf["default_set"])
        assert before == (mr.REPORT_TYPE_FULL, "chromiq_tight")
        seen = []
        c.activated.connect(lambda i: seen.append(c.itemData(i)))
        _walk(c, Qt.Key.Key_Down, 2, qapp)
        assert any(t in mr.REPORT_TYPE_ISO_SET for t in seen), (
            f"the walk never reached an ISO type: {seen}")
        _walk(c, Qt.Key.Key_Up, 2, qapp)
        assert (c.currentData(), buf["default_set"]) == before
        _choose(c, mr.REPORT_TYPE_ISO_7, qapp)
        assert buf["default_set"] == "iso_12647_7"
        _choose(c, mr.REPORT_TYPE_FULL, qapp)
        assert buf["default_set"] == "chromiq_tight"
        # Knut, 5822758830: an allowed ISO set is kept, nothing to put back
        buf["default_set"] = "custom_iso_12647_8"
        _choose(c, mr.REPORT_TYPE_ISO_7, qapp)
        assert buf["default_set"] == "custom_iso_12647_8"
        _choose(c, mr.REPORT_TYPE_FULL, qapp)
        assert buf["default_set"] == "custom_iso_12647_8"
    finally:
        _close(dlg)
        s.set("compliance_default_set", "chromiq_default")


# -------------------------------------------------------------- B8-1074
def _dialog(tmp_path, qapp):
    from tests.test_the_report_type_pulldown_stores_on_the_run import _dialog
    return _dialog(tmp_path, qapp)


def _state(dlg):
    return (dlg._type_combo.currentData(), dlg._set_combo.currentData(),
            dlg._report_limits().set_id, dlg._settings_were_modified())


def test_walking_the_report_window_type_past_an_iso_type_changes_nothing(
        tmp_path, qapp, repo_values):
    """MUTATION: drop the put-back from `_on_type_chosen` -> the walk leaves
    "Judged against" on ISO 12647-8 (red); always move the set under an ISO
    type -> the Custom ISO set is replaced (red)."""
    dlg, _run = _dialog(tmp_path, qapp)
    try:
        i = dlg._set_combo.findData("chromiq_tight")
        dlg._set_combo.setCurrentIndex(i)
        qapp.processEvents()
        assert dlg._type_combo.currentData() == mr.REPORT_TYPE_FULL
        before = _state(dlg)
        assert before[2] == "chromiq_tight"
        seen = []
        dlg._type_combo.currentIndexChanged.connect(
            lambda i: seen.append(dlg._type_combo.itemData(i)))
        _walk(dlg._type_combo, Qt.Key.Key_Down, 2, qapp)
        assert any(t in mr.REPORT_TYPE_ISO_SET for t in seen), (
            f"the walk never reached an ISO type: {seen}")
        _walk(dlg._type_combo, Qt.Key.Key_Up, 2, qapp)
        assert _state(dlg) == before
        dlg._type_combo.setCurrentIndex(
            dlg._type_combo.findData(mr.REPORT_TYPE_ISO_7))
        qapp.processEvents()
        assert dlg._report_limits().set_id == "iso_12647_7"
        dlg._type_combo.setCurrentIndex(
            dlg._type_combo.findData(mr.REPORT_TYPE_FULL))
        qapp.processEvents()
        assert _state(dlg) == before
        # Knut, 5822758830: an allowed ISO set is kept
        dlg._set_combo.setCurrentIndex(
            dlg._set_combo.findData("custom_iso_12647_8"))
        qapp.processEvents()
        dlg._type_combo.setCurrentIndex(
            dlg._type_combo.findData(mr.REPORT_TYPE_ISO_7))
        qapp.processEvents()
        assert dlg._report_limits().set_id == "custom_iso_12647_8"
        assert dlg._set_combo.currentData() == "custom_iso_12647_8"
    finally:
        _close(dlg)


# -------------------------------------------------------------- B8-1075
def test_knut_an_allowed_iso_set_is_kept(qapp, repo_values):
    """The presets window and the starting pair. MUTATION: move the presets
    window's set on every ISO type -> red; `set_held_to_type` returning the
    type's set always -> red."""
    assert mr.set_held_to_type(mr.REPORT_TYPE_ISO_7, "iso_12647_8") \
        == "iso_12647_8"
    assert mr.set_held_to_type(mr.REPORT_TYPE_ISO_8, "custom_iso_12647_7") \
        == "custom_iso_12647_7"
    assert mr.set_held_to_type(mr.REPORT_TYPE_ISO_8, "chromiq_quick") \
        == "iso_12647_8"
    from ui.dialogs.preset_verification_dialog import PresetVerificationDialog
    dlg = PresetVerificationDialog([])
    try:
        dlg._set_combo.setCurrentIndex(
            dlg._set_combo.findData("custom_iso_12647_8"))
        dlg._type_combo.setCurrentIndex(
            dlg._type_combo.findData(mr.REPORT_TYPE_ISO_7))
        qapp.processEvents()
        assert dlg.current_set() == "custom_iso_12647_8"
    finally:
        dlg.deleteLater()


# -------------------------------------------------------------- B8-1076
def test_the_readme_and_the_site_say_a_calibration_gets_no_iso_type():
    """MUTATION: the old "a verification or a calibration gets the judged
    types" sentence back -> red."""
    for path in (ROOT / "README.md", ROOT / "docs" / "index.html"):
        text = re.sub(r"\s+", " ", path.read_text(encoding="utf-8"))
        assert "a verification or a calibration gets the judged types" \
            not in text, path.name
        assert "without the two ISO types" in text, path.name


def test_the_sites_beta_link_names_no_beta_number():
    """The link's TAG follows core/version.py (test_the_site_offers_the_
    current_beta); its TEXT must not carry a number that stays behind when
    the version moves. MUTATION: "4.3.0 beta 41" as the link text -> red."""
    text = (ROOT / "docs" / "index.html").read_text(encoding="utf-8")
    anchors = re.findall(
        r'<a [^>]*releases/tag/v[^"]*"[^>]*>(.*?)</a>', text, re.S)
    assert anchors
    for a in anchors:
        assert not re.search(r"beta\s*\.?\s*\d", a), a
    assert "in that beta" not in re.sub(r"\s+", " ", text)
