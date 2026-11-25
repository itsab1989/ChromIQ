"""Item 69, ruled by Basti, 25 Nov 2026: a chart already made in Guided =
Manual shows the values REALLY USED for that chart; no chart made yet = Manual
stays as it is; the info panel's numbers are correct in both cases.

Until 4.3.66 the switch copied what Guided's fields said at that moment, with
6 mm margins the build did not use: 506 patches beside an i1Pro chart of 484,
and Letter beside an A4 chart when Letter was chosen afterwards.

What is a person's stays a person's: Manual's settings of a run without a
chart, and every edit in Manual after the chart was shown there. The two modes
show one instrument (Knut, #130): with another one chosen in Guided since,
Manual takes nothing of the chart.

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
from tests.test_i1io_run_types import (_generate, _pick, _prof,  # noqa: E402,F401
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
                         ids=["at once", "another paper in Guided since"])
def test_generate_in_manual_makes_the_same_layout(
        win, qapp, qtbot, monkeypatch, instrument, paper, ticks,  # noqa: F811
        later):
    tc = _made(win, qapp, qtbot, instrument, paper, ticks)
    guided, built = _record(win)["layout"], tc._guided_chart_params
    printed, patches = _pages(_prof(win).parent), _patches_of(win)
    assert built.instrument == instrument and built.paper == paper
    if later:
        _guided(tc, qapp, instrument, "Letter" if paper != "Letter" else "A4")
        tc._pages_spin.setValue(2)
        held = (tc._instr_combo.currentData(), tc._paper_combo.currentData(),
                tc._pages_spin.value())
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
        assert (tc._instr_combo.currentData(), tc._paper_combo.currentData(),
                tc._pages_spin.value()) == held
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


SAID = "Manual now shows the settings"


def _edit_manual(tc, qapp):
    """A person's own Manual settings: Auto off, 321 patches, area-first."""
    tc._manual_auto_patches_check.setChecked(False)
    tc._on_auto_patches_toggled(False)
    tc._set_manual_value("targen", "-f", 321)
    tc._manual_layout_panel.margins["t"].setValue(17.0)
    for _ in range(10):
        qapp.processEvents()


def _manual_is(tc):
    return (tc._manual_auto_patches_check.isChecked(),
            tc._manual_value("targen", "-f"),
            tc._manual_layout_panel.get_recipe().margin_top)


@requires_argyll
def test_back_and_forth_keeps_the_persons_edits_in_manual(
        win, qapp, qtbot):  # noqa: F811
    """Once shown, Manual is the person's: a second switch writes nothing over
    it, and what Guided held since stays in Guided."""
    tc = _made(win, qapp, qtbot, "i1", "A4", ())
    tc._switch_mode("manual")
    assert SAID in tc._log.toPlainText()
    _edit_manual(tc, qapp)
    mine = _manual_is(tc)
    assert mine == (False, 321, 17.0)
    _guided(tc, qapp, "i1", "Letter")
    tc._switch_mode("manual")
    qapp.processEvents()
    assert _shown_paper(tc) == ("i1", "A4") and _manual_is(tc) == mine
    assert tc._paper_combo.currentData() == "Letter"


@requires_argyll
def test_b2_another_instrument_and_back_keeps_them_too(
        win, qapp, qtbot):  # noqa: F811
    tc = _made(win, qapp, qtbot, "i1", "A4", ())
    tc._switch_mode("manual")
    _edit_manual(tc, qapp)
    mine = _manual_is(tc)
    tc._switch_mode("guided")
    for code in ("CM", "i1"):
        i = tc._instr_combo.findData(code)
        tc._instr_combo.setCurrentIndex(i)
        tc._instr_combo.activated.emit(i)
        qapp.processEvents()
    tc._switch_mode("manual")
    qapp.processEvents()
    assert _manual_is(tc) == mine
    assert tc._log.toPlainText().count(SAID) == 1


@requires_argyll
@pytest.mark.parametrize("ours", ["taken over", "taken over, Guided on CM",
                                  "not taken over"])
def test_b1_a_run_without_a_chart_keeps_manual_as_it_is(
        win, qapp, qtbot, ours):  # noqa: F811
    """Run 2 has no chart, and Manual settings of its own; run 1's chart was
    made in Guided. B2's second case is the way back to run 1."""
    tc, ctl = win._tab_chart, win._target_ctl
    project = win._file_mgr.project()
    first = project.current_run().id
    second = project.new_run().id

    def go(run):
        ctl.set_profile_run(run)
        for _ in range(30):
            qapp.processEvents()
    go(second)
    _pick(tc, qapp, "i1")
    _edit_manual(tc, qapp)
    theirs = _manual_is(tc)
    go(first)
    _guided(tc, qapp, "i1", "A4")
    _generate(win, qapp, qtbot, expect=project.run(first).chart_ti2)
    if ours.startswith("taken over"):
        tc._switch_mode("manual")
        _edit_manual(tc, qapp)
        _guided(tc, qapp, "CM" if "CM" in ours else "i1", "Letter")
    log = tc._log.toPlainText().count(SAID)
    go(second)
    tc._switch_mode("guided")
    tc._switch_mode("manual")
    for _ in range(10):
        qapp.processEvents()
    assert not tc._shows_a_guided_chart()
    assert _manual_is(tc) == theirs
    assert tc._log.toPlainText().count(SAID) == log
    go(first)
    assert tc._shows_a_guided_chart()
    if ours.startswith("taken over"):
        # (what the run's return shows in Manual is its own affair)
        for edit in (False, True):
            if edit:
                tc._switch_mode("manual")
                _edit_manual(tc, qapp)
            before = _manual_is(tc)
            tc._switch_mode("guided")
            tc._switch_mode("manual")
            qapp.processEvents()
            assert _manual_is(tc) == before
        assert before == (False, 321, 17.0)
        assert tc._log.toPlainText().count(SAID) == log
    else:
        tc._switch_mode("guided")
        tc._switch_mode("manual")
        qapp.processEvents()
        assert tc._manual_layout_panel.get_recipe().margin_top == 10.0


