#!/usr/bin/env python3
"""ON SCREEN: a note and a photograph left in `cal/` survive Generate Chart.

The F1 fault of the second critical review, driven through the REAL app with
the REAL Argyll: build a calibration chart, leave two of the person's own files
beside it in `cal/`, press Generate Chart again, answer the window that appears,
and look at what is on disk afterwards.

    CHROMIQ_DRIVE_ONSCREEN=1 python scripts/drive_cal_keeps_the_persons_files.py

Everything it touches lives in a temporary folder, never in ``~/ChromIQ``.
"""
from __future__ import annotations

import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

ONSCREEN = bool(os.environ.get("CHROMIQ_DRIVE_ONSCREEN"))
if not ONSCREEN:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    import PyQt6.QtWebEngineWidgets  # noqa: F401  (before QApplication)
except ImportError:
    pass

from PyQt6.QtCore import QTimer                             # noqa: E402
from PyQt6.QtGui import QFontDatabase                       # noqa: E402
from PyQt6.QtWidgets import (QApplication, QMessageBox,     # noqa: E402
                             QPushButton)

from core.measurement_target import RUN_TYPE_CALIBRATION    # noqa: E402
from core.resource_path import resource_path                # noqa: E402

RESULTS: "list[tuple[str, bool, str]]" = []
SHOTS = Path(os.environ.get("R4_SHOTS", tempfile.gettempdir()))


def check(name: str, ok: bool, detail: str = "") -> None:
    RESULTS.append((name, bool(ok), detail))
    print(f"  {'PASS' if ok else 'FAIL'}  {name}"
          + (f"   — {detail}" if detail else ""), flush=True)


def pump(app, ms: int = 250) -> None:
    end = time.time() + ms / 1000.0
    while time.time() < end:
        app.processEvents()
        time.sleep(0.01)


def wait_for(app, cond, timeout=240.0, label=""):
    end = time.time() + timeout
    while time.time() < end:
        app.processEvents()
        time.sleep(0.02)
        try:
            if cond():
                return True
        except Exception:      # noqa: BLE001
            pass
    print(f"  (timed out waiting for {label})", flush=True)
    return False


def build_app():
    app = QApplication(sys.argv)
    app.setApplicationName("ChromIQ")
    for fp in resource_path("assets/fonts").glob("*.ttf"):
        QFontDatabase.addApplicationFont(str(fp))
    from ui.styles import WinButtonLayoutStyle
    from ui.widgets import ButtonFontFilter, GroupBoxSurfaceFilter
    app.setStyle(WinButtonLayoutStyle("Fusion"))
    app.installEventFilter(ButtonFontFilter(app))
    app.installEventFilter(GroupBoxSurfaceFilter(app))
    return app


def answer_the_window(app, win, shot_name):
    """Screenshot the modal ChromIQ puts up, then click its accept button.

    Only ever touches a modal whose window is OUR MainWindow, so a second
    ChromIQ running beside this one is never clicked by us.
    """
    grabbed = {"text": "", "buttons": []}

    def _tick():
        box = app.activeModalWidget()
        if not isinstance(box, QMessageBox) or box.window() is box.parent():
            pass
        if not isinstance(box, QMessageBox):
            return
        if box.parentWidget() is not None and box.parentWidget().window() is not win:
            return
        grabbed["text"] = (box.text() + "\n\n" + box.informativeText()).strip()
        grabbed["buttons"] = [b.text() for b in box.findChildren(QPushButton)]
        try:
            box.grab().save(str(SHOTS / shot_name))
        except Exception:      # noqa: BLE001
            pass
        for b in box.buttons():
            if box.buttonRole(b) == QMessageBox.ButtonRole.AcceptRole:
                timer.stop()
                b.click()
                return

    timer = QTimer()
    timer.timeout.connect(_tick)
    timer.start(120)
    return grabbed, timer


