"""#182 K26 (Knut, 2026-09-23, comments 5792484060 and 5792576954).

* Run type Calibration: the Measurement Report window opens EMPTY, every
  selection field locked, and a red line where "Already generated…" stands.
* The Colour accuracy graph plots the figures the verdict judged: within the
  profile's gamut where the sheet was split by it.
* A project opened from a folder not named what its files carry is offered
  the existing rename chooser.
* The evenness demo's noisy date takes the paper as its paper white.
* Profiling windows name their reports Run1, Run2, … / Multiple runs / All
  runs, and say "Already generated for these measurements".
* "Report shown" is grouped from the start when a report it offers covers
  more than one profile run.
* ``<output folder>/reports/`` appears only with the first report across
  projects.

(The red x and the limit words are in `test_trend_graphs_explain_themselves`,
"Bound, and locked" in `test_report_window_limit_controls`.)

Every test names the mutation that turns it red; each was run.
"""
from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest                                                  # noqa: E402
from PyQt6.QtWidgets import QApplication, QWidget              # noqa: E402

ROOT = Path(__file__).resolve().parents[1]

from tests.test_report_shown_is_grouped_by_run_and_project import (  # noqa: E402,E501
    _dialog, _headings, _profiling_project, _rows, _save_doc,
    _second_project, _two_runs)


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture(autouse=True)
def _quiet(monkeypatch):
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    monkeypatch.setattr(MeasurementReportDialog, "_ask_update_or_create_new",
                        lambda self: "new")


def _bar(run_type: str) -> QWidget:
    """A parent with a profile bar whose Run type is *run_type*, the way
    the main window and the Measure tab carry `_target_ctl`."""
    w = QWidget()
    w._target_ctl = SimpleNamespace(target=SimpleNamespace(run_type=run_type))
    return w


# --------------------------------------------------------------------------
# 1. Run type Calibration
# --------------------------------------------------------------------------
def test_a_calibration_window_opens_empty_and_locked(tmp_path, qapp):
    """Knut, Q1: *"Run type= Calibration should not allow any reports, and
    the measurement report window should have disabled/locked selection
    fields ... should not load any text or reports and open as empty."*

    Handed a real measurement (every door hands one in), the window loads
    nothing, draws no text, and every selection field and report button is
    disabled, and stays so after it is shown and resized. The red line says
    Profiling or Verification; "Already generated" is not shown.

    MUTATION, proven red: drop the `_is_calibration_window()` branch in
    `__init__` (the measurement is loaded, the list fills, Generate is live).
    """
    from core.measurement_target import RUN_TYPE_CALIBRATION
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    s, _fm, run1, _run2, v1, _v2 = _two_runs(tmp_path)
    parent = _bar(RUN_TYPE_CALIBRATION)
    dlg = MeasurementReportDialog(s, parent,
                                  initial_ti3=v1[-1].measurement_ti3)
    try:
        dlg.show()
        dlg.resize(1200, 900)
        qapp.processEvents()
        assert dlg._sources == [] and dlg._history == []
        assert dlg._profile_list.count() == 0
        assert dlg._saved_combo.count() == 0
        assert dlg._view.toPlainText().strip() == ""
        assert not dlg._trend_tabs.isVisible()
        locked = dlg._calibration_controls()
        assert len(locked) == 16
        for w in locked:
            assert not w.isEnabled(), w.objectName() or type(w).__name__
        note = dlg._calibration_note
        assert note.isVisible()
        assert note.text() == ("Measurement reports can only be made with "
                               "Run type Profiling or Verification")
        assert "color: #" in note.styleSheet()
        assert not dlg._type_blurb.isVisible()
        # a later programmatic load is refused as well
        dlg._load(v1[0].measurement_ti3)
        assert dlg._sources == []
    finally:
        dlg.close()
        parent.deleteLater()


