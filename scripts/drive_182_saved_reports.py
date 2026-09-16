#!/usr/bin/env python3
"""B8-250: select and delete saved reports, in a REAL Measurement Report window.

The design authority, 2026-09-16: *"the selection and deletion of reports with
a selector input box is needed and should be made first"*.
"""
from __future__ import annotations
import json, os, re, shutil, sys, tempfile, time
from pathlib import Path

ROOT = Path("/Users/Basti/develop/ChromIQ"); sys.path.insert(0, str(ROOT))
try:
    import PyQt6.QtWebEngineWidgets  # noqa: F401
except ImportError:
    pass
from PyQt6.QtWidgets import QApplication, QDialog, QMessageBox  # noqa: E402
sys.path.insert(0, str(ROOT / "scripts"))
from onscreen_capture import capture_window                      # noqa: E402

PACK = Path("/tmp/rep-demo")
OUT = Path(sys.argv[1])
OPEN_ON = os.environ.get("OPEN_ON", "profiling")
PROJECT = os.environ.get("PROJECT", "Report-Limits-Report-Types")
RUN = os.environ.get("RUN", "run1")
R: dict = {}


def pump(app, ms=300):
    end = time.monotonic() + ms / 1000.0
    while time.monotonic() < end:
        app.processEvents(); time.sleep(0.01)


def text_of(h: str) -> str:
    import html as _h
    s = re.sub(r"<[^>]+>", "\n", h)
    return "\n".join(l.strip() for l in _h.unescape(s).splitlines() if l.strip())


