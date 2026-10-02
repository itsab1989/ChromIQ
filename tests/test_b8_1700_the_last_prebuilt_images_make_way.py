"""B8-1700 (Knut, #182 5875467209, 4.3.1): five more "by Pharmacist" charts with
a page layout, quality checked by Knut, and the last four prebuilt page images
withdrawn.

* Added, each a "Full layout setup", imported with
  ``scripts/import_pharmacist_presets.py`` exactly as the nine of beta 47:
  ColorMunki A3+ 924, ColorMunki A4 624 (2 pages), ColorMunki A3 725,
  i1Pro 4x6" 600 (4 pages), i1Pro 5x7" 702 (3 pages).
* Removed: i1Pro 10x15cm 600, i1Pro 13x18cm 648, ColorMunki A3 924 TC9.24,
  ColorMunki A4 702 ABW-optimized. No prebuilt-files preset ships any more.
* A stored key of a removed one breaks nothing: it selects no preset, a stored
  tick for it is kept and ignored, and a project made from one keeps its own
  files.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from core import curated_presets as CP
from core.resource_path import resource_path
from data.patch_db import PAPER_LABELS, paper_name_token
from ui.tabs import tab_chart as TC

ROOT = Path(__file__).resolve().parents[1]

#: slug -> (instrument, printtarg paper, paper token in the name, patches,
#:          pages, the sender's .ti1 sha256)
ADDED = {
    "pharm_cm_a3plus_924p_1page_landscape_w14_0mm_ergonomical":
        ("CM", "483x329", "A3Plus", 924, 1,
         "8b0ba5907bdd7200f7e782dd7b0a223f41b3ad4fe2a63b339164f44da3217bd5"),
    "pharm_cm_a4_624p_2pages_portrait_w14_0mm_ergonomical":
        ("CM", "A4", "A4", 624, 2,
         "1555453d0bc87c942b5f186ec5055ddc41ca87d4a94c372c39df3c3395d266b1"),
    "pharm_cm_a3_725p_1page_landscape_w14_0mm_ergonomical":
        ("CM", "420x297", "A3", 725, 1,
         "f84ead8981ea137b91dabf3e01a2cbfdbeef0575f34eef1bb7bca1a3a14f9abd"),
    "pharm_i1_4x6in_600p_4pages_w7_5mm_real_world":
        ("i1", "4x6", "4x6in", 600, 4,
         "4eb9e3b20cad5b13461f39febcc500b0172b5fdb9d0e782ba1e71c52b855bc2a"),
    "pharm_i1_5x7in_702p_3pages_w8_0mm_real_world":
        ("i1", "127x178", "5x7in", 702, 3,
         "accb5402975670da2d97e652831fe48c9345640f81072254b824f3975e12df07"),
}

#: The four removed, by the key each shipped under, with the full label.
REMOVED = {
    "__chromiq_photocard600_builtin__":
        "★  i1Pro · 10x15cm-600p-4pages by Pharmacist  ·  built-in",
    "__chromiq_photocard648_builtin__":
        "★  i1Pro · 13x18cm-648p-3pages by Pharmacist  ·  built-in",
    "__chromiq_tc924_cm_a3_builtin__":
        "★  ColorMunki · A3-924p-1page TC9.24 by Pharmacist  ·  built-in",
    "__chromiq_abw702_builtin__":
        "★  ColorMunki · A4-702p-2pages ABW-optimized by Pharmacist  ·  built-in",
}


def _p(slug):
    return TC.KNUT_PRESETS_BY_KEY[f"__chromiq_knut_{slug}__"]


def _sets(ti1: Path) -> int:
    for line in ti1.read_text(encoding="utf-8").splitlines():
        if line.startswith("NUMBER_OF_SETS"):
            return int(line.split()[1])
    raise AssertionError(ti1)


# --- the five added ------------------------------------------------------------

@pytest.mark.parametrize("slug", ADDED)
def test_the_five_are_built_ins_with_their_patches_pages_and_paper(slug):
    instr, paper, token, patches, pages, _sha = ADDED[slug]
    p = _p(slug)
    assert p.key in TC.BUILTIN_PRESET_KEYS
    assert (p.instrument, p.paper, p.patches, p.pages) == (instr, paper,
                                                            patches, pages)
    assert _sets(resource_path(p.ti1_asset)) == patches
    # the paper is one ChromIQ has, and the name spells it as ChromIQ does
    assert paper in PAPER_LABELS
    assert paper_name_token(paper) == token
    assert p.name.startswith(f"{token}-{patches}p-{pages}page")
    assert p.name.endswith("by Pharmacist")
    assert p.layout_recipe["instrument"] == instr
    assert p.layout_recipe["paper"] == paper
    # the chart lays out on as many sheets as its name says
    from tests.test_b8_1590_the_patch_scale_belongs_to_chart_area_too import (
        _laid_out)
    assert _laid_out(p)["pages"] == pages


@pytest.mark.parametrize("slug", ADDED)
def test_each_is_a_full_layout_setup_whose_design_names_its_chart(slug):
    instr, paper, _t, patches, _pg, _sha = ADDED[slug]
    p = _p(slug)
    assert p.has_full_layout_setup
    assert p.combo_label.endswith(" · Full layout setup  ·  built-in")
    rec = json.loads((resource_path(p.ti1_asset).parent / "recipe.json")
                     .read_text(encoding="utf-8"))
    assert (rec["instr"], rec["paper"]) == (instr, paper)
    assert rec["sp"]["fill_to"] == patches


@pytest.mark.parametrize("slug", ADDED)
def test_each_is_imported_the_way_the_nine_of_beta_47_were(slug):
    p = _p(slug)
    assert p.layout_recipe.get("clip_image_path") == ""
    assert "seed_fixed" not in p.layout_recipe
    assert p.stamp_settings is False
    assert p.file_group == ("ColorMunki" if ADDED[slug][0] == "CM" else "i1Pro")


@pytest.mark.parametrize("slug", ADDED)
def test_the_patch_set_is_the_senders_byte_for_byte(slug):
    data = resource_path(_p(slug).ti1_asset).read_bytes()
    assert hashlib.sha256(data).hexdigest() == ADDED[slug][5]


def test_all_five_are_shown_by_default():
    """Ticked, as every "by Pharmacist" chart with a layout is but the
    "(ChromIQ Editor)" TC3.00 equivalent (B8-1620)."""
    for slug in ADDED:
        assert CP.is_shown_by_default(_p(slug).key), slug


# --- the four removed ----------------------------------------------------------

def test_the_four_prebuilt_images_are_gone_and_no_other_is_left():
    assert TC.PREBUILT_PRESETS == {}
    assert not set(REMOVED) & TC.BUILTIN_PRESET_KEYS
    assert not set(REMOVED.values()) & TC.BUILTIN_PRESET_LABELS
    rows = {k for _h, es in TC.BUILTIN_PRESET_GROUPS for (_c, _o, k) in es}
    assert not set(REMOVED) & rows
    for leaf in ("colormunki/a4/abw702", "colormunki/a3/tc924",
                 "i1pro/100x150/photocard600", "i1pro/130x180/photocard648"):
        # A FOLDER FINDER LEFT A .DS_Store IN IS NOT A SHIPPED CHART: git
        # ignores it, a clean checkout (CI, the build) has no such folder, and
        # a developer's machine keeps the folder after the move. Real files
        # are what must be gone.
        d = ROOT / "assets/charts/pharmacist/rgb" / leaf
        left = [f for f in d.rglob("*") if f.is_file() and f.name != ".DS_Store"] if d.exists() else []
        assert not left, (leaf, left)


def test_the_count_is_189():
    # 188 in 4.3.1; +1 with Knut's three i1Pro presets, #182 5943544919 (4.3.3-beta.1): the 7.5 mm "Full Page" chart.
    assert len(TC.BUILTIN_PRESET_KEYS) == 189


def test_a_stored_tick_for_a_removed_preset_is_harmless():
    """The person's own choices name keys; one that no longer exists is kept
    and ignored, and does not shift anything else."""
    class _S(dict):
        def get(self, k, d=None):
            return super().get(k, d)

    stored = {k: True for k in REMOVED}
    s = _S({CP.SETTING_KEY: json.dumps(stored)})
    shown = CP.shown_keys(s, TC.BUILTIN_PRESET_KEYS)
    assert not set(REMOVED) & shown
    assert shown == CP.shown_keys(_S(), TC.BUILTIN_PRESET_KEYS)
    # and storing the window's boxes again keeps the unknown answers
    out = CP.choices_to_store(shown, TC.BUILTIN_PRESET_KEYS, stored)
    assert {k: out[k] for k in REMOVED} == stored


def test_a_stored_selection_of_a_removed_preset_selects_nothing(qapp, tmp_path):
    from PyQt6.QtCore import QSettings
    from core.argyll_runner import ArgyllRunner
    from core.file_manager import FileManager
    from core.settings import AppSettings
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    s.set("custom_output_path", str(tmp_path / "projects"))
    tab = TC.TabChart(ArgyllRunner(s), FileManager(s), s)
    try:
        for key in REMOVED:
            assert tab._preset_combo.findData(key) == -1
    finally:
        tab.deleteLater()


def test_a_project_built_from_a_removed_preset_still_opens(tmp_path):
    """A prebuilt preset copied its files into the run; nothing in the run
    points back at the bundle, so the project loads with its chart."""
    import shutil
    from core.file_manager import Project
    from tests._prebuilt_fixture import ABW702_KEY, PREBUILT
    proj = Project.create(tmp_path / "Old-702", "Old-702")
    run = proj.current_run()
    run.ensure_dir()
    stem = ROOT / PREBUILT[ABW702_KEY][0]
    for ext in (".ti1", ".ti2"):
        shutil.copy2(stem.with_suffix(ext), run.dir / f"Old-702{ext}")
    for i, tif in enumerate(sorted(stem.parent.glob(f"{stem.name}_*.tif")), 1):
        shutil.copy2(tif, run.dir / f"Old-702_{i:02d}.tif")
    again = Project.load(tmp_path / "Old-702")
    r = again.current_run()
    assert r.chart_ti2.is_file()
    assert _sets(r.chart_ti2.with_suffix(".ti1")) == 702
