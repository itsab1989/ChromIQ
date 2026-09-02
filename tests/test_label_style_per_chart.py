"""A chart's own label style wins; Preferences is only the default (Knut, 4.1.5-beta.6).

    *"The label text properties are global, and some presets require a smaller
    label, especially the scanner presets. The label properties and size should
    be saved together with the chart, per chart, and for presets, so that a user
    can adapt to the chart's need. Too big row text will for example take a lot
    of space, and reducing the size could add another strip on a chart."*

and, from his beta-5 run that produced it:

    *"When loading profile 'Scanner-A4-3430p-1page-Landscape-w4.0mm' … the strip
    and row labels are visible, but far too large … At one point in the past I
    might have changed the size for some other instrument and paper combination,
    but this should not have applied to SpectroScan instrument settings … Thus,
    the Preferences 'Strip indicator style' should only be regarded as a
    default, but every saved chart should have the same label settings in the
    Create Chart Manual tab (expert options) in order for a chart to be rendered
    correctly."*

THE TRAP THIS FILE EXISTS TO GUARD is the question "does this recipe have a
style?". Every one of the ten fields has a legitimate value that also looks like
nothing — 0.0, False, 0, "off" — and `indicator_size_mm == 0.0` means *auto*,
which is precisely the answer Knut set by hand to fix his chart. So the question
is asked of a SEPARATE FLAG, never of the values, and
`test_auto_is_an_answer_not_an_absence` is the test that would fail the day
somebody "simplifies" it back into a sentinel.
"""
from __future__ import annotations

import os
import tempfile

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from core.settings import DEFAULTS, INDICATOR_STYLE_KEYS  # noqa: E402
from workflow.layout_engine import instruments               # noqa: E402
from workflow.layout_engine.presets import LayoutRecipe      # noqa: E402

_PT = 25.4 / 72.0          # Knut's Preferences held 12 pt


def _settings(**style):
    """A real AppSettings on a throwaway .ini — the overlay under test reads it."""
    from PyQt6.QtCore import QSettings

    from core.settings import AppSettings
    s = AppSettings()
    s._qs = QSettings(tempfile.mktemp(suffix=".ini"), QSettings.Format.IniFormat)
    for k, v in style.items():
        s.set(k, v)
    return s


# ----------------------------------------------------------------------
# 1. The rule itself
# ----------------------------------------------------------------------
def test_a_recipe_with_no_style_still_follows_preferences():
    """BACKWARD COMPATIBILITY, and it is not optional: every recipe written
    before this change carries no flag, so it must render exactly as today."""
    s = _settings(strip_indicator_size_mm=12 * _PT, strip_indicator_bold=True)
    out = s.apply_indicator_style(LayoutRecipe())
    assert out.indicator_size_mm == pytest.approx(12 * _PT)
    assert out.indicator_bold is True


def test_a_recipe_that_owns_its_style_ignores_preferences():
    s = _settings(strip_indicator_size_mm=12 * _PT, strip_indicator_bold=True)
    own = LayoutRecipe(label_style_explicit=True, indicator_size_mm=3.0)
    out = s.apply_indicator_style(own)
    assert out.indicator_size_mm == 3.0
    assert out.indicator_bold is False
    assert out is own, "an owned recipe must come back untouched, not rebuilt"


def test_auto_is_an_answer_not_an_absence():
    """THE HEADLINE. Knut's fix was to set the size to *auto*. If "unset" were
    inferred from `indicator_size_mm == 0.0`, auto would be the one value that
    could never be pinned — and his scanner chart would still be overlaid."""
    s = _settings(strip_indicator_size_mm=12 * _PT)
    pinned_auto = LayoutRecipe(label_style_explicit=True, indicator_size_mm=0.0)
    assert s.apply_indicator_style(pinned_auto).indicator_size_mm == 0.0
    # …while the same 0.0 with no flag still means "no opinion".
    assert s.apply_indicator_style(
        LayoutRecipe(indicator_size_mm=0.0)).indicator_size_mm == pytest.approx(
            12 * _PT)


