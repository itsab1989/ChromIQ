#!/usr/bin/env python3
"""Challenge 5 of beta 42, the fixes (B8-1091 to B8-1095), ON SCREEN.

    CHROMIQ_DEMO_PACK=<pack> CHROMIQ_TREE=<tree> \\
        python drive_b42_c5_fixes.py <out> <lang> <scene> <project> <run> [arg...]

scene "saved" <date>: Verification, Measurement Report, pick the saved report
    of <date>; read and photograph Report Scope, Report Results and the notes;
    then (M2) tick "Show detailed data" and Save report as PDF (the chooser is
    answered with a path); then Clear List and Save report as PDF again. The
    verdict words of each PDF are read out of the file and compared with the
    page's.
scene "generate" [set]: "New report…", every date, detailed data, (Judged
    against <set>), Generate report; read and photograph the page the press
    wrote (M4), and the Paper white and Control strip graphs.
scene "trend": "New report…", every date: the Control strip graph's page
    (B8-1095), shown the way challenge 5 showed it.

Every popup is answered by the drive; a watchdog cancels anything else after
3 s, and a QFileDialog is expected while the drive fills it in.
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
from userdrive import DEMO_PACK, Drive                         # noqa: E402
import drive_b42_k36 as K36                                    # noqa: E402

K36.DEADLINE_S = 900
_WORDS = re.compile(r"\b(PASS|FAIL|COND|INFO|N-A)\b")


def _tr(s: str) -> str:
    from core.i18n import tr
    return tr(s)


def _results_words(text: str) -> list:
    a = text.find(_tr("Report Results"))
    b = text.find(_tr("Notes on the verdicts above:"), a)
    if a < 0:
        return []
    return _WORDS.findall(text[a:b if b > a else None])


def _pdf_text(path: Path) -> str:
    from pypdf import PdfReader
    t = "\n".join(p.extract_text() or "" for p in PdfReader(str(path)).pages)
    return re.sub(r"[ \t\xa0]+", " ", t)


def _messages() -> dict:
    """The sentences the page is searched for, in the drive's language."""
    from workflow import measurement_messages as M
    out = {}
    for mid in ("M-REPORT-NO-PAPER-PATCH", "M-REPORT-PAPER-WHITE-FROM-PROFILE",
                "M-REPORT-JUDGED-ABSOLUTE-NO-PAPER-WHITE",
                "M-REPORT-STRIP-CORNERS-PREDICTED",
                "M-REPORT-STRIP-CORNERS-IDEAL", "M-REPORT-WORKED-OUT-EARLIER"):
        m = M.CATALOGUE.get(mid)
        if m is None:
            continue
        try:
            body = m.render(profile="§", L="§", a="§", b="§")[1]
        except Exception:                                  # noqa: BLE001
            body = m.render()[1]
        # 60 characters from the middle of its longest literal stretch: two
        # of these notes share their first sentence and their last
        chunk = max(body.split("§"), key=len)
        mid_at = max(0, len(chunk) // 2 - 30)
        out[mid] = chunk[mid_at:mid_at + 60]
    return out


def _read(d, dlg, rec, tag):
    text = K36._view_text(dlg)
    (d.out / f"{tag}-page.txt").write_text(text, encoding="utf-8")
    flat = " ".join(text.split())
    rec["words"] = _results_words(text)
    rec["messages"] = {mid: (" ".join(s.split()) in flat)
                       for mid, s in _messages().items()}
    i = text.find(_tr("How the colours were judged"))
    rec["how_judged"] = text[i:i + 400] if i >= 0 else None
    rec["gen"] = K36._generate_state(dlg)
    d.note(f"[{tag}] words={rec['words']}")
    d.note(f"[{tag}] messages={rec['messages']}")
    d.note(f"[{tag}] how judged={(rec['how_judged'] or '')[:200]!r}")
    return text


def _shot(d, dlg, name):
    """A photograph, asked again once if the window server refused it."""
    if not d.shot(dlg, name):
        d.pump(1500)
        d.shot(dlg, name)


def _shots(d, dlg, tag, needles):
    for n, needle in enumerate(needles, 1):
        if K36._scroll_to(dlg, needle):
            d.pump(900)
            _shot(d, dlg, f"{tag}-{n:02d}-"
                   + re.sub(r"[^a-z0-9]+", "-", needle.lower())[:30])


def _save_pdf(d, dlg, rec, tag):
    """Save report as PDF…, answer the chooser with a path; yields."""
    pdf = d.out / f"{tag}.pdf"
    K36.EXPECTED.add("QFileDialog")
    d.later(dlg._pdf_btn.click)
    yield 800
    rec["pdf_chosen"] = d.answer_file(pdf, f"{tag}-pdf-dialog", within_ms=8000)
    yield 6000
    K36.EXPECTED.discard("QFileDialog")
    rec["pdf_written"] = pdf.is_file()
    if pdf.is_file():
        t = _pdf_text(pdf)
        (d.out / f"{tag}.pdf.txt").write_text(t, encoding="utf-8")
        rec["pdf_words"] = _results_words(t)
        d.note(f"[{tag}] pdf words={rec['pdf_words']}")


def script(scene, project, run, args):
    def s(d):
        rec = d.record
        rec.update({"scene": scene, "project": project, "run": run,
                    "args": args, "pack": str(DEMO_PACK), "tree": TREE})
        K36._install_watchdog(d, rec)
        from PyQt6.QtGui import QDesktopServices
        QDesktopServices.openUrl = staticmethod(lambda *a, **k: True)
        d.open_project(project)
        d.set_bar(run=run, run_type="Verification")
        yield 1000
        d.launch_tool("measurement_report")
        yield 4000
        dlg = K36._wait(d, "MeasurementReportDialog")
        if dlg is None:
            d.note("NO REPORT WINDOW")
            return
        combo = dlg._saved_combo
        rec["saved_list"] = [combo.itemText(i) for i in range(combo.count())]
        d.note(f"saved list: {rec['saved_list']}")
        if scene == "saved":
            date = args[0]
            idx = next((i for i in range(combo.count())
                        if date in combo.itemText(i)), None)
            if idx is None:
                d.note(f"no saved report for {date}")
                return
            combo.setCurrentIndex(idx)
            yield 3500
            r = rec.setdefault("open", {})
            r["picked"] = combo.itemText(idx)
            page = _read(d, dlg, r, "open")
            _shots(d, dlg, "open", [_tr("Report Scope"), _tr("Report Results"),
                                    _tr("Notes on the verdicts above:")])
            # M2: one setting touched, the page kept, the PDF
            dlg._detail_check.setChecked(not dlg._detail_check.isChecked())
            yield 1500
            t = rec.setdefault("touched", {})
            t["page_kept"] = K36._view_text(dlg) == page
            t["red_line"] = dlg._stale_label.isVisible()
            _shot(d, dlg, "touched-red-line")
            yield from _save_pdf(d, dlg, t, "touched")
            t["pdf_is_page"] = t.get("pdf_words") == r["words"]
            d.note(f"[touched] page kept={t['page_kept']} "
                   f"pdf is page={t['pdf_is_page']}")
            # and Clear List
            dlg._clear_btn.click()
            yield 1500
            c = rec.setdefault("cleared", {})
            c["page_kept"] = K36._view_text(dlg) == page
            _shot(d, dlg, "cleared")
            yield from _save_pdf(d, dlg, c, "cleared")
            c["pdf_is_page"] = c.get("pdf_words") == r["words"]
            d.note(f"[cleared] page kept={c['page_kept']} "
                   f"pdf is page={c['pdf_is_page']}")
        elif scene in ("generate", "trend"):
            K36._new_report_everything(d, dlg)
            yield 2500
            if not dlg._detail_check.isChecked():
                dlg._detail_check.setChecked(True)
                yield 2000
            if scene == "generate":
                if args:
                    rec["set_chosen"] = K36._choose(dlg._set_combo, args[0])
                    yield 1500
                pre = rec.setdefault("before_press", {})
                _read(d, dlg, pre, "new-report")
                K36.EXPECTED.add("QMessageBox")
                d.later(dlg._generate_btn.click)
                yield 8000
                K36.EXPECTED.discard("QMessageBox")
                g = rec.setdefault("generated", {})
                g["picked"] = combo.currentText()
                d.note(f"[generated] report shown: {g['picked']}")
                _read(d, dlg, g, "generated")
                _shots(d, dlg, "generated", [
                    _tr("How the colours were judged"),
                    _tr("Notes on the verdicts above:")])
            tabs = dlg._trend_tabs
            for key, chart in (("white", getattr(dlg, "_trend_white", None)),
                               ("strip", dlg._trend_groups.get("strip"))):
                if chart is None:
                    continue
                i = tabs.indexOf(chart)
                rec.setdefault("graphs", {})[key] = {
                    "tab_visible": tabs.isTabVisible(i),
                    "points": len(getattr(chart, "_series", []) or []),
                    "reason": (chart.empty_reason()
                               if hasattr(chart, "empty_reason") else None)}
                tabs.setCurrentIndex(i)
                yield 1200
                _shot(d, dlg, f"graph-{key}")
                d.note(f"[graph {key}] {rec['graphs'][key]}")
        dlg.close()
        yield 1500
    return s


def main() -> int:
    out = Path(sys.argv[1])
    lang, scene, project, run = sys.argv[2:6]
    d = Drive(out, projects=[project], language=lang)
    rc = d.run(script(scene, project, run, sys.argv[6:]))
    print(f"rc={rc}")
    return rc


if __name__ == "__main__":
    sys.exit(main())
