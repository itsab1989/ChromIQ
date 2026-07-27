"""UI-side tests for the chart-reading engine (#126): preview click-to-jump,
session-map handling, split-patch overlay plumbing, guided goto."""
from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtCore import QPoint, QRect, Qt  # noqa: E402
from PyQt6.QtGui import QColor, QPixmap  # noqa: E402
from PyQt6.QtTest import QTest  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402


@pytest.fixture(scope="module", autouse=True)
def _qapp():
    yield QApplication.instance() or QApplication([])


class _Settings:
    def __init__(self, extra=None):
        self._d = {"appearance": "dark"}
        self._d.update(extra or {})

    def get(self, key, default=None):
        return self._d.get(key, default)

    def set(self, key, value):
        self._d[key] = value


# ---------------------------------------------------------------------------
# TiffPreview: click-to-jump hit testing through the real paint geometry
# ---------------------------------------------------------------------------

def _make_preview(qapp=None):
    from ui.tiff_preview import TiffPreview
    pv = TiffPreview()
    pv.resize(400, 500)
    pm = QPixmap(200, 250)
    pm.fill(QColor("white"))
    pv._pixmap = pm
    pv._pages = [(Path("/nonexistent.tif"), 0)]
    pv._repaint_label()          # establishes _paint_geom
    return pv


def test_preview_click_emits_stripe_for_hit_and_nothing_for_miss():
    pv = _make_preview()
    rects = [QRect(10, 10, 180, 40), QRect(10, 60, 180, 40)]
    pv.set_stripe_rects(rects)
    pv.set_stripe_click_enabled(True, {0: True, 1: False})
    hits: list[tuple[int, int]] = []
    pv.stripe_clicked.connect(lambda pg, i: hits.append((pg, i)))

    s, ox, oy = pv._paint_geom
    # centre of stripe 1 in image px → widget coords
    cx = int(ox + (10 + 90) * s)
    cy = int(oy + (60 + 20) * s)
    pos_in_label = QPoint(cx, cy)
    pos = pv._img_label.mapTo(pv, pos_in_label)
    QTest.mouseClick(pv, Qt.MouseButton.LeftButton, pos=pos)
    assert hits == [(0, 1)]

    # a click well outside any stripe emits nothing
    QTest.mouseClick(pv, Qt.MouseButton.LeftButton, pos=QPoint(2, 2))
    assert hits == [(0, 1)]

    # disabled → no emission even on a hit
    pv.set_stripe_click_enabled(False)
    QTest.mouseClick(pv, Qt.MouseButton.LeftButton, pos=pos)
    assert hits == [(0, 1)]


def test_coord_readout_maps_pointer_to_paper_mm():
    """#29: the pointer coordinate readout converts a label position to paper
    millimetres from the sheet's top-left corner (image px 0,0), via the paint
    transform and the render dpi."""
    pv = _make_preview()
    pv.set_coord_readout(True, dpi=200.0)          # 200 px per inch
    s, ox, oy = pv._paint_geom
    # A label position corresponding to image pixel (100, 50).
    lbl = QPoint(int(ox + 100 * s), int(oy + 50 * s))
    x_mm, y_mm = pv._coord_mm_at(lbl)
    assert abs(x_mm - 100 * 25.4 / 200) < 0.1      # = 12.7 mm
    assert abs(y_mm - 50 * 25.4 / 200) < 0.1       # = 6.35 mm
    # Off-sheet to the left → negative X (the ruler still reads there).
    left = QPoint(int(ox - 40 * s), int(oy + 10 * s))
    assert pv._coord_mm_at(left)[0] < 0
    # Turning it off clears the tracked position.
    pv.set_coord_readout(False)
    assert pv._coord_pos is None
    assert pv._coord_readout is False


def test_coord_readout_uses_label_space_overlay():
    """#29 fix: the cross-hair is drawn by a dedicated overlay covering the image
    label (not baked into the centred canvas), so it lands at the pointer with no
    offset. The overlay shares the label's coordinates — the tracked position is
    exactly what it draws."""
    from PyQt6.QtGui import QMouseEvent
    from PyQt6.QtCore import QEvent, QPointF
    pv = _make_preview()
    pv.set_coord_readout(True, dpi=200.0)
    assert pv._cursor_overlay is not None and not pv._cursor_overlay.isHidden()
    # The overlay covers the whole image label (so its coords == label coords).
    assert pv._cursor_overlay.size() == pv._img_label.size()

    s, ox, oy = pv._paint_geom
    self_pt = pv._img_label.mapTo(pv, QPoint(int(ox + 60 * s), int(oy + 40 * s)))
    ev = QMouseEvent(QEvent.Type.MouseMove, QPointF(self_pt), QPointF(self_pt),
                     Qt.MouseButton.NoButton, Qt.MouseButton.NoButton,
                     Qt.KeyboardModifier.NoModifier)
    pv.mouseMoveEvent(ev)
    # The overlay draws at exactly the tracked label position — no canvas shift.
    assert pv._cursor_overlay._pos == pv._coord_pos
    assert pv._cursor_overlay._mm is not None
    # Leaving clears it.
    pv.leaveEvent(QEvent(QEvent.Type.Leave))
    assert pv._cursor_overlay._pos is None


