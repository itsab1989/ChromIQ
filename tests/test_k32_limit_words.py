"""K32, Knut on beta 41 (#182 5814107188): where a trend graph's limit words go.

*"The label for Avg threshold line is placed below the horizontal line, and
not to the left of the line and centre adjusted with the line, even though
there is space on the left side ... If there is no space on the left edge for
the threshold label (maybe because the label then would crash with the y-axis
numbered axis labels), then the label should find a better location, like on
top or below the threshold line it belongs to ... the label must be placed on
the top or bottom side that has the least conflict with other graph lines or
other horizontal threshold lines. This must be a general rule for all the
graphs label placement for the threshold lines."*

The rule is `_place_limit_words`, called by `_TrendChart.paintEvent`, which
paints the window's tabs and the PDF's graphs alike. These tests paint real
charts and measure the boxes the paint recorded (`_word_boxes`) against the
axis numbers, the other words and the data lines the same paint drew
(`_polys`), for every graph and for a seeded battery of shapes; the demo
projects are measured on screen by `scripts/drive_k32_report_rows_and_switch.py`
(scene "graphs").
"""
from __future__ import annotations

import math
import os
import random

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtCore import QPointF, QRectF                     # noqa: E402
from PyQt6.QtGui import QColor, QImage, QPainter             # noqa: E402
from PyQt6.QtWidgets import QApplication                     # noqa: E402

import ui.dialogs.measurement_report_dialog as mrd          # noqa: E402

