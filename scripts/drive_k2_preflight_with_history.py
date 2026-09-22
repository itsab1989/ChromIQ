#!/usr/bin/env python3
"""Knut, #182 on beta 34 (K2): the pre-flight still opens on a run with history.

    *"The 'Before you measure this verification chart' window still occurs if
    a verification run has several dated measurements and always seem to pop
    up when entering Measure tab."*

Driven ON SCREEN on his own demo project, Report-Limits-Threshold-Series,
copied into a sandbox. Every window the app opens is shown for real,
photographed with `onscreen_capture.capture_window` and closed, through
`drive_the_verification_preflight.install_window_capture`.

The steps, and what each is expected to say:

    A  run1, eleven measured dated verifications, clicking Measure    no
    B  switching to run3 (one measured verification) while on Measure no
    C  switching to run2 (three measured verifications)               no
    D  CONTROL: run1 again with every dated .ti3 moved aside          YES

D is what makes A to C evidence. Same project, same chart, same run; the only
difference is the history, so a driver that could not see the popup at all
would fail at D rather than pass A to C.

Run once against a tree WITHOUT the fix (CHROMIQ_TREE=<worktree at the old
HEAD>) and once against the fixed tree:

    export CHROMIQ_SETTINGS_FILE=/tmp/chromiq-k2/settings.ini
    export CHROMIQ_PRESETS_DIR=/tmp/chromiq-k2/presets
    export CHROMIQ_COMPLIANCE_ISO_FILE=$PWD/data/compliance_sets/iso12647.json
    python scripts/drive_k2_preflight_with_history.py <out-dir>
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(os.environ.get("CHROMIQ_TREE")
            or Path(__file__).resolve().parents[1]).resolve()
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

DEMO_PACK = Path(os.environ.get(
    "CHROMIQ_DEMO_PACK", "/private/tmp/chromiq-k3/ChromIQ-Report-Limit-Demos"))
NAME = "Report-Limits-Threshold-Series"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    args = ap.parse_args(argv)
    assert os.environ.get("CHROMIQ_SETTINGS_FILE"), "SANDBOX THE SETTINGS FIRST"
    assert os.environ.get("CHROMIQ_PRESETS_DIR"), "SANDBOX THE PRESETS FIRST"
    assert os.environ.get("CHROMIQ_COMPLIANCE_ISO_FILE"), "FORCE THE ISO FILE"
    assert not os.environ.get("QT_QPA_PLATFORM"), "this DRIVER opens a window"

    import drive_the_verification_preflight as D
    out = Path(args.out).resolve()
    shots = out / "photographs"
    shots.mkdir(parents=True, exist_ok=True)
    D._state["shots_dir"] = shots

    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("ChromIQ")
    D._state["app"] = app
    from ui.styles import WinButtonLayoutStyle
    app.setStyle(WinButtonLayoutStyle("Fusion"))

    from core.settings import AppSettings
    settings = AppSettings()
    work = out / "projects"
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    shutil.copytree(DEMO_PACK / NAME, work / NAME)
    settings.set("custom_output_path", str(work))
    settings.set("argyll_bin_path", "/Applications/Argyll/bin")
    settings.set("language", "en")
    assert settings.get("custom_output_path", "") == str(work), "SANDBOX FAILED"

    record: dict = {
        "mode": "ON SCREEN", "tree": str(ROOT),
        "head": subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"],
                               capture_output=True, text=True, timeout=30
                               ).stdout.strip(),
        "dirty": subprocess.run(["git", "-C", str(ROOT), "status", "--short",
                                 "ui/tabs/tab_measure.py"],
                                capture_output=True, text=True, timeout=30
                                ).stdout.strip(),
        "steps": [],
    }

    from core.measurement_target import RUN_TYPE_VERIFICATION
    from ui.main_window import MainWindow
    win = MainWindow(settings)
    win.resize(1500, 1000)
    win.show()
    win.raise_()
    D.pump(app, 2500)
    record["window_on_screen"] = bool(win.isVisible())
    D.install_window_capture(app)

    tab_measure, tab_chart = win._tab_measure, win._tab_chart
    ctl = tab_measure._target_ctl
    win._file_mgr.set_target_name(NAME)
    D.pump(app, 900)

    def goto(tab):
        win._tabs.setCurrentWidget(tab)

    def step(label, shot, body, expect):
        before = len(D._state["seen"])
        D._state["shot"] = shot
        body()
        D.pump(app, 1800)
        seen = D._state["seen"][before:]
        fired = D.PREFLIGHT_TITLE in seen
        D._state["shot"] = None
        if not fired:
            D.capture_settled(win, shot)
        rec = {"step": label, "pre_flight_appeared": fired, "expected": expect,
               "as_expected": fired == expect, "windows_seen": seen,
               "profile_run": ctl.target.profile_run,
               "verification_id": getattr(ctl.target, "verification_id", None),
               "shot": shot}
        record["steps"].append(rec)
        print(f"  {label}: pre-flight={'YES' if fired else 'no'} "
              f"(expected {'YES' if expect else 'no'}) {seen}", flush=True)

    goto(tab_chart)
    ctl.set_run_type(RUN_TYPE_VERIFICATION)
    ctl.set_profile_run("run1")
    D.pump(app, 1400)
    step("A run1 (11 measured dated verifications), clicking Measure",
         "A-run1-clicking-measure", lambda: goto(tab_measure), False)
    step("B switching to run3 (1 measured verification) while on Measure",
         "B-run3-switch", lambda: ctl.set_profile_run("run3"), False)
    step("C switching to run2 (3 measured verifications) while on Measure",
         "C-run2-switch", lambda: ctl.set_profile_run("run2"), False)

    # D: the CONTROL. Move run1's history aside, nothing else.
    goto(tab_chart)
    ctl.set_profile_run("run1")
    D.pump(app, 900)
    moved = []
    for ti3 in sorted((work / NAME / "runs/run1/verifications").glob("*/*.ti3")):
        ti3.rename(ti3.with_suffix(".ti3-aside"))
        moved.append(ti3.parent.name)
    record["control_moved_aside"] = moved
    tab_measure._preflight_silenced.clear()
    step("D CONTROL: run1 with every dated .ti3 moved aside, clicking Measure",
         "D-control-no-history", lambda: goto(tab_measure), True)

    record["all_as_expected"] = all(s["as_expected"] for s in record["steps"])
    (out / "driver-report.json").write_text(json.dumps(record, indent=2),
                                            encoding="utf-8")
    print("ALL AS EXPECTED" if record["all_as_expected"] else "NOT AS EXPECTED")
    win.close()
    D.pump(app, 500)
    return 0 if record["all_as_expected"] else 1


if __name__ == "__main__":
    sys.exit(main())
