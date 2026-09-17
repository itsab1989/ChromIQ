"""Knut's CR30 built-in presets: twenty of 2026-09-06, six more of 2026-09-12.

Thirteen charts on A4 and thirteen on US Letter, portrait, one to three sheets,
patches 11 mm to 24 mm wide, each size offered in a rectangular and (mostly) a
hexagonal cut, and six of the 11 mm hexagonal ones offered a second time with
the honeycomb turned 30 degrees so a strip runs straight down the sheet
(#159's "Straight strips"). Laid out by the ChromIQ layout engine, which for a
CR30 is not a choice: Argyll has no layout for the instrument, so
``chart_creator._should_use_engine`` forces the engine on and printtarg never
sees one of these.

WHAT THESE TESTS ARE FOR. Twenty-six rows share one base recipe, so editing
``_CR30_BASE`` changes twenty-six charts at once and silently. The base is
therefore pinned against exactly the fields a chart may own, each cut is pinned
as a named block rather than a handful of numbers loose on a dozen rows, and
**every one of the twenty-six is actually built and counted** against the name
it carries. A preset that does not deliver what its name says is worse than no
preset.

ACROSS THE FLATS IS THE PATCH. A hexagon has two spans, and only one of them is
the number a name like "w11.0mm" is promising: the distance between the two
parallel flats, which is the biggest circle that fits inside and so what a
CR30's round head has to land in. On an upright honeycomb that is the slot
rect's width; on a turned one the slot's width is the COLUMN PITCH and the
flats are its height. Measuring ``w`` in both would have read Knut's six turned
charts at 9.4 mm and called their own names wrong by 1.6 mm.

WHAT SETS A PATCH'S WIDTH HERE, measured rather than assumed, because two
mutations that looked like they should have moved it did not. The chart area is
``paper_w - margin_left - max(margin_right, clip_border_width_mm)``, divided by
``area_cols``. Both are 26 mm in this family, so the clip band and the right
margin MASK each other: dropping either one alone changes nothing on paper.
Only a change that lifts the larger of the two, or moves ``margin_left`` or the
column count, moves a patch. Anyone mutating this family to check a guard should
know that before concluding a guard is asleep.

THE TWO NAMES THAT ROUND DIFFERENTLY. ``Letter-150p-…-w17.0mm`` prints 17.53 mm
patches and ``Letter-170p-…-w16.0mm-Hexagonal`` prints 16.64 mm: both wider than
the name, both Knut's own numbers (the shipped recipe is byte-for-byte his
export). They are pinned at what they measure rather than waved through, so if
either the layout or the name is corrected the test says so. Flagged for Knut.
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
    _CR30_BASE, _CR30_GROUP, _CR30_HEX, _CR30_STRAIGHT,
    BUILTIN_PRESET_GROUPS, BUILTIN_PRESET_KEYS, BUILTIN_PRESET_LABELS,
    KNUT_PRESETS, TabChart,
)


def _across_the_flats_mm(rect: dict, dpi: float, flat_top: bool) -> float:
    """The patch's own width, in either orientation. See the module docstring.

    The slot rect is ``(column pitch, row pitch)``. An upright hexagon's flats
    are its left and right sides, so the column pitch IS the patch; a turned
    one's flats are its top and bottom, and the pitch is 3/4 of the patch's
    other span.
    """
    return (rect["h"] if flat_top else rect["w"]) * 25.4 / dpi

CR30 = [p for p in KNUT_PRESETS if p.slug.startswith("cr30_")]

#: Fields a single chart of this family may set for itself. The sheet and the
#: grid always; the three below only where a row spells them out.
OWN_FIELDS = {"paper", "area_cols", "area_rows",
              "margin_top", "margin_bottom", "area_min_patch_mm",
              # The two low-patch hexagonal charts carry a label of their own
              # (Knut, 2026-09-16: *"with exception of the two low patch
              # presets with 153 and 170 patches"*), and
              # `test_the_two_low_patch_hex_charts_carry_the_larger_label`
              # below is what stops this entry from becoming a licence for any
              # chart to set any size it likes.
              "indicator_size_mm"}

#: Keys a recipe may carry that the base does not. Only the turned cut adds
#: one: ``hex_flat_top`` is the 30-degree turn itself, and no upright chart
#: writes it at all.
EXTRA_KEYS = {"hex_flat_top"}

_NAME_RE = re.compile(
    r"^(?P<sheet>A4|Letter)-(?P<patches>\d+)p-(?P<pages>\d+)pages?-"
    r"(?P<orientation>Portrait|Landscape)-w(?P<width>[\d.]+)mm"
    r"(?P<hex>-Hexagonal)?(?P<straight>-Straight)?$")

#: What each name promises: sheet, patches, pages, patch width across the
#: flats, hexagonal, turned. Transcribed from the filenames Basti curated (the
#: twenty of 2026-09-06) and from Knut's own six exports of 2026-09-12, whose
#: files spell it "Streight" and whose presets do not: the app's own control
#: says "Straight strips (turn the honeycomb 30 degrees)" and the names follow
#: the control. Written out rather than derived from the rows, so a row that
#: drifts from its own name cannot drift past this table too.
PROMISED = {
    "A4-77p-1page-Portrait-w24.0mm": ("A4", 77, 1, 24.0, False, False),
    "A4-153p-1page-Portrait-w18.0mm-Hexagonal": ("A4", 153, 1, 18.0, True, False),
    "A4-160p-1page-Portrait-w17.0mm": ("A4", 160, 1, 17.0, False, False),
    "A4-192p-1page-Portrait-w11.0mm": ("A4", 192, 1, 11.0, False, False),
    "A4-360p-1page-Portrait-w11.0mm": ("A4", 360, 1, 11.0, False, False),
    "A4-420p-1page-Portrait-w11.0mm-Hexagonal": ("A4", 420, 1, 11.0, True, False),
    "A4-720p-2pages-Portrait-w11.0mm": ("A4", 720, 2, 11.0, False, False),
    "A4-840p-2pages-Portrait-w11.0mm-Hexagonal": ("A4", 840, 2, 11.0, True, False),
    "A4-1080p-3pages-Portrait-w11.0mm": ("A4", 1080, 3, 11.0, False, False),
    "A4-1260p-3pages-Portrait-w11.0mm-Hexagonal": ("A4", 1260, 3, 11.0, True, False),
    "Letter-88p-1page-Portrait-w22.0mm": ("Letter", 88, 1, 22.0, False, False),
    "Letter-150p-1page-Portrait-w17.0mm": ("Letter", 150, 1, 17.0, False, False),
    "Letter-170p-1page-Portrait-w16.0mm-Hexagonal": ("Letter", 170, 1, 16.0, True, False),
    "Letter-184p-1page-Portrait-w11.0mm": ("Letter", 184, 1, 11.0, False, False),
    "Letter-368p-1page-Portrait-w11.0mm": ("Letter", 368, 1, 11.0, False, False),
    "Letter-390p-1page-Portrait-w11.0mm-Hexagonal": ("Letter", 390, 1, 11.0, True, False),
    "Letter-736p-2pages-Portrait-w11.0mm": ("Letter", 736, 2, 11.0, False, False),
    "Letter-780p-2pages-Portrait-w11.0mm-Hexagonal": ("Letter", 780, 2, 11.0, True, False),
    "Letter-1104p-3pages-Portrait-w11.0mm": ("Letter", 1104, 3, 11.0, False, False),
    "Letter-1170p-3pages-Portrait-w11.0mm-Hexagonal": ("Letter", 1170, 3, 11.0, True, False),
    # The turned cut (2026-09-12). Same 11 mm hexagon, 30 degrees round.
    "A4-450p-1page-Portrait-w11.0mm-Hexagonal-Straight": ("A4", 450, 1, 11.0, True, True),
    "A4-900p-2pages-Portrait-w11.0mm-Hexagonal-Straight": ("A4", 900, 2, 11.0, True, True),
    "A4-1350p-3pages-Portrait-w11.0mm-Hexagonal-Straight": ("A4", 1350, 3, 11.0, True, True),
    "Letter-396p-1page-Portrait-w11.0mm-Hexagonal-Straight": ("Letter", 396, 1, 11.0, True, True),
    "Letter-792p-2pages-Portrait-w11.0mm-Hexagonal-Straight": ("Letter", 792, 2, 11.0, True, True),
    "Letter-1188p-3pages-Portrait-w11.0mm-Hexagonal-Straight": ("Letter", 1188, 3, 11.0, True, True),
}

#: The two charts whose printed patch width is more than 0.5 mm from the width
#: in their own name. Both are wider, both are Knut's numbers, and both are
#: pinned at what they measure so a change to either end is caught.
WIDTH_EXCEPTIONS = {
    "Letter-150p-1page-Portrait-w17.0mm": 17.53,
    # 16.76 SINCE 2026-09-16, and the 0.12 mm is the left margin no longer
    # being raised behind the recipe's back. It used to ask for 13.0 and be
    # given 14.382 by the row-label band; it now asks for 14.0 and is given
    # 14.0, so the patch area is 0.38 mm wider and each of its ten columns
    # gains a thirty-eighth of that. The name was already 0.64 mm out and is
    # now 0.76 mm out; both are Knut's numbers and neither is a rounding this
    # test may absorb quietly. Still flagged for him.
    "Letter-170p-1page-Portrait-w16.0mm-Hexagonal": 16.76,
}


# ---------------------------------------------------------------------------
# The family is registered, and it is its own group
# ---------------------------------------------------------------------------

def test_twenty_six_charts_registered():
    assert len(CR30) == 26
    assert len({p.slug for p in CR30}) == 26         # slugs are the identity
    assert len({p.name for p in CR30}) == 26
    assert all(p.key in BUILTIN_PRESET_KEYS for p in CR30)
    assert all(p.combo_label in BUILTIN_PRESET_LABELS for p in CR30)
    assert {p.name for p in CR30} == set(PROMISED)


def test_keys_are_stable_sentinels():
    for p in CR30:
        assert p.key == f"__chromiq_knut_{p.slug}__"


def test_the_family_has_its_own_group_named_as_the_instrument_field_names_it():
    assert all(p.group == _CR30_GROUP for p in CR30)
    # Knut's rule (2026-08-18): a group heading uses the Instrument selection
    # field's own words for the device.
    assert all(p.display_group == INSTRUMENT_LABELS["CR30"] for p in CR30)
    groups = dict(BUILTIN_PRESET_GROUPS)
    own = {k for (_c, _o, k) in groups[INSTRUMENT_LABELS["CR30"]]}
    assert {p.key for p in CR30} == own
    # …and it borrows nothing from, and lends nothing to, another group.
    for heading, entries in BUILTIN_PRESET_GROUPS:
        if heading == INSTRUMENT_LABELS["CR30"]:
            continue
        assert not (own & {k for (_c, _o, k) in entries})


def test_the_cr30_group_comes_before_the_scanner_section():
    """Basti, 2026-09-06: *"i want them listed for the cr30 in both preset
    dropdowns / speechbubble overlay before the scanner section"*. Both read
    this one registry in order and neither re-sorts, so pinning the order here
    pins the dropdown AND the ★ overlay."""
    headings = [h for h, _e in BUILTIN_PRESET_GROUPS]
    assert INSTRUMENT_LABELS["CR30"] in headings
    assert "Scanner" in headings
    assert headings.index(INSTRUMENT_LABELS["CR30"]) < headings.index("Scanner")


def test_every_chart_reaches_the_dropdown_and_the_overlay_smallest_sheet_first():
    entries = dict(BUILTIN_PRESET_GROUPS)[INSTRUMENT_LABELS["CR30"]]
    keys = [k for (_combo, _overlay, k) in entries]
    assert {p.key for p in CR30} == set(keys)
    order = [next(q for q in CR30 if q.key == k) for k in keys]
    # A4 before Letter, then ascending patch count inside each sheet.
    shown = [(("A4", "Letter").index(q.layout_recipe["paper"]), q.patches)
             for q in order]
    assert shown == sorted(shown)


def test_every_row_carries_the_full_layout_setup_marker():
    """Knut asked for the marker on these. It is not typed into the name: it
    follows ``builtin_preset_recipe`` (a shipped recipe.json sidecar), so every
    one of the twenty earns it by carrying the colour-set design the patch-set
    editor can load."""
    for p in CR30:
        assert p.has_full_layout_setup, p.name
        assert p.marked_name == p.name + " · Full layout setup"
        assert p.combo_label == f"★  CR30 · {p.marked_name}  ·  built-in"
        # The suggested PROJECT FOLDER keeps the sortable #68 convention and
        # never carries the marker.
        assert p.default_target_name.startswith("CR30-")
        assert "Full layout setup" not in p.default_target_name


# ---------------------------------------------------------------------------
# One shared recipe, one named cut
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("preset", CR30, ids=lambda p: p.slug)
def test_recipe_differs_from_the_base_only_where_allowed(preset):
    rec = preset.layout_recipe
    assert rec is not None, "the family is engine-built, not printtarg"
    allowed = set(_CR30_BASE) | {"paper", "area_cols", "area_rows"}
    assert set(rec) - allowed <= EXTRA_KEYS, "a key no cut of this family adds"
    assert allowed - set(rec) == set(), "a base field the row dropped"
    hexed = "Hexagonal" in preset.name
    expected = dict(_CR30_BASE)
    if hexed:
        expected.update(_CR30_HEX)
    if "-Straight" in preset.name:
        # The turned cut is a REFINEMENT of the hexagonal one, applied after
        # it, exactly as `_cr30_preset(straight=True)` applies them.
        expected.update(_CR30_STRAIGHT)
    for field in set(_CR30_BASE) - OWN_FIELDS:
        assert rec[field] == expected[field], (
            f"{preset.slug} changes {field}, which its cut of the family shares")


def test_the_hexagonal_cut_is_exactly_these_four_fields_and_no_others():
    """Eight of the twenty-six take the upright hex cut and nothing further.
    What ``hexagonal=True`` buys is written once, here and in ``_CR30_HEX``,
    instead of five keyword arguments on eight rows where a fifth could hide."""
    hexes = [p for p in CR30
             if "Hexagonal" in p.name and "-Straight" not in p.name]
    rects = [p for p in CR30 if "Hexagonal" not in p.name]
    assert (len(hexes), len(rects)) == (8, 12)
    assert set(_CR30_HEX) == {"hflag", "margin_left", "margin_top",
                              "margin_bottom", "text_edge_top_mm",
                              "indicator_size_mm", "helper_markers"}
    for p in hexes:
        assert p.layout_recipe["hflag"] is True
        # 14.0, NOT 13.0. Knut, 2026-09-16, having measured it himself:
        # *"increase the left margin from setting from 13.0 to 14.0mm"*. At
        # 13.0 with the 11 pt label below, area-first is handed a wider box
        # and fills it with bigger patches, and the three Letter charts spill
        # onto a sheet their names do not promise.
        assert p.layout_recipe["margin_left"] == 14.0
        assert p.layout_recipe["text_edge_top_mm"] == 4.0
        # MARKERS OFF ON ALL EIGHT. A honeycomb carries dashes on one axis
        # only; this cut is pointy-top, so the live axis is "Sides", and
        # `_CR30_BASE` asks for top/bottom and not sides. The box was ticked
        # and the sheet printed no dashes at all.
        assert p.layout_recipe["helper_markers"] is False, (
            "a chart that cannot print dashes must not advertise them")
        assert p.layout_recipe.get("hex_flat_top") is None, (
            "an upright chart must not carry the turn at all")
    for p in rects:
        assert p.layout_recipe["hflag"] is False
        assert p.layout_recipe["margin_left"] == 15.0
        assert p.layout_recipe["text_edge_top_mm"] == 8.0
        assert p.layout_recipe["margin_top"] == 17.0
        assert p.layout_recipe["margin_bottom"] == 12.0


def test_the_straight_cut_is_the_hexagonal_one_turned_and_six_numbers():
    """Six of the twenty-six take it, and it is applied ON TOP of the hex cut.

    Knut's six exports of 2026-09-12 differ from the hexagonal charts they were
    cut from in exactly these fields, so ``straight=True`` says all of it and no
    row of the six spells anything else out. The turn implies the hexagon: asked
    for alone it would be a flat-top nothing.
    """
    straight = [p for p in CR30 if "-Straight" in p.name]
    assert len(straight) == 6
    assert set(_CR30_STRAIGHT) == {"hflag", "hex_flat_top", "margin_left",
                                   "margin_top", "margin_bottom",
                                   "text_edge_top_mm", "indicator_size_mm",
                                   "helper_markers"}
    for p in straight:
        r = p.layout_recipe
        assert "Hexagonal" in p.name, "the turn is a cut of the hexagonal one"
        assert r["hflag"] is True and r["hex_flat_top"] is True
        assert (r["margin_left"], r["margin_top"], r["margin_bottom"]) == (
            11.0, 11.0, 6.0)
        assert r["text_edge_top_mm"] == 7.0
        assert r["indicator_size_mm"] == 3.88
        # **THE TURNED SIX KEEP THEIR DASHES**, and this line is what stops
        # them being taken away by a change to the cut they are built on:
        # `_CR30_HEX` now switches the markers OFF, `_cr30_preset` applies it
        # first, and dropping the `helper_markers: True` from `_CR30_STRAIGHT`
        # would silently disarm all six. Knut: *"The presets that end with
        # 'Hexagonal-Straight' keep their 'Print helper markers' ON with
        # 'Top/bottom' ON."*
        assert r["helper_markers"] is True
        assert r["helper_markers_top_bottom"] is True
        # Every one of the six is the same 18-column grid on both sheets.
        assert (r["area_cols"], r["area_rows"]) == (18, 28)


def test_the_two_low_patch_hex_charts_carry_the_larger_label():
    """Exactly two charts set a label size of their own, and it is 18 pt.

    `indicator_size_mm` is in OWN_FIELDS so those two may move it, and without
    this test that entry would let ANY row of the family set ANY size and stay
    green. Knut named the two and the size, 2026-09-16: 11.0 everywhere *"with
    exception of the two low patch presets with 153 and 170 patches"*, which
    get 18.0.

    The numbers are POINTS converted at the recipe boundary, because the Size
    box in "Strip and row indicators" is a point box: 11.0 pt is 3.88 mm and
    18.0 pt is 6.35 mm. He wrote "11.0mm" and "18.0mm" in the instruction and
    "11.0pt" a paragraph earlier about the same control, and the unit is
    settled by the shipped `_CR30_STRAIGHT`, which has carried 3.88 since
    2026-09-12 for the chart he pointed at as already correct.
    """
    from workflow import text_edge_fit as tef
    assert round(tef.pt_to_mm(11.0), 2) == 3.88
    assert round(tef.pt_to_mm(18.0), 2) == 6.35
    bigger = sorted(p.name for p in CR30
                    if p.layout_recipe["indicator_size_mm"] == 6.35)
    assert bigger == [
        "A4-153p-1page-Portrait-w18.0mm-Hexagonal",
        "Letter-170p-1page-Portrait-w16.0mm-Hexagonal",
    ]
    # NOBODY ELSE MOVES IT. Every other chart in the family is on 3.88 if it
    # is a honeycomb and on the base's "auto" if it is not, so a size typed
    # onto a row that should not have one is caught here rather than shipped.
    for q in CR30:
        if q.name in bigger:
            continue
        want = 3.88 if "Hexagonal" in q.name else 0.0
        assert q.layout_recipe["indicator_size_mm"] == want, q.name


def test_only_the_three_letter_hex_charts_move_a_margin_of_their_own():
    """The rest take the cut's margins untouched, so a stray margin cannot slip
    in unremarked."""
    moved = sorted(p.name for p in CR30
                   if (p.layout_recipe["margin_top"], p.layout_recipe["margin_bottom"])
                   # rectangular, hexagonal, turned: the three cuts' own pairs.
                   not in {(17.0, 12.0), (13.0, 13.0), (11.0, 6.0)})
    assert moved == [
        "Letter-1170p-3pages-Portrait-w11.0mm-Hexagonal",
        "Letter-390p-1page-Portrait-w11.0mm-Hexagonal",
        "Letter-780p-2pages-Portrait-w11.0mm-Hexagonal",
    ]
    for p in CR30:
        if p.name in moved:
            assert p.layout_recipe["margin_top"] == 11.0
            assert p.layout_recipe["margin_bottom"] == 9.0


def test_the_measured_shape_of_the_family():
    """What the sheet is cut for, written down rather than left implicit in
    twenty rows. A CR30 is a ROUND hand-held colorimeter set on one patch at a
    time, so this is a sheet for a hand and a ruler, not for a strip reader."""
    r = _CR30_BASE
    assert r["instrument"] == "CR30"
    assert r["margin_top"] == 17.0 and r["margin_bottom"] == 12.0
    assert r["margin_left"] == 15.0 and r["margin_right"] == 26.0
    assert r["use_instrument_margins"] is False
    # NO SPACERS AT ALL. Nothing is rolled along a row, so a coloured spacer
    # between patches would only cost sheet area.
    assert r["spacer_on"] is False
    assert r["spacer_mode"] == "none"
    assert r["edge_spacers"] is False
    assert r["spacer_width_mm"] == 0.0
    # The clip band: 26 mm down the RIGHT, flipped, carrying the notes box.
    assert r["clip_border"] is True
    assert r["clip_border_width_mm"] == 26.0
    assert r["clip_side"] == "right"
    assert r["clip_flip_180"] is True
    assert r["clip_content_mode"] == "notes"
    # Helper marks every third patch, top and bottom, for the ruler.
    assert r["helper_markers"] is True
    assert r["helper_marker_per_patch"] == 3
    assert r["helper_markers_top_bottom"] is True
    assert r["helper_markers_sides"] is False
    assert r["show_strip_indicators"] is True
    # Layout method and output.
    assert r["layout_mode"] == "area_first" and r["area_method"] == "by_grid"
    assert r["nolimit"] is True and r["randomize"] is True
    assert r["cm_density"] == 1          # a ColorMunki-only setting
    assert r["dpi"] == 200 and r["bit16"] is False


# ---------------------------------------------------------------------------
# Names tell the truth about the bundled files
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("preset", CR30, ids=lambda p: p.slug)
def test_name_matches_the_bundled_patch_set_and_the_grid(preset):
    m = _NAME_RE.match(preset.name)
    assert m, f"name does not follow the convention: {preset.name}"
    sheet, patches, pages, width, hexed, turned = PROMISED[preset.name]
    assert m.group("sheet") == sheet == preset.layout_recipe["paper"]
    assert int(m.group("patches")) == patches == preset.patches
    assert int(m.group("pages")) == pages == preset.pages
    assert float(m.group("width")) == width
    assert bool(m.group("hex")) == hexed == bool(preset.layout_recipe["hflag"])
    assert bool(m.group("straight")) == turned == bool(
        preset.layout_recipe.get("hex_flat_top"))

    ti1 = resource_path(preset.ti1_asset)
    assert ti1.is_file(), f"missing {preset.ti1_asset}"
    txt = ti1.read_text(encoding="latin-1", errors="ignore")
    assert int(re.search(r"NUMBER_OF_SETS\s+(\d+)", txt).group(1)) == preset.patches
    assert txt.count("NUMBER_OF_SETS") == 3      # all three tables of a targen .ti1

    cols = preset.layout_recipe["area_cols"]
    rows = preset.layout_recipe["area_rows"]
    assert -(-preset.patches // (cols * rows)) == preset.pages, (
        f"{cols}×{rows} per sheet does not put {preset.patches} patches on "
        f"{preset.pages} page(s)")


@pytest.mark.parametrize("preset", CR30, ids=lambda p: p.slug)
def test_sidecar_recipe_matches_its_chart(preset):
    """"Load setup from preset" seeds the New-chart window from this file. Knut
    designs a colour set once and lays it out on several sheets, so his exports
    carry whatever instrument and paper were on screen at design time. All
    twenty of these did (every one said "CM" or "i1"); the importer re-points
    them and this pins the result."""
    sidecar = resource_path(preset.ti1_asset).parent / "recipe.json"
    assert sidecar.is_file(), f"missing {sidecar}"
    rec = json.loads(sidecar.read_text(encoding="utf-8"))
    assert rec["instr"] == "CR30"
    assert rec["paper"] == preset.layout_recipe["paper"]
    assert rec["sp"]["fill_to"] == preset.patches
    layout = rec["layout"]
    assert layout["h"] is False                  # ColorMunki double density
    assert layout["td"] is False                 # triple density
    assert layout["dpi"] == 200
    assert layout["bit16"] is False


# ---------------------------------------------------------------------------
# A user preset of the same name is neither shadowed nor made undeletable
# ---------------------------------------------------------------------------

def test_a_user_preset_named_after_one_of_these_is_left_alone():
    """Basti has all twenty saved as ordinary Create Chart presets right now.
    Adding built-ins must not delete, hide or freeze them.

    The built-in is matched by its KEY (a sentinel) and listed under its own
    ``★ … · built-in`` label, so a user file called "CR30-A4-360p-1page-
    Portrait-w11.0mm" collides with neither. It stays listed above the built-ins
    and stays deletable."""
    from ui.tabs import tab_chart as tc
    for p in CR30:
        for candidate in (p.name, p.default_target_name, f"CR30-{p.name}"):
            assert candidate not in tc.BUILTIN_PRESET_KEYS
            assert candidate not in tc.BUILTIN_PRESET_LABELS


# ---------------------------------------------------------------------------
# Selecting one, and what the user is told
# ---------------------------------------------------------------------------

def test_tooltip_names_the_device_and_does_not_invent_a_run_up():
    """The generic engine tooltip tells the reader the wide band is "the run-up
    your instrument needs before the first patch". A CR30 has no run-up: it is
    set down on one patch at a time. Its band is the notes box, printed upside
    down because the sheet is turned to read it."""
    tip = TabChart._knut_tooltip(CR30[0].key)
    assert "cannot be deleted" in tip
    assert "CR30" in tip
    assert "run-up" not in tip
    assert "turn the sheet" in tip
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
    t = TabChart(ArgyllRunner(s), FileManager(s), s)
    t._switch_mode("manual")
    return t


def test_seeding_a_preset_puts_its_layout_on_the_panel(tab):
    """The engine path: selecting one seeds the layout panel, not the printtarg
    widgets, and the panel comes back with exactly this chart's recipe,
    hexagon flag included."""
    preset = next(p for p in CR30
                  if p.slug == "cr30_a4_420p_1page_portrait_w11_0mm_hexagonal")
    tab._seed_knut_preset(preset.key)
    got = tab._manual_layout_panel.get_recipe().to_dict()
    for field in ("instrument", "paper", "area_cols", "area_rows", "hflag",
                  "margin_top", "margin_bottom", "margin_left", "margin_right",
                  "clip_border_width_mm", "clip_side", "clip_content_mode",
                  "spacer_on", "helper_markers"):
        assert got[field] == preset.layout_recipe[field], field


def test_selecting_one_greys_targen_and_leaves_the_layout_editable(tab, monkeypatch):
    """Kind 3's contract: the patch set is fixed (targen locked), the layout is
    not (the engine panel stays editable)."""
    monkeypatch.setattr(TabChart, "_generate_from_ti1",
                        lambda self, ti1, ask=True: None)
    preset = next(p for p in CR30 if p.slug == "cr30_a4_360p_1page_portrait_w11_0mm")
    tab._apply_knut_preset(preset.key, "Probe")
    assert tab._knut_active is True
    assert tab._knut_active_key == preset.key
    assert tab._manual_targen_content, "the targen panel was never built"
    assert all(not w.isEnabled() for w in tab._manual_targen_content)
    assert tab._manual_layout_panel.isEnabled() is True


# ---------------------------------------------------------------------------
# It builds — every chart, on the real engine
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("preset", CR30, ids=lambda p: p.slug)
def test_chart_builds_with_the_pages_and_patches_its_name_promises(preset):
    from workflow.layout_engine.chart import build_from_recipe
    from workflow.layout_engine.presets import LayoutRecipe
    sheet, patches, pages, width, hexed, turned = PROMISED[preset.name]
    rec = LayoutRecipe.from_dict(preset.layout_recipe)
    assert rec.hflag is hexed
    with tempfile.TemporaryDirectory() as td:
        res, _ = build_from_recipe(resource_path(preset.ti1_asset),
                                   Path(td) / "chart", rec)
        tiffs = sorted(Path(td).glob("chart*.tif"))
        assert len(tiffs) == pages, "the name promises this many sheets"
        # Nothing is padded out with white: the grid holds the patch set exactly.
        assert res.layout.total_patches == patches
        # THE PATCH, NOT THE STRIP. A honeycomb's strip is wider than one of its
        # patches (the rows interlock), so measuring the strip reads a hexagonal
        # chart ~0.13 mm too wide. This is the rect the engine writes into the
        # chart's own `.strips.json`, which the app copies into the run's
        # `.channels.json` and "Patch width" then shows on screen.
        #
        # …AND ACROSS THE FLATS, which on a turned honeycomb is the slot's
        # HEIGHT: see the module docstring.
        blob = json.loads((Path(td) / "chart.strips.json")
                          .read_text(encoding="utf-8"))
        got = _across_the_flats_mm(blob["patches"][0], blob["dpi"], turned)
    if preset.name in WIDTH_EXCEPTIONS:
        # Knut's own layout rounds these two names down; pinned at what the
        # sheet really prints so a change at either end is caught.
        assert abs(got - WIDTH_EXCEPTIONS[preset.name]) <= 0.05, (
            f"{preset.name} now prints {got:.2f} mm patches")
    else:
        assert abs(got - width) <= 0.5, (
            f"name says {width} mm patches, the sheet has {got:.2f} mm")
