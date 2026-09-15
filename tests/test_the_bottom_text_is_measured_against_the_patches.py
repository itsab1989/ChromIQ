"""The bottom-text height warning asks where the patches really are.

Knut, 2026-09-14, testing beta 15 on the CR30 Letter 792-patch straight preset
with a custom Sheet text at Size auto:

    When bottom margin is 11.0mm there is a warning ... You can clearly see
    that there is ample space both on top and below the bottom text line, so
    the warning should not happen. Measurements are obviously calculated wrong.
    Bottom margin in Measured from Preview shows 12.8mm.

    It also seems that the bottom text is not shrunk while in size = auto ...
    This means that the size = auto setting should shrink size when the height
    or width comes close to its limits.

**MEASURED ON THE APP'S OWN SHEETS** (`scripts/drive_182_knut_bottom_text_height.py`,
his preset, bottom margin swept and the ink read off each rendered TIFF by a
two-render difference with the geometry and the seed pinned):

| requested margin | patches end | the text's ink | clear gap | the panel, before |
|---|---|---|---|---|
| 7.5 mm | 13.84 | 7.37 to 10.41 | **3.43** | warns |
| 11.0 mm | 15.62 | 7.37 to 10.41 | **5.21** | warns |
| 11.5 mm | 15.88 | 7.37 to 10.41 | 5.47 | quiet |
| 16.0 mm | 23.75 | 7.37 to 10.41 | 13.34 | quiet |

Three facts come out of that table and each one is pinned below.

1. **The text never moves with the margin.** It is anchored on the PAPER EDGE,
   at `sheet_text_bottom_mm`, so the bottom margin cannot push it.
2. **The patches do move, and never come near it**, because
   `raster._furniture_reserves_mm` holds a band back below the margin.
3. So the old test, "the requested margin less B against the line's height",
   compared two numbers neither of which was the distance in question, and
   flipped at 11.5 mm on a sheet that does not change.

**AND THEN THE PREDICTION WAS WRONG THE OTHER WAY, AND KNUT RULED IT OUT
ALTOGETHER.** #182, 2026-09-15:

    "the calculations should use the Measured from Preview numbers in the
     calculations if text fit. This simplifies very much the calculation and it
     does not need to calculate across many page sizes or other searches ... It
     is also a special case for hexagonal patches, or when "Use ChromIQ layout
     engine..." OFF, that set margins does not always match closely the
     Measured from Preview margins ... they are only usable after the Measured
     from Preview margin values have been completed (after a Generate Chart has
     been performed)."

The case that proves him right is his own chart: CR30 / A4 / area_first /
**hexagonal** patches / bottom margin 13.0 / "B" 10.0 / markers 4.0 + 2.0 /
Size auto / a ten-placeholder custom line plus the layout summary, at 200 dpi.
`predicted_patch_bottom_mm` answered **18.60 mm**, so the panel believed
8.60 mm of room for 8.38 mm of text and said nothing;
`margin_inspector.measure_from_engine` answers **15.822 mm**, which is the 15.8
the frame showed him, and against that the two lines are 2.56 mm short. **A
FLAT-TOP HONEYCOMB'S LAST ROW HANGS BELOW THE GRID BOX `geometry.compute`
RETURNS**, so a prediction built out of `compute` and `placement` cannot see
it. Measured off his own TIFF at 200 dpi: the bottom helper markers run 4.06 to
6.22 mm, and from 10.16 mm (the "B" anchor) upward the ink is unbroken, so
there is no clear paper anywhere between the text and the patches.

So the prediction is gone, and with it `margin_rise_that_clears_mm`,
`_larger_paper_note`, `_bottom_clears_with`, `lowering_b_clears` and
`markers_off_clears`: every one existed to answer *"how much more margin clears
it"*, which under this rule nothing asks, because the answer is a measurement
of a sheet that has not been drawn. The message names what is short, names the
controls, and asks for a Generate Chart.
"""
from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest                                                   # noqa: E402

from workflow import text_edge_fit as tef                       # noqa: E402


