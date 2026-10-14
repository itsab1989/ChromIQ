"""4.3.5 beta 3, Knut #182 6143186611 / 6144104040.

1. The 3D tool's colour view: the skin is sampled as finely as its seams, and
   Knut's stepwise grid exists as an EXPERIMENTAL spread that is off.
2. A preset picked in FROM PROFILE GAMUT with no built profile says why
   instead of doing nothing.
4. Strip letters that run into their neighbours are detected; the words wait
   for approval.
5. A "By columns / rows" grid fits on a DTP51 (its strip's own max/min patches
   no longer eat two of the asked rows), and on an i1Pro it fires only when a
   patch would have to be smaller than 1 mm.
6. The explained PostScript question is proposed, hidden until approved.
"""
from __future__ import annotations

import inspect
import os
import types

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from workflow import gamut_target as gt  # noqa: E402
from workflow import measurement_messages as M  # noqa: E402


# ---- 1 ---------------------------------------------------------------------
def test_the_skin_is_sampled_as_finely_as_its_seams():
    from workflow import patch_cube as pc
    assert pc.OUTLINE_FACE_STEPS == pc.OUTLINE_EDGE_STEPS


def _cube_solid(n: int = 9):
    """A device cube mapped linearly onto a box in Lab: L 10..90, a/b -40..40."""
    g = np.linspace(0.0, 1.0, n)
    r, gg, b = np.meshgrid(g, g, g, indexing="ij")
    lab = np.stack([10 + 80 * r, -40 + 80 * gg, -40 + 80 * b], -1).reshape(-1, 3)
    return gt._GamutSolid(lab, n=n)


def test_the_gamut_solid_knows_inside_from_outside():
    s = _cube_solid()
    inside = s.inside([(50, 0, 0), (89, 39, -39), (95, 0, 0), (50, 45, 0)])
    assert list(inside) == [True, True, False, False]


@pytest.mark.parametrize("goal", [20, 64, 150])
def test_the_stepwise_grid_never_overshoots_its_goal(goal):
    s = _cube_solid()
    pts, centres, spacing, history = gt._stepwise_grid(
        goal, s, np.zeros((0, 3)), start=5.0)
    assert 0 < len(pts) <= goal
    assert len(history) >= 2 and spacing > 0
    assert all(s.inside(pts))
    # the centres sit half a step off the lattice, never on a lattice point
    if len(centres):
        d = gt._nearest(np.asarray(centres), np.asarray(pts))[1]
        assert d.min() > 0.4 * spacing


def test_the_shipped_selection_is_still_the_even_spread():
    sig = inspect.signature(gt.select_gamut_targets)
    assert sig.parameters["spread"].default == gt.SPREAD_EVEN
    assert gt.GamutSelection("x", 1, 1, 1, "absolute", "safe").spread == "even"
    from ui.tabs import tab_chart
    src = inspect.getsource(tab_chart.TabChart._on_generate_gamut)
    assert '"gamut_target_spread", SPREAD_EVEN' in src
    from core.settings import DEFAULTS
    assert "gamut_target_spread" not in DEFAULTS, "no control may show it yet"


def test_only_a_grid_chart_records_how_it_was_spread(tmp_path):
    sel = gt.GamutSelection(master_version="r2", master_total=1,
                            in_gamut_total=1, requested=1,
                            intent="absolute", margin="safe")
    sel.targets = [(0, (50.0, 0.0, 0.0), (50.0, 50.0, 50.0))]
    gt.write_colorimetric_reference(sel, tmp_path / "even.ti3")
    assert "CHROMIQ_SPREAD" not in (tmp_path / "even.ti3").read_text(encoding="utf-8")
    sel.spread = gt.SPREAD_GRID
    gt.write_colorimetric_reference(sel, tmp_path / "grid.ti3")
    assert 'CHROMIQ_SPREAD "grid"' in (tmp_path / "grid.ti3").read_text(encoding="utf-8")


def test_the_colour_view_help_names_the_seams_since_approved():
    """Knut, #182 6152691121 (2026-10-13): approved and shown."""
    from ui.dialogs import patch_cube_dialog as d
    assert M.M_HELP_COLOUR_VIEW_SEAMS.approved
    assert d._view_help() == M.M_HELP_COLOUR_VIEW_SEAMS.render()[1]
    assert "seams" in d._view_help()


# ---- 2 ---------------------------------------------------------------------
def test_a_preset_in_the_gamut_module_without_a_profile_says_why(monkeypatch):
    from ui.tabs import tab_chart
    shown = []

    class _Dialog:
        def __init__(self, title, body, parent, **kw):
            shown.append((title, body))

        def exec(self):
            return 0

    monkeypatch.setattr(tab_chart, "InfoDialog", _Dialog)
    stand_in = types.SimpleNamespace(
        _runner=types.SimpleNamespace(is_running=False),
        _gamut_profile=lambda: None,
        _gamut_no_profile_message=lambda: ("This run needs a finished profile first", "body"),
        _seed_knut_preset=lambda *a: pytest.fail("the preset must not be applied"))
    key = next(iter(tab_chart.KNUT_PRESETS_BY_KEY))
    assert tab_chart.TabChart._apply_knut_layout_for_gamut(stand_in, key) is False
    assert shown == [("This run needs a finished profile first", "body")]


