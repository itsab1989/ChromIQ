"""The findings of the two challenge rounds before 4.3.0-beta.37, each held.

The rounds' reports are on the owner's Desktop, ChromIQ-beta37-proof/
challenge-A/REPORT.md and challenge-B/REPORT.md; each test names the finding
it holds and the mutation it was proved red against.
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtGui import QColor, QImage, QPainter          # noqa: E402

import ui.dialogs.measurement_report_dialog as mrd        # noqa: E402


# ---------------------------------------------------------------------------
# H6: a trend series with a single value draws that value
# ---------------------------------------------------------------------------
def _paint(chart, w=640, h=176) -> QImage:
    chart.resize(w, h)
    img = QImage(w, h, QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(0xFFFFFFFF)
    p = QPainter(img)
    chart.render(p)
    p.end()
    return img


def _count(img, rgb, x0=0, x1=None) -> int:
    n = 0
    for y in range(img.height()):
        for x in range(x0, x1 if x1 is not None else img.width()):
            c = img.pixelColor(x, y)
            if abs(c.red() - rgb[0]) < 40 and abs(c.green() - rgb[1]) < 40 \
                    and abs(c.blue() - rgb[2]) < 40:
                n += 1
    return n


def test_a_series_with_one_value_is_drawn_as_a_point(qapp):
    """Round B, H6: "The same chart measured again" was 1.45 and PASS in the
    table on the third of three dates, and the Repeatability graph sized its
    axis for it and drew nothing, in the window and in the PDF (which renders
    this same widget off screen).

    MUTATION (proved red 2026-09-23): put `if len(poly) < 2: continue` back
    in `_TrendChart.paintEvent`; the magenta point is gone."""
    series = [{"created": "2026-12-0%dT10:00:00" % (i + 1),
               "a": 0.5 + 0.1 * i, "b": 1.45 if i == 2 else None}
              for i in range(3)]
    metrics = [("a", QColor("#000000"), lambda pt: pt.get("a")),
               ("b", QColor("#ff00ff"), lambda pt: pt.get("b"))]
    chart = mrd._TrendChart()
    chart.set_data(series, metrics, dark=False)
    img = _paint(chart)
    # the legend carries a magenta dot of its own at the top left, so count
    # only below the legend band
    legend_h = 30
    plot = img.copy(0, legend_h, img.width(), img.height() - legend_h)
    assert _count(plot, (255, 0, 255)) >= 20, (
        "the only value of the series is not drawn")
    # and it is at the THIRD date, the right-hand end of the axis
    assert _count(plot, (255, 0, 255), x0=img.width() - 60) >= 20


# ---------------------------------------------------------------------------
# H3: a Printing record grades nothing, so it neither explains a PASS nor
# says where a verdict came from
# ---------------------------------------------------------------------------
def _visible(dlg) -> str:
    import html as _html
    import re
    body = dlg._report_body_html(dlg._runs_for_report(), for_pdf=True)
    return _html.unescape(re.sub(r"<[^>]+>", " ", body))


def _stamped_profiling_run(tmp_path, set_id, label):
    from core.file_manager import Project
    from workflow import measurement_report as mr
    from workflow import run_compliance as rc
    from tests.test_report_judging import _colours, _ramp, _write_ti3
    proj = Project.create(tmp_path / "P", "P")
    run = proj.current_run()
    run.ensure_dir()
    ti3 = run.dir / f"{run.stem}.ti3"
    _write_ti3(ti3, _ramp(16) + _colours(), verification=False)
    rep = mr.build_report(ti3)
    mr.stamp_verdict(rep, rc.run_limits(run, {}).limits,
                     set_id=set_id, set_label=label)
    mr.save_report(rep, ti3.parent)
    return run, ti3


def _settings(tmp_path):
    from PyQt6.QtCore import QSettings
    from core.settings import AppSettings
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    return s


_CAVEAT = "It is not proof that the print meets the standard"
_PROVENANCE = "This verdict was recorded against the limit set"


def test_a_printing_record_carries_no_standard_caveat_and_no_provenance(
        qapp, tmp_path):
    """Round B, H3: the Printing record (not graded) printed the standard's
    disclaimer ("an indication that the print would likely meet the
    standard") and, under each sheet, "This verdict was recorded when the
    report was saved, against the limit set Custom ISO 12647-7", beside
    "This sheet is not graded".

    MUTATION (proved red 2026-09-23): drop `and not self._ungraded_by_type()`
    from the caveat block in `_report_results_html`, or from the provenance
    line in `_run_detail_html`; either goes red."""
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    from workflow import measurement_report as mr
    run, ti3 = _stamped_profiling_run(tmp_path, "custom_iso_12647_7",
                                      "Custom ISO 12647-7")
    dlg = MeasurementReportDialog(_settings(tmp_path), None, initial_ti3=ti3)
    try:
        assert dlg._report_type_now() == mr.REPORT_TYPE_RECORD
        dlg._detail_check.setChecked(True)
        text = _visible(dlg)
        assert "not graded" in text
        assert _CAVEAT not in text, "a record that grades nothing explains a PASS"
        assert _PROVENANCE not in text, (
            "a record that grades nothing says where its verdict came from")
        # "Judged against" stays: Knut's earlier design names the set, and
        # whether it should is a question put to him (the register)
        assert "Judged against" in text
    finally:
        dlg.deleteLater()


def test_a_graded_verification_keeps_both(qapp, tmp_path):
    """The other half, or the test above passes on a report that never says
    either: the same set on a dated verification's Full colour check still
    carries the caveat and the provenance."""
    from tests.test_report_window_limit_controls import _verified_run
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    from workflow import measurement_report as mr
    from workflow import run_compliance as rc
    proj, run, ti3s = _verified_run(tmp_path, dates=1)
    rep = mr.build_report(ti3s[0])
    mr.stamp_verdict(rep, rc.run_limits(run, {}).limits,
                     set_id="custom_iso_12647_7", set_label="Custom ISO 12647-7")
    mr.save_report(rep, ti3s[0].parent)
    dlg = MeasurementReportDialog(_settings(tmp_path), None, initial_ti3=ti3s[0])
    try:
        rc.set_run_report_type(run, mr.REPORT_TYPE_FULL)
        dlg._forget_limits()
        dlg._sync_limit_controls()
        dlg._refresh()
        dlg._detail_check.setChecked(True)
        text = _visible(dlg)
        assert _CAVEAT in text
        assert _PROVENANCE in text
    finally:
        dlg.deleteLater()
