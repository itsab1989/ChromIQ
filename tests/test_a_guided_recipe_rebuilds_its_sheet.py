"""Restore Used Chart redraws a Guided chart as it was printed (item 60).

Guided has no margin boxes and hands the engine none, so the sheet is laid out
with the base margin on every side: 10 mm for the i1Pro, 5 mm for the CR30 and
the ColorMunki's triple density. The recipe stored with the chart said 6 mm
(4.1.3-beta.19 to 4.3.66), so its rebuild was another sheet: the letters moved
on every paper, the patches too on many. An i1iO chart without crosses and an
i1iSis chart on 127 x 178 mm had the same fault.

The stored recipe says the margins of the build now, and a chart stored with
the wrong ones is read as it was printed. Nothing else of the record changes,
and nothing at all of what is printed. The pages are the judge.
"""
from __future__ import annotations

import dataclasses
import hashlib
import importlib
import json
import os
import re
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from tests._barbieri_fixture import write_ti1                    # noqa: E402
from workflow.layout_engine.presets import (LayoutRecipe,        # noqa: E402
                                            recipe_as_printed)

CM3 = dict(triple_density=True, margin_mm=5, patch_scale=1.3,
           no_strip_limit=True)
#: (instrument, what Guided chose, does the recipe of 4.3.66 rebuild it?)
CASES = [("i1", dict(margin_mm=10, patch_scale=0.95), False),
         ("i1", dict(margin_mm=6, patch_scale=1.0), True),
         ("i1", dict(margin_mm=10, patch_scale=0.95,
                     disable_left_border=True), False),
         ("i1", dict(margin_mm=10, patch_scale=0.95, no_strip_limit=True,
                     chart_notes="notes"), False),
         ("p3", {}, True), ("CM", {}, True), ("CM", dict(double_density=True),
                                              True), ("CM", CM3, False),
         ("SS", {}, True), ("SS", dict(double_density=True), True),
         ("CR30", {}, False), ("CR30", dict(double_density=True), False),
         ("FD9", {}, True), ("IO2", {}, True),
         ("IO2", dict(i1io_layout="compact"), True),
         ("IO2", dict(i1io_crosses=False), False),
         ("IO2", dict(i1io_crosses=False, i1io_layout="compact"), False),
         ("XRISIS", {}, True), ("B100XY", {}, True)]
PAPERS = ["A4", "A4R", "A3", "Letter", "127x178"]


@pytest.fixture(autouse=True)
def _every_beta_on(monkeypatch):
    for name in ("fd9", "i1io", "isis", "barbieri"):
        support = importlib.import_module(f"workflow.{name}.support")
        monkeypatch.setattr(support, "_latched", True)


def _pages(result):
    import tifffile
    return [hashlib.sha256(tifffile.imread(str(p)).tobytes()).hexdigest()
            for p in result.tiff_paths]


def _guided(tmp_path, instrument, paper, chosen):
    """``(creator, params, the engine's kwargs, its result, the layout block
    the app stores with the chart)``, or a skip where no such sheet exists."""
    from data.patch_db import INSTRUMENT_DEFAULT_MARGIN
    from workflow.chart_creator import ChartCreator, ChartParams
    from workflow.layout_engine.chart import build_chart
    creator = ChartCreator.__new__(ChartCreator)
    creator._settings = creator._file_mgr = None
    params = ChartParams()
    for key, value in {
            "instrument": instrument, "paper": paper, "pages": 1,
            "stamp_commands": False, "tiff_dpi": 72, "patch_scale": 1.0,
            "is_manual": False, "target_name": "T",
            "margin_mm": INSTRUMENT_DEFAULT_MARGIN.get(instrument, 6),
            **({"fd9_patch_mm": 8.0, "fd9_gap_mm": 1.0}
               if instrument == "FD9" else {}), **chosen}.items():
        assert key in {f.name for f in dataclasses.fields(ChartParams)}, key
        setattr(params, key, value)
    kw = dict(creator._engine_build_kwargs(params), seed=4711,
              chart_date="2026-11-25")
    work = tmp_path / "guided"
    work.mkdir()
    ti1 = write_ti1(work / "c.ti1", 300)
    try:
        result = build_chart(ti1, work / "c", **kw)
    except ValueError as exc:
        pytest.skip(f"no such sheet: {exc}")
    creator._embed_layout_geometry(work, "c", result, params)
    doc = json.loads((work / "c.channels.json").read_text(encoding="utf-8"))
    return creator, params, kw, result, doc["layout"]


