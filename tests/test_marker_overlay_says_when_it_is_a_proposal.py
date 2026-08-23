"""The overlay has to say when it is showing something the sheet has not got.

#164, Knut, 2026-08-23. He raised "Markers per patch" from 3 to 4 and counted
five dashes per patch, unevenly spaced; at 6 he counted seven. The geometry
cannot draw either number — see
``tests/test_helper_marker_edges_and_overlay_honesty.py`` — because the count
was never wrong. The sheet in the preview carries the dashes it was GENERATED
with, and the live overlay drew the current spin-box value over the top, so what
he counted was two combs added together.

The overlay is still right to follow the controls (judging a distance without
rebuilding the chart is the whole point of it). What it has to do as well is
declare itself: while the settings differ from the ones the sheet was built
with, the dashes are a proposal, drawn in the accent colour under a caption,
and never in printed black.
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PyQt6")

from core.resource_path import resource_path  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


@pytest.fixture
def tab_with_marked_chart(qapp, tmp_path):
    """A chart GENERATED with 3 markers per patch, loaded into the tab."""
    from PyQt6.QtCore import QSettings

    from core.argyll_runner import ArgyllRunner
    from core.file_manager import FileManager
    from core.settings import AppSettings
    from ui.tabs.tab_chart import KNUT_PRESETS, TabChart
    from workflow.layout_engine.chart import build_from_recipe
    from workflow.layout_engine.presets import LayoutRecipe

    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    s.set("custom_output_path", str(tmp_path / "out"))
    tab = TabChart(ArgyllRunner(s), FileManager(s), s)
    tab._switch_mode("manual")

    preset = next(p for p in KNUT_PRESETS if p.slug.startswith("cm_a4_204p"))
    rec = LayoutRecipe.from_dict(preset.layout_recipe)
    rec.helper_markers = True
    rec.helper_marker_edge_mm = 2.0
    rec.helper_marker_len_mm = 4.0
    rec.helper_marker_per_patch = 3
    res, _ = build_from_recipe(resource_path(preset.ti1_asset),
                               tmp_path / "chart", rec)
    tab._margin_tiffs = list(res.tiff_paths)
    tab._margin_ti2 = Path(res.ti2_path)
    Path(res.ti2_path).with_suffix(".channels.json").write_text(json.dumps({
        "layout": {"engine": "chromiq", "recipe": rec.to_dict(),
                   "seed": res.seed}}), encoding="utf-8")

    lp = tab._manual_layout_panel
    lp.helper_markers_cb.setChecked(True)
    lp.helper_marker_edge.setValue(2.0)
    lp.helper_marker_len.setValue(4.0)
    lp.helper_marker_per_patch.setValue(3)
    return tab


def test_matching_settings_are_not_a_proposal(tab_with_marked_chart):
    """With the controls on the values the sheet was built with, the overlay
    coincides with the ink and there is nothing to warn about."""
    lines, pending = tab_with_marked_chart._helper_marker_lines_frac()
    assert lines
    assert pending is False


@pytest.mark.parametrize("change", [
    ("helper_marker_per_patch", 4),
    ("helper_marker_per_patch", 6),
    ("helper_marker_edge", 8.0),
    ("helper_marker_len", 9.0),
])
def test_changing_a_setting_makes_the_overlay_a_proposal(tab_with_marked_chart,
                                                         change):
    """Every control that moves a dash has to raise the flag — an edge distance
    the sheet does not have is as misleading as a count it does not have."""
    name, value = change
    lp = tab_with_marked_chart._manual_layout_panel
    getattr(lp, name).setValue(value)
    lines, pending = tab_with_marked_chart._helper_marker_lines_frac()
    assert lines
    assert pending is True, f"changing {name} left the overlay claiming to be ink"


def test_switching_an_edge_off_makes_it_a_proposal(tab_with_marked_chart):
    lp = tab_with_marked_chart._manual_layout_panel
    lp.helper_markers_sides.setChecked(False)
    _lines, pending = tab_with_marked_chart._helper_marker_lines_frac()
    assert pending is True


def test_the_preview_draws_a_proposal_in_a_different_colour(qapp):
    """Not black. A black overlay on black ink is indistinguishable from more
    ink, which is the whole failure."""
    import numpy as np
    from PyQt6.QtGui import QImage, QPainter, QPixmap

    from ui.tiff_preview import TiffPreview

    prev = TiffPreview()
    # DOWN THE LOWER HALF, well clear of the caption. The caption is drawn in
    # the accent colour too, at the top-left, and an earlier version of this
    # test sampled the whole canvas — so it passed against a mutated build that
    # drew every dash in black. Measure the dashes, and only the dashes.
    lines = [(0.02, 0.55 + k / 60.0, 0.06, 0.55 + k / 60.0) for k in range(20)]

    def painted(pending: bool) -> np.ndarray:
        img = QImage(300, 400, QImage.Format.Format_RGB32)
        img.fill(0xFFFFFFFF)
        prev.set_helper_markers(lines, pending=pending)
        p = QPainter(img)
        prev._draw_helper_markers(p, 0.0, 300.0, 400.0)
        p.end()
        buf = img.constBits()
        buf.setsize(img.sizeInBytes())
        # COPY, don't view: a numpy view over a QImage that then goes out of
        # scope reads freed memory, and the two calls quietly compared the same
        # pixels — this test passed against the unfixed code until that was
        # found. (`.astype(int)` on a fresh array is already a copy; the
        # `np.array` is here so the intent survives a refactor.)
        return np.array(np.frombuffer(buf, np.uint8).reshape(
            400, img.bytesPerLine() // 4, 4)[:, :300, :3], dtype=int)

    ink = painted(False)[220:, :]
    proposal = painted(True)[220:, :]
    # Format_RGB32 hands the bytes over as B, G, R — the accent is pink, so red
    # stands clear of green; the printed dash is neutral, where they are equal.
    def pinkness(a):
        b, g, r = a[..., 0], a[..., 1], a[..., 2]
        return int((((r - g) > 40) & (b > g)).sum())

    assert pinkness(ink) == 0, "the matching overlay must be drawn as plain ink"
    assert pinkness(proposal) > 0, "the proposal was drawn in the same black"


def test_the_dashes_land_where_the_printed_ones_are(qapp):
    """Rounded, not truncated.

    `int()` biases EVERY endpoint the same way — down, by up to a whole pixel,
    half of one on average. The gaps survive that (both roundings vary by at
    most a pixel, which was measured, so the earlier claim that truncation made
    the comb visibly uneven does not hold). What does not survive it is
    ALIGNMENT: the overlay is drawn over a sheet whose dashes are already
    printed at those same positions, and a systematically low overlay sits
    beside the ink instead of on it, thickening every dash. Rounding centres the
    error at zero, so the two coincide — which is the property the overlay's
    docstring has always claimed.
    """
    import numpy as np
    from PyQt6.QtGui import QImage, QPainter

    from ui.tiff_preview import TiffPreview

    prev = TiffPreview()
    h = 903.0
    # Positions chosen so the exact pixel row ends in .7 — truncation loses that
    # 0.7 downward on every one of them, rounding gains 0.3 upward.
    exact = [120.7, 240.7, 360.7, 480.7, 600.7]
    lines = [(0.05, y / h, 0.30, y / h) for y in exact]
    prev.set_helper_markers(lines)

    img = QImage(400, int(h), QImage.Format.Format_RGB32)
    img.fill(0xFFFFFFFF)
    p = QPainter(img)
    prev._draw_helper_markers(p, 0.0, 400.0, h)
    p.end()
    buf = img.constBits()
    buf.setsize(img.sizeInBytes())
    arr = np.array(np.frombuffer(buf, np.uint8).reshape(
        int(h), img.bytesPerLine() // 4, 4)[:, :400, :3], dtype=int)

    rows = np.where(arr[:, 20:80].min(axis=2).min(axis=1) < 120)[0]
    runs: list[list[int]] = []
    for y in rows:
        if runs and y - runs[-1][-1] <= 1:
            runs[-1].append(int(y))
        else:
            runs.append([int(y)])
    centres = [sum(r) / len(r) for r in runs]
    assert len(centres) == len(exact), f"drew {len(centres)} dashes, wanted {len(exact)}"
    errors = [c - e for c, e in zip(centres, exact)]
    # Truncation puts every one of these 0.7 px low (plus the pen's own offset,
    # which is the same for both); rounding puts them 0.3 px high. The test is
    # on the SIGNED mean, because that is what a systematic bias looks like.
    assert sum(errors) / len(errors) > -0.5, (
        f"the dashes sit systematically low — truncated, not rounded: {errors}")
