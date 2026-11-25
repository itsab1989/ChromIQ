"""THE SIZES OF AN i1iO CHART (the new chart layout, 25 November 2026).

* A size an i1iO chart did not have (a layout of an earlier ChromIQ, or one
  carried over from another instrument) is the i1iO's own now, and said: it is
  never silently a smaller patch than anybody printed.
* A chart is aimed at its corner patches only where one strip off would be seen.
* The runs stay inside the arm's reach, with the letters off too.
* Small patches, short patches and thin spacers are said.
"""
from __future__ import annotations

import json
import math

import pytest

from workflow.i1io import chart as C
from workflow.i1io import table_facts as F


@pytest.fixture(autouse=True)
def i1io_on():
    from workflow.i1io import support
    before = support._latched
    support.set_enabled_for_this_process(True)
    try:
        yield
    finally:
        support._latched = before


# ---- old layouts and other instruments' -------------------------------------

@pytest.mark.parametrize("kw,size,spacer", [
    ({"patch_h": 6.0, "patch_w": 6.0}, (10.0, 8.0), 1.0),
    ({"patch_h": 10.0, "patch_w": 6.0}, (10.0, 8.0), 1.0),
    ({"patch_h": 25.0, "patch_w": 8.0}, (10.0, 8.0), 1.0),
    ({"patch_h": 8.9, "patch_w": 7.0}, (8.9, 7.0), 1.0),
    ({"patch_h": 20.0, "patch_w": 20.0}, (20.0, 20.0), 1.0),
    ({"spacer_width": 0.4}, (10.0, 8.0), 1.0),
    ({"spacer_width": 2.0, "patch_h": 12.0}, (12.0, 8.0), 2.0)])
def test_an_old_layouts_sizes(kw, size, spacer):
    """In range unchanged, out of range the i1iO's own, and said."""
    got = C.fixed_build_kwargs(kw)
    assert (got["patch_h"], got["patch_w"]) == size
    assert got["spacer_width"] == spacer
    changed = any(kw.get(k, v) != v for k, v in (
        ("patch_h", size[0]), ("patch_w", size[1]), ("spacer_width", spacer)))
    assert bool(C.old_size_message(kw)) == changed
    # …and the same sizes asked for now are built
    now = C.fixed_build_kwargs({**kw, C.LIMITS_KEY: C.LIMITS_NOW})
    assert now["patch_h"] == kw.get("patch_h", 10.0)
    assert now["patch_w"] == kw.get("patch_w", 8.0)
    assert C.old_size_message({**kw, C.LIMITS_KEY: C.LIMITS_NOW}) == ""


@pytest.mark.parametrize("kw,parts,counts", [
    # the size that is not used, alone
    ({"patch_h": 6.0, "patch_w": 6.0},
     ["Patch size: 10 × 8 mm, the i1iO's own, not the 6 × 6 mm of the layout "
      "(an earlier ChromIQ printed 8.9 × 7 mm)"], (650, 528)),
    ({"patch_h": 12.0, "patch_w": 9.0, "spacer_width": 0.4},
     ["Spacer size: 1 mm, the i1iO's own, not the 0.4 mm of the layout"], None),
    ({"patch_h": 6.0, "patch_w": 6.0, "spacer_width": 1.5},
     ["Patch size: 10 × 8 mm, the i1iO's own, not the 6 × 6 mm of the layout "
      "(an earlier ChromIQ printed 8.9 × 7 mm)"], (625, 506)),
    # one side out of range: both are the i1iO's own
    ({"patch_h": 12.0, "patch_w": 6.0},
     ["Patch size: 10 × 8 mm, the i1iO's own, not the 12 × 6 mm of the layout "
      "(an earlier ChromIQ printed 12 × 7 mm)"], (500, 528)),
    # what an earlier ChromIQ held smaller is built as asked for, and said
    ({"spacer_width": 5.0},
     ["Spacer size: 5 mm (an earlier ChromIQ held it to 2 mm)"], (484, 374)),
    ({"strip_gap": 8.0},
     ["Strip gap: 8 mm (an earlier ChromIQ held it to 3 mm)"], (384, 264)),
    ({"inter_patch": 3.0},
     ["Inter-patch gap: 3 mm (an earlier ChromIQ held it to 2 mm)"],
     (440, 418)),
    ({"indicator_size_mm": 7.0},
     ["Size of the letters and numbers: 7 mm (an earlier ChromIQ held it to "
      "6 mm)"], None),
    # nothing to say
    ({}, [], None),
    ({"spacer_width": 1.0}, [], None),
    ({"spacer_width": 2.0, "strip_gap": 3.0, "inter_patch": 2.0,
      "indicator_size_mm": 6.0, "patch_h": 20.0, "patch_w": 7.0}, [], None),
    ({"spacer_mode": "none", "spacer_width": 0.4}, [], None),
    ({"indicator_size_mm": 9.0, "draw_indicators": False,
      "row_indicators": False}, [], None)])
