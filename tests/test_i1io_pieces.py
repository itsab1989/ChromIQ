"""AN i1iO CHART ON A SHEET LARGER THAN THE TABLE (the new chart layout, step 5).

Which pieces a sheet is divided into; that everything that lays the chart out
gets the piece and everything that names the paper the sheet; the three counts
(patches of a sheet, pieces, sheets); and THE RECORD: what Generate decided is
stored with the chart and read from there, whatever a later rule would decide.
"""
from __future__ import annotations

import ast
import json
import re
from dataclasses import replace
from pathlib import Path

import pytest

from workflow.i1io import chart as C
from workflow.i1io import pieces as P
from workflow.i1io import table_facts as F
from workflow.layout_engine import papers

ROOT = Path(__file__).resolve().parent.parent
A3 = "v1;sheet=297x420;piece=210x297;turn=1;at=0,0/0,210;cut_x=;cut_y=210"


@pytest.fixture(autouse=True)
def i1io_on():
    from workflow.i1io import support
    before = support._latched
    support.set_enabled_for_this_process(True)
    try:
        yield
    finally:
        support._latched = before


def _ti1(path, n):
    from tests.test_i1io_chart import _ti1 as t
    return t(path, n)


# ---- the division --------------------------------------------------------------------

@pytest.mark.parametrize("w,h,n,piece,standard,compact", [
    (210, 297, None, None, 528, 638), (230, 320, None, None, 624, 768),
    (210, 320, None, None, 572, 704), (216, 310, None, None, 575, 690),
    (215.9, 279.4, None, None, 506, 621),
    (215.9, 355.6, 1, (210, 297), 528, 638),
    (297, 420, 2, (210, 297), 1056, 1276),
    (279.4, 431.8, 2, (215.9, 279.4), 1012, 1242),
    (329, 483, 2, (210, 297), 1056, 1276),
    (330.2, 482.6, 2, (210, 297), 1056, 1276),
    (257, 364, 2, (182, 257), 720, 900),
    (279.4, 355.6, 2, (177.8, 279.4), 792, 972),
    (304.8, 457.2, 2, (210, 297), 1056, 1276),
    (420, 594, 4, (210, 297), 2112, 2552),
    (431.8, 558.8, 4, (215.9, 279.4), 2024, 2484),
    (594, 841, 8, (210.25, 297), 4224, 5104),
    (609.6, 594, 6, (203.2, 297), 3024, 3654)])
def test_the_pieces_of_a_sheet(w, h, n, piece, standard, compact):
    """The design's table 3.2, each sheet either way round."""
    for sheet in ((w, h), (h, w)):
        plan = P.plan_for(sheet)
        assert (plan.count if plan else None) == n
        src = {"instrument": "IO2", "paper": f"{sheet[0]}x{sheet[1]}",
               "i1io_limits": 2}
        if plan is not None:
            assert plan.piece_mm == pytest.approx(piece)
            assert papers.piece_mm_of(src) == plan.piece_mm
        elif sheet[0] > sheet[1]:
            continue                      # a lying one-piece sheet is refused
        from workflow.layout_engine import geometry, instruments
        for kw, want in (({}, standard), ({"patch_h": 8.0, "patch_w": 8.0},
                                          compact)):
            g = instruments.geom_from_build_kwargs({**src, **kw})
            per = geometry.patches_per_sheet(g, *papers.piece_mm_of(src))
            assert papers.patches_on_a_sheet(per, src) == want, (sheet, kw)


def test_the_large_pieces_wait_for_their_sign_off(monkeypatch):
    """With the one constant True the sheets of the table's last column change,
    and the one-page sheets do not."""
    before = {s: P.plan_for(s) for s in ((210.0, 297.0), (230.0, 320.0),
                                         (297.0, 420.0), (420.0, 594.0))}
    monkeypatch.setattr(F, "LARGE_PIECES", True)
    assert {s: P.plan_for(s) for s in before} == before
    for sheet, n, piece in (((329.0, 483.0), 2, (241.5, 329.0)),
                            ((257.0, 364.0), 1, None),
                            ((304.8, 457.2), 2, (228.6, 304.8))):
        plan = P.plan_for(sheet)
        assert plan.count == n
        if piece:
            assert plan.piece_mm == pytest.approx(piece)


@pytest.mark.parametrize("sheet", [(297.0, 420.0), (420.0, 297.0),
                                   (420.0, 594.0), (329.0, 483.0),
                                   (594.0, 841.0), (215.9, 355.6)])
