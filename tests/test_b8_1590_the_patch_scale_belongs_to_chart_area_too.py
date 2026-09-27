"""B8-1590 (Knut, #182 5858752082): the patch scale belongs to "Prioritise chart
area" as well.

B8-1540 fixed Knut's report that a patch size typed under "Prioritise patch
size" still ruled a "Prioritise chart area" chart, and in doing so held back the
patch scale and the chart offset too. Beta 45 shipped that. Knut: "it has been
the intention that it should work, and did work before. If this is removed that
is a change not approved and it will change other presets when loading them.
This setting should be part of the 'Prioritise chart area' mode."

Measured against the v4.3.0-beta.44 code, every one of the 172 built-in engine
presets: beta 45 laid 19 out differently (the photo cards, patch scale 0.95);
with the scale restored all 172 equal beta 44 again. The snapshot was
generated from the beta 44 tag, so this compares with what beta 44 did, not
with what this tree thinks it did."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from workflow.layout_engine import geometry, papers
from workflow.layout_engine.instruments import geom_from_build_kwargs
from workflow.layout_engine.presets import LayoutRecipe

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = json.loads(
    (ROOT / "tests/data/b8_1590_builtin_geometry_beta44.json").read_text(
        encoding="utf-8"))


def _presets():
    from ui.tabs.tab_chart import KNUT_PRESETS
    return {p.key: p for p in KNUT_PRESETS if getattr(p, "layout_recipe", None)}


def _laid_out(p) -> dict:
    rec = LayoutRecipe.from_dict(dict(p.layout_recipe))
    g = geom_from_build_kwargs(rec.build_kwargs())
    w, h = papers.dimensions_mm(rec.paper)
    lay = geometry.compute(g, w, h, int(p.patches))
    out = {}
    for f in SNAPSHOT["fields"]:
        v = getattr(g, f) if hasattr(g, f) else getattr(lay, f)
        out[f] = round(v, 4) if isinstance(v, float) else v
    out["pages"] = lay.pages
    return out


def test_every_built_in_engine_preset_is_in_the_snapshot(qapp):
    assert set(_presets()) == set(SNAPSHOT["presets"])
    assert len(SNAPSHOT["presets"]) >= 170


def test_every_built_in_engine_preset_lays_out_as_in_beta_44(qapp):
    presets = _presets()
    moved = {k: (want, _laid_out(presets[k]))
             for k, want in SNAPSHOT["presets"].items()
             if _laid_out(presets[k]) != want}
    assert not moved, sorted(moved)[:5]


def test_the_photo_cards_carry_the_scale_that_moved_them(qapp):
    """The 19 that beta 45 moved are the ones with a patch scale of 0.95, and
    that scale now reaches the engine."""
    scaled = [p for p in _presets().values()
              if abs(float(dict(p.layout_recipe).get("pscale", 1.0)) - 1.0) > 1e-9]
    assert len(scaled) == 19
    for p in scaled:
        rec = LayoutRecipe.from_dict(dict(p.layout_recipe))
        assert rec.layout_mode == "area_first"
        assert rec.build_kwargs()["pscale"] == pytest.approx(0.95)


def test_the_typed_size_and_offset_still_have_no_say_in_chart_area():
    """Knut's original report stays fixed."""
    r = LayoutRecipe(instrument="i1", paper="A4", layout_mode="area_first",
                     patch_w_mm=14.0, patch_h_mm=10.0, offset_x_mm=6.0,
                     offset_y_mm=6.0, pscale=0.75)
    kw = r.build_kwargs()
    assert (kw["patch_w"], kw["patch_h"], kw["offset_x"], kw["offset_y"]) \
        == (None, None, 0.0, 0.0)
    assert kw["pscale"] == 0.75


def test_the_patch_scale_row_is_shown_in_both_modes(qapp):
    """What a mode shows, it honours: the row is on screen in both."""
    from ui.dialogs.layout_options_panel import LayoutOptionsPanel
    panel = LayoutOptionsPanel()
    try:
        panel.show()
        for mode in ("area_first", "patch_first", "area_first"):
            panel.layout_mode.setCurrentIndex(panel.layout_mode.findData(mode))
            qapp.processEvents()
            assert all(w.isVisible() for w in panel._patch_scale_row), mode
            size_shown = any(w.isVisible() for w in panel._patch_size_row)
            assert size_shown == (mode == "patch_first")
    finally:
        panel.close()
        panel.deleteLater()
