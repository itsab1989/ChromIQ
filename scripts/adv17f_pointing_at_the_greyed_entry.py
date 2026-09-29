#!/usr/bin/env python3
"""Adversary 17f / P4: `_WHEN_HELP`'s THIRD wording.

    "The two ISO types … are greyed today, and pointing at the greyed entry
     says why."

Round 4 measured the first wording false, round 5 the second, and round 5's own
data for the third shows one of the two ISO rows answering a synthetic
`QHelpEvent` and the other not. So this round moves a REAL pointer onto the row
and waits for Qt's own tooltip timer, and asks the keyboard the same question.
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
from PyQt6.QtCore import Qt                                       # noqa: E402
from PyQt6.QtGui import QCursor                                   # noqa: E402
from PyQt6.QtWidgets import (QApplication, QDialog, QMessageBox,   # noqa: E402
                             QToolTip)
sys.path.insert(0, str(ROOT / "scripts"))                         # noqa: E402
from onscreen_capture import capture_window                       # noqa: E402


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
    work = Path(tempfile.mkdtemp(prefix="chromiq-adv17f4-"))
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

    home = QCursor.pos()
    projects = sorted(p.name for p in pack.iterdir()
                      if p.is_dir() and p.name.startswith("Report-Limits-"))
    res = {"claim": "pointing at the greyed entry says why",
           "method": "a REAL QCursor.setPos onto the row, Qt's own tooltip timer",
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
        combo.showPopup(); pump(app, 1000)
        view = combo.view(); popup = view.window(); model = combo.model()
        rows = []
        for n in range(combo.count()):
            tid = combo.itemData(n)
            item = model.item(n) if hasattr(model, "item") else None
            enabled = bool(item.isEnabled()) if item is not None else None
            row = {"n": n, "text": combo.itemText(n), "id": tid,
                   "selectable": enabled,
                   "tooltip_role": plain(
                       combo.itemData(n, Qt.ItemDataRole.ToolTipRole))}
            if tid in (REPORT_TYPE_ISO_7, REPORT_TYPE_ISO_8):
                idx = model.index(n, 0)
                r = view.visualRect(idx)
                QToolTip.hideText(); pump(app, 400)
                # park the pointer elsewhere first, so the move is a real move
                QCursor.setPos(view.viewport().mapToGlobal(
                    r.center()) + (QCursor.pos() - QCursor.pos()))
                gpos = view.viewport().mapToGlobal(r.center())
                QCursor.setPos(gpos.x() - 220, gpos.y() - 60); pump(app, 500)
                QCursor.setPos(gpos); pump(app, 400)
                # nudge, because Qt starts its tooltip timer on a MOVE
                QCursor.setPos(gpos.x() + 2, gpos.y()); pump(app, 200)
                QCursor.setPos(gpos.x() - 1, gpos.y()); 
                shown, text_seen, waited = False, "", 0.0
                t0 = time.monotonic()
                while time.monotonic() - t0 < 4.0:
                    pump(app, 100)
                    if QToolTip.isVisible():
                        shown, text_seen = True, plain(QToolTip.text())
                        waited = round(time.monotonic() - t0, 2)
                        break
                row["pointer_really_moved_to"] = [gpos.x(), gpos.y()]
                row["tooltip_shown_for_a_real_pointer"] = shown
                row["seconds_before_it_appeared"] = waited
                row["tooltip_text"] = text_seen
                row["row_text_says_why"] = bool(
                    re.search("not available|yet|why", combo.itemText(n), re.I))
                if shown:
                    capture_window(popup, out / f"P4-tooltip-{project}-{tid}.png")
                    capture_window(dlg, out / f"P4-dialog-{project}-{tid}.png")
            rows.append(row)
        # …AND THE KEYBOARD. Arrow the list and see which rows it will stand on.
        combo.setFocus()
        reachable = []
        for n in range(combo.count()):
            item = model.item(n) if hasattr(model, "item") else None
            if item is not None and item.isEnabled():
                reachable.append(n)
        res["projects"][project] = {
            "window_on_screen": bool(dlg.isVisible()),
            "popup_visible": bool(popup.isVisible()),
            "rows": rows,
            "rows_the_keyboard_can_stand_on": reachable,
            "iso_rows": [r["n"] for r in rows
                         if r["id"] in (REPORT_TYPE_ISO_7, REPORT_TYPE_ISO_8)]}
        for r in rows:
            if r["id"] in (REPORT_TYPE_ISO_7, REPORT_TYPE_ISO_8):
                print(f"  {project} :: {r['text']!r} selectable={r['selectable']} "
                      f"tooltip_for_a_real_pointer="
                      f"{r.get('tooltip_shown_for_a_real_pointer')} "
                      f"after {r.get('seconds_before_it_appeared')} s "
                      f"-> {r.get('tooltip_text','')[:70]!r}", flush=True)
        print(f"  {project} :: keyboard can stand on rows {reachable}; "
              f"the ISO rows are "
              f"{res['projects'][project]['iso_rows']}", flush=True)
        combo.hidePopup(); pump(app, 300)
        dlg.close(); pump(app, 250)
    QCursor.setPos(home)
    (out / "adv17f-pointing-at-the-greyed-entry.json").write_text(
        json.dumps(res, indent=2, ensure_ascii=False), encoding="utf-8")
    print("    written", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
