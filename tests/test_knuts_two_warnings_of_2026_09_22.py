"""Knut's two new pieces of text, and the conditions that decide each.

Both were asked for on 2026-09-22, in the same conversation as the ISO COND
cap, and both are §M-PROPOSED: his request, not his wording.

1. **M-VERIFY-UNCHECKED-METRICS.** A report that judges metrics the chart
   cannot calculate carries a note for each, and the reader should be told
   BEFORE printing that those metrics can be taken out in Report limits by
   setting the threshold to "-", so that what is handed to a customer holds
   only the metrics that were checked. Shown in the verification pre-flight
   and in "Which presets can be used for verification".

2. **M-REPORT-PATCH-COUNTS-DIFFER.** Where the selected measurements come
   from charts with different patch counts, the report says so plainly: a
   metric worked out over more patches is not worked out over quite the same
   colours as the same metric over fewer, and it shows in the trend graphs.
   *"Not an error"* are his words, which is why this file checks the COLOUR it
   is printed in as well as the words.

**THE LEVER'S TWO OUTCOMES ARE NOT THE SAME, AND THE FIRST DRAFT SAID THEY
WERE.** Measured on the real `row_verdict` before the sentence was written:

    chart cannot answer it, threshold 1.5  ->  N-A   (row drawn, with a note)
    chart cannot answer it, threshold "-"  ->  no word, so no row at all
    chart CAN answer it,    threshold "-"  ->  INFO  (row drawn, not graded)

So "-" removes the row only in the case Knut is asking about. The text says
both halves, and `test_the_lever_really_does_what_the_message_promises`
measures them rather than trusting the sentence.
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from workflow import measurement_messages as M        # noqa: E402
from workflow.compliance_sets import (INFO, Limit, N_A,  # noqa: E402
                                      limit_bearing, ROWS, row_verdict)
from workflow.measurement_report import report_scope  # noqa: E402


# ===========================================================================
# 1. the message is a promise, so the promise is measured
# ===========================================================================
def _a_real_row_id() -> str:
    live = [r.id for r in ROWS if r.status == "now"]
    assert live, "no live row to measure the lever on"
    return live[0]


def test_the_lever_really_does_what_the_message_promises():
    """MUTATION: make `row_verdict` return N-A for a "-" limit with no value
    and the first assertion goes red, which is the state in which the
    message's "disappears from the report entirely" would be false."""
    rid = _a_real_row_id()
    # the half Knut is asking about: a metric this chart cannot answer
    assert row_verdict(Limit.value(1.5), None, True) == N_A
    assert row_verdict(Limit.none(), None, True) is None, (
        "a '-' threshold no longer removes a row the chart cannot answer, so "
        "the message's promise that it 'disappears from the report entirely' "
        "is false")
    # the other half, which the message states rather than glossing over
    assert row_verdict(Limit.none(), 0.9, True) == INFO, (
        "a '-' threshold on a row the chart CAN answer no longer shows the "
        "number ungraded, so the message's second half is false")
    # and the row really does leave the limit set
    assert limit_bearing({rid: Limit.value(1.5)}) == {rid: Limit.value(1.5)}
    assert limit_bearing({rid: Limit.none()}) == {}


def test_the_message_states_both_outcomes_and_names_the_window():
    body = M.M_VERIFY_UNCHECKED_METRICS.render()[1]
    for phrase in ("Report limits",          # the lever, by the name on screen
                   "disappears from the report entirely",
                   "shown with its number and no verdict",
                   "N-A"):
        assert phrase in body, (phrase, body)


def test_both_messages_are_proposed_and_not_approved():
    """They are Knut's REQUEST and not his wording, so neither may pass for
    approved. §M's rule, and the register in test_message_catalogue.py pins
    the same two ids from the other side."""
    for mid in ("M-VERIFY-UNCHECKED-METRICS", "M-REPORT-PATCH-COUNTS-DIFFER"):
        assert mid in M.CATALOGUE, mid
        assert not M.CATALOGUE[mid].approved, mid
        assert mid in M.PROPOSED, mid