def test_his_case_is_quiet_and_a_real_collision_is_not():
    """The two ends of the table above, in the arithmetic that decides them.

    MUTATION: give `bottom_text_block_overlap` the requested margin (11.0)
    instead of the patch bottom (15.62) and the first assertion goes red.
    """
    # his sheet: patches end 15.62 mm up, the block is anchored at 7.0 and one
    # line of auto type has a 4.19 mm box
    assert tef.bottom_text_block_overlap(15.62, 7.0, 1, 4.19) is None
    # …and the same sheet with a 28 pt line, whose box is 12.06 mm
    over = tef.bottom_text_block_overlap(15.62, 7.0, 1, 12.06)
    assert over is not None
    assert over.available_mm == pytest.approx(8.62)
    assert over.overlap_mm == pytest.approx(3.44)


def test_the_old_question_gave_the_wrong_answer_on_his_sheet():
    """Kept as a record of what changed, because the numbers are his.

    The requested margin was 11.0 and "B" resolves to 7.0 on a chart with the
    helper markers on, so the old room was 4.0 mm against a 4.19 mm line: it
    warned. The real room, patch bottom less the anchor, is 8.62 mm.
    """
    assert tef.sheet_text_overlap(11.0, 7.0, 1, 4.19) is not None
    assert tef.bottom_text_block_overlap(15.62, 7.0, 1, 4.19) is None


def test_the_two_functions_are_one_piece_of_arithmetic():
    """`sheet_text_overlap` is the same subtraction with different inputs, and
    it delegates rather than repeating it.

    MUTATION: give either one its own `_overlap` call and a later change will
    move one and not the other.
    """
    import inspect
    body = inspect.getsource(tef.sheet_text_overlap).split('"""')[-1]
    assert "bottom_text_block_overlap(" in body
    assert "_overlap(\"bottom\"" not in body, (
        "sheet_text_overlap does the subtraction itself again")


def test_the_engine_reserve_and_the_line_box_quote_one_constant():
    """`_furniture_reserves_mm` held back a literal 4.2 mm per line while
    `SHEET_TEXT_LINE_MM` was the same number in three other places. The reserve
    is what the auto shrink now fits the type into, so they must not drift.

    IT ASKS THE FUNCTION, NOT THE SOURCE. The first version of this test
    grepped for the constant's name, which is satisfied by a literal that
    happens to equal it; `SHEET_TEXT_LINE_MM` IS 4.2, so the "mutation" it
    named changed nothing. Moving the constant and watching the reserve move
    with it is the same claim, proved.

    MUTATION: put `4.2 * nlines` back and this goes red.
    """
    from workflow.layout_engine import raster
    kw = {"dpi": 300, "chart_text": "x", "stamp_command": False,
          "text_edge": 4.0, "draw_indicators": False}

    class _G:                       # only the fields the reserve reads
        txhisl = 3.0
        helper_markers = False
        margin_b = 6.0
    before = raster._furniture_reserves_mm(_G(), kw)[1]
    import workflow.text_edge_fit as _tef
    keep = _tef.SHEET_TEXT_LINE_MM
    try:
        _tef.SHEET_TEXT_LINE_MM = keep + 3.0
        after = raster._furniture_reserves_mm(_G(), kw)[1]
    finally:
        _tef.SHEET_TEXT_LINE_MM = keep
    assert round(after - before, 3) == 3.0, (
        "the bottom reserve does not follow SHEET_TEXT_LINE_MM, so the band "
        "the renderer holds back and the box the shrink fits into can drift")


def test_auto_shrinks_on_the_height_as_well_as_the_width():
    """*"the size = auto setting should shrink size when the height or width
    comes close to its limits."*

    The loop only ever measured the width. It now also requires the line's box
    to fit the room the engine set aside for it.

    **AND THE ROOM IS THAT BAND AS THE DPI CAN DRAW IT.** The first version of
    this test only grepped `render_pages` for `_fits_h`, and it was green while
    the term it names was unsatisfiable at 150, 240, 300 and 360 dpi, so every
    "Size auto" line was shrunk to the 7 pt floor whatever room it had, at the
    default resolution. `tests/test_the_auto_sheet_text_does_not_shrink_with_
    the_dpi.py` measures that on rendered sheets; this one keeps the two terms
    in the loop and keeps the height term off the bare constant.

    MUTATION: drop the `_fits_h` term, or compare it with
    `text_edge_fit.SHEET_TEXT_LINE_MM`, and this goes red.
    """
    import inspect
    from workflow.layout_engine import raster
    src = inspect.getsource(raster.render_pages)
    assert "_fits_h" in src and "_fits_w" in src
    assert "if _fits_w and _fits_h:" in src
    assert "sheet_text_reserve_mm(" in src, (
        "the height term must compare against the reserve this dpi can draw")
    code = "\n".join(l for l in src.splitlines()
                      if not l.strip().startswith("#"))
    assert "_tef.SHEET_TEXT_LINE_MM" not in code.split("_fits_h")[1][:400]


