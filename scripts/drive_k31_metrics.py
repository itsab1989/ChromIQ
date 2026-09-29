#!/usr/bin/env python3
"""#182 K31 (beta 40): metrics, names and texts, driven ON SCREEN.

    CHROMIQ_DEMO_PACK=<pack> python scripts/drive_k31_metrics.py \\
        <out> <en|de> [scene ...]

The pack is the release demo package built from this tree
(`make_release_demo_package.py`), whose project folders sit at its root and
whose "Create Chart presets (verification demos)" folder holds the preset
pack with the new R15 pair.

scenes:
    split     Report-Limits-Threshold-Series run1, every date, Full colour
              check, detail on: the within-gamut names in Report Results, How
              to read and the detailed data; the Overview's "Within and beyond
              the gamut together", "Darkest black L*" and "Standard deviation
              ΔE00, all patches"; every graph tab and its unit; the PDF; the
              Report limits window from the report and the tone ramp's help
              icon
    evenness  Report-Limits-Evenness run8 (printed relative): the "How
              evenness was judged" line; the same sheet as a Grey and tone
              check, which has no evenness row and no such line; the PDF
    prefs     Preferences > Reports > Report limits…: the second limits
              window, and the evenness rows' help icon
    presets   "Which presets can be used for verification?" with the demo
              presets installed, judged against Custom ISO 12647-7: R15 FAIL
              and R15 PASS

Every scene photographs the real window (`onscreen_capture.capture_window`
through `userdrive.Drive.shot`); `k31-found.json` records what the window
text and the PDF text hold for each check.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

SPLIT = "Report-Limits-Threshold-Series"
EVEN = "Report-Limits-Evenness"
PRESET_FOLDER = "Create Chart presets (verification demos)"
ALL = ("split", "evenness", "prefs", "presets")


def _flat(s: str) -> str:
    return " ".join(str(s).split())


def _install_presets(out: Path) -> None:
    """The demo presets, copied the way a user installs them, BEFORE the app
    starts (it reads the folder once)."""
    from userdrive import DEMO_PACK
    src = DEMO_PACK / PRESET_FOLDER
    if not src.is_dir():
        print(f"no preset folder at {src}")
        return
    sb = out / "sandbox" / "presets"
    os.environ.setdefault("CHROMIQ_PRESETS_DIR", str(sb))
    from core.preset_store import tab_dir
    dest = tab_dir("create_chart")
    dest.mkdir(parents=True, exist_ok=True)
    for f in src.iterdir():
        if f.suffix in (".json", ".ti1"):
            shutil.copy2(f, dest / f.name)


def script_for(scenes, language):
    def script(d):
        from PyQt6.QtCore import Qt
        from core.i18n import tr
        from workflow.compliance_sets import ROW_BY_ID, IN_GAMUT_LABELS
        rec = d.record
        rec["language"] = language
        rec["checks"] = {}
        L = tr
        close_word = "Schließen" if language == "de" else "Close"
        tag = language

        def check(scene, what, ok, detail=""):
            rec["checks"].setdefault(scene, []).append(
                {"what": what, "ok": bool(ok), "detail": detail})
            d.note(f"   {'OK  ' if ok else 'FAIL'} {what} {detail}")

        def wait_dialog(cls="MeasurementReportDialog"):
            for _ in range(80):
                dlg = d.top_dialog(cls)
                if dlg is not None:
                    return dlg
                d.pump(250)
            return None

        def open_window(project, run, run_type):
            d.open_project(project)
            d.set_bar(run_type=run_type, run=run)
            d.pump(900)
            d.launch_tool("measurement_report")

        def new_report(dlg, detail=True):
            dlg._saved_combo.setCurrentIndex(0)
            dlg._saved_combo.activated.emit(0)
            d.pump(1200)
            lst = dlg._profile_list
            for i in range(lst.count()):
                it = lst.item(i)
                if it.flags() & Qt.ItemFlag.ItemIsUserCheckable:
                    it.setCheckState(Qt.CheckState.Checked)
                    d.pump(120)
            if detail != dlg._detail_check.isChecked():
                dlg._detail_check.click()
            d.pump(2000)

        def pick_type(dlg, tid):
            i = dlg._type_combo.findData(tid)
            if i >= 0:
                dlg._type_combo.setCurrentIndex(i)
                dlg._type_combo.activated.emit(i)
            d.pump(2000)
            return i >= 0

        def shoot_at(dlg, text, name, occurrence=0):
            view = dlg._view
            doc = view.document()
            start, cur = 0, None
            for _ in range(occurrence + 1):
                c = doc.find(text, start)
                if c.isNull():
                    d.note(f"   (not on the page: {text!r})")
                    return False
                cur, start = c, c.selectionEnd()
            from PyQt6.QtGui import QTextCursor
            plain = QTextCursor(cur)
            plain.setPosition(cur.selectionStart())
            view.setTextCursor(plain)
            sb = view.verticalScrollBar()
            sb.setValue(max(0, sb.value() + view.cursorRect(plain).top() - 30))
            d.pump(500)
            d.shot(dlg, name)
            return True

        def save_pdf(dlg, name):
            from drive_g12_notes import pdf_pages_text, render_pdf
            target = d.out / "pdf" / f"{name}.pdf"
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists():
                target.unlink()
            d.later(dlg._pdf_btn.click)
            yield 1500
            d.answer_file(target, name=None)
            for _ in range(120):
                yield 1000
                if target.exists():
                    break
            yield 3000
            text = []
            if target.exists():
                pages_dir = d.out / "pdf-pages"
                pages_dir.mkdir(exist_ok=True)
                pages = render_pdf(target, pages_dir)
                text = pdf_pages_text(target)
                (pages_dir / f"{name}.txt").write_text(
                    "\n\f\n".join(text), encoding="utf-8")
                d.note(f"   PDF {target.name}: {len(pages)} pages")
            else:
                d.note(f"   PDF {target.name}: NOT WRITTEN")
            dlg.raise_()
            return text

        def both(scene, what, window, pdf_text, needle, present=True):
            flat_pdf = _flat(" ".join(pdf_text))
            w = _flat(needle) in window
            p = _flat(needle) in flat_pdf
            check(scene, f"{what} [window]", w is present, repr(needle))
            check(scene, f"{what} [PDF]", p is present, repr(needle))

        def help_icon(dialog, row_id, name):
            """Click the row's own info icon, photograph what it says."""
            from ui.tooltip_button import TooltipButton
            want = L(ROW_BY_ID[row_id].label)
            btn = next((b for b in dialog.findChildren(TooltipButton)
                        if getattr(b, "_title", "") == want), None)
            if btn is None:
                d.note(f"   (no help icon for {want!r})")
                return ""
            from PyQt6.QtWidgets import QScrollArea
            area = next((a for a in dialog.findChildren(QScrollArea)
                         if a.isAncestorOf(btn)), None)
            if area is not None:
                area.ensureWidgetVisible(btn, 50, 200)
                d.pump(400)
            body = btn.dialog_body() if hasattr(btn, "dialog_body") else ""
            d.later(btn.click)
            yield 1500
            d.answer(close_word, name=name, within_ms=4000)
            yield 800
            return body

        # ---------------------------------------------------------------
        if "split" in scenes:
            sc = "split"
            d.note(f"[{sc}] {SPLIT} run1, every date, Full colour check")
            open_window(SPLIT, "run1", "Verification")
            yield 3500
            dlg = wait_dialog()
            new_report(dlg)
            from workflow.measurement_report import REPORT_TYPE_FULL
            pick_type(dlg, REPORT_TYPE_FULL)
            yield 1500
            runs = dlg._runs_for_report()
            check(sc, "a sheet of the document is split by the gamut",
                  any(r.get("gamut_split") for r in runs))
            text = _flat(dlg._view.toPlainText())
            within = L(IN_GAMUT_LABELS["all_de00_avg"])
            shoot_at(dlg, L("Report Results"), f"{tag}-split-01-results")
            shoot_at(dlg, L("How to read this report"), f"{tag}-split-02-guide")
            shoot_at(dlg, L("Overview of Measurement Metrics"),
                     f"{tag}-split-03-overview")
            shoot_at(dlg, L("Within and beyond the gamut together"),
                     f"{tag}-split-04-overview-together")
            shoot_at(dlg, L("Darkest black L*"), f"{tag}-split-05-overview-info")
            shoot_at(dlg, L("Colour accuracy (ΔE00 against the chart's design)"),
                     f"{tag}-split-06-detail")
            shoot_at(dlg, L("Paper white and darkest black (L*)"),
                     f"{tag}-split-07-detail-info")
            tabs = dlg._trend_tabs
            names = []
            for i in range(tabs.count()):
                if not tabs.isTabVisible(i):
                    continue
                names.append(tabs.tabText(i))
                tabs.setCurrentIndex(i)
                d.pump(700)
                d.shot(dlg, f"{tag}-split-08-graph-{i:02d}")
            rec["tabs"] = names
            check(sc, "every visible graph tab names its unit",
                  all("(" in n and ")" in n for n in names), repr(names))
            legend = [m[0] for m in dlg._trend_configs()[0][2]]
            rec["legend"] = legend
            check(sc, "the Colour accuracy legend says within gamut",
                  within in legend, repr(legend))
            pdf = yield from save_pdf(dlg, f"{tag}-split")
            for n in (within, L(IN_GAMUT_LABELS["all_de00_max"]),
                      L("Within and beyond the gamut together"),
                      L("Darkest black L*"),
                      L("Standard deviation ΔE00, all patches"),
                      L("Paper white and darkest black (L*)"),
                      L("Cube corners (ΔE00)")):
                both(sc, "present", text, pdf, n)
            for n in ("All patches together", "Spread (std. dev.)",
                      "Paper white & darkest black", "largest"):
                both(sc, "gone", text, pdf, L(n), present=False)
            # the Report limits window, from the report
            d.later(dlg._limits_btn.click)
            yield 2500
            m = d.modal()
            if m is not None and m is not dlg:
                d.shot(m, f"{tag}-split-09-report-limits")
                from PyQt6.QtWidgets import QLabel
                labels = " ".join(w.text() for w in m.findChildren(QLabel))
                for rid in ("ramps_30_70_dl_max", "solids_de00_max",
                            "uniformity_sd", "grey_balance_neutral_ramp_max"):
                    check(sc, "Report limits names the row",
                          L(ROW_BY_ID[rid].label) in labels,
                          repr(L(ROW_BY_ID[rid].label)))
                body = yield from help_icon(m, "ramps_30_70_dl_max",
                                            f"{tag}-split-10-help-tone-ramp")
                rec["help_tone_ramp"] = body
                check(sc, "the tone ramp's help icon states rule A",
                      L(ROW_BY_ID["ramps_30_70_dl_max"].detect) in body)
                body = yield from help_icon(
                    m, "grey_balance_neutral_ramp_avg",
                    f"{tag}-split-11-help-grey-ramp")
                rec["help_grey_ramp"] = body
                m.close()
                d._modal_closed()
            else:
                check(sc, "Report limits window opened", False)
            yield 1200
            dlg.close()
            yield 1200

        # ---------------------------------------------------------------
        if "evenness" in scenes:
            sc = "evenness"
            d.note(f"[{sc}] {EVEN} run8 (printed relative)")
            open_window(EVEN, "run8", "Verification")
            yield 3500
            dlg = wait_dialog()
            new_report(dlg)
            from workflow.measurement_report import (REPORT_TYPE_FULL,
                                                     REPORT_TYPE_GREY)
            pick_type(dlg, REPORT_TYPE_FULL)
            yield 1500
            text = _flat(dlg._view.toPlainText())
            line = L("How evenness was judged")
            val = L("from the readings as the instrument took them, by "
                    "comparing the nine areas of this sheet with each other.")
            shoot_at(dlg, line, f"{tag}-evenness-01-line")
            shoot_at(dlg, L(ROW_BY_ID["uniformity_sd"].label),
                     f"{tag}-evenness-02-rows")
            pdf = yield from save_pdf(dlg, f"{tag}-evenness")
            both(sc, "the evenness line", text, pdf, line)
            both(sc, "its approved text", text, pdf, val)
            both(sc, "the colours line beside it", text, pdf,
                 L("How the colours were judged"))
            pick_type(dlg, REPORT_TYPE_GREY)
            yield 1000
            # a changed type is built by Generate report, as a user builds it
            d.later(dlg._generate_btn.click)
            yield 800
            d.answer(L("Create New") if language == "en" else "Neu erstellen",
                     name=f"{tag}-evenness-02b-generate", within_ms=3000)
            yield 4000
            text2 = _flat(dlg._view.toPlainText())
            dlg._view.verticalScrollBar().setValue(0)
            d.shot(dlg, f"{tag}-evenness-03-grey-and-tone-no-line")
            check(sc, "a Grey and tone check has no evenness row and no line",
                  line not in text2)
            dlg.close()
            yield 1200

        # ---------------------------------------------------------------
        if "prefs" in scenes:
            sc = "prefs"
            d.note(f"[{sc}] Preferences > Reports > Report limits…")
            d.later(d.win._open_settings)
            yield 2500
            sd = d.modal()
            if sd is None:
                check(sc, "Preferences opened", False)
            else:
                tabs = sd._tabs
                for i in range(tabs.count()):
                    if tabs.tabText(i) == L("Reports"):
                        tabs.setCurrentIndex(i)
                d.pump(600)
                d.shot(sd, f"{tag}-prefs-01-reports")
                d.later(sd._report_limits_btn.click)
                yield 2500
                m = d.modal()
                if m is not None and m is not sd:
                    d.shot(m, f"{tag}-prefs-02-report-limits")
                    from PyQt6.QtWidgets import QLabel
                    labels = " ".join(w.text() for w in m.findChildren(QLabel))
                    for rid in ("uniformity_sd", "uniformity_de00_max_from_mean",
                                "control_strip_de00_p95"):
                        check(sc, "the second limits window names the row",
                              L(ROW_BY_ID[rid].label) in labels,
                              repr(L(ROW_BY_ID[rid].label)))
                    body = yield from help_icon(
                        m, "uniformity_sd", f"{tag}-prefs-03-help-evenness")
                    rec["help_evenness"] = body
                    check(sc, "the evenness help icon carries the approved text",
                          L(ROW_BY_ID["uniformity_sd"].detect) in body)
                    m.reject()
                    d._modal_closed()
                    yield 1200
                sd.reject()
                d._modal_closed()
                yield 1200

        # ---------------------------------------------------------------
        if "presets" in scenes:
            sc = "presets"
            d.note(f"[{sc}] the presets window, Custom ISO 12647-7")
            d.goto_tab("chart")
            tab = d.win._tab_chart
            d.open_project(EVEN)
            d.set_bar(run="run1", run_type="Verification")
            yield 1000
            if tab._mode_name() != "manual":
                tab._manual_btn.click()
                yield 1200
            d.later(tab._open_preset_verification_window)
            yield 6000
            pv = d.top_dialog("PresetVerificationDialog")
            if pv is None:
                check(sc, "presets window opened", False)
            else:
                from workflow.measurement_report import REPORT_TYPE_FULL
                pv._type_combo.setCurrentIndex(
                    pv._type_combo.findData(REPORT_TYPE_FULL))
                pv._set_combo.setCurrentIndex(
                    pv._set_combo.findData("custom_iso_12647_7"))
                yield 2500
                for side in ("FAIL", "PASS"):
                    hit = None
                    for i in range(pv._tree.topLevelItemCount()):
                        head = pv._tree.topLevelItem(i)
                        for j in range(head.childCount()):
                            it = head.child(j)
                            row = it.data(0, Qt.ItemDataRole.UserRole)
                            if row is not None and row.label.startswith(
                                    f"Verify R15 {side}"):
                                hit = (it, row)
                    if hit is None:
                        check(sc, f"R15 {side} is listed", False)
                        continue
                    pv._tree.setCurrentItem(hit[0])
                    pv._tree.scrollToItem(hit[0])
                    yield 1500
                    d.shot(pv, f"{tag}-presets-0{1 if side == 'FAIL' else 2}"
                               f"-r15-{side.lower()}")
                    missing = dict(hit[1].assessment.missing)
                    got = missing.get("ramps_30_70_dl_max")
                    check(sc, f"R15 {side}",
                          (got == "ramp_steps_bunched") if side == "FAIL"
                          else got is None, repr(got))
                pv.reject()
                d._modal_closed()
                yield 1200

        (d.out / "k31-found.json").write_text(
            json.dumps(rec.get("checks"), indent=2, ensure_ascii=False),
            encoding="utf-8")
    return script


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(2)
    out, language = Path(sys.argv[1]).resolve(), sys.argv[2]
    scenes = tuple(sys.argv[3:]) or ALL
    if "presets" in scenes:
        _install_presets(out)
    from userdrive import Drive
    d = Drive(out, projects=[SPLIT, EVEN], language=language)
    sys.exit(d.run(script_for(scenes, language)))
