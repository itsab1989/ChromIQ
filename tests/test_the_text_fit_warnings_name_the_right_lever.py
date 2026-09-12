"""The red messages under the preview must be TRUE and must name real boxes.

Knut, issue #182, 2026-09-11, with a screenshot of the message and the preview
(a ColorMunki A4 preset, a 24 mm clip border on the right, its own custom text,
and Chart Notes set):

    "The warning says that neither the right margin or the "clip" can free room
    here. First, the "Clip" is not a clear reference for a user that you mean
    the "Clip" setting in "Text distance from edge" frame. This should be
    referred to a bit more clear for a user to understand. Then, it is not
    really true that right margin cannot free room here. The Right margin is
    here overruled by the Clip-border width. Both clip border width or right
    margin should here be able to make more room. If clip-border width is kept
    at 24mm and right margin is increased to be bigger than this, then that
    should free more room in the right margin area, which it does. If the right
    margin is increased to 28mm, the clip-border text is shown fine […] The
    warning could indicate how much more space the right margin needs to show
    the Chart Notes properly, given the minimum font size requirement or the set
    font size number."

and on the "leave it" half of the same sentence:

    "the warning message above also says "..., or leave it and read them over
    the patches". The Chart Notes are placed over the patches, before the
    clip-border text area, but they are so small you cannot see them."

The message this file guards replaced one that said, verbatim, *"Neither the
right margin nor “Clip” can free room here: put the clip border on the LEFT if
you want the notes on clean paper, or leave it and read them over the
patches."* It was reproduced word for word on screen against Knut's own
`testHex` project before it was touched, by
`scripts/drive_182_text_shrink_floor.py`.
"""
from __future__ import annotations

import os
import re

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from ui.tabs.tab_chart import TabChart                    # noqa: E402
from workflow import text_edge_fit as tef                 # noqa: E402
from workflow.layout_engine import instruments            # noqa: E402
from workflow.layout_engine.presets import LayoutRecipe   # noqa: E402


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


class _Tab:
    """Just enough TabChart for the real method to run."""
    _manual_btn = _Btn()
    _manual_layout_panel = object()
    _settings = _Settings()

    def __init__(self, recipe, notes="a note about this chart", stamp=True):
        self._recipe = recipe
        self._manual_chart_notes_edit = _Edit(notes)
        self._manual_stamp_cmd_check = _Btn(stamp)

    def _current_layout_recipe(self):
        return self._recipe


def _recipe(*, margin_r=24.0, clip=4.0, band=24.0, side="right",
            content="text", clip_text="one line", note_size_mm=0.0,
            clip_size_mm=0.0):
    r = LayoutRecipe()
    r.instrument, r.paper, r.layout_mode = "CM", "A4", "area_first"
    r.show_strip_indicators, r.show_row_indicators = True, False
    r.clip_border = band > 0
    r.clip_border_width_mm = band
    r.clip_side = side
    r.clip_content_mode = content
    r.clip_text = clip_text
    r.clip_text_size_mm = clip_size_mm
    r.text_edge_clip_mm = clip
    r.chart_text_size_mm = note_size_mm
    r.margin_top = r.margin_bottom = 10.0
    r.margin_left = 14.0
    r.margin_right = margin_r
    return r


def _over(r, **kw) -> list[str]:
    return TabChart._engine_text_notes(_Tab(r, **kw))[1]


def _note_line(r, **kw) -> str:
    lines = [w for w in _over(r, **kw) if "chart notes down the right edge" in w]
    assert lines, f"no chart-note warning at all; got {_over(r, **kw)!r}"
    return lines[0]


def _clip_line(r, **kw) -> str:
    lines = [w for w in _over(r, **kw) if "clip border text" in w]
    assert lines, f"no clip-text warning at all; got {_over(r, **kw)!r}"
    return lines[0]


