"""4.3.25, the owner's ruling of 2026-11-04: an FD-9 chart may be shown TURNED
on screen (Preferences > Beta, under FD-9 support: Off, 90, 180, 270 degrees
clockwise). Display only.

* Every value the screen gives about the chart is the Off value: the pointer's
  paper position, the patch under the pointer, and the picture itself, which
  at every angle is the Off picture turned, pixel for pixel, overlays and all.
* The expected · measured split keeps its meaning ON SCREEN: expected is the
  top-left triangle at every angle, as the legend says, and the legend is
  placed upright under the lowest patch as shown.
* Only FD-9 charts turn; other charts, other previews and the Beta off are
  unaffected, and the chart's files never change.

Synthetic charts and scans only.
"""
from tests._fd9_beta import fd9_beta_on, fd9_windows  # noqa: F401

import hashlib

import pytest
from PyQt6.QtCore import QPoint, QPointF, QRect, QSettings
from PyQt6.QtGui import QColor, QImage, QTransform

from tests.test_fd9_chart_creation import ti1
from workflow.fd9 import support
from workflow.fd9.chart import build_chart, capacity, chart_pages
from workflow.fd9.measurement import checked_chart

DPI = 100
ANGLES = (0, 90, 180, 270)


class _Store(dict):
    def get(self, key, default=None):
        return dict.get(self, key, default)