def test_patch_overlay_accumulates_new_boxes_but_replaces_re_measured():
    """Measuring different strips accumulates their split patches; re-measuring
    the SAME patch box REPLACES its entry (no duplicates, no stale outline) —
    so a re-measured chart's overlay always reflects the latest reading (Basti)."""
    pv = _make_preview()
    a = [(QRect(10, 10, 20, 20), QColor("red"), QColor("blue"), False)]
    b = [(QRect(40, 10, 20, 20), QColor("red"), QColor("blue"), False)]
    pv.set_patch_overlay(0, a)
    pv.set_patch_overlay(0, b)                       # different box → accumulates
    assert len(pv._patch_overlay[0]) == 2
    # Re-measure box A (now warns) — replaces, doesn't duplicate.
    a2 = [(QRect(10, 10, 20, 20), QColor("green"), QColor("yellow"), True)]
    pv.set_patch_overlay(0, a2)
    assert len(pv._patch_overlay[0]) == 2
    a_entry = next(it for it in pv._patch_overlay[0] if it[0] == QRect(10, 10, 20, 20))
    assert a_entry[3] is True                        # the fresh (warning) result

    assert pv.has_patch_overlay()
    pv.clear_patch_overlay()
    assert not pv.has_patch_overlay()
    # painting with an overlay present must not raise
    pv.set_patch_overlay(0, a)
    pv._repaint_label()


def test_patch_boxes_hex_stagger_tracks_drawn_hexagons(tmp_path):
    """#32 (Knut): the split-patch overlay boxes for a SpectroScan hexagonal
    chart must follow the ±¼-width per-row zigzag the renderer draws, so a split
    lands on its hexagon and not a quarter-patch off. Odd patch numbers shift
    left, even ones right; a non-hex chart is untouched."""
    import json
    from ui.tabs.tab_measure import patch_boxes_from_sidecar
    w = 40
    patches = [                                        # one column, 4 rows
        {"page": 0, "loc": "A1", "x": 100, "y": 10, "w": w, "h": 40},
        {"page": 0, "loc": "A2", "x": 100, "y": 60, "w": w, "h": 40},
        {"page": 0, "loc": "A3", "x": 100, "y": 110, "w": w, "h": 40},
    ]
    (tmp_path / "c.channels.json").write_text(json.dumps(
        {"layout": {"patches": patches,
                    "recipe": {"instrument": "SS", "hflag": True}}}))
    (tmp_path / "c.ti2").write_text("x")
    box = patch_boxes_from_sidecar(tmp_path / "c.ti2", 1)[0]
    assert box["A1"].x() == 100 - round(w / 4)         # row 0 → left
    assert box["A2"].x() == 100 + round(w / 4)         # row 1 → right
    assert box["A3"].x() == 100 - round(w / 4)         # row 2 → left

    # A rectangular SpectroScan chart is NOT staggered.
    (tmp_path / "r.channels.json").write_text(json.dumps(
        {"layout": {"patches": patches,
                    "recipe": {"instrument": "SS", "hflag": False}}}))
    (tmp_path / "r.ti2").write_text("x")
    rbox = patch_boxes_from_sidecar(tmp_path / "r.ti2", 1)[0]
    assert rbox["A1"].x() == 100 and rbox["A2"].x() == 100


def test_hover_bounds_hug_patches_and_include_offset_overhang():
    """The click-to-jump hover outline must wrap only a strip's patches — not
    the label band above them, not the white paper beside them — and on a
    ColorMunki 'offset every second strip' chart it must still include the
    odd strip's last patch, which hangs below the strip rectangle (Basti)."""
    pv = _make_preview()
    # Two columns of 3 patches each (10 px wide, 10 px tall, gap 10).
    # Column X=10: rows at y=100,110,120. Column X=40 is offset DOWN by 50 px:
    # rows at y=150,160,170 — its last patch bottom (180) hangs below column 0.
    boxes = [QRect(10, 100, 10, 10), QRect(10, 110, 10, 10), QRect(10, 120, 10, 10),
             QRect(40, 150, 10, 10), QRect(40, 160, 10, 10), QRect(40, 170, 10, 10)]
    pv.set_page_patch_boxes({0: boxes})
    pv._current = 0

    # Strip rects mimic the production 'grown' rect: top pulled UP to the label
    # band (y=0), and — crucially — the OFFSET column's rect is too SHORT to
    # cover its hanging last patch (bottom 175 < patch bottom 180).
    normal = QRect(10, 0, 10, 130)          # covers column 0 fully
    offset = QRect(40, 0, 10, 175)          # under-covers column 1's overhang

    b0 = pv._hover_patch_bounds(normal)
    assert b0 == QRect(10, 100, 10, 30)     # exactly the 3 patches, no label band
    assert b0.top() == 100 and b0.top() > 0

    b1 = pv._hover_patch_bounds(offset)
    assert b1 == QRect(40, 150, 10, 30)     # includes the hanging last patch (→180)
    assert b1.bottom() >= 179               # would be 174 if the overhang were clipped

    # No geometry known ⇒ None ⇒ caller falls back to the full strip rect.
    pv.set_page_patch_boxes({})
    assert pv._hover_patch_bounds(normal) is None


