"""The chart note's two ENDS obey "T", "B" and the top/bottom ruler markers.

The note down the right margin is one rotated line, so it has three edges that
matter: its thickness runs into the RIGHT page edge, and its two ends run into
the TOP and the BOTTOM. `tiff_metadata._stamp_one` measured all three with the
side box, "Clip".

Measured by driving the real window at 200 dpi on an A4 ColorMunki sheet, the
note isolated against a control sheet built with it switched off
(`scripts/drive_182_challenge_two.py`, steps 01 and 02):

* **"T" and "B" moved the note by nothing.** At T = B = 4.0 and again at
  T = B = 20.0 the same 10,917 pixels of note ink ran from 5.46 mm of the top
  and 5.08 mm of the bottom. At 20.0 the note crossed the reserve by 14.54 mm.
* **With the markers on for "Top/bottom" and OFF for "Sides", the note's ink
  landed in the dash bands**: 5.46 mm from the top, inside the 4.0 to 6.0 mm
  comb, 9 pixels of it in the top band and 41 in the bottom. Turning "Sides"
  back on moved the note to 8.00 mm, so a checkbox about the LEFT and RIGHT
  dashes was the only thing keeping it off the TOP ones.
* On one A4 sheet at T 20 / B 4 with both marker sets on, the strip letters
  kept 20.0 mm from the top, the bottom line kept 7.0 mm from the bottom, the
  clip band's rectangle sat at 12.0 mm and the note kept 7.0 mm. Four elements,
  three answers, one page.

`text_edge_fit.edge_reserve_mm` is the one function that answers "how far in
from THIS edge", and both the stamper and the panel's prediction take what it
says now.
"""
from __future__ import annotations

import inspect
from pathlib import Path

import numpy as np
import pytest
import tifffile

from workflow import text_edge_fit, tiff_metadata

DPI = 200
PAPER_W_MM, PAPER_H_MM = 210.0, 297.0
NOTE = ("run chart notes written long on purpose so the stamped line fills the "
        "whole strip it is given and its two ends land where that strip really "
        "begins and ends, which is the thing these tests measure, and it keeps "
        "going so no amount of shrinking leaves slack at either end")


def _mm(v: float) -> int:
    return int(round(v * DPI / 25.4))


def _sheet(path: Path) -> Path:
    """A blank A4 sheet with a patch block, at 200 dpi, for the stamper."""
    W, H = _mm(PAPER_W_MM), _mm(PAPER_H_MM)
    arr = np.full((H, W, 3), 255, dtype=np.uint8)
    # A patch block, so `_detect_writable_band` finds a right margin at all.
    arr[_mm(30.0):_mm(270.0), _mm(20.0):_mm(190.0)] = 128
    tifffile.imwrite(str(path), arr, resolution=(DPI, DPI),
                     resolutionunit="INCH")
    return path


def _note_rows_mm(path: Path, control: Path) -> tuple[float, float, int]:
    """(top mm, bottom mm, pixels) of the ink the note added to the sheet."""
    a = tifffile.imread(str(control))
    b = tifffile.imread(str(path))
    a = a.min(axis=2) if a.ndim == 3 else a
    b = b.min(axis=2) if b.ndim == 3 else b
    mask = (a.astype(int) - b.astype(int)) > 40
    rows = np.where(mask.any(axis=1))[0]
    assert rows.size, "the note left no ink at all"
    H = mask.shape[0]
    k = 25.4 / DPI
    return (float(rows[0]) * k, float(H - 1 - rows[-1]) * k, int(mask.sum()))


def _stamped(tmp_path: Path, name: str, **kw) -> Path:
    p = _sheet(tmp_path / f"{name}.tif")
    tiff_metadata.stamp_chart_metadata([p], [NOTE], **kw)
    return p


@pytest.fixture()
def control(tmp_path: Path) -> Path:
    return _sheet(tmp_path / "control.tif")


