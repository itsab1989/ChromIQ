#!/usr/bin/env python3
"""Combined round 1: the delete rule on a dated verification, end to end.

One report → Delete refused, with a reason a reader can see. Generate a second
→ the refusal must lift. Delete one → it must come back. And the run list is
counted before and after every step, because a row that leaves the window is
what a deleted report really costs.
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

SOURCE = Path.home() / "ChromIQ" / "Demo-Switching"


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
    work = Path(tempfile.mkdtemp(prefix="chromiq-b20r1v-"))
    settings = AppSettings()
    settings.set("custom_output_path", str(work))
    settings.set("appearance", "dark")
    settings.set("restore_last_session", False)
    assert settings.get("custom_output_path", "") == str(work), "SANDBOX FAILED"
    print(f"    screen locked at start: {session_is_locked()}", flush=True)

    proj = work / "Demo-Switching"
    shutil.copytree(SOURCE, proj, symlinks=True)

    QDialog.exec = lambda self: 1                     # type: ignore[assignment]
    for m in ("warning", "critical", "information", "question"):
        setattr(QMessageBox, m, staticmethod(lambda *a, **k: 0))
    QMessageBox.exec = lambda self: QMessageBox.StandardButton.Ok  # type: ignore

    from core.file_manager import FileManager
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    from ui.theme import apply_appearance
    asked: list = []
    MeasurementReportDialog._confirm = (                 # type: ignore
        lambda self, t, b: (asked.append((t, b)), True)[1])
    apply_appearance(app, None, "dark")
    fm = FileManager(settings)
    del fm

    vdir = proj / "runs" / "run2" / "verifications" / "2026-05-20_090500"
    ti3 = sorted(vdir.glob("*.ti3"))[0]
    rdir = vdir / "reports"
    dlg = MeasurementReportDialog(settings, None, initial_ti3=ti3)
    dlg.resize(1500, 1040)
    dlg.show()
    dlg.raise_()
    dlg.activateWindow()
    pump(app, 3000)
    print(f"    window on screen: {dlg.isVisible()}", flush=True)
    c = dlg._saved_combo

    def snap(tag):
        return {
            "tag": tag,
            "row_visible": bool(c.isVisible()),
            "label": dlg._saved_label.text(),
            "entries": [c.itemText(i) for i in range(c.count())],
            "current": c.currentText(),
            "delete_enabled": bool(dlg._delete_report_btn.isEnabled()),
            "note_shown": dlg._saved_note.text(),
            "note_full": dlg._saved_note_full,
            "note_visible": bool(dlg._saved_note.isVisible()),
            "note_css": dlg._saved_note.styleSheet(),
            "list_rows": dlg._profile_list.count(),
            "showing": str((dlg._report or {}).get("_report_file") or ""),
            "on_disk": sorted(p.name for p in rdir.glob("report_*.json")),
        }

    R["V1_one_report"] = snap("one report")
    print(f"    V1: entries={len(R['V1_one_report']['entries'])} "
          f"delete_enabled={R['V1_one_report']['delete_enabled']} "
          f"note={R['V1_one_report']['note_shown'][:100]!r}", flush=True)
    ok, why = capture_window(dlg, out / "V1-refusal.png")
    R["V1_photo"] = "OK" if ok else f"REFUSED: {why}"
    print(f"      photograph: {R['V1_photo']}", flush=True)

    # -- press Delete anyway: nothing may go ------------------------------
    asked.clear()
    dlg._on_delete_report()
    pump(app, 1500)
    R["V1_after_pressing_delete"] = snap("after pressing a refused delete")
    R["V1_question_asked"] = [text_of(b) for _t, b in asked]
    print(f"    V1: after pressing Delete, files on disk = "
          f"{R['V1_after_pressing_delete']['on_disk']}", flush=True)

    # -- generate a SECOND report of the same date -------------------------
    dlg._on_generate_report()
    pump(app, 4000)
    R["V2_two_reports"] = snap("two reports")
    print(f"    V2: entries={len(R['V2_two_reports']['entries'])} "
          f"delete_enabled={R['V2_two_reports']['delete_enabled']} "
          f"on_disk={R['V2_two_reports']['on_disk']}", flush=True)
    for e in R["V2_two_reports"]["entries"]:
        print(f"        {e}", flush=True)
    ok, why = capture_window(dlg, out / "V2-two-reports.png")
    R["V2_photo"] = "OK" if ok else f"REFUSED: {why}"

    # -- pick the older of the two and see whether the page follows --------
    if c.count() > 1:
        c.setCurrentIndex(1)
        pump(app, 1800)
        R["V3_picked_older"] = snap("picked the older of two")
        R["V3_asked"] = list(c.itemData(1)) if c.itemData(1) else None
        R["V3_follows"] = (R["V3_asked"][1] == R["V3_picked_older"]["showing"]
                           if R["V3_asked"] else None)
        print(f"    V3: asked {R['V3_asked'][1] if R['V3_asked'] else None} "
              f"→ showing {R['V3_picked_older']['showing']} "
              f"follows={R['V3_follows']}", flush=True)
        ok, why = capture_window(dlg, out / "V3-picked-older.png")
        R["V3_photo"] = "OK" if ok else f"REFUSED: {why}"

    # -- delete one: the refusal must come back ---------------------------
    asked.clear()
    dlg._on_delete_report()
    pump(app, 2500)
    R["V4_after_delete"] = snap("after deleting one of two")
    R["V4_question"] = [text_of(b) for _t, b in asked]
    print(f"    V4: on_disk={R['V4_after_delete']['on_disk']} "
          f"delete_enabled={R['V4_after_delete']['delete_enabled']} "
          f"note={R['V4_after_delete']['note_shown'][:100]!r}", flush=True)
    ok, why = capture_window(dlg, out / "V4-refusal-back.png")
    R["V4_photo"] = "OK" if ok else f"REFUSED: {why}"

    # ---- V5: THE RULE, ASKED OF EVERY ENTRY IN THE SELECTOR --------------
    # After V4 one date is back to a single saved report. Walk the whole
    # selector and ask, per entry: how many reports does that measurement
    # really have on disk, and does the window refuse the last one?
    from core.file_manager import VERIFICATIONS_DIRNAME
    v5 = []
    for i in range(c.count()):
        c.setCurrentIndex(i)
        pump(app, 900)
        data = c.itemData(i)
        key, name = (list(data) if data else (None, None))
        origin = Path(str(key).split("|")[0]) if key else None
        on_disk = sorted(p.name for p in (origin / "reports").glob("report_*.json")) \
            if origin and (origin / "reports").is_dir() else []
        v5.append({
            "entry": c.itemText(i),
            "file": name,
            "origin": str(origin),
            "is_dated_verification": bool(
                origin and origin.parent.name == VERIFICATIONS_DIRNAME),
            "reports_of_that_measurement_on_disk": on_disk,
            "delete_enabled": bool(dlg._delete_report_btn.isEnabled()),
            "note": dlg._saved_note_full,
        })
        print(f"    V5[{i}] {c.itemText(i)[:60]!r:64} "
              f"on_disk={len(on_disk)} enabled={v5[-1]['delete_enabled']}",
              flush=True)
    R["V5_every_entry"] = v5
    # THE RULE: a dated verification whose measurement has ONE report left
    # must refuse. Broken means a verdict can be destroyed.
    R["V5_rule_broken"] = [
        e for e in v5
        if e["is_dated_verification"]
        and len(e["reports_of_that_measurement_on_disk"]) <= 1
        and e["delete_enabled"]]
    print(f"    V5: rule broken on {len(R['V5_rule_broken'])} entr(y/ies)",
          flush=True)
    ok, why = capture_window(dlg, out / "V5-every-entry.png")
    R["V5_photo"] = "OK" if ok else f"REFUSED: {why}"

    (out / "verify-sitting.json").write_text(
        json.dumps(R, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8")
    (out / "crashes-verify.txt").write_text("\n\n".join(crashes) or "none",
                                            encoding="utf-8")
    print(f"    crashes: {len(crashes)}", flush=True)
    dlg.close()
    pump(app, 400)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
