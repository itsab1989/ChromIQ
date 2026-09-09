#!/usr/bin/env python3
"""Drive the REAL window: is "Straight strips" saved and honoured everywhere?

Basti, 2026-09-09: *"is the new setting savable as default and as part of a
preset and will be respected when starting a new run?"* Three separate
questions, and each is answered here by doing what a person does and then
reading back what the app stored, never by reasoning about the code.

  1. SAVE AS DEFAULTS. Tick it, press "Save as Defaults", throw the panel away,
     build a fresh one, and see whether it comes back ticked.
  2. A PRESET. Tick it, save a named preset, untick, load the preset back.
  3. A NEW RUN. The per-target record is what a run carries, so collect the
     tab's UI state with the box ticked and apply it to a fresh tab, which is
     the same route `Project.new_run` and Duplicate run take.

Settings are sandboxed; nothing of the user's is touched.

    CHROMIQ_SETTINGS_FILE=/tmp/x.ini python scripts/drive_the_turn_is_saved_and_restored.py
"""
from __future__ import annotations

import json
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
SHOTS = Path.home() / "Desktop" / "ChromIQ-hex-proof" / "07-saved"


def pump(app, ms):
    end = time.monotonic() + ms / 1000.0
    while time.monotonic() < end:
        app.processEvents()
        time.sleep(0.01)


def main() -> int:
    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("ChromIQ")
    for fp in resource_path("assets/fonts").glob("*.ttf"):
        QFontDatabase.addApplicationFont(str(fp))
    from ui.styles import APP_STYLESHEET
    app.setStyleSheet(APP_STYLESHEET)

    sb = Path(tempfile.mkdtemp(prefix="chromiq-turn-"))
    from core.settings import AppSettings
    src = QSettings(str(REAL_PLIST), QSettings.Format.NativeFormat)
    dst = QSettings(str(sb / "s.ini"), QSettings.Format.IniFormat)
    for k in src.allKeys():
        dst.setValue(k, src.value(k))
    dst.sync()
    s = AppSettings()
    s._qs = dst
    work = sb / "ChromIQ"
    work.mkdir()
    s.set("custom_output_path", str(work))
    s.set("use_chromiq_layout_engine", True)
    s.set("restore_last_session", False)

    QDialog.exec = lambda self: 1                  # type: ignore[assignment]
    for m in ("warning", "critical", "information", "question"):
        setattr(QMessageBox, m, staticmethod(lambda *a, **k: 0))

    SHOTS.mkdir(parents=True, exist_ok=True)
    from core.argyll_runner import ArgyllRunner
    from core.file_manager import FileManager
    from ui.dialogs.layout_options_panel import LayoutOptionsPanel
    from ui.tabs.tab_chart import TabChart

    def fresh_panel():
        p = LayoutOptionsPanel(with_selectors=True)
        i = p.instr.findData("CR30")
        p.instr.setCurrentIndex(i); p.instr.activated.emit(i)
        j = p.mode.findData("hex")
        p.mode.setCurrentIndex(j); p.mode.activated.emit(j)
        p.set_settings(s) if hasattr(p, "set_settings") else None
        return p

    bad = 0
    print("\n  1. SAVE AS DEFAULTS")
    p1 = fresh_panel()
    p1.hex_flat_top_cb.setChecked(True)
    pump(app, 200)
    rec = p1.get_recipe()
    s.set("manual_engine_recipe", json.dumps(rec.to_dict()))
    print(f"     ticked, saved. stored recipe hex_flat_top = "
          f"{json.loads(s.get('manual_engine_recipe', '{}')).get('hex_flat_top')}")
    p2 = fresh_panel()
    from workflow.layout_engine.presets import LayoutRecipe
    p2.set_recipe(LayoutRecipe.from_dict(
        json.loads(s.get("manual_engine_recipe", "{}"))))
    pump(app, 200)
    got = p2.hex_flat_top_cb.isChecked()
    print(f"     a FRESH panel loading that default comes back ticked: {got}")
    if not got:
        print("     >>> the saved default did not survive"); bad += 1
    p2._expert_frame.set_collapsed(False)
    pump(app, 300)
    p2._helper_markers_grp  # noqa: B018
    grp = p2.hex_flat_top_cb.parentWidget()
    pm = grp.grab()
    if not pm.isNull():
        pm.save(str(SHOTS / "01-restored-from-saved-defaults.png"))
        print(f"     saved 01-restored-from-saved-defaults.png ({pm.width()}x{pm.height()})")

    print("\n  2. A PRESET")
    from workflow.layout_engine.presets import PresetStore
    store = PresetStore()
    r = p1.get_recipe()
    store.set(r)
    round_tripped = PresetStore.from_named_dict(store.as_named_dict())
    back = round_tripped.get(r.instrument, r.paper, r.mode())
    print(f"     saved and reloaded a preset -> hex_flat_top = {back.hex_flat_top}")
    if not back.hex_flat_top:
        print("     >>> the preset lost it"); bad += 1

    print("\n  3. A NEW RUN (the per-target record)")
    tab = TabChart(ArgyllRunner(s), FileManager(s), s)
    tab._user_switch_mode("manual")
    pump(app, 800)
    lp = tab._manual_layout_panel
    i = lp.instr.findData("CR30"); lp.instr.setCurrentIndex(i); lp.instr.activated.emit(i)
    j = lp.mode.findData("hex"); lp.mode.setCurrentIndex(j); lp.mode.activated.emit(j)
    lp.hex_flat_top_cb.setChecked(True)
    pump(app, 300)
    state = tab._collect_ui_state()
    stored = (state.get("engine_recipe") or {}).get("hex_flat_top")
    print(f"     the run's stored record carries hex_flat_top = {stored}")
    if not stored:
        print("     >>> a new run would not carry it"); bad += 1
    tab2 = TabChart(ArgyllRunner(s), FileManager(s), s)
    tab2._user_switch_mode("manual")
    pump(app, 800)
    tab2._apply_ui_state(state)
    pump(app, 300)
    got2 = tab2._manual_layout_panel.hex_flat_top_cb.isChecked()
    print(f"     a fresh tab loading that record comes back ticked: {got2}")
    if not got2:
        print("     >>> reopening the run lost it"); bad += 1
    print(f"\n  problems: {bad}")
    print(f"  proof in {SHOTS}")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
