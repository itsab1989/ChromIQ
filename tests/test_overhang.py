"""A chart a little larger than its paper (jctay 149803, Basti 2026-10-23):
printed at exactly 100 %, the part off the paper only ever empty margin, the
white the instrument needs kept; never shrunk. `workflow.overhang`."""
from __future__ import annotations

import numpy as np
import pytest
from PIL import Image

from workflow import overhang as O

FOUR_BY_SIX = (101.6, 152.4)
POSTCARD = (100.0, 148.0)


def test_a_chart_that_fits_is_centred_and_fits():
    p = O.plan((100.0, 150.0), (101.6, 152.4), O.Box(5, 5, 95, 145))
    assert p.fits and p.safe and p.offset_mm == pytest.approx((0.8, 1.2))


def test_jctays_case_with_wide_margins_is_safe_and_centred():
    # everything printed 14 mm from every edge: the i1Pro's 10 mm of white
    # and the 1 mm feed safety still leave room for 2.2 mm: centred
    content = O.Box(14, 14, 87.6, 138.4)
    keep = O.keep_box(content, FOUR_BY_SIX, "i1")
    p = O.plan(FOUR_BY_SIX, POSTCARD, content, keep)
    assert p.safe and not p.fits
    assert p.offset_mm == pytest.approx((-0.8, -2.2))
    assert p.cut_mm["top"] == pytest.approx(2.2)
    assert p.cut_mm["left"] == pytest.approx(0.8)


def test_the_cut_goes_into_the_empty_side():
    # printed content 1.5 mm from the right edge, wide margin on the left:
    # the chart moves left, the left margin takes the whole cut
    content = O.Box(25.0, 12.0, 100.1, 140.0)
    p = O.plan(FOUR_BY_SIX, POSTCARD, content, content)
    assert p.safe
    assert p.cut_mm["right"] == pytest.approx(0.0, abs=1e-6) or \
        p.cut_mm["right"] < 0.6
    assert p.offset_mm[0] + 100.1 <= 100.0 - O.SAFETY_MM + 1e-6
    assert p.cut_mm["left"] > 0.8
    assert p.shift_mm[0] < 0 and p.shift_mm[1] == pytest.approx(0.0)


def test_printed_content_near_the_edge_is_never_cut():
    # strip letters 1 mm from the top edge: 2.2 mm would go
    content = O.Box(12, 1.0, 89.6, 150.0)
    p = O.plan(FOUR_BY_SIX, POSTCARD, content, content)
    assert not p.safe and p.reason == "content"


def test_the_instruments_white_is_kept():
    # ink 3 mm from the bottom edge: fits the paper with a shift, but the
    # layout's 3 mm of white after the last patch would be taken
    content = O.Box(12, 9.0, 89.6, 149.4)
    keep = O.keep_box(content, FOUR_BY_SIX, "i1")
    p = O.plan(FOUR_BY_SIX, POSTCARD, content, keep)
    assert not p.safe and p.reason == "lead"


def test_too_much_is_a_chart_for_another_paper():
    p = O.plan((210.0, 297.0), (215.9, 279.4), O.Box(30, 30, 180, 260))
    assert not p.safe and p.reason == "too_much"


def test_unreadable_content_is_never_safe():
    p = O.plan(FOUR_BY_SIX, POSTCARD, None)
    assert not p.safe and p.reason == "unknown"


def test_a_chart_is_never_shrunk():
    """The plan only ever moves a chart; nothing in it scales."""
    import inspect
    src = inspect.getsource(O)
    assert "scale" not in src.replace("shrink", "").lower().replace(
        "never shrinks", "")


def test_content_box_reads_the_ink(tmp_path):
    a = np.full((600, 400, 3), 255, np.uint8)       # 400 x 600 px at 100 dpi
    a[50:550, 40:360] = (10, 200, 30)
    a[10:14, 200:202] = (0, 0, 0)                    # a helper mark
    path = tmp_path / "c.tif"
    Image.fromarray(a).save(path, dpi=(100, 100))
    b = O.content_box(path)
    assert b.left == pytest.approx(40 * 0.254)
    assert b.top == pytest.approx(10 * 0.254)
    assert b.right == pytest.approx(360 * 0.254)
    assert b.bottom == pytest.approx(550 * 0.254)


def test_paper_turned_like_the_chart():
    assert O.paper_like_chart((288, 432), (432, 288)) == (288, 432)
    assert O.paper_like_chart((432, 288), (432, 288)) == (432, 288)


def test_a_centred_plan_has_no_shift():
    content = O.Box(14, 14, 87.6, 138.4)
    p = O.plan(FOUR_BY_SIX, POSTCARD, content,
               O.keep_box(content, FOUR_BY_SIX, "i1"))
    assert p.shift_mm == pytest.approx((0.0, 0.0))


