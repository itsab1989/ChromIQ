"""K31 (Knut, #182 5801677743, 2026-09-23, beta 40): a report is the only
thing there is, and the limit set belongs to the report.

* A report of several measurements writes ONE file, carrying every verdict,
  and nothing into the measurements' own folders (no verdict records).
* With a report selected, Update rewrites it where it lives, whichever
  profile run the window was opened from; a new report is saved where its
  ticked measurements decide, from any window. A report of one date updated
  to cover more dates becomes a report of those dates.
* "Judged against" and Edit limits change only the report on screen; nothing
  is bound or written until Generate report. One set for the whole report,
  always (G7 Q2 option a), within one run too.
* "Unlock this run's limits", the run lock and the Preferences option that
  allowed unlocking are gone; an older meta.json still reads without error.
* A new report starts on the Preferences > Reports type and set, unless its
  profile run has a default of its own chosen in Edit limits, which wins.
* Records an earlier ChromIQ wrote are read-only history.

Spec: `docs/design/measurement_report_limits.md` §25. Every test names the
mutation that turns it red; each was run red before the commit
(~/Desktop/ChromIQ-beta40-proof/k31-a-report-model/mutations.txt).
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timedelta
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest                                                  # noqa: E402
from PyQt6.QtWidgets import QApplication, QCheckBox            # noqa: E402

from tests.test_calibration_reports import _settings, _window  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture(autouse=True)
def _quiet(monkeypatch):
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    monkeypatch.setattr(MeasurementReportDialog, "_confirm",
                        lambda self, *a, **k: True)
    monkeypatch.setattr(MeasurementReportDialog, "_say_generated",
                        lambda self, saved, failed: None)


# --------------------------------------------------------------------------
# fixtures
# --------------------------------------------------------------------------
_T0 = datetime(2026, 12, 1, 10, 0, 0)


def _automatic_report(run, v, set_id="chromiq_default"):
    """The report ChromIQ writes by itself after a measurement: that date's
    own report of one date, with its own settings (a document block of one
    measurement, "One date")."""
    from workflow.compliance_sets import SET_BY_ID, effective_limits
    from workflow.measurement_report import (SCOPE_ONE_DATE, build_report,
                                             document_measurement_key,
                                             new_document_id, report_type,
                                             save_report, stamp_document,
                                             stamp_verdict)
    rep = build_report(v.measurement_ti3)
    stamp_verdict(rep, effective_limits(set_id, {}), set_id=set_id,
                  set_label=SET_BY_ID[set_id].label)
    created = str(rep.get("created") or "")
    stamp_document(rep, doc_id=new_document_id(), created=created,
                   type_id=report_type(rep), compliance=rep.get("compliance"),
                   detail=False, scope=SCOPE_ONE_DATE,
                   measurements=[{"dir": str(v.dir), "created": created,
                                  "ti3": v.measurement_ti3.name,
                                  "key": document_measurement_key(
                                      v.dir, created, v.measurement_ti3.name)}])
    return save_report(rep, v.dir)


def _date(run, i, scale=1.0, set_id="chromiq_default"):
    from tests.test_import_measurement_module import _cgats, _PATCHES
    v = run.new_verification(_T0 + timedelta(days=7 * i))
    v.ensure_dir()
    v.measurement_ti3.write_text(
        _cgats("CTI3", [(r * scale, g, b) for (r, g, b) in _PATCHES]),
        encoding="utf-8")
    t = (_T0 + timedelta(days=7 * i)).timestamp()
    os.utime(v.measurement_ti3, (t, t))
    _automatic_report(run, v, set_id)
    return v


def _two_run_project(tmp_path):
    """Knut's case: project P, run1 with one date, run2 with two dates, each
    date with its own automatic report."""
    from core.file_manager import Project
    proj = Project.create(tmp_path / "P", "P")
    run1 = proj.current_run()
    run1.ensure_dir()
    r1 = [_date(run1, 0)]
    run2 = proj.new_run()
    run2.ensure_dir()
    r2 = [_date(run2, 3, 0.8), _date(run2, 4, 0.7)]
    return proj, run1, run2, r1, r2


def _tree(root: Path) -> dict:
    """{relative path: bytes} of every file under *root*."""
    return {str(p.relative_to(root)): p.read_bytes()
            for p in sorted(Path(root).rglob("*")) if p.is_file()}


def _entry_for(dlg, folder: Path):
    """The "Report shown" entry of the one-date report filed in *folder*."""
    docs = dlg._saved_documents(dlg._run_ctx.run)
    for d in docs:
        for r, _n in d.get("members") or []:
            if str(r.get("_origin_dir")) == str(folder) and not d.get("file"):
                return d
    raise AssertionError(f"no one-date report of {folder} is listed")


def _pick(dlg, key, qapp):
    i = dlg._saved_combo.findData(key)
    assert i >= 0, key
    dlg._saved_combo.setCurrentIndex(i)
    qapp.processEvents()


def _press(dlg, qapp, answer):
    dlg._ask_update_or_create_new = lambda: answer
    dlg._on_generate_report()
    qapp.processEvents()


# --------------------------------------------------------------------------
# 1. a report is the only thing there is
# --------------------------------------------------------------------------
def test_a_report_of_several_dates_is_one_file_and_writes_no_record(
        tmp_path, qapp):
    """Knut: *"Should a report of several measurements stop writing verdict
    records altogether?"* *"Agreed."*

    MUTATION: write a verdict record (role "record") into each date again in
    `_write_the_document` and this goes red."""
    from workflow.measurement_report import (JUDGED_KEY, recorded_document)
    proj, _r1, run2, _d1, d2 = _two_run_project(tmp_path)
    before = {str(v.dir): _tree(v.dir) for v in d2}
    dlg = _window(_settings(), d2[-1].measurement_ti3, qapp, "verification")
    try:
        dlg._saved_combo.setCurrentIndex(0)
        qapp.processEvents()
        dlg._select_all_btn.click()
        qapp.processEvents()
        _press(dlg, qapp, "new")
    finally:
        dlg.close()
    for v in d2:
        assert _tree(v.dir) == before[str(v.dir)], (
            f"a report of several dates wrote into {v.dir}")
    home = sorted((run2.verifications_dir / "reports").glob("report_*.json"))
    assert len(home) == 1, home
    block = recorded_document(json.loads(home[0].read_text(encoding="utf-8")))
    assert len(block["measurements"]) == 2
    assert all(m.get(JUDGED_KEY) for m in block["measurements"])


def test_a_report_across_runs_writes_nothing_into_any_date(tmp_path, qapp):
    """Knut: *"When a report covers more than one run or project, should
    GENERATE REPORT write anything into the dates' own folders? Answer: no."*

    MUTATION: write a record into the window's own run's dates again (the
    pre-K31 `_records_across_places`) and this goes red."""
    proj, run1, run2, d1, d2 = _two_run_project(tmp_path)
    runs_before = {str(r.dir): _tree(r.dir) for r in (run1, run2)}
    dlg = _window(_settings(), d2[-1].measurement_ti3, qapp, "verification")
    try:
        dlg._add_source(d1[0].measurement_ti3)
        qapp.processEvents()
        dlg._saved_combo.setCurrentIndex(0)
        qapp.processEvents()
        dlg._select_all_btn.click()
        qapp.processEvents()
        _press(dlg, qapp, "new")
    finally:
        dlg.close()
    for r in (run1, run2):
        assert _tree(r.dir) == runs_before[str(r.dir)], (
            f"a report across runs wrote into {r.dir}")
    assert len(list((Path(proj.root) / "reports").glob("report_*.json"))) == 1


# --------------------------------------------------------------------------
# 2. Update from any window; a new report where the ticks decide
# --------------------------------------------------------------------------
def test_knuts_case_update_run1s_one_date_report_from_run2s_window(
        tmp_path, qapp):
    """Knut's step-by-step case (§0d of our 5798697107): open from run2, add
    run1, select run1's report of one date, tick only that date, Update: that
    report is rewritten in run1's own folder, and nothing is written
    anywhere else. *"Agreed."*

    MUTATION: put the window's-own-run filter back into
    `_reports_to_generate` (Generate greys, nothing is written) and this
    goes red."""
    from workflow.measurement_report import recorded_document
    proj, run1, run2, d1, d2 = _two_run_project(tmp_path)
    target = d1[0]
    before = _tree(Path(proj.root))
    own = sorted((target.dir / "reports").glob("report_*.json"))
    assert len(own) == 1
    dlg = _window(_settings(), d2[-1].measurement_ti3, qapp, "verification")
    try:
        dlg._add_source(target.measurement_ti3)
        qapp.processEvents()
        entry = _entry_for(dlg, target.dir)
        _pick(dlg, entry["key"], qapp)
        dlg._hidden_runs = {dlg._run_key(r) for r in dlg._history
                            if str(r.get("_origin_dir")) != str(target.dir)}
        dlg._sync_limit_controls()
        qapp.processEvents()
        assert dlg._generate_btn.isEnabled(), dlg._generate_btn.toolTip()
        _press(dlg, qapp, "update")
    finally:
        dlg.close()
    after = _tree(Path(proj.root))
    changed = sorted(k for k in set(before) | set(after)
                     if before.get(k) != after.get(k))
    rel_own = str(own[0].relative_to(proj.root))
    rel_old = [k for k in changed if k.startswith(
        str((target.dir / "reports" / "old").relative_to(proj.root)))]
    assert rel_own in changed, "run1's report of one date was not rewritten"
    assert set(changed) == {rel_own, *rel_old}, (
        f"the Update wrote outside run1's report: {changed}")
    block = recorded_document(json.loads(own[0].read_text(encoding="utf-8")))
    assert block.get("updated"), block


def test_a_new_report_of_another_runs_date_is_saved_in_that_date(
        tmp_path, qapp):
    """Knut: *"With 'Create New', or 'New report...', and only another run's
    dates ticked, may the new report be saved where those dates decide?"*
    *"Agreed."*

    MUTATION: file the report in the window's run instead of where
    `document_home` puts it, or restore the own-run filter, and this goes
    red."""
    proj, run1, run2, d1, d2 = _two_run_project(tmp_path)
    target = d1[0]
    before = sorted((target.dir / "reports").glob("report_*.json"))
    dlg = _window(_settings(), d2[-1].measurement_ti3, qapp, "verification")
    try:
        dlg._add_source(target.measurement_ti3)
        qapp.processEvents()
        dlg._saved_combo.setCurrentIndex(0)                  # New report…
        qapp.processEvents()
        dlg._hidden_runs = {dlg._run_key(r) for r in dlg._history
                            if str(r.get("_origin_dir")) != str(target.dir)}
        dlg._sync_limit_controls()
        _press(dlg, qapp, "new")
    finally:
        dlg.close()
    after = sorted((target.dir / "reports").glob("report_*.json"))
    assert len(after) == len(before) + 1, (before, after)


def test_widening_a_one_date_report_makes_it_a_report_of_those_dates(
        tmp_path, qapp):
    """Knut: *"that is the logical thing, if a user chooses to update the
    automatically created reports of one date."* The report keeps its id,
    lives where its dates decide, its name follows ("Multiple dates" or "All
    dates"), and its one-date file is archived into that date's
    `reports/old/`, never deleted.

    MUTATION: skip the retirement of the files the new shape no longer has
    (`retire`) in `_write_the_document` and this goes red (the date keeps a
    one-date file of a report that now covers two)."""
    from workflow.measurement_report import (SCOPE_ONE_DATE,
                                             recorded_document)
    proj, run1, run2, d1, d2 = _two_run_project(tmp_path)
    first = d2[0]
    own = sorted((first.dir / "reports").glob("report_*.json"))[0]
    doc_id = recorded_document(json.loads(own.read_text(encoding="utf-8")))["id"]
    dlg = _window(_settings(), first.measurement_ti3, qapp, "verification")
    try:
        entry = _entry_for(dlg, first.dir)
        _pick(dlg, entry["key"], qapp)
        dlg._select_all_btn.click()
        qapp.processEvents()
        _press(dlg, qapp, "update")
    finally:
        dlg.close()
    assert not own.exists(), "the one-date file stayed live"
    assert list((own.parent / "old").glob("*/" + own.name)), (
        "the one-date file was not archived")
    home = sorted((run2.verifications_dir / "reports").glob("report_*.json"))
    assert len(home) == 1
    block = recorded_document(json.loads(home[0].read_text(encoding="utf-8")))
    assert block["id"] == doc_id and len(block["measurements"]) == 2
    assert block.get("scope") != SCOPE_ONE_DATE


# --------------------------------------------------------------------------
# 3. the limit set belongs to the report
# --------------------------------------------------------------------------
def test_changing_judged_against_writes_nothing_until_generate(tmp_path, qapp):
    """Knut: *"changing the reports settings does not change the report, and
    its binding to a limit set, unless you click Generate Report"*.

    MUTATION: bind the window's run in `_on_set_chosen` (the pre-K31
    `bind_run`) and this goes red."""
    proj, run1, run2, d1, d2 = _two_run_project(tmp_path)
    before = _tree(Path(proj.root))
    dlg = _window(_settings(), d2[-1].measurement_ti3, qapp, "verification")
    try:
        i = dlg._set_combo.findData("chromiq_tight")
        dlg._set_combo.setCurrentIndex(i)
        qapp.processEvents()
        assert dlg._report_limits().set_id == "chromiq_tight"
        assert dlg._settings_were_modified()
        assert _tree(Path(proj.root)) == before, "a set change wrote a file"
    finally:
        dlg.close()


def test_edit_limits_changes_only_the_report(tmp_path, qapp, monkeypatch):
    """With ONE profile run loaded the limits window is the REPORT's ("This
    report"), an edit is the report's own limits, and no file is written.

    MUTATION: write the edit onto the run (store it on the run's meta.json
    after `self._report_own_limits = own`, as the pre-K31 "This run" column
    did) and this goes red."""
    import ui.dialogs.thresholds_dialog as td
    from workflow.compliance_sets import Limit
    proj, run1, run2, d1, d2 = _two_run_project(tmp_path)
    before = _tree(Path(proj.root))
    seen = {}

    def _exec(self):
        seen["header"] = self._header_text(td.RUN_COLUMN)
        self._run_limits["all_de00_avg"] = Limit.value(0.4)
        self._run_dirty = True
        self.done(0)
        return 0

    monkeypatch.setattr(td.ThresholdsDialog, "exec", _exec)
    dlg = _window(_settings(), d2[-1].measurement_ti3, qapp, "verification")
    try:
        dlg._on_open_limits()
        qapp.processEvents()
        assert seen["header"] == "This report"
        own = dlg._report_own_limits
        assert own is not None and own.limits["all_de00_avg"].number == 0.4
        assert dlg._settings_were_modified()
        assert _tree(Path(proj.root)) == before, "Edit limits wrote a file"
    finally:
        dlg.close()


def test_a_set_change_still_counts_after_edit_limits_is_closed_unchanged(
        tmp_path, qapp, monkeypatch):
    """Found driving beta 40 on screen: "Judged against" moved to ChromIQ
    tight, Edit limits opened and closed with nothing changed, and Generate
    then asked "Nothing was changed for the selected report" (the file was
    still written against tight). Closing the limits window unchanged must
    leave the report's changed settings, and the red line, as they were.

    MUTATION: call `self._refresh()` again when `own is None` in
    `_open_report_limits_window` and this goes red."""
    import ui.dialogs.thresholds_dialog as td
    proj, run1, run2, d1, d2 = _two_run_project(tmp_path)
    monkeypatch.setattr(td.ThresholdsDialog, "exec",
                        lambda self: (self.done(0), 0)[1])
    dlg = _window(_settings(), d2[-1].measurement_ti3, qapp, "verification")
    try:
        _pick(dlg, _entry_for(dlg, d2[-1].dir)["key"], qapp)
        assert not dlg._settings_were_modified()
        i = dlg._set_combo.findData("chromiq_tight")
        dlg._set_combo.setCurrentIndex(i)
        qapp.processEvents()
        assert dlg._settings_were_modified()
        dlg._on_open_limits()
        qapp.processEvents()
        assert dlg._report_limits().set_id == "chromiq_tight"
        assert dlg._settings_were_modified(), (
            "closing Edit limits unchanged forgot the set change")
    finally:
        dlg.close()


def test_the_column_choice_is_remembered_and_binds_nothing(
        tmp_path, qapp, monkeypatch):
    """Which columns the limits window shows is a VIEW setting, remembered
    per profile run (K-b), and it is the only thing besides the run's own
    default that the window may write: the column choice goes into the
    window's run's meta.json, no limit set, no numbers, and no report file
    changes.

    MUTATION: drop the `set_run_columns(view_run, cols_after)` write-back in
    `_open_report_limits_window`, or let it write the report's set onto the
    run with it, and this goes red."""
    import ui.dialogs.thresholds_dialog as td
    proj, run1, run2, d1, d2 = _two_run_project(tmp_path)
    reports_before = {p: p.read_bytes()
                      for p in Path(proj.root).rglob("report_*.json")}

    def _exec(self):
        m = self._run.load_meta()
        m.compliance_columns = ["chromiq_default", "chromiq_tight"]
        self._run.save_meta(m)
        self.done(0)
        return 0

    monkeypatch.setattr(td.ThresholdsDialog, "exec", _exec)
    dlg = _window(_settings(), d2[-1].measurement_ti3, qapp, "verification")
    try:
        dlg._on_open_limits()
        qapp.processEvents()
    finally:
        dlg.close()
    meta = run2.load_meta()
    assert list(meta.compliance_columns) == ["chromiq_default",
                                             "chromiq_tight"]
    assert not meta.compliance_set_id and not meta.compliance_thresholds, (
        "the column choice bound the run to a set")
    assert {p: p.read_bytes() for p in Path(proj.root).rglob(
        "report_*.json")} == reports_before


def test_one_set_for_the_whole_report_within_one_run(tmp_path, qapp):
    """G7 Q2, option (a): *"Go for option (a) One set for the whole
    report, always."* Two dates of ONE run whose own reports were judged
    against two sets are both in the report, judged against its one set.

    MUTATION: make `_judged_by_the_document` keep each row's own recorded
    verdict (append `r` instead of `self._judged_live(r, lim)`) and this goes
    red."""
    from core.file_manager import Project
    from workflow.measurement_report import recorded_compliance
    proj = Project.create(tmp_path / "P", "P")
    run = proj.current_run()
    run.ensure_dir()
    a = _date(run, 0, 1.0, "chromiq_default")
    b = _date(run, 1, 0.9, "chromiq_tight")
    dlg = _window(_settings(), b.measurement_ti3, qapp, "verification")
    try:
        dlg._saved_combo.setCurrentIndex(0)
        qapp.processEvents()
        dlg._select_all_btn.click()
        qapp.processEvents()
        rows = dlg._runs_for_document()
        assert {str(r["_origin_dir"]) for r in rows} == {str(a.dir), str(b.dir)}
        sets = {(recorded_compliance(r) or {}).get("set_id") for r in rows}
        assert sets == {dlg._report_limits().set_id}, sets
    finally:
        dlg.close()


# --------------------------------------------------------------------------
# 4. no unlock, no lock
# --------------------------------------------------------------------------
def test_no_unlock_control_and_no_option_that_allowed_it(tmp_path, qapp):
    """Knut: *"I agree that the 'Unlock this run's limits' is no longer
    needed"*. No report window builds it, a run with two dated
    verifications keeps every limit control live, and Preferences has no
    "Allow editing of thresholds after the first verification measurement".

    MUTATION: build the unlock box again, grey the pulldown on a run with two
    dates (the old lock), or put the Preferences option back, and this goes
    red."""
    from core.settings import DEFAULTS
    from workflow import run_compliance as rc
    proj, run1, run2, d1, d2 = _two_run_project(tmp_path)
    dlg = _window(_settings(), d2[-1].measurement_ti3, qapp, "verification")
    try:
        assert not any("Unlock" in c.text()
                       for c in dlg.findChildren(QCheckBox))
        assert dlg._set_combo.isEnabled() and dlg._limits_btn.isEnabled()
        assert dlg._limits_btn.text() == "Edit limits…"
    finally:
        dlg.close()
    assert "compliance_allow_edit_after_measurement" not in DEFAULTS
    for gone in ("is_locked", "may_unlock", "bind_run", "ensure_bound",
                 "set_run_unlocked", "set_run_report_type"):
        assert not hasattr(rc, gone), gone
    import inspect
    import ui.dialogs.settings_dialog as sd
    assert "Allow editing of thresholds" not in inspect.getsource(sd)


def test_an_older_meta_json_still_reads_and_locks_nothing(tmp_path, qapp):
    """A run an earlier ChromIQ bound, edited and unlocked reads without
    error: its bound set is its default for new reports, its unlock flag is
    ignored, and no control is greyed by it.

    MUTATION: raise on, or honour, `compliance_unlocked` / `compliance_bound_at`
    and this goes red."""
    from tests.helpers.legacy_run_meta import (bind_run, set_run_unlocked)
    from workflow.run_compliance import run_limits
    proj, run1, run2, d1, d2 = _two_run_project(tmp_path)
    bind_run(run2, "chromiq_tight", None)
    set_run_unlocked(run2, True)
    rl = run_limits(run2, {}, "chromiq_default")
    assert rl.set_id == "chromiq_tight" and not rl.unlocked
    dlg = _window(_settings(), d2[-1].measurement_ti3, qapp, "verification")
    try:
        dlg._saved_combo.setCurrentIndex(0)
        qapp.processEvents()
        assert dlg._set_combo.isEnabled()
        assert dlg._report_limits().set_id == "chromiq_tight"
    finally:
        dlg.close()


# --------------------------------------------------------------------------
# 5. the starting choice of "New report…"
# --------------------------------------------------------------------------
def test_new_report_starts_on_preferences_then_the_runs_own_default(
        tmp_path, qapp):
    """Knut: *"the starting choice for 'New report...' should be the the
    defaults in preferences -> reports first, then the default in the Edit
    limits for that run, if it changed to be different from the preferences
    default."* The type always comes from Preferences.

    MUTATION: ignore the run's own default in `run_limits` (answer the
    Preferences set always), or let `set_run_default_set` keep a default equal
    to Preferences' as the run's own, and this goes red."""
    from workflow.measurement_report import REPORT_TYPE_GREY
    from workflow.run_compliance import run_default_set_id, set_run_default_set
    proj, run1, run2, d1, d2 = _two_run_project(tmp_path)
    s = _settings(report_default_type=REPORT_TYPE_GREY,
                  compliance_default_set="chromiq_quick")
    dlg = _window(s, d2[-1].measurement_ti3, qapp, "verification")
    try:
        dlg._saved_combo.setCurrentIndex(0)
        qapp.processEvents()
        assert dlg._report_limits().set_id == "chromiq_quick"
        assert dlg._report_type_now() == REPORT_TYPE_GREY
    finally:
        dlg.close()
    set_run_default_set(run2, "chromiq_tight", "chromiq_quick")
    assert run_default_set_id(run2) == "chromiq_tight"
    dlg = _window(s, d2[-1].measurement_ti3, qapp, "verification")
    try:
        dlg._saved_combo.setCurrentIndex(0)
        qapp.processEvents()
        assert dlg._report_limits().set_id == "chromiq_tight"
        assert "own default" in dlg._set_combo.toolTip()
        assert dlg._report_type_now() == REPORT_TYPE_GREY
    finally:
        dlg.close()
    set_run_default_set(run2, "chromiq_quick", "chromiq_quick")
    assert run_default_set_id(run2) == "", "choosing Preferences' set kept a default"


def test_the_default_for_this_run_row_sets_the_runs_own_default(
        tmp_path, qapp, monkeypatch):
    """The run's own default is chosen in Edit limits ("Default for this
    run"), and only there; it writes the run's meta.json and nothing else.

    MUTATION: ignore `run_default_chosen` in `_open_report_limits_window`, or
    build the dialog without `run_default=`, and this goes red."""
    import ui.dialogs.thresholds_dialog as td
    from workflow.run_compliance import run_default_set_id
    proj, run1, run2, d1, d2 = _two_run_project(tmp_path)
    seen = {}

    def _exec(self):
        seen["rows"] = sorted(self._run_default_radios)
        self._run_default_radios["chromiq_tight"].setChecked(True)
        self.done(0)
        return 0

    monkeypatch.setattr(td.ThresholdsDialog, "exec", _exec)
    reports_before = {p: p.read_bytes()
                      for p in Path(proj.root).rglob("report_*.json")}
    dlg = _window(_settings(), d2[-1].measurement_ti3, qapp, "verification")
    try:
        dlg._on_open_limits()
        qapp.processEvents()
    finally:
        dlg.close()
    assert "chromiq_tight" in seen["rows"], seen
    assert run_default_set_id(run2) == "chromiq_tight"
    assert run_default_set_id(run1) == ""
    assert {p: p.read_bytes() for p in Path(proj.root).rglob(
        "report_*.json")} == reports_before


def test_the_automatic_report_binds_nothing(tmp_path, qapp):
    """The report after a measurement is that date's own report, with the
    starting choice's settings; the run's meta.json is not written (until
    K31 the first verification bound the run and the second locked it).

    MUTATION: call `ensure_bound` / bind the run from
    `TabMeasure._report_limits_for` again and this goes red."""
    from tests.test_the_measurement_report_defaults_are_knuts import (
        _a_measured_run, _measure_tab)
    s, _fm, _ctl, run, v = _a_measured_run(tmp_path)
    meta_before = run.meta_path.read_bytes() if run.meta_path.exists() else b""
    tab = _measure_tab(s, qapp)
    try:
        tab._maybe_save_measurement_report(v.measurement_ti3)
    finally:
        tab.deleteLater()
    after = run.meta_path.read_bytes() if run.meta_path.exists() else b""
    assert after == meta_before, "a measurement wrote the run's meta.json"
    assert list((v.dir / "reports").glob("report_*.json"))


# --------------------------------------------------------------------------
# 6. records an earlier ChromIQ wrote
# --------------------------------------------------------------------------
def _k23_document(run, dates):
    """A report of several dates as betas 37 to 39 wrote it: a document file
    in `verifications/reports/` and a verdict record in each date."""
    from workflow.measurement_report import (ROLE_RECORD, SCOPE_ALL_DATES,
                                             document_file, document_home,
                                             document_measurement_key,
                                             new_document_id, rewrite_report,
                                             stamp_document)
    reps = []
    for v in dates:
        p = sorted((v.dir / "reports").glob("report_*.json"))[0]
        reps.append(json.loads(p.read_text(encoding="utf-8")))
    members = [{"dir": str(v.dir), "created": str(r.get("created") or ""),
                "ti3": v.measurement_ti3.name,
                "key": document_measurement_key(
                    v.dir, str(r.get("created") or ""), v.measurement_ti3.name)}
               for v, r in zip(dates, reps)]
    doc_id = new_document_id(_T0 + timedelta(days=60))
    records = []
    for v, r in zip(dates, reps):
        r = json.loads(json.dumps(r))
        stamp_document(r, doc_id=doc_id, created="2027-02-01T10:00:00",
                       type_id="t2_full_colour_check",
                       compliance=r.get("compliance"), detail=False,
                       measurements=members, scope=SCOPE_ALL_DATES,
                       role=ROLE_RECORD)
        records.append(rewrite_report(
            v.dir / "reports" / "report_2027-02-01_10-00-00.json", r))
    body = document_file(doc_id=doc_id, created="2027-02-01T10:00:00",
                         type_id="t2_full_colour_check",
                         compliance=reps[0].get("compliance"), detail=False,
                         measurements=members, scope=SCOPE_ALL_DATES)
    home = document_home([v.dir for v in dates])
    home.mkdir(parents=True, exist_ok=True)
    doc = rewrite_report(home / "report_2027-02-01_10-00-00.json", body)
    return doc_id, doc, records


def test_old_records_are_read_only_history(tmp_path, qapp):
    """A verdict record an earlier ChromIQ wrote is never a date's own row,
    never listed, and never rewritten, moved or deleted, not even by an
    Update of the report it belongs to (which then carries every verdict
    itself).

    MUTATION: let `_one_row_per_measurement` pick a record as a date's
    newest report, or let an Update rewrite or archive the records (drop the
    `is_verdict_record` filter on `existing`), and this goes red."""
    from workflow.measurement_report import JUDGED_KEY, recorded_document
    proj, run1, run2, d1, d2 = _two_run_project(tmp_path)
    doc_id, doc, records = _k23_document(run2, d2)
    rec_bytes = {p: p.read_bytes() for p in records}
    dlg = _window(_settings(), d2[-1].measurement_ti3, qapp, "verification")
    try:
        dlg._saved_combo.setCurrentIndex(0)
        qapp.processEvents()
        for r in dlg._history:
            assert r.get("_report_file") != records[0].name or \
                str(r["_origin_dir"]) != str(records[0].parent.parent), (
                    "a date's own row is an old verdict record")
        labels = [dlg._saved_combo.itemText(i)
                  for i in range(dlg._saved_combo.count())]
        docs = dlg._saved_documents(dlg._run_ctx.run)
        assert sum(1 for d in docs if d["key"] == f"id:{doc_id}") == 1, labels
        _pick(dlg, f"id:{doc_id}", qapp)
        dlg._detail_check.setChecked(not dlg._detail_check.isChecked())
        qapp.processEvents()
        _press(dlg, qapp, "update")
    finally:
        dlg.close()
    for p, b in rec_bytes.items():
        assert p.exists() and p.read_bytes() == b, f"{p} was touched"
    block = recorded_document(json.loads(doc.read_text(encoding="utf-8")))
    assert block.get("updated")
    assert all(m.get(JUDGED_KEY) for m in block["measurements"])


# --------------------------------------------------------------------------
# 7. the help says what is true (Knut, 5801750910)
# --------------------------------------------------------------------------
RETIRED_SENTENCES = (
    "Unlock this run's limits",
    "Allow editing of thresholds after the first verification measurement",
    "Bound, and locked.",
    "The limits belong to the run, and they lock",
    "Bound (a run's limits)",
    "Locked / Unlock this run's limits",
    "locked: tick",
    "Every ticked measurement belongs to another profile run",
    "The first verification you measure binds the run",
    "A new profile run is bound to this set at its first verification",
    "the type belongs to the profile run",
    "A profile run that HAS a report type of its own keeps it",
    "The set is chosen once per profile run",
    "Each check keeps its own result in that date's reports folder",
    "Unlocking a run's limits changes no saved report",
    "The runs loaded here were set to different report types",
    "This run is judged against {set}, which was stored on the run",
)


def test_no_help_or_window_text_still_describes_the_lock_or_the_records():
    """Knut, 5801750910: *"Make sure all the changes in functionality is
    described in help icons and relevant help cards."* So no user-facing
    string (every `tr()` literal the app has) may still carry a sentence the
    K31 model made false.

    MUTATION: put any of the retired sentences back into a `tr()` literal
    (the old "Judged against" help, the glossary's "Bound" entry, the
    Preferences option) and this goes red."""
    from scripts.i18n_extract import extract_keys
    keys = extract_keys()
    hits = [(s, k[:120]) for k in keys for s in RETIRED_SENTENCES if s in k]
    assert not hits, hits


def test_the_help_says_what_the_report_model_is():
    """…and the help that replaces them says the K31 truth where a reader
    looks: the "Judged against" help, "Report shown", the glossary, the
    Preferences "Report type, default" help and the file guide.

    MUTATION: drop any of the new paragraphs and this goes red."""
    from scripts.i18n_extract import extract_keys
    keys = "\n".join(extract_keys())
    for needle in (
            "The limit set belongs to the report",
            "whichever profile run this window was opened from",
            "becomes a report of those dates",
            "unless its profile run has a default of its own",
            "Default for this run",
            "Default for new reports",
            "A report's limit set",
            "The limits belong to the report",
            "Nothing is written into the dates' own folders",
            "The type belongs to the report"):
        assert needle in keys, needle
