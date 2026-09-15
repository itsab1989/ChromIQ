"""The bottom sheet text's line is as tall as its TYPE, not as tall as a pitch.

THE FOUR-SIDE AUDIT OF 2026-09-12 MEASURED THIS AND NOTHING WAS DONE WITH IT.
`scripts/drive_182_four_side_symmetry.py` carries the case in its own comments
("bottom sheet text at a TYPED 28 pt … measured ink crosses the 4 mm 'B'
limit", and a B4 block whose note claims a fix that was never built), and the
design record says nothing about it at all.

Reproduced on screen by `scripts/adv1_four_sides_attack.py`, driving the real
window, A4 at 200 dpi, bottom margin 12 mm, "B" 4 mm, one line of sheet text,
the ink measured off the TIFF the app itself wrote against a control sheet with
the text blanked:

| Sheet text Size | the ink's own distance to the bottom of the paper | red notices |
|---|---|---|
| auto | 4.32 mm | 0 |
| 12 pt | 3.17 mm | 0 |
| 18 pt | 0.64 mm | 0 |
| 28 pt | **0.00 mm, and it touches the right edge too** | 0 |

Two things were wrong and they are the same thing:

* `raster.render_page` stacked the lines at a fixed ``px(4.2)`` and anchored
  each by its ASCENDER, so the ink went on down as far as the face takes it.
  The "B" reserve is a limit on this edge exactly as "Clip" is on the sides
  (Knut, 2026-09-12) and it was crossed from about 12 pt up; at 28 pt on A4 the
  line was cut off by the paper edge; and with the settings stamp on as well
  the second line was printed on top of the first.
* `text_edge_fit.sheet_text_overlap` predicted 4.2 mm a line whatever the Size
  was, so the "Measured from Preview" frame stayed silent through all of it.

`raster.sheet_text_line_mm` is the one answer both sides read now: the larger
of the pitch and the face's own ascent plus descent.
"""
from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import pytest

_ROOT = Path(__file__).resolve().parents[1]

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from ui.tabs.tab_chart import TabChart                    # noqa: E402
from workflow import text_edge_fit as tef                 # noqa: E402
from workflow.layout_engine import geometry, instruments, raster  # noqa: E402
from workflow.layout_engine.presets import LayoutRecipe   # noqa: E402
from workflow.layout_engine.ti1_reader import ColorTarget  # noqa: E402

_DEV = (50.0, 50.0, 50.0)
_XYZ = (18.0, 19.0, 21.0)
_TEXT = "ChromIQ adversary one bottom sheet text"
_PAPER_W, _PAPER_H, _DPI = 210.0, 297.0, 200.0
_B_MM = 4.0


def _recipe(size_pt: float, margin_bottom: float = 12.0,
            stamp: bool = False) -> LayoutRecipe:
    r = LayoutRecipe()
    r.instrument, r.paper, r.layout_mode = "i1", "A4", "area_first"
    r.dpi = int(_DPI)
    r.clip_border, r.clip_content_mode = False, "off"
    r.margin_top = 20.0
    r.margin_left = r.margin_right = 20.0
    r.margin_bottom = margin_bottom
    r.text_edge_mm = _B_MM
    r.text_edge_top_mm = 8.0
    r.text_edge_clip_mm = 4.0
    r.chart_text = _TEXT
    r.chart_text_size_mm = (size_pt * 25.4 / 72.0) if size_pt else 0.0
    r.stamp_command = stamp
    r.show_strip_indicators, r.show_row_indicators = True, True
    r.helper_markers = False
    r.randomize, r.seed_fixed, r.seed = False, True, 7
    return r


def _page(r: LayoutRecipe, stamp_text: str = ""):
    kw = r.build_kwargs()
    g = instruments.geom_from_build_kwargs(kw)
    lay = geometry.compute(g, _PAPER_W, _PAPER_H, 120)
    target = ColorTarget(color_rep="iRGB",
                         device_fields=["RGB_R", "RGB_G", "RGB_B"],
                         patches=[(_DEV, _XYZ) for _ in range(120)])
    res = raster.render_pages(
        target, lay, g, seed=7, randomize=False,
        paper_w_mm=_PAPER_W, paper_h_mm=_PAPER_H, dpi=int(_DPI),
        chart_text=r.chart_text, chart_text_size_mm=r.chart_text_size_mm,
        stamp_text=stamp_text, text_edge_mm=r.text_edge_mm)
    return g, np.asarray(res.images[0])


def _text_ink_rows(r: LayoutRecipe, stamp_text: str = ""):
    """(first, last) inked row of the sheet text alone, against a control."""
    blank = LayoutRecipe(**{f: getattr(r, f) for f in
                            (x.name for x in r.__dataclass_fields__.values())})
    blank.chart_text = ""
    _g0, a = _page(blank, "")
    _g1, b = _page(r, stamp_text)
    assert a.shape == b.shape
    ga = a.min(axis=2) if a.ndim == 3 else a
    gb = b.min(axis=2) if b.ndim == 3 else b
    d = (ga.astype(np.int32) - gb.astype(np.int32)) > 8
    assert d.any(), "the sheet text left no ink at all"
    ys = np.where(d.any(axis=1))[0]
    return int(ys.min()), int(ys.max()), d.shape[0]


# ---- 1. the helper, and the promise that nothing already drawn moves ------
def test_the_auto_size_still_gives_the_4_2_mm_pitch():
    """Every chart that prints its bottom line at the Size box's "auto" has to
    come out exactly as it did, or this fix is a regression dressed as one."""
    got = raster.sheet_text_line_mm(0.0, "Inter", False, False, _DPI)
    assert got == pytest.approx(tef.SHEET_TEXT_LINE_MM, abs=0.03), (
        f"the auto line box moved to {got:.3f} mm from "
        f"{tef.SHEET_TEXT_LINE_MM} mm")


def test_a_bigger_size_gives_a_bigger_line_box():
    small = raster.sheet_text_line_mm(12.0 * 25.4 / 72.0, "Inter", False,
                                      False, _DPI)
    big = raster.sheet_text_line_mm(28.0 * 25.4 / 72.0, "Inter", False,
                                    False, _DPI)
    assert small > tef.SHEET_TEXT_LINE_MM, small
    assert big > small + 3.0, (small, big)
    # …and it is the FACE's own ascent plus descent, not the em.
    assert big > 28.0 * 25.4 / 72.0, big


# ---- 2. the reserve is a limit on this edge too ---------------------------
@pytest.mark.parametrize("size_pt", [0.0, 12.0, 18.0, 28.0])
def test_the_ink_never_crosses_the_B_reserve(size_pt):
    r = _recipe(size_pt)
    _g, img = _page(r)
    _first, last, height = _text_ink_rows(r)
    keep_px = (height - 1 - last) * 25.4 / _DPI
    assert keep_px >= _B_MM - 0.15, (
        f"at {size_pt or 'auto'} pt the bottom line's ink is {keep_px:.2f} mm "
        f"from the paper edge, inside the {_B_MM:.1f} mm “B” reserve")


def test_the_line_is_not_cut_off_by_the_paper_edge():
    """28 pt on A4 printed the line straight off the bottom of the sheet."""
    r = _recipe(28.0)
    _first, last, height = _text_ink_rows(r)
    assert last < height - 2, (
        "the bottom line's ink reaches the last row of the sheet, so it is "
        "being cut by the paper edge")


def test_two_lines_are_not_printed_on_top_of_each_other():
    """The sheet text and the settings stamp are two lines at one pitch."""
    r = _recipe(28.0, margin_bottom=40.0, stamp=True)
    first, last, _h = _text_ink_rows(r, stamp_text="printtarg -i i1 -h")
    span_mm = (last - first + 1) * 25.4 / _DPI
    one = raster.sheet_text_line_mm(r.chart_text_size_mm, r.chart_text_font,
                                    False, False, _DPI)
    assert span_mm > one + 2.0, (
        f"two lines of 28 pt type span {span_mm:.2f} mm, and one line's box "
        f"alone is {one:.2f} mm, so they are stacked on top of each other")


# ---- 3. and the panel says so ---------------------------------------------
class _Btn:
    def __init__(self, on=True):
        self._on = on

    def isChecked(self):
        return self._on


class _Edit:
    def text(self):
        return ""


class _Settings:
    def get(self, key, default=None):
        return True if key == "use_chromiq_layout_engine" else default


class _Tab:
    def _current_mode(self):
        """The gate `_engine_text_notes` really asks, and NOT `_manual_btn`.

        The FROM PROFILE GAMUT module is the Manual page with its own targen
        section, and it leaves that BUTTON unchecked; keying the notices on it
        turned every one of them off there (adversary round 21, measured on
        screen). The stand-in carries no `_manual_btn` on purpose, so a revert
        to the button spelling makes this file go red rather than quietly
        produce no notices at all.
        """
        return "manual"
    _manual_layout_panel = object()
    _settings = _Settings()

    def __init__(self, recipe):
        self._recipe = recipe
        self._manual_chart_notes_edit = _Edit()
        self._manual_stamp_cmd_check = _Btn(False)

    def _current_layout_recipe(self):
        return self._recipe


