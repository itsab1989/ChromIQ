"""K47 (Knut, #182 5840152058): every limited row has a data line, a limit
line and a sentence; a graph with no limit says so under it.

Knut: *"If the Control strip graph has data-lines in the graph, where each
have their own threshold (or maybe even uses the same threshold) then the
graph shall have both dotted horizontal lines (same implementation as other
graphs) in the graph and a sentence below it for the threshold."* and, on a
graph with no limit, *"If this is not noted other places, then a short note
could say so under the graphs."*

Every test below names the mutation it was proved red against.
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtGui import QColor                            # noqa: E402

from workflow import measurement_report as mr             # noqa: E402
from workflow import compliance_sets as cs                # noqa: E402
from workflow.compliance_sets import (ROW_BY_ID,          # noqa: E402
                                      effective_limits)

import ui.dialogs.measurement_report_dialog as mrd        # noqa: E402
from tests.test_trend_graphs_for_judged_metrics import (  # noqa: E402
    _open, qapp)                                           # noqa: F401

_COMPUTABLE = ("now", "build", "ref")
#: the five rows the Colour accuracy graph plots with its grey lines
_ACCURACY = {rid for rid, _fam in mrd._ACCURACY_LINE_ROWS}


def _rows_a_set_can_limit() -> "dict[str, set[str]]":
    """``{set id: {row id}}``: every computable row each set limits or, for a
    read-only ISO set, writes a limit over (its structure; its numbers may be
    empty on a machine without them)."""
    out = {}
    for d in cs.SETS:
        if d.id in cs._ISO_ROWS:
            rows = set(cs._ISO_ROWS[d.id])
        else:
            rows = {rid for rid, lim in cs.factory_limits(d.id).items()
                    if getattr(lim, "kind", "") == "value"}
        out[d.id] = {r for r in rows
                     if r in ROW_BY_ID and ROW_BY_ID[r].status in _COMPUTABLE}
    return out


def test_every_row_any_set_limits_has_a_graph():
    """Across every limit set (the three ChromIQ sets, both ISO sets and both
    Custom sets), each computable row a set can limit is plotted by some
    graph: the Colour accuracy graph's five rows, or a judged-metric tab.

    MUTATION, proven red: take ``control_strip_de00_max`` out of the strip
    group (ISO 12647-7 judges it, the graph had no line for it); or take the
    "solids" group out of `_TREND_GROUPS`."""
    plotted = set(_ACCURACY) | {rid for _k, _t, rows in mrd._TREND_GROUPS
                                for rid, _w, _c in rows}
    missing = {sid: sorted(rows - plotted)
               for sid, rows in _rows_a_set_can_limit().items()
               if rows - plotted}
    assert not missing, f"limited rows with no graph: {missing}"
    # and the trend series carries a value for every row a tab plots
    tabbed = {rid for _k, _t, rows in mrd._TREND_GROUPS
              for rid, _w, _c in rows}
    assert tabbed == set(mr.TREND_ROW_IDS)


def test_iso_12647_7_judges_the_strip_maximum_and_its_tab_plots_it():
    """The structure the report reads from: ISO 12647-7 writes a limit over
    the strip's average and maximum, not its 95th percentile, and the strip
    tab plots all three kinds.

    MUTATION, proven red: drop the maximum from the strip group."""
    assert {"control_strip_de00_avg", "control_strip_de00_max"} <= set(
        cs._ISO_ROWS["iso_12647_7"])
    assert "control_strip_de00_p95" not in cs._ISO_ROWS["iso_12647_7"]
    strip = dict((k, r) for k, _t, r in mrd._TREND_GROUPS)["strip"]
    assert [rid for rid, _w, _c in strip] == [
        "control_strip_de00_avg", "control_strip_de00_p95",
        "control_strip_de00_max"]
    assert [w() for _r, w, _c in strip] == ["Avg", "P95", "Max"]


def test_the_trend_series_carries_the_new_rows():
    """A report with a declared strip and the corners against a colorimetric
    reference puts the strip maximum and both solid rows into the point.

    MUTATION, proven red: take ``control_strip_de00_max`` out of
    `TREND_ROW_IDS`."""
    rep = {"created": "2026-01-01T10:00:00", "chart": "x",
           "reference_source": "colorimetric",
           "control_strip": {"eligible": True, "avg": 1.1, "max": 3.4,
                             "p95": 2.9},
           "corners": [
               {"name": "W", "present": True, "de": 0.8,
                "lab": [95, 0, 2], "expected_lab": [95, 0, 1.5]},
               {"name": "C", "present": True, "de": 2.2,
                "lab": [55, -37, -50], "expected_lab": [56, -36, -49]},
               {"name": "M", "present": True, "de": 1.2,
                "lab": [50, 80, -5], "expected_lab": [50, 81, -4]},
               {"name": "Y", "present": True, "de": 1.0,
                "lab": [90, -3, 110], "expected_lab": [90, -2, 111]},
               {"name": "K", "present": True, "de": 0.5,
                "lab": [3, 0, 0], "expected_lab": [3, 0, 0.5]}]}
    [pt] = mr.report_trend([rep])
    rows = pt["rows"]
    assert rows["control_strip_de00_max"] == pytest.approx(3.4)
    assert rows["control_strip_de00_p95"] == pytest.approx(2.9)
    assert rows["solids_de00_max"] == pytest.approx(2.2)
    assert "cmy_solids_dhab_max" in rows
    assert rows["substrate_de00_max"] == pytest.approx(0.8)


def _strip_plan(dlg, judged: dict):
    dlg._judged_trend_limits = lambda: dict(judged)
    for entry in dlg._trend_plan():
        if entry[0] is dlg._trend_groups["strip"]:
            return entry, dlg._trend_extras(entry[0])
    raise AssertionError("no strip tab in the plan")


@pytest.mark.parametrize("judged,words", [
    # ISO 12647-7: the average and the maximum
    ({"control_strip_de00_avg": 2.5, "control_strip_de00_max": 5.0},
     ["Avg", "Max"]),
    # a Custom set: all three, two of them at one number
    ({"control_strip_de00_avg": 2.0, "control_strip_de00_p95": 4.0,
      "control_strip_de00_max": 4.0}, ["Avg", "P95", "Max"]),
    # ISO 12647-8: the average and the 95th percentile, as before
    ({"control_strip_de00_avg": 2.5, "control_strip_de00_p95": 5.0},
     ["Avg", "P95"]),
])
def test_each_judged_strip_row_has_a_data_line_a_limit_line_and_a_sentence(
        qapp, tmp_path, judged, words):
    """Each judged strip row is plotted, with its own dotted line at its own
    limit and its own sentence naming it, the maximum included.

    MUTATION, proven red: drop the maximum from the strip group (the ISO
    12647-7 case plots and describes only the average)."""
    dlg = _open(tmp_path, qapp, effective_limits("chromiq_default", {}))
    try:
        (_c, _t, metrics, _y, _d, _a, _thr, lines, shown), ex = _strip_plan(
            dlg, judged)
        assert shown
        assert [w for _v, w, _col in lines] == words
        assert len(metrics) == len(words)
        want = {"Avg": "control_strip_de00_avg",
                "P95": "control_strip_de00_p95",
                "Max": "control_strip_de00_max"}
        for (v, w, _col), note in zip(lines, ex["line_notes"]):
            rid = want[w]
            assert v == judged[rid]
            assert ROW_BY_ID[rid].label in note, (w, note)
    finally:
        dlg.deleteLater()


def test_a_solid_row_judged_brings_its_tab(qapp, tmp_path):
    """The two solid-colour rows each have a tab of their own (different
    units), shown while judged, with its line and sentence.

    MUTATION, proven red: take the "solid_hue" group out of `_TREND_GROUPS`."""
    dlg = _open(tmp_path, qapp, effective_limits("chromiq_default", {}))
    try:
        dlg._judged_trend_limits = lambda: {"solids_de00_max": 3.0,
                                            "cmy_solids_dhab_max": 2.5}
        plan = {e[0]: e for e in dlg._trend_plan()}
        for key, rid, lim in (("solids", "solids_de00_max", 3.0),
                              ("solid_hue", "cmy_solids_dhab_max", 2.5)):
            e = plan[dlg._trend_groups[key]]
            assert e[-1] is True
            assert [v for v, _w, _c in e[7]] == [lim]
            [note] = dlg._trend_extras(e[0])["line_notes"]
            assert ROW_BY_ID[rid].label in note
    finally:
        dlg.deleteLater()


# ---------------------------------------------------------------------------
# a graph with no limit says so
# ---------------------------------------------------------------------------
def _chart(lines=None, thresholds=None, n=3, no_limit=None):
    chart = mrd._TrendChart()
    series = [{"created": f"2026-01-0{i + 1}T10:00:00", "white_L": 95.0 + i}
              for i in range(n)]
    chart.set_data(series, [("Paper white L*", QColor("#888888"),
                             lambda pt: pt.get("white_L"))],
                   dark=False, limit_lines=lines or [],
                   thresholds=thresholds,
                   line_notes=["note"] * len(lines or []),
                   no_limit=no_limit)
    return chart


def test_a_drawn_graph_with_no_limit_line_says_so():
    """No limit line, a drawn trend: one note, first. K49 (Knut, #182
    5841092535, answer 2: *"be a bit more informative than "No limit
    applies" as note"*): the graph's own sentence, what it shows, what
    watching it is for and why no line is drawn; a chart given none falls
    back to the second half alone.

    MUTATION, proven red: drop the note from `_TrendChart.descriptions`; or
    ignore ``no_limit`` there (the general sentence is printed)."""
    own = mrd.no_limit_note("white")
    [(kind, _c, text)] = _chart(no_limit=own).descriptions()
    assert kind == "note"
    assert text == own
    assert "paper" in text and "between dates" in text
    assert "no limit line is drawn" in text
    [(kind, _c, text)] = _chart().descriptions()
    assert kind == "note" and text == mrd.no_limit_note()


def test_a_graph_with_a_limit_line_carries_no_such_note():
    """MUTATION, proven red: add the note whatever the lines are."""
    got = _chart(lines=[(96.0, "Max", QColor("#e0574b"))]).descriptions()
    assert [k for k, _c, _t in got] == ["line"]


def test_a_graph_of_one_date_carries_no_note():
    """It draws no trend, so there is nothing to say about a line.

    MUTATION, proven red: drop the ``len(self._series) >= 2`` test."""
    assert _chart(n=1).descriptions() == []


def test_the_pdf_prints_the_note_without_a_line_mark():
    """Under the graph in the PDF the note is plain text: no dotted stroke,
    since there is no line for it to stand for.

    MUTATION, proven red: render a note like a line."""
    html = mrd._trend_key_html(_chart().descriptions())
    assert mrd.html.escape(mrd.no_limit_note()) in html
    assert "┈" not in html and "×" not in html


def test_the_note_names_no_control_of_the_app():
    """K39: report text names no feature, action or button of the app; and
    no em dash (CLAUDE.md), in English and in German, for every graph's
    sentence and every reason no line is drawn (K49).

    MUTATION, proven red: end a sentence with "Choose a limit set that
    judges it."."""
    import json
    from core.resource_path import resource_path
    cat = json.load(open(resource_path("data/i18n/de.json"),
                         encoding="utf-8"))
    parts = [f() for f in mrd._NO_LIMIT_SHOWS.values()] + \
        [f() for f in mrd._NO_LIMIT_WHY.values()]
    assert len(parts) == len(mrd._TREND_ABOUT) + 3
    for en in parts:
        import re
        for word in ("Choose", "Press", "tick", "window", "tab", "button"):
            assert not re.search(rf"\b{word}\b", en), (word, en)
        assert "—" not in en, en
        de = cat[en]
        assert de != en and "—" not in de, en
        # K49: German report text takes no "du" (Du-Form, never addressed)
        assert " du " not in f" {de.lower()} " and "dein" not in de.lower()


def test_every_graph_has_its_own_no_limit_sentence():
    """K49 (Knut, #182 5841092535, answer 2): the note is written for each
    graph, never the one general sentence K47 printed under all of them.
    Each says what its graph shows, what watching it is for (a change
    between dates) and why no line is drawn.

    MUTATION, proven red: map two keys of `_NO_LIMIT_SHOWS` to one text."""
    keys = set(mrd._TREND_ABOUT)
    assert set(mrd._NO_LIMIT_SHOWS) == keys
    texts = {k: mrd.no_limit_note(k) for k in keys}
    assert len(set(texts.values())) == len(keys)
    for k, t in texts.items():
        assert t.startswith("This graph shows"), k
        assert "date" in t, k
        assert t.endswith("no limit line is drawn."), k
    for why in (mrd.NO_LIMIT_WHY_SET, mrd.NO_LIMIT_WHY_RECORD,
                mrd.NO_LIMIT_WHY_ACCURACY):
        assert mrd.no_limit_note("de", why).endswith(
            mrd._NO_LIMIT_WHY[why]())
