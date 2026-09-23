"""K23 on screen: where every kind of report lives, and what "Report shown"
and "Already generated" list and count, on Report-Limits-Report-Folders.

Knut, 2026-09-23: *"Every setting, variety, type that may occur of all
mentioned parameters, location of reports, report types, included
measurements from various places, must be tested multiple times, using demo
project data, on screen on real app, while monitoring what happens in files
and locations, and on screen, to assure correct behaviour."*

Every scenario lists the report folders before and after, photographs the
window with the "Already generated" line and the opened "Report shown"
pulldown, and records both as text. The project is a COPY of the demo pack,
so it has moved since it was built: every document it holds records folders
that no longer exist, which is the moved-project case on every step.

    CHROMIQ_DEMO_PACK=<pack> python scripts/drive_k23_report_folders.py <out>
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from userdrive import Drive                                   # noqa: E402

NAME = "Report-Limits-Report-Folders"


def tree(root: Path) -> "list[str]":
    """Every report file under the project, with its role and type."""
    out = []
    for p in sorted(root.rglob("report_*.json")):
        try:
            rep = json.loads(p.read_text(encoding="utf-8"))
        except Exception:                                  # noqa: BLE001
            out.append(f"{p.relative_to(root)}  (unreadable)")
            continue
        doc = rep.get("document") or {}
        role = doc.get("role") or ("one-file report" if doc else "no block")
        out.append(f"{p.relative_to(root)}  [{role}] "
                   f"type={doc.get('type') or rep.get('report_type') or '-'} "
                   f"id={doc.get('id', '-')}")
    return out


def script(d):
    root = d.work / NAME
    listings = d.out / "folder-listings"
    listings.mkdir(exist_ok=True)
    d.record["scenarios"] = {}

    def listing(tag):
        lines = tree(root)
        (listings / f"{tag}.txt").write_text("\n".join(lines) + "\n",
                                             encoding="utf-8")
        return lines

    def state(dlg, tag, what):
        """Photograph the window and the open pulldown; record both."""
        combo = dlg._saved_combo
        entries = [combo.itemText(i) for i in range(1, combo.count())]
        line = dlg._type_blurb_full
        detail = dlg._generated_full
        rec = {"what": what, "report_shown": entries,
               "selected": combo.currentText(), "already_line": line,
               "already_detail": detail,
               "ticked": [r.get("created") for r in dlg._runs_for_report()],
               "listed_files": [str(e.get("file") or "") for e in
                                dlg._saved_documents(dlg._run_ctx.run)]}
        d.record["scenarios"][tag] = rec
        d.note(f"[{tag}] {what}")
        d.note(f"   Already generated: {line!r}")
        for e in entries:
            d.note(f"   Report shown: {e}")
        d.shot(dlg, f"{tag}-window")
        combo.showPopup()
        d.pump(700)
        d.shot(combo.view(), f"{tag}-report-shown-open")
        combo.hidePopup()
        d.pump(300)
        return rec

    def open_window(run, run_type):
        d.set_bar(run_type=run_type, run=run)
        d.pump(800)
        d.launch_tool("measurement_report")

    def pick(dlg, needle):
        combo = dlg._saved_combo
        for i in range(1, combo.count()):
            if needle in combo.itemText(i):
                combo.setCurrentIndex(i)
                d.pump(1500)
                return combo.itemText(i)
        raise AssertionError(f"no entry with {needle!r}")

    d.open_project(NAME)
    before_all = listing("00-as-shipped")
    d.note(f"{len(before_all)} report files as shipped")

    # --- S1: run1 as Verification ------------------------------------------
    open_window("run1", "Verification")
    yield 5000
    dlg = d.top_dialog("MeasurementReportDialog")
    state(dlg, "S1-run1-verification", "run1, Run type Verification: one-date "
          "reports of every verification type, all dates, two dates, legacy, "
          "across runs; never the deleted one")
    dlg.close()
    yield 800

    # --- S2: run2 as Verification ------------------------------------------
    open_window("run2", "Verification")
    yield 5000
    dlg = d.top_dialog("MeasurementReportDialog")
    state(dlg, "S2-run2-verification", "run2, Run type Verification: its "
          "one-date reports, the older no-record report, and the report "
          "across runs")
    dlg.close()
    yield 800

    # --- S3/S4: Profiling --------------------------------------------------
    for tag, run in (("S3-run1-profiling", "run1"),
                     ("S4-run2-profiling", "run2")):
        open_window(run, "Profiling")
        yield 5000
        dlg = d.top_dialog("MeasurementReportDialog")
        state(dlg, tag, f"{run}, Run type Profiling: its own Printing record "
              "and the Printing record across both profiling sheets")
        dlg.close()
        yield 800

    # --- S5: Generate a new report of every date of run1 -------------------
    open_window("run1", "Verification")
    yield 5000
    dlg = d.top_dialog("MeasurementReportDialog")
    dlg._saved_combo.setCurrentIndex(0)             # New report…
    yield 1200
    dlg._select_all_btn.click()
    yield 1200
    pre = listing("S5-before")
    dlg._generate_btn.click()                       # "New report…": no question
    yield 3000
    post = listing("S5-after")
    new = sorted(set(post) - set(pre))
    d.record["scenarios"]["S5-files-written"] = new
    d.note("S5 new files:\n   " + "\n   ".join(new))
    state(dlg, "S5-generated-all-dates", "Generate on every date of run1")

    # --- S6: Update that report down to ONE date ---------------------------
    rows = [(i, key) for i, (kind, _si, key) in enumerate(dlg._list_rows)
            if kind == "run" and key is not None]
    from PyQt6.QtCore import Qt
    for i, _key in rows[:-1]:
        dlg._profile_list.item(i).setCheckState(Qt.CheckState.Unchecked)
    yield 1500
    pre = listing("S6-before")
    d.later(dlg._generate_btn.click)
    yield 1200
    d.answer("Update", name="S6-update-question")
    yield 3000
    post = listing("S6-after")
    d.record["scenarios"]["S6-changed"] = {
        "gone": sorted(set(pre) - set(post)), "new": sorted(set(post) - set(pre))}
    d.note("S6 gone:\n   " + "\n   ".join(sorted(set(pre) - set(post))))
    d.note("S6 new:\n   " + "\n   ".join(sorted(set(post) - set(pre))))
    state(dlg, "S6-updated-to-one-date", "the same report, Updated to one date")

    # --- S7: widen it again to two dates -----------------------------------
    dlg._profile_list.item(rows[0][0]).setCheckState(Qt.CheckState.Checked)
    yield 1500
    pre = listing("S7-before")
    d.later(dlg._generate_btn.click)
    yield 1200
    d.answer("Update", name="S7-update-question")
    yield 3000
    post = listing("S7-after")
    d.record["scenarios"]["S7-changed"] = {
        "gone": sorted(set(pre) - set(post)), "new": sorted(set(post) - set(pre))}
    d.note("S7 new:\n   " + "\n   ".join(sorted(set(post) - set(pre))))
    state(dlg, "S7-updated-to-two-dates", "the same report, Updated to two "
          "dates again")

    # --- S8: Delete the seeded all-dates report ----------------------------
    picked = pick(dlg, "All dates")
    d.note(f"S8 picked {picked!r}")
    yield 1000
    pre = listing("S8-before")
    d.later(dlg._delete_report_btn.click)
    yield 1200
    d.answer("OK", name="S8-delete-question")
    yield 2500
    post = listing("S8-after")
    d.record["scenarios"]["S8-changed"] = {
        "gone": sorted(set(pre) - set(post)), "new": sorted(set(post) - set(pre))}
    old = sorted(str(p.relative_to(root)) for p in
                 (root / "runs" / "run1" / "verifications" / "old").rglob("*.json"))
    d.record["scenarios"]["S8-verifications-old"] = old
    d.note("S8 in verifications/old:\n   " + "\n   ".join(old))
    state(dlg, "S8-after-delete", "after Delete Selected Report on the "
          "all-dates report")

    # --- S9: the legacy report of two dates --------------------------------
    picked = pick(dlg, "2026-12-20 09:00")
    yield 1500
    state(dlg, "S9-legacy-selected", f"the legacy report selected: {picked}")

    # --- S10: the PDF's default folder for a report of several dates -------
    picked = pick(dlg, "2026-12-21 09:30")
    yield 1500
    d.later(dlg._pdf_btn.click)
    yield 1200
    info = d.read_file_dialog(name="S10-pdf-folder")
    d.record["scenarios"]["S10-pdf-dialog"] = info
    dlg.close()
    yield 800

    # --- S11: a one-date report on run2 ------------------------------------
    open_window("run2", "Verification")
    yield 5000
    dlg = d.top_dialog("MeasurementReportDialog")
    dlg._saved_combo.setCurrentIndex(0)
    yield 1200
    here = dlg._run_key(dlg._report)
    for i, (kind, _si, key) in enumerate(dlg._list_rows):
        if kind == "run" and key is not None and key != here:
            dlg._profile_list.item(i).setCheckState(Qt.CheckState.Unchecked)
    yield 1500
    pre = listing("S11-before")
    dlg._generate_btn.click()
    yield 3000
    post = listing("S11-after")
    d.record["scenarios"]["S11-files-written"] = sorted(set(post) - set(pre))
    d.note("S11 new:\n   " + "\n   ".join(sorted(set(post) - set(pre))))
    state(dlg, "S11-one-date-run2", "Generate on one date of run2")
    dlg.close()
    yield 800
    listing("99-at-the-end")


if __name__ == "__main__":
    d = Drive(Path(sys.argv[1]), projects=[NAME])
    rc = d.run(script)
    print("done", rc)
    sys.exit(rc)
