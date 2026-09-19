"""Adversary round 27 — three faults of the Measurement Report window.

Every one of them was found by DRIVING the shipped beta-22 window in a real
window on the demo pack, and every guard here goes through the same door the
user's hand goes through: the dialog is constructed on a real project and read
as it stands, with no helper called on its behalf.

**R27-F1 — a help text that promised a state the box does not start in.** The
ⓘ beside *Show detailed data for each run* ended *"which is why it starts
unticked"*. P.3 of `docs/design/measurement_report_limits.md` made both tick
boxes default ON and `core/settings.py` has carried
`report_default_show_details: True` ever since, so on a fresh settings file —
which is every new installation — the box opens TICKED under a sentence saying
it does not.

**R27-F2 — the document block was the next R25-F1.** `report_object` made the
TOP level of a saved report safe against `[]`, `"x"` and `5`; the `document`
block one level down was read as though its fields had the shapes this build
writes. Driven in a real window on `Report-Limits-Report-Types`, one report
file edited per case: `measurements` as a string, as a dict, as a number, as a
list of strings, and `compliance` as a string each took the WHOLE window down
*before it appeared* — the exception is raised inside
`MeasurementReportDialog(...)`, so there is no window to close and no message
to read.

**R27-F3 — the window named one report and drew another.** Driven with default
Preferences on `Report-Limits-Report-Types/run1`, with no user action at all:
*Report shown* read "2026-11-02 10:00 · **Printing record (not graded)** ·
ChromIQ default (recommended)", *Report type* read "**Colour summary (one
page)**", the page's own head line agreed with the type pulldown, and the red
"the settings have changed" line was down — so the window said nothing was out
of step. Clicking the entry the pulldown was ALREADY on changed both. Same
entry, two documents. P.10 is the rule: *"Opening the window selects the latest
report created, with the settings it was made with"*, and K.5 says what those
settings are for a report that records none of its own.
"""
from __future__ import annotations

import json
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest                                                  # noqa: E402


# --------------------------------------------------------------------------
# the fixture: a real project, a real run, real report FILES
# --------------------------------------------------------------------------
def _run_with_three_types(tmp_path):
    """A bound run with one dated verification holding three saved reports.

    The shape of `Report-Limits-Report-Types/run1`, which is where all three
    faults were driven: the newest file of the measurement is a **Printing
    record**, and the run itself is set to **Colour summary**, so what the run
    answers and what the newest file says are two different documents. None of
    the three carries a document block, because that is how every report
    already on a user's disk was written.
    """
    from tests.test_import_measurement_module import (_cgats, _PATCHES,
                                                      _verify_env)
    from workflow.measurement_report import (REPORT_TYPE_RECORD,
                                             REPORT_TYPE_SUMMARY, build_report,
                                             save_report, set_report_type,
                                             stamp_verdict)
    from workflow.run_compliance import (bind_run, run_limits,
                                         set_run_report_type)
    s, fm, _ctl, run = _verify_env(tmp_path)
    bind_run(run, "chromiq_default", None)
    lim = run_limits(run, None)
    v = run.new_verification()
    v.ensure_dir()
    v.measurement_ti3.write_text(_cgats("CTI3", _PATCHES), encoding="utf-8")
    for tid in ("t1_colour_summary", "t2_full_colour_check",
                REPORT_TYPE_RECORD):
        rep = build_report(v.measurement_ti3)
        stamp_verdict(rep, lim.limits, set_id=lim.set_id,
                      set_label=lim.label_en, edited=lim.edited)
        set_report_type(rep, tid)
        save_report(rep, v.dir)
    # THE RUN DISAGREES WITH ITS OWN NEWEST FILE, which is the state the fault
    # needs and an ordinary one: a run may hold reports of several types
    # (Knut, 2026-09-11) and its own choice is only the last one made in the
    # pulldown.
    set_run_report_type(run, REPORT_TYPE_SUMMARY)
    return s, fm, run, v


def _dialog(s, ti3, qapp):
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    dlg = MeasurementReportDialog(s, None, initial_ti3=ti3)
    dlg.show()
    qapp.processEvents()
    return dlg


