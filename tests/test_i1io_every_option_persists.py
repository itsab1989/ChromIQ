"""EVERY i1iO OPTION A PERSON CAN SET IS KEPT, WHEREVER IT IS KEPT (Job D).

Basti, 2026-11-13: "everything should be possible to be saved as defaults
and as part of a preset." And the binding per-target rules
(docs/design/per_target_settings.md §4 S1-S10, §4b, §4c): what a target was
set to is what it shows when it is opened again.

One table, one walk. Every field of `LayoutRecipe` is either in `KEPT` (an
option that works on an i1iO chart, with a value that is NOT its default)
or in `NOT_AN_I1IO_OPTION` with the reason. Each `KEPT` value is put on the
Manual panel and must come back out of:

  (a) "Save as Defaults" (`TabChart._recipe_to_save`, stored as
      ``manual_engine_recipe``) and the panel a restart builds from it;
  (b) a user layout preset (`PresetStore`, through JSON as the file holds it);
  (c) the target's own stored Create Chart state (`_collect_ui_state` ->
      meta.json -> `_apply_ui_state`).

A field added to the recipe later, and not classified here, fails
`test_every_recipe_field_is_classified`; one classified as kept that a path
loses fails that path. Guided's own i1iO controls (aiming crosses, clip
border) are walked the same way at the end.
"""
from __future__ import annotations

import json
import os
from dataclasses import fields, replace

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(autouse=True)
def i1io_on():
    from workflow.i1io import support
    before = support._latched
    support.set_enabled_for_this_process(True)
    try:
        yield
    finally:
        support._latched = before


#: field -> a value that is not its default and that an i1iO chart can use.
KEPT = {
    "paper": "Letter",
    "dpi": 400,
    "randomize": False,
    "spacer_mode": "bw",
    "edge_spacers": True,
    "margin_top": 14.0,
    "margin_right": 17.0,
    "margin_bottom": 30.0,
    "margin_left": 40.0,
    "patch_w_mm": 11.0,
    "patch_h_mm": 9.0,
    "i1io_crosses": False,
    "i1io_align": "center",
    "i1io_clip_border": True,
    "i1io_text_bold": False,
    "i1io_numbers_edge_mm": 7.0,
    "i1io_text_align": "start",
    "spacer_width_mm": 1.5,
    "inter_patch_mm": 0.5,
    "strip_gap_mm": 1.5,
    "max_strip_mm": 200.0,
    "strip_indicator_gap_mm": 1.0,
    "offset_x_mm": 1.5,
    "offset_y_mm": 1.0,
    "bit16": True,
    "compression": "none",
    "export_pdf": True,
    "show_strip_indicators": False,
    "show_row_indicators": False,
    "indicator_font": "Inter",
    "indicator_size_mm": 3.0,
    "indicator_bold": True,
    "indicator_italic": True,
    "indicator_align": "center",
    "strip_label_offset_mm": 1.0,
    "strip_label_offset_x_mm": 0.5,
    "underline_mode": "black",
    "underline_thickness_mm": 0.8,
    "underline_gap_mm": 0.7,
    "chart_text": "Lot 7",
    "chart_text_font": "JetBrains Mono",
    "chart_text_size_mm": 3.0,
    "chart_text_italic": True,
    "helper_markers": True,
    "helper_marker_edge_mm": 3.0,
    "helper_marker_len_mm": 3.0,
    "helper_marker_per_patch": 2,
    "helper_markers_top_bottom": False,
    "helper_markers_sides": False,
    "text_edge_mm": 6.0,
    "clip_border_width_mm": 30.0,
    "clip_content_mode": "text",
    "clip_text": "Paper: Hahnemuehle",
    "clip_text_font": "JetBrains Mono",
    "clip_text_size_mm": 3.0,
    "clip_flip_180": True,
    "nolimit": True,
    "strip_pattern": "1-9, 1-9",
    "patch_pattern": "A-Z;1-999",
}

