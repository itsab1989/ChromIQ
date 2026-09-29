"""The chart note obeys "Text distance from edge" on the RIGHT as well.

Knut, 2026-09-10, on a Guided chart of his own: *"Right says 5.8 mm but text
goes to the edge almost. … Like the left and top labels, I think the text needs
to stay within the default 'Text distance from edge' settings in preferences
chart layout. For all sides, for Guided mode. Not a hardwired margin."*

Measured on his own 130x180 mm card at 200 dpi with the box reading 4.0 mm: the
note ended **1.98 mm** from the paper edge and left a **3.05 mm** empty gap on
the patch side. It was pushed the wrong way at both ends, and for one reason:
`text_edge_mm` reached `_stamp_one` and was applied to the TOP and BOTTOM only.
Horizontally the band simply ran to `W - _PATCH_SAFETY_PAD_PX`, a 4 px constant
which is 0.5 mm at 200 dpi, and the line was CENTRED in a 40 px strip.

And the reserve is a LIMIT, not a preference. Knut again, the same day:
*"the labels respect the 'Text distance from edge' settings, even if the margins
defined make the patch area overlap with the text. Then the user needs to adjust
the margins."* So nothing is traded against it.

**WHAT GIVES WAY IS THE PATCH AREA, AND THIS FILE ONCE SAID THE OPPOSITE.**
4.2.3 dropped the note where the paper left between the patch block and the
reserve was too thin for a legible line, with only a log line to show for it,
and it cost the 10 x 15 cm photo card its identification line on every sheet.
Knut's ruling of 2026-09-10:

    "For the right margin, the text must still be visible, even if the patch
     area overlaps on the right Run Chart Notes text. Else the user will not
     notice that it is silently dropped, like you now do. The user must be given
     the chance to see that something is wrong, and then adjust the margins."

So the note now grows inward over the patches, the reserve still holds, and the
collision is reported in red in the "Measured from Preview" frame. See
`docs/design/issue_182_answers.md` section 2c.
"""
from __future__ import annotations

import logging
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest
import tifffile

from workflow.layout_engine import chart as le_chart
from workflow.layout_engine.presets import default_recipe
from workflow.tiff_metadata import stamp_chart_metadata

_NOTE = "Canon PRO-1000, PhotoRag 308, CM off, 2880dpi, no scaling"


def _ti1(path: Path, n: int = 120) -> None:
    lines = ["CTI1", "", 'DESCRIPTOR "n"', 'ORIGINATOR "C"',
             'KEYWORD "SAMPLE_LOC"', "NUMBER_OF_FIELDS 7", "BEGIN_DATA_FORMAT",
             "SAMPLE_ID RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z", "END_DATA_FORMAT",
             f"NUMBER_OF_SETS {n}", "BEGIN_DATA"]
    for i in range(n):
        lines.append(f"{i+1} {(i*37)%101}.0 {(i*71)%101}.0 {(i*13)%101}.0 "
                     "40.0 45.0 50.0")
    lines += ["END_DATA", ""]
    path.write_text("\n".join(lines), encoding="utf-8")


def _ink(path: Path) -> np.ndarray:
    a = np.asarray(tifffile.imread(str(path)))
    g = a[..., :3].min(axis=2) if a.ndim == 3 else a
    return g < 240


def _stamped(tmp_path: Path, tag: str, edge_mm: float, **over):
    """``(added-ink mask, mm-per-pixel, paper width px, patch right col)``.

    The note is measured against a control built with the same recipe and NOT
    stamped, because an absolute ink figure has been reported as a fault three
    times in this project and been wrong each time.
    """
    d = tmp_path / tag
    d.mkdir(parents=True, exist_ok=True)
    src = d / "n.ti1"
    _ti1(src)
    band_mm = 0.0
    r = replace(default_recipe("i1", "A4"), randomize=False,
                text_edge_clip_mm=edge_mm, **over)
    if str(r.clip_side) == "right" and r.clip_border:
        band_mm = float(r.clip_border_width_mm or 0.0)
    le_chart.build_from_recipe(src, d / "c", r)
    base = sorted(d.glob("*.tif"))[0]
    control = _ink(base)
    H, W = control.shape
    patch_cols = np.where(control.sum(axis=0) / H >= 0.30)[0]
    stamp_chart_metadata([base], [_NOTE], edge_mm, band_mm)
    added = _ink(base) & ~control
    return added, 25.4 / float(r.dpi), W, int(patch_cols.max())


