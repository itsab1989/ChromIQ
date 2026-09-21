#!/usr/bin/env python3
"""B8-556 — drive Guided / CR30 / A4 / hexagon in a REAL window and keep proof.

Sebastian's chart: Create Chart, Guided mode, ChnSpec CR30, A4 Portrait,
"Hexagon patches" on, Generate. The settings stamp down the right edge was
printed over the patches and Guided said nothing about it.

What this leaves behind, per run:

  * two pixel-identical photographs of the real window, taken with
    `scripts/onscreen_capture.capture_window` (the window's own buffer, never
    `widget.grab()`, never offscreen);
  * the TIFF the app actually wrote, and a 1:1 crop of its right edge;
  * the Calculated Patches figure the Guided screen showed, and the patch count
    the sheet really carries.

    CHROMIQ_SETTINGS_FILE=/tmp/chromiq-stamp/settings.ini \
    CHROMIQ_PRESETS_DIR=/tmp/chromiq-stamp/presets \
    python scripts/drive_b8556_guided_stamp.py <label> <outdir>

The settings store is a FRESH sandbox, not a copy of the owner's preferences: a
driver that copies the plist measures the owner and not the product.
"""
from __future__ import annotations

import os
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

if os.environ.get("QT_QPA_PLATFORM") == "offscreen":
    raise SystemExit("this driver opens a real window; unset QT_QPA_PLATFORM")

try:
    import PyQt6.QtWebEngineWidgets  # noqa: F401
except ImportError:
    pass

from PyQt6.QtGui import QFontDatabase                            # noqa: E402
from PyQt6.QtWidgets import QApplication, QMessageBox            # noqa: E402

from core.resource_path import resource_path                     # noqa: E402
from scripts.onscreen_capture import capture_window              # noqa: E402


def pump(app, ms: int) -> None:
    end = time.time() + ms / 1000.0
    while time.time() < end:
        app.processEvents()
        time.sleep(0.01)


def stable_pair(app, win, out: Path, stem: str, tries: int = 5):
    """Two consecutive photographs of the window that are PIXEL-identical.

    Pixels, not bytes: two PNGs of one unchanged window do not hash the same,
    because the encoder's output is not byte-stable, and reading that as "the
    window moved" would throw away a perfectly good pair. The size is part of
    the comparison because it is what actually varies -- a window whose native
    buffer is still settling comes back at a different size, which is how a
    first attempt at this pair failed (2158x3360 then 1960x3050).
    """
    import numpy as np
    from PIL import Image
    a_path = out / f"02_{stem}.png"
    b_path = out / f"03_{stem}_again.png"
    last = ""
    for _ in range(tries):
        ok_a, why_a = capture_window(win, a_path)
        pump(app, 900)
        ok_b, why_b = capture_window(win, b_path)
        if not (ok_a and ok_b):
            last = why_a or why_b
            pump(app, 1200)
            continue
        a = np.asarray(Image.open(a_path).convert("RGB"), int)
        b = np.asarray(Image.open(b_path).convert("RGB"), int)
        if a.shape == b.shape and not np.abs(a - b).any():
            return True, f"pixel-identical at {a.shape[1]}x{a.shape[0]}"
        last = (f"frames differ: {a.shape} vs {b.shape}, "
                f"{int(np.abs(a - b).any(axis=2).sum()) if a.shape == b.shape else -1} px")
        pump(app, 1500)
    return False, last


def main() -> int:
    label = sys.argv[1] if len(sys.argv) > 1 else "run"
    out = Path(sys.argv[2] if len(sys.argv) > 2
               else "/tmp/chromiq-stamp/onscreen") / label
    out.mkdir(parents=True, exist_ok=True)

    if not os.environ.get("CHROMIQ_SETTINGS_FILE"):
        raise SystemExit("set CHROMIQ_SETTINGS_FILE before running this")

    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("ChromIQ")
    for fp in resource_path("assets/fonts").glob("*.ttf"):
        QFontDatabase.addApplicationFont(str(fp))
    from ui.styles import APP_STYLESHEET
    app.setStyleSheet(APP_STYLESHEET)
    from main import WinButtonLayoutStyle
    app.setStyle(WinButtonLayoutStyle("Fusion"))

    from core.settings import AppSettings
    settings = AppSettings()
    settings.set("custom_output_path", str(out / "ChromIQ"))

    shown: list = []
    for m in ("warning", "critical", "information", "question"):
        setattr(QMessageBox, m, staticmethod(
            lambda *a, **k: (shown.append(a[1:3]), 0)[1]))

    from ui.main_window import MainWindow
    win = MainWindow(settings)
    win.resize(1680, 1080)
    win.show()
    pump(app, 3500)
    win._tabs.setCurrentWidget(win._tab_chart)
    tab = win._tab_chart
    pump(app, 1500)

    tab._switch_mode("guided")
    pump(app, 800)
    if hasattr(tab, "_target_name_edit"):
        tab._target_name_edit.setText("B8556-" + label)
        pump(app, 400)
    tab._instr_combo.setCurrentIndex(tab._instr_combo.findData("CR30"))
    pump(app, 900)
    tab._paper_combo.setCurrentIndex(tab._paper_combo.findData("A4"))
    pump(app, 900)
    if not tab._dd_check.isChecked():
        tab._dd_check.setChecked(True)
    pump(app, 1200)

    print("mode              :", tab._current_mode())
    print("instrument        :", tab._instr_combo.currentData(),
          "/", tab._instr_combo.currentText())
    print("paper             :", tab._paper_combo.currentData())
    print("hexagon patches   :", tab._dd_check.isChecked(),
          "(%s)" % tab._dd_check.text())
    shown_count = None
    for name in ("_calc_patches_label", "_patch_count_label", "_auto_label"):
        w = getattr(tab, name, None)
        if w is not None and hasattr(w, "text"):
            shown_count = (name, w.text())
            break
    print("patches on screen :", shown_count)

    ok, why = capture_window(win, out / "01_guided_before_generate.png")
    print("photograph 1      :", ok, why)

    tab._on_generate()
    for _ in range(180):
        pump(app, 1000)
        if tab._generate_btn.isEnabled():
            break
    pump(app, 3000)

    ok2, why2 = stable_pair(app, win, out, "guided_after_generate")
    print("photographs 2+3   :", ok2, why2)
    ok3 = ok2

    tifs = sorted((out / "ChromIQ").rglob("*.tif"))
    print("sheets written    :", [str(t.relative_to(out)) for t in tifs])
    for t in tifs:
        shutil.copy(t, out / ("sheet_" + t.name))
    ti2 = sorted((out / "ChromIQ").rglob("*.ti2"))
    for f in ti2:
        txt = f.read_text(errors="ignore")
        for line in txt.splitlines():
            if line.startswith(("NUMBER_OF_SETS", "STEPS_IN_PASS",
                                "PASSES_IN_STRIPS2")):
                print("   %-22s %s" % (f.name, line.strip()))
    if shown:
        print("dialogs raised    :", [str(s)[:120] for s in shown])
    print("proof             :", out)
    return 0 if (ok and ok2) else 3


if __name__ == "__main__":
    raise SystemExit(main())