@pytest.fixture(scope="module")
def chart(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("rot")
    before = support._latched
    support.set_enabled_for_this_process(True)   # built before the autouse
    src, _ = ti1(tmp, rep="RGB", tokens=("R", "G", "B"),
                 count=capacity("A4") + 7)
    r = build_chart(src, tmp / "rot", paper="A4", dpi=DPI, randomize=False,
                    sheet_project="Rot", sheet_run="1")
    _, doc, locations = checked_chart(r.ti2_path)
    support._latched = before
    return r, chart_pages(doc), locations


def _boxes(page):
    """{loc-ish id: image-px QRect} of one page, from the chart's own grid."""
    k = DPI / 25.4
    pw, ph = page.get("patch_mm", [8, 8])
    out = {}
    for row in page["rows"]:
        for p in row:
            x, y = p["centre_mm"]
            out[p["id"]] = QRect(round((x - pw / 2) * k), round((y - ph / 2) * k),
                                 round(pw * k), round(ph * k))
    return out


def _preview(qapp, w, h, angle=0, paths=None):
    from ui.tiff_preview import TiffPreview
    pv = TiffPreview()
    pv.set_print_preview(False)
    pv.set_legend_enabled(False)
    pv.resize(w + 40, h + 160)
    pv._img_label.setFixedSize(w, h)
    pv.show()
    store = _Store(fd9_display_rotation=angle)
    pv.set_rotation_rule(lambda p: support.display_rotation_for(p, store))
    pv._store = store
    if paths is not None:
        pv.load_tiff(paths)
    return pv


def _settle(qapp, pv):
    for _ in range(4):
        qapp.processEvents()
    pv._update_display()
    qapp.processEvents()


def _shown(pv) -> QImage:
    return pv._img_label.pixmap().toImage().convertToFormat(
        QImage.Format.Format_RGB32)


def _label_point(pv, canvas_xy):
    """A pixel of the shown canvas, as a position in the label (QLabel
    centres its pixmap)."""
    pm = pv._img_label.pixmap()
    ls = pv._img_label.size()
    return QPointF(canvas_xy[0] + (ls.width() - pm.width()) / 2,
                   canvas_xy[1] + (ls.height() - pm.height()) / 2)


def _dress(pv, boxes, mode="expected"):
    """Every overlay the Create Chart and Measure previews put on an FD-9
    chart: threshold and measured guides, and a coloured overlay patch."""
    pv.set_margin_guides([("v", 0.07, False), ("h", 0.12, True),
                          ("v", 0.93, False), ("h", 0.88, False)])
    pv.set_measured_guides([("v", 0.1), ("h", 0.2)])
    items = [(rect, QColor(255, 0, 255), QColor(0, 160, 0), i == 3)
             for i, rect in enumerate(list(boxes.values())[:8])]
    pv.set_patch_overlay(0, items, replace_page=True)
    pv.set_overlay_mode(mode)


# ---- the rule ---------------------------------------------------------------

def test_the_setting_is_off_by_default_and_only_takes_a_choice():
    from core.settings import DEFAULTS
    assert DEFAULTS[support.ROTATION_SETTING] == 0
    assert support.ROTATIONS == (0, 90, 180, 270)
    for bad in (45, -90, "x", None, 360):
        assert support.stored_rotation(_Store(fd9_display_rotation=bad)) == 0
    assert support.stored_rotation(_Store(fd9_display_rotation="180")) == 180


def test_only_an_fd9_charts_pages_turn(chart, tmp_path):
    r, _pages, _ = chart
    on = _Store(fd9_display_rotation=180)
    assert support.display_rotation_for(r.tiff_paths, on) == 180
    assert support.display_rotation_for(r.tiff_paths[1:], on) == 180
    # Another chart's TIFF: no .fd9.json beside it.
    other = tmp_path / "plain_01.tif"
    other.write_bytes(r.tiff_paths[0].read_bytes())
    assert support.display_rotation_for([other], on) == 0
    # An .fd9.json left beside a chart the .ti2 says is not the FD-9's.
    (tmp_path / "plain.fd9.json").write_text("{}", encoding="utf-8")
    (tmp_path / "plain.ti2").write_text(
        'CTI2\nTARGET_INSTRUMENT "X-Rite i1Pro"\nBEGIN_DATA_FORMAT\n',
        encoding="utf-8")
    assert support.display_rotation_for([other], on) == 0
    # Off in Preferences.
    assert support.display_rotation_for(r.tiff_paths,
                                        _Store(fd9_display_rotation=0)) == 0


def test_with_fd9_support_off_nothing_turns_and_nothing_is_read(
        chart, monkeypatch):
    r, _p, _ = chart
    support.set_enabled_for_this_process(False)
    import pathlib

    def touched(*_a, **_k):
        raise AssertionError("a file was asked about with FD-9 support off")

    monkeypatch.setattr(pathlib.Path, "is_file", touched)
    on = _Store(fd9_display_rotation=180)
    assert support.display_rotation(on) == 0
    assert support.display_rotation_for(r.tiff_paths, on) == 0


# ---- the picture and every value on it ----------------------------------------

@pytest.mark.parametrize("angle", ANGLES)
def test_the_turned_view_is_the_off_view_turned_pixel_for_pixel(
        qapp, chart, angle):
    """Page, frame, threshold and measured guide lines, the coloured patches
    and their warn outline: all of it is exactly the Off picture, turned."""
    r, pages, _ = chart
    boxes = _boxes(pages[0])
    W, H = 640, 520
    vw, vh = (H, W) if angle in (90, 270) else (W, H)
    off = _preview(qapp, vw, vh, 0, r.tiff_paths)
    on = _preview(qapp, W, H, angle, r.tiff_paths)
    try:
        for pv in (off, on):
            _settle(qapp, pv)
            _dress(pv, boxes)
            _settle(qapp, pv)
        assert off.view_rotation() == 0 and on.view_rotation() == angle
        want = _shown(off).transformed(QTransform().rotate(angle))
        got = _shown(on)
        assert got.size() == want.size()
        assert got == want
    finally:
        off.deleteLater()
        on.deleteLater()


@pytest.mark.parametrize("angle", ANGLES)
def test_the_pointer_reads_the_paper_and_the_right_patch(qapp, chart, angle):
    """Found by its colour on screen, not by the mapping under test: the one
    magenta patch, wherever the turn put it, is the patch the pointer hits,
    and the pointer's X and Y there are that patch's centre on paper."""
    r, pages, _ = chart
    boxes = _boxes(pages[0])
    target_id = list(boxes)[25]
    rect = boxes[target_id]
    pv = _preview(qapp, 640, 520, angle, r.tiff_paths)
    try:
        _settle(qapp, pv)
        pv.set_coord_readout(True, DPI)
        pv.set_patch_overlay(0, [(rect, QColor(255, 0, 255), QColor(255, 0, 255),
                                  False)], replace_page=True)
        pv.set_overlay_mode("expected")
        pv.set_patch_click_enabled(True, [{"T": rect}])
        _settle(qapp, pv)
        img = _shown(pv)
        xs, ys = [], []
        for y in range(img.height()):
            for x in range(img.width()):
                if img.pixelColor(x, y) == QColor(255, 0, 255):
                    xs.append(x)
                    ys.append(y)
        assert xs, "the magenta patch is not on screen"
        centre = _label_point(pv, ((min(xs) + max(xs) + 1) / 2,
                                   (min(ys) + max(ys) + 1) / 2))
        widget_pos = pv._img_label.mapTo(pv, centre.toPoint())
        hit = pv._patch_at(widget_pos)
        assert hit is not None and hit[0] == "T"
        mm = pv._coord_mm_at(centre)
        want = rect.center()
        k = 25.4 / DPI
        assert mm[0] == pytest.approx((want.x() + 0.5) * k, abs=1.5 * k * 2)
        assert mm[1] == pytest.approx((want.y() + 0.5) * k, abs=1.5 * k * 2)
        px = pv._image_px_at(centre)
        assert rect.contains(px[0], px[1])
    finally:
        pv.deleteLater()


@pytest.mark.parametrize("angle", ANGLES)
@pytest.mark.parametrize("scan", [False, True], ids=["layout", "scan grid"])
def test_expected_is_the_top_left_triangle_on_screen_at_every_angle(
        qapp, chart, angle, scan):
    """The owner's rule: positions follow the turn, the split's meaning does
    not. Every patch shows expected (red) in its top-left half ON SCREEN and
    measured (blue) in its bottom-right half, as the legend says."""
    r, pages, _ = chart
    boxes = list(_boxes(pages[0]).values())[:6]
    pv = _preview(qapp, 640, 520, angle, r.tiff_paths)
    try:
        _settle(qapp, pv)
        if scan:
            pv.set_scan_grid([[[[b.left(), b.top()], [b.right() + 1, b.top()],
                                [b.right() + 1, b.bottom() + 1],
                                [b.left(), b.bottom() + 1]] for b in boxes]],
                             {0})
        pv.set_patch_overlay(0, [(b, QColor(255, 0, 0), QColor(0, 0, 255), False)
                                 for b in boxes], replace_page=True)
        pv.set_overlay_mode("both")
        _settle(qapp, pv)
        img = _shown(pv)
        s, ox, oy = pv._paint_geom
        sy = pv._paint_scale_y
        for b in boxes:
            # The patch's corners on screen, through the code's own mapping;
            # which HALF is which is what is under test.
            pts = [pv._virtual_to_label(QPointF(x * s + ox, y * sy + oy))
                   for x, y in ((b.left(), b.top()),
                                (b.right() + 1, b.bottom() + 1))]
            x0, x1 = sorted(p.x() for p in pts)
            y0, y1 = sorted(p.y() for p in pts)
            pm = pv._img_label.pixmap()
            ls = pv._img_label.size()
            dx = (ls.width() - pm.width()) / 2
            dy = (ls.height() - pm.height()) / 2

            def at(fx, fy):
                return img.pixelColor(int(x0 + fx * (x1 - x0) - dx),
                                      int(y0 + fy * (y1 - y0) - dy))
            assert at(0.22, 0.22) == QColor(255, 0, 0), (angle, b)
            assert at(0.78, 0.78) == QColor(0, 0, 255), (angle, b)
    finally:
        pv.deleteLater()


@pytest.mark.parametrize("angle", ANGLES)
def test_the_legend_stays_upright_under_the_lowest_patch_as_shown(
        qapp, chart, angle):
    r, pages, _ = chart
    boxes = list(_boxes(pages[0]).values())
    pv = _preview(qapp, 640, 520, angle, r.tiff_paths)
    try:
        pv.set_legend_enabled(True)
        _settle(qapp, pv)
        pv.set_patch_overlay(0, [(b, QColor(255, 0, 0), QColor(0, 0, 255), False)
                                 for b in boxes], replace_page=True)
        pv.set_overlay_mode("both")
        _settle(qapp, pv)
        cx, cy, tw, th, txt = pv._legend_paint
        assert "expected ◤" in txt
        assert tw > th                       # a row of text, not a column
        pm = pv._img_label.pixmap()
        assert 0 <= cx and cx + tw <= pm.width() + 1
        assert 0 <= cy and cy + th <= pm.height() + 1
        # Below every patch as shown (on A4 there is room under them).
        s, ox, oy = pv._paint_geom
        sy = pv._paint_scale_y
        lowest = max(pv._virtual_to_label(QPointF(x * s + ox, y * sy + oy)).y()
                     for b in boxes for x, y in ((b.left(), b.top()),
                                                 (b.right(), b.bottom())))
        centre = _label_point(pv, (cx + tw / 2, cy + th / 2))
        assert centre.y() > lowest
        # Pointing at the chip hides it, as at Off.
        pv._apply_legend_pointer(centre.toPoint())
        assert pv._legend_hidden
        pv._apply_legend_pointer(QPoint(0, 0))
        assert not pv._legend_hidden
    finally:
        pv.deleteLater()


def test_the_page_is_never_turned_so_the_margins_are_the_papers(qapp, chart):
    """The page the margin inspector and every "Measured from Preview" number
    is measured from is the file's, unturned, at every angle."""
    r, _pages, _ = chart
    pv = _preview(qapp, 640, 520, 0, r.tiff_paths)
    try:
        _settle(qapp, pv)
        size0, margin0 = pv._pixmap.size(), pv._own_margin_frac
        for angle in ANGLES:
            pv._store["fd9_display_rotation"] = angle
            pv.refresh_view_rotation()
            _settle(qapp, pv)
            assert pv.view_rotation() == angle
            assert pv._pixmap.size() == size0
            assert pv._own_margin_frac == margin0
    finally:
        pv.deleteLater()


def test_preferences_apply_live_and_another_chart_goes_back_to_unturned(
        qapp, chart, tmp_path):
    r, _pages, _ = chart
    pv = _preview(qapp, 640, 520, 0, r.tiff_paths)
    try:
        _settle(qapp, pv)
        assert pv.view_rotation() == 0
        pv._store["fd9_display_rotation"] = 270
        pv.refresh_view_rotation()
        assert pv.view_rotation() == 270
        other = tmp_path / "other.tif"
        other.write_bytes(r.tiff_paths[0].read_bytes())
        pv.load_tiff([other])
        assert pv.view_rotation() == 0
        pv.load_tiff(r.tiff_paths)
        assert pv.view_rotation() == 270
        pv.clear()
        assert pv.view_rotation() == 0
    finally:
        pv.deleteLater()


def test_a_preview_without_a_rule_never_turns(qapp, chart):
    from ui.tiff_preview import TiffPreview
    r, _p, _ = chart
    pv = TiffPreview()
    try:
        pv.load_tiff(r.tiff_paths)
        assert pv.view_rotation() == 0
        pv.refresh_view_rotation()
        assert pv.view_rotation() == 0
    finally:
        pv.deleteLater()


@pytest.mark.parametrize("angle", ANGLES)
def test_zoom_and_pan_behave_as_at_off(qapp, chart, angle):
    """The interactive mode (zoom and pan) on a turned view does what it does
    at Off, on the same paper point: zooming about the pointer lands the same
    paper point under it, and a drag moves the picture with the pointer."""
    r, _p, _ = chart
    W, H = 600, 500
    vw, vh = (H, W) if angle in (90, 270) else (W, H)
    off = _preview(qapp, vw, vh, 0, r.tiff_paths)
    on = _preview(qapp, W, H, angle, r.tiff_paths)
    try:
        for pv in (off, on):
            pv.set_interactive(True)
            _settle(qapp, pv)
        focus = QPoint(380, 200)
        vfocus = on._label_to_virtual(QPointF(focus)).toPoint()
        assert on._coord_mm_at(QPointF(focus)) == pytest.approx(
            off._coord_mm_at(QPointF(vfocus)), abs=0.3)
        on._apply_zoom(2.0, focus)
        off._apply_zoom(2.0, vfocus)
        assert on._coord_mm_at(QPointF(focus)) == pytest.approx(
            off._coord_mm_at(QPointF(vfocus)), abs=0.3)
        # A drag of (+30, +10) on screen: the paper point that was under
        # `focus` is now under `focus + (30, 10)`.
        mm = on._coord_mm_at(QPointF(focus))
        dx, dy = on._unturn_vector(30, 10, angle)
        on._pan = QPointF(on._pan.x() + dx, on._pan.y() + dy)
        on._repaint_label()
        moved = on._coord_mm_at(QPointF(focus.x() + 30, focus.y() + 10))
        assert moved == pytest.approx(mm, abs=0.3)
    finally:
        off.deleteLater()
        on.deleteLater()


# ---- the tabs, the files and Preferences --------------------------------------

def _hashes(r):
    paths = list(r.tiff_paths) + [r.ti2_path, r.ti2_path.with_suffix(".fd9.json")]
    pdf = r.ti2_path.with_suffix(".pdf")
    if pdf.exists():
        paths.append(pdf)
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}


