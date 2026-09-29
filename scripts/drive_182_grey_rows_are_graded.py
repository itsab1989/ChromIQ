#!/usr/bin/env python3
"""The grey rows are graded and the note is numbered, in a REAL report window.

Knut, 2026-09-13, overruling CH-17:

    "the grey metric tests is not about the printer, it is about verifying that
     the profile created for a specific paper or process condition measures
     within set acceptable thresholds. The verdicts should be given, but a note
     can be given in a numbered list of notes, where a verdict is commented,
     for example regarding the tint of a paper and profile combination."

This drives the border-conditions project of the report-limits pack, whose
`Report-Limits-Border-Conditions` run 2 is the one built with no print record,
and records for every report type:

* every row, its verdict word, and the note numbers printed beside it;
* the numbered note list under the table, with the sentence;
* whether the note list is silent on the Printing record, where there are no
  verdicts to comment.

It photographs the window on each type, so the marker and the list can be read
rather than inferred.

The package is COPIED first and the copy is driven, because choosing a limit
set re-binds a run and rewrites its dated reports.

Run it::

    CHROMIQ_SETTINGS_FILE=/tmp/chromiq-grey.ini \\
    CHROMIQ_PRESETS_DIR=/tmp/chromiq-grey-presets \\
        python scripts/drive_182_grey_rows_are_graded.py <pack> <out-dir>

Never set QT_QPA_PLATFORM=offscreen for this. It is a driver, not a test.
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

from PyQt6.QtWidgets import QApplication, QDialog, QMessageBox   # noqa: E402

sys.path.insert(0, str(ROOT / "scripts"))                        # noqa: E402
from onscreen_capture import capture_window, session_is_locked   # noqa: E402


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
    from ui.styles import WinButtonLayoutStyle
    app.setStyle(WinButtonLayoutStyle("Fusion"))
    QDialog.exec = lambda self: 1                     # type: ignore[assignment]
    for m in ("warning", "critical", "information", "question"):
        setattr(QMessageBox, m, staticmethod(lambda *a, **k: 0))

    from core.settings import AppSettings
    import tempfile
    work = Path(tempfile.mkdtemp(prefix="chromiq-grey-"))
    settings = AppSettings()
    # PINNED, not merely sandboxed: an unset value in a fresh store still
    # points the app at the user's real ~/ChromIQ.
    settings.set("custom_output_path", str(work))
    settings.set("appearance", "dark")

    src = pack / "Report-Limits-Border-Conditions"
    assert src.is_dir(), f"no border-conditions project in {pack}"
    dst = work / src.name
    shutil.copytree(src, dst)
    print(f"    driving the COPY at {dst}", flush=True)

    from core.file_manager import FileManager
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    from workflow.measurement_report import (REPORT_TYPE_FULL,
                                             REPORT_TYPE_GREY,
                                             REPORT_TYPE_RECORD)
    fm = FileManager(settings)
    del fm

    ti3s = sorted(dst.rglob("verifications/*/*.ti3"))
    assert ti3s, f"no dated verification in {dst}"
    print(f"    {len(ti3s)} dated verification(s)", flush=True)

    rows_out: list = []
    for _i, ti3 in enumerate(ti3s, 1):
        dlg = MeasurementReportDialog(settings, None, initial_ti3=ti3)
        dlg.show()
        dlg.raise_()
        pump(app, 1500)
        print(f"    window on screen: {dlg.isVisible()} "
              f"{dlg.frameGeometry().width()}x{dlg.frameGeometry().height()}",
              flush=True)
        try:
            for tname, tval in (("full", REPORT_TYPE_FULL),
                                ("grey", REPORT_TYPE_GREY),
                                ("record", REPORT_TYPE_RECORD)):
                # THE COMBO, WHICH IS WHAT THE USER TOUCHES. The first
                # version of this driver called `set_run_report_type` on a
                # `dlg._run` that does not exist, so `getattr` handed back None,
                # every type produced identical rows, and the run that had to be
                # silent was never actually driven. Caught by reading the
                # driver's own output: three types, one answer.
                ti = dlg._type_combo.findData(tval)
                if ti < 0:
                    print(f"    [{tname:6s}] not offered on this run", flush=True)
                    continue
                dlg._type_combo.setCurrentIndex(ti)
                pump(app, 600)
                assert dlg._type_combo.currentData() == tval, (
                    f"the pulldown did not take {tname}")
                reps = dlg._runs_for_report()
                if not reps:
                    continue
                rows, _rec = dlg._verdict_rows(reps[0])
                numbering = dlg._note_numbering(reps)
                from workflow.measurement_report import note_numbers_for
                rec = {
                    "ti3": ti3.name, "type": tname,
                    "rows": [{"row_id": r.get("row_id"), "word": r.get("word"),
                              "value": r.get("value"),
                              "marks": note_numbers_for(r, numbering)}
                             for r in rows],
                    "numbered_notes": [
                        {"n": n, "rows": where, "sentence": sent}
                        for (n, where, sent) in dlg._numbered_notes(reps)],
                }
                body = dlg._report_body_html(reps, for_pdf=True)
                rec["note_heading_on_page"] = "Notes on the verdicts above:" in body
                # THE DATED FOLDER, NOT THE STEM. Every verification in a
                # run carries the same file stem, so naming the shot after it
                # overwrote four of five and left only the last run's window on
                # disk, which is the least interesting one.
                # SCROLL TO THE THING BEING PHOTOGRAPHED. The first run of
                # this driver photographed the Report Scope and the trend
                # chart, which is what the window opens on; the verdict table
                # and the note list are below the fold, so every picture was of
                # the wrong half of the document. `QTextBrowser` finds text, so
                # the view is scrolled to the note heading, or to the grey row
                # when there is no note.
                try:
                    from PyQt6.QtGui import QTextCursor
                    view = dlg._view
                    view.moveCursor(QTextCursor.MoveOperation.Start)
                    # THE MARKED ROW FIRST, THEN THE NOTE. Knut asked for the
                    # marker AND the list, so a picture of the list alone
                    # answers half of it: scrolled to the note heading, the
                    # grey rows carrying the raised "1)" were above the
                    # viewport in every shot.
                    for probe in ("Grey balance of the grey ramp, average",
                                  "Notes on the verdicts above",
                                  "Grey balance", "Report Results"):
                        if view.find(probe):
                            break
                    # …AND A LITTLE FURTHER, so the sentence under the heading
                    # is on screen too. Finding the heading puts it on the last
                    # line of the viewport, which is where it was clipped.
                    bar = view.verticalScrollBar()
                    bar.setValue(min(bar.maximum(), bar.value() + 6 * bar.singleStep()))
                    pump(app, 350)
                except Exception as exc:                        # noqa: BLE001
                    print(f"    could not scroll the view: {exc!r}", flush=True)
                shot = out / f"{_i:02d}-{ti3.parent.name}-{tname}.png"
                ok, why = capture_window(dlg, shot)
                rec["photo"] = shot.name if ok else f"REFUSED: {why}"
                rows_out.append(rec)
                greys = [r for r in rec["rows"]
                         if str(r["row_id"]).startswith("grey_balance")]
                print(f"    [{tname:6s}] grey rows: "
                      + ", ".join(f"{g['word']}{g['marks'] or ''}" for g in greys)
                      + f"   notes={len(rec['numbered_notes'])}"
                      + f"   heading={rec['note_heading_on_page']}"
                      + f"   photo={'ok' if ok else 'REFUSED'}", flush=True)
        finally:
            dlg.close()
            pump(app, 300)

    (out / "grey-rows.json").write_text(
        json.dumps({"screen_locked": session_is_locked(),
                    "qt_qpa_platform": os.environ.get("QT_QPA_PLATFORM", "<unset>"),
                    "results": rows_out}, indent=2, ensure_ascii=False),
        encoding="utf-8")
    print(f"\n    written {out / 'grey-rows.json'}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
