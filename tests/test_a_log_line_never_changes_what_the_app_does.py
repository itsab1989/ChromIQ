"""S1 (review of the app-log branch, 20 Nov 2026): a logging call must never
change what the app does.

The review planted a raiser in every app-log entry point and found three
call-site classes that let the fault through: the ruler diagnostics switched
off (``ruler_session``), the dual calibration and instrument handling skipped
(``measure_manager``), the answer to "Strip may be misaligned" lost
(``tab_measure``). The fix is structural: every helper entry point is wrapped
by ``core.app_log.never_raises`` (catch, count, report once), and those call
sites have their own guard as well.

Each scenario below runs three ways: with logging as it is, with a fault
raised INSIDE the helper (the logger itself raises), and with the helper
replaced by a raiser (the review's plant). All three must do the same thing.
"""
from __future__ import annotations

import json
import logging

import pytest

import core.app_log as A
import core.question_log as Q
import workflow.measure_log as ML


def _boom(*_a, **_k):
    raise RuntimeError("PLANTED-LOG-FAULT")


class _RaisingLogger:
    def log(self, *_a, **_k):
        raise RuntimeError("PLANTED-INSIDE-THE-HELPER")

    def __getattr__(self, _n):
        return self.log


@pytest.fixture(params=["plain", "inside", "plant"])
def fault(request, monkeypatch):
    if request.param == "inside":
        monkeypatch.setattr(A, "log", _RaisingLogger())
    elif request.param == "plant":
        for mod, names in ((A, ["line", "text_line", "flat", "pairs"]),
                           (Q, ["answered", "auto_answered", "window_shown",
                                "window_hidden", "panel_line", "note_rendered"]),
                           (ML, ["log_start", "log_measurement_end", "written"])):
            for n in names:
                monkeypatch.setattr(mod, n, _boom)
        monkeypatch.setattr(ML.StripLog, "decided", _boom)
        monkeypatch.setattr(ML.StripLog, "ready", _boom)
    return request.param


# --- the helpers themselves --------------------------------------------------------

def test_every_entry_point_is_wrapped():
    for fn in (A.line, A.text_line, A.pairs, Q.answered, Q.auto_answered, Q.window_shown,
               Q.window_hidden, Q.panel_line, Q.note_rendered, ML.written, ML.log_start,
               ML.log_measurement_end, ML.StripLog.decided, ML.StripLog.ready):
        assert getattr(fn, "__wrapped__", None) is not None, fn


def test_a_fault_inside_is_counted_and_reported_once(monkeypatch, caplog):
    monkeypatch.setattr(A, "log", _RaisingLogger())
    monkeypatch.setattr(A, "failures", 0)
    monkeypatch.setattr(A, "_reported", False)
    with caplog.at_level(logging.WARNING, logger="chromiq.app_log"):
        for _ in range(3):
            assert A.line("strip", id="A") is None
            Q.answered("M-X", "keep", strip="A")
            ML.written("measurement", "/x.ti3")
    assert A.failures == 9
    said = [r.getMessage() for r in caplog.records if r.name == "chromiq.app_log"]
    assert len(said) == 1 and "could not be written" in said[0]


def test_an_event_key_named_like_a_parameter_does_not_raise(caplog):
    with caplog.at_level(logging.INFO, logger="chromiq.events"):
        A.line("measure instrument", **{"tag": "x", "_level": "loud", "model": "i1pro2"})
        Q.answered("M-X", "keep", id="dup", answer="dup")
        ML.written("measurement", "/x.ti3", what="dup", path="dup")
    said = " ".join(r.getMessage() for r in caplog.records)
    assert "measure instrument: tag=x" in said and "_level=loud" in said
    assert "question answer: id=M-X answer=keep" in said
    assert "file written: what=measurement" in said


# --- (a) the ruler's diagnostics file ----------------------------------------------

def test_the_ruler_keeps_its_diagnostics_file(tmp_path, fault):
    from workflow.ruler_session import RulerSession
    ti1 = tmp_path / "runs" / "run1" / "chart.ti1"
    ti1.parent.mkdir(parents=True)
    rs = RulerSession(ti1_path=ti1)
    lines = rs.on_session({"event": "ruler", "active": True,
                           "instrument": "i1pro2", "firmware": 634})
    assert rs.diag is not None, fault
    assert rs.diagnostics_path().is_file()
    assert str(rs.diagnostics_path()) in lines[1]


# --- (b) the measure manager's engine events ---------------------------------------

def _manager(qapp):
    from workflow.measure_manager import MeasureManager

    class _R:
        is_running = True

        def write_stdin(self, _d):
            pass
    m = MeasureManager(_R())
    m._engine_active = True
    m._guided_state = "disabled"
    return m


def test_dual_calibration_instrument_and_filter_are_handled(qapp, fault):
    m = _manager(qapp)
    got = []
    m.dual_calibration.connect(lambda ev: got.append(("dual_calibration", ev.get("ok"))))
    m.instrument_detected.connect(lambda model: got.append(("instrument", model)))
    for ev in ({"event": "dual_calibration", "ok": True, "why": "", "mode": "scan"},
               {"event": "instrument", "model": "i1pro2", "tag": "x", "_level": 3},
               {"event": "filter", "filter": "UVcut"}):
        m._handle_engine_line(json.dumps(ev), lambda _l: None)
    assert got == [("dual_calibration", True), ("instrument", "i1pro2")], fault
    assert m._dual_cal_ok is True and m._engine_model == "i1pro2"
    assert m.engine_filter == "UVcut"


def test_a_skipped_strip_still_sends_its_key(qapp, fault):
    from workflow.measure_log import StripLog
    m = _manager(qapp)
    m._strip_log = StripLog()
    sent = []
    m.send_command = sent.append
    m._spot_mode = False
    m._dual_strip_now = "A"
    m.skip_current_strip()
    # what the plain run sends (the strip-log line is written BEFORE it)
    assert sent == [{"cmd": "ok"}], fault


# --- (c) the answer to "Strip may be misaligned" -----------------------------------

def test_the_misaligned_strip_answer_is_acted_on(qapp, monkeypatch, fault):
    from PyQt6.QtWidgets import QPushButton
    from core.argyll_runner import ArgyllRunner
    from core.settings import AppSettings
    from ui.tabs.tab_measure import TabMeasure
    s = AppSettings()
    tab = TabMeasure(ArgyllRunner(s), s)

    def press_remeasure(dlg):
        for b in dlg.findChildren(QPushButton):
            if b.text() == "Re-measure this strip":
                b.click()
        return 0
    monkeypatch.setattr(tab, "_exec_measurement_window", press_remeasure)
    went = []
    monkeypatch.setattr(tab._manager, "goto_strip", went.append)
    tab._on_strip_partly_misaligned({
        "strip": "36", "offset": 1, "reversed": False, "whole": False,
        "first": "36B", "last": "36H", "lead": "36A", "lead_paper": True,
        "base": 48.94, "best": 2.06})
    assert went == ["36"], fault
    tab.deleteLater()