def _bottom_notice(r) -> str:
    lines = [w for w in TabChart._engine_text_notes(_Tab(r))[1]
             if "sheet text along the bottom" in w]
    return lines[0] if lines else ""


def test_the_panel_is_silent_while_the_line_really_does_fit():
    assert _bottom_notice(_recipe(0.0)) == "", (
        "a warning on a chart whose bottom line fits is how people learn to "
        "ignore warnings")


@pytest.mark.parametrize("size_pt,margin", [(18.0, 10.0), (28.0, 12.0)])
def test_the_panel_warns_about_a_line_too_big_for_its_margin(size_pt, margin):
    """The line's own box is bigger than the paper between "B" and the patches.

    Both of these pass `sheet_text_overlap`'s old 4.2 mm test with room to
    spare, so before the fix the panel said nothing about either.
    """
    assert margin - _B_MM > tef.SHEET_TEXT_LINE_MM, (
        "pick a margin the 4.2 mm pitch fits inside, or this proves nothing")
    msg = _bottom_notice(_recipe(size_pt, margin_bottom=margin))
    assert msg, (
        f"a {size_pt:.0f} pt bottom line on a {margin:.0f} mm bottom margin "
        f"raised no warning at all")
    want = raster.sheet_text_line_mm(size_pt * 25.4 / 72.0, "Inter", False,
                                     False, _DPI)
    assert f"needs {want:.1f} mm" in msg, (
        f"the message does not name the {want:.1f} mm the line really takes:"
        f"\n  {msg}")
    assert "needs 4.2 mm" not in msg, (
        "the message is still quoting the 4.2 mm pitch:\n  " + msg)


def test_the_panel_and_the_renderer_read_one_function():
    """The prediction is only worth something while it is the same number."""
    import inspect
    src = inspect.getsource(raster.render_pages)
    assert "sheet_text_line_mm(chart_text_size_mm" in src, (
        "the renderer has gone back to a line height of its own")
    panel = inspect.getsource(TabChart._engine_text_notes)
    assert "sheet_text_line_mm" in panel, (
        "the panel is predicting the bottom line with a number of its own")


# ---- 4. both layout modes, and a lever that is real -----------------------
@pytest.mark.parametrize("mode,size_pt", (("area_first", 28.0),
                                          ("patch_first", 120.0)))
def test_the_panel_speaks_in_both_layout_modes(mode, size_pt):
    """THE CHECK WAS GATED ON area_first AND PATCH-FIRST IS A DEFAULT.

    It is the default for the SpectroScan and the CR30, and
    `LayoutRecipe.from_dict` falls back to it for any preset dict without the
    key. Driven on Knut's own CR30 preset with the ink read off the app's
    sheets, before this was lifted: the text ran into the patches by 6.60, 9.28
    and 25.02 mm in patch-first with no height warning at all.

    The gate had a reason once, and it died with the fix: the old check asked
    about the REQUESTED margin, which is not the room in patch-first, while the
    new one asks where the patches really are.

    MUTATION: put `_labels_can_overflow and` back in front of the bottom
    `_o` and the patch_first case goes red.
    """
    from dataclasses import replace
    from ui.tabs.tab_chart import predicted_patch_bottom_mm
    from workflow.layout_engine import instruments
    r = replace(_recipe(size_pt, margin_bottom=12.0), layout_mode=mode)
    # THE SIZES DIFFER BECAUSE THE MODES DO. Patch-first holds the patches far
    # higher on this recipe (46 mm against 13 mm), so 28 pt there is not a
    # collision at all and a test asserting one would be asserting a fault.
    # The premise is measured rather than assumed:
    geom = instruments.geom_from_build_kwargs(r.build_kwargs())
    bottom = predicted_patch_bottom_mm(r, geom)
    line = raster.sheet_text_line_mm(r.chart_text_size_mm, r.chart_text_font,
                                     False, False, r.dpi)
    assert bottom - _B_MM < line, (
        f"{mode}: {size_pt} pt does not reach the patches here, so this test "
        f"proves nothing; re-measure before changing it")
    assert "runs into the patches" in _bottom_notice(r), (
        f"{mode}: a {size_pt:.0f} pt line over a 12 mm margin is not reported")


def test_the_lever_is_only_offered_where_it_moves_the_text():
    """"Lower B" is inert whenever the helper markers hold the text higher.

    Measured on screen on Knut's CR30 preset (markers: edge 4.0 + length 2.0 +
    1.0 = an anchor of 7.0 mm): "B" typed at 7, 5, 4, 3, 2, 1 and 0 left the
    anchor at 7.00 mm, the text at 16.89 mm and the overlap at 1.27 mm, with
    the warning up the whole time. Seven values, no movement.

    MUTATION: return the second sentence unconditionally and the first half of
    this goes red.
    """
    from dataclasses import replace
    from ui.tabs.tab_chart import _bottom_lever_note
    held = _bottom_lever_note(4.0, 7.0)
    free = _bottom_lever_note(4.0, 4.0)
    assert "will not help" in held and "7.0 mm" in held
    assert "Print helper markers" in held, (
        "it has to name the control that hands the distance back")
    assert "will not help" not in free and "moves the text" in free
    # …and the panel really says it, on a chart whose markers hold the text.
    r = replace(_recipe(28.0, margin_bottom=12.0), helper_markers=True,
                helper_marker_edge_mm=4.0, helper_marker_len_mm=2.0,
                helper_markers_top_bottom=True, text_edge_mm=4.0)
    said = _bottom_notice(r)
    assert "runs into the patches" in said
    assert "will not help here" in said, (
        "the markers hold the text at 7.0 mm and the message still offers B")


def test_the_lever_is_withheld_when_it_cannot_close_the_gap():
    """"B" ABOVE THE MARKERS' REACH IS WHERE THE OFFER WAS FALSE.

    `_bottom_lever_note` decided from one comparison, "is the anchor above the
    typed B", which is only ever true when the markers already hold the text.
    Type "B" ABOVE their reach and the anchor equals "B", so the second
    sentence was chosen and promised "the same room" -- while lowering "B"
    stops dead at the markers.

    MEASURED ON SCREEN, 2026-09-14
    (`scripts/adv17b_the_lever_that_stops_at_the_markers.py`), Knut's CR30
    Letter preset in area_first at 24 pt, markers on at edge 4.0 + length 2.0
    (a 7.0 mm reach), "B" swept from 12 mm down to 0:

    | "B" | anchor | the panel said | warning |
    |---|---|---|---|
    | 12.0 | 12.00 | "lowering B buys the same room" | up |
    | 9.0 | 9.00 | "lowering B buys the same room" | up |
    | 7.0 | 7.00 | "lowering B buys the same room" | up |
    | 6.0 | 7.00 | "lowering B will not help here" | up |
    | 0.0 | 7.00 | "lowering B will not help here" | **still up** |

    Pulling the offered lever all the way down bought 5 mm of a larger
    shortfall and left the warning on screen, which is the same shape as the
    "raise Bottom by the size of the overlap" fault this block was rewritten
    to remove. 74 warning states were then driven after the fix and all 17
    that still offer the lever clear when it is pulled
    (`scripts/adv17b_the_lever_offer_is_kept.py`).

    MUTATION: hand `_bottom_lever_note` a constant `True` for *lever_clears*,
    or drop the `if not lever_clears` branch, and this goes red.
    """
    from dataclasses import replace
    from ui.tabs.tab_chart import _bottom_lever_note, lowering_b_clears
    # "B" at 12 mm, markers reaching 7.0: the anchor follows "B", so the old
    # comparison picks the offer, and the lever really stops at 7.0.
    r = replace(_recipe(24.0, margin_bottom=8.0), helper_markers=True,
                helper_marker_edge_mm=4.0, helper_marker_len_mm=2.0,
                helper_markers_top_bottom=True, text_edge_mm=12.0)
    line = raster.sheet_text_line_mm(r.chart_text_size_mm, r.chart_text_font,
                                     False, False, r.dpi)
    assert not lowering_b_clears(r, 1, line), (
        "the lever clears this sheet after all, so the test proves nothing; "
        "re-measure before changing it")
    said = _bottom_notice(r)
    assert "runs into the patches" in said, "this sheet is meant to warn"
    assert "buys the same room" not in said, (
        "the message offers a lever that stops at the helper markers")
    assert "will not help here" not in said, (
        "the markers are NOT holding the text here: “B” is above their reach, "
        "so that sentence would be false too")
    # …and the offer survives where it is real: same sheet, markers off.
    free = replace(r, helper_markers=False, text_edge_mm=_B_MM)
    if _bottom_notice(free):
        assert lowering_b_clears(free, 1, line) == (
            "buys the same room" in _bottom_notice(free))


