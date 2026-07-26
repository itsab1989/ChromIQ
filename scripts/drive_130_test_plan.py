#!/usr/bin/env python3
"""Drive the REAL ChromIQ app through the #130 verification-runs test plan
against the load-test fixtures (scripts/make_load_test_data.py).

It builds the actual MainWindow (mirroring main.py's font/style setup), points
the working folder at a throwaway sandbox seeded with the fixtures, then walks
the load-model scenarios — auto-answering the modal pop-ups to the choice each
row intends — and asserts the resulting file-system + bar/preview state. Every
scenario is isolated in a try/except so one failure never aborts the run; a
PASS/FAIL table is printed at the end.

Run headless for a rigorous pass/fail:
    QT_QPA_PLATFORM=offscreen python scripts/drive_130_test_plan.py
Run on screen to watch it (slower, with pauses):
    CHROMIQ_DRIVE_ONSCREEN=1 python scripts/drive_130_test_plan.py

These scenarios and the verification rows run together, with one table, via
`scripts/drive_130.py` — that is the one to run before cutting a beta.
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

# QtWebEngine MUST be imported before QApplication is instantiated, or the
# gamut panel's WebEngine view segfaults (mirrors main.py; see memory).
try:
    import PyQt6.QtWebEngineWidgets  # noqa: F401
except ImportError:
    pass

from PyQt6.QtGui import QFontDatabase                       # noqa: E402
from PyQt6.QtWidgets import QApplication, QDialog, QMessageBox  # noqa: E402

from core.resource_path import resource_path                # noqa: E402

RESULTS: list[tuple[str, bool, str]] = []


def record(name: str, ok: bool, detail: str = "") -> None:
    RESULTS.append((name, ok, detail))
    mark = "PASS" if ok else "FAIL"
    print(f"  [{mark}] {name}" + (f" — {detail}" if detail else ""))


def pump(app, ms: int = 250) -> None:
    """Let the UI settle (and, on screen, be visible) between steps.

    Only spins the event loop when running on screen — offscreen we drive the
    handlers synchronously and assert file-system state, and spinning the
    offscreen event loop can deliver queued startup slots that segfault under
    the headless platform (irrelevant to the load-model logic under test)."""
    if not ONSCREEN:
        return
    end = time.time() + ms / 1000.0
    while time.time() < end:
        app.processEvents()
        time.sleep(0.01)


def build_app():
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("ChromIQ")
    try:
        for fp in resource_path("assets/fonts").glob("*.ttf"):
            QFontDatabase.addApplicationFont(str(fp))
    except Exception:
        pass
    return app


def seed_fixtures() -> tuple[Path, Path]:
    """Generate the load-test fixtures into a sandbox; return (working_dir,
    external_dir). The working-folder projects become the app's ~/ChromIQ."""
    import scripts.make_load_test_data as mk
    sandbox = Path(tempfile.mkdtemp(prefix="chromiq_130_drive_"))
    mk.main(sandbox)
    root = sandbox / "ChromIQ-load-test-data"
    return root / "working-folder", root / "external"