def test_the_page_suffix_comes_off_the_stem_and_nothing_more(tmp_path):
    import json
    (tmp_path / "Progress300.channels.json").write_text(json.dumps(
        {"layout": {"recipe": {"instrument": "p3"}}}), encoding="utf-8")
    assert O.instrument_of(tmp_path / "Progress300_02.tif") == "p3"


def _chart_tif(tmp_path, w_px=400, h_px=600, dpi=100):
    a = np.full((h_px, w_px, 3), 255, np.uint8)
    a[50:550, 40:360] = (10, 200, 30)
    path = tmp_path / "c.tif"
    Image.fromarray(a).save(path, dpi=(dpi, dpi))
    return path


def test_the_postscript_is_moved_not_scaled(tmp_path):
    import re
    from workflow.postscript_generator import PostScriptGenerator
    tif = _chart_tif(tmp_path)                 # 288 x 432 pt
    page = (283.46, 419.53)                    # 100 x 148 mm
    plain = PostScriptGenerator().generate(tif, page_size_pt=page)
    with O.placed((-2.0, 3.0)):
        moved = PostScriptGenerator().generate(tif, page_size_pt=page)
    t0 = [float(v) for v in re.search(r"([-\d.]+) ([-\d.]+) translate", plain).groups()]
    t1 = [float(v) for v in re.search(r"([-\d.]+) ([-\d.]+) translate", moved).groups()]
    assert t1[0] == pytest.approx(t0[0] - 2.0, abs=0.01)
    assert t1[1] == pytest.approx(t0[1] - 3.0, abs=0.01)     # down = -y in PS
    s0 = re.search(r"([\d.]+) ([\d.]+) scale", plain).groups()
    s1 = re.search(r"([\d.]+) ([\d.]+) scale", moved).groups()
    assert s0 == s1 == ("288.00", "432.00")                   # 100 %, always
    # and the setting ends with its block
    again = PostScriptGenerator().generate(tif, page_size_pt=page)
    assert again == plain


def test_the_exact_size_pdf_is_moved_the_same_way(tmp_path):
    import re
    import zlib
    from workflow.postscript_generator import PdfGenerator
    tif = _chart_tif(tmp_path)
    page = (283.46, 419.53)

    def cm(pdf: bytes):
        for chunk in re.findall(rb"stream\r?\n(.*?)\r?\nendstream", pdf, re.S):
            for data in (chunk,):
                try:
                    data = zlib.decompress(data)
                except zlib.error:
                    pass
                m = re.search(rb"([-\d.]+) ([-\d.]+) ([-\d.]+) ([-\d.]+) "
                              rb"([-\d.]+) ([-\d.]+) cm", data)
                if m:
                    return [float(v) for v in m.groups()]
        raise AssertionError("no cm")
    a = cm(PdfGenerator().generate(tif, page_size_pt=page))
    with O.placed((-2.0, 3.0)):
        b = cm(PdfGenerator().generate(tif, page_size_pt=page))
    assert b[:4] == a[:4]                                     # no scaling
    assert b[4] == pytest.approx(a[4] - 2.0, abs=0.01)
    assert b[5] == pytest.approx(a[5] - 3.0, abs=0.01)


# ---- the white is measured from the PATCHES, not from labels (agent 20,
# on-screen check with printtarg's own 4x6 i1Pro layout, 2026-10-23) ----

def _page(tmp_path, name, patches_mm, marks_mm=(), dpi=100, size=FOUR_BY_SIX):
    w, h = int(size[0] / 25.4 * dpi), int(size[1] / 25.4 * dpi)
    a = np.full((h, w, 3), 255, np.uint8)
    px = dpi / 25.4
    l, t, r, b = patches_mm
    a[int(t * px):int(b * px), int(l * px):int(r * px)] = (40, 120, 200)
    for (ml, mt, mr, mb) in marks_mm:      # letters, notes, ticks: small ink
        a[int(mt * px):int(mb * px), int(ml * px):int(mr * px)] = 0
    p = tmp_path / f"{name}_01.tif"
    Image.fromarray(a).save(p, dpi=(dpi, dpi))
    (tmp_path / f"{name}.ti2").write_text('CTI2\nTARGET_INSTRUMENT "X-Rite i1 Pro"\n',
                                         encoding="utf-8")
    return p


def test_patch_box_finds_the_patches_and_not_the_labels(tmp_path):
    marks = [(30 + 6 * i, 8, 32 + 6 * i, 11) for i in range(8)]       # strip letters
    marks += [(5 + 2 * i, 1.5, 5.3 + 2 * i, 3) for i in range(40)]    # ruler ticks
    p = _page(tmp_path, "c", (26, 27, 86, 138), marks)
    pb = O.patch_box(p)
    assert pb.top == pytest.approx(27, abs=0.6) and pb.bottom == pytest.approx(138, abs=0.6)
    assert pb.left == pytest.approx(26, abs=0.6) and pb.right == pytest.approx(86, abs=0.6)
    assert O.content_box(p).top == pytest.approx(1.5, abs=0.6)


