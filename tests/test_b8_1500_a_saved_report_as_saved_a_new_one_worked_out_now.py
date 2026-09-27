"""B8-1500, B8-1501, B8-1503: a saved report is shown exactly as it was saved;
a new or updated report is made entirely by the current version (Knut, #182
5857473253, as confirmed back in 5857483490).

Knut: *"Old reports should stay exactly as they were saved, without
recalculating. When updating a report or creating a new report, then the new
version of the app will recreate the whole report according to the new
standard."* And, repeated: *"when viewing a report, by selecting a report in
the Report shown pulldown, the exact data that was saved at the time it was
saved, is recreated and shown on screen, and if a pdf is created."*

The faults this pins (challenge round 3 of beta 45):

* a saved report missing a block this version writes was shown COMPLETED
  with that block from this version's working (`_the_saved_record`);
* a NEW report judged the row the window READ, which for a date an earlier
  version reported is that report's saved numbers (`_judged_live`): a history
  saved before beta 45 kept its unfiltered evenness under the filtered limits;
* a report of several dates recorded only its verdicts and read every date's
  numbers from that date's own file, whatever the file held later;
* a run an earlier ChromIQ bound kept the old evenness limits, unconverted,
  and read "(edited)" (B8-1501);
* the Report Limits note said the Custom columns do not start from the ISO
  figures, which their evenness rows now are (B8-1503).
"""
from __future__ import annotations

import json
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from tests.test_c5_a_saved_report_is_its_own_record import (  # noqa: E402
    _window)
from tests.test_k39_update_question_and_new_report import (  # noqa: E402
    _asked, _pick)


@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


#: A figure no measurement of the fixture produces, written into a saved
#: report so it can be told apart from this version's working.
_SAVED = 9.87


def _stamped_report(v):
    """The date's report that carries a verdict (the fixture writes one bare
    file and one stamped file per date)."""
    for p in sorted((v.dir / "reports").glob("report_*.json")):
        rep = json.loads(p.read_text(encoding="utf-8"))
        if "compliance" in rep:
            return p, rep
    raise AssertionError(f"no stamped report in {v.dir}")


def _mark_saved(v, *, drop_block: "str | None" = None):
    """Write the distinctive figure into the date's saved report, and drop
    *drop_block* from it if asked; the bare file goes, so the date has one."""
    for p in (v.dir / "reports").glob("report_*.json"):
        if "compliance" not in json.loads(p.read_text(encoding="utf-8")):
            p.unlink()
    p, rep = _stamped_report(v)
    rep["de00"]["avg_all"] = _SAVED
    if drop_block:
        rep.pop(drop_block, None)
    p.write_text(json.dumps(rep), encoding="utf-8")
    return p


def _row_of(dlg, v):
    rows = [r for r in dlg._runs_for_report()
            if str(r.get("_origin_dir") or "") == str(v.dir)]
    assert len(rows) == 1, [r.get("_origin_dir") for r in
                            dlg._runs_for_report()]
    return rows[0]


def _fresh_avg(v):
    from workflow.measurement_report import build_report
    return build_report(v.measurement_ti3)["de00"]["avg_all"]


# ---------------------------------------------------------------------------
# 1. a saved report is shown exactly as it was saved
# ---------------------------------------------------------------------------
def test_a_saved_report_is_shown_with_its_saved_figures(tmp_path, qapp):
    """The date's own saved report, chosen in "Report shown": its numbers are
    the saved ones, not this version's working."""
    import ui.dialogs.measurement_report_dialog as mrd
    from tests.test_a_generated_report_is_one_document import _messy_project
    s, _fm, run, vs = _messy_project(tmp_path / "p", dates=2)
    _mark_saved(vs[-1])
    dlg = mrd.MeasurementReportDialog(s, None,
                                      initial_ti3=vs[-1].measurement_ti3)
    dlg.show()
    qapp.processEvents()
    try:
        assert dlg._loaded_doc_id != mrd.NEW_REPORT_KEY
        assert _row_of(dlg, vs[-1])["de00"]["avg_all"] == _SAVED
    finally:
        dlg.close()


def test_a_block_the_saved_report_lacks_is_not_filled_in(tmp_path, qapp):
    """A saved report missing a block this version writes is shown WITHOUT
    it. It used to be completed with the block from this version's working.

    MUTATION, proved to land: `_the_saved_record` updates the rebuild with
    the saved report again instead of taking the saved report alone (red:
    the grey balance block is on the page)."""
    import ui.dialogs.measurement_report_dialog as mrd
    from tests.test_a_generated_report_is_one_document import _messy_project
    s, _fm, run, vs = _messy_project(tmp_path / "p", dates=2)
    _mark_saved(vs[-1], drop_block="grey_balance")
    dlg = mrd.MeasurementReportDialog(s, None,
                                      initial_ti3=vs[-1].measurement_ti3)
    dlg.show()
    qapp.processEvents()
    try:
        row = _row_of(dlg, vs[-1])
        assert row["de00"]["avg_all"] == _SAVED
        assert "grey_balance" not in row, (
            "a saved report was completed with a block it never held")
    finally:
        dlg.close()


