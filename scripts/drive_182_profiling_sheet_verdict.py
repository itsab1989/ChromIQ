#!/usr/bin/env python3
"""What the report window says about a run's OWN profiling measurement.

Knut, 2026-09-13, on `Report-Limits-Custom-Columns`:

    "Why are most of them INFO, when the thresholds are set and can be tested.
     Verdict should be given when report is calculated."
    "The statemend 'It was saved by a version of ChromIQ that did not yet keep
     the verdict together with the measurements' seems wrong."
    "Make sure all verdicts exist in the demo package."

His column is headed with TODAY's date, not one of the pack's 2027
verification dates, so the sheet he opened is the run's own profiling chart:
the pack saves a report beside every dated verification and none beside the
measurement the profile was built from. That measurement therefore reaches
`_load_runs`'s `if not runs:` fall-back, which builds a report live.

This driver opens the report window on BOTH kinds from one project and records,
for each:

* the "Judged against" cell of the Report Results table;
* the provenance sentence printed under the accuracy table;
* every row with its word and its reason code;
* whether the document says anywhere why the INFO rows carry no verdict;
* a photograph of the window.

Run it::

    CHROMIQ_SETTINGS_FILE=/tmp/chromiq-prof.ini \\
    CHROMIQ_PRESETS_DIR=/tmp/chromiq-prof-presets \\
        python scripts/drive_182_profiling_sheet_verdict.py <pack> <out-dir>

Never set QT_QPA_PLATFORM=offscreen for this. It is a driver, not a test.
"""
from __future__ import annotations

import json
import os
import re
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

PROJECT = "Report-Limits-Custom-Columns"


def pump(app, ms: int = 300) -> None:
    end = time.monotonic() + ms / 1000.0
    while time.monotonic() < end:
        app.processEvents()
        time.sleep(0.01)


def text_of(html_str: str) -> str:
    """The document's prose, so a sentence can be searched for without its
    markup. `_report_body_html` is HTML; Knut reads what Qt draws."""
    s = re.sub(r"<[^>]+>", " ", html_str)
    s = s.replace("&nbsp;", " ").replace("&amp;", "&")
    s = s.replace("&quot;", '"').replace("&lt;", "<").replace("&gt;", ">")
    return re.sub(r"\s+", " ", s)


