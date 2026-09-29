"""Knut's beta 9 batch: five things wrong in one warning.

He set a ColorMunki preset going with "Stamp settings down the right edge" on,
chart notes typed, a bottom sheet text of nine placeholders at a typed 13 pt, a
four-line clip-border text at 11 pt, a **24 mm clip border** and a **31.5 mm
right margin**. The panel said:

    The chart notes down the right edge are too long for the sheet. The last 5
    characters are cut off and replaced by "...", because the text has stopped
    shrinking at 13 pt.

and every clause of it was wrong::

    1. The chart notes text does not go all the way out to the to top or bottom
       limits.
    2. There is no "..." placed at the end and 5 characters are not cut off.
    3. It is the bottom text that moves into the text area of the right margin,
       not the chart notes being too long here.
    4. When right margin is larger than clip-border width: the largest value of
       them should define the side-positions that are used for centring the
       bottom text, not only clip-border width.
    5. Shrinking stops at 7 pt, but only in size=auto. When size is manually set
       to 13, it is not a shrinking. Text is wrong.

Measured before anything was touched, by rendering his sheet and stamping it
with the real stamper: the notes' ink ran from **24.51 mm to 276.61 mm** on a
297.05 mm page, so 24.5 mm of clear paper at the top and 20.4 at the bottom
(his 1), and all **127 characters** were drawn with no ellipsis at any strip
width the stamper could have used (his 2).

The cause of 1 and 2 is one line: `_generate_from_ti1` sets
`params.chart_layout_name`, and the panel's `_collect_manual()` does not. With
a patch set armed, targen is never run and `stamp_lines` prints
"Chart layout <name> |" where the panel predicted "targen -d2 -f612 -e1 -B1 -G
test". Two different lines, so two different lengths, so a cut that was not
happening.

3 and 4 are one thing as well: the bottom line was centred between bounds that
knew about the clip border and not about the margin.
"""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest                                              # noqa: E402

from workflow import text_edge_fit as tef                  # noqa: E402


# ------------------------------------------------- 4: the margin is a bound
def test_the_margin_binds_the_side_the_clip_border_is_on():
    """His case: a 24 mm border and a 31.5 mm right margin on A4.

    MUTATION: drop `margin_right_mm` from the `max(...)` and this goes red.
    """
    before = tef.bottom_text_bounds_mm(210.0, 4.0, clip_border_mm=24.0,
                                       clip_side="right")
    assert before == (4.0, 186.0), before
    after = tef.bottom_text_bounds_mm(210.0, 4.0, clip_border_mm=24.0,
                                      clip_side="right",
                                      margin_left_mm=14.0,
                                      margin_right_mm=31.5)
    assert after[1] == pytest.approx(178.5), (
        f"the right bound is {after[1]}, so the line may still print inside a "
        f"31.5 mm margin")


def test_it_applies_whichever_side_the_border_is_on():
    """*"This should apply for both left or right side clip-border."*"""
    left = tef.bottom_text_bounds_mm(210.0, 4.0, clip_border_mm=24.0,
                                     clip_side="left",
                                     margin_left_mm=31.5, margin_right_mm=14.0)
    assert left[0] == pytest.approx(31.5), left


def test_a_narrower_margin_changes_nothing():
    """The rule is `max`, so a margin inside the border is not a new bound."""
    assert tef.bottom_text_bounds_mm(
        210.0, 4.0, clip_border_mm=24.0, clip_side="right",
        margin_right_mm=10.0) == (4.0, 186.0)


def test_his_own_worked_example_still_gives_202_mm():
    """**THE CONSERVATIVE READING, AND WHY.** Applied to BOTH sides the margin
    would contradict his earlier, already-confirmed A4 example, *"210 - Clip x2
    = 202mm"*, which has margins and ignores them. Driven that way, six tests
    pinning 202 went red. The margin joins the border's side only.

    Pinned on the BOUNDS, which is where that rule lives and which his
    2026-09-14 left-alignment ruling explicitly leaves alone: *"Leave limit
    detection as is for the left side."* The two bounds are still 4.0 and
    206.0, which is his 202 mm, and no margin moved either of them.
    """
    left, right = tef.bottom_text_bounds_mm(
        210.0, 4.0, margin_left_mm=12.0, margin_right_mm=12.0)
    assert (left, right) == (4.0, 206.0)
    assert right - left == pytest.approx(202.0)


