#!/usr/bin/env python3
"""Drive the one-page colour summary (T1) in the real window, on screen.

Knut asked for a report a person can hand to a customer: one page, the run it
came from named on it, and the colours SHOWN rather than only counted. This
driver builds a verification measurement whose numbers are plausible (a printer
that is close but not perfect), opens the Measurement Report window, picks
"Colour summary (one page)" from the report-type pulldown, and checks the page
that comes back — then photographs the real window with ``screencapture``, not
``widget.grab()``, because a grab cannot show what the window server draws.

Sandbox the settings FIRST — this builds a real ``AppSettings``::

    export CHROMIQ_SETTINGS_FILE=/tmp/chromiq-onepage.ini
    .venv/bin/python scripts/drive_one_page_report.py [outdir]

It also points ``AppSettings._qs`` at its own throwaway .ini and pins
``custom_output_path`` inside the sandbox, so neither the real preferences nor
``~/ChromIQ`` can be reached even if the variable is forgotten.
"""
from __future__ import annotations

import os
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from PyQt6.QtCore import QSettings, QTimer                  # noqa: E402
from PyQt6.QtGui import QFontDatabase                       # noqa: E402
from PyQt6.QtWidgets import QApplication                    # noqa: E402

from core.resource_path import resource_path                # noqa: E402

FAILURES: list[str] = []


def check(what: str, ok: bool, detail: str = "") -> None:
    print(f"  {'OK  ' if ok else 'FAIL'} {what}" + (f"  ({detail})" if detail else ""))
    if not ok:
        FAILURES.append(what)


def pump(app, ms: int = 300) -> None:
    end = time.time() + ms / 1000.0
    while time.time() < end:
        app.processEvents()
        time.sleep(0.01)


# ----------------------------------------------------------------------
# A measurement worth photographing: real colours, close but not perfect.
#
# The chart has no .ti2, so the report's reference is the device RGB read as
# sRGB (the "device" yardstick). The measured XYZ is therefore built from the
# SAME model with a small, systematic error — a printer slightly dark and
# slightly warm — which is what a real one does, and what makes both swatch
# columns show colour instead of two identical blocks.
_GRID = [0, 25, 50, 75, 100]


def _srgb_to_xyz_d50(r: float, g: float, b: float) -> tuple:
    """Device 0..100 read as sRGB, in XYZ under D50, scaled 0..1."""
    from workflow.i1profiler_import import _patch_xyz
    from workflow.measurement_report import _bradford_d65_to_d50
    x, y, z = _patch_xyz(r, g, b)          # sRGB -> XYZ, D65, 0..100
    return _bradford_d65_to_d50(x, y, z)


def _measurement_ti3(path: Path) -> int:
    rows, n = [], 0
    for r in _GRID:
        for g in _GRID:
            for b in _GRID:
                n += 1
                x, y, z = _srgb_to_xyz_d50(r, g, b)
                # Slightly dark and slightly warm, as ink on paper is.
                x, y, z = x * 0.985 + 0.25, y * 0.975 + 0.20, z * 0.955 + 0.15
                # ARGYLL'S .ti3 CARRIES XYZ ON 0..100, not 0..1. Dividing by
                # 100 here made every measured colour a hundredth of its real
                # brightness: the swatches photographed as eight black blocks
                # and ΔE00 came out between 39 and 85 for a printer this
                # driver describes as close but not perfect.
                rows.append(f"{n} {r:.4f} {g:.4f} {b:.4f} "
                            f"{x:.6f} {y:.6f} {z:.6f}")
    path.write_text(
        "CTI3\n\n"
        'DESCRIPTOR "Argyll Calibration Target chart information 3"\n'
        'KEYWORD "DEVICE_CLASS"\n'
        'DEVICE_CLASS "OUTPUT"\n'
        'COLOR_REP "RGB_XYZ"\n\n'
        "NUMBER_OF_FIELDS 7\n"
        "BEGIN_DATA_FORMAT\n"
        "SAMPLE_ID RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z\n"
        "END_DATA_FORMAT\n\n"
        f"NUMBER_OF_SETS {n}\n"
        "BEGIN_DATA\n" + "\n".join(rows) + "\nEND_DATA\n",
        encoding="utf-8")
    return n


def _scroll_to(dlg, tr_free: str) -> bool:
    """Put *tr_free* near the top of the report view."""
    from PyQt6.QtGui import QTextCursor
    view = dlg._view
    view.moveCursor(QTextCursor.MoveOperation.Start)
    if not view.find(tr_free):
        return False
    c = view.textCursor()
    c.clearSelection()
    view.setTextCursor(c)
    bar = view.verticalScrollBar()
    bar.setValue(min(bar.maximum(), bar.value() + view.cursorRect().top() - 16))
    return True


def shot(win, out: Path, name: str) -> Path | None:
    """Photograph the REAL window. A grab is not a screenshot (CLAUDE.md), and
    a capture that cannot be PROVED to contain the window is not one either —
    see scripts/onscreen_capture.py, which was written after a locked screen
    handed this driver 4.4 MB of wallpaper that its own check accepted."""
    from scripts.onscreen_capture import capture_window
    p = out / name
    ok, why = capture_window(win, p)
    if not ok:
        print(f"       !! NO PHOTOGRAPH: {why}")
        return None
    print(f"       → {p}  ({p.stat().st_size} bytes)")
    return p


