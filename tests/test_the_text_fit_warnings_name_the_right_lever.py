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
                _clip_line(_recipe(band=16.0, clip_text="a\nb\nc\nd"))):
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
    assert "8 pt" in auto, f"auto does not name the 8 pt floor:\n  {auto}"
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
    msg = _clip_line(_recipe(band=16.0, clip_text="one\ntwo\nthree\nfour"))
    assert "4 lines" in msg, msg
    assert "8 pt" in msg, msg
    assert "Clip border width" in msg, msg


def test_one_line_is_singular_and_two_are_not():
    one = _clip_line(_recipe(band=10.0, clip=4.0, clip_text="x",
                             clip_size_mm=40.0 * 25.4 / 72.0))
    assert "One line" in one and "lines" not in one, one
    many = _clip_line(_recipe(band=16.0, clip_text="a\nb\nc\nd"))
    assert "Its 4 lines" in many, many


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