# ===========================================================================
# 2. where the paragraph appears, and where it must not
# ===========================================================================
#: The strictest combination ChromIQ can be asked for: no preset chart can
#: answer all of it, so a row that falls short is guaranteed to exist, and the
#: everyday one, where an ordinary chart answers everything. Both are the
#: pairs `test_the_preset_window_says_what_a_chart_can_answer.py` uses, so the
#: two files cannot disagree about what "falls short" means.
def _assessed(chart, type_id, set_id):
    """One real preset chart against one real combination, through the
    window's own assessor rather than a second opinion."""
    from workflow import preset_eligibility as PE
    return PE.assess(chart, type_id, set_id)


@pytest.fixture(scope="module")
def a_real_chart(qapp):
    from core.settings import AppSettings
    from ui.tabs.tab_chart import verification_preset_rows
    for r in verification_preset_rows(AppSettings()):
        if r.builtin and r.chart is not None:
            return r
    pytest.skip("no built-in preset ships a chart")


def test_the_preset_window_prints_it_under_a_chart_that_falls_short(
        a_real_chart):
    """`detail_lines` is what the right-hand pane renders. MUTATION: drop the
    append in `preset_verification_dialog.detail_lines` and this goes red."""
    import dataclasses

    import ui.dialogs.preset_verification_dialog as PV
    from workflow import measurement_report as MR
    row = dataclasses.replace(
        a_real_chart,
        assessment=_assessed(a_real_chart.chart, MR.REPORT_TYPE_FULL,
                             "custom_iso_12647_7"))
    assert row.assessment.checked and row.assessment.missing, (
        "the strictest combination no longer leaves this chart short of "
        "anything, so this test would prove nothing")
    text = " ".join(l.text for l in PV.detail_lines(row))
    assert "Report limits" in text, text[-500:]
    assert "disappears from the report entirely" in text


def test_and_never_under_a_chart_that_falls_short_of_nothing(a_real_chart):
    """A paragraph about rows that will read N-A, on a chart where none will,
    is noise, and it would sit directly under this window's own sentence
    saying the chart answers everything."""
    import dataclasses

    import ui.dialogs.preset_verification_dialog as PV
    from core.settings import AppSettings
    from ui.tabs.tab_chart import verification_preset_rows
    from workflow import measurement_report as MR

    whole = None
    for r in verification_preset_rows(AppSettings()):
        if not r.builtin or r.chart is None:
            continue
        a = _assessed(r.chart, MR.REPORT_TYPE_FULL, "chromiq_default")
        if a.checked and a.asked and not a.missing:
            whole = dataclasses.replace(r, assessment=a)
            break
    if whole is None:
        pytest.skip("no shipped preset answers every metric of the everyday "
                    "combination")
    text = " ".join(l.text for l in PV.detail_lines(whole))
    assert "Report limits" not in text, text[-500:]


# ===========================================================================
# 3. the patch-count note: when it is made, and in what colour
# ===========================================================================
def _run(patches: "int | None", created="2026-09-22T10:00:00"):
    r = {"chart": "P", "created": created, "instrument": "i1Pro3"}
    if patches is not None:
        r["patches"] = patches
    return r


def test_one_patch_count_makes_no_note():
    sc = report_scope([_run(918), _run(918), _run(918)])
    assert sc["notes"] == [], sc["notes"]


def test_two_patch_counts_make_one_note_in_column_order():
    """Column order, not sorted: the sentence names the counts in the order a
    reader meets them across the table.

    **THE FIXTURE USED TO BE ALREADY DESCENDING** (adversary round 40c,
    finding 6): 1617, 918, 1617, 400 is what a reverse sort produces too, so
    `sorted(distinct, reverse=True)` left this green and only an ascending
    sort was caught. The order here is non-monotonic, so neither sort matches
    it.
    """
    sc = report_scope([_run(918), _run(1617), _run(918), _run(400)])
    assert sc["notes"] == [{"kind": "patch_counts",
                            "counts": [918, 1617, 400]}], sc["notes"]


def test_a_sheet_with_no_recorded_count_is_not_a_second_count():
    """A report saved before ChromIQ recorded the count carries no `patches`
    key, and `None` is not a patch count. Treating it as one would print the
    note on every report that holds one old column."""
    sc = report_scope([_run(918), _run(None), _run(918)])
    assert sc["notes"] == [], sc["notes"]
    sc = report_scope([_run(918), _run(0), _run(918)])
    assert sc["notes"] == [], "a zero count is not a chart, it is an absence"


