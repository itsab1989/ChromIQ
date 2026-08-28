#!/usr/bin/env python3
"""Drive the REAL ChromIQ window and watch what a built-in preset actually builds.

Basti, 2026-08-16: picking one of Knut's ColorMunki presets built the right
chart and then, a moment later, rebuilt it — the patches coming back much
narrower. This driver reproduces that on the real MainWindow (not a stub), by
recording **every** chart build the app starts: which patch set it used, which
grid, and whether it came from the user's click or from the live preview.

    python scripts/drive_preset_reload.py                 # on screen
    QT_QPA_PLATFORM=offscreen python scripts/drive_preset_reload.py

It works in a throwaway sandbox: the user's own ~/ChromIQ and preferences are
never touched. "Update the preview automatically" is forced ON, because that is
the setting the fault needs.

A run is CLEAN when every selection reports exactly one build, from the
preset's own ``chart.ti1``. Two builds — the second with ``by=preview`` — is the
fault.
"""
from __future__ import annotations

import os
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

ONSCREEN = os.environ.get("QT_QPA_PLATFORM") != "offscreen"

# QtWebEngine MUST be imported before QApplication (mirrors main.py).
try:
    import PyQt6.QtWebEngineWidgets  # noqa: F401
except ImportError:
    pass

from PyQt6.QtCore import QSettings                          # noqa: E402
from PyQt6.QtGui import QFontDatabase                       # noqa: E402
from PyQt6.QtWidgets import QApplication, QDialog, QMessageBox  # noqa: E402

from core.resource_path import resource_path                # noqa: E402

BUILDS: list[dict] = []


def pump(app, ms: int) -> None:
    end = time.time() + ms / 1000.0
    while time.time() < end:
        app.processEvents()
        time.sleep(0.01)


def main() -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("ChromIQ")
    try:
        for fp in resource_path("assets/fonts").glob("*.ttf"):
            QFontDatabase.addApplicationFont(str(fp))
    except Exception:      # noqa: BLE001
        pass
    try:
        from ui.styles import APP_STYLESHEET
        app.setStyleSheet(APP_STYLESHEET)
    except Exception:      # noqa: BLE001
        pass

    sandbox = Path(tempfile.mkdtemp(prefix="chromiq_preset_drive_"))
    from core.settings import AppSettings
    settings = AppSettings()
    settings._qs = QSettings(str(sandbox / "drive_settings.ini"),
                             QSettings.Format.IniFormat)
    settings.set("custom_output_path", str(sandbox / "ChromIQ"))
    settings.set("auto_update_preview", True)      # the setting the fault needs
    settings.set("use_chromiq_layout_engine", False)   # a fresh session
    print(f"Sandbox: {sandbox}")

    # Never block on a dialog; accept the name the preset suggests.
    QDialog.exec = lambda self: 1                  # type: ignore[assignment]
    for m in ("warning", "critical", "information", "question"):
        setattr(QMessageBox, m, staticmethod(lambda *a, **k: 0))

    from ui.main_window import MainWindow
    from ui.tabs.tab_chart import KNUT_PRESETS, TabChart

    # Record every build before the window exists, so nothing is missed.
    real_gen = TabChart._generate_from_ti1

    def spy(self, ti1, *, ask=True):
        rec = {}
        try:
            rec = self._manual_layout_panel.get_recipe().to_dict()
        except Exception:      # noqa: BLE001
            pass
        BUILDS.append(dict(ti1=Path(ti1).name, by="click" if ask else "preview",
                           grid=f"{rec.get('area_cols')}x{rec.get('area_rows')}",
                           paper=rec.get("paper")))
        return real_gen(self, ti1, ask=ask)
    TabChart._generate_from_ti1 = spy
    # The §4 "this replaces a measured chart" question never arises in a fresh
    # sandbox, but answer it anyway so a stray one can't stall the run.
    TabChart._confirm_displacing_results = lambda self, *a, **k: True
    TabChart._prompt_target_name = lambda self, *a, **k: "Preset-Drive"

    win = MainWindow(settings)
    win.show()
    pump(app, 1500)

    tab = win._tab_chart
    tab._switch_mode("manual")
    pump(app, 500)

    # Three ColorMunki presets whose grids differ a lot, so a re-layout of the
    # WRONG patch set is obvious in the patch width: 17x12, then 38x12, then back.
    picks = ["cm_a4_204p", "cm_a3_2280p", "cm_a4_204p", "cm_a4_204p"]
    failures = 0
    for i, slug in enumerate(picks, 1):
        preset = next(p for p in KNUT_PRESETS if p.slug.startswith(slug))
        BUILDS.clear()
        ix = tab._preset_combo.findData(preset.key)
        if ix < 0:
            print(f"  [FAIL] {slug}: not in the presets dropdown")
            failures += 1
            continue
        # Move the dropdown FIRST, then dispatch — calling the handler on its
        # own leaves `_last_preset_index` committed for an index the combo is
        # not on (#175 moved the combo to `activated`, which is silent for a
        # programmatic move).
        tab._preset_combo.blockSignals(True)
        tab._preset_combo.setCurrentIndex(ix)
        tab._preset_combo.blockSignals(False)
        tab._on_preset_selected(ix)
        pump(app, 4000)          # well past the 450 ms preview debounce
        ok = len(BUILDS) == 1 and BUILDS[0]["by"] == "click"
        failures += not ok
        print(f"\n  [{'PASS' if ok else 'FAIL'}] pick {i}: {preset.name}")
        for b in BUILDS:
            print(f"       build: {b['ti1']:<28} by={b['by']:<7} "
                  f"grid={b['grid']:<7} paper={b['paper']}")
        if not ok:
            print("       ^ a second build means the live preview re-laid out "
                  "the chart behind the preset's back")

    print(f"\n{'ALL CLEAN' if not failures else str(failures) + ' FAILED'}")
    if ONSCREEN:
        print("Window stays up for 3 s so you can see the final chart.")
        pump(app, 3000)
    win.close()
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
