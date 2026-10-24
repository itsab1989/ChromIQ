""""Label offset" X: the strip letters moved left or right (Basti, 2026-10-24).

*"In create chart tab manual module there is a section strip indicators only.
In there is the option label offset. However this offset spinbox only allows
offset in y direction. Would it be possible to add another spinbox next to it
that allows offset in x direction as well? … And the new one should allow
positive and negative values like the existing one so movement to left and
right is possible. … Also it should be possible to save this value as default
and as part of a preset. Defaults and presets saved before this change should
still work."*

What is held here:

* the value travels: recipe dict, engine kwargs, Preferences, the panel, Save
  as Defaults and a user preset, and back;
* a recipe, default or preset written before the field existed reads as 0 and
  lays out exactly as before, and a recipe at 0 serialises exactly as before
  (so the built-in presets' certificates cannot move);
* on the printed sheet: positive moves every strip letter right, negative
  left, by the amount asked, and nothing but the letters changes;
* the one limit (`raster.StripLabelShift`): the outermost letters' INK stays
  inside the side text distance and off a clip border with something printed
  in it, with the notice that says so. There is deliberately NO "own strip"
  limit (Basti, on review, 2026-10-24: people move the letters out of the
  instrument's path); a letter nearer to the next strip than to its own is
  only pointed out, and a large X with a small label prints as asked;
* the use case: on an i1Pro chart a letter at X = half the strip spacing
  clears every strip's measuring path, where at 0 it sits in its own.
"""
from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PIL import Image                                              # noqa: E402

from workflow.layout_engine import raster                          # noqa: E402
from workflow.layout_engine.chart import build_from_recipe         # noqa: E402
from workflow.layout_engine.presets import (                       # noqa: E402
    LayoutRecipe, PresetStore, default_recipe)

ROOT = Path(__file__).resolve().parent.parent
TI1 = next(iter(sorted((ROOT / "assets" / "charts").rglob("*.ti1"))))
KEY = "strip_label_offset_x_mm"
DPI = 150


# ---------------------------------------------------------------------------
# 1. the value travels, and an old record reads as 0
# ---------------------------------------------------------------------------
def test_a_recipe_carries_it_through_every_form_it_is_stored_in():
    r = LayoutRecipe(strip_label_offset_x_mm=-3.5, strip_label_offset_mm=1.0)
    assert LayoutRecipe.from_dict(r.to_dict()).strip_label_offset_x_mm == -3.5
    kw = r.build_kwargs()
    assert kw[KEY] == -3.5
    assert LayoutRecipe.from_dict(kw).strip_label_offset_x_mm == -3.5
    store = PresetStore()
    store.set(r)
    again = PresetStore.from_dict(store.to_dict()).get(
        r.instrument, r.paper, r.mode())
    assert again.strip_label_offset_x_mm == -3.5


def test_a_record_written_before_it_existed_reads_as_zero():
    d = LayoutRecipe(strip_label_offset_mm=2.0).to_dict()
    assert KEY not in d
    assert LayoutRecipe.from_dict(d).strip_label_offset_x_mm == 0.0
    kw = LayoutRecipe().build_kwargs()
    assert LayoutRecipe.from_build_kwargs(kw).strip_label_offset_x_mm == 0.0


def test_at_zero_nothing_is_written_so_old_and_new_records_are_identical():
    """The built-in presets' certificates hash `to_dict()`, and stored recipes
    are compared as dicts: at 0 the key must simply not be there."""
    for r in (LayoutRecipe(), default_recipe("CR30", "A4"),
              LayoutRecipe(strip_label_offset_x_mm=0.0)):
        assert KEY not in r.to_dict()
        assert KEY not in r.build_kwargs()


def test_preferences_seed_it_like_the_other_label_style_fields():
    from core.settings import DEFAULTS, INDICATOR_STYLE_KEYS
    assert DEFAULTS[KEY] == 0.0
    assert INDICATOR_STYLE_KEYS[KEY] == KEY
    from ui.dialogs.layout_options_panel import _LABEL_STYLE_FIELDS
    assert KEY in _LABEL_STYLE_FIELDS


