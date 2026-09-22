"""Knut's 7.5 mm i1Pro charts in the "Maximised - No Clip-border" cut
(2026-09-22, issue #182, beta-34 batch K1).

    *"I have created yet more presets for the i1Pro, to be added as built-in
    like the others."*

EIGHT charts: 837 to 3348 patches on A4 and 783 to 3132 on US Letter, one to
four sheets each, portrait, the clip band off and the side margins at 5 mm.
That fits 27 columns of 7.5 mm patches where the standard 7.5 mm cut fits 24.

WHAT THESE TESTS ARE FOR. Like the photo cards before them, the eight share a
design that moves fields no chart of the existing 7.5 mm family may set for
itself, so they got a base of their own (``_I1_75_MAX_BASE``). A shared base
changes every chart that hangs off it at once and silently, so these things
are pinned:

 1. ``_I1_75_MAX_BASE`` differs from ``_I1_75_BASE`` in exactly eight fields,
    and ``_I1_75_BASE`` still says what it said in each of them;
 2. every chart is registered, non-deletable, filed under the i1Pro heading,
    carries its bundled ``.ti1`` and ``recipe.json``, and nothing else sits in
    the asset folder;
 3. every name tells the truth about the patch set, the sheet, the page count
    and the grid, and every chart is BUILT on the real engine and counted.

TWO THINGS HIS FILES SAY THAT THE NAMES DO NOT, carried as exported and
flagged for him rather than corrected: the ruler marks are 2 per patch and
4 mm long (#164 set 5 per patch for the i1Pro families), and the US Letter
charts print 7.62 mm patches under a name that says 7.5 (the Letter sheet is
5.9 mm wider than A4 and the grid is the same 27 columns).
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
    _I1_75_BASE, _I1_75_MAX_BASE, _I1_BASE, BUILTIN_PRESET_GROUPS,
    BUILTIN_PRESET_KEYS, BUILTIN_PRESET_LABELS, KNUT_PRESETS, TabChart,
    builtin_preset_recipe,
)

MAX = [p for p in KNUT_PRESETS if p.slug.startswith("i1_w75max_")]

TAIL = "-Portrait-w7.5mm-Maximised-No Clip-border"

#: What each name promises, transcribed from the eight filenames Knut sent:
#: (paper, patches, pages).
PROMISED = {
    "A4-837p-1page" + TAIL: ("A4", 837, 1),
    "A4-1674p-2pages" + TAIL: ("A4", 1674, 2),
    "A4-2511p-3pages" + TAIL: ("A4", 2511, 3),
    "A4-3348p-4pages" + TAIL: ("A4", 3348, 4),
    "Letter-783p-1page" + TAIL: ("Letter", 783, 1),
    "Letter-1566p-2pages" + TAIL: ("Letter", 1566, 2),
    "Letter-2349p-3pages" + TAIL: ("Letter", 2349, 3),
    "Letter-3132p-4pages" + TAIL: ("Letter", 3132, 4),
}

#: The grid his exports carry, per paper: one full sheet is exactly the
#: one-page chart's patch count (27 x 31 = 837, 27 x 29 = 783).
GRID = {"A4": (27, 31), "Letter": (27, 29)}

#: What the base moves away from ``_I1_75_BASE``, and all it moves, written as
#: (maximised, standard 7.5 mm) so a change at EITHER end is caught.
BASE_DELTA = {
    "clip_border":             (False, True),
    "clip_content_mode":       ("off", "notes"),
    "margin_left":             (5.0, 26.0),
    "margin_right":            (5.0, 4.0),
    "margin_bottom":           (9.0, 19.0),
    "text_edge_top_mm":        (4.0, 8.0),
    "helper_marker_len_mm":    (4.0, 2.0),
    "helper_marker_per_patch": (2, 5),
}

OWN_FIELDS = {"paper", "area_cols", "area_rows"}

_NAME_RE = re.compile(
    r"^(?P<paper>A4|Letter)-(?P<patches>\d+)p-(?P<pages>\d+)pages?-Portrait-"
    r"w(?P<width>[\d.]+)mm-Maximised-No Clip-border$")


# ---------------------------------------------------------------------------
# Registered, protected, and filed with the other i1Pro charts
# ---------------------------------------------------------------------------

def test_every_chart_registered():
    """EXACT, deliberately: a preset that goes missing is invisible in a
    dropdown of nearly two hundred entries."""
    assert len(MAX) == 8
    assert len({p.slug for p in MAX}) == 8
    assert {p.name for p in MAX} == set(PROMISED)
    assert all(p.key in BUILTIN_PRESET_KEYS for p in MAX)
    assert all(p.combo_label in BUILTIN_PRESET_LABELS for p in MAX)
    for p in MAX:
        assert p.key == f"__chromiq_knut_{p.slug}__"


def test_the_standard_75mm_family_did_not_grow():
    """The slug prefix is distinct on purpose: ``test_i1pro75_family`` counts
    the 7.5 mm family by ``i1_w75_`` and pins its 24-column grid, and these
    charts are neither."""
    assert not any(p.slug.startswith("i1_w75_") for p in MAX)
    assert sum(1 for p in KNUT_PRESETS if p.slug.startswith("i1_w75_")) == 19


def test_they_are_i1pro_charts_under_the_i1pro_heading():
    for p in MAX:
        assert p.group == ""
        assert p.file_group == "i1Pro"
        assert p.display_group == INSTRUMENT_LABELS["i1"]
        assert p.instrument == "i1"
        assert p.layout_recipe["instrument"] == "i1"
    entries = dict(BUILTIN_PRESET_GROUPS)[INSTRUMENT_LABELS["i1"]]
    keys = [k for (_c, _o, k) in entries]
    assert all(p.key in keys for p in MAX)


def test_each_row_carries_the_full_layout_setup_marker():
    for p in MAX:
        assert p.has_full_layout_setup, p.name
        assert p.combo_label == f"★  i1Pro · {p.marked_name}  ·  built-in"
        # The suggested PROJECT FOLDER keeps the sortable #68 convention (the
        # width token moves to the end) and never carries the marker.
        assert p.default_target_name.startswith("i1Pro-")
        assert "Full layout setup" not in p.default_target_name


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
    t = TabChart(ArgyllRunner(s), FileManager(s), s)
    t._switch_mode("manual")
    return t


def test_no_chart_of_this_cut_can_be_deleted(tab):
    """Driven through the real combo, so a preset that reached the dropdown by
    another door would still be caught."""
    combo = tab._preset_combo
    keys = {p.key for p in MAX}
    seen = set()
    for i in range(combo.count()):
        data = combo.itemData(i)
        if data in keys:
            seen.add(data)
            assert tab._is_deletable_preset(i) is False, combo.itemText(i)
    assert seen == keys, f"not in the dropdown: {sorted(keys - seen)}"


def test_they_are_offered_in_the_verification_window():
    """"Which presets can be used for verification" lists every built-in from
    ``BUILTIN_PRESET_GROUPS``; these must be there with their chart on disk,
    their true patch count and the page count their names say."""
    from ui.tabs.tab_chart import verification_preset_rows
    rows = {r.key: r for r in verification_preset_rows(None) if r.builtin}
    for p in MAX:
        r = rows.get(p.key)
        assert r is not None, f"{p.name} is missing from the window"
        assert r.chart is not None and r.chart.is_file()
        assert r.patches == p.patches
        assert r.pages == p.pages
        assert r.relayoutable is True


# ---------------------------------------------------------------------------
# A base of its own, and the one it must not have touched
# ---------------------------------------------------------------------------

def test_the_base_moves_exactly_eight_fields_away_from_the_75mm_one():
    moved = {k for k in set(_I1_75_BASE) | set(_I1_75_MAX_BASE)
             if _I1_75_BASE.get(k) != _I1_75_MAX_BASE.get(k)}
    assert moved == set(BASE_DELTA)
    for field, (maxi, std) in BASE_DELTA.items():
        assert _I1_75_MAX_BASE[field] == maxi, field
        assert _I1_75_BASE[field] == std, f"_I1_75_BASE moved: {field}"


def test_the_8mm_and_75mm_bases_are_untouched():
    assert _I1_75_BASE["sscale"] == 0.75 and _I1_BASE["sscale"] == 0.8
    assert _I1_75_BASE["margin_right"] == 4.0
    assert _I1_BASE["margin_right"] == 6.0
    assert _I1_BASE["clip_border"] is True
    assert _I1_BASE["helper_marker_per_patch"] == 5


@pytest.mark.parametrize("preset", MAX, ids=lambda p: p.slug)
def test_recipe_differs_from_the_base_only_in_sheet_and_grid(preset):
    rec = preset.layout_recipe
    assert set(rec) == set(_I1_75_MAX_BASE) | OWN_FIELDS
    for field in set(_I1_75_MAX_BASE) - OWN_FIELDS:
        assert rec[field] == _I1_75_MAX_BASE[field], (
            f"{preset.slug} changes {field}, which the cut shares")
    assert (rec["area_cols"], rec["area_rows"]) == GRID[rec["paper"]]
    # The name says "No Clip-border", and the band is off.
    assert rec["clip_border"] is False
    assert rec["clip_content_mode"] == "off"


# ---------------------------------------------------------------------------
# Names tell the truth about the bundled files
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("preset", MAX, ids=lambda p: p.slug)
def test_name_matches_the_bundled_patch_set_and_the_grid(preset):
    m = _NAME_RE.match(preset.name)
    assert m, f"name does not follow the convention: {preset.name}"
    paper, patches, pages = PROMISED[preset.name]
    assert m.group("paper") == paper == preset.layout_recipe["paper"]
    assert int(m.group("patches")) == patches == preset.patches
    assert int(m.group("pages")) == pages == preset.pages
    assert float(m.group("width")) == 7.5 == preset.patch_width_mm

    ti1 = resource_path(preset.ti1_asset)
    txt = ti1.read_text(encoding="latin-1", errors="ignore")
    assert int(re.search(r"NUMBER_OF_SETS\s+(\d+)", txt).group(1)) == patches
    assert txt.count("NUMBER_OF_SETS") == 3
    assert (preset.white, preset.black) == (2, 2)
    assert 'WHITE_COLOR_PATCHES "2"' in txt and 'BLACK_COLOR_PATCHES "2"' in txt
    cols, rows = GRID[paper]
    assert -(-patches // (cols * rows)) == pages


def test_every_chart_has_its_bundled_files_and_nothing_else_is_there():
    leaves = set()
    for p in MAX:
        ti1 = resource_path(p.ti1_asset)
        assert ti1.is_file() and ti1.stat().st_size > 0, p.slug
        assert (ti1.parent / "recipe.json").is_file(), p.slug
        assert ti1.parent.name == p.slug
        leaves.add(ti1.parent)
    root = next(iter(leaves)).parent
    assert root.name == "i1pro75max"
    assert {d for d in root.iterdir() if d.is_dir()} == leaves


@pytest.mark.parametrize("preset", MAX, ids=lambda p: p.slug)
def test_sidecar_recipe_matches_its_chart(preset):
    """Five of his eight exports carried a colour-set recipe that pointed at a
    ColorMunki, at an A3 sheet or at A4 beside a Letter chart; the importer
    re-points them and this pins the result."""
    sidecar = resource_path(preset.ti1_asset).parent / "recipe.json"
    rec = json.loads(sidecar.read_text(encoding="utf-8"))
    assert rec["instr"] == "i1"
    assert rec["paper"] == preset.layout_recipe["paper"]
    assert rec["sp"]["fill_to"] == preset.patches
    assert rec["layout"]["h"] is False and rec["layout"]["td"] is False
    assert rec["layout"]["dpi"] == 200 and rec["layout"]["bit16"] is False
    assert builtin_preset_recipe(preset.key) == rec


# ---------------------------------------------------------------------------
# Selecting one, and what the user is told
# ---------------------------------------------------------------------------

def test_the_tooltip_promises_no_band_it_does_not_print():
    for p in MAX:
        tip = TabChart._knut_tooltip(p.key)
        assert "cannot be deleted" in tip
        assert f"{p.patches}-patch" in tip and "i1Pro" in tip
        assert "run-up" not in tip and "band" not in tip


@pytest.mark.parametrize("preset", MAX, ids=lambda p: p.slug)
def test_seeding_a_preset_puts_its_layout_on_the_panel(tab, preset):
    tab._seed_knut_preset(preset.key)
    got = tab._manual_layout_panel.get_recipe().to_dict()
    for field in sorted(preset.layout_recipe):
        assert got[field] == preset.layout_recipe[field], field


def test_every_chart_switches_the_settings_stamp_off(tab):
    """All eight of Knut's exports carry "Stamp settings down the right edge"
    OFF, and the app's default is ON. With it on and a 5 mm right margin the
    command line runs over the patches: driven on screen 2026-09-22, the
    A4-837p chart came up with "The settings stamp down the right edge runs
    over the patches". So the preset carries his answer, and seeding it moves
    the tick box off from on."""
    box = tab._manual_stamp_cmd_check
    for p in MAX:
        assert p.stamp_settings is False, p.slug
        box.setChecked(True)
        tab._seed_knut_preset(p.key)
        assert box.isChecked() is False, p.slug
        assert p.chart_notes == ""


# ---------------------------------------------------------------------------
# It builds, on the real engine
# ---------------------------------------------------------------------------

#: Measured 2026-09-22 on the engine: 7.49 mm on A4, 7.62 mm on Letter. The
#: Letter figure is Knut's naming, not a fault here; see the module docstring.
WIDTH = {"A4": 7.49, "Letter": 7.62}


@pytest.mark.parametrize("preset", MAX, ids=lambda p: p.slug)
def test_chart_builds_with_the_sheet_pages_and_patches_its_name_promises(preset):
    from workflow.layout_engine import papers
    from workflow.layout_engine.chart import build_from_recipe
    from workflow.layout_engine.presets import LayoutRecipe
    paper, patches, pages = PROMISED[preset.name]
    rec = LayoutRecipe.from_dict(preset.layout_recipe)
    with tempfile.TemporaryDirectory() as td:
        res, _ = build_from_recipe(resource_path(preset.ti1_asset),
                                   Path(td) / "chart", rec)
        assert len(sorted(Path(td).glob("chart*.tif"))) == pages
        assert res.layout.total_patches == patches      # no white padding
        blob = json.loads((Path(td) / "chart.strips.json")
                          .read_text(encoding="utf-8"))
        dpi = blob["dpi"]
        sheet_w, sheet_h = papers.dimensions_mm(paper)
        assert len(blob["patches"]) == patches
        for q in blob["patches"]:
            assert 0 <= q["x"] and (q["x"] + q["w"]) * 25.4 / dpi <= sheet_w
            assert 0 <= q["y"] and (q["y"] + q["h"]) * 25.4 / dpi <= sheet_h
        got = blob["patches"][0]["w"] * 25.4 / dpi
    assert got == pytest.approx(WIDTH[paper], abs=0.02)
    assert abs(got - 7.5) <= 0.5, f"name says 7.5 mm, the sheet has {got:.2f}"
