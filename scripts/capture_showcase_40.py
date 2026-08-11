#!/usr/bin/env python3
"""Capture the ChromIQ 4.0 showcase screenshots — the NEW features, from the
real running app, version shown as plain 4.0.0 (no beta suffix).

For the forum announcements Knut suggested (dpreview / PrinterKnowledge):
stages a COPY of the real ``~/ChromIQ/printer-test`` hardware project (real
charts, real ColorMunki measurements, real profile — the original is never
touched), opens it the way the app itself does, and grabs:

  01  the run bar steering a verification run (full Measure tab, IMPORT)
  02  Create Chart's FROM PROFILE GAMUT module
  03  Print Chart's Colour row — printing THROUGH the profile
  04  the Measurement Report window with the real dated history
  05  the "How was this sheet printed?" question
  06  the Dictionary's "Which verification should I use?" entry
  07  run-bar close-up (cropped from 01)

Run ON-SCREEN:  .venv/bin/python scripts/capture_showcase_40.py [outdir]
Default outdir: ~/Desktop/ChromIQ-4.0-showcase/screenshots
"""
from __future__ import annotations

import shutil
import sys
import time
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from PyQt6.QtCore import QSettings, QTimer                 # noqa: E402
from PyQt6.QtGui import QFontDatabase                      # noqa: E402
from PyQt6.QtWidgets import QApplication, QLabel, QMessageBox, QScrollArea  # noqa: E402

from core.resource_path import resource_path               # noqa: E402

SRC = Path.home() / "ChromIQ" / "printer-test"
STAGING = Path.home() / "ChromIQ-showcase"
OUT_DEFAULT = Path.home() / "Desktop" / "ChromIQ-4.0-showcase" / "screenshots"


def log(m):
    print(f"[showcase] {m}", flush=True)


def pump(app, ms=300):
    end = time.time() + ms / 1000.0
    while time.time() < end:
        app.processEvents()
        time.sleep(0.01)


def save(widget, out: Path, name: str) -> None:
    out.mkdir(parents=True, exist_ok=True)
    ok = widget.grab().save(str(out / f"{name}.png"))
    log(f"{'saved' if ok else '!! FAILED'} {name}.png")


