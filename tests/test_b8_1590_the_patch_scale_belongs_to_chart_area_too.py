"""B8-1590, REVERTED by Knut's ruling (#182 5859162180): in "Prioritise chart
area" the patch scale is neither shown nor used, also for the photo cards.

B8-1540 made "Prioritise chart area" ignore the three controls it hides: the
typed patch size, the chart offset and the patch scale. Knut first asked for the
scale back (5858752082), then checked beta 44 and found the row had only ever
been shown under "Prioritise patch size": "That field shall not be visible or
usable in 'Prioritise chart area', also for the photo cards." So beta 45's rule
stands, and this file pins what it does to every built-in engine preset.

Both snapshots were generated from release tags, never from this tree:

* every built-in engine preset as the v4.3.0-beta.44 code laid it out, and
* the 19 photo cards as the v4.3.0-beta.45 code lays them out. They carry a
  patch scale of 0.95, which beta 44 applied and chart-area mode now ignores:
  the same patches, strips and pages, the patches 0.03 mm shorter and the gaps
  0.03 mm wider.

Every other built-in preset must still equal beta 44.

The nine "by Pharmacist" charts Knut added in beta 47 (#182 5860041950) did not
exist in beta 44, so they are pinned to a third snapshot, taken from the beta 47
code that first shipped them, and a later change cannot move one either. The
five of 4.3.1 (#182 5875467209) are pinned the same way, to a fourth snapshot
taken from the 4.3.1 code."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from workflow.layout_engine import geometry, papers
from workflow.layout_engine.instruments import geom_from_build_kwargs
from workflow.layout_engine.presets import (HIDES_PATCH_CONTROLS_KEY,
                                            LayoutRecipe, build_kwargs_as_built)

ROOT = Path(__file__).resolve().parents[1]
BETA44 = json.loads(
    (ROOT / "tests/data/b8_1590_builtin_geometry_beta44.json").read_text(
        encoding="utf-8"))
BETA45_PHOTO_CARDS = json.loads(
    (ROOT / "tests/data/b8_1590_photo_cards_geometry_beta45.json").read_text(
        encoding="utf-8"))
BETA47_PHARMACIST = json.loads(
    (ROOT / "tests/data/b8_1590_pharmacist_geometry_beta47.json").read_text(
        encoding="utf-8"))
#: The five of 4.3.1 (#182 5875467209), from the 4.3.1 code that first ships
#: them (B8-1700).
V431_PHARMACIST = json.loads(
    (ROOT / "tests/data/b8_1590_pharmacist_geometry_431.json").read_text(
        encoding="utf-8"))

#: The presets Knut's ruling moves away from beta 44, named one by one so a
#: preset cannot join or leave the list without this file changing.
PHOTO_CARDS = (
    "__chromiq_knut_i1_photo_100x150mm_1080p_6pages_portrait_w7_5mm_maximised_no_clip_border__",
    "__chromiq_knut_i1_photo_100x150mm_1200p_8pages_portrait_w7_5mm__",
    "__chromiq_knut_i1_photo_100x150mm_1260p_7pages_portrait_w7_5mm_maximised_no_clip_border__",
    "__chromiq_knut_i1_photo_100x150mm_1440p_8pages_portrait_w7_5mm_maximised_no_clip_border__",
    "__chromiq_knut_i1_photo_100x150mm_1500p_10pages_portrait_w7_5mm__",
    "__chromiq_knut_i1_photo_100x150mm_150p_1page_portrait_w7_5mm__",
    "__chromiq_knut_i1_photo_100x150mm_180p_1page_portrait_w7_5mm_maximised_no_clip_border__",
    "__chromiq_knut_i1_photo_100x150mm_600p_4pages_portrait_w7_5mm__",
    "__chromiq_knut_i1_photo_100x150mm_720p_4pages_portrait_w7_5mm_maximised_no_clip_border__",
    "__chromiq_knut_i1_photo_100x150mm_900p_6pages_portrait_w7_5mm__",
    "__chromiq_knut_i1_photo_130x180mm_1080p_5pages_portrait_w8_0mm__",
    "__chromiq_knut_i1_photo_130x180mm_1152p_4pages_portrait_w7_5mm_maximised_no_clip_border__",
    "__chromiq_knut_i1_photo_130x180mm_1296p_6pages_portrait_w8_0mm__",
    "__chromiq_knut_i1_photo_130x180mm_1440p_5pages_portrait_w7_5mm_maximised_no_clip_border__",
    "__chromiq_knut_i1_photo_130x180mm_1512p_7pages_portrait_w8_0mm__",
    "__chromiq_knut_i1_photo_130x180mm_216p_1page_portrait_w8_0mm__",
    "__chromiq_knut_i1_photo_130x180mm_288p_1page_portrait_w7_5mm_maximised_no_clip_border__",
    "__chromiq_knut_i1_photo_130x180mm_648p_3pages_w8_0mm__",
    "__chromiq_knut_i1_photo_130x180mm_864p_3pages_portrait_w7_5mm_maximised_no_clip_border__",
)


def _presets():
    from ui.tabs.tab_chart import KNUT_PRESETS
    return {p.key: p for p in KNUT_PRESETS if getattr(p, "layout_recipe", None)}


def _laid_out(p) -> dict:
    rec = LayoutRecipe.from_dict(dict(p.layout_recipe))
    g = geom_from_build_kwargs(rec.build_kwargs())
    w, h = papers.dimensions_mm(rec.paper)
    lay = geometry.compute(g, w, h, int(p.patches))
    out = {}
    for f in BETA44["fields"]:
        v = getattr(g, f) if hasattr(g, f) else getattr(lay, f)
        out[f] = round(v, 4) if isinstance(v, float) else v
    out["pages"] = lay.pages
    return out


def test_every_built_in_engine_preset_is_in_the_snapshot(qapp):
    assert set(_presets()) == (set(BETA44["presets"])
                               | set(BETA47_PHARMACIST["presets"])
                               | set(V431_PHARMACIST["presets"]))
    assert len(BETA44["presets"]) >= 170
    assert len(BETA47_PHARMACIST["presets"]) == 9
    assert len(V431_PHARMACIST["presets"]) == 5
    assert not set(BETA44["presets"]) & set(BETA47_PHARMACIST["presets"])
    assert not (set(BETA44["presets"]) | set(BETA47_PHARMACIST["presets"])) \
        & set(V431_PHARMACIST["presets"])


def test_the_pharmacist_charts_lay_out_as_in_beta_47(qapp):
    presets = _presets()
    wrong = sorted(k for k, want in BETA47_PHARMACIST["presets"].items()
                   if _laid_out(presets[k]) != want)
    assert not wrong, wrong[:5]


def test_the_431_pharmacist_charts_lay_out_as_in_4_3_1(qapp):
    presets = _presets()
    wrong = sorted(k for k, want in V431_PHARMACIST["presets"].items()
                   if _laid_out(presets[k]) != want)
    assert not wrong, wrong[:5]


def test_the_photo_card_snapshot_holds_exactly_the_named_presets():
    assert set(BETA45_PHOTO_CARDS["presets"]) == set(PHOTO_CARDS)


def test_every_other_built_in_preset_lays_out_as_in_beta_44(qapp):
    presets = _presets()
    moved = sorted(k for k, want in BETA44["presets"].items()
                   if k not in PHOTO_CARDS and _laid_out(presets[k]) != want)
    assert not moved, moved[:5]


def test_the_photo_cards_lay_out_as_in_beta_45(qapp):
    presets = _presets()
    wrong = sorted(k for k in PHOTO_CARDS
                   if _laid_out(presets[k]) != BETA45_PHOTO_CARDS["presets"][k])
    assert not wrong, wrong[:5]


def test_the_photo_cards_keep_their_patches_strips_and_pages(qapp):
    """What the ruling moves is 0.03 mm, never the count of anything."""
    for k in PHOTO_CARDS:
        old, new = BETA44["presets"][k], BETA45_PHOTO_CARDS["presets"][k]
        for f in ("patches_per_page", "strips_per_page", "pages", "pwid",
                  "rpstrip"):
            assert old[f] == new[f], (k, f)
        assert abs(old["plen"] - new["plen"]) <= 0.031, k
        assert abs(old["pspa"] - new["pspa"]) <= 0.031, k


def test_the_patch_scale_has_no_say_in_chart_area():
    r = LayoutRecipe(instrument="i1", paper="A4", layout_mode="area_first",
                     patch_w_mm=14.0, patch_h_mm=10.0, offset_x_mm=6.0,
                     offset_y_mm=6.0, pscale=0.75)
    kw = r.build_kwargs()
    assert (kw["patch_w"], kw["patch_h"], kw["offset_x"], kw["offset_y"]) \
        == (None, None, 0.0, 0.0)
    assert kw["pscale"] == 1.0


def test_the_patch_scale_still_applies_in_patch_size_mode():
    r = LayoutRecipe(instrument="i1", paper="A4", layout_mode="patch_first",
                     pscale=0.75)
    assert r.build_kwargs()["pscale"] == 0.75


def test_a_chart_marked_by_the_unreleased_beta_46_build_reads_like_beta_45():
    """10bdcf20 wrote the mark as 2 before it was taken out again; no release
    carries it, but a development project might. It is read like True."""
    d = LayoutRecipe(instrument="i1", paper="A4", layout_mode="area_first",
                     pscale=0.95).to_dict()
    d[HIDES_PATCH_CONTROLS_KEY] = 2
    assert build_kwargs_as_built(d)["pscale"] == 1.0


def test_the_patch_scale_row_is_shown_only_in_patch_size_mode(qapp):
    from ui.dialogs.layout_options_panel import LayoutOptionsPanel
    panel = LayoutOptionsPanel()
    try:
        panel.show()
        for mode in ("area_first", "patch_first", "area_first"):
            panel.layout_mode.setCurrentIndex(panel.layout_mode.findData(mode))
            qapp.processEvents()
            shown = any(w.isVisible() for w in panel._patch_scale_row)
            assert shown == (mode == "patch_first"), mode
    finally:
        panel.close()
        panel.deleteLater()
