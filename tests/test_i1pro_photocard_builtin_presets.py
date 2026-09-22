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

 1. ``_I1_PHOTO_BASE`` differs from ``_I1_BASE`` in exactly twelve fields and
    holds no margin at all (no two cards share a sheet-scaled number, so there is
    nothing honest to inherit and ``_i1_photo_preset`` requires all five);
 2. ``_I1_BASE`` and ``_I1_75_BASE`` still say what they said, in each of those
    twelve fields, so this family cannot have been folded into either;
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

#: What the base moves away from ``_I1_BASE``, and all it moves. Twelve fields,
#: identical on every card — a design, which is why it is a base and not a set
#: of per-chart overrides. Written out as (photo, 8 mm) so the test reads both
#: ends and a change to EITHER is caught.
#:
#: The last two arrived on 2026-09-18 with Knut's *"All the built-in
#: 'i1Pro-100x150mm…' presets (including the new once) need the following
#: included in the saved settings"*: the sheet text at 6.0 pt and the clip
#: distance at 2.0 mm, on every chart of both card sizes.
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
    "chart_text_size_mm":    (2.12, 0.0),
    "text_edge_clip_mm":     (2.0, 4.0),
}

_NAME_RE = re.compile(
    r"^(?P<sheet>\d+x\d+)mm-(?P<patches>\d+)p-(?P<pages>\d+)pages?-"
    r"(?:(?P<orientation>Portrait|Landscape)-)?w(?P<width>[\d.]+)mm"
    r"(?P<maximised>-Maximised-No Clip-border)?$")

