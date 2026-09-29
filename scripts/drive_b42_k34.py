#!/usr/bin/env python3
"""B42, Knut #182 5817809396 (K34, section A of 5802027116), driven ON SCREEN.

    python scripts/drive_b42_k34.py <out> <en|de> [a6,a8,a9,a10,a11]

Runs on any tree (``CHROMIQ_TREE``), so the same script photographs the tree
before the change and the one after it. It records what the windows SHOW,
read off their own widgets, and photographs each by window id
(`userdrive.Drive.shot`). Settings, presets and the output folder are
sandboxed by `userdrive`, which also FORCES the repository's ISO values file.
The projects are copies of ``CHROMIQ_DEMO_PACK``; the pack itself is never
written.

Scenes:

  a11  Report-Limits-Profile-Gamut, run1, Verification: the Measurement
       Report on "New report…" with every date ticked, Full colour check,
       judged against Custom ISO 12647-7 (a set that limits the row): the row
       "Paper white, difference from the reference paper" for every date, and
       the reference paper the report compared with.
  a10  Report-Limits-Strip-And-Gamut, run4 (a chart with no paper patch):
       the "Paper white" line of the detailed section, the Overview table and
       the Paper white (L*) graph, on "New report…".
  a9   Report-Limits-Report-Folders, run1, Verification: the order of
       "Report shown" (the pulldown, open), each entry with the creation date
       its document records.
  a6   Report-Limits-Report-Folders: run1 is deleted with the profile bar's
       Delete (the real confirmation, answered), then the report across both
       runs is shown and its Report Scope read.
  a8   A Finder duplicate "Report-Limits-Profile-Gamut copy" opened while
       "Report-Limits-Profile-Gamut-copy" already exists: the folder-renamed
       window, Rename (refused: the name is taken), then what comes next.

**NOBODY HAS TO CLICK.** A watchdog answers any window this drive did not
expect (Cancel / Close / No / OK, in English or German) after three seconds,
records its text and photographs it; a deadline ends the run after twenty
minutes whatever happens.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from userdrive import DEMO_PACK, Drive                         # noqa: E402

DEADLINE_S = 1200
OURS = {"MeasurementReportDialog", "ThresholdsDialog", "_InfoDialog"}
#: windows a scene answers itself, by class, while it is expecting them
EXPECTED: "set[str]" = set()
GAMUT = "Report-Limits-Profile-Gamut"
NO_PAPER = "Report-Limits-Strip-And-Gamut"
FOLDERS = "Report-Limits-Report-Folders"


def _install_watchdog(d, rec):
    from PyQt6.QtCore import QTimer
    from PyQt6.QtWidgets import QAbstractButton, QApplication
    started = time.monotonic()
    seen: dict = {}

    def tick():
        if time.monotonic() - started > DEADLINE_S:
            d.note("WATCHDOG: deadline reached, quitting")
            rec["deadline_hit"] = True
            QApplication.instance().quit()
            return
        m = QApplication.activeModalWidget()
        if (m is None or not m.isVisible() or type(m).__name__ in OURS
                or type(m).__name__ in EXPECTED):
            seen.clear()
            return
        first = seen.setdefault(id(m), time.monotonic())
        if time.monotonic() - first < 3:
            return
        seen.pop(id(m), None)
        said = d.modal_text(m)
        n = len(rec.setdefault("watchdog", [])) + 1
        try:
            from onscreen_capture import capture_window
            capture_window(m, d.shots / f"watchdog-{n:02d}.png")
        except Exception:                                  # noqa: BLE001
            pass
        clicked = None
        for word in ("Cancel", "Abbrechen", "Close", "Schließen", "No",
                     "Nein", "OK"):
            for b in m.findChildren(QAbstractButton):
                if b.isVisible() and b.text().replace("&", "") == word:
                    clicked = word
                    b.click()
                    break
            if clicked:
                break
        if clicked is None:
            m.close()
            clicked = "(closed)"
        rec["watchdog"].append({"class": type(m).__name__, "text": said,
                                "clicked": clicked})
        d.note(f"   [watchdog] {type(m).__name__}: "
               f"{said[:160].replace(chr(10), ' / ')!r} -> {clicked}")

    dog = QTimer()
    dog.timeout.connect(tick)
    dog.start(500)
    d._k34_dog = dog


def _wait(d, cls, tries=60):
    for _ in range(tries):
        w = d.top_dialog(cls)
        if w is not None:
            return w
        d.pump(250)
    return None


def _view_text(dlg) -> str:
    from PyQt6.QtWidgets import QTextBrowser, QTextEdit
    for v in dlg.findChildren((QTextBrowser, QTextEdit)):
        if v.isVisible() and len(v.toPlainText()) > 200:
            return v.toPlainText()
    return ""


def _scroll_to(dlg, text: str) -> bool:
    """Scroll the report view so *text* is on screen, as a reader scrolls."""
    from PyQt6.QtGui import QTextCursor
    from PyQt6.QtWidgets import QTextBrowser, QTextEdit
    for v in dlg.findChildren((QTextBrowser, QTextEdit)):
        if not v.isVisible() or len(v.toPlainText()) < 200:
            continue
        v.moveCursor(QTextCursor.MoveOperation.Start)
        if v.find(text):
            v.ensureCursorVisible()
            sb = v.verticalScrollBar()
            sb.setValue(min(sb.maximum(), sb.value() + v.height() // 3))
            return True
    return False


def _new_report_everything(d, dlg):
    """"New report…", every measurement ticked: the report as it is worked
    out NOW, not a saved one."""
    dlg._saved_combo.setCurrentIndex(0)
    d.pump(1200)
    dlg._select_all_btn.click()
    d.pump(1500)
    if hasattr(dlg, "_detail_check") and not dlg._detail_check.isChecked():
        dlg._detail_check.setChecked(True)
        d.pump(1200)


def _pick_data(combo, data) -> bool:
    i = combo.findData(data)
    if i < 0:
        return False
    combo.setCurrentIndex(i)
    return True


def _combo_rows(combo) -> list:
    return [{"text": combo.itemText(i), "data": combo.itemData(i)}
            for i in range(combo.count())]


def script_for(language: str, scenes: "list[str]"):
    def script(d):
        rec = d.record
        rec.update({"language": language, "scenes": scenes,
                    "mode": "ON SCREEN", "pack": str(DEMO_PACK)})
        tag = language
        from core.i18n import tr
        from workflow import compliance_sets as cs
        rec["iso_file_in_use"] = cs.iso_data_path_text()
        d.note(f"ISO file in use: {cs.iso_data_path_text()}")
        _install_watchdog(d, rec)

        # ---------------------------------------------------------- A11
        if "a11" in scenes:
            d.open_project(GAMUT)
            d.set_bar(run="run1", run_type="Verification")
            yield 1000
            d.launch_tool("measurement_report")
            yield 4000
            dlg = _wait(d, "MeasurementReportDialog")
            if dlg is not None:
                _new_report_everything(d, dlg)
                _pick_data(dlg._type_combo, "t2_full_colour_check")
                yield 1200
                _pick_data(dlg._set_combo, "custom_iso_12647_7")
                yield 2500
                rows = []
                for r in dlg._runs_for_document():
                    vr, _rec = dlg._verdict_rows(r)
                    row = next((x for x in vr if (x.get("row_id") or
                                x.get("key")) == "substrate_de00_max"), {})
                    w = {c.get("name"): c for c in r.get("corners") or []
                         }.get("W", {})
                    rows.append({
                        "date": str(r.get("created")),
                        "value": row.get("value"),
                        "word": row.get("word"),
                        "limit": row.get("threshold"),
                        "paper_measured": w.get("lab"),
                        "compared_with": w.get("expected_lab"),
                        "paper_reference": (r.get("colorimetric") or {}).get(
                            "paper_reference_lab"),
                        "from": (r.get("colorimetric") or {}).get(
                            "paper_reference_from")})
                rec["a11_rows"] = rows
                for x in rows:
                    d.note(f"   A11 {x['date']}: {x['value']} {x['word']} "
                           f"(limit {x['limit']}); paper {x['paper_measured']}"
                           f" against {x['compared_with']}")
                label = tr(cs.ROW_BY_ID["substrate_de00_max"].label)
                _scroll_to(dlg, label)
                yield 1200
                d.shot(dlg, f"{tag}-a11-01-paper-row")
                _scroll_to(dlg, tr("Cube corners (ΔE00)"))
                yield 1200
                d.shot(dlg, f"{tag}-a11-02-cube-corners")
                dlg.close()
                yield 1500

        # ---------------------------------------------------------- A10
        if "a10" in scenes:
            d.open_project(NO_PAPER)
            d.set_bar(run="run4", run_type="Verification")
            yield 1000
            d.launch_tool("measurement_report")
            yield 4000
            dlg = _wait(d, "MeasurementReportDialog")
            if dlg is not None:
                _new_report_everything(d, dlg)
                _pick_data(dlg._type_combo, "t2_full_colour_check")
                yield 2500
                runs = dlg._runs_for_document()
                rec["a10_runs"] = [{
                    "date": str(r.get("created")),
                    "paper_patch": r.get("paper_patch"),
                    "paper_white": r.get("paper_white"),
                    "yardstick": r.get("yardstick"),
                    "yardstick_no_paper": r.get("yardstick_no_paper")}
                    for r in runs]
                text = _view_text(dlg)
                i = text.find(tr("Paper white and darkest black (L*)"))
                rec["a10_detail_text"] = text[i:i + 500] if i >= 0 else None
                j = text.find(tr("Notes on the verdicts above:"))
                rec["a10_notes_text"] = text[j:j + 1500] if j >= 0 else None
                k = text.find(tr("Paper white L*"))
                rec["a10_overview_text"] = text[k:k + 200] if k >= 0 else None
                d.note("   A10 runs: " + json.dumps(rec["a10_runs"],
                                                     ensure_ascii=False))
                d.note(f"   A10 detail: {rec['a10_detail_text']!r}"[:400])
                _scroll_to(dlg, tr("Paper white and darkest black (L*)"))
                yield 1200
                d.shot(dlg, f"{tag}-a10-01-paper-white-line")
                _scroll_to(dlg, tr("Notes on the verdicts above:"))
                yield 1200
                d.shot(dlg, f"{tag}-a10-02-notes")
                _scroll_to(dlg, tr("Paper white L*"))
                yield 1200
                d.shot(dlg, f"{tag}-a10-03-overview")
                tabs = getattr(dlg, "_trend_tabs", None)
                white = getattr(dlg, "_trend_white", None)
                if tabs is not None and white is not None:
                    tabs.setCurrentWidget(white)
                    yield 1200
                    d.shot(dlg, f"{tag}-a10-04-paper-white-graph")
                dlg.close()
                yield 1500

        # ---------------------------------------------------------- A9
        if "a9" in scenes:
            # A RESTORED FILE, the way a copy or a backup restore leaves it:
            # the 2026-12-08 report's file is given today's time. Its content
            # (and its own creation date) is untouched. In the copied pack
            # the file times already happen to agree with the dates, so
            # without this the fault B8-843 names does not show.
            now = time.time()
            touched = []
            for f in sorted((d.work / FOLDERS).rglob(
                    "report_2026-12-08_*.json")):
                if "old" in f.parts:
                    continue
                os.utime(f, (now, now))
                touched.append(str(f.relative_to(d.work)))
            rec["a9_touched"] = touched
            d.note(f"   A9 touched (restored today): {touched}")
            d.open_project(FOLDERS)
            d.set_bar(run="run1", run_type="Verification")
            yield 1000
            d.launch_tool("measurement_report")
            yield 4000
            dlg = _wait(d, "MeasurementReportDialog")
            if dlg is not None:
                rows = []
                docs = {e["key"]: e for e in dlg._saved_documents(
                    dlg._run_ctx.run if dlg._run_ctx else None)}
                for row in _combo_rows(dlg._saved_combo):
                    e = docs.get(row["data"]) or {}
                    doc = e.get("doc") or {}
                    rows.append({"text": row["text"], "key": row["data"],
                                 "document_created": doc.get("created")})
                rec["a9_report_shown"] = rows
                for x in rows:
                    d.note(f"   A9 {x['text']!r} created "
                           f"{x['document_created']}")
                for attempt in range(3):
                    dlg._saved_combo.showPopup()
                    yield 1500 + 1000 * attempt
                    ok = d.shot(dlg._saved_combo.view(),
                                f"{tag}-a9-01-report-shown-open")
                    dlg._saved_combo.hidePopup()
                    yield 600
                    if ok:
                        break
                dlg.close()
                yield 1500

        # ---------------------------------------------------------- A6
        if "a6" in scenes:
            d.open_project(FOLDERS)
            d.set_bar(run="run1", run_type="Profiling")
            yield 1200
            import core.run_delete as rd
            plan = d.ctl.delete_plan()
            label = rd.confirm_label(plan) if not isinstance(plan, str) \
                else None
            rec["a6_plan"] = {"kind": getattr(plan, "kind", plan),
                              "confirm": label}
            EXPECTED.add("QMessageBox")
            d.later(d.bar._delete_btn.click)
            yield 800
            said = d.answer(label or "Delete", f"{tag}-a6-01-delete-run1")
            EXPECTED.discard("QMessageBox")
            rec["a6_delete_asked"] = said
            yield 2500
            d.set_bar(run="run1", run_type="Verification")
            yield 1200
            d.launch_tool("measurement_report")
            yield 4000
            dlg = _wait(d, "MeasurementReportDialog")
            if dlg is not None:
                combo = dlg._saved_combo
                rows = _combo_rows(combo)
                rec["a6_report_shown"] = rows
                pick = None
                for i, row in enumerate(rows):
                    key = str(row["data"] or "")
                    if not key.startswith("id:"):
                        continue
                    docs = {e["key"]: e for e in dlg._saved_documents(
                        dlg._run_ctx.run if dlg._run_ctx else None)}
                    doc = (docs.get(key) or {}).get("doc") or {}
                    dirs = [m.get("dir", "") for m in
                            doc.get("measurements") or []]
                    if any(".deleted" in x for x in dirs):
                        pick = i
                        rec["a6_document_dirs"] = dirs
                        break
                rec["a6_picked"] = rows[pick]["text"] if pick is not None \
                    else None
                if pick is not None:
                    combo.setCurrentIndex(pick)
                    yield 3000
                text = _view_text(dlg)
                i = text.find(tr("Report Scope"))
                rec["a6_scope_text"] = text[i:i + 1400] if i >= 0 else None
                d.note(f"   A6 scope: {rec['a6_scope_text']!r}"[:600])
                from workflow import measurement_messages as M
                line = (M.M_REPORT_SCOPE_RUN_DELETED.render(count=1, runs="")[0]
                        if hasattr(M, "M_REPORT_SCOPE_RUN_DELETED") else "")
                if not (line and _scroll_to(dlg, line)):
                    _scroll_to(dlg, tr("Date range:"))
                yield 1200
                d.shot(dlg, f"{tag}-a6-02-report-scope")
                dlg.close()
                yield 1500

        # ---------------------------------------------------------- A8
        if "a8" in scenes:
            from workflow import measurement_messages as M
            dup = d.work / f"{GAMUT} copy"
            taken = d.work / f"{GAMUT}-copy"
            shutil.copytree(d.work / GAMUT, dup)
            shutil.copytree(d.work / GAMUT, taken)
            texts = M.folder_renamed_texts(folder=dup.name, name=GAMUT,
                                           new=taken.name, built=True)
            rec["a8_buttons"] = texts
            EXPECTED.update({"TargetChangeDialog", "InfoDialog",
                             "_InfoDialog", "NamePromptDialog", "QDialog",
                             "QInputDialog"})
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(0, lambda: d.win._tab_chart
                              .open_project_manifest(dup / "project.json"))
            yield 1500
            steps = []
            said = d.answer(texts["rename"], f"{tag}-a8-01-folder-renamed")
            steps.append(("rename", said))
            yield 800
            # the failure message: `InfoDialog`, one standard Close button
            close = "Schließen" if language == "de" else "Close"
            said = d.answer(close, f"{tag}-a8-02-rename-failed")
            steps.append(("failed-ok", said))
            yield 800
            # AFTER THE FAILURE: do the three choices come back?
            said = d.answer(texts["other"], f"{tag}-a8-03-choices-again",
                            within_ms=5000)
            steps.append(("choices-again", said))
            yield 800
            if said is not None:
                # the project-name window: type a free name and accept
                from PyQt6.QtWidgets import (QAbstractButton, QApplication,
                                             QLineEdit)
                m = None
                for _ in range(40):
                    d.pump(100)
                    m = QApplication.activeModalWidget()
                    if m is not None and m.findChild(QLineEdit) is not None:
                        break
                else:
                    m = None
                if m is not None:
                    box = m.findChild(QLineEdit)
                    box.setText(f"{GAMUT} renamed")
                    d.pump(400)
                    d.shot(m, f"{tag}-a8-04-another-name")
                    rec["a8_name_window"] = d.modal_text(m)
                    ok = next((b for b in m.findChildren(QAbstractButton)
                               if b.isVisible() and b.isEnabled()
                               and b.text().replace("&", "") in (
                                   "OK", "Continue", "Weiter", "Rename",
                                   "Umbenennen")), None)
                    if ok is None:
                        ok = next((b for b in m.findChildren(QAbstractButton)
                                   if b.isVisible() and b.isEnabled()
                                   and b.isDefault()), None)
                    rec["a8_name_button"] = ok.text() if ok else None
                    if ok is not None:
                        ok.click()
                        d._modal_closed()
                yield 2500
            EXPECTED.clear()
            rec["a8_steps"] = steps
            rec["a8_after"] = {
                "dup_exists": dup.exists(),
                "renamed_exists": (d.work / f"{GAMUT}-renamed").exists(),
                "taken_intact": (taken / "project.json").is_file(),
                "target_name": d.win._tab_chart._file_mgr.get_target_name()
                if d.win._tab_chart._file_mgr.is_named() else None}
            d.note("   A8 after: " + json.dumps(rec["a8_after"]))
            d.shot(d.win, f"{tag}-a8-05-main-window-after")
            yield 800
    return script


def main() -> int:
    out = Path(sys.argv[1])
    language = sys.argv[2] if len(sys.argv) > 2 else "en"
    scenes = (sys.argv[3] if len(sys.argv) > 3
              else "a11,a10,a9,a6,a8").split(",")
    projects = sorted({GAMUT, NO_PAPER, FOLDERS,
                       "Report-Limits-Report-Folders-Second"})
    projects = [p for p in projects if (DEMO_PACK / p).is_dir()]
    d = Drive(out, projects=projects, language=language)
    rc = d.run(script_for(language, scenes))
    print(f"rc={rc}")
    return rc


if __name__ == "__main__":
    sys.exit(main())
