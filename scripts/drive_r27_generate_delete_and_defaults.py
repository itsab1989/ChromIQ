#!/usr/bin/env python3
"""Adversary round 27, part two: generate, delete, regenerate, and the
Preferences defaults, driven in a real window.

  A. Generate twice in one second, and count the documents.
  B. Delete the report that is currently SHOWN: does the page follow?
  C. Delete down to the last report of a dated verification: is it refused?
  D. The Preferences report defaults reach a NEW report, and no existing one.

    CHROMIQ_SETTINGS_FILE=… CHROMIQ_PRESETS_DIR=… \\
        python scripts/drive_r27_generate_delete_and_defaults.py <proj> <out>
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
    work = Path(tempfile.mkdtemp(prefix="chromiq-r27b-"))
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
    run_name = os.environ.get("R27_RUN", "run1")

    def live_files() -> list:
        return sorted(str(p.relative_to(dest))
                      for p in dest.glob("runs/*/**/reports/report_*.json"))

    def old_files() -> list:
        return sorted(str(p.relative_to(dest))
                      for p in dest.glob("runs/**/old/**/report_*.json"))

    best = None
    for d in sorted((dest / "runs" / run_name).glob("verifications/*")):
        t = sorted(d.glob("*.ti3"))
        n = len(sorted((d / "reports").glob("report_*.json")))
        if t and n and (best is None or n > best[1]):
            best = (t[0], n)
    assert best is not None
    ti3 = best[0]
    print(f"    opening on {ti3.relative_to(dest)}", flush=True)

    dlg = MeasurementReportDialog(settings, None, initial_ti3=ti3)
    dlg.resize(1480, 1040)
    dlg.show(); dlg.raise_(); dlg.activateWindow()
    pump(app, 3200)
    print(f"    window on screen: {dlg.isVisible()}", flush=True)

    def state() -> dict:
        txt = dlg._view.toPlainText()
        return {
            "entries": [dlg._saved_combo.itemText(i)
                        for i in range(dlg._saved_combo.count())],
            "index": dlg._saved_combo.currentIndex(),
            "current": dlg._saved_combo.currentText(),
            "type": dlg._type_combo.currentText(),
            "set": dlg._set_combo.currentText(),
            "all_runs": bool(dlg._all_runs_check.isChecked()),
            "detail": bool(dlg._detail_check.isChecked()),
            "delete_enabled": bool(dlg._delete_report_btn.isEnabled()),
            "note": getattr(dlg, "_saved_note_full", ""),
            "hint": getattr(dlg, "_saved_hint_full", ""),
            "blurb": getattr(dlg, "_type_blurb_full", ""),
            "page_sha": hashlib.sha256(txt.encode()).hexdigest()[:12],
            "page_head": txt[:220],
            "live": len(live_files()),
            "old": len(old_files()),
        }

    steps: list = []

    def note(label: str) -> dict:
        st = state()
        st["step"] = label
        steps.append(st)
        print(f"    [{label}] entries={len(st['entries'])} live={st['live']} "
              f"old={st['old']} idx={st['index']} del={st['delete_enabled']} "
              f"page={st['page_sha']}", flush=True)
        print(f"        current={st['current'][:80]!r}", flush=True)
        if st["note"]:
            print(f"        note={st['note'][:100]!r}", flush=True)
        return st

    note("00-open")

    # ---- A. generate twice inside one second --------------------------
    dlg._on_generate_report()
    dlg._on_generate_report()
    pump(app, 1500)
    a = note("01-generate-twice-in-one-second")
    res["A_generate_twice"] = a

    # ---- B. delete the report that is SHOWN ---------------------------
    before = state()
    dlg._on_delete_report()
    pump(app, 1200)
    b = note("02-deleted-the-shown-report")
    res["B_delete_shown"] = {"before": before, "after": b,
                             "asked": list(asked)}
    ok, why, tries, same = capture_settled(
        app, dlg, out / "R2-after-deleting-the-shown-report.png",
        out / "R2b-after-deleting-the-shown-report.png")
    print(f"        photograph: {ok} {why}; identical: {same}/{tries}", flush=True)

    # ---- C. delete until the last one of a date is refused -----------
    for k in range(12):
        n_before = len(live_files())
        if not dlg._delete_report_btn.isEnabled():
            # move to the next entry that can be deleted
            moved = False
            for i in range(1, dlg._saved_combo.count()):
                if i == dlg._saved_combo.currentIndex():
                    continue
                dlg._saved_combo.setCurrentIndex(i)
                dlg._on_saved_chosen(i)
                dlg._on_saved_picked_again(i)
                pump(app, 500)
                if dlg._delete_report_btn.isEnabled():
                    moved = True
                    break
            if not moved:
                note(f"03-{k:02d}-nothing-left-to-delete")
                break
        dlg._on_delete_report()
        pump(app, 900)
        st = note(f"03-{k:02d}-after-a-delete")
        if len(live_files()) == n_before:
            break
    res["C_delete_to_the_last"] = steps[-1]

    # ---- D. the Preferences defaults -------------------------------
    from workflow.measurement_report import REPORT_TYPE_RECORD
    settings.set("report_default_type", REPORT_TYPE_RECORD)
    settings.set("report_default_show_all_runs", False)
    settings.set("report_default_show_details", False)
    for i in range(dlg._saved_combo.count()):
        if dlg._saved_combo.itemData(i) == "new:":
            dlg._saved_combo.setCurrentIndex(i)
            dlg._on_saved_chosen(i)
            dlg._on_saved_picked_again(i)
            break
    pump(app, 900)
    d1 = note("04-new-report-after-changing-the-defaults")
    res["D_defaults"] = {"after_new_report": d1,
                         "wanted_type": REPORT_TYPE_RECORD,
                         "wanted_all_runs": False,
                         "wanted_detail": False}
    ok, why, tries, same = capture_settled(
        app, dlg, out / "R3-new-report-with-the-new-defaults.png",
        out / "R3b-new-report-with-the-new-defaults.png")
    print(f"        photograph: {ok} {why}; identical: {same}/{tries}", flush=True)

    res["steps"] = steps
    res["live_files_end"] = live_files()
    res["old_files_end"] = old_files()
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