#: Four lines at the auto floor take ``4 x 1.2 x pt_to_mm(floor)`` across the
#: band, and the page-edge reserve is a LIMIT that is never spent on them
#: (Knut, 2026-09-12), so a band narrower than the text plus that reserve puts
#: the rest over the patches. Both bands are DERIVED from the floor rather than
#: typed: writing 16.0 and 11.0 here is what made this file go quiet the moment
#: the floor moved from 8 pt to 7.
_FOUR_LINES_MM = tef.clip_text_needed_mm(4)
#: Narrow enough that the lines do not fit inside the reserve, so some of the
#: text is printed over the patch area.
_TOO_NARROW_BAND = round(_FOUR_LINES_MM, 1)
#: Wide enough for the lines AND the reserve, so nothing reaches the patches.
_ROOMY_BAND = round(tef.clip_band_needed_mm(4.0, 4) + 0.5, 1)
#: Overflowing, but with enough band left that lowering "Clip" alone can fix
#: it. `_TOO_NARROW_BAND` is exactly the width of the text, so there the
#: reserve cannot be traded away far enough and the remedy is not offered.
_CLIP_CAN_HELP_BAND = round(_FOUR_LINES_MM + 1.0, 1)


# ----------------------------------------------------- K4(b): the false claim
def test_it_no_longer_says_the_right_margin_cannot_free_room():
    msg = _note_line(_recipe())
    assert "Neither the right margin" not in msg, msg
    assert "can free room here" not in msg, msg


def test_it_no_longer_offers_reading_an_invisible_note_over_the_patches():
    """K5. The note WAS shrunk to invisibility, so this was not an option."""
    msg = _note_line(_recipe())
    assert "read them over the patches" not in msg, msg


def test_raising_the_right_margin_past_the_band_really_does_free_room():
    """His own demonstration, as arithmetic the message can rely on.

    A warning that offers a lever has to be true, so the lever is exercised:
    at 24 mm (the band's own width) the notes have nothing, and the message
    names a margin at which they do. That margin must actually silence it.
    """
    msg = _note_line(_recipe(margin_r=24.0))
    m = re.search(r"to about ([0-9.]+) mm", msg)
    assert m, f"the message names no target right margin:\n  {msg}"
    target = float(m.group(1))
    assert target > 24.0, (
        f"the message asks for {target} mm, which is not past the 24 mm band")
    assert TabChart._engine_text_notes(
        _Tab(_recipe(margin_r=target + 0.2))) [1] == [] or not [
        w for w in _over(_recipe(margin_r=target + 0.2))
        if "chart notes down the right edge" in w], (
        f"the message asked for {target} mm and the warning survives there")


def test_the_margin_it_asks_for_is_the_arithmetic_and_not_a_guess():
    r = _recipe(margin_r=24.0)
    o = tef.chart_note_overlap("right", 24.0, 4.0, r.dpi, 24.0, 0.0)
    assert o is not None
    msg = _note_line(r)
    want = 24.0 + o.overlap_mm
    assert f"to about {want:.1f} mm" in msg, (
        f"the message does not name {want:.1f} mm:\n  {msg}")


# ------------------------------------------------- K4(a): name the real frame
def test_every_message_names_the_frame_the_clip_box_lives_in():
    """*"the 'Clip' is not a clear reference for a user"*."""
    for msg in (_note_line(_recipe()),
                _note_line(_recipe(band=0.0, content="off", side="left",
                                   margin_r=6.0)),
                _clip_line(_recipe(band=_TOO_NARROW_BAND,
                                   clip_text="a\nb\nc\nd")),
                _clip_line(_recipe(band=_CLIP_CAN_HELP_BAND,
                                   clip_text="a\nb\nc\nd"))):
        if "“Clip”" in msg:
            assert "Text distance from edge" in msg, (
                f"the message says “Clip” without saying which frame:\n  {msg}")


def test_the_shared_edge_message_names_the_clip_border_width_box():
    msg = _note_line(_recipe())
    assert "Clip border width" in msg, msg
    assert "Margins (mm)" in msg, msg


# --------------------------------------------- K4(c): say it at which size
def test_the_message_names_the_size_the_note_is_printed_at():
    auto = _note_line(_recipe())
    want = f"{tef.AUTO_SHRINK_FLOOR_PT:.0f} pt"
    assert want in auto, f"auto does not name the {want} floor:\n  {auto}"
    typed = _note_line(_recipe(note_size_mm=14.0 * 25.4 / 72.0))
    assert "14 pt" in typed, f"a typed 14 pt is not named:\n  {typed}"