# ---- 4 ---------------------------------------------------------------------
def _kw(cols, rows, size_mm, **extra):
    from workflow.layout_engine.presets import LayoutRecipe
    r = LayoutRecipe.from_dict({
        "instrument": "i1", "paper": "A4", "dpi": 200,
        "layout_mode": "area_first", "area_method": "by_grid",
        "area_cols": cols, "area_rows": rows, "area_ratio": 1.0,
        "margin_top": 41.0, "margin_right": 14.0, "margin_bottom": 21.0,
        "margin_left": 26.0, "use_instrument_margins": False,
        "clip_border": True, "clip_border_width_mm": 26.0,
        "show_strip_indicators": True, "indicator_font": "JetBrains Mono",
        "indicator_size_mm": size_mm, **extra})
    kw = r.build_kwargs()
    kw["area_target_count"] = cols * rows
    return kw


def _crowd(cols, size_mm, **extra):
    from workflow.layout_engine import instruments, raster
    kw = _kw(cols, 20, size_mm, **extra)
    return raster.strip_label_crowding(instruments.geom_from_build_kwargs(kw), kw)


def test_knuts_40_strips_at_12_pt_run_into_each_other():
    c = _crowd(40, 4.23)
    assert c is not None and c.explicit
    assert c.labels == ("AA", "AB")
    assert c.gap_mm < 0                      # they overlap
    assert c.fits_pt is not None and c.fits_pt < 12


def test_auto_and_a_roomy_chart_are_not_flagged():
    assert _crowd(40, 0.0) is None           # "auto" fits them
    assert _crowd(20, 4.23) is None          # 20 strips: one letter each
    assert _crowd(40, 4.23, indicator_rotation=90) is None


def test_the_crowding_words_are_shown_since_approved():
    """Knut, #182 6152691121 (2026-10-13)."""
    from ui.tabs.tab_chart import strip_label_crowding_notice
    c = _crowd(40, 4.23)
    assert M.M_CHART_STRIP_LABELS_CROWDED.approved
    assert strip_label_crowding_notice(c) == strip_label_crowding_notice(c, unapproved=True)
    text = strip_label_crowding_notice(c)
    assert text and "{" not in text and "“AA”" in text and "auto" in text
    assert strip_label_crowding_notice(_crowd(40, 0.0), unapproved=True) is None


# ---- 5 ---------------------------------------------------------------------
def test_a_dtp51_keeps_the_rows_it_is_asked_for():
    from workflow.layout_engine import area_fit
    for cols, rows in ((20, 5), (5, 5), (10, 20)):
        kw = _kw(cols, rows, 0.0, instrument="51")
        area_fit._CACHE.clear()
        assert area_fit.pinned_grid_shortfall(kw) is None, (cols, rows)


def test_the_grid_warning_waits_for_a_patch_under_1_mm():
    from workflow.layout_engine import area_fit
    area_fit._CACHE.clear()
    # This layout holds 117 rows of 1.00 mm; the 118th would need less.
    ok = _kw(20, 117, 0.0)
    size = area_fit.derive_area_patch_size(ok)
    assert area_fit.pinned_grid_shortfall(ok) is None and size[1] >= 1.0
    area_fit._CACHE.clear()
    assert area_fit.pinned_grid_shortfall(_kw(20, 118, 0.0)) == (20, 118, 20, 117)


# ---- 6 ---------------------------------------------------------------------
def test_the_explained_postscript_texts_are_shown_since_approved():
    """Knut, #182 6152691121 (2026-10-13): the question, its two choices and
    the merged help (the project rule, then each choice explained)."""
    from ui.tabs.tab_print import ps_texts
    for m in (M.M_PRINT_PS_ASK_EXPLAINED, M.M_PRINT_PS_FORM_CHOICE_EXPLAINED,
              M.M_PRINT_PS_FORM_HELP_PROJECT_EXPLAINED):
        assert m.approved
    ask, choice, help_ = ps_texts()
    assert ask is M.M_PRINT_PS_ASK_EXPLAINED
    assert choice is M.M_PRINT_PS_FORM_CHOICE_EXPLAINED
    assert help_ is M.M_PRINT_PS_FORM_HELP_PROJECT_EXPLAINED
    paras = help_.body.split("\n\n")
    assert len(paras) == 4
    assert paras[0].startswith("A profile only fits photos")
    assert "kept for the whole project" in paras[0]
    assert paras[1].startswith("Send the colours unchanged:")
    assert paras[2].startswith("Let the printer adjust the colours:")
    assert paras[3].startswith("If the print dialog has an RGB colour setting")
    ask, choice, help_ = ps_texts(proposed=True)
    assert ask is M.M_PRINT_PS_ASK_EXPLAINED
    lines = choice.render()[1].split("\n")
    assert len(lines) == 2 and "Photoshop" in lines[0] and "Preview" in lines[1]
