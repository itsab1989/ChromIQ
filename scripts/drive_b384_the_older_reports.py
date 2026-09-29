#!/usr/bin/env python3
"""B8-384's remainder — what changing "Judged against" does to a saved report
that was written before this beta, driven in a REAL window on a REAL screen.

Knut, 2026-09-18: *"When I change Judged Against to another setting, all listed
reports in the Saved reports pulldown change to the new judged against setting,
AND created a new (third) report. This is not the behaviour I specified."*
and, asked whether his new rule supersedes D23: *"Agreed. D23 stands."*

THE FIXTURE HOLDS REPORTS OF FOUR SHAPES, because a fixture too tidy to contain
the fault agrees with the code:

  1. two written by an OLDER SCHEMA (5), carrying no limit set and no verdict
     at all — the two Knut watched being relabelled;
  2. one in the 4.2.x shape: schema 7 WITH a recorded limit set and verdict,
     and no document block;
  3. documents, written here by the window's own Generate report button;
  4. a run folder that was RENAMED on disk (`run2` copied to `run20`, its
     reports still naming the old folder inside themselves), which is both the
     renamed-folder case and the `run2`/`run20` prefix trap this window has
     already been bitten by once.

    CHROMIQ_SETTINGS_FILE=… CHROMIQ_PRESETS_DIR=… \\
        python scripts/drive_b384_the_older_reports.py <project> <out>
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


def capture_settled(app, win, first: Path, second: Path, tries: int = 6):
    ok = ok2 = False
    why = ""
    for n in range(1, tries + 1):
        pump(app, 900)
        ok, why = capture_window(win, first)
        pump(app, 900)
        ok2, why2 = capture_window(win, second)
        why = why or why2
        if ok and ok2 and _frames_match(first, second):
            return True, why, n, True
    return bool(ok and ok2), why, tries, False


def build_the_fixture(dest: Path) -> dict:
    """Add the two shapes the copied project does not already have."""
    from workflow.compliance_sets import SET_BY_ID, effective_limits
    from workflow.measurement_report import (save_report, set_report_type,
                                             stamp_verdict)
    made: dict = {}
    # ---- 2. a 4.2.x report: schema 7, a recorded set and verdict, no document
    src = sorted(dest.glob(
        "runs/run2/verifications/*/reports/report_*.json"))[0]
    rep = json.loads(src.read_text(encoding="utf-8"))
    rep["schema"] = 7
    set_report_type(rep, "t2_full_colour_check")
    stamp_verdict(rep, effective_limits("chromiq_quick", None),
                  set_id="chromiq_quick",
                  set_label=SET_BY_ID["chromiq_quick"].label)
    p = save_report(rep, src.parent.parent)
    made["four_two_shape"] = str(p.relative_to(dest))
    # ---- 4. a run folder renamed on disk, reports still naming the old one
    old, new = dest / "runs/run2", dest / "runs/run20"
    if not new.exists():
        shutil.copytree(old, new)
    man = json.loads((dest / "project.json").read_text(encoding="utf-8"))
    if "run20" not in man.get("runs", []):
        man.setdefault("runs", []).append("run20")
        (dest / "project.json").write_text(json.dumps(man, indent=2),
                                           encoding="utf-8")
    made["renamed_run"] = "runs/run20 (copied from runs/run2)"
    return made


def main() -> int:                                          # noqa: C901
    assert os.environ.get("CHROMIQ_SETTINGS_FILE"), "SANDBOX THE SETTINGS FIRST"
    assert os.environ.get("CHROMIQ_PRESETS_DIR"), "SANDBOX THE PRESETS FIRST"
    assert not os.environ.get("QT_QPA_PLATFORM"), "this DRIVER opens a window"
    src, out = Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve()
    out.mkdir(parents=True, exist_ok=True)

    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("ChromIQ")
    from core.resource_path import resource_path
    from PyQt6.QtGui import QFontDatabase
    for fp in resource_path("assets/fonts").glob("*.ttf"):
        QFontDatabase.addApplicationFont(str(fp))
    from ui.styles import WinButtonLayoutStyle
    app.setStyle(WinButtonLayoutStyle("Fusion"))
    from core.settings import AppSettings
    work = Path(tempfile.mkdtemp(prefix="chromiq-b384-"))
    settings = AppSettings()
    settings.set("custom_output_path", str(work))
    settings.set("appearance", "dark")
    settings.set("language", "en")
    assert settings.get("custom_output_path", "") == str(work), "SANDBOX FAILED"
    dest = work / src.name
    shutil.copytree(src, dest)
    print(f"    project copied to {dest}", flush=True)
    print(f"    screen locked at start: {session_is_locked()}", flush=True)
    made = build_the_fixture(dest)
    print(f"    fixture: {made}", flush=True)
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

    def inventory() -> dict:
        """Every live report file: bytes, sha256, mtime, and what it records."""
        found: dict = {}
        for f in sorted(dest.glob("runs/**/reports/report_*.json")):
            if "/old/" in str(f):
                continue
            b = f.read_bytes()
            try:
                d = json.loads(b.decode("utf-8"))
            except Exception:                          # noqa: BLE001
                d = {}
            doc = d.get("document") or {}
            found[str(f.relative_to(dest))] = {
                "bytes": len(b),
                "sha256": hashlib.sha256(b).hexdigest()[:16],
                "mtime_ns": f.stat().st_mtime_ns,
                "schema": d.get("schema"),
                "set_id": (d.get("compliance") or {}).get("set_id"),
                "report_type": d.get("report_type"),
                "document": doc.get("id", None),
            }
        return found

    def diff(before: dict, after: dict) -> dict:
        moved = sorted(k for k in before
                       if k in after and after[k]["sha256"] != before[k]["sha256"])
        touched = sorted(k for k in before
                         if k in after and after[k]["mtime_ns"] != before[k]["mtime_ns"])
        return {
            "files_before": len(before), "files_after": len(after),
            "added": sorted(set(after) - set(before)),
            "gone": sorted(set(before) - set(after)),
            "rewritten": moved,
            "mtime_moved": touched,
            "set_id_changed": sorted(
                f"{k}: {before[k]['set_id']} -> {after[k]['set_id']}"
                for k in before if k in after
                and before[k]["set_id"] != after[k]["set_id"]),
        }

    ti3 = None
    for d in sorted((dest / "runs").glob("run2/verifications/*")):
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
    res: dict = {"project": str(src), "fixture": made}

    def entries() -> list:
        return [dlg._saved_combo.itemText(i)
                for i in range(dlg._saved_combo.count())]

    # ---- a document, written by the window's own button ----------------
    at_open = inventory()
    res["1_at_open"] = at_open
    res["1_entries_at_open"] = entries()
    print(f"    report files at open: {len(at_open)}; "
          f"entries: {len(res['1_entries_at_open'])}", flush=True)
    for k, v in at_open.items():
        print(f"        {v['schema']} / set={v['set_id']} / "
              f"doc={v['document']}  {k}", flush=True)
    dlg._generate_btn.click()
    pump(app, 5000)
    after_gen = inventory()
    res["2_after_generate"] = {"inventory": after_gen,
                               "diff": diff(at_open, after_gen),
                               "entries": entries()}
    print(f"    Generate report: {len(at_open)} files -> {len(after_gen)}, "
          f"entries -> {len(entries())}", flush=True)

    # ---- THE ACT: change "Judged against" ------------------------------
    before = inventory()
    before_entries = entries()
    asked.clear()
    ids = [dlg._set_combo.itemData(i) for i in range(dlg._set_combo.count())]
    other = next((i for i, sid in enumerate(ids)
                  if sid and sid != dlg._set_combo.currentData()), None)
    chosen = dlg._set_combo.itemText(other) if other is not None else ""
    print(f"\n    changing 'Judged against' to {chosen!r}", flush=True)
    if other is not None:
        dlg._set_combo.setCurrentIndex(other)
        pump(app, 6000)
    after = inventory()
    after_entries = entries()
    d = diff(before, after)
    res["3_judged_against"] = {
        "chosen": chosen,
        "before": before, "after": after, "diff": d,
        "questions": asked,
        "entries_before": before_entries, "entries_after": after_entries,
        "names_gone": sorted(set(before_entries) - set(after_entries)),
        "names_new": sorted(set(after_entries) - set(before_entries)),
        "old_folders": sorted(
            str(p.relative_to(dest))
            for p in dest.glob("runs/**/reports/old/**/report_*.json")),
    }
    print(f"    files rewritten: {len(d['rewritten'])} of {d['files_before']}",
          flush=True)
    for k in d["rewritten"]:
        print(f"        REWRITTEN {k}", flush=True)
    print(f"    mtimes moved: {len(d['mtime_moved'])}", flush=True)
    print(f"    files added: {d['added']}", flush=True)
    print(f"    set_id changed: {d['set_id_changed']}", flush=True)
    print(f"    entry names that changed: gone={len(res['3_judged_against']['names_gone'])}"
          f" new={len(res['3_judged_against']['names_new'])}", flush=True)
    for q in asked:
        print(f"    QUESTION: {q['title']} | {q['body'][:140]}", flush=True)
    print(f"    copies in reports/old: "
          f"{len(res['3_judged_against']['old_folders'])}", flush=True)

    ok, why, tries, same = capture_settled(
        app, dlg, out / "J1-after-changing-judged-against.png",
        out / "J1b-after-changing-judged-against-again.png")
    res["3_photograph"] = {"taken": ok, "why": why, "identical_frames": same,
                           "attempts": tries}
    print(f"    photograph: {ok} {why}; two identical frames: {same} "
          f"after {tries}", flush=True)

    # ---- and every report still opens ----------------------------------
    opens = []
    for i in range(dlg._saved_combo.count()):
        dlg._saved_combo.setCurrentIndex(i)
        pump(app, 1500)
        opens.append({"entry": dlg._saved_combo.itemText(i),
                      "index_stuck": dlg._saved_combo.currentIndex() == i,
                      "document_length": len(dlg._view.toHtml())})
    res["4_every_entry_still_opens"] = opens
    print(f"    every entry still opens: "
          f"{all(o['index_stuck'] and o['document_length'] > 500 for o in opens)}"
          f" ({len(opens)} entries)", flush=True)

    (out / "the-older-reports.json").write_text(json.dumps(res, indent=1),
                                                encoding="utf-8")
    dlg.close()
    pump(app, 500)
    shutil.rmtree(work, ignore_errors=True)
    print("    done", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