def test_what_comes_out_differently_is_said_by_name(kw, parts, counts):
    """Only what really changed, with its sizes, and the patches of a full
    sheet before and now; and the sheet is what the sentence says."""
    from workflow import measurement_messages as M
    from workflow.layout_engine import geometry, instruments, papers
    kw = {"paper": "A4", **kw}
    said = list(parts)
    if counts:
        said.append(M._I1IO_SIZE_COUNTS.format(before=counts[0],
                                               now=counts[1]))
    want = M._I1IO_OLD_SIZE_REPLACED.format(changes="; ".join(said)) \
        if said else ""
    assert C.old_size_message(kw) == want
    if counts:
        w, h = papers.dimensions_mm("A4")
        g = instruments.geom_from_build_kwargs({**kw, "instrument": "IO2"})
        assert geometry.patches_per_sheet(g, w, h) == counts[1]
    # made now, the same sizes are said by nobody
    assert C.old_size_message({**kw, C.LIMITS_KEY: C.LIMITS_NOW}) == ""


@pytest.mark.parametrize("fields,word", [
    ({"strip_gap_mm": 8.0}, "Strip gap: 8 mm"),
    ({"inter_patch_mm": 3.0}, "Inter-patch gap: 3 mm"),
    ({"spacer_width_mm": 5.0}, "Spacer size: 5 mm")])
def test_a_wide_size_of_another_instrument_is_kept_and_said(fields, word):
    """What an earlier ChromIQ silently held smaller: built as asked for now,
    and said once, in the log and on screen; another instrument's ordinary
    layout says nothing."""
    from dataclasses import replace

    from ui.tabs.tab_chart import TabChart
    from workflow.layout_engine.presets import default_recipe
    said = []

    class _Tab:
        _log = object()

        def _on_log_line(self, line):
            said.append(line)
    r = replace(default_recipe("i1", "A4"), **fields)
    out = TabChart._retargeted(_Tab(), r, "IO2", "A4")
    for k, v in fields.items():
        assert getattr(out, k) == v
    assert len(said) == 1 and word in said[0]
    assert "patches on a full sheet" in said[0]
    out = TabChart._retargeted(_Tab(), out, "IO2", "A4")
    assert len(said) == 1
    for i in ("i1", "p3", "CM", "SS", "CR30"):
        TabChart._retargeted(_Tab(), default_recipe(i, "A4"), "IO2", "A4")
    assert len(said) == 1


def test_generate_says_the_sizes_in_the_log(tmp_path, monkeypatch):
    """…as information, not as a warning; and the crosses kept on narrow
    strips too, which read well with them."""
    from tests.test_a_layout_engine_failure_reaches_a_window import _creator
    from tests.test_i1io_chart import _ti1
    from workflow import measurement_messages as M
    from workflow.chart_creator import ChartParams
    creator, fm = _creator(tmp_path)
    work = fm.cwd_for_chart(cal_target=False)
    _ti1(work / f"{fm.chart_stem(cal_target=False)}.ti1", 300)
    kw = {"instrument": "IO2", "paper": "A4", "dpi": 100, "seed": 1,
          "chart_date": "x", "strip_gap": 4.0, "patch_w": 7.0,
          "patch_h": 10.0}
    monkeypatch.setattr(creator, "_engine_kwargs", lambda p: dict(kw))

    def lines():
        out: "list[str]" = []
        creator._run_engine(ChartParams(instrument="IO2", paper="A4"), work,
                            out.append)
        assert not [ln for ln in out if "ERROR" in ln], out
        return out
    want = "[INFO] " + C.old_size_message(kw)
    assert "Strip gap: 4 mm" in want and lines().count(want) == 1
    kw.update({C.LIMITS_KEY: 2, "strip_gap": 0.0, "patch_w": 6.0,
               C.CROSSES_KEY: False})
    got = lines()
    assert "[INFO] " + M._I1IO_NARROW_KEEPS_CROSSES in got
    assert not any(M._I1IO_NARROW_KEEPS_CROSSES[:30] in ln
                   and ln.startswith("[WARNING]") for ln in got)


