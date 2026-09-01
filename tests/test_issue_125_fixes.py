"""Regression tests for the #125 batch.

Covers: the raster degenerate-rectangle guard (the "y1 must be greater than or
equal to y0" crash on Apply), the i1Profiler export handling a White / light
ink without a KeyError, and the engine-chart sidecar carrying top-level
``ink_channels`` (so the applied multi-ink preview shows its ink inspector row
instead of the floating "Approximate colours" badge that overlapped Next).
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

pytest.importorskip("PIL")
from PIL import Image, ImageDraw  # noqa: E402

pytest.importorskip("PyQt6")
from PyQt6.QtWidgets import QApplication  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


# ---------------------------------------------------------------------------
# Raster: degenerate rectangles must be skipped, not crash the page (#125)
# ---------------------------------------------------------------------------

def test_fill_rect_skips_inverted_boxes():
    from workflow.layout_engine.raster import _fill_rect
    im = Image.new("RGB", (40, 40), (255, 255, 255))
    d = ImageDraw.Draw(im)
    assert _fill_rect(d, [2, 2, 10, 10], (0, 0, 0)) is True
    # y inverted by one pixel (the exact rounding case that raised in Pillow)
    assert _fill_rect(d, [2, 10, 10, 9], (0, 0, 0)) is False
    # x inverted
    assert _fill_rect(d, [10, 2, 9, 10], (0, 0, 0)) is False
    # zero-area line is still valid (y1 == y0)
    assert _fill_rect(d, [2, 5, 10, 5], (0, 0, 0)) is True


def test_dense_multi_ink_chart_builds_without_crash(tmp_path):
    # The #125 scenario shape: a dense multi-ink chart on ColorMunki, clip
    # notes on, at a low (preview) dpi where sub-pixel rounding bites. The
    # guard must let it build rather than raise "y1 must be >= y0".
    from workflow.layout_engine import chart as le_chart
    from workflow.ti2_relayout import color_rep_for_inks, write_ti1_nchannel
    codes = ["c", "m", "y", "k", "o", "r", "g", "b", "v", "w", "lc", "lm", "ly"]
    rep, fields = color_rep_for_inks(codes)
    n = len(fields)
    rows = [(tuple((i * 3 + j) % 40 for j in range(n)), None) for i in range(400)]
    ti1 = write_ti1_nchannel(rep, fields, rows, tmp_path / "c.ti1", ink_limit=300)
    res = le_chart.build_chart(
        str(ti1), tmp_path / "out", instrument="CM", paper="A3", dpi=120,
        pscale=0.88, clip_border_width=12.0, clip_side="left",
        clip_content_mode="notes", project="Test")
    assert res.tiff_paths


# ---------------------------------------------------------------------------
# i1Profiler export: White / light inks must not KeyError (#125)
# ---------------------------------------------------------------------------

def test_extra_ink_resolver_covers_white_and_light_inks():
    from workflow.i1profiler_export import _extra_ink
    for letter in ("W", "y", "k", "2c", "2m", "2y", "2k", "1k"):
        name, lab = _extra_ink(letter)
        assert name and "|" in lab
    # A totally unknown letter still resolves rather than raising.
    assert _extra_ink("?")[0]


def test_pxf_export_handles_white_ink(tmp_path):
    from workflow import i1profiler_export as X
    from workflow.ti2_relayout import color_rep_for_inks, write_ti1_nchannel
    codes = ["c", "m", "y", "k", "o", "w", "ly"]
    rep, fields = color_rep_for_inks(codes)
    n = len(fields)
    rows = [(tuple(10.0 for _ in range(n)), None) for _ in range(4)]
    ti1 = write_ti1_nchannel(rep, fields, rows, tmp_path / "c.ti1", ink_limit=300)
    _txt, pxf = X.export_from_ti1(ti1, tmp_path, base_name="c-i1p", descriptor="c")
    body = pxf.read_text()
    assert "White" in body and "Light Yellow" in body


# ---------------------------------------------------------------------------
# Engine sidecar carries ink_channels so the preview finds the inks (#125)
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# i1Pro A4 / Letter Landscape jig margins (#125)
# ---------------------------------------------------------------------------

def test_landscape_jig_margins_in_seed():
    from core.settings import default_margin_thresholds
    t = default_margin_thresholds()
    for instr, L, T in (("i1Pro", 26, 38), ("i1Pro 3+", 28, 40)):
        for combo in ("A4 Landscape", "Letter Landscape", "A4 Portrait"):
            e = t[f"{instr}|{combo}"]
            # L/R/T are the jig margins; the bottom is 9 mm except on the two
            # i1Pro full-height-strip combos, which use 19 mm (#130).
            assert (e["L"], e["R"], e["T"]) == (L, 9, T)
            want_b = 19 if (instr == "i1Pro" and combo == "A4 Portrait") else 9
            assert e["B"] == want_b


def test_landscape_jig_migration_preserves_customisation():
    from core.settings import upgrade_margin_landscape_jig
    table = {
        "i1Pro|A4 Landscape": {"L": 9, "R": 9, "T": 9, "B": 9, "desc": "x"},
        "i1Pro|Letter Landscape": {"L": 15, "R": 9, "T": 9, "B": 9, "desc": "x"},
    }
    out, changed = upgrade_margin_landscape_jig(table)
    assert changed
    assert out["i1Pro|A4 Landscape"]["L"] == 26        # old default upgraded
    assert out["i1Pro|Letter Landscape"]["L"] == 15    # customisation kept
    # Idempotent: a second pass on the now-jig values changes nothing.
    _out2, changed2 = upgrade_margin_landscape_jig(out)
    assert changed2 is False


def test_i1pro_tall_bottom_migration_preserves_customisation():
    """#130: i1Pro A4 Portrait / A3 Landscape get a 19 mm bottom, but only when
    they still hold the old 9 mm jig default — a customised bottom is kept."""
    from core.settings import upgrade_margin_i1pro_tall_bottom, _I1_PRIMARY
    table = {
        "i1Pro|A4 Portrait": dict(_I1_PRIMARY),                       # old B=9
        "i1Pro|A3 Landscape": {"L": 26, "R": 9, "T": 38, "B": 12,     # customised
                               "desc": "x"},
    }
    out, changed = upgrade_margin_i1pro_tall_bottom(table)
    assert changed
    assert out["i1Pro|A4 Portrait"]["B"] == 19       # old default upgraded
    assert out["i1Pro|A3 Landscape"]["B"] == 12       # customisation kept
    # Idempotent on the now-19 values (A3 stays customised).
    _out2, changed2 = upgrade_margin_i1pro_tall_bottom(out)
    assert changed2 is False


def test_sidecar_ink_channels_roundtrip(tmp_path):
    from ui.tiff_preview import _find_sidecar_channels
    from workflow.layout_engine.colorants import rep_ink_codes
    codes = rep_ink_codes("CMYKOG")
    assert codes == ["c", "m", "y", "k", "o", "g"]
    (tmp_path / "chart.channels.json").write_text(
        json.dumps({"layout": {"engine": "chromiq"}, "ink_channels": codes}))
    (tmp_path / "chart_01.tif").write_bytes(b"")
    assert _find_sidecar_channels(tmp_path / "chart_01.tif") == codes


# ---------------------------------------------------------------------------
# #124 follow-up (Knut): the fill-up explanation on the ENGINE build path
# ---------------------------------------------------------------------------

def test_engine_padding_log_line():
    from workflow.chart_creator import _engine_padding_log_line
    line = _engine_padding_log_line(910, 14)
    assert "896 designed" in line and "14 paper-white" in line \
        and "= 910 total" in line
    assert _engine_padding_log_line(896, 0) == ""
    assert _engine_padding_log_line(896, -1) == ""


def test_layout_info_panel_fillup_row(qapp):
    from ui.chart_layout_info_panel import ChartLayoutInfoPanel
    p = ChartLayoutInfoPanel()
    p.set_actual(total=910, rows=13, cols=26, pages=2, fillup=14)
    p.set_estimate(total=910, rows=13, cols=26, pages=2, fillup=14)
    assert p._actual_labels["fillup"].text() == "14"
    assert p._estimate_labels["fillup"].text() == "14"
    p.set_actual(total=896, rows=13, cols=26, pages=2)   # unknown → dash
    assert p._actual_labels["fillup"].text() == "—"


# ---------------------------------------------------------------------------
# Clip text size (#125 wish list): manual size overrides the auto-fit
# ---------------------------------------------------------------------------

def test_clip_text_size_override_renders_smaller():
    import numpy as np
    from workflow.layout_engine.raster import render_clip_strip
    auto = render_clip_strip("text", width_px=140, height_px=1200, dpi=200,
                             text="RECORD SHEET", font_family="Inter")
    fixed = render_clip_strip("text", width_px=140, height_px=1200, dpi=200,
                              text="RECORD SHEET", font_family="Inter",
                              text_size_mm=3.0)
    dark = [int((np.asarray(im.convert("L")) < 128).sum()) for im in (auto, fixed)]
    assert dark[1] > 0                       # fixed size still renders text
    assert dark[0] > dark[1]                 # …and it is smaller than auto-fit


def test_clip_text_size_recipe_roundtrip():
    from workflow.layout_engine.presets import LayoutRecipe
    r = LayoutRecipe()
    r.clip_text_size_mm = 3.5
    assert LayoutRecipe.from_dict(r.to_dict()).clip_text_size_mm == 3.5
    assert LayoutRecipe.from_build_kwargs(
        r.build_kwargs()).clip_text_size_mm == 3.5


# ---------------------------------------------------------------------------
# "Where are my files?" folder guide (#125 wish list)
# ---------------------------------------------------------------------------

def test_file_guide_covers_every_file_family(qapp):
    from ui.file_guide import (file_guide_body, file_guide_card_subtitle,
                               file_guide_card_title)
    body = file_guide_body()
    assert file_guide_card_title() and file_guide_card_subtitle()
    for needle in (".icc", "_01.tif", ".ti3", ".ti1", ".ti2", "channels.json",
                   ".pdf", ".ps", "-colours.txt", "-i1profiler", ".cht", ".cie",
                   "reads/", "preconditioning", "merged", "calibrated.icc",
                   "Quality_Check_1_", "Refine_Strips_",
                   "project.json", "meta.json", "cal/", "exports/",
                   "Where are my files.txt"):
        assert needle in body, f"guide lost its {needle!r} entry"


def test_welcome_window_has_file_guide_card(qapp):
    # The guide lives in the Welcome/Help window as its OWN card (Basti) —
    # not in the Tools popup.
    from ui.dialogs.welcome_dialog import WORKFLOWS
    card = next(w for w in WORKFLOWS if w["key"] == "file_guide")
    assert card["kind"] == "files" and card["title"] and card["subtitle"]
    from ui.tools_popup import _GROUPS
    keys = [e.key for _hdr, entries in _GROUPS for e in entries]
    assert "file_guide" not in keys


def test_welcome_file_guide_card_opens_body(qapp):
    from ui.dialogs.welcome_dialog import WelcomeDialog
    # The card now renders the guide as an HTML table (Knut, #126), not the
    # plain-text body.
    from ui.file_guide import file_guide_html

    class _S:
        def get(self, k, d=None):
            return d

        def set(self, k, v):
            pass

    dlg = WelcomeDialog(_S())
    dlg._on_card_clicked("file_guide")
    from PyQt6.QtWidgets import QLabel
    texts = [w.text() for w in dlg.findChildren(QLabel)]
    assert any(t == file_guide_html() for t in texts)
    assert dlg._stack.currentIndex() == 1


def test_project_readme_mentions_new_sidecars(qapp, tmp_path):
    # The on-disk guide renders from ui.file_guide (one source with the help
    # card, #127) with {name} resolved to the real project name.
    from core.file_manager import Project
    proj = Project.create(tmp_path / "P", "P")
    s = proj.readme_path.read_text(encoding="utf-8")
    for needle in ("P.pdf", "P.ps", "P-colours.txt", "P-i1profiler.txt",
                   "P.cht", "Quality_Check_1_P.txt", "Refine_Strips_N_P.txt",
                   "Safe to tidy"):
        assert needle in s
