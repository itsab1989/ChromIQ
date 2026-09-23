"""#182 K25: the trend graphs explain their lines, their red x and themselves.

Knut, 5789263863, the graph section:

* *"implement the feature in Colour accuracy tab dictating what happens when a
  threshold label comes close to a graph's line, or y-axis labels etc."* on
  every graph;
* *"all labels are given a description under each graph when printed as PDF
  ... On screen, when hovering over the labels on the lines, a tool-tip should
  appear with the same description"*;
* *"each graph must have, at most, a two-line description above its chart"*;
* *"all the graphs are showing the relevant units in the data labels"*;
* a withheld date is *"a small red x"*, at the neighbouring date's height, the
  mean of both, or just above the x-axis when neither has a point, with a
  tooltip and the same text in the PDF.

Every test below names the mutation it was proved red against.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtCore import QPointF                             # noqa: E402
from PyQt6.QtGui import QColor, QImage, QPainter, QTextDocument  # noqa: E402
from PyQt6.QtWidgets import QApplication                     # noqa: E402

from workflow.compliance_sets import ROW_BY_ID, effective_limits  # noqa: E402

import ui.dialogs.measurement_report_dialog as mrd          # noqa: E402
from tests.test_trend_graphs_for_judged_metrics import (    # noqa: E402
    _export, _open)

ROOT = Path(__file__).resolve().parents[1]
RED = (0xd6, 0x28, 0x28)


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _pt(day: int, **rows) -> dict:
    return {"created": f"2026-01-{day:02d}T10:00:00", "rows": dict(rows)}


def _paint(chart, w=640, h=176) -> QImage:
    chart.resize(w, h)
    img = QImage(w, h, QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(0xFFFFFFFF)
    p = QPainter(img)
    chart.render(p)
    p.end()
    return img


def _red_near(img, x, y, r=5) -> int:
    n = 0
    for yy in range(max(0, int(y) - r), min(img.height(), int(y) + r + 1)):
        for xx in range(max(0, int(x) - r), min(img.width(), int(x) + r + 1)):
            c = img.pixelColor(xx, yy)
            if (abs(c.red() - RED[0]) < 45 and abs(c.green() - RED[1]) < 45
                    and abs(c.blue() - RED[2]) < 45):
                n += 1
    return n


# ---------------------------------------------------------------------------
# the red x
# ---------------------------------------------------------------------------
def test_the_red_x_height_follows_knuts_three_cases():
    """One neighbour: its height. Both: their mean. Neither: the floor (None).
    The neighbours are the dates IMMEDIATELY beside the withheld one.

    MUTATION, proven red: search outwards for the nearest date with a value
    (``[0.5, None, None, 1.0]`` then puts index 1 at 0.75, not 0.5); or
    return ``before`` only (index 0 of ``[None, 2.0]`` becomes None)."""
    f = mrd._withheld_mark_value
    assert f([1.0, None, 3.0], 1) == pytest.approx(2.0)      # both: the mean
    assert f([None, 2.0], 0) == pytest.approx(2.0)           # after only
    assert f([2.0, None], 1) == pytest.approx(2.0)           # before only
    assert f([None, None, 1.0], 0) is None                   # neither: floor
    assert f([0.5, None, None, 1.0], 1) == pytest.approx(0.5)
    assert f([0.5, None, None, 1.0], 2) == pytest.approx(1.0)


def _even_chart(series, limit=1.5, dark=False):
    rid = "uniformity_sd"
    chart = mrd._TrendChart()
    metrics = [("Pairs (ΔE00)", QColor("#e0574b"),
                lambda pt: mrd._trend_row_value(pt, rid, limit))]
    chart.set_data(series, metrics, dark=dark,
                   limit_lines=[(limit, "Pairs", QColor("#e0574b"))],
                   line_notes=[mrd._limit_line_note("Pairs", limit, "ΔE00",
                                                     rid)],
                   withheld=[lambda pt: mrd._trend_withheld_reason(
                       pt, rid, limit)])
    return chart


def _noisy(day, v=1.0):
    return {**_pt(day, uniformity_sd=v), "rows_noise": {"uniformity_sd": 2.0}}


def _quiet(day, v):
    return {**_pt(day, uniformity_sd=v), "rows_noise": {"uniformity_sd": 0.2}}


def test_a_withheld_date_stays_on_the_axis_with_its_reason():
    """Beta 37 dropped the noisy date from the axis altogether: four dates
    ticked, three drawn, nothing said. It stays, as a red x, and its tooltip
    names the date, the metric and the table's own reason.

    MUTATION, proven red: drop ``or any(f is not None and f(pt) ...)`` from
    `set_data`'s ``has_any`` (the axis holds 3 dates and no mark)."""
    chart = _even_chart([_quiet(1, 0.4), _quiet(2, 0.6), _quiet(3, 0.5),
                         _noisy(4)])
    assert len(chart._series) == 4
    [(k, i, v, text)] = chart.withheld_marks()
    assert (k, i) == (0, 3) and v == pytest.approx(0.5)
    assert text.startswith("2026-01-04, Pairs (ΔE00): not judged, because "
                           "the measured sheet is too noisy")
    assert "2.00 ΔE00" in text and "1.50 ΔE00" in text


