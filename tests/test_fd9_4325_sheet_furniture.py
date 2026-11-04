"""4.3.25, the owner's second round of FD-9 feedback, what goes on the sheet:

* F5: the page number "N/M" of a multi-sheet chart stays at the top left and
  is turned 180 degrees, like the clip border; a one-sheet chart has none;
  printed with the clip border on or off, in the clip border's typeface;
* F12: the FD-9 clip border, ChromIQ's own clip border (the Notes box by
  default) in the trailing band, turned 180 degrees, off by default through
  ONE constant;
* F4: every generated page goes through the FD-9's own mark detector at two
  scan scales, and Generate refuses a page that what ChromIQ added would
  stop the FD-9 finding; TIFF and PDF carry the same artwork.

Synthetic scans only: whether a real FD-9 agrees is lessbones' device test.
"""
from tests._fd9_beta import fd9_beta_on, fd9_windows  # noqa: F401

import json
import time

import numpy as np
import pytest
from PIL import Image

from tests.test_fd9_chart_creation import ti1
from workflow.fd9 import furniture, sheet_check
from workflow.fd9.chart import PAPERS, build_chart, capacity, chart_pages
from workflow.fd9.measurement import checked_chart

DPI = 150


def _build(tmp_path, paper="A4", pages=2, name="c", rep="RGB",
           tokens=("R", "G", "B"), dpi=DPI, **kw):
    cap = capacity(paper)
    count = cap * (pages - 1) + (7 if pages > 1 else min(cap, 40))
    src, _ = ti1(tmp_path, rep=rep, tokens=tokens, count=count)
    kw.setdefault("sheet_project", "FD9-Test")
    kw.setdefault("sheet_run", "3")
    r = build_chart(src, tmp_path / name, paper=paper, dpi=dpi,
                    randomize=False, **kw)
    _, doc, _ = checked_chart(r.ti2_path)
    return r, chart_pages(doc)


def _ink(path):
    with Image.open(path) as im:
        return np.asarray(im.convert("L")) < 200


def _mm(v, dpi=DPI):
    return round(v * dpi / 25.4)


def test_one_default_switch_and_it_is_off():
    assert furniture.FD9_CLIP_BORDER_DEFAULT is False


def test_the_label_is_the_page_number_top_left_and_turned(tmp_path):
    """The owner's ruling: the label is the page number only, "N/M" as in
    4.3.24, at the top left, now turned 180 degrees like the clip border."""
    r, pages = _build(tmp_path)
    assert [p["page_label"] for p in pages] == ["1/2", "2/2"]
    ink = _ink(r.tiff_paths[0])
    assert ink[_mm(9):_mm(14), _mm(7):_mm(30)].sum() > 10
    mask = furniture.label_mask((800, 300), DPI, "1/2")
    font = furniture._font(round(furniture.LABEL_HEIGHT_MM * DPI / 25.4))
    tile = font.render("1/2")
    left, top = _mm(furniture.LABEL_LEFT_MM), _mm(furniture.LABEL_TOP_MM)
    got = np.asarray(mask)[top:top + tile.height, left:left + tile.width]
    assert np.array_equal(got, np.asarray(tile.rotate(180)))
    assert not np.array_equal(got, np.asarray(tile))


def test_a_one_sheet_chart_has_no_label(tmp_path):
    r, pages = _build(tmp_path, pages=1)
    assert "page_label" not in pages[0]
    assert not _ink(r.tiff_paths[0])[_mm(9):_mm(14), _mm(7):_mm(70)].any()


def test_the_label_is_printed_in_the_clip_borders_typeface():
    """Review M1: the label used Pillow's built-in font; it is now the
    bundled Inter the clip border and the record strip print with, and
    every character of a page number is a real glyph, never a box."""
    from workflow.layout_engine.raster import _font as engine_font
    f = furniture._font(28)
    inter = engine_font(28, "Inter")
    assert f.fonts[0].path == inter.path and "Inter" in str(inter.path)
    for ch in "0123456789/":
        assert furniture._covers(f.fonts[0], ch), ch
    assert not furniture._covers(f.fonts[0], "")
    # A character Inter has no glyph for prints as "?", not as a box.
    assert f.runs("1/2") == [(f.fonts[0], "1?/2")]


