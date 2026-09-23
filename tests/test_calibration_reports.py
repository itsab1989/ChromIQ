"""#182 beta 39: Run type = Calibration makes reports (Knut, 5794078008).

Knut retracted beta 38's ruling (§18.1, the empty and locked window):

    *"The run type set to calibration should be able to make a report after
    all. ... Allowed report types are all except the printing record, and
    measurements are stored under project_name/cal/ folder and reports (with
    included one measurement for a project) are stored and read from
    project_name/cal/reports/, and 'Included measurements...' lists the
    measurement in the cal/ folder. ... IF a report is created that selects
    measurements across projects, then that is stored same as the other run
    types, in the <ChromIQ default folder>/reports/ ... The report names shall
    have tags 'Cal' ..., or 'Multiple cals' ..., or 'All cals' ... The 'Report
    shown' dropdown list should then group the reports ... according to the
    project name ... And reports with multiple measurements included (across
    projects) are grouped under 'Reports including multiple projects'."*

Confirmed as described in our 5794100213 (5794311113). Every test names the
mutation that turns it red; each was run (REPORT.md in
~/Desktop/ChromIQ-beta39-proof/calibration/).
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest                                                  # noqa: E402
from PyQt6.QtWidgets import QApplication, QWidget              # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


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


# --------------------------------------------------------------------------
# fixtures
# --------------------------------------------------------------------------
def _settings(**values):
    from core.settings import AppSettings
    s = AppSettings()
    for k, v in values.items():
        s.set(k, v)
    return s


def _project_with_cal(root: Path, name: str):
    """A project NAME beside the others in *root*, with a measured
    calibration and no report yet. Returns (project, cal ti3)."""
    from core.file_manager import Project
    from tests.test_import_measurement_module import _cgats, _PATCHES
    proj = Project.create(root / name, name)
    cal = proj.calibration
    cal.ensure_dir()
    ti3 = cal.dir / f"{cal.stem}.ti3"
    ti3.write_text(_cgats("CTI3", _PATCHES), encoding="utf-8")
    return proj, ti3


_CLOCK = [0]


def _save(folders, ti3s, *, type_id=None, scope=None, record_first=True):
    """A report of *folders* written the way the window writes one (K23):
    one folder, one file that is the report; several, a verdict record in
    each folder and a document file where `document_home` says."""
    from workflow.measurement_report import (
        REPORT_TYPE_FULL, ROLE_RECORD, SCOPE_MULTIPLE_DATES, SCOPE_ONE_DATE,
        build_report, document_file, document_home, document_measurement_key,
        new_document_id, save_report, stamp_document)
    _CLOCK[0] += 1
    when = datetime(2026, 12, 1, 10, 0, 0) + timedelta(minutes=_CLOCK[0])
    tid = type_id or REPORT_TYPE_FULL
    reps = [build_report(t) for t in ti3s]
    members = [{"dir": str(f), "created": str(r.get("created") or ""),
                "ti3": t.name,
                "key": document_measurement_key(f, str(r.get("created") or ""),
                                                t.name)}
               for f, t, r in zip(folders, ti3s, reps)]
    several = len(folders) > 1
    scope = scope or (SCOPE_MULTIPLE_DATES if several else SCOPE_ONE_DATE)
    doc_id = new_document_id(when)
    stamp = when.isoformat(timespec="seconds")
    for f, rep in zip(folders, reps):
        stamp_document(rep, doc_id=doc_id, created=stamp, type_id=tid,
                       compliance=None, detail=False, measurements=members,
                       scope=scope, role=ROLE_RECORD if several else "")
        rep["report_type"] = tid
        save_report(rep, f)
    if several:
        body = document_file(doc_id=doc_id, created=stamp, type_id=tid,
                             compliance=None, detail=False,
                             measurements=members, scope=scope)
        return save_report(body, document_home(folders).parent)
    return None


def _bar(run_type: str = "calibration") -> QWidget:
    w = QWidget()
    w._target_ctl = SimpleNamespace(target=SimpleNamespace(run_type=run_type))
    return w


def _window(s, ti3, qapp, run_type="calibration"):
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    parent = _bar(run_type)
    dlg = MeasurementReportDialog(s, parent, initial_ti3=ti3)
    dlg._test_parent = parent
    dlg.show()
    qapp.processEvents()
    return dlg


def _rows(dlg):
    """``[(text, key or None)]`` below "New report…", separators left out."""
    combo = dlg._saved_combo
    out = []
    for i in range(1, combo.count()):
        text, key = combo.itemText(i), combo.itemData(i)
        if not text and key is None:
            continue
        out.append((text, key))
    return out


def _entries(dlg):
    return [t for t, k in _rows(dlg) if k is not None]


def _headings(dlg):
    return [t.strip() for t, k in _rows(dlg) if k is None]


def _files(root: Path) -> "list[str]":
    return sorted(str(p.relative_to(root)) for p in root.rglob("report_*.json"))


# --------------------------------------------------------------------------
# 1. the kind and the folders
# --------------------------------------------------------------------------
def test_a_calibration_offers_every_type_but_the_printing_record():
    """*"Allowed report types are all except the printing record"*.

    MUTATION, proven red: `if kind == KIND_VERIFICATION:` again in
    `report_types_for_kind` (a calibration is offered every type, the
    Printing record with them)."""
    from workflow.measurement_report import (KIND_CALIBRATION,
                                             REPORT_TYPE_RECORD, REPORT_TYPES,
                                             report_types_for_kind)
    got = report_types_for_kind(KIND_CALIBRATION)
    assert REPORT_TYPE_RECORD not in got
    assert set(got) == set(REPORT_TYPES) - {REPORT_TYPE_RECORD}


def test_the_folders_of_a_calibration(tmp_path):
    """A project's `cal/` is its own kind, belongs to the project, and its
    reports live in `cal/reports/`; several projects' in the folder beside
    them. A folder merely NAMED cal outside a project is not a calibration.

    MUTATION, proven red: drop the `if _is_cal(d): return d.parent` branch
    of `_project_folder_of` (`measurement_place` answers the output folder's
    name as the project)."""
    from workflow.measurement_report import (
        KIND_CALIBRATION, KIND_PROFILING, document_home, measurement_dir_kind,
        measurement_place, project_relative, shared_report_folders)
    p, _ = _project_with_cal(tmp_path, "P")
    q, _ = _project_with_cal(tmp_path, "Q")
    assert measurement_dir_kind(p.calibration.dir) == KIND_CALIBRATION
    loose = tmp_path / "elsewhere" / "cal"
    loose.mkdir(parents=True)
    assert measurement_dir_kind(loose) == KIND_PROFILING
    assert measurement_place(p.calibration.dir) == ("P", "cal")
    assert project_relative(p.calibration.dir) == "cal"
    assert document_home([p.calibration.dir]) == p.calibration.dir / "reports"
    assert (document_home([p.calibration.dir, q.calibration.dir])
            == tmp_path / "reports")
    shared = shared_report_folders([p.calibration.dir, q.calibration.dir])
    assert tmp_path / "reports" in shared
    assert p.root / "reports" not in shared
    assert q.root / "reports" not in shared


def test_a_moved_pack_finds_the_other_projects_calibration(tmp_path):
    """A report across projects records each calibration's folder where it
    was; after the pack moved, the other project's `cal/` is found beside
    this one.

    MUTATION, proven red: `if not rel.startswith("runs/"):` again in
    `resolve_recorded_folder` (the recorded, gone path comes back)."""
    from workflow.measurement_report import resolve_recorded_folder
    p, _ = _project_with_cal(tmp_path, "P")
    q, _ = _project_with_cal(tmp_path, "Q")
    recorded = Path("/Volumes/Gone/pack/Q/cal")
    assert resolve_recorded_folder(recorded, [p.root]) == q.calibration.dir


# --------------------------------------------------------------------------
# 2. one calibration: list, count, name, generate
# --------------------------------------------------------------------------
def test_a_calibration_window_lists_counts_and_writes_its_own_reports(
        tmp_path, qapp):
    """Under Run type Calibration the window loads the calibration, lists
    and counts its reports from `cal/reports/` (only the types Calibration
    allows, so beta 38's automatic Printing record is not offered), names
    them "Cal", and Generate report writes into `cal/reports/` and nowhere
    else.

    MUTATION, proven red: `if run is None: return []` again at the top of
    `_saved_documents` (the list is empty)."""
    from workflow.measurement_report import (REPORT_TYPE_FULL,
                                             REPORT_TYPE_RECORD)
    s = _settings()
    p, ti3 = _project_with_cal(tmp_path, "P")
    _save([p.calibration.dir], [ti3], type_id=REPORT_TYPE_FULL)
    _save([p.calibration.dir], [ti3], type_id=REPORT_TYPE_RECORD)
    dlg = _window(s, ti3, qapp)
    try:
        assert [str(src["origin"]) for src in dlg._sources] == [str(ti3)]
        names = _entries(dlg)
        assert len(names) == 1, names
        assert names[0].endswith(" · Cal"), names
        assert _headings(dlg) == []
        assert dlg._type_blurb_full == (
            "Already generated for these measurements: "
            "Full colour check: 1"), dlg._type_blurb_full
        rec = dlg._type_combo.findData(REPORT_TYPE_RECORD)
        assert not dlg._type_combo.model().item(rec).isEnabled()
        assert dlg._generate_btn.isEnabled(), dlg._generate_btn.toolTip()
        before = _files(tmp_path)
        dlg._start_new_report()
        qapp.processEvents()
        dlg._on_generate_report()
        qapp.processEvents()
        after = _files(tmp_path)
        new = sorted(set(after) - set(before))
        assert len(new) == 1 and new[0].startswith("P/cal/reports/"), new
        assert not (tmp_path / "reports").exists()
        assert not (p.root / "reports").exists()
        rep = json.loads((tmp_path / new[0]).read_text(encoding="utf-8"))
        assert rep["document"]["type"] != REPORT_TYPE_RECORD
        assert len(_entries(dlg)) == 2
    finally:
        dlg.close()


def test_a_new_calibration_report_starts_from_the_preferences_type(
        tmp_path, qapp):
    """A calibration has no run to keep a type on, so a new report is the
    Preferences default, fitted: a stored Printing record default is read as
    the Full colour check.

    MUTATION, proven red: drop the `if self._is_calibration_window():`
    branch of `_report_type_now` (the type of the freshly built page wins,
    Full colour check, over the Preferences Grey and tone check)."""
    from workflow.measurement_report import (REPORT_TYPE_FULL,
                                             REPORT_TYPE_GREY,
                                             REPORT_TYPE_RECORD)
    p, ti3 = _project_with_cal(tmp_path, "P")
    dlg = _window(_settings(report_default_type=REPORT_TYPE_GREY), ti3, qapp)
    try:
        assert dlg._report_type_now() == REPORT_TYPE_GREY
    finally:
        dlg.close()
    dlg = _window(_settings(report_default_type=REPORT_TYPE_RECORD), ti3, qapp)
    try:
        assert dlg._report_type_now() == REPORT_TYPE_FULL
    finally:
        dlg.close()


def test_a_window_with_no_bar_on_a_calibration_is_a_calibration_window(
        tmp_path, qapp):
    """The measurement decides when there is no profile bar behind the
    window, as it does for the automatic report.

    MUTATION, proven red: drop the `is_calibration_dir(origin)` branch in
    `_window_kind` (None, which keeps every type)."""
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    from workflow.measurement_report import KIND_CALIBRATION
    p, ti3 = _project_with_cal(tmp_path, "P")
    dlg = MeasurementReportDialog(_settings(), None, initial_ti3=ti3)
    try:
        assert dlg._window_kind() == KIND_CALIBRATION
    finally:
        dlg.close()


def test_delete_moves_a_calibration_report_into_cal_reports_old(
        tmp_path, qapp):
    """Delete Selected Report moves the file to `cal/reports/old/<stamp>/`.

    MUTATION, proven red: `if run is None: return []` again in
    `_saved_documents` (nothing is selected, nothing moves)."""
    from workflow.measurement_report import REPORT_TYPE_FULL
    p, ti3 = _project_with_cal(tmp_path, "P")
    _save([p.calibration.dir], [ti3], type_id=REPORT_TYPE_FULL)
    dlg = _window(_settings(), ti3, qapp)
    try:
        key = next(k for _t, k in _rows(dlg) if k)
        dlg._saved_combo.setCurrentIndex(dlg._saved_combo.findData(key))
        qapp.processEvents()
        dlg._on_delete_report()
        qapp.processEvents()
        live = list((p.calibration.dir / "reports").glob("report_*.json"))
        old = list((p.calibration.dir / "reports" / "old").rglob(
            "report_*.json"))
        assert live == [] and len(old) == 1, (live, old)
    finally:
        dlg.close()


# --------------------------------------------------------------------------
# 3. several projects' calibrations
# --------------------------------------------------------------------------
def test_several_calibrations_are_grouped_by_project(tmp_path, qapp):
    """Another project's calibration added: a heading per project with its
    reports directly under it (no run heading), a report of both under
    "Reports including multiple projects", named "All cals" (it covers every
    calibration listed). Generate is greyed, and says why in calibration
    words.

    MUTATION, proven red: drop `if not calibration:` before the run heading
    in `_grouped_documents` (a "Cal" heading appears under each project)."""
    from workflow.measurement_report import SCOPE_ALL_DATES
    p, pti3 = _project_with_cal(tmp_path, "P")
    q, qti3 = _project_with_cal(tmp_path, "Q")
    _save([p.calibration.dir], [pti3])
    _save([q.calibration.dir], [qti3])
    _save([p.calibration.dir, q.calibration.dir], [pti3, qti3],
          scope=SCOPE_ALL_DATES)
    dlg = _window(_settings(), pti3, qapp)
    try:
        dlg._add_source(qti3)
        qapp.processEvents()
        assert _headings(dlg) == ["P", "Q",
                                  "Reports including multiple projects"], \
            _headings(dlg)
        rows = [t for t, _k in _rows(dlg)]
        assert rows[-1].endswith(" · All cals"), rows
        assert rows[1].endswith(" · Cal") and rows[3].endswith(" · Cal")
        assert not dlg._generate_btn.isEnabled()
        assert dlg._generate_btn.toolTip().startswith(
            "Calibrations of more than one project are loaded.")
        assert dlg._type_blurb_full.startswith(
            "Already generated for these measurements: ")
        assert "Full colour check: 3" in dlg._type_blurb_full
    finally:
        dlg.close()


def test_multiple_cals_and_all_cals(tmp_path, qapp):
    """Three projects: a report of two of them is "Multiple cals", a report
    of all three "All cals", one project's "Cal"; each is offered in P's own
    window from the start, grouped because it covers other projects.

    MUTATION, proven red: return `tr("All cals")` for every report of
    several projects in `_scope_tag` ("Multiple cals" is never shown)."""
    from workflow.measurement_report import SCOPE_ALL_DATES
    p, pti3 = _project_with_cal(tmp_path, "P")
    q, qti3 = _project_with_cal(tmp_path, "Q")
    r, rti3 = _project_with_cal(tmp_path, "R")
    _save([p.calibration.dir], [pti3])
    _save([p.calibration.dir, q.calibration.dir], [pti3, qti3])
    _save([p.calibration.dir, q.calibration.dir, r.calibration.dir],
          [pti3, qti3, rti3], scope=SCOPE_ALL_DATES)
    dlg = _window(_settings(), pti3, qapp)
    try:
        tags = sorted(t.rsplit(" · ", 1)[-1] for t in _entries(dlg))
        assert tags == ["All cals", "Cal", "Multiple cals"], _entries(dlg)
        assert _headings(dlg) == ["P", "Reports including multiple projects"]
    finally:
        dlg.close()


def test_a_report_of_two_calibrations_is_not_offered_to_a_third(
        tmp_path, qapp):
    """Every project has a `cal/`, so "covers a measurement in the list"
    must compare the PROJECT too: a report of P and Q is not R's.

    MUTATION, proven red: `_coverage_key` returning `project_relative(d)`
    for a calibration ("cal" for all three, so R's window lists it)."""
    p, pti3 = _project_with_cal(tmp_path, "P")
    q, qti3 = _project_with_cal(tmp_path, "Q")
    r, rti3 = _project_with_cal(tmp_path, "R")
    _save([p.calibration.dir, q.calibration.dir], [pti3, qti3])
    dlg = _window(_settings(), rti3, qapp)
    try:
        assert _entries(dlg) == []
        assert dlg._type_blurb_full == (
            "No report has been generated for these measurements yet.")
    finally:
        dlg.close()


# --------------------------------------------------------------------------
# 4. the other run types, and a calibration under them
# --------------------------------------------------------------------------
def test_a_calibration_s_reports_are_not_counted_on_a_profiling_window(
        tmp_path):
    """A calibration folder handed to the counter of a Profiling window is
    not a profiling sheet: its Printing record is not counted there (K24,
    the bar decides).

    MUTATION, proven red: drop the `is_calibration_dir` branch of
    `measurement_dir_kind` (the cal folder reads as a profiling sheet and
    its record is counted)."""
    from workflow.measurement_report import (KIND_PROFILING,
                                             REPORT_TYPE_RECORD,
                                             generated_report_types)
    p, ti3 = _project_with_cal(tmp_path, "P")
    _save([p.calibration.dir], [ti3], type_id=REPORT_TYPE_RECORD)
    assert generated_report_types(
        None, KIND_PROFILING, "",
        measurement_dirs=[str(p.calibration.dir)]) == {}


def test_under_calibration_a_run_s_measurement_is_never_written(
        tmp_path, qapp):
    """A Calibration window whose calibration was removed from the list,
    leaving a run's measurement first, writes nothing: Generate is greyed
    and says why, and the handler refuses as well.

    MUTATION, proven red: drop the `if self._is_calibration_window():`
    branch of `_reports_to_generate` (the run's sheet is offered to Generate,
    to be written as a calibration type into the run's folder). The enable
    line's own `cal_ok` condition and the handler's refusal are belt and
    braces behind it: each alone survives, because this list is empty."""
    from tests.test_import_measurement_module import _cgats, _PATCHES
    p, pti3 = _project_with_cal(tmp_path, "P")
    run = p.current_run()
    run.ensure_dir()
    sheet = run.dir / f"{p.root.name}.ti3"
    sheet.write_text(_cgats("CTI3", _PATCHES), encoding="utf-8")
    dlg = _window(_settings(), pti3, qapp)
    try:
        dlg._add_source(sheet)
        qapp.processEvents()
        del dlg._sources[0]
        dlg._report = dlg._subject_of(dlg._sources[0])
        dlg._rebuild_from_sources()
        qapp.processEvents()
        assert dlg._reports_to_generate() == []
        assert not dlg._generate_btn.isEnabled()
        assert "With Run type Calibration" in dlg._generate_btn.toolTip()
        before = _files(tmp_path)
        dlg._on_generate_report()
        assert _files(tmp_path) == before
    finally:
        dlg.close()


# --------------------------------------------------------------------------
# 5. the automatic report, the Measure tab's door, the help
# --------------------------------------------------------------------------
def test_the_automatic_report_of_a_calibration_is_never_a_printing_record(
        tmp_path):
    """After a calibration measurement ChromIQ writes the report by itself,
    as after a verification: the Preferences type, never the Printing
    record, into `cal/reports/`, named "Cal" (scope one).

    MUTATION, proven red: drop the `else:` branch that sets
    KIND_CALIBRATION in `TabMeasure._stamp_the_automatic_document` (a
    Printing record default is written as a Printing record)."""
    from ui.tabs.tab_measure import TabMeasure
    from workflow.measurement_report import (REPORT_TYPE_FULL,
                                             REPORT_TYPE_RECORD,
                                             SCOPE_ONE_DATE, build_report,
                                             save_report)
    p, ti3 = _project_with_cal(tmp_path, "P")
    fake = SimpleNamespace(
        _settings=_settings(report_default_type=REPORT_TYPE_RECORD))
    report = build_report(ti3)
    TabMeasure._stamp_the_automatic_document(fake, report, ti3, None)
    assert report["document"]["type"] == REPORT_TYPE_FULL
    assert report["document"]["scope"] == SCOPE_ONE_DATE
    path = save_report(report, ti3.parent)
    assert path.parent == p.calibration.dir / "reports"


def test_the_measure_tab_button_opens_the_calibration_s_measurement(
        tmp_path, qapp, monkeypatch):
    """The Measure tab's report button under Run type Calibration opens the
    window on `cal/<name>-cal.ti3`; a calibration not measured yet is told
    "Measure this chart first", as a run's chart is.

    MUTATION, proven red: drop the `if calibration:` block that takes the
    calibration's `.ti3` in `TabMeasure._open_measurement_report` (with no
    chart path the button says "Measure this chart first")."""
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    from ui.tabs import tab_measure as tm
    p, ti3 = _project_with_cal(tmp_path, "P")
    opened, told = [], []
    monkeypatch.setattr(MeasurementReportDialog, "exec",
                        lambda self: opened.append(self) or 0)
    monkeypatch.setattr(tm, "inform", lambda *a, **k: told.append(a),
                        raising=False)
    fake = QWidget()
    fake._target_ctl = SimpleNamespace(
        target=SimpleNamespace(run_type="calibration",
                               is_calibration=lambda: True),
        project_or_none=lambda: p)
    fake._settings = _settings()
    fake._ti1_path = None
    fake._is_verification_run = lambda: False
    try:
        tm.TabMeasure._open_measurement_report(fake)
        assert told == [] and len(opened) == 1
        assert [str(s["origin"]) for s in opened[0]._sources] == [str(ti3)]
        ti3.unlink()
        tm.TabMeasure._open_measurement_report(fake)
        assert len(told) == 1 and len(opened) == 1
    finally:
        for d in opened:
            d.deleteLater()
        fake.deleteLater()


def test_the_type_help_says_what_a_calibration_can_have():
    """The Report type help says which types each Run type offers; beta 38
    said a calibration makes none.

    MUTATION, proven red: restore "With Run type Calibration no report is
    made, and the window opens empty." in `_types_and_pairing_help`."""
    from ui.dialogs.measurement_report_dialog import _types_and_pairing_help
    text = _types_and_pairing_help()
    assert "no report is made" not in text
    assert ("With Run type Calibration, the calibration's measurement can "
            "have every type but the Printing record") in text
    assert "A calibration or a file outside a project" not in text


def test_the_withdrawn_red_line_is_gone():
    """M-REPORT-NOT-FOR-CALIBRATION was proposed for beta 38's locked window
    and never approved; with the ruling retracted it is withdrawn.

    MUTATION, proven red: put the message back in the catalogue."""
    from workflow import measurement_messages as M
    assert "M-REPORT-NOT-FOR-CALIBRATION" not in M.CATALOGUE
    src = (ROOT / "ui" / "dialogs" / "measurement_report_dialog.py").read_text(
        encoding="utf-8")
    assert "_lock_for_calibration" not in src
