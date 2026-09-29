#!/usr/bin/env python3
"""B8-388 / B8-391 / B8-392 — Knut's Measurement Report defaults, on screen.

Driven in REAL windows, on a copy of a real project, with the settings and the
presets sandboxed. Nothing of the owner's is touched: the project is copied
into a temp output root first and everything happens there.

  1. Preferences ▸ Reports: the frame's new name, the "Report type, default"
     pulldown and the two tick boxes, photographed.
  2. The Measure tab: "Save measurement report" on screen, and what it does
     when it is off and when it is on.
  3. What a measurement WRITES, before and after: the same writer the app uses
     (`TabMeasure._maybe_save_measurement_report`), and the document block the
     record now carries.
  4. The Measurement Report window: "New report…" at the top of "Report shown",
     what the window opens on, and what choosing "New report…" loads.
  5. The unlock question, word for word, after B8-391 took the false clause
     out of it.

    CHROMIQ_SETTINGS_FILE=… CHROMIQ_PRESETS_DIR=… \\
        python scripts/drive_b388_the_report_defaults.py <project> <out>
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
import tempfile
import time
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


def pump(app, ms: int = 300) -> None:
    end = time.monotonic() + ms / 1000.0
    while time.monotonic() < end:
        app.processEvents()
        time.sleep(0.01)


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


def shoot(app, win, out: Path, name: str, log: dict) -> None:
    """Two frames, kept only when they agree — a moving window is not proof."""
    a, b = out / f"{name}.png", out / f".{name}-second.png"
    ok = False
    why = ""
    for _ in range(5):
        pump(app, 800)
        ok1, why1 = capture_window(win, a)
        pump(app, 800)
        ok2, why2 = capture_window(win, b)
        why = why1 or why2
        if ok1 and ok2 and _frames_match(a, b):
            ok = True
            break
    b.unlink(missing_ok=True)
    log[name] = {"photographed": ok, "why_not": why}
    print(f"    {name}: {'PHOTOGRAPHED' if ok else 'NOT photographed: ' + why}",
          flush=True)


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
    work = Path(tempfile.mkdtemp(prefix="chromiq-b388-"))
    settings = AppSettings()
    settings.set("custom_output_path", str(work))
    settings.set("appearance", "dark")
    settings.set("language", "en")
    assert settings.get("custom_output_path", "") == str(work), "SANDBOX FAILED"
    dest = work / src.name
    shutil.copytree(src, dest)
    print(f"    project copied to {dest}", flush=True)
    print(f"    screen locked at start: {session_is_locked()}", flush=True)
    from ui.theme import apply_appearance
    apply_appearance(app, None, "dark")
    res: dict = {"project": str(src), "copy": str(dest), "shots": {}}
    shots = res["shots"]

    def report_files() -> dict:
        found = {}
        for f in sorted(dest.glob("runs/**/reports/report_*.json")):
            try:
                d = json.loads(f.read_text(encoding="utf-8"))
            except Exception:                              # noqa: BLE001
                continue
            doc = d.get("document") or {}
            found[str(f.relative_to(dest))] = {
                "document": bool(doc),
                "scope": doc.get("scope"),
                "all_runs": doc.get("all_runs"),
                "detail": doc.get("detail"),
                "type": doc.get("type") or d.get("report_type"),
                "sha": hashlib.sha256(f.read_bytes()).hexdigest()[:12],
            }
        return found

    # ---------------------------------------------------------------- 1. prefs
    from ui.dialogs.settings_dialog import SettingsDialog
    prefs = SettingsDialog(settings)
    # find the Reports page by the frame's new name
    from PyQt6.QtWidgets import QGroupBox, QTabWidget
    tabs = prefs.findChildren(QTabWidget)
    for tw in tabs:
        for i in range(tw.count()):
            if "Report" in tw.tabText(i):
                tw.setCurrentIndex(i)
    prefs.resize(900, 820)
    prefs.show()
    prefs.raise_()
    prefs.activateWindow()
    pump(app, 2500)
    res["preferences"] = {
        "frame_titles": [g.title() for g in prefs.findChildren(QGroupBox)
                         if "Report" in g.title() or "Saving" in g.title()],
        "report_type_default": prefs._report_type_default_combo.currentData(),
        "report_type_default_text": prefs._report_type_default_combo.currentText(),
        "show_all_runs_default": bool(
            prefs._report_all_runs_default_check.isChecked()),
        "show_details_default": bool(
            prefs._report_details_default_check.isChecked()),
        "save_after_each_measurement": bool(prefs._save_report_check.isChecked()),
        "entries_in_the_type_pulldown": [
            (prefs._report_type_default_combo.itemText(i),
             prefs._report_type_default_combo.itemData(i))
            for i in range(prefs._report_type_default_combo.count())],
    }
    shoot(app, prefs, out, "A-preferences-reports-defaults", shots)
    prefs.close()
    pump(app, 400)

    # ------------------------------------------------------- 2/3. the Measure tab
    from core.argyll_runner import ArgyllRunner
    from ui.tabs.tab_measure import TabMeasure
    tab = TabMeasure(ArgyllRunner(settings), settings)
    tab.resize(1200, 900)
    tab.show()
    tab.raise_()
    tab.activateWindow()
    pump(app, 2000)
    res["measure_tab"] = {
        "save_report_control_on_screen": bool(
            tab._save_report_cb.isVisible()),
        "label": tab._save_report_cb.text(),
        "checked_at_open": bool(tab._save_report_cb.isChecked()),
        "preference": bool(settings.get("save_measurement_report", True)),
    }
    shoot(app, tab, out, "B-measure-tab-save-measurement-report", shots)

    ti3s = sorted(dest.glob("runs/*/verifications/*/*.ti3"))
    assert ti3s, "no dated verification in this project"
    ti3 = ti3s[-1]
    res["measurement_driven"] = str(ti3.relative_to(dest))
    res["before_the_measurement"] = report_files()

    tab._save_report_cb.setChecked(False)
    pump(app, 200)
    tab._maybe_save_measurement_report(ti3)
    pump(app, 800)
    res["with_the_box_off"] = report_files()

    tab._save_report_cb.setChecked(True)
    pump(app, 200)
    tab._maybe_save_measurement_report(ti3)
    pump(app, 1200)
    res["after_the_measurement"] = report_files()
    written = sorted(set(res["after_the_measurement"])
                     - set(res["before_the_measurement"]))
    res["written"] = written
    if written:
        f = dest / written[-1]
        res["the_new_records_document"] = (
            json.loads(f.read_text(encoding="utf-8")).get("document"))
    tab.close()
    pump(app, 400)

    # ------------------------------------------------ 4/5. the report window
    asked: list = []
    from ui.dialogs.measurement_report_dialog import (NEW_REPORT_KEY,
                                                      MeasurementReportDialog)

    def confirm(self, title, body):
        asked.append({"title": str(title), "body": str(body)})
        return True
    MeasurementReportDialog._confirm = confirm        # type: ignore[assignment]
    QDialog.exec = lambda self: 1                     # type: ignore[assignment]
    for m in ("warning", "critical", "information", "question"):
        setattr(QMessageBox, m, staticmethod(lambda *a, **k: 0))

    dlg = MeasurementReportDialog(settings, None, initial_ti3=ti3)
    dlg.resize(1500, 1040)
    dlg.show()
    dlg.raise_()
    dlg.activateWindow()
    pump(app, 3500)

    def controls() -> dict:
        return {
            "report_type": dlg._type_combo.currentText(),
            "judged_against": dlg._set_combo.currentText(),
            "show_all_runs": bool(dlg._all_runs_check.isChecked()),
            "show_all_runs_enabled": bool(dlg._all_runs_check.isEnabled()),
            "show_detail": bool(dlg._detail_check.isChecked()),
            "report_shown_index": dlg._saved_combo.currentIndex(),
            "report_shown_text": dlg._saved_combo.currentText(),
            "entries": [dlg._saved_combo.itemText(i)
                        for i in range(dlg._saved_combo.count())],
            "loaded_document": dlg._loaded_doc_id,
        }

    res["window_on_open"] = controls()
    res["new_report_is_first"] = (
        dlg._saved_combo.itemData(0) == NEW_REPORT_KEY)
    shoot(app, dlg, out, "C-report-window-on-open", shots)

    # the pulldown itself, open, so "New report…" can be SEEN at the top
    dlg._saved_combo.showPopup()
    pump(app, 1200)
    popup = dlg._saved_combo.view().window()
    shoot(app, popup, out, "D-report-shown-pulldown-new-report-first", shots)
    dlg._saved_combo.hidePopup()
    pump(app, 600)

    # choose "New report…" and see what it loads
    dlg._saved_combo.setCurrentIndex(0)
    pump(app, 1500)
    res["after_choosing_new_report"] = controls()
    shoot(app, dlg, out, "E-new-report-loads-the-defaults", shots)

    # …and the unlock question, after B8-391
    settings.set("compliance_allow_edit_after_measurement", True)
    dlg._forget_limits()
    dlg._sync_limit_controls()
    pump(app, 600)
    before_unlock = report_files()
    if dlg._unlock_check.isEnabled():
        dlg._unlock_check.setChecked(True)
        pump(app, 1500)
    res["unlock"] = {
        "offered": bool(dlg._unlock_check.isEnabled()),
        "questions": asked[-1:] if asked else [],
        "files_rewritten": sorted(
            k for k, v in report_files().items()
            if k in before_unlock and v["sha"] != before_unlock[k]["sha"]),
        "copies_in_old": sorted(
            str(p.relative_to(dest))
            for p in dest.glob("runs/**/reports/old/**/report_*.json")),
    }
    shoot(app, dlg, out, "F-after-the-unlock", shots)
    dlg.close()
    pump(app, 400)

    (out / "the-report-defaults.json").write_text(
        json.dumps(res, indent=1), encoding="utf-8")
    print(json.dumps({k: res[k] for k in (
        "preferences", "measure_tab", "window_on_open",
        "after_choosing_new_report", "written", "unlock")}, indent=1))
    print(f"\n    wrote {out / 'the-report-defaults.json'}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
