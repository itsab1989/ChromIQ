"""Knut's "Full layout setup" ruling, pinned. It had no test at all.

Knut, 4.1.3-beta.17: *"the red river chars shall not have the 'Full layout
setup' label in the preset list pulldown."* Before this file, flipping
`_Ti1Preset.has_full_layout_setup` back to `return True` left the whole suite
green — which is exactly how the Red River presets drifted in the first place
(a ruler-marks change wrote one value across all six and nothing failed).
"""
import pytest
from PyQt6.QtWidgets import QApplication

from ui.tabs import tab_chart as tc


@pytest.fixture(scope="module", autouse=True)
def _app():
    return QApplication.instance() or QApplication([])


def test_the_marker_counts_are_exactly_115_6_and_9():
    knut = list(tc.KNUT_PRESETS)
    marked = [p for p in knut if p.has_full_layout_setup]
    unmarked = [p for p in knut if not p.has_full_layout_setup]

    assert len(tc.BUILTIN_PRESET_KEYS) == 130
    assert len(tc.PREBUILT_PRESETS) == 9        # the "by Pharmacist" rows
    assert (len(marked), len(unmarked)) == (115, 6)
    assert len(marked) + len(unmarked) + len(tc.PREBUILT_PRESETS) == 130


def test_no_red_river_row_carries_the_marker():
    rr = [p for p in tc.KNUT_PRESETS if p.display_group == "Red River Paper"]
    assert len(rr) == 6, "the Red River family changed size"
    for p in rr:
        assert not p.has_full_layout_setup, p.name
        assert tc.KNUT_FLS_SUFFIX not in p.marked_name, p.marked_name
        assert tc.KNUT_FLS_SUFFIX not in p.combo_label, p.combo_label


def test_every_other_family_still_carries_it():
    """THE CONTROL. "mark nothing" must not pass the two tests above."""
    others = [p for p in tc.KNUT_PRESETS if p.display_group != "Red River Paper"]
    assert others, "no non-Red-River presets found"
    assert all(p.has_full_layout_setup for p in others)
    assert all(tc.KNUT_FLS_SUFFIX in p.marked_name for p in others)
