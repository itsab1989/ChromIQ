#!/usr/bin/env python3
"""Drive features A + B in the real widgets, end to end, with real Argyll.

Built for the night before the first real print (Basti, 2026-08-09): clear
everything that does not need paper. It stages a COPY of the user's
``~/ChromIQ/printer-test`` project (the original is never touched), then:

  1. selects Run type = Verification and opens FROM PROFILE GAMUT,
  2. generates a small gamut chart — real xicclu selection through the run's
     real profile, real printtarg/engine layout, adoption into
     ``verifications/``, the colorimetric reference and sidecar marker,
  3. checks the Print tab forces "Raw — already converted" for it,
  4. fabricates a measurement with Argyll ``fakeread`` (never by hand) and
     files it as a dated verification,
  5. builds the measurement report and checks it judges against the
     colorimetric reference, names set version + coverage, and keeps the
     corners out of the accuracy statistics.

Run on screen (real styling; the window appears and drives itself):

    .venv/bin/python scripts/drive_feature_b_onscreen.py

or headless with QT_QPA_PLATFORM=offscreen — the checks are identical.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from PyQt6.QtCore import QSettings                          # noqa: E402
from PyQt6.QtGui import QFontDatabase                       # noqa: E402
from PyQt6.QtWidgets import QApplication                    # noqa: E402

from core.resource_path import resource_path                # noqa: E402

FAILURES: list[str] = []
ARGYLL = Path("/Applications/Argyll/bin")


def check(what: str, ok: bool, detail: str = "") -> None:
    print(f"  {'OK  ' if ok else 'FAIL'} {what}" + (f"  ({detail})" if detail else ""))
    if not ok:
        FAILURES.append(what)


def pump(app, ms: int = 200) -> None:
    end = time.time() + ms / 1000.0
    while time.time() < end:
        app.processEvents()
        time.sleep(0.01)


def wait_until(app, cond, timeout_s: float = 180.0) -> bool:
    end = time.time() + timeout_s
    while time.time() < end:
        if cond():
            return True
        app.processEvents()
        time.sleep(0.05)
    return False


def main() -> int:
    if not (ARGYLL / "printtarg").exists():
        print("ArgyllCMS is required.")
        return 2
    src_project = Path.home() / "ChromIQ" / "printer-test"
    if not (src_project / "runs" / "run1" / "printer-test.icc").exists():
        print("~/ChromIQ/printer-test with a built profile is required.")
        return 2

    app = QApplication.instance() or QApplication(sys.argv)
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

    # ---- staging: a COPY of the real project, in a sandbox working folder
    sandbox = Path(tempfile.mkdtemp(prefix="chromiq_feature_b_drive_"))
    work = sandbox / "working"
    work.mkdir()
    shutil.copytree(src_project, work / "printer-test")
    print(f"staged copy: {work / 'printer-test'}")

    from core.argyll_runner import ArgyllRunner
    from core.file_manager import FileManager
    from core.measurement_target import RUN_TYPE_VERIFICATION, resolve_run
    from core.settings import AppSettings
    from ui.measurement_target_bar import MeasurementTargetController
    from ui.tabs.tab_chart import TabChart
    from ui.tabs.tab_print import TabPrint

    settings = AppSettings()
    settings._qs = QSettings(str(sandbox / "drive.ini"), QSettings.Format.IniFormat)
    settings.set("custom_output_path", str(work))
    settings.set("argyll_bin_path", str(ARGYLL))
    settings.set("use_native_print_dialog", False)
    fm = FileManager(settings)
    fm.set_target_name("printer-test")
    ctl = MeasurementTargetController(fm)
    runner = ArgyllRunner(settings)

    chart_tab = TabChart(runner, fm, settings, None)
    chart_tab.set_target_controller(ctl)
    chart_tab.resize(1500, 1100)
    chart_tab.show()
    pump(app, 400)

    ctl.set_profile_run("run1")
    ctl.set_run_type(RUN_TYPE_VERIFICATION)
    pump(app)

    print("\n-- FROM PROFILE GAMUT --")
    check("module button visible for a verification",
          chart_tab._gamut_btn.isVisible())
    chart_tab._switch_mode("gamut")
    pump(app, 300)
    check("options shown (run has a profile)",
          chart_tab._gamut_grp.isVisible())
    chart_tab._gamut_count_spin.setValue(60)
    pump(app, 300)
    line = chart_tab._gamut_count_lbl.text()
    check("live line names coverage + corners",
          "reference colours" in line and "8 cube corners" in line, line[:90])

    # Generate — the §4 replace-question is auto-accepted for the drive.
    from PyQt6.QtWidgets import QMessageBox
    import unittest.mock as _mock
    run = resolve_run(fm.project(), ctl.target)
    with _mock.patch.object(chart_tab, "_confirm_displacing_results",
                            return_value=True):
        chart_tab._on_generate()
        done = wait_until(app, lambda: run.has_verify_chart()
                          and chart_tab._generate_btn.isEnabled())
    check("gamut chart generated and adopted as the verify chart", done)
    ti2 = run.verify_chart_ti2
    from workflow.verification_print import (STATE_CONVERTED,
                                             chart_conversion_state,
                                             colorimetric_reference_for)
    ref = colorimetric_reference_for(ti2)
    check("colorimetric reference beside the chart", ref.exists())
    sidecar = json.loads(run.verify_chart_channels_json.read_text(encoding="utf-8"))
    check("channels.json carries the marker",
          sidecar.get("colorimetric_reference") == ref.name)
    check("chart reads as already-converted",
          chart_conversion_state(ti2) == STATE_CONVERTED)
    from workflow.gamut_target import read_colorimetric_reference
    cref = read_colorimetric_reference(ref)
    check("reference: 60 colours + 8 corners",
          cref is not None and len(cref["labs"]) == 68
          and len(cref["corner_ids"]) == 8)

    print("\n-- Print tab forces Raw (§3.1a) --")
    print_tab = TabPrint(settings)
    print_tab.set_target_controller(ctl)
    print_tab._current_ti2 = ti2
    print_tab.load_tiffs(run.verify_chart_tiffs())
    print_tab.show()
    pump(app, 300)
    check("'Through the profile' is DISABLED",
          not print_tab._cm_through_rb.isEnabled())
    check("Raw is selected", print_tab._cm_raw_rb.isChecked())
    check("the print would go raw",
          print_tab._cm_selected_colour() == "raw")

    print("\n-- fakeread → dated verification → report --")
    v = run.new_verification()
    v.ensure_dir()
    ti3 = v.measurement_ti3
    r = subprocess.run(
        [str(ARGYLL / "fakeread"), str(run.built_profile_icc()),
         str(ti2.with_suffix(""))],
        cwd=str(ti2.parent), capture_output=True, text=True, timeout=120)
    made = ti2.with_suffix(".ti3")
    check("fakeread produced a measurement",
          r.returncode == 0 and made.exists(),
          (r.stderr or r.stdout).strip()[:80])
    if made.exists():
        shutil.move(str(made), str(ti3))
    from workflow.measurement_report import build_report
    rep = build_report(ti3)
    check("report judges against the colorimetric reference",
          rep.get("reference_source") == "colorimetric",
          str(rep.get("reference_source")))
    cm = rep.get("colorimetric") or {}
    check("report names set version + coverage",
          cm.get("set_version") == "PROVISIONAL-r1" and bool(cm.get("in_gamut")))
    de = rep.get("de00") or {}
    check("accuracy over the 60 colours, corners excluded",
          de.get("n") == 60, f"n={de.get('n')}")
    check("fakeread round-trip ΔE is small (sanity)",
          de.get("mean", 99) < 3.0, f"mean={de.get('mean')}")
    corners = rep.get("corners") or []
    check("corner section present with expected colours",
          len(corners) == 8 and all("de" in c for c in corners))

    print()
    print(f"sandbox kept for inspection: {sandbox}")
    if FAILURES:
        print(f"{len(FAILURES)} check(s) FAILED")
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
