#!/usr/bin/env python3
"""B8-1591 (Knut, #182 5858874320): no setting of the Measurement Report
window changes the page before Generate Report is pressed. Driven ON SCREEN
in the real app.

    CHROMIQ_DEMO_PACK=<pack> CHROMIQ_LOG_DIR=<sandbox> \\
        python scripts/drive_b8_1591_nothing_moves_before_generate.py <out>

Knut: *"Any change in settings will give a red text to click generate
report, no matter if the loaded report is an old or new report. Clicking
Generate Report will either create a new report, update the selected report
(unless canceled.). new or update will always regenerate according to the
version of ChromIQ that is running. No regenerating or change of the report
text happens before Generate Report is pressed."*

Scene 1, Report-Limits-Evenness run1 (a saved report of several dates):
every setting of the window is moved in turn (Report type, Judged against,
Edit limits…, Show detailed data, one measurement's tick, Deselect all,
Select all), and after each the page (its text, the trend graphs and the key
under them) is compared with the page before, the red line is read, and the
setting is put back. Photographs before and after the first. Then a PDF is
saved with a setting moved and its text compared with the page, and
Generate Report is pressed and answered "Update".

Scene 2, Report-Notes-Every-Reason run4: the 2026-11-02 report, whose
filtered "against the whole sheet" figure is 0.00, photographed at its
evenness notes (B8-1502's sentence).

Scene 3, Report-Notes-Every-Reason run6: the 2026-11-02 measurement taken
off the disk of the COPY (its dated folder holds none and its archive is
removed), a New report of every date, Generate pressed: the page carries
M-REPORT-NOT-WORKED-OUT, photographed.

Every modal the drive does not expect is photographed and cancelled by the
watchdog, the "Auto-update preview" window included; a deadline ends the run.
The pack is copied, never written.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import sys
from pathlib import Path

TREE = os.environ.get("CHROMIQ_TREE") or str(Path(__file__).resolve().parents[1])
sys.path.insert(0, TREE + "/scripts")
sys.path.insert(0, TREE)
from userdrive import Drive                                    # noqa: E402
import drive_b42_k36 as K36                                    # noqa: E402
import drive_k45_pdf_layout as K45                             # noqa: E402

K36.DEADLINE_S = 1200
# "Auto-update preview is on" is an _InfoDialog: answered, never waited on.
K36.OURS = {n for n in K36.OURS if n != "_InfoDialog"}
EVEN = "Report-Limits-Evenness"
NOTES = "Report-Notes-Every-Reason"


def _trend_signature(dlg) -> str:
    """Every graph's data, limit lines and notes, and the key under them."""
    parts = []
    tabs = getattr(dlg, "_trend_tabs", None)
    if tabs is not None:
        for i in range(tabs.count()):
            w = tabs.widget(i)
            parts.append(tabs.tabText(i))
            for name in ("_series", "_thresholds", "_limit_lines",
                         "_line_notes", "_no_limit_text", "_info_note"):
                parts.append(repr(getattr(w, name, None)))
    key = getattr(dlg, "_trend_key", None)
    parts.append(key.text() if key is not None else "")
    return hashlib.sha1("\n".join(parts).encode()).hexdigest()


def _page(dlg) -> dict:
    text = dlg._view.toPlainText()
    return {"text_sha": hashlib.sha1(text.encode()).hexdigest(),
            "html_sha": hashlib.sha1(dlg._view.toHtml().encode()).hexdigest(),
            "trend_sha": _trend_signature(dlg),
            "chars": len(text),
            "red_line": bool(dlg._stale_label.isVisible()),
            "red_text": dlg._stale_label.text(),
            "shown": dlg._saved_combo.currentText()}


def _same(a: dict, b: dict) -> bool:
    return (a["text_sha"], a["html_sha"], a["trend_sha"]) == (
        b["text_sha"], b["html_sha"], b["trend_sha"])


def _other_data(combo):
    """An entry of *combo* other than the current one that a user can choose."""
    m = combo.model()
    cur = combo.currentData()
    for i in range(combo.count()):
        item = m.item(i) if hasattr(m, "item") else None
        if item is not None and not item.isEnabled():
            continue
        if combo.itemData(i) not in (None, cur):
            return combo.itemData(i)
    return None


