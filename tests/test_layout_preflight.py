"""Tests for the headless pre-flight checks."""
from workflow.layout_engine import geometry, instruments, preflight


def test_clean_layout_ok():
    geom = instruments.build("i1")
    lay = geometry.compute(geom, 210.0, 297.0, 60)
    rep = preflight.check(geom, lay)
    assert rep.ok
    assert not rep.errors
    assert rep.info


def test_the_dead_low_contrast_branch_is_gone():
    """No caller in the app passed the strips, so the English-only warning
    could never be shown (review 4.3.19 r1, N7); the note a person sees is the
    Create Chart log line."""
    import inspect
    assert "low_contrast_passes" not in inspect.signature(preflight.check).parameters
    src = inspect.getsource(preflight)
    assert "a very dark patch" not in src


def test_indicator_width_warning():
    geom = instruments.build("i1")
    # auto size fits the strip → no warning
    assert preflight.indicator_width_warning(geom, 300, size_mm=0.0) is None
    # an explicit oversized indicator overflows the strip → warning
    assert preflight.indicator_width_warning(geom, 300, size_mm=12.0) is not None
    # hidden indicators never warn
    assert preflight.indicator_width_warning(geom, 300, size_mm=12.0, show=False) is None


def test_sub_minimum_patch_errors():
    # heavy down-scale pushes i1 patches below the 6 mm floor (4 x 5 mm)
    geom = instruments.build("i1", pscale=0.5)
    lay = geometry.compute(geom, 210.0, 297.0, 60)
    rep = preflight.check(geom, lay)
    assert not rep.ok
    assert any("smaller than the 6.0 mm" in e and "4.0 mm" in e
               for e in rep.errors)
    assert not any("—" in e for e in rep.errors)


def test_the_shown_texts_are_translated(monkeypatch):
    """Preferences > Chart Layout shows these two texts, so they go through
    tr() and the German catalogue has them."""
    import json
    from pathlib import Path
    import core.i18n as i18n
    de = json.loads((Path(__file__).resolve().parents[1]
                     / "data/i18n/de.json").read_text(encoding="utf-8"))
    monkeypatch.setattr(i18n, "tr", lambda s: de.get(s, s))
    geom = instruments.build("i1", pscale=0.5)
    lay = geometry.compute(geom, 210.0, 297.0, 60)
    err = preflight.check(geom, lay).errors[0]
    assert "Feldskalierung" in err and "{" not in err
    assert not err.startswith("The patches")
    warn = preflight.indicator_width_warning(instruments.build("i1"), 300,
                                             size_mm=12.0)
    assert warn and "{" not in warn
    assert not warn.startswith("The strip letters")


# ---- review 4.3.19 r2, SF-A: the advice names what really helps ----------

def _small(recipe_kwargs: dict):
    """The patch-size error for a real `LayoutRecipe` built the way
    Preferences > Chart Layout builds it (`_update_layout_calc`)."""
    from dataclasses import replace
    from workflow.layout_engine import papers
    from workflow.layout_engine.presets import LayoutRecipe
    recipe_kwargs = {"instrument": "i1", **recipe_kwargs}
    r = replace(LayoutRecipe(), paper="A4", **recipe_kwargs)
    geom = instruments.geom_from_build_kwargs(r.build_kwargs())
    w, h = papers.dimensions_mm(r.paper)
    cap = geometry.patches_per_sheet(geom, w, h)
    rep = preflight.check(geom, geometry.compute(geom, w, h, cap), recipe=r)
    assert len(rep.errors) == 1, rep.errors
    return rep.errors[0], preflight.small_patch_case(r, geom, 6.0)


# ---- review 4.3.19 r3, N1: the area advice names the control for the small
# side. In "By columns / rows" the strips set only the width (`pwid`) and the
# patches per strip only the height (`plen`); in "By patch width" the minimum
# width sets the width and the height % the height. Measured on i1, A4.

def _area(method: str, **kw):
    return _small(dict(layout_mode="area_first", area_method=method, **kw))


def test_by_grid_only_the_height_small_names_the_rows_only():
    # The review's case: 20 strips of 60 on A4 are 8.89 mm wide, 3.73 mm tall.
    err, case = _area("by_grid", area_cols=20, area_rows=60)
    assert case is preflight.SMALL_AREA_GRID_HEIGHT
    assert err.startswith("The patches are 3.7 mm tall, shorter than the 6.0 mm")
    assert "choose fewer “Patches per strip (rows)”" in err
    assert "Strips (columns)" not in err and "Minimum" not in err


def test_by_grid_only_the_width_small_names_the_strips_only():
    err, case = _area("by_grid", area_cols=60, area_rows=20)   # 2.96 x 13.2
    assert case is preflight.SMALL_AREA_GRID_WIDTH
    assert err.startswith("The patches are 3.0 mm wide, narrower than the 6.0 mm")
    assert "choose fewer “Strips (columns)”" in err
    assert "Patches per strip (rows)" not in err and "Minimum" not in err


def test_by_grid_both_small_names_both_counts():
    err, case = _area("by_grid", area_cols=60, area_rows=60)   # 2.96 x 3.73
    assert case is preflight.SMALL_AREA_GRID_BOTH
    assert err.startswith("The patches are 3.0 mm wide and 3.7 mm tall")
    assert ("fewer “Strips (columns)” for wider patches and fewer "
            "“Patches per strip (rows)” for taller ones") in err
    assert "Patch scale" not in err and "instrument." not in err


