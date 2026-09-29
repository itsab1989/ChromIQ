"""The limit demo package must show BOTH halves of every metric it can compute.

Knut, 2026-09-12:

    *"Many, or most, of the verification charts used in
    ChromIQ-Report-Limit-Demos are missing patches so that some metrics are not
    tested. This especially applies to the gray ramp test. The demo project
    pack should use various sizes of test charts for verification, so that all
    conditions and metrics are checked, and to test and verify that the
    measurement report feature can detect if each metric is supported or not
    supported by a given chart used for verification."*

The package already refused to ship dated verifications that missed their
design. That refusal says every date crossed the row it meant to; it says
nothing at all about coverage, and `metric_coverage` (the table that did) ORs
the whole package together, so a row one sheet in fifty-seven can fill reads as
covered while the other fifty-six show N-A and nobody has looked at what they
show.

`support_coverage` asks the question per report, which is the unit the reader
sees, and `support_faults` refuses a package that:

* never puts a number on a row ChromIQ can compute;
* never shows a row reading N-A, unless no chart CAN withhold it, which is a
  property of the app and is named with its reason in
  `NO_CHART_CAN_UNSUPPORT`;
* uses too few verification chart sizes for a row's availability to be seen to
  follow the chart at all.

The refusal is tested here on its own, because building the whole package to
watch it fire costs a minute and proves the same thing.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import make_report_limit_demos as gen        # noqa: E402


SIZES = [20, 90, 105, 156, 210, 400]


def _row(rid, value, na, cannot=""):
    return {"id": rid, "label": rid, "value": value, "na": na,
            "value_on": SIZES[:2] if value else [], "na_on": SIZES[2:3] if na else [],
            "reasons": ["no_greys"] if na else [],
            "cannot_unsupport": cannot}


def _cov(rows, sizes=None):
    return {"support_rows": rows, "support_reports": 57,
            "verify_chart_sizes": SIZES if sizes is None else sizes}


# ------------------------------------------------------------- the refusals
def test_a_row_nothing_fills_is_refused():
    """A computable row no verification puts a number on is a row the package
    has not tested, whatever its README claims."""
    faults = gen.support_faults(_cov([_row("all_de00_avg", 0, 57)]))
    assert faults, "a row with no value anywhere was accepted"
    assert "all_de00_avg" in faults[0]
    assert "nothing exercises it" in faults[0]


def test_a_row_never_seen_unsupported_is_refused():
    """The half Knut asked for. A row that always has a number never shows the
    report detecting a chart that cannot supply it."""
    faults = gen.support_faults(_cov([_row("grey_balance_neutral_ramp_avg",
                                           57, 0)]))
    assert faults, "a row never seen N-A was accepted"
    assert "reading N-A" in faults[0]


def test_a_row_no_chart_can_withhold_is_not_held_against_the_package():
    """Some rows the report fills from a single judged patch. Demanding an N-A
    for one of those would be demanding a state the app cannot reach, and the
    only way to produce it would be to invent one."""
    assert gen.support_faults(_cov([
        _row("all_de00_avg", 57, 0, cannot="exists as soon as one patch is "
                                            "judged")])) == []


def test_a_row_shown_both_ways_is_accepted():
    assert gen.support_faults(_cov([_row("ramps_30_70_dl_max", 55, 2)])) == []


def test_too_few_chart_sizes_is_refused():
    """A package that verifies everything on one chart size cannot show a
    row's availability following the chart, however many reports it holds."""
    faults = gen.support_faults(
        _cov([_row("ramps_30_70_dl_max", 55, 2)], sizes=[210, 105]))
    assert faults
    assert "chart size" in faults[-1]


def test_the_shape_this_package_actually_builds_is_accepted():
    """The guard has to let the real thing through, or it is only a way of
    never shipping. These are the eight computable rows as the package builds
    them: four shown both ways, four that no chart can withhold."""
    rows = [_row(rid, 55, 2) for rid in ("grey_balance_neutral_ramp_avg",
                                         "grey_balance_neutral_ramp_max",
                                         "worst5_de00_avg",
                                         "ramps_30_70_dl_max")]
    rows += [_row(rid, 57, 0, cannot=gen.NO_CHART_CAN_UNSUPPORT[rid])
             for rid in ("all_de00_avg", "best95_de00_avg", "all_de00_max",
                         "all_de00_p95")]
    assert gen.support_faults(_cov(rows)) == []


# -------------------------------------------------- the excuse list is honest
def test_every_excused_row_is_one_the_app_really_cannot_unsupport():
    """`NO_CHART_CAN_UNSUPPORT` is an excuse list, and an excuse list is the
    easiest place to hide a row nobody wanted to cover. Every id in it must be
    a real computable row, and must be one the report fills from any judged
    patch: that is exactly the rows with a `metric_key`, minus the worst 5 %,
    whose set is empty below twenty patches and which IS demonstrated.
    """
    from workflow.compliance_sets import ROW_BY_ID, ROWS
    computable = {r.id for r in ROWS if r.status in ("build", "now")}
    for rid, why in gen.NO_CHART_CAN_UNSUPPORT.items():
        assert rid in ROW_BY_ID, f"{rid} is not a row of the limits table"
        assert rid in computable, (
            f"{rid} is excused from needing an N-A, but ChromIQ cannot compute "
            f"it at all, so it belongs in the other table")
        assert ROW_BY_ID[rid].metric_key, (
            f"{rid} is excused as always-computable, but it has no metric_key, "
            f"so `row_values` does not fill it from the delta-E block")
        assert why.strip(), f"{rid} is excused with no reason given"


def test_the_worst_five_percent_is_not_excused():
    """The one row a chart really can withhold, because the worst-5 % set is
    EMPTY below twenty patches. Excusing it would quietly drop the only
    chart-driven N-A the delta-E family has."""
    assert "worst5_de00_avg" not in gen.NO_CHART_CAN_UNSUPPORT, (
        "the worst 5 % has been excused from needing an N-A, but a chart of "
        "under twenty patches genuinely cannot supply it and the package "
        "holds one")


def test_the_package_plans_a_verification_chart_at_the_twenty_patch_border():
    """The chart that makes that N-A happen. Read off the plans, so a plan
    edited to a bigger chart is caught here rather than in a coverage table
    nobody reads.

    The rule is on the JUDGED patches and not on the chart, which is a
    distinction this test got wrong first time: the package's smallest sheet is
    20 patches, and the run that uses it judges 19 of them, because a colour
    outside the profile's gamut was never printable and is not graded. Twenty
    is therefore the largest chart that can still land under the border, and
    the assertion is written on that rather than on a number that looked
    right.
    """
    sizes = {plan.verify_chart.patches
             for _name, plans in gen.PROJECTS for plan in plans}
    assert min(sizes) <= 20, (
        f"the smallest verification chart is {min(sizes)} patches; the worst "
        f"5 % needs under 20 JUDGED patches before it reads N-A, and no chart "
        f"this big can get there")
    assert len(sizes) >= 4, (
        f"the package verifies on {len(sizes)} chart size(s): {sorted(sizes)}")


def test_the_package_plans_a_verification_chart_with_no_grey_ramp():
    """The chart that makes the grey and tone rows read N-A."""
    assert any(plan.verify_chart.grey == 0
               for _name, plans in gen.PROJECTS for plan in plans), (
        "every verification chart keeps a grey ramp, so the grey-balance and "
        "tone-ramp rows are never seen reading N-A")
