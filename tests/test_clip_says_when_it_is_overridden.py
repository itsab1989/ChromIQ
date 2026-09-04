"""“Clip” says so when the number in the box is not the number the page uses.

`Text distance from edge → Clip` is a request, not a result. Three things
overrule it, all measured on Knut's own
`i1Pro-A4-162p-1page-Portrait-w7.5mm` (a 26 mm clip border):

* the row indicator band's floor is `max(Clip, the clip border's width, the
  furniture on that edge)` (`raster.apply_row_label_geometry`), so a box
  reading 4.0 mm printed the labels at 26.0;
* the clip border's own text is inset by `min(Clip, a fifth of the band)`
  (`geometry.clip_area_mm`), so it stops at 5.2 mm however high "Clip" goes;
* a typed 0 mm is read as 4 mm (`LayoutRecipe.build_kwargs`).

Basti ruled against changing the default (2026-09-02): *"That gap between what
the field says and what the page does is the actual problem, and it's the same
fault we just fixed for the silently raised margin — the app doing something
sensible and not mentioning it."* So the panel says so, and says nothing when
the typed value is in force.

Everything here drives the REAL `LayoutOptionsPanel` and the REAL geometry;
nothing is stubbed, and no expected number is written down twice — the ones the
message must carry are read back out of the same geometry the renderer builds.
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication                  # noqa: E402

from ui.dialogs.layout_options_panel import LayoutOptionsPanel   # noqa: E402
from workflow.layout_engine import geometry, instruments  # noqa: E402
from workflow.layout_engine.presets import LayoutRecipe   # noqa: E402


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def _select(p, inst: str, paper: str, mode: str) -> None:
    for combo, want in ((p.instr, inst), (p.paper, paper), (p.mode, mode)):
        for i in range(combo.count()):
            if combo.itemData(i) == want:
                combo.setCurrentIndex(i)
                break
        else:                                    # pragma: no cover - setup only
            raise AssertionError(f"no {want!r} in {combo}")


def _content(p, mode: str) -> None:
    for i in range(p.clip_content_mode.count()):
        if p.clip_content_mode.itemData(i) == mode:
            p.clip_content_mode.setCurrentIndex(i)
            return
    raise AssertionError(mode)                   # pragma: no cover - setup only


def _panel(app, *, clip: float, border: float = 26.0, rows: bool = True,
           content: str = "notes", side: str = "left", mode: str = "clip",
           instrument: str = "i1"):
    """Knut's chart, built through the real panel and its real widgets."""
    p = LayoutOptionsPanel(None, with_selectors=True)
    _select(p, instrument, "A4", mode)
    if mode == "clip":
        p.clip_width.setValue(border)
    _content(p, content)
    for i in range(p.clip_side.count()):
        if p.clip_side.itemData(i) == side:
            p.clip_side.setCurrentIndex(i)
            break
    # A CLICK, not setChecked: `apply_to_recipe` writes None (= "follow the
    # instrument's default", which is OFF for an i1Pro) until a PERSON has
    # touched the box, and with None the band is never built at all — the
    # premise of every test below would quietly evaporate.
    if bool(p.show_row_indicators.isChecked()) != rows:
        p.show_row_indicators.click()
    assert p.show_row_indicators.isChecked() is rows
    p.text_edge_clip.setValue(clip)
    return p


def _note(p) -> str:
    """What the panel is disclosing about "Clip" right now.

    It was a label under the three spin boxes until 2026-09-04; it is now the
    live note on that row's own ⓘ (Basti: *"not directly inside a section"*).
    The WORDS did not change, so neither did anything below this line.
    """
    return p._text_edge_tip.live_note()


def _geom(p):
    gh = p._clip_geom_and_height()
    return None if gh is None else gh[0]


# ------------------------------------------------------- it is said --------
def test_the_row_labels_being_held_at_the_border_is_reported(app):
    """The headline: the box says 4 mm, the labels start at 26."""
    p = _panel(app, clip=4.0)
    g = _geom(p)
    assert g is not None and g.rlwi > 0, "the premise failed: no row-label band"
    assert g.row_label_floor > 4.05, (
        f"the premise failed: the floor is {g.row_label_floor:.2f} mm, so the "
        f"typed 4.0 mm IS in force and there is nothing to report")
    txt = _note(p)
    assert p._text_edge_tip.live_note(), "the ⓘ is carrying nothing"
    assert "row indicator" in txt, txt
    # BOTH numbers, and the setting that did it, read back out of the geometry
    # rather than typed in here a second time.
    assert f"{g.row_label_floor:.1f} mm" in txt, txt
    assert "4.0 mm" in txt, txt
    assert "clip border" in txt, txt


def test_the_number_it_gives_follows_the_border_width(app):
    """Change the thing that overrides "Clip" and the message changes with it.

    A message carrying a hard-coded 26 would pass the test above and be wrong
    on every other chart.
    """
    for width in (10.0, 20.0, 26.0):
        p = _panel(app, clip=4.0, border=width)
        g = _geom(p)
        assert abs(g.row_label_floor - width) < 0.05, (
            f"the premise failed: a {width} mm border floored the labels at "
            f"{g.row_label_floor:.2f} mm")
        assert f"{width:.1f} mm" in _note(p), (width, _note(p))


def test_the_clip_border_text_being_capped_is_reported(app):
    """The second override, and it runs the other way: a CAP, not a floor."""
    p = _panel(app, clip=10.0)
    g = _geom(p)
    zone = g.lbord + g.border
    x, _y, w, _h = geometry.clip_area_mm(g, 297.0, 210.0)
    run_up = zone - w
    assert run_up + 0.05 < 10.0, (
        f"the premise failed: the clip text starts at {run_up:.2f} mm, which "
        f"IS the 10 mm asked for")
    txt = _note(p)
    assert "clip border" in txt and f"{run_up:.1f} mm" in txt, txt
    assert "10.0 mm" in txt, txt


