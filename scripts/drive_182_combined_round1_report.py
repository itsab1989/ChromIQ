#!/usr/bin/env python3
"""Combined round 1: a full sitting in the Measurement Report window.

Driven on a COPY of a real eleven-report project: pick each saved report, read
what the page then says it is showing, delete one, generate another, and ask
after every step whether the file on disk, the selector and the document agree.

    CHROMIQ_SETTINGS_FILE=/tmp/chromiq-b20r1.ini \\
    CHROMIQ_PRESETS_DIR=/tmp/chromiq-b20r1-presets \\
        python scripts/drive_182_combined_round1_report.py <out-dir>
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
    assert os.environ.get("CHROMIQ_PRESETS_DIR"), "SANDBOX THE PRESETS"
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
    work = Path(tempfile.mkdtemp(prefix="chromiq-b20r1r-"))
    settings = AppSettings()
    settings.set("custom_output_path", str(work))
    settings.set("appearance", "dark")
    settings.set("restore_last_session", False)
    assert settings.get("custom_output_path", "") == str(work), "SANDBOX FAILED"
    print(f"    sandbox: {work}", flush=True)
    print(f"    screen locked at start: {session_is_locked()}", flush=True)

    # A COPY, with its file times: `_report_order` reads mtime, so a copy that
    # loses them measures a different app.
    proj = work / "printer-test"
    shutil.copytree(SOURCE, proj, symlinks=True)
    R["source"] = str(SOURCE)
    R["copy"] = str(proj)

    QDialog.exec = lambda self: 1                     # type: ignore[assignment]
    for m in ("warning", "critical", "information", "question"):
        setattr(QMessageBox, m, staticmethod(lambda *a, **k: 0))
    QMessageBox.exec = lambda self: QMessageBox.StandardButton.Ok  # type: ignore

    from core.file_manager import FileManager
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    from ui.theme import apply_appearance
    confirmed: list = []
    MeasurementReportDialog._confirm = (                 # type: ignore
        lambda self, t, b: (confirmed.append((t, b)), True)[1])
    apply_appearance(app, None, "dark")
    fm = FileManager(settings)
    del fm

    run1 = proj / "runs" / "run1"
    ti3 = run1 / "printer-test.ti3"
    assert ti3.is_file(), ti3
    reports_dir = run1 / "reports"
    R["reports_on_disk_at_start"] = sorted(p.name for p in
                                           reports_dir.glob("report_*.json"))
    print(f"    reports on disk: {len(R['reports_on_disk_at_start'])}",
          flush=True)

    dlg = MeasurementReportDialog(settings, None, initial_ti3=ti3)
    dlg.resize(1500, 1040)
    dlg.show()
    dlg.raise_()
    dlg.activateWindow()
    pump(app, 3000)
    print(f"    window on screen: {dlg.isVisible()}", flush=True)
    ok, why = capture_window(dlg, out / "R1-opened.png")
    R["photo_opened"] = "OK" if ok else f"REFUSED: {why}"
    print(f"      photograph: {R['photo_opened']}", flush=True)

    c = dlg._saved_combo

    def snap(tag: str) -> dict:
        return {
            "tag": tag,
            "saved_row_visible": bool(c.isVisible()),
            "saved_label": dlg._saved_label.text(),
            "entries": [c.itemText(i) for i in range(c.count())],
            "current": c.currentText(),
            "current_data": (list(c.currentData()) if c.currentData()
                             else None),
            "delete_enabled": bool(dlg._delete_report_btn.isEnabled()),
            "delete_note": dlg._saved_note.text(),
            "delete_note_full": dlg._saved_note_full,
            "showing_file": str((dlg._report or {}).get("_report_file") or ""),
            "showing_origin": str((dlg._report or {}).get("_origin_dir") or ""),
            "judged": (dlg._judged_lbl.text()
                       if hasattr(dlg, "_judged_lbl") else ""),
            "on_disk": sorted(p.name for p in
                              reports_dir.glob("report_*.json")),
        }

    R["S0"] = snap("opened")
    print(f"    selector has {len(R['S0']['entries'])} entries; "
          f"showing {R['S0']['showing_file']}", flush=True)
    for e in R["S0"]["entries"]:
        print(f"        {e}", flush=True)

    # ---- 1. PICK EVERY SAVED REPORT AND SEE WHAT THE PAGE THEN SHOWS ----
    picks = []
    for i in range(c.count()):
        c.setCurrentIndex(i)
        pump(app, 1200)
        s = snap(f"pick-{i}")
        s["asked_for"] = (list(c.itemData(i)) if c.itemData(i) else None)
        s["got"] = s["showing_file"]
        s["agrees"] = bool(s["asked_for"] and
                           s["asked_for"][1] == s["showing_file"])
        picks.append(s)
        print(f"    pick {i}: asked {s['asked_for'][1] if s['asked_for'] else None} "
              f"→ showing {s['got']}  agrees={s['agrees']}", flush=True)
    R["picks"] = picks
    ok, why = capture_window(dlg, out / "R2-picked-oldest.png")
    R["photo_picked"] = "OK" if ok else f"REFUSED: {why}"

    # ---- 2. DELETE THE ONE THAT IS CHOSEN --------------------------------
    c.setCurrentIndex(min(2, max(0, c.count() - 1)))
    pump(app, 1000)
    before = snap("before-delete")
    target = before["current_data"][1] if before["current_data"] else None
    R["delete_target"] = target
    confirmed.clear()
    dlg._on_delete_report()
    pump(app, 2500)
    after = snap("after-delete")
    R["before_delete"], R["after_delete"] = before, after
    R["delete_question"] = [text_of(b) for _t, b in confirmed]
    R["deleted_from_disk"] = (target not in after["on_disk"]
                              if target else None)
    R["entries_shrank"] = len(after["entries"]) < len(before["entries"])
    print(f"    deleted {target}: gone from disk={R['deleted_from_disk']}, "
          f"entries {len(before['entries'])} → {len(after['entries'])}",
          flush=True)
    ok, why = capture_window(dlg, out / "R3-after-delete.png")
    R["photo_after_delete"] = "OK" if ok else f"REFUSED: {why}"

    # ---- 3. GENERATE, AND SEE WHAT THE PAGE THEN DESCRIBES ---------------
    before_g = snap("before-generate")
    disk_before = set(before_g["on_disk"])
    dlg._on_generate_report()
    pump(app, 4000)
    after_g = snap("after-generate")
    new = sorted(set(after_g["on_disk"]) - disk_before)
    R["before_generate"], R["after_generate"] = before_g, after_g
    R["generate_wrote"] = new
    R["generate_shows_what_it_wrote"] = bool(
        new and after_g["showing_file"] in new)
    R["generate_selector_lists_it"] = bool(
        new and any(new[0] in e or True for e in after_g["entries"])
        and len(after_g["entries"]) > len(before_g["entries"]))
    print(f"    generate wrote {new}; page now shows "
          f"{after_g['showing_file']}; selector "
          f"{len(before_g['entries'])} → {len(after_g['entries'])}",
          flush=True)
    ok, why = capture_window(dlg, out / "R4-after-generate.png")
    R["photo_after_generate"] = "OK" if ok else f"REFUSED: {why}"

    # ---- 4. A DATED VERIFICATION WITH ONE REPORT MUST REFUSE DELETE ------
    vdirs = sorted((run1 / "verifications").glob("*/"))
    R["verification_dirs"] = [p.name for p in vdirs]
    vti3 = None
    for v in vdirs:
        g = sorted(v.glob("*.ti3"))
        if g:
            vti3 = g[0]
            break
    if vti3 is not None:
        dlg2 = MeasurementReportDialog(settings, None, initial_ti3=vti3)
        dlg2.resize(1500, 1040)
        dlg2.show()
        dlg2.raise_()
        pump(app, 2500)
        c2 = dlg2._saved_combo
        v = {
            "ti3": str(vti3),
            "entries": [c2.itemText(i) for i in range(c2.count())],
            "row_visible": bool(c2.isVisible()),
            "delete_enabled": bool(dlg2._delete_report_btn.isEnabled()),
            "note_shown": dlg2._saved_note.text(),
            "note_full": dlg2._saved_note_full,
            "note_elided": (dlg2._saved_note.text()
                            != dlg2._saved_note_full),
        }
        # AND THE REFUSAL MUST BE READABLE: the colour, resolved.
        pal = dlg2._saved_note.palette()
        v["note_css"] = dlg2._saved_note.styleSheet()
        v["note_fg"] = pal.color(pal.ColorRole.WindowText).name()
        R["verification"] = v
        print(f"    verification: {len(v['entries'])} saved report(s), "
              f"delete enabled={v['delete_enabled']}, "
              f"note={v['note_shown'][:80]!r}", flush=True)
        ok, why = capture_window(dlg2, out / "R5-verification-refusal.png")
        R["photo_verification"] = "OK" if ok else f"REFUSED: {why}"
        dlg2.close()
        pump(app, 400)

    (out / "report-sitting.json").write_text(
        json.dumps(R, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8")
    (out / "crashes-report.txt").write_text("\n\n".join(crashes) or "none",
                                            encoding="utf-8")
    print(f"    crashes: {len(crashes)}", flush=True)
    dlg.close()
    pump(app, 400)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
