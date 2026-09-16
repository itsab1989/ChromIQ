#!/usr/bin/env python3
"""Challenge my own three fixes in a real window. Assume each one broke something.

Two things the first drive never touched, both of which the change introduced:

C1  The warning's OTHER fallback branch. `{fallback}` was a `+` before, and a
    `+` cannot fail. `.format()` can: a missing or misspelled placeholder in
    any of the twelve catalogues, and the reader gets a literal `{fallback}` or
    a KeyError. Only the AirPrint branch was photographed; the PDF branch runs
    on `pdf_print_fallback`, which nobody had turned on.

C2  A runtime `detail` carrying BRACES. The averaging window's reason comes
    from ArgyllCMS's stderr, which this code has never constrained. `+` never
    looked at it; `.format()` is now applied to the surrounding sentence, so
    the question is whether a `{` arriving in the VALUE can reach the format
    machinery. It cannot, and that is worth proving rather than asserting.

C3  Every catalogue, not just German: `.format(fallback=…)` and
    `.format(detail=…)` are run against all twelve translations of both keys.

Run::

    CHROMIQ_SETTINGS_FILE=/tmp/chromiq-txt.ini \
    CHROMIQ_PRESETS_DIR=/tmp/chromiq-txt-presets \
        python scripts/txt_round_challenge.py <out-dir>

NEVER offscreen.
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
from PyQt6.QtCore import QTimer                                # noqa: E402
from PyQt6.QtWidgets import QApplication, QDialog, QLabel      # noqa: E402

sys.path.insert(0, str(ROOT / "scripts"))                      # noqa: E402
from onscreen_capture import capture_window                    # noqa: E402


def pump(app, ms=350):
    end = time.monotonic() + ms / 1000.0
    while time.monotonic() < end:
        app.processEvents()
        time.sleep(0.01)


WARNING_KEY = (
    "⚠  Verify that all print settings above match the media you are printing "
    "on.\n\nWrong media type or quality settings will cause incorrect ink "
    "laydown and invalid colour measurements. Allow pigment inks to dry fully "
    "before measuring (at least 1 h; 24 h for best accuracy).\n\nColour "
    "management is disabled automatically. ChromIQ converts the chart to "
    "PostScript and sends it via lp, bypassing ColorSync entirely. {fallback}"
)
AVERAGE_KEY = (
    "<b>The reads could not be averaged.</b><br><br>{detail}<br><br>Your "
    "individual reads are still saved, you can continue from the Build "
    "Profile tab using one of them."
)


def main() -> int:
    assert os.environ.get("CHROMIQ_SETTINGS_FILE"), "SANDBOX THE SETTINGS FIRST"
    assert os.environ.get("CHROMIQ_PRESETS_DIR"), "SANDBOX THE PRESETS FIRST"
    assert os.environ.get("QT_QPA_PLATFORM") != "offscreen"

    out = Path(sys.argv[1]).resolve()
    out.mkdir(parents=True, exist_ok=True)
    r: dict = {"C1": {}, "C2": {}, "C3": {}}

    # ---- C3, before any window: every catalogue formats -----------------
    for path in sorted((ROOT / "data" / "i18n").glob("*.json")):
        code = path.stem
        cat = json.loads(path.read_text(encoding="utf-8"))
        row = {}
        for name, key, kwargs in (("warning", WARNING_KEY, {"fallback": "X"}),
                                  ("average", AVERAGE_KEY, {"detail": "X"})):
            v = cat.get(key)
            if v is None:
                row[name] = "MISSING FROM THE CATALOGUE"
                continue
            try:
                got = v.format(**kwargs)
                row[name] = "ok" if "X" in got else "the placeholder is GONE"
            except Exception as exc:                         # noqa: BLE001
                row[name] = f"{type(exc).__name__}: {exc}"
        r["C3"][code] = row

    from core.settings import AppSettings
    from core.i18n import set_language, install_qt_translator
    from ui.styles import WinButtonLayoutStyle

    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("ChromIQ")
    app.setStyle(WinButtonLayoutStyle("Fusion"))

    settings = AppSettings()
    sandbox_out = Path(os.environ["CHROMIQ_SETTINGS_FILE"]).parent / "txt-projects"
    sandbox_out.mkdir(parents=True, exist_ok=True)
    settings.set("custom_output_path", str(sandbox_out))
    settings.set("language", "en")
    set_language("en")
    install_qt_translator(app)

    from ui.main_window import MainWindow
    win = MainWindow(settings)
    win.resize(1500, 1000)
    win.show()
    pump(app, 1500)

    tp = win._tab_print
    win._tabs.setCurrentWidget(tp)
    pump(app, 600)

    # ---- C1: BOTH fallback branches, on screen -------------------------
    settings.set("use_native_print_dialog", False)
    for label, pdf in (("airprint", False), ("pdf", True)):
        settings.set("pdf_print_fallback", pdf)
        tp._set_native_mode(False)
        pump(app, 500)
        text = tp._warn_lbl.text()
        r["C1"][label] = {
            "literal_placeholder_left": "{fallback}" in text,
            "tail": text[-170:],
        }
    ok, why = capture_window(win, out / "challenge-1-pdf-fallback.png")
    r["C1"]["capture"] = [ok, why]

    # ---- C2: a reason carrying braces, and angle brackets --------------
    tm = win._tab_measure
    nasty = "Error - {not a placeholder} & <b>90</b> sets vs {15}"
    shot = {}

    def _shoot():
        for w in app.topLevelWidgets():
            if isinstance(w, QDialog) and w.isVisible():
                ok2, why2 = capture_window(
                    w, out / "challenge-2-braces-in-the-reason.png")
                bodies = [lb.text() for lb in w.findChildren(QLabel)
                          if lb.text().strip()]
                shot["body"] = max(bodies, key=len) if bodies else ""
                shot["capture"] = [ok2, why2]
                w.accept()
                return
        shot["capture"] = [False, "no dialog was up"]

    QTimer.singleShot(1200, _shoot)
    try:
        tm._show_average_failed_dialog(nasty)
        shot["raised"] = True
    except Exception as exc:                                  # noqa: BLE001
        shot["raised"] = f"{type(exc).__name__}: {exc}"
    pump(app, 500)
    r["C2"] = {
        "raised_without_error": shot.get("raised"),
        "the_braces_survived": "{not a placeholder}" in shot.get("body", ""),
        "body": shot.get("body", ""),
        "capture": shot.get("capture", [False, "the timer never fired"]),
    }

    for w in app.topLevelWidgets():
        if isinstance(w, QDialog) and w.isVisible():
            w.reject()
    win.close()
    pump(app, 400)

    (out / "challenge-result.json").write_text(
        json.dumps(r, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(r, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