def test_the_lever_sentence_cannot_take_the_panel_down_with_it():
    """`_engine_text_notes` wraps its whole body in one `except Exception`, and
    `_bottom_lever_note` was the only one of the three new call sites in that
    block without a guard of its own.

    MEASURED by injection: with it raising, the bottom notice disappeared from
    a recipe that earns three, and nothing said so.

    MUTATION: take the `try` out of `_bottom_lever_note` and this goes red.
    """
    from ui.tabs.tab_chart import _bottom_lever_note

    class _Boom:
        def __bool__(self):                 # noqa: D105
            return True

        def __float__(self):                # noqa: D105
            raise RuntimeError("a number this sentence cannot use")
    assert _bottom_lever_note(_Boom(), _Boom()) == ""

    # …and the other way a real one can blow up: a catalogue whose translation
    # of one of these two sentences has lost a placeholder.
    import ui.tabs.tab_chart as tc
    keep = tc.tr
    tc.tr = lambda s: s.replace("{anchor:.1f}", "{anchor")   # a broken format
    try:
        assert _bottom_lever_note(4.0, 7.0) == ""
    finally:
        tc.tr = keep


def test_a_b_of_zero_is_not_offered_as_a_lever():
    """A BOX READING 0 IS NOT AT THE BOTTOM OF ITS RANGE, IT IS AT 4.0 mm.

    `LayoutRecipe.effective_text_edge_mm` is `text_edge_mm or 4.0`, so a "B" of
    0 draws the text 4.0 mm up and the only way to move it DOWN is to RAISE the
    number to 0.1. The panel used to answer this state with "Lowering B moves
    the text down towards the paper edge", which is an instruction that cannot
    be carried out; the caller passes the TYPED value now, not the effective
    one, and the sentence is withheld.

    The markers sentence is still offered there, because it is true at a typed
    0 as well and it names a control that does move.

    MUTATION: pass `_bot_edge` as the typed value again and the first assertion
    goes red.
    """
    from dataclasses import replace
    from ui.tabs.tab_chart import _bottom_lever_note
    assert _bottom_lever_note(4.0, 4.0, True, 0.0) == "", (
        "a box that already reads 0 was told to go lower")
    assert "will not help" in _bottom_lever_note(4.0, 7.0, True, 0.0), (
        "the markers really do hold the text here and that is worth saying")
    # …and the panel itself, on a chart whose box reads 0 with no markers.
    r = replace(_recipe(28.0, margin_bottom=12.0), text_edge_mm=0.0,
                helper_markers=False)
    said = _bottom_notice(r)
    assert "runs into the patches" in said
    assert "moves the text down" not in said, (
        "the panel told a reader to lower a box that is already at 0")


def test_the_markers_sentence_names_a_route_that_has_to_finish():
    """THE OTHER SENTENCE IN THE SAME MESSAGE WAS NEVER ASKED OF THE SHEET.

    Round 2 made *"lowering B buys the same room"* conditional on
    :func:`lowering_b_clears`, because an offer that does not finish the job is
    a false promise. The sentence beside it is chosen by ONE comparison and
    then names a way out of its own: *"Switching 'Print helper markers' off, or
    shortening them, hands that distance back to 'B'."* Nothing tried it.

    MEASURED ON SCREEN, 2026-09-14, Knut's CR30 Letter preset, both layout
    modes, bottom margins 8 / 11 / 14, one and two lines, 14 / 24 / 40 pt
    (`scripts/adv17c_the_route_gate_one_names.py`): **24** states offered the
    sentence, and in **16** of them switching the markers off in the real
    window and taking "B" down to 0.1 left the warning exactly where it was.
    Photographed at area_first / 8 mm margin / 40 pt, one line: before, *"needs
    17.1 mm of room … leaving 7.1 mm"*; after doing precisely what the sentence
    said, *"needs 17.1 mm of room … leaving 14.0 mm"*, still red, and the ruler
    helper markers thrown away for it.

    MUTATION: hand `_bottom_lever_note` a constant `True` for
    *markers_route_clears*, or drop the `if not markers_route_clears` branch,
    and this goes red.
    """
    from dataclasses import replace
    from ui.tabs.tab_chart import _bottom_lever_note, markers_off_clears
    # the sentence itself, both ways round
    assert "will not help" in _bottom_lever_note(4.0, 7.0, True, 4.0, True)
    assert _bottom_lever_note(4.0, 7.0, True, 4.0, False) == "", (
        "the route it names buys nothing here and it was offered anyway")
    # …and a real sheet in that state: the markers hold the text, and taking
    # them out of the way with "B" at the bottom of its range does NOT clear a
    # 40 pt line over a 12 mm margin.
    r = replace(_recipe(40.0, margin_bottom=12.0), helper_markers=True,
                helper_marker_edge_mm=4.0, helper_marker_len_mm=2.0,
                helper_markers_top_bottom=True, text_edge_mm=4.0)
    line = raster.sheet_text_line_mm(r.chart_text_size_mm, r.chart_text_font,
                                     False, False, r.dpi)
    assert not markers_off_clears(r, 1, line), (
        "the route clears this sheet after all, so this test proves nothing; "
        "re-measure before changing it")
    said = _bottom_notice(r)
    assert "runs into the patches" in said, "this sheet is meant to warn"
    assert "Print helper markers" not in said, (
        "the panel told a reader to throw away the ruler helper markers for a "
        "route that leaves the warning up")
    # …and the sentence survives where the route really does finish: the same
    # markers over a line small enough that 0.1 mm of anchor is enough.
    small = replace(r, chart_text_size_mm=14.0 * 25.4 / 72.0)
    line_s = raster.sheet_text_line_mm(small.chart_text_size_mm,
                                       small.chart_text_font, False, False,
                                       small.dpi)
    if _bottom_notice(small):
        assert markers_off_clears(small, 1, line_s) == (
            "Print helper markers" in _bottom_notice(small))


def test_no_margin_the_box_holds_is_said_rather_than_asked_for():
    """THE "Margins (mm)" BOXES STOP AT 60 mm, AND THE ADVICE DID NOT.

    An adversary round measured 160 of 1,501 reachable warning states naming a
    total the box cannot hold, worst 72.9 mm: the box clamps and the warning
    stays up, so the reader has done as they were told and nothing happened.

    The search is capped at what the box will hold now, and where nothing
    inside that clears, the message says so and points at the two things that
    do work, instead of naming a number nobody can type.

    MUTATION: put the bare `cap_mm` back and the second assertion goes red.
    """
    from dataclasses import replace
    from ui.tabs.tab_chart import (_MARGIN_BOX_MAX_MM,
                                   margin_rise_that_clears_mm)
    from workflow.layout_engine.presets import LayoutRecipe
    r = LayoutRecipe()
    r.instrument, r.paper = "i1", "A4"
    r.layout_mode, r.use_instrument_margins = "area_first", False
    r.margin_top, r.margin_bottom = 10.0, 30.0
    r.margin_left = r.margin_right = 10.0
    r.chart_text = "x"
    # two lines of 40 mm type over a 30 mm margin: 56 mm short, and the box
    # has 30 mm left in it
    assert margin_rise_that_clears_mm(r, None, 7.0, 2, 40.0) is None, (
        "the search offered a rise this sheet cannot be given")
    # …and a sheet the box CAN rescue still gets its number
    rise = margin_rise_that_clears_mm(r, None, 7.0, 2, 25.0)
    assert rise is not None and 30.0 + rise <= _MARGIN_BOX_MAX_MM + 1e-9
    # …and the panel says which case it is in
    said = _bottom_notice(replace(r, chart_text="x", chart_text_size_mm=14.0,
                                  stamp_command=False, helper_markers=False))
    assert said == "" or "runs into the patches" in said


def test_the_remedy_says_the_margin_box_is_locked_when_it_is():
    """"RAISE 'BOTTOM'" NAMES A BOX THAT IS GREYED OUT BY DEFAULT.

    `LayoutRecipe` ships ``use_instrument_margins = True`` and
    `layout_options_panel._sync_instrument_margins` runs
    ``self.margins[k].setEnabled(not on)``, so with "Use instrument margins"
    ticked all four "Margins (mm)" boxes are read-only. Measured on screen on
    2026-09-14, Knut's CR30 Letter preset at Size 40 pt, both layout modes
    (`scripts/adv17d_raise_bottom_by_0_0_mm.py`): the bottom box reported
    ``isEnabled() == False`` while the warning said *"Raise “Bottom” under
    “Margins (mm)” by about 14.0 mm"*, with nothing about the tick. Every
    round so far unticked it before measuring, so nobody had seen the state
    the app starts in.

    MUTATION: drop `_locked_margins_note(r)` from the call and the first
    assertion goes red; return "" unconditionally from it and so does it.
    """
    from ui.tabs.tab_chart import _locked_margins_note
    r = _recipe(28.0, margin_bottom=12.0)
    r.use_instrument_margins = True
    locked = _bottom_notice(r)
    assert locked, "no warning at all on the state this test is about"
    assert "Untick it" in locked, (
        "the remedy names “Bottom” under “Margins (mm)” while that box is "
        "locked read-only, and says nothing about the tick that locks it:"
        f"\n  {locked}")
    # …and it is SILENT when the box is open, which is the state every earlier
    # round measured in.
    r.use_instrument_margins = False
    free = _bottom_notice(r)
    assert free and "Untick it" not in free, (
        "the locked sentence is offered on a panel whose margin boxes are "
        f"perfectly editable:\n  {free}")
    # the helper answers on its own, both ways
    assert _locked_margins_note(r) == ""
    r.use_instrument_margins = True
    assert "Untick it" in _locked_margins_note(r)
    # …and it cannot take the panel down with it: the caller's whole body is
    # inside one `except Exception: pass`.
    assert _locked_margins_note(object()) == ""


