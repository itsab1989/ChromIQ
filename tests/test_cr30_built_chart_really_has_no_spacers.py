"""Re-check of 5817c89b: the BUILT chart, not just the recipe, has no spacers.

`tests/test_cr30_manual_layout_defaults_to_no_spacers.py` proves the panel and
the recipe. The deliverable is the printed sheet, and the closest physical
probe the build result offers is `ChartResult.strip_rects` — per-strip pixel
rectangles computed from the same `Placement` the raster paints, where a
spacer adds `pspa` to every patch step. So: build the SAME six patches from
the SAME real panel twice, once on the CR30 default and once after the user
deliberately turns spacers on, and the second strip MUST be taller. If the
default's ink-free layout ever silently regressed to spacers (or the
deliberate choice stopped reaching the build), the two heights converge and
this fails.

The i1 direction is pinned the same way, because a strip reader finds each
patch edge BY the spacer: after a visit to the CR30 and back, the i1's default
build must still be the taller (spacered) one.

The panel is the real `LayoutOptionsPanel`, the instrument chosen the way a
user chooses it, the build the real `chart.build_chart` on a hand-written .ti1
(no Argyll), at 72 dpi to stay cheap.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from workflow.layout_engine import chart

TI1 = ('CTI1\nCOLOR_REP "RGB"\nNUMBER_OF_FIELDS 4\nBEGIN_DATA_FORMAT\n'
       'SAMPLE_ID RGB_R RGB_G RGB_B\nEND_DATA_FORMAT\nNUMBER_OF_SETS 6\n'
       'BEGIN_DATA\n1 100 0 0\n2 0 100 0\n3 0 0 100\n4 0 0 0\n'
       '5 100 100 100\n6 50 50 50\nEND_DATA\n')


@pytest.fixture
def panel(qtbot):
    from ui.dialogs.layout_options_panel import LayoutOptionsPanel
    p = LayoutOptionsPanel(with_selectors=True)
    qtbot.addWidget(p)
    return p


def _pick(panel, code):
    i = panel.instr.findData(code)
    assert i >= 0
    panel.instr.setCurrentIndex(i)


def _set_spacers(panel, mode):
    i = panel.spacer_mode.findData(mode)
    assert i >= 0
    panel.spacer_mode.setCurrentIndex(i)


def _build(panel, tmp_path: Path, tag: str):
    r = panel.get_recipe()
    ti1 = tmp_path / f"{tag}.ti1"
    ti1.write_text(TI1)
    res = chart.build_chart(str(ti1), str(tmp_path / f"out-{tag}"),
                            **{**r.build_kwargs(), "dpi": 72})
    assert res.tiff_paths, "the chart was not actually rendered"
    assert res.strip_rects, "the build reported no strip geometry"
    return res


def test_the_default_cr30_chart_is_built_without_spacer_ink(panel, tmp_path):
    _pick(panel, "CR30")
    h_default = _build(panel, tmp_path, "default").strip_rects[0]["h"]
    _set_spacers(panel, "colored")            # the deliberate opt-in
    h_spacered = _build(panel, tmp_path, "colored").strip_rects[0]["h"]
    # A CR30 chart is not padded, so the strip rect spans exactly the six real
    # patches: a per-patch spacer makes it strictly taller.
    assert h_default < h_spacered, (
        f"default strip height {h_default}px vs spacers-on {h_spacered}px: "
        "the built CR30 chart is not actually spacer-free (or the deliberate "
        "opt-in no longer reaches the build)")


def test_an_i1_chart_is_still_built_WITH_spacers_after_a_cr30_visit(panel, tmp_path):
    """The restore direction, in built pixels: an i1 reader finds each patch
    edge by the spacer, so after CR30 and back its default build must be the
    tall (spacered) one."""
    _pick(panel, "CR30")
    _pick(panel, "i1")
    steps_default = _build(panel, tmp_path, "i1-default").layout.steps_in_pass
    _set_spacers(panel, "none")               # the hypothetical bad state
    steps_bare = _build(panel, tmp_path, "i1-bare").layout.steps_in_pass
    # An i1 strip is padded to full length, so its rect height cannot isolate
    # the spacer -- but its CAPACITY can: each spacer makes the per-patch step
    # taller, so a spacered pass holds strictly fewer patches (45 vs 48 on A4
    # at the defaults). Equal capacities mean the spacers are gone.
    assert steps_default < steps_bare, (
        f"default pass holds {steps_default} patches vs {steps_bare} without "
        "spacers: after visiting the CR30, the i1's default chart was built "
        "without the spacers its reader needs to find patch edges")
