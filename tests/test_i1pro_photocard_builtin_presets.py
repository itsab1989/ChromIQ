"""Knut's i1Pro PHOTO-CARD built-in presets (2026-09-09, grown 2026-09-17).

FIFTEEN charts, on the two sheets a photo lab prints: 10 x 15 cm and
13 x 18 cm. His words, sending the first two:

    *"Here are both the preset for the 10x15cm and 13x18cm charts. I had to
    adjust the margins a bit to assure space for starting and ending a strip
    reading. Thus the measurements are very slightly different from the
    original pharmacist presets."*

THIRTEEN MORE ARRIVED ON 2026-09-17 (issue #182): *"I also created a few more
presets to be added as built-in as the other built-in presets."* Eleven new
patch counts on the same two cards, from 720 up to 1512, and with them the
family's FIRST second cut — seven charts named "Maximised - No Clip-border",
which are this same design with the clip band switched off and both side
margins pulled in to 5 mm. That buys two more columns on the small card and
four on the large one at the same patch width. `_I1_PHOTO_MAXIMISED` is what
`maximised=True` stands for, and the tests below pin that it stands for those
two fields and nothing else: a cut that quietly carried a margin as well would
re-cut charts nobody looked at.

They stand BESIDE the two "by Pharmacist" photo cards under the same i1Pro
heading and replace neither: those are prebuilt files copied into the run, these
are laid out by the ChromIQ engine with his wider margins.

WHAT THESE TESTS ARE FOR. A shared base recipe changes every chart that hangs
off it at once and silently, and this change added a THIRD i1Pro base beside two
that carry nineteen shipping charts each. So these things are pinned here:

 1. ``_I1_PHOTO_BASE`` differs from ``_I1_BASE`` in exactly ten fields and holds
    no margin at all (no two cards share a sheet-scaled number, so there is
    nothing honest to inherit and ``_i1_photo_preset`` requires all five);
 2. ``_I1_BASE`` and ``_I1_75_BASE`` still say what they said, in each of those
    ten fields, so this family cannot have been folded into either;
 3. ``_I1_PHOTO_MAXIMISED`` moves exactly two fields, and only the seven charts
    whose NAME says so take it;
 4. every chart is registered, non-deletable, still has its bundled ``.ti1``
    and its ``recipe.json`` sidecar on disk, and is actually BUILT and counted
    against the name it carries.

ONE NAME IS SHORT OF A TOKEN, AND IT IS KNUT'S. Every other chart in the app
spells its orientation out; ``130x180mm-648p-3pages-w8.0mm`` does not. The sheet
IS portrait (130 mm wide by 180 tall) and the layout is portrait, so nothing is
wrong on paper. It is pinned as it is rather than quietly re-spelled: what a
chart is called is his call. Flagged for him.
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
    _I1_75_BASE, _I1_BASE, _I1_PHOTO_BASE, _I1_PHOTO_CLIP_TEXT,
    _I1_PHOTO_MAXIMISED, _I1_PHOTO_PER_SHEET, BUILTIN_PRESET_GROUPS,
    BUILTIN_PRESET_KEYS, BUILTIN_PRESET_LABELS, KNUT_PRESETS, TabChart,
    builtin_preset_recipe,
)

PHOTO = [p for p in KNUT_PRESETS if p.slug.startswith("i1_photo_")]

#: The tail his "Maximised" charts carry, verbatim. The NAME is the authority
#: on which cut a chart takes: a row that took the cut without saying so in its
#: name, or said so without taking it, is the fault these tests exist to catch.
MAXIMISED_TAIL = "-Maximised-No Clip-border"

#: Exactly the fields one chart of this family may set for itself: the sheet,
#: the grid, and the five numbers that scale with the sheet. A photo card is a
#: quarter of an A4 and the two cards are not even the same shape, so not one
#: margin is shared between them. The two fields the "Maximised" cut moves are
#: NOT here — they are a named cut, not a per-chart choice, which is what
#: ``effective_base`` below expresses.
OWN_FIELDS = {"paper", "area_cols", "area_rows", *_I1_PHOTO_PER_SHEET}


def effective_base(preset) -> dict:
    """The recipe this chart's row should have started from: the family base,
    plus the "Maximised" cut where the chart's NAME says it takes it."""
    base = dict(_I1_PHOTO_BASE)
    if preset.name.endswith(MAXIMISED_TAIL):
        base.update(_I1_PHOTO_MAXIMISED)
    return base

