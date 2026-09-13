"""A gap between two bars must mean a bar, never a missing value.

Knut, 2026-09-13, after the doubled separator was removed::

    Also make sure that the empty space between two bars is not due to a
    missing parameter, or a setting that is empty etc, which would result in
    the empty space. If that would be the case, double bars would only be
    replaced by one bar IF they are empty in between.

His worry is the right one to have: collapsing "|    |" into "|" would HIDE a
field that came out empty, and the empty field is the fault. So the question
was asked of the code rather than answered by tidying the symptom.

**IT WAS NOT A MISSING VALUE.** Every place that joins fields with `_JOIN`
filters the pieces first (`if s and s.strip()`), in all four columns of the
left clip strip and in the right-margin stamp, so an absent or blank field
removes itself and takes its separator with it. The doubled bar came from a
hard-coded trailing "|" in one line, and nothing else.

One real gap turned up while checking, and it is the shape he described from
the other side: a layout name that was PRESENT but blank stamped the bare
label "Chart layout" with nothing after it. A field with no value is not a
field, so that case now names the chart the way it does when there is no name
at all.
"""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest                                              # noqa: E402

from workflow import tiff_metadata as tm                   # noqa: E402
from workflow.chart_creator import ChartCreator, ChartParams  # noqa: E402


def _lines(**kw):
    p = ChartParams(**kw)
    cc = ChartCreator.__new__(ChartCreator)
    cc._should_use_engine = lambda _p: True
    cc._build_targen_args = lambda _p, n: ["-d2", "-f10", "-G", "t"]
    cc._build_printtarg_args = lambda _p: ["-i1", "-p", "A4"]
    return ChartCreator.stamp_lines(cc, p, 10)


def _stamped(**kw) -> str:
    """What the sheet finally carries: the stamper's own filter, then _JOIN."""
    return tm._JOIN.join(s.strip() for s in _lines(**kw) if s and s.strip())


#: Every way a field can go missing, one per case.
_CASES = {
    "everything": dict(chart_notes="note", stamp_commands=True,
                       chart_layout_name="TC9.18"),
    "no notes": dict(chart_notes="", stamp_commands=True,
                     chart_layout_name="TC9.18"),
    "notes are only spaces": dict(chart_notes="   ", stamp_commands=True,
                                  chart_layout_name="TC9.18"),
    "no layout name": dict(chart_notes="note", stamp_commands=True),
    "layout name is only spaces": dict(chart_notes="note", stamp_commands=True,
                                       chart_layout_name="   "),
    "nothing stamped but notes": dict(chart_notes="note", stamp_commands=False),
}


@pytest.mark.parametrize("label", sorted(_CASES))
def test_no_missing_field_ever_leaves_a_doubled_bar(label):
    """MUTATION: put the trailing "|" back on the layout-name line and the
    "everything" and "layout name" cases go red."""
    line = _stamped(**_CASES[label])
    assert "|    |" not in line, f"{label}: {line}"
    assert not line.startswith("|") and not line.endswith("|"), f"{label}: {line}"
    assert "  |  " not in line.replace(tm._JOIN, "\x00"), (
        f"{label}: a separator that is not the shared one: {line}")


@pytest.mark.parametrize("label", sorted(_CASES))
def test_no_field_is_blank_before_it_is_joined(label):
    """The filter is a safety net, not the design. Nothing should be handing it
    an empty field in the first place, because a field nobody can see is a
    value that went missing quietly."""
    for piece in _lines(**_CASES[label]):
        assert piece and piece.strip(), (
            f"{label}: an empty field reaches the joiner: {piece!r}")


def test_a_blank_layout_name_is_not_a_layout_name():
    """PRESENT BUT EMPTY, which is his case read the other way round. It used
    to stamp "Chart layout" with nothing after it."""
    line = _stamped(chart_notes="n", stamp_commands=True,
                    chart_layout_name="   ")
    assert "Chart layout" not in line, line
    assert "targen " in line, "with no usable name the chart is named by targen"


def test_a_padded_layout_name_is_trimmed():
    line = _stamped(chart_notes="n", stamp_commands=True,
                    chart_layout_name="  TC9.18  ")
    assert "Chart layout TC9.18    |" in line, line


def test_every_joiner_drops_its_empty_pieces():
    """The four columns of the left clip strip and the right-margin stamp all
    filter before joining. Read off the syntax tree so a comment cannot pass
    for a filter."""
    import ast
    import inspect
    import textwrap

    for fn in (tm.stamp_chart_metadata, tm.stamp_left_clip_info):
        tree = ast.parse(textwrap.dedent(inspect.getsource(fn)))
        joins = [n for n in ast.walk(tree)
                 if isinstance(n, ast.Call)
                 and isinstance(n.func, ast.Attribute)
                 and n.func.attr == "join"]
        assert joins, f"{fn.__name__} no longer joins anything"
        for j in joins:
            src = ast.dump(j)
            assert "comprehension" in src or "pieces" in src, (
                f"{fn.__name__} joins a list nothing filtered: an empty field "
                f"would print as a doubled bar")
