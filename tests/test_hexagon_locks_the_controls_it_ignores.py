"""A honeycomb has ONE free dimension, and the layout panel offered two.

Knut, 4.1.5-beta.10:

    *"When I try to make hexagonal patches on a chart for CR30, and setting in
    the layout engine Calculation method 'By columns / rows…', then changing the
    patches per strip has no function or effect. When 15 strips the patch width
    is 10.9 mm, and there is 28 rows, no matter what I set on patches per strip.
    … maybe the 'Patches per strip' should be locked and greyed with a tooltip
    saying that the size of hexagonal patches are defined by the columns / rows
    number … I assume the same thinking also applies to … 'Minimum patch height
    (% of width)' is not really used. This should be verified."*

Both halves verified, both true. `area_fit.derive_area_patch_size` forces the
height ratio to ``sqrt(3)/2`` when the hexagon flag is set on a `hex_capable`
instrument, and snaps the solved height back to ``pw * sqrt(3)/2`` afterwards,
so the honeycomb cannot come out stretched (Basti's ruling, 2026-08-28). Once
the strip count fixes the width, everything else follows.

Three things are pinned here:

1. THE INERTNESS IS REAL, measured against the engine and not against the
   panel, so the lock can never be justified by a belief.
2. THE LOCK MATCHES IT EXACTLY, in every combination of shape x method x pinned
   strips, and in particular does NOT fire where the box is still live.
3. THE REASON IS REACHABLE. A disabled QWidget receives no hover events, so a
   tooltip on the greyed spin box may never appear; the note rides on the row's
   info button, which stays enabled.

…and that the geometry did not move: the same recipe produces the same patch
size and the same grid as before the lock existed.
"""
from __future__ import annotations

import math

import pytest

from ui.dialogs.layout_options_panel import LayoutOptionsPanel
from ui.tooltip_button import TooltipButton
from workflow.layout_engine import area_fit, geometry, instruments, papers
from workflow.layout_engine.presets import LayoutRecipe


# ----------------------------------------------------------------------
# the engine side: what is actually inert
# ----------------------------------------------------------------------

def _chart(**over) -> tuple:
    """(patch_w, patch_h, strips, rows, patches) for an area-first recipe."""
    paper = over.pop("paper", "A4")
    instrument = over.pop("instrument", "CR30")
    r = LayoutRecipe(instrument=instrument, paper=paper,
                     layout_mode="area_first", **over)
    kw = r.build_kwargs()
    size = area_fit.derive_area_patch_size(kw)
    assert size is not None
    pw, ph = size
    g = instruments.geom_from_build_kwargs({**kw, "patch_w": pw, "patch_h": ph})
    w_mm, h_mm = papers.dimensions_mm(paper)
    lay = geometry.compute(g, w_mm, h_mm, 100_000)
    cols = lay.patches_per_page // lay.steps_in_pass if lay.steps_in_pass else 0
    return (round(pw, 2), round(ph, 2), cols, lay.steps_in_pass,
            lay.patches_per_page)


@pytest.mark.parametrize("instrument", ["CR30", "SS"])
def test_patches_per_strip_is_inert_on_a_honeycomb_with_pinned_strips(instrument):
    """Knut's report, on the engine. 15 strips, six row counts, one chart."""
    charts = {
        _chart(instrument=instrument, hflag=True, area_method="by_grid",
               area_cols=15, area_rows=rows)
        for rows in (0, 5, 10, 20, 28, 40)
    }
    assert len(charts) == 1, charts
    pw, ph, cols, rows, _n = charts.pop()
    assert cols == 15
    # …and the height IS the honeycomb proportion, which is why.
    assert ph == pytest.approx(math.floor(pw * math.sqrt(3) / 2 * 100) / 100,
                               abs=0.02)


@pytest.mark.parametrize("instrument", ["CR30", "SS"])
def test_patches_per_strip_is_still_live_when_the_strips_are_on_auto(instrument):
    """The lock must NOT be "hexagons", it must be "hexagons AND pinned strips"."""
    charts = {
        _chart(instrument=instrument, hflag=True, area_method="by_grid",
               area_cols=0, area_rows=rows)
        for rows in (10, 20, 30, 40)
    }
    assert len(charts) == 4, charts


