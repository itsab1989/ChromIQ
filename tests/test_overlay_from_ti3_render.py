"""#134: TabMeasure._show_overlay_from_existing_ti3 paints the split-patch
overlay from a measurement on disk (reusing _on_chart_measured), and reports
False for a foreign/geometry-less .ti3."""
from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtCore import QRect                                  # noqa: E402
from PyQt6.QtWidgets import QApplication                        # noqa: E402


@pytest.fixture(scope="module", autouse=True)
def _qapp():
    yield QApplication.instance() or QApplication([])


class _Settings:
    def __init__(self): self._d = {"appearance": "dark"}
    def get(self, k, d=None): return self._d.get(k, d)
    def set(self, k, v): self._d[k] = v


def _make_tab():
    from core.argyll_runner import ArgyllRunner
    from ui.tabs.tab_measure import TabMeasure
    s = _Settings()
    return TabMeasure(ArgyllRunner(s), s)


_TI2 = ('CTI1\n\nNUMBER_OF_FIELDS 8\nBEGIN_DATA_FORMAT\n'
        'SAMPLE_ID SAMPLE_LOC RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z\n'
        'END_DATA_FORMAT\nNUMBER_OF_SETS 2\nBEGIN_DATA\n'
        '1 "A1" 100 100 100 96.42 100.00 82.53\n'
        '2 "A2" 100 0 0 41.00 21.00 2.00\nEND_DATA\n')
_TI3 = ('CTI3\n\nNUMBER_OF_FIELDS 7\nBEGIN_DATA_FORMAT\n'
        'SAMPLE_ID RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z\n'
        'END_DATA_FORMAT\nNUMBER_OF_SETS 2\nBEGIN_DATA\n'
        '1 100 100 100 95.00 99.00 81.00\n'
        '2 100 0 0 40.00 20.50 2.20\nEND_DATA\n')


def test_show_overlay_from_ti3_paints(tmp_path):
    tab = _make_tab()
    ti2 = tmp_path / "chart.ti2"; ti2.write_text(_TI2)
    (tmp_path / "chart.ti3").write_text(_TI3)
    tab._ti1_path = ti2
    tab._tiff_pages = [tmp_path / "chart_01.tif"]
    # Geometry: both patches on page 0.
    tab._patch_boxes = [{"A1": QRect(0, 0, 10, 10), "A2": QRect(10, 0, 10, 10)}]

    ok = tab._show_overlay_from_existing_ti3()
    assert ok is True
    # The preview received per-patch info for page 0 (both patches).
    assert tab._preview._patch_info.get(0)
    assert len(tab._preview._patch_info[0]) == 2


def test_show_overlay_no_ti3_returns_false(tmp_path):
    tab = _make_tab()
    ti2 = tmp_path / "chart.ti2"; ti2.write_text(_TI2)   # no sibling .ti3
    tab._ti1_path = ti2
    tab._patch_boxes = [{"A1": QRect(0, 0, 10, 10)}]
    assert tab._show_overlay_from_existing_ti3() is False


def test_show_overlay_foreign_ti3_returns_false(tmp_path):
    tab = _make_tab()
    ti2 = tmp_path / "chart.ti2"; ti2.write_text(_TI2)
    # A .ti3 whose SAMPLE_IDs don't match the chart → no items → False.
    (tmp_path / "chart.ti3").write_text(
        _TI3.replace("\n1 ", "\n801 ").replace("\n2 ", "\n802 "))
    tab._ti1_path = ti2
    tab._tiff_pages = [tmp_path / "chart_01.tif"]
    tab._patch_boxes = [{"A1": QRect(0, 0, 10, 10), "A2": QRect(10, 0, 10, 10)}]
    assert tab._show_overlay_from_existing_ti3() is False
