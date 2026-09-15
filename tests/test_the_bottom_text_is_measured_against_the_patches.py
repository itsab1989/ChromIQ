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

**AND THE MEASURED REPORT CANNOT ANSWER IT EITHER.** It describes the chart in
the preview, not the settings being edited: driven across those same seven
margins, `report.bottom_mm` was **10.29 mm every single time**, which is why
Knut read 12.8 mm in "Measured from Preview" while his box said 11.0.
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


def test_the_panel_predicts_the_patch_bottom_rather_than_measuring_it():
    """The prediction runs `geometry.compute` and `geometry.placement`, the two
    functions `render_pages` lays the page out with, so it cannot drift from
    the sheet. Driven against the app's own TIFFs it agreed to within 0.03 mm
    on all seven margins.

    MUTATION: read `report.bottom_mm` again and this goes red.
    """
    import inspect
    from ui.tabs import tab_chart as tc
    src = inspect.getsource(tc.predicted_patch_bottom_mm)
    assert "geometry.compute" in src and "geometry.placement" in src
    notes = inspect.getsource(tc.TabChart._engine_text_notes)
    assert "predicted_patch_bottom_mm(r, geom)" in notes
    assert 'getattr(report, "bottom_mm"' not in notes
    # …and it does not reach through `self`, which the blanket except eats.
    assert "self._predicted_patch_bottom_mm" not in notes
    assert not hasattr(tc.TabChart, "_predicted_patch_bottom_mm"), (
        "the method is back, and a fake tab without it loses every warning")
    # …and it asks the tab for NOTHING, because the answer does not depend on
    # the patch count (see the next test). A counter called from inside this
    # blanket `except` is a hazard for no gain.
    # …scoped to the bottom block: the right-edge stamp a hundred lines up
    # legitimately asks `_estimate_patch_total`, because the seed and the
    # patch count are printed in THAT line.
    start = notes.index("_patch_bottom = predicted_patch_bottom_mm")
    block = "\n".join(
        l for l in notes[start:notes.index("AND THE SAME BLOCK HAS A WIDTH",
                                           start)].splitlines()
        if not l.strip().startswith("#"))
    assert "_onscreen_patch_total" not in block
    assert "_estimate_patch_total" not in block


def test_the_prediction_does_not_depend_on_the_patch_count():
    """`steps_in_pass` is the page's CAPACITY, so the count cannot move it.

    This is what made the counter plumbing removable, and if a layout change
    ever makes the count matter, this is the test that says so: it goes red,
    and the caller has to decide what to feed it again.
    """
    from dataclasses import replace
    from ui.tabs.tab_chart import predicted_patch_bottom_mm
    from workflow.layout_engine import instruments
    from workflow.layout_engine.presets import LayoutRecipe
    for mode in ("area_first", "patch_first"):
        r = LayoutRecipe()
        r.instrument, r.paper, r.dpi = "CM", "A4", 150
        r.layout_mode, r.use_instrument_margins = mode, False
        r.margin_top, r.margin_bottom = 10.0, 15.0
        r.margin_left = r.margin_right = 10.0
        r.chart_text = "x"
        g = instruments.geom_from_build_kwargs(r.build_kwargs())
        answers = {predicted_patch_bottom_mm(r, g, n)
                   for n in (12, 60, 120, 480, 2000, 100_000)}
        assert len(answers) == 1, f"{mode}: the count now moves it, {answers}"
        assert predicted_patch_bottom_mm(r, g) in answers