@pytest.mark.parametrize("run_type", ["profiling", "verification"])
def test_the_other_run_types_are_untouched(tmp_path, qapp, run_type):
    """The control: under Profiling or Verification the same door loads the
    measurement and no red line exists.

    MUTATION, proven red: make `_is_calibration_window` return True always
    (both windows open empty)."""
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    s, _fm, run1, _run2, v1, _v2 = _two_runs(tmp_path)
    parent = _bar(run_type)
    dlg = MeasurementReportDialog(s, parent,
                                  initial_ti3=v1[-1].measurement_ti3)
    try:
        assert dlg._sources, "the measurement was not loaded"
        assert getattr(dlg, "_calibration_note", None) is None
    finally:
        dlg.close()
        parent.deleteLater()


def test_every_door_hands_the_window_a_parent_that_knows_the_run_type():
    """The rule lives in the window, so it holds for every door only if every
    door gives the window a parent the bar can be found from: the Tools menu
    passes the main window, the Measure tab passes itself; both carry
    `_target_ctl`.

    MUTATION, proven red: construct the dialog with ``None`` as parent in
    `tab_measure.py`'s report button (a window with no bar behind it cannot
    know it is a calibration)."""
    import re
    measure = (ROOT / "ui" / "tabs" / "tab_measure.py").read_text(
        encoding="utf-8")
    calls = re.findall(r"MeasurementReportDialog\(([^,()]+),\s*([^,()]+)[,)]",
                       measure)
    assert len(calls) >= 5, calls
    assert all(parent.strip() == "self" for _s, parent in calls), calls
    assert "self._target_ctl" in measure
    tools = (ROOT / "ui" / "dialogs" / "tools_dialogs.py").read_text(
        encoding="utf-8")
    assert re.search(r"MeasurementReportDialog\(settings, parent,", tools)


def test_the_type_help_no_longer_promises_a_calibration_every_type():
    """The Report type help said *"A measurement outside any project, or a
    calibration, can have any type ChromIQ can produce"*; under K26 a
    calibration has none.

    MUTATION, proven red: restore ", or a calibration," in
    `_types_and_pairing_help`."""
    from ui.dialogs.measurement_report_dialog import _types_and_pairing_help
    text = _types_and_pairing_help()
    assert "or a calibration" not in text
    assert "With Run type Calibration no report is made" in text


# --------------------------------------------------------------------------
# 3. the Colour accuracy graph plots the judged figures
# --------------------------------------------------------------------------
def _split_report(created, all_avg, in_avg):
    return {"created": created, "chart": "c",
            "de00": {"avg_all": all_avg, "max_all": all_avg * 3,
                     "mean": all_avg, "max": all_avg * 3},
            "gamut_split": {"de00_in": {"avg_all": in_avg,
                                        "max_all": in_avg * 3,
                                        "mean": in_avg, "max": in_avg * 3}}}


def test_the_accuracy_trend_plots_what_the_verdict_judged():
    """Knut, Q4: *"Yes, use the within-gamut figures."* A split sheet is
    judged on `graded_de00`, so the graph plots the same numbers, and a
    sheet with no split keeps its all-patch figures (which is what its
    verdict judged).

    MUTATION, proven red: read ``de = r.get("de00") or {}`` in
    `report_trend` again (the split date plots 1.36, the all-patch figure).
    """
    from workflow.measurement_report import graded_de00, report_trend
    split = _split_report("2026-12-01T10:00:00", 1.36, 1.95)
    plain = {"created": "2026-12-08T10:00:00", "chart": "c",
             "de00": {"avg_all": 1.2, "max_all": 3.0}}
    a, b = report_trend([split, plain])
    assert a["avg_all"] == pytest.approx(graded_de00(split)[0]["avg_all"])
    assert a["avg_all"] == pytest.approx(1.95)
    assert a["de00_population"] == "in_gamut"
    assert b["avg_all"] == pytest.approx(1.2)
    assert b["de00_population"] == "all"