#: What the base moves away from ``_I1_BASE``, and all it moves. Ten fields,
#: identical on both cards — a design, which is why it is a base and not a pair
#: of per-chart overrides. Written out as (photo, 8 mm) so the test reads both
#: ends and a change to EITHER is caught.
BASE_DELTA = {
    "area_min_patch_mm":     (17.5, 0.0),
    "border":                (10.0, 6.0),
    "edge_spacers":          (False, True),
    "helper_marker_edge_mm": (2.0, 4.0),
    "indicator_size_mm":     (0.0, 4.23),
    "nolimit":               (False, True),
    "pscale":                (0.95, 1.0),
    "sscale":                (0.6, 0.8),
    "text_edge_top_mm":      (4.0, 8.0),
    "clip_text":             (_I1_PHOTO_CLIP_TEXT, ""),
}

_NAME_RE = re.compile(
    r"^(?P<sheet>\d+x\d+)mm-(?P<patches>\d+)p-(?P<pages>\d+)pages?-"
    r"(?:(?P<orientation>Portrait|Landscape)-)?w(?P<width>[\d.]+)mm"
    r"(?P<maximised>-Maximised-No Clip-border)?$")

#: What each name promises, transcribed from the fifteen filenames Knut sent:
#: (paper code, patches, pages, patch width mm, orientation token or None).
PROMISED = {
    "100x150mm-600p-4pages-Portrait-w7.5mm":
        ("100x150", 600, 4, 7.5, "Portrait"),
    "100x150mm-720p-4pages-Portrait-w7.5mm-Maximised-No Clip-border":
        ("100x150", 720, 4, 7.5, "Portrait"),
    "100x150mm-900p-6pages-Portrait-w7.5mm":
        ("100x150", 900, 6, 7.5, "Portrait"),
    "100x150mm-1080p-6pages-Portrait-w7.5mm-Maximised-No Clip-border":
        ("100x150", 1080, 6, 7.5, "Portrait"),
    "100x150mm-1200p-8pages-Portrait-w7.5mm":
        ("100x150", 1200, 8, 7.5, "Portrait"),
    "100x150mm-1260p-7pages-Portrait-w7.5mm-Maximised-No Clip-border":
        ("100x150", 1260, 7, 7.5, "Portrait"),
    "100x150mm-1440p-8pages-Portrait-w7.5mm-Maximised-No Clip-border":
        ("100x150", 1440, 8, 7.5, "Portrait"),
    "100x150mm-1500p-10pages-Portrait-w7.5mm":
        ("100x150", 1500, 10, 7.5, "Portrait"),
    "130x180mm-648p-3pages-w8.0mm":
        ("130x180", 648, 3, 8.0, None),
    "130x180mm-864p-3pages-Portrait-w7.5mm-Maximised-No Clip-border":
        ("130x180", 864, 3, 7.5, "Portrait"),
    "130x180mm-1080p-5pages-Portrait-w8.0mm":
        ("130x180", 1080, 5, 8.0, "Portrait"),
    "130x180mm-1152p-4pages-Portrait-w7.5mm-Maximised-No Clip-border":
        ("130x180", 1152, 4, 7.5, "Portrait"),
    "130x180mm-1296p-6pages-Portrait-w8.0mm":
        ("130x180", 1296, 6, 8.0, "Portrait"),
    "130x180mm-1440p-5pages-Portrait-w7.5mm-Maximised-No Clip-border":
        ("130x180", 1440, 5, 7.5, "Portrait"),
    "130x180mm-1512p-7pages-Portrait-w8.0mm":
        ("130x180", 1512, 7, 8.0, "Portrait"),
}