def test_a_bigger_typed_size_asks_for_a_bigger_margin():
    small = _note_line(_recipe(margin_r=24.0, note_size_mm=0.0))
    big = _note_line(_recipe(margin_r=24.0, note_size_mm=20.0 * 25.4 / 72.0))
    def _target(m):
        return float(re.search(r"to about ([0-9.]+) mm", m).group(1))
    assert _target(big) > _target(small), (
        f"20 pt asks for no more paper than 8 pt:\n  {small}\n  {big}")


# ------------------------------------------------------ K6: the clip's text
def test_the_clip_border_text_warns_when_it_no_longer_fits_its_band():
    msg = _clip_line(_recipe(band=_TOO_NARROW_BAND,
                             clip_text="one\ntwo\nthree\nfour"))
    assert "4 lines" in msg, msg
    assert f"{tef.AUTO_SHRINK_FLOOR_PT:.0f} pt" in msg, msg
    assert "Clip border width" in msg, msg
    assert "does not fit its band" in msg, msg


def test_one_line_is_singular_and_two_are_not():
    one = _clip_line(_recipe(band=10.0, clip=4.0, clip_text="x",
                             clip_size_mm=40.0 * 25.4 / 72.0))
    assert "One line" in one and "lines" not in one, one
    many = _clip_line(_recipe(band=_TOO_NARROW_BAND, clip_text="a\nb\nc\nd"))
    assert "Its 4 lines" in many, many
    # THE BAND MUST BE WIDER THAN THE PATCH BORDER, or there is no band:
    # `instruments` stores `lbord = clip_border_width - border` and the panel
    # is silent when `lbord` is 0, because `geometry.clip_area_mm` draws
    # nothing there. A 6 mm band on a CM chart, whose border is 6 mm, is that
    # case, and it is what this line used to ask for.
    over_one = _clip_line(_recipe(band=12.0, clip=4.0, clip_text="x",
                                  clip_size_mm=40.0 * 25.4 / 72.0))
    assert "One line" in over_one and "lines" not in over_one, over_one


# --------------- Knut's ruling of 2026-09-12: the overflow goes INWARD
#: THE MARGIN HAS TO BE AT THE BAND for the overflow to reach the patches at
#: all. `instruments.geom_from_build_kwargs` raises the clip-side margin to the
#: band and never above it, so margin == band is the ordinary clip chart, and a
#: wider margin leaves clear paper between the band and the first patch column.
#: The default `_recipe` margin is 24 mm, which is that second case.
def _overflow(**kw):
    return _recipe(band=_TOO_NARROW_BAND, margin_r=_TOO_NARROW_BAND,
                   clip_text="a\nb\nc\nd", **kw)


def test_the_clip_text_overflows_over_the_patches_and_is_told_so():
    """*"The text on each of the 4 sides shall NOT cross the text-edge distance
    limit on every side … the text shall overlap in the other direction,
    inward and over the edges of the patch area instead."*"""
    msg = _clip_line(_overflow())
    assert "printed inward, past the band" in msg, msg
    assert "lands on the patch area" in msg, msg
    assert "closer to the paper edge than you asked" not in msg, (
        "the outward push is being reported again:\n" + msg)
    # AND IT DOES NOT CLAIM THE PAGE-EDGE DISTANCE IS NEVER CROSSED, because
    # it is: `clip_content_inset_mm` caps the reserve at a fifth of the band,
    # so on Knut's own 12 mm band at Clip 4 mm the ink prints 2.79 mm from the
    # paper edge, 1.2 mm inside the distance the box asks for. The message
    # names the reserve actually kept instead (the four-side audit,
    # 2026-09-12).
    assert "is a limit and is never crossed" not in msg, msg
    assert "kept clear at the paper edge" in msg, msg
    assert "or a fifth of the band where that is less" in msg, msg
    assert "Text distance from edge" in msg, msg
    assert "Clip border width" in msg, msg
    assert "Clip-border content" in msg, msg


def test_the_warning_says_what_the_overlap_costs():
    """A user who leaves the text there is putting ink on measured patches.

    That is the part of this worth more than the geometry, so it is checked
    rather than left to the reader of the code.
    """
    msg = _clip_line(_overflow())
    assert "measured with the ink on them" in msg, msg
    assert "the patch and the text together" in msg, msg


