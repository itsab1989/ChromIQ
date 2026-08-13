"""The Preferences credit line links the ChromIQ website (Knut, 2026-08-12).

His request: a link to the webpage above the update button, where the
"Created by …" text is. Sebastian's refinements: a link word, not the raw
URL ("something that looks nice"), in the app's magenta accent. And Knut's
condition — without messing up the layout of the Preferences window.
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtCore import QSettings                     # noqa: E402
from PyQt6.QtWidgets import QApplication, QLabel       # noqa: E402

from core.settings import AppSettings                  # noqa: E402
from core.updater import WEBSITE_URL                   # noqa: E402
from ui.styles import SPEC_MAGENTA                     # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _dialog(tmp_path):
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    from ui.dialogs.settings_dialog import SettingsDialog
    return SettingsDialog(s)


def _credit(dlg) -> QLabel:
    labs = [l for l in dlg.findChildren(QLabel) if "Created by" in l.text()]
    assert len(labs) == 1, [l.text() for l in labs]
    return labs[0]


def test_the_credit_line_links_the_website(qapp, tmp_path):
    dlg = _dialog(tmp_path)
    try:
        lab = _credit(dlg)
        assert f'href="{WEBSITE_URL}"' in lab.text()
        assert lab.openExternalLinks(), "the link must open the browser"
        assert ">Website<" in lab.text(), "a link word, not the raw URL"
        assert WEBSITE_URL not in lab.text().replace(
            f'href="{WEBSITE_URL}"', ""), "the raw URL must not be shown"
    finally:
        dlg.deleteLater()


def test_the_link_uses_the_magenta_accent(qapp, tmp_path):
    """Sebastian, 2026-08-13: "the website link in preferences should use
    the magenta accent color". SPEC_MAGENTA is theme-independent, so one
    inline colour reads in both light and dark mode."""
    dlg = _dialog(tmp_path)
    try:
        assert f"color:{SPEC_MAGENTA}" in _credit(dlg).text()
    finally:
        dlg.deleteLater()


def test_the_line_does_not_widen_the_dialog(qapp, tmp_path):
    """Knut's condition: without messing up the Preferences layout — the
    credit line must never be the thing that decides the dialog's width."""
    dlg = _dialog(tmp_path)
    try:
        dlg.show()
        lab = _credit(dlg)
        assert lab.sizeHint().width() < dlg.width()
    finally:
        dlg.close()
        dlg.deleteLater()
