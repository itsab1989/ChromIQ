"""CHOOSING THE i1iO BRINGS THE i1iO'S OWN VALUES (review 3, item 4).

The owner, 2026-11-13: "our defaults should be safe". Job D opened options
on the i1iO that can make a chart risky (offsets, ruler helper markers,
edge spacers, a strip cap, text distance B, the strip-indicator gap, the
letters' offsets). A person who set them on an i1Pro chart and then chose
the i1iO carried them all over (368 patches instead of 528). Now:

* choosing the i1iO shows its own values: those it had when it was last
  left in this session, else the safe factory ones;
* leaving it gives the previous instrument back exactly what it had, so an
  i1iO-only value never follows a person to another instrument's chart (as
  in 4.3.33, where these controls were greyed on the i1iO);
* a recipe being loaded brings its own values either way.
"""
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


@pytest.fixture
def panel(qapp, qtbot):
    from ui.dialogs.layout_options_panel import LayoutOptionsPanel
    p = LayoutOptionsPanel(with_selectors=True)
    qtbot.addWidget(p)
    return p


def _to(panel, code):
    i = panel.instr.findData(code)
    panel.instr.setCurrentIndex(i)
    panel.instr.activated.emit(i)


RISKY = dict(offx=3.0, offy=10.0, max_strip=180.0, text_edge=9.0, sig=4.0,
             strip_label_offset=-6.0, strip_label_offset_x=2.0)
RISKY_ON = ("helper_markers_cb", "edge_spacers_cb")


def _set_risky(panel):
    for name, v in RISKY.items():
        getattr(panel, name).setValue(v)
    for name in RISKY_ON:
        getattr(panel, name).setChecked(True)


def _values(panel):
    return ({n: getattr(panel, n).value() for n in RISKY},
            {n: getattr(panel, n).isChecked() for n in RISKY_ON})


def test_an_i1pros_risky_values_do_not_follow_it_to_the_i1io(panel):
    from workflow.layout_engine.presets import default_recipe
    _to(panel, "i1")
    _set_risky(panel)
    _to(panel, "IO2")
    r = panel.get_recipe()
    f = default_recipe("IO2", "A4")
    assert (r.offset_x_mm, r.offset_y_mm, r.max_strip_mm, r.text_edge_mm,
            r.strip_indicator_gap_mm, r.strip_label_offset_mm,
            r.strip_label_offset_x_mm, r.helper_markers, r.edge_spacers) == (
        f.offset_x_mm, f.offset_y_mm, f.max_strip_mm, f.text_edge_mm,
        f.strip_indicator_gap_mm, f.strip_label_offset_mm,
        f.strip_label_offset_x_mm, False, False)
    assert (r.i1io_numbers_edge_mm, r.i1io_text_align) == (None, "")


def test_leaving_gives_the_i1pro_back_what_it_had(panel):
    _to(panel, "i1")
    _set_risky(panel)
    before = _values(panel)
    _to(panel, "IO2")
    # the person changes the i1iO's own
    panel.offx.setValue(1.0)
    panel.helper_markers_cb.setChecked(True)
    _to(panel, "i1")
    assert _values(panel) == before


def test_the_i1io_gets_back_what_a_person_set_on_it(panel):
    _to(panel, "IO2")
    panel.offx.setValue(1.5)
    panel.text_edge.setValue(6.0)
    _to(panel, "i1")
    _to(panel, "IO2")
    r = panel.get_recipe()
    assert (r.offset_x_mm, r.text_edge_mm) == (1.5, 6.0)


def test_a_loaded_recipe_brings_its_own(panel):
    from dataclasses import replace
    from workflow.layout_engine.presets import default_recipe
    _to(panel, "i1")
    _set_risky(panel)
    rec = replace(default_recipe("IO2", "A4"), offset_x_mm=2.0,
                  helper_markers=True)
    panel.set_recipe(rec)
    r = panel.get_recipe()
    assert (r.offset_x_mm, r.helper_markers) == (2.0, True)
    assert r.offset_y_mm == 0.0


def test_a_loaded_i1pro_recipes_markers_stay_the_i1pros(panel):
    """Review 4, item 4: open an i1iO project, then an i1Pro project whose
    recipe has the ruler helper markers on, then choose the i1iO by hand:
    the markers were written before the instrument switched and kept as the
    i1iO's own. Each instrument's own values stay its own."""
    from dataclasses import replace
    from workflow.layout_engine.presets import default_recipe
    _to(panel, "IO2")
    pro = replace(default_recipe("i1", "A4"), helper_markers=True,
                  helper_marker_edge_mm=3.0, helper_marker_len_mm=4.0,
                  helper_marker_per_patch=2)
    panel.set_recipe(pro)
    assert panel.get_recipe().helper_markers is True        # the i1Pro's
    _to(panel, "IO2")
    r = panel.get_recipe()
    assert r.helper_markers is False
    _to(panel, "i1")
    r = panel.get_recipe()
    assert (r.helper_markers, r.helper_marker_edge_mm,
            r.helper_marker_len_mm, r.helper_marker_per_patch) == (
        True, 3.0, 4.0, 2)
