"""B8-1550 and B8-1551: two ways the saved-and-new rule of B8-1500 was broken
(beta 45 challenge round 4, territory A; Knut, #182 5857473253).

* **B8-1550.** A saved report of a raw-printed sheet showed a "Change since
  the previous raw check" worked out when the window opened, not the one its
  file holds: `_load_history` ended with `annotate_raw_drift`, which wrote
  the figure of now over every row. With the earlier date gone, the saved
  report said "it is the baseline" while its file said "average 0.60".
* **B8-1551.** A new report said a date's measurement is "no longer on disk"
  when ChromIQ had archived it into an ``old/<when>/`` folder itself.
"""
from __future__ import annotations

import json
import os
import shutil

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from tests.test_k39_update_question_and_new_report import _pick  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


#: A change figure no pair of the fixture's measurements produces, written
#: into a saved report so it can be told from this version's working.
_SAVED_DRIFT = {"avg": 7.77, "max": 8.88, "n": 3, "prev": "2001-01-01T00:00:00"}


def _raw_project(tmp_path, dates=2):
    """`_messy_project` with every dated sheet printed RAW, so each report is a
    raw check that carries a change figure."""
    from tests.test_a_generated_report_is_one_document import _messy_project
    from workflow.measurement_report import (build_report, save_report,
                                             stamp_verdict)
    from workflow.run_compliance import run_limits
    s, fm, run, vs = _messy_project(tmp_path, dates=dates)
    lim = run_limits(run, None)
    for v in vs:
        ti3 = v.measurement_ti3
        (ti3.parent / f"{ti3.stem}.print.json").write_text(
            json.dumps({"colour": "raw", "intent": "", "route": "test"}),
            encoding="utf-8")
        for p in (v.dir / "reports").glob("report_*.json"):
            p.unlink()
        rep = build_report(ti3)
        stamp_verdict(rep, lim.limits, set_id=lim.set_id,
                      set_label=lim.label_en, edited=lim.edited)
        save_report(rep, v.dir)
    return s, run, vs


def _saved_report(v):
    return next((v.dir / "reports").glob("report_*.json"))


def _saved(v):
    """The date's saved report, as a dict."""
    return json.loads(_saved_report(v).read_text(encoding="utf-8"))


def _row_of(dlg, v, rows=None):
    rows = [r for r in (rows if rows is not None else dlg._runs_for_report())
            if str(r.get("_origin_dir") or "") == str(v.dir)]
    assert len(rows) == 1
    return rows[0]


def _open(s, ti3, qapp):
    import ui.dialogs.measurement_report_dialog as mrd
    dlg = mrd.MeasurementReportDialog(s, None, initial_ti3=ti3)
    dlg.show()
    qapp.processEvents()
    return dlg


# ---------------------------------------------------------------------------
# B8-1550
# ---------------------------------------------------------------------------
def test_the_fixture_is_a_raw_check(tmp_path):
    from workflow.measurement_report import build_report, is_drift_check
    _s, _run, vs = _raw_project(tmp_path / "p")
    assert is_drift_check(build_report(vs[-1].measurement_ti3))


def test_a_saved_report_shows_the_change_figure_its_file_holds(tmp_path,
                                                                qapp):
    """The saved report of the last date is shown with the change figure it
    was saved with, whatever the measurements on disk say now.

    MUTATION, proved to land: the saved figure is not put back after
    `annotate_raw_drift` (red: the row reads this version's figure)."""
    s, _run, vs = _raw_project(tmp_path / "p")
    p = _saved_report(vs[-1])
    rep = json.loads(p.read_text(encoding="utf-8"))
    rep["raw_drift"] = dict(_SAVED_DRIFT)
    p.write_text(json.dumps(rep), encoding="utf-8")
    dlg = _open(s, vs[-1].measurement_ti3, qapp)
    try:
        assert _row_of(dlg, vs[-1]).get("raw_drift") == _SAVED_DRIFT
        page = dlg._run_detail_html(_row_of(dlg, vs[-1]))
        assert "7.77" in page and "8.88" in page
    finally:
        dlg.close()


