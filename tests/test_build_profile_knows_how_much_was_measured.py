"""#159 (report 11, S16): Build Profile armed on the existence of a `.ti3`.

In the owner's own session on 2026-08-28 it was offered on a measurement of
THREE patches out of 390. A profile built from that is not a poor profile, it is
not a profile at all — and nothing on screen said so.

A partial measurement is legitimate: "Refine / resume existing measurement"
exists precisely so you can stop and come back. So this does not forbid
building — it says how partial the measurement is and leaves the choice where it
belongs. An EMPTY file is different: there is nothing to build from at all.

Read from the FILE, not from any live counter — this runs for measurements the
app never watched being made.
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication                         # noqa: E402

from core.argyll_runner import ArgyllRunner                      # noqa: E402
from core.settings import AppSettings                            # noqa: E402
from ui.tabs.tab_profile import TabProfile                       # noqa: E402

_TI2 = """CTI2

NUMBER_OF_FIELDS 5
BEGIN_DATA_FORMAT
SAMPLE_ID SAMPLE_LOC RGB_R RGB_G RGB_B
END_DATA_FORMAT

NUMBER_OF_SETS 4
BEGIN_DATA
1 "A1" 100 100 100
2 "A2" 0 0 0
3 "A3" 50 50 50
4 "A4" 25 25 25
END_DATA
"""

_HEAD = """CTI3

DEVICE_CLASS "OUTPUT"
COLOR_REP "RGB_XYZ"

NUMBER_OF_FIELDS 8
BEGIN_DATA_FORMAT
SAMPLE_ID SAMPLE_LOC RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z
END_DATA_FORMAT
"""


def _ti3(n: int) -> str:
    rows = "".join(f'{i} "A{i}" 50 50 50 20 20 20\n' for i in range(1, n + 1))
    return _HEAD + f"\nNUMBER_OF_SETS {n}\nBEGIN_DATA\n{rows}END_DATA\n"


@pytest.fixture
def tab():
    QApplication.instance() or QApplication([])
    s = AppSettings()
    return TabProfile(ArgyllRunner(s), s)


def _load(tab, tmp_path, n):
    (tmp_path / "chart.ti2").write_text(_TI2)
    ti3 = tmp_path / "chart.ti3"
    ti3.write_text(_ti3(n))
    tab.set_ti3_path(ti3, propagate=False)
    return ti3


def test_an_empty_measurement_cannot_build_a_profile(tab, tmp_path):
    (tmp_path / "chart.ti2").write_text(_TI2)
    ti3 = tmp_path / "chart.ti3"
    ti3.write_text(_HEAD + "\nNUMBER_OF_SETS 0\nBEGIN_DATA\nEND_DATA\n")
    tab.set_ti3_path(ti3, propagate=False)
    assert not tab._build_btn.isEnabled(), (
        "Build Profile is offered for a measurement holding no readings")
    assert "nothing to build" in tab._build_btn.toolTip().lower()


def test_a_partial_measurement_says_how_partial_it_is(tab, tmp_path):
    _load(tab, tmp_path, 1)
    assert tab._build_btn.isEnabled(), (
        "a partial measurement is legitimate — resume exists for it")
    tip = tab._build_btn.toolTip()
    assert "1" in tip and "4" in tip, (
        f"the tooltip does not say how much of the chart was measured: {tip!r}")


def test_a_complete_measurement_is_not_nagged_about(tab, tmp_path):
    _load(tab, tmp_path, 4)
    assert tab._build_btn.isEnabled()
    assert tab._build_btn.toolTip() == ""
