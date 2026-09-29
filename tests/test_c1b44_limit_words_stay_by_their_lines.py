"""Challenge 1 of beta 44, F3 and F4 (the report's trend graphs).

F3: two limit lines at one value (Custom ISO 12647-7 puts 4.0 on the control
strip's P95 and its maximum, 2.0 on Colour accuracy's Avg and Max; its outer
and surface gamut averages share 3.0) were drawn as one line with two words,
and the second word was pushed away to a place with no line beside it, next
to an axis number ("4.9 Max"). Lines drawn at one height now carry ONE label,
"P95 / Max", with both notes behind it; and between two clear places a word
inside the plot takes the one not level with an axis number.

F4: the line word "Shell" was said nowhere else; the tab, the legend, the
description and the table say surface gamut. It is "Surface" now.

Every test names the mutation that turns it red; each was run red.
"""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest                                                  # noqa: E402
from PyQt6.QtWidgets import QApplication                       # noqa: E402

import ui.dialogs.measurement_report_dialog as mrd             # noqa: E402
from tests.test_k32_limit_words import _chart, _check, _paint  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.mark.parametrize("accuracy", [False, True])
def test_two_lines_at_one_value_carry_one_label_beside_them(qapp, accuracy):
    """The strip's case and Colour accuracy's: P95 and Max both at 4.0 (Avg
    and Max both at 2.0). One label, both words in it, centred on the line
    in the margin or right beside it inside, and both notes behind it.

    MUTATION, proven red: return every line as its own group from
    `_merge_coinciding_lines` (two words, the second pushed off its line)."""
    data = [[3.9, 4.1, 9.7], [3.8, 3.9, 5.2]]
    if accuracy:
        lines = [(2.0, "Avg"), (2.0, "Max")]
    else:
        lines = [(2.0, "Avg"), (4.0, "P95"), (4.0, "Max")]
    chart = _chart(data, lines, accuracy=accuracy)
    _paint(chart)
    boxes = chart._word_boxes
    assert len(boxes) == len(lines) - 1, boxes
    joined = [t for r, t in chart._hits if "note P95" in t or
              ("note Avg" in t and "note Max" in t)]
    assert joined and all(("note Max" in t) for t in joined), joined
    y = [yy for yy in chart._line_ys][-1]
    shared = [b for b in boxes if abs(b[2] - y) < 1.0]
    assert len(shared) == 1
    rect, where, _y = shared[0]
    if where == "margin":
        assert rect.center().y() == pytest.approx(y)
    else:
        assert abs(rect.center().y() - y) <= 16.0, (rect, y)
    _check(chart, "coinciding")


def test_the_merged_label_reads_both_words_in_line_order():
    """MUTATION, proven red: join with no separator."""
    groups = mrd._merge_coinciding_lines(
        [(4.0, "P95"), (4.0, "Max"), (2.0, "Avg")], [50.0, 50.5, 90.0],
        ["a", "b", "c"])
    assert [(g[1], g[2]) for g in groups] == [("P95 / Max", [0, 1]),
                                             ("Avg", [2])]


def test_a_word_inside_prefers_the_clear_side_away_from_an_axis_number():
    """A line just under an axis number, nothing drawn near it: the word
    goes below, not up beside the number where it read as its unit.

    MUTATION, proven red: set `_WORD_BESIDE_AXIS_NUMBER` to 0 (it goes
    above, level with the number)."""
    # a word wider than the margin (60 px), its line 20 px under the top
    # axis number
    [(rect, where)] = mrd._place_limit_words(
        [(40.0, 60.0)], L=40.0, T=20.0, h=160.0, axis_ys=[20.0, 100.0, 180.0],
        polys=[], marks=[])
    assert where == "below", (where, rect)


def test_the_surface_gamut_is_called_so_on_its_line():
    """F4: every word of the Outer and surface gamut tab is a word of its
    own row's name, in English and in German.

    MUTATION, proven red: put "Shell" back."""
    import json
    from core.resource_path import resource_path
    from workflow.compliance_sets import ROW_BY_ID
    cat = json.load(open(resource_path("data/i18n/de.json"), encoding="utf-8"))
    rows = dict((k, r) for k, _t, r in mrd._TREND_GROUPS)["gamut_edge"]
    for rid, word, _c in rows:
        label = ROW_BY_ID[rid].label
        assert word().lower() in label.lower(), (word(), label)
        assert cat[word()].lower() in cat[label].lower(), (
            cat[word()], cat[label])


# --------------------------------------------------------------------------
# F5, answered by Knut (#182 5841606710, 2026-09-26)
# --------------------------------------------------------------------------
def test_both_custom_columns_put_their_maximum_above_their_95th_percentile():
    """Knut: *"(a) Max higher, so it sits above P95 4.0 ... set to 4.50."*
    A P95 limit above the Max limit can never decide anything, so in both
    Custom columns the maximum over all patches now sits above it.

    MUTATION, proven red: put 2.0 back in either column."""
    import workflow.compliance_sets as cs
    for parent in ("iso_12647_7", "iso_12647_8"):
        d = cs.custom_defaults(parent)
        assert d["all_de00_max"] == cs.Limit.value(4.5), parent
        assert d["all_de00_max"].number > d["all_de00_p95"].number, parent
        assert cs.custom_default_sources(parent)["all_de00_max"] == "industry"


def test_every_row_of_a_family_says_how_it_relates_to_the_others(qapp):
    """Knut: *"The help text for the different metrics need to include the
    information ... that "Maximum ΔE00, lowest 95 % (P95)" can never be
    higher than "Maximum ΔE00, all patches"."* Every row of the three
    families worked out from one set of patches (all patches, the control
    strip, the grey ramp) says so in its help icon, with what it means for
    choosing limits, in English and in German, with no em dash.

    MUTATION, proven red: drop `relation` from `_row_help`."""
    import json
    from core.resource_path import resource_path
    import workflow.compliance_sets as cs
    from ui.dialogs.thresholds_dialog import ThresholdsDialog
    cat = json.load(open(resource_path("data/i18n/de.json"), encoding="utf-8"))
    fam = ("all_de00_avg", "best95_de00_avg", "worst5_de00_avg",
           "all_de00_max", "all_de00_p95", "control_strip_de00_avg",
           "control_strip_de00_max", "control_strip_de00_p95",
           "grey_balance_neutral_ramp_avg", "grey_balance_neutral_ramp_max")
    for rid in fam:
        row = cs.ROW_BY_ID[rid]
        text = ThresholdsDialog._row_help(row)
        assert row.relation and row.relation in text, rid
        assert "never higher than" in row.relation, rid
        assert "can never decide anything" in row.relation, rid
        assert "—" not in row.relation and "—" not in cat[row.relation]
        assert cat[row.relation] != row.relation
    p95 = cs.ROW_BY_ID["all_de00_p95"].relation
    assert "95th percentile" in p95 and "maximum" in p95
    strip = cs.ROW_BY_ID["control_strip_de00_p95"].relation
    assert "95th percentile is never higher than its maximum" in strip
