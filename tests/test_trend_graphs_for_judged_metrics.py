"""#182 K20/K21: a trend graph for every judged metric group, with its limit.

Knut, 5785414710: *"a graph tab can be hidden and not printed in a generated
pdf, if the belonging metric is missing or not used for a report, so that a
graph is only shown and printed IF the metric has values tested agains a
threshold"*, and *"Similar horizontal dotted lines, that represent the
threshold values each graphs metric is judged against ... shall dynamically
follow the threshold settings relevant for the report, given by the judged
against selection."* 5787117741: *"each group show maximum two metrics with
their own independent threshold level line"*, related metrics only, and a line
outside the y-range is simply out of view. 5787380408: keep "Paper white
(L*)", add "Paper white difference (ΔE00)".

Every test below names the mutation it was proved red against.
"""
from __future__ import annotations

import os
from datetime import datetime

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtCore import QSettings                        # noqa: E402
from PyQt6.QtGui import QColor, QImage, QPainter          # noqa: E402
from PyQt6.QtWidgets import QApplication                  # noqa: E402

from core.file_manager import Project                     # noqa: E402
from core.settings import AppSettings                     # noqa: E402
from workflow import measurement_report as mr             # noqa: E402
from workflow.compliance_sets import (ROW_BY_ID, Limit,   # noqa: E402
                                      effective_limits)
from workflow.ti3_analysis import mark_verification_ti3   # noqa: E402

import ui.dialogs.measurement_report_dialog as mrd        # noqa: E402
from tests.test_report_judging import _colours, _ramp, _write_ti3   # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _settings(tmp_path) -> AppSettings:
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    return s


def _run(tmp_path, limits: dict, set_id: str = "chromiq_default",
         n_dates: int = 3):
    """A run with *n_dates* dated verifications, each saved with a verdict
    recorded against *limits*, which is what "Judged against" then shows."""
    proj = Project.create(tmp_path / "P", "P")
    run = proj.current_run()
    run.ensure_dir()
    first = None
    for i in range(n_dates):
        v = run.new_verification(datetime(2026, 1, 1 + i, 10, 0, 0))
        v.ensure_dir()
        raw = v.dir / "P.ti3"
        _write_ti3(raw, _ramp(16) + _colours(), verification=False)
        mark_verification_ti3(raw).rename(v.dir / f"{run.verify_stem}.ti3")
        target = v.dir / f"{run.verify_stem}.ti3"
        rep = mr.build_report(target)
        mr.stamp_verdict(rep, limits, set_id=set_id, set_label=set_id)
        mr.save_report(rep, v.dir)
        first = first or target
    return run, first


def _report_set(s, limits: dict, set_id: str) -> None:
    """Make *limits* the numbers a NEW report of the window is judged
    against (K31: the report's own set, so every ticked date is judged
    against it, whatever each date's own report recorded): the Preferences
    default set, with *limits* as its overrides."""
    from core.settings import store_compliance_overrides
    from workflow.compliance_sets import (SET_BY_ID, effective_limits,
                                          limits_to_json)
    base = limits_to_json(effective_limits(set_id, {}))
    want = limits_to_json(limits)
    ov = {}
    for rid, lim in limits.items():
        if want.get(rid) != base.get(rid):
            ov[rid] = (None if getattr(lim, "kind", "") == "none"
                       else float(lim.number))
    if ov and SET_BY_ID[set_id].editable:
        store_compliance_overrides(s, {set_id: ov})
    s.set("compliance_default_set", set_id)


def _open(tmp_path, qapp, limits, set_id="chromiq_default"):
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    _run_, ti3 = _run(tmp_path, limits, set_id)
    s = _settings(tmp_path)
    _report_set(s, limits, set_id)
    dlg = MeasurementReportDialog(s, None, initial_ti3=ti3)
    dlg._select_all_btn.click()
    qapp.processEvents()
    # The page and the graphs are repainted together, as Generate does; the
    # PDF is built from the page as it was last drawn.
    dlg._refresh()
    qapp.processEvents()
    return dlg


def _visible(dlg) -> dict:
    t = dlg._trend_tabs
    return {t.tabText(i): t.isTabVisible(i) for i in range(t.count())}


def _group(dlg, key):
    return dlg._trend_groups[key]


