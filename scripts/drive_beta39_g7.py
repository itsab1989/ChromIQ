#!/usr/bin/env python3
"""#182 beta 39, G7, driven ON SCREEN: Generate report across profile runs and
across projects, in Verification, Profiling and Calibration.

Knut, 5794078008 (point 3): *"a user may need to see how a printers profile
has changed across different periods that are saved as different projects"*;
5794311113: *"the report's own limit set applies to every included
measurement, whatever each run is bound to."*

    CHROMIQ_DEMO_PACK=<pack> python scripts/drive_beta39_g7.py <out>

Every scenario lists the report files of the three projects and of the
folder across projects before and after, records "Report shown" row by row
and the limit-set controls, and photographs the window with
`onscreen_capture.capture_window`. Preferences > Calibration options is
switched ON in the SANDBOX settings file before the main window is built.
The pack's own `reports/` folder is NOT copied, so the drive shows the folder
across projects being made by the first report across projects.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

FOLDERS = "Report-Limits-Report-Folders"
SECOND = "Report-Limits-Report-Folders-Second"


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
        judged = sorted({(m.get("judged") or {}).get("compliance", {})
                         .get("set_id", "-")
                         for m in doc.get("measurements") or []
                         if m.get("judged")})
        out.append(f"{p.relative_to(root)}  [{role}] "
                   f"type={doc.get('type') or rep.get('report_type') or '-'} "
                   f"set={(doc.get('compliance') or {}).get('set_id', '-')} "
                   f"judged={','.join(judged) or '-'} "
                   f"updated={len(doc.get('updated') or [])} "
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
            mark = ">" if i == combo.currentIndex() else " "
            out.append(f"{mark} {'[HEADING] ' if key is None else ''}{text}")
        return out

    def state(dlg, tag, what, *, popup=False):
        rec = {"what": what,
               "window_kind": dlg._window_kind(),
               "report_shown": rows(dlg),
               "already_line": dlg._type_blurb_full,
               "judged_against": dlg._set_combo.currentText(),
               "judged_enabled": dlg._set_combo.isEnabled(),
               "judged_tooltip": dlg._set_combo.toolTip(),
               "limits_button": (dlg._limits_btn.text(),
                                 dlg._limits_btn.isEnabled()),
               "unlock_enabled": dlg._unlock_check.isEnabled(),
               "generate_enabled": dlg._generate_btn.isEnabled(),
               "generate_tooltip": dlg._generate_btn.toolTip(),
               "included": [str(Path(str(r.get("_origin_dir"))).relative_to(
                   work)) + ("" if dlg._run_key(r) not in dlg._hidden_runs
                             else "  (unticked)")
                   for r in dlg._history],
               "page_sets": sorted({str((r.get("compliance") or {})
                                        .get("set_id")) for r in
                                    dlg._runs_for_report()})}
        d.record["scenarios"][tag] = rec
        d.note(f"[{tag}] {what}")
        for k in ("window_kind", "already_line", "judged_against",
                  "judged_enabled", "judged_tooltip", "limits_button",
                  "unlock_enabled", "generate_enabled", "generate_tooltip",
                  "page_sets"):
            d.note(f"   {k}: {rec[k]!r}")
        for e in rec["report_shown"]:
            d.note(f"   | {e}")
        for e in rec["included"]:
            d.note(f"   included: {e}")
        d.shot(dlg, f"{tag}")
        if popup:
            combo = dlg._saved_combo
            combo.showPopup()
            d.pump(1200)
            d.shot(combo.view(), f"{tag}-report-shown-open")
            combo.hidePopup()
            d.pump(300)
        return rec

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
        new = sorted(set(post) - set(pre))
        gone = sorted(set(pre) - set(post))
        d.note(f"   [{tag}] folders after {time.monotonic() - t0:.1f} s")
        d.note("   new:\n      " + "\n      ".join(new or ["(none)"]))
        d.note("   gone:\n      " + "\n      ".join(gone or ["(none)"]))
        d.record["scenarios"][tag] = {"new": new, "gone": gone}

    def new_report_everything(dlg, set_id=None):
        dlg._saved_combo.setCurrentIndex(0)
        yield 1500
        dlg._select_all_btn.click()
        yield 1200
        if set_id is not None:
            i = dlg._set_combo.findData(set_id)
            if i >= 0:
                dlg._set_combo.setCurrentIndex(i)
                yield 1500

    def generate(dlg, tag, answer=None):
        pre = listing(f"{tag}-before")
        d.later(dlg._generate_btn.click)
        yield 800
        if answer:
            d.answer(answer, name=f"{tag}-question")
            yield 600
        yield from wait_change(pre, f"{tag}-after")

    def select(dlg, key):
        i = dlg._saved_combo.findData(key)
        dlg._saved_combo.setCurrentIndex(i)
        return i

    def delete(dlg, tag):
        pre = listing(f"{tag}-before")
        d.later(dlg._delete_report_btn.click)
        yield 1200
        d.answer("OK", name=f"{tag}-question")
        yield 600
        yield from wait_change(pre, f"{tag}-after")

    def dates(project, run):
        return sorted((work / project / "runs" / run / "verifications")
                      .glob("*/*.ti3"))

    def sheet(project, run):
        return work / project / "runs" / run / f"{project}.ti3"

    def cal(project):
        return work / project / "cal" / f"{project}-cal.ti3"

    d.record["calibration_mode_in_sandbox"] = bool(
        d.settings.get("calibration_mode", False))
    d.open_project(FOLDERS)
    listing("00-as-copied")
    d.record["across_folder_before"] = (work / "reports").is_dir()
    d.note(f"folder across projects before the drive: "
           f"{d.record['across_folder_before']}")

    # ---- V: Verification across two runs of one project -------------------
    d.set_bar(run_type="Verification", run="run1")
    yield 800
    d.launch_tool("measurement_report")
    yield 5000
    dlg = d.top_dialog("MeasurementReportDialog")
    state(dlg, "V0-opened", "Verification, run1: the window as it opens")
    yield from new_report_everything(dlg)
    yield from add(dlg, dates(FOLDERS, "run2")[-1], "V1-add-file-dialog")
    yield from new_report_everything(dlg, "chromiq_quick")
    state(dlg, "V1-two-runs-ticked", "run2's newest date added, everything "
          "ticked, Judged against = ChromIQ quick (neither run is bound to it)")
    yield from generate(dlg, "V2-generate-across-runs")
    state(dlg, "V2-generated", "after Generate: one document in "
          "<project>/reports/, listed under Reports including multiple runs",
          popup=True)
    key_v = dlg._loaded_doc_id
    dlg._detail_check.setChecked(not dlg._detail_check.isChecked())
    yield 1200
    yield from generate(dlg, "V3-update", answer="Update")
    state(dlg, "V3-updated", "after Update: the same file, rewritten, its "
          "old copy in reports/old/")
    select(dlg, key_v)
    yield 2500
    yield from delete(dlg, "V4-delete")
    state(dlg, "V4-deleted", "after Delete Selected Report")
    # ---- V5: Verification across two projects -----------------------------
    yield from new_report_everything(dlg)
    yield from add(dlg, dates(SECOND, "run1")[-1], "V5-add-file-dialog")
    yield from new_report_everything(dlg)
    state(dlg, "V5-two-projects-ticked", "a date of the second project "
          "added: three runs of two projects ticked")
    yield from generate(dlg, "V6-generate-across-projects")
    state(dlg, "V6-generated", "after Generate: <ChromIQ folder>/reports/ "
          "made by this write, the report under Reports including multiple "
          "projects", popup=True)
    dlg.close()
    yield 1200

    # ---- P: Profiling across runs, then across projects ------------------
    d.later(lambda: d.set_bar(run_type="Profiling", run="run1"))
    yield 1500
    m = d.modal()
    if m is not None and m.isVisible():
        said = d.modal_text(m)
        d.note(f"   [bar] a question came on Profiling: {said[:200]!r}")
        for word in ("Keep", "Cancel", "OK", "Close"):
            if d.answer(word, name="P0-bar-question", within_ms=1500):
                break
    yield 1500
    d.launch_tool("measurement_report")
    yield 5000
    dlg = d.top_dialog("MeasurementReportDialog")
    state(dlg, "P0-opened", "Profiling, run1: the window as it opens")
    yield from new_report_everything(dlg)
    state(dlg, "P1-runs-ticked", "every run's profiling sheet ticked")
    yield from generate(dlg, "P2-generate-across-runs")
    state(dlg, "P2-generated", "after Generate across runs", popup=True)
    yield from new_report_everything(dlg)
    yield from add(dlg, sheet(SECOND, "run1"), "P3-add-file-dialog")
    yield from new_report_everything(dlg)
    state(dlg, "P3-two-projects-ticked", "the second project's sheet added")
    yield from generate(dlg, "P4-generate-across-projects")
    state(dlg, "P4-generated", "after Generate across projects", popup=True)
    key_p = dlg._loaded_doc_id
    dlg._detail_check.setChecked(not dlg._detail_check.isChecked())
    yield 1200
    yield from generate(dlg, "P5-update", answer="Update")
    state(dlg, "P5-updated", "after Update of the report across projects")
    select(dlg, key_p)
    yield 2500
    yield from delete(dlg, "P6-delete")
    state(dlg, "P6-deleted", "after Delete Selected Report")
    dlg.close()
    yield 1200

    # ---- C: Calibration across projects ----------------------------------
    d.set_bar(run_type="Calibration")
    yield 1200
    d.launch_tool("measurement_report")
    yield 5000
    dlg = d.top_dialog("MeasurementReportDialog")
    state(dlg, "C0-opened", "Calibration: the window on the project's "
          "calibration")
    yield from new_report_everything(dlg)
    yield from add(dlg, cal(SECOND), "C1-add-file-dialog")
    yield from new_report_everything(dlg)
    state(dlg, "C1-two-calibrations-ticked", "the second project's "
          "calibration added, both ticked")
    yield from generate(dlg, "C2-generate-across-projects")
    state(dlg, "C2-generated", "after Generate: All cals in the folder "
          "across projects", popup=True)
    key_c = dlg._loaded_doc_id
    dlg._detail_check.setChecked(not dlg._detail_check.isChecked())
    yield 1200
    yield from generate(dlg, "C3-update", answer="Update")
    state(dlg, "C3-updated", "after Update")
    select(dlg, key_c)
    yield 2500
    yield from delete(dlg, "C4-delete")
    state(dlg, "C4-deleted", "after Delete Selected Report")
    dlg.close()
    yield 1000
    d.record["across_folder_after"] = (work / "reports").is_dir()
    listing("99-at-the-end")


if __name__ == "__main__":
    out = Path(sys.argv[1]).resolve()
    sb = out / "sandbox"
    (sb / "presets").mkdir(parents=True, exist_ok=True)
    os.environ["CHROMIQ_SETTINGS_FILE"] = str(sb / "settings.ini")
    os.environ["CHROMIQ_PRESETS_DIR"] = str(sb / "presets")
    from userdrive import Drive                               # noqa: E402
    from core.settings import AppSettings                     # noqa: E402
    AppSettings().set("calibration_mode", True)
    d = Drive(out, projects=[FOLDERS, SECOND])
    rc = d.run(script)
    print("done", rc)
    sys.exit(rc)