def test_a_bad_marker_in_a_stored_recipe_is_none():
    from workflow.layout_engine.presets import LayoutRecipe, default_recipe
    d = default_recipe("IO2", "A4").to_dict()
    for bad in ("abc", "2.0", None, [], {}):
        assert LayoutRecipe.from_dict({**d, "i1io_limits": bad}).i1io_limits == 0


def test_the_marker_stays_out_of_other_instruments_recipes():
    """An i1iO layout turned into another instrument's (a retarget keeps every
    field it does not own): its dict and its kwargs carry no marker."""
    from ui.tabs.tab_chart import TabChart
    from workflow.layout_engine.presets import default_recipe
    out = TabChart._retargeted(object(), default_recipe("IO2", "A4"), "i1",
                               "A4")
    assert out.instrument == "i1" and out.i1io_limits == C.LIMITS_NOW
    assert "i1io_limits" not in out.to_dict()
    assert C.LIMITS_KEY not in out.build_kwargs()


def test_a_label_size_comes_back_with_the_room(qtbot):
    """8 mm strips, then 5.5, then 8 again: the label the person set is the
    label again; one set meanwhile stays."""
    from ui.dialogs.layout_options_panel import LayoutOptionsPanel
    p = LayoutOptionsPanel(with_selectors=True)
    qtbot.addWidget(p)
    p.instr.setCurrentIndex(p.instr.findData("IO2"))
    p.indicator_size.setValue(17.0)
    was = p.indicator_size.value()
    p.patch_x.setValue(5.5)
    assert p.indicator_size.value() < was
    p.patch_x.setValue(8.0)
    assert p.indicator_size.value() == was
    p.patch_x.setValue(5.5)
    p.indicator_size.setValue(9.0)
    p.patch_x.setValue(8.0)
    assert p.indicator_size.value() == 9.0


def test_the_second_pass_over_the_fixed_settings_changes_nothing():
    for kw in ({"patch_h": 6.0, "patch_w": 6.0}, {"spacer_width": 0.4},
               {"patch_h": 6.0, "patch_w": 6.0, C.LIMITS_KEY: 2}):
        once = C.fixed_build_kwargs(kw)
        assert C.fixed_build_kwargs(once) == once


def test_an_old_recipe_is_built_at_the_i1ios_own_size_and_said(tmp_path):
    from dataclasses import replace

    from tests.test_i1io_chart import _ti1
    from workflow.layout_engine import chart
    from workflow.layout_engine.presets import LayoutRecipe, default_recipe
    r = replace(default_recipe("IO2", "A4"), patch_w_mm=6.0, patch_h_mm=6.0)
    d = r.to_dict()
    assert d["i1io_limits"] == C.LIMITS_NOW
    old = LayoutRecipe.from_dict({k: v for k, v in d.items()
                                  if k != "i1io_limits"})
    assert old.i1io_limits == 0
    for recipe, size, notes in ((old, [8.0, 10.0], 1), (r, [6.0, 6.0], 0)):
        out = tmp_path / str(size[1])
        out.mkdir()
        kw = recipe.build_kwargs()
        kw.update(dpi=100, seed=1, chart_date="x")
        res = chart.build_chart(_ti1(out / "c.ti1", 60), out / "c", **kw)
        side = json.loads((out / "c.i1io.json").read_text(encoding="utf-8"))
        assert side["patch_mm"] == size and len(res.notes) == notes
        # the panel says it before Generate, too
        _s, said = C.preview_checks({**kw, "area_target_count": 60})
        assert (res.notes[0] in said) if notes else res.notes == ()


