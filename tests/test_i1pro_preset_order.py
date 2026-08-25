"""The built-in preset list is ordered paper → patch width → patches → pages.

Knut, 4.1.3-beta.15: *"the preset list for i1Pro items are grouped according to
patch width first, then patch count. This is good, but is not done properly for
all the i1Pro preset items"* — and then: *"sort those groups individually
according to page size, then patch count and then page number."*

The A4 block was the broken one: inserting the 7.5 mm family and the two
"Full layout setup" charts at ascending-patch-count positions interleaved them
with the 8.0 mm charts (8.0/156, 8.0/312, 7.5/484, 8.0/572, 7.5/162, …). The
Letter and A3 blocks already read paper → width → patch count, so this restores
one rule rather than inventing one.

The width term is not in Knut's sentence on purpose: taken literally,
paper-then-patch-count interleaves the widths, which is MORE mixed than what he
reported. He had already said the widths group ("8.0 and 8.5 as same group").
"""
from __future__ import annotations

import re

import pytest

from ui.tabs.tab_chart import (KNUT_PRESETS, _KNUT_GROUP_ENTRIES,
                               _paper_sort_key, _preset_sort_key)

_W = re.compile(r"-w([0-9.]+)mm")


def _by_group(group: str):
    return [p for p in KNUT_PRESETS if p.file_group == group]


def test_the_width_comes_from_the_name_and_agrees_with_it():
    """`patch_width_mm` reads the name's own token — pin that agreement.

    There is no width FIELD; the value exists only in the name. If a preset is
    ever added whose name says one width, this catches the drift.
    """
    for p in KNUT_PRESETS:
        m = _W.search(p.name)
        if m:
            assert p.patch_width_mm == pytest.approx(float(m.group(1))), (
                f"{p.name}: name says {m.group(1)}mm, "
                f"patch_width_mm says {p.patch_width_mm}")
        else:
            assert p.patch_width_mm == 0.0, (
                f"{p.name} has no -wXXmm token but reports a width")


@pytest.mark.parametrize("group", ["i1Pro", "ColorMunki", "Scanner",
                                   "Red River Paper"])
def test_every_group_is_sorted(group):
    """Each group's displayed order must be the sorted order — no exceptions."""
    entries = _KNUT_GROUP_ENTRIES[group]
    by_key = {p.key: p for p in _by_group(group)}
    shown = [by_key[k] for _lbl, _ov, k in entries if k in by_key]
    expected = sorted(shown, key=lambda q: _preset_sort_key(q, group))
    assert [p.key for p in shown] == [p.key for p in expected], (
        f"the {group} list is not in paper → width → patches → pages order")


def test_the_a4_block_no_longer_interleaves_the_widths():
    """The exact fault Knut reported: widths mixed inside one paper."""
    i1 = [p for p in _by_group("i1Pro") if p.paper == "A4" and _W.search(p.name)]
    shown = sorted(i1, key=lambda q: _preset_sort_key(q, "i1Pro"))
    widths = [p.patch_width_mm for p in shown]
    assert widths == sorted(widths), f"A4 widths interleave: {widths}"
    # …and within one width, the patch counts rise
    for w in set(widths):
        counts = [p.patches for p in shown if p.patch_width_mm == w]
        assert counts == sorted(counts), f"A4 {w}mm patch counts: {counts}"


def test_the_letter_and_a3_blocks_did_not_move():
    """They were already right — a fix that reshuffles them is a regression."""
    # NB: A3 landscape is stored as its millimetre code, not as "A3".
    for paper, first, last in (("Letter", 162, 3432), ("420x297", 1404, 3432)):
        rows = sorted((p for p in _by_group("i1Pro") if p.paper == paper),
                      key=lambda q: _preset_sort_key(q, "i1Pro"))
        assert rows[0].patches == first
        assert rows[-1].patches == last


def test_paper_order_is_unchanged():
    """`_paper_sort_key` is deliberately NOT touched by this change.

    A4 → Letter → A3 is what the list has always shown. Three different paper
    orders are defensible (by area, alphabetical, as-shipped) and choosing
    between them is Sebastian's call, not this fix's.
    """
    papers = ["A4", "Letter", "420x297"]      # A4, US Letter, A3 landscape
    assert sorted(papers, key=_paper_sort_key) == papers


def test_the_width_term_applies_to_i1pro_only():
    """ColorMunki must NOT be width-sorted — it is pinned to patch count.

    Applying the width term everywhere moved 41 of the 45 ColorMunki rows and
    broke `test_colormunki_builtin_presets.py`. This states the scope so it
    cannot be widened by accident.
    """
    from ui.tabs.tab_chart import _WIDTH_SORTED_GROUPS
    assert _WIDTH_SORTED_GROUPS == ("i1Pro",)

    cm = [p for p in _by_group("ColorMunki") if p.paper == "A4"]
    if len(cm) > 2:
        counts = [p.patches for p in
                  sorted(cm, key=lambda q: _preset_sort_key(q, "ColorMunki"))]
        assert counts == sorted(counts), (
            "the ColorMunki A4 block is no longer in patch-count order — the "
            "width term has leaked into a group that does not want it")