#: Fields that are not an option of an i1iO chart, and why.
NOT_AN_I1IO_OPTION = {
    "instrument": "the instrument itself, set by its own selector",
    "seed": "the shuffle seed of one build, not a setting",
    "seed_fixed": "kept by the randomisation row; walked for every "
                  "instrument by the preset tests",
    "hflag": "printtarg's -h ColorMunki layout; greyed for the i1iO",
    "cm_density": "ColorMunki density; greyed for the i1iO",
    "cm_stagger": "ColorMunki's offset of every second strip; greyed",
    "hex_flat_top": "hexagon patches; greyed for the i1iO",
    "spacer_on": "follows the spacer mode ('none' is off), "
                 "test_no_spacers_is_kept",
    "spacer_palette": "the spacer colours of the coloured mode, kept for "
                      "every instrument by the preset tests",
    "spacer_overrides": "per-pair spacer colours, internal",
    "pscale": "patch scale; greyed for the i1iO (sizes are set in mm)",
    "sscale": "spacer scale; greyed for the i1iO",
    "border": "printtarg's single border, superseded by the four margins",
    "use_instrument_margins": "no instrument-margin thresholds for the "
                              "i1iO; greyed",
    "fd9_gap_mm": "FD-9 only",
    "fd9_clip_border": "FD-9 only",
    "layout_mode": "area-first sizing; greyed for the i1iO (engine work)",
    "area_method": "area-first sizing; greyed for the i1iO",
    "area_cols": "area-first sizing; greyed for the i1iO",
    "area_rows": "area-first sizing; greyed for the i1iO",
    "area_ratio": "area-first sizing; greyed for the i1iO",
    "area_min_patch_mm": "area-first sizing; greyed for the i1iO",
    "layout_explicit": "bookkeeping: whether the layout was chosen",
    "margins_explicit": "bookkeeping: whether the margins were chosen",
    "align_explicit": "bookkeeping: whether the alignment was chosen",
    "label_style_explicit": "bookkeeping: whether the label style was chosen",
    "indicator_rotation": "label rotation; greyed for the i1iO",
    "row_indicator_rotation": "label rotation; greyed for the i1iO",
    "patch_area_align": "shown for the i1iO; its alignment is i1io_align",
    "chart_text_bold": "the i1iO sheet text's Bold is i1io_text_bold",
    "chart_text_align": "the i1iO line's place is i1io_text_align",
    "text_edge_top_mm": "nothing is printed along the top; greyed",
    "text_edge_clip_mm": "the i1iO numbers' edge is i1io_numbers_edge_mm",
    "stamp_command": "the layout summary stamp; greyed for the i1iO",
    "clip_border": "the i1Pro clip band; the i1iO's is i1io_clip_border",
    "clip_side": "the i1iO clip border is always the page's left edge",
    "clip_content_when_on": "remembered content mode while the band is "
                            "off, bookkeeping",
    "clip_image_path": "a file path; kept with the content mode, walked "
                       "for every instrument by the clip tests",
    "clip_image_rotation": "image content only; walked by the clip tests",
    "clip_image_scale": "image content only; walked by the clip tests",
    "clip_image_offset_x_mm": "image content only; walked by the clip tests",
    "clip_image_offset_y_mm": "image content only; walked by the clip tests",
    "clip_border_free_space": "derived from the content mode",
}


def test_every_recipe_field_is_classified():
    from workflow.layout_engine.presets import LayoutRecipe
    names = {f.name for f in fields(LayoutRecipe)}
    assert not set(KEPT) & set(NOT_AN_I1IO_OPTION)
    unclassified = names - set(KEPT) - set(NOT_AN_I1IO_OPTION)
    assert not unclassified, (
        "a recipe field nobody classified for the i1iO: add it to KEPT "
        f"(and make every path keep it) or say why not: {sorted(unclassified)}")
    assert not (set(KEPT) | set(NOT_AN_I1IO_OPTION)) - names


def _base():
    from workflow.layout_engine.presets import default_recipe
    return default_recipe("IO2", "A4")


def test_every_kept_value_is_not_the_default():
    base = _base()
    same = [k for k, v in KEPT.items() if getattr(base, k) == v]
    assert not same, same


