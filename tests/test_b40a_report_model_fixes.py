"""B40-A: five faults the beta 40 behaviour challenge found in K31 (§25 of
`docs/design/measurement_report_limits.md`).

1. With ONE profile run loaded, an edit in Edit limits' "This report" column
   was dropped at Generate: the written file carried the set's plain numbers
   and ``edited: False`` under a red line that promised the edit
   (`_sticky_limits` honoured the report's own limits only with several runs
   loaded, a pre-K31 leftover). These tests read the WRITTEN FILE.
2. An old verdict record (K23, role "record") counted as a spare report, so
   a date's last own report could be deleted, and the record then became the
   date's row. A record is never a report and never a row (§25.1, §25.6).
3. Widening a date's ONLY one-date report to several dates archived it and
   left the date with no own report, which Delete refuses (§25.6). Knut,
   #182 5806297940, "go for (a) Keep the date's own report" (§25.7): the
   one-date report stays, and the widened report is a new report of those
   dates.
4. After an old document had been loaded, a date's row kept that document's
   record or a pre-K23 copy: rows use the date's own one-date report.
5. The "Judged against" tooltip said a set carried over from an older
   ChromIQ was "chosen in Edit limits".

Every test names the mutation that turns it red; each was run red
(~/Desktop/ChromIQ-beta40-proof/challenge-A-fixes/mutations.txt).
"""
from __future__ import annotations

import json
import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest                                                  # noqa: E402
from PyQt6.QtWidgets import QApplication                       # noqa: E402

from tests.test_calibration_reports import _settings, _window  # noqa: E402
from tests.test_k31_report_model import (_date, _entry_for,     # noqa: E402
                                         _k23_document, _pick, _press,
                                         _tree, _two_run_project)


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


def _edit_this_report(monkeypatch, value=0.4):
    """Make the limits window change "This report"'s all-patch average."""
    import ui.dialogs.thresholds_dialog as td
    from workflow.compliance_sets import Limit

    def _exec(self):
        self._run_limits["all_de00_avg"] = Limit.value(value)
        self._run_dirty = True
        self.done(0)
        return 0

    monkeypatch.setattr(td.ThresholdsDialog, "exec", _exec)


def _written(before: dict, root: Path) -> "list[Path]":
    """The live report files that are new or changed since *before*."""
    after = _tree(root)
    return [root / k for k in sorted(after)
            if before.get(k) != after[k] and "/old/" not in k
            and Path(k).name.startswith("report_")]


def _avg_limit(compliance: dict) -> "tuple[float | None, bool]":
    from workflow.compliance_sets import limits_from_json
    lim = limits_from_json(compliance.get("thresholds") or {},
                           compliance.get("set_id"))
    return lim["all_de00_avg"].number, bool(compliance.get("edited"))


# --------------------------------------------------------------------------
# 1. the report's own limits reach the file, one run or several
# --------------------------------------------------------------------------
@pytest.mark.parametrize("answer", ["new", "update"])
def test_an_edit_in_this_report_is_written_with_one_run_loaded(
        tmp_path, qapp, monkeypatch, answer):
    """§25.3: the limits window opens on "This report" whether one profile
    run or many are loaded, and Generate applies it.

    MUTATION: put ``and self._several_runs()`` back on the
    `_report_own_limits` branch of `_sticky_limits` and this goes red (the
    file carries 1.5 or whatever the set says, and edited False)."""
    proj, run1, run2, d1, d2 = _two_run_project(tmp_path)
    _edit_this_report(monkeypatch)
    root = Path(proj.root)
    dlg = _window(_settings(), d2[-1].measurement_ti3, qapp, "verification")
    try:
        entry = _entry_for(dlg, d2[-1].dir)
        _pick(dlg, entry["key"], qapp)
        assert not dlg._several_runs()
        dlg._on_open_limits()
        qapp.processEvents()
        assert dlg._report_limits().limits["all_de00_avg"].number == 0.4
        before = _tree(root)
        _press(dlg, qapp, answer)
    finally:
        dlg.close()
    files = _written(before, root)
    assert len(files) == 1, files
    rep = json.loads(files[0].read_text(encoding="utf-8"))
    assert _avg_limit(rep["compliance"]) == (0.4, True), rep["compliance"]


