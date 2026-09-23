"""Second check R3, beta 39 (B8-925): an Update of a report whose own
measurements are all gone never takes the OTHER measurements the window
holds.

Measured on screen (``~/Desktop/ChromIQ-beta39-proof/second-check-R3/attack/
UPDNL2``): every verification ``.ti3`` of a run removed, the three-date
"All dates" report selected. The window listed the run's two PROFILING
sheets ticked under it; the Update counted them as what was still there,
asked M-REPORT-UPDATE-LEAVES-OUT ("the report then covers only what is still
there", which was false), and "Update without them" rewrote the verification
report (same id, "All dates") to cover the two profiling sheets.

Every test names its mutation; each was run red.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from tests.test_calibration_reports import _settings, _window    # noqa: E402
from tests.test_challenge_c_report_files import qapp, said       # noqa: E402
from tests.test_g7_reports_across_places import (               # noqa: E402
    _date, _new_report_of_everything, _press, _project, _snapshot)

assert qapp and said


def _sheet(run):
    """The run's own profiling measurement."""
    from tests.test_import_measurement_module import _cgats, _PATCHES
    ti3 = run.dir / f"{run.stem}.ti3"
    ti3.write_text(_cgats("CTI3", _PATCHES), encoding="utf-8")
    return ti3


def _documents(tmp_path):
    out = []
    for f in tmp_path.rglob("report_*.json"):
        if "old" in f.parts:
            continue
        d = json.loads(f.read_text(encoding="utf-8")).get("document")
        if d:
            out.append((f, d))
    return out


def _all_dates_report_then_gone(tmp_path, qapp):
    """P's run 1: a profiling sheet and two dated verifications, a report of
    both dates written by the window, then both dates' ``.ti3`` removed.
    Returns (run, sheet, doc id)."""
    _p, run, first = _project(tmp_path, "P")
    second = _date(run, scale=0.98)
    sheet = _sheet(run)
    dlg = _window(_settings(), second.measurement_ti3, qapp, "verification")
    try:
        dlg._ask_update_or_create_new = lambda: "new"
        _new_report_of_everything(dlg, qapp)
        _press(dlg, qapp)
    finally:
        dlg.close()
    docs = [(f, d) for f, d in _documents(tmp_path)
            if len(d.get("measurements") or []) == 2]
    assert docs, _documents(tmp_path)
    doc_id = docs[0][1]["id"]
    first.measurement_ti3.unlink()
    second.measurement_ti3.unlink()
    return run, sheet, doc_id


def _open_with_the_sheet(sheet, doc_id, qapp):
    """A window holding the profiling sheet, the gone report selected in
    "Report shown" the way a click selects it."""
    dlg = _window(_settings(), sheet, qapp, "verification")
    i = dlg._saved_combo.findData(f"id:{doc_id}")
    assert i >= 0, [dlg._saved_combo.itemText(k)
                    for k in range(dlg._saved_combo.count())]
    dlg._saved_combo.setCurrentIndex(i)
    dlg._saved_combo.activated.emit(i)
    qapp.processEvents()
    return dlg


def test_no_other_measurement_is_ticked_under_a_report_that_is_all_gone(
        tmp_path, qapp):
    """The report's two dates are gone: the profiling sheet the window holds
    is not ticked under it.

    MUTATION, proven red: drop the all-gone rule in
    `_restore_the_documents_view` (the sheet is ticked)."""
    run, sheet, doc_id = _all_dates_report_then_gone(tmp_path, qapp)
    dlg = _open_with_the_sheet(sheet, doc_id, qapp)
    try:
        assert dlg._loaded_doc_id == f"id:{doc_id}"
        here = [dlg._run_key(r) for r in dlg._history]
        assert any(str(sheet.parent) in k for k in here), here
        ticked = [k for k in here if k not in dlg._hidden_runs]
        assert ticked == [], ticked
    finally:
        dlg.close()


