#!/usr/bin/env python3
"""Adversary round 29: a saved #182 report, opened from a project that MOVED.

A document records each measurement by `document_measurement_key`, which begins
with the measurement's ABSOLUTE folder. Copy the project anywhere else and every
recorded key stops matching, so `_restore_the_documents_view` unticks the lot.

Generates a real document in place, copies the whole project to a second path,
opens the REAL window there, selects the saved report and photographs what the
reader sees.

    export CHROMIQ_SETTINGS_FILE=/tmp/chromiq-r29/settings.ini
    export CHROMIQ_PRESETS_DIR=/tmp/chromiq-r29/presets
    python scripts/adv29_a_project_that_moved.py <project> <out> <tag>
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
try:
    import PyQt6.QtWebEngineWidgets  # noqa: F401
except ImportError:
    pass
from PyQt6.QtCore import QTimer                                  # noqa: E402
from PyQt6.QtWidgets import QApplication, QMessageBox            # noqa: E402
from onscreen_capture import capture_window, session_is_locked   # noqa: E402


def _frames_match(a: Path, b: Path, tol: int = 8) -> bool:
    try:
        import numpy as np
        from PIL import Image
        x = np.asarray(Image.open(a).convert("RGB")).astype(int)
        y = np.asarray(Image.open(b).convert("RGB")).astype(int)
        if x.shape != y.shape:
            return False
        return bool((np.abs(x - y).sum(axis=2) > tol).sum() == 0)
    except Exception:                                      # noqa: BLE001
        return False


def pump(app, ms: int = 300) -> None:
    end = time.monotonic() + ms / 1000.0
    while time.monotonic() < end:
        app.processEvents()
        time.sleep(0.01)


def capture_settled(app, win, first: Path, second: Path, tries: int = 8):
    ok = ok2 = False
    why = ""
    for n in range(1, tries + 1):
        pump(app, 1500)
        ok, why = capture_window(win, first)
        pump(app, 1500)
        ok2, why2 = capture_window(win, second)
        why = why or why2
        if ok and ok2 and _frames_match(first, second):
            return True, why, n, True
    return bool(ok and ok2), why, tries, False


def answer_once(app, label):
    seen = {"found": False, "tries": 0}

    def _act():
        if seen.get("done"):
            return
        box = next((w for w in QApplication.topLevelWidgets()
                    if isinstance(w, QMessageBox) and w.isVisible()), None)
        if box is None:
            seen["tries"] += 1
            if seen["tries"] > 24:
                seen["done"] = True
                return
            QTimer.singleShot(250, _act)
            return
        seen["done"] = True
        seen["found"] = True
        seen["buttons"] = [b.text().replace("&", "") for b in box.buttons()]
        for b in box.buttons():
            if b.text().replace("&", "") == label:
                b.click()
                return
        box.accept()

    QTimer.singleShot(300, _act)
    return seen


def ticks(dlg):
    from PyQt6.QtCore import Qt
    out = []
    for i in range(dlg._profile_list.count()):
        it = dlg._profile_list.item(i)
        if Qt.ItemFlag.ItemIsUserCheckable in it.flags():
            out.append([it.text()[:52],
                        it.checkState() == Qt.CheckState.Checked])
    return out


def open_on(app, settings, ti3):
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    dlg = MeasurementReportDialog(settings, None, initial_ti3=ti3)
    dlg.resize(1480, 1000)
    dlg.show(); dlg.raise_(); dlg.activateWindow()
    pump(app, 2500)
    return dlg


def main() -> int:                                          # noqa: C901
    assert os.environ.get("CHROMIQ_SETTINGS_FILE"), "SANDBOX THE SETTINGS FIRST"
    assert os.environ.get("CHROMIQ_PRESETS_DIR"), "SANDBOX THE PRESETS FIRST"
    assert not os.environ.get("QT_QPA_PLATFORM"), "this DRIVER opens a window"
    src, out = Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve()
    tag = sys.argv[3] if len(sys.argv) > 3 else "after"
    out.mkdir(parents=True, exist_ok=True)

    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("ChromIQ")
    from ui.styles import WinButtonLayoutStyle
    app.setStyle(WinButtonLayoutStyle("Fusion"))
    from ui.theme import apply_appearance
    apply_appearance(app, None, "light")
    from core.settings import AppSettings
    work = Path(tempfile.mkdtemp(prefix="chromiq-r29-moved-"))
    settings = AppSettings()
    settings.set("custom_output_path", str(work))
    settings.set("appearance", "light")
    settings.set("language", "en")
    assert settings.get("custom_output_path", "") == str(work), "SANDBOX FAILED"
    dest = work / src.name
    shutil.copytree(src, dest)
    from core.file_manager import FileManager
    fm = FileManager(settings); del fm
    print(f"    screen locked at start: {session_is_locked()}", flush=True)

    res = {"tag": tag, "locked_at_start": session_is_locked()}
    ti3 = sorted((dest / "runs" / "run1" / "verifications"
                  / "2026-11-16_100000").glob("*.ti3"))[0]
    dlg = open_on(app, settings, ti3)
    res["window_visible"] = dlg.isVisible()
    # a real #182 document, made from "New report…" with every row ticked
    dlg._saved_combo.setCurrentIndex(0)
    pump(app, 800)
    dlg._all_runs_check.setChecked(True)
    pump(app, 900)
    h = answer_once(app, "Create New")
    dlg._on_generate_report()
    pump(app, 3000)
    made = str(dlg._loaded_doc_id)
    res["in_place"] = {"doc": made, "asked": h.get("found"),
                       "history": len(dlg._history),
                       "hidden": len(dlg._hidden_runs),
                       "rows_on_the_page": len(dlg._runs_for_report()),
                       "generate_enabled": dlg._generate_btn.isEnabled(),
                       "ticks": ticks(dlg)}
    print(f"  in place: doc={made} history={res['in_place']['history']} "
          f"hidden={res['in_place']['hidden']} "
          f"rows={res['in_place']['rows_on_the_page']} "
          f"generate={res['in_place']['generate_enabled']}", flush=True)
    ok, why, _t, same = capture_settled(app, dlg, out / f"{tag}-inplace-1.png",
                                        out / f"{tag}-inplace-2.png")
    res["in_place"]["photo"] = {"taken": ok, "why": why, "identical": same}
    dlg.close(); pump(app, 600)

    # --- MOVE IT -----------------------------------------------------------
    moved_root = work / "moved"
    moved_root.mkdir()
    shutil.copytree(dest, moved_root / dest.name)
    settings.set("custom_output_path", str(moved_root))
    from core.file_manager import Project
    p2 = Project.load(moved_root / dest.name)
    r2 = p2.all_runs()[0]
    ti3b = sorted((moved_root / dest.name / "runs" / "run1" / "verifications"
                   / "2026-11-16_100000").glob("*.ti3"))[0]
    dlg2 = open_on(app, settings, ti3b)
    picked = None
    for i in range(dlg2._saved_combo.count()):
        if str(dlg2._saved_combo.itemData(i)).startswith("id:"):
            dlg2._saved_combo.setCurrentIndex(i)
            pump(app, 1600)
            picked = str(dlg2._saved_combo.itemData(i))
            break
    res["moved"] = {"root": str(moved_root), "picked": picked,
                    "entry": dlg2._saved_combo.currentText(),
                    "history": len(dlg2._history),
                    "hidden": len(dlg2._hidden_runs),
                    "rows_on_the_page": len(dlg2._runs_for_report()),
                    "generate_enabled": dlg2._generate_btn.isEnabled(),
                    "ticks": ticks(dlg2)}
    print(f"  moved   : picked={picked} history={res['moved']['history']} "
          f"hidden={res['moved']['hidden']} "
          f"rows={res['moved']['rows_on_the_page']} "
          f"generate={res['moved']['generate_enabled']}", flush=True)
    print(f"            ticks={res['moved']['ticks']}", flush=True)
    ok, why, _t, same = capture_settled(app, dlg2, out / f"{tag}-moved-1.png",
                                        out / f"{tag}-moved-2.png")
    res["moved"]["photo"] = {"taken": ok, "why": why, "identical": same}
    print(f"    photograph: {ok} {why}; identical {same}", flush=True)
    dlg2.close(); pump(app, 500)

    res["locked_at_end"] = session_is_locked()
    (out / f"moved-{tag}.json").write_text(json.dumps(res, indent=2,
                                                      default=str),
                                           encoding="utf-8")
    print(f"    wrote {out / f'moved-{tag}.json'}", flush=True)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception:                                      # noqa: BLE001
        traceback.print_exc()
        raise SystemExit(2)
