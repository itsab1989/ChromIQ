"""4.3.44: placeholders in the run's chart notes, and `{logo}`.

A forum tester (jctay, 2026-11-17) asked for `{page}`, `{date}`, `{seed}` in
"Run N Chart Notes" (they were printed literally; only the Sheet text filled
them in) and for a small ChromIQ logo on a high-density chart with no clip
band to carry it. The owner agreed, on one condition for the logo: it costs no
patch space, and the "IQ", the fonts and the colour are right.

Pinned here:

1. the notes are filled in ONLY where they are printed, per page, by the Sheet
   text's own rule (a chart in fixed order drops `{seed}`), and are stored
   exactly as typed (`docs/design/per_run_description.md`, awaiting
   confirmation); notes without a placeholder take the old path unchanged;
2. `{logo}` draws the clip band's own wordmark (`raster._wordmark_parts`),
   sized to the line, in its colours, in the Sheet text and in the notes; a
   line without it is measured and drawn exactly as before; a line too small
   for it leaves it out and says so in the log.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
import tifffile

from workflow import tiff_metadata
from workflow.layout_engine import raster
from workflow.layout_engine.chart import text_placeholder_context

DPI = 200
TI1 = Path(__file__).parent / "data" / "targen350_rgb.ti1"


def _mm(v):
    return int(round(v * DPI / 25.4))


def _sheet(path, channels=3):
    W, H = _mm(100.0), _mm(150.0)
    shape = (H, W, channels) if channels > 1 else (H, W)
    arr = np.full(shape, 255, dtype=np.uint8)
    arr[_mm(20.0):_mm(130.0), _mm(10.0):_mm(80.0)] = 128
    tifffile.imwrite(str(path), arr, resolution=(DPI, DPI),
                     resolutionunit="INCH")
    return path


def _pink(arr):
    """Pixels of the wordmark's magenta "IQ" (255, 69, 115), loosely."""
    a = arr.astype(int)
    return int(((a[..., 0] > 180) & (a[..., 1] < 150) & (a[..., 2] < 190)
                & (a[..., 0] - a[..., 1] > 80)).sum())


def _params(notes, recipe=None, stamp=False):
    from workflow.chart_creator import ChartParams
    from workflow.layout_engine.presets import LayoutRecipe
    rec = recipe or LayoutRecipe(instrument="i1", paper="A4")
    return ChartParams(instrument="i1", paper="A4", target_name="CP1500-192hd",
                       chart_notes=notes, stamp_commands=stamp,
                       layout_recipe=rec)


def _creator():
    from core.settings import AppSettings
    from workflow.chart_creator import ChartCreator

    class _FM:
        def chart_stem(self, cal_target: bool = False) -> str:
            return "CP1500-192hd"
    return ChartCreator(runner=None, file_mgr=_FM(), settings=AppSettings())


# ---- 1. the notes ---------------------------------------------------------------

def test_without_a_context_the_notes_are_the_line_as_typed():
    cc = _creator()
    p = _params("{page}-{date}-{seed}  123456789abcdefgh")
    assert cc.stamp_lines(p, 192) == ["{page}-{date}-{seed}  123456789abcdefgh"]


def test_the_notes_are_filled_in_like_the_sheet_text():
    cc = _creator()
    p = _params("{page}-{date}-{seed}  123456789abcdefgh")
    cc._notes_build = {"seed": 42, "randomize": True, "date": "2026-11-17",
                       "pages": 2, "patches": 192}
    ctx = cc.notes_context(p, 2, 2, 192)
    assert cc.stamp_lines(p, 192, ctx=ctx) == [
        "page 2/2-2026-11-17-seed 42  123456789abcdefgh"]
    # fixed order: the seed goes, and the separator in front of it
    cc._notes_build["randomize"] = False
    ctx = cc.notes_context(p, 1, 2, 192)
    assert cc.stamp_lines(p, 192, ctx=ctx) == [
        "page 1/2-2026-11-17  123456789abcdefgh"]
    assert p.chart_notes == "{page}-{date}-{seed}  123456789abcdefgh"


def test_notes_without_a_placeholder_are_unchanged_by_a_context():
    cc = _creator()
    p = _params("Canon Pro-1000 / Photo Rag 308")
    ctx = cc.notes_context(p, 1, 1, 100)
    assert cc.stamp_lines(p, 100, ctx=ctx) == cc.stamp_lines(p, 100)


