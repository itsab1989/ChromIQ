"""4.3.45: on Windows, "switch the printer driver's colour management off" is
asked before the print dialog opens for a chart (M-PRINT-WIN-DRIVER-CM).

A tester printed through the Windows print dialog with the Canon driver's
colour management on and lost about 30 % of the gamut; the note on the Print
Chart tab had been passed over. Pinned here, with the print dialog patched
(no real dialog ever opens, nothing is printed):

1. on Windows the reminder comes BEFORE the dialog; Cancel opens no dialog,
   prints nothing and writes no print record; "Open the print dialog" goes on;
2. "Don't show this again" is stored and then nothing is asked;
3. macOS and Linux never ask (the same route, `is_windows()` false);
4. the window's text is the catalogue's, names Canon, Epson and HP by the
   makers' own menu words, and has no em dash.
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from tests.test_205_windows_direct_print import (  # noqa: E402
    _FakeDialog, _FakePainter, _rgb_tiff, dialog_route)  # noqa: F401


@pytest.fixture
def route(dialog_route, monkeypatch):
    """The Windows dialog route with the reminder REAL, its answer scripted,
    and every QPrintDialog.exec counted (the fake never opens anything)."""
    from ui.tabs import tab_print as tp
    tab, events = dialog_route
    monkeypatch.delattr(tab, "_confirm_driver_colour_off")   # the real one
    opened = []
    real_exec = _FakeDialog.exec
    monkeypatch.setattr(_FakeDialog, "exec",
                        lambda self: opened.append(1) or real_exec(self))
    answers = {"button": "go", "hide": False, "shown": []}

    def fake_box_exec(box):
        answers["shown"].append((box.text(), box.informativeText()))
        if answers["hide"] and box.checkBox() is not None:
            box.checkBox().setChecked(True)
        want = (tp.tr("Open the print dialog") if answers["button"] == "go"
                else None)
        for b in box.buttons():
            if (want is not None and b.text() == want) or (
                    want is None
                    and box.buttonRole(b) == box.ButtonRole.RejectRole):
                b.click()
                break
        return 0
    from PyQt6.QtWidgets import QMessageBox
    monkeypatch.setattr(QMessageBox, "exec", fake_box_exec)
    return tab, events, opened, answers


def _windows(monkeypatch, on: bool):
    from ui.tabs import tab_print as tp
    monkeypatch.setattr(tp, "is_windows", lambda: on)


def test_cancel_opens_no_dialog_and_prints_nothing(route, tmp_path,
                                                   monkeypatch):
    tab, events, opened, answers = route
    _windows(monkeypatch, True)
    answers["button"] = "cancel"
    tab._print_native_qt([(_rgb_tiff(tmp_path / "c.tif"), 0)])
    assert len(answers["shown"]) == 1
    assert opened == [] and _FakePainter.draws == []
    assert events == [("record", False)]


def test_open_goes_on_to_the_dialog_and_asks_every_time(route, tmp_path,
                                                        monkeypatch):
    tab, events, opened, answers = route
    _windows(monkeypatch, True)
    tiff = _rgb_tiff(tmp_path / "c.tif")
    tab._print_native_qt([(tiff, 0)])
    assert len(answers["shown"]) == 1 and opened == [1]
    assert events == [("record", True)]
    tab._print_native_qt([(tiff, 0)])
    assert len(answers["shown"]) == 2 and opened == [1, 1]
    assert tab._settings.get("print_win_hide_driver_cm_confirm") is False


def test_dont_show_again_is_stored_and_kept(route, tmp_path, monkeypatch):
    tab, events, opened, answers = route
    _windows(monkeypatch, True)
    answers["hide"] = True
    tiff = _rgb_tiff(tmp_path / "c.tif")
    tab._print_native_qt([(tiff, 0)])
    assert tab._settings.get("print_win_hide_driver_cm_confirm") is True
    tab._print_native_qt([(tiff, 0)])
    assert len(answers["shown"]) == 1 and opened == [1, 1]


def test_cancel_with_the_box_ticked_stores_nothing(route, tmp_path,
                                                  monkeypatch):
    tab, events, opened, answers = route
    _windows(monkeypatch, True)
    answers.update(button="cancel", hide=True)
    tab._print_native_qt([(_rgb_tiff(tmp_path / "c.tif"), 0)])
    assert tab._settings.get("print_win_hide_driver_cm_confirm") is False


def test_macos_and_linux_never_ask(route, tmp_path, monkeypatch):
    tab, events, opened, answers = route
    _windows(monkeypatch, False)
    tab._print_native_qt([(_rgb_tiff(tmp_path / "c.tif"), 0)])
    assert answers["shown"] == [] and opened == [1]


def test_a_chart_refused_before_the_dialog_is_not_asked_about(
        route, tmp_path, monkeypatch):
    from tests.test_205_windows_direct_print import _cmyk_tiff
    tab, events, opened, answers = route
    _windows(monkeypatch, True)
    tab._print_native_qt([(_cmyk_tiff(tmp_path / "k.tif"), 0)])
    assert answers["shown"] == [] and opened == []


def test_the_text_says_where_the_switch_is(route, tmp_path, monkeypatch):
    tab, events, opened, answers = route
    _windows(monkeypatch, True)
    answers["button"] = "cancel"
    tab._print_native_qt([(_rgb_tiff(tmp_path / "c.tif"), 0)])
    (head, body), = answers["shown"]
    from workflow import measurement_messages as MM
    assert (head, body) == MM.M_PRINT_WIN_DRIVER_CM.render()
    # the driver's own words in straight quotes (they are not ChromIQ's
    # controls: tests/test_a_quoted_control_names_the_control_the_reader_has)
    for words in ('"Color/Intensity"', '"Matching"', '"Color Correction"',
                  '"None"', '"Off (No Color Adjustment)"',
                  '"Application Managed Colors"',
                  "“Use default Windows printer dialog”"):
        assert words in body, words
    assert "—" not in head + body


def test_the_default_is_to_ask():
    from core.settings import DEFAULTS
    assert DEFAULTS["print_win_hide_driver_cm_confirm"] is False