@pytest.mark.parametrize("mode", ("area_first", "patch_first"))
def test_the_prediction_matches_the_renderer_on_a_real_layout(mode, tmp_path):
    """A REAL SHEET, not the same formula written out twice.

    The first version of this test recomputed the placement longhand and
    compared the two copies, which catches a typo and nothing else: if the
    model is wrong, both copies are wrong together. This builds the chart and
    reads the patch rectangles the renderer recorded.

    THE BOUND IS ASYMMETRIC ON PURPOSE. Predicting the patches DEEPER than
    they are can only warn early; predicting them higher can hide a collision.
    Measured across three papers and three bottom margins: patch-first agrees
    to 0.06 mm, area_first runs from 1.42 mm deep to 0.13 mm high, because the
    prediction is of a FULL page and a 480-patch chart does not fill every row
    of one.
    """
    from dataclasses import replace
    from ui.tabs.tab_chart import predicted_patch_bottom_mm
    from workflow.layout_engine import instruments, papers
    from workflow.layout_engine.chart import build_from_recipe
    from workflow.layout_engine.presets import LayoutRecipe
    ti1 = Path(__file__).resolve().parents[1] / "tests/fixtures/charts/cm_a4_480p_2pages.ti1"
    r = LayoutRecipe()
    r.instrument, r.paper, r.dpi = "CM", "A4", 150
    r.layout_mode, r.use_instrument_margins = mode, False
    r.margin_top, r.margin_bottom = 10.0, 15.0
    r.margin_left = r.margin_right = 10.0
    r.chart_text = "x"
    res, _used = build_from_recipe(
        str(ti1), str(tmp_path / "s"),
        replace(r, randomize=True, seed_fixed=True, seed=123456789))
    rects = [q for q in (res.strip_rects or []) if int(q.get("page", 0)) == 0]
    assert rects, "the build recorded no patch rectangles"
    _w, h = papers.dimensions_mm(r.paper)
    drawn = h - max(int(q["y"]) + int(q["h"]) for q in rects) * 25.4 / r.dpi
    geom = instruments.geom_from_build_kwargs(r.build_kwargs())
    pred = predicted_patch_bottom_mm(r, geom)
    assert pred is not None
    assert pred - drawn <= 0.2, (
        f"{mode}: the prediction puts the patches {pred - drawn:.2f} mm higher "
        f"than the sheet draws them, which is the direction that hides a "
        f"collision")
    assert drawn - pred <= 1.5, (
        f"{mode}: the prediction is {drawn - pred:.2f} mm deeper than the "
        f"sheet, which warns early")


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
    _warns, over = TabChart._engine_text_notes(_BareTab(r))
    assert over, (
        "a tab that cannot count its patches lost every notice on the panel, "
        "which is what one blanket except does with one AttributeError")
    assert any("chart notes down the right edge" in w for w in over), over


def _collision_recipe(margin_bottom: float = 11.0):
    """HIS OWN SHEET, from the preset he was testing.

    A hand-built Letter recipe will not do: on a plain area_first layout the
    patch bottom moves one for one with the margin, so the naive remedy works
    there and the test would prove nothing. The CR30 Letter 792-patch straight
    preset is where it does not (7.5 / 9 / 11 / 12 / 13 mm of margin put the
    patch bottom at 13.87 / 14.62 / 15.62 / 16.12 / 16.62), and it is the sheet
    Knut reported.
    """
    from dataclasses import replace
    from ui.tabs.tab_chart import KNUT_PRESETS
    from workflow.layout_engine.presets import LayoutRecipe
    preset = next(p for p in KNUT_PRESETS if p.slug ==
                  "cr30_letter_792p_2pages_portrait_w11_0mm_hexagonal_straight")
    return replace(LayoutRecipe.from_dict(preset.layout_recipe),
                   margin_bottom=float(margin_bottom), chart_text="x",
                   chart_text_size_mm=0.0)


def _overlap_at(r, rise: float, npat: int, reserve: float, lines: int,
                line_mm: float):
    """The overlap on the sheet that `margin_bottom + rise` really produces."""
    from dataclasses import replace
    from workflow.layout_engine import instruments
    from ui.tabs.tab_chart import predicted_patch_bottom_mm
    cand = replace(r, margin_bottom=float(r.margin_bottom) + float(rise))
    geom = instruments.geom_from_build_kwargs(cand.build_kwargs())
    bottom = predicted_patch_bottom_mm(cand, geom, npat)
    assert bottom is not None
    return tef.bottom_text_block_overlap(float(bottom), reserve, lines, line_mm)