#: `(right margin, "Text distance from edge" → Clip)`. EVERY PAIR IS ONE WHERE
#: THE SETTING BINDS, and that is the whole design of the sweep. Left to itself
#: the note lands 2.12 / 8.97 / 16.93 mm from the paper edge on these three
#: sheets, so a pair asking for LESS than that would pass without the reserve
#: existing at all. Each of these asks for more.
_BINDING = [(6.0, 4.0), (12.0, 10.0), (20.0, 18.0)]


@pytest.mark.parametrize("margin_mm,edge_mm", _BINDING)
def test_the_note_keeps_the_setting_clear_of_the_right_paper_edge(
        tmp_path: Path, margin_mm: float, edge_mm: float) -> None:
    """The distance the user typed is the distance the ink keeps.

    Before this, the note sat 2.12 mm from the edge of a stock A4 sheet at
    every value of the setting, because horizontally the setting was not read
    and a 4 px constant decided instead.
    """
    added, mm, W, _patch = _stamped(tmp_path, f"e{margin_mm}_{edge_mm}", edge_mm,
                                    margin_right=margin_mm)
    assert added.any(), f"no note printed at Text distance from edge {edge_mm} mm"
    right = int(np.flatnonzero(added.any(axis=0)).max())
    to_edge = (W - 1 - right) * mm
    assert to_edge >= edge_mm - 0.1, (
        f"the note ends {to_edge:.2f} mm from the paper edge, and "
        f"“Text distance from edge” asks for {edge_mm:.2f} mm"
    )


@pytest.mark.parametrize("strip_w,dpi", [(40, 200), (20, 100)])
def test_an_anchored_line_hugs_the_patch_side_and_leaves_the_slack_at_the_edge(
        strip_w: int, dpi: float) -> None:
    """The renderer's own property, stated where it can be seen.

    Centred, a 40 px strip puts the line in columns 7..32: seven pixels of white
    on each side, half of it wasted on the side the note is trying to keep clear
    of. Anchored, it is columns 3..28, and all eleven spare pixels fall on the
    page-edge side where the reserve wants them anyway.

    EACH STRIP IS PAIRED WITH A RESOLUTION AT WHICH IT IS WIDER THAN THE FLOOR,
    because there is no slack to place below it. Knut's floor is 8 pt, which is
    22 px at 200 dpi and 11 px at 100, so a 20 px strip at 200 dpi is narrower
    than one line: the line is drawn at the floor and the strip's own edges crop
    it, which is the behaviour he asked for and the warning is what tells the
    user. The pair was ``[40, 20]`` at a fixed 200 dpi and the narrow one then
    measured the crop rather than the anchor.
    """
    import workflow.tiff_metadata as tm

    def _cols(anchor):
        arr = tm._render_fitted_rotated_line(_NOTE, 3000, strip_w, np.uint8, 3,
                                             anchor_px=anchor, dpi=dpi)
        on = np.flatnonzero((arr[..., 0] < 200).any(axis=0))
        return int(on.min()), int(on.max())

    centred_l, centred_r = _cols(None)
    anchored_l, anchored_r = _cols(tm._NOTE_PATCH_GAP_PX)
    assert anchored_l < centred_l, (
        f"anchored ink starts at column {anchored_l} and centred at "
        f"{centred_l}; anchoring is meant to move it toward the patch side"
    )
    assert anchored_l <= tm._NOTE_PATCH_GAP_PX + 1, (
        f"anchored ink starts {anchored_l} px in, and Knut asked for a gap of "
        f"{tm._NOTE_PATCH_GAP_PX} px"
    )
    assert anchored_l > 0, "the line is touching the patch side of the strip"
    # AND IT NEVER COSTS LEGIBILITY. Centring spends half the strip's slack on
    # the patch side, so the font that fits is smaller: at 20 px the centred
    # line is 11 px thick and the anchored one 17. Reclaiming that slack is
    # most of the point on a narrow margin, where the reserve has capped the
    # strip and the alternative is a note at the 8 pt floor.
    assert (anchored_r - anchored_l) >= (centred_r - centred_l), (
        f"anchored the line is {anchored_r - anchored_l + 1} px thick and "
        f"centred {centred_r - centred_l + 1} px; anchoring must not shrink it"
    )