def test_it_does_not_claim_the_patches_are_inked_when_they_are_not():
    """THE SAME BAND, a wider margin, and the text lands on clear paper.

    Measured on Knut's own run 1 with a 12 mm band and a 32 mm right margin:
    2.3 mm of text past the band, 17.7 mm of clear paper beyond it, and not one
    patch inked. A message that said otherwise would be asserting something the
    sheet does not show, which is the fault section 2c records twice.
    """
    msg = _clip_line(_recipe(band=_TOO_NARROW_BAND, margin_r=40.0,
                             clip_text="a\nb\nc\nd"))
    assert "printed inward, past the band" in msg, msg
    assert "reaches clear paper, so it lands on nothing" in msg, msg
    assert "lands on the patch area" not in msg, msg
    assert "measured with the ink on them" not in msg, msg
    assert "row indicator labels" not in msg, msg


def test_it_names_the_millimetres_that_go_over_the_patches():
    r = _overflow()
    want = tef.clip_text_overhang_mm(_TOO_NARROW_BAND, r.text_edge_clip_mm, 4)
    assert want > 0.05
    msg = _clip_line(r)
    assert f"The remaining {want:.1f} mm" in msg, (
        f"the message does not name the {want:.1f} mm that overflow:\n  {msg}")
    # …and how much of that reaches the patches, which on this chart is all of
    # it because the margin sits at the band.
    assert f"{want:.1f} mm of it lands on the patch area" in msg, msg


def test_lowering_clip_is_offered_only_when_it_can_finish_the_job():
    """It buys back at most the reserve, so on a band narrower than the text
    needs it moves the overlap without removing it."""
    can = _recipe(band=_CLIP_CAN_HELP_BAND, clip_text="a\nb\nc\nd")
    assert "Lowering “Clip”" in _clip_line(can), _clip_line(can)
    cannot = _recipe(band=_TOO_NARROW_BAND, clip_text="a\nb\nc\nd",
                     clip_size_mm=40.0 * 25.4 / 72.0)
    msg = _clip_line(cannot)
    assert "Lowering “Clip”" not in msg, (
        "a remedy that cannot remedy is offered:\n" + msg)


def test_the_number_it_asks_for_really_silences_it():
    """Set the band to the width the message names, and the warning must go.

    IT IS NOT THE BAND PLUS THE SHORTFALL, which is what the first version of
    the message said: the page-edge reserve is a fifth of the band, so widening
    the band widens the reserve and gives part of it straight back. Measured
    here rather than reasoned about, because that arithmetic shipped once.
    """
    r = _recipe(band=_TOO_NARROW_BAND, clip_text="a\nb\nc\nd")
    msg = _clip_line(r)
    m = re.search(r"Widen “Clip border width” to about ([0-9.]+) mm", msg)
    assert m, f"the message names no target width:\n  {msg}"
    want = float(m.group(1))
    assert want > _TOO_NARROW_BAND, (want, _TOO_NARROW_BAND)
    wider = _recipe(band=round(want + 0.05, 2), clip_text="a\nb\nc\nd")
    assert not [w for w in _over(wider) if "clip border text" in w], (
        f"the message asked for {want} mm and the warning survives there")
    # …and the naive answer really does NOT silence it, which is why the
    # message stopped giving it.
    over = tef.clip_text_overhang_mm(_TOO_NARROW_BAND, r.text_edge_clip_mm, 4)
    naive = _recipe(band=round(_TOO_NARROW_BAND + over, 2),
                    clip_text="a\nb\nc\nd")
    assert [w for w in _over(naive) if "clip border text" in w], (
        "band plus the shortfall now works, so this file is guarding nothing")


def test_a_roomy_band_says_nothing_about_its_text():
    assert not [w for w in _over(_recipe(band=60.0, margin_r=60.0,
                                         clip_text="one line"))
                if "clip border text" in w]


def test_a_typed_clip_size_that_fits_is_silent_and_one_that_does_not_warns():
    fits = _recipe(band=16.0, clip_text="a\nb", clip_size_mm=4.0 * 25.4 / 72.0)
    assert not [w for w in _over(fits) if "clip border text" in w]
    doesnt = _recipe(band=16.0, clip_text="a\nb",
                     clip_size_mm=40.0 * 25.4 / 72.0)
    assert _clip_line(doesnt)