# ---------------------------------------------------------------------------
# the groups themselves
# ---------------------------------------------------------------------------
def test_every_group_holds_at_most_two_related_rows_that_exist():
    """At most two metrics per tab, real rows, one unit per tab, and every
    trend row belongs to exactly one tab.

    **ONE EXCEPTION, KNUT'S (K47, #182 5840152058):** the control strip's
    tab holds its average, its 95th percentile and its maximum, since a set
    may limit all three and every limited row has its line.

    MUTATION, proven red: add ``("ramps_30_70_dl_max", ...)`` as a third
    entry of the "grey" group; or put ``ramps_30_70_dl_max`` (ΔL*) into the
    grey group (ΔCh)."""
    seen = []
    for key, title, rows in mrd._TREND_GROUPS:
        most = 3 if key == "strip" else 2
        assert 1 <= len(rows) <= most, f"{key}: {len(rows)} metrics on one tab"
        units = {ROW_BY_ID[rid].unit for rid, _w, _c in rows}
        assert len(units) == 1, f"{key} mixes units {units}"
        seen += [rid for rid, _w, _c in rows]
    assert sorted(seen) == sorted(mr.TREND_ROW_IDS)
    assert len(seen) == len(set(seen))


def test_the_paper_white_tabs_are_both_there_in_knuts_order(qapp, tmp_path):
    """"Paper white (L*)" stays, "Paper white difference (ΔE00)" sits beside it, and the
    four tabs Knut asked to keep are still there.

    MUTATION, proven red: add "Paper white difference (ΔE00)" after "Cube corners (ΔE00)"."""
    dlg = _open(tmp_path, qapp, effective_limits("chromiq_default", {}))
    try:
        names = [dlg._trend_tabs.tabText(i)
                 for i in range(dlg._trend_tabs.count())]
        assert names[:5] == ["Colour accuracy (ΔE00)", "Paper white (L*)",
                             "Paper white difference (ΔE00)", "Darkest black (L*)",
                             "Cube corners (ΔE00)"]
    finally:
        dlg.deleteLater()


# ---------------------------------------------------------------------------
# the series
# ---------------------------------------------------------------------------
def test_the_trend_series_carries_each_rows_judged_value():
    """The point holds the number `row_values` gives the results table.

    MUTATION, proven red: drop ``pt["rows"] = rows`` from `report_trend`."""
    rep = {"created": "2026-01-01T10:00:00", "chart": "x",
           "grey_balance": {"eligible": True, "avg": 0.61, "max": 1.4},
           "evenness": {"eligible": True, "pairwise": 1.2, "from_mean": 0.7,
                        "noise_pairwise_p95": 0.3,
                        "noise_from_mean_p95": 0.2}}
    [pt] = mr.report_trend([rep])
    assert pt["rows"]["grey_balance_neutral_ramp_avg"] == pytest.approx(0.61)
    assert pt["rows"]["grey_balance_neutral_ramp_max"] == pytest.approx(1.4)
    assert pt["rows"]["uniformity_sd"] == pytest.approx(1.2)
    assert pt["rows_noise"]["uniformity_sd"] == pytest.approx(0.3)


def test_a_withheld_evenness_value_is_not_plotted_against_its_limit():
    """The table reads N-A when the sheet's noise is not below the limit; the
    graph must not draw that value against the same line.

    MUTATION, proven red: return ``v`` before the `evenness_withheld` check in
    `_trend_row_value`."""
    pt = {"rows": {"uniformity_sd": 2.0}, "rows_noise": {"uniformity_sd": 1.6}}
    assert mrd._trend_row_value(pt, "uniformity_sd", 1.5) is None
    assert mrd._trend_row_value(pt, "uniformity_sd", 3.0) == 2.0
    quiet = {"rows": {"uniformity_sd": 2.0}, "rows_noise": {"uniformity_sd": 0.4}}
    assert mrd._trend_row_value(quiet, "uniformity_sd", 1.5) == 2.0


# ---------------------------------------------------------------------------
# which tabs show, and their lines
# ---------------------------------------------------------------------------
def test_a_tab_shows_only_while_one_of_its_rows_is_judged(qapp, tmp_path):
    """ChromIQ default limits the grey rows and not the tone ramp, so Grey
    balance shows and Tone does not; the four original tabs always show.

    MUTATION, proven red: ``bool(metrics)`` -> ``True`` in `_trend_plan`."""
    dlg = _open(tmp_path, qapp, effective_limits("chromiq_default", {}))
    try:
        judged = dlg._judged_trend_limits()
        assert "grey_balance_neutral_ramp_avg" in judged, (
            f"the fixture judges no grey row ({judged}), so it proves nothing")
        assert "ramps_30_70_dl_max" not in judged
        vis = _visible(dlg)
        assert vis["Grey balance (ΔCh)"] is True
        assert vis["Tone ramps 30 to 70 % (ΔL*)"] is False
        assert vis["Paper white difference (ΔE00)"] is False
        for keep in ("Colour accuracy (ΔE00)", "Paper white (L*)",
                     "Darkest black (L*)", "Cube corners (ΔE00)"):
            assert vis[keep] is True, keep
    finally:
        dlg.deleteLater()


