#!/usr/bin/env python3
"""P2, the likeliest state she was in: the RIGHT profile, in the WRONG run.

"Through the profile" reads ``run.built_profile_icc().exists()`` for the run the
target bar's **Profile run** selector points at, not "does this project have a
profile anywhere". A project with run1 (profiled) and run2 (not yet) therefore
greys the option whenever the bar is on run2 — and the notice, which is correct
for a project with no profile at all, then tells her to build one she already
has.

This drives the REAL window through both selections and records what the control
and the notice say in each.

Usage:
    export CHROMIQ_SETTINGS_FILE=/tmp/chromiq-printpath.ini
    export CHROMIQ_PRESETS_DIR=/tmp/chromiq-printpath-presets
    python proof_printpath/drive_p2_which_run_owns_the_profile.py --out DIR
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

try:
    import PyQt6.QtWebEngineWidgets  # noqa: F401
except ImportError:
    pass

from PyQt6.QtGui import QFontDatabase                             # noqa: E402
from PyQt6.QtWidgets import QApplication                          # noqa: E402

sys.path.insert(0, str(ROOT / "scripts"))                        # noqa: E402
from onscreen_capture import capture_window, session_is_locked     # noqa: E402

WORK = Path("/tmp/chromiq-printpath-p2c-work")
PROJECT = "Two-Runs"
ARGYLL = Path("/Applications/Argyll/bin")


def pump(app, ms: int = 300) -> None:
    end = time.time() + ms / 1000.0
    while time.time() < end:
        app.processEvents()
        time.sleep(0.005)


def plain(html: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", html or "")).strip()


def main() -> int:
    out = Path(sys.argv[sys.argv.index("--out") + 1]) if "--out" in sys.argv \
        else ROOT / "proof_printpath" / "onscreen"
    out.mkdir(parents=True, exist_ok=True)
    assert os.environ.get("CHROMIQ_SETTINGS_FILE"), "SANDBOX THE SETTINGS FIRST"
    assert os.environ.get("CHROMIQ_PRESETS_DIR"), "SANDBOX THE PRESETS FIRST"

    res: dict = {"screen_locked": session_is_locked(), "runs": []}
    print(f"00 screen locked: {res['screen_locked']}")

    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("ChromIQ")
    from core.resource_path import resource_path
    for fp in resource_path("assets/fonts").glob("*.ttf"):
        QFontDatabase.addApplicationFont(str(fp))

    from core.settings import AppSettings
    settings = AppSettings()
    if WORK.exists():
        shutil.rmtree(WORK)
    WORK.mkdir(parents=True)
    settings.set("custom_output_path", str(WORK))
    settings.set("argyll_bin_path", str(ARGYLL))
    settings.set("appearance", "dark")
    from ui import theme as ui_theme
    ui_theme.apply_appearance(app, None, "dark")

    from core.file_manager import Project
    from core.measurement_target import RUN_TYPE_VERIFICATION
    project = Project.create(WORK / PROJECT, PROJECT)
    run1 = project.current_run()
    run1.ensure_dir()
    run2 = project.new_run()
    run2.ensure_dir()
    print(f"00 runs: {run1.id}, {run2.id}")

    # run1 has a finished profile; run2 does not.
    srgb = ARGYLL.parent / "ref" / "sRGB.icm"
    shutil.copy(srgb, run1.profile_icc)

    stage = WORK / "_stage"
    stage.mkdir()
    shutil.copy(ROOT / "demo-projects" / "Demo-Report-Matrix" / "runs" / "run1"
                / "verifications" / "Demo-Report-Matrix-verify.ti1",
                stage / "verify.ti1")
    subprocess.run([str(ARGYLL / "printtarg"), "-iCM", "-h", "-pA4", "-t300",
                    "verify"], cwd=str(stage), capture_output=True, timeout=300)
    made = sorted(stage.glob("verify*.tif"))
    pages = {}
    for r in (run1, run2):
        r.verifications_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy(stage / "verify.ti2", r.verify_chart_ti2)
        p = r.verifications_dir / f"{r.verify_stem}_01.tif"
        shutil.copy(made[0], p)
        pages[r.id] = (r.verify_chart_ti2, p)

    from ui.main_window import MainWindow
    win = MainWindow(settings)
    win.resize(1620, 1060)
    win.show()
    pump(app, 1500)
    win._file_mgr.set_target_name(PROJECT)
    win._target_ctl.set_run_type(RUN_TYPE_VERIFICATION)
    tab = win._tab_print
    win._tabs.setCurrentWidget(tab)
    pump(app, 700)

    for r in (run1, run2):
        win._target_ctl.set_profile_run(r.id)
        pump(app, 600)
        ti2, page = pages[r.id]
        tab._current_ti2 = ti2
        tab.load_tiffs([page])
        tab._update_colour_row_visible()
        pump(app, 500)
        row = {
            "Profile run selected in the bar": r.id,
            "this run has a built profile": r.built_profile_icc().exists(),
            "the project has a profile somewhere":
                any(x.built_profile_icc().exists()
                    for x in (run1, run2)),
            "'Through the profile' enabled": bool(
                tab._cm_through_rb.isEnabled()),
            "what a print would do": tab._cm_selected_colour(),
            "the notice": plain(tab._cm_notice.text())[:420],
        }
        res["runs"].append(row)
        print(f"{r.id}: profile in this run="
              f"{row['this run has a built profile']}  through enabled="
              f"{row[chr(39) + 'Through the profile' + chr(39) + ' enabled']}")
        ok, why = capture_window(
            win, out / f"p2_profile_run_{r.id}.png")
        row["capture"] = {"ok": ok, "why_not": why}

    (out / "p2_which_run_owns_the_profile.json").write_text(
        json.dumps(res, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"wrote {out / 'p2_which_run_owns_the_profile.json'}")
    win.close()
    pump(app, 300)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
