"""B8-246 — a report is written against ONE "Judged against" limit set.

The project's design authority, 2026-09-16, on a report of his own::

    after generating several reports for a verification run, the report
    sometimes lists in red text that several reports use different Judged
    against threshold set, and then the output results only say INFO. […]
    only report data using the same judged against threshold sets as the judge
    against setting set in the report should be used when writing the report
    text. Not mix them together in the report output.

Reproduced on screen from the packs he supplied, in a real window: opened on a
run's own profiling measurement, the Measurement Report drew seven columns
judged against five different copies of three limit sets, a "Judged against"
row naming them side by side, and this red line above them:

    Warning: these reports were not all judged against the same limit set.
    The words in one column are not comparable with the words in another
    where the limit set differs:

Telling a reader that the table they are reading cannot be read is not a
report. The document now holds one limit set; the measurements judged against
another stay loaded, stay tickable and stay on the trend over time, and the
Report Scope names each of them and says why it is not in the results.

**THE SETS ARE TOLD APART BY THEIR NUMBERS, NOT THEIR NAMES.** A run carries a
COPY of the set it was bound to, so two runs can both say "ChromIQ default
(recommended)" and be judged against different numbers; the window already
derives its own "(edited)" marker from exactly that difference. In the pack
that reproduced this, one of the seven columns was such a copy, and the red
line listed it under the same name as the column it disagreed with.
"""
from __future__ import annotations

import os
import re
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


# --------------------------------------------------------------------------
# the key: the numbers, not the name
# --------------------------------------------------------------------------
def test_two_copies_of_one_set_with_different_numbers_are_two_yardsticks():
    """MUTATION: key on `set_id` alone and this goes red."""
    from workflow.measurement_report import yardstick_key
    a = {"set_id": "chromiq_default", "set_label": "ChromIQ default",
         "thresholds": {"all_de00_avg": 2.0, "all_de00_max": 3.0}}
    b = {"set_id": "chromiq_default", "set_label": "ChromIQ default",
         "thresholds": {"all_de00_avg": 1.4, "all_de00_max": 3.0}}
    assert yardstick_key(a) != yardstick_key(b)


def test_the_same_numbers_in_a_different_order_are_one_yardstick():
    """A dict is not ordered by the user, so the key may not be either."""
    from workflow.measurement_report import yardstick_key
    a = {"set_id": "s", "thresholds": {"x": 1.0, "y": [2.0, "should"]}}
    b = {"set_id": "s", "thresholds": {"y": [2.0, "should"], "x": 1.0}}
    assert yardstick_key(a) == yardstick_key(b)


def test_a_recommendation_and_a_requirement_of_the_same_value_differ():
    """`[2.0, "should"]` and `2.0` grade the same number to different words."""
    from workflow.measurement_report import yardstick_key
    a = {"set_id": "s", "thresholds": {"x": [2.0, "should"]}}
    b = {"set_id": "s", "thresholds": {"x": 2.0}}
    assert yardstick_key(a) != yardstick_key(b)


def test_a_report_with_no_record_of_what_judged_it_has_no_key():
    """None is not a set, and a caller may not read it as "matches anything"."""
    from workflow.measurement_report import yardstick_key
    assert yardstick_key(None) is None
    assert yardstick_key({"set_id": "s"}) is None
    assert yardstick_key({"set_id": "s", "thresholds": "not a dict"}) is None


# --------------------------------------------------------------------------
# the window
# --------------------------------------------------------------------------
def _save_a_report(run, v):
    """A dated report saved exactly as a measurement saves one.

    A column with no SAVED report carries no record of what judged it, which
    is a state this fault cannot occur in: `report_scope`'s old warning and
    `_one_limit_set` alike read the record. A fixture without this step cannot
    fail, and the first cut of two of these tests could not.
    """
    from workflow.measurement_report import (build_report, save_report,
                                             stamp_verdict)
    from workflow.run_compliance import run_limits
    lim = run_limits(run, None)
    rep = build_report(v.measurement_ti3)
    stamp_verdict(rep, lim.limits, set_id=lim.set_id, set_label=lim.label_en,
                  edited=lim.edited)
    return save_report(rep, v.dir)