# ---------------------------------------------------------------------------
# 2. a new report is made entirely by the current version
# ---------------------------------------------------------------------------
def test_a_new_report_works_every_date_out_again(tmp_path, qapp):
    """New report…: every date's figures are this version's working of its
    measurement, the saved figure of an earlier report included.

    MUTATION, proved to land: `_judged_live` judges *r* itself again (red:
    the new report shows the saved 9.87)."""
    import ui.dialogs.measurement_report_dialog as mrd
    from tests.test_a_generated_report_is_one_document import _messy_project
    s, _fm, run, vs = _messy_project(tmp_path / "p", dates=2)
    for v in vs:
        _mark_saved(v)
    dlg = mrd.MeasurementReportDialog(s, None,
                                      initial_ti3=vs[-1].measurement_ti3)
    dlg.show()
    qapp.processEvents()
    try:
        _pick(dlg, qapp, mrd.NEW_REPORT_KEY)
        for v in vs:
            row = _row_of(dlg, v)
            assert row["de00"]["avg_all"] != _SAVED, v.dir
            assert row["de00"]["avg_all"] == pytest.approx(_fresh_avg(v))
            assert not row.get(mrd.NOT_WORKED_OUT_AGAIN_KEY)
    finally:
        dlg.close()


def test_a_date_whose_measurement_is_gone_says_so(tmp_path, qapp):
    """A date whose measurement is no longer on disk cannot be worked out
    again: the new report keeps what was saved and says so, once, with the
    date (M-REPORT-NOT-WORKED-OUT, §M-PROPOSED)."""
    import ui.dialogs.measurement_report_dialog as mrd
    from workflow import measurement_messages as M
    from tests.test_a_generated_report_is_one_document import _messy_project
    s, _fm, run, vs = _messy_project(tmp_path / "p", dates=2)
    for v in vs:
        _mark_saved(v)
    dlg = mrd.MeasurementReportDialog(s, None,
                                      initial_ti3=vs[-1].measurement_ti3)
    dlg.show()
    qapp.processEvents()
    try:
        vs[0].measurement_ti3.unlink()
        _pick(dlg, qapp, mrd.NEW_REPORT_KEY)
        gone, kept = _row_of(dlg, vs[0]), _row_of(dlg, vs[-1])
        assert gone.get(mrd.NOT_WORKED_OUT_AGAIN_KEY)
        assert gone["de00"]["avg_all"] == _SAVED
        assert not kept.get(mrd.NOT_WORKED_OUT_AGAIN_KEY)
        html = mrd.MeasurementReportDialog._not_worked_out_again_html(
            dlg._runs_for_report())
        title = M.M_REPORT_NOT_WORKED_OUT.render(dates="x", n=1)[0]
        assert title in html
        assert str(gone.get("created") or "")[:10] in html
    finally:
        dlg.close()


def test_a_report_of_several_dates_records_the_figures_it_judged(
        tmp_path, qapp, monkeypatch):
    """Generate over two dates writes each date's working beside its verdict,
    and the report opened again is drawn from it: a date's own file changed
    afterwards does not change the saved report.

    MUTATION, proved to land: the snapshot branch of
    `_judged_by_the_document` is skipped (red: the reopened report shows the
    7.77 its date's file was changed to)."""
    import ui.dialogs.measurement_report_dialog as mrd
    from workflow.measurement_report import JUDGED_KEY, JUDGED_REPORT_KEY
    from tests.test_a_generated_report_is_one_document import _messy_project
    s, _fm, run, vs = _messy_project(tmp_path / "p", dates=2)
    for v in vs:
        _mark_saved(v)
    dlg = mrd.MeasurementReportDialog(s, None,
                                      initial_ti3=vs[-1].measurement_ti3)
    dlg.show()
    qapp.processEvents()
    try:
        _pick(dlg, qapp, mrd.NEW_REPORT_KEY)
        _asked(dlg, qapp, monkeypatch, "Create New") \
            if dlg._document_being_updated() else dlg._generate_btn.click()
        qapp.processEvents()
        doc_key = dlg._loaded_doc_id
        assert doc_key not in (mrd.NEW_REPORT_KEY, "")
    finally:
        dlg.close()
    docs = [p for p in run.dir.rglob("report_*.json")
            if "old" not in p.relative_to(run.dir).parts
            and (json.loads(p.read_text(encoding="utf-8")).get("document")
                 or {}).get("role") == "document"]
    assert len(docs) == 1, docs
    body = json.loads(docs[0].read_text(encoding="utf-8"))
    ms = body["document"]["measurements"]
    assert len(ms) == 2
    for m in ms:
        snap = m[JUDGED_KEY][JUDGED_REPORT_KEY]
        assert snap["de00"]["avg_all"] != _SAVED
    # a date's own file changed afterwards
    p, rep = _stamped_report(vs[0])
    rep["de00"]["avg_all"] = 7.77
    p.write_text(json.dumps(rep), encoding="utf-8")
    dlg = mrd.MeasurementReportDialog(s, None,
                                      initial_ti3=vs[-1].measurement_ti3)
    dlg.show()
    qapp.processEvents()
    try:
        _pick(dlg, qapp, doc_key)
        row = _row_of(dlg, vs[0])
        assert row["de00"]["avg_all"] == pytest.approx(_fresh_avg(vs[0]))
        assert row["de00"]["avg_all"] != 7.77
    finally:
        dlg.close()


