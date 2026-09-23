#!/usr/bin/env python3
"""#182 beta 38, E2 and E4 (B8-828, B8-829), driven ON SCREEN as a user.

On the project `scripts/make_evenness_demo.py` builds (Report-Limits-Evenness),
copied into a sandbox by `userdrive.Drive`:

    A  Create Chart on run4 (Knut's 572-patch i1Pro A4 chart): the "Measured
       from Preview" panel, whose four margins are the ones the coverage is
       computed from;
    B  the Measurement Report on run4: both evenness rows N-A, the note "the
       patches on page 1 of the measured chart cover 68.3 % of the page; at
       least 75 % is needed";
    C  the Measurement Report on run5 (i1Pro 3 Plus, two pages of 11 x 14):
       the same, for pages 1 and 2;
    D  the Measurement Report on run1 (837 patches, 80 % covered): the even
       date still judged, PASS / PASS;
    E  "Which presets can be used for verification?": the i1Pro 3 Plus
       presets (one page, two pages, A3) and the 572 and 837 i1Pro presets;
    F  the Measure tab's pre-flight on run3 (837, covered) and on run4 with
       its measurement moved aside (572, not covered).

    export CHROMIQ_DEMO_PACK=<folder holding Report-Limits-Evenness>
    python scripts/drive_beta38_evenness_followups.py <out-dir>
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from userdrive import Drive                                   # noqa: E402
from drive_evenness import (NAME, ROWS, _all_items, _detail,   # noqa: E402
                            _report_text, _scroll_to)


def _cov_lines(text: str) -> "list[str]":
    return [ln.strip() for ln in text.splitlines()
            if "cover" in ln and ("% of" in ln or "page" in ln)
            or ln.strip().startswith(ROWS)]


def _report(d, run: str, tag: str):
    d.set_bar(run_type="Verification", run=run)
    yield 900
    d.launch_tool("measurement_report")
    yield 5000
    dlg = d.top_dialog("MeasurementReportDialog")
    text = _report_text(dlg)
    lines = _cov_lines(text)
    d.record[tag] = {"shown": dlg._saved_combo.currentText(), "lines": lines,
                     "strip": dlg._mismatch_full}
    d.note(f"{tag} {run}: report shown {dlg._saved_combo.currentText()!r}")
    for ln in lines:
        d.note(f"   {tag} | {ln[:300]}")
    d.note(f"   {tag} strip | {dlg._mismatch_full[:400]!r}")
    _scroll_to(dlg, "Report Results")
    dlg._view.find(ROWS[0])
    dlg._view.ensureCursorVisible()
    sb = dlg._view.verticalScrollBar()
    sb.setValue(sb.value() + 260)
    yield 700
    d.shot(dlg, f"{tag}-{run}-evenness-rows")
    _scroll_to(dlg, "Notes on the verdicts above")
    yield 700
    d.shot(dlg, f"{tag}-{run}-notes")
    dlg.reject()
    yield 1200


def script(d):
    rec = d.record
    d.open_project(NAME)
    yield 800

    # -- A: Measured from Preview on the 572 chart ------------------------
    d.set_bar(run_type="Profiling", run="run4")
    d.goto_tab("chart")
    yield 4000
    tab = d.win._tab_chart
    rep = getattr(tab, "_margin_report", None)
    if rep is not None:
        rec["A_panel"] = {k: round(float(getattr(rep, k)), 2) for k in
                          ("left_mm", "right_mm", "top_mm", "bottom_mm",
                           "page_w_mm", "page_h_mm")}
        from workflow.page_coverage import coverage_of
        rec["A_panel"]["coverage"] = round(coverage_of(
            rep.page_w_mm, rep.page_h_mm, rep.left_mm, rep.right_mm,
            rep.top_mm, rep.bottom_mm), 4)
    d.note(f"A run4 Measured from Preview: {rec.get('A_panel')}")
    d.shot(d.win, "A-run4-create-chart-measured-from-preview")

    # -- B, C, D: the report --------------------------------------------------
    yield from _report(d, "run4", "B")
    yield from _report(d, "run5", "C")
    d.set_bar(run_type="Verification", run="run1")
    yield 900
    d.launch_tool("measurement_report")
    yield 5000
    dlg = d.top_dialog("MeasurementReportDialog")
    combo = dlg._saved_combo
    for i in range(combo.count()):
        if combo.itemText(i).startswith("2026-10-01"):
            d.pick(combo, combo.itemText(i))
            break
    yield 3500
    text = _report_text(dlg)
    rec["D"] = [ln.strip() for ln in text.splitlines()
                if ln.strip().startswith(ROWS)]
    d.note(f"D run1 {combo.currentText()!r}")
    for ln in rec["D"]:
        d.note(f"   D | {ln[:200]}")
    _scroll_to(dlg, "Report Results")
    dlg._view.find(ROWS[0])
    dlg._view.ensureCursorVisible()
    sb = dlg._view.verticalScrollBar()
    sb.setValue(sb.value() + 260)
    yield 700
    d.shot(dlg, "D-run1-covered-chart-judged")
    dlg.reject()
    yield 1200

    # -- E: the presets window --------------------------------------------
    d.set_bar(run_type="Profiling", run="run1")
    d.goto_tab("chart")
    yield 1500
    d.later(d.win._tab_chart._open_preset_verification_window)
    yield 6000
    pdlg = d.top_dialog("PresetVerificationDialog")
    from workflow import measurement_report as MR
    pdlg._type_combo.setCurrentIndex(
        pdlg._type_combo.findData(MR.REPORT_TYPE_FULL))
    pdlg._set_combo.setCurrentIndex(pdlg._set_combo.findData("chromiq_default"))
    yield 2500
    rec["E"] = {}
    picks = [("E1-p3-A4-154p-1page", "A4-154p-1page-Portrait-w16.0mm", "i1Pro 3 Plus"),
             ("E2-p3-A4-308p-2pages", "A4-308p-2pages-Portrait-w16.0mm", "i1Pro 3 Plus"),
             ("E3-p3-A3-336p-1page", "A3-336p-1page-Portrait-w16.0mm", "i1Pro 3 Plus"),
             ("E4-p3-A3-672p-2pages", "A3-672p-2pages-Portrait-w16.0mm", "i1Pro 3 Plus"),
             ("E5-p3-A4-84p-1page", "A4-84p-1page-Portrait-w25.0mm", "i1Pro 3 Plus"),
             ("E6-i1-A4-572p", "A4-572p-1page-Portrait-w8.0mm", None),
             ("E7-i1-A4-837p-no-clip", "A4-837p-1page", None)]
    for shot, label, group in picks:
        item = None
        for it in _all_items(pdlg._tree):
            if label in it.text(0) and it.parent() is not None and (
                    group is None or group in it.parent().text(0)):
                item = it
                break
        if item is None:
            d.note(f"   E {shot}: NO ITEM for {label!r}")
            continue
        pdlg._tree.scrollToItem(item)
        pdlg._tree.setCurrentItem(item)
        yield 1500
        lines = _detail(pdlg)
        ev = [ln for ln in lines if "Evenness" in ln or "cover" in ln
              or "strips" in ln or "ninth" in ln]
        rec["E"][shot] = {"item": item.text(0), "evenness": ev}
        d.note(f"   E {shot}: {item.text(0)!r}")
        for ln in ev:
            d.note(f"      {ln[:220]}")
        d.shot(pdlg, shot)
    pdlg.reject()
    yield 1500

    # -- F: the pre-flight ------------------------------------------------
    for run in ("run3", "run4"):
        vdir = d.work / NAME / "runs" / run / "verifications"
        moved = []
        for ti3 in sorted(vdir.glob("*/*.ti3")):
            ti3.rename(ti3.with_suffix(".ti3-aside"))
            moved.append(ti3.parent.name)
        d.note(f"F {run}: dated measurements moved aside: {moved}")
        d.goto_tab("chart")
        d.set_bar(run_type="Verification", run=run)
        yield 1200
        d.win._tab_measure._preflight_silenced.clear()
        d.later(lambda: d.win._tabs.setCurrentIndex(2))
        yield 3000
        said = d.answer("OK", name=f"F-preflight-{run}", within_ms=9000)
        rec[f"F_{run}"] = said
        for ln in (said or "").splitlines():
            d.note(f"   F {run} | {ln.strip()[:220]}")
        yield 1000
    yield 500


if __name__ == "__main__":
    d = Drive(Path(sys.argv[1]), projects=[NAME])
    rc = d.run(script)
    print(json.dumps({k: v for k, v in d.record.items()
                      if k[:1] in "ABCDEF" and k not in ("photos",)},
                     indent=1, default=str)[:6000])
    sys.exit(rc)