# ------------------ Knut's ruling of 2026-09-11: a note cut off the sheet
#: His own run 2 note, 141 characters, from the `test.zip` he attached.
KNUT_LONG_NOTE = (
    'i1Pro 1/2/3 600 patch target for 13x18cm / 5x7" photo card - print with '
    'borderless setting / NO expansion, retain size, color management: OFF'
)


def _cut_line(r, **kw) -> str:
    lines = [w for w in _over(r, **kw) if "too long for the sheet" in w]
    assert lines, f"nothing says the note was cut; got {_over(r, **kw)!r}"
    return lines[0]


def test_a_note_too_long_for_the_sheet_says_so_and_says_how_much():
    """It was a log line at INFO and nothing on screen.

    A note is cut at the floor, marked with an ellipsis, and Knut read that as
    the page overflowing. The paper is the smallest the app offers so the fault
    is reachable with a note of an ordinary length.
    """
    r = _recipe(margin_r=24.0)
    r.paper = "100x150"
    msg = _cut_line(r, notes=KNUT_LONG_NOTE * 3, stamp=False)
    assert "characters are cut off" in msg, msg
    assert "Sheet text" in msg, msg
    assert f"{tef.AUTO_SHRINK_FLOOR_PT:.0f} pt" in msg, msg
    # The count is a real count, not a word: it must name a number above one.
    n = int(re.search(r"The last (\d+) characters", msg).group(1))
    assert n > 1, msg


def test_one_character_is_singular(monkeypatch):
    """Never "(s)", and the singular branch has to be reachable to be checked.

    The fitter cuts to a PROPORTIONAL estimate of what will fit, so on a real
    sheet it drops a run of characters at a time and a note that loses exactly
    one is a coincidence, not something to search for. What is checked here is
    that the panel picks the singular sentence when the count is one, which is
    the branch, and the count itself is measured in
    `test_the_sheet_text_fits_the_sheet.py`.
    """
    from workflow import tiff_metadata as tm
    monkeypatch.setattr(tm, "note_characters_lost",
                        lambda *a, **k: 1)
    r = _recipe(margin_r=24.0)
    msg = _cut_line(r, notes="anything at all", stamp=False)
    assert "The last character is cut off" in msg, msg
    assert "characters" not in msg.split("cut off")[0], msg
    monkeypatch.setattr(tm, "note_characters_lost", lambda *a, **k: 2)
    many = _cut_line(r, notes="anything at all", stamp=False)
    assert "The last 2 characters are cut off" in many, many


def test_a_note_that_fits_says_nothing_about_length():
    assert not [w for w in _over(_recipe(margin_r=24.0), notes="a short note")
                if "too long for the sheet" in w]


def test_no_notes_and_no_stamp_means_no_note_warning():
    assert not [w for w in _over(_recipe(), notes="", stamp=False)
                if "chart notes down the right edge" in w]


def test_the_geometry_this_file_assumes_is_the_geometry_the_engine_builds():
    """The premise, measured rather than assumed: the band IS the clip zone."""
    g = instruments.geom_from_build_kwargs(_recipe().build_kwargs())
    assert abs((g.lbord + g.border) - 24.0) < 0.05, (
        f"a 24 mm clip border came out as a {g.lbord + g.border:.2f} mm zone")
    assert getattr(g, "clip_side", "left") == "right"


def test_a_chart_with_no_clip_border_is_not_told_it_has_one():
    """The ordinary patch border is not a clip band.

    `_clip_zone` is ``lbord + border``, and a CM/A4 recipe with the clip border
    OFF still reports ``lbord 0.0, border 6.0``. That made every no-border
    chart with a tight right margin read *"they share that edge with the clip
    border … the border takes the outer 6.0 mm"*, which is a band that is not
    there and advice ("put the clip border on the LEFT") that cannot be taken.
    """
    # SIDE "right", or `_clip_on_right` is False for the other reason and the
    # test proves nothing: an earlier version used "left" here and stayed green
    # with the predicate mutated back to `_clip_zone > 0`.
    msg = _note_line(_recipe(band=0.0, content="off", side="right",
                             margin_r=6.0))
    assert "clip border" not in msg, msg
    # …and the honest message is still raised, with the levers that do exist.
    assert "Margins (mm)" in msg and "Text distance from edge" in msg, msg


