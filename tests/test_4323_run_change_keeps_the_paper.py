"""A RUN CHANGE NEVER FILES THE CHART'S PAPER AS THE RUN'S OWN (§2.2, 4.3.23).

After any run change, a plain one included, the second write of Create Chart
(a second tab change, or entering Create Chart from Measure and leaving it)
put the run's chart paper into its stored printtarg -p: Letter became A4,
with no edit by anybody. 4.3.22 had it too.

Root cause: loading the run's stored Manual layout (`_set_engine_recipe` ->
`LayoutOptionsPanel.set_recipe`) sets the panel's instrument first. The
panel's `_on_instr_changed` closes its own `_loading` window part way
through, so the tab's `_sync_manual_selection_from_panel` mirrored the
panel's PREVIOUS paper, the chart's, into -p; the recipe's own paper then
arrived under `_loading` and was never mirrored. So the §2.2 shield's
snapshot of the run's own values already held the chart's paper, saw
nothing move, and did not cover the key, and every later visit to the tab
put the chart's paper back on -p. The mirror now waits until the panel holds
the whole recipe; when the chart's paint moves -p after that,
`_note_what_the_chart_imposed` records it like the layout's own fields and
`_keep_the_targets_own_values` writes the run's paper back.

Driven on the real main window and the real Demo-Full-RGB project; run 3
stores a layout of its own (Letter, 38/26 mm) that differs from its chart's.
"""
from __future__ import annotations

import json

import pytest

from tests.test_opening_a_project_never_writes_the_target_it_leaves import (
    _a_run_with_its_own_layout, _bytes, _everything_stored, _leave_and_return,
    _one_tab_change, _pump, _to_measure, world)  # noqa: F401 (fixture)


def _stored_paper(meta) -> str:
    data = json.loads(meta.read_text(encoding="utf-8"))
    return data["create_chart_settings"]["printtarg-p"]["value"]


def _run_change(qapp, win, where: str) -> None:
    """run 3 -> run 2 -> run 3, with Create Chart or Measure on screen."""
    if where == "measure":
        _to_measure(qapp, win)
    win._target_ctl.set_profile_run("run2")
    _pump(qapp, 400)
    win._target_ctl.set_profile_run("run3")
    _pump(qapp, 400)


@pytest.mark.parametrize("where", ("create_chart", "measure"))
def test_two_tab_changes_after_a_run_change_write_nothing(qapp, world, where):
    win, copy = world
    project, meta = _a_run_with_its_own_layout(qapp, win, copy,
                                               "Demo-Full-RGB", "run3")
    if where == "measure":
        # The Measure tab's own settings filed for run 3 first (its §2.1
        # write on leaving it), so anything after this is Create Chart's.
        _to_measure(qapp, win)
    before = _bytes(meta)
    everything = _everything_stored(meta)
    assert _stored_paper(meta) == "Letter"
    _run_change(qapp, win, where)
    assert win._target_ctl.target.profile_run == "run3"
    for n in (1, 2):
        _one_tab_change(qapp, win)
        after = _everything_stored(meta)
        moved = {k: (everything.get(k), after.get(k))
                 for k in set(everything) | set(after)
                 if everything.get(k) != after.get(k)}
        assert _bytes(meta) == before, (
            f"tab change {n} after a run change filed the chart as the "
            f"run's own: {moved}")
    assert _stored_paper(meta) == "Letter"


def test_the_chart_paper_is_shielded_not_lost(qapp, world):
    """The chart is still what Create Chart shows after the run change: -p
    and the panel carry the chart's paper, and the shield holds the run's
    own."""
    win, copy = world
    project, meta = _a_run_with_its_own_layout(qapp, win, copy,
                                               "Demo-Full-RGB", "run3")
    _run_change(qapp, win, "create_chart")
    tab = win._tab_chart
    chart = json.loads((project / "runs" / "run3" /
                        f"{project.name}.channels.json").read_text(
        encoding="utf-8"))["layout"]["recipe"]["paper"]
    assert chart != "Letter", "nothing to tell apart"
    assert tab._manual_layout_panel.selection()[1] == chart
    assert tab._manual_get("printtarg", "-p", None) == chart
    own, from_chart = tab._chart_imposed["params"]["printtarg-p"]
    assert own["value"] == "Letter" and from_chart["value"] == chart


def test_a_paper_the_user_chooses_after_a_run_change_is_saved(qapp, world):
    win, copy = world
    project, meta = _a_run_with_its_own_layout(qapp, win, copy,
                                               "Demo-Full-RGB", "run3")
    _run_change(qapp, win, "create_chart")
    panel = win._tab_chart._manual_layout_panel
    i = panel.paper.findData("A3")
    assert i >= 0, "the panel offers no A3 here"
    panel.paper.setCurrentIndex(i)
    _pump(qapp, 200)
    _leave_and_return(qapp, win)
    assert _stored_paper(meta) == "A3"
    assert _everything_stored(meta)["ui.engine_recipe.paper"] == "A3"
    # …and it stays the user's through a second tab change.
    _leave_and_return(qapp, win)
    assert _stored_paper(meta) == "A3"


def test_loading_a_recipe_mirrors_its_own_paper_not_the_one_before(
        qapp, world):
    """The mechanism: a recipe that changes the instrument leaves -p on the
    recipe's paper, not on the panel's previous one."""
    from workflow.layout_engine.presets import LayoutRecipe
    win, copy = world
    _a_run_with_its_own_layout(qapp, win, copy, "Demo-Full-RGB", "run3")
    tab = win._tab_chart
    panel = tab._manual_layout_panel
    rec = panel.get_recipe().to_dict()
    other = "CM" if panel.instr.currentData() != "CM" else "i1"
    before = panel.selection()[1]
    paper = "A3" if before != "A3" else "A4"
    rec.update(instrument=other, paper=paper)
    tab._set_engine_recipe(LayoutRecipe.from_dict(rec))
    assert panel.selection()[:2] == (other, paper)
    assert tab._manual_get("printtarg", "-p", None) == paper
    assert tab._manual_get("printtarg", "-i", None) == other