def test_the_places_tile_the_sheet(sheet):
    plan = P.plan_for(sheet)
    cw, ch = plan.cell_mm
    rects = [(x, y, x + cw, y + ch) for x, y in plan.places]
    assert len(set(plan.places)) == plan.count
    for i, a in enumerate(rects):
        assert a[0] >= 0 and a[1] >= 0
        assert a[2] <= sheet[0] + 0.02 and a[3] <= sheet[1] + 0.02
        for b in rects[i + 1:]:
            assert a[2] <= b[0] + 0.01 or b[2] <= a[0] + 0.01 \
                or a[3] <= b[1] + 0.01 or b[3] <= a[1] + 0.01
    # every edge of a piece inside the sheet is a cut line, and nothing else is
    xs = {round(v, 2) for r in rects for v in (r[0], r[2])
          if 0.02 < v < sheet[0] - 0.02}
    ys = {round(v, 2) for r in rects for v in (r[1], r[3])
          if 0.02 < v < sheet[1] - 0.02}
    assert {round(v, 2) for v in plan.cut_x} == xs
    assert {round(v, 2) for v in plan.cut_y} == ys
    # points there and back
    for page in range(plan.count * 2):
        for pt in ((0.0, 0.0), (11.0, 40.0), plan.piece_mm):
            x, y = plan.to_sheet(page, *pt)
            assert plan.from_sheet(page % plan.count, x, y) == \
                pytest.approx(pt)
    assert P.from_token(plan.token) == plan


def test_the_pieces_are_numbered_as_they_are_read():
    """Held so that its pieces read upright (they read a quarter turn clockwise
    on the portrait page): left to right, then down."""
    up = P.plan_for((297.0, 420.0))               # its pieces lie: as it is
    assert up.places == ((0.0, 0.0), (0.0, 210.0)) and up.turn == 1
    a2 = P.plan_for((420.0, 594.0))               # read turned clockwise
    W, H = a2.sheet_mm
    cw, ch = a2.cell_mm
    seen = [(H - (y + ch), x) for x, y in a2.places]
    assert seen == sorted(seen, key=lambda p: (p[1], p[0]))


@pytest.mark.parametrize("token", ["", "one", "v1", "v1;sheet=1x1", "nonsense",
                                   A3 + ";x", A3.replace("turn=1", "turn=7"),
                                   A3.replace("210x297", "0x297")])
def test_a_bad_token_is_no_plan(token):
    got = P.from_token(token)
    assert got is None
    if token in ("", "one"):
        assert P.plan_for((210.0, 297.0), token) is None
    else:
        with pytest.raises(P.PieceRecordError):
            P.plan_for((210.0, 297.0), token)
    assert P.plan_for((297.0, 420.0), "one") is None


def test_a_stored_division_is_of_one_sheet():
    """The record of one sheet divides no other (the review of step 5: a
    foreign record is refused, `tests/test_i1io_pieces_record.py`)."""
    for other in ((420.0, 594.0), (210.0, 297.0)):
        with pytest.raises(P.PieceRecordError):
            P.plan_for(other, A3)


# ---- who is ever divided -------------------------------------------------------------

def test_only_an_i1io_layout_with_the_marker_is_divided():
    src = {"instrument": "IO2", "paper": "A3", "i1io_limits": 2}
    assert papers.piece_mm_of(src) == (210.0, 297.0)
    assert papers.pieces_on(src) == 2 and papers.sheets_of(3, src) == 2
    for other in ({**src, "i1io_limits": 0}, {**src, "i1io_pieces": "one"},
                  {k: v for k, v in src.items() if k != "i1io_limits"},
                  {**src, "paper": "A4"}, {**src, "instrument": "i1"}):
        assert papers.piece_mm_of(other) == papers.dimensions_mm(other["paper"])
        assert papers.pieces_on(other) == 1
        assert papers.sheets_of(3, other) == 3
    from workflow.i1io import support
    support.set_enabled_for_this_process(False)
    assert papers.piece_mm_of(src) == (297.0, 420.0)
    assert papers.pieces_on(src) == 1


def test_other_instruments_never_import_the_pieces(monkeypatch):
    import sys
    for name in ("workflow.i1io.pieces",):
        monkeypatch.delitem(sys.modules, name, raising=False)
    for i in ("i1", "p3", "CM", "SS", "CR30", "", None):
        papers.piece_mm_of({"instrument": i, "paper": "A3"})
        papers.patches_on_a_sheet(5, {"instrument": i, "paper": "A3"})
        papers.sheets_of(5, {"instrument": i, "paper": "A3"})
    assert "workflow.i1io.pieces" not in sys.modules


def test_an_old_recipe_on_a_large_sheet_is_refused_as_before(tmp_path):
    from workflow.layout_engine import chart
    with pytest.raises(C.I1ioSheetRefused, match="larger than the area"):
        chart.build_chart(_ti1(tmp_path / "c.ti1", 60), tmp_path / "c",
                          instrument="IO2", paper="A3", dpi=72, seed=1,
                          chart_date="x")
    assert sorted(p.name for p in tmp_path.iterdir()) == ["c.ti1"]


def test_a_size_in_pixels_is_refused_and_one_in_inches_divided(tmp_path,
                                                             monkeypatch):
    from workflow.layout_engine import chart
    from workflow.page_output import support as po
    monkeypatch.setattr(po, "page_output_enabled", lambda: True)
    kw = dict(instrument="IO2", dpi=72, seed=1, chart_date="x", i1io_limits=2)
    with pytest.raises(C.I1ioSheetRefused, match="typed in pixels"):
        chart.build_chart(
            _ti1(tmp_path / "p.ti1", 60), tmp_path / "p", paper="297x420",
            page_size=po.make_page_size((842, "px"), (420.0, "mm"), 72), **kw)
    r = chart.build_chart(
        _ti1(tmp_path / "i.ti1", 60), tmp_path / "i", paper="330.2x482.6",
        page_size=po.make_page_size((13.0, "in"), (19.0, "in"), 72), **kw)
    plan = P.from_token(r.i1io_pieces)
    assert plan.piece_mm == (210.0, 297.0) and plan.count == 2


