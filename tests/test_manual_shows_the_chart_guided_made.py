"""Item 69, ruled by Basti, 25 Nov 2026: a chart already made in Guided =
Manual shows the values REALLY USED for that chart; no chart made yet = Manual
stays as it is; the info panel's numbers are correct in both cases.

Until 4.3.66 the switch copied what Guided's fields said at that moment, with
6 mm margins the build did not use: 506 patches beside an i1Pro chart of 484,
and Letter beside an A4 chart when Letter was chosen afterwards.

Real builds: targen from ArgyllCMS and the layout engine.
"""
from __future__ import annotations

import importlib
import json
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from tests.test_a_redraw_is_judged_by_its_sheet import (_guided,  # noqa: E402
                                                        _pages)
from tests.test_i1io_run_types import (_generate, _prof,        # noqa: E402,F401
                                       requires_argyll, win)

#: (instrument, paper, the boxes ticked in Guided)
CHARTS = [("i1", "A4", ()), ("i1", "Letter", ()), ("i1", "A4R", ("_lb_check",)),
          ("i1", "A4", ("_nsl_check",)),
          ("p3", "A4", ()), ("CM", "A4", ()), ("CM", "A4", ("_dd_check",)),
          ("CM", "A4", ("_td_check",)), ("SS", "A4", ()),
          ("SS", "A4", ("_dd_check",)),
          ("CR30", "A4", ()), ("CR30", "A4R", ()),
          ("CR30", "A4", ("_dd_check",)), ("FD9", "A4", ()),
          ("IO2", "A4", ()), ("IO2", "A3", ()),
          ("IO2", "A4", ("-_i1io_aim_check",)),
          ("IO2", "A3", ("-_i1io_aim_check",)),
          ("IO2", "A4", ("_i1io_clip_check",)),
          ("XRISIS", "A4", ()), ("XRISIS", "127x178", ()), ("B100XY", "A4", ())]

@pytest.fixture(autouse=True)
def _every_beta_on(monkeypatch):
    _betas(monkeypatch)


def _betas(monkeypatch):
    for name in ("fd9", "i1io", "isis", "barbieri"):
        support = importlib.import_module(f"workflow.{name}.support")
        monkeypatch.setattr(support, "_latched", True)
    from PyQt6.QtWidgets import QMessageBox
    monkeypatch.setattr(QMessageBox, "exec", lambda self: 0)


def _record(win):  # noqa: F811
    side = _prof(win).with_suffix(".channels.json")
    return json.loads(side.read_text(encoding="utf-8"))


def _made(win, qapp, qtbot, instrument, paper, ticks):  # noqa: F811
    tc = win._tab_chart
    _guided(tc, qapp, instrument, paper)
    for name in ticks:
        box = getattr(tc, name.lstrip("-"))
        box.setChecked(not name.startswith("-"))
        qapp.processEvents()
        assert box.isChecked() is (not name.startswith("-"))
    _generate(win, qapp, qtbot, expect=_prof(win))
    return tc


def _shown_paper(tc):
    recipe = tc._manual_layout_panel.get_recipe()
    return recipe.instrument, recipe.paper


#: What of the record is the layout. (`margins_chosen_by_user` says who chose
#: the margins: nobody in Guided, the person in Manual.)
LAYOUT = ("patches", "strips", "paper_mm", "dpi", "label_band_bottom_px",
          "color_rep", "patch_ink_top_px")
#: The colours targen is asked for are Manual's own (its neutrals): where they
#: are not Guided's, the patches stand in the same places with other colours.
NEUTRALS = ("grey_steps", "white_patches", "black_patches")


def _generate_in_manual(win, qapp, qtbot, monkeypatch, seed, like=None):  # noqa: F811
    """Generate in Manual with the shuffle *seed*, and with the patch set of
    the build parameters *like* where given."""
    from dataclasses import replace
    tc = win._tab_chart
    cls = type(tc)
    recipe = cls._current_layout_recipe
    monkeypatch.setattr(cls, "_current_layout_recipe", lambda self, *a, **k: (
        replace(recipe(self, *a, **k), seed=seed)))
    generate = type(tc._creator).generate

    def build(self, params, *a, **k):
        for name in (*NEUTRALS, "good_mode", "extra_targen_args") if (
                like is not None) else ():
            setattr(params, name, getattr(like, name))
        return generate(self, params, *a, **k)
    monkeypatch.setattr(type(tc._creator), "generate", build)
    _generate(win, qapp, qtbot, expect=_prof(win))
    return tc._creator._pending_params


def _patches_of(win):  # noqa: F811
    import re
    text = _prof(win).with_suffix(".ti1").read_text(encoding="latin-1")
    body = re.search(r"BEGIN_DATA\n(.*?)END_DATA", text, re.S).group(1)
    return [" ".join(line.split()[1:4]) for line in body.splitlines()]


@requires_argyll
@pytest.mark.parametrize("instrument,paper,ticks", CHARTS,
                         ids=[" ".join([i, p, *t]) for i, p, t in CHARTS])
@pytest.mark.parametrize("later", [False, True],
                         ids=["at once", "another choice in Guided since"])
