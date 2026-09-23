#!/usr/bin/env python3
"""#182 K26 (Knut 5792484060, 5792576954), driven ON SCREEN.

    CHROMIQ_DEMO_PACK=<k26 pack> python scripts/drive_k26.py <out-dir> <group>

The pack holds Report-Limits-Report-Folders and its -Second project, the
Border-Conditions demo, Report-Limits-Red-X and a Report-Limits-Evenness built
by this tree's generator; ``_shared_reports`` is the pack's `<output>/reports`.

groups:
    calib    Run type Calibration: the Tools menu door and the Measure tab's
             report button; the window empty and locked, the red line.
    list     Verification and Profiling windows on Report-Folders: the names
             (Run1 / Multiple runs on Profiling), "for these measurements",
             "Report shown" grouped from the start, "Bound, and locked" gone
             from the report and in the "Judged against" help.
    shared   `<output>/reports/` absent through opening, adding the second
             project, listing; a cancelled "Save report as PDF…"; created by
             the first Generate across the two projects.
    gamut    Border-Conditions: the Colour accuracy graph's values against
             the within-gamut figures of the results table.
    rename   a Finder duplicate ("… copy") opened: the chooser, Rename, the
             report window on the renamed project; a second duplicate, Leave.
    redx     Red-X: nearest-neighbour heights, two crosses on one date one
             above the other, words at the left end; the evenness demo's
             noisy date with the paper as paper white.
"""
from __future__ import annotations

import json
import shutil
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from userdrive import DEMO_PACK, Drive                        # noqa: E402

FOLDERS = "Report-Limits-Report-Folders"
SECOND = "Report-Limits-Report-Folders-Second"
BORDER = "Report-Limits-Border-Conditions"
REDX = "Report-Limits-Red-X"
EVEN = "Report-Limits-Evenness"
PROJECTS = {"calib": [FOLDERS], "list": [FOLDERS, SECOND],
            "shared": [FOLDERS, SECOND], "gamut": [BORDER],
            "rename": [FOLDERS], "redx": [REDX, EVEN]}


def rows(dlg) -> list:
    """"Report shown" as the user reads it; headings marked."""
    combo = dlg._saved_combo
    out = []
    for i in range(combo.count()):
        text, key = combo.itemText(i), combo.itemData(i)
        if not text and key is None:
            out.append("-----")
            continue
        mark = ">" if i == combo.currentIndex() else " "
        out.append(f"{mark} [HEADING] {text}" if key is None
                   else f"{mark} {text}")
    return out


def tree(root: Path) -> list:
    return sorted(str(p.relative_to(root)) for p in root.rglob("*")
                  if p.is_file() and "reports" in p.parts)


