#!/usr/bin/env python3
"""#182 G12: every N-A note, and the Printing record's detailed sections,
driven ON SCREEN.

    CHROMIQ_DEMO_PACK=<folder holding Report-Notes-Every-Reason and
    Report-Limits-Evenness> python scripts/drive_g12_notes.py <out> <group>

groups:
    before   run1's profiling sheet as a Printing record, detail on: the
             state of the tree the drive runs on (point CHROMIQ_TREE at the
             beta 38 tree for the photograph before the change)
    W<n>     one window of the list below, by its tag's prefix
    all      every window of the notes demo: each run's verification
             document with every date ticked and detail on (Full colour
             check), and the Printing records of run1 and run7; each
             photographed at its notes and saved as a PDF whose pages are
             rendered

For every window the drive records which rows read N-A with which reason, the
sentence the app has for it, whether that sentence is in the window's text and
on which PDF pages it is printed (`notes-found.json`).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from userdrive import Drive                                   # noqa: E402

NOTES = "Report-Notes-Every-Reason"

#: (tag, run, run type, what the window is for)
WINDOWS = [
    ("W1-run1-verification", "run1", "Verification",
     "fifteen mid-cube colours: no greys, no ramp, small sample, no surface, "
     "small outer quarter, no repeats, no strip, design reference, small page"),
    ("W2-run1-printing-record", "run1", "Profiling",
     "the same chart's profiling sheet: the Printing record (G12 item 1)"),
    ("W3-run2-verification", "run2", "Verification",
     "five grey steps and one repeated colour; no white; no black; the "
     "charts changed between the dates"),
    ("W4-run3-verification", "run3", "Verification",
     "a control strip of five patches"),
    ("W5-run4-verification", "run4", "Verification",
     "stored Lab aims, no patch at a cube corner"),
    ("W6-run5-verification", "run5", "Verification",
     "evenness: no positions, no page geometry, a ninth not measured, 30 % "
     "covered, noisy"),
    ("W7-run6-verification", "run6", "Verification",
     "reports saved by older ChromIQ: blocks missing with the measurement "
     "gone; grey rows for information because the printing was not recorded"),
    ("W8-run7-printing-record", "run7", "Profiling",
     "readings with no device values and no chart"),
]


#: A Profiling window lists every run's profiling sheet. Unticking some leaves
#: the page as it was ("Settings changed…") until Generate, so none are.
ONLY: dict = {}  # "New report…" ticks every profiling sheet; unticking needs Generate


def render_pdf(pdf: Path, out: Path) -> list:
    from PyQt6.QtCore import QSize
    from PyQt6.QtPdf import QPdfDocument
    doc = QPdfDocument(None)
    doc.load(str(pdf))
    pages = []
    for i in range(doc.pageCount()):
        sz = doc.pagePointSize(i)
        img = doc.render(i, QSize(int(sz.width() * 2), int(sz.height() * 2)))
        p = out / f"{pdf.stem}-page{i + 1:02d}.png"
        img.save(str(p))
        pages.append(p.name)
    return pages


def pdf_pages_text(pdf: Path) -> list:
    from PyQt6.QtPdf import QPdfDocument
    doc = QPdfDocument(None)
    doc.load(str(pdf))
    return [doc.getAllText(i).text() for i in range(doc.pageCount())]


def _flat(s: str) -> str:
    return " ".join(str(s).split())


def script_for(group):
    def script(d):
        rec = d.record
        rec["group"] = group
        rec["windows"] = {}
        d.open_project(NOTES)

        def wait_dialog():
            for _ in range(80):
                dlg = d.top_dialog("MeasurementReportDialog")
                if dlg is not None:
                    return dlg
                d.pump(250)
            return None

        def tick_all(dlg, only=None):
            """Tick every measurement row, or only the rows whose text holds
            *only* (a Profiling window lists every run's profiling sheet)."""
            from PyQt6.QtCore import Qt
            lst = dlg._profile_list
            for i in range(lst.count()):
                it = lst.item(i)
                if it.flags() & Qt.ItemFlag.ItemIsUserCheckable:
                    on = only is None or only in it.text()
                    it.setCheckState(Qt.CheckState.Checked if on
                                     else Qt.CheckState.Unchecked)
                    d.pump(150)

        def scroll_to(dlg, text: str, occurrence: int = 0) -> bool:
            """Scroll the report page so *text* sits near the top, the way a
            user scrolls down to read it."""
            view = dlg._view
            doc = view.document()
            cur = None
            start = 0
            for _ in range(occurrence + 1):
                c = doc.find(text, start)
                if c.isNull():
                    return False
                cur, start = c, c.selectionEnd()
            from PyQt6.QtGui import QTextCursor
            plain = QTextCursor(cur)
            plain.setPosition(cur.selectionStart())
            view.setTextCursor(plain)
            sb = view.verticalScrollBar()
            rect = view.cursorRect(plain)
            sb.setValue(max(0, sb.value() + rect.top() - 30))
            d.pump(500)
            return True

        def save_pdf(dlg, name):
            target = d.out / "pdf" / f"{name}.pdf"
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists():
                target.unlink()
            d.later(dlg._pdf_btn.click)
            yield 1500
            ok = d.answer_file(target, name=None)
            for _ in range(120):
                yield 1000
                if target.exists():
                    break
            yield 3000
            out = {"pdf": str(target), "written": target.exists(),
                   "dialog_ok": ok, "pages": [], "text": []}
            if target.exists():
                pages_dir = d.out / "pdf-pages"
                pages_dir.mkdir(exist_ok=True)
                out["pages"] = render_pdf(target, pages_dir)
                out["text"] = pdf_pages_text(target)
                (pages_dir / f"{name}.txt").write_text(
                    "\n\f\n".join(out["text"]), encoding="utf-8")
            d.note(f"   PDF {target.name}: "
                   f"{'written, %d pages' % len(out['pages']) if out['written'] else 'NOT WRITTEN'}")
            dlg.raise_()
            rec.setdefault("pdfs", {})[name] = {k: v for k, v in out.items()
                                                if k != "text"}
            return out

        plan = (WINDOWS if group == "all" else [WINDOWS[1]]
                if group == "before" else
                [w for w in WINDOWS if w[0].startswith(group)])
        for tag, run, run_type, what in plan:
            d.note(f"[{tag}] {what}")
            d.set_bar(run_type=run_type, run=run)
            d.pump(900)
            d.launch_tool("measurement_report")
            yield 3500
            dlg = wait_dialog()
            if dlg is None:
                m = d.modal()
                d.note(f"[{tag}] NO report window; modal "
                       f"{type(m).__name__ if m else None}")
                if m is not None:
                    d.shot(m, f"{tag}-UNEXPECTED")
                continue
            # "New report…", every date ticked, detail on: what a user does
            # to see every measurement of the run in one document
            dlg._saved_combo.setCurrentIndex(0)
            dlg._saved_combo.activated.emit(0)
            yield 1500
            tick_all(dlg, ONLY.get(tag))
            yield 800
            if not dlg._detail_check.isChecked():
                dlg._detail_check.click()
            yield 2500
            runs = dlg._runs_for_report()
            from workflow.compliance_sets import N_A
            found = []
            text = _flat(dlg._view.toPlainText())
            for r in runs:
                rows, _rec = dlg._verdict_rows(r)
                for x in rows:
                    reason = x.get("reason")
                    if not reason:
                        continue
                    said = dlg._reason_sentence(reason, r, x)
                    found.append({
                        "date": str(r.get("created") or "")[:19],
                        "row": x.get("row_id"), "word": x.get("word"),
                        "reason": reason, "sentence": said,
                        "in_window": bool(said) and _flat(said) in text})
            numbered = dlg._numbered_notes(runs)
            w = {"what": what, "run": run, "run_type": run_type,
                 "type": dlg._report_type_now(),
                 "ticked_dates": [str(r.get("created") or "")[:19]
                                  for r in runs],
                 "numbered_notes": [[n, where, s] for n, where, s in numbered],
                 "rows_with_reasons": found,
                 "window_text_has_values_heading":
                     "Notes on the values above:" in text,
                 "window_text_has_verdicts_heading":
                     "Notes on the verdicts above:" in text,
                 "measured_but_not_graded":
                     "Measured but not graded" in text}
            rec["windows"][tag] = w
            d.note(f"   type {w['type']}, dates {w['ticked_dates']}, "
                   f"{len(numbered)} numbered notes, "
                   f"{sum(1 for f in found if f['word'] == N_A)} N-A rows")
            # photographs: the top, the notes under the results grid, and the
            # notes under each detailed table
            dlg._view.verticalScrollBar().setValue(0)
            d.shot(dlg, f"{tag}-01-top")
            head = ("Notes on the values above:"
                    if w["window_text_has_values_heading"]
                    else "Notes on the verdicts above:")
            k = 0
            while scroll_to(dlg, head, k) and k < 8:
                d.shot(dlg, f"{tag}-{k + 2:02d}-notes-{k + 1}")
                k += 1
            if w["measured_but_not_graded"] and scroll_to(
                    dlg, "Measured but not graded"):
                d.shot(dlg, f"{tag}-{k + 2:02d}-measured-but-not-graded")
            if scroll_to(dlg, "Detailed data per measurement run"):
                d.shot(dlg, f"{tag}-{k + 3:02d}-detailed")
            pdf = yield from save_pdf(dlg, tag)
            pages = pdf.get("text") or []
            for f in found:
                f["pdf_pages"] = [i + 1 for i, t in enumerate(pages)
                                  if f["sentence"] and _flat(f["sentence"])
                                  in _flat(t)]
            w["pdf"] = pdf["pdf"]
            w["pdf_page_images"] = pdf["pages"]
            (d.out / "notes-found.json").write_text(
                json.dumps(rec["windows"], indent=2), encoding="utf-8")
            dlg.close()
            yield 1200
    return script


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(2)
    out, group = Path(sys.argv[1]), sys.argv[2]
    d = Drive(out, projects=[NOTES])
    sys.exit(d.run(script_for(group)))