@pytest.fixture
def chart_tab(qapp, qtbot, tmp_path, monkeypatch):
    monkeypatch.setenv("CHROMIQ_PRESETS_DIR", str(tmp_path / "presets"))
    from core.argyll_runner import ArgyllRunner
    from core.file_manager import FileManager
    from core.settings import AppSettings
    from ui.tabs.tab_chart import TabChart
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    s.set("custom_output_path", str(tmp_path / "projects"))
    t = TabChart(ArgyllRunner(s), FileManager(s), s)
    qtbot.addWidget(t)
    return t


def test_create_chart_turns_an_fd9_chart_and_no_other(chart_tab, chart,
                                                      tmp_path):
    r, _p, _ = chart
    before = _hashes(r)
    chart_tab._settings.set("fd9_display_rotation", 180)
    chart_tab._preview.load_tiff(r.tiff_paths)
    assert chart_tab._preview.view_rotation() == 180
    other = tmp_path / "plain_01.tif"
    other.write_bytes(r.tiff_paths[0].read_bytes())
    chart_tab._preview.load_tiff([other])
    assert chart_tab._preview.view_rotation() == 0
    chart_tab._settings.set("fd9_display_rotation", 90)
    chart_tab._preview.load_tiff(r.tiff_paths)
    chart_tab._preview._update_display()
    assert chart_tab._preview.view_rotation() == 90
    chart_tab._settings.set("fd9_display_rotation", 0)
    chart_tab.refresh_view_rotation()
    assert chart_tab._preview.view_rotation() == 0
    assert _hashes(r) == before            # the chart files never change


