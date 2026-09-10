"""Text on any of the four sides is never dropped, and the overlap is said in red.

Knut's ruling, 2026-09-10, correcting what shipped in 4.2.3:

    "For the right margin, the text must still be visible, even if the patch
     area overlaps on the right Run Chart Notes text. Else the user will not
     notice that it is silently dropped, like you now do. The user must be given
     the chance to see that something is wrong, and then adjust the margins to
     place the patch area further in on the paper, so that the chart notes can
     be visible. […] For the Strip labels, we previously designed a warning
     message that should come (in the message field in Measured from Preview
     frame) if the text is overlapping with the patch area due to the margins.
     This should also be implemented for text defined for the right margin, when
     Run Chart Notes are defined or 'Stamp settings used on the chart' is
     selected, or when Clip border content is defined (for either left or right
     side) and also for the bottom margin, when sheet text (custom text field)
     is defined. They should all behave the same way."

Four things have to hold, and this file is one section per thing:

1. the law is one law, in `workflow/text_edge_fit.py`, and the stamper reads its
   legibility floor from there rather than keeping a second copy that can drift;
2. the stamper prints the note over the patches rather than dropping it, while
   the page-edge reserve still holds;
3. the tab raises a warning for each of the four sides, naming that side and the
   boxes that fix it;
4. **and it says nothing on a chart with room to spare.** A warning that is
   always on is worse than none, so the negative half is tested with the same
   weight as the positive one.
"""
from __future__ import annotations

import os
from dataclasses import replace

import numpy as np
import pytest
import tifffile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PyQt6")

from PyQt6.QtCore import Qt                                    # noqa: E402
from PyQt6.QtWidgets import QApplication                       # noqa: E402

from workflow import text_edge_fit as tef                      # noqa: E402
from workflow.layout_engine.presets import LayoutRecipe        # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


# ===================================================================== 1 ====
# One law, in one place

def test_the_stamper_takes_its_legibility_floor_from_the_shared_module():
    """The panel PREDICTS what the stamper will do, so they must share a floor.

    Nothing can travel up from the stamper: it runs once, at build time, on a
    chart the user has already committed to, while the panel has to say "this
    will overlap" while they are still moving the spin boxes. The prediction is
    only true while both sides read the same number, so the stamper is not
    allowed a copy of its own.
    """
    import inspect

    import workflow.tiff_metadata as tm
    assert tm._MIN_NOTE_STRIP_PX == tef.NOTE_MIN_STRIP_PX
    assert tm._NOTE_PATCH_GAP_PX == tef.NOTE_PATCH_GAP_PX
    # …AND IT IS THE SAME NUMBER BECAUSE IT WAS FETCHED, NOT BECAUSE IT WAS
    # RETYPED TO MATCH. Equality alone cannot tell those apart: a copy that
    # agrees today is exactly the copy that drifts tomorrow, and 11 == 11 either
    # way. `inspect.getsource` is what distinguishes them.
    src = inspect.getsource(tm)
    assert "_MIN_NOTE_STRIP_PX = text_edge_fit.NOTE_MIN_STRIP_PX" in src, (
        "the stamper keeps its own copy of the legibility floor, so the panel's "
        "prediction can drift away from what the stamper actually does")
    assert "_NOTE_PATCH_GAP_PX = text_edge_fit.NOTE_PATCH_GAP_PX" in src


def test_the_floor_is_a_distance_on_paper_not_a_count_of_pixels():
    """The same sheet gives the note very different room at different dpi."""
    coarse = tef.note_min_width_mm(200)
    fine = tef.note_min_width_mm(600)
    assert coarse > fine, "a pixel floor must become a smaller distance at a finer raster"
    assert abs(coarse - 1.397) < 0.01 and abs(fine - 0.4657) < 0.01, (
        f"measured floors moved: {coarse:.4f} / {fine:.4f} mm")