@pytest.mark.parametrize("margin_mm", [12.0, 20.0])
def test_the_note_sits_beside_the_patch_block_not_out_at_the_paper_edge(
        tmp_path: Path, margin_mm: float) -> None:
    """The other half of the same fault: 3.05 mm of empty paper on the patch
    side while the note lay against the edge. Knut asked for the reverse by
    name: *"should the text move closer to the patch area edge but still leave
    2 pixels space/gap, so that it is not going towards the edge?"*

    The budget here is four pixels, and it is deliberate rather than generous.
    Measured on both sheets: anchored the note starts 0.931 mm from the patch
    block, centred in the same strip it starts 1.270 mm from it. Nothing in
    this build is random (`randomize=False`, one font, one size), so 1.10 mm
    separates the two by two pixels either way.
    """
    added, mm, _W, patch_right = _stamped(tmp_path, f"gap{margin_mm}", 4.0,
                                          margin_right=margin_mm)
    assert added.any(), "no note printed"
    left = int(np.flatnonzero(added.any(axis=0)).min())
    gap = (left - patch_right) * mm
    assert gap > 0.0, "the note is touching or overlapping the patch block"
    assert gap <= 1.10, (
        f"the note starts {gap:.3f} mm from the patch block; anchored against "
        "that side it lands at 0.931 mm and centred at 1.270 mm"
    )


def test_a_reserve_with_no_room_left_overlaps_the_patches_rather_than_dropping(
        tmp_path: Path, caplog) -> None:
    """THE RESERVE IS NOT TRADED AWAY, AND THE NOTE IS NOT DROPPED EITHER.

    With the clip band on the right there is 1.1 mm of paper between the patch
    block and a 4 mm reserve, and a line at the 9 px legibility floor needs
    0.9 mm plus its gap. 4.2.3 printed nothing there. Knut's ruling of
    2026-09-10 reverses that:

        "For the right margin, the text must still be visible, even if the patch
         area overlaps on the right Run Chart Notes text. Else the user will not
         notice that it is silently dropped, like you now do."

    So the note prints, the page-edge reserve still holds, and the collision is
    said out loud: in the log here, and in red in the "Measured from Preview"
    frame's message field, which is what the user sees.
    """
    with caplog.at_level(logging.INFO, logger="workflow.tiff_metadata"):
        added, mm, W, _p = _stamped(tmp_path, "noroom", 4.0,
                                    clip_side="right", clip_border=True)
    assert added.any(), (
        "the note was dropped, which is the silent failure the ruling forbids"
    )
    right = int(np.flatnonzero(added.any(axis=0)).max())
    to_edge = (W - 1 - right) * mm
    assert to_edge >= 4.0 - 0.1, (
        f"the note ends {to_edge:.2f} mm from the paper edge and the reserve "
        "asks for 4.00 mm; the reserve is the one limit that still holds"
    )
    # …AND IT DID NOT SOLVE ITS PROBLEM BY PRINTING ON THE USER'S OWN WORDS.
    # The ruling sanctions the note against the PATCH AREA and says nothing
    # about the note against clip-border content, which is text the user wrote.
    # So on this chart the note goes inward, over the patches, and the band
    # keeps the sliver at the paper's edge.
    _band = float(replace(default_recipe("i1", "A4")).clip_border_width_mm)
    assert to_edge >= _band - 0.5, (
        f"the note ends {to_edge:.2f} mm from the paper edge and the clip "
        f"border on that edge is {_band:.1f} mm wide, so it is printing over "
        "the user's own clip content"
    )
    said = " ".join(r.getMessage() for r in caplog.records)
    assert "overlaps the patch block" in said, (
        f"the overlap was not reported in the log; log was: {said!r}"
    )


