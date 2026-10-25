"""Preferences ▸ Printing (Basti, 2026-10-25).

Every option that changes how a chart is printed moved from General to a tab
of its own, between Measurement and Sounds, and "ChromIQ-style refinement
process" and "Enable measurement averaging" moved from General to Measurement,
below the "expected · measured" label and above the misread checks. Layout
only: every key, default and behaviour stays as it was.

Each platform keeps exactly the print options it had on General:

| platform | on Printing |
|---|---|
| macOS   | Use default macOS printer dialog; Exact-size PDF fallback (ChromIQ printing); Confirm print settings before printing; Edge this printer does not print |
| Windows | Use default Windows printer dialog; Confirm print settings before printing; Edge this printer does not print |
| Linux   | Confirm print settings before printing; Edge this printer does not print |

The platform is forced here, because only macOS can be opened on screen.
"""
from __future__ import annotations

import json
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PyQt6")

from PyQt6.QtCore import QSettings              # noqa: E402
from PyQt6.QtWidgets import (QApplication, QCheckBox, QGroupBox,  # noqa: E402
                             QWidget)


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


PLATFORMS = {
    # name: (is_macos, is_windows, route switch, labels expected on Printing)
    "macos": (True, False, True, [
        "Use default macOS printer dialog",
        "Exact-size PDF fallback (ChromIQ printing)",
        "Confirm print settings before printing"]),
    "windows": (False, True, True, [
        "Use default Windows printer dialog",
        "Confirm print settings before printing"]),
    "linux": (False, False, False, [
        "Confirm print settings before printing"]),
}
ALL_PRINT_LABELS = {
    "Use default macOS printer dialog", "Use default Windows printer dialog",
    "Exact-size PDF fallback (ChromIQ printing)",
    "Confirm print settings before printing"}


def _force(monkeypatch, name):
    from ui.dialogs import settings_dialog as sd
    mac, win, route, _ = PLATFORMS[name]
    monkeypatch.setattr(sd, "is_macos", lambda: mac)
    monkeypatch.setattr(sd, "is_windows", lambda: win)
    monkeypatch.setattr(sd, "print_route_switch_supported", lambda: route)
    return sd


def _settings(tmp_path):
    from core.settings import AppSettings
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "prefs.ini"), QSettings.Format.IniFormat)
    return s


def _page(dlg, title):
    tabs = dlg._tabs
    for i in range(tabs.count()):
        if tabs.tabText(i) == title:
            return tabs.widget(i)
    raise AssertionError(f"no {title!r} tab: "
                         f"{[tabs.tabText(i) for i in range(tabs.count())]}")


def _shown_checks(dlg, page):
    # visible on its page (a tab that is not current hides its whole page)
    return [c.text() for c in page.findChildren(QCheckBox)
            if c.isVisibleTo(page)]


def test_printing_sits_between_measurement_and_sounds(qapp, tmp_path,
                                                      monkeypatch):
    sd = _force(monkeypatch, "macos")
    dlg = sd.SettingsDialog(_settings(tmp_path), None)
    try:
        names = [dlg._tabs.tabText(i) for i in range(dlg._tabs.count())]
        i = names.index("Printing")
        assert names[i - 1:i + 2] == ["Measurement", "Printing", "Sounds"], names
    finally:
        dlg.deleteLater()


@pytest.mark.parametrize("platform", list(PLATFORMS))
def test_each_platform_shows_its_own_print_options_on_printing_only(
        qapp, tmp_path, monkeypatch, platform):
    sd = _force(monkeypatch, platform)
    dlg = sd.SettingsDialog(_settings(tmp_path), None)
    try:
        dlg.show()
        printing = _page(dlg, "Printing")
        general = _page(dlg, "General")
        expected = PLATFORMS[platform][3]
        shown = _shown_checks(dlg, printing)
        assert shown == expected, (platform, shown)
        assert not ALL_PRINT_LABELS & set(_shown_checks(dlg, general)), platform
        titles = [g.title() for g in printing.findChildren(QGroupBox)]
        assert "Edge this printer does not print" in titles
        assert not any(g.title() == "Edge this printer does not print"
                       for g in general.findChildren(QGroupBox))
        assert dlg._edge_spin.isVisibleTo(printing)
        # Nothing a platform does not use floats over the dialog either.
        for w in (dlg._native_print_check, dlg._pdf_fallback_check,
                  dlg._confirm_print_check):
            if w.text() not in expected:
                assert not w.isVisible() and w.isHidden(), w.text()
    finally:
        dlg.reject()
        dlg.deleteLater()


