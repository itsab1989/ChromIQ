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
    (tmp_path / "chart.ti2").write_text(_TI2, encoding="utf-8")
    ti3 = tmp_path / "chart.ti3"
    ti3.write_text(_ti3(n), encoding="utf-8")
    tab.set_ti3_path(ti3, propagate=False)
    return ti3


def test_an_empty_measurement_cannot_build_a_profile(tab, tmp_path):
    (tmp_path / "chart.ti2").write_text(_TI2, encoding="utf-8")
    ti3 = tmp_path / "chart.ti3"
    ti3.write_text(_HEAD + "\nNUMBER_OF_SETS 0\nBEGIN_DATA\nEND_DATA\n", encoding="utf-8")
    tab.set_ti3_path(ti3, propagate=False)
    assert not tab._build_btn.isEnabled(), (
        "Build Profile is offered for a measurement holding no readings")
    assert "nothing to build" in tab._build_btn.toolTip().lower()
    assert "no readings" in tab._file_lbl.text().lower()


def test_a_partial_measurement_says_how_partial_it_is(tab, tmp_path):
    _load(tab, tmp_path, 1)
    assert tab._build_btn.isEnabled(), (
        "a partial measurement is legitimate — resume exists for it")
    tip = tab._build_btn.toolTip()
    assert "1" in tip and "4" in tip, (
        f"the tooltip does not say how much of the chart was measured: {tip!r}")
    # And on the label, where it cannot be missed: a tooltip alone left the
    # screen saying "Ready to build?" beside an enabled button on 17 of 390.
    lbl = tab._file_lbl.text()
    assert "1" in lbl and "4" in lbl and "measured" in lbl, (
        f"the file label does not say the measurement is partial: {lbl!r}")


def test_a_complete_measurement_is_not_nagged_about(tab, tmp_path):
    _load(tab, tmp_path, 4)
    assert tab._build_btn.isEnabled()
    assert tab._build_btn.toolTip() == ""
    assert "measured" not in tab._file_lbl.text(), (
        "a complete measurement is being flagged as if it were partial")


_TI2_PADDED = """CTI2

NUMBER_OF_FIELDS 5
BEGIN_DATA_FORMAT
SAMPLE_ID SAMPLE_LOC RGB_R RGB_G RGB_B
END_DATA_FORMAT

NUMBER_OF_SETS 6
BEGIN_DATA
1 "A1" 100 100 100
2 "A2" 0 0 0
3 "A3" 50 50 50
4 "A4" 25 25 25
0 "A5" 100 100 100
0 "A6" 100 100 100
END_DATA
"""


def test_padding_patches_are_not_counted_as_missing(tab, tmp_path):
    """report 16: a COMPLETE measurement of a printtarg chart was labelled
    "924 of 940 patches measured", with advice to go back and resume.

    printtarg fills its last strip out with rows whose SAMPLE_ID is 0. They are
    never printed as readable patches and chartread never writes a reading for
    one, so counting them made every complete measurement of such a chart look
    partial. Charts from ChromIQ's own layout engine have no padding, which is
    why this only bit the established instruments.

    Real charts on the owner's machine: a 1,155-row chart with 3 padding rows
    and a 1,173-row one with 13.
    """
    (tmp_path / "chart.ti2").write_text(_TI2_PADDED, encoding="utf-8")
    ti3 = tmp_path / "chart.ti3"
    ti3.write_text(_ti3(4), encoding="utf-8")              # all four REAL patches measured
    tab.set_ti3_path(ti3, propagate=False)

    assert tab._build_btn.isEnabled()
    assert tab._build_btn.toolTip() == "", (
        f"a finished measurement was called partial: {tab._build_btn.toolTip()!r}")
    assert "measured" not in tab._file_lbl.text(), (
        f"the label calls a finished measurement partial: {tab._file_lbl.text()!r}")
