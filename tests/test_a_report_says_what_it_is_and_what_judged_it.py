"""Every report names its type and its limit set, at the top, where a reader looks.

Knut, 2026-09-14, with two PDFs of the same run attached and the window's own
pulldowns moved between them:

    As you can see, there are texts that should state correct report type used
    and judged against, but is not changing this. The top of the Report scope
    also does not show the report type generated.

Measured on his two files before anything was changed:

* the **Grey and tone check** PDF carries `Report type: Grey and tone check` on
  page 1; the **Full colour check** one carries no such line at all, because
  the code read `if _tid != REPORT_TYPE_FULL`. So the DEFAULT type produced a
  document that never said what it was;
* neither carries the limit set at the top. It IS in both, correctly and
  differently ("Custom ISO 12647-7" in one, "ChromIQ default" in the other),
  in the "Judged against" row of Report Results and again under each run's own
  table. What was missing is a line where a reader opening a saved PDF looks
  first;
* and the paragraph he quoted as evidence that nothing updates is the RUN'S
  DESCRIPTION, which no report can update. See
  `test_the_run_description_is_labelled_as_one`.
"""
from __future__ import annotations

import os
import re

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest                                                   # noqa: E402


def _dialog(tmp_path, qapp):
    from tests.test_import_measurement_module import (_cgats, _PATCHES,
                                                      _verify_env)
    s, fm, _ctl, run = _verify_env(tmp_path)
    v = run.new_verification()
    v.ensure_dir()
    v.measurement_ti3.write_text(_cgats("CTI3", _PATCHES), encoding="utf-8")
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    dlg = MeasurementReportDialog(s, None, initial_ti3=v.measurement_ti3)
    dlg.show()
    qapp.processEvents()
    # **KNUT'S BETA-25 QUESTION, ANSWERED "Create New" (B8-491).** Generate
    # report asks what to do when a report from "Report shown" is selected and
    # one of its five settings has moved. Every test here was written for the
    # behaviour that answer keeps; the question itself is guarded in
    # `tests/test_generate_report_asks_what_to_do.py`.
    dlg._ask_update_or_create_new = lambda: "new"
    return dlg, run, fm


def _plain(dlg) -> str:
    return " ".join(re.sub("<[^>]+>", " ", dlg._view.toHtml()).split())


def test_the_default_type_names_itself_too(tmp_path, qapp):
    """The type he was on when he found it, and the one the guard excluded.

    MUTATION: put `_tid != REPORT_TYPE_FULL` back in front of the line and this
    goes red.
    """
    from workflow.measurement_report import (REPORT_TYPE_FULL,
                                             report_type_name)
    dlg, _run, _fm = _dialog(tmp_path, qapp)
    try:
        assert dlg._report_type_now() == REPORT_TYPE_FULL, (
            "this test is about the default type and the window is not on it")
        text = _plain(dlg)
        assert "Report type:" in text
        assert report_type_name(REPORT_TYPE_FULL) in text
    finally:
        dlg.close()


def test_every_built_type_names_itself(tmp_path, qapp):
    """Not one type, all of them: the guard that hid one could hide another."""
    from workflow.measurement_report import (REPORT_TYPES,
                                             report_type_is_built,
                                             report_type_name)
    dlg, _run, _fm = _dialog(tmp_path, qapp)
    try:
        for tid in REPORT_TYPES:
            if not report_type_is_built(tid):
                continue
            i = [dlg._type_combo.itemData(n)
                 for n in range(dlg._type_combo.count())].index(tid)
            dlg._type_combo.setCurrentIndex(i)
            qapp.processEvents()
            dlg._on_generate_report()
            qapp.processEvents()
            text = _plain(dlg)
            assert f"Report type: {report_type_name(tid)}" in text, (
                f"a {tid} report does not name itself")
    finally:
        dlg.close()


def test_the_head_can_never_name_a_type_this_build_cannot_make(tmp_path, qapp):
    """A type ChromIQ cannot make yet renders as the full report, so naming the
    REQUESTED type would put a claim at the head of a document that is not it.

    **AND THE GUARD THAT STOPS IT IS NOT IN THIS WINDOW.** The header code has
    a `report_type_is_built` fallback, and it is unreachable: `report_type`
    already answers today's report for an id this build cannot produce, and
    `_report_type_now` goes through it on every branch. A first version of this
    test asserted on the fallback and could not fail, because the state it
    described cannot be reached. What is reachable, and what actually protects
    the header, is that normalisation, so that is what is pinned here.

    MUTATION: make `report_type` honour an unbuilt id and this goes red.
    """
    from workflow.measurement_report import (REPORT_TYPES,
                                             report_type_is_built,
                                             report_type_name)
    unbuilt = [t for t in REPORT_TYPES if not report_type_is_built(t)]
    if not unbuilt:
        pytest.skip("every report type is built, so there is no such case")
    dlg, run, _fm = _dialog(tmp_path, qapp)
    try:
        for tid in unbuilt:
            # `set_run_report_type` refuses these, which is right: the pulldown
            # greys them. A run can still CARRY one, written by a newer
            # ChromIQ that could produce it, and that is the state under test.
            meta = run.load_meta()
            meta.report_type = tid
            run.save_meta(meta)
            dlg._forget_limits()
            dlg._refresh()
            qapp.processEvents()
            now = dlg._report_type_now()
            assert report_type_is_built(now), (
                f"a run carrying {tid} makes this window claim to produce "
                f"{now}, which it cannot")
            head = _plain(dlg).split("Report Scope")[0]
            assert f"Report type: {report_type_name(now)}" in head
            assert report_type_name(tid) not in head, (
                f"the head names {tid}, and the document is a {now}")
    finally:
        dlg.close()


