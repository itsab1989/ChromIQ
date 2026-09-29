"""R23-F3 — the blank's edge spacer is resolved from the BUILD, not the record.

`ui/tabs/tab_measure.py::edge_spacer_px_from_sidecar` tells the preview how far
past the first and last patch of a strip the printed content reaches, and
"Show only measured patches" blanks exactly that far. It asked the chart's
stored recipe whether the sheet has edge spacers, two lines before asking the
engine how tall they are.

**THE RECORD AND THE BUILD DISAGREE, BY DESIGN.** `LayoutRecipe.build_kwargs`
forces edge spacers on for i1, i1Pro 3+ and ColorMunki, so a strip reader's
sheet has them whether or not the box was ticked, and the two doors record
opposite things for the same sheet: Manual stores the recipe's own field
(`false`), Guided the resolved build kwargs (`true`).

Measured by round 23 on ONE sheet through the two doors: Manual answered
**0 px** and Guided **12 px**, the blank came out **8 device rows shorter**,
and the row below it was **86.8 % dark** where the other was 0 %. On a
black-and-white spacer chart that bar is black, which is Basti's hairline
report (B8-371) arriving through a second door.

`workflow/margin_inspector.py` was corrected the same way for the same reason
(R22-F4, B8-366 F4), and the fix goes here rather than at the recording end
because it then reaches every chart already on a user's disk.

**B8-371'S GUARD CANNOT SEE THIS**, which is why this file exists: it hands
`set_edge_spacer_px(8)` in as a constant, so the sidecar is never asked. These
tests drive the sidecar.
"""
from __future__ import annotations

import dataclasses
import json
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

#: The three a strip reader forces on, whatever the recipe says.
FORCED = ("i1", "p3", "CM")


def _sidecar(tmp_path, instrument: str, edge_spacers: bool, dpi: int = 300):
    from workflow.layout_engine.presets import LayoutRecipe
    rec = LayoutRecipe(instrument=instrument, edge_spacers=edge_spacers)
    (tmp_path / "c.ti2").write_text("x", encoding="utf-8")
    (tmp_path / "c.channels.json").write_text(json.dumps(
        {"layout": {"dpi": dpi,
                    "recipe": {f.name: getattr(rec, f.name)
                               for f in dataclasses.fields(rec)}}},
        default=str), encoding="utf-8")
    return tmp_path / "c.ti2"


@pytest.mark.parametrize("instrument", FORCED)
def test_a_strip_readers_sheet_has_its_spacers_whatever_the_box_said(
        tmp_path, instrument):
    """The Manual door's record says false and the sheet has them anyway.

    MUTATION: read `recipe.get("edge_spacers")` again instead of the resolved
    `build_kwargs()` and this goes red on every one of the three.
    """
    from ui.tabs.tab_measure import edge_spacer_px_from_sidecar
    off = edge_spacer_px_from_sidecar(_sidecar(tmp_path, instrument, False))
    assert off > 0, (
        f"a {instrument} sheet was told it has no edge spacers, so the blank "
        "stops short of the ink that is printed there")


@pytest.mark.parametrize("instrument", FORCED)
def test_the_two_doors_answer_the_same_for_the_same_sheet(tmp_path, instrument):
    """Manual records the field, Guided records the resolved kwargs, and the
    sheet is the same sheet. One number, not two."""
    from ui.tabs.tab_measure import edge_spacer_px_from_sidecar
    manual = edge_spacer_px_from_sidecar(_sidecar(tmp_path, instrument, False))
    guided = edge_spacer_px_from_sidecar(_sidecar(tmp_path, instrument, True))
    assert manual == guided > 0, (
        f"the same {instrument} sheet measures {manual} px through Manual and "
        f"{guided} px through Guided")


def test_an_instrument_that_is_free_to_have_none_still_has_none(tmp_path):
    """The flag is not ignored: it is resolved. An instrument the build does
    not force still follows what the user chose, both ways.

    MUTATION: return the height unconditionally and this goes red.
    """
    from ui.tabs.tab_measure import edge_spacer_px_from_sidecar
    assert edge_spacer_px_from_sidecar(_sidecar(tmp_path, "41", False)) == 0
    assert edge_spacer_px_from_sidecar(_sidecar(tmp_path, "41", True)) > 0


def test_the_height_follows_the_page_resolution(tmp_path):
    """It is an image-pixel answer about a millimetre fact, so it has to scale
    with the sheet's own dpi."""
    from ui.tabs.tab_measure import edge_spacer_px_from_sidecar
    at300 = edge_spacer_px_from_sidecar(_sidecar(tmp_path, "i1", False, 300))
    at600 = edge_spacer_px_from_sidecar(_sidecar(tmp_path, "i1", False, 600))
    assert at600 == pytest.approx(at300 * 2, abs=1), (at300, at600)


def test_the_blank_covers_the_edge_spacer_the_build_really_prints(tmp_path):
    """**AND THIS IS WHAT IT COSTS ON SCREEN.**

    The hover/blank bounds grow by one spacer height above the first patch and
    below the last. Asked through the sidecar of a Manual i1 chart, that growth
    was zero, so the blank stopped 12 image pixels short at each end of every
    unread strip and the printed spacer there survived it.

    MUTATION: read the record again and this goes red, with the bounds equal.
    """
    from PyQt6.QtCore import QRect
    from PyQt6.QtWidgets import QApplication
    from ui.tabs.tab_measure import edge_spacer_px_from_sidecar
    from ui.tiff_preview import TiffPreview
    _app = QApplication.instance() or QApplication([])
    pv = TiffPreview()
    try:
        pv.set_page_patch_boxes({0: [QRect(100, 50, 40, 40),
                                     QRect(100, 100, 40, 40)]})
        pv._current = 0
        strip = QRect(90, 0, 60, 300)
        pv.set_edge_spacer_px(0)
        bare = pv._hover_patch_bounds(strip)
        pv.set_edge_spacer_px(
            edge_spacer_px_from_sidecar(_sidecar(tmp_path, "i1", False)))
        grown = pv._hover_patch_bounds(strip)
        assert grown.y() < bare.y() and grown.height() > bare.height(), (
            "the blank of a Manual i1 chart reaches no further than its "
            "patches, and its edge spacers are printed past them")
    finally:
        pv.close()
