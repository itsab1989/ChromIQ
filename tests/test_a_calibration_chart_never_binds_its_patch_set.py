"""Showing a calibration chart never binds its .ti1 as a patch set (#182).

Found by the 62f8ea5d review, driving Demo-Full-RGB on screen: Run type
Calibration showed the project's stored calibration chart, whose sidecar is
older than the `patch_set_given` record, so the B8-1460 question asked targen
whether the panel makes those patches. It did not, and the answer bound the
calibration .ti1 as "this run's own patch set": the targen panel came up
locked, with "Edit patch recipe (override preset)" on screen, in Calibration.

62f8ea5d makes Generate in Calibration ignore every binding and build targen's
calibration chart into cal/ (calibration_run_type §4.2), so the lock promised
something Generate would not do, and it kept "Single Channel Steps" out of
reach. A calibration chart is always made by targen; nothing is bound there.
"""
from __future__ import annotations

import pytest

from core.measurement_target import RUN_TYPE_CALIBRATION
from tests._cal_target_fixture import (bound, make_window, override_row_shown,
                                       show_run, targen_panel_enabled,
                                       write_run_chart)


class _CalSlot:
    """`write_run_chart` writes into anything with `ensure_dir` and `stem`."""

    def __init__(self, cal):
        self._cal = cal
        self.stem = cal.stem

    def ensure_dir(self):
        self._cal.dir.mkdir(parents=True, exist_ok=True)
        return self._cal.dir


@pytest.fixture
def win(qapp, tmp_path):
    w = make_window(qapp, tmp_path)
    proj = w._file_mgr.project()
    run1 = proj.current_run()
    write_run_chart(run1, given=False)
    show_run(w, qapp, run1.id)
    yield w, proj
    w.close()


@pytest.mark.parametrize("given", [True, None])
def test_the_calibration_chart_shown_binds_nothing(win, qapp, given):
    w, proj = win
    tc = w._tab_chart
    files = write_run_chart(_CalSlot(proj.calibration), given=bool(given),
                            with_results=False)
    w._target_ctl.set_run_type(RUN_TYPE_CALIBRATION)
    qapp.processEvents()
    assert tc._calibration_selected()
    # What the chart display does with the chart's own .ti1, given or (an
    # older record) whatever the B8-1460 answer says.
    tc._rebind_patch_set_from_run(files["ti1"], given=given)
    tc._rebind_patch_set_from_run(files["ti1"], given=True, sig=[])
    qapp.processEvents()
    assert not bound(tc), "a patch set was bound in Calibration"
    assert not override_row_shown(tc)
    assert targen_panel_enabled(tc), "the targen panel is locked in Calibration"