def main() -> int:
    SHOTS.mkdir(parents=True, exist_ok=True)
    app = build_app()
    home = Path(tempfile.mkdtemp(prefix="chromiq_r4_cal_"))
    try:
        from core.settings import AppSettings
        from ui.main_window import MainWindow

        settings = AppSettings()
        settings.set("custom_output_path", str(home))
        settings.set("calibration_mode", True)

        win = MainWindow(settings)
        if ONSCREEN:
            win.show()
        pump(app, 800)

        ctl = win._target_ctl
        chart = win._tab_chart

        win._file_mgr.set_target_name("R4-Cal-Keeps-My-Files")
        proj = win._file_mgr.project()
        cal = proj.calibration
        win._apply_calibration_mode()
        win._target_bar.refresh()
        pump(app, 300)
        ctl.set_run_type(RUN_TYPE_CALIBRATION)
        pump(app, 500)
        check("Run type is Calibration",
              ctl.target.run_type == RUN_TYPE_CALIBRATION, ctl.target.run_type)

        # ---- build the first calibration chart, for real -----------------
        print("\n=== Generate Chart (1st) — real targen + printtarg ===",
              flush=True)
        chart._generate_btn.click()
        ok = wait_for(app, lambda: cal.ti2.exists() and cal.chart_tiffs()
                      and not win._runner.is_running,
                      label="the first calibration chart")
        pump(app, 800)
        first = sorted(p.name for p in cal.dir.iterdir() if p.is_file())
        check("a calibration chart was really built", bool(ok), str(first))
        if not ok:
            raise SystemExit("no chart to work with")
        first_ti2 = cal.ti2.read_bytes()

        # ---- the person leaves two of their own things beside it ---------
        note = cal.dir / "notes about this calibration.txt"
        note.write_text("Hahnemuehle Photo Rag, second box, paper still damp.\n",
                        encoding="utf-8")
        photo = cal.dir / "IMG_4821.jpg"
        photo.write_bytes(b"\xff\xd8\xff\xe0" + b"a photo of the printed sheet")
        mine = cal.dir / "my measurements"
        mine.mkdir(exist_ok=True)
        (mine / "run-a.ti3").write_text("x", encoding="utf-8")
        print("\n=== the person's own things are now in cal/ ===", flush=True)
        print("   ", sorted(p.name for p in cal.dir.iterdir()), flush=True)

        check("the calibration is NOT measured (so the drop branch applies)",
              not cal.ti3.exists() and not cal.cal_path.exists())

        # ---- Generate Chart again ----------------------------------------
        print("\n=== Generate Chart (2nd) — the window, then the rebuild ===",
              flush=True)
        grabbed, timer = answer_the_window(app, win, "R4-cal-replace-window.png")
        chart._generate_btn.click()
        ok2 = wait_for(app, lambda: cal.ti2.exists()
                       and cal.ti2.read_bytes() != first_ti2
                       and not win._runner.is_running,
                       label="the replacement chart")
        timer.stop()
        pump(app, 800)

        check("the window that appeared is M-CAL-REPLACE-CHART",
              "not been measured yet" in grabbed["text"]
              and "is not kept" in grabbed["text"],
              (grabbed["text"][:90] + "…") if grabbed["text"] else "no window seen")
        check("its words talk about THE CHART and nothing else",
              "chart you have now is not kept" in grabbed["text"],
              "")

        after = sorted(p.name for p in cal.dir.iterdir())
        print("\n=== cal/ after the rebuild ===", flush=True)
        print("   ", after, flush=True)

        check("a NEW chart really replaced the old one", bool(ok2))
        check("the person's note is still there", note.is_file(),
              note.read_text(encoding="utf-8").strip() if note.is_file() else "GONE")
        check("the person's photograph is still there", photo.is_file(),
              "" if photo.is_file() else "GONE")
        check("the person's folder is still there", mine.is_dir())
        check("no dated archive was made for an unmeasured chart",
              not cal.old_dir.exists())
        check("nothing was left in a stash", cal.chart_stash_dirs() == [])

        if ONSCREEN:
            win.grab().save(str(SHOTS / "R4-cal-after-rebuild.png"))
        print(f"\nshots in {SHOTS}", flush=True)
    finally:
        shutil.rmtree(home, ignore_errors=True)

    print("\n" + "=" * 66, flush=True)
    bad = [n for n, ok, _ in RESULTS if not ok]
    for name, ok, detail in RESULTS:
        print(f"  {'PASS' if ok else 'FAIL'}  {name}", flush=True)
    print(f"{len(RESULTS) - len(bad)}/{len(RESULTS)} passed", flush=True)
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
