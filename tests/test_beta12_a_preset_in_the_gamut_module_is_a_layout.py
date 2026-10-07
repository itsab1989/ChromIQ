"""Beta 12, Basti #182 6036695078: a built-in preset chosen in the FROM
PROFILE GAMUT module gives the chart its LAYOUT only. The colours come from
the profile's gamut, with the automatic count (what fits the layout, less the
8 cube corners), not from the preset's own (profiling) patch set.

His case: "A3Plus-616p-1page-Landscape-w10.0mm-Fast Reading Speed" in a
verification run built the preset's 616 profiling patches, and the module's
count stayed at 50 (+8). It must give 608 + 8 from the gamut. Manual (and a
profiling run) keep building the preset's own patches.
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtCore import QSettings                        # noqa: E402
from PyQt6.QtWidgets import QApplication                  # noqa: E402

from core.argyll_runner import ArgyllRunner               # noqa: E402
from core.file_manager import FileManager, Project        # noqa: E402
from core.measurement_target import RUN_TYPE_VERIFICATION  # noqa: E402
from core.settings import AppSettings                     # noqa: E402
from ui.measurement_target_bar import MeasurementTargetController  # noqa: E402

KEY = ("__chromiq_knut_cm_a3plus_616p_1page_landscape_w10_0mm_"
       "fast_reading_speed__")


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _tab(tmp_path, monkeypatch, *, verification=True):
    from ui.tabs import tab_chart as TC
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    s.set("custom_output_path", str(tmp_path))
    fm = FileManager(s)
    Project.create(tmp_path / "P", "P").current_run().ensure_dir()
    fm.set_target_name("P")
    ctl = MeasurementTargetController(fm)
    fm.project().run("run1").profile_icc.write_bytes(b"icc")
    tab = TC.TabChart(ArgyllRunner(s), fm, s, None)
    tab.set_target_controller(ctl)
    monkeypatch.setattr(tab, "_gamut_coverage", lambda *a, **k: 5000)
    tab._gamut_master_total = 5960
    calls = {"gamut": [], "ti1": []}
    monkeypatch.setattr(
        tab, "_on_generate_gamut",
        lambda: calls["gamut"].append(tab._gamut_effective_count()))
    monkeypatch.setattr(
        tab, "_generate_from_ti1",
        lambda ti1, ask=True: calls["ti1"].append(str(ti1)) or True)
    ctl.set_profile_run("run1")
    if verification:
        ctl.set_run_type(RUN_TYPE_VERIFICATION)
    return tab, calls


def _pick(tab, key):
    i = tab._preset_combo.findData(key)
    assert i > 0, "the preset is not in the dropdown"
    tab._preset_combo.setCurrentIndex(i)
    tab._on_preset_selected(i)


def test_in_the_gamut_module_the_preset_is_only_a_layout(qapp, tmp_path,
                                                         monkeypatch):
    tab, calls = _tab(tmp_path, monkeypatch)
    tab._switch_mode("gamut")
    tab._gamut_auto_check.setChecked(False)
    tab._gamut_count_spin.setValue(50)
    _pick(tab, KEY)
    assert tab._mode_name() == "gamut"
    assert calls["ti1"] == [], "the preset's own patch set was built"
    assert tab._gamut_auto_check.isChecked()
    assert calls["gamut"] == [608], calls
    assert tab._gamut_chart_patch_total() == 616
    assert tab._manual_stamp_cmd_check.isChecked() is False


def test_the_count_is_capped_by_what_the_profile_can_print(qapp, tmp_path,
                                                          monkeypatch):
    tab, calls = _tab(tmp_path, monkeypatch)
    monkeypatch.setattr(tab, "_gamut_coverage", lambda *a, **k: 300)
    tab._switch_mode("gamut")
    _pick(tab, KEY)
    assert calls["gamut"] == [300]


def test_manual_still_builds_the_presets_own_patches(qapp, tmp_path,
                                                    monkeypatch):
    tab, calls = _tab(tmp_path, monkeypatch)
    tab._switch_mode("manual")
    _pick(tab, KEY)
    assert calls["gamut"] == []
    assert len(calls["ti1"]) == 1 and calls["ti1"][0].endswith(".ti1")


def test_a_profiling_run_still_builds_the_presets_own_patches(qapp, tmp_path,
                                                             monkeypatch):
    tab, calls = _tab(tmp_path, monkeypatch, verification=False)
    _pick(tab, KEY)
    assert calls["gamut"] == [] and len(calls["ti1"]) == 1