def test_preferences_window_writes_and_reads_it(qapp, tmp_path):
    from PyQt6.QtCore import QSettings
    from core.settings import AppSettings
    from ui.dialogs.settings_dialog import SettingsDialog
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    dlg = SettingsDialog(s)
    try:
        dlg._isty_offset_x.setValue(-4.5)
        dlg._save_indicator_style()
        assert s.get(KEY) == pytest.approx(-4.5)
    finally:
        dlg.deleteLater()
    dlg = SettingsDialog(s)
    try:
        assert dlg._isty_offset_x.value() == pytest.approx(-4.5)
    finally:
        dlg.deleteLater()
    out = s.apply_indicator_style(LayoutRecipe())
    assert out.strip_label_offset_x_mm == pytest.approx(-4.5)
    own = LayoutRecipe(label_style_explicit=True)
    assert s.apply_indicator_style(own).strip_label_offset_x_mm == 0.0


def test_the_panel_shows_and_returns_it(qapp):
    from ui.dialogs.layout_options_panel import LayoutOptionsPanel
    p = LayoutOptionsPanel()
    try:
        p.set_recipe(LayoutRecipe(strip_label_offset_x_mm=6.5,
                                  strip_label_offset_mm=-2.0,
                                  label_style_explicit=True))
        assert p.strip_label_offset_x.value() == pytest.approx(6.5)
        assert p.strip_label_offset.value() == pytest.approx(-2.0)
        r = p.get_recipe()
        assert r.strip_label_offset_x_mm == pytest.approx(6.5)
        assert r.strip_label_offset_mm == pytest.approx(-2.0)
        # both boxes take negative and positive values in 0.5 mm steps
        for sb in (p.strip_label_offset_x, p.strip_label_offset):
            assert sb.minimum() < 0 < sb.maximum()
            assert sb.singleStep() == 0.5 and sb.decimals() == 1
            assert sb.suffix() == " mm"
    finally:
        p.deleteLater()


def test_touching_it_makes_the_label_style_the_charts_own(qapp):
    from ui.dialogs.layout_options_panel import LayoutOptionsPanel
    p = LayoutOptionsPanel()
    try:
        p.set_recipe(LayoutRecipe())
        assert not p.get_recipe().label_style_explicit
        p.strip_label_offset_x.setValue(1.5)
        assert p.get_recipe().label_style_explicit
    finally:
        p.deleteLater()


# ---------------------------------------------------------------------------
# 2. Save as Defaults and a user preset, through the real tab
# ---------------------------------------------------------------------------
@pytest.fixture()
def store(tmp_path):
    from PyQt6.QtCore import QSettings
    from core.settings import AppSettings
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    s.set("custom_output_path", str(tmp_path / "out"))
    s.set("chart_mode", "manual")
    s.set("use_chromiq_layout_engine", True)
    return s


def _session(qapp, s):
    from core.argyll_runner import ArgyllRunner
    from core.file_manager import FileManager
    from ui.tabs import tab_chart as TC
    t = TC.TabChart(ArgyllRunner(s), FileManager(s), s)
    qapp.processEvents()
    if t._current_mode() != "manual":
        t._manual_btn.click()
        qapp.processEvents()
    return t


def _close(qapp, t):
    t.hide()
    t.deleteLater()
    qapp.processEvents()


def test_save_as_defaults_keeps_it_across_a_restart(qapp, store):
    t = _session(qapp, store)
    try:
        t._manual_layout_panel.strip_label_offset_x.setValue(-2.5)
        qapp.processEvents()
        t._on_save_defaults()
    finally:
        _close(qapp, t)
    assert store.get("manual_engine_recipe")[KEY] == pytest.approx(-2.5)
    t = _session(qapp, store)
    try:
        assert t._manual_layout_panel.strip_label_offset_x.value() == \
            pytest.approx(-2.5)
    finally:
        _close(qapp, t)


