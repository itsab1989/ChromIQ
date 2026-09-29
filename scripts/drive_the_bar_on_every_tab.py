#!/usr/bin/env python3
"""What the target bar ACTUALLY does on each of the five tabs, measured.

The design authority's specification for the locked-bar tooltip makes three
claims. Two of them are about behaviour and have to be measured from the app
before a sentence is written about them, which is precisely how the wrong
tooltip got there in the first place:

  * on Build Profile the profile run is still changeable ("and is today")
  * on Build Profile only Profiling applies, Verification cannot be selected

This walks the real window through all five tabs and reads the widgets.
Sandboxed settings and presets; a real window, photographed.
"""
import os
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
PROOF = Path.home() / "Desktop/ChromIQ-beta20-proof/migration"

os.environ["CHROMIQ_SETTINGS_FILE"] = "/tmp/chromiq-mig.ini"
os.environ["CHROMIQ_PRESETS_DIR"] = "/tmp/chromiq-mig-presets"
sys.path.insert(0, str(REPO))


def main() -> int:
    from PyQt6.QtWidgets import QApplication

    import main as chromiq_main
    from core.settings import AppSettings
    from ui.styles import WinButtonLayoutStyle

    app = QApplication(sys.argv[:1])
    app.setStyle(WinButtonLayoutStyle("Fusion"))
    sys.excepthook = chromiq_main._log_excepthook

    work = Path("/tmp/chromiq-mig-drive/projects")
    work.mkdir(parents=True, exist_ok=True)
    s = AppSettings()
    s.set("custom_output_path", str(work))

    from core.file_manager import Project
    root = work / "Bar-State-Probe"
    if not (root / "project.json").exists():
        proj = Project.create(root, "Bar-State-Probe")
        for ext in (".ti1", ".ti2", ".ti3", ".icc"):
            (proj.current_run().dir / f"Bar-State-Probe{ext}").write_text("x", encoding="utf-8")

    from ui.main_window import MainWindow
    win = MainWindow(s)
    win.resize(1500, 1000)
    win.show()
    win._file_mgr.open_project_at(root)
    win._file_mgr.project()
    win._target_ctl.changed.emit()
    for _ in range(40):
        app.processEvents(); time.sleep(0.02)

    bar = win._target_bar
    lines = ["# The target bar on each tab, measured from the running window",
             "",
             "| tab | Profile run | Run type | Verification selectable |",
             "|---|---|---|---|"]
    for i in range(win._tabs.count()):
        win._tabs.setCurrentIndex(i)
        for _ in range(20):
            app.processEvents(); time.sleep(0.01)
        model = bar._type_combo.model()
        verif = None
        from ui.measurement_target_bar import RUN_TYPE_VERIFICATION
        for j in range(bar._type_combo.count()):
            if bar._type_combo.itemData(j) == RUN_TYPE_VERIFICATION:
                item = model.item(j)
                verif = bool(item.isEnabled()) if item is not None else None
        lines.append(
            f"| {win._tabs.tabText(i)} | "
            f"{'enabled' if bar._run_combo.isEnabled() else 'GREYED'} | "
            f"{'enabled' if bar._type_combo.isEnabled() else 'GREYED'} | "
            f"{verif} |")

    # the tooltip as the user reads it, on the tab that greys the bar
    win._tabs.setCurrentIndex(4)
    for _ in range(20):
        app.processEvents(); time.sleep(0.01)
    lines += ["", "## The tooltip on the greyed Profile run box (tab 5)", "",
              "    " + bar._run_combo.toolTip().replace("\n", "\n    ")]

    sys.path.insert(0, str(REPO / "scripts"))
    from onscreen_capture import capture_window
    shot = PROOF / "bar-state-check-refine.png"
    ok, why = capture_window(win, shot)
    lines += ["", f"photograph: {ok}" + ("" if ok else f" REFUSED: {why}")]

    win._tabs.setCurrentIndex(3)
    for _ in range(25):
        app.processEvents(); time.sleep(0.02)
    shot2 = PROOF / "bar-state-build-profile.png"
    ok2, why2 = capture_window(win, shot2)
    lines += [f"photograph (Build Profile): {ok2}"
              + ("" if ok2 else f" REFUSED: {why2}")]

    win.close(); app.processEvents()
    text = "\n".join(lines)
    PROOF.mkdir(parents=True, exist_ok=True)
    (PROOF / "bar-state.md").write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0 if (ok and ok2) else 2


if __name__ == "__main__":
    raise SystemExit(main())