def _handed_over(monkeypatch, tmp_path, notes, pages=2):
    from workflow import tiff_metadata as tm
    calls = []

    def spy(paths, lines, *a, **kw):
        calls.append(([Path(x).name for x in paths], list(lines)))

    monkeypatch.setattr(tm, "stamp_chart_metadata", spy)
    cc = _creator()
    monkeypatch.setattr(type(cc), "_should_use_engine", lambda self, p: True)
    monkeypatch.setattr(type(cc), "_count_patches_in_ti1",
                        lambda self, p: 192)
    monkeypatch.setattr(type(cc), "_engine_page_patch_boxes_mm",
                        lambda self, t, p: None)
    cc._notes_build = {"seed": 7, "randomize": True, "date": "2026-11-17",
                       "pages": pages, "patches": 192}
    tiffs = [_sheet(tmp_path / f"CP1500-192hd_{i + 1:02d}.tif")
             for i in range(pages)]
    p = _params(notes)
    cc._stamp_tiff_metadata(tiffs, p)
    assert p.chart_notes == notes                 # what is stored is as typed
    return calls


def test_each_page_gets_its_own_page_number(monkeypatch, tmp_path):
    calls = _handed_over(monkeypatch, tmp_path, "{page} {date} {seed} {logo}")
    assert calls == [
        (["CP1500-192hd_01.tif"], ["page 1/2 2026-11-17 seed 7 {logo}"]),
        (["CP1500-192hd_02.tif"], ["page 2/2 2026-11-17 seed 7 {logo}"])]


def test_notes_without_a_placeholder_take_the_one_call_as_before(
        monkeypatch, tmp_path):
    calls = _handed_over(monkeypatch, tmp_path, "Photo Rag 308")
    assert calls == [(["CP1500-192hd_01.tif", "CP1500-192hd_02.tif"],
                      ["Photo Rag 308"])]


# ---- 2. {logo} --------------------------------------------------------------------

def test_a_line_without_the_logo_is_measured_as_before():
    f = raster._font(40, "Inter")
    for t in ("", "page 1/2", "ChromIQ", "{page} {seed}"):
        assert raster.line_length_px(t, f) == float(f.getlength(t))
        assert raster.resolve_keeping_logo(t, {"page": "p"}) == \
            raster.resolve_placeholders(t, {"page": "p"})


def test_the_logo_is_the_clip_bands_wordmark_sized_to_the_line():
    f = raster._font(60, "Inter")
    tile, base = raster.logo_tile(raster._cap_px(f))
    arr = np.asarray(tile)
    assert _pink(arr) > 50                        # the "IQ" in its magenta
    dark = (arr[..., 3] > 200) & (arr[..., :3].max(axis=2) < 60)
    assert dark.sum() > 50                        # "Chrom" in near-black
    # its capital C is as tall as the text's capitals, within two pixels
    # (the italic "I" and the "Q" reach a hair higher than the "C")
    ink = np.where(arr[..., 3] > 128)[0]
    assert abs((base - ink.min()) - raster._cap_px(f)) <= 2
    # the line's length counts the wordmark as drawn
    assert raster.line_length_px("a {logo} b", f) == pytest.approx(
        f.getlength("a ") + tile.width + f.getlength(" b"))


def test_too_small_a_line_leaves_the_logo_out_and_says_so(caplog):
    f = raster._font(6, "Inter")
    assert raster.logo_tile(raster._cap_px(f)) is None
    img = Image_new()
    with caplog.at_level("INFO"):
        drawn = raster.draw_line_with_logo(img, (2, 2), "x {logo} y", f)
    assert [d[0] for d in drawn] == ["text", "text"]
    assert "{logo} left out" in caplog.text


def Image_new():
    from PIL import Image
    return Image.new("RGB", (400, 60), (255, 255, 255))


