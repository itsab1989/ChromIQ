#!/usr/bin/env python3
"""Combined round 1, the seam: can the "Saved reports" pulldown (B8-250)
silently change which measurements the document covers (B8-246)?

A run is given two reports of ONE measurement judged against two different
sets. The newest wins by default. Picking the older one in the pulldown
re-anchors `_one_limit_set`, and every other measurement's place in the
document is decided by that anchor. This asks whether the page says so.

Every mutation is written and then READ BACK before the window is opened.
"""
from __future__ import annotations

import html as _html
import json
import os
import re
import shutil
import sys
import tempfile
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
try:
    import PyQt6.QtWebEngineWidgets  # noqa: F401
except ImportError:
    pass
from PyQt6.QtWidgets import QApplication, QDialog, QMessageBox   # noqa: E402
sys.path.insert(0, str(ROOT / "scripts"))
from onscreen_capture import capture_window, session_is_locked   # noqa: E402

SOURCE = Path.home() / "ChromIQ" / "printer-test"


def pump(app, ms=300):
    end = time.monotonic() + ms / 1000.0
    while time.monotonic() < end:
        app.processEvents()
        time.sleep(0.01)


def text_of(h: str) -> str:
    s = re.sub(r"<[^>]+>", "\n", h or "")
    return "\n".join(l.strip() for l in _html.unescape(s).splitlines() if l.strip())