def run_scenarios() -> None:
    """Walk every load-model scenario, appending each row to ``RESULTS``.

    Reports nothing and exits nothing, so `scripts/drive_130.py` can run this
    alongside the verification rows and print a single table for both.
    """
    app = build_app()
    work, ext = seed_fixtures()
    print(f"Sandbox working folder: {work}")
    print(f"External fixtures:      {ext}\n")

    # Real settings, pointed at the sandbox working folder; never touch the
    # user's real ~/ChromIQ or their persisted settings.
    from PyQt6.QtCore import QSettings
    from core.settings import AppSettings
    settings = AppSettings()
    settings._qs = QSettings(str(work.parent / "drive_settings.ini"),
                             QSettings.Format.IniFormat)
    settings.set("custom_output_path", str(work))

    # Auto-answer the modal pop-ups. Tests set _NEXT_CHOICE / _NEXT_NAME.
    import ui.ti2_loader as L
    state = {"choice": None, "name": ("Imported", False)}
    L._choice_dialog = lambda *a, **k: state["choice"]
    L._ask_project_name = lambda *a, **k: state["name"]
    # Any stray InfoDialog / message box: don't block.
    QDialog.exec = lambda self: 0                      # type: ignore[assignment]
    for m in ("warning", "critical", "information", "question"):
        setattr(QMessageBox, m, staticmethod(lambda *a, **k: 0))

    from ui.main_window import MainWindow
    win = MainWindow(settings)
    if ONSCREEN:
        win.show()
    pump(app, 400)

    tab_chart = win._tab_chart
    tab_measure = win._tab_measure
    ctl = getattr(tab_measure, "_target_ctl", None)
    fm = win._file_mgr

    def open_project(name: str) -> None:
        """Make the working-folder project *name* the current one (what 'Load
        profile' does), so the controller resolves the right project."""
        fm.set_target_name(name)

    from core.file_manager import Project
    from core.measurement_target import (RUN_TYPE_PROFILING,
                                          RUN_TYPE_VERIFICATION)
    from pathlib import Path as P

    # ---- SCN-1: Load profile opens Test-Profiling-P, bar + preview populate --
    print("SCN-1  Load profile → Test-Profiling-P (open a project)")
    try:
        import ui.tabs.tab_chart as tc
        p_ti2 = work / "Test-Profiling-P" / "runs" / "run2" / "Test-Profiling-P.ti2"
        # Drive the real "Load profile" via its file-picker, patched to our path.
        tc.open_file_dialog = lambda *a, **k: str(
            work / "Test-Profiling-P" / "project.json")
        tab_chart._load_existing_profile()
        pump(app)
        name_ok = tab_chart._file_mgr.get_target_name() == "Test-Profiling-P"
        record("SCN-1 project opened + named", name_ok,
               tab_chart._file_mgr.get_target_name())
    except Exception as exc:
        record("SCN-1 project opened + named", False, f"{type(exc).__name__}: {exc}")

    # ---- SCN-2: switch Run type Verification → verify chart previews ----------
    print("SCN-2  Run type = Verification → verify chart shows (has a TIFF)")
    try:
        proj = Project.load(work / "Test-Profiling-P")
        run1 = proj.run("run1")
        has_tiff = bool(run1.verify_chart_tiffs())
        if ctl is not None:
            ctl.set_profile_run("run1")
            ctl.set_run_type(RUN_TYPE_VERIFICATION)
            pump(app)
            ctl.set_run_type(RUN_TYPE_PROFILING)
            pump(app)
        record("SCN-2 verify chart has a previewable TIFF", has_tiff,
               str(run1.verify_chart_tiffs()))
    except Exception as exc:
        record("SCN-2 verify chart has a previewable TIFF", False,
               f"{type(exc).__name__}: {exc}")

    # ---- SCN-3: A1a loose chart, New run · Profiling → import full set --------
    print("SCN-3  Load loose .ti2 · New run · Profiling → new run, full set")
    try:
        from ui.ti2_loader import resolve_ti2
        proj = Project.load(work / "Test-Profiling-P")
        before = set(proj._manifest.runs)
        ctl.set_profile_run(""); ctl.set_run_type(RUN_TYPE_PROFILING)  # New run
        state["choice"] = "import"
        ti2 = ext / "loose-chart" / "loose-chart.ti2"
        out = resolve_ti2(win, ti2, settings, ctl)
        pump(app)
        proj2 = Project.load(work / "Test-Profiling-P")
        new = [r for r in proj2._manifest.runs if r not in before]
        ok = bool(new) and out is not None
        if ok:
            r = proj2.run(new[0])
            ok = r.chart_ti2.exists() and r.measurement_ti3.exists() and r.profile_icc.exists()
        record("SCN-3 loose→new run full set", ok, f"new run={new}")
    except Exception as exc:
        record("SCN-3 loose→new run full set", False, f"{type(exc).__name__}: {exc}")

    # ---- SCN-4: A1a loose chart, New run · Verification → chart only ----------
    print("SCN-4  Load loose .ti2 · New run · Verification → verify chart only")
    try:
        from ui.ti2_loader import resolve_ti2
        proj = Project.load(work / "Test-Profiling-P")
        before = set(proj._manifest.runs)
        ctl.set_profile_run(""); ctl.set_run_type(RUN_TYPE_VERIFICATION)
        state["choice"] = "import"
        out = resolve_ti2(win, ext / "loose-chart" / "loose-chart.ti2", settings, ctl)
        pump(app)
        proj2 = Project.load(work / "Test-Profiling-P")
        new = [r for r in proj2._manifest.runs if r not in before]
        ok = bool(new)
        if ok:
            r = proj2.run(new[0])
            ok = r.verify_chart_ti2.exists() and not r.profile_icc.exists()
        record("SCN-4 loose→verify chart only (no icc)", ok, f"new run={new}")
    except Exception as exc:
        record("SCN-4 loose→verify chart only (no icc)", False, f"{type(exc).__name__}: {exc}")

    # ---- SCN-5: A1b whole external project Q → copy into working folder -------
    print("SCN-5  Load Full-Project-Q's chart → copy whole project in")
    try:
        from ui.ti2_loader import resolve_ti2
        q_ti2 = ext / "Full-Project-Q" / "runs" / "run1" / "Full-Project-Q.ti2"
        state["choice"] = "whole"; state["name"] = ("Full-Project-Q", False)
        out = resolve_ti2(win, q_ti2, settings, ctl)
        pump(app)
        ok = (work / "Full-Project-Q" / "project.json").is_file()
        record("SCN-5 whole project copied in", ok, str(out))
    except Exception as exc:
        record("SCN-5 whole project copied in", False, f"{type(exc).__name__}: {exc}")

    # ---- SCN-6: A2c old-flat chart (no project.json) → import into project ----
    print("SCN-6  Load old-flat-chart .ti2 (no project.json) · New run")
    try:
        from ui.ti2_loader import resolve_ti2
        # Re-open Test-Profiling-P as the working project first.
        open_project("Test-Profiling-P")
        ctl.set_profile_run(""); ctl.set_run_type(RUN_TYPE_PROFILING)
        before = set(Project.load(work / "Test-Profiling-P")._manifest.runs)
        state["choice"] = "import"
        out = resolve_ti2(win, ext / "old-flat-chart" / "old-flat-chart.ti2",
                          settings, ctl)
        ok = out is not None
        record("SCN-6 old-flat loose import handled", ok, str(out))
    except Exception as exc:
        record("SCN-6 old-flat loose import handled", False, f"{type(exc).__name__}: {exc}")

    # ---- SCN-7: Overwrite → Replace archives displaced files to old/ ---------
    print("SCN-7  Overwrite run · Replace → displaced files moved to old/")
    try:
        from ui.ti2_loader import resolve_ti2
        open_project("Test-Profiling-P")
        proj = Project.load(work / "Test-Profiling-P")
        run1 = proj.run("run1")
        # Ensure run1 has a profiling chart + measurement to displace.
        run1.chart_ti2.write_text("old-chart"); run1.measurement_ti3.write_text("old-meas")
        ctl.set_profile_run("run1"); ctl.set_run_type(RUN_TYPE_PROFILING)
        state["choice"] = "replace"
        out = resolve_ti2(win, ext / "loose-chart" / "loose-chart.ti2", settings, ctl)
        pump(app)
        r = Project.load(work / "Test-Profiling-P").run("run1")
        ok = r.old_dir.exists() and any(r.old_dir.iterdir())
        record("SCN-7 Replace archived to old/", ok, str(r.old_dir))
    except Exception as exc:
        record("SCN-7 Replace archived to old/", False, f"{type(exc).__name__}: {exc}")

    # ---- SCN-8: Load profile porting of a pre-#127 project (Model C) ----------
    print("SCN-8  Load profile → Legacy-Flat-Project → ported to current layout")
    try:
        import shutil as _sh
        import ui.tabs.tab_chart as tc
        # Realistic flow: the legacy project lives in the working folder (the
        # user copied it into ~/ChromIQ), so opening it migrates it in place.
        legacy = work / "Legacy-Flat-Project"
        _sh.copytree(ext / "Legacy-Flat-Project", legacy, dirs_exist_ok=True)
        info_shown = {"n": 0}
        real_info = tc.InfoDialog
        class _Spy(real_info):        # count the port announcement
            def __init__(self, *a, **k):
                info_shown["n"] += 1
                super().__init__(*a, **k)
            def exec(self):
                return 0
        tc.InfoDialog = _Spy
        tc.open_file_dialog = lambda *a, **k: str(legacy / "project.json")
        tab_chart._load_existing_profile()
        pump(app)
        import json
        ver = json.loads((legacy / "project.json").read_text()).get("schema_version")
        tc.InfoDialog = real_info
        ok = info_shown["n"] >= 1 and ver == 3
        record("SCN-8 legacy project ported + announced", ok,
               f"announced={info_shown['n']}, schema now {ver}")
    except Exception as exc:
        record("SCN-8 legacy project ported + announced", False,
               f"{type(exc).__name__}: {exc}")

    # ---- SCN-9: Hole 2 guard — verification with no verify chart -------------
    print("SCN-9  Measure · Verification · profile but no verify chart → guard")
    try:
        proj = Project.load(work / "Second-Project-R")
        run = proj.run("run1")
        run.profile_icc.write_text("icc")             # has a profile
        # Remove any verify chart so Hole 2 applies.
        if run.verifications_dir.exists():
            import shutil as _sh; _sh.rmtree(run.verifications_dir)
        tab_measure._ti1_path = run.chart_ti2
        cb = (tab_measure._verify_cb if tab_measure._current_mode() == "guided"
              else tab_measure._m_verify_cb)
        cb.setChecked(True)
        msg = tab_measure._verification_guard()
        ok = msg is not None and "verification chart" in msg.lower()
        record("SCN-9 Hole-2 guard fires", ok, (msg or "")[:60])
    except Exception as exc:
        record("SCN-9 Hole-2 guard fires", False, f"{type(exc).__name__}: {exc}")

    if ONSCREEN:
        pump(app, 2000)


def main() -> int:
    """Standalone entry point: the load-model rows only, with their own table."""
    run_scenarios()
    # ---- summary (printed BEFORE teardown; the WebEngine teardown segfaults
    # offscreen — issue #38 — so we hard-exit past it after reporting) ---------
    passed = sum(1 for _, ok, _ in RESULTS if ok)
    print(f"\n==== {passed}/{len(RESULTS)} scenarios PASSED ====")
    for name, ok, detail in RESULTS:
        if not ok:
            print(f"  FAIL: {name} — {detail}")
    sys.stdout.flush()
    rc = 0 if passed == len(RESULTS) else 1
    os._exit(rc)              # skip the crash-prone WebEngine teardown (#38)
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
