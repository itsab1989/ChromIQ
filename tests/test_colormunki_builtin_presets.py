"""Knut's ColorMunki built-in presets (2026-08-16).

The whole ColorMunki line-up, re-made from scratch and measured on paper so a
ruler can be laid across the sheet, both the first and the last strip stay
readable, and the knobs under the instrument can't catch on the page edge. Every
chart is engine-built with the helper markers on, and the family shares ONE
layout recipe — each chart sets only its paper, its columns × rows grid and (for
the three big-patch "Hand Held" charts) a narrower left margin plus a matching
clip-border note.

That sharing is what these tests guard. If someone edits ``_CM_BASE``, every one
of the 45 charts changes at once, silently — so the base is checked against the
five fields a chart is allowed to own, the names are checked against the grids
they claim, and a representative sample is actually built and counted.
"""
from __future__ import annotations

import json
import os
import re

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PyQt6")

from core.resource_path import resource_path  # noqa: E402
from data.patch_db import INSTRUMENT_LABELS  # noqa: E402
from ui.tabs.tab_chart import (  # noqa: E402
    _CM_BASE, _CM_CLIP_TEXT, _CM_CLIP_TEXT_HAND_HELD,
    BUILTIN_PRESET_GROUPS, BUILTIN_PRESET_KEYS, BUILTIN_PRESET_LABELS,
    KNUT_PRESETS, TabChart,
)

CM = [p for p in KNUT_PRESETS if p.slug.startswith("cm_")]

# Exactly the fields a single chart in the family may set for itself.
OWN_FIELDS = {"paper", "area_cols", "area_rows", "margin_left", "clip_text"}

_NAME_RE = re.compile(
    r"^(?P<sheet>A4|A3Plus|A3|Letter)-(?P<patches>\d+)p-(?P<pages>\d+)pages?-"
    r"(?P<orientation>Portrait|Landscape)-w(?P<width>[\d.]+)mm-(?P<rest>.+)$")


# ---------------------------------------------------------------------------
# The family is registered, and it is the only ColorMunki family Knut ships
# ---------------------------------------------------------------------------

def test_forty_five_charts_registered():
    assert len(CM) == 45
    assert len({p.slug for p in CM}) == 45           # slugs are the identity
    assert len({p.name for p in CM}) == 45
    # The heading follows the Instrument selection field (Knut, 2026-08-18);
    # the short token that names files and folders does not.
    assert all(p.file_group == "ColorMunki" for p in CM)
    assert all(p.display_group == INSTRUMENT_LABELS["CM"] for p in CM)
    assert all(p.key in BUILTIN_PRESET_KEYS for p in CM)
    assert all(p.combo_label in BUILTIN_PRESET_LABELS for p in CM)


def test_every_chart_reaches_the_dropdown_and_the_overlay():
    entries = dict(BUILTIN_PRESET_GROUPS)[INSTRUMENT_LABELS["CM"]]
    keys = [k for (_combo, _overlay, k) in entries]
    for p in CM:
        assert p.key in keys, f"{p.slug} is registered but never offered"


def test_shown_smallest_sheet_first_then_by_patch_count():
    # The dropdown and the built-in overlay read the same list, so this order is
    # what the user sees in both.
    entries = dict(BUILTIN_PRESET_GROUPS)[INSTRUMENT_LABELS["CM"]]
    by_key = {p.key: p for p in CM}
    ours = [by_key[k] for (_c, _o, k) in entries if k in by_key]
    assert len(ours) == 45
    sheets = [n.split("-")[0] for n in (p.name for p in ours)]
    # A4, then Letter, then the A3 sheet, then A3+ — each in one unbroken block.
    assert [s for i, s in enumerate(sheets) if i == 0 or s != sheets[i - 1]] == \
        ["A4", "Letter", "A3", "A3Plus"]
    for sheet in ("A4", "Letter", "A3", "A3Plus"):
        counts = [p.patches for p in ours if p.name.startswith(sheet + "-")]
        assert counts == sorted(counts), f"{sheet} is not in patch-count order"


def test_the_superseded_colormunki_family_is_gone():
    # Knut's earlier "Full layout setup" ColorMunki charts were replaced by this
    # family. His i1Pro ones, the "by Pharmacist" charts and the Red River vendor
    # family are untouched.
    assert not [p for p in KNUT_PRESETS if p.slug.startswith("fls_colormunki")]
    assert [p for p in KNUT_PRESETS if p.slug.startswith("fls_i1pro")]
    assert [p for p in KNUT_PRESETS if p.group == "Red River Paper"]
    assert any("by Pharmacist" in lbl for lbl in BUILTIN_PRESET_LABELS)