@pytest.mark.parametrize("dpi", (150, 200, 240, 300, 360, 600))
def test_a_typed_size_above_the_reserve_is_what_can_collide(dpi):
    """The line box against the room the engine reserves, at the sizes that
    matter. Auto and 7 pt fit it; 12 pt and up do not, and a typed size never
    shrinks (Knut: *"Manually defined size value does not shrink"*), so the
    warning is the only remedy there.

    **AT EVERY RESOLUTION.** This test used to ask at 200 dpi alone, which is
    one of the two the pixel rounding is kind at: at 150, 240, 300 and 360 the
    7 pt floor measures 4.2333 mm and the same assertion against the bare 4.2
    constant is false. It picked the dpi that hid the fault.
    """
    from workflow.layout_engine import raster
    room = raster.sheet_text_reserve_mm(dpi)
    line = lambda pt: raster.sheet_text_line_mm(          # noqa: E731
        pt * 25.4 / 72.0 if pt else 0.0, "Inter", False, False, dpi)
    assert line(0) <= room, "auto does not fit the band it is given"
    assert line(7) <= room, "the shrink floor does not fit the band"
    assert line(12) > room
    assert line(28) > room


def test_the_panel_measures_the_patch_bottom_rather_than_predicting_it():
    """Knut's ruling, in the code: `report.bottom_mm` and nothing else.

    MUTATION: put `predicted_patch_bottom_mm(r, geom)` back and this goes red,
    on three separate assertions.
    """
    import inspect
    from ui.tabs import tab_chart as tc
    notes = inspect.getsource(tc.TabChart._engine_text_notes)
    body = "\n".join(l for l in notes.splitlines()
                      if not l.strip().startswith("#"))
    assert "_patch_bottom = _meas_b" in body, (
        "the bottom check no longer reads the measured report")
    assert '_edge("bottom_mm")' in body, (
        "the measured bottom edge is not read off the report")
    assert "predicted_patch_bottom_mm" not in body, (
        "the retired prediction is back in the notice builder")
    for gone in ("predicted_patch_bottom_mm", "margin_rise_that_clears_mm",
                 "_larger_paper_note", "_bottom_clears_with",
                 "lowering_b_clears", "markers_off_clears"):
        assert not hasattr(tc, gone), (
            f"{gone} is back; it can only answer 'how much more margin clears "
            f"it', which Knut's ruling of 2026-09-15 does not ask")
    # …and it does not reach through `self`, which the blanket except eats.
    assert "self._predicted_patch_bottom_mm" not in notes
    assert not hasattr(tc.TabChart, "_predicted_patch_bottom_mm")
    # …and it asks the tab for NOTHING, because a counter that can raise inside
    # this blanket `except` loses every warning on the panel.
    # …scoped to the bottom block: the right-edge stamp a hundred lines up
    # legitimately asks `_estimate_patch_total`, because the seed and the
    # patch count are printed in THAT line.
    start = body.index("_patch_bottom = _meas_b")
    block = body[start:body.index("AND THE SAME BLOCK HAS A WIDTH", start)] \
        if "AND THE SAME BLOCK HAS A WIDTH" in body[start:] \
        else body[start:start + 4000]
    assert "_onscreen_patch_total" not in block
    assert "_estimate_patch_total" not in block