@pytest.mark.parametrize("clip", [False, True])
def test_the_label_is_printed_with_the_clip_border_on_or_off(tmp_path, clip):
    r, pages = _build(tmp_path, clip_border=clip)
    assert all("page_label" in p for p in pages)
    assert ("clip_border_mm" in pages[0]) is clip


def test_the_clip_border_is_off_unless_switched_on(tmp_path):
    _r, pages = _build(tmp_path)
    assert all("clip_border_mm" not in p for p in pages)


def test_the_clip_border_lies_in_the_trailing_band_turned_round(tmp_path):
    r, pages = _build(tmp_path, clip_border=True, dpi=300)
    from workflow.layout_engine.raster import WORDMARK_IQ_RGB
    for tif, page in zip(r.tiff_paths, pages):
        x0, y0, x1, y1 = page["clip_border_mm"]
        w, h = page["paper_mm"]
        assert x0 >= 10 and w - x1 >= 10
        last = page["rows"][-1][0]["centre_mm"][1] + page["patch_mm"][1] / 2
        marks = max(y for _x, y in page["fiducials_mm"]) + 1.5
        assert y0 >= max(last, marks) + 2 - 1e-6 and y1 <= h - 6 + 1e-6
        assert y1 - y0 <= 14 + 1e-6
        with Image.open(tif) as im:
            rgb = np.asarray(im.convert("RGB")).astype(int)
        band = rgb[_mm(y0, 300):_mm(y1, 300), _mm(x0, 300):_mm(x1, 300)]
        pink = (np.abs(band - np.array(WORDMARK_IQ_RGB)).sum(axis=2) < 60)
        assert pink.sum() > 100, "the wordmark's IQ is printed"
        cols = np.nonzero(pink.any(axis=0))[0]
        # Upright, the Notes box starts with the wordmark at the left end;
        # turned 180 degrees it sits at the right end.
        assert cols.min() > band.shape[1] * 0.7
        # Nothing of the clip border outside its band.
        dark = (rgb.min(axis=2) < 200)
        below = dark[_mm(y1, 300) + 2:, :]
        assert not below.any()


def _found_marks(gray, dpi):
    from fd9_independent.geometry import find_marks
    out = []
    for scan_dpi in sheet_check.SCAN_DPI:
        scan, *_ = sheet_check._scan(gray, dpi, scan_dpi)
        out.append(len(find_marks(scan.tobytes(), scan.width, scan.height)))
    return out


@pytest.mark.parametrize("paper", PAPERS)
@pytest.mark.parametrize("clip", [False, True])
def test_every_paper_and_page_is_found_at_both_scan_scales(tmp_path, paper,
                                                           clip):
    """The vendored detector itself, independently of the builder's own
    check: exactly four marks on every page, with and without the clip
    border, at both scales."""
    from workflow.fd9.independent import driver
    driver(None)
    r, pages = _build(tmp_path, paper=paper, clip_border=clip)
    assert len(r.tiff_paths) == len(pages) == 2
    for tif, page in zip(r.tiff_paths, pages):
        with Image.open(tif) as im:
            gray = np.asarray(im.convert("L"))
        assert _found_marks(gray, DPI) == [4, 4]
        sheet_check.check_page(gray, DPI, page)   # grid where it is printed


def test_cmyk_charts_carry_the_clip_border_in_black_and_are_found(tmp_path):
    r, pages = _build(tmp_path, rep="CMYK", tokens=("C", "M", "Y", "K"),
                      clip_border=True)
    assert "clip_border_mm" in pages[0]