@pytest.mark.parametrize("series, idx, expect", [
    # one neighbour: at 0.6
    ([_quiet(1, 0.2), _quiet(2, 0.6), _noisy(3)], 2, 0.6),
    # both: the mean of 0.2 and 1.0
    ([_quiet(1, 0.2), _noisy(2), _quiet(3, 1.0)], 1, 0.6),
    # neither (the date after is withheld too): the floor
    ([_noisy(1), _noisy(2), _quiet(3, 0.8)], 0, None),
])
def test_the_red_x_is_painted_red_where_the_rule_puts_it(
        qapp, series, idx, expect):
    """The cross is drawn in red at the height the rule gives, and the floor
    case sits just above the x-axis, inside the plot.

    MUTATION, proven red: draw the cross with ``Qt.PenStyle.NoPen`` instead of
    its red pen (no red at its place); or draw the floor mark ON the axis line
    (``T + h``) instead of ``_WITHHELD_FLOOR_PX`` above it (the floor case
    finds its red 6 px lower than expected)."""
    chart = _even_chart(series)
    img = _paint(chart)
    marks = chart.withheld_marks()
    m = next(m for m in marks if m[1] == idx)
    if expect is None:
        assert m[2] is None
    else:
        assert m[2] == pytest.approx(expect)
    # the painted box of the mark is its tooltip area; its centre is the x
    box = next(r for r, t in chart._hits if t == m[3])
    c = box.center()
    assert _red_near(img, c.x(), c.y(), r=3) >= 8, "no red x at its place"
    L, B = 40.0, 26.0
    n = len(chart._series)
    assert c.x() == pytest.approx(L + (640 - L - 12) * idx / (n - 1), abs=0.6)
    if expect is None:
        assert c.y() == pytest.approx(176 - B - mrd._WITHHELD_FLOOR_PX,
                                      abs=0.6)


def test_one_measurement_still_shows_the_two_measurement_text(qapp):
    """A report of one measurement shows the old sentence, withheld or not:
    a single date is no trend, and a red x with no graph is nothing.

    MUTATION, proven red: make `has_trend` count ``>= 1``."""
    chart = _even_chart([_noisy(1)])
    assert not chart.has_trend()
    assert chart.withheld_marks() == []


# ---------------------------------------------------------------------------
# the words: collision, tooltip, description
# ---------------------------------------------------------------------------
def _grey_chart(values, lines, notes):
    rid = "grey_balance_neutral_ramp_avg"
    chart = mrd._TrendChart()
    series = [_pt(i + 1, **{rid: v}) for i, v in enumerate(values)]
    chart.set_data(series, [("m (ΔCh)", QColor("#000000"),
                             lambda pt: (pt.get("rows") or {}).get(rid))],
                   dark=False, limit_lines=lines, line_notes=notes)
    return chart