# ---- the build -----------------------------------------------------------------------

def _build(tmp_path, paper, n=1100, **kw):
    from workflow.layout_engine import chart
    from workflow.layout_engine.presets import default_recipe
    k = default_recipe("IO2", paper).build_kwargs()
    k.update(dpi=72, seed=1, chart_date="x", **kw)
    return chart.build_chart(_ti1(tmp_path / "c.ti1", n), tmp_path / "c", **k)


@pytest.mark.parametrize("paper,turn", [("A3", 1), ("420x297", 0)])
def test_a_divided_chart_is_its_pieces(tmp_path, paper, turn):
    from PIL import Image
    r = _build(tmp_path, paper)
    assert r.layout.pages == 3 and r.layout.patches_per_page == 528
    assert len(r.tiff_paths) == 3
    for t in r.tiff_paths:
        with Image.open(t) as im:
            assert im.size == (round(210 / 25.4 * 72), round(297 / 25.4 * 72))
    side = json.loads((tmp_path / "c.i1io.json").read_text(encoding="utf-8"))
    assert side["schema"] == 2 and side["paper"] == paper
    assert side["paper_mm"] == [210.0, 297.0]
    assert side["sheet"]["pieces"] == 2 and side["sheet"]["sheets"] == 2
    assert [(p["piece"]["sheet"], p["piece"]["piece"], p["piece"]["turn"])
            for p in side["pages"]] == [(1, 1, turn), (1, 2, turn),
                                        (2, 1, turn)]
    text = (tmp_path / "c.ti2").read_text(encoding="utf-8")
    assert f'{P.KEYWORD} "{r.i1io_pieces}"' in text
    assert f'KEYWORD "{P.KEYWORD}"' in text
    assert 'PAPER_SIZE "210.0x297.0"' in text
    strips = json.loads((tmp_path / "c.strips.json").read_text("utf-8"))
    assert strips["paper_mm"] == [210.0, 297.0]


def test_its_pieces_are_the_a4_charts_pages(tmp_path):
    """A piece of A3 is laid out exactly as an A4 page: the same patches at the
    same millimetres."""
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    _build(tmp_path / "a", "A3")
    _build(tmp_path / "b", "A4")
    a, b = (json.loads((tmp_path / d / "c.i1io.json").read_text("utf-8"))
            for d in "ab")
    assert len(a["pages"]) == len(b["pages"]) == 3
    for p, q in zip(a["pages"], b["pages"]):
        assert p["strips"] == q["strips"]
        assert p["aim_points"] == q["aim_points"]
    for k in ("patch_mm", "spacer_mm", "strip_gap_mm"):
        assert a[k] == b[k]


def test_a_one_piece_chart_carries_none_of_it(tmp_path):
    r = _build(tmp_path, "A4", n=60)
    assert r.i1io_pieces == ""
    side = json.loads((tmp_path / "c.i1io.json").read_text(encoding="utf-8"))
    assert side["schema"] == 1 and "sheet" not in side
    assert "piece" not in side["pages"][0]
    assert P.KEYWORD not in (tmp_path / "c.ti2").read_text(encoding="utf-8")


def test_the_second_pass_gets_what_the_first_one_settled():
    """`build_chart` hands its geometry a dict of named keys (`_geom_kw`): every
    i1iO key the sizes were settled with is in it, or the sheet is laid out."""
    from workflow.layout_engine import chart
    src = Path(chart.__file__).read_text(encoding="utf-8")
    body = src[src.index("    def _geom_kw(npat"):]
    body = body[:body.index("    w_mm, h_mm = papers.dimensions_mm(paper)")]
    for key in ("_i1io_chart.LIMITS_KEY", "_i1io_pc.PIECES_KEY",
                "_i1io_chart.CROSSES_KEY", "_i1io_chart.CLIP_KEY",
                "_i1io_chart.ALIGN_KEY", "_i1io_chart.LABELS_KEY",
                "_i1io_chart.NUMBERS_EDGE_KEY"):
        assert key in body, key
    once = C.fixed_build_kwargs({"instrument": "IO2", "paper": "A3",
                                 "i1io_limits": 2})
    assert once[P.PIECE_MM_KEY] == (210.0, 297.0)
    assert once[P.PIECES_KEY] == A3
    assert C.fixed_build_kwargs(once) == once
    assert P.PIECE_MM_KEY not in C.fixed_build_kwargs(
        {"instrument": "IO2", "paper": "A4", "i1io_limits": 2})


# ---- the record: stored with the chart, read from there ----------------------------------

