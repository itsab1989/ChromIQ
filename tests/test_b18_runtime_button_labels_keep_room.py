"""A button whose words change keeps room for every one of them (beta 18).

Beta 17 found "Undo delete" cut to "NDO DELET" in Read single patches and gave
`ui.widgets.reserve_button_labels`. Beta 18 measured every button in the app
that changes its own text, on screen, at its window's minimum width, in all
fourteen languages (`~/Desktop/ChromIQ-work/2026-10-10_beta18_builder/`,
`drive_runtime_button_labels.py`): 392 cases, and these were cut:

* scanner window, "Undo auto align" (English "NDO AUTO ALIG");
* scanner window, the build button switched between its printer and its
  scanner title (eight languages);
* scanner window, "Install Profile Anyway" (Russian);
* Preferences, "Hide each set's credit" (Swedish);
* Measure tab, "Continue Measurement" (Russian).

Each now reserves its labels. After the fix: 392 cases, 0 cut.
"""
from __future__ import annotations

import pytest
from PyQt6.QtCore import QSettings
from PyQt6.QtGui import QFont, QFontMetrics

from core import i18n
from core.argyll_runner import ArgyllRunner
from core.settings import AppSettings
from ui.widgets import _LABELS_PROP

tr = i18n.tr


class _Runner:
    is_running = False

    def run(self, *a, **k):
        raise AssertionError("no Argyll in this test")


def _settings(tmp_path):
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    return s


def _reserved(btn) -> list:
    return list(btn.property(_LABELS_PROP) or [])


def _needs(btn, text: str) -> int:
    font = btn.font()
    if font.capitalization() == QFont.Capitalization.AllUppercase:
        text = text.upper()
    return QFontMetrics(font).horizontalAdvance(text) + 2


@pytest.fixture
def scanner(qapp, tmp_path):
    from ui.dialogs.scanin_dialog import ScannerProfileDialog
    d = ScannerProfileDialog(_Runner(), _settings(tmp_path))
    yield d
    d.hide()
    d.deleteLater()


@pytest.mark.parametrize("attr, labels", [
    ("_auto_align_btn", ("Auto align", "Undo auto align")),
    ("_popout_btn", ("⤢ Pop out", "⤢ Dock back")),
    ("_run_btn", ("Build printer profile",
                  "Build profile with scanner or camera")),
    ("_install_btn", ("Install profile", "Install Profile Anyway")),
    ("_reveal_btn", ("Reveal profile", "Reveal folder")),
])
def test_the_scanner_windows_changing_buttons_reserve_their_labels(
        scanner, attr, labels):
    btn = getattr(scanner, attr)
    for label in labels:
        assert tr(label) in _reserved(btn), (attr, label)


def test_undo_auto_align_fits_at_the_minimum_width(scanner, qapp):
    scanner.show()
    qapp.processEvents()
    scanner.resize(scanner.minimumWidth(), scanner.height())
    qapp.processEvents()
    btn = scanner._auto_align_btn
    assert btn.minimumWidth() >= _needs(btn, tr("Undo auto align"))


def test_the_measure_start_button_reserves_continue(qapp, tmp_path):
    from ui.tabs.tab_measure import TabMeasure
    s = _settings(tmp_path)
    s.set("custom_output_path", str(tmp_path / "out"))
    tab = TabMeasure(ArgyllRunner(s), s)
    try:
        got = _reserved(tab._start_btn)
        assert tr("Start Measurement") in got
        assert tr("Continue Measurement") in got
    finally:
        tab.deleteLater()


def test_the_credits_button_reserves_both_words(qapp, tmp_path):
    from ui.dialogs.settings_dialog import SettingsDialog
    d = SettingsDialog(_settings(tmp_path), None)
    try:
        btn = getattr(d, "_credits_btn", None)
        assert btn is not None
        got = _reserved(btn)
        assert tr("Show each set's credit") in got
        assert tr("Hide each set's credit") in got
    finally:
        d.deleteLater()
