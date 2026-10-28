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
    r = replace(LayoutRecipe(), instrument="i1", paper="A4", **recipe_kwargs)
    geom = instruments.geom_from_build_kwargs(r.build_kwargs())
    w, h = papers.dimensions_mm(r.paper)
    cap = geometry.patches_per_sheet(geom, w, h)
    rep = preflight.check(geom, geometry.compute(geom, w, h, cap), recipe=r)
    assert len(rep.errors) == 1, rep.errors
    return rep.errors[0], preflight.small_patch_case(r, geom, 6.0)


def test_chart_area_by_columns_and_rows_names_the_counts():
    err, case = _small(dict(layout_mode="area_first", area_method="by_grid",
                            area_cols=60, area_rows=60))
    assert case is preflight.SMALL_AREA_GRID
    assert "fewer “Strips (columns)” or fewer “Patches per strip (rows)”" in err
    assert "Patch scale" not in err and "instrument." not in err


def test_chart_area_by_patch_width_names_the_minimum():
    err, case = _small(dict(layout_mode="area_first", area_method="by_width",
                            area_min_patch_mm=3.0, area_ratio=1.0))
    assert case is preflight.SMALL_AREA_WIDTH
    assert "“Minimum patch width”" in err and "“Minimum patch height”" in err
    assert "Patch scale" not in err


def test_a_typed_patch_size_names_the_patch_size_not_the_scale():
    err, case = _small(dict(layout_mode="patch_first", patch_w_mm=4.0,
                            patch_h_mm=4.0, pscale=2.0))
    assert case is preflight.SMALL_TYPED
    assert "type a larger “Patch size”" in err
    assert "“Patch scale” does not change it" in err


def test_one_side_typed_names_both():
    # 4 mm typed width, the height from the i1's 13 mm x 0.3 = 3.9 mm
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
            for ph in ("{size}", "{floor}", "{strips}", "{rows}", "{min_width}",
                       "{min_height}", "{patch_size}", "{patch_scale}"):
                assert (ph in key) == (ph in d[key]), (cat.name, ph)
