"""A tick box whose row is indented must lose the indent, not its own text.

Basti, 2026-08-27, with a screenshot: in German the Create Chart ▸ Manual tick
box "Verwendete Einstellungen aufs Chart drucken" lost its last letters and ran
under the ⓘ beside it. It needed 297 px and was handed 294.

The row is `[indent spacer][tick box][stretch][ⓘ]`, and the spacer was a FIXED
196 px whose only job is to line the tick box up with the input column above it.
A fixed width cannot yield, so when the row ran short the tick box was the only
thing left that could give — and a tick box gives by clipping its label.

Alignment is worth having when there is room and worth nothing when there is
not. The spacer now has a MAXIMUM instead of a fixed width.
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

#: Every language the app ships, longest-first by this label. Russian needs
#: 331 px against English's 225 — a 47 % spread, which is why English alone
#: never caught it.
_LANGS = ["ru", "de", "nl", "fr", "it", "pt", "pl", "es", "sv", "no", "en"]


@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def _stamp_check(qapp, lang, tmp_path):
    import importlib

    import core.i18n as i18n
    from PyQt6.QtCore import QSettings

    from core.argyll_runner import ArgyllRunner
    from core.file_manager import FileManager
    from core.settings import AppSettings

    i18n.set_language(lang)
    tc = importlib.reload(importlib.import_module("ui.tabs.tab_chart"))
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / f"{lang}.ini"), QSettings.Format.IniFormat)
    tab = tc.TabChart(ArgyllRunner(s), FileManager(s), s)
    tab.resize(1120, 900)
    tab._switch_mode("manual")
    tab.show()
    qapp.processEvents()
    return tab, tab._manual_stamp_cmd_check


@pytest.mark.parametrize("lang", _LANGS)
def test_the_stamp_tick_box_shows_its_whole_label(qapp, lang, tmp_path):
    tab, cb = _stamp_check(qapp, lang, tmp_path)
    try:
        need = cb.minimumSizeHint().width()
        assert cb.width() >= need, (
            f"{lang}: the tick box has {cb.width()} px and needs {need} — its "
            f"label is clipped: {cb.text()!r}")
    finally:
        tab.deleteLater()
        qapp.processEvents()


def test_this_file_can_see_the_bug_it_guards(qapp, tmp_path):
    """Control. Pin the indent back to a fixed width and German must fail again
    — otherwise the assertions above would hold against any layout at all."""
    from PyQt6.QtWidgets import QLabel

    tab, cb = _stamp_check(qapp, "de", tmp_path)
    try:
        row = tab._manual_stamp_cmd_row
        spacer = row.layout().itemAt(0).widget()
        assert isinstance(spacer, QLabel) and not spacer.text(), (
            "the row's first item is no longer the indent spacer — this control "
            "is testing something else now")
        spacer.setFixedWidth(spacer.maximumWidth())     # the old, unyielding form
        row.layout().activate()
        qapp.processEvents()
        assert cb.width() < cb.minimumSizeHint().width(), (
            "pinning the indent back did NOT clip the German label, so the "
            "assertions above are not measuring the indent")
    finally:
        tab.deleteLater()
        qapp.processEvents()
