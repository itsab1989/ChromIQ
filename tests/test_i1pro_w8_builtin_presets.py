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
#:
#: The two margins are here because the PAPER forces them, and Knut confirmed
#: both (#164): US Letter is 18 mm shorter than A4, so it does not need A4's
#: 19 mm bottom to keep a strip inside the i1Pro ruler's 240 mm travel, and its
#: right margin is 9 mm — ChromIQ's own i1Pro seed — against A4's 6.
OWN_FIELDS = {"paper", "area_cols", "area_rows", "margin_right", "margin_bottom"}

_NAME_RE = re.compile(
    r"^(?P<sheet>A4|Letter|A3)-(?P<patches>\d+)p-(?P<pages>\d+)pages?-"
    r"(?P<orientation>Portrait|Landscape)-w(?P<width>[\d.]+)mm$")

#: The recipe's `paper` for each sheet the names use. A3 landscape is a custom
#: size in the engine's terms, not the "A3" enum.
PAPER_OF_SHEET = {"A4": "A4", "Letter": "Letter", "A3": "420x297"}


# ---------------------------------------------------------------------------
# Registered, and filed with the other i1Pro charts
# ---------------------------------------------------------------------------

def test_all_nineteen_charts_registered():
    assert len(W8) == 19
    assert len({p.slug for p in W8}) == 19           # slugs are the identity
    assert len({p.name for p in W8}) == 19
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


def test_each_paper_reads_in_order():
    """Ascending by patch count WITHIN each sheet size, not across all three.

    One ascending run over three papers reads A4-156, Letter-156, A4-312,
    Letter-312 … and cannot be scanned for the sheet you actually have. A user
    picks the paper in their printer first, so the papers stay in blocks and
    the counts climb inside each.
    """
    for sheet in ("A4", "Letter", "A3"):
        counts = [p.patches for p in W8
                  if _NAME_RE.match(p.name).group("sheet") == sheet]
        assert counts == sorted(counts), f"{sheet} is out of order: {counts}"
        assert len(set(counts)) == len(counts), f"{sheet} repeats a patch count"


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


def test_the_grid_follows_the_sheet():
    """One grid per sheet width, and a bigger chart is more sheets rather than
    a different layout. A4 and Letter are the same 22 columns; A3 landscape is
    twice as wide, so it takes 44."""
    for p in W8:
        sheet = _NAME_RE.match(p.name).group("sheet")
        cols = 44 if sheet == "A3" else 22
        assert (p.layout_recipe["area_cols"], p.layout_recipe["area_rows"]) \
            == (cols, 26), f"{p.slug} does not use the {cols} × 26 grid"
        assert p.layout_recipe["paper"] == PAPER_OF_SHEET[sheet], (
            f"{p.slug} is laid out on {p.layout_recipe['paper']}, "
            f"not the {sheet} its name promises")


def test_the_measured_shape_of_the_family():
    """The numbers Knut laid these out with, written down rather than left
    implicit in seven rows."""
    r = _I1_BASE
    assert r["instrument"] == "i1"
    # The i1Pro jig margins: a 38 mm run-in at the top for the strip label and
    # the instrument body, and the 19 mm bottom that keeps a full-height A4
    # strip inside the ruler's own 240 mm limit (see core/settings.py).
    assert r["margin_top"] == 38.0
    assert r["margin_bottom"] == 19.0        # A4; Letter carries its own 15.0
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


def test_letter_uses_the_margins_its_shorter_sheet_needs():
    """Knut, #164: *"It is correct that the right margin for the i1Pro is 6mm,
    it is intentional. It is intentional that the letter variants are 9mm."*

    A4 is 297 mm: 38 at the top and 19 at the bottom leave exactly the 240 mm
    the ruler can travel. Letter is 279.4 mm, so the same top margin and 15 at
    the bottom leave 226 — inside the limit, and 19 would only waste paper.
    """
    for p in W8:
        sheet = _NAME_RE.match(p.name).group("sheet")
        want = (9.0, 15.0) if sheet == "Letter" else (6.0, 19.0)
        got = (p.layout_recipe["margin_right"], p.layout_recipe["margin_bottom"])
        assert got == want, f"{p.slug} has margins {got}, expected {want}"
        top = p.layout_recipe["margin_top"]
        height = 279.4 if sheet == "Letter" else 297.0
        if sheet != "A3":
            assert height - top - got[1] <= 240.0, (
                f"{p.slug} leaves {height - top - got[1]:.1f} mm of strip, "
                "past the i1Pro ruler's 240 mm travel")


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
    assert PAPER_OF_SHEET[m.group("sheet")] == preset.layout_recipe["paper"]

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
    rec = json.loads(sidecar.read_text(encoding="utf-8"))
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


# ---------------------------------------------------------------------------
# THE RULER MARKS ARE ON (#164, Knut)
# ---------------------------------------------------------------------------
# On the A4-2288p chart: *"the markers should be active so this is a bug. It
# was not intended."* All nineteen of his 8 mm exports ask for markers on and
# five to a patch; `_I1_BASE` said off and three. Because `_i1_preset` builds
# every chart in the family from the base, ALL SEVEN shipped charts lost the
# marks whatever their own export said — so it is a base fact, not a per-chart
# one, and this test guards it there.


