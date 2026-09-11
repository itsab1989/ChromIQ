"""T1, "Colour summary (one page)": the page that goes with the job.

**Knut** described it as the report handed to a customer with the print they
ordered: *"a very short overview of accuracy of a selection of colors, with
some statistics, that can be printed out for every job."* On 2026-09-11 he
settled the two things that were open: no customer or job name, but the run's
own description at the top of the scope section; and the example colours must
come from the chart that was actually measured.

**It is a DIFFERENT DOCUMENT, not the full report with rows removed.** T3
filters rows and keeps the shape; T1 changes the shape. That is what "one page"
means, and it is the thing a test has to hold on to, because the easy way to
build this type is to keep everything and hide a little.
"""
from __future__ import annotations

import html as _html
import os
import re

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from workflow.measurement_report import (REPORT_TYPE_FULL,  # noqa: E402
                                         REPORT_TYPE_SUMMARY,
                                         report_type_is_built)


def _grey_ramp_ti3() -> str:
    from tests.test_a_saved_report_does_not_leak_its_verdict_into_another_type import (
        _grey_ramp_ti3 as g)
    return g()


def _dialog(tmp_path, qapp, description=""):
    from tests.test_import_measurement_module import _verify_env
    s, _fm, _ctl, run = _verify_env(tmp_path)
    v = run.new_verification()
    v.ensure_dir()
    v.measurement_ti3.write_text(_grey_ramp_ti3(), encoding="utf-8")
    if description:
        meta = run.load_meta()
        meta.description = description
        run.save_meta(meta)
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    dlg = MeasurementReportDialog(s, None, initial_ti3=v.measurement_ti3)
    dlg.show()
    qapp.processEvents()
    return dlg, run


def _as(dlg, run, tid):
    from workflow.run_compliance import set_run_report_type
    set_run_report_type(run, tid)
    dlg._forget_limits()
    dlg._sync_limit_controls()
    return dlg._runs_for_report()


def _text(body: str) -> str:
    return _html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", body)))


def test_t1_is_offered_as_something_chromiq_can_produce():
    assert report_type_is_built(REPORT_TYPE_SUMMARY)


def test_it_is_a_fraction_of_the_full_report(tmp_path, qapp):
    """ONE PAGE, MEASURED. T3 came out at 6,169 characters against the full
    report's 6,292, which is why its own line had to stop promising "on their
    own". T1 must not repeat that: it is a different document.

    MUTATION: build T1 by filtering the full report and this goes red.
    """
    dlg, run = _dialog(tmp_path, qapp)
    try:
        full = _text(dlg._report_body_html(_as(dlg, run, REPORT_TYPE_FULL),
                                           for_pdf=True))
        one = _text(dlg._report_body_html(_as(dlg, run, REPORT_TYPE_SUMMARY),
                                          for_pdf=True))
        assert len(one) < len(full) / 2, (
            f"the one-page report is {len(one)} characters against the full "
            f"report's {len(full)}; it is the full report with bits removed")
    finally:
        dlg.close()


def test_it_carries_no_essay_and_no_trend_section(tmp_path, qapp):
    """The things a page handed to a customer does not need.

    MUTATION: put the "How to read" section back into T1 and this goes red.
    """
    from core.i18n import tr
    dlg, run = _dialog(tmp_path, qapp)
    try:
        one = _text(dlg._report_body_html(_as(dlg, run, REPORT_TYPE_SUMMARY),
                                          for_pdf=True))
        for heading in ("How to read this report", "Report Results",
                        "Trend over time (this printer)"):
            assert tr(heading) not in one, f"T1 still carries “{heading}”"
    finally:
        dlg.close()


def test_it_carries_the_run_description_the_user_wrote(tmp_path, qapp):
    """Knut's answer to the customer-name question, on the page it was asked
    about."""
    dlg, run = _dialog(tmp_path, qapp, "Hahnemühle Photo Rag, job 4471")
    try:
        one = _text(dlg._report_body_html(_as(dlg, run, REPORT_TYPE_SUMMARY),
                                          for_pdf=True))
        assert "Hahnemühle Photo Rag, job 4471" in one
    finally:
        dlg.close()


def test_it_shows_the_colours_the_chart_supplied(tmp_path, qapp):
    """Every swatch on the page is a patch of the measurement.

    MUTATION: show a fixed list of colours and this goes red, because none of
    them would carry a location from this chart.
    """
    dlg, run = _dialog(tmp_path, qapp)
    try:
        reps = _as(dlg, run, REPORT_TYPE_SUMMARY)
        picked = reps[0].get("summary_patches") or []
        assert picked, "the report carries no example colours"
        body = dlg._report_body_html(reps, for_pdf=True)
        one = _text(body)
        for x in picked:
            assert str(x["loc"]) in one, f"patch {x['loc']} is not on the page"
        # …and both swatches of each, asked-for and measured
        for x in picked:
            assert x["expected_hex"] in body and x["measured_hex"] in body
    finally:
        dlg.close()


def test_it_states_the_promise_that_governs_every_report(tmp_path, qapp):
    """The page most likely to reach somebody outside the studio is the page
    that most needs the sentence: ChromIQ measures, it does not certify."""
    dlg, run = _dialog(tmp_path, qapp)
    try:
        one = _text(dlg._report_body_html(_as(dlg, run, REPORT_TYPE_SUMMARY),
                                          for_pdf=True))
        assert "does not certify" in one
        assert "conform" not in one.lower(), \
            "a page for a customer used the word this project never prints"
    finally:
        dlg.close()


def test_it_names_itself(tmp_path, qapp):
    from core.i18n import tr
    from workflow.measurement_report import report_type_name
    dlg, run = _dialog(tmp_path, qapp)
    try:
        one = _text(dlg._report_body_html(_as(dlg, run, REPORT_TYPE_SUMMARY),
                                          for_pdf=True))
        assert tr(report_type_name(REPORT_TYPE_SUMMARY)) in one
    finally:
        dlg.close()


def test_a_report_saved_before_the_colours_existed_says_so(tmp_path, qapp):
    """An older report carries no example colours, and the page says that
    rather than showing an empty frame.

    MUTATION: drop the else branch and this goes red.
    """
    dlg, run = _dialog(tmp_path, qapp)
    try:
        reps = _as(dlg, run, REPORT_TYPE_SUMMARY)
        old = dict(reps[0])
        old.pop("summary_patches", None)
        one = _text(dlg._report_body_html([old], for_pdf=True))
        assert "saved before ChromIQ chose example colours" in one
    finally:
        dlg.close()