def test_the_ceiling_sentence_is_really_printed_on_the_panel():
    """THE TEST NAMED FOR THIS SENTENCE NEVER ASKED WHETHER IT IS SAID.

    `test_no_margin_the_box_holds_is_said_rather_than_asked_for` pins the CAP
    and then ends on ``assert said == "" or "runs into the patches" in said``,
    which is true of a panel that says nothing about the ceiling at all. An
    adversary round proved it: `return ""` in front of the sentence and the
    whole file stayed green.

    The sentence has since moved. It was an appended note beside "Raise
    “Bottom” by about {short} mm"; at a margin already on the ceiling that came
    out as **"by about 0.0 mm"**, reached by doing what the app said one step
    earlier. So the case has its own message now and names no rise at all, and
    what this test asks is that the panel really carries it.

    MUTATION: make the `_rise is not None` branch unconditional and the first
    assertion goes red.
    """
    r = _recipe(72.0, margin_bottom=10.0, stamp=True)
    r.use_instrument_margins = False
    said = _bottom_notice(r)
    assert said, "no bottom warning at all on the state this test is about"
    assert "No bottom margin this sheet allows will clear it" in said, (
        "no margin the box holds clears this sheet, and the panel promised a "
        f"cure anyway:\n  {said}")
    # …it names the ceiling the box really has, not a number out of the air
    from ui.tabs.tab_chart import _MARGIN_BOX_MAX_MM
    assert f"{_MARGIN_BOX_MAX_MM:.0f} mm" in said, said
    # …it never asks for a rise, least of all one of 0.0 mm
    assert "by about" not in said, (
        f"a rise was named on a sheet where no rise works:\n  {said}")
    # …AND IT DOES NOT OFFER A LARGER PAPER, which was measured false: on
    # screen, each of the fourteen other papers in the pulldown left the
    # warning exactly where it was, A2 included, and in geometry the patch
    # bottom moves 21.00 mm to 21.04 between A4 and A2.
    assert "larger paper does not help" in said
    # …ON BOTH WORDINGS. There are two of these sentences, one line and two,
    # and a mutation of the ONE-line copy left this test green while the state
    # it builds is the two-line one. Measured: the clause really is in both.
    from dataclasses import replace as _replace
    one = _replace(_recipe(0.0, margin_bottom=10.0, stamp=False),
                   chart_text_size_mm=55.0, helper_markers=False)
    one.use_instrument_margins = False
    said_one = _bottom_notice(one)
    assert said_one and "No bottom margin this sheet allows" in said_one, said_one
    assert "two lines" not in said_one, "this is meant to be the one-line case"
    assert "larger paper does not help" in said_one, said_one
    assert "by about" not in said_one, said_one
    # …and it is SILENT where a rise really does clear the sheet.
    ok = _recipe(18.0, margin_bottom=10.0)
    ok.use_instrument_margins = False
    cured = _bottom_notice(ok)
    assert cured and "No bottom margin this sheet allows" not in cured, (
        "a sheet a bottom margin can rescue was told no margin can:"
        f"\n  {cured}")
    assert "by about" in cured, "the sheet a rise can rescue was given no rise"


def test_no_advice_ever_asks_for_a_rise_of_zero():
    """"Raise “Bottom” under “Margins (mm)” by about 0.0 mm" was reachable by
    doing what the app said: at 55 mm it asked for 5.0, and at 60, the box's
    own ceiling, it asked for 0.0.

    MUTATION: fall back to `min(overlap, 60 - margin)` again and this goes red
    at the top of the range.
    """
    for mb in (40.0, 50.0, 55.0, 58.0, 60.0):
        for pt in (28.0, 48.0, 72.0):
            for stamp in (False, True):
                r = _recipe(pt, margin_bottom=mb, stamp=stamp)
                r.use_instrument_margins = False
                said = _bottom_notice(r)
                if not said:
                    continue
                assert "by about 0.0 mm" not in said, (
                    f"{pt} pt at a {mb} mm margin: {said}")


def test_a_gate_is_only_asked_where_its_answer_is_read():
    """EACH GATE IS A GEOMETRY REBUILD, AND BOTH WERE RUN FOR ONE ANSWER.

    `_bottom_lever_note` has three branches and each reads at most one of the
    two gates: the markers branch reads `markers_off_clears`, the free branch
    reads `lowering_b_clears`, and a "B" typed as 0 returns before either.
    Handed as values, both ran every time. Measured on screen on Knut's CR30
    preset with "B" at 0, stepping the bottom margin over twenty different
    values so no rebuild is cached: **29.8 ms of a 54.9 ms notice pass**, more
    than everything else in it together, spent on two answers nobody read.

    MUTATION: call the two gates eagerly at the call site again and the counts
    below stop being zero.
    """
    from ui.tabs.tab_chart import _bottom_lever_note
    seen = {"lever": 0, "markers": 0}

    def lever():
        seen["lever"] += 1
        return True

    def markers():
        seen["markers"] += 1
        return True

    # a "B" typed as 0: neither answer is read
    assert _bottom_lever_note(4.0, 4.0, lever, 0.0, markers) == ""
    assert seen == {"lever": 0, "markers": 0}, (
        f"a gate ran for a branch that does not read it: {seen}")
    # the markers hold the text: only that gate is asked
    seen.update(lever=0, markers=0)
    assert "will not help" in _bottom_lever_note(4.0, 7.0, lever, 4.0, markers)
    assert seen == {"lever": 0, "markers": 1}, seen
    # the lever is free: only the other one
    seen.update(lever=0, markers=0)
    assert "moves the text" in _bottom_lever_note(4.0, 4.0, lever, 4.0, markers)
    assert seen == {"lever": 1, "markers": 0}, seen
    # …and a plain bool still works, so nothing else had to change
    assert _bottom_lever_note(4.0, 4.0, False, 4.0, False) == ""
    assert "will not help" in _bottom_lever_note(4.0, 7.0, True, 4.0, True)


def test_the_call_site_hands_the_gates_over_unrun():
    """The laziness only pays if the caller does not run them first.

    MUTATION: drop either `lambda:` at the call site and this goes red.
    """
    import inspect
    from ui.tabs import tab_chart as tc
    notes = inspect.getsource(tc.TabChart._engine_text_notes)
    start = notes.index("_bottom_lever_note(")
    block = notes[start:notes.index("AND THE SAME BLOCK HAS A WIDTH", start)]
    assert "lambda: lowering_b_clears(" in block, block[:400]
    assert "lambda: markers_off_clears(" in block, block[:400]


def test_a_larger_paper_is_asked_of_the_sheet_before_it_is_denied():
    """"A LARGER PAPER DOES NOT HELP" WAS A CLAIM, NOT A MEASUREMENT.

    It was written into both "no margin clears it" wordings as a flat
    statement, from one state in which fourteen papers were tried. The half of
    it that is true is that the TEXT does not move: it is anchored on the paper
    edge. The half that decides the question is where the PATCHES stop, and the
    patch block is re-fitted to every sheet.

    MEASURED, 2026-09-14: over the reachable states of Knut's CR30 preset the
    message fired in 84 and the claim was false in **29** of them, from seven
    base papers and in both layout modes. Driven in the real window
    (`scripts/adv17e_a_larger_paper_does_help.py`), A4 in area_first at a
    59.5 mm bottom margin: the panel said no paper can clear it, and switching
    the pulldown to **A3** cleared it, four warnings down to three.

    The two states below are the same recipe in the two layout modes, and they
    are measured, not assumed: in patch-first A3, A2, Legal and 11x17 all clear
    this sheet (`_bottom_clears_with`), and in area_first no larger paper in
    the i1's list does.

    MUTATION: return the sentence unconditionally from `_larger_paper_note`
    and the patch-first half goes red; return "" and the area_first half does.
    """
    from ui.tabs.tab_chart import _bottom_clears_with, _larger_paper_note
    from workflow.layout_engine import papers as _papers

    def _state(mode):
        r = _recipe(72.0, margin_bottom=10.0, stamp=True)
        r.use_instrument_margins = False
        r.layout_mode = mode
        return r

    def _any_larger_clears(r):
        line = raster.sheet_text_line_mm(r.chart_text_size_mm,
                                         r.chart_text_font, False, False, r.dpi)
        w, h = _papers.dimensions_mm(r.paper)
        return [c for c, _l, d in _papers.list_papers(r.instrument,
                                                      for_engine=True)
                if c != r.paper and d[0] * d[1] > w * h
                and _bottom_clears_with(r, 2, line, paper=c)]

    # …patch-first: bigger sheets really do clear it, so the panel must not say
    # they cannot
    pf = _state("patch_first")
    bigger = _any_larger_clears(pf)
    assert bigger, ("no larger paper clears this sheet any more; re-measure "
                    "before changing this test")
    said = _bottom_notice(pf)
    assert said and "No bottom margin this sheet allows" in said, said
    assert "larger paper does not help" not in said, (
        f"{', '.join(bigger)} clear this collision and the panel denies it:"
        f"\n  {said}")
    # …area_first: none of them does, and there the sentence is the truth
    af = _state("area_first")
    assert not _any_larger_clears(af), (
        "a larger paper now clears the area_first state too; re-measure")
    said_af = _bottom_notice(af)
    assert said_af and "No bottom margin this sheet allows" in said_af, said_af
    assert "larger paper does not help" in said_af, (
        f"no paper the pulldown offers clears this one and nobody said so:"
        f"\n  {said_af}")
    # …and the helper cannot take the panel down with it
    assert _larger_paper_note(object(), 1, 4.2) == ""


