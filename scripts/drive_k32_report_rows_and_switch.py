#!/usr/bin/env python3
"""#182 K32 (Knut on beta 41, 5813851807), driven ON SCREEN.

    CHROMIQ_DEMO_PACK=<pack> python scripts/drive_k32_report_rows_and_switch.py \\
        <out> <en|de> [scene ...]

The pack is the release demo package built from this tree
(`make_release_demo_package.py`).

scenes:
    knut      his case, step by step: Report-Limits-Evenness, run type
              Profiling, Measurement Report; Add Profile's Measurements with a
              .ti3 of Report-Limits-Profile-Gamut, then Remove it again; an
              existing report as basis, Select all, Custom ISO 12647-7,
              Generate. The "Settings were modified" window is photographed,
              its buttons' PAINTED order, its default button and its numbered
              list are read, and it is answered with the Return key, the way
              Knut would take its default. Then the rows and graph tabs of the
              report that came out, and its PDF.
    new       "New report…", Select all, Custom ISO 12647-7, Generate, on
              Report-Limits-Every-Limit-Set (the project his text names).
    switchraw the same, with no profiler attached (what a user feels).
    switch    the bar's Run type from Profiling to Verification on
              Report-Limits-Evenness, timed: the synchronous handler under
              cProfile, and the longest stall of the event loop after it.
    iso       items 4 to 6: Report-Limits-Evenness run1 as Verification,
              every date, Custom ISO 12647-7; at the default and a narrow
              width: the Overview's dates per table, the tab bar at each
              position, every graph's limit words; and the PDF.
    empty     item 7: Report-Limits-Evenness as Verification, run 3
              (no dated verification) and run 4 (three), from Tools and from
              the Measure tab: what the list holds.
    add       item 8: Report-Limits-Profile-Gamut run 1 as Verification;
              run 2's measurements added (unticked, page unchanged, red line
              once one is ticked), and the sentence beside "Report shown" at
              three widths.
    verify    his second half: run type Verification, the pre-selected
              report, Custom ISO 12647-7, Select all, Generate, Create New.

**A WATCHDOG ANSWERS WHAT THE SCRIPT DID NOT EXPECT.** Every 500 ms it looks
for a modal window that is not the report window and not one the script is
answering; one left up for 12 s is photographed, recorded, and closed with
its Cancel / Close / OK button (in English or German), or Escape. A hard
deadline quits the app. Basti never has to click.
"""
from __future__ import annotations

import cProfile
import io
import json
import pstats
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

EVEN = "Report-Limits-Evenness"
EVERY = "Report-Limits-Every-Limit-Set"
GAMUT = "Report-Limits-Profile-Gamut"
ALL = ("knut", "new", "switch", "verify", "iso", "empty", "add")
SET = "custom_iso_12647_7"
DEADLINE_S = 900


def _flat(s: str) -> str:
    return " ".join(str(s).split())


