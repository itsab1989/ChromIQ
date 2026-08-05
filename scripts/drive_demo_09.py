"""Walk Demo-09-Run-Descriptions in the REAL app, step by step.

Knut, #130 2026-08-05: *"Run all tests in the demo project test package with
on-screen control using the chromIQ app, to verify all steps and that they are
logical and all input variables that are needed are specified so a person can
perform them manually."*

So this drives the same steps the README lists, through the app's own handlers,
and checks what the app SHOWS — not what the code says it should show. The app
is set up exactly as main.py sets it up, because an unstyled window measures a
different widget (learned the hard way in beta.143).

    python scripts/drive_demo_09.py /path/to/demo-package
"""
from __future__ import annotations

import sys
import tempfile
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

PASS, FAIL = [], []


def check(step: str, got, want) -> None:
    if got == want:
        PASS.append(step)
        print(f"  OK   {step}\n         → {got!r}")
    else:
        FAIL.append(step)
        print(f"  FAIL {step}\n         got  {got!r}\n         want {want!r}")


def main() -> int:
    pkg = Path(sys.argv[1] if len(sys.argv) > 1 else "dist/demo-package")
    src = pkg / "Demo-09-Run-Descriptions"
    if not src.is_dir():
        print(f"no Demo-09 in {pkg}")
        return 2

    work = Path(tempfile.mkdtemp())
    shutil.copytree(src, work / src.name)

    try:
        import PyQt6.QtWebEngineWidgets  # noqa: F401
    except ImportError:
        pass
    from PyQt6.QtGui import QFontDatabase
    from PyQt6.QtWidgets import QApplication

    from core.freetype_bootstrap import ensure_freetype_library
    ensure_freetype_library()
    app = QApplication(sys.argv[:1])
    app.setApplicationName("ChromIQ")
    app.setOrganizationName("ChromIQ")

    from core.resource_path import resource_path
    from ui.styles import WinButtonLayoutStyle
    from ui.theme import apply_appearance
    from ui.widgets import (ButtonFontFilter, DialogFocusFilter,
                            GroupBoxSurfaceFilter, TooltipWrapFilter)
    for fp in resource_path("assets/fonts").glob("*.ttf"):
        QFontDatabase.addApplicationFont(str(fp))
    app.setStyle(WinButtonLayoutStyle("Fusion"))
    for F in (ButtonFontFilter, GroupBoxSurfaceFilter, TooltipWrapFilter,
              DialogFocusFilter):
        app.installEventFilter(F(app))

    # An isolated settings store: driving the app must never touch the
    # developer's own preferences or projects.
    from PyQt6.QtCore import QSettings as _QS
    import core.settings as cs
    ini = Path(tempfile.mkdtemp()) / "drive.ini"
    cs.QSettings = lambda *a, **k: _QS(str(ini), _QS.Format.IniFormat)
    s = cs.AppSettings()
    s.set("custom_output_path", str(work))
    s.set("calibration_mode", True)
    apply_appearance(app, None, "light")

    from core.measurement_target import (RUN_TYPE_CALIBRATION,
                                         RUN_TYPE_PROFILING)
    from ui.main_window import MainWindow
    w = MainWindow(s)
    apply_appearance(app, w, "light")
    w.resize(1600, 1000)
    w.show()
    for _ in range(60):
        app.processEvents()

    tab, bar, ctl = w._tab_chart, w._target_bar, w._target_bar._ctl
    w._file_mgr.set_target_name("Demo-09-Run-Descriptions")
    bar.refresh()
    for _ in range(20):
        app.processEvents()

    def settle(n=25):
        for _ in range(n):
            app.processEvents()

    def select(run_id, run_type=RUN_TYPE_PROFILING):
        ctl.set_run_type(run_type)
        if run_type == RUN_TYPE_PROFILING:
            ctl.set_profile_run(run_id)
        tab._on_target_changed()
        settle()

    print("\n--- README step 2: run 1's own text, with its own labels ---")
    select("run1")
    check("run 1 description label", tab._manual_run_desc_lbl.text(),
          "Run 1 Description:")
    check("run 1 notes label", tab._manual_chart_notes_lbl.text(),
          "Run 1 Chart Notes:")
    check("run 1 description", tab._manual_run_desc_edit.text(),
          "PhotoRag Baryta, gloss, large chart")
    check("run 1 chart notes", tab._manual_chart_notes_edit.text(),
          "printed 5 Aug, tray 2")

    print("\n--- README step 3: run 2 has its own, nothing carries across ---")
    select("run2")
    check("run 2 description", tab._manual_run_desc_edit.text(),
          "PhotoRag Baryta, matte, large chart")
    check("run 2 label", tab._manual_run_desc_lbl.text(), "Run 2 Description:")
    select("run1")
    check("run 1's text returns", tab._manual_run_desc_edit.text(),
          "PhotoRag Baryta, gloss, large chart")

    print("\n--- README step 4: an undescribed run stays empty ---")
    select("run3")
    check("run 3 description is empty", tab._manual_run_desc_edit.text(), "")
    check("run 3 notes are empty", tab._manual_chart_notes_edit.text(), "")

    print("\n--- README steps 5-6: what the Profile Description is built from ---")
    prof = w._tab_profile
    select("run1")
    prof._apply_profile_description_default()
    settle()
    check("-D for a described run", prof._m_desc_edit.text(),
          "Demo-09-Run-Descriptions-PhotoRag Baryta, gloss, large chart")
    select("run3")
    prof._apply_profile_description_default()
    settle()
    check("-D with no run description", prof._m_desc_edit.text(),
          "Demo-09-Run-Descriptions")
    check("…and no trailing hyphen", prof._m_desc_edit.text().endswith("-"), False)

    print("\n--- README step 7: your own text is yours ---")
    prof._m_desc_edit.setText("My Own Profile Name")
    select("run1")
    prof._apply_profile_description_default()
    settle()
    check("typed text survives a run change", prof._m_desc_edit.text(),
          "My Own Profile Name")
    prof._m_desc_edit.setText("")
    prof._apply_profile_description_default()
    settle()
    check("clearing hands it back", prof._m_desc_edit.text(),
          "Demo-09-Run-Descriptions-PhotoRag Baryta, gloss, large chart")

    print("\n--- README steps 8-9: a calibration has its own ---")
    bar.set_calibration_allowed(True)
    select("run1", RUN_TYPE_CALIBRATION)
    check("calibration description label", tab._manual_run_desc_lbl.text(),
          "Calibration Description:")
    check("calibration notes label (no run number)",
          tab._manual_chart_notes_lbl.text(), "Chart Notes:")
    check("the calibration's own description", tab._manual_run_desc_edit.text(),
          "Canson Baryta, new ink set, warm room")
    select("run1", RUN_TYPE_PROFILING)
    check("run 1 is untouched by the visit", tab._manual_run_desc_edit.text(),
          "PhotoRag Baryta, gloss, large chart")

    print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
    for f in FAIL:
        print(f"  ✗ {f}")
    w.close()
    shutil.rmtree(work, ignore_errors=True)
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
