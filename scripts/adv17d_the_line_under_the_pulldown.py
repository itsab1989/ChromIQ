#!/usr/bin/env python3
"""Adversary 17d, probe 5: "the line under the pulldown says why".

`_WHEN_HELP`, new in this change set, ends:

    The two ISO types are for a print that has to answer to a printing
    condition somebody else supplied; they are greyed today, and the line
    under the pulldown says why.

The line under the pulldown is `_set_type_blurb(already or blurb)`, and
`blurb` is `_type_blurb_for(current)` -- the type that is CHOSEN. The two ISO
rows are `_disable_item`ed, so they can never be the chosen one, and
`_not_built_line` is only ever hung on the disabled ROW as its tooltip. On top
of that, `already` wins whenever the run has generated anything, so on such a
run the line is a list of documents.

This reads, from the real window: what the line under the pulldown says, what
each ISO row's own tooltip says, and whether either ISO row can be selected.
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
from PyQt6.QtCore import Qt                                      # noqa: E402
from PyQt6.QtWidgets import QApplication, QDialog, QMessageBox   # noqa: E402
sys.path.insert(0, str(ROOT / "scripts"))                        # noqa: E402
from onscreen_capture import capture_window                      # noqa: E402


def pump(app, ms=250):
    end = time.monotonic() + ms / 1000.0
    while time.monotonic() < end:
        app.processEvents(); time.sleep(0.01)


def plain(html):
    return " ".join(re.sub("<[^>]+>", " ", html or "").split())


def main() -> int:
    assert os.environ.get("CHROMIQ_SETTINGS_FILE"), "SANDBOX THE SETTINGS FIRST"
    assert os.environ.get("CHROMIQ_PRESETS_DIR"), "SANDBOX THE PRESETS FIRST"
    assert os.environ.get("QT_QPA_PLATFORM") != "offscreen", "ON SCREEN"
    pack = Path(sys.argv[1]).resolve()
    out = Path(sys.argv[2]).resolve(); out.mkdir(parents=True, exist_ok=True)
    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("ChromIQ")
    from ui.styles import WinButtonLayoutStyle
    app.setStyle(WinButtonLayoutStyle("Fusion"))
    from core.settings import AppSettings
    work = Path(tempfile.mkdtemp(prefix="chromiq-adv17d5-"))
    settings = AppSettings()
    settings.set("custom_output_path", str(work))
    settings.set("appearance", "dark")
    assert settings.get("custom_output_path", "") == str(work)
    QDialog.exec = lambda self: 1                  # type: ignore[assignment]
    for m in ("warning", "critical", "information", "question"):
        setattr(QMessageBox, m, staticmethod(lambda *a, **k: 0))
    from core.file_manager import FileManager
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    from ui.theme import apply_appearance
    from workflow.measurement_report import (REPORT_TYPE_ISO_7,
                                             REPORT_TYPE_ISO_8)
    apply_appearance(app, None, "dark")

    res = {}
    for project in sorted(p.name for p in pack.iterdir()
                          if p.is_dir() and p.name.startswith("Report-Limits-")):
        shutil.copytree(pack / project, work / project, dirs_exist_ok=True)
        ti3s = sorted((work / project).glob("runs/*/verifications/*/*.ti3"))
        if not ti3s:
            continue
        fm = FileManager(settings); fm.set_target_name(project)
        dlg = MeasurementReportDialog(settings, None, initial_ti3=ti3s[0])
        dlg.resize(1500, 1000); dlg.show(); dlg.raise_(); pump(app, 1600)
        combo = dlg._type_combo
        ids = [combo.itemData(n) for n in range(combo.count())]
        model = combo.model()
        rows = []
        for n, tid in enumerate(ids):
            item = model.item(n) if hasattr(model, "item") else None
            enabled = bool(item.isEnabled()) if item is not None else None
            rows.append({
                "row": combo.itemText(n), "id": tid, "selectable": enabled,
                "row_tooltip": plain(combo.itemData(
                    n, Qt.ItemDataRole.ToolTipRole))})
        line = plain(dlg._type_blurb.text())
        res[project] = {
            "window_on_screen": bool(dlg.isVisible()),
            "chosen_type": dlg._report_type_now(),
            "the_line_under_the_pulldown": line,
            "the_line_says_why_an_ISO_type_is_greyed":
                "Not available yet" in line,
            "rows": rows,
            "iso_rows_selectable": [r["selectable"] for r in rows
                                    if r["id"] in (REPORT_TYPE_ISO_7,
                                                   REPORT_TYPE_ISO_8)],
        }
        print(f"  {project}: line = {line[:140]!r}", flush=True)
        print(f"     says why = "
              f"{res[project]['the_line_says_why_an_ISO_type_is_greyed']}, "
              f"ISO rows selectable = {res[project]['iso_rows_selectable']}",
              flush=True)
        if len(res) == 1:
            ok, why = capture_window(
                dlg, out / "P5-the-line-under-the-pulldown.png")
            res[project]["photo"] = str(ok) if ok else str(why)
        dlg.close(); pump(app, 250)

    # ---- SECOND STATE: a run that has generated NOTHING ------------------
    # `_generated_types_line` returns "No report has been generated for this
    # run yet." rather than "", so `already or blurb` never reaches `blurb`.
    # Proved here by deleting the run's report artefacts and reopening.
    import glob
    for project in sorted(res):
        pdir = work / project
        killed = []
        # EVERY reports/ folder, the dated verifications' included:
        # `generated_report_types` counts `run.dir` AND each verification dir.
        for rep in pdir.rglob("report_*.json"):
            if rep.is_file():
                rep.unlink(); killed.append(str(rep.relative_to(pdir)))
        ti3s = sorted(pdir.glob("runs/*/verifications/*/*.ti3"))
        if not ti3s:
            continue
        fm = FileManager(settings); fm.set_target_name(project)
        dlg = MeasurementReportDialog(settings, None, initial_ti3=ti3s[0])
        dlg.resize(1500, 1000); dlg.show(); dlg.raise_(); pump(app, 1500)
        line = plain(dlg._type_blurb.text())
        res[project]["with_no_report_generated"] = {
            "files_removed": len(killed),
            "the_line_under_the_pulldown": line,
            "the_line_says_why_an_ISO_type_is_greyed":
                "Not available yet" in line,
            "the_line_is_the_type_description":
                "Everything ChromIQ measures" in line,
        }
        print(f"  [no reports] {project}: line = {line[:140]!r}", flush=True)
        if "photo2" not in res[project]:
            ok, why = capture_window(
                dlg, out / "P5b-no-report-generated-yet.png")
            res[project]["photo2"] = str(ok) if ok else str(why)
        dlg.close(); pump(app, 250)
        break

    (out / "adv17d-the-line-under-the-pulldown.json").write_text(
        json.dumps(res, indent=2, ensure_ascii=False), encoding="utf-8")
    bad = [p for p, v in res.items()
           if not v["the_line_says_why_an_ISO_type_is_greyed"]]
    print(f"\n  projects where the line does NOT say why: "
          f"{len(bad)} of {len(res)}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
