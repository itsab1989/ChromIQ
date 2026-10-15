"""Knut, #182 6103148331 (4.3.3 test, items 1 and 3).

1. Patches over the patch error limit that the neighbour check ALSO flags
   showed no colour range on their card (G22, AT4 of his run 2: both blue,
   both red for both reasons, both cards without "Colour range"), so they
   read as belonging to no range. By design only their own re-read can turn
   them yellow; the card now still names the range and what it has
   confirmed so far, above the two lines that say why the range cannot
   confirm them.
3. The range that took purple in beta 11 is named for both, "blue/purple",
   as the other merged ranges are.
"""
from __future__ import annotations

import pytest

from workflow import measurement_messages as M


@pytest.fixture
def qapp():
    from PyQt6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def _card(qapp, **info):
    from ui.tiff_preview import _PatchInfoTile
    tile = _PatchInfoTile(None)
    base = {"loc": "G22", "exp_rgb": (37, 13, 255), "meas_rgb": (0, 78, 149),
            "exp_lab": (35.5, 74.0, -120.9), "meas_lab": (32.1, 0.9, -46.1),
            "de": 104.68, "warn": True, "warn_de": 95.0, "flag": "red"}
    base.update(info)
    tile.set_content(base, "both")
    return [t for _sw, t in tile._rows]


NB = {"further": 5.2, "n": 2, "limit": 5.0}


def test_a_red_card_for_both_reasons_names_its_range(qapp):
    lines = _card(qapp, neighbour=NB, reread_only=True, colour_range="blue",
                  range_k=2, range_locs=("C19", "E24"))
    assert "Colour range: blue/purple" in lines
    assert "Patches of this range confirmed so far: C19, E24." in " ".join(lines)
    i = lines.index("Colour range: blue/purple")
    assert i < next(j for j, x in enumerate(lines)
                    if x.startswith("Read patch G22 again to find out."))


def test_a_learned_range_is_named_without_a_list(qapp):
    lines = _card(qapp, neighbour=NB, reread_only=True, colour_range="blue",
                  range_k=3, range_locs=("C19", "E24", "G22", "M3"))
    assert "Colour range: blue/purple" in lines
    assert not any(t.startswith(("Confirmed:", "Patches of this range"))
                   for t in lines)


def test_the_blue_range_is_named_blue_purple():
    assert M.RANGE_NAMES["blue"] == "blue/purple"
    import json
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    for p in sorted((root / "data/i18n").glob("*.json")):
        cat = json.loads(p.read_text(encoding="utf-8"))
        assert "/" in cat["blue/purple"], p.name
