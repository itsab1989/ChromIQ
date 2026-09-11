"""A run may hold reports of several types, and the window says which it has.

**Knut, 2026-09-11:** *"A user should be allowed to print several report types
for a run, as the user may have several uses for different reports. The Report
window must thus show which type of reports have been generated … This also
makes it logical that there is a Generate Report button, so the user can choose
to generate a report that is selected."*

This revises the earlier reading of D9 for the TYPE, and only for the type. The
limit set stays bound and locked exactly as he ruled, because that is what
decides pass and fail and must not move between dates. The type is a view of
the same judged data: nothing about a verdict changes when you switch, which is
why several views of one measurement can coexist without disagreeing.
"""
from __future__ import annotations

import json
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from workflow.measurement_report import (REPORT_TYPE_FULL,  # noqa: E402
                                         REPORT_TYPE_GREY,
                                         REPORT_TYPE_RECORD,
                                         generated_report_types)


def _run_with_a_measurement(tmp_path, qapp):
    from tests.test_import_measurement_module import _cgats, _PATCHES, _verify_env
    from workflow.run_compliance import ensure_bound
    s, _fm, _ctl, run = _verify_env(tmp_path)
    v = run.new_verification()
    v.ensure_dir()
    v.measurement_ti3.write_text(_cgats("CTI3", _PATCHES), encoding="utf-8")
    ensure_bound(run, None, "chromiq_default")
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    dlg = MeasurementReportDialog(s, None, initial_ti3=v.measurement_ti3)
    dlg.show()
    qapp.processEvents()
    return dlg, run, v


def _as(dlg, run, tid):
    from workflow.run_compliance import set_run_report_type
    set_run_report_type(run, tid)
    dlg._forget_limits()
    dlg._sync_limit_controls()


def test_nothing_is_generated_until_the_button_is_pressed(tmp_path, qapp):
    """The control. A run with a measurement and no generated report must say
    so, or every count below is meaningless."""
    dlg, run, _v = _run_with_a_measurement(tmp_path, qapp)
    try:
        assert generated_report_types(run) == {}
        assert "No report has been generated" in dlg._type_blurb_full
    finally:
        dlg.close()


def test_the_button_writes_a_report_of_the_chosen_type(tmp_path, qapp,
                                                       monkeypatch):
    """MUTATION: drop the `stamp_report_type` call from `_on_generate_report`
    and this goes red."""
    dlg, run, _v = _run_with_a_measurement(tmp_path, qapp)
    monkeypatch.setattr(dlg, "_say_generated", lambda saved, failed: None)
    try:
        _as(dlg, run, REPORT_TYPE_GREY)
        assert dlg._generate_btn.isEnabled(), "the button is not offered at all"
        dlg._on_generate_report()
        qapp.processEvents()
        assert generated_report_types(run) == {REPORT_TYPE_GREY: 1}
    finally:
        dlg.close()


def test_several_types_coexist_for_one_run(tmp_path, qapp, monkeypatch):
    """THE RULING ITSELF. One measurement, three types, three reports, and the
    run holds all of them.

    MUTATION: make `generated_report_types` return only the run's current type
    and this goes red.
    """
    dlg, run, _v = _run_with_a_measurement(tmp_path, qapp)
    monkeypatch.setattr(dlg, "_say_generated", lambda saved, failed: None)
    try:
        for tid in (REPORT_TYPE_FULL, REPORT_TYPE_GREY, REPORT_TYPE_RECORD):
            _as(dlg, run, tid)
            dlg._on_generate_report()
            qapp.processEvents()
        got = generated_report_types(run)
        assert got == {REPORT_TYPE_FULL: 1, REPORT_TYPE_GREY: 1,
                       REPORT_TYPE_RECORD: 1}, got
    finally:
        dlg.close()


def test_the_window_says_which_types_the_run_has(tmp_path, qapp, monkeypatch):
    """MUTATION: drop `_generated_types_line` from the blurb and this goes
    red."""
    from core.i18n import tr
    from workflow.measurement_report import report_type_name
    dlg, run, _v = _run_with_a_measurement(tmp_path, qapp)
    monkeypatch.setattr(dlg, "_say_generated", lambda saved, failed: None)
    try:
        for tid in (REPORT_TYPE_GREY, REPORT_TYPE_RECORD):
            _as(dlg, run, tid)
            dlg._on_generate_report()
            qapp.processEvents()
        _as(dlg, run, REPORT_TYPE_FULL)
        said = dlg._type_blurb_full
        for tid in (REPORT_TYPE_GREY, REPORT_TYPE_RECORD):
            assert tr(report_type_name(tid)) in said, (tid, said)
        assert tr(report_type_name(REPORT_TYPE_FULL)) not in said.split(
            "Already generated")[-1], "a type nobody generated is listed"
    finally:
        dlg.close()


