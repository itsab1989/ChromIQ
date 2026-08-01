#!/usr/bin/env python3
"""Drive the REAL ChromIQ app to prove a restored chart comes back unchanged.

Knut, #130 (2026-07-28 and again 2026-08-01): *"every time I clicked restore a
new random sequence was shown in the preview"*. A chart shown from a run already
has its final patch order in the ``.ti2`` — the shuffle happened when it was
first made — so rebuilding its pages must preserve that order.

Why this is a driver and not a unit test: three times in one day my unit-level
reasoning was right about the piece and wrong about the product. Restoring
"works" when the copy function is called directly; it did not work when Knut
pressed the button. This walks the same path he does.

The assertion needs no judgement: hash the page images, restore, let the chart
rebuild, hash again. **Identical bytes = the order survived. Different = the
bug.**

    QT_QPA_PLATFORM=offscreen python scripts/drive_restore_seed.py
    CHROMIQ_DRIVE_ONSCREEN=1 python scripts/drive_restore_seed.py   # watch it
"""
from __future__ import annotations

import hashlib
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

ONSCREEN = bool(os.environ.get("CHROMIQ_DRIVE_ONSCREEN"))
if not ONSCREEN:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

# QtWebEngine must be imported before the QApplication exists (#38).
try:
    from PyQt6 import QtWebEngineWidgets  # noqa: F401
except Exception:
    pass

from PyQt6.QtCore import QSettings                                  # noqa: E402
from PyQt6.QtGui import QFontDatabase                               # noqa: E402
from PyQt6.QtWidgets import QApplication, QDialog, QMessageBox      # noqa: E402

from core.resource_path import resource_path                        # noqa: E402
from core.settings import AppSettings                               # noqa: E402


def pump(app, ms=300):
    end = time.time() + ms / 1000.0
    while time.time() < end:
        app.processEvents()
        time.sleep(0.01)


def digests(run_dir: Path) -> dict:
    """Hash the chart's page images — the thing the user actually looks at."""
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest()[:16]
            for p in sorted(run_dir.glob("*.tif"))}


def main(project_zip_dir: Path) -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("ChromIQ")
    try:
        for fp in resource_path("assets/fonts").glob("*.ttf"):
            QFontDatabase.addApplicationFont(str(fp))
    except Exception:
        pass

    sandbox = Path(tempfile.mkdtemp(prefix="chromiq-restore-"))
    root = sandbox / "ChromIQ"
    root.mkdir()
    shutil.copytree(project_zip_dir, root / project_zip_dir.name)

    settings = AppSettings()
    settings._qs = QSettings(str(sandbox / "s.ini"), QSettings.Format.IniFormat)
    settings.set("custom_output_path", str(root))

    # Never block on a modal: this run has nobody to click.
    QDialog.exec = lambda self: 0                       # type: ignore[assignment]
    for m in ("warning", "critical", "information", "question"):
        setattr(QMessageBox, m, staticmethod(lambda *a, **k: 0))

    from ui.main_window import MainWindow
    win = MainWindow(settings)
    if ONSCREEN:
        win.show()
    pump(app, 600)

    tab_chart = win._tab_chart
    proj_dir = root / project_zip_dir.name
    manifest = proj_dir / "project.json"
    if not manifest.is_file():
        print(f"FAIL  no project.json in {proj_dir}")
        return 2

    # Drive the real "Open a printer profile" path by answering its file
    # dialog, rather than reaching for a helper that may not exist. An earlier
    # version guarded this with hasattr and silently skipped it — the run then
    # reported success having tested nothing, which is worse than a failure.
    import ui.tabs.tab_chart as TC
    TC.open_file_dialog = lambda *a, **k: str(manifest)
    tab_chart._load_existing_profile()
    pump(app, 900)

    ctl = getattr(win._tab_measure, "_target_ctl", None)
    if ctl is None:
        print("FAIL  no target controller")
        return 2

    proj = ctl.project_or_none()
    if proj is None:
        print("FAIL  the project did not load — nothing was tested")
        return 2
    runs = proj.all_runs()
    if not runs:
        print("FAIL  the project loaded but has no runs — nothing was tested")
        return 2
    print(f"loaded {proj.root.name}: {len(runs)} run(s)")

    failures = checked = 0
    for run in runs:
        run_id = run.id
        if not list(run.dir.glob("*.tif")):
            continue                       # nothing rendered to compare
        ctl.set_run_type("Profiling")
        ctl.set_profile_run(run_id)
        pump(app, 500)
        before = digests(run.dir)
        # Restore is (correctly, since beta.117) greyed when the live chart
        # already matches the stored one — so there would be nothing to test.
        # Perturb the live .ti2 the way a user does by regenerating: the stored
        # copy is untouched, so Restore lights up and has real work to do. The
        # question then is whether what comes back is the SAME chart.
        live_ti2 = next(iter(sorted(run.dir.glob("*.ti2"))), None)
        if live_ti2 is None:
            print(f"skip  {run_id}: no .ti2 to perturb")
            continue
        keep = live_ti2.read_bytes()
        live_ti2.write_bytes(keep + b"\n# perturbed by drive_restore_seed\n")
        ctl.set_profile_run(run_id)          # re-evaluate the button
        pump(app, 400)
        enabled, tip = ctl.restore_state()
        if not enabled:
            live_ti2.write_bytes(keep)
            print(f"skip  {run_id}: Restore still greyed after a real change "
                  f"— that is itself suspect: {tip}")
            continue
        ctl.restore_used_chart()
        pump(app, 900)
        after = digests(run.dir)
        # Is a rebuild even deterministic? A TIFF encoder that stamps a
        # creation time would change every byte regardless of patch order, and
        # then comparing bytes proves nothing. Restore a SECOND time and compare
        # the two rebuilds with each other: identical means the only variable
        # left is the layout, so a before/after difference is real.
        live_ti2.write_bytes(live_ti2.read_bytes() + b"\n# again\n")
        ctl.set_profile_run(run_id)
        pump(app, 300)
        if ctl.restore_state()[0]:
            ctl.restore_used_chart()
            pump(app, 900)
        after2 = digests(run.dir)
        if after != after2:
            print(f"NOTE  {run_id}: two rebuilds differ from EACH OTHER — the "
                  f"output is not byte-deterministic, so a byte comparison "
                  f"cannot prove patch order. Test is invalid for this chart.")
            continue
        same = before == after
        print(f"{'PASS' if same else 'FAIL'}  {run_id}: "
              f"{len(before)} page image(s), "
              f"{'identical after restore' if same else 'CHANGED after restore'}")
        checked += 1
        if not same:
            failures += 1
            for k in sorted(set(before) | set(after)):
                if before.get(k) != after.get(k):
                    print(f"      {k}: {before.get(k)} -> {after.get(k)}")

    shutil.rmtree(sandbox, ignore_errors=True)
    if checked == 0:
        print("\nRESULT: NOTHING WAS TESTED — no run had both page images and an "
              "enabled Restore button. Do not read this as a pass.")
        return 2
    print(f"\nRESULT: {checked} run(s) checked — "
          + ("every restore reproduced its chart" if not failures
             else f"{failures} came back with a DIFFERENT chart"))
    return 1 if failures else 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        print("usage: drive_restore_seed.py <unpacked-project-dir>")
        raise SystemExit(2)
    raise SystemExit(main(Path(sys.argv[1])))