def test_with_fd9_support_off_the_tabs_have_no_rule(qapp, qtbot, tmp_path,
                                                    monkeypatch):
    support.set_enabled_for_this_process(False)
    monkeypatch.setenv("CHROMIQ_PRESETS_DIR", str(tmp_path / "presets"))
    from core.argyll_runner import ArgyllRunner
    from core.file_manager import FileManager
    from core.settings import AppSettings
    from ui.tabs.tab_chart import TabChart
    from ui.tabs.tab_measure import TabMeasure
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    s.set("custom_output_path", str(tmp_path / "projects"))
    s.set("fd9_display_rotation", 180)
    c = TabChart(ArgyllRunner(s), FileManager(s), s)
    m = TabMeasure(ArgyllRunner(s), s)
    try:
        assert c._preview._rotation_rule is None
        assert m._preview._rotation_rule is None
    finally:
        c.deleteLater()
        m.deleteLater()


def test_the_print_tab_shows_the_chart_as_printed(qapp, qtbot, tmp_path):
    """The Print tab's preview is what goes to the printer, so it is never
    turned (it has no rule)."""
    from core.argyll_runner import ArgyllRunner
    from core.settings import AppSettings
    from ui.tabs.tab_print import TabPrint
    import inspect
    assert "set_rotation_rule" not in inspect.getsource(TabPrint)