#: The five sheet-scaled numbers, per chart, exactly as his exports carry them.
#: Spelled out here rather than read off the rows, so a row that drifts from
#: what he sent cannot drift past this table too.
#:
#: Read down a column and the cut shows itself: every "Maximised" chart carries
#: 5 mm on BOTH sides where a standard one carries the clip band's width on the
#: left (19 or 26) and 5 or 7 on the right, and it still carries the band's
#: width, because the band is off and the number is unused.
_SMALL = dict(margin_top=17.0, margin_bottom=13.0, clip_border_width_mm=19.0)
_LARGE = dict(margin_top=19.5, margin_bottom=13.5, clip_border_width_mm=26.0)
_SMALL_SIDES = dict(margin_left=19.0, margin_right=5.0)
_LARGE_SIDES = dict(margin_left=26.0, margin_right=7.0)
_MAX_SIDES = dict(margin_left=5.0, margin_right=5.0)

MARGINS = {
    "100x150mm-600p-4pages-Portrait-w7.5mm": {**_SMALL, **_SMALL_SIDES},
    "100x150mm-720p-4pages-Portrait-w7.5mm-Maximised-No Clip-border":
        {**_SMALL, **_MAX_SIDES},
    "100x150mm-900p-6pages-Portrait-w7.5mm": {**_SMALL, **_SMALL_SIDES},
    "100x150mm-1080p-6pages-Portrait-w7.5mm-Maximised-No Clip-border":
        {**_SMALL, **_MAX_SIDES},
    "100x150mm-1200p-8pages-Portrait-w7.5mm": {**_SMALL, **_SMALL_SIDES},
    "100x150mm-1260p-7pages-Portrait-w7.5mm-Maximised-No Clip-border":
        {**_SMALL, **_MAX_SIDES},
    "100x150mm-1440p-8pages-Portrait-w7.5mm-Maximised-No Clip-border":
        {**_SMALL, **_MAX_SIDES},
    "100x150mm-1500p-10pages-Portrait-w7.5mm": {**_SMALL, **_SMALL_SIDES},
    "130x180mm-648p-3pages-w8.0mm": {**_LARGE, **_LARGE_SIDES},
    "130x180mm-864p-3pages-Portrait-w7.5mm-Maximised-No Clip-border":
        {**_LARGE, **_MAX_SIDES},
    "130x180mm-1080p-5pages-Portrait-w8.0mm": {**_LARGE, **_LARGE_SIDES},
    "130x180mm-1152p-4pages-Portrait-w7.5mm-Maximised-No Clip-border":
        {**_LARGE, **_MAX_SIDES},
    "130x180mm-1296p-6pages-Portrait-w8.0mm": {**_LARGE, **_LARGE_SIDES},
    "130x180mm-1440p-5pages-Portrait-w7.5mm-Maximised-No Clip-border":
        {**_LARGE, **_MAX_SIDES},
    "130x180mm-1512p-7pages-Portrait-w8.0mm": {**_LARGE, **_LARGE_SIDES},
}

#: The grid each chart lays its patches out on, transcribed from his exports.
#: This is where the "Maximised" cut is worth the paper: the same card, the
#: same patch width, two more columns on the small one and four on the large.
GRID = {
    "100x150": {False: (10, 15), True: (12, 15)},
    "130x180": {False: (12, 18), True: (16, 18)},
}


# ---------------------------------------------------------------------------
# Registered, and filed with the other i1Pro charts
# ---------------------------------------------------------------------------

def test_every_chart_registered():
    """EXACT, deliberately. A preset that goes missing — a row deleted, a slug
    renamed, an asset folder lost — is invisible in a dropdown of 173 entries
    and would reach a user as "the chart I had is gone". The count and the
    names are both pinned so it cannot happen quietly."""
    assert len(PHOTO) == 15
    assert len({p.slug for p in PHOTO}) == 15        # slugs are the identity
    assert {p.name for p in PHOTO} == set(PROMISED)
    assert all(p.key in BUILTIN_PRESET_KEYS for p in PHOTO)
    assert all(p.combo_label in BUILTIN_PRESET_LABELS for p in PHOTO)