def test_the_photo_card_that_lost_its_line_is_the_case_that_warns():
    """The 10 x 15 cm card, by its own shipped numbers.

    `ui/tabs/tab_chart.py` builds it with a 5.0 mm right margin and the family's
    4.0 mm "Clip", at 300 dpi. 5.0 less the reserve and the 0.34 mm patch guard
    is 0.66 mm of paper, and a line at the legibility floor needs 0.93 mm. That
    0.27 mm is the whole of what 4.2.3 threw the note away for.
    """
    o = tef.chart_note_overlap("right", 5.0, 4.0, 300)
    assert o is not None, "the card that lost its line does not warn"
    assert 0.2 < o.overlap_mm < 0.35, f"the shortfall moved: {o.overlap_mm:.3f} mm"


@pytest.mark.parametrize("fn,args", [
    (tef.chart_note_overlap, ("right", 20.0, 4.0, 300)),
    (tef.strip_label_overlap, (17.0, 4.0, 7.0)),
    (tef.sheet_text_overlap, (13.0, 4.0, 2)),
    (tef.clip_content_overlap, ("left", 19.0, 19.0, 4.0)),
])
def test_a_side_with_room_to_spare_reports_nothing(fn, args):
    """THE NEGATIVE HALF, and it matters as much as the positive one."""
    assert fn(*args) is None, f"{fn.__name__} cried wolf on {args}"


def test_a_side_that_carries_no_text_reports_nothing():
    """No sheet text means no collision, however tight the bottom margin is."""
    assert tef.sheet_text_overlap(0.0, 4.0, 0) is None


# ===================================================================== 2 ====
# The stamper prints instead of dropping

_H, _W, _DPI = 900, 700, 300


def _sheet(tmp_path, right_white_px: int):
    """A sheet whose patch block leaves exactly *right_white_px* of white."""
    arr = np.full((_H, _W, 3), 255, dtype=np.uint8)
    arr[50:_H - 50, 50:_W - right_white_px, :] = 60
    p = tmp_path / f"sheet{right_white_px}.tif"
    tifffile.imwrite(str(p), arr, photometric="rgb", compression="lzw",
                     resolution=(_DPI, _DPI), resolutionunit="INCH")
    return p


def _added_ink(before, after):
    """Compositing only darkens, so every changed pixel is the note's own ink."""
    return (after < before).any(axis=2)


@pytest.mark.parametrize("right_white_px", [30, 55])
def test_a_margin_too_thin_for_a_line_is_stamped_over_the_patches(
        tmp_path, right_white_px):
    """4.2.3 returned here and printed nothing. It must print.

    Two widths, because they fail differently: 30 px is narrower than
    `_MIN_STRIP_WIDTH_PX` so no white band is detected at all, and 55 px finds a
    band that the 4 mm reserve then leaves too little of.
    """
    from workflow.tiff_metadata import stamp_chart_metadata
    p = _sheet(tmp_path, right_white_px)
    before = tifffile.imread(str(p))
    edge_mm = 4.0
    stamp_chart_metadata([p], ["Canon PRO-1000, PhotoRag 308, CM off"], edge_mm)
    ink = _added_ink(before, tifffile.imread(str(p)))
    assert ink.any(), (
        f"with {right_white_px} px of white margin the note was dropped, which "
        "is the silent failure Knut's ruling of 2026-09-10 forbids")
    right = int(np.flatnonzero(ink.any(axis=0)).max())
    to_edge = (_W - 1 - right) * 25.4 / _DPI
    assert to_edge >= edge_mm - 0.1, (
        f"the note ends {to_edge:.2f} mm from the paper edge and the reserve "
        f"asks for {edge_mm:.2f} mm")
    left = int(np.flatnonzero(ink.any(axis=0)).min())
    patch_right = _W - right_white_px
    assert left < patch_right, (
        "the premise failed: the note did not have to overlap anything")


