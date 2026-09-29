#!/usr/bin/env python3
"""Photograph the three fixed strings in a REAL window, English and German.

Run::

    CHROMIQ_SETTINGS_FILE=/tmp/chromiq-txt.ini \
    CHROMIQ_PRESETS_DIR=/tmp/chromiq-txt-presets \
        python scripts/txt_round_onscreen_proof.py <lang> <out-dir>

NEVER QT_QPA_PLATFORM=offscreen. This is a driver, not the suite: a
`widget.grab()` cannot show a tooltip or a modal, which is exactly what is
being proved here.

Every window is closed before the script returns, and nothing calls `exec()`
without a timer already scheduled to photograph and close it.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
try:
    import PyQt6.QtWebEngineWidgets  # noqa: F401
except ImportError:
    pass
from PyQt6.QtCore import QPoint, QTimer                        # noqa: E402
from PyQt6.QtWidgets import QApplication, QDialog, QToolTip    # noqa: E402

sys.path.insert(0, str(ROOT / "scripts"))                      # noqa: E402
from onscreen_capture import (                                  # noqa: E402
    _grab_window_id, capture_window, session_is_locked,
)


def tip_window_id(tipwin) -> "int | None":
    """The CGWindowID of a TOOLTIP, found by its geometry.

    `onscreen_capture.window_id_for` deliberately picks the BIGGEST window this
    process owns and says so in as many words: "a Qt app also owns tiny helper
    windows (tooltips, shadows)". That is right for a main window and useless
    here, so the tooltip is matched by its own bounds instead. Still the
    window's OWN BUFFER through Quartz, never a rectangle of the screen.

    `capture_window` cannot be used on a tooltip at all: it calls `raise_()`
    and `activateWindow()`, and Qt destroys the tip label when it loses the
    hover, so the first attempt died with "wrapped C/C++ object of type QLabel
    has been deleted" before any picture was taken.
    """
    try:
        import Quartz
    except ImportError:
        return None
    import os as _os
    g = tipwin.frameGeometry()
    infos = Quartz.CGWindowListCopyWindowInfo(
        Quartz.kCGWindowListOptionAll
        | Quartz.kCGWindowListExcludeDesktopElements,
        Quartz.kCGNullWindowID) or []
    best, best_d = None, 1e9
    for w in infos:
        if int(w.get("kCGWindowOwnerPID", -1)) != _os.getpid():
            continue
        b = w["kCGWindowBounds"]
        d = abs(b["Width"] - g.width()) + abs(b["Height"] - g.height())
        if d < best_d:
            best, best_d = w, d
    # A tolerance, not a match: the window server's bounds carry the shadow.
    if best is None or best_d > 40:
        return None
    return int(best["kCGWindowNumber"])


def pump(app, ms=350):
    end = time.monotonic() + ms / 1000.0
    while time.monotonic() < end:
        app.processEvents()
        time.sleep(0.01)


def main() -> int:
    assert os.environ.get("CHROMIQ_SETTINGS_FILE"), "SANDBOX THE SETTINGS FIRST"
    assert os.environ.get("CHROMIQ_PRESETS_DIR"), "SANDBOX THE PRESETS FIRST"
    assert os.environ.get("QT_QPA_PLATFORM") != "offscreen", \
        "a driver does not run offscreen"

    lang = sys.argv[1]
    out = Path(sys.argv[2]).resolve()
    out.mkdir(parents=True, exist_ok=True)
    result: dict = {"language": lang, "captures": {}, "text": {},
                    "locked_at_start": session_is_locked()}

    from core.settings import AppSettings
    from core.i18n import set_language, install_qt_translator, tr

    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("ChromIQ")
    # The app's own style, so the picture is of what ships.
    from ui.styles import WinButtonLayoutStyle
    app.setStyle(WinButtonLayoutStyle("Fusion"))

    settings = AppSettings()
    # PIN THE OUTPUT PATH inside the sandbox. A sandboxed .ini is NOT a
    # sandboxed output root: `custom_output_path` starts unset in a fresh one
    # and the app then writes into the real ~/ChromIQ.
    sandbox_out = Path(os.environ["CHROMIQ_SETTINGS_FILE"]).parent / "txt-projects"
    sandbox_out.mkdir(parents=True, exist_ok=True)
    settings.set("custom_output_path", str(sandbox_out))
    settings.set("language", lang)
    set_language(lang)
    install_qt_translator(app)
    result["output_root"] = str(sandbox_out)

    from ui.main_window import MainWindow
    win = MainWindow(settings)
    win.resize(1500, 1000)
    win.show()
    pump(app, 1500)

    # ---- 1. the Print Chart tab's "Load image (TIFF)" tooltip ----------
    tp = win._tab_print
    win._tabs.setCurrentWidget(tp)
    pump(app, 800)

    btn = tp._load_image_btn
    tip = btn.toolTip()
    result["text"]["load_image_tooltip"] = tip
    # Force the tooltip: a driver cannot hover, and a tooltip is a window of
    # its own, so it is found among the top-level widgets and photographed
    # there rather than inside the main window's buffer.
    pos = btn.mapToGlobal(QPoint(btn.width() // 2, btn.height()))
    QToolTip.showText(pos, tip, btn)
    pump(app, 900)
    tipwin = None
    for w in app.topLevelWidgets():
        if w.isVisible() and w.metaObject().className() == "QTipLabel":
            tipwin = w
            break
    name = f"{lang}-1-load-image-tooltip.png"
    if tipwin is None:
        result["captures"][name] = \
            [False, "no QTipLabel window was up when the capture was taken"]
    else:
        wid = tip_window_id(tipwin)
        if wid is None:
            result["captures"][name] = \
                [False, "the tooltip has no window id the server will admit"]
        else:
            ok = _grab_window_id(wid, out / name)
            result["captures"][name] = [
                ok, "" if ok else "the window server returned no image"]
            result["tooltip_size"] = [tipwin.width(), tipwin.height()]
    QToolTip.hideText()
    pump(app, 300)

    # …and the whole tab, so the picture shows the button in its real place.
    ok, why = capture_window(win, out / f"{lang}-2-print-chart-tab.png")
    result["captures"][f"{lang}-2-print-chart-tab.png"] = [ok, why]

    # ---- 2. the lp-path print warning ---------------------------------
    # Force the lp branch (the native dialog is the macOS default).
    settings.set("use_native_print_dialog", False)
    tp._set_native_mode(False)
    pump(app, 500)
    result["text"]["print_warning"] = tp._warn_lbl.text()

    # ---- 3. the averaging-failed window -------------------------------
    tm = win._tab_measure
    detail = tr("see the output log above.")
    shot = {}

    def _shoot():
        for w in app.topLevelWidgets():
            if isinstance(w, QDialog) and w.isVisible():
                ok, why = capture_window(
                    w, out / f"{lang}-3-averaging-failed.png")
                shot["r"] = [ok, why]
                shot["title"] = w.windowTitle()
                from PyQt6.QtWidgets import QLabel
                bodies = [lb.text() for lb in w.findChildren(QLabel)
                          if lb.text().strip()]
                shot["body"] = max(bodies, key=len) if bodies else ""
                w.accept()
                return
        shot["r"] = [False, "no dialog was up 1.2 s after it was raised"]

    QTimer.singleShot(1200, _shoot)
    tm._show_average_failed_dialog(detail)     # modal; the timer closes it
    pump(app, 500)
    result["captures"][f"{lang}-3-averaging-failed.png"] = shot.get(
        "r", [False, "the timer never fired"])
    result["text"]["averaging_title"] = shot.get("title", "")
    result["text"]["averaging_body"] = shot.get("body", "")

    # NOTHING LEFT OPEN.
    for w in app.topLevelWidgets():
        if isinstance(w, QDialog) and w.isVisible():
            w.reject()
    win.close()
    pump(app, 400)

    (out / f"{lang}-result.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
