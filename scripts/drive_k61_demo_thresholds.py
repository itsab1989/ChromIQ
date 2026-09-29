#!/usr/bin/env python3
"""K61 (Knut, #182 5851645723): *"Test the demo projects on-screen on real
app and via simulations, and compare the results"*. The ON-SCREEN half.

    CHROMIQ_DEMO_PACK=<pack> python drive_k61_demo_thresholds.py <out> <en|de>

A. **The demo presets, one pair per requirement.** The pack's folder "Create
   Chart presets (verification demos)" is copied into the sandbox's Create
   Chart preset folder the way a user copies it. Report-Limits-Every-Metric is
   opened (Run type Verification, run1), Create Chart put in Manual and "Which
   presets can be used for verification?" opened with its own button. Report
   type Full colour check; for each requirement R01 to R19 "Judged against" is
   Custom ISO 12647-7 (the set that limits every row a chart can answer) or
   the set the pair names, both presets are selected, what each withholds is
   recorded, and the window is photographed on each with the pane at the
   first metric it cannot answer.
B. **The report's side of the evenness lines.** Report-Limits-Evenness,
   run10 (the sheet's own noise just over and just under both of ChromIQ
   default's limits) and run9 (Knut's 648-patch page as a typical print):
   a "New report…" of type Full colour check, every date ticked, judged
   against ChromIQ default and, for run9, against ISO 12647-7:2016 values;
   the two evenness rows' words recorded and Report Results photographed.

The simulation half is `k61_threshold_matrix.py` and `k61_compare.py`,
offscreen, which read the same charts through the same functions; the
comparison is written by the latter. Every question the drive expects it
answers itself; a watchdog photographs and cancels anything else. Settings,
presets and the output folder are sandboxed by `userdrive`; the pack is
copied, never written.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import time
from pathlib import Path

TREE = os.environ.get("CHROMIQ_TREE") or str(Path(__file__).resolve().parents[1])
sys.path.insert(0, TREE + "/scripts")
sys.path.insert(0, TREE)
HERE = str(Path(__file__).resolve().parent)
if HERE not in sys.path:
    sys.path.append(HERE)
from userdrive import DEMO_PACK, Drive                         # noqa: E402
import drive_b42_k36 as K36                                    # noqa: E402
import drive_k45_pdf_layout as K45                             # noqa: E402

K36.DEADLINE_S = 2400
EVERY = "Report-Limits-Every-Metric"
EVEN = "Report-Limits-Evenness"
STRICT_SET = "custom_iso_12647_7"
PRESET_FOLDER = "Create Chart presets (verification demos)"


def _pane(dlg) -> "list[str]":
    out = []
    for i in range(dlg._detail_layout.count()):
        w = dlg._detail_layout.itemAt(i).widget()
        if w is not None and hasattr(w, "text"):
            out.append(w.text())
    return out


def _item(dlg, label):
    from PyQt6.QtCore import Qt
    for i in range(dlg._tree.topLevelItemCount()):
        head = dlg._tree.topLevelItem(i)
        for j in range(head.childCount()):
            child = head.child(j)
            r = child.data(0, Qt.ItemDataRole.UserRole)
            if r is not None and r.label == label:
                return child, r
    return None, None


def _presets(d, rec):
    import make_verification_preset_demos as GEN
    from core.i18n import tr
    from core.preset_store import tab_dir
    from PyQt6.QtWidgets import QAbstractItemView
    from workflow import measurement_report as MR
    from workflow import preset_eligibility as PE
    dest = tab_dir("create_chart")
    dest.mkdir(parents=True, exist_ok=True)
    for src in sorted((DEMO_PACK / PRESET_FOLDER).iterdir()):
        if src.suffix in (".json", ".ti1"):
            shutil.copy2(src, dest / src.name)
    d.open_project(EVERY)
    d.set_bar(run="run1", run_type="verification")
    d.goto_tab("chart")
    tab = d.win._tab_chart
    if not tab._manual_btn.isChecked():
        tab._manual_btn.click()
    yield 1500
    d.later(tab._preset_verify_btn.click)
    yield 5000
    dlg = K36._wait(d, "PresetVerificationDialog")
    if dlg is None:
        rec["presets_error"] = "no presets window"
        return
    dlg.resize(1250, 900)
    dlg._type_combo.setCurrentIndex(
        dlg._type_combo.findData(MR.REPORT_TYPE_FULL))
    yield 1000
    out = {}
    for req, fail, ok in GEN.pairs():
        sid = req.judged_with or STRICT_SET
        dlg._set_combo.setCurrentIndex(dlg._set_combo.findData(sid))
        yield 800
        t0 = time.monotonic()
        while dlg.waiting_count() and time.monotonic() - t0 < 300:
            yield 1000
        for side, demo in (("FAIL", fail), ("PASS", ok)):
            item, r = _item(dlg, demo.name)
            if item is None:
                out[f"{req.key} {side}"] = {"error": "not in the window"}
                continue
            dlg._tree.scrollToItem(
                item, QAbstractItemView.ScrollHint.PositionAtCenter)
            dlg._tree.setCurrentItem(item)
            yield 700
            first = next(("✕  " + tr(PE.row_label(rid))
                          for rid in req.rows
                if rid in dict(r.assessment.missing)), None)
            for i in range(dlg._detail_layout.count()):
                w = dlg._detail_layout.itemAt(i).widget()
                if w is not None and hasattr(w, "text") and first \
                        and w.text() == first:
                    dlg._detail_scroll.verticalScrollBar().setValue(
                        max(0, w.y() - 8))
                    break
            yield 600
            out[f"{req.key} {side}"] = {
                "preset": demo.name, "set": sid,
                "answered": list(r.assessment.answered),
                "missing": dict(r.assessment.missing),
                "noise_counts": {k: list(v) for k, v in
                                 r.assessment.noise_counts},
                "pane": _pane(dlg)}
            d.shot(dlg, f"{d.lang}-A-{req.key}-{side}")
    rec["presets"] = out
    dlg.reject()
    yield 1500


def _report(d, rec, run, sets):
    import ui.dialogs.measurement_report_dialog as mrd
    from core.i18n import tr
    shutil.rmtree(d.work / EVEN, ignore_errors=True)
    shutil.copytree(DEMO_PACK / EVEN, d.work / EVEN)
    d.open_project(EVEN)
    d.set_bar(run=run, run_type="verification")
    d.pump(1200)
    d.launch_tool("measurement_report")
    yield 4500
    dlg = K36._wait(d, "MeasurementReportDialog")
    if dlg is None:
        rec.setdefault("report_errors", []).append(f"{run}: no window")
        return
    dlg.resize(1400, 980)
    yield 1200
    K45._pick_data(dlg._saved_combo, mrd.NEW_REPORT_KEY)
    yield 1800
    K45._pick_data(dlg._type_combo, "t2_full_colour_check")
    yield 1200
    K45._tick(dlg, "all")
    yield 1200
    for sid in sets:
        K45._pick_data(dlg._set_combo, sid)
        yield 1200
        K36.EXPECTED.add("QMessageBox")
        d.later(dlg._generate_btn.click)
        yield 600
        d.answer("neu" if d.lang == "de" else "new",
                 f"{d.lang}-B-{run}-{sid}-question", within_ms=3000)
        K36.EXPECTED.discard("QMessageBox")
        yield 7000
        words = {}
        for r in dlg._runs_for_report():
            rows, _rec = dlg._verdict_rows(r)
            when = str(r.get("created") or r.get("ti3") or "")
            words[when] = {x["row_id"]: [x.get("word"), x.get("reason"),
                                         x.get("value")]
                           for x in rows if x["row_id"] in (
                               "uniformity_sd",
                               "uniformity_de00_max_from_mean")}
        rec.setdefault("report", {})[f"{run} {sid}"] = words
        from PyQt6.QtGui import QTextCursor
        view = dlg._view
        view.moveCursor(QTextCursor.MoveOperation.Start)
        view.find(tr("Report Results"))
        view.find(tr("Maximum ΔE00, between two of the nine sheet areas"))
        cur = QTextCursor(view.textCursor())
        cur.clearSelection()
        view.setTextCursor(cur)
        view.ensureCursorVisible()
        yield 900
        d.shot(dlg, f"{d.lang}-B-{run}-{sid}")
    dlg.close()
    yield 1500


def script(lang, parts):
    def s(d):
        d.lang = lang
        rec = d.record
        rec.update({"language": lang, "tree": TREE, "mode": "ON SCREEN"})
        K36._install_watchdog(d, rec)
        yield 500
        if "A" in parts:
            yield from _presets(d, rec)
        if "B" in parts:
            yield from _report(d, rec, "run10", ("chromiq_default",))
            yield from _report(d, rec, "run9",
                               ("chromiq_default", "iso_12647_7"))
        (d.out / f"{lang}-demo-thresholds.json").write_text(
            json.dumps({k: rec.get(k) for k in ("presets", "report")},
                       indent=2, ensure_ascii=False, default=str),
            encoding="utf-8")
    return s


def main() -> int:
    out = Path(sys.argv[1])
    lang = sys.argv[2]
    parts = sys.argv[3] if len(sys.argv) > 3 else "AB"
    d = Drive(out, projects=[EVERY], language=lang)
    rc = d.run(script(lang, parts))
    print(f"rc={rc}")
    return rc


if __name__ == "__main__":
    sys.exit(main())