def test_a_saved_report_that_held_no_figure_is_not_given_one(tmp_path,
                                                            qapp):
    """A report saved before the change figure existed (beta 43) is shown
    without one: it says the sheet was printed raw and nothing it never
    held."""
    from workflow import measurement_messages as M
    s, _run, vs = _raw_project(tmp_path / "p")
    p = _saved_report(vs[-1])
    rep = json.loads(p.read_text(encoding="utf-8"))
    rep.pop("raw_drift", None)
    p.write_text(json.dumps(rep), encoding="utf-8")
    dlg = _open(s, vs[-1].measurement_ti3, qapp)
    try:
        row = _row_of(dlg, vs[-1])
        assert "raw_drift" not in row
        assert M.M_REPORT_RAW_SHEET.render()[1] in (
            dlg._run_detail_html(row).replace("&#x27;", "'"))
    finally:
        dlg.close()


def test_a_new_report_works_the_change_out_now(tmp_path, qapp):
    """A NEW report of the same dates carries this version's change figure,
    worked out from the measurements on disk, not the saved one.

    MUTATION, proved to land: `_worked_out_again_from_disk` copies the row's
    ``raw_drift`` again (red: the new report reads the saved 7.77)."""
    import ui.dialogs.measurement_report_dialog as mrd
    s, _run, vs = _raw_project(tmp_path / "p")
    p = _saved_report(vs[-1])
    rep = json.loads(p.read_text(encoding="utf-8"))
    rep["raw_drift"] = dict(_SAVED_DRIFT)
    p.write_text(json.dumps(rep), encoding="utf-8")
    dlg = _open(s, vs[-1].measurement_ti3, qapp)
    try:
        _pick(dlg, qapp, mrd.NEW_REPORT_KEY)
        row = _row_of(dlg, vs[-1])
        assert row.get("raw_drift") and row["raw_drift"] != _SAVED_DRIFT
        # both dates hold the same readings, so the change of now is nil
        assert row["raw_drift"].get("avg") == pytest.approx(0.0, abs=0.01)
    finally:
        dlg.close()


def test_the_earlier_date_leaving_does_not_change_a_saved_report(tmp_path,
                                                                qapp):
    """The challenge's own steps: the earlier date leaves the run, and the
    saved report of the later one still reads its saved change."""
    s, run, vs = _raw_project(tmp_path / "p")
    p = _saved_report(vs[-1])
    rep = json.loads(p.read_text(encoding="utf-8"))
    rep["raw_drift"] = dict(_SAVED_DRIFT)
    p.write_text(json.dumps(rep), encoding="utf-8")
    shutil.move(str(vs[0].dir), str(tmp_path / "moved-aside"))
    dlg = _open(s, vs[-1].measurement_ti3, qapp)
    try:
        assert _row_of(dlg, vs[-1]).get("raw_drift") == _SAVED_DRIFT
    finally:
        dlg.close()


# ---------------------------------------------------------------------------
# B8-1551
# ---------------------------------------------------------------------------
def _archive(v, where: str):
    """Move the date's measurement where ChromIQ archives one it measures
    over, keeping its time (its stamp), and return the archived path."""
    src = v.measurement_ti3
    if where == "beside":            # MeasurementSession.begin
        dest = v.dir / "old" / "2030-01-01_000000"
    elif where == "run":             # the demo pack's own place
        dest = v.dir.parent.parent / "old" / v.dir.name
    else:                            # a verification Replace
        dest = v.dir.parent / "old" / "2030-01-01_000000"
    dest.mkdir(parents=True, exist_ok=True)
    target = dest / src.name
    shutil.move(str(src), str(target))
    return target


@pytest.mark.parametrize("where", ["beside", "run", "verifications"])
def test_a_new_report_uses_the_measurement_chromiq_archived(tmp_path, qapp,
                                                            where):
    """The first date's measurement is archived: the new report works it out
    from the archive and does not say it is gone.

    MUTATION, proved to land: `_worked_out_again_from_disk` does not ask
    `_archived_measurement_for` (red: the row is marked not worked out)."""
    import ui.dialogs.measurement_report_dialog as mrd
    from workflow.measurement_report import build_report
    from tests.test_a_generated_report_is_one_document import _messy_project
    s, _fm, _run, vs = _messy_project(tmp_path / "p", dates=2)
    want = build_report(vs[0].measurement_ti3)["de00"]["avg_all"]
    dlg = _open(s, vs[-1].measurement_ti3, qapp)
    try:
        arch = _archive(vs[0], where)
        _pick(dlg, qapp, mrd.NEW_REPORT_KEY)
        row = _row_of(dlg, vs[0])
        assert not row.get(mrd.NOT_WORKED_OUT_AGAIN_KEY), arch
        assert row.get(mrd.WORKED_OUT_NOW_KEY)
        assert row["de00"]["avg_all"] == pytest.approx(want)
        assert row.get("sheet_kind") == "verification"
    finally:
        dlg.close()


