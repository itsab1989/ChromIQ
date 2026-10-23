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

def _page(tmp_path, name, patches_mm, marks_mm=(), dpi=100, size=FOUR_BY_SIX,
          instrument="i1"):
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
    if instrument:
        # as ChromIQ's own printtarg charts record it (create_chart_settings)
        import json
        (tmp_path / f"{name}.channels.json").write_text(json.dumps(
            {"create_chart_settings": {"printtarg-i": {"value": instrument}}}),
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
    a 100 x 148 mm card, the letters too: printed at 100 %, no question.

    The patches start 26 mm from the left: printtarg's holder-clip border
    (printtarg.c:2138-2139), which the i1Pro's holder grips. It is kept, so
    the chart moves right and the empty right margin takes the cut (agent
    22, against the ArgyllCMS 3.5.0 source)."""
    marks = [(30 + 6 * i, 8, 32 + 6 * i, 11) for i in range(8)]
    p = _page(tmp_path, "c", (26, 27, 62, 138), marks)
    pt = (FOUR_BY_SIX[0] / O.MM_PER_PT, FOUR_BY_SIX[1] / O.MM_PER_PT)
    paper = (POSTCARD[0] / O.MM_PER_PT, POSTCARD[1] / O.MM_PER_PT)
    plan = O.plan_for_chart([(p, 0)], pt, paper)
    assert plan.safe and plan.shift_mm[1] == pytest.approx(0.0, abs=1e-6)
    assert plan.cut_mm["left"] == pytest.approx(0.0, abs=1e-6)
    assert plan.shift_mm[0] == pytest.approx(0.8 + O.SAFETY_MM, abs=0.05)
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


# ---- agent 22, 2026-10-23: the white is ArgyllCMS's own, and printtarg's
# caption line is the one printed thing that may be cut (Basti) -------------

def test_the_strip_white_is_printtargs_own():
    """ArgyllCMS 3.5.0 target/printtarg.c: lcar / tspa per instrument, the
    larger kept at both ends of a strip (it can be read either way)."""
    assert O.white_mm("i1") == {"left": 26.0, "right": 0.0, "top": 10.0, "bottom": 10.0}
    assert O.white_mm("p3") == {"left": 26.0, "right": 0.0, "top": 20.0, "bottom": 20.0}
    assert O.white_mm("CM") == {"left": 0.0, "right": 0.0, "top": 25.0, "bottom": 25.0}
    assert O.white_mm("41")["top"] == 25.0          # 12.7 / 18.8 at the default size
    assert O.white_mm("51")["bottom"] == pytest.approx(6.35)
    assert O.white_mm("SS")["top"] == O._LEAD_OTHER_MM
    assert O.white_mm("CR30")["top"] == O._LEAD_OTHER_MM
    assert set(O.white_mm(None).values()) == {25.0}  # not known: the most, everywhere


def test_a_bare_printtarg_ti2_is_read_as_the_instrument_that_needs_more(tmp_path):
    """printtarg writes "GretagMacbeth i1 Pro" for -i i1 AND -i 3p
    (printtarg.c:3341, spectro/insttypes.c), so a chart with nothing else to
    go by keeps the i1Pro 3 Plus's 20 mm."""
    for name, words, code in (("a", "GretagMacbeth i1 Pro", "p3"),
                              ("b", "X-Rite ColorMunki", "CM"),
                              ("c", "X-Rite DTP41", "41"),
                              ("d", "X-Rite DTP51", "51"),
                              ("e", "GretagMacbeth SpectroScan", "SS")):
        (tmp_path / f"{name}.ti2").write_text(
            f'CTI2\nORIGINATOR "Argyll printtarg"\nTARGET_INSTRUMENT "{words}"\n',
            encoding="utf-8")
        assert O.instrument_of(tmp_path / f"{name}.tif") == code, words


def test_the_colormunki_needs_no_white_beside_its_strips(tmp_path):
    """A ColorMunki 4 x 6 card: three strips from 6 to 90 mm across, the
    patches 35 to 126 mm down. Its 25 mm run-off is along the strip; across
    them printtarg asks for none, so the 1.6 mm that does not fit comes off
    the side margins and the card prints."""
    p = _page(tmp_path, "cm", (6, 35, 90, 126),
              [(10 + 28 * i, 8, 13 + 28 * i, 12) for i in range(3)],
              instrument="CM")
    pt = (FOUR_BY_SIX[0] / O.MM_PER_PT, FOUR_BY_SIX[1] / O.MM_PER_PT)
    paper = (POSTCARD[0] / O.MM_PER_PT, POSTCARD[1] / O.MM_PER_PT)
    plan = O.plan_for_chart([(p, 0)], pt, paper)
    assert plan.safe, plan.reason
    # the 25 mm after the last patch stays on the paper
    assert 126 + 25 + plan.offset_mm[1] <= POSTCARD[1] - O.SAFETY_MM + 0.3  # 100 dpi


def _printtarg_page(tmp_path, name, *, caption=(55.0, 0.0, 58.8, 152.4),
                    extra=(), originator="Argyll printtarg", dpi=100):
    """A printtarg-made 4 x 6 page: i1Pro patches 6 to 54 mm across and 27
    to 138 mm down, strip letters at 8 mm, and the caption column printtarg
    writes after the last strip (printtarg.c:2805) running *caption*."""
    import json
    p = _page(tmp_path, name, (6, 27, 54, 138),
              [(8 + 8 * i, 8, 10 + 8 * i, 11) for i in range(6)], dpi=dpi,
              instrument=None)
    a = np.asarray(Image.open(p)).copy()
    px = dpi / 25.4
    marks = list(extra)
    if caption is not None:
        l, t, r, b = caption
        # glyph-like: short dark runs with gaps, down the column
        for y in np.arange(t, b - 1.0, 2.0):
            marks.append((l, y, r, y + 1.2))
    for (ml, mt, mr, mb) in marks:
        a[int(mt * px):max(int(mt * px) + 1, int(mb * px)),
          int(ml * px):max(int(ml * px) + 1, int(mr * px))] = 0
    Image.fromarray(a).save(p, dpi=(dpi, dpi))
    (tmp_path / f"{name}.ti2").write_text(
        f'CTI2\nORIGINATOR "{originator}"\nTARGET_INSTRUMENT "GretagMacbeth i1 Pro"\n',
        encoding="utf-8")
    (tmp_path / f"{name}.channels.json").write_text(json.dumps(
        {"create_chart_settings": {"printtarg-i": {"value": "i1"}}}), encoding="utf-8")
    return p


def _plan(p, paper=POSTCARD):
    pt = (FOUR_BY_SIX[0] / O.MM_PER_PT, FOUR_BY_SIX[1] / O.MM_PER_PT)
    return O.plan_for_chart([(p, 0)], pt, (paper[0] / O.MM_PER_PT,
                                            paper[1] / O.MM_PER_PT))


@pytest.mark.parametrize("paper", [POSTCARD, (100.0, 150.0)])
def test_printtargs_caption_may_be_cut_and_nothing_else(tmp_path, paper):
    """Basti, 2026-10-23: the caption line, edge to edge on a 4 x 6 card,
    counts as cuttable; it is all that is cut."""
    p = _printtarg_page(tmp_path, "cap")
    cap = O.caption_box(p)
    assert cap is not None and cap.left == pytest.approx(55.0, abs=0.6)
    plan = _plan(p, paper)
    assert plan.safe, plan.reason
    assert plan.caption_cut()
    # the letters at 8 mm and the patches stay on, with the feed's 1 mm
    assert 8 + plan.offset_mm[1] >= O.SAFETY_MM - 1e-6


def test_the_same_line_on_a_chart_printtarg_did_not_make_is_content(tmp_path):
    p = _printtarg_page(tmp_path, "eng", originator="ChromIQ layout engine")
    assert O.caption_box(p) is None
    plan = _plan(p)
    assert not plan.safe and plan.reason == "content"


def test_anything_beyond_the_caption_is_still_content(tmp_path):
    """ChromIQ's own note or settings stamp further right is not the caption:
    run edge to edge, it still refuses."""
    p = _printtarg_page(tmp_path, "stamp", extra=[(80.0, 0.0, 81.5, 152.4)])
    cap = O.caption_box(p)
    assert cap is not None and cap.right < 60.0
    plan = _plan(p)
    assert not plan.safe and plan.reason == "content"


def test_a_column_too_far_from_the_patches_is_not_the_caption(tmp_path):
    p = _printtarg_page(tmp_path, "far", caption=(64.0, 0.0, 67.8, 152.4))
    assert O.caption_box(p) is None
    assert not _plan(p).safe


def test_the_dtp51_has_no_caption(tmp_path):
    import json
    p = _printtarg_page(tmp_path, "d51")
    (tmp_path / "d51.channels.json").write_text(json.dumps(
        {"create_chart_settings": {"printtarg-i": {"value": "51"}}}), encoding="utf-8")
    assert O.caption_box(p) is None


_ARGYLL = __import__("pathlib").Path("/Applications/Argyll/bin")


@pytest.mark.skipif(not (_ARGYLL / "printtarg").exists(), reason="no ArgyllCMS")
@pytest.mark.parametrize("inst", ["i1", "CM"])
def test_a_real_printtarg_4x6_with_a_long_name_prints_on_a_postcard(tmp_path, inst):
    """printtarg's own 4 x 6 card, named long enough that its caption runs
    from edge to edge (agent 20's refused case), i1Pro and ColorMunki."""
    import json
    import subprocess
    name = f"Jctay-4x6-{inst}Pro"
    subprocess.run([str(_ARGYLL / "targen"), "-v0", "-d2", "-f60", name],
                   cwd=tmp_path, check=True, capture_output=True, timeout=120)
    subprocess.run([str(_ARGYLL / "printtarg"), "-v0", f"-i{inst}", "-p4x6",
                    "-t300", "-m6", "-M6", "-L", "-R16", name], cwd=tmp_path, check=True,
                   capture_output=True, timeout=120)
    (tmp_path / f"{name}.channels.json").write_text(json.dumps(
        {"create_chart_settings": {"printtarg-i": {"value": inst}}}), encoding="utf-8")
    pages = sorted(tmp_path.glob(f"{name}*.tif"))
    assert pages
    # without the caption rule this card is refused: its caption comes
    # closer to an edge than the cut leaves (agent 20's on-screen case)
    whole = O.content_box(pages[0])
    pb = O.patch_box(pages[0])
    old = O.plan(FOUR_BY_SIX, POSTCARD, whole,
                 O.keep_box(whole, FOUR_BY_SIX, inst, pb))
    assert not old.safe and old.reason == "content"
    for paper in (POSTCARD, (100.0, 150.0)):
        plan = _plan(pages[0], paper) if len(pages) == 1 else O.plan_for_chart(
            [(q, 0) for q in pages],
            (FOUR_BY_SIX[0] / O.MM_PER_PT, FOUR_BY_SIX[1] / O.MM_PER_PT),
            (paper[0] / O.MM_PER_PT, paper[1] / O.MM_PER_PT))
        assert plan.safe, (paper, plan.reason)
        assert plan.caption_cut()


# ---- the layout engine's ruler helper markers may be cut too (Basti,
# 2026-10-23, through the orchestrator) --------------------------------------

def _engine_page(tmp_path, name, *, markers=True, edge=2.0, length=2.0,
                 extra=(), dpi=150, size=(100.0, 150.0), recipe=True):
    """A layout-engine 10 x 15 cm card: patches 19 to 95 mm across and 17
    to 137 mm down, strip letters at 12 mm, and ruler dashes every 3 mm along
    all four edges, *edge* mm in and *length* mm long (#152)."""
    import json
    w, h = int(round(size[0] / 25.4 * dpi)), int(round(size[1] / 25.4 * dpi))
    a = np.full((h, w, 3), 255, np.uint8)
    px = dpi / 25.4

    def ink(l, t, r, b):
        a[int(round(t * px)):max(int(round(t * px)) + 1, int(round(b * px))),
          int(round(l * px)):max(int(round(l * px)) + 1, int(round(r * px)))] = 0
    a[int(17 * px):int(137 * px), int(19 * px):int(95 * px)] = (40, 120, 200)
    for i in range(8):
        ink(21 + 9 * i, 12, 23 + 9 * i, 14.5)
    if markers:
        for x in np.arange(19.0, 95.0, 3.0):          # top and bottom edges
            ink(x, edge, x + 0.2, edge + length)
            ink(x, size[1] - edge - length, x + 0.2, size[1] - edge)
        for y in np.arange(17.0, 137.0, 3.0):         # the sides
            ink(edge, y, edge + length, y + 0.2)
            ink(size[0] - edge - length, y, size[0] - edge, y + 0.2)
    for box in extra:
        ink(*box)
    p = tmp_path / f"{name}_01.tif"
    Image.fromarray(a).save(p, dpi=(dpi, dpi))
    lay = {"engine": "chromiq"}
    if recipe:
        lay["recipe"] = {"instrument": "i1", "helper_markers": bool(markers),
                         "helper_marker_edge": edge, "helper_marker_len": length}
    (tmp_path / f"{name}.channels.json").write_text(json.dumps({"layout": lay}),
                                                    encoding="utf-8")
    return p


def _plan_card(p, paper=POSTCARD):
    pt = (100.0 / O.MM_PER_PT, 150.0 / O.MM_PER_PT)
    return O.plan_for_chart([(p, 0)], pt, (paper[0] / O.MM_PER_PT,
                                            paper[1] / O.MM_PER_PT))


def test_the_ruler_markers_are_found_as_the_engine_draws_them(tmp_path):
    p = _engine_page(tmp_path, "m")
    mk = O.helper_markers(p)
    assert set(mk) == {"top", "bottom", "left", "right"}
    assert len(mk["top"]) == len(np.arange(19.0, 95.0, 3.0))
    assert len(mk["left"]) == len(np.arange(17.0, 137.0, 3.0))


def test_a_card_whose_ruler_marks_reach_the_cut_prints_on_a_postcard(tmp_path):
    """Knut's 10 x 15 cm card on 100 x 148 mm (agent 20 refused it, the marks
    sit 0.5 mm from the edge here): they may be cut, the rest stays."""
    p = _engine_page(tmp_path, "k", edge=0.5)
    plan = _plan_card(p)
    assert plan.safe, plan.reason
    assert plan.markers_cut.get("top") and plan.markers_cut.get("bottom")
    assert "left" not in plan.markers_cut          # 100 mm wide: nothing off


def test_without_the_recipe_the_same_marks_are_content(tmp_path):
    p = _engine_page(tmp_path, "n", edge=0.5, recipe=False)
    assert O.helper_markers(p) == {}
    plan = _plan_card(p)
    assert not plan.safe and plan.reason == "content"


def test_anything_else_at_the_edge_is_still_content(tmp_path):
    """A note or a stamp 0.5 mm from the top and bottom edges is not a ruler
    mark, so there is nowhere to put the cut."""
    p = _engine_page(tmp_path, "s", edge=0.5,
                     extra=[(40.0, 148.6, 70.0, 149.5), (40.0, 0.5, 70.0, 1.4)])
    plan = _plan_card(p)
    assert not plan.safe and plan.reason == "content"


def test_a_mark_that_crosses_other_ink_is_not_recognised(tmp_path):
    p = _engine_page(tmp_path, "x", edge=0.5, extra=[(30.0, 0.5, 34.0, 2.5)])
    mk = O.helper_markers(p)
    assert all(not (29.5 < b.left < 34.5) for b in mk["top"])
    assert not _plan_card(p).safe


def test_the_log_line_says_which_marks_were_cut(tmp_path):
    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from types import SimpleNamespace
    from ui.tabs.tab_print import TabPrint
    p = _engine_page(tmp_path, "l", edge=0.5)
    plan = _plan_card(p)
    status = []
    fake = SimpleNamespace(_set_status=status.append,
                           _pending_print_record=("rec", {}))
    TabPrint._note_overhang(fake, plan)
    assert "ruler marks cut:" in status[0] and "at the top" in status[0]
    assert fake._pending_print_record[1]["ruler_marks_outside_paper"]["top"] > 0


def test_the_dialog_routes_still_refuse_what_matters(tmp_path):
    """Basti: no "print anyway" on the Windows or macOS dialog route; their
    refusal says nothing was printed."""
    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from ui.tabs.tab_print import TabPrint
    p = _engine_page(tmp_path, "r", edge=0.5,
                     extra=[(40.0, 148.6, 70.0, 149.5), (40.0, 0.5, 70.0, 1.4)])
    plan = _plan_card(p)
    paper = (POSTCARD[0] / O.MM_PER_PT, POSTCARD[1] / O.MM_PER_PT)
    title, body = TabPrint._overhang_text(plan, p, paper, anyway=False)
    assert "Nothing was printed." in body and "print anyway" not in body
    assert "ruler marks" in body                   # what may be cut, said


def test_the_print_record_keeps_what_was_cut(tmp_path):
    """Found on screen by agent 22: the record refused the two new keys and
    the print crashed in its slot after the job was sent."""
    import json
    from workflow import verification_print as vp
    ti2 = tmp_path / "c.ti2"
    ti2.write_text("CTI2\n", encoding="utf-8")
    path = vp.write_print_record(
        ti2, colour=vp.COLOUR_RAW if hasattr(vp, "COLOUR_RAW") else "raw",
        intent="", profile=None, route="chromiq",
        outside_paper_mm={"top": 2.2}, caption_outside_paper_mm={"top": 2.2},
        ruler_marks_outside_paper={"top": 12})
    rec = json.loads(path.read_text(encoding="utf-8"))
    assert rec["caption_outside_paper_mm"] == {"top": 2.2}
    assert rec["ruler_marks_outside_paper"] == {"top": 12}


def test_every_key_the_direct_route_notes_is_one_the_record_takes(tmp_path):
    import inspect
    from workflow import verification_print as vp
    from ui.tabs import tab_print
    params = inspect.signature(vp.write_print_record).parameters
    src = inspect.getsource(tab_print.TabPrint._note_overhang)
    import re
    for key in re.findall(r'pending\[1\]\["(\w+)"\]', src):
        assert key in params, key
