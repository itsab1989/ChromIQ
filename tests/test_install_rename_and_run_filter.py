"""Knut's install-rename checkbox + the report's per-run deselection
(both 2026-08-10)."""
from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtCore import QSettings, Qt                    # noqa: E402
from PyQt6.QtWidgets import QApplication                  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


# ---- the builder names the installed COPY only ---------------------------
def test_install_profile_renames_only_the_copy(tmp_path, monkeypatch):
    import workflow.profile_builder as pb
    monkeypatch.setattr(pb, "_profile_dir", lambda: tmp_path / "installed")
    icc = tmp_path / "printer-test.icc"
    icc.write_bytes(b"icc")
    b = pb.ProfileBuilder.__new__(pb.ProfileBuilder)
    dest = pb.ProfileBuilder.install_profile(b, icc, "Epson P900 Canson Baryta")
    assert dest.name == "Epson P900 Canson Baryta.icc"
    assert dest.read_bytes() == b"icc"
    assert icc.exists() and icc.name == "printer-test.icc"   # source untouched
    # Without a name the plain copy behaviour is unchanged.
    dest2 = pb.ProfileBuilder.install_profile(b, icc, None)
    assert dest2.name == "printer-test.icc"


# ---- the tab derives the name from the description -----------------------
def _profile_tab(tmp_path):
    from core.argyll_runner import ArgyllRunner
    from core.settings import AppSettings
    from ui.tabs.tab_profile import TabProfile
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    return TabProfile(ArgyllRunner(s), s), s


def test_install_name_follows_checkbox_and_description(qapp, tmp_path):
    tab, s = _profile_tab(tmp_path)
    tab._desc_edit.setText('Epson P900 / Baryta "matt" 2026')
    assert tab._install_name() is None            # checkbox off → plain copy
    tab._install_name_cb.setChecked(True)
    assert s.get("install_named_by_description", False)
    assert tab._m_install_name_cb.isChecked()     # the two boxes stay in step
    assert tab._install_name() == "Epson P900 _ Baryta _matt_ 2026"
    tab._desc_edit.setText("   ")
    assert tab._install_name() is None            # empty description → plain
    tab._m_install_name_cb.setChecked(False)
    assert not tab._install_name_cb.isChecked()


# ---- report: unticking a run leaves it out, honestly ---------------------
def test_report_run_deselection_filters_and_says_so(qapp, tmp_path):
    from tests.test_import_measurement_module import (_cgats, _PATCHES,
                                                      _verify_env)
    s, fm, ctl, run = _verify_env(tmp_path)
    import os as _os, time as _time
    for i in range(3):
        v = run.new_verification()
        v.ensure_dir()
        v.measurement_ti3.write_text(_cgats("CTI3", _PATCHES))
        t = _time.time() - 300 + i * 60
        _os.utime(v.measurement_ti3, (t, t))
    first = run.verifications()[0].measurement_ti3

    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    dlg = MeasurementReportDialog(s, None, initial_ti3=first)
    try:
        assert len(dlg._history) == 3
        assert len(dlg._runs_for_report()) == 3
        # The list holds 1 source row + 3 checkable run rows.
        run_rows = [i for i, (k, _s, _key) in enumerate(dlg._list_rows)
                    if k == "run"]
        assert len(run_rows) == 3
        item = dlg._profile_list.item(run_rows[1])
        item.setCheckState(Qt.CheckState.Unchecked)
        assert len(dlg._runs_for_report()) == 2
        assert len(dlg._history) == 3              # nothing on disk / in memory lost
        html = dlg._scope_html(dlg._runs_for_report())
        assert "hidden by you" in html
        # Re-ticking brings it straight back.
        item.setCheckState(Qt.CheckState.Checked)
        assert len(dlg._runs_for_report()) == 3
        assert "hidden by you" not in dlg._scope_html(dlg._runs_for_report())
    finally:
        dlg.deleteLater()


