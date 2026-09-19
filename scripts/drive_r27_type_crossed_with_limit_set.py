#!/usr/bin/env python3
"""Adversary round 27, part three: the report text crossed against its TYPE
and its LIMIT SET, in a real window.

Every buildable report type against every choosable limit set, on one
measurement: the page is dumped each time and the head line, the verdict
words and the row groups are read back, so a sentence that is true for one
combination and shipped for all six is visible side by side.

    CHROMIQ_SETTINGS_FILE=… CHROMIQ_PRESETS_DIR=… \\
        python scripts/drive_r27_type_crossed_with_limit_set.py <proj> <out>
"""
from __future__ import annotations

import hashlib
import json
import os
import re
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
    work = Path(tempfile.mkdtemp(prefix="chromiq-r27c-"))
    settings = AppSettings()
    settings.set("custom_output_path", str(work))
    settings.set("appearance", "dark")
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
    asked: list = []

    def confirm(self, title, body):
        asked.append({"title": str(title), "body": str(body)})
        return True
    MeasurementReportDialog._confirm = confirm        # type: ignore[assignment]
    apply_appearance(app, None, "dark")
    fm = FileManager(settings); del fm

    run_name = os.environ.get("R27_RUN", "run1")
    best = None
    for d in sorted((dest / "runs" / run_name).glob("verifications/*")):
        t = sorted(d.glob("*.ti3"))
        if t and (best is None):
            best = t[0]
    assert best is not None
    ti3 = best
    print(f"    opening on {ti3.relative_to(dest)}", flush=True)

    dlg = MeasurementReportDialog(settings, None, initial_ti3=ti3)
    dlg.resize(1480, 1040)
    dlg.show(); dlg.raise_(); dlg.activateWindow()
    pump(app, 3200)
    print(f"    window on screen: {dlg.isVisible()}", flush=True)

    types = []
    tm = dlg._type_combo.model()
    for i in range(dlg._type_combo.count()):
        item = tm.item(i) if hasattr(tm, "item") else None
        if item is not None and not item.isEnabled():
            continue
        if not dlg._type_combo.itemData(i):
            continue
        types.append((i, dlg._type_combo.itemText(i), dlg._type_combo.itemData(i)))
    sets = []
    sm = dlg._set_combo.model()
    for i in range(dlg._set_combo.count()):
        item = sm.item(i) if hasattr(sm, "item") else None
        if item is not None and not item.isEnabled():
            continue
        if not dlg._set_combo.itemData(i):
            continue
        sets.append((i, dlg._set_combo.itemText(i), dlg._set_combo.itemData(i)))
    print(f"    {len(types)} choosable types x {len(sets)} choosable sets",
          flush=True)
    res: dict = {"project": str(src), "copy": str(dest),
                 "types": [t[1] for t in types], "sets": [s[1] for s in sets]}

    cells = []
    for si, sname, sid in sets:
        dlg._set_combo.setCurrentIndex(si)
        dlg._on_set_chosen(si)
        pump(app, 700)
        for ti, tname, tid in types:
            dlg._type_combo.setCurrentIndex(ti)
            dlg._on_type_chosen(ti)
            pump(app, 700)
            txt = dlg._view.toPlainText()
            stem = f"X-{sid}-{tid}"
            (out / f"{stem}.txt").write_text(txt, encoding="utf-8")
            head = txt.splitlines()[1] if len(txt.splitlines()) > 1 else ""
            words = {w: len(re.findall(rf"(?<![A-Za-z]){w}(?![A-Za-z])", txt))
                     for w in ("PASS", "FAIL", "COND", "INFO", "N-A")}
            cell = {
                "set_id": sid, "set_name": sname,
                "type_id": tid, "type_name": tname,
                "combo_type": dlg._type_combo.currentText(),
                "combo_set": dlg._set_combo.currentText(),
                "head": head,
                "head_names_type": tname in head,
                "head_names_set": sname.split(" (")[0] in head,
                "verdicts": words,
                "has_grey_row": "Grey balance" in txt,
                "has_colour_row": "Colour accuracy" in txt,
                "sha": hashlib.sha256(txt.encode()).hexdigest()[:12],
                "lines": len(txt.splitlines()),
            }
            cells.append(cell)
            print(f"      {sid:22s} {tid:22s} head_ok={cell['head_names_type']}"
                  f"/{cell['head_names_set']} verdicts={words} "
                  f"grey={cell['has_grey_row']} colour={cell['has_colour_row']}",
                  flush=True)
    res["cells"] = cells
    ok, why, tries, same = capture_settled(
        app, dlg, out / "R4-the-last-cell.png", out / "R4b-the-last-cell.png")
    print(f"    photograph: {ok} {why}; identical: {same}/{tries}", flush=True)
    res["photo"] = {"taken": ok, "why": why, "identical": same}
    res["asked"] = asked
    json.dump(res, (out / "result.json").open("w"), indent=2, default=str)
    print("    wrote result.json", flush=True)
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