def test_an_edit_in_this_report_is_written_with_several_runs_loaded(
        tmp_path, qapp, monkeypatch):
    """The other half, which already worked: a report across runs carries
    the edit in each measurement's judged block.

    MUTATION: drop the `_report_own_limits` branch of `_sticky_limits`
    altogether and this goes red."""
    from workflow.measurement_report import JUDGED_KEY, recorded_document
    proj, run1, run2, d1, d2 = _two_run_project(tmp_path)
    _edit_this_report(monkeypatch)
    root = Path(proj.root)
    dlg = _window(_settings(), d2[-1].measurement_ti3, qapp, "verification")
    try:
        dlg._add_source(d1[0].measurement_ti3)
        qapp.processEvents()
        dlg._saved_combo.setCurrentIndex(0)                  # New report…
        qapp.processEvents()
        dlg._select_all_btn.click()
        qapp.processEvents()
        assert dlg._several_runs()
        dlg._on_open_limits()
        qapp.processEvents()
        before = _tree(root)
        _press(dlg, qapp, "new")
    finally:
        dlg.close()
    files = _written(before, root)
    assert len(files) == 1, files
    block = recorded_document(json.loads(files[0].read_text(encoding="utf-8")))
    assert len(block["measurements"]) == 3
    for m in block["measurements"]:
        assert _avg_limit(m[JUDGED_KEY]["compliance"]) == (0.4, True), m


# --------------------------------------------------------------------------
# 2. a verdict record is never a spare and never a row
# --------------------------------------------------------------------------
def test_a_record_is_no_spare_for_the_delete_rule(tmp_path, qapp):
    """§25.6: the only saved report of a dated verification is kept. A
    verdict record in the same folder is not a second report.

    MUTATION: count every readable `report_*.json` again in
    `_saved_delete_refusal` (drop the own-report test) and this goes red."""
    proj, run1, run2, d1, d2 = _two_run_project(tmp_path)
    _doc_id, _doc, records = _k23_document(run2, d2)
    date = d2[0]
    own = [p for p in sorted((date.dir / "reports").glob("report_*.json"))
           if p not in records]
    assert len(own) == 1
    dlg = _window(_settings(), d2[-1].measurement_ti3, qapp, "verification")
    try:
        entry = _entry_for(dlg, date.dir)
        assert dlg._delete_refusal_for(entry), (
            "the date's only own report may be deleted beside a record")
    finally:
        dlg.close()
    # Guard the guard: a second OWN report is a spare.
    _date_again = __import__("tests.test_k31_report_model",
                             fromlist=["_automatic_report"])._automatic_report
    _date_again(run2, date)
    dlg = _window(_settings(), d2[-1].measurement_ti3, qapp, "verification")
    try:
        entry = _entry_for(dlg, date.dir)
        assert not dlg._delete_refusal_for(entry)
    finally:
        dlg.close()


def test_a_date_with_only_a_record_has_no_report_row(tmp_path, qapp):
    """§25.1: a verdict record is never a date's own row. A date whose own
    report is gone is a measurement with no saved report of its own, judged
    live ("(not saved)"), and the record still names its report in the list.

    MUTATION: put ``or group`` back on the fallback of
    `_one_row_per_measurement` and this goes red."""
    from workflow.measurement_report import is_verdict_record
    proj, run1, run2, d1, d2 = _two_run_project(tmp_path)
    doc_id, _doc, records = _k23_document(run2, d2)
    date = d2[0]
    for p in sorted((date.dir / "reports").glob("report_*.json")):
        if p not in records:
            p.unlink()                        # the date's own report is gone
    dlg = _window(_settings(), d2[-1].measurement_ti3, qapp, "verification")
    try:
        dlg._saved_combo.setCurrentIndex(0)                  # New report…
        qapp.processEvents()
        rows = [r for r in dlg._history
                if str(r.get("_origin_dir")) == str(date.dir)]
        assert len(rows) == 1, rows
        row = rows[0]
        assert row.get("_fresh"), "the record became the date's row"
        assert not is_verdict_record(row)
        assert dlg._recorded(row) is None
        docs = dlg._saved_documents(dlg._run_ctx.run)
        assert any(d["key"] == f"id:{doc_id}" for d in docs), (
            "the old report is no longer listed")
    finally:
        dlg.close()


