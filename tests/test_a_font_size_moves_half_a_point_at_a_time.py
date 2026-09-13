"""Sizes step by half a point, and every warning prints the half.

Knut, 2026-09-13, after beta 11::

    All the places where font size is defined, the side pt number should have
    one decimal and jump half a point at a time when scrolling on the input box
    (increments of 0,5 pt). The 1 pt resolution is too course, so a 5,5 pt, of
    7,5 pt might some times be needed. As an example, this also means that the
    shrinking mechanism that shrinks text size should be able to find a better
    fit when a text length is too long for 10 pt and far within the boundaries
    for 9 pt, and a 9,5 pt fits better across the whole length within
    boundaries set.
    All warning text that refers to text size should also show the correct
    decimal used.
    This could apply to the Size parameter for Clip-border content, Sheet text,
    Strip & row labels and Preferences -> Chart Layout.

Three separate things, and the middle one had exactly one culprit. Measured at
300 dpi before any change, the four size-choosing paths could land on:

* the bottom sheet text: 12, 11.76, 11.52, 11.28 ... (one PIXEL at a time,
  0.24 pt) -- already finer than a half point;
* the clip text: computed straight to the fit, continuous;
* **the right-edge notes: 12, 10.8, 9.6, 8.64, 7.68, 6.96** -- a ten per cent
  geometric step, which walks over 9.5 and lands BELOW its own 7 pt floor;
* the Size boxes: whole points only.

So the notes shrink is the one his example describes, and the two already
finer than 0.5 pt are deliberately left alone: forcing a half-point grid on
them would make the fit WORSE, which is the opposite of what he asked for.
"""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest                                              # noqa: E402

from workflow import text_edge_fit as tef                  # noqa: E402


# ------------------------------------------------------------- the grid
def test_the_step_is_half_a_point():
    assert tef.AUTO_SHRINK_STEP_PT == 0.5


@pytest.mark.parametrize("start,want", [
    (12.0, 11.5), (11.5, 11.0), (10.0, 9.5), (9.5, 9.0), (7.5, 7.0),
    (10.3, 10.0),          # off the grid: snap down to it first
    (10.25, 10.0),
    (0.5, 0.0), (0.25, 0.0), (0.0, 0.0),
])
def test_the_next_size_down_lands_on_the_grid(start, want):
    assert tef.next_size_down_pt(start) == pytest.approx(want)


def test_it_is_always_strictly_smaller():
    """A shrink loop whose step can return its own input does not terminate."""
    v = 72.0
    for _ in range(200):
        nxt = tef.next_size_down_pt(v)
        assert nxt < v or v == 0.0, (v, nxt)
        v = nxt
        if v == 0.0:
            break
    assert v == 0.0, "the grid never reached zero, so it can stall"


# ------------------------------------------------------- the coarse shrink
@pytest.mark.parametrize("dpi", [200.0, 300.0, 600.0])
def test_the_notes_shrink_walks_half_points(dpi):
    """MUTATION: put `int(font_px * 0.9)` back and this goes red.

    Checked at three rasters, because the first fix stepped in PIXELS and the
    pixel rounding swallowed the grid: at 300 dpi it produced 12, 11.52, 11.28,
    11.04 instead of 12, 11.5, 11.0. The loop counts in points now.
    """
    from workflow.tiff_metadata import _one_step_smaller_pt
    pt, floor, seq = 12.0, 7.0, []
    while pt > floor + 1e-9 and len(seq) < 20:
        seq.append(round(pt, 2))
        pt = _one_step_smaller_pt(pt, floor)
    seq.append(round(pt, 2))
    assert seq == [12.0, 11.5, 11.0, 10.5, 10.0, 9.5, 9.0, 8.5, 8.0, 7.5, 7.0], seq
    assert 9.5 in seq, "his own example size is still stepped over"


def test_the_shrink_never_goes_under_its_floor():
    """The old step landed at 6.96 pt on a 7 pt floor."""
    from workflow.tiff_metadata import _one_step_smaller_pt
    assert _one_step_smaller_pt(7.25, 7.0) == pytest.approx(7.0)
    assert _one_step_smaller_pt(7.0, 7.0) == pytest.approx(7.0)


def test_the_finer_shrinks_are_left_alone():
    """The bottom sheet text steps one PIXEL, which is 0.24 pt at 300 dpi and
    finer than the grid. Coarsening it to half points would be a regression,
    so the renderer must still step by a pixel."""
    import inspect
    from workflow.layout_engine import raster
    src = inspect.getsource(raster.render_pages)
    assert "_sfont_px -= 1" in src, (
        "the bottom-text shrink no longer steps a pixel at a time; it was "
        "already finer than half a point and coarsening it loses fit")


# ------------------------------------------------------------ the printing
@pytest.mark.parametrize("value,want", [
    (13, "13"), (13.0, "13"), (12.0, "12"), (9.5, "9.5"), (7, "7"),
    (7.5, "7.5"), (8.5, "8.5"), (0.5, "0.5"),
])
def test_a_size_prints_its_decimal_only_when_it_has_one(value, want):
    assert tef.format_pt(value) == want


def test_the_old_spec_rounded_a_half_away():
    """Why this exists at all: `{size:.0f}` ROUNDS, and Python rounds half to
    even, so 9.5 printed as 10 and 8.5 as 8. Neither was on the sheet."""
    assert f"{9.5:.0f}" == "10" and f"{8.5:.0f}" == "8"
    assert tef.format_pt(9.5) == "9.5" and tef.format_pt(8.5) == "8.5"


def test_no_message_rounds_a_size_any_more():
    """MUTATION: put one `{size:.0f}` back and this goes red.

    Read off `tr()` literals rather than the file's text, so a comment about a
    format spec is not mistaken for one.
    """
    import ast
    import pathlib
    bad = []
    for name in ("ui/tabs/tab_chart.py", "ui/dialogs/scanin_dialog.py"):
        tree = ast.parse(pathlib.Path(name).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                    and node.func.id == "tr"):
                continue
            for arg in node.args[:1]:
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                    if "{size:.0f}" in arg.value or "{floor:.0f}" in arg.value:
                        bad.append(f"{name}: {arg.value[:70]}")
    assert not bad, (
        "a message still rounds a point size away from the half it is set to:"
        "\n  " + "\n  ".join(bad))


def test_no_catalogue_still_carries_the_old_spec():
    """The twelve catalogues were migrated with the keys; a stale one would
    simply never be found again."""
    import json
    import pathlib
    bad = []
    for p in sorted(pathlib.Path("data/i18n").glob("*.json")):
        if "parameters" in p.name:
            continue
        raw = p.read_text(encoding="utf-8")
        if "{size:.0f}" in raw or "{floor:.0f}" in raw:
            bad.append(p.name)
    assert not bad, f"catalogues still carrying a rounding spec: {bad}"