def test_the_rise_is_measured_on_the_sheet_the_reader_can_type_in():
    """THE NUMBER WAS MEASURED IN A STATE THE READER HAS TO LEAVE.

    With "Use instrument margins" ticked -- `LayoutRecipe`'s own default -- the
    four "Margins (mm)" boxes are read-only, so the only way to raise "Bottom"
    is to untick it. The tick is part of the GEOMETRY and not only of the
    widgets: `instruments.geom_from_build_kwargs` sets
    ``margins_are_law = area_first or use_instrument_margins``.

    MEASURED, 2026-09-14, Knut's CR30 Letter preset: of 57 locked states that
    named a rise, **12** did not clear once the tick came off, all in
    patch-first, and the unticked sheet always needed more (4.5 named where 8.5
    clears). Driven in the real window
    (`scripts/adv17e_the_rise_named_through_a_locked_box.py`): untick, type the
    number the panel gave, and the warning is still on screen.

    MUTATION: drop the `use_instrument_margins=False` line at the top of
    `margin_rise_that_clears_mm` and this goes red.
    """
    from dataclasses import replace
    from ui.tabs.tab_chart import (margin_rise_that_clears_mm,
                                   predicted_patch_bottom_mm)
    from workflow.layout_engine import instruments
    # 56 pt over two lines on a 6 mm bottom margin, patch-first: measured, the
    # locked sheet is cleared by a 39.5 mm rise and the unticked one is not
    # (it wants 44.5). One of 18 such states on this recipe.
    r = _recipe(56.0, margin_bottom=6.0, stamp=True)
    r.layout_mode = "patch_first"
    r.use_instrument_margins = True
    line = raster.sheet_text_line_mm(r.chart_text_size_mm, r.chart_text_font,
                                     False, False, r.dpi)
    rise = margin_rise_that_clears_mm(r, None, _B_MM, 2, line)
    assert rise is not None, "no rise at all on the state this test is about"

    def _clears(rec, margin):
        c = replace(rec, margin_bottom=margin)
        g = instruments.geom_from_build_kwargs(c.build_kwargs())
        bottom = predicted_patch_bottom_mm(c, g)
        return bottom is not None and tef.bottom_text_block_overlap(
            float(bottom), _B_MM, 2, line) is None

    free = replace(r, use_instrument_margins=False)
    # the premise: the tick really does change this sheet, or this test proves
    # nothing
    assert not _clears(free, 6.0) and not _clears(r, 6.0), (
        "no collision to report in either state; re-measure")
    assert _clears(free, 6.0 + rise), (
        f"the panel asks for {rise} mm, the reader has to untick "
        f"“Use instrument margins” to type it, and on that sheet it does not "
        f"clear")
    # …and the locked recipe is answered with the unticked sheet's own number
    assert rise == margin_rise_that_clears_mm(free, None, _B_MM, 2, line), (
        "the locked sheet is still being measured for a number that can only "
        "be typed on the unlocked one")


def test_a_marker_box_typed_zero_is_read_as_the_engine_reads_it():
    """A MARKER BOX TYPED 0 IS 2.0 mm ON THE SHEET AND WAS 0.0 IN THE WARNING.

    `LayoutRecipe.build_kwargs` sends ``helper_marker_edge_mm or 2.0`` and
    ``helper_marker_len_mm or 2.0``, so typing 0 into "Distance from page edge
    (mm)" or "Marker length (mm)" still prints 2 mm markers; the panel read the
    recipe field raw and predicted a text reserve up to 4 mm smaller than the
    one the engine holds back.

    MEASURED, 2026-09-14: rendered through the kwargs `chart.build_chart`
    itself passes, the sheet with both boxes at 0 and the sheet with both at 2
    are the same sheet, ink from 6.48 to 13.46 mm in each, while the panel's
    own number was 1.00 mm against the engine's 5.00. A sweep of the reachable
    states found **91** in which the bottom check was silent on a sheet the
    engine's own reserve says collides.

    MUTATION: read the fields raw again in `_marker_reserve_args` and the last
    assertion goes red.
    """
    from dataclasses import replace
    from ui.tabs.tab_chart import _marker_reserve_args
    r = _recipe(24.0, margin_bottom=6.0)
    r.helper_markers = True
    r.text_edge_mm = 0.5
    for edge, length in ((0.0, 0.0), (0.0, 2.0), (2.0, 0.0), (4.0, 2.0)):
        c = replace(r, helper_marker_edge_mm=edge, helper_marker_len_mm=length)
        kw = c.build_kwargs()
        assert _marker_reserve_args(c) == (
            float(kw["helper_marker_edge"]), float(kw["helper_marker_len"])), (
            f"the panel and the engine disagree at edge={edge} len={length}")
    # …and the check that reads it is no longer silent on a sheet that collides
    zero = replace(r, helper_marker_edge_mm=0.0, helper_marker_len_mm=0.0,
                   chart_text_size_mm=24.0 * 25.4 / 72.0)
    zero.use_instrument_margins = False
    two = replace(zero, helper_marker_edge_mm=2.0, helper_marker_len_mm=2.0)
    said_zero, said_two = _bottom_notice(zero), _bottom_notice(two)
    assert said_two, "the 2.0/2.0 sheet raises no warning; re-measure"
    assert said_zero, (
        "the same sheet with the marker boxes typed 0 is silent, and the "
        "engine draws it identically")
    assert said_zero == said_two, (
        f"two identical sheets described differently:\n  {said_zero}"
        f"\n  {said_two}")


# ---- 9. adversary round 6 -------------------------------------------------
def test_a_larger_paper_is_asked_about_by_size_not_by_area():
    """"A larger paper does not help" — asked of every paper that IS larger.

    Round 5 gated the sentence on the sheet and filtered the candidates by
    AREA. A bottom collision is decided by how far down the page the patch grid
    stops, which is a question about the paper's HEIGHT, and area answers it in
    neither direction: measured over the reachable states, a paper the area
    test skips falsified the denial in 44 of them, and on the widest sheet in
    the pulldown (A2 landscape) nothing at all is larger by area, so the loop
    ran over an EMPTY candidate list and the sentence was back to being the
    plain assertion it was written to stop being.

    The state below is A2 landscape, and the paper that clears it is A3+
    PORTRAIT: 63 mm taller, and 36 % smaller by area, so the old filter never
    tried it.

    The test does not re-implement the filter — that is how a fake validates
    itself. It names the paper, asks the sheet whether that paper really
    clears, and then reads the panel.
    """
    from dataclasses import replace

    from ui.tabs.tab_chart import _bottom_clears_with, _larger_paper_note
    from workflow.layout_engine import papers as _papers

    r = _recipe(72.0, margin_bottom=60.0, stamp=True)
    r.instrument, r.paper, r.layout_mode = "CR30", "594x420", "patch_first"
    r.use_instrument_margins = False
    line = raster.sheet_text_line_mm(r.chart_text_size_mm, r.chart_text_font,
                                     False, False, r.dpi)

    # the branch that makes the claim is reached at all
    said = _bottom_notice(r)
    assert said and "No bottom margin this sheet allows" in said, (
        "this state no longer reaches the 'no margin clears it' branch; "
        f"re-measure before changing this test:\n  {said}")

    here_w, here_h = _papers.dimensions_mm("594x420")
    cand_w, cand_h = _papers.dimensions_mm("329x483")
    assert cand_h > here_h, "A3+ portrait is meant to be the TALLER sheet"
    assert cand_w * cand_h < here_w * here_h, (
        "A3+ portrait is meant to be the SMALLER-BY-AREA sheet, which is what "
        "made the old filter skip it")
    assert not [c for c, _l, d in _papers.list_papers("CR30", for_engine=True)
                if d[0] * d[1] > here_w * here_h], (
        "A2 landscape is no longer the largest sheet by area; re-measure")

    # …and it really does clear the collision. Asked of the sheet.
    assert _bottom_clears_with(r, 2, line, paper="329x483"), (
        "A3+ portrait no longer clears this collision; re-measure before "
        "changing this test")

    assert _larger_paper_note(r, 2, line) == "", (
        "the panel still says a larger paper cannot help, on a sheet where "
        "A3+ portrait — 63 mm taller, in the same pulldown — clears the "
        "collision")
    assert "larger paper does not help" not in _bottom_notice(r)

    # …and where nothing larger does clear it, the sentence is still printed,
    # so the gate has not simply been switched off.
    tall = replace(r, chart_text_size_mm=110.0 * 25.4 / 72.0)
    tall_line = raster.sheet_text_line_mm(tall.chart_text_size_mm,
                                          tall.chart_text_font, False, False,
                                          tall.dpi)
    assert not [c for c, _l, d in _papers.list_papers("CR30", for_engine=True)
                if c != "594x420" and (d[0] > here_w or d[1] > here_h)
                and _bottom_clears_with(tall, 2, tall_line, paper=c)], (
        "a larger paper now clears the 110 pt state; re-measure")
    assert "does not help" in _larger_paper_note(tall, 2, tall_line), (
        "no larger paper clears this one and the panel said nothing")