def _dialog(tmp_path, qapp, bind="chromiq_default"):
    from tests.test_import_measurement_module import (_cgats, _PATCHES,
                                                      _verify_env)
    s, fm, _ctl, run = _verify_env(tmp_path)
    v = run.new_verification()
    v.ensure_dir()
    v.measurement_ti3.write_text(_cgats("CTI3", _PATCHES), encoding="utf-8")
    if bind:
        from workflow.run_compliance import bind_run
        bind_run(run, bind, None)
    _save_a_report(run, v)
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    dlg = MeasurementReportDialog(s, None, initial_ti3=v.measurement_ti3)
    dlg.show()
    qapp.processEvents()
    return dlg, run, fm


def _second_run(tmp_path, fm, dlg, qapp, set_id="chromiq_tight",
                thresholds=None):
    """A second profile run, bound to *set_id*, added to the window."""
    from tests.test_import_measurement_module import _cgats, _PATCHES
    from workflow.run_compliance import bind_run
    run2 = fm.project().new_run()
    v2 = run2.new_verification()
    v2.ensure_dir()
    v2.measurement_ti3.write_text(
        _cgats("CTI3", [(r * 0.5, g, b) for (r, g, b) in _PATCHES]),
        encoding="utf-8")
    bind_run(run2, set_id, None)
    if thresholds is not None:
        meta = run2.load_meta()
        meta.compliance_thresholds = thresholds
        run2.save_meta(meta)
    _save_a_report(run2, v2)
    dlg._add_source(v2.measurement_ti3)
    qapp.processEvents()
    return run2, v2


def _plain(dlg) -> str:
    return " ".join(re.sub("<[^>]+>", " ", dlg._view.toHtml()).split())


def test_the_document_never_holds_two_limit_sets(tmp_path, qapp):
    """The rule, measured on the document the window actually renders.

    MUTATION: drop the `_one_limit_set` call from `_report_body_html`, or make
    its loop keep every run, and this goes red.
    """
    dlg, _run, fm = _dialog(tmp_path, qapp)
    try:
        _second_run(tmp_path, fm, dlg, qapp)
        assert len(dlg._runs_for_report()) == 2, (
            "this test needs two measurements loaded")
        kept, dropped = dlg._one_limit_set(dlg._runs_for_report())
        assert len(dropped) == 1, "the two sets were not separated"
        keys = {dlg._yardstick_of(r) for r in kept}
        assert len(keys) == 1, f"{len(keys)} limit sets in one document"
        # …AND THE DOCUMENT, NOT ONLY THE HELPER. A helper nothing calls is
        # not a fix, and the first cut of this test asserted only on the
        # helper: with the call removed from `_report_body_html` it stayed
        # green while the rendered page still described both measurements.
        body = _plain(dlg)
        n = re.search(r"No\. of Measurements:\s*(\d+)", body)
        assert n is not None, "the Report Scope does not count the measurements"
        assert int(n.group(1)) == len(kept), (
            f"the page describes {n.group(1)} measurements and the report is "
            f"written for {len(kept)}")
    finally:
        dlg.close()


def test_the_left_out_measurement_is_named_in_the_report_scope(tmp_path, qapp):
    """Nothing loaded may quietly vanish: the Scope says which and why.

    MUTATION: return "" from `_other_limit_sets_html` and this goes red.
    """
    dlg, _run, fm = _dialog(tmp_path, qapp)
    try:
        _second_run(tmp_path, fm, dlg, qapp)
        body = _plain(dlg)
        assert "judged against a different limit set" in body
        assert "not in the results below" in body
        # and it names the set that WAS left out, not only a count
        assert "ChromIQ tight" in body or "ChromIQ default" in body
    finally:
        dlg.close()


