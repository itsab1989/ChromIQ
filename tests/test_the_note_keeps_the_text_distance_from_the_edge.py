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
the margins."* So nothing is traded against it: where the paper left between the
patch block and the reserve is too thin for a legible line, the note is not
printed at all, and the log says which two numbers to change. That costs four of
twenty-two measured configurations their note; see
`docs/design/issue_182_answers.md`.
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


@pytest.mark.parametrize("strip_w", [40, 20])
def test_an_anchored_line_hugs_the_patch_side_and_leaves_the_slack_at_the_edge(
        strip_w: int) -> None:
    """The renderer's own property, stated where it can be seen.

    Centred, a 40 px strip puts the line in columns 7..32: seven pixels of white
    on each side, half of it wasted on the side the note is trying to keep clear
    of. Anchored, it is columns 3..28, and all eleven spare pixels fall on the
    page-edge side where the reserve wants them anyway.
    """
    import workflow.tiff_metadata as tm

    def _cols(anchor):
        arr = tm._render_fitted_rotated_line(_NOTE, 3000, strip_w, np.uint8, 3,
                                             anchor_px=anchor)
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
    # strip and the alternative is a note at the 9 px floor.
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


def test_a_reserve_with_no_room_left_drops_the_note_and_says_so(
        tmp_path: Path, caplog) -> None:
    """THE RESERVE IS NOT TRADED AWAY, AND THE DROP IS NOT SILENT.

    With the clip band on the right there is 1.1 mm of paper between the patch
    block and a 4 mm reserve, and a line at the 9 px legibility floor needs
    0.9 mm plus its gap. Before this change the note printed there 0.76 mm from
    the paper edge, which is the fault. It is now not printed, and the log names
    the two numbers and the two settings that would give it room, because a note
    dropped without a word is the open item this must not add to
    (`docs/design/issue_182_answers.md` section 5).
    """
    with caplog.at_level(logging.INFO, logger="workflow.tiff_metadata"):
        added, _mm, _W, _p = _stamped(tmp_path, "noroom", 4.0,
                                      clip_side="right", clip_border=True)
    assert not added.any(), (
        "the note printed inside the reserve the user asked to keep clear"
    )
    said = " ".join(r.getMessage() for r in caplog.records)
    assert "text-distance-from-edge reserve" in said, (
        f"the note was dropped without saying why; log was: {said!r}"
    )