def _first_run_item(dlg):
    """The first measurement row that is TICKED, so unticking it is a move."""
    from PyQt6.QtCore import Qt
    for i, (kind, _si, _k) in enumerate(dlg._list_rows):
        item = dlg._profile_list.item(i)
        if kind == "run" and item.checkState() == Qt.CheckState.Checked:
            return item
    return None


def _ticks(dlg) -> list:
    return [dlg._profile_list.item(i).checkState()
            for i, (kind, _si, _k) in enumerate(dlg._list_rows) if kind == "run"]


def _put_ticks(dlg, states) -> None:
    rows = [i for i, (kind, _si, _k) in enumerate(dlg._list_rows)
            if kind == "run"]
    for i, st in zip(rows, states):
        dlg._profile_list.item(i).setCheckState(st)


def _pdf_text(d, dlg, name) -> str:
    """Save report as PDF… through the real button's code, the file chooser
    answered with a path in the proof folder, and read the file back."""
    import ui.widgets as _w
    from PyQt6.QtGui import QDesktopServices
    from pypdf import PdfReader
    out = d.out / f"{name}.pdf"
    real_save, real_open = _w.save_file_dialog, QDesktopServices.openUrl
    _w.save_file_dialog = lambda *a, **k: str(out)
    QDesktopServices.openUrl = staticmethod(lambda *a, **k: True)
    try:
        dlg._export_pdf()
        d.pump(800)
    finally:
        _w.save_file_dialog = real_save
        QDesktopServices.openUrl = real_open
    if not out.is_file():
        return ""
    text = "\n".join(pg.extract_text() or ""
                     for pg in PdfReader(str(out)).pages)
    return re.sub(r"[ \t\xa0]+", " ", text)