def test_report_list_shows_at_least_five_rows_and_fits_the_screen(qapp, tmp_path):
    """The run list used to sit fixed at ~3 visible rows and the window's
    bottom could land off-screen (Sebastian, 2026-08-10). Both are sized
    dynamically now."""
    from tests.test_import_measurement_module import (_cgats, _PATCHES,
                                                      _verify_env)
    s, fm, ctl, run = _verify_env(tmp_path)
    v = run.new_verification()
    v.ensure_dir()
    v.measurement_ti3.write_text(_cgats("CTI3", _PATCHES))

    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    dlg = MeasurementReportDialog(s, None, initial_ti3=v.measurement_ti3)
    try:
        dlg.show()
        qapp.processEvents()
        row_h = dlg._profile_list.sizeHintForRow(0)
        assert row_h > 0
        # Two rows fit without a scrollbar; the list never demands a hard
        # multi-row floor (that floor once pushed the window past the screen).
        assert dlg._profile_list.height() >= 2 * row_h

        # The height fit is the bug that was reported (the window's bottom
        # sat off-screen); width is bounded separately by the 920 px content
        # floor and is not this test's concern — the offscreen test screen
        # is narrower than any real display this window targets.
        scr = dlg.screen().availableGeometry()
        g = dlg.geometry()
        assert g.y() + g.height() <= scr.y() + scr.height() + 1
    finally:
        dlg.hide()
        dlg.deleteLater()


def test_report_list_caps_and_scrolls_for_many_runs(qapp, tmp_path):
    from tests.test_import_measurement_module import (_cgats, _PATCHES,
                                                      _verify_env)
    import os as _os
    import time as _time
    s, fm, ctl, run = _verify_env(tmp_path)
    for i in range(11):
        v = run.new_verification()
        v.ensure_dir()
        v.measurement_ti3.write_text(_cgats("CTI3", _PATCHES))
        t = _time.time() - 3600 + i * 60
        _os.utime(v.measurement_ti3, (t, t))

    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    first = run.verifications()[0].measurement_ti3
    dlg = MeasurementReportDialog(s, None, initial_ti3=first)
    try:
        dlg.show()
        qapp.processEvents()
        assert len(dlg._list_rows) == 12         # 1 source + 11 run rows
        row_h = dlg._profile_list.sizeHintForRow(0)
        assert row_h > 0
        # Knut's beta.5 design replaced the per-list cap: the list shows ALL
        # its rows (no scrollbar of its own), and the ONE capped scroll frame
        # above the chart tabs takes the overflow — the charts and the report
        # below always keep their room.
        assert dlg._profile_list.height() >= 12 * row_h, \
            "the list must show every row inside the capped frame"
        from PyQt6.QtWidgets import QScrollArea
        assert any(w.maximumHeight() <= 400
                   for w in dlg.findChildren(QScrollArea)), \
            "the capped top scroll frame is gone"
        scr = dlg.screen().availableGeometry()
        g = dlg.geometry()
        assert g.y() + g.height() <= scr.y() + scr.height() + 1
    finally:
        dlg.hide()
        dlg.deleteLater()


def test_pdf_default_location_follows_the_four_tier_design(qapp, tmp_path):
    """Knut's "Where are my files?" design (reconfirmed 2026-08-10): the PDF's
    proposed folder is the reports/ folder of the tightest place containing
    exactly the SELECTED data — one dated check → that date's reports/;
    several checks of one run → verifications/reports/ (NOT the project root,
    even with "Show all measurement runs" on)."""
    from tests.test_import_measurement_module import (_cgats, _PATCHES,
                                                      _verify_env)
    s, fm, ctl, run = _verify_env(tmp_path)
    import os as _os, time as _time
    for i in range(3):
        v = run.new_verification()
        v.ensure_dir()
        v.measurement_ti3.write_text(_cgats("CTI3", _PATCHES))
        t = _time.time() - 300 + i * 60
        _os.utime(v.measurement_ti3, (t, t))
    verifs = run.verifications()
    first = verifs[0].measurement_ti3

    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    dlg = MeasurementReportDialog(s, None, initial_ti3=first)
    try:
        # Several dated checks of ONE run selected → verifications/reports.
        assert dlg._all_runs_check.isChecked()
        assert len(dlg._runs_for_report()) == 3
        assert dlg._report_dir() == run.verifications_dir / "reports"

        # Untick down to a single date → that date's own reports folder.
        run_rows = [i for i, (k, _s, _key) in enumerate(dlg._list_rows)
                    if k == "run"]
        kept = None
        for idx in run_rows[1:]:
            dlg._profile_list.item(idx).setCheckState(Qt.CheckState.Unchecked)
        (only,) = dlg._runs_for_report()
        kept = Path(only["_origin_dir"])
        assert kept.name.startswith("2026-")          # a dated folder
        assert dlg._report_dir() == kept / "reports"

        # All-runs OFF → the single shown measurement's own dated folder
        # (the dialog anchors the newest date; tier 1 follows what is shown).
        dlg._all_runs_check.setChecked(False)
        shown = Path(dlg._report["_origin_dir"])
        assert shown.parent == run.verifications_dir
        assert dlg._report_dir() == shown / "reports"
    finally:
        dlg.deleteLater()