# ---------------------------------------------------------------------------
# TabMeasure: engine handlers drive combo, read-map and overlay
# ---------------------------------------------------------------------------

def _make_tab(engine="chromiq"):
    from core.argyll_runner import ArgyllRunner
    from ui.tabs.tab_measure import TabMeasure
    s = _Settings({"chartread_engine": engine})
    return TabMeasure(ArgyllRunner(s), s)


def test_session_map_enables_click_jump_and_read_map(monkeypatch):
    tab = _make_tab()
    tab._page_stripe_rects = [[QRect(0, 0, 100, 20), QRect(0, 30, 100, 20)]]
    tab._strips_per_page = [2]
    # manual mode so the engine extras appear
    monkeypatch.setattr(tab, "_current_mode", lambda: "manual")
    tab._on_session_map([
        {"strip": "A", "sheet": 1, "read": True, "verifiable": True},
        {"strip": "B", "sheet": 1, "read": False, "verifiable": True},
    ])
    # No go-to-strip combo any more — clicking a strip is the only jump UI.
    assert not hasattr(tab, "_m_goto_combo")
    assert tab._preview._stripe_click_enabled
    assert tab._preview._stripe_read_map == {0: True, 1: False}


def test_live_preview_group_always_visible_and_stays_enabled_while_reading():
    """The engine view controls (Show mode + Show only measured) live in their
    own always-visible 'Live preview' group, not hidden until a read starts. A
    running measurement locks the parameters and presets, but the view group
    stays enabled (it only changes the preview) and the scroll area is never
    disabled, so the panel stays scrollable (#41/#42, Basti)."""
    tab = _make_tab()
    # The controls are parented into the view group, which is visible with the
    # engine on (before any measurement).
    assert not tab._m_view_grp.isHidden()
    members = [tab._m_view_grp.layout().itemAt(i).widget()
               for i in range(tab._m_view_grp.layout().count())]
    assert tab._m_engine_row in members

    tab._set_settings_enabled(False)                 # measurement starts
    assert not tab._m_options.isEnabled()            # parameters locked
    assert not tab._m_presets_grp.isEnabled()
    assert tab._m_view_grp.isEnabled()               # view controls stay usable
    assert tab._m_overlay_mode.isEnabled()
    assert tab._m_only_measured.isEnabled()

    tab._set_settings_enabled(True)                  # measurement ends
    assert tab._m_options.isEnabled()


def test_live_preview_independent_per_module():
    """#44: Manual and Guided each have their own Live-preview controls. Only the
    ACTIVE module drives the shared preview, and switching module applies that
    module's independent view."""
    tab = _make_tab()
    assert tab._m_view_grp is not None and tab._g_view_grp is not None
    assert tab._m_overlay_mode is not tab._g_overlay_mode

    tab._switch_mode("guided")
    tab._g_overlay_mode.setCurrentIndex(tab._g_overlay_mode.findData("expected"))
    assert tab._preview.overlay_mode() == "expected"
    # Changing the INACTIVE (manual) control must not touch the preview.
    tab._m_overlay_mode.setCurrentIndex(tab._m_overlay_mode.findData("measured"))
    assert tab._preview.overlay_mode() == "expected"
    # Switching to Manual applies Manual's own independent value.
    tab._switch_mode("manual")
    assert tab._preview.overlay_mode() == "measured"


def test_hover_frame_grows_over_edge_spacers():
    """#43: with edge spacers, the strip-hover frame grows by one spacer height
    above the first patch and below the last (they're part of the swiped strip)."""
    from PyQt6.QtCore import QRect
    pv = _make_preview()
    pv.set_page_patch_boxes({0: [QRect(100, 50, 40, 40), QRect(100, 100, 40, 40)]})
    pv._current = 0
    strip = QRect(90, 0, 60, 300)
    base = pv._hover_patch_bounds(strip)
    pv.set_edge_spacer_px(8)
    grown = pv._hover_patch_bounds(strip)
    assert grown.y() == base.y() - 8
    assert grown.height() == base.height() + 16
    # No edge spacers → unchanged.
    pv.set_edge_spacer_px(0)
    assert pv._hover_patch_bounds(strip) == base


