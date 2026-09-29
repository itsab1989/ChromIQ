#!/usr/bin/env python3
"""Knut's two beta-25 rulings about a SELECTED report, driven in a REAL window.

  1. **All five settings of a selected report come back** — the included
     measurements, Report type, Judged against, "Show all measurement runs" and
     "Show detailed data for each run". Read off the real controls at the
     moment the window OPENS and again after clicking each entry.
  2. **Generate report asks what to do** when a report is selected and a
     setting has moved. The real popup is photographed, then its real buttons
     are pressed: Cancel, then Create New, then Update.

Run it on the unfixed tree for the BEFORE and on the fixed tree for the AFTER;
it reports the same numbers either way and never pretends a window it could not
photograph.

    export CHROMIQ_SETTINGS_FILE=/tmp/chromiq-k4/settings.ini
    export CHROMIQ_PRESETS_DIR=/tmp/chromiq-k4/presets
    python scripts/drive_k25_restore_and_generate.py <project> <out>
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
from PyQt6.QtCore import QTimer                                  # noqa: E402
from PyQt6.QtWidgets import (QApplication, QMessageBox,          # noqa: E402
                             QWidget)
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
    """Two pixel-identical photographs of a REAL window, or the honest why."""
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


def five_settings(dlg) -> dict:
    """The five things Knut named, read off the real controls."""
    from PyQt6.QtCore import Qt
    rows = []
    for i in range(dlg._profile_list.count()):
        it = dlg._profile_list.item(i)
        if Qt.ItemFlag.ItemIsUserCheckable in it.flags():
            rows.append([it.text().strip(),
                         it.checkState() == Qt.CheckState.Checked])
    return {
        "entry": dlg._saved_combo.currentText(),
        "report_type": dlg._type_combo.currentText(),
        "judged_against": dlg._set_combo.currentText(),
        "show_all_runs": dlg._all_runs_check.isChecked(),
        "show_details": dlg._detail_check.isChecked(),
        "included_measurements": rows,
        "red_line_up": dlg._stale_label.isVisible(),
    }


def press_in_the_popup(app, out: Path, tag: str, label: str) -> dict:
    """Arm a timer that PHOTOGRAPHS the popup and clicks the named button.

    Never `QDialog.exec = lambda self: 1`, which answers Accepted with no
    button chosen; this finds the real box, photographs it and presses the
    button the driver means.
    """
    seen: dict = {"found": False, "label": label, "buttons": [], "tries": 0}

    def _act():
        # **ONE HANDLER, ONE PRESS.** The first cut re-armed itself whenever it
        # found no box, and a handler left over from the PREVIOUS press went on
        # waking up during the next one: the run photographed one popup and
        # pressed a button in another, and a genuine Update came out as a
        # Create New. It now gives up after its own press and after a bounded
        # wait, and says which.
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
        ok, why, tries, same = capture_settled(
            app, box, out / f"{tag}-1.png", out / f"{tag}-2.png")
        seen["photo"] = {"taken": ok, "why": why, "identical": same,
                         "attempts": tries}
        for b in box.buttons():
            if b.text().replace("&", "") == label:
                b.click()
                seen["pressed"] = label
                return
        seen["pressed"] = None
        box.reject()

    QTimer.singleShot(400, _act)
    return seen


def report_files(run) -> list:
    out = list((run.dir / "reports").glob("report_*.json"))
    for v in run.verifications():
        out += list((v.dir / "reports").glob("report_*.json"))
    return sorted(str(p) for p in out)


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
    work = Path(tempfile.mkdtemp(prefix="chromiq-k25-restore-"))
    settings = AppSettings()
    settings.set("custom_output_path", str(work))
    settings.set("appearance", "light")
    settings.set("language", "en")
    settings.set("report_default_show_all_runs", True)
    settings.set("report_default_show_details", True)
    assert settings.get("custom_output_path", "") == str(work), "SANDBOX FAILED"
    dest = work / src.name
    shutil.copytree(src, dest)
    print(f"    project copied to {dest}", flush=True)
    print(f"    screen locked at start: {session_is_locked()}", flush=True)

    from core.file_manager import FileManager, Project
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    from ui.theme import apply_appearance
    apply_appearance(app, None, "light")
    fm = FileManager(settings); del fm
    project = Project.load(dest)
    run = next(r for r in project.all_runs() if r.dir.name == "run1")

    ti3 = sorted((dest / "runs" / "run1" / "verifications"
                  / "2026-11-16_100000").glob("*.ti3"))[0]
    print(f"    opening on {ti3.relative_to(dest)}", flush=True)

    res: dict = {"project": str(src), "copy": str(dest),
                 "locked_at_start": session_is_locked()}

    dlg = MeasurementReportDialog(settings, None, initial_ti3=ti3)
    dlg.resize(1480, 1040)
    dlg.show(); dlg.raise_(); dlg.activateWindow()
    pump(app, 3000)
    print(f"    window on screen: {dlg.isVisible()}", flush=True)
    res["window_visible"] = dlg.isVisible()

    # ---- A. what the window restores when it merely OPENS -----------------
    res["A_on_open"] = five_settings(dlg)
    print("  A  on open     =", json.dumps(
        {k: v for k, v in res["A_on_open"].items()
         if k != "included_measurements"}), flush=True)
    print("     list ticks  =", res["A_on_open"]["included_measurements"],
          flush=True)
    ok, why, tries, same = capture_settled(
        app, dlg, out / "A-on-open-1.png", out / "A-on-open-2.png")
    print(f"    photograph A: {ok} {why}; identical: {same}/{tries}", flush=True)
    res["A_photo"] = {"taken": ok, "why": why, "identical": same}

    # ---- B. each saved entry, clicked, with all five read back ------------
    res["B_each_entry"] = []
    for i in range(dlg._saved_combo.count()):
        dlg._saved_combo.setCurrentIndex(i)
        pump(app, 1200)
        row = five_settings(dlg)
        row["index"] = i
        res["B_each_entry"].append(row)
        print(f"  B  [{i}] {row['entry'][:58]!r}", flush=True)
        print(f"        type={row['report_type']!r} "
              f"set={row['judged_against']!r} all={row['show_all_runs']} "
              f"detail={row['show_details']}", flush=True)

    # ---- C. Generate report with a report selected and a setting moved ----
    # A real DOCUMENT first, so the window has one of its own to update.
    dlg._saved_combo.setCurrentIndex(0)             # "New report…"
    pump(app, 900)
    dlg._all_runs_check.setChecked(True)
    dlg._detail_check.setChecked(True)
    pump(app, 900)
    before_files = report_files(run)
    dlg._on_generate_report()                       # no report selected: quiet
    pump(app, 1600)
    made = dlg._loaded_doc_id
    res["C_made_a_document"] = {
        "key": made,
        "entry": dlg._saved_combo.currentText(),
        "files_before": len(before_files),
        "files_after": len(report_files(run)),
        "asked": False,
    }
    print(f"  C  made {made!r} -> {dlg._saved_combo.currentText()[:70]!r}",
          flush=True)
    ok, why, tries, same = capture_settled(
        app, dlg, out / "C-made-1.png", out / "C-made-2.png")
    res["C_photo"] = {"taken": ok, "why": why, "identical": same}
    print(f"    photograph C: {ok} {why}; identical: {same}/{tries}", flush=True)

    # …then move ONE setting and press Generate report. THREE presses, one per
    # button, each answered in the real popup.
    for tag, label in (("D-cancel", "Cancel"),
                       ("E-create-new", "Create New"),
                       ("F-update", "Update")):
        # **BACK TO "New report…" FIRST, AND THAT IS NOT A FLOURISH.** Choosing
        # the index the pulldown is ALREADY on emits no signal, so the document
        # is not reloaded and the tick box is not put back; a second toggle
        # then returns the setting to the document's own value, the red line
        # goes DOWN (which is right, and is the undo the window promises) and
        # Generate has nothing to ask about. The first run of this driver hit
        # exactly that and recorded "no popup" for a press that was never in
        # the state the popup is for.
        dlg._saved_combo.setCurrentIndex(0)
        pump(app, 900)
        dlg._saved_combo.setCurrentIndex(
            max(0, dlg._saved_combo.findData(made)))
        pump(app, 1200)
        dlg._detail_check.setChecked(not dlg._detail_check.isChecked())
        pump(app, 1200)
        state = {"red_line_up": dlg._stale_label.isVisible(),
                 "entry_before": dlg._saved_combo.currentText(),
                 "files_before": len(report_files(run)),
                 "entries_before": dlg._saved_combo.count()}
        seen = press_in_the_popup(app, out, tag, label)
        dlg._on_generate_report()
        pump(app, 2500)
        state.update({
            "popup": seen,
            "files_after": len(report_files(run)),
            "entries_after": dlg._saved_combo.count(),
            "entry_after": dlg._saved_combo.currentText(),
            "loaded_after": dlg._loaded_doc_id,
        })
        res[tag] = state
        print(f"  {tag}: popup found={seen.get('found')} "
              f"buttons={seen.get('buttons')} pressed={seen.get('pressed')}",
              flush=True)
        print(f"        files {state['files_before']} -> "
              f"{state['files_after']}, entries "
              f"{state['entries_before']} -> {state['entries_after']}",
              flush=True)
        print(f"        entry now {state['entry_after'][:78]!r}", flush=True)
        ok, why, tries, same = capture_settled(
            app, dlg, out / f"{tag}-after-1.png", out / f"{tag}-after-2.png")
        res[tag]["window_photo"] = {"taken": ok, "why": why, "identical": same}

    # ---- G. the included-measurements list, restored from a real document -
    # A document made with one row UNTICKED records one measurement, so
    # selecting it must bring that tick state back (Knut: *"Included
    # measurements added for report is ticked"*).
    dlg._saved_combo.setCurrentIndex(0)
    pump(app, 900)
    dlg._all_runs_check.setChecked(True)
    pump(app, 600)
    from PyQt6.QtCore import Qt as _Qt
    rows = [i for i in range(dlg._profile_list.count())
            if _Qt.ItemFlag.ItemIsUserCheckable in dlg._profile_list.item(i).flags()]
    if len(rows) >= 2:
        dlg._profile_list.item(rows[0]).setCheckState(_Qt.CheckState.Unchecked)
        pump(app, 900)
        res["G_before_generate"] = five_settings(dlg)
        dlg._on_generate_report()
        pump(app, 2000)
        narrow = dlg._loaded_doc_id
        res["G_narrow_document"] = {"key": narrow,
                                    "entry": dlg._saved_combo.currentText()}
        dlg._saved_combo.setCurrentIndex(0)             # every row ticked again
        pump(app, 1200)
        res["G_on_new_report"] = five_settings(dlg)
        dlg._saved_combo.setCurrentIndex(
            max(0, dlg._saved_combo.findData(narrow)))
        pump(app, 1400)
        res["G_back_on_the_narrow_one"] = five_settings(dlg)
        print("  G  new report  ticks =",
              res["G_on_new_report"]["included_measurements"], flush=True)
        print("     narrow doc  ticks =",
              res["G_back_on_the_narrow_one"]["included_measurements"],
              flush=True)
        ok, why, tries, same = capture_settled(
            app, dlg, out / "G-narrow-1.png", out / "G-narrow-2.png")
        res["G_photo"] = {"taken": ok, "why": why, "identical": same}
        print(f"    photograph G: {ok} {why}; identical: {same}/{tries}",
              flush=True)

    res["locked_at_end"] = session_is_locked()
    (out / "result.json").write_text(json.dumps(res, indent=2, default=str),
                                     encoding="utf-8")
    dlg.close()
    pump(app, 500)
    print(f"    wrote {out / 'result.json'}", flush=True)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception:                                      # noqa: BLE001
        traceback.print_exc()
        raise SystemExit(2)
