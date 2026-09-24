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
                                      applies_a_standard, limit_bearing,
                                      ROWS, row_verdict)
from workflow.measurement_report import report_scope  # noqa: E402


# ===========================================================================
# 1. the message is a promise, so the promise is measured
# ===========================================================================
def _a_real_row_id() -> str:
    live = [r.id for r in ROWS if r.status == "now"]
    assert live, "no live row to measure the lever on"
    return live[0]


def test_the_set_really_decides_whether_such_a_row_is_shown():
    """The message's middle paragraph, measured rather than asserted.

    *"Where the set puts a real limit on the metric, the row is shown reading
    N-A ... Where the set puts no limit on it, the row is left out."*

    MUTATION: make `row_verdict` return N-A for a limit of kind `none` with no
    value and the second assertion goes red, which is the state in which "the
    row is left out" would be false.
    """
    rid = _a_real_row_id()
    assert row_verdict(Limit.value(1.5), None, True) == N_A, (
        "a set that puts a real limit on a row the chart cannot answer no "
        "longer shows it reading N-A")
    assert row_verdict(Limit.none(), None, True) is None, (
        "a set that puts NO limit on a row the chart cannot answer no longer "
        "leaves that row out")
    # and it really is the SET, not the row: the same row, two limits.
    assert limit_bearing({rid: Limit.value(1.5)}) == {rid: Limit.value(1.5)}
    assert limit_bearing({rid: Limit.none()}) == {}


def test_which_shipped_sets_put_a_real_limit_on_an_unanswerable_row():
    """**THE SENTENCE NAMES ChromIQ'S OWN SETS, SO THE CLAIM IS MEASURED.**

    Adversary round 40b drove this end to end: only the two ISO-derived sets
    put a real limit on the rows a ChromIQ verification chart cannot answer,
    and the ChromIQ sets put none, which is why the message says "that is what
    ChromIQ's own sets do with the metrics above" rather than describing one
    behaviour as though it were universal.

    MUTATION: give a ChromIQ set a real limit on one of these rows and this
    goes red naming it, which is the state in which that clause is false.
    """
    from workflow.compliance_sets import SETS, effective_limits
    # The three rows a ChromIQ verification chart cannot answer, which are
    # what the pre-flight lists and what the paragraph sits under.
    unanswerable = ("substrate_de00_max", "solids_de00_max",
                    "cmy_solids_dhab_max")
    own, derived = [], []
    for st in SETS:
        lims = effective_limits(st.id, None)
        real = [r for r in unanswerable
                if (lims.get(r) is not None and lims[r].is_numeric)]
        (derived if applies_a_standard(st.id) else own).append((st.id, real))
    assert own, "no ChromIQ set found"
    for sid, real in own:
        assert not real, (
            f"{sid} is one of ChromIQ's own sets and now puts a real limit on "
            f"{real}, so the message's clause about what ChromIQ's own sets "
            f"do is false")


def test_the_message_says_what_decides_it_and_qualifies_the_lever():
    """**EVERY CLAUSE ROUND 40b MEASURED FALSE IS GONE, AND ITS REPLACEMENT
    IS HERE.** The first version said the row "is listed in the report all the
    same, reading N-A with a numbered note", and that the threshold is set to
    "-". Measured: that describes 2 of 7 selectable sets and 1 of 4 buildable
    report types, "-" cannot be typed into the box at all, and on a locked run
    or an ISO column the control does not exist.
    """
    body = M.M_VERIFY_UNCHECKED_METRICS.render()[1]
    for phrase in ("is decided by the limit set",      # F2: the set decides
                   "on a report type that carries notes",   # F3: so does the type
                   "threshold to zero",                # F4: not "-"
                   "\u201c\u2013\u201d",                      # F4: the en dash it shows
                   # F5, K31: the lever is the REPORT's own limits now
                   "the report's own limits"):
        assert phrase in body, (phrase, body)
    for gone in ("is listed in the report all the same",
                 "disappears from the report entirely",
                 "threshold to \u201c-\u201d",
                 "open Report limits"):
        assert gone not in body, (
            f"{gone!r} is back in the message, and round 40b measured it false")