@pytest.fixture
def measure_tab(qapp, tmp_path):
    from core.argyll_runner import ArgyllRunner
    from core.settings import AppSettings
    from ui.tabs.tab_measure import TabMeasure
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "app.ini"), QSettings.Format.IniFormat)
    s.set("custom_output_path", str(tmp_path / "out"))
    t = TabMeasure(ArgyllRunner(s), s)
    yield t
    t.close()
    t.deleteLater()


@pytest.mark.parametrize("angle", ANGLES)
def test_the_measure_tabs_fd9_preview_turns_and_its_colours_stay_on_their_patch(
        measure_tab, chart, angle, qapp):
    r, pages, locations = chart
    before = _hashes(r)
    tab = measure_tab
    tab._settings.set("fd9_display_rotation", angle)
    tab.set_ti1_path(r.ti2_path.with_suffix(".ti1"))
    assert tab._fd9_load_preview(r.ti2_path)
    assert tab._preview.view_rotation() == angle
    tab._preview.resize(700, 800)
    tab._preview.show()
    _settle(qapp, tab._preview)
    # A live colour for one patch, through the tab's own path.
    loc = next(iter(tab._patch_boxes[0]))
    box = tab._patch_boxes[0][loc]
    tab._preview.set_patch_overlay(
        0, [(box, QColor(255, 0, 255), QColor(255, 0, 255), False)],
        replace_page=True)
    tab._preview.set_overlay_mode("expected")
    _settle(qapp, tab._preview)
    pv = tab._preview
    img = _shown(pv)
    found = [(x, y) for y in range(0, img.height(), 2)
             for x in range(0, img.width(), 2)
             if img.pixelColor(x, y) == QColor(255, 0, 255)]
    assert found
    x = sum(p[0] for p in found) / len(found)
    y = sum(p[1] for p in found) / len(found)
    px = pv._image_px_at(_label_point(pv, (x, y)))
    assert px is not None and box.adjusted(-2, -2, 2, 2).contains(px[0], px[1])
    assert _hashes(r) == before
    tab._settings.set("fd9_display_rotation", 0)
    tab.refresh_view_rotation()
    assert pv.view_rotation() == 0