# ---------------------------------------------------------------------------
# One shared recipe — the point of the family
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("preset", CM, ids=lambda p: p.slug)
def test_chart_differs_from_the_family_base_only_where_allowed(preset):
    """A chart may set its paper, its grid, and (Hand Held) its left margin and
    clip note. Anything else diverging means the base and the authored charts
    have drifted apart — the layout would no longer be the one Knut measured."""
    recipe = preset.layout_recipe
    assert recipe is not None, "the family is engine-built, not printtarg"
    assert set(recipe) == set(_CM_BASE) | OWN_FIELDS
    for field in set(_CM_BASE) - OWN_FIELDS:
        assert recipe[field] == _CM_BASE[field], field


@pytest.mark.parametrize("preset", CM, ids=lambda p: p.slug)
def test_the_measured_shape_of_the_family(preset):
    r = preset.layout_recipe
    # The ColorMunki, double density, no stagger — what the charts were read on.
    assert r["instrument"] == "CM" and r["cm_density"] == 2
    assert r["cm_stagger"] is False
    # Area-first by grid: the margins are law, the grid sets the patch size.
    assert r["layout_mode"] == "area_first" and r["area_method"] == "by_grid"
    # Helper markers are the whole point — at ~10 mm patches the ruler goes four
    # markers below the strip being read.
    assert r["helper_markers"] is True
    assert r["helper_marker_edge_mm"] == 4.0 and r["helper_marker_len_mm"] == 2.0
    # Margins Knut measured: knobs clear the top edge, 12 mm of white to end a
    # strip on, and a right band wide enough to read the last strip with a ruler.
    assert r["margin_top"] == 34.0
    assert r["margin_bottom"] == 18.0
    assert r["margin_right"] == 24.0
    assert r["clip_border"] is True and r["clip_side"] == "right"
    assert r["clip_flip_180"] is True


def test_hand_held_charts_are_the_only_ones_with_a_narrow_left_margin():
    """The 26 mm 'Hand Held' charts are read by hand, not along a ruler, so the
    glide-rails don't have to stay on the page and the left margin drops to
    6 mm. Their clip-border note says so; every other chart keeps 14 mm."""
    hand_held = [p for p in CM if p.name.endswith("-Hand Held")]
    assert len(hand_held) == 3
    for p in hand_held:
        assert p.layout_recipe["margin_left"] == 6.0
        assert p.layout_recipe["clip_text"] == _CM_CLIP_TEXT_HAND_HELD
        assert "w26.0mm" in p.name
    for p in CM:
        if p in hand_held:
            continue
        assert p.layout_recipe["margin_left"] == 14.0
        assert p.layout_recipe["clip_text"] == _CM_CLIP_TEXT


def test_the_clip_border_explains_every_margin():
    # The reasoning travels on the printed sheet, so it is still there months
    # later when someone asks why the top margin is so large.
    for text in (_CM_CLIP_TEXT, _CM_CLIP_TEXT_HAND_HELD):
        for placeholder in ("{project}", "{paper}", "{instrument}",
                            "{patchcount}", "{page}", "{date}", "{seed}"):
            assert placeholder in text
        assert "Top margin: 34 mm" in text
        assert "Bottom margin: 18 mm" in text
        assert "Right margin: 24 mm" in text
        # Knut's own wording, 2026-08-16: the knobs are *underneath* the
        # instrument, not "on bottom" — his phrasing, kept verbatim.
        assert "knobs underneath" in text and "knobs on bottom" not in text


