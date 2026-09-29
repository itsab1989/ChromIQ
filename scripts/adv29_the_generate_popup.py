#!/usr/bin/env python3
"""Adversary round 29: Generate report's new three-button question, pushed.

B8-491 drove the happy path: one report, one setting moved, Cancel / Create New
/ Update pressed once each.  This drives the doors nobody opened:

  1. **Update a report whose files were deleted from under the window.**
  2. **Create New when the reports folder cannot be written.**
  3. **Cancel, then press Generate again** -- the question must come back, and
     nothing may have been written by the first press.
  4. **Update TWICE** -- the name must carry one creation stamp and one update
     stamp, and the file count must not move.
  5. **Update a pre-#182 report that records no measurements at all** -- which
     is every report in the shipped demo pack.
  6. **Move a setting, select a DIFFERENT report, then press Generate.**

Every popup is the REAL `QMessageBox`, found on screen, photographed and
answered by clicking its real button.  Never `QDialog.exec = lambda self: 1`.

    export CHROMIQ_SETTINGS_FILE=/tmp/chromiq-r29/settings.ini
    export CHROMIQ_PRESETS_DIR=/tmp/chromiq-r29/presets
    python scripts/adv29_the_generate_popup.py <project> <out>
"""
from __future__ import annotations

import json
import os
import shutil
import stat
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
from PyQt6.QtCore import QTimer                                  # noqa: E402
from PyQt6.QtWidgets import QApplication, QMessageBox            # noqa: E402
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


def capture_settled(app, win, first: Path, second: Path, tries: int = 3):
    ok = ok2 = False
    why = ""
    for n in range(1, tries + 1):
        pump(app, 700)
        ok, why = capture_window(win, first)
        pump(app, 700)
        ok2, why2 = capture_window(win, second)
        why = why or why2
        if ok and ok2 and _frames_match(first, second):
            return True, why, n, True
    return bool(ok and ok2), why, tries, False


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
        seen["informative"] = box.informativeText()
        seen["buttons"] = [b.text().replace("&", "") for b in box.buttons()]
        if out is not None:
            ok, why, tries, same = capture_settled(
                app, box, out / f"{tag}-1.png", out / f"{tag}-2.png")
            seen["photo"] = {"taken": ok, "why": why, "identical": same}
        for b in box.buttons():
            if b.text().replace("&", "") == label:
                b.click()
                seen["pressed"] = label
                return
        seen["pressed"] = None
        box.reject()

    QTimer.singleShot(400, _act)
    return seen


def catch_any_box(app) -> dict:
    """Answer whatever box turns up with its default, and say what it said."""
    seen: dict = {"found": False, "tries": 0}

    def _act():
        if seen.get("done"):
            return
        box = next((w for w in QApplication.topLevelWidgets()
                    if isinstance(w, QMessageBox) and w.isVisible()), None)
        if box is None:
            seen["tries"] += 1
            if seen["tries"] > 16:
                seen["done"] = True
                return
            QTimer.singleShot(250, _act)
            return
        seen["done"] = True
        seen["found"] = True
        seen["text"] = box.text()
        seen["informative"] = box.informativeText()
        seen["buttons"] = [b.text().replace("&", "") for b in box.buttons()]
        box.accept()

    QTimer.singleShot(300, _act)
    return seen


def all_report_files(project_dir: Path) -> list:
    return sorted(str(p.relative_to(project_dir))
                  for p in project_dir.rglob("report_*.json"))


def doc_blocks(project_dir: Path) -> dict:
    out = {}
    for p in sorted(project_dir.rglob("report_*.json")):
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except Exception:                                  # noqa: BLE001
            out[str(p.relative_to(project_dir))] = "UNREADABLE"
            continue
        doc = d.get("document") or {}
        out[str(p.relative_to(project_dir))] = {
            "id": doc.get("id"), "created": doc.get("created"),
            "updated": doc.get("updated"),
            "measurements": len(doc.get("measurements") or [])}
    return out


def entries(dlg) -> list:
    return [dlg._saved_combo.itemText(i) for i in range(dlg._saved_combo.count())]


def open_window(app, settings, ti3, width=1480):
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    dlg = MeasurementReportDialog(settings, None, initial_ti3=ti3)
    dlg.resize(width, 1000)
    dlg.show(); dlg.raise_(); dlg.activateWindow()
    pump(app, 2500)
    return dlg


