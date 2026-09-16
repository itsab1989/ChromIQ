#!/usr/bin/env python3
"""Two GRADED verification histories, judged against different limit sets, in
one window: the shape D9 named ("two projects") and the one the red line was
written for. Driven in a REAL window."""
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
from onscreen_capture import capture_window  # noqa: E402

PACK = Path("/tmp/rep-demo")
OUT = Path(sys.argv[1])


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
    work = Path(tempfile.mkdtemp(prefix="chromiq-sets2-"))
    settings = AppSettings(); settings.set("custom_output_path", str(work))
    settings.set("appearance", "dark")
    assert settings.get("custom_output_path", "") == str(work), "SANDBOX FAILED"
    src = PACK / "Report-Limits-Threshold-Series"
    dst = work / src.name; shutil.copytree(src, dst)
    QDialog.exec = lambda self: 1                     # type: ignore[assignment]
    for m in ("warning", "critical", "information", "question"):
        setattr(QMessageBox, m, staticmethod(lambda *a, **k: 0))
    from core.file_manager import FileManager
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    from ui.theme import apply_appearance
    MeasurementReportDialog._confirm = (lambda self, t, x: True)  # type: ignore
    apply_appearance(app, None, "dark")
    fm = FileManager(settings); del fm
    first = sorted((dst / "runs" / "run1" / "verifications").glob("*/*.ti3"))[-1]
    second = sorted((dst / "runs" / "run3" / "verifications").glob("*/*.ti3"))[-1]
    dlg = MeasurementReportDialog(settings, None, initial_ti3=first)
    dlg.resize(1500, 1050); dlg.show(); dlg.raise_(); pump(app, 2200)
    print("window:", dlg.isVisible(), dlg.frameGeometry().width(), flush=True)

    def snap(tag):
        runs = dlg._runs_for_report()
        body = text_of(dlg._view.toHtml())
        (OUT / f"{tag}.txt").write_text(body, encoding="utf-8")
        doc_runs = dlg._runs_for_document()
        print(f"-- {tag}: loaded={len(runs)} in-document={len(doc_runs)}", flush=True)
        for r in runs:
            print("   ", str(r.get('_origin_dir','')).split('/runs/')[-1],
                  (r.get('compliance') or {}).get('set_id'),
                  "IN" if any(dlg._run_key(x) == dlg._run_key(r) for x in doc_runs)
                  else "OUT", flush=True)
        for l in body.splitlines():
            if "limit set" in l and ("different" in l or "not all" in l):
                print("   LINE:", l, flush=True)
        print("   PASS", body.count("PASS"), "FAIL", body.count("FAIL"),
              "INFO", body.count("INFO"), flush=True)
        ok, why = capture_window(dlg, OUT / f"{tag}.png")
        print("   photo:", ok, why, flush=True)

    snap("A-one-project")
    dlg._add_source(second); pump(app, 1800)
    snap("B-second-run-added")
    dlg.close(); pump(app, 200)
    return 0


sys.exit(main())
