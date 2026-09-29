#!/usr/bin/env python3
"""Why did ONE capture of round 3's delete run refuse, twice, in the same place?

`F-after-the-delete.png` came back *"screencapture refused the window's
rectangle"* on both runs and every other shot in the same process succeeded. A
refused capture is a finding, so this reproduces that one press and measures
each step of `capture_window` instead of reporting the last line of it.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
try:
    import PyQt6.QtWebEngineWidgets  # noqa: F401
except ImportError:
    pass
from PyQt6.QtWidgets import QApplication, QDialog, QMessageBox   # noqa: E402

sys.path.insert(0, str(ROOT / "scripts"))
import onscreen_capture as OC                                    # noqa: E402

SOURCE = Path.home() / "ChromIQ" / "Demo-Switching"
DATE = "2026-06-24_164000"


def pump(app, ms=300):
    end = time.monotonic() + ms / 1000.0
    while time.monotonic() < end:
        app.processEvents()
        time.sleep(0.01)


def main() -> int:
    assert os.environ.get("CHROMIQ_SETTINGS_FILE"), "SANDBOX THE SETTINGS"
    assert not os.environ.get("QT_QPA_PLATFORM"), "ON SCREEN IS THE DEFAULT"
    out = Path(sys.argv[1]).resolve()
    out.mkdir(parents=True, exist_ok=True)
    R: dict = {}

    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("ChromIQ")
    from ui.styles import WinButtonLayoutStyle
    app.setStyle(WinButtonLayoutStyle("Fusion"))
    from core.settings import AppSettings
    work = Path(tempfile.mkdtemp(prefix="chromiq-b20r3p-"))
    settings = AppSettings()
    settings.set("custom_output_path", str(work))
    settings.set("appearance", "dark")
    settings.set("restore_last_session", False)
    from ui.theme import apply_appearance
    apply_appearance(app, None, "dark")

    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    MeasurementReportDialog._confirm = lambda self, t, b: True   # type: ignore
    QDialog.exec = lambda self: 1                     # type: ignore[assignment]
    for m in ("warning", "critical", "information", "question"):
        setattr(QMessageBox, m, staticmethod(lambda *a, **k: 0))
    QMessageBox.exec = lambda self: QMessageBox.StandardButton.Ok  # type: ignore

    proj = work / "Demo-Switching"
    shutil.copytree(SOURCE, proj, symlinks=True)
    v = proj / "runs" / "run2" / "verifications" / DATE
    d = MeasurementReportDialog(settings, None,
                                initial_ti3=v / "Demo-Switching-verify.ti3")
    d.resize(1500, 1050)
    d.show()
    pump(app, 3000)

    def measure(tag: str) -> dict:
        g = d.frameGeometry()
        wid = OC.window_id_for(d)
        info = {"tag": tag, "frame": [g.x(), g.y(), g.width(), g.height()],
                "visible": d.isVisible(), "minimised": d.isMinimized(),
                "window_id": wid}
        p = out / f"probe-{tag}.png"
        if wid is not None:
            got = OC._grab_window_id(wid, p)
            info["window_id_route"] = got
            info["flat"] = OC._is_one_flat_colour(p) if got else None
            if got:
                from PyQt6.QtGui import QImage
                im = QImage(str(p))
                info["size"] = [im.width(), im.height()]
        rect = f"{g.x()},{g.y()},{g.width()},{g.height()}"
        q = out / f"probe-{tag}-rect.png"
        info["rect"] = rect
        info["region_route"] = OC._grab_region(rect, q)
        q.unlink(missing_ok=True)
        ok, why = OC.capture_window(d, out / f"probe-{tag}-capture.png")
        info["capture_window"] = [ok, why]
        print(f"    {tag}: {json.dumps(info)}", flush=True)
        return info

    R["before"] = measure("01-before")
    d._on_generate_report()
    pump(app, 3000)
    R["after_generate"] = measure("02-after-generate")
    d._on_delete_report()
    pump(app, 3000)
    R["after_delete"] = measure("03-after-delete")
    pump(app, 4000)
    R["after_delete_settled"] = measure("04-after-delete-settled")

    (out / "capture-probe.json").write_text(json.dumps(R, indent=2),
                                            encoding="utf-8")
    d.close()
    pump(app, 500)
    return 0


if __name__ == "__main__":
    sys.exit(main())