def test_t_and_b_move_the_notes_ends(tmp_path: Path, control: Path) -> None:
    """The reserve the ends keep is "T" and "B", not the side box."""
    near = _stamped(tmp_path, "near", text_edge_mm=4.0,
                    text_edge_top_mm=4.0, text_edge_bottom_mm=4.0)
    far = _stamped(tmp_path, "far", text_edge_mm=4.0,
                   text_edge_top_mm=20.0, text_edge_bottom_mm=20.0)

    n_top, n_bot, _ = _note_rows_mm(near, control)
    f_top, f_bot, _ = _note_rows_mm(far, control)

    # The line is CENTRED along the strip and truncated at the floor, so a few
    # millimetres of slack sit at each end whatever the reserve is; measured
    # here it is 5.0 mm. What matters is that the ink is nowhere near 20.
    assert n_top < 15.0 and n_bot < 15.0, (n_top, n_bot)
    # 20 mm asked for, and the ink is inside it at both ends. The fitter's own
    # safety pad puts the first ink a fraction further in, never nearer.
    assert f_top >= 20.0, f"note ink {f_top:.2f} mm from the top, T is 20.0"
    assert f_bot >= 20.0, f"note ink {f_bot:.2f} mm from the bottom, B is 20.0"
    assert f_top - n_top > 10.0, (n_top, f_top)


def test_the_top_bottom_markers_keep_the_notes_ends_clear(
        tmp_path: Path, control: Path) -> None:
    """With "Sides" off and "Top/bottom" on, the ends still clear the dashes.

    This is the configuration that put note ink in both combs: the reserve fell
    back to "Clip" at 4.0 while the dashes run 4.0 to 6.0 mm in.
    """
    reserve = text_edge_fit.edge_reserve_mm(4.0, True, 4.0, 2.0, True)
    assert reserve == pytest.approx(7.0)

    p = _stamped(tmp_path, "markers", text_edge_mm=4.0,
                 text_edge_top_mm=reserve, text_edge_bottom_mm=reserve)
    top, bot, _ = _note_rows_mm(p, control)

    assert top >= 6.0, f"note ink at {top:.2f} mm is inside the 4.0-6.0 mm comb"
    assert bot >= 6.0, f"note ink at {bot:.2f} mm is inside the 4.0-6.0 mm comb"


def test_an_unsupplied_end_reserve_keeps_the_old_behaviour(
        tmp_path: Path, control: Path) -> None:
    """A caller that does not know gets what it always got, not a guess."""
    old = _stamped(tmp_path, "old", text_edge_mm=9.0)
    same = _stamped(tmp_path, "same", text_edge_mm=9.0,
                    text_edge_top_mm=9.0, text_edge_bottom_mm=9.0)
    assert _note_rows_mm(old, control) == _note_rows_mm(same, control)


def test_the_two_ends_are_independent(tmp_path: Path, control: Path) -> None:
    """T 20 / B 4 is not T 4 / B 20 turned over, and the ends say so."""
    p = _stamped(tmp_path, "asym", text_edge_mm=4.0,
                 text_edge_top_mm=20.0, text_edge_bottom_mm=4.0)
    top, bot, _ = _note_rows_mm(p, control)
    assert top >= 20.0, top
    assert bot < 8.0, bot


def test_the_prediction_measures_the_same_strip_as_the_stamper() -> None:
    """`note_characters_lost` takes the same two ends, or it predicts a strip
    that is not on the sheet."""
    sig = inspect.signature(tiff_metadata.note_characters_lost)
    assert "text_edge_top_mm" in sig.parameters
    assert "text_edge_bottom_mm" in sig.parameters

    long_note = NOTE * 3
    room = 5.0
    loose = tiff_metadata.note_characters_lost(
        long_note, PAPER_H_MM, 4.0, room, DPI, 0.0, "")
    tight = tiff_metadata.note_characters_lost(
        long_note, PAPER_H_MM, 4.0, room, DPI, 0.0, "",
        text_edge_top_mm=20.0, text_edge_bottom_mm=20.0)
    # A shorter strip cuts more, and the prediction has to see that.
    assert tight > loose, (loose, tight)


def test_the_stamper_reads_the_one_reserve_function_for_each_edge() -> None:
    """The caller asks `edge_reserve_mm`; it does not add the markers up here.

    Three faults on this feature came from a second copy of one rule, so the
    arithmetic lives in one place and `chart_creator` is held to calling it.
    """
    from workflow import chart_creator
    src = inspect.getsource(chart_creator.ChartCreator._stamp_tiff_metadata)
    assert "edge_reserve_mm(" in src, \
        "the note's end reserves must come from text_edge_fit.edge_reserve_mm"
    # …and never by adding the marker numbers together on the spot.
    assert "helper_marker_len_mm) + 1.0" not in src