def _head_line(dlg) -> str:
    """The page's own "Report type: … · Judged against: …" line."""
    for line in dlg._view.toPlainText().splitlines():
        if line.strip().startswith("Report type:"):
            return line.strip()
    return ""


# --------------------------------------------------------------------------
# R27-F3 — the window names one report and draws another
# --------------------------------------------------------------------------
def test_the_window_opens_drawing_the_report_its_pulldown_names(tmp_path, qapp):
    """No user action: the entry, the type pulldown and the page agree.

    MUTATION: in `_adopt_visible_document`, put back

        self._loaded_doc = entry["doc"]

    and this goes red — the entry says "Printing record (not graded)" and both
    the pulldown and the page's head line say "Colour summary (one page)".
    """
    from workflow.measurement_report import report_type_name
    s, _fm, _run, v = _run_with_three_types(tmp_path)
    dlg = _dialog(s, v.measurement_ti3, qapp)
    try:
        named = dlg._saved_combo.currentText()
        assert named and named != "New report…", named
        # what the ENTRY says this document is
        record = report_type_name("t4_printing_record")
        assert record in named, named
        # …and the two places that draw it
        assert dlg._type_combo.currentText() == record, (
            dlg._type_combo.currentText(), named)
        assert record in _head_line(dlg), (_head_line(dlg), named)
        # …and the window is not claiming that anything is out of step
        assert not dlg._stale_label.isVisible()
    finally:
        dlg.close()


def test_clicking_the_entry_the_window_opened_on_changes_no_type(tmp_path, qapp):
    """The other half of R27-F3: the open and the click give one answer.

    The fault was visible as a CHANGE — clicking the entry the pulldown was
    already on moved the type pulldown and redrew the page. One door, one
    answer, so clicking it now moves nothing.

    MUTATION: put `self._loaded_doc = entry["doc"]` back in
    `_adopt_visible_document` and this goes red: the type before the click is
    "Colour summary (one page)" and after it "Printing record (not graded)".
    """
    s, _fm, _run, v = _run_with_three_types(tmp_path)
    dlg = _dialog(s, v.measurement_ti3, qapp)
    try:
        before = (dlg._type_combo.currentText(), _head_line(dlg))
        dlg._on_saved_picked_again(dlg._saved_combo.currentIndex())
        qapp.processEvents()
        after = (dlg._type_combo.currentText(), _head_line(dlg))
        assert before == after, (before, after)
    finally:
        dlg.close()


# --------------------------------------------------------------------------
# R27-F2 — a document block the reader does not expect
# --------------------------------------------------------------------------
#: Every one of these took the window down at CONSTRUCTION in beta 22.
_BAD_BLOCKS = {
    "measurements-is-a-string": {"measurements": "2026-11-02"},
    "measurements-is-a-dict": {"measurements": {"a": 1}},
    "measurements-is-a-number": {"measurements": 3},
    "measurement-entry-is-a-string": {"measurements": ["a", "b"]},
    "compliance-is-a-string": {"compliance": "chromiq_tight"},
    "compliance-is-a-list": {"compliance": []},
    "type-is-a-list": {"type": ["t2_full_colour_check"]},
    "scope-is-a-number": {"scope": 7},
    "created-is-a-dict": {"created": {"x": 1}},
    "detail-is-a-string": {"detail": "yes"},
}


