"""The Measure tab's button row fits its pane in every language (beta 18 review).

Beta 18 (da08420f8) gave the Start button room for both of its labels, "Start
Measurement" and "Continue Measurement", so the second is never cut. In
Russian "ПРОДОЛЖИТЬ ИЗМЕРЕНИЕ" is so wide that the reserved Start button, Stop
and "Сохранить как умолчания" needed 619 px in the fixed 580 px pane. Measured
on screen at the main window's 900 px minimum: Start ran 6 px under Stop and
Save as Defaults 11 px past the pane into the preview splitter, in EVERY state,
because the reservation holds the width even while the button says Start.
Beta 17 had instead cut the Continue label ("ОДОЛЖИТЬ ИЗМЕРЕН").

The fix is the Russian label "Продолжить" (as "Continue" and "Resume" already
read), which keeps the reservation and needs less room than "Начать
измерение". Report: ~/Desktop/ChromIQ-work/2026-10-10_beta18_ru_row/.

The earlier tests asked whether each button was wide enough for its own text,
which it was. This asks the neighbour question: does each button end before
the next begins, and does the last one end inside the pane? The pane is
`setFixedWidth(580)`, so the window's width does not enter into it, and the
offscreen numbers match the on-screen ones to the pixel (Russian before the
fix: 619 px wanted, 6 px overlap, both measured here and on screen).
"""
from __future__ import annotations

import pytest
from PyQt6.QtCore import QEvent, QSettings
from PyQt6.QtWidgets import QApplication

from core import i18n
from core.argyll_runner import ArgyllRunner
from core.settings import AppSettings
from ui.widgets import ButtonFontFilter

LANGS = ("en", "de", "es", "fr", "it", "ja", "nl", "no", "pl", "pt", "ru",
         "sv", "uk", "zh_CN")


@pytest.fixture(autouse=True)
def _english_before_and_after(qapp):
    i18n.set_language("en")
    yield
    i18n.set_language("en")


@pytest.fixture
def make_tab(qapp, tmp_path):
    """A real TabMeasure built IN the language, in the light stylesheet.

    The sheet goes on the tab, never on the app (CLAUDE.md: `qapp.setStyleSheet`
    re-polishes the whole suite), and the buttons get the app's font and width
    rule from `ButtonFontFilter.fit_window`, as main.py's filter would.
    """
    from ui.tabs.tab_measure import TabMeasure
    from ui.theme import _APPEARANCE_STYLE
    made = []

    def _make(code: str):
        i18n.set_language(code)
        s = AppSettings()
        s._qs = QSettings(str(tmp_path / f"s-{code}.ini"),
                          QSettings.Format.IniFormat)
        s.set("custom_output_path", str(tmp_path / "out"))
        tab = TabMeasure(ArgyllRunner(s), s)
        made.append(tab)
        tab.setStyleSheet(_APPEARANCE_STYLE["light"][0])
        tab.resize(1200, 900)
        tab.show()
        qapp.processEvents()
        return tab, s

    yield _make
    for tab in made:
        tab.hide()
        tab.setParent(None)
        tab.deleteLater()
    qapp.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    qapp.processEvents()


def _settle(tab):
    ButtonFontFilter.fit_window(tab)
    QApplication.processEvents()
    tab._start_btn.parentWidget().layout().activate()
    QApplication.processEvents()


def _row_faults(tab) -> list[str]:
    outer = tab._start_btn.parentWidget()
    margins = outer.layout().contentsMargins()
    limit = outer.width() - margins.right()
    btns = [b for b in (tab._start_btn, tab._stop_btn, tab._calibrate_btn,
                        tab._import_go_btn, tab._save_defaults_btn)
            if b.isVisibleTo(tab)]
    btns.sort(key=lambda b: b.x())
    faults = []
    for a, b in zip(btns, btns[1:]):
        if a.geometry().right() >= b.x():
            faults.append(f"{a.text()!r} runs {a.geometry().right() - b.x() + 1}"
                          f" px under {b.text()!r}")
    last = btns[-1]
    if last.geometry().right() >= limit:
        faults.append(f"{last.text()!r} ends {last.geometry().right() - limit + 1}"
                      f" px past the pane's {limit} px")
    for b in btns:
        if b.width() < b.minimumSizeHint().width():
            faults.append(f"{b.text()!r} squeezed to {b.width()} px, below "
                          f"its own {b.minimumSizeHint().width()} px")
    return faults


@pytest.mark.parametrize("code", LANGS)
def test_the_measure_row_fits_the_pane_in_every_state(make_tab, code):
    tab, s = make_tab(code)
    tr = i18n.tr
    found = {}

    def check(state):
        _settle(tab)
        faults = _row_faults(tab)
        if faults:
            found[state] = faults

    tab._start_btn.setText(tr("Start Measurement"))
    check("start")
    tab._start_btn.setText(tr("Continue Measurement"))
    check("continue")
    # A live session: Stop enabled, and with Preferences' Calibrate button on,
    # Calibrate standing where Save as Defaults stood.
    tab._session_live = True
    tab._start_btn.setEnabled(False)
    tab._stop_btn.setEnabled(True)
    tab._sync_calibrate_btn_visible()
    check("live")
    s.set("measure_calibrate_button", True)
    tab._sync_calibrate_btn_visible()
    assert tab._calibrate_btn.isVisibleTo(tab)
    check("live-continue+calibrate")
    tab._start_btn.setText(tr("Start Measurement"))
    check("live-start+calibrate")
    tab._session_live = False
    tab._sync_calibrate_btn_visible()
    assert not found, f"[{code}] {found}"


def test_the_russian_continue_label_is_the_short_one(qapp):
    """The cause, pinned: the long form needs 39 px more than the pane has."""
    i18n.set_language("ru")
    assert i18n.tr("Continue Measurement") == "Продолжить"