def test_a_left_aligned_line_cannot_use_the_paper_behind_it():
    """His 202 mm of BOUNDS is not 202 mm of ROOM once the line starts at the
    left margin.

    Knut, 2026-09-14: *"left-aligned against the patch area left margin … This
    means a long text only gets warning when hitting towards the right side
    limits."* The line begins at 12.0 and the right limit is still 206.0, so
    what it may occupy is 194.0. Leaving the old 202 here would have let a
    typed size run 8 mm off the right-hand side of the paper with nothing said,
    which is the fault he reported against beta 8 in the first place.

    MUTATION: return `right - left` from `bottom_text_room_mm` and this goes
    red while the test above stays green, which is the pair being kept apart.
    """
    assert tef.bottom_text_anchor_mm(
        210.0, 4.0, margin_left_mm=12.0, margin_right_mm=12.0
    ) == pytest.approx(12.0)
    assert tef.bottom_text_room_mm(
        210.0, 4.0, margin_left_mm=12.0, margin_right_mm=12.0
    ) == pytest.approx(194.0)
    # and a margin INSIDE the left bound moves nothing: the bound is the floor.
    assert tef.bottom_text_anchor_mm(210.0, 4.0, margin_left_mm=1.0) == 4.0
    assert tef.bottom_text_room_mm(
        210.0, 4.0, margin_left_mm=1.0) == pytest.approx(202.0)


def test_the_room_and_the_overflow_both_take_the_margins():
    """One rule, asked through all three entry points, or the panel and the
    renderer answer differently again."""
    room = tef.bottom_text_room_mm(210.0, 4.0, clip_border_mm=24.0,
                                   clip_side="right", margin_right_mm=31.5)
    assert room == pytest.approx(174.5)
    assert tef.bottom_text_overflow(
        210.0, 4.0, 174.0, clip_border_mm=24.0, clip_side="right",
        margin_right_mm=31.5) is None
    over = tef.bottom_text_overflow(
        210.0, 4.0, 176.0, clip_border_mm=24.0, clip_side="right",
        margin_right_mm=31.5)
    assert over is not None and over.overlap_mm == pytest.approx(1.5)


def test_the_renderer_uses_the_same_bounds_and_the_same_anchor():
    """The panel warns about what the sheet does, or it is noise. Read off the
    syntax tree: `render_pages` must hand the margins to the same functions."""
    import ast
    import inspect
    import textwrap
    from workflow.layout_engine import raster

    tree = ast.parse(textwrap.dedent(inspect.getsource(raster.render_pages)))
    for name in ("bottom_text_bounds_mm", "bottom_text_anchor_mm"):
        calls = [n for n in ast.walk(tree)
                 if isinstance(n, ast.Call)
                 and isinstance(n.func, ast.Attribute)
                 and n.func.attr == name]
        assert calls, f"render_pages no longer asks for {name} at all"
        for c in calls:
            named = {kw.arg for kw in c.keywords}
            assert {"margin_left_mm", "margin_right_mm"} <= named, (
                f"the renderer asks {name} a question that does not know "
                f"about the margins, so the panel and the sheet disagree")


# --------------------------------------- 5: a typed size never shrank at all
def test_a_typed_size_is_not_described_as_a_shrink_that_stopped():
    from ui.tabs.tab_chart import _auto_floor_note, _typed_size_note
    typed = _typed_size_note(13.0, 13.0)
    assert "13" in typed and "7" in typed, typed
    assert "does not" in typed or "never" in typed, typed
    assert _auto_floor_note(13.0, 13.0) == "", (
        "the auto sentence fires on a typed size as well, so both would print")
    # …and on "auto" it is the other way round.
    assert _typed_size_note(0.0, 7.0) == ""
    assert "auto" in _auto_floor_note(0.0, 7.0)