L = 40.0


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _paint(chart, w=640, h=176):
    chart.resize(w, h)
    img = QImage(w, h, QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(0xFFFFFFFF)
    p = QPainter(img)
    chart.render(p)
    p.end()


def _chart(metric_values: "list[list]", lines: list, *, accuracy=False):
    """A chart with one polyline per list in *metric_values* and the limit
    lines ``[(value, word)]`` (the accuracy pair when *accuracy*)."""
    series = [{"created": f"2026-01-{i + 1:02d}T10:00:00",
               "rows": {f"m{k}": vals[i] for k, vals in
                        enumerate(metric_values)}}
              for i in range(len(metric_values[0]))]
    metrics = [(f"metric {k}", QColor("#3070c0"),
                (lambda pt, kk=k: (pt.get("rows") or {}).get(f"m{kk}")))
               for k in range(len(metric_values))]
    chart = mrd._TrendChart()
    if accuracy:
        chart.set_data(series, metrics, dark=False,
                       thresholds=tuple(v for v, _w in lines),
                       line_notes=[f"note {w}" for _v, w in lines])
    else:
        chart.set_data(series, metrics, dark=False,
                       limit_lines=[(v, w, QColor("#e0574b"))
                                    for v, w in lines],
                       line_notes=[f"note {w}" for _v, w in lines])
    return chart


def _geometry(chart):
    """The plot's top and height and the axis numbers' centres, as the paint
    computed them (from the chart's size and legend, like `paintEvent`)."""
    from PyQt6.QtGui import QFont, QFontMetrics
    font = QFont()
    font.setPixelSize(10)
    fm = QFontMetrics(font)
    w = max(1.0, chart.width() - L - 12.0)
    T = 24.0 + 13.0 * (chart._legend_rows(fm, L, w) - 1)
    h = max(1.0, chart.height() - T - 26.0)
    return T, h, [T + h * (1.0 - f) for f in (0.0, 0.5, 1.0)]


def _data_under(rect: QRectF, polys) -> float:
    return sum(mrd._segment_length_in(rect.adjusted(-1, -1, 1, 1), a, b)
               for poly in polys for a, b in zip(poly, poly[1:]))


def _crosses_a_line(rect: QRectF, line_ys) -> bool:
    r = rect.adjusted(-1, -1, 1, 1)
    return any(r.top() <= ly <= r.bottom() for ly in line_ys)


def _check(chart, where_msg=""):
    """Every rule of the placement, measured on what the paint recorded."""
    boxes = chart._word_boxes
    T, h, axis_ys = _geometry(chart)
    # the paint's own record wins: a chart measured after a resize and
    # before its next paint would otherwise be judged against the new size
    T, h, axis_ys = getattr(chart, "_plot_geom", (T, h, axis_ys))
    line_ys = [y for _r, _w, y in boxes]
    # 1. no two words print over each other
    for i, (a, _wa, _ya) in enumerate(boxes):
        for b, _wb, _yb in boxes[i + 1:]:
            assert not a.intersects(b), (where_msg, a, b)
    for rect, where, y in boxes:
        if where == "margin":
            # 2. a margin word is centred on its line, clear of the numbers
            assert rect.right() <= L, (where_msg, rect)
            assert rect.center().y() == pytest.approx(y), (where_msg, rect)
            assert all(abs(y - ay) >= mrd._WORD_AXIS_GAP
                       for ay in axis_ys), (where_msg, "on an axis number",
                                            rect)
            continue
        # 3. an inside word stays at the left end of its line
        assert rect.left() == pytest.approx(L + 3.0), (where_msg, rect)
        assert T - 0.01 <= rect.top() and rect.bottom() <= T + h + 0.01
        # 3b. it is inside only because the margin had no room for it
        margin_words = [yy for _r, w, yy in boxes if w == "margin"]
        assert (rect.width() - 2.0 > L - 6.0
                or any(abs(y - ay) < mrd._WORD_AXIS_GAP for ay in axis_ys)
                or any(abs(y - my) < mrd._WORD_WORD_GAP
                       for my in margin_words)), (
            where_msg, "a word went inside with room for it in the margin",
            rect)
        # 4. when either place right beside its line is clear (no word, no
        # line, no data), the word is in a clear place: measured here, on
        # the boxes and the polylines the paint recorded.
        others = [b for b, _w, _y in boxes if b is not rect]

        def clear(r):
            return (not any(r.adjusted(-1, -1, 1, 1).intersects(b)
                            for b in others)
                    and not _crosses_a_line(r, line_ys)
                    and _data_under(r, chart._polys) == 0.0)
        beside = [QRectF(rect.left(), min(max(top, T), T + h - 14.0),
                         rect.width(), 14.0)
                  for top in (y - 16.0, y + 2.0)]
        if any(clear(r) for r in beside):
            assert clear(rect), (where_msg, "the word is not in a clear place "
                                 "while one beside its line was", where,
                                 rect)


# ---------------------------------------------------------------------------
# Knut's case
# ---------------------------------------------------------------------------
def test_knuts_grey_balance_avg_goes_to_the_margin_when_there_is_room(qapp):
    """Grey balance: the Max line lands on an axis number, the Avg line is
    clear of every number, and a data line runs just under Avg's line. The
    Avg word belongs in the margin, centred on its line; it used to be sent
    inside with Max and printed under its line, over the data line.

    MUTATIONS, each proved to land: never allow the margin (`fits = False`);
    let one word that does not fit send every word inside (the rule before
    K32)."""
    # axis 0 .. 3.36 (data max 3.0 * 1.12): numbers at 0, 1.68 and 3.36
    # Avg at 1.2 is 18 px from the nearest number; data runs 4 px under it.
    chart = _chart([[1.1, 1.12, 3.0, 1.1]], [(1.2, "Avg"), (1.68, "Max")])
    _paint(chart)
    where = {chart._hits[k][1]: w for k, (_r, w, _y) in
             enumerate(chart._word_boxes)}
    assert where["note Avg"] == "margin", where
    assert where["note Max"] in ("above", "below"), where
    _check(chart, "knut")


def test_a_word_inside_goes_to_the_side_with_less_data_under_it(qapp):
    """A line on an axis number, data just ABOVE it at the left: the word
    goes below. And data just below: above.

    MUTATION, proved to land: always "above" (drop the "below" candidate)."""
    # axis 0 .. 2.24; the line at 1.12 is on the middle number
    up = _chart([[1.25, 1.3, 2.0, 2.0]], [(1.12, "Avg")])
    _paint(up)
    [(rect, where, _y)] = up._word_boxes
    assert where == "below", (where, rect)
    _check(up, "data above")
    down = _chart([[1.0, 0.98, 2.0, 2.0]], [(1.12, "Avg")])
    _paint(down)
    [(rect, where, _y)] = down._word_boxes
    assert where == "above", (where, rect)
    _check(down, "data below")


def test_a_word_wider_than_the_margin_goes_inside(qapp):
    chart = _chart([[0.2, 2.0, 0.3]], [(0.7, "Averagely-long-word")])
    _paint(chart)
    [(_rect, where, _y)] = chart._word_boxes
    assert where != "margin"
    _check(chart, "wide word")


# ---------------------------------------------------------------------------
# every graph, and a battery of shapes
# ---------------------------------------------------------------------------
_TABS = [("accuracy", (("Avg", 0), ("Max", 1)))] + [
    (key, tuple((w(), k) for k, (_rid, w, _c) in enumerate(rows)))
    for key, _t, rows in mrd._TREND_GROUPS]


@pytest.mark.parametrize("tab,words", _TABS, ids=[t for t, _w in _TABS])
@pytest.mark.parametrize("size", [(640, 176), (900, 300)])
def test_every_graph_places_every_word_by_the_one_rule(qapp, tab, words,
                                                       size):
    """For each graph (the accuracy pair and each judged-metric tab, with its
    own words), 60 seeded shapes: one or two data lines of 3 to 9 dates, and
    the graph's limit lines anywhere in and around the data, often on an axis
    number or on each other. Every placement obeys every rule `_check`
    measures.

    MUTATIONS, each proved to land: drop the axis-number test from the
    margin's `fits` (a margin word on a number); drop the "below" candidate
    (a word over a data line with the other side free); drop the words
    already placed from `_word_conflict` (two words over each other)."""
    rnd = random.Random(f"{tab}-{size}")
    for case in range(60):
        n = rnd.randint(3, 9)
        k = 1 if len(words) == 1 else rnd.randint(1, 2)
        top = rnd.choice([1.0, 2.0, 3.0, 4.5])
        data = [[round(rnd.uniform(0.05, top), 2) for _ in range(n)]
                for _ in range(k)]
        vmax = max(max(d) for d in data) * 1.12
        lines = []
        for word, _i in words:
            pick = rnd.random()
            if pick < 0.3:                       # on an axis number
                v = rnd.choice([0.0, vmax / 2.0, vmax])
            elif pick < 0.45 and lines:          # on the other line
                v = lines[-1][0] + rnd.uniform(-0.03, 0.03) * vmax
            else:
                v = rnd.uniform(0.0, vmax)
            lines.append((max(0.0, min(vmax, v)), word))
        chart = _chart(data, lines, accuracy=(tab == "accuracy"))
        _paint(chart, *size)
        assert len(chart._word_boxes) == len(lines), (tab, case)
        _check(chart, f"{tab} case {case} {data} {lines}")
