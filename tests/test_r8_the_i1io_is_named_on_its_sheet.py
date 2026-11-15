"""R8 (4.3.39): the i1iO's clip-border notes printed the internal code "IO2"
for {instrument}. The shared table the build fills {instrument} from now
names it "i1iO", and the layout panel's preview uses the same table instead
of its own copy (which lacked it). The FD-9 and the i1iSis keep what they
print today: contributor code and a Beta, never changed as a side effect."""
from __future__ import annotations

from pathlib import Path

from workflow.layout_engine.chart import (friendly_instrument,
                                          text_placeholder_context)

REPO = Path(__file__).resolve().parents[1]


def test_the_i1io_is_named():
    assert friendly_instrument("IO2") == "i1iO"
    assert text_placeholder_context(instrument="IO2")["instrument"] == "i1iO"


def test_the_others_are_as_before():
    for code, name in {"i1": "i1Pro", "p3": "i1Pro3+", "CM": "ColorMunki",
                       "SS": "SpectroScan", "CR30": "CR30",
                       "FD9": "FD9", "XRISIS": "XRISIS"}.items():
        assert friendly_instrument(code) == name


def test_the_panel_preview_uses_the_same_table():
    src = (REPO / "ui/dialogs/layout_options_panel.py").read_text(encoding="utf-8")
    assert "_instr_friendly" not in src
    assert '"instrument": friendly_instrument(inst),' in src