def test_the_limit_set_is_named_at_the_top(tmp_path, qapp):
    """*"there are texts that should state correct report type used and judged
    against"*, and it follows the pulldown.

    MUTATION: drop the "Judged against:" block and this goes red.
    """
    dlg, _run, _fm = _dialog(tmp_path, qapp)
    try:
        head = _plain(dlg).split("Report Scope")[0]
        assert "Judged against:" in head
        first = head.split("Judged against:")[1][:60]
        combo = dlg._set_combo
        other = next(i for i in range(combo.count())
                     if combo.itemData(i) != combo.currentData())
        want = combo.itemText(other)
        combo.setCurrentIndex(other)
        qapp.processEvents()
        dlg._on_generate_report()
        qapp.processEvents()
        head2 = _plain(dlg).split("Report Scope")[0]
        assert "Judged against:" in head2
        second = head2.split("Judged against:")[1][:60]
        assert second != first, (
            f"the set changed to {want!r} and the line still reads {first!r}")
        assert want.split(" (")[0] in second, (
            f"the line reads {second!r} and the set chosen is {want!r}")
    finally:
        dlg.close()


def test_two_runs_bound_to_different_sets_leave_one_in_the_document(tmp_path,
                                                                    qapp):
    """A DOCUMENT IS WRITTEN AGAINST ONE LIMIT SET (B8-246).

    This test used to pin the opposite half of the same situation: the head
    named no set, because the table under it held two. The design authority
    ruled on 2026-09-16 that the table may not hold two at all, so the state
    that made the head silent is now unreachable and the head names the one
    set the document IS written against. The `len(_sets) == 1` guard is left
    where it is as a backstop, and deliberately not tested: nothing can reach
    it any more, and a test that stages an unreachable state would pin the
    staging rather than the window.

    MUTATION: drop the `_one_limit_set` call from `_report_body_html` and this
    goes red on the head line and on the left-out note together.
    """
    from tests.test_import_measurement_module import _cgats, _PATCHES
    dlg, run, fm = _dialog(tmp_path, qapp)
    try:
        from workflow.run_compliance import bind_run
        run2 = fm.project().new_run()
        v2 = run2.new_verification()
        v2.ensure_dir()
        v2.measurement_ti3.write_text(
            _cgats("CTI3", [(r * 0.5, g, b) for (r, g, b) in _PATCHES]),
            encoding="utf-8")
        bind_run(run2, "chromiq_tight", None)
        dlg._add_source(v2.measurement_ti3)
        qapp.processEvents()
        body = _plain(dlg)
        head = body.split("Report Scope")[0]
        assert "Judged against:" in head, (
            "the document holds one limit set and the head names none of them")
        assert "ChromIQ tight" in head, head[-200:]
        # AND THE OTHER RUN IS COUNTED, NOT NAMED. Knut ruled in beta 20 that
        # a report may not "show information that other reports exist with
        # other 'judged against' threshold sets", so the sentence that used to
        # name the left-out measurement and its set is gone and the Scope
        # states the count instead.
        assert "judged against a different limit set" not in body
        import re
        assert re.search(r"covers \d+ of the \d+ measurements", body), (
            "the other run's measurement is neither in the report nor counted "
            "out of it")
    finally:
        dlg.close()


def test_the_run_description_is_labelled_as_one(tmp_path, qapp):
    """The paragraph Knut read as a stale report field.

    The demo package writes a description that names a report type and a limit
    set, because he asked for that sentence on 2026-09-11. A description is a
    field a person writes and no report can update it, so once a run is
    rebound it contradicts the live lines above it. Unlabelled, it reads as one
    of them.

    MUTATION: drop the label and this goes red.
    """
    dlg, run, _fm = _dialog(tmp_path, qapp)
    try:
        from core.i18n import tr
        meta = run.load_meta()
        meta.description = "Judged with ChromIQ tight, bound and still open."
        run.save_meta(meta)
        dlg._forget_limits()
        dlg._refresh()
        qapp.processEvents()
        text = _plain(dlg)
        assert "Judged with ChromIQ tight" in text, "the description is gone"
        i = text.index("Judged with ChromIQ tight")
        assert tr("Run description") in text[max(0, i - 120):i], (
            "the description is printed with nothing saying what it is")
    finally:
        dlg.close()