def test_the_graph_says_its_figures_are_the_judged_ones(tmp_path, qapp):
    """With a within-gamut date on the axis the two "all patches" legend
    entries say "all judged patches", and the PDF description says which
    patches those are.

    MUTATION, proven red: drop ``if judged_pop`` from `_trend_configs`
    (the legend still reads "all patches" over within-gamut figures)."""
    from workflow.compliance_sets import effective_limits
    from tests.test_trend_graphs_for_judged_metrics import _open
    dlg = _open(tmp_path, qapp, effective_limits("chromiq_default", {}))
    try:
        dlg._trend_series = [{"created": "x", "avg_all": 1.0,
                              "de00_population": "in_gamut"}]
        labels = [m[0] for m in dlg._trend_configs()[0][2]]
        assert labels[0] == "Average ΔE, all judged patches", labels
        assert labels[3] == "Maximum ΔE, all judged patches", labels
        assert "within the profile's gamut" in dlg._trend_extras(
            dlg._trend_de)["about"]
        dlg._trend_series = [{"created": "x", "avg_all": 1.0,
                              "de00_population": "all"}]
        labels = [m[0] for m in dlg._trend_configs()[0][2]]
        assert labels[0] == "Average ΔE, all patches", labels
    finally:
        dlg.deleteLater()


@pytest.mark.parametrize("code", ["en", "de"])
def test_the_judged_description_fits_two_lines(qapp, code):
    """The same two-line rule as every other graph description (K25).

    MUTATION, proven red: append ", measured on every date the report covers
    so that a change in one ink shows up as a change in the line" to it
    (three lines)."""
    import json
    from PyQt6.QtGui import QTextDocument
    import ui.dialogs.measurement_report_dialog as mrd
    cat = {} if code == "en" else json.loads(
        (ROOT / "data" / "i18n" / f"{code}.json").read_text(encoding="utf-8"))
    family = QApplication.font().family().replace("'", "")

    def height(text):
        doc = QTextDocument()
        doc.setDocumentMargin(0)
        doc.setHtml(f"<div style=\"font-family:'{family}';font-size:"
                    f"{mrd._TREND_ABOUT_PX}px\">{text}</div>")
        doc.setTextWidth(600)
        return doc.size().height()
    en = mrd._TREND_ABOUT_DE_JUDGED()
    text = cat.get(en, en)
    assert code == "en" or text != en, "no German for it"
    assert 1 <= round(height(text) / height("x")) <= 2, text


# --------------------------------------------------------------------------
# 4. a project whose folder is not named what its files carry
# --------------------------------------------------------------------------
@pytest.fixture()
def chart_tab(tmp_path, qapp):
    from PyQt6.QtCore import QSettings
    from core.argyll_runner import ArgyllRunner
    from core.file_manager import FileManager
    from core.settings import AppSettings
    from ui.tabs.tab_chart import TabChart
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    s.set("custom_output_path", str(tmp_path / "projects"))
    fm = FileManager(s)
    t = TabChart(ArgyllRunner(s), fm, s)
    yield t, fm
    t.deleteLater()


def _project_with_files(fm, name):
    from tests.test_import_measurement_module import _cgats, _PATCHES
    fm.set_target_name(name)
    run = fm.project().current_run()
    run.ensure_dir()
    run.chart_ti2.write_text(_cgats("CTI2", _PATCHES), encoding="utf-8")
    run.measurement_ti3.write_text(_cgats("CTI3", _PATCHES), encoding="utf-8")
    return fm.root_dir() / name


def _choose(monkeypatch, action, seen):
    from ui.dialogs import target_change_dialog as tcd

    def _exec(self):
        seen.append(self)
        return 0
    monkeypatch.setattr(tcd.TargetChangeDialog, "exec", _exec)
    monkeypatch.setattr(tcd.TargetChangeDialog, "result_action",
                        lambda self: action)