@pytest.mark.parametrize("channels", [3, 4])
def test_the_logo_in_the_notes_is_printed_in_its_colours(tmp_path, channels):
    plain = _sheet(tmp_path / "plain.tif", channels)
    logo = _sheet(tmp_path / "logo.tif", channels)
    tiff_metadata.stamp_chart_metadata([plain], ["Photo Rag ChromIQ"],
                                       text_edge_mm=4.0, size_pt=12.0)
    tiff_metadata.stamp_chart_metadata([logo], ["Photo Rag {logo}"],
                                       text_edge_mm=4.0, size_pt=12.0)
    a, b = tifffile.imread(str(plain)), tifffile.imread(str(logo))
    assert a.shape == b.shape
    assert _pink(b[..., :3]) > 20 and _pink(a[..., :3]) == 0
    # ink was added on the right edge in both, outside the patch block
    blank = np.asarray(tifffile.imread(str(_sheet(tmp_path / "c.tif",
                                                  channels))))
    for x in (a, b):
        d = np.abs(x.astype(int) - blank.astype(int))
        d = d.max(axis=2) if d.ndim == 3 else d
        cols = np.where(d.max(axis=0) > 40)[0]
        assert cols.size and cols.min() >= _mm(80.0)


def test_the_logo_in_the_sheet_text_is_drawn_below_the_patches(tmp_path):
    from workflow.layout_engine import chart
    from workflow.layout_engine.presets import LayoutRecipe
    out = {}
    for name, text in (("plain", "{page} ChromIQ"), ("logo", "{page} {logo}")):
        rec = LayoutRecipe(instrument="i1", paper="A4", dpi=100, seed=3,
                           chart_text=text, chart_text_size_mm=4.0)
        (tmp_path / name).mkdir()
        # the same chart name, so only the line can differ
        res, _r = chart.build_from_recipe(TI1, tmp_path / name / "chart", rec)
        out[name] = np.asarray(tifffile.imread(str(res.tiff_paths[0])))
    a, b = out["plain"], out["logo"]
    assert _pink(a) == 0 or _pink(b) > _pink(a)
    diff = np.abs(a.astype(int) - b.astype(int)).max(axis=2)
    rows = np.where(diff.max(axis=1) > 0)[0]
    assert rows.size                               # the line differs...
    assert rows.min() > a.shape[0] * 0.85          # ...only in the bottom text


@pytest.mark.parametrize("right_mm", [6.0, 9.0])
def test_a_note_with_the_logo_keeps_its_size_and_place(tmp_path, right_mm):
    """Found on screen in the fix round: with the font's empty line box
    above the wordmark counted, a narrow right margin shrank the note to the
    floor and pushed it off its strip. The note with `{logo}` takes the
    same columns as the note without it."""
    def sheet(name):
        W, H = _mm(100.0), _mm(150.0)
        a = np.full((H, W, 3), 255, np.uint8)
        a[_mm(15.0):_mm(135.0), _mm(5.0):_mm(100.0 - right_mm)] = 128
        p = tmp_path / name
        tifffile.imwrite(str(p), a, resolution=(DPI, DPI), resolutionunit="INCH")
        return p
    cols = []
    for name, text in (("a.tif", "page 1/1 2026-11-17 seed 4344"),
                       ("b.tif", "page 1/1 2026-11-17 seed 4344 {logo}")):
        p = sheet(name)
        tiff_metadata.stamp_chart_metadata([p], [text], text_edge_mm=4.0)
        a = tifffile.imread(str(p))
        ink = a.min(axis=2) < 200
        ink[:, :_mm(100.0 - right_mm)] = False
        c = np.where(ink.any(axis=0))[0]
        cols.append((int(c.min()), int(c.max())))
    assert cols[1][0] == cols[0][0]               # the same patch-side edge
    assert cols[1][1] <= a.shape[1] - _mm(4.0)    # inside the edge reserve
    assert cols[1][1] - cols[0][1] <= 3           # the "Q" tail, at most


# ---- {logo} follows the app's masthead; the clip band's branding is unchanged ----

def _old_painters(R):
    """The 4.3.43 wordmark painters (origin/master's raster.py), reinstated
    for the comparison below."""
    from PIL import ImageDraw

    def old_paint(layer, x, baseline, g):
        ImageDraw.Draw(layer).text((x, baseline), "Chrom", font=g["font"],
                                   fill=R.WORDMARK_RGB + (255,), anchor="ls")
        layer.paste(g["iq_tile"], (int(x + g["chrom_w"] + g["kern"] - g["iq_left"]),
                                   int(baseline - g["iq_base"])), g["iq_tile"])

    def old_h(canvas, draw, x, top, height, max_w):
        f, iq_tile, iq_base, iq_left, chrom_w, kern = R._wordmark_h_fit(
            draw, height, max_w)
        asc, desc = f.getmetrics()
        baseline = top + height * 0.5 + (asc - desc) / 2
        draw.text((x, baseline), "Chrom", font=f, fill=R.WORDMARK_RGB, anchor="ls")
        canvas.paste(iq_tile, (int(x + chrom_w + kern - iq_left),
                               int(baseline - iq_base)), iq_tile)
        return chrom_w + kern + (iq_tile.width - iq_left)
    return old_paint, old_h