# ------------- Knut's edited post of 2026-09-12: the ROW LABELS on the left
def _left(band: float, lines: int, rows: bool = True, clip: float = 4.0):
    """A LEFT-hand band with row indicators, which is the only arrangement in
    which the clip text can reach the labels: they are down the left."""
    r = _recipe(band=band, side="left", clip=clip,
                clip_text="\n".join(f"l{i}" for i in range(1, lines + 1)))
    r.show_row_indicators = rows
    r.margin_left = band
    return r


#: Enough lines to reach the labels on that geometry, and enough to reach past
#: them to the patches. Named rather than typed into each test.
_LEFT_ON_LABELS = 6
_LEFT_ON_BOTH = 10


def test_a_left_band_that_reaches_the_labels_says_so():
    msg = _clip_line(_left(12.0, _LEFT_ON_LABELS))
    assert "crosses the row indicator labels" in msg, msg
    assert "find your place on the sheet" in msg, msg


def test_it_names_the_millimetres_that_cross_the_labels():
    from workflow.layout_engine import geometry as gm
    r = _left(12.0, _LEFT_ON_LABELS)
    kw = r.build_kwargs()
    g = instruments.geom_from_build_kwargs(kw)
    area = gm.row_label_area_mm(g, kw)
    hit = tef.clip_text_collision(g.lbord + g.border, r.text_edge_clip_mm,
                                  _LEFT_ON_LABELS, 0.0, area[0],
                                  float(g.margin_l))
    assert hit.over_labels_mm > 0.05
    assert f"{hit.over_labels_mm:.1f} mm of it crosses" in _clip_line(r), (
        f"the message does not name {hit.over_labels_mm:.1f} mm:\n"
        + _clip_line(r))


def test_the_panel_measures_the_label_and_does_not_use_the_reservation():
    """`rlwi` is sized for the worst case and sits several millimetres out from
    the ink. A panel that asked for it would warn about blank paper, so the
    number it prints must be the measured one."""
    from workflow.layout_engine import geometry as gm
    r = _left(12.0, _LEFT_ON_LABELS)
    kw = r.build_kwargs()
    g = instruments.geom_from_build_kwargs(kw)
    reserved = gm.row_label_area_mm(g)[0]
    measured = gm.row_label_area_mm(g, kw)[0]
    assert measured > reserved + 2.0, "the two agree, so this proves nothing"
    reach = tef.clip_text_reach_mm(g.lbord + g.border, r.text_edge_clip_mm,
                                   _LEFT_ON_LABELS, 0.0)
    msg = _clip_line(r)
    assert f"{reach - measured:.1f} mm of it crosses" in msg, msg
    assert f"{reach - reserved:.1f} mm of it crosses" not in msg, (
        "the panel is predicting from the reserved band:\n" + msg)


def test_a_deep_left_overflow_names_the_labels_AND_the_patches():
    msg = _clip_line(_left(12.0, _LEFT_ON_BOTH))
    assert "crosses the row indicator labels" in msg, msg
    assert "lands on the patch area" in msg, msg
    assert "measured with the ink on them" in msg, msg


def test_a_left_band_with_the_row_labels_OFF_never_mentions_them():
    msg = _clip_line(_left(12.0, _LEFT_ON_LABELS, rows=False))
    assert "row indicator labels" not in msg, msg
    assert "lands on the patch area" in msg, msg


def test_a_RIGHT_hand_band_never_mentions_the_row_labels():
    """They are down the LEFT, so a right-hand band cannot reach them however
    far its text runs."""
    r = _recipe(band=_TOO_NARROW_BAND, margin_r=_TOO_NARROW_BAND,
                clip_text="a\nb\nc\nd")
    r.show_row_indicators = True
    msg = _clip_line(r)
    assert "row indicator labels" not in msg, msg