def test_the_note_is_never_appended_to_the_red_warning_block():
    """Knut: *"Not an error."* `_scope_warnings_html` paints everything it is
    handed in the report's FAIL colour under the word "Warning", so a note put
    into `warnings` would say the opposite of what he asked for, with nothing
    in the rendering having to change for it to happen."""
    sc = report_scope([_run(1617), _run(918)])
    assert not sc["warnings"], sc["warnings"]
    assert sc["notes"]


def test_the_rendered_note_carries_the_counts_and_is_not_the_fail_colour(qapp):
    """MUTATION: render the note through `_scope_warnings_html` instead and
    this goes red on the colour, which is the only thing that separates a
    plain note from a warning on the page."""
    from ui.dialogs.measurement_report_dialog import (MeasurementReportDialog,
                                                      _C)
    dlg = MeasurementReportDialog.__new__(MeasurementReportDialog)
    html_out = dlg._scope_notes_html(
        [{"kind": "patch_counts", "counts": [1617, 918]}])
    assert "1617, 918" in html_out, html_out
    assert "trend graphs" in html_out
    assert "not a fault" in html_out
    assert _C["fail"] not in html_out, (
        "the plain note is painted in the report's FAIL colour, which is the "
        "one thing Knut said it must not be")
    # **AND NOT ANY OTHER RED EITHER** (adversary round 40c, finding 7).
    # This used to assert `_C["dim"] in html_out`, which reads the constant it
    # is checking: setting `_C["dim"]` to #cc0000 rendered the "not an error"
    # note in a red and the test passed. What the guard is actually about is
    # that the note does not READ as an error, so the colour is parsed out and
    # measured. A neutral or dim grey has no dominant red channel; the report's
    # own FAIL colour does, and that is the measurement rather than a guess.
    import re
    colours = re.findall(r"color:(#[0-9a-fA-F]{6})", html_out)
    assert colours, html_out[:200]
    for c in colours:
        r, g, b = (int(c[i:i + 2], 16) for i in (1, 3, 5))
        assert r <= max(g, b) + 24, (
            f"the plain note is painted {c}, whose red channel dominates by "
            f"{r - max(g, b)}; that reads as an error, which Knut said this "
            f"note is not")


def test_an_empty_or_unknown_note_renders_nothing(qapp):
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    dlg = MeasurementReportDialog.__new__(MeasurementReportDialog)
    assert dlg._scope_notes_html([]) == ""
    assert dlg._scope_notes_html([{"kind": "something_later"}]) == ""


@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


# ===========================================================================
# 4. THE PRE-FLIGHT HALF, WHICH HAD NO GUARD AT ALL
# ===========================================================================
# **FOUND BY ADVERSARY ROUND 40c (M6a, M7a).** `ui/tabs/tab_measure.py`'s
# append was referenced by no test in the tree: deleting it left the whole
# everyday tier green, 17,569 passed exit 0, and making it unconditional did
# too. The commit message said "the verification pre-flight AND the preset
# window say what the report does"; only the preset window was guarded, and
# the two use DIFFERENT expressions for the same condition, so even the
# condition was untested.
#
# `_verification_preflight_message` is the method that builds what the popup
# shows, so that is what is measured, not the window it is shown in.
def _preflight_body(row):
    """What the pre-flight popup would say about *row*, through the tab's own
    builder. A `__new__` instance: the method reads nothing but its argument
    and the two module functions it imports."""
    from ui.tabs.tab_measure import TabMeasure
    tab = TabMeasure.__new__(TabMeasure)
    return TabMeasure._verification_preflight_message(tab, row)[1]


def test_the_preflight_says_it_too_when_the_chart_falls_short(a_real_chart):
    """MUTATION: delete the append in `tab_measure._verification_preflight_
    message` and this goes red."""
    import dataclasses
    from workflow import measurement_report as MR
    row = dataclasses.replace(
        a_real_chart,
        assessment=_assessed(a_real_chart.chart, MR.REPORT_TYPE_FULL,
                             "custom_iso_12647_7"))
    assert row.assessment.checked and row.assessment.missing
    body = _preflight_body(row)
    assert "Report limits" in body, body[-600:]
    assert "disappears from the report entirely" in body