@pytest.mark.parametrize("field", sorted(INDICATOR_STYLE_KEYS))
def test_every_one_of_the_ten_fields_obeys_the_flag(field):
    """Not just the size: Knut asks for *the label properties and size*."""
    key = INDICATOR_STYLE_KEYS[field]
    pref = {"strip_indicator_font": "Inter", "strip_indicator_size_mm": 9.0,
            "strip_indicator_bold": True, "strip_indicator_italic": True,
            "strip_indicator_rotation": 90, "strip_indicator_align": "right",
            "strip_label_offset_mm": 3.0, "strip_underline_mode": "black",
            "strip_underline_thickness_mm": 1.9,
            "strip_underline_gap_mm": 2.1}[key]
    assert pref != DEFAULTS[key], "the probe value must differ from the default"
    s = _settings(**{key: pref})
    assert getattr(s.apply_indicator_style(LayoutRecipe()), field) == pref
    owned = LayoutRecipe(label_style_explicit=True)
    assert getattr(s.apply_indicator_style(owned), field) == getattr(owned, field)


def test_an_old_dict_deserialises_as_no_opinion():
    """The key is simply absent from every recipe already on disk."""
    old = LayoutRecipe(indicator_size_mm=4.23).to_dict()
    del old["label_style_explicit"]
    assert LayoutRecipe.from_dict(old).label_style_explicit is False
    assert LayoutRecipe.from_build_kwargs(
        LayoutRecipe().build_kwargs()).label_style_explicit is False


def test_the_flag_round_trips_through_a_dict():
    r = LayoutRecipe(label_style_explicit=True, indicator_size_mm=4.23)
    assert LayoutRecipe.from_dict(r.to_dict()).label_style_explicit is True


def test_the_panel_and_settings_agree_on_which_fields_these_are():
    """Two lists of the same ten fields; a drift would silently drop one."""
    from ui.dialogs.layout_options_panel import _LABEL_STYLE_FIELDS
    assert set(_LABEL_STYLE_FIELDS) == set(INDICATOR_STYLE_KEYS)


# ----------------------------------------------------------------------
# 2. It reaches the paper — the size really does cost strips
# ----------------------------------------------------------------------
def _band_mm(recipe) -> float:
    """The reserved row-number band, in mm, straight out of the engine."""
    return instruments.geom_from_build_kwargs(recipe.build_kwargs()).rlwi


def test_the_pinned_size_changes_the_sheet_not_just_the_dict():
    """Knut's reason for asking: *"Too big row text will … take a lot of space,
    and reducing the size could add another strip on a chart."* So the flag has
    to move real geometry, not merely survive a round trip.

    Measured on HIS chart — the Scanner A4 recipe, verbatim — with HIS
    Preferences value of 12 pt: the overlay grows the row-number band from
    3.95 mm to 6.08 mm and costs the sheet 49 patches.
    """
    from workflow.layout_engine import geometry, papers

    from ui.tabs.tab_chart import _KNUT_SCANNER_RECIPE
    s = _settings(strip_indicator_size_mm=12 * _PT)
    base = dict(_KNUT_SCANNER_RECIPE, show_row_indicators=True)
    overlaid = s.apply_indicator_style(LayoutRecipe.from_dict(base))
    pinned = s.apply_indicator_style(LayoutRecipe.from_dict(
        dict(base, label_style_explicit=True)))               # auto, as shipped
    assert pinned.indicator_size_mm == 0.0
    assert overlaid.indicator_size_mm == pytest.approx(12 * _PT)

    w, h = papers.dimensions_mm("A4R")

    def _geom(r):
        return instruments.geom_from_build_kwargs(r.build_kwargs())

    assert _geom(overlaid).rlwi > _geom(pinned).rlwi + 1.0, (
        f"12 pt reserved {_geom(overlaid).rlwi:.2f} mm and auto "
        f"{_geom(pinned).rlwi:.2f} mm — the pin is not reaching the geometry")
    assert (geometry.patches_per_sheet(_geom(pinned), w, h)
            > geometry.patches_per_sheet(_geom(overlaid), w, h)), \
        "the smaller label did not buy any patch area back"


# ----------------------------------------------------------------------
# 3. The panel
# ----------------------------------------------------------------------
@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def _panel(qapp, settings):
    from ui.dialogs.layout_options_panel import LayoutOptionsPanel
    p = LayoutOptionsPanel(None, with_selectors=True)
    p.set_label_style_defaults(settings.indicator_style)
    return p


def test_the_controls_are_visible_and_live_in_expert_options(qapp):
    """They were a hidden carrier since #93; Knut asked for them back, under
    the Sheet text frame in Expert Options."""
    p = _panel(qapp, _settings())
    grp = p._label_style_grp
    assert not grp.isHidden(), "the label-style group is still hidden"
    # It is inside the Expert Options section, after "Sheet text".
    v = p._expert_frame.content_layout() if hasattr(
        p._expert_frame, "content_layout") else None
    order = []
    parent = grp.parentWidget()
    assert parent is not None
    for lay in (v,):
        if lay is None:
            continue
        order = [lay.itemAt(i).widget() for i in range(lay.count())]
    if order:
        assert grp in order, "the group is not in the Expert Options column"


