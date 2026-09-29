#!/usr/bin/env python3
"""B42, Knut #182 5822758830 answer 1 (K37), driven ON SCREEN.

    CHROMIQ_DEMO_PACK=<pack> python scripts/drive_b42_k37.py <out> <en|de> [e|i]

Scene "i" (K37 (i), Knut 5823088098): Report-Limits-Second-Route, run2 (a
chart built from the profile's gamut), "New report…" with every date: the
control-strip rows, their note, and the cube-corner table beside them.

Runs on any tree (``CHROMIQ_TREE``), so the same script photographs the tree
before the change and the one after it. Settings, presets and the output
folder are sandboxed by `userdrive`, which also FORCES the repository's ISO
values file. The project is a copy of ``CHROMIQ_DEMO_PACK``'s
Report-Limits-Border-Conditions; the pack itself is never written.

The three packs the proof uses (made by the proof folder's
``make_k37_packs.py`` from a copy of the release demo pack):

  control  run1's two dates are relative-intent prints through the run's
           profile, and the chart HAS paper patches;
  e        the same two measurements with every patch printed with no ink
           taken out: the chart has no paper patch, the run's profile is
           there;
  b        e, with run1's profile moved away: no profile can be read.

Scene: run1, Run type Verification, the Measurement Report, "New report…"
with every date and "Show detailed data" on. Photographed: Report Results;
the printing block ("How the colours were judged"); the "Paper white and
darkest black" line with its note number; the numbered notes; the Paper white
(L*) graph. Everything read off the widgets goes into driver-report.json.

**NOBODY HAS TO CLICK.** A watchdog answers any window this drive did not
expect (Cancel / Close / No / OK, in English or German) after three seconds,
records its text and photographs it; a deadline ends the run after ten
minutes whatever happens.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from userdrive import DEMO_PACK, Drive                         # noqa: E402
import drive_b42_k36 as K36                                    # noqa: E402

K36.DEADLINE_S = 600
PROJECT = "Report-Limits-Border-Conditions"


def script_for(language: str):
    def script(d):
        rec = d.record
        rec.update({"language": language, "mode": "ON SCREEN",
                    "pack": str(DEMO_PACK)})
        tag = language
        from core.i18n import tr
        from workflow import compliance_sets as cs
        rec["iso_file_in_use"] = cs.iso_data_path_text()
        d.note(f"ISO file in use: {cs.iso_data_path_text()}")
        K36._install_watchdog(d, rec)

        d.open_project(PROJECT)
        d.set_bar(run="run1", run_type="Verification")
        yield 1000
        d.launch_tool("measurement_report")
        yield 4000
        dlg = K36._wait(d, "MeasurementReportDialog")
        if dlg is None:
            d.note("NO REPORT WINDOW")
            return
        K36._new_report_everything(d, dlg)
        if not dlg._detail_check.isChecked():
            dlg._detail_check.setChecked(True)
        yield 3000
        text = K36._view_text(dlg)
        rec["report_text"] = text
        for key, needle, n in (
                ("results", tr("Report Results"), 1600),
                ("how_judged", tr("How the colours were judged"), 400),
                ("paper_line", tr("Paper white and darkest black (L*)"), 300),
                ("notes", tr("Notes on the verdicts above:"), 2600)):
            i = text.find(needle)
            rec[key] = text[i:i + n] if i >= 0 else None
            d.note(f"   {key}: {rec[key]!r}"[:700])
        # what the window worked out, per sheet
        try:
            runs = list(dlg._runs_for_report() or [])
        except Exception:                                  # noqa: BLE001
            runs = []
        rec["sheets"] = [{"ti3": r.get("ti3"), "created": r.get("created"),
                          "yardstick": r.get("yardstick"),
                          "paper_patch": r.get("paper_patch"),
                          "paper_white": r.get("paper_white"),
                          "paper_white_used": r.get("paper_white_used"),
                          "avg_all": (r.get("de00") or {}).get("avg_all"),
                          "max_all": (r.get("de00") or {}).get("max_all")}
                         for r in runs]
        try:
            from workflow.measurement_report import report_trend
            rec["trend_white_L"] = [p.get("white_L")
                                    for p in report_trend(runs)]
        except Exception as exc:                           # noqa: BLE001
            rec["trend_white_L"] = f"not read: {exc}"
        d.note(f"   sheets: {rec['sheets']}"[:900])
        d.note(f"   trend white_L: {rec['trend_white_L']}")

        K36._scroll_to(dlg, tr("Report Results"))
        yield 1200
        d.shot(dlg, f"{tag}-01-report-results")
        K36._scroll_to(dlg, tr("How the colours were judged"))
        yield 1200
        d.shot(dlg, f"{tag}-02-how-the-colours-were-judged")
        K36._scroll_to(dlg, tr("Paper white and darkest black (L*)"))
        yield 1200
        d.shot(dlg, f"{tag}-03-paper-white-line")
        K36._scroll_to(dlg, tr("Notes on the verdicts above:"))
        yield 1200
        d.shot(dlg, f"{tag}-04-notes")
        tabs = getattr(dlg, "_trend_tabs", None)
        if tabs is not None and getattr(dlg, "_trend_white", None) is not None:
            tabs.setCurrentWidget(dlg._trend_white)
            yield 1500
            d.shot(dlg, f"{tag}-05-paper-white-graph")
        dlg.close()
        yield 1500
    return script


#: K37 (i): a FROM PROFILE GAMUT project judged by a set that numbers the
#: control-strip rows (ChromIQ default in the package fills them).
GAMUT_PROJECT = "Report-Limits-Second-Route"
GAMUT_RUN = "run2"


def script_i(language: str):
    """K37 (i): the control-strip rows of a FROM PROFILE GAMUT run, their
    note, and the cube-corner table beside them."""
    def script(d):
        rec = d.record
        rec.update({"language": language, "mode": "ON SCREEN",
                    "pack": str(DEMO_PACK), "scene": "i"})
        tag = language
        from core.i18n import tr
        from workflow import compliance_sets as cs
        rec["iso_file_in_use"] = cs.iso_data_path_text()
        K36._install_watchdog(d, rec)
        d.open_project(GAMUT_PROJECT)
        d.set_bar(run=GAMUT_RUN, run_type="Verification")
        yield 1000
        d.launch_tool("measurement_report")
        yield 4000
        dlg = K36._wait(d, "MeasurementReportDialog")
        if dlg is None:
            d.note("NO REPORT WINDOW")
            return
        K36._new_report_everything(d, dlg)
        if not dlg._detail_check.isChecked():
            dlg._detail_check.setChecked(True)
        yield 2000
        # one set that numbers the control-strip rows on every drive, chosen
        # the way a user chooses it, so before and after read alike
        rec["set_chosen"] = K36._choose(dlg._set_combo, "custom_iso_12647_7")
        rec["set_text"] = dlg._set_combo.currentText()
        yield 1500
        # the page shows a set once a report is generated with it: Generate,
        # and answer the Update / Create New question (if asked) with Create
        # New, into this drive's own copy of the project
        if dlg._generate_btn.isEnabled():
            K36.EXPECTED.add("QMessageBox")
            d.later(dlg._generate_btn.click)
            yield 1500
            rec["generate_question"] = d.answer(
                "Create New" if language == "en" else "Neu erstellen",
                f"{tag}-i0-generate-asks", within_ms=4000)
            K36.EXPECTED.discard("QMessageBox")
        yield 5000
        text = K36._view_text(dlg)
        rec["report_text"] = text
        for key, needle, n in (
                ("results", tr("Report Results"), 2200),
                ("notes", tr("Notes on the verdicts above:"), 2600),
                ("corners", tr("Cube corners (ΔE00)"), 700)):
            i = text.find(needle)
            rec[key] = text[i:i + n] if i >= 0 else None
            d.note(f"   {key}: {rec[key]!r}"[:900])
        try:
            runs = list(dlg._runs_for_report() or [])
        except Exception:                                  # noqa: BLE001
            runs = []
        rec["sheets"] = [{"created": r.get("created"),
                          "strip": {k: (r.get("control_strip") or {}).get(k)
                                    for k in ("n", "avg", "max", "p95")},
                          "strip_corner_aims": r.get("strip_corner_aims")}
                         for r in runs]
        d.note(f"   sheets: {rec['sheets']}"[:1200])
        K36._scroll_to(dlg, tr("Report Results"))
        yield 1200
        d.shot(dlg, f"{tag}-i1-report-results")
        K36._scroll_to(dlg, tr("Average ΔE00, control strip"))
        yield 1200
        d.shot(dlg, f"{tag}-i2-strip-rows")
        K36._scroll_to(dlg, tr("Notes on the verdicts above:"))
        yield 1200
        d.shot(dlg, f"{tag}-i3-notes")
        K36._scroll_to(dlg, tr("Cube corners (ΔE00)"))
        yield 1200
        d.shot(dlg, f"{tag}-i4-cube-corner-table")
        dlg.close()
        yield 1500
    return script


def main() -> int:
    out = Path(sys.argv[1])
    language = sys.argv[2] if len(sys.argv) > 2 else "en"
    scene = sys.argv[3] if len(sys.argv) > 3 else "e"
    if scene == "i":
        d = Drive(out, projects=[GAMUT_PROJECT], language=language)
        rc = d.run(script_i(language))
        print(f"rc={rc}")
        return rc
    d = Drive(out, projects=[PROJECT], language=language)
    rc = d.run(script_for(language))
    print(f"rc={rc}")
    return rc


if __name__ == "__main__":
    sys.exit(main())