def test_defaults_saved_before_it_existed_open_at_zero(qapp, store):
    rec = default_recipe("i1", "A4").to_dict()
    rec["label_style_explicit"] = True
    assert KEY not in rec
    store.set("manual_engine_recipe", rec)
    t = _session(qapp, store)
    try:
        assert t._manual_layout_panel.strip_label_offset_x.value() == 0.0
    finally:
        _close(qapp, t)


def _pick(qapp, t, name):
    combo = t._preset_combo
    ix = combo.findData(name)
    if ix < 0:
        ix = combo.findText(name)
    assert ix >= 0, f"{name} is not in the preset list"
    combo.blockSignals(True)
    combo.setCurrentIndex(ix)
    combo.blockSignals(False)
    t._on_preset_selected(ix)
    qapp.processEvents()


def test_a_user_preset_keeps_it_and_an_old_one_loads_zero(
        qapp, store, monkeypatch):
    from PyQt6.QtWidgets import QCheckBox, QDialog, QLineEdit
    from core.preset_store import load_presets, save_presets
    from ui.tabs import tab_chart as TC
    monkeypatch.setattr(TC.TabChart, "_confirm_displacing_results",
                        lambda self, *a, **k: True, raising=False)
    t = _session(qapp, store)
    try:
        panel = t._manual_layout_panel
        panel.strip_label_offset_x.setValue(4.0)
        qapp.processEvents()

        def _answer(dlg):
            for cb in dlg.findChildren(QCheckBox):
                if "Add a descriptive prefix" in cb.text():
                    cb.setChecked(False)
            dlg.findChildren(QLineEdit)[0].setText("X-four")
            return QDialog.DialogCode.Accepted

        monkeypatch.setattr(QDialog, "exec", _answer)
        t._on_preset_save()
        monkeypatch.undo()
        monkeypatch.setattr(TC.TabChart, "_confirm_displacing_results",
                            lambda self, *a, **k: True, raising=False)
        saved = load_presets("create_chart")
        assert saved["X-four"]["layout_recipe"][KEY] == pytest.approx(4.0)
        # …and the same preset as a release before this one wrote it
        old = dict(saved["X-four"])
        old["layout_recipe"] = {k: v for k, v in old["layout_recipe"].items()
                                if k != KEY}
        saved["X-old"] = old
        save_presets("create_chart", saved)
        t._populate_preset_combo(load_presets("create_chart"))
        qapp.processEvents()
        monkeypatch.setattr("ui.dialogs.name_prompt.ask_for_project_name",
                            lambda *a, **k: "Label-X", raising=True)
        # Picking a preset builds its chart; nothing here needs ArgyllCMS, and
        # a targen still running when the tab goes away is a dead worker.
        monkeypatch.setattr(t._creator, "generate", lambda *a, **k: None)
        monkeypatch.setattr(t._creator, "load_ti1_and_generate_preview",
                            lambda *a, **k: None)

        panel.strip_label_offset_x.setValue(-7.0)
        _pick(qapp, t, "X-four")
        assert panel.strip_label_offset_x.value() == pytest.approx(4.0)
        _pick(qapp, t, "X-old")
        assert panel.strip_label_offset_x.value() == 0.0
    finally:
        _close(qapp, t)


# ---------------------------------------------------------------------------
# 3. on the printed sheet
# ---------------------------------------------------------------------------
def _recipe(x=0.0, **kw):
    r = default_recipe("i1", "A4")
    r.dpi = DPI
    r.seed = 7
    r.layout_mode = "patch_first"
    r.strip_label_offset_x_mm = x
    for k, v in kw.items():
        setattr(r, k, v)
    return r


_cache: dict = {}