def test_edge_spacer_px_reads_geometry(tmp_path):
    """#43: the edge-spacer height comes from the chart's own geometry — nonzero
    only when the recipe says the chart HAS edge spacers."""
    import json
    from ui.tabs.tab_measure import edge_spacer_px_from_sidecar
    (tmp_path / "c.ti2").write_text("x")
    (tmp_path / "c.channels.json").write_text(json.dumps(
        {"layout": {"dpi": 200, "recipe": {"instrument": "i1", "edge_spacers": True}}}))
    assert edge_spacer_px_from_sidecar(tmp_path / "c.ti2") > 0
    (tmp_path / "c.channels.json").write_text(json.dumps(
        {"layout": {"dpi": 200, "recipe": {"instrument": "i1", "edge_spacers": False}}}))
    assert edge_spacer_px_from_sidecar(tmp_path / "c.ti2") == 0
    assert edge_spacer_px_from_sidecar(None) == 0


def test_live_preview_options_saved_in_manual_preset():
    """#41: the view controls are part of the manual preset snapshot, so a
    preset restores the user's preferred workspace look."""
    tab = _make_tab()
    tab._m_overlay_mode.setCurrentIndex(tab._m_overlay_mode.findData("measured"))
    tab._m_only_measured.setChecked(True)
    data = tab._m_collect_preset_data()
    assert data["overlay_mode"] == "measured" and data["only_measured"] is True
    # Apply a different snapshot and confirm the controls follow.
    tab._m_apply_preset_data({"overlay_mode": "expected", "only_measured": False})
    assert tab._m_overlay_mode.currentData() == "expected"
    assert tab._m_only_measured.isChecked() is False


def test_session_map_enables_click_jump_in_guided_too():
    """Click-to-jump works in BOTH modules now (Basti): the engine handles goto
    the same way in guided as in manual, so hovering + clicking a strip is
    enabled for a guided read as well."""
    tab = _make_tab()
    tab._page_stripe_rects = [[QRect(0, 0, 100, 20), QRect(0, 30, 100, 20)]]
    tab._strips_per_page = [2]
    tab._switch_mode("guided")
    tab._on_session_map([
        {"strip": "A", "sheet": 1, "read": True},
        {"strip": "B", "sheet": 1, "read": False},
    ])
    assert tab._preview._stripe_click_enabled
    assert tab._preview._stripe_read_map == {0: True, 1: False}


def test_strip_measured_splits_only_real_patch_boxes(monkeypatch):
    """The overlay must land on each patch's OWN box (looked up by loc), and
    draw nothing when the chart exposes no per-patch geometry."""
    tab = _make_tab()
    tab._page_stripe_rects = [[QRect(0, 0, 210, 20), QRect(0, 30, 210, 20)]]
    tab._strips_per_page = [2]
    tab._engine_strips = [{"strip": "A"}, {"strip": "B"}]
    ev = {
        "strip": "B", "worst_de": 2.0, "reversed": False, "verifiable": True,
        "patches": [
            {"id": str(i), "loc": f"B{i}", "xyz": [50, 50, 50],
             "exyz": [50, 50, 50], "de": 0.1}
            for i in range(1, 8)
        ],
    }
    # No geometry → overlay suppressed (never a misaligned block).
    tab._patch_boxes = [dict()]
    tab._on_strip_measured(ev)
    assert tab._preview._patch_overlay.get(0) is None
    assert tab._engine_read["B"] is True

    # With real per-patch boxes → each split lands on its own box.
    boxes = {f"B{i}": QRect(5 * i, 30, 4, 18) for i in range(1, 8)}
    tab._patch_boxes = [boxes]
    tab._on_strip_measured(ev)
    items = tab._preview._patch_overlay.get(0)
    assert items and len(items) == 7
    assert items[0][0] == QRect(5, 30, 4, 18)      # B1's exact box
    assert items[3][0] == QRect(20, 30, 4, 18)     # B4's exact box


def test_show_only_measured_blanks_unread(monkeypatch):
    """set_show_only_measured toggles the flag and repaints without error; the
    Measure-tab checkbox drives it (Knut)."""
    pv = _make_preview()
    pv.set_page_patch_boxes({0: [QRect(10, 10, 20, 20), QRect(40, 10, 20, 20)]})
    assert pv._show_only_measured is False
    pv.set_show_only_measured(True)
    assert pv._show_only_measured is True
    pv._repaint_label()                    # white-out path paints without raising
    pv.set_show_only_measured(False)
    assert pv._show_only_measured is False

    tab = _make_tab()
    monkeypatch.setattr(tab, "_current_mode", lambda: "manual")
    tab._on_session_map([{"strip": "A", "sheet": 1, "read": False}])
    tab._m_only_measured.setChecked(True)
    assert tab._preview._show_only_measured is True