def _generate(tmp_path, paper="A3", manual=True, **recipe):
    """Generate as the app does it: the kwargs, the build, the sidecars."""
    import _i1io_baseline as base
    from workflow.chart_creator import ChartParams
    from workflow.layout_engine import chart, presets
    rec = None
    if manual:
        rec = replace(presets.default_recipe("IO2", paper), dpi=72, seed=3,
                      **recipe)
    params = ChartParams(instrument="IO2", paper=paper, is_manual=manual,
                         tiff_dpi=72, layout_recipe=rec, chart_date="x",
                         target_name="Proof")
    creator = base._creator()
    kw = creator._engine_kwargs(params)
    kw.update(seed=3, chart_date="x")
    out = tmp_path
    result = chart.build_chart(_ti1(out / "chart.ti1", 1056), out / "chart",
                               label_rule="argyll", **kw)
    creator._write_channel_sidecar(out, "chart", params, engine="chromiq")
    creator._embed_layout_geometry(out, "chart", result, params)
    return result, creator, params


def _stored(tmp_path):
    from workflow.layout_engine.presets import LayoutRecipe
    return LayoutRecipe.from_channels_json(tmp_path / "chart.channels.json")


@pytest.mark.parametrize("manual", (True, False), ids=("Manual", "Guided"))
def test_both_writers_record_the_division(tmp_path, manual):
    result, creator, params = _generate(tmp_path, manual=manual)
    doc = json.loads((tmp_path / "chart.channels.json").read_text("utf-8"))
    assert doc["layout"]["recipe"]["i1io_pieces"] == A3 == result.i1io_pieces
    assert doc["layout"]["recipe"]["paper"] == "A3"
    assert creator._engine_total_patches(params) == 1056
    assert _stored(tmp_path).i1io_pieces == A3


def test_one_piece_is_recorded_as_nothing(tmp_path):
    _generate(tmp_path, paper="A4")
    doc = json.loads((tmp_path / "chart.channels.json").read_text("utf-8"))
    assert "i1io_pieces" not in doc["layout"]["recipe"]
    rec = _stored(tmp_path)
    assert rec.i1io_pieces == "one" and "i1io_pieces" not in rec.to_dict()


def test_restore_draws_the_printed_chart_whatever_the_rule_is_then(tmp_path,
                                                                   monkeypatch):
    """Made as two A4 pieces; then a later ChromIQ divides A3+ otherwise: the
    stored recipe still builds the same two 210 x 297 pieces, the same .ti2."""
    from workflow.layout_engine import chart
    (tmp_path / "x").mkdir()
    _generate(tmp_path / "x", paper="329x483")
    ti2 = (tmp_path / "x/chart.ti2").read_text("utf-8")
    monkeypatch.setattr(F, "LARGE_PIECES", True)
    assert P.plan_for((329.0, 483.0)).piece_mm == pytest.approx((241.5, 329.0))
    rec = _stored(tmp_path / "x")
    assert papers.piece_mm_of(rec) == (210.0, 297.0)
    (tmp_path / "y").mkdir()
    kw = rec.build_kwargs()
    kw.update(chart_date="x", project="Proof")
    r = chart.build_chart(_ti1(tmp_path / "y/chart.ti1", 1056),
                          tmp_path / "y/chart", label_rule="argyll", **kw)
    assert P.from_token(r.i1io_pieces).piece_mm == (210.0, 297.0)

    def data(t):
        return [ln for ln in t.split("\n") if not ln.startswith("CREATED")]
    assert data((tmp_path / "y/chart.ti2").read_text("utf-8")) == data(ti2)


def test_what_is_stored_is_read_by_everything_that_describes_it(tmp_path,
                                                                monkeypatch):
    """Under a later rule, the stored chart's readers still say 210 x 297."""
    _generate(tmp_path, paper="329x483")
    monkeypatch.setattr(F, "LARGE_PIECES", True)
    rec = _stored(tmp_path)
    from workflow.layout_engine import geometry, instruments
    geom = instruments.geom_from_build_kwargs(rec.build_kwargs())
    assert geometry.patches_per_sheet(geom, *papers.piece_mm_of(rec)) == 528
    from workflow import margin_inspector, page_coverage
    assert len(page_coverage.predicted_page_coverage(rec, 1056)["pages"]) == 2
    bottom = margin_inspector.engine_patch_bottom_mm(rec, 1056)
    assert bottom is not None and 15 < bottom < 40
    # ...and a chart of one piece stays one piece, whatever the rule says then
    monkeypatch.setattr(P, "one_piece", lambda sheet: False)
    P._plan.cache_clear()
    one = replace(rec, paper="A4", i1io_pieces="one")
    assert papers.piece_mm_of(one) == (210.0, 297.0)
    monkeypatch.undo()
    P._plan.cache_clear()
    from workflow.ti2_relayout import ChartSpec
    spec = ChartSpec.from_ti2(tmp_path / "chart.ti2")
    assert (spec.paper_flag, spec.paper_mm) == ("329x483", (329.0, 483.0))


def test_the_patch_set_editor_opens_the_sheet_not_the_piece(tmp_path):
    from workflow.ti2_relayout import ChartSpec
    for paper in ("A3", "420x297", "A2", "11x17", "A4"):
        d = tmp_path / paper
        d.mkdir()
        _build(d, paper, n=60)
        spec = ChartSpec.from_ti2(d / "c.ti2")
        assert spec.paper_flag == paper
        assert spec.paper_mm == pytest.approx(papers.dimensions_mm(paper),
                                              abs=0.06)


