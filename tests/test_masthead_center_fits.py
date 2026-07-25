"""The masthead hosts the Profile-run bar on its version rail by absolute
geometry, not a layout — so a centre widget that grows silently gets positioned
off the rail and clipped. That happened when the bar gained its second line
("Location being edited", #130): the rail was a fixed 28 px, the bar became
40 px, and the centring maths put it 6 px ABOVE the rail with its bottom cut off
by the masthead's own edge. These tests pin the invariant that matters — the
centre widget is fully inside both the rail and the masthead."""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtCore import QSettings, QSize                # noqa: E402
from PyQt6.QtWidgets import QApplication, QLabel, QWidget  # noqa: E402

from core.file_manager import FileManager, Project       # noqa: E402
from core.measurement_target import RUN_TYPE_PROFILING   # noqa: E402
from core.settings import AppSettings                    # noqa: E402
from ui.masthead_header import MastheadHeader            # noqa: E402
from ui.measurement_target_bar import (MeasurementTargetBar,       # noqa: E402
                                       MeasurementTargetController)


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


class _Tall(QWidget):
    """A centre widget taller than the default rail."""
    def __init__(self, h: int):
        super().__init__()
        self._h = h
        QLabel("x", self)

    def sizeHint(self) -> QSize:            # noqa: N802
        return QSize(300, self._h)


def _assert_center_fits(mast: MastheadHeader) -> None:
    w = mast._center_widget
    g = w.geometry()
    rail_top = mast.height() - mast._rail_h
    assert g.top() >= rail_top, (
        f"centre widget starts {rail_top - g.top()} px above the rail")
    assert g.bottom() <= mast.height(), (
        f"centre widget overflows the masthead by {g.bottom() - mast.height()} px")


def test_default_height_is_unchanged_for_a_short_widget(qapp):
    mast = MastheadHeader(version="9.9.9")
    mast.resize(1000, mast.sizeHint().height())
    mast.set_center_widget(_Tall(22))
    assert mast.height() == 116                  # the long-standing masthead height
    _assert_center_fits(mast)


@pytest.mark.parametrize("h", [30, 40, 56, 80])
def test_rail_grows_so_a_taller_widget_still_fits(qapp, h):
    mast = MastheadHeader(version="9.9.9")
    mast.resize(1000, mast.sizeHint().height())
    mast.set_center_widget(_Tall(h))
    mast.resize(1000, mast.sizeHint().height())
    assert mast.height() > 116
    _assert_center_fits(mast)


def test_the_real_target_bar_fits_on_the_rail(qapp, tmp_path):
    """The case that actually broke: the two-line Profile-run bar."""
    s = AppSettings(); s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    root = tmp_path / "ChromIQ"; root.mkdir()
    s.set("custom_output_path", str(root))
    fm = FileManager(s)
    Project.create(root / "P", "P").current_run().ensure_dir()
    fm.set_target_name("P")
    ctl = MeasurementTargetController(fm)
    bar = MeasurementTargetBar(ctl)
    ctl.set_profile_run("run1"); ctl.set_run_type(RUN_TYPE_PROFILING)

    mast = MastheadHeader(version="9.9.9")
    mast.set_center_widget(bar)
    mast.resize(1200, mast.sizeHint().height())
    mast.reposition_center()

    assert bar.sizeHint().height() > 28, "the bar is the two-line one"
    _assert_center_fits(mast)
    assert bar._location.text().endswith("runs/run1/")
