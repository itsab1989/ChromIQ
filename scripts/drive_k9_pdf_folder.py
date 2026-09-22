#!/usr/bin/env python3
"""K9 (Knut, beta 34): "Save Report as PDF" did not open at the correct
reports/ folder. *"Make sure this is tested on screen on working app for all
the levels the report feature should save reports and pdfs in."*

The four homes (`_report_dir`, and the "Where are my files?" card):
  single dated verification   -> runs/<id>/verifications/<date>/reports
  several checks of one run   -> runs/<id>/verifications/reports
  a profiling run             -> runs/<id>/reports
  several runs                -> <project>/reports

Driven as a user on Report-Limits-Threshold-Series: for each level, the
window is set up through its own controls, "Save report as PDF..." is
clicked, and the folder ChromIQ's save dialog OPENS in is read from the
dialog itself and photographed; then the dialog is cancelled.

    python scripts/drive_k9_pdf_folder.py <out-dir>
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from userdrive import Drive                                   # noqa: E402

NAME = "Report-Limits-Threshold-Series"


def _tick_only(dlg, keep):
    """Tick exactly the list rows `keep(i, key)` accepts."""
    from PyQt6.QtCore import Qt
    for i, (kind, _si, key) in enumerate(dlg._list_rows):
        if kind == "run" and key is not None:
            dlg._profile_list.item(i).setCheckState(
                Qt.CheckState.Checked if keep(i, key)
                else Qt.CheckState.Unchecked)


def _save_pdf(d, dlg, tag):
    from PyQt6.QtWidgets import QPushButton
    btn = next(b for b in dlg.findChildren(QPushButton)
               if b.text().replace("&", "").lower().startswith("save report as pdf"))
    d.later(btn.click)
    yield 300
    info = d.read_file_dialog(name=f"{tag}-save-dialog")
    d.record.setdefault("levels", {})[tag] = info
    yield 500


def _generate(d, dlg):
    import time
    from PyQt6.QtWidgets import QPushButton
    gen = next(b for b in dlg.findChildren(QPushButton)
               if b.text().replace("&", "").lower() == "generate report")
    n = dlg._saved_combo.count()
    d.later(gen.click)
    t0 = time.monotonic()
    while time.monotonic() - t0 < 20 and dlg._saved_combo.count() == n:
        yield 250
    yield 1200


def level(d, run_type, run, tag, keep, expect_rel):
    root = d.work / NAME
    d.set_bar(run_type=run_type, run=run)
    yield 800
    d.launch_tool("measurement_report")
    yield 4000
    dlg = d.top_dialog("MeasurementReportDialog")
    d.pick(dlg._saved_combo, "new report")
    yield 1200
    _tick_only(dlg, keep)
    yield 1000
    yield from _generate(d, dlg)
    d.note(f"[{tag}] rows in the document: {len(dlg._runs_for_document())}; "
           f"_report_dir: {dlg._report_dir().relative_to(root)}")
    yield from _save_pdf(d, dlg, tag)
    info = d.record["levels"].get(tag) or {}
    got = Path(info.get("dir") or "/")
    try:
        rel = str(got.resolve().relative_to(root.resolve()))
    except ValueError:
        rel = str(got)
    ok = rel == expect_rel
    d.record["levels"][tag] = dict(info, relative=rel, expected=expect_rel,
                                   as_expected=ok)
    d.note(f"[{tag}] dialog opened in {rel!r}; expected {expect_rel!r}: "
           f"{'OK' if ok else 'WRONG'}")
    dlg.close()
    yield 800


def script(d):
    d.open_project(NAME)
    first = [None]

    def one_date(i, key):
        if first[0] is None:
            first[0] = key
        return key == first[0]
    yield from level(d, "Verification", "run1", "1-one-dated-verification",
                     one_date,
                     "runs/run1/verifications/2026-01-05_100000/reports")
    yield from level(d, "Verification", "run1", "2-all-checks-of-one-run",
                     lambda i, k: True, "runs/run1/verifications/reports")
    here = {}

    def own_sheet(i, key):
        here.setdefault("k", key)
        return key == here["k"]
    yield from level(d, "Profiling", "run1", "3-one-profiling-run", own_sheet,
                     "runs/run1/reports")
    yield from level(d, "Profiling", "run1", "4-several-profiling-runs",
                     lambda i, k: True, "reports")


if __name__ == "__main__":
    d = Drive(Path(sys.argv[1]), projects=[NAME])
    rc = d.run(script)
    lv = d.record.get("levels", {})
    ok = bool(lv) and all(v.get("as_expected") for v in lv.values())
    print("ALL LEVELS AS EXPECTED" if ok else "NOT AS EXPECTED")
    sys.exit(rc or (0 if ok else 1))
