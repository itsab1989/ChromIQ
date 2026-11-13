"""An i1iO chart is shown the way it is used (the owner, 2026-11-13): landscape,
as it lies on the table, its letters and numbers upright, wherever ChromIQ
shows it, through the shared preview's own view rotation, so every overlay,
the pointer readout and every click turn with it. Its paper is named the way
it is used, the Print tab says how the upright page is printed and laid on the
table, and a report names the i1iO. Other charts, and the Beta off, are
untouched.
"""
from __future__ import annotations

import json
import os

import pytest
from PyQt6.QtGui import QColor

from tests.test_fd9_4325_display_rotation import (_label_point, _settle,
                                                  _shown)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
DPI = 100


@pytest.fixture(autouse=True)
def i1io_on():
    from workflow.i1io import support
    before = support._latched
    support.set_enabled_for_this_process(True)
    try:
        yield
    finally:
        support._latched = before


@pytest.fixture
def chart(tmp_path):
    from tests.test_i1io_chart import _ti1
    from workflow.layout_engine import chart as C
    ti1 = _ti1(tmp_path / "c.ti1", 504)
    r = C.build_chart(ti1, tmp_path / "c", instrument="IO2", paper="A4",
                      dpi=DPI, randomize=False)
    side = json.loads((tmp_path / "c.i1io.json").read_text(encoding="utf-8"))
    return r, side


def _pv(qapp, paths):
    from ui.tiff_preview import TiffPreview
    pv = TiffPreview()
    pv.set_print_preview(False)
    pv.set_legend_enabled(False)
    pv.resize(800, 700)
    pv._img_label.setFixedSize(760, 540)
    pv.show()
    pv.load_tiff(paths)
    return pv


def test_every_preview_shows_an_i1io_chart_as_on_the_table(qapp, chart,
                                                             tmp_path):
    from workflow.i1io import support
    r, _side = chart
    assert support.display_rotation_for(r.tiff_paths) == 90
    pv = _pv(qapp, r.tiff_paths)
    try:
        assert pv.view_rotation() == 90       # no host rule needed
    finally:
        pv.deleteLater()


def test_other_charts_and_the_beta_off_are_never_turned(qapp, chart, tmp_path):
    from tests.test_i1io_chart import _ti1
    from workflow.i1io import support
    from workflow.layout_engine import chart as C
    other = C.build_chart(_ti1(tmp_path / "o.ti1", 50), tmp_path / "o",
                          instrument="i1", paper="A4", dpi=DPI)
    assert support.display_rotation_for(other.tiff_paths) == 0
    r, _side = chart
    support.set_enabled_for_this_process(False)
    assert support.display_rotation_for(r.tiff_paths) == 0
    pv = _pv(qapp, r.tiff_paths)
    try:
        assert pv.view_rotation() == 0
    finally:
        pv.deleteLater()


def test_a_click_on_the_drawn_c7_selects_c7(qapp, chart):
    """Found by its colour on screen, not by the mapping under test: the one
    magenta patch, C7, is where the pointer hits C7, and the pointer reads
    C7's centre on paper; on screen C7 lies right of C6 and below B7."""
    from PyQt6.QtCore import QRect
    r, side = chart
    k = DPI / 25.4
    rects = {}
    for st in side["pages"][0]["strips"]:
        for p in st["patches"]:
            cx, cy = p["centre_mm"]
            pw, pl = side["patch_mm"]
            rects[p["loc"]] = QRect(round((cx - pw / 2) * k),
                                    round((cy - pl / 2) * k),
                                    round(pw * k), round(pl * k))
    pv = _pv(qapp, r.tiff_paths)
    try:
        _settle(qapp, pv)
        pv.set_coord_readout(True, DPI)
        pv.set_patch_overlay(0, [(rects["C7"], QColor(13, 254, 251),
                                  QColor(13, 254, 251), False)],
                             replace_page=True)
        pv.set_overlay_mode("expected")
        pv.set_patch_click_enabled(True, [rects])
        _settle(qapp, pv)
        img = _shown(pv)
        xs, ys = [], []
        for y in range(img.height()):
            for x in range(img.width()):
                if img.pixelColor(x, y) == QColor(13, 254, 251):
                    xs.append(x)
                    ys.append(y)
        assert xs, "C7 is not on screen"
        centre = _label_point(pv, ((min(xs) + max(xs) + 1) / 2,
                                   (min(ys) + max(ys) + 1) / 2))
        hit = pv._patch_at(pv._img_label.mapTo(pv, centre.toPoint()))
        assert hit is not None and hit[0] == "C7"
        mm = pv._coord_mm_at(centre)
        want = rects["C7"].center()
        assert mm[0] == pytest.approx((want.x() + 0.5) / k, abs=1.0)
        assert mm[1] == pytest.approx((want.y() + 0.5) / k, abs=1.0)
        # the picture is the page turned a quarter turn clockwise: C7's
        # paper box, turned, is where the magenta is
        w, h = img.width(), img.height()
        assert (max(xs) - min(xs)) > (max(ys) - min(ys)) * 0.9  # 10 x 8 mm
    finally:
        pv.deleteLater()


