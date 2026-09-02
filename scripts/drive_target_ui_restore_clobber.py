#!/usr/bin/env python3
"""Basti's report, reproduced: Guided + SpectroScan + 4x6 + Generate lands in
Manual with ColorMunki selected.

It needs a target that has ALREADY stored a different Create Chart state — his
"ChromIQ Test Chart" holds mode=manual, guided={instrument: CM, paper: A4} — so
a clean sandbox cannot show it. This copies the small manifest files of a real
project (project.json + each run's meta.json, never the bitmaps) into a
throwaway working folder and drives the sequence against that.

    python scripts/drive_target_ui_restore_clobber.py [project-name]

Basti's preferences are copied to a throwaway .ini; nothing of his is touched.
"""
from __future__ import annotations

import json
import shutil
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


def clone_manifests(src: Path, dst: Path) -> None:
    """Only the small JSON manifests — the state that decides this, and nothing
    that could be mistaken for the user's own measurements."""
    dst.mkdir(parents=True, exist_ok=True)
    for f in ("project.json",):
        if (src / f).is_file():
            shutil.copy(src / f, dst / f)
    for meta in sorted(src.glob("runs/*/meta.json")):
        out = dst / "runs" / meta.parent.name
        out.mkdir(parents=True, exist_ok=True)
        shutil.copy(meta, out / "meta.json")


def main() -> int:
    name = sys.argv[1] if len(sys.argv) > 1 else "ChromIQ-Test-Chart"
    real = Path.home() / "ChromIQ" / name
    if not real.is_dir():
        print(f"no such project: {real}")
        return 2

    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("ChromIQ")
    for fp in resource_path("assets/fonts").glob("*.ttf"):
        QFontDatabase.addApplicationFont(str(fp))
    from ui.styles import APP_STYLESHEET
    app.setStyleSheet(APP_STYLESHEET)

    sandbox = Path(tempfile.mkdtemp(prefix="chromiq_uiclobber_"))
    work = sandbox / "ChromIQ"
    clone_manifests(real, work / name)
    stored = json.loads((work / name / "runs/run1/meta.json").read_text(encoding="utf-8"))
    ui = stored.get("create_chart_ui") or {}
    print(f"the target's STORED state: mode={ui.get('mode')!r} "
          f"guided.instrument={(ui.get('guided') or {}).get('instrument')!r} "
          f"guided.paper={(ui.get('guided') or {}).get('paper')!r}\n")

    from core.settings import AppSettings
    src = QSettings(str(REAL_PLIST), QSettings.Format.NativeFormat)
    dst = QSettings(str(sandbox / "settings.ini"), QSettings.Format.IniFormat)
    for k in src.allKeys():
        dst.setValue(k, src.value(k))
    dst.sync()
    settings = AppSettings()
    settings._qs = dst
    settings.set("custom_output_path", str(work))

    for m in ("warning", "critical", "information", "question"):
        setattr(QMessageBox, m, staticmethod(lambda *a, **k: 0))

    from ui.main_window import MainWindow
    win = MainWindow(settings)
    win.resize(1600, 1050)
    win.show()
    pump(app, 3000)
    win._tabs.setCurrentWidget(win._tab_chart)
    tab = win._tab_chart
    pump(app, 1000)

    def state(tag):
        print(f"{tag:26s} mode={tab._current_mode():7s} "
              f"guided instrument={tab._instr_combo.currentData()!r} "
              f"paper={tab._paper_combo.currentData()!r} "
              f"manual -i={tab._manual_get('printtarg', '-i', None)!r}")

    tab._switch_mode("guided")
    pump(app, 600)
    # The project he had open, typed as he would type it.
    for attr in ("_target_name_edit", "_manual_target_name_edit"):
        w = getattr(tab, attr, None)
        if w is not None:
            w.setText("ChromIQ Test Chart")
    pump(app, 800)
    state("1. Guided, his project")
    tab.grab().save(str(sandbox / "1_guided.png"))

    tab._instr_combo.setCurrentIndex(tab._instr_combo.findData("SS"))
    pump(app, 600)
    for k in range(tab._paper_combo.count()):
        if "4x6" in str(tab._paper_combo.itemData(k) or ""):
            tab._paper_combo.setCurrentIndex(k)
            break
    pump(app, 800)
    state("2. SpectroScan + 4x6")
    tab.grab().save(str(sandbox / "2_ss_4x6.png"))

    tab._on_generate()
    for _ in range(90):
        pump(app, 1000)
        if tab._generate_btn.isEnabled():
            break
    pump(app, 3000)
    state("3. after Generate")
    tab.grab().save(str(sandbox / "3_after_generate.png"))

    jumped = tab._current_mode() != "guided"
    lost = tab._instr_combo.currentData() != "SS"
    print(f"\nleft Guided by itself : {jumped}")
    print(f"instrument overwritten: {lost} "
          f"(now {tab._instr_combo.currentData()!r})")
    print("shots:", sandbox)
    return 1 if (jumped or lost) else 0


if __name__ == "__main__":
    raise SystemExit(main())