def test_an_update_never_takes_another_kinds_measurements(tmp_path, qapp,
                                                          said):
    """The sheet ticked by hand under the gone verification report and
    Update pressed: refused with M-REPORT-UPDATE-NOTHING-LEFT (none of the
    report's own measurements is on disk), never M-REPORT-UPDATE-LEAVES-OUT,
    and nothing on disk changes.

    MUTATION, proven red: `_update_leaves_out` deciding on every pressed
    measurement (``members = pressed``): LEAVES-OUT is asked, and "Update
    without them" rewrites the report about the profiling sheet."""
    from PyQt6.QtCore import Qt
    from workflow import measurement_messages as M
    run, sheet, doc_id = _all_dates_report_then_gone(tmp_path, qapp)
    dlg = _open_with_the_sheet(sheet, doc_id, qapp)
    try:
        for i, (kind, _si, key) in enumerate(dlg._list_rows):
            if kind == "run" and key is not None:
                dlg._profile_list.item(i).setCheckState(Qt.CheckState.Checked)
        qapp.processEvents()
        assert dlg._runs_for_document(), "nothing ticked"
        dlg._ask_update_or_create_new = lambda: "update"
        dlg._ask_leave_out = lambda title, body: (
            dlg.__dict__.setdefault("_asked", []).append(title) or True)
        before = _snapshot(tmp_path)
        _press(dlg, qapp)
        assert not dlg.__dict__.get("_asked"), dlg.__dict__.get("_asked")
        assert _snapshot(tmp_path) == before, "the Update wrote something"
    finally:
        dlg.close()
    title = M.CATALOGUE["M-REPORT-UPDATE-NOTHING-LEFT"].render(missing="")[0]
    hits = [x for _k, t, x in said if t == title]
    assert hits, said
    for _f, d in _documents(tmp_path):
        if d.get("id") == doc_id:
            assert all("verifications" in m["dir"]
                       for m in d["measurements"]), d["measurements"]


def test_update_may_cover_keeps_to_the_reports_kind():
    """The rule on its own: a verification report takes verifications, a
    profiling report profiling sheets, a calibration report calibrations,
    and a report that records nothing takes what is pressed."""
    from workflow.measurement_report import update_may_cover
    v = {"dir": "/x/P/runs/run1/verifications/2026-12-01_100000"}
    s = {"dir": "/x/P/runs/run2"}
    c = {"dir": "/x/P/cal"}
    assert update_may_cover([v], [s, v, c]) == [v]
    assert update_may_cover([s], [s, v, c]) == [s]
    assert update_may_cover([c], [s, v, c]) == [c]
    assert update_may_cover([], [s, v]) == [s, v]
    assert update_may_cover([v, s], [s, v, c]) == [s, v]


def test_an_update_with_its_own_measurements_there_still_works(tmp_path,
                                                                qapp, said):
    """The normal case: both dates on disk, a setting changed, Update: the
    report is rewritten about its two dates, and nothing is asked."""
    _p, run, first = _project(tmp_path, "P")
    second = _date(run, scale=0.98)
    dlg = _window(_settings(), second.measurement_ti3, qapp, "verification")
    try:
        dlg._ask_update_or_create_new = lambda: "new"
        _new_report_of_everything(dlg, qapp)
        _press(dlg, qapp)
        doc_id = dlg._loaded_doc_id.split(":", 1)[1]
        dlg._ask_update_or_create_new = lambda: "update"
        dlg._ask_leave_out = lambda title, body: (
            dlg.__dict__.setdefault("_asked", []).append(title) or True)
        dlg._detail_check.setChecked(not dlg._detail_check.isChecked())
        qapp.processEvents()
        _press(dlg, qapp)
        assert not dlg.__dict__.get("_asked")
    finally:
        dlg.close()
    ds = [d for _f, d in _documents(tmp_path) if d.get("id") == doc_id]
    assert ds and all(len(d["measurements"]) == 2 for d in ds), ds
    assert all(Path(m["dir"]).parent.name == "verifications"
               for d in ds for m in d["measurements"]), ds
    assert {Path(m["dir"]).name for d in ds for m in d["measurements"]} == {
        first.dir.name, second.dir.name}
