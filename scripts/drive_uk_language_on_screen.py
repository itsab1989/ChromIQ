#!/usr/bin/env python3
"""Ukrainian on screen: the real app, in a real window, in `uk`.

Issue #198, LackiUA's contributed catalogue. This driver exists to answer the
one question no catalogue test can: does Ukrainian FIT. Ukrainian is longer than
English almost everywhere, and `test_i18n.py::test_short_labels_stay_compact`
only sees strings under 25 characters, while `test_translation_integrity.py`
only measures the parameter column. Everything else is a picture.

    export CHROMIQ_SETTINGS_FILE=/tmp/chromiq-uk/settings.ini
    export CHROMIQ_PRESETS_DIR=/tmp/chromiq-uk/presets
    python scripts/drive_uk_language_on_screen.py <out-dir> [uk|en]

SANDBOX THE SETTINGS FIRST, and the presets with them. This builds a real
`AppSettings`; unsandboxed it writes into the store the owner works in every
day. The script refuses to start without both.

NO `widget.grab()` ANYWHERE IN HERE. A grab is a render, not a photograph: it
cannot show a native title bar, a popup, compositing, or a control the window
server clipped. Every picture goes through `onscreen_capture.capture_window`,
twice, and is kept only when the two frames are pixel-identical.

The clipping measurement is deliberately NOT "does the text look cut off". It
asks each widget for the advance width of the string it is painting and compares
it with the width it was given, so a finding is a number and not an impression.
"""
from __future__ import annotations

import json
import os
import sys
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

if not os.environ.get("CHROMIQ_SETTINGS_FILE"):
    raise SystemExit("CHROMIQ_SETTINGS_FILE is not set: refusing to write "
                     "into the owner's real preferences.")
if not os.environ.get("CHROMIQ_PRESETS_DIR"):
    raise SystemExit("CHROMIQ_PRESETS_DIR is not set: refusing to write into "
                     "the owner's real presets.")
if os.environ.get("QT_QPA_PLATFORM"):
    raise SystemExit("QT_QPA_PLATFORM is set. This driver opens a WINDOW; "
                     "offscreen is the test suite's business, not a driver's.")

from PyQt6.QtCore import QTimer                                    # noqa: E402
from PyQt6.QtWidgets import (QApplication, QCheckBox, QComboBox,   # noqa: E402
                             QGroupBox, QLabel, QPushButton,
                             QRadioButton, QTabWidget, QToolButton)

from onscreen_capture import capture_window, session_is_locked     # noqa: E402

OUT = Path(".")
RAISED: list = []


def rec_hook() -> None:
    prev = sys.excepthook

    def hook(t, e, tb):
        RAISED.append({"type": t.__name__, "msg": str(e),
                       "tb": "".join(traceback.format_tb(tb))[-400:]})
        prev(t, e, tb)
    sys.excepthook = hook


def pump(app, ms=300):
    end = time.monotonic() + ms / 1000.0
    while time.monotonic() < end:
        app.processEvents()
        time.sleep(0.01)


def _same(a: Path, b: Path, tol: int = 8) -> bool:
    import numpy as np
    from PIL import Image
    x = np.asarray(Image.open(a).convert("RGB")).astype(int)
    y = np.asarray(Image.open(b).convert("RGB")).astype(int)
    return x.shape == y.shape and bool((np.abs(x - y).sum(2) > tol).sum() == 0)


def photo(app, win, tag: str) -> dict:
    """Two frames, kept only when they are pixel-identical."""
    why = ""
    for _ in range(3):
        pump(app, 650)
        ok1, w1 = capture_window(win, OUT / f"{tag}-1.png")
        pump(app, 650)
        ok2, w2 = capture_window(win, OUT / f"{tag}-2.png")
        if ok1 and ok2 and _same(OUT / f"{tag}-1.png", OUT / f"{tag}-2.png"):
            return {"taken": True, "identical": True, "file": f"{tag}-1.png"}
        why = why or w1 or w2
    return {"taken": False, "identical": False, "why": why}


# ----------------------------------------------------------------------
# Clipping, measured rather than eyeballed
# ----------------------------------------------------------------------
#
# Qt paints an elided label as "Автоматичне вирівню…" and a button simply cuts
# its text off at the frame. Both look like a design choice in a screenshot, so
# the question is asked of the font metrics instead: how wide is the string the
# widget is painting, and how much room does the widget have for it.