def test_the_raise_clip_remedy_is_offered_and_is_the_smallest_that_works():
    from workflow.layout_engine import geometry as gm
    r = _left(12.0, _LEFT_ON_BOTH)
    msg = _clip_line(r)
    m = re.search(r"Raising “Clip” to ([0-9.]+) mm", msg)
    assert m, f"no raise-Clip remedy offered:\n  {msg}"
    want = float(m.group(1))

    def _over(clip_mm):
        r2 = _left(12.0, _LEFT_ON_BOTH, clip=clip_mm)
        kw = r2.build_kwargs()
        g2 = instruments.geom_from_build_kwargs(kw)
        area = gm.row_label_area_mm(g2, kw)
        return tef.clip_text_collision(
            g2.lbord + g2.border, r2.text_edge_clip_mm, _LEFT_ON_BOTH, 0.0,
            area[0], float(g2.margin_l)).over_labels_mm

    assert _over(want + 0.1) == 0.0, (
        f"raising Clip to {want} mm does not clear the labels")
    # AND IT IS NOT WILDLY MORE THAN IS NEEDED. Not exact, and it cannot be:
    # the gap between the label ink and the band's inner edge comes from
    # `rlwi`, which `raster.row_label_band_mm` measures on the PROVISIONAL
    # geometry, so moving "Clip" moves the margin and re-solves it. Measured on
    # this chart: the gap is 5.21 mm at Clip 4 and 4.22 mm at Clip 24, so the
    # answer is about a millimetre conservative, which is the safe direction
    # for a message that says "to about".
    assert _over(want - 1.5) > 0.0, (
        f"{want} mm is far more than is needed, so the message is asking for "
        f"left margin it does not have to spend")


def _i1_left(band: float, lines: int, clip: float = 4.0) -> LayoutRecipe:
    """An i1 left band, where the label RESERVATION barely exceeds the number.

    The ColorMunki chart `_left` builds over-allows by about 5 mm, so the
    label's own width and the paper between its floor and its ink come out
    within a millimetre of each other and either one clears the labels. Here
    they are 5.89 mm and 1.00 mm apart, which is what makes the difference
    visible at all.
    """
    r = _recipe(band=band, side="left", clip=clip,
                clip_text="\n".join(f"clip line {i}" for i in range(1, lines + 1)))
    r.instrument = "i1"
    r.show_row_indicators = True
    r.margin_left = band
    return r


def test_the_raise_clip_answer_is_the_floor_to_ink_offset_not_the_label_width():
    """The remedy named 21.0 mm and 25.9 mm was the number that works.

    `geometry.row_label_area_mm` answers ``(where the ink starts, where the
    band ends)``. The panel was subtracting ``[1] - [0]``, the WIDTH of the row
    number; what "Clip" carries when it raises the labels' floor is
    ``[0] - floor``. Two distances in one frame out of one call, which is how
    the wrong one was picked, and the function's own arithmetic is the same
    either way, so only a test that APPLIES the answer can see it.

    Driven on screen (`scripts/adv1_remedies_attack.py`): told to raise "Clip"
    to 20.8 mm on an i1 chart with a 16 mm band and eight lines, the user got
    the same red warning back with 5.1 mm of the text still on the numbers.
    """
    from workflow.layout_engine import geometry as gm
    r = _i1_left(16.0, 8)
    kw = r.build_kwargs()
    g = instruments.geom_from_build_kwargs(kw)
    area = gm.row_label_area_mm(g, kw)
    floor = float(getattr(g, "row_label_floor", 0.0) or 0.0)
    width, offset = area[1] - area[0], area[0] - floor
    assert width > offset + 2.0, (
        f"on this chart the label width ({width:.2f} mm) and the floor-to-ink "
        f"offset ({offset:.2f} mm) are too close to tell apart")

    msg = _clip_line(r)
    assert "crosses the row indicator labels" in msg, msg
    m = re.search(r"Raising “Clip” to ([0-9.]+) mm", msg)
    assert m, f"no raise-Clip remedy offered:\n  {msg}"
    told = float(m.group(1))

    def _still_over(clip_mm: float) -> float:
        r2 = _i1_left(16.0, 8, clip=round(clip_mm, 2))
        kw2 = r2.build_kwargs()
        g2 = instruments.geom_from_build_kwargs(kw2)
        a2 = gm.row_label_area_mm(g2, kw2)
        return tef.clip_text_collision(
            g2.lbord + g2.border, r2.text_edge_clip_mm, 8, 0.0,
            a2[0], float(g2.margin_l)).over_labels_mm

    assert _still_over(told + 0.1) == 0.0, (
        f"the message says to raise “Clip” to {told:.1f} mm and "
        f"{_still_over(told + 0.1):.2f} mm of the text is still printed over "
        f"the row numbers there")
    # …and the distance it used to name does NOT work, so this is not a test
    # that would pass with the fix taken out again.
    reach = tef.clip_text_reach_mm(g.lbord + g.border, r.text_edge_clip_mm, 8,
                                   0.0)
    old = tef.clip_edge_to_clear_labels_mm(reach, width)
    assert _still_over(old + 0.1) > 1.0, (
        f"the label-width answer ({old:.1f} mm) clears the labels on this "
        f"chart too, so it cannot tell the two distances apart")