def _page(tmp_path, r):
    key = repr(r.to_dict())
    if key not in _cache:
        # one stem for every sheet: the clip border's notes print the
        # chart's name, so a different name would be a different sheet
        out = tmp_path / f"d{len(_cache)}"
        out.mkdir()
        res, _ = build_from_recipe(TI1, out / "c", r)
        _cache[key] = (np.asarray(Image.open(res.tiff_paths[0]).convert("L"))
                       .astype(int))
    return _cache[key]


def _letters(tmp_path, **kw):
    """The pixels the strip letters account for: the page with them, against
    the same page with them switched off."""
    on = _page(tmp_path, _recipe(**kw))
    off_kw = dict(kw, show_strip_indicators=False)
    off_kw.pop("x", None)
    off = _page(tmp_path, _recipe(**off_kw))
    return on, on != off


def _cols(mask):
    xs = np.nonzero(mask.any(axis=0))[0]
    return int(xs.min()), int(xs.max())


@pytest.mark.parametrize("x", [2.0, -0.5])
def test_the_letters_move_by_the_amount_asked_and_nothing_else_moves(
        tmp_path, x):
    """+ is to the right, - to the left. This chart's first strip sits on the
    i1Pro clip border with its notes in it, so the left room is small: -0.5 mm
    is inside it."""
    base, m0 = _letters(tmp_path)
    page, m = _letters(tmp_path, x=x)
    px = round(x * DPI / 25.4)
    l0, r0 = _cols(m0)
    l1, r1 = _cols(m)
    assert (l1 - l0, r1 - r0) == (px, px)
    # the rows are the same rows: X never moves anything up or down
    ys0 = np.nonzero(m0.any(axis=1))[0]
    ys1 = np.nonzero(m.any(axis=1))[0]
    assert (ys0.min(), ys0.max()) == (ys1.min(), ys1.max())
    # and outside the letters not one pixel of the sheet changed
    assert not ((page != base) & ~m & ~m0).any()


def test_an_old_recipe_without_the_key_prints_the_same_pixels(tmp_path):
    d = _recipe().to_dict()
    assert KEY not in d
    old = LayoutRecipe.from_dict(d)
    a = _page(tmp_path, old)
    b = _page(tmp_path, _recipe(0.0))
    assert np.array_equal(a, b)


def _shift(r):
    from workflow.layout_engine import instruments
    kw = dict(r.build_kwargs(), area_target_count=_patch_count())
    return raster.strip_label_x_shift(instruments.geom_from_build_kwargs(kw),
                                      kw), kw


def test_a_large_x_with_a_small_label_prints_as_asked(tmp_path):
    """Basti, on review: the X limits must not be too strict. 15 mm is nearly
    two strips on this chart, and it is printed, with only the gentle hint.
    (A right margin with room for it: on the default sheet the patches run
    to within 7 mm of the side text distance.)"""
    small = dict(indicator_size_mm=2.0, margin_right=25.0,
                 margins_explicit=True)
    _base, m0 = _letters(tmp_path, **small)
    page, m = _letters(tmp_path, x=15.0, **small)
    shift, _kw = _shift(_recipe(15.0, **small))
    assert shift is not None and not shift.held
    assert shift.used_mm == pytest.approx(15.0, abs=0.1)
    assert shift.near_neighbour
    px = round(15.0 * DPI / 25.4)
    assert (_cols(m)[0] - _cols(m0)[0], _cols(m)[1] - _cols(m0)[1]) == (px, px)
    base = _page(tmp_path, _recipe(**small))
    assert not ((page != base) & ~m & ~m0).any()


def test_the_hint_comes_only_past_half_the_strip_spacing():
    near = raster._nearer_the_next_strip
    assert not near(0, 48)
    assert not near(24, 48)          # on the line between two strips
    assert not near(-24, 48)
    assert near(26, 48) and near(-26, 48)
    assert not near(400, 0)          # a single strip has no neighbour
    shift, _kw = _shift(_recipe(2.0))
    assert shift is not None and not shift.near_neighbour
    assert shift.pitch_mm > 4.0


