"""Preferences ▸ Measurement ▸ "Show the “expected · measured” label on the
chart preview" (Basti, 2026-10-23: "add an option to Preferences measure tab
to show the measured vs expected overlay ... this one on by default").

The option is the LABEL (the legend chip), not the split drawing of the
patches, which stays with the Measure tab's "Each patch shows"
(`TiffPreview.set_overlay_mode`). Off, nothing brings the chip back: not the
hover, not the pause note giving way and coming back.
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QRect  # noqa: E402
from PyQt6.QtGui import QColor, QImage, QPixmap  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def test_on_by_default_so_everybody_keeps_it():
    from core.settings import DEFAULTS
    assert DEFAULTS["measure_preview_legend"] is True


def _preview():
    from ui.tiff_preview import TiffPreview
    pv = TiffPreview()
    pv.resize(500, 700)
    img = QImage(600, 900, QImage.Format.Format_RGB32)
    img.fill(QColor(255, 255, 255))
    pv._pixmap = QPixmap.fromImage(img)
    return pv


def test_off_the_chip_is_neither_drawn_nor_placed(app, monkeypatch):
    pv = _preview()
    drawn = []
    from ui import see_through
    monkeypatch.setattr(see_through, "paint_panel",
                        lambda *a, **k: drawn.append(1))
    pv.set_legend_enabled(False)
    assert not pv.legend_enabled()
    pv._legend_paint = (10, 10, 100, 20, "expected ◤ · measured ◢")
    pv._legend_opacity = 1.0
    from PyQt6.QtGui import QPainter
    canvas = QPixmap(200, 200)
    p = QPainter(canvas)
    pv._paint_legend_chip(p)
    p.end()
    assert drawn == []
    pv.set_legend_enabled(True)
    canvas = QPixmap(200, 200)
    p = QPainter(canvas)
    pv._legend_paint = (10, 10, 100, 20, "expected ◤ · measured ◢")
    pv._paint_legend_chip(p)
    p.end()
    assert drawn == [1]


def test_the_pause_note_never_brings_a_switched_off_chip_back(app):
    pv = _preview()
    pv.set_legend_enabled(False)
    pv.set_legend_suppressed(True)       # the note fades in: chip gives way
    pv.set_legend_suppressed(False)      # the note goes: chip "comes back"
    if pv._legend_fade is not None:
        pv._legend_fade.setCurrentTime(pv._legend_fade.duration())
    pv._legend_paint = (10, 10, 100, 20, "x")
    from ui import see_through
    calls = []
    real = see_through.paint_panel
    see_through.paint_panel = lambda *a, **k: calls.append(1)
    try:
        from PyQt6.QtGui import QPainter
        canvas = QPixmap(200, 200)
        p = QPainter(canvas)
        pv._paint_legend_chip(p)
        p.end()
    finally:
        see_through.paint_panel = real
    assert calls == []


def test_back_on_while_the_note_is_up_it_waits_for_the_note(app):
    pv = _preview()
    pv.set_legend_enabled(False)
    pv.set_legend_suppressed(True)
    pv.set_legend_enabled(True)
    assert pv._legend_opacity == 0.0 and pv._legend_hidden
    pv2 = _preview()
    pv2.set_legend_enabled(False)
    pv2.set_legend_enabled(True)
    assert pv2._legend_opacity == 1.0 and not pv2._legend_hidden


def test_switching_it_leaves_the_patch_drawing_alone(app):
    pv = _preview()
    pv.set_overlay_mode("measured")
    pv.set_legend_enabled(False)
    assert pv.overlay_mode() == "measured"
    pv.set_legend_enabled(True)
    assert pv.overlay_mode() == "measured"


def test_off_hovering_where_it_was_does_nothing(app):
    pv = _preview()
    pv._legend_rect = QRect(0, 0, 100, 20)
    pv.set_legend_enabled(False)
    pv._repaint_label()
    assert pv._legend_rect is None


def test_preferences_has_the_option_and_saves_it(app, tmp_path, monkeypatch):
    from core.settings import AppSettings
    from ui.dialogs.settings_dialog import SettingsDialog, preview_legend_help
    s = AppSettings()
    s.set("measure_preview_legend", True)
    dlg = SettingsDialog(s)
    assert dlg._preview_legend_cb.isChecked()
    dlg._preview_legend_cb.setChecked(False)
    dlg._save_and_close()
    assert s.get("measure_preview_legend") is False
    s.set("measure_preview_legend", True)
    dlg.deleteLater()
    help_ = preview_legend_help()
    for words in ("Each patch shows", "**Default:** on.", "at once",
                  "Only whether that label is shown"):
        assert words in help_, words


def test_it_applies_when_preferences_closes():
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent
    mw = (root / "ui/main_window.py").read_text(encoding="utf-8")
    assert "self._tab_measure.refresh_preview_legend()" in mw
    tm = (root / "ui/tabs/tab_measure.py").read_text(encoding="utf-8")
    assert tm.count('self._settings.get("measure_preview_legend", True)') == 2
