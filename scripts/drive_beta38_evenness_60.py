#!/usr/bin/env python3
"""#182 beta 38, E2 at 60 % (Knut, 5792912682) and E4, driven ON SCREEN.

On the project `scripts/make_evenness_demo.py` builds (Report-Limits-Evenness),
copied into a sandbox by `userdrive.Drive`:

    P  "Which presets can be used for verification?", Full colour check
       against ChromIQ default: the i1Pro 3 Plus presets on two pages (A4 308,
       Letter 286) and the one-page A3 answering the evenness rows; the
       one-page A4 154 (noise) and A4 84 (grid) not answering them; the i1Pro
       572 (68.4 %) answering and the half-page i1Pro 312 (37.3 %) refused
       with the coverage line quoting 60 %;
    R  the Measurement Report on run6 (the 312 chart): both evenness rows
       N-A, the note "... cover 37.2 % of the page; at least 60 % is needed";
       on run7 (i1Pro 3 Plus, one page, a typical print): N-A for the noise;
       on run5 (i1Pro 3 Plus, two pages) and run4 (572): judged.

    export CHROMIQ_DEMO_PACK=<folder holding Report-Limits-Evenness>
    python scripts/drive_beta38_evenness_60.py <out-dir>
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from userdrive import Drive                                   # noqa: E402
from drive_evenness import (NAME, ROWS, _all_items, _detail,   # noqa: E402
                            _report_text, _scroll_to)


def _ev_lines(text: str) -> "list[str]":
    return [ln.strip() for ln in text.splitlines()
            if ("cover" in ln and "%" in ln) or "noise" in ln
            or ln.strip().startswith(ROWS)]


def _report(d, run: str, tag: str):
    d.set_bar(run_type="Verification", run=run)
    yield 900
    d.launch_tool("measurement_report")
    yield 5000
    dlg = d.top_dialog("MeasurementReportDialog")
    text = _report_text(dlg)
    lines = _ev_lines(text)
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
    # The heading sits at the bottom of the view; the notes are below it.
    sb = dlg._view.verticalScrollBar()
    sb.setValue(sb.maximum())
    yield 700
    d.shot(dlg, f"{tag}-{run}-notes-text")
    dlg.reject()
    yield 1200


def script(d):
    rec = d.record
    d.open_project(NAME)
    yield 800

    # -- P: the presets window --------------------------------------------
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
    rec["P"] = {}
    p3 = "i1Pro 3 Plus"
    picks = [("P1-p3-A4-308p-2pages-answers", "A4-308p-2pages-Portrait-w16.0mm", p3),
             ("P2-p3-Letter-286p-2pages-answers", "Letter-286p-2pages-Portrait-w16.0mm", p3),
             ("P3-p3-A3-336p-1page-answers", "A3-336p-1page-Portrait-w16.0mm", p3),
             ("P4-p3-A4-154p-1page-noise", "A4-154p-1page-Portrait-w16.0mm", p3),
             ("P5-p3-A4-84p-1page-grid", "A4-84p-1page-Portrait-w25.0mm", p3),
             ("P6-i1-A4-572p-answers", "A4-572p-1page-Portrait-w8.0mm", None),
             ("P7-i1-A4-312p-coverage", "A4-312p-1page-Portrait-w8.0mm", None)]
    for shot, label, group in picks:
        item = None
        for it in _all_items(pdlg._tree):
            if label in it.text(0) and it.parent() is not None and (
                    group is None or group in it.parent().text(0)):
                item = it
                break
        if item is None:
            d.note(f"   P {shot}: NO ITEM for {label!r}")
            continue
        pdlg._tree.scrollToItem(item)
        pdlg._tree.setCurrentItem(item)
        yield 1500
        lines = _detail(pdlg)
        ev = [ln for ln in lines if "Evenness" in ln or "cover" in ln
              or "strips" in ln or "ninth" in ln or "noise" in ln]
        rec["P"][shot] = {"item": item.text(0), "group": item.parent().text(0),
                          "evenness": ev, "detail": lines}
        d.note(f"   P {shot}: {item.parent().text(0)!r} / {item.text(0)!r}")
        for ln in ev:
            d.note(f"      {ln[:260]}")
        d.shot(pdlg, shot)
    pdlg.reject()
    yield 1500

    # -- R: the report ----------------------------------------------------
    yield from _report(d, "run6", "R1")
    yield from _report(d, "run7", "R2")
    yield from _report(d, "run5", "R3")
    yield from _report(d, "run4", "R4")
    yield 500


if __name__ == "__main__":
    d = Drive(Path(sys.argv[1]), projects=[NAME])
    rc = d.run(script)
    print(json.dumps({k: v for k, v in d.record.items()
                      if k[:1] in "PR" and k not in ("photos",)},
                     indent=1, default=str)[:8000])
    sys.exit(rc)
