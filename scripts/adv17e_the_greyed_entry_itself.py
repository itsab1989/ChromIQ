#!/usr/bin/env python3
"""Adversary 17e / P3: "the greyed entry itself says why when you open the list".

Round 4 measured `_WHEN_HELP`'s old ending ("the line under the pulldown says
why") false in six of six demo projects. The replacement moves the claim onto
the ROW. The row's own text is "Validation print check (ISO 12647-8)", which
says nothing about why; the reason is hung on the row as a `ToolTipRole`.

So: open the list in a real window and find out whether a reader can get that
text off the greyed row at all.
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
from PyQt6.QtCore import QEvent, QPoint, Qt                      # noqa: E402
from PyQt6.QtGui import QHelpEvent                               # noqa: E402
from PyQt6.QtWidgets import (QApplication, QDialog, QMessageBox,  # noqa: E402
                             QToolTip)
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
    work = Path(tempfile.mkdtemp(prefix="chromiq-adv17e3-"))
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
    from workflow.measurement_report import REPORT_TYPE_ISO_7, REPORT_TYPE_ISO_8
    apply_appearance(app, None, "dark")

    projects = sorted(p.name for p in pack.iterdir()
                      if p.is_dir() and p.name.startswith("Report-Limits-"))
    res = {"claim": ("the greyed entry itself says why when you open the list"),
           "projects": {}}
    for project in projects[:2]:
        shutil.copytree(pack / project, work / project, dirs_exist_ok=True)
        ti3s = sorted((work / project).glob("runs/*/verifications/*/*.ti3"))
        if not ti3s:
            continue
        fm = FileManager(settings); fm.set_target_name(project)
        dlg = MeasurementReportDialog(settings, None, initial_ti3=ti3s[0])
        dlg.resize(1500, 1000); dlg.show(); dlg.raise_(); pump(app, 1600)
        combo = dlg._type_combo
        combo.showPopup(); pump(app, 900)
        view = combo.view()
        popup = view.window()
        rows = []
        model = combo.model()
        for n in range(combo.count()):
            tid = combo.itemData(n)
            item = model.item(n) if hasattr(model, "item") else None
            enabled = bool(item.isEnabled()) if item is not None else None
            row = {"n": n, "text": combo.itemText(n), "id": tid,
                   "selectable": enabled,
                   "tooltip_role": plain(
                       combo.itemData(n, Qt.ItemDataRole.ToolTipRole))}
            if tid in (REPORT_TYPE_ISO_7, REPORT_TYPE_ISO_8):
                # WHAT A READER GETS BY HOVERING THE GREYED ROW. The view
                # answers a ToolTip help event; whether it answers one over a
                # DISABLED row is the whole question.
                idx = model.index(n, 0)
                r = view.visualRect(idx)
                QToolTip.hideText(); pump(app, 200)
                pos = r.center()
                gpos = view.viewport().mapToGlobal(pos)
                ev = QHelpEvent(QEvent.Type.ToolTip, pos, gpos)
                QApplication.sendEvent(view.viewport(), ev)
                pump(app, 700)
                row["tooltip_shown_on_hover"] = bool(QToolTip.isVisible())
                row["tooltip_text_on_hover"] = plain(QToolTip.text())
                row["row_text_says_why"] = ("Not available" in combo.itemText(n)
                                            or "yet" in combo.itemText(n))
                if tid == REPORT_TYPE_ISO_8:
                    capture_window(popup, out / f"popup-{project}.png")
                    capture_window(dlg, out / f"popup-dialog-{project}.png")
            rows.append(row)
        res["projects"][project] = {
            "window_on_screen": bool(dlg.isVisible()),
            "popup_visible": bool(popup.isVisible()),
            "rows": rows}
        for r in rows:
            if r["id"] in (REPORT_TYPE_ISO_7, REPORT_TYPE_ISO_8):
                print(f"  {project} :: {r['text']!r} selectable={r['selectable']} "
                      f"row_text_says_why={r['row_text_says_why']} "
                      f"tooltip_on_hover={r.get('tooltip_shown_on_hover')} "
                      f"-> {r.get('tooltip_text_on_hover','')[:80]!r}",
                      flush=True)
        combo.hidePopup(); pump(app, 300)
        dlg.close(); pump(app, 250)

    (out / "adv17e-the-greyed-entry.json").write_text(
        json.dumps(res, indent=2, ensure_ascii=False), encoding="utf-8")
    print("    written", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