_SLACK = {QPushButton: 18, QToolButton: 14, QCheckBox: 26,
          QRadioButton: 26, QLabel: 4, QComboBox: 34, QGroupBox: 18}


def clipped(root, seen: set | None = None) -> list[dict]:
    seen = set() if seen is None else seen
    out = []
    for cls, slack in _SLACK.items():
        for w in root.findChildren(cls):
            if id(w) in seen or not w.isVisible():
                continue
            seen.add(id(w))
            text = (w.currentText() if isinstance(w, QComboBox)
                    else (w.title() if isinstance(w, QGroupBox) else w.text()))
            text = (text or "").replace("&", "")
            if not text or "\n" in text or len(text) < 3:
                continue
            if isinstance(w, QLabel) and w.wordWrap():
                continue          # a wrapped label is allowed to be long
            need = w.fontMetrics().horizontalAdvance(text) + slack
            have = w.width()
            if need > have:
                out.append({"class": cls.__name__, "text": text,
                            "need_px": need, "have_px": have,
                            "over_px": need - have,
                            "object": w.objectName()})
    return sorted(out, key=lambda d: -d["over_px"])


def tab_texts(tabs: QTabWidget) -> list[dict]:
    """A tab bar clips silently and is the first thing a long language breaks."""
    bar = tabs.tabBar()
    out = []
    for i in range(tabs.count()):
        text = tabs.tabText(i).replace("&", "")
        need = bar.fontMetrics().horizontalAdvance(text)
        out.append({"index": i, "text": text, "need_px": need,
                    "have_px": bar.tabRect(i).width(),
                    "over_px": need + 24 - bar.tabRect(i).width()})
    return out


