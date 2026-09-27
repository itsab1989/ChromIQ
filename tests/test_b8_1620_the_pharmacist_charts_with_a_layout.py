"""B8-1620 (Knut, #182 5860041950): the "by Pharmacist" built-ins with a page
layout replace seven that were only page images.

* Seven prebuilt page images are withdrawn; four stay (the i1Pro 10x15cm 600,
  the i1Pro 13x18cm 648, the ColorMunki A3 924 and the ColorMunki A4 702).
* Nine new charts arrive with their page layout. Every one is a "Full layout
  setup" except the ColorMunki A4 300-patch TC3.00 Target, which is marked
  "Layout, but no editor setup".
* All but the "(ChromIQ Editor)" TC3.00 Equivalent are shown by default.
* Each builds exactly the sender's patch set.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from core.curated_presets import is_shown_by_default
from core.resource_path import resource_path
from ui.tabs import tab_chart as TC

ROOT = Path(__file__).resolve().parents[1]

KEPT = {
    "__chromiq_photocard600_builtin__", "__chromiq_photocard648_builtin__",
    "__chromiq_tc924_cm_a3_builtin__", "__chromiq_abw702_builtin__",
}
WITHDRAWN = {
    "__chromiq_abw1110_builtin__", "__chromiq_tc918eg_a4_builtin__",
    "__chromiq_tc918eg_letter_builtin__", "__chromiq_tc300_builtin__",
    "__chromiq_tc918eg_cm_a3_builtin__", "__chromiq_ext1944_a4_builtin__",
    "__chromiq_ext1944_letter_builtin__",
}
LAYOUT_ONLY = "__chromiq_knut_pharm_cm_a4r_300p_1page_landscape_w9_0mm_tc300__"
EDITOR_EQUIVALENT = \
    "__chromiq_knut_pharm_cm_a4r_300p_1page_landscape_w9_0mm_tc300_editor__"


def _new():
    return [p for p in TC.KNUT_PRESETS if p.slug.startswith("pharm_")]


def test_seven_prebuilt_images_are_withdrawn_and_four_stay():
    assert set(TC.PREBUILT_PRESETS) == KEPT
    assert not WITHDRAWN & TC.BUILTIN_PRESET_KEYS
    for leaf in ("i1pro/a4/abw1110", "i1pro/a4/tc918eg", "i1pro/letter/tc918eg",
                 "colormunki/a4/tc300", "colormunki/a3plus/tc918eg",
                 "i1pro/a4/extended1944", "i1pro/letter/extended1944"):
        assert not (ROOT / "assets/charts/pharmacist/rgb" / leaf).exists(), leaf


def test_nine_new_charts_each_with_its_page_layout():
    new = _new()
    assert len(new) == 9
    for p in new:
        assert p.layout_recipe, p.slug
        assert "by Pharmacist" in p.name or "(ChromIQ Editor)" in p.name, p.name
        assert p.layout_recipe.get("clip_image_path") == "", p.slug
        assert "seed_fixed" not in p.layout_recipe, p.slug
        # every export has the settings stamp off, and its layout has no room
        assert p.stamp_settings is False, p.slug


def test_the_markers_are_the_ones_knut_named():
    for p in _new():
        if p.key == LAYOUT_ONLY:
            assert p.combo_label.endswith(
                " · Layout, but no editor setup  ·  built-in"), p.combo_label
            assert not p.has_full_layout_setup
        else:
            assert p.combo_label.endswith(" · Full layout setup  ·  built-in"), \
                p.combo_label
            assert p.has_full_layout_setup, p.slug


def test_all_but_the_editor_equivalent_are_shown_by_default():
    for p in _new():
        assert is_shown_by_default(p.key) is (p.key != EDITOR_EQUIVALENT), p.slug


@pytest.mark.parametrize("p", _new(), ids=lambda p: p.slug)
def test_the_patch_set_is_the_senders_byte_for_byte(p):
    """Each bundled .ti1 is the file the sender attached, byte for byte; its
    fingerprint is pinned here so a re-import that altered a patch fails."""
    data = resource_path(p.ti1_asset).read_bytes()
    assert hashlib.sha256(data).hexdigest() == SHA256[p.slug]


SHA256 = {
    # the .ti1 files Knut attached to #182 5860041950
    "pharm_cm_a4r_300p_1page_landscape_w9_0mm_tc300_editor":
        "0535e7e6b14330f3bb8b699b1c7d76092c17e038979b4044a111b9e8b0447db1",
    "pharm_cm_a4r_300p_1page_landscape_w9_0mm_tc300":
        "b2ec627a7802608962717f576794225bc554eca5ae8997eedd343beab96a1c7d",
    "pharm_cm_a4r_600p_2pages_landscape_w9_0mm_abw":
        "e09015681b7b03ed0e949a781c2fc24442f5333270ec437cdc00ade7905b3125",
    "pharm_i1_a4_648p_1page_portrait_w7_5mm_real_world":
        "061e22de1403435d83475d1d9bc904a6fa568745708f90f05238911c1267913b",
    "pharm_i1_a4_1296p_2pages_portrait_w7_5mm_real_world":
        "1825cb3a991adeb08d6234c600fe83619391653504764542678eec135e134add",
    "pharm_i1_a4_1944p_3pages_portrait_w7_5mm_real_world":
        "9fd47558857489ca72fa350f2f354f1e52bb29b009d26abfa74920825ee8ea98",
    "pharm_i1_letter_648p_1page_portrait_w7_5mm_real_world":
        "35ce2bcd503921cc376393068ce246806efbd154c25b314e13cd228169d359a8",
    "pharm_i1_letter_1296p_2pages_portrait_w7_5mm_real_world":
        "798d728e26819cb05a0e281e8ddd571480f9b86dd48d5b90e46bf4833976f5c3",
    "pharm_i1_letter_1944p_3pages_portrait_w7_5mm_real_world":
        "d067e1057ca6d4ea396c049420314d88d070d0aaf0d7947b381f43525f67532a",
}
