"""B8-957 (beta 41): a trend graph's limit-line note prints its value with
the decimal mark of the report's language.

Beta 40 second check: the German report's evenness graph said "Bereiche
(1.5 ΔE00): …" beside sentences that write "59,4" (`_level_text`, B8-950).
`_limit_value_text` formatted with a point in every language.

MUTATION, proven red (~/Desktop/ChromIQ-beta41-proof/small-fixes/p3/):
drop the ``s.replace(".", ",")`` line from `_limit_value_text`.
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtGui import QColor                              # noqa: E402
from PyQt6.QtWidgets import QApplication                    # noqa: E402

from core import i18n                                       # noqa: E402
import ui.dialogs.measurement_report_dialog as mrd          # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def lang():
    before = i18n.current_language()

    def _set(code):
        i18n.set_language(code)
    yield _set
    i18n.set_language(before or "en")


def test_german_writes_a_decimal_comma(lang):
    lang("de")
    assert mrd._limit_value_text(1.5, "ΔE00") == "1,5 ΔE00"
    assert mrd._limit_value_text(0.75, "ΔE00") == "0,75 ΔE00"
    assert mrd._limit_value_text(3, "ΔL*") == "3,0 ΔL*"
    note = mrd._limit_line_note(i18n.tr("Areas"), 1.5, "ΔE00",
                                "uniformity_sd")
    assert "(1,5 ΔE00)" in note and "1.5" not in note, note


def test_english_keeps_its_point(lang):
    lang("en")
    assert mrd._limit_value_text(1.5, "ΔE00") == "1.5 ΔE00"
    assert "(1.5 ΔE00)" in mrd._limit_line_note("Areas", 1.5, "ΔE00",
                                                 "uniformity_sd")


def test_the_graph_in_german_describes_its_line_with_a_comma(qapp, lang):
    """On a graph: the note under it in the PDF (and its tooltip) is the
    same sentence."""
    lang("de")
    rid = "uniformity_sd"
    chart = mrd._TrendChart()
    pts = [{"created": f"2026-12-0{d}T10:00:00", "rows": {rid: 0.5 + d / 10},
            "rows_noise": {rid: 0.1}} for d in (1, 2, 3)]
    word = i18n.tr("Areas")
    chart.set_data(pts, [("x", QColor("#e0574b"),
                          lambda pt: mrd._trend_row_value(pt, rid, 1.5))],
                   limit_lines=[(1.5, word, QColor("#e0574b"))],
                   line_notes=[mrd._limit_line_note(word, 1.5, "ΔE00", rid)])
    texts = [t for kind, _c, t in chart.descriptions() if kind == "line"]
    assert texts and all("1,5 ΔE00" in t for t in texts), texts
