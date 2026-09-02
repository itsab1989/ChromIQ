"""Two extra landing-page shots that `capture_screens.py` does not take.

Knut's landing-page review (2026-08-27) asks for the chart PATCH-SET EDITOR to
be promoted beside the chart itself, and for a section on verification over
time. Neither had a picture, so this shoots them:

    01  the chart patch-set editor (Tools ▸ Edit / create chart patch set),
        pre-loaded with the sample project's chart — goes on top of the
        Create Chart shot, angled, as the "duo";
    02  the Measurement Report (mean / worst ΔE00, worst patches, drift over
        time) — the picture for the new verification section.

It reuses `capture_screens.py` wholesale: the same app build, the same staged
copy of the sample project (so nothing under the user's own ~/ChromIQ is
written), and the same theme handling.

    source .venv/bin/activate
    CHROMIQ_SHOTS_OUT=/tmp/landing-extras python scripts/capture_landing_extras.py

Writes <out>/L1-patch-set-editor-<theme>.png and <out>/L2-measurement-report-<theme>.png.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from core.proc_text import run_text

import capture_screens as C          # noqa: E402  (a sibling in scripts/)
from PyQt6.QtCore import QTimer      # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

OUT = Path(os.environ.get("CHROMIQ_SHOTS_OUT", "/tmp/landing-extras"))
THEMES = ("dark", "light")


def _grab(widget, name: str, theme: str) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    pix = widget.grab()
    path = OUT / f"{name}-{theme}.png"
    pix.save(str(path))
    C.log(f"  wrote {path}  ({pix.width()}x{pix.height()})")


def _seed_verification_history(settings) -> "Path | None":
    """Give the staged run three dated verification measurements.

    The verification section of the landing page is about watching a profile
    over months, and the Measurement Report's trend graph needs at least two
    dated points before it draws anything — a first capture produced the shot
    with "a trend graph needs at least two measurement runs" printed across it,
    which is a poor advert for the feature it illustrates.

    So: three dates, each a REAL `fakeread` of the run's own chart through the
    run's own profile, with a rising `-R` deviation so the three differ the way
    a drifting printer does, and each file stamped with its date (the report
    dates a measurement by the file's own mtime). Nothing here is hand-written
    — a .ti3 we invented would be fiction.

    Returns the newest verification .ti3, or None if it could not be built.
    """
    import shutil
    import subprocess
    from core.file_manager import Project

    root = Path(settings.get("custom_output_path", "")) / C.A_DIR.name
    try:
        run = Project.load(root).current_run()
    except Exception as e:                       # noqa: BLE001
        C.log(f"  no project at {root}: {e}")
        return None
    # The sample project's profile sits at the PROJECT root, not in the run
    # folder (it predates the per-run layout), so try both.
    icc = run.profile_icc
    if not icc.exists():
        icc = C.A_ICC
    ti2 = run.chart_ti2
    if not (icc.exists() and ti2.exists()):
        C.log(f"  no profile or chart to fake verifications from "
              f"(icc={icc.exists()} ti2={ti2.exists()})")
        return None

    fakeread = shutil.which("fakeread") or "/Applications/Argyll/bin/fakeread"
    vdir = run.verifications_dir
    vdir.mkdir(parents=True, exist_ok=True)
    newest = None
    # (folder id, mtime, deviation %) — a printer that slowly drifts.
    dates = [("2026-02-11_101500", "202602111015", 0.4),
             ("2026-05-06_143000", "202605061430", 0.9),
             ("2026-08-19_092000", "202608190920", 1.7)]
    for idx, (folder, stamp, dev) in enumerate(dates):
        d = vdir / folder
        d.mkdir(parents=True, exist_ok=True)
        base = d / run.verify_stem
        shutil.copy2(ti2, base.with_suffix(".ti2"))
        try:
            r = run_text(
                [fakeread, "-2", "-R", str(dev), "-S", str(1000 + idx),
                 str(icc), str(base)],
                cwd=str(d), capture_output=True, timeout=300)
        except Exception as e:                   # noqa: BLE001
            C.log(f"  fakeread for {folder} failed: {e}")
            return None
        out = base.with_suffix(".ti3")
        if r.returncode != 0 or not out.exists():
            C.log(f"  fakeread for {folder}: "
                  f"{(r.stderr or r.stdout).strip()[:120]}")
            return None
        # The report dates each point by the file's own mtime.
        subprocess.run(["touch", "-t", stamp, str(out)], check=False)
        newest = out
    C.log(f"seeded {len(dates)} dated verifications under {vdir}")
    return newest


def _run_ti3(settings) -> Path | None:
    """The staged project's measurement, for the report dialog."""
    from core.file_manager import Project
    root = Path(settings.get("custom_output_path", "")) / C.A_DIR.name
    try:
        run = Project.load(root).current_run()
    except Exception as e:                       # noqa: BLE001
        C.log(f"  no project at {root}: {e}")
        return None
    ti3 = run.measurement_ti3
    return ti3 if ti3.exists() else None


def main() -> int:
    C.patch_loaders()
    app = C.build_app()
    from core.settings import AppSettings
    settings = AppSettings()
    # THIS RUNS AGAINST THE USER'S REAL PREFERENCES. `stage_the_project` points
    # `custom_output_path` at its throwaway copy and never puts it back, so a
    # capture used to leave the app looking at a folder the script had just
    # deleted. Remember every key we touch and restore them however this ends.
    saved = {k: settings.get(k, "") for k in
             ("custom_output_path", "session_target_name", "session_project_root")}
    C.log(f"saved settings to restore afterwards: {saved}")
    if not C.stage_the_project(settings):
        C.log("could not stage the sample project — aborting")
        for k, v in saved.items():
            settings.set(k, v)
        return 2
    win = C.MainWindow(settings)
    win.showMaximized()
    C.pump(1200)
    C.open_the_project(win, settings)
    C.pump(600)

    ti2 = win._current_chart_ti2()
    C.log(f"chart for the editor: {ti2}")
    ti3 = _seed_verification_history(settings) or _run_ti3(settings)
    C.log(f"measurement for the report: {ti3}")

    for theme in THEMES:
        C.set_theme(app, win, theme)
        C.pump(400)

        # 01 — the patch-set editor, pre-loaded with the run's chart.
        try:
            from ui.dialogs.ti2_relayout_dialog import Ti2RelayoutDialog
            dlg = Ti2RelayoutDialog(win._runner, settings, win,
                                    on_apply=None, initial_chart=ti2)
            dlg.setModal(False)
            dlg.show()
            dlg.raise_()
            C.pump(2500)
            _grab(dlg, "L1-patch-set-editor", theme)
            dlg.close()
            C.pump(300)
        except Exception as e:                   # noqa: BLE001
            C.log(f"  editor shot failed: {e}")

        # 02 — the measurement report.
        try:
            from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
            rep = MeasurementReportDialog(settings, win, initial_ti3=ti3)
            rep.setModal(False)
            rep.show()
            rep.raise_()
            C.pump(2500)
            _grab(rep, "L2-measurement-report", theme)
            rep.close()
            C.pump(300)
        except Exception as e:                   # noqa: BLE001
            C.log(f"  report shot failed: {e}")

    try:
        win._tab_check.shutdown_webengine()
    except Exception:                            # noqa: BLE001
        pass
    try:
        import shutil
        if C.STAGING_ROOT.exists() and C.STAGING_ROOT.name == "ChromIQ-docs":
            shutil.rmtree(C.STAGING_ROOT)
            C.log(f"removed the staged copy at {C.STAGING_ROOT}")
    except Exception as e:                       # noqa: BLE001
        C.log(f"could not remove {C.STAGING_ROOT}: {e}")
    for k, v in saved.items():
        settings.set(k, v)
    C.log("restored the settings this run changed")
    QTimer.singleShot(300, app.quit)
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
