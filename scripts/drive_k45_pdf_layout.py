#!/usr/bin/env python3
"""K45 (Knut, #182 5834422633): the Measurement Report's PDF layout, driven
ON SCREEN, on any tree, so the same cases run before and after a change.

    CHROMIQ_DEMO_PACK=<pack> CHROMIQ_TREE=<tree> \\
        python drive_k45_pdf_layout.py <out> <en|de> <case> [<case> ...]

A case is ``tag:project:run:runtype:type_id:set_id:ticks``:

  * ``runtype`` ``verification`` or ``profiling``;
  * ``type_id`` a report type id (``t1_colour_summary`` ...);
  * ``set_id`` a limit set id, or ``-`` for what the window offers;
  * ``ticks`` ``all``, or ``N`` for the first N measurements of the list.

For each case the report window is opened from the Tools menu entry, "New
report…" is chosen in "Report shown", the type, the set and the ticks are set,
Generate report is pressed, the window is photographed with the Colour
accuracy graph in front (and the Grey balance graph where there is one), and
"Save report as PDF…" is answered in ChromIQ's own file dialog with
``<out>/<lang>-<tag>.pdf``.

**NOBODY HAS TO CLICK.** Every question the drive expects it answers itself; a
watchdog photographs and cancels anything else after three seconds; a deadline
ends the run whatever happens. The one thing replaced is
``QDesktopServices.openUrl``, so a saved PDF is not opened in a viewer for
every case. The pack is copied, never written.
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

TREE = os.environ.get("CHROMIQ_TREE") or str(Path(__file__).resolve().parents[1])
sys.path.insert(0, TREE + "/scripts")
sys.path.insert(0, TREE)
from userdrive import Drive                                    # noqa: E402
import drive_b42_k36 as K36                                    # noqa: E402

K36.DEADLINE_S = 1500


def _cases(argv) -> list:
    out = []
    for a in argv:
        tag, project, run, runtype, tid, sid, ticks = a.split(":")
        out.append({"tag": tag, "project": project, "run": run,
                    "runtype": runtype, "type": tid,
                    "set": None if sid == "-" else sid, "ticks": ticks})
    return out


def _pick_data(combo, data) -> bool:
    i = combo.findData(data)
    if i < 0:
        return False
    combo.setCurrentIndex(i)
    combo.activated.emit(i)
    return True


def _tick(dlg, ticks: str) -> list:
    from PyQt6.QtCore import Qt
    items = [dlg._profile_list.item(i)
             for i in range(dlg._profile_list.count())]
    # the dated measurements only; a group row above them ticks them all
    items = [it for it in items
             if it.flags() & Qt.ItemFlag.ItemIsUserCheckable
             and re.match(r"\s*\d{4}-\d{2}-\d{2}", it.text())]
    n = len(items) if ticks == "all" else int(ticks)
    for k, it in enumerate(items):
        want = Qt.CheckState.Checked if k < n else Qt.CheckState.Unchecked
        if it.checkState() != want:
            it.setCheckState(want)
    return [(it.text().strip()[:60], it.checkState() == Qt.CheckState.Checked)
            for it in items]


def _key_text(dlg) -> "str | None":
    """The limit-line key under the graph in front, or None when the tree
    being driven has none (the tree before K45) or it is hidden."""
    key = getattr(dlg, "_trend_key", None)
    return key.text() if key is not None and key.isVisible() else None


def _tab_to(dlg, chart) -> bool:
    tabs = dlg._trend_tabs
    i = tabs.indexOf(chart)
    if i < 0 or not tabs.isTabVisible(i):
        return False
    tabs.setCurrentIndex(i)
    return True


def script(cases, lang):
    def s(d):
        rec = d.record
        rec.update({"language": lang, "tree": TREE, "mode": "ON SCREEN",
                    "cases": {}})
        K36._install_watchdog(d, rec)
        from PyQt6.QtGui import QDesktopServices
        QDesktopServices.openUrl = staticmethod(lambda *a, **k: True)
        import ui.dialogs.measurement_report_dialog as mrd
        yield 500
        for c in cases:
            tag = f"{lang}-{c['tag']}"
            cr = rec["cases"].setdefault(c["tag"], dict(c))
            d.note(f"== case {tag}: {c}")
            d.open_project(c["project"])
            d.set_bar(run=c["run"], run_type=c["runtype"])
            d.pump(1200)
            d.launch_tool("measurement_report")
            yield 4500
            dlg = K36._wait(d, "MeasurementReportDialog")
            if dlg is None:
                cr["error"] = "no report window"
                d.note("NO REPORT WINDOW")
                continue
            dlg.resize(1400, 980)
            yield 1500
            _pick_data(dlg._saved_combo, mrd.NEW_REPORT_KEY)
            yield 2000
            cr["type_set"] = _pick_data(dlg._type_combo, c["type"])
            yield 1500
            if c["set"]:
                cr["set_set"] = _pick_data(dlg._set_combo, c["set"])
                yield 1500
            cr["ticks"] = _tick(dlg, c["ticks"])
            yield 1500
            if not dlg._detail_check.isChecked():
                dlg._detail_check.setChecked(True)
                yield 800
            K36.EXPECTED.add("QMessageBox")
            d.later(dlg._generate_btn.click)
            yield 600
            said = d.answer("neu" if lang == "de" else "new", f"{tag}-question",
                            within_ms=4000)
            cr["generate_question"] = said
            K36.EXPECTED.discard("QMessageBox")
            yield 9000
            cr["state"] = {"type": dlg._type_combo.currentText(),
                           "set": dlg._set_combo.currentText(),
                           "shown": dlg._saved_combo.currentText(),
                           "red_line": dlg._stale_label.isVisible()}
            # the Colour accuracy graph in front, and what is under it
            if _tab_to(dlg, dlg._trend_de):
                yield 1200
                cr["window_key_accuracy"] = _key_text(dlg)
                cr["accuracy_descriptions"] = [
                    t for _k, _c, t in dlg._trend_de.descriptions()]
                d.shot(dlg, f"{tag}-01-window-colour-accuracy")
            grey = dlg._trend_groups.get("grey")
            if grey is not None and _tab_to(dlg, grey):
                yield 1200
                cr["window_key_grey"] = _key_text(dlg)
                d.shot(dlg, f"{tag}-02-window-grey-balance")
            if K36._scroll_to(dlg, mrd.tr("How to read this report")):
                yield 900
                d.shot(dlg, f"{tag}-03-window-how-to-read")
            pdf = d.out / f"{tag}.pdf"
            pdf.unlink(missing_ok=True)
            K36.EXPECTED.add("QFileDialog")
            d.later(dlg._pdf_btn.click)
            yield 800
            cr["pdf_chosen"] = d.answer_file(pdf, f"{tag}-04-pdf-dialog",
                                             within_ms=8000)
            yield 7000
            K36.EXPECTED.discard("QFileDialog")
            cr["pdf"] = pdf.name if pdf.is_file() else None
            d.note(f"   pdf {pdf.name}: {'written' if pdf.is_file() else 'MISSING'}")
            dlg.close()
            yield 2000
        (d.out / f"{lang}-cases.json").write_text(
            json.dumps(rec["cases"], indent=2, ensure_ascii=False,
                       default=str), encoding="utf-8")
    return s


def main() -> int:
    out = Path(sys.argv[1])
    lang = sys.argv[2]
    cases = _cases(sys.argv[3:])
    projects = sorted({c["project"] for c in cases})
    d = Drive(out, projects=projects, language=lang)
    rc = d.run(script(cases, lang))
    print(f"rc={rc}")
    return rc


if __name__ == "__main__":
    sys.exit(main())
