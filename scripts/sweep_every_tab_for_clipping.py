#!/usr/bin/env python3
"""Every tab, every heading, every button: what is CLIPPED, and by how much.

Sebastian found the Print Chart button row by using the app for a minute, after
a round of photographs had missed it entirely. So this asks the whole window
instead of the places somebody thought to look, and it asks the widgets rather
than a screenshot: for each control it measures the widest LINE of the text the
widget will actually paint (capitalisation and all, because ChromIQ's buttons
are painted in Menlo caps) against the room that widget has.

    export CHROMIQ_SETTINGS_FILE=/tmp/chromiq-uk/settings.ini
    export CHROMIQ_PRESETS_DIR=/tmp/chromiq-uk/presets
    python scripts/sweep_every_tab_for_clipping.py <out-dir> [uk|en|de]

ON SCREEN, in a real window: `QT_QPA_PLATFORM` is refused, because the offscreen
plugin does not propagate size hints and has already reported this panel as
fitting when the photograph showed it cut.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

if not os.environ.get("CHROMIQ_SETTINGS_FILE"):
    raise SystemExit("CHROMIQ_SETTINGS_FILE is not set.")
if not os.environ.get("CHROMIQ_PRESETS_DIR"):
    raise SystemExit("CHROMIQ_PRESETS_DIR is not set.")
if os.environ.get("QT_QPA_PLATFORM"):
    raise SystemExit("QT_QPA_PLATFORM is set; this driver opens a window.")

from PyQt6.QtGui import QFont, QFontMetrics                       # noqa: E402
from PyQt6.QtWidgets import (QApplication, QCheckBox, QLabel,     # noqa: E402
                             QPushButton, QRadioButton, QTabWidget,
                             QToolButton)


def pump(app, ms=300):
    end = time.monotonic() + ms / 1000.0
    while time.monotonic() < end:
        app.processEvents()
        time.sleep(0.01)


def _painted(w) -> str:
    """The string the widget will really draw, capitalisation applied."""
    text = (w.text() or "").replace("&&", "\x00").replace("&", "").replace(
        "\x00", "&")
    if w.font().capitalization() == QFont.Capitalization.AllUppercase:
        text = text.upper()
    return text


def _room(w) -> int:
    """Width available for TEXT, after the control's own furniture."""
    from PyQt6.QtWidgets import QStyle, QStyleOptionButton
    if isinstance(w, (QCheckBox, QRadioButton)):
        try:
            opt = QStyleOptionButton()
            opt.initFrom(w)
            sub = (QStyle.SubElement.SE_CheckBoxContents
                   if isinstance(w, QCheckBox)
                   else QStyle.SubElement.SE_RadioButtonContents)
            r = w.style().subElementRect(sub, opt, w)
            if r.width() > 0:
                return r.width()
        except Exception:      # noqa: BLE001
            pass
        return w.width() - 24
    if isinstance(w, QPushButton):
        # The frame eats a few px each side; the same constant the fitter uses
        # for "comfortable" chrome would over-report, so this is deliberately
        # the tight one: it only flags text that genuinely does not fit.
        return w.width() - 12
    return w.width()


def survey(root, where: str) -> list[dict]:
    out = []
    for cls in (QPushButton, QToolButton, QCheckBox, QRadioButton, QLabel):
        for w in root.findChildren(cls):
            if not w.isVisible() or w.width() <= 0:
                continue
            if isinstance(w, QLabel) and w.wordWrap():
                continue          # allowed to be long: it wraps
            if type(w).__name__ == "WrappingCheckBox":
                continue          # ditto: its label wraps onto a second line
            text = _painted(w)
            if not text or len(text.strip()) < 2:
                continue
            if "<" in text and ">" in text:
                continue          # rich text: advance() would measure markup
            fm = QFontMetrics(w.font())
            need = max(fm.horizontalAdvance(line) for line in text.split("\n"))
            room = _room(w)
            # A BUTTON THAT IS NARROWER THAN ITS OWN FITTED MINIMUM is being
            # squeezed by its row, and that is the shape Sebastian found on
            # Print Chart: `fit_button_width` had already written the width the
            # label needs into `minimumWidth`, and the layout handed it less.
            # Measuring only "text wider than the frame" missed all four,
            # because the frame estimate is generous by design.
            squeezed = (isinstance(w, QPushButton) and w.minimumWidth()
                        and w.width() < w.minimumWidth())
            if need > room or squeezed:
                out.append({
                    "where": where, "class": cls.__name__,
                    "text": text, "lines": text.count("\n") + 1,
                    "need_px": need, "room_px": room,
                    "over_px": max(need - room,
                                   (w.minimumWidth() - w.width())
                                   if squeezed else 0),
                    "squeezed_below_its_minimum": bool(squeezed),
                    "min_px": w.minimumWidth() if isinstance(w, QPushButton) else None,
                    "width_px": w.width(),
                    "object": w.objectName(),
                })
    return sorted(out, key=lambda d: -d["over_px"])


def main() -> int:
    out_dir = Path(sys.argv[1]).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    lang = sys.argv[2] if len(sys.argv) > 2 else "uk"

    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("ChromIQ")
    from ui.styles import WinButtonLayoutStyle
    app.setStyle(WinButtonLayoutStyle("Fusion"))
    app.setCursorFlashTime(0)

    from core.settings import AppSettings
    settings = AppSettings()
    assert "/tmp/chromiq-uk" in settings._qs.fileName()
    settings.set("appearance", "light")
    settings.set("language", lang)
    from core import i18n
    i18n.set_language(lang)
    i18n.install_qt_translator(app)
    from ui.theme import apply_appearance
    apply_appearance(app, None, "light")

    from ui.main_window import MainWindow
    win = MainWindow(settings)
    apply_appearance(app, win, "light")
    win.resize(1360, 900)
    win.show()
    pump(app, 2500)

    tabs = win.findChild(QTabWidget)
    found: list[dict] = []
    for i in range(tabs.count()):
        tabs.setCurrentIndex(i)
        pump(app, 1600)
        name = tabs.tabText(i).replace("&", "")
        found += survey(tabs.widget(i), f"tab{i} {name}")
    res = {"lang": lang, "window": [win.width(), win.height()],
           "clipped": found, "total": len(found)}
    (out_dir / f"sweep-{lang}.json").write_text(
        json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{lang}: {len(found)} clipped control(s)")
    for d in found:
        print(f"  +{d['over_px']:4}px  {d['where']:28} {d['class']:12} "
              f"{d['text']!r}")
    win.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