def test_half_the_strip_spacing_clears_the_i1pro_path(tmp_path):
    """The use case the help describes, measured on the sheet: an i1Pro reads
    through an opening about 4.5 mm wide down the middle of each strip. At 0
    the letters sit in that path; at half the strip spacing their ink touches
    no strip's path at all."""
    from workflow.layout_engine import geometry, instruments, papers
    r = _recipe()
    kw = dict(r.build_kwargs(), area_target_count=_patch_count())
    g = instruments.geom_from_build_kwargs(kw)
    w, h = papers.dimensions_mm(r.paper)
    lay = geometry.compute(g, w, h, _patch_count())
    place = geometry.placement(g, w, h, lay)
    pitch = place.x_of(1) - place.x_of(0)
    n = -(-min(lay.total_patches, lay.patches_per_page) // lay.steps_in_pass)
    mm = DPI / 25.4
    path = np.zeros(int(w * mm) + 2, bool)
    for i in range(n):
        c = (place.x_of(i) + place.pwid / 2) * mm
        path[int(np.floor(c - 2.25 * mm)):int(np.ceil(c + 2.25 * mm)) + 1] = True
    _b, m0 = _letters(tmp_path)
    _p, m = _letters(tmp_path, x=pitch / 2)
    cols0 = m0.any(axis=0)
    cols = m.any(axis=0)
    assert (cols0 & path[:cols0.size]).any()
    assert not (cols & path[:cols.size]).any()


def test_a_letter_stops_before_the_clip_border_with_notes_in_it(tmp_path):
    r = _recipe(-40.0)
    assert r.clip_content_mode != "off" and r.clip_border
    kw = dict(r.build_kwargs(), area_target_count=_patch_count())
    from workflow.layout_engine import instruments
    g = instruments.geom_from_build_kwargs(kw)
    shift = raster.strip_label_x_shift(g, kw)
    assert shift.held and shift.held_by == "edge"
    assert shift.used_mm == pytest.approx(-shift.left_mm)
    # where the letters really are: their left ink is not inside the band.
    # Page 1's "A" may stop a little short of it: one shift serves every
    # page, and a later page's first letter can be wider.
    _page_, m = _letters(tmp_path, x=-40.0)
    band_px = (g.lbord + g.border) * DPI / 25.4
    assert band_px - 2 <= _cols(m)[0] <= band_px + 2.0 * DPI / 25.4


@pytest.mark.parametrize("rot", [90, 270])
def test_a_turned_letter_is_held_at_its_ink_not_its_tile(tmp_path, rot):
    """A turned tile is as wide as the font's ascent plus descent, about 2 mm
    more than the letter inks; the limit is the ink."""
    from workflow.layout_engine import instruments
    r = _recipe(-40.0, indicator_rotation=rot)
    kw = dict(r.build_kwargs(), area_target_count=_patch_count())
    g = instruments.geom_from_build_kwargs(kw)
    _page_, m = _letters(tmp_path, x=-40.0, indicator_rotation=rot)
    band_px = (g.lbord + g.border) * DPI / 25.4
    assert band_px - 2 <= _cols(m)[0] <= band_px + 2


def test_without_clip_content_the_paper_edge_is_the_limit():
    from workflow import text_edge_fit
    from workflow.layout_engine import instruments
    r = _recipe(-200.0, clip_content_mode="off", clip_border=False,
                margin_left=40.0)
    kw = dict(r.build_kwargs(), area_target_count=_patch_count())
    g = instruments.geom_from_build_kwargs(kw)
    shift = raster.strip_label_x_shift(g, kw)
    edge = text_edge_fit.geom_side_text_edge_mm(g)
    assert edge > 0
    assert shift.held
    # the left limit is never past the side text distance
    from workflow.layout_engine import geometry, papers
    w, h = papers.dimensions_mm(r.paper)
    lay = geometry.compute(g, w, h, _patch_count())
    place = geometry.placement(g, w, h, lay)
    assert place.x_of(0) + place.pwid / 2 - shift.left_mm > edge


def test_at_zero_the_limits_never_move_a_letter():
    """A chart whose letters already sit closer to an edge than the rule
    allows prints them where they always were."""
    lo, hi = raster._strip_label_x_limits_px(
        page_w_px=1000, first_x0=10, first_xr=50, last_x0=950, last_xr=990,
        reach_left_px=15, reach_right_px=15, left_bound_px=100,
        right_bound_px=100)
    assert lo == 0 == hi
    assert raster._clamp_shift(0, lo, hi) == (0, "")


def _patch_count() -> int:
    from workflow.layout_engine.ti1_reader import read_ti1
    return len(read_ti1(TI1).patches)


# ---------------------------------------------------------------------------
# 4. the words
# ---------------------------------------------------------------------------
def test_the_notice_says_what_was_printed_and_why(qapp):
    from ui.tabs.tab_chart import strip_label_x_held_notice
    S = raster.StripLabelShift
    assert strip_label_x_held_notice(None) is None
    assert strip_label_x_held_notice(S(3.0, 3.0, 4.0, 4.0, "")) is None
    b = strip_label_x_held_notice(S(-9.0, -0.8, 0.8, 3.9, "edge"))
    assert "-9.0 mm" in b and "-0.8 mm" in b and "side of the paper" in b
    assert "0.8 mm to the left" in b and "3.9 mm to the right" in b


def test_the_neighbour_hint_names_the_spacing_and_a_value_that_clears(qapp):
    from ui.tabs.tab_chart import strip_label_x_neighbour_notice as hint
    S = raster.StripLabelShift
    assert hint(None) is None
    assert hint(S(3.0, 3.0, 9.0, 9.0, "", 8.03, False)) is None
    t = hint(S(15.0, 15.0, 20.0, 20.0, "", 8.03, True))
    assert "15.0 mm" in t and "8.0 mm apart" in t
    # half of 8.03 rounded DOWN, so the value it offers really clears
    assert "from -4.0 to 4.0 mm" in t
    from workflow import measurement_messages as MM
    assert "M-CHART-STRIP-LABELS-X-HELD-STRIP" not in MM.CATALOGUE


def test_the_help_states_the_sign_convention_and_the_limits():
    from ui.dialogs.layout_options_panel import LABEL_OFFSET_HELP as H
    assert "A positive value moves them to the right" in H
    assert "a negative value to the left" in H
    assert "lowers them toward the patches" in H
    assert "without moving the patches" in H
    # the use case, and its worked figures (measured above)
    assert "out of that path" in H
    assert "half the distance from one strip to the next" in H
    assert "X is 4 mm" in H and "about 4.5 mm wide" in H
    # no "own strip" limit any more, and the hint that replaced it is named
    assert "half a strip's width" not in H
    assert "nearer to the next strip than to their own" in H
    assert "—" not in H


def test_label_offset_is_greyed_with_the_strip_letters_off(qapp):
    """Both boxes move only the strip letters: with the letters off they are
    greyed, as the underline is, and keep their values."""
    from ui.dialogs.layout_options_panel import LayoutOptionsPanel
    p = LayoutOptionsPanel()
    try:
        p.set_recipe(LayoutRecipe(strip_label_offset_x_mm=3.0,
                                  label_style_explicit=True))
        assert p.strip_label_offset_x.isEnabled()
        assert p.strip_label_offset.isEnabled()
        p.show_indicators.setChecked(False)
        assert not p.strip_label_offset_x.isEnabled()
        assert not p.strip_label_offset.isEnabled()
        assert p.get_recipe().strip_label_offset_x_mm == pytest.approx(3.0)
        p.show_indicators.setChecked(True)
        assert p.strip_label_offset_x.isEnabled()
    finally:
        p.deleteLater()