def test_the_old_red_warning_can_no_longer_fire_on_a_rendered_document(
        tmp_path, qapp):
    """The sentence he reported: it described a mix the document no longer has.

    MUTATION: drop the `_one_limit_set` call from `_report_body_html` and this
    goes red.
    """
    dlg, _run, fm = _dialog(tmp_path, qapp)
    try:
        _second_run(tmp_path, fm, dlg, qapp)
        body = _plain(dlg)
        assert "were not all judged against the same limit set" not in body
    finally:
        dlg.close()


def test_two_copies_of_ONE_set_are_still_separated_in_the_window(tmp_path,
                                                                 qapp):
    """The case the red line itself could not see: same name, other numbers.

    MUTATION: make `_yardstick_of` key on the set id alone and this goes red,
    because the two columns then read as one set and neither is left out.
    """
    dlg, run, fm = _dialog(tmp_path, qapp)
    try:
        from workflow.run_compliance import run_limits
        mine = run_limits(run, None).set_id
        meta = run.load_meta()
        edited = dict(meta.compliance_thresholds or {})
        assert edited, "the window's own run is not bound, so there is no copy"
        # one number moved, the set id untouched: the same NAME, another
        # yardstick
        for rid, val in list(edited.items()):
            if isinstance(val, (int, float)):
                edited[rid] = float(val) + 0.4
                break
        else:                                   # pragma: no cover — data guard
            raise AssertionError("no numeric limit in the run's own copy")
        _second_run(tmp_path, fm, dlg, qapp, set_id=mine, thresholds=edited)
        kept, dropped = dlg._one_limit_set(dlg._runs_for_report())
        assert len(dropped) == 1, (
            "two copies of one set with different numbers were read as one")
        assert len(kept) == 1
    finally:
        dlg.close()


def test_one_limit_set_everywhere_keeps_the_history_loaded(tmp_path, qapp):
    """"Keep the history and separate the sets, not delete either."

    MUTATION: filter inside `_runs_for_report` instead and this goes red.
    """
    dlg, _run, fm = _dialog(tmp_path, qapp)
    try:
        _second_run(tmp_path, fm, dlg, qapp)
        assert len(dlg._history) == 2, "a measurement was dropped from the list"
        assert len(dlg._runs_for_report()) == 2, (
            "the trend and the run list lost a measurement")
        from workflow.measurement_report import report_trend
        assert len(report_trend(dlg._runs_for_report())) == 2, (
            "the trend over time lost a point it should keep")
    finally:
        dlg.close()


def test_the_button_files_a_report_only_for_what_the_page_describes(tmp_path,
                                                                    qapp):
    """`_runs_for_document` and the body must agree about the document.

    MUTATION: drop the `_one_limit_set` call from `_runs_for_document` and this
    goes red.
    """
    dlg, _run, fm = _dialog(tmp_path, qapp)
    try:
        _second_run(tmp_path, fm, dlg, qapp)
        keys = {dlg._yardstick_of(r) for r in dlg._runs_for_document()}
        assert len(keys) == 1, (
            "the Generate button would file a report for a measurement the "
            "page does not describe")
    finally:
        dlg.close()


def test_a_single_measurement_is_never_filtered_out_of_its_own_report(
        tmp_path, qapp):
    """The everyday window: one measurement, nothing to separate."""
    dlg, _run, _fm = _dialog(tmp_path, qapp)
    try:
        runs = dlg._runs_for_report()
        kept, dropped = dlg._one_limit_set(runs)
        assert dropped == []
        assert len(kept) == len(runs) == 1
    finally:
        dlg.close()


def test_the_anchor_is_the_sheet_the_window_is_on(tmp_path, qapp):
    """Never the pulldown: a run's own profiling report is deliberately not
    recalculated when its set changes (§5), so a run bound to one set can hold
    a report judged against another, and anchoring on the pulldown would throw
    the window's own subject out of its own report.

    MUTATION: anchor on `self._window_limits()` and this goes red.
    """
    dlg, _run, fm = _dialog(tmp_path, qapp)
    try:
        _second_run(tmp_path, fm, dlg, qapp)
        kept, _dropped = dlg._one_limit_set(dlg._runs_for_report())
        subject = dlg._run_key(dlg._report)
        assert any(dlg._run_key(r) == subject for r in kept), (
            "the measurement the window is on is not in its own report")
    finally:
        dlg.close()