def test_the_cut_is_taken_by_exactly_the_charts_whose_name_says_so():
    """Seven of the fifteen are "Maximised - No Clip-border", and the name is
    the promise: the band is off on exactly those, and on on the other eight."""
    named = {p.name for p in PHOTO if p.name.endswith(MAXIMISED_TAIL)}
    assert len(named) == 7
    for p in PHOTO:
        off = p.layout_recipe["clip_border"] is False
        assert off == (p.name in named), (
            f"{p.name}: the name and the clip band disagree")


def test_no_chart_of_this_family_can_be_deleted(tab):
    """A built-in is protected by its KEY being in ``BUILTIN_PRESET_KEYS``, and
    the Delete button reads exactly that. Driven through the real combo rather
    than asserted on the set, so a preset that reached the dropdown by some
    other door would still be caught."""
    combo = tab._preset_combo
    keys = {p.key for p in PHOTO}
    seen = set()
    for i in range(combo.count()):
        data = combo.itemData(i)
        if data in keys:
            seen.add(data)
            assert tab._is_deletable_preset(i) is False, combo.itemText(i)
    assert seen == keys, f"not in the dropdown: {sorted(keys - seen)}"


def test_keys_are_stable_sentinels():
    for p in PHOTO:
        assert p.key == f"__chromiq_knut_{p.slug}__"


def test_they_are_i1pro_charts_not_a_family_of_their_own():
    """Cut for the original i1Pro, so they belong under the heading an i1Pro
    owner reads, next to the two Pharmacist photo cards. Only the BASE recipe
    is separate; the group is not."""
    for p in PHOTO:
        assert p.group == ""
        assert p.file_group == "i1Pro"
        assert p.display_group == INSTRUMENT_LABELS["i1"]
        assert p.instrument == "i1"
        assert p.layout_recipe["instrument"] == "i1"
    entries = dict(BUILTIN_PRESET_GROUPS)[INSTRUMENT_LABELS["i1"]]
    keys = [k for (_c, _o, k) in entries]
    assert all(p.key in keys for p in PHOTO)


def test_they_sit_beside_the_pharmacist_photo_cards():
    """Basti: the two cards go under the existing i1Pro heading, beside the
    Pharmacist ones, which stay exactly as they are.

    All SEVEN Pharmacist rows are hard-coded at the head of the group and the
    Knut rows are appended after them in ``_paper_sort_key`` order, so the
    photo cards land at the head of the Knut block — before every A4 chart he
    ever exported. Both halves are pinned: the two prebuilt photo cards still
    open the group, and all fifteen of his open the Knut block, unbroken.
    """
    entries = dict(BUILTIN_PRESET_GROUPS)[INSTRUMENT_LABELS["i1"]]
    overlays = [o for (_c, o, _k) in entries]
    keys = [k for (_c, _o, k) in entries]
    # The Pharmacist block did not move: its two photo cards still open it.
    assert overlays[:2] == ["10x15cm-600p-4pages by Pharmacist",
                            "13x18cm-648p-3pages by Pharmacist"]
    knut = {p.key for p in KNUT_PRESETS}
    first_knut = next(i for i, k in enumerate(keys) if k in knut)
    photo = {p.key for p in PHOTO}
    block = keys[first_knut:first_knut + len(PHOTO)]
    assert set(block) == photo, "the photo cards no longer open the Knut block"
    # The small card comes before the large one (the sort is area-based), and
    # the very first of his is still the 600-patch chart he sent in September.
    assert overlays[first_knut] == "100x150mm-600p-4pages-Portrait-w7.5mm"
    assert [o[:7] for o in overlays[first_knut:first_knut + len(PHOTO)]] == (
        ["100x150"] * 8 + ["130x180"] * 7)
    # …and every Knut chart after them is on a named sheet (A4 / Letter / A3),
    # so nothing of his is left stranded between the cards and the A4 block.
    assert all(not o[0].isdigit()
               for o in overlays[first_knut + len(PHOTO):])


def test_each_row_carries_the_full_layout_setup_marker():
    """The marker follows ``builtin_preset_recipe`` (a shipped recipe.json
    sidecar), so each earns it by carrying the colour-set design the patch-set
    editor can load."""
    for p in PHOTO:
        assert p.has_full_layout_setup, p.name
        assert p.marked_name == p.name + " · Full layout setup"
        assert p.combo_label == f"★  i1Pro · {p.marked_name}  ·  built-in"
        # The suggested PROJECT FOLDER keeps the sortable #68 convention and
        # never carries the marker.
        assert p.default_target_name.startswith("i1Pro-")
        assert "Full layout setup" not in p.default_target_name