def test_two_reports_of_two_types_carry_the_SAME_verdict(tmp_path, qapp,
                                                         monkeypatch):
    """The type is a view, not a re-judgement. Two reports saved from one
    measurement must agree about what was measured and what it was judged
    against, or "nothing about a verdict changes when you switch type" is not
    true of what reaches the disk.

    MUTATION: re-judge on the generate path and this goes red.
    """
    from workflow.measurement_report import list_reports, report_type
    dlg, run, v = _run_with_a_measurement(tmp_path, qapp)
    monkeypatch.setattr(dlg, "_say_generated", lambda saved, failed: None)
    try:
        for tid in (REPORT_TYPE_FULL, REPORT_TYPE_RECORD):
            _as(dlg, run, tid)
            dlg._on_generate_report()
            qapp.processEvents()
        docs = [json.loads(p.read_text(encoding="utf-8"))
                for p in list_reports(v.dir)]
        assert len(docs) == 2, f"{len(docs)} reports"
        assert {report_type(d) for d in docs} == {REPORT_TYPE_FULL,
                                                  REPORT_TYPE_RECORD}
        a, b = docs
        assert a["verdict"]["overall"] == b["verdict"]["overall"]
        assert a["verdict"]["rows"] == b["verdict"]["rows"]
        assert a.get("compliance") == b.get("compliance")
        assert a.get("de00") == b.get("de00"), "the measurement itself moved"
    finally:
        dlg.close()


def test_the_saved_report_carries_no_window_bookkeeping(tmp_path, qapp,
                                                        monkeypatch):
    """The window hangs its own keys on a report to know where it came from.
    Those are not part of a report and must not reach the file.

    MUTATION: stop stripping the leading-underscore keys and this goes red.
    """
    from workflow.measurement_report import list_reports
    dlg, run, v = _run_with_a_measurement(tmp_path, qapp)
    monkeypatch.setattr(dlg, "_say_generated", lambda saved, failed: None)
    try:
        _as(dlg, run, REPORT_TYPE_FULL)
        assert any(k.startswith("_") for k in dlg._runs_for_report()[0]), \
            "the window hangs no private keys, so this proves nothing"
        dlg._on_generate_report()
        qapp.processEvents()
        doc = json.loads(list_reports(v.dir)[0].read_text(encoding="utf-8"))
        leaked = [k for k in doc if k.startswith("_")]
        assert not leaked, f"the window's own keys reached the file: {leaked}"
        assert doc.get("schema") == 7
    finally:
        dlg.close()


def test_the_button_is_not_offered_where_it_has_nowhere_to_write(tmp_path,
                                                                 qapp):
    """A measurement in no project has no run to keep a report for (CH-14).

    MUTATION: enable the button unconditionally and this goes red.
    """
    from tests.test_import_measurement_module import _cgats, _PATCHES, _verify_env
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    s, _fm, _ctl, _run = _verify_env(tmp_path)
    loose = tmp_path / "downloads" / "loose.ti3"
    loose.parent.mkdir(parents=True, exist_ok=True)
    loose.write_text(_cgats("CTI3", _PATCHES), encoding="utf-8")
    dlg = MeasurementReportDialog(s, None, initial_ti3=loose)
    dlg.show()
    qapp.processEvents()
    try:
        assert dlg._run_ctx is None
        assert not dlg._generate_btn.isEnabled()
    finally:
        dlg.close()


def test_three_reports_in_one_second_are_three_files(tmp_path):
    """FOUND BY THE TEST FOR KNUT'S OWN RULING, and it is what makes the
    ruling workable.

    The filename is a timestamp to the second, which was fine while the only
    way a report arrived was a measurement. With a Generate report button a
    user keeps three types of one measurement in the time it takes to click
    three times, and all three named one file: the run ended with one report
    where he asked for several.

    MUTATION: drop the suffix loop from `save_report` and this goes red.
    """
    from workflow.measurement_report import REPORT_SCHEMA, list_reports, save_report
    run_dir = tmp_path / "runs" / "run1"
    run_dir.mkdir(parents=True)
    paths = [save_report({"schema": REPORT_SCHEMA, "n": i}, run_dir)
             for i in range(3)]
    assert len({p.name for p in paths}) == 3, [p.name for p in paths]
    assert len(list_reports(run_dir)) == 3
    # …and the date a person reads is still at the front of every one
    for p in paths:
        assert p.name.startswith("report_20")


def test_which_types_exist_is_the_half_that_survives_elision(tmp_path, qapp,
                                                             monkeypatch):
    """PHOTOGRAPHED ON SCREEN: the line was "…this is the report you know. ·
    Already generate…", and what the ellipsis ate was precisely the thing Knut
    asked the window to show.

    Both sentences share one elided line, so the order decides which half a
    user reads. What a type is FOR has another home: the pulldown's own entries
    and the help button beside it. What a run already holds has none.

    MUTATION: put the blurb first again and this goes red.
    """
    from core.i18n import tr
    from workflow.measurement_report import report_type_name
    dlg, run, _v = _run_with_a_measurement(tmp_path, qapp)
    monkeypatch.setattr(dlg, "_say_generated", lambda saved, failed: None)
    try:
        _as(dlg, run, REPORT_TYPE_GREY)
        dlg._on_generate_report()
        qapp.processEvents()
        _as(dlg, run, REPORT_TYPE_FULL)
        line = dlg._type_blurb_full
        blurb = dlg._type_blurb_for(REPORT_TYPE_FULL)
        named = tr(report_type_name(REPORT_TYPE_GREY))
        assert named in line and blurb in line, line
        assert line.index(named) < line.index(blurb), (
            "the generated list is after the blurb, so elision eats it first")
        # …and the blurb is still reachable, on the control it describes
        assert dlg._type_combo.toolTip() == blurb
    finally:
        dlg.close()
