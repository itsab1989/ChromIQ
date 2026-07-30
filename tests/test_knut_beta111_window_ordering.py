"""#130 (Knut, 2026-07-30, testing beta.109): pre-measurement windows must be
settled one at a time, in order.

    *"Started measurement: Two windows popped up simultaneously, first 'This
    chart was made for a different instrument' (i1Pro, but I have connected
    colormunki), then 'Calibration Required' came on top. The window check that
    makes 'This chart was made for a different instrument' window appear should
    come first, and should be completed before progressing if I chose 'Measure
    Anyway', and only then go to measurement and the 'Calibration Required'
    window … Any check that has a window popup that come before going into
    actual measurement mode, should be handled and completed first."*

They stacked because the instrument the chart was made for can only be compared
against the instrument that is actually connected once ``chartread`` has opened
the device — so the check runs on a signal from the running process, and its
window runs a nested event loop. That loop keeps delivering chartread's output,
so the calibration prompt opened on top of a question nobody had answered.

The fix serialises them: while a check that must be settled is on screen, a
calibration prompt is held, and it opens once — and only if — the user chose to
carry on measuring.
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtCore import QSettings                          # noqa: E402
from PyQt6.QtWidgets import QApplication                    # noqa: E402

from core.argyll_runner import ArgyllRunner                 # noqa: E402
from core.settings import AppSettings                       # noqa: E402
from ui.tabs.tab_measure import TabMeasure                  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _tab(tmp_path):
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    return TabMeasure(ArgyllRunner(s), s)


def test_a_calibration_prompt_waits_while_a_check_is_on_screen(qapp, tmp_path,
                                                               monkeypatch):
    tab = _tab(tmp_path)
    opened: list = []
    monkeypatch.setattr(tab, "_cue_window", lambda ev: opened.append(ev))

    tab._pre_measure_window_open = True
    tab._on_calibration_prompt("reflective", "please calibrate", False)

    assert opened == [], "the calibration window opened over an unanswered check"
    assert tab._deferred_calibration == ("reflective", "please calibrate", False)


def test_it_opens_normally_when_nothing_is_waiting(qapp, tmp_path, monkeypatch):
    """The hold must not become a permanent block: with no check on screen the
    prompt behaves exactly as before.

    The dialog is answered without being shown — a real ``exec()`` here would
    wait forever for a click that no test can make.
    """
    from PyQt6.QtWidgets import QDialog
    monkeypatch.setattr(QDialog, "exec", lambda self: 0)
    tab = _tab(tmp_path)
    reached: list = []
    monkeypatch.setattr(tab, "_cue_window", lambda ev: reached.append(ev))
    tab._pre_measure_window_open = False

    tab._on_calibration_prompt("reflective", "please calibrate", False)

    assert reached == ["INSTRUMENT_ERROR"], "the prompt was swallowed"
    assert getattr(tab, "_deferred_calibration", None) is None


def test_the_mismatch_window_holds_and_then_releases(qapp):
    """Order, expressed as code: claim the turn, answer, hand it on."""
    import inspect
    src = inspect.getsource(TabMeasure._warn_if_instrument_does_not_match_chart)
    assert src.index("_pre_measure_window_open = True") < src.index("box.exec()")
    assert src.index("box.exec()") < src.index("_on_calibration_prompt(*held)")


def test_the_hold_is_released_even_if_the_window_raises(qapp):
    """A stuck flag would silence every calibration prompt for the rest of the
    session, which is far worse than the bug being fixed."""
    import inspect
    src = inspect.getsource(TabMeasure._warn_if_instrument_does_not_match_chart)
    assert "finally:" in src
    assert src.index("finally:") < src.index("_pre_measure_window_open = False")


def test_declining_the_measurement_drops_the_held_window(qapp):
    """Cancel means no measurement, so a calibration window for it would be
    about something that is no longer happening."""
    import inspect
    src = inspect.getsource(TabMeasure._warn_if_instrument_does_not_match_chart)
    abort = src.index("self._manager.abort()")
    assert src.index("_deferred_calibration = None", abort) > abort
    assert src.index("return", abort) > abort