def test_a_limit_on_the_tone_row_brings_its_tab(qapp, tmp_path):
    """The same measurements judged against a column that limits the tone
    ramp: the Tone tab appears, with its line at that limit.

    MUTATION, proven red: read the judged rows from the window's run set
    (``self._window_limits().limits``) instead of the verdict rows: the run is
    bound to nothing, so the tone row is never found."""
    lim = dict(effective_limits("chromiq_default", {}))
    lim["ramps_30_70_dl_max"] = Limit.value(2.5)
    dlg = _open(tmp_path, qapp, lim)
    try:
        assert _visible(dlg)["Tone ramps 30 to 70 % (ΔL*)"] is True
        assert [v for v, _w, _c in _group(dlg, "tone")._limit_lines] == [2.5]
    finally:
        dlg.deleteLater()


def test_each_line_sits_at_the_limit_the_report_was_judged_against(
        qapp, tmp_path):
    """Judged against ChromIQ tight, the grey lines are tight's 1.0 and 2.0,
    not the 1.5 and 3.0 of the default the unbound run would fall back to.

    MUTATION, proven red: build the judged rows in `_judged_trend_limits`
    from ``self._window_limits().limits`` instead of `_verdict_rows` (the
    unbound run falls back to ChromIQ default, so the lines read 1.5 / 3.0)."""
    dlg = _open(tmp_path, qapp, effective_limits("chromiq_tight", {}),
                set_id="chromiq_tight")
    try:
        lines = _group(dlg, "grey")._limit_lines
        assert [(v, w) for v, w, _c in lines] == [(1.0, "Avg"), (2.0, "Max")]
        # each line in its own metric's colour, one line per plotted metric
        cols = [c.name() for _v, _w, c in lines]
        assert cols == [QColor(c).name() for _r, _w, c in
                        dict((k, r) for k, _t, r in mrd._TREND_GROUPS)["grey"]]
        assert len(_group(dlg, "grey")._metrics) == len(lines)
    finally:
        dlg.deleteLater()


def test_only_the_judged_rows_of_a_group_are_plotted(qapp, tmp_path):
    """A column that limits the grey average and not the grey largest: the tab
    shows one metric and one line, never a metric with no limit beside it.

    MUTATION, proven red: drop ``if rid not in judged: continue`` (and give an
    unjudged row ``lim = None``)."""
    lim = dict(effective_limits("chromiq_default", {}))
    lim["grey_balance_neutral_ramp_max"] = Limit.none()
    dlg = _open(tmp_path, qapp, lim)
    try:
        g = _group(dlg, "grey")
        assert [m[0] for m in g._metrics] == [
            # the row's label, with its unit since K25
            "Average ΔCh, grey balance of the grey ramp"]
        assert [v for v, _w, _c in g._limit_lines] == [1.5]
    finally:
        dlg.deleteLater()


def test_a_report_that_judges_nothing_shows_none_of_the_new_tabs(
        qapp, tmp_path, monkeypatch):
    """The Printing record judges nothing (every row INFO), so no
    judged-metric tab is shown, whatever the set limits.

    MUTATION, proven red: accept ``INFO`` as judged in
    `_judged_trend_limits`."""
    dlg = _open(tmp_path, qapp, effective_limits("chromiq_default", {}))
    try:
        # The Printing record is what `_ungraded_by_type` answers True for;
        # a verification window does not offer it (K24), so the type's
        # answer is given directly rather than through a pulldown that does
        # not list it.
        monkeypatch.setattr(type(dlg), "_ungraded_by_type", lambda self: True)
        dlg._refresh_trend()
        qapp.processEvents()
        assert dlg._judged_trend_limits() == {}
        vis = _visible(dlg)
        assert not any(vis[t()] for _k, t, _r in mrd._TREND_GROUPS)
    finally:
        dlg.deleteLater()


