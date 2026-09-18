#!/usr/bin/env python3
"""B8-383/382/381/380 after the document record, driven in a real window.

The SAME sequence `drive_b22_knuts_five_report_defects.py` drove before any of
this was built, on the same project, so the numbers can be laid side by side:

  1. the arrangement, control by control, top to bottom;
  2. pick every entry in turn, and watch the page AND the settings;
  3. Generate report, and count the files on disk and the entries in the list;
  4. "Show all measurement runs" ON, Generate again, and count both again;
  5. change "Judged against" and check that not one byte on disk moves for a
     report that was GENERATED (D23, Knut 2026-09-18: "Agreed. D23 stands.");
  6. Delete Selected Report, and find the files in their old/ folder.

    CHROMIQ_SETTINGS_FILE=… CHROMIQ_PRESETS_DIR=… \\
        python scripts/drive_b22_the_document_record.py <project> <out>
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


def _frames_match(a: Path, b: Path, tol: int = 8) -> bool:
    """Whether two captures show the same picture, pixel for pixel."""
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


def capture_settled(app, win, first: Path, second: Path, tries: int = 5):
    """Photograph *win* twice and keep going until two frames agree."""
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
    work = Path(tempfile.mkdtemp(prefix="chromiq-b22-doc-"))
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
        found = {}
        for f in sorted(dest.glob("runs/*/verifications/*/reports/report_*.json")):
            try:
                d = json.loads(f.read_text(encoding="utf-8"))
            except Exception:                          # noqa: BLE001
                continue
            doc = d.get("document") or {}
            found[str(f.relative_to(dest))] = (
                f"{(d.get('compliance') or {}).get('set_id')}"
                f" / {d.get('report_type')} / doc={doc.get('id', '-')}")
        return found

    def raw() -> "dict[str, str]":
        """sha256 of every live report file, to prove nothing was rewritten."""
        return {str(f.relative_to(dest)):
                hashlib.sha256(f.read_bytes()).hexdigest()[:12]
                for f in sorted(dest.glob(
                    "runs/*/verifications/*/reports/report_*.json"))}

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
                    ("Delete Selected Report", dlg._delete_report_btn),
                    ("Generated reports", dlg._saved_combo),
                    ("Save report as PDF", dlg._pdf_btn),
                    ("Show all measurement runs", dlg._all_runs_check),
                    ("Show detailed data", dlg._detail_check),
                    ("Report type", dlg._type_combo),
                    ("Judged against", dlg._set_combo)):
        try:
            order.append((name, w.mapTo(dlg, w.rect().topLeft()).y(),
                          w.mapTo(dlg, w.rect().topLeft()).x(), w.width()))
        except Exception:                              # noqa: BLE001
            pass
    order.sort(key=lambda t: (t[1], t[2]))
    print("    [1] the controls, top to bottom (y, x, width):", flush=True)
    for n, y, x, wdt in order:
        print(f"        y={y:4d}  x={x:4d}  w={wdt:4d}  {n}", flush=True)
    res["1_arrangement"] = [{"control": n, "y": y, "x": x, "w": wdt}
                            for n, y, x, wdt in order]
    # TWO CONSECUTIVE IDENTICAL FRAMES, because another process may be driving
    # the app at the same time and a single frame cannot tell a settled window
    # from one mid-repaint. It caught one here on the first run: the two
    # captures came back 2080x2944 and 2120x3000, so the window was still
    # settling when the first was taken and that frame was not the window Knut
    # would see.
    ok, why, tries, same = capture_settled(
        app, dlg, out / "D1-the-arrangement.png",
        out / "D1b-the-arrangement-again.png")
    print(f"        photograph: {ok} {why}; identical consecutive frames: "
          f"{same} after {tries} attempt(s)", flush=True)
    res["1_photograph"] = {"taken": bool(ok), "why": why,
                           "two_identical_frames": bool(same),
                           "attempts": tries}

    # ---- 2 + 3. choosing a generated report ----------------------------
    picks = []
    base_files = report_files()
    res["files_at_open"] = base_files
    res["entries_at_open"] = controls()["saved_entries"]
    print(f"    saved report files on disk at open: {len(base_files)}; "
          f"entries in the list: {dlg._saved_combo.count()}", flush=True)
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
        print(f"    [2/3] pick {i}: {before_c['saved_entries'][i][:70]!r}",
              flush=True)
        print(f"          stayed picked: {picks[-1]['index_stuck']}   "
              f"document redrawn: {picks[-1]['document_changed']}", flush=True)
        print(f"          ticks {before_c['show_all_runs']}/"
              f"{before_c['show_detail']} -> {after_c['show_all_runs']}/"
              f"{after_c['show_detail']}", flush=True)
    res["2_3_picking_a_saved_report"] = picks
    capture_window(dlg, out / "D2-after-picking-a-generated-report.png")

    # ---- 4. Generate report -------------------------------------------
    dlg._all_runs_check.setChecked(True)
    pump(app, 1500)
    b, be = report_files(), dlg._saved_combo.count()
    dlg._generate_btn.click()
    pump(app, 4500)
    a, ae = report_files(), dlg._saved_combo.count()
    added = sorted(set(a) - set(b))
    print(f"    [4] Generate with 'Show all measurement runs' ON: "
          f"{len(b)} files -> {len(a)}, {be} entries -> {ae}", flush=True)
    res["4_generate_show_all"] = {"files_before": len(b), "files_after": len(a),
                                  "entries_before": be, "entries_after": ae,
                                  "added": added,
                                  "entries": controls()["saved_entries"]}
    capture_window(dlg, out / "D4a-after-generate.png")

    # …and again, which is Knut's own second press
    b2, be2 = report_files(), dlg._saved_combo.count()
    dlg._generate_btn.click()
    pump(app, 4500)
    a2, ae2 = report_files(), dlg._saved_combo.count()
    print(f"    [4] Generate again: {len(b2)} files -> {len(a2)}, "
          f"{be2} entries -> {ae2}", flush=True)
    res["4_generate_again"] = {"files_before": len(b2), "files_after": len(a2),
                               "entries_before": be2, "entries_after": ae2,
                               "added": sorted(set(a2) - set(b2))}
    capture_window(dlg, out / "D4b-generate-again.png")

    # ---- 5. "Judged against" may not touch a generated report ----------
    before_raw = raw()
    before_entries = controls()["saved_entries"]
    ids = [dlg._set_combo.itemData(i) for i in range(dlg._set_combo.count())]
    other = next((i for i, sid in enumerate(ids)
                  if sid and sid != dlg._set_combo.currentData()), None)
    if other is not None:
        print(f"    [5] changing 'Judged against' to "
              f"{dlg._set_combo.itemText(other)!r}", flush=True)
        dlg._set_combo.setCurrentIndex(other)
        pump(app, 5000)
    after_raw = raw()
    after_entries = controls()["saved_entries"]
    docs = {k for k, v in before_files.items()} if False else set()
    generated = {k for k, v in after_raw.items()
                 if "doc=" in report_files().get(k, "")
                 and not report_files()[k].endswith("doc=-")}
    moved = sorted(k for k in before_raw
                   if after_raw.get(k) != before_raw.get(k))
    print(f"    [5] files rewritten: {len(moved)} of {len(before_raw)}", flush=True)
    print(f"        of which GENERATED documents: "
          f"{sorted(set(moved) & generated)}", flush=True)
    res["5_judged_against"] = {
        "entries_before": before_entries, "entries_after": after_entries,
        "files_rewritten": moved,
        "generated_documents": sorted(generated),
        "generated_documents_rewritten": sorted(set(moved) & generated),
        # **AS SETS, NOT BY POSITION.** The list is newest first and a rewrite
        # moves a file's mtime, so comparing position by position reports every
        # entry as "relabelled" when nothing but the ORDER moved. The first cut
        # of this driver did exactly that.
        "names_gone": sorted(set(before_entries) - set(after_entries)),
        "names_new": sorted(set(after_entries) - set(before_entries)),
        "names_kept": sorted(set(before_entries) & set(after_entries)),
    }
    capture_window(dlg, out / "D5-after-changing-judged-against.png")

    # ---- 6. Delete Selected Report ------------------------------------
    # back onto a generated document, then delete it
    gen = next((i for i in range(dlg._saved_combo.count())
                if str(dlg._saved_combo.itemData(i) or "").startswith("id:")),
               None)
    res["6_delete"] = {"found_a_generated_entry": gen is not None}
    if gen is not None:
        dlg._saved_combo.setCurrentIndex(gen)
        pump(app, 2500)
        label = dlg._saved_combo.itemText(gen)
        live_before = set(report_files())
        n_before = dlg._saved_combo.count()
        asked.clear()
        dlg._delete_report_btn.click()
        pump(app, 3500)
        live_after = set(report_files())
        old_files = sorted(str(p.relative_to(dest))
                           for p in dest.glob("runs/**/old/**/report_*.json"))
        print(f"    [6] deleted {label[:60]!r}: "
              f"{len(live_before)} live files -> {len(live_after)}, "
              f"{n_before} entries -> {dlg._saved_combo.count()}", flush=True)
        print(f"        moved into old/: {old_files}", flush=True)
        res["6_delete"].update({
            "entry": label,
            "live_before": sorted(live_before), "live_after": sorted(live_after),
            "gone_from_live": sorted(live_before - live_after),
            "in_old": old_files,
            "entries_before": n_before, "entries_after": dlg._saved_combo.count(),
            "question": asked[0] if asked else None,
        })
        capture_window(dlg, out / "D6-after-delete.png")

    (out / "the-document-record.json").write_text(
        json.dumps(res, indent=1), encoding="utf-8")
    dlg.close()
    pump(app, 500)
    shutil.rmtree(work, ignore_errors=True)
    print("    done", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