# --------------------------------------------------------------------------
# 3. widening a date's only one-date report (§25.7, Knut 5806297940)
# --------------------------------------------------------------------------
def test_widening_a_dates_only_report_keeps_it_and_writes_a_new_one(
        tmp_path, qapp):
    """Knut, 5806297940: *"go for (a) Keep the date's own report."* (§25.7)
    An Update that would
    widen the ONLY own report of a date leaves that one-date file untouched
    and writes the widened report as a new report of those dates.

    MUTATION: skip `_update_would_orphan_a_date` (let the Update widen as
    §25.2 built it) and this goes red (the one-date file is archived)."""
    from workflow.measurement_report import recorded_document
    proj, run1, run2, d1, d2 = _two_run_project(tmp_path)
    first = d2[0]
    own = sorted((first.dir / "reports").glob("report_*.json"))[0]
    own_bytes = own.read_bytes()
    own_id = recorded_document(json.loads(own_bytes))["id"]
    dlg = _window(_settings(), first.measurement_ti3, qapp, "verification")
    try:
        entry = _entry_for(dlg, first.dir)
        _pick(dlg, entry["key"], qapp)
        dlg._select_all_btn.click()
        qapp.processEvents()
        _press(dlg, qapp, "update")
    finally:
        dlg.close()
    assert own.exists() and own.read_bytes() == own_bytes, (
        "the date's only one-date report was changed or archived")
    assert not (own.parent / "old").exists()
    home = sorted((run2.verifications_dir / "reports").glob("report_*.json"))
    assert len(home) == 1, home
    block = recorded_document(json.loads(home[0].read_text(encoding="utf-8")))
    assert len(block["measurements"]) == 2
    assert block["id"] != own_id, "the widened report took the one-date id"
    assert not block.get("updated")


def test_widening_a_report_the_date_has_a_spare_of_still_widens(
        tmp_path, qapp):
    """Guard the guard: when the date keeps another own report, the Update
    widens as §25.2 says (id kept, the one-date file archived).

    MUTATION: make `_update_would_orphan_a_date` answer True always and this
    goes red."""
    from tests.test_k31_report_model import _automatic_report
    from workflow.measurement_report import recorded_document
    proj, run1, run2, d1, d2 = _two_run_project(tmp_path)
    first = d2[0]
    own = sorted((first.dir / "reports").glob("report_*.json"))[0]
    doc_id = recorded_document(json.loads(own.read_text(encoding="utf-8")))["id"]
    _automatic_report(run2, first)                   # a second own report
    dlg = _window(_settings(), first.measurement_ti3, qapp, "verification")
    try:
        _pick(dlg, f"id:{doc_id}", qapp)
        dlg._select_all_btn.click()
        qapp.processEvents()
        _press(dlg, qapp, "update")
    finally:
        dlg.close()
    assert not own.exists()
    assert list((own.parent / "old").glob("*/" + own.name))
    home = sorted((run2.verifications_dir / "reports").glob("report_*.json"))
    block = recorded_document(json.loads(home[0].read_text(encoding="utf-8")))
    assert block["id"] == doc_id


# --------------------------------------------------------------------------
# 4. rows are the dates' own one-date reports
# --------------------------------------------------------------------------
def _pre_k23_copy(v, doc_id, members, name="report_2026-12-20_09-00-00.json"):
    """A report of several dates as a build before K23 wrote it: a full copy
    in each date's folder, with no role."""
    from workflow.measurement_report import (SCOPE_MULTIPLE_DATES,
                                             rewrite_report, stamp_document)
    p = sorted((v.dir / "reports").glob("report_*.json"))[0]
    r = json.loads(p.read_text(encoding="utf-8"))
    stamp_document(r, doc_id=doc_id, created="2026-12-20T09:00:00",
                   type_id="t2_full_colour_check",
                   compliance=r.get("compliance"), detail=False,
                   measurements=members, scope=SCOPE_MULTIPLE_DATES)
    return rewrite_report(v.dir / "reports" / name, r)


