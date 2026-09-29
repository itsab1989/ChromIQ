#!/usr/bin/env python3
"""#182, evenness across the sheet (B8-814), driven ON SCREEN as a user.

On the project `scripts/make_evenness_demo.py` builds (Report-Limits-Evenness),
copied into a sandbox by `userdrive.Drive`:

    A  the Measurement Report on run1, all four dated measurements ticked:
       even (PASS / PASS), a drift across the strips (FAIL / PASS), one area
       lighter (PASS / FAIL), noisy (N-A / N-A, the noise named);
    B  the same report on run2, whose 84-patch chart has 7 strips: N-A, the
       grid named;
    C  "Which presets can be used for verification?": the current chart line
       and three of Knut's presets (572 answered, 154 too noisy on a typical
       print, 84 under 9 by 9);
    D  the Measure tab's pre-flight on run2 and on run1 with their dated
       measurements moved aside, so the pre-flight is due.

    export CHROMIQ_DEMO_PACK=<folder holding Report-Limits-Evenness>
    python scripts/drive_evenness.py <out-dir>
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from userdrive import Drive                                   # noqa: E402

NAME = "Report-Limits-Evenness"
ROWS = ("Evenness across the sheet, nine locations",
        "Evenness across the sheet, largest difference from the mean")


def _report_text(dlg) -> str:
    return dlg._view.toPlainText()


def _evenness_lines(text: str) -> "list[str]":
    out = []
    for ln in text.splitlines():
        if "Evenness across the sheet" in ln or "ninth of the page" in ln \
                or "banding" in ln or "strips" in ln and "rows" in ln:
            out.append(ln.strip())
    return out


def _scroll_to(dlg, needle: str) -> None:
    from PyQt6.QtGui import QTextCursor
    v = dlg._view
    v.moveCursor(QTextCursor.MoveOperation.Start)
    v.find(needle)
    v.ensureCursorVisible()


def _all_items(tree):
    def walk(item):
        yield item
        for i in range(item.childCount()):
            yield from walk(item.child(i))
    for i in range(tree.topLevelItemCount()):
        yield from walk(tree.topLevelItem(i))


def _detail(dlg) -> "list[str]":
    out = []
    for i in range(dlg._detail_layout.count()):
        w = dlg._detail_layout.itemAt(i).widget()
        if w is not None and hasattr(w, "text") and w.text():
            out.append(w.text())
    return out


def script(d):
    rec = d.record
    d.open_project(NAME)
    d.set_bar(run_type="Verification", run="run1")
    yield 800

    # -- A: the report on the large chart, all four dates -------------------
    d.launch_tool("measurement_report")
    yield 5000
    dlg = d.top_dialog("MeasurementReportDialog")
    d.note(f"A report shown: {dlg._saved_combo.currentText()!r}")
    # each dated report in turn, as a reader picks them from "Report shown"
    combo = dlg._saved_combo
    rec["A"] = {}
    for i in range(combo.count()):
        label = combo.itemText(i)
        if "2026-10" not in label:
            continue
        d.pick(combo, label)
        yield 3500
        text = _report_text(dlg)
        day = label[:10]
        rec["A"][day] = _evenness_lines(text)
        d.note(f"A {label!r}")
        for ln in rec["A"][day]:
            if not ln.startswith("Evenness across the sheet, nine locations:") \
                    and not ln.startswith("Evenness across the sheet, largest "
                                          "difference from the mean: The"):
                d.note(f"   A | {ln[:260]}")
        _scroll_to(dlg, "Report Results")
        dlg._view.find(ROWS[0])
        dlg._view.ensureCursorVisible()
        sb = dlg._view.verticalScrollBar()
        sb.setValue(sb.value() + 260)
        yield 700
        if not d.shot(dlg, f"A-{day}-evenness-rows"):
            yield 1500
            d.shot(dlg, f"A-{day}-evenness-rows")
        _scroll_to(dlg, "Notes on the verdicts above")
        yield 700
        if not d.shot(dlg, f"A-{day}-notes"):
            yield 1500
            d.shot(dlg, f"A-{day}-notes")
    dlg.reject()
    yield 1200

    # -- B: the small chart ------------------------------------------------
    d.set_bar(run="run2")
    yield 800
    d.launch_tool("measurement_report")
    yield 5000
    dlg = d.top_dialog("MeasurementReportDialog")
    text = _report_text(dlg)
    rec["B_lines"] = _evenness_lines(text)
    for ln in rec["B_lines"]:
        d.note(f"   B | {ln[:220]}")
    rec["B_strip"] = dlg._mismatch_full
    d.note(f"   B strip: {dlg._mismatch_full[:300]!r}")
    _scroll_to(dlg, "Report Results")
    dlg._view.find(ROWS[0])
    dlg._view.ensureCursorVisible()
    sb = dlg._view.verticalScrollBar()
    sb.setValue(sb.value() + 260)
    yield 700
    d.shot(dlg, "B1-run2-small-chart-na")
    _scroll_to(dlg, "Notes on the verdicts above")
    yield 700
    d.shot(dlg, "B2-run2-small-chart-note")
    dlg.reject()
    yield 1200

    # -- C: the presets window, from Create Chart on run1 ------------------
    d.set_bar(run="run1")
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
    rec["C"] = {}
    picks = [("C1-current-chart-572", None),
             ("C2-preset-i1-572p", "A4-572p-1page-Portrait-w8.0mm"),
             ("C3-preset-p3-154p", "A4-154p-1page-Portrait-w16.0mm"),
             ("C4-preset-p3-84p", "A4-84p-1page-Portrait-w25.0mm")]
    for shot, label in picks:
        item = None
        for it in _all_items(pdlg._tree):
            t = it.text(0)
            if label is None and it.parent() is None and it.childCount() == 0 \
                    and t:
                item = it            # the current chart's own line
                break
            if label is not None and label in t and it.parent() is not None \
                    and ("i1Pro 3 Plus" in it.parent().text(0)
                         if "p3" in shot else True):
                item = it
                break
        if item is None:
            d.note(f"   C {shot}: NO ITEM for {label!r}")
            continue
        pdlg._tree.scrollToItem(item)
        pdlg._tree.setCurrentItem(item)
        yield 1500
        lines = _detail(pdlg)
        ev = [ln for ln in lines if "Evenness" in ln or "strips" in ln
              or "ninth" in ln]
        rec["C"][shot] = {"item": item.text(0), "evenness": ev}
        d.note(f"   C {shot}: {item.text(0)!r}")
        for ln in ev:
            d.note(f"      {ln[:200]}")
        d.shot(pdlg, shot)
    pdlg.reject()
    yield 1500

    # -- D: the pre-flight, on run2 and then run1, with no history ----------
    for run in ("run3", "run2"):
        vdir = d.work / NAME / "runs" / run / "verifications"
        moved = []
        for ti3 in sorted(vdir.glob("*/*.ti3")):
            ti3.rename(ti3.with_suffix(".ti3-aside"))
            moved.append(ti3.parent.name)
        d.note(f"D {run}: dated measurements moved aside: {moved}")
        d.goto_tab("chart")
        d.set_bar(run=run)
        yield 1200
        d.win._tab_measure._preflight_silenced.clear()
        d.later(lambda: d.win._tabs.setCurrentIndex(2))
        yield 3000
        said = d.answer("OK", name=f"D-preflight-{run}", within_ms=9000)
        rec[f"D_{run}"] = said
        for ln in (said or "").splitlines():
            d.note(f"   D {run} | {ln.strip()[:200]}")
        yield 1000
    yield 500


if __name__ == "__main__":
    d = Drive(Path(sys.argv[1]), projects=[NAME])
    rc = d.run(script)
    print(json.dumps({k: v for k, v in d.record.items()
                      if k.startswith(("A_", "B_", "C", "D_"))},
                     indent=1)[:4000])
    sys.exit(rc)
