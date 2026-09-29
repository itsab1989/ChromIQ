"""The hundredfold CIE scale reaches the user through a SECOND door.

2026-09-11's measurement-import round put the repair inside
``finalize_converted_ti3``, which is genuinely the one place every CONVERT path
calls, so every import is covered. The measurement that was converted YESTERDAY
is not: it is a finished ``.ti3`` sitting in the run folder, and the Build
Profile tab loads it, arms its button and says nothing.

Reproduced on screen with the reporting user's own 4,000-patch export, converted
the way her copy of ChromIQ converted it (``txt2ti3`` alone, no finalise step)
and opened in her project:

* the file's lightest patch reads ``XYZ 0.87254 0.88577 0.86923`` = **L\\* 8.0**;
* the tab's label named the file and nothing else, and the Build button was
  enabled with an empty tooltip;
* the Measurement Report generated and FILED a report recording
  ``paper_white.lab [8.0, 0.74, -2.46]``, hex ``#17171b``.

The fix says so. It does not repair the file (a write the user did not ask for)
and does not refuse the build (a decision that is not ours to take): it puts the
fact on the label beside the file name, where this tab already says how partial
a measurement is, and spells it out in the Build button's tooltip.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from workflow.reference_convert import cie_columns_are_unscaled     # noqa: E402


def _ti3(scale: float, *, cie: bool = True, n: int = 4,
         paper: bool = True) -> str:
    """A converted ``.ti3``. *scale* 1.0 is ArgyllCMS's 0..100, 0.01 is
    i1Profiler's 0..1 reflectance factor.

    THE FIRST ROW IS BARE PAPER, because a printed chart's first row is. Device
    RGB 100/100/100 is "no ink", and that patch is what tells the reading below
    which scale the file is on — see ``_xyz_scale_verdict``. Pass *paper* False
    for a set that holds no paper patch at all (a rich-black / Dmax comparison
    set), which cannot be judged and must not be.
    """
    cols = "SAMPLE_ID SAMPLE_LOC RGB_R RGB_G RGB_B" + (" XYZ_X XYZ_Y XYZ_Z" if cie else "")
    body = []
    for i in range(n):
        y = 88.0 - i * 20.0
        d = 100.0 if (paper and i == 0) else 92.0 * (max(y, 0.0) / 88.0) ** 0.45
        row = f'{i + 1} "A{i + 1}" {d:.4f} {d:.4f} {d:.4f}'
        if cie:
            row += "".join(f" {y * k * scale:.6f}" for k in (0.95, 1.0, 0.82))
        body.append(row)
    return ('CTI3   \n\nDESCRIPTOR "x"\nDEVICE_CLASS "OUTPUT"\n'
            'COLOR_REP "iRGB_XYZ"\n\n'
            f"NUMBER_OF_FIELDS {len(cols.split())}\n"
            f"BEGIN_DATA_FORMAT\n{cols}\nEND_DATA_FORMAT\n\n"
            f"NUMBER_OF_SETS {len(body)}\nBEGIN_DATA\n" + "\n".join(body)
            + "\nEND_DATA\n")


# ---------------------------------------------------------------------------
# 1 · the reading itself
# ---------------------------------------------------------------------------

def test_a_file_on_the_0_to_1_scale_is_recognised(tmp_path):
    p = tmp_path / "m.ti3"
    p.write_text(_ti3(0.01), encoding="utf-8")
    assert cie_columns_are_unscaled(p) is True


def test_an_ordinary_measurement_is_left_alone(tmp_path):
    p = tmp_path / "m.ti3"
    p.write_text(_ti3(1.0), encoding="utf-8")
    assert cie_columns_are_unscaled(p) is False


def test_the_reading_never_writes(tmp_path):
    """It is a reading. A file it looked at is byte for byte the file it was."""
    p = tmp_path / "m.ti3"
    p.write_text(_ti3(0.01), encoding="utf-8")
    before = p.read_bytes()
    assert cie_columns_are_unscaled(p) is True
    assert p.read_bytes() == before


def test_a_file_with_no_cie_columns_cannot_carry_this_fault(tmp_path):
    p = tmp_path / "m.ti3"
    p.write_text(_ti3(1.0, cie=False), encoding="utf-8")
    assert cie_columns_are_unscaled(p) is False


def test_nothing_readable_is_never_an_accusation(tmp_path):
    assert cie_columns_are_unscaled(None) is False
    assert cie_columns_are_unscaled(tmp_path / "nope.ti3") is False
    p = tmp_path / "junk.ti3"
    p.write_text("not a CGATS file at all\n", encoding="utf-8")
    assert cie_columns_are_unscaled(p) is False
    empty = tmp_path / "empty.ti3"
    empty.write_text(
        'CTI3   \n\nNUMBER_OF_FIELDS 8\nBEGIN_DATA_FORMAT\n'
        "SAMPLE_ID SAMPLE_LOC RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z\n"
        "END_DATA_FORMAT\n\nNUMBER_OF_SETS 0\nBEGIN_DATA\nEND_DATA\n",
        encoding="utf-8")
    assert cie_columns_are_unscaled(empty) is False


def test_a_ragged_row_stops_it_rather_than_being_indexed_into(tmp_path):
    p = tmp_path / "m.ti3"
    lines = _ti3(0.01).splitlines()
    cut = next(i for i, ln in enumerate(lines) if ln.startswith('4 "A4"'))
    lines[cut] = '4 "A4" 28.0000'                  # two tokens, not eight
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    assert cie_columns_are_unscaled(p) is False


# ---------------------------------------------------------------------------
# 2 · and the tab says so
# ---------------------------------------------------------------------------

@pytest.fixture
def profile_tab(qtbot):
    from core.argyll_runner import ArgyllRunner
    from core.settings import AppSettings
    from ui.tabs.tab_profile import TabProfile
    s = AppSettings()
    tab = TabProfile(ArgyllRunner(s), s)
    qtbot.addWidget(tab)
    return tab


def test_the_tab_names_the_wrong_scale_on_the_label(profile_tab, tmp_path):
    p = tmp_path / "chart.ti3"
    p.write_text(_ti3(0.01), encoding="utf-8")

    profile_tab.set_ti3_path(p, propagate=False)

    assert "wrong scale" in profile_tab._file_lbl.text(), \
        profile_tab._file_lbl.text()
    tip = profile_tab._build_btn.toolTip()
    assert "0 to 1" in tip and "0 to 100" in tip, tip


def test_an_ordinary_measurement_gets_no_such_line(profile_tab, tmp_path):
    p = tmp_path / "chart.ti3"
    p.write_text(_ti3(1.0), encoding="utf-8")

    profile_tab.set_ti3_path(p, propagate=False)

    assert "wrong scale" not in profile_tab._file_lbl.text()
    assert "0 to 1" not in profile_tab._build_btn.toolTip()