def test_the_panel_lays_out_by_todays_rule(qtbot):
    """A stored chart opened in Manual and laid out again is divided by the
    rule of today; its record stays in its files."""
    from ui.dialogs.layout_options_panel import LayoutOptionsPanel
    from workflow.layout_engine.presets import default_recipe
    p = LayoutOptionsPanel(with_selectors=True)
    qtbot.addWidget(p)
    p.instr.setCurrentIndex(p.instr.findData("IO2"))
    for token in (A3, "one"):
        p.set_recipe(replace(default_recipe("IO2", "A3"), i1io_pieces=token))
        assert p.get_recipe().i1io_pieces == ""
        assert p.get_recipe().paper == "A3"
        # (the panel of the patch set editor and of Preferences fills a recipe)
        assert p.apply_to_recipe(replace(
            default_recipe("IO2", "A3"), i1io_pieces=token)).i1io_pieces == ""


# ---- the lists, the panel's turn --------------------------------------------------------

def test_the_lists_offer_the_divided_sheets_after_the_others():
    codes = [c for c, _l, _d in papers.list_papers("IO2")]
    assert codes == list(C.GUIDED_PAPERS)
    assert codes[-4:] == ["A3", "11x17", "329x483", "A2"]
    for c in codes[:-4]:
        assert P.one_piece(papers.dimensions_mm(c))
    for c in codes[-4:]:
        assert P.plan_for(papers.dimensions_mm(c)) is not None
        assert "Landscape" not in C.i1io_paper_label(c)
    for c in ("A3", "A2", "11x17", "329x483"):
        assert C.paper_for(c) == c
    assert C.paper_for("420x297") == "A3" and C.paper_for("594x420") == "A2"
    assert C.paper_for("Legal") == "Letter" and C.paper_for("A4R") == "A4"


def test_only_a_one_piece_custom_size_is_turned_upright(qtbot):
    from ui.dialogs.layout_options_panel import LayoutOptionsPanel
    p = LayoutOptionsPanel(with_selectors=True)
    qtbot.addWidget(p)
    p.instr.setCurrentIndex(p.instr.findData("IO2"))
    p.paper.setCurrentIndex(p.paper.findData("__custom__"))
    for w, h, want in ((210, 148, "148x210"), (320, 230, "230x320"),
                       (420, 297, "420x297"), (297, 420, "297x420")):
        p.custom_w.setValue(w)
        p.custom_h.setValue(h)
        p._turn_custom_upright()
        assert p.selection()[1] == want


# ---- the counts --------------------------------------------------------------------------

def test_the_counts_of_a_divided_sheet(qtbot, monkeypatch, tmp_path):
    """Guided, A3, 1 sheet: 1 sheet, 1056 patches, two pieces; no question
    about a bound set that fits it; the name says one page."""
    from PyQt6.QtCore import QSettings

    from core.argyll_runner import ArgyllRunner
    from core.file_manager import FileManager
    from core.settings import AppSettings
    from ui.tabs import tab_chart
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "i.ini"), QSettings.Format.IniFormat)
    s.set("custom_output_path", str(tmp_path / "projects"))
    tab = tab_chart.TabChart(ArgyllRunner(s), FileManager(s), s)
    qtbot.addWidget(tab)
    tab._switch_mode("guided")
    i = tab._instr_combo.findData("IO2")
    tab._instr_combo.setCurrentIndex(i)
    tab._instr_combo.activated.emit(i)
    k = tab._paper_combo.findData("A3")
    assert k >= 0
    tab._paper_combo.setCurrentIndex(k)
    tab._update_patch_count()
    assert tab._predicted_patch_count == 1056
    assert "1 SHEET · 2 PIECES" in tab._patch_detail_lbl.text()
    assert tab._pages_row_lbl.text() == "Number of sheets:"
    assert not tab._i1io_pieces_note.isVisibleTo(tab)   # (item 65)
    assert tab._paper_tip.live_note() == tab._i1io_pieces_note.text()
    assert tab._i1io_pieces_note.text().startswith(
        "1 sheet, 2 pieces, 1056 patches.")
    tab._pages_spin.setValue(2)
    tab._update_patch_count()
    assert tab._predicted_patch_count == 2112
    assert tab._i1io_pieces_note.text().startswith(
        "2 sheets, 4 pieces, 2112 patches.")
    # …and a one-piece sheet says nothing of it
    tab._paper_combo.setCurrentIndex(tab._paper_combo.findData("A4"))
    tab._update_patch_count()
    assert "2 PAGES" in tab._patch_detail_lbl.text()
    assert tab._pages_row_lbl.text() == "Number of pages:"
    assert not tab._i1io_pieces_note.isVisibleTo(tab)
    assert not tab._paper_tip.live_note()
    tab._paper_combo.setCurrentIndex(k)
    tab._pages_spin.setValue(1)
    # a bound set of 1000 patches takes two pieces, one sheet
    monkeypatch.setattr(tab, "_pending_patch_set_total", lambda *a, **k: 1000,
                        raising=False)
    tab._update_patch_count()
    if tab._bound_set_pages is not None:
        assert tab._bound_set_pages == 1
    src = tab._guided_i1io_crosses_source()
    assert src["pages"] == 2
    lay = tab._predict_layout_info(
        tab._engine_geom("IO2", "A3", dd=False, td=False, eff_lb=False,
                         nsl=False, pscale=1.0, margin=10.0), "A3", 1)
    assert (lay.pages, lay.total_patches, lay.patches_per_page) == (2, 1056,
                                                                   528)
    info = tab._layout_info_panel
    assert info._row_names["pages"].text() == "Pieces"
    info.set_pieces(False, "estimate")
    assert info._row_names["pages"].text() == "Pages"


