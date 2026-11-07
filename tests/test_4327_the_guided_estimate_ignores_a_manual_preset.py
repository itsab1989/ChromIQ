"""4.3.27: Guided's estimate described the Manual preset still selected over
there, and Generate built something else.

Measured on screen on 4.3.26 (2026-11-07, `drive_layout_speed.py`): pick the
built-in "ColorMunki · A4-1224p-4pages" preset in Manual, switch to Guided,
ColorMunki, A4, Pages 6. The big number said 1230 PATCHES · 12 PAGES before
Generate and after it, and Generate built 630 patches on 6 pages.

`_on_generate` uses a built-in preset's bundled patch set only in Manual
(`self._current_mode() == "manual"`); Guided runs targen for the pages it is
given. `_pending_patch_set_total`, which says what the next Generate will lay
out, answered the preset's 1224 in either mode. It now asks the same mode
question. A patch set LOADED by hand ("Load patch set" in the tab header) is
laid out in both modes, and stays counted in both.
"""
from __future__ import annotations

import re
import shutil
from pathlib import Path

import pytest

pytest.importorskip("PyQt6")
from PyQt6.QtCore import QSettings  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

from core.argyll_runner import ArgyllRunner  # noqa: E402
from core.file_manager import FileManager  # noqa: E402
from core.resource_path import resource_path  # noqa: E402
from core.settings import AppSettings  # noqa: E402
from ui.tabs.tab_chart import TabChart  # noqa: E402

KEY = "__chromiq_knut_cm_a4_1224p_4pages_portrait_w10_0mm_slow_reading_speed__"


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _tab(tmp_path):
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "t.ini"), QSettings.Format.IniFormat)
    s.set("custom_output_path", str(tmp_path / "out"))
    s.set("layout_info_show", True)
    tab = TabChart(ArgyllRunner(s), FileManager(s), s)
    tab._switch_mode("manual")
    # The preset armed as picking it in Manual arms it (`_on_preset_selected`
    # then `_apply_knut_preset`), without building it.
    tab._seed_knut_preset(KEY)
    tab._builtin_ti1_path = resource_path(TabChart._builtin_ti1_asset(KEY))
    tab._knut_active = True
    tab._knut_active_key = KEY
    tab._knut_targen_sig = tab._targen_signature()
    return tab


def _guided_cm_a4(tab, pages: int) -> None:
    tab._switch_mode("guided")
    tab._instr_combo.setCurrentIndex(tab._instr_combo.findData("CM"))
    tab._paper_combo.setCurrentIndex(tab._paper_combo.findData("A4"))
    tab._pages_spin.setValue(pages)
    tab._update_patch_count()


def _big_number(tab) -> "tuple[int, str]":
    n = int(re.match(r"\d+", tab._patch_count_lbl.text()).group(0))
    return n, tab._patch_detail_lbl.text()


def test_guided_counts_its_own_pages_not_the_manual_preset(qapp, tmp_path):
    tab = _tab(tmp_path)
    assert tab._pending_patch_set_total() == 1224       # Manual: the preset

    _guided_cm_a4(tab, 6)
    assert tab._knut_active                       # still armed for Manual
    assert tab._pending_patch_set_total() is None, (
        "Guided promised the Manual preset's patch set")
    n, detail = _big_number(tab)
    assert "6 PAGES" in detail, detail
    assert n != 1224 and n != 1230, (n, detail)
    # what Guided's Generate fills: its own capacity on six sheets, and the
    # layout information panel's estimate column says the same
    est = tab._layout_info_panel.predicted() or {}
    if est:
        assert est.get("pages") == 6 and est.get("total") == n, est
    assert tab._predicted_patch_count == n               # Suggest name

    tab._switch_mode("manual")
    assert tab._pending_patch_set_total() == 1224       # unchanged in Manual


def test_a_patch_set_loaded_in_guided_is_still_counted(qapp, tmp_path):
    tab = _tab(tmp_path)
    ti1 = tmp_path / "mine.ti1"
    shutil.copy(Path(__file__).resolve().parent / "fixtures" / "charts"
                / "cm_a4_480p_2pages.ti1", ti1)
    _guided_cm_a4(tab, 6)
    assert tab._pending_patch_set_total() is None
    tab._preset_ti1_path = ti1
    tab._preset_ti1_targen_sig = tab._targen_signature()
    assert tab._pending_patch_set_total() == 480
    tab._update_patch_count()
    n, detail = _big_number(tab)
    assert n >= 480 and "6 PAGES" not in detail, (n, detail)
