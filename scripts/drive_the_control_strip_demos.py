#!/usr/bin/env python3
"""B8-393 / B8-405: drive the control-strip rows of the demo package on screen.

Knut, 2026-09-18, making it a condition of beta 22:

    *"Make sure to verify the feature and that the new demo package contains
    charts with control strips and that the associated metrics are tested,
    verified and limits tripped, as part of the demo projects package."*

`scripts/drive_b393_the_demo_package.py` drives every project of the pack and
checks every verdict word on every page. This one is narrower and deeper: it
opens the Measurement Report on the runs the control strip is about and asks,
for every dated column,

* **what word the three strip rows carry on the RENDERED PAGE**, against what
  the generator's `intended-vs-actual.json` says that date was built to
  produce. A row the data crossed must read FAIL or COND; a row the data
  judged and left inside must read PASS or INFO;
* **which sentence the page gives when a row has no word.** The three states
  ChromIQ can be in about a chart are `no_control_strip`,
  `control_strip_too_small` and a judged strip, and the package holds all
  three; a driver that only counted words could not tell the first two apart,
  and they send a reader to different places.

It photographs one window per state with `capture_window` (the CoreGraphics
window buffer), twice, and keeps the pair only when the two frames agree pixel
for pixel.

    CHROMIQ_SETTINGS_FILE=… CHROMIQ_PRESETS_DIR=… \\
        python scripts/drive_the_control_strip_demos.py <pack> <out>

`<pack>` is the built ChromIQ-Report-Limit-Demos folder. It is COPIED into a
temporary output root first, because opening a project migrates it in place.
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
sys.path.insert(0, str(ROOT / "scripts"))
try:
    import PyQt6.QtWebEngineWidgets  # noqa: F401
except ImportError:
    pass
from PyQt6.QtWidgets import QApplication, QDialog, QMessageBox   # noqa: E402
from onscreen_capture import capture_window, session_is_locked   # noqa: E402

from drive_b393_the_demo_package import (capture_settled,       # noqa: E402
                                         pump, read_grid)

#: The three rows this driver is about, by row id.
STRIP_ROWS = ("control_strip_de00_avg", "control_strip_de00_max",
              "control_strip_de00_p95")

#: A fragment of each reason sentence, short enough to survive a rewording of
#: the rest and specific enough that one cannot be read as the other. Taken
#: from `measurement_report_dialog._reason_sentence` and
#: `_control_strip_sentence`.
REASON_MARK = {
    "no_control_strip": "declares no control strip",
    "control_strip_too_small": "at least 20 for the 95th percentile",
}

#: Which runs of the pack this driver opens, and what each one is here to
#: show. Everything else in the pack is covered by the wider driver.
SUBJECTS = [
    ("Report-Limits-Strip-And-Gamut", "run1",
     "a full 29-rung strip, each of the three rows crossing on its own date"),
    ("Report-Limits-Strip-And-Gamut", "run4",
     "a chart ChromIQ REFUSES a strip for: all three rows say so"),
    ("Report-Limits-Border-Conditions", "run1",
     "a 20-patch chart: 8 rungs, so the average and the largest are judged "
     "and the 95th percentile is withheld"),
    ("Report-Limits-Profile-Gamut", "run2",
     "a FROM PROFILE GAMUT chart: 17 rungs, same split, on the one shipped "
     "column that numbers every row"),
    ("Report-Limits-Every-Limit-Set", "run1",
     "ChromIQ default, every row over on one date and inside on the next"),
    ("Report-Limits-Every-Limit-Set", "run3",
     "ChromIQ tight, the same pair"),
    ("Report-Limits-Every-Limit-Set", "run5",
     "Quick check, the same pair"),
    ("Report-Limits-Every-Limit-Set", "run7",
     "Custom ISO 12647-7, the same pair"),
    ("Report-Limits-Every-Limit-Set", "run9",
     "Custom ISO 12647-8, the same pair"),
]


def _scroll_to(dlg, needle: str) -> bool:
    """Put *needle* in view in the report page, so a photograph shows it.

    The page is a rich-text view; `find` moves its own cursor, and the view
    only scrolls when the cursor it is shown is the one that moved. Returns
    whether the text was found at all, so a photograph of the wrong part of
    the page is recorded as such rather than passed off as evidence.
    """
    view = dlg._view
    doc = view.document()
    cur = doc.find(needle, 0)
    if cur.isNull():
        return False
    view.setTextCursor(cur)
    view.ensureCursorVisible()
    # ensureCursorVisible only guarantees the line is IN the viewport, which on
    # this page put it on the last visible row with the two rows under it out
    # of frame. The three strip rows are consecutive, so the first of them is
    # pushed to just under the top of the pane and all three are in the
    # picture.
    rect = view.cursorRect()
    bar = view.verticalScrollBar()
    bar.setValue(max(bar.minimum(),
                     min(bar.maximum(), bar.value() + rect.top() - 24)))
    return True


def main() -> int:                                          # noqa: C901
    assert os.environ.get("CHROMIQ_SETTINGS_FILE"), "SANDBOX THE SETTINGS FIRST"
    assert os.environ.get("CHROMIQ_PRESETS_DIR"), "SANDBOX THE PRESETS FIRST"
    assert not os.environ.get("QT_QPA_PLATFORM"), "this DRIVER opens a window"
    pack, out = Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve()
    out.mkdir(parents=True, exist_ok=True)
    shots = out / "photographs"
    shots.mkdir(exist_ok=True)

    expected = {}
    for e in json.loads((pack / "intended-vs-actual.json").read_text("utf-8")):
        expected[(e["project"], e["run"], e["date"])] = e

    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("ChromIQ")
    from ui.styles import WinButtonLayoutStyle
    app.setStyle(WinButtonLayoutStyle("Fusion"))
    from core.settings import AppSettings
    work = Path(tempfile.mkdtemp(prefix="chromiq-strip-"))
    settings = AppSettings()
    settings.set("custom_output_path", str(work))
    settings.set("appearance", "dark")
    settings.set("language", "en")
    assert settings.get("custom_output_path", "") == str(work), "SANDBOX FAILED"
    for p in sorted(pack.glob("Report-Limits-*")):
        shutil.copytree(p, work / p.name)
    locked_at_start = session_is_locked()
    print(f"    pack copied to {work}", flush=True)
    print(f"    screen locked at start: {locked_at_start}", flush=True)

    QDialog.exec = lambda self: 1                     # type: ignore[assignment]
    for m in ("warning", "critical", "information", "question"):
        setattr(QMessageBox, m, staticmethod(lambda *a, **k: 0))
    from core.file_manager import FileManager
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    from ui.theme import apply_appearance
    MeasurementReportDialog._confirm = (                # type: ignore[assignment]
        lambda self, title, body: True)
    apply_appearance(app, None, "dark")
    fm = FileManager(settings)
    del fm

    from workflow.compliance_sets import ROWS
    id_of = {r.label: r.id for r in ROWS}
    label_of = {r.id: r.label for r in ROWS}

    results: list = []
    faults: list = []
    words_checked = 0
    for project, run_id, what in SUBJECTS:
        rdir = work / project / "runs" / run_id
        dates_on_disk = sorted(d for d in (rdir / "verifications").glob("*")
                               if d.is_dir() and sorted(d.glob("*.ti3")))
        if not dates_on_disk:
            faults.append(f"{project}/{run_id}: no dated verification on disk")
            continue
        ti3 = sorted(dates_on_disk[0].glob("*.ti3"))[0]
        dlg = MeasurementReportDialog(settings, None, initial_ti3=ti3)
        dlg.resize(1500, 1060)
        dlg.show()
        dlg.raise_()
        dlg.activateWindow()
        pump(app, 2600)
        text = dlg._view.toPlainText()
        dates, grid = read_grid(text)
        entry: dict = {
            "project": project, "run": run_id, "what": what,
            "visible": bool(dlg.isVisible()),
            "judged_against": dlg._set_combo.currentText(),
            "dates_on_page": dates,
            "strip_rows_on_page": [label_of[r] for r in STRIP_ROWS
                                   if label_of[r] in grid],
            "cells": [],
            "reasons_on_page": sorted(
                k for k, mark in REASON_MARK.items() if mark in text),
        }
        if not dlg.isVisible():
            faults.append(f"{project}/{run_id}: the window did not open")

        # A STRIP ROW THIS RUN'S COLUMN NUMBERS MUST BE ON THE PAGE, with its
        # word or with its reason. A row the column does NOT number and the
        # chart cannot supply carries neither, and the window does not draw it
        # (CH-20): measured here on Border-Conditions/run1, where a stock
        # ChromIQ column leaves the strip rows unnumbered, the 20-patch chart
        # supplies the average and the largest, and the 95th percentile is
        # drawn nowhere — so the `control_strip_too_small` sentence reaches no
        # reader on that page. That is the app behaving as ruled, not a fault,
        # and it is why the package shows that sentence on Profile-Gamut/run2,
        # whose column numbers all three.
        numbered = set()
        for key in expected:
            if key[0] == project and key[1] == run_id:
                numbered |= set(expected[key]["values"])
                numbered |= set(expected[key].get("shown_reasons") or {})
        entry["rows_this_column_numbers"] = sorted(
            r for r in STRIP_ROWS if r in numbered)
        for rid in entry["rows_this_column_numbers"]:
            if label_of[rid] not in grid:
                faults.append(
                    f"{project}/{run_id}: '{label_of[rid]}' is numbered by "
                    f"this run's column and is not on the page at all, so a "
                    f"reader is never told what the chart could or could not "
                    f"supply")

        for date_txt in dates:
            key = next((k for k in expected
                        if k[0] == project and k[1] == run_id
                        and k[2].startswith(date_txt)), None)
            if key is None:
                continue
            exp = expected[key]
            over, judged = set(exp["actual"]), set(exp["values"])
            for rid in STRIP_ROWS:
                word = grid.get(label_of[rid], {}).get(date_txt)
                if word is None:
                    continue
                words_checked += 1
                want = ("crossed" if rid in over else
                        "inside" if rid in judged else "no verdict")
                ok = ((want == "crossed" and word in ("FAIL", "COND"))
                      or (want == "inside" and word in ("PASS", "INFO"))
                      or (want == "no verdict" and word in ("N-A", "INFO")))
                entry["cells"].append({"date": date_txt, "row": rid,
                                       "word": word, "data_says": want,
                                       "agrees": bool(ok)})
                if not ok:
                    faults.append(
                        f"{project}/{run_id} {date_txt} {rid}: the window "
                        f"says {word} and the data was built to be {want}")
                # A ROW WITH NO WORD MUST CARRY A SENTENCE. Knut's rule for
                # every metric: the report says what the chart could not
                # supply rather than going quiet.
                if word == "N-A":
                    reason = (exp.get("shown_reasons") or {}).get(rid, "")
                    mark = REASON_MARK.get(reason)
                    if mark and mark not in text:
                        faults.append(
                            f"{project}/{run_id} {date_txt} {rid}: the row "
                            f"reads N-A and the page does not carry the "
                            f"{reason!r} sentence")

        # PHOTOGRAPH THE ROWS, NOT THE TOP OF THE PAGE. The verdict table is
        # well below the fold on a 1500x1060 window, and a picture of the
        # header proves the window opened and nothing else.
        entry["scrolled_to_the_strip_rows"] = _scroll_to(dlg, label_of[
            "control_strip_de00_avg"])
        pump(app, 600)

        a = shots / f"{project}-{run_id}.png"
        b = shots / f"{project}-{run_id}-again.png"
        ok, why, tries, same = capture_settled(app, dlg, a, b)
        entry["photograph"] = {"file": a.name, "taken": bool(ok),
                               "two_identical_frames": bool(same),
                               "attempts": tries, "why": why}
        if not (ok and same):
            faults.append(f"{project}/{run_id}: no settled photograph ({why})")
        else:
            b.unlink(missing_ok=True)
        results.append(entry)
        print(f"    {project}/{run_id}: {len(dates)} column(s), "
              f"{len(entry['cells'])} strip cell(s), reasons on page "
              f"{entry['reasons_on_page']}", flush=True)
        dlg.close()
        dlg.deleteLater()
        pump(app, 300)

    summary = {
        "pack": str(pack),
        "mode": "ON SCREEN (no QT_QPA_PLATFORM); capture_window, two frames",
        "screen_locked_at_start": bool(locked_at_start),
        "runs_driven": len(results),
        "strip_verdict_words_checked": words_checked,
        "faults": faults,
        "runs": results,
    }
    (out / "on-screen-control-strip.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8")
    print(f"\n    {len(results)} runs driven on screen, {words_checked} "
          f"control-strip verdict words read off the rendered page", flush=True)
    if faults:
        print(f"    {len(faults)} FAULT(S):", flush=True)
        for f in faults[:40]:
            print(f"      {f}", flush=True)
    else:
        print("    no faults", flush=True)
    shutil.rmtree(work, ignore_errors=True)
    return 1 if faults else 0


if __name__ == "__main__":
    raise SystemExit(main())