def test_a_recipe_of_another_instrument_never_brings_its_small_patches(qtbot):
    """Retargeted to the i1iO: the 6 mm patch and the 0.4 mm spacer become the
    i1iO's own, the line is logged, and what is in range stays."""
    from dataclasses import replace

    from ui.tabs.tab_chart import TabChart
    from workflow.layout_engine.presets import default_recipe
    said = []

    class _Tab:
        _log = object()

        def _on_log_line(self, line):
            said.append(line)
    r = replace(default_recipe("i1", "A4"), patch_w_mm=6.0, patch_h_mm=6.0,
                spacer_width_mm=0.4, i1io_limits=2)
    out = TabChart._retargeted(_Tab(), r, "IO2", "Letter")
    assert (out.instrument, out.paper) == ("IO2", "Letter")
    assert (out.patch_h_mm, out.patch_w_mm, out.spacer_width_mm) == (10, 8, 1)
    assert out.i1io_limits == C.LIMITS_NOW and len(said) == 1
    r = replace(default_recipe("i1", "A4"), patch_w_mm=9.0, patch_h_mm=12.0)
    out = TabChart._retargeted(_Tab(), r, "IO2", "A4")
    assert (out.patch_h_mm, out.patch_w_mm) == (12, 9) and len(said) == 1
    # an i1iO recipe on another paper keeps its sizes
    io = replace(default_recipe("IO2", "A4"), patch_w_mm=6.0, patch_h_mm=6.0)
    assert TabChart._retargeted(_Tab(), io, "IO2", "Letter").patch_w_mm == 6.0


def test_the_panel_takes_over_an_old_layout_and_says_it_once(qtbot):
    from dataclasses import replace

    from ui.dialogs.layout_options_panel import LayoutOptionsPanel
    from workflow.layout_engine.presets import default_recipe
    p = LayoutOptionsPanel(with_selectors=True)
    qtbot.addWidget(p)
    p.instr.setCurrentIndex(p.instr.findData("IO2"))
    said = []
    p.notice.connect(said.append)
    old = replace(default_recipe("IO2", "A4"), patch_w_mm=6.0, patch_h_mm=6.0,
                  i1io_limits=0)
    p.set_recipe(old)
    assert (p.patch_x.value(), p.patch_y.value()) == (8.0, 10.0)
    assert len(said) == 1
    back = p.get_recipe()
    assert back.i1io_limits == C.LIMITS_NOW
    p.set_recipe(replace(back, patch_w_mm=6.0, patch_h_mm=6.5,
                         spacer_width_mm=0.5))
    assert (p.patch_x.value(), p.patch_y.value()) == (6.0, 6.5)
    assert p.spacer_width.value() == 0.5 and len(said) == 1


def test_choosing_the_i1io_after_a_chart_of_small_patches(qtbot):
    from ui.dialogs.layout_options_panel import LayoutOptionsPanel
    p = LayoutOptionsPanel(with_selectors=True)
    qtbot.addWidget(p)
    p.instr.setCurrentIndex(p.instr.findData("i1"))
    p.patch_x.setValue(6.0)
    p.patch_y.setValue(6.0)
    p.spacer_width.setValue(0.5)
    p.instr.setCurrentIndex(p.instr.findData("IO2"))
    assert (p.patch_x.value(), p.patch_y.value()) == (8.0, 10.0)
    assert p.spacer_width.value() == 1.0
    p.instr.setCurrentIndex(p.instr.findData("i1"))
    assert (p.patch_x.value(), p.spacer_width.value()) == (6.0, 0.5)


# ---- corner patches only where one strip off is seen ------------------------

def _geometry(paper, across, along=10.0, gap=0.0):
    from workflow.layout_engine import geometry, instruments, papers
    w, h = papers.dimensions_mm(paper)
    g = instruments.geom_from_build_kwargs({
        "instrument": "IO2", "paper": paper, "patch_w": across,
        "patch_h": along, "strip_gap": gap, C.LIMITS_KEY: 2,
        C.CROSSES_KEY: False})
    n = geometry.patches_per_sheet(g, w, h)
    return g, geometry.compute(g, w, h, n), w, h


