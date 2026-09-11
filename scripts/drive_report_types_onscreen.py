#!/usr/bin/env python3
"""Drive the Measurement Report over every report type and every limit set.

Knut, 2026-09-11 (issue #182): *"Claude must also use the demo projects to test
all limits on screen, and to verify that all report types and all 'judge
against' threshold sets are verified."*

ON SCREEN, in a real window, because that is this project's default and because
a pulldown that greys an item is one of the things ``widget.grab()`` cannot
show. The window is photographed with ``scripts/onscreen_capture.py``, which
refuses rather than hand back wallpaper when the login session is locked.

What it does, for the runs of ``Report-Limits-Report-Types``:

* copies the package first and drives the COPY, because choosing a limit set
  re-binds the run and rewrites its dated reports. The package on disk is meant
  to be reproducible, and a driver that judged it would also have changed it.
* opens the real ``MeasurementReportDialog`` on each dated verification,
* walks the report-type pulldown and the "Judged against" pulldown over every
  combination ChromIQ offers, and for each one records every row, its verdict
  word, the Overall word and the sentence under it,
* checks the two types ChromIQ cannot produce are SHOWN, disabled, and carry
  the reason, and that the refusal holds one level below the control as well,
* writes everything to JSON so it can be compared against the package's own
  intended/actual table.

Run it::

    CHROMIQ_SETTINGS_FILE=/tmp/chromiq-demos.ini \\
    CHROMIQ_PRESETS_DIR=/tmp/chromiq-demos-presets \\
    .venv/bin/python scripts/drive_report_types_onscreen.py <pack> <out-dir>

Never set ``QT_QPA_PLATFORM=offscreen`` for this. It is a driver, not a test.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import time
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE.parent))

from PyQt6.QtCore import QSettings, Qt                       # noqa: E402
from PyQt6.QtWidgets import QApplication                     # noqa: E402

from core.settings import AppSettings                        # noqa: E402
from scripts.onscreen_capture import (capture_window,        # noqa: E402
                                      session_is_locked)
from ui.theme import apply_appearance                        # noqa: E402

PROJECT = "Report-Limits-Report-Types"


def pump(app, ms: int) -> None:
    end = time.monotonic() + ms / 1000.0
    while time.monotonic() < end:
        app.processEvents()
        time.sleep(0.005)


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    src_pack = Path(argv[0]).resolve() if argv else \
        _HERE.parent / "demo-projects" / "ChromIQ-Report-Limit-Demos"
    out = Path(argv[1]).resolve() if len(argv) > 1 else \
        Path("/tmp/agent-report-demo/onscreen")
    out.mkdir(parents=True, exist_ok=True)
    shots = out / "shots"
    shots.mkdir(exist_ok=True)

    if os.environ.get("QT_QPA_PLATFORM") == "offscreen":
        print("REFUSING: QT_QPA_PLATFORM=offscreen. This driver opens a real "
              "window; offscreen is the test suite's platform and cannot show "
              "a greyed pulldown item, a popup or a native dialog.")
        return 2

    # DRIVE A COPY. Choosing a limit set re-binds the run and rewrites its
    # dated reports, so a driver pointed at the shipped package would change
    # the thing it is checking.
    pack = out / "pack"
    if pack.exists():
        shutil.rmtree(pack)
    shutil.copytree(src_pack, pack)

    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setStyle("Fusion")

    # THE SANDBOX, BEFORE ANY WINDOW. `CHROMIQ_SETTINGS_FILE` keeps the app out
    # of the real preferences; `custom_output_path` keeps the projects it finds
    # out of ~/ChromIQ. Both, because the first alone does not do the second.
    settings = AppSettings()
    settings._qs = QSettings(str(out / "drive.ini"), QSettings.Format.IniFormat)
    settings.set("custom_output_path", str(pack))
    settings.set("compliance_set_overrides", "")
    settings.set("compliance_default_set", "chromiq_default")
    settings.set("compliance_allow_edit_after_measurement", True)
    settings.set("appearance", "dark")
    apply_appearance(app, None, "dark")

    locked = session_is_locked()
    print(f"screen locked: {locked}")
    print(f"driving a copy at: {pack}")

    from core.file_manager import Run
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    from workflow.compliance_sets import (SET_BY_ID, selectable_set_ids,
                                          summary_text, word_label)
    from workflow.measurement_report import (REPORT_TYPE_ISO_7,
                                             REPORT_TYPE_ISO_8,
                                             REPORT_TYPE_MENU,
                                             REPORT_TYPE_MENU_HEADING,
                                             report_type_name)
    from workflow.run_compliance import set_run_report_type

    project = pack / PROJECT
    if not project.is_dir():
        print(f"REFUSING: {project} is not there. Build the package first.")
        return 2

    record: dict = {"screen_locked": locked, "pack": str(src_pack),
                    "menu": [], "seen": [], "refusals": [], "shots": []}

    runs = sorted((project / "runs").glob("run*"),
                  key=lambda p: int(p.name[3:] or 0))
    builts = [(tid, name) for tid, name, _b, built in REPORT_TYPE_MENU if built]
    set_ids = selectable_set_ids({})

    dates = [(rd, ti3) for rd in runs
             for ti3 in sorted((rd / "verifications").glob("*/*.ti3"))]
    print(f"{len(runs)} runs, {len(dates)} dated verifications, "
          f"{len(builts)} documents, {len(set_ids)} limit sets "
          f"=> {len(dates) * len(builts) * len(set_ids)} combinations")

    first = True
    for rd, ti3 in dates:
        date = ti3.parent.name
        dlg = MeasurementReportDialog(settings, None, initial_ti3=str(ti3))
        dlg.resize(1240, 1000)
        dlg.move(50, 40)
        dlg.show()
        dlg.raise_()
        dlg.activateWindow()
        # every confirmation this sweep can raise gets a yes, so nothing blocks
        dlg._confirm = lambda *a, **k: True                  # noqa: E731
        pump(app, 900 if first else 350)

        if first:
            combo = dlg._type_combo
            model = combo.model()
            for i in range(combo.count()):
                record["menu"].append({
                    "index": i,
                    "text": combo.itemText(i),
                    "data": combo.itemData(i),
                    "enabled": bool(model.item(i).isEnabled()),
                    "tooltip": combo.itemData(i, Qt.ItemDataRole.ToolTipRole) or "",
                })
            print("\n-- the report type pulldown, as the window draws it --")
            for e in record["menu"]:
                mark = "x" if e["enabled"] else " "
                print(f"  [{mark}] {e['text']}")
                if not e["enabled"] and e["tooltip"]:
                    print(f"        {e['tooltip']}")
            heading = [e for e in record["menu"]
                       if e["text"] == REPORT_TYPE_MENU_HEADING]
            record["menu_heading_present"] = bool(heading)
            record["menu_heading_enabled"] = bool(heading and heading[0]["enabled"])

            for tid in (REPORT_TYPE_ISO_8, REPORT_TYPE_ISO_7):
                entry = next((e for e in record["menu"] if e["data"] == tid), None)
                refused = ""
                try:
                    set_run_report_type(Run.for_dir(rd), tid)
                except ValueError as exc:
                    refused = str(exc)
                record["refusals"].append({
                    "type": tid, "name": report_type_name(tid),
                    "shown_in_pulldown": entry is not None,
                    "enabled": bool(entry and entry["enabled"]),
                    "reason_in_menu": (entry or {}).get("tooltip", ""),
                    "store_refused_with": refused,
                })

            ok, why = capture_window(dlg, shots / "01-window.png")
            record["shots"].append({"file": "01-window.png", "ok": ok,
                                    "why": why})
            print(f"capture 01-window.png: "
                  f"{'OK' if ok else 'REFUSED: ' + why}")
            first = False

        run_obj = Run.for_dir(rd)
        for sid in set_ids:
            si = dlg._set_combo.findData(sid)
            if si < 0:
                record["seen"].append({
                    "run": rd.name, "date": date, "set": SET_BY_ID[sid].label,
                    "offered": False})
                continue
            dlg._set_combo.setCurrentIndex(si)
            pump(app, 260)
            for tid, tname in builts:
                ti = dlg._type_combo.findData(tid)
                dlg._type_combo.setCurrentIndex(ti)
                pump(app, 140)
                rr = dlg._runs_for_report()
                if not rr:
                    continue
                # THE COLUMN FOR THE DATE THIS WINDOW WAS OPENED ON, not the
                # last one in the list. Opening the report on one dated
                # measurement loads the run's WHOLE history, so `rr[-1]` is the
                # newest date; taking it made every crossing date read as its
                # own recovery, and the first sweep reported five disagreements
                # that were all this.
                r = next((x for x in rr
                          if str(x.get("created", ""))[:10] == date[:10]), rr[-1])
                if str(r.get("created", ""))[:10] != date[:10]:
                    print(f"  !! {rd.name}/{date}: the window has no column "
                          f"for this date; reading {r.get('created')}")
                rows, from_saved = dlg._verdict_rows(r)
                sm = dlg._column_summary(r)
                record["seen"].append({
                    "run": rd.name, "date": date, "type": tname, "type_id": tid,
                    "set": SET_BY_ID[sid].label, "set_id": sid, "offered": True,
                    "set_combo_enabled": bool(dlg._set_combo.isEnabled()),
                    "type_combo_enabled": bool(dlg._type_combo.isEnabled()),
                    "from_saved_verdict": bool(from_saved),
                    "column_created": str(r.get("created", "")),
                    "columns_loaded": len(rr),
                    "already_line": dlg._generated_types_line(run_obj),
                    "blurb": dlg._type_blurb_full,
                    "rows": [{"row": x.get("row_id") or x.get("key"),
                              "word": x.get("word"),
                              "value": x.get("value"),
                              "reason": x.get("reason")} for x in rows],
                    "overall": word_label(sm.word),
                    "overall_token": sm.word,
                    "sentence": summary_text(sm),
                })
        print(f"  {rd.name}/{date}: "
              f"{len(builts) * len(set_ids)} combinations recorded")

        if rd.name == "run7" and date.startswith("2026-11-08"):
            ok, why = capture_window(dlg, shots / "02-nothing-to-judge.png")
            record["shots"].append({"file": "02-nothing-to-judge.png",
                                    "ok": ok, "why": why})
            print(f"capture 02-nothing-to-judge.png: "
                  f"{'OK' if ok else 'REFUSED: ' + why}")

        dlg.close()
        pump(app, 80)
        dlg.deleteLater()
        pump(app, 80)

    # ---- EVERY DATE OF EVERY PROJECT, against the set and type it is bound
    #      to. Knut asked for the limits to be tested on screen, and the rows
    #      that cross live in the first two projects, whose runs are locked on
    #      purpose: their set cannot be chosen, so this pass reads what the
    #      window shows rather than driving the pulldowns.
    #      A SECOND, UNTOUCHED COPY. The sweep above chose a limit set on every
    #      run it walked, which re-binds the run and rewrites its dated
    #      reports; reading those back would be reading what this driver did,
    #      not what the package ships.
    pack2 = out / "pack-as-shipped"
    if pack2.exists():
        shutil.rmtree(pack2)
    shutil.copytree(src_pack, pack2)
    settings.set("custom_output_path", str(pack2))

    record["all_dates"] = []
    all_dates = [(pd.name, rd, ti3)
                 for pd in sorted(pack2.glob("Report-Limits-*"))
                 for rd in sorted((pd / "runs").glob("run*"),
                                  key=lambda p: int(p.name[3:] or 0))
                 for ti3 in sorted((rd / "verifications").glob("*/*.ti3"))]
    # AND THE RUN'S OWN PROFILING MEASUREMENT, which is a sheet the report
    # refuses to grade (it was printed raw by definition) and whose Overall
    # sentence nothing else in the package reaches. It needs no new data: every
    # run has had one since the package existed and nobody opened it.
    all_dates += [(pd.name, rd, ti3)
                  for pd in sorted(pack2.glob("Report-Limits-*"))
                  for rd in sorted((pd / "runs").glob("run*"),
                                   key=lambda p: int(p.name[3:] or 0))[:1]
                  for ti3 in sorted(rd.glob("*.ti3"))]
    print(f"\n-- every dated verification of every project: "
          f"{len(all_dates)} --")
    for pname, rd, ti3 in all_dates:
        profiling = ti3.parent == rd
        date = "the profiling measurement" if profiling else ti3.parent.name
        dlg = MeasurementReportDialog(settings, None, initial_ti3=str(ti3))
        dlg.resize(1240, 1000)
        dlg.move(50, 40)
        dlg.show()
        dlg.raise_()
        dlg.activateWindow()
        dlg._confirm = lambda *a, **k: True                  # noqa: E731
        pump(app, 320)
        rr = dlg._runs_for_report()
        r = (rr[-1] if rr else None) if profiling else next(
            (x for x in rr if str(x.get("created", ""))[:10] == date[:10]),
            rr[-1] if rr else None)
        if r is None:
            print(f"  !! {pname}/{rd.name}/{date}: the window loaded no run")
            dlg.close()
            continue
        rows, from_saved = dlg._verdict_rows(r)
        sm = dlg._column_summary(r)
        body = dlg._report_body_html([r], for_pdf=False)
        record["all_dates"].append({
            "project": pname.replace("Report-Limits-", ""),
            "run": rd.name, "date": date,
            "type": dlg._type_combo.currentText(),
            "type_id": dlg._type_combo.currentData(),
            "set": dlg._set_combo.currentText(),
            "set_id": dlg._set_combo.currentData(),
            "set_combo_enabled": bool(dlg._set_combo.isEnabled()),
            "unlock_visible": bool(dlg._unlock_check.isVisible()),
            "unlock_enabled": bool(dlg._unlock_check.isEnabled()),
            "from_saved_verdict": bool(from_saved),
            "rows": [{"row": x.get("row_id") or x.get("key"),
                      "word": x.get("word"), "value": x.get("value"),
                      "reason": x.get("reason")} for x in rows],
            "overall": word_label(sm.word),
            "overall_token": sm.word,
            "sentence": summary_text(sm),
            "document_chars": len(body),
        })
        # the rendered document, kept for the four types once each
        keep = out / "documents"
        keep.mkdir(exist_ok=True)
        tag = dlg._type_combo.currentData()
        f = keep / f"{tag}.html"
        if not f.exists():
            f.write_text(f"<!-- {pname}/{rd.name}/{date} -->\n" + body,
                         encoding="utf-8")
        dlg.close()
        pump(app, 40)
        dlg.deleteLater()
        pump(app, 40)
    print(f"   {len(record['all_dates'])} dated verifications read")

    (out / "onscreen.json").write_text(
        json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nwritten to {out / 'onscreen.json'} "
          f"({len(record['seen'])} recordings)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
