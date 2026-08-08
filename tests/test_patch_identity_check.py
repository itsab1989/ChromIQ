"""A measurement's readings really do belong to the chart they are compared with.

ChromIQ's report pairs a measurement with its chart by ``SAMPLE_ID``. For a
measurement returned from i1Profiler that ID is **only the row number**: the
CxF objects are labelled ``M0_Measurement1``, ``c1`` … and carry no trace of
the original patch, so ``reference_convert`` numbers them 1..N by their order
in the file (``reference_convert.py:327``). If anything re-orders the patches
on the way, every patch is compared against the wrong one — and the report
looks perfectly normal, because each comparison is against a real patch.

A real round trip on 2026-08-08 (550 patches, through i1Profiler and back) kept
the order exactly, with a worst channel error of 0.5 on the 0..255 scale —
rounding, nothing more. So this check is expected to pass; it guards the case
that would not, and i1Profiler has a ``ScramblePatches`` setting that produces
exactly that case.

This release **reports** the answer and acts on nothing, so no existing figure
changes on the strength of it.
"""
from __future__ import annotations

import numpy as np
import pytest

from workflow.measurement_report import (
    PATCH_IDENTITY_TOL, verify_patch_identity,
)
from workflow.ti3_analysis import parse_ti3


def _write(path, rgb, ids=None, kind="CTI2"):
    """A minimal CGATS file. XYZ is required for a measurement to parse at all,
    so it is written for both kinds — its values are irrelevant here, because
    this check only ever looks at the device values."""
    ids = ids or [str(i + 1) for i in range(len(rgb))]
    lines = [kind, "", 'DESCRIPTOR "test"', 'ORIGINATOR "test"',
             'DEVICE_CLASS "OUTPUT"', 'COLOR_REP "RGB_XYZ"', "",
             "NUMBER_OF_FIELDS 7", "BEGIN_DATA_FORMAT",
             "SAMPLE_ID RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z",
             "END_DATA_FORMAT", "",
             f"NUMBER_OF_SETS {len(rgb)}", "BEGIN_DATA"]
    for sid, (r, g, b) in zip(ids, rgb):
        # A plausible XYZ so the parser is satisfied; never read by this check.
        y = max(0.01, (r + g + b) / 3.0)
        lines.append(f"{sid} {r:.4f} {g:.4f} {b:.4f} "
                     f"{y * 0.95:.4f} {y:.4f} {y * 1.09:.4f}")
    lines += ["END_DATA", ""]
    path.write_text("\n".join(lines))
    return path


#: A chart whose patches are far apart, as a real one is.
CHART = [(100.0, 100.0, 100.0), (0.0, 0.0, 0.0), (100.0, 0.0, 0.0),
         (0.0, 100.0, 0.0), (0.0, 0.0, 100.0), (50.0, 25.0, 75.0)]


@pytest.fixture
def chart(tmp_path):
    return _write(tmp_path / "chart.ti2", CHART)


def _measured(tmp_path, rgb, ids=None):
    return parse_ti3(_write(tmp_path / "m.ti3", rgb, ids, kind="CTI3"))


# ---- the normal case ------------------------------------------------------
def test_an_untouched_measurement_is_verified(tmp_path, chart):
    v = verify_patch_identity(_measured(tmp_path, CHART), chart)
    assert v["verdict"] == "verified"
    assert v["compared"] == len(CHART)
    assert v["mismatched"] == 0
    assert v["paired_by"] == "SAMPLE_ID"


def test_rounding_does_not_trip_it(tmp_path, chart):
    """The real round trip's worst error was 0.5 on the 0..255 scale — 0.196
    here. A check that fired on that would cry wolf on every import."""
    nudged = [(r + 0.196, g - 0.196, b + 0.19) for r, g, b in CHART]
    v = verify_patch_identity(_measured(tmp_path, nudged), chart)
    assert v["verdict"] == "verified", v
    assert v["worst"] < PATCH_IDENTITY_TOL