def test_no_constant_sits_under_the_users_own_number(tmp_path: Path) -> None:
    """Knut, 2026-09-10: *"there shall not be any hard-coded values in the
    code"*.

    The sweep above only ever asks for MORE than the constant, so every case in
    it passes whether the constant is there or not: putting
    `max(_PATCH_SAFETY_PAD_PX, …)` back leaves all of them green. That is a
    mutation that does not land, and a check nobody proved is not a check.

    This one asks for LESS, and it asks it on a sheet where the answer is
    visible. The setting is a MINIMUM, not a position: on a roomy margin the
    note keeps its 40 px strip anchored to the patch side and the slack falls on
    the page-edge side, so it lands far outside the reserve whatever the reserve
    says, and the constant cannot be seen. Measured across four right margins,
    only the narrow ones pin the note to the reserve:

        margin 1.0 mm, setting 0.2 mm -> 0.169 mm from the edge
        margin 2.0 mm, setting 0.2 mm -> 0.169 mm
        margin 3.0 mm, setting 0.2 mm -> 0.508 mm
        margin 6.0 mm, setting 0.2 mm -> 2.963 mm   <- slack, not the reserve

    So the sheet is a narrow one, where the note is pinned at ``W - reserve``.

    AND IT MEASURES THE MOVE, NOT THE POSITION. It used to assert that 0.2 mm
    put the ink closer to the edge than the old 0.339 mm constant would, which
    stopped being visible when the shrink floor rose to Knut's 8 pt on
    2026-09-11: the strip is now wider than one line of ink, and the anchor
    deliberately leaves that slack on the page-edge side, so the ink stands off
    the reserve by a constant amount at every setting. The DIFFERENCE between
    two settings is unaffected by that constant and is what the setting
    actually controls: ask for 0.8 mm more reserve and the ink must move 0.8 mm
    inward. A ``max(_PATCH_SAFETY_PAD_PX, ...)`` under the small one shortens
    the move to 0.66 mm, which this catches.
    """
    import workflow.tiff_metadata as tm

    # 0.0 AND 1.0, NOT 0.2 AND 1.0. The move under test is
    # `large - small`, and the constant can only shorten it to
    # `large - floor_mm`. At 0.2 that is 0.66 against 0.80, which is inside the
    # 0.15 mm the ink's own rounding needs; at 0.0 it is 0.66 against 1.00 and
    # the mutation lands. Measured: putting `max(_PATCH_SAFETY_PAD_PX, ...)`
    # back left this test GREEN at 0.2.
    small, large = 0.0, 1.0
    added_s, mm, W, _patch = _stamped(tmp_path, "below_the_old_floor", small,
                                      margin_right=2.0)
    assert added_s.any(), "no note printed at all, so this measures nothing"
    added_l, _mm2, _W2, _p2 = _stamped(tmp_path, "above_the_old_floor", large,
                                       margin_right=2.0)
    assert added_l.any(), "no note printed at all, so this measures nothing"

    floor_mm = tm._PATCH_SAFETY_PAD_PX * mm
    assert small < floor_mm < large, (
        f"the two settings under test ({small} / {large} mm) do not straddle "
        f"the old constant ({floor_mm:.3f} mm), so this test could not tell "
        "them apart")

    def _to_edge(added):
        right = int(np.flatnonzero(added.any(axis=0)).max())
        return (W - 1 - right) * mm

    moved = _to_edge(added_l) - _to_edge(added_s)
    assert abs(moved - (large - small)) < 0.15, (
        f"asking for {large - small:.1f} mm more reserve moved the note "
        f"{moved:.3f} mm ({_to_edge(added_s):.3f} -> {_to_edge(added_l):.3f} mm "
        f"from the paper edge); a hard-coded value is still sitting under the "
        "setting")