def test_an_empty_box_says_what_it_is_really_read_as(app):
    """And the number comes from the substitution, not from a 4.0 written here.

    `LayoutRecipe.build_kwargs()` turns a typed 0 into its own fallback; the
    note must quote whatever that is, so this asks the recipe rather than
    asserting the constant.
    """
    p = _panel(app, clip=0.0)
    fallback = float(LayoutRecipe(text_edge_clip_mm=0.0)
                     .build_kwargs()["text_edge_clip"])
    assert fallback > 0.0, (
        "the premise failed: a typed 0 is no longer substituted")
    assert "0.0 mm is not used" in _note(p), _note(p)
    assert f"{fallback:.1f} mm" in _note(p), (fallback, _note(p))


# ---------------------------------------------------- it is NOT said -------
def test_nothing_is_said_when_the_typed_value_is_in_force(app):
    """The whole point. A line that shows on every chart is a line nobody reads."""
    p = _panel(app, clip=27.0, content="off")
    g = _geom(p)
    assert abs(g.row_label_floor - 27.0) < 0.05, "the premise failed"
    assert _note(p) == "", _note(p)
    assert not p._text_edge_tip.live_note()


def test_nothing_is_said_when_clip_exactly_matches_the_border(app):
    """The boundary, and the one case where only the "is it in force?" test can
    keep the message quiet.

    At 27 mm against a 26 mm border the clause is also blocked by the border no
    longer being the larger term; at exactly 26 it is not, so this is what pins
    the rule that the message appears ONLY when the typed value is overruled.
    """
    p = _panel(app, clip=26.0, content="off")
    g = _geom(p)
    assert abs(g.row_label_floor - 26.0) < 0.05 and abs(g.lbord + g.border - 26.0) < 0.05, (
        "the premise failed: this is not the boundary case")
    assert _note(p) == "", _note(p)


def test_raising_clip_past_the_border_puts_the_row_line_away(app):
    """Knut's own move: raise "Clip" above the border and the labels follow it
    again, so the line about them goes."""
    p = _panel(app, clip=4.0)
    assert "row indicator" in _note(p)
    p.text_edge_clip.setValue(30.0)
    assert "row indicator" not in _note(p), _note(p)


def test_nothing_is_said_about_row_labels_when_there_are_none(app):
    p = _panel(app, clip=4.0, rows=False, content="off")
    assert _note(p) == "", _note(p)


def test_nothing_is_said_about_clip_text_when_none_is_printed(app):
    """An i1Pro clip border with the content Off reserves the band and writes
    nothing in it, so there is no text for the cap to move."""
    p = _panel(app, clip=20.0, content="off")
    assert "clip border's text" not in _note(p), _note(p)


def test_a_border_on_the_far_side_leaves_the_row_labels_alone(app):
    """The labels are always on the left; a right-hand clip band never floors
    them, so nothing about them may be claimed."""
    p = _panel(app, clip=4.0, side="right")
    g = _geom(p)
    assert abs(g.row_label_floor - 4.0) < 0.05, (
        f"the premise failed: floor {g.row_label_floor:.2f} mm on a right band")
    assert "row indicator" not in _note(p), _note(p)


# ------------------------------------------------------------- counts ------
def test_the_count_is_singular_and_plural_and_never_bracket_s(app):
    one = _note(_panel(app, clip=4.0))
    two = _note(_panel(app, clip=10.0))
    assert "one thing" in one and "not placed at that distance" in one, one
    assert "2 things" in two, two
    for txt in (one, two):
        assert "(s)" not in txt, txt
        assert "—" not in txt and "--" not in txt, ("no em dashes", txt)


# ------------------------------------------------------------ premises -----
def test_the_clip_border_is_always_what_floors_the_labels(app):
    """The message names the clip border by name, and only fires when the
    border really is the larger term.

    `apply_row_label_geometry`'s floor also counts `lbord`, the furniture on
    that edge — but `lbord` IS that border less the patch border, so it can
    never be the bigger of the two. If that ever stops being true the message
    would name the wrong setting, so it is pinned here rather than assumed.
    """
    for width in (10.0, 26.0, 40.0):
        for inst in ("i1", "p3", "CM", "SS"):
            r = LayoutRecipe()
            r.instrument, r.paper, r.layout_mode = inst, "A4", "area_first"
            r.show_row_indicators = True
            r.clip_border, r.clip_border_width_mm = True, width
            r.clip_side, r.clip_content_mode = "left", "notes"
            g = instruments.geom_from_build_kwargs(r.build_kwargs())
            assert g.lbord <= width + 0.05, (
                f"{inst} at {width} mm: lbord {g.lbord} exceeds the border, so "
                f"the message would name the wrong setting")


def test_showing_the_note_changes_nothing_about_the_chart(app):
    """This is a message, not a geometry change.

    The panel hands out the same recipe, and the engine the same geometry,
    before and after the note has been computed and shown.
    """
    p = _panel(app, clip=4.0)
    before = p.get_recipe().build_kwargs()
    g_before = instruments.geom_from_build_kwargs(dict(before))
    assert _note(p) != "", "the premise failed: no note was computed"
    for _ in range(3):
        p._update_text_edge_clip_note()
    after = p.get_recipe().build_kwargs()
    g_after = instruments.geom_from_build_kwargs(dict(after))
    assert before == after, "the recipe moved"
    assert g_before == g_after, "the geometry moved"