# --------------------------------------------------------------------------
# AND THE CALLER, WHICH IS WHERE THE NUMBERS ARE DECIDED.
#
# A source check passes while one of the two edges is computed and the other
# is not, which is exactly the shape this whole feature keeps being caught by.
# So the values `chart_creator` hands the stamper are read off a spy.
# --------------------------------------------------------------------------

def _params_with(recipe, tmp_path: Path):
    from workflow.chart_creator import ChartParams
    return ChartParams(instrument=recipe.instrument, paper=recipe.paper,
                       target_name="EndsTest", chart_notes=NOTE,
                       stamp_commands=False, layout_recipe=recipe)


def _creator(tmp_path: Path):
    from core.settings import AppSettings
    from workflow.chart_creator import ChartCreator

    class _FM:
        def chart_stem(self, cal_target: bool = False) -> str:
            return "EndsTest"
    return ChartCreator(runner=None, file_mgr=_FM(), settings=AppSettings())


def _end_reserves_handed_over(monkeypatch, tmp_path: Path, **over):
    """(top, bottom) the real caller passes to the real stamper."""
    from workflow import tiff_metadata as tm
    from workflow.layout_engine.presets import LayoutRecipe

    seen: dict = {}

    def spy(paths, lines, text_edge_mm=0.0, clip_band_mm=0.0, font_family="",
            size_pt=0.0, clip_reach_mm=-1.0, gap_mm=0.0,
            text_edge_top_mm=-1.0, text_edge_bottom_mm=-1.0,
            patch_gap_mm=0.0):
        seen.update(side=text_edge_mm, top=text_edge_top_mm,
                    bottom=text_edge_bottom_mm)

    monkeypatch.setattr(tm, "stamp_chart_metadata", spy)
    rec = LayoutRecipe.from_dict({
        "instrument": "CM", "paper": "A4", "text_edge_top_mm": 4.0,
        "text_edge_mm": 4.0, "text_edge_clip_mm": 4.0,
        "helper_markers": False, "helper_marker_edge_mm": 4.0,
        "helper_marker_len_mm": 2.0, "helper_markers_top_bottom": True,
        "helper_markers_sides": True, **over})
    cc = _creator(tmp_path)
    monkeypatch.setattr(type(cc), "_should_use_engine", lambda self, p: True)
    monkeypatch.setattr(type(cc), "_count_patches_in_ti1",
                        lambda self, p: 100)
    cc._stamp_tiff_metadata([_sheet(tmp_path / "s.tif")],
                            _params_with(rec, tmp_path))
    return seen


def test_the_caller_hands_over_both_ends_marker_aware(
        monkeypatch, tmp_path: Path) -> None:
    """Top and bottom are each computed, and each sees the markers."""
    plain = _end_reserves_handed_over(monkeypatch, tmp_path,
                                      text_edge_top_mm=12.0,
                                      text_edge_mm=5.0)
    assert plain["top"] == pytest.approx(12.0)
    assert plain["bottom"] == pytest.approx(5.0)
    assert plain["side"] == pytest.approx(4.0)

    # The markers on the TOP/BOTTOM edges raise both ends to 4 + 2 + 1.
    marked = _end_reserves_handed_over(monkeypatch, tmp_path,
                                       helper_markers=True,
                                       helper_markers_top_bottom=True,
                                       helper_markers_sides=False)
    assert marked["top"] == pytest.approx(7.0)
    assert marked["bottom"] == pytest.approx(7.0)
    # …and the SIDES checkbox, which is about the other pair of edges, does
    # not decide the ends. This is the fault: with "Sides" off the note used
    # to fall back to "Clip" at 4.0 and print inside the 4.0 to 6.0 mm comb.
    assert marked["side"] == pytest.approx(4.0)

    # "Top/bottom" OFF means no dashes on those edges, so nothing to keep off.
    unmarked = _end_reserves_handed_over(monkeypatch, tmp_path,
                                         helper_markers=True,
                                         helper_markers_top_bottom=False,
                                         helper_markers_sides=True)
    assert unmarked["top"] == pytest.approx(4.0)
    assert unmarked["bottom"] == pytest.approx(4.0)