# ---- the recipe itself ------------------------------------------------------

@pytest.mark.parametrize("name", sorted(KEPT))
def test_the_recipe_and_a_preset_file_keep_it(name, tmp_path):
    from workflow.layout_engine.presets import LayoutRecipe, PresetStore
    r = replace(_base(), **{name: KEPT[name]})
    assert getattr(LayoutRecipe.from_dict(
        json.loads(json.dumps(r.to_dict()))), name) == KEPT[name]
    store = PresetStore()
    store.set(r)
    back = PresetStore.from_dict(json.loads(json.dumps(store.to_dict())))
    got = [getattr(x, name) for x in back._presets.values()]
    assert got == [KEPT[name]]


# ---- through the screen -----------------------------------------------------

@pytest.fixture
def chart_tab(qapp, tmp_path):
    from PyQt6.QtCore import QSettings
    from core.argyll_runner import ArgyllRunner
    from core.file_manager import FileManager
    from core.settings import AppSettings
    from ui.tabs.tab_chart import TabChart
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "app.ini"), QSettings.Format.IniFormat)
    s.set("custom_output_path", str(tmp_path / "out"))
    s.set("use_chromiq_layout_engine", True)
    tab = TabChart(ArgyllRunner(s), FileManager(s), s)
    yield tab, s, tmp_path
    tab.deleteLater()


def _manual_io2(tab):
    from PyQt6.QtWidgets import QApplication
    tab._switch_mode("manual")
    tab._init_manual_layout_panel()
    panel = tab._manual_layout_panel
    tab._set_manual_value("printtarg", "-i", "IO2")
    panel.instr.setCurrentIndex(panel.instr.findData("IO2"))
    QApplication.processEvents()
    return panel


def _the_whole_recipe():
    """Every kept value at once: what a person who set them all saved,
    with the marks the panel sets when a person changes those groups."""
    return replace(_base(), margins_explicit=True, align_explicit=True,
                   label_style_explicit=True, layout_explicit=True, **KEPT)


def _show(tab, panel, rec):
    from PyQt6.QtWidgets import QApplication
    tab._set_manual_value("printtarg", "-p", rec.paper)
    panel.set_recipe(rec)
    QApplication.processEvents()


def _lost(rec, want_names=KEPT):
    return {k: (getattr(rec, k), v) for k, v in want_names.items()
            if getattr(rec, k) != v}


def test_the_panel_shows_and_gives_back_every_option(chart_tab):
    tab, _s, _t = chart_tab
    panel = _manual_io2(tab)
    _show(tab, panel, _the_whole_recipe())
    assert _lost(panel.get_recipe()) == {}


def test_a_preset_applied_on_screen_keeps_every_option(chart_tab):
    """(b) A user preset saved from the screen and applied again."""
    from workflow.layout_engine.presets import PresetStore
    tab, _s, _t = chart_tab
    panel = _manual_io2(tab)
    _show(tab, panel, _the_whole_recipe())
    store = PresetStore()
    store.set(panel.get_recipe())
    back = PresetStore.from_dict(json.loads(json.dumps(store.to_dict())))
    (saved,) = back._presets.values()
    _show(tab, panel, _base())
    assert _lost(panel.get_recipe()) != {}
    _show(tab, panel, saved)
    assert _lost(panel.get_recipe()) == {}


def test_the_layout_preset_bar_keeps_every_option(chart_tab):
    """(b) "Update preset" on the preset bar, then "Reset to preset"."""
    tab, _s, _t = chart_tab
    panel = _manual_io2(tab)
    _show(tab, panel, _the_whole_recipe())
    tab._update_manual_preset()
    _show(tab, panel, replace(_base(), paper="Letter"))
    assert _lost(panel.get_recipe()) != {}
    tab._reset_manual_to_preset()
    assert _lost(panel.get_recipe()) == {}


