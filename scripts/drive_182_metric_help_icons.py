#!/usr/bin/env python3
"""Knut's per-metric help icons, in the REAL Report limits window.

Knut, 2026-09-14::

    In report limits window (Edit limits button) the first column is a name for
    each metric. Right aligned to the end of each metric name, add an info help
    icon, where each help icon describes the metric for that line and details
    the conditions used to detect if a chart contains the patches needed to
    assess and judge this metric. If any metric is missing a detection method
    for checking if a chart used for verification contains needed patches, then
    this detection method must be determined and specified.

This opens the window on a real project, records every row's icon and the text
behind it, photographs the window, and then opens three of the info dialogs so
the text can be READ on screen rather than inferred from the source: one row
that ChromIQ judges, one it cannot judge without the right chart, and one it
does not judge at all.

The info dialog is modal (`TooltipButton._show_dialog` calls `exec`), so it is
opened here by building the same dialog and SHOWING it, which is the same
widget with the same text and never blocks. The driver says so rather than
pretending it clicked.

Run it::

    CHROMIQ_SETTINGS_FILE=/tmp/chromiq-help.ini \\
    CHROMIQ_PRESETS_DIR=/tmp/chromiq-help-presets \\
        python scripts/drive_182_metric_help_icons.py <pack> <out-dir>

Never set QT_QPA_PLATFORM=offscreen for this. It is a driver, not a test.
"""
from __future__ import annotations

import json
import os
import shutil
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

from PyQt6.QtWidgets import QApplication, QDialog, QMessageBox   # noqa: E402

sys.path.insert(0, str(ROOT / "scripts"))                        # noqa: E402
from onscreen_capture import capture_window, session_is_locked   # noqa: E402

PROJECT = "Report-Limits-Report-Types"
RUN = "run1"
#: One row ChromIQ judges, one it can judge only with the right chart, and one
#: it does not judge at all.
SHOW = ("all_de00_avg", "substrate_de00_max", "control_strip_de00_avg")


def pump(app, ms: int = 300) -> None:
    end = time.monotonic() + ms / 1000.0
    while time.monotonic() < end:
        app.processEvents()
        time.sleep(0.01)


def main() -> int:
    assert os.environ.get("CHROMIQ_SETTINGS_FILE"), "SANDBOX THE SETTINGS FIRST"
    assert os.environ.get("CHROMIQ_PRESETS_DIR"), "SANDBOX THE PRESETS FIRST"
    pack = Path(sys.argv[1]).resolve()
    out = Path(sys.argv[2]).resolve()
    out.mkdir(parents=True, exist_ok=True)

    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("ChromIQ")
    from ui.styles import WinButtonLayoutStyle
    app.setStyle(WinButtonLayoutStyle("Fusion"))

    from core.settings import AppSettings
    work = Path(tempfile.mkdtemp(prefix="chromiq-help-"))
    settings = AppSettings()
    settings.set("custom_output_path", str(work))
    settings.set("appearance", "dark")
    assert settings.get("custom_output_path", "") == str(work), "SANDBOX FAILED"
    print(f"    sandbox: {work}", flush=True)

    src = pack / PROJECT
    assert src.is_dir(), f"no {PROJECT} in {pack}"
    shutil.copytree(src, work / src.name)

    # A DIALOG THAT BLOCKS IS A DIALOG BASTI CLICKS.
    QDialog.exec = lambda self: 1                     # type: ignore[assignment]
    for m in ("warning", "critical", "information", "question"):
        setattr(QMessageBox, m, staticmethod(lambda *a, **k: 0))

    from core.file_manager import FileManager
    from core.i18n import tr
    from ui.theme import apply_appearance
    from ui.dialogs.thresholds_dialog import ThresholdsDialog
    from ui.tooltip_button import TooltipButton, _InfoDialog
    from workflow import compliance_sets as cs
    apply_appearance(app, None, "dark")
    fm = FileManager(settings)
    del fm

    td = ThresholdsDialog(settings, None)
    td.resize(1500, 1000)
    td.show()
    td.raise_()
    pump(app, 1800)
    print(f"    limits window on screen: {td.isVisible()} "
          f"{td.frameGeometry().width()}x{td.frameGeometry().height()}",
          flush=True)

    # WHICH ROWS CARRY AN ICON, AND WHERE IT SITS.
    g = td._grid
    rows: list = []
    xs: list = []
    for i in range(g.count()):
        item = g.itemAt(i)
        w = item.widget() if item else None
        if w is None or isinstance(w, TooltipButton):
            continue
        kids = w.findChildren(TooltipButton)
        r, c, _rs, _cs = g.getItemPosition(i)
        if len(kids) == 1 and c == 0:
            xs.append(kids[0].pos().x())
    print(f"    rows with an icon in the name column: {len(xs)} "
          f"of {len(cs.ROWS)}; they sit at x={sorted(set(xs))}", flush=True)

    for row in cs.ROWS:
        body = td._row_help(row)
        rows.append({
            "id": row.id, "status": row.status,
            "label": tr(row.label),
            "has_blurb": bool(row.blurb),
            "has_detect": bool(row.detect),
            "help_chars": len(body),
            "help_starts": body[:90],
            "names_a_condition": bool(row.detect) or bool(row.note),
        })

    shot = out / "01-limits-window-with-icons.png"
    ok, why = capture_window(td, shot)
    print(f"    photo: {'ok' if ok else 'REFUSED: ' + str(why)}", flush=True)

    # THREE OF THE INFO DIALOGS, SHOWN RATHER THAN EXEC'D.
    shots = {}
    for rid in SHOW:
        row = next(r for r in cs.ROWS if r.id == rid)
        d = _InfoDialog(tr(row.label), td._row_help(row), td, 460)
        d.show()
        d.raise_()
        pump(app, 1200)
        p = out / f"02-info-{rid}.png"
        ok2, why2 = capture_window(d, p)
        shots[rid] = p.name if ok2 else f"REFUSED: {why2}"
        print(f"    info dialog {rid}: "
              f"{'ok' if ok2 else 'REFUSED: ' + str(why2)}", flush=True)
        d.close()
        pump(app, 300)

    judgeable = [r for r in cs.ROWS
                 if r.status not in ("unmeasurable", "unknown")]
    verdicts = {
        "every row carries an icon": len(xs) == len(cs.ROWS),
        "every judgeable row tells the reader what to do": all(
            r.remedy for r in judgeable),
        "no row that cannot be judged offers advice": not [
            r for r in cs.ROWS if r.remedy and r.status in (
                "unmeasurable", "unknown")],
        "the icons line up in one column": len(set(xs)) == 1 and xs[0] > 0,
        "every row says what it measures": all(r["has_blurb"] for r in rows),
        "every row says how it is detected, or why it is not":
            all(r["names_a_condition"] for r in rows),
        "no help text is a stub": all(r["help_chars"] > 120 for r in rows),
    }
    (out / "metric-help-icons.json").write_text(
        json.dumps({"photo": shot.name if ok else f"REFUSED: {why}",
                    "info_dialogs": shots, "icon_x": sorted(set(xs)),
                    "rows": rows, "verdicts": verdicts}, indent=2),
        encoding="utf-8")
    print(json.dumps(verdicts, indent=2), flush=True)
    print(f"    screen locked at start: {session_is_locked()}", flush=True)
    td.close()
    pump(app, 400)
    return 0 if all(verdicts.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