def select_doc(app, dlg, key):
    dlg._saved_combo.setCurrentIndex(0)
    pump(app, 700)
    i = dlg._saved_combo.findData(key)
    dlg._saved_combo.setCurrentIndex(max(0, i))
    pump(app, 1100)
    return i


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
    work = Path(tempfile.mkdtemp(prefix="chromiq-r29-gen-"))
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
    print(f"    screen locked at start: {session_is_locked()}", flush=True)

    ti3 = sorted((dest / "runs" / "run1" / "verifications"
                  / "2026-11-16_100000").glob("*.ti3"))[0]
    res: dict = {"project": str(src), "copy": str(dest),
                 "locked_at_start": session_is_locked(),
                 "files_at_start": all_report_files(dest)}

    dlg = open_window(app, settings, ti3)
    res["window_visible"] = dlg.isVisible()
    print(f"    window on screen: {dlg.isVisible()}", flush=True)

    # ===================================================================
    # 5. UPDATE A PRE-#182 REPORT THAT RECORDS NO MEASUREMENTS.
    #    Every report in the shipped demo pack is one, and the window
    #    opens on one, so this is the door a user reaches first.
    # ===================================================================
    opened_on = dlg._loaded_doc_id
    res["S5_pre182"] = {
        "opened_on": opened_on,
        "entry": dlg._saved_combo.currentText(),
        "doc_recorded": bool(dlg._loaded_doc),
        "files_before": all_report_files(dest),
        "docs_before": doc_blocks(dest),
        "entries_before": entries(dlg),
    }
    dlg._detail_check.setChecked(not dlg._detail_check.isChecked())
    pump(app, 900)
    res["S5_pre182"]["red_line_up"] = dlg._stale_label.isVisible()
    seen = press_in_the_popup(app, out, "S5-popup", "Update")
    dlg._on_generate_report()
    pump(app, 2500)
    res["S5_pre182"].update({
        "popup": seen,
        "files_after": all_report_files(dest),
        "docs_after": doc_blocks(dest),
        "entries_after": entries(dlg),
        "entry_now": dlg._saved_combo.currentText(),
        "loaded_after": dlg._loaded_doc_id,
    })
    print(f"  S5 pre-#182 Update: popup={seen.get('found')} "
          f"pressed={seen.get('pressed')}", flush=True)
    print(f"     files {len(res['S5_pre182']['files_before'])} -> "
          f"{len(res['S5_pre182']['files_after'])}", flush=True)
    print(f"     entry now {dlg._saved_combo.currentText()[:90]!r}", flush=True)
    ok, why, t, same = capture_settled(app, dlg, out / "S5-after-1.png",
                                       out / "S5-after-2.png")
    res["S5_pre182"]["photo"] = {"taken": ok, "why": why, "identical": same}

    # ===================================================================
    # 4. UPDATE TWICE.  The name must not collect two creation stamps and
    #    the file count must not move.
    # ===================================================================
    made = dlg._loaded_doc_id
    res["S4_update_twice"] = {"doc": made, "name_after_1": dlg._saved_combo.currentText()}
    select_doc(app, dlg, made)
    dlg._detail_check.setChecked(not dlg._detail_check.isChecked())
    pump(app, 900)
    seen2 = press_in_the_popup(app, out, "S4-popup", "Update")
    dlg._on_generate_report()
    pump(app, 2500)
    res["S4_update_twice"].update({
        "popup": seen2,
        "name_after_2": dlg._saved_combo.currentText(),
        "files_after": all_report_files(dest),
        "docs_after": doc_blocks(dest),
        "loaded_after": dlg._loaded_doc_id,
    })
    print(f"  S4 second Update: name now "
          f"{dlg._saved_combo.currentText()[:100]!r}", flush=True)

    # ===================================================================
    # 3. CANCEL, THEN GENERATE AGAIN.
    # ===================================================================
    select_doc(app, dlg, made)
    dlg._detail_check.setChecked(not dlg._detail_check.isChecked())
    pump(app, 900)
    before = all_report_files(dest)
    seen3 = press_in_the_popup(app, out, "S3-cancel", "Cancel")
    dlg._on_generate_report()
    pump(app, 2000)
    mid = all_report_files(dest)
    res["S3_cancel_then_again"] = {
        "first_popup": seen3, "files_before": before, "files_after_cancel": mid,
        "red_line_still_up": dlg._stale_label.isVisible(),
        "still_selected": dlg._loaded_doc_id,
    }
    seen4 = press_in_the_popup(app, None, "S3-again", "Cancel")
    dlg._on_generate_report()
    pump(app, 2000)
    res["S3_cancel_then_again"].update({
        "second_popup_found": seen4.get("found"),
        "second_popup_buttons": seen4.get("buttons"),
        "files_after_second_cancel": all_report_files(dest),
    })
    print(f"  S3 cancel: files {len(before)} -> {len(mid)}; "
          f"second popup found={seen4.get('found')}; "
          f"red line still up={res['S3_cancel_then_again']['red_line_still_up']}",
          flush=True)

    # ===================================================================
    # 6. MOVE A SETTING, SELECT A DIFFERENT REPORT, THEN GENERATE.
    # ===================================================================
    keys = [dlg._saved_combo.itemData(i) for i in range(dlg._saved_combo.count())]
    others = [k for k in keys[1:] if k and k != made]
    res["S6_switch"] = {"keys": [str(k) for k in keys], "picked": str(others[0]) if others else None}
    if others:
        select_doc(app, dlg, made)
        dlg._detail_check.setChecked(not dlg._detail_check.isChecked())
        pump(app, 900)
        res["S6_switch"]["red_before_switch"] = dlg._stale_label.isVisible()
        dlg._saved_combo.setCurrentIndex(dlg._saved_combo.findData(others[0]))
        pump(app, 1400)
        res["S6_switch"]["red_after_switch"] = dlg._stale_label.isVisible()
        res["S6_switch"]["loaded_after_switch"] = str(dlg._loaded_doc_id)
        before = all_report_files(dest)
        seen6 = press_in_the_popup(app, None, "S6", "Cancel")
        dlg._on_generate_report()
        pump(app, 2200)
        res["S6_switch"].update({
            "popup_found": seen6.get("found"),
            "files_before": len(before),
            "files_after": len(all_report_files(dest)),
            "entry_after": dlg._saved_combo.currentText(),
        })
        print(f"  S6 switch: red before={res['S6_switch']['red_before_switch']} "
              f"after={res['S6_switch']['red_after_switch']} "
              f"popup={seen6.get('found')} files "
              f"{len(before)} -> {res['S6_switch']['files_after']}", flush=True)

    # ===================================================================
    # 1. UPDATE A REPORT WHOSE FILES WERE DELETED FROM UNDER THE WINDOW.
    # ===================================================================
    select_doc(app, dlg, made)
    pump(app, 800)
    members = []
    for d in dlg._saved_documents(dlg._run_ctx.run):
        if d["key"] == made:
            members = [(r.get("_origin_dir"), n) for r, n in (d.get("members") or [])]
    gone = []
    for origin, name in members:
        p = Path(str(origin)) / "reports" / name
        if p.exists():
            p.unlink()
            gone.append(str(p.relative_to(dest)))
    res["S1_deleted"] = {"deleted": gone, "files_after_delete": all_report_files(dest)}
    print(f"  S1 deleted from disk: {gone}", flush=True)
    dlg._detail_check.setChecked(not dlg._detail_check.isChecked())
    pump(app, 900)
    seen7 = press_in_the_popup(app, out, "S1-popup", "Update")
    other = catch_any_box(app)
    dlg._on_generate_report()
    pump(app, 3000)
    res["S1_deleted"].update({
        "popup": seen7, "other_box": other,
        "files_after_update": all_report_files(dest),
        "docs_after": doc_blocks(dest),
        "entry_after": dlg._saved_combo.currentText(),
        "loaded_after": str(dlg._loaded_doc_id),
        "entries_after": entries(dlg),
    })
    print(f"  S1 update after delete: popup={seen7.get('found')} "
          f"files now {len(res['S1_deleted']['files_after_update'])}", flush=True)
    ok, why, t, same = capture_settled(app, dlg, out / "S1-after-1.png",
                                       out / "S1-after-2.png")
    res["S1_deleted"]["photo"] = {"taken": ok, "why": why, "identical": same}

    # ===================================================================
    # 2. CREATE NEW WITH THE REPORTS FOLDER READ-ONLY.
    # ===================================================================
    folders = sorted({p.parent for p in dest.rglob("report_*.json")})
    folders += [dest / "runs" / "run1" / "verifications" / "2026-11-16_100000" / "reports"]
    modes = {}
    for f in folders:
        if f.exists():
            modes[str(f)] = f.stat().st_mode
            os.chmod(f, stat.S_IRUSR | stat.S_IXUSR)
    res["S2_readonly"] = {"locked_folders": sorted(modes)}
    try:
        select_doc(app, dlg, dlg._loaded_doc_id)
        dlg._detail_check.setChecked(not dlg._detail_check.isChecked())
        pump(app, 900)
        before = all_report_files(dest)
        seen8 = press_in_the_popup(app, out, "S2-popup", "Create New")
        after_box = catch_any_box(app)
        dlg._on_generate_report()
        pump(app, 3000)
        res["S2_readonly"].update({
            "popup": seen8,
            "message_after": after_box,
            "files_before": len(before),
            "files_after": len(all_report_files(dest)),
            "entry_after": dlg._saved_combo.currentText(),
            "page_still_on": str(dlg._loaded_doc_id),
        })
        print(f"  S2 read-only Create New: popup={seen8.get('found')} "
              f"message={after_box.get('text', '')[:70]!r} files "
              f"{len(before)} -> {res['S2_readonly']['files_after']}", flush=True)
        ok, why, t, same = capture_settled(app, dlg, out / "S2-after-1.png",
                                           out / "S2-after-2.png")
        res["S2_readonly"]["photo"] = {"taken": ok, "why": why, "identical": same}
    finally:
        for f, m in modes.items():
            try:
                os.chmod(f, m)
            except OSError:
                pass

    res["locked_at_end"] = session_is_locked()
    (out / "generate-popup.json").write_text(
        json.dumps(res, indent=2, default=str), encoding="utf-8")
    dlg.close()
    pump(app, 500)
    print(f"    wrote {out / 'generate-popup.json'}", flush=True)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception:                                      # noqa: BLE001
        traceback.print_exc()
        raise SystemExit(2)
