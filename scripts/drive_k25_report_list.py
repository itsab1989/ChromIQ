"""K25 on screen: "Report shown" grouped by run and project, the names kept,
every run's Printing records on a Profiling window.

Knut, #182 5789263863 and 5789532633. *"Make sure all conditions, variables,
modes, report types, file locations, measurements included (one and several
sets) etc, are tested an verified on screen on real app, while monitoring both
screen and files and locations."*

Every scenario lists the report files of both projects and the pack's own
`reports/` before and after, records "Report shown" row by row (headings
marked), photographs the window, and photographs the OPENED pulldown (its
popup is a window of its own, so it is captured by its own window id).

    CHROMIQ_DEMO_PACK=<pack> python scripts/drive_k25_report_list.py <out>
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from userdrive import DEMO_PACK, Drive                        # noqa: E402

NAME = "Report-Limits-Report-Folders"
OTHER = "Report-Limits-Report-Folders-Second"


def tree(root: Path) -> "list[str]":
    """Every report file under *root*, with its role, type and id."""
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
    from PyQt6.QtCore import Qt
    work = d.work
    listings = d.out / "folder-listings"
    listings.mkdir(exist_ok=True)
    d.record["scenarios"] = {}

    def listing(tag):
        lines = tree(work)
        (listings / f"{tag}.txt").write_text("\n".join(lines) + "\n",
                                             encoding="utf-8")
        return lines

    def rows(dlg):
        """Every row of "Report shown", as the user reads it; a heading is
        marked, and so is the row the pulldown is on."""
        combo = dlg._saved_combo
        out = []
        for i in range(combo.count()):
            text, key = combo.itemText(i), combo.itemData(i)
            if not text and key is None:
                out.append("-----")
                continue
            item = combo.model().item(i)
            mark = ">" if i == combo.currentIndex() else " "
            if key is None:
                out.append(f"{mark} [HEADING{'' if item.isEnabled() else ', not selectable'}] {text}")
            else:
                out.append(f"{mark} {text}")
        return out

    def state(dlg, tag, what):
        rec = {"what": what, "label": dlg._saved_label.text(),
               "report_shown": rows(dlg),
               "already_line": dlg._type_blurb_full,
               "already_detail": dlg._generated_full,
               "included": [dlg._run_row_label(r) + "  @ " + str(
                   Path(str(r.get("_origin_dir"))).relative_to(work))
                   for r in dlg._history],
               "ticked": [str(Path(str(r.get("_origin_dir"))).relative_to(work))
                          + " " + str(r.get("created"))
                          for r in dlg._runs_for_report()],
               "trend_points": len(getattr(dlg, "_trend_series", []) or [])}
        d.record["scenarios"][tag] = rec
        d.note(f"[{tag}] {what}")
        d.note(f"   label: {rec['label']!r}")
        d.note(f"   Already generated: {rec['already_line']!r}")
        for e in rec["report_shown"]:
            d.note(f"   | {e}")
        d.note(f"   ticked: {rec['ticked']}; trend points: {rec['trend_points']}")
        d.shot(dlg, f"{tag}-window")
        combo = dlg._saved_combo
        combo.showPopup()
        d.pump(900)
        d.shot(combo.view(), f"{tag}-report-shown-open")
        combo.hidePopup()
        d.pump(300)
        return rec

    def open_window(run, run_type):
        d.set_bar(run_type=run_type, run=run)
        d.pump(800)
        d.launch_tool("measurement_report")

    def dated(project, run):
        vroot = work / project / "runs" / run / "verifications"
        return sorted(p for p in vroot.iterdir()
                      if p.is_dir() and p.name[:4].isdigit())

    def ti3_in(folder):
        return sorted(folder.glob("*.ti3"))[0]

    import ui.dialogs.measurement_report_dialog as _M
    _orig_ofd = _M.open_files_dialog

    def _ofd(*a, **k):
        got = _orig_ofd(*a, **k)
        d.note(f"   [trace] open_files_dialog returned {got}")
        return got
    _M.open_files_dialog = _ofd

    def add(dlg, target, name):
        """Add Profile's Measurements, the file picked in ChromIQ's own
        dialog, then wait until the window holds one more source."""
        import time as _t
        before = len(dlg._sources)
        d.later(dlg._add_btn.click)
        yield 400
        ok = d.answer_file(target, name=name)
        t0 = _t.monotonic()
        while _t.monotonic() - t0 < 45 and len(dlg._sources) <= before:
            yield 250
        d.note(f"   [add] {Path(target).name} picked={ok}; sources "
               f"{before} -> {len(dlg._sources)} after "
               f"{_t.monotonic() - t0:.1f} s")
        yield 1500

    d.open_project(NAME)
    listing("00-as-shipped")

    # --- V1: Verification, one run: flat -------------------------------------
    open_window("run1", "Verification")
    yield 5000
    dlg = d.top_dialog("MeasurementReportDialog")
    state(dlg, "V1a-verification-as-opened", "run1, Run type Verification, "
          "as the window opens: on the newest report covering run1, which "
          "loads whatever else that report covers (beta 37, 'a report is "
          "shown whole')")
    dlg._saved_combo.setCurrentIndex(0)                  # New report…
    yield 1500
    state(dlg, "V1b-verification-one-run", "\"New report…\" chosen, so only "
          "run1's dates are in the list: no headings, names as before")

    # --- V2: add a run2 date: Run1 / Run2 --------------------------------------
    target = ti3_in(dated(NAME, "run2")[0])
    yield from add(dlg, target, "V2-add-file-dialog")
    state(dlg, "V2-verification-two-runs", "run1 as Verification with a run2 "
          "date added: Run1 / Run2 headings")

    # --- V3: add the second project's date: project headings ----------------
    target = ti3_in(dated(OTHER, "run1")[0])
    yield from add(dlg, target, "V3-add-file-dialog")
    state(dlg, "V3-verification-two-projects", "and a date of the second "
          "project added: project headings, runs under them, and 'Reports "
          "including multiple projects'")

    # --- V4: pick the report across projects -------------------------------
    combo = dlg._saved_combo
    heading_at = next((i for i in range(combo.count())
                       if combo.itemData(i) is None
                       and "multiple projects" in combo.itemText(i)), -1)
    pick = next((i for i in range(heading_at + 1, combo.count())
                 if combo.itemData(i)), -1)
    d.note(f"V4 picks row {pick}: {combo.itemText(pick)!r}")
    combo.setCurrentIndex(pick)
    yield 3000
    state(dlg, "V4-report-across-projects-selected", "the report across the "
          "two projects selected")
    dlg.close()
    yield 800

    # --- P1/P2: Profiling on run1 and run2 -----------------------------------
    for tag, run in (("P1-profiling-run1", "run1"),
                     ("P2-profiling-run2", "run2")):
        open_window(run, "Profiling")
        yield 5000
        dlg = d.top_dialog("MeasurementReportDialog")
        state(dlg, tag, f"{run}, Run type Profiling: every run's Printing "
              "record, grouped by run; the window opens on its own run's")
        if run == "run2":
            break
        dlg.close()
        yield 800

    # --- P3: run2 Profiling + the second project's profiling sheet ----------
    target = ti3_in(work / OTHER / "runs" / "run1")
    yield from add(dlg, target, "P3-add-file-dialog")
    state(dlg, "P3-profiling-two-projects", "run2 as Profiling with the "
          "second project's profiling sheet added")
    dlg.close()
    yield 800

    # --- G1: Generate on every sheet of the project (Profiling) --------------
    open_window("run1", "Profiling")
    yield 5000
    dlg = d.top_dialog("MeasurementReportDialog")
    dlg._saved_combo.setCurrentIndex(0)                  # New report…
    yield 1200
    dlg._select_all_btn.click()
    yield 1500
    pre = listing("G1-before")
    dlg._generate_btn.click()
    yield 3500
    post = listing("G1-after")
    new = sorted(set(post) - set(pre))
    d.record["scenarios"]["G1-files-written"] = new
    d.note("G1 new files:\n   " + "\n   ".join(new))
    state(dlg, "G1-generated-across-runs", "Generate on both runs' sheets, "
          "Profiling: a Printing record across runs")

    # --- D1: Delete it: M-REPORT-DELETE --------------------------------------
    pre = listing("D1-before")
    d.later(dlg._delete_report_btn.click)
    yield 1200
    said = d.answer("OK", name="D1-delete-question")
    # THE MOVE RUNS WHEN THE QUESTION'S OWN LOOP HAS RETURNED, which is after
    # this step: the first drive listed the folders 2.5 s later and found
    # nothing moved, while the log shows the move ten seconds on. Wait for it.
    import time as _t
    t0 = _t.monotonic()
    while _t.monotonic() - t0 < 30 and listing("D1-after") == pre:
        yield 500
    d.note(f"   [delete] the folders changed after {_t.monotonic() - t0:.1f} s")
    yield 1500
    post = listing("D1-after")
    d.record["scenarios"]["D1-changed"] = {
        "gone": sorted(set(pre) - set(post)),
        "new": sorted(set(post) - set(pre)), "question": said}
    d.note("D1 gone:\n   " + "\n   ".join(sorted(set(pre) - set(post))))
    d.note("D1 new:\n   " + "\n   ".join(sorted(set(post) - set(pre))))
    state(dlg, "D1-after-delete", "after Delete Selected Report")
    dlg.close()
    yield 800

    # --- the folder guide, as text ------------------------------------------
    import ui.file_guide as fg
    rows_ = [f"{f}  |  {where}  |  {text}" for _g, items in fg._rows()
             for (f, where, text, _o) in items if f == "report_*.json"]
    d.record["file_guide_report_rows"] = rows_
    for r in rows_:
        d.note(f"   GUIDE {r}")
    listing("99-at-the-end")


if __name__ == "__main__":
    out = Path(sys.argv[1])
    d = Drive(out, projects=[NAME, OTHER])
    # The pack's own reports/ folder holds the two reports across projects.
    if (DEMO_PACK / "reports").is_dir():
        shutil.copytree(DEMO_PACK / "reports", d.work / "reports")
    rc = d.run(script)
    print("done", rc)
    sys.exit(rc)