#: What each name promises, transcribed from the nineteen filenames Knut sent:
#: (paper code, patches, pages, patch width mm, orientation token or None).
PROMISED = {
    "100x150mm-150p-1page-Portrait-w7.5mm":
        ("100x150", 150, 1, 7.5, "Portrait"),
    "100x150mm-180p-1page-Portrait-w7.5mm-Maximised-No Clip-border":
        ("100x150", 180, 1, 7.5, "Portrait"),
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
    "130x180mm-216p-1page-Portrait-w8.0mm":
        ("130x180", 216, 1, 8.0, "Portrait"),
    "130x180mm-288p-1page-Portrait-w7.5mm-Maximised-No Clip-border":
        ("130x180", 288, 1, 7.5, "Portrait"),
    "130x180mm-648p-3pages-Portrait-w8.0mm":
        ("130x180", 648, 3, 8.0, "Portrait"),
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
    "100x150mm-150p-1page-Portrait-w7.5mm": {**_SMALL, **_SMALL_SIDES},
    "100x150mm-180p-1page-Portrait-w7.5mm-Maximised-No Clip-border":
        {**_SMALL, **_MAX_SIDES},
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
    "130x180mm-216p-1page-Portrait-w8.0mm": {**_LARGE, **_LARGE_SIDES},
    "130x180mm-288p-1page-Portrait-w7.5mm-Maximised-No Clip-border":
        {**_LARGE, **_MAX_SIDES},
    "130x180mm-648p-3pages-Portrait-w8.0mm": {**_LARGE, **_LARGE_SIDES},
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
    assert len(PHOTO) == 19
    assert len({p.slug for p in PHOTO}) == 19        # slugs are the identity
    assert {p.name for p in PHOTO} == set(PROMISED)
    assert all(p.key in BUILTIN_PRESET_KEYS for p in PHOTO)
    assert all(p.combo_label in BUILTIN_PRESET_LABELS for p in PHOTO)


def test_the_cut_is_taken_by_exactly_the_charts_whose_name_says_so():
    """Nine of the nineteen are "Maximised - No Clip-border", and the name is
    the promise: the band is off on exactly those, and on on the other ten."""
    named = {p.name for p in PHOTO if p.name.endswith(MAXIMISED_TAIL)}
    assert len(named) == 9
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
    open the group, and all nineteen of his open the Knut block, unbroken.
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
    assert overlays[first_knut] == "100x150mm-150p-1page-Portrait-w7.5mm"
    assert [o[:7] for o in overlays[first_knut:first_knut + len(PHOTO)]] == (
        ["100x150"] * 10 + ["130x180"] * 9)
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

def test_the_base_moves_exactly_twelve_fields_away_from_the_8mm_one():
    """Twelve fields, identical on every card, none of them in any i1Pro
    ``varying`` set. That is why this is a base and not a few rows on an
    existing family: folding it in would have re-cut nineteen shipping charts
    in the 8 mm family and nineteen more in the 7.5 mm one."""
    moved = {k for k in set(_I1_BASE) & set(_I1_PHOTO_BASE)
             if _I1_BASE[k] != _I1_PHOTO_BASE[k]}
    assert moved == set(BASE_DELTA)
    for field, (photo, eight) in BASE_DELTA.items():
        assert _I1_PHOTO_BASE[field] == photo, field
        assert _I1_BASE[field] == eight, f"_I1_BASE moved: {field}"


def test_the_75mm_base_is_untouched_too():
    """``_I1_75_BASE`` derives from ``_I1_BASE``, so it inherits eleven of the
    twelve and sets ``sscale`` itself. Pinned at both ends for the same
    reason."""
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


# ---------------------------------------------------------------------------
# Knut's three settings, 2026-09-18 — on EVERY chart of both card sizes
# ---------------------------------------------------------------------------

#: The note each card carries, transcribed from his post character for
#: character. Written out here rather than imported from the app, because a
#: test that asks the code what the code says proves nothing: this is the
#: sentence HE wrote, and the app has to match it.
#:
#: He gave it inside quotation marks in the issue; three of his four exports
#: carry it bare and one carries the outer quotes too. Bare is what reads
#: correctly on a printed sheet, and bare is what is pinned.
NOTE = {
    "100x150": 'i1Pro 1/2/3 target for 10x15cm / 4x6" photo card - print with '
               'borderless setting / NO expansion, retain size, '
               'color management: OFF',
    "130x180": 'i1Pro 1/2/3 target for 13x18cm / 5x7" photo card - print with '
               'borderless setting / NO expansion, retain size, '
               'color management: OFF',
}


@pytest.mark.parametrize("preset", PHOTO, ids=lambda p: p.slug)
def test_every_card_carries_the_note_for_the_card_it_is_cut_for(preset):
    """Knut, 2026-09-18: *"Make sure Chart Notes are set to: …"*, one sentence
    per card size, *"Some of the presets already have a similar text in the
    Chart Notes, but it must be replaced by the text defined above."*

    Two of his earlier exports carried an older wording with "600 patch" in it,
    and one of those was on a 648-patch chart. The note is printed down the
    edge of every sheet, so a stale one is a false statement on paper."""
    assert preset.chart_notes == NOTE[preset.layout_recipe["paper"]]
    # …and nothing of the older wording survives anywhere.
    assert "600 patch" not in preset.chart_notes


def test_the_note_names_the_card_and_never_the_other_one():
    """The 10 x 15 note must not appear on a 13 x 18 chart, or the sheet tells
    the person printing it to use the wrong paper."""
    for p in PHOTO:
        other = "130x180" if p.layout_recipe["paper"] == "100x150" else "100x150"
        wrong = "13x18cm" if other == "130x180" else "10x15cm"
        assert wrong not in p.chart_notes, p.name


@pytest.mark.parametrize("preset", PHOTO, ids=lambda p: p.slug)
def test_every_card_carries_the_sheet_text_size_and_clip_distance(preset):
    """His other two: *"the text 'Size' parameter in 'Sheet text' is set to
    6,0mm"* and *"the 'Clip' parameter in 'Text distance from edge' is set to
    2,0mm"*.

    THE SIZE BOX IS IN POINTS, and that is the whole reason this test states
    the conversion instead of the number. `layout_options_panel` reads and
    writes that box with `mm_to_pt` / `pt_to_mm`, so the 6.0 he types is 6.0
    POINTS and the recipe stores 2.12 mm — which is exactly what all four of
    his 2026-09-18 exports carry. The clip distance really is millimetres."""
    from ui.dialogs.layout_options_panel import mm_to_pt, pt_to_mm
    rec = preset.layout_recipe
    assert rec["chart_text_size_mm"] == round(pt_to_mm(6.0), 2) == 2.12
    assert round(mm_to_pt(rec["chart_text_size_mm"]), 1) == 6.0
    assert rec["text_edge_clip_mm"] == 2.0


def test_the_notes_are_not_translated_and_carry_no_em_dash():
    """Chart content he authored, like the clip note beside it: what a sheet
    says on paper is his call, and a translated copy would not be the sheet he
    tested. The house dash rule still applies to anything new."""
    from ui.tabs.tab_chart import _I1_PHOTO_NOTE
    assert set(_I1_PHOTO_NOTE) == {"100x150", "130x180"}
    for paper, text in _I1_PHOTO_NOTE.items():
        assert text == NOTE[paper]
        assert "\u2014" not in text


def test_a_builtin_note_is_taken_back_out_of_the_box_and_a_typed_one_is_not(tab):
    """The else-branch of `_seed_builtin_chart_notes`, which is the half that
    is easy to leave out and expensive to leave out.

    Pick a photo card, then pick a chart that carries no note: the box must be
    EMPTY, because "10x15cm / 4x6" photo card" would otherwise be stamped down
    the edge of an A4 ColorMunki sheet. Type your own note first and the same
    selection must leave it exactly where it is."""
    from ui.tabs.tab_chart import BUILTIN_CHART_NOTES, KNUT_PRESETS
    box = tab._manual_chart_notes_edit
    other = next(q for q in KNUT_PRESETS if not q.chart_notes)

    tab._seed_knut_preset(PHOTO[0].key)
    assert box.text() == PHOTO[0].chart_notes
    assert box.text() in BUILTIN_CHART_NOTES
    tab._seed_knut_preset(other.key)
    assert box.text() == "", "a card's note rode onto a chart on other paper"

    box.setText("Canon Pro-1000 / Hahnemuehle Photo Rag 308")
    tab._seed_knut_preset(other.key)
    assert box.text() == "Canon Pro-1000 / Hahnemuehle Photo Rag 308", (
        "a note the user typed was wiped")


@pytest.mark.parametrize("preset", PHOTO, ids=lambda p: p.slug)
def test_every_card_switches_the_settings_stamp_off(preset):
    """All twenty of Knut's photo-card exports carry "Stamp settings down the
    right edge" OFF; the app's default is ON and a built-in preset used to
    carry no answer at all.

    IT IS NOT COSMETIC ON A CARD THIS SMALL, and the number is measured rather
    than argued. The right edge of a 150 mm sheet is not tall enough for his
    note AND the command line, so with the stamp on the note was cut off and
    replaced by "…" — driven on screen 2026-09-18, 19 of 19 warned with it on
    and 0 of 19 with it off."""
    assert preset.stamp_settings is False


def test_a_preset_with_no_opinion_leaves_the_stamp_box_alone(tab):
    """`None` is not `False`. Every family but the photo cards states nothing,
    and nothing must mean "leave the checkbox where the user had it" — the
    default this app shipped with for a hundred and fifty-eight presets."""
    from ui.tabs.tab_chart import KNUT_PRESETS
    other = next(q for q in KNUT_PRESETS if q.stamp_settings is None)
    box = tab._manual_stamp_cmd_check
    for state in (True, False):
        box.setChecked(state)
        tab._seed_knut_preset(other.key)
        assert box.isChecked() is state, (
            f"{other.slug} moved a checkbox it states no opinion on")
    # …and a photo card does state one, so it moves it in both directions.
    box.setChecked(True)
    tab._seed_knut_preset(PHOTO[0].key)
    assert box.isChecked() is False


def test_only_the_photo_cards_have_an_opinion_on_the_stamp():
    """Stated so that giving another family one is a decision, not a side
    effect of editing a shared helper.

    The second decision was taken on 2026-09-22 (K1): Knut's eight 7.5 mm
    "Maximised - No Clip-border" A4/Letter charts carry the stamp OFF too,
    for the same measured reason (a 5 mm right margin, the command line over
    the patches with it on). See test_i1pro75_maximised_builtin_presets.py."""
    from ui.tabs.tab_chart import KNUT_PRESETS
    opinionated = {q.slug for q in KNUT_PRESETS if q.stamp_settings is not None}
    maximised_a4_letter = {q.slug for q in KNUT_PRESETS
                           if q.slug.startswith("i1_w75max_")}
    assert len(maximised_a4_letter) == 8
    assert opinionated == {q.slug for q in PHOTO} | maximised_a4_letter


def test_a_builtin_preset_gives_its_text_a_home_in_the_project_it_creates():
    """THE HOLE THIS CLOSED, and it was found by driving rather than by reading.

    `_seed_new_project_text` is what writes the Run description and the Chart
    Notes into a project that did not exist when they were written, and its own
    docstring says the write must happen before anything re-reads the fields
    from the fresh, empty ``meta.json``. `_on_generate` calls it. A built-in
    preset builds through `_generate_from_ti1`, which did NOT — so on screen the
    first photo card picked in a session came back with an empty Chart Notes box
    and all nineteen wrote ``chart_notes: ""`` into their run's record.

    Pinned by reading the source, because the alternative is a full chart build
    per preset: both branches of the same decision must exist in both
    functions."""
    import inspect
    import re
    from ui.tabs.tab_chart import TabChart
    for fn in (TabChart._on_generate, TabChart._generate_from_ti1):
        src = inspect.getsource(fn)
        assert "_builds_into_project(_proj_before)" in src, fn.__name__
        assert re.search(r"_seed_new_project_text\(", src), (
            f"{fn.__name__} claims a new project without giving the Output "
            f"fields a home in it")


def test_only_the_photo_cards_carry_a_note():
    """Stated so that adding one to another family is a decision, not a
    side effect."""
    from ui.tabs.tab_chart import BUILTIN_CHART_NOTES, KNUT_PRESETS
    with_notes = {q.slug for q in KNUT_PRESETS if q.chart_notes}
    assert with_notes == {q.slug for q in PHOTO}
    assert BUILTIN_CHART_NOTES == set(NOTE.values())


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
    b = MARGINS["130x180mm-648p-3pages-Portrait-w8.0mm"]
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


def test_every_name_now_spells_its_orientation_out():
    """IT USED TO BE ONE NAME SHORT OF A TOKEN, AND HE CORRECTED IT.

    `130x180mm-648p-3pages-w8.0mm` carried no orientation where every other
    chart in the app spells one out. It was pinned as it stood rather than
    quietly re-spelled, because what a chart is called is Knut's call. He then
    sent the chart again twice, both times named "…-3pages-Portrait-w8.0mm",
    and on 2026-09-18 asked for that file to replace the shipped one. So the
    display name gained the token.

    THE SLUG DID NOT MOVE. It is still `i1_photo_130x180mm_648p_3pages_w8_0mm`,
    because the slug is baked into the preset key that projects and settings
    store, and the doc's rule is that renaming a name must never change one.
    Both halves are pinned here."""
    from workflow.layout_engine import papers
    p = next(q for q in PHOTO
             if q.slug == "i1_photo_130x180mm_648p_3pages_w8_0mm")
    assert p.name == "130x180mm-648p-3pages-Portrait-w8.0mm"
    assert p.key == "__chromiq_knut_i1_photo_130x180mm_648p_3pages_w8_0mm__"
    w, h = papers.dimensions_mm(p.layout_recipe["paper"])
    assert (w, h) == (130.0, 180.0) and h > w, "the sheet really is portrait"
    # …and it is now a policy, not one name: every card spells it out.
    assert all("Portrait" in q.name for q in PHOTO), \
        [q.name for q in PHOTO if "Portrait" not in q.name]


def test_the_648_patch_card_carries_the_colour_set_he_replaced_it_with():
    """Knut, 2026-09-18: *"replace with the following one, do not keep the
    old"*. The chart that shipped stepped each channel in SIX levels
    (0, 20, 40, 60, 80, 100); the one he sent steps it in SEVEN
    (0, 16.6667, 33.3333 …). Same 648 patches, same grid, different colours, so
    nothing else in the row moved and only the bundled file did — which means
    nothing but this test can tell the two apart."""
    p = next(q for q in PHOTO
             if q.slug == "i1_photo_130x180mm_648p_3pages_w8_0mm")
    # THE FIRST TABLE ONLY. A targen .ti1 carries three, and the other two are
    # not the patch set: counting levels across all of them answers 223 and
    # says nothing about either chart.
    txt = resource_path(p.ti1_asset).read_text(
        encoding="latin-1", errors="ignore")
    # "\nBEGIN_DATA\n", not "BEGIN_DATA": the header's BEGIN_DATA_FORMAT
    # block comes first and matches the shorter needle.
    first = txt.split("\nBEGIN_DATA\n", 1)[1].split("\nEND_DATA", 1)[0]
    rows = [r.split() for r in first.splitlines() if r[:1].isdigit()]
    assert len(rows) == 648, f"{len(rows)} patches in the first table"
    # THE BLUE AXIS IS THE SHARP DISCRIMINATOR. Counting distinct levels over
    # the whole table answers 223 for both sets, because neither is a plain
    # cube; the patches with R = G = 0 are the one ramp both sets lay out and
    # they disagree on it outright.
    axis = sorted({float(r[3]) for r in rows
                   if float(r[1]) == 0 and float(r[2]) == 0})
    assert axis[4] == pytest.approx(16.6667, abs=1e-4), axis
    assert 20.0 not in axis and 40.0 not in axis, (
        "this is still the set that was replaced: it steps in 20s")
    assert len(axis) == 12, axis


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