def test_a_roomy_margin_is_still_stamped_beside_the_patches_not_over_them():
    """THE NEGATIVE HALF AGAIN: nothing that fitted before now overlaps."""
    import tempfile
    from pathlib import Path

    from workflow.tiff_metadata import stamp_chart_metadata
    with tempfile.TemporaryDirectory() as d:
        p = _sheet(Path(d), 120)
        before = tifffile.imread(str(p))
        stamp_chart_metadata([p], ["a note with plenty of room"], 4.0)
        ink = _added_ink(before, tifffile.imread(str(p)))
        assert ink.any(), "no note printed on a sheet with room to spare"
        left = int(np.flatnonzero(ink.any(axis=0)).min())
        assert left >= _W - 120, (
            f"the note starts at column {left} and the patch block ends at "
            f"{_W - 120}; with room to spare it must not touch the patches")


# ===================================================================== 3 ====
# The warning, on all four sides


class _Btn:
    def __init__(self, on=True):
        self._on = on

    def isChecked(self):
        return self._on


class _Edit:
    def __init__(self, text=""):
        self._t = text

    def text(self):
        return self._t


class _Settings:
    def get(self, key, default=None):
        return True if key == "use_chromiq_layout_engine" else default


class _Report:
    def __init__(self, right_mm):
        self.right_mm = right_mm


class _Tab:
    """Just enough TabChart for the notes builder to run."""

    _manual_btn = _Btn()
    _manual_layout_panel = object()
    _settings = _Settings()

    def __init__(self, recipe, notes="", stamp=False):
        self._recipe = recipe
        self._manual_chart_notes_edit = _Edit(notes)
        self._manual_stamp_cmd_check = _Btn(stamp)

    def _current_layout_recipe(self):
        return self._recipe


def _notes(r, *, notes="", stamp=False, report=None):
    from ui.tabs.tab_chart import TabChart
    return TabChart._engine_text_notes(_Tab(r, notes, stamp), report)


def _roomy() -> LayoutRecipe:
    """An i1Pro A4 chart with room on every side and nothing colliding."""
    r = LayoutRecipe()
    r.instrument, r.paper, r.layout_mode = "i1", "A4", "area_first"
    r.clip_border = False
    r.clip_content_mode = "off"
    r.show_strip_indicators, r.show_row_indicators = True, False
    r.margin_top = r.margin_right = r.margin_bottom = r.margin_left = 25.0
    r.text_edge_top_mm = r.text_edge_mm = r.text_edge_clip_mm = 4.0
    r.chart_text = ""
    r.stamp_command = False
    return r


def test_a_chart_with_room_to_spare_says_nothing_at_all(qapp):
    """THE NEGATIVE HALF. A warning that is always on is worse than none."""
    _all, over = _notes(_roomy(), notes="Canon PRO-1000", stamp=True,
                        report=_Report(25.0))
    assert over == [], f"a chart with 25 mm on every side warned: {over}"


def test_the_right_edge_warns_when_the_notes_run_over_the_patches(qapp):
    r = replace(_roomy(), margin_right=5.0)
    _all, over = _notes(r, notes="Canon PRO-1000 / PhotoRag 308",
                        report=_Report(5.0))
    assert len(over) == 1, f"expected one notice, got {over}"
    assert "chart notes down the right edge" in over[0]
    assert "“Right” under “Margins (mm)”" in over[0], (
        f"the notice does not name the box that fixes it: {over[0]}")


def test_a_chart_that_does_not_fill_its_page_is_judged_on_what_was_measured(qapp):
    """The typed margin is not the paper the note has, and using it cries wolf.

    "Right" says where the patch area is ALLOWED to start; the note has to fit
    between the paper edge and where the block actually ENDS. Measured on a
    120-patch A4 i1 chart with the right margin typed at 3 mm: 151.1 mm of white
    paper on the right. This is the "Measured from Preview" frame, so it
    measures.
    """
    r = replace(_roomy(), margin_right=3.0)
    assert _notes(r, notes="Canon PRO-1000", report=_Report(3.0))[1], (
        "the premise failed: 3 mm typed is meant to be a collision on paper")
    over = _notes(r, notes="Canon PRO-1000", report=_Report(151.1))[1]
    assert over == [], (
        f"151 mm of white paper on the right was reported as an overlap: {over}")


