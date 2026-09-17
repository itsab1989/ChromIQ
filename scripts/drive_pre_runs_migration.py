#!/usr/bin/env python3
"""Drive the REAL ChromIQ window over a tester's pre-redesign project.

Opens a window (never offscreen), loads a copy of one of the three projects a
tester reported as "not migrated", and records the folder listing before and
after, plus a photograph of the window taken with
`scripts/onscreen_capture.py::capture_window`.

The settings and presets stores are sandboxed BEFORE `core` is imported, and
`custom_output_path` is pinned to this run's own temp folder, so the real
preferences cannot be reached at all.
"""
import os
import shutil
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
RUN_ROOT = Path("/tmp/chromiq-mig-drive")
WORK = RUN_ROOT / "projects"
PROOF = Path.home() / "Desktop/ChromIQ-beta20-proof/migration"

# ---- SANDBOX FIRST, before anything imports core.settings ------------------
os.environ["CHROMIQ_SETTINGS_FILE"] = "/tmp/chromiq-mig.ini"
os.environ["CHROMIQ_PRESETS_DIR"] = "/tmp/chromiq-mig-presets"
sys.path.insert(0, str(REPO))

SOURCES = {
    "A_no_manifest": Path("/tmp/mig-work/originals/A-1168-Old/Printer_HP_CLJ5550-PostScript-Plain90g-White-sRGB-1168Patches-Calib-Argyll-Colormunki_2026.02.09"),
    "B_manifest_flat": Path("/tmp/mig-work/originals/B-900/Printer_HP_CLJ5550-PostScript-Plain90g-White-sRGB-900Patches-Calib-Argyll-Colormunki_2026.02.09"),
}


def listing(root: Path) -> list[str]:
    return sorted(("DIR  " if p.is_dir() else "FILE ") + str(p.relative_to(root))
                  for p in root.rglob("*"))


def main() -> int:
    which = sys.argv[1] if len(sys.argv) > 1 else "A_no_manifest"
    src = SOURCES[which]
    PROOF.mkdir(parents=True, exist_ok=True)
    if RUN_ROOT.exists():
        shutil.rmtree(RUN_ROOT)
    WORK.mkdir(parents=True)
    dest = WORK / src.name
    shutil.copytree(src, dest)

    report: list[str] = [f"# {which}: {src.name}", ""]
    report.append("## On disk BEFORE the app touched it")
    report += ["    " + l for l in listing(dest)]

    from PyQt6.QtWidgets import QApplication

    import main as chromiq_main
    from core.settings import AppSettings

    app = QApplication(sys.argv[:1])
    # THE APP'S OWN STYLE, the one CLAUDE.md insists a measurement is taken in.
    from ui.styles import WinButtonLayoutStyle
    app.setStyle(WinButtonLayoutStyle("Fusion"))
    # main.py's excepthook, so a fault in the driven app is loud, not silent.
    sys.excepthook = chromiq_main._log_excepthook

    s = AppSettings()
    s.set("custom_output_path", str(WORK))
    assert "chromiq-mig" in str(s.get("custom_output_path", "")), "sandbox failed"

    from ui.main_window import MainWindow
    win = MainWindow(s)
    win.resize(1500, 1000)
    win.show()
    for _ in range(40):
        app.processEvents()
        time.sleep(0.02)

    # ---- open the project exactly as a person does: name it, then use it ---
    fm = win._file_mgr
    fm.open_project_at(dest)
    proj = fm.project()                 # this is the call that loads/migrates
    win._target_ctl.changed.emit()
    win._tabs.setCurrentIndex(4)        # 5. Check & Refine
    for _ in range(60):
        app.processEvents()
        time.sleep(0.02)

    report += ["", "## On disk AFTER the app opened it"]
    report += ["    " + l for l in listing(dest)]

    run = proj.current_run()
    report += ["", "## What the app now holds",
               f"    current run        : {run.id}",
               f"    run folder exists  : {run.dir.is_dir()}",
               f"    chart  .ti2 present: {run.chart_ti2.is_file()}",
               f"    measurement .ti3   : {run.measurement_ti3.is_file()}",
               f"    profile .icc       : {run.profile_icc.is_file()}"]

    tab = win._tab_check
    report += ["", "## Check & Refine, on arrival (nothing browsed)",
               f"    Measurement field  : {tab.ti3_path}",
               f"    Profile field      : {tab.icc_path}"]

    # ---- photograph the window --------------------------------------------
    sys.path.insert(0, str(REPO / "scripts"))
    from onscreen_capture import capture_window
    shot = PROOF / f"{which}-check-refine.png"
    ok, why = capture_window(win, shot)
    report += ["", "## Photograph",
               f"    captured: {ok}" + ("" if ok else f"  --  REFUSED: {why}"),
               f"    file    : {shot if ok else '(none kept)'}"]

    win.close()
    app.processEvents()

    text = "\n".join(report)
    (PROOF / f"{which}.md").write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
