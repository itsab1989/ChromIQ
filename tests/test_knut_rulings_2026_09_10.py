"""Knut's rulings of 2026-09-10 20:21 on #182, in two halves.

**The custom-paper name.** *"To be consistent with naming of presets, we can
automatically detect 'Portrait' or 'Landscape' and add that to the name. If
first parameter, which is the page width, is smaller than the second parameter,
which is the height, then we have Portrait. If opposite, width larger than
height, then we have Landscape. Can you implement that in the naming generator,
and also explain this in the help icon?"* -- which supersedes his earlier
instruction that a custom size carry no orientation at all. And with the
orientation settled, the fault it was blocking can be finished: the suggested
preset name for a Custom sheet used to read ``i1Pro-__custom__-600p-4pages``,
printing the combo's sentinel where the size belongs.

**The seed tag.** *"I think when a chart is generated, the seed used should be
stored, but also a tag should be stored that records what the checkbox status
was (ON or OFF)."* Loading a chart as it was made is not the same operation as
generating one from the current settings: on load the stored seed goes into the
Seed box and reproduces the sheet **even when the tick is off**, and the tick
comes from the stored tag. The two used to be one field, which is why selecting
a run re-ticked a box the user had turned off.
"""
from __future__ import annotations

import json
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtCore import QSettings                   # noqa: E402
from PyQt6.QtWidgets import QApplication             # noqa: E402

from core.argyll_runner import ArgyllRunner          # noqa: E402
from core.file_manager import FileManager            # noqa: E402
from core.settings import AppSettings                # noqa: E402
from workflow.layout_engine.presets import LayoutRecipe  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _tab(tmp_path):
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "t.ini"), QSettings.Format.IniFormat)
    s.set("custom_output_path", str(tmp_path / "out"))
    from ui.tabs.tab_chart import TabChart
    return TabChart(ArgyllRunner(s), FileManager(s), s)


def _panel(**kw):
    from ui.dialogs.layout_options_panel import LayoutOptionsPanel
    return LayoutOptionsPanel(**kw)


# =====================================================================
# A. the custom paper's name
# =====================================================================
@pytest.mark.parametrize("paper, orient", [
    ("100x150", "Portrait"),      # width < height
    ("130x180", "Portrait"),
    ("180x130", "Landscape"),     # width > height
    ("250x150", "Landscape"),   # a size the paper table has no name for
])
def test_a_custom_size_takes_its_orientation_from_its_two_numbers(qapp, paper, orient):
    """The orientation half of his ruling, unchanged. The SIZE half gained its
    "mm" a day later (see `test_knut_rulings_2026_09_11.py`), so the token is
    checked there and only the word is pinned here."""
    from ui.tabs.tab_chart import TabChart
    assert TabChart._paper_name_and_orientation(paper)[1] == orient


def test_a_square_custom_sheet_is_named_square(qapp):
    """SUPERSEDED, and by the person who left the question open.

    This file used to pin "a square page gets neither word", which was the
    honest reading of a ruling that spoke only about the two inequalities. Knut
    closed it on 2026-09-11: *"I suggest, when both Custom size boxes are the
    same, say 'Square' instead of Portrait or Landscape."*"""
    from ui.tabs.tab_chart import TabChart
    assert TabChart._paper_name_and_orientation("200x200") == ("200x200mm",
                                                              "Square")


def test_the_suggested_name_carries_the_custom_size_not_the_sentinel(qapp, tmp_path):
    """Knut's report: a preset whose sheet is 100 x 150 mm was offered the name
    ``i1Pro-__custom__-600p-4pages``."""
    tab = _tab(tmp_path)
    tab._manual_btn.setChecked(True)
    tab._set_engine_checked(True)
    panel = tab._manual_layout_panel
    panel.paper.setCurrentIndex(panel.paper.findData("__custom__"))
    panel.custom_w.setValue(100)
    panel.custom_h.setValue(150)

    name = tab._suggest_target_name()
    assert "__custom__" not in name
    assert "100x150" in name
    assert name.endswith("Portrait"), name


def test_a_wide_custom_sheet_is_named_landscape(qapp, tmp_path):
    tab = _tab(tmp_path)
    tab._manual_btn.setChecked(True)
    tab._set_engine_checked(True)
    panel = tab._manual_layout_panel
    panel.paper.setCurrentIndex(panel.paper.findData("__custom__"))
    panel.custom_w.setValue(180)
    panel.custom_h.setValue(130)

    name = tab._suggest_target_name()
    assert "180x130" in name and name.endswith("Landscape"), name