def test_printtarg_style_4x6_on_a_postcard_prints_at_100_percent(tmp_path):
    """jctay's case: patches 27 to 138 mm down a 4x6 card, strip letters
    at 8 mm. The i1Pro's 10 mm of white before and after the patches stays on
    a 100 x 148 mm card, the letters too: printed centred, no question."""
    marks = [(30 + 6 * i, 8, 32 + 6 * i, 11) for i in range(8)]
    p = _page(tmp_path, "c", (26, 27, 62, 138), marks)
    pt = (FOUR_BY_SIX[0] / O.MM_PER_PT, FOUR_BY_SIX[1] / O.MM_PER_PT)
    paper = (POSTCARD[0] / O.MM_PER_PT, POSTCARD[1] / O.MM_PER_PT)
    plan = O.plan_for_chart([(p, 0)], pt, paper)
    assert plan.safe and plan.shift_mm == pytest.approx((0.0, 0.0), abs=1e-6)
    assert plan.cut_mm["top"] == pytest.approx(2.2, abs=0.05)


def test_the_lead_counts_from_the_patches(tmp_path):
    pt = (FOUR_BY_SIX[0] / O.MM_PER_PT, FOUR_BY_SIX[1] / O.MM_PER_PT)
    paper = (POSTCARD[0] / O.MM_PER_PT, POSTCARD[1] / O.MM_PER_PT)
    # patches end 9 mm above the bottom edge, with 27 mm of white above them:
    # the chart moves UP, so the whole cut falls in the top margin
    p = _page(tmp_path, "a", (26, 27, 62, 143.4))
    plan = O.plan_for_chart([(p, 0)], pt, paper)
    assert plan.safe and plan.cut_mm["bottom"] == pytest.approx(0.0, abs=1e-6)
    assert plan.shift_mm[1] < -2.0
    # ...and with only 12 mm above them too, there is no room either way
    q = _page(tmp_path, "b", (26, 12, 62, 143.4))
    plan = O.plan_for_chart([(q, 0)], pt, paper)
    assert not plan.safe and plan.reason == "lead"


def test_no_patches_found_grows_everything(tmp_path):
    # a page of small marks only: no patch band, the cautious rule
    p = _page(tmp_path, "c", (0, 0, 0, 0), [(10, 10, 11, 11), (90, 140, 91, 141)])
    assert O.patch_box(p) is None
    c = O.content_box(p)
    k = O.keep_box(c, FOUR_BY_SIX, "i1", None)
    assert k.top == 0.0 and k.bottom > 150.0     # the marks grown by the lead


# ---- the direct route's helpers (ui/tabs/tab_print.py) --------------------

def test_the_direct_route_notes_a_safe_overhang(tmp_path):
    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from types import SimpleNamespace
    from ui.tabs.tab_print import TabPrint
    marks = [(30 + 6 * i, 8, 32 + 6 * i, 11) for i in range(8)]
    p = _page(tmp_path, "c", (26, 27, 62, 138), marks, dpi=150)
    paper = (POSTCARD[0] / O.MM_PER_PT, POSTCARD[1] / O.MM_PER_PT)
    status = []
    fake = SimpleNamespace(_set_status=status.append,
                           _pending_print_record=("rec", {}))
    plan = TabPrint._overhang_plan(fake, [(p, 0)], paper)
    assert plan is not None and plan.safe
    TabPrint._note_overhang(fake, plan)
    assert status and "100 %" in status[0] and "2.2 mm at the top" in status[0]
    assert fake._pending_print_record[1]["outside_paper_mm"]["top"] == pytest.approx(2.2, abs=0.05)
    # a chart that fits asks nothing at all
    assert TabPrint._overhang_plan(fake, [(p, 0)], (300.0, 450.0)) is None


def test_the_direct_route_words_an_unsafe_overhang(tmp_path):
    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from types import SimpleNamespace
    from ui.tabs.tab_print import TabPrint
    p = _page(tmp_path, "c", (26, 27, 62, 138), [(10, 0.5, 12, 3), (10, 150, 12, 152)],
              dpi=150)
    paper = (POSTCARD[0] / O.MM_PER_PT, POSTCARD[1] / O.MM_PER_PT)
    plan = TabPrint._overhang_plan(SimpleNamespace(), [(p, 0)], paper)
    assert plan is not None and not plan.safe and plan.reason == "content"
    title, body = TabPrint._overhang_text(plan, p, paper, anyway=True)
    assert "102 × 152 mm" in body and "100 × 148 mm" in body
    assert "If you print anyway" in body and "strip letters" in body
    _t, body2 = TabPrint._overhang_text(plan, p, paper, anyway=False)
    assert "Nothing was printed." in body2
