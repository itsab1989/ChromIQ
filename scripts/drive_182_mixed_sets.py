#!/usr/bin/env python3
"""Reproduce: a report whose red line says the reports were not all judged
against the same limit set, on a REAL window, from the pack the design
authority supplied."""
from __future__ import annotations
import json, os, re, shutil, sys, tempfile, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[0]
if (ROOT / "ui").is_dir():
    sys.path.insert(0, str(ROOT))
else:
    ROOT = Path("/Users/Basti/develop/ChromIQ"); sys.path.insert(0, str(ROOT))
try:
    import PyQt6.QtWebEngineWidgets  # noqa: F401
except ImportError:
    pass
from PyQt6.QtWidgets import QApplication, QDialog, QMessageBox  # noqa: E402
sys.path.insert(0, str(ROOT / "scripts"))
from onscreen_capture import capture_window, session_is_locked  # noqa: E402

PACK = Path("/tmp/rep-demo")
PROJECT = sys.argv[1] if len(sys.argv) > 1 else "Report-Limits-Report-Types"
RUN = sys.argv[2] if len(sys.argv) > 2 else "run1"
OUT = Path(sys.argv[3] if len(sys.argv) > 3 else
           "/Users/Basti/Desktop/ChromIQ-beta20-proof/report-sets/round0")


def pump(app, ms=300):
    end = time.monotonic() + ms / 1000.0
    while time.monotonic() < end:
        app.processEvents(); time.sleep(0.01)


def text_of(html_s: str) -> str:
    s = re.sub(r"<[^>]+>", "\n", html_s)
    import html as _h
    s = _h.unescape(s)
    return "\n".join(l.strip() for l in s.splitlines() if l.strip())


def main() -> int:
    assert os.environ.get("CHROMIQ_SETTINGS_FILE"), "SANDBOX THE SETTINGS FIRST"
    assert os.environ.get("CHROMIQ_PRESETS_DIR"), "SANDBOX THE PRESETS FIRST"
    OUT.mkdir(parents=True, exist_ok=True)
    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("ChromIQ")
    def _hook(t, v, tb):
        import traceback; traceback.print_exception(t, v, tb)
    sys.excepthook = _hook
    from ui.styles import WinButtonLayoutStyle
    app.setStyle(WinButtonLayoutStyle("Fusion"))
    from core.settings import AppSettings
    work = Path(tempfile.mkdtemp(prefix="chromiq-sets-"))
    settings = AppSettings()
    settings.set("custom_output_path", str(work))
    settings.set("appearance", "dark")
    assert settings.get("custom_output_path", "") == str(work), "SANDBOX FAILED"
    print("sandbox:", work, flush=True)
    src = PACK / PROJECT
    dst = work / src.name
    shutil.copytree(src, dst)
    QDialog.exec = lambda self: 1                     # type: ignore[assignment]
    for m in ("warning", "critical", "information", "question"):
        setattr(QMessageBox, m, staticmethod(lambda *a, **k: 0))
    from core.file_manager import FileManager
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    from ui.theme import apply_appearance
    MeasurementReportDialog._confirm = (lambda self, t, x: True)  # type: ignore
    apply_appearance(app, None, "dark")
    fm = FileManager(settings); del fm
    WHERE = os.environ.get("OPEN_ON", "verification")
    if WHERE == "profiling":
        ti3s = sorted(p for p in (dst / "runs" / RUN).glob("*.ti3")
                      if p.name not in ("preconditioning.ti3", "merged.ti3"))
    else:
        ti3s = sorted((dst / "runs" / RUN / "verifications").glob("*/*.ti3"))
    assert ti3s, f"no {WHERE} measurement in {RUN}"
    print("opened on:", ti3s[-1].relative_to(work), flush=True)
    dlg = MeasurementReportDialog(settings, None, initial_ti3=ti3s[-1])
    dlg.resize(1500, 1050); dlg.show(); dlg.raise_()
    pump(app, 2500)
    print("window on screen:", dlg.isVisible(), dlg.frameGeometry().width(),
          "x", dlg.frameGeometry().height(), flush=True)
    runs = dlg._runs_for_report()
    rows = [{"created": r.get("created"), "origin": str(r.get("_origin_dir", "")).split("/runs/")[-1],
             "file": r.get("_report_file"), "type": r.get("report_type"),
             "set": (r.get("compliance") or {}).get("set_id"),
             "judged": dlg._judged_label_for(r),
             "fresh": bool(r.get("_fresh"))}
            for r in runs]
    for x in rows:
        print("  ROW", x, flush=True)
    doc = dlg._view.toHtml()
    body = text_of(doc)
    (OUT / "document.txt").write_text(body, encoding="utf-8")
    warn = [l for l in body.splitlines() if "judged against" in l.lower()
            or "Warning" in l]
    print("--- warning lines ---", flush=True)
    for l in warn: print("  ", l, flush=True)
    print("--- INFO count:", body.count("INFO"), " PASS:", body.count("PASS"),
          " FAIL:", body.count("FAIL"), flush=True)
    sc = dlg._set_combo
    print("set combo:", sc.currentText(), "enabled", sc.isEnabled(), flush=True)
    if session_is_locked():
        print("SCREEN LOCKED before capture", flush=True)
    ok, why = capture_window(dlg, OUT / "A-opened.png")
    print("photo A-opened:", ok, why, flush=True)
    (OUT / "rows.json").write_text(json.dumps(rows, indent=1), encoding="utf-8")
    dlg.close(); pump(app, 300)
    return 0


sys.exit(main())