def test_the_help_icon_explains_where_the_orientation_comes_from(qapp):
    """His second obligation, and the easy one to drop: *"and also explain this
    in the help icon"*."""
    from ui.tabs.tab_chart import TabChart
    text = TabChart._auto_suffix_tooltip()
    low = text.lower()
    assert "custom" in low
    assert "portrait" in low and "landscape" in low
    assert "smaller than the height" in low and "larger than the height" in low


# =====================================================================
# B. the seed and the tick are two facts
# =====================================================================
def test_the_tick_follows_the_stored_tag_not_the_stored_number(qapp):
    """A chart built with the box UNTICKED still records the number it drew, so
    the number must not be read as the tick."""
    panel = _panel(with_selectors=True)
    panel.set_recipe(LayoutRecipe(randomize=True, seed=322855251,
                                  seed_fixed=False))
    assert panel.fixed_seed_cb.isChecked() is False
    # …and the number is on screen anyway, because it is what reproduces the
    # sheet (his "even when the checkbox is OFF").
    assert panel.seed_spin.value() == 322855251


def test_a_stored_tick_of_on_ticks_the_box(qapp):
    panel = _panel(with_selectors=True)
    panel.set_recipe(LayoutRecipe(randomize=True, seed=4242, seed_fixed=True))
    assert panel.fixed_seed_cb.isChecked() is True
    assert panel.seed_spin.value() == 4242


def test_a_recipe_written_before_the_tag_reads_exactly_as_it_did(qapp):
    """Every sidecar and preset on disk lacks the field. For those the number is
    still the only evidence there is, and nothing may move."""
    panel = _panel(with_selectors=True)
    panel.set_recipe(LayoutRecipe(randomize=True, seed=777))   # seed_fixed=None
    assert panel.fixed_seed_cb.isChecked() is True
    panel.set_recipe(LayoutRecipe(randomize=True, seed=None))
    assert panel.fixed_seed_cb.isChecked() is False


def test_the_panel_records_the_tick_when_it_is_asked_for_a_recipe(qapp):
    panel = _panel(with_selectors=True)
    panel.randomize_cb.setChecked(True)
    panel.fixed_seed_cb.setChecked(False)
    assert panel.get_recipe().seed_fixed is False
    panel.fixed_seed_cb.setChecked(True)
    panel.seed_spin.setValue(31337)
    r = panel.get_recipe()
    assert r.seed_fixed is True and r.seed == 31337


def test_the_tag_is_recorded_even_while_randomising_is_off(qapp):
    """With randomisation off there is no order to fix, so no seed is written;
    the tick is still a thing the user set, so the tag says what it says. What
    it should MEAN in that state is an open question for Knut."""
    panel = _panel(with_selectors=True)
    panel.fixed_seed_cb.setChecked(True)
    panel.randomize_cb.setChecked(False)
    r = panel.get_recipe()
    assert r.seed is None
    assert r.seed_fixed is True


def _sidecar(tmp_path, *, drawn: int, recipe: dict):
    ti2 = tmp_path / "c.ti2"
    ti2.write_text("CTI2\nNUMBER_OF_SETS 240\nBEGIN_DATA\nEND_DATA\n",
                   encoding="utf-8")
    ti2.with_suffix(".channels.json").write_text(json.dumps(
        {"layout": {"engine": "chromiq", "recipe": recipe, "seed": drawn,
                    "patches": [{"loc": "A1", "page": 0}]}}), encoding="utf-8")
    return ti2


def test_selecting_a_run_does_not_tick_a_box_the_user_turned_off(qapp, tmp_path):
    """Knut, 2026-09-10: unticked on run 1, generate, go to run 2, come back,
    and it was ON again. The chart's own record now says which it was."""
    tab = _tab(tmp_path)
    ti2 = _sidecar(tmp_path, drawn=322855251,
                   recipe={"instrument": "CM", "paper": "A4", "dpi": 300,
                           "randomize": True, "seed": None, "seed_fixed": False})

    assert tab._restore_chart_settings(ti2) is True
    panel = tab._manual_layout_panel
    assert panel.fixed_seed_cb.isChecked() is False
    assert panel.seed_spin.value() == 322855251
    # …so the next Generate draws a fresh seed, which is the OFF + randomise row
    # of his table.
    assert panel.get_recipe().seed is None


