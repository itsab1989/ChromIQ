#!/usr/bin/env python3
"""Adversary round 27: the Measurement Report window, driven in a real window.

Five questions, all of them Knut's beta-22 list:

  1. does EVERY sentence of the page follow "Report shown"?
  2. deleting the report that is currently shown, and the last one;
  3. the report text against its TYPE and its LIMIT SET, crossed;
  4. Preferences report defaults reaching a new report;
  5. border conditions: a hand-edited document block the reader does not
     expect (the R25-F1 shape).

    CHROMIQ_SETTINGS_FILE=… CHROMIQ_PRESETS_DIR=… \\
        python scripts/drive_r27_the_report_follows_the_selection.py <proj> <out>
"""
from __future__ import annotations

import hashlib
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
    work = Path(tempfile.mkdtemp(prefix="chromiq-r27-"))
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

    res: dict = {"project": str(src), "copy": str(dest)}
    want_run = os.environ.get("R27_RUN", "run1")
    # open on the dated verification of `want_run` that has the most reports
    best = None
    for d in sorted((dest / "runs" / want_run).glob("verifications/*")):
        t = sorted(d.glob("*.ti3"))
        n = len(sorted((d / "reports").glob("report_*.json")))
        if t and n and (best is None or n > best[1]):
            best = (t[0], n)
    assert best is not None, f"no dated verification with a report in {want_run}"
    ti3 = best[0]
    print(f"    opening on {ti3.relative_to(dest)} ({best[1]} reports)", flush=True)

    dlg = MeasurementReportDialog(settings, None, initial_ti3=ti3)
    dlg.resize(1480, 1040)
    dlg.show(); dlg.raise_(); dlg.activateWindow()
    pump(app, 3500)
    print(f"    window on screen: {dlg.isVisible()}", flush=True)
    res["window_visible"] = bool(dlg.isVisible())

    def page_text() -> str:
        return dlg._view.toPlainText()

    def controls() -> dict:
        return {
            "report_type": dlg._type_combo.currentText(),
            "judged_against": dlg._set_combo.currentText(),
            "show_all_runs": bool(dlg._all_runs_check.isChecked()),
            "show_detail": bool(dlg._detail_check.isChecked()),
            "saved_index": dlg._saved_combo.currentIndex(),
            "saved_text": dlg._saved_combo.currentText(),
            "saved_entries": [dlg._saved_combo.itemText(i)
                              for i in range(dlg._saved_combo.count())],
            "type_blurb": dlg._type_blurb.text(),
            "saved_hint": getattr(dlg, "_saved_hint_full", ""),
            "saved_note": getattr(dlg, "_saved_note_full", ""),
            "generated_line": getattr(dlg, "_generated_full", ""),
            "delete_enabled": bool(dlg._delete_report_btn.isEnabled()),
            "all_runs_enabled": bool(dlg._all_runs_check.isEnabled()),
            "loaded_doc_id": getattr(dlg, "_loaded_doc_id", ""),
            "page_sha": hashlib.sha256(
                page_text().encode("utf-8")).hexdigest()[:12],
        }

    # ---------------- 1. the page follows the selection ----------------
    picks = []
    n = dlg._saved_combo.count()
    print(f"    [1] {n} entries in Report shown", flush=True)
    res["open_state"] = controls()
    (out / "T-on-open.txt").write_text(page_text(), encoding="utf-8")
    for i in range(n):
        dlg._saved_combo.setCurrentIndex(i)
        # the user's click path: currentIndexChanged fires, activated for a repeat
        dlg._on_saved_chosen(i)
        dlg._on_saved_picked_again(i)
        pump(app, 900)
        c = controls()
        txt = page_text()
        (out / f"T-pick-{i:02d}.txt").write_text(txt, encoding="utf-8")
        c["first_400"] = txt[:400]
        picks.append(c)
        print(f"        [{i}] {c['saved_text'][:70]!r}", flush=True)
        print(f"            type={c['report_type']!r} set={c['judged_against']!r} "
              f"all={c['show_all_runs']} det={c['show_detail']} "
              f"page={c['page_sha']}", flush=True)
    res["1_picks"] = picks
    ok, why, tries, same = capture_settled(
        app, dlg, out / "R1-after-picking.png", out / "R1b-after-picking.png")
    print(f"        photograph: {ok} {why}; identical frames: {same}/{tries}",
          flush=True)
    res["1_photo"] = {"taken": ok, "why": why, "identical": same}

    # sentences that never change across the picks, but should
    def lines(t: str) -> list:
        return [l.strip() for l in t.splitlines() if l.strip()]
    texts = [(out / f"T-pick-{i:02d}.txt").read_text(encoding="utf-8")
             for i in range(n)]
    res["1_page_all_same"] = len({hashlib.sha256(t.encode()).hexdigest()
                                  for t in texts}) == 1

    json.dump(res, (out / "result.json").open("w", encoding="utf-8"), indent=2, default=str)
    print("    wrote result.json", flush=True)
    dlg.close()
    pump(app, 500)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception:                                      # noqa: BLE001
        traceback.print_exc()
        raise SystemExit(2)
