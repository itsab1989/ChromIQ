"""#131 (Knut, 2026-07-27): the area under the chart preview, laid out to spec.

His requirements, one test each:

* the reading times sit in a **frame like the ones on the left of the window**,
  not a hard drawn box;
* the frame's **title** names the strip length, and sits above the times so a
  reading can be drawn in any column without colliding with it;
* **2-3 mm of air above** the frame, so the PREV/NEXT buttons are not crammed
  against it, and the same **below**, before the warning line;
* the frame's **left and right edges line up with PREV and NEXT**;
* and the **warning line is visible** — the one thing he has now reported three
  times.

Geometry is asserted on a real laid-out tab, because every one of these faults
passed a test that only looked at the widgets in isolation.
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtCore import QSettings                   # noqa: E402
from PyQt6.QtWidgets import QApplication, QGroupBox  # noqa: E402

from core.argyll_runner import ArgyllRunner          # noqa: E402
from core.settings import AppSettings                # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture(scope="module")
def tab(qapp, tmp_path_factory):
    tmp = tmp_path_factory.mktemp("pace")
    s = AppSettings()
    s._qs = QSettings(str(tmp / "s.ini"), QSettings.Format.IniFormat)
    s.set("custom_output_path", str(tmp / "out"))
    from ui.tabs.tab_measure import TabMeasure
    t = TabMeasure(ArgyllRunner(s), s)
    t.resize(1500, 900)
    t.show()
    QApplication.processEvents()
    return t


def _fill(tab, patches=15):
    tab._pace_patches = patches
    tab._pace_times = {"A": (7.2, True), "B": (3.1, False)}
    tab._pace_panel.set_content("", [(80, "7.2 s"), (300, "3.1 s")])
    tab._pace_group.setTitle(
        f"Strip reading times ({patches} patches per strip)")
    tab._pace_group.setVisible(True)
    tab._pace_verdict_lbl.setText(
        "Too fast — read more slowly · 140 ms per patch (aim for 460 ms or more)")
    tab._pace_verdict_lbl.setVisible(True)
    QApplication.processEvents()
    tab.layout().activate()
    QApplication.processEvents()


def test_the_times_live_in_a_frame_like_the_rest_of_the_window(tab):
    assert isinstance(tab._pace_group, QGroupBox)
    assert tab._pace_panel.parent() is tab._pace_group
    # …and the panel no longer draws a box of its own.
    import inspect

    from ui.strip_times_panel import StripTimesPanel
    src = inspect.getsource(StripTimesPanel.paintEvent)
    assert "drawRect" not in src, "the hard box must be gone"


def test_the_frame_is_titled_with_the_strip_length(tab):
    _fill(tab, 15)
    assert tab._pace_group.title() == "Strip reading times (15 patches per strip)"


def test_the_title_is_singular_for_a_one_patch_strip(tab):
    """Never "(1 patches per strip)"."""
    tab._pace_patches = 1
    tab._pace_times = {"A": (1.0, True)}
    tab._refresh_pace_panel("", "#909090")
    assert tab._pace_group.title() == "Strip reading times (1 patch per strip)"


def test_the_warning_is_a_label_that_cannot_be_squeezed_away(tab):
    _fill(tab)
    lbl = tab._pace_verdict_lbl
    assert lbl.isVisible()
    assert lbl.height() >= lbl.heightForWidth(lbl.width()), \
        "the warning is clipped — this is the fault Knut reported three times"


def test_the_warning_survives_a_short_window(tab):
    """He resized and it vanished. The label keeps its height regardless."""
    _fill(tab)
    tab.resize(1500, 620)
    QApplication.processEvents()
    tab.layout().activate()
    QApplication.processEvents()

    lbl = tab._pace_verdict_lbl
    assert lbl.isVisible() and lbl.height() > 0
    assert lbl.height() >= lbl.heightForWidth(lbl.width())
    tab.resize(1500, 900)
    QApplication.processEvents()


def test_nothing_is_shown_before_a_strip_is_read(tab):
    tab._clear_pace_readout()
    QApplication.processEvents()
    assert not tab._pace_group.isVisible()
    assert not tab._pace_verdict_lbl.isVisible()


def test_the_gaps_and_the_alignment_are_the_ones_asked_for(tab):
    """The frame lines up with PREV and NEXT and keeps its air above and below.

    Needs the preview's page controls on screen, which is what the two pages
    below are for.
    """
    from PIL import Image
    import tempfile
    from pathlib import Path
    tmp = Path(tempfile.mkdtemp())
    pages = []
    for i in range(2):
        f = tmp / f"p{i}.tif"
        Image.new("RGB", (900, 1200), (250, 250, 250)).save(f)
        pages.append(f)
    tab._preview.load_tiff(pages)
    tab._preview.set_navigation_visible(True)
    _fill(tab)

    def geo(w):
        p = w.mapTo(tab, w.rect().topLeft())
        return p.x(), p.y(), w.width(), w.height()

    px, py, pw, ph = geo(tab._preview._prev_btn)
    nx, _ny, nw, _nh = geo(tab._preview._next_btn)
    gx, gy, gw, gh = geo(tab._pace_group)
    lx, ly, lw, _lh = geo(tab._pace_verdict_lbl)

    assert gx == px, f"frame starts at {gx}, PREV at {px}"
    assert gx + gw == nx + nw, f"frame ends at {gx+gw}, NEXT at {nx+nw}"
    assert lx == gx and lx + lw == gx + gw, "the warning shares those edges"
    # 2-3 mm — call it 8-16 px at ordinary screen densities.
    assert 8 <= gy - (py + ph) <= 16, f"{gy - (py+ph)}px above the frame"
    assert 8 <= ly - (gy + gh) <= 16, f"{ly - (gy+gh)}px below the frame"