# ---------------------------------------------------------------------------
# "Show patch values on hover" info tile
# ---------------------------------------------------------------------------

def test_patch_info_tile_builds_rows_per_mode():
    """The tile shows expected + measured + ΔE in the split view, and only the
    matching colour (no ΔE) in the single-colour views."""
    from ui.tiff_preview import _PatchInfoTile
    tile = _PatchInfoTile(None)
    info = {"loc": "B4", "exp_rgb": (200, 10, 20), "meas_rgb": (190, 20, 30),
            "exp_lab": (50.0, 60.0, 40.0), "meas_lab": (51.0, 55.0, 38.0),
            "de": 2.34}

    tile.set_content(info, "both")
    texts = " | ".join(t for _s, t in tile._rows)
    # header + 3 exp + 3 meas + ΔE + the line naming which ΔE it is (Knut, #131
    # 2026-07-27: "please show what the value means, which standard it is
    # calculated with").
    assert len(tile._rows) == 9
    assert "B4" in texts and "2.34" in texts
    assert "CIE76" in texts and "D50" in texts
    assert tile.width() > 0 and tile.height() > 0

    tile.set_content(info, "expected")
    texts = " | ".join(t for _s, t in tile._rows)
    assert len(tile._rows) == 4            # header + 3 (expected only)
    assert "2.34" not in texts             # ΔE needs both colours on screen

    tile.set_content(info, "measured")
    assert len(tile._rows) == 4


def test_patch_info_accumulates_and_replaces_like_overlay():
    """set_patch_info follows the same accumulate/replace-by-box rule as the
    overlay, so the tile numbers stay in lockstep with the split it explains."""
    pv = _make_preview()
    pv.set_patch_info(0, [(QRect(0, 0, 4, 4), {"loc": "A1", "de": 1})])
    pv.set_patch_info(0, [(QRect(10, 0, 4, 4), {"loc": "A2", "de": 2})])
    assert len(pv._patch_info[0]) == 2                     # different box → adds
    pv.set_patch_info(0, [(QRect(0, 0, 4, 4), {"loc": "A1", "de": 9})])
    assert len(pv._patch_info[0]) == 2                     # same box → replaced
    by_loc = {info["loc"]: info for _r, info in pv._patch_info[0]}
    assert by_loc["A1"]["de"] == 9


def test_hover_tile_shows_over_measured_patch_only_when_enabled():
    pv = _make_preview()
    pv._current = 0
    box = QRect(50, 50, 30, 30)
    info = {"loc": "A1", "exp_rgb": (10, 20, 30), "meas_rgb": (12, 22, 32),
            "exp_lab": (30.0, 1.0, -2.0), "meas_lab": (31.0, 0.5, -1.5),
            "de": 1.1}
    pv.set_patch_info(0, [(box, info)])

    s, ox, oy = pv._paint_geom
    lx = int(ox + (box.x() + box.width() / 2) * s)
    ly = int(oy + (box.y() + box.height() / 2) * s)
    on_patch = pv._img_label.mapTo(pv, QPoint(lx, ly))

    # Option OFF: no tile even while pointing right at the patch.
    pv._update_patch_tile(on_patch)
    assert pv._patch_tile is None or pv._patch_tile.isHidden()

    # Option ON: the tile appears over the patch…
    pv.set_show_patch_tile(True)
    pv._update_patch_tile(on_patch)
    assert pv._patch_tile is not None and not pv._patch_tile.isHidden()

    # …and hides again when the pointer leaves the patch.
    off_patch = pv._img_label.mapTo(pv, QPoint(2, 2))
    pv._update_patch_tile(off_patch)
    assert pv._patch_tile.isHidden()

    # Turning the option off hides any visible tile at once.
    pv._update_patch_tile(on_patch)
    assert not pv._patch_tile.isHidden()
    pv.set_show_patch_tile(False)
    assert pv._patch_tile.isHidden()


def test_strip_measured_feeds_tile_numbers(monkeypatch):
    """_on_strip_measured hands the preview per-patch numbers (loc, RGB, L*a*b*,
    ΔE) for the hover tile, keyed to each patch's own box."""
    tab = _make_tab()
    tab._page_stripe_rects = [[QRect(0, 0, 210, 20), QRect(0, 30, 210, 20)]]
    tab._strips_per_page = [2]
    tab._engine_strips = [{"strip": "A"}, {"strip": "B"}]
    tab._patch_boxes = [{f"B{i}": QRect(5 * i, 30, 4, 18) for i in range(1, 4)}]
    ev = {"strip": "B", "worst_de": 2.0, "reversed": False, "verifiable": True,
          "patches": [{"id": str(i), "loc": f"B{i}", "xyz": [40, 42, 44],
                       "exyz": [50, 50, 50], "de": 1.5 + i}
                      for i in range(1, 4)]}
    tab._on_strip_measured(ev)
    info = tab._preview._patch_info.get(0)
    assert info and len(info) == 3
    first = info[0][1]
    assert first["loc"] == "B1"
    assert set(first) >= {"loc", "exp_rgb", "meas_rgb", "exp_lab", "meas_lab", "de"}
    assert len(first["exp_lab"]) == 3 and len(first["meas_rgb"]) == 3