def test_his_own_chart_is_warned_about_now_and_was_not_before():
    """THE WHOLE BUG, IN ONE SUBTRACTION, ON THE NUMBERS OFF HIS SHEET.

    The recipe, the anchor and the line box are his: CR30 / A4 / area_first /
    hexagonal / "B" 10.0 with the markers at 4.0 + 2.0 (so the anchor is "B",
    10.0 mm), two lines of Size-auto type at 200 dpi (4.191 mm a line, 8.382 mm
    for the block).

    MUTATION: feed it 18.60, which is what `geometry.compute` and
    `geometry.placement` answered, and the first assertion goes red.
    """
    assert tef.bottom_text_block_overlap(18.601, 10.0, 2, 4.191) is None, (
        "the retired prediction is what made this sheet quiet")
    over = tef.bottom_text_block_overlap(15.822, 10.0, 2, 4.191)
    assert over is not None, (
        "the measured patch bottom must warn: 8.38 mm of text into 5.82 mm")
    assert over.available_mm == pytest.approx(5.822, abs=0.01)
    assert over.needed_mm == pytest.approx(8.382, abs=0.01)
    assert over.overlap_mm == pytest.approx(2.560, abs=0.01)


def test_the_measured_bottom_on_his_own_chart_is_the_number_he_quoted():
    """`measure_from_engine` off his `channels.json` answers 15.8, not 18.6.

    His chart is in the repository's own fixtures so this is not a claim about
    a file on somebody's Desktop. If the fixture is absent the test skips
    rather than passing on nothing.

    MUTATION: read the grid box instead of the recorded patch rectangles and
    the answer moves back up to 18.6.
    """
    from workflow.margin_inspector import measure_from_engine
    ch = (Path(__file__).resolve().parents[1]
          / "tests/fixtures/charts/knut_cr30_a4_hex_bottom_text.channels.json")
    if not ch.is_file():
        pytest.skip("Knut's hexagonal chart fixture is not in the tree")
    eng = measure_from_engine(ch, 0)
    assert eng is not None, "the fixture is not readable as an engine chart"
    report, _ruler = eng
    assert report.bottom_mm == pytest.approx(15.822, abs=0.01), (
        f"the measured bottom moved: {report.bottom_mm}")


def test_the_notes_survive_a_tab_that_cannot_count_its_patches():
    """THE TRAP THIS FILE WAS WRITTEN INSIDE, AND IT CAUGHT ME.

    `_engine_text_notes` wraps its whole body in one `except Exception: pass`.
    The first version of the height fix called
    `self._predicted_patch_bottom_mm`, the stand-in tabs in two other test
    files do not have that attribute, and the AttributeError did not lose the
    height sentence: it lost **every warning the method produces**, on every
    side. Four tests went quiet at once and the silence read as the fix
    working.

    So the rule is pinned here rather than remembered: a tab that can answer
    nothing about its patch count still gets all its other notices. The recipe
    is the one `test_all_four_sides_can_be_wrong_at_once` uses, which is known
    to earn three of them.

    MUTATION: reach through `self` for the prediction again and this goes red.
    """
    from dataclasses import replace

    from ui.tabs.tab_chart import TabChart
    from tests.test_text_is_never_dropped_on_any_side import (_roomy, _Btn,
                                                              _Edit, _Settings)

    class _BareTab:
        """A tab that knows its recipe and nothing else at all."""

        def _current_mode(self):
            """The gate `_engine_text_notes` really asks, NOT `_manual_btn`.

            The FROM PROFILE GAMUT module is the Manual page with its own
            targen section, and it leaves that BUTTON unchecked; keying the
            notices on it turned every one of them off there. This stand-in
            carries no `_manual_btn` on purpose, so a revert to the button
            spelling makes the file go red rather than quietly produce no
            notices at all.
            """
            return "manual"
        _manual_layout_panel = object()
        _settings = _Settings()

        def __init__(self, r):
            self._recipe = r
            self._manual_chart_notes_edit = _Edit("Canon PRO-1000")
            self._manual_stamp_cmd_check = _Btn(False)

        def _current_layout_recipe(self):
            return self._recipe

    r = replace(_roomy(), margin_top=6.0, margin_bottom=5.0, margin_right=5.0,
                chart_text="Hahnemuehle Photo Rag")
    from tests.margin_reports import report_for
    _warns, over = TabChart._engine_text_notes(_BareTab(r), report_for(r))
    assert over, (
        "a tab that cannot count its patches lost every notice on the panel, "
        "which is what one blanket except does with one AttributeError")
    assert any("chart notes down the right edge" in w for w in over), over
