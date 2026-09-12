#!/usr/bin/env python3
"""Drive the REAL Print Chart tab and read the notice under a greyed-out
"Through the profile", in a project whose profile is in ANOTHER run.

A user reported the option greyed with no way to work out why. ChromIQ keeps a
verification inside the profiling run it judges, so the option asks whether THIS
run holds a profile. Hers was in a different run, and the message told her to
set Run type to Profiling and build one, which she had already done.

This driver builds a sandbox project of two runs, puts a profile in run 1 and a
verification chart in run 2, points the bar at run 2 and photographs the window.
It then does the same in a project with no profile anywhere, to prove the old
words survive where they are still the right ones. Nothing is asserted from the
widget's own render: the window is photographed with ``scripts/onscreen_capture``,
which refuses a locked screen and proves the picture contains the window.

Basti's preferences are copied to a throwaway .ini and his ChromIQ root replaced
by a sandbox. Check afterwards with

    defaults read com.chromiq.ChromIQ custom_output_path

Usage::

    CHROMIQ_SETTINGS_FILE=/tmp/chromiq-notice.ini \
    CHROMIQ_PRESETS_DIR=/tmp/chromiq-notice-presets \
        python scripts/drive_182_no_profile_notice.py
"""
from __future__ import annotations

import json
import re
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

try:
    import PyQt6.QtWebEngineWidgets  # noqa: F401
except ImportError:
    pass

from PyQt6.QtCore import QSettings                              # noqa: E402
from PyQt6.QtWidgets import QApplication, QDialog, QMessageBox  # noqa: E402

from scripts.onscreen_capture import capture_window, session_is_locked  # noqa: E402

REAL_PLIST = Path.home() / "Library/Preferences/com.chromiq.ChromIQ.plist"
OUT = Path("/tmp/chromiq-notice-proof")


def pump(app, ms):
    end = time.monotonic() + ms / 1000.0
    while time.monotonic() < end:
        app.processEvents()
        time.sleep(0.01)


def plain(html: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html)).strip()


def build_project(work: Path, name: str, *, profile_in: list[str],
                  runs: int, chart_in: str):
    """A project of ``runs`` runs with a stub profile in each of ``profile_in``
    and a verification chart with two pages in ``chart_in``."""
    from core.file_manager import Project
    project = Project.create(work / name, name)
    project.current_run().ensure_dir()
    for _ in range(runs - 1):
        project.new_run()
    for rid in profile_in:
        project.run(rid).profile_icc.write_bytes(b"icc-stub")
    run = project.run(chart_in)
    run.verifications_dir.mkdir(parents=True, exist_ok=True)
    run.verify_chart_ti2.write_text("CTI2\n", encoding="utf-8")
    from PIL import Image
    pages = []
    for i in (1, 2):
        p = run.verifications_dir / f"{run.verify_stem}_{i:02d}.tif"
        Image.new("RGB", (64, 90), (255, 255, 255)).save(p, format="TIFF")
        pages.append(p)
    # The bar reads the manifest's current run; leave it on the one being shown.
    project.set_current_run(chart_in)
    return project, run, pages


def show(win, app, ctl, project_name, run_id, ti2, pages):
    from core.measurement_target import RUN_TYPE_VERIFICATION
    win._file_mgr.set_target_name(project_name)
    ctl.set_profile_run(run_id)
    ctl.set_run_type(RUN_TYPE_VERIFICATION)
    win._target_bar.refresh()
    pump(app, 400)
    win._tabs.setCurrentWidget(win._tab_print)
    pump(app, 300)
    # The two calls main_window itself makes when a run's chart is put in front
    # of the user (main_window.py ~1599).
    win._tab_print.set_ti2_path(ti2)
    win._tab_print.load_tiffs(list(pages))
    pump(app, 900)


def run(app) -> int:
    from core.settings import AppSettings

    sandbox = Path(tempfile.mkdtemp(prefix="chromiq-notice-"))
    src = QSettings(str(REAL_PLIST), QSettings.Format.NativeFormat)
    dst = QSettings(str(sandbox / "settings.ini"), QSettings.Format.IniFormat)
    for k in src.allKeys():
        dst.setValue(k, src.value(k))
    dst.sync()
    settings = AppSettings()
    settings._qs = dst
    work = sandbox / "ChromIQ"
    work.mkdir()
    settings.set("custom_output_path", str(work))
    settings.set("restore_last_session", False)
    settings.set("appearance", "dark")
    print(f"    sandbox: {sandbox}", flush=True)

    QDialog.exec = lambda self: 1                      # type: ignore[assignment]
    for m in ("warning", "critical", "information", "question"):
        setattr(QMessageBox, m, staticmethod(lambda *a, **k: 0))
    QMessageBox.exec = lambda self: QMessageBox.StandardButton.Ok  # type: ignore

    from ui.main_window import MainWindow
    from ui.theme import apply_appearance

    apply_appearance(app, None, "dark")
    win = MainWindow(settings)
    win.show()
    win.raise_()
    win.activateWindow()
    pump(app, 3000)
    on_screen = win.isVisible() and win.frameGeometry().width() > 0
    print(f"    window is on screen: {on_screen} "
          f"{win.frameGeometry().width()}x{win.frameGeometry().height()}",
          flush=True)
    if session_is_locked():
        print("    FINDING: the screen is LOCKED; no capture can be proved",
              flush=True)

    OUT.mkdir(parents=True, exist_ok=True)
    ctl = win._target_ctl
    rows = []

    cases = [
        ("profile-in-run1", dict(runs=2, profile_in=["run1"], chart_in="run2")),
        ("profiles-in-run1-and-run2",
         dict(runs=3, profile_in=["run1", "run2"], chart_in="run3")),
        ("no-profile-anywhere", dict(runs=2, profile_in=[], chart_in="run2")),
    ]
    for name, spec in cases:
        project, run_obj, pages = build_project(work, name, **spec)
        show(win, app, ctl, name, spec["chart_in"], run_obj.verify_chart_ti2,
             pages)
        tab = win._tab_print
        text = plain(tab._cm_notice.text())
        shot = OUT / f"{name}.png"
        ok, why = capture_window(win, shot)
        rows.append({
            "case": name,
            "runs": spec["runs"],
            "profile_in": spec["profile_in"],
            "selected_run": spec["chart_in"],
            "through_enabled": tab._cm_through_rb.isEnabled(),
            "notice_visible": tab._cm_notice.isVisible(),
            "notice": text,
            "names_run_1": "Run 1" in text,
            "names_run_2": "Run 2" in text,
            "sends_user_to_build_profile": "Build Profile" in text,
            "capture": str(shot) if ok else None,
            "capture_refused": None if ok else why,
        })
        print(f"    {name}: through={tab._cm_through_rb.isEnabled()} "
              f"capture={'ok' if ok else 'REFUSED: ' + why}", flush=True)
        print(f"      {text[:150]}", flush=True)

    (OUT / "result.json").write_text(
        json.dumps({"on_screen": on_screen,
                    "screen_locked": session_is_locked(),
                    "cases": rows}, indent=2, ensure_ascii=False),
        encoding="utf-8")
    print(f"\n    wrote {OUT / 'result.json'}", flush=True)
    win.close()
    return 0


def main() -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    try:
        return run(app)
    finally:
        app.processEvents()


if __name__ == "__main__":
    raise SystemExit(main())
