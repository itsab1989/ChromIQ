"""B8-388 and B8-392 — where a Measurement Report's settings come from.

Knut, 2026-09-18, on issue #182, after asking where the report ChromIQ writes
by itself gets its settings and being told that two of the five are specified
nowhere at all (§13.5)::

    I suggest that the automatic record should itself carry a document block,
    so that "Show all measurement runs" and "Show detailed data for each run"
    are a fact on disk rather than an inference when it is loaded. Bot set to
    OFF as default. However, when the Measurement window appears, the latest
    report shall load automatically with its settings.

    Regarding "the report type": The type belongs to the run, yes, but the
    default should be the "Full colour check".

    The "Save measurement report" should be ON, visible in the settings
    on-screen (measurement tab?) when "Preferences -> reports" "Save
    measurement report after each measurement" is set (should be default ON).
    When ... is OFF, then "Save measurement report" is default OFF, but a user
    may still change it to ON. "Save measurement report" parameter is also
    remembered as all other settings are remembered for a run.

    1. "Measurement Report limits" frame is renamed to "Measurement Report
       Defaults" frame.
    2. Below the Report Limits button ... add a pulldown selector to select
       "Report type, default" ...
    3. Add two checkboxes to set the default value for "Show all measurement
       runs" and "Show detailed data for each run". These shall be default ON.
       however, during automatic saving of a report during measurement, these
       are always OFF (that is natural because it is one measurement only)
    4. The Report Limits button contain the Judged Against default chosen, so
       no separate selection box is needed in the Preferences -> Reports tab.

    In the "Measurement Report" window, when "Report shown" is set to "New
    report....", all default values shall be loaded on the settings, which then
    can be changed by a user. The default values are fetched from the
    preferences->reports tab.

and, asked whether "New report…" is first or last and whether it is selected
when a run has none::

    The default when loading the Measurement Report window is the latest report
    created. "New report..." should be at the top of the list in the pulldown.

and the naming rules of B8-392::

    If "Show all measurement runs" is ON and all measurement dates are marked
    to be included, then the name should include the flag "All dates". ... "One
    date". ... "Multiple dates". ... If the list of measurement dates to be
    included only holds one measurement, then the "Show all measurement runs"
    is automatically set to OFF, and the report name should include the flag
    "One date". This should include all the automatically created reports
    during measurement. ... If "Show detailed data for each run" in ON, the
    name should include the flag "Detailed".

**NOTHING HERE MAY DELETE, RENAME OR REWRITE A FILE ON A USER'S DISK**, which
is the constraint the whole of B8-380 to B8-384 was built under. The document
block the measurement-time record now carries is additive and `REPORT_SCHEMA`
stays 7.

**AND ONE OF THE THREE DEFAULTS WAS WITHDRAWN TWO DAYS LATER (B8-590).** Knut,
2026-09-20, on the box his point 3 asked for a default for::

    I realise now this checkbox is not a reasonable feature to have (and has
    evolved to something that it was not originally used) and should be
    removed ... The feature that actually is desired here is a button "Select
    All" ... and a button "Deselect All" ... Remove the feature "Show all
    measurement runs" totally from the design, and any feature that belongs to
    that button ... only the selected/ticked measurements shall be part of the
    report when created/updated (always).

So "Show all measurement runs, by default" is gone from Preferences ▸ Reports,
the key `report_default_show_all_runs` is gone from `core/settings.py`, and the
B8-392 rule that turned the box off and greyed it on a one-measurement list has
nothing left to turn off. Everything else below is unchanged: the other two
defaults, the naming flags, and where a new report's settings come from. What
"the whole history" means is now a LIST state, reached with the "Select all"
button he asked for, and each check that used to set or read the box says so
where it does it.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest                                                   # noqa: E402
from PyQt6.QtCore import QSettings                              # noqa: E402
from PyQt6.QtWidgets import QApplication, QGroupBox             # noqa: E402

from core.settings import AppSettings                           # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _settings(tmp_path, **kw) -> AppSettings:
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    for k, v in kw.items():
        s.set(k, v)
    return s


def _only_this_measurement(dlg, qapp):
    """Untick every row but the one the window was opened on.

    What `dlg._all_runs_check.setChecked(False)` used to mean, in the
    vocabulary that is left: a report covers the measurements that are ticked
    (B8-590), so "one measurement" is a state of the LIST now.

    **THE OTHER ROWS ARE UNTICKED ONE BY ONE, AND NOT THROUGH "Deselect
    all".** Both reach the same ticks, but the button passes through a state
    where NOTHING is ticked, and a repaint taken there re-stamps
    `_doc_built_with` from it: putting the last tick back then leaves the
    window saying the settings have moved when they are exactly where the
    document was built, and Generate asks "Update or Create New?" about a
    document nobody changed. That is a fault in its own right and is reported
    separately; it is not what these checks are about, and unticking the rows
    you do not want is what a reader does anyway.
    """
    from PyQt6.QtCore import Qt
    here = dlg._run_key(dlg._report)
    found = False
    for i, (kind, _si, key) in enumerate(dlg._list_rows):
        if kind != "run" or key is None:
            continue
        if key == here:
            found = True
            continue
        dlg._profile_list.item(i).setCheckState(Qt.CheckState.Unchecked)
    qapp.processEvents()
    assert found, f"the window's measurement has no row: {here!r}"
    assert [dlg._run_key(r) for r in dlg._runs_for_report()] == [here]


def _every_measurement(dlg, qapp):
    """Tick them all, which is what the removed box ON used to mean."""
    dlg._select_all_btn.click()
    qapp.processEvents()
    assert dlg._hidden_runs == set(), dlg._hidden_runs


# ---------------------------------------------------------------------------
# 1. Preferences ▸ Reports
# ---------------------------------------------------------------------------
def _prefs(s, qapp):
    from ui.dialogs.settings_dialog import SettingsDialog
    return SettingsDialog(s)


def test_the_frame_is_named_measurement_report_defaults(tmp_path, qapp):
    """His point 1, and it is the name a user looks for.

    MUTATION: put "Measurement Report limits" back and this goes red.
    """
    d = _prefs(_settings(tmp_path), qapp)
    try:
        titles = [g.title() for g in d.findChildren(QGroupBox)]
        assert "Measurement Report Defaults" in titles, titles
        assert "Measurement Report limits" not in titles, titles
    finally:
        d.deleteLater()


def test_the_two_defaults_that_are_left_are_on_screen_and_default_on(tmp_path,
                                                                     qapp):
    """His points 2 and 3, **minus the box he withdrew (B8-590)**: a "Report
    type, default" pulldown under the Report limits button, and the ONE tick
    box that is left, default ON.

    It used to be two boxes. "Show all measurement runs, by default" set the
    starting state of a control that no longer exists, so a preference for it
    has nothing to start; Knut, 2026-09-20: *"Remove the feature 'Show all
    measurement runs' totally from the design, and any feature that belongs to
    that button"*. Its absence is asserted here rather than left unwatched.

    MUTATION: flip the `report_default_show_details` default in
    `core/settings.py` to False, drop a control from `_build_reports_tab`, or
    build the removed box again, and this goes red.
    """
    from workflow.measurement_report import REPORT_TYPE_FULL
    d = _prefs(_settings(tmp_path), qapp)
    try:
        assert d._report_type_default_combo.currentData() == REPORT_TYPE_FULL, (
            "the default report type is not Full colour check")
        assert getattr(d, "_report_all_runs_default_check", None) is None, (
            "“Show all measurement runs, by default” is still built")
        assert d._report_details_default_check.isChecked()
        # …and the two ISO types are offered and refused, exactly as the report
        # window offers them: shown, so the reason can be read; disabled, so
        # they cannot be stored.
        model = d._report_type_default_combo.model()
        from workflow.measurement_report import (REPORT_TYPE_ISO_7,
                                                 REPORT_TYPE_ISO_8)
        for tid in (REPORT_TYPE_ISO_7, REPORT_TYPE_ISO_8):
            row = d._report_type_default_combo.findData(tid)
            assert row >= 0, f"{tid} is not offered at all"
            assert not model.item(row).isEnabled(), f"{tid} can be chosen"
    finally:
        d.deleteLater()


def test_there_is_no_second_judged_against_selector(tmp_path, qapp):
    """His point 4: *"The Report Limits button contain the Judged Against
    default chosen, so no separate selection box is needed"*.

    MUTATION: add a limit-set pulldown to the Reports tab and this goes red.
    """
    from PyQt6.QtWidgets import QComboBox
    d = _prefs(_settings(tmp_path), qapp)
    try:
        page = d._build_reports_tab()
        datas = {str(c.itemData(i) or "")
                 for c in page.findChildren(QComboBox)
                 for i in range(c.count())}
        assert "chromiq_default" not in datas, (
            "the Reports tab offers a limit set of its own; the Report limits "
            "button already carries that choice")
        page.deleteLater()
    finally:
        d.deleteLater()


def test_the_defaults_are_written_and_read_back(tmp_path, qapp):
    """The app's own sequence: load the dialog, move the controls, press Save,
    build it again.

    MUTATION: drop either `s.set("report_default_…")` line from
    `_save_and_close` and this goes red.
    """
    from workflow.measurement_report import REPORT_TYPE_GREY
    s = _settings(tmp_path)
    d = _prefs(s, qapp)
    try:
        d._report_type_default_combo.setCurrentIndex(
            d._report_type_default_combo.findData(REPORT_TYPE_GREY))
        d._report_details_default_check.setChecked(False)
        d._save_and_close()
    finally:
        d.deleteLater()
    assert s.get("report_default_type") == REPORT_TYPE_GREY
    assert bool(s.get("report_default_show_details")) is False
    # …and the withdrawn one is not written either (B8-590). A Save that still
    # stored `report_default_show_all_runs` would keep a dead key alive in
    # every user's settings file and invite the next reader to honour it.
    assert s.get("report_default_show_all_runs") is None, (
        "Save still writes the preference of the removed box")
    again = _prefs(s, qapp)
    try:
        assert again._report_type_default_combo.currentData() == REPORT_TYPE_GREY
        assert not again._report_details_default_check.isChecked()
    finally:
        again.deleteLater()


# ---------------------------------------------------------------------------
# 2. the automatic measurement-time record
# ---------------------------------------------------------------------------
def _a_measured_run(tmp_path):
    """A profile run with a real measurement beside it, and the Measure tab
    wired to it, which is what writes the automatic report."""
    from tests.test_import_measurement_module import (_cgats, _PATCHES,
                                                      _verify_env)
    s, fm, ctl, run = _verify_env(tmp_path)
    v = run.new_verification()
    v.ensure_dir()
    v.measurement_ti3.write_text(_cgats("CTI3", _PATCHES), encoding="utf-8")
    return s, fm, ctl, run, v


def _measure_tab(s, qapp):
    from core.argyll_runner import ArgyllRunner
    from ui.tabs.tab_measure import TabMeasure
    tab = TabMeasure(ArgyllRunner(s), s)
    qapp.processEvents()
    return tab


def test_the_automatic_record_carries_a_document_of_its_own(tmp_path, qapp):
    """*"the automatic record should itself carry a document block, so that
    'Show all measurement runs' and 'Show detailed data for each run' are a
    fact on disk rather than an inference when it is loaded. Bot set to OFF as
    default."*

    Driven through `_maybe_save_measurement_report`, which is the app's own
    writer and the only place ChromIQ writes a report by itself.

    MUTATION, to be proved to land: delete the
    `self._stamp_the_automatic_document(...)` call from
    `_maybe_save_measurement_report`.
    """
    from workflow.measurement_report import (REPORT_TYPE_FULL, list_reports,
                                             recorded_document)
    s, _fm, _ctl, _run, v = _a_measured_run(tmp_path)
    tab = _measure_tab(s, qapp)
    try:
        tab._maybe_save_measurement_report(v.measurement_ti3)
    finally:
        tab.deleteLater()
    paths = list_reports(v.dir)
    assert len(paths) == 1, paths
    doc = recorded_document(json.loads(Path(paths[0]).read_text(
        encoding="utf-8")))
    assert doc is not None, "the measurement-time record carries no document"
    assert doc["all_runs"] is False and doc["detail"] is False, doc
    assert doc["type"] == REPORT_TYPE_FULL, doc["type"]
    assert len(doc["measurements"]) == 1, doc["measurements"]
    assert doc["measurements"][0]["ti3"] == v.measurement_ti3.name


def test_the_automatic_records_type_is_the_preferences_default(tmp_path,
                                                               qapp):
    """K31 turned this test round (it was
    `test_the_automatic_records_type_follows_the_run_then_preferences`, D9).
    Knut, 5801677743: the report after a measurement is that date's own
    report with its own settings, and a new report starts on *"the defaults
    in preferences -> reports"*. A type an earlier ChromIQ stored on the run
    no longer decides it.

    MUTATION: make `new_report_type` (or the Measure tab) read the run's
    stored type again (`report_type_default_for(run, ...)`) and this goes
    red.
    """
    from workflow.measurement_report import (REPORT_TYPE_GREY,
                                             REPORT_TYPE_SUMMARY, list_reports,
                                             recorded_document)
    from tests.helpers.legacy_run_meta import (set_run_report_type)
    s, _fm, _ctl, run, v = _a_measured_run(tmp_path)
    s.set("report_default_type", REPORT_TYPE_SUMMARY)
    tab = _measure_tab(s, qapp)
    try:
        tab._maybe_save_measurement_report(v.measurement_ti3)
        first = recorded_document(json.loads(
            Path(list_reports(v.dir)[-1]).read_text(encoding="utf-8")))
        assert first["type"] == REPORT_TYPE_SUMMARY, (
            "the automatic report ignored the Preferences default")
        set_run_report_type(run, REPORT_TYPE_GREY)       # an earlier ChromIQ's
        tab._maybe_save_measurement_report(v.measurement_ti3)
        newest = sorted(list_reports(v.dir))[-1]
        second = recorded_document(json.loads(
            Path(newest).read_text(encoding="utf-8")))
        assert second["type"] == REPORT_TYPE_SUMMARY, (
            "a type stored on the run by an earlier ChromIQ decided the "
            "automatic report")
    finally:
        tab.deleteLater()


def test_the_automatic_record_is_named_one_date(tmp_path, qapp):
    """B8-392's fourth rule: *"This should include all the automatically
    created reports during measurement."*

    MUTATION: stamp `scope=SCOPE_ALL_DATES` in
    `_stamp_the_automatic_document` and this goes red.
    """
    from workflow.measurement_report import (SCOPE_ONE_DATE, document_scope_of,
                                             list_reports, recorded_document)
    s, _fm, _ctl, _run, v = _a_measured_run(tmp_path)
    tab = _measure_tab(s, qapp)
    try:
        tab._maybe_save_measurement_report(v.measurement_ti3)
    finally:
        tab.deleteLater()
    doc = recorded_document(json.loads(
        Path(list_reports(v.dir)[0]).read_text(encoding="utf-8")))
    # THE RECORDED ID, not the derived one: `document_scope_of` answers "One
    # date" for a file with no block at all, so asking it alone would pass over
    # a record that carries nothing.
    assert doc is not None and doc.get("scope") == SCOPE_ONE_DATE, doc
    assert document_scope_of(doc) == SCOPE_ONE_DATE


def test_the_block_is_additive_and_the_schema_does_not_move(tmp_path, qapp):
    """The absolute constraint, again: a ChromIQ that has never heard of the
    document block must read this file exactly as it did.

    MUTATION: raise `REPORT_SCHEMA` and this goes red.
    """
    from workflow.measurement_report import REPORT_SCHEMA, list_reports
    s, _fm, _ctl, _run, v = _a_measured_run(tmp_path)
    tab = _measure_tab(s, qapp)
    try:
        tab._maybe_save_measurement_report(v.measurement_ti3)
    finally:
        tab.deleteLater()
    rep = json.loads(Path(list_reports(v.dir)[0]).read_text(encoding="utf-8"))
    assert rep["schema"] == REPORT_SCHEMA == 7
    # every field the previous shape carried is still there and unchanged in
    # meaning; the block sits beside them under one key.
    for key in ("created", "ti3", "chart", "patches", "compliance",
                "report_type"):
        assert key in rep, key


# ---------------------------------------------------------------------------
# 3. "Save measurement report" on the Measure tab
# ---------------------------------------------------------------------------
def test_the_measure_tab_shows_the_save_switch_and_it_starts_from_preferences(
        tmp_path, qapp):
    """*"'Save measurement report' should be ON, visible in the settings
    on-screen (measurement tab?) when ... is set (should be default ON). When
    ... is OFF, then 'Save measurement report' is default OFF, but a user may
    still change it to ON."*

    MUTATION: hard-code `setChecked(True)` in the constructor and the second
    half goes red.
    """
    s_on = _settings(tmp_path / "on")
    tab = _measure_tab(s_on, qapp)
    try:
        assert tab._save_report_cb.isVisibleTo(tab), (
            "the switch is not on screen in the Measure tab")
        assert tab._save_report_cb.isChecked(), "it does not default ON"
        assert tab._save_report_cb.isEnabled(), (
            "a user may still change it, whatever the preference says")
    finally:
        tab.deleteLater()
    s_off = _settings(tmp_path / "off", save_measurement_report=False)
    tab2 = _measure_tab(s_off, qapp)
    try:
        assert not tab2._save_report_cb.isChecked(), (
            "the preference is off and the run's own switch did not follow it")
        assert tab2._save_report_cb.isEnabled()
    finally:
        tab2.deleteLater()


def test_the_switch_and_not_the_preference_decides(tmp_path, qapp):
    """The half that makes *"but a user may still change it to ON"* mean
    anything: the preference is OFF, the box is ticked, and a report is
    written.

    MUTATION: read `self._settings.get("save_measurement_report")` in
    `_maybe_save_measurement_report` again and this goes red.
    """
    from workflow.measurement_report import list_reports
    s, _fm, _ctl, _run, v = _a_measured_run(tmp_path)
    s.set("save_measurement_report", False)
    tab = _measure_tab(s, qapp)
    try:
        tab._save_report_cb.setChecked(False)
        tab._maybe_save_measurement_report(v.measurement_ti3)
        assert not list_reports(v.dir), "a report was written with the box off"
        tab._save_report_cb.setChecked(True)
        tab._maybe_save_measurement_report(v.measurement_ti3)
        assert len(list_reports(v.dir)) == 1, (
            "the box was ticked and no report was written")
    finally:
        tab.deleteLater()


def test_the_switch_is_remembered_for_the_run(tmp_path, qapp):
    """*"'Save measurement report' parameter is also remembered as all other
    settings are remembered for a run."*

    **THE APP'S OWN SEQUENCE**, which is what `MainWindow` calls on leaving a
    tab and on changing target: `save_target_settings`, then
    `load_target_settings` back.

    MUTATION, to be proved to land: remove `"save_measurement_report"` from
    `MEASURE_CONTROLS` and this goes red.
    """
    from workflow.measure_settings import snapshot
    s, fm, _ctl, run, _v = _a_measured_run(tmp_path)
    tab = _measure_tab(s, qapp)
    try:
        tab._save_report_cb.setChecked(False)
        assert tab.save_target_settings(run) is True
        stored = run.load_meta().measure_settings
        assert "save_measurement_report" in stored, sorted(stored)
        assert stored["save_measurement_report"]["value"] is False
        # …and it comes back on screen, through the reader the tab uses
        tab._save_report_cb.setChecked(True)
        from workflow.measure_settings import apply
        apply(tab, stored)
        assert not tab._save_report_cb.isChecked(), (
            "the stored value did not reach the control")
        assert snapshot(tab)["save_measurement_report"]["value"] is False
    finally:
        tab.deleteLater()


def test_a_run_with_nothing_stored_opens_on_the_preference(tmp_path, qapp):
    """§4 S4-S7 of `per_target_settings.md`: a target with nothing stored opens
    on its defaults, and for this one the default lives in Preferences.

    MUTATION: drop the `_save_report_cb` line from `_restore_defaults` and this
    goes red.
    """
    s, _fm, _ctl, _run, _v = _a_measured_run(tmp_path)
    s.set("save_measurement_report", False)
    tab = _measure_tab(s, qapp)
    try:
        tab._save_report_cb.setChecked(True)
        tab._restore_defaults()
        assert not tab._save_report_cb.isChecked(), (
            "a run with nothing stored kept the last run's answer")
    finally:
        tab.deleteLater()


# ---------------------------------------------------------------------------
# 4. "New report…", and what the window opens on
# ---------------------------------------------------------------------------
def _report_window(s, ti3, qapp):
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    dlg = MeasurementReportDialog(s, None, initial_ti3=ti3)
    dlg.show()
    qapp.processEvents()
    # **KNUT'S BETA-25 QUESTION, ANSWERED "Create New" (B8-491).** Generate
    # report now asks what to do when a report from "Report shown" is selected
    # and one of its five settings has moved, and the answer decides whether a
    # new report is written or the selected one is updated. Every test in this
    # file was written for the behaviour his "Create New" button keeps, so that
    # is what these windows answer. The QUESTION itself, and the Update button,
    # are guarded in `tests/test_generate_report_asks_what_to_do.py`.
    dlg._questions_asked = []

    def _answer_create_new():
        dlg._questions_asked.append("asked")
        return "new"

    dlg._ask_update_or_create_new = _answer_create_new
    return dlg


def _generated_project(tmp_path, qapp, presses=2):
    """A run with two dated verifications and *presses* generated DOCUMENTS,
    written by the window's own button, so the list holds real documents and
    not only the per-measurement records."""
    from tests.test_a_generated_report_is_one_document import _messy_project
    s, fm, run, vs = _messy_project(tmp_path, dates=2)
    dlg = _report_window(s, vs[-1].measurement_ti3, qapp)
    try:
        dlg._say_generated = lambda saved, failed: None
        for _ in range(presses):
            dlg._on_generate_report()
            qapp.processEvents()
    finally:
        dlg.close()
    return s, fm, run, vs


def test_new_report_is_the_first_entry_in_the_pulldown(tmp_path, qapp):
    """*"'New report...' should be at the top of the list in the pulldown."*

    MUTATION: add the entry after the documents instead of before them and
    this goes red.
    """
    from ui.dialogs.measurement_report_dialog import NEW_REPORT_KEY
    s, _fm, _run, vs = _generated_project(tmp_path, qapp)
    dlg = _report_window(s, vs[-1].measurement_ti3, qapp)
    try:
        assert dlg._saved_combo.itemData(0) == NEW_REPORT_KEY, [
            dlg._saved_combo.itemData(i)
            for i in range(dlg._saved_combo.count())]
        assert dlg._saved_combo.count() > 1, "no document is listed beside it"
    finally:
        dlg.close()


def test_the_window_opens_on_the_latest_report_created(tmp_path, qapp):
    """*"The default when loading the Measurement Report window is the latest
    report created."* — not on "New report…", and not on the newest file of
    the measurement the window happens to be opened on.

    **THE TWO HAVE TO DIFFER OR THIS PROVES NOTHING**, and the first version of
    this test did not make them: the window already followed the file the page
    was drawn from (`_adopt_visible_document`), which on an ordinary project is
    also the latest document, so the mutation below left it green. So the
    latest document here is about the OLDER date, written with "Show all
    measurement runs" off, and the window is opened on the NEWER one.

    MUTATION, proved to land: delete the `_open_on_the_latest_report()` call
    from `_rebuild_from_sources`.
    """
    from tests.test_a_generated_report_is_one_document import _messy_project
    from ui.dialogs.measurement_report_dialog import NEW_REPORT_KEY
    s, _fm, run, vs = _messy_project(tmp_path, dates=2)
    first = _report_window(s, vs[0].measurement_ti3, qapp)
    try:
        first._say_generated = lambda saved, failed: None
        # ONE MEASUREMENT TICKED — it used to be `_all_runs_check` OFF, which
        # is the same document said in the vocabulary that is left (B8-590).
        _only_this_measurement(first, qapp)
        first._detail_check.setChecked(True)
        qapp.processEvents()
        first._on_generate_report()
        qapp.processEvents()
        made = first._loaded_doc_id
    finally:
        first.close()
    assert made.startswith("id:"), made

    dlg = _report_window(s, vs[-1].measurement_ti3, qapp)
    try:
        assert dlg._loaded_doc_id == made, (
            f"the window opened on {dlg._loaded_doc_id!r}, not on the latest "
            f"report created ({made!r})")
        assert dlg._saved_combo.currentData() == made
        assert dlg._saved_combo.currentData() != NEW_REPORT_KEY
        assert dlg._saved_combo.currentIndex() != 0
        # …and with its settings, which is the other half of his sentence.
        assert dlg._loaded_doc is not None
        assert dlg._hidden_runs == (
            {dlg._run_key(r) for r in dlg._history}
            - {str(m.get("key") or "")
               for m in (dlg._loaded_doc.get("measurements") or [])}), (
            "the document's own measurements did not come back ticked: "
            f"hidden={dlg._hidden_runs!r}")
        assert len(dlg._runs_for_report()) == 1, (
            "the report covers more than the one measurement it was made from")
        assert dlg._detail_check.isChecked() is True
    finally:
        dlg.close()


def test_choosing_new_report_loads_the_preferences_defaults(tmp_path, qapp):
    """*"when 'Report shown' is set to 'New report....', all default values
    shall be loaded on the settings, which then can be changed by a user. The
    default values are fetched from the preferences->reports tab."*

    MUTATION, to be proved to land: make `_start_new_report` leave the tick
    boxes alone and this goes red.
    """
    from ui.dialogs.measurement_report_dialog import NEW_REPORT_KEY
    from workflow.measurement_report import REPORT_TYPE_GREY
    s, _fm, _run, vs = _generated_project(tmp_path, qapp)
    s.set("report_default_show_details", True)
    s.set("report_default_type", REPORT_TYPE_GREY)
    dlg = _report_window(s, vs[-1].measurement_ti3, qapp)
    try:
        # the window opened on a document made with the box off and a narrowed
        # list; both are moved away from the defaults before they are asked for
        _only_this_measurement(dlg, qapp)
        dlg._detail_check.setChecked(False)
        qapp.processEvents()
        dlg._saved_combo.setCurrentIndex(0)      # "New report…"
        qapp.processEvents()
        assert dlg._loaded_doc_id == NEW_REPORT_KEY
        # THE LIST IS PART OF WHAT "New report…" LOADS (B8-590). The starting
        # state that used to be "Show all measurement runs, by default: on" is
        # now simply every measurement ticked, which is what `_start_new_report`
        # clears `_hidden_runs` for.
        assert dlg._hidden_runs == set(), (
            "“New report…” kept the previous document's narrowing: "
            f"{dlg._hidden_runs!r}")
        assert dlg._detail_check.isChecked(), (
            "“Show detailed data for each run” did not come from Preferences")
        assert dlg._report_type_now() == REPORT_TYPE_GREY, (
            "the report type did not come from Preferences")
    finally:
        dlg.close()


def test_new_report_writes_nothing_and_reads_nothing_off_the_run(tmp_path,
                                                                 qapp):
    """It is a starting point, not an act. Nothing on disk moves, and the RUN
    is not told what the defaults are.

    MUTATION: write the default type onto the run in `_start_new_report` (the
    obvious way to make the pulldown agree) and this goes red.
    """
    from workflow.measurement_report import REPORT_TYPE_RECORD
    from workflow.run_compliance import run_report_type
    s, _fm, run, vs = _generated_project(tmp_path, qapp)
    s.set("report_default_type", REPORT_TYPE_RECORD)
    before_type = run_report_type(run)
    before = {str(p): p.read_bytes()
              for v in run.verifications()
              for p in (v.dir / "reports").glob("report_*.json")}
    dlg = _report_window(s, vs[-1].measurement_ti3, qapp)
    try:
        dlg._saved_combo.setCurrentIndex(0)
        qapp.processEvents()
        after = {str(p): p.read_bytes()
                 for v in run.verifications()
                 for p in (v.dir / "reports").glob("report_*.json")}
        assert set(after) == set(before), (
            f"files appeared or vanished: {sorted(set(after) ^ set(before))}")
        assert all(after[k] == before[k] for k in before), (
            "choosing “New report…” rewrote a saved report")
        assert run_report_type(run) == before_type, (
            "choosing “New report…” stored the default type on the run")
    finally:
        dlg.close()


def test_new_report_starts_on_the_preferences_type_whatever_the_run_holds(
        tmp_path, qapp):
    """K31 turned this test round (it was
    `test_the_defaults_do_not_override_a_run_that_chose_its_type`, D9).
    Knut, 5801677743: *"the starting choice for 'New report...' should be the
    defaults in preferences -> reports first"*, and the type is the report's.
    A type an earlier ChromIQ stored on the run is not a starting choice.

    MUTATION: ask the run's stored type in `_report_type_now` before the
    Preferences default and this goes red.
    """
    from workflow.measurement_report import (REPORT_TYPE_GREY,
                                             REPORT_TYPE_RECORD)
    from tests.helpers.legacy_run_meta import (set_run_report_type)
    s, _fm, run, vs = _generated_project(tmp_path, qapp, presses=0)
    from workflow.measurement_report import REPORT_TYPE_SUMMARY
    s.set("report_default_type", REPORT_TYPE_SUMMARY)
    set_run_report_type(run, REPORT_TYPE_GREY)          # an earlier ChromIQ's
    dlg = _report_window(s, vs[-1].measurement_ti3, qapp)
    try:
        dlg._saved_combo.setCurrentIndex(0)      # "New report…"
        qapp.processEvents()
        assert dlg._report_type_now() == REPORT_TYPE_SUMMARY, (
            "the run's stored type overrode the Preferences default")
    finally:
        dlg.close()


# ---------------------------------------------------------------------------
# 5. B8-392 — one measurement in the list
# ---------------------------------------------------------------------------
def test_one_measurement_needs_no_box_turned_off_for_it(tmp_path, qapp):
    """**THE RULE THIS PINNED HAS NOTHING LEFT TO ACT ON (B8-590).**

    B8-392 said: *"If the list of measurement dates to be included only holds
    one measurement, then the 'Show all measurement runs' is automatically set
    to OFF, and the report name should include the flag 'One date'."* The first
    half was a rule about a control, and this test pinned it: the box off, the
    box greyed, and a tooltip saying why, beating the Preferences default.

    Knut removed the control and the feature behind it on 2026-09-20, so there
    is no box to force off and no default to beat. The SECOND half of his
    sentence is about the report and survives untouched, so that is what is
    checked here now: one measurement in the list, that measurement ticked,
    and a report that says "One date".

    MUTATION, proved to land: build `_all_runs_check` again (the first
    assertion), or return anything but the one-member scope from
    `_document_scope` (the last).
    """
    from tests.test_a_generated_report_is_one_document import _messy_project
    s, _fm, _run, vs = _messy_project(tmp_path, dates=1)
    dlg = _report_window(s, vs[0].measurement_ti3, qapp)
    try:
        assert len(dlg._history) == 1, [r.get("created") for r in dlg._history]
        assert getattr(dlg, "_all_runs_check", None) is None, (
            "“Show all measurement runs” is still built")
        assert dlg._profile_list.isEnabled(), (
            "the one control that decides what a report covers is disabled")
        assert dlg._hidden_runs == set()
        assert len(dlg._runs_for_report()) == 1
        dlg._say_generated = lambda saved, failed: None
        dlg._saved_combo.setCurrentIndex(0)      # "New report…"
        qapp.processEvents()
        dlg._on_generate_report()
        qapp.processEvents()
        name = dlg._saved_combo.itemText(1)
        assert "One date" in name, name
    finally:
        dlg.close()


def test_the_name_carries_knuts_flags(tmp_path, qapp):
    """The three date flags and "Detailed", in the one builder that composes a
    generated report's name.

    MUTATION, to be proved to land: drop the scope clause from
    `_document_label` and this goes red.
    """
    from tests.test_a_generated_report_is_one_document import _messy_project
    s, _fm, run, vs = _messy_project(tmp_path, dates=2)
    dlg = _report_window(s, vs[-1].measurement_ti3, qapp)
    try:
        dlg._say_generated = lambda saved, failed: None
        # From "New report…", because a window that opens on a saved
        # report now comes up with that report's own measurements
        # ticked and no others (B8-490, Knut's beta-25 ruling), and
        # every report in this fixture is about one date.
        dlg._saved_combo.setCurrentIndex(0)
        qapp.processEvents()
        # "ALL DATES" IS EVERY MEASUREMENT TICKED and "One date" is one of
        # them, said through the buttons and the list: the box these two used
        # to set was removed on 2026-09-20 (B8-590), and the flag was already
        # derived from the document's own member list (B8-522), so the words
        # this checks are unchanged.
        _every_measurement(dlg, qapp)
        dlg._detail_check.setChecked(True)
        qapp.processEvents()
        dlg._on_generate_report()
        qapp.processEvents()
        all_dates = dlg._saved_combo.itemText(1)
        assert "All dates" in all_dates, all_dates
        assert "Detailed" in all_dates, all_dates

        _only_this_measurement(dlg, qapp)
        dlg._detail_check.setChecked(False)
        qapp.processEvents()
        dlg._on_generate_report()
        qapp.processEvents()
        one_date = dlg._saved_combo.itemText(1)
        assert "One date" in one_date, one_date
        assert "Detailed" not in one_date, one_date
    finally:
        dlg.close()


def test_the_flag_words_are_translated_at_display_and_not_stored(tmp_path,
                                                                 qapp):
    """**WHAT IS STORED IS STABLE; ONLY WHAT IS SHOWN IS TRANSLATED.** A report
    named on a German machine has to mean the same thing on an English one, so
    the document block keeps ids (the type id, the set id beside its ENGLISH
    label, and the scope id) and `_document_label` is the one place that turns
    them into words.

    MUTATION: store `tr("All dates")` in the block instead of the id and this
    goes red.
    """
    from workflow.measurement_report import (DOCUMENT_SCOPES, list_reports,
                                             recorded_document)
    from tests.test_a_generated_report_is_one_document import _messy_project
    s, _fm, run, vs = _messy_project(tmp_path, dates=2)
    dlg = _report_window(s, vs[-1].measurement_ti3, qapp)
    try:
        dlg._say_generated = lambda saved, failed: None
        _every_measurement(dlg, qapp)
        dlg._on_generate_report()
        qapp.processEvents()
    finally:
        dlg.close()
    # K31: a report of two dates is ONE file, in the run's
    # verifications/reports/, beside the dates' own reports.
    files = [p for v in run.verifications() for p in list_reports(v.dir)]
    files += sorted((run.verifications_dir / "reports").glob("report_*.json"))
    blocks = [recorded_document(json.loads(Path(p).read_text(encoding="utf-8")))
              for p in files]
    blocks = [b for b in blocks if b]
    assert blocks, "nothing was generated, so this proves nothing"
    for b in blocks:
        assert b.get("scope") in DOCUMENT_SCOPES, b.get("scope")
        assert b["compliance"]["set_label"] == "ChromIQ default (recommended)", (
            "the limit set's label is stored translated, so a name written in "
            "one language would not read in another")


# ---------------------------------------------------------------------------
# 6. what the new default reached, and what it found there
# ---------------------------------------------------------------------------
def test_the_detailed_section_survives_a_report_of_another_shape(tmp_path,
                                                                 qapp):
    """**FOUND BY DRIVING THE NEW DEFAULT ON SCREEN**, and it took the whole
    window down twice: `KeyError: 'hex'` and then `KeyError: 'loc'`.

    "Show detailed data for each run" starts ON now (B8-388, P.3), so the
    detailed section is drawn for every reader on open. It read
    `paper_white['hex']`, `['loc']` and `['lab'][0]`, and all four keys of every
    worst-patch entry, straight out of the record — and ChromIQ's own demo
    projects hold paper white as `{"L":…, "a":…, "b":…}` and worst patches as
    `{"id":…, "de00":…}`. A user with such a file could not open the window at
    all.

    **THE FIXTURE IS THE SHAPE THAT BROKE IT**, not a tidied version of it.

    MUTATION, proved to land: put `w['hex']` or `p['loc']` back and this goes
    red with a KeyError rather than an assertion.
    """
    from tests.test_a_generated_report_is_one_document import _messy_project
    from workflow.measurement_report import list_reports
    s, _fm, run, vs = _messy_project(tmp_path, dates=2)
    for v in run.verifications():
        for path in list_reports(v.dir):
            rep = json.loads(Path(path).read_text(encoding="utf-8"))
            rep["paper_white"] = {"L": 95.4, "a": 0.8, "b": -2.1}
            rep["max_black"] = {"L": 6.2, "a": 0.3, "b": -0.4}
            rep["worst_patches"] = [{"id": 118, "de00": 4.65},
                                    {"id": 7, "de00": 3.1}]
            rep["corners"] = [{"name": "W", "present": True, "de": 1.2}]
            Path(path).write_text(json.dumps(rep), encoding="utf-8")
    dlg = _report_window(s, vs[-1].measurement_ti3, qapp)
    try:
        dlg._detail_check.setChecked(True)
        qapp.processEvents()
        html = dlg._report_body_html(dlg._runs_for_report(), for_pdf=False)
        assert html, "the document did not render at all"
        # …and what it could print, it printed: the L* it has, and the patch
        # named by the key the file uses.
        assert "95.4" in html, "paper white's L* is in the file and not on the page"
        assert "118" in html, "the worst patch is in the file and not on the page"
    finally:
        dlg.close()


# ---------------------------------------------------------------------------
# 5. R24-F1 — the window may not say "New report…" over other settings
# ---------------------------------------------------------------------------
def _pick_the_row_the_list_is_on(combo, qapp) -> None:
    """Open the pulldown and choose the entry it is ALREADY on.

    The app's own gesture, and the only one that reaches the fault: Qt emits
    no `currentIndexChanged` for a pick that does not move the index, so a
    window whose pulldown already reads "New report…" could not be told to
    load the defaults. `activated` is what a real choice emits.
    """
    from PyQt6.QtCore import Qt
    from PyQt6.QtTest import QTest

    combo.showPopup()
    qapp.processEvents()
    view = combo.view()
    view.setCurrentIndex(view.model().index(combo.currentIndex(), 0))
    QTest.keyClick(view, Qt.Key.Key_Return)
    qapp.processEvents()


def _a_run_whose_newest_sheet_has_no_report(tmp_path):
    """A project with saved reports in it, opened on a measurement that is not
    one of their subjects -- so "Report shown" lands on "New report…".

    This is the shape round 24 photographed on ChromIQ's own `Demo-Switching`:
    the list holds saved reports, none of them names the file the page is
    drawn from, and the pulldown therefore shows the top row. Every project a
    user already has has saved reports in it, which is why this branch and not
    the empty one is where nearly every window lands.
    """
    from tests.test_a_generated_report_is_one_document import _messy_project

    s, fm, run, vs = _messy_project(tmp_path, dates=2)
    for f in (vs[-1].dir / "reports").glob("report_*.json"):
        f.unlink()
    return s, fm, run, vs


def test_a_window_that_lands_on_new_report_holds_its_defaults(tmp_path, qapp):
    """R24-F1. The pulldown said "New report…" over settings that were not
    the "New report…" defaults.

    `_open_on_the_latest_report` loaded the Preferences defaults only when the
    run had NO saved report at all; with saved reports that carry no document
    block -- which is every project made before this beta -- it returned, and
    the tick boxes kept whatever they were built with, while the list showed
    "New report…" because no document matched. Measured on screen on a fresh
    settings file: Preferences ▸ Reports said "Show detailed data for each
    run, by default" was ON and the window it governs opened with it OFF.

    MUTATION, proved to land: put `if docs: return` back in front of
    `_load_the_defaults()` in `_open_on_the_latest_report`.
    """
    from ui.dialogs.measurement_report_dialog import NEW_REPORT_KEY

    s, _fm, _run, vs = _a_run_whose_newest_sheet_has_no_report(tmp_path)
    s.set("report_default_show_details", True)
    dlg = _report_window(s, vs[-1].measurement_ti3, qapp)
    try:
        assert dlg._saved_combo.count() > 1, (
            "the fixture has no saved reports, so this is the empty case that "
            "already worked")
        assert not any(d.get("doc") for d in
                       dlg._saved_documents(dlg._run_ctx.run
                                            if dlg._run_ctx else None)), (
            "a saved DOCUMENT exists here, so the window opens on it and this "
            "is not the branch the fault lives in")
        assert dlg._detail_check.isChecked(), (
            "“Show detailed data for each run” did not come from Preferences: "
            "the window opened on a run with saved reports, so the defaults "
            "never reached it")
        # The other box this used to check went with the feature behind it
        # (B8-590); what a "New report…" state means for the LIST is every
        # measurement ticked, and that is asserted here in its place.
        assert dlg._hidden_runs == set(), dlg._hidden_runs
        # …and the pulldown's claim and the window's state are the same thing
        assert dlg._loaded_doc_id == NEW_REPORT_KEY
        assert dlg._saved_combo.currentData() == NEW_REPORT_KEY, (
            "the window is in the “New report…” state and the list says "
            "something else")
    finally:
        dlg.close()


def test_that_opening_state_is_preferences_and_not_a_constant(tmp_path, qapp):
    """The other direction, which is what makes the test above mean something:
    with the Preferences defaults OFF the same window opens with both off."""
    s, _fm, _run, vs = _a_run_whose_newest_sheet_has_no_report(tmp_path)
    s.set("report_default_show_details", False)
    dlg = _report_window(s, vs[-1].measurement_ti3, qapp)
    try:
        assert not dlg._detail_check.isChecked(), (
            "the detail box is on with the Preferences default off")
    finally:
        dlg.close()


def test_the_tick_box_is_built_from_the_preferences_default(tmp_path, qapp):
    """One question, one answer. It was built from `report_show_details` (and,
    while it existed, `report_show_all_runs`) — the last-used values — so a
    window that never reached `_defaults_document()` at all showed a third
    state.

    It was a pair until B8-590 took the other box away; the remaining half is
    the whole of the rule now, and the dead last-used key is left in the
    settings file below to prove nothing reads it any more.

    MUTATION: read `report_show_details` again in `__init__` and this goes red.
    """
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog

    s = _settings(tmp_path, report_default_show_details=True,
                  report_show_all_runs="false", report_show_details="false")
    dlg = MeasurementReportDialog(s, None)
    try:
        assert getattr(dlg, "_all_runs_check", None) is None
        assert dlg._detail_check.isChecked(), (
            "the box was built from the last-used value, not from Preferences")
    finally:
        dlg.close()


def test_picking_new_report_again_still_loads_the_defaults(tmp_path, qapp):
    """R24-F1's other half: the user cannot correct it by hand either.

    Choosing "New report…" while the pulldown already reads "New report…"
    emits no `currentIndexChanged`, so `_start_new_report` never ran and the
    one control that loads the defaults did nothing at all. Driven the way a
    user does it: open the list, pick the row it is on.

    MUTATION, proved to land: drop the `activated` connection.
    """
    from ui.dialogs.measurement_report_dialog import NEW_REPORT_KEY

    s, _fm, _run, vs = _a_run_whose_newest_sheet_has_no_report(tmp_path)
    s.set("report_default_show_details", True)
    dlg = _report_window(s, vs[-1].measurement_ti3, qapp)
    try:
        assert dlg._saved_combo.currentData() == NEW_REPORT_KEY
        # the user has since changed both, and now wants the defaults back.
        # "Both" is the detail box and the LIST since B8-590: the second box
        # is gone and the ticks are what a report covers.
        _only_this_measurement(dlg, qapp)
        dlg._detail_check.setChecked(False)
        qapp.processEvents()
        assert dlg._saved_combo.currentIndex() == 0, (
            "the list moved off “New report…”, so re-picking it would move "
            "the index and this proves nothing")

        _pick_the_row_the_list_is_on(dlg._saved_combo, qapp)

        assert dlg._hidden_runs == set(), (
            "choosing “New report…” did nothing, because it was already the "
            f"current entry: {dlg._hidden_runs!r}")
        assert dlg._detail_check.isChecked(), (
            "choosing “New report…” did nothing, because it was already the "
            "current entry")
    finally:
        dlg.close()



def test_a_printing_record_default_is_refused_for_a_verification(tmp_path, qapp):
    """K13 (Knut, beta 34): a verification is never a Printing record. A
    Preferences default of Printing record, legal until beta 35, is refused
    at read time for the automatic report of a verification measurement, and
    the Preferences pulldown no longer offers it.

    MUTATION: drop `and tid in allowed` from `report_type_default_for` and the
    first assert goes red; drop the T4 disable in the Preferences builder and
    the second does.
    """
    from workflow.measurement_report import (REPORT_TYPE_FULL,
                                             REPORT_TYPE_RECORD, list_reports,
                                             recorded_document)
    s, _fm, _ctl, _run, v = _a_measured_run(tmp_path)
    s.set("report_default_type", REPORT_TYPE_RECORD)
    tab = _measure_tab(s, qapp)
    try:
        tab._maybe_save_measurement_report(v.measurement_ti3)
        doc = recorded_document(json.loads(
            Path(list_reports(v.dir)[-1]).read_text(encoding="utf-8")))
        assert doc["type"] == REPORT_TYPE_FULL, doc["type"]
    finally:
        tab.deleteLater()
    d = _prefs(s, qapp)
    try:
        combo = d._report_type_default_combo
        i = combo.findData(REPORT_TYPE_RECORD)
        assert i >= 0 and not combo.model().item(i).isEnabled(), (
            "Preferences still offers Printing record as the default type")
        assert combo.currentData() != REPORT_TYPE_RECORD
    finally:
        d.deleteLater()
