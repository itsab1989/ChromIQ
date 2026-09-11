"""A report with several columns prints every sentence, not the first.

The footnote under the results table explains an Overall word a reader cannot
account for from the table: INFO on a sheet nobody graded, INFO on a Printing
record, N-A where nothing could be checked. It was chosen with `next(...)`, so
the FIRST column that needed one printed and every other column went silent.

**Widening the rule from two reasons to three made that worse, not better**,
and the comment above it said "EVERY reason that has to be read" while the code
printed one. A second adversarial round drove three columns as a Printing
record: only the profiling sheet's sentence appeared, so the document told its
reader the verification sheets were *"measured to build a profile rather than
to check one"* — the sentence `record_type` exists precisely because that would
be false.

Distinct sentences, in column order: three columns of the same kind need it
said once.
"""
from __future__ import annotations

import html as _html
import os
import re

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from workflow.compliance_sets import SUMMARY_REASONS  # noqa: E402
from workflow.measurement_report import (REPORT_TYPE_FULL,  # noqa: E402
                                         REPORT_TYPE_RECORD)


def _two_kinds_in_one_window(tmp_path, qapp):
    """A VERIFICATION and a PROFILING sheet of the same run, in one window.

    Two kinds, because two kinds is what needs two sentences: a profiling sheet
    is never graded and says so with the 12b reason, while the verification
    beside it says the Printing record one. Two columns of the SAME kind need
    one sentence and cannot tell `next(...)` from a loop, which is how the
    first version of this file passed under the mutation it was written for.
    """
    from tests.test_import_measurement_module import _cgats, _PATCHES, _verify_env
    from workflow.measurement_report import (build_report, save_report,
                                             stamp_verdict)
    from workflow.run_compliance import ensure_bound
    s, _fm, _ctl, run = _verify_env(tmp_path)
    v = run.new_verification()
    v.ensure_dir()
    v.measurement_ti3.write_text(_cgats("CTI3", _PATCHES), encoding="utf-8")
    lim = ensure_bound(run, None, "chromiq_default")
    rep = build_report(str(v.measurement_ti3))
    stamp_verdict(rep, lim.limits, set_id=lim.set_id, set_label=lim.set_label)
    save_report(rep, v.dir)
    # …and the run's own profiling measurement, which is not a verification
    profiling = run.dir / "profiling.ti3"
    profiling.write_text(_cgats("CTI3", _PATCHES), encoding="utf-8")
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    dlg = MeasurementReportDialog(s, None, initial_ti3=v.measurement_ti3)
    dlg.show()
    qapp.processEvents()
    dlg._add_source(profiling)
    dlg._refresh()
    qapp.processEvents()
    return dlg, run


def test_two_columns_needing_two_sentences_get_two(tmp_path, qapp):
    """MUTATION: go back to `next(...)` and this goes red."""
    from workflow.compliance_sets import summary_text
    from workflow.run_compliance import set_run_report_type
    dlg, run = _two_kinds_in_one_window(tmp_path, qapp)
    try:
        assert len(dlg._runs_for_report()) == 2, "the second sheet did not load"
        set_run_report_type(run, REPORT_TYPE_RECORD)
        dlg._forget_limits()
        dlg._sync_limit_controls()
        runs = dlg._runs_for_report()
        needed = {summary_text(dlg._column_summary(r)) for r in runs}
        assert needed, "no column needs a sentence, so this proves nothing"
        body = dlg._report_body_html(runs, for_pdf=True)
        for line in needed:
            n = _html.escape(line.split(".")[0])
            places = [m.start() for m in re.finditer(re.escape(n), body)]
            rendered = [i for i in places
                        if not re.search(r"title='[^']*$", body[:i])]
            assert rendered, f"no column printed: {line[:60]}"
    finally:
        dlg.close()


def test_the_same_sentence_is_not_printed_once_per_column(tmp_path, qapp):
    """Three columns of one kind need it said once.

    MUTATION: drop the `not in _said` check and this goes red.
    """
    from workflow.run_compliance import set_run_report_type
    dlg, run = _two_kinds_in_one_window(tmp_path, qapp)
    try:
        set_run_report_type(run, REPORT_TYPE_RECORD)
        dlg._forget_limits()
        dlg._sync_limit_controls()
        body = dlg._report_body_html(dlg._runs_for_report(), for_pdf=True)
        n = _html.escape(SUMMARY_REASONS["record_type"].split(".")[0])
        rendered = [i for i in
                    [m.start() for m in re.finditer(re.escape(n), body)]
                    if not re.search(r"title='[^']*$", body[:i])]
        assert len(rendered) == 1, f"the same sentence printed {len(rendered)} times"
    finally:
        dlg.close()


def test_the_full_report_prints_no_footnote_it_does_not_need(tmp_path, qapp):
    """The control: a graded column's ordinary sentence is not a footnote, and
    widening the rule must not turn every Overall reason into one."""
    from workflow.run_compliance import set_run_report_type
    dlg, run = _two_kinds_in_one_window(tmp_path, qapp)
    try:
        set_run_report_type(run, REPORT_TYPE_FULL)
        dlg._forget_limits()
        dlg._sync_limit_controls()
        runs = dlg._runs_for_report()
        body = dlg._report_body_html(runs, for_pdf=True)
        for key in ("pass", "fail", "cond_missing"):
            frag = _html.escape(SUMMARY_REASONS[key].split("{")[0].strip())
            if len(frag) < 12:
                continue
            rendered = [i for i in
                        [m.start() for m in re.finditer(re.escape(frag), body)]
                        if not re.search(r"title='[^']*$", body[:i])]
            assert not rendered, f"a graded column's sentence became a footnote: {frag}"
    finally:
        dlg.close()