# ---------------------------------------------------------------------------
# A third i1Pro base, and the two it must not have touched
# ---------------------------------------------------------------------------

def test_the_base_moves_exactly_ten_fields_away_from_the_8mm_one():
    """Ten fields, identical on both cards, none of them in any i1Pro
    ``varying`` set. That is why this is a base and not two rows on an existing
    family: folding it in would have re-cut nineteen shipping charts."""
    moved = {k for k in set(_I1_BASE) & set(_I1_PHOTO_BASE)
             if _I1_BASE[k] != _I1_PHOTO_BASE[k]}
    assert moved == set(BASE_DELTA)
    for field, (photo, eight) in BASE_DELTA.items():
        assert _I1_PHOTO_BASE[field] == photo, field
        assert _I1_BASE[field] == eight, f"_I1_BASE moved: {field}"


def test_the_75mm_base_is_untouched_too():
    """``_I1_75_BASE`` derives from ``_I1_BASE``, so it inherits nine of the ten
    and sets ``sscale`` itself. Pinned at both ends for the same reason."""
    for field, (_photo, eight) in BASE_DELTA.items():
        expected = 0.75 if field == "sscale" else eight
        assert _I1_75_BASE[field] == expected, f"_I1_75_BASE moved: {field}"
    assert _I1_75_BASE["margin_right"] == 4.0
    assert _I1_BASE["margin_right"] == 6.0


def test_the_base_holds_no_sheet_scaled_number():
    """The point of the family. There is no shared margin between a 10 x 15 cm
    card and a 13 x 18 cm one, so the base carries none and a row cannot
    silently inherit an A4 jig's 38 mm top margin onto a photo card."""
    assert set(_I1_PHOTO_PER_SHEET) == {
        "margin_top", "margin_right", "margin_bottom", "margin_left",
        "clip_border_width_mm"}
    for field in _I1_PHOTO_PER_SHEET:
        assert field not in _I1_PHOTO_BASE, field
        assert field in _I1_BASE, f"{field} is no longer an _I1_BASE field"
    # …and the helper therefore has no default to fall back to.
    import inspect
    from ui.tabs.tab_chart import _i1_photo_preset
    sig = inspect.signature(_i1_photo_preset)
    for field in _I1_PHOTO_PER_SHEET:
        par = sig.parameters[field]
        assert par.kind is inspect.Parameter.KEYWORD_ONLY, field
        assert par.default is inspect.Parameter.empty, (
            f"{field} has a default — a card could inherit a margin silently")


def test_the_clip_note_is_shared_with_the_cr30_family_verbatim():
    """Byte-for-byte the note the CR30 charts carry, so it is one constant
    rather than a second copy that can drift. It has the same flaw there and
    here: the numbers in it describe a jig neither family uses. Carried as Knut
    exported it, because what a chart prints on paper is his call."""
    from ui.tabs.tab_chart import _CR30_CLIP_TEXT
    assert _I1_PHOTO_CLIP_TEXT is _CR30_CLIP_TEXT
    assert _I1_PHOTO_BASE["clip_text"] == _CR30_CLIP_TEXT
    assert "Top margin: 34 mm" in _I1_PHOTO_CLIP_TEXT


def test_the_maximised_cut_moves_exactly_two_fields():
    """What ``maximised=True`` stands for, stated once. The cut is the clip
    band off and NOTHING else — the wider side margins those cards gain are two
    of the five sheet-scaled numbers every row of this family already spells
    out, so folding them in here would hide a per-card number inside a family
    flag. That is precisely what ``_I1_PHOTO_PER_SHEET`` exists to prevent."""
    assert _I1_PHOTO_MAXIMISED == {"clip_border": False,
                                   "clip_content_mode": "off"}
    # The base it is applied over says the opposite, so the cut really cuts.
    assert _I1_PHOTO_BASE["clip_border"] is True
    assert _I1_PHOTO_BASE["clip_content_mode"] == "notes"
    assert not set(_I1_PHOTO_MAXIMISED) & set(_I1_PHOTO_PER_SHEET)


