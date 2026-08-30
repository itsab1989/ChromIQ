"""The CR30 aiming help: what it draws, when, and at what size.

A CR30 is aimed by hand through a 4 mm opening, and its 33 mm body hides the
patch the moment it is lowered. The overlay draws that body to scale so the user
can line it up on the NEIGHBOURS before contact — the technique the agreed
mockup (`docs/design/mockups/cr30/aiming-circle.png`) was drawn to support.

Two things here are safety, not decoration:

* the circles are a factual claim about hardware, drawn at scale. An unknown
  dpi must draw NOTHING rather than a circle of the wrong size.
* the aperture circle is the ONLY place a patch too small for the instrument is
  ever visible, because nothing refuses such a chart (Basti, 2026-08-30:
  ArgyllCMS offers no such guard for any instrument, so ChromIQ invents none).

These drive the real `TiffPreview` and the real constants. Only the settings
backend and the chart sidecar are stood in for — the outermost edges.
"""
import json

import pytest
from PyQt6.QtCore import QRect
from PyQt6.QtGui import QColor

from workflow.layout_engine.instruments import (CR30_APERTURE_DIAMETER_MM,
                                                CR30_BODY_DIAMETER_MM)

#: The sourced figures. If either changes, the change must be deliberate: they
#: are drawn on screen at scale and the user is entitled to trust them.
def test_the_figures_are_the_sourced_ones():
    assert CR30_BODY_DIAMETER_MM == 33.0
    assert CR30_APERTURE_DIAMETER_MM == 4.0


def _preview(qtbot):
    from ui.tiff_preview import TiffPreview
    p = TiffPreview()
    qtbot.addWidget(p)
    return p


def test_it_draws_nothing_until_it_is_switched_on(qtbot):
    p = _preview(qtbot)
    assert p._aim_overlay is False


def test_an_unknown_scale_disarms_it_rather_than_guessing(qtbot):
    """A circle that claims to be 33 mm and is not is worse than no circle."""
    p = _preview(qtbot)
    p.set_aim_overlay(True, 0.0, 0.0)
    assert p._aim_body_px == 0.0 and p._aim_aperture_px == 0.0
    p.set_aim_overlay(True, -5.0, -9.0)
    assert p._aim_body_px == 0.0, "a negative diameter must not become a circle"


def test_the_diameters_are_kept_as_given(qtbot):
    p = _preview(qtbot)
    p.set_aim_overlay(True, 47.2, 389.8)
    assert (p._aim_aperture_px, p._aim_body_px) == (47.2, 389.8)


# -- the scale, computed from the chart's own dpi ---------------------------

class _Tab:
    """Enough of TabMeasure for the real `_cr30_aim_diameters_px` to run."""

    def __init__(self, tmp_path, dpi, is_cr30=True):
        from ui.tabs.tab_measure import TabMeasure
        self._cr30_aim_diameters_px = TabMeasure._cr30_aim_diameters_px.__get__(self)
        self._is = is_cr30
        self._ti1_path = tmp_path / "chart.ti2"
        self._ti1_path.write_text("")
        if dpi is not None:
            side = self._ti1_path.with_suffix(".channels.json")
            side.write_text(json.dumps({"layout": {"dpi": dpi}}))

    def _chart_is_cr30(self):
        return self._is

    @staticmethod
    def _chart_file_for(path):
        return path


@pytest.mark.parametrize("dpi", [300.0, 600.0, 720.0])
def test_the_scale_comes_from_the_charts_own_dpi(tmp_path, dpi):
    ap, body = _Tab(tmp_path, dpi)._cr30_aim_diameters_px()
    assert body == pytest.approx(CR30_BODY_DIAMETER_MM * dpi / 25.4)
    assert ap == pytest.approx(CR30_APERTURE_DIAMETER_MM * dpi / 25.4)
    # …and the ratio is the physical one, whatever the dpi.
    assert body / ap == pytest.approx(33.0 / 4.0)


def test_no_sidecar_means_no_circles(tmp_path):
    t = _Tab(tmp_path, None)
    assert t._cr30_aim_diameters_px() == (0.0, 0.0)


def test_a_corrupt_sidecar_means_no_circles(tmp_path):
    t = _Tab(tmp_path, 300.0)
    t._ti1_path.with_suffix(".channels.json").write_text("{not json")
    assert t._cr30_aim_diameters_px() == (0.0, 0.0)


def test_a_zero_dpi_means_no_circles(tmp_path):
    assert _Tab(tmp_path, 0.0)._cr30_aim_diameters_px() == (0.0, 0.0)


def test_a_non_cr30_chart_gets_nothing(tmp_path):
    assert _Tab(tmp_path, 300.0, is_cr30=False)._cr30_aim_diameters_px() == (0.0, 0.0)


# -- the aperture warning ---------------------------------------------------

def _aperture_pixels(qtbot, tmp_path, patch_mm, dpi=300.0):
    """Render one armed patch and count the alarm-red pixels.

    The page is a REAL image loaded through the widget's own `load_tiff`. An
    earlier version hand-set `_pages` and rendered nothing at all, which scored
    a confident zero — the same vacuous probe that has caught me twice today.
    `test_a_patch_smaller_than_the_aperture_is_marked` is the guard against it:
    if the harness draws nothing, that test fails rather than passing.
    """
    from PIL import Image
    p = _preview(qtbot)
    per_mm = dpi / 25.4
    side = round(patch_mm * per_mm)
    tif = tmp_path / f"page_{patch_mm}.tif"
    Image.new("RGB", (600, 600), (128, 128, 128)).save(tif)
    p.resize(700, 700)
    p.load_tiff([tif])
    box = QRect(200, 200, side, side)
    p._active_patch_box = box
    p._active_patch_page = 0
    p._current = 0
    p.set_aim_overlay(True, CR30_APERTURE_DIAMETER_MM * per_mm,
                      CR30_BODY_DIAMETER_MM * per_mm)
    p.show()
    qtbot.waitExposed(p)
    # waitExposed returns before the paint has landed; without this the grab is
    # of an unpainted widget and every count is zero — vacuously "no warning".
    from PyQt6.QtWidgets import QApplication
    QApplication.processEvents()
    im = p.grab().toImage()
    red = QColor("#ff2b2b")
    return sum(1 for y in range(im.height()) for x in range(im.width())
               if (abs(im.pixelColor(x, y).red() - red.red()) < 45
                   and im.pixelColor(x, y).green() < 100
                   and im.pixelColor(x, y).blue() < 100))


def test_a_patch_smaller_than_the_aperture_is_marked(qtbot, tmp_path):
    """3 mm patch, 4 mm opening: part of every reading is the neighbour, and
    nothing else in ChromIQ will ever say so."""
    assert _aperture_pixels(qtbot, tmp_path, 3.0) > 0


def test_a_comfortable_patch_is_left_alone(qtbot, tmp_path):
    """12 mm patch: the warning would be noise, so it must not appear."""
    assert _aperture_pixels(qtbot, tmp_path, 12.0) == 0
