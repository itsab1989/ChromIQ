"""The Barbieri Spectro 100xy chart (a Beta): geometry, grid numbers, marks,
check patches, reading order and the ready-made sizes.

The acceptance numbers come from an owner's real Spectro32 template: a 32 x 28
chart of 6.5 mm patches, read in one run of 896 patches, whose template line
was ``R0,0,2015,1755,32,28`` (spans from the first centre to the last, 0.1 mm).
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from tests._barbieri_fixture import barbieri_on, write_ti1


@pytest.fixture(autouse=True)
def _on():
    with barbieri_on():
        yield


def _build(tmp_path, n=896, **over):
    from workflow.layout_engine import presets
    from workflow.layout_engine.chart import build_chart
    ti1 = write_ti1(tmp_path / "c.ti1", n)
    paper = over.pop("paper", "A4R")
    kw = presets.default_recipe("B100XY", paper).build_kwargs()
    kw.update(over)
    res = build_chart(ti1, tmp_path / "c", **kw)
    doc = json.loads((tmp_path / "c.barbieri.json").read_text(encoding="utf-8"))
    return res, doc


def _owner_margins():
    """Margins that hold exactly 32 x 28 patches of 6.5 mm on A4 landscape
    (208 x 182 mm, with 0.1 mm to spare on the right and the bottom)."""
    return (10.0, 297.0 - 15.0 - 208.0 - 0.1, 210.0 - 10.0 - 182.0 - 0.1, 15.0)


def test_the_owners_chart_gives_his_template_line(tmp_path):
    res, doc = _build(tmp_path, 896, margins=_owner_margins(),
                      patch_w=6.5, patch_h=6.5)
    pg = doc["pages_detail"][0]
    assert (pg["columns"], pg["rows"]) == (32, 28)
    assert pg["spectro32"] == "R0,0,2015,1755,32,28"
    from workflow.barbieri import chart_facts as F
    assert pg["spectro32"] == F.OWNER_TEMPLATE.value[3]
    gw = pg["gateway"]
    assert (gw["patches_x"], gw["patches_y"]) == (32, 28)
    assert (gw["size_x_mm"], gw["size_y_mm"]) == (208, 182)
    assert gw["exact"] is True
    assert pg["aim_patch"] == "AF1"
    assert pg["first_patch"] == "A1"
    assert doc["reading_minutes"] == 28        # 896 x 1.9 s
    assert res.layout.padding == 0


def test_spectro32_line_is_centre_to_centre_in_tenths():
    from workflow.barbieri.chart import gateway_numbers, spectro32_line
    assert spectro32_line(32, 28, 6.5, 6.5) == "R0,0,2015,1755,32,28"
    assert spectro32_line(36, 23, 1.0, 1.0) == "R0,0,350,220,36,23"
    assert spectro32_line(1, 1, 6.5, 6.5) == "R0,0,0,0,1,1"
    g = gateway_numbers(30, 24, 7.5, 7.5)
    assert (g["size_x_mm"], g["size_y_mm"], g["exact"]) == (225, 180, True)
    assert gateway_numbers(31, 29, 6.5, 6.5)["exact"] is False


def test_no_run_up_the_first_patch_sits_at_the_top_margin(tmp_path):
    """Unlike the SpectroScan entry (6 + 2 mm band in patch-first), the
    Barbieri grid starts exactly at the margins typed."""
    _res, doc = _build(tmp_path, 200, margins=(1.0, 10.0, 10.0, 15.0))
    left, top, _r, _b = doc["pages_detail"][0]["grid_mm"]
    assert top == pytest.approx(1.0, abs=1e-6)
    assert left == pytest.approx(15.0, abs=1e-6)


def test_reading_order_is_row_by_row_and_names_match_the_ti2(tmp_path):
    _res, doc = _build(tmp_path, 300)
    pg = doc["pages_detail"][0]
    order = pg["reading_order"]
    cols, rows = pg["columns"], pg["rows"]
    assert len(order) == cols * rows == len(set(order))
    strips = json.loads((tmp_path / "c.strips.json").read_text(encoding="utf-8"))
    at = {p["loc"]: (p["x"], p["y"]) for p in strips["patches"]}
    pos = [at[name] for name in order]
    for r in range(rows):
        row = pos[r * cols:(r + 1) * cols]
        assert len({y for _x, y in row}) == 1, "a row is one line"
        assert [x for x, _y in row] == sorted(x for x, _y in row)
        if r:
            assert row[0][1] > pos[(r - 1) * cols][1], "rows go down"
    assert order[:3] == ["A1", "B1", "C1"]
    assert order[cols] == "A2"
    ti2 = (tmp_path / "c.ti2").read_text(encoding="utf-8")
    for name in order:
        assert f' "{name}" ' in ti2


def test_the_corner_marks_lie_on_the_grid_edges_in_the_margins(tmp_path):
    from workflow.barbieri import chart as C
    _res, doc = _build(tmp_path, 300)
    pg = doc["pages_detail"][0]
    left, top, right, bottom = pg["grid_mm"]
    grid = C.PageGrid(page=0, cols=pg["columns"], rows=pg["rows"],
                      first_slot=0, steps=pg["rows"], pitch_x=6.5,
                      pitch_y=6.5, patch_w=6.5, patch_h=6.5, left=left,
                      top=top, right=right, bottom=bottom, paper_w=297.0,
                      paper_h=210.0)
    plan = C.plan_marks(grid)
    assert not plan.left_out
    for (a, b, c, d) in plan.rects:
        inside_x = a < right - 1e-6 and c > left + 1e-6
        inside_y = b < bottom - 1e-6 and d > top + 1e-6
        assert not (inside_x and inside_y), "a mark on the patch grid"
        assert 0 <= a and 0 <= b and c <= 297.0 and d <= 210.0
    xs = {round(v, 4) for r in plan.rects for v in (r[0], r[2])}
    ys = {round(v, 4) for r in plan.rects for v in (r[1], r[3])}
    for edge in (left, right):
        assert round(edge, 4) in xs
    for edge in (top, bottom):
        assert round(edge, 4) in ys
    # the two aim ticks cross at the upper-right patch's centre
    cx, cy = pg["aim_centre_mm"]
    vertical = [r for r in plan.rects
                if abs((r[0] + r[2]) / 2 - cx) < 1e-6 and r[3] <= top]
    horizontal = [r for r in plan.rects
                  if abs((r[1] + r[3]) / 2 - cy) < 1e-6 and r[0] >= right]
    assert vertical and horizontal
    # the upper-right corner is the bold one
    t = C.F.MARK_LINE_MM.value
    widths = [round(r[2] - r[0], 4) for r in plan.rects if r[0] >= right - 1e-6
              and r[3] <= top + 1e-6 and r[2] - r[0] < 2]
    assert round(t * C.F.MARK_BOLD_FACTOR.value, 4) in widths


def test_the_marks_are_printed_on_every_page_and_only_in_the_margins(tmp_path):
    from PIL import Image
    res, doc = _build(tmp_path, 1500)
    assert doc["pages"] == 2 == len(res.tiff_paths)
    for path, pg in zip(sorted(res.tiff_paths), doc["pages_detail"]):
        im = Image.open(path).convert("L")
        s = 300 / 25.4
        left, top, right, bottom = pg["grid_mm"]
        # ink just above the upper-right corner (the bold arm)
        x = int(right * s) + 2
        col = [im.getpixel((x, y)) for y in range(int((top - 4) * s),
                                                   int(top * s) - 1)]
        assert min(col) < 60, f"no aim corner on page {pg['page']}"
        # ink left of A1's centre row (the start square)
        _cx, cy = (left, top + 3.25)
        row = [im.getpixel((xx, int(cy * s)))
               for xx in range(int((left - 3) * s), int(left * s) - 1)]
        assert min(row) < 60, f"no start square on page {pg['page']}"


def test_check_patches_are_in_their_places_and_the_set_is_unchanged(tmp_path):
    from workflow.layout_engine import ti1_reader
    from workflow.barbieri.chart import patch_labs
    _res, doc = _build(tmp_path, 300)
    target = ti1_reader.read_ti1(tmp_path / "c.ti1")
    labs = patch_labs(target)
    checks = {c["role"]: c for c in doc["pages_detail"][0]["check_patches"]}
    assert set(checks) == {"first", "aim", "lower_left", "right_of_first",
                           "below_first"}
    assert checks["first"]["patch"] == "A1"
    assert checks["aim"]["patch"] == doc["pages_detail"][0]["aim_patch"]
    assert checks["first"]["lab"][0] == pytest.approx(min(L[0] for L in labs),
                                                      abs=0.01)
    assert checks["lower_left"]["lab"][0] == pytest.approx(
        max(L[0] for L in labs), abs=0.01)
    # only positions moved: the .ti2 holds exactly the .ti1's patches
    text = (tmp_path / "c.ti2").read_text(encoding="utf-8")
    body = text.split("BEGIN_DATA\n", 1)[1].split("END_DATA", 1)[0]
    rows = [ln.split() for ln in body.strip().splitlines()]
    got = sorted(tuple(round(float(v), 3) for v in r[2:5]) for r in rows)
    assert all(r[1].startswith('"') for r in rows)
    want = sorted(tuple(round(float(v), 3) for v in dev)
                  for dev, _xyz in target.patches)
    pad = len(got) - len(want)
    assert got.count((100.0, 100.0, 100.0)) >= pad
    for p in want:
        got.remove(p)
    assert all(p == (100.0, 100.0, 100.0) for p in got)


def test_check_patches_off_keeps_the_engines_order(tmp_path):
    from workflow.layout_engine import permutation
    res, doc = _build(tmp_path, 300, barbieri_check_patches=False, seed=11)
    assert doc["check_patches_on"] is False
    assert res.slots is None
    _res2, doc2 = _build(tmp_path, 300, seed=11)
    assert doc2["check_patches_on"] is True
    del permutation


def test_a_size_with_more_decimals_is_rounded_and_said(tmp_path):
    res, doc = _build(tmp_path, 200, patch_w=6.55, patch_h=6.55)
    assert doc["patch_mm"] == [6.6, 6.6]
    assert any("6.6" in w and "0.1 mm" in w for w in res.warnings)


def test_more_than_99_columns_are_capped_and_said(tmp_path):
    res, doc = _build(tmp_path, 10000, patch_w=1.0, patch_h=1.0,
                      margins=(10.0, 10.0, 10.0, 15.0))
    pg = doc["pages_detail"][0]
    assert pg["columns"] == 99
    assert pg["rows"] == 99
    assert doc["pages"] == 2
    assert doc["pages_detail"][1]["rows"] == 99
    assert any("99" in w for w in res.warnings)
    # a chart that does not reach the cap is not told about it
    res2, doc2 = _build(tmp_path, 3000, patch_w=1.0, patch_h=1.0,
                        margins=(10.0, 10.0, 10.0, 15.0))
    assert doc2["pages_detail"][0]["columns"] < 99
    assert not any("Gateway reads at most" in w for w in res2.warnings)


def test_a_patch_too_small_for_the_opening_is_warned_not_refused(tmp_path):
    res, _doc = _build(tmp_path, 100, patch_w=0.8, patch_h=0.8,
                       barbieri_head="transmission-0.5")
    assert any("0.25 mm" in w for w in res.warnings)
    res2, _doc2 = _build(tmp_path, 100, patch_w=1.0, patch_h=1.0,
                         barbieri_head="transmission-0.5")
    assert not any("0.25 mm" in w for w in res2.warnings)


def test_side_file_holds_the_ti2_checksum_and_the_opening(tmp_path):
    _res, doc = _build(tmp_path, 120, barbieri_head="transmission-3")
    digest = hashlib.sha256((tmp_path / "c.ti2").read_bytes()).hexdigest()
    assert doc["ti2_sha256"] == digest
    assert doc["head"] == "transmission-3"
    assert doc["spectro32_mode"] == "MT"
    assert "CHROMIQ_BARBIERI_HEAD" in (tmp_path / "c.ti2").read_text(encoding="utf-8")
    assert 'TARGET_INSTRUMENT "Barbieri Spectro 100xy"' in (
        tmp_path / "c.ti2").read_text(encoding="utf-8")


@pytest.mark.parametrize("key,cols,rows", [
    ("a4", 36, 28), ("letter", 36, 30), ("standard", 30, 24),
    ("full", 36, 30)])
def test_every_size_preset_gives_its_patch_area(tmp_path, key, cols, rows):
    from workflow.barbieri.chart import size_preset
    p = size_preset(key)
    res, doc = _build(tmp_path, cols * rows, paper=p.paper,
                      margins=p.margins, patch_w=p.patch_mm,
                      patch_h=p.patch_mm, barbieri_head=p.head,
                      barbieri_size=p.key)
    pg = doc["pages_detail"][0]
    assert (pg["columns"], pg["rows"]) == (cols, rows)
    assert doc["pages"] == 1
    aw, ah = pg["patch_area_mm"]
    assert aw <= 235.0 and ah <= 200.0
    left = pg["grid_mm"][0]
    assert left >= 15.0 - 1e-6           # the left border kept
    if key == "standard":
        assert (aw, ah) == (pytest.approx(225.0), pytest.approx(180.0))
    # every ready-made size gives exact numbers to both programs: spans in
    # whole 0.1 mm (Spectro32) and a target size in whole mm (Gateway)
    assert pg["gateway"]["exact"], pg["gateway"]
    assert doc["size_preset"] == key


@pytest.mark.parametrize("key,cols,rows", [("film_35", 36, 23),
                                           ("film_large", 34, 28)])
def test_the_film_presets_need_and_use_the_page_beta(tmp_path, key, cols,
                                                    rows):
    from workflow.page_output import support as po
    from workflow.barbieri.chart import size_preset
    p = size_preset(key)
    assert p.needs_page_beta
    before = po._latched
    po.set_enabled_for_this_process(True)
    try:
        if key == "film_large":
            # the 2032 ppi page is large: the grid is what is checked here
            from workflow.layout_engine import geometry, instruments, presets
            kw = presets.default_recipe("B100XY", "A4R").build_kwargs()
            kw.update(margins=p.margins, patch_w=p.patch_mm,
                      patch_h=p.patch_mm, barbieri_head=p.head,
                      page_size=p.page_size, dpi=p.dpi)
            w, h = po.page_mm(po.clean_page_size(p.page_size), p.dpi)
            kw["paper"] = po.paper_code(w, h)
            g = instruments.geom_from_build_kwargs(kw)
            lay = geometry.compute(g, w, h, cols * rows)
            assert (lay.patches_per_page // lay.steps_in_pass,
                    lay.steps_in_pass) == (cols, rows)
            from workflow.barbieri.chart import gateway_numbers
            assert gateway_numbers(cols, rows, 6.5, 6.5)["exact"]
            return
        w, h = po.page_mm(po.clean_page_size(p.page_size), p.dpi)
        res, doc = _build(tmp_path, cols * rows, paper=po.paper_code(w, h),
                          margins=p.margins, patch_w=p.patch_mm,
                          patch_h=p.patch_mm, barbieri_head=p.head,
                          page_size=p.page_size, dpi=p.dpi,
                          tiff_res_unit="in")
        pg = doc["pages_detail"][0]
        assert (pg["columns"], pg["rows"]) == (cols, rows)
        assert pg["spectro32"] == "R0,0,350,220,36,23"
        assert pg["gateway"]["exact"]
        assert doc["spectro32_mode"] == "M5"
        # 1 mm margins still carry the corner marks, drawn thinner
        assert doc["marks_on"] is True
        assert not any("too narrow" in w for w in res.warnings), res.warnings
    finally:
        po._latched = before


def test_field_defaults_agree():
    from workflow.barbieri.chart import FIELD_DEFAULTS
    from workflow.layout_engine.presets import BARBIERI_FIELD_DEFAULTS
    assert FIELD_DEFAULTS == BARBIERI_FIELD_DEFAULTS


def test_the_recipe_keeps_the_options_only_for_a_barbieri_recipe():
    from workflow.layout_engine.presets import LayoutRecipe, default_recipe
    r = default_recipe("B100XY", "A4R")
    r.barbieri_head = "transmission-0.5"
    r.barbieri_check_patches = False
    r.barbieri_marks = False
    r.barbieri_size = "film_35"
    d = r.to_dict()
    back = LayoutRecipe.from_dict(d)
    for f in ("barbieri_head", "barbieri_check_patches", "barbieri_marks",
              "barbieri_size"):
        assert getattr(back, f) == getattr(r, f)
        assert f in r.build_kwargs()
    back2 = LayoutRecipe.from_build_kwargs(r.build_kwargs())
    assert back2.barbieri_head == "transmission-0.5"
    other = LayoutRecipe(instrument="i1")
    other.barbieri_head = "transmission-0.5"
    assert not any(k.startswith("barbieri") for k in other.to_dict())
    assert not any(k.startswith("barbieri") for k in other.build_kwargs())


def test_default_margins_keep_the_patch_area_in_the_reading_area():
    from workflow.barbieri.chart import default_margins
    assert default_margins(297.0, 210.0) == (10.0, 47.0, 10.0, 15.0)
    t, r, b, l_ = default_margins(210.0, 297.0)
    assert l_ == 15.0 and 297.0 - t - b <= 200.0 + 1e-9


def test_marks_fit_a_one_millimetre_margin():
    from workflow.barbieri import chart as C
    g = C.PageGrid(page=0, cols=36, rows=23, first_slot=0, steps=23,
                   pitch_x=1.0, pitch_y=1.0, patch_w=1.0, patch_h=1.0,
                   left=1.0, top=1.0, right=37.0, bottom=24.0, paper_w=38.1,
                   paper_h=25.4)
    plan = C.plan_marks(g)
    assert plan.left_out == []
    for (a, b, c, d) in plan.rects:
        assert 0 <= a and 0 <= b and c <= 38.1 and d <= 25.4
        assert not (a < 37.0 and c > 1.0 and b < 24.0 and d > 1.0)


def test_guided_offers_only_the_film_frames_for_the_half_millimetre_opening():
    from workflow.barbieri import chart as C
    films = C.guided_papers("transmission-0.5")
    assert films == tuple(C.film_paper_code(k) for k in C.GUIDED_FILM_SIZES)
    assert not set(films) & set(C.GUIDED_PAPERS)
    for code in films:
        assert C.guided_paper_label(code)
    for head in ("reflection-3", "transmission-3", "reflection-6", ""):
        assert C.guided_papers(head) == C.GUIDED_PAPERS


def test_guided_kwargs_on_a_film_frame_take_the_frames_own_page():
    from workflow.barbieri import chart as C
    from workflow.page_output import support as po
    code = C.film_paper_code("film_35")
    before = po._latched
    try:
        po.set_enabled_for_this_process(True)
        kw = C.guided_kwargs(code, "transmission-0.5")
        assert kw["margins"] == (1.0, 1.0, 1.0, 1.0)
        assert kw["page_size"]["w"] == [4096, "px"] and kw["dpi"] == 2731
        assert kw["patch_w"] == 1.0
        po.set_enabled_for_this_process(False)
        assert "page_size" not in C.guided_kwargs(code, "transmission-0.5")
    finally:
        po._latched = before
