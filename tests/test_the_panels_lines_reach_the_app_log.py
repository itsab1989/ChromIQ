"""A5 (4.3.50): the Measure panel's lines (and the other tabs' on-screen logs) also go
to the app log, in English with the message id where there is one, never twice."""
from __future__ import annotations

import inspect
import logging

from ui.widgets import TailFollowLog


def _panel(caplog):
    return [r.getMessage() for r in caplog.records if r.getMessage().startswith("panel:")]


def test_a_mirrored_panel_writes_each_line(qapp, caplog, monkeypatch):
    from core import i18n
    from core import question_log as ql
    monkeypatch.setattr(i18n, "_catalog", {"Live patch preview off": "Live-Vorschau aus"})
    ql._REVERSE = None
    w = TailFollowLog()
    w.mirror_tab = "measure"
    with caplog.at_level(logging.INFO, logger="chromiq.events"):
        w.appendPlainText("Live-Vorschau aus")
        w.appendHtml("<b>bold</b> line")
        w.appendPlainText("   ")
        w.append_logged_elsewhere("already logged")
    ql._REVERSE = None
    assert _panel(caplog) == ['panel: tab=measure text=Live patch preview off',
                              'panel: tab=measure text=bold line']


def test_a_rendered_message_carries_its_id(qapp, caplog):
    from workflow import measurement_messages as M
    w = TailFollowLog()
    w.mirror_tab = "measure"
    title, body = M.M_CR30_STOCK_READER.render()
    with caplog.at_level(logging.INFO, logger="chromiq.events"):
        w.appendPlainText(body)
    (ln,) = _panel(caplog)
    assert ln.startswith("panel: tab=measure id=M-CR30-STOCK-READER text=")


def test_an_unmirrored_panel_stays_quiet(qapp, caplog):
    w = TailFollowLog()
    with caplog.at_level(logging.INFO, logger="chromiq.events"):
        w.appendPlainText("x")
    assert _panel(caplog) == []


def test_a_flood_is_cut_and_counted(qapp, caplog, monkeypatch):
    from core import question_log as ql
    monkeypatch.setattr(ql, "PANEL_LINES_PER_MINUTE", 5)
    ql._PANEL_COUNT.clear()
    w = TailFollowLog()
    w.mirror_tab = "check"
    with caplog.at_level(logging.INFO, logger="chromiq.events"):
        for i in range(12):
            w.appendPlainText(f"patch {i}")
    assert len(_panel(caplog)) == 5
    ql._PANEL_COUNT.clear()


def test_every_tab_panel_is_mirrored_and_the_measure_lines_are_not_doubled():
    from ui.tabs import tab_chart, tab_check_refine, tab_measure, tab_profile
    for mod, tab in ((tab_measure, "measure"), (tab_chart, "chart"),
                     (tab_profile, "profile"), (tab_check_refine, "check")):
        assert f'self._log.mirror_tab = "{tab}"' in inspect.getsource(mod)
    src = inspect.getsource(tab_measure.TabMeasure._on_log_line)
    assert "append_logged_elsewhere(line)" in src and "log.info(" in src
    src = inspect.getsource(tab_measure.TabMeasure._on_table_log_line)
    assert "append_logged_elsewhere" in src


def test_a_tool_line_the_runner_logged_is_not_mirrored_again(qapp, caplog):
    """S6 (review of 20 Nov): Create Chart and Build Profile wrote every tool
    line twice ("[argyll] Re-seeding" and "panel: tab=chart text=Re-seeding")."""
    from core import argyll_runner as ar
    w = TailFollowLog()
    w.mirror_tab = "chart"
    with caplog.at_level(logging.DEBUG):
        for ln in ("Re-seeding", "Re-seeding", "Added 10/702"):
            ar.log.debug("[argyll] %s", ln)
            ar._note_tool_line(ln)
        w.appendPlainText("Re-seeding")
        w.appendPlainText("Re-seeding")
        w.appendPlainText("Re-seeding")          # a third, the runner logged only two
        w.appendPlainText("Arranging colour patches: 2%")   # the tab's own line
    assert _panel(caplog) == ["panel: tab=chart text=Re-seeding",
                              "panel: tab=chart text=Arranging colour patches: 2%"]


def test_the_runner_notes_every_line_it_logs():
    from core import argyll_runner as ar
    src = inspect.getsource(ar)
    assert src.count('log.debug("[argyll] %s", line)') == src.count("_note_tool_line(line)") == 3