# ---------------------------------------------------------------------------
# the drawing
# ---------------------------------------------------------------------------
def _paint(chart, w=640, h=176) -> QImage:
    chart.resize(w, h)
    img = QImage(w, h, QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(0xFFFFFFFF)
    p = QPainter(img)
    chart.render(p)
    p.end()
    return img


def _count(img, rgb) -> int:
    n = 0
    for y in range(img.height()):
        for x in range(img.width()):
            c = img.pixelColor(x, y)
            if abs(c.red() - rgb[0]) < 40 and abs(c.green() - rgb[1]) < 40 \
                    and abs(c.blue() - rgb[2]) < 40:
                n += 1
    return n


def test_a_line_outside_the_data_range_neither_shows_nor_moves_the_axis(qapp):
    """Knut: a limit far from the trend is out of view until the data reaches
    it. The axis is the data's alone; a line inside it is drawn.

    MUTATION, proven red: include the limit-line values in `_y_range`'s
    ``vals`` (the axis then stretches to 5.0)."""
    series = [{"created": "2026-01-0%dT10:00:00" % (i + 1),
               "rows": {"grey_balance_neutral_ramp_avg": 0.3 + 0.02 * i}}
              for i in range(4)]
    metrics = [("m", QColor("#000000"),
                lambda pt: mrd._trend_row_value(pt, "grey_balance_neutral_ramp_avg"))]
    far = mrd._TrendChart()
    far.set_data(series, metrics, dark=False,
                 limit_lines=[(5.0, "Max", QColor("#ff00ff"))])
    near = mrd._TrendChart()
    near.set_data(series, metrics, dark=False,
                  limit_lines=[(0.3, "Avg", QColor("#ff00ff"))])
    bare = mrd._TrendChart()
    bare.set_data(series, metrics, dark=False)
    assert far._y_range() == bare._y_range(), (
        f"the axis moved for a line: {far._y_range()} vs {bare._y_range()}")
    assert _count(_paint(far), (255, 0, 255)) == 0
    assert _count(_paint(near), (255, 0, 255)) > 100


# ---------------------------------------------------------------------------
# the PDF
# ---------------------------------------------------------------------------
def _export(dlg, tmp_path, monkeypatch):
    sizes, titles_html = [], []
    real_resize = mrd._TrendChart.resize
    real_pdf_html = type(dlg)._pdf_html

    def _resize(self, *a):
        sizes.append(tuple(a) if len(a) == 2 else (a[0].width(), a[0].height()))
        return real_resize(self, *a)

    def _pdf_html(self, runs, charts_html):
        titles_html.append(charts_html)
        return real_pdf_html(self, runs, charts_html)

    import ui.widgets as _w
    monkeypatch.setattr(_w, "save_file_dialog",
                        lambda *a, **k: str(tmp_path / "out.pdf"))
    from PyQt6.QtGui import QDesktopServices
    monkeypatch.setattr(QDesktopServices, "openUrl",
                        staticmethod(lambda *a, **k: True))
    monkeypatch.setattr(mrd._TrendChart, "resize", _resize)
    monkeypatch.setattr(type(dlg), "_pdf_html", _pdf_html)
    dlg._export_pdf()
    return sizes, (titles_html[0] if titles_html else "")


def test_the_pdf_prints_the_shown_tabs_and_leaves_the_hidden_out(
        qapp, tmp_path, monkeypatch):
    """Grey balance is printed, Tone is not, and each chart is one table so a
    title never stays behind at the foot of a page.

    MUTATION, proven red: drop ``if not shown: continue`` in `_export_pdf`
    (Tone is printed); or go back to a bare ``<div>`` + ``<img>``."""
    dlg = _open(tmp_path, qapp, effective_limits("chromiq_default", {}))
    try:
        if not dlg._trend_de.has_trend():
            pytest.skip("no trend on this fixture, so nothing is printed")
        _sizes, html_ = _export(dlg, tmp_path, monkeypatch)
        assert "Grey balance (ΔCh)" in html_
        assert "Tone ramps 30 to 70 % (ΔL*)" not in html_
        assert "Paper white difference (ΔE00)" not in html_
        n_charts = html_.count("chart://")
        assert n_charts == sum(1 for e in dlg._trend_plan() if e[-1])
        assert html_.count("<table") == n_charts
    finally:
        dlg.deleteLater()


def test_colour_accuracy_is_printed_twice_as_tall(qapp, tmp_path, monkeypatch):
    """Knut: try the Colour accuracy y-axis about twice the screen height in
    the PDF, so small variations stay visible. The others keep their height.

    MUTATION, proven red: ``ch_h = _PDF_TREND_H`` for every chart."""
    assert mrd._PDF_ACCURACY_SCALE == 2
    dlg = _open(tmp_path, qapp, effective_limits("chromiq_default", {}))
    try:
        if not dlg._trend_de.has_trend():
            pytest.skip("no trend on this fixture, so nothing is printed")
        sizes, _html = _export(dlg, tmp_path, monkeypatch)
        pdf = [s for s in sizes if s[0] == 640]
        assert pdf[0] == (640, 2 * mrd._PDF_TREND_H)
        assert all(s == (640, mrd._PDF_TREND_H) for s in pdf[1:]), pdf
    finally:
        dlg.deleteLater()
