"""The strip letters are judged against the real ruler dashes and against "T",
and clip-border lines cut off across the band are warned about (Knut, forum
149832, 2026-10-25).

* "The strip letters are printed over the ruler helper markers ... 3.1 mm of
  them is on the markers" was said of letters standing BETWEEN the dashes: the
  check took "Distance from page edge" + "Marker length" + 1.0 mm as a band
  across the whole page. Now each letter's ink is tested against each dash and
  the 1.0 mm of clear paper below it, and the letters are tested against "T",
  which nothing checked.
* "With 4 lines, the 4th is cut in half at an 11 mm clip border", in silence.
"""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest                                                  # noqa: E402

from workflow import measurement_messages as M                 # noqa: E402
from workflow import text_edge_fit                             # noqa: E402
from workflow.layout_engine import geometry, instruments, raster  # noqa: E402
from workflow.layout_engine.presets import LayoutRecipe        # noqa: E402

from tests.test_row_labels_use_the_free_part_of_the_clip_border import KNUT  # noqa: E402,E501

PT = 25.4 / 72.0
T2 = KNUT["clip_text"]
T4 = (T2 + "\n{instrument} - {patchcount} - {page} - {date}"
           "\n{instrument} - {patchcount} - {page} - {date}")


def _geom(**kw):
    r = LayoutRecipe.from_dict(dict(KNUT, clip_border_free_space=False, **kw))
    k = dict(r.build_kwargs(), area_target_count=600)
    return instruments.geom_from_build_kwargs(k), k, r


def _his(**kw):
    """His IMG_2807: 4 pt, turned 90 degrees, Right, X -2.5, Y -3.5, two
    markers per patch."""
    base = dict(indicator_size_mm=4 * PT, indicator_rotation=90,
                indicator_align="right", strip_label_offset_x_mm=-2.5,
                strip_label_offset_mm=-3.5, helper_marker_per_patch=2)
    base.update(kw)
    return _geom(**base)


def _ink_top(g):
    return geometry.strip_label_leader_top_mm(g) + g.label_ink_top_mm


def test_his_letters_beside_the_dashes_are_not_on_the_markers():
    g, kw, r = _his()
    # the old band check said they were
    old = text_edge_fit.strip_label_marker_overlap(
        geometry.strip_label_leader_top_mm(g), g.label_ink_top_mm, True,
        2.0, 2.0, True)
    assert old is not None and old.overlap_mm > 3.0
    assert raster.strip_letters_against_markers(g, kw) is None


def test_his_letters_are_closer_to_the_edge_than_t_and_that_is_said():
    g, kw, r = _his()
    te = text_edge_fit.strip_letters_above_text_edge(
        _ink_top(g), r.effective_text_edge_top_mm)
    assert te is not None
    assert te.text_edge_mm == pytest.approx(4.0)
    assert 1.5 < te.ink_top_mm < 2.0
    assert te.over_mm == pytest.approx(4.0 - te.ink_top_mm)
    from ui.tabs.tab_chart import strip_letters_past_t_notice
    text = strip_letters_past_t_notice(te)
    assert "{" not in text and "“T”" in text and "Label offset" in text


def test_a_letter_on_a_dash_is_still_on_the_markers():
    # three markers per patch put a dash in the middle of every strip, right
    # under a centred letter
    g, kw, _r = _his(helper_marker_per_patch=3, strip_label_offset_x_mm=0.0)
    hit = raster.strip_letters_against_markers(g, kw)
    assert hit is not None
    assert hit.overlap_mm > 3.0


def test_the_clear_paper_below_a_dash_still_counts():
    # Y -1.0: the letter is below the dash itself but in its 1.0 mm
    g, kw, _r = _his(helper_marker_per_patch=3, strip_label_offset_x_mm=0.0,
                     strip_label_offset_mm=-1.0)
    hit = raster.strip_letters_against_markers(g, kw)
    assert hit is not None and hit.ink_top_mm > 4.0


@pytest.mark.parametrize("rot,y", [(0, 0.0), (90, 0.0)])
def test_letters_where_the_layout_puts_them_say_nothing(rot, y):
    g, kw, r = _his(indicator_rotation=rot, strip_label_offset_mm=y,
                    strip_label_offset_x_mm=0.0, helper_marker_per_patch=3)
    assert raster.strip_letters_against_markers(g, kw) is None
    assert text_edge_fit.strip_letters_above_text_edge(
        _ink_top(g), r.effective_text_edge_top_mm) is None


# ---- B: clip-border lines cut off across the band ---------------------------

def test_his_fourth_line_at_11_mm_is_cut_and_named():
    g, kw, _r = _geom(clip_border_width_mm=11.0, clip_text=T4)
    cut = raster.clip_lines_cut_across(g, kw, raster.clip_text_lines(T4))
    assert cut is not None and cut.lines == 4
    assert [c[0] for c in cut.cuts] == [4]
    line, mm, height = cut.cuts[0]
    assert 0.8 < mm < 1.5 and mm < height          # about half of it
    assert cut.avail_mm == pytest.approx(9.0, abs=0.05)
    assert cut.want_mm >= 11.0 + mm - 0.05
    from ui.tabs.tab_chart import _clip_lines_cut_text
    text = _clip_lines_cut_text(cut, 6.0)
    assert "{" not in text and "Line 4 loses" in text, text


def test_the_wider_band_it_names_prints_every_line_whole():
    g, kw, _r = _geom(clip_border_width_mm=11.0, clip_text=T4)
    want = raster.clip_lines_cut_across(
        g, kw, raster.clip_text_lines(T4)).want_mm
    g2, kw2, _r2 = _geom(clip_border_width_mm=want, clip_text=T4)
    assert raster.clip_lines_cut_across(
        g2, kw2, raster.clip_text_lines(T4)) is None


@pytest.mark.parametrize("width,text,size", [
    (11.0, T2, 2.12), (13.0, T4, 2.12), (11.0, T4, 0.0)])
def test_lines_that_fit_or_auto_say_nothing(width, text, size):
    g, kw, _r = _geom(clip_border_width_mm=width, clip_text=text,
                      clip_text_size_mm=size)
    assert raster.clip_lines_cut_across(
        g, kw, raster.clip_text_lines(text)) is None


def test_whole_lines_lost_are_counted():
    eight = "\n".join(["{instrument} - {page}"] * 8)
    g, kw, _r = _geom(clip_border_width_mm=11.0, clip_text=eight)
    cut = raster.clip_lines_cut_across(g, kw, raster.clip_text_lines(eight))
    assert cut is not None
    from ui.tabs.tab_chart import _clip_lines_cut_text
    text = _clip_lines_cut_text(cut, 6.0)
    assert "are not printed at all" in text and "{" not in text, text


def test_the_new_messages_are_proposed_not_approved():
    for m in (M.M_CHART_STRIP_LABELS_PAST_T, M.M_CHART_CLIP_LINES_CUT,
              M.M_CHART_CLIP_LINE_PART_CUT, M.M_CHART_CLIP_LINES_NOT_PRINTED):
        assert not m.approved
