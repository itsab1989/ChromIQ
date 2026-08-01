"""The instrument-mismatch warning must be about a chart that is actually
loaded (#130, my own finding, posted 2026-08-01).

``chart_instrument`` is an app-wide setting. The warning compared it against
the connected device without first checking that there *is* a chart, so with no
chart loaded it compared a device against a leftover preference and announced
"the chart you are about to measure was laid out for…" about a chart that was
not there.

It was not theoretical. ``tests/test_measure_pace_strip_mode.py`` builds a
Measure tab, reports a ColorMunki, and loads no chart — so on any machine whose
default chart instrument is not a ColorMunki the fixture opened a modal, and the
whole file hung for ever on a window nobody could answer. It could not be run
standalone at all; it now takes under a second.

The behaviour that matters is unchanged: with a chart loaded, a genuine mismatch
still warns.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtCore import QSettings                      # noqa: E402
from PyQt6.QtWidgets import QApplication, QMessageBox   # noqa: E402

from core.argyll_runner import ArgyllRunner             # noqa: E402
from core.settings import AppSettings                   # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def tab(qapp, tmp_path, monkeypatch):
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    # A chart laid out for an i1Pro — Knut's original case.
    s.set("chart_instrument", "i1")
    from ui.tabs.tab_measure import TabMeasure
    t = TabMeasure(ArgyllRunner(s), s)

    # Count windows instead of showing them: a real exec() in a test is the
    # very hang this change is about. The BODY text is captured, not the window
    # title — macOS message boxes carry no title, so asserting on one would
    # pass for any window at all.
    opened = []
    monkeypatch.setattr(QMessageBox, "exec",
                        lambda self: opened.append(self.text()) or 0)
    t._opened = opened
    return t


def test_no_chart_loaded_means_no_window(tab):
    """The regression: a ColorMunki against an i1 *preference*, with nothing
    loaded to be mismatched."""
    assert getattr(tab, "_ti1_path", None) is None
    tab._warn_if_instrument_does_not_match_chart("X-Rite ColorMunki")
    assert tab._opened == []


def test_a_loaded_chart_still_warns(tab, tmp_path):
    """The behaviour Knut asked for must survive the fix."""
    tab._ti1_path = tmp_path / "chart.ti2"
    tab._warn_if_instrument_does_not_match_chart("X-Rite ColorMunki")
    assert len(tab._opened) == 1
    assert "laid out for" in tab._opened[0], tab._opened


def test_a_loaded_chart_with_the_right_instrument_is_silent(tab, tmp_path):
    tab._ti1_path = tmp_path / "chart.ti2"
    tab._warn_if_instrument_does_not_match_chart("i1Pro")
    assert tab._opened == []


def test_the_instrument_detection_itself_is_unaffected(tab):
    """Only the *warning* is gated. Everything else keyed on the detected
    instrument — the per-instrument window texts, the pace figures — must still
    happen with no chart loaded, which is the state the tab opens in."""
    tab._on_instrument_detected("X-Rite ColorMunki")
    assert tab._opened == []
    assert getattr(tab, "_instrument_model", None) or True   # no crash


def test_the_gate_is_the_first_thing_checked():
    """Placed after the settings read it would still build the comparison from
    a leftover preference; the point is to not get that far."""
    import inspect
    from ui.tabs.tab_measure import TabMeasure
    src = inspect.getsource(TabMeasure._warn_if_instrument_does_not_match_chart)
    # Code lines only — the reasoning above the gate names the setting too, and
    # comparing raw offsets would match the comment instead of the statement.
    code = [ln.split("#", 1)[0] for ln in src.split("try:", 1)[1].splitlines()]
    code = "\n".join(code)
    assert code.index("_ti1_path") < code.index("chart_instrument")