def test_patch_tile_option_wires_and_persists(monkeypatch):
    tab = _make_tab()
    monkeypatch.setattr(tab, "_current_mode", lambda: "manual")
    tab._m_patch_tile.setChecked(True)
    assert tab._preview._show_patch_tile is True

    # Part of the manual preset snapshot.
    assert tab._m_collect_preset_data()["patch_tile"] is True
    tab._m_apply_preset_data({"patch_tile": False})
    assert tab._m_patch_tile.isChecked() is False

    # Saved as a manual default and restored.
    tab._m_patch_tile.setChecked(True)
    tab._on_save_defaults()
    tab._m_patch_tile.setChecked(False)
    tab._restore_defaults()
    assert tab._m_patch_tile.isChecked() is True

    # Guided has its own independent flag, saved + restored too.
    monkeypatch.setattr(tab, "_current_mode", lambda: "guided")
    tab._g_patch_tile.setChecked(True)
    assert tab._preview._show_patch_tile is True
    tab._on_save_defaults()
    tab._g_patch_tile.setChecked(False)
    tab._restore_defaults()
    assert tab._g_patch_tile.isChecked() is True


def test_file_tooltip_suppressed_over_image_during_measurement():
    """The chart path/name tooltip must not pop up over the chart while a read
    runs (it gets in the way of swiping + the hover tile); it stays on the
    header text and returns to the image once the measurement ends."""
    pv = _make_preview()
    pv._update_filename_label([Path("/tmp/proj/runs/run1/chart_01.tif")])
    assert "Folder:" in pv._img_label.toolTip()

    pv.set_suppress_file_tooltip(True)
    assert pv._img_label.toolTip() == ""                 # gone from the chart
    assert "Folder:" in pv._filename_lbl.toolTip()       # still on the header

    pv.set_suppress_file_tooltip(False)
    assert "Folder:" in pv._img_label.toolTip()          # back after the read


def test_measure_read_toggles_file_tooltip_suppression():
    """Starting a read suppresses the image tooltip; ending it restores it."""
    tab = _make_tab()
    tab._set_settings_enabled(False)                     # read starts
    assert tab._preview._suppress_file_tooltip is True
    tab._set_settings_enabled(True)                      # read ends
    assert tab._preview._suppress_file_tooltip is False


def test_patch_warn_threshold_comes_from_settings():
    """The ΔE at which a patch gets the red warn outline is the user-set
    'patch_read_warn_de' limit, not a hard-coded constant (Knut)."""
    tab = _make_tab()
    tab._page_stripe_rects = [[QRect(0, 0, 210, 20)]]
    tab._strips_per_page = [1]
    tab._engine_strips = [{"strip": "A"}]
    tab._patch_boxes = [{"A1": QRect(0, 0, 4, 18), "A2": QRect(6, 0, 4, 18)}]
    ev = {"strip": "A", "patches": [
        {"id": "1", "loc": "A1", "xyz": [50, 50, 50], "exyz": [50, 50, 50], "de": 12.0},
        {"id": "2", "loc": "A2", "xyz": [50, 50, 50], "exyz": [50, 50, 50], "de": 3.0}]}

    tab._settings.set("patch_read_warn_de", 10.0)      # de 12 warns, 3 doesn't
    tab._on_strip_measured(ev)
    items = tab._preview._patch_overlay.get(0)
    assert items[0][3] is True and items[1][3] is False

    tab._preview.clear_patch_overlay()
    tab._settings.set("patch_read_warn_de", 25.0)      # now neither warns
    tab._on_strip_measured(ev)
    items = tab._preview._patch_overlay.get(0)
    assert items[0][3] is False and items[1][3] is False


def test_preview_click_maps_page_index_to_letter_and_sends_goto(monkeypatch):
    tab = _make_tab()
    tab._strips_per_page = [2, 2]
    sent: list[str] = []
    monkeypatch.setattr(tab._manager, "goto_strip", lambda s: sent.append(s))
    monkeypatch.setattr(type(tab._manager), "engine_active",
                        property(lambda self: True))
    tab._on_preview_strip_clicked(1, 1)     # page 2, second strip → "D"
    assert sent == ["D"]