# ---- the case this exists for --------------------------------------------
def test_a_reordered_measurement_is_caught(tmp_path, chart):
    """i1Profiler's ScramblePatches, or any tool that re-orders: the IDs still
    read 1..N, so nothing else in the app can tell."""
    shuffled = [CHART[i] for i in (1, 0, 3, 2, 5, 4)]
    v = verify_patch_identity(_measured(tmp_path, shuffled), chart)
    assert v["verdict"] == "mismatch"
    assert v["mismatched"] == len(CHART)
    assert "may not line up" in v["reason"] or "different colour" in v["reason"]


def test_the_wrong_chart_entirely_is_caught(tmp_path, chart):
    other = [(0.0, 0.0, 0.0)] * len(CHART)
    v = verify_patch_identity(_measured(tmp_path, other), chart)
    assert v["verdict"] == "mismatch"


# ---- the cases that must NOT be called a fault ---------------------------
def test_a_partial_measurement_is_not_a_fault(tmp_path, chart):
    """Reading part of a chart is a normal, supported state. Flagging it would
    be a false alarm on a first-class workflow — and it was, in the first
    version of this check, on a real 940-patch project measured to 924."""
    part = CHART[:3]
    v = verify_patch_identity(_measured(tmp_path, part, ids=["1", "2", "3"]),
                              chart)
    assert v["verdict"] == "verified"
    assert v["compared"] == 3


def test_a_measurement_read_out_of_order_but_correctly_paired(tmp_path, chart):
    """Rows in a different order but carrying their own IDs are fine — the
    pairing is by ID, and that is what the report uses."""
    order = [4, 0, 2]
    rgb = [CHART[i] for i in order]
    ids = [str(i + 1) for i in order]
    v = verify_patch_identity(_measured(tmp_path, rgb, ids=ids), chart)
    assert v["verdict"] == "verified", v


def test_scales_are_reconciled(tmp_path, chart):
    """i1Profiler exports 0..255, ChromIQ's charts are 0..100. Comparing the
    two scales directly would make every identical patch look wrong."""
    as_255 = [(r * 2.55, g * 2.55, b * 2.55) for r, g, b in CHART]
    v = verify_patch_identity(_measured(tmp_path, as_255), chart)
    assert v["verdict"] == "verified", v


# ---- it must never be the reason a report fails --------------------------
@pytest.mark.parametrize("ti2", [None, "missing"])
def test_no_chart_means_unchecked_not_failed(tmp_path, chart, ti2):
    path = None if ti2 is None else tmp_path / "nope.ti2"
    v = verify_patch_identity(_measured(tmp_path, CHART), path)
    assert v["verdict"] == "unchecked"
    assert v["reason"]


def test_an_unreadable_chart_means_unchecked(tmp_path):
    bad = tmp_path / "bad.ti2"
    bad.write_text("this is not a CGATS file at all")
    v = verify_patch_identity(_measured(tmp_path, CHART), bad)
    assert v["verdict"] == "unchecked"


def test_a_measurement_without_device_values_means_unchecked(tmp_path, chart):
    class _NoRgb:
        rgb = np.array([])
        sample_ids: list = []
    v = verify_patch_identity(_NoRgb(), chart)
    assert v["verdict"] == "unchecked"


def test_the_verdict_is_json_able(tmp_path, chart):
    import json
    json.dumps(verify_patch_identity(_measured(tmp_path, CHART), chart))


# ---- and the report carries it -------------------------------------------
def test_build_report_reports_it(tmp_path):
    """The whole point of this release: the answer is stated."""
    import inspect
    from workflow import measurement_report as mr
    src = inspect.getsource(mr.build_report)
    assert 'report["patch_identity"]' in src, \
        "build_report must record the verdict"
    assert "verify_patch_identity" in src


def test_the_report_states_it_but_changes_nothing(tmp_path):
    """Step one reports and does not act. If a later change starts suppressing
    or altering figures on the strength of this check, that is a decision, and
    it should break this test rather than happen quietly."""
    import inspect
    from workflow import measurement_report as mr
    src = inspect.getsource(mr.build_report)
    after = src.split('report["patch_identity"]', 1)[1]
    for forbidden in ("de00 = None", "del report[", "return {}"):
        assert forbidden not in after, (
            f"the identity check appears to suppress results ({forbidden!r}); "
            "this release only reports")
