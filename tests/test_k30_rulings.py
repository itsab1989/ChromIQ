"""#182 K30: Knut's rulings of 5798461562 (2026-09-23) and the challenge
round B / A findings fixed with them (spec section 24,
`docs/design/measurement_report_limits.md`).

* A loaded report can always be generated again, and Generate asks
  Update / Create New / Cancel; an Update renames the report.
* Limits belong to the report: with several places loaded, the limits window
  edits the REPORT's own limits, no run's.
* Projects that are not side by side share the ChromIQ folder's reports/.
* A lone project carries its heading in "Report shown".
* The report's words are true of several runs and projects, of a
  calibration, and of what a row really judges.

Every test names the mutation that turns it red in its docstring.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest                                                  # noqa: E402
from PyQt6.QtWidgets import QApplication                       # noqa: E402

from tests.test_calibration_reports import (                   # noqa: E402
    _headings, _project_with_cal, _rows, _save, _settings, _window)
from tests.test_g7_reports_across_places import (              # noqa: E402
    _new_report_of_everything, _press, _project, _read, _reports)


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture(autouse=True)
def _quiet(monkeypatch):
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    monkeypatch.setattr(MeasurementReportDialog, "_ask_update_or_create_new",
                        lambda self: "new")
    monkeypatch.setattr(MeasurementReportDialog, "_confirm",
                        lambda self, *a, **k: True)
    monkeypatch.setattr(MeasurementReportDialog, "_say_generated",
                        lambda self, saved, failed: None)


def _two_runs(tmp_path):
    """Project P with run1 (ChromIQ default) and run2 (ChromIQ tight), one
    dated verification each. Returns (project, run1, v1, run2, v2)."""
    from tests.test_g7_reports_across_places import _date
    from workflow.run_compliance import bind_run
    proj, run1, v1 = _project(tmp_path, "P", "chromiq_default")
    run2 = proj.new_run()
    run2.ensure_dir()
    bind_run(run2, "chromiq_tight", None)
    v2 = _date(run2, 0.5)
    return proj, run1, v1, run2, v2


def _edit_in_the_limits_window(monkeypatch, row="all_de00_avg", value=0.4,
                               pick=""):
    """Drive the REAL ThresholdsDialog: type one number into its first
    column (or pick a set in its radio row) and close it, as a user does."""
    import ui.dialogs.thresholds_dialog as td
    from workflow.compliance_sets import Limit
    seen = {}

    def _exec(self):
        seen["dialog"] = self
        seen["header"] = self._header_text(td.RUN_COLUMN)
        if pick:
            self.run_set_chosen = pick
        else:
            self._run_limits[row] = Limit.value(value)
            self._run_dirty = True
        self.done(0)
        return 0

    monkeypatch.setattr(td.ThresholdsDialog, "exec", _exec)
    return seen


# --------------------------------------------------------------------------
# A3: the limits of a report across places are the report's own
# --------------------------------------------------------------------------
def test_across_places_the_limits_window_edits_the_reports_own_limits(
        tmp_path, qapp, monkeypatch):
    """Knut, 5798461562: *"Why is editing limits is per run? I have not
    specified this. I have specified the opposite that all settings belong
    to a report"*. With two runs loaded the limits button is live, its first
    column is "This report", a number typed there marks the report changed
    (the red line), no run's meta moves, and Generate writes the report
    judged against the edited number.

    MUTATION, proven red: `self._limits_btn.setEnabled(not several)` back
    in `_sync_limit_controls` (the button is greyed), or drop the
    `_report_own_limits` branch at the head of `_sticky_limits` (the
    document is written with the set's own number, 2.0)."""
    from workflow.measurement_report import recorded_document
    proj, run1, v1, run2, v2 = _two_runs(tmp_path)
    metas = [(r.dir / "meta.json").read_bytes() for r in (run1, run2)]
    seen = _edit_in_the_limits_window(monkeypatch, value=0.4)
    dlg = _window(_settings(), v1.measurement_ti3, qapp, "verification")
    try:
        dlg._add_source(v2.measurement_ti3)
        qapp.processEvents()
        _new_report_of_everything(dlg, qapp)
        assert dlg._limits_btn.isEnabled(), dlg._limits_btn.toolTip()
        assert dlg._limits_btn.text() == "Edit limits…"
        dlg._on_open_limits()
        qapp.processEvents()
        assert seen["header"] == "This report"
        assert dlg._settings_were_modified(), "the red line did not come up"
        _press(dlg, qapp)
    finally:
        dlg.close()
    assert [(r.dir / "meta.json").read_bytes() for r in (run1, run2)] == metas
    docs = _reports(Path(proj.root) / "reports")
    assert len(docs) == 1, docs
    comp = recorded_document(_read(docs[0]))["compliance"]
    assert comp["thresholds"]["all_de00_avg"] == pytest.approx(0.4), comp
    assert comp.get("edited") is True, comp


def test_one_run_loaded_the_limits_window_is_still_the_runs(
        tmp_path, qapp, monkeypatch):
    """With ONE place loaded, the limits window is the run's, as spec
    section 5 and the confirmed 19.6 / 19.13 have it: "This run", and the
    report window keeps no report-own limits.

    MUTATION, proven red: call `_open_report_limits_window` unconditionally
    in `_open_limits_window` (the header reads "This report")."""
    from tests.test_g7_reports_across_places import _date  # noqa: F401
    proj, run1, v1 = _project(tmp_path, "P", "chromiq_default")
    seen = _edit_in_the_limits_window(monkeypatch, value=0.4)
    dlg = _window(_settings(), v1.measurement_ti3, qapp, "verification")
    try:
        dlg._on_open_limits()
        qapp.processEvents()
        assert seen["header"] == "This run"
        assert getattr(dlg, "_report_own_limits", None) is None
    finally:
        dlg.close()


def test_a_set_picked_for_the_report_in_the_limits_window(
        tmp_path, qapp, monkeypatch):
    """The "Used for this report" radio chooses the report's set: the
    pulldown follows it and no run is re-bound.

    MUTATION, proven red: ignore `run_set_chosen` in
    `_open_report_limits_window` (the pulldown stays on the old set)."""
    from workflow.run_compliance import run_limits
    proj, run1, v1, run2, v2 = _two_runs(tmp_path)
    bound = (run_limits(run1, None).set_id, run_limits(run2, None).set_id)
    _edit_in_the_limits_window(monkeypatch, pick="chromiq_quick")
    dlg = _window(_settings(), v1.measurement_ti3, qapp, "verification")
    try:
        dlg._add_source(v2.measurement_ti3)
        qapp.processEvents()
        _new_report_of_everything(dlg, qapp)
        dlg._on_open_limits()
        qapp.processEvents()
        assert dlg._set_combo.currentData() == "chromiq_quick"
        assert dlg._settings_were_modified()
    finally:
        dlg.close()
    assert (run_limits(run1, None).set_id,
            run_limits(run2, None).set_id) == bound


# --------------------------------------------------------------------------
# F5: a calibration whose measurement was moved still lists its reports
# --------------------------------------------------------------------------
def test_a_calibration_with_no_measurement_lists_its_saved_reports(
        tmp_path, qapp):
    """Challenge A F5: `cal/<name>-cal.ti3` moved aside (a new chart), its
    `cal/reports/` still full. The window lists and opens them, Generate is
    greyed with the reason, and "Unlock this run's limits" is not live.

    MUTATION, proven red: drop `_a_calibration_with_saved_reports` from the
    `__init__` load condition (the window opens empty, nothing listed)."""
    proj, ti3 = _project_with_cal(tmp_path, "P")
    _save([ti3.parent], [ti3])
    ti3.rename(ti3.with_suffix(".moved"))
    dlg = _window(_settings(), ti3, qapp, "calibration")
    try:
        assert [t for t, k in _rows(dlg) if k is not None], _rows(dlg)
        assert not dlg._generate_btn.isEnabled()
        assert "has not been measured" in dlg._generate_btn.toolTip()
        assert not dlg._unlock_check.isEnabled()
    finally:
        dlg.close()


def test_an_empty_window_offers_no_unlock(qapp):
    """Challenge A F5, the other half: a window opened on nothing keeps no
    live "Unlock this run's limits".

    MUTATION, proven red: drop the `if not self._sources:` block at the end
    of `__init__` (the box is live)."""
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    dlg = MeasurementReportDialog(_settings(), None, initial_ti3=None)
    try:
        assert not dlg._unlock_check.isEnabled()
    finally:
        dlg.deleteLater()


# --------------------------------------------------------------------------
# A5: a lone project carries its heading in a Calibration window
# --------------------------------------------------------------------------
def test_a_lone_project_carries_its_heading_under_calibration(tmp_path,
                                                                qapp):
    """Spec 18.12 asked *"say if a lone project should carry its heading
    too"*; Knut, 5798461562: *"ok"*. One project's calibration in the list,
    no report of another project offered: its reports sit under a heading
    naming the project. A Verification window on one run keeps no heading.

    MUTATION, proven red: drop the `kind == KIND_CALIBRATION` branch in
    `_grouped_documents` (the list is flat)."""
    p, ti3 = _project_with_cal(tmp_path, "P")
    _save([p.calibration.dir], [ti3])
    dlg = _window(_settings(), ti3, qapp, "calibration")
    try:
        assert _headings(dlg) == ["P"], _rows(dlg)
        assert dlg._saved_label.text() == "Report shown:"
    finally:
        dlg.close()
    proj, run1, v1 = _project(tmp_path / "v", "V")
    dlg = _window(_settings(), v1.measurement_ti3, qapp, "verification")
    try:
        assert _headings(dlg) == [], _rows(dlg)
    finally:
        dlg.close()


# --------------------------------------------------------------------------
# A6: a "–" row leaves the Printing record too
# --------------------------------------------------------------------------
def test_a_dash_row_leaves_the_printing_record(tmp_path, qapp):
    """Knut, 5798461562: *"Yes, all report types. It was a general rule."*
    A row whose limit is "–" is in neither the Report Results, the guide,
    the detailed table nor the Overview of a Printing record.

    MUTATION, proven red: make `_drop_dash_rows` return its rows unchanged
    (the row comes back on the record)."""
    import html as _html
    import re
    from tests.test_k28b_one_vocabulary import _limits_with_dash, _open
    from workflow.measurement_report import REPORT_TYPE_RECORD
    dlg = _open(tmp_path, qapp, _limits_with_dash("worst5_de00_avg"))
    try:
        dlg._report_type_now = lambda: REPORT_TYPE_RECORD
        dlg._detail_check.setChecked(True)
        runs = dlg._runs_for_report()
        assert dlg._ungraded_by_type()
        body = _html.unescape(re.sub(r"<[^>]+>", " ", dlg._report_body_html(
            runs, for_pdf=True)))
        assert "Average ΔE00, highest 5 %" not in body
        assert "Average ΔE00, lowest 95 %" in body
    finally:
        dlg.deleteLater()


# --------------------------------------------------------------------------
# A1 / A2: every loaded report can be generated again; Update renames it
# --------------------------------------------------------------------------
def test_the_report_a_window_opens_on_can_be_updated_and_is_renamed(
        tmp_path, qapp, monkeypatch):
    """Knut, 5798461562: *"The reports settings are loaded, and the user
    should be able to modify the settings and select Generate Report, which
    then gives a popup window where user can choose to update selected
    report or create a new report, or cancel. This is the standard behaviour
    ... also those loading when report window is opened."* And: *"If update
    is chosen, then name of the report is updated too, according to the
    settings"*.

    A Calibration window opens on its newest report, "All cals" across
    three projects. Generate is live over it, a press asks the question,
    and Update after unticking one project keeps the report (its id) and
    renames it "Multiple cals".

    MUTATION, proven red: return None from `_document_being_updated` (no
    question: a second report is written), or compute the scope from the
    OLD document in `_write_the_document` (the name stays "All cals")."""
    from PyQt6.QtCore import Qt
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    from workflow.measurement_report import SCOPE_ALL_DATES
    p, pti3 = _project_with_cal(tmp_path, "P")
    q, qti3 = _project_with_cal(tmp_path, "Q")
    r, rti3 = _project_with_cal(tmp_path, "R")
    _save([p.calibration.dir], [pti3])
    _save([p.calibration.dir, q.calibration.dir, r.calibration.dir],
          [pti3, qti3, rti3], scope=SCOPE_ALL_DATES)
    asked = []

    def _ask(self):
        asked.append(self._loaded_doc_id)
        return "update"
    monkeypatch.setattr(MeasurementReportDialog, "_ask_update_or_create_new",
                        _ask)
    dlg = _window(_settings(), pti3, qapp, "calibration")
    try:
        opened = dlg._loaded_doc_id
        assert dlg._saved_combo.currentText().endswith(" · All cals"), \
            dlg._saved_combo.currentText()
        assert dlg._generate_btn.isEnabled(), dlg._generate_btn.toolTip()
        lst = dlg._profile_list
        r_dir = str(r.calibration.dir)
        for i in range(lst.count()):
            it = lst.item(i)
            if not it.flags() & Qt.ItemFlag.ItemIsUserCheckable:
                continue
            it.setCheckState(Qt.CheckState.Unchecked)
            qapp.processEvents()
            if r_dir not in {x.get("_origin_dir")
                             for x in dlg._runs_for_document()}:
                break
            it.setCheckState(Qt.CheckState.Checked)
            qapp.processEvents()
        assert len(dlg._runs_for_document()) == 2, [
            x.get("_origin_dir") for x in dlg._runs_for_document()]
        _press(dlg, qapp)
        assert asked == [opened], asked
        assert dlg._loaded_doc_id == opened
        assert " · Multiple cals · updated " in \
            dlg._saved_combo.currentText(), dlg._saved_combo.currentText()
    finally:
        dlg.close()


# --------------------------------------------------------------------------
# F4 / F3: the Calibration window's own sentences
# --------------------------------------------------------------------------
def test_a_run_measurement_beside_the_calibration_gets_the_true_reason(
        tmp_path, qapp):
    """Challenge A F4: the window's OWN calibration ticked, plus a run's
    verification added: Generate stays refused (a Calibration report covers
    calibrations only) and says so, not "Every ticked measurement belongs to
    another profile run".

    MUTATION, proven red: drop the `calibration and _doc_runs and not
    all(is_calibration_dir(...))` sentence in `_sync_type_combo` (the false
    one comes back)."""
    p, pti3 = _project_with_cal(tmp_path, "P")
    proj, run1, v1 = _project(tmp_path / "v", "V")
    dlg = _window(_settings(), pti3, qapp, "calibration")
    try:
        dlg._add_source(v1.measurement_ti3)
        qapp.processEvents()
        _new_report_of_everything(dlg, qapp)
        assert not dlg._generate_btn.isEnabled()
        tip = dlg._generate_btn.toolTip()
        assert "covers calibrations only" in tip, tip
        assert "Every ticked measurement" not in tip, tip
    finally:
        dlg.close()


def test_a_calibration_window_never_says_runs_were_set_to_types(tmp_path,
                                                                qapp):
    """Challenge A F3: three projects' calibrations, their saved reports of
    different types. A calibration stores no type and is not a run, so the
    line under "Report shown" must not say "The runs loaded here were set
    to different report types".

    MUTATION, proven red: drop the calibration skip in
    `_types_of_loaded_runs` (the saved reports' types disagree, and the
    sentence comes back)."""
    from workflow.measurement_report import (REPORT_TYPE_FULL,
                                             REPORT_TYPE_GREY)
    p, pti3 = _project_with_cal(tmp_path, "P")
    q, qti3 = _project_with_cal(tmp_path, "Q")
    _save([p.calibration.dir], [pti3], type_id=REPORT_TYPE_FULL)
    _save([q.calibration.dir], [qti3], type_id=REPORT_TYPE_GREY)
    dlg = _window(_settings(), pti3, qapp, "calibration")
    try:
        dlg._add_source(qti3)
        qapp.processEvents()
        assert "different report types" not in dlg._type_blurb_full, \
            dlg._type_blurb_full
        assert dlg._types_of_loaded_runs() == set()
    finally:
        dlg.close()


# --------------------------------------------------------------------------
# F6: the orange strip names every row the page cannot answer
# --------------------------------------------------------------------------
def test_the_strip_names_rows_of_every_sheet_on_the_page(tmp_path, qapp):
    """Challenge A F6: with several dates ticked, the strip named the
    evenness rows of the window's own sheet and not the grey rows another
    ticked sheet reads N-A. It names every such row now.

    MUTATION, proven red: take `_pages = [r]` in `_mismatch_text` (only
    the subject sheet is read, the grey row is missing)."""
    from workflow.compliance_sets import N_A, ROW_BY_ID
    from workflow.measurement_report import REASON_GREY_STEPS_BUNCHED
    proj, run1, v1, run2, v2 = _two_runs(tmp_path)
    dlg = _window(_settings(), v1.measurement_ti3, qapp, "verification")
    try:
        dlg._add_source(v2.measurement_ti3)
        qapp.processEvents()
        _new_report_of_everything(dlg, qapp)
        subject = dlg._report
        grey = "grey_balance_neutral_ramp_avg"

        def _rows_of(r):
            if r is subject:
                return ([], False)
            return ([{"row_id": grey, "word": N_A,
                      "reason": REASON_GREY_STEPS_BUNCHED}], False)
        dlg._verdict_rows = _rows_of
        text = dlg._mismatch_text()
        assert ROW_BY_ID[grey].label in text, text
    finally:
        dlg.close()


# --------------------------------------------------------------------------
# B1 / B8: the words of a report across runs
# --------------------------------------------------------------------------
def test_a_report_across_runs_names_every_run_it_judges(tmp_path, qapp):
    """Challenge B B1 and B8: across run 1 and run 2 the report said "This
    report judges the profile built in P, run 1", and Report Scope listed
    "P-verify · 2 verification runs" with no run named. Both name each run.

    MUTATION, proven red: return `places[:1]` from `_places_of` (the
    sentence names run 1 only, the Scope groups both dates under one)."""
    import html as _html
    import re
    proj, run1, v1, run2, v2 = _two_runs(tmp_path)
    dlg = _window(_settings(), v1.measurement_ti3, qapp, "verification")
    try:
        dlg._add_source(v2.measurement_ti3)
        qapp.processEvents()
        _new_report_of_everything(dlg, qapp)
        runs = dlg._runs_for_document()
        said = dlg._what_this_report_judges(runs)
        assert "P, run 1; P, run 2" in said, said
        scope = _html.unescape(re.sub(r"<[^>]+>", " ", dlg._scope_html(runs)))
        assert "P, run 1" in scope and "P, run 2" in scope, scope
    finally:
        dlg.close()


# --------------------------------------------------------------------------
# B2 / B10: a calibration's report says it is one
# --------------------------------------------------------------------------
def test_a_calibration_report_has_its_own_title_and_scope(tmp_path, qapp):
    """Challenge B B2: a calibration report was titled "Measurement Report -
    Profiling of Printer"; B10: its Scope said "The following profiles'
    measurement runs are included: ...-cal · 1 run".

    MUTATION, proven red: drop the calibration branch of `_report_kind`
    (the profiling title and scope come back)."""
    import html as _html
    import re
    p, ti3 = _project_with_cal(tmp_path, "P")
    dlg = _window(_settings(), ti3, qapp, "calibration")
    try:
        runs = dlg._runs_for_document()
        assert dlg._report_title(runs).startswith(
            "Measurement Report - Calibration of Printer"), \
            dlg._report_title(runs)
        scope = _html.unescape(re.sub(r"<[^>]+>", " ", dlg._scope_html(runs)))
        assert "The following calibration measurements are included:" in scope
        assert "P, calibration" in scope and "1 measurement" in scope, scope
        assert "measurement runs are included" not in scope
    finally:
        dlg.close()


# --------------------------------------------------------------------------
# B3 / B7 / B4 / B9: the report's own words and layout
# --------------------------------------------------------------------------
def test_the_guide_says_within_gamut_only_where_a_row_uses_it():
    """Challenge B B3 (spec 22.1): "the verdict words judge the within-gamut
    figures" stood in How to read on every report. It is said only where a
    row shown is fed by the split; B7 (spec 19.1): "Compare a profile with
    itself over time" addressed the reader.

    MUTATION, proven red: print the within-gamut sentence unconditionally
    in `_how_to_read_html`."""
    from types import SimpleNamespace
    import ui.dialogs.measurement_report_dialog as mrd
    fake = SimpleNamespace(_ungraded_by_type=lambda: False)
    grey = mrd.MeasurementReportDialog._how_to_read_html(
        fake, ["grey_balance_neutral_ramp_avg"])
    full = mrd.MeasurementReportDialog._how_to_read_html(
        fake, ["all_de00_avg", "grey_balance_neutral_ramp_avg"])
    s = "judge the within-gamut"
    assert s not in grey and s in full
    for text in (grey, full):
        assert "Compare a profile with itself" not in text
        assert "These figures show how one profile holds up over time" in text


def test_grey_rows_sit_under_all_patches_on_a_split_sheet(tmp_path, qapp):
    """Challenge B B3: a Grey and tone check put the grey-balance value in
    the "Within gamut" column of a sheet split by the profile's gamut, and
    said "The Result judges the within-gamut figures" under it.

    MUTATION, proven red: drop the `rid not in WITHIN_GAMUT_ROWS` branch in
    `_run_detail_html` (the value moves back under "Within gamut")."""
    import re
    from tests.test_k28b_one_vocabulary import _open
    from workflow.compliance_sets import effective_limits
    from workflow.measurement_report import REPORT_TYPE_GREY
    dlg = _open(tmp_path, qapp, effective_limits("chromiq_default", {}))
    try:
        dlg._report_type_now = lambda: REPORT_TYPE_GREY
        r = dict(dlg._runs_for_report()[-1])
        r["gamut_split"] = r.get("gamut_split") or {
            "de00_in": {}, "de00_out": {}, "n_in": 10, "n_out": 2,
            "profile": "x.icc"}
        body = dlg._run_detail_html(r, None)
        row = re.search(r"Grey balance of the grey ramp, average</td>(.*?)</tr>",
                        body, re.S)
        assert row, body[:400]
        cells = re.findall(r"<td align='right'>(.*?)</td>", row.group(1))
        assert cells[0] == "—" and cells[1] == "—" and "<b>" in cells[2], cells
        assert "The Result judges the within-gamut" not in body
    finally:
        dlg.deleteLater()


def test_a_printing_record_draws_no_limit_line(tmp_path, qapp):
    """Challenge B B4 (spec 17 item 4): the record's Colour accuracy graph
    drew Avg and Max lines labelled "the limit for ...".

    MUTATION, proven red: take `_no_lines = False` in `_trend_plan`."""
    from tests.test_k28b_one_vocabulary import _open
    from workflow.compliance_sets import effective_limits
    from workflow.measurement_report import REPORT_TYPE_RECORD
    dlg = _open(tmp_path, qapp, effective_limits("chromiq_default", {}))
    try:
        dlg._report_type_now = lambda: REPORT_TYPE_RECORD
        plan = dlg._trend_plan()
        de = next(e for e in plan if e[0] is dlg._trend_de)
        assert de[6] is None, de[6]
        assert dlg._trend_extras(dlg._trend_de)["line_notes"] == []
    finally:
        dlg.deleteLater()


def test_the_report_text_explains_no_chromiq_control():
    """Challenge B B7 (spec 19.1, K18): "create this report again while
    enabling the checkbox" and "this run's current limits do not change it"
    explained ChromIQ to a report's reader.

    MUTATION, proven red: put either old sentence back in the source."""
    import inspect
    import ui.dialogs.measurement_report_dialog as mrd
    src = inspect.getsource(mrd)
    for old in ("while enabling the checkbox",
                "this run's current limits do not",
                "Compare a profile with itself over time"):
        assert old not in src, old


def test_worst_patches_heading_travels_with_its_table():
    """Challenge B B9: "Worst patches" was left alone at a page foot. The
    heading is the first row of a table that may not break.

    MUTATION, proven red: put `parts.append(_h3(tr("Worst patches")))` back
    (the heading is a paragraph of its own again)."""
    import inspect
    import ui.dialogs.measurement_report_dialog as mrd
    src = inspect.getsource(mrd.MeasurementReportDialog._run_detail_html)
    assert 'parts.append(_h3(tr("Worst patches")))' not in src
    i = src.index('html.escape(tr("Worst patches"))')
    tail = src[i:i + 2500]
    assert "page-break-inside:avoid" in tail


# --------------------------------------------------------------------------
# B6 / B11: the German words
# --------------------------------------------------------------------------
def test_the_german_report_limits_intro_is_german_and_true():
    """Challenge B B6: the Report limits intro was English in de.json and
    spoke of "two buttons below" where "Reference values…" is one.

    MUTATION, proven red: restore the old English key (its value English)."""
    import json
    from pathlib import Path
    de = json.loads((Path(__file__).resolve().parent.parent / "data" / "i18n"
                     / "de.json").read_text(encoding="utf-8"))
    # B8-910: the sentence no longer says "still being decided".
    k = next(k for k in de if k.startswith("Neither ISO value set can be chosen here"))
    assert "two buttons" not in k and "Reference values…" in k
    assert de[k] != k and "Referenzwerte…" in de[k]


def test_the_german_report_uses_one_word_each():
    """Challenge B B11: the Measurement Report's German texts used Testform
    beside Testchart, Sollwert beside Zielwert, and "So liest du" addressed
    the reader. One term each: Testchart, Zielwert, Anmerkung for a numbered
    note, "innerhalb des Profil-Gamuts".

    MUTATION, proven red: put "Sollwerten" back into one report text."""
    import ast
    import json
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent
    de = json.loads((root / "data/i18n/de.json").read_text(encoding="utf-8"))
    keys = set()
    for f in ("ui/dialogs/measurement_report_dialog.py",
              "workflow/compliance_sets.py", "workflow/measurement_report.py"):
        for n in ast.walk(ast.parse((root / f).read_text(encoding="utf-8"))):
            if (isinstance(n, ast.Call) and getattr(n.func, "id", "") == "tr"
                    and n.args and isinstance(n.args[0], ast.Constant)):
                keys.add(n.args[0].value)
            if f.endswith("compliance_sets.py") and isinstance(n, ast.Constant) \
                    and isinstance(n.value, str):
                keys.add(n.value)
    vals = [de[k] for k in keys if isinstance(de.get(k), str)]
    for bad in ("Testform", "Sollwert", "So liest du", "im Farbumfang des Profils",
                "im Gamut des Profils", "Der Hinweis unten"):
        hits = [v for v in vals if bad in v]
        assert not hits, (bad, hits[:2])