def _alignment_refuses(sheet_h, cells, pitch, honest_deg):
    """Mark 3 aimed one strip too far in, and the sheet's honest half degree
    the other way: does the table's own alignment refuse it?"""
    from workflow.i1io.table import geometry as geo
    pts = []
    for corner in C.CORNERS[:3]:
        c = cells[corner]
        pts.append(C.to_table_mm(sheet_h, ((c[3] + c[5]) / 2, (c[4] + c[6]) / 2)))

    def table(u, v):
        return (1650 - 10 * u, 600 + 10 * v)
    aims = [table(*p) for p in pts]
    x3, y3 = aims[2]
    # one strip too far in (towards mark 1's side, the back)
    y3 -= 10 * pitch
    # what an honest aim may be off the other way: towards the front
    y3 += math.tan(math.radians(honest_deg)) * abs(aims[2][0] - aims[1][0])
    read = [aims[0], aims[1], (x3, y3)]
    try:
        geo.fit_model(pts, [tuple(round(v) for v in p) for p in read])
    except geo.AlignmentRefused:
        return True
    return False


@pytest.mark.parametrize("paper", ("A4", "Letter", "230x320", "242x329"))
@pytest.mark.parametrize("across", (5.5, 6.0, 6.6, 6.8, 7.0, 7.5, 7.6, 8.0,
                                    10.0))
def test_one_strip_off_is_refused_or_the_page_keeps_its_crosses(paper, across):
    g, lay, w, h = _geometry(paper, across)
    cells = C.corner_cells(g, lay, w, h, 0)
    seen = _alignment_refuses(h, cells, float(g.rrsp), F.ALIGN_HONEST_DEG.value)
    kept = not C.corners_tell_a_strip(cells, float(g.rrsp))
    assert seen or kept, (paper, across)
    if paper == "A4":
        assert kept == (across < 6.7)
    assert kept == (C.strip_turn_deg(cells, float(g.rrsp)) < 1.5)
    if across >= 8.0:
        assert not kept and seen


def test_such_a_page_keeps_its_crosses_and_says_so(tmp_path):
    from tests.test_i1io_chart import _ti1
    from workflow.layout_engine import chart
    from workflow import measurement_messages as M
    for across, aim, said in ((6.0, "crosses", True),
                              (8.0, "corner patches", False)):
        out = tmp_path / str(across)
        out.mkdir()
        # dark patches, so the corners can be aimed at
        r = chart.build_chart(
            _ti1(out / "c.ti1", 500), out / "c", instrument="IO2", paper="A4",
            dpi=100, seed=1, chart_date="x", patch_w=across, patch_h=10.0,
            i1io_limits=2, i1io_crosses=False)
        side = json.loads((out / "c.i1io.json").read_text(encoding="utf-8"))
        assert (M._I1IO_NARROW_KEEPS_CROSSES in r.notes) == said
        assert M._I1IO_NARROW_KEEPS_CROSSES not in r.warnings
        # the panel says it before Generate, too
        _s, notes = C.preview_checks({
            "instrument": "IO2", "paper": "A4", "dpi": 100,
            "patch_w": across, "patch_h": 10.0, "i1io_limits": 2,
            "i1io_crosses": False, "area_target_count": 500})
        assert (M._I1IO_NARROW_KEEPS_CROSSES in notes) == said
        assert side["pages"][0]["aim"] == aim


def test_the_strip_gap_counts_for_the_strip_pitch(tmp_path):
    """5.5 mm patches with a 3 mm gap between the strips: one strip off turns
    the corner by 8.5 mm, which is seen, so the corner patches are aimed at."""
    from tests.test_i1io_chart import _ti1
    from workflow.layout_engine import chart
    for gap, aim in ((3.0, "corner patches"), (0.0, "crosses")):
        out = tmp_path / str(gap)
        out.mkdir()
        chart.build_chart(
            _ti1(out / "c.ti1", 500), out / "c", instrument="IO2", paper="A4",
            dpi=100, seed=1, chart_date="x", patch_w=5.5, patch_h=10.0,
            strip_gap=gap, i1io_limits=2, i1io_crosses=False)
        side = json.loads((out / "c.i1io.json").read_text(encoding="utf-8"))
        assert side["pages"][0]["aim"] == aim, gap