def _rebuilt(tmp_path, creator, params, kw, recipe: dict):
    from workflow.layout_engine.chart import build_chart
    r = LayoutRecipe.from_stored(dict(recipe))
    r.seed = 4711
    if r.instrument == "FD9":
        params = dataclasses.replace(params, layout_recipe=r)
        again = dict(creator._engine_build_kwargs(params), seed=4711)
    else:
        again = r.build_kwargs()
        again.update({k: kw[k] for k in ("side_stamp", "project",
                                         "rundescription") if k in kw})
    again["chart_date"] = "2026-11-25"
    work = tmp_path / f"again{len(list(tmp_path.iterdir()))}"
    work.mkdir()
    return build_chart(write_ti1(work / "c.ti1", 300), work / "c", **again)


def _as_4366(layout):
    """*layout* with the margins 4.3.66 stored."""
    recipe = layout["recipe"]
    if recipe["instrument"] == "B100XY":
        return layout
    mm = 5.0 if recipe["instrument"] == "XRISIS" else 6.0
    return {**layout, "recipe": {**recipe, **{
        f"margin_{side}": mm for side in ("top", "right", "bottom", "left")}}}


@pytest.mark.parametrize("paper", PAPERS)
@pytest.mark.parametrize(
    "instrument,chosen,right", CASES,
    ids=[" ".join([i, *c]) for i, c, _r in CASES])
def test_a_guided_chart_is_rebuilt_pixel_for_pixel(tmp_path, instrument,
                                                   chosen, right, paper):
    creator, params, kw, result, layout = _guided(tmp_path, instrument, paper,
                                                  chosen)
    printed = _pages(result)
    assert layout["margins_chosen_by_user"] is False
    # a chart made now: its recipe says the sheet itself
    assert recipe_as_printed(layout) == layout["recipe"]
    assert _pages(_rebuilt(tmp_path, creator, params, kw,
                           layout["recipe"])) == printed
    # one made by 4.3.66: read as it was printed
    old = _as_4366(layout)
    assert _pages(_rebuilt(tmp_path, creator, params, kw,
                           recipe_as_printed(old))) == printed
    # the recipe alone rebuilt another sheet
    if not right:
        assert _pages(_rebuilt(tmp_path, creator, params, kw,
                               old["recipe"])) != printed


SIX = {f"margin_{side}": 6.0 for side in ("top", "right", "bottom", "left")}


@pytest.mark.parametrize("layout", [
    {"recipe": {"instrument": "i1", "border": 10.0, **SIX}},
    {"recipe": {"instrument": "i1", "border": 10.0, **SIX},
     "margins_chosen_by_user": True},
    {"recipe": {"instrument": "IO2", "i1io_crosses": False, **SIX},
     "margins_chosen_by_user": False},
    {"recipe": {"instrument": "i1", "border": 10.0, **SIX, "margin_left": 9.0},
     "margins_chosen_by_user": False}, {}])
def test_a_recipe_that_does_not_say_guided_is_read_as_it_stands(layout):
    """A Manual chart's margins are the person's (no flag), and so is every
    chart of 4.1.3-beta.19, which does not say; an i1iO chart from before
    4.3.66 may follow a rule of its version; and margins that are not the 6 mm
    4.3.66 filled in are somebody's."""
    assert recipe_as_printed(layout) == layout.get("recipe", {})


@pytest.mark.parametrize("instrument,chosen,right", CASES[:1] + CASES[10:11]
                         + CASES[13:16])
def test_the_margins_are_the_only_field_that_changed(
        tmp_path, monkeypatch, instrument, chosen, right):
    from workflow.layout_engine import presets
    new = _guided(tmp_path, instrument, "A4", chosen)[4]
    (tmp_path / "guided").rename(tmp_path / "new")
    monkeypatch.setattr(presets, "guided_margin_fields", lambda recipe: {})
    old = _guided(tmp_path, instrument, "A4", chosen)[4]
    assert list(new) == list(old) and list(new["recipe"]) == list(old["recipe"])
    margins = {"margin_top", "margin_right", "margin_bottom", "margin_left"}
    assert {k: v for k, v in new.items() if k != "recipe"} == {
        k: v for k, v in old.items() if k != "recipe"}
    assert {k: v for k, v in new["recipe"].items() if k not in margins} == {
        k: v for k, v in old["recipe"].items() if k not in margins}
    assert (new == old) is right


@pytest.mark.parametrize("instrument,name", [("IO2", "i1io"),
                                             ("XRISIS", "isis")])