def test_no_message_still_claims_a_typed_size_stopped_shrinking():
    """MUTATION: put the clause back into either message and this goes red.

    Read off the `tr()` LITERALS, not the file's text. The first version
    grepped the whole source and matched this module's own docstring quoting
    Knut, which is the comment-defeats-the-check fault arriving from the other
    direction: a test that reads prose cannot tell a message from a note about
    a message.
    """
    import ast
    import pathlib as _p

    src = _p.Path("ui/tabs/tab_chart.py").read_text(encoding="utf-8")
    bad = []
    for node in ast.walk(ast.parse(src)):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id == "tr"):
            continue
        for arg in node.args[:1]:
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                if "stopped shrinking at" in arg.value:
                    bad.append(arg.value[:90])
    assert not bad, (
        "a message still tells the user their typed size is where the text "
        "stopped shrinking:\n  " + "\n  ".join(bad))


def test_the_auto_case_still_says_where_shrinking_stops():
    """THE OTHER HALF. Removing the clause from the sentence must not remove
    the fact: on "auto" the reader still has to be told that 7 pt is the
    floor, and `_auto_floor_note` is what carries it."""
    from ui.tabs.tab_chart import _auto_floor_note
    said = _auto_floor_note(0.0, 7.0)
    assert "7" in said and "auto" in said, said
    assert "Sheet text" in said, said


# ------------------------------ 1 and 2: the panel measured a different line
def test_a_chart_layout_name_replaces_the_targen_line():
    """The fact the prediction was missing.

    With a patch set already armed, targen is never run, so `stamp_lines`
    names the layout instead of stamping a targen command that was not issued.
    Two different strings of two different lengths.
    """
    from workflow.chart_creator import ChartParams, ChartCreator
    import types

    def _lines(**kw):
        p = ChartParams(**{"chart_notes": "n", "stamp_commands": True, **kw})
        cc = ChartCreator.__new__(ChartCreator)
        cc._should_use_engine = lambda _p: True
        cc._build_targen_args = lambda _p, n: ["-d2", f"-f{n}", "-G", "test"]
        return ChartCreator.stamp_lines(cc, p, 612)

    with_name = _lines(chart_layout_name="test")
    without = _lines()
    assert any(l.startswith("Chart layout ") for l in with_name), with_name
    assert not any(l.startswith("Chart layout ") for l in without), without
    assert any(l.startswith("targen ") for l in without), without
    assert len("    |    ".join(with_name)) != len("    |    ".join(without)), (
        "the two lines are the same length, so this fixture cannot show the "
        "prediction measuring the wrong one")


def test_the_prediction_sets_the_layout_name_the_build_sets():
    """MUTATION: delete the `_pm.chart_layout_name = ...` line and this goes
    red. Read off the syntax tree, because the name appears in comments here.

    Driven on screen afterwards on his own preset: the panel's line and the
    line `_generate_from_ti1` would build came out identical, 187 characters
    both, where before the fix they were 143 and 187.
    """
    import ast
    import inspect
    import textwrap
    from ui.tabs.tab_chart import TabChart

    tree = ast.parse(textwrap.dedent(
        inspect.getsource(TabChart._engine_text_notes)))
    assigned = [
        n for n in ast.walk(tree)
        if isinstance(n, ast.Assign)
        and any(isinstance(t, ast.Attribute) and t.attr == "chart_layout_name"
                for t in n.targets)
    ]
    assert assigned, (
        "the prediction never sets chart_layout_name, so with a patch set "
        "armed it measures a targen line the sheet does not stamp")
    call = assigned[0].value
    # …AND IT ASKS THE PREDICATE, NOT THE LABEL. `_active_layout_name` answers
    # "what would this chart's layout be called", falling back to the stem of
    # `_current_ti1_path`, which EVERY finished build sets. Asking it directly
    # here made the panel predict "Chart layout <stem>" for an ordinary Manual
    # targen build, whose sheet stamps the targen command instead: 23
    # characters short, and the panel then went silent while the rendered
    # sheet cut 15 characters and printed "ChromI…" (adversary round 22,
    # measured and photographed on screen, 2026-09-15).
    # `_predicted_chart_layout_name` mirrors the routes `_on_generate` takes
    # and still answers with `_active_layout_name()` on every one of them that
    # goes through `_generate_from_ti1` — so Knut's ColorMunki case above is
    # unchanged.
    assert (isinstance(call, ast.Call) and isinstance(call.func, ast.Attribute)
            and call.func.attr == "_predicted_chart_layout_name"), (
        "the prediction invents a layout name instead of asking the predicate "
        "that mirrors what `_on_generate` will really hand the stamper")