@requires_argyll
@pytest.mark.parametrize("again", [False, True],
                         ids=["CM", "CM and back to i1"])
def test_another_instrument_in_guided_takes_nothing_of_the_chart(
        win, qapp, qtbot, again):  # noqa: F811
    """The two modes show one instrument (#130), and the chart's values are
    another instrument's. Back on its own instrument, Manual takes it."""
    tc = _made(win, qapp, qtbot, "i1", "A4", ())
    _guided(tc, qapp, "CM", "Letter")
    if again:
        _guided(tc, qapp, "i1", "Letter")
    tc._switch_mode("manual")
    for _ in range(10):
        qapp.processEvents()
    assert tc._instr_combo.currentData() == tc._manual_value(
        "printtarg", "-i") == ("i1" if again else "CM")
    if again:
        assert _shown_paper(tc) == ("i1", "A4")
        assert SAID in tc._log.toPlainText()
    else:
        assert _shown_paper(tc) == ("CM", "Letter")
        assert SAID not in tc._log.toPlainText()
        # ...and not later either: Manual was opened, it is the person's now
        _edit_manual(tc, qapp)
        mine = _manual_is(tc)
        tc._switch_mode("guided")
        tc._switch_mode("manual")
        qapp.processEvents()
        assert _manual_is(tc) == mine


@requires_argyll
@pytest.mark.parametrize("record", ["missing", "damaged", "a wrong type",
                                    "a wrong margin", "a wrong text",
                                    "of another instrument",
                                    "of a later version"])
def test_a_record_that_cannot_be_used_is_not_claimed(
        win, qapp, qtbot, record):  # noqa: F811
    """S2: Manual as it was, and nothing is said. (A record with fields of a
    later version can be used.)"""
    tc = win._tab_chart
    tc._switch_mode("manual")
    before = tc._manual_layout_panel.get_recipe()
    tc = _made(win, qapp, qtbot, "i1", "A4", ())
    side = _prof(win).with_suffix(".channels.json")
    doc = json.loads(side.read_text(encoding="utf-8"))
    recipe = doc["layout"]["recipe"]
    if record == "missing":
        side.unlink()
    elif record == "damaged":
        side.write_text("{\"layout\": {", encoding="utf-8")
    else:
        key, value = {"a wrong type": ("border", "abc"),
                      "a wrong margin": ("margin_left", "9"),
                      "a wrong text": ("clip_text_font", 5),
                      "of another instrument": ("instrument", "CM"),
                      "of a later version": ("from_the_future", {"a": 1}),
                      }[record]
        recipe[key] = value
        side.write_text(json.dumps(doc), encoding="utf-8")
    tc._switch_mode("manual")
    for _ in range(10):
        qapp.processEvents()
    now = tc._manual_layout_panel.get_recipe()
    used = record == "of a later version"
    assert (SAID in tc._log.toPlainText()) is used
    if used:
        assert now.margin_top == 10.0
    else:
        for name in ("margin_top", "margin_left", "layout_mode", "pscale",
                     "border"):
            assert getattr(now, name) == getattr(before, name), name


@requires_argyll
def test_a_panel_that_would_not_take_it_is_not_claimed(
        win, qapp, qtbot, monkeypatch):  # noqa: F811
    tc = _made(win, qapp, qtbot, "i1", "A4", ())

    def refuse(*_a, **_k):
        raise RuntimeError("no")
    monkeypatch.setattr(tc, "_set_engine_recipe", refuse)
    tc._switch_mode("manual")
    assert SAID not in tc._log.toPlainText()
    assert not tc._manual_has_the_guided_chart()


@requires_argyll
def test_a_chart_made_in_manual_ends_it(win, qapp, qtbot):  # noqa: F811
    """S3: then the chart on screen is Manual's, and a paper chosen in Guided
    comes along again (#9)."""
    tc = _made(win, qapp, qtbot, "i1", "A4", ())
    tc._switch_mode("manual")
    assert tc._shows_a_guided_chart() and tc._manual_has_the_guided_chart()
    _generate(win, qapp, qtbot, expect=_prof(win))
    assert not tc._shows_a_guided_chart()
    _guided(tc, qapp, "i1", "Letter")
    tc._switch_mode("manual")
    qapp.processEvents()
    assert _shown_paper(tc) == ("i1", "Letter")


@requires_argyll
def test_another_chart_in_its_place_is_not_the_one_guided_made(
        win, qapp, qtbot):  # noqa: F811
    tc = _made(win, qapp, qtbot, "i1", "A4", ())
    assert tc._shows_a_guided_chart()
    tc._shown_chart_stamp = "another"
    assert not tc._shows_a_guided_chart()


@requires_argyll
def test_the_charts_label_style_is_the_printed_one(
        win, qapp, qtbot, monkeypatch):  # noqa: F811
    """S3: other label settings in Preferences since are not the chart's."""
    tc = _made(win, qapp, qtbot, "i1", "A4", ())
    printed, seed = _pages(_prof(win).parent), _record(win)["layout"]["seed"]
    from core.settings import INDICATOR_STYLE_KEYS
    tc._settings.set(INDICATOR_STYLE_KEYS["indicator_size_mm"], 9.0)
    tc._settings.set(INDICATOR_STYLE_KEYS["indicator_bold"], True)
    tc._switch_mode("manual")
    qapp.processEvents()
    _generate_in_manual(win, qapp, qtbot, monkeypatch, seed)
    assert _pages(_prof(win).parent) == printed


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
