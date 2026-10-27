""""Edge spacers (bracket each strip)" is greyed exactly while ticking it cannot
change the printed sheet (4.3.18 review r2, SF-A and NIT6).

4.3.18 r1 greyed the box by the spacer-SIZE rule (the instrument's base spacer
width above 0 and Spacers not None). That was wrong both ways:

* a SpectroScan's base spacer width is 0, so the box was greyed on it in every
  mode, while with an inter-patch gap its sheet differs ticked and clear
  (the reviewer: SS, Coloured, 1 mm gap);
* it was asked again only when Spacers changed, so after SpectroScan -> CR30
  it stayed greyed on an instrument where it works.

And "grey it while Spacers is None" is not the rule either: with None and an
inter-patch gap a SpectroScan or CR30 sheet still differs, because the gap is
kept at both ends of every strip (no ink, but the patches move). The rule is
the build's own answer, `presets.edge_spacers_effect`, and it is checked here
against the rendered TIFFs: "changes" exactly when ticked and clear are two
different sheets. On the strip readers (i1Pro, i1Pro 3 Plus, ColorMunki) the
build turns edge spacers on whatever the box says, so it is greyed there with
a tooltip that says so (NIT6); the recipe still saves the tick as it is.
"""
from __future__ import annotations

import hashlib
import os
import random
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from workflow.layout_engine.presets import (                       # noqa: E402
    EDGE_SPACERS_ALWAYS_ON, LayoutRecipe, edge_spacers_effect)


def _ti1(path: Path, n: int) -> Path:
    rnd = random.Random(1)
    lines = ["CTI1", "", 'DESCRIPTOR "t"', 'COLOR_REP "RGB"', "",
             "NUMBER_OF_FIELDS 7", "BEGIN_DATA_FORMAT",
             "SAMPLE_ID RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z", "END_DATA_FORMAT",
             "", f"NUMBER_OF_SETS {n}", "BEGIN_DATA"]
    for i in range(1, n + 1):
        r, g, b = (round(rnd.uniform(0, 100), 4) for _ in range(3))
        lines.append(f"{i} {r} {g} {b} 10 10 10")
    path.write_text("\n".join(lines + ["END_DATA", ""]), encoding="utf-8")
    return path


def _recipe(inst, mode, gap, hflag=False, edge=False) -> LayoutRecipe:
    return LayoutRecipe(instrument=inst, layout_mode="patch_first",
                        spacer_mode=mode, inter_patch_mm=gap, hflag=hflag,
                        edge_spacers=edge, seed=1)


def _sheet(folder: Path, recipe: LayoutRecipe) -> str:
    from workflow.layout_engine.chart import build_from_recipe
    folder.mkdir(parents=True, exist_ok=True)
    build_from_recipe(_ti1(folder / "c.ti1", 80), folder / "c", recipe)
    tifs = sorted(folder.glob("c*.tif"))
    assert tifs
    return hashlib.sha256(b"".join(t.read_bytes() for t in tifs)).hexdigest()


# (instrument, Spacers, inter-patch gap mm, honeycomb)
CASES = [
    # Spacers None on every instrument, no gap: never a different sheet
    ("i1", "none", 0.0, False), ("p3", "none", 0.0, False),
    ("CM", "none", 0.0, False), ("SS", "none", 0.0, False),
    ("CR30", "none", 0.0, False), ("SS", "none", 0.0, True),
    ("CR30", "none", 0.0, True),
    # the reviewer's case and its neighbours on the SpectroScan
    ("SS", "colored", 1.0, False), ("SS", "colored", 0.0, False),
    ("SS", "bw", 1.0, False), ("SS", "colored", 1.0, True),
    # None WITH a gap: no ink, but the gap is kept at the strip ends
    ("SS", "none", 1.0, False), ("CR30", "none", 1.0, False),
    ("SS", "none", 1.0, True),
    # the CR30 with spacers, flat and honeycomb
    ("CR30", "colored", 0.0, False), ("CR30", "colored", 0.0, True),
    # the strip readers bracket every strip whatever the box says
    ("i1", "colored", 1.0, False), ("p3", "bw", 0.0, False),
    ("CM", "colored", 0.0, False),
]


@pytest.mark.parametrize("inst,mode,gap,hflag", CASES,
                         ids=[f"{i}-{m}-gap{g:g}-{'hex' if h else 'flat'}"
                              for i, m, g, h in CASES])
def test_the_rule_is_the_rendered_sheet(tmp_path, inst, mode, gap, hflag):
    off = _sheet(tmp_path / "off", _recipe(inst, mode, gap, hflag, False))
    on = _sheet(tmp_path / "on", _recipe(inst, mode, gap, hflag, True))
    effect = edge_spacers_effect(_recipe(inst, mode, gap, hflag))
    assert (effect == "changes") == (on != off), (effect, on != off)
    if inst in EDGE_SPACERS_ALWAYS_ON:
        assert effect == "always_on"


def test_the_reviewers_case_changes_the_sheet():
    """SS, Spacers Coloured, 1 mm gap: the box works and must not be greyed."""
    assert edge_spacers_effect(_recipe("SS", "colored", 1.0)) == "changes"


def test_none_with_a_gap_is_not_greyed_on_ss_and_cr30():
    for inst in ("SS", "CR30"):
        assert edge_spacers_effect(_recipe(inst, "none", 1.0)) == "changes"


