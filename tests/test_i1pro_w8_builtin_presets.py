"""Knut's 8 mm i1Pro built-in presets (#164, 2026-08-23).

Seven charts on A4 for the original i1Pro, from a single 156-patch sheet up to
2,860 patches on five, all laid out by the ChromIQ layout engine on one 22 × 26
grid. His own description: *"They are all 8.0mm wide patches. So a tiny bit
larger than some of the others, 572 patches per sheet as basis."*

Built like the i1Pro 3 Plus family next door and guarded the same way: one
shared base recipe, a chart owning only its sheet and its grid, and every chart
actually built and counted — because editing ``_I1_BASE`` changes all seven at
once and silently.

They arrived in the same message that withdrew the A4 495p landscape chart and
the parked "TC9.24 by Pharmacist", so the counts here move together with the
ones in ``test_knut_spyderprint_presets.py``.
"""
from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PyQt6")

from core.resource_path import resource_path  # noqa: E402
from ui.tabs.tab_chart import (  # noqa: E402
    _I1_BASE, BUILTIN_PRESET_GROUPS, BUILTIN_PRESET_KEYS,
    BUILTIN_PRESET_LABELS, KNUT_PRESETS,
)

W8 = [p for p in KNUT_PRESETS if p.slug.startswith("i1_w8_")]

#: Exactly the fields one chart of this family may set for itself.
OWN_FIELDS = {"paper", "area_cols", "area_rows"}

_NAME_RE = re.compile(
    r"^(?P<sheet>A4)-(?P<patches>\d+)p-(?P<pages>\d+)pages?-"
    r"(?P<orientation>Portrait|Landscape)-w(?P<width>[\d.]+)mm$")


# ---------------------------------------------------------------------------
# Registered, and filed with the other i1Pro charts
# ---------------------------------------------------------------------------

def test_seven_charts_registered():
    assert len(W8) == 7
    assert len({p.slug for p in W8}) == 7            # slugs are the identity
    assert len({p.name for p in W8}) == 7
    assert all(p.key in BUILTIN_PRESET_KEYS for p in W8)
    assert all(p.combo_label in BUILTIN_PRESET_LABELS for p in W8)
    grouped = {k for _i, entries in BUILTIN_PRESET_GROUPS for (_c, _o, k) in entries}
    assert all(p.key in grouped for p in W8), "a chart no dropdown group reaches"


def test_they_are_i1pro_charts_not_a_family_of_their_own():
    """Cut for the original i1Pro, so they belong under the heading an i1Pro
    owner already reads — unlike the i1Pro 3 Plus charts, whose layout is for a
    different body and which therefore have their own group."""
    assert all(p.instrument == "i1" for p in W8)
    assert all(p.file_group == "i1Pro" for p in W8)
    assert all(p.group == "" for p in W8)


def test_the_target_name_is_the_name_he_gave_it():
    """`suffix=""` — these are not the "Full layout setup" family, and the
    default target name must come out as his own file name, unchanged."""
    p = next(q for q in W8 if q.patches == 572)
    assert p.suffix == ""
    assert p.default_target_name == "i1Pro-A4-572p-1page-Portrait-w8.0mm"


def test_the_i1pro_group_reads_in_order():
    """Ascending by patch count, like the ColorMunki and i1Pro 3 Plus groups.
    The heading mixes these seven with the older Full-layout-setup charts, and a
    dropdown that jumps 1200 → 156 → 484 is a dropdown nobody can scan."""
    i1 = [p for p in KNUT_PRESETS if p.file_group == "i1Pro"]
    counts = [int(re.search(r"A4-(\d+)p", p.name).group(1)) for p in i1]
    assert counts == sorted(counts), f"the i1Pro group is out of order: {counts}"


# ---------------------------------------------------------------------------
# One shared recipe
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("preset", W8, ids=lambda p: p.slug)
def test_recipe_differs_from_the_base_only_where_allowed(preset):
    rec = preset.layout_recipe
    assert rec is not None, "the family is engine-built, not printtarg"
    assert set(rec) == set(_I1_BASE) | OWN_FIELDS
    for field in set(_I1_BASE) - OWN_FIELDS:
        assert rec[field] == _I1_BASE[field], (
            f"{preset.slug} changes {field}, which the whole family shares")


def test_every_chart_shares_one_grid():
    """The 22 × 26 grid is what makes them one family — 572 patches a sheet, and
    a bigger chart is more sheets rather than a different layout."""
    assert {(p.layout_recipe["area_cols"], p.layout_recipe["area_rows"])
            for p in W8} == {(22, 26)}
    assert {p.layout_recipe["paper"] for p in W8} == {"A4"}


