"""Every place that reads a strip or patch label back reads the chart's OWN labels.

Knut, #182 5965589190 (2026-10-03): *"it shall be possible to switch the
running number and alphabetic labels, and use the rules defined for the strip
and patch patterns defined by ArgyllCMS."* So a chart may be numbered by strip
and lettered by patch ("12C" is strip 12, patch C), and every reader of
locations (the Measure tab's arrow and click targets, the read map, guided
refinement, Check & Refine, the evenness report, the chart editor) had read
"letters, then a number counted from 1". Each is checked here on a real chart
built by the engine with numbered strips, and with the default patterns, which
must read exactly as before.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from workflow.layout_engine import chart as le_chart            # noqa: E402
from workflow.layout_engine.labels import (ChartLabels,        # noqa: E402
                                           labels_for_chart,
                                           labels_for_measurement)

NUMBERED = ("0-9,@-9;1-99", "A-Z")          # strips 1, 2 ... ; patches A, B ...


def _ti1(d: Path, n: int) -> Path:
    lines = ["CTI1", "", 'DESCRIPTOR "p"', 'ORIGINATOR "ChromIQ"',
             "NUMBER_OF_FIELDS 7", "BEGIN_DATA_FORMAT",
             "SAMPLE_ID RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z", "END_DATA_FORMAT",
             f"NUMBER_OF_SETS {n}", "BEGIN_DATA"]
    for i in range(n):
        lines.append(f"{i+1} {(i*7)%100}.0 {(i*13)%100}.0 {(i*29)%100}.0 40 45 50")
    lines += ["END_DATA", ""]
    p = d / "p.ti1"
    p.write_text("\n".join(lines), encoding="utf-8")
    return p


@pytest.fixture(scope="module")
def numbered(tmp_path_factory):
    d = tmp_path_factory.mktemp("numbered")
    res = le_chart.build_chart(_ti1(d, 400), d / "c", instrument="i1",
                               paper="A4", dpi=72, seed=11,
                               strip_pattern=NUMBERED[0],
                               patch_pattern=NUMBERED[1])
    return d / "c.ti2", res


def _locs(ti2: Path) -> "list[str]":
    from workflow.measurement_pairing import chart_locations
    return [x for x in chart_locations(ti2) if x]


def test_the_chart_is_labelled_and_read_with_argylls_rules(numbered):
    ti2, res = numbered
    cl = labels_for_chart(ti2)
    assert cl.rule == "argyll"
    steps = res.layout.steps_in_pass
    n = (res.layout.total_patches + steps - 1) // steps
    assert n > 10, "the premise: a strip numbered 10 or more"
    assert cl.split(f"{n}A") == (n - 1, 0)
    assert cl.split("1" + cl.patch(steps - 1)) == (0, steps - 1)
    assert cl.strip_index("12") == 11 and cl.strip(11) == "12"
    assert all(cl.location(*cl.split(loc)) == loc for loc in _locs(ti2))


def test_the_measurement_finds_its_charts_labels(numbered, tmp_path):
    ti2, _res = numbered
    assert labels_for_measurement(ti2.with_suffix(".ti3")).rule == "argyll"
    assert labels_for_measurement(ti2.with_suffix(".ti3")).strip_pattern \
        == NUMBERED[0]


# ---- the old rule: charts printed before 4.3.3-beta.7 ----------------------
def test_a_legacy_chart_is_recognised_and_read_as_printed(tmp_path):
    res = le_chart.build_chart(_ti1(tmp_path, 400), tmp_path / "c",
                               instrument="i1", paper="A4", dpi=72, seed=3,
                               strip_pattern="0-9", patch_pattern="A-Z",
                               label_rule="legacy")
    cl = labels_for_chart(tmp_path / "c.ti2")
    assert cl.rule == "legacy"
    steps = res.layout.steps_in_pass
    assert cl.split("14A") == (13, 0)
    assert cl.strip(0) == "1"


def test_legacy_labels_that_run_together_are_nobodys():
    cl = ChartLabels("0-9", "1-999", rule="legacy", n_strips=12, steps=12)
    assert cl.split("111") is None       # strip 1 patch 11, or strip 11 patch 1
    assert cl.split("19") == (0, 8)


# ---- Measure: the read map, guided refinement, the strip announcement -----
def test_the_read_map_orders_a_numbered_chart_by_strip_then_patch(numbered):
    from PyQt6.QtCore import QCoreApplication
    QCoreApplication.instance() or QCoreApplication([])
    from workflow.measure_manager import MeasureManager

    class _R:
        def run(self, *a, **k): pass
        def write_stdin(self, t): pass

    ti2, res = numbered
    mgr = MeasureManager(_R())
    cl = labels_for_chart(ti2)
    steps = res.layout.steps_in_pass
    n = (res.layout.total_patches + steps - 1) // steps
    strips = [{"strip": cl.strip(i)} for i in range(n)]
    mgr._is_resume = False
    mgr._build_read_map(str(ti2), strips)
    want = [cl.location(s, p) for s in range(n) for p in range(steps)]
    got = [loc for loc in mgr._read_order]
    assert got == [w for w in want if w in set(got)]
    assert mgr._loc_strip["12A"] == "12"


def test_stock_chartread_announcing_a_numbered_strip_moves_the_arrow():
    from PyQt6.QtCore import QCoreApplication
    QCoreApplication.instance() or QCoreApplication([])
    from workflow.measure_manager import MeasureManager

    class _R:
        def run(self, *a, **k): pass
        def write_stdin(self, t): pass

    mgr = MeasureManager(_R())
    seen: list = []
    mgr.stripe_changed.connect(seen.append)
    mgr._handle_line("Ready to read strip pass 12", lambda _l: None)
    mgr._handle_line("Ready to read strip pass AB (!! ALL ROWS READ !!)",
                     lambda _l: None)
    assert seen == ["12", "AB"]


def test_guided_refinement_goes_forward_on_a_numbered_chart(numbered):
    from workflow.measure_manager import _strip_order_of
    cl = labels_for_chart(numbered[0])
    assert _strip_order_of(cl, "12") > _strip_order_of(cl, "9")
    assert _strip_order_of(None, "AB") > _strip_order_of(None, "Z")   # default


def test_the_measure_tab_puts_the_arrow_on_a_numbered_strip(numbered):
    """The tab's own label methods, on a stand-in that has only what they read."""
    from ui.tabs.tab_measure import TabMeasure

    class _T:
        _chart_file_for = staticmethod(TabMeasure._chart_file_for)
        _chart_labels = TabMeasure._chart_labels
        _strip_index = TabMeasure._strip_index
        _strip_name = TabMeasure._strip_name
        _strip_of = TabMeasure._strip_of
        _locate_strip = TabMeasure._locate_strip
        _letter_for_page_idx = TabMeasure._letter_for_page_idx

    ti2, res = numbered
    t = _T()
    t._ti1_path = ti2
    from core.strip_utils import parse_passes_per_page
    t._strips_per_page = parse_passes_per_page(ti2)
    t._page_stripe_rects = []
    assert t._strip_name("12") == "12"
    assert t._strip_of("12C") == "12"
    page, local, _r = t._locate_strip("12")
    first = t._strips_per_page[0]
    assert (page, local) == ((0, 11) if first > 11 else (1, 11 - first))
    assert t._letter_for_page_idx(page, local) == "12"
    # a default chart still reads letters exactly as before
    t._ti1_path = None
    assert t._strip_of("AB12") == "AB" and t._strip_index("AB") == 27


