#!/usr/bin/env python3
"""Drive the REAL app through the #137 calibration Run type and check each step.

Headless tests miss sequencing faults, and the bar is shared by three tabs —
which is exactly where #130's bugs lived. So this launches the real
``MainWindow`` with the real fonts, theme and event loop, drives it the way a
person would, and compares what the window actually shows against what the
design promises.

    CHROMIQ_DRIVE_ONSCREEN=1 python scripts/drive_calibration_run_type.py

Every project it touches lives in a temporary folder, never in ``~/ChromIQ``.
One failure never stops the walk; the run ends with a PASS/FAIL table.
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

from PyQt6.QtGui import QFontDatabase                       # noqa: E402
from PyQt6.QtWidgets import QApplication                    # noqa: E402

from core.resource_path import resource_path                # noqa: E402
from core.measurement_target import (                       # noqa: E402
    RUN_TYPE_CALIBRATION, RUN_TYPE_PROFILING, RUN_TYPE_VERIFICATION)

RESULTS: "list[tuple[str, bool, str]]" = []


def check(name: str, ok: bool, detail: str = "") -> None:
    RESULTS.append((name, bool(ok), detail))
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"   — {detail}" if detail else ""),
          flush=True)


def pump(app, ms: int = 250) -> None:
    end = time.time() + ms / 1000.0
    while time.time() < end:
        app.processEvents()
        time.sleep(0.01)


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


def main() -> int:
    app = build_app()
    home = Path(tempfile.mkdtemp(prefix="chromiq_cal_drive_"))
    try:
        from core.settings import AppSettings
        from ui.main_window import MainWindow

        settings = AppSettings()
        settings.set("custom_output_path", str(home))
        settings.set("calibration_mode", False)

        win = MainWindow(settings)
        if ONSCREEN:
            win.show()
        pump(app, 600)

        bar = win._target_bar
        ctl = win._target_ctl
        chart = win._tab_chart
        profile = win._tab_profile

        def types():
            return [bar._type_combo.itemData(i)
                    for i in range(bar._type_combo.count())]

        # ---- the preference is OFF: the app must be as it always was -----
        print("\n=== Preference OFF — nothing may change ===", flush=True)
        win._apply_calibration_mode()
        pump(app)
        check("Run type offers exactly Profiling and Verification",
              types() == [RUN_TYPE_PROFILING, RUN_TYPE_VERIFICATION], str(types()))
        check("Profile run box is live",
              bar._run_combo.isEnabled() or ctl.project_or_none() is None)
        ctl.set_run_type(RUN_TYPE_CALIBRATION)
        pump(app)
        check("Calibration cannot be selected",
              ctl.target.run_type == RUN_TYPE_PROFILING, ctl.target.run_type)

        # ---- a project, and the preference ON ----------------------------
        print("\n=== Preference ON ===", flush=True)
        win._file_mgr.set_target_name("Drive-Test")
        proj = win._file_mgr.project()
        proj.new_run()
        settings.set("calibration_mode", True)
        win._apply_calibration_mode()
        bar.refresh()
        pump(app)
        check("Calibration is offered", RUN_TYPE_CALIBRATION in types(), str(types()))

        ctl.set_profile_run("run1")
        pump(app)
        ctl.set_run_type(RUN_TYPE_CALIBRATION)
        pump(app, 400)

        check("Profile run shows one fixed entry",
              bar._run_combo.count() == 1 and not bar._run_combo.isEnabled(),
              f"{bar._run_combo.count()} item(s), enabled={bar._run_combo.isEnabled()}")
        check("Profile run text is not clipped",
              bar._run_combo.width() >= bar._run_combo.fontMetrics()
              .horizontalAdvance(bar._run_combo.currentText()),
              f"{bar._run_combo.width()} px for {bar._run_combo.currentText()!r}")
        check("Verification box is hidden", not bar._verify_combo.isVisible())
        check("Duplicate is greyed with a reason",
              not bar._duplicate_btn.isEnabled() and bool(bar._duplicate_btn.toolTip()))
        check("Delete is greyed with a reason",
              not bar._delete_btn.isEnabled() and bool(bar._delete_btn.toolTip()))
        check("Restore stays visible", bar._restore_btn.isVisible())

        # ---- Create Chart ------------------------------------------------
        def pw(flag, tool="targen"):
            for w in chart._manual_widgets.get(tool, []):
                if w.flag == flag:
                    return w

        autos = {n: getattr(chart, n, None) for n in chart._CAL_AUTO_CHECKS}
        check("every Auto box is off AND greyed",
              all(cb is not None and not cb.isChecked() and not cb.isEnabled()
                  for cb in autos.values()),
              str({n: (cb.isChecked(), cb.isEnabled()) for n, cb in autos.items()}))
        check("Single Channel Steps is 20", pw("-s").get_raw_value() == 20,
              str(pw("-s").get_raw_value()))
        check("Total Patch Count is 0", pw("-f").get_raw_value() == 0)
        check("Pages is greyed", not chart._manual_pages_spin.isEnabled())
        check("the greyed boxes explain themselves",
              all("Single Channel Steps" in cb.toolTip() for cb in autos.values()))
        check("the calibration checkbox is gone",
              not chart._cal_target_grp.isVisible())

        # ---- tab 4 --------------------------------------------------------
        win._tabs.setCurrentIndex(3)
        pump(app, 400)
        # isVisibleTo(parent), not isVisible(): a widget reports itself
        # invisible whenever an ancestor is, and only one tab is ever current.
        # Asking isVisible() here would test which tab is open, not what the
        # tab offers.
        def shown(btn) -> bool:
            return btn.isVisibleTo(btn.parentWidget())

        check("tab 4 offers Create Calibration File only",
              shown(profile._cal_create_btn)
              and not shown(profile._cal_profile_btn)
              and not shown(profile._cal_apply_btn))

        # ---- back to Profiling -------------------------------------------
        print("\n=== Back to Profiling ===", flush=True)
        win._tabs.setCurrentIndex(0)
        ctl.set_run_type(RUN_TYPE_PROFILING)
        pump(app, 400)
        check("the selected run survived the round trip",
              ctl.target.profile_run == "run1", ctl.target.profile_run)
        check("every Auto box is clickable again",
              all(cb.isEnabled() for cb in autos.values()))
        check("tab 4 offers Build Profile and Apply Calibration again",
              shown(profile._cal_profile_btn) and shown(profile._cal_apply_btn))

        # ---- the preference goes OFF while Calibration is selected --------
        print("\n=== Preference switched OFF while Calibration selected ===", flush=True)
        ctl.set_run_type(RUN_TYPE_CALIBRATION)
        pump(app, 300)
        settings.set("calibration_mode", False)
        win._apply_calibration_mode()
        pump(app, 400)
        check("fell back to Profiling",
              ctl.target.run_type == RUN_TYPE_PROFILING, ctl.target.run_type)
        check("the run selection is still intact",
              ctl.target.profile_run == "run1", ctl.target.profile_run)
        check("Run type is back to two values",
              types() == [RUN_TYPE_PROFILING, RUN_TYPE_VERIFICATION], str(types()))
        check("Profile run box is live again", bar._run_combo.isEnabled())

        win.close()
        pump(app, 200)
    finally:
        shutil.rmtree(home, ignore_errors=True)

    passed = sum(1 for _, ok, _ in RESULTS if ok)
    print(f"\n{passed}/{len(RESULTS)} checks behave as the design describes",
          flush=True)
    return 0 if passed == len(RESULTS) else 1


if __name__ == "__main__":
    raise SystemExit(main())