def test_a_finder_duplicate_is_offered_the_rename_and_renamed(
        chart_tab, monkeypatch):
    """Knut, Q5: *"If a project is opened where the root project folder is
    different than the defined name in 'Printer profile project name'
    field, then the user should be given the option, with a popup window,
    to rename the project."* A Finder duplicate ("X copy") opened: the
    chooser comes up in its folder mode, and Rename leaves a project called
    "X-copy" whose files carry that name, so its measurement is found.

    MUTATION, proven red: leave `_offer_rename_for_a_renamed_folder` out of
    `open_project_manifest` (no chooser; the run's measurement is not found).
    """
    from ui.dialogs.target_change_dialog import TargetChangeAction
    t, fm = chart_tab
    src = _project_with_files(fm, "Demo")
    dup = src.parent / "Demo copy"
    shutil.copytree(src, dup)
    seen: list = []
    _choose(monkeypatch, TargetChangeAction.RENAME, seen)
    t.open_project_manifest(dup / "project.json")
    assert len(seen) == 1 and seen[0]._folder_renamed
    new = src.parent / "Demo-copy"
    assert new.is_dir() and not dup.exists()
    run = fm.project().current_run()
    assert run.dir.parents[1] == new
    assert run.measurement_ti3.is_file(), sorted(
        p.name for p in run.dir.iterdir())
    assert run.measurement_ti3.name == "Demo-copy.ti3"
    assert fm.project().target_name == "Demo-copy"
    assert fm.get_target_name() == "Demo-copy"
    # the original is untouched
    assert (src / "runs" / "run1" / "Demo.ti3").is_file()


def test_leave_it_as_it_is_writes_nothing(chart_tab, monkeypatch):
    """"Leave it as it is" changes nothing on disk.

    MUTATION, proven red: rename on any answer but Rename (test the result
    against CANCEL instead of RENAME)."""
    from ui.dialogs.target_change_dialog import TargetChangeAction
    t, fm = chart_tab
    src = _project_with_files(fm, "Demo")
    dup = src.parent / "Demo-2"
    shutil.copytree(src, dup)
    before = sorted(str(p.relative_to(dup)) for p in dup.rglob("*"))
    seen: list = []
    _choose(monkeypatch, TargetChangeAction.CANCEL, seen)
    t.open_project_manifest(dup / "project.json")
    assert len(seen) == 1
    assert sorted(str(p.relative_to(dup)) for p in dup.rglob("*")) == before


def test_a_folder_already_named_as_chromiq_would_is_renamed_in_place(
        chart_tab, monkeypatch):
    """A duplicate renamed "Demo-2" by hand needs no move, only its files:
    `rename_existing_project` returned early for that case and renamed
    nothing.

    MUTATION, proven red: restore ``if new_root == old_root: return
    old_root`` at the top of `rename_existing_project` (the files keep
    "Demo")."""
    from ui.dialogs.target_change_dialog import TargetChangeAction
    t, fm = chart_tab
    src = _project_with_files(fm, "Demo")
    dup = src.parent / "Demo-2"
    shutil.copytree(src, dup)
    _choose(monkeypatch, TargetChangeAction.RENAME, [])
    t.open_project_manifest(dup / "project.json")
    assert (dup / "runs" / "run1" / "Demo-2.ti3").is_file()
    assert not (dup / "runs" / "run1" / "Demo.ti3").exists()
    assert fm.name_its_files_carry(dup) is None


def test_a_project_whose_names_agree_is_not_asked(chart_tab, monkeypatch):
    """The control: an ordinary project opens with no question.

    MUTATION, proven red: make `name_its_files_carry` compare the raw
    stored name against ``root.name + " "`` (every project is asked)."""
    from ui.dialogs.target_change_dialog import TargetChangeAction
    t, fm = chart_tab
    src = _project_with_files(fm, "Demo")
    seen: list = []
    _choose(monkeypatch, TargetChangeAction.RENAME, seen)
    t.open_project_manifest(src / "project.json")
    assert seen == []