def test_the_paper_is_named_as_it_is_used(qapp):
    from workflow.layout_engine import papers
    labels = [lab for _c, lab, _d in papers.list_papers("IO2", for_engine=True)]
    assert labels and all("Landscape" in lab for lab in labels), labels
    # A4 and Letter first; every other sheet inside the table's reach
    # follows (review 5, item 7)
    assert [c for c, _l, _d in papers.list_papers("IO2")][:2] == ["A4",
                                                                 "Letter"]


def test_a_report_on_an_i1io_chart_names_the_i1io(chart, tmp_path):
    """Review r2: a measurement that names no instrument, on an i1iO chart,
    read "Unknown instrument"."""
    from workflow.measurement_report import _i1io_chart_instrument
    r, _side = chart
    ti3 = r.ti2_path.with_suffix(".ti3")
    ti3.write_text("CTI3\n", encoding="utf-8")
    assert _i1io_chart_instrument(ti3) == "X-Rite i1iO"
    from workflow.i1io import support
    support.set_enabled_for_this_process(False)
    assert _i1io_chart_instrument(ti3) is None


def test_the_highlight_for_strip_c_covers_strip_c_on_screen(qapp, chart):
    """The Measure tab's strip highlight turns with the picture: what the
    highlight changes on screen lies over strip C as shown (a horizontal row
    on the table), not over another strip or across the strips."""
    from PyQt6.QtCore import QRect
    import numpy as np
    r, side = chart
    k = DPI / 25.4
    strips = side["pages"][0]["strips"]
    rects = []
    for st in strips:
        ys = [p["centre_mm"][1] for p in st["patches"]]
        pw, pl = side["patch_mm"]
        x0 = st["x_mm"] - pw / 2
        rects.append(QRect(round(x0 * k), round((min(ys) - pl / 2) * k),
                           round(pw * k),
                           round((max(ys) - min(ys) + pl) * k)))
    pv = _pv(qapp, r.tiff_paths)
    try:
        pv.set_stripe_rects(rects)
        _settle(qapp, pv)

        def arr():
            img = _shown(pv)
            ptr = img.bits()
            ptr.setsize(img.sizeInBytes())
            return np.frombuffer(ptr, np.uint8).reshape(
                img.height(), img.bytesPerLine() // 4, 4)[:, :img.width(),
                                                          2::-1].copy()
        before = arr()
        pv.highlight_stripe(2)
        _settle(qapp, pv)
        after = arr()
        changed = np.argwhere((before != after).any(axis=2))
        assert len(changed), "the highlight changed nothing on screen"
        ys = changed[:, 0]
        # where strips B, C and D are on screen, found by colour
        colours = {1: (13, 254, 251), 2: (251, 13, 254), 3: (254, 251, 13)}
        pv.highlight_stripe(-1)
        pv.set_patch_overlay(0, [(rects[i], QColor(*c), QColor(*c), False)
                                 for i, c in colours.items()],
                             replace_page=True)
        pv.set_overlay_mode("expected")
        _settle(qapp, pv)
        shown = arr()
        rows = {}
        for i, c in colours.items():
            hit = np.argwhere((shown == np.array(c, np.uint8)).all(axis=2))
            assert len(hit), i
            rows[i] = (hit[:, 0].min(), hit[:, 0].max(),
                       hit[:, 1].max() - hit[:, 1].min())
        # each strip is a ROW on screen (wider than tall), B above C above D
        for i in colours:
            assert rows[i][2] > 3 * (rows[i][1] - rows[i][0])
        assert rows[1][0] < rows[2][0] < rows[3][0]
        # and the highlight sits on C's row
        assert rows[2][0] - 1 <= ys.mean() <= rows[2][1] + 1
    finally:
        pv.deleteLater()
