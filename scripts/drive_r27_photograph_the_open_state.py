#!/usr/bin/env python3
"""R27-F3, photographed: the window names one report and draws another.

Opens the Measurement Report window on `Report-Limits-Report-Types/run1` with
default Preferences and takes NO action at all, then photographs it and prints
the three places that have to agree: the "Report shown" entry, the "Report
type" pulldown, and the page's own head line.

    CHROMIQ_SETTINGS_FILE=… CHROMIQ_PRESETS_DIR=… \\
        python scripts/drive_r27_photograph_the_open_state.py <project> <out> <tag>
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
from PyQt6.QtWidgets import QApplication, QDialog, QMessageBox   # noqa: E402
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


def main() -> int:
    assert os.environ.get("CHROMIQ_SETTINGS_FILE"), "SANDBOX THE SETTINGS FIRST"
    assert os.environ.get("CHROMIQ_PRESETS_DIR"), "SANDBOX THE PRESETS FIRST"
    assert not os.environ.get("QT_QPA_PLATFORM"), "this DRIVER opens a window"
    src, out, tag = (Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve(),
                     sys.argv[3])
    out.mkdir(parents=True, exist_ok=True)
    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("ChromIQ")
    from ui.styles import WinButtonLayoutStyle
    app.setStyle(WinButtonLayoutStyle("Fusion"))
    from core.settings import AppSettings
    work = Path(tempfile.mkdtemp(prefix="chromiq-r27p-"))
    settings = AppSettings()
    settings.set("custom_output_path", str(work))
    settings.set("appearance", "dark")
    settings.set("language", "en")
    assert settings.get("custom_output_path", "") == str(work), "SANDBOX FAILED"
    dest = work / src.name
    shutil.copytree(src, dest)
    QDialog.exec = lambda self: 1                     # type: ignore[assignment]
    for m in ("warning", "critical", "information", "question"):
        setattr(QMessageBox, m, staticmethod(lambda *a, **k: 0))
    from core.file_manager import FileManager
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    from ui.theme import apply_appearance
    apply_appearance(app, None, "dark")
    fm = FileManager(settings); del fm
    print(f"    screen locked at start: {session_is_locked()}", flush=True)
    ti3 = dest / ("runs/run1/verifications/2026-11-02_100000/"
                  "Report-Limits-Report-Types-verify.ti3")
    dlg = MeasurementReportDialog(settings, None, initial_ti3=ti3)
    dlg.resize(1420, 1000)
    dlg.show(); dlg.raise_(); dlg.activateWindow()
    pump(app, 3500)
    head = next((ln.strip() for ln in dlg._view.toPlainText().splitlines()
                 if ln.strip().startswith("Report type:")), "")
    facts = {
        "tag": tag,
        "window_visible": bool(dlg.isVisible()),
        "report_shown": dlg._saved_combo.currentText(),
        "report_type_pulldown": dlg._type_combo.currentText(),
        "judged_against_pulldown": dlg._set_combo.currentText(),
        "page_head_line": head,
        "red_settings_changed_line": bool(dlg._stale_label.isVisible()),
        "they_agree": bool(
            dlg._type_combo.currentText() in dlg._saved_combo.currentText()
            and dlg._type_combo.currentText() in head),
    }
    for k, v in facts.items():
        print(f"    {k}: {v}", flush=True)
    ok = same = False
    why = ""
    for n in range(1, 5):
        pump(app, 800)
        ok, why = capture_window(dlg, out / f"{tag}-open-state.png")
        pump(app, 800)
        ok2, why2 = capture_window(dlg, out / f"{tag}-open-state-again.png")
        why = why or why2
        ok = bool(ok and ok2)
        if ok and _frames_match(out / f"{tag}-open-state.png",
                                out / f"{tag}-open-state-again.png"):
            same = True
            break
    print(f"    photograph: {ok} {why}; two identical frames: {same}",
          flush=True)
    facts["photograph"] = {"taken": ok, "why": why, "two_identical_frames": same}
    json.dump(facts, (out / f"{tag}-facts.json").open("w"), indent=2)
    dlg.close()
    pump(app, 400)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception:                                      # noqa: BLE001
        traceback.print_exc()
        raise SystemExit(2)
