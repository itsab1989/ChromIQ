"""B8-1409: a built-in preset on a custom paper puts printtarg's -p on it.

The engine built-ins go into the layout panel with its mirror held off
(`set_recipe` runs under `_loading`), so "i1Pro 100x150mm-600p-4pages" laid
out on 100 x 150 while printtarg's -p stayed on the A4 it held before, and the
settings stored with the chart recorded `printtarg-p = A4` (the B8-1363 probe).
`_seed_knut_preset` now mirrors the panel's instrument and paper into -i / -p
once, the way a paper chosen in the panel is mirrored.

Mutation (run red): M1409-a the mirror call removed.
"""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest                                                  # noqa: E402

KEY_100x150 = "__chromiq_knut_i1_photo_100x150mm_600p_4pages_portrait_w7_5mm__"


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
    t = TabChart(ArgyllRunner(s), FileManager(s), s)
    t._switch_mode("manual")
    yield t
    t.hide()
    t.deleteLater()


def _engine_builtin(key):
    from ui.tabs.tab_chart import KNUT_PRESETS_BY_KEY
    p = KNUT_PRESETS_BY_KEY[key]
    assert p.layout_recipe is not None or p.engine
    return p


def test_the_100x150_builtin_puts_minus_p_on_its_paper(tab):
    p = _engine_builtin(KEY_100x150)
    tab._set_manual_value("printtarg", "-p", "A4")
    tab._set_engine_checked(True)
    tab._seed_knut_preset(KEY_100x150)
    panel_paper = tab._manual_layout_panel.selection()[1]
    assert panel_paper == "100x150", panel_paper
    assert tab._manual_get("printtarg", "-p", None) == "100x150"
    assert tab._manual_get("printtarg", "-i", None) == p.instrument


def test_an_a4_builtin_still_reads_a4(tab):
    from ui.tabs.tab_chart import KNUT_PRESETS_BY_KEY
    key = next(k for k, v in KNUT_PRESETS_BY_KEY.items()
               if (v.layout_recipe is not None or v.engine)
               and str(v.paper) == "A4")
    tab._set_manual_value("printtarg", "-p", "Letter")
    tab._set_engine_checked(True)
    tab._seed_knut_preset(key)
    assert tab._manual_get("printtarg", "-p", None) == \
        tab._manual_layout_panel.selection()[1]