@pytest.mark.parametrize("preset", PHOTO, ids=lambda p: p.slug)
def test_recipe_differs_from_the_base_only_where_allowed(preset):
    rec = preset.layout_recipe
    assert rec is not None, "the family is engine-built, not printtarg"
    base = effective_base(preset)
    assert set(rec) == set(_I1_PHOTO_BASE) | OWN_FIELDS
    for field in set(base) - OWN_FIELDS:
        assert rec[field] == base[field], (
            f"{preset.slug} changes {field}, which the family shares")


@pytest.mark.parametrize("preset", PHOTO, ids=lambda p: p.slug)
def test_each_chart_lays_out_on_the_grid_his_export_carries(preset):
    """The grid is where the cut pays: same card, same patch width, two more
    columns on the small card and four on the large one."""
    cols, rows = GRID[preset.layout_recipe["paper"]][
        preset.name.endswith(MAXIMISED_TAIL)]
    assert (preset.layout_recipe["area_cols"],
            preset.layout_recipe["area_rows"]) == (cols, rows)


@pytest.mark.parametrize("preset", PHOTO, ids=lambda p: p.slug)
def test_each_card_carries_the_margins_knut_sent(preset):
    for field, value in MARGINS[preset.name].items():
        assert preset.layout_recipe[field] == value, field


def test_the_two_cards_share_no_sheet_scaled_number():
    """Stated as a fact about the family, not just implied by the table above:
    every one of the five really does differ between the two cards, which is
    what makes ``always`` in the importer the honest emitter for this batch.

    Compared on the STANDARD cut of each card, because that is the design the
    base was measured against; the maximised cut deliberately puts 5 mm on both
    sides of both cards, so two of the five agree there by construction."""
    a = MARGINS["100x150mm-600p-4pages-Portrait-w7.5mm"]
    b = MARGINS["130x180mm-648p-3pages-w8.0mm"]
    for field in _I1_PHOTO_PER_SHEET:
        assert a[field] != b[field], f"{field} agrees; it belongs in the base"


# ---------------------------------------------------------------------------
# Names tell the truth about the bundled files
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("preset", PHOTO, ids=lambda p: p.slug)
def test_name_matches_the_bundled_patch_set_and_the_grid(preset):
    m = _NAME_RE.match(preset.name)
    assert m, f"name does not follow the convention: {preset.name}"
    paper, patches, pages, width, orientation = PROMISED[preset.name]
    # A "<W>x<H>mm" name token says the sheet outright, unlike the named ones
    # (the i1Pro A3 charts store "420x297" and call themselves "A3"), so the
    # name and the layout can be held to each other.
    assert m.group("sheet") == paper == preset.layout_recipe["paper"]
    assert int(m.group("patches")) == patches == preset.patches
    assert int(m.group("pages")) == pages == preset.pages
    assert float(m.group("width")) == width == preset.patch_width_mm
    assert m.group("orientation") == orientation
    assert bool(m.group("maximised")) == preset.name.endswith(MAXIMISED_TAIL)

    ti1 = resource_path(preset.ti1_asset)
    assert ti1.is_file(), f"missing {preset.ti1_asset}"
    txt = ti1.read_text(encoding="latin-1", errors="ignore")
    assert int(re.search(r"NUMBER_OF_SETS\s+(\d+)", txt).group(1)) == patches
    assert txt.count("NUMBER_OF_SETS") == 3   # all three tables of a targen .ti1

    cols = preset.layout_recipe["area_cols"]
    rows = preset.layout_recipe["area_rows"]
    assert -(-patches // (cols * rows)) == pages, (
        f"{cols}×{rows} per sheet does not put {patches} patches on "
        f"{pages} page(s)")