def _scroll_to(d, dlg, needle, name):
    from PyQt6.QtGui import QTextCursor
    view = dlg._view
    view.moveCursor(QTextCursor.MoveOperation.Start)
    found = view.find(needle)
    if found:
        view.ensureCursorVisible()
        sb = view.verticalScrollBar()
        sb.setValue(min(sb.maximum(), sb.value() + view.height() // 3))
    cur = QTextCursor(view.textCursor())
    cur.clearSelection()
    view.setTextCursor(cur)
    d.pump(500)
    d.shot(dlg, name)
    return bool(found)


def _open_report(d, project, run):
    d.open_project(project)
    d.set_bar(run=run, run_type="verification")
    d.pump(1200)
    d.launch_tool("measurement_report")
    return None


def script():
    def s(d):
        rec = d.record
        assert os.environ.get("CHROMIQ_LOG_DIR"), "SANDBOX THE LOG FIRST"
        K36._install_watchdog(d, rec)
        from PyQt6.QtCore import Qt
        import ui.dialogs.measurement_report_dialog as mrd
        from ui.dialogs.thresholds_dialog import RUN_COLUMN
        yield 600

        # ---------------------------------------------------------------
        # SCENE 1: every setting, the page before and after
        # ---------------------------------------------------------------
        _open_report(d, EVEN, "run1")
        yield 4500
        dlg = K36._wait(d, "MeasurementReportDialog")
        if dlg is None:
            rec["error"] = "no report window"
            return
        dlg.resize(1420, 980)
        yield 2500
        base = _page(dlg)
        rec["opened_on"] = base["shown"]
        rec["baseline"] = base
        d.shot(dlg, "01-saved-report-before-a-setting-moves")
        results = rec.setdefault("settings", [])

        def check(label, do, undo, photo=None):
            """Move one setting, read the page, put it back, read it again."""
            before = _page(dlg)
            ok = do()
            d.pump(1800)
            after = _page(dlg)
            if photo:
                d.shot(dlg, photo)
            undo()
            d.pump(1500)
            back = _page(dlg)
            results.append({
                "setting": label, "moved": bool(ok),
                "page_unchanged": _same(before, after),
                "red_line_after_move": after["red_line"],
                "red_text": after["red_text"],
                "shown_after_move": after["shown"],
                "page_unchanged_after_undo": _same(before, back),
                "red_line_after_undo": back["red_line"]})
            d.note(f"   [{label}] moved={ok} unchanged={_same(before, after)}"
                   f" red={after['red_line']} undo-same={_same(before, back)}"
                   f" red-after-undo={back['red_line']}")

        # Report type
        t0 = dlg._type_combo.currentData()
        t1 = _other_data(dlg._type_combo)
        check("Report type",
              lambda: K36._choose(dlg._type_combo, t1) if t1 else False,
              lambda: K36._choose(dlg._type_combo, t0),
              photo="02-report-type-moved-page-unchanged-red-line")
        yield 800
        # Judged against
        s0 = dlg._set_combo.currentData()
        s1 = _other_data(dlg._set_combo)
        check("Judged against",
              lambda: K36._choose(dlg._set_combo, s1) if s1 else False,
              lambda: K36._choose(dlg._set_combo, s0))
        yield 800
        # Show detailed data
        det = dlg._detail_check.isChecked()
        check("Show detailed data",
              lambda: (dlg._detail_check.setChecked(not det), True)[1],
              lambda: dlg._detail_check.setChecked(det))
        yield 800
        # one measurement's tick
        item = _first_run_item(dlg)
        check("one measurement unticked",
              lambda: (item.setCheckState(Qt.CheckState.Unchecked), True)[1]
              if item is not None else False,
              lambda: item.setCheckState(Qt.CheckState.Checked)
              if item is not None else None)
        yield 800
        # Deselect all, and Select all; each put back to the ticks as built
        ticks0 = _ticks(dlg)
        check("Deselect all",
              lambda: (dlg._deselect_all_btn.click(), True)[1],
              lambda: _put_ticks(dlg, ticks0))
        yield 800
        check("Select all",
              lambda: (dlg._select_all_btn.click(), True)[1],
              lambda: _put_ticks(dlg, ticks0))
        yield 800

        # Edit limits…: one number of the report's own column, then Close
        before = _page(dlg)
        d.later(dlg._limits_btn.click)
        yield 2500
        td = getattr(dlg, "_report_limits_dialog", None)
        edited = None
        if td is not None:
            cell = td._cells.get((RUN_COLUMN, "uniformity_sd"))
            if cell is not None and hasattr(cell, "setValue"):
                edited = (cell.value(), round(cell.value() + 0.3, 2))
                cell.setValue(edited[1])
                d.pump(600)
            d.shot(td, "03-edit-limits-one-number-changed")
            td.accept()
        yield 2500
        after = _page(dlg)
        d.shot(dlg, "04-after-edit-limits-page-unchanged-red-line")
        results.append({"setting": "Edit limits… (one number)",
                        "moved": edited is not None, "edited": edited,
                        "page_unchanged": _same(before, after),
                        "red_line_after_move": after["red_line"],
                        "red_text": after["red_text"]})
        d.note(f"   [Edit limits] edited={edited} "
               f"unchanged={_same(before, after)} red={after['red_line']}")

        # A PDF with a setting moved: the page it prints. The report type is
        # moved as well, so the PDF names one type or the other.
        page_type = dlg._type_combo.currentText()
        if t1:
            K36._choose(dlg._type_combo, t1)
            d.pump(1500)
        moved_type = dlg._type_combo.currentText()
        pdf_moved = _pdf_text(d, dlg, "05-pdf-with-a-setting-moved")
        rec["pdf_with_setting_moved"] = {
            "written": bool(pdf_moved),
            "page_type": page_type, "moved_type": moved_type,
            "pdf_names_page_type": page_type in pdf_moved,
            "pdf_names_moved_type": moved_type in pdf_moved,
            "page_unchanged": _same(after, _page(dlg))}
        (d.out / "05-pdf-with-a-setting-moved.txt").write_text(
            pdf_moved, encoding="utf-8")
        yield 800

        # Generate Report with the setting moved: Cancel keeps everything
        before_cancel = _page(dlg)
        K36.EXPECTED.add("QMessageBox")
        d.later(dlg._generate_btn.click)
        yield 700
        rec["cancel_question"] = d.answer("cancel", None, within_ms=5000)
        yield 2500
        cancelled = _page(dlg)
        rec["after_cancel"] = {"page_unchanged": _same(before_cancel, cancelled),
                               "red_line": cancelled["red_line"]}
        d.note(f"   [Cancel] unchanged={_same(before_cancel, cancelled)} "
               f"red={cancelled['red_line']}")

        # Generate Report with the settings moved: Update
        after = _page(dlg)
        d.later(dlg._generate_btn.click)
        yield 700
        rec["generate_question"] = d.answer("update", "06-generate-question",
                                            within_ms=5000)
        K36.EXPECTED.discard("QMessageBox")
        yield 12000
        gen = _page(dlg)
        rec["after_generate"] = {"page_changed": not _same(after, gen),
                                 "red_line": gen["red_line"],
                                 "shown": gen["shown"]}
        d.shot(dlg, "07-after-generate-report-worked-out-again")
        dlg.close()
        yield 2000

        # ---------------------------------------------------------------
        # SCENE 2: the even sheet (B8-1502)
        # ---------------------------------------------------------------
        _open_report(d, NOTES, "run4")
        yield 4500
        dlg = K36._wait(d, "MeasurementReportDialog")
        if dlg is not None:
            dlg.resize(1420, 980)
            yield 2000
            picked = D_pick(dlg._saved_combo, "2026-11-02")
            yield 3000
            rec["even_sheet_report"] = dlg._saved_combo.currentText()
            rec["even_sheet_picked"] = picked
            sentence = ("no ninth of the page differs from the average "
                        "of all nine")
            rec["even_sheet_sentence_on_page"] = (
                sentence in dlg._view.toPlainText())
            rec["even_sheet_found"] = _scroll_to(
                d, dlg, sentence, "08-even-sheet-no-ninth-differs")
            dlg.close()
            yield 2000

        # ---------------------------------------------------------------
        # SCENE 3: a measurement truly gone (M-REPORT-NOT-WORKED-OUT)
        # ---------------------------------------------------------------
        run6 = d.work / NOTES / "runs" / "run6"
        gone = []
        for p in list((run6 / "old").glob("2026-11-02_*/*.ti3")) + list(
                (run6 / "verifications").glob("2026-11-02_*/*.ti3")):
            gone.append(str(p.relative_to(d.work)))
            p.unlink()
        rec["removed_from_the_copy"] = gone
        _open_report(d, NOTES, "run6")
        yield 4500
        dlg = K36._wait(d, "MeasurementReportDialog")
        if dlg is not None:
            dlg.resize(1420, 980)
            yield 2000
            K45._pick_data(dlg._saved_combo, mrd.NEW_REPORT_KEY)
            yield 2000
            rec["gone_ticks"] = K45._tick(dlg, "all")
            yield 2000
            K36.EXPECTED.add("QMessageBox")
            d.later(dlg._generate_btn.click)
            yield 700
            rec["gone_question"] = d.answer("new", "09-gone-generate-question",
                                            within_ms=4000)
            K36.EXPECTED.discard("QMessageBox")
            yield 12000
            title = "Figures an earlier report saved"
            rec["gone_message_on_page"] = title in dlg._view.toPlainText()
            rec["gone_found"] = _scroll_to(
                d, dlg, title, "10-figures-an-earlier-report-saved")
            dlg.close()
            yield 2000
    return s


def D_pick(combo, text: str) -> bool:
    for i in range(combo.count()):
        if text in combo.itemText(i):
            combo.setCurrentIndex(i)
            combo.activated.emit(i)
            return True
    return False


def main() -> int:
    out = Path(sys.argv[1])
    d = Drive(out, projects=[EVEN, NOTES], language="en", appearance="light")
    rc = d.run(script())
    (out / "record.json").write_text(
        json.dumps(d.record, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8")
    print(f"rc={rc}")
    return rc


if __name__ == "__main__":
    sys.exit(main())