def test_the_right_edge_stays_quiet_when_no_note_is_defined(qapp):
    """Nothing is stamped, so nothing can collide."""
    r = replace(_roomy(), margin_right=5.0)
    _all, over = _notes(r, notes="", stamp=False, report=_Report(5.0))
    assert over == [], f"warned about a note that does not exist: {over}"


def test_the_stamp_settings_tick_box_is_enough_on_its_own(qapp):
    """Knut names both triggers: *"when Run Chart Notes are defined or 'Stamp
    settings used on the chart' is selected"*."""
    r = replace(_roomy(), margin_right=5.0)
    _all, over = _notes(r, notes="", stamp=True, report=_Report(5.0))
    assert len(over) == 1 and "chart notes down the right edge" in over[0]


def test_the_top_warns_when_the_strip_letters_run_into_the_patches(qapp):
    r = replace(_roomy(), margin_top=6.0)
    _all, over = _notes(r, report=_Report(25.0))
    assert len(over) == 1, f"expected one notice, got {over}"
    assert "strip letters across the top" in over[0]
    assert "“Top” under “Margins (mm)”" in over[0]


def test_the_label_offset_moves_the_letters_and_the_warning_follows(qapp):
    """*"for the strip labels it may additionally be moved by 'Label offset'"*.

    The margin that was fine becomes too small once the letters are pushed down
    into it, and the warning has to know that.
    """
    r = replace(_roomy(), margin_top=12.0)
    assert _notes(r, report=_Report(25.0))[1] == [], "the premise failed"
    r2 = replace(r, strip_label_offset_mm=5.0)
    over = _notes(r2, report=_Report(25.0))[1]
    assert len(over) == 1 and "strip letters" in over[0], (
        f"a 5 mm label offset into a 12 mm margin went unreported: {over}")


@pytest.mark.parametrize("lines,phrase", [
    (("Hahnemuehle Photo Rag", False), "sheet text along the bottom runs"),
    (("Hahnemuehle Photo Rag", True), "two lines of sheet text"),
])
def test_the_bottom_warns_and_counts_its_lines(qapp, lines, phrase):
    """One line or two, said as one or two. "(s)" is not written here."""
    text, stamp = lines
    r = replace(_roomy(), margin_bottom=5.0, chart_text=text,
                stamp_command=stamp)
    _all, over = _notes(r, report=_Report(25.0))
    assert len(over) == 1, f"expected one notice, got {over}"
    assert phrase in over[0], over[0]
    assert "(s)" not in over[0]


def test_the_clip_border_content_is_asked_about_on_its_own_edge(qapp):
    """It stays silent today, and the predicate is what decides that.

    `instruments.geom_from_build_kwargs` raises the clip-side margin to the
    band's width, so the band ends exactly where the first patch column starts.
    The question is asked anyway, and the arithmetic is checked here, so a
    geometry that stops raising the margin is reported rather than shipped.
    """
    r = _roomy()
    r.clip_border, r.clip_content_mode = True, "notes"
    r.clip_border_width_mm, r.clip_side = 26.0, "left"
    r.margin_left = 6.0
    _all, over = _notes(r, report=_Report(25.0))
    assert [w for w in over if "clip border content" in w] == [], (
        "the clip band is raising the margin, so nothing may be reported here")
    o = tef.clip_content_overlap("left", 10.0, 26.0, 4.0)
    assert o is not None and abs(o.overlap_mm - 16.0) < 0.01, (
        f"the predicate that guards that day is wrong: {o}")


