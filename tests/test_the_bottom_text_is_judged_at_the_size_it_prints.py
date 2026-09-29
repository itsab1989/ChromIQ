"""The bottom text's width is predicted at the size the renderer will choose.

A tester, on beta 19:

    if I then enable "Stamp layout summary..." the measured bottom margin
    changes from 11.3mm to 19,0mm, and there becomes much more space for the
    bottom text. However, the bottom text sometime is set to a larger size than
    there is room for, there the bottom text overlaps with the right side placed
    clip-border area, but there is no warning message.

**THE PANEL WAS MEASURING A LINE THE RENDERER DOES NOT DRAW.**
`TabChart._sheet_text_width_mm` resolved an auto Size to
`text_edge_fit.AUTO_SHRINK_FLOOR_PT`, 7 pt. That was right while "auto" could
only ever shrink: the panel must not warn about a line the renderer is about to
make fit. Since beta 17 `raster.auto_sheet_text_size_mm` starts at
`AUTO_SIZE_CEILING_PT` (16 pt) and returns **the largest size that fits**, so the
panel measured the narrowest line the renderer might draw while the renderer drew
one up to 16 pt wide, and the width warning could not fire for an auto-sized
block at all.

His own chart says so: measured through `margin_inspector.measure_from_engine`,
`~/Desktop/ChromIQ-beta20-proof/knut-beta19/chart/test.channels.json` reports a
bottom margin of **18.964 mm**, which is the 19.0 he read off the panel.
"""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest                                              # noqa: E402

from workflow import text_edge_fit as tef                  # noqa: E402
from workflow.layout_engine import raster                  # noqa: E402


class _R:
    """The handful of fields the two width helpers read."""
    chart_text_size_mm = 0.0                # "auto"
    chart_text_font = "Inter"
    chart_text_bold = False
    chart_text_italic = False
    dpi = 300


def test_auto_is_resolved_by_the_renderers_own_chooser():
    """Given a room, the panel asks `auto_sheet_text_size_mm`, not the floor.

    MUTATION: return `pt_to_mm(AUTO_SHRINK_FLOOR_PT)` regardless of `room_mm`
    from `_bottom_text_size_mm` and the "bigger than the floor" assertion goes
    red.
    """
    from ui.tabs.tab_chart import TabChart
    lines = ["ChromIQ"]
    floor_mm = tef.pt_to_mm(tef.AUTO_SHRINK_FLOOR_PT)

    # With no room to go on, the floor is still the answer: warning only at the
    # smallest size the renderer may reach is the conservative fallback.
    assert TabChart._bottom_text_size_mm(_R(), lines, 0.0) == pytest.approx(
        floor_mm)

    # With a wide sheet to fill, "auto" grows, and the panel must know it.
    roomy = TabChart._bottom_text_size_mm(_R(), lines, 180.0)
    assert roomy > floor_mm, (
        f"the panel still measures at the {tef.AUTO_SHRINK_FLOOR_PT} pt floor "
        f"on a sheet with 180 mm of room; the renderer would draw larger")
    # …asked of the renderer's own chooser and never above what it answers.
    width_only = raster.auto_sheet_text_size_mm(
        lines, 180.0, "Inter", False, False, 300)
    assert roomy <= width_only + 1e-9, (
        "the panel predicts a LARGER size than the width rule allows, so it "
        "would warn about a line the renderer never draws")
    # **AND THE RENDERER'S SECOND LOOP IS APPLIED TOO.** `render_pages` walks
    # the size down again until the line's box fits the band the engine
    # reserved. At a 200 mm room the width rule alone says 14.50 pt and the
    # sheet carries 9.84; predicting the wider one is a false width warning.
    assert raster.sheet_text_line_mm(roomy, "Inter", False, False, 300) <= \
        raster.sheet_text_reserve_mm(300) + 1e-9, (
        "the resolved size does not fit the band the renderer holds the type "
        "to, so the panel is predicting a line that will be shrunk")
    # …and it never exceeds the ceiling the renderer works to.
    assert roomy <= tef.pt_to_mm(tef.AUTO_SIZE_CEILING_PT) + 1e-9


def test_a_typed_size_is_still_used_as_typed():
    """A number the user chose is never second-guessed by a room."""
    from ui.tabs.tab_chart import TabChart

    class _T(_R):
        chart_text_size_mm = 13.0 * 25.4 / 72.0

    for room in (0.0, 20.0, 400.0):
        assert TabChart._bottom_text_size_mm(_T(), ["x"], room) == \
            pytest.approx(_T.chart_text_size_mm)


def test_a_wider_line_is_what_overflows_a_clip_border():
    """The arithmetic the fix restores: at the real size, the line is too wide.

    A narrow room and a long line. At the 7 pt floor it fits and nothing is
    said; at the size "auto" really picks for a WIDE sheet it does not. That is
    the gap his sheet fell through, in two numbers.
    """
    from ui.tabs.tab_chart import TabChart
    line = ["ChromIQ  profile name: test  strips on page: 18  patches: 648"]
    floor_mm = tef.pt_to_mm(tef.AUTO_SHRINK_FLOOR_PT)
    narrow = raster.sheet_text_width_mm(line, floor_mm, "Inter", False, False,
                                        300)
    big = TabChart._bottom_text_size_mm(_R(), line, narrow * 2.0)
    assert big > floor_mm, (
        "the resolved size did not grow past the floor on a roomier sheet, so "
        "this case cannot tell the two apart")
    wide = raster.sheet_text_width_mm(line, big, "Inter", False, False, 300)
    assert wide > narrow, (
        "the resolved size draws no wider than the floor, so this case cannot "
        "distinguish the two and proves nothing")
    # The panel now compares THAT width against the room, so a room between the
    # two figures is a genuine overflow it can see.
    room = (narrow + wide) / 2.0
    assert tef.bottom_text_overflow(
        210.0, 4.0, wide, False, 0.0, 0.0, True,
        clip_border_mm=210.0 - room - 4.0, clip_side="right") is not None
    assert tef.bottom_text_overflow(
        210.0, 4.0, narrow, False, 0.0, 0.0, True,
        clip_border_mm=210.0 - room - 4.0, clip_side="right") is None


def test_the_panel_hands_the_measured_room_to_the_width_helper():
    """Wired in, and with the room the overflow check itself uses.

    Two rooms would be two sheets, and the warning would describe neither.

    MUTATION: drop `room_mm=_room_mm` from the `_sheet_text_width_mm` call and
    this goes red.
    """
    import inspect
    from ui.tabs import tab_chart as tc
    src = inspect.getsource(tc.TabChart._engine_text_notes)
    body = "\n".join(l for l in src.splitlines()
                     if not l.strip().startswith("#"))
    assert "_room_mm = text_edge_fit.bottom_text_room_mm(" in body, (
        "the panel no longer works out the room the renderer shrinks against")
    assert "_sheet_text_width_mm(r, room_mm=_room_mm)" in body, (
        "the width is measured without the room, so 'auto' falls back to the "
        "7 pt floor and the warning cannot fire")
    # …and the room is built from the MEASURED margins, which is the whole
    # point of the frame it is named after.
    i = body.index("_room_mm = text_edge_fit.bottom_text_room_mm(")
    block = body[i:i + 900]
    assert "margin_left_mm=_margin_l_mm" in block
    assert "_meas_l if _meas_l is not None" in body