@pytest.mark.parametrize("instrument", ["CR30", "SS"])
def test_minimum_patch_height_is_inert_on_a_honeycomb(instrument):
    """Knut's second assumption: the height % does nothing for hexagons."""
    hexed = {
        _chart(instrument=instrument, hflag=True, area_method="by_width",
               area_min_patch_mm=8.0, area_ratio=ratio)
        for ratio in (0.5, 1.0, 1.5, 2.0, 3.0)
    }
    assert len(hexed) == 1, hexed
    # …and it is emphatically NOT inert for rectangular patches, so the lock is
    # about the shape and not about the method.
    flat = {
        _chart(instrument=instrument, hflag=False, area_method="by_width",
               area_min_patch_mm=8.0, area_ratio=ratio)
        for ratio in (0.5, 1.0, 1.5, 2.0, 3.0)
    }
    assert len(flat) == 5, flat


def test_minimum_patch_width_stays_live_on_a_honeycomb():
    """The one area-first size input a honeycomb still obeys must not be locked."""
    charts = {
        _chart(hflag=True, area_method="by_width", area_min_patch_mm=mw)
        for mw in (4.0, 8.0, 12.0, 20.0)
    }
    assert len(charts) == 4, charts


# ----------------------------------------------------------------------
# the panel side: the lock matches, exactly
# ----------------------------------------------------------------------

@pytest.fixture
def panel(qapp):
    p = LayoutOptionsPanel(with_selectors=True)
    yield p
    p.deleteLater()


def _row_state(panel, which):
    row = getattr(panel, f"_area_row_{which}")
    tips = [w for w in row if isinstance(w, TooltipButton)]
    others = [w for w in row if not isinstance(w, TooltipButton)]
    assert tips and others, row
    return (all(w.isEnabled() for w in others), tips[0])


def _select(panel, instrument, mode, method, cols):
    panel.instr.setCurrentIndex(panel.instr.findData(instrument))
    panel.mode.setCurrentIndex(panel.mode.findData(mode))
    panel.area_method.setCurrentIndex(panel.area_method.findData(method))
    panel.area_cols.setValue(cols)


# (instrument, shape, method, strips) -> (ratio row live?, rows row live?)
EXPECTED = {
    ("CR30", "flat", "by_width", 0): (True, True),
    ("CR30", "flat", "by_width", 15): (True, True),
    ("CR30", "flat", "by_grid", 0): (True, True),
    ("CR30", "flat", "by_grid", 15): (True, True),
    ("CR30", "hex", "by_width", 0): (False, True),
    ("CR30", "hex", "by_width", 15): (False, True),
    ("CR30", "hex", "by_grid", 0): (True, True),
    ("CR30", "hex", "by_grid", 15): (True, False),
    ("SS", "hex", "by_width", 0): (False, True),
    ("SS", "hex", "by_grid", 15): (True, False),
    ("SS", "flat", "by_grid", 15): (True, True),
    # An i1 has no hexagons at all, so nothing may ever lock there.
    ("i1", "clip", "by_width", 0): (True, True),
    ("i1", "clip", "by_grid", 15): (True, True),
    ("i1", "noclip", "by_grid", 15): (True, True),
}


@pytest.mark.parametrize("key,want", sorted(EXPECTED.items()))
def test_the_lock_fires_exactly_where_the_control_is_inert(panel, key, want):
    _select(panel, *key)
    ratio_live, _ = _row_state(panel, "ratio")
    rows_live, _ = _row_state(panel, "rows")
    assert (ratio_live, rows_live) == want, key


@pytest.mark.parametrize("key", [k for k, v in EXPECTED.items() if not all(v)])
def test_a_locked_row_always_says_why_on_a_button_that_still_works(panel, key):
    """The reason must be reachable, and a disabled widget cannot deliver it.

    The note goes on the row's info button, which `TooltipButton.changeEvent`
    keeps enabled inside a disabled parent, and whose hover tooltip carries the
    note's first line, so the icon says there is something to read before it is
    clicked (Knut: greyed, but never unexplained).
    """
    _select(panel, *key)
    for which in ("ratio", "rows"):
        live, tip = _row_state(panel, which)
        if live:
            assert tip.live_note() == "", (key, which)
            continue
        assert tip.isEnabled(), (key, which)
        note = tip.live_note()
        assert note, (key, which)
        assert "Hexagon" in note
        assert note.splitlines()[0] in tip.toolTip()
        assert note in tip.dialog_body()
        # …and the standing help is still there underneath it.
        assert len(tip.dialog_body()) > len(note)
        assert "—" not in note, "no em dash in new user-facing text"


def test_clearing_the_lock_restores_the_row_and_drops_the_note(panel):
    """Switching back to Rectangular must un-grey and un-annotate both rows."""
    _select(panel, "CR30", "hex", "by_grid", 15)
    assert not _row_state(panel, "rows")[0]
    _select(panel, "CR30", "flat", "by_grid", 15)
    live, tip = _row_state(panel, "rows")
    assert live
    assert tip.live_note() == ""