def test_all_four_sides_can_be_wrong_at_once(qapp):
    """*"They should all behave the same way."* So they stack, they do not race."""
    r = replace(_roomy(), margin_top=6.0, margin_bottom=5.0, margin_right=5.0,
                chart_text="Hahnemuehle Photo Rag")
    _all, over = _notes(r, notes="Canon PRO-1000", report=_Report(5.0))
    joined = " ".join(over)
    assert len(over) == 3, f"expected three notices, got {over}"
    for phrase in ("chart notes down the right edge",
                   "strip letters across the top",
                   "sheet text along the bottom"):
        assert phrase in joined, f"{phrase!r} missing from {over}"


def test_the_overlaps_reach_the_information_icon_as_well(qapp):
    """The ⓘ keeps everything; the message field takes the overlaps."""
    r = replace(_roomy(), margin_top=6.0)
    every, over = _notes(r, report=_Report(25.0))
    assert over and all(w in every for w in over)


# ===================================================================== 4 ====
# …in red, in the message field of "Measured from Preview"

_RED = "#e0564b"


def _panel(qapp, **kw):
    from ui.margin_inspector_panel import MarginInspectorPanel
    from workflow.margin_inspector import MarginReport
    p = MarginInspectorPanel()
    rep = MarginReport(left_mm=25.0, right_mm=5.0, top_mm=25.0, bottom_mm=25.0,
                       strip_width_mm=8.0, strip_length_mm=232.1,
                       page_w_mm=210.0, page_h_mm=297.0)
    p.update_report(rep, [], thresholds_defined=True, notify=True, **kw)
    return p


def test_an_overlap_is_shown_on_the_panel_itself_and_in_red(qapp):
    """Knut asked for this place and this colour by name.

    The alternative was tried and it failed him: these notices moved off the
    panel's surface onto its ⓘ on 2026-09-04, and an ⓘ is only read if it is
    asked for. A chart whose text runs over its own patches has to be visible
    without a hover.
    """
    p = _panel(qapp, overlap_warnings=["⚠ The chart notes run over the patches."],
               text_warnings=["⚠ The chart notes run over the patches."])
    assert "run over the patches" in p.status_message(), (
        "the overlap is not on the panel's own surface")
    assert _RED in p._status.styleSheet().lower(), (
        f"the message field is not red: {p._status.styleSheet()!r}")
    assert p._status.alignment() & Qt.AlignmentFlag.AlignLeft, (
        "a five-line paragraph is centred, which is markedly harder to read")


def test_a_margin_violation_and_an_overlap_are_both_shown(qapp):
    """A chart can meet every instrument minimum and still print over itself.

    That is the 10 x 15 cm photo card exactly, so the first notice may not
    swallow the second.
    """
    from workflow.margin_inspector import Violation
    p = _panel(qapp, overlap_warnings=["⚠ The chart notes run over the patches."],
               text_warnings=[])
    p._update_status([Violation(edge="Right", measured_mm=5.0, threshold_mm=8.0)],
                     thresholds_defined=True, notify=True,
                     overlap_warnings=["⚠ The chart notes run over the patches."])
    said = p.status_message()
    assert "Right margin" in said and "run over the patches" in said, said


def test_no_overlap_leaves_the_green_verdict_alone(qapp):
    """THE NEGATIVE HALF, on the panel."""
    p = _panel(qapp, overlap_warnings=[], text_warnings=[])
    assert p.status_message() == "Margins: OK", p.status_message()
    assert p._status.alignment() & Qt.AlignmentFlag.AlignHCenter


def test_a_theme_switch_repaints_the_overlap_rather_than_losing_it(qapp):
    """`set_appearance` replays the last report, and it has to carry the new
    argument with it or a theme change silently clears the warning."""
    p = _panel(qapp, overlap_warnings=["⚠ The chart notes run over the patches."],
               text_warnings=[])
    p.set_appearance("light")
    assert "run over the patches" in p.status_message()
