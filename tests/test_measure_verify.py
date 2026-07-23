"""Measure-tab verification option: a verify run must save a separate, tagged
'-verify.ti3' and never advance to Build Profile."""
from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtWidgets import QApplication, QDialog  # noqa: E402


@pytest.fixture(scope="module", autouse=True)
def _qapp():
    yield QApplication.instance() or QApplication([])


class _Settings:
    def __init__(self):
        self._d = {"appearance": "dark"}

    def get(self, key, default=None):
        return self._d.get(key, default)

    def set(self, key, value):
        self._d[key] = value


def _write_chart_ti3(p: Path) -> None:
    p.write_text(
        'CTI3\n\nDEVICE_CLASS "OUTPUT"\nCOLOR_REP "iRGB_XYZ"\nNUMBER_OF_FIELDS 7\n'
        "BEGIN_DATA_FORMAT\nSAMPLE_ID RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z\n"
        "END_DATA_FORMAT\n\nNUMBER_OF_SETS 1\nBEGIN_DATA\n1 100 100 100 86 90 75 \n"
        "END_DATA\n")


def _make_tab():
    from core.argyll_runner import ArgyllRunner
    from ui.tabs.tab_measure import TabMeasure
    s = _Settings()
    return TabMeasure(ArgyllRunner(s), s)


def test_verify_run_saves_tagged_verify_file(tmp_path, monkeypatch):
    # Don't let the completion dialog block or open the inspector.
    monkeypatch.setattr(QDialog, "exec", lambda self: 0)
    from workflow.ti3_analysis import is_verification_ti3, parse_ti3

    tab = _make_tab()
    chart = tmp_path / "chart.ti2"
    chart.touch()
    _write_chart_ti3(tmp_path / "chart.ti3")

    tab._ti1_path = chart
    tab._verify_run = True
    tab._ti3_mtime_before = None      # fresh file
    tab._all_done_shown = True
    tab._measure_failed = False

    emitted: list = []
    tab.measure_finished.connect(emitted.append)

    tab._on_measure_done(0)

    # #130: a verification is filed in a dated verifications/<date>/ folder
    # (history), not overwritten flat next to the chart.
    verifs = list(tmp_path.glob("verifications/*/*-verify.ti3"))
    assert len(verifs) == 1                        # one dated verification run
    out = verifs[0]
    assert not (tmp_path / "chart.ti3").exists()   # original renamed away
    assert not (tmp_path / "chart-verify.ti3").exists()  # not left flat at root
    assert is_verification_ti3(parse_ti3(out))     # tagged
    assert emitted == []                           # never advanced to Build Profile
    assert tab._verify_run is False                # consumed


def test_normal_run_unaffected(tmp_path, monkeypatch):
    """A non-verify read still emits measure_finished on the plain .ti3."""
    monkeypatch.setattr(QDialog, "exec", lambda self: 0)
    tab = _make_tab()
    chart = tmp_path / "chart.ti2"
    chart.touch()
    _write_chart_ti3(tmp_path / "chart.ti3")
    tab._ti1_path = chart
    tab._verify_run = False
    tab._ti3_mtime_before = None
    tab._all_done_shown = True
    tab._measure_failed = False

    emitted: list = []
    tab.measure_finished.connect(emitted.append)
    tab._on_measure_done(0)

    assert (tmp_path / "chart.ti3").exists()       # untouched
    assert not (tmp_path / "chart-verify.ti3").exists()
    assert emitted and emitted[0].name == "chart.ti3"