def test_no_notice_reads_a_marker_box_raw():
    """Every side of this frame reads the markers AS THE ENGINE DOES.

    `LayoutRecipe.build_kwargs` sends ``helper_marker_edge_mm or 2.0``, so a
    box typed 0 draws 2 mm of marker. Round 5 put that in
    `_marker_reserve_args` and swept the two BOTTOM checks with it; the top and
    the two side ones were left reading the field raw, and the top one was then
    measured silent over strip letters that really are printed on the patches
    (A4, area_first, top margin 8.0 mm, "T" 2.0 mm: the label band's ink ends
    at 8.94 mm and the first patch row starts at 8.04).

    A source test, because the fault is a call site and not a value: any new
    notice that reaches for the raw field is the same fault again.
    """
    import inspect

    src = inspect.getsource(TabChart._engine_text_notes)
    raw = [ln.strip() for ln in src.splitlines()
           if ("helper_marker_edge_mm" in ln or "helper_marker_len_mm" in ln)
           and "getattr(r," in ln]
    assert not raw, (
        "these lines read the marker box instead of what the engine draws; "
        "use `_marker_reserve_args(r)`:\n  " + "\n  ".join(raw))


def test_the_strip_letters_are_judged_with_the_markers_the_engine_draws():
    """The top check speaks where the engine's own reserve says it must.

    With both marker boxes typed 0 the renderer still draws 2 + 2 mm markers,
    `geometry.strip_label_reserve_mm` puts the label band 5.0 mm down, and on a
    sheet whose first patch row starts at 9.0 mm the letters are on the
    patches. Measured off `geometry.placement`, which is the function the
    renderer lays the page out with.
    """
    from workflow.layout_engine import geometry as _geom
    from workflow.layout_engine import papers as _papers

    r = _recipe(0.0, margin_bottom=12.0)
    r.instrument, r.paper, r.layout_mode = "i1", "A4", "area_first"
    r.use_instrument_margins = False
    r.margin_top, r.text_edge_top_mm = 8.0, 2.0
    r.helper_markers, r.helper_markers_top_bottom = True, True
    r.helper_marker_edge_mm = r.helper_marker_len_mm = 0.0
    r.show_strip_indicators = True

    g = instruments.geom_from_build_kwargs(r.build_kwargs())
    w, h = _papers.dimensions_mm(r.paper)
    pl = _geom.placement(g, w, h, _geom.compute(g, w, h, 120))
    ink = float(getattr(g, "label_ink_bottom_mm", 0.0) or 0.0)
    over = float(pl.leader_top) + ink - float(pl.y0_first)
    assert over > 0.05, (
        f"the letters no longer reach the patches here ({over:.2f} mm); "
        "re-measure before changing this test")

    said = [m for m in TabChart._engine_text_notes(_Tab(r))[1]
            if "strip letters are printed over the patches" in m]
    assert said, (
        f"{over:.2f} mm of every strip letter is on the first row of patches "
        "and the panel said nothing, because it read the marker boxes as 0 "
        "where the engine reads them as 2.0")


def test_the_gates_answer_with_the_markers_the_engine_draws():
    """A BEHAVIOURAL GUARD, BECAUSE THE SOURCE GREP WAS A SPELLING.

    An adversary round proved the point by rewriting one call site as
    `float(r.helper_marker_edge_mm or 0.0)`, with no `getattr(r,` on the line:
    the grep passed and the whole file stayed green. It also measured what the
    raw read does at `_bottom_clears_with`: with both marker boxes typed 0 it
    flips `lowering_b_clears` in 5 of 140 reachable states, **every one of them
    to True**, which is the "lower B and it clears" promise this block was
    rewritten to stop making.

    So this asks the function, not the file: a box typed 0 must answer exactly
    as a box typed 2.0 does, because that is what the engine draws.

    MUTATION: read the raw field in `_bottom_clears_with` and this goes red.
    """
    from dataclasses import replace
    from ui.tabs.tab_chart import lowering_b_clears, markers_off_clears
    base = _recipe(28.0, margin_bottom=12.0)
    base.use_instrument_margins = False
    flips = []
    for lines, line_mm in ((1, 12.1), (2, 12.1), (1, 20.6)):
        for mb in (8.0, 12.0, 20.0):
            zero = replace(base, margin_bottom=mb, helper_markers=True,
                           helper_marker_edge_mm=0.0, helper_marker_len_mm=0.0,
                           helper_markers_top_bottom=True)
            drawn = replace(zero, helper_marker_edge_mm=2.0,
                            helper_marker_len_mm=2.0)
            for fn in (lowering_b_clears, markers_off_clears):
                if fn(zero, lines, line_mm) != fn(drawn, lines, line_mm):
                    flips.append((fn.__name__, mb, lines, line_mm))
    assert not flips, (
        "a marker box typed 0 draws 2.0 mm, and these gates answered as if it "
        f"drew nothing: {flips}")


def _logical_lines(source: str):
    """Every STATEMENT of `source` on one line, with its comments removed.

    A source rule that walks `splitlines()` reads a wrapped statement as two
    unrelated fragments, and adversary round 9 defeated the rule below with
    nothing cleverer than the line wrap black formats to anyway::

        edge_mm = float(getattr(rec,
                                "helper_marker_edge_mm", 0.0) or 0.0)

    The continuation line `.strip()`s to `"helper_marker_edge_mm", 0.0)...`,
    which starts with a quote, and the rule waved it through as prose naming
    the field. Put into the overlay's Guided branch it took a sheet carrying
    214 dashes down to none while three test files stayed green (57 passed).

    Joining the statement closes it by construction: the text a rule sees
    starts at the statement, so a continuation can never masquerade as the
    beginning of one, and a `_marker_reserve_args` two lines down still
    exempts the read it belongs to. Comments are dropped, so a SAFE word in a
    trailing comment cannot exempt the code beside it either.
    """
    import io
    import tokenize

    rows = source.splitlines()
    comments = {}                       # row -> column where the comment starts
    spans, start = [], None
    for tok in tokenize.generate_tokens(io.StringIO(source).readline):
        if tok.type == tokenize.COMMENT:
            comments.setdefault(tok.start[0], tok.start[1])
            continue
        if tok.type in (tokenize.NL, tokenize.INDENT, tokenize.DEDENT,
                        tokenize.ENCODING, tokenize.ENDMARKER):
            continue
        if start is None:
            start = tok.start[0]
        if tok.type == tokenize.NEWLINE:
            spans.append((start, tok.end[0]))
            start = None
    out = []
    for first, last in spans:
        parts = []
        for n in range(first, last + 1):
            row = rows[n - 1]
            if n in comments:
                row = row[:comments[n]]
            parts.append(row.strip())
        out.append((" ".join(x for x in parts if x), first))
    return out