def test_without_room_for_its_crosses_such_a_page_is_refused(tmp_path):
    from tests.test_i1io_chart import _ti1
    from workflow.layout_engine import chart
    with pytest.raises(C.I1ioSheetRefused, match="so narrow"):
        chart.build_chart(
            _ti1(tmp_path / "c.ti1", 500), tmp_path / "c", instrument="IO2",
            paper="A4", dpi=100, seed=1, chart_date="x", patch_w=6.0,
            patch_h=10.0, i1io_limits=2, i1io_crosses=False,
            margins=(1.0, 1.0, 1.0, 1.0), draw_indicators=False,
            row_indicators=False)
    assert sorted(p.name for p in tmp_path.iterdir()) == ["c.ti1"]


# ---- the runs inside the reach ----------------------------------------------

@pytest.mark.parametrize("letters", (True, False))
@pytest.mark.parametrize("along", (5.5, 8.0, 10.0))
@pytest.mark.parametrize("paper", ("A4", "230x320", "242x324", "242x328.5",
                                   "242x331"))
def test_a_run_never_spans_more_than_the_reach(paper, along, letters):
    from workflow.layout_engine import geometry, instruments, papers
    w, h = papers.dimensions_mm(paper)
    kw = {"instrument": "IO2", "paper": paper, "patch_h": along,
          "patch_w": 8.0, "spacer_mode": "none", "margins": (0.1,) * 4,
          "draw_indicators": letters, "row_indicators": letters,
          # (as ONE page: the piece of a divided sheet is at most A4 / Letter
          # until the large pieces are signed off)
          C.LIMITS_KEY: 2, "i1io_pieces": "one"}
    g = instruments.geom_from_build_kwargs(kw)
    lay = geometry.compute(g, w, h, geometry.patches_per_sheet(g, w, h))
    for _x, y0, y1, _c in C.scan_strips(C.page_patches(g, lay, w, h, 0)):
        assert y1 - y0 <= F.REACH_MM.value[0] + 1e-6
    # nothing floored on a sheet that is inside the reach itself
    if h <= 320:
        assert C.least_margins_mm(kw)[0] == F.RUN_EDGE_MM.value + F.RUN_MM.value


def test_the_build_holds_the_runs_inside_the_reach(tmp_path, monkeypatch):
    """Through the build (a sheet over the reach is refused today, so its
    check is taken away here): the page's own height reaches the margins."""
    from tests.test_i1io_chart import _ti1
    from workflow.layout_engine import chart
    monkeypatch.setattr(C, "sheet_size", lambda paper: None)
    chart.build_chart(
        _ti1(tmp_path / "c.ti1", 400), tmp_path / "c", instrument="IO2",
        paper="242x331", dpi=100, seed=1, chart_date="x", patch_w=8.0,
        patch_h=8.0, spacer_mode="none", draw_indicators=False,
        row_indicators=False, margins=(0.1,) * 4, i1io_limits=2,
        i1io_pieces="one")
    side = json.loads((tmp_path / "c.i1io.json").read_text(encoding="utf-8"))
    spans = [st["run_mm"][1] - st["run_mm"][0]
             for st in side["pages"][0]["strips"]]
    assert 300 < max(spans) <= F.REACH_MM.value[0] + 0.1


# ---- what is said about sizes -----------------------------------------------

@pytest.mark.parametrize("along,across,spacer,ids", [
    (10.0, 8.0, 1.0, ()), (10.0, 7.0, 1.0, ()),
    (8.0, 8.0, 1.0, ("SHORT",)), (8.0, 8.0, 0.75, ("SHORT", "THIN")),
    (7.6, 8.0, 1.0, ("SHORT",)), (7.5, 8.0, 1.0, ("SPOT",)),
    (10.0, 6.0, 1.0, ("SMALL",)), (5.5, 5.5, 1.0, ("SMALL", "SPOT"))])