def test_generate_in_manual_makes_the_same_layout(
        win, qapp, qtbot, monkeypatch, instrument, paper, ticks,  # noqa: F811
        later):
    tc = _made(win, qapp, qtbot, instrument, paper, ticks)
    guided, built = _record(win)["layout"], tc._guided_chart_params
    printed, patches = _pages(_prof(win).parent), _patches_of(win)
    assert built.instrument == instrument and built.paper == paper
    if later:
        _guided(tc, qapp, "CM" if instrument == "i1" else "i1",
                "Letter" if paper != "Letter" else "A4")
        held = (tc._instr_combo.currentData(), tc._paper_combo.currentData())
        assert held != (instrument, paper)
    tc._switch_mode("manual")
    for _ in range(20):
        qapp.processEvents()
    assert _shown_paper(tc) == (instrument, paper)
    # the info panel: both columns are the chart
    first = [p for p in guided["patches"] if p.get("page", 0) == 0]
    estimate = tc._layout_info_panel.predicted()
    assert estimate["total"] == len(patches), estimate
    assert estimate["pages"] == len(printed) or instrument == "IO2"
    # 1. as a person who presses Generate with nothing changed
    made = _generate_in_manual(win, qapp, qtbot, monkeypatch, guided["seed"])
    manual = _record(win)["layout"]
    for key in LAYOUT:
        assert manual.get(key) == guided.get(key), key
    assert len(manual["patches"]) == len(guided["patches"]) >= len(first)
    assert len(_pages(_prof(win).parent)) == len(printed)
    same_colours = all(getattr(made, n) == getattr(built, n) for n in NEUTRALS)
    assert (_patches_of(win) == patches) is same_colours
    assert (_pages(_prof(win).parent) == printed) is same_colours
    if later:                         # nothing of Guided's is lost
        assert (tc._instr_combo.currentData(),
                tc._paper_combo.currentData()) == held
    # 2. with Guided's own patch set: the very same pages
    if not same_colours:
        _generate_in_manual(win, qapp, qtbot, monkeypatch, guided["seed"],
                            like=built)
        assert _patches_of(win) == patches
        assert _pages(_prof(win).parent) == printed


@requires_argyll
@pytest.mark.parametrize("instrument,paper,total,margin", [
    ("i1", "A4", 484, 10.0), ("i1", "Letter", 506, 10.0),
    ("CR30", "A4", 345, 5.0), ("CR30", "A4R", 368, 5.0),
    ("CM", "A4", 105, 6.0), ("p3", "A4", 99, 6.0), ("SS", "A4", 1053, 6.0),
    ("IO2", "A4", 528, None), ("XRISIS", "A4", 1008, 5.0)])
def test_the_reviewers_table(win, qapp, qtbot, instrument, paper,  # noqa: F811
                             total, margin):
    """Both columns of "Chart layout information", and the margins shown."""
    tc = _made(win, qapp, qtbot, instrument, paper, ())
    tc._switch_mode("manual")
    for _ in range(20):
        qapp.processEvents()
    panel = tc._layout_info_panel
    assert len(_record(win)["layout"]["patches"]) == total
    assert panel.predicted()["total"] == total
    assert panel._actual_labels["total"].text() == str(total)
    assert panel._estimate_labels["total"].text() == str(total)
    if margin is not None:
        recipe = tc._manual_layout_panel.get_recipe()
        assert {recipe.margin_top, recipe.margin_right, recipe.margin_bottom,
                recipe.margin_left} == {margin}


def test_no_chart_made_yet_leaves_manual_as_it_is(win, qapp):  # noqa: F811
    """Only the instrument and the paper come along, as ever (#9)."""
    tc = win._tab_chart
    tc._switch_mode("manual")
    tc._switch_mode("guided")
    _guided(tc, qapp, "CM", "A4R")
    tc._switch_mode("manual")
    qapp.processEvents()
    assert not tc._shows_a_guided_chart()
    assert _shown_paper(tc) == ("CM", "A4R")
    assert "Manual now shows" not in tc._log.toPlainText()


@requires_argyll
def test_back_and_forth_keeps_the_persons_edit_in_manual(
        win, qapp, qtbot):  # noqa: F811
    """Once shown, Manual is the person's: a second switch writes nothing over
    it, and what Guided held since stays in Guided. Another instrument chosen
    in Guided takes Manual along (Knut, #130), so there the chart comes back."""
    tc = _made(win, qapp, qtbot, "i1", "A4", ())
    tc._switch_mode("manual")
    box = tc._manual_layout_panel.margins["t"]
    box.setValue(box.value() + 1.0)
    edited = tc._manual_layout_panel.get_recipe().margin_top
    _guided(tc, qapp, "i1", "Letter")
    tc._switch_mode("manual")
    qapp.processEvents()
    assert _shown_paper(tc) == ("i1", "A4")
    assert tc._manual_layout_panel.get_recipe().margin_top == edited == 11.0
    assert tc._paper_combo.currentData() == "Letter"
    _guided(tc, qapp, "CM", "Letter")
    tc._switch_mode("manual")
    qapp.processEvents()
    assert _shown_paper(tc) == ("i1", "A4")
    assert tc._manual_layout_panel.get_recipe().margin_top == 10.0
    assert tc._instr_combo.currentData() == "CM"


@requires_argyll
def test_the_rows_beside_the_panel_are_the_charts_too(
        win, qapp, qtbot):  # noqa: F811
    """Its pages and printtarg's rows (with the engine off they lay out)."""
    tc = _made(win, qapp, qtbot, "CM", "A4", ("_dd_check",))
    tc._dd_check.setChecked(False)
    tc._pages_spin.setValue(3)
    qapp.processEvents()
    tc._switch_mode("manual")
    qapp.processEvents()
    assert tc._manual_pages_spin.value() == 1
    assert tc._manual_value("printtarg", "-h") is True
    assert tc._manual_value("printtarg", "-m") == 6
    assert tc._pages_spin.value() == 3 and not tc._dd_check.isChecked()