def test_no_raw_marker_read_survives_anywhere_in_the_panel():
    """…and the source rule that catches a NEW call site, spelling and all.

    The earlier version matched `getattr(r,` on the line, so the same read
    written as a plain attribute slipped through it three times in one round.
    The rule here is the principle rather than a spelling: **a line that reads
    one of those two fields must also say what a box left at 0 means**, either
    by substituting the engine's own default or by going through
    `_marker_reserve_args`. A read that falls back to 0.0, or does not fall
    back at all, is the fault.

    MUTATION: write `float(r.helper_marker_edge_mm or 0.0)` anywhere in the
    module and this goes red, which is exactly the spelling that defeated the
    old test.
    """
    import inspect
    import re
    from ui.tabs import tab_chart as tc
    FIELDS = ("helper_marker_edge_mm", "helper_marker_len_mm")
    SAFE = ("_marker_reserve_args", "_MARKER_DEFAULT_MM", "or 2.0", "_HM_KEYS")
    bad = []
    # ONE STATEMENT PER LINE, NOT ONE PHYSICAL LINE. See `_logical_lines`: the
    # physical-line version of this rule was defeated by an ordinary wrap.
    for line, _lineno in _logical_lines(inspect.getsource(tc)):
        if not any(f in line for f in FIELDS):
            continue
        t = line.strip()
        if t.startswith('"') or t.startswith("'"):
            continue                      # a docstring naming the field
        if any(w in line for w in SAFE):
            continue                      # reads it the way the engine does
        if re.search(r"helper_marker_(edge|len)_mm\s*=", line):
            continue                      # builds a recipe, does not read a box
        # A DICT KEY IS SPELT WITH A COLON, AND THE COMMA SWALLOWED THE FAULT.
        #
        # This exemption was `["\']field["\']\s*[:,)]`, which also matches
        # every `getattr(obj, "helper_marker_edge_mm", 0.0)` -- the exact
        # spelling the original fault was written in. Adversary round 8 put
        # `float(getattr(rec, "helper_marker_edge_mm", 0.0) or 0.0)` into the
        # overlay's Guided branch: on a chart built with both boxes at 0 the
        # preview went from the sheet's own 214 dashes to NONE, measured in the
        # real window (`scripts/adv18c_the_guided_branch_on_a_manual_sheet.py`),
        # and the everyday tier came back 14,619 passed, exit 0. The other
        # source test cannot help -- it is scoped to `_engine_text_notes`, and
        # it matches the literal `getattr(r,`, so `getattr(rec,` is invisible to
        # it as well. A dict key keeps its colon; a settings key says so.
        #
        # Round 9 generalised it once more. A NAME IS NOT A READ: where the
        # field appears only as a quoted string and the statement never
        # reaches THROUGH an object for it, there is no box being read, so a
        # dict key, a settings key and a tuple of persisted key names are all
        # exempt by the same sentence. A subscript IS a read and stays in.
        _reaches = ("getattr(" in line
                    or re.search(r"\.helper_marker_(edge|len)_mm\b", line)
                    or re.search(
                        r"\[\s*[\"']helper_marker_(edge|len)_mm[\"']\s*\]",
                        line))
        if not _reaches and re.search(
                r"[\"']helper_marker_(edge|len)_mm[\"']", line):
            continue                      # a key or a name, never a box
        bad.append(t)
    assert not bad, (
        "these lines read a marker box without saying what a 0 means; use "
        "`_marker_reserve_args(r)` or the engine's own default:\n  "
        + "\n  ".join(bad))


# ---- adversary round 9 ------------------------------------------------------
#: Every control the four bottom-text messages quote, and the catalogue key its
#: own widget label is registered under. The prose drops the label's colon.
_QUOTED_CONTROLS = {
    "Bottom": "Bottom",
    "Margins (mm)": "Margins (mm):",
    "Sheet text": "Sheet text",
    "B": "B",
    "Text distance from edge (mm)": "Text distance from edge (mm):",
    "Print helper markers": "Print helper markers",
}


def _bottom_message_keys(cat: dict) -> list:
    """The four new bottom-text wordings and the two lever sentences."""
    return [k for k in cat
            if "patches come down to" in k or k.startswith("Lowering “B”")]


@pytest.mark.parametrize("code", sorted(
    p.stem for p in (_ROOT / "data/i18n").glob("*.json")
    if not p.stem.startswith("parameters")))
def test_every_language_names_the_margin_box_as_that_language_shows_it(code):
    """A REMEDY THAT NAMES A CONTROL THE READER CANNOT FIND IS NOT A REMEDY.

    `test_the_type_help_says_which_set_and_which_chart.py` asks exactly this of
    the report-type help, and the same change set rewrote these four chart
    messages into new keys and re-translated them in all twelve catalogues with
    nothing asking it here.

    MEASURED, adversary round 9, driving the real window: in it, no, pl, ru and
    sv the two "Raise Bottom" wordings named a word that is not on the box, and
    in zh_CN all four named 「下」 -- which is what that window calls the "B" box
    under "Text distance from edge (mm)", so one notice used the same name for
    two different controls one sentence apart. Photographed in Norwegian and in
    Chinese with the "Margins (mm)" group in the same picture. Every one of the
    REMOVED strings had it right, so this was a regression, not a gap.

    MUTATION: put «Nederst» back in no.json's one-line "Raise Bottom" wording
    and this goes red for `no` alone.
    """
    import json as _json
    import re as _re
    cat = _json.loads((_ROOT / "data/i18n" / f"{code}.json").read_text(
        encoding="utf-8"))
    for key in _bottom_message_keys(cat):
        body = cat.get(key)
        assert body, f"{code} has no translation of {key[:50]!r}"
        for english in sorted(set(_re.findall(r"“([^”]+)”", key))):
            label_key = _QUOTED_CONTROLS.get(english)
            if label_key is None:
                continue
            want = cat.get(label_key, english).rstrip(":").strip()
            assert want in body, (
                f"{code}: the message names {english!r}, which this language's "
                f"own window labels {want!r}, and {want!r} is nowhere in the "
                f"translation:\n  {body}")


# ---- adversary round 10 -----------------------------------------------------
def test_a_ceiling_that_cannot_be_built_does_not_deny_every_margin_below_it():
    """"NO BOTTOM MARGIN THIS SHEET ALLOWS WILL CLEAR IT" -- AND 36.5 mm DOES.

    :func:`margin_rise_that_clears_mm` gave up on one assumption it documents
    as false. The line that probes the ceiling,

        ``if _bracket >= cap_mm and not clears(cap_mm): return None``

    reads the largest rise the box will hold as a verdict on every smaller one
    -- on a predicate the same function calls NOT monotone twenty lines further
    down (*"a rise of 9.7 mm clears, 9.8 does not, and 9.9 clears again,
    because a whole row of patches drops out and comes back"*). On a small
    paper the ceiling is not merely worse than the answer, it cannot be laid
    out at all, so that one probe denied every margin below it.

    MEASURED ON SCREEN, 2026-09-15, in the real window, with the chart really
    built and the message read back off the "Measured from Preview" field
    (`scripts/adv20c_no_margin_clears_it_except_36_5.py`): i1Pro, Paper =
    Custom 62 x 88 mm (the pulldown's "Custom…", whose boxes take 20 to 2000
    mm), "Prioritise patch size", helper markers on for top and bottom at
    4.0 + 2.0 mm, sheet text plus the settings stamp at 36 pt, margins
    12 / 6 / 12 / 12 with "Use instrument margins" unticked. The panel printed

        "… No bottom margin this sheet allows will clear it: “Bottom” under
         “Margins (mm)” stops at 60 mm and even that leaves the text in the
         patches. Make the sheet text smaller under “Sheet text”, or switch
         one of the two lines off."

    Typing 36.5 into that very box cleared it, and so did every grid point up
    to 47.0 -- twenty-two of them. Photographed both ways, four warnings on
    the panel against three.

    MUTATION: put ``return None`` back in place of the full-range walk and
    this goes red, with ``assert None is not None``.
    """
    from dataclasses import replace
    from ui.tabs.tab_chart import margin_rise_that_clears_mm
    from workflow.layout_engine import geometry as _geom
    from workflow.layout_engine import papers as _papers

    r = _recipe(36.0, margin_bottom=6.0)
    r.instrument, r.paper, r.layout_mode = "i1", "62x88", "patch_first"
    r.use_instrument_margins = False
    r.margin_top = r.margin_left = r.margin_right = 12.0
    r.helper_markers = r.helper_markers_top_bottom = True
    r.helper_marker_edge_mm, r.helper_marker_len_mm = 4.0, 2.0
    r.text_edge_mm, r.stamp_command = 4.0, True

    w, h = _papers.dimensions_mm(r.paper)

    def builds(mb: float) -> bool:
        cand = replace(r, margin_bottom=mb)
        try:
            g = instruments.geom_from_build_kwargs(cand.build_kwargs())
            _geom.compute(g, w, h, 120)
            return True
        except Exception:                            # noqa: BLE001
            return False

    # THE PREMISE, MEASURED: the ceiling this function probes cannot be laid
    # out at all, and the answer below it can.
    assert not builds(60.0), (
        "a 60 mm bottom margin lays out on this sheet after all, so the "
        "ceiling probe never raises and this test proves nothing; re-measure")
    assert builds(36.5), "36.5 mm no longer lays out; re-measure"

    line = raster.sheet_text_line_mm(r.chart_text_size_mm, r.chart_text_font,
                                     False, False, r.dpi)
    rise = margin_rise_that_clears_mm(r, None, 7.0, 2, line, hint_mm=12.0)
    assert rise is not None, (
        "the search still denies every margin because the ceiling cannot be "
        "built")
    assert not _bottom_notice(replace(r, margin_bottom=6.0 + rise)), (
        f"the rise it names ({rise} mm) does not clear the collision")
    said = _bottom_notice(r)
    assert "Raise “Bottom”" in said, said
    assert "No bottom margin this sheet allows" not in said, (
        "the panel still tells a reader nothing will work while 36.5 mm "
        f"does:\n  {said}")