def main() -> int:
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else OUT_DEFAULT
    if not (SRC / "runs/run1/printer-test.icc").exists():
        log("ERROR: ~/ChromIQ/printer-test with a built profile is required")
        return 2

    app = QApplication(sys.argv)
    app.setApplicationName("ChromIQ")
    try:
        for fp in Path(resource_path("assets/fonts")).glob("*.ttf"):
            QFontDatabase.addApplicationFont(str(fp))
    except Exception:      # noqa: BLE001
        pass
    from ui import styles
    app.setStyle(styles.WinButtonLayoutStyle("Fusion"))
    app.setPalette(styles.make_dark_palette())
    app.setStyleSheet(styles.APP_STYLESHEET)

    # Stable-release look: the masthead prints APP_VERSION at construction.
    import core.version as _ver
    _ver.APP_VERSION = _ver.APP_VERSION.split("-")[0]

    # Stage a copy — the real project is never written to.
    if STAGING.exists():
        shutil.rmtree(STAGING)
    STAGING.mkdir(parents=True)
    shutil.copytree(SRC, STAGING / SRC.name)
    log(f"staged copy at {STAGING / SRC.name}")

    from core.settings import AppSettings
    settings = AppSettings()
    settings._qs = QSettings(str(STAGING / "showcase.ini"),
                             QSettings.Format.IniFormat)
    settings.set("custom_output_path", str(STAGING))
    settings.set("argyll_bin_path", "/Applications/Argyll/bin")
    settings.set("appearance", "dark")
    settings.set("show_welcome_dialog", False)
    # The pace warning is the point of shot 09 — show it armed.
    settings.set("pace_hint_enabled", True)
    settings.set("session_target_name", SRC.name)
    settings.set("session_project_root", "")

    # The staged chart TIFF carries the version stamp it was made under —
    # a "3.14.8-beta.N" micro-text in the preview. Re-render the same chart
    # from its own recorded recipe (channels.json), now under 4.0.0: same
    # layout, honest pages, stable stamp.
    try:
        from workflow.layout_engine import chart as le_chart
        from workflow.layout_engine.presets import LayoutRecipe
        vroot = STAGING / SRC.name / "runs/run1/verifications"
        stem = vroot / "printer-test-verify"
        rec = LayoutRecipe.from_channels_json(
            stem.with_suffix(".channels.json"))
        if rec is not None:
            for leftover in vroot.glob("printer-test-verify*.tif"):
                leftover.unlink()
            le_chart.build_from_recipe(stem.with_suffix(".ti1"), stem, rec)
            log("verify chart re-rendered under 4.0.0")
    except Exception as e:      # noqa: BLE001
        log(f"chart re-render skipped ({e}) — preview keeps the old stamp")

    from ui.main_window import MainWindow
    win = MainWindow(settings)
    win.showFullScreen()
    pump(app, 900)
    try:
        win._restore_last_session()
    except Exception as e:      # noqa: BLE001
        log(f"open project: {e}")
    pump(app, 1200)

    from core.measurement_target import RUN_TYPE_VERIFICATION
    bar = win._target_bar
    ctl = win._target_ctl
    try:
        ctl.set_profile_run("run1")
        ctl.set_run_type(RUN_TYPE_VERIFICATION)
    except Exception as e:      # noqa: BLE001
        log(f"bar: {e}")
    pump(app, 800)

    # 01 — Measure tab, verification run, IMPORT module
    win._tabs.setCurrentWidget(win._tab_measure)
    try:
        win._tab_measure._import_btn.click()
    except Exception as e:      # noqa: BLE001
        log(f"import module: {e}")
    pump(app, 900)
    save(win, out, "01-run-bar-verification-and-import-module")

    # 07 — bar close-up from the same state
    pix = win.grab()
    try:
        from PyQt6.QtCore import QPoint
        dpr = pix.devicePixelRatio()
        top = bar.mapTo(win, QPoint(0, 0))
        y = int(max(0, (top.y() - 12) * dpr))
        h = int((bar.height() + 24) * dpr)
        crop = pix.copy(0, y, pix.width(), h)
        out.mkdir(parents=True, exist_ok=True)
        crop.save(str(out / "07-run-bar-closeup.png"))
        log("saved 07-run-bar-closeup.png")
    except Exception as e:      # noqa: BLE001
        log(f"bar crop: {e}")

    # 02 — Create Chart, FROM PROFILE GAMUT
    try:
        win._tab_chart._switch_mode("gamut")
    except Exception as e:      # noqa: BLE001
        log(f"gamut mode: {e}")
    win._tabs.setCurrentWidget(win._tab_chart)
    pump(app, 1200)
    save(win, out, "02-create-chart-from-profile-gamut")

    # 03 — Print Chart, the Colour row
    win._tabs.setCurrentWidget(win._tab_print)
    pump(app, 1200)
    save(win, out, "03-print-chart-colour-row-through-profile")

    # 04 — the Measurement Report window on the real history
    v1 = (STAGING / SRC.name / "runs/run1/verifications")
    first = sorted(d for d in v1.iterdir()
                   if d.is_dir() and d.name[:4].isdigit())[0]
    ti3 = first / "printer-test-verify.ti3"
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    dlg = MeasurementReportDialog(settings, None, initial_ti3=ti3)
    dlg.show()
    pump(app, 1500)
    save(dlg, out, "04-measurement-report-history-and-trends")
    dlg.close()
    pump(app, 200)

    # 05 — the "How was this sheet printed?" window (on a disposable copy
    # with its records removed, so the real question genuinely fires)
    probe = STAGING / "probe"
    shutil.copytree(first, probe)
    for rec in probe.rglob("*.print.json"):
        rec.unlink()
    box_holder = {}

    def snap_modal():
        w = app.activeModalWidget()
        if isinstance(w, QMessageBox):
            save(w, out, "05-how-was-this-sheet-printed")
            box_holder["done"] = True
            w.reject()
        elif "done" not in box_holder:
            QTimer.singleShot(150, snap_modal)

    QTimer.singleShot(600, snap_modal)
    try:
        win._tab_measure._ask_how_printed(probe / "printer-test-verify.ti3")
    except Exception as e:      # noqa: BLE001
        log(f"how-printed: {e}")
    pump(app, 1200)

    # 06 — the Dictionary entry
    from ui.dialogs import welcome_dialog as wd
    wdlg = wd.WelcomeDialog(settings)
    wdlg.show()
    pump(app, 500)
    wdlg._on_card_clicked("glossary")
    pump(app, 500)
    try:
        target = next(l for l in wdlg.findChildren(QLabel)
                      if l.isVisible()
                      and "Which verification should I use" in l.text())
        sa, par = None, target.parentWidget()
        while par is not None:
            if isinstance(par, QScrollArea):
                sa = par
                break
            par = par.parentWidget()
        if sa is not None:
            sa.ensureWidgetVisible(target, 0, 250)
        pump(app, 400)
    except StopIteration:
        log("dictionary entry not found")
    save(wdlg, out, "06-dictionary-which-verification-should-i-use")
    wdlg.close()

    # 08/09 — Preferences: Sounds, and the too-fast reading warning
    try:
        from ui.dialogs.settings_dialog import SettingsDialog
        sdlg = SettingsDialog(settings, None)
        sdlg.show()
        pump(app, 800)
        for tab_label, shot in ((("Sounds",), "08-preferences-sounds"),
                                (("Measurement",),
                                 "09-preferences-too-fast-warning")):
            for i in range(sdlg._tabs.count()):
                if sdlg._tabs.tabText(i) in tab_label:
                    sdlg._tabs.setCurrentIndex(i)
                    break
            pump(app, 600)
            save(sdlg, out, shot)
        sdlg.close()
    except Exception as e:      # noqa: BLE001
        log(f"preferences shots: {e}")

    win.close()
    shutil.rmtree(STAGING, ignore_errors=True)
    log(f"done — screenshots in {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
