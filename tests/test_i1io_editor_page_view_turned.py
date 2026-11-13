"""THE PATCH SET EDITOR SHOWS AN i1iO CHART AS IT LIES ON THE TABLE.

Every preview built on `ui.tiff_preview.TiffPreview` already turns an i1iO
chart a quarter turn clockwise (`workflow.i1io.support.display_rotation_for`,
the one shared rule). The editor's own page view (`Ti2RelayoutDialog`,
`_PreviewLabel`) did not. It now turns with the same rule, display only:

* every rect it keeps (the engine's patch rects, the spacer rects) stays in
  the page's own pixels, and `_image_to_view` / `_view_to_image` turn them
  for the highlight and back for a click or a marquee;
* a click on a patch as shown selects THAT patch, a marquee selects what it
  covers on screen, and the highlight lands on the patch selected;
* every other chart is shown exactly as before (rotation 0, same picture).
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PyQt6")

from PyQt6.QtCore import QPoint, QRect, QSettings, Qt  # noqa: E402

from tests.test_i1io_chart import _ti1  # noqa: E402

DPI = 60


@pytest.fixture(autouse=True)
def i1io_on():
    from workflow.i1io import support
    before = support._latched
    support.set_enabled_for_this_process(True)
    try:
        yield
    finally:
        support._latched = before


def _settings():
    from core.settings import AppSettings
    s = AppSettings()
    s._qs = QSettings(QSettings.Format.IniFormat, QSettings.Scope.UserScope,
                      "chromiq-test", "i1io-editor-turned")
    s._qs.clear()
    s.set("use_chromiq_layout_engine", True)
    return s


def _chart(tmp_path, instrument):
    from workflow.layout_engine import chart, geometry, instruments, papers
    ti1 = _ti1(tmp_path / "c.ti1", 60)
    result = chart.build_chart(ti1, tmp_path / "c", instrument=instrument,
                               paper="A4", dpi=DPI, seed=3)
    g = instruments.geom_from_build_kwargs({"instrument": instrument,
                                            "paper": "A4"})
    w, h = papers.dimensions_mm("A4")
    rects = geometry.patch_rects_px(g, w, h, result.layout, DPI)
    return result, rects


def _open(qapp, tmp_path, result, rects):
    import ui.dialogs.ti2_relayout_dialog as M
    from core.argyll_runner import ArgyllRunner
    from workflow import ti2_relayout as R
    from workflow.layout_engine import permutation
    ed = M.Ti2RelayoutDialog(ArgyllRunner(_settings()), _settings())
    ed._spec = R.ChartSpec.from_ti2(result.ti2_path)
    ed._engine_panel_grp.setVisible(True)
    n = result.layout.total_patches
    for i in range(n):
        ed._grid.addItem(ed._grid_item((float(i % 100), 50.0, 50.0)))
    ed._engine_patch_rects = {(d["page"], d["slot"]): d for d in rects}
    ed._engine_slots = permutation.location_permutation(n, result.seed, True)
    ed._page = 0
    ed._mode_patches.setChecked(True)
    ed._hl_patches.setChecked(True)
    ed._preview.resize(700, 520)
    ed._show_image(result.tiff_paths[0])
    assert ed._engine_active()
    return ed


def _label_point(ed, ix, iy) -> QPoint:
    """Where the page pixel (ix, iy) is on the preview label as shown."""
    u, v = ed._image_to_view(ix, iy)
    dpr = ed._base_pixmap.devicePixelRatio() or 1.0
    off_x = (ed._preview.width() - ed._base_pixmap.width() / dpr) / 2
    off_y = (ed._preview.height() - ed._base_pixmap.height() / dpr) / 2
    B = ed._preview_border
    return QPoint(round(off_x + B + u * ed._preview_scale),
                  round(off_y + B + v * ed._preview_scale))


def test_the_mapping_round_trips_at_every_turn(qapp, tmp_path):
    result, rects = _chart(tmp_path, "IO2")
    ed = _open(qapp, tmp_path, result, rects)
    ed._image_size = (300, 500)
    for rot in (0, 90, 180, 270):
        ed._view_rotation = rot
        for x, y in ((0, 0), (12.5, 40.0), (299, 499)):
            assert ed._view_to_image(*ed._image_to_view(x, y)) == \
                pytest.approx((x, y))
    ed._view_rotation = 90          # clockwise: top-left goes top-right
    assert ed._image_to_view(0, 0) == (500, 0)
    assert ed._image_to_view(0, 500) == (0, 0)


def test_an_i1io_page_is_shown_turned_and_a_click_picks_the_patch(qapp,
                                                                  tmp_path):
    from PIL import Image
    result, rects = _chart(tmp_path, "IO2")
    ed = _open(qapp, tmp_path, result, rects)
    w, h = Image.open(result.tiff_paths[0]).size
    assert h > w                                   # printed portrait
    assert ed._view_rotation == 90
    assert ed._full_pixmap.width() == h and ed._full_pixmap.height() == w
    s2g = ed._engine_slot_to_grid()
    page0 = [d for d in rects if d["page"] == 0]
    for d in (page0[0], page0[len(page0) // 2], page0[-1]):
        cx, cy = d["x"] + d["w"] / 2, d["y"] + d["h"] / 2
        ed._on_preview_click(_label_point(ed, cx, cy),
                             Qt.KeyboardModifier.NoModifier)
        rows = [ed._grid.row(it) for it in ed._grid.selectedItems()]
        assert rows == [s2g[d["slot"]]], d["slot"]


def _array(pm):
    import numpy as np
    from PyQt6.QtGui import QImage
    img = pm.toImage().convertToFormat(QImage.Format.Format_RGB32)
    ptr = img.constBits()
    ptr.setsize(img.sizeInBytes())
    return np.frombuffer(ptr, np.uint8).reshape(
        img.height(), img.bytesPerLine())[:, :img.width() * 4].reshape(
        img.height(), img.width(), 4)[..., :3].copy()


def test_the_highlight_lands_on_the_patch_as_shown(qapp, tmp_path):
    """What the highlight changes on the picture is the selected patch's
    place as shown (turned), not its place on the portrait page."""
    import numpy as np
    result, rects = _chart(tmp_path, "IO2")
    ed = _open(qapp, tmp_path, result, rects)
    ed._grid.clearSelection()
    ed._refresh_preview()
    before = _array(ed._preview.pixmap())
    d = [d for d in rects if d["page"] == 0][5]
    ed._grid.item(ed._engine_slot_to_grid()[d["slot"]]).setSelected(True)
    ed._refresh_preview()
    pm = ed._preview.pixmap()
    after = _array(pm)
    ys, xs = np.nonzero((before != after).any(axis=2))
    assert len(xs)
    dpr = pm.devicePixelRatio() or 1.0
    B, s = ed._preview_border, ed._preview_scale
    a = ed._image_to_view(d["x"], d["y"])
    b = ed._image_to_view(d["x"] + d["w"], d["y"] + d["h"])
    want = (min(a[0], b[0]) * s + B - 1, min(a[1], b[1]) * s + B - 1,
            max(a[0], b[0]) * s + B + 1, max(a[1], b[1]) * s + B + 1)
    got = (xs.min() / dpr, ys.min() / dpr, xs.max() / dpr, ys.max() / dpr)
    assert got == pytest.approx(want, abs=3), (got, want)
    # and it is NOT where the unturned page would have it
    assert abs(got[0] - (d["x"] * s + B)) > 5 or \
        abs(got[1] - (d["y"] * s + B)) > 5


def test_a_marquee_picks_what_it_covers_on_screen(qapp, tmp_path):
    result, rects = _chart(tmp_path, "IO2")
    ed = _open(qapp, tmp_path, result, rects)
    page0 = sorted((d for d in rects if d["page"] == 0),
                   key=lambda d: (d["x"], d["y"]))
    a, b = page0[0], page0[1]         # two neighbours on one strip
    p1 = _label_point(ed, a["x"] + a["w"] / 2, a["y"] + a["h"] / 2)
    p2 = _label_point(ed, b["x"] + b["w"] / 2, b["y"] + b["h"] / 2)
    ed._on_marquee(QRect(p1, p2).normalized(), Qt.KeyboardModifier.NoModifier)
    s2g = ed._engine_slot_to_grid()
    rows = sorted(ed._grid.row(it) for it in ed._grid.selectedItems())
    assert rows == sorted({s2g[a["slot"]], s2g[b["slot"]]})


def test_every_other_chart_is_shown_as_before(qapp, tmp_path):
    from PIL import Image
    result, rects = _chart(tmp_path, "i1")
    ed = _open(qapp, tmp_path, result, rects)
    w, h = Image.open(result.tiff_paths[0]).size
    assert ed._view_rotation == 0
    assert (ed._full_pixmap.width(), ed._full_pixmap.height()) == (w, h)
    d = [d for d in rects if d["page"] == 0][3]
    ed._on_preview_click(_label_point(ed, d["x"] + d["w"] / 2,
                                      d["y"] + d["h"] / 2),
                         Qt.KeyboardModifier.NoModifier)
    assert [ed._grid.row(it) for it in ed._grid.selectedItems()] == \
        [ed._engine_slot_to_grid()[d["slot"]]]


def test_with_i1io_support_off_nothing_is_turned(qapp, tmp_path):
    from workflow.i1io import support
    result, rects = _chart(tmp_path, "IO2")
    ed = _open(qapp, tmp_path, result, rects)
    support._latched = False
    ed._show_image(result.tiff_paths[0])
    assert ed._view_rotation == 0