def script_for(scenes, language):
    def script(d):
        from PyQt6.QtCore import Qt, QTimer
        from PyQt6.QtWidgets import QApplication, QMessageBox
        from core.i18n import tr as L
        from workflow.compliance_sets import ROWS
        rec = d.record
        rec["language"] = language
        rec["checks"] = {}
        rec["scenes"] = {}
        tag = language
        started = time.monotonic()
        expecting = {"on": False}

        # ---- the watchdog --------------------------------------------------
        seen_since: dict = {}

        def watchdog():
            if time.monotonic() - started > DEADLINE_S:
                d.note("WATCHDOG: deadline reached, quitting")
                QApplication.instance().quit()
                return
            m = QApplication.activeModalWidget()
            if (m is None or not m.isVisible() or expecting["on"]
                    or type(m).__name__ == "MeasurementReportDialog"):
                seen_since.clear()
                return
            first = seen_since.setdefault(id(m), time.monotonic())
            if time.monotonic() - first < 12:
                return
            seen_since.pop(id(m), None)
            from PyQt6.QtWidgets import QAbstractButton
            said = d.modal_text(m)
            d.note(f"WATCHDOG: unexpected {type(m).__name__}: "
                   f"{said[:200]!r}")
            rec.setdefault("watchdog", []).append(
                {"class": type(m).__name__, "text": said})
            for word in ("Cancel", "Abbrechen", "Close", "Schließen", "OK"):
                for b in m.findChildren(QAbstractButton):
                    if b.isVisible() and b.text().replace("&", "") == word:
                        b.click()
                        return
            m.close()

        dog = QTimer()
        dog.timeout.connect(watchdog)
        dog.start(500)
        rec["_dog"] = str(dog)                 # keep a reference

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

        def open_window(project, run_type, run=None):
            d.open_project(project)
            d.set_bar(run_type=run_type, run=run)
            d.pump(900)
            d.launch_tool("measurement_report")

        def select_all(dlg):
            dlg._select_all_btn.click()
            d.pump(1500)

        def choose_set(dlg, set_id):
            i = dlg._set_combo.findData(set_id)
            if i < 0:
                return False
            dlg._set_combo.setCurrentIndex(i)
            dlg._set_combo.activated.emit(i)
            d.pump(1500)
            return True

        def pick_saved(dlg):
            """The first saved report in "Report shown", as a basis."""
            c = dlg._saved_combo
            for i in range(c.count()):
                key = str(c.itemData(i) or "")
                if key.startswith(("id:", "file:")):
                    c.setCurrentIndex(i)
                    c.activated.emit(i)
                    d.pump(2000)
                    return c.itemText(i)
            return None

        def rows_on_page(dlg):
            text = _flat(dlg._view.toPlainText())
            # THE RESULTS TABLE ONLY: from its heading to the next section.
            head = _flat(L("Report Results"))
            i = text.find(head)
            part = text[i:] if i >= 0 else text
            for stop in (L("Trend over time (this printer)"),
                         L("Overview of Measurement Metrics")):
                j = part.find(_flat(stop))
                if j > 0:
                    part = part[:j]
                    break
            return [r.id for r in ROWS if _flat(L(r.label)) in part], text

        def tabs_of(dlg):
            t = dlg._trend_tabs
            return [t.tabText(i) for i in range(t.count())
                    if t.isTabVisible(i)]

        def shoot_at(dlg, text, name):
            view = dlg._view
            c = view.document().find(text)
            if c.isNull():
                d.note(f"   (not on the page: {text!r})")
                return False
            from PyQt6.QtGui import QTextCursor
            plain = QTextCursor(c)
            plain.setPosition(c.selectionStart())
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
            expecting["on"] = True
            d.later(dlg._pdf_btn.click)
            yield 1500
            d.answer_file(target, name=None)
            expecting["on"] = False
            for _ in range(120):
                yield 1000
                if target.exists():
                    break
            yield 2500
            text = []
            if target.exists():
                pages_dir = d.out / "pdf-pages"
                pages_dir.mkdir(exist_ok=True)
                render_pdf(target, pages_dir)
                text = pdf_pages_text(target)
                (pages_dir / f"{name}.txt").write_text(
                    "\n\f\n".join(text), encoding="utf-8")
            d.note(f"   PDF {target.name}: "
                   f"{'written' if target.exists() else 'NOT WRITTEN'}")
            return text

        def read_popup(scene, name):
            """The question window: photograph it and read it, then press
            Return, which is what its default button answers."""
            from PyQt6.QtTest import QTest
            m = None
            for _ in range(60):
                d.pump(100)
                m = QApplication.activeModalWidget()
                if isinstance(m, QMessageBox):
                    break
                m = None
            if m is None:
                check(scene, "the question window came up", False)
                return None
            d.pump(700)
            d.shot(m, name)
            btns = sorted([b for b in m.buttons() if b.isVisible()],
                          key=lambda b: b.mapToGlobal(b.rect().topLeft()).x())
            painted = [b.text().replace("&", "") for b in btns]
            default = m.defaultButton()
            info = {"title": m.text(), "body": m.informativeText(),
                    "painted_left_to_right": painted,
                    "default": default.text().replace("&", "")
                    if default else None,
                    "x": [b.mapToGlobal(b.rect().topLeft()).x() for b in btns]}
            rec["scenes"].setdefault(scene, {})["popup"] = info
            want = [L("Create New"), L("Update"), L("Cancel")]
            check(scene, "buttons from the left: Create New, Update, Cancel",
                  painted == want, repr(painted))
            check(scene, "Create New is the default button",
                  info["default"] == L("Create New"), repr(info["default"]))
            lines = [ln for ln in info["body"].splitlines()
                     if ln[:2] in ("1.", "2.", "3.")]
            check(scene, "the numbered list: Create New first, Update second",
                  len(lines) == 3 and ("Neuen Bericht" in lines[0]
                                       or "Create new" in lines[0])
                  and ("Ausgewählten Bericht" in lines[1]
                       or "Update selected" in lines[1]), repr(lines))
            QTest.keyClick(m, Qt.Key.Key_Return)
            d._modal_closed()
            return info

        def report_state(scene, dlg, name):
            rows, text = rows_on_page(dlg)
            tabs = tabs_of(dlg)
            judged = dlg._report_limits()
            st = rec["scenes"].setdefault(scene, {})
            st.update({"rows_in_results": rows, "graph_tabs": tabs,
                       "report_limits": judged.set_id,
                       "loaded_doc": dlg._loaded_doc_id,
                       "patch_counts_note": _flat(L(
                           "These measurements do not all hold the same "
                           "number of readings")) in text})
            d.note(f"   set {judged.set_id}; {len(rows)} rows: {rows}")
            d.note(f"   graph tabs: {tabs}")
            dlg._view.verticalScrollBar().setValue(0)
            d.pump(400)
            d.shot(dlg, f"{name}-01-top")
            shoot_at(dlg, L("Report Results"), f"{name}-02-results")
            shoot_at(dlg, L("Notes on the values above:"), f"{name}-03-notes")
            t = dlg._trend_tabs
            for i in range(t.count()):
                if t.isTabVisible(i):
                    t.setCurrentIndex(i)
                    d.pump(500)
            shoot_at(dlg, L("Trend over time (this printer)"),
                     f"{name}-04-graphs")
            return rows, tabs, text

        # ------------------------------------------------------------------
        if "knut" in scenes:
            sc = "knut"
            d.note(f"[{sc}] {EVEN}, Profiling, his steps")
            open_window(EVEN, "Profiling")
            yield 4000
            dlg = wait_dialog()
            d.shot(dlg, f"{tag}-knut-00-open")
            # Add Profile's Measurements: a .ti3 of another demo project
            gamut_ti3 = (d.work / GAMUT / "runs" / "run1" / f"{GAMUT}.ti3")
            expecting["on"] = True
            d.later(dlg._add_btn.click)
            yield 1500
            d.answer_file(gamut_ti3, name=f"{tag}-knut-01-add-file")
            expecting["on"] = False
            yield 4000
            d.shot(dlg, f"{tag}-knut-02-added")
            # ...and removed again: select its list entry, Remove
            lst = dlg._profile_list
            hit = None
            for i in range(lst.count()):
                if GAMUT in lst.item(i).text():
                    hit = i
                    break
            check(sc, "the added project is in the list", hit is not None)
            if hit is not None:
                lst.setCurrentRow(hit)
                d.pump(400)
                dlg._remove_btn.click()
                yield 3000
            d.shot(dlg, f"{tag}-knut-03-removed")
            base = pick_saved(dlg)
            d.note(f"   basis: {base!r}")
            select_all(dlg)
            check(sc, "Custom ISO 12647-7 chosen", choose_set(dlg, SET))
            yield 1500
            d.shot(dlg, f"{tag}-knut-04-before-generate")
            expecting["on"] = True
            d.later(dlg._generate_btn.click)
            yield 600
            read_popup(sc, f"{tag}-knut-05-question")
            expecting["on"] = False
            yield 5000
            rows, tabs, _t = report_state(sc, dlg, f"{tag}-knut-06")
            check(sc, "the report judges against Custom ISO 12647-7",
                  rec["scenes"][sc]["report_limits"] == SET)
            for rid in ("solids_de00_max", "control_strip_de00_avg",
                        "substrate_de00_max", "surface_gamut_de00_avg",
                        "uniformity_sd"):
                check(sc, f"row {rid} is in the results", rid in rows)
            pdf = yield from save_pdf(dlg, f"{tag}-knut")
            rec["scenes"][sc]["pdf_judged_against"] = [
                ln for ln in "\n".join(pdf).splitlines()
                if L("Judged against") in ln][:3]
            dlg.close()
            yield 1500

        # ------------------------------------------------------------------
        if "new" in scenes:
            sc = "new"
            d.note(f"[{sc}] {EVERY}, Profiling, New report…")
            open_window(EVERY, "Profiling")
            yield 4000
            dlg = wait_dialog()
            dlg._saved_combo.setCurrentIndex(0)
            dlg._saved_combo.activated.emit(0)
            d.pump(1500)
            select_all(dlg)
            check(sc, "Custom ISO 12647-7 chosen", choose_set(dlg, SET))
            d.later(dlg._generate_btn.click)
            yield 6000
            rows, tabs, _t = report_state(sc, dlg, f"{tag}-new")
            check(sc, "the report judges against Custom ISO 12647-7",
                  rec["scenes"][sc]["report_limits"] == SET)
            yield from save_pdf(dlg, f"{tag}-new")
            dlg.close()
            yield 1500

        # ------------------------------------------------------------------
        if "switch" in scenes or "switchraw" in scenes:
            # "switchraw" times the same presses with no profiler attached,
            # which is what a user feels; "switch" names where the time goes.
            raw = "switchraw" in scenes
            sc = "switch"
            d.note(f"[{sc}] {EVEN}: Run type Profiling -> Verification, timed")
            d.open_project(EVEN)
            d.set_bar(run_type="Profiling")
            yield 2500
            from core import measurement_target as MT
            b = d.bar
            timings = []
            for rnd, (frm, to) in enumerate(
                    [(MT.RUN_TYPE_PROFILING, MT.RUN_TYPE_VERIFICATION),
                     (MT.RUN_TYPE_VERIFICATION, MT.RUN_TYPE_PROFILING),
                     (MT.RUN_TYPE_PROFILING, MT.RUN_TYPE_VERIFICATION)]):
                idx = b._type_combo.findData(to)
                gaps = []
                last = [time.monotonic()]

                def tick():
                    now = time.monotonic()
                    gaps.append(now - last[0])
                    last[0] = now
                beat = QTimer()
                beat.timeout.connect(tick)
                prof = cProfile.Profile()
                t0 = time.monotonic()
                beat.start(20)
                if not raw:
                    prof.enable()
                b._type_combo.setCurrentIndex(idx)
                b._type_combo.activated.emit(idx)
                if not raw:
                    prof.disable()
                sync = time.monotonic() - t0
                last[0] = time.monotonic()
                # THE WORK QUEUED BY THE SWITCH, profiled on its own: the
                # handler returns and the event loop then runs whatever it
                # scheduled, which is where a stall shows.
                prof_after = cProfile.Profile()
                if not raw:
                    prof_after.enable()
                d.pump(6000)
                if not raw:
                    prof_after.disable()
                beat.stop()
                for pr, suffix, n in ((prof_after, "-after", 60),
                                      (prof, "", 45)):
                    if raw:
                        break
                    s2 = io.StringIO()
                    pstats.Stats(pr, stream=s2).sort_stats(
                        "cumulative").print_stats(n)
                    (d.out / f"switch-profile-{rnd}{suffix}.txt").write_text(
                        s2.getvalue(), encoding="utf-8")
                timings.append({"from": frm, "to": to,
                                "handler_s": round(sync, 3),
                                "longest_stall_after_s":
                                    round(max(gaps or [0]), 3)})
                d.note(f"   {frm} -> {to}: handler {sync:.2f} s, longest "
                       f"stall after it {max(gaps or [0]):.2f} s")
                d.shot(d.win, f"{tag}-switch-{rnd}")
            rec["scenes"][sc] = {"timings": timings}

        # ------------------------------------------------------------------
        if "verify" in scenes:
            sc = "verify"
            d.note(f"[{sc}] {EVEN}, Verification, the pre-selected report")
            open_window(EVEN, "Verification")
            yield 4000
            dlg = wait_dialog()
            d.shot(dlg, f"{tag}-verify-00-open")
            check(sc, "Custom ISO 12647-7 chosen", choose_set(dlg, SET))
            select_all(dlg)
            expecting["on"] = True
            d.later(dlg._generate_btn.click)
            yield 600
            read_popup(sc, f"{tag}-verify-01-question")
            expecting["on"] = False
            yield 5000
            report_state(sc, dlg, f"{tag}-verify-02")
            check(sc, "the report judges against Custom ISO 12647-7",
                  rec["scenes"][sc]["report_limits"] == SET)
            dlg.close()
            yield 1500

        # ------------------------------------------------------------------
        if "iso" in scenes:
            # Items 4 to 6 (Knut, 5814107188 and 5814390886): a report of
            # every date of Report-Limits-Evenness run1, judged against Custom
            # ISO 12647-7, at the window's default width and a narrow one.
            sc = "iso"
            d.note(f"[{sc}] {EVEN} run1, Verification, New report, Custom ISO")
            open_window(EVEN, "Verification", run="run1")
            yield 4000
            dlg = wait_dialog()
            dlg._saved_combo.setCurrentIndex(0)
            dlg._saved_combo.activated.emit(0)
            d.pump(1500)
            select_all(dlg)
            choose_set(dlg, SET)
            d.later(dlg._generate_btn.click)
            yield 6000
            sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
            from tests.test_k32_limit_words import _check as _check_words
            from PyQt6.QtGui import QTextTable
            st = rec["scenes"].setdefault(sc, {})
            default_w = dlg.width()

            def tables(frame):
                for f in frame.childFrames():
                    if isinstance(f, QTextTable):
                        yield f
                    yield from tables(f)

            for wname, width in (("default", default_w), ("narrow", 820)):
                dlg.resize(width, dlg.height())
                yield 1500
                # the page is laid out for the width it is DRAWN at; a user
                # reaches that by showing the report again
                dlg._render()
                yield 1500
                tag2 = f"{tag}-{wname}"
                # ---- 4. the Overview's columns --------------------------
                doc = dlg._view.document()
                head = doc.find(L("Overview of Measurement Metrics"))
                cols = [t.columns() - 1 for t in tables(doc.rootFrame())
                        if not head.isNull()
                        and t.firstPosition() > head.position()]
                vpw = dlg._view.viewport().width()
                ndates = len(dlg._runs_for_document())
                st[f"overview_{wname}"] = {
                    "viewport_px": vpw,
                    "table_width_px": getattr(dlg, "_table_width", None),
                    "dates_per_table": cols[:6], "dates": ndates}
                d.note(f"   overview {wname}: viewport {vpw} px, "
                       f"dates per table {cols[:6]}")
                check(sc, f"Overview shows at least 4 dates a table ({wname})",
                      bool(cols) and cols[0] >= min(4, ndates),
                      repr(cols[:6]))
                shoot_at(dlg, L("Overview of Measurement Metrics"),
                         f"{tag2}-04-overview")
                # ---- 6. the tab bar ------------------------------------
                bar = dlg._trend_tabs.tabBar()
                states = []
                if hasattr(bar, "peek_state"):
                    for _ in range(12):
                        if not bar.peek_state()["arrows"][0]:
                            break
                        bar.scroll_left()
                    d.pump(400)
                    k = 0
                    while True:
                        ps = bar.peek_state()
                        states.append({
                            "arrows": ps["arrows"], "first": ps["first"],
                            "last": ps["last"],
                            "shown": {dlg._trend_tabs.tabText(i):
                                      round(v, 3) for i, v in
                                      ps["shown"].items() if v}})
                        d.shot(dlg, f"{tag2}-06-tabs-{k:02d}")
                        if not ps["arrows"][1] or k > 10:
                            break
                        bar._right_btn.click()
                        d.pump(500)
                        k += 1
                else:
                    d.shot(dlg, f"{tag2}-06-tabs-00")
                st[f"tabs_{wname}"] = states
                d.note(f"   tabs {wname}: "
                       + "; ".join(str(x["arrows"]) for x in states))
                # ---- 5. every graph's limit words ----------------------
                t = dlg._trend_tabs
                words = {}
                for i in range(t.count()):
                    if not t.isTabVisible(i):
                        continue
                    t.setCurrentIndex(i)
                    d.pump(700)
                    chart = t.widget(i)
                    boxes = getattr(chart, "_word_boxes", None)
                    if boxes is None:
                        d.shot(dlg, f"{tag2}-05-graph-{i:02d}")
                        continue
                    try:
                        _check_words(chart, t.tabText(i))
                        ok, why = True, ""
                    except AssertionError as exc:
                        ok, why = False, str(exc)[:300]
                    words[t.tabText(i)] = {
                        "placed": [w for _r, w, _y in boxes], "ok": ok,
                        "why": why}
                    check(sc, f"limit words of {t.tabText(i)!r} ({wname})",
                          ok, why or repr([w for _r, w, _y in boxes]))
                    d.shot(dlg, f"{tag2}-05-graph-{i:02d}")
                st[f"words_{wname}"] = words
            dlg.resize(default_w, dlg.height())
            yield 800
            dlg._render()
            yield 1200
            yield from save_pdf(dlg, f"{tag}-iso")
            dlg.close()
            yield 1500

        # ------------------------------------------------------------------
        if "empty" in scenes:
            # Item 7 (Knut, 5814558912): Report-Limits-Every-Limit-Set, Run
            # type Verification; run 4 has three dated verifications, run 3
            # has none. Opened from Tools > Measurement report and from the
            # Measure tab's button.
            sc = "empty"
            st = rec["scenes"].setdefault(sc, {})
            # Knut names Every-Limit-Set; the project with his shape (eight
            # runs, run 4 with three dates, run 3 with none) is Evenness.
            d.open_project(EVEN)
            for run in ("run3", "run4"):
                for door in ("tools", "measure"):
                    d.set_bar(run_type="Verification", run=run)
                    yield 1500
                    if door == "tools":
                        d.launch_tool("measurement_report")
                    else:
                        d.goto_tab("measure")
                        expecting["on"] = True
                        d.later(d.win._tab_measure._open_measurement_report)
                    yield 4000
                    expecting["on"] = False
                    dlg = wait_dialog()
                    if dlg is None:
                        # the Measure tab may answer with a message instead
                        said = d.answer("OK", name=f"{tag}-07-{run}-{door}-msg",
                                        within_ms=3000)
                        st[f"{run}_{door}"] = {"window": False, "said": said}
                        continue
                    lst = dlg._profile_list
                    rows = [lst.item(i).text() for i in range(lst.count())]
                    ticked = [lst.item(i).text() for i in range(lst.count())
                              if lst.item(i).checkState()
                              == Qt.CheckState.Checked]
                    page = _flat(dlg._view.toPlainText())[:300]
                    st[f"{run}_{door}"] = {"list": rows, "ticked": ticked,
                                           "page_starts": page}
                    d.note(f"   {run} via {door}: {len(rows)} list rows, "
                           f"{len(ticked)} ticked; page: {page[:120]!r}")
                    dlg._view.verticalScrollBar().setValue(0)
                    d.shot(dlg, f"{tag}-07-{run}-{door}")
                    dlg.close()
                    yield 1500
            # Knut's addition (5814673639): Profiling, and no run of the
            # project has a measurement. This drive's own copy of the project
            # loses its eight sheets (the dated verifications stay, and must
            # not be borrowed).
            for sheet in (d.work / EVEN / "runs").glob(f"run*/{EVEN}.ti3"):
                sheet.unlink()
            d.open_project(EVEN)
            d.set_bar(run_type="Profiling", run="run1")
            yield 1500
            d.launch_tool("measurement_report")
            yield 4000
            dlg = wait_dialog()
            if dlg is not None:
                lst = dlg._profile_list
                rows = [lst.item(i).text() for i in range(lst.count())]
                page = _flat(dlg._view.toPlainText())[:300]
                st["profiling_no_sheet"] = {"list": rows, "page_starts": page}
                d.note(f"   profiling, no sheet: {len(rows)} list rows; "
                       f"page: {page[:160]!r}")
                d.shot(dlg, f"{tag}-07-profiling-no-sheet")
                dlg.close()
                yield 1500
            d.goto_tab("chart")

        # ------------------------------------------------------------------
        if "add" in scenes:
            # Item 8 (Knut, 5815133233). (b) Report-Limits-Profile-Gamut,
            # run 1, Verification: run 2's measurements added to the list.
            # (a) the sentence beside "Report shown" at a wide and a narrow
            # width.
            sc = "add"
            st = rec["scenes"].setdefault(sc, {})
            open_window(GAMUT, "Verification", run="run1")
            yield 4000
            dlg = wait_dialog()

            def ticks():
                out = {}
                for i, (kind, _si, key) in enumerate(dlg._list_rows):
                    if kind == "run" and key:
                        out[dlg._profile_list.item(i).text().strip()] = (
                            dlg._profile_list.item(i).checkState()
                            == Qt.CheckState.Checked)
                return out
            page0 = _flat(dlg._view.toPlainText())
            st["before_add"] = {"ticks": ticks(),
                                "red_line": dlg._stale_label.isVisible(),
                                "report_shown": dlg._saved_combo.currentText()}
            dlg._view.verticalScrollBar().setValue(0)
            d.shot(dlg, f"{tag}-08b-1-before-add")
            run2 = (d.work / GAMUT / "runs" / "run2" / "verifications"
                    / "2028-06-29_100000" / f"{GAMUT}-verify.ti3")
            expecting["on"] = True
            d.later(dlg._add_btn.click)
            yield 1500
            d.answer_file(run2, name=None)
            expecting["on"] = False
            yield 4000
            page1 = _flat(dlg._view.toPlainText())
            st["after_add"] = {"ticks": ticks(),
                               "red_line": dlg._stale_label.isVisible(),
                               "page_unchanged": page1 == page0}
            check(sc, "the report text did not change on Add",
                  page1 == page0)
            new = {k: v for k, v in ticks().items()
                   if k not in st["before_add"]["ticks"]}
            check(sc, "added measurements come in unticked",
                  bool(new) and not any(new.values()), repr(new))
            dlg._view.verticalScrollBar().setValue(0)
            d.shot(dlg, f"{tag}-08b-2-after-add")
            # tick one of the added rows: the red line, the same page
            for i, (kind, _si, key) in enumerate(dlg._list_rows):
                it = dlg._profile_list.item(i)
                if kind == "run" and it.text().strip() in new:
                    it.setCheckState(Qt.CheckState.Checked)
                    break
            d.pump(1200)
            page2 = _flat(dlg._view.toPlainText())
            st["after_tick"] = {"red_line": dlg._stale_label.isVisible(),
                                "page_unchanged": page2 == page0}
            check(sc, "ticking an added row raises the red line",
                  dlg._stale_label.isVisible())
            check(sc, "and the report text still did not change",
                  page2 == page0)
            d.shot(dlg, f"{tag}-08b-3-ticked")
            # (a) the sentence beside "Report shown"
            for wname, width in (("wide", 1500), ("mid", 1100),
                                 ("narrow", 820)):
                dlg.resize(width, dlg.height())
                yield 1500
                lab = dlg._saved_hint if dlg._saved_hint.isVisible() \
                    else dlg._saved_note
                fm = lab.fontMetrics()
                lines = round(lab.heightForWidth(lab.width())
                              / fm.lineSpacing())
                st[f"hint_{wname}"] = {
                    "text": lab.text(), "full": lab.toolTip(),
                    "elided": lab.text().endswith("…"),
                    "lines": lines, "label_h": lab.height(),
                    "needed_h": lab.heightForWidth(lab.width())}
                d.note(f"   hint {wname}: {lines} lines, elided "
                       f"{lab.text().endswith('…')}, label {lab.height()} px "
                       f"for {lab.heightForWidth(lab.width())} px")
                check(sc, f"the sentence is drawn whole ({wname})",
                      lab.heightForWidth(lab.width()) <= lab.height() + 1)
                d.shot(dlg, f"{tag}-08a-hint-{wname}")
            dlg.close()
            yield 1500

        dog.stop()
        rec.pop("_dog", None)
        (d.out / "k32-found.json").write_text(
            json.dumps({k: rec[k] for k in ("checks", "scenes",
                                            "language")},
                       indent=2, ensure_ascii=False, default=str),
            encoding="utf-8")
    return script


def main() -> int:
    out = Path(sys.argv[1])
    language = sys.argv[2] if len(sys.argv) > 2 else "en"
    scenes = tuple(sys.argv[3:]) or ALL
    from userdrive import Drive
    d = Drive(out, projects=[EVEN, EVERY, GAMUT], language=language)
    return d.run(script_for(scenes, language))


if __name__ == "__main__":
    raise SystemExit(main())