def test_a_chart_built_with_a_fixed_seed_comes_back_with_the_box_ticked(qapp, tmp_path):
    tab = _tab(tmp_path)
    ti2 = _sidecar(tmp_path, drawn=4242,
                   recipe={"instrument": "CM", "paper": "A4", "dpi": 300,
                           "randomize": True, "seed": 4242, "seed_fixed": True})
    assert tab._restore_chart_settings(ti2) is True
    panel = tab._manual_layout_panel
    assert panel.fixed_seed_cb.isChecked() is True
    # The stored seed is used, so the layout stays as it was.
    assert panel.get_recipe().seed == 4242


def test_the_exact_recipe_kept_for_a_restore_still_carries_the_drawn_seed(qapp, tmp_path):
    """His July requirement is untouched: Restore Used Chart rebuilds from the
    sidecar's own recipe, which carries the number whatever the tick says."""
    tab = _tab(tmp_path)
    ti2 = _sidecar(tmp_path, drawn=987654,
                   recipe={"instrument": "CM", "paper": "A4", "dpi": 300,
                           "randomize": True, "seed": None, "seed_fixed": False})
    tab._restore_chart_settings(ti2)
    assert tab._restored_exact_recipe.seed == 987654


def test_a_preset_stores_the_layout_but_not_this_chart_s_tick(qapp):
    """A preset drops the seed, and must drop the tick with it: stored ON with
    no number beside it would tick the box over whatever the Seed box happens to
    be holding when the preset is loaded."""
    from workflow.layout_engine.presets import PresetStore
    store = PresetStore()
    r = LayoutRecipe(instrument="i1", paper="A4", randomize=True,
                     seed=4242, seed_fixed=True)
    store.set(r)
    # …addressed by the recipe's OWN key: the mode is part of it, so asking for
    # "default" would quietly answer with a factory recipe instead.
    inst, paper, mode = r.preset_key().split("|")
    got = store.get(inst, paper, mode)
    assert got.seed is None, "a preset never stores one chart's seed"
    assert got.seed_fixed is None, "…nor the tick that would apply a stale one"


# =====================================================================
# C. the tick reaches the TARGET'S STORE, not just the panel
# =====================================================================
# W-beta4-plan F4, from J-seed-tick-conflict-FOR-KNUT.md:
#
#   "Unticking 'Use a fixed seed' on a chart built without one is never written
#    to disk, so the setting is genuinely lost, not merely mis-displayed."
#
# J was corrected on its own page: the untick does reach disk. But everything
# above this line is the PANEL, and the claim was about `runs/runN/meta.json`,
# which nothing covered. A tag that is recorded in the recipe and dropped by
# the store round trip would satisfy every test above and still lose the tick.
def _project_with_a_run(tmp_path):
    tab = _tab(tmp_path)
    tab._file_mgr.set_target_name("SeedStore")
    run = tab._file_mgr.project().current_run()
    run.ensure_dir()
    tab._switch_mode("manual")
    return tab, run


def _stored_tag(run):
    meta = json.loads((run.dir / "meta.json").read_text(encoding="utf-8"))
    recipe = (meta.get("create_chart_ui") or {}).get("engine_recipe") or {}
    return recipe.get("seed_fixed", "<absent>")


def test_the_tick_is_written_into_the_targets_meta_json(qapp, tmp_path):
    tab, run = _project_with_a_run(tmp_path)
    tab._manual_layout_panel.set_recipe(
        LayoutRecipe(randomize=True, seed=4242, seed_fixed=True))
    assert tab.save_target_settings(run) is True
    assert _stored_tag(run) is True


def test_unticking_it_is_written_too(qapp, tmp_path):
    """The claim itself. The tick going in and never coming out is the shape of
    a setting that is lost rather than merely mis-shown."""
    tab, run = _project_with_a_run(tmp_path)
    panel = tab._manual_layout_panel
    panel.set_recipe(LayoutRecipe(randomize=True, seed=4242, seed_fixed=True))
    tab.save_target_settings(run)
    assert _stored_tag(run) is True, "the tick never got there to begin with"

    panel.fixed_seed_cb.setChecked(False)
    tab.save_target_settings(run)
    assert _stored_tag(run) is False, (
        "the untick did not reach runs/runN/meta.json, so selecting the run "
        "again re-ticks a box the user turned off")