@pytest.mark.parametrize("key", [k for k, _t, _r in mrd._TREND_GROUPS])
def test_every_tab_places_its_words_by_the_accuracy_rule(qapp, key):
    """Each judged tab's words sit in the left margin while they fit there,
    and move inside the plot, the upper line's word above it and the lower
    one's below, when a word would land on an axis number or on the other
    word: the Colour accuracy rule, on every tab.

    MUTATION, proven red: compute ``collide`` only for the accuracy pair
    (``collide = collide and bool(self._thresholds)``): the words stay in the
    margin on top of the axis numbers."""
    rows = dict((k, r) for k, _t, r in mrd._TREND_GROUPS)[key]
    words = [w() for _rid, w, _c in rows]
    # axis 0 .. 2.24 (data max 2.0 * 1.12): numbers at 0, 1.12, 2.24
    far = [(0.5 + 0.8 * j, w, QColor("#3070c0")) for j, w in enumerate(words)]
    near = [(1.12 + 0.02 * j, w, QColor("#3070c0")) for j, w in enumerate(words)]
    notes = [f"note {w}" for w in words]
    for lines, inside in ((far, False), (near, True)):
        chart = _grey_chart([0.2, 2.0, 0.3], lines, notes)
        _paint(chart)
        boxes = [r for r, t in chart._hits if t.startswith("note ")]
        assert len(boxes) == len(words), "a word was not drawn"
        for b in boxes:
            assert (b.left() >= 40.0) == inside, (key, inside, b)
        if inside and len(boxes) == 2:
            # the upper line's word above it, the lower one's below it
            ys = sorted(b.center().y() for b in boxes)
            assert ys[1] - ys[0] >= 14.0


def test_a_word_inside_the_plot_moves_off_a_data_line(qapp):
    """A word placed inside the plot slides along its own line to the first
    place no data line, point or red x crosses (Knut: *"when a threshold
    label comes close to a graph's line"*); where none is clear it keeps the
    left end, so it is never dropped.

    MUTATION, proven red: ``return start`` at the top of `_clear_left` (the
    word sits on the line that rises through the left end)."""
    # data at 1.25 where the line starts, the line at 1.12 (an axis number,
    # so the word is inside the plot, just above its line at the left end)
    chart = _grey_chart([1.25, 1.3, 2.0, 2.0, 2.0],
                        [(1.12, "Avg", QColor("#3070c0"))], ["note Avg"])
    _paint(chart)
    [box] = [r for r, t in chart._hits if t == "note Avg"]
    assert box.left() > 44.0, "the word stayed on the data line"
    rid = "grey_balance_neutral_ramp_avg"
    series = chart._series
    L, T, w = 40.0, 24.0, 640 - 40.0 - 12.0
    h = 176 - T - 26.0
    vmin, vmax = chart._y_range()

    def xy(i, v):
        return QPointF(L + w * i / (len(series) - 1),
                       T + h * (1 - (v - vmin) / (vmax - vmin)))
    vals = [pt["rows"][rid] for pt in series]
    for a, b in zip(range(len(vals)), range(1, len(vals))):
        assert not mrd._segment_meets_rect(xy(a, vals[a]), xy(b, vals[b]),
                                           box.adjusted(1, 1, -1, -1))


def test_hovering_a_word_or_a_red_x_shows_the_text_the_pdf_prints(qapp):
    """The tooltip over a line's word, and over a red x, is word for word the
    text the PDF prints under the graph.

    MUTATION, proven red: record the hit box of a margin word as
    ``QRectF(0, 0, 0, 0)`` (no tooltip over the word); or give
    `descriptions` the note without its value; or show the plain text
    (``QToolTip.showText(..., text, ...)``: one line 1,580 px wide on the
    red x, photographed in the drive)."""
    from PyQt6.QtCore import QEvent
    from PyQt6.QtGui import QHelpEvent
    from PyQt6.QtWidgets import QToolTip
    chart = _even_chart([_quiet(1, 0.4), _quiet(2, 0.9), _noisy(3)],
                        limit=0.7)
    chart.show()
    _paint(chart)
    printed = [t for _k, _c, t in chart.descriptions()]
    assert printed[0] == ("Pairs (0.7 ΔE00): the limit for the largest "
                          "difference between any two of the nine areas of "
                          "the sheet.")
    assert printed[1].startswith("2026-01-03, Pairs (ΔE00): not judged")
    for rect, text in chart._hits:
        assert text in printed
        c = rect.center().toPoint()
        assert chart.tooltip_at(QPointF(c)) == text
        ev = QHelpEvent(QEvent.Type.ToolTip, c, chart.mapToGlobal(c))
        QApplication.sendEvent(chart, ev)
        # the same words, wrapped by Qt rather than one line wider than
        # the window
        assert QToolTip.text() == mrd._tip_rich(text)
    assert {t for _r, t in chart._hits} == set(printed)
    chart.hide()


