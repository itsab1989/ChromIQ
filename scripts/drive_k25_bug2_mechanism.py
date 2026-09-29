#!/usr/bin/env python3
"""Knut's beta-25 bug 2, driven to its MECHANISM in a real window.

His words: *"If I change Judged against from 'ChromIQ default' to 'ChromIQ
tight', then suddenly report type also changes to 'Grey and tone check'."*

Grey and tone check is what `Report-Limits-Report-Types/run1` carries on the
RUN once the type pulldown has been used, and a saved report carries the type
it was made with. The sequence below is ordinary:

    1. open on run1's 2026-11-16 measurement;
    2. use the "Report type" pulldown once, choosing "Grey and tone check"
       (this writes the type onto the RUN, D9);
    3. select the saved report "2026-11-16 10:00 · Colour summary (one page)"
       in "Report shown" (its own type is T1, so the pulldown reads T1);
    4. change ONLY "Judged against".

Step 4 drops the loaded document's claim on the controls, `_report_type_now`
falls back to the RUN, and the type pulldown jumps to what step 2 wrote.

    CHROMIQ_SETTINGS_FILE=… CHROMIQ_PRESETS_DIR=… \\
        python scripts/drive_k25_bug2_mechanism.py <project> <out>
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


def capture_settled(app, win, first: Path, second: Path, tries: int = 4):
    ok = ok2 = False
    why = ""
    for n in range(1, tries + 1):
        pump(app, 800)
        ok, why = capture_window(win, first)
        pump(app, 800)
        ok2, why2 = capture_window(win, second)
        why = why or why2
        if ok and ok2 and _frames_match(first, second):
            return True, why, n, True
    return bool(ok and ok2), why, tries, False


def main() -> int:                                          # noqa: C901
    assert os.environ.get("CHROMIQ_SETTINGS_FILE"), "SANDBOX THE SETTINGS FIRST"
    assert os.environ.get("CHROMIQ_PRESETS_DIR"), "SANDBOX THE PRESETS FIRST"
    assert not os.environ.get("QT_QPA_PLATFORM"), "this DRIVER opens a window"
    src, out = Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve()
    out.mkdir(parents=True, exist_ok=True)

    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("ChromIQ")
    from ui.styles import WinButtonLayoutStyle
    app.setStyle(WinButtonLayoutStyle("Fusion"))
    from core.settings import AppSettings
    work = Path(tempfile.mkdtemp(prefix="chromiq-k25b-"))
    settings = AppSettings()
    settings.set("custom_output_path", str(work))
    settings.set("appearance", "light")
    settings.set("language", "en")
    assert settings.get("custom_output_path", "") == str(work), "SANDBOX FAILED"
    dest = work / src.name
    shutil.copytree(src, dest)
    print(f"    project copied to {dest}", flush=True)
    print(f"    screen locked at start: {session_is_locked()}", flush=True)
    QDialog.exec = lambda self: 1                     # type: ignore[assignment]
    for m in ("warning", "critical", "information", "question"):
        setattr(QMessageBox, m, staticmethod(lambda *a, **k: 0))
    from core.file_manager import FileManager
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    from ui.theme import apply_appearance
    MeasurementReportDialog._confirm = (                # type: ignore[assignment]
        lambda self, title, body: True)
    apply_appearance(app, None, "light")
    fm = FileManager(settings); del fm

    ti3 = sorted((dest / "runs" / "run1" / "verifications"
                  / "2026-11-16_100000").glob("*.ti3"))[0]
    dlg = MeasurementReportDialog(settings, None, initial_ti3=ti3)
    dlg.resize(1480, 1040)
    dlg.show(); dlg.raise_(); dlg.activateWindow()
    pump(app, 3000)
    print(f"    window on screen: {dlg.isVisible()}", flush=True)
    res: dict = {"project": str(src), "copy": str(dest), "steps": []}

    def snap(tag: str) -> dict:
        s = {
            "step": tag,
            "report_shown": dlg._saved_combo.currentText(),
            "report_type": dlg._type_combo.currentText(),
            "report_type_id": dlg._type_combo.currentData(),
            "judged_against": dlg._set_combo.currentText(),
            "judged_against_id": dlg._set_combo.currentData(),
            "run_meta_type": json.loads(
                (dest / "runs" / "run1" / "meta.json").read_text(encoding="utf-8")
            ).get("report_type", ""),
            "run_meta_set": json.loads(
                (dest / "runs" / "run1" / "meta.json").read_text(encoding="utf-8")
            ).get("compliance_set_id", ""),
        }
        res["steps"].append(s)
        print(f"  {tag:34s} type={s['report_type']!r:32s} "
              f"set={s['judged_against']!r:32s} run.meta.type={s['run_meta_type']!r}",
              flush=True)
        return s

    snap("1 opened")

    # -- 2. use the type pulldown once (an ordinary thing a user does) ------
    i = dlg._type_combo.findData("t3_grey_and_tone")
    assert i >= 0, "no Grey and tone check in the pulldown"
    dlg._type_combo.setCurrentIndex(i)
    pump(app, 1200)
    snap("2 chose Grey and tone check")

    # -- 3. select the saved Colour summary report --------------------------
    want = [k for k in range(dlg._saved_combo.count())
            if dlg._saved_combo.itemText(k).startswith("2026-11-16 10:00")]
    assert want, [dlg._saved_combo.itemText(k)
                  for k in range(dlg._saved_combo.count())]
    dlg._saved_combo.setCurrentIndex(want[0])
    # A CLICK, not a programmatic index move: the pulldown is already on this
    # entry (the window opened on the latest report), and Qt fires
    # `currentIndexChanged` only when the index MOVES. `activated` is what a
    # real click sends, and `_on_saved_picked_again` is the slot behind it.
    dlg._saved_combo.activated.emit(want[0])
    pump(app, 1600)
    before = snap("3 selected the 2026-11-16 report")
    ok, why, tries, same = capture_settled(
        app, dlg, out / "B2-before-1.png", out / "B2-before-2.png")
    print(f"    photograph before: {ok} {why}; identical: {same}/{tries}", flush=True)
    res["photo_before"] = {"taken": ok, "why": why, "identical": same}

    # -- 4. change ONLY "Judged against" ------------------------------------
    j = dlg._set_combo.findData("chromiq_tight")
    assert j >= 0
    dlg._set_combo.setCurrentIndex(j)
    pump(app, 1600)
    after = snap("4 changed Judged against only")
    ok, why, tries, same = capture_settled(
        app, dlg, out / "B2-after-1.png", out / "B2-after-2.png")
    print(f"    photograph after: {ok} {why}; identical: {same}/{tries}", flush=True)
    res["photo_after"] = {"taken": ok, "why": why, "identical": same}

    res["type_moved_on_a_set_change"] = (
        before["report_type_id"] != after["report_type_id"])
    res["from"] = before["report_type"]
    res["to"] = after["report_type"]
    print(f"\n  BUG 2 REPRODUCED: {res['type_moved_on_a_set_change']}  "
          f"{before['report_type']!r} -> {after['report_type']!r}", flush=True)

    json.dump(res, (out / "result.json").open("w", encoding="utf-8"),
              indent=2, default=str)
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