def test_the_notes_about_sizes(along, across, spacer, ids):
    from workflow import measurement_messages as M
    said = C.size_notes(C.fixed_build_kwargs({
        "patch_h": along, "patch_w": across, "spacer_width": spacer,
        C.LIMITS_KEY: 2}))
    starts = {"SHORT": M._I1IO_SHORT_PATCH.format(size="10")[:40],
              "SPOT": M._I1IO_SPOT_PATCH.format(size="7.6")[:40],
              "THIN": M._I1IO_THIN_SPACER[:13],
              "SMALL": M._I1IO_SMALL_PATCH[:30]}
    assert [any(s.startswith(v) for s in said) for v in starts.values()] == [
        k in ids for k in starts]
    if "SMALL" in ids:
        share = {5.5: "9.9 %", 6.0: "5.2 %"}[min(along, across)]
        assert any(share in s for s in said)
        assert not any("just as good" in s for s in said)


def test_the_build_and_the_panel_say_the_notes(tmp_path):
    from tests.test_i1io_chart import _ti1
    from workflow import measurement_messages as M
    from workflow.layout_engine import chart
    kw = dict(instrument="IO2", paper="A4", dpi=100, patch_w=6.0, patch_h=8.0,
              i1io_limits=2)
    r = chart.build_chart(_ti1(tmp_path / "c.ti1", 60), tmp_path / "c", seed=1,
                          chart_date="x", **kw)
    _s, said = C.preview_checks({**kw, "area_target_count": 60})
    for start in (M._I1IO_SMALL_PATCH[:30], M._I1IO_SHORT_PATCH[:14]):
        assert any(w.startswith(start) for w in r.warnings)
        assert any(w.startswith(start) for w in said)


# ---- every recipe made now says under which limits --------------------------

def test_a_layout_made_in_manual_carries_the_limits(qtbot):
    from ui.dialogs.layout_options_panel import LayoutOptionsPanel
    p = LayoutOptionsPanel(with_selectors=True)
    qtbot.addWidget(p)
    p.instr.setCurrentIndex(p.instr.findData("IO2"))
    p.patch_x.setValue(6.0)
    r = p.get_recipe()
    assert r.build_kwargs()[C.LIMITS_KEY] == C.LIMITS_NOW
    assert r.to_dict()["i1io_limits"] == C.LIMITS_NOW
    p.instr.setCurrentIndex(p.instr.findData("i1"))
    r = p.get_recipe()
    assert "i1io_limits" not in r.to_dict()
    assert C.LIMITS_KEY not in r.build_kwargs()


def test_guided_carries_the_limits():
    import _i1io_baseline as base
    from workflow.chart_creator import ChartParams
    kw = base._creator()._engine_kwargs(ChartParams(instrument="IO2"))
    assert kw[C.LIMITS_KEY] == C.LIMITS_NOW
    for other in ("i1", "CM", "p3", "SS", "CR30"):
        assert C.LIMITS_KEY not in base._creator()._engine_kwargs(
            ChartParams(instrument=other))


def test_a_recipe_goes_through_kwargs_and_back_with_its_limits():
    from workflow.layout_engine.presets import LayoutRecipe, default_recipe
    r = default_recipe("IO2", "A4")
    assert LayoutRecipe.from_build_kwargs(r.build_kwargs()).i1io_limits == 2
    assert LayoutRecipe.from_dict(json.loads(json.dumps(
        r.to_dict()))).i1io_limits == 2


def test_an_old_recipe_edited_in_the_panel_carries_the_limits(qtbot):
    from dataclasses import replace

    from ui.dialogs.layout_options_panel import LayoutOptionsPanel
    from workflow.layout_engine.presets import default_recipe
    p = LayoutOptionsPanel(with_selectors=True)
    qtbot.addWidget(p)
    p.instr.setCurrentIndex(p.instr.findData("IO2"))
    old = replace(default_recipe("IO2", "A4"), i1io_limits=0)
    p.set_recipe(old)
    p.patch_x.setValue(6.0)
    out = p.apply_to_recipe(replace(old))
    assert (out.patch_w_mm, out.i1io_limits) == (6.0, C.LIMITS_NOW)
