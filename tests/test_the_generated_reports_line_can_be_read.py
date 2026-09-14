"""The list of reports a run has produced must be readable, not elided away.

Knut, 2026-09-13::

    To the right of the help icon for report type a greyed out text (barely
    visible) says something about "Already generated for this run". It is not
    clear what is communicated, and the end of the text is cut off with a "..."
    at the end. All generated reports should be listed clearly and visible,
    even if it is a list of 6 report types. This might require a taller text
    area. If limited space, this could be handled with one-line text that opens
    for more detailed information.

**THE TALLER AREA IS THE ONE THING THAT CANNOT BE DONE HERE**, and the comment
beside the widget says why: a word-wrapped label of its own pushed this
window's bottom off an 800 px screen twice, because a wrapped label's minimum
height is computed before the window has been given its width. So it is his
second option.

Two changes. The line carries the LIST and nothing else: an earlier round had
already moved the list in front of the type's description, but the two still
shared one elided line, so on any narrow window the description pushed the list
out again. What a type is for has two other homes (the pulldown's entries and
its tooltip); what a run already holds had none. And when the list still will
not fit, the line grows a "show all" link that opens the whole thing, one type
per line.
"""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest                                              # noqa: E402


def _dialog_with(tmp_path, qapp, type_ids):
    """A run holding a saved report of each type in *type_ids*."""
    from tests.test_import_measurement_module import _cgats, _PATCHES, _verify_env
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    from workflow.measurement_report import (build_report, save_report,
                                             set_report_type, stamp_verdict)
    from workflow.run_compliance import ensure_bound
    s, _fm, _ctl, run = _verify_env(tmp_path)
    v = run.new_verification()
    v.ensure_dir()
    v.measurement_ti3.write_text(_cgats("CTI3", _PATCHES), encoding="utf-8")
    lim = ensure_bound(run, None, "chromiq_default")
    for tid in type_ids:
        rep = build_report(str(v.measurement_ti3))
        stamp_verdict(rep, lim.limits, set_id=lim.set_id, set_label=lim.set_label)
        set_report_type(rep, tid)
        save_report(rep, v.dir)
    dlg = MeasurementReportDialog(s, None, initial_ti3=v.measurement_ti3)
    dlg.show()
    qapp.processEvents()
    return dlg


def test_the_line_carries_the_list_and_not_the_type_description(tmp_path, qapp):
    """MUTATION: join the description back on and this goes red."""
    from workflow.measurement_report import REPORT_TYPE_FULL
    dlg = _dialog_with(tmp_path, qapp, [REPORT_TYPE_FULL])
    try:
        text = dlg._type_blurb.text()
        assert "Already generated" in text, text
        # The description of the chosen type belongs to the pulldown, not here.
        blurb = dlg._type_blurb_for(dlg._type_combo.currentData())
        assert blurb, "this fixture has no description to be crowded out by"
        assert blurb[:40] not in text, (
            "the type's description is back on the line, so it can push the "
            "list off the end again: " + text)
        assert blurb[:40] in dlg._type_combo.toolTip(), (
            "the description lost its remaining home")
    finally:
        dlg.close()


def test_a_short_list_needs_no_link(tmp_path, qapp):
    from workflow.measurement_report import REPORT_TYPE_FULL
    dlg = _dialog_with(tmp_path, qapp, [REPORT_TYPE_FULL])
    try:
        assert "#generated" not in dlg._type_blurb.text()
        assert dlg._generated_full.count("\n") == 0
    finally:
        dlg.close()


def test_a_list_too_long_for_the_line_opens_in_full(tmp_path, qapp):
    """His six-types case. MUTATION: drop the link and this goes red."""
    from workflow.measurement_report import (REPORT_TYPE_FULL, REPORT_TYPE_GREY,
                                             REPORT_TYPE_RECORD,
                                             REPORT_TYPE_SUMMARY)
    dlg = _dialog_with(tmp_path, qapp, [REPORT_TYPE_FULL, REPORT_TYPE_GREY,
                                        REPORT_TYPE_RECORD, REPORT_TYPE_SUMMARY])
    try:
        dlg.resize(700, dlg.height())          # a window too narrow for four
        dlg._sync_limit_controls()
        qapp.processEvents()
        text = dlg._type_blurb.text()
        assert "#generated" in text, (
            "the list is cut and there is no way to read the rest: " + text)
        detail = dlg._generated_full
        assert len(detail.splitlines()) == 4, detail
        # Every type is in the long form, whatever the line could show.
        for word in ("Colour summary", "Full colour check",
                     "Grey and tone check", "Printing record"):
            assert word in detail, f"{word} missing from the full list"
    finally:
        dlg.close()


def test_the_link_opens_a_window_naming_every_type(tmp_path, qapp, monkeypatch):
    from workflow.measurement_report import (REPORT_TYPE_FULL, REPORT_TYPE_GREY,
                                             REPORT_TYPE_RECORD)
    import ui.dialogs.measurement_report_dialog as M
    seen = {}
    monkeypatch.setattr("ui.warning_sign.inform",
                        lambda parent, title, text: seen.update(title=title,
                                                                text=text))
    dlg = _dialog_with(tmp_path, qapp, [REPORT_TYPE_FULL, REPORT_TYPE_GREY,
                                        REPORT_TYPE_RECORD])
    try:
        dlg._show_generated_reports("#generated")
        assert seen.get("text"), "the link opened nothing"
        assert len(seen["text"].splitlines()) == 3, seen["text"]
    finally:
        dlg.close()


def test_the_tooltip_is_the_whole_list(tmp_path, qapp):
    """A tooltip is not a substitute for the link, but it must not lie."""
    from workflow.measurement_report import REPORT_TYPE_FULL, REPORT_TYPE_GREY
    dlg = _dialog_with(tmp_path, qapp, [REPORT_TYPE_FULL, REPORT_TYPE_GREY])
    try:
        assert dlg._type_blurb.toolTip() == dlg._generated_full
        assert len(dlg._generated_full.splitlines()) == 2
    finally:
        dlg.close()


def test_a_run_with_nothing_generated_still_says_so(tmp_path, qapp):
    dlg = _dialog_with(tmp_path, qapp, [])
    try:
        assert "No report has been generated" in dlg._type_blurb.text()
        assert dlg._generated_full == ""
        assert "#generated" not in dlg._type_blurb.text()
    finally:
        dlg.close()