# ---- the words and placeholders of a piece (step 6) ------------------------------------

def _texts(side):
    return [p["text_line"]["text"] for p in side["pages"]]


@pytest.mark.parametrize("paper,n,sheets", [("A3", 2, 1), ("A3", 4, 2),
                                            ("A2", 4, 1)])
def test_every_piece_carries_its_own_numbers(tmp_path, paper, n, sheets):
    """(What is printed is English in every language, as on every chart.)"""
    from workflow.layout_engine.presets import default_recipe
    kw = replace(default_recipe("IO2", paper),
                 chart_text="{page} of {pages}, {sheet}, {patchcount}, {paper}"
                 ).build_kwargs()
    last = 528 * (n - 1) + 100
    from workflow.layout_engine import chart
    kw.update(dpi=100, seed=1, chart_date="x", project="P")
    r = chart.build_chart(_ti1(tmp_path / "c.ti1", last), tmp_path / "c", **kw)
    assert not [w for w in r.warnings if "no room on piece" in w]
    side = json.loads((tmp_path / "c.i1io.json").read_text("utf-8"))
    per = P.plan_for(papers.dimensions_mm(paper)).count
    pad = side["pages"][-1]["strips"]
    last_n = sum(len(s["patches"]) for s in pad)
    for k, text in enumerate(_texts(side)):
        count = 528 if k < n - 1 else last_n
        sheet = f"{k // per + 1}/{sheets}"
        sep = C.TEXT_SEP
        assert text.startswith(f"{k + 1}/{n}{sep}P{sep}{k + 1}/{n} of {n}, "
                               f"{sheet}, {count} patches, "), text
        assert paper in text or "A" in text


def test_a_one_piece_chart_leaves_sheet_out_cleanly(tmp_path):
    from workflow.layout_engine.presets import default_recipe
    for k, (text, want) in enumerate((("a, {sheet}, b", "a, b"),
                                      ("{sheet}", ""), ("x ({sheet})", "x"))):
        d = tmp_path / str(k)
        d.mkdir()
        kw = replace(default_recipe("IO2", "A4"), chart_text=text).build_kwargs()
        kw.update(dpi=72, seed=1, chart_date="x", project="P")
        from workflow.layout_engine import chart
        chart.build_chart(_ti1(d / "c.ti1", 60), d / "c", **kw)
        side = json.loads((d / "c.i1io.json").read_text("utf-8"))
        assert _texts(side)[0] == ("P" + C.TEXT_SEP + want if want
                                   else "P"), text


def test_other_charts_print_the_word_sheet_as_typed():
    from workflow.layout_engine.raster import (drop_the_logo,
                                               resolve_placeholders)
    assert resolve_placeholders("a, {sheet}, b", {"page": "1"}) == \
        "a, {sheet}, b"
    assert drop_the_logo("a, {logo}, b") == "a, b"


def test_the_panel_predicts_a_pieces_own_numbers(qtbot, tmp_path):
    from PyQt6.QtCore import QSettings

    from core.argyll_runner import ArgyllRunner
    from core.file_manager import FileManager
    from core.settings import AppSettings
    from ui.tabs import tab_chart
    from workflow.layout_engine.presets import default_recipe
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "i.ini"), QSettings.Format.IniFormat)
    tab = tab_chart.TabChart(ArgyllRunner(s), FileManager(s), s)
    qtbot.addWidget(tab)
    r = default_recipe("IO2", "A3")
    tab._estimated_layout = tab._predict_layout_info(
        __import__("workflow.layout_engine.instruments", fromlist=["x"])
        .geom_from_build_kwargs(r.build_kwargs()), "A3", 1, source=r)
    ctx = tab._text_placeholder_context(r)
    assert (ctx["sheet"], ctx["patchcount"]) == ("1/1", "528 patches")
    assert "_pages" not in ctx
    assert tab._text_placeholder_context(default_recipe(
        "IO2", "A4"))["sheet"] == ""
    assert "sheet" not in tab._text_placeholder_context(default_recipe(
        "i1", "A4"))


def test_no_room_for_a_pieces_number_is_said(tmp_path):
    from workflow import measurement_messages as M
    r = _build(tmp_path, "A3", i1io_crosses=False, project="P",
               margins=(12.0, 5.0, 12.0, 12.0), patch_w=8.0, patch_h=10.0)
    side = json.loads((tmp_path / "c.i1io.json").read_text("utf-8"))
    lost = [k for k, t in enumerate(_texts(side), 1)
            if not t.startswith(f"{k}/")]
    said = [w for w in r.warnings if "no room on piece" in w]
    assert bool(lost) == bool(said)
    assert lost, "the case must be one without room"
    assert said == [M._I1IO_PIECE_NUMBER_LOST.format(number=f"{lost[0]}/{r.layout.pages}")]


