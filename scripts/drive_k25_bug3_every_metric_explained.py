#!/usr/bin/env python3
"""Knut's beta-25 bug 3, measured in a REAL window.

*"Whatever metrics are shown in Report Results: each metric used in the report
shall have a corresponding explanation of each metric in the 'How to read this
report' section. Currently, only 4 metrics are described in a bullet list …
The bullet list of parameters explained is then changing with which metrics the
report contains."*

So: for every report type that carries a Report Results table, crossed with
every limit set the window offers, read the metric rows the table lists and the
metric names the guide explains, and report the rows that are judged with no
explanation anywhere.

    CHROMIQ_SETTINGS_FILE=… CHROMIQ_PRESETS_DIR=… \\
        python scripts/drive_k25_bug3_every_metric_explained.py <project> <out>
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
    work = Path(tempfile.mkdtemp(prefix="chromiq-k25c-"))
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
    from core.i18n import tr
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    from ui.theme import apply_appearance
    from workflow.compliance_sets import ROW_BY_ID
    MeasurementReportDialog._confirm = (                # type: ignore[assignment]
        lambda self, title, body: True)
    apply_appearance(app, None, "light")
    fm = FileManager(settings); del fm

    ti3 = sorted((dest / "runs" / "run1" / "verifications"
                  / "2026-11-02_100000").glob("*.ti3"))[0]
    dlg = MeasurementReportDialog(settings, None, initial_ti3=ti3)
    dlg.resize(1480, 1040)
    dlg.show(); dlg.raise_(); dlg.activateWindow()
    pump(app, 3000)
    print(f"    window on screen: {dlg.isVisible()}", flush=True)

    res: dict = {"project": str(src), "copy": str(dest), "cells": []}

    def choosable(combo):
        model = combo.model()
        out_ = []
        for i in range(combo.count()):
            item = model.item(i) if hasattr(model, "item") else None
            if item is not None and not item.isEnabled():
                continue
            if not combo.itemData(i):
                continue
            out_.append((i, combo.itemText(i), combo.itemData(i)))
        return out_

    types = choosable(dlg._type_combo)
    sets = choosable(dlg._set_combo)
    print(f"    {len(types)} types x {len(sets)} sets", flush=True)

    worst = None
    for ti, tname, tid in types:
        dlg._type_combo.setCurrentIndex(ti)
        pump(app, 500)
        for si, sname, sid in sets:
            dlg._set_combo.setCurrentIndex(si)
            pump(app, 700)
            txt = dlg._view.toPlainText()
            if "Report Results" not in txt or "How to read this report" not in txt:
                res["cells"].append({"type": tid, "set": sid,
                                     "no_results_table": True})
                continue
            guide = txt.split("How to read this report", 1)[1]
            guide = guide.split("Report Results", 1)[0]
            table = txt.split("Report Results", 1)[1]
            table = table.split("Overview of Measurement Metrics", 1)[0]
            table = table.split("Detailed data", 1)[0]
            # the metric rows the TABLE lists, and whether the GUIDE names each
            shown, unexplained = [], []
            for rid, row in ROW_BY_ID.items():
                lab = tr(row.label)
                if lab and lab in table:
                    shown.append(lab)
                    if lab not in guide:
                        unexplained.append(lab)
            cell = {"type": tid, "type_name": tname, "set": sid,
                    "set_name": sname, "rows_shown": len(shown),
                    "rows_unexplained": unexplained}
            res["cells"].append(cell)
            (out / f"K3-{tid}-{sid}.txt").write_text(txt, encoding="utf-8")
            flag = "OK " if not unexplained else "GAP"
            print(f"      {flag} {tid:22s} {sid:20s} rows={len(shown):2d} "
                  f"unexplained={len(unexplained)}", flush=True)
            if unexplained and (worst is None or
                                len(unexplained) > len(worst[2])):
                worst = (ti, si, unexplained)

    res["total_unexplained"] = sum(len(c.get("rows_unexplained") or [])
                                   for c in res["cells"])
    res["cells_with_a_gap"] = sum(1 for c in res["cells"]
                                  if c.get("rows_unexplained"))
    print(f"\n  metrics judged with no explanation: {res['total_unexplained']} "
          f"across {res['cells_with_a_gap']} combinations", flush=True)

    # photograph the worst one, or the richest one when there is no gap
    ti, si = (worst[0], worst[1]) if worst else (types[-1][0], sets[-1][0])
    dlg._type_combo.setCurrentIndex(ti)
    pump(app, 500)
    dlg._set_combo.setCurrentIndex(si)
    pump(app, 900)
    dlg._view.verticalScrollBar().setValue(
        int(dlg._view.verticalScrollBar().maximum() * 0.32))
    ok, why, tries, same = capture_settled(
        app, dlg, out / "K3-guide-1.png", out / "K3-guide-2.png")
    print(f"    photograph: {ok} {why}; identical: {same}/{tries}", flush=True)
    res["photo"] = {"taken": ok, "why": why, "identical": same}

    json.dump(res, (out / "bug3.json").open("w", encoding="utf-8"),
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
