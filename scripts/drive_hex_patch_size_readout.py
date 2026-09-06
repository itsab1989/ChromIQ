#!/usr/bin/env python3
"""Drive the REAL ChromIQ window for Knut's hexagonal "Patch size (mm)" report.

    "In the Chart layout information frame, the 'Patch size (mm)' has the
    correct width according to the Patch width measurement in the 'Measured
    from Preview' frame, but the height part is wrong and too small. For a
    hexagonal patch, the height top-tip to bottom-tip is always larger than the
    patch width, but the 'Patch size (mm)' says 11.3 x 9.78."
                                                    (Knut, 2026-09-06, B8-80)

Builds a REAL honeycomb chart at exactly his numbers (a hexagon 11.3 mm wide
whose slot is 9.78 mm) and reads the two frames back off the screen, from the
labels themselves, so the same script tells the truth on the tree before the
fix and on the tree after it.

Basti's preferences are copied to a throwaway .ini and his ChromIQ root is
replaced by a sandbox. Nothing of his is touched.

    CHROMIQ_SETTINGS_FILE=/tmp/chromiq-co.ini \
        python scripts/drive_hex_patch_size_readout.py [before|after]
"""
from __future__ import annotations

import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

try:
    import PyQt6.QtWebEngineWidgets  # noqa: F401
except ImportError:
    pass

from PyQt6.QtCore import QSettings                              # noqa: E402
from PyQt6.QtGui import QFontDatabase                           # noqa: E402
from PyQt6.QtWidgets import QApplication, QDialog, QMessageBox  # noqa: E402

from core.resource_path import resource_path                    # noqa: E402

REAL_PLIST = Path.home() / "Library/Preferences/com.chromiq.ChromIQ.plist"
SHOTS = Path.home() / "Desktop" / "beta 9" / "hex-patch-size"
PATCH_W_MM, PATCH_H_MM = 11.3, 9.78          # Knut's own two numbers


def pump(app, ms):
    end = time.monotonic() + ms / 1000.0
    while time.monotonic() < end:
        app.processEvents()
        time.sleep(0.01)


def shot(w, name):
    SHOTS.mkdir(parents=True, exist_ok=True)
    p = SHOTS / f"{name}.png"
    w.grab().save(str(p))
    print(f"    saved {p}")
    return p


def run(app, tag: str) -> int:
    from core.settings import AppSettings

    sandbox = Path(tempfile.mkdtemp(prefix="chromiq-hexsize-"))
    src = QSettings(str(REAL_PLIST), QSettings.Format.NativeFormat)
    dst = QSettings(str(sandbox / "settings.ini"), QSettings.Format.IniFormat)
    for k in src.allKeys():
        dst.setValue(k, src.value(k))
    dst.sync()
    settings = AppSettings()
    settings._qs = dst
    work = sandbox / "ChromIQ"
    work.mkdir()
    settings.set("custom_output_path", str(work))
    settings.set("restore_last_session", False)
    print(f"    sandbox: {sandbox}")

    QDialog.exec = lambda self: 1                      # type: ignore[assignment]
    for m in ("warning", "critical", "information", "question"):
        setattr(QMessageBox, m, staticmethod(lambda *a, **k: 0))

    from ui.main_window import MainWindow
    from ui.tabs.tab_chart import TabChart
    TabChart._confirm_displacing_results = lambda self, *a, **k: True
    TabChart._prompt_target_name = lambda self, *a, **k: "hex-patch-size"

    win = MainWindow(settings)
    win.show()
    pump(app, 2500)
    win._tabs.setCurrentWidget(win._tab_chart)
    tab = win._tab_chart
    pump(app, 600)

    tab._user_switch_mode("manual")
    pump(app, 900)
    pnl = tab._manual_layout_panel

    i = pnl.instr.findData("CR30")
    assert i >= 0, "the CR30 is not offered"
    pnl.instr.setCurrentIndex(i)
    pump(app, 700)
    j = pnl.mode.findData("hex")
    assert j >= 0, "this instrument offers no hexagonal shape"
    pnl.mode.setCurrentIndex(j)
    pump(app, 700)
    pnl.patch_x.setValue(PATCH_W_MM)
    pnl.patch_y.setValue(PATCH_H_MM)
    pump(app, 700)
    print(f"    set on screen: {pnl.instr.currentText()}, "
          f"{pnl.mode.currentText()}, patch {pnl.patch_x.value()} × "
          f"{pnl.patch_y.value()} mm")

    tab._target_name_edit.setText("hex-patch-size")
    pump(app, 300)
    tab._on_generate()
    for _ in range(120):
        pump(app, 500)
        if getattr(tab, "_margin_ti2", None):
            break
    ti2 = getattr(tab, "_margin_ti2", None)
    if not ti2:
        print("    -> the chart did not build. STOP.")
        win.close()
        return 1
    pump(app, 2500)
    print(f"    generated: {ti2}")

    # Read the two frames off the SCREEN, from their own labels.
    info = tab._layout_info_panel
    rows = {}
    for key, lbl in info._actual_labels.items():
        name = (info._row_names[key].text()
                if hasattr(info, "_row_names") else key)
        vis = (not info._row_names[key].isHidden()
               if hasattr(info, "_row_names") else True)
        if vis:
            rows[name] = lbl.text()
    print("\n    Chart layout information (on screen):")
    for k, v in rows.items():
        print(f"        {k:26s} {v}")

    mi = tab._margin_panel if hasattr(tab, "_margin_panel") else None
    mi = mi or getattr(tab, "_margin_inspector", None)
    if mi is not None and hasattr(mi, "_strip_mm"):
        print(f"\n    Measured from Preview: Patch width = "
              f"{mi._strip_mm.text()} mm")

    shot(info, f"{tag}-chart-layout-information")
    if mi is not None:
        shot(mi, f"{tag}-measured-from-preview")
    shot(win, f"{tag}-window")
    win.close()
    pump(app, 400)
    return 0


def main() -> int:
    tag = sys.argv[1] if len(sys.argv) > 1 else "after"
    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("ChromIQ")
    for fp in resource_path("assets/fonts").glob("*.ttf"):
        QFontDatabase.addApplicationFont(str(fp))
    from ui.styles import APP_STYLESHEET
    app.setStyleSheet(APP_STYLESHEET)
    rc = run(app, tag)
    print(f"\nscreenshots in {SHOTS}")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
