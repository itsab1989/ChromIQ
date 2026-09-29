#!/usr/bin/env python3
"""File a verification chart with the app, on screen, and photograph what it says.

#182, beta 22. ChromIQ now writes a control-strip declaration beside every
verification chart it creates (`workflow/control_strip.py`), and tells the user
when a chart cannot carry one. This driver shows both in a REAL window:

1. it builds two real charts with ``targen`` and ``printtarg``, one big enough
   to carry a strip and one that is not;
2. it opens the Create Chart tab in a real top-level window;
3. it puts each chart at the run root and lets the app finish a generation with
   Run type = Verification, which is the funnel every creation path reaches;
4. it photographs the tab after each, with ``capture_window`` and never
   ``widget.grab()``, two frames that have to agree pixel for pixel;
5. and it photographs the real M-VERIFY-NO-CONTROL-STRIP window, with its real
   text, rather than asserting that it would have opened.

    export CHROMIQ_SETTINGS_FILE=/tmp/chromiq-strip/settings.ini
    export CHROMIQ_PRESETS_DIR=/tmp/chromiq-strip/presets
    python scripts/drive_the_control_strip_declaration.py <out-dir>
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(os.environ.get("CHROMIQ_TREE")
            or Path(__file__).resolve().parents[1]).resolve()
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

ARGYLL = Path("/Applications/Argyll/bin")
#: (label, patch count). Measured: 210 fills 27 rungs, 16 fills 7.
CHARTS = (("big", 210), ("tiny", 16))


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


def capture_settled(app, win, first: Path, second: Path, tries: int = 4):
    """Two consecutive photographs that agree pixel for pixel, or say so."""
    from onscreen_capture import capture_window
    ok = ok2 = False
    why = ""
    for n in range(1, tries + 1):
        pump(app, 900)
        ok, why = capture_window(win, first)
        pump(app, 900)
        ok2, why2 = capture_window(win, second)
        why = why or why2
        if ok and ok2 and _frames_match(first, second):
            return {"photographed": True, "settled": True, "attempts": n,
                    "file": first.name, "why": why}
    return {"photographed": bool(ok and ok2), "settled": False,
            "attempts": tries, "file": first.name, "why": why}


def build_charts(work: Path) -> "dict[str, Path]":
    out = {}
    for label, n in CHARTS:
        d = work / label
        d.mkdir(parents=True, exist_ok=True)
        for cmd in ([str(ARGYLL / "targen"), "-v", "-d2", f"-f{n}", "-e4",
                     "-B4", "-G", "chart"],
                    [str(ARGYLL / "printtarg"), "-v", "-ii1", "-pA4", "-t300",
                     "chart"]):
            subprocess.run(cmd, cwd=str(d), check=True, capture_output=True,
                           timeout=300)
        out[label] = d / "chart.ti2"
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    args = ap.parse_args()

    assert os.environ.get("CHROMIQ_SETTINGS_FILE"), "SANDBOX THE SETTINGS FIRST"
    assert os.environ.get("CHROMIQ_PRESETS_DIR"), "SANDBOX THE PRESETS FIRST"
    assert not os.environ.get("QT_QPA_PLATFORM"), "this DRIVER opens a window"

    out = Path(args.out).resolve()
    shots = out / "photographs"
    shots.mkdir(parents=True, exist_ok=True)

    from PyQt6.QtWidgets import (QApplication, QMainWindow, QMessageBox)
    from onscreen_capture import session_is_locked
    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("ChromIQ")
    from ui.styles import WinButtonLayoutStyle
    app.setStyle(WinButtonLayoutStyle("Fusion"))   # what main.py does

    for m in ("warning", "critical", "information", "question"):
        setattr(QMessageBox, m, staticmethod(lambda *a, **k: 0))

    from core.argyll_runner import ArgyllRunner
    from core.file_manager import FileManager, Project
    from core.measurement_target import RUN_TYPE_VERIFICATION
    from core.settings import AppSettings
    from ui.measurement_target_bar import MeasurementTargetController
    from ui.tabs.tab_chart import TabChart
    from workflow import control_strip as cs

    settings = AppSettings()
    work = out / "work"
    projects = work / "projects"
    projects.mkdir(parents=True, exist_ok=True)
    settings.set("custom_output_path", str(projects))
    settings.set("argyll_bin_path", str(ARGYLL))
    settings.set("language", "en")
    assert settings.get("custom_output_path", "") == str(projects), "SANDBOX FAILED"

    record: dict = {
        "mode": "ON SCREEN",
        "tree": str(ROOT),
        "head": subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"],
                               capture_output=True, text=True, timeout=30,
                               encoding="utf-8", errors="replace"
                               ).stdout.strip(),
        "screen_locked_at_start": session_is_locked(),
        "ladder_rungs": len(cs.SLOTS),
        "tolerance": cs.SLOT_TOL,
        "steps": [],
    }

    charts = build_charts(work / "charts")

    fm = FileManager(settings)
    Project.create(projects / "Strip", "Strip").current_run().ensure_dir()
    fm.set_target_name("Strip")
    ctl = MeasurementTargetController(fm)
    tab = TabChart(ArgyllRunner(settings), fm, settings, None)
    tab.set_target_controller(ctl)

    win = QMainWindow()
    win.setWindowTitle("ChromIQ - Create Chart - the control-strip declaration")
    win.setCentralWidget(tab)
    win.resize(1500, 1000)
    win.show()
    win.raise_()
    win.activateWindow()
    pump(app, 1800)
    record["window_visible"] = bool(win.isVisible())

    # THE REAL WARNING WINDOW, SHOWN AND PHOTOGRAPHED. `.exec()` would block
    # this driver for ever, so the dialog is built exactly as the app builds
    # it and shown modelessly; the widget, its title and its text are the
    # app's own.
    import ui.tabs.tab_chart as tc
    real_info = tc.InfoDialog
    opened: "list" = []

    class _Shown:
        def __init__(self, *a, **kw):
            self.dlg = real_info(*a, **kw)
            self.dlg.show()
            self.dlg.raise_()
            opened.append(self.dlg)

        def exec(self):
            return 0

    tc.InfoDialog = _Shown                          # type: ignore[assignment]

    for label, _n in CHARTS:
        run = fm.project().current_run()
        run.ensure_dir()
        src = charts[label]
        for ext in (".ti1", ".ti2"):
            if src.with_suffix(ext).is_file():
                shutil.copyfile(src.with_suffix(ext), run.artefact(ext))
        tif = run.dir / f"{run.stem}_01.tif"
        shutil.copyfile(next(src.parent.glob("*.tif")), tif)

        tab._log.clear()
        ctl.set_run_type(RUN_TYPE_VERIFICATION)
        pump(app, 400)
        tab._on_generate_finished([tif])            # THE APP'S OWN FUNNEL
        pump(app, 1200)

        sidecar = cs.declaration_path(run.verify_chart_ti2)
        step = {
            "chart": label,
            "patches_on_the_chart": len(cs.chart_device_values(src)),
            "rungs_filled": cs.strip_for_chart(src).n,
            "declaration_written": sidecar.is_file(),
            "declaration": (json.loads(sidecar.read_text(encoding="utf-8"))
                            if sidecar.is_file() else None),
            "log": tab._log.toPlainText().strip().splitlines()[-4:],
            "warning_opened": len(opened) > 0,
        }
        if step["declaration"]:
            step["declaration"] = {
                k: step["declaration"][k]
                for k in ("name", "sample_ids", "generator", "tolerance")}
        step["photograph_tab"] = capture_settled(
            app, win, shots / f"{label}-tab-1.png", shots / f"{label}-tab-2.png")
        if opened:
            dlg = opened[-1]
            dlg.resize(620, 560)
            pump(app, 900)
            step["warning_title"] = dlg.windowTitle()
            step["warning_text"] = _dialog_text(dlg)
            step["photograph_warning"] = capture_settled(
                app, dlg, shots / f"{label}-warning-1.png",
                shots / f"{label}-warning-2.png")
            dlg.close()
            opened.clear()
        record["steps"].append(step)
        pump(app, 400)

    tc.InfoDialog = real_info                       # type: ignore[assignment]
    win.close()
    (out / "record.json").write_text(json.dumps(record, indent=2) + "\n",
                                     encoding="utf-8")
    print(json.dumps(record, indent=2))
    return 0


def _dialog_text(dlg) -> str:
    from PyQt6.QtWidgets import QLabel
    return "\n\n".join(lb.text() for lb in dlg.findChildren(QLabel) if lb.text())


if __name__ == "__main__":
    raise SystemExit(main())