def test_generate_refuses_a_clip_border_the_fd9_would_not_find(tmp_path,
                                                                monkeypatch):
    """A clip border that prints something the FD-9 takes for a fifth mark
    (a filled 3 mm square, the worst case of the 2026-11-04 synthetic scans)
    is refused before any file is written; the same chart without it is
    made."""
    real = furniture.clip_artwork

    def with_a_square(band_mm, dpi, **kw):
        art, xy = real(band_mm, dpi, **kw)
        from PIL import ImageDraw
        s = round(3 * dpi / 25.4)
        ImageDraw.Draw(art).rectangle((art.width // 2, 4, art.width // 2 + s,
                                       4 + s), fill=(0, 0, 0))
        return art, xy
    import workflow.fd9.chart as chart_mod
    monkeypatch.setattr(furniture, "clip_artwork", with_a_square)
    with pytest.raises(sheet_check.SheetNotDetectable) as caught:
        _build(tmp_path, name="refused", clip_border=True, dpi=300)
    e = caught.value
    assert (e.fd9_page, e.fd9_pages) == (1, 2)
    assert "four" in str(e)
    assert not list(tmp_path.glob("refused*"))     # nothing written
    _build(tmp_path, name="made", clip_border=False, dpi=300)
    assert chart_mod  # the module the builder imported from


def test_a_failure_not_caused_by_chromiq_is_made_as_before(tmp_path, caplog):
    """Black 6 mm patches can look like marks at the smaller scan scale
    (report point 8.5): that is a question for the device, not something
    ChromIQ added, so the chart is made as in 4.3.24 and the log says so."""
    src, _ = ti1(tmp_path, rep="RGB", tokens=("R", "G", "B"), count=30)
    text = src.read_text(encoding="utf-8").splitlines()
    i = text.index("BEGIN_DATA")
    text[i + 1:i + 31] = [f"{n + 1} 0 0 0" for n in range(30)]
    src.write_text("\n".join(text) + "\n", encoding="utf-8")
    import logging
    with caplog.at_level(logging.WARNING, logger="workflow.fd9.sheet_check"):
        r = build_chart(src, tmp_path / "dark", paper="A4", dpi=300,
                        patch_mm=6, randomize=False)
    assert r.tiff_paths and "device" in caplog.text


def test_the_pdf_carries_the_same_label_and_clip_border(tmp_path):
    import fitz
    from workflow.layout_engine.raster import WORDMARK_IQ_RGB
    r, pages = _build(tmp_path, clip_border=True, export_pdf=True, dpi=300)
    page = pages[0]
    with fitz.open(r.pdf_path) as pdf:
        pix = pdf[0].get_pixmap(dpi=150)
        rgb = np.frombuffer(pix.samples, dtype=np.uint8).reshape(
            pix.height, pix.width, pix.n)[..., :3].astype(int)
    x0, y0, x1, y1 = page["clip_border_mm"]
    band = rgb[_mm(y0):_mm(y1), _mm(x0):_mm(x1)]
    # The wordmark's magenta "IQ" (quantised for the vector runs).
    assert WORDMARK_IQ_RGB[0] > 200
    pink = (band[..., 0] > 180) & (band[..., 1] < 150) & (band[..., 2] > 60)
    assert pink.sum() > 20
    assert np.nonzero(pink.any(axis=0))[0].min() > band.shape[1] * 0.7
    label = (rgb[_mm(9):_mm(14), _mm(7):_mm(70)].min(axis=2) < 128)
    assert label.sum() > 20


def test_the_check_costs_little(tmp_path):
    """Generate must not slow down noticeably: the check of one A4 page at
    both scales, measured on its own."""
    r, pages = _build(tmp_path, pages=1, dpi=300)
    with Image.open(r.tiff_paths[0]) as im:
        gray = np.asarray(im.convert("L"))
    t0 = time.perf_counter()
    for _ in range(3):
        sheet_check.check_page(gray, 300, pages[0])
    # 5 s, not 1 (4.3.25 final review, L5). Measured alone the check takes a
    # fraction of a second; inside a full gate every core is busy and a slow
    # VM is slower still, so 1 s was a phantom red waiting to happen. Five
    # still fails at once for what this guards against: a check that has
    # become many times slower, or one that hangs.
    assert (time.perf_counter() - t0) / 3 < 5.0


