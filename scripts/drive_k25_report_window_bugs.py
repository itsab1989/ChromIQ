#!/usr/bin/env python3
"""Knut's beta-25 Measurement Report bugs, reproduced in a REAL window.

Drives the window exactly as he described it: demo "Report-Limits-Report-Types",
run1, the report shown as "2026-11-16 10:00 Colour summary…", then

  1. reads the "Created:" line of the report TEXT and compares it with the
     creation stamp the selected entry's NAME carries;
  2. moves "Judged against" from ChromIQ default to ChromIQ tight and reads the
     report-type pulldown BEFORE and AFTER;
  3. lists the metric rows the Report Results table shows and the metrics the
     "How to read this report" bullet list explains, and reports the difference.

    CHROMIQ_SETTINGS_FILE=… CHROMIQ_PRESETS_DIR=… \\
        python scripts/drive_k25_report_window_bugs.py <project> <out>
"""
from __future__ import annotations

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


def results_rows(txt: str) -> "list[str]":
    """The metric labels the Report Results table lists, in order."""
    from workflow.compliance_sets import ROWS
    from core.i18n import tr
    out = []
    body = txt.split("Report Results", 1)[-1]
    body = body.split("Overview of Measurement Metrics", 1)[0]
    for row in ROWS:
        lab = tr(row.label)
        if lab and lab in body:
            out.append(lab)
    return out


def bullet_metrics(txt: str) -> "list[str]":
    """The lead-in of each bullet in "How to read this report"'s first list."""
    seg = txt.split("How to read this report", 1)[-1]
    seg = seg.split("The five verdict words", 1)[0]
    out = []
    for line in seg.splitlines():
        s = line.strip()
        if not s or s.startswith("This report compares"):
            continue
        # the QTextBrowser renders <li> as a bullet glyph
        s = s.lstrip("•·-– ").strip()
        if not s:
            continue
        head = re.split(r"[:—]", s, 1)[0].strip()
        if head and len(head) < 90:
            out.append(head)
    return out


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
    work = Path(tempfile.mkdtemp(prefix="chromiq-k25-"))
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
    print(f"    opening on {ti3.relative_to(dest)}", flush=True)

    dlg = MeasurementReportDialog(settings, None, initial_ti3=ti3)
    dlg.resize(1480, 1040)
    dlg.show(); dlg.raise_(); dlg.activateWindow()
    pump(app, 3000)
    print(f"    window on screen: {dlg.isVisible()}", flush=True)
    res: dict = {"project": str(src), "copy": str(dest)}

    # -- pick the entry whose NAME starts with 2026-11-16 10:00 -------------
    entries = [(i, dlg._saved_combo.itemText(i))
               for i in range(dlg._saved_combo.count())]
    res["entries"] = [t for _i, t in entries]
    want = [i for i, t in entries if t.startswith("2026-11-16 10:00")]
    assert want, f"no 2026-11-16 entry: {res['entries']}"
    idx = want[0]
    dlg._saved_combo.setCurrentIndex(idx)
    pump(app, 1400)
    name = dlg._saved_combo.currentText()
    txt = dlg._view.toPlainText()
    (out / "A-loaded.txt").write_text(txt, encoding="utf-8")
    created_line = next((l for l in txt.splitlines() if l.startswith("Created:")), "")
    res["bug1"] = {
        "entry_name": name,
        "created_line": created_line,
        "name_stamp": (re.search(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}", name) or [None])
                      and re.search(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}", name).group(0),
        "text_stamp": (re.search(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}", created_line).group(0)
                       if re.search(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}", created_line) else ""),
    }
    res["bug1"]["same"] = (res["bug1"]["name_stamp"] == res["bug1"]["text_stamp"])
    print(f"  BUG 1  entry  = {name}", flush=True)
    print(f"         text   = {created_line}", flush=True)
    print(f"         same?  = {res['bug1']['same']}", flush=True)

    ok, why, tries, same = capture_settled(
        app, dlg, out / "A-loaded-1.png", out / "A-loaded-2.png")
    print(f"    photograph A: {ok} {why}; identical: {same}/{tries}", flush=True)
    res["photo_a"] = {"taken": ok, "why": why, "identical": same}

    # -- bug 3: what the results table lists vs what the guide explains -----
    res["bug3"] = {
        "type_before": dlg._type_combo.currentText(),
        "results_rows": results_rows(txt),
        "guide_bullets": bullet_metrics(txt),
    }
    print(f"  BUG 3  results rows  = {res['bug3']['results_rows']}", flush=True)
    print(f"         guide bullets = {res['bug3']['guide_bullets']}", flush=True)

    # -- bug 2: move ONLY "Judged against" ----------------------------------
    before_type = dlg._type_combo.currentText()
    before_type_id = dlg._type_combo.currentData()
    sets = [(i, dlg._set_combo.itemText(i), dlg._set_combo.itemData(i))
            for i in range(dlg._set_combo.count())]
    res["sets"] = [s[1] for s in sets]
    tight = [i for i, t, d in sets if d == "chromiq_tight"]
    assert tight, f"no tight set: {res['sets']}"
    dlg._set_combo.setCurrentIndex(tight[0])
    pump(app, 1600)
    after_type = dlg._type_combo.currentText()
    after_type_id = dlg._type_combo.currentData()
    res["bug2"] = {
        "set_before": "ChromIQ default (recommended)",
        "set_after": dlg._set_combo.currentText(),
        "type_before": before_type, "type_before_id": before_type_id,
        "type_after": after_type, "type_after_id": after_type_id,
        "type_moved": before_type_id != after_type_id,
    }
    print(f"  BUG 2  type before = {before_type!r} ({before_type_id})", flush=True)
    print(f"         type after  = {after_type!r} ({after_type_id})", flush=True)
    print(f"         MOVED       = {res['bug2']['type_moved']}", flush=True)
    (out / "B-after-set-change.txt").write_text(
        dlg._view.toPlainText(), encoding="utf-8")
    ok, why, tries, same = capture_settled(
        app, dlg, out / "B-after-set-change-1.png", out / "B-after-set-change-2.png")
    print(f"    photograph B: {ok} {why}; identical: {same}/{tries}", flush=True)
    res["photo_b"] = {"taken": ok, "why": why, "identical": same}

    # -- the widths B8-425 is about -----------------------------------------
    widths = {}
    for w in (1000, 1200, 1500):
        dlg.resize(w, 1040)
        pump(app, 900)
        widths[str(w)] = {
            "window": [dlg.width(), dlg.height()],
            "minimum": [dlg.minimumSizeHint().width(),
                        dlg.minimumSizeHint().height()],
            "set_combo": [dlg._set_combo.width(), dlg._set_combo.height()],
            "type_combo": [dlg._type_combo.width(), dlg._type_combo.height()],
            "saved_combo": [dlg._saved_combo.width(), dlg._saved_combo.height()],
            "view": [dlg._view.width(), dlg._view.height()],
        }
        ok, why, tries, same = capture_settled(
            app, dlg, out / f"C-{w}px-1.png", out / f"C-{w}px-2.png")
        widths[str(w)]["photo"] = {"taken": ok, "why": why, "identical": same}
        print(f"    {w} px: min={widths[str(w)]['minimum']} photo={ok}/{same}",
              flush=True)
    res["widths"] = widths

    json.dump(res, (out / "result.json").open("w", encoding="utf-8"),
              indent=2, default=str)
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