def test_a_measurement_truly_gone_still_says_so(tmp_path, qapp):
    import ui.dialogs.measurement_report_dialog as mrd
    from tests.test_a_generated_report_is_one_document import _messy_project
    s, _fm, _run, vs = _messy_project(tmp_path / "p", dates=2)
    dlg = _open(s, vs[-1].measurement_ti3, qapp)
    try:
        vs[0].measurement_ti3.unlink()
        _pick(dlg, qapp, mrd.NEW_REPORT_KEY)
        assert _row_of(dlg, vs[0]).get(mrd.NOT_WORKED_OUT_AGAIN_KEY)
    finally:
        dlg.close()


def _bump_first_device_value(path):
    """Change one patch's RGB_R in *path*, keeping the file's time."""
    st = path.stat()
    lines = path.read_text(encoding="utf-8").splitlines()
    fmt_at = next(i for i, ln in enumerate(lines)
                  if ln.strip() == "BEGIN_DATA_FORMAT")
    fields = lines[fmt_at + 1].split()
    col = fields.index("RGB_R")
    data_at = next(i for i, ln in enumerate(lines) if ln.strip() == "BEGIN_DATA")
    vals = lines[data_at + 1].split()
    vals[col] = f"{(float(vals[col]) + 37.0) % 100.0:.4f}"
    lines[data_at + 1] = " ".join(vals)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    os.utime(path, (st.st_atime, st.st_mtime))


def test_an_archived_copy_its_chart_no_longer_matches_is_refused(tmp_path,
                                                                 qapp):
    """An archive whose patches no longer hold what the chart there asks for
    (the chart was generated again since) is not worked out against that
    chart: the report keeps what was saved and says so."""
    import ui.dialogs.measurement_report_dialog as mrd
    from tests.test_a_generated_report_is_one_document import _messy_project
    s, _fm, _run, vs = _messy_project(tmp_path / "p", dates=2)
    dlg = _open(s, vs[-1].measurement_ti3, qapp)
    try:
        arch = _archive(vs[0], "beside")
        _bump_first_device_value(arch)
        assert mrd.MeasurementReportDialog._archived_measurement_for(
            _saved(vs[0]), vs[0].dir, arch.name) is None
        _pick(dlg, qapp, mrd.NEW_REPORT_KEY)
        assert _row_of(dlg, vs[0]).get(mrd.NOT_WORKED_OUT_AGAIN_KEY)
    finally:
        dlg.close()


def test_an_archive_of_another_measurement_is_not_taken(tmp_path, qapp):
    """An archive whose stamp is not the report's is another measurement."""
    import ui.dialogs.measurement_report_dialog as mrd
    from tests.test_a_generated_report_is_one_document import _messy_project
    s, _fm, _run, vs = _messy_project(tmp_path / "p", dates=2)
    dlg = _open(s, vs[-1].measurement_ti3, qapp)
    try:
        arch = _archive(vs[0], "beside")
        assert mrd.MeasurementReportDialog._archived_measurement_for(
            _saved(vs[0]), vs[0].dir, arch.name) == arch
        os.utime(arch, (1.0e9, 1.0e9))
        assert mrd.MeasurementReportDialog._archived_measurement_for(
            _saved(vs[0]), vs[0].dir, arch.name) is None
    finally:
        dlg.close()


def test_build_report_at_reads_the_file_and_looks_up_at_the_place(tmp_path):
    """`build_report(..., at=)`: the readings and the stamp from the archive,
    the chart and the sheet kind from where it was measured."""
    from workflow.measurement_report import build_report, created_stamp_for
    from tests.test_a_generated_report_is_one_document import _messy_project
    _s, _fm, _run, vs = _messy_project(tmp_path / "p", dates=2)
    here = build_report(vs[0].measurement_ti3)
    stamp = created_stamp_for(vs[0].measurement_ti3)
    arch = _archive(vs[0], "run")
    at = build_report(arch, at=vs[0].dir / arch.name)
    assert at["sheet_kind"] == "verification" == here["sheet_kind"]
    assert at["created"] == stamp
    assert at["reference_source"] == here["reference_source"]
    assert at["de00"]["avg_all"] == pytest.approx(here["de00"]["avg_all"])