@pytest.mark.parametrize("case", sorted(_BAD_BLOCKS))
def test_a_document_block_of_the_wrong_shape_does_not_take_the_window_down(
        tmp_path, qapp, case):
    """One hand-edited report file, and the window still opens and lists it.

    MUTATION: reduce `recorded_document` to its beta-22 body

        d = report_object(report).get(DOCUMENT_BLOCK)
        if not isinstance(d, dict) or not str(d.get("id") or ""):
            return None
        return d

    and five of these ten go red with `AttributeError: 'str' object has no
    attribute 'get'` / `TypeError: object of type 'int' has no len()`, raised
    inside `MeasurementReportDialog(...)` before a window exists.
    """
    s, _fm, _run, v = _run_with_three_types(tmp_path)
    target = sorted((v.dir / "reports").glob("report_*.json"))[0]
    rep = json.loads(target.read_text(encoding="utf-8"))
    block = {"id": "doc_20261102_100000_aaaaaa",
             "created": "2026-11-02T10:00:00",
             "type": "t2_full_colour_check", "compliance": None,
             "all_runs": False, "detail": False, "measurements": []}
    block.update(_BAD_BLOCKS[case])
    rep["document"] = block
    target.write_text(json.dumps(rep), encoding="utf-8")

    dlg = _dialog(s, v.measurement_ti3, qapp)
    try:
        assert dlg.isVisible()
        # the run's three reports are all still reachable, plus "New report…"
        assert dlg._saved_combo.count() == 4, [
            dlg._saved_combo.itemText(i)
            for i in range(dlg._saved_combo.count())]
        # and every one of them can be picked without taking the window down
        for i in range(dlg._saved_combo.count()):
            dlg._saved_combo.setCurrentIndex(i)
            dlg._on_saved_picked_again(i)
            qapp.processEvents()
        assert dlg._view.toPlainText().strip()
    finally:
        dlg.close()


def test_a_document_block_keeps_the_fields_it_records(tmp_path, qapp):
    """Dropping a bad shape must not drop a good one.

    The guard above passes trivially if `recorded_document` starts returning
    None for everything, so this is the other side of it: a block written by
    this build comes back whole.
    """
    from workflow.measurement_report import (SCOPE_ALL_DATES, recorded_document,
                                             stamp_document)
    rep: dict = {}
    stamp_document(rep, doc_id="doc_x", created="2026-11-02T10:00:00",
                   type_id="t4_printing_record",
                   compliance={"set_id": "chromiq_tight"},
                   all_runs=True, detail=True,
                   measurements=[{"key": "a"}, {"key": "b"}],
                   scope=SCOPE_ALL_DATES)
    doc = recorded_document(rep)
    assert doc is not None
    assert doc["id"] == "doc_x"
    assert doc["created"] == "2026-11-02T10:00:00"
    assert doc["type"] == "t4_printing_record"
    assert doc["compliance"] == {"set_id": "chromiq_tight"}
    assert doc["all_runs"] is True and doc["detail"] is True
    assert [m["key"] for m in doc["measurements"]] == ["a", "b"]
    assert doc["scope"] == SCOPE_ALL_DATES


# --------------------------------------------------------------------------
# R27-F1 — the help text and the box it describes
# --------------------------------------------------------------------------
def _help_body(dlg, title: str) -> str:
    from ui.tooltip_button import TooltipButton
    for btn in dlg.findChildren(TooltipButton):
        if getattr(btn, "_title", "") == title:
            return str(getattr(btn, "_body", ""))
    raise AssertionError(f"no help button titled {title!r}")


def test_the_detail_help_does_not_claim_a_state_the_box_is_not_in(tmp_path, qapp):
    """The ⓘ beside "Show detailed data for each run", read off the real window.

    MUTATION: put the beta-22 sentence back —

        "It makes the report, and the saved PDF, considerably longer, "
        "which is why it starts unticked."

    — and this goes red: the box is TICKED on a fresh settings file and the
    help says it starts unticked.
    """
    s, _fm, _run, v = _run_with_three_types(tmp_path)
    dlg = _dialog(s, v.measurement_ti3, qapp)
    try:
        body = _help_body(dlg, "Show detailed data for each run")
        # **FROM "New report…", WHICH IS THE STATE THE HELP IS ABOUT
        # (B8-490).** Since Knut's beta-25 ruling a window that opens showing a
        # SAVED report brings that report's own tick boxes with it, so the
        # Preferences default decides where a NEW report starts and nothing
        # else. The help sentence says exactly that now, and this is the state
        # it describes.
        dlg._saved_combo.setCurrentIndex(0)
        qapp.processEvents()
        ticked = dlg._detail_check.isChecked()
        assert ticked is bool(s.get("report_default_show_details", True))
        if "starts unticked" in body:
            assert not ticked, (
                "the help says the box starts unticked and it is ticked")
        if "starts ticked" in body:
            assert ticked, (
                "the help says the box starts ticked and it is not")
    finally:
        dlg.close()