def test_a_named_preset_keeps_every_option(chart_tab):
    """(b) A named Manual preset: what `_on_preset_save` captures for the
    layout, through JSON, applied by `_restore_user_preset`."""
    from PyQt6.QtWidgets import QApplication
    tab, _s, _t = chart_tab
    panel = _manual_io2(tab)
    _show(tab, panel, _the_whole_recipe())
    data = {"printtarg_-i": "IO2", "printtarg_-p": "Letter",
            "layout_recipe": replace(tab._pinned_layout_recipe(), seed=None,
                                     seed_fixed=None).to_dict()}
    data = json.loads(json.dumps(data))
    _show(tab, panel, _base())
    tab._restore_user_preset(data)
    QApplication.processEvents()
    assert _lost(tab._manual_layout_panel.get_recipe()) == {}


def test_save_as_defaults_keeps_every_option(chart_tab):
    """(a) "Save as Defaults" stores it, and a restart shows it."""
    from PyQt6.QtCore import QSettings
    from PyQt6.QtWidgets import QApplication
    from core.argyll_runner import ArgyllRunner
    from core.file_manager import FileManager
    from core.settings import AppSettings
    from ui.tabs.tab_chart import TabChart
    from workflow.layout_engine.presets import LayoutRecipe
    tab, s, tmp = chart_tab
    panel = _manual_io2(tab)
    _show(tab, panel, _the_whole_recipe())
    tab._on_save_defaults()
    stored = s.get("manual_engine_recipe")
    assert _lost(LayoutRecipe.from_dict(json.loads(json.dumps(stored)))) == {}
    # the next start, on the same store
    s2 = AppSettings()
    s2._qs = QSettings(str(tmp / "app.ini"), QSettings.Format.IniFormat)
    tab2 = TabChart(ArgyllRunner(s2), FileManager(s2), s2)
    try:
        tab2._switch_mode("manual")
        tab2._init_manual_layout_panel()
        QApplication.processEvents()
        assert _lost(tab2._manual_layout_panel.get_recipe()) == {}
    finally:
        tab2.deleteLater()


def test_the_targets_own_state_keeps_every_option(chart_tab):
    """(c) The per-target Create Chart state, through JSON as meta.json
    holds it, put back after the screen moved on."""
    from PyQt6.QtWidgets import QApplication
    tab, _s, _t = chart_tab
    panel = _manual_io2(tab)
    _show(tab, panel, _the_whole_recipe())
    state = json.loads(json.dumps(tab._collect_ui_state()))
    _show(tab, panel, _base())
    tab._apply_ui_state(state)
    QApplication.processEvents()
    assert _lost(panel.get_recipe()) == {}


def test_no_spacers_is_kept(chart_tab):
    """`spacer_on` follows the spacer mode: "none" is no spacers."""
    tab, _s, _t = chart_tab
    panel = _manual_io2(tab)
    _show(tab, panel, replace(_the_whole_recipe(), spacer_mode="none",
                              spacer_on=False))
    got = panel.get_recipe()
    assert (got.spacer_mode, got.spacer_on) == ("none", False)
    state = json.loads(json.dumps(tab._collect_ui_state()))
    _show(tab, panel, _base())
    tab._apply_ui_state(state)
    got = panel.get_recipe()
    assert (got.spacer_mode, got.spacer_on) == ("none", False)


# ---- Guided's own i1iO controls ---------------------------------------------

GUIDED = {"_i1io_aim_check": ("chart_i1io_crosses", "i1io_crosses", False),
          "_i1io_clip_check": ("chart_i1io_clip_border", "i1io_clip_border",
                               True)}


@pytest.mark.parametrize("attr", sorted(GUIDED))
def test_guided_keeps_its_i1io_controls(chart_tab, attr):
    from PyQt6.QtWidgets import QApplication
    tab, s, _t = chart_tab
    key, fld, value = GUIDED[attr]
    tab._switch_mode("guided")
    tab._shared_set("guided", "instrument", "IO2")
    QApplication.processEvents()
    box = getattr(tab, attr)
    box.setChecked(value)
    QApplication.processEvents()
    # (a) Save as Defaults, from Guided
    tab._on_save_defaults()
    assert s.get(key) is value
    # (c) the target's own state
    state = json.loads(json.dumps(tab._collect_ui_state()))
    assert state["guided"][fld] is value
    box.setChecked(not value)
    tab._apply_ui_state(state)
    QApplication.processEvents()
    assert box.isChecked() is value


