"""Every log panel in the app shows nine lines — not just the Measure tab's.

Knut, beta.120: *"only 6 lines of text are visible, but showing 9 is better."*
Knut, beta.125: *"The log window at the bottom left still has only space for 6
lines of text. The promised increase of height to 9 lines is not implemented."*

He was right, and the reason is worth keeping: the fix had been applied to the
Measure tab only, while Create Chart and Build Profile still pinned their logs
to a hard-coded 67 px. A test that only looked at the tab that was changed
would have stayed green through the whole complaint — so this one measures
**every** log, in lines of the font it really has.
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from ui.widgets import LOG_VISIBLE_LINES, fit_log_height       # noqa: E402


def _lines(log) -> float:
    """How many lines of its own text the panel can actually show."""
    fm = log.fontMetrics()
    inner = (log.height()
             - int(log.document().documentMargin()) * 2
             - log.frameWidth() * 2)
    return inner / fm.lineSpacing()


def _tabs(qapp):
    from core.argyll_runner import ArgyllRunner
    from core.file_manager import FileManager
    from core.settings import AppSettings
    from ui.tabs.tab_chart import TabChart
    from ui.tabs.tab_measure import TabMeasure
    from ui.tabs.tab_profile import TabProfile

    st = AppSettings()
    runner = ArgyllRunner(st)
    fm = FileManager(st)
    return [
        ("Create Chart", TabChart(runner, fm, st, None), ["_log"]),
        ("Build Profile", TabProfile(runner, st, None),
         ["_log", "_pc_log", "_ac_log"]),
        ("Measure", TabMeasure(runner, st, None), ["_log"]),
    ]


def test_every_log_shows_nine_lines(qapp):
    seen = 0
    for name, tab, attrs in _tabs(qapp):
        tab.resize(1200, 900)
        tab.show()
        qapp.processEvents()
        for attr in attrs:
            log = getattr(tab, attr, None)
            if log is None:
                continue
            seen += 1
            assert _lines(log) == pytest.approx(LOG_VISIBLE_LINES, abs=0.25), \
                f"{name}.{attr} shows {_lines(log):.2f} lines"
        tab.hide()
    assert seen >= 5, "every log panel in the app is covered"


def test_no_tab_pins_a_log_to_a_pixel_height():
    """A pixel number cannot promise a line count — the log's font arrives at
    polish, after any height set in __init__."""
    import inspect

    from ui.tabs import tab_chart, tab_measure, tab_profile

    for module in (tab_chart, tab_measure, tab_profile):
        src = inspect.getsource(module)
        for line in src.splitlines():
            if "log" in line.lower() and "setMaximumHeight(" in line:
                assert "fit_log_height" in line or "(h)" in line, \
                    f"{module.__name__}: {line.strip()}"


def test_the_height_is_re_measured_after_polish():
    """Set in __init__ it is measured against the wrong font, so every tab has
    to re-fit once it is shown."""
    import inspect

    from ui.tabs.tab_chart import TabChart
    from ui.tabs.tab_measure import TabMeasure
    from ui.tabs.tab_profile import TabProfile

    for cls, hook in ((TabChart, "_refit_logs"),
                      (TabProfile, "_refit_logs"),
                      (TabMeasure, "_fit_log_height")):
        assert hook in inspect.getsource(cls.showEvent), cls.__name__
        assert hook in inspect.getsource(cls.changeEvent), \
            f"{cls.__name__} must follow a theme or font change too"


def test_sizing_a_broken_log_never_raises():
    """A log that cannot be measured keeps the height it has; it does not take
    the tab down with it."""
    class _Broken:
        def fontMetrics(self):
            raise RuntimeError("no font")

    fit_log_height(_Broken())      # must not raise