def main() -> int:
    global OUT
    OUT = Path(sys.argv[1]).resolve()
    OUT.mkdir(parents=True, exist_ok=True)
    lang = sys.argv[2] if len(sys.argv) > 2 else "uk"

    rec_hook()
    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("ChromIQ")
    from ui.styles import WinButtonLayoutStyle
    app.setStyle(WinButtonLayoutStyle("Fusion"))      # what main.py ships
    # A BLINKING CARET IS NOT A DIFFERENCE WORTH REPORTING. The two-frame
    # rule exists to catch a window that is still painting; a text cursor
    # flashing in an empty field defeats it on every attempt and would
    # have cost this round its main-window photograph. Stopping the flash
    # hides nothing: the caret is drawn solid instead of blinking.
    app.setCursorFlashTime(0)

    from core.settings import AppSettings
    settings = AppSettings()
    res: dict = {"lang": lang,
                 "settings_store": settings._qs.fileName(),
                 "locked_at_start": session_is_locked(),
                 "platform_plugin": app.platformName()}
    assert "/tmp/chromiq-uk" in res["settings_store"], res["settings_store"]

    settings.set("appearance", "light")
    settings.set("language", lang)
    from core import i18n
    i18n.set_language(lang)
    # WHAT main.py DOES, LINE 199. Qt's own dialog buttons (OK, Cancel,
    # Close) come from qtbase_<code>.qm, not from ChromIQ's catalogue, and
    # a driver that skips this photographs English buttons in a window the
    # shipped app renders in Ukrainian. PyQt6 does ship qtbase_uk.qm.
    i18n.install_qt_translator(app)
    res["current_language"] = i18n.current_language()
    res["language_name"] = dict(i18n.available_languages()).get(lang)

    from ui.theme import apply_appearance
    apply_appearance(app, None, "light")

    # ---- 1. the main window -------------------------------------------
    from ui.main_window import MainWindow
    win = MainWindow(settings)
    apply_appearance(app, win, "light")
    win.resize(1360, 900)
    win.show()
    pump(app, 2500)
    res["main_window"] = {
        "title": win.windowTitle(),
        "size": [win.width(), win.height()],
        "photo": photo(app, win, "01-main-window"),
        "tabs": tab_texts(win.findChild(QTabWidget)),
        "clipped": clipped(win)[:40],
    }

    # ---- 2. every tab, because each carries different labels ----------
    tabs = win.findChild(QTabWidget)
    per_tab = []
    for i in range(tabs.count()):
        tabs.setCurrentIndex(i)
        pump(app, 1200)
        name = tabs.tabText(i).replace("&", "")
        bad = clipped(tabs.widget(i))
        per_tab.append({"index": i, "tab": name, "clipped": bad[:25],
                        "clipped_total": len(bad),
                        "photo": photo(app, win, f"02-tab{i}")})
    res["tabs"] = per_tab

    # ---- 2b. WHY the Guided ⓘ buttons are cut, measured in a REAL window
    # Offscreen this panel reports numbers that do not match the photograph
    # (the plugin says so itself: "does not support propagateSizeHints"), so
    # the question is asked here, where the window server has actually laid
    # the thing out.
    from PyQt6.QtWidgets import QScrollArea, QWidget
    from ui.tooltip_button import TooltipButton
    tabs.setCurrentIndex(0)
    pump(app, 1500)
    inner = win.findChild(QTabWidget).widget(0)
    combo = None
    for c in win.findChildren(QComboBox):
        if c.isVisible() and any("i1Pro" in c.itemText(i)
                                 for i in range(c.count())):
            combo = c
            break
    if combo is not None:
        panel = combo.parentWidget()
        sa = panel
        while sa is not None and not isinstance(sa, QScrollArea):
            sa = sa.parentWidget()
        icons = []
        for b in win.findChildren(TooltipButton):
            if b.isVisible() and b.parentWidget() is panel:
                icons.append({
                    "y": b.y(), "right": b.x() + b.width(),
                    "panel_w": panel.width(),
                    "viewport_w": sa.viewport().width() if sa else None,
                    "off_by": (b.x() + b.width()) -
                              (sa.viewport().width() if sa else 0),
                })
        res["guided_panel"] = {
            "panel_width": panel.width(),
            "panel_minimumWidth": panel.minimumWidth(),
            "panel_minimumSizeHint": panel.minimumSizeHint().width(),
            "panel_sizeHint": panel.sizeHint().width(),
            "viewport_width": sa.viewport().width() if sa else None,
            "scrollarea_class": type(sa).__name__ if sa else None,
            "scrollarea_width": sa.width() if sa else None,
            "widget_is_panel": (sa.widget() is panel) if sa else None,
            "widgetResizable": sa.widgetResizable() if sa else None,
            "hbar_policy": (sa.horizontalScrollBarPolicy().name if sa else None),
            "vbar_visible": sa.verticalScrollBar().isVisible() if sa else None,
            "vbar_width": sa.verticalScrollBar().width() if sa else None,
            "combo_class": type(combo).__name__,
            "combo_min": combo.minimumSizeHint().width(),
            "combo_width": combo.width(),
            "scroll_widget": (type(sa.widget()).__name__ if sa else None),
            "scroll_widget_w": (sa.widget().width() if sa else None),
            "scroll_widget_min": (sa.widget().minimumSizeHint().width()
                                  if sa else None),
            "who_demands_the_width": sorted(
                [{"cls": type(w).__name__,
                  "min": w.minimumSizeHint().width(),
                  "minW": w.minimumWidth(),
                  "w": w.width(),
                  "text": ((w.title() if hasattr(w, "title") else
                            (w.text() if hasattr(w, "text") else ""))or"")[:40]}
                 for w in (sa.widget().findChildren(QWidget) if sa else [])
                 if w.isVisible()
                 and max(w.minimumSizeHint().width(), w.minimumWidth()) > 500],
                key=lambda d: -max(d["min"], d["minW"]))[:6],
            "icons_off_the_edge": [i for i in icons if i["off_by"] > 0],
            "icons_total": len(icons),
        }

    # ---- 3. the Settings dialog, showing Ukrainian in the list --------
    from ui.dialogs.settings_dialog import SettingsDialog
    dlg = SettingsDialog(settings, win)
    dlg.show()
    dlg.raise_()
    pump(app, 2000)
    combo_items, picked = [], None
    for c in dlg.findChildren(QComboBox):
        items = [c.itemText(i) for i in range(c.count())]
        if any("Deutsch" in t or "English" in t for t in items):
            combo_items, picked = items, c.currentText()
            break
    res["settings_dialog"] = {
        "language_items": combo_items,
        "current": picked,
        "ukrainian_listed": any("Українська" in t for t in combo_items),
        "size": [dlg.width(), dlg.height()],
        "photo": photo(app, dlg, "03-settings-language"),
        "clipped": clipped(dlg)[:40],
    }
    dlg.close()
    pump(app, 600)

    # ---- 4. the parameter rows + a real tooltip -----------------------
    # The parameter NAME column is the one `test_translation_integrity.py`
    # measures in pixels; this photographs what those numbers mean.
    tabs.setCurrentIndex(0)
    pump(app, 1200)
    from ui.parameter_widget import ParameterWidget
    rows = win.findChildren(ParameterWidget)
    over = []
    for r in rows:
        for lbl in r.findChildren(QLabel):
            t = (lbl.text() or "").replace("&", "")
            if not t or "\n" in t or lbl.wordWrap():
                continue
            need = lbl.fontMetrics().horizontalAdvance(t)
            if need > lbl.width():
                over.append({"text": t, "need_px": need,
                             "have_px": lbl.width(),
                             "over_px": need - lbl.width()})
    res["parameter_rows"] = {
        "rows_found": len(rows),
        "labels_overflowing": sorted(over, key=lambda d: -d["over_px"])[:40],
        "labels_overflowing_total": len(over),
    }

    # A real tooltip window, not the tooltip STRING. Expert rows are collapsed,
    # so this takes the first visible row that has one.
    from ui.tooltip_button import TooltipButton, _InfoDialog
    tips = [b for b in win.findChildren(TooltipButton) if b.isVisible()]
    res["tooltip_buttons_visible"] = len(tips)
    if tips:
        shown: list = []

        def grab_tip():
            box = next((w for w in QApplication.topLevelWidgets()
                        if isinstance(w, _InfoDialog) and w.isVisible()), None)
            if box is None:
                QTimer.singleShot(250, grab_tip)
                return
            shown.append([t for t in ((lb.text() or "").strip()
                                      for lb in box.findChildren(QLabel)) if t])
            res["tooltip"] = {"photo": photo(app, box, "04-parameter-tooltip"),
                              "clipped": clipped(box)[:20]}
            for b in box.findChildren(QPushButton):
                if b.isVisible():
                    b.click()
                    return
            box.accept()

        QTimer.singleShot(400, grab_tip)
        tips[0].click()
        pump(app, 6000)
        res["tooltip_text"] = shown

    # ---- 5. the Report limits window ----------------------------------
    from ui.dialogs.thresholds_dialog import ThresholdsDialog
    th = ThresholdsDialog(settings, win)
    th.show()
    th.raise_()
    pump(app, 2500)
    screen = th.screen() or QApplication.primaryScreen()
    res["report_limits"] = {
        "title": th.windowTitle(),
        "size": [th.width(), th.height()],
        "fits_screen": th.height() <= screen.availableGeometry().height(),
        "photo": photo(app, th, "05-report-limits"),
        "clipped": clipped(th)[:40],
    }
    th.close()
    pump(app, 600)

    # ---- 6. a help card ------------------------------------------------
    from ui.dialogs.welcome_dialog import WelcomeDialog
    wd = WelcomeDialog(settings, None, "light")
    wd.resize(1180, 900)
    wd.show()
    wd.raise_()
    pump(app, 2000)
    res["help_menu"] = {"photo": photo(app, wd, "06-help-menu"),
                        "clipped": clipped(wd)[:40]}
    wd._on_card_clicked("first_profile")
    pump(app, 2000)
    res["help_card_first_profile"] = {
        "photo": photo(app, wd, "07-help-card-first-profile"),
        "clipped": clipped(wd)[:40],
    }
    wd._on_card_clicked("glossary")
    pump(app, 2000)
    res["help_card_glossary"] = {
        "photo": photo(app, wd, "08-help-card-glossary"),
        "clipped": clipped(wd)[:40],
    }
    wd.close()
    pump(app, 600)

    res["exceptions"] = RAISED
    (OUT / f"result-{lang}.json").write_text(
        json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: v for k, v in res.items()
                      if k not in ("tabs", "tooltip_text")},
                     ensure_ascii=False, indent=1)[:4000])
    win.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
