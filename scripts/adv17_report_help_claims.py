#!/usr/bin/env python3
"""Adversary round 17: the three checkable claims in the new type/pairing help.

Drives the REAL Measurement Report window on real demo projects and reads the
rows the window would DRAW, per report type and per limit set.

Claim A  "Printing record grades nothing at all: every row of it reads INFO
          whichever set is beside it"
Claim B  "an ordinary test chart has none and the rows read N-A" (paper/solid)
Claim C  "The report names every row it could not compute and why"

Run::

    CHROMIQ_SETTINGS_FILE=... CHROMIQ_PRESETS_DIR=... \
        python scripts/adv17_report_help_claims.py <pack> <out-dir>

Never QT_QPA_PLATFORM=offscreen. This is a driver.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
try:
    import PyQt6.QtWebEngineWidgets  # noqa: F401
except ImportError:
    pass
from PyQt6.QtWidgets import QApplication, QDialog, QMessageBox   # noqa: E402
sys.path.insert(0, str(ROOT / "scripts"))                        # noqa: E402
from onscreen_capture import capture_window, session_is_locked   # noqa: E402


def pump(app, ms=250):
    end = time.monotonic() + ms / 1000.0
    while time.monotonic() < end:
        app.processEvents()
        time.sleep(0.01)


def plain(html):
    return " ".join(re.sub("<[^>]+>", " ", html).split())


def main() -> int:
    assert os.environ.get("CHROMIQ_SETTINGS_FILE"), "SANDBOX THE SETTINGS FIRST"
    assert os.environ.get("CHROMIQ_PRESETS_DIR"), "SANDBOX THE PRESETS FIRST"
    pack = Path(sys.argv[1]).resolve()
    out = Path(sys.argv[2]).resolve()
    out.mkdir(parents=True, exist_ok=True)

    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("ChromIQ")
    from ui.styles import WinButtonLayoutStyle
    app.setStyle(WinButtonLayoutStyle("Fusion"))
    from core.settings import AppSettings
    work = Path(tempfile.mkdtemp(prefix="chromiq-adv17-"))
    settings = AppSettings()
    settings.set("custom_output_path", str(work))
    settings.set("appearance", "dark")
    assert settings.get("custom_output_path", "") == str(work), "SANDBOX FAILED"

    QDialog.exec = lambda self: 1                 # type: ignore[assignment]
    for m in ("warning", "critical", "information", "question"):
        setattr(QMessageBox, m, staticmethod(lambda *a, **k: 0))

    from core.file_manager import FileManager
    from ui.theme import apply_appearance
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    from workflow.measurement_report import REPORT_TYPE_MENU
    from workflow.compliance_sets import SETS
    apply_appearance(app, None, "dark")

    findings = {}
    photos = []
    for project in sorted(p.name for p in pack.iterdir()
                          if p.is_dir() and p.name.startswith("Report-Limits-")):
        shutil.copytree(pack / project, work / project, dirs_exist_ok=True)
        ti3s = sorted((work / project).glob("runs/*/verifications/*/*.ti3"))
        if not ti3s:
            continue
        fm = FileManager(settings)
        fm.set_target_name(project)
        dlg = MeasurementReportDialog(settings, None, initial_ti3=ti3s[0])
        dlg.resize(1500, 1000)
        dlg.show()
        dlg.raise_()
        pump(app, 1500)
        runs = dlg._runs_for_report()
        if not runs:
            dlg.close(); continue
        r = runs[0]
        rep = dlg._report or {}
        per_type = {}
        for tid, name, _b, built in REPORT_TYPE_MENU:
            if not built:
                continue
            i = [dlg._type_combo.itemData(n)
                 for n in range(dlg._type_combo.count())].index(tid)
            dlg._type_combo.setCurrentIndex(i)
            pump(app, 150)
            rows, _rec = dlg._verdict_rows(r)
            per_type[name] = {(x.get("row_id") or x.get("key")): x.get("word")
                              for x in rows}
        # …and back to Full colour check for the note check
        i = [dlg._type_combo.itemData(n)
             for n in range(dlg._type_combo.count())].index(
                 REPORT_TYPE_MENU[1][0])
        dlg._type_combo.setCurrentIndex(i)
        pump(app, 150)
        note = dlg._mismatch_text()
        lim = dlg._window_limits()
        findings[project] = {
            "measurement": str(ti3s[0].relative_to(work)),
            "reference_source": rep.get("reference_source"),
            "graded": bool(rep.get("verification")),
            "limit_set": getattr(lim, "set_label", ""),
            "per_type_rows": per_type,
            "chart_mismatch_note": note,
            "window_on_screen": dlg.isVisible(),
        }
        if not photos:
            p = out / f"01-{project}-report-window.png"
            ok, why = capture_window(dlg, p)
            photos.append(p.name if ok else f"REFUSED {why}")
        dlg.close()
        pump(app, 250)

    # --- the two claims, judged
    verdict = {}
    for project, f in findings.items():
        rec = f["per_type_rows"].get("Printing record (not graded)", {})
        full = f["per_type_rows"].get("Full colour check", {})
        verdict[project] = {
            "reference_source": f["reference_source"],
            "limit_set": f["limit_set"],
            "record rows that are NOT INFO":
                {k: v for k, v in rec.items() if v != "INFO"},
            "paper row present in Full colour check":
                "substrate_de00_max" in full,
            "solid row present in Full colour check":
                "solids_de00_max" in full,
            "paper row word": full.get("substrate_de00_max"),
            "solid row word": full.get("solids_de00_max"),
            "mismatch note names the paper row":
                "paper" in (f["chart_mismatch_note"] or "").lower(),
        }
    (out / "claims.json").write_text(json.dumps(
        {"verdict": verdict, "raw": findings, "photos": photos,
         "locked_at_start": session_is_locked(),
         "sets": [s.id for s in SETS]},
        indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(verdict, indent=2, ensure_ascii=False))
    print("photos:", photos)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