# ---------------------------------------------------------------------------
# Names tell the truth about the bundled files
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("preset", CM, ids=lambda p: p.slug)
def test_name_matches_the_bundled_patch_set_and_the_grid(preset):
    m = _NAME_RE.match(preset.name)
    assert m, f"name does not follow the convention: {preset.name}"
    assert int(m.group("patches")) == preset.patches
    assert int(m.group("pages")) == preset.pages

    ti1 = resource_path(preset.ti1_asset)
    assert ti1.is_file(), f"missing {preset.ti1_asset}"
    txt = ti1.read_text(encoding="latin-1", errors="ignore")
    assert int(re.search(r"NUMBER_OF_SETS\s+(\d+)", txt).group(1)) == preset.patches
    # printtarg needs all three tables of a targen .ti1 — a truncated export
    # builds nothing, so guard the bundled file's completeness.
    assert txt.count("NUMBER_OF_SETS") == 3

    # The grid decides how many sheets the set needs; the name must agree.
    per_sheet = preset.layout_recipe["area_cols"] * preset.layout_recipe["area_rows"]
    assert -(-preset.patches // per_sheet) == preset.pages


@pytest.mark.parametrize("preset", CM, ids=lambda p: p.slug)
def test_chart_carries_its_colour_set_recipe(preset):
    """Every chart ships the design it was generated from, so "Load setup from
    preset" in the New-chart window can start from it.

    Knut designs a colour set once and lays it out on several sheets, so his
    export's recipe keeps whatever instrument and paper were on screen when the
    *colours* were designed — for 33 of the 45 that was not this chart's sheet.
    The import script re-points them (see ``normalise_recipe``); without that,
    loading the setup for a ColorMunki A3 chart would seed an i1Pro on A4.
    """
    side = resource_path(preset.ti1_asset).parent / "recipe.json"
    assert side.is_file(), f"{preset.slug} has no recipe.json"
    rec = json.loads(side.read_text(encoding="utf-8"))
    assert rec.get("instr") == "CM"
    assert rec.get("paper") == preset.layout_recipe["paper"]
    assert rec["sp"]["fill_to"] == preset.patches
    assert rec.get("layout", {}).get("h") is True     # double density
    assert rec.get("layout", {}).get("td") is False


def test_the_slow_and_fast_pairs_differ_only_in_strip_length():
    """The ColorMunki reads a strip at a speed the patch count per strip sets, so
    most sheets come in a Fast and a Slow variant. Same paper, same patch count,
    fewer strips down the page on the fast one."""
    pairs = [("cm_a4_1224p_4pages_portrait_w10_0mm_slow_reading_speed",
              "cm_a4_1224p_6pages_portrait_w10_0mm_fast_reading_speed"),
             ("cm_letter_612p_2pages_portrait_w10_0mm_slow_reading_speed",
              "cm_letter_612p_3pages_portrait_w10_0mm_fast_reading_speed")]
    by_slug = {p.slug: p for p in CM}
    for slow_slug, fast_slug in pairs:
        slow, fast = by_slug[slow_slug], by_slug[fast_slug]
        assert slow.patches == fast.patches
        assert slow.layout_recipe["paper"] == fast.layout_recipe["paper"]
        assert slow.layout_recipe["area_cols"] == fast.layout_recipe["area_cols"]
        assert fast.layout_recipe["area_rows"] < slow.layout_recipe["area_rows"]
        assert fast.pages > slow.pages       # shorter strips, more sheets


# ---------------------------------------------------------------------------
# The tooltip a user actually reads
# ---------------------------------------------------------------------------

def test_tooltip_describes_the_sheet_not_a_scanner():
    p = next(x for x in CM if x.slug.startswith("cm_a4_204p"))
    tip = TabChart._knut_tooltip(p.key)
    assert "204-patch" in tip and "ColorMunki" in tip
    assert "17 patches across × 12 strips down" in tip
    assert "ruler" in tip
    # These are read with a spectrophotometer — the scanner family's wording
    # ("scan it on a flatbed scanner") must not leak into them.
    assert "flatbed" not in tip


# ---------------------------------------------------------------------------
# What the screen says after a preset is loaded
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


@pytest.fixture
def tab(qapp, tmp_path):
    from PyQt6.QtCore import QSettings
    from core.argyll_runner import ArgyllRunner
    from core.file_manager import FileManager
    from core.settings import AppSettings
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    s.set("custom_output_path", str(tmp_path / "projects"))
    s.set("helper_markers_show", False)          # off before the preset loads
    t = TabChart(ArgyllRunner(s), FileManager(s), s)
    t._switch_mode("manual")
    return t


def test_loading_a_preset_ticks_show_helper_markers(tab, monkeypatch):
    """Basti, 2026-08-16: *"loading knuts presets with the helper markers turned
    on did not set the show helper markers option there."*

    The markers reached the printed sheet, but the tick box —
    the only place they are shown on screen — still said off. Every one of these
    charts has them on, so after loading one the box must be ticked and the two
    distances must show the preset's values.
    """
    monkeypatch.setattr(TabChart, "_generate_from_ti1",
                        lambda self, ti1, ask=True: None)
    lp = tab._manual_layout_panel
    assert lp.helper_markers_cb.isChecked() is False

    preset = next(p for p in CM if p.slug.startswith("cm_a4_204p"))
    tab._apply_knut_preset(preset.key, "Probe")

    on = lp.helper_markers_cb.isChecked()
    edge = lp.helper_marker_edge.value()
    length = lp.helper_marker_len.value()
    assert on is True
    assert edge == preset.layout_recipe["helper_marker_edge_mm"] == 4.0
    assert length == preset.layout_recipe["helper_marker_len_mm"] == 2.0
    # …and remembered, so the next chart starts where this one left off.
    assert tab._settings.get("helper_markers_show") is True


# ---------------------------------------------------------------------------
# Built for real
# ---------------------------------------------------------------------------

def _build(preset, tmp_path):
    from workflow.layout_engine.chart import build_from_recipe
    from workflow.layout_engine.presets import LayoutRecipe
    result, _ = build_from_recipe(
        resource_path(preset.ti1_asset), tmp_path / "chart",
        LayoutRecipe.from_dict(preset.layout_recipe))
    return result


def _ti2_rows(path) -> int:
    txt = path.read_text(encoding="latin-1", errors="ignore")
    start = txt.index("BEGIN_DATA\n", txt.index("END_DATA_FORMAT"))
    body = txt[start + len("BEGIN_DATA\n"):txt.index("END_DATA", start)]
    return len([ln for ln in body.strip().splitlines() if ln.strip()])


# One per sheet size, portrait and landscape, single- and multi-page — enough to
# catch a broken recipe without building all 45 in the everyday tier.
_SAMPLE = ["cm_a4_204p_1page_portrait_w10_0mm_fast_reading_speed",
           "cm_a4_1623p_8pages_portrait_w10_0mm_fast_reading_speed",
           "cm_letter_612p_3pages_portrait_w10_0mm_fast_reading_speed",
           "cm_a3_912p_2pages_landscape_w10_0mm_fast_reading_speed",
           "cm_a3plus_616p_1page_landscape_w10_0mm_fast_reading_speed"]


@pytest.mark.parametrize("slug", _SAMPLE)
def test_sample_charts_build_to_the_promised_page_count(slug, tmp_path):
    preset = next(p for p in CM if p.slug == slug)
    result = _build(preset, tmp_path)
    assert len(result.tiff_paths or []) == preset.pages
    # A patch count that doesn't fill the last strip is padded out with white —
    # ordinary engine behaviour — so the chart holds AT LEAST Knut's colours.
    rows = _ti2_rows(result.ti2_path)
    assert rows >= preset.patches
    per_sheet = preset.layout_recipe["area_cols"] * preset.layout_recipe["area_rows"]
    assert rows <= preset.pages * per_sheet


@pytest.mark.parametrize("slug", _SAMPLE)
def test_helper_markers_are_actually_drawn(slug, tmp_path):
    """The markers reach the paper, not just the recipe — measured by looking for
    ink in the blank band along the page edge, where only they can be."""
    from PIL import Image
    import numpy as np
    preset = next(p for p in CM if p.slug == slug)
    result = _build(preset, tmp_path)
    dpi = preset.layout_recipe["dpi"]
    page = np.asarray(Image.open(result.tiff_paths[0]).convert("L"))
    # The recipe puts the dashes 4 mm from the edge, 2 mm long. Sample a band
    # from the very edge to just past their inner end.
    band_px = int(round((4.0 + 2.0 + 1.0) / 25.4 * dpi))
    left = page[:, :band_px]
    assert (left < 128).any(), "no helper markers along the left edge"
    top = page[:band_px, :]
    assert (top < 128).any(), "no helper markers along the top edge"


@pytest.mark.slow
@pytest.mark.parametrize("preset", CM, ids=lambda p: p.slug)
def test_every_chart_builds_to_the_promised_page_count(preset, tmp_path):
    """The full sweep — all 45, because the page count in a name is a promise the
    user plans their paper around."""
    result = _build(preset, tmp_path)
    assert len(result.tiff_paths or []) == preset.pages
    rows = _ti2_rows(result.ti2_path)
    per_sheet = preset.layout_recipe["area_cols"] * preset.layout_recipe["area_rows"]
    assert preset.patches <= rows <= preset.pages * per_sheet