def test_and_the_preflight_leaves_it_out_when_the_chart_does_not(qapp):
    """The other direction, which M7a proved nothing was checking. The
    paragraph would otherwise sit directly under this window's own line
    "Nothing is missing: every metric this chart is asked for can be measured
    on it.", which is the same sentence contradicting itself."""
    import dataclasses
    from core.settings import AppSettings
    from ui.tabs.tab_chart import verification_preset_rows
    from workflow import measurement_report as MR
    whole = None
    for r in verification_preset_rows(AppSettings()):
        if not r.builtin or r.chart is None:
            continue
        a = _assessed(r.chart, MR.REPORT_TYPE_FULL, "chromiq_default")
        if a.checked and a.asked and not a.missing:
            whole = dataclasses.replace(r, assessment=a)
            break
    assert whole is not None, (
        "no shipped preset answers every metric of the everyday combination, "
        "so this guard would prove nothing")
    body = _preflight_body(whole)
    assert "Report limits" not in body, body[-600:]
    assert "Nothing is missing" in body, (
        "the fixture no longer reaches the state this guard is about")


def test_the_two_windows_agree_about_when_to_say_it(a_real_chart):
    """They are two expressions of one rule, written in different files, and
    round 40c pointed out that nothing held them together. Measured over both
    combinations rather than asserted on one."""
    import dataclasses

    import ui.dialogs.preset_verification_dialog as PV
    from workflow import measurement_report as MR
    for set_id in ("custom_iso_12647_7", "chromiq_default"):
        row = dataclasses.replace(
            a_real_chart,
            assessment=_assessed(a_real_chart.chart, MR.REPORT_TYPE_FULL,
                                 set_id))
        in_popup = "Report limits" in _preflight_body(row)
        in_window = "Report limits" in " ".join(
            l.text for l in PV.detail_lines(row))
        assert in_popup == in_window, (
            f"{set_id}: the pre-flight says it {in_popup} and the preset "
            f"window says it {in_window}, so one of them is wrong")


# ===========================================================================
# 5. …AND THE PATCH-COUNT NOTE HAS TO REACH A RENDERED REPORT
# ===========================================================================
# **FOUND BY ADVERSARY ROUND 40c (M12).** `_scope_html` is the only caller of
# `_scope_notes_html`, and deleting that one call left the ENTIRE everyday
# tier green: 17,569 passed, exit 0. Every guard above stops either at
# `report_scope()` returning a dict or at `_scope_notes_html()` called
# directly. Nothing asserted the sentence reaches a page. That is the exact
# fault shape `test_a_saved_pass_under_a_standard_is_never_bare.py` exists
# for: a sentence a reader cannot read explains nothing.
def test_the_note_reaches_the_rendered_report_and_the_pdf(qapp, tmp_path):
    """MUTATION: drop `+ self._scope_notes_html(...)` from `_scope_html`'s
    return and this goes red, where nothing in the suite did."""
    import html as _html
    import re

    from tests.test_a_saved_pass_under_a_standard_is_never_bare import (
        _dialog, _saved_run, _settings)
    proj, run, ti3 = _saved_run(tmp_path, "chromiq_default",
                                "ChromIQ default (recommended)")
    dlg = _dialog(_settings(tmp_path), ti3)
    try:
        runs = dlg._runs_for_report()
        assert runs
        # Two columns of the same measurement with different counts on them:
        # what the note is about, made without needing two real charts.
        pair = [dict(runs[0]), dict(runs[0])]
        pair[0]["patches"] = 1617
        pair[1]["patches"] = 918
        body = dlg._report_body_html(pair, for_pdf=True)
        seen = _html.unescape(re.sub(r"<[^>]+>", " ", body))
        seen = " ".join(seen.split())
        assert "1617, 918" in seen, (
            "the patch-count note does not reach the rendered report. If it "
            "is only in a dict it is in no document and no reader sees it.")
        assert "trend graphs" in seen
    finally:
        dlg.deleteLater()
