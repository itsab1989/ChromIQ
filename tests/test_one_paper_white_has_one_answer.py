"""R24-F2 — one measurement, one paper white, one number, everywhere.

Round 24, driving ChromIQ's own `Demo-Switching` with the shipped defaults,
read ONE document that said three different things about one paper white:

    the detailed section           White - L* 95.4
    Overview of Measurement Metrics    Paper white L*   —
    the "Paper white (L*)" trend chart  no point at all

The report on disk is schema 5, which keeps paper white as
``{"L": 95.4, "a": …, "b": …}``; schemas 6 and 7 write
``{"loc": …, "lab": [L, a, b], "hex": …}``. Both shapes are on users' disks
and both are in ChromIQ's own demo projects. B8-396 taught the DETAILED
section to read either and left the other two on ``lab`` alone, so a reader
comparing two papers sees a dash and concludes the value was never measured --
it is on the page above -- and a trend whose whole job is to show drift over a
year silently drops every measurement written before the shape changed, with
nothing anywhere saying a point is missing.

`workflow.measurement_report.point_lightness` is the one reader now, and this
file is what keeps the other three from growing back.
"""
from __future__ import annotations

import json
import os
import re

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest                                                  # noqa: E402
from PyQt6.QtWidgets import QApplication                       # noqa: E402

WHITE_L = 95.4
BLACK_L = 6.2


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _the_older_shape(payload: dict) -> dict:
    """Rewrite a report's two extremes the way schema 5 wrote them."""
    payload["schema"] = 5
    payload["paper_white"] = {"L": WHITE_L, "a": -0.3, "b": 2.1}
    payload["max_black"] = {"L": BLACK_L, "a": 0.2, "b": -1.4}
    return payload


def _a_project_holding_both_shapes(tmp_path):
    """Two dated measurements: the older one in schema 5's shape, the newer
    one exactly as ChromIQ writes it today.

    The newer one is the CONTROL. It is what round 24 read beside the dash,
    and it is what says a failure here is about the shape and not about the
    fixture.

    **AND THE OLDER DATE'S MEASUREMENT IS GONE**, which is not tidying: a
    saved report whose own `.ti3` is still there is REBUILT from it
    (`_report_needs_rebuilding`), and the rebuild writes today's shape, so a
    fixture that keeps the file measures the rebuild and never the reader.
    That is also why this is reachable on a real disk at all -- the report
    round 24 read is dated 2026-05-02 and the run has been measured again
    since, which is the ordinary life of a run.
    """
    from tests.test_a_generated_report_is_one_document import _messy_project

    s, fm, run, vs = _messy_project(tmp_path, dates=2)
    old = sorted((vs[0].dir / "reports").glob("report_*.json"))
    assert old, "the fixture saved no report for the older date"
    for f in old:
        f.write_text(json.dumps(_the_older_shape(
            json.loads(f.read_text(encoding="utf-8")))), encoding="utf-8")
    vs[0].measurement_ti3.unlink()
    return s, fm, run, vs


def _window(s, ti3, qapp):
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    dlg = MeasurementReportDialog(s, None, initial_ti3=ti3)
    dlg.show()
    qapp.processEvents()
    # **FROM "New report…" (B8-490).** Since Knut's beta-25 ruling a window
    # that opens showing a saved report brings that report's own settings and
    # its own measurement ticks with it, and a per-measurement record is about
    # ONE date, so the window comes up covering one measurement where these
    # checks need the history. "New report…" is the control that means "start
    # from the defaults with everything loaded" (it clears `_hidden_runs`),
    # which is the state these checks are about, and it repaints, which a
    # setting deliberately does not.
    #
    # It used to tick "Show all measurement runs" here as well. That box was
    # removed with the feature behind it (B8-590, Knut 2026-09-20: *"only the
    # selected/ticked measurements shall be part of the report when
    # created/updated (always)"*), so covering the whole history is the
    # "Select all" button he asked for in its place.
    dlg._saved_combo.setCurrentIndex(0)
    qapp.processEvents()
    dlg._select_all_btn.click()
    dlg._detail_check.setChecked(True)
    qapp.processEvents()
    assert dlg._hidden_runs == set(), dlg._hidden_runs
    dlg._render()
    qapp.processEvents()
    return dlg


def _row_cells(html: str, label: str) -> str:
    """The Overview table row for *label*, as raw html."""
    i = html.find(label)
    assert i >= 0, f"the document has no {label!r} row at all"
    end = html.find("</tr>", i)
    return html[i:end if end > 0 else len(html)]


# ---- the reader itself ----------------------------------------------------
def test_the_one_reader_knows_both_shapes(tmp_path):
    """`point_lightness` is public because three places need it.

    MUTATION: drop the ``{"L": …}`` branch and every test in this file goes
    red at once.
    """
    from workflow.measurement_report import point_lightness

    assert point_lightness({"L": WHITE_L, "a": 0.0, "b": 0.0}) == WHITE_L
    assert point_lightness({"lab": [WHITE_L, 0.0, 0.0]}) == WHITE_L
    assert point_lightness({}) is None
    assert point_lightness(None) is None