@pytest.mark.slow
@pytest.mark.parametrize("slug", ["i1_w8_a4_156p_1page_portrait_w8_0mm",
                                  "i1_w8_letter_156p_1page_portrait_w8_0mm"])
def test_the_ruler_marks_reach_the_paper(slug, tmp_path):
    """Ink, not a dictionary entry.

    The test below asserts the recipe asks for marks. It cannot tell whether a
    dash ever lands on a sheet — and the fault it guards was precisely that the
    per-chart value never reached the built chart. So this one builds a real
    chart and looks for ink in the band along the edge, where only the comb can
    be. Modelled on the ColorMunki family's own test, but sampling TOP and
    BOTTOM: this family sets `helper_markers_sides` False, so the side edges
    are legitimately bare.
    """
    import numpy as np
    from PIL import Image

    from workflow.layout_engine.chart import build_from_recipe
    from workflow.layout_engine.presets import LayoutRecipe

    preset = next(p for p in W8 if p.slug == slug)
    rec = LayoutRecipe.from_dict(preset.layout_recipe)
    res, _ = build_from_recipe(resource_path(preset.ti1_asset),
                               tmp_path / "chart", rec)
    dpi = preset.layout_recipe["dpi"]
    page = np.asarray(Image.open(res.tiff_paths[0]).convert("L"))
    # SAMPLE ONLY WHERE A DASH CAN BE, AND NOTHING ELSE CAN.
    # The comb sits `edge_mm` from the paper edge and runs `len_mm` inwards, so
    # it lives entirely within the first (edge + len) mm. A wider band reaches
    # the strip labels: with the marks OFF the nearest ink is 6.22 mm from the
    # top, so a band of 7 mm found ink either way and the test passed against
    # its own mutation. Measured, not guessed.
    # Measured at 200 dpi on the 156p chart: with the marks ON the first inked
    # row is 3.94 mm from the top; with them OFF it is 6.10 mm. The comb's own
    # extent is edge + len = 6.0 mm, which leaves only 0.1 mm of headroom, so
    # the band is pulled in half a millimetre.
    band = int(round((preset.layout_recipe["helper_marker_edge_mm"]
                      + preset.layout_recipe["helper_marker_len_mm"] - 0.5)
                     / 25.4 * dpi))
    assert (page[:band, :] < 128).any(), f"{slug}: no ruler marks along the top"
    assert (page[-band:, :] < 128).any(), f"{slug}: no ruler marks along the bottom"


def test_every_chart_in_the_family_prints_its_ruler_marks():
    assert _I1_BASE["helper_markers"] is True, (
        "the 8 mm i1Pro charts print without ruler marks")
    assert _I1_BASE["helper_marker_per_patch"] == 5, (
        f"{_I1_BASE['helper_marker_per_patch']} marks per patch, not the 5 "
        "Knut's exports ask for")
    for preset in W8:
        rec = preset.layout_recipe
        assert rec["helper_markers"] is True, f"{preset.slug} has no marks"
        assert rec["helper_marker_per_patch"] == 5, f"{preset.slug} marks differ"


@pytest.mark.parametrize("preset", W8, ids=lambda p: p.slug)
def test_the_recipe_matches_the_export_field_for_field(preset):
    """Every field of the shipped layout, against Knut's own export.

    Stronger than picking two fields by hand — which is what the marker test
    below does, and it would miss any of the other sixty-odd. The exports are
    the source of truth for this family; if a field drifts from them, the chart
    ChromIQ builds is not the chart he designed.
    """
    from ui.tabs.tab_chart import _I1_BASE

    rec = preset.layout_recipe
    # The three fields a chart of this family owns, plus the two margins the
    # paper forces, may differ from the base; nothing else may.
    for key, value in _I1_BASE.items():
        if key in OWN_FIELDS:
            continue
        assert rec[key] == value, (
            f"{preset.slug}.{key} is {rec[key]!r}, the family base says "
            f"{value!r}")


def test_the_2288_chart_can_be_rebuilt_from_its_own_recipe(qapp):
    """Its sidecar used to describe a DIFFERENT design — `cube_n` 9 against a
    chart built with 11 — so "Load setup from preset" offered a setup that
    regenerated other colours. Knut re-exported it; this pins the pairing.

    Checked cheaply: the recipe's own patch count must match the chart's. The
    full colour-for-colour regeneration lives in the import checker, which is
    too slow for the gate.
    """
    import json

    preset = next(p for p in W8 if p.patches == 2288)
    sidecar = resource_path(preset.ti1_asset).parent / "recipe.json"
    rec = json.loads(sidecar.read_text(encoding="utf-8"))
    assert rec["sp"]["fill_to"] == preset.patches, (
        f"the recipe rebuilds {rec['sp']['fill_to']} patches, the chart has "
        f"{preset.patches}")
    assert rec.get("cb", {}).get("fill") is False, (
        "the design relies on gap-filling, so its patch count is not its own")
    # THE FAULT WAS THE CUBE, NOT THE COUNT. `fill_to` was ALREADY 2288 before
    # the fix — the importer had re-pointed it — so a test resting on it was
    # green throughout the bug. What was wrong was the colour cube: 9 levels
    # recorded against a chart built with 12, which regenerated 2287 different
    # patches out of 2288.
    assert rec["sp"]["cube_n"] == 12, (
        f"the recipe builds a {rec['sp']['cube_n']}-level colour cube; this "
        "chart was built with 12, so the design cannot reproduce it")