# ---- Check & Refine --------------------------------------------------------
def test_check_and_refine_groups_and_orders_a_numbered_chart(numbered):
    from workflow.refine_plan import build_plan, parse_patches
    cl = labels_for_chart(numbered[0])
    errors = [("12C", 9.0), ("12D", 1.0), ("3A", 8.0), ("10B", 7.5)]
    patches = parse_patches("", errors, cl)
    by = {p.loc: p for p in patches}
    assert by["12C"].strip == "12" and by["12C"].pos == 3
    plan = build_plan(patches, 5.0, labels=cl)
    assert [s for s, _de in plan.chosen(first_only=False)] == ["3", "10", "12"]


def test_check_and_refine_reads_a_location_with_any_label(numbered):
    from workflow.refine_plan import parse_patches
    line = ("[3.000000] 7 @ 12C: 0.5 0.4 0.3 -> 50.0 1.0 2.0 should be "
            "51.0 1.5 2.5")
    p = parse_patches(line, None, labels_for_chart(numbered[0]))
    assert [x.loc for x in p] == ["12C"] and p[0].strip == "12"


# ---- the evenness report ---------------------------------------------------
def test_the_report_places_every_patch_of_a_numbered_chart(numbered):
    from workflow.measurement_report import chart_grid
    ti2, res = numbered
    g = chart_grid(ti2)
    assert "reason" not in g, g
    steps = res.layout.steps_in_pass
    assert g["rows"] == steps
    assert g["strip_label"][11] == "12" and g["row_label"][2] == "C"


# ---- the chart editor ------------------------------------------------------
def test_the_editor_groups_a_numbered_chart_into_its_strips(numbered):
    from workflow.ti2_relayout import _read_ti2_strips
    ti2, res = numbered
    strips = _read_ti2_strips(ti2)
    steps = res.layout.steps_in_pass
    n = (res.layout.total_patches + steps - 1) // steps
    assert len(strips) == n
    assert all(len(s) <= steps for s in strips)