def test_a_line_out_of_view_is_still_described_and_says_so(qapp):
    """The PDF lists a line the axis does not reach, and says it is outside
    the range shown, since there is no word on the graph for it.

    MUTATION, proven red: list only the lines inside ``vmin..vmax`` in
    `descriptions`."""
    chart = _grey_chart([0.2, 0.3, 0.25], [(5.0, "Max", QColor("#e0574b"))],
                        ["Max (5.0 ΔCh): x."])
    [(kind, _c, text)] = chart.descriptions()
    assert kind == "line"
    assert text == "Max (5.0 ΔCh): x. Outside the range of values shown."


# ---------------------------------------------------------------------------
# the dialog: every tab has its notes, its units and its description
# ---------------------------------------------------------------------------
_UNITS = ("ΔE", "L*", "ΔCh", "ΔL*")


def test_every_shown_tab_has_units_and_a_note_per_line(qapp, tmp_path):
    """Every legend entry on every shown tab carries a unit, and every line
    has a note naming its word and its value with the unit.

    MUTATION, proven red: drop `_with_unit` around the corner labels in
    `_trend_configs` (Cube corners' legends read "White", no unit); or stop
    passing ``line_notes`` in `_update_trends` (no line has a note)."""
    dlg = _open(tmp_path, qapp, effective_limits("chromiq_default", {}))
    try:
        seen = 0
        for (chart, title, metrics, *_r, lines, shown) in dlg._trend_plan():
            if not shown:
                continue
            for lbl, _c, _a in chart._metrics:
                assert any(u in lbl for u in _UNITS), (title, lbl)
            drawn = chart._lines()
            for tv, word, _col, note in drawn:
                assert note.startswith(f"{word} ("), (title, note)
                assert f"{tv:.1f}" in note and ")" in note
                seen += 1
        assert seen >= 4       # accuracy's pair and the grey pair at least
    finally:
        dlg.deleteLater()


def test_the_evenness_red_x_is_wired_into_the_tab(qapp, tmp_path, monkeypatch):
    """The Evenness tab is handed the withheld rule for each of its judged
    rows, so a noisy date is a red x on it.

    MUTATION, proven red: leave ``withheld=ex["withheld"]`` out of
    `_update_trends`."""
    dlg = _open(tmp_path, qapp, effective_limits("chromiq_default", {}))
    try:
        monkeypatch.setattr(type(dlg), "_judged_trend_limits",
                            lambda self: {"uniformity_sd": 1.5})
        series = [_quiet(1, 0.4), _quiet(2, 0.8), _noisy(3)]
        dlg._update_trends(series, False)
        ev = dlg._trend_groups["evenness"]
        assert [(k, i) for k, i, _v, _t in ev.withheld_marks()] == [(0, 2)]
    finally:
        dlg.deleteLater()


def _catalogue(code):
    return json.loads((ROOT / "data" / "i18n" / f"{code}.json")
                      .read_text(encoding="utf-8"))


