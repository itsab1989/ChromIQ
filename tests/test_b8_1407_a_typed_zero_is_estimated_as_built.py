"""B8-1407: with "Auto patch count" off and -f typed as 0, the estimate says
what Generate builds.

targen then makes the fixed patches alone (white, black, the grey and
single-channel steps), which is also exactly what a calibration chart is
(`TabChart._CAL_VALUES`: -f 0, -s 20). `_estimate_patch_total` fell through to
the chart on screen, so the B8-1363 round read an estimate of 525 / 48 / 345
beside builds of 16 / 16 / 14. It now asks targen, with the arguments Generate
gives it, how many fixed patches it makes.

Mutations (each run red): M1407-a the fixed-patch branch removed; M1407-b the
count taken from -e + -B + -g added up instead of asked of targen; M1407-c the
branch taken with Auto on as well; M1407-d the cache keyed on nothing (a
changed -g answered with the old count).
"""
from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest                                                  # noqa: E402

TARGEN = Path("/Applications/Argyll/bin/targen")
pytestmark = pytest.mark.skipif(not TARGEN.exists(), reason="needs ArgyllCMS")


@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


@pytest.fixture
def tab(qapp, tmp_path):
    from PyQt6.QtCore import QSettings
    from core.argyll_runner import ArgyllRunner
    from core.file_manager import FileManager
    from core.settings import AppSettings
    from ui.tabs.tab_chart import TabChart
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    s.set("custom_output_path", str(tmp_path / "projects"))
    s.set("argyll_bin_path", str(TARGEN.parent))
    t = TabChart(ArgyllRunner(s), FileManager(s), s)
    t._switch_mode("manual")
    yield t
    t.hide()
    t.deleteLater()


def _fixed_state(tab, e, b, g, s=0):
    tab._manual_auto_patches_check.setChecked(False)
    for chk in (tab._manual_auto_white_check, tab._manual_auto_black_check,
                tab._manual_auto_grey_check):
        if chk is not None:
            chk.setChecked(False)
    tab._set_manual_value("targen", "-f", 0)
    tab._set_manual_value("targen", "-e", e)
    tab._set_manual_value("targen", "-B", b)
    tab._set_manual_value("targen", "-g", g)
    tab._set_manual_value("targen", "-s", s)


def _targen_says(tmp_path, *args) -> int:
    subprocess.run([str(TARGEN), *args, "x"], cwd=tmp_path, check=True,
                   capture_output=True, timeout=30)
    text = (tmp_path / "x.ti1").read_text(encoding="latin-1")
    return int(re.search(r"^NUMBER_OF_SETS\s+(\d+)", text, re.M).group(1))


def test_a_typed_zero_is_the_fixed_patches_targen_makes(tab, tmp_path):
    _fixed_state(tab, 4, 4, 9)
    want = _targen_says(tmp_path, "-d2", "-f0", "-e4", "-B4", "-g9")
    assert want == 15          # the grey ramp's ends are the white and black
    assert tab._estimate_patch_total() == want


def test_a_calibration_like_chart_is_estimated_as_built(tab, tmp_path):
    _fixed_state(tab, 0, 0, 0, s=20)
    want = _targen_says(tmp_path, "-d2", "-f0", "-e0", "-B0", "-s20")
    assert tab._estimate_patch_total() == want


def test_the_answer_follows_the_settings(tab):
    _fixed_state(tab, 4, 4, 9)
    first = tab._estimate_patch_total()
    tab._set_manual_value("targen", "-g", 33)
    assert tab._estimate_patch_total() != first


def test_auto_on_or_a_typed_count_is_not_this_path(tab):
    _fixed_state(tab, 4, 4, 9)
    tab._set_manual_value("targen", "-f", 400)
    assert tab._fixed_patches_only_count() is None
    assert tab._estimate_patch_total() == 400
    tab._manual_auto_patches_check.setChecked(True)
    assert tab._fixed_patches_only_count() is None