def test_both_messages_are_proposed_and_not_approved():
    """They were Knut's REQUEST and not his wording, so neither could pass for
    approved. §M's rule, and the register in test_message_catalogue.py pins
    the same ids from the other side.

    K33 (#182 5816565326, 2026-09-24): Knut approved section C of 5802027116.
    M-REPORT-PATCH-COUNTS-DIFFER (C11) was unchanged since that post and is
    approved; M-VERIFY-UNCHECKED-METRICS (C13) was reworded for K31 after it,
    so it still waits."""
    mid = "M-VERIFY-UNCHECKED-METRICS"
    assert mid in M.CATALOGUE, mid
    assert not M.CATALOGUE[mid].approved, mid
    assert mid in M.PROPOSED, mid
    mid = "M-REPORT-PATCH-COUNTS-DIFFER"
    assert M.CATALOGUE[mid].approved, mid
    assert mid not in M.PROPOSED, mid


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
    assert "is decided by the limit set" in text, text[-500:]
    assert "threshold to zero" in text


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
    assert "is decided by the limit set" not in text, text[-500:]


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
    # TEXT AND BACKGROUND COLOURS BOTH (R4 made the note a tinted box; a
    # `bgcolor` attribute is a colour on the page as much as `color:` is).
    colours = re.findall(r"color[:=]'?(#[0-9a-fA-F]{6})", html_out)
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
def _preflight_body(row, short: bool = False):
    """What the pre-flight popup would say about *row*, through the tab's own
    builder. A `__new__` instance: the method reads nothing but its argument
    and the two module functions it imports. *short* is the one-line version
    a screen too short for the wide box gets (#182 R2)."""
    from ui.tabs.tab_measure import TabMeasure
    tab = TabMeasure.__new__(TabMeasure)
    return TabMeasure._verification_preflight_message(tab, row, short)[1]


def test_the_preflight_says_it_too_when_the_chart_falls_short(a_real_chart):
    """MUTATION: delete the append in `tab_measure._verification_preflight_
    message` and this goes red; so does appending the one line in place of
    the paragraph (the beta 38 popup)."""
    import dataclasses
    from workflow import measurement_report as MR
    row = dataclasses.replace(
        a_real_chart,
        assessment=_assessed(a_real_chart.chart, MR.REPORT_TYPE_FULL,
                             "custom_iso_12647_7"))
    assert row.assessment.checked and row.assessment.missing
    # **THE FULL PARAGRAPH, IN A WIDER BOX** (#182 R2, Knut 5781645939 and
    # 5795087247: "Leave the window wider as previously specified"). Until
    # beta 39 this asserted the opposite (one line only), because the
    # paragraph took the popup past a 13-inch screen at its natural width.
    body = _preflight_body(row)
    assert "It is never judged, and it can never make the report fail." in body
    assert "threshold to zero" in body, body[-600:]
    # …and the one line is what a screen too short for the wide box gets.
    short = _preflight_body(row, short=True)
    assert "is decided by the limit set" in short, short[-600:]
    assert "threshold to zero" not in short


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
    assert "is decided by the limit set" not in body, body[-600:]
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
        # The two windows say DIFFERENT text on purpose (one line against the
        # paragraph); what has to agree is WHEN they say anything at all.
        in_popup = "is decided by the limit set" in _preflight_body(row)
        in_window = "is decided by the limit set" in " ".join(
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



def test_the_note_is_set_apart_from_body_text(qapp):
    """R4 (Knut, 2026-09-22): *"a clear information note, not the same font
    and colour as other bread-text, so that the note is not hidden."* It is a
    tinted box, not a paragraph in the body's dim grey.

    MUTATION: return the old `<div style='color:dim'>` paragraph and this goes
    red.
    """
    from ui.dialogs.measurement_report_dialog import (MeasurementReportDialog,
                                                      _C)
    dlg = MeasurementReportDialog.__new__(MeasurementReportDialog)
    out = dlg._scope_notes_html([{"kind": "patch_counts", "counts": [1617, 918]}])
    assert f"bgcolor='{_C['panel']}'" in out, out[:300]
    assert f"color:{_C['dim']}" not in out, (
        "the note is painted in the body text's dim colour again")
