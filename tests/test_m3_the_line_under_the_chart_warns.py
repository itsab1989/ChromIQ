"""M3 on screen (Basti, 2026-10-21): when the engine's automatic save fails
(M-AUTOSAVE-NOT-SAVED in the log), the line under the chart that says
"Auto-save on, every strip is written to disk..." turns into a warning
(M-AUTOSAVE-RETRYING, on the app's warning colours), and the next save that
works brings the usual line back.
"""
from __future__ import annotations

import types

from PyQt6.QtCore import QObject


def test_the_manager_reports_a_failed_save_as_a_signal(qtbot):
    from workflow.measure_manager import MeasureManager
    mm = MeasureManager.__new__(MeasureManager)
    QObject.__init__(mm)
    got = []
    mm.autosave_failed.connect(lambda *a: got.append(a))
    lines = []
    MeasureManager._on_autosave_failed(
        mm, {"event": "error", "kind": "autosave_rename", "detail": "/x/p.ti3",
             "temp": "/x/p.ti3.cqtmp", "code": 21}, lines.append)
    assert got == [("/x/p.ti3", "/x/p.ti3.cqtmp", "21")]
    assert lines and "p.ti3.cqtmp" in lines[0]       # the log line still comes


def _fake_tab(qtbot):
    from ui.tabs.tab_measure import TabMeasure
    from ui.tiff_preview import TiffPreview
    pv = TiffPreview()
    qtbot.addWidget(pv)
    fake = types.SimpleNamespace(
        _preview=pv, _manager=types.SimpleNamespace(engine_active=True))
    fake._set_autosave_banner = lambda saved=None: TabMeasure._set_autosave_banner(fake, saved)
    return fake, pv, TabMeasure


def test_a_failed_save_turns_the_line_into_a_warning_and_a_good_save_back(qtbot):
    from workflow import measurement_messages as M
    fake, pv, Tab = _fake_tab(qtbot)
    Tab._on_readings_saved(fake, "/x/p.ti3", 21)
    normal = pv._notice_lbl.text()
    assert normal.startswith("Auto-save on") and not pv.notice_is_warning()
    Tab._on_autosave_failed(fake, "/x/p.ti3", "/x/p.ti3.cqtmp", "21")
    assert pv._notice_lbl.text() == M.M_AUTOSAVE_RETRYING.render()[1]
    assert pv.notice_is_warning()
    from ui.warning_sign import warning_colours
    bg, fg = warning_colours(pv._mode)
    assert bg in pv._notice_lbl.styleSheet() and fg in pv._notice_lbl.styleSheet()
    # A later save that works: the usual line, in the usual style.
    Tab._on_readings_saved(fake, "/x/p.ti3", 42)
    assert pv._notice_lbl.text().startswith("Auto-save on")
    assert not pv.notice_is_warning()
    assert "transparent" in pv._notice_lbl.styleSheet()


def test_no_engine_no_warning(qtbot):
    fake, pv, Tab = _fake_tab(qtbot)
    fake._manager.engine_active = False
    Tab._on_autosave_failed(fake, "/x/p.ti3", "/x/p.ti3.cqtmp", "21")
    assert not pv._notice_lbl.text()


def test_the_warning_follows_the_theme(qtbot):
    from ui.warning_sign import warning_colours
    fake, pv, Tab = _fake_tab(qtbot)
    Tab._on_autosave_failed(fake, "/x/p.ti3", "/x/p.ti3.cqtmp", "21")
    for mode in ("light", "neutral", "dark"):
        pv.set_appearance(mode)
        bg, _fg = warning_colours(mode)
        assert bg in pv._notice_lbl.styleSheet(), mode


def test_the_tab_listens():
    import inspect
    from ui.tabs.tab_measure import TabMeasure
    assert "autosave_failed.connect(self._on_autosave_failed)" in inspect.getsource(TabMeasure)
