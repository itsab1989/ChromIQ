#!/usr/bin/env python3
"""Reproduce Basti's log: Create Chart in Guided, SpectroScan, 4x6, Generate.

He reports the app leaves Guided for Manual on its own when the chart is
generated, with ColorMunki apparently still selected in Manual. This drives the
real window through exactly that sequence and photographs the tab before and
after, reporting the mode and BOTH instrument controls at every step.

    python scripts/drive_guided_ss_4x6.py [paper]

Basti's preferences are copied to a throwaway .ini; nothing of his is touched.
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
from PyQt6.QtWidgets import QApplication, QMessageBox           # noqa: E402

from core.resource_path import resource_path                    # noqa: E402

REAL_PLIST = Path.home() / "Library/Preferences/com.chromiq.ChromIQ.plist"


def pump(app, ms: int) -> None:
    end = time.time() + ms / 1000.0
    while time.time() < end:
        app.processEvents()
        time.sleep(0.01)


def state(tab) -> str:
    g = tab._instr_combo.currentData()
    gl = tab._instr_combo.currentText()
    m = tab._manual_get("printtarg", "-i", None)
    return (f"mode={tab._current_mode():7s}  guided instrument={g!r} ({gl})  "
            f"manual printtarg -i={m!r}")


def main() -> int:
    paper = sys.argv[1] if len(sys.argv) > 1 else "4x6"
    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("ChromIQ")
    for fp in resource_path("assets/fonts").glob("*.ttf"):
        QFontDatabase.addApplicationFont(str(fp))
    from ui.styles import APP_STYLESHEET
    app.setStyleSheet(APP_STYLESHEET)

    sandbox = Path(tempfile.mkdtemp(prefix="chromiq_guided46_"))
    shots = sandbox / "shots"
    shots.mkdir()
    from core.settings import AppSettings
    src = QSettings(str(REAL_PLIST), QSettings.Format.NativeFormat)
    dst = QSettings(str(sandbox / "settings.ini"), QSettings.Format.IniFormat)
    for k in src.allKeys():
        dst.setValue(k, src.value(k))
    dst.sync()
    settings = AppSettings()
    settings._qs = dst
    settings.set("custom_output_path", str(sandbox / "ChromIQ"))

    shown: list = []
    for m in ("warning", "critical", "information", "question"):
        setattr(QMessageBox, m, staticmethod(
            lambda *a, **k: (shown.append(a[1:3]), 0)[1]))

    from ui.main_window import MainWindow
    win = MainWindow(settings)
    win.resize(1600, 1050)
    win.show()
    pump(app, 3000)
    win._tabs.setCurrentWidget(win._tab_chart)
    tab = win._tab_chart
    pump(app, 1200)

    # A NORMAL USER'S SEQUENCE, in order, nothing skipped.
    tab._switch_mode("guided")
    pump(app, 600)
    print("1. opened Guided          :", state(tab))
    tab._target_name_edit.setText("HexProbe") if hasattr(tab, "_target_name_edit") else None
    tab.grab().save(str(shots / "1_guided_opened.png"))

    i = tab._instr_combo.findData("SS")
    print(f"   SpectroScan at index {i} of {tab._instr_combo.count()}")
    tab._instr_combo.setCurrentIndex(i)
    pump(app, 800)
    print("2. instrument = SpectroScan:", state(tab))
    tab.grab().save(str(shots / "2_spectroscan.png"))

    papers = [tab._paper_combo.itemData(k) or tab._paper_combo.itemText(k)
              for k in range(tab._paper_combo.count())]
    hit = [k for k, p in enumerate(papers) if paper.lower() in str(p).lower()]
    print(f"   paper choices: {papers}")
    if not hit:
        print(f"   !! no paper matching {paper!r}")
        return 2
    tab._paper_combo.setCurrentIndex(hit[0])
    pump(app, 800)
    print(f"3. paper = {papers[hit[0]]!r:12s}:", state(tab))
    tab.grab().save(str(shots / "3_paper_4x6.png"))

    before = state(tab)
    tab._on_generate()
    for _ in range(60):                       # generation is a QProcess chain
        pump(app, 1000)
        if tab._generate_btn.isEnabled():
            break
    pump(app, 2500)
    after = state(tab)
    print("4. after Generate         :", after)
    tab.grab().save(str(shots / "4_after_generate.png"))

    print()
    print("BEFORE:", before)
    print("AFTER :", after)
    moved = tab._current_mode() != "guided"
    print(f"\nmode changed by itself: {moved}")
    if shown:
        print("dialogs raised:", [str(s)[:110] for s in shown])
    print("shots:", shots)
    return 1 if moved else 0


if __name__ == "__main__":
    raise SystemExit(main())
