"""4.3.44 re-review: nothing typed in braces can stop a chart, and `{logo}` is
either drawn or left out cleanly, never printed as the word.

Chart Notes "made {date.year}" raised an AttributeError out of
`raster.resolve_placeholders` (it was `str.format`), and Generate failed. Now
only a plain known `{name}` is filled in; anything else in braces is printed
exactly as typed, through the Sheet text and the Chart Notes alike, and the
known names in the same line are still filled in.
"""
from __future__ import annotations

import pytest

from workflow.layout_engine import raster
from workflow.layout_engine.chart import text_placeholder_context

#: Texts that are not a known placeholder, each printed exactly as typed.
AS_TYPED = [
    "made {date.year}",
    "{project.upper}",
    "{0}",
    "{page!r}",
    "{page:>10}",
    "{}",
    "{abc}",
    "{{page}}",
    "{ page }",
    "{Page}",
    "{date[0]}",
    "{seed!s:>4}",
    "a { b",
    "c } d",
    "{project",
    "100% {} done {",
]


def _ctx():
    c = text_placeholder_context(project="CP1500", instrument="i1",
                                 seed=7, chart_date="2026-11-17")
    c["page"] = "page 1/2"
    return c


@pytest.mark.parametrize("text", AS_TYPED)
def test_the_sheet_text_prints_an_unknown_brace_group_as_typed(text):
    assert raster.resolve_placeholders(text, _ctx()) == text
    assert raster.resolve_keeping_logo(text, _ctx()) == text


@pytest.mark.parametrize("text", AS_TYPED)
def test_the_chart_notes_print_an_unknown_brace_group_as_typed(text):
    from tests.test_4344_placeholders_in_chart_notes_and_logo import (
        _creator, _params)
    cc = _creator()
    p = _params(text)
    cc._notes_build = {"seed": 7, "randomize": True, "date": "2026-11-17",
                       "pages": 2, "patches": 192}
    assert cc.stamp_lines(p, 192, ctx=cc.notes_context(p, 1, 2, 192)) == \
        [text.strip()]


def test_the_notes_with_date_year_make_their_chart(monkeypatch, tmp_path):
    """The reviewer's case on screen: Generate failed. Through the real
    stamping call, the line is printed as typed."""
    from tests.test_4344_placeholders_in_chart_notes_and_logo import (
        _handed_over)
    calls = _handed_over(monkeypatch, tmp_path, "made {date.year} {page}",
                         pages=1)
    assert calls == [(["CP1500-192hd_01.tif"], ["made {date.year} page 1/1"])]


@pytest.mark.parametrize("text,expected", [
    ("{page} {abc}", "page 1/2 {abc}"),
    ("{project} - {date} - {seed}", "CP1500 - 2026-11-17 - seed 7"),
    ("{page}-{date}-{seed}  123456789abcdefgh",
     "page 1/2-2026-11-17-seed 7  123456789abcdefgh"),
    ("made {date.year} on {date}", "made {date.year} on 2026-11-17"),
])
def test_the_known_names_are_still_filled_in(text, expected):
    assert raster.resolve_placeholders(text, _ctx()) == expected


# ---- {logo}: drawn, or left out cleanly ---------------------------------------

@pytest.mark.parametrize("text,expected", [
    ("{project} {logo}", "CP1500"),
    ("{logo} {project}", "CP1500"),
    ("{project} - {logo} - {page}", "CP1500 - page 1/2"),
    ("({logo})", ""),
    ("x ({logo}) y", "x y"),
])
def test_where_the_logo_is_not_drawn_it_is_left_out_cleanly(text, expected):
    assert raster.resolve_placeholders(text, _ctx()) == expected


def test_the_clip_borders_text_leaves_the_logo_out():
    lines = raster.clip_text_lines("{logo} My chart\nline two {logo}")
    assert lines == ["My chart", "line two"]
    assert raster.clip_text_lines("no logo here") == ["no logo here"]


def test_an_i1io_table_charts_sheet_text_leaves_the_logo_out():
    from workflow.i1io.chart import page_line_parts
    head, extra = page_line_parts("Chart", 0, 2, "{project} - {logo}",
                                  {"project": "CP1500"})
    assert extra == "CP1500" and "logo" not in head + extra
    head, extra = page_line_parts("Chart", 0, 1, "{logo}", {})
    assert extra == ""


def test_an_i1isis_charts_notes_leave_the_logo_out():
    """The i1iSis trailer takes the notes without a context: printed as
    typed, except `{logo}`, which is left out."""
    from tests.test_4344_placeholders_in_chart_notes_and_logo import (
        _creator, _params)
    cc = _creator()
    assert cc.stamp_lines(_params("{page} paper {logo}"), 10) == ["{page} paper"]


def test_the_fd9_clip_text_goes_through_the_shared_lines():
    """The FD-9's own code fills its known names and hands the text to the
    engine's `render_clip_strip`, whose `clip_text_lines` leaves `{logo}`
    out (no FD-9 file is changed)."""
    import inspect
    src = inspect.getsource(raster.render_clip_strip)
    assert src.count("clip_text_lines(text)") >= 2
    img = raster.render_clip_strip("text", width_px=200, height_px=1200,
                                   dpi=200, text="{logo}")
    import numpy as np
    assert (np.asarray(img.convert("L")) > 250).all()   # nothing printed
