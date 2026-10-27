"""The turned i1Profiler export asks the SHEET whether it has spacers, not the
recipe's "Edge spacers" box (4.3.18; forum, pharmacist, post 149886).

His chart: Create Chart > Manual, i1Pro, A4, "Prioritise patch size, then fit
to page", 8 x 10 mm, scale 1, strip letters on, row letters off, clip border
On, Spacers None: 504 patches, 21 strips of 24. 4.3.17 wrote no ``.txf`` and
said *"the chart has spacers at the ends of its strips"*. He had removed them,
and he was right: "Edge spacers (bracket each strip)" was still ticked under
Expert Options, and the engine draws an edge spacer only on a chart that has
spacers at all (``raster.render_pages``), with a spacer width of 0 when Spacers
is None, so the box changes nothing on that sheet. Measured: the TIFFs made
with and without the box differ only in the printed project name.

The box is ticked by every built-in i1Pro preset, by every Guided chart (whose
recipe stores the build's own value, which turns edge spacers on for strip
readers) and by anything loaded from them, so a sheet without a single spacer
was refused for spacers it did not have.

Also here: pharmacist's suggestion (post 149890), "Prioritise chart area"
with a fixed grid: it qualifies on A4, and on a page tall enough to stretch the
strips past an i1Profiler row the note now says which setting to change.
"""
from __future__ import annotations

import inspect
import json
import os
import random
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from workflow import i1profiler_turned as T                       # noqa: E402


def _ti1(path: Path, n: int) -> Path:
    rnd = random.Random(1)
    lines = ["CTI1", "", 'DESCRIPTOR "t"', 'COLOR_REP "RGB"', "",
             "NUMBER_OF_FIELDS 7", "BEGIN_DATA_FORMAT",
             "SAMPLE_ID RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z", "END_DATA_FORMAT",
             "", f"NUMBER_OF_SETS {n}", "BEGIN_DATA"]
    for i in range(1, n + 1):
        r, g, b = (round(rnd.uniform(0, 100), 4) for _ in range(3))
        lines.append(f"{i} {r} {g} {b} 10 10 10")
    path.write_text("\n".join(lines + ["END_DATA", ""]), encoding="utf-8")
    return path


def _chart(folder: Path, name: str, n: int, *, store="recipe", **kw) -> Path:
    """A real engine chart, stored as Create Chart stores it. *store* =
    "recipe" is the Manual door (the panel's recipe), "kwargs" the Guided
    door (`LayoutRecipe.from_build_kwargs` of the resolved build)."""
    from workflow.layout_engine.chart import build_from_recipe
    from workflow.layout_engine.presets import LayoutRecipe
    folder.mkdir(parents=True, exist_ok=True)
    src = _ti1(folder / f"{name}.ti1", n)
    args = dict(instrument="i1", paper="A4", seed=4242,
                layout_mode="patch_first", patch_w_mm=8.0, patch_h_mm=10.0,
                pscale=1.0, show_strip_indicators=True,
                show_row_indicators=False, clip_border=True)
    args.update(kw)
    res, used = build_from_recipe(src, folder / name, LayoutRecipe(**args))
    sj = folder / f"{name}.strips.json"
    lay = json.loads(sj.read_text(encoding="utf-8"))
    rec = (used.to_dict() if store == "recipe"
           else LayoutRecipe.from_build_kwargs(used.build_kwargs()).to_dict())
    lay.update(engine="chromiq", engine_version=1, seed=res.seed, recipe=rec)
    (folder / f"{name}.channels.json").write_text(
        json.dumps({"layout": lay}), encoding="utf-8")
    sj.unlink()
    return folder / f"{name}.ti2"


@pytest.fixture(scope="module")
def charts(tmp_path_factory):
    d = tmp_path_factory.mktemp("pharmacist")
    return {
        # his chart, the box ticked (what 4.3.17 refused)
        "edge": _chart(d / "edge", "testprofiel", 504, spacer_mode="none",
                       edge_spacers=True),
        # the same chart, the box clear (what 4.3.17 accepted)
        "plain": _chart(d / "plain", "testprofiel", 504, spacer_mode="none",
                        edge_spacers=False),
        # the Guided door: the resolved build, edge spacers forced on
        "guided": _chart(d / "guided", "testprofiel", 504, spacer_mode="none",
                         store="kwargs"),
        # a chart that really has spacers, with and without the box
        "spaced_edge": _chart(d / "se", "spaced", 300, spacer_mode="colored",
                              edge_spacers=True),
        "spaced_bw": _chart(d / "sb", "spacedbw", 300, spacer_mode="bw",
                            edge_spacers=False),
    }