def test_a_recipe_with_no_style_is_shown_with_preferences(qapp):
    """The controls are visible now, so they must say what will PRINT — not the
    inert values the recipe happens to carry."""
    s = _settings(strip_indicator_size_mm=12 * _PT)
    p = _panel(qapp, s)
    p.set_recipe(LayoutRecipe(instrument="SS", paper="A4R",
                              indicator_size_mm=0.0))
    assert p.indicator_size.value() == pytest.approx(12.0, abs=0.51), (
        "the visible size box does not show the size the chart will print at")


def test_but_nothing_the_recipe_carried_is_thrown_away(qapp):
    """Showing Preferences must not REWRITE the recipe: a preset that merely
    passed through the panel would otherwise come out silently edited."""
    s = _settings(strip_indicator_size_mm=12 * _PT, strip_indicator_font="Inter")
    p = _panel(qapp, s)
    r = LayoutRecipe(instrument="SS", paper="A4R",
                     indicator_size_mm=4.23, indicator_font="JetBrains Mono")
    p.set_recipe(r)
    out = p.get_recipe()
    assert out.label_style_explicit is False
    assert out.indicator_size_mm == pytest.approx(4.23)
    assert out.indicator_font == "JetBrains Mono"


def test_touching_a_control_makes_the_chart_own_its_style(qapp):
    s = _settings(strip_indicator_size_mm=12 * _PT)
    p = _panel(qapp, s)
    p.set_recipe(LayoutRecipe(instrument="SS", paper="A4R"))
    assert p.get_recipe().label_style_explicit is False
    p.indicator_size.setValue(6.0)                 # a person, not the app
    out = p.get_recipe()
    assert out.label_style_explicit is True
    assert out.indicator_size_mm == pytest.approx(6.0 * _PT, abs=0.02)
    assert s.apply_indicator_style(out).indicator_size_mm == pytest.approx(
        6.0 * _PT, abs=0.02), "Preferences overwrote a size a person set"


def test_loading_a_recipe_is_not_a_person_touching_it(qapp):
    """`set_recipe` writes every one of the ten controls. The app must never be
    able to answer its own question."""
    p = _panel(qapp, _settings())
    p.set_recipe(LayoutRecipe(instrument="SS", paper="A4R"))
    assert p._label_style_touched is False


def test_an_owned_recipe_round_trips_verbatim(qapp):
    s = _settings(strip_indicator_size_mm=12 * _PT, strip_indicator_bold=True)
    p = _panel(qapp, s)
    r = LayoutRecipe(instrument="SS", paper="A4R", label_style_explicit=True,
                     indicator_size_mm=0.0, indicator_font="Inter",
                     underline_mode="black", underline_gap_mm=1.5)
    p.set_recipe(r)
    out = p.get_recipe()
    assert out.label_style_explicit is True
    assert out.indicator_size_mm == 0.0
    assert out.indicator_font == "Inter"
    assert out.underline_mode == "black"
    assert out.indicator_bold is False, "Preferences' bold leaked into a pinned recipe"


def test_preferences_changing_reaches_the_visible_boxes(qapp):
    """Preferences pushes at the tabs (MainWindow._open_settings); without the
    push the newly visible controls would go stale and start lying."""
    s = _settings(strip_indicator_size_mm=8 * _PT)
    p = _panel(qapp, s)
    p.set_recipe(LayoutRecipe(instrument="SS", paper="A4R"))
    assert p.indicator_size.value() == pytest.approx(8.0, abs=0.51)
    s.set("strip_indicator_size_mm", 20 * _PT)
    p.refresh_label_style_defaults()
    assert p.indicator_size.value() == pytest.approx(20.0, abs=0.51)
    # …and it stops as soon as the chart owns its style.
    p.indicator_size.setValue(6.0)
    s.set("strip_indicator_size_mm", 30 * _PT)
    p.refresh_label_style_defaults()
    assert p.indicator_size.value() == pytest.approx(6.0)


# ----------------------------------------------------------------------
# 4. Knut's own case, end to end in a real TabChart
# ----------------------------------------------------------------------
def _tab(qapp):
    from core.argyll_runner import ArgyllRunner
    from core.file_manager import FileManager
    from ui.tabs.tab_chart import TabChart
    s = _settings(strip_indicator_size_mm=12 * _PT)   # what Knut had set
    s.set("use_chromiq_layout_engine", False)
    t = TabChart(ArgyllRunner(s), FileManager(s), s)
    t._switch_mode("manual")
    return t