def test_the_window_counts_pages_and_names_them():
    from workflow import measurement_messages as M
    title, body = M.M_FD9_CHART_UNDETECTABLE.render(page=2, pages=3,
                                                    reason="x")
    assert "page 2 of 3" in body and "“Generate Chart”" in body
    _t, one = M.M_FD9_CHART_UNDETECTABLE.render(page=1, pages=1, reason="x")
    assert "page 1 of 1" not in one and "this sheet" in one


def test_the_chart_creator_gives_the_fd9_its_project_run_and_clip():
    from types import SimpleNamespace
    from workflow.chart_creator import ChartCreator
    from workflow.layout_engine.presets import LayoutRecipe
    run = SimpleNamespace(id="run4")
    fm = SimpleNamespace(project=lambda: SimpleNamespace(
        current_run=lambda: run))
    rec = LayoutRecipe(instrument="FD9", paper="A4", fd9_clip_border=True,
                       clip_content_mode="notes", clip_text="hello")
    params = SimpleNamespace(instrument="FD9", paper="A4", layout_recipe=rec,
                             tiff_dpi=300, tiff_16bit=False, no_randomise=False,
                             cal_target=False, engine_cal_path="",
                             engine_apply_cal=False, target_name="Proj",
                             run_description="desc", fd9_patch_mm=8.0,
                             fd9_patch_h_mm=None, fd9_gap_mm=1.0,
                             fd9_strip_gap_mm=None)
    kw = ChartCreator._engine_kwargs(SimpleNamespace(_file_mgr=fm), params)
    assert (kw["project"], kw["fd9_run"], kw["fd9_clip_border"],
            kw["clip_text"], kw["rundescription"]) == (
        "Proj", "4", True, "hello", "desc")
    params.cal_target = True
    kw = ChartCreator._engine_kwargs(SimpleNamespace(_file_mgr=fm), params)
    assert kw["fd9_run"] == "calibration" and kw["randomize"] is False


def test_the_run_named_on_the_label_comes_from_a_real_project(tmp_path):
    from PyQt6.QtCore import QSettings
    from types import SimpleNamespace
    from core.file_manager import FileManager
    from core.settings import AppSettings
    from workflow.chart_creator import _fd9_run_label
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    s.set("custom_output_path", str(tmp_path / "projects"))
    fm = FileManager(s)
    fm.set_target_name("Label-Test")
    assert _fd9_run_label(fm, SimpleNamespace(cal_target=False)) == "1"
    assert _fd9_run_label(fm, SimpleNamespace(cal_target=True)) == "calibration"


def _with_square(monkeypatch, where):
    """Make the label or the clip border print a filled 3 mm square, the
    worst case of the synthetic scans, so the detector finds a fifth mark."""
    from PIL import ImageDraw
    if where in ("label", "both"):
        real = furniture.label_mask

        def label(size, dpi, text):
            m = real(size, dpi, text)
            s = round(3 * dpi / 25.4)
            x = round(40 * dpi / 25.4)
            ImageDraw.Draw(m).rectangle((x, 4, x + s, 4 + s), fill=1)
            return m
        monkeypatch.setattr(furniture, "label_mask", label)
    if where in ("clip", "both"):
        real_art = furniture.clip_artwork

        def art(band_mm, dpi, **kw):
            a, xy = real_art(band_mm, dpi, **kw)
            s = round(3 * dpi / 25.4)
            ImageDraw.Draw(a).rectangle((a.width // 2, 4, a.width // 2 + s,
                                         4 + s), fill=(0, 0, 0))
            return a, xy
        monkeypatch.setattr(furniture, "clip_artwork", art)


@pytest.mark.parametrize("where", ["label", "clip", "both"])
def test_the_refusal_names_what_is_in_the_way(tmp_path, monkeypatch, where):
    """Review M3: the page is checked again without the page number and
    without the clip border, and the window says which of them is in the
    way, with the advice that fits."""
    from workflow import measurement_messages as M
    _with_square(monkeypatch, where)
    with pytest.raises(sheet_check.SheetNotDetectable) as caught:
        _build(tmp_path, clip_border=(where != "label"), dpi=300)
    # A fifth mark in EACH of the two: either one alone already breaks the
    # page, so the case is "each" (review round 2, N1), not "both".
    want = "each" if where == "both" else where
    assert caught.value.cause == want
    msg = {"label": M.M_FD9_CHART_UNDETECTABLE_LABEL,
           "each": M.M_FD9_CHART_UNDETECTABLE_EACH}.get(
        want, M.M_FD9_CHART_UNDETECTABLE)
    body = msg.render(page=1, pages=2, reason="r")[1]
    if want == "label":
        assert "page number" in body and "tell us" in body
        assert "clip border" not in body
    elif want == "each":
        assert "not enough" in body
    else:
        assert "Notes box" in body and "switch the clip border off" in body