def test_spacers_on_sheet_follows_the_renderer_on_a_spectroscan_with_a_gap():
    """`spacers_on_sheet` (the turned export's question) says what the
    renderer draws: spacers between the patches on an SS chart with a gap,
    flat or honeycomb (its ring is the spacer), at the ends only when the
    box is ticked; none without a gap or with Spacers None."""
    from workflow.i1profiler_turned import spacers_on_sheet
    for hflag in (False, True):
        for edge in (False, True):
            d = _recipe("SS", "colored", 1.0, hflag, edge).to_dict()
            assert spacers_on_sheet(d) == (True, edge), (hflag, edge)
        assert spacers_on_sheet(
            _recipe("SS", "colored", 0.0, hflag, True).to_dict()) == (
                False, False)
        assert spacers_on_sheet(
            _recipe("SS", "none", 1.0, hflag, True).to_dict()) == (
                False, False)


# ---------------------------------------------------------------------------
# The panel
# ---------------------------------------------------------------------------

@pytest.fixture()
def panel():
    from PyQt6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    from ui.dialogs.layout_options_panel import LayoutOptionsPanel
    p = LayoutOptionsPanel(with_selectors=True)
    yield p
    p.deleteLater()


def _pick(combo, key):
    i = combo.findData(key)
    assert i >= 0, key
    combo.setCurrentIndex(i)


def _agrees(panel) -> bool:
    return panel.edge_spacers_cb.isEnabled() == (
        edge_spacers_effect(panel.get_recipe()) == "changes")


def test_ss_with_a_gap_enables_the_box_and_keeps_the_tick(panel):
    panel.set_recipe(LayoutRecipe(instrument="SS", spacer_mode="colored",
                                  edge_spacers=True))
    cb = panel.edge_spacers_cb
    assert not cb.isEnabled() and cb.isChecked()
    assert cb.toolTip()                          # it says why
    panel.inter_patch.setValue(1.0)
    assert cb.isEnabled() and cb.isChecked() and cb.toolTip() == ""
    panel.inter_patch.setValue(0.0)
    assert not cb.isEnabled() and cb.isChecked()
    _pick(panel.spacer_mode, "none")
    panel.inter_patch.setValue(1.0)
    assert cb.isEnabled(), "None with a gap still changes an SS sheet"
    assert panel.get_recipe().edge_spacers is True


def test_switching_instrument_asks_again(panel):
    """SS -> CR30 left the box greyed (review r2): every switch asks again."""
    panel.set_recipe(LayoutRecipe(instrument="SS", spacer_mode="colored",
                                  edge_spacers=True))
    cb = panel.edge_spacers_cb
    assert not cb.isEnabled()
    _pick(panel.instr, "CR30")
    assert _agrees(panel)
    _pick(panel.spacer_mode, "colored")
    assert cb.isEnabled() and cb.isChecked()
    _pick(panel.instr, "SS")
    assert _agrees(panel) and not cb.isEnabled()
    _pick(panel.instr, "CR30")
    _pick(panel.spacer_mode, "colored")
    assert cb.isEnabled()
    _pick(panel.instr, "i1")
    assert not cb.isEnabled() and cb.isChecked()
    assert "i1Pro" in cb.toolTip()
    for inst in ("SS", "CR30", "CM", "p3", "i1"):
        for gap in (0.0, 1.0):
            _pick(panel.instr, inst)
            panel.inter_patch.setValue(gap)
            assert _agrees(panel), (inst, gap)


def test_spacers_none_greys_it_on_every_instrument_without_a_gap(panel):
    for inst, _label in panel.INSTRUMENTS:
        _pick(panel.instr, inst)
        _pick(panel.spacer_mode, "none")
        panel.inter_patch.setValue(0.0)
        assert not panel.edge_spacers_cb.isEnabled(), inst
        assert panel.edge_spacers_cb.toolTip(), inst


def test_greying_changes_no_recipe(panel):
    """NIT6: on a strip reader the box is greyed, and the recipe (and so the
    chart, which the build brackets anyway) is exactly what the tick says."""
    for tick in (True, False):
        panel.set_recipe(LayoutRecipe(instrument="i1", spacer_mode="colored",
                                      edge_spacers=tick))
        assert not panel.edge_spacers_cb.isEnabled()
        assert panel.edge_spacers_cb.isChecked() is tick
        r = panel.get_recipe()
        assert r.edge_spacers is tick
        assert r.build_kwargs()["edge_spacers"] is True


def test_the_embedded_panel_asks_the_recipe_it_was_given():
    """Preferences > Chart Layout has no instrument selector: the box follows
    the recipe set on it, honeycomb included."""
    from PyQt6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    from ui.dialogs.layout_options_panel import LayoutOptionsPanel
    p = LayoutOptionsPanel()
    try:
        p.set_recipe(LayoutRecipe(instrument="CR30", spacer_mode="colored",
                                  hflag=True, edge_spacers=True))
        assert p.edge_spacers_cb.isEnabled()
        p.set_recipe(LayoutRecipe(instrument="SS", spacer_mode="colored",
                                  hflag=True, edge_spacers=True))
        assert not p.edge_spacers_cb.isEnabled()
        p.inter_patch.setValue(1.0)
        assert p.edge_spacers_cb.isEnabled()
        p.set_recipe(LayoutRecipe(instrument="i1", edge_spacers=False))
        assert not p.edge_spacers_cb.isEnabled()
    finally:
        p.deleteLater()
