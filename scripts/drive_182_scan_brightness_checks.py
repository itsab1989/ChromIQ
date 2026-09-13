#!/usr/bin/env python3
"""Drive the REAL *Build profile with scanner or camera* window, printer mode,
and photograph the brightness warning appearing and not appearing.

#182, 2026-09-13. With **"Profile my printer from this scan"** ticked, ``scanin
-c`` writes a ``.ti3`` whose ``RGB_*`` are the CHART's device values, so the two
checks that ask about the scan's exposure were answering about the chart: the
clipped share never moved with the scan (23.3 % for both of the CR30 pack's two
scans, which differ only in brightness) and the too-dark check could never fire.
The window now reads the scan's own device values back with a second
``scanin -o`` pass (:mod:`workflow.scan_device_values`).

This drives that, on screen, in a real window, through the window's own
**Check alignment** button, on the pack's two scans one after the other. The
in-range one must come back with no brightness warning and the out-of-scale one
must raise it, and both windows are photographed with
``scripts/onscreen_capture``, which wakes a locked screen, takes the window's
own buffer rather than a rectangle of the desktop, and refuses rather than
hand back wallpaper.

Nothing is asserted from a ``widget.grab()``. Nothing is asserted from the
checks either: the numbers printed at the end are read off the window's own
verdict lines.

The settings are sandboxed to a throwaway ``.ini`` and the presets to a
throwaway folder, so this cannot reach the preferences Basti works in. Check
afterwards with::

    defaults read com.chromiq.ChromIQ custom_output_path

Usage::

    CHROMIQ_SETTINGS_FILE=/tmp/chromiq-scanbright.ini \\
    CHROMIQ_PRESETS_DIR=/tmp/chromiq-scanbright-presets \\
        python scripts/drive_182_scan_brightness_checks.py <pack-dir> <out-dir>
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

try:
    import PyQt6.QtWebEngineWidgets  # noqa: F401
except ImportError:
    pass

from PyQt6.QtWidgets import QApplication, QDialog       # noqa: E402

from scripts.onscreen_capture import (                  # noqa: E402
    capture_window, session_is_locked, wake_the_screen,
)

ARGYLL = Path(os.environ.get("CHROMIQ_ARGYLL_BIN", "/Applications/Argyll/bin"))
SRGB = ARGYLL.parent / "ref" / "sRGB.icm"
STEM = "testHex"


DISMISSED: list[str] = []


def _dismiss_modals() -> None:
    """Click OK on any modal the app raises, the way a user would.

    Loading this chart raises the app's own **"Hexagonal chart"** notice, and a
    driver that ignores it simply STOPS: ``QMessageBox.exec`` runs its own
    event loop and never returns, so the script sits at 0 % CPU for ever and
    the modal waits on screen for whoever walks past. That has happened on this
    project before and the person who clicked it was Basti.

    A repeating timer is used rather than patching ``QDialog.exec``, because
    patching it would change the behaviour under test: the modal really does
    appear, it is really dismissed, and what it was is recorded.
    """
    from PyQt6.QtWidgets import QApplication, QMessageBox
    w = QApplication.activeModalWidget()
    if w is None:
        return
    DISMISSED.append(f"{type(w).__name__}: {w.windowTitle()!r} "
                     f"{getattr(w, 'text', lambda: '')()[:90]!r}")
    if isinstance(w, QMessageBox):
        w.accept()
    else:
        w.close()


def arm_dismisser(app):
    from PyQt6.QtCore import QTimer
    t = QTimer()
    t.setInterval(120)
    t.timeout.connect(_dismiss_modals)
    t.start()
    return t


def pump(app, ms: int) -> None:
    end = time.monotonic() + ms / 1000.0
    while time.monotonic() < end:
        app.processEvents()
        time.sleep(0.01)


def wait_for(app, predicate, timeout: float = 240.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        app.processEvents()
        got = predicate()
        if got:
            return got
        time.sleep(0.05)
    return None


def result_windows() -> list[QDialog]:
    """Every open *Alignment check* window, newest last."""
    return [w for w in QApplication.topLevelWidgets()
            if isinstance(w, QDialog) and w.isVisible()
            and "Alignment check" in w.windowTitle()]


def verdict_lines(dlg: QDialog) -> list[str]:
    from PyQt6.QtWidgets import QLabel
    return [l.text() for l in dlg.findChildren(QLabel)
            if l.text() and len(l.text()) > 3]


def stage(pack: Path, work: Path) -> Path:
    """The pack's chart, plus the recognition files the window would have been
    given by *Create scanner or camera target*, in one sandbox folder."""
    from workflow.scanin_target import build_scanin_target_from_paths
    work.mkdir(parents=True, exist_ok=True)
    for name in (f"{STEM}.ti3", f"{STEM}.ti2", f"{STEM}.channels.json",
                 f"{STEM}.ti1"):
        shutil.copy2(pack / "chart" / name, work / name)
    build_scanin_target_from_paths(work / f"{STEM}.channels.json",
                                   work / f"{STEM}.ti3", work / STEM)
    return work / f"{STEM}.ti3"


def corners_for(pack: Path, work: Path, page: int):
    """Where page *page*'s patch block landed in its scan.

    Taken from the generator, which is the code that made the scan, so the
    corners are the ones a user would place by hand if they placed them
    exactly. Nothing about the check under test depends on them being perfect,
    only on both passes using the SAME ones, which they do by construction.
    """
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "mk", ROOT / "scripts" / "make_cr30_hex_demo.py")
    mk = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mk)
    return mk.corners_for_page(work / f"{STEM}_{page:02d}.cht",
                               pack / "chart" / f"{STEM}_{page:02d}.tif")


def main() -> int:
    pack = Path(sys.argv[1]).resolve()
    out = Path(sys.argv[2]).resolve() if len(sys.argv) > 2 else \
        Path("/tmp/chromiq-scanbright-proof")
    out.mkdir(parents=True, exist_ok=True)
    if not os.environ.get("CHROMIQ_SETTINGS_FILE"):
        print("REFUSING: set CHROMIQ_SETTINGS_FILE first; this driver builds a "
              "real AppSettings and would write into the real preferences.")
        return 2
    if not SRGB.is_file():
        print(f"REFUSING: no scanner ICC at {SRGB}; printer mode needs one.")
        return 2

    locked = session_is_locked()
    woke = ""
    if locked:
        ok, why = wake_the_screen()
        woke = f"screen was LOCKED; wake {'cleared it' if ok else 'FAILED: ' + why}"
        print(woke)

    app = QApplication.instance() or QApplication(sys.argv)
    _keep_alive = arm_dismisser(app)
    from core.argyll_runner import ArgyllRunner
    from core.settings import AppSettings
    from ui.dialogs.scanin_dialog import ScannerProfileDialog

    settings = AppSettings()
    work = out / "work"
    shutil.rmtree(work, ignore_errors=True)
    ti3 = stage(pack, work)

    runner = ArgyllRunner(settings)
    dlg = ScannerProfileDialog(runner, settings, None)
    dlg.show()
    dlg.resize(1180, 900)
    pump(app, 900)

    # The window in the state a user reaches by loading this chart and ticking
    # the box: a ChromIQ chart (not a standard target), printer mode, a scanner
    # ICC to convert through.
    dlg._ti3 = ti3
    dlg._pages = [0, 1]
    dlg._printer_cb.setChecked(True)
    dlg._printer_scan_profile = SRGB
    pump(app, 400)
    print(f"printer mode on: {dlg._printer_mode()}   "
          f"standard mode: {dlg._standard_mode()}")

    corners = corners_for(pack, work, 1)
    findings = {}

    for tag, scan_name in (("in-range", f"{STEM}_01-scan.tif"),
                           ("out-of-scale", f"{STEM}_01-scan-out-of-scale.tif")):
        scan = pack / "scan" / scan_name
        dlg._page = 0
        dlg._shot_idx = 0
        dlg._shots[0] = [{"path": scan, "corners": [tuple(c) for c in corners]}]
        pump(app, 300)
        print(f"\n=== {tag}: {scan.name} ===")
        before = len(result_windows())
        dlg._on_check_alignment()
        got = wait_for(app, lambda: (result_windows()[-1]
                                     if len(result_windows()) > before else None))
        if got is None:
            print(f"  {tag}: no alignment-check window appeared")
            findings[tag] = None
            continue
        pump(app, 700)
        lines = verdict_lines(got)
        findings[tag] = lines
        for l in lines:
            print("   |", l)
        shot = out / f"{'03' if tag == 'in-range' else '04'}-{tag}-checked.png"
        ok, why = capture_window(got, shot)
        print(f"  photograph: {'OK ' + shot.name if ok else 'REFUSED: ' + why}")
        got.close()
        pump(app, 400)

    # The window itself, with the box ticked, so the mode is on the record.
    ok, why = capture_window(dlg, out / "02-scanner-window-printer-mode.png")
    print(f"\nwindow photograph: {'OK' if ok else 'REFUSED: ' + why}")

    print(f"\nmodals the app raised and this driver clicked OK on: "
          f"{DISMISSED or 'none'}")
    (out / "verdicts.json").write_text(json.dumps(
        {"locked_at_start": locked, "wake": woke, "findings": findings,
         "modals_dismissed": DISMISSED}, indent=2, ensure_ascii=False),
        encoding="utf-8")

    dlg.close()
    pump(app, 300)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