def main() -> int:
    assert os.environ.get("CHROMIQ_SETTINGS_FILE"), "SANDBOX THE SETTINGS FIRST"
    assert os.environ.get("CHROMIQ_PRESETS_DIR"), "SANDBOX THE PRESETS FIRST"
    OUT.mkdir(parents=True, exist_ok=True)
    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("ChromIQ")
    import traceback
    sys.excepthook = lambda t, v, tb: traceback.print_exception(t, v, tb)
    from ui.styles import WinButtonLayoutStyle
    app.setStyle(WinButtonLayoutStyle("Fusion"))
    from core.settings import AppSettings
    work = Path(tempfile.mkdtemp(prefix="chromiq-saved-"))
    settings = AppSettings(); settings.set("custom_output_path", str(work))
    settings.set("appearance", "dark")
    settings.set("language", os.environ.get("LANG_CODE", "en"))
    from core.i18n import set_language
    set_language(settings.get("language", "en"))     # main.py:185 does this
    assert settings.get("custom_output_path", "") == str(work), "SANDBOX FAILED"
    src = PACK / PROJECT
    dst = work / src.name; shutil.copytree(src, dst)
    QDialog.exec = lambda self: 1                     # type: ignore[assignment]
    for m in ("warning", "critical", "information", "question"):
        setattr(QMessageBox, m, staticmethod(lambda *a, **k: 0))
    from core.file_manager import FileManager
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    from ui.theme import apply_appearance
    asked: list = []
    MeasurementReportDialog._confirm = (                 # type: ignore
        lambda self, t, b: (asked.append((t, b)), True)[1])
    apply_appearance(app, None, "dark")
    fm = FileManager(settings); del fm
    if OPEN_ON == "profiling":
        ti3 = dst / "runs" / RUN / f"{PROJECT}.ti3"
    else:
        ti3 = sorted((dst / "runs" / RUN / "verifications").glob("*/*.ti3"))[-1]
    assert ti3.is_file(), ti3
    dlg = MeasurementReportDialog(settings, None, initial_ti3=ti3)
    dlg.resize(1500, 1080); dlg.show(); dlg.raise_(); pump(app, 2500)
    print("window:", dlg.isVisible(), dlg.frameGeometry().width(), flush=True)

    combo = dlg._saved_combo
    R["S1_visible"] = combo.isVisible()
    R["S1_count"] = combo.count()
    R["S1_label"] = dlg._saved_label.text()
    R["S1_first_five"] = [combo.itemText(i) for i in range(min(5, combo.count()))]
    R["S1_delete_enabled"] = dlg._delete_report_btn.isEnabled()
    R["S1_note"] = dlg._saved_note.toolTip()
    print("S1", json.dumps({k: R[k] for k in list(R)}, indent=1), flush=True)
    ok, why = capture_window(dlg, OUT / "S1-selector.png")
    print("   photo:", ok, why, flush=True)

    # ---- S2: pick a different saved report and see the document follow
    before = text_of(dlg._view.toHtml())
    pick = None
    for i in range(combo.count()):
        if combo.itemText(i) != combo.itemText(combo.currentIndex()):
            pick = i
            break
    if pick is not None:
        was = combo.itemText(combo.currentIndex())
        combo.setCurrentIndex(pick)
        pump(app, 2000)
        after = text_of(dlg._view.toHtml())
        R["S2_from"] = was
        R["S2_to"] = combo.itemText(pick)
        R["S2_document_changed"] = before != after
        R["S2_head"] = next((l for l in after.splitlines()
                             if l.startswith("Report type:")), "")
        print("S2", R["S2_from"], "->", R["S2_to"],
              "changed", R["S2_document_changed"], "|", R["S2_head"], flush=True)
        ok, why = capture_window(dlg, OUT / "S2-another-report-chosen.png")
        print("   photo:", ok, why, flush=True)

    # ---- S3: delete it
    files_before = sorted(p.name for p in
                          (Path(str(dlg._report["_origin_dir"])) / "reports"
                           ).glob("report_*.json"))
    target = combo.currentData()
    asked.clear()
    dlg._delete_report_btn.click()
    pump(app, 2500)
    files_after = sorted(p.name for p in
                         (Path(str(dlg._report["_origin_dir"])) / "reports"
                          ).glob("report_*.json"))
    R["S3_asked"] = asked[0] if asked else None
    R["S3_target"] = target[1] if target else None
    R["S3_gone"] = sorted(set(files_before) - set(files_after))
    R["S3_count_before"] = len(files_before)
    R["S3_count_after"] = len(files_after)
    R["S3_combo_after"] = dlg._saved_combo.count()
    print("S3 asked:", (R["S3_asked"] or ("", ""))[0], flush=True)
    print("   body:", repr((R["S3_asked"] or ("", ""))[1])[:400], flush=True)
    print("   gone:", R["S3_gone"], R["S3_count_before"], "->",
          R["S3_count_after"], "combo", R["S3_combo_after"], flush=True)
    ok, why = capture_window(dlg, OUT / "S3-after-delete.png")
    print("   photo:", ok, why, flush=True)

    # ---- S4: delete down to the last one and watch the refusal appear
    guard = 0
    while dlg._delete_report_btn.isEnabled() and dlg._saved_combo.count() > 0 \
            and guard < 80:
        dlg._delete_report_btn.click(); pump(app, 500); guard += 1
    R["S4_presses"] = guard
    R["S4_left"] = dlg._saved_combo.count()
    R["S4_delete_enabled"] = dlg._delete_report_btn.isEnabled()
    R["S4_note"] = dlg._saved_note.toolTip()
    R["S4_document"] = next(
        (l for l in text_of(dlg._view.toHtml()).splitlines()
         if l.startswith("Report type:")), "")
    print("S4 pressed", guard, "left", R["S4_left"],
          "enabled", R["S4_delete_enabled"], flush=True)
    print("   note:", R["S4_note"], flush=True)
    print("  ", R["S4_document"], flush=True)
    ok, why = capture_window(dlg, OUT / "S4-down-to-the-last.png")
    print("   photo:", ok, why, flush=True)

    (OUT / "result.json").write_text(json.dumps(R, indent=1), encoding="utf-8")
    dlg.close(); pump(app, 200)
    return 0


sys.exit(main())
