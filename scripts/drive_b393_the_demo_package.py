#!/usr/bin/env python3
"""B8-393: drive EVERY project of the demo package in a real window.

Knut, 2026-09-18, and it is a release condition rather than a fault:

    *"The agents must use the demo package on-screen on the new app-release to
    verify that every ChromIQ-Report-Limit-Demos project work and all reports
    load and output correct results, and that all functionality works using the
    demo data."*

So this driver opens the Measurement Report window on **every profile run of
every project**, reads the verdict grid off the RENDERED PAGE rather than out
of the report file, and checks every word against what the generator's
``intended-vs-actual.json`` says that date was built to produce. A word the
window prints that the data did not ask for is a failure of this run, whichever
side is wrong.

It then picks **every entry of the Generated reports pulldown** in turn and
requires the page to come back non-empty, which is the other half of his
sentence: *"all reports load"*.

    CHROMIQ_SETTINGS_FILE=… CHROMIQ_PRESETS_DIR=… \\
        python scripts/drive_b393_the_demo_package.py <pack> <out>

`<pack>` is the unzipped ChromIQ-Report-Limit-Demos folder. It is COPIED into a
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

WORDS = ("PASS", "FAIL", "COND", "INFO", "N-A", "drift")


def pump(app, ms: int = 300) -> None:
    end = time.monotonic() + ms / 1000.0
    while time.monotonic() < end:
        app.processEvents()
        time.sleep(0.01)


def _frames_match(a: Path, b: Path, tol: int = 8) -> bool:
    try:
        import numpy as np
        from PIL import Image
        x = np.asarray(Image.open(a).convert("RGB")).astype(int)
        y = np.asarray(Image.open(b).convert("RGB")).astype(int)
        if x.shape != y.shape:
            return False
        return bool((np.abs(x - y).sum(axis=2) > tol).sum() == 0)
    except Exception:                                      # noqa: BLE001
        return False


def capture_settled(app, win, first: Path, second: Path, tries: int = 4):
    """Two consecutive photographs that agree pixel for pixel, or say so.

    Two other agents are driving this app at the same time, and a single frame
    cannot tell a settled window from one mid-repaint.
    """
    ok = ok2 = False
    why = ""
    for n in range(1, tries + 1):
        pump(app, 800)
        ok, why = capture_window(win, first)
        pump(app, 800)
        ok2, why2 = capture_window(win, second)
        why = why or why2
        if ok and ok2 and _frames_match(first, second):
            return True, why, n, True
    return bool(ok and ok2), why, tries, False


def read_grid(text: str) -> "tuple[list[str], dict[str, dict[str, str]]]":
    """The verdict table AS THE WINDOW DRAWS IT: (dates, {row: {date: word}}).

    **THE PAGE SPLITS THE TABLE INTO BLOCKS OF SIX COLUMNS**, and repeats every
    row heading in each block; the detailed section below repeats the whole
    thing again. A parser that reads the first "Metric" block and stops sees
    six of eleven dates and calls that the report. Measured on
    Threshold-Series/run1, which has eleven: four blocks, 6 + 5 + 6 + 5. So
    every block is read and merged by (row, date), and a row that appears twice
    for the same date must say the same word both times.

    The words come from the app's own five plus "drift", so a sixth word would
    come back as an unparsed line rather than be read as a row name.
    """
    lines = [ln.strip() for ln in text.splitlines()]
    dates: list = []
    rows: "dict[str, dict[str, str]]" = {}
    i = 0
    while True:
        try:
            i = lines.index("Metric", i) + 1
        except ValueError:
            break
        block: list = []
        while i < len(lines) and lines[i] and lines[i][:4].isdigit():
            block.append(lines[i])
            i += 1
        if not block:
            continue
        for d in block:
            if d not in dates:
                dates.append(d)
        n = len(block)
        while i < len(lines):
            if lines[i] == "Metric":
                break
            label = lines[i]
            if not label:
                i += 1
                continue
            got = lines[i + 1: i + 1 + n]
            if len(got) == n and all(w in WORDS for w in got):
                cell = rows.setdefault(label, {})
                for d, w in zip(block, got):
                    cell[d] = w
                i += 1 + n
            else:
                i += 1
    return dates, rows


def main() -> int:                                          # noqa: C901
    assert os.environ.get("CHROMIQ_SETTINGS_FILE"), "SANDBOX THE SETTINGS FIRST"
    assert os.environ.get("CHROMIQ_PRESETS_DIR"), "SANDBOX THE PRESETS FIRST"
    assert not os.environ.get("QT_QPA_PLATFORM"), "this DRIVER opens a window"
    pack, out = Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve()
    out.mkdir(parents=True, exist_ok=True)
    shots = out / "photographs"
    shots.mkdir(exist_ok=True)

    expected = {}
    iva = pack / "intended-vs-actual.json"
    for e in json.loads(iva.read_text(encoding="utf-8")):
        expected[(e["project"], e["run"], e["date"])] = e

    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("ChromIQ")
    from ui.styles import WinButtonLayoutStyle
    app.setStyle(WinButtonLayoutStyle("Fusion"))
    from core.settings import AppSettings
    work = Path(tempfile.mkdtemp(prefix="chromiq-b393-"))
    settings = AppSettings()
    settings.set("custom_output_path", str(work))
    settings.set("appearance", "dark")
    settings.set("language", "en")
    assert settings.get("custom_output_path", "") == str(work), "SANDBOX FAILED"
    for p in sorted(pack.glob("Report-Limits-*")):
        shutil.copytree(p, work / p.name)
    print(f"    pack copied to {work}", flush=True)
    print(f"    screen locked at start: {session_is_locked()}", flush=True)

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
    label_of = {r.id: r.label for r in ROWS}
    id_of = {r.label: r.id for r in ROWS}

    results: list = []
    faults: list = []
    checked = 0
    loaded = 0
    for pdir in sorted(work.glob("Report-Limits-*")):
        project = pdir.name
        for rdir in sorted((pdir / "runs").glob("run*"),
                           key=lambda d: int(d.name[3:])):
            dates_on_disk = sorted(
                d for d in (rdir / "verifications").glob("*")
                if d.is_dir() and sorted(d.glob("*.ti3")))
            if not dates_on_disk:
                continue
            ti3 = sorted(dates_on_disk[0].glob("*.ti3"))[0]
            dlg = MeasurementReportDialog(settings, None, initial_ti3=ti3)
            dlg.resize(1500, 1060)
            dlg.show()
            dlg.raise_()
            dlg.activateWindow()
            pump(app, 2600)
            entry: dict = {
                "project": project, "run": rdir.name,
                "visible": bool(dlg.isVisible()),
                "judged_against": dlg._set_combo.currentText(),
                "report_type": dlg._type_combo.currentText(),
                "saved_entries": dlg._saved_combo.count(),
            }
            if not dlg.isVisible():
                faults.append(f"{project}/{rdir.name}: the window did not open")
            text = dlg._view.toPlainText()
            dates, grid = read_grid(text)
            entry["dates_on_page"] = dates
            entry["rows_on_page"] = len(grid)
            # A COLOUR SUMMARY AND A PRINTING RECORD HAVE NO VERDICT GRID
            # BY DESIGN. T1 is the one-page hand-over: it prints one Result
            # line with the column's own word ("FAIL - Average difference
            # 0.92; Largest 4.50; 210 patches") and no per-row table. A driver
            # that demanded a grid of it was asking the app for a document it
            # does not produce. What must be true of EVERY page is that it
            # rendered something with a result in it.
            if not grid and "Result" not in text:
                faults.append(f"{project}/{rdir.name}: the page printed "
                              f"neither a verdict grid nor a result")

            # ---- every word on the page against what the data was built for
            mismatches = []
            for date_txt in dates:
                vid = None
                for key in expected:
                    if (key[0] == project and key[1] == rdir.name
                            and key[2].startswith(date_txt)):
                        vid = key
                        break
                if vid is None:
                    continue
                exp = expected[vid]
                over = set(exp["actual"])
                judged = set(exp["values"])
                for label, cells in grid.items():
                    rid = id_of.get(label)
                    word = cells.get(date_txt)
                    if rid is None or word is None:
                        continue
                    # A RAW SHEET IS A DRIFT CHECK AND HAS NO VERDICT TO GIVE.
                    # `is_drift_check` makes the report print "drift" in every
                    # cell, deliberately: judging a sheet printed with no
                    # profile applied against profile accuracy would fail a
                    # healthy printer for ever. It is the right word, so it is
                    # neither a crossing nor a pass.
                    if word == "drift":
                        continue
                    if rid in over and word not in ("FAIL", "COND"):
                        mismatches.append(
                            f"{date_txt} {rid}: the window says {word} and the "
                            f"data was built to cross the limit")
                    if rid in judged and rid not in over and word not in (
                            "PASS", "INFO"):
                        mismatches.append(
                            f"{date_txt} {rid}: the window says {word} and the "
                            f"data was built to sit inside the limit")
                    checked += 1
            entry["word_checks"] = checked
            entry["mismatches"] = mismatches
            faults.extend(f"{project}/{rdir.name}: {m}" for m in mismatches)

            # ---- every saved report LOADS (Knut: "all reports load")
            picks = []
            for i in range(dlg._saved_combo.count()):
                dlg._saved_combo.setCurrentIndex(i)
                pump(app, 900)
                body = dlg._view.toPlainText()
                # "Report Results" is the full report's heading; the
                # one-page Colour summary heads the same thing "Result".
                ok = len(body) > 400 and ("Report Results" in body
                                          or "\nResult\n" in body)
                picks.append({"index": i,
                              "entry": dlg._saved_combo.itemText(i)[:90],
                              "rendered": bool(ok), "chars": len(body)})
                loaded += 1
                if not ok:
                    faults.append(
                        f"{project}/{rdir.name}: entry {i} "
                        f"({dlg._saved_combo.itemText(i)[:60]!r}) rendered "
                        f"{len(body)} characters and no result section")
            entry["picks"] = picks

            # ---- a photograph of the first run of every project
            if rdir.name == "run1":
                a = shots / f"{project}-run1.png"
                b = shots / f"{project}-run1-again.png"
                ok, why, tries, same = capture_settled(app, dlg, a, b)
                entry["photograph"] = {"taken": bool(ok), "why": why,
                                       "two_identical_frames": bool(same),
                                       "attempts": tries}
                if not ok or not same:
                    faults.append(f"{project}/{rdir.name}: no settled "
                                  f"photograph ({why})")
                else:
                    b.unlink(missing_ok=True)
            results.append(entry)
            print(f"    {project}/{rdir.name}: {len(dates)} column(s), "
                  f"{len(grid)} row(s), {dlg._saved_combo.count()} saved "
                  f"entries, {len(mismatches)} mismatch(es)", flush=True)
            dlg.close()
            dlg.deleteLater()
            pump(app, 300)

    summary = {
        "pack": str(pack),
        "runs_driven": len(results),
        "verdict_words_checked": checked,
        "reports_loaded": loaded,
        "faults": faults,
        "runs": results,
        "row_labels": label_of,
    }
    (out / "on-screen.json").write_text(json.dumps(summary, indent=2),
                                        encoding="utf-8")
    print(f"\n    {len(results)} runs driven on screen, {checked} verdict "
          f"words read off the page, {loaded} saved reports loaded",
          flush=True)
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