def _marker_box_reads(source: str):
    """Every STATEMENT of *source* that reaches for a marker box, by AST.

    **A SPELLING RULE IS DEFEATED BY A SPELLING, TWICE NOW.** Round 8 beat the
    `getattr(r,` literal with `getattr(rec,`; round 9 beat the physical-line
    walk with an ordinary wrap; and round 10 measured four more spellings the
    rewritten rule still waves through, none of them clever::

        float(r.__dict__.get("helper_marker_edge_mm", 0.0) or 0.0)
        float(asdict(r).get("helper_marker_edge_mm", 0.0) or 0.0)
        float(operator.attrgetter("helper_marker_edge_mm")(r) or 0.0)
        replace(r, helper_marker_edge_mm=float(r.helper_marker_edge_mm or 0.0))

    The last one is the worst, because it is not exotic: the whole statement
    was exempt from the text rule by ``helper_marker_edge_mm\\s*=``, which is
    there to let a recipe be BUILT, and a statement can build one and read a
    box in the same breath.

    So this asks the code instead of the text. A read is an attribute load of
    the field, a subscript by its name, or its name handed to something that
    LOOKS A VALUE UP (`getattr`, `attrgetter`, `.get`, `.pop`). A dict key, a
    tuple of persisted key names and a keyword argument that BUILDS a recipe
    are none of those and stay exempt by construction rather than by a
    pattern, and a settings key keeps its own exemption because the saved
    preference is a different store from the box.
    """
    import ast
    rows = source.splitlines()
    FIELDS = ("helper_marker_edge_mm", "helper_marker_len_mm")

    def looks_a_value_up(call) -> bool:
        f = call.func
        if isinstance(f, ast.Name) and f.id in ("getattr", "attrgetter"):
            return True
        if isinstance(f, ast.Attribute):
            if f.attr == "attrgetter":
                return True
            if f.attr in ("get", "pop"):
                # …but a SETTINGS key is not a box. `tab_chart` saves the two
                # boxes under the same names, and that read is the preference.
                return "settings" not in ast.unparse(f.value).lower()
        return False

    def reaches(node) -> bool:
        for sub in ast.walk(node):
            if (isinstance(sub, ast.Attribute) and sub.attr in FIELDS
                    and isinstance(sub.ctx, ast.Load)):
                return True
            if (isinstance(sub, ast.Subscript)
                    and isinstance(sub.slice, ast.Constant)
                    and sub.slice.value in FIELDS):
                return True
            if isinstance(sub, ast.Call) and looks_a_value_up(sub):
                for arg in list(sub.args) + [k.value for k in sub.keywords]:
                    if isinstance(arg, ast.Constant) and arg.value in FIELDS:
                        return True
        # …AND THE NAME DOES NOT HAVE TO BE THE CALL'S OWN ARGUMENT.
        #
        # Round 21 measured four more spellings the rule above waves through,
        # and unlike round 10's local alias one of them is a shape this very
        # file already uses (`tuple(getattr(rec, k) for k in self._HM_KEYS)`,
        # line ~22008), so it is what somebody writes NEXT::
        #
        #     for _f in ("helper_marker_edge_mm", "helper_marker_len_mm"):
        #         v = float(getattr(r, _f, 0.0) or 0.0)
        #     vals = {k: getattr(r, k) for k in ("helper_marker_edge_mm", …)}
        #     edge, ln = (getattr(r, k) for k in ("helper_marker_edge_mm", …))
        #
        # The lookup's argument is a NAME there, so no constant is ever handed
        # to `getattr` and the walk above sees nothing. What the statement does
        # carry is both halves: a call that looks a value up, and the field
        # spelt out. Neither half alone is a read -- a bare tuple of key names
        # is a name being a name, and a settings `.get` is a different store --
        # so the pair is the rule, and all six must-not-catch cases below still
        # pass it: a dict key, a key tuple, a settings get and set, a keyword
        # that BUILDS a recipe and a plain write carry no lookup call at all.
        _looks_up = any(isinstance(s, ast.Call) and looks_a_value_up(s)
                        for s in ast.walk(node))
        if _looks_up:
            for sub in ast.walk(node):
                if isinstance(sub, ast.Constant) and sub.value in FIELDS:
                    return True
        return False

    out = []
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.stmt):
            continue
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef,
                             ast.ClassDef)):
            continue                      # its body is walked on its own
        end = node.end_lineno or node.lineno
        text = " ".join(rows[n - 1].strip() for n in range(node.lineno, end + 1))
        if reaches(node):
            out.append((text, node.lineno))
    return out


def test_no_raw_marker_read_survives_a_rule_that_reads_the_code():
    """…and the rule that cannot be beaten by how the read is SPELT.

    Both sibling rules above are kept: the text one still catches a bare name,
    and the behavioural one (`test_the_gates_answer_with_the_markers_the_engine
    _draws`) is the only one that can speak for a read in another module. What
    this adds is every spelling of a read INSIDE this module, measured against
    the four that got through on 2026-09-15.

    MUTATION: write any of the four spellings in the helper's docstring
    anywhere in `ui/tabs/tab_chart.py` and this goes red. So does
    `float(r.helper_marker_edge_mm or 0.0)`.
    """
    import inspect
    from ui.tabs import tab_chart as tc
    SAFE = ("_marker_reserve_args", "_MARKER_DEFAULT_MM", "or 2.0", "_HM_KEYS")
    bad = [t for t, _ln in _marker_box_reads(inspect.getsource(tc))
           if not any(w in t for w in SAFE)]
    assert not bad, (
        "these statements read a marker box without saying what a 0 means; "
        "use `_marker_reserve_args(r)` or the engine's own default:\n  "
        + "\n  ".join(bad))


@pytest.mark.parametrize("spelling", (
    'edge = float(r.helper_marker_edge_mm or 0.0)',
    'edge = float(getattr(rec, "helper_marker_edge_mm", 0.0) or 0.0)',
    'edge = float(r.__dict__.get("helper_marker_edge_mm", 0.0) or 0.0)',
    'edge = float(asdict(r).get("helper_marker_len_mm", 0.0) or 0.0)',
    'edge = float(operator.attrgetter("helper_marker_edge_mm")(r) or 0.0)',
    'edge = float(vars(r)["helper_marker_edge_mm"] or 0.0)',
    'c = replace(r, helper_marker_edge_mm=float(r.helper_marker_edge_mm or 0))',
    'edge = float(getattr(r,\n               "helper_marker_edge_mm", 0.0) or 0)',
    # …and round 21's three, where the lookup's argument is a NAME. The first
    # is not exotic: `tuple(getattr(rec, k) for k in self._HM_KEYS)` is already
    # in the file, so this is the shape the next raw read arrives in.
    ('for _f in ("helper_marker_edge_mm", "helper_marker_len_mm"):\n'
     '    v = float(getattr(r, _f, 0.0) or 0.0)'),
    ('vals = {k: float(getattr(r, k, 0.0) or 0.0)\n'
     '        for k in ("helper_marker_edge_mm", "helper_marker_len_mm")}'),
    ('edge, ln = (float(getattr(r, k, 0.0) or 0.0)\n'
     '            for k in ("helper_marker_edge_mm", "helper_marker_len_mm"))'),
))
def test_the_rule_catches_every_spelling_that_ever_got_through(spelling):
    """THE RULE IS ONLY WORTH ITS MUTATIONS. Each of these is a read that a
    version of this guard waved through, or one an adversary round wrote into a
    live call site and watched the suite stay green."""
    assert _marker_box_reads(spelling), (
        f"a raw marker-box read spelt {spelling!r} is invisible to the rule")


@pytest.mark.parametrize("spelling", (
    'x = {"helper_marker_edge_mm": 2.0}',
    '_HM = ("helper_markers", "helper_marker_edge_mm", "helper_marker_len_mm")',
    'self._settings.set("helper_marker_edge_mm", float(w.value()))',
    'v = self._settings.get("helper_marker_len_mm", 2.0)',
    'cand = replace(r, helper_marker_edge_mm=2.0, helper_marker_len_mm=2.0)',
    'r.helper_marker_edge_mm = 0.0',
))
def test_the_rule_still_lets_a_name_be_a_name(spelling):
    """A NAME IS NOT A READ, which is round 9's own sentence and still right.

    A dict key, a tuple of persisted key names, a settings key, a keyword that
    BUILDS a recipe and a plain write are not boxes being read, and a rule that
    flags them would be swept round after round until somebody deleted it.
    """
    assert not _marker_box_reads(spelling), (
        f"{spelling!r} is not a marker box being read and the rule says it is")