# ---- the preset bar's "modified" --------------------------------------------

def test_the_preset_bar_compares_every_option():
    from workflow.i1io.chart import READ_RECIPE_FIELDS
    assert set(KEPT) <= READ_RECIPE_FIELDS
    # greyed and shown-only fields are not compared
    for name in ("patch_area_align", "chart_text_bold", "chart_text_align",
                 "text_edge_clip_mm", "use_instrument_margins", "pscale",
                 "layout_mode", "area_ratio", "stamp_command"):
        assert name not in READ_RECIPE_FIELDS


def _modified(tab):
    from PyQt6.QtWidgets import QApplication
    QApplication.processEvents()
    return tab._layout_preset_status()[1]


def test_a_fresh_i1io_layout_is_not_modified(chart_tab):
    """Choosing the i1iO shows its preset as it is. (4.3.33 lit "modified"
    here, and still does for every other instrument: area_ratio and the
    margins differ from the stored default whatever is done.)"""
    tab, _s, _t = chart_tab
    _manual_io2(tab)
    assert _modified(tab) is False
    tab._reset_manual_to_preset()
    assert _modified(tab) is False


#: What an option needs on before it shows on the sheet at all.
NEEDS = {k: {"i1io_clip_border": True} for k in (
    "clip_border_width_mm", "clip_content_mode", "clip_flip_180")}
NEEDS.update({k: {"i1io_clip_border": True, "clip_content_mode": "text",
                  "clip_text": "x"}
              for k in ("clip_text", "clip_text_font", "clip_text_size_mm")})


def test_every_option_changed_lights_modified(chart_tab):
    """Each option, changed on screen, makes the layout differ from its
    preset. The chart's own text is left out on purpose: it belongs to the
    chart, not to the layout preset (`_layout_recipe_values`)."""
    tab, _s, _t = chart_tab
    panel = _manual_io2(tab)
    tab._reset_manual_to_preset()
    # a person who touches a label control makes the style the chart's own
    start = replace(panel.get_recipe(), label_style_explicit=True)
    _show(tab, panel, start)
    assert _modified(tab) is False
    quiet = []
    for name, value in KEPT.items():
        if name in ("paper", "chart_text"):
            continue                  # another preset / the chart's own
        before = replace(start, **NEEDS.get(name, {}))
        _show(tab, panel, before)
        was = tab._layout_recipe_values(panel.get_recipe())
        _show(tab, panel, replace(before, **{name: value}))
        if tab._layout_recipe_values(panel.get_recipe()) == was:
            quiet.append(name)
    assert quiet == []
    _show(tab, panel, start)
    assert _modified(tab) is False


# ---- what Generate hands the build is what the chart records ----------------

@pytest.mark.parametrize("name", sorted(KEPT))
def test_generate_builds_what_the_recipe_records(chart_tab, name):
    """Review 5 brief, item 1: for every i1iO option, the build kwargs the
    Generate path passes (`ChartCreator._engine_kwargs`) equal the ones
    derived from the recipe the chart records (`_current_layout_recipe`,
    written to channels.json), but for what a build adds of its own (the
    project's name, the date, the run's description, the side stamp)."""
    tab, _s, _t = chart_tab
    panel = _manual_io2(tab)
    rec = replace(_base(), margins_explicit=True, label_style_explicit=True,
                  **{name: KEPT[name]})
    _show(tab, panel, rec)
    recorded = tab._current_layout_recipe().build_kwargs()
    built = tab._creator._engine_kwargs(tab._collect_params())
    own = {"project", "chart_date", "rundescription", "side_stamp"}
    diff = {k: (recorded.get(k), built.get(k))
            for k in set(recorded) | set(built)
            if k not in own and recorded.get(k) != built.get(k)}
    assert diff == {}