def test_the_measure_tab_turns_nothing_for_another_chart(measure_tab, tmp_path):
    from tests.test_fd9_beta_option import _plain_chart
    tab = measure_tab
    tab._settings.set("fd9_display_rotation", 180)
    plain = _plain_chart(tmp_path)
    tab.set_ti1_path(plain.with_suffix(".ti1"))
    assert tab._preview.view_rotation() == 0


def test_preferences_row_is_under_fd9_support_and_greyed_while_it_is_off(qapp,
                                                                        tmp_path):
    from core.settings import AppSettings
    from ui.dialogs.settings_dialog import SettingsDialog, fd9_rotation_help
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "p.ini"), QSettings.Format.IniFormat)
    s.set("fd9_support_beta", False)
    s.set("fd9_display_rotation", 180)
    dlg = SettingsDialog(s, None)
    try:
        combo = dlg._fd9_rotation_combo
        assert [combo.itemData(i) for i in range(combo.count())] == [0, 90, 180, 270]
        assert combo.itemText(0) == "Off"
        assert combo.currentData() == 180
        assert not combo.isEnabled() and not dlg._fd9_rotation_label.isEnabled()
        dlg._fd9_support_check.setChecked(True)
        assert combo.isEnabled()
        combo.setCurrentIndex(combo.findData(90))
        dlg._save_and_close()
        assert s.get("fd9_display_rotation") == 90
    finally:
        dlg.deleteLater()
    text = fd9_rotation_help()
    for must in ("TIFF", ".fd9.json", "printed", "90°", "180°", "270°",
                 "Measured from Preview", "**Default:** off"):
        assert must in text
    assert "—" not in text
    # 4.3.26 (lessbones): the page number and the clip border are printed
    # upright, readable with the arrow up. The help said they were "printed
    # turned round" and that 180° made them read the right way up; neither
    # is true any more.
    assert "printed turned round" not in text
    assert "reads the right way up with the arrow pointing up" in text
    assert "upside down on screen" in text.split("180°", 1)[1].split("270°")[0]