def script_for(group):
    def script(d):
        rec = d.record
        rec["group"] = group
        rec["scenarios"] = {}

        def open_window(project, run, run_type):
            d.open_project(project)
            d.set_bar(run_type=run_type, run=run)
            d.pump(800)
            d.launch_tool("measurement_report")

        def wait_dialog():
            for _ in range(60):
                dlg = d.top_dialog("MeasurementReportDialog")
                if dlg is not None:
                    return dlg
                d.pump(250)
            return None

        def popup(dlg, tag):
            combo = dlg._saved_combo
            combo.showPopup()
            d.pump(900)
            d.shot(combo.view(), f"{tag}-report-shown-open")
            combo.hidePopup()
            d.pump(300)

        def list_state(dlg, tag, what):
            r = {"what": what, "label": dlg._saved_label.text(),
                 "report_shown": rows(dlg),
                 "already_line": dlg._type_blurb_full,
                 "included": [dlg._run_row_label(x) for x in dlg._history]}
            rec["scenarios"][tag] = r
            d.note(f"[{tag}] {what}")
            d.note(f"   label {r['label']!r}; already {r['already_line']!r}")
            for e in r["report_shown"]:
                d.note(f"   | {e}")
            d.shot(dlg, f"{tag}-window")
            popup(dlg, tag)
            return r

        # ------------------------------------------------------------------
        if group == "calib":
            d.settings.set("calibration_mode", True)
            d.win._apply_calibration_mode()
            d.pump(600)
            d.open_project(FOLDERS)
            d.set_bar(run_type="Calibration")
            d.pump(900)
            b = d.bar
            d.note("bar run type now: "
                   f"{b._type_combo.currentText()!r} "
                   f"({d.ctl.target.run_type!r})")
            d.shot(d.win, "C0-main-window-run-type-calibration")
            for door, how in (("C1-tools-menu", "tools"),
                              ("C2-measure-tab-button", "measure")):
                if how == "tools":
                    d.launch_tool("measurement_report")
                else:
                    d.goto_tab("measure")
                    d.shot(d.win, f"{door}-measure-tab")
                    d.later(d.win._tab_measure._m_report_btn.click)
                yield 2500
                dlg = wait_dialog()
                if dlg is None:
                    m = d.modal()
                    d.note(f"[{door}] NO report window; modal: "
                           f"{type(m).__name__ if m else None}: "
                           f"{d.modal_text(m)[:200] if m else ''}")
                    if m is not None:
                        d.shot(m, f"{door}-UNEXPECTED")
                    continue
                ctrls = {type(w).__name__ + ":" + (
                    w.text() if hasattr(w, "text") and callable(w.text)
                    else ""): w.isEnabled()
                    for w in dlg._calibration_controls()} \
                    if hasattr(dlg, "_calibration_controls") else {}
                note = getattr(dlg, "_calibration_note", None)
                r = {"sources": len(dlg._sources),
                     "report_text": dlg._view.toPlainText()[:200],
                     "red_line": note.text() if note else None,
                     "red_line_visible": bool(note and note.isVisible()),
                     "red_line_style": note.styleSheet() if note else None,
                     "tooltip": note.toolTip() if note else None,
                     "already_visible": dlg._type_blurb.isVisible(),
                     "controls_enabled": ctrls,
                     "graphs_visible": dlg._trend_tabs.isVisible()}
                rec["scenarios"][door] = r
                d.note(f"[{door}] sources={r['sources']} "
                       f"text={r['report_text']!r} red={r['red_line']!r} "
                       f"visible={r['red_line_visible']}")
                d.note("   enabled controls: "
                       f"{[k for k, v in ctrls.items() if v] or 'none'}")
                d.shot(dlg, f"{door}-report-window")
                dlg.close()
                yield 1000

        # ------------------------------------------------------------------
        if group == "list":
            open_window(FOLDERS, "run1", "Verification")
            yield 5000
            dlg = wait_dialog()
            dlg._saved_combo.setCurrentIndex(0)             # New report…
            dlg._saved_combo.activated.emit(0)
            yield 2500
            list_state(dlg, "L1-verification-one-run-new-report",
                       "run1, Verification, New report…: only run1's dates "
                       "listed; the pack's report across run1 and run2 is "
                       "offered, so the list is grouped from the start")
            # Bound, and locked: gone from the page, in the help
            text = dlg._view.toPlainText()
            rec["scenarios"]["B1-report-text"] = {
                "bound_and_locked_in_report": "Bound, and locked" in text}
            d.note(f"[B1] 'Bound, and locked' in the report text: "
                   f"{'Bound, and locked' in text}")
            from ui.tooltip_button import TooltipButton
            helps = [b for b in dlg.findChildren(TooltipButton)
                     if "Bound, and locked." in getattr(b, "_body", "")]
            d.note(f"[B2] help icons that explain bound and locked: "
                   f"{[b._title for b in helps]}")
            if helps:
                d.later(helps[0].click)
                yield 1200
                said = d.answer("", name="B2-judged-against-help")
                rec["scenarios"]["B2-help"] = {"shown": said}
            dlg.close()
            yield 1000

            open_window(FOLDERS, "run1", "Profiling")
            yield 5000
            dlg = wait_dialog()
            list_state(dlg, "P1-profiling-run1",
                       "run1, Profiling: names Run1 / Run2 / Multiple runs; "
                       "'Already generated for these measurements'")
            dlg.close()
            yield 1000

        # ------------------------------------------------------------------
        if group == "shared":
            work = d.work
            shared = work / "reports"
            d.note(f"[S0] {shared} exists at the start: {shared.exists()}")
            open_window(FOLDERS, "run1", "Verification")
            yield 5000
            dlg = wait_dialog()
            dlg._saved_combo.setCurrentIndex(0)
            dlg._saved_combo.activated.emit(0)
            yield 2000
            vroot = work / SECOND / "runs" / "run1" / "verifications"
            target = sorted(sorted(p for p in vroot.iterdir()
                                   if p.is_dir() and p.name[:4].isdigit())[0]
                            .glob("*.ti3"))[0]
            before = len(dlg._sources)
            d.later(dlg._add_btn.click)
            yield 500
            d.answer_file(target, name="S1-add-file-dialog")
            t0 = time.monotonic()
            while time.monotonic() - t0 < 45 and len(dlg._sources) <= before:
                yield 250
            yield 2000
            list_state(dlg, "S1-two-projects-listed",
                       "the second project's date added and listed")
            s1 = shared.exists()
            d.note(f"[S1] {shared} exists after opening, adding, listing: {s1}")
            rec["scenarios"]["S1-shared-exists"] = s1
            # a cancelled PDF
            dlg._select_all_btn.click()
            yield 1500
            d.later(dlg._pdf_btn.click)
            yield 1500
            info = d.read_file_dialog(name="S2-pdf-chooser-cancelled")
            yield 1500
            s2 = shared.exists()
            rec["scenarios"]["S2-after-cancelled-pdf"] = {
                "chooser": info, "shared_exists": s2,
                "contents": sorted(p.name for p in shared.iterdir())
                if s2 else None}
            d.note(f"[S2] after a CANCELLED 'Save report as PDF…': "
                   f"{shared} exists: {s2}")
            if s2 and not any(shared.iterdir()):
                shutil.rmtree(shared)
                d.note("   (empty folder removed so S3 measures Generate "
                       "alone)")
            # Generate across the two projects
            dlg._saved_combo.setCurrentIndex(0)
            dlg._saved_combo.activated.emit(0)
            yield 1500
            dlg._select_all_btn.click()
            yield 1500
            d.note(f"[S3] Generate enabled: {dlg._generate_btn.isEnabled()}; "
                   f"tooltip {dlg._generate_btn.toolTip()[:160]!r}")
            d.later(dlg._generate_btn.click)
            yield 800
            d.answer("New", name="S3-generate-question", within_ms=3000)
            t0 = time.monotonic()
            while time.monotonic() - t0 < 60 and not shared.exists():
                yield 500
            yield 2500
            s3 = shared.exists()
            rec["scenarios"]["S3-after-generate"] = {
                "shared_exists": s3,
                "files": sorted(p.name for p in shared.iterdir())
                if s3 else None}
            d.note(f"[S3] after Generate across the two projects: {shared} "
                   f"exists: {s3}; files "
                   f"{rec['scenarios']['S3-after-generate']['files']}")
            list_state(dlg, "S3-after-generate", "after Generate across the "
                       "two projects")
            dlg.close()
            yield 1000

        # ------------------------------------------------------------------
        if group == "gamut":
            open_window(BORDER, "run1", "Verification")
            yield 5000
            dlg = wait_dialog()
            dlg._saved_combo.setCurrentIndex(0)
            dlg._saved_combo.activated.emit(0)
            yield 2000
            dlg._select_all_btn.click()
            yield 2000
            d.later(dlg._generate_btn.click)
            yield 800
            d.answer("New", within_ms=2500)
            for _ in range(60):
                yield 1000
                if len(dlg._trend_series or []) >= 2:
                    break
            yield 1500
            from workflow.measurement_report import graded_de00
            pts = []
            for r, pt in zip(dlg._runs_for_report(), dlg._trend_series):
                g, src = graded_de00(r)
                pts.append({"date": str(pt.get("created"))[:16],
                            "plotted_avg_all": pt.get("avg_all"),
                            "judged_avg_all": g.get("avg_all"),
                            "all_patches_avg_all": (r.get("de00") or {})
                            .get("avg_all"),
                            "population": pt.get("de00_population")})
            rec["scenarios"]["G1"] = {
                "legend": [m[0] for m in dlg._trend_de._metrics],
                "about": dlg._trend_extras(dlg._trend_de)["about"],
                "points": pts}
            d.note(f"[G1] legend {rec['scenarios']['G1']['legend']}")
            for p in pts:
                d.note(f"   {p}")
            t = dlg._trend_tabs
            t.setCurrentIndex(t.indexOf(dlg._trend_de))
            d.shot(dlg, "G1-colour-accuracy-within-gamut")
            dlg.close()
            yield 1000

        # ------------------------------------------------------------------
        if group == "rename":
            work = d.work
            for dup in (f"{FOLDERS} copy", f"{FOLDERS} copy 2"):
                shutil.copytree(work / FOLDERS, work / dup)
            rec["scenarios"]["R0-folders"] = sorted(
                p.name for p in work.iterdir())
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(0, lambda: d.win._tab_chart.open_project_manifest(
                work / f"{FOLDERS} copy" / "project.json"))
            yield 400
            said = d.answer("Rename the project", name="R1-chooser")
            yield 2500
            new = work / f"{FOLDERS}-copy"
            files = sorted(p.name for p in (new / "runs" / "run1").glob(
                "*.ti*")) if new.is_dir() else []
            rec["scenarios"]["R1"] = {
                "chooser_text": said, "renamed_folder_exists": new.is_dir(),
                "old_folder_exists": (work / f"{FOLDERS} copy").exists(),
                "run1_files": files,
                "name_field": d.win._tab_chart._manual_target_name_edit.text()}
            d.note(f"[R1] {rec['scenarios']['R1']}")
            d.shot(d.win, "R1-main-window-after-rename")
            d.set_bar(run_type="Verification", run="run1")
            d.pump(800)
            d.launch_tool("measurement_report")
            yield 5000
            dlg = wait_dialog()
            list_state(dlg, "R2-report-window-on-renamed-copy",
                       "the renamed copy's report window")
            rec["scenarios"]["R2-sources"] = len(dlg._sources)
            dlg.close()
            yield 1000
            c2 = work / f"{FOLDERS} copy 2"

            def named(root):
                """The files that carry the project's name, and the
                manifest: what a rename would change. (Opening a project
                writes its own run state as well, whatever is answered.)"""
                return sorted(str(p.relative_to(root)) for p in root.rglob("*")
                              if p.name.startswith(FOLDERS)) + [
                    (root / "project.json").read_text(encoding="utf-8")]
            before = named(c2)
            QTimer.singleShot(0, lambda: d.win._tab_chart.open_project_manifest(
                work / f"{FOLDERS} copy 2" / "project.json"))
            yield 400
            said = d.answer("Leave it as it is", name="R3-chooser-leave")
            yield 2500
            after = named(c2)
            rec["scenarios"]["R3"] = {"unchanged": before == after,
                                      "chooser_text": said}
            d.note(f"[R3] Leave it as it is: the named files and project.json "
                   f"unchanged = {before == after}; folder still "
                   f"'{c2.name}': {c2.is_dir()}")

        # ------------------------------------------------------------------
        if group == "redx":
            from drive_k25_trend_graphs import chart_info
            open_window(REDX, "run1", "Verification")
            yield 5000
            dlg = wait_dialog()
            dlg._saved_combo.setCurrentIndex(0)
            dlg._saved_combo.activated.emit(0)
            yield 1500
            dlg._select_all_btn.click()
            yield 1500
            d.later(dlg._generate_btn.click)
            yield 800
            d.answer("New", within_ms=2500)
            for _ in range(90):
                yield 1000
                if len(dlg._trend_series or []) >= 7:
                    break
            yield 1500
            t = dlg._trend_tabs
            for key, tag in (("evenness", "X1-evenness"),
                             ("repeat", "X2-repeatability")):
                c = dlg._trend_groups[key]
                if not t.isTabVisible(t.indexOf(c)):
                    d.note(f"[{tag}] tab hidden")
                    continue
                t.setCurrentIndex(t.indexOf(c))
                d.pump(700)
                info = chart_info(c)
                rec["scenarios"][tag] = info
                d.note(f"[{tag}] dates {info['dates']}")
                for x in info["red_x"]:
                    d.note(f"   RED X {x['date']} metric {x['metric']} "
                           f"height {x['height']}")
                for h in info["hits"]:
                    d.note(f"   hit {h['rect']} {h['text'][:50]!r}")
                d.shot(dlg, tag)
            dlg.close()
            yield 1000
            # the evenness demo, noisy date, as built by this tree
            open_window(EVEN, "run1", "Verification")
            yield 5000
            dlg = wait_dialog()
            dlg._saved_combo.setCurrentIndex(0)
            dlg._saved_combo.activated.emit(0)
            yield 1500
            from PyQt6.QtCore import Qt
            lst = dlg._profile_list
            for i in range(lst.count()):
                it = lst.item(i)
                if it.flags() & Qt.ItemFlag.ItemIsUserCheckable:
                    it.setCheckState(Qt.CheckState.Checked
                                     if "2026-10-22" in it.text()
                                     else Qt.CheckState.Unchecked)
            yield 1500
            d.later(dlg._generate_btn.click)
            yield 800
            d.answer("New", within_ms=2500)
            yield 5000
            text = dlg._view.toPlainText()
            i = text.find("Paper white")
            rec["scenarios"]["E1"] = {
                "paper_white_lines": [ln for ln in text.splitlines()
                                      if ln.startswith("White")
                                      or "Paper white" in ln][:6]}
            d.note(f"[E1] {rec['scenarios']['E1']}")
            d.shot(dlg, "E1-evenness-noisy-date-top")
            view = dlg._view
            if i >= 0:
                cur = view.document().find("Paper white")
                if not cur.isNull():
                    view.setTextCursor(cur)
                    view.ensureCursorVisible()
                    d.pump(600)
            d.shot(dlg, "E1-evenness-noisy-date-paper-white")
            dlg.close()
            yield 1000
    return script


if __name__ == "__main__":
    out, group = Path(sys.argv[1]), sys.argv[2]
    d = Drive(out, projects=PROJECTS[group])
    if group == "list" and (DEMO_PACK / "_shared_reports").is_dir():
        shutil.copytree(DEMO_PACK / "_shared_reports", d.work / "reports")
    rc = d.run(script_for(group))
    (out / "driver-report.json").write_text(
        json.dumps(d.record, indent=2, default=str), encoding="utf-8")
    print("done", rc)
    sys.exit(rc)