def test_by_width_only_the_width_small_names_the_minimum_width_only():
    err, case = _area("by_width", area_min_patch_mm=3.0, area_ratio=3.0)  # 3.01 x 9.14
    assert case is preflight.SMALL_AREA_WIDTH_WIDTH
    assert err.startswith("The patches are 3.0 mm wide")
    assert err.endswith("To make them wider, choose a larger “Minimum patch width”.")
    assert "Minimum patch height" not in err and "Strips" not in err


def test_by_width_only_the_height_small_names_the_minimum_height_only():
    err, case = _area("by_width", area_min_patch_mm=8.0, area_ratio=0.3)  # 8.09 x 2.46
    assert case is preflight.SMALL_AREA_WIDTH_HEIGHT
    assert err.startswith("The patches are 2.5 mm tall")
    assert err.endswith("To make them taller, choose a larger “Minimum patch height”.")
    assert "Minimum patch width" not in err and "Patches per strip" not in err


def test_by_width_both_small_names_both_minimums():
    err, case = _area("by_width", area_min_patch_mm=3.0, area_ratio=1.0)  # 3.01 x 3.05
    assert case is preflight.SMALL_AREA_WIDTH_BOTH
    assert ("a larger “Minimum patch width” for wider patches and a larger "
            "“Minimum patch height” for taller ones") in err
    assert "Patch scale" not in err


def test_a_honeycomb_names_the_width_control_even_when_the_height_is_small():
    """Its height follows its width, and the panel greys the height % (and,
    with the strips set, the rows), so only the width control helps."""
    err, case = _small(dict(instrument="CR30", hflag=True, layout_mode="area_first",
                            area_method="by_width", area_min_patch_mm=6.5))
    assert case is preflight.SMALL_AREA_WIDTH_HEX      # 6.57 wide, 5.69 tall
    assert err.endswith("choose a larger “Minimum patch width”.")
    assert "Minimum patch height" not in err
    err, case = _small(dict(instrument="SS", hflag=True, layout_mode="area_first",
                            area_method="by_grid", area_cols=40, area_rows=0))
    assert case is preflight.SMALL_AREA_GRID_HEX       # 4.26 wide, 3.69 tall
    assert err.endswith("choose fewer “Strips (columns)”.")
    assert "Patches per strip" not in err


def test_the_named_controls_really_set_that_side():
    """Not assumed: fewer strips widens and leaves the height, fewer rows
    raises the height and leaves the width; likewise the two minimums."""
    from dataclasses import replace
    from workflow.layout_engine.presets import LayoutRecipe

    def g(**kw):
        r = replace(LayoutRecipe(), instrument="i1", paper="A4",
                    layout_mode="area_first", **kw)
        geom = instruments.geom_from_build_kwargs(r.build_kwargs())
        return round(geom.pwid, 2), round(geom.plen, 2)
    w0, h0 = g(area_method="by_grid", area_cols=20, area_rows=60)
    w1, h1 = g(area_method="by_grid", area_cols=15, area_rows=60)
    w2, h2 = g(area_method="by_grid", area_cols=20, area_rows=30)
    assert w1 > w0 and h1 == h0
    assert h2 > h0 and w2 == w0
    w0, h0 = g(area_method="by_width", area_min_patch_mm=8.0, area_ratio=0.3)
    w3, h3 = g(area_method="by_width", area_min_patch_mm=8.0, area_ratio=0.8)
    assert h3 > h0 and w3 == w0
    w4, _ = g(area_method="by_width", area_min_patch_mm=12.0, area_ratio=0.3)
    assert w4 > w0


def test_a_typed_patch_size_names_the_patch_size_not_the_scale():
    err, case = _small(dict(layout_mode="patch_first", patch_w_mm=4.0,
                            patch_h_mm=4.0, pscale=2.0))
    assert case is preflight.SMALL_TYPED
    assert "type a larger “Patch size”" in err
    assert "“Patch scale” does not change it" in err


def test_one_side_typed_names_both():
    # 4 mm typed width, the height from the i1's 10 mm x 0.3 = 3.0 mm
    err, case = _small(dict(layout_mode="patch_first", patch_w_mm=4.0,
                            patch_h_mm=0.0, pscale=0.3))
    assert case is preflight.SMALL_TYPED_AND_SCALE
    assert "“Patch size”" in err and "“Patch scale”" in err


def test_the_scale_names_the_scale():
    err, case = _small(dict(layout_mode="patch_first", pscale=0.5))
    assert case is preflight.SMALL_SCALE
    assert err.endswith("To make them larger, choose a larger “Patch scale”.")


def test_no_text_sends_anyone_to_a_larger_instrument():
    for text in preflight.SMALL_PATCH_TEXTS:
        assert "instrument." not in text and "larger paper" not in text
        assert "—" not in text


def test_the_dialog_passes_its_recipe():
    import inspect
    from ui.dialogs import settings_dialog
    src = inspect.getsource(settings_dialog.SettingsDialog._update_layout_calc)
    assert "preflight.check(geom, layout, recipe=r)" in src


def test_every_case_is_translated_with_its_own_labels():
    import json
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    for cat in sorted((root / "data/i18n").glob("*.json")):
        d = json.loads(cat.read_text(encoding="utf-8"))
        for key in preflight.SMALL_PATCH_TEXTS:
            assert d.get(key), (cat.name, key[-60:])
            for ph in ("{size}", "{width}", "{height}", "{floor}", "{strips}",
                       "{rows}", "{min_width}",
                       "{min_height}", "{patch_size}", "{patch_scale}"):
                assert (ph in key) == (ph in d[key]), (cat.name, ph)