def test_manual_says_what_is_printed_and_cut(qtbot):
    from ui.dialogs.layout_options_panel import LayoutOptionsPanel
    p = LayoutOptionsPanel(with_selectors=True)
    qtbot.addWidget(p)
    p.instr.setCurrentIndex(p.instr.findData("IO2"))
    for paper, words in (("A3", "1 sheet, 2 pieces, 1056 patches."),
                         ("A2", "1 sheet, 4 pieces, 2112 patches."),
                         ("A4", "")):
        p.paper.setCurrentIndex(p.paper.findData(paper))
        assert not p._i1io_pieces_note.isVisibleTo(p)   # (item 65)
        assert bool(p._paper_tip.live_note()) == bool(words)
        assert p._pages_lbl.text() == ("Sheets:" if words else "Pages:")
        if words:
            assert p._i1io_pieces_note.text().startswith(words)
    p.paper.setCurrentIndex(p.paper.findData("__custom__"))
    p.custom_w.setValue(420)
    p.custom_h.setValue(297)
    assert p._paper_tip.live_note() == p._i1io_pieces_note.text()
    assert "upright" not in p._custom_size_lbl.text()
    p.custom_w.setValue(148)
    p.custom_h.setValue(210)
    assert not p._paper_tip.live_note()
    assert "upright" in p._custom_size_lbl.text()
    p.instr.setCurrentIndex(p.instr.findData("i1"))
    assert not p._paper_tip.live_note()
    assert p._pages_lbl.text() == "Pages:"


def test_the_labels_name_the_pieces():
    assert C.i1io_paper_label("A3") == "A3 (297 × 420 mm), 2 pieces"
    assert C.i1io_paper_label("Legal").endswith(", 1 piece")
    assert C.i1io_paper_label("420x300").endswith(" pieces")
    assert "piece" not in C.i1io_paper_label("A4")


def test_a3_from_a_preset(tmp_path):
    """A layout preset saved on A3 keeps "automatic"; chosen again it lays out
    two pieces a sheet, 1056 patches."""
    from workflow.layout_engine import geometry, instruments
    from workflow.layout_engine.presets import PresetStore, default_recipe
    rec = replace(default_recipe("IO2", "A3"), patch_w_mm=8.0, patch_h_mm=10.0)
    store = PresetStore()
    store.set(rec)
    f = tmp_path / "p.json"
    store.save(f)
    assert "i1io_pieces" not in f.read_text("utf-8")
    back = PresetStore.load(f).get(*rec.preset_key().split("|"))
    assert (back.paper, back.i1io_pieces) == ("A3", "")
    g = instruments.geom_from_build_kwargs(back.build_kwargs())
    per = geometry.patches_per_sheet(g, *papers.piece_mm_of(back))
    assert papers.patches_on_a_sheet(per, back) == 1056


# ---- every reader of a paper size, and what it gets ----------------------------------------

READERS = json.loads((ROOT / "tests/data/i1io_readers.json").read_text("utf-8"))


