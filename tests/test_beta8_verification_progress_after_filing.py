"""A verification's progress bar follows its readings into the dated folder
(#182, Knut 5973177088: "after measurement was completed the progress still
showed 0%").

Reproduced on screen on a copy of his project (Create Chart, Generate, Print
tab, Measure, through the real engine in replay mode): the bar counted 4.5 %
to 100 % while reading, then fell to 0.0 % on Finish and stayed there.
`_on_measure_done` settled the count from the files BEFORE
`_finalize_verification` moved the readings from beside the chart into the
dated folder the bar selects, so it read neither and nothing counted again.
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtWidgets import QApplication  # noqa: E402

from tests.test_182_a_a_verification_writes_its_automatic_report import (  # noqa: E402
    _guided_ending, _setup)


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def test_the_bar_reads_the_filed_verification(tmp_path, qapp, monkeypatch):
    s, fm, ctl, run, tab = _setup(tmp_path, qapp, tick=False)
    # Start moved the bar to the new date, as `_on_start` does.
    v = run.new_verification()
    v.ensure_dir()
    ctl.set_verification_id(v.id)
    saved = []
    try:
        _guided_ending(tab, run, monkeypatch, saved=saved)
        qapp.processEvents()
        assert saved and saved[0] == v.measurement_ti3
        assert tab._selected_measurement_ti3() == v.measurement_ti3
        assert tab._preview.measurement_progress() == 100.0, (
            "the bar did not count the verification it had just filed")
    finally:
        tab.deleteLater()
