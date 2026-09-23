#!/usr/bin/env python3
"""#182 beta 39, driven ON SCREEN: Run type Calibration makes reports.

Knut, 5794078008 (confirmed 5794311113): every report type but the Printing
record; the calibration's measurement in ``<project>/cal/``, its reports in
``<project>/cal/reports/``; another project's calibration may be added; a
report across projects in ``<ChromIQ folder>/reports/``; names Cal / Multiple
cals / All cals; "Report shown" grouped by project.

    CHROMIQ_DEMO_PACK=<pack> python scripts/drive_beta39_calibration.py <out>

Preferences > Calibration options is switched ON in the SANDBOX settings file
before the main window is built, exactly as a user's saved preference would
be. Every scenario lists the report files of the three projects and the
pack's own ``reports/`` before and after, records "Report shown" row by row,
photographs the window and the opened pulldowns.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

FOLDERS = "Report-Limits-Report-Folders"
SECOND = "Report-Limits-Report-Folders-Second"
TYPES = "Report-Limits-Report-Types"


def tree(root: Path) -> "list[str]":
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
                out.append(f"{mark} [HEADING"
                           f"{'' if item.isEnabled() else ', not selectable'}]"
                           f" {text}")
            else:
                out.append(f"{mark} {text}")
        return out

    def types(dlg):
        combo = dlg._type_combo
        out = []
        for i in range(combo.count()):
            item = combo.model().item(i)
            if not combo.itemText(i):
                continue
            out.append(f"{'>' if i == combo.currentIndex() else ' '} "
                       f"{combo.itemText(i)}"
                       f"{'' if item.isEnabled() else '  (greyed: ' + str(combo.itemData(i, 3) or '') + ')'}")
        return out

    def state(dlg, tag, what, *, popups=True):
        rec = {"what": what,
               "window_kind": dlg._window_kind(),
               "label": dlg._saved_label.text(),
               "report_shown": rows(dlg),
               "already_line": dlg._type_blurb_full,
               "report_type": types(dlg),
               "generate_enabled": dlg._generate_btn.isEnabled(),
               "generate_tooltip": dlg._generate_btn.toolTip(),
               "included": [str(Path(str(r.get("_origin_dir"))).relative_to(
                   work)) + "  " + str(r.get("created"))
                   for r in dlg._history]}
        d.record["scenarios"][tag] = rec
        d.note(f"[{tag}] {what}")
        d.note(f"   kind: {rec['window_kind']}; label: {rec['label']!r}")
        d.note(f"   Already generated: {rec['already_line']!r}")
        for e in rec["report_shown"]:
            d.note(f"   | {e}")
        d.note(f"   included: {rec['included']}")
        d.note(f"   Generate enabled: {rec['generate_enabled']}; tooltip: "
               f"{rec['generate_tooltip']!r}")
        d.shot(dlg, f"{tag}-window")
        if popups:
            combo = dlg._saved_combo
            combo.showPopup()
            d.pump(900)
            d.shot(combo.view(), f"{tag}-report-shown-open")
            combo.hidePopup()
            d.pump(300)
        return rec

    def cal_ti3(project):
        return work / project / "cal" / f"{project}-cal.ti3"

    def add(dlg, target, name):
        before = len(dlg._sources)
        d.later(dlg._add_btn.click)
        yield 400
        ok = d.answer_file(target, name=name)
        t0 = time.monotonic()
        while time.monotonic() - t0 < 45 and len(dlg._sources) <= before:
            yield 250
        d.note(f"   [add] {Path(target).relative_to(work)} picked={ok}; "
               f"sources {before} -> {len(dlg._sources)}")
        yield 1500

    def wait_change(pre, tag, limit=30):
        t0 = time.monotonic()
        while time.monotonic() - t0 < limit and listing(tag) == pre:
            yield 500
        post = listing(tag)
        d.note(f"   [{tag}] the folders changed after "
               f"{time.monotonic() - t0:.1f} s")
        d.note("   new:\n      " + "\n      ".join(sorted(set(post) - set(pre))
                                                   or ["(none)"]))
        d.note("   gone:\n      " + "\n      ".join(sorted(set(pre) - set(post))
                                                    or ["(none)"]))
        d.record["scenarios"][tag] = {
            "new": sorted(set(post) - set(pre)),
            "gone": sorted(set(pre) - set(post))}

    d.record["calibration_mode_in_sandbox"] = bool(
        d.settings.get("calibration_mode", False))
    d.note(f"Preferences > Calibration options (sandbox): "
           f"{d.record['calibration_mode_in_sandbox']}")
    d.open_project(FOLDERS)
    listing("00-as-shipped")
    shared_before = (work / "reports").is_dir()
    tab = d.win._tab_measure
    if PART == "part2":
        yield from part2(d, work, state, listing, wait_change, cal_ti3, tab,
                         shared_before)
        return

    # --- C1: Tools ▸ Measurement report under Run type Calibration ----------
    d.set_bar(run_type="Calibration")
    yield 800
    d.note(f"   bar run type: {d.ctl.target.run_type!r}")
    d.launch_tool("measurement_report")
    yield 5000
    dlg = d.top_dialog("MeasurementReportDialog")
    state(dlg, "C1-calibration-window", "Run type Calibration, Tools > "
          "Measurement report: the window on the project's calibration, as "
          "it opens (the newest report covering it)")
    combo = dlg._type_combo
    combo.showPopup()
    yield 900
    d.shot(combo.view(), "C1-report-type-open")
    combo.hidePopup()
    yield 300

    # --- C2: New report… then Generate: one file in cal/reports/ -----------
    dlg._saved_combo.setCurrentIndex(0)
    yield 2000
    state(dlg, "C2a-new-report", "\"New report…\": the Preferences type, "
          "the calibration alone ticked", popups=False)
    pre = listing("C2-before")
    dlg._generate_btn.click()
    yield 1500
    yield from wait_change(pre, "C2-after-generate")
    state(dlg, "C2b-generated", "after Generate report: the new report is "
          "in the list, named Cal, and on screen")

    # --- C3: Delete it -------------------------------------------------------
    pre = listing("C3-before")
    d.later(dlg._delete_report_btn.click)
    yield 1200
    said = d.answer("OK", name="C3-delete-question")
    d.note(f"   [delete] answered {said!r}")
    yield from wait_change(pre, "C3-after-delete")
    state(dlg, "C3-after-delete", "after Delete Selected Report",
          popups=False)

    # --- C4: another project's calibration added -----------------------------
    dlg._saved_combo.setCurrentIndex(0)
    yield 1500
    yield from add(dlg, cal_ti3(SECOND), "C4-add-file-dialog")
    state(dlg, "C4-two-calibrations", "the second project's calibration "
          "added: grouped by project, Generate greyed")

    # --- C5: the reports across projects, selected -------------------------
    combo = dlg._saved_combo
    for tag in ("Multiple cals", "All cals"):
        at = next((i for i in range(combo.count())
                   if combo.itemData(i) and combo.itemText(i).endswith(tag)),
                  -1)
        d.note(f"C5 picks {tag!r} at row {at}: {combo.itemText(at)!r}")
        if at < 0:
            continue
        combo.setCurrentIndex(at)
        yield 3500
        state(dlg, f"C5-{tag.replace(' ', '-').lower()}-selected",
              f"the report named {tag!r} selected: it loads the calibrations "
              "it covers")
        combo.setCurrentIndex(0)
        yield 2000
    dlg.close()
    yield 800

    # --- C6: the Measure tab's own report button -----------------------------
    d.goto_tab("measure")
    yield 800
    tab = d.win._tab_measure
    d.later(tab._m_report_btn.click)
    yield 5000
    dlg = d.top_dialog("MeasurementReportDialog")
    if dlg is not None:
        state(dlg, "C6-measure-tab-button", "the Measure tab's "
              "\"Measurement report\" button under Run type Calibration",
              popups=False)
        dlg.close()
        yield 800
    else:
        d.note("[C6] no report window came")

    # --- C7: the other run types do not list the calibration's reports -------
    # VERIFICATION ONLY: switching the bar to Profiling on run1 asks "This
    # chart already has a measurement" (a real modal the first drive met and
    # was blocked by); the Profiling half is pinned by
    # test_a_calibration_s_reports_are_not_counted_on_a_profiling_window.
    for rt in ("Verification",):
        d.set_bar(run_type=rt, run="run1")
        yield 800
        d.launch_tool("measurement_report")
        yield 5000
        dlg = d.top_dialog("MeasurementReportDialog")
        rec = state(dlg, f"C7-{rt.lower()}-control", f"Run type {rt}, run1: "
                    "the control; no calibration report may be listed",
                    popups=False)
        cal_rows = [r for r in rec["report_shown"]
                    if r.rstrip().endswith(("Cal", "cals"))]
        d.note(f"   calibration names in the list: {cal_rows}")
        dlg.close()
        yield 800

    yield from part2(d, work, state, listing, wait_change, cal_ti3, tab,
                     shared_before, again=False)


def part2(d, work, state, listing, wait_change, cal_ti3, tab, shared_before,
          again=True):
    if again:
        # C1 again, for the two pulldown photographs the first drive lost
        # (the popup was captured before it was drawn).
        d.set_bar(run_type="Calibration")
        yield 800
        d.launch_tool("measurement_report")
        yield 5000
        dlg = d.top_dialog("MeasurementReportDialog")
        state(dlg, "C1b-calibration-window-again", "the same window, opened "
              "again, for the pulldown photographs")
        combo = dlg._type_combo
        combo.showPopup()
        yield 1500
        d.shot(combo.view(), "C1b-report-type-open")
        combo.hidePopup()
        yield 300
        dlg.close()
        yield 800
    # --- C8: the measurement-finished signal for the calibration ---------
    # No instrument is attached, so no chart can be measured; the Measure
    # tab's own `measure_finished` signal is what a finished measurement
    # emits, and `_maybe_save_measurement_report` is connected to it.
    d.set_bar(run_type="Calibration")
    yield 800
    tab._save_report_cb.setChecked(True) if getattr(
        tab, "_save_report_cb", None) is not None else None
    pre = listing("C8-before")
    tab.measure_finished.emit(cal_ti3(FOLDERS))
    yield 1500
    yield from wait_change(pre, "C8-after-measure-finished")
    new = d.record["scenarios"]["C8-after-measure-finished"]["new"]
    for line in new:
        p = work / line.split("  ")[0]
        rep = json.loads(p.read_text(encoding="utf-8"))
        d.note(f"   automatic report: type={rep['document']['type']} "
               f"scope={rep['document'].get('scope')} "
               f"verdict set={(rep.get('compliance') or {}).get('set_id')}")
    d.record["shared_reports_before"] = shared_before
    d.record["shared_reports_after"] = (work / "reports").is_dir()
    listing("99-at-the-end")


PART = ""

if __name__ == "__main__":
    out = Path(sys.argv[1]).resolve()
    PART = sys.argv[2] if len(sys.argv) > 2 else ""
    sb = out / "sandbox"
    (sb / "presets").mkdir(parents=True, exist_ok=True)
    os.environ["CHROMIQ_SETTINGS_FILE"] = str(sb / "settings.ini")
    os.environ["CHROMIQ_PRESETS_DIR"] = str(sb / "presets")
    from userdrive import DEMO_PACK, Drive                    # noqa: E402
    # PREFERENCES > CALIBRATION OPTIONS ON, IN THE SANDBOX, before the main
    # window is built: the Run type pulldown offers "Calibration" only then.
    from core.settings import AppSettings                     # noqa: E402
    AppSettings().set("calibration_mode", True)
    d = Drive(out, projects=[FOLDERS, SECOND, TYPES])
    if (DEMO_PACK / "reports").is_dir():
        shutil.copytree(DEMO_PACK / "reports", d.work / "reports")
    rc = d.run(script)
    print("done", rc)
    sys.exit(rc)
