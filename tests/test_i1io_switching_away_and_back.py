"""i1iO -> ANOTHER INSTRUMENT -> i1iO GIVES THE i1iO BACK WHAT IT HAD
(the parity review, 2026-11-13, reproduced on screen there).

On the i1iO a person set a top margin of 16, a 9 mm patch and a sheet text,
switched to the i1Pro and back: the margin was 12 again, the patch 8 mm and
the i1Pro's sheet text had replaced the i1iO's. Every field of the i1iO's
recipe now comes back, for every other instrument; and that instrument gets
back what IT had, so neither inherits the other's values.
"""
from __future__ import annotations

import os
from dataclasses import replace

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from tests.test_i1io_every_option_persists import KEPT  # noqa: E402


@pytest.fixture(autouse=True)
def i1io_on():
    from workflow.i1io import support
    before = support._latched
    support.set_enabled_for_this_process(True)
    try:
        yield
    finally:
        support._latched = before


@pytest.fixture
def panel(qapp, qtbot):
    from ui.dialogs.layout_options_panel import LayoutOptionsPanel
    p = LayoutOptionsPanel(with_selectors=True)
    qtbot.addWidget(p)
    return p


def _to(panel, code):
    i = panel.instr.findData(code)
    assert i >= 0, code
    panel.instr.setCurrentIndex(i)


OTHERS = ("i1", "SS", "CM")


def _i1io_recipe():
    from workflow.layout_engine.presets import default_recipe
    return replace(default_recipe("IO2", "A4"), margins_explicit=True,
                   label_style_explicit=True, layout_explicit=True,
                   chart_text="i1iO text", **{
                       k: v for k, v in KEPT.items()
                       if k not in ("paper", "chart_text")})


@pytest.mark.parametrize("other", OTHERS)
def test_every_i1io_field_comes_back(panel, other):
    _to(panel, "IO2")
    want = _i1io_recipe()
    panel.set_recipe(want)
    before = panel.get_recipe()
    _to(panel, other)
    _to(panel, "IO2")
    after = panel.get_recipe()
    lost = {f: (getattr(before, f), getattr(after, f))
            for f in KEPT
            if getattr(before, f) != getattr(after, f)}
    assert lost == {}


@pytest.mark.parametrize("other", OTHERS)
def test_the_other_instrument_gets_back_what_it_had(panel, other):
    from workflow.layout_engine.presets import default_recipe
    _to(panel, other)
    mine = replace(default_recipe(other, "A4"), chart_text="its own",
                   margin_top=9.0, margins_explicit=True)
    panel.set_recipe(mine)
    before = panel.get_recipe()
    _to(panel, "IO2")
    panel.chart_text.setText("i1iO text")
    panel.margins["t"].setValue(18.0)
    _to(panel, other)
    after = panel.get_recipe()
    assert (after.chart_text, after.margin_top) == (before.chart_text,
                                                    before.margin_top)