def test_a_pre_k23_copy_is_not_a_dates_row(tmp_path, qapp):
    """A date that holds its own report of one date and a newer pre-K23 copy
    of a report of several dates is drawn from its own report.

    MUTATION: let the fallback of `_one_row_per_measurement` take any
    non-record file (drop the one-date test) and this goes red."""
    from workflow.measurement_report import document_measurement_key
    proj, run1, run2, d1, d2 = _two_run_project(tmp_path)
    members = [{"dir": str(v.dir), "created": "", "ti3": v.measurement_ti3.name,
                "key": document_measurement_key(v.dir, "",
                                                v.measurement_ti3.name)}
               for v in d2]
    for v in d2:
        _pre_k23_copy(v, "doc_20261220_090000_abcdef", members)
    dlg = _window(_settings(), d2[-1].measurement_ti3, qapp, "verification")
    try:
        dlg._saved_combo.setCurrentIndex(0)
        qapp.processEvents()
        for r in dlg._history:
            assert r.get("_report_file") != "report_2026-12-20_09-00-00.json", (
                f"{r['_origin_dir']}'s row is a pre-K23 copy")
    finally:
        dlg.close()


def test_rows_return_to_their_own_reports_after_an_old_document(
        tmp_path, qapp):
    """d3 run.log 381: an old document (records as its members) is loaded,
    then "New report…": every date's row is its own report again.

    MUTATION: drop the re-gather from `_start_new_report` and this goes
    red (a record stays the date's row)."""
    from workflow.measurement_report import is_verdict_record
    proj, run1, run2, d1, d2 = _two_run_project(tmp_path)
    doc_id, _doc, records = _k23_document(run2, d2)
    dlg = _window(_settings(), d2[-1].measurement_ti3, qapp, "verification")
    try:
        _pick(dlg, f"id:{doc_id}", qapp)
        # The window opens on it; any re-read of the disk (an Update of it,
        # as in the tester's drive, or a Delete elsewhere) then draws its
        # members from its records.
        dlg._reload_sources()
        qapp.processEvents()
        # While the old report is loaded its records speak for it (§25.6).
        loaded = {Path(str(r.get("_origin_dir"))) / "reports"
                  / str(r.get("_report_file") or "") for r in dlg._history}
        assert set(records) <= loaded, (records, loaded)
        dlg._saved_combo.setCurrentIndex(0)                  # New report…
        qapp.processEvents()
        for r in dlg._history:
            f = Path(str(r.get("_origin_dir"))) / "reports" / str(
                r.get("_report_file") or "")
            assert f not in records, f"{f} is still a date's row"
            assert not is_verdict_record(r)
    finally:
        dlg.close()


# --------------------------------------------------------------------------
# 5. the tooltip of a set carried over from an older ChromIQ
# --------------------------------------------------------------------------
def test_a_carried_over_set_is_not_said_to_be_chosen_in_edit_limits(
        tmp_path, qapp):
    """An older ChromIQ bound the run (a copy of the set's numbers in
    meta.json). Nobody chose it in Edit limits, and the tooltip may not say
    so.

    MUTATION: give the bound case the "chosen in Edit limits" sentence
    again and this goes red."""
    from workflow.compliance_sets import effective_limits, limits_to_json
    proj, run1, run2, d1, d2 = _two_run_project(tmp_path)
    meta = run2.load_meta()
    meta.compliance_set_id = "chromiq_tight"
    meta.compliance_set_label = "ChromIQ tight"
    meta.compliance_thresholds = limits_to_json(
        effective_limits("chromiq_tight", {}))
    meta.compliance_bound_at = "2026-12-01T10:00:00"
    run2.save_meta(meta)
    dlg = _window(_settings(), d2[-1].measurement_ti3, qapp, "verification")
    try:
        dlg._saved_combo.setCurrentIndex(0)                  # New report…
        qapp.processEvents()
        tip = dlg._set_combo.toolTip()
        assert "chosen in Edit limits" not in tip, tip
        assert "earlier version of ChromIQ" in tip, tip
    finally:
        dlg.close()