def test_a_panel_with_no_selectors_locks_from_the_recipe(qapp):
    """Preferences > Chart Layout and the relayout dialog have no shape combo,
    so they read the shape off the recipe they were handed."""
    p = LayoutOptionsPanel(with_selectors=False)
    try:
        p.set_recipe(LayoutRecipe(instrument="CR30", paper="A4", hflag=True,
                                   layout_mode="area_first",
                                   area_method="by_grid", area_cols=15,
                                   area_rows=20))
        assert not _row_state(p, "rows")[0]
        p.set_recipe(LayoutRecipe(instrument="CR30", paper="A4", hflag=False,
                                   layout_mode="area_first",
                                   area_method="by_grid", area_cols=15,
                                   area_rows=20))
        assert _row_state(p, "rows")[0]
    finally:
        p.deleteLater()


# ----------------------------------------------------------------------
# the mutation lands
# ----------------------------------------------------------------------

def test_the_guard_would_catch_a_lock_that_stopped_firing(panel, monkeypatch):
    """PROVE THE MUTATION LANDS. Neuter `_area_is_hexagonal` (the one input the
    lock turns on) and the expectation table above must go red, or the table is
    asserting nothing."""
    monkeypatch.setattr(LayoutOptionsPanel, "_area_is_hexagonal",
                        lambda self: False)
    _select(panel, "CR30", "hex", "by_grid", 15)
    assert _row_state(panel, "rows")[0], (
        "the mutation did not land: the row is still locked with the hexagon "
        "test forced False")
    # …and with the mutation in place the real expectation fails, which is what
    # makes the table above a guard rather than a description.
    assert (True, True) != EXPECTED[("CR30", "hex", "by_grid", 15)]


def test_the_guard_would_catch_a_lock_that_fired_on_everything(panel, monkeypatch):
    """The opposite mutation: claim every chart is a honeycomb, and the
    rectangular rows must stop being live."""
    monkeypatch.setattr(LayoutOptionsPanel, "_area_is_hexagonal",
                        lambda self: True)
    _select(panel, "CR30", "flat", "by_grid", 15)
    assert not _row_state(panel, "rows")[0], (
        "the mutation did not land: the row stayed live with the hexagon test "
        "forced True")


# ----------------------------------------------------------------------
# the geometry did not move
# ----------------------------------------------------------------------

# Recorded from `origin/master` @ 848e6965 (v4.1.5-beta.10), BEFORE the lock
# existed. A greyed control is a UI change and must be nothing else: every one
# of these is a chart somebody may already have printed.
FROZEN = {
    ("CR30", True, "by_grid", 15, 20, 1.0, 0.0, "A4"): (10.85, 9.39, 15, 26, 390),
    ("CR30", True, "by_grid", 15, 20, 1.0, 0.0, "A3"): (16.42, 14.22, 15, 26, 390),
    ("CR30", True, "by_grid", 0, 20, 1.0, 0.0, "A4"): (15.95, 13.82, 10, 18, 180),
    ("CR30", True, "by_width", 0, 0, 1.5, 8.0, "A4"): (8.29, 7.18, 20, 33, 660),
    ("CR30", False, "by_grid", 15, 20, 1.0, 0.0, "A4"): (11.19, 13.01, 15, 20, 300),
    ("CR30", False, "by_width", 0, 0, 1.5, 8.0, "A4"): (8.1, 12.33, 21, 21, 441),
    ("SS", True, "by_grid", 15, 20, 1.0, 0.0, "A4"): (10.96, 9.49, 15, 29, 435),
    ("SS", True, "by_width", 0, 0, 2.0, 8.0, "A4"): (8.29, 7.18, 20, 39, 780),
    ("SS", False, "by_grid", 15, 20, 1.0, 0.0, "A4"): (11.33, 14.25, 15, 20, 300),
    ("i1", False, "by_grid", 15, 20, 1.0, 0.0, "A4"): (11.86, 13.2, 15, 20, 300),
    ("i1", False, "by_width", 0, 0, 1.5, 8.0, "A4"): (8.09, 12.52, 22, 21, 462),
}


@pytest.mark.parametrize("key,want", sorted(FROZEN.items(),
                                            key=lambda kv: str(kv[0])))
def test_the_chart_that_came_out_before_still_comes_out(key, want):
    inst, hexed, method, cols, rows, ratio, min_w, paper = key
    got = _chart(instrument=inst, paper=paper, hflag=hexed,
                 area_method=method, area_cols=cols, area_rows=rows,
                 area_ratio=ratio, area_min_patch_mm=min_w)
    assert got == want, key
