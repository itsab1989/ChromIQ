#!/usr/bin/env python3
"""Drive the real ChromIQ window with **Basti's own settings and project**.

The sandbox drivers could not reproduce his reload, because the fault depends on
state he has and a fresh sandbox does not: the per-target Create Chart settings
already stored against ``ChromIQ-Test-Chart``, plus his own preferences (the
live preview on, the layout engine on, helper markers on).

So this driver copies both — his real settings store and his real
``~/ChromIQ/<target>`` project — into a throwaway folder and runs against the
copies. Same state, nothing of his touched. The preset is chosen by moving the
Presets combo box, which is the signal a click sends.

    python scripts/drive_preset_reload_real.py [target] [preset-slug ...]

Default: ChromIQ-Test-Chart, then the 204-patch preset followed by the 84-patch
Hand Held one — his sequence.
"""
from __future__ import annotations

import os
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

from PyQt6.QtCore import QSettings                          # noqa: E402
from PyQt6.QtGui import QFontDatabase                       # noqa: E402
from PyQt6.QtWidgets import QApplication, QDialog, QMessageBox  # noqa: E402

from core.resource_path import resource_path                # noqa: E402

BUILDS: list[dict] = []
REAL_PLIST = Path.home() / "Library/Preferences/com.chromiq.ChromIQ.plist"


def pump(app, ms: int) -> None:
    end = time.time() + ms / 1000.0
    while time.time() < end:
        app.processEvents()
        time.sleep(0.01)


def main() -> int:
    target = sys.argv[1] if len(sys.argv) > 1 else "ChromIQ-Test-Chart"
    slugs = sys.argv[2:] or ["cm_a4_204p", "cm_a4_84p"]

    app = QApplication.instance() or QApplication(sys.argv[:1])
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

    sandbox = Path(tempfile.mkdtemp(prefix="chromiq_real_drive_"))

    # 1. His real preferences, copied. Reading the plist through QSettings and
    #    writing an .ini copy keeps every key, including the per-target blobs.
    from core.settings import AppSettings
    src = QSettings(str(REAL_PLIST), QSettings.Format.NativeFormat)
    dst_path = sandbox / "settings.ini"
    dst = QSettings(str(dst_path), QSettings.Format.IniFormat)
    for k in src.allKeys():
        dst.setValue(k, src.value(k))
    dst.sync()
    settings = AppSettings()
    settings._qs = dst

    # 2. His real project, copied.
    configured = str(settings.get("custom_output_path") or "").strip()
    real_root = Path(configured) if configured else (Path.home() / "ChromIQ")
    if not real_root.is_dir():
        real_root = Path.home() / "ChromIQ"
    work = sandbox / "ChromIQ"
    work.mkdir()
    src_proj = real_root / target
    if src_proj.is_dir():
        shutil.copytree(src_proj, work / target)
        print(f"Copied project: {src_proj}  ->  {work / target}")
    else:
        print(f"!! no project {src_proj} — running without one")
    settings.set("custom_output_path", str(work))

    print(f"Sandbox: {sandbox}")
    for k in ("auto_update_preview", "use_chromiq_layout_engine",
              "helper_markers_show", "session_target_name"):
        print(f"   {k} = {settings.get(k)!r}")

    QDialog.exec = lambda self: 1                  # type: ignore[assignment]
    for m in ("warning", "critical", "information", "question"):
        setattr(QMessageBox, m, staticmethod(lambda *a, **k: 0))

    from ui.main_window import MainWindow
    from ui.tabs.tab_chart import KNUT_PRESETS, TabChart

    real_gen = TabChart._generate_from_ti1

    def spy(self, ti1, *, ask=True):
        rec = {}
        try:
            rec = self._manual_layout_panel.get_recipe().to_dict()
        except Exception:      # noqa: BLE001
            pass
        BUILDS.append(dict(ti1=Path(ti1).name, by="click" if ask else "preview",
                           cols=rec.get("area_cols"), rows=rec.get("area_rows"),
                           left=rec.get("margin_left"), paper=rec.get("paper")))
        return real_gen(self, ti1, ask=ask)
    TabChart._generate_from_ti1 = spy
    TabChart._confirm_displacing_results = lambda self, *a, **k: True
    TabChart._prompt_target_name = lambda self, *a, **k: target

    win = MainWindow(settings)
    win.show()
    pump(app, 2000)

    tab = win._tab_chart
    tab._switch_mode("manual")
    pump(app, 800)
    mp = tab._margin_panel
    print(f"\nOn open: helper markers = {mp.helper_markers()[0]}, "
          f"engine = {settings.get('use_chromiq_layout_engine')}")
    e = mp._helper_edge
    print(f"Helper-marker spin box: {e.size().width()}x{e.size().height()} px, "
          f"objectName={e.objectName()!r}")

    # HIS SEQUENCE: open, turn "Show helper markers" OFF, then pick the preset.
    print("\nTurning 'Show helper markers' off…")
    mp._helper_check.setChecked(False)
    pump(app, 3000)          # let any re-render it triggers land and settle
    BUILDS.clear()

    failures = 0
    for n, slug in enumerate(slugs, 1):
        preset = next(p for p in KNUT_PRESETS if p.slug.startswith(slug))
        BUILDS.clear()
        ix = tab._preset_combo.findData(preset.key)
        if ix < 0:
            print(f"  [FAIL] {slug} not in the dropdown")
            failures += 1
            continue
        # Move the combo — the same signal a click on the item sends.
        tab._preset_combo.setCurrentIndex(ix)
        pump(app, 6000)
        ok = len(BUILDS) == 1 and BUILDS[0]["by"] == "click"
        failures += not ok
        print(f"\n  [{'PASS' if ok else 'FAIL'}] step {n}: {preset.name}")
        for b in BUILDS:
            print(f"       {b['by']:<7} {b['ti1']:<28} "
                  f"{b['cols']}x{b['rows']} grid, left margin {b['left']}, "
                  f"{b['paper']}")

    print(f"\n{'ALL CLEAN' if not failures else str(failures) + ' STEP(S) FAILED'}")
    win.close()
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