def _layout(ti2: Path) -> dict:
    return json.loads(ti2.with_name(f"{ti2.stem}.channels.json").read_text(
        encoding="utf-8"))["layout"]


def test_his_exact_chart_qualifies_for_both_families(charts):
    lay = _layout(charts["edge"])
    assert lay["recipe"]["edge_spacers"] is True
    assert lay["recipe"]["spacer_mode"] == "none"
    plan = T.plan_for(charts["edge"])
    assert plan.reasons == []
    assert plan.families == ["i1Pro 2", "i1Pro 3"], plan.family_reasons
    assert (plan.rows, plan.columns) == (21, 24)
    assert plan.patch_len_mm == pytest.approx(10.0, abs=0.01)


def test_the_box_does_not_change_the_sheet_or_the_order(charts):
    """Ticked or not, the same rectangles, the same strips, the same order."""
    a, b = _layout(charts["edge"]), _layout(charts["plain"])
    rect = lambda l: [(p["x"], p["y"], p["w"], p["h"], p.get("page", 0))
                      for p in l["patches"]]
    assert rect(a) == rect(b)
    assert a["strips"] == b["strips"]
    pa, pb = T.plan_for(charts["edge"]), T.plan_for(charts["plain"])
    assert [o[0] for o in pa.order] == [o[0] for o in pb.order]
    assert pa.families == pb.families


def test_the_sheets_differ_only_in_the_printed_name(charts):
    """The pixels: only the record strip's project name may differ, and here
    both are called the same, so nothing does."""
    from PIL import Image, ImageChops
    ta = sorted(charts["edge"].parent.glob("*.tif"))
    tb = sorted(charts["plain"].parent.glob("*.tif"))
    assert ta and len(ta) == len(tb)
    for x, y in zip(ta, tb):
        diff = ImageChops.difference(Image.open(x).convert("RGB"),
                                     Image.open(y).convert("RGB"))
        assert diff.getbbox() is None, (x.name, diff.getbbox())


def test_a_guided_chart_without_spacers_qualifies(charts):
    lay = _layout(charts["guided"])
    assert lay["recipe"]["edge_spacers"] is True     # the build's own value
    plan = T.plan_for(charts["guided"])
    assert plan.reasons == [] and plan.families == ["i1Pro 2", "i1Pro 3"]


@pytest.mark.parametrize("key", ["spaced_edge", "spaced_bw"])
def test_a_chart_that_has_spacers_is_still_refused(charts, key):
    plan = T.plan_for(charts[key])
    assert plan.families == []
    assert plan.reasons == [
        "the chart has spacers between its patches; i1Profiler would count "
        "every spacer as a patch"]


def test_spacers_on_sheet_follows_the_renderer():
    """(between, at the ends) is what `raster.render_pages` draws:
    an edge spacer only with spacers on and a width above 0."""
    base = dict(instrument="i1", paper="A4", layout_mode="patch_first")
    s = T.spacers_on_sheet
    assert s({**base, "spacer_mode": "none", "edge_spacers": True}) == (False, False)
    assert s({**base, "spacer_mode": "none", "edge_spacers": False}) == (False, False)
    assert s({**base, "spacer_mode": "colored", "edge_spacers": True}) == (True, True)
    # the i1Pro's build turns edge spacers on whatever the box says
    assert s({**base, "spacer_mode": "colored", "edge_spacers": False}) == (True, True)
    assert s({**base, "spacer_mode": "bw"}) == (True, True)


def test_the_renderer_still_draws_edge_spacers_only_with_spacers_on():
    """The rule `spacers_on_sheet` copies; if the renderer changes, so must it."""
    from workflow.layout_engine import raster
    src = inspect.getsource(raster)
    assert ('if edge_spacers and sp_px > 0 and spacer_mode != "none" and '
            'col_slots:') in src


def test_the_refusal_never_reads_the_box_itself():
    src = inspect.getsource(T.plan_for)
    assert 'recipe.get("edge_spacers")' not in src
    assert "spacers at the ends of its strips" not in inspect.getsource(T)


def test_the_4317_refusal_text_is_gone_from_every_catalogue():
    old = ("the chart has spacers at the ends of its strips; i1Profiler would "
           "count them as patches")
    root = Path(__file__).resolve().parents[1] / "data" / "i18n"
    for p in root.glob("*.json"):
        assert old not in json.loads(p.read_text(encoding="utf-8")), p.name


# ---------------------------------------------------------------------------
# pharmacist's suggestion: "Prioritise chart area, then fit patches to it"
# ---------------------------------------------------------------------------