def test_measured_from_preview_and_the_guides_describe_the_paper_at_every_angle(
        chart_tab, chart):
    """Left / Right / Top / Bottom in "Measured from Preview", and the guide
    lines handed to the preview (as fractions of the PAPER), are the Off
    values at every angle."""
    r, _p, _ = chart
    seen = []
    for angle in ANGLES:
        chart_tab._settings.set("fd9_display_rotation", angle)
        chart_tab._preview.load_tiff(r.tiff_paths)
        chart_tab._preview._update_display()
        chart_tab._set_margin_chart(r.tiff_paths, r.ti2_path)
        rep = chart_tab._margin_report
        assert chart_tab._preview.view_rotation() == angle
        seen.append((None if rep is None else
                     (rep.left_mm, rep.right_mm, rep.top_mm, rep.bottom_mm),
                     list(chart_tab._preview._margin_guides),
                     list(chart_tab._preview._measured_guides)))
    assert seen[0][0] is not None
    assert all(s == seen[0] for s in seen)


@pytest.mark.parametrize("angle", ANGLES)
@pytest.mark.parametrize("interactive", [False, True], ids=["fit", "zoom"])
def test_the_first_paint_after_a_resize_is_already_right(
        qapp, chart, angle, interactive):
    """Review r1, R1: the zoom path recorded the turned frame AFTER drawing
    the overlays, so the first paint after a resize placed the legend chip
    (and the hover-to-hide test) by the previous size. The first paint after
    a resize must equal the second."""
    r, pages, _ = chart
    boxes = list(_boxes(pages[0]).values())
    pv = _preview(qapp, 640, 520, angle, r.tiff_paths)
    try:
        pv.set_legend_enabled(True)
        if interactive:
            pv.set_interactive(True)
        _settle(qapp, pv)
        pv.set_patch_overlay(0, [(b, QColor(255, 0, 0), QColor(0, 0, 255), False)
                                 for b in boxes], replace_page=True)
        pv.set_overlay_mode("both")
        _settle(qapp, pv)
        if interactive:
            pv._apply_zoom(1.5, QPoint(300, 260))
        # No event loop in between: the paint right after the label's new
        # size is the one under test (an event would repaint first).
        pv._img_label.setFixedSize(560, 700)
        assert pv._img_label.size().width() == 560

        def paint():
            pv._repaint_label()
            return (pv._legend_paint, pv._legend_label_off, pv._rot_frame,
                    QRect(pv._legend_rect), _shown(pv))
        first = paint()
        second = paint()
        assert first[:4] == second[:4]
        assert first[4] == second[4]
        if angle == 0:
            assert first[1] is None and first[2] is None
    finally:
        pv.deleteLater()
