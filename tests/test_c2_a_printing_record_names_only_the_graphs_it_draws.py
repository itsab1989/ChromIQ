"""A Printing record's graph sentence names only the graphs it DRAWS
(challenge 2 of beta 42, #5; register B8-1005).

§28.3 (K32) put a sentence under a Printing record's results saying why it
carries no graph of a judged metric, and naming the four it does carry. It
named all four whatever was drawn: a record of ONE measurement draws none (its
tabs are empty frames saying a trend needs two measurements, and its PDF has
no graph at all), and still read "The graphs it carries show colour accuracy,
paper white, darkest black and the cube corners." Photographed on screen,
challenge 2, runs/en-main/…/en-pr-04.
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from tests.test_k32_report_rows_and_switch import (  # noqa: E402
    _choose, _profiling_window)

FOUR = ("The graphs it carries show colour accuracy, paper white, darkest "
        "black and the cube corners.")


@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def test_one_measurement_names_no_graph_and_says_why(tmp_path, qapp):
    """MUTATION, proved to land: `_record_graphs_sentence` returns the
    four-graph sentence whatever `_graphs_drawn_for` says."""
    dlg, host = _profiling_window(tmp_path, qapp)
    try:
        _choose(dlg, qapp, "custom_iso_12647_7")
        runs = dlg._runs_for_document()
        assert len(runs) >= 1
        one = runs[:1]
        assert dlg._graphs_drawn_for(one) == []
        html = dlg._report_results_html(one, dlg._rows_the_results_show(one))
        assert "carries no graph of a judged metric" in html
        assert FOUR not in html, "a record of one date names four graphs"
        assert "a graph needs at least two measurements" in html
    finally:
        dlg.close()
        host.deleteLater()


def test_the_sentence_names_exactly_the_graphs_drawn(tmp_path, qapp,
                                                      monkeypatch):
    """All four: the §28.3 sentence as it was. Two of them: those two, in
    tab order, and no other."""
    dlg, host = _profiling_window(tmp_path, qapp)
    try:
        runs = dlg._runs_for_document()
        monkeypatch.setattr(dlg, "_graphs_drawn_for",
                            lambda r: ["de", "white", "black", "corners"])
        assert FOUR in dlg._record_graphs_sentence(runs)
        monkeypatch.setattr(dlg, "_graphs_drawn_for",
                            lambda r: ["white", "black"])
        s = dlg._record_graphs_sentence(runs)
        assert s.endswith("The graphs it carries show paper white and "
                          "darkest black."), s
        monkeypatch.setattr(dlg, "_graphs_drawn_for", lambda r: ["corners"])
        s = dlg._record_graphs_sentence(runs)
        assert s.endswith("The one graph it carries shows the cube "
                          "corners."), s
    finally:
        dlg.close()
        host.deleteLater()


def test_german_is_written_by_hand():
    """EN and DE by hand (the other twelve carry the English under the beta
    rule)."""
    import json
    from pathlib import Path
    de = json.loads((Path(__file__).resolve().parents[1] / "data" / "i18n"
                     / "de.json").read_text(encoding="utf-8"))
    for key in ("This report is not graded, so it carries no graph of a "
                "judged metric: each of those graphs is drawn against its "
                "limit.",
                "It carries no other graph either: a graph needs at least "
                "two measurements, and this report has one.",
                "The graphs it carries show {graphs}.",
                "{list} and {last}", "the cube corners"):
        assert de.get(key) and de[key] != key, key