def test_the_chooser_offers_two_choices_in_its_folder_mode(qapp, tmp_path):
    """Keep both and Delete do not apply to one folder; the heading and the
    introduction are M-PROJECT-FOLDER-RENAMED's; a built profile is named.

    MUTATION, proven red: build the ordinary three choices in the folder
    mode too (four buttons with Cancel)."""
    from PyQt6.QtWidgets import QLabel, QPushButton
    from ui.dialogs.target_change_dialog import TargetChangeDialog
    dlg = TargetChangeDialog("Demo", "Demo-copy", tmp_path / "Demo copy",
                             tmp_path / "Demo-copy", None,
                             folder_renamed=True, built_profile=True)
    try:
        buttons = [b.text() for b in dlg.findChildren(QPushButton)]
        assert buttons == ['Rename the project to "Demo-copy"',
                           "Leave it as it is"], buttons
        text = "\n".join(lab.text() for lab in dlg.findChildren(QLabel))
        assert "This project's folder is called “Demo copy”, but its files " \
               "are named “Demo”" in text
        assert "keeps the name written inside it" in text
        assert "The folder becomes" in text
    finally:
        dlg.deleteLater()


# --------------------------------------------------------------------------
# 5. the evenness demo's paper white
# --------------------------------------------------------------------------
def test_the_evenness_demo_noisy_date_takes_the_paper_as_paper_white(
        tmp_path):
    """Knut, Q6: *"Fix it."* The noisy date's lightest reading, which the
    report takes as the paper white, is a paper patch, on the demo's own
    noisy date (seed 104) and on the neighbouring seeds.

    MUTATION, proven red: drop the ceiling in `_sheet` (seed 104 takes
    patch 337, a yellow, as the paper)."""
    sys.path.insert(0, str(ROOT / "scripts"))
    import make_evenness_demo as E
    from workflow.measurement_report import measurement_facts
    from workflow.ti3_analysis import parse_ti3
    ti2 = E._lay_out(E.UNCOVERED, tmp_path, "X")
    for seed in (104, 105, 106, 504):
        out = E._sheet(ti2, tmp_path / f"n{seed}.ti3", E._noisy, seed,
                       "X-Rite i1Pro 2", "2026-10-22T10:00:00")
        facts = measurement_facts(out)
        data = parse_ti3(out)
        ids = list(data.sample_locs or data.sample_ids)
        rgb = data.rgb[ids.index(facts["paper_white"]["loc"])]
        assert all(float(v) >= 99.999 for v in rgb), (seed, facts, rgb)


# --------------------------------------------------------------------------
# 6/7. Profiling names, and "for these measurements"
# --------------------------------------------------------------------------
def test_a_profiling_window_names_reports_after_their_runs(tmp_path, qapp):
    """Knut: *"When run type is set to Profiling: The name tags become Run1,
    Run2, ..., then Multiple runs and All runs"*. The grouping of B8-826
    stays.

    MUTATION, proven red: make `_scope_tag` answer with the Verification
    words whatever the kind ("One date" on a Profiling window)."""
    from datetime import datetime
    from workflow.measurement_report import SCOPE_ALL_DATES
    s, run1, run2 = _profiling_project(tmp_path)
    _save_doc([run1.dir], [run1.measurement_ti3],
              when=datetime(2026, 12, 1, 9, 0, 0))
    _save_doc([run2.dir], [run2.measurement_ti3],
              when=datetime(2026, 12, 2, 9, 0, 0))
    _save_doc([run1.dir, run2.dir], [run1.measurement_ti3,
                                     run2.measurement_ti3],
              when=datetime(2026, 12, 3, 9, 0, 0))
    dlg = _dialog(s, run1.measurement_ti3, qapp)
    try:
        names = [t for t, k, _e in _rows(dlg) if k]
        assert len(names) == 3, names
        assert sum(" · Run1" in n for n in names) == 1, names
        assert sum(" · Run2" in n for n in names) == 1, names
        assert sum(" · Multiple runs" in n for n in names) == 1, names
        assert not any("date" in n for n in names), names
        assert dlg._scope_tag(SCOPE_ALL_DATES) == "All runs"
        assert _headings(dlg)[:2] == ["Run1", "Run2"]
        assert dlg._type_blurb_full.startswith(
            "Already generated for these measurements: "), \
            dlg._type_blurb_full
    finally:
        dlg.close()