def test_the_rise_the_message_names_really_clears_the_patches():
    """THE REMEDY IS A PROMISE, AND THE OBVIOUS NUMBER BREAKS IT.

    Raising the bottom margin by the size of the overlap does NOT clear the
    overlap, because the patch grid is re-fitted as the margin moves and the
    patch area's bottom edge travels roughly half a millimetre per millimetre
    asked for. Driven on screen on Knut's own preset at 28 pt and 48 pt: the
    message said 3.4 mm and 12.0 mm, both were typed into the box, and the
    warning was still there afterwards.

    MUTATION: hand `short=_o.overlap_mm` back to the message and the first
    half of this test is what goes red.
    """
    from ui.tabs.tab_chart import margin_rise_that_clears_mm
    reserve, lines, line_mm, npat = 7.0, 1, 12.1, 792
    r = _collision_recipe()
    now = _overlap_at(r, 0.0, npat, reserve, lines, line_mm)
    assert now is not None, "this recipe is meant to be in the warning state"
    # the number the message used to name, applied
    assert _overlap_at(r, now.overlap_mm, npat, reserve, lines,
                       line_mm) is not None, (
        "the overlap is no longer too small a rise, so this test proves "
        "nothing; re-measure before deleting it")
    # …and the one it names now
    rise = margin_rise_that_clears_mm(r, npat, reserve, lines, line_mm)
    assert rise is not None and rise > now.overlap_mm
    assert _overlap_at(r, rise, npat, reserve, lines, line_mm) is None
    # …and it is the number the SENTENCE carries, not one only a test can see.
    # The other three edges still name the overlap itself, so the region read
    # here is the bottom block alone.
    import inspect
    from ui.tabs import tab_chart as tc
    notes = inspect.getsource(tc.TabChart._engine_text_notes)
    # …from where the rise is worked out, not from the sentence: the call
    # moved above the message when the "no margin the box holds" case needed
    # its answer before the string was built.
    start = notes.index("_patch_bottom = predicted_patch_bottom_mm")
    block = notes[start:notes.index("AND THE SAME BLOCK HAS A WIDTH", start)]
    assert "margin_rise_that_clears_mm(" in block
    assert "short=_o.overlap_mm" not in block


def test_the_rise_is_a_number_the_spin_box_can_reach():
    """WHAT THE ADVICE PROMISES NOW, and each clause was paid for.

    * it CLEARS, always, because every candidate is tested before it is named;
    * it lands on the 0.5 mm grid the "Margins (mm)" boxes step in, so a reader
      can click to it instead of typing it to the tenth;
    * its two grid neighbours above clear too, because the predicate is not
      monotone and a number that only works exactly is not advice;
    * and on a smooth layout it stays within one grid step of the overlap, so
      the answer is the small one, not a safe round-up.

    MUTATION: name the raw bisection answer off the grid and the second
    assertion goes red.
    """
    from ui.tabs.tab_chart import margin_rise_that_clears_mm
    reserve, lines, line_mm, npat = 7.0, 1, 12.1, 792
    r = _collision_recipe()
    now = _overlap_at(r, 0.0, npat, reserve, lines, line_mm)
    assert now is not None, "this recipe is meant to be in the warning state"
    rise = margin_rise_that_clears_mm(r, npat, reserve, lines, line_mm,
                                      hint_mm=now.overlap_mm)
    assert rise is not None
    assert _overlap_at(r, rise, npat, reserve, lines, line_mm) is None
    assert abs(rise / 0.5 - round(rise / 0.5)) < 1e-9, (
        f"{rise} mm is not on the 0.5 mm grid the margin box steps in")
    for step in (0.5, 1.0):
        assert _overlap_at(r, round(rise + step, 1), npat, reserve, lines,
                           line_mm) is None
    # …within a click of the overlap, not exactly one: the overlap itself is
    # rarely on the grid (3.48 mm here), and the grid point above it does not
    # always clear, so the honest bound is the next one after that.
    assert rise <= now.overlap_mm + 1.0 + 1e-9, (
        f"the overlap is {now.overlap_mm:.2f} mm and the advice is {rise} mm, "
        f"which is more than a click of round-up on a layout with no hole")


def test_nothing_is_promised_when_no_margin_can_clear_it():
    """A block taller than the page cannot be cleared by any margin, and the
    search says so rather than naming a number that does nothing.

    MUTATION: return `cap_mm` instead of None and this goes red.
    """
    from ui.tabs.tab_chart import margin_rise_that_clears_mm
    r = _collision_recipe()
    assert margin_rise_that_clears_mm(r, 792, 7.0, 1, 400.0) is None


def test_the_search_rebuilds_the_layout_for_every_candidate():
    """IT CANNOT REPLACE `margin_b` ON A GEOMETRY BUILT ONCE.

    In area_first the patch length is fitted to the margins, so a geometry
    built at one margin carries the wrong `plen` for another: measured, 8.49 mm
    against 8.68 mm on a single 5 mm move, and the shortcut answered a 9.8 mm
    rise where a rebuild answers 15.0. The proof is that the two disagree:
    """
    from dataclasses import replace
    from workflow.layout_engine import instruments
    from workflow.layout_engine.presets import LayoutRecipe
    # A PLAIN area_first sheet, not his preset: his pins the patch size, so it
    # is the one layout where the shortcut would have been harmless.
    r = LayoutRecipe()
    r.instrument, r.paper = "i1", "Letter"
    r.layout_mode, r.use_instrument_margins = "area_first", False
    r.margin_top = 10.0
    r.margin_bottom = 11.0
    r.margin_left = r.margin_right = 10.0
    r.chart_text = "x"
    once = instruments.geom_from_build_kwargs(r.build_kwargs())
    rebuilt = instruments.geom_from_build_kwargs(
        replace(r, margin_bottom=r.margin_bottom + 5.0).build_kwargs())
    patched = replace(once, margin_b=rebuilt.margin_b)
    assert rebuilt.margin_b == patched.margin_b
    assert rebuilt.plen != patched.plen, (
        "the shortcut is safe after all; re-measure before using it")
    import inspect
    from ui.tabs import tab_chart as tc
    src = inspect.getsource(tc.margin_rise_that_clears_mm)
    assert "geom_from_build_kwargs" in src


