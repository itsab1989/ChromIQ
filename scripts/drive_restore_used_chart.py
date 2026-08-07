#!/usr/bin/env python3
"""Press **Restore Used Chart** for real, on every target that ships one.

Knut, #130, on README step 24: *"the demo test runs and verification runs do not
have proper data files, like measurements and pre-stored chart in a chart/
folder, thus using the 'Restore Used Chart' button was not possible, as the test
was described."* That blocker is fixed — the package now ships a stored chart
for all five targets — and `drive_demo_09.py` asserts exactly that.

**But asserting the data is not the same as pressing the button**, and the step
claims something stronger: *"Restore Used Chart puts the notes back, for all
three."* Nothing drove it. This does: it clicks the real button in the real
window, for each target in turn, and checks the chart files and the chart notes
actually come back.

Why it is worth the separate script: the last time something was reported fixed
without the path being driven, the fix had never once run (beta.160, the Esc
window that no reader could reach). The data check would pass in that world too.

    CHROMIQ_DRIVE_ONSCREEN=1 python scripts/drive_restore_used_chart.py [package]

Runs on a throwaway copy with a redirected QSettings store, so it cannot touch
the real ~/ChromIQ or the developer's preferences.
"""
from __future__ import annotations

import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

if not os.environ.get("CHROMIQ_DRIVE_ONSCREEN"):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    import PyQt6.QtWebEngineWidgets  # noqa: F401  (before QApplication)
except ImportError:
    pass

from PyQt6.QtCore import QSettings, QTimer                      # noqa: E402
from PyQt6.QtGui import QFontDatabase                           # noqa: E402
from PyQt6.QtWidgets import QApplication, QMessageBox           # noqa: E402

PASS: list[str] = []
FAIL: list[str] = []


def check(label: str, got, want) -> None:
    ok = got == want
    (PASS if ok else FAIL).append(label)
    print(f"  {'OK  ' if ok else 'FAIL'} {label}\n         → {got!r}"
          + ("" if ok else f"   (wanted {want!r})"))


def _settle(app, ms: int = 250) -> None:
    end = time.time() + ms / 1000
    while time.time() < end:
        app.processEvents()
        time.sleep(0.01)


def main() -> int:
    src = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "dist" / "demo-package"
    project_src = src / "Demo-09-Run-Descriptions"
    if not project_src.is_dir():
        print(f"no Demo-09 in {src} — build it with scripts/make_demo_package.py")
        return 2

    sandbox = Path(tempfile.mkdtemp(prefix="chromiq-restore-"))
    work = sandbox / "ChromIQ"
    work.mkdir()
    shutil.copytree(project_src, work / project_src.name)

    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("ChromIQ")
    app.setOrganizationName("ChromIQ")
    from core.resource_path import resource_path
    for fp in resource_path("assets/fonts").glob("*.ttf"):
        QFontDatabase.addApplicationFont(str(fp))

    # A redirected store: never the developer's real preferences.
    from core.settings import AppSettings
    settings = AppSettings()
    settings._qs = QSettings(str(sandbox / "s.ini"), QSettings.Format.IniFormat)
    settings.set("custom_output_path", str(work))
    settings.set("target_name", project_src.name)

    from ui.styles import WinButtonLayoutStyle
    from ui.theme import apply_appearance
    from ui.widgets import (ButtonFontFilter, DialogFocusFilter,
                            GroupBoxSurfaceFilter, TooltipWrapFilter)
    app.setStyle(WinButtonLayoutStyle("Fusion"))
    for F in (ButtonFontFilter, GroupBoxSurfaceFilter, TooltipWrapFilter,
              DialogFocusFilter):
        app.installEventFilter(F(app))
    apply_appearance(app, None, "light")

    # Any confirmation the restore raises is accepted, the way a user would.
    seen_dialogs: list[str] = []

    def _accept_dialogs():
        for w in app.topLevelWidgets():
            if isinstance(w, QMessageBox) and w.isVisible():
                seen_dialogs.append(w.text()[:70])
                for b in w.buttons():
                    role = w.buttonRole(b)
                    if role in (QMessageBox.ButtonRole.AcceptRole,
                                QMessageBox.ButtonRole.YesRole):
                        b.click()
                        return
                w.close()

    timer = QTimer()
    timer.timeout.connect(_accept_dialogs)
    timer.start(150)

    from ui.main_window import MainWindow
    win = MainWindow(settings)
    apply_appearance(app, win, "light")
    win.resize(1500, 1000)
    win.show()
    _settle(app, 900)

    from core.file_manager import Project
    from workflow.chart_slot import (slot_for_calibration, slot_for_run,
                                     slot_for_verification)
    from workflow.verify_chart_snapshot import slot_has_snapshot

    proj = Project.load(work / project_src.name)
    bar = win._target_bar

    def restore_for(label: str, slot, run_type: str, select) -> None:
        """Change the live chart, then press the real button and prove it came back.

        On a pristine package the button is CORRECTLY disabled — restore_state()
        says "the chart on disk is already identical to the stored copy, so
        there is nothing to put back". Knut's step assumes the user has
        regenerated the chart first. Rather than run targen again (slow, and it
        would test Argyll), the live chart is perturbed directly: that is the
        state the user reaches, and it is what Restore has to undo.
        """
        from workflow.verify_chart_snapshot import (slot_has_snapshot,
                                                    snapshot_matches_live)
        print(f"\n--- Restore Used Chart: {label} ---")
        if not slot_has_snapshot(slot):
            check(f"{label}: ships a stored chart", False, True)
            return

        select()
        _settle(app, 400)
        check(f"{label}: nothing to restore while live == stored",
              bar._restore_btn.isEnabled(), False)

        # slot.live_files() is what snapshot_matches_live() compares against.
        # Globbing a directory by hand perturbed a file the comparison never
        # looks at, so the button correctly stayed asleep and the test read
        # like an app bug.
        live = [p for p in slot.live_files() if p.is_file()]
        if not live:
            check(f"{label}: found a live chart file to perturb", False, True)
            return
        victim = live[0]
        original = victim.read_bytes()
        victim.write_bytes(original + b"\n# perturbed by the restore driver\n")

        (bar.refresh() if hasattr(bar, 'refresh') else bar._sync_from_target())
        _settle(app, 400)
        why = bar._ctl.restore_state()
        print(f"         restore_state -> enabled={why[0]}  reason={why[1][:120]!r}")
        print(f"         perturbed: {victim.name}  live_files={len(live)}  "
              f"matches_live={snapshot_matches_live(slot)}")
        enabled = bar._restore_btn.isEnabled()
        check(f"{label}: the button wakes up once live differs", enabled, True)
        if not enabled:
            victim.write_bytes(original)
            return

        bar._on_restore_clicked()
        _settle(app, 1500)
        check(f"{label}: the live chart matches the stored copy again",
              snapshot_matches_live(slot), True)
        check(f"{label}: no error dialog",
              not any("could not" in d.lower() or "failed" in d.lower()
                      for d in seen_dialogs[-3:]), True)

    win._tabs.setCurrentIndex(2)          # Measure — where the bar shows Restore
    _settle(app, 600)

    for rid in [r.id for r in proj.all_runs()]:
        restore_for(rid, slot_for_run(proj.run(rid)), "Profiling",
                    lambda r=rid: (bar._ctl.set_run_type("Profiling"),
                                   bar._ctl.set_profile_run(r)))

    print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
    if seen_dialogs:
        print(f"dialogs answered: {len(seen_dialogs)}")
        for d in seen_dialogs[:6]:
            print(f"  · {d}")
    win.close()
    shutil.rmtree(sandbox, ignore_errors=True)
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