def test_the_measured_shape_of_the_family():
    """The numbers Knut laid these out with, written down rather than left
    implicit in seven rows."""
    r = _I1_BASE
    assert r["instrument"] == "i1"
    # The i1Pro jig margins: a 38 mm run-in at the top for the strip label and
    # the instrument body, and the 19 mm bottom that keeps a full-height A4
    # strip inside the ruler's own 240 mm limit (see core/settings.py).
    assert r["margin_top"] == 38.0
    assert r["margin_bottom"] == 19.0
    assert r["margin_left"] == 26.0
    assert r["use_instrument_margins"] is False
    # The clip band: 26 mm down the LEFT, upright, carrying the notes box.
    assert r["clip_border"] is True
    assert r["clip_border_width_mm"] == 26.0
    assert r["clip_side"] == "left"
    assert r["clip_content_mode"] == "notes"
    assert r["layout_mode"] == "area_first" and r["area_method"] == "by_grid"
    assert r["randomize"] is True and r["seed"] is None
    assert r["dpi"] == 200 and r["bit16"] is False


def test_the_right_margin_is_narrower_than_the_apps_own_seed():
    """KNOWN, AND HIS TO DECIDE — not a mistake to be quietly corrected.

    ChromIQ's own i1Pro seed asks for 9 mm on the right; these charts were
    authored with 6. The charts are Knut's, so his number ships unchanged, but
    ChromIQ's Measured-from-Preview panel judges every sheet against the seed
    and will flag the right edge on all seven until he says which of the two
    should move. This test exists so that the difference is deliberate and
    visible rather than a surprise to the next reader.
    """
    from core.settings import default_margin_thresholds

    seed = default_margin_thresholds()["i1Pro|A4 Portrait"]
    assert _I1_BASE["margin_right"] == 6.0
    assert seed["R"] == 9
    # …while the three he did match are matched exactly.
    assert (_I1_BASE["margin_top"], _I1_BASE["margin_bottom"],
            _I1_BASE["margin_left"]) == (seed["T"], seed["B"], seed["L"])


# ---------------------------------------------------------------------------
# Names tell the truth about the bundled files
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("preset", W8, ids=lambda p: p.slug)
def test_name_matches_the_bundled_patch_set_and_the_grid(preset):
    m = _NAME_RE.match(preset.name)
    assert m, f"name does not follow the convention: {preset.name}"
    assert int(m.group("patches")) == preset.patches
    assert int(m.group("pages")) == preset.pages
    assert m.group("sheet") == preset.layout_recipe["paper"]

    ti1 = resource_path(preset.ti1_asset)
    assert ti1.is_file(), f"missing {preset.ti1_asset}"
    txt = ti1.read_text(encoding="latin-1", errors="ignore")
    assert int(re.search(r"NUMBER_OF_SETS\s+(\d+)", txt).group(1)) == preset.patches
    assert txt.count("NUMBER_OF_SETS") == 3      # printtarg needs all three tables

    per_page = preset.layout_recipe["area_cols"] * preset.layout_recipe["area_rows"]
    assert -(-preset.patches // per_page) == preset.pages, (
        f"22×26 per sheet does not put {preset.patches} patches on "
        f"{preset.pages} page(s)")


@pytest.mark.parametrize("preset", W8, ids=lambda p: p.slug)
def test_sidecar_recipe_matches_its_chart(preset):
    """"Load setup from preset" seeds the New-chart window from this file.

    Knut designs a colour set once and lays it out on several sheets, so his
    exports carry whatever instrument and paper happened to be on screen at
    design time — three of these seven arrived pointing at a ColorMunki, one of
    them on A3. The importer re-points them; this pins the result, because a
    sidecar nobody checks would seed the wrong device for the right chart.
    """
    sidecar = resource_path(preset.ti1_asset).parent / "recipe.json"
    assert sidecar.is_file(), f"missing {sidecar}"
    rec = json.loads(sidecar.read_text())
    assert rec["instr"] == "i1"
    assert rec["paper"] == preset.layout_recipe["paper"]
    assert rec["sp"]["fill_to"] == preset.patches


# ---------------------------------------------------------------------------
# It builds — every chart, on the real engine
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("preset", W8, ids=lambda p: p.slug)
def test_chart_builds_with_the_pages_and_patches_its_name_promises(preset):
    from workflow.layout_engine.chart import build_from_recipe
    from workflow.layout_engine.presets import LayoutRecipe

    rec = LayoutRecipe.from_dict(preset.layout_recipe)
    with tempfile.TemporaryDirectory() as td:
        res, _ = build_from_recipe(resource_path(preset.ti1_asset),
                                   Path(td) / "chart", rec)
        tiffs = sorted(Path(td).glob("chart*.tif"))
        assert len(tiffs) == preset.pages
        # Nothing is padded out with white: the grid holds the patch set exactly.
        assert res.layout.total_patches == preset.patches
        # The patch width the name advertises, as it lands on paper (±0.5 mm).
        said = float(re.search(r"-w([\d.]+)mm", preset.name).group(1))
        got = res.strip_rects[0]["w"] * 25.4 / rec.dpi
        assert abs(got - said) <= 0.5, (
            f"name says {said} mm patches, the sheet has {got:.2f} mm")