# --------------------------------------------------- his rule, in his words
def _his_rule(paper_w, clip, border, side, m_left, m_right,
              markers=False, m_edge=0.0, m_len=0.0, m_sides=True):
    """Knut's answer of 2026-09-13, comment 5656432962, transcribed::

        If clip-border ON has Side= left, then the highest value of clip-border
        width and left margin is used as the left-side limit for the bottom
        text. If Clip in "Text distance from edge" or the sum of ("Distance
        from page edge" + "Marker length" + 1.0mm) (if helper markers are on
        for the sides) are larger than both clip-border width and left margin,
        then the largest value wins and is used.
        [and the same sentence again for Side= right]

    Both clauses open with "If clip-border ON", so with the border OFF he
    states no rule and his earlier confirmed example stands: 210 - Clip x2.

    WRITTEN OUT LONGHAND ON PURPOSE. Calling `bottom_text_bounds_mm` to check
    `bottom_text_bounds_mm` is the self-validating shape this project keeps
    finding; this is his prose turned into arithmetic and nothing else.
    """
    reserve = (max(clip, m_edge + m_len + 1.0) if (markers and m_sides) else clip)
    left = right_in = reserve
    if border > 0.0:
        if side == "left":
            left = max(border, m_left, reserve)
        else:
            right_in = max(border, m_right, reserve)
    return (left, paper_w - right_in)


@pytest.mark.parametrize(
    "pw,clip,border,side,mL,mR,mk,me,ml",
    [
        (210.0, 4.0, 24.0, "right", 14.0, 31.5, False, 0.0, 0.0),   # his sheet
        (210.0, 4.0, 24.0, "left", 31.5, 14.0, False, 0.0, 0.0),    # mirrored
        (210.0, 4.0, 24.0, "right", 14.0, 10.0, False, 0.0, 0.0),   # margin < border
        (210.0, 40.0, 24.0, "right", 14.0, 31.5, False, 0.0, 0.0),  # Clip wins
        (210.0, 4.0, 24.0, "right", 14.0, 31.5, True, 4.0, 2.0),    # markers on
        (210.0, 4.0, 24.0, "right", 14.0, 31.5, True, 40.0, 2.0),   # markers win
        (210.0, 4.0, 0.0, "right", 14.0, 31.5, False, 0.0, 0.0),    # no border
        (210.0, 4.0, 0.0, "left", 31.5, 14.0, True, 4.0, 2.0),      # no border
        (297.0, 6.0, 26.0, "left", 12.0, 12.0, False, 0.0, 0.0),    # A3
    ],
)
def test_the_bounds_are_what_he_wrote(pw, clip, border, side, mL, mR, mk, me, ml):
    """Confirmed by Knut, 2026-09-13. Nine crossings of his four terms."""
    want = _his_rule(pw, clip, border, side, mL, mR, mk, me, ml)
    got = tef.bottom_text_bounds_mm(pw, clip, mk, me, ml, True,
                                    clip_border_mm=border, clip_side=side,
                                    margin_left_mm=mL, margin_right_mm=mR)
    assert got[0] == pytest.approx(want[0]), (side, "left bound", got, want)
    assert got[1] == pytest.approx(want[1]), (side, "right bound", got, want)
