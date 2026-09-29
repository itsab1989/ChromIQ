#!/usr/bin/env python3
"""Knut's five Measurement Report defects, 2026-09-18, driven in a real window.

    1. the controls are not arranged as he specified;
    2. choosing a saved report does not redraw the window with that report;
    3. choosing a saved report does not restore the settings it was made with;
    4. Generate WRITES A NEW report instead of rebuilding the selected one, and
       "Show all measurement runs" ON then Generate wrote TWO;
    5. changing "Judged against" relabels every entry already in the pulldown
       AND writes another report.

Nothing is fixed here. This measures what the window does, counts the files on
disk before and after every action, and photographs each step.

    CHROMIQ_SETTINGS_FILE=… CHROMIQ_PRESETS_DIR=… \\
        python scripts/drive_b22_knuts_five_report_defects.py <project> <out>
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
    work = Path(tempfile.mkdtemp(prefix="chromiq-b22-five-"))
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

    def report_files() -> "dict[str, str]":
        """Every live saved report in the project → its set id and type."""
        found = {}
        for f in sorted(dest.glob("runs/*/verifications/*/reports/report_*.json")):
            try:
                d = json.loads(f.read_text(encoding="utf-8"))
            except Exception:                          # noqa: BLE001
                continue
            found[str(f.relative_to(dest))] = (
                f"{(d.get('compliance') or {}).get('set_id')}"
                f" / {d.get('report_type')}")
        return found

    ti3 = None
    for d in sorted((dest / "runs").glob("run*/verifications/*")):
        if sorted(d.glob("*.ti3")) and sorted((d / "reports").glob("report_*.json")):
            ti3 = sorted(d.glob("*.ti3"))[0]
            break
    assert ti3 is not None, "no dated verification WITH a saved report here"
    print(f"    opening on {ti3.relative_to(dest)}", flush=True)

    dlg = MeasurementReportDialog(settings, None, initial_ti3=ti3)
    dlg.resize(1500, 1060)
    dlg.show(); dlg.raise_(); dlg.activateWindow()
    pump(app, 3500)
    print(f"    window on screen: {dlg.isVisible()}", flush=True)
    res: dict = {"project": str(src)}

    def controls() -> dict:
        return {
            "report_type": dlg._type_combo.currentText(),
            "judged_against": dlg._set_combo.currentText(),
            "show_all_runs": bool(dlg._all_runs_check.isChecked()),
            "show_detail": bool(dlg._detail_check.isChecked()),
            "saved_index": dlg._saved_combo.currentIndex(),
            "saved_entries": [dlg._saved_combo.itemText(i)
                              for i in range(dlg._saved_combo.count())],
        }

    def doc_hash() -> str:
        return hashlib.sha256(dlg._view.toHtml().encode("utf-8")).hexdigest()[:12]

    # ---- 1. the arrangement -------------------------------------------
    order = []
    for name, w in (("measurement list", dlg._profile_list),
                    ("Generate report", dlg._generate_btn),
                    ("Save report as PDF", dlg._pdf_btn),
                    ("Show all measurement runs", dlg._all_runs_check),
                    ("Show detailed data", dlg._detail_check),
                    ("Report type", dlg._type_combo),
                    ("Judged against", dlg._set_combo),
                    ("Saved reports", dlg._saved_combo)):
        try:
            order.append((name, w.mapTo(dlg, w.rect().topLeft()).y(),
                          w.mapTo(dlg, w.rect().topLeft()).x(), w.width()))
        except Exception:                              # noqa: BLE001
            pass
    order.sort(key=lambda t: t[1])
    print("    [1] the controls, top to bottom (y, x, width):", flush=True)
    for n, y, x, wdt in order:
        print(f"        y={y:4d}  x={x:4d}  w={wdt:4d}  {n}", flush=True)
    res["1_arrangement"] = [{"control": n, "y": y, "x": x, "w": wdt}
                            for n, y, x, wdt in order]
    ok, why = capture_window(dlg, out / "K1-the-arrangement.png")
    print(f"        photograph: {ok} {why}", flush=True)

    # ---- 2 + 3. choosing a saved report --------------------------------
    picks = []
    base_files = report_files()
    res["files_at_open"] = base_files
    print(f"    saved report files on disk at open: {len(base_files)}", flush=True)
    for i in range(dlg._saved_combo.count()):
        before_c, before_h = controls(), doc_hash()
        dlg._saved_combo.setCurrentIndex(i)
        pump(app, 2200)
        after_c, after_h = controls(), doc_hash()
        picks.append({
            "asked": i, "entry": before_c["saved_entries"][i],
            "index_stuck": after_c["saved_index"] == i,
            "document_changed": after_h != before_h,
            "controls_before": {k: before_c[k] for k in
                                ("report_type", "judged_against",
                                 "show_all_runs", "show_detail")},
            "controls_after": {k: after_c[k] for k in
                               ("report_type", "judged_against",
                                "show_all_runs", "show_detail")},
        })
        print(f"    [2/3] pick {i}: {before_c['saved_entries'][i][:60]!r}",
              flush=True)
        print(f"          stayed picked: {picks[-1]['index_stuck']}   "
              f"document redrawn: {picks[-1]['document_changed']}", flush=True)
        print(f"          type {before_c['report_type']!r} -> "
              f"{after_c['report_type']!r}   judged "
              f"{before_c['judged_against']!r} -> "
              f"{after_c['judged_against']!r}", flush=True)
    res["2_3_picking_a_saved_report"] = picks
    capture_window(dlg, out / "K2-after-picking-a-saved-report.png")

    # ---- 4. Generate writes a new report --------------------------------
    b = report_files()
    dlg._generate_btn.click()
    pump(app, 4000)
    a = report_files()
    added = sorted(set(a) - set(b))
    print(f"    [4] Generate with 'Show all measurement runs' "
          f"{dlg._all_runs_check.isChecked()}: {len(b)} files -> {len(a)}; "
          f"added {added}", flush=True)
    res["4_generate_plain"] = {"before": b, "after": a, "added": added,
                               "show_all": bool(dlg._all_runs_check.isChecked())}
    capture_window(dlg, out / "K4a-after-generate.png")

    dlg._all_runs_check.setChecked(True)
    pump(app, 2000)
    b2 = report_files()
    dlg._generate_btn.click()
    pump(app, 4500)
    a2 = report_files()
    added2 = sorted(set(a2) - set(b2))
    print(f"    [4] 'Show all measurement runs' ON then Generate: "
          f"{len(b2)} files -> {len(a2)}; added {added2}", flush=True)
    res["4_generate_show_all"] = {"before": b2, "after": a2, "added": added2}
    capture_window(dlg, out / "K4b-show-all-then-generate.png")

    # ---- 5. changing "Judged against" -----------------------------------
    entries_before = [dlg._saved_combo.itemText(i)
                      for i in range(dlg._saved_combo.count())]
    files_before = report_files()
    j = dlg._set_combo
    nxt = None
    for i in range(j.count()):
        if i != j.currentIndex() and j.model().item(i) is not None \
                and j.model().item(i).isEnabled():
            nxt = i
            break
    print(f"    [5] Judged against {j.currentText()!r} -> "
          f"{j.itemText(nxt)!r}", flush=True)
    asked.clear()
    j.setCurrentIndex(nxt)
    pump(app, 4500)
    entries_after = [dlg._saved_combo.itemText(i)
                     for i in range(dlg._saved_combo.count())]
    files_after = report_files()
    relabelled = [(x, y) for x, y in zip(entries_before, entries_after) if x != y]
    changed_on_disk = {k: (files_before.get(k), v) for k, v in files_after.items()
                       if files_before.get(k) not in (None, v)}
    print(f"        entries {len(entries_before)} -> {len(entries_after)}; "
          f"{len(relabelled)} relabelled", flush=True)
    for x, y in relabelled:
        print(f"          {x[:70]!r}\n            -> {y[:70]!r}", flush=True)
    print(f"        files {len(files_before)} -> {len(files_after)}; "
          f"added {sorted(set(files_after) - set(files_before))}", flush=True)
    print(f"        rewritten in place: {changed_on_disk}", flush=True)
    print(f"        windows it asked: {[a_['title'] for a_ in asked]}", flush=True)
    res["5_judged_against"] = {
        "entries_before": entries_before, "entries_after": entries_after,
        "relabelled": relabelled,
        "files_before": files_before, "files_after": files_after,
        "added": sorted(set(files_after) - set(files_before)),
        "rewritten_in_place": changed_on_disk,
        "confirmations": asked[:],
    }
    capture_window(dlg, out / "K5-after-changing-judged-against.png")

    (out / "five-defects.json").write_text(
        json.dumps(res, indent=2, ensure_ascii=False), encoding="utf-8")
    dlg.close()
    pump(app, 400)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