def test_the_pdf_is_offered_in_the_folder_of_the_run_it_describes(tmp_path,
                                                                  qapp):
    """B8-247, found in B8-246's own challenge round.

    `_report_dir` takes the common ancestor of the folders the report covers,
    and it asked "what is loaded". Once a document can be narrower than that,
    a report describing ONE run of a several-run project was offered in the
    whole project's `reports/` folder, because the common ancestor of several
    runs is the `runs` container. Driven on screen before the fix:
    `Report-Limits-Report-Types/reports`; after it,
    `Report-Limits-Report-Types/runs/run1/reports`.

    MUTATION: put `_runs_for_report` back in `_report_dir` and this goes red.
    """
    dlg, run, fm = _dialog(tmp_path, qapp)
    try:
        run2, _v2 = _second_run(tmp_path, fm, dlg, qapp)
        kept, dropped = dlg._one_limit_set(dlg._runs_for_report())
        assert len(kept) == 1 and len(dropped) == 1, "the fixture did not mix"
        where = dlg._report_dir()
        covered = Path(kept[0]["_origin_dir"])
        assert str(where).startswith(str(covered)), (
            f"the report describes {covered} and would be saved in {where}")
        assert str(run.dir) not in str(where) or str(run2.dir) not in str(where)
    finally:
        dlg.close()


# --------------------------------------------------------------------------
# B8-249: which report of a measurement is the newest
# --------------------------------------------------------------------------
def test_the_tenth_report_of_one_second_is_newer_than_the_ninth():
    """`save_report` numbers them `_2`, `_3`, … and strings stop sorting at ten.

    MUTATION: make `_report_file_order` return the name and this goes red.
    """
    from ui.dialogs.measurement_report_dialog import _report_file_order as order
    ninth = "report_2026-09-15_13-35-33_9.json"
    sixteenth = "report_2026-09-15_13-35-33_16.json"
    assert sixteenth < ninth, "the string comparison this exists for changed"
    assert order(sixteenth) > order(ninth), (
        "the ninth report of that second still counts as the newest")


def test_the_first_report_of_a_second_is_the_oldest_of_it():
    """No suffix means the first, not the last."""
    from ui.dialogs.measurement_report_dialog import _report_file_order as order
    assert order("report_2026-09-15_13-35-33.json") \
        < order("report_2026-09-15_13-35-33_2.json")


def test_a_later_second_wins_whatever_the_suffixes_are():
    from ui.dialogs.measurement_report_dialog import _report_file_order as order
    assert order("report_2026-09-15_13-35-34.json") \
        > order("report_2026-09-15_13-35-33_16.json")


def test_a_name_in_no_known_shape_never_jumps_the_queue():
    """An unreadable name is not evidence of being newer."""
    from ui.dialogs.measurement_report_dialog import _report_file_order as order
    assert order("odd.json") < order("report_2026-09-15_13-35-33.json")


def test_the_merge_keeps_the_sixteenth_report_not_the_ninth():
    """The promise `_one_row_per_measurement` makes, on the shape that broke it.

    MUTATION: put the `str(...) >= str(...)` comparison back and this goes red.
    """
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    rows = [{"_origin_dir": "/p/runs/run1", "created": "2026-09-15T13:00:00",
             "ti3": "p.ti3", "_report_file": f"report_2026-09-15_13-35-33_{n}.json",
             "compliance": {"set_id": f"set{n}", "thresholds": {"a": n}}}
            for n in range(2, 17)]
    out = MeasurementReportDialog._one_row_per_measurement(rows)
    assert len(out) == 1
    assert out[0]["_report_file"] == "report_2026-09-15_13-35-33_16.json", (
        f"the row carries {out[0]['_report_file']}")