def test_the_13x18_name_carries_no_orientation_token_and_that_is_his():
    """Every other chart in the app spells its orientation out. This one does
    not, and the sheet it lays out is portrait all the same (130 mm wide by 180
    tall). Pinned as it is rather than re-spelled: the name is Knut's. If it is
    ever corrected, this test says so instead of the change passing unnoticed.
    """
    from workflow.layout_engine import papers
    p = next(q for q in PHOTO if q.name == "130x180mm-648p-3pages-w8.0mm")
    assert "Portrait" not in p.name and "Landscape" not in p.name
    w, h = papers.dimensions_mm(p.layout_recipe["paper"])
    assert (w, h) == (130.0, 180.0) and h > w, "the sheet is portrait"
    # …and the other one does spell it out, so this is one name, not a policy.
    other = next(q for q in PHOTO if q is not p)
    assert "Portrait" in other.name


def test_every_chart_still_has_its_bundled_files_and_nothing_else_is_there():
    """A preset whose ``.ti1`` is gone is a preset that builds nothing, and the
    failure arrives at Generate time rather than at import time. Both halves are
    pinned: every row has its two files under its own slug, and the asset folder
    holds no leaf that no row points at (a rename that staged a second copy
    would otherwise sit there unnoticed, shipped in the bundle)."""
    leaves = set()
    for p in PHOTO:
        ti1 = resource_path(p.ti1_asset)
        assert ti1.is_file(), f"{p.slug}: missing {p.ti1_asset}"
        assert ti1.stat().st_size > 0, f"{p.slug}: empty .ti1"
        sidecar = ti1.parent / "recipe.json"
        assert sidecar.is_file(), f"{p.slug}: missing recipe.json"
        assert ti1.parent.name == p.slug, (
            f"{p.slug}: the asset folder is named {ti1.parent.name!r}")
        leaves.add(ti1.parent)
    root = next(iter(leaves)).parent
    on_disk = {d for d in root.iterdir() if d.is_dir()}
    assert on_disk == leaves, (
        f"asset folders no row points at: "
        f"{sorted(d.name for d in on_disk - leaves)}")


@pytest.mark.parametrize("preset", PHOTO, ids=lambda p: p.slug)
def test_sidecar_recipe_matches_its_chart(preset):
    """"Load setup from preset" seeds the New-chart window from this file. Both
    of Knut's exports carried ``paper: "A4"`` and one of them ``fill_to: 600``
    beside a 648-patch chart, from the design they were cloned out of; the
    importer re-points them and this pins the result."""
    sidecar = resource_path(preset.ti1_asset).parent / "recipe.json"
    assert sidecar.is_file(), f"missing {sidecar}"
    rec = json.loads(sidecar.read_text(encoding="utf-8"))
    assert rec["instr"] == "i1"
    assert rec["paper"] == preset.layout_recipe["paper"]
    assert rec["sp"]["fill_to"] == preset.patches
    assert (rec["paper_w"], rec["paper_h"]) == tuple(
        int(x) for x in preset.layout_recipe["paper"].split("x"))
    layout = rec["layout"]
    assert layout["h"] is False                  # ColorMunki double density
    assert layout["td"] is False                 # triple density
    assert layout["dpi"] == 200
    assert layout["bit16"] is False
    # The editor can find it through the same door the New-chart window uses.
    assert builtin_preset_recipe(preset.key) == rec


# ---------------------------------------------------------------------------
# Selecting one, and what the user is told
# ---------------------------------------------------------------------------

def test_tooltip_describes_an_engine_chart_on_the_card_it_is_cut_for():
    tip = TabChart._knut_tooltip(PHOTO[0].key)
    assert "cannot be deleted" in tip
    assert "600-patch" in tip and "i1Pro" in tip
    assert "100x150" in tip and "4 pages" in tip
    assert "7.5mm patches" in tip
    assert "helper marks" in tip
    # It IS a strip reader, so the run-up wording is the right one here.
    assert "run-up" in tip


def test_a_maximised_chart_is_not_promised_a_band_it_does_not_print():
    """The shared engine tooltip describes the wide band as "the run-up your
    instrument needs before the first patch". A "Maximised - No Clip-border"
    chart prints no band at all, so that sentence would be a promise the sheet
    does not keep. It is already gated on the band being on; pinned here,
    because this family is the first to ship a chart with it off."""
    off = next(p for p in PHOTO if p.name.endswith(MAXIMISED_TAIL))
    tip = TabChart._knut_tooltip(off.key)
    assert "run-up" not in tip
    assert "band" not in tip
    # …and it still says the things that ARE true of it.
    assert "cannot be deleted" in tip
    assert f"{off.patches}-patch" in tip and "i1Pro" in tip
    assert off.layout_recipe["paper"] in tip


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