#: Marker colours with the luminance of the wordmark's own (#1c1b18 and
#: #ff4573), so the clip content's measured reach (luminance < 250) and with
#: it the layout are exactly the new drawing's.
_MARK_DARK, _MARK_IQ = (0, 0, 236), (0, 200, 111)


def _marker_painter(R):
    """The new wordmark AND the old "IQ" (at 4.3.43's +2 % kern) in marker
    colours: the pixels a marked build changes against the real one are the
    union of the old and the new wordmark, the box the change must keep to."""
    from PIL import ImageDraw

    def paint(canvas, x, baseline, size, parts=None):
        g = parts if parts is not None else R._wordmark_parts(int(size))
        rgba = canvas.mode == "RGBA"
        ImageDraw.Draw(canvas).text((x, baseline), "Chrom", font=g["font"],
                                    fill=_MARK_DARK + ((255,) if rgba else ()),
                                    anchor="ls")
        tile = g["iq_tile"].copy()
        a = np.asarray(tile).copy()
        a[..., :3] = _MARK_IQ
        from PIL import Image
        tile = Image.fromarray(a, "RGBA")
        y = int(baseline - g["iq_base"])
        canvas.paste(tile, (int(round(x + g["chrom_w"] + R.MASTHEAD_IQ_KERN
                                      * g["size"])) - R._ITALIC_TILE_PEN, y),
                     tile)                                    # the new "IQ"
        canvas.paste(tile, (int(x + g["chrom_w"] + 0.02 * g["size"]
                                - g["iq_left"]), y), tile)    # 4.3.43's
    return paint


def _box(a, b):
    d = np.abs(a.astype(int) - b.astype(int)).max(axis=2)
    ys, xs = np.nonzero(d)
    return None if not len(ys) else (xs.min(), ys.min(), xs.max(), ys.max())


def _without_the_created_stamp(ti2: bytes) -> bytes:
    """The .ti2 with its one ``CREATED "<date time>"`` line emptied (ti2_writer stamps the
    build time to the second); every other byte is kept."""
    import re
    out, n = re.subn(rb'^CREATED "[^"\r\n]*"$', b'CREATED ""', ti2, flags=re.M)
    assert n == 1, n
    return out


@pytest.mark.parametrize("kw", [
    dict(instrument="i1", paper="A4", dpi=150, clip_content_mode="branding",
         clip_text="Line one\nLine two"),
    dict(instrument="i1", paper="A4", dpi=150, clip_content_mode="notes"),
    dict(instrument="CM", paper="Letter", dpi=150, clip_content_mode="notes",
         clip_side="right", clip_flip_180=True),
], ids=["branding", "notes", "notes_right_flipped"])
def test_the_new_wordmark_changes_only_the_wordmarks_own_pixels(
        tmp_path, monkeypatch, kw):
    """The owner, 2026-11-17: the wordmark on every chart is drawn as the
    app's masthead draws it. Against 4.3.43's drawing, the ONLY pixels that
    differ lie inside the wordmark's own box (the union of the old and the
    new wordmark's ink, found by building the chart with both in marker
    colours of the same luminance); the .ti2,
    every patch, strip, text and mark are identical."""
    from workflow.layout_engine import chart
    from workflow.layout_engine.presets import LayoutRecipe
    built = {}
    current = raster._paint_wordmark, raster._draw_wordmark_h
    painter = raster.paint_masthead_wordmark
    for which in ("old", "new", "marked"):
        p1, p2 = _old_painters(raster) if which == "old" else current
        monkeypatch.setattr(raster, "_paint_wordmark", p1)
        monkeypatch.setattr(raster, "_draw_wordmark_h", p2)
        monkeypatch.setattr(raster, "paint_masthead_wordmark",
                            _marker_painter(raster) if which == "marked"
                            else painter)
        raster._clip_reach_cached.cache_clear()
        (tmp_path / which).mkdir()
        res, _r = chart.build_from_recipe(
            TI1, tmp_path / which / "c", LayoutRecipe(seed=5, **kw))
        built[which] = ([np.asarray(tifffile.imread(str(p)))
                         for p in sorted(res.tiff_paths)],
                        (tmp_path / which / "c.ti2").read_bytes())
    raster._clip_reach_cached.cache_clear()
    # the three builds may straddle a second under load: the .ti2's CREATED time stamp (and
    # only that one line) is not part of what is compared
    ti2 = {k: _without_the_created_stamp(v[1]) for k, v in built.items()}
    assert ti2["old"] == ti2["new"]
    assert ti2["marked"] == ti2["new"]
    for old, new, marked in zip(built["old"][0], built["new"][0],
                                built["marked"][0]):
        changed = _box(old, new)
        assert changed is not None            # the drawing really changed
        x0, y0, x1, y1 = _box(new, marked)    # old and new wordmark, together
        assert x0 <= changed[0] and y0 <= changed[1] \
            and changed[2] <= x1 and changed[3] <= y1, (changed, (x0, y0, x1, y1))
        outside = np.abs(old.astype(int) - new.astype(int)).max(axis=2)
        outside[y0:y1 + 1, x0:x1 + 1] = 0
        assert not outside.any()