def test_with_the_beta_off_its_charts_are_read_as_they_stand(
        monkeypatch, instrument, name):
    """...and none of its code is loaded for it (tests/test_*_off_stale*)."""
    support = importlib.import_module(f"workflow.{name}.support")
    mm = 5.0 if instrument == "XRISIS" else 6.0
    recipe = {"instrument": instrument, "paper": "127x178", "i1io_limits": 2,
              "i1io_crosses": False, **{k: mm for k in SIX}}
    layout = {"recipe": recipe, "margins_chosen_by_user": False}
    assert recipe_as_printed(layout) != recipe
    monkeypatch.setattr(support, "_latched", False)
    assert recipe_as_printed(layout) == recipe


# ---- every reader of a stored recipe (S1 of the review) ---------------------

#: Raw readers of a chart's ``layout["recipe"]``: none lays anything out with
#: its margins. Everything else asks `recipe_as_printed`.
RAW_READERS = {
    "ui/dialogs/scanin_dialog.py": (3, "hexagons and the ring's width"),
    "ui/tabs/tab_measure.py": (1, "whether the strip letters are drawn"),
    "ui/tabs/tab_chart.py": (4, "the render dpi; the instrument, twice; a "
                                "person's own margins, never Guided's"),
    "workflow/margin_inspector.py": (1, "the instrument"),
    "workflow/patch_size_check.py": (2, "the instrument, the patch size"),
    "workflow/overhang.py": (2, "the helper markers, the instrument"),
    "workflow/hex_support.py": (2, "hexagons"),
    "workflow/layout_engine/presets.py": (1, "recipe_as_printed itself"),
}


READ = re.compile(r"""(?:layout|lay|\{\})\)?(?:\.get\(["']recipe["']"""
                  r"""|\["recipe"\](?! =))""")


def test_every_other_reader_asks_for_the_recipe_as_printed():
    root = Path(__file__).resolve().parent.parent
    got = {}
    for top in ("core", "ui", "workflow"):
        for f in sorted((root / top).rglob("*.py")):
            n = sum(len(READ.findall(line)) for line in
                    f.read_text(encoding="utf-8").splitlines()
                    if "isinstance(" not in line)
            if n:
                got[f.relative_to(root).as_posix()] = n
    assert got == {k: n for k, (n, _why) in RAW_READERS.items()}


def _stored_by_4366(tmp_path, instrument, paper, chosen):
    _c, _p, kw, result, layout = _guided(tmp_path, instrument, paper, chosen)
    side = tmp_path / "guided" / "c.channels.json"
    doc = json.loads(side.read_text(encoding="utf-8"))
    doc["layout"] = _as_4366(layout)
    side.write_text(json.dumps(doc), encoding="utf-8")
    return side, kw, result


@pytest.mark.parametrize("instrument,paper,chosen,patches", [
    ("CR30", "A4R", {}, (368, 345)),          # (the sheet, what 6 mm makes)
    ("i1", "A4", dict(margin_mm=10, patch_scale=0.95), None),
    ("i1", "Letter", dict(margin_mm=10, patch_scale=0.95), None)])
def test_the_editor_lays_a_stored_guided_chart_out_as_it_is(
        tmp_path, instrument, paper, chosen, patches):
    from workflow.layout_engine import geometry, instruments, papers

    def on_a_page(kw):
        return geometry.patches_per_sheet(
            instruments.geom_from_build_kwargs(kw), *papers.piece_mm_of(kw))
    side, kw, result = _stored_by_4366(tmp_path, instrument, paper, chosen)
    recipe = LayoutRecipe.from_channels_json(side)
    raw = LayoutRecipe.from_stored(
        json.loads(side.read_text(encoding="utf-8"))["layout"]["recipe"])
    got = on_a_page(recipe.build_kwargs()), on_a_page(raw.build_kwargs())
    assert got[0] == on_a_page(kw) != got[1]
    assert patches is None or got == patches
    # ...and the notices about the chart on screen
    from types import SimpleNamespace
    from ui.tabs.tab_chart import TabChart
    me = SimpleNamespace(
        _margin_ti2=result.ti2_path,
        _settings=SimpleNamespace(apply_indicator_style=lambda r: r))
    for attr in ("_manual_layout_panel", "_notice_recipe_cache"):
        setattr(me, attr, None)
    me._current_layout_recipe = lambda *a, **k: None
    shown = TabChart._notice_layout_recipe(me)
    assert shown is not None and shown.margin_top == recipe.margin_top