def main() -> int:
    out = Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/onepage-proof")
    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("ChromIQ")
    try:
        for fp in Path(resource_path("assets/fonts")).glob("*.ttf"):
            QFontDatabase.addApplicationFont(str(fp))
    except Exception:                                         # noqa: BLE001
        pass
    from ui import styles
    from ui.theme import apply_appearance
    app.setStyle(styles.WinButtonLayoutStyle("Fusion"))

    sandbox = Path(tempfile.mkdtemp(prefix="chromiq_onepage_"))
    work = sandbox / "working"
    work.mkdir()
    os.environ.setdefault("CHROMIQ_PRESETS_DIR", str(sandbox / "presets"))

    from core.file_manager import Project
    from core.settings import AppSettings
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    from workflow import measurement_report as mr

    settings = AppSettings()
    settings._qs = QSettings(str(sandbox / "drive.ini"),
                             QSettings.Format.IniFormat)
    settings.set("custom_output_path", str(work))
    settings.set("compliance_set_overrides", "")
    settings.set("compliance_default_set", "chromiq_default")

    # ONE APPEARANCE, SET ONCE AND READ BY BOTH. Two drivers' worth of false
    # findings came out of getting this wrong. Setting only APP_STYLESHEET
    # leaves the default LIGHT palette behind the dark sheet, and the report
    # type pulldown then draws #e6e6e6 text on a #ffffff base. Forcing the app
    # dark while the SETTING stays "auto" is the same mistake one level in: the
    # report body picks its own palette from the setting, so a light-mode
    # report gets painted onto a dark window and photographs as unreadable
    # text. Both look exactly like product faults and neither is one.
    appearance = os.environ.get("CHROMIQ_DRIVE_APPEARANCE", "dark")
    settings.set("appearance", appearance)
    apply_appearance(app, None, appearance)

    proj = Project.create(work / "HandOver", "HandOver")
    run = proj.current_run()
    run.ensure_dir()
    meta = run.load_meta()
    meta.description = "Hahnemuhle Photo Rag 308, job 4471"
    run.save_meta(meta)
    ti3 = run.dir / "HandOver.ti3"
    n = _measurement_ti3(ti3)
    print(f"\n== a {n}-patch measurement, close but not perfect ==")

    dlg = MeasurementReportDialog(settings, None, initial_ti3=ti3)
    dlg.resize(1180, 900)
    dlg.move(60, 60)
    dlg.show()
    dlg.raise_()
    dlg.activateWindow()
    pump(app, 1200)
    check("the window is on screen", dlg.isVisible(),
          str(dlg.frameGeometry().getRect()))

    combo = dlg._type_combo
    idx = combo.findData(mr.REPORT_TYPE_SUMMARY)
    check("the pulldown offers the one-page summary", idx >= 0)
    full = dlg._view.toPlainText()
    combo.setCurrentIndex(idx)
    pump(app, 900)
    text = dlg._view.toPlainText()

    check("the page is not the full report", text != full,
          f"{len(full)} chars -> {len(text)}")
    check("it names the run the user described",
          "Hahnemuhle Photo Rag 308, job 4471" in text)
    check("it shows example colours", "Example colours" in text)
    check("…with both swatch columns labelled",
          "Asked for" in text and "Measured" in text)
    check("it shows the cube corners", "Cube corners" in text)
    check("it says what ChromIQ does not do",
          "does not certify" in text)
    check("it is ONE page: no per-column table",
          "Rows checked" not in text and "Limit" not in text)
    from workflow.run_compliance import run_report_type
    check("the run stored the choice",
          run_report_type(run) == mr.REPORT_TYPE_SUMMARY,
          run_report_type(run))

    # The swatches must be COLOUR, not eight black blocks: the html carries a
    # background-color per swatch and they must not all be the same.
    html = dlg._view.toHtml()
    import re
    hexes = re.findall(r"background-color:\s*(#[0-9a-fA-F]{6})", html)
    check("the swatches carry real colours", len(set(hexes)) >= 8,
          f"{len(hexes)} swatches, {len(set(hexes))} distinct")

    p = shot(dlg, out, "01-one-page-summary.png")
    # THE COLOURS ARE THE POINT OF THIS PAGE, and they are below the fold. A
    # photograph of the scope block proves the window, not the document.
    _scroll_to(dlg, tr_free="Example colours")
    pump(app, 400)
    shot(dlg, out, "02-the-colours.png")
    if p is None:
        # Not a check: a photograph the window server will not give us is a
        # finding about the machine, not a failure of the page. The checks
        # above still measure the real widgets in a real window.
        print("  NOTE the page was measured in a real window; the PICTURE of "
              "it could not be taken (see above)")
    else:
        check("the photograph shows the window",
              p.stat().st_size > 20000, f"{p.stat().st_size} bytes")

    QTimer.singleShot(0, dlg.close)
    pump(app, 400)
    print(f"\n{'ALL CHECKS PASSED' if not FAILURES else 'FAILURES: ' + str(FAILURES)}")
    return 1 if FAILURES else 0


if __name__ == "__main__":
    raise SystemExit(main())