def _calls(path: Path) -> "list[tuple[str, str]]":
    """``[(function, name)]`` of every size call in *path*, and of every use of
    a table of paper sizes."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    spans = [(n.lineno, n.end_lineno, n.name) for n in ast.walk(tree)
             if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
    out = []
    for n in ast.walk(tree):
        if isinstance(n, (ast.Name, ast.Attribute)) and isinstance(
                n.ctx, ast.Load):
            name = getattr(n, "attr", getattr(n, "id", ""))
            hit = name in ("PAPER_SIZES", "_PAPER_MM", "_NAMED_MM",
                           "_NAMED_PAPERS")
        elif isinstance(n, ast.Call):
            name = getattr(n.func, "attr", getattr(n.func, "id", ""))
            hit = name in ("dimensions_mm", "piece_mm_of", "parse_custom",
                           "patches_on_a_sheet", "sheets_of", "pieces_on",
                           "_paper_mm_of", "paper_mm_of")
        else:
            continue
        if hit:
            inside = [s for s in spans if s[0] <= n.lineno <= s[1]]
            out.append((max(inside)[2] if inside else "", name))
    return out


def test_every_reader_of_a_paper_size_is_in_the_table():
    """The table the design asks for, as data: `dimensions_mm` is the SHEET (or
    a chart that is never divided), `piece_mm_of` the PIECE, the rest are the
    counts. A new reader fails here until somebody says which it is."""
    found: "dict[str, dict[str, int]]" = {}
    for top in ("core", "ui", "workflow"):
        for f in sorted((ROOT / top).rglob("*.py")):
            rel = f.relative_to(ROOT).as_posix()
            if rel.startswith(("workflow/barbieri/", "workflow/isis/",
                               "workflow/fd9/")):
                continue                # (the other instruments' own modules)
            for fn, name in _calls(f):
                d = found.setdefault(rel, {})
                key = f"{fn}: {name}"
                d[key] = d.get(key, 0) + 1
    want = {rel: {k: v["calls"] for k, v in d.items()}
            for rel, d in READERS["calls"].items()}
    assert found == want
    for rel, d in READERS["calls"].items():
        for k, v in d.items():
            assert v["is"] in ("sheet", "piece", "count", "never divided",
                               "the rule itself"), (rel, k)
            if k.endswith(": piece_mm_of"):
                assert v["is"] == "piece"
            if k.endswith((": patches_on_a_sheet", ": sheets_of",
                           ": pieces_on")):
                assert v["is"] == "count"


def test_every_count_place_counts_what_the_table_says(qtbot, monkeypatch,
                                                      tmp_path):
    """Where sheets and pieces meet (RA2), each place asked for its NUMBER on
    two sheets of A3 (four pieces, 1056 patches a sheet): the value itself,
    not the function's name. A place whose number is of another meaning, and
    one the table names that nobody asks here, fail."""
    from PyQt6.QtCore import QSettings
    from PyQt6.QtWidgets import QMessageBox

    from core.argyll_runner import ArgyllRunner
    from core.file_manager import FileManager
    from core.settings import AppSettings
    from ui.tabs import tab_chart
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "i.ini"), QSettings.Format.IniFormat)
    s.set("custom_output_path", str(tmp_path / "projects"))
    s.set("use_chromiq_layout_engine", True)
    tab = tab_chart.TabChart(ArgyllRunner(s), FileManager(s), s)
    qtbot.addWidget(tab)
    got: "dict[str, float]" = {}

    # Guided, two sheets
    tab._switch_mode("guided")
    i = tab._instr_combo.findData("IO2")
    tab._instr_combo.setCurrentIndex(i)
    tab._instr_combo.activated.emit(i)
    tab._paper_combo.setCurrentIndex(tab._paper_combo.findData("A3"))
    tab._pages_spin.setValue(2)
    tab._update_patch_count()
    shown = re.search(r"(\d+) SHEETS? · (\d+) PIECES",
                      tab._patch_detail_lbl.text())
    assert int(shown.group(2)) == 4
    got["_update_patch_count"] = int(shown.group(1))
    opts = dict(dd=False, td=False, eff_lb=False, nsl=False, pscale=1.0,
                margin=10.0)
    got["_engine_capacity"] = tab._engine_capacity("IO2", "A3", **opts)
    got["_predict_layout_info"] = tab._predict_layout_info(
        tab._engine_geom("IO2", "A3", **opts), "A3", 2).pages
    got["_guided_i1io_crosses_source"] = \
        tab._guided_i1io_crosses_source()["pages"]
    params = tab._collect_guided()
    got["_engine_total_patches"] = tab._creator._engine_total_patches(
        params) / params.pages
    # a bound set that takes two sheets is no reason to ask at "2"
    monkeypatch.setattr(tab, "_pending_patch_set_total", lambda *a, **k: 2000)
    asked = []
    monkeypatch.setattr(QMessageBox, "exec", lambda box: asked.append(
        box.informativeText()) or 0)
    tab._guided_capacity = 1056
    tab._bound_set_pages = 2
    monkeypatch.setattr(tab, "_update_patch_count", lambda *a, **k: None)
    assert tab._guided_bound_set_pages_answer() == "keep" and not asked
    monkeypatch.undo()
    monkeypatch.setattr(tab, "_pending_patch_set_total", lambda *a, **k: 2000)
    tab._update_patch_count()
    got["_guided_bound_set_pages_answer"] = getattr(
        tab, "_bound_set_pages", None) or -(-2000 // 1056)

    # Manual, two sheets
    monkeypatch.undo()
    tab._switch_mode("manual")
    panel = tab._manual_layout_panel
    panel.set_recipe(replace(
        __import__("workflow.layout_engine.presets",
                   fromlist=["x"]).default_recipe("IO2", "A3"), dpi=72))
    panel.pages.setValue(2)
    if tab._manual_pages_spin is not None:
        tab._manual_pages_spin.setValue(2)
    got["_recipe_capacity"] = tab._recipe_capacity()
    got["_manual_i1io_context"] = tab._manual_i1io_context()["pages"]
    monkeypatch.setattr(tab, "_gamut_auto_check",
                        type("B", (), {"isChecked": lambda s: True})(),
                        raising=False)
    monkeypatch.setattr(tab, "_gamut_in_gamut_total", lambda: None)
    got["_gamut_effective_count"] = (tab._gamut_effective_count()
                                     + tab_chart._GAMUT_CORNER_PATCHES) / 2
    # the chart on screen: its pieces
    r = _build(tmp_path, "A3", n=2000)
    tab._margin_tiffs, tab._margin_ti2 = list(r.tiff_paths), r.ti2_path
    tab._preview.load_tiff(list(r.tiff_paths))
    info = tab._layout_info_panel
    seen = {}
    monkeypatch.setattr(info, "set_actual",
                        lambda **k: seen.update(k), raising=False)
    tab._update_layout_info()
    got["_update_layout_info"] = seen["pages"]
    want = {"sheets": 2, "pieces": 4, "patches of a sheet": 1056}
    assert got == {p["function"]: want[p["means"]] for p in READERS["counts"]}