#: The margins Create Chart gives an i1Pro chart (what the real app stored on
#: screen, 4.3.18): top 38, right 9, bottom 19, left 26 mm.
_APP_MARGINS = dict(margin_top=38.0, margin_right=9.0, margin_bottom=19.0,
                    margin_left=26.0, use_instrument_margins=True)


def _area(d: Path, name: str, paper: str, cols: int, rows: int) -> Path:
    return _chart(d / name, name, cols * rows, spacer_mode="none",
                  layout_mode="area_first", area_method="by_grid",
                  area_cols=cols, area_rows=rows, patch_w_mm=0.0,
                  patch_h_mm=0.0, paper=paper, **_APP_MARGINS)


@pytest.fixture(scope="module")
def area_charts(tmp_path_factory):
    d = tmp_path_factory.mktemp("area")
    return {"a4": _area(d, "a4", "A4", 24, 27),
            "a3": _area(d, "a3", "A3", 24, 27)}


@pytest.fixture(scope="module")
def area_chart(area_charts):
    return area_charts["a3"]


def test_his_suggested_grid_on_a4_qualifies_for_both_families(area_charts):
    """24 strips of 27, "Prioritise chart area": 8.88 mm patches, 27 to a
    row. Since 4.3.18 the i1Pro 2 qualifies from 7 mm too (Basti
    2026-10-27), so both files are written."""
    plan = T.plan_for(area_charts["a4"])
    assert plan.families == ["i1Pro 2", "i1Pro 3"], plan.family_reasons
    assert (plan.rows, plan.columns) == (24, 27)
    assert 8.657 < plan.patch_len_mm <= 8.944       # window_mm(27)
    assert plan.hints == []


def test_an_area_first_grid_on_a3_is_refused_with_the_numbers(area_chart):
    """On A3 area-first stretches the strips over the page (362.9 mm),
    longer than an i1Profiler row."""
    plan = T.plan_for(area_chart)
    assert plan.families == []
    for fam in T.FAMILIES:
        assert any("longer than the 241.5 mm" in r
                   for r in plan.family_reasons[fam]), plan.family_reasons


def test_the_note_says_once_what_to_change(area_chart):
    plan = T.plan_for(area_chart)
    note = T.note_not_qualified(plan, "area")
    assert note.count("Why the strips are so long") == 1
    assert '"Prioritise patch size, then fit to page"' in note
    assert '"Prioritise chart area, then fit patches to it"' in note
    assert "—" not in note


def test_the_hint_names_the_labels_the_ui_shows():
    from ui.dialogs import layout_options_panel as P
    src = inspect.getsource(P)
    for label in ("Prioritise chart area, then fit patches to it",
                  "Prioritise patch size, then fit to page", "Create layout:",
                  # review r2, NIT3: the hint names the strip length controls
                  "Max strip length", "Don't cap strip length"):
        assert f'tr("{label}")' in src, label


def test_a_patch_first_chart_has_no_hint(charts):
    plan = T.plan_for(charts["edge"])
    assert plan.hints == []


# ---------------------------------------------------------------------------
# The box itself: greyed while it can print nothing
# ---------------------------------------------------------------------------

def test_the_edge_spacer_box_is_greyed_while_spacers_are_none():
    from PyQt6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    from ui.dialogs.layout_options_panel import LayoutOptionsPanel
    from workflow.layout_engine.presets import LayoutRecipe
    panel = LayoutOptionsPanel()
    try:
        # Pharmacist's case: i1Pro, Spacers None. Greyed, tick kept. Since
        # review r2 (NIT6) it stays greyed on the i1Pro with spacers too,
        # because the build brackets every i1Pro strip whatever it says; the
        # full rule is pinned in
        # test_edge_spacers_box_greys_only_when_it_changes_nothing.py.
        panel.set_recipe(LayoutRecipe(instrument="i1", spacer_mode="none",
                                      edge_spacers=True))
        cb = panel.edge_spacers_cb
        assert not cb.isEnabled()
        assert cb.isChecked()                    # kept, not cleared
        assert panel.get_recipe().edge_spacers is True
        panel.spacer_mode.setCurrentIndex(panel.spacer_mode.findData("colored"))
        assert not cb.isEnabled() and cb.isChecked()
        # where the box does change the sheet, Spacers None greys it again
        panel.set_recipe(LayoutRecipe(instrument="CR30",
                                      spacer_mode="colored",
                                      edge_spacers=True))
        assert cb.isEnabled() and cb.isChecked()
        panel.spacer_mode.setCurrentIndex(panel.spacer_mode.findData("none"))
        assert not cb.isEnabled() and cb.isChecked()
    finally:
        panel.deleteLater()
