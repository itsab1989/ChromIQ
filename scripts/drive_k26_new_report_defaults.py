#!/usr/bin/env python3
"""Knut, beta 26: "New report…" must start from Preferences ▸ Reports.

> *"When selecting 'New report…' in Report shown, then the Judged against is
> set to Quick check, which is not set as the default limit set in the Report
> Limits window. The Judged against, report type, and the two checkboxes shall
> be set to the set default value defined in Preferences->Reports-> inside
> Measurement Report Defaults."*

This measures, on a REAL window, for every project in his demo pack and every
run in it: what Preferences holds, whether the run is bound and to what, and
what the four controls read after "New report…" is chosen. It also records
whether "Unlock this run's limits" is on screen, and what the OLD visibility
rule would have said about it, so the two can be compared without a second
build.

    export CHROMIQ_SETTINGS_FILE=/tmp/chromiq-k26/settings.ini
    export CHROMIQ_PRESETS_DIR=/tmp/chromiq-k26/presets
    python scripts/drive_k26_new_report_defaults.py <demo-pack-root> <out>
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
from PyQt6.QtWidgets import QApplication                         # noqa: E402
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
        return x.shape == y.shape and bool((np.abs(x - y).sum(axis=2) > tol).sum() == 0)
    except Exception:                                      # noqa: BLE001
        return False


def photo(app, win, out: Path, tag: str, tries: int = 3) -> dict:
    ok = ok2 = False
    why = ""
    for _ in range(tries):
        pump(app, 700)
        ok, why = capture_window(win, out / f"{tag}-1.png")
        pump(app, 700)
        ok2, why2 = capture_window(win, out / f"{tag}-2.png")
        why = why or why2
        if ok and ok2 and _frames_match(out / f"{tag}-1.png", out / f"{tag}-2.png"):
            return {"taken": True, "identical": True, "why": why}
    return {"taken": bool(ok and ok2), "identical": False, "why": why}


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
    work = Path(tempfile.mkdtemp(prefix="chromiq-k26-def-"))
    settings = AppSettings()
    settings.set("custom_output_path", str(work))
    settings.set("appearance", "light")
    settings.set("language", "en")
    assert settings.get("custom_output_path", "") == str(work), "SANDBOX FAILED"
    from ui.theme import apply_appearance
    apply_appearance(app, None, "light")
    from core.file_manager import FileManager
    fm = FileManager(settings); del fm

    from ui.dialogs.measurement_report_dialog import (MeasurementReportDialog,
                                                      NEW_REPORT_KEY)
    from workflow.run_compliance import (has_measured_verification, is_bound,
                                         is_locked, may_unlock, run_context_for,
                                         run_limits)

    res: dict = {"locked_at_start": session_is_locked(),
                 "prefs_default_set": settings.get("compliance_default_set", ""),
                 "prefs_default_type": settings.get("report_default_type", ""),
                 "prefs_show_all": settings.get("report_default_show_all_runs", ""),
                 "prefs_show_details": settings.get("report_default_show_details", ""),
                 "rows": []}
    print(f"    screen locked at start: {res['locked_at_start']}", flush=True)

    projects = sorted(p for p in src.iterdir() if (p / "project.json").exists())
    shot_taken = False
    for proj in projects:
        dest = work / proj.name
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(proj, dest)
        for run_dir in sorted((dest / "runs").glob("run*")):
            ti3s = sorted(run_dir.glob("*.ti3")) or sorted(
                run_dir.glob("verifications/*/*.ti3"))
            if not ti3s:
                continue
            ti3 = ti3s[-1]
            row: dict = {"project": proj.name, "run": run_dir.name,
                         "ti3": ti3.name}
            try:
                ctx = run_context_for(ti3)
                run = ctx.run if ctx else None
                lim = run_limits(run, None,
                                 str(settings.get("compliance_default_set",
                                                  "chromiq_default")))
                row["run_bound"] = bool(run is not None and is_bound(run))
                row["run_set"] = lim.set_id
                row["run_locked"] = bool(run is not None and is_locked(run))
                dlg = MeasurementReportDialog(settings, None, initial_ti3=ti3)
                dlg.resize(1480, 1000)
                dlg.show(); dlg.raise_(); dlg.activateWindow()
                pump(app, 1500)
                row["window_visible"] = dlg.isVisible()
                i = dlg._saved_combo.findData(NEW_REPORT_KEY)
                dlg._saved_combo.setCurrentIndex(max(0, i))
                pump(app, 1200)
                row["new_report"] = {
                    "judged": dlg._set_combo.currentText(),
                    "judged_id": str(dlg._set_combo.currentData() or ""),
                    "type": dlg._type_combo.currentText(),
                    "type_id": str(dlg._type_combo.currentData() or ""),
                    "all_runs": dlg._all_runs_check.isChecked(),
                    "detail": dlg._detail_check.isChecked(),
                    "detail_enabled": dlg._detail_check.isEnabled(),
                    "list_enabled": dlg._profile_list.isEnabled(),
                }
                # THE UNLOCK BOX, AND WHAT THE RULE IT REPLACED WOULD HAVE SAID.
                several = len(dlg._distinct_run_dirs()) > 1
                locked_here = dlg._locked_here(run)
                allow = bool(settings.get(
                    "compliance_allow_edit_after_measurement", False))
                row["unlock"] = {
                    "visible_now": dlg._unlock_check.isVisible(),
                    "enabled": dlg._unlock_check.isEnabled(),
                    "tooltip": dlg._unlock_check.toolTip(),
                    "old_rule_would_show": bool(
                        run is not None and not several
                        and (locked_here or bool(lim.unlocked))),
                    "may_unlock": bool(run is not None
                                       and may_unlock(run, allow)
                                       and has_measured_verification(run)),
                }
                if not shot_taken and row["window_visible"]:
                    row["photo"] = photo(app, dlg, out, "new-report-defaults")
                    shot_taken = True
                dlg.close()
                pump(app, 300)
            except Exception:                              # noqa: BLE001
                row["error"] = traceback.format_exc(limit=4)
            res["rows"].append(row)
            print(f"    {row['project']}/{row['run']}: "
                  f"{row.get('new_report', {}).get('judged_id')} "
                  f"(run {row.get('run_set')}, bound={row.get('run_bound')}) "
                  f"unlock now={row.get('unlock', {}).get('visible_now')} "
                  f"old={row.get('unlock', {}).get('old_rule_would_show')}",
                  flush=True)

    (out / "new-report-defaults.json").write_text(
        json.dumps(res, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({k: v for k, v in res.items() if k != "rows"}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
