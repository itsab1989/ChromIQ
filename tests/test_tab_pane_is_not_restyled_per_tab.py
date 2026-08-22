"""Switching tabs must not re-style the whole window.

The QTabWidget pane stylesheet used to carry the current tab's accent, so the
string differed on every tab and was re-applied on every switch. Setting a
stylesheet on the tab widget re-polishes all five tab trees — 26,053
style/font/palette events — which made a switch cost 256 ms, felt as a delay
between the click and the tab appearing. Measured after: 8.9 ms.

Nothing on screen changes. The hairline is covered by the tab bar (forcing it
opaque red over a bright green pane moved 0 of 7,464,960 pixels, while a 12 px
border moved a million, so the rule reaches the widget and is simply invisible),
and the accent under the active tab is `_accent_line`, a separate widget.
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PyQt6")

from PyQt6.QtCore import QSettings                     # noqa: E402
from PyQt6.QtWidgets import QApplication              # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def win(qapp, tmp_path):
    from core.settings import AppSettings
    from ui.main_window import MainWindow
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    s.set("custom_output_path", str(tmp_path / "projects"))
    w = MainWindow(s)
    yield w
    w.close()


def test_the_pane_sheet_is_the_same_for_every_tab(win):
    """The property the whole saving rests on."""
    sheets = {win._compose_pane_qss() for _ in range(3)}
    assert len(sheets) == 1
    # …and it takes no index. A leftover positional argument would bind to
    # pane_bg and produce invalid QSS that nothing would notice.
    import inspect
    params = list(inspect.signature(win._compose_pane_qss).parameters)
    assert "index" not in params, (
        "the pane sheet must not depend on which tab is current")


def test_the_pane_sheet_still_follows_the_theme(win):
    """It must NOT be frozen outright: dark would keep light's pane."""
    win._title_bar_mode = "light"
    light = win._compose_pane_qss()
    win._title_bar_mode = "dark"
    dark = win._compose_pane_qss()
    assert light != dark, "the pane no longer changes with the theme"
    assert "#ffffff" in light and "#181818" in dark


def test_switching_tabs_does_not_set_the_stylesheet_again(win):
    """Counted, not timed — a timing test would be flaky, and the cost IS the
    call. A theme change must still re-apply it."""
    calls = []
    real = win._tabs.setStyleSheet
    win._tabs.setStyleSheet = lambda qss: (calls.append(qss), real(qss))[1]

    for i in list(range(win._tabs.count())) + [0, 2, 1]:
        win._tabs.setCurrentIndex(i)
        win._on_tab_changed(i)
    assert not calls, (
        f"{len(calls)} pane re-styles across 8 tab switches; each one repolishes "
        "every widget in every tab")

    win.apply_theme("light" if win._title_bar_mode == "dark" else "dark")
    assert calls, "a theme change must still re-apply the pane sheet"


def test_the_pane_border_is_the_colour_the_report_dialog_needs(win):
    """The one property nobody pinned, which is the one I got wrong.

    `MeasurementReportDialog` is parented to the Measure tab, so its trend tabs
    INHERIT this sheet when the dialog is opened from there — and do not when it
    is opened from Tools. Any border colour other than these leaves the same
    dialog showing a different hairline depending on where the user came from:
    `rgba(0,0,0,0.10)` measured 2,400 px apart at ΔRGB 42 between the two entry
    points. These give (0,0,0) from both.

    Also pins that the rule still EXISTS and is still applied — deleting
    `border-top`, or never applying the sheet in the constructor, was caught by
    nothing before.
    """
    for mode, border, bg in (("light", "#d0ccc6", "#ffffff"),
                             ("dark", "#000000", "#181818")):
        win._title_bar_mode = mode
        qss = win._compose_pane_qss()
        assert f"border-top: 1px solid {border}" in qss, (
            f"{mode}: the pane border must be {border}, or the measurement "
            "report dialog disagrees with itself")
        assert f"background: {bg}" in qss
    # …and the constructor really applies it, so the report dialog inherits
    # something rather than falling back to the app-wide rule.
    assert win._tabs.styleSheet() == win._pane_qss != ""