def test_a_clip_border_no_wider_than_the_patch_border_says_nothing():
    """There is no band at all, so there is no clip text to warn about.

    `instruments` stores `lbord = clip_border_width - border` and
    `geometry.clip_area_mm` returns None at `lbord <= 0`, so the renderer draws
    nothing. Measured on Knut's run 2, whose border is 10 mm, with the width
    set to 10: no clip content on the sheet and a red warning about eight lines
    printed 15.7 mm over the patches.
    """
    r = _recipe(band=6.0, clip_text="a\nb\nc\nd")   # CM's border is 6 mm
    g = instruments.geom_from_build_kwargs(r.build_kwargs())
    assert float(g.lbord) <= 0, "pick a width that really collapses the band"
    assert not [w for w in _over(r) if "clip border text" in w], (
        "the panel warns about a clip band that is never drawn")


# ------------------------- the four-side audit's two findings, 2026-09-12
def test_the_message_names_the_reserve_actually_kept_not_the_typed_one():
    """"Clip" is capped at a fifth of the band, so the two differ on a narrow
    band and the message has to print the one that decides.

    Measured on Knut's run 2 at Clip 4.0 mm, the outermost ink from the paper
    edge: a 40 mm band prints at 5.33, 26 mm at 5.08, 16 mm at 3.81 and 12 mm
    at 2.79. From about a 20 mm band down the ink is closer to the edge than
    the box asks, so a message quoting the box would be describing a distance
    the sheet does not keep.
    """
    r = _overflow()
    kept = tef.clip_content_inset_mm(_TOO_NARROW_BAND, r.text_edge_clip_mm)
    assert kept < r.text_edge_clip_mm - 0.05, (
        f"the cap does not bite at {_TOO_NARROW_BAND} mm, so this test is "
        f"not measuring the case it describes")
    msg = _clip_line(r)
    assert f"{kept:.1f} mm is kept clear" in msg, (
        f"the message does not name the {kept:.1f} mm actually kept:\n  {msg}")
    assert f"{r.text_edge_clip_mm:.1f} mm is kept clear" not in msg, (
        "the message quotes the typed Clip, which is not what is kept:\n"
        + msg)


def test_a_band_wide_enough_keeps_the_typed_clip_and_says_so():
    """The other half: where the cap does not bite, the two agree."""
    wide = 40.0
    r = _recipe(band=wide, margin_r=wide, clip=4.0,
                clip_text="\n".join(f"l{i}" for i in range(1, 15)))
    kept = tef.clip_content_inset_mm(wide, r.text_edge_clip_mm)
    assert kept == pytest.approx(r.text_edge_clip_mm, abs=0.01)
    assert f"{kept:.1f} mm is kept clear" in _clip_line(r)


@pytest.mark.parametrize("mode", ["image", "branding", "notes"])
def test_only_plain_text_is_told_it_overflows(mode):
    """The image and branding modes scale to whatever band they are given.

    Measured at a 12 mm band with four lines: the text really does reach
    13.46 mm, past the band, and branding reaches 11.18 mm and never leaves
    it, while the panel told both that 2.3 mm was printed past the band.
    """
    r = _recipe(band=_TOO_NARROW_BAND, margin_r=_TOO_NARROW_BAND,
                content=mode, clip_text="a\nb\nc\nd")
    assert not [w for w in _over(r) if "clip border text" in w], (
        f"content mode {mode!r} is warned about as if it were text")
    # …and the same chart in TEXT mode still is, so the gate is not simply off.
    text = _recipe(band=_TOO_NARROW_BAND, margin_r=_TOO_NARROW_BAND,
                   content="text", clip_text="a\nb\nc\nd")
    assert _clip_line(text)
