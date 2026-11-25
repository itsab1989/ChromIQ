"""THE RECORD OF A DIVIDED i1iO SHEET (the new chart layout, step 5b).

One writer for every place that stores a chart's recipe, one reader for every
place that takes it from there, and no division is ever believed that ChromIQ
would not make: a damaged, foreign or newer record is refused in words, and
START does not open the table.
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
from workflow.layout_engine.presets import (LayoutRecipe, build_kwargs_as_built,
                                            default_recipe, stored_recipe)

ROOT = Path(__file__).resolve().parent.parent
A3 = "v1;sheet=297x420;piece=210x297;turn=1;at=0,0/0,210;cut_x=;cut_y=210"
A2 = ("v1;sheet=420x594;piece=210x297;turn=0;at=0,297/0,0/210,297/210,0;"
      "cut_x=210;cut_y=297")


@pytest.fixture(autouse=True)
def i1io_on():
    from workflow.i1io import support
    before = support._latched
    support.set_enabled_for_this_process(True)
    try:
        yield
    finally:
        support._latched = before


# ---- one writer --------------------------------------------------------------------

def test_every_writer_of_a_charts_recipe_uses_the_one_function():
    """Whoever stores ``layout["recipe"]`` with a chart stores what its build
    resolved: an assignment of anything but `stored_recipe(...)` fails here."""
    found = []
    for top in ("core", "ui", "workflow"):
        for f in sorted((ROOT / top).rglob("*.py")):
            src = f.read_text(encoding="utf-8")
            if '"recipe"' not in src:
                continue
            for n in ast.walk(ast.parse(src)):
                for t in getattr(n, "targets", ()) if isinstance(
                        n, ast.Assign) else ():
                    if (isinstance(t, ast.Subscript)
                            and isinstance(t.slice, ast.Constant)
                            and t.slice.value == "recipe"
                            and getattr(t.value, "id", "") not in (
                                "snap", "parts")):      # (not a chart's record)
                        call = n.value
                        name = getattr(getattr(call, "func", None), "id", "")
                        found.append((f.relative_to(ROOT).as_posix(), name))
    assert sorted(found) == [
        ("ui/dialogs/ti2_relayout_dialog.py", "stored_recipe"),
        ("workflow/chart_creator.py", "stored_recipe"),
        ("workflow/chart_creator.py", "stored_recipe")]


def _editor(tmp_path, recipe, n):
    import ui.dialogs.ti2_relayout_dialog as M
    from PyQt6.QtCore import QSettings
    from core.argyll_runner import ArgyllRunner
    from core.settings import AppSettings
    from tests.test_i1io_chart import _ti1
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "e.ini"), QSettings.Format.IniFormat)
    s.set("use_chromiq_layout_engine", True)
    ed = M.Ti2RelayoutDialog(ArgyllRunner(s), s)
    ed._engine_panel.set_recipe(recipe)
    ed._engine_ti1 = _ti1(tmp_path / "in.ti1", n)
    return ed


@pytest.mark.parametrize("paper,per_piece,pages", [("A3", 528, 2),
                                                   ("A2", 528, 2),
                                                   ("11x17", 506, 3)])
def test_the_patch_set_editors_chart_is_its_pieces_for_every_reader(
        qtbot, tmp_path, monkeypatch, paper, per_piece, pages):
    """The editor is the third writer (the review's blocker): saved from it,
    the chart is read as pieces everywhere, also by a later version."""
    ed = _editor(tmp_path, replace(default_recipe("IO2", paper), dpi=72), 1056)
    qtbot.addWidget(ed)
    out = tmp_path / "out"
    out.mkdir()
    ed._write_engine_chart_into(out, "x")
    doc = json.loads((out / "x.channels.json").read_text(encoding="utf-8"))
    rec_d = doc["layout"]["recipe"]
    plan = P.record_of(out / "x.ti2")
    assert plan is not None and rec_d["i1io_pieces"] == plan.token
    assert len(list(out.glob("x_*.tif"))) == pages
    from workflow.layout_engine import geometry, instruments
    monkeypatch.setattr(F, "LARGE_PIECES", True)           # a later rule
    for kw in (LayoutRecipe.from_channels_json(
                   out / "x.channels.json").build_kwargs(),
               build_kwargs_as_built(rec_d),
               LayoutRecipe.from_stored(rec_d).build_kwargs()):
        w, h = papers.piece_mm_of(kw)
        assert (w, h) == pytest.approx(plan.piece_mm)
        g = instruments.geom_from_build_kwargs(kw)
        assert geometry.patches_per_sheet(g, w, h) == per_piece
    from workflow.margin_inspector import measure_from_engine
    got = measure_from_engine(out / "x.channels.json")
    assert got is not None and got[0] is not None


def test_the_editors_pages_are_sheets_like_the_new_chart_windows(
        qtbot, tmp_path, monkeypatch):
    import ui.dialogs.ti2_relayout_dialog as M
    ed = _editor(tmp_path, replace(default_recipe("IO2", "A3"), dpi=72), 600)
    qtbot.addWidget(ed)
    assert ed._engine_cap_per_page() == 1056
    from types import SimpleNamespace
    dlg = SimpleNamespace(
        _settings=ed._settings,
        _initial_recipe=ed._engine_panel.get_recipe().to_dict())
    assert M._NewChartDialog._engine_cap_per_page(dlg) == 1056
    # filled to one sheet: 1056 patches, and drawn it shows one sheet
    monkeypatch.setattr(ed, "_engine_active", lambda: True)
    ed._engine_preview_timer.stop()
    for k in range(1056):
        ed._grid.addItem(ed._grid_item(
            ((k * 7) % 101, (k * 13) % 101, (k * 29) % 101)))
    ed._on_engine_pages_changed(1)
    assert ed._grid.count() == 1056
    shown = []
    monkeypatch.setattr(ed, "_sync_pages_spin", shown.append)
    ed._engine_preview_timer.stop()
    ed._do_engine_preview()
    assert shown == [1] and len(ed._engine_tiffs) == 2
    # two sheets more: said in sheets
    monkeypatch.setattr(M.G, "enforce_min_distance",
                        lambda fresh, *a, **k: fresh)
    ed._on_engine_pages_changed(2)
    assert ed._grid.count() == 2112
    assert "2 sheets" in ed._status.text()
    ed._engine_preview_timer.stop()


# ---- one reader -----------------------------------------------------------------------

def test_a_stored_chart_without_the_record_is_one_piece_at_every_door(
        monkeypatch):
    """Also under a rule that divides its sheet today: the chart was made as
    one page and is described and drawn again as one."""
    rec = replace(default_recipe("IO2", "230x320"), dpi=72).to_dict()
    rec.pop("i1io_pieces", None)
    monkeypatch.setattr(F, "REACH_MM", F.Fact((300.0, 220.0), "test", F.OURS))
    P._plan.cache_clear()
    try:
        assert papers.is_divided(LayoutRecipe.from_dict(rec))   # today's rule
        for source in (LayoutRecipe.from_stored(rec),
                       build_kwargs_as_built(rec)):
            assert not papers.is_divided(source)
            assert papers.piece_mm_of(source) == (230.0, 320.0)
    finally:
        P._plan.cache_clear()


#: Who may build a recipe from a dict that is NOT a chart's record.
FROM_DICT = {
    ("ui/tabs/tab_chart.py", "the stored defaults, the ui state, presets"): 6,
    ("ui/dialogs/ti2_relayout_dialog.py", "the New chart window's own"): 1,
    ("ui/dialogs/settings_dialog.py", "the layout store"): 1,
    ("workflow/preset_eligibility.py", "built-in presets"): 2,
    ("workflow/layout_engine/presets.py", "from_stored, the preset stores"): 4,
}


def test_the_readers_of_a_charts_record_use_the_one_function():
    """`LayoutRecipe.from_dict` in a new place fails here until somebody says
    that what it reads is not a chart's record (that is `from_stored`)."""
    got: "dict[str, int]" = {}
    for top in ("core", "ui", "workflow"):
        for f in sorted((ROOT / top).rglob("*.py")):
            n = len(re.findall(r"(?<!\w)(?:LayoutRecipe|cls)\.from_dict\(",
                               f.read_text(encoding="utf-8")))
            rel = f.relative_to(ROOT).as_posix()
            if n and (rel in {k for k, _w in FROM_DICT}
                      or "LayoutRecipe.from_dict(" in f.read_text("utf-8", encoding="utf-8")):
                got[rel] = n
    assert got == {k: v for (k, _w), v in FROM_DICT.items()}
    src = (ROOT / "ui/tabs/tab_chart.py").read_text(encoding="utf-8")
    for marker in ("self._restored_exact_recipe = recipe",
                   "self._notice_recipe_cache = (stamp, built)"):
        at = src.index(marker)
        assert "from_stored(" in src[at - 2500:at], marker
        # …held against the chart's own files
        assert "from_stored(rec_dict, ti2_path)" in src[at - 2500:at] or \
            "from_stored(rec, ti2)" in src[at - 2500:at], marker
    src = (ROOT / "ui/tabs/tab_measure.py").read_text(encoding="utf-8")
    assert "build_kwargs_as_built(recipe, ti2_path)" in src


def test_stored_recipe_carries_what_the_build_resolved():
    from types import SimpleNamespace
    rec = default_recipe("IO2", "A3")
    assert stored_recipe(rec, SimpleNamespace(i1io_pieces=A3))[
        "i1io_pieces"] == A3
    assert stored_recipe(rec, SimpleNamespace()) == rec.to_dict()


# ---- a record that cannot be trusted --------------------------------------------------

BAD = {
    "larger than the reach": A3.replace("210x297", "400x500"),
    "lying": A3.replace("210x297", "297x210"),
    "off the sheet": A3.replace("0,210;", "0,310;"),
    "negative": A3.replace("at=0,0", "at=-5,0"),
    "overlapping": A3.replace("0,210;cut_x=;cut_y=210",
                              "0,100;cut_x=;cut_y=100"),
    "turn that does not fit": A3.replace("turn=1", "turn=0"),
    "turn 3": A3.replace("turn=1", "turn=3"),
    "not a number": A3.replace("0,210;", "0,nan;"),
    "no end": A3.replace("297x420", "297xinf"),
    "one place twice": A3.replace("0,210;", "0,0;"),
    "another order": A3.replace("0,0/0,210", "0,210/0,0"),
    "a place left out": A2.replace("/210,0", ""),
    "no cut": A3.replace("cut_y=210", "cut_y="),
    "a cut too many": A3.replace("cut_x=", "cut_x=100"),
    "a sheet that is one piece": (
        "v1;sheet=210x297;piece=105x148.5;turn=0;at=0,148.5/0,0/105,148.5/105,0"
        ";cut_x=105;cut_y=148.5"),
    "too narrow": ("v1;sheet=297x420;piece=50x297;turn=1;at="
                   + "/".join(f"0,{50 * k}" for k in range(8))
                   + ";cut_x=;cut_y=" + ",".join(
                       str(50 * k) for k in range(1, 9))),
    # (full grids, each wrong in one thing only)
    "a grid of lying pieces": (
        "v1;sheet=297x420;piece=297x210;turn=0;at=0,210/0,0;cut_x=;cut_y=210"),
    "a grid of pieces beyond the reach": (
        "v1;sheet=420x594;piece=297x420;turn=1;at=0,0/0,297;cut_x=;cut_y=297"),
    "a grid longer than its sheet": (
        "v1;sheet=297x420;piece=148.5x210;turn=1;at=0,0/0,148.5/0,297;"
        "cut_x=210;cut_y=148.5,297"),
    "a grid longer than any roll": (
        "v1;sheet=297x29820;piece=210x297;turn=1;at="
        + "/".join(f"0,{210 * k}" for k in range(142)) + ";cut_x=;cut_y="
        + ",".join(str(210 * k) for k in range(1, 142))),
    "a newer version": A3.replace("v1;", "v2;"),
    "nothing": "v1;", "words": "pieces",
}


@pytest.mark.parametrize("why", sorted(BAD))
def test_a_damaged_division_is_never_believed(tmp_path, why):
    from tests.test_i1io_chart import _ti1
    from workflow.layout_engine import chart
    token = BAD[why]
    assert P.from_token(token) is None
    with pytest.raises(P.PieceRecordError):
        P.stored_plan(token)
    k = default_recipe("IO2", "A3").build_kwargs()
    k.update(dpi=72, seed=1, i1io_pieces=token)
    for ask in (papers.is_divided, papers.piece_mm_of, papers.pieces_on):
        with pytest.raises(P.PieceRecordError):
            ask(k)                              # described as nothing at all
    with pytest.raises(C.I1ioSheetRefused) as e:
        chart.build_chart(_ti1(tmp_path / "c.ti1", 60), tmp_path / "c", **k)
    assert "cannot be trusted" in str(e.value)
    assert sorted(p.name for p in tmp_path.iterdir()) == ["c.ti1"]
    _shift, warn = C.preview_checks({**k, "area_target_count": 60})
    assert warn and "cannot be trusted" in warn[0]


def test_a_division_of_another_sheet_is_refused_too(tmp_path):
    from tests.test_i1io_chart import _ti1
    from workflow.layout_engine import chart
    k = default_recipe("IO2", "A2").build_kwargs()
    k.update(dpi=72, seed=1, i1io_pieces=A3)
    with pytest.raises(C.I1ioSheetRefused):
        chart.build_chart(_ti1(tmp_path / "c.ti1", 60), tmp_path / "c", **k)
    with pytest.raises(P.PieceRecordError):
        P.stored_plan(A3, (420.0, 594.0))


def test_every_division_the_rule_makes_is_believed():
    """…and one it would not choose today, but could have, is as well."""
    import itertools
    sizes = list(itertools.product(range(60, 1300, 97), range(60, 1300, 89)))
    sizes += [(297, 420), (420, 594), (594, 841), (841, 1189), (215.9, 355.6),
              (304.8, 457.2), (609.6, 594), (1117.6, 3000), (244.7, 250.8),
              (298, 420), (329, 483)]
    plans = 0
    for s in sizes:
        plan = P.plan_for(s)
        if plan is not None:
            plans += 1
            assert P.from_token(plan.token) is not None, plan.token
            assert P.from_token(plan.token).token == plan.token
    assert plans > 100
    four = ("v1;sheet=297x420;piece=148.5x210;turn=0;at=0,210/0,0/148.5,210/"
            "148.5,0;cut_x=148.5;cut_y=210")
    assert P.plan_for((297.0, 420.0), four).count == 4


def _chart(tmp_path, **kw):
    from tests.test_i1io_pieces import _build
    _build(tmp_path, "A3", n=700, **kw)
    return tmp_path / "c.ti2", tmp_path / "c.i1io.json"


def _edit(side, fn):
    doc = json.loads(side.read_text(encoding="utf-8"))
    fn(doc)
    side.write_text(json.dumps(doc), encoding="utf-8")


SPOIL = {
    "the side file says another division":
        lambda t, s: _edit(s, lambda d: d["sheet"].update(token=A2)),
    "the side file's token is cut off":
        lambda t, s: _edit(s, lambda d: d["sheet"].update(token=A3[:40])),
    "no sheet block": lambda t, s: _edit(s, lambda d: d.pop("sheet")),
    "a one-page side file beside a divided .ti2":
        lambda t, s: _edit(s, lambda d: d.update(schema=1, sheet=None)),
    "a newer side file": lambda t, s: _edit(s, lambda d: d.update(schema=3)),
    "the .ti2's is damaged": lambda t, s: t.write_text(
        t.read_text(encoding="utf-8").replace("cut_y=210", "cut_y=200"),
        encoding="utf-8"),
    "a piece named as another": lambda t, s: _edit(
        s, lambda d: d["pages"][1]["piece"].update(piece=1)),
    "a piece standing elsewhere": lambda t, s: _edit(
        s, lambda d: d["pages"][1]["piece"].update(place_mm=[0.0, 0.0])),
    "pages of another size": lambda t, s: _edit(
        s, lambda d: d.update(paper_mm=[297.0, 420.0])),
    "not a file that can be read": lambda t, s: s.write_text("{", encoding="utf-8"),
    "the sheet block is a word": lambda t, s: _edit(
        s, lambda d: d.update(sheet="x")),
    "the sheet block is a list": lambda t, s: _edit(
        s, lambda d: d.update(sheet=[1])),
    "no number for the paper": lambda t, s: _edit(
        s, lambda d: d.update(paper_mm=[float("nan"), 297.0])),
    "no number for a place": lambda t, s: _edit(
        s, lambda d: d["pages"][1]["piece"].update(
            place_mm=[float("nan"), 210.0])),
    "half a paper": lambda t, s: _edit(s, lambda d: d.update(paper_mm=[210.0])),
    "no pages": lambda t, s: _edit(s, lambda d: d.update(pages=[])),
    "pages of another kind": lambda t, s: _edit(
        s, lambda d: d.update(pages="two")),
    "one page is gone": lambda t, s: _edit(s, lambda d: d["pages"].pop()),
    "the side file is a list": lambda t, s: s.write_text("[]", encoding="utf-8"),
    "the side file is nothing": lambda t, s: s.write_text("null", encoding="utf-8"),
}


@pytest.mark.parametrize("how", sorted(SPOIL))
def test_a_charts_record_must_agree_with_itself(tmp_path, how):
    ti2, side = _chart(tmp_path)
    assert P.record_of(ti2).token == A3
    SPOIL[how](ti2, side)
    with pytest.raises(P.PieceRecordError):
        P.record_of(ti2)


FOUR = ("v1;sheet=297x420;piece=148.5x210;turn=0;at=0,210/0,0/148.5,210/"
        "148.5,0;cut_x=148.5;cut_y=210")
#: What channels.json says of an A3 chart of two pieces -> what is believed.
STORED = {"the same": (A3, A3), "nothing (a chart of the editor before)":
          ("", A3), "another sound division": (FOUR, P.NOT_TRUSTED),
          "one piece": ("one", P.NOT_TRUSTED),
          "damaged": (A3[:30], P.NOT_TRUSTED),
          "a newer version": (A3.replace("v1", "v2"), P.NOT_TRUSTED),
          "another sheet's": (A2, P.NOT_TRUSTED)}


@pytest.mark.parametrize("what", sorted(STORED))
def test_a_stored_recipe_is_held_against_the_charts_own_record(tmp_path, what):
    """One truth: the chart's side file and .ti2. Every reader of
    channels.json gets their division, or nothing at all, and Restore's build
    draws that division or is refused in words."""
    from workflow.layout_engine import chart, presets
    token, want = STORED[what]
    ti2, _side = _chart(tmp_path, project="Proof")
    d = replace(default_recipe("IO2", "A3"), dpi=72, seed=1).to_dict()
    if token:
        d["i1io_pieces"] = token
    ch = tmp_path / "c.channels.json"
    ch.write_text(json.dumps({"layout": {"engine": "chromiq", "recipe": d,
                                         "seed": 1}}), encoding="utf-8")
    recs = [LayoutRecipe.from_channels_json(ch),
            LayoutRecipe.from_stored(d, ti2)]
    for r in recs:
        assert r.i1io_pieces == want
    kws = [r.build_kwargs() for r in recs]
    kws.append(build_kwargs_as_built(d, ti2))
    for kw in kws:
        if want == A3:
            assert papers.piece_mm_of(kw) == (210.0, 297.0)
            assert papers.pieces_on(kw) == 2
        else:
            for ask in (papers.piece_mm_of, papers.pieces_on,
                        papers.is_divided):
                with pytest.raises(ValueError):
                    ask(kw)
    out = tmp_path / "again"
    out.mkdir()
    from tests.test_i1io_chart import _ti1
    ti1 = _ti1(out / "c.ti1", 700)
    if want == A3:
        r = chart.build_chart(ti1, out / "c", **{**kws[1], "dpi": 72})
        assert r.i1io_pieces == A3 and len(r.tiff_paths) == 2
    else:
        with pytest.raises(C.I1ioSheetRefused) as e:
            chart.build_chart(ti1, out / "c", **{**kws[1], "dpi": 72})
        assert "cannot be trusted" in str(e.value)
        assert [p.name for p in out.iterdir()] == ["c.ti1"]


@pytest.mark.parametrize("what", ["a one piece chart with a division",
                                  "a damaged side file", "no other file"])
def test_the_other_ways_round(tmp_path, what):
    from tests.test_i1io_pieces import _build
    d = replace(default_recipe("IO2", "A4"), dpi=72).to_dict()
    _build(tmp_path, "A4", n=60)
    ti2 = tmp_path / "c.ti2"
    if what == "a damaged side file":
        (tmp_path / "c.i1io.json").write_text("{", encoding="utf-8")
        assert LayoutRecipe.from_stored(d, ti2).i1io_pieces == P.NOT_TRUSTED
    elif what == "no other file":
        assert LayoutRecipe.from_stored(
            {**d, "i1io_pieces": A3}, tmp_path / "x.ti2").i1io_pieces == A3
        assert LayoutRecipe.from_stored(
            d, tmp_path / "x.ti2").i1io_pieces == "one"
    else:
        assert LayoutRecipe.from_stored(d, ti2).i1io_pieces == "one"
        assert LayoutRecipe.from_stored(
            {**d, "i1io_pieces": A3}, ti2).i1io_pieces == P.NOT_TRUSTED


def test_what_describes_a_chart_says_nothing_of_one_it_cannot_trust(
        qtbot, tmp_path):
    """Create Chart's own readers (the last page, its capacity, the helper
    markers): no 297 x 420 page, no exception."""
    from types import SimpleNamespace
    from ui.tabs.tab_chart import TabChart
    ti2, _side = _chart(tmp_path, project="Proof")
    d = replace(default_recipe("IO2", "A3"), dpi=72, seed=1).to_dict()
    for token, per in ((A3, 528), (FOUR, 0), ("one", 0)):
        (tmp_path / "c.channels.json").write_text(json.dumps(
            {"layout": {"engine": "chromiq", "seed": 1, "dpi": 72,
                        "recipe": {**d, "i1io_pieces": token}}}),
            encoding="utf-8")
        me = SimpleNamespace(
            _recipe_rebuilds_its_own_sheet=lambda t: True,
            _PARTIAL_PAGE_MIN_FILL=0.5)
        assert TabChart._last_page_capacity(me, ti2) == per
        blank = TabChart._partial_last_page_blank(me, ti2)
        assert blank is None or per


def test_a_record_without_pages_is_none_also_without_the_ti2(tmp_path):
    ti2, side = _chart(tmp_path)
    ti2.unlink()
    assert P.record_of(ti2).token == A3
    _edit(side, lambda d: d.update(pages=[]))
    with pytest.raises(P.PieceRecordError):
        P.record_of(ti2)


def test_an_ordinary_chart_has_no_record(tmp_path):
    from tests.test_i1io_pieces import _build
    _build(tmp_path, "A4", n=60)
    assert P.record_of(tmp_path / "c.ti2") is None
    assert P.record_of(tmp_path / "none.ti2") is None


# ---- START ------------------------------------------------------------------------------

from tests.i1io_table.test_window_in_the_measure_tab import (  # noqa: E402,F401
    beta, start, tab, table_run)


@pytest.mark.parametrize("how", ["damaged token", "keyword alone", "newer",
                                 "a word", "no pages"])
def test_start_does_not_open_the_table(tab, beta, tmp_path, monkeypatch, how):
    from PyQt6.QtWidgets import QMessageBox
    run, _sheet = table_run(tmp_path)
    ti2 = run.chart_ti2
    side = ti2.with_name(ti2.name[:-4] + ".i1io.json")
    if how == "keyword alone":
        ti2.write_text(ti2.read_text(encoding="utf-8").replace(
            "NUMBER_OF_FIELDS", f'{P.KEYWORD} "{A3}"\nNUMBER_OF_FIELDS', 1),
            encoding="utf-8")
    elif how == "newer":
        _edit(side, lambda d: d.update(schema=3))
    elif how == "a word":
        _edit(side, lambda d: d.update(schema=2, sheet="x"))
    elif how == "no pages":
        _edit(side, lambda d: d.update(schema=2, sheet={"token": A3}))
    else:
        _edit(side, lambda d: d.update(schema=2, sheet={"token": A3[:30]}))
    said = []
    monkeypatch.setattr(QMessageBox, "exec",
                        lambda box: said.append((box.text(),
                                                 box.informativeText())) or 0)
    start(tab, run, monkeypatch)
    assert getattr(tab, "_table_window", None) is None
    if how == "newer":
        from workflow import measurement_messages as M
        assert said == [M.M_I1IO_CHART_NEWER.render(
            sent=" Nothing was sent to the table.")]
        return
    assert len(said) == 1 and "cannot be trusted" in said[0][0]
    assert "did not move" in said[0][1]
    assert "cut into pieces" not in "".join(said[0])


def test_the_same_chart_of_this_version_is_taken(tab, beta, tmp_path,
                                                 monkeypatch):
    """Schema 2 with a sound record, and no schema 3: START goes on."""
    run, sheet = table_run(tmp_path)
    start(tab, run, monkeypatch)
    assert getattr(tab, "_table_window", None) is not None


def test_create_chart_says_it_once(qtbot, tmp_path, monkeypatch):
    """A chart of a newer ChromIQ opened in Create Chart: its own window, once
    for the file as it is; an ordinary one says nothing, and with the Beta off
    nothing is read."""
    from types import SimpleNamespace
    from PyQt6.QtWidgets import QApplication
    from ui.tabs import tab_chart
    from workflow.i1io import support
    said = []
    monkeypatch.setattr(tab_chart, "inform", lambda w, t, b: said.append((t, b)))
    ti2, side = _chart(tmp_path)
    me = SimpleNamespace()

    def ask():
        tab_chart.TabChart._say_if_chart_is_newer(me, ti2)
        QApplication.processEvents()
    ask()
    assert said == []
    _edit(side, lambda d: d.update(schema=3))
    support.set_enabled_for_this_process(False)
    ask()
    assert said == []
    support.set_enabled_for_this_process(True)
    ask()
    ask()
    assert len(said) == 1 and "newer version of ChromIQ" in said[0][0]
    assert "Please update ChromIQ" in said[0][1] and "sent" not in said[0][1]
    src = (ROOT / "ui/tabs/tab_chart.py").read_text(encoding="utf-8")
    assert src.count("self._say_if_chart_is_newer(") == 2


# ---- what the review's faults found nobody looking at -----------------------------------

@pytest.mark.parametrize("sheet,divided", [
    ((230.0, 320.0), False), ((230.1, 320.0), True), ((230.0, 320.1), True),
    ((320.0, 230.0), False), ((320.1, 230.0), True)])
def test_the_reach_is_the_reach(sheet, divided):
    assert (P.plan_for(sheet) is not None) is divided


def test_every_pieces_own_place_is_in_the_side_file(tmp_path):
    from tests.test_i1io_pieces import _build
    _build(tmp_path, "A2", n=2112)
    doc = json.loads((tmp_path / "c.i1io.json").read_text(encoding="utf-8"))
    plan = P.from_token(A2)
    assert [tuple(p["piece"]["place_mm"]) for p in doc["pages"]] == list(
        plan.places)


def test_a_listed_paper_is_named_within_a_tenth(tmp_path):
    assert papers.code_of((297.05, 419.95)) == "A3"
    assert papers.code_of((298.0, 420.0)) == "298x420"
    assert papers.code_of((297.2, 420.0)) == "297.2x420"


@pytest.mark.parametrize("paper", ["500x50", "59x330"])
def test_the_preview_says_an_impossible_sheet(paper):
    k = default_recipe("IO2", paper).build_kwargs()
    _shift, warn = C.preview_checks({**k, "area_target_count": 60})
    assert len(warn) == 1
    with pytest.raises(C.I1ioSheetRefused):
        C.check_sheet_size({**k, "instrument": "IO2"})


def test_trimmed_letter_pieces_from_a_long_roll():
    """Letter pieces are among the cuts (a roll that holds them best)."""
    got = {(c[3], c[4], c[5]) for c in P._candidates(215.9, 1500.0, False)}
    assert any(cw == 215.9 and ch == 279.4 for _r, cw, ch in got)


def test_a_stored_recipe_without_a_division_is_one_piece_with_the_beta_off():
    """(the final review, D1): never divided by today's rule."""
    from workflow.i1io import support
    from workflow.layout_engine.presets import LayoutRecipe, default_recipe
    d = {**default_recipe("IO2", "A3").to_dict(), "i1io_pieces": ""}
    for on in (False, True):
        support.set_enabled_for_this_process(on)
        assert LayoutRecipe.from_stored(d).i1io_pieces == "one"
    support.set_enabled_for_this_process(True)