def test_a_verification_window_keeps_its_date_names(tmp_path, qapp):
    """Knut: Verification keeps "One date", "Multiple dates", "All dates",
    and its line keeps "for this run".

    MUTATION, proven red: say "for these measurements" on every window."""
    s, _fm, run1, _run2, v1, _v2 = _two_runs(tmp_path)
    dlg = _dialog(s, v1[-1].measurement_ti3, qapp)
    try:
        names = [t for t, k, _e in _rows(dlg) if k]
        assert names and all("One date" in n for n in names), names
        assert dlg._type_blurb_full.startswith(
            "Already generated for this run: "), dlg._type_blurb_full
    finally:
        dlg.close()


def test_a_profiling_window_with_nothing_generated_says_these_measurements(
        tmp_path, qapp):
    """The empty case follows the same words.

    MUTATION, proven red: keep "for this run yet." on the Profiling window."""
    s, run1, _run2 = _profiling_project(tmp_path)
    dlg = _dialog(s, run1.measurement_ti3, qapp)
    try:
        assert dlg._generated_types_line(dlg._run_ctx.run) == (
            "No report has been generated for these measurements yet.")
    finally:
        dlg.close()


# --------------------------------------------------------------------------
# 10. grouped from the start
# --------------------------------------------------------------------------
def test_report_shown_is_grouped_from_the_start(tmp_path, qapp):
    """Knut, 5792576954: *"'Report shown' should be grouped from the start,
    because one of the reports it offers covers two profile runs."* With
    only run1's dates in "Included measurements in report" and a report
    across run1 and run2 on offer, the headings are there before that report
    is selected.

    MUTATION, proven red: decide the grouping from the included measurements
    alone again (``if len(listed) <= 1``): the list is flat."""
    s, _fm, run1, run2, v1, v2 = _two_runs(tmp_path)
    _save_doc([v1[-1].dir, v2[0].dir],
              [v1[-1].measurement_ti3, v2[0].measurement_ti3])
    dlg = _dialog(s, v1[0].measurement_ti3, qapp)
    try:
        dlg._saved_combo.setCurrentIndex(0)             # New report…
        qapp.processEvents()
        origins = {str(r.get("_origin_dir")) for r in dlg._history}
        assert all(str(run1.dir) in o for o in origins), origins
        heads = _headings(dlg)
        assert "Run1" in heads, heads
        assert "Reports including multiple runs" in heads, heads
        assert dlg._saved_label.text() == "Report shown:"
    finally:
        dlg.close()


# --------------------------------------------------------------------------
# 8. <output folder>/reports/ only with the first report across projects
# --------------------------------------------------------------------------
def test_the_shared_reports_folder_waits_for_a_report_across_projects(
        tmp_path, qapp):
    """Knut, K26 (Q5 of the list questions): *"the reports/ folder should
    not be created before reports are created that include measurements
    that go across projects."* Opening a window, adding the other project's
    measurement, listing, counting and choosing "New report…" create
    nothing there; the first report across the two projects creates it.

    MUTATION, proven red: create each shared folder when it is read
    (``folder.mkdir(...)`` in `shared_documents`): the folder is there
    before any report."""
    from workflow.measurement_report import document_home
    s, _fm, run1, _run2, v1, _v2 = _two_runs(tmp_path)
    _qrun, qv = _second_project(tmp_path)
    shared = tmp_path / "reports"
    dlg = _dialog(s, v1[-1].measurement_ti3, qapp)
    try:
        dlg._saved_combo.setCurrentIndex(0)
        qapp.processEvents()
        dlg._add_source(qv.measurement_ti3)
        qapp.processEvents()
        dlg._sync_saved_reports(dlg._run_ctx.run)
        dlg._generated_types_line(dlg._run_ctx.run)
        assert not shared.exists(), "created before any report across projects"
    finally:
        dlg.close()
    home = _save_doc([v1[0].dir, qv.dir],
                     [v1[0].measurement_ti3, qv.measurement_ti3])
    assert home == document_home([v1[0].dir, qv.dir]) == shared
    assert shared.is_dir()


