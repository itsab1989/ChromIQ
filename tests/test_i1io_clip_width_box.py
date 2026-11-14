"""THE CLIP BORDER'S WIDTH BOX OFFERS WHAT THE i1iO BUILDS (review 5, item 5).

The box took 10 to 19.9 mm while the i1iO is chosen and the build used its
minimum, 20 mm (`table_facts.CLIP_MIN_MM`): recorded and printed differed.
While the i1iO is chosen the box starts at that minimum; leaving gives the
other instrument its own minimum back."""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(autouse=True)
def i1io_on():
    from workflow.i1io import support
    before = support._latched
    support.set_enabled_for_this_process(True)
    try:
        yield
    finally:
        support._latched = before


def test_the_box_starts_at_what_the_build_uses(qapp, qtbot):
    from ui.dialogs.layout_options_panel import LayoutOptionsPanel
    from workflow.i1io import chart as C
    from workflow.i1io.table_facts import CLIP_MIN_MM
    p = LayoutOptionsPanel(with_selectors=True)
    qtbot.addWidget(p)
    other_min = p.clip_width.minimum()
    p.instr.setCurrentIndex(p.instr.findData("IO2"))
    assert p.clip_width.minimum() == CLIP_MIN_MM.value
    p.clip_width.setValue(12.0)
    assert p.clip_width.value() == CLIP_MIN_MM.value
    r = p.get_recipe()
    built = C.clip_width_of({C.CLIP_KEY: True,
                             "clip_border_width": r.clip_border_width_mm})
    assert r.clip_border_width_mm == built
    p.instr.setCurrentIndex(p.instr.findData("i1"))
    assert p.clip_width.minimum() == other_min