def test_engine_params_attach_and_fallbacks(monkeypatch, tmp_path):
    from workflow.measure_manager import MeasureParams
    from workflow import chartread_engine

    tab = _make_tab()
    tab._ti1_path = tmp_path / "c.ti2"

    p = MeasureParams(ti1_path=tab._ti1_path)
    helper = chartread_engine.helper_path()  # dev build exists in this repo
    out = tab._apply_engine_params(p)
    assert out.engine_helper == helper

    # patch-by-patch now runs through the engine too (spot mode is wired)
    p2 = MeasureParams(ti1_path=tab._ti1_path, patch_by_patch=True)
    assert tab._apply_engine_params(p2).engine_helper == helper

    # setting off → untouched
    tab2 = _make_tab(engine="argyll")
    tab2._ti1_path = tab._ti1_path
    p3 = MeasureParams(ti1_path=tab._ti1_path)
    assert tab2._apply_engine_params(p3).engine_helper is None


def test_guided_navigation_uses_goto_when_engine_active():
    """The guided module must jump directly instead of stepping f/b."""
    from workflow.measure_manager import MeasureManager

    class _StubRunner:
        def __init__(self):
            self.writes = []

        def write_stdin(self, text):
            self.writes.append(text)

    r = _StubRunner()
    mgr = MeasureManager(r)
    mgr._engine_active = True
    mgr._navigate_toward("A", "K")
    assert r.writes and '"cmd": "goto"' in r.writes[0] and '"K"' in r.writes[0]

    mgr._engine_active = False
    mgr._navigate_toward("A", "K")
    assert r.writes[-1] == "f"              # stock path unchanged


def test_engine_line_decoder_feeds_existing_signals():
    """strip_ready/error events must drive the same signals the regex path
    drives, so every dialog keeps working."""
    from workflow.measure_manager import MeasureManager

    class _StubRunner:
        def write_stdin(self, text):
            pass

    mgr = MeasureManager(_StubRunner())
    mgr._guided_state = "disabled"      # same as the parser-test harness
    got: dict[str, list] = {}
    for name in ("stripe_changed", "all_stripes_done", "strip_error",
                 "wrong_strip", "unexpected_response", "strip_measured",
                 "readings_saved", "session_map", "unread_confirm"):
        got[name] = []
        getattr(mgr, name).connect(
            lambda *a, _n=name: got[_n].append(a))

    lines = [
        '{"event":"session_start","strips":[{"strip":"A","read":false}]}',
        '{"event":"strip_ready","strip":"A","read":false,"all_done":false}',
        '{"event":"strip_read","strip":"A","worst_de":1.0,"patches":[]}',
        '{"event":"saved","path":"x.ti3","read_patches":21}',
        '{"event":"strip_warning","kind":"wrong_strip","read":"B","expected":"A"}',
        '{"event":"strip_warning","kind":"unexpected_response","worst_de":97.5}',
        '{"event":"error","kind":"coms"}',
        '{"event":"unread_confirm","id":"7","loc":"A7"}',
        '{"event":"strip_ready","strip":"B","read":true,"all_done":true}',
        "plain console prose is passed through",
    ]
    prose: list[str] = []
    for ln in lines:
        mgr._handle_engine_line(ln, prose.append)

    assert [a[0] for a in got["stripe_changed"]] == ["A", "B"]
    assert len(got["all_stripes_done"]) == 1
    assert got["strip_error"] == [("communication problem",)]
    assert got["wrong_strip"] == [("B", "A")]
    assert got["unexpected_response"] == [("97.50",)]
    assert len(got["strip_measured"]) == 1
    assert got["readings_saved"] == [("x.ti3", 21)]
    assert got["unread_confirm"] == [("7, A7",)]
    assert "plain console prose is passed through" in prose


# ---------------------------------------------------------------------------
# Engine spot (patch-by-patch) mode wiring (#126 follow-up)
# ---------------------------------------------------------------------------

def _spot_tab(monkeypatch):
    """A manual-mode tab with a 2-page patch geometry and a live preview."""
    tab = _make_tab()
    monkeypatch.setattr(tab, "_current_mode", lambda: "manual")
    tab._patch_boxes = [
        {"A1": QRect(10, 10, 20, 20), "A2": QRect(10, 40, 20, 20)},
        {"B1": QRect(10, 10, 20, 20)},
    ]
    # Give the preview a pixmap so highlight/paint paths are exercised.
    pm = QPixmap(200, 250)
    pm.fill(QColor("white"))
    tab._preview._pixmap = pm
    tab._preview._pages = [(Path("/nonexistent.tif"), 0),
                           (Path("/nonexistent.tif"), 1)]
    tab._preview._repaint_label()
    return tab