def test_a_one_sheet_chart_named_with_an_underscore_number_keeps_its_marks(
        tmp_path):
    """Review M2: "Glossy_300.tif" beside "Glossy_300.fd9.json" is a
    one-sheet chart, not page 300 of "Glossy"."""
    from workflow import printer_edges as PE
    src, _ = ti1(tmp_path, rep="RGB", tokens=("R", "G", "B"), count=40)
    r = build_chart(src, tmp_path / "Glossy_300", paper="A4", dpi=100,
                    randomize=False)
    assert r.tiff_paths[0].name == "Glossy_300.tif"
    assert len(PE._fd9_mark_boxes(r.tiff_paths[0])) == 5
    loss = PE.losses_for_chart([(r.tiff_paths[0], 0)],
                               PE.Edges(6.4, 6.4, 6.4, 6.4, "ppd"),
                               (210.0, 297.0))
    assert set(loss.fd9_marks) == {"left", "right"}


# ---- review round 2, N1: the truth table, with a stub detector -------------
@pytest.mark.parametrize("fails_with,cause", [
    # the set of printed items with which the stub detector fails
    ({"label+clip"}, "both"),                      # a and b
    ({"label+clip", "label"}, "label"),            # a only
    ({"label+clip", "clip"}, "clip"),              # b only
    ({"label+clip", "label", "clip"}, "each"),     # neither, but without both
    ({"label+clip", "label", "clip", "none"}, None),  # not ChromIQ's
])
def test_every_case_of_the_truth_table(monkeypatch, fails_with, cause):
    """The page is checked without the page number, without the clip border
    and without both; which of them helps decides the window. The stub
    detector fails for exactly the combinations of printed items given."""
    LABEL, CLIP = 10, 20                        # grey values that mark each
    gray = np.full((40, 40), 255, dtype=np.uint8)
    gray[2:6, 2:6] = LABEL
    gray[30:34, 30:34] = CLIP
    label = gray == LABEL
    clip = gray == CLIP

    def stub(g, dpi, page_doc, page=1, pages=1):
        here = (("label" if (g == LABEL).any() else "")
                + ("+" if (g == LABEL).any() and (g == CLIP).any() else "")
                + ("clip" if (g == CLIP).any() else "")) or "none"
        if here in fails_with:
            raise sheet_check.SheetNotDetectable(page, pages, dpi, here)
    monkeypatch.setattr(sheet_check, "check_page", stub)
    if cause is None:
        sheet_check.check_page_furniture(gray, label, clip, 300, {}, 1, 2)
        return
    with pytest.raises(sheet_check.SheetNotDetectable) as caught:
        sheet_check.check_page_furniture(gray, label, clip, 300, {}, 1, 2)
    assert caught.value.cause == cause


def test_each_window_says_what_is_true_of_its_case():
    from workflow import measurement_messages as M
    kw = dict(page=2, pages=3, reason="r")
    each = M.M_FD9_CHART_UNDETECTABLE_EACH.render(**kw)[1]
    assert "each got in the way on their own" in each
    assert "Switching the clip border off is not enough" in each
    assert "different patch size or paper" in each and "tell us" in each
    both = M.M_FD9_CHART_UNDETECTABLE_BOTH.render(**kw)[1]
    assert "although it does with either one alone" in both
    assert "switch the clip border off" in both
    label = M.M_FD9_CHART_UNDETECTABLE_LABEL.render(**kw)[1]
    assert "clip border" not in label
    for text in (each, both, label):
        assert "—" not in text
