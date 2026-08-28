"""#159 (report 11, S6): loading a chart with no TIFF left the PREVIOUS chart's
per-patch geometry in place.

`_setup_stripe_rects` is where `_patch_boxes` is built, and it runs only on the
branch that found TIFFs. The other branch cleared the strip rects and the
preview but not the boxes — so after loading a chart with no preview,
`_locate_patch` still answered with rectangles belonging to a different sheet,
and the split-patch overlay would draw this chart's colours at the last chart's
coordinates.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QRect                                   # noqa: E402
from PyQt6.QtWidgets import QApplication                         # noqa: E402

from core.argyll_runner import ArgyllRunner                      # noqa: E402
from core.settings import AppSettings                            # noqa: E402
from ui.tabs.tab_measure import TabMeasure                       # noqa: E402


@pytest.fixture
def tab():
    QApplication.instance() or QApplication([])
    s = AppSettings()
    return TabMeasure(ArgyllRunner(s), s)


def test_geometry_from_the_previous_chart_does_not_survive(tab, tmp_path):
    tab._patch_boxes = [{"A1": QRect(10, 20, 30, 40)}]
    assert tab._locate_patch("A1")[1] is not None      # the premise

    lonely = tmp_path / "no-preview.ti2"
    lonely.write_text("CTI2\n")                        # a chart with no .tif
    tab._try_load_tiffs(lonely)

    assert tab._tiff_pages == []
    assert tab._locate_patch("A1") == (-1, None), (
        "a chart with no preview kept the previous chart's patch boxes — the "
        "overlay would draw at another sheet's coordinates")