def _plain_recipe(paper="Letter", mode="area_first", margin_bottom=20.0):
    """A plain i1 sheet. NOT the CR30 preset: that one pins its patch size, and
    the non-monotone behaviour below cannot happen while it does."""
    from workflow.layout_engine.presets import LayoutRecipe
    r = LayoutRecipe()
    r.instrument, r.paper = "i1", paper
    r.layout_mode, r.use_instrument_margins = mode, False
    r.margin_top, r.margin_bottom = 10.0, float(margin_bottom)
    r.margin_left = r.margin_right = 10.0
    r.chart_text = "x"
    return r


def _clears(r, rise, reserve, lines, line_mm):
    from dataclasses import replace
    from ui.tabs.tab_chart import predicted_patch_bottom_mm
    from workflow.layout_engine import instruments
    cand = replace(r, margin_bottom=float(r.margin_bottom) + float(rise))
    geom = instruments.geom_from_build_kwargs(cand.build_kwargs())
    bottom = predicted_patch_bottom_mm(cand, geom)
    return bottom is not None and tef.bottom_text_block_overlap(
        float(bottom), reserve, lines, line_mm) is None


def test_the_rise_survives_a_click_past_it():
    """THE PREDICATE IS NOT MONOTONE, SO THE SMALLEST ANSWER IS A KNIFE EDGE.

    Brute-forced on a 0.1 mm grid, an adversary round found six states where
    the margin clears, stops clearing and clears again as it rises, because a
    whole row of patches drops out and comes back. On one of them the smallest
    clearing rise was 17.4 mm while 17.5 and 17.6 brought the warning back, and
    **the margin spin box steps in 0.5 mm**, so the nearest arrow-click to the
    advice failed. A number that only works if typed to the tenth is not advice.

    Reproduced here on a plain i1 Letter sheet, two lines of 12 mm type over a
    20 mm bottom margin: 9.7 mm clears, **9.8 does not**, and the message must
    not name 9.7.

    **AND THIS TEST PINS THE PROPERTY, NOT THE WALK, WHICH IS THE HONEST
    STATE.** Removing the neighbourhood walk does NOT turn this red: across
    about 240 states measured here the bisection's own answer already survived
    its neighbours, and the one case the adversary round reported (17.4 mm
    clearing, 17.5 and 17.6 not) could not be reproduced. What is pinned is
    that the hole exists and that whatever the code names has to clear at both
    spin-box steps above it; if a future change starts naming the smallest
    answer in a hole, that is what goes red.
    """
    from ui.tabs.tab_chart import margin_rise_that_clears_mm
    r = _plain_recipe()
    reserve, lines, line_mm = 7.0, 2, 12.0
    assert not _clears(r, 0.0, reserve, lines, line_mm), (
        "this recipe is meant to be in the warning state")
    # the hole is real, and it is what makes the smallest answer wrong
    assert _clears(r, 9.7, reserve, lines, line_mm)
    assert not _clears(r, 9.8, reserve, lines, line_mm), (
        "the layout no longer has a hole here, so this test proves nothing; "
        "re-measure before deleting it")
    rise = margin_rise_that_clears_mm(r, None, reserve, lines, line_mm)
    assert rise is not None and rise > 9.7
    for step in (0.0, 0.5, 1.0):
        assert _clears(r, round(rise + step, 1), reserve, lines, line_mm), (
            f"the advice is {rise} mm and +{step} brings the warning back, "
            f"which is one click of the spin box")