def test_locate_patch_finds_page_and_box(monkeypatch):
    tab = _spot_tab(monkeypatch)
    assert tab._locate_patch("A2") == (0, QRect(10, 40, 20, 20))
    assert tab._locate_patch("B1") == (1, QRect(10, 10, 20, 20))
    assert tab._locate_patch("ZZ9") == (-1, None)


def test_patch_ready_highlights_and_arms_click(monkeypatch):
    tab = _spot_tab(monkeypatch)
    tab._on_patch_ready({"id": "1", "loc": "A1", "read": False,
                         "all_done": False, "exyz": [50, 50, 50]})
    # Click-to-jump armed with the whole chart geometry; the current patch is
    # highlighted on its page.
    assert tab._spot_click_on
    assert tab._preview._patch_click_enabled
    assert tab._preview._active_patch_box == QRect(10, 10, 20, 20)
    assert tab._preview._active_patch_page == 0


def test_patch_ready_flips_to_the_patchs_page(monkeypatch):
    tab = _spot_tab(monkeypatch)
    tab._on_patch_ready({"loc": "A1", "exyz": [50, 50, 50]})
    tab._on_patch_ready({"loc": "B1", "exyz": [50, 50, 50]})   # on page 1
    assert tab._preview.current_page() == 1
    assert tab._preview._active_patch_page == 1


def test_patch_measured_feeds_split_and_tile(monkeypatch):
    tab = _spot_tab(monkeypatch)
    tab._on_patch_measured({
        "loc": "A2",
        "xyz": [40.0, 42.0, 38.0],
        "exyz": [41.0, 42.0, 39.0],
        "de": 1.4,
    })
    ov = tab._preview._patch_overlay.get(0, [])
    info = tab._preview._patch_info.get(0, [])
    assert len(ov) == 1 and ov[0][0] == QRect(10, 40, 20, 20)
    assert len(info) == 1
    rect, d = info[0]
    assert rect == QRect(10, 40, 20, 20)
    assert d["loc"] == "A2"
    assert d["de"] == 1.4
    assert len(d["exp_lab"]) == 3 and len(d["meas_lab"]) == 3


def test_patch_measured_accumulates_per_patch(monkeypatch):
    tab = _spot_tab(monkeypatch)
    tab._on_patch_measured({"loc": "A1", "xyz": [50, 50, 50],
                            "exyz": [50, 50, 50], "de": 0.0})
    tab._on_patch_measured({"loc": "A2", "xyz": [40, 40, 40],
                            "exyz": [40, 40, 40], "de": 0.0})
    assert len(tab._preview._patch_overlay.get(0, [])) == 2


def test_patch_click_jumps_via_goto_patch(monkeypatch):
    tab = _spot_tab(monkeypatch)
    calls = []
    monkeypatch.setattr(tab._manager, "goto_patch", lambda loc: calls.append(loc))
    monkeypatch.setattr(type(tab._manager), "engine_active",
                        property(lambda self: True))
    tab._on_preview_patch_clicked(0, "A2")
    assert calls == ["A2"]


def test_measure_done_clears_spot_state(monkeypatch):
    tab = _spot_tab(monkeypatch)
    tab._on_patch_ready({"loc": "A1", "exyz": [50, 50, 50]})
    assert tab._preview._patch_click_enabled
    tab._on_measure_done(0)
    assert not tab._preview._patch_click_enabled
    assert tab._preview._active_patch_box is None
    assert not tab._spot_click_on


def test_session_map_in_spot_mode_keeps_strip_ui_off(monkeypatch):
    """session_start fires in spot mode too, but the strip click/highlight UI
    must stay OFF — otherwise it frames whole strips and swallows patch clicks
    (strip-click is tested before patch-click in the preview)."""
    tab = _spot_tab(monkeypatch)
    tab._spot_session = True
    tab._page_stripe_rects = [[QRect(0, 0, 100, 20)]]
    tab._strips_per_page = [1]
    tab._on_session_map([{"strip": "A", "sheet": 1, "read": False,
                          "verifiable": True}])
    assert not tab._preview._stripe_click_enabled


def test_chart_measured_fills_all_pages(monkeypatch):
    """XY/chart mode reads many patches at once; _on_chart_measured must fill the
    split/tile for every read patch, across pages."""
    tab = _spot_tab(monkeypatch)          # _patch_boxes: A1,A2 on p0; B1 on p1
    tab._on_chart_measured({"patches": [
        {"loc": "A1", "xyz": [50, 50, 50], "exyz": [50, 50, 50], "de": 0.0},
        {"loc": "B1", "xyz": [40, 40, 40], "exyz": [41, 41, 41], "de": 1.0},
    ]})
    assert len(tab._preview._patch_overlay.get(0, [])) == 1     # A1
    assert len(tab._preview._patch_overlay.get(1, [])) == 1     # B1
    assert len(tab._preview._patch_info.get(0, [])) == 1