def test_the_logo_is_drawn_from_the_mastheads_own_definition():
    """The masthead draws "Chrom" in Instrument Serif and "IQ" in its italic,
    both at 62 px, "IQ" at the advance of "Chrom" less 1 px. If that ever
    changes, `raster.paint_masthead_wordmark` has to follow it."""
    import inspect
    from ui import masthead_header
    src = inspect.getsource(masthead_header.MastheadHeader.paintEvent)
    assert src.count("setPixelSize(62)") == 2
    assert "x_start + chrom_w - 1" in src
    assert '"Instrument Serif"' in src
    assert raster.MASTHEAD_IQ_KERN == -1.0 / 62.0
    # "IQ" starts where the masthead puts it: Chrom's advance less size/62
    size = 124
    from PIL import Image
    layer = Image.new("RGBA", (int(size * 4.2), int(size * 1.8)), (0, 0, 0, 0))
    raster.paint_masthead_wordmark(layer, 10, int(size * 1.3), size)
    a = np.asarray(layer)
    pink = (a[..., 3] > 128) & (a[..., 0] > 200) & (a[..., 1] < 140)
    dark = (a[..., 3] > 128) & (a[..., :3].max(axis=2) < 80)
    gap = np.argwhere(pink)[:, 1].min() - np.argwhere(dark)[:, 1].max()
    assert -2 <= gap <= 2          # the masthead capture: 0 px at 124 px
    # the render is stable: the same size twice gives the same pixels
    again = Image.new("RGBA", layer.size, (0, 0, 0, 0))
    raster.paint_masthead_wordmark(again, 10, int(size * 1.3), size)
    assert again.tobytes() == layer.tobytes()


def test_the_logo_minimum_is_eight_pixels():
    assert raster.LOGO_MIN_CAP_PX == 8
    assert raster.logo_tile(7.9) is None and raster.logo_tile(8) is not None


@pytest.mark.parametrize("width", [12.5, 13.0, 20.0])
@pytest.mark.parametrize("scale", [100.0, 150.0])
def test_the_clip_content_reach_the_layout_measures_is_unchanged(
        monkeypatch, width, scale):
    """The layout places the row labels and the right-edge note against the
    clip content's measured reach across the band, which the wordmark's ink
    decides: the new drawing moves the "IQ" only ALONG the band, so the reach,
    and with it every layout, is 4.3.43's to the pixel."""
    from tests.test_clip_border_content_is_centred_across_the_band import (
        T2, _setup)
    raster._clip_reach_cached.cache_clear()
    new = _setup(True, width, T2, scale)[0].clip_content_reach_mm
    p1, p2 = _old_painters(raster)
    monkeypatch.setattr(raster, "_paint_wordmark", p1)
    monkeypatch.setattr(raster, "_draw_wordmark_h", p2)
    raster._clip_reach_cached.cache_clear()
    old = _setup(True, width, T2, scale)[0].clip_content_reach_mm
    raster._clip_reach_cached.cache_clear()
    assert new == old
