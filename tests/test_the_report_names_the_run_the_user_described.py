"""The run's description heads the Report Scope, and nothing heads it when empty.

**Knut, 2026-09-11**, answering whether the one-page report should carry a
customer or job name: *"No customer or job name per today. But print the run's
description at the top of the section that shows the scope of the report and
the measurements included, and nothing when it is empty."*

He named the section rather than the type, and every report type has it, so it
is there rather than in one type's own body.

**Nothing when empty** is the half worth a test. Not a blank line, not a label
with no value: a run nobody described says nothing about itself.
"""
from __future__ import annotations

import html as _html
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def _dialog(tmp_path, qapp):
    from tests.test_import_measurement_module import _cgats, _PATCHES, _verify_env
    s, _fm, _ctl, run = _verify_env(tmp_path)
    v = run.new_verification()
    v.ensure_dir()
    v.measurement_ti3.write_text(_cgats("CTI3", _PATCHES), encoding="utf-8")
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    dlg = MeasurementReportDialog(s, None, initial_ti3=v.measurement_ti3)
    dlg.show()
    qapp.processEvents()
    return dlg, run


def _describe(run, text):
    meta = run.load_meta()
    meta.description = text
    run.save_meta(meta)


def test_a_described_run_says_so_at_the_top_of_the_scope(tmp_path, qapp):
    """MUTATION: drop the description line and this goes red."""
    dlg, run = _dialog(tmp_path, qapp)
    try:
        _describe(run, "Hahnemühle Photo Rag, job 4471")
        dlg._forget_limits()
        dlg._sync_limit_controls()
        for for_pdf in (False, True):
            body = dlg._report_body_html(dlg._runs_for_report(), for_pdf=for_pdf)
            needle = _html.escape("Hahnemühle Photo Rag, job 4471")
            assert needle in body, f"for_pdf={for_pdf}: the description is nowhere"
            # …at the TOP of the scope, before the list of what is included
            from core.i18n import tr
            intro = _html.escape(tr(
                "The following profile verification runs are included:"))
            if intro in body:
                assert body.index(needle) < body.index(intro), \
                    "the description is below the list it is supposed to head"
    finally:
        dlg.close()


def test_a_run_nobody_described_says_nothing(tmp_path, qapp):
    """Not a blank line, not a label with no value.

    MUTATION: print the line unconditionally and this goes red.
    """
    dlg, run = _dialog(tmp_path, qapp)
    try:
        _describe(run, "")
        dlg._forget_limits()
        dlg._sync_limit_controls()
        assert dlg._run_description() == ""
        body = dlg._report_body_html(dlg._runs_for_report(), for_pdf=True)
        from core.i18n import tr
        head = _html.escape(tr("Report Scope"))
        i = body.index(head)
        between = body[i:i + 400]
        assert "font-weight:bold;margin:0 0 4px" not in between, \
            "an empty description still printed its own line"
    finally:
        dlg.close()


def test_whitespace_is_not_a_description(tmp_path, qapp):
    dlg, run = _dialog(tmp_path, qapp)
    try:
        _describe(run, "   \n\t ")
        dlg._forget_limits()
        dlg._sync_limit_controls()
        assert dlg._run_description() == ""
    finally:
        dlg.close()


def test_a_report_holding_several_runs_names_none_of_them(tmp_path, qapp):
    """A heading that names one run would be wrong about the rest.

    MUTATION: drop the several-runs check and this goes red.
    """
    from tests.test_import_measurement_module import _cgats, _PATCHES, _verify_env
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    s, fm, _ctl, run1 = _verify_env(tmp_path)
    v1 = run1.new_verification()
    v1.ensure_dir()
    v1.measurement_ti3.write_text(_cgats("CTI3", _PATCHES), encoding="utf-8")
    _describe(run1, "the first run")
    run2 = fm.project().new_run()
    v2 = run2.new_verification()
    v2.ensure_dir()
    v2.measurement_ti3.write_text(_cgats("CTI3", _PATCHES), encoding="utf-8")
    _describe(run2, "the second run")
    dlg = MeasurementReportDialog(s, None, initial_ti3=v1.measurement_ti3)
    dlg.show()
    qapp.processEvents()
    try:
        dlg._add_source(v2.measurement_ti3)
        dlg._refresh()
        qapp.processEvents()
        assert len(dlg._distinct_run_dirs()) == 2
        assert dlg._run_description() == "", \
            "one run's description was used to head a report about two"
        body = dlg._report_body_html(dlg._runs_for_report(), for_pdf=True)
        assert "the first run" not in body and "the second run" not in body
    finally:
        dlg.close()