def test_the_rise_still_clears_on_his_own_preset():
    """The same promise on the sheet Knut reported, where the layout is smooth.

    Swept: no state in this range has a hole at all, so the walk returns the
    bisection's own answer and the advice is the smallest that works.
    """
    from ui.tabs.tab_chart import margin_rise_that_clears_mm
    for reserve, lines, line_mm in ((7.0, 1, 12.1), (7.0, 2, 12.1),
                                    (4.0, 1, 20.6)):
        for mb in (8.0, 11.0, 14.0):
            r = _collision_recipe(mb)
            if _overlap_at(r, 0.0, 792, reserve, lines, line_mm) is None:
                continue
            rise = margin_rise_that_clears_mm(r, None, reserve, lines, line_mm)
            if rise is None:
                continue
            for step in (0.0, 0.5, 1.0):
                assert _overlap_at(r, round(rise + step, 1), 792, reserve,
                                   lines, line_mm) is None, (
                    f"margin {mb}, {lines} line(s) of {line_mm} mm: +{step} "
                    f"after the advised {rise} mm brings the warning back")


def test_the_hint_is_a_ceiling_and_never_the_answer():
    """**TAKING THE OVERLAP FOR THE ANSWER MADE THE ADVICE FOUR TIMES TOO BIG.**

    `margin_rise_that_clears_mm` is handed the overlap as *hint_mm* and starts
    its walk there, which is a large saving and was measured to be right in
    most states. But the walk only ever goes UP, so on any sheet whose true
    answer lies BELOW the overlap the bisection was never reached at all.

    Measured over 380 overlapping states, 77 answered larger than the
    un-hinted bisection. The worst is pinned here: a plain i1 Letter sheet in
    patch-first, 18 mm bottom margin, two lines of 28 pt type. A 2.5 mm rise
    drops one whole strip off the page and takes the patch bottom from 21.4 mm
    to 32.4 mm, which clears it; the overlap is 9.02 mm, and the hint path
    answered **9.5 mm** -- seven millimetres of bottom margin given away for
    nothing, on a chart that is already two pages.

    The cure is one probe: the grid point below the hint's answer. If it does
    not clear, the hint's answer is the smallest; if it does, the hint was
    loose and becomes the bracket the bisection runs inside.

    MUTATION: return `_hint` without probing `_below` and this goes red.
    """
    from ui.tabs.tab_chart import margin_rise_that_clears_mm
    from workflow.layout_engine import raster
    from workflow.layout_engine.presets import LayoutRecipe
    r = LayoutRecipe()
    r.instrument, r.paper = "i1", "Letter"
    r.layout_mode, r.use_instrument_margins = "patch_first", False
    r.margin_top = r.margin_left = r.margin_right = 10.0
    r.margin_bottom = 18.0
    r.chart_text, r.stamp_command = "test-chart", True
    r.chart_text_size_mm = 28.0 * 25.4 / 72.0
    reserve, lines = 4.0, 2
    line_mm = raster.sheet_text_line_mm(r.chart_text_size_mm, "", False, False,
                                        r.dpi)
    over = _overlap_at(r, 0.0, None, reserve, lines, line_mm)
    assert over is not None, "this recipe is meant to be in the warning state"
    # the premise: the answer really is below the overlap on this sheet
    assert _clears(r, 2.5, reserve, lines, line_mm)
    assert not _clears(r, 2.0, reserve, lines, line_mm), (
        "the strip no longer drops out at 2.5 mm here, so this test proves "
        "nothing; re-measure before changing it")
    assert over.overlap_mm > 3.0, (
        f"the overlap is only {over.overlap_mm:.2f} mm, so the hint no longer "
        f"sits above the answer and this test proves nothing")
    # …and the hint must not push the advice past it
    hinted = margin_rise_that_clears_mm(r, None, reserve, lines, line_mm,
                                        hint_mm=over.overlap_mm)
    plain = margin_rise_that_clears_mm(r, None, reserve, lines, line_mm)
    assert plain == 2.5, f"the un-hinted search moved: {plain}"
    assert hinted == plain, (
        f"the overlap hint answered {hinted} mm where the search itself "
        f"answers {plain} mm; the hint is a ceiling, not an answer")
    # …and the caller really does hand it the overlap, so this path is live
    import inspect
    from ui.tabs import tab_chart as tc
    notes = inspect.getsource(tc.TabChart._engine_text_notes)
    # …from where the rise is worked out, not from the sentence: the call
    # moved above the message when the "no margin the box holds" case needed
    # its answer before the string was built.
    start = notes.index("_patch_bottom = predicted_patch_bottom_mm")
    block = notes[start:notes.index("AND THE SAME BLOCK HAS A WIDTH", start)]
    assert "hint_mm=" in block
