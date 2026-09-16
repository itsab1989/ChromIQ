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


def _bottom_notice(r, *, bottom_mm=None) -> str:
    """The bottom notice this recipe earns, WITH the sheet's own measurement.

    Knut's ruling of 2026-09-15 (#182): the bottom check reads the patch
    area's measured bottom edge off "Measured from Preview" and says nothing
    without it. `report_for` gives the margins the geometry resolved, which is
    where the patch area lands on a rectangular chart that fills its page and
    so keeps every case in this file on the sheet it was written for;
    *bottom_mm* describes a sheet where it does not, which is the hexagonal and
    engine-off case his ruling is about.
    """
    from tests.margin_reports import report_for
    rep = report_for(r, bottom_mm=bottom_mm)
    lines = [w for w in TabChart._engine_text_notes(_Tab(r), rep)[1]
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
    # THE SIZE BEING DRAWN, NOT THE SIZE IN THE BOX. This used to require the
    # literal `sheet_text_line_mm(chart_text_size_mm`, which is 0 for "auto",
    # and while "auto" could never exceed `SHEET_TEXT_DEFAULT_MM` the two
    # agreed by accident. `text_edge_fit.AUTO_SIZE_CEILING_PT` lets "auto" grow,
    # and the moment it did, the block was positioned for a 4.2 mm line and
    # drawn at 16 pt: the ink crossed the "B" reserve on its way to the paper
    # edge. `_drawn_size_mm` is `chart_text_size_mm or the resolved auto size`.
    assert "sheet_text_line_mm(_drawn_size_mm" in src, (
        "the renderer has gone back to a line height of its own")
    assert "_drawn_size_mm = chart_text_size_mm or" in src, (
        "the renderer's line height no longer follows the size it draws at")
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
    from tests.margin_reports import report_for
    r = replace(_recipe(size_pt, margin_bottom=12.0), layout_mode=mode)
    # THE SIZES DIFFER BECAUSE THE MODES DO. Patch-first holds the patches far
    # higher on this recipe, so 28 pt there is not a collision at all and a
    # test asserting one would be asserting a fault. The premise is read off
    # the same report the panel is given, which since Knut's ruling of
    # 2026-09-15 is where the whole question is decided:
    bottom = report_for(r).bottom_mm
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
    assert _bottom_lever_note(4.0, 4.0, 0.0) == "", (
        "a box that already reads 0 was told to go lower")
    assert "will not help" in _bottom_lever_note(4.0, 7.0, 0.0), (
        "the markers really do hold the text here and that is worth saying")
    # …and the panel itself, on a chart whose box reads 0 with no markers.
    r = replace(_recipe(28.0, margin_bottom=12.0), text_edge_mm=0.0,
                helper_markers=False)
    said = _bottom_notice(r)
    assert "runs into the patches" in said
    assert "moves the text down" not in said, (
        "the panel told a reader to lower a box that is already at 0")


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


def test_no_bottom_message_names_a_rise_or_a_paper_any_more():
    """KNUT'S RULING OF 2026-09-15 TOOK BOTH PROMISES OUT.

    The four wordings this replaces were built around a searched rise ("Raise
    “Bottom” … by about {short} mm", from `margin_rise_that_clears_mm`) and,
    where no rise worked, around a claim about paper ("No bottom margin this
    sheet allows will clear it … A larger paper does not help", from
    `_larger_paper_note`). Both were answers to *"how much more margin clears
    it"*, and under the ruling nothing asks it: the numbers come from the sheet
    in the preview, and the next sheet has not been drawn.

    So the message states what is short, names the controls, and asks for a
    Generate Chart. Four states are checked, including the one that used to
    reach the ceiling wording (72 pt over a 10 mm bottom margin, two lines).

    MUTATION: put "by about {short:.1f} mm" back into either wording and this
    goes red.
    """
    from dataclasses import replace as _replace
    states = [
        _replace(_recipe(28.0, margin_bottom=12.0), use_instrument_margins=False),
        _replace(_recipe(18.0, margin_bottom=10.0), use_instrument_margins=False),
        _replace(_recipe(0.0, margin_bottom=10.0, stamp=False),
                 chart_text_size_mm=55.0, helper_markers=False,
                 use_instrument_margins=False),
        _replace(_recipe(72.0, margin_bottom=10.0, stamp=True),
                 use_instrument_margins=False),
    ]
    seen = 0
    for r in states:
        said = _bottom_notice(r)
        if not said:
            continue
        seen += 1
        assert "by about" not in said, (
            f"a rise is still being named, and nothing measured it:\n  {said}")
        assert "larger paper" not in said, (
            f"a claim about paper survives:\n  {said}")
        assert "No bottom margin this sheet allows" not in said, said
        assert "press Generate Chart" in said, (
            "the message must send the reader back to the one control that "
            f"can measure the next state:\n  {said}")
        assert "Raise “Bottom” under “Margins (mm)”" in said, said
        assert "(s)" not in said
    assert seen >= 3, f"only {seen} of these states warned; re-measure"


def test_the_bottom_message_quotes_the_measured_patch_edge(qapp=None):
    """The three numbers in the sentence are the sheet's, and one is measured.

    MUTATION: hand `report_for` a different `bottom_mm` and the quoted figure
    follows it, which is the whole of Knut's ruling in one assertion.
    """
    from dataclasses import replace as _replace
    r = _replace(_recipe(28.0, margin_bottom=12.0), use_instrument_margins=False)
    for bottom in (12.0, 9.5, 6.0):
        said = _bottom_notice(r, bottom_mm=bottom)
        assert said, f"no warning at a measured patch bottom of {bottom} mm"
        assert f"comes down to {bottom:.1f} mm" in said, (
            f"the message does not quote the measured patch edge {bottom}:"
            f"\n  {said}")


def test_the_bottom_check_is_silent_before_a_chart_is_generated():
    """*"they are only usable after the Measured from Preview margin values
    have been completed (after a Generate Chart has been performed)."*

    A prediction is not offered in its place, because the prediction is what
    was wrong on Knut's hexagonal chart.

    MUTATION: fall back to `r.margin_bottom` when there is no report and this
    goes red.
    """
    from dataclasses import replace as _replace
    r = _replace(_recipe(28.0, margin_bottom=12.0), use_instrument_margins=False)
    assert _bottom_notice(r), "the premise failed: this state must warn"
    none = [w for w in TabChart._engine_text_notes(_Tab(r), None)[1]
            if "sheet text along the bottom" in w]
    assert none == [], (
        "the bottom check spoke with nothing measured, so it is predicting "
        f"the patch edge again: {none}")


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

    # THE PATCH TOP THE PANEL IS GIVEN IS THE ONE MEASURED ABOVE. Since
    # Knut's ruling of 2026-09-15 the top check reads "Measured from Preview"
    # rather than the "Top" box, and `pl.y0_first` is where the renderer really
    # starts the first row, which is what the frame reports.
    from tests.margin_reports import report_for
    _rep = report_for(r, top_mm=float(pl.y0_first))
    said = [m for m in TabChart._engine_text_notes(_Tab(r), _rep)[1]
            if "strip letters are printed over the patches" in m]
    assert said, (
        f"{over:.2f} mm of every strip letter is on the first row of patches "
        "and the panel said nothing, because it read the marker boxes as 0 "
        "where the engine reads them as 2.0")


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
        if body == key:
            # AN UNTRANSLATED PLACEHOLDER IS THE ENGLISH SOURCE ITSELF, and the
            # English source quotes the English control by construction. The
            # fault this test was written for is a TRANSLATION that names a word
            # the reader's own window does not show; a placeholder is not a
            # translation, and the project's beta rule keeps new strings English
            # until the pre-release pass. `test_a_quoted_control_names_the_
            # control_the_reader_has.py` has carried the same exemption, in the
            # same words, since 2026-09-08. Without it a new sentence could only
            # be added by translating it into twelve languages in the same
            # commit, which is the rule this project has explicitly declined.
            continue
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