# ---------------------------------------------------------------------------
# 3. B8-1501: a run an earlier ChromIQ bound
# ---------------------------------------------------------------------------
def _bound(tmp_path, set_id, sd, fm):
    from tests.helpers.legacy_run_meta import bind_run
    from tests.test_import_measurement_module import _verify_env
    from workflow.compliance_sets import (Limit, limits_from_json,
                                          limits_to_json)
    _s, _fm, _ctl, run = _verify_env(tmp_path)
    bind_run(run, set_id, None)
    meta = run.load_meta()
    lim = limits_from_json(meta.compliance_thresholds, set_id)
    lim["uniformity_sd"] = Limit.value(sd)
    lim["uniformity_de00_max_from_mean"] = Limit.value(fm)
    meta.compliance_thresholds = limits_to_json(lim)
    run.save_meta(meta)
    return run


@pytest.mark.parametrize("set_id,old,now", [
    ("chromiq_default", (1.5, 1.0), (1.8, 1.2)),
    ("chromiq_quick", (3.0, 2.0), (2.5, 1.7)),
    ("custom_iso_12647_7", (1.0, 1.0), (1.5, 1.0)),
    ("custom_iso_12647_8", (1.5, 1.0), (3.0, 2.0)),
    ("iso_12647_7", (0.5, 2.0), (1.5, 1.0)),
    ("iso_12647_8", (1.5, 2.0), (3.0, 2.0)),
])
def test_a_copy_of_a_shipped_evenness_limit_takes_todays(tmp_path, set_id,
                                                         old, now):
    """MUTATION, proved to land: `run_limits` does not call
    `refresh_bound_evenness` (red: the old numbers, and "(edited)")."""
    from workflow.run_compliance import run_limits
    run = _bound(tmp_path / set_id, set_id, *old)
    lim = run_limits(run, None)
    got = (lim.limits["uniformity_sd"].number,
           lim.limits["uniformity_de00_max_from_mean"].number)
    assert got == pytest.approx(now), got
    assert lim.edited is False


def test_a_limit_the_user_chose_stays_the_users(tmp_path):
    from workflow.run_compliance import run_limits
    run = _bound(tmp_path, "chromiq_default", 1.3, 1.0)
    lim = run_limits(run, None)
    assert lim.limits["uniformity_sd"].number == pytest.approx(1.3)
    assert lim.limits["uniformity_de00_max_from_mean"].number == \
        pytest.approx(1.2)
    assert lim.edited is True


# ---------------------------------------------------------------------------
# 4. B8-1503: the Report Limits note
# ---------------------------------------------------------------------------
_ACCEPTED = (
    "The two Custom columns start from limits researched from industry "
    "practice, and from ChromIQ's own numbers on the rows that research does "
    "not cover, so that every row ChromIQ can measure has a limit to be judged "
    "against. Apart from the two evenness rows, which are the standard's "
    "figures converted to ChromIQ's method (note ⁴), neither source is "
    "the published tolerances of ISO 12647-7 or ISO 12647-8: where ChromIQ "
    "ships those, they are in the read-only ISO column, and a Custom column "
    "does not start from them. Every limit here is yours to change.")


def test_the_note_carries_knuts_accepted_wording():
    """Verbatim from our #182 5857381652, item 3, which Knut accepted in
    5857473253 ("yes")."""
    import inspect
    import ui.dialogs.thresholds_dialog as td
    src = inspect.getsource(td.ThresholdsDialog._notes_text)
    flat = "".join(part for part in __import__("re").findall(
        r'"((?:[^"\\]|\\.)*)"', src)).encode().decode("unicode_escape")
    assert _ACCEPTED in flat
    assert ("Neither source is the published tolerances of ISO 12647-7 or "
            "ISO 12647-8: where") not in flat