def test_the_detail_help_names_the_lever_that_decides_its_state(tmp_path, qapp):
    """…and it says WHERE the starting state is decided.

    A help text that simply dropped the false clause would leave a reader with
    no way of finding the switch. Preferences ▸ Reports ▸ Measurement Report
    Defaults is where P.3 put it.

    MUTATION: delete the "Preferences" sentence from the tooltip and this goes
    red.
    """
    s, _fm, _run, v = _run_with_three_types(tmp_path)
    dlg = _dialog(s, v.measurement_ti3, qapp)
    try:
        body = _help_body(dlg, "Show detailed data for each run")
        assert "Preferences" in body and "Reports" in body, body
    finally:
        dlg.close()


# --------------------------------------------------------------------------
# R27-F3, the other half: absence is not a choice
# --------------------------------------------------------------------------
def _run_with_a_typeless_report(tmp_path):
    """A run set to T1 whose one saved report RECORDS no type at all.

    Every report written before `stamp_report_type` existed is this file, and
    so is every one a fixture makes with `build_report` + `save_report`. §10:
    a report with no type of its own *"still follows the run"*.
    """
    from tests.test_import_measurement_module import (_cgats, _PATCHES,
                                                      _verify_env)
    from workflow.measurement_report import (REPORT_TYPE_SUMMARY, build_report,
                                             save_report, stamp_verdict)
    from workflow.run_compliance import (bind_run, run_limits,
                                         set_run_report_type)
    s, fm, _ctl, run = _verify_env(tmp_path)
    bind_run(run, "chromiq_default", None)
    lim = run_limits(run, None)
    v = run.new_verification()
    v.ensure_dir()
    v.measurement_ti3.write_text(_cgats("CTI3", _PATCHES), encoding="utf-8")
    rep = build_report(v.measurement_ti3)
    stamp_verdict(rep, lim.limits, set_id=lim.set_id,
                  set_label=lim.label_en, edited=lim.edited)
    save_report(rep, v.dir)            # NO `stamp_report_type`: it chose nothing
    assert "report_type" not in json.loads(
        sorted((v.dir / "reports").glob("report_*.json"))[0].read_text(
            encoding="utf-8"))
    set_run_report_type(run, REPORT_TYPE_SUMMARY)
    return s, fm, run, v


def test_a_report_that_records_no_type_still_follows_the_run(tmp_path, qapp):
    """The run is on Colour summary and its one report says nothing: T1 wins.

    This is the narrowing R27-F3's fix needed. `report_type` answers T2 for a
    file that chose nothing, because T2 is what such a file RENDERS as, so a
    window restoring "the settings it was made with" from that answer would
    claim a choice nobody made and override the run's own.

    MUTATION: in `_settings_of_one_saved_report`, put `report_type(rep)` back
    in place of `recorded_report_type(rep)` and this goes red — the pulldown
    and the page both read "Full colour check" on a run set to Colour summary.
    """
    from workflow.measurement_report import report_type_name
    s, _fm, _run, v = _run_with_a_typeless_report(tmp_path)
    dlg = _dialog(s, v.measurement_ti3, qapp)
    try:
        want = report_type_name("t1_colour_summary")
        assert dlg._type_combo.currentText() == want, (
            dlg._type_combo.currentText(), _head_line(dlg))
        assert want in _head_line(dlg), _head_line(dlg)
    finally:
        dlg.close()


def test_the_same_is_true_after_clicking_that_entry(tmp_path, qapp):
    """…and the click door gives the same answer, which is the whole point of
    the two doors sharing `_settings_of_one_saved_report`.

    MUTATION: the same one. `report_type(rep)` makes the click move the
    pulldown from "Colour summary (one page)" to "Full colour check".
    """
    from workflow.measurement_report import report_type_name
    s, _fm, _run, v = _run_with_a_typeless_report(tmp_path)
    dlg = _dialog(s, v.measurement_ti3, qapp)
    try:
        want = report_type_name("t1_colour_summary")
        dlg._on_saved_picked_again(dlg._saved_combo.currentIndex())
        qapp.processEvents()
        assert dlg._type_combo.currentText() == want, (
            dlg._type_combo.currentText(), _head_line(dlg))
        assert want in _head_line(dlg), _head_line(dlg)
    finally:
        dlg.close()
