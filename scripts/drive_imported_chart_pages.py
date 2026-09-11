#!/usr/bin/env python3
"""Import a chart file on its own, on screen, and check the run can be printed.

Knut asked for every path that loads or builds a chart to be checked. The audit
found that importing a `.ti2` with no page bitmaps beside it made a run with a
chart, no pages, an empty preview and nothing in the Print tab saying why. He
then chose the fix (#182, 2026-09-11): *"Rebuild only the missing pages, from
the recipe the file itself carries … A chart you have already printed still
reprints exactly as it was."*

This drives the real import through its real dialog, in a real window, and
looks at what the run ends up holding. Nothing is stubbed but the file chooser,
which has no bearing on what the import does with the file it is given.

Sandbox the settings FIRST — this builds a real `AppSettings`::

    export CHROMIQ_SETTINGS_FILE=/tmp/chromiq-import.ini
    .venv/bin/python scripts/drive_imported_chart_pages.py [outdir]
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from PyQt6.QtCore import QSettings, QTimer                  # noqa: E402
from PyQt6.QtWidgets import (QApplication, QMessageBox,     # noqa: E402
                             QPushButton)

FAILURES: list[str] = []
ARGYLL = Path("/Applications/Argyll/bin")


def check(what: str, ok: bool, detail: str = "") -> None:
    print(f"  {'OK  ' if ok else 'FAIL'} {what}" + (f"  ({detail})" if detail else ""))
    if not ok:
        FAILURES.append(what)


def pump(app, ms: int = 300) -> None:
    end = time.time() + ms / 1000.0
    while time.time() < end:
        app.processEvents()
        time.sleep(0.01)


def _a_real_chart(into: Path) -> Path:
    """A 60-patch chart built by the real Argyll tools."""
    into.mkdir(parents=True, exist_ok=True)
    subprocess.run([str(ARGYLL / "targen"), "-d2", "-f60", "real"],
                   cwd=into, check=True, capture_output=True, timeout=120)
    subprocess.run([str(ARGYLL / "printtarg"), "-ii1", "-pA4", "-t300", "real"],
                   cwd=into, check=True, capture_output=True, timeout=120)
    return into / "real.ti2"


def _click(app, label_part: str, tries: int = 60) -> bool:
    """Press the button whose text contains *label_part* in whatever modal is
    up. A driver that BLOCKS on a modal gets clicked by a person, and every
    result after that point is worthless (CLAUDE.md)."""
    for _ in range(tries):
        app.processEvents()
        for w in app.topLevelWidgets():
            if isinstance(w, QMessageBox) and w.isVisible():
                for b in w.findChildren(QPushButton):
                    if label_part.lower() in b.text().lower().replace("&", ""):
                        b.click()
                        return True
        time.sleep(0.05)
    return False


def main() -> int:
    out = Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/import-proof")
    if not (ARGYLL / "printtarg").exists():
        print("!! no ArgyllCMS on this machine; nothing was driven")
        return 1
    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("ChromIQ")
    from ui import styles
    from ui.theme import apply_appearance
    app.setStyle(styles.WinButtonLayoutStyle("Fusion"))

    sandbox = Path(tempfile.mkdtemp(prefix="chromiq_import_"))
    work = sandbox / "working"
    work.mkdir()
    os.environ.setdefault("CHROMIQ_PRESETS_DIR", str(sandbox / "presets"))

    from core.file_manager import Project
    from core.settings import AppSettings
    settings = AppSettings()
    settings._qs = QSettings(str(sandbox / "drive.ini"),
                             QSettings.Format.IniFormat)
    settings.set("custom_output_path", str(work))
    settings.set("appearance", "dark")
    apply_appearance(app, None, "dark")

    # The chart arrives ALONE, which is the shape the audit found.
    src = _a_real_chart(sandbox / "src")
    lone = sandbox / "loose" / "Imported.ti2"
    lone.parent.mkdir(parents=True, exist_ok=True)
    lone.write_bytes(src.read_bytes())
    print(f"\n== a chart file on its own: {lone.name}, "
          f"{len(list(lone.parent.iterdir()))} file in its folder ==")

    proj = Project.create(work / "Target", "Target")
    from core.file_manager import FileManager
    fm = FileManager(settings)
    fm.set_target_name("Target")
    from ui.measurement_target_bar import MeasurementTargetController
    ctl = MeasurementTargetController(fm)

    from ui.main_window import MainWindow
    win = MainWindow(settings)
    win.resize(1500, 1000)
    win.show()
    win.raise_()
    pump(app, 1200)
    check("the app is on screen", win.isVisible(),
          str(win.frameGeometry().getRect()))

    from ui.ti2_loader import resolve_ti2
    result: list = []
    QTimer.singleShot(400, lambda: _click(app, "Import as a new run"))
    result.append(resolve_ti2(win, lone, settings, ctl))
    pump(app, 600)

    check("the import returned a chart", result[0] is not None)
    if result[0] is None:
        return 1
    ti2, tiffs = result[0]
    check("the chart landed inside the project", str(work) in str(ti2), str(ti2))

    # WHAT THE WINDOWS ARE HANDED, not only what is on disk. `resolve_ti2`
    # returns the pages it found beside the imported chart, and that list is
    # what the Measure tab passes on to Create Chart and Print Chart. An empty
    # list here is an empty preview and a Print tab with nothing in it, which
    # is the fault this change exists to remove.
    check("the loader handed the windows a list of pages", bool(tiffs),
          ", ".join(Path(t).name for t in (tiffs or [])) or "none")

    from workflow.chart_import import chart_page_tiffs
    pages = chart_page_tiffs(Path(ti2))
    check("the imported run HAS printable pages", bool(pages),
          ", ".join(p.name for p in pages) or "none")
    check("…and every page is a real bitmap",
          all(p.stat().st_size > 1000 for p in pages))
    check("the chart file itself is byte for byte what was imported",
          Path(ti2).read_bytes() == lone.read_bytes())

    from workflow.ti2_relayout import ChartSpec
    a = [(p.loc, p.dev) for p in ChartSpec.from_ti2(lone).patches]
    b = [(p.loc, p.dev) for p in ChartSpec.from_ti2(Path(ti2)).patches]
    check("every patch is where the imported file says it is", a == b,
          f"{len(a)} patches")

    check("the patch set was written beside the chart",
          Path(ti2).with_suffix(".ti1").is_file())

    from scripts.onscreen_capture import capture_window
    ok, why = capture_window(win, out / "01-imported-run.png")
    if not ok:
        print(f"       !! NO PHOTOGRAPH: {why}")
    else:
        print(f"       → {out / '01-imported-run.png'}")

    QTimer.singleShot(0, win.close)
    pump(app, 400)
    print(f"\n{'ALL CHECKS PASSED' if not FAILURES else 'FAILURES: ' + str(FAILURES)}")
    return 1 if FAILURES else 0


if __name__ == "__main__":
    raise SystemExit(main())