# --------------------------------------------------------------------------
# Q3: the Printing record keeps "Judged against"
# --------------------------------------------------------------------------
def test_the_printing_record_keeps_its_judged_against_row(tmp_path, qapp):
    """Knut, Q3: *"keep the judged against row, which defines the thresholds
    shown."* A Printing record grades nothing and still names, in its
    results, the set its thresholds come from.

    MUTATION, proven red: leave ``row_getters.append((tr("Judged against"),
    self._thresholds_cell))`` out of `_report_results_html`."""
    import html as _html
    from datetime import datetime
    from workflow.measurement_report import REPORT_TYPE_RECORD
    s, run1, _run2 = _profiling_project(tmp_path)
    _save_doc([run1.dir], [run1.measurement_ti3],
              when=datetime(2026, 12, 1, 9, 0, 0))
    dlg = _dialog(s, run1.measurement_ti3, qapp)
    try:
        assert dlg._report_type_now() == REPORT_TYPE_RECORD
        page = _html.unescape(dlg._report_body_html(dlg._runs_for_report(),
                                                    for_pdf=True))
        # the ROW of the results table, not the header line above it
        assert ">Judged against</td>" in page
    finally:
        dlg.close()


def test_the_measure_tab_button_opens_the_empty_window_under_calibration(
        qapp, monkeypatch):
    """The Measure tab's own "Measurement report" button asked for a
    measurement first and, with the calibration chart not measured, said
    "Measure this chart first". Under Run type Calibration it opens the
    window, which opens empty and says why.

    MUTATION, proven red: drop the ``if calibration:`` branch from
    `TabMeasure._open_measurement_report` (the "measure first" message
    comes instead of the window)."""
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    from ui.tabs import tab_measure as tm
    opened, told = [], []
    monkeypatch.setattr(MeasurementReportDialog, "exec",
                        lambda self: opened.append(self) or 0)
    monkeypatch.setattr(tm, "inform", lambda *a, **k: told.append(a),
                        raising=False)
    fake = QWidget()
    fake._target_ctl = SimpleNamespace(target=SimpleNamespace(
        run_type="calibration", is_calibration=lambda: True))
    from core.settings import AppSettings
    fake._settings = AppSettings()
    fake._ti1_path = None
    fake._is_verification_run = lambda: False
    try:
        tm.TabMeasure._open_measurement_report(fake)
        assert len(opened) == 1 and told == []
        assert opened[0]._calibration_locked
    finally:
        for d in opened:
            d.deleteLater()
        fake.deleteLater()


def test_a_cancelled_pdf_save_leaves_no_reports_folder(tmp_path, monkeypatch):
    """Knut (5792484060, 5): `<output folder>/reports/` exists only once a
    report across projects is written. `_export_pdf` created the folder for
    its file chooser and left it when the user cancelled.

    MUTATION: drop the `rmdir` on cancel and the folder is left: red."""
    import types
    from pathlib import Path
    import ui.dialogs.measurement_report_dialog as M
    import ui.widgets as W
    where = tmp_path / "out" / "reports"
    host = types.SimpleNamespace(
        _report_dir=lambda: where,
        _as_the_document_was_built=lambda: __import__("contextlib").nullcontext(),
        _report_filename=lambda runs: "x.pdf",
        _runs_for_document=lambda: [],
        _report={"x": 1}, _ti3=tmp_path / "m.ti3",
        _settings={"custom_output_path": ""})
    host._settings = types.SimpleNamespace(get=lambda k, d="": "")
    monkeypatch.setattr(W, "save_file_dialog", lambda *a, **k: "")
    M.MeasurementReportDialog._export_pdf(host)
    assert not where.exists(), "a cancelled save left an empty reports folder"
    # a folder that was already there is never removed
    where.mkdir(parents=True)
    M.MeasurementReportDialog._export_pdf(host)
    assert where.exists()
