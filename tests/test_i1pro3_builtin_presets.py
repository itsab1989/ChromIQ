"""Knut's i1Pro 3 Plus built-in presets (2026-08-18).

His whole i1Pro 3 Plus line-up: one colour set per size, from a single sheet of
84 big patches up to 2,016 patches on six A3 sheets, all laid out by the ChromIQ
layout engine.

It is a TIGHTER family than the ColorMunki one next door. Every chart shares all
four margins and shows the automatic notes box in the clip border, so a single
chart owns only its paper and its columns × rows grid. That is what these tests
guard: editing ``_P3_BASE`` changes all 24 charts at once and silently, so the
base is pinned against the three fields a chart may own, the names are checked
against the grids and patch sets they claim, and every chart is actually built
and counted.

They also pin the boundary against the plain i1Pro family: these layouts are cut
for the 3 Plus and appear under their own group, never folded in with charts for
the i1Pro 1/2.
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
from data.patch_db import INSTRUMENT_LABELS  # noqa: E402
from ui.tabs.tab_chart import (  # noqa: E402
    _P3_BASE, _P3_GROUP,
    BUILTIN_PRESET_GROUPS, BUILTIN_PRESET_KEYS, BUILTIN_PRESET_LABELS,
    KNUT_PRESETS, TabChart,
)

P3 = [p for p in KNUT_PRESETS if p.slug.startswith("p3_")]

# Exactly the fields a single chart in this family may set for itself.
OWN_FIELDS = {"paper", "area_cols", "area_rows"}

_NAME_RE = re.compile(
    r"^(?P<sheet>A4|A3Plus|A3|Letter)-(?P<patches>\d+)p-(?P<pages>\d+)pages?-"
    r"(?P<orientation>Portrait|Landscape)-w(?P<width>[\d.]+)mm$")


# ---------------------------------------------------------------------------
# The family is registered, and it is its own family
# ---------------------------------------------------------------------------

def test_twenty_four_charts_registered():
    assert len(P3) == 24
    assert len({p.slug for p in P3}) == 24           # slugs are the identity
    assert len({p.name for p in P3}) == 24
    assert all(p.key in BUILTIN_PRESET_KEYS for p in P3)
    assert all(p.combo_label in BUILTIN_PRESET_LABELS for p in P3)


def test_the_family_has_its_own_group_and_never_joins_the_i1pro_one():
    """An i1Pro 1/2 owner must not be handed a layout cut for the 3 Plus, so the
    group is explicit rather than derived from the instrument."""
    assert all(p.display_group == _P3_GROUP for p in P3)
    # The heading is the Instrument selection field's own name for the device.
    assert _P3_GROUP == INSTRUMENT_LABELS["p3"] == "i1Pro 3 Plus"
    groups = dict(BUILTIN_PRESET_GROUPS)
    assert _P3_GROUP in groups
    own = {k for (_c, _o, k) in groups[_P3_GROUP]}
    assert {p.key for p in P3} == own
    i1_keys = {k for (_c, _o, k) in groups[INSTRUMENT_LABELS["i1"]]}
    assert not (own & i1_keys)


def test_every_chart_reaches_the_dropdown_and_the_overlay():
    entries = dict(BUILTIN_PRESET_GROUPS)[_P3_GROUP]
    keys = [k for (_combo, _overlay, k) in entries]
    for p in P3:
        assert p.key in keys
    # Smallest sheet first, then ascending patch count — the order the user sees.
    order = [next(q for q in P3 if q.key == k) for k in keys]
    sheets = [("A4", "Letter", "A3").index(q.layout_recipe["paper"]) for q in order]
    assert sheets == sorted(sheets)


def test_keys_are_stable_sentinels():
    for p in P3:
        assert p.key == f"__chromiq_knut_{p.slug}__"


# ---------------------------------------------------------------------------
# One shared recipe: a chart owns its sheet and its grid, nothing else
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("preset", P3, ids=lambda p: p.slug)
def test_recipe_differs_from_the_base_only_where_allowed(preset):
    rec = preset.layout_recipe
    assert rec is not None, "the family is engine-built, not printtarg"
    # The chart's recipe is the shared base plus exactly its own three fields.
    assert set(rec) == set(_P3_BASE) | OWN_FIELDS
    for field in set(_P3_BASE) - OWN_FIELDS:
        assert rec[field] == _P3_BASE[field], (
            f"{preset.slug} changes {field}, which the whole family shares")


def test_the_measured_shape_of_the_family():
    """The numbers Knut measured on paper. They are the reason the family exists,
    so they are written down rather than left implicit in 24 rows."""
    r = _P3_BASE
    assert r["instrument"] == "p3"
    # Margins: a 40 mm run-in at the top so the instrument body clears the first
    # patch, 20 mm of white at the bottom to finish a strip on.
    assert r["margin_top"] == 40.0
    assert r["margin_bottom"] == 20.0
    assert r["margin_left"] == 28.0
    assert r["margin_right"] == 10.0
    assert r["use_instrument_margins"] is False
    # The clip band: 28 mm down the LEFT, upright, carrying the notes box.
    assert r["clip_border"] is True
    assert r["clip_border_width_mm"] == 28.0
    assert r["clip_side"] == "left"
    assert r["clip_flip_180"] is False
    assert r["clip_content_mode"] == "notes"
    assert r["clip_text"] == ""                  # the notes box is generated
    # Reading aids and the layout method.
    assert r["helper_markers"] is True
    assert r["show_strip_indicators"] is True
    assert r["spacer_on"] is True and r["edge_spacers"] is True
    assert r["layout_mode"] == "area_first" and r["area_method"] == "by_grid"
    assert r["nolimit"] is True
    assert r["randomize"] is True
    assert r["cm_density"] == 1                  # a ColorMunki-only setting
    assert r["dpi"] == 200 and r["bit16"] is False


def test_the_left_margin_is_never_per_chart():
    """Unlike the ColorMunki family, no chart here pulls its own margin in — if
    one ever needs to, OWN_FIELDS and _p3_preset have to say so explicitly."""
    assert all(p.layout_recipe["margin_left"] == 28.0 for p in P3)


# ---------------------------------------------------------------------------
# Names tell the truth about the bundled files
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("preset", P3, ids=lambda p: p.slug)
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

    cols = preset.layout_recipe["area_cols"]
    rows = preset.layout_recipe["area_rows"]
    per_page = cols * rows
    assert -(-preset.patches // per_page) == preset.pages, (
        f"{cols}×{rows} per sheet does not put {preset.patches} patches on "
        f"{preset.pages} page(s)")


def test_the_two_big_patch_charts_are_the_only_wide_ones():
    """84 patches at 25 mm is the one-sheet quick chart; everything else is the
    16 mm working size."""
    wide = [p for p in P3 if "w25.0mm" in p.name]
    assert len(wide) == 2
    assert {p.layout_recipe["paper"] for p in wide} == {"A4", "Letter"}
    assert all(p.patches == 84 and p.pages == 1 for p in wide)
    assert all(p.layout_recipe["area_cols"] == 7 for p in wide)
    for p in P3:
        if p not in wide:
            assert "w16.0mm" in p.name


# ---------------------------------------------------------------------------
# The colour-set sidecar (Set B) points at the chart it actually built
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("preset", P3, ids=lambda p: p.slug)
def test_sidecar_recipe_matches_its_chart(preset):
    """"Load setup from preset" seeds the New-chart window from this file. Knut
    designs a colour set once and lays it out on several sheets, so his exports
    carry whatever instrument and paper were on screen at design time — every one
    of these 24 did. The importer re-points them; this pins the result."""
    sidecar = resource_path(preset.ti1_asset).parent / "recipe.json"
    assert sidecar.is_file(), f"missing {sidecar}"
    rec = json.loads(sidecar.read_text())
    assert rec["instr"] == "p3"
    assert rec["paper"] == preset.layout_recipe["paper"]
    assert rec["sp"]["fill_to"] == preset.patches
    layout = rec["layout"]
    assert layout["h"] is False                  # ColorMunki double density
    assert layout["td"] is False                 # triple density
    assert layout["dpi"] == 200
    assert layout["bit16"] is False


# ---------------------------------------------------------------------------
# Selecting one, and what the user is told
# ---------------------------------------------------------------------------

def test_tooltip_describes_the_sheet_and_the_run_up_band():
    tip = TabChart._knut_tooltip(P3[0].key)
    assert "cannot be deleted" in tip
    assert "i1Pro 3 Plus" in tip                 # the group's name, not "i1Pro 3+"
    assert "run-up" in tip                       # the wide empty band is explained
    assert "helper marks" in tip


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
    """Same rule the ColorMunki family is held to (Basti, 2026-08-16): the
    markers are on in every chart here, so the tick box under the preview — the
    only place they show on screen — must say so after one is loaded."""
    monkeypatch.setattr(TabChart, "_generate_from_ti1",
                        lambda self, ti1, ask=True: None)
    assert tab._margin_panel.helper_markers()[0] is False

    preset = next(p for p in P3 if p.slug.startswith("p3_a4_154p"))
    tab._apply_knut_preset(preset.key, "Probe")

    on, edge, length = tab._margin_panel.helper_markers()
    assert on is True
    assert edge == preset.layout_recipe["helper_marker_edge_mm"] == 2.0
    assert length == preset.layout_recipe["helper_marker_len_mm"] == 1.0
    assert tab._settings.get("helper_markers_show") is True


def test_seeding_a_preset_puts_its_layout_on_the_panel(tab):
    """The engine path: selecting one seeds the layout panel, not the printtarg
    widgets, and the panel comes back with exactly this chart's recipe."""
    preset = next(p for p in P3 if p.slug.startswith("p3_a3_336p"))
    tab._seed_knut_preset(preset.key)
    got = tab._manual_layout_panel.get_recipe().to_dict()
    for field in ("paper", "area_cols", "area_rows", "margin_left",
                  "clip_border_width_mm", "clip_content_mode", "instrument"):
        assert got[field] == preset.layout_recipe[field], field


# ---------------------------------------------------------------------------
# It builds — every chart, on the real engine
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("preset", P3, ids=lambda p: p.slug)
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
        strip = res.strip_rects[0]
        got = strip["w"] * 25.4 / rec.dpi
        assert abs(got - said) <= 0.5, (
            f"name says {said} mm patches, the sheet has {got:.2f} mm")
