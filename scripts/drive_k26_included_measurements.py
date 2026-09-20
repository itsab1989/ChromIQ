#!/usr/bin/env python3
"""Knut, beta 26: what a report STORES is not what was ticked when Generate
was pressed, and the date tag in its name does not follow it either.

Two scenarios, both his, both on his own demo project
``Report-Limits-Threshold-Series`` run 1 (11 dated verifications):

  A. Select a pre-created report, change Report type to "Colour summary", tick
     ALL measurements, press Generate report, answer **Create New**.
     He measured: the new name ends "One date" (he expected "All dates"), and
     re-selecting it leaves ONE row ticked.

  B. Select "New report…", leave 3 of the 11 ticked, press Generate report.
     He measured: the name says "All dates" and every row comes back ticked.

Nothing is changed by this script; it reads the window and the files it wrote.

    export CHROMIQ_SETTINGS_FILE=/tmp/chromiq-k26/settings.ini
    export CHROMIQ_PRESETS_DIR=/tmp/chromiq-k26/presets
    python scripts/drive_k26_included_measurements.py <project> <out>
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
from PyQt6.QtCore import Qt, QTimer                              # noqa: E402
from PyQt6.QtWidgets import QApplication, QMessageBox            # noqa: E402
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


def press_in_the_popup(app, out: Path, tag: str, label: str) -> dict:
    """Photograph the real popup and click the button named, once."""
    seen: dict = {"found": False, "label": label, "buttons": [], "tries": 0}

    def _act():
        if seen.get("done"):
            return
        box = next((w for w in QApplication.topLevelWidgets()
                    if isinstance(w, QMessageBox) and w.isVisible()), None)
        if box is None:
            seen["tries"] += 1
            if seen["tries"] > 20:
                seen["done"] = True
                seen["why"] = "no QMessageBox appeared within 6 s"
                return
            QTimer.singleShot(300, _act)
            return
        seen["done"] = True
        seen["found"] = True
        seen["text"] = box.text()
        seen["buttons"] = [b.text().replace("&", "") for b in box.buttons()]
        if out is not None:
            seen["photo"] = photo(app, box, out, tag)
        for b in box.buttons():
            if b.text().replace("&", "") == label:
                b.click()
                seen["pressed"] = label
                return
        seen["pressed"] = None
        box.reject()

    QTimer.singleShot(400, _act)
    return seen


def entries(dlg) -> list:
    return [dlg._saved_combo.itemText(i) for i in range(dlg._saved_combo.count())]


def ticks(dlg) -> list:
    """(row label, ticked) for every RUN row of the included-measurements list."""
    out = []
    for i in range(dlg._profile_list.count()):
        it = dlg._profile_list.item(i)
        kind = dlg._list_rows[i][0] if i < len(dlg._list_rows) else "?"
        if kind != "run":
            continue
        out.append((it.text().strip(),
                    it.checkState() == Qt.CheckState.Checked))
    return out


def set_tick(app, dlg, row_index: int, on: bool) -> None:
    """Tick/untick the nth RUN row through the model, as a click does."""
    n = -1
    for i in range(dlg._profile_list.count()):
        if i >= len(dlg._list_rows) or dlg._list_rows[i][0] != "run":
            continue
        n += 1
        if n == row_index:
            dlg._profile_list.item(i).setCheckState(
                Qt.CheckState.Checked if on else Qt.CheckState.Unchecked)
            pump(app, 250)
            return
    raise AssertionError(f"no run row {row_index}")


def state(dlg) -> dict:
    return {
        "shown": dlg._saved_combo.currentText(),
        "shown_key": str(dlg._saved_combo.currentData() or ""),
        "type": dlg._type_combo.currentText(),
        "type_id": str(dlg._type_combo.currentData() or ""),
        "judged": dlg._set_combo.currentText(),
        "all_runs": dlg._all_runs_check.isChecked(),
        "all_runs_enabled": dlg._all_runs_check.isEnabled(),
        "detail": dlg._detail_check.isChecked(),
        "detail_enabled": dlg._detail_check.isEnabled(),
        "hidden_runs": sorted(dlg._hidden_runs),
        "ticks": ticks(dlg),
        "n_ticked": sum(1 for _l, t in ticks(dlg) if t),
        "n_rows": len(ticks(dlg)),
        "unlock_visible": dlg._unlock_check.isVisible(),
        "unlock_enabled": dlg._unlock_check.isEnabled(),
        "generate_enabled": dlg._generate_btn.isEnabled(),
    }


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
    work = Path(tempfile.mkdtemp(prefix="chromiq-k26-"))
    settings = AppSettings()
    settings.set("custom_output_path", str(work))
    settings.set("appearance", "light")
    settings.set("language", "en")
    assert settings.get("custom_output_path", "") == str(work), "SANDBOX FAILED"
    dest = work / src.name
    shutil.copytree(src, dest)
    from ui.theme import apply_appearance
    apply_appearance(app, None, "light")
    from core.file_manager import FileManager
    fm = FileManager(settings); del fm

    res: dict = {"project": str(src), "copy": str(dest),
                 "locked_at_start": session_is_locked()}
    print(f"    screen locked at start: {res['locked_at_start']}", flush=True)

    ti3 = (dest / "runs" / "run1" / "verifications" / "2026-05-25_100000"
           / "Report-Limits-Threshold-Series-verify.ti3")
    assert ti3.exists(), ti3

    from ui.dialogs.measurement_report_dialog import (MeasurementReportDialog,
                                                      NEW_REPORT_KEY)
    dlg = MeasurementReportDialog(settings, None, initial_ti3=ti3)
    dlg.resize(1480, 1000)
    dlg.show(); dlg.raise_(); dlg.activateWindow()
    pump(app, 2500)
    res["window_visible"] = dlg.isVisible()
    print(f"    window on screen: {dlg.isVisible()}", flush=True)
    res["entries_at_open"] = entries(dlg)
    res["open"] = state(dlg)
    res["open_photo"] = photo(app, dlg, out, "A0-window-at-open")

    # =================================================================
    # A. a pre-created report, type -> Colour summary, ALL ticked,
    #    Generate report -> Create New.
    # =================================================================
    try:
        from workflow.measurement_report import REPORT_TYPE_SUMMARY
        # Select the first real (non-"New report…") entry.
        key = next(str(dlg._saved_combo.itemData(i))
                   for i in range(dlg._saved_combo.count())
                   if str(dlg._saved_combo.itemData(i)) != NEW_REPORT_KEY)
        dlg._saved_combo.setCurrentIndex(dlg._saved_combo.findData(key))
        pump(app, 1200)
        res["A_selected"] = state(dlg)

        i = dlg._type_combo.findData(REPORT_TYPE_SUMMARY)
        res["A_summary_in_menu"] = i
        dlg._type_combo.setCurrentIndex(i)
        pump(app, 1200)
        res["A_after_type"] = state(dlg)
        res["A_after_type_photo"] = photo(app, dlg, out, "A1-colour-summary-chosen")

        for n in range(len(ticks(dlg))):
            set_tick(app, dlg, n, True)
        pump(app, 900)
        res["A_all_ticked"] = state(dlg)

        before = {str(p.relative_to(dest)) for p in dest.rglob("report_*.json")}
        seen = press_in_the_popup(app, out, "A2-generate-popup", "Create New")
        dlg._generate_btn.click()
        pump(app, 4000)
        res["A_popup"] = seen
        after = {str(p.relative_to(dest)) for p in dest.rglob("report_*.json")}
        res["A_new_files"] = sorted(after - before)
        res["A_after_generate"] = state(dlg)
        res["A_entries_after"] = entries(dlg)
        res["A_after_photo"] = photo(app, dlg, out, "A3-after-generate")

        # …select another report, then come back to the new one.
        new_key = str(dlg._saved_combo.currentData() or "")
        res["A_new_key"] = new_key
        other = next((str(dlg._saved_combo.itemData(i))
                      for i in range(dlg._saved_combo.count())
                      if str(dlg._saved_combo.itemData(i))
                      not in (NEW_REPORT_KEY, new_key)), "")
        dlg._saved_combo.setCurrentIndex(dlg._saved_combo.findData(other))
        pump(app, 1400)
        res["A_on_other"] = state(dlg)
        dlg._saved_combo.setCurrentIndex(dlg._saved_combo.findData(new_key))
        pump(app, 1400)
        res["A_back_on_new"] = state(dlg)
        res["A_back_photo"] = photo(app, dlg, out, "A4-back-on-the-new-report")
    except Exception:                                      # noqa: BLE001
        res["A_error"] = traceback.format_exc()

    # =================================================================
    # B. "New report…", 3 of 11 ticked, Generate report.
    # =================================================================
    try:
        dlg._saved_combo.setCurrentIndex(dlg._saved_combo.findData(NEW_REPORT_KEY))
        pump(app, 1400)
        res["B_new_report"] = state(dlg)
        # A type that is not the one-page summary, so the narrowing under test
        # is the ROW TICKS and nothing else.
        from workflow.measurement_report import REPORT_TYPE_FULL
        j = dlg._type_combo.findData(REPORT_TYPE_FULL)
        if j >= 0:
            dlg._type_combo.setCurrentIndex(j)
            pump(app, 1000)
        if not dlg._all_runs_check.isChecked() and dlg._all_runs_check.isEnabled():
            dlg._all_runs_check.setChecked(True)
            pump(app, 900)
        n_rows = len(ticks(dlg))
        for n in range(n_rows):
            set_tick(app, dlg, n, n < 3)
        pump(app, 1200)
        res["B_three_ticked"] = state(dlg)
        res["B_three_photo"] = photo(app, dlg, out, "B1-three-of-eleven-ticked")

        before = {str(p.relative_to(dest)) for p in dest.rglob("report_*.json")}
        seen = press_in_the_popup(app, out, "B2-generate-popup", "Create New")
        dlg._generate_btn.click()
        pump(app, 5000)
        res["B_popup"] = seen
        after = {str(p.relative_to(dest)) for p in dest.rglob("report_*.json")}
        res["B_new_files"] = sorted(after - before)
        res["B_after_generate"] = state(dlg)
        res["B_entries_after"] = entries(dlg)
        res["B_after_photo"] = photo(app, dlg, out, "B3-after-generate")

        blocks = {}
        for rel in res["B_new_files"]:
            d = json.loads((dest / rel).read_text(encoding="utf-8"))
            doc = d.get("document") or {}
            blocks[rel] = {"scope": doc.get("scope"),
                           "all_runs": doc.get("all_runs"),
                           "n_measurements": len(doc.get("measurements") or [])}
        res["B_doc_blocks"] = blocks
    except Exception:                                      # noqa: BLE001
        res["B_error"] = traceback.format_exc()

    # =================================================================
    # C. All eleven ticked on a type that holds several -> "All dates".
    # D. Untick two and press Update -> the tag must FOLLOW the change.
    # =================================================================
    try:
        dlg._saved_combo.setCurrentIndex(dlg._saved_combo.findData(NEW_REPORT_KEY))
        pump(app, 1400)
        from workflow.measurement_report import REPORT_TYPE_FULL
        j = dlg._type_combo.findData(REPORT_TYPE_FULL)
        if j >= 0:
            dlg._type_combo.setCurrentIndex(j)
            pump(app, 1000)
        if not dlg._all_runs_check.isChecked():
            dlg._all_runs_check.setChecked(True)
            pump(app, 900)
        for n in range(len(ticks(dlg))):
            set_tick(app, dlg, n, True)
        pump(app, 1200)
        res["C_all_ticked"] = state(dlg)
        seen = press_in_the_popup(app, out, "C1-generate-popup", "Create New")
        dlg._generate_btn.click()
        pump(app, 6000)
        res["C_popup_found"] = seen.get("found")
        res["C_after_generate"] = state(dlg)
        res["C_photo"] = photo(app, dlg, out, "C2-all-dates")

        # D: the same document, two rows fewer, UPDATE.
        for n in (0, 1):
            set_tick(app, dlg, n, False)
        pump(app, 1400)
        res["D_nine_ticked"] = state(dlg)
        seen = press_in_the_popup(app, out, "D1-update-popup", "Update")
        dlg._generate_btn.click()
        pump(app, 6000)
        res["D_popup"] = {"found": seen.get("found"),
                          "buttons": seen.get("buttons"),
                          "pressed": seen.get("pressed")}
        res["D_after_update"] = state(dlg)
        res["D_entries"] = entries(dlg)
        res["D_photo"] = photo(app, dlg, out, "D2-tag-follows-the-update")
    except Exception:                                      # noqa: BLE001
        res["CD_error"] = traceback.format_exc()

    (out / "included-measurements.json").write_text(
        json.dumps(res, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({k: v for k, v in res.items()
                      if not k.endswith("photo")}, indent=2,
                     ensure_ascii=False)[:9000])
    dlg.close()
    pump(app, 400)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