def main() -> int:                                   # noqa: C901
    assert os.environ.get("CHROMIQ_SETTINGS_FILE"), "SANDBOX THE SETTINGS"
    out = Path(sys.argv[1]).resolve()
    out.mkdir(parents=True, exist_ok=True)
    R: dict = {}
    crashes: list = []
    prev = sys.excepthook
    sys.excepthook = lambda t, e, tb: (
        crashes.append("".join(traceback.format_exception(t, e, tb))),
        prev(t, e, tb))

    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("ChromIQ")
    from ui.styles import WinButtonLayoutStyle
    app.setStyle(WinButtonLayoutStyle("Fusion"))
    from core.settings import AppSettings
    work = Path(tempfile.mkdtemp(prefix="chromiq-b20r1s-"))
    settings = AppSettings()
    settings.set("custom_output_path", str(work))
    settings.set("appearance", "dark")
    settings.set("restore_last_session", False)
    assert settings.get("custom_output_path", "") == str(work), "SANDBOX FAILED"
    print(f"    screen locked at start: {session_is_locked()}", flush=True)

    proj = work / "printer-test"
    shutil.copytree(SOURCE, proj, symlinks=True)
    run1 = proj / "runs" / "run1"
    ti3 = run1 / "printer-test.ti3"
    rdir = run1 / "reports"

    QDialog.exec = lambda self: 1                     # type: ignore[assignment]
    for m in ("warning", "critical", "information", "question"):
        setattr(QMessageBox, m, staticmethod(lambda *a, **k: 0))
    QMessageBox.exec = lambda self: QMessageBox.StandardButton.Ok  # type: ignore
    from core.file_manager import FileManager
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    from ui.theme import apply_appearance
    MeasurementReportDialog._confirm = lambda self, t, b: True      # type: ignore
    apply_appearance(app, None, "dark")
    fm = FileManager(settings)
    del fm

    # ---- STAGE 1: a Generate, so every measurement has a report that
    #      carries the limit set it was judged against.
    d0 = MeasurementReportDialog(settings, None, initial_ti3=ti3)
    d0.resize(1400, 1000)
    d0.show()
    pump(app, 2500)
    before = {p.name for p in rdir.glob("report_*.json")}
    d0._on_generate_report()
    pump(app, 5000)
    fresh = sorted(set(p.name for p in rdir.glob("report_*.json")) - before)
    R["generated"] = fresh
    print(f"    stage 1 wrote {len(fresh)} report(s): {fresh[:3]}", flush=True)
    d0.close()
    pump(app, 600)

    # ---- STAGE 2: THE MUTATION, WRITTEN AND THEN READ BACK ---------------
    # The subject is the newest measurement. Give it a SECOND report whose
    # limit set really is a different set of numbers, saved LATER, so it is
    # the one the merge keeps.
    with_comp = []
    for p in sorted(rdir.glob("report_*.json")):
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except Exception:                            # noqa: BLE001
            continue
        if isinstance(d.get("compliance"), dict):
            with_comp.append((p, d))
    R["reports_with_compliance"] = len(with_comp)
    assert with_comp, "stage 1 wrote no compliance block: nothing to mix"
    newest = max(with_comp, key=lambda t: str(t[1].get("created") or ""))
    p_new, d_new = newest
    other = dict(d_new)
    comp = json.loads(json.dumps(d_new["compliance"]))
    thr = comp.get("thresholds") or {}
    moved = 0
    for k, v in list(thr.items()):
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            thr[k] = round(float(v) * 2.0, 4)
            moved += 1
    comp["thresholds"] = thr
    comp["set_id"] = str(comp.get("set_id", "")) + "-round1"
    comp["set_label"] = "Combined round 1 yardstick"
    other["compliance"] = comp
    p_other = rdir / (p_new.stem + "_2.json")
    p_other.write_text(json.dumps(other, indent=1), encoding="utf-8")
    os.utime(p_other, (time.time() + 5, time.time() + 5))   # written LAST
    back = json.loads(p_other.read_text(encoding="utf-8"))
    R["mutation"] = {
        "file": p_other.name,
        "thresholds_moved": moved,
        "set_id_on_disk": back["compliance"]["set_id"],
        "created_matches_subject": back.get("created") == d_new.get("created"),
        "mtime_is_later": p_other.stat().st_mtime > p_new.stat().st_mtime,
    }
    assert moved > 0, "the mutation moved no threshold: it would not land"
    assert back["compliance"]["set_id"].endswith("-round1"), "mutation lost"
    assert R["mutation"]["mtime_is_later"], "the twin is not the newer file"
    print(f"    stage 2: {p_other.name} carries {moved} moved thresholds, "
          f"set_id={back['compliance']['set_id']}", flush=True)

    # ---- STAGE 3: OPEN A FRESH WINDOW ON THAT STATE ----------------------
    dlg = MeasurementReportDialog(settings, None, initial_ti3=ti3)
    dlg.resize(1500, 1040)
    dlg.show()
    dlg.raise_()
    dlg.activateWindow()
    pump(app, 3500)
    c = dlg._saved_combo

    def snap(tag):
        doc = dlg._runs_for_document()
        return {
            "tag": tag,
            "showing": str((dlg._report or {}).get("_report_file") or ""),
            "entries": [c.itemText(i) for i in range(c.count())],
            "current": c.currentText(),
            "rows_in_window": dlg._profile_list.count(),
            "rows_in_document": len(doc),
            "document_files": [str(r.get("_report_file") or "") for r in doc],
            "mismatch_strip": dlg._mismatch.text(),
            "body": text_of(dlg._view.toHtml()),
        }

    S1 = snap("opened, the round-1 yardstick is newest")
    R["S1"] = S1
    print(f"    S1: showing={S1['showing']}  window rows={S1['rows_in_window']}"
          f"  document rows={S1['rows_in_document']}", flush=True)
    ok, why = capture_window(dlg, out / "SC1-newest-yardstick.png")
    R["S1_photo"] = "OK" if ok else f"REFUSED: {why}"
    print(f"      photograph: {R['S1_photo']}", flush=True)

    # ---- STAGE 4: PICK THE OTHER REPORT OF THE SAME MEASUREMENT ----------
    want = p_new.name
    idx = next((i for i in range(c.count())
                if c.itemData(i) and c.itemData(i)[1] == want), -1)
    R["index_of_the_other_report"] = idx
    if idx >= 0:
        c.setCurrentIndex(idx)
        pump(app, 2500)
        S2 = snap("picked the other report of the same measurement")
        R["S2"] = S2
        R["pick_took"] = S2["showing"] == want
        R["document_changed"] = (S2["document_files"] != S1["document_files"])
        print(f"    S2: asked {want} → showing {S2['showing']} "
              f"(took={R['pick_took']})", flush=True)
        print(f"    S2: document rows {S1['rows_in_document']} → "
              f"{S2['rows_in_document']}", flush=True)
        ok, why = capture_window(dlg, out / "SC2-other-yardstick.png")
        R["S2_photo"] = "OK" if ok else f"REFUSED: {why}"

    (out / "scope-seam.json").write_text(
        json.dumps(R, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8")
    (out / "crashes-scope.txt").write_text("\n\n".join(crashes) or "none",
                                           encoding="utf-8")
    print(f"    crashes: {len(crashes)}", flush=True)
    dlg.close()
    pump(app, 400)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
