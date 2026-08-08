"""The overlay window must say WHICH of three things went wrong.

Basti, 2026-08-08, measuring a chart he made long before the layout engine:

    This chart's measurement can't be shown on the patches — it looks like it
    was made for a different chart (the patch layout doesn't match).

It was not made for a different chart. Measured against his own files, the
measurement resolved **90 patches** of that chart with real ΔE values; the only
thing missing was the per-patch geometry, because a printtarg sheet carries
neither a ``.strips.json`` nor a ``channels.json`` ``layout`` block. Telling
someone their good measurement belongs to another chart invites them to discard
it and re-measure — the most expensive possible reaction, since re-measuring
means reprinting and re-reading a whole chart.

The same shape as Knut's report in #130, where an empty ``.ti3`` was also
reported as a mismatch. Both come from the same place: the overlay returning
False says nothing about *why*, so the reason has to be established from the
files. There are three causes and they need three different answers —
re-measure / nothing is wrong / find the right chart.
"""
from __future__ import annotations

import os
import shutil

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from ui.tabs.tab_measure import TabMeasure, patch_boxes_from_sidecar  # noqa: E402


class _Stub:
    """Only what `_overlay_failure_reason` touches — building a tab is not the point."""
    _ti1_path = None
    _overlay_failure_reason = TabMeasure._overlay_failure_reason
    _measurement_is_empty = TabMeasure._measurement_is_empty

    def __init__(self, ti2, ti3):
        self._ti1_path = ti2
        self._ti3 = ti3

    def _existing_ti3_for_chart(self):
        return self._ti3 if self._ti3 and self._ti3.is_file() else None


_CHART = """CTI2

DESCRIPTOR "Argyll Calibration Target chart information 2"
ORIGINATOR "Argyll printtarg"
COLOR_REP "iRGB"

NUMBER_OF_FIELDS 8
BEGIN_DATA_FORMAT
SAMPLE_ID SAMPLE_LOC RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z
END_DATA_FORMAT

NUMBER_OF_SETS 2
BEGIN_DATA
1 "A1" 100.00 100.00 100.00 95.05 100.00 108.90
2 "A2" 0.00 0.00 0.00 0.30 0.31 0.34
END_DATA
"""

_MEASURED = """CTI3

DESCRIPTOR "Argyll Calibration Target chart information 3"
ORIGINATOR "Argyll target"
DEVICE_CLASS "OUTPUT"
COLOR_REP "RGB_XYZ"

NUMBER_OF_FIELDS 8
BEGIN_DATA_FORMAT
SAMPLE_ID SAMPLE_LOC RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z
END_DATA_FORMAT

NUMBER_OF_SETS 2
BEGIN_DATA
1 "A1" 100.00 100.00 100.00 95.05 100.00 108.90
2 "A2" 0.00 0.00 0.00 0.30 0.31 0.34
END_DATA
"""

_EMPTY = _MEASURED.split("NUMBER_OF_SETS")[0] + """NUMBER_OF_SETS 0
BEGIN_DATA
END_DATA
"""

# Genuinely foreign: `per_patch_overlay` matches on SAMPLE_ID, so renaming only
# the SAMPLE_LOC still matches and would make this fixture prove nothing.
_FOREIGN = (_MEASURED.replace('1 "A1"', '501 "Z9"')
                     .replace('2 "A2"', '502 "Z8"'))


def _make(tmp_path, ti3_body):
    ti2 = tmp_path / "chart.ti2"
    ti2.write_text(_CHART)
    ti3 = tmp_path / "chart.ti3"
    ti3.write_text(ti3_body)
    return _Stub(ti2, ti3)


def test_a_pre_engine_chart_is_not_called_a_different_chart(tmp_path):
    """Basti's case. The readings match; only the geometry is missing."""
    stub = _make(tmp_path, _MEASURED)
    # the premise: this chart really does carry no per-patch geometry
    assert not any(patch_boxes_from_sidecar(stub._ti1_path, 1)), \
        "premise failed — the fixture chart should have no geometry sidecar"
    assert stub._overlay_failure_reason() == "no_geometry", (
        "a printtarg chart with a perfectly good measurement is being reported "
        "as belonging to a different chart"
    )


def test_an_empty_measurement_is_still_reported_as_empty(tmp_path):
    """Knut's #130 case must not regress while fixing Basti's."""
    stub = _make(tmp_path, _EMPTY)
    assert stub._overlay_failure_reason() == "empty"


def test_a_genuinely_foreign_measurement_still_says_so(tmp_path):
    """The warning that matters must survive: don't make everything 'no_geometry'."""
    stub = _make(tmp_path, _FOREIGN)
    assert stub._overlay_failure_reason() == "mismatch"


def test_no_measurement_at_all_is_not_a_geometry_claim(tmp_path):
    ti2 = tmp_path / "chart.ti2"
    ti2.write_text(_CHART)
    assert _Stub(ti2, None)._overlay_failure_reason() == "mismatch"


@pytest.mark.skipif(not (os.path.expanduser("~/ChromIQ/printer-test/runs/run1"
                                            "/printer-test.ti3")
                         and os.path.isfile(os.path.expanduser(
                             "~/ChromIQ/printer-test/runs/run1/printer-test.ti3"))),
                    reason="the reporter's own project is not on this machine")
def test_the_reported_project_reproduces_it(tmp_path):
    """Against the real files that produced the report, when they are present.

    Copied first: `Project.load` migrates in place and a test must never write
    into the user's own projects.
    """
    src = os.path.expanduser("~/ChromIQ/printer-test/runs/run1")
    dst = tmp_path / "run1"
    shutil.copytree(src, dst)
    stub = _Stub(dst / "printer-test.ti2", dst / "printer-test.ti3")
    assert stub._overlay_failure_reason() == "no_geometry"
