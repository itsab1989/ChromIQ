"""Recipes saved before 4.3.14 lay out exactly as they did (Basti,
2026-10-25: "leave the current presets as they are. he can give new ones if
he wants to"). The clip-border rules of 4.3.14 (row_label_geometry.md
§R1.3a: row labels and strip letters in the free part of the border, a width
at the base margin as a band of that width) apply only to recipes made or
saved from 4.3.14 on. `LayoutRecipe.clip_border_free_space` says which: a
stored dict without it is an old recipe."""
from __future__ import annotations

import inspect
import json
import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from workflow.layout_engine import geometry, instruments, papers   # noqa: E402
from workflow.layout_engine.presets import LayoutRecipe            # noqa: E402

#: Knut's forum 149832 preset, as his 4.3.13 saved it (no flag).
KNUT = dict(instrument="i1", paper="100x150", dpi=200, border=10.0,
            clip_border=True, clip_border_width_mm=11.0, clip_side="left",
            clip_content_mode="branding",
            clip_text="{project} - {rundescription} - {paper}\n"
                      "{instrument} - {patchcount} - {page} - {date} - {seed}",
            clip_text_font="JetBrains Mono", clip_text_size_mm=2.12,
            show_row_indicators=True, indicator_size_mm=2.12,
            indicator_font="JetBrains Mono", text_edge_clip_mm=2.0,
            margin_left=11.0, margin_top=17.0, margin_right=5.0,
            margin_bottom=13.0, layout_mode="area_first", area_method="by_grid",
            area_cols=10, area_rows=12, area_min_patch_mm=17.5, pscale=0.95,
            sscale=0.6, layout_explicit=True, label_style_explicit=True)


def _margin_left(r: LayoutRecipe) -> float:
    return instruments.geom_from_build_kwargs(r.build_kwargs()).margin_l


def test_a_stored_recipe_without_the_flag_is_an_old_one():
    assert LayoutRecipe.from_dict(dict(KNUT)).clip_border_free_space is False
    assert LayoutRecipe().clip_border_free_space is True
    new = LayoutRecipe.from_dict(dict(KNUT, clip_border_free_space=True))
    assert LayoutRecipe.from_dict(new.to_dict()).clip_border_free_space is True
    old = LayoutRecipe.from_dict(dict(KNUT))
    assert LayoutRecipe.from_dict(old.to_dict()).clip_border_free_space is False


def test_knuts_old_preset_keeps_its_15_5_mm_and_a_new_one_gets_less():
    old = LayoutRecipe.from_dict(dict(KNUT))
    new = LayoutRecipe.from_dict(dict(KNUT, clip_border_free_space=True))
    assert round(_margin_left(old), 1) == 15.5
    assert _margin_left(new) < _margin_left(old) - 2.0


def test_ten_millimetres_keeps_its_old_meaning_on_an_old_recipe():
    old = LayoutRecipe.from_dict(dict(KNUT, clip_border_width_mm=10.0))
    g = instruments.geom_from_build_kwargs(old.build_kwargs())
    assert g.lbord == 0.0
    new = LayoutRecipe.from_dict(dict(KNUT, clip_border_width_mm=10.0,
                                      clip_border_free_space=True))
    assert instruments.geom_from_build_kwargs(new.build_kwargs()).lbord > 0


def test_the_kwargs_of_a_new_recipe_are_unchanged():
    """The key goes into the build kwargs only for an old recipe, so every
    new chart's kwargs are what they were."""
    assert "clip_border_free_space" not in LayoutRecipe().build_kwargs()
    old = LayoutRecipe.from_dict(dict(KNUT))
    assert old.build_kwargs()["clip_border_free_space"] is False


def test_live_build_kwargs_are_new_and_stored_ones_old():
    kw = LayoutRecipe().build_kwargs()
    assert LayoutRecipe.from_build_kwargs(kw).clip_border_free_space is True
    stored = dict(kw, nolpcbord=False)
    assert LayoutRecipe.from_dict(stored).clip_border_free_space is False


def test_the_old_rule_never_counts_differently_from_4_3_13():
    """The frozen v4.3.13 counts, for recipes read as stored before 4.3.14."""
    from workflow.layout_engine import area_fit
    from workflow.layout_engine.presets import default_recipe
    old_counts = json.loads((Path(__file__).parent / "data" /
                             "patch_counts_v4_3_13.json").read_text("utf-8"))
    for key in ("CR30|A4|class_patch|hflag=False",
                "CR30|10x15cm|class_area|hflag=False",
                "SS|A4|class_patch|hflag=True"):
        inst, paper, name, _hx = key.split("|")
        mode = "area_first" if "area" in name else "patch_first"
        r = LayoutRecipe(instrument=inst, paper=paper, layout_mode=mode)
        if key.endswith("True"):
            r.hflag = True
        d = {k: v for k, v in r.to_dict().items()
             if k != "clip_border_free_space"}
        r = LayoutRecipe.from_dict(d)
        kw = r.build_kwargs()
        if kw.get("layout_mode") == "area_first":
            s = area_fit.derive_area_patch_size(kw)
            kw = {**kw, "patch_w": s[0], "patch_h": s[1]}
        w, h = papers.dimensions_mm(paper)
        n = geometry.compute(instruments.geom_from_build_kwargs(kw), w, h,
                             100_000).patches_per_page
        assert n == old_counts[key], (key, n, old_counts[key])


def test_the_panel_carries_the_flag_and_a_new_name_gets_the_new_rule():
    from ui.dialogs import layout_options_panel as P
    from ui.tabs import tab_chart as T
    src = inspect.getsource(P.LayoutOptionsPanel)
    assert "self._clip_border_free_space = bool(" in src
    assert "r.clip_border_free_space = bool(" in src
    save = inspect.getsource(T.TabChart._on_preset_save)
    assert 'capture["layout_recipe"]["clip_border_free_space"] = True' in save