def main() -> int:
    assert os.environ.get("CHROMIQ_SETTINGS_FILE"), "SANDBOX THE SETTINGS FIRST"
    assert os.environ.get("CHROMIQ_PRESETS_DIR"), "SANDBOX THE PRESETS FIRST"
    pack = Path(sys.argv[1]).resolve()
    out = Path(sys.argv[2]).resolve()
    out.mkdir(parents=True, exist_ok=True)

    app = QApplication.instance() or QApplication(sys.argv[:1])
    from ui.styles import WinButtonLayoutStyle
    app.setStyle(WinButtonLayoutStyle("Fusion"))
    QDialog.exec = lambda self: 1                     # type: ignore[assignment]
    for m in ("warning", "critical", "information", "question"):
        setattr(QMessageBox, m, staticmethod(lambda *a, **k: 0))

    from core.settings import AppSettings
    work = Path(tempfile.mkdtemp(prefix="chromiq-prof-"))
    settings = AppSettings()
    settings.set("custom_output_path", str(work))
    settings.set("appearance", "dark")

    src = pack / PROJECT
    assert src.is_dir(), f"no {PROJECT} in {pack}"
    dst = work / src.name
    shutil.copytree(src, dst)
    print(f"    driving the COPY at {dst}", flush=True)

    from core.file_manager import FileManager
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    fm = FileManager(settings)
    del fm

    # run1's own measurement first, then one of its dated verifications, so the
    # two are read from the same project, the same limit set and the same run.
    prof = dst / "runs" / "run1" / f"{PROJECT}.ti3"
    verifs = sorted((dst / "runs" / "run1" / "verifications").glob("*/*.ti3"))
    assert prof.is_file(), f"no profiling measurement at {prof}"
    assert verifs, "no dated verification in run1"
    todo = [("profiling", prof), ("verification", verifs[0])]

    results: list = []
    for i, (kind, ti3) in enumerate(todo, 1):
        dlg = MeasurementReportDialog(settings, None, initial_ti3=ti3)
        dlg.show()
        dlg.raise_()
        pump(app, 1500)
        print(f"    [{kind}] window on screen: {dlg.isVisible()} "
              f"{dlg.frameGeometry().width()}x{dlg.frameGeometry().height()}",
              flush=True)
        try:
            reps = dlg._runs_for_report()
            rec: dict = {"kind": kind, "ti3": str(ti3.relative_to(dst)),
                         "columns": len(reps)}
            body = dlg._report_body_html(reps, for_pdf=True)
            prose = text_of(body)
            cols = []
            for r in reps:
                rows, recorded = dlg._verdict_rows(r)
                cols.append({
                    "created": str(r.get("created"))[:19],
                    "sheet_kind": r.get("sheet_kind"),
                    "_fresh": bool(r.get("_fresh")),
                    "recorded": recorded,
                    "judged_against": text_of(dlg._thresholds_cell(r)).strip(),
                    "provenance": dlg._verdict_provenance(r, recorded),
                    "rows": [{"row_id": x.get("row_id"), "word": x.get("word"),
                              "value": x.get("value"),
                              "reason": x.get("reason")} for x in rows],
                    "measured_not_graded": dlg._measured_not_graded(r),
                })
            rec["cols"] = cols
            # DOES THE DOCUMENT EXPLAIN THE INFO ROWS ANYWHERE? Searched as
            # prose, because a sentence that exists only in a tooltip or a
            # help card is not on the page Knut pasted.
            rec["says_older_chromiq"] = (
                "did not yet keep the verdict together with the measurements"
                in prose)
            rec["says_printed_raw"] = "printed raw" in prose
            rec["says_build_a_profile"] = "build a profile" in prose
            (out / f"{i:02d}-{kind}-body.txt").write_text(prose, encoding="utf-8")

            try:
                from PyQt6.QtGui import QTextCursor
                view = dlg._view
                view.moveCursor(QTextCursor.MoveOperation.Start)
                for probe in ("Colour accuracy", "Report Results", "Grey balance"):
                    if view.find(probe):
                        break
                bar = view.verticalScrollBar()
                bar.setValue(min(bar.maximum(), bar.value() + 4 * bar.singleStep()))
                pump(app, 350)
            except Exception as exc:                            # noqa: BLE001
                print(f"    could not scroll the view: {exc!r}", flush=True)
            shot = out / f"{i:02d}-{kind}.png"
            ok, why = capture_window(dlg, shot)
            rec["photo"] = shot.name if ok else f"REFUSED: {why}"
            results.append(rec)
            for c in cols:
                words = {}
                for x in c["rows"]:
                    words[x["word"]] = words.get(x["word"], 0) + 1
                print(f"      col {c['created']} kind={c['sheet_kind']} "
                      f"fresh={c['_fresh']} recorded={c['recorded']} "
                      f"judged_against={c['judged_against']!r} {words}",
                      flush=True)
            print(f"      older-chromiq sentence on the page: "
                  f"{rec['says_older_chromiq']}   photo="
                  f"{'ok' if ok else 'REFUSED'}", flush=True)
        finally:
            dlg.close()
            pump(app, 300)

    (out / "profiling-sheet.json").write_text(
        json.dumps({"screen_locked": session_is_locked(),
                    "qt_qpa_platform": os.environ.get("QT_QPA_PLATFORM", "<unset>"),
                    "results": results}, indent=2, ensure_ascii=False),
        encoding="utf-8")
    print(f"\n    written {out / 'profiling-sheet.json'}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
