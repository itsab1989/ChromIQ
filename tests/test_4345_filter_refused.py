"""4.3.45: a "Spectral filter type (-F)" choice the instrument refuses is SAID.

A tester on dpreview (#349) chose a Spectral Filter in Measure > Manual with
an i1Pro 2 (also sold as ES-2000): the measurement started and fell straight
back to Start with no message. ArgyllCMS 3.5.0's chartread (and the helper's
copy of its code) prints "Setting requested filter not supported by
instrument" and exits; nothing in ChromIQ listened for it.

Pinned here: the line is the one the C sources print; either reader's parser
raises `filter_refused`; the refusal is never a reason to fall back to stock
chartread (it refuses -F the same way); the Measure tab shows M-FILTER-REFUSED
(§M-PROPOSED) when the read ends, with the row's entry and the Start button
named, plays Instrument error, and does not grey the row.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parent.parent
LINE = "Setting requested filter not supported by instrument"


def test_the_line_is_the_one_the_reader_prints():
    helper = (ROOT / "native" / "chartread_helper" /
              "chromiq_chartread.c").read_text(encoding="utf-8", errors="replace")
    assert f'printf("{LINE}\\n");' in helper
    orig = ROOT / "native" / "instlib" / "chartread.c.orig"
    if orig.is_file():
        assert f'printf("{LINE}\\n");' in orig.read_text(encoding="utf-8", errors="replace")


def test_either_parser_raises_it_and_nothing_else(qapp):
    from core.argyll_runner import ArgyllRunner
    from core.settings import AppSettings
    from workflow.measure_manager import MeasureManager
    s = AppSettings()
    mm = MeasureManager(ArgyllRunner(s))
    got = {}
    for name in ("filter_refused", "coms_init_failed", "inst_init_failed",
                 "instrument_wrong_type", "ccmx_load_failed",
                 "mode_set_failed"):
        getattr(mm, name).connect(
            lambda *a, n=name: got.setdefault(n, []).append(a))
    mm._check_startup_failures(LINE)
    assert got == {"filter_refused": [(LINE,)]}
    assert mm._filter_refused is True
    # a line that only mentions a filter is not it
    got.clear()
    mm._check_startup_failures("Spectral filter type set to D50")
    assert got == {}


def test_a_refusal_is_never_a_reason_to_fall_back(qapp):
    from core.argyll_runner import ArgyllRunner
    from core.settings import AppSettings
    from workflow.measure_manager import MeasureManager
    s = AppSettings()
    mm = MeasureManager(ArgyllRunner(s))
    mm._engine_progress = False
    mm._user_quit = False
    mm._engine_fallback_used = False
    mm._cal_request_used = False
    mm._chart_unreadable = None
    mm._stock_cannot_read_chart = ""
    mm._resume_spectral_changed = False
    mm._engine_fatal = None
    mm._engine_saw_event = False          # a helper that "never spoke"
    mm._filter_refused = False
    assert mm._engine_should_fall_back(255) is True
    mm._filter_refused = True
    assert mm._engine_should_fall_back(255) is False
    assert mm._engine_should_resume_fallback(255) is False


@pytest.fixture
def tab(qapp, monkeypatch):
    from core.argyll_runner import ArgyllRunner
    from core.settings import AppSettings
    from ui.tabs.tab_measure import TabMeasure
    s = AppSettings()
    t = TabMeasure(ArgyllRunner(s), s)
    cues = []
    monkeypatch.setattr(t, "_cue_window", lambda ev: cues.append(ev))
    t._cues = cues
    yield t
    t.deleteLater()


def test_the_window_says_what_happened_and_what_to_do(tab, monkeypatch):
    from PyQt6.QtWidgets import QMessageBox
    shown = []
    monkeypatch.setattr(QMessageBox, "exec", lambda self: shown.append(
        (self.windowTitle(), self.text(), self.informativeText())) or 0)
    monkeypatch.setattr(type(tab), "_measure_filter_code", lambda self: "5")
    tab._filter_refused_window()
    assert tab._cues == ["INSTRUMENT_ERROR"]
    (_title, head, body), = shown       # (macOS shows no title on a box)
    assert head == "The instrument does not accept this filter choice"
    assert "“M1: D50 daylight (with UV)”" in body
    assert LINE in body
    assert "i1Pro 2 (also sold as ES-2000)" in body
    assert "switch “Spectral filter type (-F)” off" in body
    assert f"press “{tab._start_button_name()}” again" in body
    assert "M0" in body and "—" not in body and "{" not in body


def test_the_read_ending_that_way_shows_it_once(tab, monkeypatch):
    seen = []
    monkeypatch.setattr(type(tab), "_filter_refused_window",
                        lambda self: seen.append("window"))
    tab._on_filter_refused(LINE)
    assert tab._filter_refused is True
    tab._on_measure_done(255)
    assert seen == ["window"] and tab._filter_refused is False
    tab._on_measure_done(255)                       # a later ending: silent
    assert seen == ["window"]


def test_the_row_is_not_greyed():
    """The owner's rule: an option is greyed only where it has no meaning;
    -F has one on the instruments that accept it, so this is a warning."""
    import inspect
    from ui.tabs import tab_measure
    src = inspect.getsource(tab_measure.TabMeasure._filter_refused_window)
    assert "setEnabled" not in src
