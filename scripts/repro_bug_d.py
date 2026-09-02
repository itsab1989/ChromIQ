#!/usr/bin/env python3
"""Reproduce (or rule out) #130 Bug D: with the Profile-run bar set to
"Overwrite run 1", selecting a preset builds into run 2 instead of run 1.

Drives the REAL MainWindow and the REAL Profile-run combo widget (not the
controller directly), so the actual Qt signal flow — combo → controller →
bar.refresh() → _sync_from_controller — is exercised, which a headless
controller-only drive skips. Run on screen:

    CHROMIQ_DRIVE_ONSCREEN=1 python scripts/repro_bug_d.py
"""
from __future__ import annotations

import os
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
from PyQt6.QtGui import QFontDatabase                          # noqa: E402
from PyQt6.QtWidgets import QApplication, QDialog, QMessageBox  # noqa: E402

from core.resource_path import resource_path                   # noqa: E402


def pump(app, ms=300):
    end = time.time() + ms / 1000.0
    while time.time() < end:
        app.processEvents()
        time.sleep(0.01)


def main() -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    try:
        for fp in resource_path("assets/fonts").glob("*.ttf"):
            QFontDatabase.addApplicationFont(str(fp))
    except Exception:
        pass

    # Sandbox working folder with Test-Profiling-P: run1 (profiling + verify
    # chart), run2, current run = run2 (as the fixture leaves it).
    sandbox = Path(tempfile.mkdtemp(prefix="chromiq_bugd_"))
    from core.file_manager import Project
    proj = Project.create(sandbox / "Test-Profiling-P", "Test-Profiling-P")
    r1 = proj.current_run(); r1.ensure_dir()
    r1.chart_ti2.write_text("c1", encoding="utf-8"); (r1.dir / "Test-Profiling-P.tif").write_bytes(b"")
    r1.profile_icc.write_text("icc", encoding="utf-8"); r1.measurement_ti3.write_text("m", encoding="utf-8")
    r1.verifications_dir.mkdir(parents=True, exist_ok=True)
    r1.verify_chart_ti2.write_text("v", encoding="utf-8")
    (r1.verifications_dir / "Test-Profiling-P-verify.tif").write_bytes(b"")
    r2 = proj.new_run(); r2.ensure_dir()
    r2.chart_ti2.write_text("c2", encoding="utf-8"); (r2.dir / "Test-Profiling-P.tif").write_bytes(b"")
    r2.profile_icc.write_text("icc2", encoding="utf-8"); r2.measurement_ti3.write_text("m2", encoding="utf-8")
    print(f"Sandbox: {sandbox}")
    print(f"current_run in manifest: {Project.load(proj.root).current_run().id}")

    from PyQt6.QtCore import QSettings
    from core.settings import AppSettings
    settings = AppSettings()
    settings._qs = QSettings(str(sandbox / "s.ini"), QSettings.Format.IniFormat)
    settings.set("custom_output_path", str(sandbox))
    settings.set("use_chromiq_layout_engine", False)

    QDialog.exec = lambda self: 0                       # non-blocking dialogs
    for m in ("warning", "critical", "information", "question"):
        setattr(QMessageBox, m, staticmethod(lambda *a, **k: 0))

    from ui.main_window import MainWindow
    import ui.tabs.tab_chart as tc
    win = MainWindow(settings)
    if ONSCREEN:
        win.show()
    pump(app, 500)

    tab = win._tab_chart
    ctl = win._target_ctl
    bar = win._target_bar

    # --- Load the project via the real "Load profile" ------------------------
    tc.open_file_dialog = lambda *a, **k: str(proj.root / "project.json")
    win._tabs.setCurrentWidget(tab)
    tab._switch_mode("manual")
    if not tab._manual_panel_inited:
        tab._init_manual_layout_panel()
    tab._load_existing_profile()
    pump(app, 400)
    print(f"\nafter Load profile: bar profile_run = {ctl.target.profile_run!r} "
          f"(project current_run = {Project.load(proj.root).current_run().id})")

    # --- Drive the REAL run combo to "Run 1 (overwrite)" ---------------------
    combo = bar._run_combo
    idx = combo.findData("run1")
    print(f"run combo items: {[(combo.itemText(i), combo.itemData(i)) for i in range(combo.count())]}")
    combo.setCurrentIndex(idx)
    pump(app, 300)
    print(f"after selecting 'Run 1' in the combo: bar profile_run = {ctl.target.profile_run!r}")

    # A refresh (as happens on tab switch / accent change) — does it reset?
    bar.refresh()
    pump(app, 200)
    print(f"after bar.refresh(): bar profile_run = {ctl.target.profile_run!r}")

    # --- Capture where a build WOULD route, then run the preset --------------
    captured = {}
    real_generate = tab._on_generate
    def _spy_generate():
        captured["profile_run_at_generate"] = ctl.target.profile_run
        real_generate()
    tab._on_generate = _spy_generate

    # ColorMunki A3 1575-patch, 3 pages (Knut's preset). Runs real targen/
    # printtarg via Argyll; wait for it to finish.
    tab._apply_colormunki_td_preset(1575, 13, 13, 40)
    # Wait for generation to finish (or time out).
    end = time.time() + 40
    while tab._runner.is_running and time.time() < end:
        app.processEvents(); time.sleep(0.02)
    pump(app, 500)

    print(f"\nprofile_run AT generate entry: {captured.get('profile_run_at_generate')!r}")
    print(f"bar profile_run AFTER generate: {ctl.target.profile_run!r}")
    p2 = Project.load(proj.root)
    print(f"project current_run AFTER generate: {p2.current_run().id}")
    # Which run's chart TIFFs changed (were rewritten)?
    for rid in p2._manifest.runs:
        r = p2.run(rid)
        tifs = sorted(r.dir.glob("*.tif"))
        vtifs = sorted(r.verifications_dir.glob("*.tif")) if r.verifications_dir.exists() else []
        print(f"  {rid}: root tifs={[t.name for t in tifs]} verify tifs={[t.name for t in vtifs]} "
              f"ti3={r.measurement_ti3.exists()} icc={r.profile_icc.exists()}")

    if ONSCREEN:
        pump(app, 2500)
    os._exit(0)


if __name__ == "__main__":
    main()