@pytest.mark.parametrize("code", ["en", "de"])
def test_every_graph_description_fits_two_lines_in_the_pdf(qapp, code):
    """Knut: *"at most, a two-line description above its chart"*. Laid out
    in the report's font at the PDF's size and the picture's width, in
    English and in German, the longer of the two.

    MUTATION, proven red: append ", including the paper white, the black and
    the six solid colours of the colour cube, measured on every date the
    report covers so that a change in one ink shows" to the Cube corners
    sentence (three lines; the key changes, so German falls back to it too).
    A shorter addition of about 85 characters still fit in two lines and did
    NOT turn it red: two lines at 600 px hold about 215 characters."""
    cat = {} if code == "en" else _catalogue(code)
    family = QApplication.font().family().replace("'", "")
    assert set(mrd._TREND_ABOUT) == {"de", "white", "black", "corners"} | {
        k for k, _t, _r in mrd._TREND_GROUPS}
    def height(text: str) -> float:
        # A QTextDocument's block layouts report no lines to Python; its
        # height does, in whole lines of the one font.
        doc = QTextDocument()
        doc.setDocumentMargin(0)
        doc.setHtml(f"<div style=\"font-family:'{family}';font-size:"
                    f"{mrd._TREND_ABOUT_PX}px\">{text}</div>")
        doc.setTextWidth(600)
        return doc.size().height()

    one = height("x")
    assert one > 0
    for key, about in mrd._TREND_ABOUT.items():
        en = about()
        text = cat.get(en, en)
        lines = round(height(text) / one)
        assert 1 <= lines <= 2, f"[{code}] {key}: {lines} lines: {text}"


def test_the_pdf_prints_the_description_above_and_the_key_under(
        qapp, tmp_path, monkeypatch):
    """In each printed chart cell: title, then the description, then the
    picture, then one entry per line in the words of its tooltip.

    MUTATION, proven red: leave `_trend_about_html` out of the chart cell
    (no description); or leave `_trend_key_html` out (no key); or print the
    bare ``<img>`` without its ``<div>`` (found on screen: the last line of
    a description then stood beside the picture's foot)."""
    dlg = _open(tmp_path, qapp, effective_limits("chromiq_default", {}))
    try:
        if not dlg._trend_de.has_trend():
            pytest.skip("no trend on this fixture, so nothing is printed")
        _sizes, html_ = _export(dlg, tmp_path, monkeypatch)
        cells = html_.split("<table")[1:]
        assert cells
        shown = [e for e in dlg._trend_plan() if e[-1]]
        assert len(cells) == len(shown)
        for cell, e in zip(cells, shown):
            about = dlg._trend_extras(e[0])["about"]
            import html as _h
            a = cell.find(_h.escape(about))
            img = cell.find("<img")
            assert 0 <= a < img, f"{e[1]}: no description above the graph"
            for word in [w for _v, w, _c in (e[7] or [])]:
                assert cell.find(_h.escape(word) + " (", img) > img, (
                    f"{e[1]}: {word} is not explained under the graph")
        # the picture is a block of its own, never on the last line of the
        # description (a bare <img> printed "all nine." beside its foot)
        for cell in cells:
            doc = QTextDocument()
            doc.setHtml("<table" + cell)
            b = doc.begin()
            while b.isValid():
                if "\ufffc" in b.text():
                    assert b.text().strip() == "\ufffc", repr(b.text())
                b = b.next()
        acc = cells[0]
        assert "Avg (" in acc[acc.find("<img"):]
        assert "Max (" in acc[acc.find("<img"):]
    finally:
        dlg.deleteLater()


def test_every_limit_word_has_a_note_written_for_it():
    """Every row with a trend line, and the accuracy pair, has its own
    sentence; none is ChromIQ how-to (K18) or carries an em dash.

    MUTATION, proven red: delete the ``"uniformity_sd"`` entry of
    `_LIMIT_NOTES` (KeyError when the Evenness tab is built)."""
    need = {rid for _k, _t, rows in mrd._TREND_GROUPS for rid, _w, _c in rows}
    need |= {"all_de00_avg", "all_de00_max"}
    assert need <= set(mrd._LIMIT_NOTES)
    for rid, f in mrd._LIMIT_NOTES.items():
        t = f()
        assert t.startswith("the limit for ") and t.endswith(".")
        assert "—" not in t and "ChromIQ" not in t and "click" not in t
        assert rid in ROW_BY_ID