@pytest.mark.parametrize("preset", PHOTO, ids=lambda p: p.slug)
def test_seeding_a_preset_puts_its_layout_on_the_panel(tab, preset):
    """The engine path: selecting one seeds the layout panel, not the printtarg
    widgets. A photo card is a CUSTOM paper code, which the panel reaches
    through its "Custom…" entry, so the round trip is worth pinning here rather
    than assuming the named sizes' behaviour carries over."""
    tab._seed_knut_preset(preset.key)
    got = tab._manual_layout_panel.get_recipe().to_dict()
    assert got["paper"] == preset.layout_recipe["paper"]
    for field in sorted(preset.layout_recipe):
        assert got[field] == preset.layout_recipe[field], field


def test_selecting_one_greys_targen_and_leaves_the_layout_editable(tab, monkeypatch):
    """Kind 3's contract: the patch set is fixed (targen locked), the layout is
    not (the engine panel stays editable)."""
    monkeypatch.setattr(TabChart, "_generate_from_ti1",
                        lambda self, ti1, ask=True: None)
    preset = PHOTO[0]
    tab._apply_knut_preset(preset.key, "Probe")
    assert tab._knut_active is True
    assert tab._knut_active_key == preset.key
    assert tab._manual_targen_content, "the targen panel was never built"
    assert all(not w.isEnabled() for w in tab._manual_targen_content)
    assert tab._manual_layout_panel.isEnabled() is True


def test_a_user_preset_named_after_one_of_these_is_left_alone():
    """Adding built-ins must not delete, hide or freeze a user's own preset of
    the same name. The built-in is matched by its KEY (a sentinel) and listed
    under its own ``★ … · built-in`` label, so neither collides."""
    from ui.tabs import tab_chart as tc
    for p in PHOTO:
        for candidate in (p.name, p.default_target_name, f"i1Pro-{p.name}"):
            assert candidate not in tc.BUILTIN_PRESET_KEYS
            assert candidate not in tc.BUILTIN_PRESET_LABELS


# ---------------------------------------------------------------------------
# It builds — both charts, on the real engine
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("preset", PHOTO, ids=lambda p: p.slug)
def test_chart_builds_with_the_sheet_pages_and_patches_its_name_promises(preset):
    from workflow.layout_engine import papers
    from workflow.layout_engine.chart import build_from_recipe
    from workflow.layout_engine.presets import LayoutRecipe
    paper, patches, pages, width, _orientation = PROMISED[preset.name]
    rec = LayoutRecipe.from_dict(preset.layout_recipe)
    with tempfile.TemporaryDirectory() as td:
        res, _ = build_from_recipe(resource_path(preset.ti1_asset),
                                   Path(td) / "chart", rec)
        tiffs = sorted(Path(td).glob("chart*.tif"))
        assert len(tiffs) == pages, "the name promises this many sheets"
        # Nothing is padded out with white: the grid holds the patch set exactly.
        assert res.layout.total_patches == patches
        blob = json.loads((Path(td) / "chart.strips.json")
                          .read_text(encoding="utf-8"))
        got = blob["patches"][0]["w"] * 25.4 / blob["dpi"]
        # Every patch on every sheet must sit inside the card.
        sheet_w, sheet_h = papers.dimensions_mm(paper)
        dpi = blob["dpi"]
        for q in blob["patches"]:
            assert 0 <= q["x"] and (q["x"] + q["w"]) * 25.4 / dpi <= sheet_w + 0.01
            assert 0 <= q["y"] and (q["y"] + q["h"]) * 25.4 / dpi <= sheet_h + 0.01
        assert len(blob["patches"]) == patches
    assert abs(got - width) <= 0.5, (
        f"name says {width} mm patches, the sheet has {got:.2f} mm")