# ---- the three places -----------------------------------------------------
def test_the_trend_has_a_point_for_the_older_shape(tmp_path, qapp):
    """The chart drew no point at all for it, and said nothing about that.

    MUTATION, proved to land: put ``if w and w.get("lab")`` back in
    `report_trend`.
    """
    s, _fm, _run, vs = _a_project_holding_both_shapes(tmp_path)
    dlg = _window(s, vs[-1].measurement_ti3, qapp)
    try:
        whites = [p.get("white_L") for p in dlg._trend_series]
        blacks = [p.get("black_L") for p in dlg._trend_series]
        assert WHITE_L in whites, (
            f"the paper-white trend has no point for the measurement whose "
            f"report is in the older shape: {whites}")
        assert BLACK_L in blacks, (
            f"the black trend has no point for it either: {blacks}")
        assert None not in whites, (
            f"a measurement contributes an empty point: {whites}")
    finally:
        dlg.close()


def test_the_overview_table_prints_it_rather_than_a_dash(tmp_path, qapp):
    """The dash a reader takes for "not measured".

    MUTATION, proved to land: read ``(r.get("paper_white") or {}).get("lab",
    [None])[0]`` again in the Overview row getters.
    """
    s, _fm, _run, vs = _a_project_holding_both_shapes(tmp_path)
    dlg = _window(s, vs[-1].measurement_ti3, qapp)
    try:
        html = dlg._report_body_html(dlg._runs_for_report(), for_pdf=True)
        white = _row_cells(html, "Paper white L*")
        black = _row_cells(html, "Black L*")
        assert "95.4" in white, (
            f"the Overview table has no number for the older shape: {white!r}")
        assert "6.2" in black, (
            f"the Overview table has no black L* for it either: {black!r}")
        assert "—" not in re.sub(r"<[^>]+>", "", white), (
            f"the Overview table still prints a dash for a measurement whose "
            f"paper white is on the page above: {white!r}")
    finally:
        dlg.close()


def test_the_detailed_section_and_the_table_say_the_same_number(tmp_path,
                                                               qapp):
    """The third place, and the one B8-396 already fixed: this is what makes
    the document self-contradictory rather than merely quiet."""
    s, _fm, _run, vs = _a_project_holding_both_shapes(tmp_path)
    dlg = _window(s, vs[-1].measurement_ti3, qapp)
    try:
        html = dlg._report_body_html(dlg._runs_for_report(), for_pdf=True)
        assert "L* 95.4" in html, (
            "the detailed section does not print the paper white either, so "
            "this fixture is not the one round 24 measured")
        assert "95.4" in _row_cells(html, "Paper white L*"), (
            "the detailed section and the Overview table disagree about one "
            "paper white, in one document")
    finally:
        dlg.close()


def test_the_swatch_line_prints_a_and_b_as_well_as_l(tmp_path, qapp):
    """K5, Knut on beta 34: *"White (1) - L* 100.0"* beside a LIGHT BLUE
    swatch. The swatch was right (the demo's white was Lab 100 / -2.4 / -19.4)
    and the line printed only L*, so nothing on the page said why it was blue.
    Both record shapes carry a* and b*, so both print them."""
    from workflow.measurement_report import point_lab
    assert point_lab({"lab": [100.0, -2.39, -19.38]}) == (100.0, -2.39, -19.38)
    assert point_lab({"L": 95.4, "a": -0.3, "b": 2.1}) == (95.4, -0.3, 2.1)
    assert point_lab({"L": 95.4}) is None
    assert point_lab(None) is None
    s, _fm, _run, vs = _a_project_holding_both_shapes(tmp_path)
    dlg = _window(s, vs[-1].measurement_ti3, qapp)
    try:
        html = dlg._report_body_html(dlg._runs_for_report(), for_pdf=True)
        assert "L* 95.4, a* -0.3, b* 2.1" in html
        assert "L* 6.2, a* 0.2, b* -1.4" in html
    finally:
        dlg.close()


def test_the_line_never_prints_nan_or_minus_zero(tmp_path, qapp):
    """ROUND A (A-7), 2026-09-22: `point_lab` handed "b* nan" and "a* -0.0"
    to the page. A NaN in a* or b* falls back to the one number the record
    has; a value that rounds to zero prints "0.0".

    MUTATION: drop the `math.isfinite` check, or the `+ 0.0`, and this goes
    red.
    """
    s, _fm, _run, vs = _a_project_holding_both_shapes(tmp_path)
    old = sorted((vs[0].dir / "reports").glob("report_*.json"))
    for f in old:
        p = json.loads(f.read_text(encoding="utf-8"))
        p["paper_white"] = {"L": WHITE_L, "a": -0.04, "b": 2.1}
        p["max_black"] = {"L": BLACK_L, "a": float("nan"), "b": -1.4}
        f.write_text(json.dumps(p), encoding="utf-8")
    dlg = _window(s, vs[-1].measurement_ti3, qapp)
    try:
        html = dlg._report_body_html(dlg._runs_for_report(), for_pdf=True)
        assert "nan" not in html.lower()
        assert "a* -0.0" not in html
        assert "L* 95.4, a* 0.0, b* 2.1" in html
        assert "L* 6.2" in html
    finally:
        dlg.close()