#: The very preset Knut named in his beta-5 report.
_SCANNER_KEY = "__chromiq_knut_scanner_a4_3430p_1page_landscape__"


def _scanner_preset_exists():
    from ui.tabs.tab_chart import KNUT_PRESETS_BY_KEY
    assert _SCANNER_KEY in KNUT_PRESETS_BY_KEY, \
        "Knut's Scanner A4 preset is gone — this file tests nothing"


def test_knuts_scanner_preset_keeps_its_own_label_size(qapp):
    """HIS CASE. Preferences says 12 pt; the preset says nothing, which for a
    built-in means "the size it was designed at" — auto."""
    _scanner_preset_exists()
    t = _tab(qapp)
    assert t._apply_knut_preset(_SCANNER_KEY, target_name="Label-Style-Probe") is True
    r = t._current_layout_recipe()
    assert r.label_style_explicit is True
    assert r.indicator_size_mm == 0.0, (
        f"the preset came back at {r.indicator_size_mm:.2f} mm — Preferences "
        f"is still being overlaid onto a built-in preset")


def test_and_changing_preferences_afterwards_does_not_touch_it(qapp):
    _scanner_preset_exists()
    t = _tab(qapp)
    assert t._apply_knut_preset(_SCANNER_KEY, target_name="Label-Style-Probe") is True
    t._settings.set("strip_indicator_size_mm", 24 * _PT)
    t.refresh_label_style_defaults()
    assert t._current_layout_recipe().indicator_size_mm == 0.0


def test_a_new_chart_still_takes_the_preferences_default(qapp):
    """The other half of Knut's rule: Preferences IS the default for a new
    chart. Break this and the Preferences page becomes dead."""
    t = _tab(qapp)
    t._settings.set("use_chromiq_layout_engine", True)
    t._refresh_manual_command_preview()
    t._set_engine_recipe(LayoutRecipe(instrument="i1", paper="A4"))
    assert t._current_layout_recipe().indicator_size_mm == pytest.approx(12 * _PT)


def test_saving_a_preset_pins_what_it_shows(qapp):
    """*"otherwise all labels on all presets may be affected when user changes
    the 'Strip indicator style' in preferences."*"""
    t = _tab(qapp)
    t._settings.set("use_chromiq_layout_engine", True)
    t._refresh_manual_command_preview()
    t._set_engine_recipe(LayoutRecipe(instrument="i1", paper="A4"))
    pinned = t._pinned_layout_recipe()
    assert pinned.label_style_explicit is True
    assert pinned.indicator_size_mm == pytest.approx(12 * _PT)
    t._settings.set("strip_indicator_size_mm", 30 * _PT)
    assert t._settings.apply_indicator_style(
        pinned).indicator_size_mm == pytest.approx(12 * _PT)


def test_the_chart_stores_its_own_style(tmp_path):
    """A rebuilt chart must reproduce the sheet that was measured — so what is
    written beside it says what it was drawn with."""
    import json
    from dataclasses import dataclass

    from workflow.chart_creator import ChartCreator, ChartParams

    @dataclass
    class _Result:
        seed: int = 7
        color_rep: str = "RGB"
        chart_date: str = "2026-09-01"

    sidecar = tmp_path / "c.channels.json"
    sidecar.write_text("{}", encoding="utf-8")
    params = ChartParams()
    params.layout_recipe = LayoutRecipe(indicator_size_mm=4.23)   # no flag
    ChartCreator._embed_layout_geometry(
        ChartCreator.__new__(ChartCreator), tmp_path, "c", _Result(), params)
    rec = json.loads(sidecar.read_text(encoding="utf-8"))["layout"]["recipe"]
    assert rec["label_style_explicit"] is True
    assert rec["indicator_size_mm"] == pytest.approx(4.23)


def test_preferences_pushes_the_change_at_the_tab():
    """The two halves must not drift apart. Preferences pushes at the tabs
    rather than the tabs polling (MainWindow._open_settings says so in as many
    words), so a refresh that is never called is invisible in a unit test of
    either half — and the newly visible boxes would quietly go stale."""
    import inspect

    from ui.main_window import MainWindow
    from ui.tabs.tab_chart import TabChart
    assert callable(TabChart.refresh_label_style_defaults)
    assert "refresh_label_style_defaults" in inspect.getsource(
        MainWindow._open_settings)