def test_refinement_and_averaging_moved_to_measurement_in_their_place(
        qapp, tmp_path, monkeypatch):
    sd = _force(monkeypatch, "macos")
    dlg = sd.SettingsDialog(_settings(tmp_path), None)
    try:
        dlg.show()
        meas = _page(dlg, "Measurement")
        general = _page(dlg, "General")
        for c in (dlg._chromiq_refine_check, dlg._averaging_check):
            assert meas.isAncestorOf(c), c.text()
            assert not general.isAncestorOf(c), c.text()
            assert c.isVisibleTo(meas)

        def y(w: QWidget) -> int:
            return w.mapTo(meas, w.rect().topLeft()).y()
        assert (y(dlg._preview_legend_cb) < y(dlg._chromiq_refine_check)
                < y(dlg._averaging_check) < y(dlg._misread_group))
    finally:
        dlg.reject()
        dlg.deleteLater()


@pytest.mark.parametrize("platform", list(PLATFORMS))
def test_every_moved_option_reads_and_writes_its_own_key(qapp, tmp_path,
                                                         monkeypatch, platform):
    """A non-default value goes in, survives OK, a reopen and a restart (a
    fresh settings object on the same file), and a change made on the new
    tab is written to the same key it always was."""
    from core.settings import AppSettings
    from workflow import printer_edges as PE
    sd = _force(monkeypatch, platform)
    ini = tmp_path / "prefs.ini"

    def fresh():
        s = AppSettings()
        s._qs = QSettings(str(ini), QSettings.Format.IniFormat)
        return s

    s = fresh()
    flipped = {"use_native_print_dialog": True, "pdf_print_fallback": False,
               "confirm_before_printing": False, "chromiq_refinement": True,
               "averaging_enabled": True}
    for k, v in flipped.items():
        s.set(k, v)
    s.set(PE.OVERRIDE_KEY, json.dumps({"Test Printer": 3.5}))

    def boxes(d):
        return {"use_native_print_dialog": d._native_print_check,
                "pdf_print_fallback": d._pdf_fallback_check,
                "confirm_before_printing": d._confirm_print_check,
                "chromiq_refinement": d._chromiq_refine_check,
                "averaging_enabled": d._averaging_check}

    dlg = sd.SettingsDialog(s, None)
    checks = boxes(dlg)
    for k, c in checks.items():
        assert c.isChecked() is flipped[k], k
    dlg._save_and_close()
    dlg.deleteLater()

    for settings in (s, fresh()):              # reopen, then "restart"
        for k, v in flipped.items():
            assert bool(settings.get(k)) is v, k
        assert json.loads(settings.get(PE.OVERRIDE_KEY)) == {"Test Printer": 3.5}

    # A change made on the new tabs lands on the old keys.
    s2 = fresh()
    dlg = sd.SettingsDialog(s2, None)
    for c in boxes(dlg).values():
        c.setChecked(not c.isChecked())
    i = dlg._edge_printer_combo.findData("Test Printer")
    dlg._edge_printer_combo.setCurrentIndex(i)
    dlg._edge_spin.setValue(5.0)
    dlg._save_and_close()
    dlg.deleteLater()
    s3 = fresh()
    for k, v in flipped.items():
        assert bool(s3.get(k)) is (not v), k
    assert json.loads(s3.get(PE.OVERRIDE_KEY)) == {"Test Printer": 5.0}
